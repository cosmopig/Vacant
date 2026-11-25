import pathlib, sys, os
prompt = sys.argv[1]
log = pathlib.Path(os.environ["LFAKE_LOG"])
n = len(list(log.glob("prompt_*.txt"))) + 1
(log / f"prompt_{n}.txt").write_text(prompt)
# 錯的解：少了最後那一句（每次都一樣錯）
pathlib.Path("proverb.py").write_text('''def proverb(*items, qualifier=None):
    out = []
    for a, b in zip(items, items[1:]):
        out.append(f"For want of a {a} the {b} was lost.")
    return out
''')
