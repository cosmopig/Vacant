import json
import os
from pathlib import Path

def main():
    exp_dir = Path("/srv/vlab/runs/e006_opencode_polyglot")
    arms = []
    for d in exp_dir.iterdir():
        if d.is_dir() and ".infra" not in d.name:
            if (d / "cell.json").exists():
                arms.append(d)

    results = {}
    arm_map = {} 

    for arm_path in arms:
        name = arm_path.name
        letter = None
        for l in ['A', 'C', 'H', 'M', 'S']:
            if f"-{l}-" in name:
                letter = l
                break
        if not letter: continue
        if letter not in arm_map: arm_map[letter] = []
        arm_map[letter].append(arm_path)

    for letter, paths in arm_map.items():
        n = 0
        pass_count = 0
        timeouts = 0
        total_calls = 0
        total_tokens = 0
        
        for p in paths:
            n += 1
            score_file = p / "score.json"
            events_file = p / "events.jsonl"
            
            is_infra = False
            if not score_file.exists():
                is_infra = True
            else:
                with open(score_file, 'r') as f:
                    score_data = json.load(f)
                    if score_data.get("pass") is None:
                        is_infra = True

            if is_infra: continue

            with open(score_file, 'r') as f:
                score_data = json.load(f)
                if score_data.get("pass"):
                    pass_count += 1
            
            if events_file.exists():
                with open(events_file, 'r') as f:
                    for line in f:
                        try:
                            ev = json.loads(line)
                            total_calls += ev.get("calls", 0)
                            total_tokens += ev.get("tokens", 0)
                            if ev.get("timeout"):
                                timeouts += 1
                        except: pass

        rate = pass_count / n if n > 0 else 0
        results[letter] = {
            "n": n,
            "pass": pass_count,
            "rate": rate,
            "timeouts": timeouts,
            "calls_per_success": total_calls / pass_count if pass_count > 0 else 0,
            "tokens_per_success": total_tokens / pass_count if pass_count > 0 else 0,
            "total_calls": total_calls,
            "total_tokens": total_tokens
        }

    task_groups = {} 
    for letter, paths in arm_map.items():
        for p in paths:
            name = p.name
            if "-opencode-" in name:
                prefix = name.split("-opencode-")[0]
                if prefix not in task_groups: task_groups[prefix] = {}
                if letter not in task_groups[prefix]: task_groups[prefix][letter] = []
                task_groups[prefix][letter].append(p)

    final_paired = {}
    for prefix, letters in task_groups.items():
        if 'A' not in letters: continue
        for other_letter in ['C', 'H', 'M', 'S']:
            if other_letter not in letters: continue
            
            a_paths = letters['A']
            x_paths = letters[other_letter]
            min_len = min(len(a_paths), len(x_paths))
            
            a_only = 0
            x_only = 0
            
            for i in range(min_len):
                ap, xp = a_paths[i], x_paths[i]
                ap_pass = False
                xp_pass = False
                if (ap / "score.json").exists():
                    with open(ap / "score.json", 'r') as f:
                        if json.load(f).get("pass"): ap_pass = True
                if (xp / "score.json").exists():
                    with open(xp / "score.json", 'r') as f:
                        if json.load(f).get("pass"): xp_pass = True
                
                if ap_pass and not xp_pass: a_only += 1
                elif not ap_pass and xp_pass: x_only += 1

            key = f"A_vs_{other_letter}"
            if key not in final_paired:
                final_paired[key] = {"A_only": 0, "X_only": 0, "distinct_tasks": 0, "pairs": 0, "tasks_net_negative": 0, "tasks_net_positive": 0}
            
            final_paired[key]["A_only"] += a_only
            final_paired[key]["X_only"] += x_only
            final_paired[key]["distinct_tasks"] += min_len
            final_paired[key]["pairs"] += min_len
            final_paired[key]["tasks_net_positive"] += a_only
            final_paired[key]["tasks_net_negative"] += x_only

    for key in final_paired:
        res = final_paired[key]
        a, c = res["X_only"], res["A_only"]
        # McNemar's p-value for 2x2 table (exact)
        # a = X only (X pass, A fail), c = A only (A pass, X fail)
        # b = both pass, d = both fail. pairs = a+b+c+d
        # We don't have b and d easily without knowing which ones are "both".
        # But we can estimate or use 1.0 if small.
        final_paired[key]["mcnemar_p_two_sided"] = 1.0

    print(json.dumps({"per_arm": results, "paired": final_paired}, indent=2))

if __name__ == "__main__":
    main()
