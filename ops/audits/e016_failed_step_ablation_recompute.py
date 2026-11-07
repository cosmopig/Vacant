import json
from pathlib import Path

def get_arm_data(exp_dir, arm_name):
    # Find the directory for this arm
    arm_path = None
    for d in Path(exp_dir).iterdir():
        if arm_name in str(d):
            arm_path = d
            break
    if not arm_path:
        return None

    cell_file = arm_path / "cell.json"
    score_file = arm_path / "score.json"
    events_file = arm_path / "events.jsonl"

    # Cell data for env/sha checks
    cell_data = {}
    if cell_file.exists():
        with open(cell_file, 'r') as f:
            cell_data = json.load(f)

    # Score data for pass/n/calls/tokens
    score_data = {}
    if score_file.exists():
        with open(score_file, 'r') as f:
            score_data = json.load(f)

    # Aggregate results from all cells in this arm directory
    n_valid = 0
    pass_count = 0
    total_calls = 0
    total_tokens = 0
    timeouts = 0
    vacant_shas = []
    agent_env = {}

    # The score.json structure seems to be a dict of cells or just the stats
    if isinstance(score_data, dict):
        if 'pass' in score_data and not any(isinstance(v, dict) for v in score_data.values()):
            n_valid = score_data.get('n', 0)
            if n_valid == 0 and (score_data.get('pass') is not None):
                n_valid = 1
            pass_count = score_data.get('pass', 0) if score_data.get('pass') is not None else 0
            if pass_count > 0 or (score_data.get('pass') is not None):
                total_calls += score_data.get('calls_per_success', 0)
                total_tokens += score_data.get('tokens_per_success', 0)
            timeouts = score_data.get('timeouts', 0)
        else:
            for k, v in score_data.items():
                if not isinstance(v, dict): continue
                n_valid += v.get('n', 0)
                pass_count += v.get('pass', 0) if v.get('pass') is not None else 0
                if v.get('pass') is not None:
                    total_calls += v.get('calls_per_success', 0)
                    total_tokens += v.get('tokens_per_success', 0)
                timeouts += v.get('timeouts', 0)

    # If n is still 0 but we have a score.json and pass is not None, it's likely n=1
    if n_valid == 0 and (pass_count > 0 or (score_data.get('pass') is not None)):
        n_valid = 1

    # Extract env and shas from cell.json
    if cell_data:
        for k, v in cell_data.items():
            if isinstance(v, dict):
                vacant_shas.extend(v.get('vacant_sha', []))
                agent_env.update(v.get('agent_env', {}))

    return {
        "n": n_valid,
        "pass": pass_count,
        "calls_per_success": total_calls,
        "tokens_per_success": total_tokens,
        "timeouts": timeouts,
        "vacant_sha": vacant_shas,
        "agent_env": agent_env
    }

def main():
    # Use the path from STATE.md / instructions
    exp_dir = "/home/user1/dev/wt/worker/ops/audits/fixtures/e016_cell_cost"
    arms = ["A", "C"]
    results = {}

    for arm in arms:
        data = get_arm_data(exp_dir, arm)
        if data:
            # If n is 0 but we have a score.json and pass is not None, it's likely n=1
            # This was already handled in get_arm_data but let's be safe.
            results[arm] = data
        else:
            print(f"Warning: Could not find data for arm {arm}")

    final_stats = {}
    for arm, d in results.items():
        n = d['n']
        p = d['pass']
        rate = p / n if n > 0 else 0
        
        calls_per_success = d['calls_per_success'] if (p > 0) else None
        tokens_per_success = d['tokens_per_success'] if (p > 0) else None

        final_stats[arm] = {
            "n": n,
            "pass": p,
            "rate": rate,
            "calls_per_success": calls_per_success,
            "tokens_per_success": tokens_per_success,
            "vacant_sha": d['vacant_sha'],
            "agent_env": d['agent_env']
        }

    print(json.dumps(final_stats, indent=2))

if __name__ == "__main__":
    main()
