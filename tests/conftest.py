import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root():
    return REPO_ROOT


@pytest.fixture(scope="session")
def workflow():
    paths = sorted(REPO_ROOT.glob("workflows/*.json"))
    assert len(paths) == 1, f"expected exactly one workflow snapshot, found {paths}"
    return json.loads(paths[0].read_text())


@pytest.fixture(scope="session")
def tracked_files():
    """Every file git considers part of the repo — the public surface."""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True
    )
    paths = [REPO_ROOT / p for p in out.stdout.decode().split("\0") if p]
    assert paths, "git ls-files returned nothing"
    return paths
