# -*- coding: utf-8 -*-
"""레이드 예고 — 바탕화면에 내려오는 빛기둥.

회차가 가까워지면 **포켓몬이 돌아다니는 영역의 윗변**에서 빛기둥이 내려온다
(화면 꼭대기가 아니다). 영역을 직접 그려 둔 사람은 그 사각형 위에서 나오고,
안 그린 사람은 기본 영역 위에서 나온다 - 어느 쪽이든 자기 포켓몬들 머리
위다.

누르면 레이드 창이 열린다. 기둥 밑에는 남은 시간을 세는 작은 판이 붙는다.

창 둘을 쓴다.
    기둥   투명색 + -alpha 로 비치게. 그림은 effects.pillar_frames.
    안내판 평범한 창. 글씨는 또렷해야 해서 알파를 안 건다.

**맥에서는 투명한 자리도 클릭을 먹는다** (platform_mac.SpriteView 의 설명).
풀숲과 같은 방법으로 커서를 좇아가며 비켜 준다.
"""
import time
import tkinter as tk

from . import effects
from . import platform_os as PLAT
from . import ui_common as U

# 기둥이 비치는 정도. 1.0 이면 바탕화면을 가리는 색판이 된다.
ALPHA = 0.72
STEP_MS = 110
# 회차 몇 초 전부터 보이나. 10분.
SHOW_BEFORE = 600

# 공개 전에는 색을 안 쓴다 (무엇이 나오는지 색으로도 흘리지 않는다).
HIDDEN_COLOR = (150, 156, 178)


def _rgb(hexcolor, fallback=(255, 192, 64)):
    try:
        s = hexcolor.lstrip("#")
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:                                       # noqa: BLE001
        return fallback


def pillar_color(card):
    """보스 타입 색. 아직 공개 전이면 회색빛."""
    if not card or not card.get("revealed"):
        return HIDDEN_COLOR
    # types 는 한글 이름이라 색표의 열쇠가 아니다. typeIds 를 쓴다.
    tid = (card.get("typeIds") or [None])[0]
    if tid and tid in U.TYPE_COLOR:
        return _rgb(U.TYPE_COLOR[tid])
    return _rgb(U.ACCENT)


def geometry(overlay):
    """(x, y, 폭, 높이). 영역 윗변 가운데에서 아래로 내려온다."""
    x1, y1, x2, y2 = overlay.area()
    aw, ah = max(1, x2 - x1), max(1, y2 - y1)
    w = max(110, min(int(aw * 0.45), U.h(240)))
    h = max(90, min(int(ah * 0.55), U.h(180)))
    x = x1 + (aw - w) // 2
    return x, y1, w, h


class RaidPillar(object):

    def __init__(self, app, card, on_click=None):
        self.app = app
        self.root = app.root
        self.on_click = on_click
        self.card = card or {}
        self.alive = True
        self.frame = 0
        self._job = None
        self._tick_job = None
        # 남은 시간은 **받은 순간부터 직접 센다.** 서버 시각을 매초 물을
        # 수는 없고, 서버가 준 leftSec 에 흐른 시간을 빼면 어긋나지 않는다.
        self.left = int(self.card.get("leftSec") or 0)
        self.at = time.time()

        ov = app.overlay
        key = ov.key
        hexkey = "#%02x%02x%02x" % key
        x, y, w, h = geometry(ov)
        self.x, self.y, self.w, self.h = x, y, w, h
        frames, fw, fh = effects.pillar_frames(w, h, 8, key, pillar_color(self.card))
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        bg = PLAT.transparent_window(self.win, hexkey)
        try:
            self.win.attributes("-alpha", ALPHA)
        except tk.TclError:
            pass
        self.view = PLAT.SpriteView(self.win, bg, fw, fh, cursor="hand2")
        self.photos = self.view.frames(frames, key)
        self.win.geometry("+%d+%d" % (x, y))
        self.view.show(self.photos[0])
        self.view.widget.bind("<Button-1>", self._clicked)
        PLAT.bind_right(self.view.widget, self._clicked)
        PLAT.raise_above(self.win)

        self._badge()
        self.animate()
        self.count()

    # ---------------- 안내판 ----------------
    def _badge(self):
        self.badge = tk.Toplevel(self.root)
        self.badge.overrideredirect(True)
        self.badge.configure(bg=U.ACCENT, highlightthickness=0)
        try:
            self.badge.attributes("-topmost", True)
        except tk.TclError:
            pass
        inner = tk.Frame(self.badge, bg=U.ACCENT_DARK, cursor="hand2")
        inner.pack(padx=2, pady=2)
        self.title = tk.Label(inner, text="", bg=U.ACCENT_DARK, fg=U.ACCENT_TEXT,
                              font=(U.FAMILY, U.pt(10), "bold"), padx=10, pady=(1))
        self.title.pack()
        self.sub = tk.Label(inner, text="", bg=U.ACCENT_DARK, fg=U.ACCENT,
                            font=(U.FAMILY, U.pt(9)), padx=10)
        self.sub.pack(pady=(0, 3))
        for w in (self.badge, inner, self.title, self.sub):
            w.bind("<Button-1>", self._clicked)
        self._place_badge()

    def _place_badge(self):
        try:
            self.badge.update_idletasks()
            bw = self.badge.winfo_reqwidth()
            bx = self.x + (self.w - bw) // 2
            by = self.y + self.h - U.h(6)
            self.badge.geometry("+%d+%d" % (max(0, bx), max(0, by)))
        except tk.TclError:
            pass

    # ---------------- 움직임 ----------------
    def animate(self):
        if not self.alive:
            return
        self.frame = (self.frame + 1) % len(self.photos)
        try:
            self.view.show(self.photos[self.frame])
        except tk.TclError:
            return
        if PLAT.NEEDS_HIT_TRACKING:
            # 기둥 창은 절반 넘게 비어 있다. 그 자리로 바탕화면 클릭이
            # 지나가도록 커서를 좇는다 (풀숲과 같다).
            try:
                cx, cy = self.root.winfo_pointerxy()
                self.view.update_hit(cx - int(self.x), cy - int(self.y))
            except Exception:                               # noqa: BLE001
                pass
        self._job = self.root.after(STEP_MS, self.animate)

    def count(self):
        """남은 시간을 1초마다 다시 적는다."""
        if not self.alive:
            return
        left = max(0, self.left - int(time.time() - self.at))
        card = self.card
        name = card.get("kr") if card.get("revealed") else None
        kind = {"mythical": "환상"}.get(card.get("kind"), "전설")
        head = ("%s 레이드 — %s" % (kind, name)) if name else "레이드가 다가온다"
        if left <= 0:
            tail = "지금 모이는 중! 눌러서 참가"
        elif left < 60:
            tail = "%d초 뒤 시작 · 눌러서 참가" % left
        else:
            tail = "%d분 %d초 뒤 시작" % (left // 60, left % 60)
        try:
            self.title.configure(text=head)
            self.sub.configure(text=tail)
        except tk.TclError:
            return
        self._place_badge()
        self._tick_job = self.root.after(1000, self.count)

    def update(self, card):
        """서버가 새 안내를 보내왔다. 남은 시간과 보스 이름을 맞춘다."""
        if not card or not self.alive:
            return
        was = self.card.get("revealed")
        self.card = card
        self.left = int(card.get("leftSec") or 0)
        self.at = time.time()
        if card.get("revealed") and not was:
            # 보스가 공개됐다 - 기둥 색이 타입 색으로 바뀐다
            self.repaint()

    def repaint(self):
        try:
            frames, fw, fh = effects.pillar_frames(
                self.w, self.h, 8, self.app.overlay.key, pillar_color(self.card))
            self.photos = self.view.frames(frames, self.app.overlay.key)
            self.view.show(self.photos[0])
        except Exception:                                   # noqa: BLE001
            pass

    def reposition(self):
        """활동 영역이 바뀌었다 (설정·직접 그리기). 다시 재서 옮긴다."""
        if not self.alive:
            return
        x, y, w, h = geometry(self.app.overlay)
        if (w, h) != (self.w, self.h):
            self.x, self.y, self.w, self.h = x, y, w, h
            self.repaint()
        else:
            self.x, self.y = x, y
        try:
            self.win.geometry("+%d+%d" % (x, y))
        except tk.TclError:
            pass
        self._place_badge()

    # ---------------- 끝 ----------------
    def _clicked(self, _e=None):
        if self.on_click:
            try:
                self.on_click()
            except Exception:                               # noqa: BLE001
                pass

    def destroy(self):
        self.alive = False
        for j in (self._job, self._tick_job):
            if j:
                try:
                    self.root.after_cancel(j)
                except Exception:                           # noqa: BLE001
                    pass
        self._job = self._tick_job = None
        for w in ("badge", "win"):
            win = getattr(self, w, None)
            if win is not None:
                try:
                    win.destroy()
                except Exception:                           # noqa: BLE001
                    pass
