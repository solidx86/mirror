# Architecture walkthrough

The runtime is a single n8n workflow (28 nodes). The exported JSON in `workflows/`
is hard to review by eye; this page is the human-readable map. The test suite
(`tests/test_workflow.py`) machine-checks the same graph on every push.

## The pipeline

```
Telegram Trigger
  → Authz + Parse          code     allowlist on chat id (ships as 0 = bootstrap mode)
  → Get Session            postgres one-row state machine per chat: idle | awaiting_intake | reflecting
  → Route                  code     command + state → route decision
  → Switch on Route
      ├─ /start            → static reply
      ├─ /journal          → Open Entry (postgres upsert) → opening prompt
      ├─ /cancel           → Cancel Entry → reply
      ├─ idle fallback     → reply
      └─ append intake     → the agent loop, below
```

## The agent loop (cheap model gates the expensive one)

```
Append User Turn           postgres  transcript += message
Load Intake Prompt         code      reads /files/prompts/intake_v1.md, substitutes {{_global}}
Intake Agent               http      claude-haiku-4-5 — one conversational question per turn
Parse Intake Response      code      checks for the READY_FOR_REFLECTION sentinel
Escape Assistant Text      code      single-quote doubling — see "SQL convention" below
Append Assistant Turn      postgres
Ready for Reflection?      if
  ├─ NO  → send next question to Telegram (loop continues on the user's reply)
  └─ YES → "reflecting" notice → Mark Reflecting (postgres)
           Load Reflect Prompt     code
           Stress Reflection       http   claude-sonnet-4-6 — structured decision review as strict JSON (thought-record format, from CBT)
           Parse Reflection        code   JSON.parse with fence-stripping fallback;
                                          renders rumination / no-stress / full-record variants
           Escape Reflection Text  code
           Persist Reflection      postgres  reflections + llm_calls + close entry + reset session
           Export Markdown         code   archive/YYYY/MM/DD-entry-N.md
           Send reflection         telegram
```

Design choice: the intake model is ~10× cheaper than the reflection model and runs
5–10 turns per entry; the reflection model runs exactly once, and only when the
intake model emits the sentinel. The sentinel is an exact string contract between
a prompt file and a parser node — `tests/test_prompts.py::test_sentinel_contract_is_shared`
pins it.

## SQL convention (why no parameter binding)

The n8n Postgres node's `$1` binding proved unreliable, so values are inlined.
Every LLM-generated string passes through a dedicated Escape node
(`split("'").join("''")`) and reaches SQL only as a `safe_*` field; numbers and
ids are inlined bare with `::bigint` casts. Two tests enforce this end-to-end:
no `$1` anywhere, and every `safe_*` consumed in SQL is produced by an escaping
node.

## State machine

`sessions` holds one row per chat (`telegram_chat_id` PK). States:
`idle → awaiting_intake → reflecting → idle`. `/cancel` short-circuits back to
idle and marks the entry cancelled. Crash mid-reflection leaves state
recoverable by inspection — no distributed anything, deliberately.

## Failure handling

- Reflection output that fails `JSON.parse` is stored raw (`parse_error` kept),
  the user gets a graceful fallback message, and the transcript is preserved.
- A `rumination_flag` in the reflection suppresses re-analysis of a repeating
  stress theme and sends a distancing question instead — an anti-loop guard at
  the prompt layer.
