# -*- coding: utf-8 -*-
"""구경하는 배틀 장면 (1.10.3) — 길드원의 실시간 배틀을 **바탕화면에서 야생 배틀처럼** 보여 준다.

창도 배경도 없다. 바탕화면 오른쪽 아래에 포켓몬 둘이 마주 서서 싸운다:

  * 포켓몬은 **바탕화면에 돌아다니는 그 도트**(걷는 도트)이고, 저마다 테두리 없는 투명 창이다
    (바탕화면의 내 포켓몬·야생 포켓몬과 같은 방식 - PLAT.SpriteView).
  * 체력 막대·떠오르는 글씨·기술 연출은 그 위에 깐 **투명 레이어**에 그린다 (fx_layer - 야생 배틀과
    같은 레이어, 같은 연출 battle_fx / move_fx). 기술 이름은 쓴 포켓몬 머리 위에 떠오른다.
  * 포켓몬은 **몬스터볼에서 나온다.** 볼이 날아와 열리고, 흰 빛이 커지다가 포켓몬이 된다.
    불러들일 때는 거꾸로 - 흰 빛으로 줄어들어 붉은 줄기가 되어 돌아간다.
  * 쓰러지면 가라앉고, 다음 포켓몬이 또 볼에서 나온다.

전부 **클릭이 통과한다** - 구경하는 동안에도 그 자리의 바탕화면과 다른 프로그램을 그대로 쓴다.

처음에는 작은 창 안에 코트를 그리고 그 안에서 보여 줬다. "바탕화면에서 자연스럽게 야생 배틀처럼
보이게" 해 달라고 해서 창을 없앴다.

## 구경꾼의 화면이다

서버는 판이 넘어갈 때마다 '지금 모습'과 '방금 일어난 일들'을 민다 (server/app/live.spectate).
일들을 줄 세워 하나씩 틀고(queue), 다 틀면 지금 모습에 맞춘다(_sync) - 놓친 것이 있어도 어긋난 채로
남지 않는다. 이미 진행 중인 판을 뒤늦게 열면 일은 틀지 않고 지금 모습을 바로 세운다.

## 그리는 법

시간이 걸리는 것(볼이 날아간다, 커진다, 막대가 준다)은 tick(now) 이 굴린다. root.after 로 저마다
굴리지 않는다 - 검사가 시각을 넣어 가며 볼 수 있다. (기술 연출과 떠오르는 글씨만은 battle_fx 와
fx_layer 가 스스로 굴린다.)

(이 장면은 길드 광장의 배틀 코트로 처음 만들었다. 광장은 접었고 장면만 남겼다 - trash/plaza 브랜치.)
"""
import math
import tkinter as tk

from common import tint as T
from common.korean import natural
from . import fx_layer as FL
from . import platform_os as PLAT
from .ui_common import run_async

SCALE = 2                     # 걷는 도트를 그리는 배율 (원본 도트의 두 배)
GAP = 150                     # 마주 선 두 포켓몬의 사이 (발에서 발까지)
EDGE = 150                    # 오른쪽 포켓몬이 화면 오른쪽 끝에서 떨어진 거리
LIFT = 4                      # 발을 작업 영역 바닥에서 띄우는 높이
MON_H = 60                    # 걷는 도트가 없어 배틀 도트로 대신할 때 맞추는 키
MON_W = 96                    # 폭은 여기까지
MON_MAX_H = 84                # 걷는 도트는 두 배로 그리되, 큰 종은 이 키를 넘지 않게 줄인다
BALL = 22                     # 날아오는 몬스터볼의 크기
BAR_W, BAR_H = 46, 5          # 체력 막대 (바탕화면 야생 배틀의 것과 같은 크기)
GROW = (0.2, 0.4, 0.6, 0.8, 1.0)   # 볼에서 나올 때 흰 빛이 커지는 단계
THROW_S = 0.36                # 볼이 날아가는 시간
OPEN_S = 0.14                 # 볼이 열려 빛이 터지는 시간
GROW_S = 0.30                 # 흰 빛이 포켓몬만큼 커지는 시간
RECALL_S = 0.26               # 흰 빛으로 줄어드는 시간
BEAM_S = 0.14                 # 붉은 줄기가 돌아가는 시간
STEP_S = 0.55                 # 글 한 줄을 읽는 시간
FX_CAP_S = 2.6                # 기술 연출을 기다려 주는 한도 (배틀 창과 같다)
RESULT_S = 2.6                # 끝난 뒤 결과를 띄워 두는 시간
BACKLOG = 18                  # 틀 일이 이보다 밀리면 앞의 것은 건너뛴다 (구경이 배틀보다 늦어지지 않게)
SHORT = 20                    # 떠오르는 글씨 한 줄의 글자 수
SIDES = ("a", "b")
KEY = (254, 1, 254)           # 도트 창의 투명색 (바탕화면의 도트가 따로 주지 않을 때)
WHITE = "#ffffff"
MOVE_COLOR = "#ffffff"        # 방금 쓴 기술 이름 (투기장과 같다)
TEXT_COLOR = "#dfe6ff"        # 그 밖의 한 줄
BAR_BG, BAR_EDGE = "#14161f", "#3a4055"


# ---------------------------------------------------------------- 계산 (창 없이 검사한다)
def arc(p0, p1, t, lift):
    """p0 에서 p1 로 포물선을 그리며 가는 점 (t = 0..1). lift 는 가운데에서 떠오르는 높이."""
    x = p0[0] + (p1[0] - p0[0]) * t
    y = p0[1] + (p1[1] - p0[1]) * t - lift * 4.0 * t * (1.0 - t)
    return x, y


def lerp(a, b, t):
    return a + (b - a) * t


def stage_of(t, n):
    """0..1 을 n 단계 가운데 몇째로 (마지막 단계는 t = 1 에서만이 아니라 끝 구간 내내)."""
    return max(0, min(n - 1, int(t * n)))


def wait_of(ev):
    """그 일을 틀고 다음 일로 넘어가기까지의 시간(초). 기술(move)은 연출이 끝나야 넘어가므로 None."""
    t = ev.get("t")
    if t == "switch":
        return THROW_S + OPEN_S + GROW_S + 0.4
    if t == "recall":
        return RECALL_S + BEAM_S + 0.2
    if t == "move":
        return None
    if t == "hit":
        return 0.5
    if t == "faint":
        return STEP_S + 0.2
    if t == "mega":
        return 0.9
    if t == "ability":
        return 0.8
    if t == "_result":
        return RESULT_S
    if ev.get("text") or t in ("heal", "recoil", "chip"):
        return STEP_S
    return 0.05


def hp_color(frac):
    return "#4cd964" if frac > 0.5 else ("#ffcc33" if frac > 0.2 else "#ff4d4d")


def result_text(fight):
    r = fight.get("result")
    if r in SIDES:
        return "%s 님이 이겼습니다!" % ((fight.get(r) or {}).get("name") or "?")
    if r == "draw":
        return "비겼습니다."
    return "배틀이 끝났습니다."


def spots(area, edge=EDGE, gap=GAP, lift=LIFT):
    """작업 영역(x1, y1, x2, y2)의 오른쪽 아래에 두 포켓몬이 설 자리 {쪽: (발의 x, 발의 y)}. a 가 왼쪽이다."""
    x1, _y1, x2, y2 = area
    bx = max(x1 + gap + 60, x2 - edge)
    return {"a": (bx - gap, y2 - lift), "b": (bx, y2 - lift)}


def short_text(text):
    """떠오르는 글씨로 띄울 만큼만. '○○ 은(는) ...' 은 뒷부분만 (누구인지는 뜬 자리를 보면 안다)."""
    t = natural((text or "").split(" 은(는) ")[-1].split(" 의 ")[-1])
    return t if len(t) <= SHORT else t[:SHORT - 1] + "…"


def box_of(frames):
    """그림들이 다 들어가는 칸의 크기 (폭, 키)."""
    return (max([f.width for f in frames] or [1]), max([f.height for f in frames] or [1]))


def fit(frame, box):
    """그림을 칸에 **아래 가운데**로 맞춰 넣은 새 그림 (투명 바탕). 도트 창은 크기를 바꾸면 번쩍여서
    한 포켓몬의 그림은 전부 같은 칸에 넣어 둔다 - 발이 늘 같은 자리에 닿는다."""
    from PIL import Image
    out = Image.new("RGBA", box, (0, 0, 0, 0))
    out.paste(frame, ((box[0] - frame.width) // 2, box[1] - frame.height))
    return out


def grow_frames(first, box):
    """볼에서 나올 때의 흰 빛: 포켓몬의 윤곽을 희게 칠해 GROW 단계로 키운 그림들 (칸에 맞춰서)."""
    from PIL import Image
    white = Image.new("RGBA", first.size, (255, 255, 255, 0))
    white.putalpha(first.getchannel("A"))
    out = []
    for k in GROW:
        size = (max(1, int(round(first.width * k))), max(1, int(round(first.height * k))))
        out.append(fit(white if size == first.size else white.resize(size, Image.NEAREST), box))
    return out


# ---------------------------------------------------------------- 포켓몬 그림
def load_art(host, mon, side, done):
    """포켓몬 도트 한 벌을 준비해서 done(art) 를 부른다 (Tk 스레드에서. 이미 있으면 바로).

    art = {"frames": 서 있는 그림들(칸에 맞춘 RGBA), "durs": 장마다 머무는 시간(ms),
    "grow": 볼에서 나올 때의 흰 빛, "box": 칸의 크기, "size": 도트의 (폭, 키)}. 못 받았으면 빈 dict.
    같은 포켓몬(번호·색·보는 쪽)은 한 번만 만든다.
    """
    num, skin = mon.get("num"), T.skin(mon)
    key = (num, skin, side)
    cache = host._art
    got = cache.get(key)
    if isinstance(got, dict):
        return done(got)
    if isinstance(got, list):
        got.append(done)                     # 받는 중이다 - 줄만 선다
        return None
    cache[key] = [done]
    if not num:
        return _art_ready(host, key, None)
    api = host.app.api

    def work():
        from . import sprite_cache, sprites
        got = walk_frames(api, num, skin, side)
        if got:
            return got
        # 걷는 도트가 없는 종은 배틀 도트로 대신한다 (바탕화면의 포켓몬도 그렇게 한다)
        path = sprite_cache.ensure(api, num, skin)
        if not path:
            return None
        anim = sprites.load_animation(path, MON_H, 0.2, 4.0, max_size=(MON_W, MON_H))
        # 쇼다운 도트는 원본이 왼쪽을 본다 (sprites.RIGHT 에 원본, LEFT 에 뒤집은 것).
        # 왼쪽에 선 a 는 오른쪽을 봐야 하므로 뒤집은 쪽을 쓴다.
        frames = anim.frames[sprites.LEFT if side == "a" else sprites.RIGHT]
        return [sprites.to_rgba(f, anim.key) for f in frames], list(anim.durations) or [100]

    run_async(host.root, work, lambda r, err: _art_ready(host, key, None if err else r))
    return None


def walk_frames(api, num, skin, side):
    """**바탕화면에 돌아다니는 그 도트**(걷는 도트)로 설 그림을 만든다: (그림들, 장마다 머무는 시간).

    왼쪽에 선 a 는 오른쪽을, b 는 왼쪽을 본다. 가만히 숨 쉬는 동작(Idle)이 있는 종은 그것으로 서 있고,
    걷기밖에 없는 종은 제자리에서 걷는다 (서 있는 그림 한 장으로 굳혀 두면 죽은 것 같다).
    걷는 도트가 아예 없는 종이면 None.
    **작업 스레드에서 부를 것** (없으면 서버에서 받아 온다).

    크기는 원본의 두 배다 - 종마다 덩치가 다르게 보인다. 다만 큰 종은 MON_MAX_H / MON_W 를 넘지 않게 줄인다.
    """
    from . import sprites, walk_cache
    try:
        sheet, meta = walk_cache.ensure(api, num, "Walk", skin)
        if not (sheet and meta):
            return None
        walk = sprites.load_walk(sheet, meta, scale=float(SCALE))
        k = min(float(SCALE), MON_MAX_H * SCALE / float(walk.h or 1), MON_W * SCALE / float(walk.w or 1))
        if k < SCALE:
            walk = sprites.load_walk(sheet, meta, scale=round(k, 3))
        way = sprites.RIGHT if side == "a" else sprites.LEFT
        anim = walk
        try:
            isheet, imeta = walk_cache.ensure(api, num, "Idle", skin)
            if isheet and imeta:
                anim = sprites.load_walk(isheet, imeta, scale=walk.scale, name="Idle")
        except Exception:                                   # noqa: BLE001
            anim = walk
        frames = [sprites.to_rgba(f, anim.key) for f in anim.frames[way]]
        if not frames:
            return None
        return frames, list(anim.durations) or [100]
    except Exception:                                       # noqa: BLE001
        return None


def _art_ready(host, key, r):
    waiting = host._art.get(key)
    art = {}
    if r and host.alive:
        try:
            frames, durs = r
            box = box_of(frames)
            art = {"frames": [fit(f, box) for f in frames], "durs": durs,
                   "grow": grow_frames(frames[0], box), "box": box, "size": frames[0].size}
        except Exception:                                   # noqa: BLE001
            art = {}
    host._art[key] = art                     # 빈 dict = 그림이 없다 (다시 받지 않는다)
    for cb in (waiting if isinstance(waiting, list) else []):
        try:
            cb(art)
        except Exception:                                   # noqa: BLE001
            pass


# ---------------------------------------------------------------- 바탕화면에 서는 것들
class Sprite(object):
    """바탕화면의 도트 하나: 테두리 없는 투명 창 (PLAT.SpriteView). **발(아래 가운데)을 화면 자리에 맞춘다.**

    창의 크기는 처음 잡은 칸 그대로다 (투명색 창은 크기가 바뀌는 순간 검게 번쩍인다). 숨길 때도 창을
    거두지 않고 빈 그림을 건다 - 거뒀다 띄우면 맥에서 '항상 위' 와 클릭 통과가 풀린다.
    """

    def __init__(self, root, key, box):
        from PIL import Image
        self.key, self.box = key, box
        self.at = None                # 발의 화면 자리
        self.shown = None             # 지금 걸린 그림 (검사가 본다)
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry("+%d+%d" % (-4000, -4000))        # 자리를 잡기 전에는 화면 밖에
        bg = PLAT.transparent_window(self.win, "#%02x%02x%02x" % key)
        self.view = PLAT.SpriteView(self.win, bg, box[0], box[1])
        self.blank = self.load([Image.new("RGBA", box, (0, 0, 0, 0))])[0]
        self.view.show(self.blank)
        PLAT.raise_above(self.win)
        self.through = bool(PLAT.make_click_through(self.win))

    def load(self, frames):
        """RGBA 그림들을 이 창이 걸 수 있는 꼴로 (투명색을 칠해서 넘긴다 - 윈도우·맥이 같은 것을 받는다)."""
        from . import sprites
        return self.view.frames([sprites.flatten_rgba(f, self.key) for f in frames], self.key)

    def show(self, handle):
        if handle is not self.shown:
            self.shown = handle
            self.view.show(handle if handle is not None else self.blank)

    def hide(self):
        self.show(None)

    def visible(self):
        return self.shown is not None

    def move(self, sx, sy):
        at = (int(round(sx)), int(round(sy)))
        if at != self.at:
            self.at = at
            try:
                self.win.geometry("+%d+%d" % (at[0] - self.box[0] // 2, at[1] - self.box[1]))
            except tk.TclError:
                pass

    def destroy(self):
        try:
            self.view.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        try:
            self.win.destroy()
        except tk.TclError:
            pass


class SceneHost(object):
    """장면이 서는 곳: 투명 레이어(체력 막대·글씨·기술 연출)와, 바뀐 것만 건드리는 도우미.

    캔버스는 같은 자리로 coords 해도, 같은 값으로 itemconfigure 해도 그 자리를 다시 그린다.
    가만히 서 있는 장면을 매 틱 건드리면 쉬지 않고 그리게 된다. 그래서 마지막에 놓은 자리와
    걸어 둔 값을 적어 두고, 달라졌을 때만 캔버스를 부른다.

    레이어를 못 깔면(클릭 통과를 못 거는 환경) 도트만 선다 - 통과하지 않는 투명 레이어는 그 자리의
    바탕화면을 못 누르게 하는 벽이라 띄우지 않는다 (fx_layer.open_layer).
    """

    def __init__(self, app, root, area):
        self.app, self.root = app, root
        self.alive = True
        self.now = 0.0                # 지금 틱의 시각
        self.spot = spots(area)
        ov = getattr(app, "overlay", None)
        self.key = tuple(getattr(ov, "key", None) or KEY)
        xs = [p[0] for p in self.spot.values()]
        ground = self.spot["a"][1]
        self.layer = FL.open_layer(root, (min(xs) - 170, ground - 200, max(xs) + 170, ground + 6))
        self.spare = None
        if self.layer is not None:
            self.cv = self.layer.cv
        else:
            self.cv = self.spare = tk.Canvas(root)           # 안 보이는 캔버스 (그리는 코드가 그대로 돈다)
        self._at, self._cfg = {}, {}
        self._art = {}                # {(도감 번호, skin, 쪽): 포켓몬 그림} (load_art)
        self._moves = None
        self.texts = []               # 떠 있는 글씨들

    def loc(self, sx, sy):
        """화면 자리 -> 레이어 캔버스의 자리."""
        return self.layer.to_local(sx, sy) if self.layer is not None else (sx, sy)

    def _put(self, item, *xy):
        if self._at.get(item) != xy:
            self._at[item] = xy
            self.cv.coords(item, *xy)

    def _set(self, item, **kw):
        old = self._cfg.setdefault(item, {})
        new = dict((k, v) for k, v in kw.items() if old.get(k) != v)
        if new:
            old.update(new)
            self.cv.itemconfigure(item, **new)

    def _del(self, item):
        self._at.pop(item, None)
        self._cfg.pop(item, None)
        try:
            self.cv.delete(item)
        except tk.TclError:
            pass

    def float_text(self, sx, sy, text, color=TEXT_COLOR, ms=900):
        """그 자리 위에 잠깐 떠올랐다 사라지는 글씨 (야생 배틀과 같은 것). 레이어가 없으면 아무것도 안 한다."""
        if self.layer is None or not text:
            return None
        self.texts = [t for t in self.texts if t.items]
        t = FL.FloatText(self.layer, sx, sy, text, color, ms)
        self.texts.append(t)
        return t

    def find_move(self, ev):
        """그 일(기술을 썼다)의 기술. 연출을 고르는 데 쓴다 (배틀 창과 같은 방식)."""
        if self._moves is None:
            moves = getattr(getattr(self.app, "dex", None), "moves", None) or {}
            self._moves = dict((m.get("kr"), m) for m in moves.values() if m.get("kr"))
        return self._moves.get(ev.get("move")) or {"type": ev.get("moveType") or "NORMAL",
                                                   "cat": ev.get("cat") or "physical", "flags": []}

    def close(self):
        self.alive = False
        for t in self.texts:
            try:
                t.stop()
            except Exception:                               # noqa: BLE001
                pass
        self.texts = []
        if self.layer is not None:
            self.layer.destroy()
            self.layer = None
        if self.spare is not None:
            try:
                self.spare.destroy()
            except tk.TclError:
                pass
        self._at.clear()
        self._cfg.clear()
        self._art.clear()


class _Stage(object):
    """battle_fx.Effect 가 바라는 무대: cv, root, lunge(who, done)."""

    def __init__(self, scene):
        self.scene = scene
        self.cv = scene.pane.cv
        self.root = scene.pane.root

    def lunge(self, who, done):
        self.scene.lunge(who, done)


class _Tween(object):
    """t0 부터 dur 초 동안 fn(0..1) 을 부르고, 끝나면 end() 를 부른다."""

    def __init__(self, t0, dur, fn, end=None):
        self.t0, self.dur, self.fn, self.end = t0, max(0.001, dur), fn, end


class _Side(object):
    """한쪽: 나와 있는 포켓몬과 그 도트 창."""

    def __init__(self):
        self.mon = None               # 나와 있는(나오는 중인) 포켓몬
        self.art = None               # 그 그림 (load_art). 아직 못 받았으면 None, 없으면 {}
        self.sprite = None            # 그 도트 창 (그림을 받은 뒤에 생긴다)
        self.idle, self.grow = [], [] # 그 창에 걸 그림들
        self.look = None              # 지금 걸려 있어야 할 것: ("idle", i) / ("grow", i) / None
        self.out = False              # 다 나와서 서 있다 (볼에서 나오는 중·불러들이는 중이면 False)
        self.busy = False             # 나오는 중이거나 들어가는 중이다
        self.frame = 0
        self.next_frame = 0.0
        self.hp = 0.0                 # 막대에 그려진 체력 (줄어드는 중이면 그 사이 값)
        self.maxhp = 1
        self.off = (0.0, 0.0)         # 제자리에서 비켜 있는 만큼 (달려들기·흔들리기·가라앉기)
        self.left, self.size = 0, 0   # 남은 마릿수, 데려온 마릿수
        self.ball = None              # 날아오는 볼 (도트 창)
        self.balls = ()               # 그 창에 걸 그림 (닫힌 볼, 열린 볼)
        self.ball_at = None
        self.bar = self.fill = None   # 체력 막대 (레이어의 네모 둘)


class FightScene(object):
    """바탕화면 오른쪽 아래에서 벌어지는 배틀. pane 은 서는 곳(SceneHost)."""

    def __init__(self, pane, mid):
        self.pane = pane
        self.cv = pane.cv
        self.mid = mid
        self.alive = True
        self.fight = None
        self.queue = []               # 틀 일들
        self.next_at = 0.0            # 다음 일을 틀 수 있는 때
        self.tweens = []
        self.fx = None                # 돌고 있는 기술 연출
        self.fx_done = False
        self.fx_until = 0.0
        self.synced = True            # 일을 다 틀고 지금 모습에 맞췄다
        self.done = False             # 끝난 판을 다 봤다 - 치워도 된다
        self.over = False             # 끝났다는 것을 받았다 (결과까지 틀고 나면 done)
        self.said = []                # 띄운 글 (검사가 본다): [(쪽 또는 None, 글)]
        self.beam = None
        self.beam_ends = None
        self.rays = []
        self.sides = dict((s, _Side()) for s in SIDES)
        self.spot = dict(pane.spot)
        ground = self.spot["a"][1]
        # 볼이 날아 들어오는 자리: 저마다 바깥쪽 위에서
        self.hand = {"a": (self.spot["a"][0] - 130, ground - 70),
                     "b": (min(self.spot["b"][0] + 130, self.spot["b"][0] + EDGE - 12), ground - 70)}
        self.top = ((self.spot["a"][0] + self.spot["b"][0]) / 2.0, ground - 120)   # 가운데 위 (승부 시작·결과)
        try:
            for s in SIDES:
                side = self.sides[s]
                side.bar = self.cv.create_rectangle(0, 0, 1, 1, fill=BAR_BG, outline=BAR_EDGE, state="hidden")
                side.fill = self.cv.create_rectangle(0, 0, 1, 1, fill=hp_color(1.0), outline="", state="hidden")
        except tk.TclError:
            self.alive = False

    # ---------------- 치우기 ----------------
    def close(self):
        """장면을 치운다 (도트 창과 그린 것을 전부 없앤다)."""
        if self.fx is not None:
            try:
                self.fx.stop()
            except Exception:                               # noqa: BLE001
                pass
            self.fx = None
        self._clear_fx_bits()
        for side in self.sides.values():
            for sp in (side.sprite, side.ball):
                if sp is not None:
                    sp.destroy()
            side.sprite = side.ball = None
            for item in (side.bar, side.fill):
                if item is not None:
                    self.pane._del(item)
            side.bar = side.fill = None
        self.tweens, self.queue = [], []
        self.alive = False

    # ---------------- 서버가 보낸 판 ----------------
    def feed(self, fight, now, replay=True):
        """판의 새 모습. replay 가 False 면 일어난 일은 틀지 않고 지금 모습만 세운다."""
        if not self.alive:
            return
        first = self.fight is None
        self.fight = fight
        events = [e for e in (fight.get("events") or []) if isinstance(e, dict)] if replay else []
        if first and not events:
            self._sync(now)                  # 이미 진행 중인 판에 뒤늦게 들어왔다
        else:
            if len(self.queue) > BACKLOG:
                self._skip(now)
            self.queue += events
            self.synced = False
        if fight.get("over") and not self.over:
            self.over = True
            self.queue.append({"t": "_result"})
        for s in SIDES:
            info = fight.get(s) or {}
            side = self.sides[s]
            if not side.size:
                side.left, side.size = int(info.get("left") or 0), int(info.get("size") or 0)

    def _skip(self, now):
        """밀린 일을 건너뛴다. 움직이던 것은 멈추고 지금 모습으로 세운다."""
        self.queue = []
        self.tweens = []
        if self.fx is not None:
            try:
                self.fx.stop()
            except Exception:                               # noqa: BLE001
                pass
            self.fx = None
        self._clear_fx_bits()
        for s in SIDES:
            self.sides[s].busy = False
            self.sides[s].off = (0.0, 0.0)
        self.next_at = now
        self._sync(now)

    def _sync(self, now):
        """지금 판의 모습에 맞춘다: 누가 나와 있나, 체력, 남은 마릿수."""
        f = self.fight or {}
        for s in SIDES:
            side, info = self.sides[s], f.get(s) or {}
            mon = info.get("mon") or {}
            side.left, side.size = int(info.get("left") or 0), int(info.get("size") or 0)
            if not mon or mon.get("fainted") or not mon.get("num"):
                if side.out:
                    self._hide(s)
                continue
            cur = side.mon or {}
            if not side.out or (cur.get("num"), T.skin(cur)) != (mon.get("num"), T.skin(mon)):
                self._stand(s, mon, now)
            side.mon = dict(mon)
            side.hp, side.maxhp = float(mon.get("hp") or 0), max(1, int(mon.get("maxhp") or 1))
        self.synced = True

    # ---------------- 한쪽의 포켓몬 ----------------
    def _enter(self, s, mon):
        """그 포켓몬으로 바꿔 들 준비: 앞 포켓몬의 창을 치우고 새 그림을 받는다."""
        side = self.sides[s]
        if side.sprite is not None:
            side.sprite.destroy()
        side.sprite, side.idle, side.grow, side.look = None, [], [], None
        side.mon, side.art, side.off = dict(mon), None, (0.0, 0.0)
        side.hp, side.maxhp = float(mon.get("hp") or 0), max(1, int(mon.get("maxhp") or 1))
        side.frame, side.next_frame = 0, 0.0
        load_art(self.pane, mon, s, lambda art, m=mon: self._got_art(s, m, art))

    def _stand(self, s, mon, now):
        """볼 없이 바로 세운다 (뒤늦게 들어왔을 때, 놓친 교체를 맞출 때)."""
        side = self.sides[s]
        side.out, side.busy = True, False
        self._enter(s, mon)
        side.look = ("idle", 0)

    def _got_art(self, s, mon, art):
        side = self.sides.get(s)
        if not self.alive or side is None or side.mon is None:
            return
        if (side.mon.get("num"), T.skin(side.mon)) != (mon.get("num"), T.skin(mon)):
            return                           # 그사이 다른 포켓몬으로 바뀌었다
        side.art = art
        if not art.get("frames"):
            return
        try:
            side.sprite = Sprite(self.pane.root, self.pane.key, art["box"])
            side.idle = side.sprite.load(art["frames"])
            side.grow = side.sprite.load(art["grow"])
        except Exception:                                   # noqa: BLE001
            side.sprite, side.idle, side.grow = None, [], []
            return
        if self.pane.layer is not None:
            self.pane.layer.raise_above()    # 새 창이 생겼다 - 체력 막대와 연출이 그 위에 오게

    def _hide(self, s):
        side = self.sides[s]
        side.out, side.busy, side.look, side.off = False, False, None, (0.0, 0.0)
        side.mon, side.art = None, None
        if side.sprite is not None:
            side.sprite.destroy()
        side.sprite, side.idle, side.grow = None, [], []

    # ---------------- 글 ----------------
    def say(self, text, who=None, color=TEXT_COLOR, ms=1100):
        """글 한 줄을 띄운다: 그 포켓몬 머리 위에, 누구 것도 아니면 가운데 위에."""
        if not text:
            return
        text = natural(text)                 # '회피율 이(가) 올랐다' -> '회피율이 올랐다'
        self.said.append((who, text))
        if who in SIDES:
            x, y = self.spot[who][0], self.spot[who][1] - self._height(who) - 22
        else:
            x, y = self.top
        self.pane.float_text(x, y, text, color, ms)

    def _height(self, s):
        return ((self.sides[s].art or {}).get("size") or (0, MON_H))[1]

    # ---------------- 틀기 ----------------
    def _apply(self, ev, now):
        t, who, text = ev.get("t"), ev.get("who"), ev.get("text")
        wait = wait_of(ev)
        if t == "_result":
            self.say(result_text(self.fight or {}), None, WHITE, int(RESULT_S * 1000))
            self.tweens.append(_Tween(now + RESULT_S, 0.01, lambda _t: None, self._finish))
        elif t == "intro":
            self.say(text, None, WHITE, 1300)
        elif t == "switch" and who in SIDES and isinstance(ev.get("mon"), dict):
            self._send_out(who, ev["mon"], now)
            self.say(text, None)
        elif t == "recall" and who in SIDES:
            self._recall(who, now)
            self.say(text, None)
        elif t == "mega" and who in SIDES and self.sides[who].mon:
            mon = dict(self.sides[who].mon)
            mon["num"] = ev.get("num") or mon.get("num")
            mon["name"] = ev.get("newName") or ev.get("to") or mon.get("name")
            mon["mega"] = True
            self._flash(who, mon, now)
            self.say("메가진화!", who, "#ffe08a", 1200)
        elif t == "move":
            other = "b" if who == "a" else "a"
            if who in SIDES:
                self.say("%s!" % ev["move"] if ev.get("move") else short_text(text), who, MOVE_COLOR)
            if who in SIDES and self.sides[who].out and self.sides[other].out and self._play_fx(ev, who, other, now):
                wait = None
            else:
                wait = STEP_S
        elif t == "hit":
            target = ev.get("target")
            if target in SIDES and self.sides[target].out:
                if ev.get("crit"):
                    self.say("급소!", target, "#ffd447")
                eff = ev.get("eff", 1)
                if eff and eff > 1:
                    self.say("효과가 굉장하다!", target, "#7bffa0")
                elif eff and eff < 1:
                    self.say("효과가 별로...", target, "#b0b0c0")
                self._shake(target, now)
                self._bar_to(target, ev.get("hp", 0), now)
        elif t in ("heal", "recoil", "chip"):
            if who in SIDES and self.sides[who].out and "hp" in ev:
                self._bar_to(who, ev["hp"], now)
            self.say(short_text(text), who if who in SIDES else None)
        elif t == "faint" and who in SIDES:
            self._faint(who, now)
            self.say("쓰러졌다!", who, "#ff9d9d")
        elif text:
            self.say(short_text(text), who if who in SIDES else None)
        if wait is not None:
            self.next_at = now + wait

    def _finish(self):
        self.done = True

    def _ball(self, s):
        """그쪽의 볼 창 (처음 쓸 때 만든다)."""
        side = self.sides[s]
        if side.ball is None:
            try:
                from . import effects, sprites
                side.ball = Sprite(self.pane.root, self.pane.key, (BALL, BALL))
                side.balls = tuple(side.ball.load([sprites.to_rgba(effects.ball_image(BALL, self.pane.key, open_top=o),
                                                                    self.pane.key)])[0] for o in (False, True))
            except Exception:                               # noqa: BLE001
                side.ball, side.balls = None, ()
        return side.ball

    def _send_out(self, s, mon, now):
        """볼이 날아온다 -> 열린다 -> 흰 빛이 커져서 포켓몬이 된다."""
        side = self.sides[s]
        side.out, side.busy = False, True
        self._enter(s, mon)
        ball = self._ball(s)
        p0, p1 = self.hand[s], (self.spot[s][0], self.spot[s][1] - 20)
        side.ball_at = p0
        if ball is not None and side.balls:
            ball.show(side.balls[0])

        def fly(t):
            side.ball_at = arc(p0, p1, t, 34.0)

        def landed():
            if ball is not None and side.balls:
                ball.show(side.balls[1])
            self._burst(p1, now + THROW_S)
            self.tweens.append(_Tween(now + THROW_S + OPEN_S * 0.6, GROW_S, grow, standing))

        def grow(t):
            if ball is not None:
                ball.hide()
            side.look = ("grow", stage_of(t, len(GROW)))

        def standing():
            if side.mon is None:
                return
            side.out, side.busy = True, False
            side.look = ("idle", 0)
            side.frame, side.next_frame = 0, 0.0
        self.tweens.append(_Tween(now, THROW_S, fly, landed))

    def _burst(self, at, t0):
        """볼이 열릴 때 터지는 흰 빛 (여섯 갈래)."""
        try:
            rays = [self.cv.create_line(0, 0, 0, 0, fill=WHITE, width=2) for _i in range(6)]
        except tk.TclError:
            return
        self.rays += rays
        cx, cy = self.pane.loc(*at)

        def spread(t):
            for i, item in enumerate(rays):
                ang = math.pi / 3.0 * i + 0.3
                r0, r1 = 4 + 16 * t, 10 + 22 * t
                try:
                    self.cv.coords(item, cx + math.cos(ang) * r0, cy + math.sin(ang) * r0,
                                   cx + math.cos(ang) * r1, cy + math.sin(ang) * r1)
                except tk.TclError:
                    pass

        def gone():
            for item in rays:
                self.pane._del(item)
                if item in self.rays:
                    self.rays.remove(item)
        self.tweens.append(_Tween(t0, OPEN_S + 0.08, spread, gone))

    def _recall(self, s, now):
        """흰 빛으로 줄어든다 -> 붉은 줄기가 되어 돌아간다."""
        side = self.sides[s]
        if not side.out:
            return self._hide(s)
        side.out, side.busy = False, True
        p0, p1 = (self.spot[s][0], self.spot[s][1] - 20), self.hand[s]

        def shrink(t):
            side.look = ("grow", len(GROW) - 1 - stage_of(t, len(GROW)))

        def beam_start():
            side.look = None
            try:
                self.beam = self.cv.create_line(0, 0, 0, 0, fill="#ff5a4f", width=3)
            except tk.TclError:
                self.beam = None
            self.beam_ends = (p0, p1)
            self.tweens.append(_Tween(now + RECALL_S, BEAM_S, pull, beam_end))

        def pull(t):
            self.beam_ends = ((lerp(p0[0], p1[0], t), lerp(p0[1], p1[1], t)), p1)

        def beam_end():
            if self.beam is not None:
                self.pane._del(self.beam)
                self.beam = None
            self._hide(s)
        self.tweens.append(_Tween(now, RECALL_S, shrink, beam_start))

    def _flash(self, s, mon, now):
        """메가진화: 흰 빛에 싸였다가 새 모습이 된다."""
        side = self.sides[s]
        side.look = ("grow", len(GROW) - 1)
        side.busy = True

        def swap():
            self._stand(s, mon, now)
        self.tweens.append(_Tween(now, 0.45, lambda _t: None, swap))

    def _faint(self, s, now):
        side = self.sides[s]
        side.left = max(0, side.left - 1)
        if not side.out:
            return
        side.busy = True

        def sink(t):
            side.off = (0.0, 26.0 * t)

        def gone():
            self._hide(s)
        self.tweens.append(_Tween(now, 0.32, sink, gone))

    def _shake(self, s, now):
        side = self.sides[s]

        def shake(t):
            side.off = (math.sin(t * math.pi * 5.0) * 5.0 * (1.0 - t), 0.0)
        self.tweens.append(_Tween(now, 0.26, shake, lambda: setattr(side, "off", (0.0, 0.0))))

    def _bar_to(self, s, hp, now):
        side = self.sides[s]
        start, to = side.hp, max(0.0, float(hp or 0))

        def move(t):
            side.hp = lerp(start, to, t)
        self.tweens.append(_Tween(now, 0.4, move))

    def lunge(self, s, done):
        """기술 연출이 부른다: 몸이 앞으로 움찔했다 돌아온다."""
        side = self.sides.get(s)
        if side is not None:
            sign = 1.0 if s == "a" else -1.0
            self.tweens.append(_Tween(self.pane.now, 0.17,
                                      lambda t: setattr(side, "off", (sign * 12.0 * math.sin(math.pi * t), 0.0)),
                                      lambda: setattr(side, "off", (0.0, 0.0))))
        try:
            self.pane.root.after(190, lambda: self.alive and done())
        except Exception:                                   # noqa: BLE001
            pass

    def center(self, s):
        """그 포켓몬의 몸 가운데 (레이어 캔버스의 자리). 기술이 여기서 나가 저기에 맞는다."""
        return self.pane.loc(self.spot[s][0], self.spot[s][1] - self._height(s) / 2.0)

    def _play_fx(self, ev, who, other, now):
        if self.pane.layer is None:
            return False                     # 그릴 레이어가 없다 - 연출 없이 넘어간다
        from . import battle_fx as FX
        self.fx_done = False

        def done():
            self.fx_done = True
        try:
            self.fx = FX.Effect(_Stage(self), self.pane.find_move(ev), self.center(who), self.center(other),
                                done, who=who)
            self.fx_until = now + FX_CAP_S
            self.fx.play()
            return True
        except Exception:                                   # noqa: BLE001
            self.fx = None
            return False

    def _clear_fx_bits(self):
        for item in self.rays:
            self.pane._del(item)
        self.rays = []
        if self.beam is not None:
            self.pane._del(self.beam)
            self.beam = None
        for s in SIDES:
            ball = self.sides[s].ball
            if ball is not None:
                ball.hide()

    # ---------------- 한 틱 ----------------
    def tick(self, now):
        if not self.alive:
            return
        for tw in list(self.tweens):                     # 1) 움직이는 것들
            if now < tw.t0:
                continue
            t = min(1.0, (now - tw.t0) / tw.dur)
            tw.fn(t)
            if t >= 1.0:
                if tw in self.tweens:
                    self.tweens.remove(tw)
                if tw.end:
                    tw.end()
        for s in SIDES:                                  # 2) 도트의 다음 장
            side = self.sides[s]
            n = len(side.idle)
            if side.out and not side.busy and n > 1 and now >= side.next_frame:
                if side.next_frame:
                    side.frame = (side.frame + 1) % n
                side.look = ("idle", side.frame)
                durs = (side.art or {}).get("durs") or [100]
                side.next_frame = now + max(40, int(durs[side.frame % len(durs)] or 100)) / 1000.0
        if self.fx is not None and (self.fx_done or self.fx.dead or now >= self.fx_until):   # 3) 기술이 끝났다
            try:
                self.fx.stop()
            except Exception:                               # noqa: BLE001
                pass
            self.fx = None
            self.next_at = now + 0.09
        if self.fx is None and now >= self.next_at:      # 4) 다음 일
            if self.queue:
                self._apply(self.queue.pop(0), now)
            elif not self.synced and not self.tweens:
                self._sync(now)
        self._place()

    def _place(self):
        """도트 창과 그린 것들을 제자리에 놓는다 (바뀐 것만 옮겨진다)."""
        put, conf, loc = self.pane._put, self.pane._set, self.pane.loc
        for s in SIDES:
            side = self.sides[s]
            x, y = self.spot[s]
            sp = side.sprite
            if sp is not None:
                sp.move(x + side.off[0], y + side.off[1])
                kind = side.look
                handle = None
                if kind is not None:
                    pool = side.idle if kind[0] == "idle" else side.grow
                    handle = pool[min(kind[1], len(pool) - 1)] if pool else None
                sp.show(handle)
            if side.ball is not None:
                at = side.ball_at or self.hand[s]
                side.ball.move(at[0], at[1] + BALL // 2)
            if side.bar is not None:
                on = "normal" if (side.out and side.mon) else "hidden"
                frac = max(0.0, min(1.0, side.hp / float(side.maxhp or 1)))
                lx, ly = loc(x, y - self._height(s) - 8)
                x0, y0 = lx - BAR_W // 2, ly - BAR_H
                put(side.bar, x0 - 1, y0 - 1, x0 + BAR_W + 1, y0 + BAR_H + 1)
                put(side.fill, x0, y0, x0 + int(BAR_W * frac), y0 + BAR_H)
                conf(side.bar, state=on)
                conf(side.fill, state=on if frac > 0 else "hidden", fill=hp_color(frac))
        if self.beam is not None and self.beam_ends:
            (x0, y0), (x1, y1) = self.beam_ends
            a, b = loc(x0, y0), loc(x1, y1)
            put(self.beam, a[0], a[1], b[0], b[1])
