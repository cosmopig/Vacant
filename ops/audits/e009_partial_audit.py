import os
import json
import re
from pathlib import Path

def main():
    base_dir = Path("/srv/vlab/runs/e009_replicate_e002_AC/")
    complete_count = 0
    infra_count = 0
    in_progress_count = 0
    anomalies = []

    # L002 questions for early signals
    l002_questions = [
        "pg_bowling", "pg_connect", "pg_list_ops",
        "pg_pig_latin", "pg_react", "pg_transpose", "pg_wordy"
    ]
    # Track status: {question_name: {"A": pass_count, "C": pass_count}}
    signals = {q: {"A": 0, "C": 0} for q in l002_questions}

    # Scan directories
    for entry in os.scandir(base_dir):
        if not entry.is_dir():
            continue
        
        path = Path(entry.path)
        name = path.name
        
        has_score = (path / "score.json").exists()
        # Prompt: "*.infra-* directory = infra"
        # Looking at ls output, it seems they are siblings of the cell dir.
        is_complete = has_score
        is_infra = False
        if not is_complete and ".infra-" in name:
            is_infra = True

        if is_complete:
            complete_count += 1
            try:
                cell_json = json.loads((path / "cell.json").read_text())
                score_json = json.loads((path / "score.json").read_text())
                
                # a. cell.json and score.json are valid JSON (already checked by loads)
                
                # b. cell.json.metrics exists, model_calls and input_tokens non-null
                metrics = cell_json.get("metrics")
                if metrics is None:
                    anomalies.append(f"{name}: missing metrics in cell.json")
                else:
                    mc = metrics.get("model_calls")
                    it = metrics.get("input_tokens")
                    if mc is None or it is None:
                        anomalies.append(f"{name}: model_calls or input_tokens is null in cell.json.metrics")

                # c. arm == "C" -> vacant_sha non-empty
                arm = cell_json.get("arm")
                if arm == "C":
                    v_sha = cell_json.get("vacant_sha")
                    if not v_sha or str(v_sha).strip() == "":
                        anomalies.append(f"{name}: arm is C but vacant_sha is empty")

                # d. cell.json.arm / cell.json.rep match name ...-pi-{A,C}-r{n}
                match = re.search(r"-pi-(A|C)-r\d+$", name)
                if match:
                    name_arm = match.group(1)
                    if arm != name_arm:
                        anomalies.append(f"{name}: cell.json.arm ({arm}) does not match directory name ({name_arm})")

                # Update signals for L002
                for q in l002_questions:
                    if q in name:
                        if score_json.get("pass"):
                            signals[q][arm] += 1
            except Exception as e:
                anomalies.append(f"{name}: error parsing JSON - {str(e)}")

        elif is_infra:
            infra_count += 1
            # Prompt says "讀 infra.json.why". Let's check if it exists or if it's just infra.json
            # Based on ls, there are directories like ...-pi-A-r2.infra-...
            # Inside those dirs, we look for infra.json (which might contain why)
            infra_file = path / "infra.json"
            if infra_file.exists():
                try:
                    with open(infra_file) as f:
                        content = f.read()
                except: pass

        else:
            in_progress_count += 1

    print(f"Complete: {complete_count}")
    print(f"Infra: {infra_count}")
    print(f"In Progress: {in_progress_count}")
    print("\nAnomalies:")
    for a in anomalies:
        print(a)

    print("\nL002 Early Signals (PARTIAL):")
    print(f"{'Question':<25} | {'A Pass?':<8} | {'C Pass?':<8}")
    print("-" * 45)
    for q, s in signals.items():
        # The prompt says "就目前已 complete 的 A/C 格，列出每題 A pass?／C pass?"
        # If a question was never seen in any complete cell, it stays 0/0.
        print(f"{q:<25} | {s['A']:<8} | {s['C']:<8}")

if __name__ == "__main__":
    main()
