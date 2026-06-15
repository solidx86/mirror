-- Project Mirror — MVP schema (Postgres)

CREATE TABLE IF NOT EXISTS entries (
  id SERIAL PRIMARY KEY,
  telegram_chat_id BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  concluded_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','concluded','cancelled')),
  raw_transcript TEXT NOT NULL DEFAULT '',
  turn_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_entries_chat ON entries(telegram_chat_id, created_at DESC);

CREATE TABLE IF NOT EXISTS reflections (
  id SERIAL PRIMARY KEY,
  entry_id INTEGER NOT NULL REFERENCES entries(id),
  agent TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  model TEXT NOT NULL,
  output_json TEXT NOT NULL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reflections_entry ON reflections(entry_id);

CREATE TABLE IF NOT EXISTS sessions (
  telegram_chat_id BIGINT PRIMARY KEY,
  entry_id INTEGER REFERENCES entries(id),
  state TEXT NOT NULL DEFAULT 'idle'
    CHECK(state IN ('idle','awaiting_intake','reflecting')),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS llm_calls (
  id SERIAL PRIMARY KEY,
  agent TEXT NOT NULL,
  model TEXT NOT NULL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  latency_ms INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
