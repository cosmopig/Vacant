"""Streamlit dashboard for the P7 demo.

Run with: `uv run streamlit run src/vacant/mvp/dashboard.py`.

Pages:
- 網路 (Network) -- list of vacants with state, capability, mean
  reputation per dim.
- 血緣 (Lineage) -- parent_id chain visualisation.
- Scenario -- pick + run; events stream.
- 指標 (Metrics) -- 8 metrics, time-series.
- 對抗 (Adversarial) -- adversarial seed=666 ring detection.

User-facing text is in 繁體中文 per CLAUDE.md.
"""

from __future__ import annotations

import asyncio
from typing import Any

import streamlit as st

from vacant.mvp.demo_store import DemoStore
from vacant.mvp.metrics import METRIC_NAMES, MetricsSnapshot, compute_all
from vacant.mvp.scenarios import (
    ADVERSARIAL_SEED,
    DEFAULT_SEEDS,
    adversarial,
    get_runner,
)
from vacant.substrate import MockSubstrate

st.set_page_config(page_title="Vacant 居所層 Demo", layout="wide")

# Session state for caching scenario runs + a per-session DemoStore.
if "scenario_results" not in st.session_state:
    st.session_state["scenario_results"] = {}
if "demo_store" not in st.session_state:
    st.session_state["demo_store"] = DemoStore(":memory:")


def _store() -> DemoStore:
    store: DemoStore = st.session_state["demo_store"]
    return store


def _run_scenario(name: str, seed: int) -> Any:
    runner = get_runner(name)
    substrate = MockSubstrate(seed=seed)

    async def _go() -> Any:
        return await runner(substrate=substrate, seed=seed, store=_store())

    return asyncio.run(_go())


def _ensure_scenario(name: str) -> Any:
    cache = st.session_state["scenario_results"]
    if name not in cache:
        if name == "adversarial":
            cache[name] = _run_scenario(name, ADVERSARIAL_SEED)
        else:
            cache[name] = _run_scenario(name, DEFAULT_SEEDS[name])
    return cache[name]


def render_network() -> None:
    st.title("網路 — 線上 vacants")
    st.caption("每一個 vacant 的居所形態、能力卡、五維信譽。")
    name = st.selectbox(
        "情境",
        options=sorted(DEFAULT_SEEDS.keys()),
        format_func=_zh_label,
        key="net_scenario",
    )
    result = _ensure_scenario(name)
    rows = []
    for label, meta in result.vacants.items():
        rep = result.reputation.get(label, {})
        rows.append(
            {
                "標籤": label,
                "能力": meta.get("capability", ""),
                "狀態": meta.get("state", ""),
                "F": _round(rep.get("factual", 0.5)),
                "L": _round(rep.get("logical", 0.5)),
                "R": _round(rep.get("relevance", 0.5)),
                "H": _round(rep.get("honesty", 0.5)),
                "A": _round(rep.get("adoption", 0.5)),
            }
        )
    st.dataframe(rows, hide_index=True, width="stretch")
    st.markdown(
        "💡 *halo（公網能力卡）*：每一個 ACTIVE vacant 都會把這張卡簽名後推到 Registry；"
        " LOCAL vacant 保有 halo 但不公佈到索引。"
    )


def render_lineage() -> None:
    st.title("血緣 — Lineage Tree")
    st.caption("Self-replication 路徑（D1/D2/D3/D5）的親代鏈。")
    result = _ensure_scenario("self_replication")
    nodes = []
    for label, meta in result.vacants.items():
        nodes.append(
            {
                "節點": label,
                "vacant_id": meta.get("vacant_id", "")[:12],
                "parent": (meta.get("parent_id") or "—")[:12],
                "path": meta.get("path", "root"),
                "state": meta.get("state", ""),
            }
        )
    st.dataframe(nodes, hide_index=True, width="stretch")
    st.markdown(
        f"血緣深度：**{result.metrics.get('lineage_depth', 0)}** ， "
        f"獨立 keypair 數：**{result.metrics.get('unique_keypairs', 0)}** ， "
        f"D2 子代是否畢業：**{'是' if result.metrics.get('d2_graduated') else '否'}** ， "
        f"STYLO 漂移 epochs：**{result.metrics.get('stylo_drift_epochs', 0)}** ， "
        f"SUNK custody heartbeat：**{'是' if result.metrics.get('sunk_custody_key_in_custody') else '否'}**"
    )
    if result.metrics.get("lineage_continuation_clean_posterior"):
        st.success("血緣延續：D1 個體 stall 後，新的 D1' 子代以乾淨先驗開始（§4.3）。")


def render_scenario() -> None:
    st.title("情境跑流程 — Run a Scenario")
    name = st.selectbox(
        "選擇情境",
        options=sorted(DEFAULT_SEEDS.keys()),
        format_func=_zh_label,
        key="run_scenario",
    )
    seed = st.number_input("種子", value=DEFAULT_SEEDS[name], step=1, format="%d")
    if st.button("執行"):
        with st.spinner("跑情境中…"):
            result = _run_scenario(name, int(seed))
            st.session_state["scenario_results"][name] = result
        st.success("已完成。")
    result = st.session_state["scenario_results"].get(name)
    if result is None:
        return
    st.subheader("事件串流")
    st.dataframe(result.events[:50], hide_index=True, width="stretch")
    st.subheader("結果指標")
    st.json(result.metrics)
    st.subheader("logbook 鏈完整性")
    st.metric("verify_chain", "✅ 通過" if result.logbook_chains_ok else "❌ 失敗")


def render_metrics() -> None:
    st.title("指標 — 8 Metrics")
    st.caption("依 dispatch/P7_mvp.md §3 列舉。每一個指標附上 30-tick 時間序列。")
    name = st.selectbox(
        "情境",
        options=sorted(DEFAULT_SEEDS.keys()),
        format_func=_zh_label,
        key="metrics_scenario",
    )
    result = _ensure_scenario(name)

    # B2: build a real MetricsSnapshot from the scenario's aggregator
    # state so the 8 metrics aren't computed on an empty input.
    snap = _snapshot_from_result(result)
    values = compute_all(snap)

    cols = st.columns(2)
    for i, name_ in enumerate(METRIC_NAMES):
        col = cols[i % 2]
        key = name_ if name_ != "dispatch_p99_latency" else "dispatch_p99_latency_ms"
        key = key if key != "signature_verify_throughput" else "signature_verify_throughput_per_s"
        key = key if key != "registry_consistency_under_concurrency" else "registry_consistency_pct"
        v = values.get(key, "—")
        col.metric(label=_zh_metric(name_), value=str(v)[:64])

    # B2: time series rendered from demo_store metric events.
    st.subheader("時間序列（demo store）")
    series_metric = st.selectbox(
        "指標",
        options=[
            "reputation_distribution",
            "lineage_depth_distribution",
        ],
        key="series_metric",
    )
    pts = _store().metric_series(name, series_metric)
    if pts:
        # Normalise nested-dict metric values to a dataframe for plotting.
        if isinstance(pts[0][1], dict):
            rows = []
            for ts, val in pts:
                row = {"ts": ts}
                row.update(
                    {k: float(v) if isinstance(v, int | float) else 0.0 for k, v in val.items()}
                )
                rows.append(row)
            st.line_chart(rows, x="ts")
        else:
            st.line_chart({"ts": [t for t, _ in pts], "value": [v for _, v in pts]}, x="ts")
    else:
        st.caption("（demo store 還沒有此指標的時間序列；先執行情境。）")


def render_adversarial() -> None:
    st.title("對抗檢測 — Adversarial (seed=666)")
    st.caption(
        "依 dispatch/P7_demo_seed.md §對抗 seed=666 設定：10 個 ACTIVE vacant，"
        "其中 4 個共享 controller_id（環）、6 個獨立。環互推高分；獨立各自誠實。"
        "本頁示範同控制者偵測，並重申『提高成本而非阻止』（CLAUDE.md §Same-* detection）。"
    )
    result = _ensure_scenario("adversarial")
    m = result.metrics

    cols = st.columns(3)
    cols[0].metric(
        "環同控制者信號強度",
        f"{m.get('ring_signal_strength', 0.0):.2f}",
        f"門檻 {adversarial.RING_SIGNAL_THRESHOLD:.2f}",
    )
    cols[1].metric(
        "環內審權重 / 獨立審權重",
        f"{m.get('ring_weight_per_review', 0.0):.4f} / {m.get('indep_weight_per_review', 0.0):.4f}",
        "≤ 0.5 即達標",
    )
    cols[2].metric(
        "環在前 6 名次中的數量",
        f"{m.get('n_ring_in_top_indep', 0)}",
        "(≤ 1 即達標)",
    )

    st.markdown("---")
    cols = st.columns(2)
    cols[0].metric(
        "環平均 n_eff (factual)",
        f"{m.get('ring_avg_n_eff_factual', 0.0):.2f}",
    )
    cols[1].metric(
        "獨立平均 n_eff (factual)",
        f"{m.get('indep_avg_n_eff_factual', 0.0):.2f}",
    )

    st.subheader("最終排名（UCB）")
    rank_rows = []
    for rank_idx, vid_short in enumerate(m.get("final_ranking", [])):
        is_ring = any(
            vid_short == meta.get("vacant_id", "")[:8] and meta.get("is_ring", False)
            for meta in result.vacants.values()
        )
        rank_rows.append(
            {"#": rank_idx + 1, "vacant_id": vid_short, "ring?": "是" if is_ring else "否"}
        )
    st.dataframe(rank_rows, hide_index=True, width="stretch")

    st.markdown(
        "**解讀**：環的 same-controller 信號被 `same_controller(...)` 真實計算出來"
        "（不是 hardcode）。在 aggregator 中，環內互審的有效權重被乘以"
        "`(1 - max(strength))`，但保留一個 **floor**（D015 §A）—— "
        "**這個系統不阻止造假；它讓造假的成本上升**。"
        "攻擊者可以付得起一次身份新陳代謝的代價，但每多一次都是真實成本。"
    )


def _snapshot_from_result(result: Any) -> MetricsSnapshot:
    """Build a MetricsSnapshot that the 8 P7 metrics can compute from.

    The scenario's `vacants` payload is mapped into the snapshot's
    expected shape. `aggregator` is left as None for now since the
    scenario doesn't expose the live Aggregator object — the
    reputation_distribution metric reads from `result.reputation`
    instead via an override below.
    """
    vacants_in: dict[Any, dict[str, Any]] = {}
    from vacant.core.types import VacantId

    def _vid(h: str | None) -> VacantId | None:
        if not h:
            return None
        try:
            return VacantId(pubkey_bytes=bytes.fromhex(h))
        except Exception:
            return None

    for _label, meta in result.vacants.items():
        vid = _vid(meta.get("vacant_id"))
        if vid is None:
            continue
        vacants_in[vid] = {
            "state": meta.get("state", "ACTIVE"),
            "parent_id": _vid(meta.get("parent_id")),
            "n_calls": int(meta.get("n_calls", 1)),
            "is_composite": meta.get("is_composite", False),
        }
    return MetricsSnapshot(
        aggregator=None,
        vacants=vacants_in,
        graduations=(float(result.metrics.get("d2_graduated_at", 0.0)),)
        if result.metrics.get("d2_graduated")
        else (),
    )


def _round(x: Any, digits: int = 3) -> Any:
    try:
        return round(float(x), digits)
    except (TypeError, ValueError):
        return x


def _zh_label(name: str) -> str:
    return {
        "law_firm": "法律問答（複合 vacant）",
        "code_review": "代碼審查（多 vacant 競爭）",
        "multilingual_translation": "多語翻譯（跨基底）",
        "self_replication": "自我複製（血緣 + 畢業）",
        "adversarial": "對抗（環互推）",
    }.get(name, name)


def _zh_metric(name: str) -> str:
    return {
        "reputation_distribution": "信譽分佈（per dim）",
        "cold_start_uplift": "新人上線比例",
        "same_controller_detection_rate": "同控制者偵測率",
        "lineage_depth_distribution": "血緣深度分佈",
        "graduation_rate": "畢業率（per parent / 24h）",
        "dispatch_p99_latency": "派工 p99 延遲 (ms)",
        "signature_verify_throughput": "簽章驗證吞吐 (per s)",
        "registry_consistency_under_concurrency": "Registry 寫入一致率 (%)",
    }.get(name, name)


PAGES = {
    "網路": render_network,
    "血緣": render_lineage,
    "情境": render_scenario,
    "指標": render_metrics,
    "對抗": render_adversarial,
}


def main() -> None:
    page = st.sidebar.radio("頁面", list(PAGES.keys()))
    st.sidebar.markdown("---")
    st.sidebar.caption("Vacant 居所層 MVP — P7 demo")
    PAGES[page]()


main()
