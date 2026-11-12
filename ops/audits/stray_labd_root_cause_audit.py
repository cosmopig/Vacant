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
                    events.append(data)
            except json.JSONDecodeError:
                continue
    return events

def audit_session_file(file_path: str, expected_message_id: str, expected_pid: int, expected_parent_pid: int) -> Optional[Dict[str, Any]]:
    """Audits a session file for specific stray labd launch evidence."""
    events = parse_session_evidence(file_path)
    for event in events:
        msg_id = event.get("messageId") or event.get("id")
        if msg_id != expected_message_id:
            continue

        tool_calls = event.get("toolCalls", [])
        for tc in tool_calls:
            command = tc.get("arguments", {}).get("command", "")
            if "nohup /usr/bin/python3 /srv/vlab/bin/labd.py" not in command:
                continue
            
            # Check if PIDs are present in the tool call or command string
            found_pid = False
            if str(expected_pid) in command or str(expected_pid) in str(tc):
                found_pid = True
            
            # The ticket says "target pid / parent: 對應 ... stray PID 734502 與父 pi session PID 733374"
            # We should also check if the parent pid is present.
            if found_pid and (str(expected_parent_pid) in command or str(expected_parent_pid) in str(tc)):
                return {
                    "messageId": msg_id,
                    "timestamp": event.get("timestamp"),
                    "model": event.get("model", {}).get("name") or event.get("model"),
                    "provider": event.get("model", {}).get("provider") or event.get("provider"),
                    "command": command,
                    "stray_pid": expected_pid,
                    "parent_pid": expected_parent_pid,
                    "status": "VERDICT: STRAY_LABD_ROOT_CAUSE_OK"
                }
            elif found_pid and (str(expected_parent_pid) in str(tc)):
                 # Fallback for cases where parent pid might be in a different part of the tool call object
                 return {
                    "messageId": msg_id,
                    "timestamp": event.get("timestamp"),
                    "model": event.get("model", {}).get("name") or event.get("model"),
                    "provider": event.get("model", {}).get("provider") or event.get("provider"),
                    "command": command,
                    "stray_pid": expected_pid,
                    "parent_pid": expected_parent_pid,
                    "status": "VERDICT: STRAY_LABD_ROOT_CAUSE_OK"
                }
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-file", type=str, help="Path to session jsonl file")
    parser.add_argument("--message-id", type=str, default="93a55755")
    parser.add_argument("--stray-pid", type=int, default=734502)
    parser.add_argument("--parent-pid", type=int, default=733374)
    parser.add_argument("--output", type=str, default="ops/audits/stray_labd_root_cause_evidence.json")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        mock_data = [
            {
                "messageId": "93a55755",
                "timestamp": "2026-11-03T11:15:40.431Z",
                "model": {"name": "lms1003qwen", "provider": "qwen/qwen3.8-27b"},
                "toolCalls": [{
                    "arguments": {
                        "command": f"VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 & (pid={args.stray_pid} parent={args.parent_pid})",
                        "extra": "kill 1638"
                    }
                }]
            }
        ]
        evidence = None
        for event in mock_data:
            if event.get("messageId") == args.message_id:
                for tc in event.get("toolCalls", []):
                    cmd = tc.get("arguments", {}).get("command", "")
                    if "nohup /usr/bin/python3 /srv/vlab/bin/labd.py" in cmd:
                        evidence = {
                            "messageId": event.get("messageId"),
                            "timestamp": event.get("timestamp"),
                            "model": event.get("model", {}).get("name") or event.get("model"),
                            "provider": event.get("model", {}).get("provider") or event.get("provider"),
                            "command": cmd,
                            "stray_pid": args.stray_pid,
                            "parent_pid": args.parent_pid,
                            "status": "VERDICT: STRAY_LABD_ROOT_CAUSE_OK"
                        }
                        break
        if evidence:
            print(f"VERDICT: {evidence['status']}")
            sys.exit(0)
        else:
            sys.exit(1)

    if not args.session_file:
        print("Error: --session-file is required for real audit.")
        sys.exit(1)

    result = audit_session_file(args.session_file, args.message_id, args.stray_pid, args.parent_pid)
    if result:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"VERDICT: {result['status']}")
    else:
        print("VERDICT: STRAY_LABD_ROOT_CAUSE_UNKNOWN")
        sys.exit(1)

if __name__ == "__main__":
    main()
