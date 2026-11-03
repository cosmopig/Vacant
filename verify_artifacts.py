import json
from pathlib import Path

packet_path = Path("/home/user1/dev/ops/packets/e015_h_multi_review.md")
audit_path = Path("/home/user1/dev/ops/audits/e015_artifact_set.json")

with open(audit_path, 'r') as f:
    audit = json.load(f)

good_artifacts = audit['good']
bad_artifacts = audit['bad']

# Extract from markdown (this is a bit tricky because of the table format)
content = packet_path.read_text()

def extract_table_data(content, section_name):
    # Find the section and then find the tables under it
    lines = content.split('\n')
    start_idx = -1
    for i, line in enumerate(lines):
        if f"## {section_name}" in line:
            start_idx = i
            break
    
    if start_idx == -1:
        return []

    data = []
    in_table = False
    for i in range(start_idx, len(lines)):
        line = lines[i]
        if "|" in line and "---" not in line and "run" not in line and "cell" not in line:
            # This is a data row
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 7: # run, cell, task, arm, sha256, bytes, instruction_sha256
                data.append(parts)
        elif "run" in line and "|" in line:
            in_table = True
        elif in_table and ("|" not in line or "---" in line):
            # Table ended? Or just a separator
            if "---" in line: continue
            in_table = False
    return data

good_rows = extract_table_data(content, "2.1 被裁決件（植入 artifact 集，32 件、逐件 sha256 釘死；結果出來前不可改）")
bad_rows = extract_table_data(content, "BAD（16 件；reviewer 應 REJECT）")

print(f"Found {len(good_rows)} good rows in markdown.")
print(f"Found {len(bad_rows)} bad rows in markdown.")

# Verification logic
def verify(expected, actual_rows, label):
    if len(expected) != len(actual_rows):
        print(f"ERROR: Expected {len(expected)} {label} artifacts, but found {len(actual_rows)}")
        return False
    
    for i, exp in enumerate(expected):
        act = actual_rows[i]
        # Check sha256 (index 4) and instruction_sha256 (index 6)
        if exp['artifact_sha256'] != act[4]:
            print(f"ERROR: {label} artifact {i+1} sha256 mismatch!")
            print(f"  Expected: {exp['artifact_sha256']}")
            print(f"  Actual:   {act[4]}")
            return False
        if exp['instruction_sha256'] != act[6]:
            print(f"ERROR: {label} artifact {i+1} instruction_sha256 mismatch!")
            print(f"  Expected: {exp['instruction_sha256']}")
            print(f"  Actual:   {act[6]}")
            return False
    print(f"SUCCESS: All {label} artifacts verified.")
    return True

verify(good_artifacts, good_rows, "GOOD")
verify(bad_artifacts, bad_rows, "BAD")
