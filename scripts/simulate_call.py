"""Text-only rehearsal of a confirmation call: the real agent prompt and tools
against a simulated customer (also Claude), writing to the real database.

    uv run scripts/simulate_call.py CMD-1044 "You moved last week. New address: Residence Al Andalous, apt 9, Gueliz. Prefer Thursday."

Useful as a quick regression check of the prompt + tool flow without a microphone.
"""

import asyncio
import os
import sys
from datetime import date
from pathlib import Path

from anthropic import AsyncAnthropic
from dotenv import load_dotenv

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from pipecat.adapters.llm.services.anthropic_adapter import AnthropicLLMAdapter  # noqa: E402
from pipecat.processors.aggregators.llm_context import LLMContext  # noqa: E402

from cod_agent.prompts import system_prompt  # noqa: E402
from cod_agent.store import OrderStore  # noqa: E402
from cod_agent.tools import build_tools  # noqa: E402

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
MAX_TURNS = 14


class Params:
    def __init__(self):
        self.result = None
        self.pipeline_worker = None

    async def result_callback(self, result, *, properties=None):
        self.result = result


async def main(order_id: str, persona: str):
    client = AsyncAnthropic()
    store = OrderStore(os.environ["DATABASE_URL"])
    order = await store.start_call(order_id)
    tools = {fn.__name__: fn for fn in build_tools(store, order.id) if fn.__name__ != "end_call"}
    tool_schemas = AnthropicLLMAdapter().to_provider_tools_format(LLMContext(tools=build_tools(store, order.id)).tools)

    agent_system = system_prompt(order, date.today())
    customer_system = (
        f"You are {order.customer_name}, answering a phone call about your online order {order.id} "
        f"({', '.join(i['name'] for i in order.items)}). {persona} "
        "Reply like a real person on the phone: one or two short sentences, no stage directions."
    )

    agent_msgs = [{"role": "user", "content": "(The customer picked up. Start the call.)"}]
    customer_msgs = []
    for _ in range(MAX_TURNS):
        resp = await client.messages.create(model=MODEL, max_tokens=400, system=agent_system,
                                            tools=tool_schemas, messages=agent_msgs)
        agent_msgs.append({"role": "assistant", "content": resp.content})
        said = " ".join(b.text for b in resp.content if b.type == "text").strip()
        if said:
            print(f"\nAGENT:    {said}")
        calls = [b for b in resp.content if b.type == "tool_use"]
        if calls:
            results = []
            for call in calls:
                if call.name == "end_call":
                    print("          [end_call]")
                    await store.log(order.id, "call_ended")
                    return
                p = Params()
                await tools[call.name](p, **call.input)
                print(f"          [{call.name}({call.input}) -> {p.result}]")
                results.append({"type": "tool_result", "tool_use_id": call.id, "content": str(p.result)})
            agent_msgs.append({"role": "user", "content": results})
            continue

        customer_msgs.append({"role": "user", "content": said or "(silence)"})
        reply = await client.messages.create(model=MODEL, max_tokens=150, system=customer_system,
                                             messages=customer_msgs)
        heard = " ".join(b.text for b in reply.content if b.type == "text").strip()
        customer_msgs.append({"role": "assistant", "content": heard})
        print(f"CUSTOMER: {heard}")
        agent_msgs.append({"role": "user", "content": heard})
    print("\n(stopped: too many turns)")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "You are happy with the order."))
