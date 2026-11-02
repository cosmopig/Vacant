import json
from pathlib import Path

def main():
    exp = "e010_bigwork_pi_AC"
    base_path = Path(f"/srv/vlab/runs/{exp}")
    results = []
    
    # Find all cells (directories containing cell.json)
    for p in base_path.iterdir():
        if p.is_dir() and (p / "cell.json").exists():
            cell_data = json.loads((p / "cell.json").read_text())
            score_data = json.loads((p / "score.json").read_text())
            
            arm = cell_data.get("arm")
            task = cell_data.get("task")
            pass_status = score_data.get("pass", False)
            wall_s = cell_data.get("wall_s", 0)
            
            # C arm specific metrics
            vacant_home = cell_data.get("vacant_home_bytes", 0)
            vacant_objs = cell_data.get("vacant_objects_bytes", 0)
            
            results.append({
                "task": task,
                "arm": arm,
                "pass": pass_status,
                "wall_s": wall_s,
                "vacant_home_bytes": vacant_home,
                "vacant_objects_bytes": vacant_objs,
                "cell_path": str(p)
            })

    # Print summary for audit
    print(f"{'Task':<30} | {'Arm':<2} | {'Pass':<5} | {'WallS':<8} | {'HomeBytes':<15} | {'ObjBytes':<15}")
    print("-" * 90)
    for r in sorted(results, key=lambda x: x["task"]):
        print(f"{r['task'][:30]:<30} | {r['arm']:<2} | {str(r['pass']):<5} | {r['wall_s']:<8.2f} | {r['vacant_home_bytes']:<15} | {r['vacant_objects_bytes']:<15}")

if __name__ == "__main__":
    main()
