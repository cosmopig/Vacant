# -*- coding: utf-8 -*-
"""R535 S2 層的**題目原始資料**（`名字給、契約細節未給`，n=40）。

這支在架構裡承重什麼（Fable 2026-09-19 裁決 R535「題庫與量具」）
--------------------------------------------------------------
S2 比 S1 接近真工作負載：`TASK.md` **給函式名＋白話描述**，但 withhold
一到兩個行為細節（dict 的 key 集合、排序、空輸入、四捨五入、例外型別）；
可見驗收把那些細節釘死。事前預期第 1 次可見失敗率 **0.4–0.8**——
比 S1 低，因為名字不必猜；比 0 高，因為細節是真的沒寫。

修法**不像 S1 那樣讀一行 ImportError 就知道**：agent 得讀
`args=…got=…want=…` 那一行然後改邏輯。量具第 3 項在 S2 量的就是這件事
（回饋裡一定有 `args=` 與 `want=`）。

⚠ **題庫是資料不是程式**（R452）：本檔是來源資料，
`ops/gain/r535/build_bank.py` 確定性渲染成 `ops/gain/r535/bank/`，
sha256 凍進 `ops/gain/r535/bank_manifest.json`。

⚠ **出題紀律**：不用 gemma-12b 出題；不抄 LCB／r530／codebench 的題面；
題目真的微型（參考解 1–14 行），**不寫成 LeetCode**。

欄位（與 `tasks_s1.py` 相同，多一個 `withheld`）
----------------------------------------------
``withheld``  **必須不出現在 `TASK.md` 裡**的字面值／片語清單。
              這就是「被 withhold 的契約細節」的可執行定義——量具第 5 項
              對每一條做大小寫不敏感的子字串比對，命中就是這一題壞了。
"""

TASKS = [
    {
        "id": "s2_01_mean",
        "title": "mean(xs)",
        "prose": """`mean(xs)` takes a list of numbers and gives back their arithmetic
average as a number.

Callers pass whatever list of readings they happen to have to hand, and they
compare the answers they get against each other, so two runs over the same
readings have to agree to the last digit.""",
        "names": ["mean"],
        "withheld": ["decimal", "round", "0.0", "2.333", "no numbers"],
        "trap": "withheld: rounded to 3 decimal places; a list with no numbers gives 0.0",
        "solution": r"""def mean(xs):
    if not xs:
        return 0.0
    return round(sum(xs) / len(xs), 3)
""",
        "bad_a": r"""def mean(xs):
    if not xs:
        return 0.0
    return sum(xs) / len(xs)
""",
        "bad_b": r"""def mean(xs):
    return round(sum(xs) / len(xs), 3)
""",
        "bad_c": r"""def average(xs):
    if not xs:
        return 0.0
    return round(sum(xs) / len(xs), 3)
""",
        "visible": [
            {"fn": "mean", "args": ([1, 2, 4],), "want": 2.333},
            {"fn": "mean", "args": ([],), "want": 0.0},
        ],
        "hidden_extra": [
            {"fn": "mean", "args": ([1, 2, 3],), "want": 2.0},
            {"fn": "mean", "args": ([0],), "want": 0.0},
            {"fn": "mean", "args": ([1, 1, 1, 1],), "want": 1.0},
            {"fn": "mean", "args": ([1, 2],), "want": 1.5},
            {"fn": "mean", "args": ([2, 3, 4, 5],), "want": 3.5},
            {"fn": "mean", "args": ([1, 2, 2],), "want": 1.667},
        ],
    },
    {
        "id": "s2_02_tally",
        "title": "tally(words)",
        "prose": """`tally(words)` takes a list of words and gives back a lookup from a
word to how many times it showed up.

The words come out of prose that people typed by hand, so the same word turns
up written in more than one way; the counts are meant to be about the word,
not about how it happened to be typed.""",
        "names": ["tally"],
        "withheld": ["lower", "upper case", "casefold", "case-insensitive"],
        "trap": "withheld: the keys are lower-cased",
        "solution": r"""def tally(words):
    out = {}
    for w in words:
        k = w.lower()
        out[k] = out.get(k, 0) + 1
    return out
""",
        "bad_a": r"""def tally(words):
    out = {}
    for w in words:
        out[w] = out.get(w, 0) + 1
    return out
""",
        "bad_b": r"""def tally(words):
    out = {}
    for w in words:
        k = w.lower()
        out[k] = out.get(k, 0) + 1
    return sorted(out.items())
""",
        "bad_c": r"""def count_words(words):
    out = {}
    for w in words:
        k = w.lower()
        out[k] = out.get(k, 0) + 1
    return out
""",
        "visible": [
            {"fn": "tally", "args": (["A", "a", "b"],), "want": {"a": 2, "b": 1}},
            {"fn": "tally", "args": ([],), "want": {}},
        ],
        "hidden_extra": [
            {"fn": "tally", "args": (["x"],), "want": {"x": 1}},
            {"fn": "tally", "args": (["Q", "q", "Q"],), "want": {"q": 3}},
            {"fn": "tally", "args": (["one", "two"],), "want": {"one": 1, "two": 1}},
            {"fn": "tally", "args": (["Mix", "mix", "MIX"],), "want": {"mix": 3}},
            {"fn": "tally", "args": (["a", "b", "a"],), "want": {"a": 2, "b": 1}},
        ],
    },
    {
        "id": "s2_03_top_n",
        "title": "top_n(counts, n)",
        "prose": """`top_n(counts, n)` takes a lookup from a name to a count and gives
back the n names carrying the highest counts, highest first.

Asking for more names than the lookup holds is allowed and simply gives back
all of them. The result is a plain list of names.""",
        "names": ["top_n"],
        "withheld": ["tie", "alphabetic", "ascending", "sorted by name",
                     "same count"],
        "trap": "withheld: names on the same count are ordered alphabetically",
        "solution": r"""def top_n(counts, n):
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:n]]
""",
        "bad_a": r"""def top_n(counts, n):
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return [k for k, _ in ranked[:n]]
""",
        "bad_b": r"""def top_n(counts, n):
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:n]
""",
        "bad_c": r"""def top_keys(counts, n):
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:n]]
""",
        "visible": [
            {"fn": "top_n", "args": ({"b": 2, "a": 2, "c": 1}, 2), "want": ["a", "b"]},
            {"fn": "top_n", "args": ({"x": 5}, 3), "want": ["x"]},
        ],
        "hidden_extra": [
            {"fn": "top_n", "args": ({"a": 1, "b": 3, "c": 2}, 2), "want": ["b", "c"]},
            {"fn": "top_n", "args": ({}, 3), "want": []},
            {"fn": "top_n", "args": ({"z": 1, "y": 1}, 1), "want": ["y"]},
            {"fn": "top_n", "args": ({"a": 1}, 0), "want": []},
            {"fn": "top_n", "args": ({"n": 2, "m": 2, "o": 2}, 3),
             "want": ["m", "n", "o"]},
        ],
    },
    {
        "id": "s2_04_split_csv",
        "title": "split_csv(line)",
        "prose": """`split_csv(line)` takes one line of comma-separated text and gives
back its fields in order as a list of strings.

There are no quoted fields and no escaped commas, so every comma separates.
The lines come straight off a file that sometimes has a blank line in it.""",
        "names": ["split_csv"],
        "withheld": ["strip", "surrounding space", "[]", "blank line gives",
                     "trim"],
        "trap": "withheld: fields are stripped; a line with nothing in it gives []",
        "solution": r"""def split_csv(line):
    if not line:
        return []
    return [p.strip() for p in line.split(",")]
""",
        "bad_a": r"""def split_csv(line):
    if not line:
        return []
    return line.split(",")
""",
        "bad_b": r"""def split_csv(line):
    return [p.strip() for p in line.split(",")]
""",
        "bad_c": r"""def parse_csv(line):
    if not line:
        return []
    return [p.strip() for p in line.split(",")]
""",
        "visible": [
            {"fn": "split_csv", "args": ("a, b ,c",), "want": ["a", "b", "c"]},
            {"fn": "split_csv", "args": ("",), "want": []},
        ],
        "hidden_extra": [
            {"fn": "split_csv", "args": ("a",), "want": ["a"]},
            {"fn": "split_csv", "args": ("a,,b",), "want": ["a", "", "b"]},
            {"fn": "split_csv", "args": (" x , y ",), "want": ["x", "y"]},
            {"fn": "split_csv", "args": (",",), "want": ["", ""]},
            {"fn": "split_csv", "args": ("one",), "want": ["one"]},
        ],
    },
    {
        "id": "s2_05_clamp",
        "title": "clamp(x, lo, hi)",
        "prose": """`clamp(x, lo, hi)` gives back x when it already sits between the two
bounds, and otherwise gives back the bound that x went past.

The bounds arrive from a configuration file that nobody validates, so they are
not always the right way round.""",
        "names": ["clamp"],
        "withheld": ["ValueError", "raise", "error", "the wrong way round is"],
        "trap": "withheld: lo above hi is rejected with a ValueError",
        "solution": r"""def clamp(x, lo, hi):
    if lo > hi:
        raise ValueError("lo must not be above hi")
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x
""",
        "bad_a": r"""def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x
""",
        "bad_b": r"""def clamp(x, lo, hi):
    if lo > hi:
        lo, hi = hi, lo
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x
""",
        "bad_c": r"""def pin(x, lo, hi):
    if lo > hi:
        raise ValueError("lo must not be above hi")
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x
""",
        "visible": [
            {"fn": "clamp", "args": (5, 1, 10), "want": 5},
            {"fn": "clamp", "args": (1, 10, 0), "raises": "ValueError"},
        ],
        "hidden_extra": [
            {"fn": "clamp", "args": (0, 1, 10), "want": 1},
            {"fn": "clamp", "args": (99, 1, 10), "want": 10},
            {"fn": "clamp", "args": (1, 1, 1), "want": 1},
            {"fn": "clamp", "args": (-5, -3, 3), "want": -3},
            {"fn": "clamp", "args": (2, 5, 1), "raises": "ValueError"},
        ],
    },
    {
        "id": "s2_06_pct",
        "title": "pct(part, whole)",
        "prose": """`pct(part, whole)` expresses the first number as a percentage of the
second and gives back a number.

It is called once per row of a report, and a report is allowed to hold a row
that nothing has happened to yet.""",
        "names": ["pct"],
        "withheld": ["decimal", "round", "33.3", "ZeroDivision", "0.0"],
        "trap": "withheld: one decimal place; a whole of nothing gives 0.0 not an error",
        "solution": r"""def pct(part, whole):
    if whole == 0:
        return 0.0
    return round(part * 100 / whole, 1)
""",
        "bad_a": r"""def pct(part, whole):
    if whole == 0:
        return 0.0
    return part * 100 / whole
""",
        "bad_b": r"""def pct(part, whole):
    return round(part * 100 / whole, 1)
""",
        "bad_c": r"""def percent(part, whole):
    if whole == 0:
        return 0.0
    return round(part * 100 / whole, 1)
""",
        "visible": [
            {"fn": "pct", "args": (1, 3), "want": 33.3},
            {"fn": "pct", "args": (4, 0), "want": 0.0},
        ],
        "hidden_extra": [
            {"fn": "pct", "args": (1, 2), "want": 50.0},
            {"fn": "pct", "args": (0, 5), "want": 0.0},
            {"fn": "pct", "args": (5, 5), "want": 100.0},
            {"fn": "pct", "args": (2, 3), "want": 66.7},
            {"fn": "pct", "args": (0, 0), "want": 0.0},
            {"fn": "pct", "args": (1, 8), "want": 12.5},
        ],
    },
    {
        "id": "s2_07_median",
        "title": "median(xs)",
        "prose": """`median(xs)` gives back the middle value of a list of numbers once
they have been put in order.

It is handed whatever the caller collected during a window, and some windows
turn out to have collected nothing.""",
        "names": ["median"],
        "withheld": ["ValueError", "halfway", "average of the two", "2.5",
                     "even"],
        "trap": "withheld: an even count averages the two middles; nothing at all raises ValueError",
        "solution": r"""def median(xs):
    if not xs:
        raise ValueError("median of nothing")
    ys = sorted(xs)
    n = len(ys)
    if n % 2:
        return ys[n // 2]
    return (ys[n // 2 - 1] + ys[n // 2]) / 2
""",
        "bad_a": r"""def median(xs):
    if not xs:
        raise ValueError("median of nothing")
    ys = sorted(xs)
    return ys[(len(ys) - 1) // 2]
""",
        "bad_b": r"""def median(xs):
    ys = sorted(xs)
    n = len(ys)
    if n % 2:
        return ys[n // 2]
    return (ys[n // 2 - 1] + ys[n // 2]) / 2
""",
        "bad_c": r"""def mid(xs):
    if not xs:
        raise ValueError("median of nothing")
    ys = sorted(xs)
    n = len(ys)
    if n % 2:
        return ys[n // 2]
    return (ys[n // 2 - 1] + ys[n // 2]) / 2
""",
        "visible": [
            {"fn": "median", "args": ([4, 1, 3, 2],), "want": 2.5},
            {"fn": "median", "args": ([],), "raises": "ValueError"},
        ],
        "hidden_extra": [
            {"fn": "median", "args": ([1],), "want": 1},
            {"fn": "median", "args": ([3, 1, 2],), "want": 2},
            {"fn": "median", "args": ([1, 2],), "want": 1.5},
            {"fn": "median", "args": ([5, 5],), "want": 5.0},
            {"fn": "median", "args": ([-1, 0, 1],), "want": 0},
            {"fn": "median", "args": ([1, 2, 3, 4, 5, 6],), "want": 3.5},
        ],
    },
    {
        "id": "s2_08_dedupe",
        "title": "dedupe(xs)",
        "prose": """`dedupe(xs)` takes a list of strings and gives back a list with the
repeats taken out, in the order the survivors were first met.

The strings are tags that people typed themselves, so the same tag arrives
typed several different ways and the team wants one row per tag, spelled the
way it was first written down.""",
        "names": ["dedupe"],
        "withheld": ["lower", "case-insensitive", "ignoring case"],
        "trap": "withheld: the comparison ignores case, the first spelling is what stays",
        "solution": r"""def dedupe(xs):
    seen = set()
    out = []
    for x in xs:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out
""",
        "bad_a": r"""def dedupe(xs):
    seen = set()
    out = []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
""",
        "bad_b": r"""def dedupe(xs):
    out = {}
    for x in xs:
        out[x.lower()] = x
    return list(out.values())
""",
        "bad_c": r"""def uniq(xs):
    seen = set()
    out = []
    for x in xs:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out
""",
        "visible": [
            {"fn": "dedupe", "args": (["Ab", "ab", "b"],), "want": ["Ab", "b"]},
            {"fn": "dedupe", "args": ([],), "want": []},
        ],
        "hidden_extra": [
            {"fn": "dedupe", "args": (["a"],), "want": ["a"]},
            {"fn": "dedupe", "args": (["A", "a", "A"],), "want": ["A"]},
            {"fn": "dedupe", "args": (["x", "y", "X"],), "want": ["x", "y"]},
            {"fn": "dedupe", "args": (["one", "two", "ONE"],), "want": ["one", "two"]},
            {"fn": "dedupe", "args": (["p", "q"],), "want": ["p", "q"]},
        ],
    },
    {
        "id": "s2_09_chunks",
        "title": "chunks(xs, n)",
        "prose": """`chunks(xs, n)` cuts a list into consecutive pieces of size n, in
order, and gives the pieces back gathered in one list. The last piece is
whatever is left over and may be shorter than the others.

The size arrives from a command line flag, and callers do not always pass
something sensible.""",
        "names": ["chunks"],
        "withheld": ["ValueError", "positive", "zero or", "raise"],
        "trap": "withheld: a size that is not positive is rejected with a ValueError",
        "solution": r"""def chunks(xs, n):
    if n <= 0:
        raise ValueError("n must be positive")
    return [xs[i:i + n] for i in range(0, len(xs), n)]
""",
        "bad_a": r"""def chunks(xs, n):
    if n <= 0:
        return []
    return [xs[i:i + n] for i in range(0, len(xs), n)]
""",
        "bad_b": r"""def chunks(xs, n):
    if n <= 0:
        raise ValueError("n must be positive")
    return [xs[i:i + n] for i in range(0, len(xs), n) if i + n <= len(xs)]
""",
        "bad_c": r"""def chunk(xs, n):
    if n <= 0:
        raise ValueError("n must be positive")
    return [xs[i:i + n] for i in range(0, len(xs), n)]
""",
        "visible": [
            {"fn": "chunks", "args": ([1, 2, 3], 2), "want": [[1, 2], [3]]},
            {"fn": "chunks", "args": ([1], 0), "raises": "ValueError"},
        ],
        "hidden_extra": [
            {"fn": "chunks", "args": ([], 3), "want": []},
            {"fn": "chunks", "args": ([1, 2], 5), "want": [[1, 2]]},
            {"fn": "chunks", "args": ([1, 2, 3, 4], 2), "want": [[1, 2], [3, 4]]},
            {"fn": "chunks", "args": ([1], -1), "raises": "ValueError"},
            {"fn": "chunks", "args": ([1, 2, 3], 1), "want": [[1], [2], [3]]},
        ],
    },
    {
        "id": "s2_10_wrap",
        "title": "wrap(s, width)",
        "prose": """`wrap(s, width)` breaks a line of text so that no piece comes out
longer than `width` characters, breaking between words. It gives the pieces
back in order, gathered in one list.

Words are separated by whitespace on the way in and by a single space inside a
piece. The text is a log message, and log messages contain identifiers that
nobody chose for their brevity.""",
        "names": ["wrap"],
        "withheld": ["never cut", "on a piece of its own", "not broken",
                     "longer than width"],
        "trap": "withheld: a word longer than width is never cut, it gets a piece of its own",
        "solution": r"""def wrap(s, width):
    lines = []
    cur = ""
    for w in s.split():
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines
""",
        "bad_a": r"""def wrap(s, width):
    joined = " ".join(s.split())
    return [joined[i:i + width] for i in range(0, len(joined), width)]
""",
        "bad_b": r"""def wrap(s, width):
    lines = []
    cur = ""
    for w in s.split():
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return "\n".join(lines)
""",
        "bad_c": r"""def wrap_text(s, width):
    lines = []
    cur = ""
    for w in s.split():
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines
""",
        "visible": [
            {"fn": "wrap", "args": ("a bb ccc", 5), "want": ["a bb", "ccc"]},
            {"fn": "wrap", "args": ("enormous", 3), "want": ["enormous"]},
        ],
        "hidden_extra": [
            {"fn": "wrap", "args": ("", 5), "want": []},
            {"fn": "wrap", "args": ("one two", 100), "want": ["one two"]},
            {"fn": "wrap", "args": ("a a a a", 3), "want": ["a a", "a a"]},
            {"fn": "wrap", "args": ("xx yy zz", 5), "want": ["xx yy", "zz"]},
            {"fn": "wrap", "args": ("word", 4), "want": ["word"]},
        ],
    },
    {
        "id": "s2_11_titleize",
        "title": "titleize(s)",
        "prose": """`titleize(s)` gives back a phrase with the first letter of each word
capitalised.

Words are separated by single spaces. The phrases are headings copied out of
technical documents, so they carry the names of protocols and organisations
alongside ordinary prose.""",
        "names": ["titleize"],
        "withheld": ["acronym", "already", "all in upper case", "unchanged",
                     "left alone"],
        "trap": "withheld: a word already written entirely in upper case is left alone",
        "solution": r"""def titleize(s):
    out = []
    for w in s.split(" "):
        if w.isupper():
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)
""",
        "bad_a": r"""def titleize(s):
    return s.title()
""",
        "bad_b": r"""def titleize(s):
    return " ".join(w[:1].upper() + w[1:].lower() for w in s.split(" "))
""",
        "bad_c": r"""def title_case(s):
    out = []
    for w in s.split(" "):
        if w.isupper():
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)
""",
        "visible": [
            {"fn": "titleize", "args": ("the NASA report",), "want": "The NASA Report"},
            {"fn": "titleize", "args": ("hello world",), "want": "Hello World"},
        ],
        "hidden_extra": [
            {"fn": "titleize", "args": ("",), "want": ""},
            {"fn": "titleize", "args": ("a",), "want": "A"},
            {"fn": "titleize", "args": ("HTTP is fine",), "want": "HTTP Is Fine"},
            {"fn": "titleize", "args": ("mIxEd case",), "want": "Mixed Case"},
            {"fn": "titleize", "args": ("ABC def",), "want": "ABC Def"},
            {"fn": "titleize", "args": ("one",), "want": "One"},
        ],
    },
    {
        "id": "s2_12_slugify",
        "title": "slugify(s)",
        "prose": """`slugify(s)` turns a title into a lower-case URL fragment made only
of letters, digits and hyphens.

Anything that is not a letter or a digit gives way to a hyphen. The titles are
typed by editors, complete with punctuation, spacing and the occasional
decorative dash at either end.""",
        "names": ["slugify"],
        "withheld": ["collapse", "run of", "two hyphens", "strip", "trim",
                     "never starts"],
        "trap": "withheld: runs of hyphens collapse to one, and hyphens at either end go",
        "solution": r"""def slugify(s):
    t = "".join(c if c.isalnum() else "-" for c in s.lower())
    while "--" in t:
        t = t.replace("--", "-")
    return t.strip("-")
""",
        "bad_a": r"""def slugify(s):
    t = "".join(c if c.isalnum() else "-" for c in s.lower())
    return t.strip("-")
""",
        "bad_b": r"""def slugify(s):
    t = "".join(c if c.isalnum() else "-" for c in s.lower())
    while "--" in t:
        t = t.replace("--", "-")
    return t
""",
        "bad_c": r"""def slug(s):
    t = "".join(c if c.isalnum() else "-" for c in s.lower())
    while "--" in t:
        t = t.replace("--", "-")
    return t.strip("-")
""",
        "visible": [
            {"fn": "slugify", "args": ("Hello,  World!",), "want": "hello-world"},
            {"fn": "slugify", "args": ("--A--",), "want": "a"},
        ],
        "hidden_extra": [
            {"fn": "slugify", "args": ("",), "want": ""},
            {"fn": "slugify", "args": ("abc",), "want": "abc"},
            {"fn": "slugify", "args": ("A B",), "want": "a-b"},
            {"fn": "slugify", "args": ("x___y",), "want": "x-y"},
            {"fn": "slugify", "args": ("1 2 3",), "want": "1-2-3"},
            {"fn": "slugify", "args": ("!!!",), "want": ""},
        ],
    },
    {
        "id": "s2_13_parse_int",
        "title": "parse_int(s)",
        "prose": """`parse_int(s)` reads a whole number out of a piece of text and gives
it back as a number. Text that does not spell a whole number is rejected with
a ValueError.

The caller is a configuration reader, and the values it hands over have
already been through several layers that are not fussy about what they pass
along.""",
        "names": ["parse_int"],
        "withheld": ["TypeError", "isinstance", "not a string", "not text"],
        "trap": "withheld: something that is not text at all is a TypeError, not a ValueError",
        "solution": r"""def parse_int(s):
    if not isinstance(s, str):
        raise TypeError("parse_int wants text")
    return int(s.strip())
""",
        "bad_a": r"""def parse_int(s):
    return int(str(s).strip())
""",
        "bad_b": r"""def parse_int(s):
    try:
        return int(str(s).strip())
    except ValueError:
        return None
""",
        "bad_c": r"""def to_int(s):
    if not isinstance(s, str):
        raise TypeError("to_int wants text")
    return int(s.strip())
""",
        "visible": [
            {"fn": "parse_int", "args": (" 42 ",), "want": 42},
            {"fn": "parse_int", "args": (5,), "raises": "TypeError"},
        ],
        "hidden_extra": [
            {"fn": "parse_int", "args": ("0",), "want": 0},
            {"fn": "parse_int", "args": ("-7",), "want": -7},
            {"fn": "parse_int", "args": ("+3",), "want": 3},
            {"fn": "parse_int", "args": ("x",), "raises": "ValueError"},
            {"fn": "parse_int", "args": ("",), "raises": "ValueError"},
            {"fn": "parse_int", "args": (None,), "raises": "TypeError"},
        ],
    },
    {
        "id": "s2_14_range_sum",
        "title": "range_sum(a, b)",
        "prose": """`range_sum(a, b)` adds up the whole numbers lying between the two
bounds it is handed and gives back the total.

The bounds are row numbers picked out of a spreadsheet by a user dragging a
selection, which they sometimes drag upwards.""",
        "names": ["range_sum"],
        "withheld": ["inclusive", "both bounds count", "15", "0 when"],
        "trap": "withheld: both bounds are counted in; a first bound above the second gives 0",
        "solution": r"""def range_sum(a, b):
    if a > b:
        return 0
    return sum(range(a, b + 1))
""",
        "bad_a": r"""def range_sum(a, b):
    if a > b:
        return 0
    return sum(range(a, b))
""",
        "bad_b": r"""def range_sum(a, b):
    if a > b:
        raise ValueError("a above b")
    return sum(range(a, b + 1))
""",
        "bad_c": r"""def sum_range(a, b):
    if a > b:
        return 0
    return sum(range(a, b + 1))
""",
        "visible": [
            {"fn": "range_sum", "args": (1, 5), "want": 15},
            {"fn": "range_sum", "args": (5, 1), "want": 0},
        ],
        "hidden_extra": [
            {"fn": "range_sum", "args": (0, 0), "want": 0},
            {"fn": "range_sum", "args": (3, 3), "want": 3},
            {"fn": "range_sum", "args": (-2, 2), "want": 0},
            {"fn": "range_sum", "args": (1, 100), "want": 5050},
            {"fn": "range_sum", "args": (-3, -1), "want": -6},
            {"fn": "range_sum", "args": (2, 4), "want": 9},
        ],
    },
    {
        "id": "s2_15_normalize",
        "title": "normalize(p)",
        "prose": """`normalize(p)` tidies a forward-slash path: a run of separators
becomes a single separator.

The paths are joined together by other code that is careless about whether a
piece already ends in a separator, so what arrives here has separators in
places nobody meant to put one.""",
        "names": ["normalize"],
        "withheld": ["trailing", "at the end", "except", "root"],
        "trap": "withheld: a separator at the very end goes, unless the whole path is one",
        "solution": r"""def normalize(p):
    while "//" in p:
        p = p.replace("//", "/")
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p
""",
        "bad_a": r"""def normalize(p):
    while "//" in p:
        p = p.replace("//", "/")
    return p.rstrip("/")
""",
        "bad_b": r"""def normalize(p):
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p
""",
        "bad_c": r"""def norm_path(p):
    while "//" in p:
        p = p.replace("//", "/")
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p
""",
        "visible": [
            {"fn": "normalize", "args": ("a//b/",), "want": "a/b"},
            {"fn": "normalize", "args": ("/",), "want": "/"},
        ],
        "hidden_extra": [
            {"fn": "normalize", "args": ("",), "want": ""},
            {"fn": "normalize", "args": ("a",), "want": "a"},
            {"fn": "normalize", "args": ("/a/",), "want": "/a"},
            {"fn": "normalize", "args": ("///",), "want": "/"},
            {"fn": "normalize", "args": ("a/b//c",), "want": "a/b/c"},
            {"fn": "normalize", "args": ("./x/",), "want": "./x"},
        ],
    },
    {
        "id": "s2_16_size_label",
        "title": "size_label(n)",
        "prose": """`size_label(n)` turns a count of bytes into a short label for a user
interface, using the units B, KB, MB and GB and stopping at the largest unit
the number reaches.

The labels sit in a column next to each other in a file listing, so they are
meant to line up and read consistently.""",
        "names": ["size_label"],
        "withheld": ["1024", "1.5 KB", "one decimal", "a space before",
                     "%.1f"],
        "trap": "withheld: the step is 1024, one decimal place above B, a space before the unit",
        "solution": r"""def size_label(n):
    units = ["B", "KB", "MB", "GB"]
    i = 0
    v = float(n)
    while v >= 1024 and i < 3:
        v /= 1024
        i += 1
    if i == 0:
        return "%d B" % n
    return "%.1f %s" % (v, units[i])
""",
        "bad_a": r"""def size_label(n):
    units = ["B", "KB", "MB", "GB"]
    i = 0
    v = float(n)
    while v >= 1000 and i < 3:
        v /= 1000
        i += 1
    if i == 0:
        return "%d B" % n
    return "%.1f %s" % (v, units[i])
""",
        "bad_b": r"""def size_label(n):
    units = ["B", "KB", "MB", "GB"]
    i = 0
    v = float(n)
    while v >= 1024 and i < 3:
        v /= 1024
        i += 1
    if i == 0:
        return "%dB" % n
    return "%.1f%s" % (v, units[i])
""",
        "bad_c": r"""def human_size(n):
    units = ["B", "KB", "MB", "GB"]
    i = 0
    v = float(n)
    while v >= 1024 and i < 3:
        v /= 1024
        i += 1
    if i == 0:
        return "%d B" % n
    return "%.1f %s" % (v, units[i])
""",
        "visible": [
            {"fn": "size_label", "args": (1536,), "want": "1.5 KB"},
            {"fn": "size_label", "args": (512,), "want": "512 B"},
            {"fn": "size_label", "args": (1023,), "want": "1023 B"},
        ],
        "hidden_extra": [
            {"fn": "size_label", "args": (0,), "want": "0 B"},
            {"fn": "size_label", "args": (1024,), "want": "1.0 KB"},
            {"fn": "size_label", "args": (1048576,), "want": "1.0 MB"},
            {"fn": "size_label", "args": (1610612736,), "want": "1.5 GB"},
            {"fn": "size_label", "args": (2048,), "want": "2.0 KB"},
        ],
    },
    {
        "id": "s2_17_ordinal",
        "title": "ordinal(n)",
        "prose": """`ordinal(n)` writes a positive whole number as a position: the number
itself followed by st, nd, rd or th.

It is used to label the rows of a leaderboard, which is long enough that the
whole of the second decade shows up on it.""",
        "names": ["ordinal"],
        "withheld": ["11", "12", "13", "teen", "exception"],
        "trap": "withheld: the three teens take th regardless of their last digit",
        "solution": r"""def ordinal(n):
    if n % 100 in (11, 12, 13):
        tail = "th"
    else:
        tail = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, tail)
""",
        "bad_a": r"""def ordinal(n):
    tail = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, tail)
""",
        "bad_b": r"""def ordinal(n):
    if n % 100 in (11, 12, 13):
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
""",
        "bad_c": r"""def ord_suffix(n):
    if n % 100 in (11, 12, 13):
        tail = "th"
    else:
        tail = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, tail)
""",
        "visible": [
            {"fn": "ordinal", "args": (12,), "want": "12th"},
            {"fn": "ordinal", "args": (21,), "want": "21st"},
        ],
        "hidden_extra": [
            {"fn": "ordinal", "args": (1,), "want": "1st"},
            {"fn": "ordinal", "args": (2,), "want": "2nd"},
            {"fn": "ordinal", "args": (3,), "want": "3rd"},
            {"fn": "ordinal", "args": (4,), "want": "4th"},
            {"fn": "ordinal", "args": (11,), "want": "11th"},
            {"fn": "ordinal", "args": (113,), "want": "113th"},
            {"fn": "ordinal", "args": (22,), "want": "22nd"},
        ],
    },
    {
        "id": "s2_18_is_palindrome",
        "title": "is_palindrome(s)",
        "prose": """`is_palindrome(s)` says whether a piece of text reads the same
forwards and backwards, giving back a true or false value.

The texts are phrases people submit to a puzzle page, typed the way an English
sentence is normally typed.""",
        "names": ["is_palindrome"],
        "withheld": ["punctuation", "ignoring case", "alphanumeric",
                     "letters and digits", "spaces are"],
        "trap": "withheld: only letters and digits are looked at, and case is set aside",
        "solution": r"""def is_palindrome(s):
    t = [c.lower() for c in s if c.isalnum()]
    return t == t[::-1]
""",
        "bad_a": r"""def is_palindrome(s):
    return s == s[::-1]
""",
        "bad_b": r"""def is_palindrome(s):
    t = [c.lower() for c in s if c.isalnum()]
    return "yes" if t == t[::-1] else "no"
""",
        "bad_c": r"""def is_pal(s):
    t = [c.lower() for c in s if c.isalnum()]
    return t == t[::-1]
""",
        "visible": [
            {"fn": "is_palindrome", "args": ("A man, a plan, a canal: Panama",),
             "want": True},
            {"fn": "is_palindrome", "args": ("ab",), "want": False},
        ],
        "hidden_extra": [
            {"fn": "is_palindrome", "args": ("",), "want": True},
            {"fn": "is_palindrome", "args": ("Racecar",), "want": True},
            {"fn": "is_palindrome", "args": ("abc",), "want": False},
            {"fn": "is_palindrome", "args": ("12321",), "want": True},
            {"fn": "is_palindrome", "args": ("No 'x' in Nixon",), "want": True},
            {"fn": "is_palindrome", "args": ("!!",), "want": True},
        ],
    },
    {
        "id": "s2_19_group_by_first",
        "title": "group_by_first(words)",
        "prose": """`group_by_first(words)` sorts words into a lookup keyed by the letter
each one starts with, keeping each group in the order the words arrived.

The words are read out of a file one per line, so what arrives is whatever the
file held, including the odd line that held nothing.""",
        "names": ["group_by_first"],
        "withheld": ["lower", "dropped", "skipped", "case"],
        "trap": "withheld: the key is lower-cased, and a word with nothing in it is dropped",
        "solution": r"""def group_by_first(words):
    out = {}
    for w in words:
        if not w:
            continue
        out.setdefault(w[0].lower(), []).append(w)
    return out
""",
        "bad_a": r"""def group_by_first(words):
    out = {}
    for w in words:
        if not w:
            continue
        out.setdefault(w[0], []).append(w)
    return out
""",
        "bad_b": r"""def group_by_first(words):
    out = {}
    for w in words:
        out.setdefault(w[:1].lower(), []).append(w)
    return out
""",
        "bad_c": r"""def group_first(words):
    out = {}
    for w in words:
        if not w:
            continue
        out.setdefault(w[0].lower(), []).append(w)
    return out
""",
        "visible": [
            {"fn": "group_by_first", "args": (["Apple", "ant", "Bee"],),
             "want": {"a": ["Apple", "ant"], "b": ["Bee"]}},
            {"fn": "group_by_first", "args": (["", "x"],), "want": {"x": ["x"]}},
        ],
        "hidden_extra": [
            {"fn": "group_by_first", "args": ([],), "want": {}},
            {"fn": "group_by_first", "args": (["z"],), "want": {"z": ["z"]}},
            {"fn": "group_by_first", "args": (["A", "a"],), "want": {"a": ["A", "a"]}},
            {"fn": "group_by_first", "args": (["one", "two"],),
             "want": {"o": ["one"], "t": ["two"]}},
            {"fn": "group_by_first", "args": (["", ""],), "want": {}},
        ],
    },
    {
        "id": "s2_20_merge",
        "title": "merge(a, b)",
        "prose": """`merge(a, b)` combines two lookups into one new lookup holding
everything from both of them.

The first is the set of defaults shipped with the program and the second is
what the user put in their own configuration file.""",
        "names": ["merge"],
        "withheld": ["wins", "overrides", "takes precedence", "beats"],
        "trap": "withheld: on a clash the second lookup is the one that wins",
        "solution": r"""def merge(a, b):
    out = dict(a)
    out.update(b)
    return out
""",
        "bad_a": r"""def merge(a, b):
    out = dict(b)
    out.update(a)
    return out
""",
        "bad_b": r"""def merge(a, b):
    return list(a.items()) + list(b.items())
""",
        "bad_c": r"""def merge_dicts(a, b):
    out = dict(a)
    out.update(b)
    return out
""",
        "visible": [
            {"fn": "merge", "args": ({"x": 1}, {"x": 2, "y": 3}),
             "want": {"x": 2, "y": 3}},
            {"fn": "merge", "args": ({}, {}), "want": {}},
        ],
        "hidden_extra": [
            {"fn": "merge", "args": ({"a": 1}, {"b": 2}), "want": {"a": 1, "b": 2}},
            {"fn": "merge", "args": ({"a": 1}, {}), "want": {"a": 1}},
            {"fn": "merge", "args": ({}, {"b": 2}), "want": {"b": 2}},
            {"fn": "merge", "args": ({"k": 0}, {"k": 0}), "want": {"k": 0}},
            {"fn": "merge", "args": ({"p": 1, "q": 2}, {"q": 9}),
             "want": {"p": 1, "q": 9}},
        ],
    },
    {
        "id": "s2_21_flatten",
        "title": "flatten(xs)",
        "prose": """`flatten(xs)` gives back a single list gathered from the entries of
the list it is handed.

The list is the result of collecting answers from several workers: a worker
that had several answers put a list in, and a worker that had exactly one put
the answer itself in.""",
        "names": ["flatten"],
        "withheld": ["one level", "not recurse", "deeper", "as they are"],
        "trap": "withheld: only one level is undone; a deeper list stays a list",
        "solution": r"""def flatten(xs):
    out = []
    for x in xs:
        if isinstance(x, list):
            out.extend(x)
        else:
            out.append(x)
    return out
""",
        "bad_a": r"""def flatten(xs):
    out = []
    for x in xs:
        if isinstance(x, list):
            out.extend(flatten(x))
        else:
            out.append(x)
    return out
""",
        "bad_b": r"""def flatten(xs):
    return [y for x in xs for y in x]
""",
        "bad_c": r"""def flat(xs):
    out = []
    for x in xs:
        if isinstance(x, list):
            out.extend(x)
        else:
            out.append(x)
    return out
""",
        "visible": [
            {"fn": "flatten", "args": ([[1, 2], 3, [[4]]],), "want": [1, 2, 3, [4]]},
            {"fn": "flatten", "args": ([],), "want": []},
        ],
        "hidden_extra": [
            {"fn": "flatten", "args": ([[1]],), "want": [1]},
            {"fn": "flatten", "args": ([1, 2],), "want": [1, 2]},
            {"fn": "flatten", "args": ([[], [1]],), "want": [1]},
            {"fn": "flatten", "args": ([[1, [2]]],), "want": [1, [2]]},
            {"fn": "flatten", "args": ([["a"], "b"],), "want": ["a", "b"]},
        ],
    },
    {
        "id": "s2_22_only_in_first",
        "title": "only_in_first(a, b)",
        "prose": """`only_in_first(a, b)` gives back the entries of the first list that
are not in the second one.

The first list is a log of events in the order they happened, and the second
is the set of event names that have already been dealt with.""",
        "names": ["only_in_first"],
        "withheld": ["duplicate", "repeat", "as many times",
                     "same order as the first"],
        "trap": "withheld: the order of the first list and its repeats are both kept",
        "solution": r"""def only_in_first(a, b):
    return [x for x in a if x not in b]
""",
        "bad_a": r"""def only_in_first(a, b):
    return sorted(set(a) - set(b))
""",
        "bad_b": r"""def only_in_first(a, b):
    return set(a) - set(b)
""",
        "bad_c": r"""def difference(a, b):
    return [x for x in a if x not in b]
""",
        "visible": [
            {"fn": "only_in_first", "args": ([3, 1, 3, 2], [2]), "want": [3, 1, 3]},
            {"fn": "only_in_first", "args": ([], [1]), "want": []},
        ],
        "hidden_extra": [
            {"fn": "only_in_first", "args": ([1], [1]), "want": []},
            {"fn": "only_in_first", "args": ([1, 2], []), "want": [1, 2]},
            {"fn": "only_in_first", "args": (["a", "a"], ["b"]), "want": ["a", "a"]},
            {"fn": "only_in_first", "args": ([1, 1, 2], [1]), "want": [2]},
            {"fn": "only_in_first", "args": ([5, 4], [4]), "want": [5]},
        ],
    },
    {
        "id": "s2_23_running_total",
        "title": "running_total(xs)",
        "prose": """`running_total(xs)` reports the total accumulated as a list of
numbers is walked from the start.

It feeds a chart where each point sits above the reading it belongs to, so a
point and a reading have to line up.""",
        "names": ["running_total"],
        "withheld": ["same length", "including", "inclusive", "[1, 3, 6]"],
        "trap": "withheld: one entry per reading, and the reading itself is included",
        "solution": r"""def running_total(xs):
    out = []
    t = 0
    for x in xs:
        t += x
        out.append(t)
    return out
""",
        "bad_a": r"""def running_total(xs):
    out = []
    t = 0
    for x in xs:
        out.append(t)
        t += x
    return out
""",
        "bad_b": r"""def running_total(xs):
    out = [0]
    t = 0
    for x in xs:
        t += x
        out.append(t)
    return out
""",
        "bad_c": r"""def cumsum(xs):
    out = []
    t = 0
    for x in xs:
        t += x
        out.append(t)
    return out
""",
        "visible": [
            {"fn": "running_total", "args": ([1, 2, 3],), "want": [1, 3, 6]},
            {"fn": "running_total", "args": ([],), "want": []},
        ],
        "hidden_extra": [
            {"fn": "running_total", "args": ([5],), "want": [5]},
            {"fn": "running_total", "args": ([0, 0],), "want": [0, 0]},
            {"fn": "running_total", "args": ([-1, 1],), "want": [-1, 0]},
            {"fn": "running_total", "args": ([2, 2, 2],), "want": [2, 4, 6]},
            {"fn": "running_total", "args": ([10],), "want": [10]},
        ],
    },
    {
        "id": "s2_24_round_money",
        "title": "round_money(x)",
        "prose": """`round_money(x)` gives back an amount of money as a number with its
cents resolved.

It is used on invoice lines, and the finance team reconciles the result
against what their accounting package produces for the same figures.""",
        "names": ["round_money"],
        "withheld": ["half", "away from zero", "banker", "2.68", "Decimal",
                     "two decimal"],
        "trap": "withheld: a half goes away from zero, not to the even digit",
        "solution": r"""from decimal import Decimal, ROUND_HALF_UP


def round_money(x):
    return float(Decimal(str(x)).quantize(Decimal("0.01"),
                                          rounding=ROUND_HALF_UP))
""",
        "bad_a": r"""def round_money(x):
    return round(x, 2)
""",
        "bad_b": r"""def round_money(x):
    return int(x * 100) / 100
""",
        "bad_c": r"""from decimal import Decimal, ROUND_HALF_UP


def round_to_cents(x):
    return float(Decimal(str(x)).quantize(Decimal("0.01"),
                                          rounding=ROUND_HALF_UP))
""",
        "visible": [
            {"fn": "round_money", "args": (2.675,), "want": 2.68},
            {"fn": "round_money", "args": (0.125,), "want": 0.13},
        ],
        "hidden_extra": [
            {"fn": "round_money", "args": (1.005,), "want": 1.01},
            {"fn": "round_money", "args": (2.0,), "want": 2.0},
            {"fn": "round_money", "args": (-1.005,), "want": -1.01},
            {"fn": "round_money", "args": (0.0,), "want": 0.0},
            {"fn": "round_money", "args": (3.14159,), "want": 3.14},
            {"fn": "round_money", "args": (2.5,), "want": 2.5},
        ],
    },
    {
        "id": "s2_25_truncate",
        "title": "truncate(s, n)",
        "prose": """`truncate(s, n)` shortens a piece of text so that it fits a column
`n` characters wide, marking that it was shortened by putting an ellipsis of
three dots at the end. Text that already fits is given back untouched.

The column is part of a fixed-width table, and the table's borders line up.""",
        "names": ["truncate"],
        "withheld": ["count towards", "including the", "n - 3", "ab...",
                     "three dots count"],
        "trap": "withheld: the three dots count towards n, so the result is never longer than n",
        "solution": r"""def truncate(s, n):
    if len(s) <= n:
        return s
    return s[:max(n - 3, 0)] + "..."
""",
        "bad_a": r"""def truncate(s, n):
    if len(s) <= n:
        return s
    return s[:n] + "..."
""",
        "bad_b": r"""def truncate(s, n):
    if len(s) <= n:
        return s
    return s[:max(n - 1, 0)] + "…"
""",
        "bad_c": r"""def shorten(s, n):
    if len(s) <= n:
        return s
    return s[:max(n - 3, 0)] + "..."
""",
        "visible": [
            {"fn": "truncate", "args": ("abcdefgh", 5), "want": "ab..."},
            {"fn": "truncate", "args": ("abc", 3), "want": "abc"},
        ],
        "hidden_extra": [
            {"fn": "truncate", "args": ("", 5), "want": ""},
            {"fn": "truncate", "args": ("abcd", 4), "want": "abcd"},
            {"fn": "truncate", "args": ("abcde", 4), "want": "a..."},
            {"fn": "truncate", "args": ("hello world", 8), "want": "hello..."},
            {"fn": "truncate", "args": ("xyz", 10), "want": "xyz"},
            {"fn": "truncate", "args": ("abcdef", 3), "want": "..."},
        ],
    },
    {
        "id": "s2_26_initials",
        "title": "initials(name)",
        "prose": """`initials(name)` reduces a person's full name to its initials and
gives them back as text. The parts of a name are separated by spaces.

The names come from a membership list of a European society, where compound
given names joined by a punctuation mark are common and both halves are part
of how someone is addressed.""",
        "names": ["initials"],
        "withheld": ["hyphen", "dot after", "A.L.", "upper case", "full stop"],
        "trap": "withheld: dotted upper case, and a hyphenated part contributes both halves",
        "solution": r"""def initials(name):
    out = []
    for part in name.split():
        for piece in part.split("-"):
            if piece:
                out.append(piece[0].upper() + ".")
    return "".join(out)
""",
        "bad_a": r"""def initials(name):
    out = []
    for part in name.split():
        for piece in part.split("-"):
            if piece:
                out.append(piece[0].upper())
    return "".join(out)
""",
        "bad_b": r"""def initials(name):
    return "".join(p[0].upper() + "." for p in name.split())
""",
        "bad_c": r"""def get_initials(name):
    out = []
    for part in name.split():
        for piece in part.split("-"):
            if piece:
                out.append(piece[0].upper() + ".")
    return "".join(out)
""",
        "visible": [
            {"fn": "initials", "args": ("ada lovelace",), "want": "A.L."},
            {"fn": "initials", "args": ("jean-luc picard",), "want": "J.L.P."},
        ],
        "hidden_extra": [
            {"fn": "initials", "args": ("",), "want": ""},
            {"fn": "initials", "args": ("x",), "want": "X."},
            {"fn": "initials", "args": ("Mary Jane Watson",), "want": "M.J.W."},
            {"fn": "initials", "args": ("anne-marie",), "want": "A.M."},
            {"fn": "initials", "args": ("  a  b ",), "want": "A.B."},
        ],
    },
    {
        "id": "s2_27_count_lines",
        "title": "count_lines(text)",
        "prose": """`count_lines(text)` reports how many lines a piece of text holds.

The text is read whole out of a file. Some of the tools that write those files
finish the last line properly and some of them do not, and the count is meant
to be the same either way.""",
        "names": ["count_lines"],
        "withheld": ["splitlines", "trailing newline does not", "0", "zero"],
        "trap": "withheld: a line break at the very end adds nothing; text with nothing in it has no lines",
        "solution": r"""def count_lines(text):
    return len(text.splitlines())
""",
        "bad_a": r"""def count_lines(text):
    return text.count("\n")
""",
        "bad_b": r"""def count_lines(text):
    return len(text.split("\n"))
""",
        "bad_c": r"""def line_count(text):
    return len(text.splitlines())
""",
        "visible": [
            {"fn": "count_lines", "args": ("a\nb\n",), "want": 2},
            {"fn": "count_lines", "args": ("a\nb",), "want": 2},
            {"fn": "count_lines", "args": ("",), "want": 0},
        ],
        "hidden_extra": [
            {"fn": "count_lines", "args": ("a",), "want": 1},
            {"fn": "count_lines", "args": ("\n",), "want": 1},
            {"fn": "count_lines", "args": ("\n\n",), "want": 2},
            {"fn": "count_lines", "args": ("x\ny\nz\n",), "want": 3},
            {"fn": "count_lines", "args": ("one\n",), "want": 1},
        ],
    },
    {
        "id": "s2_28_parse_kv",
        "title": "parse_kv(line)",
        "prose": """`parse_kv(line)` reads a settings line of name=value pairs separated
by semicolons and gives back the lookup from name to value, both kept as text
with the spaces around them removed. A stretch between two semicolons with
nothing in it is skipped.

Lines are edited by hand, so both the same name written twice and a pair with
its equals sign missing turn up in real files.""",
        "names": ["parse_kv"],
        "withheld": ["later", "wins", "ValueError", "last one", "rejected"],
        "trap": "withheld: later wins on a repeat; a pair with no equals sign raises ValueError",
        "solution": r"""def parse_kv(line):
    out = {}
    for part in line.split(";"):
        if not part.strip():
            continue
        if "=" not in part:
            raise ValueError("no '=' in %r" % part)
        name, _, value = part.partition("=")
        out[name.strip()] = value.strip()
    return out
""",
        "bad_a": r"""def parse_kv(line):
    out = {}
    for part in line.split(";"):
        if not part.strip():
            continue
        if "=" not in part:
            raise ValueError("no '=' in %r" % part)
        name, _, value = part.partition("=")
        out.setdefault(name.strip(), value.strip())
    return out
""",
        "bad_b": r"""def parse_kv(line):
    out = {}
    for part in line.split(";"):
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        out[name.strip()] = value.strip()
    return out
""",
        "bad_c": r"""def parse_settings(line):
    out = {}
    for part in line.split(";"):
        if not part.strip():
            continue
        if "=" not in part:
            raise ValueError("no '=' in %r" % part)
        name, _, value = part.partition("=")
        out[name.strip()] = value.strip()
    return out
""",
        "visible": [
            {"fn": "parse_kv", "args": ("a=1;a=2",), "want": {"a": "2"}},
            {"fn": "parse_kv", "args": ("bare",), "raises": "ValueError"},
        ],
        "hidden_extra": [
            {"fn": "parse_kv", "args": ("",), "want": {}},
            {"fn": "parse_kv", "args": ("x=",), "want": {"x": ""}},
            {"fn": "parse_kv", "args": (" a = 1 ",), "want": {"a": "1"}},
            {"fn": "parse_kv", "args": ("a=1;b=2",), "want": {"a": "1", "b": "2"}},
            {"fn": "parse_kv", "args": ("a=1;;b=2",), "want": {"a": "1", "b": "2"}},
            {"fn": "parse_kv", "args": ("a=1;b",), "raises": "ValueError"},
        ],
    },
    {
        "id": "s2_29_rle",
        "title": "rle(s)",
        "prose": """`rle(s)` compresses a piece of text by reporting each run of one
repeated character as that character together with how long the run was, in
order.

The result is handed to code that puts the runs into a table and then hashes
the table, so the runs have to come back as values that cannot be changed
afterwards.""",
        "names": ["rle"],
        "withheld": ["tuple", "immutable pair", "('a', 2)"],
        "trap": "withheld: each run is a tuple, not a list",
        "solution": r"""def rle(s):
    out = []
    for c in s:
        if out and out[-1][0] == c:
            out[-1] = (c, out[-1][1] + 1)
        else:
            out.append((c, 1))
    return out
""",
        "bad_a": r"""def rle(s):
    out = []
    for c in s:
        if out and out[-1][0] == c:
            out[-1][1] += 1
        else:
            out.append([c, 1])
    return out
""",
        "bad_b": r"""def rle(s):
    out = []
    for c in s:
        if out and out[-1][0] == c:
            out[-1] = (c, out[-1][1] + 1)
        else:
            out.append((c, s.count(c)))
    return out
""",
        "bad_c": r"""def encode_runs(s):
    out = []
    for c in s:
        if out and out[-1][0] == c:
            out[-1] = (c, out[-1][1] + 1)
        else:
            out.append((c, 1))
    return out
""",
        "visible": [
            {"fn": "rle", "args": ("aab",), "want": [("a", 2), ("b", 1)]},
            {"fn": "rle", "args": ("",), "want": []},
        ],
        "hidden_extra": [
            {"fn": "rle", "args": ("a",), "want": [("a", 1)]},
            {"fn": "rle", "args": ("aaa",), "want": [("a", 3)]},
            {"fn": "rle", "args": ("abab",),
             "want": [("a", 1), ("b", 1), ("a", 1), ("b", 1)]},
            {"fn": "rle", "args": ("xxyy",), "want": [("x", 2), ("y", 2)]},
            {"fn": "rle", "args": ("  ",), "want": [(" ", 2)]},
        ],
    },
    {
        "id": "s2_30_caesar",
        "title": "caesar(s, k)",
        "prose": """`caesar(s, k)` shifts the letters of a piece of text k places along
the alphabet, wrapping round from the end back to the beginning.

The texts are ordinary sentences with punctuation and capitals in them, and
the shift comes from a spinner that the user can turn in either direction as
far as they like.""",
        "names": ["caesar"],
        "withheld": ["non-letter", "left alone", "case is kept", "negative",
                     "unchanged"],
        "trap": "withheld: anything that is not a letter is untouched and case is preserved",
        "solution": r"""def caesar(s, k):
    out = []
    for c in s:
        if "a" <= c <= "z":
            out.append(chr((ord(c) - 97 + k) % 26 + 97))
        elif "A" <= c <= "Z":
            out.append(chr((ord(c) - 65 + k) % 26 + 65))
        else:
            out.append(c)
    return "".join(out)
""",
        "bad_a": r"""def caesar(s, k):
    return "".join(chr((ord(c) + k) % 128) for c in s)
""",
        "bad_b": r"""def caesar(s, k):
    out = []
    for c in s.lower():
        if "a" <= c <= "z":
            out.append(chr((ord(c) - 97 + k) % 26 + 97))
        else:
            out.append(c)
    return "".join(out)
""",
        "bad_c": r"""def shift_letters(s, k):
    out = []
    for c in s:
        if "a" <= c <= "z":
            out.append(chr((ord(c) - 97 + k) % 26 + 97))
        elif "A" <= c <= "Z":
            out.append(chr((ord(c) - 65 + k) % 26 + 65))
        else:
            out.append(c)
    return "".join(out)
""",
        "visible": [
            {"fn": "caesar", "args": ("abc-XYZ", 1), "want": "bcd-YZA"},
            {"fn": "caesar", "args": ("abc", -1), "want": "zab"},
        ],
        "hidden_extra": [
            {"fn": "caesar", "args": ("", 5), "want": ""},
            {"fn": "caesar", "args": ("Hello, World!", 13), "want": "Uryyb, Jbeyq!"},
            {"fn": "caesar", "args": ("xyz", 3), "want": "abc"},
            {"fn": "caesar", "args": ("ABC", 0), "want": "ABC"},
            {"fn": "caesar", "args": ("a1b", 1), "want": "b1c"},
            {"fn": "caesar", "args": ("abc", 27), "want": "bcd"},
        ],
    },
    {
        "id": "s2_31_mean_by",
        "title": "mean_by(rows, field)",
        "prose": """`mean_by(rows, field)` takes a list of lookups and averages the
numbers stored under the given field, giving back a number.

The rows come from an import where not every source system fills in every
column, and the report has to render whatever came back.""",
        "names": ["mean_by"],
        "withheld": ["skip", "missing", "0.0", "KeyError", "absent"],
        "trap": "withheld: rows without the field are passed over; no usable row gives 0.0",
        "solution": r"""def mean_by(rows, field):
    vals = [r[field] for r in rows if field in r]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)
""",
        "bad_a": r"""def mean_by(rows, field):
    vals = [r.get(field, 0) for r in rows]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)
""",
        "bad_b": r"""def mean_by(rows, field):
    vals = [r[field] for r in rows]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)
""",
        "bad_c": r"""def average_by(rows, field):
    vals = [r[field] for r in rows if field in r]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)
""",
        "visible": [
            {"fn": "mean_by", "args": ([{"v": 1}, {"v": 3}, {"w": 9}], "v"),
             "want": 2.0},
            {"fn": "mean_by", "args": ([], "v"), "want": 0.0},
        ],
        "hidden_extra": [
            {"fn": "mean_by", "args": ([{"v": 2}], "v"), "want": 2.0},
            {"fn": "mean_by", "args": ([{"a": 1}], "v"), "want": 0.0},
            {"fn": "mean_by", "args": ([{"v": 1}, {"v": 2}], "v"), "want": 1.5},
            {"fn": "mean_by", "args": ([{"v": 0}], "v"), "want": 0.0},
            {"fn": "mean_by", "args": ([{"v": -1}, {"v": 1}], "v"), "want": 0.0},
        ],
    },
    {
        "id": "s2_32_sort_versions",
        "title": "sort_versions(vs)",
        "prose": """`sort_versions(vs)` puts a list of dotted version strings into
increasing order and gives back a new list.

Every string is made of parts separated by dots and every part is written with
digits only. Releases have been coming out for long enough that the parts have
run well past a single digit.""",
        "names": ["sort_versions"],
        "withheld": ["numeric", "as numbers", "lexicograph", "int(",
                     "not as text"],
        "trap": "withheld: parts compare as numbers, so 1.10 comes after 1.9",
        "solution": r"""def sort_versions(vs):
    return sorted(vs, key=lambda v: [int(p) for p in v.split(".")])
""",
        "bad_a": r"""def sort_versions(vs):
    return sorted(vs)
""",
        "bad_b": r"""def sort_versions(vs):
    return sorted(vs, key=lambda v: [int(p) for p in v.split(".")],
                  reverse=True)
""",
        "bad_c": r"""def version_sort(vs):
    return sorted(vs, key=lambda v: [int(p) for p in v.split(".")])
""",
        "visible": [
            {"fn": "sort_versions", "args": (["1.10", "1.9", "1.2"],),
             "want": ["1.2", "1.9", "1.10"]},
            {"fn": "sort_versions", "args": ([],), "want": []},
        ],
        "hidden_extra": [
            {"fn": "sort_versions", "args": (["2.0", "10.0", "1.0"],),
             "want": ["1.0", "2.0", "10.0"]},
            {"fn": "sort_versions", "args": (["1.0.1", "1.0.0"],),
             "want": ["1.0.0", "1.0.1"]},
            {"fn": "sort_versions", "args": (["3"],), "want": ["3"]},
            {"fn": "sort_versions", "args": (["0.1", "0.10", "0.2"],),
             "want": ["0.1", "0.2", "0.10"]},
            {"fn": "sort_versions", "args": (["1.1", "1.1"],),
             "want": ["1.1", "1.1"]},
        ],
    },
    {
        "id": "s2_33_is_leap",
        "title": "is_leap(y)",
        "prose": """`is_leap(y)` says whether a year in the Gregorian calendar has an
extra day in February, giving back a true or false value.

The years arrive as free text that a user typed into a form, converted to a
number by code that does no checking of its own.""",
        "names": ["is_leap"],
        "withheld": ["ValueError", "below one", "must be positive", "reject"],
        "trap": "withheld: a year that is not at least 1 is rejected with a ValueError",
        "solution": r"""def is_leap(y):
    if y < 1:
        raise ValueError("year must be at least 1")
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
""",
        "bad_a": r"""def is_leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
""",
        "bad_b": r"""def is_leap(y):
    if y < 1:
        raise ValueError("year must be at least 1")
    return y % 4 == 0
""",
        "bad_c": r"""def leap_year(y):
    if y < 1:
        raise ValueError("year must be at least 1")
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
""",
        "visible": [
            {"fn": "is_leap", "args": (1900,), "want": False},
            {"fn": "is_leap", "args": (0,), "raises": "ValueError"},
        ],
        "hidden_extra": [
            {"fn": "is_leap", "args": (2000,), "want": True},
            {"fn": "is_leap", "args": (2024,), "want": True},
            {"fn": "is_leap", "args": (2023,), "want": False},
            {"fn": "is_leap", "args": (2100,), "want": False},
            {"fn": "is_leap", "args": (-4,), "raises": "ValueError"},
            {"fn": "is_leap", "args": (4,), "want": True},
        ],
    },
    {
        "id": "s2_34_hms",
        "title": "hms(seconds)",
        "prose": """`hms(seconds)` writes a whole number of seconds as a clock-style
label with colons between the parts.

The labels sit under a progress bar for clips that are usually under a minute
but occasionally run for hours, and the bar is narrow. The number arrives as
the difference between two timestamps that are not guaranteed to be in
order.""",
        "names": ["hms"],
        "withheld": ["ValueError", "hours are left out", "omit", "two digits",
                     "00:59"],
        "trap": "withheld: hours vanish when zero, mm and ss always two digits, negative raises",
        "solution": r"""def hms(seconds):
    if seconds < 0:
        raise ValueError("seconds must not be negative")
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%02d:%02d" % (m, s)
""",
        "bad_a": r"""def hms(seconds):
    if seconds < 0:
        raise ValueError("seconds must not be negative")
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s)
""",
        "bad_b": r"""def hms(seconds):
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%02d:%02d" % (m, s)
""",
        "bad_c": r"""def format_hms(seconds):
    if seconds < 0:
        raise ValueError("seconds must not be negative")
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%02d:%02d" % (m, s)
""",
        "visible": [
            {"fn": "hms", "args": (59,), "want": "00:59"},
            {"fn": "hms", "args": (3723,), "want": "1:02:03"},
            {"fn": "hms", "args": (-1,), "raises": "ValueError"},
        ],
        "hidden_extra": [
            {"fn": "hms", "args": (0,), "want": "00:00"},
            {"fn": "hms", "args": (61,), "want": "01:01"},
            {"fn": "hms", "args": (3600,), "want": "1:00:00"},
            {"fn": "hms", "args": (86399,), "want": "23:59:59"},
            {"fn": "hms", "args": (600,), "want": "10:00"},
            {"fn": "hms", "args": (-100,), "raises": "ValueError"},
        ],
    },
    {
        "id": "s2_35_pluralize",
        "title": "pluralize(word, n)",
        "prose": """`pluralize(word, n)` describes n of something in English and gives
back the phrase as text, putting the word into the form that goes with that
number.

The phrases end up in notification messages such as the one telling a user how
much of their inbox is waiting. The nouns are ordinary English ones, including
the kind whose plural needs an extra syllable.""",
        "names": ["pluralize"],
        "withheld": ["2 cats", "the count is part", "number in front",
                     "boxes", "sibilant"],
        "trap": "withheld: the count is part of the answer; sibilant endings take es",
        "solution": r"""def pluralize(word, n):
    if n == 1:
        return "1 %s" % word
    if word.endswith(("s", "x", "ch", "sh")):
        return "%d %ses" % (n, word)
    return "%d %ss" % (n, word)
""",
        "bad_a": r"""def pluralize(word, n):
    if n == 1:
        return word
    if word.endswith(("s", "x", "ch", "sh")):
        return word + "es"
    return word + "s"
""",
        "bad_b": r"""def pluralize(word, n):
    if n == 1:
        return "1 %s" % word
    return "%d %ss" % (n, word)
""",
        "bad_c": r"""def plural(word, n):
    if n == 1:
        return "1 %s" % word
    if word.endswith(("s", "x", "ch", "sh")):
        return "%d %ses" % (n, word)
    return "%d %ss" % (n, word)
""",
        "visible": [
            {"fn": "pluralize", "args": ("cat", 2), "want": "2 cats"},
            {"fn": "pluralize", "args": ("box", 3), "want": "3 boxes"},
        ],
        "hidden_extra": [
            {"fn": "pluralize", "args": ("cat", 1), "want": "1 cat"},
            {"fn": "pluralize", "args": ("cat", 0), "want": "0 cats"},
            {"fn": "pluralize", "args": ("bus", 2), "want": "2 buses"},
            {"fn": "pluralize", "args": ("dish", 2), "want": "2 dishes"},
            {"fn": "pluralize", "args": ("match", 5), "want": "5 matches"},
            {"fn": "pluralize", "args": ("dog", 10), "want": "10 dogs"},
        ],
    },
    {
        "id": "s2_36_mask",
        "title": "mask(s, keep)",
        "prose": """`mask(s, keep)` hides most of a piece of text, leaving `keep` of its
characters readable and replacing every other character with one single mask
character.

It is used on card numbers and account references in a support console, where
agents read the part back to the customer to confirm which card they are
looking at. `keep` comes from a policy file and is sometimes larger than the
text itself.""",
        "names": ["mask"],
        "withheld": ["last", "at the end", "asterisk", "*", "untouched"],
        "trap": "withheld: the readable characters are the ones at the end; the mask character is *",
        "solution": r"""def mask(s, keep):
    if keep >= len(s):
        return s
    return "*" * (len(s) - keep) + s[len(s) - keep:]
""",
        "bad_a": r"""def mask(s, keep):
    if keep >= len(s):
        return s
    return s[:keep] + "*" * (len(s) - keep)
""",
        "bad_b": r"""def mask(s, keep):
    if keep >= len(s):
        return s
    return "x" * (len(s) - keep) + s[len(s) - keep:]
""",
        "bad_c": r"""def mask_tail(s, keep):
    if keep >= len(s):
        return s
    return "*" * (len(s) - keep) + s[len(s) - keep:]
""",
        "visible": [
            {"fn": "mask", "args": ("1234567890", 4), "want": "******7890"},
            {"fn": "mask", "args": ("abc", 5), "want": "abc"},
        ],
        "hidden_extra": [
            {"fn": "mask", "args": ("", 3), "want": ""},
            {"fn": "mask", "args": ("abcd", 0), "want": "****"},
            {"fn": "mask", "args": ("abcd", 4), "want": "abcd"},
            {"fn": "mask", "args": ("abcdef", 2), "want": "****ef"},
            {"fn": "mask", "args": ("xy", 1), "want": "*y"},
            {"fn": "mask", "args": ("abc", 3), "want": "abc"},
        ],
    },
    {
        "id": "s2_37_column",
        "title": "column(rows, field)",
        "prose": """`column(rows, field)` pulls one field out of every row of a list of
lookups, in order, and gives back a list.

The result is written out as one column of a table whose other columns come
from the same rows, so the rows and the entries have to stay lined up.""",
        "names": ["column"],
        "withheld": ["None", "skip", "placeholder", "KeyError"],
        "trap": "withheld: a row without the field contributes None rather than being skipped",
        "solution": r"""def column(rows, field):
    return [r.get(field) for r in rows]
""",
        "bad_a": r"""def column(rows, field):
    return [r[field] for r in rows if field in r]
""",
        "bad_b": r"""def column(rows, field):
    return [r[field] for r in rows]
""",
        "bad_c": r"""def pluck(rows, field):
    return [r.get(field) for r in rows]
""",
        "visible": [
            {"fn": "column", "args": ([{"a": 1}, {"b": 2}], "a"), "want": [1, None]},
            {"fn": "column", "args": ([], "a"), "want": []},
        ],
        "hidden_extra": [
            {"fn": "column", "args": ([{"a": 1}], "a"), "want": [1]},
            {"fn": "column", "args": ([{}, {}], "a"), "want": [None, None]},
            {"fn": "column", "args": ([{"a": None}], "a"), "want": [None]},
            {"fn": "column", "args": ([{"a": 1}, {"a": 2}], "a"), "want": [1, 2]},
            {"fn": "column", "args": ([{"b": 1}], "a"), "want": [None]},
        ],
    },
    {
        "id": "s2_38_in_range",
        "title": "in_range(x, lo, hi)",
        "prose": """`in_range(x, lo, hi)` says whether x falls inside the window
described by the two bounds, giving back a true or false value.

The windows are the buckets of a histogram, laid end to end so that the whole
number line is covered and every value lands in exactly one bucket.""",
        "names": ["in_range"],
        "withheld": ["inclusive", "exclusive", "half-open", "upper bound is not"],
        "trap": "withheld: the lower bound counts, the upper bound does not",
        "solution": r"""def in_range(x, lo, hi):
    return lo <= x < hi
""",
        "bad_a": r"""def in_range(x, lo, hi):
    return lo <= x <= hi
""",
        "bad_b": r"""def in_range(x, lo, hi):
    return lo < x < hi
""",
        "bad_c": r"""def within(x, lo, hi):
    return lo <= x < hi
""",
        "visible": [
            {"fn": "in_range", "args": (1, 1, 5), "want": True},
            {"fn": "in_range", "args": (5, 1, 5), "want": False},
        ],
        "hidden_extra": [
            {"fn": "in_range", "args": (0, 1, 5), "want": False},
            {"fn": "in_range", "args": (4, 1, 5), "want": True},
            {"fn": "in_range", "args": (1.0, 1, 5), "want": True},
            {"fn": "in_range", "args": (-1, -5, 0), "want": True},
            {"fn": "in_range", "args": (0, -5, 0), "want": False},
            {"fn": "in_range", "args": (3, 3, 4), "want": True},
        ],
    },
    {
        "id": "s2_39_strip_comments",
        "title": "strip_comments(text)",
        "prose": """`strip_comments(text)` removes everything from a hash character to
the end of the line it sits on, and gives back the remaining text.

The text is a configuration file, and the tool that reads the result reports
problems by line number, so those numbers have to keep pointing at the same
places. Nobody wants the diff to show whitespace that used to be in front of
a comment.""",
        "names": ["strip_comments"],
        "withheld": ["rstrip", "trailing space", "line is kept", "blank line"],
        "trap": "withheld: the line stays even when nothing is left, and trailing spaces go",
        "solution": r"""def strip_comments(text):
    out = []
    for line in text.split("\n"):
        out.append(line.split("#", 1)[0].rstrip())
    return "\n".join(out)
""",
        "bad_a": r"""def strip_comments(text):
    out = []
    for line in text.split("\n"):
        head = line.split("#", 1)[0].rstrip()
        if head:
            out.append(head)
    return "\n".join(out)
""",
        "bad_b": r"""def strip_comments(text):
    out = []
    for line in text.split("\n"):
        out.append(line.split("#", 1)[0])
    return "\n".join(out)
""",
        "bad_c": r"""def remove_comments(text):
    out = []
    for line in text.split("\n"):
        out.append(line.split("#", 1)[0].rstrip())
    return "\n".join(out)
""",
        "visible": [
            {"fn": "strip_comments", "args": ("a = 1  # set\n# all\nb",),
             "want": "a = 1\n\nb"},
            {"fn": "strip_comments", "args": ("",), "want": ""},
        ],
        "hidden_extra": [
            {"fn": "strip_comments", "args": ("#x",), "want": ""},
            {"fn": "strip_comments", "args": ("a",), "want": "a"},
            {"fn": "strip_comments", "args": ("a#b",), "want": "a"},
            {"fn": "strip_comments", "args": ("a \n b ",), "want": "a\n b"},
            {"fn": "strip_comments", "args": ("x\n#y\nz",), "want": "x\n\nz"},
            {"fn": "strip_comments", "args": ("  # c",), "want": ""},
        ],
    },
    {
        "id": "s2_40_first_match",
        "title": "first_match(words, prefix)",
        "prose": """`first_match(words, prefix)` finds the first word in the list that
starts with the given prefix.

It backs the type-ahead box of a search field: the list is what the index
holds, spelled the way the documents spell it, and the prefix is whatever the
user has typed so far, spelled the way a person in a hurry types.""",
        "names": ["first_match"],
        "withheld": ["None", "ignoring case", "case-insensitive", "raise"],
        "trap": "withheld: matching ignores case; nothing matching gives None rather than an error",
        "solution": r"""def first_match(words, prefix):
    p = prefix.lower()
    for w in words:
        if w.lower().startswith(p):
            return w
    return None
""",
        "bad_a": r"""def first_match(words, prefix):
    for w in words:
        if w.startswith(prefix):
            return w
    return None
""",
        "bad_b": r"""def first_match(words, prefix):
    p = prefix.lower()
    for w in words:
        if w.lower().startswith(p):
            return w
    raise ValueError("no match")
""",
        "bad_c": r"""def find_first(words, prefix):
    p = prefix.lower()
    for w in words:
        if w.lower().startswith(p):
            return w
    return None
""",
        "visible": [
            {"fn": "first_match", "args": (["Apple", "ant"], "a"), "want": "Apple"},
            {"fn": "first_match", "args": (["x"], "z"), "want": None},
        ],
        "hidden_extra": [
            {"fn": "first_match", "args": ([], "a"), "want": None},
            {"fn": "first_match", "args": (["abc"], ""), "want": "abc"},
            {"fn": "first_match", "args": (["B", "b"], "B"), "want": "B"},
            {"fn": "first_match", "args": (["cat", "Car"], "ca"), "want": "cat"},
            {"fn": "first_match", "args": (["Zed"], "z"), "want": "Zed"},
            {"fn": "first_match", "args": (["a"], "ab"), "want": None},
        ],
    },
]

#: S2 的 `TASK_explicit.md` 插入塊（Fable 2026-09-19 重裁的增補）。
#:
#: 第四條臂 `PC`（正控制，每題只跑 1 次、不重試）跑同一題，但 `TASK.md` 換成
#: `TASK_explicit.md`——S2 這一層被 withhold 的是**那一到兩個行為細節**
#: （dict 的 key 集合／排序／空輸入／四捨五入／例外型別），這裡把它們寫明。
#: 每一條都對應這一題 `withheld` 裡的東西，**不多講別的**。
#:
#: PC 是 RP 臂的天花板：沒有它，「RP 沒提升」分不開「看得到回饋但不照做」與
#: 「講明白了也寫不出來」。事前預測 PC 第 1 次可見通過 ≥ 0.8；
#: PC < 0.5 ⇒ 該層判 `CEILING_TOO_LOW`。
#:
#: ⚠ 這個塊是**唯一**允許出現在兩份 TASK 之間的差（量具第 6 項是可執行擋門）。
EXPLICIT = {
    "s2_01_mean": [
        "the average is rounded to three decimal places;",
        "a list with no numbers in it gives back 0.0 rather than raising.",
    ],
    "s2_02_tally": [
        "the keys are lower-cased, so two spellings of one word share a count.",
    ],
    "s2_03_top_n": [
        "names carrying the same count come out in alphabetical order.",
    ],
    "s2_04_split_csv": [
        "each field has the spaces around it removed;",
        "a line with nothing in it gives back [], not a list holding one "
        "empty string.",
    ],
    "s2_05_clamp": [
        "a lo above hi raises ValueError.",
    ],
    "s2_06_pct": [
        "the answer is rounded to one decimal place;",
        "a whole of 0 gives back 0.0 rather than raising.",
    ],
    "s2_07_median": [
        "an even count gives the value halfway between the two middle ones;",
        "a list with no numbers in it raises ValueError.",
    ],
    "s2_08_dedupe": [
        "the comparison ignores case, and the spelling kept is the first one "
        "seen.",
    ],
    "s2_09_chunks": [
        "an n that is not positive raises ValueError.",
    ],
    "s2_10_wrap": [
        "a word longer than width is never cut: it gets a piece to itself.",
    ],
    "s2_11_titleize": [
        "a word already written entirely in upper case is left exactly as it is.",
    ],
    "s2_12_slugify": [
        "a run of hyphens collapses into a single hyphen;",
        "hyphens at the start and at the end are removed.",
    ],
    "s2_13_parse_int": [
        "something that is not text at all raises TypeError, not ValueError.",
    ],
    "s2_14_range_sum": [
        "both bounds are counted in;",
        "a first bound above the second gives 0.",
    ],
    "s2_15_normalize": [
        "a separator at the very end is removed, unless the whole path is that "
        "separator.",
    ],
    "s2_16_size_label": [
        "the step between units is 1024;",
        "above B the number takes one decimal place;",
        "there is a single space between the number and the unit.",
    ],
    "s2_17_ordinal": [
        "11, 12 and 13 take th whatever their last digit is.",
    ],
    "s2_18_is_palindrome": [
        "only letters and digits are compared, and case is ignored.",
    ],
    "s2_19_group_by_first": [
        "the key is the lower-cased first letter;",
        "a word with nothing in it is dropped.",
    ],
    "s2_20_merge": [
        "where both hold the same key, the value from the second one is kept.",
    ],
    "s2_21_flatten": [
        "only one level is undone: a list inside an inner list stays a list.",
    ],
    "s2_22_only_in_first": [
        "the order of the first list is kept, and so is every repeat in it.",
    ],
    "s2_23_running_total": [
        "the answer is the same length as the input, and each entry includes "
        "the reading at that position.",
    ],
    "s2_24_round_money": [
        "a half rounds away from zero, not to the nearest even digit;",
        "the answer keeps two decimal places.",
    ],
    "s2_25_truncate": [
        "the three dots count towards n, so the answer is never longer than n.",
    ],
    "s2_26_initials": [
        "each initial is upper case and is followed by a full stop;",
        "a part joined by a hyphen contributes one initial per half.",
    ],
    "s2_27_count_lines": [
        "a line break at the very end does not add a line;",
        "text with nothing in it has 0 lines.",
    ],
    "s2_28_parse_kv": [
        "where a name appears more than once, the later one wins;",
        "a pair with no equals sign in it raises ValueError.",
    ],
    "s2_29_rle": [
        "each run comes back as a tuple, not as a list.",
    ],
    "s2_30_caesar": [
        "anything that is not a letter is left exactly as it is, and upper "
        "case stays upper case.",
    ],
    "s2_31_mean_by": [
        "rows that do not carry the field are passed over;",
        "when no row carries it, the answer is 0.0.",
    ],
    "s2_32_sort_versions": [
        "each dotted part compares as a number, so 1.10 comes after 1.9.",
    ],
    "s2_33_is_leap": [
        "a year below 1 raises ValueError.",
    ],
    "s2_34_hms": [
        "the hours part is left out when it is zero;",
        "minutes and seconds always take two digits;",
        "a negative input raises ValueError.",
    ],
    "s2_35_pluralize": [
        "the count itself is part of the answer, in front of the word;",
        "a word ending in s, x, ch or sh takes es rather than s.",
    ],
    "s2_36_mask": [
        "the readable characters are the ones at the end;",
        "the mask character is an asterisk;",
        "a keep at least as large as the text leaves it untouched.",
    ],
    "s2_37_column": [
        "a row that does not carry the field contributes None; it is not "
        "skipped.",
    ],
    "s2_38_in_range": [
        "the lower bound counts as inside; the upper bound does not.",
    ],
    "s2_39_strip_comments": [
        "a line whose whole content was a comment stays, as a line with "
        "nothing in it;",
        "trailing spaces are removed from every line.",
    ],
    "s2_40_first_match": [
        "matching ignores case;",
        "when nothing matches, the answer is None rather than an error.",
    ],
}
