// 退化外觀：**跑的是產品裡同一行**（`waitResolverTick` 讀到
// engine==="fallback_deterministic" 時就是這兩行），只是用 CDP 直接觸發，
// 因為演練模式沒有真的來源可讀。
(() => {
  const w = director.wait;
  if (!w) return "no-wait";
  w.sub = { id: w.id, card: w.card, twin: {
    arrival: null, working: null, handover: null,
    engine: "fallback_deterministic", status: "submitted" } };
  w.degraded = true;
  w.rgb = clayRgbFor(w.img, w.card, true);
  return "degraded=" + w.degraded + " rgb=" + JSON.stringify(w.rgb);
})();
