"""展件「一天的收據」（`examples/twin_viewer.html`）的驗收。

這組測試存在的理由與收據牆那一組逐字相同：那一頁的整個宣稱是「觀眾眼前這台
機器自己把這些鏈重算了一次」。如果頁內 JS 的位元組佈局跟 `vacant_network/logbook.py`
差一個字元，畫面會照樣顯示綠色的「驗證通過」——**一把會 PASS 的瞎尺**。

所以：

  1. CANON 區段必須與 `examples/receipt_viewer.html` **逐位元組相同**——
     那一頁的 `receipt_viewer_crosscheck.py` 與 node check 已經把它釘死，
     複製一份就等於把那些覆蓋率一起帶過來；分岔就代表少了一半的保護。
  2. 內嵌資料必須與磁碟上的來源逐位元組相同（`build_viewer.py --check`）。
  3. 展場口徑（不准出現「信任／防止／保證」）與離線紅線（不准有任何外部資源）
     **當成測試跑，不是靠記得**。
  4. 證據等級的 fail-closed 規則有正反兩面控制：`requests_seen == 0` 的格
     一定是 L-none，而且宣告蓋不過去。

真的那一份 JS（不是鏡像）由 `ops/exhibit/twin/twin_viewer_node_check.mjs` 跑，
需要 node，所以不放進 pytest 的必跑路徑。
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import build_viewer, pack as packlib, roster  # noqa: E402
from ops.gain.replay import receipt_viewer_crosscheck as X  # noqa: E402
from vacant_network.canonical import canonical_bytes  # noqa: E402
from vacant_network.identity import PublicIdentity  # noqa: E402
from vacant_network.logbook import LogEntry, Logbook  # noqa: E402

VIEWER = REPO / "examples" / "twin_viewer.html"
SOURCE_VIEWER = REPO / "examples" / "receipt_viewer.html"
PACK = REPO / "ops" / "exhibit" / "twin" / "twin_pack.json"
NODE_CHECK = REPO / "ops" / "exhibit" / "twin" / "twin_viewer_node_check.mjs"


@pytest.fixture(scope="module")
def html():
    return VIEWER.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def pack(html):
    return json.loads(build_viewer.extract_block(html, "twin-pack"))


# --- 頁面結構 ---------------------------------------------------------------

def test_single_self_contained_file(html):
    assert html.startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in html
    assert '<script type="application/json" id="twin-pack"' in html
    assert '<script type="application/json" id="twin-assets"' in html
    assert build_viewer.CANON_BEGIN in html and build_viewer.CANON_END in html
    assert "/* === LOGIC-BEGIN ===" in html and "/* === LOGIC-END === */" in html


def test_canon_is_byte_identical_to_the_receipt_wall(html):
    """CANON 分岔 ＝ 兩頁的 hash 佈局可能不同，而 node check 只咬得到其中一頁。"""
    assert build_viewer.extract_canon(html) == build_viewer.expected_canon()
    src = SOURCE_VIEWER.read_text(encoding="utf-8")
    i, j = src.find(build_viewer.CANON_BEGIN), src.find(build_viewer.CANON_END)
    assert build_viewer.extract_canon(html) == src[i:j + len(build_viewer.CANON_END)]


def test_embedded_blocks_match_their_sources(html):
    assert build_viewer.check(html) == []


def test_embedded_pack_is_byte_identical_to_the_file(html):
    assert build_viewer.extract_block(html, "twin-pack") == \
        PACK.read_text(encoding="utf-8").strip("\n")


# --- 展場紅線 ---------------------------------------------------------------

def test_wording_red_lines(html):
    """CLAUDE.md：口徑用「可究責性／讓依賴有根據」，不要用「信任」；也不寫防止／保證。"""
    hits = [w for w in X.FORBIDDEN_WORDS if w in html]
    assert not hits, hits


def test_offline_no_external_resources(html):
    """實體場地不能假設網路：整頁不得有任何外部資源或連線。與收據牆共用同一份清單。"""
    low = html.lower()
    hits = [p for p in X.FORBIDDEN_NET if p.lower() in low]
    assert not hits, hits


def test_assets_are_inline_data_uris(html):
    """素材只能是內嵌的 data URI——展場那台機器不會有別的檔案。"""
    assets = json.loads(build_viewer.extract_block(html, "twin-assets"))
    assert assets, "一張素材都沒有"
    for name, uri in assets.items():
        assert uri.startswith("data:image/png;base64,"), name


def test_residents_have_a_human_image(html):
    """人類連續三次否決抽象發光生物：每一位居民都要有一張人的像。"""
    assets = json.loads(build_viewer.extract_block(html, "twin-assets"))
    pack = json.loads(build_viewer.extract_block(html, "twin-pack"))
    missing = [r["body"] for r in pack["residents"]
               if f"{r['body']}_portrait" not in assets]
    assert not missing, missing


def test_no_build_machine_paths_leak(html):
    """建置這台機器的絕對路徑不准印在展場螢幕上。"""
    for needle in ("/Users/", "/home/", "C:\\\\Users"):
        assert needle not in html, needle


def test_required_labels_present(html):
    """真資料要說是真的、示範要說是示範、驗不了簽要老實說。"""
    required = [
        "這是示範，不是資料",
        "此瀏覽器不支援 Ed25519 驗簽，只驗了 hash 鏈",
        "程序生成，不是任何人的分身",
        "requests_seen",
    ]
    missing = [t for t in required if t not in html]
    assert not missing, missing


def test_hidden_test_data_never_enters_the_page(html):
    """V/GT 紅線：隱藏測資一個 byte 都不進展件。"""
    bank = REPO / "ops" / "gain" / "r535" / "bank"
    pack = json.loads(build_viewer.extract_block(html, "twin-pack"))
    for c in pack["cells"]:
        hidden = bank / c["task_id"] / "hidden" / "test_hidden.py"
        if not hidden.exists():
            continue
        body = hidden.read_text(encoding="utf-8")
        # 逐個 check 函式名比對：可見那幾條在頁面上是應該的，隱藏獨有的不准在。
        hidden_names = set(re.findall(r"^def (check_\w+)\(", body, re.M))
        visible = bank / c["task_id"] / "tests_visible" / "test_visible.py"
        visible_names = set(re.findall(
            r"^def (check_\w+)\(", visible.read_text(encoding="utf-8"), re.M))
        leaked = sorted(n for n in (hidden_names - visible_names) if n in html)
        assert not leaked, (c["task_id"], leaked)


# --- 資料本身 ---------------------------------------------------------------

def test_both_endings_exist(pack):
    """一個永遠拒交的閘門跟沒有閘門一樣沒用：兩種結局都要在。"""
    assert pack["delivered"] > 0 and pack["refused"] > 0


def test_every_cell_declares_an_evidence_level(pack):
    known = {"L-real", "L-fake", "L-none", "L-unknown"}
    for c in pack["cells"]:
        assert c["evidence"] in known, c["cell_id"]
        assert c["evidence"] in pack["evidence_text"], c["evidence"]


def test_evidence_is_fail_closed_against_the_declaration():
    """宣告蓋不過資料：`requests_seen == 0` 出來一定是 L-none。"""
    assert packlib.evidence_level(requests_seen=0, declared="L-real") == "L-none"
    assert packlib.evidence_level(requests_seen=0, declared="L-fake") == "L-none"
    assert packlib.evidence_level(requests_seen=3, declared="L-real") == "L-real"
    assert packlib.evidence_level(requests_seen=3, declared="L-fake") == "L-fake"
    assert packlib.evidence_level(requests_seen=3, declared="") == "L-unknown"


def test_packed_levels_agree_with_requests_seen(pack):
    for c in pack["cells"]:
        if c["requests_seen"] == 0:
            assert c["evidence"] == "L-none", c["cell_id"]
        else:
            assert c["evidence"] != "L-none", c["cell_id"]


def test_upstream_never_carries_a_scheme(pack):
    """URL 形狀的字串不准進頁面（離線紅線），但資訊本身不能消失。"""
    for c in pack["cells"]:
        assert "://" not in (c["declared_upstream"] or "")
    assert packlib.strip_scheme("https://a.example:9/v1") == "a.example:9/v1"
    assert packlib.strip_scheme("a.example:9") == "a.example:9"


# --- 鏈：兩條獨立的路走到同一個 hash ----------------------------------------

def test_every_chain_verifies_with_the_authoritative_implementation(pack):
    for c in pack["cells"]:
        book = Logbook([LogEntry.from_json(json.loads(ln)) for ln in c["chain"]])
        who = PublicIdentity.from_hex(c["pub"]["vacant_id"], c["pub"]["pub_hex"])
        assert book.verify_chain(who), c["cell_id"]


def test_js_hash_layout_matches_logbook(pack):
    """JS 的正規化規則在 crosscheck 裡被**重寫一次**，兩條獨立的路要走到同一個 hash。"""
    for c in pack["cells"]:
        for line in c["chain"]:
            d = json.loads(line)
            assert X.js_entry_hash(d) == LogEntry.from_json(d).hash()
            assert X.js_line_has_only_safe_integers(line), c["cell_id"]


def test_tampering_breaks_hash_and_link(pack):
    """竄改斷言：改 payload ⇒ hash 變、下一筆 prev_hash 接不上、驗鏈紅。"""
    c = next(x for x in pack["cells"] if len(x["chain"]) >= 2)
    dicts = [json.loads(ln) for ln in c["chain"]]
    idx = 0                                   # 不挑最後一筆，才有下一筆可以對照
    tam = json.loads(c["chain"][idx])
    tam["payload"]["accepted"] = not tam["payload"].get("accepted")
    assert X.js_entry_hash(tam) != X.js_entry_hash(dicts[idx])
    assert dicts[idx + 1]["prev_hash"] != X.js_entry_hash(tam)
    book = Logbook([LogEntry.from_json(d) for d in dicts])
    book.entries[idx] = LogEntry.from_json(tam)
    who = PublicIdentity.from_hex(c["pub"]["vacant_id"], c["pub"]["pub_hex"])
    assert not book.verify_chain(who)


def test_verdict_in_the_chain_agrees_with_the_summary(pack):
    """摘要沒有進簽章。兩者現在必須一致——不一致代表有一邊在說謊。"""
    for c in pack["cells"]:
        verdict = None
        for ln in c["chain"]:
            d = json.loads(ln)
            if d["type"] == "ws_verdict":
                verdict = d["payload"]
        assert verdict is not None, c["cell_id"]
        for k in ("accepted", "stop_reason", "ws_end_sha256", "requests_seen"):
            assert verdict[k] == c[k], (c["cell_id"], k)


def test_delivery_tree_hash_recomputes_to_the_signed_value(pack):
    """把「它交出來的那份程式碼」綁回鏈上那一筆（vacant_network/vrun/wshash.py 的佈局）。"""
    import hashlib
    n = 0
    for c in pack["cells"]:
        d = c["delivery"]
        if not d["recomputable"]:
            continue
        n += 1
        leaves = []
        for f in d["files"]:
            assert hashlib.sha256(f["text"].encode("utf-8")).hexdigest() == f["sha256"]
            leaves.append({"path": f["path"], "sha256": f["sha256"], "exec": f["exec"]})
        leaves.sort(key=lambda x: x["path"])
        root = hashlib.sha256(canonical_bytes(leaves)).hexdigest()
        assert root == d["root_claimed"], c["cell_id"]
    assert n > 0, "沒有任何一格是可重算的——那樣這條斷言等於沒跑"


# --- 同意鏈 -----------------------------------------------------------------

def test_consent_chain_verifies_and_has_an_erasure(pack):
    from vacant_network import consent
    cn = pack["consent"]
    assert cn, "資料包裡沒有同意鏈"
    book = Logbook([LogEntry.from_json(json.loads(ln)) for ln in cn["chain"]])
    who = PublicIdentity.from_hex(cn["pub"]["vacant_id"], cn["pub"]["pub_hex"])
    assert book.verify_chain(who)
    a = consent.audit(book, who)
    assert a["problems"] == []
    assert any(s.state == "erased" for s in a["subjects"].values())


def test_no_persona_plaintext_anywhere_in_the_page(html):
    """鏈上不准有原文——而且整頁的**同意那一塊**也不准有。

    居民卡上會顯示 persona 的值（那是展件本體），所以這一條只掃同意鏈本身：
    鏈是 append-only，上去就刪不掉。
    """
    from vacant_network import consent
    pack = json.loads(build_viewer.extract_block(html, "twin-pack"))
    book = Logbook([LogEntry.from_json(json.loads(ln))
                    for ln in pack["consent"]["chain"]])
    values = [v for r in pack["residents"] for vs in r["persona"].values() for v in vs]
    consent.assert_no_plaintext(book, values)


def test_residents_are_flagged_synthetic(pack):
    """倫理未定案之前，名冊上每一位都必須標成合成的。"""
    from vacant_network import consent
    for r in pack["residents"]:
        assert r["synthetic"] is True, r["codename"]
        # 只准 SPEC_v3 §四-1 那四類，不多不少——與 `vacant_network/consent.py` 同一份清單
        assert set(r["persona"]) == set(consent.ALLOWED_FIELDS), r["codename"]
        assert r["subject_ref"].startswith("SYN-"), r["subject_ref"]
    assert roster.BODIES, "體型清單是空的 ⇒ 居民沒有形象可用"


# --- 真的那一份 JS（要有 node）-----------------------------------------------

@pytest.mark.skipif(shutil.which("node") is None, reason="這台機器沒有 node")
def test_node_check_passes():
    r = subprocess.run(["node", str(NODE_CHECK)], capture_output=True, text=True,
                       cwd=str(REPO), timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "全部通過" in r.stdout
