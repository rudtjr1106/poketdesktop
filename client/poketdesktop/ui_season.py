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
from . import skins
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
@skins.skinnable
class TeamWindow(object):
    """랭크 팀을 고르는 창.

    랜덤 배틀에서 **걸 때도 걸려올 때도** 이 팀으로 싸운다. 등록하지 않으면
    바탕화면에 데리고 다니는 파티로 싸운다 - 그래서 처음 열면 지금 파티가
    골라져 있다.

    **길드전의 방어팀·공격팀도 이 창으로 짠다** (시즌 4, spec). 고르는 방식과 규칙(여섯 마리,
    레벨 상한, 전설·환상 한 마리)이 같아서다. spec 은 무엇이 다른지만 적는다:
        title     창 제목 ("길드전 방어팀")
        note      위에 적을 설명
        load      () -> (팀, 내 포켓몬)        팀은 /api/pvp/team 과 같은 꼴
        save      (ids) -> {"registered", "ids"}
        saved     저장했을 때 띄울 말

    서버에서 받기 · 고르기 규칙 · 저장은 여기 것을 테마도 그대로 쓴다. 테마는 짓는 고리만 바꾼다:
    _build(창 안) · _row(줄 하나) · _repack(찾기로 바뀐 목록) · _paint_found · _paint_rows · _paint_slots ·
    _paint_state · _paint_note · _show_unreg · say.
    """
    SIZE = (560, 660, 460, 520)        # 창 크기 · 가장 작은 크기 (테마가 바꿔 쓴다)

    def __init__(self, app, on_saved=None, spec=None):
        self.app = app
        self.root = app.root
        self.on_saved = on_saved
        self.spec = spec or {}
        title = self.spec.get("title") or "랭크 팀"
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
        self.same_max = None           # 같은 종 상한 (10/22 서버만 준다)
        self.rank_min = None           # 랭크전 조건 {"count", "level"} (시즌 4 서버만 준다)
        # 찾기 (1.10.0). 포켓몬이 수백 마리가 되면 레벨 순 목록을 끝까지 굴려야 했다.
        # 포켓몬 관리의 '이름 찾기' 와 같은 규칙이다 - 별명·종 이름·도감 번호를 다 본다.
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_a: self._filter())

        w, h, minw, minh = self.SIZE
        self.win = U.panel(None, self.root, title, w, h, minw, minh, self.close)
        U.install_wheel(self.win)
        self._build(title)

        self._wait = ui_loading.Overlay(self.win, "포켓몬을 불러오는 중")

        def work():
            if self.spec.get("load"):
                return self.spec["load"]()
            return self.app.api.pvp_team(), self.app.api.pokemon()
        run_async(self.root, work, self._loaded)

    # ---------------- 짓기 (테마마다 짓는 곳) ----------------
    def _build(self, title):
        """창 안: 머리(제목 · 상태) · 설명 · 여섯 자리 · 찾기 · 목록 · 단추 · 아래 줄.

        self.state · note · slots · found · nomatch · cv · inner · fit · save_btn · unreg_btn · status 를 둔다."""
        self.win.configure(bg=U.BG, highlightthickness=2,
                           highlightbackground=U.LINE2)

        head = tk.Frame(self.win, bg=U.BG2, height=U.h(56))
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text=title, bg=U.BG2, fg=U.FG,
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

        find = tk.Frame(self.win, bg=U.BG)
        find.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(find, text="포켓몬 찾기", bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS).pack(side="left")
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

    def say(self, text, color=U.GOOD):
        U.set_status(self.status, text, color)

    def _paint_note(self, text):
        """설명 칸의 글."""
        self.note.configure(text=text)

    def _show_unreg(self, on):
        """'등록 풀기' 단추를 보일까."""
        if on:
            self.unreg_btn.pack(side="left", padx=(8, 0))
        else:
            self.unreg_btn.holder.pack_forget()      # PushButton 은 틀(holder)을 담는다

    def _loaded(self, r, err):
        if self._wait:
            self._wait.close()
            self._wait = None
        if err:
            return self.say(getattr(err, "message", str(err)), U.DANGER)
        team, mons = r
        self._take(team or {}, mons)
        self._paint_note(natural(self.note_text()))
        if self.registered and not self.spec:
            self._show_unreg(True)
        for m in self.mons:
            self._row(m)
        self.visible = [m["id"] for m in self.mons]
        self._filter()
        self._paint()
        for text in self.open_warnings():
            self.say(text, U.ACCENT)

    # ---------------- 자료 (테마도 그대로 쓴다) ----------------
    def _take(self, team, mons):
        """서버가 준 팀 · 포켓몬을 받아 둔다."""
        self.max = int(team.get("maxParty") or 6)
        self.cap = int(team.get("levelCap") or 50)
        self.restricted = set(int(n) for n in team.get("restrictedNums") or [])
        self.restricted_max = int(team.get("restrictedMax") or 1)
        # 같은 종 상한 (10/22). 옛 서버는 안 보낸다 - 그때는 막지 않는다 (서버가 본다).
        self.same_max = int(team["sameSpeciesMax"]) if team.get("sameSpeciesMax") else None
        self.rank_min = None if self.spec else team.get("rankMin")
        self.registered = bool(team.get("registered"))
        self.picked = [int(i) for i in team.get("ids") or []]
        # 레벨 높은 순. 랭크 팀은 대개 제일 센 애들로 짠다.
        self.mons = sorted(mons or [], key=lambda m: (-int(m.get("level", 0)),
                                                      m.get("id", 0)))

    def note_text(self):
        """설명 칸에 적을 말 (spec 의 note, 아니면 랭크 팀 규칙)."""
        if self.spec.get("note"):
            note = self.spec["note"]
        elif self.rank_min:
            note = ("랜덤 배틀에서 걸 때도 걸려올 때도 이 팀으로 싸웁니다. "
                    "등록하지 않으면 바탕화면에 데리고 다니는 파티로 싸웁니다.\n"
                    "랭크전은 Lv.%d 이상 포켓몬 %d마리로 채워야 걸 수 있고, 상대로도 그런 팀만 뽑힙니다. "
                    "Lv.%d 넘는 포켓몬은 Lv.%d(으)로 싸웁니다. 전설·환상 포켓몬은 %d마리까지 넣을 수 있습니다."
                    % (int(self.rank_min.get("level") or 50), int(self.rank_min.get("count") or 6),
                       self.cap, self.cap, self.restricted_max))
        else:
            note = ("랜덤 배틀에서 걸 때도 걸려올 때도 이 팀으로 싸웁니다. "
                    "등록하지 않으면 바탕화면에 데리고 다니는 파티로 싸웁니다.\n"
                    "Lv.%d 넘는 포켓몬은 Lv.%d(으)로 싸웁니다. %d마리로 걸면 %d마리 "
                    "팀만 만나고, 받는 쪽도 거는 쪽보다 적은 팀이면 안 붙습니다. "
                    "전설·환상 포켓몬은 %d마리까지 넣을 수 있습니다."
                    % (self.cap, self.cap, self.max, self.max, self.restricted_max))
        if self.same_max and not self.spec.get("note"):
            note += " 같은 포켓몬은 %d마리까지 넣을 수 있습니다." % self.same_max
        return note

    def open_warnings(self):
        """열 때 알릴 것 (등록해 둔 팀이 규칙을 넘는다). 차례로 띄운다 - 뒤의 것이 남는다."""
        out = []
        extra = self._restricted_count(self.picked) - self.restricted_max
        if extra > 0 and not self.spec:
            out.append("전설·환상이 %d마리 더 있어 랭크 배틀에는 앞의 %d마리만 나갑니다. "
                       "등록하려면 %d마리를 빼세요." % (extra, self.restricted_max, extra))
        same = self._same_extra(self.picked)
        if same and not self.spec:
            out.append("같은 포켓몬이 %d마리 더 있어 랭크 배틀에는 앞의 %d마리만 나갑니다. "
                       "등록하려면 %d마리를 빼세요." % (same, self.same_max, same))
        return out

    def row_info(self, m):
        """목록 한 줄에 적을 것: 이름 · 이로치 · 레벨(상한을 넘으면 '→ Lv.50') · 종(별명이면) · 데리고 다님 · 전설·환상."""
        info = m.get("info") or {}
        lv = int(m.get("level", 0))
        lv_text = "Lv.%d" % lv
        if lv > self.cap:
            lv_text += " → Lv.%d" % self.cap       # 가방의 사탕 줄과 같은 꼴
        species = info.get("species") or ""
        return {"name": info.get("name") or "?", "shiny": bool(m.get("shiny")), "lv": lv_text,
                "species": species if species and species != info.get("name") else "",
                "desk": bool(m.get("onDesktop")), "restricted": self._is_restricted(m)}

    def slot_mons(self):
        """여섯 자리에 놓을 포켓몬 (고른 차례대로, 빈 자리는 None)."""
        by = dict((m["id"], m) for m in self.mons)
        n = len(self.picked)
        return [by.get(self.picked[i] if i < n else None) for i in range(self.max)]

    def state_parts(self):
        """머리에 적을 것: (등록 상태, 'n / 6마리')."""
        if self.spec:
            head = "짜 둠" if self.registered else "아직 안 짬 · 랭크 팀으로 나감"
        else:
            head = "등록됨" if self.registered else "등록 안 함 · 바탕화면 파티로 싸움"
        return head, "%d / %d마리" % (len(self.picked), self.max)

    def team_hint(self):
        """지금 고른 팀에 대해 아래 줄에 띄울 말 (글, 빛깔). 할 말이 없으면 빈 글."""
        n = len(self.picked)
        if self.spec:
            return "", U.GOOD
        if self.rank_min:
            need, lv = int(self.rank_min.get("count") or 6), int(self.rank_min.get("level") or 50)
            ready = self.rank_ready_count()
            if ready < need:
                return ("랭크전은 Lv.%d 이상 %d마리가 있어야 걸 수 있습니다 - 지금 %d마리."
                        % (lv, need, ready)), U.ACCENT
            return "", U.GOOD
        if n and n < self.max:
            return ("%d마리 팀에는 %d마리 이하로 거는 사람만 걸어옵니다. "
                    "%d마리를 채우면 더 많은 상대와 붙습니다." % (n, n, self.max)), U.ACCENT
        return "", U.GOOD

    def found_text(self, q, want):
        """찾기 칸 옆의 마릿수."""
        return ("%d마리 중 %d마리" % (len(self.mons), len(want))) if q.strip() else "%d마리" % len(self.mons)

    @staticmethod
    def nomatch_text(q):
        return natural("'%s' 에 맞는 포켓몬이 없습니다." % q.strip())

    def _filter(self):
        """찾기 칸의 글에 맞는 포켓몬만 목록에 담는다. 고른 것은 안 보여도 고른 그대로다."""
        q = self.q.get()
        dex = getattr(self.app, "dex", None)
        want = [m["id"] for m in self.mons if box_filter.matches(m, dex, None, q)]
        if want != self.visible:
            old, self.visible = self.visible, want
            self._repack(old, want)
        self._paint_found(q, want)

    # ---------------- 칠하기 (테마마다 짓는 곳) ----------------
    def _repack(self, old, want):
        """찾기로 목록에 담길 줄이 바뀌었다 (old -> want, 화면 순서대로). 맨 위로 굴린다."""
        for pid in old:
            self.row_box[pid].pack_forget()
        for pid in want:
            self.row_box[pid].pack(fill="x")
        try:
            self.cv.yview_moveto(0)
        except tk.TclError:
            pass
        self.fit.schedule()

    def _paint_found(self, q, want):
        """찾은 마릿수 · '맞는 포켓몬이 없다'."""
        if self.mons and not want:
            self.nomatch.configure(text=self.nomatch_text(q))
            self.nomatch.pack(pady=22)
        else:
            self.nomatch.pack_forget()
        self.found.configure(text=self.found_text(q, want))

    def _row(self, m):
        r = self.row_info(m)
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
        tk.Label(line, text=r["name"], bg=U.INK,
                 fg=U.SHINY if r["shiny"] else U.FG,
                 font=U.FONT_B).pack(side="left")
        tk.Label(line, text=r["lv"], bg=U.INK, fg=U.FG_DIM,
                 font=U.FONT_S).pack(side="left", padx=(8, 0))
        if r["species"]:
            tk.Label(line, text=r["species"], bg=U.INK, fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(side="left", padx=(8, 0))
        if r["desk"]:
            tk.Label(line, text="데리고 다님", bg=U.INK, fg=U.INFO,
                     font=U.FONT_XS).pack(side="right")
        if r["restricted"]:
            tk.Label(line, text="전설·환상", bg=U.INK, fg=U.SHINY,
                     font=U.FONT_XS).pack(side="right", padx=(0, 8))
        tk.Frame(box, bg="#1a1f2e", height=U.h(1)).pack(fill="x")
        pid = m["id"]
        for w in (f, line) + tuple(line.winfo_children()):
            w.bind("<Button-1>", lambda _e, p=pid: self.toggle(p))
        self.rows[pid] = (f, line, mark)

    def _paint(self):
        """고른 것이 바뀌었다 - 줄 · 여섯 자리 · 머리를 다시 칠하고 아래 줄에 할 말을 띄운다."""
        self._paint_rows()
        self._paint_slots()
        self._paint_state("  %s  ·  %s" % self.state_parts())
        self.say(*self.team_hint())

    def _paint_rows(self):
        """목록의 줄마다 골랐나 (바탕 · 고른 차례)."""
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

    def _paint_slots(self):
        """고른 여섯 자리."""
        for w in self.slots.winfo_children():
            w.destroy()
        for i, m in enumerate(self.slot_mons()):
            text = ("%d. %s" % (i + 1, (m.get("info") or {}).get("name", "?"))
                    if m else "%d. 빈 자리" % (i + 1))
            tk.Label(self.slots, text=text, bg=U.BG2 if m else U.BG,
                     fg=U.FG if m else U.FG_FAINT, font=U.FONT_XS,
                     padx=6, pady=2, highlightthickness=1,
                     highlightbackground=U.LINE).grid(
                row=i // 3, column=i % 3, sticky="we", padx=2, pady=2)
        for c in range(3):
            self.slots.grid_columnconfigure(c, weight=1, uniform="slot")

    def _paint_state(self, text):
        """머리의 상태 글 (등록했나 · 몇 마리)."""
        self.state.configure(text=text)

    def rank_ready_count(self):
        """고른 팀에서 랭크전 조건(Lv.N 이상)에 드는 마릿수. 서버처럼 같은 종·전설·환상은 앞의 몇 마리만 나간다고 센다."""
        lv = int((self.rank_min or {}).get("level") or 50)
        by = dict((m["id"], m) for m in self.mons)
        legends = n = 0
        kinds = {}
        for pid in self.picked:
            m = by.get(pid)
            if not m:
                continue
            sp = self._species(m)
            if sp and self.same_max and kinds.get(sp, 0) >= self.same_max:
                continue
            if sp:
                kinds[sp] = kinds.get(sp, 0) + 1
            if self._is_restricted(m):
                legends += 1
                if legends > self.restricted_max:
                    continue
            if int(m.get("level") or 1) >= lv:
                n += 1
        return n

    def _is_restricted(self, m):
        return bool(m) and m.get("num") in self.restricted

    def _restricted_count(self, ids):
        by = dict((m["id"], m) for m in self.mons)
        return sum(1 for i in ids if self._is_restricted(by.get(i)))

    @staticmethod
    def _species(m):
        """종 (내부 이름). 옛 자료처럼 없으면 None - 그 포켓몬은 같은 종을 세지 않는다."""
        return (m or {}).get("species") or None

    def _same_count(self, ids, species):
        by = dict((m["id"], m) for m in self.mons)
        return sum(1 for i in ids if species and self._species(by.get(i)) == species)

    def _same_extra(self, ids):
        """같은 종이 상한보다 몇 마리 더 있나 (서버 pvp.split_restricted 처럼 뒤의 것이 빠진다)."""
        if not self.same_max:
            return 0
        by = dict((m["id"], m) for m in self.mons)
        count = {}
        for i in ids:
            sp = self._species(by.get(i))
            if sp:
                count[sp] = count.get(sp, 0) + 1
        return sum(max(0, n - self.same_max) for n in count.values())

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
            if self.same_max and self._same_count(self.picked, self._species(by.get(pid))) >= self.same_max:
                return self.say("같은 포켓몬은 %d마리까지 넣을 수 있습니다." % self.same_max, U.ACCENT)
            self.picked.append(pid)
        self._paint()

    def fill_party(self):
        party = [m for m in self.mons if m.get("onDesktop")]
        party.sort(key=lambda m: (m.get("slot") if m.get("slot") is not None
                                  else 99, m["id"]))
        picked, legends = [], 0
        for m in party:
            if self.same_max and self._same_count(picked, self._species(m)) >= self.same_max:
                continue                # 같은 종 두 마리째는 건너뛴다 (10/22)
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
        if not self.picked and self.spec:
            return self.say("포켓몬을 한 마리 이상 고르세요.", U.ACCENT)
        if not self.picked:
            return self.say("포켓몬을 한 마리 이상 고르세요. 등록을 풀려면 "
                            "'등록 풀기' 를 누르세요.", U.ACCENT)
        self._send(list(self.picked), self.spec.get("saved") or "랭크 팀을 등록했습니다.")

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
            self._show_unreg(self.registered and not self.spec)
            self._paint()
            self.say(done_text)
            if self.on_saved:
                try:
                    self.on_saved()
                except Exception:                           # noqa: BLE001
                    pass
        save = self.spec.get("save") or self.app.api.pvp_set_team
        run_async(self.root, lambda: save(ids), done)

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        if getattr(self.app, "team_window", None) is self:
            self.app.team_window = None


# ---------------------------------------------------------------- 칭호 · 명패
@skins.skinnable
class RewardsWindow(object):
    """가진 칭호와 명패 중에서 하나씩 단다.

    받기 · 달기(save)는 여기 것을 테마도 그대로 쓴다 - 고른 것은 title_var · frame_var 에 둔다.
    테마는 짓는 고리만 바꾼다: _build(창 틀) · _fill(목록) · say.
    """

    def __init__(self, app, on_saved=None):
        self.app = app
        self.root = app.root
        self.on_saved = on_saved
        # '달지 않기' 를 빈 글자로 두지 않는다. Tk 라디오 단추는 변수가 빈
        # 글자이면 나머지 단추를 전부 '반쯤 골라짐' 으로 그린다(tristatevalue
        # 기본값이 빈 글자다). 명패 칸이 둘 다 골라진 것처럼 보였다.
        self.title_var = tk.StringVar(value=NONE)
        self.frame_var = tk.StringVar(value=NONE)
        self.cv = None
        self.fit = None
        self._radios = {}             # (변수 이름, 값) -> 라디오 단추

        self._build()
        # 칭호가 많으면(도감 업적으로 수십 개가 된다) 목록을 굴려서 본다
        U.install_wheel(self.win)
        self._wait = ui_loading.Overlay(self.win, "불러오는 중")
        run_async(self.root, self.app.api.rewards, self._loaded)

    # ---------------- 짓기 (테마마다 짓는 곳) ----------------
    def _build(self):
        """창 틀: self.win · body · status 를 둔다."""
        self.win, self.body = _dialog(self.root, "칭호 · 명패", 440, 520)
        self.status = U.status_line(self.win, "")
        self.status.pack(side="bottom", fill="x", padx=16, pady=(0, 10))

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
        self._fill(r.get("titles") or [], r.get("frames") or [])

    def _fill(self, titles, frames):
        """목록: 칭호 줄 · 명패 줄 ('달지 않기' 가 맨 위), 그 아래 '닫기 · 달기'. 달고 있는 칭호까지 굴려 둔다."""
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
    U.dialog_bar(win, title)
    body = tk.Frame(win, bg=U.BG)
    body.pack(fill="both", expand=True, padx=18, pady=14)
    return win, body
