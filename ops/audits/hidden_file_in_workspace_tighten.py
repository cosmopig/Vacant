import argparse
import hashlib
import json
import os
import tarfile
import io
from typing import List, Dict, Any

# Constants for violation types
CONFIRMED_VIOLATION = "CONFIRMED_VIOLATION"
FALSE_POSITIVE_BENIGN = "FALSE_POSITIVE_BENIGN"
SUSPECTED_LEAK = "SUSPECTED_LEAK"

def get_non_trivial_lines(content: str) -> List[str]:
    """
    Extracts non-trivial lines from a string.
    Non-trivial means: not empty, doesn't start with #, and has trailing , or ; stripped.
    """
    lines = content.splitlines()
    non_trivial = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Strip trailing commas and semicolons
        while stripped and (stripped[-1] == "," or stripped[-1] == ";"):
            stripped = stripped[:-1].strip()
        if stripped:
            non_trivial.append(stripped)
    return sorted(list(set(non_trivial)))

def get_content_hash(lines: List[str]) -> str:
    """Computes SHA256 of sorted non-trivial lines."""
    content = "\n".join(sorted(list(set(lines))))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def analyze_archive(tar_path: str, ground_truth_dir: str) -> Dict[str, Any]:
    """
    Analyzes a .tar.gz archive for hidden file leaks against a ground truth directory.
    Returns a dictionary of findings.
    """
    findings = {}
    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                
                # Identify suspicious files (containing 'hidden' or 'test_' in name)
                name = member.name
                if "hidden" in name or "test_" in name:
                    f_content = tar.extractfile(member).read().decode("utf-8", errors="ignore")
                    f_lines = get_non_trivial_lines(f_content)
                    f_hash = get_content_hash(f_lines)
                    
                    # Check against ground truth
                    match_found = False
                    for root, _, files in os.walk(ground_truth_dir):
                        for f in files:
                            f_path = os.path.join(root, f)
                            with open(f_path, "r", encoding="utf-8", errors="ignore") as gt_file:
                                gt_content = gt_file.read()
                                gt_lines = get_non_trivial_lines(gt_content)
                                if get_content_hash(gt_lines) == f_hash:
                                    match_found = True
                                    break
                        if match_found: break
                    
                    if match_found:
                        findings[name] = {
                            "type": CONFIRMED_VIOLATION,
                            "reason": "SHA256 matches ground truth hidden data."
                        }
                    else:
                        # Check for overlap
                        gt_lines_all = []
                        for root, _, files in os.walk(ground_truth_dir):
                            for f in files:
                                with open(os.path.join(root, f), "r", encoding="utf-8", errors="ignore") as gt_file:
                                    gt_lines_all.extend(get_non_trivial_lines(gt_file.read()))
                        
                        # Calculate overlap percentage of non-trivial lines
                        if not f_lines or not gt_lines_all:
                            overlap = 0.0
                        else:
                            f_set = set(f_lines)
                            gt_set = set(gt_lines_all)
                            intersection = f_set.intersection(gt_set)
                            # Overlap is % of non-trivial lines in the suspicious file that are also in ground truth
                            overlap = len(intersection) / len(f_set) if f_set else 0.0

                        if overlap == 0.0:
                            findings[name] = {
                                "type": FALSE_POSITIVE_BENIGN,
                                "reason": "Different SHA256 and 0% non-trivial line overlap."
                            }
                        else:
                            findings[name] = {
                                "type": SUSPECTED_LEAK,
                                "overlap_pct": overlap,
                                "reason": f"Different SHA256 but {overlap:.2%} non-trivial line overlap."
                            }
    except Exception as e:
        print(f"Error processing {tar_path}: {e}")

    return findings

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=str, help="Path to .tar.gz archive")
    parser.add_argument("--ground-truth", type=str, help="Path to ground truth directory")
    parser.add_argument("--selftest", action="store_true", help="Run mock self-test")
    parser.add_argument("--audit-r530", action="store_true", help="Audit specific R530 runs")
    args = parser.parse_args()

    if args.selftest:
        print("Running selftest...")
        # Mock data for selftest
        mock_archive = "mock_archive.tar.gz"
        with tarfile.open(mock_archive, "w:gz") as tar:
            content = "test_hidden.py\nimport solution\ndef check(): pass"
            info = tarfile.TarInfo(name="suspicious/test_hidden.py")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content.encode("utf-8")))
        
        mock_gt = "mock_gt"
        os.makedirs(mock_gt, exist_ok=True)
        with open(os.path.join(mock_gt, "real_hidden.py"), "w") as f:
            f.write("import solution\ndef check(): pass")
        
        results = analyze_archive(mock_archive, mock_gt)
        print(json.dumps(results, indent=2))
        os.remove(mock_archive)

    elif args.audit_r530:
        # The 4 specific runs are identified in the ticket as having "hidden" files that were false positives
        # We need to find where these archives are. They are usually in ops/gain/r530/archives/ or similar?
        # Actually, let's look at the directory structure again.
        # The prompt says: "verify 4 specific historical runs (confirming they are false positives)"
        print("Auditing R530 runs...")
        # These archives were identified in the ticket as being part of the r530 run set.
        # Based on the audit results, we can see the paths used:
        archives = [
            "ops/gain/r530/archives/g_r530_s1_1004_1.tar.gz",
            "ops/gain/r530/archives/g_r530_s2_1003_1.tar.gz",
            "ops/gain/r530/archives/g_r530_s2_1004_2.tar.gz",
            "ops/gain/r530/archives/g_r530_s3_1003_1.tar.gz",
        ]
        # The ground truth directory for r530 is ops/gain/r530/hidden/
        gt = "ops/gain/r530/hidden/"

        results = {}
        for arch in archives:
            if os.path.exists(arch):
                res = analyze_archive(arch, gt)
                # Merge results into a flat dict for easier reading if needed, 
                # or just print them as they come.
                print(f"Results for {arch}:")
                print(json.dumps(res, indent=2))
            else:
                print(f"Warning: Archive {arch} not found.")

        # Save the final audit results to the required file
        with open("ops/audits/r530_hidden_file_tighten_audit.json", "w") as f:
            json.dump(results, f, indent=2)
        print(f"Audit results saved to ops/audits/r530_hidden_file_tighten_audit.json")

    elif args.archive and args.ground_truth:
        results = analyze_archive(args.archive, args.ground_truth)
        print(json.dumps(results, indent=2))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
