# -*- coding: utf-8 -*-
"""낚시 (다음 시즌, 2026-11-26) — 바탕화면의 연못 · 찌 던지기 · 입질 · 챔질.

흐름 (design-notes/2026-11-26-fishing.md)
    1. 활동 영역 왼쪽 아래, 탐험 보따리 자리 바로 오른쪽에 작은 연못. 줄을 안 던졌으면 낚싯대가 둑에 눕는다
    2. 연못을 누르면 찌를 던진다 - 마지막에 쓴 미끼를 달고 (볼의 '마지막 볼' 처럼)
    3. 입질 시각은 서버만 안다. '입질 준비' (알림 소켓의 밀어 보내기 · 90초 동기화 카드의 ready) 를 받으면
       지금 보여 줄 수 있을 때만 /api/fish/bite 로 입질을 연다 - 콕콕(찌가 흔들림) 뒤 쭉(찌가 잠기고 '!')
    4. 쭉 동안 누르면 낚인다. 낚인 포켓몬은 풀숲 야생과 같은 야생(src 'fish')이라 WildController.show_hooked 가
       연못 옆에 띄우고, 그 뒤로는 풀숲 야생과 똑같다 (배틀 · 볼 · 60초 뒤 도망)

콕콕 · 쭉 · 완벽한 챔질 판정은 **서버가 요청이 닿은 시각으로** 한다. 앱은 카드대로 보여 주기만 한다.
누름은 **뗄 때가 아니라 누를 때** 받는다 - 맥은 앱이 비활성일 때 '뗐다' 를 잃는다 (app._unstick).
입질 시각을 앱에 미리 알려 주지 않는다 - 알면 '짧게 나올 때까지 던졌다 거두기' 를 할 수 있다 (설계 '피할 것').
"""
import time
import tkinter as tk

from common import held as HELD
from common.korean import natural

from . import config
from . import fishing_art as ART
from . import platform_os as PLAT
from . import ui_common as U
from .ui_common import run_async

# 앱 글자 (설계 그대로)
TIP_IDLE = "눌러서 찌 던지기 · 오른쪽 클릭: 미끼"
TIP_WAIT = "입질을 기다리는 중"
TIP_NOW = "지금 눌러!"
SAY_EARLY = "아직! 찌가 쏙 잠기면 누르세요"
SAY_SPOOKED = "너무 일찍 당겼다…"
SAY_MISSED = "놓쳤다…"
SAY_PERFECT = "완벽한 챔질!"
BADGE_BIG = "대물!"
BADGE_HUGE = "왕대물!"
HINT_FIRST = "연못을 눌러 찌를 던져 보세요"
HINT_BITE = "찌가 쏙 잠기면 그때 눌러요!"
MENU_BAIT = "미끼"
MENU_REEL = "줄 거두기"
MENU_MOVE = "낚시터 옮기기"
MENU_RECORDS = "낚시 기록"
MENU_HIDE = "낚시터 숨기기"
NO_BAIT = "미끼 없이"

GOLD = "#ffd447"
WARN = "#ffd447"
SAD = "#ff8a8a"
GOOD = "#7bffa0"
WHITE = "#ffffff"

BAIT_ROWS = 14               # 미끼 메뉴에 적는 열매 수 (많은 순)
BUNDLE_GAP = 12              # 탐험 보따리와 연못 사이


# ---------------------------------------------------------------- 글 · 셈
def weight_text(g):
    """잰 무게 글 - 10kg 아래는 소수 둘째 자리, 그 위는 첫째 자리 (관리 창 상세 한 줄과 같은 셈)."""
    kg = int(g or 0) / 1000.0
    return ("%.2fkg" if kg < 10 else "%.1fkg") % kg


def badge_of(mon):
    """'big' · 'huge' · None. 서버가 준 배지를 먼저 믿고, 없으면 배율로 (1.6배 · 1.3배)."""
    b = (mon or {}).get("fishBadge")
    if b in ("big", "huge"):
        return b
    try:
        r = float((mon or {}).get("fishRatio") or 0)
    except (TypeError, ValueError):
        return None
    return "huge" if r >= 1.6 else ("big" if r >= 1.3 else None)


def bait_kr(iid):
    return HELD.KR.get(iid or "", iid or "")


def baits(bag_resp):
    """가방(/api/bag)에서 미끼로 쓸 수 있는 것 [(id, 한글, 개수)], 많은 순.

    **지닌 열매만** - 노력치 내리는 열매(분류 'ev')는 지닌 도구 이름표(common.held.KR)에 없어서 저절로 빠진다.
    서버도 같은 규칙으로 거절한다 (400) - 여기서 거르는 것은 메뉴를 짧게 하려는 것이다.
    """
    bag = (bag_resp or {}).get("bag") or {}
    out = []
    for iid, n in bag.items():
        try:
            n = int(n or 0)
        except (TypeError, ValueError):
            continue
        if n > 0 and str(iid).endswith("BERRY") and iid in HELD.KR:
            out.append((iid, HELD.KR[iid], n))
    out.sort(key=lambda t: (-t[2], t[1]))
    return out


def default_home(ov, w, h):
    """연못의 기본 자리 (옮겨 두기 전) - 탐험 보따리 바로 오른쪽 · 바닥에 맞춰.

    텃밭(garden)이 이 자리를 기준으로 선다 - 연못을 옮기거나 숨겨도 텃밭 자리는 그대로여야 해서 지금 자리가 아니라
    기본 자리를 따로 알려 준다."""
    x1, y1, x2, y2 = ov.area()
    m = ov.settings["areaMargin"]
    lo_x, hi_x = x1 + m, max(x1 + m, x2 - w - m)
    hi_y = max(y1 + m, y2 - h - m)
    # 탐험 보따리 폭 - expedition_ui.Bundle 과 같은 셈 (보따리가 없어도 그 자리는 비워 둔다)
    bw = int(max(30, int(ov.settings["targetHeight"] * 0.9)) * 1.1)
    x = min(hi_x, x1 + m + 10 + bw + BUNDLE_GAP)
    return (int(max(lo_x, x)), int(hi_y))


def overlaps(a, b, pad=0):
    """두 상자 (x1, y1, x2, y2) 가 겹치나. 하나라도 None 이면 아니다."""
    if not a or not b:
        return False
    return (a[0] - pad < b[2] and b[0] - pad < a[2]
            and a[1] - pad < b[3] and b[1] - pad < a[3])


# ---------------------------------------------------------------- 연못 창
class Pond(object):
    """연못 창 하나 (풀숲 · 보따리와 같은 방식의 작은 창). 그림은 fishing_art 가 그린다."""

    def __init__(self, ctl, x, y):
        self.ctl = ctl
        ov = ctl.app.overlay
        self.key = ov.key
        self.fw, self.fh = ART.size()
        self.x, self.y = int(x), int(y)
        self.state = None
        self.frame_i = 0
        self.front = None               # 지금 '항상 위' 인가 (None = 아직 안 정함)
        self.photos = {}
        self.win = tk.Toplevel(ov.root)
        self.win.overrideredirect(True)
        # 자리를 먼저 - 만들자마자 엉뚱한 곳에 한 번 떴다 옮겨 가는 것이 보이지 않게 (overlay.Pet 과 같다)
        self.win.geometry("+%d+%d" % (self.x, self.y))
        bg = PLAT.transparent_window(self.win, "#%02x%02x%02x" % self.key)
        self.view = PLAT.SpriteView(self.win, bg, self.fw, self.fh, cursor="hand2")
        self.label = self.view.widget
        # 맥은 상태마다 그림을 따로 만들면 클릭 자리(알파 합)가 그때그때 달라진다 - 처음에 전부 만들어 둔다
        for s in ART.STATES:
            self.photos[s] = self.view.frames(list(ART.frames(s, self.key)), self.key)
        self.label.bind("<Button-1>", ctl.on_press)
        PLAT.bind_right(self.label, ctl.on_menu)
        self.label.bind("<Enter>", lambda e: ctl.show_tip())
        self.label.bind("<Leave>", lambda e: ctl.hide_tip())
        self.show("idle")

    def show(self, state, i=None):
        fr = self.photos.get(state) or self.photos["idle"]
        if i is None:
            i = self.frame_i
        self.state = state
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


# ---------------------------------------------------------------- 낚시 조종
class FishingController(object):
    """낚시 전체를 맡는다 (앱이 하나 들고 있다 - app.fishing).

    phase: off(카드 없음 · 열리기 전) · idle · cast · nibble(콕콕) · strike(쭉) · late(쭉이 끝났지만 서버 여유 안)
           · hooked(낚인 야생이 나와 있다)
    """

    TICK_MS = 140              # 연못 그림 · 클릭 통과 · 층 맞추기
    RETRY_MS = 3000            # 입질을 못 여는 동안 다시 볼 간격 (서버는 안 부른다)
    WAIT_WILD_MS = 30000       # 서버가 '화면에 야생이 있다' 며 미뤘으면 (앱이 모르는 야생일 수 있다 - 자주 두드리지 않게)
    MISS_CHECK_MS = 6500       # 쭉이 끝난 뒤 카드를 다시 볼 때 (서버 여유 5초 + 조금)
    LATE_MS = 5000             # 쭉이 끝나고도 서버가 챔질을 받는 여유 (server config.FISH_GRACE) - 이 동안 누름은 챔질
    AREA_TICKS = 7             # 연못 자리를 다시 볼 틱 수 (TICK_MS x 7 = 약 1초)
    STALE_S = 12.0             # 방금 무엇을 했으면 그보다 먼저 떠난 동기화 카드는 믿지 않는다
    TAP_REFRESH_S = 5.0        # 던져 둔 동안 연못을 누르면 카드를 다시 본다 (이 간격 안에는 한 번)
    HINT_MS = 1500             # 연못이 처음 보이고 안내 말풍선까지
    HINT_RETRY_MS = 5000       # 안내할 선두 포켓몬이 아직 없으면
    SPLASH_TICKS = 4           # 낚아 올린 물보라 장 수
    MOVE_LIMIT_MS = 30000      # 옮기기 덮개를 잊고 두면 저절로 걷는다
    BUBBLE_MS = 7000

    def __init__(self, app):
        self.app = app
        self.card = None
        self.open = False
        self.phase = "off"
        self.pond = None
        self.paused = False
        self.moving = None
        self.tip = None
        self.errors = 0
        self._jobs = {}
        self._req = None           # 서버에 보내 둔 동작 (cast · hook · bite · reel)
        self._loading = False      # 카드를 다시 묻는 중
        self._again = False        # 묻는 동안 또 물어 달라고 했다
        self._menu_loading = False
        self._want_bite = False
        self._bite_at = 0.0
        self._tap_at = 0.0
        self._acted = 0.0
        self._epoch = 0
        self._splash = 0
        self._reel_hidden = False  # 숨기며 줄을 거두기로 했다 (던지는 요청이 오가는 중이면 그 답 뒤에)
        self._home = None          # 연못을 마지막으로 놓은 제자리 (x, y) - 영역이 바뀌었나 견준다

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
        """/api/me 동기화의 낚시 카드. 방금 무엇을 했으면(던지기 · 챔질 …) 그 전에 떠난 카드일 수 있어 상태는 안 믿는다."""
        if self._req is not None or time.time() - self._acted < self.STALE_S:
            if not (isinstance(card, dict) and card.get("open")):
                self._apply(card)               # 닫힘(열리기 전 · 시즌이 바뀜)은 그대로 믿는다
            return
        self._apply(card)

    def on_push(self, ev):
        """알림 소켓 {"t": "fish", "s": "ready"} - 입질 시각이 지났다."""
        if (ev or {}).get("s") != "ready":
            return
        if self.phase == "cast":
            self.want_bite()
        elif self.phase == "off" or self.card is None:
            self.refresh()

    def pause(self):
        """풀숲이 멈출 때 같이 (친구 집 · 집중 · 올림픽 중계 · 투기장 · 공습 · 로그아웃). 연못을 걷고 입질을 미룬다."""
        self.paused = True
        self._cancel("bite", "miss", "nibble", "strike", "late", "splash", "hop")
        if self.phase in ("nibble", "strike"):
            # 입질 타이머를 걷었다 - 던져 둔 것으로 되돌려 두면, 다시 열 때 카드(bite)가 남은 초로 입질을 새로 건다
            self.phase = "cast"
        elif self.phase == "late":
            # 여유 타이머를 걷었다. 다시 열 때 카드가 아직 bite(여유 안)면 _begin_bite 가 late 로 되돌린다
            self.phase = "idle"
        self._end_move()
        self._sync_pond()

    def resume(self):
        """풀숲이 다시 돌 때. 카드를 다시 물어서 맞춘다 (그사이 입질 시각이 지났거나 낚인 포켓몬이 남아 있을 수 있다)."""
        self.paused = False
        self.refresh()

    def set_visible(self, on):
        """설정 '낚시터 보이기' 가 바뀌었다 (저장은 부르는 쪽이 했다).

        끌 때 줄이 던져져 있으면(cast) 거둔다 - 미끼는 서버가 돌려준다. 숨긴 채 두면 아무도 입질을 안 열어
        서버가 그 사이 풀숲을 미루고, 사용자는 안 보이는 줄이 물에 남은 줄 모른다.
        입질 중(콕콕 · 쭉)이면 그대로 둔다 - 35초 안에 서버 쪽에서 놓침으로 끝난다 (거두면 미끼도 안 돌아온다).
        """
        self._reel_hidden = not on
        if not on:
            self._end_move()
        self._sync_pond()
        self._paint()
        if not on:
            self._reel_if_hidden()

    def _reel_if_hidden(self):
        """숨기며 거두기로 한 줄을 거둔다. 요청이 오가는 중이면(던지는 중 …) 그 답이 _apply 로 온 뒤 다시 본다."""
        if not self._reel_hidden or self._req is not None:
            return
        self._reel_hidden = False
        if self.phase == "cast" and self.open and not config.show_pond(self.app.settings):
            self.reel(quiet=True)

    def clear(self):
        """로그아웃 · 세션 끊김 · 종료. 창 · 타이머를 전부 치우고 처음으로 (다음 카드가 오면 다시 뜬다)."""
        self._epoch += 1                 # 이미 보낸 요청의 답은 버린다
        for name in list(self._jobs):
            self._cancel(name)
        self._end_move()
        self.hide_tip()
        if self.pond is not None:
            self.pond.destroy()
            self.pond = None
        self.card = None
        self.open = False
        self.phase = "off"
        self.paused = False
        self._req = None
        self._loading = self._again = self._menu_loading = False
        self._want_bite = False
        self._acted = 0.0
        self._splash = 0
        self._reel_hidden = False
        self._home = None

    def rect(self):
        """연못 자리 (x1, y1, x2, y2) - 풀숲 · 알이 피한다. 안 보이면 None."""
        return self.pond.rect() if self.pond is not None else None

    def anchor(self):
        """낚인 야생이 내려앉을 발 자리 (x, y) - 연못 옆 (오른쪽, 자리가 모자라면 왼쪽). 연못이 없으면 None."""
        p = self.pond
        if p is None:
            return None
        x1, _y1, x2, _y2 = self.app.overlay.area()
        right = x2 - (p.x + p.fw)
        if right >= 70 or right >= p.x - x1:
            ax = p.x + p.fw + 30
        else:
            ax = p.x - 30
        return (ax, p.y + p.fh)

    def busy(self):
        """입질 중이거나 낚인 야생이 나와 있다 (공습 · 다른 연출이 바탕화면을 빼앗지 않게)."""
        return (self.phase in ("nibble", "strike", "late") or self._req == "hook"
                or (self.phase == "hooked" and self._fish_shown()))

    def reposition(self):
        """영역이 바뀌었다 - 기억해 둔 비율대로 다시 놓는다."""
        p = self.pond
        if p is None:
            return
        self._home = self.home(p.fw, p.fh)
        p.move(*self._home)
        self.hide_tip()

    def _follow_area(self):
        """영역이 app._area_changed 없이 바뀌었으면 따라간다 - 모니터를 뺌 · 해상도/배율 · 작업 표시줄을 옮기거나
        자동 숨김 (overlay.area() 가 작업 영역에서 셈한다). 틱에서 1초에 한 번 - area() 는 잠깐 기억해 둔 값이라 가볍다."""
        p = self.pond
        if p is None or self.moving is not None:
            return
        if self.home(p.fw, p.fh) != self._home:
            self.reposition()

    # ---------------------------------------------------------------- 자리
    def home(self, w, h):
        """연못 자리. 옮겨 둔 것(pondPos - 영역 안 비율)이 있으면 그것, 없으면 탐험 보따리 바로 오른쪽 · 바닥에 맞춰."""
        ov = self.app.overlay
        x1, y1, x2, y2 = ov.area()
        m = ov.settings["areaMargin"]
        lo_x, hi_x = x1 + m, max(x1 + m, x2 - w - m)
        lo_y, hi_y = y1 + m, max(y1 + m, y2 - h - m)
        pos = self.app.settings.get("pondPos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            try:
                fx = min(1.0, max(0.0, float(pos[0])))
                fy = min(1.0, max(0.0, float(pos[1])))
                return (int(round(lo_x + fx * (hi_x - lo_x))), int(round(lo_y + fy * (hi_y - lo_y))))
            except (TypeError, ValueError):
                pass
        return default_home(ov, w, h)

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

    def visible(self):
        return (self.open and not self.paused and self.app.overlay is not None
                and config.show_pond(self.app.settings) and not self._away())

    def _sync_pond(self):
        """보여야 하면 연못을 세우고, 아니면 걷는다."""
        if self.visible():
            if self.pond is None:
                x, y = self._home = self.home(*ART.size())
                try:
                    self.pond = Pond(self, x, y)
                except Exception as e:                      # noqa: BLE001
                    self.pond = None
                    self.errors += 1
                    config.log("연못을 못 띄웠습니다: %s" % e)
                    return
                self._paint()
                self._layer(force=True)
                self._after("tick", self.TICK_MS, self._tick)
                if int(self.app.settings.get("pondHints") or 0) < 1:
                    self._after("hint", self.HINT_MS, lambda: self._hint(1, HINT_FIRST))
                if self._want_bite:
                    self._after("bite", 500, self._try_bite)      # 숨긴 동안 입질 준비가 왔다
            return
        self._cancel("tick", "hint")
        self.hide_tip()
        self._end_move()
        if self.pond is not None:
            self.pond.destroy()
            self.pond = None

    def _freeze_setting(self):
        """'낚시터 보이기' 의 처음 값은 그때의 '풀숲 보이기' 를 따른다 - 풀숲을 끈 사람에게 갑자기 연못이 생기지 않게."""
        s = self.app.settings
        if s.get("showPond") is None:
            s["showPond"] = bool(s.get("showGrass", True))
            try:
                config.save_settings(s)
            except Exception:                               # noqa: BLE001
                pass

    # ---------------------------------------------------------------- 카드
    def refresh(self):
        """카드를 다시 묻는다 (GET /api/fish). 그사이 내가 무엇을 했으면 답을 버린다."""
        api = self.app.api
        if api is None or not hasattr(api, "fish"):
            return
        if self._loading:
            self._again = True
            return
        self._loading = True
        epoch = self._epoch

        def done(r, err):
            self._loading = False
            if epoch == self._epoch and self._req is None:
                if err is None:
                    self._apply(r)
                elif getattr(err, "status", 0) == 404:
                    self._apply(None)            # 열리기 전 · 낚시를 모르는 서버
            if self._again:
                self._again = False
                self.refresh()
        run_async(self.app.root, api.fish, done)

    def _apply(self, card):
        """카드대로 맞춘다 (계약: open · state · ready · nibbleLeft · strikeLeft · bait · baitLeft · wait · wild)."""
        self.card = card if isinstance(card, dict) else None
        if not self.card or not self.card.get("open"):
            self.open = False
            self._end_bite()
            self._want_bite = False
            self._cancel("bite")
            self.phase = "off"
            self._sync_pond()
            return
        self.open = True
        self._freeze_setting()
        self._sync_pond()
        st = self.card.get("state") or "idle"
        if st == "bite":
            if self.phase not in ("nibble", "strike"):
                self._begin_bite(self.card)
        else:
            self._end_bite()
            if st == "hooked":
                self.phase = "hooked"
                self._want_bite = False
                self._show_hooked(self.card)
            elif st == "cast":
                self.phase = "cast"
                if self.card.get("wait"):
                    # 서버가 '화면에 야생이 있다' 며 미뤘다. 앱이 모르는 야생일 수 있어 한참 뒤에 다시 본다
                    self._want_bite = True
                    self._after("bite", self.WAIT_WILD_MS, self._try_bite)
                elif self.card.get("ready"):
                    self.want_bite()
                else:
                    self._want_bite = False
            else:
                if self.phase == "hooked":
                    self._drop_wild()            # 서버에 낚인 야생이 없다 (잡힘 · 이김 · 도망 · 만료)
                self.phase = "idle"
                self._want_bite = False
                self._cancel("bite")
        self._paint()
        self._reel_if_hidden()

    # ---------------------------------------------------------------- 입질
    def want_bite(self):
        self._want_bite = True
        self._try_bite()

    def nudge(self):
        """화면의 야생이 사라졌다 (WildController.clear). 야생 때문에 미뤄 둔 입질을 곧 다시 본다.

        실제 앱 시험 (11/27): 풀숲이 사라진 뒤에도 서버의 wait:'wild' 로 잡아 둔 30초 재시도를 기다려 입질이 17초 늦게 열렸다.
        도망 요청이 서버에 닿을 틈(3초)을 두고 본다 - 그래도 서버가 아직 있다고 하면 그때는 30초 뒤.
        """
        if self._want_bite and self.phase == "cast":
            self._after("bite", 3000, self._try_bite)

    def blocked(self):
        """지금 입질을 열면 안 되는 까닭 (없으면 None) - 공습을 못 여는 까닭 + 화면의 야생 (설계 '안 보이는 입질')."""
        if self.paused or self.pond is None:
            return "hidden"
        app = self.app
        r = getattr(app, "airraid", None)
        if r is not None:
            why = r.blocked()
            if why:
                return why
            if r.busy():
                return "airraid"
        w = getattr(app, "wild", None)
        if w is not None and (w.grass is not None or w.pet is not None
                              or getattr(w, "revealing", False) or getattr(w, "throwing", False)):
            return "wild"
        try:
            from . import stealth
            if stealth.active():
                return "stealth"
        except Exception:                                   # noqa: BLE001
            pass
        return None

    def _try_bite(self):
        self._cancel("bite")
        if not self._want_bite or self.phase != "cast" or self.app.api is None:
            return
        # 막혔거나 다른 요청이 오가는 중이면 조금 뒤에 다시 본다 (서버는 안 부른다).
        # 같은 답이 거듭 와도 2초에 한 번보다 자주 묻지 않는다.
        why = self.blocked()
        if why == "hidden":
            return                               # 연못이 다시 뜨면 _sync_pond 가 다시 부른다
        if (why or self._req is not None or self._loading
                or time.time() - self._bite_at < 2.0):
            self._after("bite", self.RETRY_MS, self._try_bite)
            return
        self._bite_at = time.time()
        self._start("bite")
        epoch = self._epoch

        def done(r, err):
            if epoch != self._epoch:
                return
            self._finish()
            if err is not None:
                if getattr(err, "status", 0) == 409:
                    self.refresh()               # 상태가 어긋났다 (다른 PC 에서 거뒀다 …)
                else:
                    self._after("bite", self.RETRY_MS * 10, self._try_bite)
                return
            self._apply(r)
        run_async(self.app.root, self.app.api.fish_bite, done)

    def _begin_bite(self, card):
        nib = max(0.0, _num(card.get("nibbleLeft")))
        stk = max(0.0, _num(card.get("strikeLeft")))
        self._want_bite = False
        if nib <= 0 and stk <= 0:
            # 쭉은 지났지만 카드가 아직 bite 다 - 서버 여유(FISH_GRACE) 안이다 (다시 연 앱 · 멈췄다 다시 열기).
            # idle 로 두면 누름이 던지기가 되어 409 를 받는다 - late 로 두어 챔질로 보낸다 (서버가 낚임/놓침을 정한다)
            self._cancel("bite", "nibble", "strike")
            self._to_late()
            return
        self._cancel("bite", "nibble", "strike", "miss", "late")
        if nib > 0:
            self.phase = "nibble"
            self._after("nibble", nib * 1000, self._to_strike)
        else:
            self.phase = "strike"
        self._after("strike", max(nib, stk) * 1000, self._strike_over)
        self._layer()
        self._hint(2, HINT_BITE)

    def _to_strike(self):
        if self.phase == "nibble":
            self.phase = "strike"
            self._paint()

    def _strike_over(self):
        """쭉이 끝났다. 누르는 중이면 그 답을 기다린다.

        '놓쳤다…' 를 띄우되 서버는 여유 5초(FISH_GRACE)를 더 bite 로 읽는다 - 그 사이(late) 누름은 챔질로 보낸다.
        바로 idle 로 두면 그 누름이 던지기가 되어 서버가 409 로 거절한다 (아직 bite 라).
        """
        if self._req == "hook" or self.phase not in ("nibble", "strike"):
            return
        self._say(SAY_MISSED, SAD)
        self._to_late()
        self._paint()
        self._after("miss", self.MISS_CHECK_MS, self.refresh)

    def _to_late(self):
        """late 로 (이미 late 면 타이머를 다시 걸지 않는다 - 동기화 카드가 거듭 와도 여유가 늘지 않게)."""
        if self.phase != "late":
            self.phase = "late"
            self._after("late", self.LATE_MS, self._late_over)

    def _late_over(self):
        """서버 여유도 끝났다 - 이제 누르면 던진다."""
        if self.phase == "late":
            self.phase = "idle"
            self._paint()

    def _end_bite(self):
        self._cancel("nibble", "strike", "late")

    # ---------------------------------------------------------------- 누르기
    def on_press(self, e=None):
        """연못을 눌렀다 (<Button-1> - 뗌이 아니라 누름). 상태에 따라 던지기 · 챔질."""
        if self.moving is not None or self._req is not None:
            return
        self.hide_tip()
        ph = self.phase
        if ph == "idle":
            self.cast()
        elif ph in ("nibble", "strike", "late"):
            self.hook()                          # late: 서버 여유 안 - 던지지 말고 챔질 (서버가 낚임/놓침을 정한다)
        elif ph == "cast":
            self._say(TIP_WAIT, WHITE, ms=900)
            if time.time() - self._tap_at > self.TAP_REFRESH_S:
                self._tap_at = time.time()
                self.refresh()                   # 밀어 보낸 알림을 놓쳤을 수 있다

    def _bait(self):
        """이번에 달 미끼. 마지막에 쓴 것이 떨어졌으면(카드의 baitLeft 0) 없이."""
        want = self.app.settings.get("lastBait") or None
        c = self.card or {}
        if want and c.get("bait") == want and int(c.get("baitLeft") or 0) <= 0:
            return None
        return want

    def cast(self, bait="last"):
        api = self.app.api
        if api is None:
            return
        if bait == "last":
            bait = self._bait()
        self._start("cast")
        epoch = self._epoch

        def done(r, err):
            if epoch != self._epoch:
                return
            self._finish()
            if err is not None:
                if bait and getattr(err, "status", 0) == 400:
                    # 그 열매가 없다 (다른 PC 에서 썼다 · 팔았다) - 미끼 없이 다시 던진다
                    self.app.settings["lastBait"] = None
                    config.save_settings(self.app.settings)
                    self.app.notify("%s이(가) 없어 미끼 없이 던집니다." % bait_kr(bait))
                    return self.cast(bait=None)
                if getattr(err, "status", 0) == 409:
                    return self._recheck(err)
                self._fail(err)
                return
            self._say("퐁!", WHITE, ms=700)
            self._apply(r)
        run_async(self.app.root, lambda: api.fish_cast(bait), done)

    def _recheck(self, err):
        """던지기가 409 - 대개 상태가 어긋난 것이다 (다른 PC 에서 던졌다 · 서버는 아직 bite 여유 안).
        서버의 날 글('이미 찌를 던져 두었습니다') 대신 카드를 다시 물어 맞춘다. 다시 물어도 idle 이면 상태 탓이 아니다
        (상자가 가득) - 그때만 그 글을 띄운다."""
        api = self.app.api
        epoch = self._epoch

        def done(r, e):
            if epoch != self._epoch or self._req is not None:
                return                           # 그사이 다른 것을 눌렀다 - 그 답이 맞춘다
            if e is None:
                self._apply(r)
            if e is not None or self.phase == "idle":
                self._fail(err)
        run_async(self.app.root, api.fish, done)

    def hook(self):
        api = self.app.api
        if api is None:
            return
        self._start("hook")
        epoch = self._epoch

        def done(r, err):
            if epoch != self._epoch:
                return
            self._finish()
            if err is not None:
                if getattr(err, "status", 0) != 409:
                    self._fail(err)
                self.refresh()
                return
            r = r or {}
            res = r.get("result")
            if res == "hooked":
                return self._hooked(r)
            if res == "early":
                self._say(SAY_EARLY, WARN, ms=1600)
            elif res == "spooked":
                self._say(SAY_SPOOKED, SAD, ms=1600)
            elif res == "missed":
                self._say(SAY_MISSED, SAD, ms=1600)
            if isinstance(r.get("card"), dict):
                self._apply(r["card"])
            else:
                self.refresh()                   # 카드를 안 실어 왔다 - 닫힌 것으로 읽지 않고 다시 묻는다
        run_async(self.app.root, api.fish_hook, done)

    def _hooked(self, r):
        """낚았다 - 물보라, 완벽하면 그 글, 낚인 야생을 연못 옆에 (도착하면 머리 위에 무게)."""
        self._end_bite()
        self.phase = "hooked"
        self._splash = self.SPLASH_TICKS
        if r.get("perfect"):
            self._say(SAY_PERFECT, GOOD, ms=1500, dy=-22)
        mon = (r.get("wild") or {}).get("pokemon") or {}
        w = getattr(self.app, "wild", None)
        shown = False
        if w is not None and not self.paused:
            shown = w.show_hooked(r, self.anchor(), then=lambda pet: self._landed(pet, mon))
        if not shown:
            self._landed(None, mon)
        self._apply(r.get("card") or dict(self.card or {}, state="hooked"))

    def _landed(self, pet, mon):
        """낚인 포켓몬이 떴다 - 찌에서 튀어 올라 연못 옆에 내려앉고, 머리 위에 무게 (대물이면 금색)."""
        g = (mon or {}).get("fishG")
        text, color = None, WHITE
        if g:
            text = weight_text(g)
            b = badge_of(mon)
            if b:
                text, color = "%s  %s" % (BADGE_HUGE if b == "huge" else BADGE_BIG, text), GOLD
        if pet is None or self.pond is None:
            if text:
                a = self.anchor()
                if a is not None:
                    self._float(a[0], a[1] - 50, text, color, 2200)
            return
        tx, ty = pet.x, pet.y
        bx, by = ART.bob_point()
        sx = self.pond.x + bx - pet.fw / 2.0
        sy = self.pond.y + by - pet.fh
        self._hop(pet, (sx, sy), (tx, ty), 0, text, color)

    def _hop(self, pet, start, end, k, text, color, n=9):
        w = getattr(self.app, "wild", None)
        if w is None or w.pet is not pet:
            return
        t = k / float(n)
        try:
            pet.x = start[0] + (end[0] - start[0]) * t
            pet.y = start[1] + (end[1] - start[1]) * t - 34 * 4 * t * (1 - t)
            pet.place()
        except Exception:                                   # noqa: BLE001
            return
        if k < n:
            self._after("hop", 30, lambda: self._hop(pet, start, end, k + 1, text, color, n))
            return
        if text:
            # 야생 표식('잉어킹 Lv.12')이 도트 바로 위에 있다 - 그 위로 띄운다
            self._float(pet.x + pet.fw / 2.0, pet.y - 40, text, color, 2400)

    def reel(self, quiet=False):
        """줄 거두기 (입질 전이면 서버가 미끼를 돌려준다).

        quiet: 숨기며 거둘 때 (set_visible) - 연못이 없으니 실패해도 글을 띄우지 않고 카드만 다시 묻는다."""
        api = self.app.api
        if api is None or self._req is not None:
            return
        self._start("reel")
        epoch = self._epoch

        def done(r, err):
            if epoch != self._epoch:
                return
            self._finish()
            if err is not None:
                if not quiet:
                    self._fail(err)
                self.refresh()
                return
            self._end_bite()
            self._apply(r)
        run_async(self.app.root, api.fish_reel, done)

    def _start(self, kind):
        self._req = kind
        self._acted = time.time()
        self._epoch += 1

    def _finish(self):
        self._req = None
        self._acted = time.time()

    def _fail(self, err):
        msg = natural(getattr(err, "message", "") or str(err) or "낚시를 하지 못했습니다.")
        self.app.notify(msg)
        self._say(msg.rstrip("."), SAD, ms=1800)

    # ---------------------------------------------------------------- 낚인 야생
    def _fish_shown(self):
        w = getattr(self.app, "wild", None)
        return bool(w is not None and w.has_fish())

    def _show_hooked(self, card):
        """카드에 낚인 야생이 실려 왔다 (다시 켠 앱 · 다른 길로 놓친 것) - 연못 옆에 되살린다."""
        w = getattr(self.app, "wild", None)
        if w is None or self.paused or not (card or {}).get("wild"):
            return                               # 멈춘 동안(투기장 · 친구 집 …)은 띄우지 않는다 - 다시 열 때 카드로 되살린다
        try:
            w.show_hooked(card, self.anchor())
        except Exception as e:                              # noqa: BLE001
            self.errors += 1
            config.log("낚인 포켓몬을 못 띄웠습니다: %s" % e)

    def _drop_wild(self):
        """서버에는 이제 낚인 야생이 없다 - 화면에 남은 것을 치운다 (배틀 · 던지는 중이면 그쪽이 끝낸다)."""
        w = getattr(self.app, "wild", None)
        if w is None or not w.has_fish():
            return
        b = getattr(self.app, "battle", None)
        if (b is not None and not getattr(b, "closed", False)) or getattr(w, "throwing", False):
            return
        w.clear()

    # ---------------------------------------------------------------- 그리기
    def _tick(self):
        p = self.pond
        if p is None:
            return
        try:
            p.frame_i += 1
            if p.frame_i % self.AREA_TICKS == 0:
                self._follow_area()
            # 낚인 야생이 사라졌으면 (잡힘 · 도망 · 만료) 다시 던질 수 있다
            if self.phase == "hooked" and self._req is None and not self._fish_shown():
                self.phase = "idle"
            if self._splash > 0:
                self._splash -= 1
            self._paint()
            self._layer()
            if PLAT.NEEDS_HIT_TRACKING:
                # 연못 창은 둑 바깥이 비어 있다. 그 자리가 바탕화면 클릭을 먹지 않게 커서를 좇는다 (맥)
                cx, cy = self.app.root.winfo_pointerxy()
                p.view.update_hit(cx - int(p.x), cy - int(p.y))
        except Exception as e:                              # noqa: BLE001
            if not self.errors:
                import traceback
                config.log("연못 그리기 오류: %s\n%s" % (e, traceback.format_exc()))
            self.errors += 1
        self._after("tick", self.TICK_MS, self._tick)

    def _look(self):
        if self._splash > 0:
            return "splash"
        return {"cast": "cast", "nibble": "nibble", "strike": "strike"}.get(self.phase, "idle")

    def _paint(self):
        p = self.pond
        if p is None:
            return
        try:
            p.show(self._look())
        except Exception as e:                              # noqa: BLE001
            self.errors += 1
            config.log("연못 그림 오류: %s" % e)

    def _layer(self, force=False):
        """petBehind 면 기다리는 동안 다른 창 뒤로, 입질(콕콕 · 쭉) 동안만 앞으로 (설계)."""
        p = self.pond
        if p is None:
            return
        ov = self.app.overlay
        behind = bool(getattr(ov, "behind", lambda: False)())
        front = self.phase in ("nibble", "strike") or not behind
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

    def _say(self, text, color, ms=1400, dy=-6):
        """연못 위에 글 (결과는 늘 여기 - notify 는 화면에 안 뜬다)."""
        p = self.pond
        if p is None:
            return
        self._float(p.x + p.fw / 2.0, p.y + dy, text, color, ms)

    def tip_text(self):
        ph = self.phase
        c = self.card or {}
        if ph == "strike":
            return TIP_NOW
        if ph in ("cast", "nibble"):
            t = TIP_WAIT
            if c.get("bait"):
                # baitLeft 는 바늘에 단 것을 뺀 가방의 수다. 마지막 하나를 달았으면 '×0' 이 아니라 그렇다고 적는다
                n = int(c.get("baitLeft") or 0)
                t += ("\n미끼: %s ×%d" % (bait_kr(c["bait"]), n) if n > 0
                      else "\n미끼: %s (마지막 하나)" % bait_kr(c["bait"]))
            return t
        if ph in ("hooked", "late"):
            return ""                            # late: '던지기' 라고 하면 거짓말이다 (누르면 챔질)
        t = TIP_IDLE
        last = self.app.settings.get("lastBait")
        if last:
            t += "\n미끼: %s" % bait_kr(last)
        return t

    def show_tip(self):
        self.hide_tip()
        p = self.pond
        text = self.tip_text() if p is not None else ""
        if not text or self.moving is not None:
            return
        try:
            w = tk.Toplevel(self.app.root)
            w.overrideredirect(True)
            w.configure(bg=U.TIP_BG)
            tk.Label(w, text=text, bg=U.TIP_BG, fg=U.GOOD, font=U.FONT_TIP, justify="center",
                     padx=7, pady=3).pack()
            w.update_idletasks()
            w.geometry("+%d+%d" % (p.x + p.fw // 2 - w.winfo_width() // 2,
                                   p.y - w.winfo_height() - 4))
            PLAT.raise_above(w)
            self.tip = w
        except Exception:                                   # noqa: BLE001
            self.tip = None

    def hide_tip(self):
        w, self.tip = self.tip, None
        if w is not None:
            try:
                w.destroy()
            except Exception:                               # noqa: BLE001
                pass

    def _hint(self, stage, text):
        """처음 한 번 안내 - 선두 포켓몬 말풍선 (집중하기와 같은 방식). 단계는 설정 pondHints 에 남긴다."""
        s = self.app.settings
        if int(s.get("pondHints") or 0) >= stage or self.pond is None:
            return
        ov = self.app.overlay
        pet = next(iter(ov.pets.values()), None) if ov is not None else None
        if pet is None:
            if stage == 1:
                self._after("hint", self.HINT_RETRY_MS, lambda: self._hint(1, HINT_FIRST))
            return
        try:
            from .visit import Bubble
            Bubble(self.app.root, pet, text, ms=self.BUBBLE_MS)
        except Exception as e:                              # noqa: BLE001
            config.log("낚시 안내 말풍선 실패: %s" % e)
            return
        s["pondHintAt"] = time.time()            # 텃밭 안내는 이 뒤 10분을 기다린다 (garden._hint_wait)
        s["pondHints"] = stage
        try:
            config.save_settings(s)
        except Exception:                                   # noqa: BLE001
            pass

    # ---------------------------------------------------------------- 메뉴
    def on_menu(self, e):
        """오른쪽 클릭 (맥은 app._right_click_at 이 넘겨 준다). 미끼 목록은 가방을 물어 그때 만든다."""
        if self.moving is not None:
            return self._end_move()
        if self.pond is None or self._menu_loading or self.app.api is None:
            return
        self.hide_tip()
        x, y = e.x_root, e.y_root
        self._menu_loading = True

        def done(r, err):
            self._menu_loading = False
            if self.pond is None:
                return                          # 가방을 묻는 사이에 연못이 걷혔다 (숨기기 · 로그아웃)
            self._popup(x, y, [] if err is not None else baits(r))
        run_async(self.app.root, self.app.api.bag, done)

    def _popup(self, x, y, berries):
        cur = self._bait()
        can_reel = self.phase in ("cast", "nibble", "strike") and self._req is None
        if not PLAT.NATIVE_MENU:
            # 맥. tk.Menu 는 NSMenu 라 여는 순간 앱이 죽는다 (app.pet_menu 와 같다)
            rows = [{"text": MENU_BAIT, "header": True}]
            if not berries:
                rows.append({"text": "가진 지닌 열매가 없습니다", "enabled": False, "indent": 1})
            for iid, kr, n in berries[:BAIT_ROWS]:
                rows.append({"text": "%s ×%d" % (kr, n), "indent": 1, "checked": iid == cur,
                             "command": (lambda i=iid: self.set_bait(i))})
            rows.append({"text": NO_BAIT, "indent": 1, "checked": not cur,
                         "command": lambda: self.set_bait(None)})
            rows += [None,
                     {"text": MENU_REEL, "command": self.reel, "enabled": can_reel},
                     {"text": MENU_MOVE, "command": self.start_move},
                     {"text": MENU_RECORDS, "command": self.open_records},
                     None,
                     {"text": MENU_HIDE, "command": self.hide_pond}]
            U.PopupMenu(self.app.root, rows, x, y, width=220)
            return
        root = self.app.root
        kw = dict(tearoff=0, bg=U.BG2, fg=U.FG, activebackground=U.BG4, activeforeground=U.FG, bd=0, font=U.FONT_S)
        m = tk.Menu(root, **kw)
        sub = tk.Menu(m, **kw)
        var = tk.StringVar(master=m, value=cur or "")
        m._bait_var = var                       # 메뉴가 닫히기 전까지 붙잡아 둔다
        if not berries:
            sub.add_command(label="가진 지닌 열매가 없습니다", state="disabled")
        for iid, kr, n in berries[:BAIT_ROWS]:
            sub.add_radiobutton(label="%s ×%d" % (kr, n), variable=var, value=iid,
                                command=(lambda i=iid: self.set_bait(i)))
        sub.add_radiobutton(label=NO_BAIT, variable=var, value="", command=lambda: self.set_bait(None))
        m.add_cascade(label=MENU_BAIT, menu=sub)
        m.add_command(label=MENU_REEL, command=self.reel, state="normal" if can_reel else "disabled")
        m.add_command(label=MENU_MOVE, command=self.start_move)
        m.add_command(label=MENU_RECORDS, command=self.open_records)
        m.add_separator()
        m.add_command(label=MENU_HIDE, command=self.hide_pond)
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def set_bait(self, iid):
        """다음에 던질 때 달 미끼 (볼의 lastBall 처럼 이 PC 의 취향 - 서버에 두지 않는다)."""
        self.app.settings["lastBait"] = iid or None
        config.save_settings(self.app.settings)
        self._say(("미끼: %s" % bait_kr(iid)) if iid else NO_BAIT, WHITE, ms=1100)

    def open_records(self):
        """낚시 기록 창 (ui_fishing - 따로 만든다). 아직 없으면 아무것도 안 한다."""
        try:
            from . import ui_fishing
        except ImportError:
            return
        fn = getattr(ui_fishing, "open_records", None)
        if fn is not None:
            fn(self.app)

    def hide_pond(self):
        """낚시터 숨기기 - 설정 '낚시터 보이기' 를 끈다 (설정 · 트레이에서 다시 켠다)."""
        fn = getattr(self.app, "set_show_pond", None)
        if fn is not None:
            fn(False)
            return
        self.app.settings["showPond"] = False
        config.save_settings(self.app.settings)
        self.set_visible(False)

    # ---------------------------------------------------------------- 옮기기
    def start_move(self):
        """옮기기: 영역을 덮고 놓을 곳을 한 번 누르게 한다. 끌기는 맥에서 놓는 순간을 잃어 챔질과 헷갈린다 (설계)."""
        if self.pond is None:
            return
        self._end_move()
        self.hide_tip()
        x1, y1, x2, y2 = self.app.overlay.area()
        try:
            cat = tk.Toplevel(self.app.root)
            cat.overrideredirect(True)
            cat.configure(bg="#14324a", cursor="crosshair")
            cat.geometry("%dx%d+%d+%d" % (max(1, x2 - x1), max(1, y2 - y1), x1, y1))
            try:
                cat.attributes("-alpha", 0.35)
            except Exception:                               # noqa: BLE001
                pass
            tk.Label(cat, text="낚시터를 놓을 곳을 누르세요\n(Esc · 오른쪽 클릭: 그만두기)", bg="#14324a", fg="#ffffff",
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
            config.log("낚시터 옮기기 덮개 실패: %s" % e)
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
        """연못 가운데를 (x, y) 에 - 영역 안으로 가두고, 영역 안 비율로 기억한다."""
        self._end_move()
        p = self.pond
        if p is None:
            return
        ov = self.app.overlay
        x1, y1, x2, y2 = ov.area()
        m = ov.settings["areaMargin"]
        nx = max(x1 + m, min(int(x) - p.fw // 2, x2 - p.fw - m))
        ny = max(y1 + m, min(int(y) - p.fh // 2, y2 - p.fh - m))
        p.move(nx, ny)
        self.app.settings["pondPos"] = self._ratio(nx, ny, p.fw, p.fh)
        config.save_settings(self.app.settings)
        # 비율을 넷째 자리로 줄여 기억해서 제자리가 1px 다를 수 있다 - 그것을 영역이 바뀐 것으로 읽지 않게
        self._home = self.home(p.fw, p.fh)


def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0
