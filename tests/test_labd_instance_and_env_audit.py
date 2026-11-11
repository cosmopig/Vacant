import json
import os

# Mocking the environment for testing
def test_audit_run_dir_no_violations():
    # Create a dummy directory with no violations
    test_dir = "test_audit_ok"
    os.makedirs(test_dir, exist_ok=True)
    cell_path = os.path.join(test_dir, "cell.json")
    with open(cell_path, 'w') as f:
        json.dump({
            "arm": "A",
            "agent_env": {
                "SOME_VAR": "some_value",
                "OTHER_VAR": 123
            }
        }, f)

    from ops.audits.labd_instance_and_env_audit import audit_run_dir
    results = audit_run_dir(test_dir)
    assert results["violations"] == 0
    assert results["total_cells"] == 1
    os.remove(cell_path)
    os.rmdir(test_dir)

def test_audit_run_dir_with_violations():
    # Create a dummy directory with violations
    test_dir = "test_audit_fail"
    os.makedirs(test_dir, exist_ok=True)
    cell_path = os.path.join(test_dir, "cell.json")
    with open(cell_path, 'w') as f:
        json.dump({
            "arm": "A",
            "agent_env": {
                "VACANT_SECRET": "leak",
                "PI_SELF": "host_info"
            }
        }, f)

    from ops.audits.labd_instance_and_env_audit import audit_run_dir
    results = audit_run_dir(test_dir)
    assert results["violations"] == 1
    assert results["total_cells"] == 1
    os.remove(cell_path)
    os.rmdir(test_dir)

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
