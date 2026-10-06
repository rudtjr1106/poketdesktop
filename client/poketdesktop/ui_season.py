# -*- coding: utf-8 -*-
"""랭크 시즌 — 티어 표시, 랭크 팀 고르기, 칭호·명패 달기.

랭킹·대전·친구 창이 같은 모양의 티어 칩과 이름 색을 쓰도록 여기에 모았다.
창마다 따로 그리면 같은 '마스터볼' 이 창마다 다른 색이 된다.

규칙(티어 경계 RP, 레벨 상한, 보상)은 **서버가 보내 준 값**을 그린다.
여기에 숫자를 박아 두면 서버에서 바꿨을 때 화면이 거짓말을 한다.
"""
import tkinter as tk
from tkinter import ttk

from common.korean import natural

from . import box_filter
from . import ui_common as U
from . import ui_loading
from .ui_common import run_async

# 볼 색을 따른다. 사천왕·챔피언은 볼이 아니라서 따로 정했다.
TIER_COLOR = {
    "monster": "#e8483f",
    "super": "#4f8cff",
    "hyper": "#f5c542",
    "master": "#b57bff",
    "elite": "#ff7a59",
    "champion": "#ffd447",
}
TIER_MARK = {"elite": "♛ ", "champion": "★ "}
NONE = "-"          # 칭호·명패 창의 '달지 않기' (RewardsWindow)


def tier_chip(parent, tier, tier_kr, bg=None, big=False):
    """티어 이름을 볼 색 칩으로. 모르는 티어면 빈 칸을 만들지 않는다."""
    if not tier or not tier_kr:
        return None
    color = TIER_COLOR.get(tier, U.BG3)
    font = (U.FAMILY, U.pt(11 if big else 8), "bold")
    lb = tk.Label(parent, text=TIER_MARK.get(tier, "") + tier_kr, bg=color,
                  fg="#14141a", font=font, padx=7 if big else 5,
                  pady=2 if big else 0)
    return lb


def name_color(row, default=U.FG):
    """명패를 달았으면 그 색으로 이름을 쓴다."""
    return row.get("frameColor") or default


def title_text(row):
    return row.get("title") or ""


# ---------------------------------------------------------------- 랭크 팀
class TeamWindow(object):
    """랭크 팀을 고르는 창.

    랜덤 배틀에서 **걸 때도 걸려올 때도** 이 팀으로 싸운다. 등록하지 않으면
    바탕화면에 데리고 다니는 파티로 싸운다 - 그래서 처음 열면 지금 파티가
    골라져 있다.
    """

    def __init__(self, app, on_saved=None):
        self.app = app
        self.root = app.root
        self.on_saved = on_saved
        self.mons = []
        self.picked = []          # 고른 순서대로 포켓몬 id
        self.registered = False
        self.max = 6
        self.cap = 50
        self.rows = {}
        self.row_box = {}              # id -> 그 줄을 담은 틀 (찾기로 숨겼다 담았다 한다)
        self.visible = []              # 지금 목록에 담긴 id, 화면 순서대로
        self.restricted = set()        # 전설·환상 도감 번호
        self.restricted_max = 1

        self.win = U.panel(None, self.root, "랭크 팀", 560, 660, 460, 520,
                           self.close)
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)
        U.install_wheel(self.win)

        head = tk.Frame(self.win, bg=U.BG2, height=U.h(56))
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text="랭크 팀", bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY_BLACK, U.pt(14))).pack(side="left", padx=16)
        self.state = tk.Label(head, text="", bg=U.BG2, fg=U.FG_DIM,
                              font=U.FONT_XS)
        self.state.pack(side="left")
        tk.Frame(self.win, bg=U.LINE2, height=U.h(2)).pack(fill="x")

        self.note = tk.Label(
            self.win, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS,
            anchor="w", justify="left", wraplength=520)
        self.note.pack(fill="x", padx=16, pady=(10, 4))

        # 고른 여섯 자리
        self.slots = tk.Frame(self.win, bg=U.BG)
        self.slots.pack(fill="x", padx=16, pady=(4, 8))

        # 찾기 (1.10.0). 포켓몬이 수백 마리가 되면 레벨 순 목록을 끝까지 굴려야 했다.
        # 포켓몬 관리의 '이름 찾기' 와 같은 규칙이다 - 별명·종 이름·도감 번호를 다 본다.
        find = tk.Frame(self.win, bg=U.BG)
        find.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(find, text="포켓몬 찾기", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS).pack(side="left")
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_a: self._filter())
        self.q_box = U.entry(find, self.q, width=18)
        self.q_box.pack(side="left", padx=(8, 0))
        self.found = tk.Label(find, text="", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS)
        self.found.pack(side="left", padx=(10, 0))

        holder = tk.Frame(self.win, bg=U.BG)
        holder.pack(fill="both", expand=True, padx=16)
        self.cv = tk.Canvas(holder, bg=U.INK, highlightthickness=2,
                            highlightbackground=U.LINE, bd=0)
        sb = ttk.Scrollbar(holder, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.cv, bg=U.INK)
        self._wid = self.cv.create_window((0, 0), window=self.inner, anchor="nw")
        self.fit = U.scroll_fitter(self.cv, self.inner, self._wid)
        U.scrollable(self.cv, 60)
        self.nomatch = tk.Label(self.inner, text="", bg=U.INK, fg=U.FG_FAINT, font=U.FONT_S)

        bar = tk.Frame(self.win, bg=U.BG)
        bar.pack(fill="x", padx=16, pady=(10, 4))
        self.save_btn = U.PushButton(bar, "등록", self.save, height=34,
                                     font=U.FONT_B)
        self.save_btn.pack(side="right")
        U.ghost_button(bar, "바탕화면 파티로 채우기", self.fill_party,
                       height=34).pack(side="left")
        U.ghost_button(bar, "비우기", self.clear,
                       height=34).pack(side="left", padx=(8, 0))
        self.unreg_btn = U.ghost_button(bar, "등록 풀기", self.unregister,
                                        height=34)
        self.status = U.status_line(self.win, "")
        self.status.pack(fill="x", padx=16, pady=(4, 12))

        self._wait = ui_loading.Overlay(self.win, "포켓몬을 불러오는 중")

        def work():
            return self.app.api.pvp_team(), self.app.api.pokemon()
        run_async(self.root, work, self._loaded)

    def say(self, text, color=U.GOOD):
        U.set_status(self.status, text, color)

    def _loaded(self, r, err):
        if self._wait:
            self._wait.close()
            self._wait = None
        if err:
            return self.say(getattr(err, "message", str(err)), U.DANGER)
        team, mons = r
        team = team or {}
        self.max = int(team.get("maxParty") or 6)
        self.cap = int(team.get("levelCap") or 50)
        self.restricted = set(int(n) for n in team.get("restrictedNums") or [])
        self.restricted_max = int(team.get("restrictedMax") or 1)
        self.registered = bool(team.get("registered"))
        self.picked = [int(i) for i in team.get("ids") or []]
        # 레벨 높은 순. 랭크 팀은 대개 제일 센 애들로 짠다.
        self.mons = sorted(mons or [], key=lambda m: (-int(m.get("level", 0)),
                                                      m.get("id", 0)))
        self.note.configure(text=natural(
            "랜덤 배틀에서 걸 때도 걸려올 때도 이 팀으로 싸웁니다. "
            "등록하지 않으면 바탕화면에 데리고 다니는 파티로 싸웁니다.\n"
            "Lv.%d 넘는 포켓몬은 Lv.%d(으)로 싸웁니다. %d마리로 걸면 %d마리 "
            "팀만 만나고, 받는 쪽도 거는 쪽보다 적은 팀이면 안 붙습니다. "
            "전설·환상 포켓몬은 %d마리까지 넣을 수 있습니다."
            % (self.cap, self.cap, self.max, self.max, self.restricted_max)))
        if self.registered:
            self.unreg_btn.pack(side="left", padx=(8, 0))
        for m in self.mons:
            self._row(m)
        self.visible = [m["id"] for m in self.mons]
        self._filter()
        self._paint()
        extra = self._restricted_count(self.picked) - self.restricted_max
        if extra > 0:
            self.say("전설·환상이 %d마리 더 있어 랭크 배틀에는 앞의 %d마리만 나갑니다. "
                     "등록하려면 %d마리를 빼세요." % (extra, self.restricted_max, extra),
                     U.ACCENT)

    def _filter(self):
        """찾기 칸의 글에 맞는 포켓몬만 목록에 담는다. 고른 것은 안 보여도 고른 그대로다."""
        q = self.q.get()
        dex = getattr(self.app, "dex", None)
        want = [m["id"] for m in self.mons if box_filter.matches(m, dex, None, q)]
        if want != self.visible:
            for pid in self.visible:
                self.row_box[pid].pack_forget()
            for pid in want:
                self.row_box[pid].pack(fill="x")
            self.visible = want
            try:
                self.cv.yview_moveto(0)
            except tk.TclError:
                pass
            self.fit.schedule()
        if self.mons and not want:
            self.nomatch.configure(text=natural("'%s' 에 맞는 포켓몬이 없습니다." % q.strip()))
            self.nomatch.pack(pady=22)
        else:
            self.nomatch.pack_forget()
        self.found.configure(text=("%d마리 중 %d마리" % (len(self.mons), len(want))) if q.strip()
                             else "%d마리" % len(self.mons))

    def _row(self, m):
        info = m.get("info") or {}
        # 줄과 그 아래 선을 한 틀에 담는다 - 찾기로 숨길 때 둘이 같이 빠져야 한다.
        box = tk.Frame(self.inner, bg=U.INK)
        box.pack(fill="x")
        self.row_box[m["id"]] = box
        f = tk.Frame(box, bg=U.INK, cursor="hand2")
        f.pack(fill="x")
        line = tk.Frame(f, bg=U.INK)
        line.pack(fill="x", padx=10, pady=6)
        mark = tk.Label(line, text="", bg=U.INK, fg=U.ACCENT, width=3,
                        font=U.FONT_B)
        mark.pack(side="left")
        lv = int(m.get("level", 0))
        tk.Label(line, text=info.get("name") or "?", bg=U.INK,
                 fg=U.SHINY if m.get("shiny") else U.FG,
                 font=U.FONT_B).pack(side="left")
        lv_text = "Lv.%d" % lv
        if lv > self.cap:
            lv_text += " → Lv.%d" % self.cap       # 가방의 사탕 줄과 같은 꼴
        tk.Label(line, text=lv_text, bg=U.INK, fg=U.FG_DIM,
                 font=U.FONT_S).pack(side="left", padx=(8, 0))
        species = info.get("species") or ""
        if species and species != info.get("name"):
            tk.Label(line, text=species, bg=U.INK, fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(side="left", padx=(8, 0))
        if m.get("onDesktop"):
            tk.Label(line, text="데리고 다님", bg=U.INK, fg=U.INFO,
                     font=U.FONT_XS).pack(side="right")
        if self._is_restricted(m):
            tk.Label(line, text="전설·환상", bg=U.INK, fg=U.SHINY,
                     font=U.FONT_XS).pack(side="right", padx=(0, 8))
        tk.Frame(box, bg="#1a1f2e", height=U.h(1)).pack(fill="x")
        pid = m["id"]
        for w in (f, line) + tuple(line.winfo_children()):
            w.bind("<Button-1>", lambda _e, p=pid: self.toggle(p))
        self.rows[pid] = (f, line, mark)

    def _paint(self):
        n = len(self.picked)
        for pid, (f, line, mark) in self.rows.items():
            on = pid in self.picked
            bg = U.ACCENT_SOFT if on else U.INK
            try:
                for w in (f, line) + tuple(line.winfo_children()):
                    w.configure(bg=bg)
                mark.configure(text=("%d" % (self.picked.index(pid) + 1))
                               if on else "")
            except tk.TclError:
                pass
        for w in self.slots.winfo_children():
            w.destroy()
        by = dict((m["id"], m) for m in self.mons)
        for i in range(self.max):
            pid = self.picked[i] if i < n else None
            m = by.get(pid)
            text = ("%d. %s" % (i + 1, (m.get("info") or {}).get("name", "?"))
                    if m else "%d. 빈 자리" % (i + 1))
            tk.Label(self.slots, text=text, bg=U.BG2 if m else U.BG,
                     fg=U.FG if m else U.FG_FAINT, font=U.FONT_XS,
                     padx=6, pady=2, highlightthickness=1,
                     highlightbackground=U.LINE).grid(
                row=i // 3, column=i % 3, sticky="we", padx=2, pady=2)
        for c in range(3):
            self.slots.grid_columnconfigure(c, weight=1, uniform="slot")
        self.state.configure(
            text=("  등록됨" if self.registered else "  등록 안 함 · 바탕화면 파티로 싸움")
            + "  ·  %d / %d마리" % (n, self.max))
        if n and n < self.max:
            self.say("%d마리 팀에는 %d마리 이하로 거는 사람만 걸어옵니다. "
                     "%d마리를 채우면 더 많은 상대와 붙습니다." % (n, n, self.max),
                     U.ACCENT)
        else:
            self.say("")

    def _is_restricted(self, m):
        return bool(m) and m.get("num") in self.restricted

    def _restricted_count(self, ids):
        by = dict((m["id"], m) for m in self.mons)
        return sum(1 for i in ids if self._is_restricted(by.get(i)))

    def toggle(self, pid):
        if pid in self.picked:
            self.picked.remove(pid)
        elif len(self.picked) >= self.max:
            return self.say("%d마리까지입니다. 뺄 포켓몬을 먼저 누르세요."
                            % self.max, U.ACCENT)
        else:
            by = dict((m["id"], m) for m in self.mons)
            if (self._is_restricted(by.get(pid))
                    and self._restricted_count(self.picked) >= self.restricted_max):
                return self.say("전설·환상 포켓몬은 %d마리까지 넣을 수 있습니다."
                                % self.restricted_max, U.ACCENT)
            self.picked.append(pid)
        self._paint()

    def fill_party(self):
        party = [m for m in self.mons if m.get("onDesktop")]
        party.sort(key=lambda m: (m.get("slot") if m.get("slot") is not None
                                  else 99, m["id"]))
        picked, legends = [], 0
        for m in party:
            if self._is_restricted(m):
                if legends >= self.restricted_max:
                    continue            # 두 마리째 전설·환상은 건너뛴다
                legends += 1
            picked.append(m["id"])
        self.picked = picked[:self.max]
        self._paint()

    def clear(self):
        self.picked = []
        self._paint()

    def save(self):
        if not self.picked:
            return self.say("포켓몬을 한 마리 이상 고르세요. 등록을 풀려면 "
                            "'등록 풀기' 를 누르세요.", U.ACCENT)
        self._send(list(self.picked), "랭크 팀을 등록했습니다.")

    def unregister(self):
        self._send([], "등록을 풀었습니다. 바탕화면 파티로 싸웁니다.")

    def _send(self, ids, done_text):
        self.say("저장하는 중...", U.FG_FAINT)

        def done(r, err):
            if err:
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            r = r or {}
            self.registered = bool(r.get("registered"))
            self.picked = [int(i) for i in r.get("ids") or []]
            if self.registered:
                self.unreg_btn.pack(side="left", padx=(8, 0))
            else:
                self.unreg_btn.holder.pack_forget()      # PushButton 은 틀(holder)을 담는다
            self._paint()
            self.say(done_text)
            if self.on_saved:
                try:
                    self.on_saved()
                except Exception:                           # noqa: BLE001
                    pass
        run_async(self.root, lambda: self.app.api.pvp_set_team(ids), done)

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        if getattr(self.app, "team_window", None) is self:
            self.app.team_window = None


# ---------------------------------------------------------------- 칭호 · 명패
class RewardsWindow(object):
    """가진 칭호와 명패 중에서 하나씩 단다."""

    def __init__(self, app, on_saved=None):
        self.app = app
        self.root = app.root
        self.on_saved = on_saved
        # '달지 않기' 를 빈 글자로 두지 않는다. Tk 라디오 단추는 변수가 빈
        # 글자이면 나머지 단추를 전부 '반쯤 골라짐' 으로 그린다(tristatevalue
        # 기본값이 빈 글자다). 명패 칸이 둘 다 골라진 것처럼 보였다.
        self.title_var = tk.StringVar(value=NONE)
        self.frame_var = tk.StringVar(value=NONE)

        self.win, self.body = _dialog(self.root, "칭호 · 명패", 440, 520)
        # 칭호가 많으면(도감 업적으로 수십 개가 된다) 목록을 굴려서 본다
        U.install_wheel(self.win)
        self.cv = None
        self.fit = None
        self._radios = {}             # (변수 이름, 값) -> 라디오 단추
        self.status = U.status_line(self.win, "")
        self.status.pack(side="bottom", fill="x", padx=16, pady=(0, 10))
        self._wait = ui_loading.Overlay(self.win, "불러오는 중")
        run_async(self.root, self.app.api.rewards, self._loaded)

    def say(self, text, color=U.GOOD):
        U.set_status(self.status, text, color)

    def _loaded(self, r, err):
        if self._wait:
            self._wait.close()
            self._wait = None
        if err:
            return self.say(getattr(err, "message", str(err)), U.DANGER)
        r = r or {}
        eq = r.get("equipped") or {}
        self.title_var.set(eq.get("title") or NONE)
        self.frame_var.set(eq.get("frame") or NONE)
        titles = r.get("titles") or []
        frames = r.get("frames") or []

        # **단추 줄을 먼저 아래에 붙인다.** 칭호가 수십 개면 목록이 창보다 길어서,
        # 목록 뒤에 담으면 '달기' 가 창 밖으로 밀려 누를 수가 없었다 (1.7.0 -
        # 도감 업적으로 칭호가 46개까지 늘었다). 목록은 그 위에서 굴린다.
        row = tk.Frame(self.body, bg=U.BG)
        row.pack(fill="x", side="bottom", pady=(10, 0))
        U.PushButton(row, "달기", self.save, height=34,
                     font=U.FONT_B).pack(side="right")
        U.ghost_button(row, "닫기", self.close, height=34).pack(
            side="right", padx=(0, 8))
        holder = tk.Frame(self.body, bg=U.BG)
        holder.pack(fill="both", expand=True)
        self.cv = tk.Canvas(holder, bg=U.BG, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(holder, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        f = tk.Frame(self.cv, bg=U.BG)
        wid = self.cv.create_window((0, 0), window=f, anchor="nw")
        self.fit = U.scroll_fitter(self.cv, f, wid)
        U.scrollable(self.cv, 60)
        self._inner = f

        tk.Label(f, text="칭호", bg=U.BG, fg=U.FG, font=U.FONT_H).pack(anchor="w")
        tk.Label(f, text="랭킹·친구 목록·투기장에서 이름 옆에 붙습니다.",
                 bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS).pack(anchor="w")
        box = U.framed(f, bg=U.INK)
        box.pack(fill="x", pady=(6, 12), padx=(0, 8))
        self._radio(box, self.title_var, NONE, "달지 않기", U.FG_DIM)
        for t in titles:
            self._radios[("title", t["id"])] = self._radio(
                box, self.title_var, t["id"], t["name"], U.ACCENT_TEXT)
        if not titles:
            tk.Label(box, text="아직 받은 칭호가 없습니다. 시즌 보상이나 도감 업적으로 "
                               "받습니다.", bg=U.INK, fg=U.FG_FAINT,
                     font=U.FONT_XS, wraplength=340, justify="left").pack(
                anchor="w", padx=10, pady=6)

        tk.Label(f, text="명패", bg=U.BG, fg=U.FG, font=U.FONT_H).pack(anchor="w")
        tk.Label(f, text="이름이 명패 색으로 바뀝니다.", bg=U.BG, fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(anchor="w")
        box = U.framed(f, bg=U.INK)
        box.pack(fill="x", pady=(6, 12), padx=(0, 8))
        self._radio(box, self.frame_var, NONE, "달지 않기", U.FG_DIM)
        for fr in frames:
            self._radio(box, self.frame_var, fr["id"], fr["name"],
                        fr.get("color") or U.FG)
        if not frames:
            tk.Label(box, text="아직 받은 명패가 없습니다.", bg=U.INK,
                     fg=U.FG_FAINT, font=U.FONT_XS).pack(anchor="w", padx=10,
                                                         pady=6)
        self.fit.fit_now()
        self._show_equipped()

    def _show_equipped(self):
        """달고 있는 칭호가 목록 아래쪽에 있으면 거기까지 굴려 둔다."""
        rb = self._radios.get(("title", self.title_var.get()))
        if rb is None or self.cv is None:
            return
        try:
            self.win.update_idletasks()
            total = self._inner.winfo_height()
            view = self.cv.winfo_height()
            y = rb.master.winfo_y() + rb.winfo_y()
            if total > view and y + rb.winfo_height() > view:
                self.cv.yview_moveto(max(0.0, (y - view // 3) / float(total)))
        except tk.TclError:
            pass

    def _radio(self, parent, var, value, text, color):
        rb = tk.Radiobutton(parent, text=text, variable=var, value=value,
                            bg=U.INK, fg=color, selectcolor=U.BG3,
                            activebackground=U.INK, activeforeground=color,
                            font=U.FONT_B, anchor="w", highlightthickness=0,
                            bd=0)
        rb.pack(fill="x", padx=10, pady=3)
        return rb

    def save(self):
        title, frame = self.title_var.get(), self.frame_var.get()
        title = "" if title == NONE else title      # 서버는 빈 글자를 '떼기' 로 읽는다
        frame = "" if frame == NONE else frame
        self.say("다는 중...", U.FG_FAINT)

        def done(r, err):
            if err:
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            self.say("달았습니다.")
            if self.on_saved:
                try:
                    self.on_saved()
                except Exception:                           # noqa: BLE001
                    pass
        run_async(self.root, lambda: self.app.api.equip_reward(title, frame),
                  done)

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass


def _dialog(root, title, w, h):
    win = tk.Toplevel(root)
    U.style_window(win, title, w, h)
    U.apply_theme(win)
    win.configure(bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2)
    bar = tk.Frame(win, bg=U.BG2, height=U.h(34))
    bar.pack(fill="x")
    bar.pack_propagate(False)
    tk.Frame(bar, bg=U.ACCENT, width=3, height=U.h(13)).pack(side="left",
                                                             padx=(12, 8))
    tk.Label(bar, text=title, bg=U.BG2, fg=U.FG, font=U.FONT_B).pack(side="left")
    tk.Frame(win, bg=U.LINE2, height=U.h(2)).pack(fill="x")
    body = tk.Frame(win, bg=U.BG)
    body.pack(fill="both", expand=True, padx=18, pady=14)
    return win, body
