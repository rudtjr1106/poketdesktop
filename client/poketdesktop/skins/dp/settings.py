# -*- coding: utf-8 -*-
"""DP 테마 - 설정.

DP 의 '설정' 화면처럼: 흰 판에 항목이 한 줄씩, 고른 줄은 빨간 둥근 테, 값은 오른쪽에서 ◀ ▶ 로 바꾼다.
고른 줄의 설명은 아래 글 상자에 뜬다 (원작도 아래 창에 설명이 뜬다).

    포켓몬 크기            ◀  48 px  ▶      (아래 막대를 눌러도 그 값으로)
    이름표 보이기          ◀   켜기   ▶
    야생 배틀에서 잡기     ◀ 아직 안 잡은 포켓몬만 ▶
    돌아다닐 영역          [화면에 그리기] [기본 자리로]
    …

v2 (2026-10-25): 판 · 글상자는 테 한 겹 (글상자 오른쪽 줄무늬를 뺐다), 줄 사이에 옅은 금, ◀ ▶ 는
글자 단추. 줄 높이를 줄여 기본 설정 창만큼 한 화면에 보인다.

값을 바꾸는 일은 기본 설정 창(ui_settings.SettingsWindow)의 것을 그대로 부른다 (_set_size · _toggle · _set_catch …).
"""
import tkinter as tk

from common.korean import natural

from ... import autostart, config, skins
from ... import ui_common as U
from ... import ui_settings as ST
from . import CUR, DIM, INK, INK2, LINE, LINE_D, SEP, WHITE, font, tone
from . import kit as K

PAGE = "#cfe0f4"                 # 바탕 (마이페이지와 같은 빛깔, 무늬 없음)
SEL_FILL = "#fff3ec"             # 고른 줄


class _Cfg(object):
    """configure(**kw) 를 받아 함수로 넘긴다 (기본 창의 코드가 Label 처럼 부르는 자리)."""

    def __init__(self, fn):
        self.fn = fn
        self.kw = {}

    def configure(self, **kw):
        self.kw.update(kw)
        self.fn(**kw)

    config = configure

    def cget(self, key):
        return self.kw.get(key, "")


def _is_act(key):
    """아래 설명 창의 단추 열쇠인가 ("act:글자"). 줄의 단추는 (줄 번호, 글자) 다."""
    return isinstance(key, str) and key.startswith("act:")


class SettingsWindow(ST.SettingsWindow):

    def _build(self, s, header):
        self.rows = []
        self.cur = 0
        self._job = None
        self._note_extra = {}
        self._msg = ("바꾸면 바로 적용됩니다.", None)
        self.win.configure(bg=PAGE, highlightthickness=0)
        # 아래 설명 창 (고른 줄의 설명 · 바꾼 결과) - 굴려도 늘 보이게 따로 둔다
        self.ncv = tk.Canvas(self.win, bg=PAGE, highlightthickness=0, bd=0, height=U.h(112))
        self.ncv.pack(side="bottom", fill="x")
        self.ncv.bind("<Configure>", lambda _e: self._soon())
        self.cv = tk.Canvas(self.win, bg=PAGE, highlightthickness=0, bd=0, yscrollincrement=1)
        self.sb = K.Scroll(self.win, self.cv, PAGE)
        self.sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.configure(yscrollcommand=self.sb.set)
        U.scrollable(self.cv, 3)
        self.cv.bind("<Configure>", lambda _e: self._soon())
        self._bar_color = None
        # 기본 창의 코드가 U.set_status(self.status, …) 로 적는 자리
        self.status = tk.Frame(self.win)
        self.status._bar = _Cfg(lambda **kw: setattr(self, "_bar_color", kw.get("bg")))
        self.status._label = _Cfg(lambda **kw: self._say(kw.get("text"), kw.get("fg") or self._bar_color))
        # 기본 창이 configure 로 칠하는 칸들
        self.area_note = _Cfg(lambda **kw: self._soon())
        self.zoom_btn = _Cfg(lambda **kw: self._soon())
        self.zoom_msg = _Cfg(lambda **kw: self._soon())
        self.boss_msg = _Cfg(lambda **kw: self._soon())
        self.boot_note = _Cfg(lambda **kw: self._soon())
        self.catch_pick_note = _Cfg(lambda **kw: self._soon())    # 고른 포켓몬 몇 종 (_paint_catch_pick)
        # 값 (기본 창의 이름 그대로 - 바꾸는 함수들이 이것을 읽는다)
        self.names = tk.BooleanVar(value=bool(s.get("showNames")))
        self.grass = tk.BooleanVar(value=bool(s.get("showGrass", True)))
        self.notif = tk.BooleanVar(value=bool(s.get("notifyImportant", True)))
        self.drag = tk.BooleanVar(value=bool(s.get("petDrag", False)))
        self.fr_note = tk.BooleanVar(value=bool(s.get("friendlyNotify", True)))
        self.fr_auto = tk.BooleanVar(value=bool(s.get("friendlyAuto", False)))
        self.catch = tk.StringVar(value=config.catch_mode(s))
        from ... import hotkey as HOTKEY
        self.boss = tk.StringVar(value=HOTKEY.clean(s.get("bossKey"))) if HOTKEY.supported() else None
        st, _msg = autostart.state()
        self.boot_var = tk.BooleanVar(value=st in ("on", "blocked"))
        self.skin_pick = s.get("skin") if skins.usable(s.get("skin")) else skins.DEFAULT
        self.skin_rows = {}
        self.text_pick = U.text_size_of(s)
        self.btns = {}
        self._rows(s)
        self._paint_area()
        self._paint_zoom()
        self._paint_autostart(*autostart.state())

    # ---------------- 항목 ----------------
    def _num(self, label, note, lo, hi, step, fmt, get, put, big=None):
        self.rows.append({"kind": "num", "label": label, "note": note, "lo": lo, "hi": hi, "step": step,
                          "big": big or step, "fmt": fmt, "get": get, "put": put})

    def _flag(self, label, note, var, key, how):
        self.rows.append({"kind": "choice", "label": label, "note": note,
                          "choices": [(True, "켜기"), (False, "끄기")],
                          "get": lambda: bool(var.get()),
                          "put": lambda v: (var.set(v), how(key, var))})

    def _rows(self, s):
        self._num("포켓몬 크기", "도트를 이 높이에 맞춰 통일합니다.", 24, 120, 4, "%.0f px",
                  lambda: self.app.settings["targetHeight"], lambda v: self._set_size(int(v)))
        self._num("포켓몬 투명도", "올릴수록 뒤가 비쳐 보입니다. 바탕화면을 걸어다니는 포켓몬과 거기서 싸우는 포켓몬에 "
                  "적용됩니다. 99% 면 거의 보이지 않습니다.", 0, 100 - config.PET_OPACITY_MIN, 1, "%.0f%%",
                  lambda: 100 - int(round(config.pet_alpha(self.app.settings) * 100)),
                  lambda v: self._set_alpha(int(round(v))), big=10)
        self._num("걷는 속도", "느리게 두면 더 느긋하게 돌아다닙니다.", 0.3, 3.0, 0.1, "x%.1f",
                  lambda: self.app.settings["walkSpeed"], lambda v: self._set("walkSpeed", round(v, 1)))
        self._num("부드러움", "높을수록 부드럽지만 그만큼 더 자주 그립니다.", 10, 60, 5, "%.0f fps",
                  lambda: self.app.settings["fps"], lambda v: self._set("fps", int(v)))
        self._num("서버와 맞추는 주기", "짧게 두면 다른 기기에서 바꾼 것이 빨리 반영됩니다. 짧을수록 서버를 자주 두드립니다.",
                  30, 300, 10, "%.0f초", lambda: self.app.settings["syncSeconds"],
                  lambda v: self._set("syncSeconds", int(v)))
        if len(skins.choices()) >= 2:
            self.rows.append({"kind": "choice", "label": "화면 테마",
                              "note": "창과 배틀 화면을 그 세대 게임처럼 그립니다. 바꾸면 프로그램을 다시 켜서 적용합니다.",
                              "choices": [(sk.key, sk.name) for sk in skins.choices()],
                              "get": lambda: self.skin_pick, "put": self._pick_skin,
                              "action": ("다시 켜서 적용", self._restart_for_skin,
                                         lambda: self.skin_pick != skins.active())})
        self.rows.append({"kind": "choice", "label": "글자 크기",
                          "note": "창과 메뉴의 글자를 키웁니다. 글자가 든 칸도 같이 커집니다. 바꾸면 프로그램을 다시 켜서 "
                                  "적용합니다.",
                          "choices": [(i, name) for i, (name, _k) in enumerate(U.TEXT_SIZES)],
                          "get": lambda: self.text_pick, "put": self._pick_text,
                          "action": ("다시 켜서 적용", self._restart_for_skin,
                                     lambda: self.text_pick != U.TEXT_SIZE)})
        for var, label, key, note, how in (
                (self.names, "이름표 보이기", "showNames", "포켓몬 위에 이름과 레벨을 띄웁니다.", self._toggle),
                (self.drag, "포켓몬 들어서 옮기기", "petDrag",
                 "켜면 포켓몬과 알을 마우스로 누른 채 끌어서 원하는 자리에 내려놓을 수 있습니다. 돌아다닐 영역 안에서만 "
                 "옮겨지고, 포켓몬은 내려놓으면 잠깐 서 있다가 다시 걸어다닙니다. 야생 포켓몬과 배틀 중인 포켓몬은 "
                 "옮길 수 없습니다.", self._toggle_plain),
                (self.grass, "풀숲 띄우기", "showGrass", "끄면 야생이 돋지 않습니다. 데려온 포켓몬은 그대로 걸어다닙니다.",
                 self._toggle_grass),
                (self.notif, "새 버전·친구 요청·댓글 알림", "notifyImportant",
                 "화면에 자국이 안 남는 이 셋만 알립니다. 게시판은 내 글에 댓글이, 내 댓글에 답글이 달렸을 때입니다. "
                 "잡았다·레벨업 같은 것은 띄우지 않습니다.", self._toggle_plain),
                (self.fr_note, "길드 친선전 알림", "friendlyNotify",
                 "길드원이 친선전 상대를 구하거나 친선전이 열리면 화면 오른쪽 아래에 잠깐 알립니다. 길드 채팅을 보고 "
                 "있을 때는 띄우지 않습니다 (채팅에 카드가 놓입니다).", self._toggle_plain),
                (self.fr_auto, "길드 친선전 바로 관전하기", "friendlyAuto",
                 "길드 친선전이 열리면 묻지 않고 바탕화면에서 바로 관전합니다.", self._toggle_plain)):
            self._flag(label, note, var, key, how)
        self.rows.append({"kind": "choice", "label": "야생 배틀에서 잡기",
                          "note": "체력을 조금 남기고 멈춰서 볼을 던질 틈을 줍니다. 10초 안에 안 던지거나 야생 포켓몬을 "
                                  "왼쪽 클릭하면 끝까지 싸웁니다. 색이 다른 포켓몬은 잡은 적이 있거나 고르지 않았어도 "
                                  "이렇게 합니다.",
                          "choices": list(self.CATCH_CHOICES), "get": lambda: self.catch.get(),
                          "put": lambda v: (self.catch.set(v), self._set_catch()),
                          # '고른 포켓몬만' 의 고르는 창 (ui_catch_pick) - 다른 것을 골라도 미리 골라 둘 수 있게 늘 둔다
                          "value": lambda: self._catch_pick_text(),
                          "action": ("고르기…", self._open_catch_pick, lambda: True)})
        btns = [("화면에 그리기", self._pick_area), ("기본 자리로", self._clear_area)]
        get = getattr(self.app, "screen_choices", None)
        for name, rect in (list(get()) if get else []):
            btns.append(("%s 전체" % name, (lambda r, n: lambda: self._pick_screen(r, n))(rect, name)))
        self.rows.append({"kind": "buttons", "label": "돌아다닐 영역", "note": None, "buttons": btns,
                          "value": lambda: self._area_text(self.app.settings)})
        self.rows.append({"kind": "buttons", "label": "배틀 창 크기",
                          "note": "관장·레이드·실시간 배틀 창은 다른 창처럼 가장자리를 끌어서 크기를 바꿀 수 있습니다. 창을 "
                                  "키우면 장면과 글자가 함께 커지고, 줄이면 작아집니다. 바꾼 크기는 기억해서 다음 배틀도 그 "
                                  "크기로 뜹니다.",
                          "buttons": [("기본 크기로", self._reset_zoom)],
                          "value": lambda: self.zoom_msg.cget("text"),
                          "enabled": lambda: bool(self.app.settings.get("battleSize"))})
        if self.boss is not None:
            from ... import hotkey as HOTKEY
            self.rows.append({"kind": "choice", "label": "긴급 숨기기 단축키",
                              "note": "누르면 바탕화면의 포켓몬과 포스크탑 창, 배틀 창이 한 번에 사라지고, 다시 누르면 그대로 "
                                      "돌아옵니다. 다른 프로그램을 쓰는 중에도 먹습니다. 단축키 없이도 트레이 메뉴의 "
                                      "'모두 숨기기' 로 같은 일을 할 수 있습니다.",
                              "choices": HOTKEY.choices(), "get": lambda: self.boss.get(),
                              "put": lambda v: (self.boss.set(v), self._set_boss()),
                              "extra": lambda: self.boss_msg.cget("text")})
        self.rows.append({"kind": "choice", "label": "컴퓨터 켤 때 같이 시작", "note": None,
                          "choices": [(True, "켜기"), (False, "끄기")], "get": lambda: bool(self.boot_var.get()),
                          "put": lambda v: (self.boot_var.set(v), self._toggle_autostart()),
                          "value_note": lambda: self.boot_note.cget("text"),
                          "disabled": not autostart.supported()})
        self.rows.append({"kind": "buttons", "label": "기본값으로", "note": "모든 설정을 처음 값으로 되돌립니다. 자동 시작 · "
                          "화면 테마 · 글자 크기 · 읽은 글 기록 · 잡기에서 고른 포켓몬은 그대로 둡니다.", "buttons": [("되돌리기", self.reset)]})

    # ---------------- 기본 창이 부르는 자리 ----------------
    def _say(self, text, color=None):
        self._msg = (natural(text or ""), color)
        self._soon()

    def status_say(self, text):
        self._say(text, U.DANGER)

    def _pick_skin(self, key):
        if key == self.skin_pick:
            return
        self.skin_pick = key
        self._set("skin", key)
        if key != skins.active():
            self._say("'%s' 테마는 다시 켜면 적용됩니다." % skins.BY_KEY[key].name, U.ACCENT)
        self._soon()

    def _paint_skin(self):
        self._soon()

    def _pick_text(self, level):
        if level == self.text_pick:
            return
        self.text_pick = level
        self._set("textSize", level)
        if level != U.TEXT_SIZE:
            self._say("글자 크기 '%s' 는 다시 켜면 적용됩니다." % U.TEXT_SIZES[level][0], U.ACCENT)
        self._soon()

    def show_grass(self):
        self.grass.set(bool(self.app.settings.get("showGrass", True)))
        self._soon()

    def show_boss(self):
        if self.boss is not None:
            from ... import hotkey as HOTKEY
            self.boss.set(HOTKEY.clean(self.app.settings.get("bossKey")))
            self.boss_msg.configure(text="")

    def _set_boss(self):
        ST.SettingsWindow._set_boss(self)
        self._soon()

    def _soon(self):
        if self._job is None:
            try:
                self._job = self.cv.after_idle(self._paint)
            except tk.TclError:
                pass

    # ---------------- 그리기 ----------------
    def _step(self, r, d, big=False):
        if r["kind"] == "num":
            v = r["get"]()
            s = r["big"] if big else r["step"]
            nv = max(r["lo"], min(r["hi"], round((v + d * s) / r["step"]) * r["step"]))
            if abs(nv - v) > 1e-9:
                r["put"](nv)
        elif r["kind"] == "choice" and not r.get("disabled"):
            keys = [k for k, _l in r["choices"]]
            cur = r["get"]()
            i = keys.index(cur) if cur in keys else 0
            r["put"](keys[(i + d) % len(keys)])
        self._soon()

    def _pick_row(self, i):
        self.cur = i
        self._soon()

    def _paint(self):
        self._job = None
        cv = self.cv
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 100:
            return
        cv.delete("all")
        pad = U.h(16)
        x1, x2 = pad, W - pad
        y = U.h(12)
        rh = U.h(40)
        vx2 = x2 - U.h(14)
        vw = max(U.h(220), int((x2 - x1) * 0.48))
        vx1 = vx2 - vw
        f = K.tkfont_of(cv, font(10))
        # 이름이 ◀ 단추까지 닿으면 줄을 바꾸고 그 줄만 높인다 (글꼴은 그대로 - '새 버전·친구 요청·댓글 알림' 이 단추에 가렸다)
        lf = K.tkfont_of(cv, font(11))
        lw = (vx1 - U.h(8)) - (x1 + U.h(20))
        labels, heights = [], []
        for r in self.rows:
            t = r["label"] if lf.measure(r["label"]) <= lw else K.wrap(cv, r["label"], font(11), lw)
            labels.append(t)
            heights.append(max(rh, (t.count("\n") + 1) * lf.metrics("linespace") + U.h(14)))
        # 흰 판 (진한 테 한 겹)
        K.rrect(cv, x1, y, x2, y + U.h(12) + sum(heights), 10, fill=WHITE, outline=LINE_D, width=2)
        y += U.h(6)
        for i, r in enumerate(self.rows):
            on = i == self.cur
            ry1, ry2 = y, y + heights[i]
            tg = ("row", "row%d" % i)
            if i and not on and i - 1 != self.cur:
                cv.create_line(x1 + U.h(14), ry1, x2 - U.h(14), ry1, fill=SEP)
            if on:
                K.rrect(cv, x1 + U.h(6), ry1 + 2, x2 - U.h(6), ry2 - 2, 8, fill=SEL_FILL, outline=CUR, width=2, tags=tg)
            cv.create_rectangle(x1 + U.h(8), ry1, vx1 - U.h(8), ry2, fill="", outline="", tags=tg)
            cv.create_text(x1 + U.h(20), (ry1 + ry2) // 2, text=labels[i], fill=CUR if on else INK, font=font(11),
                           anchor="w", justify="left", tags=tg)
            cv.tag_bind("row%d" % i, "<Button-1>", lambda _e, n=i: self._pick_row(n))
            m = (ry1 + ry2) // 2
            if r["kind"] in ("num", "choice"):
                bw = U.h(28)
                dis = r.get("disabled")
                for side, d, bx in (("l", -1, vx1), ("r", 1, vx2 - bw)):
                    btg = ("arr", "arr%d%s" % (i, side))
                    K.rrect(cv, bx, m - U.h(12), bx + bw, m + U.h(12), 6, fill="#eef2f7" if not dis else "#f4f5f7",
                            outline="#8a96a8" if not dis else LINE, width=1, tags=btg)
                    cv.create_text(bx + bw // 2, m, text="◀" if d < 0 else "▶", fill=CUR if not dis else DIM,
                                   font=font(10), tags=btg)
                    cv.tag_bind("arr%d%s" % (i, side), "<Button-1>",
                                lambda _e, rr=r, dd=d, n=i: (self._pick_row(n), self._step(rr, dd)))
                    cv.tag_bind("arr%d%s" % (i, side), "<Shift-Button-1>",
                                lambda _e, rr=r, dd=d, n=i: (self._pick_row(n), self._step(rr, dd, big=True)))
                if r["kind"] == "num":
                    v = r["get"]()
                    text = r["fmt"] % v
                    # 값 막대: 눌러서 그 자리 값으로
                    bx1, bx2 = vx1 + bw + U.h(10), vx2 - bw - U.h(10)
                    by = m + U.h(9)
                    cv.create_rectangle(bx1, by, bx2, by + U.h(4), fill="#d4d8de", outline="", tags=("bar%d" % i,))
                    k = (v - r["lo"]) / float((r["hi"] - r["lo"]) or 1)
                    cv.create_rectangle(bx1, by, bx1 + int((bx2 - bx1) * k), by + U.h(4), fill="#3a6ad0",
                                        outline="", tags=("bar%d" % i,))
                    cv.tag_bind("bar%d" % i, "<Button-1>",
                                lambda e, rr=r, a=bx1, b=bx2, n=i: (self._pick_row(n), self._bar_set(rr, e.x, a, b)))
                    cv.create_text((vx1 + vx2) // 2, m - U.h(5), text=text, fill=INK, font=font(11), anchor="center")
                else:
                    cur = r["get"]()
                    text = dict(r["choices"]).get(cur, str(cur))
                    tw = vx2 - vx1 - 2 * bw - U.h(16)
                    if f.measure(text) > tw:
                        while len(text) > 2 and f.measure(text + "…") > tw:
                            text = text[:-1]
                        text += "…"
                    cv.create_text((vx1 + vx2) // 2, m, text=text, fill=DIM if dis else INK, font=font(10),
                                   anchor="center")
            else:
                x = vx2
                for label, fn in reversed(r["buttons"]):
                    key = (i, label)
                    b = self.btns.get(key)
                    if b is None:
                        b = self.btns[key] = K.CButton(cv, label, fn, "gray", font(10))
                    en = r.get("enabled")
                    b.configure(state="normal" if (en is None or en()) else "disabled")
                    w = b.want_width(U.h(18))
                    b.layout(x - w, m - U.h(14), x, m + U.h(14))
                    x -= w + U.h(6)
            y += heights[i]
        total = y + U.h(18)
        h = max(total, H)
        cv.configure(scrollregion=(0, 0, W, h))
        bg = cv.create_rectangle(0, 0, W, h, fill=PAGE, outline="")
        cv.tag_lower(bg)
        for b in self.btns.values():
            if b.box and b.cv is cv:
                b.draw()
        self._paint_note()

    def _paint_note(self):
        """아래 설명 창: 고른 줄의 설명 (DP 의 아래 창) · 다시 켜서 적용 · 바꾼 결과 한 줄."""
        cv = self.ncv
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 100:
            return
        cv.delete("all")
        pad = U.h(16)
        x1, x2 = pad, W - pad
        y = U.h(6)
        r = self.rows[self.cur] if self.rows else None
        if r is not None:
            lines = []
            if r.get("note"):
                lines.append((r["note"], None))
            if r.get("value"):
                v = r["value"]()
                if v:
                    lines.append((v, U.FG_DIM))
            if r.get("value_note"):
                lines.append((r["value_note"](), U.DANGER if autostart.state()[0] == "blocked" else U.FG_DIM))
            if r.get("extra") and r["extra"]():
                lines.append((r["extra"](), U.DANGER))
            act = r.get("action")
            act_on = bool(act and act[2]())
            bh = H - U.h(12) - (U.h(24) if self._msg[0] else 0)
            # 글상자 (흰 판 · 진한 테 한 겹 - v2: 오른쪽 줄무늬 없이)
            K.rrect(cv, x1, y, x2, y + bh, 8, fill=WHITE, outline=LINE_D, width=2)
            ty = y + U.h(10)
            tw = x2 - x1 - U.h(28) - (U.h(170) if act_on else 0)
            for t, c in lines:
                if not t:
                    continue
                _a, tid = K.text(cv, x1 + U.h(14), ty, t, font(10), fill=tone(c) if c else INK, width=tw)
                bb = cv.bbox(tid)
                ty = (bb[3] if bb else ty + U.h(16)) + U.h(4)
            # 단추는 글자(act[0])마다 하나다 - 예전에는 하나를 같이 써서, 처음 만든 줄의 글자·할 일이 다른 줄에도
            # 남았다 ('다시 켜서 적용' 자리에 '고르기…' 를 달면서 나눴다).
            want = "act:" + act[0] if act_on else None
            for k in [k for k in self.btns if _is_act(k) and k != want]:
                self.btns[k].hide()
            if act_on:
                b = self.btns.get(want)
                if b is None:
                    b = self.btns[want] = K.CButton(cv, act[0], act[1], "blue", font(10))
                w = b.want_width(U.h(22))
                b.layout(x2 - U.h(12) - w, y + (bh - U.h(36)) // 2, x2 - U.h(12), y + (bh + U.h(36)) // 2)
            y += bh + U.h(4)
        # 상태 한 줄 (바꾼 결과)
        text, color = self._msg
        if text:
            K.text(cv, x1 + 4, y, text, font(10), fill=tone(color) if color else INK2, width=x2 - x1 - 8)
        for k, b in self.btns.items():
            if _is_act(k) and b.box:
                b.draw()

    def _bar_set(self, r, x, a, b):
        k = max(0.0, min(1.0, (x - a) / float((b - a) or 1)))
        v = r["lo"] + k * (r["hi"] - r["lo"])
        v = round(v / r["step"]) * r["step"]
        r["put"](max(r["lo"], min(r["hi"], v)))
        self._soon()
