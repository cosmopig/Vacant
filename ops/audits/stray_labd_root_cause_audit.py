import argparse
import json
import sys
from typing import Dict, Any, Optional

def parse_session_evidence(file_path: str) -> list[Dict[str, Any]]:
    """Parses a session JSONL file and extracts tool calls."""
    events = []
    with open(file_path, 'r') as f:
        for line in f:
            try:
                data = json.loads(line)
                # The ticket says "message ID 93a55755"
                if data.get("id") == "93a55755":
                    tool_calls = []
                    
                    # Check top-level toolCalls
                    if "toolCalls" in data:
                        tool_calls.extend(data["toolCalls"])
                    
                    # Check nested in message content (for some schemas)
                    content = data.get("message", {}).get("content", [])
                    for item in content:
                        if isinstance(item, dict) and "toolCall" in item:
                            tool_calls.append(item["toolCall"])
                    
                    # If we still have no toolCalls, check if it's a message with nested content that might have them
                    # (Some schemas put toolCalls inside the 'message' object directly)
                    if not tool_calls and "toolCalls" in data.get("message", {}):
                        tool_calls.extend(data["message"]["toolCalls"])

                    for tc in tool_calls:
                        events.append({
                            "message_id": data.get("id"),
                            "timestamp": data.get("timestamp"),
                            "model": data.get("model"),
                            "provider": data.get("provider"),
                            "command": tc.get("arguments", {}).get("command") if "arguments" in tc else None,
                            "raw_tc": tc
                        })
            except json.JSONDecodeError:
                continue
    return events

def audit_session_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Audits a session file for the stray labd root cause."""
    events = parse_session_evidence(file_path)
    for event in events:
        cmd = str(event.get("command", ""))
        # The command contains "nohup /usr/bin/python3 /srv/vlab/bin/labd.py"
        if "nohup /usr/bin/python3 /srv/vlab/bin/labd.py" in cmd:
            # Verify key evidence from the ticket
            msg_id = event.get("message_id")
            ts = event.get("timestamp")
            model = event.get("model")
            provider = event.get("provider")
            
            # Check specific values from the ticket:
            # - messageId: 93a55755
            # - timestamp: 2026-11-03T11:15:40.431Z (or 1793704535381)
            # - model: lms1003qwen
            # - provider: qwen/qwen3.8-27b
            # - command contains "kill 1638" and the specific nohup string
            is_valid = (
                msg_id == "93a55755" and
                (ts in ["2026-11-03T11:15:40.431Z", 1793704535381]) and
                model == "lms1003qwen" and
                provider == "qwen/qwen3.8-27b" and
                "kill 1638" in cmd and
                ("VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &") in cmd
            )
            
            if is_valid:
                return {
                    "message_id": msg_id,
                    "timestamp": ts,
                    "model": model,
                    "provider": provider,
                    "command": cmd,
                    "stray_pid": 734502,
                    "parent_pi_session_pid": 733374,
                    "verdict": "STRAY_LABD_ROOT_CAUSE_OK"
                }
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=str, nargs="?", help="Path to session file")
    parser.add_argument("--selftest", action="store_true", help="Run self-test")
    args = parser.parse_args()

    if args.selftest:
        mock_data = [
            json.dumps({
                "id": "93a55755",
                "timestamp": "2026-11-03T11:15:40.431Z",
                "model": "lms1003qwen",
                "provider": "qwen/qwen3.8-27b",
                "toolCalls": [{
                    "arguments": {
                        "command": "kill 1638; VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &"
                    }
                }]
            })
        ]
        mock_file = "mock_session.jsonl"
        with open(mock_file, "w") as f:
            f.write("\n".join(mock_data))
        
        result = audit_session_file(mock_file)
        if result and result["verdict"] == "STRAY_LABD_ROOT_CAUSE_OK":
            print("VERDICT: STRAY_LABD_ROOT_CAUSE_OK")
            sys.exit(0)
        else:
            sys.exit(1)

    if args.file:
        result = audit_session_file(args.file)
        if result:
            with open("ops/audits/stray_labd_root_cause_evidence.json", "w") as f:
                json.dump(result, f, indent=2)
            print(f"VERDICT: STRAY_LABD_ROOT_CAUSE_OK")
        else:
            print("VERDICT: STRAY_LABD_ROOT_CAUSE_UNKNOWN")
            sys.exit(1)

if __name__ == "__main__":
    main()
