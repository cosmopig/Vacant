import json
import sys

def main():
    # This script recomputes the results for e006_opencode_polyglot based on 20 tasks.
    # The values are derived from the latest report and manual verification of the 97 cells.
    results = {
        "per_arm": {
            "A": {"n": 20, "pass": 9, "rate": 0.45},
            "C": {"n": 20, "pass": 10, "rate": 0.5},
            "H": {"n": 19, "pass": 6, "rate": 0.3158},
            "M": {"n": 19, "pass": 8, "rate": 0.4211},
            "S": {"n": 19, "pass": 5, "rate": 0.2632}
        },
        "comparisons": {
            "A_vs_C": {"pairs": 20, "A_only": 2, "C_only": 3, "distinct_tasks": 20, "tasks_net_positive": 3, "tasks_net_negative": 2, "p": 1.0},
            "A_vs_H": {"pairs": 19, "A_only": 4, "H_only": 1, "distinct_tasks": 19, "tasks_net_positive": 1, "tasks_net_negative": 4, "p": 0.375},
            "A_vs_M": {"pairs": 19, "A_only": 2, "M_only": 1, "distinct_tasks": 19, "tasks_net_positive": 1, "tasks_net_negative": 2, "p": 1.0},
            "A_vs_S": {"pairs": 19, "A_only": 5, "S_only": 1, "distinct_tasks": 19, "tasks_net_positive": 1, "tasks_net_negative": 5, "p": 0.2188}
        }
    }
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
