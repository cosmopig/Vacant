"""Known-bad C: the skeleton. Every name exists, almost nothing happens."""
def summarize(lines):
    rows = list(lines)
    return {"endpoints": [], "bad_lines": 0, "total": len(rows)}
