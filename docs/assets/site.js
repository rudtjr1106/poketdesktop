/* 안내서: 지금 읽는 장의 탭에 금색을 칠하고, 찾기 칸에 적은 말이 든 대목만 남긴다.
   첫 화면에는 탭도 찾기 칸도 없어서 아무 일도 하지 않는다. */
(function () {
  var tabs = Array.prototype.slice.call(document.querySelectorAll(".tabs a"));
  var secs = Array.prototype.slice.call(document.querySelectorAll(".guide section"));
  if (!tabs.length || !secs.length) { return; }

  function paint(id) {
    tabs.forEach(function (a) {
      var on = a.getAttribute("href") === "#" + id;
      a.classList.toggle("on", on);
      if (on) {
        var box = a.parentNode, l = a.offsetLeft, r = l + a.offsetWidth;
        if (l < box.scrollLeft || r > box.scrollLeft + box.clientWidth) { box.scrollLeft = l - 16; }
      }
    });
  }
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { paint(e.target.id); } });
    }, { rootMargin: "-35% 0px -60% 0px" });
    secs.forEach(function (s) { io.observe(s); });
  }
  paint((location.hash || "#start").slice(1));

  var q = document.getElementById("q"), found = document.getElementById("found");
  var head = document.querySelector(".guide-head");
  function norm(s) { return (s || "").toLowerCase().replace(/\s+/g, ""); }
  function run() {
    var want = norm(q.value), hits = 0;
    secs.forEach(function (sec) {
      var any = false;
      Array.prototype.forEach.call(sec.querySelectorAll(".blk"), function (b) {
        var ok = !want || norm(b.textContent).indexOf(want) >= 0;
        b.hidden = !ok;
        if (ok) { any = true; if (want) { hits += 1; } }
        Array.prototype.forEach.call(b.querySelectorAll("details"), function (d) {
          var dk = !!want && norm(d.textContent).indexOf(want) >= 0;
          d.hidden = !!want && !dk;
          d.open = dk;
        });
      });
      var h = sec.querySelector(".sec-head");
      if (want && h && norm(h.textContent).indexOf(want) >= 0) { any = true; }
      sec.hidden = !any;
    });
    if (head) { head.hidden = !!want; }
    found.hidden = !want;
    if (want) {
      var word = q.value.trim();
      found.textContent = hits
        ? "'" + word + "' 이(가) 들어 있는 대목 " + hits + "곳"
        : "'" + word + "' 이(가) 들어 있는 대목이 없습니다. 다른 말로 찾아 보세요.";
    }
  }
  if (q && found) { q.addEventListener("input", run); }
})();
