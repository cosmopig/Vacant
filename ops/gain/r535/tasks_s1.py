# -*- coding: utf-8 -*-
"""R535 S1 層的**題目原始資料**（`介面未給`，n=50）。

這支在架構裡承重什麼（Fable 2026-09-19 裁決 R535「題庫與量具」）
--------------------------------------------------------------
S1 是**管道的正控制**：`TASK.md` 只用白話講功能，**不給函式名／簽名／回傳形狀**；
可見驗收套件用 2–3 條 `check_*` 把名字與形狀釘死。第 1 次嘗試幾乎一定失敗
（事前預期可見失敗率 ≥ 0.8），而失敗回饋
（`ImportError: cannot import name 'mul' from 'solution'`）**充分決定修法**——
任何會消費回饋的 agent 都救得回來。救不回來就不是題目難，是管道沒把回饋送到。

窗口是**設計進去的**，不是靠運氣：每一題至少兩個獨立的陷阱，從下面三族取：

  · 名字族——白話描述會誘出一個**自然但錯**的名字（"multiply" ⇒ `multiply`，
    要的是 `mul`）；
  · 形狀族——白話說「一起給回來」，要的是特定 key 的 dict 而不是 tuple；
  · 參數族——引數順序／個數在白話裡只被暗示。

⚠ **題庫是資料不是程式**（R452）。本檔是**來源資料**，
`ops/gain/r535/build_bank.py` 把它確定性地渲染成 `ops/gain/r535/bank/` 底下的
字面檔案，並以 sha256 凍進 `ops/gain/r535/bank_manifest.json`。
渲染器只會渲染自己讀得懂的三個欄位（`fn`／`args`／`want|raises`），
有狀態、雜湊黑名單、擬態三種攻擊在這個資料形狀裡**不可表達**（R452 §同）。

⚠ **出題紀律**（裁決逐條）：不用 gemma-12b 出題（那是被測的模型）；
不抄 LCB／r530／codebench 的題面；題目真的微型（參考解 1–12 行，
一次嘗試 3 通 wire、秒級牆鐘），**不寫成 LeetCode**。

欄位
----
``id``            題目 id（＝ `bank/` 底下的目錄名）
``title``         一行標題（只進 `meta.json`，不進工作區）
``prose``         `TASK.md` 正文。**不准出現 `names` 裡的任何一個名字**
                  （量具第 5 項會擋）。
``names``         可見／隱藏套件會 import 的函式名，**就是被 withhold 的東西**。
``trap``          這一題把窗口設計在哪裡（只進 `meta.json`）。
``solution``      參考解原始碼（`reference/solution.py`）。
``bad_a``         **名字對、行為錯**的壞樁（裁決指定）。
``bad_b``         第三個壞樁，多半是**回傳形狀錯**。
``bad_c``         **名字錯**的壞樁（裁決指定）——量具第 3 項就量它的回饋。
``visible``       2–3 條可見 case。
``hidden_extra``  隱藏套件在可見之外多出來的 4–8 條（隱藏＝可見 ∪ 這些）。

case 的形狀：``{"fn": 名字, "args": tuple, "want": 字面值}``，
或 ``{"fn": 名字, "args": tuple, "raises": "ValueError"}``。
"""

TASKS = [
    {
        "id": "s1_01_addmul",
        "title": "two arithmetic helpers",
        "prose": """A small numeric helper module is needed.

Two operations:

- given two numbers, give back their sum;
- given two numbers, give back the result of multiplying them together.

Each one takes the two numbers as its two positional arguments and gives
back a single number.""",
        "names": ["add", "mul"],
        "trap": "name: the prose says 'sum' and 'multiplying', the suite wants add/mul",
        "solution": r"""def add(a, b):
    return a + b


def mul(a, b):
    return a * b
""",
        "bad_a": r"""def add(a, b):
    return a + b


def mul(a, b):
    return a + b
""",
        "bad_b": r"""def add(a, b):
    return str(a + b)


def mul(a, b):
    return a * b
""",
        "bad_c": r"""def add(a, b):
    return a + b


def multiply(a, b):
    return a * b
""",
        "visible": [
            {"fn": "add", "args": (2, 3), "want": 5},
            {"fn": "mul", "args": (3, 4), "want": 12},
        ],
        "hidden_extra": [
            {"fn": "add", "args": (-1, 1), "want": 0},
            {"fn": "add", "args": (0.5, 0.25), "want": 0.75},
            {"fn": "mul", "args": (0, 7), "want": 0},
            {"fn": "mul", "args": (-2, 3), "want": -6},
            {"fn": "mul", "args": (1.5, 2), "want": 3.0},
        ],
    },
    {
        "id": "s1_02_span",
        "title": "both ends of a list of numbers",
        "prose": """Given a list of numbers, report the two ends of it at once: the
smallest value in the list and the largest value in the list, handed back
together in one object so that a caller does not have to walk the list twice.

The list handed in is never without entries.""",
        "names": ["span"],
        "trap": "name + return shape (dict with keys lo/hi, not a tuple)",
        "solution": r"""def span(xs):
    return {"lo": min(xs), "hi": max(xs)}
""",
        "bad_a": r"""def span(xs):
    return {"lo": max(xs), "hi": min(xs)}
""",
        "bad_b": r"""def span(xs):
    return (min(xs), max(xs))
""",
        "bad_c": r"""def minmax(xs):
    return {"lo": min(xs), "hi": max(xs)}
""",
        "visible": [
            {"fn": "span", "args": ([3, 1, 4],), "want": {"lo": 1, "hi": 4}},
            {"fn": "span", "args": ([7],), "want": {"lo": 7, "hi": 7}},
        ],
        "hidden_extra": [
            {"fn": "span", "args": ([-5, 0, 5],), "want": {"lo": -5, "hi": 5}},
            {"fn": "span", "args": ([2, 2, 2],), "want": {"lo": 2, "hi": 2}},
            {"fn": "span", "args": ([1.5, -1.5],), "want": {"lo": -1.5, "hi": 1.5}},
            {"fn": "span", "args": ([10, 9, 8, 7],), "want": {"lo": 7, "hi": 10}},
        ],
    },
    {
        "id": "s1_03_nwords",
        "title": "how many words a line holds",
        "prose": """Report how many words a line of text contains.

Words are separated by runs of whitespace. Whitespace at the start or the end
of the line does not create extra words, and a line made of nothing but
whitespace contains none at all.""",
        "names": ["n_words"],
        "trap": "name: 'count the words' pulls towards count_words / word_count",
        "solution": r"""def n_words(line):
    return len(line.split())
""",
        "bad_a": r"""def n_words(line):
    return len(line.split(" "))
""",
        "bad_b": r"""def n_words(line):
    return line.split()
""",
        "bad_c": r"""def count_words(line):
    return len(line.split())
""",
        "visible": [
            {"fn": "n_words", "args": ("hello world",), "want": 2},
            {"fn": "n_words", "args": ("  a  b  c ",), "want": 3},
        ],
        "hidden_extra": [
            {"fn": "n_words", "args": ("",), "want": 0},
            {"fn": "n_words", "args": ("   ",), "want": 0},
            {"fn": "n_words", "args": ("one",), "want": 1},
            {"fn": "n_words", "args": ("a\tb\nc",), "want": 3},
            {"fn": "n_words", "args": ("  spaced   out  ",), "want": 2},
        ],
    },
    {
        "id": "s1_04_toc",
        "title": "Fahrenheit onto the Celsius scale",
        "prose": """Convert a temperature given on the Fahrenheit scale onto the Celsius
scale.

The answer is a number rounded to one decimal place.""",
        "names": ["to_c"],
        "trap": "name (fahrenheit_to_celsius is the natural guess) + the rounding",
        "solution": r"""def to_c(f):
    return round((f - 32) * 5 / 9, 1)
""",
        "bad_a": r"""def to_c(f):
    return (f - 32) * 5 / 9
""",
        "bad_b": r"""def to_c(f):
    return "%.1f" % ((f - 32) * 5 / 9)
""",
        "bad_c": r"""def fahrenheit_to_celsius(f):
    return round((f - 32) * 5 / 9, 1)
""",
        "visible": [
            {"fn": "to_c", "args": (32,), "want": 0.0},
            {"fn": "to_c", "args": (0,), "want": -17.8},
        ],
        "hidden_extra": [
            {"fn": "to_c", "args": (212,), "want": 100.0},
            {"fn": "to_c", "args": (-40,), "want": -40.0},
            {"fn": "to_c", "args": (98.6,), "want": 37.0},
            {"fn": "to_c", "args": (100,), "want": 37.8},
            {"fn": "to_c", "args": (72,), "want": 22.2},
        ],
    },
    {
        "id": "s1_05_initials",
        "title": "the initial of each part of a name",
        "prose": """Take a person's full name and pull out the initial of each part of
it. The parts of a name are separated by spaces.

Give them back as a sequence of single upper-case characters, one per
part, in the order the parts appear.""",
        "names": ["initials"],
        "trap": "return shape: 'a sequence of characters' is a list here, not a string",
        "solution": r"""def initials(full_name):
    return [p[0].upper() for p in full_name.split()]
""",
        "bad_a": r"""def initials(full_name):
    return [p[0] for p in full_name.split()]
""",
        "bad_b": r"""def initials(full_name):
    return "".join(p[0].upper() for p in full_name.split())
""",
        "bad_c": r"""def get_initials(full_name):
    return [p[0].upper() for p in full_name.split()]
""",
        "visible": [
            {"fn": "initials", "args": ("ada lovelace",), "want": ["A", "L"]},
            {"fn": "initials", "args": ("Grace Brewster Hopper",),
             "want": ["G", "B", "H"]},
        ],
        "hidden_extra": [
            {"fn": "initials", "args": ("x",), "want": ["X"]},
            {"fn": "initials", "args": ("  jean  luc  picard ",),
             "want": ["J", "L", "P"]},
            {"fn": "initials", "args": ("MARIE curie",), "want": ["M", "C"]},
            {"fn": "initials", "args": ("a b c d",), "want": ["A", "B", "C", "D"]},
        ],
    },
    {
        "id": "s1_06_parity",
        "title": "separate a list by divisibility by two",
        "prose": """Split a list of whole numbers into the ones that divide by two and
the ones that do not.

Each group keeps the order its members appeared in, and both groups come back
together in one object.""",
        "names": ["split_parity"],
        "trap": "name + return shape (dict with keys even/odd, not a pair)",
        "solution": r"""def split_parity(xs):
    return {"even": [x for x in xs if x % 2 == 0],
            "odd": [x for x in xs if x % 2 != 0]}
""",
        "bad_a": r"""def split_parity(xs):
    return {"even": [x for x in xs if x % 2 != 0],
            "odd": [x for x in xs if x % 2 == 0]}
""",
        "bad_b": r"""def split_parity(xs):
    return ([x for x in xs if x % 2 == 0], [x for x in xs if x % 2 != 0])
""",
        "bad_c": r"""def partition_parity(xs):
    return {"even": [x for x in xs if x % 2 == 0],
            "odd": [x for x in xs if x % 2 != 0]}
""",
        "visible": [
            {"fn": "split_parity", "args": ([1, 2, 3, 4],),
             "want": {"even": [2, 4], "odd": [1, 3]}},
            {"fn": "split_parity", "args": ([],),
             "want": {"even": [], "odd": []}},
        ],
        "hidden_extra": [
            {"fn": "split_parity", "args": ([2, 4, 6],),
             "want": {"even": [2, 4, 6], "odd": []}},
            {"fn": "split_parity", "args": ([-3, -2],),
             "want": {"even": [-2], "odd": [-3]}},
            {"fn": "split_parity", "args": ([0],),
             "want": {"even": [0], "odd": []}},
            {"fn": "split_parity", "args": ([5, 5, 5],),
             "want": {"even": [], "odd": [5, 5, 5]}},
        ],
    },
    {
        "id": "s1_07_flipwords",
        "title": "words of a sentence in the opposite order",
        "prose": """Take a sentence and give it back with its words in the opposite
order.

Words are separated by whitespace on the way in, and by a single space on the
way out.""",
        "names": ["flip_words"],
        "trap": "name (reverse_words is the natural guess)",
        "solution": r"""def flip_words(s):
    return " ".join(reversed(s.split()))
""",
        "bad_a": r"""def flip_words(s):
    return s[::-1]
""",
        "bad_b": r"""def flip_words(s):
    return list(reversed(s.split()))
""",
        "bad_c": r"""def reverse_words(s):
    return " ".join(reversed(s.split()))
""",
        "visible": [
            {"fn": "flip_words", "args": ("one two three",), "want": "three two one"},
            {"fn": "flip_words", "args": ("solo",), "want": "solo"},
        ],
        "hidden_extra": [
            {"fn": "flip_words", "args": ("",), "want": ""},
            {"fn": "flip_words", "args": ("a b",), "want": "b a"},
            {"fn": "flip_words", "args": ("the quick brown fox",),
             "want": "fox brown quick the"},
            {"fn": "flip_words", "args": ("  padded   words  ",),
             "want": "words padded"},
        ],
    },
    {
        "id": "s1_08_nvowels",
        "title": "count the vowels in a piece of text",
        "prose": """Count the vowels in a piece of text.

The five English vowel letters count, in either case. Every other character
does not, and that includes the letter y.""",
        "names": ["n_vowels"],
        "trap": "name (count_vowels is the natural guess)",
        "solution": r"""def n_vowels(s):
    return sum(1 for c in s.lower() if c in "aeiou")
""",
        "bad_a": r"""def n_vowels(s):
    return sum(1 for c in s if c in "aeiou")
""",
        "bad_b": r"""def n_vowels(s):
    return sum(1 for c in s.lower() if c in "aeiouy")
""",
        "bad_c": r"""def count_vowels(s):
    return sum(1 for c in s.lower() if c in "aeiou")
""",
        "visible": [
            {"fn": "n_vowels", "args": ("Education",), "want": 5},
            {"fn": "n_vowels", "args": ("rhythm",), "want": 0},
        ],
        "hidden_extra": [
            {"fn": "n_vowels", "args": ("",), "want": 0},
            {"fn": "n_vowels", "args": ("AEIOU",), "want": 5},
            {"fn": "n_vowels", "args": ("xyz",), "want": 0},
            {"fn": "n_vowels", "args": ("Banana",), "want": 3},
            {"fn": "n_vowels", "args": ("Queue",), "want": 4},
        ],
    },
    {
        "id": "s1_09_pin",
        "title": "keep a value inside a window",
        "prose": """Keep a value inside a permitted window.

Given a value and the two edges of the window, give back the value itself when
it already sits inside the window, and otherwise give back whichever edge it
has passed.

The value is the first argument, then the lower edge, then the upper edge.""",
        "names": ["pin"],
        "trap": "name (clamp is the natural guess)",
        "solution": r"""def pin(x, low, high):
    if x < low:
        return low
    if x > high:
        return high
    return x
""",
        "bad_a": r"""def pin(x, low, high):
    if x < low:
        return high
    if x > high:
        return low
    return x
""",
        "bad_b": r"""def pin(x, low, high):
    if low <= x <= high:
        return None
    return low if x < low else high
""",
        "bad_c": r"""def clamp(x, low, high):
    if x < low:
        return low
    if x > high:
        return high
    return x
""",
        "visible": [
            {"fn": "pin", "args": (5, 1, 10), "want": 5},
            {"fn": "pin", "args": (-3, 0, 10), "want": 0},
        ],
        "hidden_extra": [
            {"fn": "pin", "args": (99, 0, 10), "want": 10},
            {"fn": "pin", "args": (0, 0, 10), "want": 0},
            {"fn": "pin", "args": (10, 0, 10), "want": 10},
            {"fn": "pin", "args": (2.5, 0, 1), "want": 1},
            {"fn": "pin", "args": (-1, -5, -2), "want": -2},
        ],
    },
    {
        "id": "s1_10_uniq",
        "title": "drop repeats, keep first appearances",
        "prose": """Remove repeats from a list, keeping the first time each value was
seen and the order those first appearances came in.""",
        "names": ["uniq"],
        "trap": "name (dedupe / unique are the natural guesses)",
        "solution": r"""def uniq(xs):
    out = []
    for x in xs:
        if x not in out:
            out.append(x)
    return out
""",
        "bad_a": r"""def uniq(xs):
    return sorted(set(xs))
""",
        "bad_b": r"""def uniq(xs):
    out = []
    for x in xs:
        if x in out:
            out.remove(x)
        out.append(x)
    return out
""",
        "bad_c": r"""def dedupe(xs):
    out = []
    for x in xs:
        if x not in out:
            out.append(x)
    return out
""",
        "visible": [
            {"fn": "uniq", "args": ([3, 1, 3, 2, 1],), "want": [3, 1, 2]},
            {"fn": "uniq", "args": ([],), "want": []},
        ],
        "hidden_extra": [
            {"fn": "uniq", "args": ([1, 1, 1],), "want": [1]},
            {"fn": "uniq", "args": (["b", "a", "b"],), "want": ["b", "a"]},
            {"fn": "uniq", "args": ([2, 3, 2, 4, 3],), "want": [2, 3, 4]},
            {"fn": "uniq", "args": ([1],), "want": [1]},
            {"fn": "uniq", "args": (["x"],), "want": ["x"]},
        ],
    },
    {
        "id": "s1_11_caps",
        "title": "first letter of every word up, rest down",
        "prose": """Take a phrase and give it back with the first letter of every word
in upper case and every other letter of that word in lower case.

Words are separated by single spaces, and only a space starts a new word --
an apostrophe or a hyphen inside a word does not.""",
        "names": ["caps"],
        "trap": "name (title_case) + str.title() is wrong on apostrophes",
        "solution": r"""def caps(s):
    return " ".join(w[:1].upper() + w[1:].lower() for w in s.split(" "))
""",
        "bad_a": r"""def caps(s):
    return s.title()
""",
        "bad_b": r"""def caps(s):
    return s.upper()
""",
        "bad_c": r"""def title_case(s):
    return " ".join(w[:1].upper() + w[1:].lower() for w in s.split(" "))
""",
        "visible": [
            {"fn": "caps", "args": ("hello world",), "want": "Hello World"},
            {"fn": "caps", "args": ("mcADAM o'neil",), "want": "Mcadam O'neil"},
        ],
        "hidden_extra": [
            {"fn": "caps", "args": ("",), "want": ""},
            {"fn": "caps", "args": ("a",), "want": "A"},
            {"fn": "caps", "args": ("ALL CAPS HERE",), "want": "All Caps Here"},
            {"fn": "caps", "args": ("mixed CaSe words",), "want": "Mixed Case Words"},
            {"fn": "caps", "args": ("x y z",), "want": "X Y Z"},
        ],
    },
    {
        "id": "s1_12_hms",
        "title": "seconds as a clock-style label",
        "prose": """Turn a whole number of seconds into a clock-style label made of
hours, minutes and seconds with colons between them.

The hours are always shown and take as many digits as they need. The minutes
and the seconds always take exactly two digits each.""",
        "names": ["hms"],
        "trap": "name (format_duration) + hours must not be zero-padded",
        "solution": r"""def hms(total_seconds):
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s)
""",
        "bad_a": r"""def hms(total_seconds):
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return "%02d:%02d:%02d" % (h, m, s)
""",
        "bad_b": r"""def hms(total_seconds):
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return (h, m, s)
""",
        "bad_c": r"""def format_duration(total_seconds):
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s)
""",
        "visible": [
            {"fn": "hms", "args": (3723,), "want": "1:02:03"},
            {"fn": "hms", "args": (59,), "want": "0:00:59"},
        ],
        "hidden_extra": [
            {"fn": "hms", "args": (0,), "want": "0:00:00"},
            {"fn": "hms", "args": (3600,), "want": "1:00:00"},
            {"fn": "hms", "args": (86399,), "want": "23:59:59"},
            {"fn": "hms", "args": (61,), "want": "0:01:01"},
            {"fn": "hms", "args": (7322,), "want": "2:02:02"},
        ],
    },
    {
        "id": "s1_13_mean",
        "title": "arithmetic average, two decimal places",
        "prose": """Work out the arithmetic average of a list of numbers.

The answer is a number rounded to two decimal places. The list handed in is
never without entries.""",
        "names": ["mean"],
        "trap": "name (average / avg) + the rounding",
        "solution": r"""def mean(xs):
    return round(sum(xs) / len(xs), 2)
""",
        "bad_a": r"""def mean(xs):
    return sum(xs) / len(xs)
""",
        "bad_b": r"""def mean(xs):
    return sum(xs) // len(xs)
""",
        "bad_c": r"""def average(xs):
    return round(sum(xs) / len(xs), 2)
""",
        "visible": [
            {"fn": "mean", "args": ([1, 2, 4],), "want": 2.33},
            {"fn": "mean", "args": ([10],), "want": 10.0},
        ],
        "hidden_extra": [
            {"fn": "mean", "args": ([1, 2, 3],), "want": 2.0},
            {"fn": "mean", "args": ([0, 0],), "want": 0.0},
            {"fn": "mean", "args": ([-1, 1],), "want": 0.0},
            {"fn": "mean", "args": ([1, 1, 1, 2],), "want": 1.25},
            {"fn": "mean", "args": ([2, 3],), "want": 2.5},
            {"fn": "mean", "args": ([1, 2, 2],), "want": 1.67},
        ],
    },
    {
        "id": "s1_14_mid",
        "title": "the middle value once ordered",
        "prose": """Find the middle value of a list of numbers once they have been put
in order.

When the count is even there are two middle values, and the answer is halfway
between them. The answer is a number. The list handed in is never without
entries.""",
        "names": ["mid"],
        "trap": "name (median is the natural guess)",
        "solution": r"""def mid(xs):
    ys = sorted(xs)
    n = len(ys)
    if n % 2:
        return ys[n // 2]
    return (ys[n // 2 - 1] + ys[n // 2]) / 2
""",
        "bad_a": r"""def mid(xs):
    n = len(xs)
    if n % 2:
        return xs[n // 2]
    return (xs[n // 2 - 1] + xs[n // 2]) / 2
""",
        "bad_b": r"""def mid(xs):
    ys = sorted(xs)
    return ys[(len(ys) - 1) // 2]
""",
        "bad_c": r"""def median(xs):
    ys = sorted(xs)
    n = len(ys)
    if n % 2:
        return ys[n // 2]
    return (ys[n // 2 - 1] + ys[n // 2]) / 2
""",
        "visible": [
            {"fn": "mid", "args": ([3, 1, 2],), "want": 2},
            {"fn": "mid", "args": ([4, 1, 3, 2],), "want": 2.5},
        ],
        "hidden_extra": [
            {"fn": "mid", "args": ([1],), "want": 1},
            {"fn": "mid", "args": ([2, 1],), "want": 1.5},
            {"fn": "mid", "args": ([5, 3, 1, 4, 2],), "want": 3},
            {"fn": "mid", "args": ([10, -10],), "want": 0.0},
            {"fn": "mid", "args": ([1, 2, 3, 4, 5, 6],), "want": 3.5},
        ],
    },
    {
        "id": "s1_15_chunks",
        "title": "cut a list into consecutive pieces",
        "prose": """Cut a list into consecutive pieces of a given maximum size, in
order.

The last piece is whatever is left over and may be shorter than the others.
All the pieces come back gathered in one list, and each piece is itself a
list.""",
        "names": ["chunks"],
        "trap": "name (split_into_chunks / batch) + pieces are lists, not tuples",
        "solution": r"""def chunks(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n)]
""",
        "bad_a": r"""def chunks(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n) if i + n <= len(xs)]
""",
        "bad_b": r"""def chunks(xs, n):
    return [tuple(xs[i:i + n]) for i in range(0, len(xs), n)]
""",
        "bad_c": r"""def split_into_chunks(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n)]
""",
        "visible": [
            {"fn": "chunks", "args": ([1, 2, 3, 4, 5], 2),
             "want": [[1, 2], [3, 4], [5]]},
            {"fn": "chunks", "args": ([], 3), "want": []},
        ],
        "hidden_extra": [
            {"fn": "chunks", "args": ([1, 2, 3], 3), "want": [[1, 2, 3]]},
            {"fn": "chunks", "args": ([1], 5), "want": [[1]]},
            {"fn": "chunks", "args": ([1, 2, 3, 4], 2), "want": [[1, 2], [3, 4]]},
            {"fn": "chunks", "args": (["a", "b", "c"], 1),
             "want": [["a"], ["b"], ["c"]]},
            {"fn": "chunks", "args": ([1, 2, 3, 4, 5, 6, 7], 3),
             "want": [[1, 2, 3], [4, 5, 6], [7]]},
        ],
    },
    {
        "id": "s1_16_flat",
        "title": "one flat list out of a list of lists",
        "prose": """Take a list whose entries are themselves lists and give back one
single list holding the inner entries in the order they appear.

Only one level of nesting is ever present, and the order is left exactly as it
was.""",
        "names": ["flat"],
        "trap": "name (flatten is the natural guess)",
        "solution": r"""def flat(nested):
    return [x for inner in nested for x in inner]
""",
        "bad_a": r"""def flat(nested):
    return sorted(x for inner in nested for x in inner)
""",
        "bad_b": r"""def flat(nested):
    return tuple(x for inner in nested for x in inner)
""",
        "bad_c": r"""def flatten(nested):
    return [x for inner in nested for x in inner]
""",
        "visible": [
            {"fn": "flat", "args": ([[1, 2], [3]],), "want": [1, 2, 3]},
            {"fn": "flat", "args": ([[3], [1, 2]],), "want": [3, 1, 2]},
        ],
        "hidden_extra": [
            {"fn": "flat", "args": ([],), "want": []},
            {"fn": "flat", "args": ([[]],), "want": []},
            {"fn": "flat", "args": ([[1], [], [2]],), "want": [1, 2]},
            {"fn": "flat", "args": ([["a", "b"]],), "want": ["a", "b"]},
            {"fn": "flat", "args": ([[1], [2], [3]],), "want": [1, 2, 3]},
        ],
    },
    {
        "id": "s1_17_pairs_to_map",
        "title": "build a lookup from two parallel lists",
        "prose": """Given one list of keys and one list of values of the same length,
build a lookup that maps each key to the value sitting at the same position.

If a key shows up more than once, the value that stays is the one from the
later position.""",
        "names": ["pairs_to_map"],
        "trap": "name (zip_dict / to_dict) + later-wins",
        "solution": r"""def pairs_to_map(keys, values):
    return dict(zip(keys, values))
""",
        "bad_a": r"""def pairs_to_map(keys, values):
    out = {}
    for k, v in zip(keys, values):
        if k not in out:
            out[k] = v
    return out
""",
        "bad_b": r"""def pairs_to_map(keys, values):
    return list(zip(keys, values))
""",
        "bad_c": r"""def zip_dict(keys, values):
    return dict(zip(keys, values))
""",
        "visible": [
            {"fn": "pairs_to_map", "args": (["a", "b"], [1, 2]),
             "want": {"a": 1, "b": 2}},
            {"fn": "pairs_to_map", "args": (["a", "a"], [1, 2]), "want": {"a": 2}},
        ],
        "hidden_extra": [
            {"fn": "pairs_to_map", "args": ([], []), "want": {}},
            {"fn": "pairs_to_map", "args": (["x"], [9]), "want": {"x": 9}},
            {"fn": "pairs_to_map", "args": (["a", "b", "a"], [1, 2, 3]),
             "want": {"a": 3, "b": 2}},
            {"fn": "pairs_to_map", "args": (["k"], [None]), "want": {"k": None}},
            {"fn": "pairs_to_map", "args": (["p", "q"], ["1", "2"]),
             "want": {"p": "1", "q": "2"}},
        ],
    },
    {
        "id": "s1_18_flip_map",
        "title": "turn a lookup inside out",
        "prose": """Turn a lookup inside out: every value becomes a key and the key it
came from becomes its value.

When two keys share a value, the one that comes later in the original is the
one that wins.""",
        "names": ["flip_map"],
        "trap": "name (invert / reverse_dict) + later-wins",
        "solution": r"""def flip_map(d):
    return {v: k for k, v in d.items()}
""",
        "bad_a": r"""def flip_map(d):
    out = {}
    for k, v in d.items():
        if v not in out:
            out[v] = k
    return out
""",
        "bad_b": r"""def flip_map(d):
    return [(v, k) for k, v in d.items()]
""",
        "bad_c": r"""def invert(d):
    return {v: k for k, v in d.items()}
""",
        "visible": [
            {"fn": "flip_map", "args": ({"a": 1, "b": 2},), "want": {1: "a", 2: "b"}},
            {"fn": "flip_map", "args": ({"a": 1, "b": 1},), "want": {1: "b"}},
        ],
        "hidden_extra": [
            {"fn": "flip_map", "args": ({},), "want": {}},
            {"fn": "flip_map", "args": ({"x": "y"},), "want": {"y": "x"}},
            {"fn": "flip_map", "args": ({"a": 1, "b": 2, "c": 1},),
             "want": {1: "c", 2: "b"}},
            {"fn": "flip_map", "args": ({1: "one"},), "want": {"one": 1}},
            {"fn": "flip_map", "args": ({"k": 0},), "want": {0: "k"}},
        ],
    },
    {
        "id": "s1_19_tally",
        "title": "how many times each entry shows up",
        "prose": """Count how many times each entry shows up in a list.

Give back a lookup from the entry to its count. Entries that never show up are
not in the result at all.""",
        "names": ["tally"],
        "trap": "name (count_items / counter) + a lookup, not a list of pairs",
        "solution": r"""def tally(items):
    out = {}
    for it in items:
        out[it] = out.get(it, 0) + 1
    return out
""",
        "bad_a": r"""def tally(items):
    return {it: 1 for it in items}
""",
        "bad_b": r"""def tally(items):
    out = {}
    for it in items:
        out[it] = out.get(it, 0) + 1
    return sorted(out.items())
""",
        "bad_c": r"""def count_items(items):
    out = {}
    for it in items:
        out[it] = out.get(it, 0) + 1
    return out
""",
        "visible": [
            {"fn": "tally", "args": (["a", "b", "a"],), "want": {"a": 2, "b": 1}},
            {"fn": "tally", "args": ([],), "want": {}},
        ],
        "hidden_extra": [
            {"fn": "tally", "args": (["x"],), "want": {"x": 1}},
            {"fn": "tally", "args": ([1, 1, 1],), "want": {1: 3}},
            {"fn": "tally", "args": (["a", "a", "b", "b"],), "want": {"a": 2, "b": 2}},
            {"fn": "tally", "args": (["p", "q", "r"],),
             "want": {"p": 1, "q": 1, "r": 1}},
            {"fn": "tally", "args": (["z", "z"],), "want": {"z": 2}},
        ],
    },
    {
        "id": "s1_20_top_key",
        "title": "which name holds the highest count",
        "prose": """Given a lookup from names to counts, report which name holds the
highest count.

When several names share the highest count, the answer is the one that sorts
earliest alphabetically. The lookup handed in is never without entries.""",
        "names": ["top_key"],
        "trap": "name (most_common / argmax) + the tie rule",
        "solution": r"""def top_key(d):
    best = None
    for k in sorted(d):
        if best is None or d[k] > d[best]:
            best = k
    return best
""",
        "bad_a": r"""def top_key(d):
    best = None
    for k in sorted(d):
        if best is None or d[k] >= d[best]:
            best = k
    return best
""",
        "bad_b": r"""def top_key(d):
    return max(d.values())
""",
        "bad_c": r"""def most_common(d):
    best = None
    for k in sorted(d):
        if best is None or d[k] > d[best]:
            best = k
    return best
""",
        "visible": [
            {"fn": "top_key", "args": ({"a": 1, "b": 3},), "want": "b"},
            {"fn": "top_key", "args": ({"b": 2, "a": 2},), "want": "a"},
        ],
        "hidden_extra": [
            {"fn": "top_key", "args": ({"x": 5},), "want": "x"},
            {"fn": "top_key", "args": ({"a": 1, "b": 1, "c": 1},), "want": "a"},
            {"fn": "top_key", "args": ({"z": 9, "y": 9, "a": 1},), "want": "y"},
            {"fn": "top_key", "args": ({"m": 0, "n": -1},), "want": "m"},
            {"fn": "top_key", "args": ({"q": 3, "p": 4},), "want": "p"},
        ],
    },
    {
        "id": "s1_21_total",
        "title": "add up the whole numbers between two bounds",
        "prose": """Add up every whole number from one bound to another, with both
bounds themselves counted in.

When the first bound sits above the second there is nothing to add up, and the
answer is zero.""",
        "names": ["total"],
        "trap": "name (range_sum / sum_range) + inclusive bounds",
        "solution": r"""def total(a, b):
    if a > b:
        return 0
    return sum(range(a, b + 1))
""",
        "bad_a": r"""def total(a, b):
    if a > b:
        return 0
    return sum(range(a, b))
""",
        "bad_b": r"""def total(a, b):
    if a > b:
        return None
    return sum(range(a, b + 1))
""",
        "bad_c": r"""def range_sum(a, b):
    if a > b:
        return 0
    return sum(range(a, b + 1))
""",
        "visible": [
            {"fn": "total", "args": (1, 5), "want": 15},
            {"fn": "total", "args": (5, 1), "want": 0},
        ],
        "hidden_extra": [
            {"fn": "total", "args": (0, 0), "want": 0},
            {"fn": "total", "args": (3, 3), "want": 3},
            {"fn": "total", "args": (-2, 2), "want": 0},
            {"fn": "total", "args": (1, 100), "want": 5050},
            {"fn": "total", "args": (-3, -1), "want": -6},
        ],
    },
    {
        "id": "s1_22_digit_list",
        "title": "the digits of a number, one by one",
        "prose": """Break a whole number that is never negative into its individual
digits, most significant first.

Each digit comes back as a whole number, and they come back gathered in a
list.""",
        "names": ["digit_list"],
        "trap": "name (digits / to_digits) + whole numbers, not characters",
        "solution": r"""def digit_list(n):
    return [int(c) for c in str(n)]
""",
        "bad_a": r"""def digit_list(n):
    return [int(c) for c in reversed(str(n))]
""",
        "bad_b": r"""def digit_list(n):
    return list(str(n))
""",
        "bad_c": r"""def digits(n):
    return [int(c) for c in str(n)]
""",
        "visible": [
            {"fn": "digit_list", "args": (120,), "want": [1, 2, 0]},
            {"fn": "digit_list", "args": (7,), "want": [7]},
        ],
        "hidden_extra": [
            {"fn": "digit_list", "args": (0,), "want": [0]},
            {"fn": "digit_list", "args": (1000,), "want": [1, 0, 0, 0]},
            {"fn": "digit_list", "args": (9876,), "want": [9, 8, 7, 6]},
            {"fn": "digit_list", "args": (10,), "want": [1, 0]},
            {"fn": "digit_list", "args": (505,), "want": [5, 0, 5]},
        ],
    },
    {
        "id": "s1_23_cross_sum",
        "title": "add the digits of a number together",
        "prose": """Add together the individual digits of a whole number that is never
negative, and give back the total as a whole number.

The digits are added exactly once: the total is not reduced any further.""",
        "names": ["cross_sum"],
        "trap": "name (digit_sum / sum_digits)",
        "solution": r"""def cross_sum(n):
    return sum(int(c) for c in str(n))
""",
        "bad_a": r"""def cross_sum(n):
    while n > 9:
        n = sum(int(c) for c in str(n))
    return n
""",
        "bad_b": r"""def cross_sum(n):
    return str(sum(int(c) for c in str(n)))
""",
        "bad_c": r"""def digit_sum(n):
    return sum(int(c) for c in str(n))
""",
        "visible": [
            {"fn": "cross_sum", "args": (99,), "want": 18},
            {"fn": "cross_sum", "args": (0,), "want": 0},
        ],
        "hidden_extra": [
            {"fn": "cross_sum", "args": (5,), "want": 5},
            {"fn": "cross_sum", "args": (1234,), "want": 10},
            {"fn": "cross_sum", "args": (1000,), "want": 1},
            {"fn": "cross_sum", "args": (999,), "want": 27},
            {"fn": "cross_sum", "args": (10,), "want": 1},
        ],
    },
    {
        "id": "s1_24_is_pal",
        "title": "does it read the same both ways",
        "prose": """Decide whether a piece of text reads the same forwards and
backwards, once letters and digits are the only characters looked at and the
difference between upper and lower case is set aside.

Text with no letters or digits in it at all counts as reading the same. The
answer is a true or false value.""",
        "names": ["is_pal"],
        "trap": "name (is_palindrome is the natural guess)",
        "solution": r"""def is_pal(s):
    t = [c.lower() for c in s if c.isalnum()]
    return t == t[::-1]
""",
        "bad_a": r"""def is_pal(s):
    t = [c for c in s if c.isalnum()]
    return t == t[::-1]
""",
        "bad_b": r"""def is_pal(s):
    t = [c.lower() for c in s if c.isalnum()]
    return "yes" if t == t[::-1] else "no"
""",
        "bad_c": r"""def is_palindrome(s):
    t = [c.lower() for c in s if c.isalnum()]
    return t == t[::-1]
""",
        "visible": [
            {"fn": "is_pal", "args": ("A man, a plan, a canal: Panama",), "want": True},
            {"fn": "is_pal", "args": ("Ab",), "want": False},
        ],
        "hidden_extra": [
            {"fn": "is_pal", "args": ("",), "want": True},
            {"fn": "is_pal", "args": ("!!!",), "want": True},
            {"fn": "is_pal", "args": ("aa",), "want": True},
            {"fn": "is_pal", "args": ("Racecar",), "want": True},
            {"fn": "is_pal", "args": ("abc",), "want": False},
            {"fn": "is_pal", "args": ("12321",), "want": True},
        ],
    },
    {
        "id": "s1_25_shift_letters",
        "title": "move every letter along the alphabet",
        "prose": """Shift every letter of a piece of text along the alphabet by a given
number of places, wrapping round from the end back to the beginning.

Upper case stays upper case, lower case stays lower case, and anything that is
not a letter is left exactly as it was. The shift may be negative and may be
larger than the alphabet.""",
        "names": ["shift_letters"],
        "trap": "name (caesar / rot / encrypt)",
        "solution": r"""def shift_letters(s, k):
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
        "bad_a": r"""def shift_letters(s, k):
    return "".join(chr((ord(c) + k) % 128) for c in s)
""",
        "bad_b": r"""def shift_letters(s, k):
    out = []
    for c in s.lower():
        if "a" <= c <= "z":
            out.append(chr((ord(c) - 97 + k) % 26 + 97))
        else:
            out.append(c)
    return "".join(out)
""",
        "bad_c": r"""def caesar(s, k):
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
            {"fn": "shift_letters", "args": ("abc-XYZ", 1), "want": "bcd-YZA"},
            {"fn": "shift_letters", "args": ("abc", -1), "want": "zab"},
        ],
        "hidden_extra": [
            {"fn": "shift_letters", "args": ("", 5), "want": ""},
            {"fn": "shift_letters", "args": ("Hello, World!", 13),
             "want": "Uryyb, Jbeyq!"},
            {"fn": "shift_letters", "args": ("xyz", 3), "want": "abc"},
            {"fn": "shift_letters", "args": ("ABC", 0), "want": "ABC"},
            {"fn": "shift_letters", "args": ("a1b", 1), "want": "b1c"},
        ],
    },
    {
        "id": "s1_26_cells",
        "title": "fields of one comma-separated line",
        "prose": """Take one line of comma-separated text and give back its fields in
order, with any spaces around each field removed.

There are no quoted fields and no escaped commas, so every comma separates.
A line with nothing in it has one field, and that field is text with nothing
in it.""",
        "names": ["cells"],
        "trap": "name (parse_csv_line / split_line) + the stripping",
        "solution": r"""def cells(line):
    return [p.strip() for p in line.split(",")]
""",
        "bad_a": r"""def cells(line):
    return line.split(",")
""",
        "bad_b": r"""def cells(line):
    return [p.strip() for p in line.split(",") if p.strip()]
""",
        "bad_c": r"""def parse_csv_line(line):
    return [p.strip() for p in line.split(",")]
""",
        "visible": [
            {"fn": "cells", "args": ("a, b ,c",), "want": ["a", "b", "c"]},
            {"fn": "cells", "args": ("",), "want": [""]},
        ],
        "hidden_extra": [
            {"fn": "cells", "args": ("x",), "want": ["x"]},
            {"fn": "cells", "args": ("a,,b",), "want": ["a", "", "b"]},
            {"fn": "cells", "args": (" one , two ",), "want": ["one", "two"]},
            {"fn": "cells", "args": (",",), "want": ["", ""]},
            {"fn": "cells", "args": ("p,q,r",), "want": ["p", "q", "r"]},
        ],
    },
    {
        "id": "s1_27_parse_kv",
        "title": "read a semicolon-separated settings line",
        "prose": """Read a settings line made of name-and-value pairs.

Pairs are separated by semicolons. Inside a pair the name comes before an
equals sign and the value after it. Spaces around a name or a value are not
part of it. A stretch between two semicolons with nothing in it is skipped.

Build the lookup from name to value, both kept as text. When the same name
appears more than once, the later one wins.""",
        "names": ["parse_kv"],
        "trap": "name (parse_settings / parse_config) + later-wins",
        "solution": r"""def parse_kv(line):
    out = {}
    for part in line.split(";"):
        if not part.strip():
            continue
        name, _, value = part.partition("=")
        out[name.strip()] = value.strip()
    return out
""",
        "bad_a": r"""def parse_kv(line):
    out = {}
    for part in line.split(";"):
        if not part.strip():
            continue
        name, _, value = part.partition("=")
        out.setdefault(name.strip(), value.strip())
    return out
""",
        "bad_b": r"""def parse_kv(line):
    out = []
    for part in line.split(";"):
        if not part.strip():
            continue
        name, _, value = part.partition("=")
        out.append((name.strip(), value.strip()))
    return out
""",
        "bad_c": r"""def parse_settings(line):
    out = {}
    for part in line.split(";"):
        if not part.strip():
            continue
        name, _, value = part.partition("=")
        out[name.strip()] = value.strip()
    return out
""",
        "visible": [
            {"fn": "parse_kv", "args": ("a=1; b = 2",), "want": {"a": "1", "b": "2"}},
            {"fn": "parse_kv", "args": ("k=1;k=2",), "want": {"k": "2"}},
        ],
        "hidden_extra": [
            {"fn": "parse_kv", "args": ("",), "want": {}},
            {"fn": "parse_kv", "args": ("x=",), "want": {"x": ""}},
            {"fn": "parse_kv", "args": ("a=1;;b=2",), "want": {"a": "1", "b": "2"}},
            {"fn": "parse_kv", "args": (" n = v ",), "want": {"n": "v"}},
            {"fn": "parse_kv", "args": ("a=1;b=2;a=3",), "want": {"a": "3", "b": "2"}},
        ],
    },
    {
        "id": "s1_28_split_path",
        "title": "break a path into three pieces",
        "prose": """Break a file path into three pieces: the folder part in front of the
last separator, the file's own name without its extension, and the extension
without the dot in front of it.

The separator is a forward slash. A path with no folder part has a folder
piece with nothing in it; a name with no dot has an extension with nothing in
it; when there is more than one dot, only the last one starts the extension.

The three pieces come back together in one object.""",
        "names": ["split_path"],
        "trap": "name + return shape (dict with keys dir/name/ext, not a 3-tuple)",
        "solution": r"""def split_path(p):
    head, _, tail = p.rpartition("/")
    base, dot, ext = tail.rpartition(".")
    if not dot:
        base, ext = tail, ""
    return {"dir": head, "name": base, "ext": ext}
""",
        "bad_a": r"""def split_path(p):
    head, _, tail = p.rpartition("/")
    base, dot, ext = tail.rpartition(".")
    if not dot:
        return {"dir": head, "name": tail, "ext": ""}
    return {"dir": head, "name": base, "ext": "." + ext}
""",
        "bad_b": r"""def split_path(p):
    head, _, tail = p.rpartition("/")
    base, dot, ext = tail.rpartition(".")
    if not dot:
        base, ext = tail, ""
    return (head, base, ext)
""",
        "bad_c": r"""def path_parts(p):
    head, _, tail = p.rpartition("/")
    base, dot, ext = tail.rpartition(".")
    if not dot:
        base, ext = tail, ""
    return {"dir": head, "name": base, "ext": ext}
""",
        "visible": [
            {"fn": "split_path", "args": ("a/b/c.txt",),
             "want": {"dir": "a/b", "name": "c", "ext": "txt"}},
            {"fn": "split_path", "args": ("readme",),
             "want": {"dir": "", "name": "readme", "ext": ""}},
        ],
        "hidden_extra": [
            {"fn": "split_path", "args": ("x.y",),
             "want": {"dir": "", "name": "x", "ext": "y"}},
            {"fn": "split_path", "args": ("/abs/f.md",),
             "want": {"dir": "/abs", "name": "f", "ext": "md"}},
            {"fn": "split_path", "args": ("a/b/",),
             "want": {"dir": "a/b", "name": "", "ext": ""}},
            {"fn": "split_path", "args": ("d/n.tar.gz",),
             "want": {"dir": "d", "name": "n.tar", "ext": "gz"}},
            {"fn": "split_path", "args": ("./f",),
             "want": {"dir": ".", "name": "f", "ext": ""}},
        ],
    },
    {
        "id": "s1_29_strip_zeros",
        "title": "tidy a decimal written as text",
        "prose": """Tidy a decimal number that is written as text by removing the zeros
sitting at the end of its fractional part, and then the dot itself when
nothing is left after it.

Text with no dot in it is given back untouched, and the answer is still
text.""",
        "names": ["strip_zeros"],
        "trap": "name (trim_zeros) + the answer stays text, not a number",
        "solution": r"""def strip_zeros(s):
    if "." not in s:
        return s
    s = s.rstrip("0")
    if s.endswith("."):
        s = s[:-1]
    return s
""",
        "bad_a": r"""def strip_zeros(s):
    s = s.rstrip("0")
    if s.endswith("."):
        s = s[:-1]
    return s
""",
        "bad_b": r"""def strip_zeros(s):
    if "." not in s:
        return s
    return float(s)
""",
        "bad_c": r"""def trim_zeros(s):
    if "." not in s:
        return s
    s = s.rstrip("0")
    if s.endswith("."):
        s = s[:-1]
    return s
""",
        "visible": [
            {"fn": "strip_zeros", "args": ("1.500",), "want": "1.5"},
            {"fn": "strip_zeros", "args": ("100",), "want": "100"},
        ],
        "hidden_extra": [
            {"fn": "strip_zeros", "args": ("2.000",), "want": "2"},
            {"fn": "strip_zeros", "args": ("0.0",), "want": "0"},
            {"fn": "strip_zeros", "args": ("3.14",), "want": "3.14"},
            {"fn": "strip_zeros", "args": ("10.10",), "want": "10.1"},
            {"fn": "strip_zeros", "args": ("0",), "want": "0"},
        ],
    },
    {
        "id": "s1_30_ord_suffix",
        "title": "a number written as a position",
        "prose": """Write a positive whole number the way it is said when counting
positions: the number itself followed by the two-letter ending that goes with
it.

The three teens that sit between ten and fourteen are the well-known exception
and take the plain ending. The answer is text.""",
        "names": ["ord_suffix"],
        "trap": "name (ordinal) + the teen exception",
        "solution": r"""def ord_suffix(n):
    if n % 100 in (11, 12, 13):
        tail = "th"
    else:
        tail = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, tail)
""",
        "bad_a": r"""def ord_suffix(n):
    tail = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, tail)
""",
        "bad_b": r"""def ord_suffix(n):
    if n % 100 in (11, 12, 13):
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
""",
        "bad_c": r"""def ordinal(n):
    if n % 100 in (11, 12, 13):
        tail = "th"
    else:
        tail = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, tail)
""",
        "visible": [
            {"fn": "ord_suffix", "args": (1,), "want": "1st"},
            {"fn": "ord_suffix", "args": (12,), "want": "12th"},
        ],
        "hidden_extra": [
            {"fn": "ord_suffix", "args": (2,), "want": "2nd"},
            {"fn": "ord_suffix", "args": (3,), "want": "3rd"},
            {"fn": "ord_suffix", "args": (4,), "want": "4th"},
            {"fn": "ord_suffix", "args": (11,), "want": "11th"},
            {"fn": "ord_suffix", "args": (21,), "want": "21st"},
            {"fn": "ord_suffix", "args": (113,), "want": "113th"},
            {"fn": "ord_suffix", "args": (100,), "want": "100th"},
        ],
    },
    {
        "id": "s1_31_money",
        "title": "cents written the way a receipt writes them",
        "prose": """Show an amount given as a whole number of cents the way it appears on
a receipt in dollars: a dollar sign, then the whole dollars, then a dot, then
always exactly two digits of cents.

Amounts below one dollar still show a single zero in front of the dot. Amounts
are never negative, and the answer is text.""",
        "names": ["money"],
        "trap": "name (format_money / to_dollars) + the answer is text",
        "solution": r"""def money(cents):
    return "$%d.%02d" % divmod(cents, 100)
""",
        "bad_a": r"""def money(cents):
    return "$%d.%d" % divmod(cents, 100)
""",
        "bad_b": r"""def money(cents):
    return cents / 100
""",
        "bad_c": r"""def format_money(cents):
    return "$%d.%02d" % divmod(cents, 100)
""",
        "visible": [
            {"fn": "money", "args": (1234,), "want": "$12.34"},
            {"fn": "money", "args": (5,), "want": "$0.05"},
        ],
        "hidden_extra": [
            {"fn": "money", "args": (0,), "want": "$0.00"},
            {"fn": "money", "args": (100,), "want": "$1.00"},
            {"fn": "money", "args": (99,), "want": "$0.99"},
            {"fn": "money", "args": (100000,), "want": "$1000.00"},
            {"fn": "money", "args": (250,), "want": "$2.50"},
        ],
    },
    {
        "id": "s1_32_pct",
        "title": "one quantity as a percentage of another",
        "prose": """Express one quantity as a percentage of another.

The answer is a number rounded to one decimal place. When the second quantity
is nothing at all, the answer is nothing at all rather than an error.""",
        "names": ["pct"],
        "trap": "name (percentage / percent_of) + the rounding",
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
    if whole == 0:
        return "0.0%"
    return "%.1f%%" % (part * 100 / whole)
""",
        "bad_c": r"""def percentage(part, whole):
    if whole == 0:
        return 0.0
    return round(part * 100 / whole, 1)
""",
        "visible": [
            {"fn": "pct", "args": (1, 3), "want": 33.3},
            {"fn": "pct", "args": (0, 0), "want": 0.0},
        ],
        "hidden_extra": [
            {"fn": "pct", "args": (1, 2), "want": 50.0},
            {"fn": "pct", "args": (2, 3), "want": 66.7},
            {"fn": "pct", "args": (0, 5), "want": 0.0},
            {"fn": "pct", "args": (5, 5), "want": 100.0},
            {"fn": "pct", "args": (1, 8), "want": 12.5},
        ],
    },
    {
        "id": "s1_33_band",
        "title": "a mark reported as a single letter",
        "prose": """Turn a mark out of one hundred into the single letter it is reported
as at an American school.

Ninety and above is the top letter, eighty and above the next one down,
seventy and above the one after that, sixty and above the one after that, and
anything lower is the fifth letter used -- which is not the fifth letter of
the alphabet.

The answer is a single upper-case character.""",
        "names": ["band"],
        "trap": "name (grade / letter_grade) + the boundaries are inclusive",
        "solution": r"""def band(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"
""",
        "bad_a": r"""def band(score):
    if score > 90:
        return "A"
    if score > 80:
        return "B"
    if score > 70:
        return "C"
    if score > 60:
        return "D"
    return "F"
""",
        "bad_b": r"""def band(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "E"
""",
        "bad_c": r"""def grade(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"
""",
        "visible": [
            {"fn": "band", "args": (90,), "want": "A"},
            {"fn": "band", "args": (59,), "want": "F"},
        ],
        "hidden_extra": [
            {"fn": "band", "args": (100,), "want": "A"},
            {"fn": "band", "args": (85,), "want": "B"},
            {"fn": "band", "args": (70,), "want": "C"},
            {"fn": "band", "args": (60,), "want": "D"},
            {"fn": "band", "args": (0,), "want": "F"},
            {"fn": "band", "args": (89,), "want": "B"},
        ],
    },
    {
        "id": "s1_34_days_in",
        "title": "how long a given month is",
        "prose": """Report how many days a given month of a given year has.

The year is the first argument and the month is the second, written as a
number from one to twelve. February follows the usual rule about years
divisible by four, by one hundred and by four hundred.""",
        "names": ["days_in"],
        "trap": "name (days_in_month / month_length) + argument order",
        "solution": r"""def days_in(y, m):
    if m == 2:
        leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
        return 29 if leap else 28
    return 30 if m in (4, 6, 9, 11) else 31
""",
        "bad_a": r"""def days_in(y, m):
    if m == 2:
        return 29 if y % 4 == 0 else 28
    return 30 if m in (4, 6, 9, 11) else 31
""",
        "bad_b": r"""def days_in(y, m):
    if m == 2:
        leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
        return "29" if leap else "28"
    return "30" if m in (4, 6, 9, 11) else "31"
""",
        "bad_c": r"""def days_in_month(y, m):
    if m == 2:
        leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
        return 29 if leap else 28
    return 30 if m in (4, 6, 9, 11) else 31
""",
        "visible": [
            {"fn": "days_in", "args": (2000, 2), "want": 29},
            {"fn": "days_in", "args": (1900, 2), "want": 28},
        ],
        "hidden_extra": [
            {"fn": "days_in", "args": (2024, 2), "want": 29},
            {"fn": "days_in", "args": (2023, 2), "want": 28},
            {"fn": "days_in", "args": (2023, 4), "want": 30},
            {"fn": "days_in", "args": (2023, 12), "want": 31},
            {"fn": "days_in", "args": (2023, 1), "want": 31},
            {"fn": "days_in", "args": (2100, 2), "want": 28},
        ],
    },
    {
        "id": "s1_35_rle",
        "title": "compress runs of one repeated character",
        "prose": """Compress a piece of text by replacing each run of one repeated
character with that character together with how many times it repeated in a
row.

The runs come back in order, each one as a pair holding the character first
and the count second. A pair here is the immutable kind.""",
        "names": ["rle"],
        "trap": "name (encode / compress) + pairs are tuples, not lists",
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
            out[-1] = (c, out[-1][1] + 1)
        else:
            out.append((c, s.count(c)))
    return out
""",
        "bad_b": r"""def rle(s):
    out = []
    for c in s:
        if out and out[-1][0] == c:
            out[-1][1] += 1
        else:
            out.append([c, 1])
    return out
""",
        "bad_c": r"""def encode(s):
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
            {"fn": "rle", "args": ("xxyyzz",),
             "want": [("x", 2), ("y", 2), ("z", 2)]},
            {"fn": "rle", "args": ("  ",), "want": [(" ", 2)]},
        ],
    },
    {
        "id": "s1_36_longest_run",
        "title": "the longest stretch of one character",
        "prose": """Find the longest stretch of one repeated character in a piece of text
and report both which character it was and how long the stretch ran.

When two stretches are the same length, the one that started earlier is the
answer. The two facts come back together in one object. The text handed in is
never without characters.""",
        "names": ["longest_run"],
        "trap": "name + return shape (dict with keys ch/n, not a pair)",
        "solution": r"""def longest_run(s):
    best_ch, best_n = s[0], 0
    cur_ch, cur_n = None, 0
    for c in s:
        if c == cur_ch:
            cur_n += 1
        else:
            cur_ch, cur_n = c, 1
        if cur_n > best_n:
            best_ch, best_n = cur_ch, cur_n
    return {"ch": best_ch, "n": best_n}
""",
        "bad_a": r"""def longest_run(s):
    best_ch, best_n = s[0], 0
    cur_ch, cur_n = None, 0
    for c in s:
        if c == cur_ch:
            cur_n += 1
        else:
            cur_ch, cur_n = c, 1
        if cur_n >= best_n:
            best_ch, best_n = cur_ch, cur_n
    return {"ch": best_ch, "n": best_n}
""",
        "bad_b": r"""def longest_run(s):
    best_ch, best_n = s[0], 0
    cur_ch, cur_n = None, 0
    for c in s:
        if c == cur_ch:
            cur_n += 1
        else:
            cur_ch, cur_n = c, 1
        if cur_n > best_n:
            best_ch, best_n = cur_ch, cur_n
    return (best_ch, best_n)
""",
        "bad_c": r"""def max_run(s):
    best_ch, best_n = s[0], 0
    cur_ch, cur_n = None, 0
    for c in s:
        if c == cur_ch:
            cur_n += 1
        else:
            cur_ch, cur_n = c, 1
        if cur_n > best_n:
            best_ch, best_n = cur_ch, cur_n
    return {"ch": best_ch, "n": best_n}
""",
        "visible": [
            {"fn": "longest_run", "args": ("aabbb",), "want": {"ch": "b", "n": 3}},
            {"fn": "longest_run", "args": ("aabb",), "want": {"ch": "a", "n": 2}},
        ],
        "hidden_extra": [
            {"fn": "longest_run", "args": ("x",), "want": {"ch": "x", "n": 1}},
            {"fn": "longest_run", "args": ("aaa",), "want": {"ch": "a", "n": 3}},
            {"fn": "longest_run", "args": ("abc",), "want": {"ch": "a", "n": 1}},
            {"fn": "longest_run", "args": ("zzzaa",), "want": {"ch": "z", "n": 3}},
            {"fn": "longest_run", "args": ("  ab",), "want": {"ch": " ", "n": 2}},
        ],
    },
    {
        "id": "s1_37_same_letters",
        "title": "made of exactly the same letters",
        "prose": """Decide whether two pieces of text are made of exactly the same
characters in some order, each used the same number of times.

Upper and lower case are treated as the same, and spaces are ignored
altogether. Everything else counts. The answer is a true or false value.""",
        "names": ["same_letters"],
        "trap": "name (is_anagram) + multiset, not set",
        "solution": r"""def _key(t):
    return sorted(t.lower().replace(" ", ""))


def same_letters(a, b):
    return _key(a) == _key(b)
""",
        "bad_a": r"""def same_letters(a, b):
    return sorted(a.replace(" ", "")) == sorted(b.replace(" ", ""))
""",
        "bad_b": r"""def same_letters(a, b):
    return set(a.lower().replace(" ", "")) == set(b.lower().replace(" ", ""))
""",
        "bad_c": r"""def is_anagram(a, b):
    def key(t):
        return sorted(t.lower().replace(" ", ""))
    return key(a) == key(b)
""",
        "visible": [
            {"fn": "same_letters", "args": ("Listen", "Silent"), "want": True},
            {"fn": "same_letters", "args": ("aab", "abb"), "want": False},
        ],
        "hidden_extra": [
            {"fn": "same_letters", "args": ("", ""), "want": True},
            {"fn": "same_letters", "args": ("a b", "ba"), "want": True},
            {"fn": "same_letters", "args": ("abc", "cab"), "want": True},
            {"fn": "same_letters", "args": ("abc", "abd"), "want": False},
            {"fn": "same_letters", "args": ("Dormitory", "Dirty Room"), "want": True},
        ],
    },
    {
        "id": "s1_38_shared_start",
        "title": "the opening every word has in common",
        "prose": """Given a list of words, find the longest opening stretch of characters
that every one of them begins with.

The comparison is exact, so a difference of case is a difference. When there
is nothing in common the answer is text with nothing in it. The list handed in
is never without entries.""",
        "names": ["shared_start"],
        "trap": "name (common_prefix / longest_common_prefix)",
        "solution": r"""def shared_start(words):
    out = ""
    for i in range(min(len(w) for w in words)):
        c = words[0][i]
        if all(w[i] == c for w in words):
            out += c
        else:
            break
    return out
""",
        "bad_a": r"""def shared_start(words):
    out = ""
    for i in range(min(len(w) for w in words)):
        c = words[0][i]
        if all(w[i].lower() == c.lower() for w in words):
            out += c
        else:
            break
    return out
""",
        "bad_b": r"""def shared_start(words):
    out = ""
    for i in range(min(len(w) for w in words)):
        c = words[0][i]
        if all(w[i] == c for w in words):
            out += c
        else:
            break
    return out or None
""",
        "bad_c": r"""def common_prefix(words):
    out = ""
    for i in range(min(len(w) for w in words)):
        c = words[0][i]
        if all(w[i] == c for w in words):
            out += c
        else:
            break
    return out
""",
        "visible": [
            {"fn": "shared_start", "args": (["flow", "flower", "flight"],),
             "want": "fl"},
            {"fn": "shared_start", "args": (["Abc", "abc"],), "want": ""},
        ],
        "hidden_extra": [
            {"fn": "shared_start", "args": (["x"],), "want": "x"},
            {"fn": "shared_start", "args": (["ab", "ab"],), "want": "ab"},
            {"fn": "shared_start", "args": (["", ""],), "want": ""},
            {"fn": "shared_start", "args": (["abc", "abd", "abe"],), "want": "ab"},
            {"fn": "shared_start", "args": (["dog", "cat"],), "want": ""},
        ],
    },
    {
        "id": "s1_39_wrap_at",
        "title": "break a line at a given width",
        "prose": """Break a line of text into pieces no longer than a given width,
breaking only between words.

A word longer than the width goes on a piece of its own and is never cut in
half. Words are separated by whitespace on the way in and by a single space
inside a piece. The pieces come back in order, gathered together.""",
        "names": ["wrap_at"],
        "trap": "name (wrap / word_wrap) + the pieces come back as a list",
        "solution": r"""def wrap_at(s, width):
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
        "bad_a": r"""def wrap_at(s, width):
    joined = " ".join(s.split())
    return [joined[i:i + width] for i in range(0, len(joined), width)]
""",
        "bad_b": r"""def wrap_at(s, width):
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
        "bad_c": r"""def wrap(s, width):
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
            {"fn": "wrap_at", "args": ("a bb ccc", 5), "want": ["a bb", "ccc"]},
            {"fn": "wrap_at", "args": ("enormous", 3), "want": ["enormous"]},
        ],
        "hidden_extra": [
            {"fn": "wrap_at", "args": ("", 5), "want": []},
            {"fn": "wrap_at", "args": ("one two", 100), "want": ["one two"]},
            {"fn": "wrap_at", "args": ("a a a a", 3), "want": ["a a", "a a"]},
            {"fn": "wrap_at", "args": ("xx yy zz", 5), "want": ["xx yy", "zz"]},
            {"fn": "wrap_at", "args": ("word", 4), "want": ["word"]},
        ],
    },
    {
        "id": "s1_40_bullets",
        "title": "lay a list out for a plain-text note",
        "prose": """Take a list of short strings and lay them out as a simple list for a
plain-text note: each entry on its own line, introduced by a hyphen and one
space.

There is no line break after the last entry, and a list without entries gives
text with nothing in it.""",
        "names": ["bullets"],
        "trap": "name (to_bullets / bullet_list) + no trailing newline",
        "solution": r"""def bullets(items):
    return "\n".join("- " + it for it in items)
""",
        "bad_a": r"""def bullets(items):
    return "\n".join("* " + it for it in items)
""",
        "bad_b": r"""def bullets(items):
    return "".join("- " + it + "\n" for it in items)
""",
        "bad_c": r"""def to_bullets(items):
    return "\n".join("- " + it for it in items)
""",
        "visible": [
            {"fn": "bullets", "args": (["a", "b"],), "want": "- a\n- b"},
            {"fn": "bullets", "args": ([],), "want": ""},
        ],
        "hidden_extra": [
            {"fn": "bullets", "args": (["x"],), "want": "- x"},
            {"fn": "bullets", "args": (["a", "b", "c"],), "want": "- a\n- b\n- c"},
            {"fn": "bullets", "args": ([""],), "want": "- "},
            {"fn": "bullets", "args": (["one two"],), "want": "- one two"},
            {"fn": "bullets", "args": (["1", "2"],), "want": "- 1\n- 2"},
        ],
    },
    {
        "id": "s1_41_squeeze",
        "title": "collapse whitespace down to single spaces",
        "prose": """Tidy a piece of text so that every run of whitespace inside it
becomes one single space, and so that there is no whitespace left at the start
or at the end.""",
        "names": ["squeeze"],
        "trap": "name (normalize_spaces / collapse_whitespace)",
        "solution": r"""def squeeze(s):
    return " ".join(s.split())
""",
        "bad_a": r"""def squeeze(s):
    return s.strip().replace("  ", " ")
""",
        "bad_b": r"""def squeeze(s):
    out = []
    prev_space = False
    for c in s:
        if c.isspace():
            if not prev_space:
                out.append(" ")
            prev_space = True
        else:
            out.append(c)
            prev_space = False
    return "".join(out)
""",
        "bad_c": r"""def normalize_spaces(s):
    return " ".join(s.split())
""",
        "visible": [
            {"fn": "squeeze", "args": ("  a   b  ",), "want": "a b"},
            {"fn": "squeeze", "args": ("",), "want": ""},
        ],
        "hidden_extra": [
            {"fn": "squeeze", "args": ("a",), "want": "a"},
            {"fn": "squeeze", "args": ("a\t\tb",), "want": "a b"},
            {"fn": "squeeze", "args": ("\n x \n",), "want": "x"},
            {"fn": "squeeze", "args": ("a  b  c",), "want": "a b c"},
            {"fn": "squeeze", "args": ("   ",), "want": ""},
        ],
    },
    {
        "id": "s1_42_snakeify",
        "title": "capitals marking words become underscores",
        "prose": """Rewrite an identifier whose word boundaries are marked by capital
letters so that the words are separated by underscores instead and every
letter is lower case.

The first character may or may not be a capital; either way the result never
starts with an underscore. Every capital after the first character starts a
new word, with no special treatment for runs of capitals.""",
        "names": ["snakeify"],
        "trap": "name (to_snake_case / camel_to_snake)",
        "solution": r"""def snakeify(s):
    out = []
    for i, c in enumerate(s):
        if c.isupper() and i > 0:
            out.append("_")
        out.append(c.lower())
    return "".join(out)
""",
        "bad_a": r"""def snakeify(s):
    out = []
    for c in s:
        if c.isupper():
            out.append("_")
        out.append(c.lower())
    return "".join(out)
""",
        "bad_b": r"""def snakeify(s):
    out = []
    for i, c in enumerate(s):
        if c.isupper() and i > 0:
            out.append("_")
        out.append(c.upper())
    return "".join(out)
""",
        "bad_c": r"""def to_snake_case(s):
    out = []
    for i, c in enumerate(s):
        if c.isupper() and i > 0:
            out.append("_")
        out.append(c.lower())
    return "".join(out)
""",
        "visible": [
            {"fn": "snakeify", "args": ("camelCase",), "want": "camel_case"},
            {"fn": "snakeify", "args": ("PascalCase",), "want": "pascal_case"},
        ],
        "hidden_extra": [
            {"fn": "snakeify", "args": ("",), "want": ""},
            {"fn": "snakeify", "args": ("a",), "want": "a"},
            {"fn": "snakeify", "args": ("A",), "want": "a"},
            {"fn": "snakeify", "args": ("HTTPServer",), "want": "h_t_t_p_server"},
            {"fn": "snakeify", "args": ("oneTwoThree",), "want": "one_two_three"},
        ],
    },
    {
        "id": "s1_43_camelise",
        "title": "underscores become capitals",
        "prose": """Rewrite an identifier whose words are separated by underscores so
that the words run together instead.

Every word after the first one starts with a capital and carries on in lower
case; the first word is left entirely in lower case.""",
        "names": ["camelise"],
        "trap": "name (to_camel_case / snake_to_camel)",
        "solution": r"""def camelise(s):
    parts = s.split("_")
    return parts[0].lower() + "".join(
        p[:1].upper() + p[1:].lower() for p in parts[1:])
""",
        "bad_a": r"""def camelise(s):
    parts = s.split("_")
    return "".join(p[:1].upper() + p[1:].lower() for p in parts)
""",
        "bad_b": r"""def camelise(s):
    return s.lower()
""",
        "bad_c": r"""def to_camel_case(s):
    parts = s.split("_")
    return parts[0].lower() + "".join(
        p[:1].upper() + p[1:].lower() for p in parts[1:])
""",
        "visible": [
            {"fn": "camelise", "args": ("one_two_three",), "want": "oneTwoThree"},
            {"fn": "camelise", "args": ("single",), "want": "single"},
        ],
        "hidden_extra": [
            {"fn": "camelise", "args": ("",), "want": ""},
            {"fn": "camelise", "args": ("a_b",), "want": "aB"},
            {"fn": "camelise", "args": ("A_B",), "want": "aB"},
            {"fn": "camelise", "args": ("x_y_z",), "want": "xYZ"},
            {"fn": "camelise", "args": ("snake_case_name",), "want": "snakeCaseName"},
        ],
    },
    {
        "id": "s1_44_by_length",
        "title": "order words from shortest to longest",
        "prose": """Put a list of words in order from the shortest to the longest.

Words that are the same length keep exactly the order they were handed in, so
nothing else is compared.""",
        "names": ["by_length"],
        "trap": "name (sort_by_length) + the sort has to be stable, not alphabetical",
        "solution": r"""def by_length(words):
    return sorted(words, key=len)
""",
        "bad_a": r"""def by_length(words):
    return sorted(words, key=lambda w: (len(w), w))
""",
        "bad_b": r"""def by_length(words):
    return sorted(words, key=len, reverse=True)
""",
        "bad_c": r"""def sort_by_length(words):
    return sorted(words, key=len)
""",
        "visible": [
            {"fn": "by_length", "args": (["bbb", "a", "dd", "cc"],),
             "want": ["a", "dd", "cc", "bbb"]},
            {"fn": "by_length", "args": ([],), "want": []},
        ],
        "hidden_extra": [
            {"fn": "by_length", "args": (["x"],), "want": ["x"]},
            {"fn": "by_length", "args": (["bb", "aa"],), "want": ["bb", "aa"]},
            {"fn": "by_length", "args": (["ccc", "b", "aa"],),
             "want": ["b", "aa", "ccc"]},
            {"fn": "by_length", "args": (["", ""],), "want": ["", ""]},
            {"fn": "by_length", "args": (["abcd", "ab", "abc"],),
             "want": ["ab", "abc", "abcd"]},
        ],
    },
    {
        "id": "s1_45_group_first",
        "title": "sort words into groups by their first letter",
        "prose": """Sort a list of words into groups according to the letter each one
starts with.

The letter used for a group is written in lower case. Inside a group the words
keep the order they were handed in, and they keep their own spelling exactly.
The groups come back as a lookup from the letter to the words. No word handed
in is ever without characters.""",
        "names": ["group_first"],
        "trap": "name (group_by_first_letter) + the group letter is lower-cased",
        "solution": r"""def group_first(words):
    out = {}
    for w in words:
        out.setdefault(w[0].lower(), []).append(w)
    return out
""",
        "bad_a": r"""def group_first(words):
    out = {}
    for w in words:
        out.setdefault(w[0], []).append(w)
    return out
""",
        "bad_b": r"""def group_first(words):
    out = {}
    for w in words:
        out.setdefault(w[0].lower(), []).append(w)
    return sorted(out.items())
""",
        "bad_c": r"""def group_by_first_letter(words):
    out = {}
    for w in words:
        out.setdefault(w[0].lower(), []).append(w)
    return out
""",
        "visible": [
            {"fn": "group_first", "args": (["apple", "Avocado", "beet"],),
             "want": {"a": ["apple", "Avocado"], "b": ["beet"]}},
            {"fn": "group_first", "args": ([],), "want": {}},
        ],
        "hidden_extra": [
            {"fn": "group_first", "args": (["x"],), "want": {"x": ["x"]}},
            {"fn": "group_first", "args": (["Ab", "ac"],),
             "want": {"a": ["Ab", "ac"]}},
            {"fn": "group_first", "args": (["b", "a"],),
             "want": {"b": ["b"], "a": ["a"]}},
            {"fn": "group_first", "args": (["one", "two", "three"],),
             "want": {"o": ["one"], "t": ["two", "three"]}},
            {"fn": "group_first", "args": (["Zoo"],), "want": {"z": ["Zoo"]}},
        ],
    },
    {
        "id": "s1_46_merge_spans",
        "title": "join up overlapping intervals",
        "prose": """Given a list of closed numeric intervals, each written as a pair of a
start and an end, join up the ones that overlap and also the ones that merely
touch at a single point.

The intervals that come back are in increasing order of their starts, and each
one is itself written the same way the inputs were: a pair of two numbers that
can be changed after the fact.""",
        "names": ["merge_spans"],
        "trap": "name (merge_intervals) + touching counts + pieces are lists",
        "solution": r"""def merge_spans(spans):
    out = []
    for lo, hi in sorted(spans):
        if out and lo <= out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out
""",
        "bad_a": r"""def merge_spans(spans):
    out = []
    for lo, hi in sorted(spans):
        if out and lo < out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out
""",
        "bad_b": r"""def merge_spans(spans):
    out = []
    for lo, hi in sorted(spans):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out
""",
        "bad_c": r"""def merge_intervals(spans):
    out = []
    for lo, hi in sorted(spans):
        if out and lo <= out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out
""",
        "visible": [
            {"fn": "merge_spans", "args": ([[1, 3], [2, 5]],), "want": [[1, 5]]},
            {"fn": "merge_spans", "args": ([[1, 2], [2, 3]],), "want": [[1, 3]]},
        ],
        "hidden_extra": [
            {"fn": "merge_spans", "args": ([],), "want": []},
            {"fn": "merge_spans", "args": ([[1, 2]],), "want": [[1, 2]]},
            {"fn": "merge_spans", "args": ([[5, 6], [1, 2]],),
             "want": [[1, 2], [5, 6]]},
            {"fn": "merge_spans", "args": ([[1, 10], [2, 3]],), "want": [[1, 10]]},
            {"fn": "merge_spans", "args": ([[1, 2], [4, 5], [5, 7]],),
             "want": [[1, 2], [4, 7]]},
        ],
    },
    {
        "id": "s1_47_pairwise_diff",
        "title": "the step from each entry to the next",
        "prose": """Given a list of numbers, report the step taken from each entry to the
one after it.

The answer holds one entry fewer than the input, and a list with fewer than
two entries gives an answer with nothing in it.""",
        "names": ["pairwise_diff"],
        "trap": "name (deltas / diffs) + one shorter, not the same length",
        "solution": r"""def pairwise_diff(xs):
    return [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
""",
        "bad_a": r"""def pairwise_diff(xs):
    return [xs[i] - xs[i + 1] for i in range(len(xs) - 1)]
""",
        "bad_b": r"""def pairwise_diff(xs):
    if not xs:
        return []
    return [0] + [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
""",
        "bad_c": r"""def deltas(xs):
    return [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
""",
        "visible": [
            {"fn": "pairwise_diff", "args": ([1, 4, 2],), "want": [3, -2]},
            {"fn": "pairwise_diff", "args": ([],), "want": []},
        ],
        "hidden_extra": [
            {"fn": "pairwise_diff", "args": ([5],), "want": []},
            {"fn": "pairwise_diff", "args": ([1, 1],), "want": [0]},
            {"fn": "pairwise_diff", "args": ([0, 10, 20],), "want": [10, 10]},
            {"fn": "pairwise_diff", "args": ([-1, -5],), "want": [-4]},
            {"fn": "pairwise_diff", "args": ([2, 3, 5, 8],), "want": [1, 2, 3]},
        ],
    },
    {
        "id": "s1_48_cumsum",
        "title": "the total so far at every position",
        "prose": """Given a list of numbers, give back a list of exactly the same length
where each entry is the total of everything up to and including the entry at
that position.""",
        "names": ["cumsum"],
        "trap": "name (running_total / accumulate) + the current entry is included",
        "solution": r"""def cumsum(xs):
    out = []
    t = 0
    for x in xs:
        t += x
        out.append(t)
    return out
""",
        "bad_a": r"""def cumsum(xs):
    out = []
    t = 0
    for x in xs:
        out.append(t)
        t += x
    return out
""",
        "bad_b": r"""def cumsum(xs):
    return sum(xs)
""",
        "bad_c": r"""def running_total(xs):
    out = []
    t = 0
    for x in xs:
        t += x
        out.append(t)
    return out
""",
        "visible": [
            {"fn": "cumsum", "args": ([1, 2, 3],), "want": [1, 3, 6]},
            {"fn": "cumsum", "args": ([],), "want": []},
        ],
        "hidden_extra": [
            {"fn": "cumsum", "args": ([5],), "want": [5]},
            {"fn": "cumsum", "args": ([0, 0],), "want": [0, 0]},
            {"fn": "cumsum", "args": ([-1, 1],), "want": [-1, 0]},
            {"fn": "cumsum", "args": ([2, 2, 2, 2],), "want": [2, 4, 6, 8]},
            {"fn": "cumsum", "args": ([10],), "want": [10]},
        ],
    },
    {
        "id": "s1_49_rgb",
        "title": "read a stylesheet colour",
        "prose": """Read a colour written the way a stylesheet writes it -- a hash
character followed by six hexadecimal digits -- and report the three channel
values.

Each channel is a whole number from zero to two hundred and fifty-five, and
the three of them come back together in one object. Hexadecimal digits are
accepted in either case.""",
        "names": ["rgb"],
        "trap": "name (hex_to_rgb) + return shape (dict with keys r/g/b)",
        "solution": r"""def rgb(code):
    t = code.lstrip("#")
    return {"r": int(t[0:2], 16), "g": int(t[2:4], 16), "b": int(t[4:6], 16)}
""",
        "bad_a": r"""def rgb(code):
    t = code.lstrip("#")
    return {"r": int(t[4:6], 16), "g": int(t[2:4], 16), "b": int(t[0:2], 16)}
""",
        "bad_b": r"""def rgb(code):
    t = code.lstrip("#")
    return (int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16))
""",
        "bad_c": r"""def hex_to_rgb(code):
    t = code.lstrip("#")
    return {"r": int(t[0:2], 16), "g": int(t[2:4], 16), "b": int(t[4:6], 16)}
""",
        "visible": [
            {"fn": "rgb", "args": ("#FF8000",), "want": {"r": 255, "g": 128, "b": 0}},
            {"fn": "rgb", "args": ("#000000",), "want": {"r": 0, "g": 0, "b": 0}},
        ],
        "hidden_extra": [
            {"fn": "rgb", "args": ("#ffffff",),
             "want": {"r": 255, "g": 255, "b": 255}},
            {"fn": "rgb", "args": ("#010203",), "want": {"r": 1, "g": 2, "b": 3}},
            {"fn": "rgb", "args": ("#00ff00",), "want": {"r": 0, "g": 255, "b": 0}},
            {"fn": "rgb", "args": ("#AABBCC",),
             "want": {"r": 170, "g": 187, "b": 204}},
            {"fn": "rgb", "args": ("#123456",), "want": {"r": 18, "g": 52, "b": 86}},
        ],
    },
    {
        "id": "s1_50_ends",
        "title": "the first and the last entry of a list",
        "prose": """Report the first entry and the last entry of a list, handed back
together in one object.

A list holding a single entry has that same entry at each end. The
list handed in is never without entries.""",
        "names": ["ends"],
        "trap": "name (first_last / head_tail) + return shape (dict with first/last)",
        "solution": r"""def ends(xs):
    return {"first": xs[0], "last": xs[-1]}
""",
        "bad_a": r"""def ends(xs):
    return {"first": xs[-1], "last": xs[0]}
""",
        "bad_b": r"""def ends(xs):
    return (xs[0], xs[-1])
""",
        "bad_c": r"""def first_last(xs):
    return {"first": xs[0], "last": xs[-1]}
""",
        "visible": [
            {"fn": "ends", "args": ([1, 2, 3],), "want": {"first": 1, "last": 3}},
            {"fn": "ends", "args": (["only"],),
             "want": {"first": "only", "last": "only"}},
        ],
        "hidden_extra": [
            {"fn": "ends", "args": ([0, 9],), "want": {"first": 0, "last": 9}},
            {"fn": "ends", "args": (["a", "b", "c", "d"],),
             "want": {"first": "a", "last": "d"}},
            {"fn": "ends", "args": ([None, 1],), "want": {"first": None, "last": 1}},
            {"fn": "ends", "args": ([5],), "want": {"first": 5, "last": 5}},
            {"fn": "ends", "args": ([1, 2],), "want": {"first": 1, "last": 2}},
        ],
    },
]

#: S1 的 `TASK_explicit.md` 插入塊（Fable 2026-09-19 重裁的增補）。
#:
#: 第四條臂 `PC`（正控制，每題只跑 1 次、不重試）跑的是**同一題**，但把
#: `TASK.md` 換成 `TASK_explicit.md`——S1 這一層被 withhold 的東西就是
#: **函式名／簽名／回傳形狀**，所以這裡把它們寫明。
#:
#: PC 是 RP 臂的**天花板**：沒有它，「RP 沒提升」有兩個分不開的解釋——
#: 「agent 看得到回饋但不照做」與「講明白了它也寫不出來」。PC 把後者切掉。
#: 事前預測 PC 第 1 次可見通過 ≥ 0.8；PC < 0.5 ⇒ 該層判 `CEILING_TOO_LOW`
#: （題目對這顆模型太難，管道問題根本沒被提出來）。
#:
#: ⚠ 這個塊是**唯一**允許出現在兩份 TASK 之間的差（量具第 6 項是可執行擋門）：
#: 兩份若在別的地方也不一樣（多一句提示、少一個例子、換個語氣），
#: PC 就不再是同一題的天花板，`CEILING_TOO_LOW` 判準就失效。
EXPLICIT = {
    "s1_01_addmul": ["add(a, b) -> number", "mul(a, b) -> number"],
    "s1_02_span": ['span(xs) -> {"lo": <smallest>, "hi": <largest>}'],
    "s1_03_nwords": ["n_words(line) -> int"],
    "s1_04_toc": ["to_c(f) -> float"],
    "s1_05_initials": ["initials(full_name) -> list[str]"],
    "s1_06_parity": ['split_parity(xs) -> {"even": list, "odd": list}'],
    "s1_07_flipwords": ["flip_words(s) -> str"],
    "s1_08_nvowels": ["n_vowels(s) -> int"],
    "s1_09_pin": ["pin(x, low, high) -> number"],
    "s1_10_uniq": ["uniq(xs) -> list"],
    "s1_11_caps": ["caps(s) -> str"],
    "s1_12_hms": ["hms(total_seconds) -> str"],
    "s1_13_mean": ["mean(xs) -> float"],
    "s1_14_mid": ["mid(xs) -> number"],
    "s1_15_chunks": ["chunks(xs, n) -> list[list]"],
    "s1_16_flat": ["flat(nested) -> list"],
    "s1_17_pairs_to_map": ["pairs_to_map(keys, values) -> dict"],
    "s1_18_flip_map": ["flip_map(d) -> dict"],
    "s1_19_tally": ["tally(items) -> dict"],
    "s1_20_top_key": ["top_key(d) -> the name, as it appears in the lookup"],
    "s1_21_total": ["total(a, b) -> int"],
    "s1_22_digit_list": ["digit_list(n) -> list[int]"],
    "s1_23_cross_sum": ["cross_sum(n) -> int"],
    "s1_24_is_pal": ["is_pal(s) -> bool"],
    "s1_25_shift_letters": ["shift_letters(s, k) -> str"],
    "s1_26_cells": ["cells(line) -> list[str]"],
    "s1_27_parse_kv": ["parse_kv(line) -> dict[str, str]"],
    "s1_28_split_path":
        ['split_path(p) -> {"dir": str, "name": str, "ext": str}'],
    "s1_29_strip_zeros": ["strip_zeros(s) -> str"],
    "s1_30_ord_suffix": ["ord_suffix(n) -> str"],
    "s1_31_money": ["money(cents) -> str"],
    "s1_32_pct": ["pct(part, whole) -> float"],
    "s1_33_band": ["band(score) -> str"],
    "s1_34_days_in": ["days_in(y, m) -> int"],
    "s1_35_rle": ["rle(s) -> list[tuple[str, int]]"],
    "s1_36_longest_run": ['longest_run(s) -> {"ch": str, "n": int}'],
    "s1_37_same_letters": ["same_letters(a, b) -> bool"],
    "s1_38_shared_start": ["shared_start(words) -> str"],
    "s1_39_wrap_at": ["wrap_at(s, width) -> list[str]"],
    "s1_40_bullets": ["bullets(items) -> str"],
    "s1_41_squeeze": ["squeeze(s) -> str"],
    "s1_42_snakeify": ["snakeify(s) -> str"],
    "s1_43_camelise": ["camelise(s) -> str"],
    "s1_44_by_length": ["by_length(words) -> list[str]"],
    "s1_45_group_first": ["group_first(words) -> dict[str, list[str]]"],
    "s1_46_merge_spans": ["merge_spans(spans) -> list[list[number]]"],
    "s1_47_pairwise_diff": ["pairwise_diff(xs) -> list[number]"],
    "s1_48_cumsum": ["cumsum(xs) -> list[number]"],
    "s1_49_rgb": ['rgb(code) -> {"r": int, "g": int, "b": int}'],
    "s1_50_ends": ['ends(xs) -> {"first": <first entry>, "last": <last entry>}'],
}
