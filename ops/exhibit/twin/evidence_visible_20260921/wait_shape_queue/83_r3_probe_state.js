/* 只讀：把「現在誰在等、誰在排隊」印出來。不碰任何狀態。 */
(() => {
  const w = director.wait;
  return JSON.stringify({
    mode: director.mode,
    waiting: w ? { id: w.id, phase: w.phase, stage: w.stage,
                   elapsed: +((performance.now() - w.startedAt) / 1000).toFixed(1) } : null,
    backlog: (typeof waitBacklog !== "undefined") ? waitBacklog.map(s => s.id) : "undefined",
    spawnQueue: spawnQueue.length,
    arrivalsWaiting: (typeof arrivals !== "undefined" && arrivals.waiting)
      ? arrivals.waiting.map(a => a.label) : null,
    marks: (typeof marklayer !== "undefined" && marklayer.retiring)
      ? { live: marklayer.live() ? (marklayer.live().tok || {}).word : null,
          retiring: marklayer.retiring.length } : null,
  });
})()
