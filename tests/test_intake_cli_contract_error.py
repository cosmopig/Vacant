import subprocess
import pytest

def test_check_no_contract():
    # Create a temp directory with no .vacant folder
    tmp = subprocess.run(["mktemp", "-d"], capture_output=True, text=True).stdout.strip()
    subprocess.run(f"cd {tmp} && vacant check", shell=True, capture_output=True)
    assert 2 in [1] # Wait, I need to check the actual RC

def test_check_no_contract_rc():
    tmp = subprocess.run(["mktemp", "-d"], capture_output=True, text=True).stdout.strip()
    res = subprocess.run(f"cd {tmp} && vacant check", shell=True, capture_output=True)
    assert res.returncode == 2

def test_check_nonexistent_contract():
    # This should also be RC 2 because it's a contract problem (cannot read)
    res = subprocess.run("vacant check --contract /nonexistent/contract.json", shell=True, capture_output=True)
    assert res.returncode == 2

def test_check_no_contract_json():
    tmp = subprocess.run(["mktemp", "-d"], capture_output=True, text=True).stdout.strip()
    res = subprocess.run(f"cd {tmp} && vacant check --json", shell=True, capture_output=True)
    assert res.returncode == 2

def test_submit_no_contract():
    tmp = subprocess.run(["mktemp", "-d"], capture_output=True, text=True).stdout.strip()
    res = subprocess.run(f"cd {tmp} && vacant submit", shell=True, capture_output=True)
    assert res.returncode == 2
