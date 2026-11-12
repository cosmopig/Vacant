import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

def parse_session_evidence(file_path: str) -> list[Dict[str, Any]]:
    """Parses a session JSONL file and extracts tool calls."""
    events = []
    with open(file_path, 'r') as f:
        for line in f:
            try:
                data = json.loads(line)
                if "toolCalls" in data:
                    for tc in data["toolCalls"]:
                        # We are looking for the specific labd launch command
                        args = tc.get("arguments", {})
                        events.append({
                            "message_id": data.get("messageId"),
                            "timestamp": data.get("timestamp"),
                            "model": data.get("model", {}).get("name") if isinstance(data.get("model"), dict) else None,
                            "provider": data.get("model", {}).get("provider") if isinstance(data.get("model"), dict) else None,
                            "command": args.get("command") if isinstance(args, dict) else None,
                            "raw_tc": tc
                        })
            except json.JSONDecodeError:
                continue
    return events

def audit_session_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Audits a session file for the stray labd root cause."""
    events = parse_session_evidence(file_path)
    for event in events:
        cmd = event.get("command") or ""
        if "nohup /usr/bin/python3 /srv/vlab/bin/labd.py" in cmd:
            msg_id = event.get("message_id")
            ts = event.get("timestamp")
            model = event.get("model")
            provider = event.get("provider")
            
            if "kill 1638" in cmd and "VLAB_PAR=1" in cmd:
                return {
                    "message_id": msg_id,
                    "timestamp": ts,
                    "model": model,
                    "provider": provider,
                    "command": cmd,
                    "status": "STRAY_LABD_ROOT_CAUSE_OK",
                    "evidence_source": file_path
                }
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-file", type=str, help="Path to session JSONL file")
    parser.add_argument("--output", type=str, default="ops/audits/stray_labd_root_cause_evidence.json", help="Output path for evidence")
    parser.add_argument("--selftest", action="store_true", help="Run self-test with mock data")
    args = parser.parse_args()

    if args.selftest:
        mock_data = [
            {
                "messageId": "93a55755",
                "timestamp": "2026-11-03T11:15:40.431Z",
                "model": {"name": "lms1003qwen", "provider": "qwen/qwen3.8-27b"},
                "toolCalls": [{
                    "arguments": {
                        "command": "kill 1638; VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &"
                    }
                }]
            }
        ]
        with open("mock_session.jsonl", "w") as f:
            for entry in mock_data:
                f.write(json.dumps(entry) + "\n")
        
        result = audit_session_file("mock_session.jsonl")
        if result and result["status"] == "STRAY_LABD_ROOT_CAUSE_OK":
            print("VERDICT: STRAY_LABD_ROOT_CAUSE_OK")
            sys.exit(0)
        else:
            print("VERDICT: FAILURE")
            sys.exit(1)

    if args.session_file:
        result = audit_session_file(args.session_file)
        if result:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
            print(f"Audit complete. Evidence saved to {args.output}")
            sys.exit(0)
        else:
            print("No matching stray labd launch found in session file.")
            sys.exit(1)

if __name__ == "__main__":
    main()
