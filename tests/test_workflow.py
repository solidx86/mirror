"""Graph-integrity and convention validators for the n8n workflow snapshot.

n8n CE gives no static checking: a connection naming a missing node, a Postgres
query using unreliable $1 binding, or unescaped LLM text inlined into SQL all
fail silently at runtime. These tests are the compile step the platform lacks.
"""
import re

# Workflow shape as shipped. A structural edit (Class B in CLAUDE.md) must
# update these pins deliberately — that is the point.
EXPECTED_NODE_COUNT = 28
EXPECTED_NODE_TYPES = {
    "n8n-nodes-base.code",
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.if",
    "n8n-nodes-base.postgres",
    "n8n-nodes-base.switch",
    "n8n-nodes-base.telegram",
    "n8n-nodes-base.telegramTrigger",
}

# Pre-existing violations would be pinned here; keep these empty.
KNOWN_DANGLING_CONNECTIONS = set()
KNOWN_UNSAFE_SQL_NODES = set()


def iter_connection_targets(workflow):
    for source, outputs in workflow["connections"].items():
        yield source
        for branches in outputs.values():
            for branch in branches:
                for conn in branch:
                    yield conn["node"]


def test_workflow_parses_and_has_expected_shape(workflow):
    assert len(workflow["nodes"]) == EXPECTED_NODE_COUNT
    assert {n["type"] for n in workflow["nodes"]} == EXPECTED_NODE_TYPES


def test_every_connection_references_an_existing_node(workflow):
    names = {n["name"] for n in workflow["nodes"]}
    dangling = set(iter_connection_targets(workflow)) - names
    assert dangling == KNOWN_DANGLING_CONNECTIONS


def test_no_orphan_nodes(workflow):
    """Every node except the trigger must be reachable in the connection graph."""
    wired = set(iter_connection_targets(workflow))
    triggers = {n["name"] for n in workflow["nodes"] if "Trigger" in n["type"]}
    orphans = {n["name"] for n in workflow["nodes"]} - wired - triggers
    assert not orphans


def test_postgres_queries_avoid_dollar_binding(workflow):
    """Project convention: $1 binding is unreliable in the n8n Postgres node;
    values are inlined after explicit escaping instead (see CLAUDE.md)."""
    offenders = {
        n["name"]
        for n in workflow["nodes"]
        if n["type"] == "n8n-nodes-base.postgres"
        and re.search(r"\$\d", n["parameters"].get("query", ""))
    }
    assert offenders == KNOWN_UNSAFE_SQL_NODES


def test_llm_text_reaches_sql_only_via_escaped_fields(workflow):
    """Any field interpolated inside SQL string literals must come from a
    safe_* property produced by an escaping code node."""
    offenders = set()
    for n in workflow["nodes"]:
        if n["type"] != "n8n-nodes-base.postgres":
            continue
        query = n["parameters"].get("query", "")
        for field in re.findall(r"'\{\{\s*\$json\.(\w+)\s*\}\}'", query):
            if not field.startswith("safe_"):
                offenders.add((n["name"], field))
    assert offenders == set()


def test_escaping_nodes_exist_for_every_safe_field(workflow):
    """Every safe_* field consumed in SQL is produced by a code node that
    performs the single-quote doubling escape."""
    consumed = set()
    for n in workflow["nodes"]:
        if n["type"] == "n8n-nodes-base.postgres":
            consumed |= set(
                f
                for f in re.findall(
                    r"\{\{\s*\$json\.(safe_\w+)\s*\}\}", n["parameters"].get("query", "")
                )
            )
    produced = set()
    for n in workflow["nodes"]:
        code = n["parameters"].get("jsCode", "")
        if "split(\"'\").join(\"''\")" in code:
            produced |= set(re.findall(r"(safe_\w+)\s*:", code))
    assert consumed <= produced, f"unescaped fields: {consumed - produced}"


def test_no_credential_secrets_in_snapshot(workflow):
    """n8n strips secrets on export; credentials blocks may only carry id+name."""
    for n in workflow["nodes"]:
        for cred in n.get("credentials", {}).values():
            assert set(cred.keys()) <= {"id", "name"}, n["name"]


def test_authz_chat_id_is_placeholder(workflow):
    """The allowlisted Telegram chat id ships as the documented bootstrap
    placeholder, never a real id."""
    authz = next(n for n in workflow["nodes"] if n["name"] == "Authz + Parse")
    match = re.search(r"ALLOWED_CHAT_ID\s*=\s*(\d+)", authz["parameters"]["jsCode"])
    assert match and match.group(1) == "0"


def test_anthropic_calls_use_credential_auth(workflow):
    """LLM HTTP nodes must authenticate via the n8n credential, not headers."""
    llm_nodes = [
        n for n in workflow["nodes"] if n["type"] == "n8n-nodes-base.httpRequest"
    ]
    assert llm_nodes, "expected HTTP Request nodes for the LLM calls"
    for n in llm_nodes:
        assert "api.anthropic.com" in str(n["parameters"].get("url", ""))
        assert "anthropicApi" in n.get("credentials", {}), n["name"]
