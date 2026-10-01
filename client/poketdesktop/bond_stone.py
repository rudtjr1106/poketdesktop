# -*- coding: utf-8 -*-
"""바탕화면의 '빛나는 돌' 과 메가스톤 알림 (시즌 3).

## 빛나는 돌

/api/me 의 bond.ready 에 든 포켓몬 - 데리고 다니고, 유대(친밀도)가 가득
찼고, 키스톤이 있고, 그 종의 스톤 중 아직 없는 것이 있는 개체 - 머리 위에
작은 표식이 반짝인다. 누르면 유대 미션을 시작하고 포켓몬 관리 창에서 그
포켓몬을 연다. 미션 셋과 진행은 거기(ui_bond)에 있다.

bond.claim - 미션을 다 채웠는데 X/Y 를 골라야 하는 개체 - 에는 '스톤
고르기' 표식이 같은 자리에 뜬다. 누르면 관리 창을 연다 (고르는 단추가 거기
있다).

표식은 야생 표식(wild_ui)처럼 도트 위, 이름표가 있으면 **그 위**에 둔다.
도트·이름표 창을 한 픽셀도 덮지 않는다 - 겹친 자리는 검게 나온다
(overlay.measure_nameplate). 배틀 중·숨김·진화 중에는 숨긴다.

## 스톤 알림

스톤이 하나뿐인 종은 미션을 채우는 순간(배틀·잡기 도중) 서버가 저절로
준다. bond.got 으로 오면 선물처럼 연출이 끝난 뒤 작은 창으로 알리고 seen 을
부른다. 운영체제 알림은 쓰지 않는다 - 게임 안의 일이고 이 창이 자국이다.
"""
import tkinter as tk

from common.korean import natural

from . import platform_os as PLAT
from . import ui_common as U
from .ui_common import run_async

FILL = "#8a5cf6"
FILL_LIT = "#a98bff"
PULSE_MS = 650
TEXT = {"ready": "✦ 빛나는 돌", "claim": "✦ 메가스톤 고르기"}


class StoneBadge(object):
    """포켓몬 한 마리 머리 위의 표식. Pet.place 가 움직일 때마다 옮긴다."""

    def __init__(self, pet, kind, on_click):
        self.pet = pet
        self.ov = pet.ov
        self.kind = kind
        self.on_click = on_click
        self.bw = self.h = 0
        self.lit = False
        self._job = None
        w = tk.Toplevel(self.ov.root)
        w.overrideredirect(True)
        w.configure(bg=FILL)
        self.label = tk.Label(w, text=TEXT.get(kind, TEXT["ready"]), bg=FILL, fg="#ffffff",
                              font=U.FONT_XS, padx=7, pady=1, cursor="hand2")
        self.label.pack()
        self.label.bind("<ButtonRelease-1>", self._click)
        PLAT.raise_above(w)
        self.win = w
        self.shown = True
        self.place()
        self._pulse()

    def _click(self, _e=None):
        if self.on_click:
            self.on_click(self.pet.id, self.kind)

    def _want_visible(self):
        ov, p = self.ov, self.pet
        if ov.hidden or getattr(ov, "_names_block", 0) > 0:
            return False                     # 배틀 중이거나 치워 둔 동안
        if getattr(p, "evolving", False) or getattr(p, "battling", False):
            return False
        try:
            return p.win.state() != "withdrawn"
        except Exception:                                   # noqa: BLE001
            return False

    def place(self):
        vis = self._want_visible()
        if vis != self.shown:
            try:
                PLAT.show_again(self.win) if vis else self.win.withdraw()
            except Exception:                               # noqa: BLE001
                pass
            self.shown = vis
        if not vis:
            return
        try:
            if self.h <= 4:
                self.win.update_idletasks()
                self.bw, self.h = self.win.winfo_width(), self.win.winfo_height()
            p = self.pet
            top = int(p.y)
            if p.name_win is not None:
                top -= getattr(p, "name_h", 25) + 2
            x = int(p.x) + p.fw // 2 - self.bw // 2
            y = top - self.h - 3
            x1, y1, x2, _y2 = self.ov.area()
            if y < y1:                       # 화면 위로 나가면 도트 아래로
                y = int(p.y) + p.fh + 3
            x = max(x1, min(x, x2 - self.bw))
            self.win.geometry("+%d+%d" % (x, y))
        except Exception:                                   # noqa: BLE001
            pass

    def _pulse(self):
        """반짝인다. 투명도는 맥에서 클릭 통과와 부딪히므로 색을 바꾼다."""
        try:
            self.lit = not self.lit
            c = FILL_LIT if self.lit else FILL
            self.win.configure(bg=c)
            self.label.configure(bg=c)
        except Exception:                                   # noqa: BLE001
            return
        self._job = self.ov.root.after(PULSE_MS, self._pulse)

    def destroy(self):
        if self._job:
            try:
                self.ov.root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
            self._job = None
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass


class BondStones(object):
    """바탕화면의 표식 전부를 /api/me 의 bond 에 맞춘다."""

    def __init__(self, app):
        self.app = app
        self.want = {}                       # pid -> "ready" / "claim"

    def sync(self, bond):
        want = {}
        for pid in (bond or {}).get("claim") or []:
            want[pid] = "claim"
        for pid in (bond or {}).get("ready") or []:
            want.setdefault(pid, "ready")
        self.want = want
        self.apply()

    def apply(self):
        """지금 바탕화면의 도트에 표식을 붙이거나 뗀다. 도트를 새로 만들었으면
        (크기 바꾸기) 표식도 다시 붙어야 해서 sync 와 따로 둔다."""
        ov = getattr(self.app, "overlay", None)
        if not ov:
            return
        for pid, pet in list(ov.pets.items()):
            kind = self.want.get(pid)
            b = getattr(pet, "stone_badge", None)
            if b is not None and b.kind != kind:
                b.destroy()
                pet.stone_badge = b = None
            if kind and b is None:
                try:
                    pet.stone_badge = StoneBadge(pet, kind, self.click)
                except Exception:                           # noqa: BLE001
                    pet.stone_badge = None

    def remove(self, pid):
        self.want.pop(pid, None)
        self.apply()

    # ---------------- 누르면 ----------------
    def click(self, pid, kind):
        app = self.app
        if getattr(app, "arena", None) or getattr(app, "battle", None) or not app.api:
            return
        pet = app.overlay.pets.get(pid) if app.overlay else None
        if pet is None:
            return
        if kind == "claim":
            return self._open(pet, "미션을 다 채웠습니다! 받을 메가스톤을 고르세요.")
        from .ui_box import confirm
        name = (pet.mon.get("info") or {}).get("name") or "포켓몬"
        PLAT.activate()
        if not confirm(app.root, "빛나는 돌",
                       natural("%s 와(과)의 유대가 가득 찼습니다!\n\n세 가지 미션을 마치면 "
                               "메가스톤을 받습니다. 시작할까요?" % name),
                       danger=False, ok_text="시작"):
            return

        def done(_r, err):
            if err:
                return app.notify(getattr(err, "message", str(err)))
            self.remove(pid)
            self._open(pet, "유대 미션을 시작했습니다!")
            app.request_sync()
        run_async(app.root, lambda: app.api.bond_start(pid), done)

    def _open(self, pet, msg):
        """관리 창에서 그 포켓몬을 연다 - 미션 칸이 거기 있다."""
        app = self.app
        app.pet_open(pet)
        w = getattr(app, "box_window", None)
        if w is not None:
            try:
                w.say(msg, U.GOOD)
            except Exception:                               # noqa: BLE001
                pass


def announce_got(parent, got):
    """저절로 받은 메가스톤을 알린다. 여럿이면 한 창에."""
    if not got:
        return
    from . import ui_box
    win, f = ui_box._shell(parent, "메가스톤", 440, U.h(250))
    tk.Label(f, text="메가스톤을 받았습니다!", bg=U.BG, fg=U.ACCENT_TEXT,
             font=(U.FAMILY_BLACK, U.pt(17))).pack(anchor="w")
    box = tk.Frame(f, bg="#161b28", highlightthickness=2, highlightbackground=U.LINE)
    box.pack(fill="x", pady=(12, 0))
    inner = tk.Frame(box, bg="#161b28")
    inner.pack(fill="x", padx=14, pady=10)
    for g in got:
        row = tk.Frame(inner, bg="#161b28")
        row.pack(fill="x", pady=2)
        tk.Label(row, text="✦", bg="#161b28", fg=FILL_LIT, font=U.FONT_B).pack(side="left", anchor="n")
        lb = tk.Label(row, text=natural("%s 와(과)의 유대 미션을 마쳐 %s 을(를) 받았습니다."
                                        % (g.get("name") or "포켓몬",
                                           g.get("stoneKr") or g.get("stone") or "메가스톤")),
                      bg="#161b28", fg=U.FG, font=U.FONT_S, anchor="w", justify="left",
                      wraplength=340)
        lb.pack(side="left", fill="x", expand=True, padx=(6, 0))
    note = tk.Label(f, text="가방에 넣어 두었습니다. 포켓몬 관리에서 지니게 하고, 배틀에서 "
                            "'메가진화' 를 켜면 한 판에 한 번 메가진화합니다.",
                    bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left",
                    wraplength=390)
    note.pack(fill="x", pady=(10, 0))
    row = tk.Frame(f, bg=U.BG)
    row.pack(fill="x", pady=(14, 0))
    U.PushButton(row, "확인", win.destroy, height=34, font=U.FONT_B).pack(side="right")
    # 줄바꿈 폭은 창 폭(440, 배율과 상관없이 그대로)에서 여백을 뺀 값이다 -
    # wrap_to_width 는 창이 뜬 뒤에야 폭을 알아서 아래의 높이 재기가 틀린다.
    # 글자를 줄이지 않고 창을 내용에 맞춘다 (업적·선물 창과 같다)
    try:
        win.update_idletasks()
        need = win.winfo_reqheight()
        if need > win.winfo_height():
            win.geometry("%dx%d" % (win.winfo_width() or 440, need))
    except Exception:                                      # noqa: BLE001
        pass
    return win
