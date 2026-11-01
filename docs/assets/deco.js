/* 안내서 '꾸미기' 장의 입혀 보기 무대. 사이트의 직접 그린 생물이 장식을 쓰고 걸어다닌다.

   그림(sprites/deco.png)과 장식 자리(deco-data.js)는 tools/make_site_deco.py 가 게임 것 그대로 만든다.
   효과(별가루 · 꽃잎 · 하트 · 발자국 · 발밑 빛)는 게임의 deco_fx 와 같은 수로 흉내 낸다: 만드는 간격, 사는 시간,
   흘러가는 빠르기, 옅어지기 시작하는 때. 생물은 6배(좁은 화면은 4배), 장식 · 효과는 그 절반으로 그린다 (게임과 같은 2:1).

   단추(.deco-chip)와 묶음(.deco-set)은 HTML 에 있다. 이 스크립트가 없으면 무대는 숨은 채로 남는다.
   화면에 보일 때만 돌고, '움직임 줄이기' 를 켠 사람에게는 걷던 한순간을 멈춰 보여 준다. */
(function () {
  var root = document.querySelector("[data-deco]");
  var D = window.DECO_DATA;
  if (!root || !D) { return; }
  var canvas = root.querySelector("canvas");
  var ctx = canvas && canvas.getContext && canvas.getContext("2d");
  if (!ctx) { return; }

  var CELL = D.cell, SC = 6, K = 3, SIZE = CELL * SC;
  var ROW = { down: 0, right: 1, up: 2, left: 3 };
  var SLOT = { crown_gold: "head", crown_silver: "head", crown_bronze: "head", bow: "hair", flower: "hair",
               pearls: "neck", fx_stars_gold: "trail", fx_stars_silver: "trail", fx_stars_bronze: "trail",
               fx_paw: "trail", fx_petals: "trail", fx_hearts: "trail", fx_glow: "aura" };
  var SETS = { rank1: ["crown_gold", "fx_stars_gold", "fx_glow"], rank2: ["crown_silver", "fx_stars_silver"],
               rank3: ["crown_bronze", "fx_stars_bronze"], join_bow: ["bow", "fx_paw"],
               join_flower: ["flower", "fx_petals"], join_pearls: ["pearls", "fx_hearts"] };
  var NAME = { crown_gold: "금관", crown_silver: "은관", crown_bronze: "동관", bow: "분홍 리본", flower: "꽃핀",
               pearls: "진주 목걸이", fx_stars_gold: "금빛 별가루", fx_stars_silver: "은빛 별가루",
               fx_stars_bronze: "동빛 별가루", fx_paw: "발자국", fx_petals: "꽃잎", fx_hearts: "하트", fx_glow: "발밑 빛" };
  var me = document.currentScript;
  function url(rel) {
    try { return new URL(rel, me && me.src ? me.src : location.href).href; } catch (e) { return rel; }
  }
  var critters = new Image(), deco = new Image(), ready = 0;
  critters.onload = deco.onload = function () { ready += 1; if (ready === 2) { start(); } };
  critters.src = url("../sprites/critters.png?v=3");
  deco.src = url("../sprites/deco.png?v=1");

  var still = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var wear = {};                     // 칸 -> 열쇠
  var kindIx = 0, W = 0, H = 0, dpr = 1, raf = 0, last = 0, seen = true;
  var pet = { x: 40, y: 120, tx: 40, ty: 120, dir: "down", frame: 0, ft: 0, wait: 1, speed: 34, hop: 0 };
  var fx = { parts: [], walked: 0, back: 0, since: { star: 0, petal: 0, heart: 0 }, side: 0, last: null, t: 0 };

  function rnd(a, b) { return a + Math.random() * (b - a); }
  function kind() { return D.kinds[kindIx]; }

  // ---------------- 그리기
  function blit(name, x, y, k, flip, alpha) {
    var r = D.sprites[name];
    if (!r) { return; }
    var w = r[2] * k, h = r[3] * k;
    x = Math.round(x); y = Math.round(y);
    if (alpha !== undefined && alpha < 1) { ctx.globalAlpha = Math.max(0, alpha); }
    if (flip) {
      ctx.save();
      ctx.translate(x + w, y);
      ctx.scale(-1, 1);
      ctx.drawImage(deco, r[0], r[1], r[2], r[3], 0, 0, w, h);
      ctx.restore();
    } else {
      ctx.drawImage(deco, r[0], r[1], r[2], r[3], x, y, w, h);
    }
    ctx.globalAlpha = 1;
  }
  function fade(f, keep) { return f <= keep ? 1 : Math.max(0, Math.round(16 * (1 - f) / (1 - keep)) / 16); }

  function drawPart(p) {
    var f = p.age / p.life, name, r;
    if (p.kind === "paw") { blit("paw", p.x, p.y, K, false, fade(f, 0.3)); return; }
    if (p.kind === "star") {
      var s = Math.sin(p.tw + p.age / 90) > -0.2 ? p.size : Math.max(1, p.size - 2);
      name = "star" + s + "_" + p.tone; r = D.sprites[name];
      blit(name, p.x - r[2] * K / 2, p.y + p.vy * p.age - r[3] * K / 2, K, false, fade(f, 0.6));
      return;
    }
    if (p.kind === "petal") {
      var xx = p.x + Math.sin(p.ph + p.age / 260) * 4 * K - p.age / 160;
      blit("petal" + ((p.rot + Math.floor(p.age / 180)) % 4), xx, p.y + p.vy * p.age, K, false, fade(f, 0.65));
      return;
    }
    if (p.kind === "heart") {
      r = D.sprites.heartfx;
      var hx = p.x + Math.sin(p.ph + p.age / 200) * 3 * K - r[2] * K / 2;
      blit("heartfx", hx, p.y - p.age / 28, K, false, fade(f, 0.55));
    }
  }

  function at(set) {                 // 지금 방향 · 프레임에서 그 묶음의 자리 (촘촘한 칸)
    var a = kind().at[pet.dir][set];
    return a ? a[pet.frame] : null;
  }

  function draw(now) {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, W, H);
    var k = kind(), box = k.box;
    var hopY = pet.hop > 0 ? -Math.round(Math.sin(Math.PI * (1 - pet.hop / 0.42)) * 14) : 0;
    var x = Math.round(pet.x), y = Math.round(pet.y) + hopY;
    var feetX = x + SIZE / 2, feetY = Math.round(pet.y) + box[3] * SC - 2;

    if (wear.aura) {                 // 발밑 빛: 테가 밝아졌다 어두워졌다
      var ph = Math.round(1.5 + 1.5 * Math.sin(now / 45 / 5)), rr = D.sprites["ring" + ph];
      blit("ring" + ph, feetX - rr[2] * K / 2, feetY - rr[3] * K / 2 + K, K);
    }
    fx.parts.forEach(drawPart);      // 효과는 포켓몬 밑에 깔린다 (게임에서도 제 포켓몬 창 아래)

    var row = k.row + ROW[pet.dir];
    ctx.drawImage(critters, pet.frame * CELL, row * CELL, CELL, CELL, x, y, SIZE, SIZE);

    var p, flip = k.at[pet.dir].flip;
    if (wear.neck && (p = at("pearls"))) {
      p.forEach(function (q) { blit("pearl", x + q[0] * K, y + q[1] * K, K); });
      var h = at("heart");
      blit("heart", x + h[0] * K, y + h[1] * K, K);
    }
    if (wear.head && (p = at("crown"))) { blit(wear.head, x + p[0] * K, y + p[1] * K, K); }
    if (wear.hair && (p = at(wear.hair + (wear.head ? "C" : "")))) {
      blit(wear.hair, x + p[0] * K, y + p[1] * K, K, flip);
    }
    if (wear.head && !still) {       // 왕관이 1.4초마다 한 번 반짝
      var g = Math.floor((now % 1400) / 80);
      if (g >= 1 && g <= 4 && (p = at("glint"))) { blit("glint" + g, x + p[0] * K, y + p[1] * K, K); }
    }
  }

  // ---------------- 걷기
  function measure() {
    var r = canvas.getBoundingClientRect();
    dpr = Math.max(1, Math.min(3, Math.round(window.devicePixelRatio || 1)));
    SC = r.width < 560 ? 4 : 6; K = SC / 2; SIZE = CELL * SC;
    W = Math.max(SIZE * 2, Math.round(r.width));
    H = Math.max(SIZE * 2, Math.round(r.height));
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    pet.x = Math.min(pet.x, W - SIZE); pet.tx = Math.min(pet.tx, W - SIZE);
    pet.y = Math.min(Math.max(pet.y, top()), bottom()); pet.ty = Math.min(Math.max(pet.ty, top()), bottom());
  }
  function top() { return Math.min(SIZE * 1.2, H - SIZE - 24); }          // 위로 하트 · 왕관 자리를 남긴다
  function bottom() { return H - SIZE - 14; }
  function aim() {
    // 옆으로 길게 걷는 편이 효과가 잘 보인다 - 반대편 쪽으로, 높이는 조금만 바꾼다
    var left = pet.x > W / 2;
    pet.tx = left ? rnd(8, Math.max(9, W * 0.3)) : rnd(Math.min(W * 0.62, W - SIZE - 9), W - SIZE - 8);
    pet.ty = rnd(top(), bottom());
    pet.speed = rnd(30, 40);
  }

  function spawn(ms, moved) {
    var k = kind(), box = k.box;
    var x0 = pet.x + box[0] * SC, x1 = pet.x + box[2] * SC, y0 = pet.y + box[1] * SC, y1 = pet.y + box[3] * SC;
    var mid = pet.x + SIZE / 2, half = (x1 - x0) / 2, back = fx.back;
    var fxX = mid, fxY = pet.y + box[3] * SC - 2;
    function behind() { var d = rnd(0, half); return mid + (back ? back * d : (Math.random() < 0.5 ? -d : d)); }
    var key = wear.trail;
    if (key === "fx_paw") {
      fx.walked += moved;
      if (fx.walked >= 13 * K) {
        fx.walked = 0; fx.side ^= 1;
        var side = fx.side ? 2 * K : -2 * K, pw = D.sprites.paw[2] * K;
        fx.parts.push({ kind: "paw", x: fxX - pw / 2 + (back === 0 ? side : 0), y: fxY - 4 * K + (back ? side : 0),
                        life: 2200, age: 0 });
      }
    } else if (key && key.indexOf("fx_stars_") === 0) {
      fx.since.star += ms;
      while (fx.since.star >= 70) {
        fx.since.star -= 70;
        fx.parts.push({ kind: "star", x: behind(), y: rnd(y0 + (y1 - y0) * 0.1, y1 - 2), life: rnd(700, 1500), age: 0,
                        size: [1, 3, 3, 5, 5, 5, 7, 7][Math.floor(Math.random() * 8)], tw: rnd(0, 6.28),
                        vy: rnd(0.004, 0.012), tone: key.slice(9) });
      }
    } else if (key === "fx_petals") {
      fx.since.petal += ms;
      while (fx.since.petal >= 90) {
        fx.since.petal -= 90;
        fx.parts.push({ kind: "petal", x: behind(), y: y0 + rnd(0, (y1 - y0) * 0.4), life: rnd(1300, 1900), age: 0,
                        ph: rnd(0, 6.28), vy: rnd(0.009, 0.015), rot: Math.floor(Math.random() * 4) });
      }
    } else if (key === "fx_hearts") {
      fx.since.heart += ms;
      while (fx.since.heart >= 300) {
        fx.since.heart -= 300;
        fx.parts.push({ kind: "heart", x: mid + rnd(-6, 6) * K, y: y0 - (wear.head ? 14 : 4) * K, life: 1200, age: 0,
                        ph: rnd(0, 6.28) });
      }
    }
    if (fx.parts.length > 90) { fx.parts = fx.parts.slice(-90); }
  }

  function step(dt) {
    var ms = dt * 1000;
    if (pet.hop > 0) { pet.hop = Math.max(0, pet.hop - dt); }
    var ox = pet.x, oy = pet.y;
    if (pet.wait > 0) {
      pet.wait -= dt;
      if (pet.wait <= 0) { aim(); }
    } else {
      var dx = pet.tx - pet.x, dy = pet.ty - pet.y, d = Math.sqrt(dx * dx + dy * dy);
      if (d < 2) {
        pet.wait = rnd(1.0, 2.0); pet.dir = "down"; pet.frame = 0;       // 다 왔다 - 잠깐 서서 앞을 본다
      } else {
        var go = Math.min(d, pet.speed * dt);
        pet.x += dx / d * go; pet.y += dy / d * go;
        pet.dir = Math.abs(dx) >= Math.abs(dy) * 1.6 ? (dx > 0 ? "right" : "left") : (dy > 0 ? "down" : "up");
        pet.ft += dt;
        if (pet.ft > 0.16) { pet.ft = 0; pet.frame = (pet.frame + 1) % D.frames; }
      }
    }
    var mx = pet.x - ox, moved = Math.sqrt(mx * mx + (pet.y - oy) * (pet.y - oy));
    if (moved > 0.3) {
      fx.back = mx > 0.2 ? -1 : (mx < -0.2 ? 1 : 0);
      spawn(ms, moved);
    }
    fx.parts.forEach(function (p) { p.age += ms; });
    fx.parts = fx.parts.filter(function (p) { return p.age < p.life; });
  }

  // ---------------- 고르기
  var chips = Array.prototype.slice.call(root.querySelectorAll(".deco-chip[data-key]"));
  var sets = Array.prototype.slice.call(document.querySelectorAll(".deco-set[data-set]"));
  var say = root.querySelector(".deco-now");
  function paint() {
    chips.forEach(function (b) {
      b.setAttribute("aria-pressed", wear[SLOT[b.getAttribute("data-key")]] === b.getAttribute("data-key") ? "true" : "false");
    });
    sets.forEach(function (b) {
      var keys = SETS[b.getAttribute("data-set")], on = 0, n = 0;
      Object.keys(wear).forEach(function (s) { if (wear[s]) { n += 1; if (keys.indexOf(wear[s]) >= 0) { on += 1; } } });
      b.setAttribute("aria-pressed", on === keys.length && n === keys.length ? "true" : "false");
    });
    var names = ["head", "hair", "neck", "trail", "aura"].filter(function (s) { return wear[s]; })
      .map(function (s) { return NAME[wear[s]]; });
    if (say) { say.textContent = names.length ? names.join(" · ") : "아무것도 안 썼습니다"; }
    canvas.setAttribute("aria-label", "꾸미기를 쓰고 걷는 도트" + (names.length ? ": " + names.join(", ") : ""));
    if (still) { freeze(); } else if (!raf && W) { draw(now()); }     // 멈춰 있는 동안(탭이 뒤에 있을 때)에도 바로 보이게
  }
  function now() { return window.performance && performance.now ? performance.now() : Date.now(); }
  function put(keys) {
    wear = {};
    fx.parts = [];
    keys.forEach(function (k) { wear[SLOT[k]] = k; });
    paint();
  }
  chips.forEach(function (b) {
    b.addEventListener("click", function () {
      var key = b.getAttribute("data-key"), slot = SLOT[key];
      if (wear[slot] === key) { delete wear[slot]; } else { wear[slot] = key; }
      if (slot === "trail") { fx.parts = []; }
      paint();
    });
  });
  sets.forEach(function (b) {
    b.addEventListener("click", function () {
      put(SETS[b.getAttribute("data-set")]);
      var r = canvas.getBoundingClientRect();
      if (r.bottom < 80 || r.top > (window.innerHeight || 800) - 80) {
        canvas.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "center" });
      }
    });
  });
  var other = root.querySelector("[data-deco-other]"), bare = root.querySelector("[data-deco-bare]");
  if (other) {
    other.addEventListener("click", function () {
      kindIx = (kindIx + 1) % D.kinds.length;
      pet.hop = 0.42;
      if (still) { freeze(); } else if (!raf) { draw(now()); }
    });
  }
  if (bare) { bare.addEventListener("click", function () { put([]); }); }
  canvas.addEventListener("click", function () {     // 누르면 이쪽을 보고 폴짝
    pet.wait = 1.4; pet.dir = "down"; pet.frame = 0; pet.hop = 0.42;
    if (still) { freeze(); }
  });

  // 단추의 작은 그림 (시트 그대로 1:1 - 도트가 뭉개지지 않게 pixelated)
  Array.prototype.forEach.call(document.querySelectorAll("[data-icon]"), function (el) {
    var r = D.sprites["icon_" + el.getAttribute("data-icon")];
    if (!r) { return; }
    el.style.backgroundImage = "url(\"" + deco.src + "\")";
    el.style.backgroundPosition = (-r[0]) + "px " + (-r[1]) + "px";
  });

  // ---------------- 돌리기
  function freeze() {                // 움직임 줄이기: 옆으로 걷던 한순간을 셈해서 멈춰 둔다
    measure();
    pet.hop = 0;
    pet.x = Math.max(8, W / 2 - SIZE); pet.y = (top() + bottom()) / 2;
    pet.tx = W - SIZE - 8; pet.ty = pet.y; pet.wait = 0; pet.speed = 36;
    fx.parts = []; fx.since = { star: 0, petal: 0, heart: 0 }; fx.walked = 0;
    for (var i = 0; i < 70; i++) { step(1 / 60); }
    pet.frame = 0;
    draw(0);
  }
  function tick(now) {
    raf = 0;
    if (!seen || document.hidden) { return; }
    var dt = Math.min(0.05, (now - (last || now)) / 1000);
    last = now;
    step(dt);
    draw(now);
    raf = requestAnimationFrame(tick);
  }
  function go() { if (!raf && !still) { last = 0; raf = requestAnimationFrame(tick); } }

  function start() {
    root.hidden = false;
    measure();
    pet.x = 16; pet.tx = 16; pet.y = pet.ty = (top() + bottom()) / 2; pet.wait = 0.6;
    put(SETS.rank1);
    window.addEventListener("resize", function () { measure(); if (still) { freeze(); } });
    if (still) { freeze(); return; }
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) {
        seen = es[0].isIntersecting;
        if (seen) { go(); }
      }).observe(canvas);
    }
    document.addEventListener("visibilitychange", function () { if (!document.hidden) { go(); } });
    go();
  }
})();
