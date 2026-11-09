"""COD order-confirmation voice agent.

    uv run bot.py                 # browser call over WebRTC: open http://localhost:7860
    uv run bot.py -t livekit      # join a LiveKit room (local server from docker-compose)

Speech-to-text (Whisper MLX) and text-to-speech (Kokoro) run locally;
Claude decides what to say and which tool to call; every action is written to Postgres.
"""

import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent / "src"))

from pipecat.audio.vad.silero import SileroVADAnalyzer  # noqa: E402
from pipecat.frames.frames import LLMRunFrame  # noqa: E402
from pipecat.pipeline.pipeline import Pipeline  # noqa: E402
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy  # noqa: E402
from pipecat.processors.aggregators.llm_context import LLMContext  # noqa: E402
from pipecat.processors.aggregators.llm_response_universal import (  # noqa: E402
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments  # noqa: E402
from pipecat.runner.utils import create_transport  # noqa: E402
from pipecat.services.anthropic.llm import AnthropicLLMService  # noqa: E402
from pipecat.services.kokoro.tts import KokoroTTSService  # noqa: E402
from pipecat.services.whisper.stt import MLXModel, WhisperSTTServiceMLX  # noqa: E402
from pipecat.transcriptions.language import Language  # noqa: E402
from pipecat.transports.base_transport import BaseTransport, TransportParams  # noqa: E402
from pipecat.transports.livekit.transport import LiveKitParams  # noqa: E402
from pipecat.workers.runner import WorkerRunner  # noqa: E402

from cod_agent.prompts import system_prompt  # noqa: E402
from cod_agent.store import OrderStore  # noqa: E402
from cod_agent.tools import build_tools  # noqa: E402

load_dotenv(override=True)

LANG = os.getenv("AGENT_LANGUAGE", "en")
VOICES = {"en": ("af_heart", Language.EN), "fr": ("ff_siwis", Language.FR)}

transport_params = {
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    "livekit": lambda: LiveKitParams(audio_in_enabled=True, audio_out_enabled=True),
}


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    store = OrderStore(os.environ["DATABASE_URL"])
    order = await store.start_call(os.getenv("ORDER_ID"))
    if order is None:
        logger.warning("No pending orders to confirm.")
        return
    logger.info(f"Calling {order.customer_name} about {order.id}")

    voice, language = VOICES.get(LANG, VOICES["en"])
    stt = WhisperSTTServiceMLX(
        settings=WhisperSTTServiceMLX.Settings(model=MLXModel.LARGE_V3_TURBO.value, language=language)
    )
    tts = KokoroTTSService(settings=KokoroTTSService.Settings(voice=voice, language=language))
    llm = AnthropicLLMService(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        settings=AnthropicLLMService.Settings(
            model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"),
            system_instruction=system_prompt(order, date.today(), LANG),
        ),
    )

    context = LLMContext(tools=build_tools(store, order.id))
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context, user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer())
    )

    pipeline = Pipeline([
        transport.input(),
        stt,
        user_aggregator,
        llm,
        tts,
        transport.output(),
        assistant_aggregator,
    ])

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
        processor_unusable_policy=ProcessorUnusablePolicy.END,
    )
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        context.add_message({"role": "developer", "content": "The customer picked up. Start the call."})
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await store.log(order.id, "customer_hung_up")
        await runner.cancel()

    await runner.run()


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
