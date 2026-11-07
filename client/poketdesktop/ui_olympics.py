# -*- coding: utf-8 -*-
"""포스크탑 올림픽 — 올림픽 창 · 신청 창 · 순위표 · 결과 카드.

    open_olympics(app, pet=None)   트레이 · 포켓몬 오른쪽 클릭 ('올림픽에 출전...')
    menu_row(app, pet)             오른쪽 클릭 메뉴 줄 (기간 밖이면 None)

올림픽 창: 위에 다음 경기(평일 O.AT, 오후 2시)까지 남은 때 · 오늘의 응원 타입 · 지친 포켓몬, 아래에 종목 카드 7장.
카드마다 내 신청(포켓몬 · 작전) · 내 최고 기록과 주간 순위 · 지난 경기 결과와 '다시 보기', [신청]/[바꾸기] [순위].

신청 창: 내 포켓몬마다 별(1~5)과 알기 쉬운 표시('체형 딱 맞음' · '전기 특기' · '오늘 응원 타입!' · '지침 −3%').
숫자는 보여 주지 않는다 - 모두에게 같은 정보 (계산을 잘하는 사람만 유리하지 않게). 작전은 안정 / 승부수.
"""
import tkinter as tk

from common import olympics as O

from . import config
from . import platform_os as PLAT
from . import ui_box
from . import ui_common as U
from .ui_common import run_async

W = 600
ENTRY_W = 560
BOARD_W = 560
OLD_SERVER_MSG = "서버 업데이트 뒤에 쓸 수 있어요."
TACTIC_NOTE = {"safe": "기록이 고르게 나와요. 실수 5%.",
               "bold": "+3% 에 운의 폭이 넓어요. 대신 실수 15% (달리기형은 넘어지고, 시기형은 파울)."}
SHOW_MAX = 80               # 신청 창에 한 번에 보이는 포켓몬 수 (찾기로 좁힌다)


def _err(err):
    if getattr(err, "status", 0) == 404:
        return OLD_SERVER_MSG
    return getattr(err, "message", None) or str(err)


def _md(day):
    if not day:
        return ""
    return "%d/%d" % (int(day[5:7]), int(day[8:10]))


def _left(sec):
    sec = max(0, int(sec or 0))
    if sec >= 86400:
        return "%d일 %d시간" % (sec // 86400, sec % 86400 // 3600)
    if sec >= 3600:
        return "%d시간 %d분" % (sec // 3600, sec % 3600 // 60)
    return "%d분" % max(1, sec // 60)


def menu_row(app, pet):
    o = getattr(app, "olympics", None)
    if o is None or not hasattr(o, "card") or (getattr(pet, "id", 0) or 0) <= 0:
        return None          # (App 메서드를 빌려 쓰는 검사의 가짜 앱 - 올림픽 기능이 없다)
    if not o.on():
        return None
    if (o.card or {}).get("phase") != "entry":
        return {"text": "포스크탑 올림픽...", "command": lambda: open_olympics(app)}
    return {"text": "올림픽에 출전...", "command": lambda: open_olympics(app, pet)}


def open_olympics(app, pet=None):
    old = getattr(app, "olympics_window", None)
    if old is not None and old.alive():
        old.lift()
        old.reload()
        return old
    w = OlympicsWindow(app, pet)
    app.olympics_window = w
    return w


class _Win(object):
    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except Exception:                                   # noqa: BLE001
            return False

    def lift(self):
        try:
            self.win.deiconify()
            self.win.lift()
        except Exception:                                   # noqa: BLE001
            pass

    def close(self):
        if self.alive():
            try:
                self.win.destroy()
            except Exception:                               # noqa: BLE001
                pass


# ---------------------------------------------------------------- 올림픽 창
class OlympicsWindow(_Win):

    def __init__(self, app, pet=None):
        self.app, self.root = app, app.root
        self.pet = pet
        self.st = None
        self.win, body = ui_box._shell(app.root, "포스크탑 올림픽", W, U.h(560))
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.head = tk.Label(body, text="불러오는 중…", bg=U.BG, fg=U.ACCENT_TEXT, font=U.FONT_H, anchor="w",
                             justify="left")
        self.head.pack(fill="x")
        self.sub = tk.Label(body, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left")
        self.sub.pack(fill="x", pady=(2, 0))
        U.wrap_to_width(self.sub)
        self.cheer = tk.Frame(body, bg=U.BG)
        self.cheer.pack(fill="x", pady=(8, 0))
        self.fatigue = tk.Label(body, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left")
        self.fatigue.pack(fill="x", pady=(4, 0))
        U.wrap_to_width(self.fatigue)
        self.err = tk.Label(body, text="", bg=U.BG, fg=U.DANGER, font=U.FONT_XS, anchor="w", justify="left")
        self.err.pack(fill="x")
        U.wrap_to_width(self.err)
        # **바닥 줄(단추)을 먼저 잡는다** (side="bottom"). 굴러가는 칸을 먼저 담으면 그 칸이 높이를 다 먹어서 목록이
        # 길 때 단추가 창 밖으로 밀려난다 - 신청 창에서 '신청' 단추가 안 보였다 (11/06 사용자 제보, expedition_ui 와 같은 까닭)
        bar = tk.Frame(body, bg=U.BG)
        bar.pack(fill="x", pady=(10, 0), side="bottom")
        self.close_btn = U.ghost_button(bar, "닫기", self.close, height=32)
        self.close_btn.pack(side="right")
        U.ghost_button(bar, "새로 고침", self.reload, height=32).pack(side="right", padx=(0, 8))
        self.inner, self.cv = ui_box.scroll_body(body)
        ui_box.fit(self.win, hi=U.h(720), scroll=(self.cv, self.inner))
        self.reload()

    def close(self):
        _Win.close(self)
        if getattr(self.app, "olympics_window", None) is self:
            self.app.olympics_window = None

    def reload(self):
        run_async(self.root, lambda: self.app.api.olympics(), self._got)

    def _show_if(self, label, on):
        """빈 글 줄이 자리를 먹지 않게 - 글이 있을 때만 놓는다 (응원 줄 바로 아래 차례로)."""
        try:
            if on and not label.winfo_manager():
                label.pack(fill="x", pady=(4, 0), before=self.cv.master)
            elif not on and label.winfo_manager():
                label.pack_forget()
        except Exception:                                   # noqa: BLE001
            pass

    def _got(self, r, err):
        if not self.alive():
            return
        if err:
            self.err.configure(text=_err(err))
            self._show_if(self.err, True)
            self.head.configure(text="포스크탑 올림픽")
            return self._fit()
        self.err.configure(text="")
        self._show_if(self.err, False)
        self.st = r or {}
        self._paint()
        if self.pet is not None and self.st.get("phase") == "entry":
            pet, self.pet = self.pet, None
            ev = self._best_event_for(pet)
            if ev:
                EntryWindow(self.app, ev, self, pre=pet.id)

    def _best_event_for(self, pet):
        """오른쪽 클릭으로 열었을 때: 그 포켓몬이 아직 안 나간 첫 종목."""
        for e in self.st.get("events") or []:
            ent = e.get("entry")
            if ent is None or (ent.get("pokemon") or {}).get("id") == pet.id:
                return e["key"]
        return None

    def _fit(self):
        ui_box.fit(self.win, hi=U.h(720), scroll=(self.cv, self.inner), keep_pos=True)

    # ---------------- 그리기
    def _paint(self):
        st = self.st
        ph = st.get("phase")
        days = st.get("days") or []
        nday = st.get("nextDay")
        if ph == "before":
            self.head.configure(text="포스크탑 올림픽 — 곧 시작해요")
            self.sub.configure(text="신청은 %s 뒤부터 받아요. 경기는 평일 %d번, 매일 %s에 다 같이 해요."
                               % (_left(st.get("openIn")), len(days), O.at_text(st.get("at"))))
        elif ph == "entry":
            self.head.configure(text="포스크탑 올림픽 %d일째 · %s %s" % (st.get("dayNo") or 1, _md(nday),
                                                                     O.at_text(st.get("at"))))
            self.sub.configure(text="경기까지 %s 남았어요. 경기 전까지 종목마다 한 마리씩 신청해 두면, %s에 "
                               "신청한 포켓몬이 다 같이 뛰고 바탕화면에서 중계돼요." % (_left(st.get("startsIn")),
                                                                     O.at_text(st.get("at"))))
        elif ph == "live":
            self.head.configure(text="포스크탑 올림픽 %d일째 · 지금 경기 중!" % (st.get("dayNo") or 1))
            self.sub.configure(text="내 포켓몬 경기는 바탕화면에서 중계돼요. 종목 결과는 그 종목 중계가 끝나면 나와요.")
        else:
            self.head.configure(text="포스크탑 올림픽 — 끝났어요")
            self.sub.configure(text="종목마다 일주일 최고 기록으로 최종 순위를 정했어요. 경기 다시 보기는 일주일 동안 열려 있어요.")
        for w in self.cheer.winfo_children():
            w.destroy()
        if st.get("cheer") and ph in ("entry", "live", "before"):
            tk.Label(self.cheer, text="%s 응원 타입 (+5%%)" % ("오늘의" if ph == "live" else "다음 경기"),
                     bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(side="left", padx=(0, 8))
            for c in st["cheer"]:
                U.chip(self.cheer, c["kr"], U.TYPE_COLOR.get(c["type"], U.BG3), font=U.FONT_S,
                       padx=8, pady=1).pack(side="left", padx=(0, 4))
        fat = st.get("fatigue") or {}
        bits = []
        for e in st.get("events") or []:
            lst = fat.get(e["key"]) or []
            if lst:
                bits.append("%s: %s" % (e["short"], ", ".join("%s −%d%%" % (f["species"], f["pen"]) for f in lst[:3])))
        self.fatigue.configure(text=("지친 포켓몬 (앞 경기에 많이 나간 종) — " + " · ".join(bits)) if bits else "")
        self._show_if(self.fatigue, bool(bits))
        for w in self.inner.winfo_children():
            w.destroy()
        if st.get("myMedals"):
            self._medals(st)
        for e in st.get("events") or []:
            self._event_card(e, ph)
        if st.get("medals"):
            self._podium(st)
        self._fit()

    def _event_card(self, e, ph):
        card = tk.Frame(self.inner, bg=U.BG2, highlightthickness=1, highlightbackground=U.LINE)
        card.pack(fill="x", pady=3, padx=(0, 4))
        top = tk.Frame(card, bg=U.BG2)
        top.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(top, text=e["kr"], bg=U.BG2, fg=U.FG, font=U.FONT_B).pack(side="left")
        tries = "  ·  세 번 중 최고" if e.get("tries", 1) > 1 else ""
        tk.Label(top, text="%s%s" % (e["statKr"], tries), bg=U.BG2, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="left", padx=(8, 0))
        btns = tk.Frame(top, bg=U.BG2)
        btns.pack(side="right")
        U.ghost_button(btns, "순위", lambda k=e["key"]: BoardWindow(self.app, k), height=26).pack(side="right")
        if ph == "entry":
            text = "바꾸기" if e.get("entry") else "신청"
            b = U.PushButton(btns, text, lambda k=e["key"]: EntryWindow(self.app, k, self), height=26,
                             font=U.FONT_S)
            b.pack(side="right", padx=(0, 6))
        tip = "특기 %s%s · %dkg 안팎이 알맞아요" % (
            "·".join(e.get("types") or []),
            (" · 특성 %s" % "·".join(e.get("abil") or [])) if e.get("abil") else "", e.get("kg0") or 0)
        if e.get("dislike"):
            tip += " · %s 은(는) 물을 싫어해요" % "·".join(e["dislike"])
        tk.Label(card, text=tip, bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left"
                 ).pack(fill="x", padx=12)
        ent = e.get("entry")
        if ent:
            line = "신청: %s · %s" % (ent["pokemon"]["name"], ent.get("tacticKr"))
            row = tk.Frame(card, bg=U.BG2)
            row.pack(fill="x", padx=12, pady=(4, 0))
            tk.Label(row, text=line, bg=U.BG2, fg=U.GOOD, font=U.FONT_S).pack(side="left")
            if ph == "entry":
                x = tk.Label(row, text="취소", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_XS, cursor="hand2")
                x.pack(side="left", padx=(10, 0))
                x.bind("<Button-1>", lambda _e, k=e["key"]: self._cancel(k))
        elif ph == "entry":
            tk.Label(card, text="아직 신청 안 했어요", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w"
                     ).pack(fill="x", padx=12, pady=(4, 0))
        best = e.get("best")
        if best:
            tk.Label(card, text="내 최고 %s (%s) · 주간 %d위 / %d명" % (best["text"], _md(best["day"]), best["rank"],
                                                                best["total"]),
                     bg=U.BG2, fg=U.ACCENT_TEXT, font=U.FONT_S, anchor="w").pack(fill="x", padx=12, pady=(2, 0))
        last = e.get("last")
        if last:
            row = tk.Frame(card, bg=U.BG2)
            row.pack(fill="x", padx=12, pady=(2, 0))
            if last.get("released", True) and last.get("text"):
                rk = ("%d위" % last["rank"]) if last.get("rank") else ""
                text = "%s 경기: %s %s%s" % (_md(last["day"]), last["pokemon"]["name"], last["text"],
                                           " · " + rk if rk else "")
            else:
                text = "%s 경기: %s · 중계 전이에요 (기록은 중계 뒤에)" % (_md(last["day"]), last["pokemon"]["name"])
            tk.Label(row, text=text, bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S).pack(side="left")
            if last.get("released", True):              # 중계 전에 다시 보기로 먼저 보면 결과가 샌다
                v = tk.Label(row, text="다시 보기", bg=U.BG2, fg=U.INFO, font=U.FONT_XS, cursor="hand2")
                v.pack(side="left", padx=(10, 0))
                v.bind("<Button-1>", lambda _e, i=last["entryId"]: self._replay(i))
        tk.Frame(card, bg=U.BG2, height=8).pack(fill="x")

    def _medals(self, st):
        box = tk.Frame(self.inner, bg=U.BG2, highlightthickness=2, highlightbackground=U.ACCENT)
        box.pack(fill="x", pady=(0, 6), padx=(0, 4))
        tk.Label(box, text="내 메달", bg=U.BG2, fg=U.ACCENT, font=U.FONT_B, anchor="w").pack(fill="x", padx=12,
                                                                                         pady=(8, 2))
        names = {1: "금메달", 2: "은메달", 3: "동메달"}
        for m in st["myMedals"]:
            text = "%s  %s · %s %s" % (names.get(m["rank"], "%d위 (결선)" % m["rank"]), m["kr"],
                                      m["pokemon"]["name"], m["text"])
            tk.Label(box, text=text, bg=U.BG2, fg=U.FG, font=U.FONT_S, anchor="w").pack(fill="x", padx=12)
        tk.Frame(box, bg=U.BG2, height=8).pack(fill="x")

    def _podium(self, st):
        box = tk.Frame(self.inner, bg=U.BG2, highlightthickness=1, highlightbackground=U.LINE)
        box.pack(fill="x", pady=(6, 0), padx=(0, 4))
        tk.Label(box, text="종목별 메달", bg=U.BG2, fg=U.ACCENT_TEXT, font=U.FONT_B, anchor="w").pack(
            fill="x", padx=12, pady=(8, 2))
        for e in st.get("events") or []:
            rows = st["medals"].get(e["key"]) or []
            text = "  ".join("%d. %s의 %s %s" % (r["rank"], r["user"], r["pokemon"]["name"], r["text"]) for r in rows)
            tk.Label(box, text="%s — %s" % (e["short"], text or "기록 없음"), bg=U.BG2, fg=U.FG_DIM, font=U.FONT_XS,
                     anchor="w", justify="left").pack(fill="x", padx=12)
        tk.Frame(box, bg=U.BG2, height=8).pack(fill="x")

    # ---------------- 하기
    def _cancel(self, event):
        def back(_r, err):
            if err:
                self.err.configure(text=_err(err))
                return self._fit()
            self.reload()
            self.app.request_sync()
        run_async(self.root, lambda: self.app.api.olympics_cancel(event), back)

    def _replay(self, entry_id):
        o = getattr(self.app, "olympics", None)
        if o is None:
            return

        def back(_h, err):
            if err and self.alive():
                self.err.configure(text=err)
                self._fit()
        o.replay(entry_id, back)


# ---------------------------------------------------------------- 신청 창
class EntryWindow(_Win):

    def __init__(self, app, event, parent=None, pre=None):
        self.app, self.root = app, app.root
        self.event = event
        self.parent = parent
        self.pick = pre
        self.tactic = "safe"
        self.cands = []
        self.rows = {}
        ev = O.EV[event]
        self.win, body = ui_box._shell(app.root, "%s 신청" % ev["kr"], ENTRY_W, U.h(560))
        tk.Label(body, text="%s — 누가 나갈까요?" % ev["kr"], bg=U.BG, fg=U.FG, font=U.FONT_H, anchor="w"
                 ).pack(fill="x")
        intro = tk.Label(body, text="별이 많을수록 이 종목에 어울려요. 노력치 · 개체값 · 레벨은 기록에 들어가지 않아요 - "
                                    "종 · 몸무게 · 타입 · 특성 · 오늘의 응원과 운으로 정해져요. 한 마리는 하루 한 종목만 나가요.",
                         bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS, anchor="w", justify="left")
        intro.pack(fill="x", pady=(2, 6))
        U.wrap_to_width(intro)
        find = tk.Frame(body, bg=U.BG)
        find.pack(fill="x", pady=(0, 6))
        tk.Label(find, text="찾기", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(side="left")
        self.q = tk.StringVar()
        ent = tk.Entry(find, textvariable=self.q, bg=U.BG3, fg=U.FG, insertbackground=U.FG, relief="flat",
                       font=U.FONT_S)
        ent.pack(side="left", fill="x", expand=True, padx=(8, 0), ipady=3)
        self.q.trace_add("write", lambda *_a: self._list())
        # **바닥 줄(단추)을 먼저 잡는다** (side="bottom"). 굴러가는 칸을 먼저 담으면 그 칸이 높이를 다 먹어서 목록이
        # 길 때 단추가 창 밖으로 밀려난다 - 신청 창에서 '신청' 단추가 안 보였다 (11/06 사용자 제보, expedition_ui 와 같은 까닭)
        foot = tk.Frame(body, bg=U.BG)
        foot.pack(fill="x", side="bottom")
        tac = tk.Frame(foot, bg=U.BG)
        tac.pack(fill="x", pady=(8, 0))
        tk.Label(tac, text="작전", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(side="left")
        self.tac_btns = {}
        for key in ("safe", "bold"):
            b = tk.Label(tac, text=O.TACTICS[key]["kr"], bg=U.BG4, fg=U.FG, font=U.FONT_S, padx=12, pady=3,
                         cursor="hand2")
            b.pack(side="left", padx=(8, 0))
            b.bind("<Button-1>", lambda _e, k=key: self._tac(k))
            self.tac_btns[key] = b
        self.tac_note = tk.Label(foot, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left")
        self.tac_note.pack(fill="x", pady=(2, 0))
        U.wrap_to_width(self.tac_note)
        self.err = tk.Label(foot, text="", bg=U.BG, fg=U.DANGER, font=U.FONT_XS, anchor="w", justify="left")
        self.err.pack(fill="x")
        U.wrap_to_width(self.err)
        bar = tk.Frame(foot, bg=U.BG)
        bar.pack(fill="x", pady=(10, 0))
        self.go = U.PushButton(bar, "신청", self._go, height=34, font=U.FONT_B)
        self.go.pack(side="right")
        U.ghost_button(bar, "닫기", self.close, height=34).pack(side="right", padx=(0, 8))
        self.inner, self.cv = ui_box.scroll_body(body)
        self._tac("safe")
        tk.Label(self.inner, text="불러오는 중…", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(anchor="w")
        ui_box.fit(self.win, hi=U.h(700), scroll=(self.cv, self.inner))
        run_async(self.root, lambda: app.api.olympics_candidates(event), self._got)

    def _fit(self):
        ui_box.fit(self.win, hi=U.h(700), scroll=(self.cv, self.inner), keep_pos=True)

    def _tac(self, key):
        self.tactic = key
        for k, b in self.tac_btns.items():
            on = k == key
            b.configure(bg=U.ACCENT if on else U.BG4, fg=U.ACCENT_DARK if on else U.FG)
        self.tac_note.configure(text=TACTIC_NOTE[key])

    def _got(self, r, err):
        if not self.alive():
            return
        if err:
            self.err.configure(text=_err(err))
            return self._fit()
        self.cands = (r or {}).get("pokemon") or []
        cur = next((c for c in self.cands if c.get("entered")), None)
        if self.pick is None and cur is not None:
            self.pick = cur["id"]
        self._list()

    def _list(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.rows = {}
        q = (self.q.get() or "").strip()
        shown = [c for c in self.cands if not q or q in (c.get("name") or "") or q in (c.get("species") or "")]
        for c in shown[:SHOW_MAX]:
            self._row(c)
        if len(shown) > SHOW_MAX:
            tk.Label(self.inner, text="… %d마리 더 있어요. 이름으로 찾아 보세요." % (len(shown) - SHOW_MAX),
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS).pack(anchor="w", pady=4)
        if not shown:
            tk.Label(self.inner, text="포켓몬이 없어요", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(anchor="w")
        self._fit()

    def _row(self, c):
        off = bool(c.get("away") or c.get("usedIn"))
        on = c["id"] == self.pick
        bg = U.BG4 if on else U.BG2
        row = tk.Frame(self.inner, bg=bg, highlightthickness=1,
                       highlightbackground=U.ACCENT if on else U.LINE, cursor="arrow" if off else "hand2")
        row.pack(fill="x", pady=2, padx=(0, 4))
        top = tk.Frame(row, bg=bg)
        top.pack(fill="x", padx=10, pady=(5, 0))
        name = "%s%s" % (c.get("name"), "" if c.get("name") == c.get("species") else " (%s)" % c.get("species"))
        tk.Label(top, text=name, bg=bg, fg=U.SHINY if c.get("shiny") else (U.FG_FAINT if off else U.FG),
                 font=U.FONT_B).pack(side="left")
        tk.Label(top, text="Lv.%s · %skg" % (c.get("level"), c.get("kg")), bg=bg, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(side="left", padx=(6, 0))
        tk.Label(top, text="★" * c["stars"] + "☆" * (5 - c["stars"]), bg=bg,
                 fg=U.FG_FAINT if off else U.ACCENT, font=U.FONT_S).pack(side="right")
        line = tk.Frame(row, bg=bg)
        line.pack(fill="x", padx=10, pady=(2, 6))
        if c.get("away"):
            tk.Label(line, text="탐험에 나가 있어요", bg=bg, fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left")
        elif c.get("usedIn"):
            tk.Label(line, text="이번 경기에 %s에 나가요" % O.EV[c["usedIn"]]["kr"], bg=bg, fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(side="left")
        for h in c.get("hints") or []:
            good = not (h.startswith("너무") or h.startswith("조금") or "부족" in h or "지침" in h or "싫어" in h)
            fg = U.GOOD if good else U.DANGER
            if h == "오늘 응원 타입!":
                fg = U.ACCENT
            tk.Label(line, text=h, bg=U.BG3, fg=fg, font=U.FONT_XS, padx=6).pack(side="left", padx=(0, 4))
        if not off:
            for w in [row, top, line] + list(top.winfo_children()) + list(line.winfo_children()):
                w.bind("<Button-1>", lambda _e, i=c["id"]: self._choose(i))
        self.rows[c["id"]] = row

    def _choose(self, pid):
        self.pick = pid
        y = self.cv.yview()
        self._list()
        try:
            self.cv.yview_moveto(y[0])
        except Exception:                                   # noqa: BLE001
            pass

    def _go(self):
        if self.pick is None:
            self.err.configure(text="나갈 포켓몬을 골라 주세요.")
            return self._fit()

        def back(r, err):
            if not self.alive():
                return
            if err:
                self.err.configure(text=_err(err))
                return self._fit()
            msg = (r or {}).get("message")
            self.close()
            if self.parent is not None and self.parent.alive():
                self.parent.reload()
            try:
                self.app.request_sync()
            except Exception:                               # noqa: BLE001
                pass
            if msg:
                config.log("[올림픽] %s" % msg)
        run_async(self.root, lambda: self.app.api.olympics_enter(self.event, self.pick, self.tactic), back)


# ---------------------------------------------------------------- 순위표
class BoardWindow(_Win):

    def __init__(self, app, event):
        self.app, self.root = app, app.root
        self.event = event
        self.day = None
        ev = O.EV[event]
        self.win, body = ui_box._shell(app.root, "%s 순위" % ev["kr"], BOARD_W, U.h(560))
        tabs = tk.Frame(body, bg=U.BG)
        tabs.pack(fill="x")
        self.tabs = {}
        for key, text in [(None, "주간 (최종)")] + [(d, "%d일째" % (i + 1)) for i, d in enumerate(O.DAYS)]:
            b = tk.Label(tabs, text=text, bg=U.BG4, fg=U.FG, font=U.FONT_XS, padx=7, pady=2, cursor="hand2")
            b.pack(side="left", padx=(0, 3))
            b.bind("<Button-1>", lambda _e, k=key: self._tab(k))
            self.tabs[key] = b
        self.note = tk.Label(body, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS, anchor="w", justify="left")
        self.note.pack(fill="x", pady=(6, 4))
        U.wrap_to_width(self.note)
        # **바닥 줄(단추)을 먼저 잡는다** (side="bottom"). 굴러가는 칸을 먼저 담으면 그 칸이 높이를 다 먹어서 목록이
        # 길 때 단추가 창 밖으로 밀려난다 - 신청 창에서 '신청' 단추가 안 보였다 (11/06 사용자 제보, expedition_ui 와 같은 까닭)
        bar = tk.Frame(body, bg=U.BG)
        bar.pack(fill="x", pady=(10, 0), side="bottom")
        self.close_btn = U.ghost_button(bar, "닫기", self.close, height=32)
        self.close_btn.pack(side="right")
        self.inner, self.cv = ui_box.scroll_body(body)
        self._tab(None)

    def _fit(self):
        ui_box.fit(self.win, hi=U.h(700), scroll=(self.cv, self.inner), keep_pos=self.win.winfo_ismapped())

    def _tab(self, day):
        self.day = day
        for k, b in self.tabs.items():
            on = k == day
            b.configure(bg=U.ACCENT if on else U.BG4, fg=U.ACCENT_DARK if on else U.FG)
        self.note.configure(text="불러오는 중…")
        run_async(self.root, lambda: self.app.api.olympics_board(self.event, day), self._got)

    def _got(self, r, err):
        if not self.alive():
            return
        for w in self.inner.winfo_children():
            w.destroy()
        if err:
            self.note.configure(text=_err(err))
            return self._fit()
        r = r or {}
        if r.get("hidden"):
            self.note.configure(text="아직 결과가 공개되지 않았어요 (그 종목 중계가 끝나면 나와요).")
        elif not r.get("rows"):
            self.note.configure(text="아직 기록이 없어요.")
        else:
            me = r.get("me")
            self.note.configure(text="%d명 참가%s" % (r.get("total", 0), (" · 내 순위 %d위 (%s)" % (me["rank"], me["text"]))
                                                   if me else ""))
        rows = list(r.get("rows") or [])
        me = r.get("me")
        if me and not any(x.get("mine") for x in rows):
            rows.append(None)
            rows.append(me)
        for x in rows:
            if x is None:
                tk.Label(self.inner, text="⋯", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S).pack(anchor="w")
                continue
            self._row(x)
        self._fit()

    def _row(self, x):
        bg = U.BG4 if x.get("mine") else U.BG2
        row = tk.Frame(self.inner, bg=bg)
        row.pack(fill="x", pady=1, padx=(0, 4))
        medal = {1: U.ACCENT, 2: "#d6dbe6", 3: "#d09a6a"}.get(x["rank"], U.FG_DIM)
        tk.Label(row, text="%d" % x["rank"], bg=bg, fg=medal, font=U.FONT_B, width=4, anchor="e").pack(side="left")
        tk.Label(row, text="%s의 %s" % (x["user"], x["pokemon"]["name"]), bg=bg,
                 fg=U.ACCENT_TEXT if x.get("mine") else U.FG, font=U.FONT_S).pack(side="left", padx=(8, 0))
        v = tk.Label(row, text="보기", bg=bg, fg=U.INFO, font=U.FONT_XS, cursor="hand2")
        v.pack(side="right", padx=(6, 8))
        v.bind("<Button-1>", lambda _e, i=x["entryId"]: self._watch(i))
        tk.Label(row, text=x["text"], bg=bg, fg=U.FG, font=U.FONT_B).pack(side="right")
        if not self.day:
            tk.Label(row, text=_md(x.get("day")), bg=bg, fg=U.FG_FAINT, font=U.FONT_XS).pack(side="right", padx=(0, 8))

    def _watch(self, entry_id):
        o = getattr(self.app, "olympics", None)
        if o is None:
            return

        def back(_h, err):
            if err and self.alive():
                self.note.configure(text=err)
                self._fit()
        o.replay(entry_id, back)


# ---------------------------------------------------------------- 결과 카드
class ResultCard(object):
    """중계가 끝나면 경기장 위에 잠깐: 기록 · 조 순위 · 오늘 순위 · [다시 보기] [올림픽 창] [닫기]."""

    def __init__(self, app, heat, result, ms=15000):
        self.app, self.root = app, app.root
        self.dead = False
        mine = next((e for e in heat.get("entrants") or [] if e.get("mine")), None) or {}
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.configure(bg=U.ACCENT)
        box = tk.Frame(self.win, bg=U.BG2)
        box.pack(padx=2, pady=2)
        tk.Label(box, text="%s · %d조" % (O.EV[heat["event"]]["kr"], heat.get("heat") or 1), bg=U.BG2,
                 fg=U.FG_DIM, font=U.FONT_XS).pack(anchor="w", padx=12, pady=(8, 0))
        tk.Label(box, text="%s  %s" % ((mine.get("pokemon") or {}).get("name", "?"), result.get("text") or "-"),
                 bg=U.BG2, fg=U.ACCENT_TEXT, font=U.FONT_H).pack(anchor="w", padx=12)
        bits = []
        if result.get("heatRank"):
            bits.append("조 %d위 / %d" % (result["heatRank"], result.get("heatSize") or 0))
        if result.get("rank"):
            bits.append("이 경기 날 %d위 / %d명" % (result["rank"], result.get("total") or 0))
        else:
            bits.append("전체 순위는 이 종목 중계가 다 끝나면 올림픽 창에")     # 순위표 공개 전 (서버가 안 싣는다)
        tk.Label(box, text="  ·  ".join(bits), bg=U.BG2, fg=U.FG, font=U.FONT_S).pack(anchor="w", padx=12)
        bar = tk.Frame(box, bg=U.BG2)
        bar.pack(fill="x", padx=12, pady=(6, 10))
        for text, fn in (("다시 보기", self._again), ("올림픽 창", self._open), ("닫기", self.close)):
            b = tk.Label(bar, text=text, bg=U.BG3, fg=U.FG, font=U.FONT_XS, padx=8, pady=2, cursor="hand2")
            b.pack(side="left", padx=(0, 6))
            b.bind("<Button-1>", lambda _e, f=fn: f())
        self.entry_id = result.get("entryId")
        self.win.update_idletasks()
        try:
            from .olympics_show import stage_screen
            x1, _y1, x2, y2 = stage_screen(app)
            w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
            self.win.geometry("+%d+%d" % (int((x1 + x2) / 2 - w / 2), int(y2 - h - 60)))
        except Exception:                                   # noqa: BLE001
            pass
        PLAT.raise_above(self.win)
        self._job = self.root.after(ms, self.close)

    def _again(self):
        eid = self.entry_id
        self.close()
        o = getattr(self.app, "olympics", None)
        if o is not None and eid:
            o.replay(eid)

    def _open(self):
        self.close()
        open_olympics(self.app)

    def close(self):
        if self.dead:
            return
        self.dead = True
        try:
            self.root.after_cancel(self._job)
        except Exception:                                   # noqa: BLE001
            pass
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
