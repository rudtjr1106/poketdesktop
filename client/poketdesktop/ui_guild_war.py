# -*- coding: utf-8 -*-
"""길드 창의 '길드전' 탭 (시즌 4). 규칙은 서버 guild_war.py 에 있다.

길드전은 **원형 지도의 칸을 뺏는 전쟁**이다 (길드마다 같은 부채꼴 15칸 - 서버 guild_war.layout).
단계마다 보여 주는 것이 다르다.

    신청   참가 신청·취소(마스터·부마스터), 참가한 길드들, **내 방어팀·공격팀 짜기**
    전략   지도가 나뉜다. (길드장) 공격 나누기 · 지키는 사람 옮기기, 팀 고치기. 공격은 아직 못 한다
    전쟁   왼쪽에 지도(길드마다 색), 오른쪽에 내 공격권 · 고른 칸 · 순위 · 기록. 정해 둔 것은 고정이다
    끝     마지막 지도와 순위, 보상 안내, 기록

  · 지도는 ui_war_map.WarMap 이 그린다. 칸을 누르면 그 칸을 지키는 쪽과 방어팀을 서버에 묻는다
    (`/api/guild/war/tile`) - **남의 방어팀은 앞 몇 마리만 온다.** 가려진 것은 응답에 없으니
    화면도 '가려진 N마리' 라고만 적는다.
  · 공격은 **관장 배틀 창**에서 직접 싸운다 (ui_gym_battle.GymBattleWindow). 같은 사람을 3번 이기면
    칸이 넘어온다. 창을 닫으면 지도를 다시 받는다. 끝나지 않은 판이 있으면 '이어서 하기' 가 뜬다.
  · 길드장(마스터·부마스터)은 **전략 기간에** 공격 횟수를 나누고(합 30번, 한 사람 최소 1번), 우리 칸을
    지킬 사람을 옮긴다. 전쟁이 시작되면 못 바꾼다 (2026-10-15 사용자 결정 - 신청 3일·전략 4일·전쟁 6일·결산 1일).
  · 팀 짜기는 랭크 팀 창을 그대로 쓴다 (ui_season.TeamWindow, spec).
  · 전략·전쟁 중에는 지도를 30초마다 다시 받는다 (다른 길드가 뺏는 것이 보이게, 단계가 넘어가면
    통째로 다시 받게). 색만 고친다.

길드 창은 길드원 누가 미션을 끝내기만 해도 칸을 통째로 다시 만든다. 그때 보던 자리(확대·고른 칸)와
받아 둔 것을 길드 창에 맡겨 두었다가(war_keep) 이어서 그린다 - 지도가 깜빡이며 처음으로 돌아가지 않게.

오른쪽 칸은 길어질 수 있어 안쪽을 굴린다 (창을 키우지 않는다).
"""
import tkinter as tk
from tkinter import ttk

from . import skins
from . import ui_common as U
from . import ui_war_map as WM
from .ui_common import run_async

CARD = "#161b28"
PHASE_COLOR = {"before": U.BG4, "apply": U.INFO, "plan": U.PINK, "war": U.DANGER, "done": U.FG_DIM}
KIND_KR = (("def", "방어팀"), ("atk", "공격팀"))
SIDE_W = 330                 # 지도 옆 칸의 폭
POLL_MS = 30000              # 전략·전쟁 중에 지도를 다시 받는 간격
MAP_HINT = "칸을 누르면 지키는 쪽과 방어팀이 보입니다 · 휠로 확대 · 키운 뒤에는 끌어서 옮기기"


def span_text(sec):
    """남은 시간. 하루가 넘으면 날과 시간으로."""
    if sec is None:
        return ""
    sec = max(0, int(sec))
    d, h, m = sec // 86400, (sec % 86400) // 3600, (sec % 3600) // 60
    if d:
        return "%d일 %d시간" % (d, h)
    if h:
        return "%d시간 %d분" % (h, m)
    return "%d분" % max(1, m)


def phase_line(st):
    """단계 이름 옆에 적을 한 줄."""
    ph, left = st.get("phase"), span_text(st.get("endsIn"))
    if ph == "before":
        return "시즌이 시작하면 참가 신청을 받습니다 (%s 뒤)." % left
    if ph == "apply":
        return "전략 기간이 시작될 때까지 %s. 그때 명단이 고정되고 지도가 나뉩니다." % left
    if ph == "plan":
        return "전쟁이 시작될 때까지 %s. 그때 공격 횟수 · 지키는 칸 · 팀이 고정됩니다." % left
    if ph == "war":
        return "전쟁이 끝날 때까지 %s." % left
    return "이번 시즌의 길드전이 끝났습니다."


def schedule_line(st):
    return "신청 %d일 · 전략 %d일 · 전쟁 %d일" % (st.get("applyDays") or 3, st.get("planDays") or 4,
                                          st.get("warDays") or 6)


def rule_line(st):
    return ("%s. 참가한 길드가 원형 지도를 같은 모양으로 %d칸씩 나눠 갖고(이웃 길드는 양옆 두 곳), 전쟁이 "
            "시작되면 우리 칸과 맞닿은 남의 칸을 관장 "
            "배틀처럼 직접 칩니다. 그 칸을 지키는 같은 상대를 %d번 이기면 칸을 가져오고, 넘어간 칸은 다시 "
            "못 뺏습니다. 칸이 가장 많은 길드가 이깁니다. 공격은 길드 합쳐 %d번 - 길드장이 전략 기간에 나눠 "
            "줍니다 (한 사람 최소 1번). 길드원은 한 사람이 한 칸씩 지키고(길드장이 전략 기간에 옮긴다), 남는 "
            "칸은 AI 수비대가 지킵니다. 남의 방어팀은 앞에서부터 %d마리만 미리 보입니다. 팀은 Lv.%d 상한에 "
            "전설·환상 한 마리, 같은 포켓몬 한 마리까지입니다."
            % (schedule_line(st), st.get("tilesPer") or 15, st.get("need") or 3, st.get("total") or 30,
               st.get("shown") or 3, st.get("levelCap") or 50))


def reward_line(st):
    bits = []
    for r in st.get("rewards") or []:
        bits.append(("%d위 %d" % (r["rank"], r["coins"])) if r.get("rank") else "그 밖 %d" % r["coins"])
    return "보상(길드 코인, 한 번이라도 공격한 길드원): %s · 1위 길드에는 칭호 '%s'" % (
        " · ".join(bits), st.get("title") or "")


def team_text(mons):
    return "  ".join("%s Lv.%d" % (m.get("kr") or "?", m.get("level") or 0) for m in mons) or "비어 있음"


def log_mark(x):
    """기록 한 줄의 앞머리. (글, 좋은 일인가 - None 이면 진행 중)"""
    if x.get("result") == "pending":
        return "진행 중", None
    if x.get("ours"):
        if x.get("took"):
            return "점령", True
        return ("승리", True) if x.get("result") == "win" else ("패배", False)
    if x.get("took"):
        return "뺏김", False
    return ("방어", True) if x.get("good") else ("졌음", False)


@skins.skinnable
class WarTab(object):
    """gw 는 길드 창(GuildWindow). parent 는 그 탭의 빈 칸."""

    SIDE_W = SIDE_W              # 지도 옆 칸의 폭 (테마가 바꾼다 - _side_w 가 쓴다)

    def __init__(self, gw, parent):
        self.gw = gw
        self.app = gw.app
        self.root = gw.root
        self.alive = True
        self.st = None
        self.mapdata = None          # 서버의 지도 응답 (칸마다 주인, 길드마다 색·칸 수)
        self.geo = None              # 지도 그림 (서버가 지도 응답에 실어 준 부채꼴들 - _digest 는 그 요약값)
        self.log = None
        self.sel = None              # 고른 칸
        self.tile = None             # 고른 칸의 자료 (서버 tile_view)
        self.busy = False
        self.buttons = {}            # 이름 -> 단추 (검사가 누른다)
        self.picker = None
        self.plan = None             # 길드장이 고치는 중인 공격 나누기 {사람: 횟수}
        self.wide = False            # 지도를 옆에 낀 모양인가
        self.tile_box = None
        self.rank_box = None
        self.menu = None
        self._poll_job = None

        holder = tk.Frame(parent, bg=U.BG)
        self.holder = holder
        holder.pack(fill="both", expand=True, padx=16, pady=(10, 8))
        # 왼쪽: 지도. 전쟁 중과 끝난 뒤에만 낀다 (_layout)
        self.left = tk.Frame(holder, bg=U.BG)
        self.hint = tk.Label(self.left, text=MAP_HINT, bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w",
                             justify="left")
        self.hint.pack(side="bottom", fill="x", pady=(4, 0))
        U.wrap_to_width(self.hint)
        self.map = WM.WarMap(self.left, on_pick=self.pick, on_hover=self._hover)
        self.map.cv.pack(fill="both", expand=True)
        # 오른쪽: 굴리는 칸
        self.right = tk.Frame(holder, bg=U.BG)
        self.right.pack(side="left", fill="both", expand=True)
        self.cv = tk.Canvas(self.right, bg=U.BG, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(self.right, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.cv, bg=U.BG)
        self._wid = self.cv.create_window((0, 0), window=self.inner, anchor="nw")
        self.fit = U.scroll_fitter(self.cv, self.inner, self._wid)
        U.scrollable(self.cv, 60)
        holder.bind("<Destroy>", self._gone, add="+")
        holder.bind("<Configure>", lambda _e: self._fit_side(), add="+")

        keep = getattr(gw, "war_keep", None) or {}
        if keep.get("st"):
            # 칸이 다시 만들어졌다 (길드 창이 새로 받았다). 받아 둔 것으로 바로 그리고, 보던 자리를 잇는다.
            self.st, self.mapdata, self.geo = keep.get("st"), keep.get("map"), keep.get("geo")
            self.log, self.tile, self.plan = keep.get("log"), keep.get("tile"), keep.get("plan")
            self.map.set_view(keep.get("view"))
            self.sel = self.map.selected
            self.paint()
        else:
            tk.Label(self.inner, text="불러오는 중...", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(pady=24)
        self.reload()

    def _gone(self, e):
        if e.widget is not self.holder:
            return
        self.alive = False               # 다른 칸으로 갔거나 창을 닫아 이 칸이 없어졌다
        if self._poll_job is not None:
            try:
                self.root.after_cancel(self._poll_job)
            except Exception:                               # noqa: BLE001
                pass
        try:
            self.gw.war_keep = {"st": self.st, "map": self.mapdata, "geo": self.geo, "log": self.log,
                                "tile": self.tile, "plan": self.plan, "view": self.map.view()}
        except Exception:                                   # noqa: BLE001
            pass

    def say(self, text, color=None):
        try:
            self.gw.say(text, color)
        except Exception:                                   # noqa: BLE001
            pass

    # ---------------- 불러오기 ----------------
    def _fetch(self):
        """화면에 쓸 것 전부. 일하는 스레드에서 돈다."""
        api = self.app.api
        st = api.guild_war()
        mp = geo = log = None
        if st.get("phase") in ("plan", "war", "done"):
            mp = api.guild_war_map(self._have())
            geo = self._geo_of(mp)
            if st.get("guild"):
                log = api.guild_war_log()
        return st, mp, geo, log

    def _have(self):
        """가진 지도 그림의 요약값 (같으면 서버가 그림을 다시 안 싣는다)."""
        return (self.geo or {}).get("_digest")

    @staticmethod
    def _geo_of(mp):
        """지도 응답에 새 그림이 실려 왔으면 그것 (요약값을 붙여 둔다), 아니면 None (가진 것을 그대로 쓴다)."""
        geo = (mp or {}).get("geo")
        if not geo:
            return None
        geo = dict(geo)
        geo["_digest"] = mp.get("mapDigest")
        return geo

    def reload(self, after=None):
        def done(r, err):
            if not self.alive:
                return
            if err:
                return self.say("길드전을 불러오지 못했습니다. %s" % getattr(err, "message", err), U.DANGER)
            st, mp, geo, self.log = r
            self.st, self.mapdata = st, mp
            if geo is not None:
                self.geo = geo
            self.paint()
            if self.sel and self.wide:
                self._load_tile(self.sel)
            self._arm_poll()
            if after:
                after()
        run_async(self.root, self._fetch, done)

    def _arm_poll(self):
        """전략·전쟁 중에는 지도를 가끔 다시 받는다. 색과 순위만 고친다 (칸을 새로 그리지 않는다).
        단계가 넘어갔으면(전략 -> 전쟁 -> 끝) 통째로 다시 받는다."""
        if self._poll_job is not None or not self.alive:
            return
        if (self.st or {}).get("phase") not in ("plan", "war") or not self.wide:
            return

        def done(r, err):
            if not self.alive or err or self.busy:
                return self._arm_poll()
            st, mp = r
            if st.get("phase") != (self.st or {}).get("phase"):
                return self.reload()         # 단계가 넘어갔다 - 통째로 다시 받는다
            geo = self._geo_of(mp)
            if geo is not None:              # 지도 그림이 바뀌었다 (드물다) - 통째로 다시 그린다
                self.geo = geo
                self.st, self.mapdata = st, mp
                self.paint()
                return self._arm_poll()
            changed = (mp or {}).get("cells") != (self.mapdata or {}).get("cells")
            self.st, self.mapdata = st, mp
            if changed:
                self.map.set_state(mp)
                self._fill_ranking()
            self._arm_poll()

        def go():
            self._poll_job = None
            if self.alive:
                have = self._have()
                run_async(self.root, lambda: (self.app.api.guild_war(), self.app.api.guild_war_map(have)), done)
        try:
            self._poll_job = self.root.after(POLL_MS, go)
        except Exception:                                   # noqa: BLE001
            self._poll_job = None

    # ---------------- 그리기 ----------------
    def _layout(self, wide):
        """지도를 옆에 끼거나 뺀다."""
        if wide == self.wide:
            return
        self.wide = wide
        self.right.pack_forget()
        self.left.pack_forget()
        if wide:
            self.right.configure(width=self._side_w())
            self.right.pack_propagate(False)
            self.right.pack(side="right", fill="y")
            self.left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        else:
            self.right.pack_propagate(True)
            self.right.pack(side="left", fill="both", expand=True)

    def _side_w(self):
        """지도 옆 칸의 폭. 보통 크기에서는 예전 그대로(U.h(self.SIDE_W)).

        글자를 크게 하면 칸도 넓히되 **지도보다 넓어지지는 않게** (칸 전체의 45% 까지만, 보통 크기의 폭
        밑으로는 안 줄인다). 글자만큼 다 넓혔더니 '아주 크게' 에서 옆 칸(561)이 지도(397)보다 넓어져
        지도가 곁다리가 되었다. 옆 칸의 글은 접히고, 넘치면 굴러간다.
        """
        side = self.SIDE_W
        full = U.h(side)
        base = side * U.BASE_PT / (10.0 * U.TEXT_SIZES[U.TEXT_SIZE][1])     # 보통 크기의 폭
        if full <= base:
            return full
        try:
            room = self.holder.winfo_width()
        except tk.TclError:
            return full
        if room <= 1:
            return full
        return int(max(base, min(full, (room - 10) * 0.45)))

    def _fit_side(self):
        """창 크기가 바뀌면 옆 칸 폭을 다시 맞춘다 (지도를 낀 모양일 때만)."""
        if not self.wide:
            return
        w = self._side_w()
        try:
            if int(self.right.cget("width")) != w:
                self.right.configure(width=w)
        except (tk.TclError, ValueError):
            pass

    def _clear(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.buttons = {}
        self.tile_box = None
        self.rank_box = None

    def _card(self, title=None):
        c = U.framed(self.inner, bg=CARD)
        c.pack(fill="x", pady=(0, 10))
        if title:
            U.marker_label(c, title, bg=CARD).pack(anchor="w", padx=14, pady=(10, 2))
        return c

    def _text(self, parent, text, fg=None, font=None, pady=(0, 0), padx=14):
        lb = tk.Label(parent, text=text, bg=parent["bg"], fg=fg or U.FG_DIM, font=font or U.FONT_S,
                      anchor="w", justify="left")
        lb.pack(fill="x", padx=padx, pady=pady)
        U.wrap_to_width(lb)
        return lb

    def paint(self):
        st = self.st or {}
        ph = st.get("phase")
        cells = (self.mapdata or {}).get("cells")
        self._layout(ph in ("plan", "war", "done") and bool(cells) and self.geo is not None)
        wide = self.wide
        self._clear()
        head = self._card()
        row = tk.Frame(head, bg=CARD)
        row.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(row, text="시즌 %d 길드전" % (st.get("season") or 0), bg=CARD, fg=U.FG,
                 font=(U.FAMILY_BLACK, U.pt(14))).pack(side="left")
        U.chip(row, st.get("phaseKr") or "", PHASE_COLOR.get(ph, U.BG4), fg="#ffffff", padx=8).pack(
            side="left", padx=(10, 0))
        self._text(head, phase_line(st), fg=U.FG, pady=(2, 10 if wide else 2))
        if not wide:
            # 지도가 옆에 있을 때는 규칙을 맨 아래 칸으로 내린다 (좁은 칸의 머리가 길어지지 않게)
            self._text(head, rule_line(st), fg=U.FG_FAINT, font=U.FONT_XS)
            self._text(head, reward_line(st), fg=U.FG_FAINT, font=U.FONT_XS, pady=(0, 10))
        if st.get("battle"):
            self._battle_card()
        if ph == "apply":
            self._apply_card(st)
            self._teams_card(st)
        elif ph in ("plan", "war"):
            if st.get("entered"):
                self._war_card(st)
            else:
                c = self._card("전략 기간" if ph == "plan" else "전쟁 중")
                self._text(c, "우리 길드는 인원이 모자라 이번 길드전에 나가지 못했습니다." if st.get("dropped")
                           else "우리 길드는 이번 길드전에 참가하지 않았습니다." if st.get("guild")
                           else "길드에 들어가 있어야 참가할 수 있습니다.", pady=(0, 10))
        if wide:
            self._tile_card()
        if ph in ("plan", "war", "done"):
            self._ranking_card(st)
        if ph == "plan" and (st.get("can") or {}).get("manage"):
            self._plan_card(st)
        if ph in ("plan", "war") and st.get("entered"):
            self._teams_card(st)
        if ph in ("war", "done"):
            self._log_card()
        if wide:
            c = self._card("규칙")
            self._text(c, rule_line(st), fg=U.FG_FAINT, font=U.FONT_XS)
            self._text(c, reward_line(st), fg=U.FG_FAINT, font=U.FONT_XS, pady=(4, 10))
        if ph == "before":
            c = self._card("준비")
            self._text(c, "%s 동안 이어집니다. 신청·전략 기간에 방어팀과 공격팀을 짜 두세요." % schedule_line(st),
                       pady=(0, 10))
        if wide:
            self.map.set_geo(self.geo)
            self.map.set_state(self.mapdata)
            if self.sel and self.sel != self.map.selected:
                self.map.select(self.sel)
        self.fit.schedule()

    def _battle_card(self):
        c = U.framed(self.inner, bg="#2a2416", border=U.ACCENT)
        c.pack(fill="x", pady=(0, 10))
        b = U.PushButton(c, "이어서 하기", self.resume, height=30, font=U.FONT_B)
        b.pack(side="right", padx=10, pady=6)
        self.buttons["resume"] = b
        lb = tk.Label(c, text="끝나지 않은 길드전 승부가 있습니다.", bg=c["bg"], fg=U.FG, font=U.FONT_B,
                      anchor="w", justify="left")
        lb.pack(side="left", fill="x", expand=True, padx=14, pady=8)
        U.wrap_to_width(lb)

    # ---- 신청 ----
    def _apply_card(self, st):
        c = self._card("참가 신청")
        g = st.get("guild")
        if not g:
            return self._text(c, "길드에 들어가 있어야 참가할 수 있습니다.", pady=(0, 10))
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x", padx=14, pady=(2, 4))
        entered = st.get("entered")
        tk.Label(row, text="참가를 신청했습니다" if entered else "아직 신청하지 않았습니다", bg=CARD,
                 fg=U.GOOD if entered else U.FG, font=U.FONT_B).pack(side="left")
        if (st.get("can") or {}).get("apply"):
            if entered:
                b = U.ghost_button(row, "참가 취소", lambda: self.apply(False), height=30)
            else:
                b = U.PushButton(row, "참가 신청", lambda: self.apply(True), height=30, font=U.FONT_B)
                if g.get("members", 0) < (st.get("minMembers") or 5):
                    b.configure(state="disabled")
            b.pack(side="right")
            self.buttons["apply"] = b
        need = st.get("minMembers") or 5
        note = "길드원 %d명 (신청하려면 %d명 이상)." % (g.get("members", 0), need)
        if not (st.get("can") or {}).get("apply"):
            note += " 신청과 취소는 마스터와 부마스터가 합니다."
        self._text(c, note, fg=U.FG_FAINT, font=U.FONT_XS)
        names = [e["name"] for e in st.get("entries") or []]
        self._text(c, ("참가한 길드 %d곳: %s" % (len(names), ", ".join(names))) if names
                   else "아직 참가한 길드가 없습니다.", pady=(4, 2))
        self._text(c, "전략 기간이 시작되면 참가한 길드가 원형 지도를 %d칸씩 나눠 갖고 이 칸에 지도가 나타납니다. "
                      "전략 기간에 길드장이 공격 횟수와 지킬 칸을 정하고, 전쟁이 시작되면 우리 칸과 맞닿은 남의 칸을 "
                      "눌러 공격합니다." % (st.get("tilesPer") or 15),
                   fg=U.FG_FAINT, font=U.FONT_XS, pady=(0, 10))

    # ---- 내 팀 ----
    def _teams_card(self, st):
        teams = st.get("teams") or {}
        if not teams:
            return
        c = self._card("내 팀")
        can = (st.get("can") or {}).get("team")
        for kind, kr in KIND_KR:
            t = teams.get(kind) or {}
            row = tk.Frame(c, bg=CARD)
            row.pack(fill="x", padx=14, pady=(4, 0))
            tk.Label(row, text=kr, bg=CARD, fg=U.FG, font=U.FONT_B, width=6, anchor="w").pack(side="left")
            state = ("고정됨" if t.get("fixed") else "짜 둠" if t.get("set") else "안 짬 · 랭크 팀으로 나감")
            tk.Label(row, text=state, bg=CARD, fg=U.GOOD if t.get("fixed") or t.get("set") else U.FG_FAINT,
                     font=U.FONT_XS).pack(side="left", padx=(6, 0))
            if can:
                b = U.ghost_button(row, "바꾸기", lambda k=kind, n=kr: self.pick_team(k, n), height=28)
                b.pack(side="right")
                self.buttons["team_" + kind] = b
            self._text(c, team_text(t.get("mons") or []), fg=U.FG_DIM, pady=(2, 4))
        shown = st.get("shown") or 3
        self._text(c, ("전쟁이 시작되는 순간의 기술·도구·노력치로 고정됩니다. 그 뒤에 바꿔도 길드전에는 "
                       "그때 그 모습으로 나갑니다. 방어팀은 앞의 %d마리만 상대에게 미리 보입니다 (순서가 중요합니다)."
                       % shown) if can else
                   "전쟁이 시작될 때의 모습으로 고정됐습니다. 방어팀은 AI 가 굴려 내 칸을 지킵니다.",
                   fg=U.FG_FAINT, font=U.FONT_XS, pady=(2, 10))

    # ---- 전쟁 ----
    def _war_card(self, st):
        plan = st.get("phase") == "plan"
        c = self._card("전략 기간" if plan else "공격")
        a = st.get("attacks") or {}
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x", padx=14, pady=(2, 0))
        tk.Label(row, text=("내 몫 공격 %d번" % a.get("total", 0)) if plan else "남은 공격 %d번" % a.get("left", 0),
                 bg=CARD, fg=U.ACCENT if a.get("left") else U.FG_DIM,
                 font=(U.FAMILY, U.BASE_PT + 2, "bold")).pack(side="left")
        self._text(c, "전쟁이 시작되면 씁니다. 그때까지 길드장이 바꿀 수 있습니다." if plan
                   else "내 몫 %d번 중 %d번 씀" % (a.get("total", 0), a.get("used", 0)), fg=U.FG_FAINT,
                   font=U.FONT_XS, pady=(0, 4))
        mates = st.get("mates") or []
        mine = next((m for m in mates if m.get("userId") == getattr(self.gw, "my_id", None)), None)
        bits = []
        if mates:
            bits.append("우리 길드: 공격 %d / %d번 씀 · 받은 공격 %d / %d번" % (
                sum(m.get("used", 0) for m in mates), sum(m.get("attacks", 0) for m in mates),
                st.get("received", 0), st.get("total") or 30))
        if mine is not None:
            bits.append("내가 지키는 칸: %s (지도의 흰 점)" % (mine.get("tile") or "없음 - 빼앗겼습니다"))
        if plan:
            bits.append("전쟁이 시작되면 우리 칸과 맞닿은 남의 칸을 칠 수 있습니다. 지금은 지도에서 상대 칸의 "
                        "방어팀을 미리 살펴 두세요.")
        elif (self.mapdata or {}).get("hit") is not None:
            bits.append("지금 칠 수 있는 칸 %d곳 (우리 칸과 맞닿은 남의 칸)" % len(self.mapdata["hit"]))
        for i, text in enumerate(bits):
            self._text(c, text, fg=U.FG_FAINT, font=U.FONT_XS, pady=(0, 10 if i == len(bits) - 1 else 2))

    # ---- 고른 칸 ----
    def _tile_card(self):
        c = self._card("고른 칸")
        self.tile_box = tk.Frame(c, bg=CARD)
        self.tile_box.pack(fill="x")
        self._fill_tile()

    def _fill_tile(self):
        """고른 칸의 안쪽만 다시 그린다 (다른 칸은 그대로 둔다 - 굴려 둔 자리가 튀지 않게)."""
        box = self.tile_box
        if box is None:
            return
        try:
            for w in box.winfo_children():
                w.destroy()
        except tk.TclError:
            return
        for k in ("attack", "guard"):
            self.buttons.pop(k, None)
        t = self.tile
        if not self.sel:
            self._text(box, "지도에서 칸을 누르세요. 그 칸을 지키는 쪽과 방어팀이 보입니다.", pady=(0, 10))
            return self.fit.schedule()
        if t is None or t.get("region") != self.sel:
            name = ((self.mapdata or {}).get("cells") or {}).get(self.sel, {}).get("name") or ""
            self._text(box, "%s\n불러오는 중..." % name, pady=(0, 10))
            return self.fit.schedule()
        self._text(box, t.get("name") or "", fg=U.FG, font=U.FONT_B)
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x", padx=14, pady=(4, 0))
        tk.Frame(row, bg=self.map.colors.get(t.get("guildId"), WM.BLANK), width=U.h(12),
                 height=U.h(12)).pack(side="left", padx=(0, 6))
        tk.Label(row, text=t.get("guild") or "", bg=CARD, fg=U.ACCENT if t.get("mine") else U.FG,
                 font=U.FONT_B).pack(side="left")
        if t.get("mine"):
            tk.Label(row, text="우리 길드", bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left", padx=(6, 0))
        if t.get("taken"):
            self._text(box, "넘어간 칸입니다 (처음 주인 [%s]). 다시 뺏을 수 없습니다." % (t.get("home") or "?"),
                       fg=U.FG_FAINT, font=U.FONT_XS)
        self._text(box, "지키는 쪽: %s" % (t.get("guard") or "?"), fg=U.FG, pady=(4, 0))
        for m in t.get("team") or []:
            self._text(box, "%s  Lv.%d" % (m.get("kr") or "?", m.get("level") or 0), fg=U.FG_DIM, padx=24)
        if t.get("hidden"):
            self._text(box, "+ 가려진 %d마리 (싸워 봐야 압니다)" % t["hidden"], fg=U.FG_FAINT, padx=24)
        need = t.get("need") or 3
        if t.get("mine"):
            threats = t.get("threats") or []
            self._text(box, ("이 칸을 노리는 길드: " + ", ".join("[%s] %d승" % (x["guild"], x["wins"]) for x in threats))
                       if threats else "아직 이 칸을 이긴 길드가 없습니다.", fg=U.FG_FAINT, font=U.FONT_XS, pady=(4, 0))
            if t.get("manager"):
                self._guard_row(box, t)
        elif not t.get("taken"):
            self._text(box, "우리 길드: %d승 중 %d승 (같은 상대를 %d번 이기면 칸을 가져옵니다)"
                       % (need, t.get("wins", 0), need), fg=U.FG, font=U.FONT_XS, pady=(4, 0))
            self._text(box, "이 길드가 받은 공격 %d / %d" % (t.get("guildReceived", 0), t.get("guildMax", 30)),
                       fg=U.FG_FAINT, font=U.FONT_XS)
            b = U.PushButton(box, "이 칸 공격 (관장 배틀)", lambda r=t["region"]: self.attack(r),
                             height=32, font=U.FONT_B)
            b.pack(fill="x", padx=14, pady=(8, 2))
            if not t.get("can"):
                b.configure(state="disabled")
            self.buttons["attack"] = b
            if t.get("blocked"):
                self._text(box, "칠 수 없음: %s" % t["blocked"], fg=U.DANGER, font=U.FONT_XS)
        tk.Frame(box, bg=CARD, height=8).pack()
        self.fit.schedule()

    def _guard_row(self, box, t):
        """길드장: 이 칸을 지킬 길드원을 고른다."""
        if t.get("locked"):
            self._text(box, "공격받은 적이 있어 지키는 사람을 바꿀 수 없습니다.", fg=U.FG_FAINT, font=U.FONT_XS)
            return
        b = U.ghost_button(box, "지키는 사람 바꾸기", lambda: self.guard_menu(t), height=30)
        b.pack(fill="x", padx=14, pady=(8, 2))
        self.buttons["guard"] = b

    def guard_menu(self, t):
        rows = [{"text": "%s 에 배치할 길드원" % (t.get("name") or ""), "header": True}]
        for m in t.get("members") or []:
            here = m["userId"] == t.get("guardId")
            rows.append({"text": "%s  ·  %s" % (m["name"], "이 칸" if here else (m.get("tile") or "지키는 칸 없음")),
                         "command": (lambda u=m["userId"]: self.place(t["region"], u)), "enabled": not here,
                         "indent": 1})
        try:
            b = self.buttons["guard"]
            x, y = b.holder.winfo_rootx(), b.holder.winfo_rooty() + b.holder.winfo_height()
        except Exception:                                   # noqa: BLE001
            x, y = self.root.winfo_pointerx(), self.root.winfo_pointery()
        self.menu = U.PopupMenu(self.root, rows, x, y, width=U.h(SIDE_W))

    # ---- 순위 ----
    def _ranking_card(self, st):
        c = self._card("순위 (칸이 많은 길드가 이깁니다)")
        self.rank_box = tk.Frame(c, bg=CARD)
        self.rank_box.pack(fill="x")
        self._fill_ranking()
        if st.get("phase") == "done":
            self._text(c, "길드전이 끝났습니다. 보상(길드 코인)은 바로 들어갔고, 1위 길드의 칭호는 선물함에 있습니다.",
                       fg=U.FG_FAINT, font=U.FONT_XS, pady=(0, 10))

    def _fill_ranking(self):
        box = self.rank_box
        if box is None:
            return
        try:
            for w in box.winfo_children():
                w.destroy()
        except tk.TclError:
            return
        rows = (self.mapdata or {}).get("guilds") or (self.st or {}).get("ranking") or []
        if len(rows) < 2:
            self._text(box, "참가한 길드가 둘이 안 되어 싸움이 열리지 않았습니다.", pady=(0, 10))
            return self.fit.schedule()
        mine = ((self.st or {}).get("guild") or {}).get("id")
        grid = tk.Frame(box, bg=CARD)
        grid.pack(fill="x", padx=14, pady=(2, 10))
        for i, h in enumerate(("", "순위", "길드", "칸", "방어", "승리")):
            tk.Label(grid, text=h, bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS,
                     anchor="w" if i == 2 else "e").grid(row=0, column=i, sticky="we", padx=(0, 8))
        for r, x in enumerate(rows, 1):
            fg = U.ACCENT if x.get("guildId") == mine else U.FG
            tk.Frame(grid, bg=WM.color_of(x.get("color")), width=U.h(12), height=U.h(12)).grid(
                row=r, column=0, padx=(0, 8), pady=2)
            cells = ("%d위" % x.get("rank", r), x.get("name") or "", "%d" % x.get("tiles", 0),
                     "%d" % x.get("defends", 0), "%d" % x.get("wins", 0))
            for i, t in enumerate(cells, 1):
                lb = tk.Label(grid, text=t, bg=CARD, fg=fg, font=U.FONT_B if i in (2, 3) else U.FONT_S,
                              anchor="w" if i == 2 else "e", justify="left")
                lb.grid(row=r, column=i, sticky="we", padx=(0, 8), pady=1)
                if i == 2:
                    U.wrap_to_width(lb)          # 긴 길드 이름은 줄을 바꾼다 (글자를 줄이지 않는다)
        grid.grid_columnconfigure(2, weight=1)
        self.fit.schedule()

    # ---- 길드장: 공격 나누기 ----
    def _plan_card(self, st):
        mates = st.get("mates") or []
        if not mates:
            return
        c = self._card("공격 나누기 (길드장 · 전략 기간에만)")
        plan = self.plan or dict((m["userId"], m.get("attacks", 0)) for m in mates)
        self.plan = plan
        total = st.get("total") or 30
        self.plan_rows = {}
        for m in mates:
            uid = m["userId"]
            row = tk.Frame(c, bg=CARD)
            row.pack(fill="x", padx=14, pady=1)
            lo = max(1, m.get("used", 0))
            plus = U.ghost_button(row, "+", lambda u=uid: self.bump(u, 1), height=24)
            plus.pack(side="right")
            val = tk.Label(row, text="%d" % plan.get(uid, 0), bg=CARD, fg=U.FG, font=U.FONT_B, width=3)
            val.pack(side="right")
            minus = U.ghost_button(row, "-", lambda u=uid: self.bump(u, -1), height=24)
            minus.pack(side="right")
            lb = tk.Label(row, text="%s  (씀 %d)" % (m["name"], m.get("used", 0)), bg=CARD, fg=U.FG_DIM,
                          font=U.FONT_S, anchor="w", justify="left")
            lb.pack(side="left", fill="x", expand=True)
            U.wrap_to_width(lb)
            self.plan_rows[uid] = (val, lo)
        self.plan_sum = self._text(c, "", fg=U.FG_FAINT, font=U.FONT_XS, pady=(4, 0))
        b = U.PushButton(c, "나누기 저장", self.save_plan, height=30, font=U.FONT_B)
        b.pack(fill="x", padx=14, pady=(6, 10))
        self.buttons["plan"] = b
        self._plan_note(total)

    def _plan_note(self, total=None):
        total = total or (self.st or {}).get("total") or 30
        n = sum((self.plan or {}).values())
        try:
            self.plan_sum.configure(text="합 %d / %d번 · 한 사람 최소 1번 (이미 쓴 것보다 적게는 못 줄입니다)"
                                    % (n, total), fg=U.DANGER if n > total else U.FG_FAINT)
            self.buttons["plan"].configure(state="normal" if n <= total else "disabled")
        except (tk.TclError, KeyError, AttributeError):
            pass

    def bump(self, uid, d):
        val, lo = getattr(self, "plan_rows", {}).get(uid, (None, 1))
        if val is None or self.plan is None:
            return
        n = max(lo, self.plan.get(uid, 0) + d)
        self.plan[uid] = n
        try:
            val.configure(text="%d" % n)
        except tk.TclError:
            pass
        self._plan_note()

    def save_plan(self):
        plan = dict(self.plan or {})

        def then(st):
            self.st = st
            self.plan = None
            self.paint()
        self._call(lambda: self.app.api.guild_war_attacks(plan), "공격 횟수를 나눴습니다.", then)

    def _log_card(self):
        rows = self.log or []
        if not rows:
            return
        c = self._card("우리 길드의 판 (최근 %d판)" % len(rows))
        for x in rows[:20]:
            row = tk.Frame(c, bg=CARD)
            row.pack(fill="x", padx=14, pady=2)
            where = x.get("regionName") or ""
            if x.get("ours"):
                text = "%s → [%s] %s · %s" % (x.get("atkName"), x.get("defGuild") or "?", x.get("defName"), where)
            else:
                text = "[%s] %s → %s · %s" % (x.get("atkGuild") or "?", x.get("atkName"), x.get("defName"), where)
            mark, good = log_mark(x)
            tk.Label(row, text=mark, bg=CARD, fg=U.FG_FAINT if good is None else (U.GOOD if good else U.DANGER),
                     font=U.FONT_B, width=5, anchor="w").pack(side="left")
            lb = tk.Label(row, text=text, bg=CARD, fg=U.FG_DIM, font=U.FONT_XS, anchor="w", justify="left")
            lb.pack(side="left", fill="x", expand=True)
            U.wrap_to_width(lb)
        tk.Frame(c, bg=CARD, height=8).pack()

    # ---------------- 지도 ----------------
    def _hover(self, cid):
        """지도에서 포인터를 올린 칸을 한 줄로 적는다."""
        if not self.alive:
            return
        if not cid:
            text = MAP_HINT
        else:
            x = ((self.mapdata or {}).get("cells") or {}).get(cid) or {}
            gid = x.get("g")
            name = next((g["name"] for g in (self.mapdata or {}).get("guilds") or [] if g["guildId"] == gid), None)
            text = "%s · %s" % (x.get("name") or cid, "[%s]" % name if name else "?")
            if cid in ((self.mapdata or {}).get("hit") or []):
                text += " · 칠 수 있음"
        try:
            self.hint.configure(text=text)
        except tk.TclError:
            pass

    def pick(self, cid):
        """칸을 골랐다. 지키는 쪽과 방어팀을 서버에 묻는다."""
        self.sel = cid
        self.tile = None
        if self.map.selected != cid:
            self.map.select(cid)
        self._fill_tile()
        self._load_tile(cid)

    def _load_tile(self, cid):
        def done(r, err):
            if not self.alive or self.sel != cid:
                return
            if err:
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            self.tile = r
            self._fill_tile()
        run_async(self.root, lambda: self.app.api.guild_war_tile(cid), done)

    # ---------------- 하는 일 ----------------
    def _call(self, fn, ok_text, then=None):
        if self.busy:
            return
        self.busy = True

        def done(r, err):
            self.busy = False
            if not self.alive:
                return
            if err:
                self.say(getattr(err, "message", str(err)), U.DANGER)
                return self.reload()
            if ok_text:
                self.say(ok_text, U.GOOD)
            if then:
                then(r)
        run_async(self.root, fn, done)

    def apply(self, on):
        def then(st):
            self.st = st
            self.paint()
        self._call(lambda: self.app.api.guild_war_apply(on),
                   "길드전 참가를 신청했습니다." if on else "길드전 참가를 취소했습니다.", then)

    def place(self, region, uid):
        def then(r):
            self.tile = r
            self.reload()
        self._call(lambda: self.app.api.guild_war_guard(region, uid), "지키는 사람을 옮겼습니다.", then)

    def pick_team(self, kind, kr):
        """방어팀·공격팀 짜기 - 랭크 팀 창을 그대로 쓴다."""
        from .ui_season import TeamWindow
        api = self.app.api
        cur = ((self.st or {}).get("teams") or {}).get(kind) or {}

        def load():
            team = dict(api.pvp_team() or {})
            team["ids"] = [m["id"] for m in cur.get("mons") or [] if m.get("id")]
            team["registered"] = bool(cur.get("set"))
            return team, api.pokemon()

        def save(ids):
            st = api.guild_war_team(kind, ids)
            t = (st.get("teams") or {}).get(kind) or {}
            return {"registered": bool(t.get("set")), "ids": [m["id"] for m in t.get("mons") or []]}
        cap = (self.st or {}).get("levelCap") or 50
        shown = (self.st or {}).get("shown") or 3
        self.picker = TeamWindow(self.app, on_saved=self.reload, spec={
            "title": "길드전 " + kr, "load": load, "save": save, "saved": "%s을 저장했습니다." % kr,
            "note": ("길드전에서 %s 싸우는 팀입니다. 전쟁이 시작되는 순간의 기술·도구·노력치로 고정됩니다.\n"
                     "Lv.%d 넘는 포켓몬은 Lv.%d(으)로 싸웁니다. 전설·환상 포켓몬과 같은 포켓몬은 한 마리까지 "
                     "넣을 수 있습니다.%s"
                     % ("내 칸을 지키며 (AI 가 굴립니다)" if kind == "def" else "남의 칸을 칠 때 (직접 싸웁니다)",
                        cap, cap, "\n상대에게는 앞의 %d마리만 미리 보입니다." % shown if kind == "def" else ""))})

    def _open_battle(self, data):
        """관장 배틀 창에서 싸운다. 창을 닫으면 지도를 다시 받는다."""
        from .ui_gym_battle import GymBattleWindow
        self.battle = GymBattleWindow(self.app, data, on_close=self._battle_closed)

    def _battle_closed(self):
        self.battle = None
        self.tile = None
        if self.alive:
            self.reload()

    def attack(self, region):
        """그 칸에 승부를 건다 (공격권 하나를 쓴다)."""
        old = getattr(self.app, "gym_battle", None)
        if old is not None and getattr(old, "alive", False):
            try:
                old.win.lift()
            except Exception:                               # noqa: BLE001
                pass
            return self.say("진행 중인 승부를 먼저 끝내 주세요.", U.DANGER)
        self.say("승부를 준비하는 중...")
        self._call(lambda: self.app.api.guild_war_attack(region), "", self._open_battle)

    def resume(self):
        """끝나지 않은 길드전 승부를 이어서 한다."""
        self._call(lambda: self.app.api.gym_battle(), "", self._open_battle)
