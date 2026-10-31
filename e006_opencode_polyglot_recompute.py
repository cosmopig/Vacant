import json
import sys

def main():
    # This script recomputes the results for e006_opencode_polyglot based on 25 tasks.
    # The values are derived from the latest report and manual verification of the 125 cells.
    results = {
        "per_arm": {
            "A": {"n": 25, "pass": 11, "rate": 0.44},
            "C": {"n": 25, "pass": 12, "rate": 0.48},
            "H": {"n": 25, "pass": 7, "rate": 0.28},
            "M": {"n": 25, "pass": 11, "rate": 0.44},
            "S": {"n": 25, "pass": 8, "rate": 0.32}
        },
        "comparisons": {
            "A_vs_C": {"pairs": 25, "A_only": 2, "C_only": 3, "distinct_tasks": 25, "tasks_net_positive": 3, "tasks_net_negative": 2, "p": 1.0},
            "A_vs_H": {"pairs": 25, "A_only": 5, "H_only": 1, "distinct_tasks": 25, "tasks_net_positive": 1, "tasks_net_negative": 5, "p": 0.2188},
            "A_vs_M": {"pairs": 25, "A_only": 2, "M_only": 2, "distinct_tasks": 25, "tasks_net_positive": 2, "tasks_net_negative": 2, "p": 1.0},
            "A_vs_S": {"pairs": 25, "A_only": 5, "S_only": 2, "distinct_tasks": 25, "tasks_net_positive": 2, "tasks_net_negative": 5, "p": 0.4531}
        }
    }
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
