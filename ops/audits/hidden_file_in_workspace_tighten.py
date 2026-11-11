import argparse
import hashlib
import pathlib
import tarfile
import json
import sys

def get_non_trivial_lines(content: str) -> list[str]:
    """Removes empty lines and comments."""
    lines = content.splitlines()
    result = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Remove trailing commas/semicolons which are common in code but might differ slightly
        line = line.rstrip(',;')
        result.append(line)
    return result

def calculate_content_hash(content: str) -> str:
    """Hash of the non-trivial lines, sorted for determinism."""
    lines = get_non_trivial_lines(content)
    if not lines:
        return "empty"
    # Sort to ensure deterministic hash regardless of order (though usually it's ordered)
    return hashlib.sha256("".join(sorted(lines)).encode()).hexdigest()

def audit_workspace(ws_path: pathlib.Path, task: dict) -> list[dict]:
    violations = []
    hidden_lits_hashes = set()
    hidden_lits_lines = set()
    visible_lits_hashes = set()
    visible_lits_lines = set()
    
    hid_dir = pathlib.Path(task.get("hidden_dir", "."))
    vis_dir = pathlib.Path(task.get("visible_dir", "."))
    
    # Load hidden/visible lits
    for p in hid_dir.glob("test_*.py"):
        content = p.read_text(encoding="utf-8")
        lines = get_non_trivial_lines(content)
        hidden_lits_hashes.add(calculate_content_hash(content))
        hidden_lits_lines |= {line for line in lines}
    for p in vis_dir.glob("test_*.py"):
        content = p.read_text(encoding="utf-8")
        lines = get_non_trivial_lines(content)
        visible_lits_hashes.add(calculate_content_hash(content))
        visible_lits_lines |= {line for line in lines}

    archives = list(ws_path.glob("*.tar.gz"))
    for arc in archives:
        try:
            with tarfile.open(arc, "r:gz") as tf:
                members = tf.getmembers()
                for m in members:
                    low = m.name.lower()
                    if "hidden" in low or "rubric" in low:
                        content = ""
                        if m.isfile():
                            try:
                                with tf.extractfile(m) as fh:
                                    content = fh.read().decode("utf-8", "replace")
                            except: pass
                        
                        c_hash = calculate_content_hash(content)
                        # If it's in hidden_lits, it's a confirmed violation
                        if c_hash in hidden_lits_hashes:
                            violations.append({
                                "rule": "CONFIRMED_VIOLATION",
                                "archive": arc.name,
                                "member": m.name,
                                "evidence": {
                                    "sha256": c_hash,
                                    "is_hidden_lit": True
                                }
                            })
                        else:
                            # Check for false positive (model-built)
                            candidate_lines = get_non_trivial_lines(content)
                            overlap = [line for line in candidate_lines if line in hidden_lits_lines]
                            
                            if len(overlap) == 0:
                                violations.append({
                                    "rule": "FALSE_POSITIVE_BENIGN",
                                    "archive": arc.name,
                                    "member": m.name,
                                    "evidence": {
                                        "sha256": c_hash,
                                        "non_trivial_overlap": 0,
                                        "is_model_built": True
                                    }
                                })
                            else:
                                violations.append({
                                    "rule": "SUSPECTED_LEAK",
                                    "archive": arc.name,
                                    "member": m.name,
                                    "evidence": {
                                        "sha256": c_hash,
                                        "non_trivial_overlap": len(overlap)
                                    }
                                })
        except Exception as e:
            violations.append({
                "rule": "workspace_archive_unreadable",
                "archive": arc.name,
                "error": str(e)
            })
    return violations

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--audit-r530", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        mock_task = {
            "hidden_dir": pathlib.Path("./mock_hidden"),
            "visible_dir": pathlib.Path("./mock_visible"),
            "task_id": "mock_test"
        }
        mock_task["hidden_dir"].mkdir(parents=True, exist_ok=True)
        mock_task["visible_dir"].mkdir(parents=True, exist_ok=True)
        
        # Hidden lit: 1 line of content
        with open(mock_task["hidden_dir"] / "test_hidden.py", "w") as f:
            f.write("solve_val = 42\n")
        # Visible lit: 1 line of content
        with open(mock_task["visible_dir"] / "test_visible.py", "w") as f:
            f.write("solve_val = 10\n")
        
        ws = pathlib.Path("./mock_ws")
        ws.mkdir(parents=True, exist_ok=True)
        # Confirmed violation (exact match of non-trivial lines)
        with open(ws / "test_hidden.py", "w") as f:
            f.write("solve_val = 42\n")
        # Benign false positive (suspicious name, different content, no overlap)
        with open(ws / "test_hidden_fake.py", "w") as f:
            f.write("solve_val = 99\n")
        # Suspect leak (suspicious name, some overlap)
        with open(ws / "test_suspect.py", "w") as f:
            f.write("solve_val = 42\n# Some comment\n")

        tar_path = pathlib.Path("./mock_ws.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(ws / "test_hidden.py", arcname="test_hidden.py")
            tf.add(ws / "test_hidden_fake.py", arcname="test_hidden_fake.py")
            tf.add(ws / "test_suspect.py", arcname="test_suspect.py")
        
        results = audit_workspace(pathlib.Path("./mock_ws"), mock_task)
        has_confirmed = any(r["rule"] == "CONFIRMED_VIOLATION" for r in results)
        has_benign = any(r["rule"] == "FALSE_POSITIVE_BENIGN" for r in results)
        has_suspect = any(r["rule"] == "SUSPECTED_LEAK" for r in results)

        if has_confirmed and has_benign and has_suspect:
            print("VERDICT: HIDDEN_FILE_TIGHTEN_OK")
            sys.exit(0)
        else:
            # Debug output to see what's happening
            for r in results:
                print(f"Result: {r}")
            print(f"VERDICT: FAIL (Confirmed: {has_confirmed}, Benign: {has_benign}, Suspect: {has_suspect})")
            sys.exit(1)

    if args.audit_r530:
        # Real audit logic for R530
        print("Audit R530 not implemented in this mock - requires real run data.")
        sys.exit(1)

if __name__ == "__main__":
    main()
