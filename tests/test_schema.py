"""Schema and fixture validators."""
import re

EXPECTED_TABLES = {"entries", "reflections", "sessions", "llm_calls"}

# Sections every journal export (and therefore the synthetic sample) carries.
REQUIRED_ENTRY_SECTIONS = ["## Transcript", "## Stress Reflection"]
REQUIRED_REFLECTION_FIELDS = [
    "**Stress level:**",
    "**Situation:**",
    "**Automatic thought:**",
    "**Balanced thought:**",
    "**Controllability:**",
]


def test_schema_defines_expected_tables(repo_root):
    sql = (repo_root / "scripts" / "schema.sql").read_text()
    found = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql))
    assert found == EXPECTED_TABLES


def test_llm_calls_table_stores_metadata_only(repo_root):
    """Privacy invariant: the audit log records model/tokens/latency, never
    prompt or journal content."""
    sql = (repo_root / "scripts" / "schema.sql").read_text()
    block = re.search(r"CREATE TABLE IF NOT EXISTS llm_calls \((.*?)\);", sql, re.S)
    assert block
    columns = {
        line.strip().split()[0]
        for line in block.group(1).splitlines()
        if line.strip() and not line.strip().startswith("--")
    }
    assert columns == {"id", "agent", "model", "input_tokens", "output_tokens",
                       "latency_ms", "created_at"}


def test_workflow_persists_to_known_tables(workflow, repo_root):
    sql = " ".join(
        n["parameters"].get("query", "")
        for n in workflow["nodes"]
        if n["type"] == "n8n-nodes-base.postgres"
    )
    written = set(re.findall(r"INSERT INTO\s+(\w+)", sql))
    written |= set(re.findall(r"(?<!DO )UPDATE\s+(\w+)\s+SET", sql))
    assert written <= EXPECTED_TABLES, written - EXPECTED_TABLES


def test_sample_entry_conforms_to_export_format(repo_root):
    text = (repo_root / "examples" / "sample-entry.md").read_text()
    assert "SYNTHETIC" in text.splitlines()[0]
    for section in REQUIRED_ENTRY_SECTIONS:
        assert section in text, section
    for field in REQUIRED_REFLECTION_FIELDS:
        assert field in text, field
    assert "READY_FOR_REFLECTION" in text  # transcript shows the sentinel handoff
