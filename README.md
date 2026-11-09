# COD Voice Agent

A real-time voice agent that calls cash-on-delivery customers to confirm their order before it ships: it reads back the items and total, checks the address, books a delivery day, or records a cancellation reason. Every decision is written to PostgreSQL.

In Moroccan e-commerce most orders are cash on delivery, and stores pay call-center agents to confirm each one by phone because unconfirmed orders get refused at the door. This project automates that call.

Built with **Pipecat** (pipeline), **LiveKit** or WebRTC (audio transport), **Whisper large-v3-turbo on MLX** (speech-to-text, local), **Kokoro** (text-to-speech, local), **Claude** (conversation and tool calls) and **PostgreSQL**.

```
mic ─▶ transport (WebRTC | LiveKit) ─▶ Silero VAD ─▶ Whisper (local) ─▶ Claude ─▶ Kokoro (local) ─▶ speaker
                                                                         │
                                                                   tool calls
                                                                         ▼
                                              confirm_order · update_address · reschedule_order
                                              cancel_order · end_call  ──▶  PostgreSQL (orders, call_events)
```

## What it handles

- Reads the order from the database and greets the customer by name.
- Confirms items and the cash amount, spoken naturally ("two hundred forty nine dirhams").
- Address changes: asks for the full address, reads it back, saves it, and logs the old value.
- Delivery booking with business rules: tomorrow to 7 days ahead, no Sundays. Invalid dates come back to the model as errors, so it asks again instead of saving bad data.
- Cancellations with a normalised reason (`found_cheaper`, `did_not_order`, ...).
- Barge-in: the customer can interrupt the agent mid-sentence.
- English or French (`AGENT_LANGUAGE=fr`).

## Run it

Requirements: Apple Silicon Mac (for MLX Whisper), Docker, [uv](https://docs.astral.sh/uv/), an Anthropic API key.

```bash
docker compose up -d                 # Postgres (with demo orders) + LiveKit dev server
cp .env.example .env                 # add ANTHROPIC_API_KEY
uv sync

uv run bot.py                        # open http://localhost:7860 and click Connect
uv run dashboard.py                  # http://localhost:7870 shows orders and agent actions live
```

LiveKit instead of direct WebRTC:

```bash
uv run bot.py -t livekit             # joins a room on ws://localhost:7880 (keys devkey / secret)
```

The first start downloads the Whisper (about 1.6 GB) and Kokoro models.

## Tests

```bash
uv run pytest                        # business rules + tool handlers against Postgres
uv run scripts/simulate_call.py CMD-1044 "You moved last week and want delivery on Thursday."
```

`simulate_call.py` runs the real prompt and tools in text mode against a simulated customer (also Claude), which makes prompt changes quick to check without a microphone.

## Layout

```
bot.py                  Pipecat pipeline and transports
dashboard.py            live orders / events page
src/cod_agent/rules.py  delivery-date, address and cancel-reason rules (pure, unit tested)
src/cod_agent/store.py  Postgres access; every action is logged in call_events
src/cod_agent/tools.py  tools the LLM calls
src/cod_agent/prompts.py system prompt built from the order
db/                     schema and fictional demo orders
```

## Next steps

- Phone calls through a SIP trunk (LiveKit SIP or Twilio) instead of the browser.
- Moroccan Darija: needs a speech-to-text and voice model that handle it well.
- Retry policy for `no_answer` orders and a daily confirmation-rate report.
