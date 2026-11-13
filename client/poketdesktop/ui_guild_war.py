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
  · 시즌 5 (서버가 jokerMax · contrib 를 보낼 때만): 길드장이 전략 기간에 우리 칸을 눌러 그 칸을 지키는
    길드원을 **조커로 숨긴다** (길드마다 3명). 남의 조커 칸은 서버가 이름·방어팀을 '???' 로 보낸다 - 지도에는
    '?' 표시. 판이 끝날 때마다 받는 **기여 보상**(이기면 · 조커를 이기면 · 막아 내면)을 규칙 칸에 적는다.
  · 전략·전쟁 중에는 지도를 30초마다 다시 받는다 (다른 길드가 뺏는 것이 보이게, 단계가 넘어가면
    통째로 다시 받게). 색만 고친다.

길드 창은 길드원 누가 미션을 끝내기만 해도 칸을 통째로 다시 만든다. 그때 보던 자리(확대·고른 칸)와
받아 둔 것을 길드 창에 맡겨 두었다가(war_keep) 이어서 그린다 - 지도가 깜빡이며 처음으로 돌아가지 않게.

오른쪽 칸은 길어질 수 있어 안쪽을 굴린다 (창을 키우지 않는다).

## 1:1 맞대결 (시즌 7~, 설계 design-notes/2026-11-12-guild-war-1v1.md)

서버가 state 에 `"mode": "match"` 를 실으면 지도 대신 **맞대결 판**을 낀다 (없으면 위의 지도전 그대로 - 옛 서버 ·
시즌 6 까지). 인원이 비슷한 길드끼리 1:1 (홀수면 세 길드 삼각형: 우리 -> B, C -> 우리), 한 사람 2번 공격, 별 ★~★★★,
길드 성적은 별 %.

    왼쪽   맞대결 판: 위에 [우리] 별 % · 쓰러뜨린 비율 · 남은 공격 vs [상대] (삼각형이면 '우리가 칠 길드' ·
           '우리를 치는 길드' 두 줄), 앞서는 쪽 · 결과. 아래에 상대 출전 명단 한 줄씩 (이름 · 방어팀 앞 3마리 ·
           받은 최고 별 · 조커는 '???' · 내가 이미 쳤는지). 줄을 누르면 오른쪽 '고른 상대' 에 미리보기 + [공격].
    오른쪽 내 남은 공격(●● / ●○ / ○○) · 고른 상대 · (길드장 · 전략) 출전 명단 고르기 · 우리 명단(남은 공격 · 얻은 별 ·
           막아 낸 것, 길드장은 조커 지정) · 이번 시즌 맞대결 · 내 팀 · 기록(별) · 별 규칙 · 보상 · 규칙.

  · 보상은 **길드 코인만** (설계 design-notes/2026-11-12-guild-war-rewards.md). 순위 · 금관 같은 꾸미기 · 칭호 ·
    기술머신 뽑기권이 없다 - 서버가 rewards [] · tmActive None · ranking [] 을 싣고, 코인 규칙은 coinRules 로 온다
    (판마다 별 코인 · 조커 · 막기 · 한 시즌 상한, 결산 이김 / 비김 / 짐). 보상 칸은 그것을 표로, 내 contrib.earned 와 함께.
  · 순위 칸 자리에 **이번 시즌 맞대결** (서버 matches): 짝(삼각형은 셋)마다 한 덩어리, 우리 판이 맨 위(서버 차례).
    길드마다 별 % · 쓰러뜨린 비율 · 승패 (final 이 아니면 '앞섬' - 지금까지의 별로 본 것). 줄 세우는 순위는 없다.
  · 끝나면(done) 맨 위에 결산 칸: 우리 판 결과와 받은 결산 코인 (coinRules.result[결과], 공격을 한 번이라도 했으면).
  · 공격 창을 닫으면 그 판의 별과 코인 줄(서버 reward.lines 의 '길드 코인 ...')을 길드 창 알림 줄에 띄운다 -
    관장 배틀 창의 결과 칸은 이긴 판에만 서버 줄을 적어서, 지고도 ★ 을 얻은 판의 코인이 안 보였다.

  · 상대 명단은 `/api/guild/war/match` 한 번에 다 온다 (줄을 눌러도 서버에 안 묻는다). 조커로 가려진 상대는 이름이
    '???' 이고 userId 가 음수(자리 표시)다 - 그 값을 그대로 열쇠로 쓰고 공격할 때도 그대로 보낸다.
  · 공격은 지도전과 같은 관장 배틀 창 (POST /attack {target}). 창이 닫히면 다시 받는다.
  · 전략 · 전쟁 중에는 POLL_MS 마다 다시 받아 판 · 명단 · 고른 상대 · 순위만 고친다 (굴려 둔 자리 그대로).
"""
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from common import tint as T

from . import skins, sprite_cache, sprites
from . import ui_common as U
from . import ui_war_map as WM
from .ui_common import run_async
from .ui_spectate import star_text

CARD = "#161b28"
PHASE_COLOR = {"before": U.BG4, "apply": U.INFO, "plan": U.PINK, "war": U.DANGER, "done": U.FG_DIM}
KIND_KR = (("def", "방어팀"), ("atk", "공격팀"))
SIDE_W = 330                 # 지도 옆 칸의 폭
POLL_MS = 30000              # 전략·전쟁 중에 지도를 다시 받는 간격
MAP_HINT = "칸을 누르면 지키는 쪽과 방어팀이 보입니다 · 휠로 확대 · 키운 뒤에는 끌어서 옮기기"
THUMB = 40                   # 맞대결 판 · 고른 상대의 도트 한 변 (그림이라 글자 크기로 키우지 않는다)
STAR_RULES = ("상대 방어팀 절반 이상 쓰러뜨림", "이김", "이기고 내 팀 절반 이상 남음")    # 서버가 안 실으면


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


def is_match(st):
    """1:1 맞대결 시즌(시즌 7~)인가. 서버가 state 에 mode='match' 를 실을 때만 - 없으면 지도전."""
    return (st or {}).get("mode") == "match"


def pct_text(x):
    """0~100 실수 -> '54.2%' (딱 떨어지면 '50%')."""
    try:
        x = float(x or 0)
    except (TypeError, ValueError):
        x = 0.0
    return ("%d%%" % round(x)) if abs(x - round(x)) < 0.05 else ("%.1f%%" % x)


def dots(left, total):
    """남은 공격 -> ●● / ●○ / ○○."""
    try:
        total = max(0, int(total or 0))
        left = max(0, min(total, int(left or 0)))
    except (TypeError, ValueError):
        return ""
    return "●" * left + "○" * (total - left)


def ratio_text(x):
    try:
        return ("%.1f" % float(x)).rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "1.2"


def match_phase_line(st):
    """1:1 맞대결: 단계 이름 옆에 적을 한 줄."""
    ph, left = st.get("phase"), span_text(st.get("endsIn"))
    if ph == "before":
        return "시즌이 시작하면 참가 신청을 받습니다 (%s 뒤)." % left
    if ph == "apply":
        return "전략 기간이 시작될 때까지 %s. 그때 명단이 고정되고 상대가 발표됩니다." % left
    if ph == "plan":
        return "전쟁이 시작될 때까지 %s. 그때 출전 명단 · 조커 · 팀이 고정됩니다." % left
    if ph == "war":
        return "전쟁이 끝날 때까지 %s." % left
    return "이번 시즌의 길드전이 끝났습니다."


def match_rule_line(st):
    each = int(st.get("each") or 2)
    out = ("%s. 전략 기간이 시작될 때 출전 인원이 비슷한 길드끼리 1:1 로 맞붙습니다 (길드 수가 홀수면 세 길드가 "
           "삼각형으로 - 한 길드를 치고 다른 한 길드에게 맞습니다). 전쟁이 시작되면 한 사람이 %d번, 상대 출전 명단에서 "
           "골라 관장 배틀처럼 직접 칩니다 (같은 사람은 한 번만, 넘겨줄 수 없음). 상대 방어팀은 앞에서부터 %d마리만 "
           "미리 보입니다. 별 %% 가 높은 길드가 이기고, 같으면 쓰러뜨린 비율로 가립니다. 인원이 다르면 큰 길드는 작은 "
           "길드의 %s배까지만 나갑니다 (나갈 사람은 길드장이 고름). 팀은 Lv.%d 상한에 전설·환상 한 마리, 같은 포켓몬 "
           "한 마리까지입니다."
           % (schedule_line(st), each, st.get("shown") or 3, ratio_text(st.get("capRatio") or 1.2),
              st.get("levelCap") or 50))
    if st.get("jokerMax"):
        out += (" 길드장은 전략 기간에 길드원을 %d명까지 조커로 숨길 수 있습니다 - 상대에게는 이름과 방어팀이 '???' 로 "
                "보이고, 한 번 붙어 본 길드에게만 보입니다." % st["jokerMax"])
    return out


COIN_RULES = {"stars": [20, 40, 60], "joker": 20, "defend": 20, "max": 300,       # 서버가 coinRules 를 안 실으면
              "result": {"win": 100, "draw": 60, "lose": 30}}
RESULT_WORD = (("win", "이김"), ("draw", "비김"), ("lose", "짐"))


def coin_rules(st):
    """1:1 맞대결의 코인 규칙 (서버 coinRules, 빠진 칸은 설계값으로)."""
    c = dict(COIN_RULES)
    got = (st or {}).get("coinRules")
    if isinstance(got, dict):
        c.update((k, v) for k, v in got.items() if v is not None)
    return c


def earned_of(st):
    """이번 시즌에 판마다 받은 길드 코인 (contrib.earned)."""
    try:
        return int(((st or {}).get("contrib") or {}).get("earned") or 0)
    except (TypeError, ValueError):
        return 0


def earned_text(st):
    """'이번 시즌 40 / 300개' - 판마다 받는 코인이 상한까지 얼마나 찼나."""
    return "이번 시즌 %d / %d개" % (earned_of(st), int(coin_rules(st).get("max") or 0))


def match_reward_lines(st):
    """1:1 맞대결의 보상 안내 (줄마다) - 보상은 길드 코인만 (시즌 7, 순위 보상이 없다)."""
    c = coin_rules(st)
    stars = list(c.get("stars") or [])[:3]
    res = c.get("result") or {}
    out = ["보상은 길드 코인만입니다 (순위 · 꾸미기 · 칭호 · 뽑기권은 없습니다)."]
    if len(stars) == 3:
        out.append("공격 한 판이 끝나면 공격한 사람에게 ★ %d · ★★ %d · ★★★ %d개, 조커를 이기면 +%d개. 공격을 막아 내면 "
                   "(공격팀을 다 쓰러뜨림) 지킨 사람에게 %d개. 판마다 받는 코인은 한 사람 한 시즌 %d개까지 (%s)."
                   % (stars[0], stars[1], stars[2], int(c.get("joker") or 0), int(c.get("defend") or 0),
                      int(c.get("max") or 0), earned_text(st)))
    out.append("결산: 한 번이라도 공격한 길드원에게 우리 길드의 맞대결 결과로 %s개 (상한 밖)."
               % " · ".join("%s %d" % (kr, int(res.get(k) or 0)) for k, kr in RESULT_WORD))
    return out


def match_result_text(res, final, plan=False):
    """맞대결 목록의 승패 글과 빛깔. 전쟁 중(final 아님)에는 지금까지의 별로 본 앞섬 · 뒤짐."""
    if plan or res not in ("win", "lose", "draw"):
        return "-", U.FG_FAINT
    if final:
        return {"win": ("승", U.GOOD), "lose": ("패", U.DANGER), "draw": ("비김", U.FG)}[res]
    return {"win": ("앞섬", U.GOOD), "lose": ("뒤짐", U.DANGER), "draw": ("같음", U.FG_DIM)}[res]


def match_cycle(guilds):
    """삼각형의 도는 차례 '[A] → [B] → [C] → [A]' (vs = 그 길드가 칠 길드). 못 이으면 빈 글."""
    by = dict((g.get("name"), g) for g in guilds or [])
    if len(by) < 3:
        return ""
    start = (guilds[0] or {}).get("name")
    path, cur = [start], start
    for _i in range(len(by)):
        cur = (by.get(cur) or {}).get("vs")
        if cur not in by:
            return ""
        path.append(cur)
        if cur == start:
            break
    if path[-1] != start or len(path) != len(by) + 1:
        return ""
    return " → ".join("[%s]" % x for x in path)


def match_end_line(reward):
    """1:1 공격 창을 닫은 뒤 길드 창에 띄울 한 줄 ('★★☆  길드 코인 40개 - 이번 시즌 80 / 300개.').

    코인 글은 서버 결과 줄(reward.lines 의 '길드 코인 ...')을 그대로 쓴다. 지도전 · 끝나지 않은 판이면 None."""
    war = (reward or {}).get("war") or {}
    if war.get("mode") != "match" or war.get("stars") is None:
        return None
    n = int(war.get("stars") or 0)
    head = star_text(n)
    line = next((x for x in reward.get("lines") or [] if "길드 코인" in str(x)), None)
    if line:
        return "%s  %s" % (head, line)
    if war.get("coins"):
        return "%s  길드 코인 %d개." % (head, int(war["coins"]))
    if not n:
        return "%s  별을 얻지 못해 길드 코인은 없습니다." % head
    return head


def match_log_text(x):
    """1:1 맞대결 기록 한 줄 (공격마다 별)."""
    if x.get("ours"):
        text = "%s → [%s] %s" % (x.get("atkName"), x.get("defGuild") or "?", x.get("defName"))
    else:
        text = "[%s] %s → %s" % (x.get("atkGuild") or "?", x.get("atkName"), x.get("defName"))
    if x.get("result") != "pending" and x.get("stars") is not None:
        text += " · %s" % star_text(x["stars"])
        if x.get("ko") is not None:
            text += " (%d마리 쓰러뜨림)" % int(x["ko"])
    return text


def lead_line(st, m):
    """맞대결 판 아래의 한 줄: 결과 또는 지금 누가 앞서나. (글, 빛깔)"""
    res = m.get("result")
    if res == "win":
        return "승리! 우리 길드가 이겼습니다.", U.GOOD
    if res == "lose":
        return "패배 - 이번 맞대결은 졌습니다.", U.DANGER
    if res == "draw":
        return "비김 - 별 % 도 쓰러뜨린 비율도 같습니다.", U.FG
    if st.get("phase") == "plan":
        return "상대가 발표됐습니다. 전쟁이 시작되면 별이 쌓입니다.", U.FG
    lead = m.get("lead")
    if lead == "us":
        return "지금은 우리가 이기고 있습니다.", U.GOOD
    if lead == "them":
        return "지금은 우리가 지고 있습니다.", U.DANGER
    return "지금은 비기고 있습니다 (별 % 가 같습니다).", U.FG_DIM


def phase_line(st):
    """단계 이름 옆에 적을 한 줄."""
    if is_match(st):
        return match_phase_line(st)
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
    if is_match(st):
        return match_rule_line(st)
    return ("%s. 참가한 길드가 원형 지도를 같은 모양으로 %d칸씩 나눠 갖고(이웃 길드는 양옆 두 곳), 전쟁이 "
            "시작되면 우리 칸과 맞닿은 남의 칸을 관장 "
            "배틀처럼 직접 칩니다. 그 칸을 지키는 같은 상대를 %d번 이기면 칸을 가져오고, 넘어간 칸은 다시 "
            "못 뺏습니다. 칸이 가장 많은 길드가 이깁니다. 공격은 길드 합쳐 %d번 - 길드장이 전략 기간에 나눠 "
            "줍니다 (한 사람 최소 1번). 길드원은 한 사람이 한 칸씩 지키고(길드장이 전략 기간에 옮긴다), 남는 "
            "칸은 AI 수비대가 지킵니다. 남의 방어팀은 앞에서부터 %d마리만 미리 보입니다. 팀은 Lv.%d 상한에 "
            "전설·환상 한 마리, 같은 포켓몬 한 마리까지입니다."
            % (schedule_line(st), st.get("tilesPer") or 15, st.get("need") or 3, st.get("total") or 30,
               st.get("shown") or 3, st.get("levelCap") or 50)) + joker_line(st)


def joker_line(st):
    """시즌 5: 조커 규칙 한 문장 (옛 서버 · 시즌 4 면 빈 글)."""
    if not st.get("jokerMax"):
        return ""
    return (" 길드장은 전략 기간에 길드원을 %d명까지 조커로 숨길 수 있습니다 - 다른 길드에는 그 칸을 지키는 사람과 "
            "방어팀이 '???' 로 보이고(지도의 ? 칸), 한 번 붙어 본 길드에게만 보입니다." % st["jokerMax"])


def reward_line(st):
    if is_match(st):
        return "\n".join(match_reward_lines(st))
    rewards = st.get("rewards") or []
    if any("deco" in r for r in rewards):
        # 시즌 5 결산 보상 (2.0.2): 순위마다 길드 코인 + 꾸미기 + 랜덤 기술머신 뽑기권
        bits = []
        for r in rewards:
            one = "%s 코인 %d · %s" % ("%d위" % r["rank"] if r.get("rank") else "그 밖", r["coins"], r.get("deco") or "")
            if r.get("tm"):
                one += " · 뽑기권 %d장" % r["tm"]
            bits.append(one)
        out = "보상(한 번이라도 공격한 길드원): %s / 1위 길드에는 칭호 '%s'" % (" / ".join(bits), st.get("title") or "")
        act = st.get("tmActive") or {}
        out += ("\n뽑기권은 랜덤 기술머신 뽑기권 - 공격에서 이긴 길드원만 받습니다. 활약 보상: 공격에서 %d번 이상 이기면 "
                "순위와 상관없이 %d장 (순위 몫이 있으면 거기에 더)" % (int(act.get("wins") or 3), int(act.get("count") or 1)))
    else:
        bits = []
        for r in rewards:
            bits.append(("%d위 %d" % (r["rank"], r["coins"])) if r.get("rank") else "그 밖 %d" % r["coins"])
        out = "보상(길드 코인, 한 번이라도 공격한 길드원): %s · 1위 길드에는 칭호 '%s'" % (
            " · ".join(bits), st.get("title") or "")
    c = st.get("contrib")
    if c:
        out += ("\n기여 보상(판이 끝나면 바로): 공격에서 이기면 %d · 조커를 이기면 %d · 내 칸이 상대를 다 "
                "쓰러뜨려 막으면 %d (기권 · 시간 초과는 없음, 한 시즌 %d개까지, 지금 %d개)" % (c["win"], c["win"] + c["joker"], c["defend"], c["max"],
                                            c.get("earned", 0)))
    return out


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
        self.coin_box = None         # 1:1 보상 칸 (코인 규칙 · 내 몫 - 다시 받으면 이것만 고친다)
        self.menu = None
        self._poll_job = None
        # 1:1 맞대결 (시즌 7~)
        self.mview = None            # 서버 match_view (상대 출전 명단 · 우리 명단)
        self.foe_sel = None          # 고른 상대 (match 의 userId - 가려진 조커는 음수 자리 표시)
        self.roster_out = None       # 길드장이 고치는 중인 출전 명단 - 뺄 사람들 (전략 기간)
        self.foe_box = None
        self.mates_box = None
        self.foe_rows = {}           # 맞대결 판의 줄 {userId: 틀}
        self.thumbs = {}             # {(도감 번호, 색): PhotoImage}
        self._thumb_wait = {}        # 그림을 기다리는 라벨 {(번호, 색): [라벨]}
        self._thumb_busy = set()
        self._board_on = False       # 왼쪽에 지도 대신 맞대결 판을 꼈나

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
        self._build_board()          # 1:1 맞대결 판 (지도 자리에 낀다 - 지금은 안 담는다)
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
            self.mview, self.foe_sel, self.roster_out = keep.get("mview"), keep.get("foe"), keep.get("roster")
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
                                "tile": self.tile, "plan": self.plan, "view": self.map.view(),
                                "mview": self.mview, "foe": self.foe_sel, "roster": self.roster_out}
        except Exception:                                   # noqa: BLE001
            pass
        # 도트 그림은 지금(Tk 스레드에서) 놓는다 - 칸이 GC 로 작업 스레드에서 풀리면 그림을 지우다 막힌다 (2.1.3)
        self.thumbs.clear()
        self._thumb_wait.clear()

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
        mp = geo = log = mv = None
        if is_match(st):
            # 1:1 맞대결: 지도는 없다 (서버가 /map 을 409 로 막는다). 우리 판이 있을 때만 상대 명단을 받는다.
            if st.get("phase") in ("plan", "war", "done"):
                if st.get("match"):
                    mv = api.guild_war_match()
                if st.get("guild"):
                    log = api.guild_war_log()
            return st, mp, geo, log, mv
        if st.get("phase") in ("plan", "war", "done"):
            mp = api.guild_war_map(self._have())
            geo = self._geo_of(mp)
            if st.get("guild"):
                log = api.guild_war_log()
        return st, mp, geo, log, mv

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
            st, mp, geo, self.log, self.mview = r
            self.st, self.mapdata = st, mp
            if geo is not None:
                self.geo = geo
            self.paint()
            if self.sel and self.wide and not is_match(st):
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
        if is_match(self.st):
            return self._arm_match_poll()

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

    @staticmethod
    def _match_key(st, mv):
        """다시 받은 것이 화면에 바뀔 것이 있나 (남은 시간 endsIn 은 늘 바뀌니 빼고 본다)."""
        st = st or {}
        return (mv, st.get("match"), st.get("mates"), st.get("ranking"), st.get("attacks"), st.get("matches"),
                st.get("contrib"))

    def _arm_match_poll(self):
        """1:1 맞대결: 가끔 다시 받아 판 · 명단 · 고른 상대 · 순위만 고친다. 단계가 넘어갔으면 통째로."""
        def done(r, err):
            if not self.alive or err or self.busy:
                return self._arm_poll()
            st, mv = r
            old = self.st or {}
            if (st.get("phase") != old.get("phase") or not is_match(st)
                    or bool(st.get("match")) != bool(old.get("match")) or st.get("attacks") != old.get("attacks")):
                return self.reload()
            changed = self._match_key(st, mv) != self._match_key(old, self.mview)
            self.st, self.mview = st, mv
            if changed:
                self._refresh_match()
            self._arm_poll()

        def go():
            self._poll_job = None
            if self.alive:
                api = self.app.api
                run_async(self.root, lambda: (api.guild_war(), api.guild_war_match()), done)
        try:
            self._poll_job = self.root.after(POLL_MS, go)
        except Exception:                                   # noqa: BLE001
            self._poll_job = None

    def _refresh_match(self):
        """다시 받은 것으로 판 · 고른 상대 · 우리 명단 · 맞대결 목록 · 보상(내 몫)만 다시 그린다 (오른쪽 칸을 통째로
        다시 만들지 않는다)."""
        if not self._board_on:
            return self.paint()
        self._paint_board(keep=True)
        self._fill_foe()
        self._fill_mates()
        self._fill_ranking()
        self._fill_coin()

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
        self.coin_box = None
        self.foe_box = None
        self.mates_box = None

    def _card(self, title=None, parent=None):
        """판 한 장. parent 를 안 주면 오른쪽 굴리는 칸에 (맞대결 판의 별 판은 왼쪽에 준다)."""
        c = U.framed(parent or self.inner, bg=CARD)
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
        if is_match(st):
            return self._paint_match(st)
        self._use_board(False)
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
        if is_match(st):
            self._text(c, "전략 기간이 시작되면 출전 인원이 비슷한 길드와 짝이 지어지고(홀수면 세 길드 삼각형) 이 칸에 "
                          "맞대결 판이 나타납니다. 전략 기간에 상대 명단을 살펴보고, 전쟁이 시작되면 한 사람이 %d번, "
                          "상대 명단에서 골라 공격합니다." % int(st.get("each") or 2),
                       fg=U.FG_FAINT, font=U.FONT_XS, pady=(0, 10))
            return
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
                   "전쟁이 시작될 때의 모습으로 고정됐습니다. 방어팀은 AI 가 굴려 %s."
                   % ("나를 치는 상대를 막습니다" if is_match(st) else "내 칸을 지킵니다"),
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
        if st.get("jokerMax"):
            jokers = [m["name"] for m in mates if m.get("joker")]
            if plan and (st.get("can") or {}).get("manage"):
                bits.append("조커 %d / %d명%s - 우리 칸을 누르고 '조커로 숨기기' (전쟁이 시작되면 고정)" % (
                    len(jokers), st["jokerMax"], (": " + ", ".join(jokers)) if jokers else ""))
            elif jokers:
                bits.append("우리 조커: %s (다른 길드에는 '???' 로 보입니다)" % ", ".join(jokers))
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
        for k in ("attack", "guard", "joker"):
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
        if t.get("jokerHidden"):
            self._text(box, "조커 칸 - 지키는 사람과 방어팀이 숨겨져 있습니다. 한 번 붙어 보면 보입니다.",
                       fg=U.PINK, font=U.FONT_XS, padx=24)
        elif t.get("joker") and t.get("mine"):
            self._text(box, "조커 - 다른 길드에는 이 칸이 '???' 로 보입니다.", fg=U.PINK, font=U.FONT_XS, padx=24)
        for m in t.get("team") or []:
            self._text(box, "%s  Lv.%d" % (m.get("kr") or "?", m.get("level") or 0), fg=U.FG_DIM, padx=24)
        if t.get("hidden"):
            self._text(box, ("방어팀 %d마리 (싸워 봐야 압니다)" if not t.get("team") else
                             "+ 가려진 %d마리 (싸워 봐야 압니다)") % t["hidden"], fg=U.FG_FAINT, padx=24)
        need = t.get("need") or 3
        if t.get("mine"):
            threats = t.get("threats") or []
            self._text(box, ("이 칸을 노리는 길드: " + ", ".join("[%s] %d승" % (x["guild"], x["wins"]) for x in threats))
                       if threats else "아직 이 칸을 이긴 길드가 없습니다.", fg=U.FG_FAINT, font=U.FONT_XS, pady=(4, 0))
            if t.get("manager"):
                self._guard_row(box, t)
                self._joker_row(box, t)
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

    def _joker_row(self, box, t):
        """길드장 (시즌 5): 이 칸을 지키는 길드원을 조커로 숨기거나 푼다."""
        if not t.get("jokerMax") or t.get("ai") or t.get("taken"):
            return
        on = bool(t.get("joker"))
        n, top = t.get("jokerCount", 0), t["jokerMax"]
        b = U.ghost_button(box, ("조커 풀기 (%d/%d명)" if on else "조커로 숨기기 (%d/%d명)") % (n, top),
                           lambda: self.joker(t["region"], not on), height=30)
        b.pack(fill="x", padx=14, pady=(4, 2))
        if not on and n >= top:
            b.configure(state="disabled")
            self._text(box, "조커는 %d명까지입니다. 다른 조커를 먼저 풀어 주세요." % top, fg=U.FG_FAINT,
                       font=U.FONT_XS)
        self.buttons["joker"] = b

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
            done = ("길드전이 끝났습니다. 길드 코인은 바로 들어갔고, 꾸미기 · 기술머신 뽑기권 · 1위 길드의 칭호는 선물함에 "
                    "있습니다." if any("deco" in r for r in st.get("rewards") or [])
                    else "길드전이 끝났습니다. 보상(길드 코인)은 바로 들어갔고, 1위 길드의 칭호는 선물함에 있습니다.")
            self._text(c, done, fg=U.FG_FAINT, font=U.FONT_XS, pady=(0, 10))

    def _fill_ranking(self):
        box = self.rank_box
        if box is None:
            return
        try:
            for w in box.winfo_children():
                w.destroy()
        except tk.TclError:
            return
        if is_match(self.st):
            return self._fill_matches(box)
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
            if is_match(self.st):
                text = match_log_text(x)            # 1:1 맞대결: 칸 대신 별
            elif x.get("ours"):
                text = "%s → [%s] %s · %s" % (x.get("atkName"), x.get("defGuild") or "?", x.get("defName"), where)
            else:
                text = "[%s] %s → %s · %s" % (x.get("atkGuild") or "?", x.get("atkName"), x.get("defName"), where)
            mark, good = log_mark(x)
            if is_match(self.st) and x.get("result") == "draw":
                mark, good = "비김", None           # 1:1 맞대결의 비긴 판 (지도전 앞머리는 그대로)
            tk.Label(row, text=mark, bg=CARD, fg=U.FG_FAINT if good is None else (U.GOOD if good else U.DANGER),
                     font=U.FONT_B, width=5, anchor="w").pack(side="left")
            lb = tk.Label(row, text=text, bg=CARD, fg=U.FG_DIM, font=U.FONT_XS, anchor="w", justify="left")
            lb.pack(side="left", fill="x", expand=True)
            U.wrap_to_width(lb)
        tk.Frame(c, bg=CARD, height=8).pack()

    # ================ 1:1 맞대결 (시즌 7~) ================
    def _build_board(self):
        """맞대결 판의 뼈대. 지도 자리(self.left)에 끼우고 뺀다 (_use_board). 위는 별 판(안 굴림), 아래는 상대
        출전 명단(굴림)."""
        bg = self.left["bg"]
        self.board = tk.Frame(self.left, bg=bg)
        self.score_box = tk.Frame(self.board, bg=bg)
        self.score_box.pack(fill="x")
        self.list_head = tk.Label(self.board, text="", bg=bg, fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left")
        self.list_head.pack(fill="x", pady=(0, 6))
        U.wrap_to_width(self.list_head)
        self.barea = tk.Frame(self.board, bg=bg)
        self.barea.pack(fill="both", expand=True)
        self.bcv = tk.Canvas(self.barea, bg=bg, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(self.barea, orient="vertical", command=self.bcv.yview)
        self.bcv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.bcv.pack(side="left", fill="both", expand=True)
        self.binner = tk.Frame(self.bcv, bg=bg)
        self._bwid = self.bcv.create_window((0, 0), window=self.binner, anchor="nw")
        self.bfit = U.scroll_fitter(self.bcv, self.binner, self._bwid)
        U.scrollable(self.bcv, 60)

    def _use_board(self, on):
        """왼쪽에 지도와 맞대결 판 가운데 하나를 담는다."""
        if bool(on) == self._board_on:
            return
        self._board_on = bool(on)
        if on:
            self.hint.pack_forget()
            self.map.cv.pack_forget()
            self.board.pack(fill="both", expand=True)
        else:
            self.board.pack_forget()
            self.hint.pack(side="bottom", fill="x", pady=(4, 0))
            self.map.cv.pack(fill="both", expand=True)

    def _me(self, st=None):
        mates = (st or self.st or {}).get("mates") or []
        return next((m for m in mates if m.get("userId") == getattr(self.gw, "my_id", None)), None)

    def _foe(self, uid):
        if uid is None:
            return None
        return next((f for f in (self.mview or {}).get("foes") or [] if f.get("userId") == uid), None)

    def _paint_match(self, st):
        """1:1 맞대결의 칸 전부. 지도전의 paint 와 같은 자리에 같은 판들을, 지도 대신 맞대결 판으로."""
        ph = st.get("phase")
        m = st.get("match")
        board = ph in ("plan", "war", "done") and bool(m) and self.mview is not None
        self._use_board(board)
        self._layout(board)
        self._clear()
        head = self._card()
        row = tk.Frame(head, bg=CARD)
        row.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(row, text="시즌 %d 길드전" % (st.get("season") or 0), bg=CARD, fg=U.FG,
                 font=(U.FAMILY_BLACK, U.pt(14))).pack(side="left")
        U.chip(row, st.get("phaseKr") or "", PHASE_COLOR.get(ph, U.BG4), fg="#ffffff", padx=8).pack(
            side="left", padx=(10, 0))
        self._text(head, phase_line(st), fg=U.FG, pady=(2, 10 if board else 2))
        if not board:
            # 판이 없을 때(신청 · 준비 · 안 나감)는 규칙을 머리에 (판이 있으면 맨 아래 칸으로). 보상은 늘 보상 칸
            self._text(head, rule_line(st), fg=U.FG_FAINT, font=U.FONT_XS, pady=(0, 10))
        if st.get("battle"):
            self._battle_card()
        if ph == "done" and m:
            self._settle_card(st, m)
        if ph == "apply":
            self._apply_card(st)
            self._teams_card(st)
        elif ph in ("plan", "war"):
            if st.get("entered") and m:
                self._my_attack_card(st)
            else:
                self._no_match_card(st)
        if board:
            self._foe_card()
        if ph == "plan" and m and (st.get("can") or {}).get("roster"):
            self._roster_card(st)
        if m and st.get("mates"):
            self._mates_card(st)
        if ph in ("plan", "war", "done") and st.get("matches"):
            self._matches_card(st)
        if ph in ("plan", "war") and st.get("entered"):
            self._teams_card(st)
        if ph in ("war", "done"):
            self._log_card()
        self._star_card(st)
        self._coin_card(st)
        if board:
            c = self._card("규칙")
            self._text(c, rule_line(st), fg=U.FG_FAINT, font=U.FONT_XS, pady=(0, 10))
        if ph == "before":
            c = self._card("준비")
            self._text(c, "%s 동안 이어집니다. 신청·전략 기간에 방어팀과 공격팀을 짜 두세요." % schedule_line(st),
                       pady=(0, 10))
        if board:
            self._paint_board()
        self.fit.schedule()

    def _no_match_card(self, st):
        c = self._card("전략 기간" if st.get("phase") == "plan" else "전쟁 중")
        self._text(c, "우리 길드는 인원이 모자라 이번 길드전에 나가지 못했습니다." if st.get("dropped")
                   else "짝을 지을 길드가 없어 이번 길드전에서는 맞대결이 열리지 않았습니다." if st.get("entered")
                   else "우리 길드는 이번 길드전에 참가하지 않았습니다." if st.get("guild")
                   else "길드에 들어가 있어야 참가할 수 있습니다.", pady=(0, 10))

    # ---- 내 공격 ----
    def _my_attack_card(self, st):
        plan = st.get("phase") == "plan"
        each = int(st.get("each") or 2)
        a = st.get("attacks") or {}
        mine = self._me(st)
        c = self._card("전략 기간" if plan else "내 공격")
        if (mine or {}).get("bench") or (not plan and a and not a.get("total")):
            self._text(c, "이번 판에는 출전하지 않습니다 - 인원 상한에 걸려 명단에서 빠졌습니다. 공격도 방어도 "
                          "하지 않습니다.", fg=U.FG, pady=(0, 10))
            return
        total = each if plan else int(a.get("total") or each)
        left = total if plan else int(a.get("left") or 0)
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x", padx=14, pady=(2, 0))
        big = (U.FAMILY, U.BASE_PT + 2, "bold")
        tk.Label(row, text=dots(left, total), bg=CARD, fg=U.ACCENT if left else U.FG_FAINT, font=big).pack(side="left")
        tk.Label(row, text=("공격 %d번" % total) if plan else "남은 공격 %d번" % left, bg=CARD,
                 fg=U.ACCENT if left else U.FG_DIM, font=big).pack(side="left", padx=(8, 0))
        bits = []
        if plan:
            bits.append("전쟁이 시작되면 상대 출전 명단에서 골라 한 사람에 한 번씩, %d번 칩니다. 지금은 왼쪽 명단에서 "
                        "상대 방어팀을 미리 살펴 두세요." % total)
        elif left:
            bits.append("%d번 중 %d번 씀 · 같은 상대는 한 번만 칠 수 있습니다. 왼쪽 명단에서 상대를 누르세요."
                        % (total, int(a.get("used") or 0)))
        else:
            bits.append("공격을 다 썼습니다 (%d번). 길드원의 공격을 응원해 주세요." % total)
        mates = [m for m in st.get("mates") or [] if not m.get("bench")]
        if mates and not plan:
            idle = [m for m in mates if not m.get("used")]
            bits.append("우리 길드: 공격 %d / %d번 씀 · 아직 한 번도 안 친 사람 %d명" % (
                sum(int(m.get("used") or 0) for m in mates), sum(int(m.get("attacks") or 0) for m in mates), len(idle)))
        if st.get("jokerMax"):
            jokers = [m["name"] for m in mates if m.get("joker")]
            if plan and (st.get("can") or {}).get("manage"):
                bits.append("조커 %d / %d명 - 아래 '우리 명단' 에서 고릅니다 (전쟁이 시작되면 고정)"
                            % (len(jokers), st["jokerMax"]))
            elif jokers:
                bits.append("우리 조커: %s (상대에게는 '???' 로 보입니다)" % ", ".join(jokers))
        for i, text in enumerate(bits):
            self._text(c, text, fg=U.FG_FAINT, font=U.FONT_XS, pady=(4 if i == 0 else 0, 10 if i == len(bits) - 1 else 2))

    # ---- 맞대결 판 (왼쪽) ----
    def _paint_board(self, keep=False):
        """별 판과 상대 출전 명단을 다시 그린다. keep 이면 굴려 둔 자리를 잇는다 (가끔 다시 받을 때)."""
        try:
            top = self.bcv.yview()[0] if keep else 0.0
            for box in (self.score_box, self.binner):
                for w in box.winfo_children():
                    w.destroy()
        except tk.TclError:
            return
        self.foe_rows = {}
        st, mv = self.st or {}, self.mview or {}
        m = st.get("match") or {}
        self._score_card(st, m)
        foes = mv.get("foes") or []
        tg = m.get("target") or {}
        who = ("우리가 칠 길드 [%s]" if m.get("kind") == "tri" else "상대 [%s]") % (tg.get("name") or "?")
        self.list_head.configure(text="%s 의 출전 명단 %d명 · 줄을 누르면 오른쪽에 방어팀과 공격 단추가 나옵니다"
                                 % (who, len(foes)))
        for f in foes:
            self._foe_row(f)
        if not foes:
            tk.Label(self.binner, text="상대 출전 명단이 비어 있습니다.", bg=self.binner["bg"], fg=U.FG_DIM,
                     font=U.FONT_S).pack(pady=16)
        self._flush_thumbs()
        if keep:
            self.bfit.fit_now()
            try:
                self.bcv.yview_moveto(top)
            except tk.TclError:
                pass
        else:
            self.bfit.schedule()

    def _score_card(self, st, m):
        """별 판: 1:1 이면 [우리] vs [상대] 두 칸, 삼각형이면 '우리가 칠 길드' · '우리를 치는 길드' 두 줄."""
        c = self._card(parent=self.score_box)
        plan = st.get("phase") == "plan"
        tri = m.get("kind") == "tri"
        tg, fr = m.get("target") or {}, m.get("from") or {}
        own = m.get("own") or {}             # 우리 길드 {guildId, name, size = 출전 인원}
        ours = own.get("size")
        if ours is None:                     # (own 을 안 싣는 서버) 명단에서 센다
            ours = len([x for x in st.get("mates") or [] if not x.get("bench")])
        ours = int(ours or 0)
        if tri:
            self._text(c, "세 길드 삼각 맞대결 · 우리 → [%s] → [%s] → 우리" % (tg.get("name") or "?", fr.get("name") or "?"),
                       fg=U.FG_FAINT, font=U.FONT_XS, pady=(10, 2))
            self._side_row(c, "우리가 칠 길드 [%s] · 출전 %d명" % (tg.get("name") or "?", int(tg.get("size") or 0)),
                           "우리", m.get("us") or {}, plan, True)
            self._side_row(c, "우리를 치는 길드 [%s] · 출전 %d명" % (fr.get("name") or "?", int(fr.get("size") or 0)),
                           "[%s]" % (fr.get("name") or "?"), m.get("them") or {}, plan, False)
        else:
            self._text(c, "1:1 맞대결", fg=U.FG_FAINT, font=U.FONT_XS, pady=(10, 2))
            grid = tk.Frame(c, bg=CARD)
            grid.pack(fill="x", padx=14, pady=(2, 0))
            grid.grid_columnconfigure(0, weight=1, uniform="side")
            grid.grid_columnconfigure(2, weight=1, uniform="side")
            self._side_col(grid, "우리 [%s]" % own["name"] if own.get("name") else "우리 길드", ours, m.get("us") or {},
                           plan, True).grid(row=0, column=0, sticky="nwe")
            tk.Label(grid, text="vs", bg=CARD, fg=U.FG_FAINT, font=(U.FAMILY_BLACK, U.pt(14))).grid(
                row=0, column=1, padx=10, sticky="n", pady=(U.h(18), 0))
            self._side_col(grid, "[%s]" % (tg.get("name") or "?"), int(tg.get("size") or 0), m.get("them") or {},
                           plan, False).grid(row=0, column=2, sticky="nwe")
        text, color = lead_line(st, m)
        self._text(c, text, fg=color, font=U.FONT_B, pady=(8, 2))
        if tri and not plan:
            self._text(c, "삼각형에서는 '우리가 [%s] 에게서 얻은 성적' 과 '[%s] 가 우리에게서 얻은 성적' 을 견줍니다."
                       % (tg.get("name") or "?", fr.get("name") or "?"), fg=U.FG_FAINT, font=U.FONT_XS)
        if m.get("cap"):
            self._text(c, "출전 상한 %d명 (작은 쪽 인원 x %s) - 큰 길드는 그만큼만 나갑니다."
                       % (int(m["cap"]), ratio_text(st.get("capRatio") or 1.2)), fg=U.FG_FAINT, font=U.FONT_XS)
        tk.Frame(c, bg=CARD, height=8).pack()

    @staticmethod
    def _side_bits(side):
        """한쪽 성적의 작은 글: (별 · 쓰러뜨린 비율, 공격 · 남은 공격)."""
        return ("별 %d / %d개 · 쓰러뜨린 비율 %s" % (int(side.get("stars") or 0), int(side.get("max") or 0),
                                               pct_text(side.get("ko"))),
                "공격 %d번 · 남은 공격 %d번" % (int(side.get("attacks") or 0), int(side.get("left") or 0)))

    def _side_col(self, parent, title, size, side, plan, us):
        """1:1 별 판의 한 칸 (위에서 아래로)."""
        f = tk.Frame(parent, bg=CARD)
        lb = tk.Label(f, text=title, bg=CARD, fg=U.ACCENT if us else U.FG, font=U.FONT_B, anchor="w", justify="left")
        lb.pack(fill="x")
        U.wrap_to_width(lb)
        tk.Label(f, text="출전 %d명" % size, bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w").pack(fill="x")
        if plan:
            return f
        tk.Label(f, text=pct_text(side.get("pct")), bg=CARD, fg=U.ACCENT if us else U.FG,
                 font=(U.FAMILY_BLACK, U.pt(16)), anchor="w").pack(fill="x", pady=(2, 0))
        for i, t in enumerate(self._side_bits(side)):
            lb = tk.Label(f, text=t, bg=CARD, fg=U.FG_DIM if i == 0 else U.FG_FAINT,
                          font=U.FONT_S if i == 0 else U.FONT_XS, anchor="w", justify="left")
            lb.pack(fill="x")
            U.wrap_to_width(lb)
        return f

    def _side_row(self, parent, title, who, side, plan, us):
        """삼각형 별 판의 한 줄: 제목, 그 아래 큰 별 % 와 작은 글."""
        self._text(parent, title, fg=U.ACCENT if us else U.FG, font=U.FONT_B, pady=(6, 0))
        if plan:
            return
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=14)
        tk.Label(row, text=pct_text(side.get("pct")), bg=CARD, fg=U.ACCENT if us else U.FG,
                 font=(U.FAMILY_BLACK, U.pt(16))).pack(side="left", anchor="n")
        a, b = self._side_bits(side)
        lb = tk.Label(row, text="%s 성적 · %s\n%s" % (who, a, b), bg=CARD, fg=U.FG_DIM, font=U.FONT_XS,
                      anchor="w", justify="left")
        lb.pack(side="left", fill="x", expand=True, padx=(10, 0))
        U.wrap_to_width(lb)

    def _stars(self, parent, n, font=None):
        """★★☆ - 얻은 별은 금색, 빈 별은 흐리게."""
        f = tk.Frame(parent, bg=parent["bg"])
        try:
            n = max(0, min(3, int(n or 0)))
        except (TypeError, ValueError):
            n = 0
        if n:
            tk.Label(f, text="★" * n, bg=parent["bg"], fg=U.ACCENT, font=font or U.FONT_B, bd=0, padx=0).pack(
                side="left")
        if n < 3:
            tk.Label(f, text="☆" * (3 - n), bg=parent["bg"], fg=U.FG_FAINT, font=font or U.FONT_B, bd=0,
                     padx=0).pack(side="left")
        return f

    def _foe_row(self, f):
        """상대 출전 명단 한 줄: 이름 · 한 줄 설명 | 방어팀 앞 3마리 | 받은 최고 별. 누르면 고른다."""
        uid = f.get("userId")
        sel = uid == self.foe_sel
        hidden = bool(f.get("hidden"))
        row = U.framed(self.binner, bg=CARD, border=U.ACCENT if sel else U.LINE, bw=2)
        row.pack(fill="x", pady=(0, 6))
        best = f.get("best") or {}
        self._stars(row, best.get("stars")).pack(side="right", padx=(6, 12))
        pics = tk.Frame(row, bg=CARD)
        pics.pack(side="right", pady=4)
        team = f.get("team") or []
        if hidden or not team:
            tk.Label(pics, text="???", bg=CARD, fg=U.PINK, font=U.FONT_B).pack(side="left", padx=(0, 4))
        else:
            for mon in team[:int((self.st or {}).get("shown") or 3)]:
                self._thumb_slot(pics, mon).pack(side="left")
            if f.get("more"):
                tk.Label(pics, text="+%d" % int(f["more"]), bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS).pack(
                    side="left", padx=(2, 0))
        body = tk.Frame(row, bg=CARD)
        body.pack(side="left", fill="x", expand=True, padx=(12, 6), pady=6)
        name = tk.Label(body, text=f.get("name") or "???", bg=CARD, fg=U.PINK if hidden else U.FG, font=U.FONT_B,
                        anchor="w", justify="left")
        name.pack(fill="x")
        U.wrap_to_width(name)
        bits = []
        if f.get("joker"):
            bits.append("조커")
        bits.append("방어팀 %d마리" % int(f.get("size") or 0))
        tries = f.get("tries") or []
        bits.append("도전 %d번" % len(tries) if tries else "아직 아무도 안 침")
        sub = tk.Label(body, text=" · ".join(bits), bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w",
                       justify="left")
        sub.pack(fill="x")
        U.wrap_to_width(sub)
        if f.get("mine"):
            tk.Label(body, text="내가 이미 쳤음", bg=CARD, fg=U.INFO, font=U.FONT_XS, anchor="w").pack(fill="x")
        self._clickable(row, lambda u=uid: self.pick_foe(u))
        self.foe_rows[uid] = row

    def _clickable(self, w, fn):
        try:
            w.configure(cursor="hand2")
        except tk.TclError:
            pass
        w.bind("<Button-1>", lambda _e: fn())
        for ch in w.winfo_children():
            self._clickable(ch, fn)

    def pick_foe(self, uid):
        """맞대결 판에서 상대를 골랐다. 미리보기는 받아 둔 명단에서 그린다 (서버에 안 묻는다)."""
        old = self.foe_sel
        self.foe_sel = uid
        for k in (old, uid):
            row = self.foe_rows.get(k)
            if row is None:
                continue
            color = U.ACCENT if k == uid else U.LINE
            try:
                row.configure(highlightbackground=color, highlightcolor=color)
            except tk.TclError:
                pass
        self._fill_foe()

    # ---- 고른 상대 (오른쪽) ----
    def _foe_card(self):
        c = self._card("고른 상대")
        self.foe_box = tk.Frame(c, bg=CARD)
        self.foe_box.pack(fill="x")
        self._fill_foe()

    def _fill_foe(self):
        """고른 상대의 안쪽만 다시 그린다 (다른 판은 그대로 - 굴려 둔 자리가 튀지 않게)."""
        box = self.foe_box
        if box is None:
            return
        try:
            for w in box.winfo_children():
                w.destroy()
        except tk.TclError:
            return
        self.buttons.pop("attack", None)
        st = self.st or {}
        f = self._foe(self.foe_sel)
        if f is None:
            self.foe_sel = None              # 다시 받은 명단에 없다 (가려진 조커의 자리 표시가 바뀌었다 등)
            self._text(box, "왼쪽 명단에서 상대를 누르세요. 방어팀 앞 %d마리와 받은 별이 보입니다."
                       % int(st.get("shown") or 3), pady=(0, 10))
            return self.fit.schedule()
        hidden = bool(f.get("hidden"))
        tg = ((st.get("match") or {}).get("target") or {}).get("name") or "?"
        self._text(box, f.get("name") or "???", fg=U.PINK if hidden else U.FG, font=U.FONT_B)
        self._text(box, "[%s] 출전 명단" % tg, fg=U.FG_FAINT, font=U.FONT_XS)
        if hidden:
            self._text(box, "조커 - 이름과 방어팀이 숨겨져 있습니다. 한 번 붙어 보면 보입니다.", fg=U.PINK,
                       font=U.FONT_XS, pady=(4, 0))
        elif f.get("joker"):
            self._text(box, "조커 - 우리 길드가 한 번 붙어 봐서 보입니다.", fg=U.PINK, font=U.FONT_XS, pady=(4, 0))
        team = f.get("team") or []
        size = int(f.get("size") or 0)
        if team:
            grid = tk.Frame(box, bg=CARD)
            grid.pack(fill="x", padx=14, pady=(6, 0))
            for mon in team:
                r = tk.Frame(grid, bg=CARD)
                r.pack(fill="x", pady=1)
                self._thumb_slot(r, mon).pack(side="left")
                lb = tk.Label(r, text="%s  Lv.%d" % (mon.get("kr") or "?", int(mon.get("level") or 0)), bg=CARD,
                              fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left")
                lb.pack(side="left", fill="x", expand=True, padx=(6, 0))
                U.wrap_to_width(lb)
            if f.get("more"):
                self._text(box, "+ 가려진 %d마리 (싸워 봐야 압니다)" % int(f["more"]), fg=U.FG_FAINT, padx=24)
        else:
            self._text(box, "방어팀 %d마리 (싸워 봐야 압니다)" % size, fg=U.FG_FAINT, padx=24, pady=(4, 0))
        best = f.get("best")
        if best:
            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", padx=14, pady=(8, 0))
            tk.Label(row, text="받은 최고 별", bg=CARD, fg=U.FG, font=U.FONT_XS).pack(side="left")
            self._stars(row, best.get("stars"), font=U.FONT_S).pack(side="left", padx=(6, 0))
            lb = tk.Label(row, text="%s · %d마리 쓰러뜨림" % (best.get("by") or "?", int(best.get("ko") or 0)), bg=CARD,
                          fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left")
            lb.pack(side="left", fill="x", expand=True, padx=(6, 0))
            U.wrap_to_width(lb)
        else:
            self._text(box, "아직 아무도 치지 않았습니다.", fg=U.FG_FAINT, font=U.FONT_XS, pady=(8, 0))
        for t in (f.get("tries") or [])[:10]:
            res = t.get("result")
            self._text(box, "%s %s · %d마리 쓰러뜨림%s" % (
                t.get("by") or "?", star_text(t.get("stars")), int(t.get("ko") or 0),
                {"win": " · 이김", "draw": " · 비김", "pending": " · 진행 중"}.get(res, "")),
                fg=U.FG_FAINT, font=U.FONT_XS, padx=24)
        b = U.PushButton(box, "이 상대 공격 (관장 배틀)", lambda u=f.get("userId"): self.attack_foe(u),
                         height=32, font=U.FONT_B)
        b.pack(fill="x", padx=14, pady=(8, 2))
        if not f.get("can"):
            b.configure(state="disabled")
        self.buttons["attack"] = b
        if f.get("why"):
            self._text(box, "칠 수 없음: %s" % f["why"], fg=U.DANGER, font=U.FONT_XS)
        elif f.get("mine"):
            self._text(box, "내가 이미 친 상대입니다 (같은 사람은 두 번 칠 수 없습니다).", fg=U.FG_FAINT, font=U.FONT_XS)
        tk.Frame(box, bg=CARD, height=8).pack()
        self._flush_thumbs()
        self.fit.schedule()

    # ---- 우리 명단 ----
    def _mates_card(self, st):
        c = self._card("우리 명단")
        self.mates_box = tk.Frame(c, bg=CARD)
        self.mates_box.pack(fill="x")
        self._fill_mates()

    def _fill_mates(self):
        """길드원마다 남은 공격(●●/●○/○○) · 얻은 별 · 막아 낸 것. 길드장은 전략 기간에 조커를 고른다."""
        box = self.mates_box
        if box is None:
            return
        try:
            for w in box.winfo_children():
                w.destroy()
        except tk.TclError:
            return
        for k in [k for k in self.buttons if k.startswith("joker_")]:
            self.buttons.pop(k, None)
        st = self.st or {}
        plan = st.get("phase") == "plan"
        each = int(st.get("each") or 2)
        mates = st.get("mates") or []
        ours = dict((o.get("userId"), o) for o in (self.mview or {}).get("ours") or [])
        top = int(st.get("jokerMax") or 0)
        manage = plan and top and (st.get("can") or {}).get("manage")
        jokers = [m for m in mates if m.get("joker")]
        playing = [m for m in mates if not m.get("bench")]
        if manage:
            self._text(box, "조커 %d / %d명 - 상대에게는 이름과 방어팀이 '???' 로 보입니다 (한 번 붙어 본 길드에게만 "
                            "보입니다). 전쟁이 시작되면 고정됩니다." % (len(jokers), top),
                       fg=U.FG_FAINT, font=U.FONT_XS, pady=(0, 2))
        elif not plan:
            idle = [m for m in playing if not m.get("used")]
            self._text(box, "공격 %d / %d번 씀 · 아직 한 번도 안 친 사람 %d명" % (
                sum(int(m.get("used") or 0) for m in playing), sum(int(m.get("attacks") or 0) for m in playing),
                len(idle)), fg=U.FG_FAINT, font=U.FONT_XS, pady=(0, 2))
        for m in playing + [m for m in mates if m.get("bench")]:
            self._mate_row(box, m, ours.get(m.get("userId")), each, plan, manage, len(jokers) >= top)
        tk.Frame(box, bg=CARD, height=8).pack()
        self.fit.schedule()

    def _mate_row(self, box, m, o, each, plan, manage, full):
        uid = m.get("userId")
        bench = bool(m.get("bench"))
        me = uid == getattr(self.gw, "my_id", None)
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x", padx=14, pady=(4, 0))
        top = tk.Frame(row, bg=CARD)
        top.pack(fill="x")
        if manage and not bench:
            on = bool(m.get("joker"))
            b = U.ghost_button(top, "조커 풀기" if on else "조커로", lambda u=uid, v=not on: self.joker_user(u, v),
                               height=24)
            b.pack(side="right", padx=(6, 0))
            if not on and full:
                b.configure(state="disabled")
            self.buttons["joker_%s" % uid] = b
        if not bench:
            total = each if plan else int(m.get("attacks") or each)
            left = total if plan else max(0, total - int(m.get("used") or 0))
            tk.Label(top, text=dots(left, total), bg=CARD, fg=U.ACCENT if left else U.FG_FAINT, font=U.FONT_B).pack(
                side="right")
        name = tk.Label(top, text=(m.get("name") or "?") + ("  (나)" if me else ""), bg=CARD,
                        fg=U.FG_FAINT if bench else (U.ACCENT if me else U.FG), font=U.FONT_B, anchor="w", justify="left")
        name.pack(side="left", fill="x", expand=True)
        U.wrap_to_width(name)
        line = tk.Frame(row, bg=CARD)
        if m.get("joker"):
            U.chip(line, "조커", U.PINK, fg="#ffffff").pack(side="left", padx=(0, 6))
        if bench:
            text = "이번 판에는 빠짐 (인원 상한)"
        elif plan:
            text = ""
        else:
            parts = ["얻은 별 %d" % int(m.get("stars") or 0), "이김 %d판" % int(m.get("wins") or 0)]
            o = o or {}
            n = int(o.get("tries") or 0)
            parts.append("막아 냄 %d / %d번" % (int(o.get("defends") or 0), n) if n else "받은 공격 없음")
            if o.get("worst"):
                parts.append("내준 별 %s" % star_text(o["worst"].get("stars")))
            text = " · ".join(parts)
        if text:
            lb = tk.Label(line, text=text, bg=CARD, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w", justify="left")
            lb.pack(side="left", fill="x", expand=True)
            U.wrap_to_width(lb)
        if text or m.get("joker"):
            line.pack(fill="x")

    def joker_user(self, uid, on):
        """길드장 (1:1 · 전략 기간): 그 길드원을 조커로 숨기거나 푼다."""
        self._call(lambda: self.app.api.guild_war_joker(user_id=uid, on=on),
                   "조커로 숨겼습니다." if on else "조커를 풀었습니다.", lambda _st: self.reload())

    # ---- 출전 명단 고르기 (길드장 · 전략 기간 · 인원 상한에 걸린 판) ----
    def _roster_card(self, st):
        mates = st.get("mates") or []
        cap = int((st.get("match") or {}).get("cap") or 0)
        if not mates or not cap:
            return
        if self.roster_out is None:
            self.roster_out = set(m.get("userId") for m in mates if m.get("bench"))
        c = self._card("출전 명단 고르기 (길드장 · 전략 기간에만)")
        self._text(c, "이번 판의 출전 상한은 %d명입니다 (작은 쪽 인원 x %s). 우리 길드원 %d명 가운데 %d명이 나갑니다 - "
                      "빠진 사람은 이번 판에서 공격도 방어도 하지 않습니다. 고르지 않으면 방어팀 전력이 센 순으로 "
                      "나갑니다." % (cap, ratio_text(st.get("capRatio") or 1.2), len(mates), cap),
                   fg=U.FG_FAINT, font=U.FONT_XS, pady=(0, 4))
        self.roster_rows = {}
        for m in mates:
            uid = m.get("userId")
            row = tk.Frame(c, bg=CARD)
            row.pack(fill="x", padx=14, pady=1)
            b = U.ghost_button(row, "", lambda u=uid: self.toggle_roster(u), height=24)
            b.pack(side="right")
            self.buttons["roster_%s" % uid] = b
            lb = tk.Label(row, text="", bg=CARD, fg=U.FG, font=U.FONT_S, anchor="w", justify="left")
            lb.pack(side="left", fill="x", expand=True)
            U.wrap_to_width(lb)
            self.roster_rows[uid] = (lb, b, m.get("name") or "?")
        self.roster_sum = self._text(c, "", fg=U.FG_FAINT, font=U.FONT_XS, pady=(4, 0))
        b = U.PushButton(c, "출전 명단 저장", self.save_roster, height=30, font=U.FONT_B)
        b.pack(fill="x", padx=14, pady=(6, 10))
        self.buttons["roster"] = b
        self._roster_note()

    def _roster_note(self):
        st = self.st or {}
        cap = int((st.get("match") or {}).get("cap") or 0)
        out = self.roster_out or set()
        for uid, (lb, b, name) in getattr(self, "roster_rows", {}).items():
            gone = uid in out
            try:
                lb.configure(text="%s  ·  %s" % (name, "빠짐" if gone else "출전"), fg=U.FG_FAINT if gone else U.FG)
                b.configure(text="넣기" if gone else "빼기")
            except tk.TclError:
                pass
        n = len(st.get("mates") or []) - len(out)
        tail = (" - %d명을 더 빼 주세요" % (n - cap)) if n > cap else (" - %d명을 더 넣어 주세요" % (cap - n)) if n < cap else ""
        try:
            self.roster_sum.configure(text="출전 %d / %d명%s" % (n, cap, tail), fg=U.DANGER if n != cap else U.FG_FAINT)
            self.buttons["roster"].configure(state="normal" if n == cap else "disabled")
        except (tk.TclError, KeyError, AttributeError):
            pass

    def toggle_roster(self, uid):
        if self.roster_out is None:
            return
        if uid in self.roster_out:
            self.roster_out.discard(uid)
        else:
            self.roster_out.add(uid)
        self._roster_note()

    def save_roster(self):
        out = sorted(self.roster_out or ())

        def then(_st):
            self.roster_out = None
            self.reload()
        self._call(lambda: self.app.api.guild_war_roster(out), "출전 명단을 정했습니다.", then)

    # ---- 이번 시즌 맞대결 (순위 대신) · 보상 · 결산 ----
    def _matches_card(self, st):
        """이번 시즌 맞대결 목록 (서버 matches). 줄 세우는 순위가 없다 - 짝(삼각형)마다 한 덩어리, 우리 판이 맨 위."""
        c = self._card("이번 시즌 맞대결")
        self.rank_box = tk.Frame(c, bg=c["bg"])
        self.rank_box.pack(fill="x")
        self._fill_ranking()
        ph = st.get("phase")
        if ph == "plan":
            note = "상대가 발표됐습니다. 전쟁이 시작되면 별 % 와 승패가 보입니다."
        elif ph == "done":
            note = ("길드전이 끝났습니다. 결산 길드 코인은 한 번이라도 공격한 길드원에게 바로 들어갔습니다 "
                    "(순위 보상은 없습니다).")
        else:
            note = "전쟁 중에는 지금까지 얻은 별로 본 '앞섬' 입니다. 승패는 전쟁이 끝날 때 정해집니다."
        self._text(c, note, fg=U.FG_FAINT, font=U.FONT_XS, pady=(6, 10))

    def _fill_matches(self, box):
        st = self.st or {}
        rows = st.get("matches") or []
        mine = (st.get("guild") or {}).get("id")
        plan = st.get("phase") == "plan"
        bg = box["bg"]
        if not rows:
            self._text(box, "이번 시즌에는 열린 맞대결이 없습니다.", pady=(0, 4))
            return self.fit.schedule()
        for i, mt in enumerate(rows):
            ours = bool(mt.get("ours"))
            tri = mt.get("kind") == "tri"
            gs = mt.get("guilds") or []
            blk = U.framed(box, bg=bg, border=U.ACCENT if ours else U.LINE, bw=2 if ours else 1)
            blk.pack(fill="x", padx=14, pady=(2 if i == 0 else 8, 0))
            kind = "삼각 맞대결 (세 길드)" if tri else "1:1 맞대결"
            self._text(blk, ("우리 맞대결 · %s" % kind) if ours else kind, fg=U.ACCENT if ours else U.FG_DIM,
                       font=U.FONT_B if ours else U.FONT_XS, pady=(6, 0), padx=10)
            cyc = match_cycle(gs) if tri else ""
            if cyc:
                self._text(blk, cyc, fg=U.FG_FAINT, font=U.FONT_XS, padx=10)
            for g in gs:
                self._match_guild_row(blk, g, mt, mine, plan, tri)
            tk.Frame(blk, bg=bg, height=6).pack()
        self.fit.schedule()

    def _match_guild_row(self, parent, g, mt, mine, plan, tri):
        """맞대결 덩어리 안의 길드 한 줄: [이름] · 승패(오른쪽), 그 아래 별 % · 쓰러뜨린 비율 (삼각형은 칠 길드)."""
        bg = parent["bg"]
        me = mine is not None and g.get("guildId") == mine
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", padx=10, pady=(4, 0))
        text, color = match_result_text(g.get("result"), mt.get("final"), plan)
        tk.Label(row, text=text, bg=bg, fg=color, font=U.FONT_B).pack(side="right", anchor="n", padx=(8, 0))
        lb = tk.Label(row, text="[%s]%s" % (g.get("name") or "?", "  우리" if me else ""), bg=bg,
                      fg=U.ACCENT if me else U.FG, font=U.FONT_B, anchor="w", justify="left")
        lb.pack(side="left", fill="x", expand=True)
        U.wrap_to_width(lb)                      # 긴 길드 이름은 줄을 바꾼다 (글자를 줄이지 않는다)
        bits = []
        if tri and g.get("vs"):
            bits.append("칠 길드 [%s]" % g["vs"])
        if not plan:
            bits.append("별 %d / %d개 (%s) · 쓰러뜨린 비율 %s" % (int(g.get("stars") or 0), int(g.get("max") or 0),
                                                         pct_text(g.get("pct")), pct_text(g.get("ko"))))
        for t in bits:
            self._text(parent, t, fg=U.FG_DIM, font=U.FONT_XS, padx=10)

    def _coin_card(self, st):
        """보상 (길드 코인만): 판마다 받는 코인 표 · 한 시즌 상한과 내 몫 · 결산 코인."""
        c = self._card("보상 - 길드 코인")
        self.coin_box = tk.Frame(c, bg=c["bg"])
        self.coin_box.pack(fill="x")
        self._fill_coin()
        self._text(c, "순위 보상(꾸미기 · 칭호 · 기술머신 뽑기권)은 없습니다. 모은 코인은 코인 상점에서 쓰고, '길드 전용' "
                      "상품은 코인으로만 살 수 있습니다.", fg=U.FG_FAINT, font=U.FONT_XS, pady=(6, 10))

    def _fill_coin(self):
        box = getattr(self, "coin_box", None)
        if box is None:
            return
        try:
            for w in box.winfo_children():
                w.destroy()
        except tk.TclError:
            return
        st = self.st or {}
        c = coin_rules(st)
        stars = (list(c.get("stars") or []) + [0, 0, 0])[:3]
        res = c.get("result") or {}
        self._text(box, "공격 한 판이 끝나면 (공격한 사람, 그 판의 별로)", fg=U.FG_FAINT, font=U.FONT_XS, pady=(2, 0))
        for i, n in enumerate(stars):
            row = self._coin_row(box, None, "%d개" % int(n or 0))
            self._stars(row, i + 1).pack(side="left", anchor="n")
        self._coin_row(box, "조커를 이기면", "+%d개" % int(c.get("joker") or 0))
        self._coin_row(box, "공격을 막아 내면 (지킨 사람 · 공격팀을 다 쓰러뜨렸을 때)", "%d개" % int(c.get("defend") or 0))
        self._text(box, "판마다 받는 코인은 한 사람 한 시즌 %d개까지입니다." % int(c.get("max") or 0),
                   fg=U.FG_FAINT, font=U.FONT_XS, pady=(4, 0))
        full = earned_of(st) >= int(c.get("max") or 0) > 0
        self._text(box, earned_text(st) + (" - 다 받았습니다" if full else ""), fg=U.FG_DIM if full else U.ACCENT,
                   font=U.FONT_B)
        self._text(box, "결산 (한 번이라도 공격한 사람, 우리 길드의 결과로 · 상한 밖)", fg=U.FG_FAINT, font=U.FONT_XS,
                   pady=(8, 0))
        for k, kr in RESULT_WORD:
            self._coin_row(box, kr, "%d개" % int(res.get(k) or 0))
        self.fit.schedule()

    def _coin_row(self, parent, text, value):
        """보상 표의 한 줄: 왼쪽 글 · 오른쪽 코인 수. text 가 None 이면 왼쪽을 비워 둔다 (부르는 쪽이 별을 담는다)."""
        bg = parent["bg"]
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", padx=14, pady=1)
        tk.Label(row, text=value, bg=bg, fg=U.ACCENT, font=U.FONT_B).pack(side="right", anchor="n", padx=(8, 0))
        if text is not None:
            lb = tk.Label(row, text=text, bg=bg, fg=U.FG, font=U.FONT_S, anchor="w", justify="left")
            lb.pack(side="left", fill="x", expand=True)
            U.wrap_to_width(lb)
        return row

    def _settle_card(self, st, m):
        """끝난 뒤(done) 맨 위: 우리 판 결과와 받은 결산 코인 (coinRules.result[결과])."""
        res = m.get("result")
        if res not in ("win", "lose", "draw"):
            return
        n = int((coin_rules(st).get("result") or {}).get(res) or 0)
        word, color = {"win": ("승리! 우리 길드가 이겼습니다.", U.GOOD), "draw": ("비김 - 우리 길드는 비겼습니다.", U.FG),
                       "lose": ("패배 - 이번 맞대결은 졌습니다.", U.DANGER)}[res]
        c = self._card("결산")
        self._text(c, word, fg=color, font=U.FONT_B, pady=(0, 2))
        self._text(c, "한 번이라도 공격한 길드원은 결산 길드 코인 %d개를 받았습니다 (%s)."
                   % (n, " · ".join("%s %d" % (kr, int((coin_rules(st).get("result") or {}).get(k) or 0))
                                    for k, kr in RESULT_WORD)), fg=U.FG)
        used = int((st.get("attacks") or {}).get("used") or 0)
        got = earned_of(st)
        settled = (st.get("contrib") or {}).get("settled")
        if settled is not None:                  # 서버가 실제로 준 결산 코인 (없으면 짐작)
            n, used = int(settled), used if settled else 0
        if used:
            mine = "나는 공격 %d번 - 판마다 받은 코인 %d개 + 결산 %d개 = %d개." % (used, got, n, got + n)
        else:
            mine = "나는 이번 길드전에서 공격하지 않아 결산 코인이 없습니다 (판마다 받은 코인 %d개)." % got
        self._text(c, mine, fg=U.ACCENT if used else U.FG_DIM, font=U.FONT_S, pady=(2, 10))

    # ---- 별 규칙 ----
    def _star_card(self, st):
        c = self._card("별 규칙")
        rules = list(st.get("starRules") or STAR_RULES)
        for i, t in enumerate(rules[:3]):
            row = tk.Frame(c, bg=CARD)
            row.pack(fill="x", padx=14, pady=1)
            self._stars(row, i + 1).pack(side="left", anchor="n")
            lb = tk.Label(row, text=t, bg=CARD, fg=U.FG, font=U.FONT_S, anchor="w", justify="left")
            lb.pack(side="left", fill="x", expand=True, padx=(8, 0))
            U.wrap_to_width(lb)
        self._text(c, "방어자 한 명마다 가장 잘한 공격 하나만 셉니다 (별이 많은 것, 같으면 쓰러뜨린 수가 많은 것). "
                      "별 % = 얻은 별 / (3 x 상대 출전 인원) 이라 인원이 달라도 견줄 수 있고, 같으면 쓰러뜨린 비율로 "
                      "가립니다. 기권 · 창 닫기 · 시간 초과도 공격 한 번을 쓴 것이고, 그때까지 쓰러뜨린 수로 셉니다.",
                   fg=U.FG_FAINT, font=U.FONT_XS, pady=(4, 10))

    # ---- 도트 ----
    def _thumb_slot(self, parent, mon):
        """도트 한 칸 (크기가 정해진 틀 - 그림이 늦게 와도 줄이 들썩이지 않게)."""
        bg = parent["bg"]
        f = tk.Frame(parent, bg=bg, width=THUMB, height=THUMB)
        f.pack_propagate(False)
        lb = tk.Label(f, bg=bg, bd=0)
        lb.pack(expand=True)
        num = mon.get("num")
        if num:
            key = (num, T.skin(mon))
            ph = self.thumbs.get(key)
            if ph is not None:
                lb.configure(image=ph)
            else:
                self._thumb_wait.setdefault(key, []).append(lb)
        return f

    def _flush_thumbs(self):
        """기다리는 도트를 한 번에 받는다 (작업 스레드 하나)."""
        keys = [k for k in self._thumb_wait if k not in self._thumb_busy]
        if not keys or not self.alive:
            return
        self._thumb_busy.update(keys)
        api = self.app.api

        def work():
            out = {}
            for num, skin in keys:
                try:
                    path = sprite_cache.ensure(api, num, skin)
                    if not path:
                        continue
                    anim = sprites.load_animation(path, THUMB, 0.2, 3.0, max_frames=1, max_size=(THUMB, THUMB))
                    out[(num, skin)] = sprites.to_rgba(anim.frames[sprites.RIGHT][0], anim.key)
                except Exception:                           # noqa: BLE001
                    continue
            return out

        def done(imgs, err):
            self._thumb_busy.difference_update(keys)
            if not self.alive:
                return
            for k in keys:
                labels = self._thumb_wait.pop(k, [])
                img = (imgs or {}).get(k) if not err else None
                if img is None:
                    continue
                try:
                    ph = self.thumbs.get(k) or ImageTk.PhotoImage(img)
                except Exception:                           # noqa: BLE001
                    continue
                self.thumbs[k] = ph
                for lb in labels:
                    try:
                        lb.configure(image=ph)
                    except tk.TclError:
                        pass                     # 그사이 다시 그렸다
        run_async(self.root, work, done)

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

    def joker(self, region, on):
        def then(r):
            self.tile = r
            self.reload()
        self._call(lambda: self.app.api.guild_war_joker(region, on),
                   "조커로 숨겼습니다." if on else "조커를 풀었습니다.", then)

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
                     % ((("나를 치는 상대를 막으며 (AI 가 굴립니다)" if kind == "def" else "상대를 칠 때 (직접 싸웁니다)")
                         if is_match(self.st) else
                         ("내 칸을 지키며 (AI 가 굴립니다)" if kind == "def" else "남의 칸을 칠 때 (직접 싸웁니다)")),
                        cap, cap, "\n상대에게는 앞의 %d마리만 미리 보입니다." % shown if kind == "def" else ""))})

    def _open_battle(self, data):
        """관장 배틀 창에서 싸운다. 창을 닫으면 지도를 다시 받는다."""
        from .ui_gym_battle import GymBattleWindow
        self.battle = GymBattleWindow(self.app, data, on_close=self._battle_closed)

    def _battle_closed(self):
        gb, self.battle = getattr(self, "battle", None), None
        self.tile = None
        # 1:1: 그 판의 별과 받은 코인 (관장 배틀 창의 결과 칸은 이긴 판에만 서버 줄을 적는다 - 지고 얻은 ★ 의 코인도 보이게)
        note = match_end_line(getattr(gb, "reward", None))
        if note and self.alive:
            self.say(note, U.GOOD if "길드 코인" in note and "없습니다" not in note else U.FG)
        if self.alive:
            self.reload()

    def attack(self, region):
        """그 칸에 승부를 건다 (공격권 하나를 쓴다)."""
        self._start(lambda: self.app.api.guild_war_attack(region))

    def attack_foe(self, uid):
        """1:1 맞대결: 상대 길드원에게 승부를 건다 (공격권 하나를 쓴다). 가려진 조커는 음수 자리 표시 그대로 보낸다.
        자리 표시가 낡았으면 서버가 409 '맞대결 판이 바뀌었습니다...' 로 막는다 - _call 이 그 글을 띄우고 판을 다시 받는다."""
        self._start(lambda: self.app.api.guild_war_attack(target=uid))

    def _start(self, fn):
        old = getattr(self.app, "gym_battle", None)
        if old is not None and getattr(old, "alive", False):
            try:
                old.win.lift()
            except Exception:                               # noqa: BLE001
                pass
            return self.say("진행 중인 승부를 먼저 끝내 주세요.", U.DANGER)
        self.say("승부를 준비하는 중...")
        self._call(fn, "", self._open_battle)

    def resume(self):
        """끝나지 않은 길드전 승부를 이어서 한다."""
        self._call(lambda: self.app.api.gym_battle(), "", self._open_battle)
