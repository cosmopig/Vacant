"""`ops/exhibit/twin/qr.py` 的可執行判準。

## 為什麼這一支特別要緊

展場那張「掃一下」的 QR **必須在執行期生成**（舊的 `world3/qr.png` 是 2026-08-30
的靜態佔位圖，比 `phone.html` 早三個星期，不可能指對地方）。而 QR 是
**觀眾唯一的入口**：它壞掉的失敗模式是「觀眾掃了沒反應，然後走掉」——
現場不會有人回報，也看不出來。所以它要有外部對照。

## 判準怎麼分層（哪一層被驗到什麼程度）

1. **滿載 payload × 6 個版本 × 8 個遮罩 ＝ 48 張，與 `segno` 逐 bit 相同。**
   這一層涵蓋：模式指示、字數指示、資料位元流、RS 生成多項式、區塊交錯、
   定位／對齊／時序圖樣、固定黑點、**每一個遮罩的格式資訊**、遮罩套用。
   `segno` 不在就 **skip**——那時候這一層**沒有被驗過**，不是「驗過了」。
2. **補位（padding）自己驗。** `segno` 在這一點上**與 ISO 不合**
   （`write_padding_bits` 寫 `8 - (length % 8)`，已經對齊時會多塞一整個 0x00），
   所以這一層不能拿它當對照。改成把自己的矩陣讀回來，逐碼字比對 ISO 的規定。
   ⚠ 同時把「與 segno 差幾個 0x00」釘住：哪天 segno 修了，這一條會紅，
   而那是我們想知道的事。
3. **遮罩挑哪一個是啟發式，不是對錯。** 選中的遮罩寫在格式資訊裡，
   任何一個都解得開，而各家的 N3 算法本來就不同。所以只驗
   「用 segno 自己的評分器看，我挑的那個排在前半段」。
"""
from __future__ import annotations

import pathlib
import sys
import zlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import qr  # noqa: E402

try:
    import segno as _segno
    import segno.encoder as _segno_enc
except ImportError:                                   # pragma: no cover
    _segno = None
    _segno_enc = None

ALPHA = "abcdefghijklmnopqrstuvwxyz0123456789-._~:/?#[]@!$&'()*+,;="

#: 版本 → 剛好塞滿（一個補位碼字都沒有）的 byte 數。EC 等級 M。
EXACT = {1: 14, 2: 26, 3: 42, 4: 62, 5: 84, 6: 106}

needs_segno = pytest.mark.skipif(_segno is None,
                                 reason="沒有 segno ⇒ 這一層沒有外部對照，不是驗過了")


def payload(n: int) -> str:
    return "".join(ALPHA[i % len(ALPHA)] for i in range(n))


def read_back(m: list[list[int]], version: int, mask: int) -> list[int]:
    """把模組矩陣反遮罩、依 zigzag 讀回碼字序列（測試專用的逆運算）。"""
    _sk, fn = qr._skeleton(version)
    f = qr._mask_fn(mask)
    n = len(m)
    bits: list[int] = []
    up, col = True, n - 1
    while col > 0:
        if col == 6:
            col -= 1
        for r in (range(n - 1, -1, -1) if up else range(n)):
            for c in (col, col - 1):
                if fn[r][c]:
                    continue
                bits.append(m[r][c] ^ (1 if f(r, c) else 0))
        up = not up
        col -= 2
    return [int("".join(map(str, bits[i:i + 8])), 2)
            for i in range(0, len(bits) // 8 * 8, 8)]


def data_codewords(m: list[list[int]], version: int, mask: int) -> list[int]:
    """讀回來 **並且解交錯**，還原成資料碼字的原始順序。

    ⚠ 版本 4／5／6 是多區塊，落在符號上的是**交錯過**的碼字流。
    忘記解交錯的話，前幾個碼字看起來還是對的（區塊 0 的開頭），
    再往後就全錯——而測試如果只檢查標頭就會漏掉。
    """
    _ec, groups = qr._SPEC_M[version]
    sizes = [k for n, k in groups for _ in range(n)]
    n_data = sum(sizes)
    inter = read_back(m, version, mask)[:n_data]
    blocks: list[list[int]] = [[] for _ in sizes]
    j = 0
    for i in range(max(sizes)):
        for b, k in enumerate(sizes):
            if i < k:
                blocks[b].append(inter[j])
                j += 1
    return [c for b in blocks for c in b]


def mask_of(m: list[list[int]]) -> int:
    """從格式資訊反推用了哪一個遮罩（順便驗格式資訊寫對了位置）。"""
    for mk in range(8):
        bits = qr._format_bits(mk)
        if all(m[8][i] == bits[i] for i in range(6)) \
           and m[8][7] == bits[6] and m[8][8] == bits[7] and m[7][8] == bits[8]:
            return mk
    raise AssertionError("格式資訊解不出任何一個遮罩")


# ── 第 1 層：與 segno 逐 bit 相同 ────────────────────────────────
@needs_segno
@pytest.mark.parametrize("version", sorted(EXACT))
def test_matches_segno_bit_for_bit_every_mask(version):
    """滿載 payload、遮罩釘死 ⇒ 48 張全部與 segno 逐 bit 相同。

    釘死遮罩是關鍵：不釘的話「資料放錯」與「遮罩挑得不一樣」的症狀一模一樣
    （整片不同），分不出是哪一個。
    """
    s = payload(EXACT[version])
    assert _segno.make(s, error="m", mode="byte", micro=False,
                       boost_error=False).version == version
    for mk in range(8):
        ref = _segno.make(s, error="m", mode="byte", micro=False,
                          boost_error=False, mask=mk)
        want = [[1 if x else 0 for x in row] for row in ref.matrix]
        assert qr.matrix(s, force_mask=mk) == want, (version, mk)


@needs_segno
def test_all_same_byte_payload_would_hide_a_shift():
    """這一條是給**測試自己**的防呆。

    最早的版本用 `"x" * n` 當 payload，結果一個「整串碼字位移一格」的錯
    完全看不出來——因為每一個碼字都長得一樣。判準要用**各不相同**的位元組。
    """
    s_same, s_diff = "x" * 42, payload(42)
    ref = _segno.make(s_diff, error="m", mode="byte", micro=False,
                      boost_error=False, mask=0)
    assert qr.matrix(s_diff, force_mask=0) == [[1 if x else 0 for x in r]
                                               for r in ref.matrix]
    cw = read_back(qr.matrix(s_same, force_mask=0), 3, 0)
    assert len(set(cw[2:40])) == 1, "全同位元組的 payload 讀回來就是一串一樣的碼字"


# ── 第 2 層：補位自己驗（segno 在這一點上與 ISO 不合）────────────
@pytest.mark.parametrize("n", [1, 5, 10, 13, 20, 35, 41, 55, 80, 100])
def test_padding_follows_iso(n):
    """ISO 18004 §7.4.10：終止符最多 4 個 0、補到整個碼字、然後 0xEC／0x11 交替。"""
    s = payload(n)
    v = qr._pick_version(len(s.encode()))
    data = data_codewords(qr.matrix(s, force_mask=0), v, 0)
    n_data = len(data)
    # 標頭：0100（byte 模式）＋ 8 bits 長度
    assert data[0] >> 4 == 0b0100
    assert ((data[0] & 0x0F) << 4) | (data[1] >> 4) == len(s.encode())
    # 補位碼字：從第一個整碼字開始，0xEC／0x11 交替，一個都不能多
    used_bits = 4 + 8 + 8 * len(s.encode()) + 4        # 含終止符
    first_pad = -(-used_bits // 8)
    expect = [0xEC if i % 2 == 0 else 0x11
              for i in range(n_data - first_pad)]
    assert data[first_pad:] == expect, (v, first_pad, data[first_pad:][:6])


@needs_segno
@pytest.mark.parametrize("n", [10, 35, 50, 80])
def test_segno_padding_divergence_is_exactly_one_zero_codeword(n):
    """**把與 segno 的差異釘住**：只差一個多出來的 0x00，而且只在補位處。

    segno 的 `write_padding_bits` 寫 `8 - (length % 8)`：資料流已經對齊的時候
    會多補 8 個 0（byte 模式在版本 1–9 永遠對齊，所以每一張都多一個 0x00）。
    那不影響解碼（解碼器讀到終止符就停），但**不是 ISO 寫的**。
    哪天 segno 修了，這一條會紅——那正是我們想知道的事。
    """
    s = payload(n)
    ref = _segno.make(s, error="m", mode="byte", micro=False, boost_error=False)
    v = ref.version
    theirs = data_codewords([[1 if x else 0 for x in r] for r in ref.matrix],
                            v, ref.mask)
    mine = data_codewords(qr.matrix(s, force_mask=ref.mask), v, ref.mask)
    i = next(k for k in range(len(mine)) if theirs[k] != mine[k])
    assert theirs[i] == 0x00, (i, hex(theirs[i]))
    # 拿掉那一個多出來的 0x00 之後，資料區其餘完全相同（最後少一個補位碼字）
    assert theirs[:i] + theirs[i + 1:] == mine[:-1]


# ── 第 3 層：遮罩是啟發式，只驗「不是明顯差的那幾個」──────────────
@needs_segno
@pytest.mark.parametrize("n", [10, 14, 26, 35, 42, 62, 84, 106])
def test_mask_choice_is_in_segnos_better_half(n):
    """挑哪一個遮罩不影響對錯（遮罩寫在格式資訊裡，任何一個都解得開），
    但挑到很差的會讓現場掃不順。用 segno 自己的評分器看，我挑的要在前半段。"""
    s = payload(n)
    v = qr._pick_version(len(s.encode()))
    size = 17 + 4 * v
    scores = {mk: sum(_segno_enc.mask_scores(
        [bytearray(r) for r in qr.matrix(s, force_mask=mk)], size, size))
        for mk in range(8)}
    picked = mask_of(qr.matrix(s))
    rank = sorted(scores, key=lambda k: scores[k]).index(picked) + 1
    assert rank <= 4, (n, picked, rank, scores)


@pytest.mark.parametrize("n", [1, 14, 35, 106])
def test_format_info_records_the_mask_actually_used(n):
    """格式資訊寫的遮罩，要等於真的套上去的那一個——不然掃描器會解錯。"""
    s = payload(n)
    v = qr._pick_version(len(s.encode()))
    for mk in range(8):
        m = qr.matrix(s, force_mask=mk)
        assert mask_of(m) == mk
        # 第二份格式資訊要跟第一份一致（兩份都壞掉才會讀不出來，所以兩份都要對）
        bits = qr._format_bits(mk)
        size = len(m)
        assert [m[size - 1 - i][8] for i in range(7)] == bits[:7]
        assert [m[8][size - 8 + i] for i in range(8)] == bits[7:]
        assert m[size - 8][8] == 1, "固定黑點被格式資訊蓋掉了"


# ── 結構與邊界 ─────────────────────────────────────────────────
@pytest.mark.parametrize("version,n", sorted(EXACT.items()))
def test_size_and_finders(version, n):
    m = qr.matrix(payload(n))
    size = 17 + 4 * version
    assert len(m) == size and all(len(r) == size for r in m)
    for (r0, c0) in ((0, 0), (0, size - 7), (size - 7, 0)):
        assert m[r0][c0] == 1 and m[r0 + 3][c0 + 3] == 1
        assert m[r0 + 1][c0 + 1] == 0


def test_too_long_raises_instead_of_truncating():
    """**不會默默截斷。** 一張截斷過的 QR 掃得開、內容卻是錯的——那是最糟的失敗。"""
    with pytest.raises(ValueError, match="不會默默截斷"):
        qr.matrix("x" * (qr.MAX_BYTES + 1))
    qr.matrix("x" * qr.MAX_BYTES)          # 剛好塞得下就要過


def test_exhibition_url_fits_with_room_to_spare():
    """展場真正會用的那種網址要塞得下，而且不要剛好卡在邊界上。"""
    for host in ("192.168.1.23", "10.0.0.7", "172.16.254.199"):
        url = f"http://{host}:8899/phone.html"
        v = qr._pick_version(len(url.encode()))
        assert v <= 3, (url, v)
        assert qr.matrix(url)


def test_png_is_a_valid_png_and_scales():
    png = qr.to_png("http://192.168.1.23:8899/phone.html", scale=4, quiet=4)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    # IHDR 的寬高要等於 (模組數 + 靜區*2) * scale
    import struct
    w, h = struct.unpack(">II", png[16:24])
    n = len(qr.matrix("http://192.168.1.23:8899/phone.html"))
    assert w == h == (n + 8) * 4
    # IDAT 解得開，而且每一列的 filter byte 是 0
    idat = png[png.index(b"IDAT") + 4:]
    raw = zlib.decompress(idat[:-12] if idat[-12:-8] == b"IEND" else idat)
    assert len(raw) == h * (w + 1)
    assert all(raw[i * (w + 1)] == 0 for i in range(h))


def test_svg_has_a_quiet_zone_and_no_external_resource():
    svg = qr.to_svg("http://127.0.0.1:8899/phone.html")
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "http://www.w3.org/2000/svg" in svg      # 只有 namespace，不是要載入的東西
    assert svg.count("<rect") > 10
    n = len(qr.matrix("http://127.0.0.1:8899/phone.html"))
    assert f'viewBox="0 0 {n + 8} {n + 8}"' in svg


def test_deterministic():
    """同一個字串畫兩次要逐 bit 相同（展場開機兩次不該長不一樣）。"""
    s = "http://192.168.1.23:8899/phone.html"
    assert qr.matrix(s) == qr.matrix(s)
    assert qr.to_png(s) == qr.to_png(s)
