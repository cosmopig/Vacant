import os
import json
import argparse
from pathlib import Path

def calculate_cost(jsonl_path):
    model_calls = 0
    input_tokens = 0
    output_tokens = 0
    
    if not jsonl_path.exists():
        return model_calls, input_tokens, output_tokens

    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("type") == "message":
                    usage = data.get("message", {}).get("usage", {})
                    if usage:
                        model_calls += 1
                        input_tokens += usage.get("input_tokens", 0)
                        output_tokens += usage.get("output_tokens", 0)
                        # cacheReadInputTokens is also part of input side
                        input_tokens += usage.get("cacheReadInputTokens", 0)
            except json.JSONDecodeError:
                continue
    return model_calls, input_tokens, output_tokens

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=str, required=True, help="Base directory for cells")
    parser.add_argument("--out", type=str, required=True, help="Output directory for costs")
    parser.add_argument("--main-calls", type=int, default=0)
    parser.add_argument("--main-in", type=int, default=0)
    parser.add_argument("--main-out", type=int, default=0)
    args = parser.parse_args()

    base_path = Path(args.base)
    results = []

    # Find all unique cell names from both base and archive
    cell_names = set()
    for p in base_path.glob("*/"):
        if p.is_dir():
            cell_names.add(p.name)
    out_path = Path(args.out)
    for p in out_path.glob("*/"):
        if p.is_dir():
            cell_names.add(p.name)

    for cell_name in sorted(list(cell_names)):
        sessions_dir = base_path / cell_name / "home" / ".pi" / "agent" / "sessions"
        archive_cell_path = out_path / cell_name / "sessions"
        
        final_calls = 0
        final_in = 0
        final_out = 0
        final_files = []

        # If archive exists, use it as primary source
        if archive_cell_path.exists():
            for jsonl_file in archive_cell_path.rglob("*.jsonl"):
                c, i, o = calculate_cost(jsonl_file)
                final_calls += c
                final_in += i
                final_out += o
                final_files.append(str(jsonl_file.relative_to(archive_cell_path)))
        elif sessions_dir.exists():
            for jsonl_file in sessions_dir.rglob("*.jsonl"):
                c, i, o = calculate_cost(jsonl_file)
                final_calls += c
                final_in += i
                final_out += o
                final_files.append(str(jsonl_file.relative_to(sessions_dir)))

        # Calculate diff
        diff_calls = final_calls - args.main_calls
        diff_in = final_in - args.main_in
        diff_out = final_out - args.main_out
        
        note = ""
        if diff_calls < 0 or diff_in < 0 or diff_out < 0:
            note = "差為負：會話檔計法與 events.jsonl 不一致，需人工核對"
            diff_calls = max(0, diff_calls)
            diff_in = max(0, diff_in)
            diff_out = max(0, diff_out)

        results.append({
            "cell": cell_name,
            "files": final_files,
            "model_calls": diff_calls,
            "input_tokens": diff_in,
            "output_tokens": diff_out,
            "note": note
        })

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
