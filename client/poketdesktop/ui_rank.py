# -*- coding: utf-8 -*-
"""랭킹 — 랭크 포인트(RP) 순으로 줄 세운 판.

시즌 2 부터 보이는 점수는 RP 다. 이기면 크게 오르고 지면 조금 내려가서
판을 한 만큼 올라간다. 티어는 볼 이름(몬스터볼 -> 마스터볼)이고, 마스터볼
안에서 RP 1등이 챔피언, 2~5등이 사천왕이다. 숨은 점수(MMR)는 화면에 안
나온다 - RP 가 한 판에 얼마나 움직일지를 정하는 데만 쓴다.

점수는 **내가 건 랜덤 배틀**만 움직인다. 상대는 접속해 있지 않아도 붙는
구조라(자는 사람의 팀을 가져와 돌린다), 걸려온 판까지 넣으면 자는 동안
남이 몇 번 걸었느냐로 내 등수가 정해진다.

배치(5판)를 마쳐야 표에 오른다.

**대전 기록** (1.12.1): 머리줄의 '대전 기록' 을 누르면 같은 칸이 내 전적으로 바뀐다 -
내가 건 판(공격)과 걸려온 판(방어)을 [전체 | 공격한 판 | 공격받은 판] 으로 걸러 보고,
로그가 남아 있는 판은 다시 본다. 그 자리에 있던 '칭호·명패' 는 마이페이지로 옮겼다.
"""
import datetime
import tkinter as tk

from . import skins
from . import ui_common as U
from . import ui_loading
from . import ui_season as S
from .ui_common import run_async

W, H = 900, 660

# 1·2·3 등만 색으로 구분한다. 그 아래까지 물들이면 표가 시끄러워진다.
MEDAL = {1: "#ffc043", 2: "#c9d1e6", 3: "#d08a52"}

# 목록을 나눠 만드는 크기(U.Chunked). 쉰 줄을 한 번에 만들면 그동안 창이
# 멈춘다. 카드에 단추가 없어 가벼우니 친구·대전보다 크게 끊는다. 첫 묶음은
# 첫 화면(카드 여덟 장 남짓)이면 된다.
FIRST_ROWS = 10
CHUNK_ROWS = 6

CARD_BG = "#161b28"

# 대전 기록 (1.12.1)
RECORD_LIMIT = 50
RESULT = {"win": ("승", U.GOOD), "lose": ("패", U.RED), "draw": ("무", U.FG_DIM)}
KIND = {"random": "랜덤 배틀", "friend": "친구 배틀", "live": "실시간 배틀"}
REC_FILTERS = (("all", "전체"), ("attack", "공격한 판"), ("defend", "공격받은 판"))
REC_EMPTY = {"all": "아직 대전 기록이 없습니다.\n랜덤 배틀로 한 판 붙어 보세요.",
             "attack": "내가 건 대전이 아직 없습니다.",
             "defend": "아직 나에게 걸려온 대전이 없습니다.\n"
                       "랜덤 배틀 상대로 뽑히거나 친구가 걸면 여기에 남습니다."}


def _date_kr(s):
    """2026-10-27 -> 10월 27일."""
    try:
        _y, m, d = (int(x) for x in (s or "").split("-"))
        return "%d월 %d일" % (m, d)
    except ValueError:
        return s or ""


def when_text(s):
    """2026-09-02T03:22:07+00:00 -> 09-02 12:22 (이 PC 의 시간대로). 서버는 UTC 로 보낸다."""
    if not s:
        return ""
    try:
        return datetime.datetime.fromisoformat(s).astimezone().strftime("%m-%d %H:%M")
    except ValueError:
        return s.replace("T", " ")[:16]


def rank_short_text(me, rules):
    """랭크전 조건(시즌 4)을 못 채웠으면 알릴 한 줄, 채웠거나 옛 서버면 None."""
    if me.get("rankReady") is not False:
        return None
    rm = (rules or {}).get("rankMin") or {}
    need, lv = int(rm.get("count") or 6), int(rm.get("level") or 50)
    return ("랭크전은 Lv.%d 이상 %d마리가 있어야 걸 수 있습니다 - 지금 %d마리. '랭크 팀' 에서 채우세요."
            % (lv, need, int(me.get("rankReadyCount") or 0)))


def today_text(fight):
    """머리줄에 적을 '오늘 몇 판 가능'. 하루 상한(랜덤 배틀 20판) 기준이다."""
    left = max(0, int(fight.get("left") or 0))
    cap = int(fight.get("dailyBattles") or 0)
    if not left:
        return "오늘은 다 했습니다 (%d판)" % cap if cap else "오늘은 다 했습니다"
    return "오늘 %d판 가능" % left


@skins.skinnable
class RankWindow(object):

    def __init__(self, app, parent=None):
        self.app = app
        self.root = app.root
        self.busy = False
        self._job = None          # 목록을 나눠 만드는 일 (U.Chunked)
        self.rows = []
        self.me = {}
        self.rules = {}
        self.hall = {}
        self.season = 1
        self.placement = 5
        self._reload_later = False   # 대전 재생이 끝나면 다시 읽기로 걸어 두었다 (reload)
        # 지금 보는 것: "rank"(순위표) 또는 "records"(대전 기록, 1.12.1)
        self.mode = "rank"
        self.records = []
        self.rec_summary = {}
        self.rec_filter = "all"

        self.win = U.panel(parent, self.root, "포스크탑 — 랭킹",
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
        self.title = tk.Label(inner, text="랭킹", bg=U.BG2, fg=U.FG,
                              font=(U.FAMILY_BLACK, U.pt(15)))
        self.title.pack(side="left", pady=17)
        self.sub = tk.Label(inner, text="", bg=U.BG2, fg=U.FG_DIM,
                            font=U.FONT_XS)
        self.sub.pack(side="left", padx=(12, 0))

        U.ghost_button(inner, "새로고침", self.reload,
                       height=32).pack(side="right", pady=15)
        # 칭호·명패가 있던 자리 (1.12.1 - 칭호·명패는 마이페이지로). 누르면 랭킹 <-> 대전 기록.
        self.mode_btn = U.ghost_button(inner, "대전 기록", self._toggle_mode, height=32)
        self.mode_btn.pack(side="right", padx=(0, 8), pady=15)
        U.ghost_button(inner, "랭크 팀", self._team,
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
        # **대전을 재생하는 동안에는 읽지 않는다** (1.12.1). 서버에는 점수가 이미 들어가
        # 있어서, 지금 읽으면 재생이 끝나기도 전에 RP·승패가 바뀌어 보인다. 끝나면 읽는다.
        playing = getattr(self.app, "match_playing", None)
        if playing is not None and playing():
            if not self._reload_later:
                self._reload_later = True
                self.app.after_match(self._reload_after)
            return self.say("대전이 끝나면 새로 불러옵니다", U.FG_FAINT)
        self.busy = True
        mode = self.mode
        wait = ui_loading.Overlay(self.win, "랭킹을 불러오는 중" if mode == "rank"
                                  else "대전 기록을 불러오는 중")

        def done(r, err):
            self.busy = False
            if mode != self.mode:
                wait.close()            # 받는 사이에 보는 것을 바꿨다 - 그쪽을 읽는다
                return self.reload()
            if err:
                wait.close()
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            try:
                if mode == "records":
                    self.records = r.get("records") or []
                    self.rec_summary = r.get("summary") or {}
                else:
                    self.rows = r.get("ranking") or []
                    self.me = r.get("me") or {}
                    self.rules = r.get("rules") or {}
                    self.hall = r.get("hall") or {}
                    self.season = r.get("season", 1)
                    self.placement = r.get("placement", 5)
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
        if mode == "records":
            run_async(self.root, lambda: self.app.api.pvp_records(RECORD_LIMIT), done)
        else:
            run_async(self.root, self.app.api.pvp_ranking, done)

    def _reload_after(self):
        self._reload_later = False
        try:
            if not self.win.winfo_exists():
                return                          # 그사이 창을 닫았다
        except tk.TclError:
            return
        self.reload()

    # ---------------- 그리기 ----------------
    def draw(self):
        keep = self._scroll_top()
        if self._job is not None:
            self._job.cancel()      # 옛 목록의 남은 카드가 새 목록 뒤에 붙지 않게
            self._job = None
        if self.mode == "records":
            return self._paint_records(self._records_head(), self._shown_records(), keep)
        self._paint_rank(self._rank_head(), keep)

    # ---- 무엇을 보일지 (글은 다 여기서 정한다 - 테마는 그리기만 한다)
    def _rank_head(self):
        """(제목, 머리줄의 작은 글)."""
        me = self.me
        bits = []
        if me.get("ranked"):
            mine = next((x for x in self.rows if x.get("me")), None)
            bits.append("%d위" % mine["rank"] if mine else "순위 밖")
        else:
            left = me.get("placementLeft", self.placement)
            bits.append("배치까지 %d판" % left if left else "곧 오릅니다")
        bits.append("%d전 %d승 %d패" % (me.get("games", 0), me.get("wins", 0),
                                      me.get("losses", 0)))
        # 오늘 랜덤 배틀을 몇 판 더 걸 수 있나 (1.9.0). 옛 서버는 안 실어 준다.
        fight = me.get("fight") or {}
        if fight.get("left") is not None:
            bits.append(today_text(fight))
        if self.rules.get("endsAt"):
            bits.append("%s까지" % _date_kr(self.rules["endsAt"]))
        return "랭킹  ·  시즌 %d" % self.season, "  ·  ".join(bits)

    def _empty_text(self):
        return "아직 순위표가 비어 있습니다.\n랜덤 배틀 %d판을 치르면 이름이 올라갑니다." % self.placement

    def _me_data(self):
        """내 티어와 다음 티어까지. 옛 서버(RP 없음)면 None."""
        me = self.me
        if "rp" not in me:
            return None
        lines = []
        if me.get("nextTierKr"):
            lines.append("%s까지 %d RP" % (me["nextTierKr"], me.get("rpToNext", 0)))
        elif me.get("tier") == "master":
            lines.append("마스터볼 RP 5위 안에 들면 사천왕, 1위면 챔피언")
        if me.get("floorRp"):
            lines.append("%d RP 아래로는 안 떨어짐" % me["floorRp"])
        if me.get("firstWinToday") is False:
            fw = (self.rules.get("rp") or {}).get("firstWin")
            if fw:
                lines.append("오늘 첫 승 +%d RP 남음" % fw)
        team = ("랭크 팀 %d마리" % me.get("teamSize", 0) if me.get("teamRegistered")
                else "랭크 팀 없음 · 바탕화면 파티 %d마리로 싸움" % me.get("teamSize", 0))
        lines.append(team)
        if me.get("restrictedDropped"):
            lines.append("전설·환상은 %d마리까지라 %d마리는 빠지고 싸움"
                         % (me.get("restrictedMax") or 1, me["restrictedDropped"]))
        if me.get("sameDropped"):
            lines.append("같은 포켓몬은 %d마리까지라 %d마리는 빠지고 싸움"
                         % (me.get("sameSpeciesMax") or 1, me["sameDropped"]))
        return {"tier": me.get("tier"), "tierKr": me.get("tierKr"),
                "rp": "%s RP" % format(int(me.get("rp") or 0), ","),
                "title": me.get("title"), "color": me.get("frameColor"),
                "lines": "  ·  ".join(lines),
                # 랭크전 조건 (시즌 4): 못 채우면 랜덤 배틀을 못 건다 - 누르기 전에 보이게
                "short": rank_short_text(me, self.rules)}

    RULES_NOTE = ("점수는 내가 건 랜덤 배틀만 오르내립니다. "
                  "걸려온 판과 친구 배틀은 점수에 들어가지 않습니다.")

    def _rules_data(self):
        """규칙과 이번 시즌 보상. 서버가 보낸 숫자 그대로 적는다. 규칙이 없으면(옛 서버) None."""
        r = self.rules
        if not r:
            return None
        tiers = []
        for t in r.get("tiers") or []:
            need = ("%d" % t["rp"]) if "rp" in t else ("%d명" % t.get("seats", 0))
            tiers.append((t.get("tier"), t.get("tierKr"), need))
        rp = r.get("rp") or {}
        text = []
        if rp.get("win") and rp.get("lose"):
            text.append("이기면 +%d~%d RP, 지면 -%d~%d RP (상대가 셀수록 더 오르고 덜 깎입니다)"
                        % (rp["win"][0], rp["win"][1], rp["lose"][0], rp["lose"][1]))
        if rp.get("firstWin"):
            text.append("하루 첫 승 +%d RP" % rp["firstWin"])
        if rp.get("lossGuard"):
            text.append("%d연패 뒤에는 절반만 깎임" % rp["lossGuard"])
        if r.get("safeRp"):
            text.append("슈퍼볼(%d RP)에 한 번 오르면 그 아래로 안 떨어짐" % r["safeRp"])
        if r.get("levelCap"):
            text.append("랜덤 배틀은 Lv.%d 상한 · 랭크 팀으로 싸움 · 점수가 비슷한 상대와 붙음"
                        % r["levelCap"])
        rm = r.get("rankMin") or {}
        if rm.get("count"):
            text.append("랭크전 참가 조건: Lv.%d 이상 포켓몬 %d마리 (못 채우면 걸 수도, 상대로 뽑히지도 않음)"
                        % (rm.get("level", 50), rm["count"]))
        if r.get("restrictedMax"):
            # 시즌 3 부터 랭크만이 아니라 모든 팀 배틀이다 (server/app/pvp.RESTRICTED_MAX)
            text.append("전설·환상 포켓몬은 한 팀에 %d마리까지 (랭크·친구·관장·레이드)"
                        % r["restrictedMax"])
        if r.get("sameSpeciesMax"):
            # 10/22: 같은 종도 한 마리 (server/app/pvp.SAME_SPECIES_MAX) - 전설 제한과 같은 곳에 건다
            text.append("같은 포켓몬은 한 팀에 %d마리까지 (랭크·친구·관장·레이드·길드전)" % r["sameSpeciesMax"])
        text.append("내가 건 랜덤 배틀만 점수에 들어갑니다")
        rewards = []
        for rw in r.get("rewards") or []:
            bits = [rw["egg"]] if rw.get("egg") else []
            if rw.get("title"):
                bits.append("칭호 '%s'" % rw["title"])
            if rw.get("frame"):
                bits.append(rw["frame"])
            if rw.get("shiny"):
                bits.append("이로치사탕 %d개" % rw["shiny"])
            # 도구와 도구가 아닌 보상 (시즌 4 부터: 기술머신 뽑기권 · 관장 등록)
            for it in rw.get("items") or []:
                n = int(it.get("count") or 1)
                bits.append(it.get("kr", "?") if n == 1 else "%s %d개" % (it.get("kr", "?"), n))
            bits.extend(rw.get("perks") or [])
            rewards.append((rw.get("tier"), rw.get("tierKr"), " · ".join(bits), rw.get("frameColor")))
        return {"tiers": tiers, "text": "\n".join(text), "rewards": rewards,
                "rewards_title": "시즌 보상 (도달한 최고 티어 · 사천왕과 챔피언은 끝날 때 자리)"}

    def _hall_data(self):
        """지난 시즌 명예의 전당: (제목, [(등수, 이름, 칭호, 점수 글)]). 없으면 None."""
        rows = (self.hall or {}).get("rows") or []
        if not rows:
            return None
        out = []
        for r in rows:
            if r.get("tierKr"):
                # 시즌 2 부터: 끝날 때의 티어(챔피언·사천왕은 자리)와 RP
                score = "%s · %d RP · %d승 %d패" % (
                    r["tierKr"], r.get("rp") or 0, r.get("wins", 0), r.get("losses", 0))
            else:
                score = "%d점 · %d승 %d패" % (
                    r.get("rating", 0), r.get("wins", 0), r.get("losses", 0))
            out.append((r.get("rank", 0), r.get("name", "?"), r.get("title"), score))
        return "시즌 %d 명예의 전당" % self.hall.get("season", 0), out

    def _row_data(self, r):
        """순위표의 한 줄."""
        streak = r.get("streak", 0)
        bits = ["%d전 %d승 %d패" % (r.get("games", 0), r.get("wins", 0),
                                  r.get("losses", 0))]
        if r.get("draws"):
            bits.append("%d무" % r["draws"])
        if streak >= 2:
            bits.append("%d연승" % streak)
        elif streak <= -2:
            bits.append("%d연패" % abs(streak))
        # 옛 서버는 rp 가 없다. 그때는 점수를 그대로.
        score = "%s RP" % format(int(r.get("rp") or 0), ",") if "rp" in r else "%d" % r.get("rating", 0)
        return {"mine": bool(r.get("me")), "rank": r.get("rank", 0), "tier": r.get("tier"),
                "tierKr": r.get("tierKr"), "name": r.get("name", "?"), "color": r.get("frameColor"),
                "title": r.get("title"), "bits": "  ·  ".join(bits), "score": score}

    def _records_head(self):
        s = self.rec_summary
        bits = ["랜덤 배틀 %d전 %d승 %d패" % (s.get("games", 0), s.get("wins", 0), s.get("losses", 0))]
        if s.get("draws"):
            bits[0] += " %d무" % s["draws"]
        fw, fl = s.get("friendWins", 0), s.get("friendLosses", 0)
        if fw or fl:
            bits.append("친구 배틀 %d승 %d패" % (fw, fl))
        bits.append("최근 %d판" % RECORD_LIMIT)
        return "대전 기록", "  ·  ".join(bits)

    REC_NOTE = ("공격한 판은 내가 건 대전, 공격받은 판은 나를 상대로 걸려온 대전입니다. "
                "점수와 상금은 내가 건 랜덤 배틀에만 붙습니다.")

    def _record_data(self, r):
        """대전 기록의 한 줄. watch = 다시 볼 수 있으면 대전 번호."""
        attack = r.get("started", True)
        bits = [KIND.get(r.get("kind"), r.get("kind") or ""), when_text(r.get("at")),
                "%d턴" % (r.get("turns") or 0),
                "남은 %d : %d" % (r.get("myLeft") or 0, r.get("foeLeft") or 0)]
        if r.get("rpDelta"):
            bits.append("RP %+d" % r["rpDelta"])
        if r.get("reward"):
            bits.append("%s원" % format(r["reward"], ","))
        if not attack:
            bits.append("점수·승패에 안 들어감")
        # 다시 보기: 로그가 남아 있는 판만 (옛 서버는 canReplay 가 없다 - 그때는 띄운다)
        watch = r.get("matchId") if (r.get("matchId") and r.get("canReplay", True)) else None
        return {"attack": attack, "result": r.get("result"), "foe": r.get("foe") or "?",
                "lead": self._lead_text(r), "bits": "  ·  ".join(b for b in bits if b), "watch": watch}

    # ---- 그리기 (테마마다 그리는 곳)
    def _paint_rank(self, head, keep):
        for w in self.list.winfo_children():
            w.destroy()
        # 카드는 위에서부터 나눠 만든다. 맨 위로 올려 둬야 먼저 만든 묶음이
        # 곧 보이는 화면이다 - 아래를 보던 채로 두면 아직 안 만든 자리가
        # 빈 채로 먼저 보인다. 다 만들면 보던 자리로 돌려놓는다 (_back_to).
        self.cv.yview_moveto(0)
        self.title.configure(text=head[0])
        self.sub.configure(text=head[1])

        self._me_card()
        self._rules_card()

        if not self.rows:
            tk.Label(self.list, text=self._empty_text(),
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S,
                     justify="center").pack(pady=36)
            self._hall()
            return self.fit.schedule()

        def finished():
            self._hall()
            self.fit.schedule()
            self._back_to(keep)

        self._job = U.Chunked(self.win, self.rows, self._card,
                              first=FIRST_ROWS, size=CHUNK_ROWS,
                              on_done=finished)
        self.fit.schedule()

    def _me_card(self):
        """내 티어와 다음 티어까지. 표 맨 위에 둔다 - 제일 먼저 궁금한 것이다."""
        d = self._me_data()
        if d is None:
            return          # 옛 서버. RP 가 없으면 그리지 않는다
        box = tk.Frame(self.list, bg=U.BG2, highlightthickness=2,
                       highlightbackground=d["color"] or U.LINE2)
        box.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(box, bg=U.BG2)
        inner.pack(fill="x", padx=14, pady=10)
        top = tk.Frame(inner, bg=U.BG2)
        top.pack(fill="x")
        chip = S.tier_chip(top, d["tier"], d["tierKr"], big=True)
        if chip:
            chip.pack(side="left")
        tk.Label(top, text=d["rp"],
                 bg=U.BG2, fg=U.FG, font=(U.FAMILY_BLACK, U.pt(14))).pack(
            side="left", padx=(10, 0))
        if d["title"]:
            tk.Label(top, text=d["title"], bg=U.BG2,
                     fg=d["color"] or U.ACCENT_TEXT,
                     font=U.FONT_S).pack(side="right")
        tk.Label(inner, text=d["lines"], bg=U.BG2, fg=U.FG_DIM,
                 font=U.FONT_XS, anchor="w", justify="left",
                 wraplength=W - 90).pack(fill="x", pady=(6, 0))
        if d["short"]:
            tk.Label(inner, text=d["short"], bg=U.BG2, fg=U.DANGER, font=U.FONT_XS, anchor="w",
                     justify="left", wraplength=W - 90).pack(fill="x", pady=(4, 0))

    def _rules_card(self):
        """규칙과 이번 시즌 보상."""
        d = self._rules_data()
        if d is None:
            note = tk.Label(
                self.list,
                text=self.RULES_NOTE,
                bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w",
                justify="left", wraplength=W - 80)
            note.pack(fill="x", pady=(0, 8))
            return
        box = tk.Frame(self.list, bg=CARD_BG, highlightthickness=1,
                       highlightbackground=U.LINE)
        box.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(box, bg=CARD_BG)
        inner.pack(fill="x", padx=14, pady=10)

        row = tk.Frame(inner, bg=CARD_BG)
        row.pack(fill="x")
        for tier, tier_kr, need in d["tiers"]:
            chip = S.tier_chip(row, tier, tier_kr)
            if not chip:
                continue
            chip.pack(side="left", padx=(0, 4))
            tk.Label(row, text=need, bg=CARD_BG, fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(side="left", padx=(0, 10))

        tk.Label(inner, text=d["text"], bg=CARD_BG, fg=U.FG_DIM,
                 font=U.FONT_XS, anchor="w", justify="left",
                 wraplength=W - 90).pack(fill="x", pady=(8, 0))

        if d["rewards"]:
            tk.Label(inner, text=d["rewards_title"],
                     bg=CARD_BG, fg=U.FG, font=U.FONT_B, anchor="w").pack(
                fill="x", pady=(10, 2))
            grid = tk.Frame(inner, bg=CARD_BG)
            grid.pack(fill="x")
            for i, (tier, tier_kr, text, color) in enumerate(d["rewards"]):
                chip = S.tier_chip(grid, tier, tier_kr)
                if chip:
                    chip.grid(row=i, column=0, sticky="w", pady=1)
                # 챔피언 줄은 길어서 한 줄에 다 안 들어간다 - 글씨를 줄이지 않고 줄을 바꾼다.
                # 폭은 카드 안쪽에서 티어 칸(가장 긴 '마스터볼')만큼 뺀 것.
                tk.Label(grid, text=text, bg=CARD_BG,
                         fg=color or U.FG_DIM,
                         font=U.FONT_XS, anchor="w", justify="left",
                         wraplength=W - 90 - U.h(110)).grid(
                    row=i, column=1, sticky="w", padx=(8, 0))

    def _hall(self):
        """지난 시즌 명예의 전당."""
        d = self._hall_data()
        if d is None:
            return
        title, rows = d
        tk.Label(self.list, text=title,
                 bg=U.BG, fg=U.FG, font=U.FONT_H, anchor="w").pack(
            fill="x", pady=(14, 4))
        box = tk.Frame(self.list, bg=CARD_BG, highlightthickness=1,
                       highlightbackground=U.LINE)
        box.pack(fill="x", pady=(0, 10))
        for rank, name, title_, score in rows:
            line = tk.Frame(box, bg=CARD_BG)
            line.pack(fill="x", padx=12, pady=3)
            tk.Label(line, text="%d" % rank, bg=CARD_BG,
                     fg=MEDAL.get(rank, U.FG_DIM), width=3, anchor="e",
                     font=U.FONT_B).pack(side="left")
            tk.Label(line, text=name, bg=CARD_BG, fg=U.FG,
                     font=U.FONT_B).pack(side="left", padx=(10, 0))
            if title_:
                tk.Label(line, text=title_, bg=CARD_BG, fg=U.ACCENT_TEXT,
                         font=U.FONT_XS).pack(side="left", padx=(8, 0))
            tk.Label(line, text=score, bg=CARD_BG, fg=U.FG_FAINT,
                     font=U.FONT_XS).pack(side="right")

    def _scroll_top(self):
        try:
            return self.cv.yview()[0]
        except tk.TclError:
            return 0.0

    def _back_to(self, top):
        """다 그린 뒤 보던 자리로 돌아간다.

        새로고침을 눌러도 1.2.2 까지는 보던 순위에 그대로 있었다. 나눠
        그리려고 맨 위로 올린 채로 두면 누를 때마다 맨 위로 튄다. 처음 열
        때는 top 이 0 이라 아무것도 안 한다.
        """
        if top <= 0:
            return
        try:
            self.fit.fit_now()
            self.cv.yview_moveto(top)
        except tk.TclError:
            pass

    def _card(self, r):
        d = self._row_data(r)
        mine = d["mine"]
        rank = d["rank"]
        # 내 줄은 금색 테두리로 찾기 쉽게. 목록이 길어지면 자기 줄을
        # 눈으로 뒤지게 된다. 명패를 단 사람은 그 색 테두리.
        edge = U.ACCENT if mine else (d["color"] or U.LINE)
        box = tk.Frame(self.list, bg=U.BG2 if mine else CARD_BG,
                       highlightthickness=2, highlightbackground=edge)
        box.pack(fill="x", pady=(0, 7))
        inner = tk.Frame(box, bg=box["bg"])
        inner.pack(fill="x", padx=13, pady=10)

        tk.Label(inner, text="%d" % rank, bg=box["bg"],
                 fg=MEDAL.get(rank, U.FG_DIM),
                 font=(U.FAMILY_BLACK, U.pt(13)), width=3,
                 anchor="e").pack(side="left")

        left = tk.Frame(inner, bg=box["bg"])
        left.pack(side="left", fill="x", expand=True, padx=(12, 0))
        top = tk.Frame(left, bg=box["bg"])
        top.pack(fill="x")
        chip = S.tier_chip(top, d["tier"], d["tierKr"])
        if chip:
            chip.pack(side="left", padx=(0, 8))
        tk.Label(top, text=d["name"], bg=box["bg"],
                 fg=d["color"] or (U.ACCENT if mine else U.FG),
                 font=U.FONT_B).pack(side="left")
        if mine:
            tk.Label(top, text="나", bg=U.ACCENT, fg="#14141a",
                     font=U.FONT_XS, padx=5).pack(side="left", padx=(8, 0))
        if d["title"]:
            tk.Label(top, text=d["title"], bg=box["bg"],
                     fg=d["color"] or U.ACCENT_TEXT,
                     font=U.FONT_XS).pack(side="left", padx=(8, 0))

        tk.Label(left, text=d["bits"], bg=box["bg"], fg=U.FG_FAINT,
                 font=U.FONT_XS).pack(anchor="w", pady=(4, 0))

        tk.Label(inner, text=d["score"], bg=box["bg"], fg=U.FG,
                 font=U.FONT_NUM).pack(side="right")

    # ---------------- 대전 기록 (1.12.1) ----------------
    def _toggle_mode(self):
        self.mode = "records" if self.mode == "rank" else "rank"
        self.mode_btn.configure(text="랭킹" if self.mode == "records" else "대전 기록")
        self.reload()

    def _pick_filter(self, key):
        self.rec_filter = key
        self.draw()

    def _shown_records(self):
        if self.rec_filter == "attack":
            return [r for r in self.records if r.get("started", True)]
        if self.rec_filter == "defend":
            return [r for r in self.records if not r.get("started", True)]
        return list(self.records)

    def _paint_records(self, head, rows, keep):
        for w in self.list.winfo_children():
            w.destroy()
        self.cv.yview_moveto(0)
        self.title.configure(text=head[0])
        self.sub.configure(text=head[1])

        bar = tk.Frame(self.list, bg=U.BG)
        bar.pack(fill="x", pady=(0, 8))
        self.rec_seg = U.Segmented(bar, REC_FILTERS, self.rec_filter, self._pick_filter)
        self.rec_seg.pack(side="left")
        tk.Label(self.list, text=self.REC_NOTE,
                 bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left",
                 wraplength=W - 80).pack(fill="x", pady=(0, 8))

        if not rows:
            tk.Label(self.list, text=REC_EMPTY.get(self.rec_filter, REC_EMPTY["all"]),
                     bg=U.BG, fg=U.FG_FAINT, font=U.FONT_S, justify="center").pack(pady=36)
            return self.fit.schedule()

        def finished():
            self.fit.schedule()
            self._back_to(keep)
        self._job = U.Chunked(self.win, rows, self._record_card,
                              first=FIRST_ROWS, size=CHUNK_ROWS, on_done=finished)
        self.fit.schedule()

    def _lead_text(self, r):
        """'피카츄 vs 꼬부기' - 양쪽 선두. 도감이 없거나 모르는 종이면 빈 글."""
        dex = getattr(self.app, "dex", None)

        def kr(sp):
            got = dex.get(sp) if (dex and sp) else None
            return (got or {}).get("kr") or ""
        a, b = kr(r.get("lead")), kr(r.get("foeLead"))
        return "%s vs %s" % (a, b) if a and b else ""

    def _record_card(self, r):
        d = self._record_data(r)
        attack = d["attack"]
        box = tk.Frame(self.list, bg=CARD_BG, highlightthickness=2,
                       highlightbackground=U.LINE)
        box.pack(fill="x", pady=(0, 7))
        inner = tk.Frame(box, bg=CARD_BG)
        inner.pack(fill="x", padx=13, pady=10)

        left = tk.Frame(inner, bg=CARD_BG)
        left.pack(side="left", fill="x", expand=True)
        top = tk.Frame(left, bg=CARD_BG)
        top.pack(fill="x")
        mark, color = RESULT.get(d["result"], ("?", U.FG_DIM))
        tk.Label(top, text=mark, bg=color, fg="#14141a",
                 font=(U.FAMILY_BLACK, U.pt(11)), width=3).pack(side="left")
        U.chip(top, "공격" if attack else "방어", U.ACCENT if attack else U.INFO,
               font=U.FONT_XS, padx=6).pack(side="left", padx=(8, 0))
        tk.Label(top, text=d["foe"], bg=CARD_BG, fg=U.FG,
                 font=U.FONT_B).pack(side="left", padx=(9, 0))
        if d["lead"]:
            tk.Label(top, text=d["lead"], bg=CARD_BG, fg=U.FG_DIM,
                     font=U.FONT_XS).pack(side="left", padx=(10, 0))

        tk.Label(left, text=d["bits"], bg=CARD_BG,
                 fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left",
                 wraplength=W - 260).pack(anchor="w", fill="x", pady=(4, 0))

        if d["watch"]:
            U.ghost_button(inner, "다시 보기", lambda m=d["watch"]: self._watch(m),
                           height=30).pack(side="right")

    def _watch(self, mid):
        playing = getattr(self.app, "match_playing", None)
        if playing is not None and playing():
            return self.say("보고 있는 대전이 끝난 뒤에 봐 주세요.", U.DANGER)
        self.app.watch_match(mid)

    # ---------------- 동작 ----------------
    def _random(self):
        self.say("상대를 찾는 중...", U.FG_FAINT)
        self.app.pvp_random(on_done=self._battle_done, on_found=self._found)

    def _found(self, r):
        """상대를 찾았다 - 이제 바탕화면에서 재생한다. 점수는 재생이 끝나야 바뀐다 (1.12.1)."""
        try:
            self.say("대전 중... 끝나면 점수가 반영됩니다", U.FG_FAINT)
        except Exception:                                   # noqa: BLE001
            pass                                            # 그사이 창을 닫았다

    def _battle_done(self, r, why):
        """대전이 끝났다 (막혔거나, 성사돼서 재생까지 끝났다). '찾는 중' 글을 걷는다."""
        try:
            if why:
                self.say(why, U.DANGER)
            else:
                self.say("")
                self.reload()
        except Exception:                                   # noqa: BLE001
            pass                                            # 그사이 창을 닫았다

    def _team(self):
        S.TeamWindow(self.app, on_saved=self.reload)

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
        if getattr(self.app, "rank_window", None) is self:
            self.app.rank_window = None
