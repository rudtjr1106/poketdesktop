# -*- coding: utf-8 -*-
"""아르케 (2.4.0) — 바탕화면 현상. 서버가 '지금 일어날 것' 으로 준 현상 하나를 바탕화면에서 재생한다.

    play(app, ph, on_seen) -> Show       ph = {"id", "at", "until", "left"?, "kind", "data"}

**같은 시각에 모두에게 똑같이** 일어난다 (서버가 정한 값만 그린다 - 무작위로 자리를 바꾸지 않는다). 놓치면 놓친 것.

    unown    안농(도감 201) 도트가 작업 표시줄 선을 걸어 지나가다 가운데쯤 아르케 글자(data.glyph 0~23)를 떨군다.
             data.dir 1 이면 왼쪽에서, -1 이면 오른쪽에서. 글자는 8초 남았다가 한 점씩 흩어져 사라진다
    relic    작은 돌 조각이 떨어진다. **누르면** 새겨진 글(data.text, data.glyph?)이 뜬다. 안 누르면 끝 시각에 사라진다
    stars    화면 위쪽 띠(data.band - 화면 높이의 몇 분의 몇)에 별 몇 개 (data.pts [[x, y, 밝기 0~2]] - 띠 안의 0..1)
    drip     물방울이 하나씩 떨어진다 (data.count 개 - 세어 보라는 것)
    sand     모래바람이 data.dir 쪽으로 분다
    tremor   땅이 흔들린다 - 바탕화면 포켓몬이 떨다가 data.dir 쪽을 본다

on_seen(ph, 그림) 은 **사람이 정말 봤을 때 한 번** 부른다 (글자를 떨궜다 · 유물을 눌렀다 · 별이 다 떴다 · 물방울이 다
떨어졌다 ...). 그림(PIL)은 일지의 '내가 본 것' 에 남길 것 - 스크린샷 찍어 나누기 좋게.

공습 장면(airraid_show)의 틀을 그대로 쓴다: 예약은 모두 `after` 로 (닫히면 안 돈다 · 예외는 정리로), 진행이 멎으면
정리하는 멈춤 감시 (단, 유물을 누르길 기다리는 동안은 hold 로 빼 준다), **몇 번 불러도 안전한** cleanup.
맥: 큰 화면 캔버스를 깔지 않는다 - 별 하나 · 물방울 하나가 각자 작은 창(duel_scene.Sprite)이다. 오래 떠 있는 창은
몇 초마다 '항상 위' 와 클릭 통과를 다시 건다 (맥은 순서가 바뀌면 풀린다). 창은 화면 밖에서 바로 없애지 않는다
(Sprite.destroy 가 막아 준다).
"""
import datetime
import math
import random
import time
import traceback

from PIL import Image, ImageDraw

from . import arche_art as ART
from . import arena_layout as L
from . import config
from . import platform_os as PLAT
from .arena import ArenaPet
from .duel_scene import Sprite
from .overlay import work_area

SPEED = 1.0                  # 검사가 빠르게 돌린다 (끝 시각까지 남은 시간도 같이 줄인다)
STALL_MS = 15000             # 장면의 예약이 이만큼 하나도 안 돌면 멈춘 것으로 보고 정리 (기다리는 동안은 hold 로 뺀다)
MAX_MS = 10 * 60 * 1000      # 무엇이든 이보다 길게는 안 띄운다
TICK_MS = 100                # 맥 클릭 자리 좇기 · 항상 위 다시 걸기
KEEP_TICKS = 30              # 3초마다 '항상 위' 다시
KEY = (255, 0, 253)          # 현상 창의 투명색

UNOWN_NUM = 201
WALK_SPEED = 120             # px/초 - 안농은 천천히 지나간다
PAUSE_MS = 700               # 가운데에서 멈칫
GLYPH_K = 4                  # 떨군 글자 배율
GLYPH_FALL_MS = 450
GLYPH_HOLD_MS = 8000         # 떨군 글자가 남아 있는 시간
FADE_MS = 1200               # 한 점씩 흩어져 사라지기
FADE_STEPS = 6

RELIC_K = 3
RELIC_FALL_MS = 1400
RELIC_MIN_WAIT = 5000        # 끝 시각이 다 됐어도 이만큼은 떠 있는다
READ_MIN_MS = 10000          # 새겨진 글을 읽을 시간
READ_PER_CHAR = 150
READ_MAX_MS = 45000
PANEL_W = 320                # 새겨진 글 판의 폭 (화면 px) - 긴 글은 줄을 바꿔 아래로 늘린다 (글자는 안 줄인다)
TEXT_PX = 11                 # Galmuri11 (2배로 키워 그린다)

STAR_K = 2
STAR_GAP = 260               # 별이 하나씩 뜬다
STAR_MIN_MS = 6000

DRIP_FALL_MS = 900
DRIP_GAP = 1200
DRIP_SPLASH_MS = 180
DRIP_MAX = 30

SAND_N = 8
SAND_MS = 2600
SAND_STAGGER = 140

TREMOR_SEQ = (5, -4, 6, -5, 4, -6, 5, -3, 4, -2, 3, -1, 2, 0)
TREMOR_STEP = 45
TREMOR_FACE_MS = 2500        # 흔들린 뒤 dir 쪽을 바라보는 시간

KINDS = ("unown", "relic", "stars", "drip", "sand", "tremor")
DEFAULT_LEFT = {"unown": 60, "relic": 60, "stars": 40, "drip": 30, "sand": 20, "tremor": 15}


def ms(x):
    return max(1, int(x / float(SPEED)))


def play(app, ph, on_seen, on_done=None):
    """현상 하나를 바로 튼다. 무엇이 터져도 예외를 내지 않는다 (돌려준 Show 는 이미 닫혀 있을 수 있다)."""
    show = Show(app, ph, on_seen, on_done)
    show.start()
    return show


# ---------------------------------------------------------------- 도우미
def _solid(im):
    """반투명 점을 없앤다 (투명색 창은 반투명을 못 그린다 - 128 넘으면 꽉, 아니면 뚫림)."""
    im = im.convert("RGBA")
    a = im.split()[3].point(lambda v: 255 if v >= 128 else 0)
    im.putalpha(a)
    return im


def _when(v):
    """'at' · 'until' 값 -> 유닉스 초. ISO 글자(시간대 있음 · Z) 또는 숫자. 모르면 None."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        s = str(v).strip().replace("Z", "+00:00")
        d = datetime.datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=9)))     # 시간대 없으면 KST
        return d.timestamp()
    except Exception:                                       # noqa: BLE001
        return None


def left_seconds(ph):
    """끝까지 남은 초. 컨트롤러가 서버 시각으로 셈한 'left' 가 있으면 그것 (PC 시계가 틀려도 맞게), 없으면 until."""
    kind = (ph or {}).get("kind")
    try:
        if ph.get("left") is not None:
            return float(ph["left"])
    except Exception:                                       # noqa: BLE001
        pass
    u = _when((ph or {}).get("until"))
    if u is None:
        return float(DEFAULT_LEFT.get(kind, 30))
    return u - time.time()


def dissolve(im, steps=FADE_STEPS, seed=0):
    """그림이 한 점씩 흩어지는 프레임들 (마지막은 빈 그림). 투명색 창이라 반투명 대신 점을 지운다."""
    im = _solid(im)
    px = [(x, y) for y in range(im.height) for x in range(im.width) if im.getpixel((x, y))[3]]
    random.Random(seed).shuffle(px)
    out = []
    for k in range(1, steps + 1):
        f = im.copy()
        p = f.load()
        for x, y in px[:int(len(px) * k / float(steps))]:
            p[x, y] = (0, 0, 0, 0)
        out.append(f)
    return out


def wrap(text, font, width):
    """글을 폭(px)에 맞춰 줄을 나눈다 - 띄어쓰기에서 먼저, 안 되면 글자에서. 글자 크기는 안 줄인다."""
    lines = []
    for para in str(text or "").split("\n"):
        cur = ""
        for word in para.split(" "):
            cand = (cur + " " + word) if cur else word
            if font.getlength(cand) <= width:
                cur = cand
                continue
            if cur:
                lines.append(cur)
                cur = ""
            while word and font.getlength(word) > width:   # 한 낱말이 폭보다 길다 - 글자에서 자른다
                i = 1
                while i < len(word) and font.getlength(word[:i + 1]) <= width:
                    i += 1
                lines.append(word[:i])
                word = word[i:]
            cur = word
        lines.append(cur)
    while lines and not lines[-1]:
        lines.pop()
    return lines or [""]


def panel_image(text, glyph=None):
    """유물에 새겨진 글 판 (RGBA, 폭 PANEL_W 안). 낮은 해상도로 그려 2배 (도트 결)."""
    k = 2
    f = ART.font(TEXT_PX)
    pad = 6
    inner = PANEL_W // k - pad * 2
    lines = wrap(text, f, inner)
    lh = TEXT_PX + 4
    gh = ((ART.GLYPH_H + 2) * 2 + 4) if glyph is not None else 0
    w = max(60, min(inner, max(int(f.getlength(s)) for s in lines) + 1)) + pad * 2
    h = pad * 2 + gh + lh * len(lines)
    im = Image.new("RGBA", (w, h), (62, 66, 78, 255))
    d = ImageDraw.Draw(im)
    d.fontmode = "1"                                        # 투명색 창 - 글자 둘레를 흐리지 않는다
    d.rectangle([0, 0, w - 1, h - 1], outline=(28, 30, 38))
    d.rectangle([1, 1, w - 2, h - 2], outline=(104, 110, 124))
    d.line([(2, h - 3), (w - 3, h - 3)], fill=(44, 47, 58))
    y = pad
    if glyph is not None:
        g = ART.glyph(int(glyph) % len(ART.GLYPHS), 2, ART.TEAL, glow=False)
        im.paste(g, ((w - g.width) // 2, y), g)
        y += gh
    for s in lines:                                         # 줄마다 가운데 (돌에 새긴 글)
        d.text((max(pad, (w - int(f.getlength(s))) // 2), y), s, font=f, fill=ART.PAPER)
        y += lh
    return ART.up(im, k)


def snap_unown(gi):
    g = ART.glyph(gi, 6)
    im = Image.new("RGBA", (g.width + 36, g.height + 36), (16, 20, 30, 255))
    im.paste(g, (18, 18), g)
    return im


def snap_stars(pts, ratio):
    w = 360
    h = max(48, int(w * ratio))
    im = Image.new("RGBA", (w, h), (8, 12, 30, 255))
    for x, y, mag in pts:
        s = ART.star(mag, STAR_K)
        im.paste(s, (int(x * (w - 1)) - s.width // 2, int(y * (h - 1)) - s.height // 2), s)
    return im


def snap_drip(n):
    d = ART.drip(3)
    cols = min(n, 10)
    rows = (n + cols - 1) // cols
    im = Image.new("RGBA", (12 + cols * (d.width + 8), 12 + rows * (d.height + 8)), (10, 22, 40, 255))
    for i in range(n):
        im.paste(d, (8 + (i % cols) * (d.width + 8), 8 + (i // cols) * (d.height + 8)), d)
    return im


def snap_dir(kind, dr):
    """모래바람 · 떨림: 어느 쪽인지 (화살 + 모래 / 금)."""
    im = Image.new("RGBA", (120, 48), (40, 30, 22, 255) if kind == "sand" else (24, 22, 30, 255))
    d = ImageDraw.Draw(im)
    if kind == "sand":
        for i in range(4):
            s = ART.sand(2, i)
            im.paste(s, (10 + i * 22, 6 + (i % 2) * 18), s)
    else:
        d.line([(10, 30), (30, 20), (44, 34), (62, 18), (80, 30), (110, 22)], fill=(150, 140, 170), width=2)
    x0, x1 = (20, 104) if dr > 0 else (104, 20)
    d.line([(x0, 40), (x1, 40)], fill=(240, 230, 200), width=2)
    d.polygon([(x1, 40), (x1 - 8 * dr, 35), (x1 - 8 * dr, 45)], fill=(240, 230, 200))
    return im


class UnownPet(ArenaPet):
    """안농 도트. 이름표를 달지 않는다 (지나가는 현상이다 - 누구 포켓몬도 아니다)."""

    def make_nameplate(self):
        return


class ClickSprite(Sprite):
    """누를 수 있는 Sprite (유물). duel_scene.Sprite 와 같지만 클릭이 통과하지 않고, 손가락 커서 · 왼쪽 클릭을 받는다.

    투명색 자리는 윈도우가 알아서 통과시킨다. 맥은 커서를 좇아 빈 자리를 통과시켜야 한다 (Show._tick 이 update_hit).
    """

    def __init__(self, root, key, box, on_click):
        import tkinter as tk
        self.key, self.box = key, box
        self.at = None
        self.shown = None
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry("+%d+%d" % (-4000, -4000))
        bg = PLAT.transparent_window(self.win, "#%02x%02x%02x" % key)
        self.view = PLAT.SpriteView(self.win, bg, box[0], box[1], cursor="hand2")
        self.label = self.view.widget
        self.blank = self.load([Image.new("RGBA", box, (0, 0, 0, 0))])[0]
        self.view.show(self.blank)
        PLAT.raise_above(self.win)
        self.through = False
        self.label.bind("<Button-1>", lambda e: on_click())

    def update_hit(self, root):
        if not PLAT.NEEDS_HIT_TRACKING or self.at is None:
            return
        try:
            cx, cy = root.winfo_pointerxy()
            self.view.update_hit(cx - (self.at[0] - self.box[0] // 2), cy - (self.at[1] - self.box[1]))
        except Exception:                                   # noqa: BLE001
            pass


# ---------------------------------------------------------------- 장면
class Show(object):

    def __init__(self, app, ph, on_seen, on_done=None):
        self.app = app
        self.root = app.root
        self.ph = ph if isinstance(ph, dict) else {}
        self.kind = self.ph.get("kind")
        self.data = self.ph.get("data") if isinstance(self.ph.get("data"), dict) else {}
        self.on_seen = on_seen
        self.on_done = on_done
        self.closed = False
        self.phase = "new"
        self.jobs = []
        self.issued = []            # 건 예약 전부 (검사가 정리 뒤 남은 것이 없는지 본다)
        self.sprites = []
        self.pet = None
        self.glyph_sprite = None
        self.relic = None
        self.panel = None
        self.frozen = []            # 떨림 동안 멈춰 세운 바탕화면 도트
        self.frozen_all = []
        self.home = {}
        self.seen_done = False
        self.read = False
        self.beat = time.monotonic()
        self.hold_until = 0.0
        self.t0 = time.monotonic()
        self.watch_job = None
        self.tick_job = None
        self._n = 0
        self.work = None
        self.ground = None
        self.parts = 0
        self.drops = 0

    # ---------------- 도구 ----------------
    def after(self, t, fn):
        if self.closed:
            return None

        def run():
            if self.closed:
                return
            self.beat = time.monotonic()             # 진행했다 (멈춤 감시)
            try:
                fn()
            except Exception as e:                          # noqa: BLE001
                config.log("아르케 현상 오류(%s): %s\n%s" % (self.kind, e, traceback.format_exc()))
                self.cleanup()
        j = self.root.after(max(1, int(t)), run)
        self.jobs.append(j)
        self.issued.append(j)
        if len(self.jobs) > 400:
            self.jobs = self.jobs[-200:]
        return j

    def cancel(self, j):
        if j is not None:
            try:
                self.root.after_cancel(j)
            except Exception:                               # noqa: BLE001
                pass

    def hold(self, t):
        """이만큼(ms)은 진행이 없어도 멈춘 것이 아니다 (유물을 누르길 · 별을 보길 기다림)."""
        self.hold_until = max(self.hold_until, time.monotonic() + t / 1000.0)

    def left_ms(self):
        """끝 시각까지 남은 ms (SPEED 로 줄인 값)."""
        return ms(max(0.0, left_seconds(self.ph)) * 1000.0)

    def seen(self, img):
        """사람이 봤다 - on_seen 을 **한 번만** 부른다. 그 안에서 무엇이 터져도 연출은 이어진다."""
        if self.seen_done or self.closed:
            return
        self.seen_done = True
        if self.on_seen is None:                            # 일지에 안 남기는 연출 (창 제목이 맞았을 때의 떨림)
            return
        try:
            self.on_seen(self.ph, img)
        except Exception as e:                              # noqa: BLE001
            config.log("아르케 현상: 본 것 남기기 실패: %s" % e)

    def sprite(self, frames, cls=Sprite, **kw):
        """작은 창 하나 + 걸 수 있는 그림들. 창 크기는 가장 큰 그림에 맞춘다 (한 번 잡으면 안 바꾼다)."""
        frames = [_solid(f) for f in frames]
        box = (max(f.width for f in frames), max(f.height for f in frames))
        sp = cls(self.root, KEY, box, **kw) if kw else cls(self.root, KEY, box)
        self.sprites.append(sp)
        return sp, sp.load(frames)

    def drop_sprite(self, sp):
        if sp is None:
            return
        if sp in self.sprites:
            self.sprites.remove(sp)
        try:
            sp.destroy()
        except Exception:                                   # noqa: BLE001
            pass

    def _find_work(self):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        ov = self.app.overlay
        w = None
        if ov is not None:
            try:
                w = L.work_for(ov.area(), PLAT.screens(sw, sh), PLAT.screen_works(sw, sh))
            except Exception:                               # noqa: BLE001
                w = None
        return tuple(w or work_area(sw, sh))

    def _area(self):
        """바탕화면 포켓몬이 다니는 영역 (없으면 작업 영역의 아래쪽)."""
        ov = self.app.overlay
        if ov is not None:
            try:
                return tuple(ov.area())
            except Exception:                               # noqa: BLE001
                pass
        wl, wt, wr, wb = self.work
        return wl, wb - 300, wr, wb

    def fall(self, sp, handle, x, y0, y1, t, done):
        """sp 를 (x, y0) 에서 (x, y1) 로 떨어뜨린다 (발 기준 · 점점 빨라진다)."""
        steps = max(1, int(t / 33))
        sp.show(handle)

        def go(i):
            k = min(1.0, i / float(steps))
            sp.move(x, y0 + (y1 - y0) * k * k)
            if k >= 1.0:
                return done()
            self.after(33, lambda: go(i + 1))
        go(0)

    def walk(self, pet, fx, fy, t, done=None):
        """공습 장면의 walk 와 같다 (발 자리로 t ms 동안)."""
        tx, ty = L.feet_to_topleft(fx, fy, pet.fw, pet.fh)
        x0, y0 = pet.x, pet.y
        steps = max(1, int(t / 33))
        pet.state = "walk"

        def go(i):
            if self.closed or self.pet is not pet:
                return
            k = min(1.0, i / float(steps))
            nx, ny = x0 + (tx - x0) * k, y0 + (ty - y0) * k
            pet.walked = getattr(pet, "walked", 0) + abs(nx - pet.x) + abs(ny - pet.y)
            if i == 1 or (i % 4 == 0 and k < 1.0):
                pet.turn_to(tx - pet.x, ty - pet.y)
            pet.x, pet.y = nx, ny
            pet.place()
            if k >= 1.0:
                pet.state = "idle"
                return done() if done else None
            self.after(33, lambda: go(i + 1))
        go(1)

    def place_feet(self, pet, fx, fy):
        pet.x, pet.y = L.feet_to_topleft(fx, fy, pet.fw, pet.fh)
        pet.place()

    def part_done(self):
        """동시에 도는 갈래(안농 걷기 · 글자) 하나가 끝났다. 다 끝나면 정리."""
        self.parts -= 1
        if self.parts <= 0:
            self.cleanup()

    # ---------------- 시작 · 감시 ----------------
    def start(self):
        try:
            self.work = self._find_work()
            fn = getattr(self, "_" + str(self.kind), None) if self.kind in KINDS else None
            if fn is None:
                config.log("아르케 현상: 모르는 종류 %r - 건너뜁니다" % (self.kind,))
                return self.cleanup()
            self.beat = time.monotonic()
            self._watch()
            self._tick()
            fn()
        except Exception as e:                              # noqa: BLE001
            config.log("아르케 현상 준비 실패(%s): %s\n%s" % (self.kind, e, traceback.format_exc()))
            self.cleanup()

    def _watch(self):
        if self.closed:
            return
        now = time.monotonic()
        if (now - max(self.beat, self.hold_until)) * 1000.0 > STALL_MS or (now - self.t0) * 1000.0 > MAX_MS:
            config.log("아르케 현상(%s)이 멈춰 정리합니다 (단계 %s)" % (self.kind, self.phase))
            return self.cleanup()
        self.watch_job = self.root.after(500, self._watch)
        self.issued.append(self.watch_job)

    def _tick(self):
        """맥: 유물 창의 빈 자리를 통과시키고, 몇 초마다 창들을 '항상 위' 로 다시 (클릭 통과도 다시)."""
        if self.closed:
            return
        self._n += 1
        if self.relic is not None:
            self.relic.update_hit(self.root)
        if self._n % KEEP_TICKS == 0:
            for sp in list(self.sprites):
                try:
                    PLAT.keep_on_top(sp.win)
                    if getattr(sp, "through", False):
                        PLAT.keep_click_through(sp.win)
                except Exception:                           # noqa: BLE001
                    pass
        self.tick_job = self.root.after(TICK_MS, self._tick)
        self.issued.append(self.tick_job)

    # ---------------- 안농 ----------------
    def _unown(self):
        self.gi = int(self.data.get("glyph") or 0) % len(ART.GLYPHS)
        self.dir = -1 if self.data.get("dir") in (-1, "-1", "left") else 1
        wl, wt, wr, wb = self.work
        self.ground = wb - 2                                # 작업 표시줄 선
        self.mid = (wl + wr) / 2.0
        ov = self.app.overlay
        pet = None
        if ov is not None:
            try:
                pet = ov.make({"id": -3000, "num": UNOWN_NUM, "shiny": False, "tint": None,
                               "info": {"name": "안농", "species": "안농", "level": 1, "types": []}}, cls=UnownPet)
            except Exception as e:                          # noqa: BLE001
                config.log("아르케: 안농 도트 실패: %s" % e)
                pet = None
        self.parts = 1
        if pet is None:                                     # 도트가 없으면 글자만 가운데에 떨군다
            self.phase = "drop"
            return self.after(ms(300), self._drop_glyph)
        self.pet = pet
        ov.extra.append(pet)
        self.parts = 2
        sx = wl - pet.fw / 2.0 - 1 if self.dir > 0 else wr + pet.fw / 2.0 + 1
        self.place_feet(pet, sx, self.ground)
        pet.turn_to(self.dir, 0)
        self.phase = "walk"
        t = abs(self.mid - sx) * 1000.0 / WALK_SPEED
        # 첫 걸음은 다음 예약에서 - 화면 밖 자리에 먼저 서야 화면 끝에서 '걸어 들어온다' (바로 걸으면 한 걸음 안에서 시작)
        self.after(ms(120), lambda: self.walk(pet, self.mid, self.ground, ms(t), self._pause))

    def _pause(self):
        self.phase = "drop"
        if self.pet is not None:
            self.pet.state = "idle"
        self.after(ms(PAUSE_MS), self._drop_glyph)

    def _drop_glyph(self):
        img = ART.glyph(self.gi, GLYPH_K)
        frames = [img] + dissolve(img, FADE_STEPS, seed=self.gi)
        sp, hs = self.sprite(frames)
        self.glyph_sprite = sp
        if self.pet is not None:
            y0 = self.pet.y + self.pet.fh / 2.0 + img.height / 2.0
        else:
            y0 = self.ground - 80
        y0 = min(y0, self.ground - 4)
        self.fall(sp, hs[0], self.mid, y0, self.ground, ms(GLYPH_FALL_MS),
                  lambda: self._glyph_landed(sp, hs))

    def _glyph_landed(self, sp, hs):
        self.phase = "shown"
        self.seen(snap_unown(self.gi))
        if self.pet is not None:                            # 가던 쪽으로 마저 걷는다
            wl, wt, wr, wb = self.work
            ex = wr + self.pet.fw / 2.0 + 2 if self.dir > 0 else wl - self.pet.fw / 2.0 - 2
            t = abs(ex - self.mid) * 1000.0 / WALK_SPEED
            self.after(ms(250), lambda: self.walk(self.pet, ex, self.ground, ms(t), self._unown_gone))

        def fade(i):
            if i >= len(hs):
                self.drop_sprite(sp)
                self.glyph_sprite = None
                return self.part_done()
            sp.show(hs[i])
            self.after(ms(FADE_MS / float(FADE_STEPS)), lambda: fade(i + 1))
        self.after(ms(GLYPH_HOLD_MS), lambda: fade(1))

    def _unown_gone(self):
        self._drop_pet()
        self.part_done()

    def _drop_pet(self):
        pet, self.pet = self.pet, None
        if pet is None:
            return
        ov = self.app.overlay
        try:
            if ov is not None and pet in ov.extra:
                ov.extra.remove(pet)
        except Exception:                                   # noqa: BLE001
            pass
        try:
            pet.destroy()
        except Exception:                                   # noqa: BLE001
            pass

    # ---------------- 유물 ----------------
    def _relic(self):
        self.text = str(self.data.get("text") or "")
        g = self.data.get("glyph")
        self.rglyph = int(g) % len(ART.GLYPHS) if isinstance(g, (int, float)) or (isinstance(g, str) and g.isdigit()) \
            else None
        img = ART.relic(RELIC_K)
        frames = [img] + dissolve(img, FADE_STEPS, seed=7)
        self.relic, self.relic_hs = self.sprite(frames, cls=ClickSprite, on_click=self.on_click)
        x1, y1, x2, y2 = self._area()
        wl, wt, wr, wb = self.work
        self.rx = x1 + (x2 - x1) * 0.35
        self.ground = min(y2 - 4, wb - 2)
        self.phase = "fall"
        self.fall(self.relic, self.relic_hs[0], self.rx, wt + img.height, self.ground, ms(RELIC_FALL_MS),
                  self._relic_bounce)

    def _relic_bounce(self):
        seq = (-6, -8, -6, -3, 0)

        def go(i):
            if self.relic is None:
                return
            if i >= len(seq):
                return self._relic_wait()
            self.relic.move(self.rx, self.ground + seq[i])
            self.after(40, lambda: go(i + 1))
        go(0)

    def _relic_wait(self):
        if self.read:
            return
        self.phase = "wait"
        wait = max(ms(RELIC_MIN_WAIT), min(self.left_ms(), MAX_MS))
        self.hold(wait + 1000)
        self.wait_job = self.after(wait, self._relic_leave)

    def on_click(self):
        """유물을 눌렀다 - 새겨진 글을 띄운다 (한 번). 다시 눌러도 그대로."""
        if self.closed or self.read or self.relic is None:
            return
        self.read = True
        self.cancel(getattr(self, "wait_job", None))
        self.phase = "read"
        img = panel_image(self.text, self.rglyph)
        self.panel, hs = self.sprite([img])
        self.panel.show(hs[0])
        wl, wt, wr, wb = self.work
        half = img.width / 2.0
        px = max(wl + 4 + half, min(wr - 4 - half, self.rx))
        top = self.ground - self.relic.box[1] - 6
        self.panel.move(px, max(wt + img.height + 2, top))
        self.seen(img)
        read = min(READ_MAX_MS, READ_MIN_MS + READ_PER_CHAR * len(self.text))
        self.hold(ms(read) + 1000)
        self.after(ms(read), self._relic_leave)

    def _relic_leave(self):
        self.phase = "leave"
        if self.panel is not None:
            self.drop_sprite(self.panel)
            self.panel = None
        hs = self.relic_hs

        def go(i):
            if i >= len(hs) or self.relic is None:
                return self.cleanup()
            self.relic.show(hs[i])
            self.after(ms(FADE_MS / float(FADE_STEPS)), lambda: go(i + 1))
        go(1)

    # ---------------- 별 ----------------
    def _stars(self):
        pts = []
        for p in self.data.get("pts") or []:
            try:
                x, y = float(p[0]), float(p[1])
                mag = int(p[2]) if len(p) > 2 else 1
            except Exception:                               # noqa: BLE001
                continue
            pts.append((max(0.0, min(1.0, x)), max(0.0, min(1.0, y)), max(0, min(2, mag))))
        if not pts:
            return self.cleanup()
        try:
            band = float(self.data.get("band") or 0.25)
        except Exception:                                   # noqa: BLE001
            band = 0.25
        band = max(0.05, min(0.6, band))
        wl, wt, wr, wb = self.work
        bh = (wb - wt) * band
        self.star_pts = pts
        self.star_ratio = bh / float(max(1, wr - wl))
        self.phase = "rise"
        placed = []
        for x, y, mag in pts:
            im = ART.star(mag, STAR_K)
            sp, hs = self.sprite([im])
            sp.move(wl + x * (wr - wl), wt + y * bh + im.height / 2.0)
            placed.append((sp, hs[0]))

        def show(i):
            if i >= len(placed):
                return self._stars_shown(placed)
            sp, h = placed[i]
            sp.show(h)
            self.after(ms(STAR_GAP), lambda: show(i + 1))
        show(0)

    def _stars_shown(self, placed):
        self.phase = "shown"
        self.seen(snap_stars(self.star_pts, self.star_ratio))
        stay = max(ms(STAR_MIN_MS), min(self.left_ms(), MAX_MS))
        self.hold(stay + 1000)

        def hide(i):
            if i >= len(placed):
                return self.cleanup()
            placed[i][0].hide()
            self.after(ms(STAR_GAP), lambda: hide(i + 1))
        self.after(stay, lambda: hide(0))

    # ---------------- 물방울 ----------------
    def _drip(self):
        try:
            self.count = max(1, min(DRIP_MAX, int(self.data.get("count") or 1)))
        except Exception:                                   # noqa: BLE001
            self.count = 1
        d = ART.drip(3)
        splash = d.resize((d.width + d.width // 2, max(2, d.height // 2)), Image.NEAREST)
        self.drip_sp, self.drip_hs = self.sprite([d, splash])
        x1, y1, x2, y2 = self._area()
        wl, wt, wr, wb = self.work
        self.dx = (x1 + x2) / 2.0
        self.dtop = max(wt + d.height, y1 - 220)
        self.ground = min(y2 - 4, wb - 2)
        self.phase = "drip"
        self._drip_one()

    def _drip_one(self):
        sp, hs = self.drip_sp, self.drip_hs

        def landed():
            sp.show(hs[1])
            self.after(ms(DRIP_SPLASH_MS), after_splash)

        def after_splash():
            sp.hide()
            self.drops += 1
            if self.drops >= self.count:
                self.seen(snap_drip(self.count))
                return self.after(ms(400), self.cleanup)
            self.after(ms(DRIP_GAP - DRIP_FALL_MS - DRIP_SPLASH_MS), self._drip_one)
        self.fall(sp, hs[0], self.dx, self.dtop, self.ground, ms(DRIP_FALL_MS), landed)

    # ---------------- 모래바람 ----------------
    def _sand(self):
        self.dir = -1 if self.data.get("dir") in (-1, "-1", "left") else 1
        x1, y1, x2, y2 = self._area()
        wl, wt, wr, wb = self.work
        grains = []
        for i in range(SAND_N):
            sp, hs = self.sprite([ART.sand(2, i)])
            sp.show(hs[0])
            gy = y1 + (y2 - y1) * (0.25 + 0.6 * ((i * 37) % 10) / 10.0)
            sx = wl - 20 - i * 30 if self.dir > 0 else wr + 20 + i * 30
            ex = wr + 40 if self.dir > 0 else wl - 40
            sp.move(sx, gy)
            grains.append((sp, sx, ex, gy, i))
        self.parts = len(grains)
        self.phase = "blow"
        for g in grains:
            self.after(ms(g[4] * SAND_STAGGER), lambda g=g: self._blow(*g))

    def _blow(self, sp, sx, ex, gy, i):
        t = ms(SAND_MS)
        steps = max(1, int(t / 33))

        def go(k):
            f = min(1.0, k / float(steps))
            sp.move(sx + (ex - sx) * f, gy + math.sin(f * math.pi * 3 + i) * 10)
            if f >= 1.0:
                sp.hide()
                if self.parts <= 1:
                    self.seen(snap_dir("sand", self.dir))
                return self.part_done()
            self.after(33, lambda: go(k + 1))
        go(0)

    # ---------------- 떨림 ----------------
    def _tremor(self):
        self.dir = -1 if self.data.get("dir") in (-1, "-1", "left") else 1
        ov = self.app.overlay
        if ov is None or getattr(ov, "locked", False):
            return self.cleanup()                           # 다른 장면이 바탕화면을 쥐고 있다
        for p in list(ov.pets.values()):
            if (p.battling or getattr(p, "dragging", False) or p.state == "held"
                    or getattr(p, "evolving", False)):
                continue
            p.battling = True
            p.state = "idle"
            self.home[id(p)] = (p.x, p.y)
            self.frozen.append(p)
        self.frozen_all = list(self.frozen)
        if not self.frozen:
            return self.cleanup()
        self.phase = "shake"

        def go(i):
            if i >= len(TREMOR_SEQ):
                return self._tremor_face()
            for p in self.frozen:
                hx, hy = self.home[id(p)]
                p.x = hx + TREMOR_SEQ[i]
                p.place()
            self.after(ms(TREMOR_STEP), lambda: go(i + 1))
        go(0)

    def _tremor_face(self):
        self.phase = "face"
        for p in self.frozen:
            hx, hy = self.home[id(p)]
            p.x, p.y = hx, hy
            p.place()
            try:
                p.face_towards(p.x + self.dir * 100)
            except Exception:                               # noqa: BLE001
                pass
        self.seen(snap_dir("tremor", self.dir))
        self.after(ms(TREMOR_FACE_MS), self.cleanup)

    # ---------------- 정리 ----------------
    def cleanup(self):
        """원상 복귀. **몇 번을 불러도 안전하다** (끝 · 예외 · 멈춤 · 로그아웃 모두 여기로)."""
        if self.closed:
            return
        self.closed = True
        self.phase = "done"
        for j in [self.watch_job, self.tick_job] + list(self.jobs):
            self.cancel(j)
        self.watch_job = self.tick_job = None
        self.jobs = []
        for sp in list(self.sprites):
            try:
                sp.destroy()
            except Exception:                               # noqa: BLE001
                pass
        self.sprites = []
        self.glyph_sprite = self.relic = self.panel = None
        self._drop_pet()
        for p in self.frozen:
            try:
                hx, hy = self.home.get(id(p), (p.x, p.y))
                p.x, p.y = hx, hy
                p.battling = False
                p.state = "idle"
                p.place()
            except Exception:                               # noqa: BLE001
                pass
        self.frozen = []
        if self.on_done:
            try:
                self.on_done()
            except Exception:                               # noqa: BLE001
                config.log("아르케 현상 끝 처리 실패: %s" % traceback.format_exc())
