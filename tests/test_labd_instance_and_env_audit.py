import json
from pathlib import Path
import shutil
import os

def test_audit_run_dir():
    from ops.audits.labd_instance_and_env_audit import audit_run_dir_v2
    import shutil

    # Use a unique name to avoid collisions and ensure it's in the current directory
    test_dir = Path("./test_audit_dir_v2")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    try:
        # 1. Clean cell
        cell_path_clean = test_dir / "cell_clean.json"
        with open(cell_path_clean, 'w') as f:
            json.dump({"agent_env": {"VAR": "VAL"}}, f)
            
        # 2. Leaked cell
        cell_path_leak = test_dir / "cell_leak.json"
        with open(cell_path_leak, 'w') as f:
            json.dump({"agent_env": {"VACANT_PI_SELF": "leaked"}}, f)
            
        # 3. Infra cell (should be ignored)
        infra_dir = test_dir / ".infra-data"
        infra_dir.mkdir(parents=True, exist_ok=True)
        cell_path_infra = infra_dir / "cell.json"
        with open(cell_path_infra, 'w') as f:
            json.dump({"agent_env": {"VACANT_PI_SELF": "should_be_ignored"}}, f)

        results = audit_run_dir_v2(test_dir)
        # total_cells should be 2 because .infra-data is ignored
        assert results["total_cells"] == 2, f"Expected 2 cells, found {results['total_cells']}"
        assert len(results["violations"]) == 1
        assert len(results["clean_cells"]) == 1
        return True
    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir)

def test_audit_run_dir_e016():
    pass

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
