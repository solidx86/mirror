"""Golden-fixture validation of the reflection agent's output contract.

The prompt (prompts/reflect_stress_v1.md) specifies a strict JSON schema; the
renderer node assumes it. This validates the synthetic golden fixture against
that schema — the same checks would reject a malformed live output.
"""
import json

DISTORTION_VOCAB = {
    "catastrophising", "mind_reading", "fortune_telling", "all_or_nothing",
    "personalisation", "should_statements", "emotional_reasoning",
    "filtering", "labeling",
}
CONTROLLABILITY_VOCAB = {"controllable", "partial", "not_controllable", None}

THOUGHT_RECORD_FIELDS = {
    "situation": str,
    "automatic_thought": str,
    "emotion": str,
    "emotion_intensity": int,
    "cognitive_distortions": list,
    "evidence_for": str,
    "evidence_against": str,
    "balanced_thought": str,
    "projected_emotion_intensity": int,
}


def validate_reflection(data):
    """Schema check mirroring prompts/reflect_stress_v1.md. Returns error list."""
    errors = []

    def expect(cond, msg):
        if not cond:
            errors.append(msg)

    expect(isinstance(data.get("stress_present"), bool), "stress_present: bool")
    expect(isinstance(data.get("rumination_flag"), bool), "rumination_flag: bool")
    expect(isinstance(data.get("one_observation"), str) and data["one_observation"],
           "one_observation: non-empty str")
    expect(isinstance(data.get("one_question"), str) and data["one_question"],
           "one_question: non-empty str")
    expect(data.get("controllability") in CONTROLLABILITY_VOCAB,
           f"controllability: {data.get('controllability')!r} not in vocab")

    level = data.get("stress_level")
    expect(level is None or (isinstance(level, int) and 1 <= level <= 10),
           "stress_level: 1-10 or null")

    tr = data.get("thought_record")
    if tr is not None:
        for field, ftype in THOUGHT_RECORD_FIELDS.items():
            expect(isinstance(tr.get(field), ftype), f"thought_record.{field}: {ftype.__name__}")
        for key in ("emotion_intensity", "projected_emotion_intensity"):
            if isinstance(tr.get(key), int):
                expect(1 <= tr[key] <= 10, f"thought_record.{key}: 1-10")
        unknown = set(tr.get("cognitive_distortions", [])) - DISTORTION_VOCAB
        expect(not unknown, f"unknown distortions: {unknown}")
    elif data.get("stress_present") and not data.get("rumination_flag"):
        errors.append("thought_record may be null only when stress_present is "
                      "false or rumination_flag is true")
    return errors


def test_golden_fixture_conforms_to_reflection_schema(repo_root):
    data = json.loads((repo_root / "examples" / "sample-reflection.json").read_text())
    assert validate_reflection(data) == []


def test_validator_rejects_malformed_output():
    """The validator itself must have teeth."""
    bad = {"stress_present": True, "rumination_flag": False, "thought_record": None,
           "one_observation": "x", "one_question": "y", "controllability": "maybe",
           "stress_level": 14}
    errors = validate_reflection(bad)
    assert len(errors) >= 3
