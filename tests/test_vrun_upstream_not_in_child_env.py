"""真上游位址**不准**出現在 agent 的環境裡（2026-09-20 稽核發現的洞）。

這支在架構裡承重什麼：`envmap.py` 第 15 行的誠實邊界句寫著
「`UPSTREAM_VARS`——從父行程讀真正上游位址用的（**讀完就從子環境拿掉**）」，
而 `build_child_env` 在 2026-09-20 之前只剝 `SECRET_VARS`。
Fable 唯讀稽核實讀 pi 子行程的 `/proc/<pid>/environ`，兩個變數都在
⇒ **規格說了、碼沒做**。本檔把那句話變成可執行的。

⚠ **這是 hygiene 不是 security boundary**（`UPSTREAM_ONLY_VARS` 的 ⚠）：
   擋的是「地址直接擺在 agent 面前」，擋不住 agent 用別的方法找到上游。
   結構性的答案是 netns（`sandbox.py`／`block_egress.sh`），不是藏地址。
"""
from vacant_network.vrun import envmap

REAL = "http://100.86.226.21:1234"
PROXY = "http://127.0.0.1:38109"


def _env():
    return {
        "VACANT_RUN_UPSTREAM_OPENAI": REAL + "/v1",
        "VACANT_RUN_UPSTREAM_ANTHROPIC": REAL,
        "OPENAI_BASE_URL": REAL + "/v1",     # 使用者自己設的，會被 redirect 蓋掉
        "OPENAI_API_KEY": "sk-real-secret",
        "PATH": "/usr/bin",
    }


def test_real_upstream_address_is_absent_from_child_env():
    child, _ = envmap.build_child_env(PROXY, "SENTINEL", env=_env())
    leaked = {k: v for k, v in child.items() if REAL in str(v)}
    assert not leaked, f"真後端位址洩漏進 agent 的環境：{leaked}"


def test_mediation_survives_the_strip():
    """⚠ 這一條不可省：`UPSTREAM_VARS` 與 `REDIRECT_VARS` 有 5 個名字重疊，
    整組剝掉會把**中介本身**拆掉。剝的必須是差集。"""
    child, _ = envmap.build_child_env(PROXY, "SENTINEL", env=_env())
    assert child["OPENAI_BASE_URL"] == PROXY + "/v1"
    assert child["VACANT_RUN_PROXY"] == PROXY


def test_stripped_upstream_is_recorded_separately_from_secrets():
    """金鑰與上游位址是兩種洩漏；混成一欄事後查不出那一跑有沒有交出真後端。"""
    _, meta = envmap.build_child_env(PROXY, "SENTINEL", env=_env())
    assert meta["stripped_upstream"] == [
        "VACANT_RUN_UPSTREAM_ANTHROPIC", "VACANT_RUN_UPSTREAM_OPENAI"]
    assert "OPENAI_API_KEY" in meta["stripped"]
    assert "VACANT_RUN_UPSTREAM_OPENAI" not in meta["stripped"]


def test_upstream_only_vars_is_computed_not_handwritten():
    """名單要算出來——以後有人往任一張表加名字都自動正確。"""
    up = {n for _, names in envmap.UPSTREAM_VARS for n in names}
    red = {n for n, _ in envmap.REDIRECT_VARS}
    assert set(envmap.UPSTREAM_ONLY_VARS) == up - red
    assert not set(envmap.UPSTREAM_ONLY_VARS) & red


def test_negative_control_the_old_behaviour_would_fail_this_file():
    """**負控制。** 把修法拿掉（只剝 SECRET_VARS）之後，第一條必須紅。

    沒有這一條，上面那幾個 assert 與一個永遠通過的測試長得一樣。
    """
    env = _env()
    child = dict(env)
    for name, suffix in envmap.REDIRECT_VARS:
        child[name] = PROXY.rstrip("/") + suffix
    for name in envmap.SECRET_VARS:
        child.pop(name, None)
    # ← 這裡刻意**不**剝 UPSTREAM_ONLY_VARS，重現 2026-09-20 之前的行為
    leaked = {k: v for k, v in child.items() if REAL in str(v)}
    assert leaked, "負控制失效：舊行為應該會洩漏，卻沒有 ⇒ 上面的測試不算數"
    assert set(leaked) == {"VACANT_RUN_UPSTREAM_OPENAI",
                           "VACANT_RUN_UPSTREAM_ANTHROPIC"}
