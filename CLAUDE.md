# CLAUDE.md — Mirror

Mirror is a private, single-user, two-agent journaling system: Telegram → n8n → Claude agents → Postgres, with markdown export. Phase 1 (intake + reflection) is shipped and in daily use. Do not propose multi-tenant features, user accounts, or public deployment surface — the single-user constraint is a design feature.

## Source of truth

- `prompts/*.md` — the agent prompts. **Prompts are the product**; the rest is plumbing. Diff them in git, version them (`_v1.md` → `_v2.md`), never overwrite a version in place.
- `workflows/mirror-workflow.json` — exported n8n workflow snapshot (28 nodes). The visual graph in n8n is the runtime truth; this file is the audit trail.
- `scripts/schema.sql` — Postgres schema: `entries`, `reflections`, `sessions`, `llm_calls`.
- `README.md` — architecture diagram and data-file provenance.

## Editing rules

**Prompts:** mounted read-only into n8n at `/files/prompts/`; re-read on every run, no restart needed. `_global_v1.md` is prepended via `{{_global}}` substitution in the Load-Prompt code nodes. If an agent's output schema changes, bump the prompt filename version and update the loader node + `prompt_version` in the Persist node.

**Workflow JSON — two classes of edits:**
- *Class A (edit the JSON directly):* code-node JS bodies, SQL query strings, Telegram text, HTTP body templates, prompt file paths. After editing: re-import into n8n (Workflows → Import from File) and re-attach credentials to touched nodes — n8n CE strips them on import.
- *Class B (do NOT edit the JSON):* adding/removing nodes, renaming, rewiring `connections`, anything touching `credentials`. Make these in the n8n UI, then export and overwrite the JSON. n8n CE regenerates IDs on import and a small mistake silently breaks the graph.

After every workflow change of either class: export from n8n, overwrite the JSON, commit.

**Postgres writes containing LLM text:** do not use `$1` parameter binding (unreliable in the n8n Postgres node). Pre-escape in a code node — `safeText = (text || '').split("'").join("''")` — then inline `'{{ $json.safe_field }}'`. Cast chat ids: `{{ $json.chat_id }}::bigint`.

**Schema changes:** `scripts/schema.sql` runs only on first container init. To alter a live database, write a numbered migration (`scripts/migrations/NNN_description.sql`), apply it with `docker exec -i mirror-postgres psql -U mirror -d mirror < scripts/migrations/NNN_description.sql`, and fold the change into `schema.sql` in the same commit so fresh installs match.

**LLM calls:** HTTP Request nodes against `https://api.anthropic.com/v1/messages` with the `anthropicApi` credential and `anthropic-version: 2023-06-01`. Intake runs Haiku; reflection runs Sonnet. New agent = copy the Intake node, change model + prompt loader.

## Privacy invariants (non-negotiable)

- `archive/` and `backups/` are **gitignored** here; journal content lives in a separate private repo (`archive/` is a nested git repo — see `scripts/backup.sh`).
- `.env`, `data/`, `n8n-data/` are gitignored.
- `llm_calls` logs metadata only (model, tokens, latency) — never prompt content.
- `tests/test_privacy.py` denylist-scans every tracked file; it must stay green before any push.

## Tests & CI

```bash
python3 -m venv .venv && .venv/bin/pip install pytest && .venv/bin/pytest
```

Deterministic validators only (no network, no API keys): workflow-graph integrity, prompt/sentinel contracts, schema presence, privacy denylist, sample-entry format. CI runs the same suite via GitHub Actions (`.github/workflows/ci.yml`). Keep the suite green; new drift should fail loudly rather than be pinned.

## Working philosophy

- The system is a thinking partner, not a cheerleader. Anti-sycophancy clauses in the prompts are load-bearing — refuse changes that soften them.
- Decision quality > outcome quality; education > instruction (agents ask, not tell).
- Resist scope creep: before adding a feature, ask whether the payoff lands within a week and whether journaling actually surfaced the friction it solves.

## Common commands

```bash
docker compose up -d                                   # run the stack
docker exec -it mirror-postgres psql -U mirror -d mirror   # DB shell
docker logs -f mirror-n8n                              # tail n8n
./scripts/backup.sh                                    # journal data → private backup repo
```
