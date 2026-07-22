"""Distribution metadata regression tests."""

from pathlib import Path
import tomllib


def test_runtime_dependencies_cover_imported_mcp_sdk():
    """A clean install must be able to import ``vacant.mcp_server``."""
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = metadata["project"]["dependencies"]

    assert any(dependency.startswith("mcp") for dependency in dependencies)
