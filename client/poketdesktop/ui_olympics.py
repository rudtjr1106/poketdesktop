# -*- coding: utf-8 -*-
"""포스크탑 올림픽 — 허브 '이벤트' 탭(OlympicsPane) · 신청 창 · 결과 창 · 결과 카드.

    open_olympics(app, pet=None)   트레이 · 포켓몬 오른쪽 클릭 ('올림픽에 출전...') - 허브를 이벤트 탭으로 연다
    menu_row(app, pet)             오른쪽 클릭 메뉴 줄 (기간 밖이면 None)

이벤트 탭 (11/08 사용자 '이벤트탭을 신설해서 참여할 수 있게'): 위에 다음 경기 · 남은 때, 아래에 종목 일곱 줄 (하루 한
종목 - 날짜 · 상태 · 그날 응원 타입 · 내 신청 · 내 결과(순위 · 간 라운드) · [신청/바꾸기] [결과] [다시 보기]).
결과 창: 공개된 라운드마다 조 결과(Q/q) · 그날 끝나면 최종 순위.

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
    """허브를 이벤트 탭(올림픽)으로 연다. pet 을 주면(오른쪽 클릭) 그 포켓몬으로 신청 창까지."""
    pane = None
    try:
        pane = app._tab("olympics")                          # 허브를 열고 그 탭으로 (app._tab)
    except Exception as e:                                   # noqa: BLE001
        config.log("이벤트 탭 열기 실패: %s" % e)
    if pane is None:
        return None
    if pet is not None:
        pane.pre = pet
    pane.reload()
    return pane


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


# ---------------------------------------------------------------- 이벤트 탭 (허브)
WEEK = "월화수목금토일"


def _mdw(day):
    if not day:
        return ""
    import datetime
    d = datetime.date(int(day[0:4]), int(day[5:7]), int(day[8:10]))
    return "%d/%d(%s)" % (d.month, d.day, WEEK[d.weekday()])


STATUS = {"before": ("곧 신청", U.FG_FAINT), "entry": ("신청 중", U.GOOD), "live": ("경기 중", U.ACCENT),
          "done": ("끝", U.FG_DIM)}


class OlympicsPane(object):
    """허브 '이벤트' 묶음의 '올림픽' 탭. 판(win)은 허브가 끼운다."""

    def __init__(self, app, holder):
        self.app, self.root = app, app.root
        self.st = None
        self.pre = None              # 오른쪽 클릭으로 연 포켓몬 - 불러온 뒤 신청 창
        self._loaded_at = 0.0        # 마지막으로 불러온 때 (다시 보일 때 오래됐으면 새로)
        self.win = tk.Frame(holder, bg=U.BG)
        body = tk.Frame(self.win, bg=U.BG)
        body.pack(fill="both", expand=True, padx=U.h(16), pady=U.h(12))
        top = tk.Frame(body, bg=U.BG)
        top.pack(fill="x")
        self.head = tk.Label(top, text="불러오는 중…", bg=U.BG, fg=U.ACCENT_TEXT, font=U.FONT_H, anchor="w",
                             justify="left")
        self.head.pack(side="left", fill="x", expand=True)
        U.ghost_button(top, "새로 고침", self.reload, height=30).pack(side="right")
        self.sub = tk.Label(body, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left")
        self.sub.pack(fill="x", pady=(2, 0))
        U.wrap_to_width(self.sub)
        self.err = tk.Label(body, text="", bg=U.BG, fg=U.DANGER, font=U.FONT_XS, anchor="w", justify="left")
        self.err.pack(fill="x")
        U.wrap_to_width(self.err)
        self.inner, self.cv = ui_box.scroll_body(body)
        app.olympics_window = self                   # 로그아웃 정리 · 다시 불러오기가 찾는다
        self.reload()

    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except Exception:                                   # noqa: BLE001
            return False

    def close(self):
        """로그아웃: 판은 허브가 치운다 - 여기서는 잊기만."""
        if getattr(self.app, "olympics_window", None) is self:
            self.app.olympics_window = None

    def lift(self):
        pass

    def reload(self):
        run_async(self.root, lambda: self.app.api.olympics(), self._got)

    def on_shown(self):
        """허브가 이 탭을 다시 보여 줄 때 - 30초 넘게 지났으면 새로 불러온다 (13:50 에 연 탭을 14:05 에 다시 보면
        '신청 중' · 남은 시간이 옛것이었다 - 독립 검토 11/08)."""
        import time
        if time.time() - self._loaded_at > 30:
            self.reload()

    def _fit(self):
        try:
            self.inner.update_idletasks()
            self.cv.configure(scrollregion=self.cv.bbox("all"))
        except Exception:                                   # noqa: BLE001
            pass

    def _got(self, r, err):
        if not self.alive():
            return
        if err:
            self.err.configure(text=_err(err))
            self.head.configure(text="포스크탑 올림픽")
            return self._fit()
        self.err.configure(text="")
        self.st = r or {}
        import time
        self._loaded_at = time.time()
        self._paint()
        if self.pre is not None:
            pet, self.pre = self.pre, None
            ev = self._best_event_for(pet)
            if ev:
                EntryWindow(self.app, ev, self, pre=pet.id)

    def _best_event_for(self, pet):
        """오른쪽 클릭으로 열었을 때: 신청을 받는 종목 가운데 아직 안 낸 첫 종목 (없으면 그 포켓몬이 나간 종목)."""
        evs = [e for e in self.st.get("events") or [] if e.get("canEnter")]
        for e in evs:
            if e.get("entry") is None:
                return e["key"]
        for e in evs:
            if ((e.get("entry") or {}).get("pokemon") or {}).get("id") == pet.id:
                return e["key"]
        return evs[0]["key"] if evs else None

    # ---------------- 그리기
    def _paint(self):
        st = self.st
        ph = st.get("phase")
        nday = st.get("nextDay")
        today = O.EV.get(st.get("today") or "", {}).get("kr", "")
        n = len(st.get("days") or [])
        if ph == "before":
            self.head.configure(text="포스크탑 올림픽 — 곧 시작해요")
            self.sub.configure(text="신청은 %s 뒤부터 받아요. 평일 %d번, 하루 한 종목씩 %s에 예선부터 결승까지 치러요."
                               % (_left(st.get("openIn")), n, O.at_text(st.get("at"))))
        elif ph == "entry":
            self.head.configure(text="포스크탑 올림픽 · 다음 경기 %s %s %s" % (_mdw(nday), today, O.at_text(st.get("at"))))
            self.sub.configure(text="%s 남았어요. 종목마다 한 마리씩, 그 종목 날 %s 전까지 신청해 두세요. 참가한 포켓몬 "
                               "수에 맞춰 예선 · 준결승 · 결승으로 나뉘어 치르고 바탕화면에서 중계돼요."
                               % (_left(st.get("startsIn")), O.at_text(st.get("at"))))
        elif ph == "live":
            self.head.configure(text="포스크탑 올림픽 %d일째 · %s 경기 중!" % (st.get("dayNo") or 1, today))
            self.sub.configure(text="내 포켓몬이 뛰는 조와 결승이 바탕화면에서 중계돼요. 결과는 그날 중계가 끝나면 나와요.")
        elif ph == "closed":
            self.head.configure(text="지금 열린 이벤트가 없어요")
            self.sub.configure(text="포스크탑 올림픽은 끝났어요. 다음 이벤트가 열리면 여기에서 참가할 수 있어요.")
        else:
            self.head.configure(text="포스크탑 올림픽 — 끝났어요")
            self.sub.configure(text="종목마다 그날 결승 순위로 메달을 정했어요. 다시 보기는 일주일 동안 열려 있어요.")
        for w in self.inner.winfo_children():
            w.destroy()
        if ph == "closed":
            return self._fit()
        if st.get("myMedals"):
            self._medals(st)
        for e in st.get("events") or []:
            self._event_card(e)
        if st.get("medals"):
            self._podium(st)
        self._fit()

    def _event_card(self, e):
        on = e.get("status") in ("entry", "live")
        card = tk.Frame(self.inner, bg=U.BG2, highlightthickness=1,
                        highlightbackground=U.ACCENT if e.get("status") == "live" else U.LINE)
        card.pack(fill="x", pady=3, padx=(0, 4))
        top = tk.Frame(card, bg=U.BG2)
        top.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(top, text=_mdw(e.get("day")), bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S).pack(side="left")
        tk.Label(top, text=e["kr"], bg=U.BG2, fg=U.FG if on or e.get("ran") else U.FG_DIM,
                 font=U.FONT_B).pack(side="left", padx=(8, 0))
        text, fg = STATUS.get(e.get("status"), ("", U.FG_DIM))
        tk.Label(top, text=text, bg=U.BG2, fg=fg, font=U.FONT_XS).pack(side="left", padx=(8, 0))
        btns = tk.Frame(top, bg=U.BG2)
        btns.pack(side="right")
        if e.get("ran"):
            U.ghost_button(btns, "결과", lambda k=e["key"]: BoardWindow(self.app, k), height=26).pack(side="right")
        if e.get("canEnter"):
            b = U.PushButton(btns, "바꾸기" if e.get("entry") else "신청",
                             lambda k=e["key"]: EntryWindow(self.app, k, self), height=26, font=U.FONT_S)
            b.pack(side="right", padx=(0, 6))
        tip = "%s · 특기 %s%s · %dkg 안팎이 알맞아요" % (
            e["statKr"], "·".join(e.get("types") or []),
            (" · 특성 %s" % "·".join(e.get("abil") or [])) if e.get("abil") else "", e.get("kg0") or 0)
        tk.Label(card, text=tip, bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left"
                 ).pack(fill="x", padx=12)
        if O.TITLE.get(e["key"]):                       # 1~3위 상 (목에 거는 메달 + 그 종목 칭호)
            tk.Label(card, text="1~3위: 메달 꾸미기 · 칭호 '%s'" % O.TITLE[e["key"]], bg=U.BG2, fg=U.FG_DIM,
                     font=U.FONT_XS, anchor="w").pack(fill="x", padx=12)
        if e.get("cheer") and e.get("status") != "done":
            row = tk.Frame(card, bg=U.BG2)
            row.pack(fill="x", padx=12, pady=(3, 0))
            tk.Label(row, text="그날 응원 타입 (+5%)", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_XS).pack(side="left",
                                                                                         padx=(0, 6))
            for c in e["cheer"]:
                U.chip(row, c["kr"], U.TYPE_COLOR.get(c["type"], U.BG3), font=U.FONT_XS, padx=6,
                       pady=0).pack(side="left", padx=(0, 4))
        ent = e.get("entry")
        if ent:
            row = tk.Frame(card, bg=U.BG2)
            row.pack(fill="x", padx=12, pady=(4, 0))
            tk.Label(row, text="신청: %s · %s" % (ent["pokemon"]["name"], ent.get("tacticKr")), bg=U.BG2,
                     fg=U.GOOD, font=U.FONT_S).pack(side="left")
            if e.get("canEnter"):
                x = tk.Label(row, text="취소", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_XS, cursor="hand2")
                x.pack(side="left", padx=(10, 0))
                x.bind("<Button-1>", lambda _e, k=e["key"]: self._cancel(k))
        elif e.get("canEnter"):
            tk.Label(card, text="아직 신청 안 했어요", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w"
                     ).pack(fill="x", padx=12, pady=(4, 0))
        res = e.get("result")
        if e.get("status") == "live" and ent:
            tk.Label(card, text="지금 중계 중이에요 - 바탕화면에서 보세요", bg=U.BG2, fg=U.ACCENT, font=U.FONT_S,
                     anchor="w").pack(fill="x", padx=12, pady=(2, 0))
        if res:
            row = tk.Frame(card, bg=U.BG2)
            row.pack(fill="x", padx=12, pady=(2, 0))
            medal = {1: "금메달!", 2: "은메달!", 3: "동메달!"}.get(res["rank"], "")
            bits = ["%d위 / %d명" % (res["rank"], res.get("total") or 0)]
            if res.get("reached"):
                bits.append(res["reached"])
            if res.get("text"):
                bits.append(res["text"])
            tk.Label(row, text="%s%s" % ("  ".join(bits), "  " + medal if medal else ""), bg=U.BG2,
                     fg=U.ACCENT_TEXT, font=U.FONT_S).pack(side="left")
            w = res.get("watch")
            if w and w.get("heat"):
                v = tk.Label(row, text="다시 보기", bg=U.BG2, fg=U.INFO, font=U.FONT_XS, cursor="hand2")
                v.pack(side="left", padx=(10, 0))
                v.bind("<Button-1>", lambda _e, k=e["key"], ww=w: self._replay(k, ww["round"], ww["heat"]))
        tk.Frame(card, bg=U.BG2, height=8).pack(fill="x")

    def _medals(self, st):
        box = tk.Frame(self.inner, bg=U.BG2, highlightthickness=2, highlightbackground=U.ACCENT)
        box.pack(fill="x", pady=(0, 6), padx=(0, 4))
        tk.Label(box, text="내 메달", bg=U.BG2, fg=U.ACCENT, font=U.FONT_B, anchor="w").pack(fill="x", padx=12,
                                                                                         pady=(8, 2))
        names = {1: "금메달", 2: "은메달", 3: "동메달"}
        for m in st["myMedals"]:
            text = "%s  %s · %s %s" % (names.get(m["rank"], "%d위 (결선)" % m["rank"]), m["kr"],
                                      m["pokemon"]["name"], m.get("text") or "")
            tk.Label(box, text=text, bg=U.BG2, fg=U.FG, font=U.FONT_S, anchor="w").pack(fill="x", padx=12)
        tk.Frame(box, bg=U.BG2, height=8).pack(fill="x")

    def _podium(self, st):
        box = tk.Frame(self.inner, bg=U.BG2, highlightthickness=1, highlightbackground=U.LINE)
        box.pack(fill="x", pady=(6, 0), padx=(0, 4))
        tk.Label(box, text="종목별 메달", bg=U.BG2, fg=U.ACCENT_TEXT, font=U.FONT_B, anchor="w").pack(
            fill="x", padx=12, pady=(8, 2))
        for e in st.get("events") or []:
            rows = st["medals"].get(e["key"]) or []
            if not rows:
                continue
            text = "  ".join("%d. %s의 %s %s" % (r["rank"], r["user"], r["pokemon"]["name"], r.get("text") or "")
                             for r in rows)
            tk.Label(box, text="%s — %s" % (e["short"], text), bg=U.BG2, fg=U.FG_DIM, font=U.FONT_XS,
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

    def _replay(self, event, rnd, heat_no):
        o = getattr(self.app, "olympics", None)
        if o is None:
            return

        def back(_h, err):
            if err and self.alive():
                self.err.configure(text=err)
                self._fit()
        o.replay(event, rnd, heat_no, back)


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
                                    "종 · 몸무게 · 타입 · 특성 · 그날 응원과 운으로 정해져요. 같은 포켓몬을 여러 종목에 내도 돼요.",
                         bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS, anchor="w", justify="left")
        intro.pack(fill="x", pady=(2, 0))
        U.wrap_to_width(intro)
        self.share = tk.Label(body, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left")
        self.share.pack(fill="x", pady=(2, 6))
        U.wrap_to_width(self.share)
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
        sh = (r or {}).get("share") or []
        if sh:
            self.share.configure(text="지금 신청자 %d명 · 많이 나온 종: %s (몫이 5%%를 넘으면 지침 −5%%, 2시에 확정)" % (
                (r or {}).get("total") or 0, ", ".join("%s %d%%" % (x["species"], x["pct"]) for x in sh)))
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
        off = bool(c.get("away"))
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
        elif c.get("alsoIn"):
            tk.Label(line, text="%s에도 나가요" % " · ".join(c["alsoIn"]), bg=bg, fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(side="left", padx=(0, 4))
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


# ---------------------------------------------------------------- 결과 창 (라운드 · 최종 순위)
class BoardWindow(_Win):

    def __init__(self, app, event):
        self.app, self.root = app, app.root
        self.event = event
        self.r = None
        self.view = None             # 라운드 번호 · 'final'
        ev = O.EV[event]
        self.win, body = ui_box._shell(app.root, "%s 결과" % ev["kr"], BOARD_W, U.h(560))
        self.tabs_box = tk.Frame(body, bg=U.BG)
        self.tabs_box.pack(fill="x")
        self.tabs = {}
        self.note = tk.Label(body, text="불러오는 중…", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS, anchor="w",
                             justify="left")
        self.note.pack(fill="x", pady=(6, 4))
        U.wrap_to_width(self.note)
        bar = tk.Frame(body, bg=U.BG)
        bar.pack(fill="x", pady=(10, 0), side="bottom")
        self.close_btn = U.ghost_button(bar, "닫기", self.close, height=32)
        self.close_btn.pack(side="right")
        self.inner, self.cv = ui_box.scroll_body(body)
        ui_box.fit(self.win, hi=U.h(700), scroll=(self.cv, self.inner))
        run_async(self.root, lambda: self.app.api.olympics_board(event), self._got)

    def _fit(self):
        ui_box.fit(self.win, hi=U.h(700), scroll=(self.cv, self.inner), keep_pos=self.win.winfo_ismapped())

    def _got(self, r, err):
        if not self.alive():
            return
        if err:
            self.note.configure(text=_err(err))
            return self._fit()
        self.r = r or {}
        for w in self.tabs_box.winfo_children():
            w.destroy()
        self.tabs = {}
        keys = [(x["no"], x["kr"]) for x in self.r.get("rounds") or []]
        if not self.r.get("hidden"):
            keys.append(("final", "최종 순위"))
        for key, text in keys:
            b = tk.Label(self.tabs_box, text=text, bg=U.BG4, fg=U.FG, font=U.FONT_XS, padx=7, pady=2, cursor="hand2")
            b.pack(side="left", padx=(0, 3))
            b.bind("<Button-1>", lambda _e, k=key: self._tab(k))
            self.tabs[key] = b
        if not keys:
            self.note.configure(text="아직 결과가 공개되지 않았어요 (라운드마다 다음 라운드 중계가 시작하면 나와요)."
                                if self.r.get("total") else "아직 경기 전이에요.")
            return self._fit()
        self._tab(keys[-1][0])

    def _tab(self, key):
        self.view = key
        for k, b in self.tabs.items():
            on = k == key
            b.configure(bg=U.ACCENT if on else U.BG4, fg=U.ACCENT_DARK if on else U.FG)
        for w in self.inner.winfo_children():
            w.destroy()
        r = self.r or {}
        if key == "final":
            me = r.get("me")
            self.note.configure(text="%d명 참가%s" % (r.get("total", 0), (" · 내 순위 %d위" % me["rank"]) if me else ""))
            rows = list(r.get("standings") or [])
            if me and not any(x.get("mine") for x in rows):
                rows += [None, me]
            for x in rows:
                if x is None:
                    tk.Label(self.inner, text="⋯", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S).pack(anchor="w")
                    continue
                self._line(x["rank"], "%s의 %s" % (x["user"], x["pokemon"]["name"]), "%s%s" % (
                    x.get("text") or "", ("  (%s)" % x["reached"]) if x.get("reached") else ""), x.get("mine"))
            return self._fit()
        rnd = next((x for x in r.get("rounds") or [] if x["no"] == key), None)
        if rnd is None:
            return self._fit()
        self.note.configure(text=rnd.get("note") or "")
        for h in rnd.get("heats") or []:
            head = tk.Frame(self.inner, bg=U.BG)
            head.pack(fill="x", pady=(6, 1))
            title = ("%d조" % h["no"]) if len(rnd["heats"]) > 1 else rnd["kr"]
            if rnd.get("format") == "match":
                title = "%d경기" % h["no"] if len(rnd["heats"]) > 1 else rnd["kr"]
            tk.Label(head, text=title, bg=U.BG, fg=U.ACCENT_TEXT, font=U.FONT_B).pack(side="left")
            v = tk.Label(head, text="다시 보기", bg=U.BG, fg=U.INFO, font=U.FONT_XS, cursor="hand2")
            v.pack(side="left", padx=(8, 0))
            v.bind("<Button-1>", lambda _e, rn=rnd["no"], hn=h["no"]: self._watch(rn, hn))
            for x in h.get("rows") or []:
                q = ("  " + x["q"]) if x.get("q") else ""
                self._line(x["place"], "%s의 %s" % (x["user"], x["pokemon"]["name"]), "%s%s" % (x.get("text") or "", q),
                           x.get("mine"))
        self._fit()

    def _line(self, rank, who, text, mine):
        bg = U.BG4 if mine else U.BG2
        row = tk.Frame(self.inner, bg=bg)
        row.pack(fill="x", pady=1, padx=(0, 4))
        medal = {1: U.ACCENT, 2: "#d6dbe6", 3: "#d09a6a"}.get(rank, U.FG_DIM)
        tk.Label(row, text="%d" % rank, bg=bg, fg=medal, font=U.FONT_B, width=4, anchor="e").pack(side="left")
        tk.Label(row, text=who, bg=bg, fg=U.ACCENT_TEXT if mine else U.FG, font=U.FONT_S).pack(side="left", padx=(8, 0))
        tk.Label(row, text=text, bg=bg, fg=U.FG, font=U.FONT_B).pack(side="right", padx=(0, 8))

    def _watch(self, rnd, heat_no):
        o = getattr(self.app, "olympics", None)
        if o is None:
            return

        def back(_h, err):
            if err and self.alive():
                self.note.configure(text=err)
                self._fit()
        o.replay(self.event, rnd, heat_no, back)


# ---------------------------------------------------------------- 결과 카드
class ResultCard(object):
    """중계가 끝나면 경기장 위에 잠깐: 기록 · 조 순위 · 진출 · [다시 보기] [이벤트 탭] [닫기]."""

    def __init__(self, app, heat, result, ms=15000):
        self.app, self.root = app, app.root
        self.dead = False
        mine = next((e for e in heat.get("entrants") or [] if e.get("mine")), None) or {}
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.configure(bg=U.ACCENT)
        box = tk.Frame(self.win, bg=U.BG2)
        box.pack(padx=2, pady=2)
        where = heat.get("roundKr") or ""
        if (heat.get("heats") or 1) > 1:
            where += " %d조" % (heat.get("heat") or 1)
        tk.Label(box, text="%s · %s" % (O.EV[heat["event"]]["kr"], where.strip() or "%d조" % (heat.get("heat") or 1)),
                 bg=U.BG2, fg=U.FG_DIM, font=U.FONT_XS).pack(anchor="w", padx=12, pady=(8, 0))
        tk.Label(box, text="%s  %s" % ((mine.get("pokemon") or {}).get("name", "?"), result.get("text") or "-"),
                 bg=U.BG2, fg=U.ACCENT_TEXT, font=U.FONT_H).pack(anchor="w", padx=12)
        bits = []
        if result.get("heatRank"):
            from .olympics_show import place_text
            bits.append(place_text(heat, result["heatRank"]) if heat.get("roundKr")
                        else "조 %d위" % result["heatRank"])
        if mine.get("q"):
            bits.append("다음 라운드 진출 (%s)" % mine["q"])
        if not heat.get("medal"):
            bits.append("전체 결과는 이벤트 탭에")
        tk.Label(box, text="  ·  ".join(bits), bg=U.BG2, fg=U.FG, font=U.FONT_S).pack(anchor="w", padx=12)
        bar = tk.Frame(box, bg=U.BG2)
        bar.pack(fill="x", padx=12, pady=(6, 10))
        for text, fn in (("다시 보기", self._again), ("이벤트 탭", self._open), ("닫기", self.close)):
            b = tk.Label(bar, text=text, bg=U.BG3, fg=U.FG, font=U.FONT_XS, padx=8, pady=2, cursor="hand2")
            b.pack(side="left", padx=(0, 6))
            b.bind("<Button-1>", lambda _e, f=fn: f())
        self.where = (heat.get("event"), heat.get("roundNo"), heat.get("heat"))
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
        ev, rn, hn = self.where
        self.close()
        o = getattr(self.app, "olympics", None)
        if o is not None and ev and rn and hn:
            o.replay(ev, rn, hn)

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
