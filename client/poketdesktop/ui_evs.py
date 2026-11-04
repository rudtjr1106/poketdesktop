# -*- coding: utf-8 -*-
"""노력치 조정 창 (2.1.3, 게시판 #450 핑꾸말미잘 '노력치 간편화').

능력마다 맞출 값을 끌거나(막대) 적어서(칸) 고르면, 서버가 **도구를 하나씩 쓸 때와 똑같은 도구 · 값**으로
계획을 짜 보여 주고(dry), '적용' 을 누르면 한 번에 맞춘다 (POST /api/pokemon/{pid}/evs).

    HP        지금 252   [=========|====]  [252]  -
    공격      지금   0   [==|===========]  [ 25]  +25
    ...
    합계 277 / 510
    가방에서: 타우린 1개 · 근력깃털 13개
    사서 쓸 것: 근력깃털 2개 (2,000원)  ·  가진 돈 30,000원
                                         [되돌리기] [닫기] [적용]

  · 막대는 합계 510 을 넘게 끌리지 않는다 (넘는 만큼 그 자리에서 멈춘다).
  · 칸에 적은 값은 고치지 않는다 - 0~252 가 아니거나 합계가 510 을 넘으면 빨갛게 알리고 '적용' 을 잠근다
    (적는 도중의 값을 멋대로 바꾸면 무엇을 적었는지 헷갈린다).
  · 계획은 고친 뒤 잠깐 멈추면 묻는다 (PLAN_MS) - 끄는 동안 요청이 쌓이지 않게.
  · 모자란 도구가 있으면 **사기 전에 묻는다** ('부족한 도구 N개를 X원에 사서 쓸까요?'). 물어본 값을 서버에
    같이 보낸다(cost) - 그사이 가방이 바뀌어 값이 달라졌으면 서버가 쓰지 않는다.
"""
import tkinter as tk

from common import pokelogic as P
from common.korean import natural

from . import ui_box as BX
from . import ui_common as U
from . import ui_loading

STAT_MAX = 252
TOTAL_MAX = P.EV_TOTAL_MAX
PLAN_MS = 300               # 고친 뒤 이만큼 멈추면 계획을 묻는다
W = 480                     # 창 폭 (내용이 더 넓으면 잰 만큼)
SLIDER = 200                # 막대 길이 (글자가 아니라서 글자 크기로 늘리지 않는다)
# 접는 글의 처음 폭. 안 주면 긴 안내 글이 한 줄로 재여 창 폭을 끝없이 넓힌다 - 자리가 잡히면 실제 폭으로 다시 접는다
WRAP = W - 2 * 18 - 24


def won(n):
    return "%s원" % format(int(n or 0), ",")


def plan_text(r):
    """서버 계획(dry 답)을 사람 말로. (글, 빛깔)."""
    plan = r.get("plan") or []
    if not plan:
        return "바꿀 노력치를 고르세요.", U.FG_FAINT
    bag = ["%s %d개" % (x.get("kr") or x["item"], x["owned"]) for x in plan if x.get("owned")]
    buy = ["%s %d개" % (x.get("kr") or x["item"], x["buy"]) for x in plan if x.get("buy")]
    lines = ["가방에서: %s" % " · ".join(bag)] if bag else []
    money = int(r.get("money") or 0)
    if buy:
        lines.append("사서 쓸 것: %s  (모두 %s)" % (" · ".join(buy), won(r.get("cost"))))
        if r.get("buyable") is False:
            lines.append("상점에서 팔지 않는 도구가 모자랍니다.")
            return "\n".join(lines), U.DANGER
        if not r.get("affordable"):
            lines.append("가진 돈 %s - 돈이 모자랍니다." % won(money))
            return "\n".join(lines), U.DANGER
        lines.append("가진 돈 %s → 쓰고 나면 %s" % (won(money), won(money - int(r.get("cost") or 0))))
    else:
        lines.append("살 것 없음 - 가방의 도구만 씁니다.")
    return "\n".join(lines), U.FG


def open_editor(app, parent, mon, on_done=None):
    """창을 연다. 다른 포켓몬의 창이 떠 있으면 닫고 연다 (한 번에 하나)."""
    old = getattr(app, "ev_editor", None)
    if old is not None:
        old.close()
    app.ev_editor = EvEditor(app, parent, mon, on_done)
    return app.ev_editor


class EvEditor(object):

    def __init__(self, app, parent, mon, on_done=None):
        self.app = app
        self.root = getattr(app, "root", None) or parent
        self.mon = mon
        self.on_done = on_done
        evs = (mon.get("info") or {}).get("evs") or mon.get("evs") or {}
        self.cur = dict((k, max(0, min(STAT_MAX, int(evs.get(k, 0) or 0)))) for k, _l in BX.STAT_ROWS)
        self.want = dict(self.cur)
        self.bad = set()            # 칸에 0~252 정수가 아닌 것을 적은 능력
        self.plan = None            # 마지막 계획 (dry 답)
        self.plan_for = None        # 그 계획이 무엇을 위한 것인지 (맞출 값)
        self._seq = 0
        self._job = None
        self._quiet = False         # 막대 · 칸을 코드로 맞추는 동안 (서로 다시 부르지 않게)
        self.busy = False
        self.closed = False
        self._wait = None
        self._build(parent)
        self._changed()
        self._fit()

    # ---------------- 짓기 ----------------
    def _build(self, parent):
        name = (self.mon.get("info") or {}).get("name") or self.mon.get("nickname") or self.mon.get("species", "")
        self.win, body = BX._shell(parent, "노력치 조정", W, 520)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.bind("<Escape>", lambda _e: self.close())
        # 포켓몬 관리 창을 닫으면 이 창도 같이 부서진다 (그 창의 아이) - 늦게 온 답이 부서진 위젯을 만지지 않게
        self.win.bind("<Destroy>", lambda e: e.widget is self.win and self._gone(), add="+")
        # 단추 줄과 알림 줄을 먼저 아래에 붙인다 - 굴러가는 칸이 창을 다 차지해도 잘리지 않게.
        row = tk.Frame(body, bg=U.BG)
        row.pack(side="bottom", fill="x", pady=(10, 0))
        self.btn_apply = U.PushButton(row, "적용", self.apply, height=34, font=U.FONT_B)
        self.btn_apply.pack(side="right")
        U.ghost_button(row, "닫기", self.close, height=34).pack(side="right", padx=(0, 8))
        self.btn_reset = U.ghost_button(row, "되돌리기", self.reset, height=34)
        self.btn_reset.pack(side="left")
        self.say_lb = tk.Label(body, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS, anchor="w", justify="left",
                               wraplength=WRAP)
        self.say_lb.pack(side="bottom", fill="x", pady=(8, 0))
        U.wrap_to_width(self.say_lb)

        self.inner, self.cv = BX.scroll_body(body)
        f = self.inner
        tk.Label(f, text="%s  ·  Lv.%d" % (name, int(self.mon.get("level") or 0)), bg=U.BG, fg=U.ACCENT_TEXT,
                 font=U.FONT_B, anchor="w").pack(fill="x")
        note = tk.Label(f, text=natural("막대를 끌거나 숫자를 적어 맞추세요. 능력마다 0~%d, 합계 %d까지. "
                                        "도구를 하나씩 쓸 때와 같은 도구 · 같은 값이 듭니다."
                                        % (STAT_MAX, TOTAL_MAX)),
                        bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left", wraplength=WRAP)
        note.pack(fill="x", pady=(2, 10))
        U.wrap_to_width(note)

        grid = tk.Frame(f, bg=U.BG)
        grid.pack(fill="x")
        self.now_lb, self.scales, self.vars, self.entries, self.diff_lb = {}, {}, {}, {}, {}
        for i, (k, label) in enumerate(BX.STAT_ROWS):
            tk.Label(grid, text=label, bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, anchor="w").grid(
                row=i, column=0, sticky="w", pady=3)
            now = tk.Label(grid, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="e")
            now.grid(row=i, column=1, sticky="e", padx=(8, 10))
            # 손잡이는 금색 (설정 창의 막대와 같다 - 손잡이 색이 bg 다). 홈은 가는 테로 둘러 밝은 테마에서도 보이게
            sc = tk.Scale(grid, from_=0, to=STAT_MAX, resolution=1, orient="horizontal", showvalue=0,
                          length=SLIDER, sliderlength=U.h(16), width=U.h(12), bd=0, highlightthickness=1,
                          highlightbackground=U.LINE, relief="flat", sliderrelief="flat", bg=U.ACCENT,
                          troughcolor=U.INK, activebackground=U.SHINY, cursor="hand2",
                          command=lambda v, key=k: self._on_scale(key, v))
            sc.set(self.cur[k])
            sc.grid(row=i, column=2, sticky="we")
            var = tk.StringVar(value=str(self.cur[k]))
            box = tk.Frame(grid, bg=U.INK, highlightthickness=2, highlightbackground=U.LINE,
                           highlightcolor=U.ACCENT, bd=0)
            e = tk.Entry(box, textvariable=var, width=4, bg=U.INK, fg=U.FG, insertbackground=U.ACCENT,
                         relief="flat", bd=0, highlightthickness=0, font=U.FONT, justify="right")
            e.pack(padx=6, pady=2)
            box.grid(row=i, column=3, padx=(10, 0))
            var.trace_add("write", lambda *_a, key=k: self._on_entry(key))
            diff = tk.Label(grid, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", width=5)
            diff.grid(row=i, column=4, sticky="w", padx=(8, 0))
            self.now_lb[k], self.scales[k], self.vars[k], self.entries[k], self.diff_lb[k] = now, sc, var, box, diff
        grid.grid_columnconfigure(2, weight=1)

        self.total_lb = tk.Label(f, text="", bg=U.BG, fg=U.FG, font=U.FONT_B, anchor="w")
        self.total_lb.pack(fill="x", pady=(10, 6))
        pb = tk.Frame(f, bg=U.BG2, highlightthickness=1, highlightbackground=U.LINE)
        pb.pack(fill="x")
        self.plan_lb = tk.Label(pb, text="", bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left",
                                wraplength=WRAP - 22)
        self.plan_lb.pack(fill="x", padx=10, pady=8)
        U.wrap_to_width(self.plan_lb)
        self._paint_now()

    def _fit(self, keep=False):
        """창을 내용에 맞춘다 - 폭은 줄이 바라는 만큼(글자를 줄이지 않는다), 높이는 내용만큼, 화면을 넘으면 안쪽이 굴러간다.

        keep: 이미 떠 있다 (계획 글이 길어졌다). 모자랄 때만 늘린다 - 막대를 끄는 동안 창이 늘었다 줄었다 하지 않게.
        """
        try:
            self.win.update_idletasks()
            bar = 18                                        # 굴러가는 막대가 떠도 줄이 안 눌리게
            need = self.inner.winfo_reqwidth() + 2 * 18 + 4 + bar
            self.win.shell_w = max(W, need)
            lo = self.win.winfo_height() if keep else 0
            BX.fit(self.win, lo=lo, hi=U.work_size(self.win)[1], scroll=(self.cv, self.inner), keep_pos=keep)
        except tk.TclError:
            pass

    # ---------------- 칠하기 ----------------
    def _paint_now(self):
        for k, _l in BX.STAT_ROWS:
            self.now_lb[k].configure(text="지금 %d" % self.cur[k])

    def _valid(self):
        return not self.bad and sum(self.want.values()) <= TOTAL_MAX

    def _changed(self):
        """값이 바뀌었다: 줄마다 차이 · 합계 · 단추를 칠하고, 바뀐 것이 있으면 계획을 묻는다 (잠깐 멈춘 뒤)."""
        if self.closed:
            return
        for k, _l in BX.STAT_ROWS:
            box = self.entries[k]
            if k in self.bad:
                self.diff_lb[k].configure(text="0~%d" % STAT_MAX, fg=U.DANGER)
                box.configure(highlightbackground=U.DANGER)
                continue
            box.configure(highlightbackground=U.LINE)
            d = self.want[k] - self.cur[k]
            self.diff_lb[k].configure(text=("+%d" % d) if d > 0 else ("−%d" % -d if d < 0 else ""),
                                      fg=U.GOOD if d > 0 else U.DANGER)
        total = sum(self.want.values())
        over = total > TOTAL_MAX
        self.total_lb.configure(text="합계 %d / %d%s" % (total, TOTAL_MAX, "  - %d 넘었습니다" % (total - TOTAL_MAX)
                                                      if over else ""),
                                fg=U.DANGER if over else U.FG)
        self._cancel_plan()
        self.plan = None
        self._seq += 1                  # 이미 나간 계획 요청의 답은 옛 값의 것이다 - 오면 버린다
        if self.bad:
            self._show_plan("능력마다 0~%d 사이의 숫자를 적어 주세요." % STAT_MAX, U.DANGER)
        elif over:
            self._show_plan("합계가 %d을(를) 넘습니다. 다른 능력을 줄여 주세요." % TOTAL_MAX, U.DANGER)
        elif self.want == self.cur:
            self._show_plan("바꿀 노력치를 고르세요.", U.FG_FAINT)
        else:
            self._show_plan("필요한 도구를 세는 중...", U.FG_FAINT)
            try:
                self._job = self.win.after(PLAN_MS, self._ask_plan)
            except tk.TclError:
                self._job = None
        self._buttons()

    def _buttons(self):
        ready = (not self.busy and self._valid() and self.want != self.cur and self.plan is not None
                 and self.plan_for == self.want and bool(self.plan.get("plan"))
                 and (not self.plan.get("buyCount") or self.plan.get("affordable")))
        self.btn_apply.configure(state="normal" if ready else "disabled")
        self.btn_reset.configure(state="normal" if (self.want != self.cur or self.bad) and not self.busy
                                 else "disabled")

    def _show_plan(self, text, color):
        self.plan_lb.configure(text=natural(text), fg=color)

    def say(self, text, color=None):
        self.say_lb.configure(text=natural(text or ""), fg=color or U.FG_DIM)

    # ---------------- 막대 · 칸 ----------------
    def _on_scale(self, k, v):
        if self._quiet or self.closed:
            return
        v = int(round(float(v)))
        if v == self.want[k] and k not in self.bad:
            return                                      # 칸에서 맞춘 값이 돌아온 것 (아래 _on_entry)
        room = TOTAL_MAX - sum(x for s, x in self.want.items() if s != k)
        if v > room:                                    # 합계 510 을 넘게는 안 끌린다
            v = max(0, room)
            self._quiet = True
            try:
                self.scales[k].set(v)
            finally:
                self._quiet = False
        self.want[k] = v
        self.bad.discard(k)
        self._quiet = True
        try:
            self.vars[k].set(str(v))
        finally:
            self._quiet = False
        self._changed()

    def _on_entry(self, k):
        if self._quiet or self.closed:
            return
        text = self.vars[k].get().strip()
        if not text.isdigit() or int(text) > STAT_MAX:
            self.bad.add(k)
            return self._changed()
        v = int(text)
        self.bad.discard(k)
        if v != self.want[k]:
            self.want[k] = v
            self._quiet = True
            try:
                self.scales[k].set(v)
            finally:
                self._quiet = False
        self._changed()

    def set_value(self, k, v):
        """한 능력의 값을 코드로 맞춘다 (되돌리기 · 적용 뒤)."""
        self._quiet = True
        try:
            self.scales[k].set(v)
            self.vars[k].set(str(v))
        finally:
            self._quiet = False
        self.want[k] = v
        self.bad.discard(k)

    def reset(self):
        for k, _l in BX.STAT_ROWS:
            self.set_value(k, self.cur[k])
        self.say("")
        self._changed()

    # ---------------- 서버 ----------------
    def _cancel_plan(self):
        if self._job is not None:
            try:
                self.win.after_cancel(self._job)
            except (tk.TclError, ValueError):
                pass
            self._job = None

    def _ask_plan(self, then=None):
        """dry 로 계획을 묻는다. 늦게 온 옛 답은 버린다 (그사이 값을 또 바꿨다)."""
        self._job = None
        if self.closed or not self._valid() or self.want == self.cur:
            return
        self._seq += 1
        seq, want, pid, api = self._seq, dict(self.want), self.mon["id"], self.app.api

        def done(r, err):
            if self.closed or seq != self._seq:
                return
            try:
                if err:
                    self.plan = None
                    self._show_plan(_err(err), U.DANGER)
                else:
                    self.plan, self.plan_for = r or {}, want
                    self._show_plan(*plan_text(self.plan))
                self._buttons()
                self._fit(keep=True)
            except tk.TclError:
                return
            if then is not None and not err:
                then(self.plan)
        U.run_async(self.root, lambda: api.set_evs(pid, want, dry=True), done)

    def apply(self):
        if self.busy or self.closed or not self._valid() or self.want == self.cur:
            return
        if self.plan is not None and self.plan_for == self.want:
            return self._go(self.plan)
        self._cancel_plan()
        self._ask_plan(then=self._go)                   # 아직 계획이 안 왔다 - 묻고 이어 간다

    def _go(self, plan):
        if self.closed or not plan or not plan.get("plan"):
            return
        n, cost = int(plan.get("buyCount") or 0), int(plan.get("cost") or 0)
        if n:
            if not plan.get("affordable"):
                return self.say("돈이 모자랍니다. (%s 필요)" % won(cost), U.DANGER)
            if not BX.confirm(self.win, "도구 사기", "부족한 도구 %d개를 %s에 사서 쓸까요?" % (n, won(cost)),
                              danger=False, ok_text="사서 쓰기") or self.closed:
                return
        want, pid, api = dict(self.plan_for or self.want), self.mon["id"], self.app.api
        self.busy = True
        self._buttons()
        self.say("노력치를 맞추는 중...")
        self._wait = ui_loading.Overlay(self.win, "노력치를 맞추는 중")
        U.run_async(self.root, lambda: api.set_evs(pid, want, buy=bool(n), dry=False, cost=cost), self._applied)

    def _applied(self, r, err):
        self.busy = False
        if self._wait is not None:
            try:
                self._wait.close()
            except tk.TclError:
                pass
            self._wait = None
        if not err and self.on_done is not None:
            try:
                self.on_done(r or {})                   # 창을 그사이 닫았어도 박스는 맞춘다 (이미 바뀌었다)
            except tk.TclError:
                pass
        if self.closed:
            return
        if err:
            self.say(_err(err), U.DANGER)
            self._changed()                             # 계획을 다시 묻는다 (그사이 가방 · 돈이 바뀌었을 수 있다)
            return
        r = r or {}
        evs = r.get("evs") or ((r.get("pokemon") or {}).get("info") or {}).get("evs") or self.want
        if r.get("pokemon"):
            self.mon = r["pokemon"]
        self.cur = dict((k, int(evs.get(k, 0) or 0)) for k, _l in BX.STAT_ROWS)
        for k, _l in BX.STAT_ROWS:
            self.set_value(k, self.cur[k])
        self._paint_now()
        self.say(r.get("message") or "노력치를 맞췄습니다.", U.GOOD)
        self._changed()

    def _gone(self):
        if self.closed:
            return
        self.closed = True
        self._cancel_plan()
        if getattr(self.app, "ev_editor", None) is self:
            self.app.ev_editor = None

    def close(self):
        self._gone()
        try:
            self.win.destroy()
        except tk.TclError:
            pass


def _err(err):
    msg = getattr(err, "message", None) or str(err)
    if getattr(err, "status", 0) == 404 and msg.strip().lower() == "not found":
        return "서버가 아직 이 기능을 모릅니다. 잠시 뒤에 다시 해 주세요."
    return msg
