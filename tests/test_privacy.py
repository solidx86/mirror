"""Privacy regression suite.

This repo is the public face of a system whose entire purpose is processing
private journal content. Journal data lives in a separate private repo;
nothing personal may appear in any tracked file. This suite is the tripwire
for accidental leaks in future commits.
"""
import re

# Patterns that must never appear in a tracked file. Mix of credential
# formats and markers of real journal content.
DENYLIST = [
    (re.compile(r"\b\d{8,10}:AA[\w-]{30,}"), "telegram bot token"),
    (re.compile(r"sk-ant-[\w-]{20,}"), "anthropic api key"),
    (re.compile(r"\b(sk|ghp|gho|xoxb|xoxp)-[A-Za-z0-9]{20,}"), "api token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws key"),
    (re.compile(r"ALLOWED_CHAT_ID\s*=\s*[1-9]\d*"), "real telegram chat id"),
]

REQUIRED_IGNORES = [".env", "data/", "n8n-data/", "archive/", "backups/"]

# Dirs whose presence in git would mean journal data got tracked.
FORBIDDEN_TRACKED_PREFIXES = ("archive/", "backups/", "data/", "n8n-data/")


def test_no_denylisted_patterns_in_tracked_files(tracked_files, repo_root):
    hits = []
    for path in tracked_files:
        try:
            text = path.read_text(errors="ignore")
        except (IsADirectoryError, FileNotFoundError):
            continue
        for pattern, label in DENYLIST:
            if pattern.search(text):
                hits.append((str(path.relative_to(repo_root)), label))
    assert not hits


def test_no_personal_data_directories_tracked(tracked_files, repo_root):
    tracked = {str(p.relative_to(repo_root)) for p in tracked_files}
    leaked = {p for p in tracked if p.startswith(FORBIDDEN_TRACKED_PREFIXES)}
    assert not leaked


def test_gitignore_covers_personal_data(repo_root):
    ignored = (repo_root / ".gitignore").read_text()
    missing = [entry for entry in REQUIRED_IGNORES if entry not in ignored]
    assert not missing


def test_transcripts_only_in_marked_synthetic_files(tracked_files, repo_root):
    """A '## Transcript' section is the signature of a journal export. Any
    tracked file containing one must be explicitly marked synthetic."""
    for path in tracked_files:
        if path.suffix != ".md":
            continue
        text = path.read_text(errors="ignore")
        if "## Transcript" in text:
            assert "SYNTHETIC" in text, str(path.relative_to(repo_root))


def test_env_template_contains_no_real_values(repo_root):
    for line in (repo_root / "env.template").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            value = line.split("=", 1)[1].strip()
            assert value == "" or value.startswith("replace_me"), line
