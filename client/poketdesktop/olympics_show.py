# -*- coding: utf-8 -*-
"""포스크탑 올림픽 — 바탕화면 경기 중계 (한 조).

    s = Show(app, heat, on_done=None, replay=False)    heat = 서버의 조 각본 (/api/olympics/live · heat)
    s.start()      s.stop()      s.alive

같은 조 8마리(모두 실제 다른 사람 포켓몬)가 내 바탕화면에서 뛴다. 기록은 서버가 이미 정했다 - 여기서는 그 기록대로
그리기만 한다. 달리기 곡선은 씨앗으로 common/olympics.race_curve 가 만든다 (같은 조를 보는 누구 화면에서도 같다).

## 중계 (11/07 다시 만듦 - 사용자 '관전하는 만큼 퀄리티', 시안 '16비트 올림픽 중계')

    출전식   한 마리씩 걸어 들어와 자기 자리(레인 · 벤치)에 선다. 아래 자막 '○레인  주인의 포켓몬', 전광판 '선수 소개 k/n'
    출발     달리기는 '제자리에 · 차려 · 탕!' (연기), 봅슬레이 · 시기형은 차례마다
    경기     100m · 마라톤 = 다 같이 / 봅슬레이 = 한 대씩 (구간 기록 · 선두와 차이) / 장대 · 양궁 · 원반 · 스키점프 = 세 번씩
    결과     결과판 (조 순위 · 기록, 1~3위 메달 빛깔)
    시상대   조 1~3위가 단에 올라 메달을 건다

## 화면

경기장은 olympics_art 가 그린 픽셀 그림 한 장 - 클릭이 지나가는 창 하나에 **한 번만** 깐다 (맥 Tk 는 창 그림을 바꿀 때마다
통째로 다시 칠한다). 자막 · 전광판 · 결과판 · 시상대 · 소품(스키 · 썰매 · 장대 · 활 · 화살 · 원반)은 저마다 작은 창이라
바뀌어도 그 창만 다시 칠한다. 틱마다 바꾸는 것은 선수 창 · 소품 창의 자리뿐이다. 경기 중 바탕화면 포켓몬 · 알은 잠깐 숨는다.
떠오르는 글(기록 · '탕!')은 투명 층(fx_layer)에 그린다.

## 응원

경기 중 내 포켓몬을 누르면 '♥ 힘내!' 가 뜬다. **기록에는 아무 영향이 없다** (기록은 서버가 이미 정했다).
"""
import math
import time
import tkinter as tk

from common import olympics as O
from common import olympics_rounds as OR

from . import config
from . import fx_layer
from . import olympics_art as A
from . import platform_os as PLAT
from . import ui_common as U
from .overlay import Pet
from .sprites import DOWN, LEFT, RIGHT, UP

TICK_MS = 33
WALK_IN_MS = 1100           # 출전식: 한 마리가 걸어 들어오는 시간
INTRO_HOLD_MS = 420         # 자리에 서서 자막을 읽는 틈
READY_MS = 2100             # 제자리에 · 차려 · 탕
RESULT_MS = 3000            # 결과판
PODIUM_MS = 3600            # 시상대
INTRO_MS = 2600             # (옛 이름 - 검사 · 컨트롤러가 셈에 쓴다) 출발 신호까지의 기본 틈
OUTRO_MS = RESULT_MS + PODIUM_MS
MARATHON_SHOW = 95.0        # 2:10:00 이 중계로 몇 초인가
MARATHON_MAX = 118.0        # 조의 가장 느린 선수도 이 안에 (프로그램 끝 END 전에 끝나게 - 독립 검토 #6)
BOB_SHOW = 0.13             # 봅슬레이: 기록 1초가 중계로 몇 초인가 (50초 -> 6.5초)
ATTEMPT_MIN, ATTEMPT_MAX = 1700, 4200
POLE_L = 46                 # 장대 길이 (논리 픽셀)
KEY = A.KEY
MINE = "#ffc043"
WHITE = "#f4f6fb"
HEAD_BG, HEAD_FG = "#12161f", "#c4ccda"     # 이름 띠 (유리판과 같은 어두운 빛)
GOOD = "#5fd97a"
BAD = "#ff6b6b"
TACTIC_KR = dict((k, v["kr"]) for k, v in O.TACTICS.items())


def _font(size=9, bold=True):
    return (U.FAMILY, U.pt(size), "bold" if bold else "normal")


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


# ---------------------------------------------------------------- 그림 창 (경기장 · 카드 · 소품)
class ArtWin(object):
    """PIL 그림 한 장을 띄우는 작은 창 (클릭이 지나간다). 자리 · 그림이 바뀐 때만 손댄다 (맥 CPU).

    처음 자리는 화면 안이어야 한다 - 화면 밖에 만들었다 바로 없애면 맥 Tk 의 update() 가 멈출 수 있다."""

    def __init__(self, root, img, at=(0, 0), show=True, alpha=1.0):
        self.root = root
        self.alpha = alpha
        self._pos = None
        self.win = None
        self.view = None
        self.shown = False
        self._make(img, at)
        if show:
            self.show()

    def _make(self, img, at):
        self.w, self.h = img.size
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        bg = PLAT.transparent_window(self.win, "#%02x%02x%02x" % KEY)
        if self.alpha < 1.0:                # 유리판: 창 전체 투명도로 바탕화면이 비친다 (맥 · 윈도우 같게)
            try:
                self.win.attributes("-alpha", self.alpha)
            except Exception:                               # noqa: BLE001
                pass
        self.view = PLAT.SpriteView(self.win, bg, self.w, self.h)
        self.photos = self.view.frames([A.keyed(img)], KEY)
        self.view.show(self.photos[0])
        self._pos = (int(at[0]), int(at[1]))
        self.win.geometry("+%d+%d" % self._pos)
        try:
            PLAT.make_click_through(self.win)
        except Exception:                                   # noqa: BLE001
            pass
        self.win.withdraw()
        self.shown = False

    def set(self, img):
        """그림을 바꾼다. 크기가 같으면 그 창에, 다르면 창을 새로 (자리 · 보임은 그대로).

        **크기가 바뀌는 일은 없게 쓴다** (전광판 · 자막은 처음에 크기를 정해 둔다). 맥에서 창을 지우자마자 같은
        자리에 새 창을 만들면 지운 창의 그림이 화면에 자국으로 남았다 (11/07 시연 캡처). 그래도 바뀌면 옛 창은
        먼저 숨기고 조금 뒤에 지운다."""
        if img.size == (self.w, self.h):
            self.photos = self.view.frames([A.keyed(img)], KEY)
            self.view.show(self.photos[0])
            return
        shown, pos, old = self.shown, self._pos, self.win
        try:
            old.withdraw()
        except Exception:                                   # noqa: BLE001
            pass

        def gone(w=old):
            try:
                w.destroy()
            except Exception:                               # noqa: BLE001
                pass
        self.root.after(400, gone)
        self.win = self.view = None
        self._make(img, pos)
        if shown:
            self.show()

    def put(self, x, y):
        """왼쪽 위를 (x, y) 에."""
        pos = (int(x), int(y))
        if pos != self._pos:
            self._pos = pos
            self.win.geometry("+%d+%d" % pos)
        if not self.shown:
            self.show()

    def center(self, cx, cy):
        self.put(cx - self.w / 2.0, cy - self.h / 2.0)

    def show(self):
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

    def _kill(self):
        try:
            if self.win is not None:
                self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        self.view = self.win = None
        self.shown = False

    def destroy(self):
        self._kill()


Prop = ArtWin               # (옛 이름 - 검사가 소품 창을 센다)


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
    """조 안 순위 {entryId: 순위}. 라운드 각본이면 서버 결과로 센 조 안 차례(place - 스키점프는 점수 · 장대는 실패 수까지),
    아니면 기록 차례 (같으면 서버의 전체 순위 차례)."""
    if ents and all(e.get("place") for e in ents):
        # 라운드 각본: 서버 결과로 센 진짜 조 순위 그대로 (화면에 고른 몇 명 안에서 1..n 으로 다시 세면 실제 5위가
        # 시상대에 서고 실제 4위가 '금메달!' 을 외쳤다 - 독립 검토 11/08)
        return dict((e["entryId"], e["place"]) for e in ents)
    else:
        order = sorted(ents, key=lambda e: (O.rank_key(event, e.get("record")), e.get("rank") or 9999))
    return dict((e["entryId"], i) for i, e in enumerate(order, 1))


def place_text(heat, place):
    """중계 · 결과 카드의 순위 말. 동메달전 승/패 · 조가 하나인데 몇 명만 보이면 'N위 / 전체 M명' · 결승 · 조."""
    if heat.get("roundKey") == "bronze":
        return "동메달 결정전 %s" % ("승" if place == 1 else "패")
    size = heat.get("heatSize") or 0
    if (heat.get("heats") or 1) == 1 and size > len(heat.get("entrants") or []):
        return "%d위 / %d명" % (place, size)
    if heat.get("medal"):
        return "결승 %d위" % place
    if (heat.get("heats") or 1) > 1:
        return "조 %d위" % place
    return "%d위" % place


def trial_place(heat, eid):
    """봅슬레이 주행: 이 썰매가 들어온 때의 합계 순위 - 그때까지 출발한 모든 썰매 가운데 (화면의 몇 대 안이 아니다)."""
    rows = heat.get("allTotals") or []
    me = next((r for r in rows if r[2] == eid), None)
    if me is None or me[1] is None:
        return None
    return 1 + sum(1 for o, t, i in rows if i != eid and o <= me[0] and t is not None and t < me[1])


def event_budget(event, heat=None):
    """그 라운드 중계에 쓸 수 있는 초 (그 라운드 칸 - 도트 받기 기다림 9초 - 여유 6초).
    라운드 각본은 칸(budget)을 싣고 온다. 없으면 그 종목 결승 칸."""
    slot = (heat or {}).get("budget") or OR.slot(event, "final")
    return float(slot) - 9.0 - 6.0


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
        self.arts = []              # 띄운 그림 창 전부 (끝날 때 치운다)
        self.props = self.arts
        self.layer = None
        self.bubble = None
        self.said = []              # 띄운 말 (검사 · 기록)
        self.moves = 0              # 선수 창을 옮긴 횟수 (검사가 맥 CPU 를 본다)
        self._job = None
        self._t0 = None
        self._last = None
        self.phase = "intro"
        self.steps = []
        self.result = None
        self.best = {}
        self.pts = {}               # 스키점프 라운드: 점수 (전광판이 점수로 줄 세운다)
        self.fouls = {}
        self.done_at = {}
        self.T = {}
        self.layer_items = {}
        self._ski_cache = {}
        self._sled_cache = {}

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
            self._sizes()
            self.venue_win = self._art(self.venue.img, (self.vx, self.vy), alpha=A.VENUE_ALPHA)   # 맨 아래
            self.layer = fx_layer.open_layer(self.root, (self.vx - 10, self.vy - 70, self.vx + self.venue.w + 10,
                                                         self.vy + self.venue.h + 10))
            self._head()
            self._make_athletes()
            self._board([self._title(), self.heat.get("note") or "선수 소개"])
            self.steps = self._program()
        except Exception as e:                              # noqa: BLE001
            # 여기서 터진 채로 두면 포켓몬 · 이름표가 숨은 채, 풀숲 · 집중 · 대전이 '중계 중' 으로 갇힌다 (독립 검토 #3)
            import traceback
            config.log("올림픽 중계 준비 실패: %s\n%s" % (e, traceback.format_exc()))
            self.aborted = True
            self._finish()
            return self
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
        for a in list(self.arts):
            a.destroy()
        del self.arts[:]
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
        self.S = A.scale_of(self.th)
        W = min(1500, max(480, (wx2 - wx1) - 80))         # 폭은 넉넉히 (사용자 '폭은 꽉 써도 괜찮아 높이만')
        self.venue = A.venue(self.ev, W, self.S)
        self.geo = self.venue.geo
        cx = (wx1 + wx2) / 2.0
        self.vx = int(cx - self.venue.w / 2.0)
        self.vy = int(max(wy1 + 90, wy2 - 14 - self.venue.h))
        self.x1, self.x2 = self.vx, self.vx + self.venue.w
        self.W = self.venue.w
        self.top, self.bottom = self.vy, self.vy + self.venue.h

    def _sizes(self):
        """전광판 · 자막 창 크기를 처음에 정한다 - 이 조에서 나올 가장 긴 글에 맞춰서 (창을 다시 만들지 않게)."""
        S = self.S
        names = [self._name(e) for e in self.ents] or ["?"]
        texts = [e.get("text") or "-" for e in self.ents] or ["-"]
        ln, lt = max(names, key=len), max(texts + ["125.30m", "2:59:59"], key=len)
        top3 = sorted(names, key=len)[-3:]
        cands = [self._title(), "선수 소개  8 / 8", "경기 시작", "시상식"]
        if self.ev == "sprint":
            cands += ["사진 판정…  " + lt]
        elif self.ev == "marathon":
            cands += ["%d위  %s  %s" % (8, ln, lt), "  ".join("%d %s" % (i, n) for i, n in enumerate(top3, 1))]
        elif self.ev == "bobsled":
            cands += ["%s  %s  지금 8위" % (ln, lt), "8 / 8  출발 준비"]
        else:
            cands += ["%d %s %s" % (3, ln, lt)]
        w = 110
        for c in cands:
            w = max(w, A.board([c]).width, A.board([" ", c]).width)
        self.board_w = w
        self.board_h = A.board([self._title()] + [ln] * 3, w).height
        subs = ["작전 승부수", "3번째 시기  최고 %s" % lt, "3번째 화살  합계 30점", "선두 기록 %s" % lt]
        cw = 0
        for e in self.ents:
            for sub in subs:
                cw = max(cw, A.lower_third(8, e.get("user") or "?", self._name(e), sub, S,
                                           mine=bool(e.get("mine"))).width)
        self.card_w = cw or None

    def _at(self, x, y):
        """경기장 좌표 -> 화면 좌표."""
        return self.vx + x, self.vy + y

    def _art(self, img, at, show=True, alpha=1.0):
        a = ArtWin(self.root, img, at, show, alpha)
        self.arts.append(a)
        return a

    def _title(self):
        short = O.EV[self.ev]["short"] if self.ev != "sprint" else "100m"
        rk = self.heat.get("roundKr")
        if rk:                                       # 라운드 각본: '100m 예선 3조' · '양궁 결승' (조가 하나면 조 번호 없이)
            many = (self.heat.get("heats") or 1) > 1
            return "%s %s%s" % (short, rk, " %d조" % (self.heat.get("heat") or 1) if many else "")
        return "%s  %d조" % (short, self.heat.get("heat") or 1)

    def _head(self):
        """경기장 위의 이름 띠: 대회 · 종목 · 조 · (다시 보기) · 닫기 ×."""
        try:
            w = tk.Toplevel(self.root)
            w.overrideredirect(True)
            w.configure(bg=HEAD_BG)
            try:
                w.attributes("-alpha", A.CARD_ALPHA)
            except Exception:                               # noqa: BLE001
                pass
            day = self.heat.get("dayNo")
            if self.heat.get("roundKr"):
                many = (self.heat.get("heats") or 1) > 1
                where = "%s%s" % (self.heat["roundKr"], " %d조" % (self.heat.get("heat") or 1) if many else "")
            else:
                where = "%d조" % (self.heat.get("heat") or 1)
            text = "포스크탑 올림픽%s · %s · %s%s" % (
                " %d일째" % day if day else "", O.EV[self.ev]["kr"], where, "  (다시 보기)" if self.replay else "")
            tk.Label(w, text=text, bg=HEAD_BG, fg=HEAD_FG, font=_font(9, False), padx=9, pady=2).pack(side="left")
            x = tk.Label(w, text=" × ", bg=HEAD_BG, fg=HEAD_FG, font=_font(10), cursor="hand2")
            x.pack(side="left")
            x.bind("<Button-1>", lambda _e: self.stop())
            w.update_idletasks()
            w.geometry("+%d+%d" % (self.x1, self.top - w.winfo_reqheight() - 6))
            PLAT.raise_above(w)
            self.head_win = w
        except Exception as e:                              # noqa: BLE001
            config.log("올림픽 이름 띠 실패: %s" % e)
            self.head_win = None

    def _board(self, lines, colors=None):
        """전광판 (경기장 위 오른쪽 유리 칩)."""
        img = A.board(lines, self.board_w, colors=colors)
        if img.size != (self.board_w, self.board_h) and img.width <= self.board_w and img.height <= self.board_h:
            box = A.Image.new("RGBA", (self.board_w, self.board_h), (0, 0, 0, 0))      # 줄이 적으면 위를 비운다
            box.alpha_composite(img, (0, self.board_h - img.height))                    # (아래 끝은 제자리)
            img = box
        x = self.x2 - img.width
        y = self.top - img.height - 6
        b = getattr(self, "board_win", None)
        if b is None:
            self.board_win = self._art(img, (x, y), alpha=A.CARD_ALPHA)
        else:
            b.set(img)
            b.put(x, y)

    def _card(self, num, e, sub, label="레인"):
        """아래 자막: 번호 블록 + '주인의 포켓몬' + 아래 줄."""
        img = A.lower_third(num, e.get("user") or "?", self._name(e), sub, self.S, mine=bool(e.get("mine")),
                            label=label, w=getattr(self, "card_w", None))
        corner = self.geo.get("card", "bl")     # 경기장마다 경기 자리와 안 겹치는 귀퉁이
        x = self.x1 + 8 if corner[1] == "l" else self.x2 - img.width - 8
        y = self.top + 8 if corner[0] == "t" else self.bottom - img.height - 8
        at = (x, y)
        c = getattr(self, "card_win", None)
        if c is None:
            self.card_win = self._art(img, at, alpha=A.CARD_ALPHA)
        else:
            c.set(img)
            c.put(*at)
            c.show()
        for p in self.pets.values():        # 자막 창이 새로 뜨면 선수 위로 올라온다 - 선수가 가려지지 않게
            if p.out:
                PLAT.raise_above(p.win)

    def _card_off(self):
        c = getattr(self, "card_win", None)
        if c is not None:
            c.hide()

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
            pet.out = False
            try:
                pet.win.withdraw()          # 출전식에서 차례로 나온다
            except Exception:                               # noqa: BLE001
                pass
            if e.get("mine"):
                pet.on_click = self._cheer
            self.pets[e["entryId"]] = pet

    # ---------------------------------------------------------------- 선수 창 도움
    def _foot(self, pet):
        """발 자리 = 몸 가로 기준점(ax) · 그림 맨 아래(fh)."""
        return pet.x + pet.ax, pet.y + pet.fh

    def _put(self, pet, fx, fy):
        x, y = fx - pet.ax, fy - pet.fh
        if (int(x), int(y)) != (int(pet.x), int(pet.y)):
            pet.x, pet.y = x, y
            pet.place()
            self.moves += 1

    def _appear(self, pet, fx, fy, face=None):
        """그 자리에 나타난다 (출전식 · 순간 이동)."""
        self._put(pet, fx, fy)
        if face is not None:
            self._face(pet, face)
        if not pet.out:
            pet.out = True
            try:
                PLAT.show_again(pet.win)
                PLAT.raise_above(pet.win)
            except Exception:                               # noqa: BLE001
                pass

    def _face(self, pet, face):
        if face in getattr(pet, "photos", {}) and pet.facing != face:
            pet.facing = face
            pet.redraw()
        elif pet.facing != face:
            pet.turn_to({RIGHT: 1, LEFT: -1}.get(face, 0), {DOWN: 1, UP: -1}.get(face, 0))

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
        """선다. 그림을 바꾸면 Pet.play 는 칸 한가운데를 붙든다 - 발이 땅에서 뜨므로 발 자리로 다시 놓는다."""
        fx, fy = self._foot(pet)
        pet.state = "idle"
        if not pet.once:
            pet.play(pet.rest_anim())
            self._put(pet, fx, fy)
        if face is not None:
            self._face(pet, face)

    def _hop(self, pet):
        if pet is not None and pet.anim_for("Hop") is not None:
            pet.play("Hop", once=True)

    def _hurt(self, pet):
        if pet is not None and pet.anim_for("Hurt") is not None:
            pet.play("Hurt", once=True)

    def _float(self, pet_or_xy, text, color=WHITE, ms=1400):
        if self.layer is None:
            return
        if isinstance(pet_or_xy, tuple):
            sx, sy = pet_or_xy
        else:
            fx, _fy = self._foot(pet_or_xy)
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

    def _text(self, sx, sy, text, color=WHITE, size=9, anchor="w", tag=None):
        """투명 층에 글 (그림자 하나). 경기 중에는 거의 안 쓴다 - 결승 기록 · 선두 표시만."""
        if self.layer is None:
            return []
        x, y = self.layer.to_local(sx, sy)
        cv = self.layer.cv
        f = _font(size)
        return [cv.create_text(x + 1, y + 1, text=text, fill="#101014", font=f, anchor=anchor, tags=tag),
                cv.create_text(x, y, text=text, fill=color, font=f, anchor=anchor, tags=tag)]

    def _line(self, a, b, color=WHITE, width=2, tag=None):
        if self.layer is None:
            return None
        x1, y1 = self.layer.to_local(*a)
        x2, y2 = self.layer.to_local(*b)
        return self.layer.cv.create_line(x1, y1, x2, y2, fill=color, width=width, tags=tag)

    def _drop(self, key):
        """투명 층에 그려 둔 그 열쇠의 것들을 지운다."""
        if self.layer is None:
            return
        for it in self.layer_items.pop(key, []):
            try:
                self.layer.cv.delete(it)
            except Exception:                               # noqa: BLE001
                pass

    # ---------------------------------------------------------------- 틱 · 단계 기계
    def _tick(self):
        self._job = None
        if not self.alive:
            return
        now = time.monotonic()
        dt = now - self._last
        self._last = now
        try:
            self._run_steps(dt * 1000.0)
        except Exception as e:                              # noqa: BLE001
            import traceback
            config.log("올림픽 중계 오류: %s\n%s" % (e, traceback.format_exc()))
            return self._finish()
        if self.alive:
            self._job = self.root.after(TICK_MS, self._tick)

    def _run_steps(self, ms):
        while self.steps and self.alive:
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
        if not self.steps and self.alive:
            self._finish()

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
                if face is not None:
                    self._face(pet, face)
                pet.state = "idle"
                self._put(pet, x, y)
            if p >= 1.0 and walk:
                self._stand(pet, face)
        st.update({"fn": fn, "start": start})
        return st

    def _timed(self, ms, fn, start=None):
        return {"ms": ms, "fn": fn, "start": start}

    # ---------------------------------------------------------------- 프로그램 (종목마다)
    def _program(self):
        ev = self.ev
        steps = self._intro()
        if self.heat.get("resultsOnly"):             # 새 장면이 아직 없는 꼴 (양궁 랭킹 · 1대1) - 출전식과 결과판
            steps += self._results()
            if self.heat.get("podium", self.heat.get("medal", True)):
                steps += self._podium()
            return steps
        if ev == "sprint":
            steps += self._sprint()
        elif ev == "marathon":
            steps += self._marathon()
        elif ev == "bobsled":
            steps += self._bobsled()
        else:
            steps += self._field()
        steps += self._results()
        # 시상식은 메달 라운드(결승)만 - 예선 · 준결승은 결과판까지, 양궁 동메달전은 결승 뒤 시상식에서
        if self.heat.get("podium", self.heat.get("medal", True)):
            steps += self._podium()
        return steps

    # ---- 출전식: 한 마리씩 걸어 들어와 자리에 선다
    def _slots(self):
        """{entryId: ((들어오는 곳), (설 곳), 바라볼 쪽)} - 화면 좌표."""
        g, ev, out = self.geo, self.ev, {}
        n = len(self.ents)
        if ev == "sprint":
            for e in self.ents:
                L = g["lanes"].get(int(e.get("lane") or 1)) or g["lanes"][1]
                out[e["entryId"]] = (self._at(L["enter"], L["y"]), self._at(L["start"], L["y"]), RIGHT)
        elif ev == "marathon":
            path = g["path"]
            for i, e in enumerate(self.ents):
                k = len(path) - 10 - (i // 2) * 14
                x, y = path[k % len(path)]
                y += (i % 2) * 5 * self.S
                out[e["entryId"]] = (self._at(x - 120 * self.S, y), self._at(x, y), RIGHT)
        else:
            x1, x2, y = self._lineup()
            step = (x2 - x1) / float(max(1, n))
            for i, e in enumerate(self.ents):
                x = x1 + step * (i + 0.5)
                out[e["entryId"]] = (self._at(x1 - 30 * self.S, y), self._at(x, y), DOWN)
        return out

    def _lineup(self):
        """시기형 · 봅슬레이 출전식에서 설 줄 (x1, x2, 발 y) - 경기장 그림이 정한 빈 곳 (자막 · 경기 자리와 안 겹친다)."""
        return self.geo["lineup"]

    def _hide(self, pet):
        """대기석으로 (창을 숨긴다 - 시기형은 차례인 선수만 보인다)."""
        if pet is not None and pet.out:
            pet.out = False
            try:
                pet.win.withdraw()
            except Exception:                               # noqa: BLE001
                pass

    def _to_bench(self):
        """출전식이 끝나면 시기형 · 봅슬레이 선수는 대기석으로 (차례가 오면 출발 자리에 나온다)."""
        self._card_off()
        if self.ev in O.RACES:
            return
        for p in self.pets.values():
            self._hide(p)
        self._board([self._title(), "경기 시작"])

    def _intro(self):
        self.slot = {}
        slots = self._slots()
        n = len(self.ents)
        steps = []
        for k, e in enumerate(self.ents, 1):
            eid = e["entryId"]
            enter, spot, face = slots[eid]
            self.slot[eid] = (spot, face)
            pet = self.pets.get(eid)
            num = int(e.get("lane") or k) if self.ev in O.RACES else k
            label = "레인" if self.ev in O.RACES else "순서"
            sub = "작전 %s" % TACTIC_KR.get(e.get("tactic"), "안정")

            def intro(e=e, k=k, pet=pet, enter=enter, num=num, label=label, sub=sub):
                self._card(num, e, sub, label)
                self._board([self._title(), "선수 소개  %d / %d" % (k, n)])
                if pet is not None:
                    self._appear(pet, enter[0], enter[1])
                if e.get("mine"):
                    self._say_mine("%s 선수 입장!" % self._name(e), 1800)
            steps.append(self._do(intro))
            if pet is not None:
                steps.append(self._move(pet, spot, WALK_IN_MS, face=face))
                if e.get("mine"):
                    steps.append(self._do(lambda pet=pet: self._hop(pet)))
            else:
                steps.append(self._wait(WALK_IN_MS))          # 도트가 없어도 소개 시간은 같게 (중계 길이가 안 바뀐다)
            steps.append(self._wait(INTRO_HOLD_MS))
        steps.append(self._wait(500))
        steps.append(self._do(self._to_bench))
        return steps

    def _home(self, e):
        """차례가 끝난 선수는 대기석으로."""
        self._hide(self.pets.get(e["entryId"]))

    # ================================================================ 100m
    def _race_setup(self):
        """T(중계 초) · 곡선 · 실수 때. 선수 창이 없어도 된다 (검사가 셈만 본다)."""
        ev = self.ev
        self.curve = {}
        self.slip_at = {}
        worst = max([e.get("record") or 0 for e in self.ents] or [0]) or O.EV[ev]["base"]
        raw = dict((e["entryId"], e.get("record") or worst * 1.08) for e in self.ents)
        scale = 1.0
        if ev == "marathon":
            scale = min(MARATHON_SHOW / O.EV["marathon"]["base"], MARATHON_MAX / max(raw.values()))
        elif ev == "bobsled":
            scale = BOB_SHOW
        for i, e in enumerate(self.ents):
            self.T[e["entryId"]] = raw[e["entryId"]] * scale
            slip = next((t.get("at") for t in e.get("tries") or [] if t.get("slip")), None)
            self.curve[e["entryId"]] = O.race_curve(e.get("seed") or i, ev, slip)
            self.slip_at[e["entryId"]] = slip

    def _ready(self, starter):
        """'제자리에 · 차려 · 탕!' - starter = 연기가 나는 자리 (화면)."""
        def bang():
            self._board([self._title(), "탕!"], {1: (255, 90, 80)})
            try:
                img = A.puff(self.S)
                p = self._art(img, (starter[0] - img.width // 2, starter[1] - img.height))
                self.root.after(700, p.hide)
            except Exception:                               # noqa: BLE001
                pass
            self._float(starter, "탕!", MINE, 900)
            self._say_mine("출발!", 1400)
        return [self._do(lambda: self._board([self._title(), "제자리에"])), self._wait(int(READY_MS * 0.45)),
                self._do(lambda: self._board([self._title(), "차려"])), self._wait(int(READY_MS * 0.55)),
                self._do(bang)]

    def _sprint(self):
        self._race_setup()
        g = self.geo
        lane1 = g["lanes"][1]
        starter = self._at(lane1["start"] - 10 * self.S, g["apron"])
        self.leader = None
        self.lead_said = 0.0
        self.slip_said = set()
        total = max(self.T.values() or [1.0]) + 1.4

        def tick(p):
            rt = p * total
            lead_id, lead_d = None, -1.0
            crossed = []
            for e in self.ents:
                eid = e["entryId"]
                T = self.T[eid]
                frac = min(1.0, rt / T) if T > 0 else 1.0
                d = O.at_curve(self.curve[eid], frac)
                if frac < 1.0 and d > lead_d:
                    lead_id, lead_d = eid, d
                if frac >= 1.0 and eid not in self.done_at:
                    crossed.append(e)
                pet = self.pets.get(eid)
                if pet is not None:
                    L = g["lanes"].get(int(e.get("lane") or 1)) or g["lanes"][1]
                    (sx, y), (fx, _y) = self._at(L["start"], L["y"]), self._at(L["finish"], L["y"])
                    if frac < 1.0:
                        self._walk(pet, sx + d * (fx - sx), y)
                    else:
                        ax, _ay = self._at(L["after"], L["y"])
                        ox, _oy = self._foot(pet)
                        if ox < ax - 1:
                            self._walk(pet, min(ax, ox + 4 * self.S), y)
                        else:
                            self._stand(pet, DOWN)
                    sa = self.slip_at.get(eid)
                    if sa is not None and eid not in self.slip_said and frac >= sa:
                        self.slip_said.add(eid)
                        self._hurt(pet)
                        if e.get("mine"):
                            self._say(pet, "앗, 넘어졌어요!", 1800)
            for e in sorted(crossed, key=lambda x: self.T[x["entryId"]]):       # 한 틱에 여럿이면 기록 차례로
                self.done_at[e["entryId"]] = self.T[e["entryId"]]
                self._crossed(e)
            if lead_id is not None and lead_id != self.leader and rt > 0.3 * min(self.T.values()):
                if rt - self.lead_said > 2.6:
                    self.lead_said = rt
                    le = next(x for x in self.ents if x["entryId"] == lead_id)
                    self._say(self.pets.get(lead_id), "%s 선두!" % self._name(le), 1800)
                self.leader = lead_id
            elif self.leader is None:
                self.leader = lead_id
        return self._ready(starter) + [self._timed(int(total * 1000), tick)]

    def _crossed(self, e):
        """결승선을 지났다: 레인 끝에 순위와 기록 (한 번만 그린다), 1위면 사진 판정."""
        k = len(self.done_at)
        pet = self.pets.get(e["entryId"])
        if self.ev == "marathon":
            if k == 1 and pet is not None:
                self._say(pet, "%s 1위로 들어왔어요!" % self._name(e), 2200)
            self._board([self._title(), "%d위  %s  %s" % (k, self._name(e), e.get("text") or "")])
            return
        L = self.geo["lanes"].get(int(e.get("lane") or 1)) or self.geo["lanes"][1]
        y = self.vy + L["y"] - 6 * self.S
        self.layer_items.setdefault("res", []).extend(       # 레인 오른쪽 끝에 붙여 쓴다 (경기장 밖으로 안 나가게)
            self._text(self.x2 - 4 * self.S, y, "%d위 %s" % (k, e.get("text")),
                       MINE if e.get("mine") else (GOOD if k == 1 else WHITE), 9, anchor="e"))
        if k == 1:
            self._board([self._title(), "사진 판정…  %s" % (e.get("text") or "")])
            if pet is not None:
                self._float(pet, "1위!", MINE)

    # ================================================================ 마라톤
    LAPS = 2

    def _marathon(self):
        self._race_setup()
        path = self.geo["path"]
        n = len(path)
        start = self._at(*self.geo["finish"])
        self.check_said = set()
        self.board_at = -9.0
        total = max(self.T.values() or [1.0]) + 2.0
        rest_y = self.geo["rest_y"]

        def tick(p):
            rt = p * total
            crossed = []
            for e in self.ents:
                eid = e["entryId"]
                T = self.T[eid]
                frac = min(1.0, rt / T) if T > 0 else 1.0
                d = O.at_curve(self.curve[eid], frac)
                if frac >= 1.0 and eid not in self.done_at:
                    crossed.append(e)
                pet = self.pets.get(eid)
                if pet is None:
                    continue
                if frac < 1.0:
                    i = int(d * self.LAPS * n) % n
                    x, y = path[i]
                    lane = (e.get("lane") or 0) % 3 * 3 * self.S
                    self._walk(pet, *self._at(x, y - lane + 4 * self.S))
                else:
                    k = sorted(self.done_at, key=lambda q: self.done_at[q]).index(eid) if eid in self.done_at else 0
                    tx, ty = self._at(self.geo["finish"][0] + (14 + k * 14) * self.S, rest_y)
                    ox, oy = self._foot(pet)
                    if math.hypot(tx - ox, ty - oy) > 2:
                        self._walk(pet, ox + (tx - ox) * 0.2, oy + (ty - oy) * 0.2)
                    else:
                        self._stand(pet, DOWN)
            for e in sorted(crossed, key=lambda x: self.T[x["entryId"]]):
                self.done_at[e["entryId"]] = self.T[e["entryId"]]
                self._crossed(e)
            self._marathon_board(rt)
        return self._ready((start[0], start[1] - 30 * self.S)) + [self._timed(int(total * 1000), tick)]

    def _marathon_board(self, rt):
        """전광판에 지금 1~3위 (2초마다), 4분의 1 · 반환 · 4분의 3 지점에서 내 순위."""
        if rt - self.board_at < 2.0:
            return
        self.board_at = rt
        med = sorted(self.T.values())[len(self.T) // 2]
        order = self._live_order(rt)
        for k, frac in ((1, 0.25), (2, 0.5), (3, 0.75)):
            if k not in self.check_said and rt >= frac * med:
                self.check_said.add(k)
                if self.mine and self.mine["entryId"] not in self.done_at:
                    pos = order.index(self.mine["entryId"]) + 1
                    self._say_mine("%s 지점 · 지금 %d위!" % (("4분의 1", "반환", "4분의 3")[k - 1], pos), 2200)
        if self.done_at:
            return
        names = []
        for i, eid in enumerate(order[:3], 1):
            e = next(x for x in self.ents if x["entryId"] == eid)
            names.append("%d %s" % (i, self._name(e)))
        self._board([self._title(), "  ".join(names)])

    def _live_order(self, rt):
        def dist(eid):
            T = self.T[eid]
            return O.at_curve(self.curve[eid], min(1.0, rt / T) if T else 1.0)
        return sorted((e["entryId"] for e in self.ents), key=lambda i: (-dist(i), self.T[i]))

    # ================================================================ 봅슬레이 (한 대씩)
    def _bobsled(self):
        self._race_setup()
        steps = []
        n = len(self.ents)
        self.splits = {}            # entryId -> [구간 초 ...]
        for k, e in enumerate(self.ents, 1):
            steps += self._bob_run(k, n, e)
        return steps

    def _sled_img(self, angle):
        """기울기 6도 칸마다 한 장 - 모두 같은 크기 네모에 가운데로 (창을 새로 안 만들고 그림만 바꾸게)."""
        a = int(round(math.degrees(angle) / 6.0)) * 6
        if a not in self._sled_cache:
            img, _seat = A.sled(self.S, math.radians(a))
            side = 46 * self.S
            box = A.Image.new("RGBA", (side, side), (0, 0, 0, 0))
            box.alpha_composite(img, ((side - img.width) // 2, (side - img.height) // 2))
            self._sled_cache[a] = (box, (side // 2, side // 2))
        return self._sled_cache[a]

    def _bob_run(self, k, n, e):
        eid = e["entryId"]
        pet = self.pets.get(eid)
        path = self.geo["path"]
        npts = len(path)
        T = self.T[eid]
        rec = e.get("record") or 0
        checks = self.geo["checks"]
        st = {"sled": None, "said": set()}

        def begin():
            self._card(k, e, self._bob_lead_text(), "순서")
            self._board([self._title(), "%d / %d  출발 준비" % (k, n)])
            if pet is not None:
                x, y = path[0]
                self._appear(pet, *self._at(x, y))
                self._stand(pet, RIGHT)
            if e.get("mine"):
                self._say_mine("내 차례! 썰매 출발!", 1500)

        def run(p):
            d = O.at_curve(self.curve[eid], p)
            i = min(npts - 1, int(d * (npts - 1)))
            x, y = path[i]
            x2, y2 = path[min(npts - 1, i + 6)]
            ang = math.atan2(y2 - y, x2 - x)
            sx, sy = self._at(x, y)
            img, seat = self._sled_img(ang)
            if st["sled"] is None:
                st["sled"] = self._art(img, (sx - seat[0], sy - seat[1]))
                st["ang"] = img
            elif st.get("ang") is not img:
                st["sled"].set(img)
                st["ang"] = img
            st["sled"].put(sx - seat[0], sy - seat[1] + 2 * self.S)
            if pet is not None:
                self._face(pet, RIGHT if x2 >= x else LEFT)
                pet.state = "idle"
                self._put(pet, sx, sy - 1 * self.S)
            for ci, u in enumerate(checks):
                if d >= u and ci not in st["said"]:
                    st["said"].add(ci)
                    self._split(e, ci, u, (sx, sy))
            sa = self.slip_at.get(eid)
            if sa is not None and "slip" not in st["said"] and p >= sa:
                st["said"].add("slip")
                self._float((sx, sy - 30 * self.S), "벽에 쿵!", BAD, 900)
                if e.get("mine"):
                    self._say(pet, "앗, 벽에 부딪혔어요!", 1500)

        def finish():
            old = [self.best[x] for x in self.best]
            self.best[eid] = rec
            self.done_at[eid] = T
            place = sorted(self.best.values()).index(rec) + 1
            if self.heat.get("allTotals"):              # 라운드 각본: 모든 썰매의 합계로 센 '지금 N위'
                place = trial_place(self.heat, eid) or place
            fx, fy = self._at(*path[-1])
            self._float((fx, fy - 34 * self.S), e.get("text") or "", GOOD if not old or rec < min(old) else WHITE, 1600)
            self._board([self._title(), "%s  %s  지금 %d위" % (self._name(e), e.get("text") or "", place)],
                        {1: A.TXT if place > 1 else (130, 230, 140)})
            if e.get("mine"):
                self._say_mine("%s · 지금 %d위!" % (e.get("text") or "", place), 1800)
            if st["sled"] is not None:
                st["sled"].hide()
        steps = [self._do(begin), self._wait(700), self._timed(int(T * 1000), run), self._do(finish), self._wait(900)]
        if pet is not None:
            steps.append(self._do(lambda: (self._home(e), self._card_off())))
        return steps

    def _bob_lead_text(self):
        if not self.best:
            return "첫 주행"
        b = min(self.best.values())
        return "선두 기록 %s" % O.text("bobsled", b)

    def _split(self, e, ci, u, at):
        """구간 기록: 지금까지 가장 빠른 주행과의 차이 (초록 = 빠름, 빨강 = 느림)."""
        eid = e["entryId"]
        t_here = self._time_at(eid, u) * (e.get("record") or 0)
        self.splits.setdefault(eid, []).append(t_here)
        if not self.best:
            self._float((at[0], at[1] - 28 * self.S), "%.2f" % t_here, WHITE, 1100)
            return
        lead = min(self.best, key=lambda q: self.best[q])
        ls = self.splits.get(lead) or []
        if ci >= len(ls):
            return
        diff = t_here - ls[ci]
        self._float((at[0], at[1] - 28 * self.S), "%+.2f" % diff, GOOD if diff < 0 else BAD, 1200)

    def _time_at(self, eid, u):
        """곡선에서 거리 몫 u 에 닿는 시간 몫."""
        pts = self.curve[eid]
        for (t0, d0), (t1, d1) in zip(pts, pts[1:]):
            if d1 >= u:
                if d1 <= d0:
                    return t1
                return t0 + (t1 - t0) * (u - d0) / (d1 - d0)
        return 1.0

    # ================================================================ 시기형 (장대 · 양궁 · 원반 · 스키점프)
    def _field(self):
        ev, n = self.ev, len(self.ents)
        # 사람마다 시도 수가 다를 수 있다 (원반 결승: 3번 뒤 상위 8명만 3번 더) - 그 사람 시도 목록만큼
        tries = max([len(e.get("tries") or []) for e in self.ents] or [O.EV[ev]["tries"]]) or 1
        total = sum(len(e.get("tries") or []) for e in self.ents) or n * tries
        intro = n * (WALK_IN_MS + INTRO_HOLD_MS) / 1000.0
        # 한 시기는 A 의 1.02 배쯤 걸린다 (동작 몫 + 기록 뒤 쉼) - 넉넉히 1.05 로 나눈다
        span = (event_budget(ev, self.heat) - intro - OUTRO_MS / 1000.0) * 1000.0 / max(1, total) / 1.05
        self.A = int(min(ATTEMPT_MAX, max(ATTEMPT_MIN, span)))
        self.arrows = {}
        self.flag_win = {}
        if self.heat.get("format") == "bar":         # 장대 라운드: 마지막 시도들만 보여 준다 - 그 전에 넘은 높이를 먼저 적는다
            for e in self.ents:
                if e.get("barBefore") is not None:
                    self.best[e["entryId"]] = e["barBefore"]
        steps = []
        for r in range(tries):
            if r == 3 and self.heat.get("after3"):      # 원반 결승: 3번 뒤 상위 8명만 3번 더 (실제 대회처럼)
                steps.append(self._do(lambda: self._board([self._title(), "3차까지 상위 8명이 3번 더 던져요"])))
                steps.append(self._wait(1200))
            for k, e in enumerate(self.ents, 1):
                if r < len(e.get("tries") or []):
                    steps += self._attempt(r, k, e)
        return steps

    def _attempt(self, r, k, e):
        """한 시기: 자막 · 내 차례 말 · 종목 동작 · 기록 · 벤치로."""
        eid = e["entryId"]
        tries = e.get("tries") or []
        t = tries[r] if r < len(tries) else {"v": None, "slip": True}
        pet = self.pets.get(eid)

        def begin():
            best = self.best.get(eid)
            sub = "%d번째 시기  최고 %s" % (r + 1, O.text(self.ev, best) if best is not None else "-")
            if t.get("bar"):
                sub = "바 %.2fm  기록 %s" % (t["bar"], O.text(self.ev, best) if best is not None else "-")
            if t.get("pts") is not None and t.get("total") is not None:      # 스키점프 결선: 1라운드 점수
                sub = "결선 점프  1라운드 %.1f점" % (t["total"] - t["pts"])
            if self.ev == "archery":
                got = sum(p or 0 for p, _x, _a in self.arrows.get(eid, []))
                sub = "첫 화살" if r == 0 else "%d번째 화살  합계 %d점" % (r + 1, got)
                if self.heat.get("match"):
                    sub = "슛오프!" if t.get("shoot") else "%d세트 %d번째 화살" % (
                        (self.heat.get("setStart") or {}).get("skip", 0) + r // 3 + 1, r % 3 + 1)
            self._card(k, e, sub, "순서")
            if e.get("mine"):
                self._say_mine("내 차례! (%s)" % (sub.split("  ")[0] if self.heat.get("match") or t.get("bar")
                                                  else "%d번째 시기" % (r + 1)), 1500)
        steps = [self._do(begin)]
        if pet is None:
            steps += [self._wait(int(self.A * 0.8)), self._do(lambda: self._record(e, t, None))]
            return steps
        steps += getattr(self, "_att_" + self.ev)(pet, e, t, self.A, r)
        steps.append(self._do(lambda: self._record(e, t, pet)))
        steps.append(self._wait(int(self.A * 0.14)))
        steps.append(self._do(lambda: self._home(e)))
        return steps

    def _record(self, e, t, pet):
        eid = e["entryId"]
        v = t.get("v")
        where = pet if pet is not None else (self.x2 - 80, self.top + 40)
        if v is None:
            self.fouls[eid] = self.fouls.get(eid, 0) + 1
            if self.ev != "archery":            # 양궁은 과녁 위에 'M' 이 이미 떴다
                self._float(where, "넘어짐!" if self.ev == "ski" else ("실패 ×" if t.get("bar") else "파울!"), BAD)
            if e.get("mine"):
                self._say_mine("아쉬워요… 다음 시기에!", 1500)
        if self.ev == "archery":
            if pet is None:                     # 도트가 없는 선수 - 과녁 연출 없이 셈만
                self.arrows.setdefault(eid, []).append((v, bool(t.get("x")), 0.0))
            got = [{"v": p, "x": x} for p, x, _a in self.arrows.get(eid, [])]
            if any(g["v"] is not None for g in got):
                self.best[eid] = O.archery_total(got)
            if self.heat.get("match"):
                return self._match_board()
            self._field_board()
            return
        if v is None:
            self._field_board()
            return
        old = self.best.get(eid)
        new = old is None or O.better(self.ev, v, old)
        text = O.text(self.ev, v)
        if t.get("pts") is not None:            # 스키점프 라운드: 비거리 + 점수 (자세 점수 포함)
            text = "%s · %.1f점" % (text, t["pts"])
            self.pts[eid] = t.get("total") if t.get("total") is not None else t["pts"]
        self._float(where, text, GOOD if new else WHITE)
        if new:
            self.best[eid] = v
            if self.ev == "ski":
                self._lead_line()
        self._field_board()

    def _field_board(self):
        """전광판: 지금 1~3위 (최고 기록 - 스키점프 라운드는 점수)."""
        if self.pts:
            order = sorted(self.pts, key=lambda q: -self.pts[q])[:3]
            fmt = lambda eid: "%.1f점" % self.pts[eid]                    # noqa: E731
        else:
            order = sorted(self.best, key=lambda q: O.rank_key(self.ev, self.best[q]))[:3]
            fmt = lambda eid: O.text(self.ev, self.best[eid])              # noqa: E731
        names = []
        for i, eid in enumerate(order, 1):
            e = next(x for x in self.ents if x["entryId"] == eid)
            names.append("%d %s %s" % (i, self._name(e), fmt(eid)))
        self._board([self._title()] + (names or ["경기 중"]))

    def _match_board(self):
        """양궁 1대1 전광판: 세트 점수 (보여 주기 전 세트 포함) · 이번 세트 합."""
        st = self.heat.get("setStart") or {}
        sp = list(st.get("sp") or [0, 0])
        a, b = (self.ents + [None, None])[:2]
        if a is None or b is None:
            return self._field_board()
        xa = [p or 0 for p, _x, _ang in self.arrows.get(a["entryId"], [])]
        xb = [p or 0 for p, _x, _ang in self.arrows.get(b["entryId"], [])]
        nset = min(len(xa), len(xb)) // 3
        for k in range(min(nset, 5)):
            sa, sb = sum(xa[3 * k:3 * k + 3]), sum(xb[3 * k:3 * k + 3])
            if sa > sb:
                sp[0] += 2
            elif sb > sa:
                sp[1] += 2
            else:
                sp[0] += 1
                sp[1] += 1
        cur = "이번 세트 %d : %d" % (sum(xa[3 * nset:3 * nset + 3]), sum(xb[3 * nset:3 * nset + 3]))
        self._board([self._title(), "%s %d : %d %s" % (self._name(a), sp[0], sp[1], self._name(b)), cur])

    # ---- 장대높이뛰기: 장대를 들고 달려 높이에 맞춘 가로대를 넘는다
    def _bar_y(self, m):
        g = self.geo
        u = max(0.0, min(1.0, (m - 4.0) / 2.6))
        return g["bar_low"] + (g["bar_top"] - g["bar_low"]) * u

    def _set_bar(self, m, knocked):
        self._drop("bar")
        g = self.geo
        y = self._bar_y(m)
        a = self._at(g["bar_x"] - 13 * self.S, y)
        b = self._at(g["bar_x"] + 13 * self.S, y + (14 * self.S if knocked else 0))
        items = [self._line(a, b, "#ffd34d" if not knocked else BAD, self.S + 1)]
        hx, hy, hw, hh = g["height_board"]
        items += self._text(*self._at(hx + hw / 2.0, hy + hh / 2.0), text="%.2fm" % m, color=MINE, size=8,
                            anchor="center")
        self.layer_items["bar"] = [i for i in items if i]

    def _pole_img(self, angle):
        """장대 그림 (5도 칸마다 한 장, 모두 같은 크기). 장대 끝(검은 쪽) = 꽂는 쪽."""
        a = int(round(math.degrees(angle) / 5.0)) * 5
        k = ("pole", a)
        if k not in self._ski_cache:
            self._ski_cache[k] = A.pole_stick(self.S, math.radians(a), POLE_L)
        return self._ski_cache[k]

    def _att_pole(self, pet, e, t, A_, r):
        """장대를 앞으로 낮게 들고 달린다 -> 끝을 박스에 꽂는다 -> 장대가 서며 몸이 들린다 -> 가로대를 넘어(또는 걸려) 매트로.

        장대 그림은 가운데 기준이다. 끝(꽂는 쪽)이 P 이고 기울기가 a 이면 손 = P - L(cos a, sin a), 가운데 = P - L/2(..)."""
        g = self.geo
        v = t.get("v")
        best = self.best.get(e["entryId"])
        bar_m = t.get("bar") or (v if v is not None else ((best or 4.6) + 0.15))     # 라운드 각본은 시도한 바 높이를 싣는다
        ground = g["ground"]
        L = POLE_L * self.S
        hand_dy = max(8 * self.S, pet.fh * 0.36)                     # 손 높이 (발에서)
        a0, a1 = math.asin(min(0.8, hand_dy / float(L))), 1.42       # 꽂는 순간: 장대 끝이 땅(박스)에 닿는 기울기
        P = self._at(g["box"], ground)                              # 꽂는 자리 (박스)
        run0 = self._at(g["run0"], ground)
        plant_x = P[0] - L * math.cos(a0) - 3 * self.S              # 달리기가 끝나는 발 자리 (그때 장대 끝이 박스에 닿는다)
        over = self._at(g["bar_x"] - 2 * self.S, self._bar_y(bar_m) - 4 * self.S)
        land = self._at((g["mat"][0] + g["mat"][1]) / 2.0, g["mat_top"] + 1)
        st = {"pole": None, "img": None}

        def pole_at(cx, cy, ang):
            img = self._pole_img(ang)
            if st["pole"] is None:
                st["pole"] = self._art(img, (cx - img.width / 2.0, cy - img.height / 2.0))
            elif st["img"] is not img:
                st["pole"].set(img)
            st["img"] = img
            st["pole"].center(cx, cy)

        def carry(p=0.0):
            """처음엔 끝을 들고 달리다가 박스에 다가가며 낮춘다."""
            ang = -0.32 + (a0 + 0.32) * (p ** 2)
            fx, fy = self._foot(pet)
            hx, hy = fx + 3 * self.S, fy - hand_dy
            pole_at(hx + math.cos(ang) * L / 2.0, hy + math.sin(ang) * L / 2.0, ang)

        def start():
            self._appear(pet, *run0)
            self._stand(pet, RIGHT)
            self._set_bar(bar_m, False)
            carry()

        def run(p):
            q = p ** 1.25                                               # 점점 빨라진다
            self._walk(pet, run0[0] + (plant_x - run0[0]) * q, run0[1])
            carry(p)

        def vault(p):
            ang = a0 + (a1 - a0) * (p ** 0.8)
            hx, hy = P[0] - math.cos(ang) * L, P[1] - math.sin(ang) * L
            pet.state = "idle"
            self._face(pet, RIGHT)
            self._put(pet, hx - 3 * self.S, hy + hand_dy)
            pole_at(P[0] - math.cos(ang) * L / 2.0, P[1] - math.sin(ang) * L / 2.0, ang)

        def release():
            if st["pole"] is not None:
                st["pole"].hide()
            if v is None:
                self._set_bar(bar_m, True)
                self._hurt(pet)
        steps = [self._do(start), self._wait(int(A_ * 0.08)),
                 self._timed(int(A_ * 0.30), run),
                 self._timed(int(A_ * 0.18), vault)]
        if v is not None:
            steps.append(self._move(pet, over, int(A_ * 0.12), arc=6 * self.S, walk=False, face=RIGHT))
            steps.append(self._do(release))
            steps.append(self._move(pet, land, int(A_ * 0.12), walk=False, face=RIGHT))
            steps.append(self._do(lambda: self._hop(pet)))
        else:
            steps.append(self._move(pet, (over[0] - 4 * self.S, over[1] + 8 * self.S), int(A_ * 0.10), arc=3 * self.S,
                                    walk=False, face=RIGHT))
            steps.append(self._do(release))
            steps.append(self._move(pet, land, int(A_ * 0.12), walk=False, face=RIGHT))
        steps.append(self._wait(int(A_ * 0.08)))
        steps.append(self._do(lambda: st["pole"] is not None and st["pole"].destroy()))
        return steps

    # ---- 양궁: 사선에서 활을 들고 쏜다 - 과녁 확대 화면에 맞은 자리
    def _att_archery(self, pet, e, t, A_, r):
        g = self.geo
        eid = e["entryId"]
        v = t.get("v")
        x = bool(t.get("x"))
        spot = self._at(g["shoot_x"] - 6 * self.S, g["ground"])
        tx, ty = self._at(*g["target"])
        ang = (r * 2.3 + (eid % 7)) % (2 * math.pi)
        rr = g["face_r"]
        hit = (tx, ty) if v is None else (tx + math.cos(ang) * (0.25 if x else (10 - v + 0.5)) * rr / 10.0,
                                          ty + math.sin(ang) * (0.25 if x else (10 - v + 0.5)) * rr / 10.0)
        if v is None:
            hit = (tx + rr * 1.8, ty - rr * 1.2)
        st = {}

        def draw():
            self._appear(pet, *spot)
            self._stand(pet, RIGHT)
            fx, fy = self._foot(pet)
            st["bow"] = self._art(A.bow(self.S), (fx + 6 * self.S, fy - pet.fh * 0.75))
            st["from"] = (fx + 12 * self.S, fy - pet.fh * 0.55)

        def fly(p):
            (ax, ay), (bx, by) = st["from"], hit
            px = ax + (bx - ax) * p
            py = ay + (by - ay) * p - 18 * self.S * 4 * p * (1 - p)
            if "arrow" not in st:
                st["arrow"] = self._art(A.arrow(self.S, math.atan2(by - ay, bx - ax)), (px, py))
            st["arrow"].center(px, py)

        def hit_it():
            self.arrows.setdefault(eid, []).append((v, x, ang))
            label = "X" if x else ("M" if v is None else str(v))
            self._float((tx, ty - rr - 6 * self.S), label, GOOD if (v or 0) >= 9 else (BAD if v is None else WHITE), 1100)
            self._target(eid)

        def clean():
            for k in ("bow", "arrow"):
                if st.get(k) is not None:
                    st[k].destroy()
        return [self._do(draw), self._wait(int(A_ * 0.22)), self._timed(int(A_ * 0.26), fly), self._do(hit_it),
                self._wait(int(A_ * 0.24)), self._do(clean)]

    def _target(self, eid):
        arrows = self.arrows.get(eid, [])
        if self.heat.get("match") and arrows:      # 1대1: 이번 세트 화살만 (세트마다 과녁을 비운다 - 실제 경기처럼)
            k = (len(arrows) - 1) // 3 * 3
            arrows = arrows[k:k + 3]
        img = A.target_face(arrows, self.S)
        zx, zy = self.geo["zoom"]                   # 과녁 왼쪽 위 (화살이 안 지나는 곳)
        at = (self.x1 + zx - img.width, self.top + zy)
        w = getattr(self, "target_win", None)
        if w is None:
            self.target_win = self._art(img, at, alpha=A.CARD_ALPHA)
        else:
            w.set(img)
            w.put(*at)

    # ---- 원반던지기: 원 안에서 돌다 던진다 - 깃발이 꽂힌다 (파울은 그물에)
    def _att_discus(self, pet, e, t, A_, r):
        g = self.geo
        v = t.get("v")
        cx, cy = self._at(*g["circle"])
        faces = [DOWN, RIGHT, UP, LEFT, DOWN, RIGHT]
        land = self._at(g["mx"](v) if v is not None else g["circle"][0] + 4 * self.S, g["ground"])
        st = {}

        def spin(p):
            self._face(pet, faces[min(len(faces) - 1, int(p * len(faces)))])

        def throw_start():
            fx, fy = self._foot(pet)
            st["a"] = (fx + 6 * self.S, fy - pet.fh * 0.5)

        def fly(p):
            (ax, ay), (bx, by) = st["a"], land
            x = ax + (bx - ax) * p
            y = ay + (by - ay) * p - ((34 if v is not None else 8) * self.S) * 4 * p * (1 - p)
            if "disc" not in st:
                st["disc"] = self._art(A.disc(self.S), (x, y))
            st["disc"].center(x, y)

        def landed():
            if st.get("disc") is not None:
                st["disc"].destroy()
            if v is not None:
                self._pin(e, land, v)
        return [self._do(lambda: (self._appear(pet, cx, cy), self._stand(pet, DOWN))),
                self._timed(int(A_ * 0.24), spin),
                self._timed(int(A_ * 0.34), fly, throw_start),
                self._do(landed), self._wait(int(A_ * 0.10))]

    def _pin(self, e, at, v):
        """그 선수의 깃발 - 최고 기록 자리에만 남긴다 (내 것은 금빛). 기록이 늘면 깃발을 옮긴다."""
        eid = e["entryId"]
        old = self.best.get(eid)
        if old is not None and not O.better(self.ev, v, old):
            return
        img = A.flag_pin(self.S, A.GOLD if e.get("mine") else (120, 180, 255))
        at = (at[0] - self.S, at[1] - img.height)
        w = self.flag_win.get(eid)
        if w is None:
            self.flag_win[eid] = self._art(img, at)
        else:
            w.put(*at)

    # ---- 스키점프: 스키를 신고 내려와 날고, 착지 - 선두 비거리 선
    def _ski_img(self, mode, angle):
        a = int(round(math.degrees(angle) / 5.0)) * 5
        k = (mode, a)
        if k not in self._ski_cache:
            self._ski_cache[k] = A.skis(mode, self.S, math.radians(a))
        return self._ski_cache[k]

    def _att_ski(self, pet, e, t, A_, r):
        g = self.geo
        v = t.get("v")
        ramp = g["ramp"]
        land_m = v if v is not None else 92.0
        lx, ly = g["hill"](land_m)
        hill_y = g["hill_y"]
        T = g["T"]
        stop_x = min(self.venue.w - 90, max(lx + 70, g["hill"](160)[0] + 40))   # 브레이킹 트랙에서 멈출 곳
        h0 = hill_y(T[0]) - T[1]                                              # 도약대 끝이 눈 위로 떠 있는 높이
        st = {"skis": None, "img": None}

        def put_skis(fx, fy, mode, ang):
            img, foot = self._ski_img(mode, ang)
            if st["skis"] is None:
                st["skis"] = self._art(img, (fx - foot[0], fy - foot[1]))
            elif st["img"] is not img:
                st["skis"].set(img)
            st["img"] = img
            st["skis"].put(fx - foot[0], fy - foot[1])

        def start():
            px, py = self._at(*g["plat"])
            self._appear(pet, px, py)
            self._stand(pet, RIGHT)
            (ax, ay), (bx, by) = ramp[0], ramp[min(len(ramp) - 1, 4)]
            put_skis(px, py, "flat", math.atan2(by - ay, bx - ax))          # 출발대에서도 비탈을 따라

        def inrun(p):
            i = min(len(ramp) - 1, int((p ** 1.6) * (len(ramp) - 1)))
            x, y = ramp[i]
            x2, y2 = ramp[min(len(ramp) - 1, i + 4)]
            fx, fy = self._at(x, y)
            pet.state = "idle"
            self._face(pet, RIGHT)
            self._put(pet, fx, fy)
            put_skis(fx, fy, "flat", math.atan2(y2 - y, x2 - x))

        def air(p):
            """비행: 언덕을 따라 낮게 (실제 점프처럼 눈 위 몇 m) - 도약대 끝에서 떠올랐다가 착지점에 닿는다."""
            x = T[0] + (lx - T[0]) * p
            lift = 9 * self.S if v is not None else 4 * self.S
            return x, hill_y(x) - ((1 - p) * h0 + lift * math.sin(math.pi * p))

        def flight(p):
            x, y = air(p)
            x2, y2 = air(min(1.0, p + 0.03))
            fx, fy = self._at(x, y)
            pet.state = "idle"
            self._put(pet, fx, fy)
            put_skis(fx, fy, "v", math.atan2(y2 - y, max(0.5, x2 - x)) - 0.12)   # 앞코를 조금 들고 V 자

        def outrun(p):
            q = 1 - (1 - p) ** 2                                              # 미끄러지다 선다
            x = lx + (stop_x - lx) * q
            y = hill_y(x)
            y2 = hill_y(x + 3)
            fx, fy = self._at(x, y)
            self._put(pet, fx, fy)
            put_skis(fx, fy, "flat", math.atan2(y2 - y, 3.0))

        def landed():
            if v is None:
                self._hurt(pet)
            else:
                self._hop(pet)

        def clean():
            if st["skis"] is not None:
                st["skis"].destroy()
        return [self._do(start), self._wait(int(A_ * 0.10)), self._timed(int(A_ * 0.26), inrun),
                self._timed(int(A_ * 0.26), flight), self._do(landed), self._timed(int(A_ * 0.14), outrun),
                self._do(clean)]

    def _lead_line(self):
        """선두 비거리 선 (언덕에 연두 사선 + 이름) - 선두가 바뀔 때만 다시 그린다."""
        if not self.best:
            return
        self._drop("lead")
        eid = max(self.best, key=lambda q: self.best[q])
        m = self.best[eid]
        hill = self.geo["hill"]
        x, y = hill(m)
        (xa, ya), (xb, yb) = hill(m - 1), hill(m + 1)
        nl = math.hypot(xb - xa, yb - ya) or 1.0
        nx, ny = -(yb - ya) / nl, (xb - xa) / nl                # 표면에 수직 (아래쪽)
        a = self._at(x - nx * 10, y - ny * 10)
        b = self._at(x + nx * 9, y + ny * 9)
        items = [self._line(a, b, "#82e28c", 2)]
        e = next(q for q in self.ents if q["entryId"] == eid)
        items += self._text(a[0] + 4, a[1] - 7, "선두 %s" % O.text("ski", m), "#a0eca0", 9)
        self.layer_items["lead"] = [i for i in items if i]
        if e.get("mine"):
            self._say_mine("선두예요!", 1400)

    # ================================================================ 결과 · 시상대
    def _results(self):
        def show():
            self._card_off()
            rows = []
            for e in sorted(self.ents, key=lambda q: self.ranks.get(q["entryId"], 99)):
                rec = e.get("text") or "-"
                if e.get("q"):                       # 다음 라운드 진출: Q = 조 순위, q = 기록 (서버가 연 뒤)
                    rec = "%s  %s" % (rec, e["q"])
                rows.append((self.ranks.get(e["entryId"]), self._name(e), rec, bool(e.get("mine")),
                             e.get("user") or ""))
            img = A.results_board("%s 결과" % self._title(), rows, self.S)
            at = (self.x1 + (self.W - img.width) // 2, self.top + (self.venue.h - img.height) // 2)
            self.result_win = self._art(img, at, alpha=A.CARD_ALPHA)
            self._board([self._title(), "결과"])
            if self.mine:
                r = self.ranks.get(self.mine["entryId"])
                if self.heat.get("roundKr"):
                    self._say_mine("%s · %s%s" % (self.mine.get("text"), place_text(self.heat, r), "!" if r == 1 else ""),
                                   RESULT_MS)
                else:
                    self._say_mine("%s · 조 %d위%s" % (self.mine.get("text"), r, "!" if r == 1 else ""), RESULT_MS)
        return [self._do(show), self._wait(RESULT_MS)]

    def _podium(self):
        top = [e for e in sorted(self.ents, key=lambda q: self.ranks.get(q["entryId"], 99))
               if self.ranks.get(e["entryId"], 99) <= 3]

        def show():
            rw = getattr(self, "result_win", None)
            if rw is not None:
                rw.hide()
            img, feet = A.podium(self.S)
            px = self.x1 + (self.W - img.width) // 2
            py = self.bottom - img.height - 6
            self.podium_win = self._art(img, (px, py), alpha=A.CARD_ALPHA)
            self._board([self._title(), "시상식"])
            for e in top:
                place = self.ranks[e["entryId"]]
                pet = self.pets.get(e["entryId"])
                if pet is None:
                    continue
                fx, fy = px + feet[place][0], py + feet[place][1]
                self._appear(pet, fx, fy)
                PLAT.raise_above(pet.win)
                self._stand(pet, DOWN)
                self._hop(pet)
                med = A.medal(place, 1)                      # 단 앞면, 번호 왼쪽 (몸에 걸면 도트마다 얼굴을 가린다)
                self._art(med, (fx - 16 - med.width // 2, fy + 7))
            if self.mine and self.ranks.get(self.mine["entryId"], 99) <= 3:
                place = self.ranks[self.mine["entryId"]]
                if self.heat.get("roundKr"):        # 라운드 각본의 메달 라운드 = 진짜 메달
                    self._say_mine("%s!" % ("금메달", "은메달", "동메달")[place - 1], PODIUM_MS)
                else:
                    self._say_mine("조 %d위로 시상대에!" % place, PODIUM_MS)
        return [self._do(show), self._wait(PODIUM_MS)]
