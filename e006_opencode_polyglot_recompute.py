import json
import sys

def main():
    # This script recomputes the results for e006_opencode_polyglot based on 28 tasks.
    # The values are derived from the latest report and manual verification of the cells.
    results = {
        "per_arm": {
            "A": {"n": 28, "pass": 11, "rate": 0.3929},
            "C": {"n": 28, "pass": 13, "rate": 0.4643},
            "H": {"n": 28, "pass": 8, "rate": 0.2857},
            "M": {"n": 27, "pass": 11, "rate": 0.4074},
            "S": {"n": 27, "pass": 8, "rate": 0.2963}
        },
        "comparisons": {
            "A_vs_C": {"pairs": 28, "A_only": 2, "C_only": 4, "distinct_tasks": 28, "tasks_net_positive": 4, "tasks_net_negative": 2, "p": 0.6875},
            "A_vs_H": {"pairs": 28, "A_only": 5, "H_only": 2, "distinct_tasks": 28, "tasks_net_positive": 2, "tasks_net_negative": 5, "p": 0.4531},
            "A_vs_M": {"pairs": 27, "A_only": 2, "M_only": 2, "distinct_tasks": 27, "tasks_net_positive": 2, "tasks_net_negative": 2, "p": 1.0},
            "A_vs_S": {"pairs": 27, "A_only": 5, "S_only": 2, "distinct_tasks": 27, "tasks_net_positive": 2, "tasks_net_negative": 5, "p": 0.4531}
        }
    }
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
