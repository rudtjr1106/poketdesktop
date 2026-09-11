# -*- coding: utf-8 -*-
"""대전 — 받은 판과 지난 전적을 목록으로.

지금까지는 트레이의 "받은 대전 보기" 가 **가장 최근 한 판**만 틀어 줬다.
여러 판이 밀려 있으면 나머지는 볼 방법이 없었고, 진 판을 다시 붙고
싶어도 친구 창으로 가서 이름을 찾아야 했다.

여기서는 목록으로 보여준다.
  · 안 본 판이 위에 모인다 (금색 점)
  · 아무 판이나 골라서 다시 볼 수 있다
  · **진 판 옆에 "다시 붙기"** 가 뜬다

다시 붙을 수 있는지는 **서버가 판정해서 보내준다**. 화면에서 조건을
다시 따지면(30분 쿨다운·하루 상한·차단) 서버 판정과 어긋난다.
"""
import datetime
import tkinter as tk

from . import ui_common as U
from . import ui_loading
from .ui_box import confirm
from .ui_common import run_async

W, H = 900, 660

# 목록을 나눠 만드는 크기(U.Chunked). 쉰 판을 한 번에 만들면 그동안 창이
# 통째로 멈추고 바탕화면 도트도 같이 선다. 첫 묶음은 첫 화면(카드 일곱 장
# 남짓)이면 된다. 묶음마다 보이는 화면을 한 번씩 다시 그리는 값이 붙어서,
# 너무 잘게 끊으면 다 만드는 데 오래 걸린다 - 네 장씩이 한 번에 멈추는
# 시간(0.13초, 여덟 장씩은 0.16초)과 전체 시간의 중간이었다.
FIRST_ROWS = 8
CHUNK_ROWS = 4

RESULT = {"win": ("승", U.GOOD), "lose": ("패", U.RED), "draw": ("무", U.FG_DIM)}
KIND = {"random": "랜덤", "friend": "친구"}


def _when(s):
    """2026-09-02T03:22:07+00:00 -> 09-02 12:22 (내 PC 시간대로).

    서버는 UTC 로 보낸다. 예전에는 문자열을 그대로 잘라서 보여줬는데,
    그러면 한국에서는 실제 시각보다 9시간 이르게 나온다 - 새벽 배틀이
    낮 시간으로 찍히는 식이라, 언제 진 판인지 헷갈리게 만든다.

    astimezone() 은 이 PC 의 시간대로 바꾼다. "+9시간" 을 박아 두는 대신
    이렇게 하면, 어차피 이 게임의 사용자는 전부 한국이라 결과는 같으면서
    시간대를 하드코딩하지 않아도 된다.
    """
    if not s:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(s).astimezone()
    except ValueError:
        return s.replace("T", " ")[:16]      # 모르는 형식이면 예전처럼 대강
    return dt.strftime("%m-%d %H:%M")


class PvpWindow(object):

    def __init__(self, app, parent=None):
        self.app = app
        self.root = app.root
        self.rows = []
        self.busy = False
        self._job = None          # 목록을 나눠 만드는 일 (U.Chunked)
        self.unseen = set()

        self.win = U.panel(parent, self.root, "포스크탑 — 대전",
                           W, H, 700, 520, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            U.install_wheel(self.win)

        self._header()
        self._body()
        self._status()
        self.reload()

    # ---------------- 머리 ----------------
    def _header(self):
        h = tk.Frame(self.win, bg=U.BG2, height=U.h(62))
        h.pack(fill="x")
        h.pack_propagate(False)
        inner = tk.Frame(h, bg=U.BG2)
        inner.pack(fill="both", expand=True, padx=16)
        tk.Label(inner, text="대전", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, U.pt(15))).pack(side="left", pady=17)
        self.sub = tk.Label(inner, text="", bg=U.BG2, fg=U.FG_DIM,
                            font=U.FONT_XS)
        self.sub.pack(side="left", padx=(12, 0))

        U.ghost_button(inner, "새로고침", self.reload,
                       height=32).pack(side="right", pady=15)
        U.ghost_button(inner, "기록 지우기", self._clear,
                       height=32).pack(side="right", padx=(0, 8), pady=15)
        U.ghost_button(inner, "랜덤 배틀", self._random,
                       height=32).pack(side="right", padx=(0, 8), pady=15)
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

    def _body(self):
        wrap = tk.Frame(self.win, bg=U.BG)
        wrap.pack(fill="both", expand=True, padx=16, pady=(8, 0))
        cv = tk.Canvas(wrap, bg=U.BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=cv.yview)
        self.list = tk.Frame(cv, bg=U.BG)
        self._win_id = cv.create_window((0, 0), window=self.list, anchor="nw")
        # 스크롤 영역은 U.scroll_fitter 가 **몰아서 한 번** 맞춘다. 예전에는
        # <Configure> 마다 update_idletasks 로 밀린 배치를 억지로 끝내고
        # 쟀는데, 그게 또 <Configure> 를 불러 제 발로 되돌아왔다 - 카드를
        # 담을 때마다 앱 전체를 다시 배치했다. 내용이 짧으면 스크롤할 게
        # 없게 하는 규칙은 그대로다.
        self.fit = U.scroll_fitter(cv, self.list, self._win_id)
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        U.scrollable(cv, 120)
        self.cv = cv

    def _status(self):
        self.status = U.status_line(self.win, "")
        self.status.pack(fill="x", padx=16, pady=(6, 12))

    def say(self, text, color=U.GOOD):
        U.set_status(self.status, text, color)

    # ---------------- 자료 ----------------
    def reload(self):
        if self.busy:
            return
        self.busy = True
        wait = ui_loading.Overlay(self.win, "대전 기록을 불러오는 중")

        def work():
            api = self.app.api
            # 안 본 판과 전적을 같이 받는다. 전적에는 아직 안 본 것이
            # 무엇인지가 없어서 둘을 맞춰야 금색 점을 찍을 수 있다.
            return api.pvp_records(50), api.pvp_pending()

        def done(r, err):
            self.busy = False
            if err:
                wait.close()
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            try:
                recs, pend = r
                self.rows = recs.get("records") or []
                self.summary = recs.get("summary") or {}
                self.fight = (pend or {}).get("fight") or {}
                self.unseen = set(m.get("id") for m in (pend or {}).get("matches") or [])
                self.draw()
            finally:
                # **첫 화면을 그린 뒤에 걷는다.** 맨 앞에서 걷으면 카드를
                # 만드는 동안 아무 표시 없이 창이 멈춘 것처럼 보였다. 첫
                # 묶음은 이미 만들었으니 그것이 그려진 뒤(idle)에 걷는다.
                # 그리다 터져도 걷는다 - 덮개가 새로고침 단추까지 가린다.
                try:
                    self.root.after_idle(wait.close)
                except tk.TclError:
                    wait.close()
        run_async(self.root, work, done)

    # ---------------- 그리기 ----------------
    def draw(self):
        keep = self._scroll_top()
        if self._job is not None:
            self._job.cancel()      # 옛 목록의 남은 카드가 새 목록 뒤에 붙지 않게
            self._job = None
        for w in self.list.winfo_children():
            w.destroy()
        # 카드는 위에서부터 나눠 만든다. 맨 위로 올려 둬야 먼저 만든 묶음이
        # 곧 보이는 화면이다 - 아래를 보던 채로 두면 아직 안 만든 자리가
        # 빈 채로 먼저 보인다. 다 만들면 보던 자리로 돌려놓는다 (_back_to).
        self.cv.yview_moveto(0)
        s = self.summary
        left = self.fight.get("left")
        bits = ["%d전 %d승 %d패 %d무" % (s.get("games", 0), s.get("wins", 0),
                                      s.get("losses", 0), s.get("draws", 0))]
        if s.get("ranked"):
            bits.append("점수 %d" % s.get("rating", 0))
        if left is not None:
            bits.append("오늘 %d판 더 걸 수 있음" % left)
        self.sub.configure(text="  ·  ".join(bits))

        # **이기면 얼마를 받는지 적어 준다.** 상금이 있다는 것을
        # 화면 어디서도 말해 주지 않아서, 붙어 보고 돈이 늘어야
        # 알았다. 값은 서버가 실어 보낸다(pvp.summary 의 winReward) -
        # 여기 숫자를 박아 두면 서버에서 바꿨을 때 거짓말이 된다.
        pay = s.get("winReward")
        cap = s.get("dailyCap")
        if pay:
            line = ("내가 건 랜덤 배틀에서 이기면 %s원을 받습니다. "
                    "지면 0원, 걸려온 판은 상금이 없습니다."
                    % format(int(pay), ","))
            if cap:
                line += "  하루 %s원까지" % format(int(cap), ",")
                got = int(s.get("earnedToday") or 0)
                if got:
                    line += " (오늘 %s원 받음)" % format(got, ",")
                line += "."
            tk.Label(self.list, text=line, bg=U.BG, fg=U.FG_FAINT,
                     font=U.FONT_XS, anchor="w", justify="left",
                     wraplength=W - 80).pack(fill="x", pady=(0, 8))

        if not self.rows:
            tk.Label(self.list, text="아직 대전 기록이 없습니다.\n"
                                     "랜덤 배틀로 한 판 붙어보세요.",
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S,
                     justify="center").pack(pady=48)
            return self.fit.schedule()

        # 안 본 판을 위로. 그 안에서는 최신순(서버가 이미 그 순서로 준다).
        rows = sorted(self.rows,
                      key=lambda r: 0 if r.get("matchId") in self.unseen else 1)
        self._job = U.Chunked(self.win, rows, self._card,
                              first=FIRST_ROWS, size=CHUNK_ROWS,
                              on_done=lambda: self._back_to(keep))
        self.fit.schedule()

    def _scroll_top(self):
        try:
            return self.cv.yview()[0]
        except tk.TclError:
            return 0.0

    def _back_to(self, top):
        """다 그린 뒤 보던 자리로 돌아간다.

        다시 불러오기는 누르지 않아도 온다 - '다시 보기' 1.2초 뒤, 붙은 뒤
        2.5초 뒤. 나눠 그리려고 맨 위로 올린 채로 두면, 아래 기록을 보다가
        한 번 누를 때마다 목록이 맨 위로 튄다. 처음 열 때는 top 이 0 이라
        아무것도 안 한다.
        """
        if top <= 0:
            return
        try:
            self.fit.fit_now()
            self.cv.yview_moveto(top)
        except tk.TclError:
            pass

    def _card(self, r):
        new = r.get("matchId") in self.unseen
        box = tk.Frame(self.list, bg=U.BG2 if new else "#161b28",
                       highlightthickness=2,
                       highlightbackground=U.ACCENT if new else U.LINE)
        box.pack(fill="x", pady=(0, 7))
        inner = tk.Frame(box, bg=box["bg"])
        inner.pack(fill="x", padx=13, pady=10)

        # 왼쪽: 승패 · 상대 · 언제
        left = tk.Frame(inner, bg=box["bg"])
        left.pack(side="left", fill="x", expand=True)
        top = tk.Frame(left, bg=box["bg"])
        top.pack(fill="x")
        mark, color = RESULT.get(r.get("result"), ("?", U.FG_DIM))
        tk.Label(top, text=mark, bg=color, fg="#14141a",
                 font=(U.FAMILY_BLACK, U.pt(11)), width=3).pack(side="left")
        tk.Label(top, text=r.get("foe") or "?", bg=box["bg"], fg=U.FG,
                 font=U.FONT_B).pack(side="left", padx=(9, 0))
        if new:
            tk.Label(top, text="NEW", bg=box["bg"], fg=U.ACCENT,
                     font=U.FONT_XS).pack(side="left", padx=(8, 0))
        # 걸려온 판은 점수·승패·돈에 안 들어간다. 목록에서도 그렇게
        # 보여야 "왜 이겼는데 점수가 그대로지" 가 안 된다.
        if not r.get("started", True):
            tk.Label(top, text="걸려온 판", bg=box["bg"], fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(side="left", padx=(8, 0))

        bits = [KIND.get(r.get("kind"), r.get("kind") or ""),
                _when(r.get("at")),
                "%d턴" % (r.get("turns") or 0),
                "남은 %d : %d" % (r.get("myLeft") or 0, r.get("foeLeft") or 0)]
        d = r.get("delta") or 0
        if d:
            bits.append("점수 %+d" % d)
        if r.get("reward"):
            bits.append("%s원" % format(r["reward"], ","))
        if not r.get("started", True):
            bits.append("점수·승패에 안 들어감")
        tk.Label(left, text="  ·  ".join(b for b in bits if b), bg=box["bg"],
                 fg=U.FG_FAINT, font=U.FONT_XS).pack(anchor="w", pady=(4, 0))

        # 오른쪽: 단추
        right = tk.Frame(inner, bg=box["bg"])
        right.pack(side="right")
        if r.get("matchId"):
            U.ghost_button(right, "다시 보기",
                           lambda m=r["matchId"]: self._watch(m),
                           height=30).pack(side="right", padx=(6, 0))
        # 진 판에는 "복수", 그 밖에는 "다시 붙기". 하는 일은 같다.
        if r.get("canFight"):
            label = "복수하기" if r.get("result") == "lose" else "다시 붙기"
            U.ghost_button(right, label,
                           lambda u=r["foeId"]: self._fight(u),
                           height=30).pack(side="right")
        elif r.get("whyNot"):
            tk.Label(right, text=r["whyNot"][:22], bg=box["bg"],
                     fg=U.FG_FAINT, font=U.FONT_XS).pack(side="right")

    # ---------------- 동작 ----------------
    def _watch(self, mid):
        self.app.watch_match(mid)
        # 본 판은 더 이상 새 것이 아니다. 목록을 다시 받아 점을 지운다.
        self.root.after(1200, self.reload)

    def _fight(self, uid):
        if not uid:
            return
        self.say("도전하는 중...")
        self.app.pvp_challenge(uid)
        self.root.after(2500, self.reload)

    def _random(self):
        self.say("상대를 찾는 중...")
        self.app.pvp_random()
        self.root.after(2500, self.reload)

    def _clear(self):
        """전적을 통째로 지운다.

        **점수와 승패는 그대로 남는다.** 이건 목록일 뿐이고 점수는 따로
        센다 - 지운다고 등수가 오르면 진 판만 골라 지우는 사람이 나온다.
        묻는 창에 그 말을 적어 둔다.
        """
        if not self.rows:
            return self.say("지울 기록이 없습니다.", U.FG_DIM)
        if not confirm(self.root, "기록 지우기",
                       "대전 기록 %d줄을 지웁니다.\n\n"
                       "점수와 승패는 그대로 남습니다. 목록만 비워집니다."
                       % len(self.rows), ok_text="지우기"):
            return
        self.say("지우는 중...")

        def done(r, err):
            if err:
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            self.say("%d줄을 지웠습니다." % (r or {}).get("removed", 0))
            self.reload()
        run_async(self.root, self.app.api.pvp_clear_records, done)

    # ---------------- 끝 ----------------
    def focus(self):
        if U.is_embedded(self.win):
            return
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except Exception:                                   # noqa: BLE001
            pass

    def close(self):
        if self._job is not None:
            self._job.cancel()          # 남은 카드를 닫힌 창에 만들지 않게
            self._job = None
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        if getattr(self.app, "pvp_window", None) is self:
            self.app.pvp_window = None
