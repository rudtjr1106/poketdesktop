# -*- coding: utf-8 -*-
"""열매 텃밭 (다음 시즌, 2026-11-26) — 바탕화면의 화단 · 심기 · 물 · 거두기 · 먹이 · 친구 화단.

흐름 (design-notes/2026-11-26-garden.md)
    1. 연못 '기본' 자리 오른쪽, 낚인 포켓몬이 내려앉는 자리 다음에 화분 셋이 놓인 나무 화단 하나
    2. 빈 화분을 누르면 심을 열매 메뉴 (4 · 8 · 16시간 묶음) - 고른 열매 하나가 씨앗이 된다
    3. 자라는 화분을 누르면 그 순간 물이 필요한 화분 모두에 물 → 그 단계의 물방울이 찬다
    4. 익은 화분을 누르면 익은 화분 전부를 거두고, 같은 열매가 가방에 있으면 그 자리에 다시 심는다
    5. 친구 집에 가 있으면 그 자리에 친구 화단이 흐리게 (누르면 친구 물) · 내 포켓몬 오른클릭 '열매 먹이기'

단계 · 남은 초 · 물 · 하루 천장은 **서버가 읽을 때 시계로 센다** (앱이 꺼져 있어도 자란다, 시계 조작이 안 통한다).
앱은 카드대로 그리고, 어느 화분이든 단계가 바뀌는 때(nextIn)에 다시 묻는다.
누름은 뗄 때가 아니라 누를 때 받는다 - 맥은 앱이 비활성일 때 '뗐다' 를 잃는다 (낚시와 같다).
"""
import math
import time
import tkinter as tk

from common import held as HELD
from common.korean import natural

from . import config
from . import fishing as FI
from . import fishing_art as FART
from . import garden_art as ART
from . import platform_os as PLAT
from . import ui_common as U
from .ui_common import run_async

# 앱 글자 (설계 그대로)
TIP_EMPTY = "눌러서 열매 심기"
TIP_RIPE = "다 익었어요! 누르면 거둬요"
TIP_CAP = "오늘은 %d개를 다 거뒀어요 · 0시부터 다시"
TIP_FRIEND = "눌러서 화분에 물 주기"
# 친구 화단 마우스 올림 · 누름 글. 오른쪽 클릭 메뉴 줄은 손님 펫 메뉴와 같은 글을 쓴다 (visit.WATER_WHY)
FRIEND_WHY = {"empty": "심은 화분이 없어요", "ripe": "다 익은 화분뿐이에요", "bonus": "이미 물을 받은 화분뿐이에요",
              "done": "오늘은 이미 물을 받았어요", "closed": "친구 텃밭이 닫혀 있어요"}
HINT_FIRST = "화분을 눌러 열매를 심어 보세요"
HINT_WATER = "단계마다 물을 주면 열매가 늘어요"
HINT_RIPE = "다 익었어요! 눌러서 거둬요"
HINTS = {1: HINT_FIRST, 2: HINT_WATER, 3: HINT_RIPE}   # 안내 단계 (설정 gardenHints 에 띄운 단계를 남긴다)
MENU_PLANT = "심을 열매"
MENU_PULL = "뽑기"
MENU_MOVE = "텃밭 옮기기"
MENU_HIDE = "텃밭 숨기기"
FEED = "열매 먹이기"
FEED_DONE = "열매 먹이기 (오늘 줌)"
SAY_FED = "%s 냠 ♥ +%d (%d/255)"
SAY_FRIEND = "%s 님이 화분에 물을 줬어요 +1"        # 주인 화면 (놀러 가기의 visit.WATERED 와 같은 글)
SAY_REPLANT = "다시 심음"
SAY_PLANTED = "%s을(를) 심었어요"
SAY_WATERED = "물을 줬어요"
SAY_ENOUGH = "물은 넉넉해요"
SAY_NOT_RIPE = "아직 익은 화분이 없어요"
SAY_SEED_BACK = "씨앗을 돌려받았어요"
SAY_PULLED = "뽑았어요"
SAY_GAVE = "친구 화분에 물을 줬어요"
BAIT_MARK = " · 미끼"
NO_BERRY = "가진 지닌 열매가 없습니다"
GROUP_KR = {4: "4시간", 8: "8시간", 16: "16시간"}
GROUP_ROWS = 5               # 심을 열매 메뉴: 묶음마다 이만큼 (많은 순)
CAP = 20                     # 하루 거둠 천장 (카드에 cap 이 없을 때)

LANE_MIN = 64                # 연못 오른쪽 낚인 포켓몬이 내려앉는 자리 - 가장 좁을 때 (fishing.anchor 의 +30 에 도트 반 폭)
LANE_PAD = 16                # 포켓몬 크기에 더 비우는 틈 (lane)
ROW_GAP = 4                  # 좁은 영역: 연못 위 줄과의 틈

GOLD = "#ffd447"
WARN = "#ffd447"
SAD = "#ff8a8a"
GOOD = "#7bffa0"
BLUE = "#9fd8ff"
PINK = "#ff9ecb"
WHITE = "#ffffff"


# ---------------------------------------------------------------- 글 · 셈
def left_text(sec):
    """익기까지 남은 때 - 분은 올림 (1초 남아도 '1분'). 1분 안쪽이면 곧 익는다."""
    m = int(math.ceil(max(0.0, float(sec or 0)) / 60.0))
    if m <= 0:
        return "곧 익어요"
    h, m = divmod(m, 60)
    if h and m:
        return "%d시간 %d분 남음" % (h, m)
    if h:
        return "%d시간 남음" % h
    return "%d분 남음" % m


def drops_text(mask):
    return "".join("●" if int(mask or 0) & (1 << k) else "○" for k in range(3))


def berry_kr(iid):
    return HELD.KR.get(iid or "", iid or "")


def group_of(iid):
    """열매의 묶음 (4 · 8 · 16시간) - 서버와 같은 표 (common.garden). 표를 못 읽으면 None (묶음 없이 맨 끝)."""
    try:
        from common import garden as GC
    except ImportError:
        return None
    return GC.group_of(iid)


def _stage(pot):
    try:
        return int((pot or {}).get("stage") or 0)
    except (TypeError, ValueError):
        return 0


def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def lane(settings):
    """연못 오른쪽에 비워 둘 낚인 포켓몬 자리 (px) - 포켓몬 크기를 따라 넓어진다: max(64, 크기 x maxScale + 16).

    고정 64px 이면 '포켓몬 크기' 를 키웠을 때(120) 연못 오른쪽 +30 에 내려앉은 낚인 포켓몬 창이 첫 화분을 덮었다 -
    그 자리를 누르면 화분이 아니라 야생이 받았다 (검토 8). 크기를 바꾸면 _follow_area 가 화단을 새 자리로 옮긴다."""
    s = settings or {}
    th = _num(s.get("targetHeight")) or _num(config.DEFAULTS.get("targetHeight"))
    ms = _num(s.get("maxScale")) or _num(config.DEFAULTS.get("maxScale"))
    return max(LANE_MIN, int(round(th * ms)) + LANE_PAD)


def menu_row(app, pet):
    """내 포켓몬 오른쪽 클릭 메뉴의 '열매 먹이기' 줄 (텃밭이 열렸을 때 · 내 포켓몬만). 오늘 먹였으면 죽은 줄.

    놀러 온 친구 포켓몬 · 야생은 id 가 0 아래라 줄이 없다. App 메서드를 빌려 쓰는 검사의 가짜 앱은 garden 이
    없거나 아무 것이나 들고 있다 - 진짜 텃밭(fed_today · feed)이 아니면 줄을 안 만든다.
    """
    gd = getattr(app, "garden", None)
    if gd is None or not callable(getattr(gd, "fed_today", None)) or not callable(getattr(gd, "feed", None)):
        return None
    if getattr(gd, "open", False) is not True:
        return None
    pid = getattr(pet, "id", 0) or 0
    if pid <= 0:
        return None
    if gd.fed_today(pid):
        return {"text": FEED_DONE, "enabled": False}
    return {"text": FEED, "command": lambda: gd.feed(pet)}


# ---------------------------------------------------------------- 화단 창
class Planter(object):
    """화단 창 하나 (연못 · 풀숲과 같은 방식의 작은 창). 그림은 garden_art 가 그린다. 누른 x 로 화분을 고른다."""

    CACHE = 8                # 모습마다 만든 그림을 이만큼 들고 있는다 (카드가 바뀔 때만 새로 만든다)

    def __init__(self, ctl, x, y):
        self.ctl = ctl
        ov = ctl.app.overlay
        self.key = tuple(ov.key)
        self.fw, self.fh = ART.size()
        self.x, self.y = int(x), int(y)
        self.look = None
        self.frame_i = 0
        self.front = None               # 지금 '항상 위' 인가 (None = 아직 안 정함)
        self._cache = {}
        self.win = tk.Toplevel(ov.root)
        self.win.overrideredirect(True)
        # 자리를 먼저 - 만들자마자 엉뚱한 곳에 한 번 떴다 옮겨 가는 것이 보이지 않게 (overlay.Pet 과 같다)
        self.win.geometry("+%d+%d" % (self.x, self.y))
        bg = PLAT.transparent_window(self.win, "#%02x%02x%02x" % self.key)
        self.view = PLAT.SpriteView(self.win, bg, self.fw, self.fh, cursor="hand2")
        self.label = self.view.widget
        self.label.bind("<Button-1>", ctl.on_press)
        PLAT.bind_right(self.label, ctl.on_menu)
        self.label.bind("<Enter>", ctl.on_hover)
        self.label.bind("<Motion>", ctl.on_hover)
        self.label.bind("<Leave>", lambda e: ctl.hide_tip())

    def show(self, look, i):
        """그 모습의 i 번째 장. 같은 모습이면 만든 그림을 다시 쓴다 (맥은 그림마다 CGImage · 클릭 자리를 만든다)."""
        fr = self._cache.get(look)
        if fr is None:
            if len(self._cache) >= self.CACHE:
                self._cache.pop(next(iter(self._cache)))
            pots, mode, water, faded = look
            fr = self._cache[look] = self.view.frames(list(ART.frames(pots, self.key, mode, water, faded)), self.key)
        self.look = look
        self.view.show(fr[i % len(fr)])

    def move(self, x, y):
        self.x, self.y = int(x), int(y)
        try:
            self.win.geometry("+%d+%d" % (self.x, self.y))
        except Exception:                                   # noqa: BLE001
            pass

    def rect(self):
        return (self.x, self.y, self.x + self.fw, self.y + self.fh)

    def destroy(self):
        try:
            self.view.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass


# ---------------------------------------------------------------- 텃밭 조종
class GardenController(object):
    """텃밭 전체를 맡는다 (앱이 하나 들고 있다 - app.garden).

    mode: None(안 보임) · 'mine'(내 화단) · 'friend'(놀러 간 친구 집의 화단, 흐리게)
    """

    TICK_MS = 150              # 화단 그림 · 클릭 통과 · 층 맞추기
    SPARK_TICKS = 3            # 반짝임 한 장을 이만큼 틱 동안 (약 0.45초)
    AREA_TICKS = 7             # 화단 자리를 다시 볼 틱 수 (약 1초)
    WATER_TICKS = 12           # 물뿌리개 연출 (6장 x 2바퀴)
    STALE_S = 12.0             # 방금 무엇을 했으면 그보다 먼저 떠난 동기화 카드는 믿지 않는다
    NEXT_MAX_S = 6 * 3600      # nextIn 이 이보다 길면 이만큼 뒤에 (계약 - 6시간 넘으면 6시간)
    NEXT_SLACK_MS = 1500       # 단계가 바뀌는 그 초에 묻으면 서버 시계와 엇갈려 옛 단계를 받을 수 있다
    HINT_MS = 10 * 60 * 1000   # 화단이 처음 보이고 첫 안내까지 - 연못 안내와 겹치지 않게 (설계 '연못 안내 뒤 10분')
    HINT_RETRY_MS = 60 * 1000  # 연못 안내가 아직이거나 안내할 포켓몬이 없으면
    POND_GAP_MS = 10 * 60 * 1000   # 마지막 연못 안내(설정 pondHintAt)에서 이만큼 지나야 텃밭 안내 (안내 셋 모두)
    BUBBLE_GAP_S = 8.0         # 같은 포켓몬 위에 다른 말풍선이 뜬 지 이만큼 안이면 기다린다 - 따로 뜨는 말풍선은 안 쌓인다
    PUSH_REFRESH_MS = 2500     # 친구가 물을 준 연출 뒤 카드를 다시 본다 (친구 물 보너스 별)
    FRIEND_WAIT_S = 15.0       # 친구 화단을 누른 뒤 이 안에 '오늘 받음' view 가 오면 내가 준 물이다
    MOVE_LIMIT_MS = 30000      # 옮기기 덮개를 잊고 두면 저절로 걷는다
    BUBBLE_MS = 7000

    def __init__(self, app):
        self.app = app
        self.card = None
        self.open = False
        self.paused = False
        self.friend = None         # 놀러 간 친구 화단 view {canWater, why, pots} (visit.py 가 show_friend 로 준다)
        self.mode = None
        self.planter = None
        self.moving = None
        self.tip = None
        self.errors = 0
        self._jobs = {}
        self._req = None           # 서버에 보내 둔 동작 (plant · water · harvest · pull · friend)
        self._loading = False
        self._again = False
        self._menu_loading = False
        self._acted = 0.0
        self._got_at = 0.0         # 카드를 받은 때 - 남은 초를 그만큼 줄여 적는다
        self._next_s = None
        self._epoch = 0
        self._seq = 0              # 카드를 바꾸는 일(동작 시작 · 끝 · 먹이)마다 오른다 - 그 전에 떠난 카드 묻기는 버린다
        self._hint_want = 0        # 띄우고 싶은 가장 높은 안내 단계 (때가 맞을 때까지 _try_hint 가 기다린다)
        self._life = 0             # 로그인 한 번 (clear 가 올린다) - 먹이 답은 이것만 본다
        self._anim = 0             # 물뿌리개 연출 남은 틱
        self._anim_slots = ()
        self._home = None
        self._tip_slot = None
        self._friend_tap = 0.0
        self._feeding = set()

    # ---------------------------------------------------------------- 타이머
    def _after(self, name, ms, fn):
        """이름 붙인 예약 하나 (같은 이름은 앞의 것을 지운다). clear() 가 전부 지운다."""
        self._cancel(name)

        def run():
            self._jobs.pop(name, None)
            fn()
        self._jobs[name] = self.app.root.after(max(1, int(ms)), run)

    def _cancel(self, *names):
        for name in names:
            job = self._jobs.pop(name, None)
            if job is not None:
                try:
                    self.app.root.after_cancel(job)
                except Exception:                           # noqa: BLE001
                    pass

    # ---------------------------------------------------------------- 밖에서 부르는 것
    def note(self, card):
        """/api/me 동기화 · 주인 쪽 친구 물 푸시의 카드. 방금 무엇을 했으면(심기 · 물 …) 그 전에 떠난 카드일 수 있다."""
        if self._req is not None or time.time() - self._acted < self.STALE_S:
            if not (isinstance(card, dict) and card.get("open")):
                self._apply(card)               # 닫힘(열리기 전 · 시즌이 바뀜)은 그대로 믿는다
            return
        self._apply(card)

    def pause(self):
        """풀숲이 멈출 때 같이 (친구 집 · 집중 · 올림픽 중계 · 투기장 · 공습 · 로그아웃). 화단을 걷는다 - 화분은 서버에서 자란다."""
        self.paused = True
        self._end_move()
        self._sync()

    def resume(self):
        """풀숲이 다시 돌 때. 카드를 다시 물어서 맞춘다 (쉬는 사이 단계가 바뀌었을 수 있다)."""
        self.paused = False
        self.refresh()
        self._sync()

    def set_visible(self, on):
        """설정 '텃밭 보이기' 가 바뀌었다 (저장은 부르는 쪽이 했다). 꺼도 화분은 그대로 자란다."""
        if not on:
            self._end_move()
        self._sync()
        self._paint()

    def clear(self):
        """로그아웃 · 세션 끊김 · 종료. 창 · 타이머를 전부 치우고 처음으로 (다음 카드가 오면 다시 뜬다)."""
        self._epoch += 1                 # 이미 보낸 요청의 답은 버린다
        self._life += 1
        for name in list(self._jobs):
            self._cancel(name)
        self._end_move()
        self.hide_tip()
        if self.planter is not None:
            self.planter.destroy()
            self.planter = None
        self.card = None
        self.open = False
        self.paused = False
        self.friend = None
        self.mode = None
        self._req = None
        self._loading = self._again = self._menu_loading = False
        self._acted = 0.0
        self._next_s = None
        self._hint_want = 0
        self._anim = 0
        self._anim_slots = ()
        self._home = None
        self._tip_slot = None
        self._friend_tap = 0.0
        self._feeding = set()

    def rect(self):
        """화단 자리 (x1, y1, x2, y2) - 풀숲 · 알이 피한다. 안 보이면 None."""
        return self.planter.rect() if self.planter is not None else None

    def spot(self):
        """주인 쪽: 놀러 온 포켓몬이 물을 주러 걸어갈 발 자리 (x, y) - 화단 옆 바닥 줄. 화단이 안 보이면 None.

        왼쪽은 낚인 포켓몬이 내려앉는 자리라 오른쪽을 먼저 쓴다 (자리가 모자라면 왼쪽)."""
        p = self.planter
        if p is None or self.mode != "mine":
            return None
        x1, _y1, x2, _y2 = self.app.overlay.area()
        right = x2 - (p.x + p.fw)
        if right >= 60 or right >= p.x - x1:
            return (p.x + p.fw + 26, p.y + p.fh)
        return (p.x - 26, p.y + p.fh)

    def play_water(self, name):
        """주인 쪽: 친구가 내 화분에 물을 줬다 - 물뿌리개 연출과 글. 화단이 안 보이면 False (말풍선은 놀러 가기 몫)."""
        p = self.planter
        if p is None or self.mode != "mine":
            return False
        pots = self._pots()
        slots = [i for i, pot in enumerate(pots) if 1 <= _stage(pot) <= 3] or [0, 1, 2]
        self._water_anim(slots)
        self._say(None, SAY_FRIEND % (name or "친구"), BLUE, ms=2600, dy=-12)
        # 실린 카드(note)가 '방금 한 일' 에 막힐 수 있다 - 연출 뒤에 한 번 더 물어 친구 물 보너스 별을 맞춘다
        self._after("pushfresh", self.PUSH_REFRESH_MS, self.refresh)
        return True

    def show_friend(self, view):
        """손님 쪽: 친구(주인)의 화단 view {canWater, why, pots} 를 내 화단 자리에 흐리게. None 이면 걷는다 (내 화단은
        풀숲과 함께 돌아온다). 내가 누른 뒤 '오늘 받음' view 가 오면 그것이 내가 준 물이다 - 물뿌리개를 보인다."""
        if isinstance(view, dict) and view.get("why") == "closed":
            view = None                                       # 친구 텃밭이 닫혔다 - 그릴 것이 없다
        old = self.friend
        self.friend = view if isinstance(view, dict) else None
        gave = (self.friend is not None and old is not None and old.get("canWater")
                and not self.friend.get("canWater") and self.friend.get("why") == "done"
                and time.time() - self._friend_tap < self.FRIEND_WAIT_S)
        self._sync()
        if gave:
            self._friend_tap = 0.0
            pots = self._pots()
            self._water_anim([i for i, pot in enumerate(pots) if 1 <= _stage(pot) <= 3] or [0, 1, 2])
        self._paint()

    def fed_today(self, pid):
        """오늘 먹인 포켓몬인가 (카드의 fedToday - 먹인 그 자리에서 앱도 적어 둔다)."""
        try:
            return int(pid) in [int(x) for x in ((self.card or {}).get("fedToday") or [])]
        except (TypeError, ValueError):
            return False

    def reposition(self):
        """영역이 바뀌었다 - 다시 놓는다 (옮겨 둔 것은 영역 안 비율대로)."""
        p = self.planter
        if p is None:
            return
        self._home = self.home(p.fw, p.fh)
        p.move(*self._home)
        self.hide_tip()

    def _follow_area(self):
        """영역이 app._area_changed 없이 바뀌었으면 따라간다 (모니터를 뺌 · 해상도 · 작업 표시줄 - 연못과 같다)."""
        p = self.planter
        if p is None or self.moving is not None:
            return
        if self.home(p.fw, p.fh) != self._home:
            self.reposition()

    # ---------------------------------------------------------------- 자리
    def home(self, w, h):
        """화단 자리. 옮겨 둔 것(gardenPos)이 있으면 그것. 없으면 **연못 기본 자리** + 연못 너비 + 낚인 포켓몬 자리
        (lane - 포켓몬 크기만큼, 적어도 64px), 바닥에 맞춰.

        연못의 지금 자리가 아니라 기본 자리를 본다 - 연못을 옮기거나 숨겨도 이 칸은 비워 두고(낚인 포켓몬 자리),
        화단이 연못을 따라 이리저리 다니지 않는다. 오른쪽이 모자란 좁은 영역이면 연못 위 줄.
        """
        ov = self.app.overlay
        x1, y1, x2, y2 = ov.area()
        m = ov.settings["areaMargin"]
        lo_x, hi_x = x1 + m, max(x1 + m, x2 - w - m)
        lo_y, hi_y = y1 + m, max(y1 + m, y2 - h - m)
        pos = self.app.settings.get("gardenPos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            try:
                fx = min(1.0, max(0.0, float(pos[0])))
                fy = min(1.0, max(0.0, float(pos[1])))
                return (int(round(lo_x + fx * (hi_x - lo_x))), int(round(lo_y + fy * (hi_y - lo_y))))
            except (TypeError, ValueError):
                pass
        pw, ph = FART.size()
        px, py = FI.default_home(ov, pw, ph)
        x = px + pw + lane(ov.settings)
        if x <= hi_x:
            return (int(x), int(hi_y))
        return (int(max(lo_x, min(px, hi_x))), int(max(lo_y, py - h - ROW_GAP)))

    def _ratio(self, x, y, w, h):
        ov = self.app.overlay
        x1, y1, x2, y2 = ov.area()
        m = ov.settings["areaMargin"]
        sx = max(1, (x2 - w - m) - (x1 + m))
        sy = max(1, (y2 - h - m) - (y1 + m))
        return [round(min(1.0, max(0.0, (x - x1 - m) / float(sx))), 4),
                round(min(1.0, max(0.0, (y - y1 - m) / float(sy))), 4)]

    # ---------------------------------------------------------------- 보이기
    def _away(self):
        """친구 집에 가 있거나 집중 · 올림픽 중계 · 공습 중 (풀숲이 쉬는 때와 같다)."""
        w = getattr(self.app, "wild", None)
        if w is None:
            return False
        try:
            return bool(w._away() or w._focusing())
        except Exception:                                   # noqa: BLE001
            return False

    def _want(self):
        """지금 그릴 화단 - 'friend' · 'mine' · None. 친구 화단은 놀러 가 쉬는 동안(paused)에도 그린다."""
        if self.app.overlay is None or not config.show_garden(self.app.settings):
            return None
        if self.friend is not None:
            return "friend"
        if self.open and not self.paused and not self._away():
            return "mine"
        return None

    def _sync(self):
        """보여야 하면 화단을 세우고, 아니면 걷는다."""
        want = self._want()
        if want is None:
            self._cancel("tick", "hint")
            self.hide_tip()
            self._end_move()
            if self.planter is not None:
                self.planter.destroy()
                self.planter = None
            self.mode = None
            self._anim = 0
            return
        if want != self.mode:
            self.hide_tip()
            self._end_move()
            self._anim = 0
        self.mode = want
        if self.planter is None:
            x, y = self._home = self.home(*ART.size())
            try:
                self.planter = Planter(self, x, y)
            except Exception as e:                          # noqa: BLE001
                self.planter = None
                self.errors += 1
                config.log("화단을 못 띄웠습니다: %s" % e)
                return
            self._paint()
            self._layer(force=True)
            self._after("tick", self.TICK_MS, self._tick)
        if want != "mine":
            self._cancel("hint")
        elif "hint" not in self._jobs:
            done = int(self.app.settings.get("gardenHints") or 0)
            if self._hint_want > done:
                self._after("hint", self.HINT_RETRY_MS, self._try_hint)     # 쉬는 사이 미뤄 둔 안내 (심기 · 익음)
            elif done < 1:
                self._after("hint", self.HINT_MS, self._first_hint)

    def _freeze_setting(self):
        """'텃밭 보이기' 의 처음 값은 그때의 '낚시터 보이기' 를 따른다 - 연못을 끈 사람에게 갑자기 화단이 생기지 않게."""
        s = self.app.settings
        if s.get("showGarden") is None:
            s["showGarden"] = config.show_pond(s)
            try:
                config.save_settings(s)
            except Exception:                               # noqa: BLE001
                pass

    # ---------------------------------------------------------------- 카드
    def refresh(self):
        """카드를 다시 묻는다 (GET /api/garden). 그사이 내가 무엇을 했으면 답을 버린다.

        동작(거두기 …)을 보낸 **사이에** 부른 것도 버린다 - _epoch 는 동작을 시작할 때만 올라서, 그 뒤에 떠난 GET 이
        동작 전 줄을 읽고 동작 답보다 늦게 오면 새 카드를 덮었다 (익은 화분이 되살아남 · '오늘 줌' 이 풀림, 검토 5).
        _seq 는 동작의 시작 · 끝 · 먹이마다 오르므로 그 사이에 떠난 묻기는 모두 걸린다. 버리면 동작 답의 카드가 맞다
        (동작이 실패했으면 그 쪽이 다시 묻는다 - _again)."""
        api = self.app.api
        if api is None or not hasattr(api, "garden"):
            return
        if self._loading:
            self._again = True
            return
        self._loading = True
        epoch, seq = self._epoch, self._seq

        def done(r, err):
            self._loading = False
            if epoch == self._epoch and seq == self._seq and self._req is None:
                if err is None:
                    self._apply(r)
                elif getattr(err, "status", 0) == 404:
                    self._apply(None)            # 열리기 전 · 텃밭을 모르는 서버
            if self._again:
                self._again = False
                self.refresh()
        run_async(self.app.root, api.garden, done)

    def _apply(self, card):
        """카드대로 맞춘다 (계약: open · pots[3] · harvested · cap · nextIn · fedToday · friendWater)."""
        self.card = card if isinstance(card, dict) else None
        self._got_at = time.time()
        if not self.card or not self.card.get("open"):
            self.open = False
            self._next_s = None
            self._cancel("next")
            self._sync()
            return
        self.open = True
        self._freeze_setting()
        self._sync()
        nxt = self.card.get("nextIn")
        if nxt is not None:
            # 어느 화분이든 단계가 바뀌는 때에 다시 묻는다 (앱이 단계를 셈하지 않는다 - 서버 시계만 믿는다)
            self._next_s = min(self.NEXT_MAX_S, max(1, int(_num(nxt))))
            self._after("next", self._next_s * 1000 + self.NEXT_SLACK_MS, self.refresh)
        else:
            self._next_s = None
            self._cancel("next")
        if self.mode == "mine" and any((p or {}).get("ripe") for p in self._pots()):
            self._hint(3)
        self._paint()

    def _pots(self):
        """지금 그리는 화분 셋 (내 카드 또는 친구 view) - 빠진 칸은 빈 화분."""
        src = (self.friend or {}).get("pots") if self.mode == "friend" else (self.card or {}).get("pots")
        out = [{}, {}, {}]
        for i, p in enumerate(src or []):
            if not isinstance(p, dict):
                continue
            slot = p.get("slot", i)
            try:
                slot = int(slot)
            except (TypeError, ValueError):
                slot = i
            if 0 <= slot < 3:
                out[slot] = p
        return out

    # ---------------------------------------------------------------- 누르기
    def _slot_of(self, e):
        """눌린 화분 번호. Tk 이벤트는 창 안 x, 맥 감시자가 넘긴 오른쪽 클릭은 화면 x 만 있다."""
        x = getattr(e, "x", None)
        if x is None and self.planter is not None:
            x = getattr(e, "x_root", 0) - self.planter.x
        return ART.slot_at(x or 0)

    def _at(self, e, slot):
        """메뉴를 띄울 화면 자리 (검사가 만든 이벤트는 화면 좌표가 없을 수 있다 - 그때는 그 화분 위)."""
        x, y = getattr(e, "x_root", 0) or 0, getattr(e, "y_root", 0) or 0
        p = self.planter
        if (not x and not y) and p is not None:
            x, y = p.x + ART.pot_x(slot), p.y + p.fh // 2
        return x, y

    def on_press(self, e=None):
        """화단을 눌렀다 (<Button-1> - 뗌이 아니라 누름). 그 화분 상태에 따라 심기 메뉴 · 물 · 거두기."""
        if self.moving is not None or self.planter is None:
            return
        self.hide_tip()
        slot = self._slot_of(e)
        if self.mode == "friend":
            return self._friend_press(slot)
        if self._req is not None:
            return
        pot = self._pots()[slot]
        st = _stage(pot)
        if st <= 0:
            return self.plant_menu(slot, *self._at(e, slot))
        if pot.get("ripe") or st >= 4:
            return self.harvest(slot)
        return self.water(slot)

    def plant_rows(self, slot, berries, sub=False):
        """심을 열매 줄 (PopupMenu 꼴) - 머리줄 4시간 / 8시간 / 16시간 아래 가진 지닌 열매, 묶음마다 많은 순 다섯 줄.

        지금 미끼로 쓰는 열매는 '· 미끼' (심으면 미끼가 줄어든다는 것을 알게). sub 면 오른쪽 클릭 메뉴의 '심을 열매'
        아래에 들어가는 것이라 머리줄 대신 한 칸 들인 죽은 줄로 쓴다 (머리줄 아래 머리줄은 읽기 어렵다)."""
        bait = self.app.settings.get("lastBait")
        groups = {}
        for iid, kr, n in berries:
            groups.setdefault(group_of(iid), []).append((iid, kr, n))
        base = 1 if sub else 0
        rows = []
        if not berries:
            rows.append({"text": NO_BERRY, "enabled": False, "indent": base})
        for g in (4, 8, 16, None):
            items = groups.get(g)
            if not items:
                continue
            label = GROUP_KR.get(g, "기타")
            rows.append({"text": label, "enabled": False, "indent": base} if sub else {"text": label, "header": True})
            for iid, kr, n in items[:GROUP_ROWS]:
                rows.append({"text": "%s ×%d%s" % (kr, n, BAIT_MARK if iid == bait else ""), "indent": base + 1,
                             "command": (lambda i=iid: self.plant(slot, i))})
        return rows

    def plant_menu(self, slot, x, y):
        """빈 화분을 눌렀다 - 가방을 물어 심을 열매 메뉴를 그때 만든다."""
        if self._menu_loading or self.app.api is None:
            return
        self._menu_loading = True

        def done(r, err):
            self._menu_loading = False
            if self.planter is None or self.mode != "mine":
                return                          # 가방을 묻는 사이에 화단이 걷혔다 (숨기기 · 로그아웃)
            if err is not None:
                return self._fail(err)
            self._show_menu(self.plant_rows(slot, FI.baits(r)), x, y)
        run_async(self.app.root, self.app.api.bag, done)

    def _show_menu(self, rows, x, y):
        if not PLAT.NATIVE_MENU:
            # 맥. tk.Menu 는 NSMenu 라 여는 순간 앱이 죽는다 (app.pet_menu 와 같다)
            U.PopupMenu(self.app.root, rows, x, y, width=220)
            return
        m = self._menu()
        _fill(m, rows)
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def _menu(self, parent=None):
        return tk.Menu(parent or self.app.root, tearoff=0, bg=U.BG2, fg=U.FG, activebackground=U.BG4,
                       activeforeground=U.FG, bd=0, font=U.FONT_S)

    def plant(self, slot, berry):
        api = self.app.api
        if api is None or self._req is not None:
            return
        self._start("plant")
        epoch = self._epoch

        def done(r, err):
            if epoch != self._epoch:
                return
            self._finish()
            if err is not None:
                self._fail(err, slot)
                if getattr(err, "status", 0) == 409:
                    self.refresh()               # 다른 PC 에서 심었다 - 카드를 다시 물어 맞춘다
                return
            self._apply(_card_of(r))
            self._say(slot, natural(SAY_PLANTED % berry_kr(berry)), GOOD, ms=1400)
            self._bag_changed()
            self._hint(2)
        run_async(self.app.root, lambda: api.garden_plant(slot, berry), done)

    def water(self, slot):
        """그 순간 물이 필요한 화분 모두에 물 (서버가 단계 비트를 채운다). 줄 것이 없으면 그렇다고만."""
        api = self.app.api
        if api is None or self._req is not None:
            return
        need = [i for i, p in enumerate(self._pots()) if p.get("needsWater")] or [slot]
        self._start("water")
        epoch = self._epoch

        def done(r, err):
            if epoch != self._epoch:
                return
            self._finish()
            if err is not None:
                self._fail(err, slot)
                return self.refresh()
            r = r or {}
            if int(r.get("watered") or 0) > 0:
                self._water_anim(need)
                self._say(slot, SAY_WATERED, BLUE, ms=1200)
            else:
                self._say(slot, SAY_ENOUGH, WHITE, ms=1200)
            if isinstance(r.get("card"), dict):
                self._apply(r["card"])
            else:
                self.refresh()
        run_async(self.app.root, api.garden_water, done)

    def harvest(self, slot):
        """익은 화분을 모두 거두고, 같은 열매가 가방에 있으면 그 자리에 다시 심는다 (서버가 한다)."""
        api = self.app.api
        if api is None or self._req is not None:
            return
        self._start("harvest")
        epoch = self._epoch

        def done(r, err):
            if epoch != self._epoch:
                return
            self._finish()
            if err is not None:
                self._fail(err, slot)
                return self.refresh()
            r = r or {}
            got = [g for g in (r.get("got") or []) if isinstance(g, dict)]
            card = r.get("card") if isinstance(r.get("card"), dict) else None
            if got:
                text = " · ".join("+%d %s" % (int(_num(g.get("n"))), g.get("kr") or berry_kr(g.get("berry")))
                                  for g in got)
                if r.get("replanted"):
                    text += " · " + SAY_REPLANT
                self._say(slot, text, GOLD, ms=2200)
                if r.get("capped"):
                    # 거두다가 하루 천장에 닿았다 - 남은 화분은 기다린다고 바로 알린다 (실제 앱 시험 11/27: 마우스를 올려야 알았다)
                    cap = int(_num((card or self.card or {}).get("cap")) or CAP)
                    self._say(None, TIP_CAP % cap, WARN, ms=2600, dy=-28)
                self._bag_changed()
            elif r.get("capped"):
                cap = int(_num((card or self.card or {}).get("cap")) or CAP)
                self._say(slot, TIP_CAP % cap, WARN, ms=2200)
            else:
                self._say(slot, SAY_NOT_RIPE, WHITE, ms=1400)
            if card is not None:
                self._apply(card)
            else:
                self.refresh()
        run_async(self.app.root, lambda: api.garden_harvest(True), done)

    def pull(self, slot):
        """화분을 비운다. 새싹 단계면 서버가 씨앗을 돌려준다 - 돌려줬는지는 답의 refunded 로만 안다.

        앱 카드의 단계로 정하지 않는다: 단계는 nextIn · 동기화 때만 다시 읽어서(잠에서 깬 직후 등) 앱은 새싹인데 서버는
        이미 줄기일 수 있다 - 그러면 돌려받지 않은 씨앗을 '돌려받았어요' 라고 했다 (검토 1). 칸이 없는 답(옛 서버)이면
        씨앗 글 없이 '뽑았어요'."""
        api = self.app.api
        if api is None or self._req is not None:
            return
        self._start("pull")
        epoch = self._epoch

        def done(r, err):
            if epoch != self._epoch:
                return
            self._finish()
            if err is not None:
                self._fail(err, slot)
                return self.refresh()
            r = r if isinstance(r, dict) else {}
            seed = bool(r.get("refunded"))
            self._apply(_card_of(r))
            self._say(slot, SAY_SEED_BACK if seed else SAY_PULLED, WHITE, ms=1400)
            if seed or "refunded" not in r:
                self._bag_changed()          # 돌려받았거나 모른다 - 가방 수를 다시 본다
        run_async(self.app.root, lambda: api.garden_pull(slot), done)

    def _start(self, kind):
        self._req = kind
        self._acted = time.time()
        self._epoch += 1
        self._seq += 1

    def _finish(self):
        self._req = None
        self._acted = time.time()
        self._seq += 1                   # 동작 중에 떠난 카드 묻기(refresh)는 이 답보다 옛것이다

    def _fail(self, err, slot=None):
        msg = natural(getattr(err, "message", "") or str(err) or "텃밭을 돌보지 못했습니다.")
        self.app.notify(msg)
        self._say(slot, msg.rstrip("."), SAD, ms=1800)

    def _bag_changed(self):
        fn = getattr(self.app, "bag_changed", None)
        if fn is not None:
            try:
                fn()
            except Exception:                               # noqa: BLE001
                pass

    # ---------------------------------------------------------------- 친구 화단
    def _friend_press(self, slot):
        """친구 화단을 눌렀다 - 줄 수 있으면 친구 물. 놀러 가기(Visit.water)가 있으면 그 길로 보낸다 (메뉴 줄과 같은 길 -
        답의 view 가 show_friend 로 다시 온다). 못 주면 까닭만."""
        v = self.friend or {}
        if not v.get("canWater"):
            return self._say(slot, FRIEND_WHY.get(v.get("why"), "지금은 물을 줄 수 없어요"), WARN, ms=1600)
        self._friend_tap = time.time()
        vis = getattr(self.app, "visit", None)
        fn = getattr(vis, "water", None) if vis is not None else None
        if callable(fn):
            fn()
            return
        api = self.app.api
        if api is None or self._req is not None or not hasattr(api, "visit_water"):
            return
        self._start("friend")
        epoch = self._epoch

        def done(r, err):
            if epoch != self._epoch:
                return
            self._finish()
            if err is not None:
                return self._fail(err, slot)
            r = r or {}
            n = int(_num(r.get("bonus")))
            self._say(slot, SAY_GAVE + ((" · 열매 +%d" % n) if n > 0 else ""), BLUE, ms=1800)
            if isinstance(r.get("garden"), dict):
                self.show_friend(r["garden"])
        run_async(self.app.root, api.visit_water, done)

    # ---------------------------------------------------------------- 먹이
    def feed(self, pet):
        """바탕화면 포켓몬에게 열매를 먹인다 (하루 한 번 · 친밀도 +10). 서버가 가방에서 가장 많은 지닌 열매를 고른다 -
        지금 미끼는 빼 달라고 보낸다. 친밀 진화 조건을 넘으면 가방의 진화 도구와 같은 길로 진화 연출."""
        pid = getattr(pet, "id", 0) or 0
        api = self.app.api
        if pid <= 0 or api is None or pid in self._feeding:
            return
        self._feeding.add(pid)
        avoid = self.app.settings.get("lastBait") or None
        # 화분 일(심기 · 물 …)의 _epoch 가 아니라 로그인 한 번만 본다 - 먹이는 사이에 화분을 눌렀다고 진화 연출을 버리면
        # 진화한 줄 모른다 (검토 '먹이 진화가 앱에 안 보이기')
        life = self._life

        def done(r, err):
            self._feeding.discard(pid)
            if life != self._life:
                return
            if err is not None:
                msg = natural(getattr(err, "message", "") or str(err) or "열매를 먹이지 못했습니다.")
                self.app.notify(msg)
                self._over_pet(pid, msg.rstrip("."), SAD, 1800)
                self.refresh()                   # 오늘 줌 · 바탕화면 아님 - 카드의 fedToday 를 맞춘다
                return
            r = r or {}
            if isinstance(self.card, dict):
                fed = list(self.card.get("fedToday") or [])
                if pid not in fed:
                    fed.append(pid)
                self.card["fedToday"] = fed
                self._acted = time.time()        # 먹이기 전에 떠난 동기화 카드가 '안 먹임' 으로 되돌리지 않게
                self._seq += 1                   # 먹이기 전에 떠난 카드 묻기(refresh)도 같은 까닭으로 버린다
            kr = r.get("kr") or berry_kr(r.get("berry")) or "열매"
            self._over_pet(pid, SAY_FED % (kr, int(_num(r.get("gain"))), int(_num(r.get("happiness")))), PINK, 2200)
            # 하트는 글자 줄 양옆 바깥에서 오른다 (실제 앱 시험 11/27: 가운데 가까이 뜬 하트가 '+10' 을 '+1♥0' 처럼 덮었다)
            for k, (dx, ms) in enumerate(((-70, 250), (70, 600))):
                self._after("heart%d" % k, ms, lambda dx=dx: self._over_pet(pid, "♥", PINK, 1200, dx=dx, dy=-34))
            self._bag_changed()
            ev = r.get("evolve")
            if ev:
                info = dict(ev, pokemonId=pid)
                show = getattr(self.app, "show_evolutions", None)
                if show is not None:
                    show([info])             # 바탕화면에 있으면 그 자리에서 진화 연출 (ui_bag 의 도구 진화와 같다)
                else:
                    from .ui_bag import announce_evolve
                    announce_evolve(self.app.root, self.app, info)
            fn = getattr(self.app, "request_sync", None)
            if fn is not None:
                fn()                             # 친밀도 · 진화한 도트를 맞춘다
        run_async(self.app.root, lambda: api.feed(pid, avoid=avoid), done)

    def _over_pet(self, pid, text, color, ms, dx=0, dy=-6):
        ov = self.app.overlay
        pet = ov.pets.get(pid) if ov is not None else None
        if pet is None:
            return
        self._float(pet.x + pet.fw / 2.0 + dx, pet.y + dy, text, color, ms)

    # ---------------------------------------------------------------- 그리기
    def _water_anim(self, slots):
        self._anim = self.WATER_TICKS
        self._anim_slots = tuple(sorted(set(int(s) for s in slots)))
        self._paint()

    def _tick(self):
        p = self.planter
        if p is None:
            return
        try:
            p.frame_i += 1
            if p.frame_i % self.AREA_TICKS == 0:
                self._follow_area()
            if self._anim > 0:
                self._anim -= 1
            self._paint()
            self._layer()
            if PLAT.NEEDS_HIT_TRACKING:
                # 화단 창은 화분 위가 비어 있다. 그 자리가 바탕화면 클릭을 먹지 않게 커서를 좇는다 (맥)
                cx, cy = self.app.root.winfo_pointerxy()
                p.view.update_hit(cx - int(p.x), cy - int(p.y))
        except Exception as e:                              # noqa: BLE001
            if not self.errors:
                import traceback
                config.log("화단 그리기 오류: %s\n%s" % (e, traceback.format_exc()))
            self.errors += 1
        self._after("tick", self.TICK_MS, self._tick)

    def _look(self):
        """지금 모습 (화분 셋, 모드, 물 붓는 화분, 흐림) - garden_art.frames 의 열쇠."""
        friend = self.mode == "friend"
        pots = []
        for pot in self._pots():
            st = max(0, min(4, _stage(pot)))
            berry = pot.get("berry") if st > 0 else None
            if friend:
                pots.append((st, berry, None, 1 if pot.get("friendBonus") else 0))
            else:
                pots.append((st, berry, int(_num(pot.get("wetMask"))) & 7, 1 if pot.get("friendBonus") else 0))
        mode = "water" if self._anim > 0 else "idle"
        return (tuple(pots), mode, self._anim_slots if mode == "water" else (), friend)

    def _paint(self):
        p = self.planter
        if p is None:
            return
        try:
            look = self._look()
            i = (self.WATER_TICKS - self._anim) if look[1] == "water" else p.frame_i // self.SPARK_TICKS
            p.show(look, i)
        except Exception as e:                              # noqa: BLE001
            self.errors += 1
            config.log("화단 그림 오류: %s" % e)

    def _layer(self, force=False):
        """petBehind 를 따른다 - 켜 두면 다른 창 뒤로 (화단은 오래 두고 가끔 보는 것이다)."""
        p = self.planter
        if p is None:
            return
        ov = self.app.overlay
        front = not bool(getattr(ov, "behind", lambda: False)())
        if not force and front == p.front:
            return
        p.front = front
        try:
            if front:
                p.win._poket_behind = False
                PLAT.raise_above(p.win)
            else:
                lift = getattr(ov, "lift_pet", None)
                if lift is not None:
                    lift(p.win)
                else:
                    PLAT.send_back(p.win)
        except Exception:                                   # noqa: BLE001
            pass

    # ---------------------------------------------------------------- 글
    def _float(self, sx, sy, text, color, ms):
        fn = getattr(self.app, "float_at", None)
        if fn is None or not text:
            return
        try:
            fn(sx, sy, text, color, ms=ms)
        except Exception:                                   # noqa: BLE001
            pass

    def _say(self, slot, text, color, ms=1400, dy=-6):
        """화단 위에 글 (결과는 늘 여기 - notify 는 화면에 안 뜬다). slot 이 있으면 그 화분 위."""
        p = self.planter
        if p is None:
            return
        x = p.x + (ART.pot_x(slot) if slot is not None else p.fw / 2.0)
        self._float(x, p.y + dy, text, color, ms)

    def tip_text(self, slot):
        if self.mode == "friend":
            v = self.friend or {}
            return TIP_FRIEND if v.get("canWater") else FRIEND_WHY.get(v.get("why"), "")
        pot = self._pots()[slot]
        st = _stage(pot)
        if st <= 0:
            return TIP_EMPTY
        c = self.card or {}
        if pot.get("ripe") or st >= 4:
            cap = int(_num(c.get("cap")) or CAP)
            if int(_num(c.get("harvested"))) >= cap:
                return TIP_CAP % cap
            return TIP_RIPE
        left = _num(pot.get("left")) - (time.time() - self._got_at)
        t = "%s · %s · %s · 물 %s" % (berry_kr(pot.get("berry")), ART.STAGE_KR.get(st, ""), left_text(left),
                                     drops_text(pot.get("wetMask")))
        if pot.get("friendBonus"):
            t += " · 친구 물 +1"
        return t

    def on_hover(self, e):
        """마우스 올림 · 움직임 - 그 화분 글 (옆 화분으로 옮기면 바꾼다)."""
        if self.moving is not None or self.planter is None:
            return
        slot = self._slot_of(e)
        if slot == self._tip_slot and self.tip is not None:
            return
        self.show_tip(slot)

    def show_tip(self, slot):
        self.hide_tip()
        p = self.planter
        text = self.tip_text(slot) if p is not None else ""
        if not text or self.moving is not None:
            return
        try:
            w = tk.Toplevel(self.app.root)
            w.overrideredirect(True)
            w.configure(bg=U.TIP_BG)
            tk.Label(w, text=text, bg=U.TIP_BG, fg=U.GOOD, font=U.FONT_TIP, justify="center",
                     padx=7, pady=3).pack()
            w.update_idletasks()
            w.geometry("+%d+%d" % (p.x + ART.pot_x(slot) - w.winfo_width() // 2, p.y - w.winfo_height() - 4))
            PLAT.raise_above(w)
            self.tip = w
            self._tip_slot = slot
        except Exception:                                   # noqa: BLE001
            self.tip = None

    def hide_tip(self):
        w, self.tip = self.tip, None
        self._tip_slot = None
        if w is not None:
            try:
                w.destroy()
            except Exception:                               # noqa: BLE001
                pass

    def _first_hint(self):
        """화단이 처음 보이고 HINT_MS 뒤 - 첫 안내를 바란다 (띄울 때는 _try_hint 가 본다)."""
        self._hint(1)

    def _hint(self, stage):
        """처음 한 번 안내를 바란다 (1 첫 안내 · 2 첫 심기 뒤 · 3 첫 익음). 바로 띄우지 않고 _try_hint 가 때를 본다.
        앞 단계를 건너뛰었으면(첫 안내 전에 심었다) 그 단계는 다시 안 한다."""
        if int(self.app.settings.get("gardenHints") or 0) >= stage or self.mode != "mine":
            return
        self._hint_want = max(self._hint_want, stage)
        self._try_hint()

    def _hint_pick(self):
        """지금 띄울 단계 - 바란 것 중 아직 맞는 가장 높은 것. 기다리는 사이 다 거뒀으면 '다 익었어요' 는 빼고 그때
        맞는 것 (자라는 화분이 있으면 '물', 아니면 첫 안내)."""
        done = int(self.app.settings.get("gardenHints") or 0)
        pots = self._pots()
        for st in (3, 2, 1):
            if st <= done or st > self._hint_want:
                continue
            if st == 3 and not any(p.get("ripe") or _stage(p) >= 4 for p in pots):
                continue
            if st == 2 and not any(1 <= _stage(p) <= 3 for p in pots):
                continue
            return st
        return None

    def _hint_wait(self, pet):
        """안내를 지금 띄워도 되나 - 기다릴 ms (0 이면 지금). 안내 셋 모두 같은 문을 지난다 (검토 7 · 16):

        1. 연못이 떠 있는데 연못 첫 안내가 아직이면 그것이 먼저다
        2. 마지막 연못 안내(설정 pondHintAt - 낚시가 띄울 때 남긴다)에서 10분 (설계 '연못 안내가 끝난 뒤 10분')
        3. 같은 포켓몬 위에 다른 말풍선이 떠 있거나 8초 안에 떴으면 - 따로 뜨는 말풍선은 안 쌓여서 겹친다
        """
        s = self.app.settings
        fz = getattr(self.app, "fishing", None)
        if fz is not None and getattr(fz, "pond", None) is not None and int(s.get("pondHints") or 0) < 1:
            return self.HINT_RETRY_MS
        now = time.time()
        at = _num(s.get("pondHintAt"))
        gap = self.POND_GAP_MS / 1000.0
        if 0 < at <= now and now - at < gap:              # 시계를 되돌려 앞날이 된 때는 막지 않는다
            return int((gap - (now - at)) * 1000) + 1
        if any(not getattr(b, "dead", True) for b in getattr(pet, "_bubbles", ())):
            return int(max(0.5, self.BUBBLE_GAP_S) * 1000)  # 떠 있는 동안은 기다린다 (오래 떠 있는 알람 등)
        last = _num(getattr(pet, "_bubble_at", 0))
        if 0 < last <= now and now - last < self.BUBBLE_GAP_S:
            return int((self.BUBBLE_GAP_S - (now - last)) * 1000) + 1
        return 0

    def _try_hint(self):
        """바란 안내를 띄울 때가 됐으면 선두 포켓몬 말풍선 (낚시와 같은 방식), 아니면 다시 볼 때를 건다.
        단계는 **말풍선이 뜬 뒤에야** 설정 gardenHints 에 남긴다 - 미룬 안내를 잃지 않게."""
        self._cancel("hint")
        if self.mode != "mine":
            return
        stage = self._hint_pick()
        if stage is None:
            return
        ov = self.app.overlay
        pet = next(iter(ov.pets.values()), None) if ov is not None else None
        wait = self.HINT_RETRY_MS if pet is None else self._hint_wait(pet)
        if wait > 0:
            return self._after("hint", wait, self._try_hint)
        try:
            from .visit import Bubble
            Bubble(self.app.root, pet, HINTS[stage], ms=self.BUBBLE_MS)
        except Exception as e:                              # noqa: BLE001
            config.log("텃밭 안내 말풍선 실패: %s" % e)
            return
        s = self.app.settings
        s["gardenHints"] = stage
        try:
            config.save_settings(s)
        except Exception:                                   # noqa: BLE001
            pass

    # ---------------------------------------------------------------- 메뉴
    def on_menu(self, e):
        """오른쪽 클릭 (맥은 app._right_click_at 이 넘겨 준다). 빈 화분이면 가방을 물어 심을 열매 줄을 그때 만든다."""
        if self.moving is not None:
            return self._end_move()
        if self.planter is None or self.app.api is None:
            return
        self.hide_tip()
        slot = self._slot_of(e)
        x, y = self._at(e, slot)
        if self.mode == "friend":
            # 손님 펫 메뉴(visit.water_row)와 같은 글 - 같은 때 두 메뉴가 다른 말을 하지 않게 (검토 14)
            from .visit import WATER_ROW, WATER_WHY
            v = self.friend or {}
            row = ({"text": WATER_ROW, "command": lambda: self._friend_press(slot)} if v.get("canWater")
                   else {"text": WATER_WHY.get(v.get("why"), WATER_ROW + " (지금은 못 줌)"), "enabled": False})
            return self._show_menu([row], x, y)
        if _stage(self._pots()[slot]) > 0:
            return self._popup(x, y, slot, None)
        if self._menu_loading:
            return
        self._menu_loading = True

        def done(r, err):
            self._menu_loading = False
            if self.planter is None or self.mode != "mine":
                return
            self._popup(x, y, slot, [] if err is not None else FI.baits(r))
        run_async(self.app.root, self.app.api.bag, done)

    def _popup(self, x, y, slot, berries):
        """그 화분의 메뉴: 심을 열매 ▸ · 뽑기 · 텃밭 옮기기 · 텃밭 숨기기. berries None = 심은 화분 (심을 열매는 죽은 줄)."""
        can_pull = _stage(self._pots()[slot]) > 0 and self._req is None
        if not PLAT.NATIVE_MENU:
            # 맥 - 하위 메뉴가 없으니 '심을 열매' 머리줄 아래에 묶음 · 열매 줄을 들여 적는다
            if berries is None:
                rows = [{"text": MENU_PLANT, "enabled": False}]
            else:
                rows = [{"text": MENU_PLANT, "header": True}] + self.plant_rows(slot, berries, sub=True)
            rows += [None,
                     {"text": MENU_PULL, "command": lambda: self.pull(slot), "enabled": can_pull},
                     {"text": MENU_MOVE, "command": self.start_move},
                     None,
                     {"text": MENU_HIDE, "command": self.hide_garden}]
            U.PopupMenu(self.app.root, rows, x, y, width=220)
            return
        m = self._menu()
        if berries is None:
            m.add_command(label=MENU_PLANT, state="disabled")
        else:
            sub = self._menu(m)
            _fill(sub, self.plant_rows(slot, berries))
            m.add_cascade(label=MENU_PLANT, menu=sub)
        m.add_command(label=MENU_PULL, command=lambda: self.pull(slot), state="normal" if can_pull else "disabled")
        m.add_command(label=MENU_MOVE, command=self.start_move)
        m.add_separator()
        m.add_command(label=MENU_HIDE, command=self.hide_garden)
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def hide_garden(self):
        """텃밭 숨기기 - 설정 '텃밭 보이기' 를 끈다 (설정 · 트레이에서 다시 켠다). 화분은 그대로 자란다."""
        fn = getattr(self.app, "set_show_garden", None)
        if fn is not None:
            fn(False)
            return
        self.app.settings["showGarden"] = False
        config.save_settings(self.app.settings)
        self.set_visible(False)

    # ---------------------------------------------------------------- 옮기기
    def start_move(self):
        """옮기기: 영역을 덮고 놓을 곳을 한 번 누르게 한다 (연못과 같은 방식 - 맥에서 끌기는 놓는 순간을 잃는다)."""
        if self.planter is None or self.mode != "mine":
            return
        self._end_move()
        self.hide_tip()
        x1, y1, x2, y2 = self.app.overlay.area()
        try:
            cat = tk.Toplevel(self.app.root)
            cat.overrideredirect(True)
            cat.configure(bg="#23401c", cursor="crosshair")
            cat.geometry("%dx%d+%d+%d" % (max(1, x2 - x1), max(1, y2 - y1), x1, y1))
            try:
                cat.attributes("-alpha", 0.35)
            except Exception:                               # noqa: BLE001
                pass
            tk.Label(cat, text="텃밭을 놓을 곳을 누르세요\n(Esc · 오른쪽 클릭: 그만두기)", bg="#23401c", fg="#ffffff",
                     font=U.FONT_B, justify="center").place(relx=0.5, rely=0.5, anchor="center")
            cat.bind("<Button-1>", self._move_click)
            for w in cat.winfo_children():
                w.bind("<Button-1>", self._move_click)
            for seq in ("<Button-2>", "<Button-3>"):
                cat.bind(seq, lambda e: self._end_move())
            cat.bind("<Escape>", lambda e: self._end_move())
            PLAT.raise_above(cat)                # 진짜 위로 - 맥에서도 첫 누름을 덮개가 받는다
            try:
                cat.focus_force()
            except Exception:                               # noqa: BLE001
                pass
        except Exception as e:                              # noqa: BLE001
            config.log("텃밭 옮기기 덮개 실패: %s" % e)
            return
        self.moving = cat
        self._after("move", self.MOVE_LIMIT_MS, self._end_move)

    def _move_click(self, e):
        self.place_at(e.x_root, e.y_root)

    def _end_move(self):
        self._cancel("move")
        cat, self.moving = self.moving, None
        if cat is not None:
            try:
                cat.destroy()
            except Exception:                               # noqa: BLE001
                pass

    def place_at(self, x, y):
        """화단 가운데를 (x, y) 에 - 영역 안으로 가두고, 영역 안 비율로 기억한다."""
        self._end_move()
        p = self.planter
        if p is None:
            return
        ov = self.app.overlay
        x1, y1, x2, y2 = ov.area()
        m = ov.settings["areaMargin"]
        nx = max(x1 + m, min(int(x) - p.fw // 2, x2 - p.fw - m))
        ny = max(y1 + m, min(int(y) - p.fh // 2, y2 - p.fh - m))
        p.move(nx, ny)
        self.app.settings["gardenPos"] = self._ratio(nx, ny, p.fw, p.fh)
        config.save_settings(self.app.settings)
        # 비율을 넷째 자리로 줄여 기억해서 제자리가 1px 다를 수 있다 - 그것을 영역이 바뀐 것으로 읽지 않게
        self._home = self.home(p.fw, p.fh)


def _card_of(r):
    """심기 · 뽑기 답은 카드 그대로다. 혹시 {card: …} 로 싸여 오면 벗긴다."""
    if isinstance(r, dict) and "pots" not in r and isinstance(r.get("card"), dict):
        return r["card"]
    return r


def _fill(m, rows):
    """PopupMenu 꼴 줄을 tk.Menu (윈도우) 에 - 머리줄 · 못 누르는 줄은 죽은 줄, 들임은 앞 칸으로."""
    for r in rows:
        if r is None:
            m.add_separator()
            continue
        label = "   " * int(r.get("indent") or 0) + r.get("text", "")
        if r.get("header") or r.get("enabled") is False or not r.get("command"):
            m.add_command(label=label, state="disabled")
        else:
            m.add_command(label=label, command=r["command"])
