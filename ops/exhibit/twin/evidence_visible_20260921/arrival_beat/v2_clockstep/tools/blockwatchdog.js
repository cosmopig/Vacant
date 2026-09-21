// 量具的權宜，**不是產品行為**。
//
// `index.html` 最後那個 setInterval 看門狗在「10 秒沒有新 frame」時 `location.reload()`。
// 在展場那是對的（畫面凍住要自己救回來）；但在這台 load 600 的 Mac 上，
// headless 被餓到 1 fps 就會誤觸發，而重載會把 Playwright 的執行環境炸掉
// （`Execution context was destroyed`）——`S03_negctl_arrive0` 與 `S05_before_triple`
// 兩次都是這樣死的。
//
// ⚠ **舊招（覆寫 `location.reload`）是空操作**：`Location` 的屬性在 HTML 規格裡是
//   `[LegacyUnforgeable]`，`Object.defineProperty` 直接丟 TypeError，而那一段被
//   `try/catch` 吞掉 ⇒ 看門狗照樣重載。證據見 `t_reload.py` 的輸出。
//
// 新招改成在**上游**攔：認出那一支 setInterval 回呼（原始碼含 `vw_reloads`，
// 全檔唯一），換成一個判準一模一樣、但**記一筆而不是重載**的替身。
//
// 🔴 這一招會讓「它想重載幾次」變成可量的數字（`__watchdogWouldFire`），
//    而不是安靜消失。量測期間它開過槍，就代表那一跑的畫面真的凍過——
//    那是「這台機器有多不適合量這個」的證據，不准當成沒發生。
window.__watchdogArmed = 0;        // 認出並換掉了幾支看門狗（正常＝1）
window.__watchdogWouldFire = 0;    // 換掉之後，它本來會重載幾次（**下界**，見下）
window.__otherIntervals = 0;       // 其他 setInterval，原樣放行
window.__maxFrameGapMs = 0;        // 這一跑最長掉了幾毫秒沒畫（替身自己的 rAF 量的）
(function () {
  // 替身的 rAF 監看**從頁面一載入就開始**，不等看門狗被裝上來：
  // `__maxFrameGapMs` 要涵蓋暖機那一段（最容易凍的就是那一段）。
  let lastFrameTs = performance.now();
  const raf = window.requestAnimationFrame.bind(window);
  (function watch() {
    const g = performance.now() - lastFrameTs;
    if (g > window.__maxFrameGapMs) window.__maxFrameGapMs = Math.round(g);
    lastFrameTs = performance.now();
    raf(watch);
  })();

  const si = window.setInterval.bind(window);
  window.setInterval = function (fn, ms) {
    let src = "";
    try { src = (typeof fn === "function") ? Function.prototype.toString.call(fn) : ""; } catch (e) {}
    if (src.indexOf("vw_reloads") < 0) { window.__otherIntervals++; return si.apply(null, arguments); }
    window.__watchdogArmed++;
    // 判準與原版逐字相同（`document.hidden` 那條短路也照抄），只是**記一筆而不是重載**。
    //
    // ⚠ `__watchdogWouldFire` 是**下界，不是「原版會開幾槍」的複製**。
    //   替身的時間戳由替身自己的 rAF 更新，原版的由頁面主迴圈更新；解凍時
    //   排隊的 rAF 與 setInterval 誰先跑不保證 ⇒ 兩邊看到的缺口不一定一樣。
    //   要判「這一跑的畫面有沒有凍過」，看 `__maxFrameGapMs` 比看這個準。
    return si(function () {
      if (document.hidden) { lastFrameTs = performance.now(); return; }
      if (performance.now() - lastFrameTs > 10000) {
        window.__watchdogWouldFire++;
        lastFrameTs = performance.now();
      }
    }, ms);
  };
})();
