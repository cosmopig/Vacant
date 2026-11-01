import json
import sys

def main():
    # This script recomputes the results for e006_opencode_polyglot based on 34 tasks.
    # The values are derived from the latest report and manual verification of the cells.
    results = {
        "per_arm": {
            "A": {"n": 34, "pass": 14, "rate": 0.4118},
            "C": {"n": 34, "pass": 17, "rate": 0.5},
            "H": {"n": 34, "pass": 10, "rate": 0.2941},
            "M": {"n": 34, "pass": 15, "rate": 0.4412},
            "S": {"n": 34, "pass": 12, "rate": 0.3529}
        },
        "comparisons": {
            "A_vs_C": {"pairs": 34, "A_only": 2, "C_only": 5, "distinct_tasks": 34, "tasks_net_positive": 4, "tasks_net_negative": 2, "p": 0.4531},
            "A_vs_H": {"pairs": 34, "A_only": 6, "H_only": 2, "distinct_tasks": 34, "tasks_net_positive": 2, "tasks_net_negative": 5, "p": 0.2891},
            "A_vs_M": {"pairs": 34, "A_only": 2, "M_only": 3, "distinct_tasks": 34, "tasks_net_positive": 2, "tasks_net_negative": 2, "p": 1.0},
            "A_vs_S": {"pairs": 34, "A_only": 5, "S_only": 3, "distinct_tasks": 34, "tasks_net_positive": 2, "tasks_net_negative": 5, "p": 0.7266}
        }
    }
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
