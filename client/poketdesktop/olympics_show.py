# -*- coding: utf-8 -*-
"""포스크탑 올림픽 — 바탕화면 경기 중계 (한 조).

    s = Show(app, heat, on_done=None, replay=False)    heat = 서버의 조 각본 (/api/olympics/live · heat)
    s.start()      s.stop()      s.alive

같은 조 8마리(모두 실제 다른 사람 포켓몬)가 내 바탕화면에서 뛴다. 기록은 서버가 이미 정했다 - 여기서는 그 기록대로
그리기만 한다. 달리기 곡선은 씨앗으로 common/olympics.race_curve 가 만든다 (같은 조를 보는 누구 화면에서도 같다).

    달리기형  100m · 수영 50m(25m 를 갔다 온다) · 마라톤(바탕 둘레 두 바퀴) - 8마리가 같이 달린다
    시기형    장대 · 역도 · 원반 · 스키점프 - 차례로 세 번씩, 오른쪽 위 점수판이 바뀐다

## 화면

내 포켓몬이 있는 모니터 아래쪽에 경기장을 깐다. 그동안 바탕화면 포켓몬 · 알은 잠깐 숨는다(overlay.set_only(-1)) -
끝나면 되살린다. 선 · 결승선 · 물 · 이름은 클릭이 지나가는 투명 층(fx_layer)에 **한 번만** 그린다 (맥 Tk 는 캔버스를
바꿀 때마다 통째로 다시 칠한다 - 틱마다 바꾸는 것은 선수 창 자리뿐이다). 층은 선수보다 **먼저** 만든다 - 선수 창이 그
위에 온다 (물에 잠긴 수영 선수는 창 아래를 잘라서 만든다).

## 응원

경기 중 내 포켓몬을 누르면 '♥ 힘내!' 가 뜬다. **기록에는 아무 영향이 없다** (기록은 서버가 이미 정했다).

선수 도트는 이미 받는 동작 그림(걷기 · 서기 · 깡충 · 아파함)만 쓴다. 없는 종은 걷기 그림으로 대신한다.
"""
import math
import time
import tkinter as tk

from PIL import Image, ImageDraw

from common import olympics as O

from . import config
from . import fx_layer
from . import platform_os as PLAT
from . import ui_common as U
from .overlay import Pet
from .sprites import DOWN, LEFT, RIGHT, UP, flatten_rgba, premultiply

TICK_MS = 33
INTRO_MS = 2600
OUTRO_MS = 3200
MARATHON_SHOW = 95.0        # 2:10:00 이 중계로 몇 초인가
MARATHON_MAX = 118.0        # 조의 가장 느린 선수도 이 안에 (프로그램 끝 END 전에 끝나게 - 독립 검토 #6)
FIELD_SHOW = 72.0           # 시기형 한 조를 이 안에 (초)
ATTEMPT_MIN, ATTEMPT_MAX = 1500, 3200
LABEL_W = 170               # 달리기형 왼쪽 이름 칸
KEY = (255, 0, 255)
MINE = "#ffc043"
INK = "#101014"
WHITE = "#f4f6fb"
WATER = "#2f6fc4"
WATER_HI = "#8cc4ff"
LINE = "#e9edf5"
GOOD = "#5fd97a"
BAD = "#ff6b6b"


def _font(size=9, bold=True):
    return (U.FAMILY, U.pt(size), "bold") if bold else (U.FAMILY, U.pt(size))


# ---------------------------------------------------------------- 선수 도트
class OlyPet(Pet):
    """중계에 나오는 선수. overlay.extra 에 넣는다 - 서버가 주는 내 포켓몬 목록과 섞이지 않게.

    스스로 돌아다니지 않는다(battling). 프레임만 넘기고, 자리는 Show 가 정한다. 끌기 · 메뉴 · 두 번 누르기는 없다.
    """

    def __init__(self, overlay, mon, anim):
        Pet.__init__(self, overlay, mon, anim)
        self.battling = True
        self.state = "idle"
        self.on_click = None

    def update(self, ms):
        self.advance(ms)

    def on_press(self, e):
        self.hide_tip()
        cb = self.on_click
        if cb is not None:
            try:
                cb(self)
            except Exception:                               # noqa: BLE001
                pass

    def on_motion(self, e):
        pass

    def on_release(self, e):
        pass

    def on_double(self, e):
        pass

    def on_menu(self, e):
        pass

    def show_tip(self):
        pass

    def can_drag(self):
        return False


# ---------------------------------------------------------------- 움직이는 소품 (바벨 · 원반)
def _pix(colors, rows, scale):
    im = Image.new("RGBA", (len(rows[0]), len(rows)), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in colors:
                im.putpixel((x, y), colors[ch] + (255,))
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST)


def barbell_image(width):
    """바벨: 가운데 봉 + 양끝 원판. width 에 맞춰 늘린다."""
    s = max(2, int(width / 40))
    n = max(12, int(width / s))
    rows = []
    for y in range(7):
        line = ""
        for x in range(n):
            plate = x < 4 or x >= n - 4
            if plate and 0 <= y <= 6 and (x in (1, 2) or x in (n - 3, n - 2)):
                line += "P"
            elif y == 3:
                line += "b"
            else:
                line += "."
        rows.append(line)
    return _pix({"P": (52, 58, 78), "b": (196, 200, 212)}, rows, s)


def disc_image(px):
    rows = ["..ww..", ".wGGw.", "wGggGw", "wGggGw", ".wGGw.", "..ww.."]
    return _pix({"w": (236, 238, 244), "G": (120, 128, 150), "g": (240, 196, 72)}, rows, max(2, int(px / 6)))


class Prop(object):
    """작은 그림 창 하나 (클릭이 지나간다). 자리가 바뀐 때만 옮긴다 (맥 CPU)."""

    def __init__(self, root, img, at=(0, 0)):
        """at = 처음 둘 자리 (화면 안). 화면 밖에 만들었다 바로 없애면 맥 Tk 의 update() 가 멈출 수 있다."""
        self.root = root
        self.w, self.h = img.size
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self._pos = None
        bg = PLAT.transparent_window(self.win, "#%02x%02x%02x" % KEY)
        self.view = PLAT.SpriteView(self.win, bg, self.w, self.h)
        frame = flatten_rgba(premultiply(img), KEY)
        self.photos = self.view.frames([frame], KEY)
        self.view.show(self.photos[0])
        self.win.geometry("+%d+%d" % (int(at[0]), int(at[1])))
        PLAT.raise_above(self.win)
        try:
            PLAT.make_click_through(self.win)
        except Exception:                                   # noqa: BLE001
            pass
        self.win.withdraw()
        self.shown = False

    def put(self, cx, cy):
        """그림 가운데를 (cx, cy) 에."""
        pos = (int(cx - self.w / 2.0), int(cy - self.h / 2.0))
        if pos != self._pos:
            self._pos = pos
            self.win.geometry("+%d+%d" % pos)
        if not self.shown:
            self.shown = True
            PLAT.show_again(self.win)
            PLAT.raise_above(self.win)

    def hide(self):
        if self.shown:
            self.shown = False
            try:
                self.win.withdraw()
            except Exception:                               # noqa: BLE001
                pass

    def destroy(self):
        try:
            self.view.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass


# ---------------------------------------------------------------- 화면 고르기
def stage_screen(app):
    """내 포켓몬 활동 영역이 있는 모니터의 작업 영역 (x1, y1, x2, y2)."""
    root = app.root
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    try:
        works = list(PLAT.screen_works(sw, sh)) or [(0, 0, sw, sh)]
    except Exception:                                       # noqa: BLE001
        works = [(0, 0, sw, sh)]
    try:
        ax1, ay1, ax2, ay2 = app.overlay.area()
        cx, cy = (ax1 + ax2) / 2.0, (ay1 + ay2) / 2.0
        for w in works:
            if w[0] <= cx < w[2] and w[1] <= cy < w[3]:
                return tuple(w)
    except Exception:                                       # noqa: BLE001
        pass
    return tuple(works[0])


def heat_rank(event, ents):
    """조 안 순위 {entryId: 순위} - 기록 차례 (같으면 서버의 전체 순위 차례)."""
    order = sorted(ents, key=lambda e: (O.rank_key(event, e.get("record")), e.get("rank") or 9999))
    return dict((e["entryId"], i) for i, e in enumerate(order, 1))


# ---------------------------------------------------------------- 중계
class Show(object):

    def __init__(self, app, heat, on_done=None, replay=False):
        self.app, self.root = app, app.root
        self.heat = heat
        self.ev = heat["event"]
        self.on_done = on_done
        self.replay = replay
        self.alive = False
        self.aborted = False
        self.ents = sorted(heat.get("entrants") or [], key=lambda e: e.get("lane", 0))
        self.ranks = heat_rank(self.ev, self.ents)
        self.mine = next((e for e in self.ents if e.get("mine")), None)
        self.pets = {}              # entryId -> OlyPet (도트를 못 구한 선수는 없다)
        self.props = []
        self.layer = None
        self.bar = None
        self.bubble = None
        self.said = []              # 띄운 말 (검사 · 기록)
        self.moves = 0              # 선수 창을 옮긴 횟수 (검사가 맥 CPU 를 본다)
        self._job = None
        self._t0 = None
        self._last = None
        self.phase = "intro"
        self.steps = []
        self.result = None

    # ---------------------------------------------------------------- 시작 · 끝
    def start(self):
        ov = self.app.overlay
        if ov is None or not self.ents:
            return self._done()
        self.alive = True
        try:
            ov.set_only(-1)                 # 바탕화면 포켓몬 · 알은 잠깐 숨는다
            ov.block_names()
            self._stage()
            self.layer = fx_layer.open_layer(self.root, (self.x1 - 10, self.top - 40, self.x2 + 10, self.bottom + 10))
            self._head()
            self._make_athletes()
            if self.ev in O.RACES:
                self._race_setup()
            else:
                self._field_setup()
        except Exception as e:                              # noqa: BLE001
            # 여기서 터진 채로 두면 포켓몬 · 이름표가 숨은 채, 풀숲 · 집중 · 대전이 '중계 중' 으로 갇힌다 (독립 검토 #3)
            import traceback
            config.log("올림픽 중계 준비 실패: %s\n%s" % (e, traceback.format_exc()))
            self.aborted = True
            self._finish()
            return self
        self._say_mine("%s 선수 입장!" % self._name(self.mine) if self.mine else None)
        self._t0 = self._last = time.monotonic()
        self._job = self.root.after(TICK_MS, self._tick)
        return self

    def stop(self):
        """중간에 닫기 (×) · 로그아웃. 기록은 서버에 이미 있다."""
        if self.alive:
            self.aborted = True
            self._finish()

    def _finish(self):
        if not self.alive:
            return
        self.alive = False
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
            self._job = None
        ov = self.app.overlay
        for p in list(self.pets.values()):
            try:
                if ov is not None and p in ov.extra:
                    ov.extra.remove(p)
                p.destroy()
            except Exception:                               # noqa: BLE001
                pass
        self.pets = {}
        for pr in self.props:
            pr.destroy()
        self.props = []
        self._close_bubble()
        for w in (getattr(self, "head_win", None),):
            try:
                if w is not None:
                    w.destroy()
            except Exception:                               # noqa: BLE001
                pass
        if self.layer is not None:
            for f in list(getattr(self.layer, "floats", []) or []):
                try:
                    f.stop()
                except Exception:                           # noqa: BLE001
                    pass
            self.layer.destroy()
            self.layer = None
        if ov is not None:
            try:
                ov.release_names()
                # 되살릴 때: 중계 중에 (다른 PC 에서 이어 받은) 집중이 시작됐으면 그 포켓몬만 (독립 검토 #5)
                f = getattr(self.app, "focus", None)
                keep = getattr(f, "pet_id", None) if (f is not None and f.active()) else None
                ov.set_only(keep)
            except Exception:                               # noqa: BLE001
                pass
        self._done()

    def _done(self):
        mine = self.mine
        self.result = {"event": self.ev, "aborted": self.aborted, "replay": self.replay,
                       "record": mine.get("record") if mine else None,
                       "text": mine.get("text") if mine else None,
                       "heatRank": self.ranks.get(mine["entryId"]) if mine else None,
                       "heatSize": len(self.ents), "rank": mine.get("rank") if mine else None,
                       "total": self.heat.get("total"), "entryId": mine.get("entryId") if mine else None}
        cb, self.on_done = self.on_done, None
        if cb is not None:
            try:
                cb(self, self.result)
            except Exception as e:                          # noqa: BLE001
                config.log("올림픽 중계 끝 처리 실패: %s" % e)

    # ---------------------------------------------------------------- 경기장
    def _stage(self):
        wx1, wy1, wx2, wy2 = stage_screen(self.app)
        self.th = int(self.app.overlay.settings.get("targetHeight", 64) or 64)
        W = min(1100, max(480, (wx2 - wx1) - 80))
        cx = (wx1 + wx2) / 2.0
        self.x1, self.x2 = int(cx - W / 2.0), int(cx + W / 2.0)
        self.W = self.x2 - self.x1
        self.bottom = int(wy2 - 30)
        n = max(1, len(self.ents))
        self.G = max(18, int(self.th * 0.40))
        H = {"sprint": (n - 1) * self.G + self.th + 40, "swim": (n - 1) * self.G + self.th + 40,
             "marathon": 300, "pole": self.th * 2 + 170, "lift": self.th * 2 + 110,
             "discus": self.th * 2 + 130, "ski": 320}[self.ev]
        self.top = int(max(wy1 + 40, self.bottom - H))

    def _head(self):
        """경기장 위의 이름 띠: 종목 · 조 · (다시 보기) · 닫기 ×."""
        try:
            w = tk.Toplevel(self.root)
            w.overrideredirect(True)
            w.configure(bg=U.TIP_BG)
            day = self.heat.get("dayNo")
            text = "포스크탑 올림픽%s · %s · %d조%s" % (
                " %d일째" % day if day else "", O.EV[self.ev]["kr"], self.heat.get("heat") or 1,
                "  (다시 보기)" if self.replay else "")
            tk.Label(w, text=text, bg=U.TIP_BG, fg=MINE, font=_font(10), padx=10, pady=3).pack(side="left")
            x = tk.Label(w, text=" × ", bg=U.TIP_BG, fg=U.FG_DIM, font=_font(11), cursor="hand2")
            x.pack(side="left")
            x.bind("<Button-1>", lambda _e: self.stop())
            w.geometry("+%d+%d" % (self.x1, self.top - 34))
            PLAT.raise_above(w)
            self.head_win = w
        except Exception as e:                              # noqa: BLE001
            config.log("올림픽 이름 띠 실패: %s" % e)
            self.head_win = None

    def _name(self, e):
        return ((e or {}).get("pokemon") or {}).get("name") or "?"

    def _label(self, e):
        return "%s (%s)" % (self._name(e), e.get("user") or "?")

    def _make_athletes(self):
        ov = self.app.overlay
        for i, e in enumerate(self.ents):
            p = e.get("pokemon") or {}
            mon = {"id": -3000 - i, "num": p.get("num"), "shiny": bool(p.get("shiny")), "tint": p.get("tint"),
                   "info": {"name": p.get("name"), "species": p.get("species"), "level": "", "types": []}}
            if p.get("look") and p.get("look") != p.get("num"):
                mon["lookNum"] = p["look"]
            try:
                pet = ov.make(mon, cls=OlyPet)
                if pet is None and mon.get("lookNum"):
                    mon.pop("lookNum", None)
                    pet = ov.make(mon, cls=OlyPet)
            except Exception as ex:                         # noqa: BLE001
                config.log("올림픽 선수 도트 실패: %s" % ex)
                pet = None
            if pet is None:
                continue
            ov.extra.append(pet)
            pet.ent = e
            if e.get("mine"):
                pet.on_click = self._cheer
            self.pets[e["entryId"]] = pet

    # ---------------------------------------------------------------- 그리기 도움
    def _foot(self, pet):
        """발 자리 = 몸 가로 기준점(ax) · 그림 맨 아래(fh). ay 는 칸 한가운데라 땅에 세우는 데는 안 맞는다
        (큰 포켓몬은 발이 선 아래로 내려간다)."""
        return pet.x + pet.ax, pet.y + pet.fh

    def _put(self, pet, fx, fy):
        x, y = fx - pet.ax, fy - pet.fh
        if (int(x), int(y)) != (int(pet.x), int(pet.y)):
            pet.x, pet.y = x, y
            pet.place()
            self.moves += 1

    def _walk(self, pet, fx, fy):
        """발을 (fx, fy) 로 걸어 옮긴다 (다리가 거리만큼 움직인다)."""
        ox, oy = self._foot(pet)
        dx, dy = fx - ox, fy - oy
        if abs(dx) + abs(dy) >= 0.5:
            if pet.anim_name != "Walk" and not pet.once:
                pet.play("Walk")
            pet.state = "walk"
            pet.turn_to(dx, dy)
            pet.walked += math.hypot(dx, dy)
        self._put(pet, fx, fy)

    def _stand(self, pet, face=None):
        """선다. 그림을 바꾸면 Pet.play 는 칸 한가운데를 붙든다 - 발이 땅에서 뜨므로 발 자리로 다시 놓는다
        (데모 11/06: 역도 단 위의 보스로라가 한참 떠 있었다)."""
        fx, fy = self._foot(pet)
        pet.state = "idle"
        if not pet.once:
            pet.play(pet.rest_anim())
            self._put(pet, fx, fy)
        if face is not None:
            if face in getattr(pet, "photos", {}) and pet.facing != face:
                pet.facing = face
                pet.redraw()

    def _text(self, sx, sy, text, color=WHITE, size=9, anchor="w", tag=None):
        if self.layer is None:
            return []
        x, y = self.layer.to_local(sx, sy)
        cv = self.layer.cv
        f = _font(size)
        return [cv.create_text(x + 1, y + 1, text=text, fill=INK, font=f, anchor=anchor, tags=tag),
                cv.create_text(x, y, text=text, fill=color, font=f, anchor=anchor, tags=tag)]

    def _line(self, a, b, color=LINE, width=2, dash=None, tag=None):
        if self.layer is None:
            return None
        x1, y1 = self.layer.to_local(*a)
        x2, y2 = self.layer.to_local(*b)
        return self.layer.cv.create_line(x1, y1, x2, y2, fill=color, width=width, dash=dash, tags=tag)

    def _rect(self, a, b, fill, outline="", tag=None):
        if self.layer is None:
            return None
        x1, y1 = self.layer.to_local(*a)
        x2, y2 = self.layer.to_local(*b)
        return self.layer.cv.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, tags=tag)

    def _float(self, pet_or_xy, text, color=WHITE, ms=1400):
        if self.layer is None:
            return
        if isinstance(pet_or_xy, tuple):
            sx, sy = pet_or_xy
        else:
            fx, fy = self._foot(pet_or_xy)
            sx, sy = fx, pet_or_xy.y - 8
        try:
            fx_layer.FloatText(self.layer, sx, sy, text, color=color, ms=ms)
        except Exception:                                   # noqa: BLE001
            pass

    def _say(self, pet, text, ms=2600):
        if not text:
            return
        self.said.append(text)
        if pet is None:
            return
        self._close_bubble()
        try:
            from .visit import Bubble
            self.bubble = Bubble(self.root, pet, text, ms=ms)
        except Exception as e:                              # noqa: BLE001
            config.log("올림픽 말풍선 실패: %s" % e)

    def _say_mine(self, text, ms=2600):
        pet = self.pets.get(self.mine["entryId"]) if self.mine else None
        self._say(pet, text, ms)

    def _close_bubble(self):
        b, self.bubble = self.bubble, None
        if b is not None:
            try:
                b.close()
            except Exception:                               # noqa: BLE001
                pass

    def _cheer(self, pet):
        """응원 - 연출뿐이다. 기록은 서버가 이미 정했다."""
        self._float(pet, "♥ 힘내!", color="#ff7eb6", ms=1100)
        self.said.append("♥")

    # ---------------------------------------------------------------- 틱
    def _tick(self):
        self._job = None
        if not self.alive:
            return
        now = time.monotonic()
        dt = now - self._last
        self._last = now
        try:
            if self.ev in O.RACES:
                self._race_tick(now - self._t0)
            else:
                self._field_tick(dt)
        except Exception as e:                              # noqa: BLE001
            import traceback
            config.log("올림픽 중계 오류: %s\n%s" % (e, traceback.format_exc()))
            return self._finish()
        if self.alive:
            self._job = self.root.after(TICK_MS, self._tick)

    # ================================================================ 달리기형
    def _race_setup(self):
        ev = self.ev
        n = len(self.ents)
        self.lane_y = {}
        self.T = {}
        self.curve = {}
        self.done_at = {}
        self.leader = None
        self.lead_said = 0.0
        self.slip_said = set()
        self.check_said = set()
        worst = max([e.get("record") or 0 for e in self.ents] or [0]) or O.EV[ev]["base"]
        raw = dict((e["entryId"], e.get("record") or worst * 1.08) for e in self.ents)
        scale = 1.0
        if ev == "marathon":
            scale = min(MARATHON_SHOW / O.EV["marathon"]["base"], MARATHON_MAX / max(raw.values()))
        for i, e in enumerate(self.ents):
            self.T[e["entryId"]] = raw[e["entryId"]] * scale
            slip = next((t.get("at") for t in e.get("tries") or [] if t.get("slip")), None)
            self.curve[e["entryId"]] = O.race_curve(e.get("seed") or i, ev, slip)
            self.slip_at = getattr(self, "slip_at", {})
            self.slip_at[e["entryId"]] = slip
        if ev == "marathon":
            return self._marathon_setup()
        self.x_start = self.x1 + LABEL_W
        self.x_end = self.x2 - 40
        for i, e in enumerate(self.ents):
            self.lane_y[e["entryId"]] = self.bottom - (n - 1 - i) * self.G
        top = self.bottom - (n - 1) * self.G - int(self.G * 0.6)
        if ev == "swim":
            for i, e in enumerate(self.ents):           # 물 띠 (선수 창은 그 위에서 허리 아래가 잘린다)
                y = self.lane_y[e["entryId"]] - self._waist()
                self._rect((self.x_start - 14, y - 2), (self.x_end + 14, y + self.G * 0.55), WATER)
                for k in range(int((self.x_end - self.x_start) / 26)):
                    x = self.x_start + k * 26 + (i % 2) * 13
                    self._line((x, y + 1), (x + 9, y + 1), WATER_HI, 2)
            self._line((self.x_end + 14, top), (self.x_end + 14, self.bottom + 6), "#d9dee8", 5)   # 반환 벽
        else:
            for i in range(n + 1):                      # 레인 줄
                y = self.bottom - (n - 1 - i) * self.G + self.G * 0.45
                self._line((self.x_start - 10, y), (self.x_end + 30, y), "#c9ced8", 1, dash=(4, 4))
            fx = self.x_end
            sq = max(4, int(self.G / 4))
            for k in range(int((self.bottom + self.G * 0.45 - top) / sq) + 1):    # 결승선 (체크무늬)
                for j in range(2):
                    color = INK if (k + j) % 2 else WHITE
                    self._rect((fx + j * sq, top + k * sq), (fx + (j + 1) * sq, top + (k + 1) * sq), color)
        self._line((self.x_start, top), (self.x_start, self.bottom + self.G * 0.45), "#ffffff", 3)   # 출발선
        for e in self.ents:
            self._text(self.x_start - 14, self.lane_y[e["entryId"]] - self.G * 0.35, self._label(e),
                       MINE if e.get("mine") else WHITE, 9, "e")
        for e in self.ents:
            p = self.pets.get(e["entryId"])
            if p is not None:
                self._put(p, self.x_start - 4, self.lane_y[e["entryId"]])
                self._stand(p, RIGHT)
                if ev == "swim":
                    self._dip(p)

    def _waist(self):
        return int(self.th * 0.35)

    def _dip(self, pet):
        """물에 잠긴 것처럼: 창 아래(발 위 _waist px)를 잘라 낸다. 창 크기는 한 번만 바꾼다.
        (맥 SpriteView 에는 bw 가 없다 - 없으면 그림 폭)"""
        try:
            h = max(8, int(pet.fh - self._waist()))
            w = max(getattr(pet.view, "bw", 0) or 0, pet.fw)
            pet.win.geometry("%dx%d" % (int(w), h))
        except Exception as e:                              # noqa: BLE001
            config.log("올림픽 수영 물 자르기 실패: %s" % e)

    def _race_tick(self, t):
        if t < INTRO_MS / 1000.0:
            if self.phase == "intro" and t > INTRO_MS / 1000.0 - 0.8:
                self.phase = "set"
                self._float((self.x_start, self.top + 4) if self.ev != "marathon" else self.start_xy, "준비…",
                            WHITE, 800)
            return
        rt = t - INTRO_MS / 1000.0
        if self.phase in ("intro", "set"):
            self.phase = "run"
            self._float((self.x_start, self.top + 4) if self.ev != "marathon" else self.start_xy, "탕! 출발!",
                        MINE, 1200)
            self._say_mine("출발!", 1400)
        moving = 0
        lead_id, lead_d = None, -1.0
        crossed = []
        for e in self.ents:
            eid = e["entryId"]
            T = self.T[eid]
            frac = min(1.0, rt / T) if T > 0 else 1.0
            d = O.at_curve(self.curve[eid], frac)
            if frac < 1.0:
                moving += 1
                if d > lead_d:
                    lead_id, lead_d = eid, d
            elif eid not in self.done_at:
                crossed.append(e)
        for e in sorted(crossed, key=lambda x: self.T[x["entryId"]]):    # 한 틱에 여럿이면 기록 차례로
            self.done_at[e["entryId"]] = self.T[e["entryId"]]
            self._crossed(e)
        for e in self.ents:
            eid = e["entryId"]
            T = self.T[eid]
            frac = min(1.0, rt / T) if T > 0 else 1.0
            d = O.at_curve(self.curve[eid], frac)
            pet = self.pets.get(eid)
            if pet is None:
                continue
            if self.ev == "marathon":
                self._marathon_put(pet, eid, d, frac >= 1.0)
            else:
                self._lane_put(pet, eid, d, frac >= 1.0)
            sa = self.slip_at.get(eid)
            if sa is not None and eid not in self.slip_said and frac >= sa:
                self.slip_said.add(eid)
                if pet.anim_for("Hurt") is not None:
                    pet.play("Hurt", once=True)
                if e.get("mine"):
                    self._say(pet, "앗, %s!" % ("물을 먹었어요" if self.ev == "swim" else "넘어졌어요"), 1800)
        # 중계: 선두가 바뀌면 (너무 자주 말하지 않게)
        if lead_id is not None and lead_id != self.leader and rt > 0.3 * min(self.T.values()):
            if rt - self.lead_said > 2.6:
                self.lead_said = rt
                le = next(e for e in self.ents if e["entryId"] == lead_id)
                self._say(self.pets.get(lead_id), "%s 선두!" % self._name(le), 1800)
            self.leader = lead_id
        elif self.leader is None:
            self.leader = lead_id
        if self.ev == "marathon":
            self._marathon_board(rt)
        if not moving:
            if self.phase == "run":
                self.phase = "outro"
                self.outro_at = rt
                self._outro()
            elif rt - self.outro_at > OUTRO_MS / 1000.0:
                self._finish()

    def _lane_put(self, pet, eid, d, done):
        fy = self.lane_y[eid]
        if self.ev == "swim":
            L = self.x_end - self.x_start
            back = d > 0.5
            x = self.x_start + (d / 0.5) * L if not back else self.x_end - ((d - 0.5) / 0.5) * L
            if done:
                self._put(pet, self.x_start, fy)
                if pet.facing != LEFT:
                    pet.turn_to(-1, 0)
                pet.state = "idle"
                return
            bob = 2 * math.sin(time.monotonic() * 7 + eid)
            want = LEFT if back else RIGHT
            ox, _oy = self._foot(pet)
            pet.state = "walk"
            pet.walked += abs(x - ox)
            if pet.facing != want:
                pet.turn_to(-1 if back else 1, 0)
            self._put(pet, x, fy + bob)
            return
        x = self.x_start + d * (self.x_end - self.x_start)
        if done:
            ox, _oy = self._foot(pet)
            if abs(ox - (self.x_end + 18)) > 1:
                self._walk(pet, min(self.x_end + 18, ox + 3), fy)
            else:
                self._stand(pet, DOWN)
            return
        self._walk(pet, x, fy)

    def _crossed(self, e):
        """결승선을 지났다: 오른쪽에 순위와 기록 (한 번만 그린다)."""
        k = len(self.done_at)
        if self.ev == "marathon":
            self._text(self.board_x, self.board_y + 16 + k * 16, "%d. %s  %s" % (k, self._label(e), e.get("text")),
                       MINE if e.get("mine") else WHITE, 9, "w")
            pet = self.pets.get(e["entryId"])
            if k == 1 and pet is not None:
                self._say(pet, "%s 1위로 들어왔어요!" % self._name(e), 2200)
            return
        y = self.lane_y[e["entryId"]] - self.G * 0.35
        x = (self.x_start - 14) if self.ev == "swim" else (self.x_end + 30)
        anchor = "e" if self.ev == "swim" else "w"
        if self.ev == "swim":
            x = self.x2 - 4
            anchor = "e"
        self._text(x, y, "%d위 %s" % (k, e.get("text")), MINE if e.get("mine") else (GOOD if k == 1 else WHITE),
                   9, anchor)
        pet = self.pets.get(e["entryId"])
        if k == 1 and pet is not None:
            self._float(pet, "1위!", MINE)

    def _outro(self):
        win = self.ents and min(self.ents, key=lambda e: self.ranks.get(e["entryId"], 99))
        pw = self.pets.get(win["entryId"]) if win else None
        if pw is not None and pw.anim_for("Hop") is not None:
            pw.play("Hop", once=True)
        if self.mine:
            r = self.ranks.get(self.mine["entryId"])
            self._say_mine("%s · 조 %d위%s" % (self.mine.get("text"), r, "!" if r == 1 else ""), OUTRO_MS)

    # ---- 마라톤: 경기장 둘레를 두 바퀴
    LAPS = 2

    def _marathon_setup(self):
        m = 30
        self.track = (self.x1 + m, self.top + 40, self.x2 - m, self.bottom - 4)
        l, t, r, b = self.track
        self.perim = 2.0 * ((r - l) + (b - t))
        self.start_xy = (l + 60, b)
        self._line((l, b), (r, b), "#c9ced8", 2, dash=(6, 5))
        self._line((r, b), (r, t), "#c9ced8", 2, dash=(6, 5))
        self._line((r, t), (l, t), "#c9ced8", 2, dash=(6, 5))
        self._line((l, t), (l, b), "#c9ced8", 2, dash=(6, 5))
        sx = self.start_xy[0]
        self._line((sx, b - 22), (sx, b + 8), "#ffffff", 4)
        self._text(sx, b + 16, "출발 · 결승", WHITE, 8, "center")
        self.board_x, self.board_y = l + 30, t + 22
        self._text(self.board_x, self.board_y, "마라톤 순위", MINE, 9, "w")
        self.board_items = []
        self.board_at = -9.0
        for i, e in enumerate(self.ents):
            p = self.pets.get(e["entryId"])
            if p is not None:
                self._put(p, sx - 8 - i * 6, b)
                self._stand(p, RIGHT)

    def _path(self, s):
        """둘레 위 거리 s -> (x, y, vx, vy). 출발점에서 오른쪽으로 돈다 (아래 -> 오른쪽 -> 위 -> 왼쪽)."""
        l, t, r, b = self.track
        sx = self.start_xy[0]
        legs = (((sx, b), (r, b)), ((r, b), (r, t)), ((r, t), (l, t)), ((l, t), (l, b)), ((l, b), (sx, b)))
        s = s % self.perim
        for (ax, ay), (bx, by) in legs:
            L = math.hypot(bx - ax, by - ay)
            if s <= L or (bx, by) == (sx, b):
                k = s / L if L else 1.0
                return ax + (bx - ax) * min(1.0, k), ay + (by - ay) * min(1.0, k), bx - ax, by - ay
            s -= L
        return sx, b, 1, 0

    def _marathon_put(self, pet, eid, d, done):
        if done:
            k = sorted(self.done_at, key=lambda i: self.done_at[i]).index(eid)
            tx, ty = self.start_xy[0] + 26 + k * 16, self.track[3] + 2
            ox, oy = self._foot(pet)
            if math.hypot(tx - ox, ty - oy) > 2:
                self._walk(pet, ox + (tx - ox) * 0.2, oy + (ty - oy) * 0.2)
            else:
                self._stand(pet, DOWN)
            return
        x, y, vx, vy = self._path(d * self.LAPS * self.perim)
        lane = (eid % 5) * 3
        if abs(vx) > abs(vy):
            y -= lane
        else:
            x -= lane
        self._walk(pet, x, y)

    def _marathon_board(self, rt):
        """중간 순위 (2초마다 다시 적는다 - 글자 몇 줄)."""
        if rt - self.board_at < 2.0 or self.layer is None:
            return
        self.board_at = rt
        med = sorted(self.T.values())[len(self.T) // 2]
        for k, frac in ((1, 0.25), (2, 0.5), (3, 0.75)):
            if k not in self.check_said and rt >= frac * med:
                self.check_said.add(k)
                if self.mine and self.mine["entryId"] not in self.done_at:
                    order = self._live_order(rt)
                    pos = order.index(self.mine["entryId"]) + 1
                    self._say_mine("%s 지점 · 지금 %d위!" % (("4분의 1", "반환", "4분의 3")[k - 1], pos), 2200)
        if self.done_at:
            return
        for it in self.board_items:
            self.layer.cv.delete(it)
        self.board_items = []
        for i, eid in enumerate(self._live_order(rt)[:8], 1):
            e = next(x for x in self.ents if x["entryId"] == eid)
            self.board_items += self._text(self.board_x, self.board_y + i * 16, "%d. %s" % (i, self._label(e)),
                                           MINE if e.get("mine") else WHITE, 9, "w")

    def _live_order(self, rt):
        def dist(eid):
            T = self.T[eid]
            return O.at_curve(self.curve[eid], min(1.0, rt / T) if T else 1.0)
        return sorted((e["entryId"] for e in self.ents), key=lambda i: (-dist(i), self.T[i]))

    # ================================================================ 시기형
    def _field_setup(self):
        ev, n = self.ev, len(self.ents)
        tries = O.EV[ev]["tries"]
        span = (FIELD_SHOW * 1000.0 - INTRO_MS - OUTRO_MS) / max(1, n * tries)
        self.A = int(min(ATTEMPT_MAX, max(ATTEMPT_MIN, span)))
        self.best = {}
        self.fouls = {}
        self.flags = {}
        self.board_items = []
        W = self.W
        # 기다리는 줄 (왼쪽). 스키점프는 비탈이 왼쪽 위라 아래에.
        row_w = min(0.40 * W, n * max(46, self.th * 0.8))
        step = row_w / max(1, n)
        self.row_y = self.bottom - (0 if ev == "ski" else int(self.th * 1.15))
        self.slot = {}
        for i, e in enumerate(self.ents):
            self.slot[e["entryId"]] = (self.x1 + 30 + step * (i + 0.5), self.row_y)
        if ev == "pole":
            self.run0 = self.x1 + 0.12 * W
            self.bar_x = self.x1 + 0.66 * W
            self.mat_x = self.bar_x + 70
            self._rect((self.mat_x - 40, self.bottom - 10), (self.mat_x + 50, self.bottom + 4), "#3f6fd8")
            self._line((self.run0, self.bottom + 4), (self.bar_x, self.bottom + 4), "#d08a4c", 4)
            for dx in (-6, 6):
                self._line((self.bar_x + dx, self.bottom), (self.bar_x + dx, self.top + 10), "#e2e6ee", 3)
            self.bar = None
        elif ev == "lift":
            self.plat_x = self.x1 + 0.62 * W
            self._rect((self.plat_x - 70, self.bottom - 2), (self.plat_x + 70, self.bottom + 8), "#8a6a46", "#5a4630")
            self.barbell = Prop(self.root, barbell_image(max(60, int(self.th * 1.3))), (self.plat_x, self.bottom - 40))
            self.props.append(self.barbell)
        elif ev == "discus":
            self.circle = (self.x1 + 0.10 * W, self.bottom)
            cx, cy = self.circle
            if self.layer is not None:
                x, y = self.layer.to_local(cx, cy)
                self.layer.cv.create_oval(x - 26, y - 8, x + 26, y + 8, outline="#e2e6ee", width=2)
            self.field0, self.field1 = self.x1 + 0.22 * W, self.x2 - 20
            for m in (30, 45, 60, 75):
                x = self._discus_x(m)
                self._line((x, self.bottom - 4), (x, self.bottom + 6), "#c9ced8", 1)
                self._text(x, self.bottom + 14, "%dm" % m, "#c9ced8", 8, "center")
            self.disc = Prop(self.root, disc_image(max(12, int(self.th * 0.22))), self.circle)
            self.props.append(self.disc)
        elif ev == "ski":
            self.slope0 = (self.x1 + 0.06 * W, self.top + 30)
            self.take = (self.x1 + 0.30 * W, self.top + 150)
            self.land0, self.land1 = self.x1 + 0.34 * W, self.x2 - 20
            self._line(self.slope0, self.take, "#eef4ff", 5)
            self._line((self.take[0] + 20, self.take[1] + 30), (self.land0 + 0.25 * W, self.bottom), "#eef4ff", 3)
            self._line((self.land0 + 0.25 * W, self.bottom), (self.x2, self.bottom), "#eef4ff", 3)
            for m in (90, 110, 130):
                x = self._ski_x(m)
                self._line((x, self.bottom - 4), (x, self.bottom + 6), "#c9ced8", 1)
                self._text(x, self.bottom + 14, "%dm" % m, "#c9ced8", 8, "center")
        self.score_x, self.score_y = self.x2 - 250, self.top + 6
        self._text(self.score_x, self.score_y, "%s · 점수판" % O.EV[ev]["kr"], MINE, 9, "w")
        self._draw_board()
        for e in self.ents:
            p = self.pets.get(e["entryId"])
            if p is not None:
                self._put(p, *self.slot[e["entryId"]])
                self._stand(p, DOWN)
        # 차례: 라운드마다 레인 차례로
        self.turns = [(r, e) for r in range(tries) for e in self.ents]
        self.steps = [self._wait(INTRO_MS)]

    def _discus_x(self, m):
        return self.field0 + (m / 85.0) * (self.field1 - self.field0)

    def _ski_x(self, m):
        return self.land0 + max(0.0, (m - 60.0) / 90.0) * (self.land1 - self.land0)

    def _draw_board(self):
        if self.layer is None:
            return
        for it in self.board_items:
            self.layer.cv.delete(it)
        self.board_items = []
        order = sorted(self.ents, key=lambda e: (O.rank_key(self.ev, self.best.get(e["entryId"])),
                                                 e.get("lane", 0)))
        for i, e in enumerate(order, 1):
            b = self.best.get(e["entryId"])
            line = "%d. %s  %s" % (i, self._label(e), O.text(self.ev, b) if b is not None else "-")
            self.board_items += self._text(self.score_x, self.score_y + i * 16, line,
                                           MINE if e.get("mine") else WHITE, 9, "w")

    # ---- 단계 기계: [{'ms', 'fn'(p), 'start'}] 를 차례로 돈다
    def _wait(self, ms, start=None):
        return {"ms": ms, "fn": None, "start": start}

    def _do(self, fn):
        return {"ms": 0, "fn": None, "start": fn}

    def _move(self, pet, to, ms, arc=0.0, walk=True, face=None):
        st = {"ms": ms, "from": None}

        def start():
            st["from"] = self._foot(pet)

        def fn(p):
            (ax, ay), (bx, by) = st["from"], to
            x = ax + (bx - ax) * p
            y = ay + (by - ay) * p - arc * 4 * p * (1 - p)
            if walk:
                self._walk(pet, x, y)
            else:
                if face is not None and pet.facing != face and face in getattr(pet, "photos", {}):
                    pet.facing = face
                    pet.redraw()
                pet.state = "idle"
                self._put(pet, x, y)
            if p >= 1.0 and walk:
                self._stand(pet, face)
        st.update({"fn": fn, "start": start})
        return st

    def _field_tick(self, dt):
        ms = dt * 1000.0
        while self.steps:
            st = self.steps[0]
            if not st.get("begun"):
                st["begun"] = True
                st["t"] = 0.0
                if st.get("start"):
                    st["start"]()
                    if not self.alive:
                        return
            st["t"] += ms
            ms = 0.0
            p = 1.0 if st["ms"] <= 0 else min(1.0, st["t"] / float(st["ms"]))
            if st.get("fn"):
                st["fn"](p)
            if p < 1.0:
                return
            over = st["t"] - st["ms"]
            self.steps.pop(0)
            ms = max(0.0, over)
        if self.turns:
            r, e = self.turns.pop(0)
            self.steps = self._attempt(r, e)
        elif self.phase != "outro":
            self.phase = "outro"
            self._field_outro()
            self.steps = [self._wait(OUTRO_MS), self._do(self._finish)]

    def _attempt(self, r, e):
        """한 시기의 단계들."""
        eid = e["entryId"]
        tries = e.get("tries") or []
        t = tries[r] if r < len(tries) else {"v": None, "slip": True}
        pet = self.pets.get(eid)
        A = self.A
        steps = []
        if e.get("mine"):
            steps.append(self._do(lambda: self._say_mine("내 차례! (%d번째 시기)" % (r + 1), 1500)))
        if pet is None:
            steps.append(self._wait(int(A * 0.5)))
            steps.append(self._do(lambda: self._record(e, t, None)))
            return steps
        home = self.slot[eid]
        fn = getattr(self, "_att_" + self.ev)
        steps += fn(pet, e, t, A)
        steps.append(self._do(lambda: self._record(e, t, pet)))
        steps.append(self._wait(int(A * 0.12)))
        steps.append(self._do(lambda: (self._put(pet, *home), self._stand(pet, DOWN))))
        return steps

    def _record(self, e, t, pet):
        eid = e["entryId"]
        v = t.get("v")
        where = pet if pet is not None else (self.score_x, self.score_y)
        if v is None:
            self.fouls[eid] = self.fouls.get(eid, 0) + 1
            self._float(where, "파울!" if self.ev != "ski" else "넘어짐!", BAD)
            if e.get("mine"):
                self._say_mine("아쉬워요… 다음 시기에!", 1500)
            return
        old = self.best.get(eid)
        self._float(where, O.text(self.ev, v), GOOD if old is None or O.better(self.ev, v, old) else WHITE)
        if old is None or O.better(self.ev, v, old):
            self.best[eid] = v
            if self.ev == "discus":
                self._flag(e, self._discus_x(v))
            elif self.ev == "ski":
                self._flag(e, self._ski_x(v))
            self._draw_board()

    def _flag(self, e, x):
        """원반 · 스키점프: 그 선수의 최고 지점에 깃발 (그 선수의 것만 옮긴다)."""
        if self.layer is None:
            return
        for it in self.flags.pop(e["entryId"], []):
            self.layer.cv.delete(it)
        color = MINE if e.get("mine") else "#7fb6ff"
        items = [self._line((x, self.bottom), (x, self.bottom - 26), "#f4f6fb", 2)]
        lx, ly = self.layer.to_local(x, self.bottom - 26)
        items.append(self.layer.cv.create_polygon(lx, ly, lx + 12, ly + 5, lx, ly + 10, fill=color, outline=""))
        lift = 12 * (self.ents.index(e) % 3)          # 깃발이 붙어 있어도 이름이 겹치지 않게 높이를 엇갈린다
        if lift:
            items.append(self._line((x, self.bottom - 26), (x, self.bottom - 26 - lift), "#f4f6fb", 1))
        items += self._text(x + 3, self.bottom - 32 - lift, self._name(e), color, 8, "w")
        self.flags[e["entryId"]] = items

    def _field_outro(self):
        order = sorted(self.ents, key=lambda e: (O.rank_key(self.ev, self.best.get(e["entryId"])),
                                                 self.ranks.get(e["entryId"], 99)))
        if order:
            pw = self.pets.get(order[0]["entryId"])
            if pw is not None:
                if pw.anim_for("Hop") is not None:
                    pw.play("Hop", once=True)
                self._float(pw, "조 1위!", MINE)
        if self.mine:
            r = self.ranks.get(self.mine["entryId"])
            self._say_mine("%s · 조 %d위%s" % (self.mine.get("text"), r, "!" if r == 1 else ""), OUTRO_MS)

    # ---- 장대높이뛰기
    def _att_pole(self, pet, e, t, A):
        v = t.get("v")
        best = self.best.get(e["entryId"])
        bar_m = v if v is not None else ((best or 4.6) + 0.15)
        px_per_m = (self.bottom - self.top - 40) / 7.0
        bar_y = self.bottom - bar_m * px_per_m
        steps = [self._move(pet, (self.run0, self.bottom), int(A * 0.14)),
                 self._do(lambda: self._set_bar(bar_y, False)),
                 self._move(pet, (self.bar_x - 60, self.bottom), int(A * 0.24))]
        if v is not None:
            steps.append(self._move(pet, (self.mat_x, self.bottom - 8), int(A * 0.30),
                                    arc=(self.bottom - bar_y) + 14, walk=False, face=RIGHT))
        else:
            steps.append(self._move(pet, (self.bar_x - 4, self.bottom), int(A * 0.22),
                                    arc=(self.bottom - bar_y) * 0.8, walk=False, face=RIGHT))
            steps.append(self._do(lambda: (self._set_bar(bar_y, True), self._hurt(pet))))
        steps.append(self._wait(int(A * 0.10)))
        return steps

    def _set_bar(self, y, knocked):
        if self.layer is None:
            return
        if self.bar is not None:
            self.layer.cv.delete(self.bar)
        a = (self.bar_x - 34, y)
        b = (self.bar_x + 34, y + (22 if knocked else 0))
        self.bar = self._line(a, b, "#ffd34d" if not knocked else BAD, 3)

    def _hurt(self, pet):
        if pet.anim_for("Hurt") is not None:
            pet.play("Hurt", once=True)

    # ---- 역도
    def _att_lift(self, pet, e, t, A):
        v = t.get("v")
        to = (self.plat_x, self.bottom)
        bb = self.barbell
        st = {}

        def at(p_from, p_to):
            def fn(p):
                fx, fy = self._foot(pet)
                hy = fy - pet.fh * p_from - (pet.fh * (p_to - p_from)) * p
                bb.put(fx, hy)
            return fn
        steps = [self._move(pet, to, int(A * 0.22), face=DOWN),
                 self._do(lambda: (self._stand(pet, DOWN), bb.put(self._foot(pet)[0], self._foot(pet)[1] - 4))),
                 {"ms": int(A * 0.16), "fn": at(0.05, 0.5), "start": None}]
        if v is not None:
            steps.append({"ms": int(A * 0.18), "fn": at(0.5, 1.05), "start": None})
            steps.append({"ms": int(A * 0.22), "fn": lambda p: None,
                          "start": lambda: pet.anim_for("Hop") is not None and pet.play("Hop", once=True)})
        else:
            steps.append({"ms": int(A * 0.16), "fn": at(0.5, 0.0), "start": lambda: self._hurt(pet)})
        steps.append(self._do(bb.hide))
        st.clear()
        return steps

    # ---- 원반던지기
    def _att_discus(self, pet, e, t, A):
        v = t.get("v")
        cx, cy = self.circle
        faces = [DOWN, RIGHT, UP, LEFT, DOWN, RIGHT]

        def spin(p):
            f = faces[min(len(faces) - 1, int(p * len(faces)))]
            if f in getattr(pet, "photos", {}) and pet.facing != f:
                pet.facing = f
                pet.redraw()
        land = self._discus_x(v) if v is not None else cx + 30
        st = {}

        def throw_start():
            fx, fy = self._foot(pet)
            st["a"] = (fx + 10, fy - pet.fh * 0.5)

        def fly(p):
            (ax, ay), bx, by = st["a"], land, self.bottom - 4
            x = ax + (bx - ax) * p
            y = ay + (by - ay) * p - (140 if v is not None else 40) * 4 * p * (1 - p)
            self.disc.put(x, y)
        return [self._move(pet, (cx, cy), int(A * 0.18)),
                {"ms": int(A * 0.22), "fn": spin, "start": None},
                {"ms": int(A * 0.34), "fn": fly, "start": throw_start},
                self._wait(int(A * 0.08)),
                self._do(self.disc.hide)]

    # ---- 스키점프
    def _att_ski(self, pet, e, t, A):
        v = t.get("v")
        land = self._ski_x(v) if v is not None else self._ski_x(95)
        steps = [self._do(lambda: (self._put(pet, *self.slope0), self._stand(pet, RIGHT))),
                 self._move(pet, self.take, int(A * 0.24), walk=False, face=RIGHT),
                 self._move(pet, (land, self.bottom), int(A * 0.36), arc=60, walk=False, face=RIGHT)]
        if v is None:
            steps.append(self._do(lambda: self._hurt(pet)))
        else:
            steps.append(self._do(lambda: pet.anim_for("Hop") is not None and pet.play("Hop", once=True)))
        steps.append(self._wait(int(A * 0.12)))
        return steps
