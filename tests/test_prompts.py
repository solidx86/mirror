"""Contract validators for the prompt layer.

The prompts are the product (CLAUDE.md). These tests pin the contracts the
plumbing depends on: the global-layer substitution, the readiness sentinel
shared between the intake prompt and the parser node, the reflection JSON
schema fields the renderer reads, and the anti-sycophancy clauses that define
the system's voice.
"""
import re
from pathlib import Path

SENTINEL = "READY_FOR_REFLECTION"

# Fields the Parse Reflection node renders into the Telegram message.
REFLECTION_SCHEMA_FIELDS = [
    "stress_present",
    "stress_level",
    "thought_record",
    "automatic_thought",
    "cognitive_distortions",
    "evidence_for",
    "evidence_against",
    "balanced_thought",
    "controllability",
    "rumination_flag",
    "one_observation",
    "one_question",
]

ANTI_SYCOPHANCY_MARKERS = [
    "That's totally understandable",
    "amazing/incredible/powerful",
    '"buddy", "friend", "you got this"',
]


def prompt(repo_root, name):
    return (repo_root / "prompts" / name).read_text()


def test_global_prompt_is_a_layer_not_a_consumer(repo_root):
    assert "{{_global}}" not in prompt(repo_root, "_global_v1.md")


def test_agent_prompts_include_global_layer(repo_root):
    for name in ("intake_v1.md", "reflect_stress_v1.md"):
        assert prompt(repo_root, name).startswith("{{_global}}"), name


def test_loader_nodes_reference_existing_prompt_files(repo_root, workflow):
    """Every /files/prompts/*.md path read by a code node must exist in prompts/."""
    referenced = set()
    for n in workflow["nodes"]:
        referenced |= set(
            re.findall(r"/files/prompts/([\w.]+\.md)", n["parameters"].get("jsCode", ""))
        )
    assert referenced, "expected loader nodes to reference prompt files"
    missing = {f for f in referenced if not (repo_root / "prompts" / f).exists()}
    assert not missing


def test_sentinel_contract_is_shared(repo_root, workflow):
    """The intake prompt emits the sentinel; the parser node must look for the
    exact same string. A mismatch silently breaks the readiness gate."""
    assert SENTINEL in prompt(repo_root, "intake_v1.md")
    parser = next(n for n in workflow["nodes"] if n["name"] == "Parse Intake Response")
    assert SENTINEL in parser["parameters"]["jsCode"]


def test_reflection_prompt_defines_fields_the_renderer_reads(repo_root, workflow):
    text = prompt(repo_root, "reflect_stress_v1.md")
    for field in REFLECTION_SCHEMA_FIELDS:
        assert field in text, field
    renderer = next(n for n in workflow["nodes"] if n["name"] == "Parse Reflection")
    code = renderer["parameters"]["jsCode"]
    for field in ("stress_present", "rumination_flag", "thought_record", "one_question"):
        assert field in code, field


def test_reflection_prompt_demands_bare_json(repo_root):
    text = prompt(repo_root, "reflect_stress_v1.md")
    assert "STRICT VALID JSON" in text
    assert "NO MARKDOWN CODE FENCES" in text


def test_anti_sycophancy_clauses_present(repo_root):
    """The system's voice is a feature; these clauses must not be softened away."""
    text = prompt(repo_root, "_global_v1.md")
    for marker in ANTI_SYCOPHANCY_MARKERS:
        assert marker in text, marker


def test_prompt_files_are_versioned(repo_root):
    names = [p.name for p in (repo_root / "prompts").glob("*.md")]
    assert names
    unversioned = [n for n in names if not re.search(r"_v\d+\.md$", n)]
    assert not unversioned
