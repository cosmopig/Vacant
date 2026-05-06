"""Streamlit dashboard for the P7 demo.

Run with: `uv run streamlit run src/vacant/mvp/dashboard.py`.

Pages:
- 網路 (Network) -- list of vacants with state, capability, mean
  reputation per dim.
- 血緣 (Lineage) -- parent_id chain visualisation.
- Scenario -- pick + run; events stream.
- 指標 (Metrics) -- 8 metrics, time-series.
- 對抗 (Adversarial) -- adversarial set with detection rates.

User-facing text is in 繁體中文 per CLAUDE.md.
"""

from __future__ import annotations

import asyncio
from typing import Any

import streamlit as st

from vacant.mvp.metrics import METRIC_NAMES, MetricsSnapshot, compute_all
from vacant.mvp.scenarios import DEFAULT_SEEDS, get_runner
from vacant.substrate import MockSubstrate

st.set_page_config(page_title="Vacant 居所層 Demo", layout="wide")

# Session state for caching scenario runs.
if "scenario_results" not in st.session_state:
    st.session_state["scenario_results"] = {}


def _run_scenario(name: str, seed: int) -> Any:
    runner = get_runner(name)
    substrate = MockSubstrate(seed=seed)

    async def _go() -> Any:
        return await runner(substrate=substrate, seed=seed)

    return asyncio.run(_go())


def _ensure_scenario(name: str) -> Any:
    cache = st.session_state["scenario_results"]
    if name not in cache:
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
        f"D2 子代是否畢業：**{'是' if result.metrics.get('d2_graduated') else '否'}**"
    )


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
    st.caption("依 dispatch/P7_mvp.md §3 列舉。")
    name = st.selectbox(
        "情境",
        options=sorted(DEFAULT_SEEDS.keys()),
        format_func=_zh_label,
        key="metrics_scenario",
    )
    result = _ensure_scenario(name)
    snap = MetricsSnapshot(
        aggregator=None,
        vacants={},
        graduations=(),
    )
    values = compute_all(snap)
    # Override the reputation distribution from the scenario's reputation.
    rep_means = {dim: 0.0 for dim in ("factual", "logical", "relevance", "honesty", "adoption")}
    counts = dict.fromkeys(rep_means, 0)
    for rep in result.reputation.values():
        for dim, mu in rep.items():
            base_dim = dim.split("/", maxsplit=1)[-1]
            if base_dim in rep_means:
                rep_means[base_dim] += float(mu)
                counts[base_dim] += 1
    for dim in rep_means:
        if counts[dim]:
            rep_means[dim] /= counts[dim]
    values["reputation_distribution"] = {f"mean_{k}": v for k, v in rep_means.items()}

    cols = st.columns(2)
    for i, name_ in enumerate(METRIC_NAMES):
        col = cols[i % 2]
        key = name_ if name_ != "dispatch_p99_latency" else "dispatch_p99_latency_ms"
        key = key if key != "signature_verify_throughput" else "signature_verify_throughput_per_s"
        key = key if key != "registry_consistency_under_concurrency" else "registry_consistency_pct"
        v = values.get(key, "—")
        col.metric(label=_zh_metric(name_), value=str(v)[:64])


def render_adversarial() -> None:
    st.title("對抗檢測 — Adversarial")
    st.caption(
        "這頁示範 same-controller / same-substrate / same-stylo 的偵測率，"
        "並重申『提高成本而非阻止』的設計取捨（CLAUDE.md §Same-* detection）。"
    )
    # Rerun code_review which carries the ring-downweight test.
    result = _ensure_scenario("code_review")
    bump_with = result.metrics.get("ring_signal_bump", 0.0)
    bump_without = result.metrics.get("unflagged_bump", 0.0)
    tp_rate = result.metrics.get("same_controller_tp_rate", 0.0)
    fp_rate = result.metrics.get("same_controller_fp_rate", 0.0)
    rationale = result.metrics.get("ring_signal_rationale", "")
    ring_strength = result.metrics.get("ring_signal_strength", 0.0)
    st.metric("環路被檢出 → 加權後信號", f"{bump_with:+.4f}")
    st.metric("未被檢出 → 加權後信號", f"{bump_without:+.4f}")
    cols = st.columns(2)
    cols[0].metric("same_controller TP rate (seeded ring)", f"{tp_rate:.2f}")
    cols[1].metric("same_controller FP rate (control)", f"{fp_rate:.2f}")
    st.metric("偵測強度（colluding pair）", f"{ring_strength:.2f}")
    if rationale:
        st.caption(f"偵測器理由：{rationale}")
    st.write(
        "解讀：信號由 `same_controller(...)` 真實跑出來（不是 hardcode）。"
        "被偵測到的 review 仍保留 D015 §A 規定的最低權重 floor —— "
        "**這個系統不阻止造假；它讓造假的成本上升**——攻擊者必須持續支付"
        "身份新陳代謝的代價，但不會因為一次偵測命中而被永久封口。"
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
