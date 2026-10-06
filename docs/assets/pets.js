/* 풀밭을 걸어다니는 도트와 풀숲. 직접 그린 생물이다 (tools/make_site_sprites.py 가 시트를 만든다).

   시트: 한 칸 16x16, 가로 = 프레임 4장. 생물 하나가 4줄(아래·오른쪽·위·왼쪽), 생물을 세로로
   이어 붙이고 맨 아래 한 줄이 풀숲이다 [풀숲 1, 풀숲 2, 꽃 핀 풀숲 1, 꽃 핀 풀숲 2].

   게임과 같은 흐름이다: 가끔 풀숲이 돋고, 누르면 새 도트가 튀어나와 걸어다닌다. 꽃 핀 풀숲에서는
   금빛 조약돌이 나온다. 화면에 보일 때만 돌고, '움직임 줄이기' 를 켠 사람에게는 서 있는 모습만 보인다.

   **크기와 그림은 여기서 직접 입힌다.** 스타일 파일이 옛것으로 남아 있는 브라우저에서도(새로 고친
   직후의 캐시) 도트가 보여야 한다. */
(function () {
  var field = document.querySelector(".meadow");
  if (!field) { return; }

  var CELL = 16, SCALE = 3, SIZE = CELL * SCALE, FRAMES = 4;
  var KINDS = 12;                    // 시트에 든 생물 수. 마지막은 금빛 조약돌이다
  var GOLD = KINDS - 1, TUFT_ROW = KINDS * 4;
  var MAX = 8;                       // 이보다 많아지면 가장 오래된 도트가 풀밭 밖으로 걸어 나간다 (좁으면 5)
  var ROW = { down: 0, right: 1, up: 2, left: 3 };
  var me = document.currentScript;
  var SHEET = "sprites/critters.png";
  try { SHEET = new URL("../sprites/critters.png?v=3", me && me.src ? me.src : location.href).href; } catch (e) { /* 그대로 쓴다 */ }

  var still = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var pets = [], tuft = null, untilTuft = 3, W = 0, H = 0, last = 0, raf = 0, seen = true;

  function rnd(a, b) { return a + Math.random() * (b - a); }
  function pick(n) { return Math.floor(Math.random() * n); }

  // 풀밭 자체: 스타일이 안 먹었어도 자리를 잡는다
  if (getComputedStyle(field).position === "static") { field.style.position = "relative"; }
  field.style.overflow = "hidden";
  if (field.clientHeight < 60) { field.style.height = "120px"; }
  function measure() { W = Math.max(SIZE, field.clientWidth); H = Math.max(SIZE + 8, field.clientHeight); }

  function holder(tag) {             // 도트 하나가 놓이는 칸
    var el = document.createElement(tag), body = document.createElement("i");
    var s = el.style, b = body.style;
    s.position = "absolute"; s.left = "0"; s.top = "0"; s.width = SIZE + "px"; s.height = SIZE + "px";
    s.cursor = "pointer"; s.padding = "0"; s.border = "0"; s.background = "none";
    b.display = "block"; b.width = "100%"; b.height = "100%";
    b.backgroundImage = "url(\"" + SHEET + "\")";
    b.backgroundRepeat = "no-repeat";
    b.backgroundSize = (CELL * FRAMES * SCALE) + "px " + ((TUFT_ROW + 1) * SIZE) + "px";
    b.imageRendering = "pixelated";
    el.appendChild(body);
    field.appendChild(el);
    return { el: el, body: body };
  }
  function place(o, col, row) {
    o.el.style.transform = "translate3d(" + Math.round(o.x) + "px," + Math.round(o.y) + "px,0)";
    o.el.style.zIndex = String(Math.round(o.y));          // 아래에 선 쪽이 앞에 보인다
    o.body.style.backgroundPosition = (-col * SIZE) + "px " + (-row * SIZE) + "px";
  }
  function hop(el) {
    el.classList.remove("hop");
    void el.offsetWidth;
    el.classList.add("hop");
  }

  // ---------------- 도트 ----------------
  function aim(p) {                  // 다음에 갈 곳
    p.tx = rnd(0, W - SIZE);
    p.ty = rnd(0, H - SIZE - 6);
    p.speed = rnd(16, 30);
  }
  function draw(p) { place(p, p.frame, p.kind * 4 + ROW[p.dir]); }
  function spawn(kind, x, y) {
    var h = holder("span");
    h.el.className = "pet";
    h.el.setAttribute("aria-hidden", "true");
    var p = { el: h.el, body: h.body, kind: kind, frame: 0, ft: 0, dir: "down", x: x, y: y,
              wait: rnd(0.3, 2.2), leave: false };
    aim(p);
    h.el.addEventListener("click", function () {          // 누르면 이쪽을 보고 폴짝 뛴다
      p.wait = 1.3; p.dir = "down"; p.frame = 0;
      hop(h.el);
      draw(p);
    });
    pets.push(p);
    draw(p);
    var staying = pets.filter(function (q) { return !q.leave; });
    if (staying.length > (W < 520 ? 5 : MAX)) { send(staying[0]); }     // 가장 오래된 도트를 내보낸다
    return p;
  }
  function send(p) {
    p.leave = true; p.wait = 0; p.speed = 60;
    p.tx = p.x < W / 2 ? -SIZE - 4 : W + 4;
    p.ty = p.y;
    if (still) { gone(p); }
  }
  function gone(p) {
    var i = pets.indexOf(p);
    if (i >= 0) { pets.splice(i, 1); }
    if (p.el.parentNode) { p.el.parentNode.removeChild(p.el); }
  }
  function step(p, dt) {
    if (p.wait > 0) {
      p.wait -= dt;
      if (p.wait <= 0) { aim(p); }
      return;
    }
    var dx = p.tx - p.x, dy = p.ty - p.y, d = Math.sqrt(dx * dx + dy * dy);
    if (d < 2) {
      if (p.leave) { return gone(p); }
      p.wait = rnd(0.8, 3.2); p.dir = "down"; p.frame = 0;      // 다 왔다 - 잠깐 서서 앞을 본다
      return;
    }
    var go = Math.min(d, p.speed * dt);
    p.x += dx / d * go;
    p.y += dy / d * go;
    p.dir = Math.abs(dx) >= Math.abs(dy) ? (dx > 0 ? "right" : "left") : (dy > 0 ? "down" : "up");
    p.ft += dt;
    if (p.ft > 0.16) { p.ft = 0; p.frame = (p.frame + 1) % FRAMES; }
  }

  // ---------------- 풀숲 ----------------
  function sprout() {
    var h = holder("button");
    h.el.type = "button";
    h.el.className = "tuft";
    var flower = Math.random() < 0.18;
    h.el.setAttribute("aria-label", flower ? "꽃이 핀 풀숲. 누르면 도트가 나옵니다" : "풀숲. 누르면 도트가 나옵니다");
    tuft = { el: h.el, body: h.body, flower: flower, age: 0, sway: 0,
             x: rnd(8, Math.max(9, W - SIZE - 8)), y: rnd(2, Math.max(3, H - SIZE - 8)) };
    h.el.addEventListener("click", open);
    paint();
  }
  function paint() { place(tuft, (tuft.flower ? 2 : 0) + tuft.sway, TUFT_ROW); }
  function clear() {
    if (tuft && tuft.el.parentNode) { tuft.el.parentNode.removeChild(tuft.el); }
    tuft = null;
  }
  function open() {                  // 풀숲을 눌렀다: 도트가 튀어나온다
    if (!tuft) { return; }
    var t = tuft;
    clear();
    var p = spawn(t.flower ? GOLD : pick(GOLD), t.x, t.y);
    p.wait = 1.1;
    hop(p.el);
    untilTuft = rnd(6, 12);
    if (still) { sprout(); }         // 시계가 돌지 않으니 바로 다음 풀숲을 둔다
  }

  // ---------------- 돌리기 ----------------
  function tick(now) {
    raf = 0;
    var dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    for (var i = pets.length - 1; i >= 0; i--) {
      var p = pets[i];
      step(p, dt);
      if (pets[i] === p) { draw(p); }
    }
    if (tuft) {
      tuft.age += dt;
      var s = Math.floor(tuft.age / 0.5) % 2;
      if (s !== tuft.sway) { tuft.sway = s; paint(); }
      if (tuft.age > 24) { clear(); untilTuft = rnd(5, 10); }      // 아무도 안 누르면 시든다
    } else {
      untilTuft -= dt;
      if (untilTuft <= 0) { sprout(); }
    }
    run();
  }
  function run() {
    if (!raf && seen && !still && !document.hidden) {
      last = performance.now();
      raf = requestAnimationFrame(tick);
    }
  }

  measure();
  var n = W < 520 ? 3 : 5, start = [];
  while (start.length < n) {                              // 처음 나와 있는 도트는 서로 다른 종으로
    var k = pick(GOLD);
    if (start.indexOf(k) < 0) { start.push(k); }
  }
  for (var i = 0; i < n; i++) {
    spawn(start[i], (W - SIZE) * (i + 0.5) / n, rnd(4, Math.max(5, H - SIZE - 8)));
  }
  if (still) { sprout(); }

  window.addEventListener("resize", function () {
    measure();
    pets.forEach(function (p) {
      p.x = Math.min(p.x, W - SIZE); p.y = Math.min(p.y, H - SIZE - 6);
      if (!p.leave) { aim(p); }
      draw(p);
    });
    if (tuft) { tuft.x = Math.min(tuft.x, W - SIZE - 8); paint(); }
  });
  document.addEventListener("visibilitychange", run);
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (es) { seen = es[0].isIntersecting; run(); }).observe(field);
  }
  run();
})();
