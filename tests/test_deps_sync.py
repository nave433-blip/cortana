"""Pins dependency declarations in sync across pyproject.toml, setup.py,
and core/deps.py — and pins the removal of genuinely unused packages.
"""
import ast
import re
import tomllib
from pathlib import Path

from core.deps import PYTHON_DEPS

REPO = Path(__file__).resolve().parent.parent
REMOVED_UNUSED = {"sentence-transformers", "pillow", "botocore", "boto3"}


def _norm(name: str) -> str:
    return re.split(r"[<>=!~; ]", name.strip(), 1)[0].strip().lower()


def _pyproject_deps():
    with open(REPO / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return {_norm(d) for d in data["project"]["dependencies"]}


def _setup_py_deps():
    src = (REPO / "setup.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "install_requires":
            return {_norm(e.value) for e in node.value.elts if isinstance(e, ast.Constant)}
    raise AssertionError("install_requires not found in setup.py")


def test_unused_packages_stay_removed():
    assert not (REMOVED_UNUSED & _pyproject_deps()), "unused dep back in pyproject.toml"
    assert not (REMOVED_UNUSED & _setup_py_deps()), "unused dep back in setup.py"
    assert not (REMOVED_UNUSED & {k.lower() for k in PYTHON_DEPS}), "unused dep back in deps.py"


def test_dep_sources_in_sync():
    assert _pyproject_deps() == _setup_py_deps(), (
        "pyproject.toml and setup.py disagree: "
        f"{_pyproject_deps() ^ _setup_py_deps()}"
    )


def test_runtime_check_covers_declared_deps():
    # Everything the installer may check should be a declared dependency
    # (modulo pip-name vs import-name differences, compared case-insensitively).
    declared = _pyproject_deps()
    checked = {k.lower() for k in PYTHON_DEPS}
    assert checked <= declared, (
        f"deps.py checks undeclared packages: {checked - declared}"
    )
