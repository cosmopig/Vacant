"""Weekly hours report."""
import argparse
import json

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def summarize(rows):
    out = {}
    for r in rows:
        out[r["name"]] = out.get(r["name"], 0) + r["hours"]
    return out

def render_text(summary):
    return "\n".join(f"{k}: {v:.1f}h" for k, v in sorted(summary.items()))

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("data")
    a = p.parse_args(argv)
    print(render_text(summarize(load(a.data))))

if __name__ == "__main__":
    main()
