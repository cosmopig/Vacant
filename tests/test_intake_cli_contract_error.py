import subprocess
import pytest

def test_check_no_contract_returns_2():
    # Create a temp directory with no .vacant folder
    tmp = subprocess.run(["mktemp", "-d"], capture_output=True, text=True).stdout.strip()
    subprocess.run(f"cd {tmp} && vacant check", shell=True, capture_output=True)
    assert subprocess.run(f"cd {tmp} && vacant check", shell=True, capture_output=True).returncode == 2

def test_check_nonexistent_contract_returns_2():
    # This should return RC 2 as per the ticket requirements
    res = subprocess.run(["vacant", "check", "--contract", "/nonexistent/contract.json"], capture_output=True)
    assert res.returncode == 2

def test_check_no_contract_json_returns_2():
    tmp = subprocess.run(["mktemp", "-d"], capture_output=True, text=True).stdout.strip()
    res = subprocess.run(f"cd {tmp} && vacant check --json", shell=True, capture_output=True)
    assert res.returncode == 2

def test_submit_no_contract_returns_2():
    tmp = subprocess.run(["mktemp", "-d"], capture_output=True, text=True).stdout.strip()
    res = subprocess.run(f"cd {tmp} && vacant submit", shell=True, capture_output=True)
    assert res.returncode == 2

def test_check_success_returns_0():
    # Create a valid contract to ensure normal path works
    tmp = subprocess.run(["mktemp", "-d"], capture_output=True, text=True).stdout.strip()
    subprocess.run(f"mkdir -p {tmp}/.vacant && echo '{{\"task_id\": \"test\", \"version\": 1, \"claims\": [{{\"id\": \"c1\", \"verifier\": \"v1\", \"required\": true}}], \"release\": {{}}}}' > {tmp}/.vacant/contract.json", shell=True)
    res = subprocess.run(f"cd {tmp} && vacant check", shell=True, capture_output=True)
    assert res.returncode == 0

def test_check_nonexistent_contract_no_regression():
    # Ensure --contract /nonexistent/c.json still returns 2 (consistency anchor)
    res = subprocess.run(["vacant", "check", "--contract", "/nonexistent/c.json"], capture_output=True)
    assert res.returncode == 2
