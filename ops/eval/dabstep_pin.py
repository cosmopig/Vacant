"""DABstep 的釘死環境：450 題共用同一份官方 Dockerfile（建置時從 HuggingFace 的浮動分支抓資料）。
評測計畫 §3.2：改成**一個**建好一次、記下 ID 的映像，資料 7 個檔核對 sha256，所有題目、所有條件用同一個。

    python3 ops/eval/dabstep_pin.py --export <harbor download 的 dabstep 目錄> --out <輸出目錄> \
        --image <本機映像 tag> --pin <釘死的資料檔目錄>

做的事：
1. 確認 export 裡每一題的 Dockerfile 都是同一份（sha256 一樣），不一樣就停。
2. 在映像裡核對 `/app/data/` 的 7 個檔和 `--pin` 目錄裡的一樣（sha256），不一樣就停。
3. 複製整個資料集，每一題的 Dockerfile 換成 `FROM <映像>`（題目、評分程式一個字都不動）。
4. 寫 `PIN_MANIFEST.json`：映像 ID、官方 Dockerfile 的 sha256、資料檔 sha256、換過的題數。

⚠ 映像＝官方 Dockerfile＋這台沙箱的憑證修正（容器對外的 TLS 被攔截，不信任那張憑證就裝不了套件）；
不是官方做法的一部分，寫在評測紀錄的偏差欄。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

DATA = ["acquirer_countries.csv", "fees.json", "manual.md", "merchant_category_codes.csv",
        "merchant_data.json", "payments-readme.md", "payments.csv"]


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--pin", required=True)
    a = ap.parse_args()
    src, out, pin = pathlib.Path(a.export), pathlib.Path(a.out), pathlib.Path(a.pin)
    docker_shas = {sha(d) for d in src.glob("*/environment/Dockerfile")}
    if len(docker_shas) != 1:
        print(f"refusing: {len(docker_shas)} different Dockerfiles in the export", file=sys.stderr)
        return 1
    want = {n: sha(pin / n) for n in DATA}
    p = subprocess.run(["docker", "run", "--rm", "--network", "none", a.image, "bash", "-c",
                        "cd /app/data && sha256sum " + " ".join(DATA)],
                       capture_output=True, text=True, timeout=300)
    got = {ln.split()[1]: ln.split()[0] for ln in p.stdout.splitlines() if ln.strip()}
    if got != want:
        print(f"refusing: data in {a.image} differs from the pinned files\n{got}\n{want}",
              file=sys.stderr)
        return 1
    image_id = subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", a.image],
                              capture_output=True, text=True, check=True).stdout.strip()
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out)
    n = 0
    for d in out.glob("*/environment/Dockerfile"):
        d.write_text(f"# Vacant eval: pinned DABstep environment (ops/eval/dabstep_pin.py)\n"
                     f"FROM {a.image}\nWORKDIR /app\n")
        n += 1
    man = {"image": a.image, "image_id": image_id, "official_dockerfile_sha256": docker_shas.pop(),
           "data_sha256": want, "tasks_rewritten": n}
    (out / "PIN_MANIFEST.json").write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
