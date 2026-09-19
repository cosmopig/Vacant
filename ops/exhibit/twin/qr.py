"""twin/qr — 最小 QR 編碼器（**stdlib only**），給展場那張「掃一下」用。

## 這支在架構裡承重什麼

`vacant_hm/world3/qr.png` 是 **735 bytes 的靜態檔**，2026-08-30 進 repo
（`7c6392c` 骨架期），**比 `serve_twin.py`／`phone.html` 早三個星期**。
不管它編的是什麼，都不可能是執行期的手機網址。

而 `exhibit_boot.sh --lan` 會把 `serve_twin` 綁到 `0.0.0.0`，手機要連的是
**展場那台機器的區網 IP**——每次開機可能不同。**一張烤死的 QR 必然指到錯的地方**，
而畫面正大聲叫觀眾「掃一下 · 用你自己的手機就好」。那是展場當天一定會壞的東西。

⇒ QR 在**執行期**由這一支畫，內容是 `serve_twin` 當下真正綁在哪裡。

## 為什麼自己寫而不裝一個套件

展場機（Linux VM）不能假設裝得了東西，而 `serve_twin.py` 的整條線是
stdlib only、離線、零外部資源（CLAUDE.md 硬約束 2）。用外部 QR 服務更不行——
那是一個對外請求。

## 範圍（**刻意很小**，因為小才驗得完）

- **byte 模式**、**EC 等級 M**、**版本 1–6**（最多 106 bytes）。
  展場的網址長這樣：`http://192.168.1.23:8899/phone.html` ＝ 35 bytes ⇒ 版本 3 就夠。
  超過 106 bytes 直接 `ValueError`，**不會默默截斷**。
- 版本 ≤ 6 ⇒ **不需要版本資訊區塊**（那是版本 ≥ 7 才有的），少一塊要寫對的東西。

## 誠實邊界

1. **這一支沒有解碼器，所以它不能自己證明自己對。** 判準在
   `tests/test_qr.py`：拿 `segno`（開發機上有）當**外部對照**，
   逐 bit 比對模組矩陣。`segno` 不在就 skip——那時候這一支**沒有被驗過**，
   不是「驗過了」。
2. 掃不掃得到還牽涉列印／螢幕對比與鏡頭，那不是這一支保證得了的。
   展場要實機掃過一次。
"""
from __future__ import annotations

import struct
import zlib

# ── GF(256)，本原多項式 0x11D（QR 規格指定）──────────────────────
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a: int, b: int) -> int:
    return 0 if (a == 0 or b == 0) else _EXP[_LOG[a] + _LOG[b]]


def _gen_poly(n: int) -> list[int]:
    """(x-α⁰)(x-α¹)…(x-α^{n-1})，最高次在前。"""
    g = [1]
    for i in range(n):
        ng = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            ng[j] ^= c
            ng[j + 1] ^= _mul(c, _EXP[i])
        g = ng
    return g


def _rs(data: list[int], n: int) -> list[int]:
    g = _gen_poly(n)
    res = list(data) + [0] * n
    for i in range(len(data)):
        c = res[i]
        if c:
            for j, gc in enumerate(g):
                res[i + j] ^= _mul(gc, c)
    return res[len(data):]


#: 版本 → (每塊 EC 碼字數, [(區塊數, 每塊資料碼字數), …])。EC 等級 M。
#: 來源：ISO/IEC 18004 表 13–22。`tests/test_qr.py` 用 segno 對照過。
_SPEC_M: dict[int, tuple[int, list[tuple[int, int]]]] = {
    1: (10, [(1, 16)]),
    2: (16, [(1, 28)]),
    3: (26, [(1, 44)]),
    4: (18, [(2, 32)]),
    5: (24, [(2, 43)]),
    6: (16, [(4, 27)]),
}

#: 版本 → 對齊圖樣的中心座標。版本 1 沒有。
_ALIGN: dict[int, list[int]] = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
}

MAX_BYTES = 106  # 版本 6-M 的 byte 模式容量


def _capacity(v: int) -> int:
    _ec, groups = _SPEC_M[v]
    data_cw = sum(n * k for n, k in groups)
    return data_cw - 2            # 4 bits 模式 ＋ 8 bits 長度 ＝ 1.5 → 進位成 2


def _pick_version(n: int) -> int:
    for v in sorted(_SPEC_M):
        if n <= _capacity(v):
            return v
    raise ValueError(
        f"這一支只做到版本 6（{MAX_BYTES} bytes），給了 {n} bytes。"
        "**不會默默截斷**——要更長就要把 _SPEC_M 補到更高版本，並且重跑對照測試。")


def _bitstream(payload: bytes, version: int) -> list[int]:
    _ec, groups = _SPEC_M[version]
    total_data = sum(n * k for n, k in groups)
    bits: list[int] = []
    bits += [0, 1, 0, 0]                                   # byte 模式
    bits += [(len(payload) >> i) & 1 for i in range(7, -1, -1)]   # 8 bits 長度
    for b in payload:
        bits += [(b >> i) & 1 for i in range(7, -1, -1)]
    # 終止符：最多 4 個 0，容量不夠就少放幾個
    bits += [0] * min(4, total_data * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)                          # 補到整個 byte
    pad = (0xEC, 0x11)
    i = 0
    while len(bits) < total_data * 8:
        bits += [(pad[i % 2] >> k) & 1 for k in range(7, -1, -1)]
        i += 1
    return bits


def _codewords(payload: bytes, version: int) -> list[int]:
    ec_n, groups = _SPEC_M[version]
    bits = _bitstream(payload, version)
    data = [int("".join(str(b) for b in bits[i:i + 8]), 2)
            for i in range(0, len(bits), 8)]
    blocks: list[list[int]] = []
    pos = 0
    for n, k in groups:
        for _ in range(n):
            blocks.append(data[pos:pos + k])
            pos += k
    eccs = [_rs(b, ec_n) for b in blocks]
    out: list[int] = []
    for i in range(max(len(b) for b in blocks)):
        for b in blocks:
            if i < len(b):
                out.append(b[i])
    for i in range(ec_n):
        for e in eccs:
            out.append(e[i])
    return out


def _skeleton(version: int) -> tuple[list[list[int | None]], list[list[bool]]]:
    """回傳 (模組矩陣, 是否為機能區)。`None` ＝ 還沒填的資料位。"""
    size = 17 + 4 * version
    m: list[list[int | None]] = [[None] * size for _ in range(size)]
    fn = [[False] * size for _ in range(size)]

    def put(r, c, v):
        m[r][c] = v
        fn[r][c] = True

    # 定位圖樣（三個角）＋分隔線
    for (r0, c0) in ((0, 0), (0, size - 7), (size - 7, 0)):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = r0 + dr, c0 + dc
                if not (0 <= r < size and 0 <= c < size):
                    continue
                edge = dr in (-1, 7) or dc in (-1, 7)
                if edge:
                    put(r, c, 0)
                else:
                    ring = dr in (0, 6) or dc in (0, 6)
                    core = 2 <= dr <= 4 and 2 <= dc <= 4
                    put(r, c, 1 if (ring or core) else 0)
    # 對齊圖樣（避開定位圖樣）
    cs = _ALIGN[version]
    for r0 in cs:
        for c0 in cs:
            if (r0 < 8 and c0 < 8) or (r0 < 8 and c0 > size - 9) \
               or (r0 > size - 9 and c0 < 8):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    ring = max(abs(dr), abs(dc))
                    put(r0 + dr, c0 + dc, 1 if ring != 1 else 0)
    # 時序圖樣
    for i in range(8, size - 8):
        put(6, i, 1 if i % 2 == 0 else 0)
        put(i, 6, 1 if i % 2 == 0 else 0)
    # 固定黑點
    put(4 * version + 9, 8, 1)
    # 格式資訊區先佔位（值稍後填）
    for i in range(9):
        if m[8][i] is None:
            put(8, i, 0)
        if m[i][8] is None:
            put(i, 8, 0)
    # ⚠ 第二份格式資訊**不是對稱的 8+8**：直的那一段只有 7 格
    #   （row size-1 … size-7），第 8 格 (size-8, 8) 是**固定黑點**，不是格式位。
    #   橫的那一段才是 8 格（col size-8 … size-1）。寫成 8+7 會把黑點蓋掉，
    #   而且每一個遮罩的懲罰分數都會算錯 ⇒ 挑到跟規格不同的遮罩
    #   （實測：v2/v4/v6 剛好一樣、v1/v3/v5 整片不同）。
    for i in range(7):
        put(size - 1 - i, 8, 0)
    for i in range(8):
        put(8, size - 1 - i, 0)
    return m, fn


def _place(m, fn, cw: list[int]) -> None:
    size = len(m)
    bits = [(b >> i) & 1 for b in cw for i in range(7, -1, -1)]
    k = 0
    up = True
    col = size - 1
    while col > 0:
        if col == 6:            # 第 6 行是時序圖樣，跳過
            col -= 1
        rows = range(size - 1, -1, -1) if up else range(size)
        for r in rows:
            for c in (col, col - 1):
                if fn[r][c]:
                    continue
                m[r][c] = bits[k] if k < len(bits) else 0
                k += 1
        up = not up
        col -= 2


def _mask_fn(k: int):
    return (
        lambda r, c: (r + c) % 2 == 0,
        lambda r, c: r % 2 == 0,
        lambda r, c: c % 3 == 0,
        lambda r, c: (r + c) % 3 == 0,
        lambda r, c: (r // 2 + c // 3) % 2 == 0,
        lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
        lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
        lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
    )[k]


def _penalty(m) -> int:
    size = len(m)
    score = 0
    # N1：一列／一行連續 5 個以上同色
    for line in [[m[r][c] for c in range(size)] for r in range(size)] + \
                [[m[r][c] for r in range(size)] for c in range(size)]:
        run, prev = 1, line[0]
        for v in line[1:]:
            if v == prev:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run, prev = 1, v
        if run >= 5:
            score += 3 + (run - 5)
    # N2：2×2 同色
    for r in range(size - 1):
        for c in range(size - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    # N3：1011101 前後接四格空白（會被誤認成定位圖樣）。
    #
    # ⚠ **這一條的算法各家不同**，而且差很多：只掃符號內部的話，
    #   實測一張 v5 只找得到 2 處；把符號外的靜區也算成空白（zxing 等的做法）
    #   則是 20 幾處，與 segno 同一個量級。採後者——靜區本來就是空白，
    #   貼在邊上的 1011101 對掃描器一樣像定位圖樣。
    #   **它只影響挑哪一個遮罩，不影響對錯**：選中的遮罩會寫進格式資訊，
    #   任何一個遮罩都解得開。判準因此不比對「跟 segno 挑同一個」，
    #   只比對「不是明顯差的那幾個」（tests/test_qr.py）。
    pats = ([1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0], [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1])
    for line in [[m[r][c] for c in range(size)] for r in range(size)] + \
                [[m[r][c] for r in range(size)] for c in range(size)]:
        padded = [0] * 4 + line + [0] * 4
        for i in range(len(padded) - 10):
            if padded[i:i + 11] in pats:
                score += 40
    # N4：黑格比例偏離 50%
    dark = sum(sum(row) for row in m)
    pct = dark * 100 / (size * size)
    score += 10 * int(abs(pct - 50) / 5)
    return score


def _format_bits(mask: int) -> list[int]:
    """EC 等級 M ＝ 0b00；BCH(15,5) ＋ 固定遮罩 0x5412。"""
    v = (0b00 << 3) | mask
    d = v << 10
    g = 0b10100110111
    for i in range(4, -1, -1):
        if d & (1 << (i + 10)):
            d ^= g << i
    out = ((v << 10) | d) ^ 0b101010000010010
    return [(out >> i) & 1 for i in range(14, -1, -1)]


def matrix(text: str, force_mask: int | None = None) -> list[list[int]]:
    """字串 → QR 模組矩陣（1 ＝ 黑）。不含靜區。

    `force_mask` 只給測試用：把遮罩釘死之後，就分得出「資料放錯」與
    「遮罩挑錯」是兩回事——不釘死的話兩者的症狀一模一樣（整片不同）。
    """
    payload = text.encode("utf-8")
    version = _pick_version(len(payload))
    cw = _codewords(payload, version)
    best = None
    for mask in (range(8) if force_mask is None else (force_mask,)):
        m, fn = _skeleton(version)
        _place(m, fn, cw)
        f = _mask_fn(mask)
        for r in range(len(m)):
            for c in range(len(m)):
                if not fn[r][c] and f(r, c):
                    m[r][c] ^= 1
        size = len(m)
        bits = _format_bits(mask)
        # 格式資訊兩份，位置由規格寫死
        for i in range(6):
            m[8][i] = bits[i]
            m[i][8] = bits[14 - i]
        m[8][7] = bits[6]
        m[8][8] = bits[7]
        m[7][8] = bits[8]
        for i in range(7):                   # 直的 7 格：bits[0..6]
            m[size - 1 - i][8] = bits[i]
        for i in range(8):                   # 橫的 8 格：bits[7..14]
            m[8][size - 8 + i] = bits[7 + i]
        m[size - 8][8] = 1                   # 固定黑點（格式資訊不碰它）
        p = _penalty(m)
        if best is None or p < best[0]:
            best = (p, m)
    return best[1]


def to_png(text: str, *, scale: int = 8, quiet: int = 4) -> bytes:
    """QR → PNG（1 bit 灰階，stdlib 的 zlib 壓）。"""
    m = matrix(text)
    n = len(m)
    side = (n + quiet * 2) * scale
    rows = []
    for y in range(side):
        qy = y // scale - quiet
        line = bytearray([0])                     # filter type 0
        for x in range(side):
            qx = x // scale - quiet
            dark = (0 <= qy < n and 0 <= qx < n and m[qy][qx] == 1)
            line.append(0 if dark else 255)
        rows.append(bytes(line))
    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", side, side, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def to_svg(text: str, *, quiet: int = 4) -> str:
    m = matrix(text)
    n = len(m)
    side = n + quiet * 2
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side} {side}" '
             f'shape-rendering="crispEdges">',
             f'<rect width="{side}" height="{side}" fill="#fff"/>']
    for r in range(n):
        for c in range(n):
            if m[r][c]:
                parts.append(f'<rect x="{c + quiet}" y="{r + quiet}" '
                             'width="1" height="1" fill="#000"/>')
    parts.append("</svg>")
    return "".join(parts)
