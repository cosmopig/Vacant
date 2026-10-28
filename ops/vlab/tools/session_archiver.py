import os
import shutil
import time
import argparse
from pathlib import Path

def archive_sessions(base_dir, out_dir, once=False):
    base_path = Path(base_dir)
    out_path = Path(out_dir)
    
    # Ensure output directory exists
    if not out_path.exists():
        out_path.mkdir(parents=True, exist_ok=True)

    def process_cell(cell_path):
        cell_name = cell_path.name
        sessions_dir = cell_path / "home" / ".pi" / "agent" / "sessions"
        if not sessions_dir.exists():
            return

        # Target directory for this cell's archive
        target_dir = out_path / cell_name / "sessions"
        
        # Find all .jsonl files in subdirectories of sessions
        for jsonl_file in sessions_dir.rglob("*.jsonl"):
            dest_file = target_dir / jsonl_file.relative_to(sessions_dir)
            
            if not dest_file.parent.exists():
                dest_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file (overwrite if exists for idempotency in this context)
            shutil.copy2(jsonl_file, dest_file)

    if once:
        for cell_path in base_path.glob("*/"):
            if cell_path.is_dir():
                process_cell(cell_path)
    else:
        while True:
            try:
                for cell_path in base_path.glob("*/"):
                    if cell_path.is_dir():
                        process_cell(cell_path)
                time.sleep(5)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--base", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args()

    archive_sessions(args.base, args.out, args.once)
