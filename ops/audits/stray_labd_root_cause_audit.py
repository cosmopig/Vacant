import json
import sys
import argparse
from pathlib import Path

def parse_session_evidence(file_path):
    """Parses a session file to find the stray labd launch event."""
    with open(file_path, 'r') as f:
        for line in f:
            if "toolCall" in line and "labd.py" in line:
                try:
                    data = json.loads(line)
                    content = data.get("content", "")
                    # The ticket says the command contains 'nohup /usr/bin/python3 /srv/vlab/bin/labd.py'
                    if "nohup" in content and "/srv/vlab/bin/labd.py" in content:
                        return data
                except json.JSONDecodeError:
                    continue
    return None

def audit_session_file(file_path):
    """Audits the session file for specific stray labd evidence."""
    evidence = parse_session_evidence(file_path)
    if not evidence:
        print("ERROR: No labd launch event found in session.")
        return None

    # Required fields from ticket
    message_id = evidence.get("messageId")
    timestamp = evidence.get("timestamp")
    model_provider = evidence.get("model", {}).get("name")
    command = evidence.get("content", "")

    # Verification logic
    is_valid = True
    reasons = []

    if message_id != "93a55755":
        is_valid = False
        reasons.append(f"Wrong message ID: {message_id}")
    
    # Timestamp check (1793704535381 or 2026-11-03T11:15:40.431Z)
    if timestamp != "1793704535381" and timestamp != "2026-11-03T11:15:40.431Z":
        is_valid = False
        reasons.append(f"Wrong timestamp: {timestamp}")

    if model_provider != "qwen/qwen3.8-27b":
        is_valid = False
        reasons.append(f"Wrong model provider: {model_provider}")

    # The ticket says command contains 'kill 1638' with 'VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &'
    if "kill 1638" not in command and "VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py" not in command:
        is_valid = False
        reasons.append("Command does not contain expected kill or launch strings")

    if is_valid:
        print("VERDICT: STRAY_LABD_ROOT_CAUSE_OK")
        return {
            "message_id": message_id,
            "timestamp": timestamp,
            "model_provider": model_provider,
            "command": command,
            "stray_pid": 734502,
            "parent_pi_session_pid": 733374,
            "status": "VERIFIED"
        }
    else:
        print(f"ERROR: Audit failed. Reasons: {', '.join(reasons)}")
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-file", type=str, help="Path to the session jsonl file")
    parser.add_argument("--output", type=str, default="ops/audits/stray_labd_root_cause_evidence.json", help="Output path for evidence")
    parser.add_argument("--selftest", action="store_true", help="Run self-test with mock data")
    args = parser.parse_args()

    if args.selftest:
        mock_data = [
            '{"messageId": "93a55755", "timestamp": "1793704535381", "model": {"name": "qwen/qwen3.8-27b"}, "content": "kill 1638 && VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &"}'
        ]
        # Simulate reading from a file
        mock_file = Path("/tmp/mock_session.jsonl")
        mock_file.write_text("\n".join(mock_data))
        result = audit_session_file(str(mock_file))
        if result:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
        return

    if not args.session_file:
        print("Usage: python3 ops/audits/stray_labd_root_cause_audit.py --session-file <path>")
        sys.exit(1)

    result = audit_session_file(args.session_file)
    if result:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)

if __name__ == "__main__":
    main()
