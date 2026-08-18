#!/usr/bin/env python3
"""去背——純標準庫實作（zlib + struct），因為這台 VM **沒有 ImageMagick 也沒有 PIL 也沒有 pip**。

為什麼要重寫而不是裝 ImageMagick：
  裝東西要 sudo（`sudo -n true` 已測回「a password is required」），
  sudo 安裝是規則七明訂的三個停下來等人類之一。`genimg.sh` 的檔頭本來就寫了
  「這台沒有 ImageMagick 也沒有 PIL」——`cutout.sh` 卻假設 `magick` 存在，
  是還沒被撞到過的死路（這一輪撞到了：DECISION_PIPELINE.md 記的
  「cutout.sh 已實測」那次八成是在別台機器上測的，這台没有 `magick` 可執行）。
  改成純標準庫可以繞開裝東西，不必等人類。

演算法跟 cutout.sh 原本要做的事一樣，只是自己實作淹沒填色：
  **從四個角落**各自以該角的顏色為種子，向內做連通填色（4-鄰接、比對「目前
  像素」與「該角種子色」的距離，不是比對前一個像素——避免沿著漸層一路吃進去）。
  只吃連通到角落的背景，主體內部（哪怕也是白的）留得住。

只支援 8-bit、非交錯的 PNG（colortype 2=RGB 或 6=RGBA）——codex 生出來的
都是這個格式（genimg.sh 已驗過 IHDR）。其他格式直接報錯，不猜。

用法：cutout.py <輸入.png> [輸出.png] [fuzz 0~1，預設 0.08]
"""
from __future__ import annotations

import struct
import sys
import zlib
from collections import deque

SIG = b"\x89PNG\r\n\x1a\n"


def _read_chunks(data: bytes):
    if data[:8] != SIG:
        raise ValueError("不是 PNG（signature 不對）")
    pos = 8
    chunks = []
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8].decode("ascii")
        cdata = data[pos + 8:pos + 8 + length]
        chunks.append((ctype, cdata))
        pos += 8 + length + 4  # + CRC
    return chunks


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode_png(path: str):
    data = open(path, "rb").read()
    chunks = _read_chunks(data)
    ihdr = next(c for t, c in chunks if t == "IHDR")
    w, h, bitdepth, colortype, comp, filt, inter = struct.unpack(">IIBBBBB", ihdr)
    if bitdepth != 8 or inter != 0 or colortype not in (2, 6):
        raise ValueError(
            f"不支援的 PNG 格式：bitdepth={bitdepth} colortype={colortype} "
            f"interlace={inter}（只支援 8-bit 非交錯 RGB/RGBA）")
    src_bpp = 3 if colortype == 2 else 4
    idat = b"".join(c for t, c in chunks if t == "IDAT")
    raw = zlib.decompress(idat)

    row_bytes = w * src_bpp
    out = bytearray(w * h * 4)  # 一律轉成 RGBA 存
    prev = bytearray(row_bytes)
    pos = 0
    for y in range(h):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + row_bytes])
        pos += row_bytes
        if ftype == 1:  # Sub
            for i in range(src_bpp, row_bytes):
                line[i] = (line[i] + line[i - src_bpp]) & 0xFF
        elif ftype == 2:  # Up
            for i in range(row_bytes):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:  # Average
            for i in range(row_bytes):
                a = line[i - src_bpp] if i >= src_bpp else 0
                b = prev[i]
                line[i] = (line[i] + ((a + b) >> 1)) & 0xFF
        elif ftype == 4:  # Paeth
            for i in range(row_bytes):
                a = line[i - src_bpp] if i >= src_bpp else 0
                b = prev[i]
                c = prev[i - src_bpp] if i >= src_bpp else 0
                line[i] = (line[i] + _paeth(a, b, c)) & 0xFF
        # ftype == 0: None, no-op
        row_off = y * w * 4
        if src_bpp == 4:
            out[row_off:row_off + row_bytes] = line
        else:
            for x in range(w):
                so = x * 3
                do = row_off + x * 4
                out[do:do + 3] = line[so:so + 3]
                out[do + 3] = 255
        prev = line
    return w, h, out


def encode_png(path: str, w: int, h: int, rgba: bytearray) -> None:
    row_bytes = w * 4
    raw = bytearray((row_bytes + 1) * h)
    for y in range(h):
        row_off = y * row_bytes
        dst_off = y * (row_bytes + 1)
        raw[dst_off] = 0  # filter: None
        raw[dst_off + 1:dst_off + 1 + row_bytes] = rgba[row_off:row_off + row_bytes]
    idat = zlib.compress(bytes(raw), 6)

    def chunk(ctype: bytes, cdata: bytes) -> bytes:
        return (struct.pack(">I", len(cdata)) + ctype + cdata +
                struct.pack(">I", zlib.crc32(ctype + cdata)))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(SIG)
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", idat))
        f.write(chunk(b"IEND", b""))


def flood_cut(w: int, h: int, rgba: bytearray, fuzz: float) -> None:
    """從四角淹沒填色，比對對象是各自角落的種子色（不是前一像素）——防止沿漸層吃穿。"""
    thresh = fuzz * 255.0 * 1.732  # 8% 對到 RGB 歐氏距離的粗略換算，跟 IM -fuzz 同量級
    visited = bytearray(w * h)

    def px(i):
        o = i * 4
        return rgba[o], rgba[o + 1], rgba[o + 2]

    def close(c1, c2):
        dr, dg, db = c1[0] - c2[0], c1[1] - c2[1], c1[2] - c2[2]
        return (dr * dr + dg * dg + db * db) ** 0.5 <= thresh

    for cx, cy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        seed_i = cy * w + cx
        if visited[seed_i]:
            continue
        seed_color = px(seed_i)
        q = deque([seed_i])
        visited[seed_i] = 1
        while q:
            i = q.popleft()
            x, y = i % w, i // w
            c = px(i)
            if not close(c, seed_color):
                continue
            rgba[i * 4 + 3] = 0
            if x > 0 and not visited[i - 1]:
                visited[i - 1] = 1
                q.append(i - 1)
            if x < w - 1 and not visited[i + 1]:
                visited[i + 1] = 1
                q.append(i + 1)
            if y > 0 and not visited[i - w]:
                visited[i - w] = 1
                q.append(i - w)
            if y < h - 1 and not visited[i + w]:
                visited[i + w] = 1
                q.append(i + w)


def trim(w: int, h: int, rgba: bytearray):
    """裁到 alpha>0 的 bounding box——等同 `-trim +repage`。"""
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        row_off = y * w * 4
        for x in range(w):
            if rgba[row_off + x * 4 + 3] != 0:
                if x < minx:
                    minx = x
                if x > maxx:
                    maxx = x
                if y < miny:
                    miny = y
                if y > maxy:
                    maxy = y
    if maxx < 0:
        return w, h, rgba  # 全透明，別崩，照原樣還回去
    nw, nh = maxx - minx + 1, maxy - miny + 1
    out = bytearray(nw * nh * 4)
    for y in range(nh):
        src_off = (y + miny) * w * 4 + minx * 4
        dst_off = y * nw * 4
        out[dst_off:dst_off + nw * 4] = rgba[src_off:src_off + nw * 4]
    return nw, nh, out


def diagnose(w: int, h: int, rgba: bytearray, label: str) -> None:
    n = w * h
    opaque = sum(1 for i in range(n) if rgba[i * 4 + 3] != 0)
    frac = opaque / n if n else 0.0
    print(f"  {label}  {w}x{h}  不透明比例 {frac:.2f}")
    if frac > 0.97:
        print("  ⚠ 幾乎沒有透明像素——背景可能沒被吃掉（純白？fuzz 太小？）")
    elif frac < 0.25:
        print("  ⚠ 不透明比例過低——主體可能被吃掉了，去看圖不要只看數字")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法：cutout.py <輸入.png> [輸出.png] [fuzz 0~1]")
    inp = sys.argv[1]
    outp = sys.argv[2] if len(sys.argv) > 2 else inp.rsplit(".png", 1)[0] + "_cut.png"
    fuzz = float(sys.argv[3]) if len(sys.argv) > 3 else 0.08

    w, h, rgba = decode_png(inp)
    flood_cut(w, h, rgba, fuzz)
    w, h, rgba = trim(w, h, rgba)
    encode_png(outp, w, h, rgba)
    diagnose(w, h, rgba, outp)
