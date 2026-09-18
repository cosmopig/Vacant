"""suitemutate — 把「驗收套件擋得住多少種**已知的錯**」從 1 種變成 N 種的刻度尺。

這支在架構裡承重什麼
====================
`vacant/suitegauge.py` 是套件上鏈前的合格閘，但它的壞解集合實務上只有**一個**
變異體：`broken_stub()` 產生的最退化那份（`return None`）。那把尺的下界低到
一套「把三條 assert 刪到只剩一條」的套件照樣拿滿分——這句話是 suitegauge
docstring §3「單邊保證」自己寫的，本模組不是來推翻它，是把**同一條保證的刻度
變細**：從「擋得住 1 種錯」變成「擋得住我們造得出來的 N 種錯裡的幾種」。

用法是餵給既有的量具，不是另做一把：

    from vacant.suitemutate import score_suite

    out = score_suite(task["visible_check"]["code"], reference,
                      entry_point=task["entry_point"])
    out.score          # 變異致死率
    out.survivors      # 活下來的變異體（有資訊的是這個，不是分數）

⚠ **致死率不綁 `GaugeOutcome.ok`，這是紅線。** `ok` 要求壞解集合**全部**被擋；
  把變異體接成 `commit_suite` 的 `broken_stubs` 會讓「活下來一個」＝整份套件拒收，
  那是**改掉閘門語意**，r452c 那批已歸檔資料會失去可比性。本模組對
  `gauge_suite` 的呼叫是**唯讀的量測**：只取 `accepted_stubs`／`n_rejected`，
  `ok` 一個字都不看，也不回傳。要換閘門語意請另走裁決，不要從這裡偷渡。

紅線與誠實邊界（改碼不得刪）
----------------------------
1. **致死率永遠是下界，而且是雙重下界。**
   (a) 分母只有「我們造得出來的那 N 種錯」——變異運算子是一張有限的表，
       真需求裡的錯不在表上的一律不算；
   (b) **等價變異體不可判定**（程式等價性是停機問題的一個實例）。改了碼但語義
       沒變的變異體活下來時，它被算進「沒擋住」，所以真值只會**高於**回報值。
   本模組只做得起一種便宜過濾：變異後的正規化原始碼與基準逐字相同就丟掉
   （`build_mutants` 裡的 `code == base`）。抓不到的殘留就留著並如實計進分母。
2. **致死率 100% ≠ 驗收涵蓋需求。** 它只代表「這 N 種我們造得出來的錯都被擋住」。
   這與 suitegauge §3 是同一條保證，只是刻度變細；**不准**讀成套件固定點已解。
3. **正規化基準要自己先過。** `ast.unparse` 的往返若改了語義，每個變異體都會
   「被擋住」而分數假性衝到 1.0。`verify_baseline=True` 多跑一次正規化後的
   參考解把這件事變成可見的 `normalized_passed=False`，不是安靜的滿分。
4. **只動參考解，不動驗收碼。** 本模組不 parse、不改 `check_code`，
   `hidden_check` 一處都沒有出現——V/GT 分離與 suitegauge §1 同一條論證。
"""

from __future__ import annotations

import ast
import difflib
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence, cast

from vacant.suitegauge import DEFAULT_TIMEOUT_S, CheckRunner, sha256_hex

MUTATION_VERSION = 1

#: 比較運算子翻轉表（只翻成**同元數**的另一個運算子，不改樹形）。
_CMP_FLIP: dict[type, type] = {
    ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}
#: 二元運算子替換表。`+`↔`-`、`*`↔`/` 等；型別錯（str 相減）也算合法變異，
#: 它會被擋下＝套件確實在跑那條路徑。
_BIN_SWAP: dict[type, type] = {
    ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mult, ast.Mod: ast.FloorDiv, ast.Pow: ast.Mult,
    ast.LShift: ast.RShift, ast.RShift: ast.LShift,
    ast.BitAnd: ast.BitOr, ast.BitOr: ast.BitAnd, ast.BitXor: ast.BitAnd,
}

#: 運算子名稱表（回報用；`by_operator` 的鍵就是這些字串）。
OPERATORS: tuple[str, ...] = (
    "num_plus_1", "num_minus_1", "bool_const_flip", "cmp_flip", "bool_op_swap",
    "not_remove", "not_insert", "bin_op_swap", "continue_to_pass",
    "break_to_pass", "str_truncate", "return_const",
)


@dataclass(frozen=True)
class Mutant:
    """一個變異體：完整的變異後原始碼 ＋ 它到底改了哪一行。"""

    index: int
    operator: str
    lineno: int          # 行號是**正規化後**（`ast.unparse`）的行號，不是原檔行號
    before: str
    after: str
    code: str

    def as_dict(self) -> dict:
        return {"index": self.index, "operator": self.operator,
                "lineno": self.lineno, "before": self.before, "after": self.after}


class _Patch(ast.NodeTransformer):
    """只改一個節點：`_mut_id` 命中就換掉，並且**不往下遞迴**（一次一個變異）。"""

    def __init__(self, target: int, apply: Callable[[ast.AST], Any]) -> None:
        self.target = target
        self.apply = apply

    def visit(self, node: ast.AST) -> Any:
        if getattr(node, "_mut_id", None) == self.target:
            return self.apply(node)
        return self.generic_visit(node)


def _indexed(source: str) -> ast.AST:
    """重新 parse 並給每個節點一個穩定編號（`ast.walk` 順序＝確定性）。"""
    tree = ast.parse(source)
    for i, node in enumerate(ast.walk(tree)):
        node._mut_id = i                                     # type: ignore[attr-defined]
    return tree


def _docstring_ids(tree: ast.AST) -> set[int]:
    """docstring 的字串常數不變異：改它一定是等價變異體，白花一次沙箱。"""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and getattr(node, "body", None):
            first = node.body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                out.add(first.value._mut_id)                 # type: ignore[attr-defined]
    return out


def _kval(n: ast.AST) -> Any:
    """變異函式收到的那個節點的常數值。

    **只在型別層做事**（`typing.cast` 執行期是恆等函式，一個位元都不改）。
    下面那幾個 lambda 是在 `isinstance(node, ast.Constant)` 的分支裡註冊的，
    `_Patch` 也只會把它們套回**同一個 `_mut_id`** 的那個節點上 ⇒ 收到的一定是
    常數節點，而且是註冊時那個守衛（bool／int、float／str）挑中的那一種。
    回 `Any` 就是因為**是哪一種由註冊處的守衛決定**，而「註冊時的守衛決定
    lambda 會收到什麼」這件事型別系統表達不了；它是這支的結構保證，不是希望。
    """
    return cast(ast.Constant, n).value


def _sites(source: str) -> list[tuple[str, int, Callable[[ast.AST], Any]]]:
    """列出所有變異點（運算子名, 節點 id, 套用函式）。"""
    tree = _indexed(source)
    skip = _docstring_ids(tree)
    tests = {n.test._mut_id for n in ast.walk(tree)           # type: ignore[attr-defined]
             if isinstance(n, (ast.If, ast.While))}
    out: list[tuple[str, int, Callable[[ast.AST], Any]]] = []
    for node in ast.walk(tree):
        nid = node._mut_id                                    # type: ignore[attr-defined]
        if isinstance(node, ast.Constant) and nid not in skip:
            v = node.value
            if isinstance(v, bool):
                out.append(("bool_const_flip", nid,
                            lambda n: ast.Constant(value=not _kval(n))))
            elif isinstance(v, (int, float)):
                out.append(("num_plus_1", nid,
                            lambda n: ast.Constant(value=_kval(n) + 1)))
                out.append(("num_minus_1", nid,
                            lambda n: ast.Constant(value=_kval(n) - 1)))
            elif isinstance(v, str) and len(v) >= 2:
                out.append(("str_truncate", nid,
                            lambda n: ast.Constant(value=_kval(n)[:-1])))
        elif type(node) in _CMP_FLIP:
            out.append(("cmp_flip", nid, lambda n: _CMP_FLIP[type(n)]()))
        elif type(node) in _BIN_SWAP:
            out.append(("bin_op_swap", nid, lambda n: _BIN_SWAP[type(n)]()))
        elif isinstance(node, (ast.And, ast.Or)):
            out.append(("bool_op_swap", nid,
                        lambda n: ast.Or() if isinstance(n, ast.And) else ast.And()))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            # cast 的理由同 `_kval`：這個 lambda 只會被套回這個
            # `ast.UnaryOp` 節點。執行期是恆等函式。
            out.append(("not_remove", nid,
                        lambda n: cast(ast.UnaryOp, n).operand))
        elif isinstance(node, ast.Continue):
            out.append(("continue_to_pass", nid, lambda n: ast.Pass()))
        elif isinstance(node, ast.Break):
            out.append(("break_to_pass", nid, lambda n: ast.Pass()))
        elif isinstance(node, ast.Return) and node.value is not None:
            out.append(("return_const", nid, _degrade_return))
        if nid in tests:
            # `tests` 收的是 `ast.If`／`ast.While` 的 `.test`，那一欄的型別
            # 就是 `ast.expr` ⇒ 包成 `not <expr>` 合法。cast 執行期是恆等函式。
            out.append(("not_insert", nid,
                        lambda n: ast.UnaryOp(op=ast.Not(),
                                              operand=cast(ast.expr, n))))
    return out


def _degrade_return(node: ast.AST) -> ast.Return:
    """return 值退化成常數：原本不是 None 就回 None，本來就 None 的回 0。"""
    v = getattr(node, "value", None)
    to_none = not (isinstance(v, ast.Constant) and v.value is None)
    return ast.Return(value=ast.Constant(value=None if to_none else 0))


def _render(source: str, target: int, apply: Callable[[ast.AST], Any]) -> str:
    tree = _Patch(target, apply).visit(_indexed(source))
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _first_diff(base: str, mutant: str) -> tuple[int, str, str]:
    a, b = base.splitlines(), mutant.splitlines()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b).get_opcodes():
        if tag != "equal":
            return i1 + 1, " ⏎ ".join(a[i1:i2]).strip(), " ⏎ ".join(b[j1:j2]).strip()
    return 0, "", ""


def build_mutants(
    source: str, *, limit: int | None = None, seed: Any = "suitemutate",
    operators: Sequence[str] | None = None,
) -> list[Mutant]:
    """造變異體。`limit` 給定時**依運算子輪流抽**（seed 決定性），不是取前 N 個。

    輪流抽的理由：取前 N 個會被 `ast.walk` 的順序綁死，通常整批都是同一類
    （檔頭的數值常數），量到的就變成「這一類擋不擋得住」而不是套件強度。
    """
    base = ast.unparse(ast.parse(source))
    wanted = set(operators) if operators else None
    groups: dict[str, list[Mutant]] = {}
    for op, nid, apply in _sites(source):
        if wanted is not None and op not in wanted:
            continue
        try:
            code = _render(source, nid, apply)
        except Exception:                                    # noqa: BLE001
            continue                                          # 造不出來就不算（不進分母）
        if code == base:
            continue                                          # 便宜的等價過濾（見 §1）
        ln, before, after = _first_diff(base, code)
        groups.setdefault(op, []).append(
            Mutant(index=-1, operator=op, lineno=ln, before=before,
                   after=after, code=code))
    ordered: list[Mutant] = []
    if limit is None:
        for op in OPERATORS:
            ordered.extend(groups.get(op, []))
    else:
        rng = random.Random(f"{seed}:{sha256_hex(source)[:16]}")
        pools = {op: rng.sample(v, len(v)) for op, v in groups.items()}
        while len(ordered) < limit and any(pools.values()):
            for op in OPERATORS:
                if pools.get(op):
                    ordered.append(pools[op].pop())
                    if len(ordered) >= limit:
                        break
    seen: set[str] = set()
    out: list[Mutant] = []
    for m in ordered:
        if m.code in seen:
            continue                                          # 同一份碼只算一次
        seen.add(m.code)
        out.append(Mutant(index=len(out), operator=m.operator, lineno=m.lineno,
                          before=m.before, after=m.after, code=m.code))
    return out


def mutant_sources(source: str, **kw: Any) -> list[str]:
    """只要原始碼字串的捷徑——直接可餵 `gauge_suite(..., broken_stubs=...)`。"""
    return [m.code for m in build_mutants(source, **kw)]


@dataclass(frozen=True)
class MutationOutcome:
    """一次變異量測的完整產物。**沒有 `ok`**：本模組不產生合格判準（見模組 docstring）。"""

    suite_sha256: str
    ref_sha256: str
    ref_passed: bool
    normalized_passed: bool | None
    killed: int
    total: int
    survivors: tuple[Mutant, ...] = field(default_factory=tuple)
    by_operator: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def score(self) -> float | None:
        """致死率。**永遠是下界**（等價變異體不可判定＋運算子表有限）。"""
        return None if self.total == 0 else self.killed / self.total

    def as_dict(self) -> dict:
        return {
            "v": MUTATION_VERSION, "suite_sha256": self.suite_sha256,
            "ref_sha256": self.ref_sha256, "ref_passed": self.ref_passed,
            "normalized_passed": self.normalized_passed,
            "killed": self.killed, "total": self.total, "score": self.score,
            "survivors": [m.as_dict() for m in self.survivors],
            "by_operator": {k: list(v) for k, v in sorted(self.by_operator.items())},
        }


def score_suite(
    check_code: str, reference: str, *, entry_point: str | None = None,
    runner: CheckRunner | None = None, timeout_s: int = DEFAULT_TIMEOUT_S,
    limit: int | None = None, seed: Any = "suitemutate",
    operators: Sequence[str] | None = None, verify_baseline: bool = True,
) -> MutationOutcome:
    """對**一套**可見驗收算變異致死率。

    走的是既有量具 `suitegauge.gauge_suite`（一個字都沒改）：變異體當它的
    `broken_stubs`，回來只取 `accepted_stubs`（活下來的）與 `n_rejected`。
    **`GaugeOutcome.ok` 不讀、不回傳、不參與任何判定**——理由見模組 docstring。

    例外不吞：`runner` 丟出來的（`InfraVoid` 等）照原樣往上拋，
    「量不起來」與「量到 0」必須分得開（06-30 稽核紀律）。
    """
    from vacant.suitegauge import gauge_suite                 # noqa: PLC0415

    mutants = build_mutants(reference, limit=limit, seed=seed, operators=operators)
    g = gauge_suite(check_code, reference, [m.code for m in mutants],
                    entry_point=entry_point, runner=runner, timeout_s=timeout_s)
    norm: bool | None = None
    if verify_baseline:
        gn = gauge_suite(check_code, ast.unparse(ast.parse(reference)), [],
                         entry_point=entry_point, runner=runner, timeout_s=timeout_s)
        norm = gn.ref_passed
    alive = set(g.accepted_stubs)
    by_op: dict[str, list[int]] = {}
    for m in mutants:
        k, t = by_op.setdefault(m.operator, [0, 0])
        by_op[m.operator] = [k + (0 if m.index in alive else 1), t + 1]
    return MutationOutcome(
        suite_sha256=g.suite_sha256, ref_sha256=g.ref_sha256, ref_passed=g.ref_passed,
        normalized_passed=norm, killed=g.n_rejected, total=len(mutants),
        survivors=tuple(m for m in mutants if m.index in alive),
        by_operator={k: (v[0], v[1]) for k, v in by_op.items()},
    )
