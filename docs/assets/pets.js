/* 풀밭을 걸어다니는 도트. 직접 그린 생물이다 (tools/make_site_sprites.py 가 시트를 만든다).
   시트: 한 칸 16x16, 가로 = 프레임 4장, 세로 = 방향 4줄(아래·오른쪽·위·왼쪽) x 생물 셋.
   화면에 보일 때만 돌고, '움직임 줄이기' 를 켠 사람에게는 서 있는 모습만 보인다. */
(function () {
  var field = document.querySelector(".meadow");
  if (!field) { return; }
  var CELL = 16, SCALE = 3, SIZE = CELL * SCALE, FRAMES = 4, KINDS = 3;
  var ROW = { down: 0, right: 1, up: 2, left: 3 };
  var still = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var pets = [], W = 0, H = 0, last = 0, raf = 0, seen = true;

  function rnd(a, b) { return a + Math.random() * (b - a); }
  function measure() { W = Math.max(SIZE, field.clientWidth); H = Math.max(SIZE, field.clientHeight); }

  function aim(p) {                        // 다음에 갈 곳을 정한다
    p.tx = rnd(0, W - SIZE);
    p.ty = rnd(0, H - SIZE - 6);
    p.speed = rnd(16, 30);
  }
  function draw(p) {
    p.el.style.transform = "translate3d(" + Math.round(p.x) + "px," + Math.round(p.y) + "px,0)";
    p.el.style.zIndex = String(Math.round(p.y));          // 아래에 선 쪽이 앞에 보인다
    p.body.style.backgroundPosition = (-p.frame * SIZE) + "px " + (-(p.kind * 4 + ROW[p.dir]) * SIZE) + "px";
  }
  function make(i, n) {
    var el = document.createElement("span"), body = document.createElement("i");
    el.className = "pet";
    el.appendChild(body);
    field.appendChild(el);
    var p = { el: el, body: body, kind: i % KINDS, frame: 0, ft: 0, dir: "down",
              x: (W - SIZE) * (i + 0.5) / n, y: rnd(4, Math.max(5, H - SIZE - 8)), wait: rnd(0.2, 2.2) };
    aim(p);
    el.addEventListener("click", function () {            // 누르면 이쪽을 보고 폴짝 뛴다
      p.wait = 1.3; p.dir = "down"; p.frame = 0;
      el.classList.remove("hop");
      void el.offsetWidth;
      el.classList.add("hop");
      draw(p);
    });
    draw(p);
    return p;
  }

  function step(p, dt) {
    if (p.wait > 0) {
      p.wait -= dt;
      if (p.wait <= 0) { aim(p); }
      return;
    }
    var dx = p.tx - p.x, dy = p.ty - p.y, d = Math.sqrt(dx * dx + dy * dy);
    if (d < 2) {                                          // 다 왔다 - 잠깐 서서 앞을 본다
      p.wait = rnd(0.8, 3.2); p.dir = "down"; p.frame = 0;
      return;
    }
    var go = Math.min(d, p.speed * dt);
    p.x += dx / d * go;
    p.y += dy / d * go;
    p.dir = Math.abs(dx) >= Math.abs(dy) ? (dx > 0 ? "right" : "left") : (dy > 0 ? "down" : "up");
    p.ft += dt;
    if (p.ft > 0.16) { p.ft = 0; p.frame = (p.frame + 1) % FRAMES; }
  }

  function tick(now) {
    raf = 0;
    var dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    for (var i = 0; i < pets.length; i++) { step(pets[i], dt); draw(pets[i]); }
    run();
  }
  function run() {
    if (!raf && seen && !still && !document.hidden) {
      last = performance.now();
      raf = requestAnimationFrame(tick);
    }
  }

  measure();
  var n = W < 520 ? 3 : 5;
  for (var i = 0; i < n; i++) { pets.push(make(i, n)); }

  window.addEventListener("resize", function () {
    measure();
    pets.forEach(function (p) {
      p.x = Math.min(p.x, W - SIZE); p.y = Math.min(p.y, H - SIZE - 6); aim(p); draw(p);
    });
  });
  document.addEventListener("visibilitychange", run);
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (es) { seen = es[0].isIntersecting; run(); }).observe(field);
  }
  run();
})();
