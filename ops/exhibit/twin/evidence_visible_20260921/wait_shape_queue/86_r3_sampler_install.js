/* 只讀取樣器：每 250ms 記一次「誰擋著 backlog」。狀態變了才記一筆。
   判成「卡住」之前先證明量得動 ⇒ 這一支要能指出是哪一個條件為真。 */
(() => {
  window.__s = [];
  const t0 = performance.now();
  let prev = "";
  window.__siv = setInterval(() => {
    const st = {
      hold: (typeof arrivals !== "undefined") ? !!arrivals.holding() : null,
      holdT: (typeof arrivals !== "undefined") ? +(arrivals.holdT || 0).toFixed(2) : null,
      visitor: !!director.visitor,
      wait: director.wait ? director.wait.id : null,
      mode: director.mode,
      backlog: (typeof waitBacklog !== "undefined") ? waitBacklog.length : null,
      spawnQ: spawnQueue.length,
    };
    const key = [st.hold, st.visitor, st.wait, st.mode, st.backlog, st.spawnQ].join("|");
    if (key !== prev) {
      prev = key;
      st.t = +((performance.now() - t0) / 1000).toFixed(2);
      window.__s.push(st);
    }
  }, 250);
  return "sampler on";
})()
