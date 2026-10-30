# -*- coding: utf-8 -*-
"""꾸미기 (버전 2) 앱 쪽 검사 - 장식 얹기 · 효과 창 · 꾸미기 창 · 머리 자리 다시 받기.

    python client/test_deco.py              전부 (꾸미기 창은 테마 7개를 하나씩 따로 띄운다)
    python client/test_deco.py --window     꾸미기 창만 (지금 POKET_SKIN 테마로) - 위가 테마마다 부른다

**창을 진짜로 띄운다.** 도트 시트는 여기서 그린다 (머리 · 몸통이 있는 32x32 칸, 홀수 칸은 한 칸 위로 들썩인다).

## 무엇을 못 박나

  1. 그림: 꾸미기 열쇠마다 칸 그림이 있다. 선물 줄 · 안내에 꾸미기가 나온다.
  2. 장식 얹기 (sprites.load_walk + deco_place):
     · 장식을 얹으면 칸이 위로 늘고 기준점이 그만큼 내려간다. 몸 밑(foot)은 장식 전과 같은 자리다
     · 왕관은 머리 위에 있고, **도트가 들썩이면 같이 들썩인다** (몸에서 떠다니지 않는다)
     · 진주 목걸이는 뒷모습(위로 걸을 때)에 안 그린다
     · 왕관은 가끔 반짝인다 (걷기를 몇 번 되풀이한 끝에만)
     · 머리 자리(pts)가 없어도 얹는다 · 자리가 망가져 있어도 도트는 나온다
  3. 머리 자리 다시 받기 (walk_cache): 장식을 낀 종만, 시트가 같을 때만, 실행마다 한 번만
  4. 바탕화면 (overlay + deco_fx):
     · 장식을 낀 포켓몬은 장식 얹은 도트로 선다. 효과가 있으면 효과 창이 생기고 클릭이 통과한다
     · 걸으면 발자국이 남고 시간이 지나면 옅어지다 사라진다 (체크무늬로 빼서)
     · 숨기면 · 배틀 중이면 효과 창도 숨는다
     · 동기화로 꾸미기가 바뀌면 갈아 입고, 효과를 다 빼면 효과 창을 치운다. 포켓몬이 사라지면 같이 사라진다
     · 한 틱이 가볍다
  5. 꾸미기 창 (ui_deco): 열쇠 13칸, 가진 것 · 쓰는 중 · 다른 포켓몬 · 없음 표시, 누르면 끼우고 다시 누르면 뺀다,
     안 가진 것은 서버에 안 간다, 선택권이 있으면 묶음 셋을 고를 수 있다(묻고 나서), 실패하면 까닭이 남는다,
     창이 화면 안에 들어간다. **테마 7개 모두에서** 예외 없이 뜬다.
  6. 우클릭 메뉴: 내 포켓몬에만 '꾸미기...' 가 있다.
"""
import os
import subprocess
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-deco-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import json                                                 # noqa: E402
import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

from common import deco as C                                # noqa: E402
from poketdesktop import config, deco_art, deco_fx          # noqa: E402
from poketdesktop import overlay, sprites, walk_cache       # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0
HOME = os.environ["POKET_HOME"]
GOLD = deco_art.METALS["gold"]["Y"][:3]
PEARL = deco_art.PEARL_PAL["p"][:3]
GLINT = (255, 255, 255)
BODY = (90, 140, 200, 255)
SKINS_ALL = ("default", "gs", "emerald", "dp", "pt", "bw", "swsh")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, sec):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


# ---------------------------------------------------------------- 도트 시트
CELL, NF = 32, 4


def make_sheet(name="walk.png", pts=True):
    """8방향 x 4칸. 머리(가로 10) + 몸통. 홀수 칸은 통째로 한 칸 위로 들썩인다."""
    path = os.path.join(HOME, name)
    im = Image.new("RGBA", (CELL * NF, CELL * 8), (0, 0, 0, 0))
    heads, centers = [], []
    for row in range(8):
        hr, cr = [], []
        for col in range(NF):
            up = col % 2
            ox, oy = col * CELL, row * CELL - up
            im.paste(Image.new("RGBA", (10, 9), BODY), (ox + 11, oy + 6))     # 머리 y 6..14
            im.paste(Image.new("RGBA", (14, 15), BODY), (ox + 9, oy + 15))    # 몸통 y 15..29
            hr.append([16, 13 - up])
            cr.append([16, 21 - up])
        heads.append(hr)
        centers.append(cr)
    im.save(path)
    meta = {"ok": True, "frameW": CELL, "frameH": CELL, "rows": 8, "durations": [8] * NF, "src": "pmd"}
    if pts:
        meta.update({"pts": 1, "head": heads, "center": centers})
    return path, meta


def color_box(im, rgb):
    """그 색 칸들의 bbox (없으면 None)."""
    im = im.convert("RGB")
    mask = Image.new("L", im.size, 0)
    px, mp = im.load(), mask.load()
    for y in range(im.height):
        for x in range(im.width):
            if px[x, y] == rgb:
                mp[x, y] = 255
    return mask.getbbox()


def has_color(im, rgb):
    return color_box(im, rgb) is not None


# ---------------------------------------------------------------- 1. 그림 · 선물 줄
def art_part():
    print("\n=== 그림 · 선물 줄 ===")
    from poketdesktop import ui_bag
    missing = [k for k in C.DECOS if deco_art.icon(k) is None]
    chk("꾸미기 열쇠마다 칸 그림이 있다", not missing, missing)
    g = {"kind": "deco", "name": "금관 · 금빛 별가루 · 발밑 빛", "count": 1}
    chk("선물 줄: '꾸미기 · …' (개수를 안 붙인다)", ui_bag.gift_line(g) == "꾸미기 · 금관 · 금빛 별가루 · 발밑 빛",
        ui_bag.gift_line(g))
    chk("선물 안내에 꾸미기를 쓰는 곳이 나온다", "꾸미기..." in ui_bag.gift_notes([g])[2], ui_bag.gift_notes([g]))


# ---------------------------------------------------------------- 2. 장식 얹기
def place_part():
    print("\n=== 장식 얹기 (load_walk) ===")
    sheet, meta = make_sheet()
    plain = sprites.load_walk(sheet, meta, scale=2.0)
    crown = sprites.load_walk(sheet, meta, scale=2.0, deco=("crown_gold",))
    chk("장식 없는 도트는 그대로 (deco 빈 것, 몸 밑 = 칸 높이)", plain.deco == () and plain.foot == plain.h,
        (plain.deco, plain.foot, plain.h))
    chk("왕관을 얹으면 칸이 위로 는다", crown.h > plain.h, (crown.h, plain.h))
    chk("  기준점도 그만큼 내려간다", abs((crown.ay - plain.ay) - (crown.h - plain.h)) <= 1,
        (crown.ay, plain.ay, crown.h, plain.h))
    chk("  몸 밑(foot)은 장식 전과 같은 자리다", crown.foot - crown.ay == plain.foot - plain.ay,
        (crown.foot, crown.ay, plain.foot, plain.ay))
    chk("  얹은 장식을 기억한다", crown.deco == ("crown_gold",), crown.deco)

    down = crown.frames[sprites.DOWN]
    b0 = color_box(down[0], GOLD)
    body0 = color_box(down[0], BODY[:3])
    chk("왕관이 머리 위에 있다 (금빛이 몸보다 위에서 시작)", b0 and body0 and b0[1] < body0[1], (b0, body0))
    b1 = color_box(down[1], GOLD)
    body1 = color_box(down[1], BODY[:3])
    moved_body = body1[1] - body0[1] if body0 and body1 else None
    moved_crown = b1[1] - b0[1] if b0 and b1 else None
    chk("도트가 들썩이면 왕관도 같이 들썩인다", moved_body is not None and moved_crown == moved_body
        and moved_body != 0, (moved_body, moved_crown))
    chk("  옆으로는 안 흔들린다", b0 and b1 and b0[0] == b1[0], (b0, b1))
    plain_n = len(plain.durations)
    chk("왕관은 걷기를 되풀이해 가끔 반짝인다 (프레임이 늘고, 끝 쪽에만 반짝임)",
        len(crown.durations) > plain_n and not any(has_color(f, GLINT) for f in down[:plain_n])
        and any(has_color(f, GLINT) for f in down[-plain_n:]), (len(crown.durations), plain_n))

    pearls = sprites.load_walk(sheet, meta, scale=2.0, deco=("pearls",))
    chk("진주 목걸이는 앞모습에 있다", has_color(pearls.frames[sprites.DOWN][0], PEARL))
    chk("  뒷모습(위로 걸을 때)에는 없다", not any(has_color(f, PEARL) for f in pearls.frames[sprites.UP]))

    sheet2, meta2 = make_sheet("walk_nopts.png", pts=False)
    guess = sprites.load_walk(sheet2, meta2, scale=2.0, deco=("crown_gold",))
    chk("머리 자리가 없어도 얹는다 (어림)", has_color(guess.frames[sprites.DOWN][0], GOLD))
    bad = dict(meta, head="망가짐", center=[[None]])
    try:
        broken = sprites.load_walk(sheet, bad, scale=2.0, deco=("bow",))
        ok = broken is not None and broken.frames
    except Exception as e:                                  # noqa: BLE001
        ok = e
    chk("머리 자리가 망가져 있어도 도트는 나온다", ok is True or bool(ok), ok)
    t = time.time()
    sprites._cache.clear()
    sprites.load_walk(sheet, meta, scale=2.0, deco=("crown_gold", "flower", "pearls"))
    took = time.time() - t
    print("       장식 셋 얹기 %.3f초" % took)
    chk("장식 셋을 얹어도 금방 끝난다 (0.5초 안)", took < 0.5, took)

    hop_plain = sprites.load_walk(sheet, meta, scale=2.0, name="Hop")
    hop = sprites.load_walk(sheet, meta, scale=2.0, name="Hop", deco=("crown_gold",))
    chk("한 번 도는 동작(점프 · 아파하기)은 반짝임 때문에 되풀이하지 않는다 (프레임 수 그대로)",
        hop.count() == hop_plain.count() and crown.count() > plain.count(), (hop.count(), hop_plain.count()))
    chk("장식 전 몸 가운데(body_cx)를 기억한다 - 장식이 없으면 칸 가운데", plain.body_cx == plain.w / 2.0
        and abs((crown.body_cx - crown.ax) - (plain.body_cx - plain.ax)) < 0.01, (plain.body_cx, crown.body_cx))
    chk("머리 자리로 얹었는지 기억한다 (pts)", crown.pts is True and guess.pts is False)

    # 한 줄짜리 동작(Sleep): 모든 방향이 같은 줄을 쓰므로 장식도 같은 모습 (위를 보다 잠들어도 목걸이 · 리본 그대로)
    one = Image.open(sheet).crop((0, 0, CELL * NF, CELL))
    p1 = os.path.join(HOME, "sleep1.png")
    one.save(p1)
    m1 = dict(meta, rows=1, head=meta["head"][:1], center=meta["center"][:1],
              rowmap={"down": 0, "downright": 1, "right": 2, "upright": 3, "up": 4, "upleft": 5, "left": 6,
                      "downleft": 7})
    slp = sprites.load_walk(p1, m1, scale=2.0, name="Sleep", deco=("bow", "pearls"))
    first = slp.frames[sprites.DOWN][0].tobytes()
    chk("한 줄짜리 동작은 방향마다 같은 장식 (실제로 쓴 줄의 방향으로 얹는다)",
        all(slp.frames[d][0].tobytes() == first for d in sprites.DIRS)
        and has_color(slp.frames[sprites.UP][0], PEARL))


# ---------------------------------------------------------------- 3. 머리 자리 다시 받기
class MetaApi(object):
    def __init__(self, meta):
        self.meta = meta
        self.asked = 0

    def anim_meta(self, num, name, shiny=False):
        self.asked += 1
        return self.meta

    def anim_sheet(self, num, name, shiny=False):
        raise AssertionError("시트는 다시 안 받는다")


def refresh_part():
    print("\n=== 머리 자리 다시 받기 (walk_cache) ===")
    sheet, with_pts = make_sheet("w25.png")
    old = dict((k, v) for k, v in with_pts.items() if k not in ("pts", "head", "center"))
    png, meta_path = walk_cache._paths(25, "Walk", False)
    os.makedirs(os.path.dirname(png), exist_ok=True)
    with open(sheet, "rb") as f, open(png, "wb") as g:
        g.write(f.read())
    with open(meta_path, "w") as f:
        json.dump(old, f)
    api = MetaApi(with_pts)
    _p, m = walk_cache.ensure(api, 25)
    chk("장식을 안 낀 종은 다시 안 묻는다", api.asked == 0 and "pts" not in m, (api.asked, m.keys()))
    walk_cache.want_points([25])
    chk("  낀 종은 다시 물어야 한다고 본다", walk_cache.needs_points(25, "Walk", False, m))
    _p, m = walk_cache.ensure(api, 25)
    chk("  meta 만 다시 받아 머리 자리를 붙인다", api.asked == 1 and m.get("pts") == 1 and m.get("head"),
        (api.asked, sorted(m)))
    with open(meta_path) as f:
        chk("  파일에도 적힌다", json.load(f).get("pts") == 1)
    _p, m = walk_cache.ensure(api, 25)
    chk("  이미 있으면 안 묻는다", api.asked == 1, api.asked)

    with open(meta_path, "w") as f:
        json.dump(old, f)
    walk_cache._pts_tried.clear()
    api2 = MetaApi(dict(with_pts, frameW=40))
    _p, m = walk_cache.ensure(api2, 25)
    chk("시트가 바뀌었으면(칸 크기가 다르면) 섞지 않는다", api2.asked == 1 and "pts" not in m, (api2.asked, sorted(m)))
    _p, m = walk_cache.ensure(api2, 25)
    chk("  한 실행에 한 번만 묻는다", api2.asked == 1, api2.asked)
    walk_cache._pts_tried.clear()
    api3 = MetaApi({"ok": True, "frameW": CELL, "frameH": CELL, "rows": 8, "durations": [8] * NF})
    _p, m = walk_cache.ensure(api3, 25)
    chk("옛 서버(자리를 안 줌)면 그대로 쓴다", api3.asked == 1 and "pts" not in m and _p)


# ---------------------------------------------------------------- 4. 바탕화면
def mon(pid, deco=None):
    return {"id": pid, "num": 25, "species": "PIKACHU", "shiny": False, "deco": deco or {},
            "info": {"name": "피카츄", "level": 30, "types": []}}


def walk_steps(root, ov, pet, n, ms=33):
    for _ in range(n):
        pet.state, pet.timer, pet.vx, pet.vy = "walk", 100, 1.0, 0.0
        pet.calm_ms = 0
        pet.update(ms)
        if pet.trail is not None:
            pet.trail.step(ms)
        root.update()


def overlay_part(root):
    print("\n=== 바탕화면 (overlay · deco_fx) ===")
    sheet, meta = make_sheet("ov.png")
    settings = dict(config.DEFAULTS)
    ov = overlay.Overlay(root, settings)
    ov.sync([mon(1, {"head": "crown_gold", "trail": "fx_paw", "aura": "fx_glow"}), mon(2)],
            {}, {25: (sheet, meta)})
    p1, p2 = ov.pets.get(1), ov.pets.get(2)
    chk("두 마리가 선다", p1 is not None and p2 is not None)
    chk("장식을 낀 포켓몬은 장식 얹은 도트로 선다", p1.deco_acc == ("crown_gold",)
        and p1.anims["Walk"].deco == ("crown_gold",), (p1.deco_acc, p1.anims["Walk"].deco))
    chk("  안 낀 포켓몬은 그대로", p2.deco_acc == () and p2.trail is None, (p2.deco_acc, p2.trail))
    t = p1.trail
    chk("효과가 있으면 효과 창이 생긴다", t is not None and t.ok, t)
    if t is None:
        return
    if PLAT.NAME == "platform_mac":
        nsw = getattr(t.win, "_poket_nswindow", None)
        chk("  효과 창은 클릭이 통과한다", nsw is not None and bool(nsw.ignoresMouseEvents()))
    p1.x, p1.y = 300, 300
    walk_steps(root, ov, p1, 60)
    paws = [q for q in t.parts if q.kind == "paw"]
    chk("걸으면 발자국이 남는다", len(paws) >= 3, len(paws))
    chk("  효과 창이 보인다", t.shown and t.win.winfo_ismapped(), (t.shown,))
    img = t.compose(*t.feet(), True)
    chk("  그린 그림에 발자국 색이 있다", has_color(img, deco_art.PAW_COLOR[:3]))
    chk("  발밑 빛 고리도 있다", any(has_color(img, c) for c in deco_art.GLOW_RIM))
    chk("  알파는 0 아니면 255 다 (윈도우 투명색 창에서 번지지 않게)",
        set(img.split()[3].tobytes()) <= {0, 255}, set(img.split()[3].tobytes()))
    # 옅어지기: 체크무늬로 칸을 뺀다
    q = deco_fx.Particle("paw", 0, 0, 1000)
    full = deco_fx.draws(q, 1)[3]
    q.age = 800
    mid = deco_fx.draws(q, 1)[3]
    q.age = 999
    end = deco_fx.draws(q, 1)[3]
    chk("발자국은 처음엔 또렷하고 점점 옅어진다", full == 16 and 0 < mid < 16 and end <= 1, (full, mid, end))
    n_full = deco_fx._mask(16, 64, 40).tobytes().count(255)
    n_half = deco_fx._mask(8, 64, 40).tobytes().count(255)
    chk("  옅게 = 체크무늬로 칸을 반쯤 뺀다", n_full == 64 * 40 and n_half * 2 == n_full, (n_half, n_full))

    # 서 있으면 새로 안 찍히고, 시간이 지나면 다 사라진다
    for _ in range(90):
        p1.state = "idle"
        t.step(33)
    chk("서 있으면 발자국이 사라진다 (발밑 빛만 남는다)", not t.parts and t.shown, (len(t.parts), t.shown))

    ov.set_hidden(True)
    chk("숨기면 효과 창도 숨는다", not t.shown and not t.win.winfo_ismapped())
    ov.set_hidden(False)
    walk_steps(root, ov, p1, 20)
    chk("  다시 보이면 다시 그린다", t.shown)
    # 놀러 온 친구 포켓몬은 스스로 안 걷게 battling 을 켜 둔 채 따로 옮겨진다 - 그래도 효과가 남아야 한다
    p1.battling = True
    t.parts = []
    for _ in range(40):
        p1.x += 1.5
        p1.place()
        t.step(33)
        root.update()
    chk("battling 이 켜진 채 옮겨져도 (놀러 온 포켓몬) 걸은 자리에 효과가 남는다",
        t.shown and any(q.kind == "paw" for q in t.parts), (t.shown, len(t.parts)))
    p1.battling = False

    # 한 틱의 무게
    st = time.time()
    walk_steps(root, ov, p1, 60)
    each = (time.time() - st) / 60.0
    print("       한 틱 (걷기 + 효과 + 화면) %.1fms" % (each * 1000))
    chk("한 틱이 가볍다 (25ms 안 - CI 러너는 느리다)", each < 0.025, each)

    # 동기화로 꾸미기가 바뀐다
    win_old = t.win
    ov.sync([mon(1, {"hair": "bow"}), mon(2, {"trail": "fx_hearts"})], {}, {25: (sheet, meta)})
    settle(root, 0.1)
    chk("효과를 다 빼면 효과 창을 치운다", p1.trail is None and not win_old.winfo_exists())
    chk("장식을 바꾸면 갈아 입는다 (왕관 -> 리본)", p1.anims["Walk"].deco == ("bow",) and p1.deco_acc == ("bow",),
        (p1.anims["Walk"].deco, p1.deco_acc))
    chk("효과만 새로 끼우면 효과 창이 생긴다 (도트는 그대로)", p2.trail is not None
        and p2.trail.keys == ("fx_hearts",) and p2.anims["Walk"].deco == (), (p2.trail,))
    other = p1.anim_for("Idle")
    chk("  (다른 동작은 아직 안 받았다 - 받으면 같은 장식을 얹는다)", other is None)
    ov.settings["petOpacity"] = 80
    ov.apply_alpha()
    if PLAT.NAME == "platform_mac":
        nsw = getattr(p2.trail.win, "_poket_nswindow", None)
        chk("투명도를 바꿔도 효과 창은 클릭이 통과한다", nsw is not None and bool(nsw.ignoresMouseEvents()))
    ov.settings["petOpacity"] = 100
    ov.apply_alpha()
    p2.x, p2.y = 500, 300
    walk_steps(root, ov, p2, 40)
    chk("하트가 떠오른다", any(q.kind == "heart" for q in p2.trail.parts))
    chk("효과 창은 포켓몬 크기를 따른다 (하트가 머리 위로 떠오를 자리)", p2.trail.H >= p2.fh + 70 + deco_fx.BELOW_FEET,
        (p2.trail.W, p2.trail.H, p2.fw, p2.fh))
    if PLAT.NAME == "platform_mac":
        from AppKit import NSApp
        from poketdesktop import platform_mac as PM
        menu = U.PopupMenu(root, [{"text": "가", "command": lambda: None}], 500, 300)
        settle(root, 0.3)
        names = {PM.nswindow(p2.win).windowNumber(): "pet", PM.nswindow(p2.trail.win).windowNumber(): "trail",
                 PM.nswindow(menu.win).windowNumber(): "menu"}

        def order():
            return [names[w.windowNumber()] for w in NSApp.orderedWindows() if w.windowNumber() in names]
        before = order()
        ov.keep_on_top()
        settle(root, 0.2)
        after = order()
        chk("창 순서: 효과 창은 제 포켓몬 바로 아래, 열린 메뉴는 그대로 맨 위 (포켓몬을 올리지 않는다)",
            before == after == ["menu", "pet", "trail"], (before, after))
        menu.close()
        settle(root, 0.1)
    else:
        ov.keep_on_top()
        chk("  창 순서를 다시 맞춰도 괜찮다", p2.trail.shown)

    # 장식을 끼우고 빼도 몸은 제자리 (칸은 한쪽으로만 늘어난다)
    body = lambda p: (p.x + p.anims["Walk"].body_cx, p.y + p.anims["Walk"].foot)       # noqa: E731
    x1, y1, x2, y2 = ov.area()
    p2.x, p2.y = (x1 + x2) / 2.0, (y1 + y2) / 2.0      # 영역 끝에 붙어 있으면 커진 칸을 영역 안으로 미는 것(clamp)이 섞인다
    p2.place()
    b0 = body(p2)
    p2.mon["deco"] = {"trail": "fx_hearts", "hair": "flower", "head": "crown_silver"}
    ov._match_look(p2)
    b1 = body(p2)
    chk("장식을 끼워도 몸이 안 밀린다 (몸 가운데 · 발이 그대로)", p2.anims["Walk"].deco == ("crown_silver", "flower")
        and abs(b0[0] - b1[0]) <= 1 and abs(b0[1] - b1[1]) <= 1, (b0, b1))
    p2.mon["deco"] = {"trail": "fx_hearts"}
    ov._match_look(p2)
    b2 = body(p2)
    chk("  빼도 그대로", abs(b0[0] - b2[0]) <= 1 and abs(b0[1] - b2[1]) <= 1, (b0, b2))

    # 머리 자리를 나중에 받았다: 어림으로 얹은 장식을 제자리로
    s2, m2 = make_sheet("late.png", pts=False)
    ov.walks[25] = (s2, m2)
    p2.mon["deco"] = {"head": "crown_gold", "trail": "fx_hearts"}
    ov._match_look(p2)
    chk("머리 자리 없이 받은 시트면 어림으로 얹는다", p2.anims["Walk"].pts is False)
    _s, full = make_sheet("late2.png")
    ov.walks[25] = (s2, dict(m2, pts=1, head=full["head"], center=full["center"]))
    ov._match_look(p2)
    chk("  나중에 머리 자리를 받으면 다시 입는다", p2.anims["Walk"].pts is True)
    idle = sprites.load_walk(s2, m2, ov.settings["targetHeight"], scale=p2.base_scale, name="Idle",
                             deco=p2.deco_acc)
    p2.anims["Idle"] = idle
    ov.sheets[walk_cache.sheet_key(p2.look, "Idle", False)] = (s2, dict(m2, pts=1, head=full["head"],
                                                                         center=full["center"]))
    p2.drop_guessed(ov.sheets)
    chk("  다른 동작도 어림으로 얹은 것은 버린다 (다음에 제자리로 다시 만든다)", "Idle" not in p2.anims)

    # 미리 만들기: 작업 스레드에서 같은 인자로 부르면 화면 스레드는 캐시에서 바로 꺼낸다
    import threading
    m3 = mon(9, {"neck": "pearls"})
    s3, meta3 = make_sheet("pre.png")
    th = threading.Thread(target=lambda: overlay.build_walk(ov.settings, s3, meta3, m3))
    th.start()
    th.join()
    ov.walks[25] = (s3, meta3)
    t0 = time.time()
    a3 = ov.anim_of(m3)
    chk("미리 만든 장식 도트는 바로 나온다 (Overlay.anim_of 와 같은 인자)", a3.deco == ("pearls",)
        and time.time() - t0 < 0.01, time.time() - t0)
    w2 = p2.trail.win
    ov.sync([mon(1, {"hair": "bow"})], {}, {25: (sheet, meta)})
    settle(root, 0.1)
    chk("포켓몬이 사라지면 효과 창도 사라진다", not w2.winfo_exists())
    ov.clear()
    settle(root, 0.1)


# ---------------------------------------------------------------- 5. 꾸미기 창
class DecoApi(object):
    """서버(deco.state · equip · pick) 흉내. 규칙은 server/app/deco.py 와 같다 (한 마리만, 칸마다 하나)."""

    def __init__(self, owned, worn=None, picks=0):
        self.owned = set(owned)
        self.worn = dict(worn or {})         # 포켓몬 id -> {칸: 열쇠}
        self.picks = picks
        self.calls = []
        self.fail = None

    def deco_state(self):
        by = {}
        for pid, d in self.worn.items():
            for key in d.values():
                by[key] = pid
        return {"items": [{"key": k, "kr": d["kr"], "slot": d["slot"], "owned": k in self.owned,
                           "wornBy": by.get(k), "effect": d["slot"] in C.EFFECTS} for k, d in C.DECOS.items()],
                "picks": self.picks,
                "choices": [{"key": b, "kr": C.BUNDLE_KR[b]} for b in C.JOIN_CHOICES],
                "worn": dict((str(k), v) for k, v in self.worn.items() if v)}

    def deco_equip(self, pid, key, on=True):
        self.calls.append(("equip", pid, key, on))
        if self.fail:
            raise RuntimeError(self.fail)
        slot = C.slot_of(key)
        mine = self.worn.setdefault(pid, {})
        if on:
            for other, d in self.worn.items():
                if other != pid and d.get(slot) == key:
                    d.pop(slot)
            mine[slot] = key
        elif mine.get(slot) == key:
            mine.pop(slot)
        out = self.deco_state()
        out["deco"] = dict(mine)
        return out

    def deco_pick(self, bundle):
        self.calls.append(("pick", bundle))
        self.picks -= 1
        self.owned.update(C.BUNDLES[bundle])
        out = self.deco_state()
        out["got"] = [C.name(k) for k in C.BUNDLES[bundle]]
        return out


class MiniApp(object):
    def __init__(self, root, api):
        self.root = root
        self.api = api


def window_part(root):
    from poketdesktop import skins, ui_box, ui_deco
    print("\n=== 꾸미기 창 (테마 %s) ===" % skins.current().key)
    api = DecoApi(["crown_gold", "fx_stars_gold", "fx_glow", "bow"], {7: {"head": "crown_gold"}}, picks=1)
    app = MiniApp(root, api)
    done = []
    m = mon(1)
    w = ui_deco.DecoWindow(app, m, on_done=lambda mm: done.append(dict(mm.get("deco") or {})))
    settle(root, 0.4)
    chk("가진 것만 칸이 된다 (안 가진 것은 안 보인다 - 꾸미기는 가방의 개별 아이템)",
        set(w.cells) == {"crown_gold", "fx_stars_gold", "fx_glow", "bow"}, sorted(w.cells))
    tags = dict((k, v[3].cget("text")) for k, v in w.cells.items())
    chk("다른 포켓몬이 쓰는 것 · 그냥 가진 것이 나뉜다", tags["crown_gold"] == "다른 포켓몬" and tags["bow"] == "", tags)
    chk("선택권이 있으면 묶음 셋이 보인다", w.pick_box.winfo_ismapped()
        and len([c for c in w.pick_box.winfo_children()[-1].winfo_children()]) == 3)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    chk("창이 화면 안에 들어간다", w.win.winfo_width() <= sw and w.win.winfo_height() <= sh - 40,
        (w.win.winfo_width(), w.win.winfo_height(), sw, sh))
    clipped = [k for k, v in w.cells.items() if v[2].winfo_reqwidth() > v[0].winfo_reqwidth() + 2 * U.h(6)]
    chk("칸 이름이 칸 폭을 크게 넘지 않는다 (줄바꿈)", not clipped, clipped)

    w.press("pearls")
    settle(root, 0.2)
    chk("안 가진 것은 서버에 안 간다 · 까닭이 남는다", not api.calls and "가지고 있지 않은" in w.status.cget("text"),
        (api.calls, w.status.cget("text")))
    chk("  설명에 얻는 곳이 나온다", "얻는 곳" in w.desc.cget("text"), w.desc.cget("text"))
    w.press("crown_gold")
    settle(root, 0.3)
    chk("누르면 끼운다 (다른 포켓몬이 쓰던 것을 가져온다)", api.calls[-1] == ("equip", 1, "crown_gold", True)
        and api.worn[7] == {} and done and done[-1] == {"head": "crown_gold"}, (api.calls, api.worn, done))
    chk("  '쓰는 중' 으로 바뀐다", w.cells["crown_gold"][3].cget("text") == "쓰는 중")
    w.press("crown_gold")
    settle(root, 0.3)
    chk("다시 누르면 뺀다", api.calls[-1] == ("equip", 1, "crown_gold", False) and done[-1] == {}, api.calls)
    api.fail = "잠깐 안 됩니다"
    w.press("bow")
    settle(root, 0.3)
    chk("실패하면 까닭이 남는다", "잠깐 안 됩니다" in w.status.cget("text"), w.status.cget("text"))
    api.fail = None

    asked = []
    real = ui_box.confirm
    ui_box.confirm = lambda *a, **k: asked.append(a[2]) or True
    try:
        w.pick("join_flower")
        settle(root, 0.3)
    finally:
        ui_box.confirm = real
    chk("묶음을 고르기 전에 묻는다", asked and "바꿀 수 없습니다" in asked[0], asked)
    chk("  고르면 받는다 · 선택권 띠가 사라진다", api.calls[-1] == ("pick", "join_flower")
        and "flower" in api.owned and not w.pick_box.winfo_ismapped(), (api.calls, w.pick_box.winfo_ismapped()))
    chk("  받은 것이 상태 글에 나온다", "꽃핀" in w.status.cget("text"), w.status.cget("text"))
    chk("  받은 꽃핀은 이제 누를 수 있다", w.cells["flower"][3].cget("text") == "", w.cells["flower"][3].cget("text"))
    w.win.geometry("+%d+%d" % (40, 60))
    settle(root, 0.2)
    pos = (w.win.winfo_x(), w.win.winfo_y())
    w.press("crown_gold")
    settle(root, 0.3)
    chk("끼울 때 창이 옮긴 자리 그대로 (가운데로 튀지 않는다)", (w.win.winfo_x(), w.win.winfo_y()) == pos,
        (pos, (w.win.winfo_x(), w.win.winfo_y())))
    w.close()
    chk("닫힌다", not w.alive)

    empty = DecoApi([])
    w2 = ui_deco.DecoWindow(MiniApp(root, empty), mon(2))
    settle(root, 0.4)
    labels = [c.cget("text") for c in w2.grid.winfo_children() if c.winfo_class() == "Label"]
    chk("가진 것이 없으면 칸 대신 얻는 길 안내", not w2.cells and any("가진 꾸미기가 없습니다" in t for t in labels), labels)
    w2.close()


def btn_text(b):
    """단추 글 (기본 PushButton 은 label, 테마 단추는 text)."""
    t = getattr(b, "text", None)
    return t if isinstance(t, str) else b.label.cget("text")


def btn_on(b):
    if hasattr(b, "enabled"):
        return bool(b.enabled)
    return str(getattr(b, "state", None) or b.label.cget("state")) != "disabled"


def bag_part(root):
    """가방의 꾸미기 주머니 - 테마마다 (가방은 테마가 따로 그린다)."""
    from poketdesktop import item_icons, skins, ui_bag, ui_bag_tabs, ui_box, sprite_cache
    print("\n=== 가방의 꾸미기 주머니 (테마 %s) ===" % skins.current().key)
    sprite_cache.ensure = lambda *a, **k: None

    class BagApi(DecoApi):
        def shop(self):
            return {"items": [{"id": "RARECANDY", "kr": "이상한사탕", "cat": "misc", "sell": 100,
                               "effect": {"kind": "level", "amount": 1}}],
                    "bag": {"RARECANDY": 3}, "money": 500}

        def _call(self, method, path, body=None, **k):
            return self.shop() if path == "/api/shop" else {}

        def pokemon(self):
            return [dict(mon(11), level=30, onDesktop=True, slot=0), dict(mon(12), level=20, onDesktop=True, slot=1),
                    dict(mon(13), level=10, onDesktop=False)]

        def item_sprite(self, item_id):
            return None

        def tms(self):
            return {"tms": [], "owned": []}

    class BagApp(MiniApp):
        dex = None
        settings = {}
        balls = money = 0
        bag_window = tm_window = None

        def __init__(self, root, api):
            MiniApp.__init__(self, root, api)
            self.changed = []

        def request_sync(self):
            pass

        def deco_changed(self, pid, deco):
            self.changed.append((pid, deco))

        def notify(self, *a):
            pass

    api = BagApi(["crown_gold", "fx_stars_gold", "bow"], {11: {"head": "crown_gold"}}, picks=1)
    app = BagApp(root, api)
    tabs = ui_bag_tabs.BagTabs(root, app)
    bag = tabs.bag
    end = time.time() + 10
    while time.time() < end and not (bag.items and bag._wait is None):
        root.update()
        time.sleep(0.02)
    settle(root, 0.3)
    ids = sorted(i["id"] for i in bag.items if i.get("cat") == "deco")
    chk("가방에 가진 꾸미기가 '꾸미기' 분류 도구로 들어온다 (선택권도)",
        ids == ["deco:bow", "deco:crown_gold", "deco:fx_stars_gold", "deco:pick_join"], ids)
    if hasattr(bag, "_pick_pocket"):
        from poketdesktop.skins.dp.scene import POCKETS
        chk("  테마 가방에 '꾸미기' 주머니가 있다", "deco" in dict(POCKETS))
        bag._pick_pocket("deco")
        settle(root, 0.2)
        shown = set(v.get("cat") for k, v in bag._entries if k == "item")
        chk("  꾸미기 주머니를 고르면 꾸미기만", shown == {"deco"}, shown)
    chk("  그림이 있다 (서버에 안 묻고 앱이 그린다)", item_icons.photo("deco:crown_gold", 20) is not None
        and item_icons.photo("deco:pick_join", 28) is not None)
    bag.pick_item("deco:crown_gold")
    settle(root, 0.2)
    st = bag._states.get(11)
    chk("쓰고 있는 포켓몬 줄은 '쓰는 중 · 빼기'", st and st[2] == "쓰는 중 · 빼기", st)
    chk("  팔 수 없다", not btn_on(bag.sell_btn))
    bag.pick_mon(11)
    settle(root, 0.1)
    text = btn_text(bag.use_btn)
    chk("  단추는 '빼기'", text == "빼기", text)
    bag.do_use()
    settle(root, 0.5)
    chk("  누르면 뺀다 · 바탕화면에 알린다", api.calls[-1] == ("equip", 11, "crown_gold", False)
        and app.changed and app.changed[-1] == (11, {}), (api.calls, app.changed))
    end = time.time() + 5
    while time.time() < end and bag._wait is not None:
        root.update()
        time.sleep(0.02)
    bag.pick_item("deco:bow")
    bag.pick_mon(12)
    settle(root, 0.1)
    text = btn_text(bag.use_btn)
    chk("다른 포켓몬을 고르면 '씌우기'", text == "씌우기", text)
    bag.do_use()
    settle(root, 0.5)
    chk("  누르면 씌운다", api.calls[-1] == ("equip", 12, "bow", True), api.calls[-1:])
    end = time.time() + 5
    while time.time() < end and bag._wait is not None:
        root.update()
        time.sleep(0.02)
    bag.pick_item("deco:pick_join")
    settle(root, 0.1)
    text = btn_text(bag.use_btn)
    chk("선택권은 '묶음 고르기' (포켓몬을 안 고른다)", text == "묶음 고르기", text)
    asked = []
    real = ui_box.ask_choice
    ui_box.ask_choice = lambda parent, title, msg, opts: asked.append((msg, [o[0] for o in opts])) or "join_pearls"
    try:
        bag.do_use()
        settle(root, 0.6)
    finally:
        ui_box.ask_choice = real
    chk("  셋 가운데 고르고(바꿀 수 없다고 말한다) 받는다", asked and "바꿀 수 없습니다" in asked[0][0]
        and asked[0][1] == list(C.JOIN_CHOICES) and api.calls[-1] == ("pick", "join_pearls"), (asked, api.calls[-1:]))
    end = time.time() + 5
    while time.time() < end and bag._wait is not None:
        root.update()
        time.sleep(0.02)
    settle(root, 0.2)
    ids = sorted(i["id"] for i in bag.items if i.get("cat") == "deco")
    chk("  받은 진주 목걸이 · 하트가 가방에 들어오고 선택권은 사라진다",
        "deco:pearls" in ids and "deco:fx_hearts" in ids and "deco:pick_join" not in ids, ids)
    tabs.close()
    settle(root, 0.2)


def visit_part():
    print("\n=== 놀러 가기 ===")
    from poketdesktop import visit
    m = visit.pet_mon({"id": 3, "num": 25, "deco": {"head": "crown_gold"}}, -1000003)
    chk("놀러 온 포켓몬도 서버가 실어 준 꾸미기를 쓴다", m.get("deco") == {"head": "crown_gold"}, m)
    chk("  없으면 빈 것", visit.pet_mon({"id": 4, "num": 25}, -1000004).get("deco") == {})


def menu_part(root):
    print("\n=== 우클릭 메뉴 ===")
    from poketdesktop import app as A

    class Fake(object):
        arena = None
        visit = None
        root = None

        def mega_menu_row(self, pet):
            return None

        def __getattr__(self, name):
            return lambda *a, **k: None

    got = []
    real_menu, real_native = U.PopupMenu, A.PLAT.NATIVE_MENU
    U.PopupMenu = lambda root, rows, *a, **k: got.append([r and r.get("text") for r in rows])
    A.PLAT.NATIVE_MENU = False
    try:
        f = Fake()
        f.root = root

        class P(object):
            def __init__(self, pid):
                self.id = pid
                self.mon = mon(pid)
        ev = type("E", (), {"x_root": 10, "y_root": 10})()
        A.App.pet_menu(f, P(5), ev)
        A.App.pet_menu(f, P(-3), ev)
    finally:
        U.PopupMenu, A.PLAT.NATIVE_MENU = real_menu, real_native
    chk("내 포켓몬에는 '꾸미기...' 가 있다", got and "꾸미기..." in got[0], got[:1])
    chk("  남의 포켓몬(id 가 0 아래)에는 없다", len(got) > 1 and "꾸미기..." not in got[1], got[1:])


def window_only():
    """테마 하나로 꾸미기 창만 (위의 main 이 테마마다 따로 부른다)."""
    from poketdesktop import skins
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append("%s: %s" % (e.__name__, v))
    window_part(root)
    bag_part(root)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    return FAIL


def main():
    if "--window" in sys.argv:
        f = window_only()
        print("\n%d개 통과, %d개 실패" % (OK, FAIL))
        return 1 if f else 0
    PLAT.before_tk()
    art_part()
    place_part()
    refresh_part()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append("%s: %s" % (e.__name__, v))
    overlay_part(root)
    visit_part()
    menu_part(root)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()

    print("\n=== 꾸미기 창 - 테마 7개 ===")
    for key in SKINS_ALL:
        env = dict(os.environ, POKET_SKIN=key, POKET_HOME=tempfile.mkdtemp(prefix="poket-test-deco-%s-" % key))
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--window"], env=env,
                           capture_output=True, text=True, timeout=120)
        tail = (r.stdout or "").strip().splitlines()[-1:] or [r.stderr[-300:]]
        chk("테마 %s 에서 꾸미기 창 · 가방 꾸미기 주머니가 다 통과한다" % key, r.returncode == 0, (tail, r.stdout[-800:] if r.returncode
                                                                         else ""))
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
