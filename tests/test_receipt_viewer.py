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


# ===========================================================================
# R455 展件：三把金鑰的收據（examples/receipt_viewer_multiparty.html）
# ===========================================================================
#
# 那一頁的宣稱比收據牆更強：「三條**完整**的鏈、5579 筆，在你眼前這台機器上從創世
# 驗到鏈頭；每一格的裁決、指名與出貨都是這一頁自己重算的」。所以這裡要咬的是同一
# 件事的三個面向：
#   1. 頁內內嵌的三條鏈與 ops/gain/replay/r454/ 的原檔**逐位元組相同**（不是「差不多」）；
#   2. 同一批 entry 用權威實作（vacant/logbook.py、vacant/peerexec.py）在 Python 這端
#      再驗一次、再判一次——頁面說被指名的是 K3，Python 也必須自己得到 K3；
#   3. 竄改斷言：翻掉 K3 那一票、少一票誠實的，兩條路徑都要真的變。
# 「真的那兩段 JS」由 ops/gain/replay/multiparty_viewer_node_check.mjs 跑（要 node）。

from ops.gain.replay import build_multiparty_viewer as B  # noqa: E402
from vacant import peerexec as PX  # noqa: E402
from vacant.crypto import vacant_id_from_pubkey  # noqa: E402
from vacant.identity import PublicIdentity  # noqa: E402
from vacant.logbook import LogEntry  # noqa: E402

MP_VIEWER = REPO / "examples" / "receipt_viewer_multiparty.html"
MP_NODE_CHECK = REPO / "ops" / "gain" / "replay" / "multiparty_viewer_node_check.mjs"
MP_KEYS = ("K1", "K2", "K3")
#: R454 真跑的鏈長（DECISION_20260906…§二 P-5）。寫死是故意的：這是被測的事實，
#: 不是從被測物讀出來的——從頁面讀就等於讓頁面自己出考題。
MP_CHAIN_LEN = {"K1": 1840, "K2": 1840, "K3": 1899}
MP_TOTAL_ENTRIES = 5579

#: 隱藏測資推出來的字眼。它們只准出現在頁面上那一塊圍起來的「給觀眾的答案」裡，
#: 以及內嵌資料區塊裡（那是資料不是畫面）。
MP_HIDDEN_TOKENS = [
    "隱藏測資", "對答案", "給觀眾的答案",
    "hidden_check_scoring_only", "delivered_correct", "false_delivery",
    "delivery_scoring_hidden_only",
]
MP_FENCE_BEGIN = "<!-- HIDDEN-ANSWER-BEGIN"
MP_FENCE_END = "<!-- HIDDEN-ANSWER-END -->"
MP_REQUIRED_TEXT = [
    "以下是 2026-09-06 真實執行紀錄（r454），不是模擬",
    "給觀眾的答案，機制看不到",
    "這是示範，不是資料",
    "此瀏覽器不支援 Ed25519 驗簽，只驗了 hash 鏈",
    '<meta charset="utf-8">',
]

needs_r454 = pytest.mark.skipif(
    not (REPO / "ops" / "gain" / "replay" / "r454" / "att_K1.book.json").exists(),
    reason="r454 的三條鏈不在這份工作區裡")


@pytest.fixture(scope="module")
def mp_html() -> str:
    return MP_VIEWER.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def mp_books(mp_html) -> dict:
    """頁面**自己內嵌**的那三條鏈（不是磁碟上的檔案）。後面的驗證都對這一份跑。"""
    out = {}
    for key in MP_KEYS:
        text = B.extract_block(mp_html, "book-" + key)
        out[key] = [json.loads(ln) for ln in text.split("\n") if ln.strip()]
    return out


@pytest.fixture(scope="module")
def mp_pubs(mp_html) -> dict:
    return {k: json.loads(B.extract_block(mp_html, "pub-" + k)) for k in MP_KEYS}


# --- 內嵌樣本 vs 來源 -------------------------------------------------------

@needs_r454
def test_multiparty_embedded_blocks_are_byte_identical_to_their_sources(mp_html):
    """C4 的多方版：十個內嵌區塊，八個是原檔、兩個是可重現的推導表。
    「頁內樣本沒有被改過」是頁面的性質，所以這裡逐塊比位元組，不比語意。"""
    bad = B.check(mp_html)
    assert not bad, bad
    for block_id, src in B.BLOCKS.items():
        got = B.extract_block(mp_html, block_id)
        if src is not None:
            assert got == (B.R454 / src).read_text(encoding="utf-8").strip("\n"), block_id


@needs_r454
def test_multiparty_embedded_entry_count_equals_the_r454_books(mp_books):
    """1840／1840／1899＝5579。少一筆就不是「三條完整的鏈」了，而頁面正是這樣講的。"""
    for key in MP_KEYS:
        assert len(mp_books[key]) == MP_CHAIN_LEN[key], key
        disk = [ln for ln in (B.R454 / f"att_{key}.book.json")
                .read_text(encoding="utf-8").split("\n") if ln.strip()]
        assert len(disk) == MP_CHAIN_LEN[key], key
    assert sum(len(v) for v in mp_books.values()) == MP_TOTAL_ENTRIES


@needs_r454
def test_multiparty_cand_map_is_pinned_to_the_chain_by_entry_hash():
    """「第幾份」不在簽章裡，所以那張對照表必須被釘住：`cand_map()` 逐筆比對
    att_K*.ndjson 的 entry 與鏈上同一筆的 hash，對不上就整支拋掉不出貨。"""
    m = B.cand_map()
    for key in MP_KEYS:
        assert len(m[key]) == MP_CHAIN_LEN[key], key
        assert set(m[key]) <= set("01234"), key
    # K1／K2 每一格恰一筆 ⇒ 對照表必須等於「這一題的第幾筆」。
    for key in ("K1", "K2"):
        rows = [json.loads(ln) for ln in (B.R454 / f"att_{key}.ndjson")
                .read_text(encoding="utf-8").split("\n") if ln.strip()]
        pos, last = [], None
        for r in rows:
            pos.append(0 if r["task_id"] != last else pos[-1] + 1)
            last = r["task_id"]
        assert m[key] == "".join(str(p) for p in pos), key
    # K3 多出來的 59 筆＝自相矛盾格的第二份證言（同一格簽兩次）。
    assert len(m["K3"]) - len(m["K1"]) == 59


@needs_r454
def test_multiparty_reference_table_carries_no_hidden_derived_field(mp_html):
    """展件上唯一提到隱藏測資的地方是那塊圍起來的靜態文字。分析檔裡的
    delivered_correct／false_delivery **不准**被搬進頁面。"""
    ref = json.loads(B.extract_block(mp_html, "single-key-ref"))
    blob = json.dumps(ref, ensure_ascii=False)
    for token in ("delivered_correct", "false_delivery", "delivery_scoring_hidden_only", "hidden"):
        assert token not in blob, token
    assert len(ref["tasks"]) == 368


# --- Python 這端把同一批 entry 再驗一次 -------------------------------------

@needs_r454
def test_multiparty_python_reverifies_the_embedded_chains(mp_books, mp_pubs):
    """頁面說「三條鏈都驗得過」。這裡用權威實作（Logbook.verify_chain）對
    **頁面內嵌的那一份**再驗一次：三條全過，而且重算出來的鏈頭等於公鑰檔宣稱的。"""
    for key in MP_KEYS:
        who = PublicIdentity.from_hex(mp_pubs[key]["vacant_id"], mp_pubs[key]["pub_hex"])
        book = Logbook([LogEntry.from_json(d) for d in mp_books[key]])
        assert book.verify_chain(who), key
        assert book.head() == mp_pubs[key]["book_head"], key
        assert len(book) == MP_CHAIN_LEN[key], key
        # 名冊之外唯一能自證的一件事：vacant_id ＝ 公鑰的多重雜湊（頁面也重算這一條）。
        assert vacant_id_from_pubkey(who.pub) == mp_pubs[key]["vacant_id"], key


def _mp_cell(books, task_id, cand):
    """把某一格的三票從內嵌的鏈裡挑出來（K1 的鏈就是 job 表：sorted(task)×候選）。"""
    idx = {}
    for key in MP_KEYS:
        pos, last = [], None
        for i, e in enumerate(books[key]):
            tid = e["payload"]["task_id"]
            pos.append(0 if tid != last else pos[-1] + 1)
            last = tid
        idx[key] = [e for i, e in enumerate(books[key])
                    if e["payload"]["task_id"] == task_id and pos[i] == cand]
    return idx


@needs_r454
def test_multiparty_exhibition_cell_names_K3_when_recomputed_in_python(mp_books, mp_pubs, mp_html):
    """展出那一格（Mbpp/100 第 0 份）：Python 這端用 peerexec.form_verdict 自己判一次，
    必須自己得到「不通過、被指名的是 K3」——不是抄頁面、也不是抄歸檔收據。"""
    receipt = json.loads(B.extract_block(mp_html, "exhibition-receipt"))
    cell = _mp_cell(mp_books, receipt["task_id"], receipt["candidate_index"])
    roster = {k: PublicIdentity.from_hex(mp_pubs[k]["vacant_id"], mp_pubs[k]["pub_hex"])
              for k in MP_KEYS}
    atts = [PX.Attestation(k, LogEntry.from_json(e)) for k in MP_KEYS for e in cell[k]]
    p0 = atts[0].entry.payload
    v = PX.form_verdict(atts, roster, task_id=receipt["task_id"],
                        draft_sha256=p0["draft_sha256"], suite_sha256=p0["suite_sha256"],
                        render_sha256=p0["render_sha256"], quorum=receipt["verdict"]["quorum"])
    assert v.visible_ok is False
    assert v.dissenters == ("K3",)
    assert v.n_admitted == 3 and v.quorum == 2
    # 與歸檔收據對上（頁面畫面上那幾行也是照這一份長出來的）。
    assert list(v.dissenters) == receipt["named"]["dissenters"]
    assert v.visible_ok == receipt["verdict"]["visible_ok"]
    for k in MP_KEYS:
        assert dict(v.evidence)[k] == receipt["votes"][k]["entry_hash"], k


@needs_r454
def test_multiparty_tamper_flipping_K3_vote_breaks_its_signature(mp_books, mp_pubs, mp_html):
    """竄改示範（a）的 Python 對照：翻掉 K3 那一票 ⇒ hash 變、簽章驗不過、
    下一筆 prev_hash 接不上、整條鏈 verify_chain 為假，而且那一票**不進計票**
    （理由 bad_signature），所以裁決裡沒有人被指名——它不是「另一種意見」。"""
    receipt = json.loads(B.extract_block(mp_html, "exhibition-receipt"))
    cell = _mp_cell(mp_books, receipt["task_id"], receipt["candidate_index"])
    who = PublicIdentity.from_hex(mp_pubs["K3"]["vacant_id"], mp_pubs["K3"]["pub_hex"])
    roster = {k: PublicIdentity.from_hex(mp_pubs[k]["vacant_id"], mp_pubs[k]["pub_hex"])
              for k in MP_KEYS}

    entries = [LogEntry.from_json(d) for d in mp_books["K3"]]
    i = next(j for j, e in enumerate(entries) if e.to_json() == cell["K3"][0])
    tam = json.loads(json.dumps(cell["K3"][0]))
    tam["payload"]["visible_ok"] = not tam["payload"]["visible_ok"]
    tam_entry = LogEntry.from_json(tam)

    assert tam_entry.hash() != entries[i].hash()
    assert not PX._entry_signature_ok(tam_entry, who)[0]
    assert PX._entry_signature_ok(tam_entry, who)[1] == "bad_signature"
    assert mp_books["K3"][i + 1]["prev_hash"] != tam_entry.hash()
    tampered_book = Logbook([LogEntry.from_json(d) for d in mp_books["K3"]])
    tampered_book.entries[i] = tam_entry
    assert not tampered_book.verify_chain(who)

    atts = [PX.Attestation(k, LogEntry.from_json(e)) for k in ("K1", "K2") for e in cell[k]]
    atts.append(PX.Attestation("K3", tam_entry))
    p0 = atts[0].entry.payload
    v = PX.form_verdict(atts, roster, task_id=receipt["task_id"],
                        draft_sha256=p0["draft_sha256"], suite_sha256=p0["suite_sha256"],
                        render_sha256=p0["render_sha256"], quorum=receipt["verdict"]["quorum"])
    assert ("K3", "bad_signature") in v.rejected
    assert v.n_admitted == 2 and v.visible_ok is False and v.dissenters == ()


@needs_r454
def test_multiparty_tamper_dropping_K2_makes_it_a_tie_with_nobody_named(mp_books, mp_pubs, mp_html):
    """竄改示範（b）＝ R454 §三-3：k=3、法定人數 2 時少一票誠實的 ⇒ 1 比 1 平手、
    未決、**不指名**。指名的前提是誠實多數在場，不是「有簽章」。"""
    receipt = json.loads(B.extract_block(mp_html, "exhibition-receipt"))
    cell = _mp_cell(mp_books, receipt["task_id"], receipt["candidate_index"])
    roster = {k: PublicIdentity.from_hex(mp_pubs[k]["vacant_id"], mp_pubs[k]["pub_hex"])
              for k in MP_KEYS}
    atts = [PX.Attestation(k, LogEntry.from_json(e)) for k in ("K1", "K3") for e in cell[k]]
    p0 = atts[0].entry.payload
    v = PX.form_verdict(atts, roster, task_id=receipt["task_id"],
                        draft_sha256=p0["draft_sha256"], suite_sha256=p0["suite_sha256"],
                        render_sha256=p0["render_sha256"], quorum=receipt["verdict"]["quorum"])
    assert v.n_admitted == 2 and v.n_pass == 1 and v.n_fail == 1
    assert v.visible_ok is None
    assert v.dissenters == ()
    # K2 的鏈本身沒有被動到——少的是一票，不是一段鏈。
    who = PublicIdentity.from_hex(mp_pubs["K2"]["vacant_id"], mp_pubs["K2"]["pub_hex"])
    assert Logbook([LogEntry.from_json(d) for d in mp_books["K2"]]).verify_chain(who)


@needs_r454
def test_multiparty_platform_label_is_not_covered_by_any_signature(mp_books, mp_pubs):
    """竄改示範（c）：平台字串沒有進任何被簽的 payload，所以換掉它什麼都不會變。
    反面對照：executor_id 有進 payload，改掉它簽章就掛——不能兩者都「教觀眾」成一樣。"""
    for key in MP_KEYS:
        label = mp_pubs[key]["platform"]
        assert label
        for e in mp_books[key]:
            assert label not in canonical_bytes(e["payload"]).decode("utf-8"), key
        assert canonical_bytes(mp_books[key][0]["payload"]).decode("utf-8").count(
            '"executor_id":"%s"' % key) == 1
    who = PublicIdentity.from_hex(mp_pubs["K3"]["vacant_id"], mp_pubs["K3"]["pub_hex"])
    tam = json.loads(json.dumps(mp_books["K3"][0]))
    tam["payload"]["executor_id"] = "K9"
    assert not PX._entry_signature_ok(LogEntry.from_json(tam), who)[0]


# --- 位元組佈局：CANON 區段與收據牆是同一份 ---------------------------------

def test_multiparty_canon_block_is_byte_identical_to_the_receipt_wall(html, mp_html):
    """兩頁的正規化必須是**同一份位元組**，否則 receipt_viewer_node_check.mjs 的
    N5／N5b 只咬得到其中一頁，另一頁可以悄悄長出一把會 PASS 的瞎尺。"""
    a = html[html.index(X.CANON_BEGIN):html.index(X.CANON_END) + len(X.CANON_END)]
    assert B.extract_canon(mp_html) == a
    assert _SORT_WITH_COMPARATOR in a


def test_multiparty_canon_mirror_matches_canonical_bytes_on_a_non_bmp_key():
    """N5b 的同一組跨平面鍵：五個鍵的第一個字元就跨 BMP／非 BMP 邊界。
    （這裡跑的是 Python 鏡像；「真的那份 JS」由 multiparty_viewer_node_check.mjs 的 M11 跑。）"""
    obj = {"\U0001F331": 2, "�": 1, "Ａ": 3, "a": 4, " ": 5}
    assert X.js_canonical_string(obj).encode("utf-8") == canonical_bytes(obj)


@needs_r454
def test_multiparty_every_embedded_line_is_within_the_pages_number_rules(mp_html):
    """頁面對浮點數／超大整數選擇說「不知道」。內嵌的 5579 行必須一行都不落在那裡，
    否則展場會出現一格「本頁算不出來」。"""
    n = 0
    for key in MP_KEYS:
        for line in B.extract_block(mp_html, "book-" + key).split("\n"):
            if not line.strip():
                continue
            n += 1
            assert X.js_line_has_only_safe_integers(line), (key, line[:80])
    assert n == MP_TOTAL_ENTRIES


# --- 展場紅線 ---------------------------------------------------------------

def test_multiparty_wording_red_lines(mp_html):
    hits = [w for w in X.FORBIDDEN_WORDS if w in mp_html]
    assert not hits, hits


def test_multiparty_offline_no_external_resources(mp_html):
    low = mp_html.lower()
    hits = [p for p in X.FORBIDDEN_NET if p.lower() in low]
    assert not hits, hits


def test_multiparty_required_labels_present(mp_html):
    missing = [t for t in MP_REQUIRED_TEXT if t not in mp_html]
    assert not missing, missing


def test_multiparty_single_self_contained_file(mp_html):
    assert mp_html.startswith("<!doctype html>")
    assert len(mp_html.encode("utf-8")) < 8 * 1024 * 1024
    for block_id in B.BLOCKS:
        assert 'id="%s"' % block_id in mp_html


def _mp_code_region(mp_html: str) -> str:
    """把內嵌的資料區塊挖掉，剩下的才是「畫面與程式碼」。
    r454 的歸檔檔案裡本來就有隱藏測資欄位，那是**資料**；這條紅線管的是畫面。"""
    out = mp_html
    for block_id in B.BLOCKS:
        body = B.extract_block(mp_html, block_id)
        out = out.replace(body, "", 1)
    return out


def test_multiparty_hidden_answer_text_is_fenced(mp_html):
    """隱藏測資推出來的話只准出現在那一塊圍起來的「給觀眾的答案，機制看不到」裡。
    圍欄之外一個字都不准有——包括 JS 裡的字串。"""
    code = _mp_code_region(mp_html)
    i, j = code.index(MP_FENCE_BEGIN), code.index(MP_FENCE_END)
    assert i < j
    fence = code[i:j + len(MP_FENCE_END)]
    assert "給觀眾的答案，機制看不到" in fence
    outside = code[:i] + code[j + len(MP_FENCE_END):]
    leaked = [t for t in MP_HIDDEN_TOKENS if t in outside]
    assert not leaked, leaked
    assert all(t in fence for t in ("隱藏測資", "對答案"))


# --- 真的那兩段 JS（要 node）------------------------------------------------

def _stage_mp_node_tree(tmp_path: pathlib.Path, *, mutate: bool) -> pathlib.Path:
    root = tmp_path / "repo"
    (root / "examples").mkdir(parents=True)
    (root / "ops" / "gain" / "replay").mkdir(parents=True)
    page = MP_VIEWER.read_text(encoding="utf-8")
    if mutate:
        assert _SORT_WITH_COMPARATOR in page
        page = page.replace(_SORT_WITH_COMPARATOR, _SORT_WITHOUT_COMPARATOR, 1)
    (root / "examples" / "receipt_viewer_multiparty.html").write_text(page, encoding="utf-8")
    shutil.copy(MP_NODE_CHECK, root / "ops" / "gain" / "replay" / MP_NODE_CHECK.name)
    (root / "ops" / "gain" / "replay" / "r454").symlink_to(B.R454.resolve())
    return root


@needs_node
@needs_r454
def test_multiparty_node_check_passes_on_the_unmutated_page(tmp_path):
    """「真的那兩段 JS」對真資料跑一次：5579 個簽章、1840 格裁決、368 題出貨。"""
    root = _stage_mp_node_tree(tmp_path, mutate=False)
    proc = subprocess.run(["node", "ops/gain/replay/" + MP_NODE_CHECK.name],
                          cwd=root, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "總判定：OK" in proc.stdout
    assert "5579/5579" in proc.stdout
    assert "1840/1840 列" in proc.stdout


@needs_node
@needs_r454
def test_multiparty_node_check_catches_the_sort_without_comparator_mutation(tmp_path):
    """瞎尺迴歸：把 `.sort(cmpCodePoint)` 換成 `.sort()`，這一頁的 5579 個簽章仍然
    全數通過（payload 的鍵全是 ASCII），所以**只有** M11 那條跨平面鍵的斷言會咬人。
    它必須真的咬。"""
    root = _stage_mp_node_tree(tmp_path, mutate=True)
    proc = subprocess.run(["node", "ops/gain/replay/" + MP_NODE_CHECK.name],
                          cwd=root, capture_output=True, text=True, timeout=300)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "[BROKEN] M11" in proc.stdout, proc.stdout
