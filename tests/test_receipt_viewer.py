"""展件「收據牆」（`examples/receipt_viewer.html`）的驗收。

這組測試存在的理由：那一頁的整個宣稱是「觀眾眼前這台機器自己把 482 筆重算了一次」。
如果頁內 JS 的位元組佈局跟 `vacant/logbook.py` 差一個字元，畫面會照樣顯示綠色的
「驗證通過」——**一把會 PASS 的瞎尺**。所以：

  1. JS 的正規化規則在 `receipt_viewer_crosscheck.py` 裡被**重寫一次**（不是呼叫
     `vacant.canonical`），再去對 `LogEntry.hash()`；兩條獨立的路走到同一個 hash。
  2. 每一條乾淨斷言旁邊都有一條竄改斷言（改 payload ⇒ hash 變、簽章掛、下一筆
     prev_hash 接不上）。
  3. 展場口徑（CLAUDE.md 鐵律：不准出現「信任／防止／保證」）與離線紅線
     （不准有任何外部資源）當成測試跑，不是靠記得。

真的那一份 JS（不是鏡像）由 `ops/gain/replay/receipt_viewer_node_check.mjs` 跑，
需要 node，所以不放進 pytest 的必跑路徑。
"""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ops.gain.replay import receipt_viewer_crosscheck as X  # noqa: E402
from vacant.canonical import canonical_bytes  # noqa: E402
from vacant.identity import Identity, PublicIdentity  # noqa: E402
from vacant.logbook import Logbook  # noqa: E402

VIEWER = REPO / "examples" / "receipt_viewer.html"
RUN = REPO / "runs" / "g_r445_conform_mbpp_ext"
RUN2 = REPO / "runs" / "g_r447_conform_lcb2"
NODE_CHECK = REPO / "ops" / "gain" / "replay" / "receipt_viewer_node_check.mjs"

needs_run = pytest.mark.skipif(
    not (RUN / "receipts_CONFORM.ndjson").exists(),
    reason="歸檔的 r445 收據不在這份工作區裡")
needs_run2 = pytest.mark.skipif(
    not (RUN2 / "receipts_CONFORM.ndjson").exists(),
    reason="歸檔的 r447 收據不在這份工作區裡")
needs_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node 不在 PATH 上")


@pytest.fixture(scope="module")
def html() -> str:
    return VIEWER.read_text(encoding="utf-8")


# --- 對照腳本整包 -----------------------------------------------------------

@needs_run
def test_crosscheck_all_ok():
    out = X.run(RUN, "CONFORM", VIEWER)
    broken = [c for c in out["checks"] if c["verdict"] != "OK"]
    assert not broken, broken
    assert out["n_entries"] == 482


@needs_run2
def test_crosscheck_ok_on_a_second_independent_chain():
    """一條鏈過關可能是巧合。g_r447 是另一把 keypair、另一個題庫簽出來的 325 筆，
    兩條都要逐筆對上，才排得掉「鏡像剛好跟著 logbook 一起錯」。"""
    out = X.run(RUN2, "CONFORM", VIEWER)
    broken = [c for c in out["checks"] if c["verdict"] != "OK"]
    assert not broken, broken
    assert out["n_entries"] == 325
    # 兩條鏈的身分不同——否則「第二條鏈」只是同一條的複本，不構成獨立證據。
    assert out["vacant_id"] != X.run(RUN, "CONFORM", VIEWER)["vacant_id"]


@needs_run
@needs_run2
def test_crosscheck_cli_all_returns_zero(capsys):
    """`--all` 是報告裡引用的那一條指令；它自己要能退出碼 0。"""
    assert X.main(["--all"]) == 0
    out = capsys.readouterr().out
    assert "482 筆 OK" in out and "325 筆 OK" in out


@needs_run2
def test_mirror_matches_logbook_for_every_entry_of_r447():
    """C2 的獨立重述：325 筆逐筆 js_entry_hash == LogEntry.hash()。"""
    book = Logbook.load(RUN2 / "receipts_CONFORM.ndjson")
    lines = [ln for ln in (RUN2 / "receipts_CONFORM.ndjson")
             .read_text(encoding="utf-8").split("\n") if ln.strip()]
    assert len(book.entries) == len(lines) == 325
    for ln, e in zip(lines, book.entries):
        assert X.js_entry_hash(json.loads(ln)) == e.hash()


@needs_run2
def test_embedded_sample_is_checked_against_its_own_source_not_the_run_under_test():
    """C4 是頁面的性質不是 run 的性質：`--run` 指到 g_r447 時它照樣比 g_r445，
    否則換個 run 來檢查就會冒出一條假的紅字。"""
    c4 = [c for c in X.run(RUN2, "CONFORM", VIEWER)["checks"] if c["check"] == "C4"][0]
    assert c4["verdict"] == "OK"
    assert X.EMBEDDED_RUN.name in c4["msg"]


# --- 鏡像 vs 權威實作 -------------------------------------------------------

def test_mirror_matches_logbook_on_a_fresh_chain():
    """不只靠歸檔檔：現場簽一條新的鏈，鏡像照樣要逐筆對上。"""
    ident = Identity.generate()
    book = Logbook()
    payloads = [
        {"task_id": "t/1", "worker": "careful-1", "visible_ok": True, "err": ""},
        {"task_id": "t/1", "accepted": True, "attempts": 1, "worker": "careful-1"},
        {"中文鍵": "值", "巢狀": {"b": [1, -2, None, True], "a": "引號\" 反斜線\\"}},
        {"控制字元": "\x00\x1f\n\t", "emoji": "🌱", "大整數": 2 ** 53 - 1},
    ]
    for i, p in enumerate(payloads):
        book.append("conform_attempt", p, ident, ts_ms=1_700_000_000_000 + i)
    for e in book.entries:
        assert X.js_entry_hash(e.to_json()) == e.hash()


def test_mirror_matches_canonical_bytes_on_edge_cases():
    for c in X.CANON_FIXTURES:
        assert X.js_canonical_string(c).encode("utf-8") == canonical_bytes(c)


def test_mirror_key_order_is_code_point_not_utf16():
    """非 BMP 的鍵：JS 預設的字串比較（UTF-16 code unit）會排錯，所以頁面沒有用它。"""
    obj = {"\U0001F331": 1, "Ａ": 2}
    assert X.js_canonical_string(obj).encode("utf-8") == canonical_bytes(obj)
    assert X.js_canonical_string(obj).index('"Ａ"') < X.js_canonical_string(obj).index('"\U0001F331"')


def test_mirror_refuses_floats_instead_of_guessing():
    """浮點數是 JS 與 Python 的格式會分岔的地方；頁面在那裡選擇說「不知道」。"""
    with pytest.raises(ValueError):
        X.js_canonical_string({"a": 1.5})
    with pytest.raises(ValueError):
        X.js_canonical_string({"a": 2 ** 53})
    assert X.js_canonical_string({"a": 5.0}) == '{"a":5}'  # JS 的 Number.isInteger(5.0)


def test_float_guard_flags_the_lines_the_page_cannot_recompute():
    assert X.js_line_has_only_safe_integers('{"a":1,"b":true,"c":"1.5e7"}')
    assert not X.js_line_has_only_safe_integers('{"a":1.5}')
    assert not X.js_line_has_only_safe_integers('{"a":1e7}')
    assert not X.js_line_has_only_safe_integers('{"a":12345678901234567}')


# --- 竄改（乾淨路徑通過不算數）---------------------------------------------

@needs_run
def test_tamper_breaks_hash_signature_and_linkage():
    lines = [ln for ln in (RUN / "receipts_CONFORM.ndjson")
             .read_text(encoding="utf-8").split("\n") if ln.strip()]
    dicts = [json.loads(ln) for ln in lines]
    meta = json.loads((RUN / "receipts_CONFORM.pub.json").read_text(encoding="utf-8"))
    who = PublicIdentity.from_hex(meta["vacant_id"], meta["pub_hex"])
    book = Logbook.load(RUN / "receipts_CONFORM.ndjson")
    assert book.verify_chain(who)

    idx = X.js_tamper_target(dicts)
    assert 0 < idx < len(dicts) - 1  # 不能挑最後一筆，否則沒有下一筆可以互相對照
    tam = json.loads(lines[idx])
    tam["payload"]["visible_ok"] = not tam["payload"]["visible_ok"]

    assert X.js_entry_hash(tam) != X.js_entry_hash(dicts[idx])
    assert dicts[idx + 1]["prev_hash"] != X.js_entry_hash(tam)
    book.entries[idx] = type(book.entries[idx]).from_json(tam)
    assert not book.verify_chain(who)


# --- 展場紅線 ---------------------------------------------------------------

def test_wording_red_lines(html):
    """CLAUDE.md：口徑用「可究責性／讓依賴有根據」，不要用「信任」；也不寫防止／保證。"""
    hits = [w for w in X.FORBIDDEN_WORDS if w in html]
    assert not hits, hits


def test_offline_no_external_resources(html):
    """實體場地不能假設網路：整頁不得有任何外部資源或連線。"""
    low = html.lower()
    hits = [p for p in X.FORBIDDEN_NET if p.lower() in low]
    assert not hits, hits


def test_required_labels_present(html):
    """真實資料要標「不是模擬」、示範要標「不是資料」、驗不了簽要老實說。"""
    missing = [t for t in X.REQUIRED_TEXT if t not in html]
    assert not missing, missing


def test_single_self_contained_file(html):
    assert html.startswith("<!doctype html>")
    assert '<script type="application/x-ndjson" id="embedded-chain"' in html
    assert X.CANON_BEGIN in html and X.CANON_END in html


@needs_run
def test_embedded_sample_is_byte_identical_to_the_run(html):
    chain, pub = X.extract_embedded(html)
    assert chain == (RUN / "receipts_CONFORM.ndjson").read_text(encoding="utf-8").rstrip("\n")
    assert pub == (RUN / "receipts_CONFORM.pub.json").read_text(encoding="utf-8").strip()


# --- 變異測試：node check 真的會咬人（blind ruler 迴歸）---------------------
#
# 對抗性覆核指出過一把「會 PASS 的瞎尺」：`receipt_viewer_node_check.mjs` 的
# N5 曾經只在孤立狀態下測 `cmpCodePoint` 這個比較器本身，從沒斷言頁面的
# `canonicalString` 真的把它接上去用，而且唯一的形狀 fixture 全是 ASCII 鍵。
# 把第 849 行的 `Object.keys(v).sort(cmpCodePoint)` 換成不吃比較器的
# `Object.keys(v).sort()`，node check 9/9、crosscheck、render check 三邊照樣
# 全線——頁面對非 BMP 鍵算出的 canonical bytes 已經跟 `vacant/canonical.py`
# 分岔，卻沒有任何一條 check 抓到。N5b（見 node_check.mjs）補了這個洞；
# 這裡直接跑一次「真的那份 JS」來證明它會咬人：乾淨頁面過、竄改頁面不過。

_SORT_WITH_COMPARATOR = "Object.keys(v).sort(cmpCodePoint)"
_SORT_WITHOUT_COMPARATOR = "Object.keys(v).sort()"


def _stage_node_check_tree(tmp_path: pathlib.Path, *, mutate: bool) -> pathlib.Path:
    """在 tmp_path 底下搭 node_check.mjs 認得的最小骨架：
    `<root>/examples/receipt_viewer.html`（可竄改）、
    `<root>/ops/gain/replay/receipt_viewer_node_check.mjs`（原封不動的檢查腳本本身，
    不是被測物）、`<root>/runs/g_r445_conform_mbpp_ext/`（symlink 回真檔，
    482 筆不重複複製）。node_check.mjs 用 `import.meta.url` 算 REPO，
    跟呼叫時的 cwd 無關，所以骨架長什麼樣它自己說了算。"""
    root = tmp_path / "repo"
    (root / "examples").mkdir(parents=True)
    (root / "ops" / "gain" / "replay").mkdir(parents=True)
    run_dst = root / "runs" / "g_r445_conform_mbpp_ext"
    run_dst.mkdir(parents=True)

    page = VIEWER.read_text(encoding="utf-8")
    if mutate:
        assert _SORT_WITH_COMPARATOR in page, "找不到要竄改的那一行，頁面已經變了？"
        mutated = page.replace(_SORT_WITH_COMPARATOR, _SORT_WITHOUT_COMPARATOR, 1)
        assert mutated != page, "字串替換沒有真的改到東西"
        page = mutated
    (root / "examples" / "receipt_viewer.html").write_text(page, encoding="utf-8")

    shutil.copy(NODE_CHECK, root / "ops" / "gain" / "replay" / "receipt_viewer_node_check.mjs")

    for name in ("receipts_CONFORM.ndjson", "receipts_CONFORM.pub.json"):
        (run_dst / name).symlink_to((RUN / name).resolve())

    return root


def _run_node_check(root: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", "ops/gain/replay/receipt_viewer_node_check.mjs"],
        cwd=root, capture_output=True, text=True, timeout=60)


@needs_node
@needs_run
def test_node_check_passes_on_the_unmutated_page(tmp_path):
    root = _stage_node_check_tree(tmp_path, mutate=False)
    proc = _run_node_check(root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "總判定：OK" in proc.stdout


@needs_node
@needs_run
def test_node_check_catches_the_sort_without_comparator_mutation(tmp_path):
    """把 `.sort(cmpCodePoint)` 換成 `.sort()`：node check 必須整組退出碼非零，
    且 N5b 那一項要點名 BROKEN——不能只是「剛好有別項也紅了」矇混過去。"""
    root = _stage_node_check_tree(tmp_path, mutate=True)
    proc = _run_node_check(root)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "[BROKEN] N5b" in proc.stdout, proc.stdout
