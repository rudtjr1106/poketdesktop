# -*- coding: utf-8 -*-
"""길드전 (시즌 4) — 시즌마다 한 번, 참가한 길드 전부가 **원형 지도의 땅을 뺏는 전쟁**.

## 일정 (시즌이 시작한 순간부터 센다 - 시즌 2주 = 3 + 4 + 6 + 1, 2026-10-15 사용자 결정)

    신청  3일   마스터·부마스터가 참가를 넣고 뺀다. 길드원은 방어팀·공격팀을 짠다.
    전략  4일   명단이 고정되고 지도가 나뉜다. 길드장이 공격 횟수와 지킬 칸을 정하고, 길드원은 팀을
                고칠 수 있다. 공격은 아직 못 한다.
    전쟁  6일   정해 둔 것(공격 횟수·지킬 칸·팀)은 못 바꾼다. 맞닿은 남의 칸을 골라 관장 배틀처럼 싸운다.
    끝          결산 - 칸이 가장 많은 길드부터 보상. 다음 시즌까지 지도와 순위표가 남는다.

따로 도는 시계는 없다. 누가 길드전 화면을 열거나 공격할 때 지금이 어느 때인지 보고
(phase), 넘어가야 할 일이 있으면 그 자리에서 한다 (명단 고정·지도 나누기 _lock, 결산 settle).
둘 다 **한 번만** 돌게 표시를 먼저 적는다.

## 지도

**고리(도넛) 모양 판을 참가 길드 수만큼 같은 부채꼴로 나눈다** (layout). 부채꼴 하나 = 줄 5개(바깥 -> 안)
x 칸 3개 = 15칸. 처음에는 한반도 지도(시·군·구를 묶은 칸)였는데 자리에 따라 맞닿은 길드가 1~7곳, 남과
맞닿은 칸이 4~14칸으로 갈려서 (10/16 사용자 결정) 모든 길드가 똑같은 판으로 바꿨다:

  · 이웃 길드는 양옆 두 곳 (길드가 둘이면 서로 양쪽에서 맞닿는다)
  · 남과 맞닿은 칸은 양쪽 가장자리 줄의 10칸, 가운데 줄 5칸은 안쪽 - 길드마다 같다
  · 길드가 몇 곳이든 15칸 (지도 크기가 길드 수를 따라 늘어난다)

길드 차례(누가 누구와 이웃인가)는 **신청이 끝나고 전략 기간이 시작될 때(4일째) 무작위로 뽑아 적어 둔다**
(placement - 그 전에는 아무도 모른다. 적어 둔 뒤로는 다시 나눠도 같다). 칸 이름은
"처음 주인 길드 n번" (바깥 줄부터 1~3, 4~6 ...). 지도 그림(부채꼴 도형·길드 이름)은 map_view 가
함께 준다 (ring_geo) - 화면이 따로 자료를 받지 않는다. 중립 칸은 없다.

## 지키는 사람

길드원은 **한 사람이 한 칸씩** 지킨다 (15명 길드는 15칸 전부를 사람이). 남는 칸은 **AI 수비대**가
지킨다 - 관장 자료의 팀을 Lv.50·개체값 31로 맞춘 것 가운데, 참가자 방어팀 전력의 중간값에 가까운 것
(모든 길드가 같은 기준이다). 처음 배치는 서버가 한다: 방어팀이 센 사람부터 남의 땅과 많이 맞닿은
칸에. **전략 기간에** 길드장(마스터·부마스터)이 옮길 수 있다 (place). 전쟁이 시작되면 못 바꾼다.

## 공격

길드마다 공격 30번 (TOTAL_ATTACKS). 처음에는 인원수로 나눠 주고(quota), 길드장이 **전략 기간에**
마음대로 다시 나눈다 (set_attacks - 한 사람 최소 1번, 합 30번 까지). 공격은 전쟁 기간에만 하고,
**우리 칸과 맞닿은 남의 칸만** 칠 수 있다.

공격은 **관장 배틀처럼 직접 싸운다** - common/trainer_battle 판을 gym_battle 표에 두고 관장 배틀 창으로
한다 (region = "gw:시즌:칸"). 상대 방어팀은 AI 가 굴린다 (ai="war": 실수 없이, 한 턴을 미리 셈해서,
Z기술·메가진화도 쓴다). **판을 시작하는 순간 공격권 하나를 쓴다** - 기권·창 닫기·시간 초과는
진 것이다. 판이 끝나면 gym_routes.act 가 on_end 를 부른다.

**그 칸을 지키는 사람을 우리 길드가 합쳐 3번 이기면**(WINS_TO_TAKE) 칸이 넘어온다. **한 번 넘어간
칸은 다시 못 뺏는다.** 길드 하나가 받는 공격도 30번까지다 (여러 이웃이 한 길드만 두드리지 못하게).

**길드원이 구경한다** (시즌 4, 친선전과 같은 길 - friendly.watch_open / watch_feed): 공격이 열리면 공격한
길드의 채팅에 카드가 놓이고 [관전] 으로 바탕화면에서 본다. 턴이 돌 때마다 판의 모습(spectate)을 민다.
싸우는 사람은 '관전 N명' 을 본다 (watchers).

남의 방어팀은 **앞에서부터 SHOWN 마리만** 미리 보인다 (나머지는 마릿수만). 가려진 것은 응답에
아예 싣지 않는다 - 화면에서만 가리면 요청을 들여다봐서 알 수 있다. 싸우면서 나온 것은 보인다.

## 이기는 길드

**가진 칸이 가장 많은 길드.** 같으면 방어 성공 수, 그다음 공격 승리 수, 먼저 닿은 길드.

## 조커 · 개인 기여 보상 (시즌 5 - season.rules_v5, 2026-10-30 사용자 결정, 게시판 #373 의견)

**조커**: 길드장이 전략 기간에 길드원을 JOKER_MAX 명까지 숨긴다 (사람에 붙는다 - 칸을 옮겨도 따라간다).
남의 길드에는 그 사람이 지키는 칸의 이름·방어팀이 '???' 로 온다 (마릿수만). 그 길드가 그 사람과 한 번이라도
붙어 보면(그 사람이 지키는 칸에 판을 열면) 보통 칸처럼 보인다 - 싸우면서 이름과 나온 포켓몬을 이미 봤다.
조커가 남의 칸을 뺏어 지키게 된 칸도 똑같이 가린다 (거기서 보이면 숨긴 칸의 방어팀이 드러난다 - 10/30 검토).
지도에는 조커 칸이 표시된다 (누가 숨었는지는 모른다). AI 수비대 칸은 조커가 아니다.

**기여 보상**: 판이 끝날 때마다 바로 길드 코인 - 공격에서 이기면 CONTRIB_WIN (조커를 이기면 CONTRIB_JOKER 더),
내가 지키는 칸이 막아 내면 CONTRIB_DEFEND - **공격 팀을 실제로 다 쓰러뜨렸을 때만** (판의 결과 lost). 기권·시간
초과도 공격한 쪽에서는 진 것이지만 지킨 사람은 안 받는다 - 짠 길드끼리 바로 기권해 주며 코인을 주고받지 못하게
(10/30 검토). 한 사람이 한 시즌에 CONTRIB_MAX 까지 (guild_war_team.earned). 비기면 없다. 순위 보상(settle)은
그대로 따로 나간다.
"""
import datetime
import hashlib
import json
import math
import random

from fastapi import HTTPException

from common import trainer_battle as TB

from . import config, db, deps, friendly, gimmick, guild, gym, live, mega, pvp, season, watchers

KST = datetime.timezone(datetime.timedelta(hours=9))
APPLY_DAYS = 3               # 참가 신청
PLAN_DAYS = 4                # 전략: 지도가 나뉘고 길드장이 공격 횟수·지킬 칸을 정한다 (공격은 못 한다)
WAR_DAYS = 6                 # 전쟁: 정해 둔 것은 못 바꾼다
SETTLE_DAYS = 1              # 결산 (끝난 첫날). 시즌 2주 = 3 + 4 + 6 + 1
MIN_MEMBERS = 5              # 이만큼은 있어야 신청할 수 있다
TOTAL_ATTACKS = 30           # 길드 하나의 공격 수 합 = 길드 하나가 받는 공격 수 상한
RING_ROWS = 5                # 원형 지도: 길드마다 부채꼴 하나 = 줄 5개(바깥 -> 안) x 칸 3개
RING_COLS = 3
# 명단을 고정하던 요청이 이만큼 지나도 안 끝났으면(서버가 그사이 죽었다) 그 표시는 낡은 것으로 보고 다시 고정한다
STALE_LOCK_SEC = 120
TILES_PER_GUILD = RING_ROWS * RING_COLS     # 15칸 - 길드가 몇 곳이든 같다
RING_INNER = 0.38            # 고리 안쪽 반지름 (바깥이 1)
RING_ARC = 120               # 한 바퀴를 몇 토막의 선으로 그리나 (칸이 많으면 칸마다 2토막은 쓴다)
_RAND = random.SystemRandom()   # 이웃 배치를 뽑는 주사위 (placement - 검사는 씨앗 있는 것으로 바꿔 끼운다)
WINS_TO_TAKE = 3             # 같은 사람을 이만큼 이기면 칸이 넘어온다
SHOWN = 3                    # 남의 방어팀에서 미리 보이는 마릿수 (앞에서부터)
AI_GUARD = 0                 # guard_user 가 이것이면 AI 수비대
AI_CHOICES = 5               # AI 수비대 팀의 후보 수 (전력이 중간값에 가까운 것부터)
AI_LEVEL = 50
PREFIX = "gw:"               # gym_battle.region 의 머리 ("gw:4:c07")
REWARD_COINS = {1: 300, 2: 200, 3: 150}
REWARD_OTHER = 50
# 시즌 5 (위 '조커 · 개인 기여 보상')
JOKER_MAX = 3                # 길드마다 숨길 수 있는 길드원
CONTRIB_WIN = 20             # 공격에서 이길 때마다 (길드 코인, 1개 = 250원어치)
CONTRIB_JOKER = 20           # 조커를 이기면 더
CONTRIB_DEFEND = 20          # 내가 지키는 칸이 공격을 막아 낼 때마다
CONTRIB_MAX = 300            # 한 사람이 한 시즌에 받는 기여 보상 상한
TITLE = "s4_guildwar"
GIFT_TITLE = "시즌 %d 길드전"
KINDS = ("def", "atk")
KIND_KR = {"def": "방어팀", "atk": "공격팀"}
PHASE_KR = {"before": "준비 중", "apply": "참가 신청", "plan": "전략", "war": "전쟁", "done": "끝"}
RESULT_OF = {"won": "win", "draw": "draw"}     # 판의 결과 (사람 쪽) -> 공격 기록. 나머지는 lose


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(t=None):
    return (t or _now()).replace(microsecond=0).isoformat()


def parse_time(v):
    try:
        t = datetime.datetime.fromisoformat(v)
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)


def starts():
    """이번 시즌 길드전의 시작 = 시즌이 시작하는 날 0시 (한국 시각)."""
    y, m, d = (int(x) for x in season.SEASON_STARTS.split("-"))
    return datetime.datetime(y, m, d, 0, 0, tzinfo=KST)


def plan_at():
    """전략 기간이 시작하는 때 = 명단이 고정되고 지도가 나뉘는 때."""
    return starts() + datetime.timedelta(days=APPLY_DAYS)


def war_at():
    return plan_at() + datetime.timedelta(days=PLAN_DAYS)


def ends_at():
    return war_at() + datetime.timedelta(days=WAR_DAYS)


def phase(now=None):
    """지금이 어느 때인가. ("before"/"apply"/"plan"/"war"/"done", 그때가 끝나는 시각 또는 None)"""
    now = now or _now()
    if now < starts():
        return "before", starts()
    if now < plan_at():
        return "apply", plan_at()
    if now < war_at():
        return "plan", war_at()
    if now < ends_at():
        return "war", ends_at()
    return "done", None


def quota(n):
    """n 명이 TOTAL_ATTACKS 를 나눠 갖는 수 (처음 나눌 때). 앞사람부터 하나씩 더 받는다."""
    if n <= 0:
        return []
    base, more = divmod(TOTAL_ATTACKS, n)
    return [base + (1 if i < more else 0) for i in range(n)]


# ---------------------------------------------------------------- 지도 (원형)
def layout(order):
    """지도. order = 고리를 도는 길드 차례 (placement 가 정한다 - 앞뒤와 끝·처음이 이웃이다).
    (칸들, 칸마다 주인 길드, 길드마다 칸 수)

    칸 = [줄, 고리를 도는 차례, 한 바퀴의 칸 수]. 줄 0 이 바깥이다. 길드 k 는 차례 k*RING_COLS 부터
    RING_COLS 칸 너비의 부채꼴을 가진다. 같은 차례면 늘 같은 지도다.
    """
    order = list(order)
    if not order:
        return [], [], 0
    total = RING_COLS * len(order)
    cells, owner = [], []
    for k, g in enumerate(order):
        for row in range(RING_ROWS):
            for j in range(RING_COLS):
                cells.append([row, k * RING_COLS + j, total])
                owner.append(g)
    return cells, owner, TILES_PER_GUILD


def placement(s, gids):
    """누가 누구와 이웃인가 = 고리를 도는 길드 차례. **신청이 끝나고 전략 기간이 시작될 때(4일째) 처음 지도를
    나누면서 무작위로 뽑아 적어 둔다** (10/16 사용자 결정 - 미리 셈해 볼 수 없게). 그 뒤로는 적어 둔 것을 쓴다
    - 나누다 끊겨 다시 돌아도, 두 요청이 같이 나눠도 같은 배치다 (먼저 적은 쪽).
    """
    want = sorted(set(gids))
    key = "gw:%d:order" % s
    if not _meta(key):
        order = list(want)
        _RAND.shuffle(order)
        _mark(key, json.dumps(order))
    got = [g for g in json.loads(_meta(key) or "[]") if g in want]
    rest = [g for g in want if g not in got]          # 적어 둔 뒤에 생긴 길드는 없어야 하지만, 있으면 끝에
    return got + rest


def _ring(c):
    """칸 자리 [줄, 차례, 한 바퀴] 이면 그대로, 아니면 None (예전 한반도 지도로 나눈 칸)."""
    if isinstance(c, list) and len(c) == 3 and all(isinstance(v, int) for v in c):
        return c
    return None


def ring_total(cells):
    """한 바퀴의 칸 수 = 칸들에 적힌 것 가운데 가장 큰 것 (가장 큰 열 번호 + 1 보다 작지 않게).

    **칸마다 적힌 수가 섞일 수 있다** (2026-10-20 운영): 두 요청이 겹쳐 지도를 9길드(27열)로 먼저 나눈 뒤,
    늦게 고정된 10번째 길드의 칸이 30열 기준 27~29열로 들어갔다. 첫 칸의 수(27)로 그리면 그 칸들이 한 바퀴를
    넘어 0~2열(동물농장) 위에 포개졌다. 가장 큰 수로 보면 저장된 열 번호 그대로 10길드 지도가 된다.
    """
    rings = [c for c in cells if _ring(c)]
    if not rings:
        return 0
    return max(max(c[2] for c in rings), max(c[1] for c in rings) + 1)


def _cell_adj(cells):
    """칸 번호 -> 맞닿은 칸 번호들. 같은 줄의 옆 칸(고리라 끝과 처음이 맞닿는다)과 같은 차례의 위아래 줄."""
    at = dict(((c[0], c[1]), i) for i, c in enumerate(cells) if _ring(c))
    out = dict((i, set()) for i in range(len(cells)))
    total = ring_total(cells)                       # 칸마다 적힌 수가 아니라 고리 전체의 수로 감는다
    for i, c in enumerate(cells):
        if not _ring(c):
            continue
        row, col, _t = c
        for key in ((row - 1, col), (row + 1, col), (row, (col - 1) % total), (row, (col + 1) % total)):
            j = at.get(key)
            if j is not None and j != i:
                out[i].add(j)
    return out


def cell_id(i):
    return "c%02d" % (i + 1)


def cell_number(c):
    """길드 안의 칸 번호 1 ~ TILES_PER_GUILD (바깥 줄부터, 줄마다 고리를 도는 차례로)."""
    row, col, _total = c
    return row * RING_COLS + col % RING_COLS + 1


def ring_geo(rows, names=None, scale=1000.0):
    """지도 그림 (화면이 그린다 - ui_war_map). 칸마다 부채꼴 하나: {"sgg": [{"code": 칸, "rings": [[x, y]...],
    "area", "center"}], "box", "labels": [{"text", "x", "y"}]}. 이웃한 칸은 경계의 점이 똑같다 (선을 고를 때 쓴다).

    rows 는 guild_war_tile 의 줄 (region, codes, home_guild). names 는 {길드: 이름} - 부채꼴 바깥에 적는다.
    """
    cells = [(r["region"], _ring(json.loads(r["codes"] or "null"))) for r in rows]
    cells = [(rid, c) for rid, c in cells if c]
    if not cells:
        return None
    total = ring_total([c for _rid, c in cells])    # 첫 칸의 수가 아니라 가장 큰 수 (위 ring_total)
    seg = max(2, int(math.ceil(RING_ARC / float(total))))
    steps = total * seg
    thick = (1.0 - RING_INNER) / RING_ROWS

    def pt(b, m):
        r = (1.0 - b * thick) * scale
        a = 2 * math.pi * (m % steps) / steps - math.pi / 2       # 맨 위에서 시계 방향
        return [round(r * math.cos(a), 1), round(r * math.sin(a), 1)]

    out = []
    for rid, (row, col, _t) in cells:
        outer = [pt(row, col * seg + j) for j in range(seg + 1)]
        inner = [pt(row + 1, col * seg + j) for j in range(seg, -1, -1)]
        out.append({"code": rid, "rings": [outer + inner], "area": 1.0,
                    "center": pt(row + 0.5, col * seg + seg / 2.0)})
    labels = []
    homes = {}
    for r in rows:
        c = _ring(json.loads(r["codes"] or "null"))
        if c:
            homes.setdefault(r["home_guild"], []).append(c[1])
    for gid, cols in homes.items():
        if names and gid in names:
            mid = (min(cols) + max(cols) + 1) / 2.0
            x, y = pt(-0.55, mid * seg)
            labels.append({"text": names[gid], "x": x, "y": y, "guildId": gid})
    edge = scale * (1.0 + 0.55 * thick + 0.12)
    return {"sgg": out, "box": [-edge, edge, -edge, edge], "labels": labels}


# ---------------------------------------------------------------- AI 수비대
def _ai_pool():
    """AI 수비대 팀의 후보: 관장 자료의 팀을 Lv.50·개체값 31로 맞춘 것. [(전력, 트레이너, 팀)]"""
    out = []
    for t in gym.gyms()["trainers"]:
        team = [TB.trainer_mon(dict(e, level=AI_LEVEL, iv=31)) for e in t["team"]]
        team = pvp.capped(pvp.restrict(team[:config.MAX_PARTY])[0])
        if team:
            out.append((pvp.team_power(team), t, team))
    out.sort(key=lambda x: (x[0], x[1]["id"]))
    return out


def _ai_teams(powers):
    """참가자 방어팀 전력의 중간값에 가장 가까운 후보 AI_CHOICES 개. [(트레이너, 팀)]"""
    pool = _ai_pool()
    if not pool:
        return []
    ps = sorted(powers) or [pool[len(pool) // 2][0]]
    mid = ps[len(ps) // 2] if len(ps) % 2 else (ps[len(ps) // 2 - 1] + ps[len(ps) // 2]) / 2.0
    near = sorted(pool, key=lambda x: (abs(x[0] - mid), x[1]["id"]))[:AI_CHOICES]
    return [(t, team) for _p, t, team in near]


# ---------------------------------------------------------------- 참가 신청
def entry(gid, s=None):
    return db.q1("SELECT * FROM guild_war_entry WHERE season=? AND guild_id=?",
                 (s or season.SEASON, gid))


def entries(s=None):
    return db.q("SELECT * FROM guild_war_entry WHERE season=? ORDER BY applied_at, guild_id",
                (s or season.SEASON,))


def apply(uid, now=None):
    m = guild._need_manager(uid)
    if phase(now)[0] != "apply":
        raise HTTPException(409, "지금은 참가 신청을 받는 때가 아닙니다.")
    gid = m["guild_id"]
    if guild._count(gid) < MIN_MEMBERS:
        raise HTTPException(409, "길드원이 %d명 이상이어야 길드전에 나갈 수 있습니다." % MIN_MEMBERS)
    if entry(gid):
        raise HTTPException(409, "이미 참가를 신청했습니다.")
    g = guild.guild_of(gid)
    db.run("INSERT INTO guild_war_entry (season, guild_id, name, applied_by, applied_at)"
           " VALUES (?,?,?,?,?)", (season.SEASON, gid, g["name"], uid, _iso(now)))
    guild._say(gid, "%s 님이 길드전 참가를 신청했습니다. 방어팀과 공격팀을 짜 두세요."
               % guild._name_of(uid), now)
    guild._changed(gid)
    return True


def withdraw(uid, now=None):
    m = guild._need_manager(uid)
    if phase(now)[0] != "apply":
        raise HTTPException(409, "참가 신청 기간이 끝난 뒤에는 취소할 수 없습니다.")
    gid = m["guild_id"]
    if not entry(gid):
        raise HTTPException(409, "참가를 신청하지 않았습니다.")
    db.run("DELETE FROM guild_war_entry WHERE season=? AND guild_id=?", (season.SEASON, gid))
    guild._say(gid, "%s 님이 길드전 참가를 취소했습니다." % guild._name_of(uid), now)
    guild._changed(gid)
    return True


# ---------------------------------------------------------------- 팀 짜기
def _row(uid, s=None):
    return db.q1("SELECT * FROM guild_war_team WHERE season=? AND user_id=?",
                 (s or season.SEASON, uid))


def _ids(raw):
    try:
        return [int(x) for x in json.loads(raw or "[]")]
    except (TypeError, ValueError):
        return []


def _mons(uid, ids):
    """내 포켓몬 가운데 ids 에 든 것, 그 순서대로."""
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    rows = dict((r["id"], r) for r in db.q(
        "SELECT * FROM pokemon WHERE user_id=? AND id IN (%s)" % marks, (uid,) + tuple(ids)))
    return [db.row_to_mon(rows[i]) for i in ids if i in rows]


def set_team(uid, kind, ids, now=None):
    """방어팀·공격팀을 짠다. 신청·전략 기간에 된다 (전쟁이 시작되면 고정이다).

    전략 기간에는 이미 명단이 고정돼 있다 - 전쟁에 나가는 사람이면 고정된 팀(def_team/atk_team)도
    같이 고친다. 지키는 칸은 그대로다 (길드장이 옮긴다).
    """
    if kind not in KINDS:
        raise HTTPException(400, "방어팀인지 공격팀인지 알 수 없습니다.")
    m = guild._need(uid)
    ph = phase(now)[0]
    if ph not in ("apply", "plan"):
        raise HTTPException(409, "팀은 전략 기간까지만 바꿀 수 있습니다. 전쟁이 시작되면 고정입니다.")
    clean = []
    for i in ids or []:
        try:
            i = int(i)
        except (TypeError, ValueError):
            continue
        if i not in clean:
            clean.append(i)
    if len(clean) > config.MAX_PARTY:
        raise HTTPException(400, "한 팀은 최대 %d마리입니다." % config.MAX_PARTY)
    mons = _mons(uid, clean)
    if len(mons) != len(clean):
        raise HTTPException(404, "내 포켓몬이 아닌 것이 섞여 있습니다.")
    names = pvp.restricted_species()
    if sum(1 for x in mons if x["species"] in names) > pvp.RESTRICTED_MAX:
        raise HTTPException(409, "전설·환상 포켓몬은 한 팀에 %d마리만 넣을 수 있습니다."
                            % pvp.RESTRICTED_MAX)
    if pvp.too_many_same([x["species"] for x in mons]):
        raise HTTPException(409, "같은 포켓몬은 한 팀에 %d마리만 넣을 수 있습니다." % pvp.SAME_SPECIES_MAX)
    col = "def_ids" if kind == "def" else "atk_ids"
    # 고정된 줄의 길드는 안 바꾼다 - 전략 기간에 다른 길드로 옮긴 사람이 그 길드 사람이 되면 안 된다
    db.run("INSERT INTO guild_war_team (season, user_id, guild_id, name, %s, updated_at)"
           " VALUES (?,?,?,?,?,?) ON CONFLICT(season, user_id) DO UPDATE SET"
           " %s=excluded.%s,"
           " guild_id=CASE WHEN guild_war_team.locked=1 THEN guild_war_team.guild_id ELSE excluded.guild_id END,"
           " name=excluded.name, updated_at=excluded.updated_at" % (col, col, col),
           (season.SEASON, uid, m["guild_id"], guild._name_of(uid), json.dumps(clean), _iso(now)))
    if ph == "plan" and _me_in_war(uid):
        fixed = _snapshot(uid, clean)
        db.run("UPDATE guild_war_team SET %s=? WHERE season=? AND user_id=? AND locked=1"
               % ("def_team" if kind == "def" else "atk_team"), (json.dumps(fixed), season.SEASON, uid))
        return preview(fixed)
    return preview(mons)


def preview(mons):
    """화면에 줄 팀 (종·레벨까지 - 기술·도구는 싸워 봐야 안다)."""
    d = deps.dex()
    out = []
    for m in mons:
        sp = d.get(m["species"]) or {}
        out.append({"id": m.get("id"), "species": m["species"], "num": sp.get("num"),
                    "kr": m.get("nickname") or sp.get("kr"), "level": min(season.LEVEL_CAP, int(m["level"])),
                    "shiny": bool(m.get("shiny")), "tint": m.get("tint") if m.get("shiny") else None})
    return out


def _default_team(uid):
    """안 짠 사람의 팀: 랭크 팀, 없으면 바탕화면 파티."""
    return pvp._ranked_source(uid)


def _snapshot(uid, ids):
    """전쟁에 나갈 팀. 랭크 배틀과 같은 규칙으로 다듬는다 (전설·환상 한 마리, 같은 종 한 마리, 레벨 상한)."""
    mons = _mons(uid, ids) if ids else []
    if not mons:
        mons = _default_team(uid)
    return pvp.capped(pvp.restrict(mons[:config.MAX_PARTY])[0])


def _ready(team):
    """고정해 둔 팀을 판에 올리기 직전에 다시 다듬는다 (10/22).

    팀은 전략 기간에 고정되는데 규칙은 그 뒤에 생길 수 있다 - 같은 종은 한 마리만 나가고(pvp.restrict),
    유대 미션을 마친 개체만 메가진화한다(mega.mark_bonded - 지금의 유대로). AI 수비대 팀은 id 가 없어 유대는 그대로다.
    """
    return mega.mark_bonded(pvp.restrict(team)[0])


# ---------------------------------------------------------------- 명단 고정·지도 나누기 (전략 기간 시작)
def _meta(key):
    r = db.q1("SELECT v FROM meta WHERE k=?", (key,))
    return r["v"] if r else None


def _mark(key, value):
    """표시를 적는다. 이미 있으면 False (누가 먼저 했다)."""
    cur = db.run("INSERT INTO meta (k, v) VALUES (?,?) ON CONFLICT(k) DO NOTHING", (key, value))
    return getattr(cur, "rowcount", 1) > 0


def _lock(now=None):
    """전략 기간이 시작됐으면 참가 길드의 명단과 팀을 고정하고 지도를 나눈다. 한 번만 돈다.

    전쟁이 시작됐으면 팀을 그 순간의 모습으로 한 번 더 고정한다 (_freeze).
    """
    s = season.SEASON
    ph = phase(now)[0]
    if ph not in ("plan", "war", "done"):
        return False
    did = False
    if not _meta("gw:%d:locked" % s):
        did = _lock_all(s, now)
    if ph in ("war", "done") and _meta("gw:%d:locked" % s) and not _meta("gw:%d:fixed" % s):
        _freeze(s, now)
    return did


def _freeze(s, now=None):
    """전쟁이 시작되는 순간의 팀으로 다시 고정한다 (한 번만).

    명단은 전략 기간이 시작될 때 고정했지만, 팀은 그때 모습이 아니라 **전쟁이 시작되는 순간의 기술·도구·
    노력치**로 나간다 - 전략 기간에 '바꾸기' 를 안 누른 사람도 그사이 키운 것이 그대로 실린다.
    길드를 나간 사람의 줄은 건드리지 않는다. 포켓몬을 다 놓아줘서 팀이 비면 전에 고정한 것을 둔다.
    """
    if not _mark("gw:%d:fixed" % s, _iso(now)):
        return
    for r in db.q("SELECT * FROM guild_war_team WHERE season=? AND locked=1", (s,)):
        uid = r["user_id"]
        m = guild.member(uid)
        if not m or m["guild_id"] != r["guild_id"]:
            continue
        try:
            d_team = _snapshot(uid, _ids(r["def_ids"]))
            a_team = _snapshot(uid, _ids(r["atk_ids"]))
            if d_team and a_team:
                db.run("UPDATE guild_war_team SET def_team=?, atk_team=? WHERE season=? AND user_id=?",
                       (json.dumps(d_team), json.dumps(a_team), s, uid))
        except Exception as err:                              # noqa: BLE001
            from . import errors
            errors.record("GWAR", "guild_war._freeze %s" % uid, err)


def _lock_all(s, now=None):
    """참가 길드의 명단을 고정하고 지도를 나눈다 (_lock 이 부른다)."""
    whole = True
    for e in entries(s):
        gid = e["guild_id"]
        # **길드마다 표시를 먼저 적는다.** 두 요청이 같이 들어와도 한 길드는 한쪽만 고정한다.
        if e["locked"] != 0 or not _mark("gw:%d:locked:%d" % (s, gid), _iso(now)):
            continue
        try:
            _lock_guild(s, gid, now)
        except Exception as err:                              # noqa: BLE001
            # 이 길드를 고정하다 터졌다. 표시를 지워 다음 요청이 다시 해 보게 하고(이미 넣은 줄은
            # 같은 값으로 다시 써질 뿐이다), 남은 길드는 계속한다 - 한 길드 때문에 전쟁이 안 열리면 안 된다.
            db.run("DELETE FROM meta WHERE k=?", ("gw:%d:locked:%d" % (s, gid),))
            from . import errors
            errors.record("GWAR", "guild_war._lock %s" % gid, err)
            whole = False
    if not whole:
        return True
    # **다른 요청이 아직 고정 중인 길드가 있으면 지도를 나누지 않는다** (2026-10-20 운영). 그 길드는 위에서
    # 표시를 보고 건너뛰었다 - 여기서 나누면 그 길드를 뺀 지도가 먼저 생기고(9길드 27열), 그 길드는 나중에
    # 다른 열 수로 끼어들어 남의 칸 위에 포개진다. 고정을 마친 쪽이 다시 와서 나눈다.
    # 표시가 STALE_LOCK_SEC 넘게 묵었으면 고정하던 서버가 죽은 것이다 - 지워서 다음 요청이 다시 고정하게 한다.
    busy = False
    for e in entries(s):
        if e["locked"] != 0:
            continue
        key = "gw:%d:locked:%d" % (s, e["guild_id"])
        when = parse_time(_meta(key))
        if when is None or ((now or _now()) - when).total_seconds() > STALE_LOCK_SEC:
            db.run("DELETE FROM meta WHERE k=?", (key,))
        busy = True
    if busy:
        return True
    try:
        _deal(s, now)                         # 명단이 다 고정됐으니 지도를 나눈다
    except Exception as err:                                  # noqa: BLE001
        from . import errors
        errors.record("GWAR", "guild_war._deal", err)
        return True                           # 표시를 안 적었으니 다음 요청이 다시 나눈다 (같은 줄이 들어간다)
    _mark("gw:%d:locked" % s, _iso(now))      # 다 끝났다 - 이제부터는 위에서 바로 돌아간다
    return True


def _lock_guild(s, gid, now=None):
    """길드 하나의 명단과 팀을 고정한다. 공격 횟수는 인원수로 나눠 두고, 길드장이 나중에 바꾼다."""
    alive = bool(db.q1("SELECT 1 FROM guild WHERE id=?", (gid,)))
    rows = db.q("SELECT user_id, joined_at FROM guild_member WHERE guild_id=?"
                " ORDER BY joined_at, user_id", (gid,))
    people = []
    for r in rows:
        uid = r["user_id"]
        t = _row(uid, s)
        d_team = _snapshot(uid, _ids(t["def_ids"]) if t else [])
        a_team = _snapshot(uid, _ids(t["atk_ids"]) if t else [])
        if d_team and a_team:
            people.append((uid, d_team, a_team))
    if len(people) < MIN_MEMBERS:
        # 신청한 뒤에 사람이 빠져 모자라게 됐다 (길드가 해산된 것도 여기로 온다). 이번에 못 나간다.
        db.run("UPDATE guild_war_entry SET locked=-1 WHERE season=? AND guild_id=?", (s, gid))
        if alive:
            guild._say(gid, "길드전 전략 기간이 시작됐지만 싸울 수 있는 길드원이 %d명이 안 되어 이번에는 "
                       "나가지 못합니다." % MIN_MEMBERS, now)
        return
    counts = quota(len(people))
    for (uid, d_team, a_team), n in zip(people, counts):
        # used·attacks 는 다시 고정하게 되더라도 건드리지 않는다 (이미 쓴 횟수가 0 으로 돌아가면 안 된다)
        db.run("INSERT INTO guild_war_team (season, user_id, guild_id, name, def_team, atk_team,"
               " attacks, used, locked, updated_at) VALUES (?,?,?,?,?,?,?,0,1,?)"
               " ON CONFLICT(season, user_id) DO UPDATE SET guild_id=excluded.guild_id,"
               " name=excluded.name, def_team=excluded.def_team, atk_team=excluded.atk_team,"
               " attacks=CASE WHEN guild_war_team.locked=1 THEN guild_war_team.attacks"
               " ELSE excluded.attacks END, locked=1, updated_at=excluded.updated_at",
               (s, uid, gid, guild._name_of(uid), json.dumps(d_team), json.dumps(a_team), n, _iso(now)))
    db.run("UPDATE guild_war_entry SET locked=1 WHERE season=? AND guild_id=?", (s, gid))
    guild._say(gid, "길드전 전략 기간이 시작됐습니다! 지도가 나뉘고 명단이 고정됐습니다. 전쟁이 시작되기 전까지 "
               "길드장은 공격 횟수(길드 합쳐 %d번, 지금은 한 사람 %s번)와 지킬 칸을 정하고, 길드원은 팀을 "
               "고칠 수 있습니다. 전쟁이 시작되면 바꿀 수 없습니다."
               % (TOTAL_ATTACKS, "~".join(str(x) for x in sorted(set(counts)))), now)
    guild._changed(gid)


def _deal(s, now=None):
    """전쟁에 나간 길드들에게 지도를 나누고 지키는 사람을 정한다. 넣은 줄 수를 돌려준다.

    지키는 사람: 방어팀 전력이 센 사람부터, **남의 칸과 많이 맞닿은 칸에** 한 사람씩. 남는 칸은
    AI 수비대. 다시 불러도 이미 있는 줄은 그대로 둔다 (같은 값이다).
    """
    gids = [e["guild_id"] for e in in_war(s)]
    if not gids:
        return 0
    cells, owner, _per = layout(placement(s, gids))
    adj = _cell_adj(cells)
    team_of = dict((r["user_id"], json.loads(r["def_team"])) for r in db.q(
        "SELECT user_id, def_team FROM guild_war_team WHERE season=? AND locked=1", (s,)))
    ai = _ai_teams([pvp.team_power(t) for t in team_of.values() if t])
    n = 0
    for gid in sorted(set(owner)):
        mine = [i for i, g in enumerate(owner) if g == gid]
        e = entry(gid, s)
        gname = (e["name"] if e else None) or "길드"
        exposed = sorted(mine, key=lambda i: (-sum(1 for j in adj[i] if owner[j] != gid), i))
        people = sorted((r["user_id"] for r in fighters(gid, s)),
                        key=lambda u: (-pvp.team_power(team_of.get(u) or []), u))
        new = 0
        for k, i in enumerate(exposed):
            rid = cell_id(i)
            if k < len(people):
                vals = (people[k], None, None, None)
            else:
                t, team = ai[int(hashlib.sha256(("%d:%s" % (s, rid)).encode()).hexdigest()[:8], 16) % len(ai)]
                vals = (AI_GUARD, json.dumps(team), t.get("name") or "수비대", t.get("sprite"))
            cur = db.run("INSERT INTO guild_war_tile (season, region, name, codes, guild_id, guard_user, home_guild,"
                         " ai_team, ai_name, ai_sprite) VALUES (?,?,?,?,?,?,?,?,?,?)"
                         " ON CONFLICT(season, region) DO NOTHING",
                         (s, rid, "%s %d번" % (gname, cell_number(cells[i])), json.dumps(cells[i]), gid, vals[0],
                          gid) + vals[1:])
            new += 1 if getattr(cur, "rowcount", 1) > 0 else 0
        n += new
        if new and db.q1("SELECT 1 FROM guild WHERE id=?", (gid,)):      # 처음 나눌 때만 알린다
            guild._say(gid, "지도가 나뉘었습니다. 우리 길드는 %d칸 - 전쟁이 시작되면 맞닿은 남의 칸을 눌러 "
                            "공격하세요. 같은 사람을 %d번 이기면 그 칸을 가져옵니다." % (len(mine), WINS_TO_TAKE), now)
    return n


def fighters(gid, s=None):
    """그 길드에서 이번 전쟁에 나간 사람들 (고정된 줄)."""
    return db.q("SELECT * FROM guild_war_team WHERE season=? AND guild_id=? AND locked=1"
                " ORDER BY user_id", (s or season.SEASON, gid))


def in_war(s=None):
    """전쟁에 나간 길드들 (명단이 고정된 것)."""
    return [e for e in entries(s) if e["locked"] == 1]


# ---------------------------------------------------------------- 칸
def tile(region, s=None):
    return db.q1("SELECT * FROM guild_war_tile WHERE season=? AND region=?", (s or season.SEASON, str(region)))


def tiles(s=None):
    return db.q("SELECT * FROM guild_war_tile WHERE season=? ORDER BY region", (s or season.SEASON,))


def tile_counts(s=None):
    """길드 -> 지금 가진 칸 수."""
    return dict((r["guild_id"], r["n"]) for r in db.q(
        "SELECT guild_id, COUNT(*) n FROM guild_war_tile WHERE season=? GROUP BY guild_id",
        (s or season.SEASON,)))


def neighbors(s=None):
    """칸 -> 맞닿은 칸들 (지도는 전쟁 내내 그대로라 칸의 시·군·구로 다시 셈한다)."""
    rows = tiles(s)
    cells = [json.loads(r["codes"] or "[]") for r in rows]
    adj = _cell_adj(cells)
    ids = [r["region"] for r in rows]
    return dict((ids[i], set(ids[j] for j in adj[i])) for i in range(len(ids)))


def _guard_name(t, s=None):
    if t["guard_user"] == AI_GUARD:
        return "AI 수비대 (%s)" % (t["ai_name"] or "수비대")
    r = _row(t["guard_user"], s)
    return r["name"] if r else "?"


def _guard_team(t, s=None):
    if t["guard_user"] == AI_GUARD:
        return json.loads(t["ai_team"] or "[]")
    r = _row(t["guard_user"], s)
    return json.loads(r["def_team"]) if r else []


def _wins(s, region, gid):
    """그 칸에서 그 길드가 지금까지 이긴 수 (끝난 판만)."""
    return db.q1("SELECT COUNT(*) c FROM guild_war_attack WHERE season=? AND region=? AND atk_guild=?"
                 " AND result='win'", (s, region, gid))["c"]


def _received(s, gid):
    """그 길드의 칸이 받은 공격 수 (진행 중인 판도 센다)."""
    return db.q1("SELECT COUNT(*) c FROM guild_war_attack WHERE season=? AND def_guild=?", (s, gid))["c"]


def _attacked(s, region):
    return bool(db.q1("SELECT 1 FROM guild_war_attack WHERE season=? AND region=? LIMIT 1", (s, region)))


def _me_in_war(uid):
    """전쟁에 나간 내 줄. 길드를 나갔으면 None (남은 공격권은 사라진다)."""
    t = _row(uid)
    m = guild.member(uid)
    if not t or t["locked"] != 1 or not m or m["guild_id"] != t["guild_id"]:
        return None
    return t


def _my_gid(uid, s=None):
    """이 사람이 **지금** 든 길드. 방어팀을 다 보여 줄지는 이것으로 정한다 - 전쟁 중에 길드를 나간
    사람에게는 옛 길드의 방어팀도 남의 것처럼 앞 몇 마리만 보인다."""
    m = guild.member(uid)
    return m["guild_id"] if m else None


def _why(uid, t, s, adj=None, now=None, memo=None):
    """이 칸을 지금 내가 칠 수 없는 까닭 (칠 수 있으면 None). 공격할 때도 이것으로 본다.

    memo 를 주면 칸마다 같은 것을 다시 묻지 않는다 (지도 한 장에서 칸 수십 개를 볼 때)."""
    memo = memo if memo is not None else {}
    if "phase" not in memo:
        memo["phase"] = phase(now)[0]
    if memo["phase"] == "plan":
        return "아직 전략 기간이다 (공격은 전쟁이 시작되면)"
    if memo["phase"] != "war":
        return "지금은 전쟁 중이 아니다"
    if "me" not in memo:
        memo["me"] = _me_in_war(uid)
    me = memo["me"]
    if not me:
        return "이번 길드전에 나가지 않았다"
    if t["guild_id"] == me["guild_id"]:
        return "우리 길드의 칸이다"
    if t["taken_at"]:
        return "이미 주인이 바뀐 칸이다 (다시 못 뺏는다)"
    adj = adj if adj is not None else neighbors(s)
    if "mine" not in memo:
        memo["mine"] = set(r["region"] for r in db.q(
            "SELECT region FROM guild_war_tile WHERE season=? AND guild_id=?", (s, me["guild_id"])))
    if not (adj.get(t["region"], set()) & memo["mine"]):
        return "우리 칸과 맞닿지 않았다"
    if me["used"] >= me["attacks"]:
        return "공격 횟수를 다 썼다"
    got = memo.setdefault("received", {})
    if t["guild_id"] not in got:
        got[t["guild_id"]] = _received(s, t["guild_id"])
    if got[t["guild_id"]] >= TOTAL_ATTACKS:
        return "이 길드는 더 받을 수 없다"
    return None


# ---------------------------------------------------------------- 조커 · 기여 보상 (시즌 5)
def v5():
    """조커 · 기여 보상이 켜졌나 (시즌 번호에 묶는다 - season.rules_v5)."""
    return season.rules_v5()


def _joker_ids(s):
    """조커로 숨긴 사람들 (전쟁에 나간 줄). 꺼져 있으면 빈 것."""
    if not v5():
        return set()
    return set(r["user_id"] for r in db.q(
        "SELECT user_id FROM guild_war_team WHERE season=? AND locked=1 AND joker=1", (s,)))


def _joker_tile(t, jokers):
    """조커 칸인가 (지도 표시 · 조커를 이긴 보상) - 사람이 지키고, 그 사람이 조커이고, 아직 안 넘어간 칸."""
    return bool(t["guard_user"] != AI_GUARD and not t["taken_at"] and t["guard_user"] in jokers)


def _joker_hidden(t, my, s, jokers):
    """길드 my 에게 이 칸을 지키는 쪽이 가려지나 - 지키는 사람이 조커면. **조커가 뺏어 지키는 칸(넘어간 칸)도**
    가린다: 거기서 이름과 방어팀 앞 몇 마리가 보이면 숨긴 칸의 것이 그대로 드러난다 (같은 방어팀이다).
    우리 길드 칸이면, 또는 우리 길드가 그 사람과 한 번이라도 붙어 봤으면 안 가린다 (이미 봤다)."""
    if t["guard_user"] == AI_GUARD or t["guard_user"] not in jokers or (my is not None and t["guild_id"] == my):
        return False
    if my is None:
        return True
    return not db.q1("SELECT 1 FROM guild_war_attack WHERE season=? AND def_user=? AND atk_guild=? LIMIT 1",
                     (s, t["guard_user"], my))


def joker_count(gid, s=None):
    return db.q1("SELECT COUNT(*) c FROM guild_war_team WHERE season=? AND guild_id=? AND locked=1 AND joker=1",
                 (s or season.SEASON, gid))["c"]


def set_joker(uid, region, on, now=None):
    """길드장이 그 칸을 지키는 길드원을 조커로 숨기거나 푼다 (전략 기간에만, 길드마다 JOKER_MAX 명).
    조커는 사람에 붙는다 - 나중에 그 사람을 다른 칸으로 옮겨도 그대로다."""
    if not v5():
        raise HTTPException(409, "조커는 시즌 5 부터입니다.")
    m = guild._need_manager(uid)
    if phase(now)[0] != "plan":
        raise HTTPException(409, "조커는 전략 기간에만 정할 수 있습니다. 전쟁이 시작되면 바꿀 수 없습니다.")
    s = season.SEASON
    gid = m["guild_id"]
    t = tile(region, s)
    if not t or t["guild_id"] != gid or t["home_guild"] != gid:
        raise HTTPException(409, "우리 길드의 칸이 아닙니다.")
    if t["guard_user"] == AI_GUARD:
        raise HTTPException(409, "AI 수비대는 조커로 숨길 수 없습니다. 길드원이 지키는 칸을 고르세요.")
    who = _row(t["guard_user"], s)
    if not who or who["locked"] != 1 or who["guild_id"] != gid:
        raise HTTPException(404, "이번 길드전에 나간 길드원이 아닙니다.")
    want = 1 if on else 0
    if int(who["joker"] or 0) == want:
        return False
    if want:
        # 셈과 고치기를 한 문장에 - 두 길드장이 같이 눌러도 JOKER_MAX 를 못 넘는다
        cur = db.run("UPDATE guild_war_team SET joker=1 WHERE season=? AND user_id=? AND locked=1 AND joker=0"
                     " AND (SELECT COUNT(*) FROM guild_war_team WHERE season=? AND guild_id=? AND locked=1"
                     " AND joker=1) < ?", (s, who["user_id"], s, gid, JOKER_MAX))
        if getattr(cur, "rowcount", 1) == 0:
            raise HTTPException(409, "조커는 길드마다 %d명까지입니다. 다른 조커를 먼저 풀어 주세요." % JOKER_MAX)
    else:
        db.run("UPDATE guild_war_team SET joker=0 WHERE season=? AND user_id=?", (s, who["user_id"]))
    n = joker_count(gid, s)
    guild._say(gid, ("%s 님이 %s 님을 조커로 숨겼습니다 (%d/%d명). 다른 길드에는 이름과 방어팀이 '???' 로 보입니다."
                     if want else "%s 님이 %s 님의 조커를 풀었습니다 (%d/%d명).")
               % (guild._name_of(uid), who["name"], n, JOKER_MAX), now)
    return True


def _pay(s, uid, n):
    """기여 보상을 준다 - 이번 시즌 받은 것(guild_war_team.earned)이 CONTRIB_MAX 를 넘지 않게. 준 수를 돌려준다.

    받은 것을 먼저 늘린다(조건을 건 UPDATE - 두 판이 같이 끝나도 상한을 못 넘는다) 그리고 코인을 넣는다."""
    if n <= 0 or not uid:
        return 0
    for _ in range(5):
        r = db.q1("SELECT earned FROM guild_war_team WHERE season=? AND user_id=?", (s, uid))
        if not r:
            return 0
        had = int(r["earned"] or 0)
        give = min(n, CONTRIB_MAX - had)
        if give <= 0:
            return 0
        cur = db.run("UPDATE guild_war_team SET earned=earned+? WHERE season=? AND user_id=? AND earned=?",
                     (give, s, uid, had))
        if getattr(cur, "rowcount", 1) > 0:
            guild._coin_add(uid, give)
            return give
    return 0


def _reward(a, res, raw=None):
    """공격 한 판이 끝났다 (_finish 가 적은 뒤에 한 번) - 이긴 공격자, 막아 낸 지키는 사람에게 기여 보상.
    (공격자가 받은 것, 지킨 사람이 받은 것, 조커를 이겼나). 보상이 깨져도 판의 결과는 그대로다.

    raw 는 판의 진짜 결과 (won / lost / draw / forfeit / expired). 지킨 사람은 lost 일 때만 받는다 (위 설명)."""
    if not v5():
        return 0, 0, False
    s = a["season"]
    got = kept = 0
    joker = False
    try:
        if res == "win":
            joker = bool(a["def_user"]) and a["def_user"] in _joker_ids(s)
            got = _pay(s, a["atk_user"], CONTRIB_WIN + (CONTRIB_JOKER if joker else 0))
        elif res == "lose" and raw == "lost" and a["def_user"] != AI_GUARD:
            kept = _pay(s, a["def_user"], CONTRIB_DEFEND)
        if got or kept:
            db.run("UPDATE guild_war_attack SET coins=?, def_coins=? WHERE id=?", (got, kept, a["id"]))
    except Exception as err:                                  # noqa: BLE001
        from . import errors
        errors.record("GWAR", "guild_war._reward %s" % a["id"], err)
    return got, kept, joker


def _earned(s, uid):
    r = db.q1("SELECT earned FROM guild_war_team WHERE season=? AND user_id=?", (s, uid))
    return int(r["earned"] or 0) if r else 0


# ---------------------------------------------------------------- 길드장이 하는 일
def set_attacks(uid, plan, now=None):
    """길드장이 공격 횟수를 나눈다 (전략 기간에만). plan = {사람: 횟수}. 한 사람 최소 1번(이미 쓴 것보다
    적게는 안 된다), 길드 합 TOTAL_ATTACKS 까지. 안 적은 사람은 그대로 둔다."""
    m = guild._need_manager(uid)
    if phase(now)[0] != "plan":
        raise HTTPException(409, "공격 횟수는 전략 기간에만 나눌 수 있습니다. 전쟁이 시작되면 바꿀 수 없습니다.")
    s = season.SEASON
    gid = m["guild_id"]
    rows = dict((r["user_id"], r) for r in fighters(gid, s))
    if not rows:
        raise HTTPException(409, "이번 길드전에 나가지 않았습니다.")
    want = dict((u, r["attacks"]) for u, r in rows.items())
    for k, v in (plan or {}).items():
        try:
            k, v = int(k), int(v)
        except (TypeError, ValueError):
            raise HTTPException(400, "횟수를 알 수 없습니다.")
        if k not in rows:
            raise HTTPException(404, "이번 길드전에 나간 길드원이 아닙니다.")
        if v < max(1, rows[k]["used"]):
            raise HTTPException(409, "%s 님은 %d번 아래로 줄일 수 없습니다 (최소 1번, 이미 쓴 만큼)."
                                % (rows[k]["name"], max(1, rows[k]["used"])))
        want[k] = v
    if sum(want.values()) > TOTAL_ATTACKS:
        raise HTTPException(409, "길드 합쳐 %d번까지입니다 (지금 %d번)." % (TOTAL_ATTACKS, sum(want.values())))
    changed = 0
    for k, v in want.items():
        if v == rows[k]["attacks"]:
            continue
        # 쓰는 사이에 횟수가 넘치지 않게 조건을 건다
        cur = db.run("UPDATE guild_war_team SET attacks=? WHERE season=? AND user_id=? AND used<=?",
                     (v, s, k, v))
        if getattr(cur, "rowcount", 1) == 0:
            raise HTTPException(409, "그사이 %s 님이 공격했습니다. 다시 불러와 주세요." % rows[k]["name"])
        changed += 1
    if changed:
        guild._say(gid, "%s 님이 길드전 공격 횟수를 다시 나눴습니다." % guild._name_of(uid), now)
    return changed


def place(uid, member, region, now=None):
    """길드장이 길드원 한 사람을 그 칸으로 옮긴다 (전략 기간에만). 그 칸에 다른 사람이 있으면 자리를
    맞바꾸고, AI 수비대 칸이면 원래 칸이 AI 수비대 칸이 된다. **공격받은 적 있는 칸은 못 건드린다**
    (전략 기간에는 공격이 없으니 걸릴 일이 없지만, 판이 남아 있는 칸을 지키려고 그대로 둔다)."""
    m = guild._need_manager(uid)
    if phase(now)[0] != "plan":
        raise HTTPException(409, "지키는 칸은 전략 기간에만 바꿀 수 있습니다. 전쟁이 시작되면 바꿀 수 없습니다.")
    s = season.SEASON
    gid = m["guild_id"]
    member = int(member)
    who = _row(member, s)
    if not who or who["locked"] != 1 or who["guild_id"] != gid:
        raise HTTPException(404, "이번 길드전에 나간 길드원이 아닙니다.")
    to = tile(region, s)
    if not to or to["guild_id"] != gid or to["home_guild"] != gid:
        raise HTTPException(409, "우리 길드의 칸이 아닙니다.")
    if to["guard_user"] == member:
        return False
    if _attacked(s, to["region"]):
        raise HTTPException(409, "공격받은 적 있는 칸은 지키는 사람을 바꿀 수 없습니다.")
    frm = db.q1("SELECT * FROM guild_war_tile WHERE season=? AND guild_id=? AND guard_user=? AND taken_at IS NULL",
                (s, gid, member))
    if frm and _attacked(s, frm["region"]):
        raise HTTPException(409, "%s 님이 지키는 칸은 공격받은 적이 있어 옮길 수 없습니다." % who["name"])
    if not frm and to["guard_user"] != AI_GUARD:
        raise HTTPException(409, "지키는 칸이 없는 사람은 AI 수비대 칸으로만 옮길 수 있습니다.")
    if to["guard_user"] == AI_GUARD:
        # AI 칸으로 간다: 원래 칸에는 그 AI 팀이 옮겨 간다 (AI 수비대 수는 그대로)
        db.run("UPDATE guild_war_tile SET guard_user=?, ai_team=NULL, ai_name=NULL, ai_sprite=NULL"
               " WHERE season=? AND region=?", (member, s, to["region"]))
        if frm:
            db.run("UPDATE guild_war_tile SET guard_user=?, ai_team=?, ai_name=?, ai_sprite=? WHERE season=? AND region=?",
                   (AI_GUARD, to["ai_team"], to["ai_name"], to["ai_sprite"], s, frm["region"]))
    else:
        db.run("UPDATE guild_war_tile SET guard_user=? WHERE season=? AND region=?", (member, s, to["region"]))
        db.run("UPDATE guild_war_tile SET guard_user=? WHERE season=? AND region=?",
               (to["guard_user"], s, frm["region"]))
    guild._say(gid, "%s 님이 %s 님을 %s 에 배치했습니다." % (guild._name_of(uid), who["name"], to["name"]), now)
    return True


# ---------------------------------------------------------------- 공격 (관장식 승부)
def is_war(region):
    return str(region or "").startswith(PREFIX)


def battle_region(s, region):
    return "%s%d:%s" % (PREFIX, s, region)


def parse(region):
    """"gw:4:c07" -> (4, "c07"). 아니면 None."""
    if not is_war(region):
        return None
    try:
        _p, s, cell = str(region).split(":")
        return int(s), cell
    except ValueError:
        return None


def _trainer(t, s):
    """그 칸을 지키는 쪽을 관장 판의 '트레이너' 로."""
    e = entry(t["guild_id"], s)
    gname = e["name"] if e else "?"
    team = _ready(_guard_team(t, s))
    if t["guard_user"] == AI_GUARD:
        name, sprite, uid = "AI 수비대", t["ai_sprite"], None
    else:
        r = _row(t["guard_user"], s)
        name, sprite, uid = (r["name"] if r else "?"), None, t["guard_user"]
    return {"id": "gw:%s" % t["region"], "name": name, "role": "[%s]" % gname, "sprite": sprite,
            "level": AI_LEVEL, "team": team, "noMega": True, "ai": "war",
            # 사람이 지키는 칸은 그 사람의 키스톤·Z링을 쓴다. AI 수비대는 둘 다 가졌다.
            "keystone": mega.has_keystone(uid) if uid else True,
            "zring": gimmick.has_zring(uid) if uid else True}


def _active_battle(uid):
    return db.q1("SELECT * FROM gym_battle WHERE user_id=? AND state='active' ORDER BY id DESC LIMIT 1", (uid,))


def attack(uid, region, now=None):
    """그 칸에 승부를 건다. 공격권 하나를 쓰고 관장 배틀 판을 연다 (끝나면 on_end).

    돌려주는 것은 관장 배틀의 시작(gym_routes.start)과 같은 꼴이라 관장 배틀 창이 그대로 연다.
    """
    _lock(now)
    expire(now)
    if phase(now)[0] != "war":
        raise HTTPException(409, "지금은 전쟁 중이 아닙니다.")
    s = season.SEASON
    me = _me_in_war(uid)
    if not me:
        raise HTTPException(403, "이번 길드전에 나가지 않았습니다.")
    t = tile(region, s)
    if not t:
        raise HTTPException(404, "그런 칸이 없습니다.")
    why = _why(uid, t, s, now=now)
    if why:
        raise HTTPException(409, "칠 수 없습니다: %s." % why)
    if _active_battle(uid):
        raise HTTPException(409, "아직 끝나지 않은 승부가 있습니다. 그 승부를 먼저 끝내 주세요.")
    trainer = _trainer(t, s)
    if not trainer["team"]:
        raise HTTPException(409, "그 칸을 지키는 팀이 없습니다.")
    tb = TB.TrainerBattle(deps.dex(), _ready(json.loads(me["atk_team"])), trainer, random.Random())
    tb.keystone["me"] = mega.has_keystone(uid)
    tb.zring["me"] = gimmick.has_zring(uid)
    events = tb.start()
    # 공격권을 먼저 쓴다. 조건을 건 UPDATE 라 두 창에서 동시에 눌러도 한도를 못 넘는다.
    cur = db.run("UPDATE guild_war_team SET used=used+1 WHERE season=? AND user_id=? AND used < attacks", (s, uid))
    if getattr(cur, "rowcount", 1) == 0:
        raise HTTPException(409, "공격할 수 있는 횟수를 다 썼습니다.")
    stamp = _iso(now)
    bid = db.run("INSERT INTO gym_battle (user_id, region, trainer, state, turn, rev, data, created_at, updated_at)"
                 " VALUES (?,?,?,?,?,?,?,?,?)",
                 (uid, battle_region(s, t["region"]), "gw", "active", 0, 0, json.dumps(tb.dump()), stamp,
                  (now or _now()).isoformat())).lastrowid
    # **상한과 칸의 주인은 넣는 문장 안에서 다시 본다.** 위에서 본 것은 안내용이다 - 같은 순간에 둘이
    # 치면 둘 다 위를 지나오므로, 여기서 세어 넘치거나 그사이 칸이 넘어갔으면 안 넣는다.
    cur = db.run(
        "INSERT INTO guild_war_attack (season, region, atk_user, atk_guild, atk_name, def_user, def_guild, def_name,"
        " result, battle_id, created_at) SELECT ?,?,?,?,?,?,?,?,?,?,?"
        " WHERE (SELECT COUNT(*) FROM guild_war_attack WHERE season=? AND def_guild=?) < ?"
        " AND EXISTS (SELECT 1 FROM guild_war_tile WHERE season=? AND region=? AND guild_id=? AND guard_user=?"
        " AND taken_at IS NULL)",
        (s, t["region"], uid, me["guild_id"], me["name"], t["guard_user"], t["guild_id"], trainer["name"], "pending",
         bid, stamp, s, t["guild_id"], TOTAL_ATTACKS, s, t["region"], t["guild_id"], t["guard_user"]))
    if getattr(cur, "rowcount", 1) == 0:
        db.run("DELETE FROM gym_battle WHERE id=?", (bid,))
        db.run("UPDATE guild_war_team SET used=used-1 WHERE season=? AND user_id=?", (s, uid))
        raise HTTPException(409, "그사이 그 칸이 넘어갔거나 더 받을 수 없게 됐습니다. 다른 칸을 고르세요.")
    wins = _wins(s, t["region"], me["guild_id"])
    _watch_open(me, t, trainer, bid, tb, events, wins)
    return {"id": bid, "region": battle_region(s, t["region"]), "rev": 0, "battle": tb.view(), "events": events,
            "watchers": watchers.count(fight_id(bid)),
            "war": {"region": t["region"], "name": t["name"], "wins": wins, "need": WINS_TO_TAKE}}


def _finish(a, res, turns=0, now=None):
    """공격 한 판의 끝을 적는다. 이겨서 승수가 찼으면 칸을 가져온다. (적었나, 가져왔나)"""
    s = a["season"]
    cur = db.run("UPDATE guild_war_attack SET result=?, turns=?, ended_at=? WHERE id=? AND result='pending'",
                 (res, int(turns or 0), _iso(now), a["id"]))
    if getattr(cur, "rowcount", 1) == 0:
        return False, False
    took = False
    if res == "win" and _wins(s, a["region"], a["atk_guild"]) >= WINS_TO_TAKE:
        # 조건을 건 UPDATE 라, 같은 순간에 둘이 셋째 승을 거둬도 한쪽만 가져간다
        cur = db.run("UPDATE guild_war_tile SET guild_id=?, guard_user=?, ai_team=NULL, ai_name=NULL, ai_sprite=NULL,"
                     " taken_at=? WHERE season=? AND region=? AND taken_at IS NULL AND guild_id=?",
                     (a["atk_guild"], a["atk_user"], _iso(now), s, a["region"], a["def_guild"]))
        took = getattr(cur, "rowcount", 1) > 0
        if took:
            db.run("UPDATE guild_war_attack SET took=1 WHERE id=?", (a["id"],))
    return True, took


def on_end(uid, row, tb, events=None, now=None):
    """관장 배틀 창에서 길드전 판이 끝났다 (gym_routes.act 가 부른다). 결과 창에 적을 줄을 돌려준다."""
    a = db.q1("SELECT * FROM guild_war_attack WHERE battle_id=?", (row["id"],))
    if not a or a["atk_user"] != uid:
        return None
    res = RESULT_OF.get(tb.result, "lose")
    wrote, took = _finish(a, res, tb.turn, now)
    if not wrote:
        return None
    got, kept, joker = _reward(a, res, tb.result)
    s = a["season"]
    t = tile(a["region"], s)
    wins = _wins(s, a["region"], a["atk_guild"])
    gname = (entry(a["def_guild"], s) or {"name": "?"})["name"]
    mine_name = (entry(a["atk_guild"], s) or {"name": "?"})["name"]
    where = t["name"] if t else a["region"]
    lines = []
    if took:
        lines.append("%s 을(를) 점령했다! 이제 우리 길드의 칸이다." % where)
        mine_text = "길드전: %s 님이 [%s] 의 칸을 점령했습니다! - %s" % (a["atk_name"], gname, where)
        foe_text = "길드전: [%s] %s 님에게 칸을 빼앗겼습니다. - %s" % (mine_name, a["atk_name"], where)
    elif res == "win":
        left = max(0, WINS_TO_TAKE - wins)
        lines.append("%s - %d승 중 %d승." % (where, WINS_TO_TAKE, min(wins, WINS_TO_TAKE)))
        if t and t["taken_at"] and t["guild_id"] != a["atk_guild"]:
            lines.append("그사이 다른 길드가 이 칸을 먼저 가져갔다.")
        elif left:
            lines.append("한 번 더 이기면 이 칸을 가져온다." if left == 1 else "%d번 더 이기면 이 칸을 가져온다." % left)
        mine_text = "길드전: %s 님이 [%s] %s 을(를) 이겼습니다 - %s (%d승 중 %d승)" % (
            a["atk_name"], gname, a["def_name"], where, WINS_TO_TAKE, min(wins, WINS_TO_TAKE))
        foe_text = "길드전: [%s] %s 님에게 %s 이(가) 졌습니다 - %s (%d승 중 %d승)" % (
            mine_name, a["atk_name"], a["def_name"], where, WINS_TO_TAKE, min(wins, WINS_TO_TAKE))
    else:
        mine_text = "길드전: %s 님이 [%s] %s 에게 졌습니다. - %s" % (a["atk_name"], gname, a["def_name"], where)
        foe_text = "길드전: [%s] %s 님의 공격을 %s 이(가) 막아냈습니다! - %s" % (
            mine_name, a["atk_name"], a["def_name"], where)
        if kept:
            foe_text += " (기여 보상: 길드 코인 %d개)" % kept
    if v5() and res == "win":
        if got:
            lines.append("기여 보상: 길드 코인 %d개%s - 이번 시즌 %d / %d개." % (
                got, " (조커를 이겼다!)" if joker else "", _earned(s, uid), CONTRIB_MAX))
        else:
            lines.append("기여 보상은 이번 시즌 상한(%d개)을 다 받았다." % CONTRIB_MAX)
    guild._say(a["atk_guild"], mine_text, now)
    if db.q1("SELECT 1 FROM guild WHERE id=?", (a["def_guild"],)):
        guild._say(a["def_guild"], foe_text, now)
    _watch_end(a, tb, events, (row["rev"] or 0) + 1, res, took, wins, mine_text)
    return {"lines": lines, "war": {"region": a["region"], "name": where, "wins": wins, "need": WINS_TO_TAKE,
                                    "took": took, "result": res}}


def expire(now=None, everything=False):
    """손 놓은 길드전 판을 접는다 (진 것으로). everything 이면 진행 중인 것도 전부 (전쟁이 끝났다)."""
    now = now or _now()
    cutoff = (now - datetime.timedelta(seconds=config.GYM_BATTLE_TTL)).isoformat()
    db.run("UPDATE gym_battle SET state='done', result='expired' WHERE state='active' AND region LIKE ?"
           " AND (updated_at < ? OR ?)", (PREFIX + "%", cutoff, 1 if everything else 0))
    # 판은 끝났는데 기록이 '진행 중' 인 것 (시간이 지났거나 관장 쪽에서 접힌 것) -> 진 것
    for a in db.q("SELECT a.* FROM guild_war_attack a JOIN gym_battle b ON b.id = a.battle_id"
                  " WHERE a.result='pending' AND b.state='done'"):
        b = db.q1("SELECT result, turn FROM gym_battle WHERE id=?", (a["battle_id"],))
        res = RESULT_OF.get(b["result"], "lose")
        wrote, took = _finish(a, res, b["turn"], now)
        if wrote:
            _reward(a, res, b["result"])
            _watch_end(a, None, None, None, res, took, _wins(a["season"], a["region"], a["atk_guild"]),
                       "길드전: %s 님의 공격이 끝났습니다 (시간이 지나 진 것으로)." % a["atk_name"])


def battle_open(row, now=None):
    """이 길드전 판을 아직 이어서 할 수 있나. 전쟁이 끝났으면 그 판을 진 것으로 접고 False."""
    p = parse(row["region"])
    if p and p[0] == season.SEASON and phase(now)[0] == "war":
        return True
    db.run("UPDATE gym_battle SET state='done', result='expired' WHERE id=? AND state='active'", (row["id"],))
    expire(now)
    return False


# ---------------------------------------------------------------- 구경 (길드원이 공격을 본다)
def fight_id(bid):
    """구경하는 화면이 쓰는 판 번호. 실시간 배틀 번호와 겹치지 않게 'w' 를 붙인다."""
    return "w%d" % int(bid)


def spectate(tb, bid, names, events, rev, war=None):
    """관장 판을 구경하는 사람에게 줄 모습 - 친선전의 것(live.spectate)과 같은 꼴. a = 공격한 사람, b = 막는 쪽.

    지금 나와 있는 포켓몬과 체력, 남은 마릿수, 방금 일어난 일. 기술·도구·아직 안 나온 포켓몬은 싣지 않는다.
    """
    def side(who):
        team, f = (tb.me_team, tb.me) if who == "a" else (tb.foe_team, tb.foe)
        m = tb.side(f, False)
        return {"id": names.get(who + "Id"), "name": names[who], "left": sum(1 for x in team if x.alive()),
                "size": len(team), "mon": dict((k, m.get(k)) for k in live.SPECTATE_MON)}
    seat = {"me": "a", "foe": "b"}
    out = []
    for e in events or []:
        if not isinstance(e, dict):
            continue
        one = dict((k, e[k]) for k in live.SPECTATE_EVENT if k in e)
        for k in ("who", "target"):
            if k in one:
                one[k] = seat.get(one[k], one[k])
        if isinstance(one.get("text"), str):
            one["text"] = live._neutral(e, one.get("who"), names)
        if e.get("t") == "switch" and isinstance(e.get("mon"), dict):
            one["mon"] = dict((k, e["mon"].get(k)) for k in live.SPECTATE_MON)
        out.append(one)
    over = bool(tb.over)
    return {"id": fight_id(bid), "kind": "guildwar", "rev": rev, "turn": tb.turn, "step": rev,
            "a": side("a"), "b": side("b"), "events": out, "over": over,
            "result": {"won": "a", "draw": "draw"}.get(tb.result, "b") if over else None, "war": war or {}}


def _names(a_name, b_name, a_id=None, b_id=None):
    return {"a": a_name, "b": b_name, "aId": a_id, "bId": b_id}


def _watch_open(me, t, trainer, bid, tb, events, wins):
    """공격이 열렸다 - 공격한 길드의 채팅에 관전 카드를 놓고 첫 모습을 민다. 구경이 깨져도 공격은 그대로다."""
    try:
        s = season.SEASON
        gname = (entry(t["guild_id"], s) or {"name": "?"})["name"]
        a = {"id": me["user_id"], "name": me["name"]}
        b = {"id": t["guard_user"] or 0, "name": "[%s] %s" % (gname, trainer["name"])}
        war = {"region": t["region"], "name": t["name"], "guild": gname, "wins": wins, "need": WINS_TO_TAKE}
        fid = fight_id(bid)
        friendly.watch_open(me["guild_id"], fid, a, b, "길드전: %s 님이 [%s] 의 칸을 칩니다 - %s"
                            % (a["name"], gname, t["name"]), war)
        friendly.watch_feed(me["guild_id"], fid, spectate(tb, bid, _names(a["name"], b["name"], a["id"], b["id"]),
                                                          events, 0, war))
    except Exception as err:                                  # noqa: BLE001
        from . import errors
        errors.record("GWAR", "guild_war._watch_open", err)


def spectate_turn(uid, row, tb, events):
    """길드전 판의 한 턴이 돌았다 (gym_routes.act) - 구경하는 길드원에게 민다."""
    try:
        a = db.q1("SELECT * FROM guild_war_attack WHERE battle_id=?", (row["id"],))
        if not a:
            return
        t = tile(a["region"], a["season"])
        gname = (entry(a["def_guild"], a["season"]) or {"name": "?"})["name"]
        names = _names(a["atk_name"], "[%s] %s" % (gname, a["def_name"]), a["atk_user"], a["def_user"])
        war = {"region": a["region"], "name": t["name"] if t else a["region"], "guild": gname,
               "wins": _wins(a["season"], a["region"], a["atk_guild"]), "need": WINS_TO_TAKE}
        friendly.watch_feed(a["atk_guild"], fight_id(row["id"]),
                            spectate(tb, row["id"], names, events, (row["rev"] or 0) + 1, war))
    except Exception as err:                                  # noqa: BLE001
        from . import errors
        errors.record("GWAR", "guild_war.spectate_turn", err)


def _watch_end(a, tb, events, rev, res, took, wins, text):
    """공격이 끝났다 - 마지막 모습을 밀고 카드를 결과로 고친다 (tb 가 없으면 시간이 지나 접힌 것이다)."""
    try:
        fid = fight_id(a["battle_id"])
        result = {"win": "a", "draw": "draw"}.get(res, "b")
        more = {"took": bool(took), "wins": wins, "result": res}
        if tb is not None:
            gname = (entry(a["def_guild"], a["season"]) or {"name": "?"})["name"]
            fight = spectate(tb, a["battle_id"], _names(a["atk_name"], "[%s] %s" % (gname, a["def_name"]),
                                                        a["atk_user"], a["def_user"]), events, rev)
            fight["over"], fight["result"] = True, result
        else:
            fight = {"id": fid, "kind": "guildwar", "over": True, "result": result, "events": []}
        fight["war"] = more
        friendly.watch_feed(a["atk_guild"], fid, fight, result, text, more)
    except Exception as err:                                  # noqa: BLE001
        from . import errors
        errors.record("GWAR", "guild_war._watch_end", err)


# ---------------------------------------------------------------- 점수와 순위
def scores(s=None):
    """순위표. 가진 칸 -> 방어 성공 수 -> 공격 승리 수 -> 먼저 닿은 길드.

    color 는 지도에 칠할 색 번호다 - 신청한 차례라 전쟁 내내 안 바뀐다 (순위가 바뀌어도 색은 그대로).
    """
    s = s or season.SEASON
    rows = dict((e["guild_id"], {"guildId": e["guild_id"], "name": e["name"], "color": i, "score": 0,
                                 "tiles": 0, "taken": 0, "lost": 0, "wins": 0, "defends": 0, "attacks": 0,
                                 "received": 0, "last": ""})
                for i, e in enumerate(in_war(s)))
    for gid, n in tile_counts(s).items():
        if gid in rows:
            rows[gid]["tiles"] = n
    for a in db.q("SELECT atk_guild, def_guild, result, took, ended_at FROM guild_war_attack"
                  " WHERE season=? AND result<>'pending' ORDER BY id", (s,)):
        atk, dfn = rows.get(a["atk_guild"]), rows.get(a["def_guild"])
        if atk:
            atk["attacks"] += 1
        if dfn:
            dfn["received"] += 1
        if a["result"] == "win":
            if atk:
                atk["wins"] += 1
                atk["taken"] += a["took"]
                atk["last"] = a["ended_at"] or ""
            if dfn:
                dfn["lost"] += a["took"]
        elif dfn:
            dfn["defends"] += 1
            dfn["last"] = max(dfn["last"], a["ended_at"] or "")
    for r in rows.values():
        r["score"] = r["tiles"]
    out = sorted(rows.values(), key=lambda r: (-r["tiles"], -r["defends"], -r["wins"], r["last"] or "~",
                                               r["guildId"]))
    for i, r in enumerate(out, 1):
        r["rank"] = i
        r.pop("last", None)
    return out


def coins_for(rank):
    return REWARD_COINS.get(rank, REWARD_OTHER)


def settle(now=None):
    """전쟁이 끝났으면 순위대로 보상한다. 한 번만 돈다.

    받는 사람: 그 길드에서 **한 번이라도 공격한** 길드원. 길드 코인은 바로 들어가고, 1위 길드에는
    칭호가 선물함으로 간다. 참가 길드가 둘이 안 되면 싸움이 없었으니 아무것도 안 준다.
    끝날 때 진행 중이던 판은 진 것으로 접고 나서 센다.
    """
    _lock(now)
    s = season.SEASON
    if phase(now)[0] != "done" or _meta("gw:%d:settled" % s):
        return False
    expire(now, everything=True)
    table = scores(s)
    if len(table) < 2:
        _mark("gw:%d:settled" % s, _iso(now))
        return True
    msg_of = {}
    for r in table:
        gid, rank, n = r["guildId"], r["rank"], coins_for(r["rank"])
        db.run("UPDATE guild_war_entry SET rank=?, score=? WHERE season=? AND guild_id=?",
               (rank, r["score"], s, gid))
        active = [x["atk_user"] for x in db.q(
            "SELECT DISTINCT atk_user FROM guild_war_attack WHERE season=? AND atk_guild=?", (s, gid))]
        for uid in active:
            # **사람마다 표시를 먼저 적는다.** 도중에 끊겨 다시 돌아도, 두 요청이 같이 돌아도
            # 한 사람은 한 번만 받는다 (전체 표시는 다 준 뒤 맨 끝에 적는다).
            if not _mark("gw:%d:paid:%d" % (s, uid), _iso(now)):
                continue
            guild._coin_add(uid, n)
            if rank == 1:
                msg = ("시즌 %d 길드전에서 [%s] 길드가 우승했습니다! 칭호 '%s' 을(를) 드립니다. "
                       "칭호는 랭킹 탭에서 바꿀 수 있습니다." % (s, r["name"], season.TITLES[TITLE]))
                db.run("INSERT INTO gift (user_id, kind, item_id, count, title, message, created_at)"
                       " VALUES (?,?,?,?,?,?,?)", (uid, "title", TITLE, 1, GIFT_TITLE % s, msg, _iso(now)))
        msg_of[gid] = ("길드전이 끝났습니다. [%s] %d위 (%d칸). 한 번이라도 공격한 길드원에게 길드 코인 %d개%s"
                       % (r["name"], rank, r["tiles"], n,
                          "와 칭호 '%s' 을(를) 드렸습니다." % season.TITLES[TITLE] if rank == 1
                          else "를 드렸습니다."))
    for gid, text in msg_of.items():
        if db.q1("SELECT 1 FROM guild WHERE id=?", (gid,)) and _mark("gw:%d:said:%d" % (s, gid), _iso(now)):
            guild._say(gid, text, now)
            guild._changed(gid)
    _mark("gw:%d:settled" % s, _iso(now))
    return True


# ---------------------------------------------------------------- 보여주기
def _left_sec(until, now):
    return max(0, int((until - (now or _now())).total_seconds())) if until else None


def _hide(team, mine):
    """남의 방어팀은 앞 SHOWN 마리만 (포켓몬 번호도 뺀다). (보여 줄 것, 가려진 수)"""
    shown = team if mine else team[:SHOWN]
    mons = preview(shown)
    if not mine:
        for m in mons:
            m.pop("id", None)
    return mons, len(team) - len(shown)


def tile_view(uid, region, now=None):
    """칸 하나: 주인, 지키는 사람, 방어팀 미리보기, 우리 길드의 승수, 내가 칠 수 있는지.

    **남의 칸이면 방어팀의 앞 SHOWN 마리만 싣는다.** 가려진 포켓몬의 종·레벨은 이 응답 어디에도 없다.
    길드장에게는 우리 칸의 지키는 사람을 바꿀 수 있는지와 길드원 목록을 더 준다.
    """
    _lock(now)
    expire(now)
    s = season.SEASON
    t = tile(region, s)
    if not t:
        raise HTTPException(404, "그런 칸이 없습니다.")
    my = _my_gid(uid, s)
    mine = t["guild_id"] == my
    # 판에 나가는 것과 같게 - 규칙(같은 종 한 마리, 10/22) 전에 고정된 팀도 거른다 (_ready 와 같다)
    jokers = _joker_ids(s)
    veil = _joker_hidden(t, my, s, jokers)
    if veil:
        # 조커: 이름도 포켓몬도 싣지 않는다 (마릿수만). 화면에서만 가리면 요청을 들여다봐서 알 수 있다.
        mons, hidden = [], len(pvp.restrict(_guard_team(t, s))[0])
    else:
        mons, hidden = _hide(pvp.restrict(_guard_team(t, s))[0], mine)
    e = entry(t["guild_id"], s)
    home = entry(t["home_guild"], s) if t["home_guild"] != t["guild_id"] else None
    adj = neighbors(s)
    why = _why(uid, t, s, adj, now)
    out = {"region": t["region"], "name": t["name"], "codes": json.loads(t["codes"] or "[]"),
           "guildId": t["guild_id"], "guild": e["name"] if e else "?", "mine": mine,
           "ai": t["guard_user"] == AI_GUARD, "guardId": None if veil else (t["guard_user"] or None),
           "guard": "???" if veil else _guard_name(t, s),
           "team": mons, "size": len(mons) + hidden, "hidden": hidden,
           "taken": bool(t["taken_at"]), "home": home["name"] if home else None,
           "wins": _wins(s, t["region"], my) if my and not mine else 0, "need": WINS_TO_TAKE,
           "guildReceived": _received(s, t["guild_id"]), "guildMax": TOTAL_ATTACKS,
           "can": why is None, "blocked": why}
    if v5():
        out["joker"] = _joker_tile(t, jokers)
        out["jokerHidden"] = veil
    if mine:
        # 우리 칸: 누가 몇 승까지 쌓았나 (지키는 쪽이 알아야 한다)
        out["threats"] = [{"guild": (entry(r["atk_guild"], s) or {"name": "?"})["name"], "wins": r["c"]}
                          for r in db.q("SELECT atk_guild, COUNT(*) c FROM guild_war_attack WHERE season=?"
                                        " AND region=? AND result='win' GROUP BY atk_guild ORDER BY c DESC",
                                        (s, t["region"]))]
        m = guild.member(uid)
        manager = bool(m and m["role"] in ("master", "sub") and phase(now)[0] == "plan")
        out["locked"] = _attacked(s, t["region"]) or bool(t["taken_at"])
        out["manager"] = manager
        if v5():
            out["jokerCount"] = joker_count(t["guild_id"], s)
            out["jokerMax"] = JOKER_MAX
        if manager:
            where = dict((r["guard_user"], r["name"]) for r in db.q(
                "SELECT guard_user, name FROM guild_war_tile WHERE season=? AND guild_id=? AND taken_at IS NULL",
                (s, t["guild_id"])))
            out["members"] = [{"userId": r["user_id"], "name": r["name"], "tile": where.get(r["user_id"])}
                              for r in fighters(t["guild_id"], s)]
    return out


def map_view(uid, now=None, have=None):
    """지도에 칠할 것: 칸마다 시·군·구와 주인, 길드마다 색과 칸 수, 내가 지금 칠 수 있는 칸.

    cells 의 값: {"codes": [...], "g": 주인, "name": 이름, "me": 내가 지키면 1, "ai": AI 수비대면 1,
    "taken": 넘어간 칸이면 1, "wins": 우리 길드가 쌓은 승수(있으면)}. 방어팀은 싣지 않는다 (누르면 tile_view).
    """
    now = now or _now()
    _lock(now)
    expire(now)
    s = season.SEASON
    ph = phase(now)[0]
    table = scores(s) if ph in ("plan", "war", "done") else []
    my = _my_gid(uid, s)
    adj = neighbors(s)
    prog = dict((r["region"], r["c"]) for r in db.q(
        "SELECT region, COUNT(*) c FROM guild_war_attack WHERE season=? AND atk_guild=? AND result='win'"
        " GROUP BY region", (s, my or -1)))
    cells, hit, memo = {}, [], {}
    jokers = _joker_ids(s)
    for t in tiles(s):
        x = {"codes": [t["region"]], "g": t["guild_id"], "name": t["name"]}     # 지도 그림(geo)의 칸 이름
        if t["guard_user"] == uid:
            x["me"] = 1
        if jokers and _joker_tile(t, jokers):
            x["joker"] = 1                    # 누가 숨었는지는 안 싣는다 (칸을 누르면 tile_view 가 가린다)
        if t["guard_user"] == AI_GUARD:
            x["ai"] = 1
        if t["taken_at"]:
            x["taken"] = 1
        if prog.get(t["region"]) and t["guild_id"] != my:
            x["wins"] = prog[t["region"]]
        cells[t["region"]] = x
        if ph == "war" and t["guild_id"] != my and _why(uid, t, s, adj, now, memo) is None:
            hit.append(t["region"])
    rows = tiles(s)
    names = dict((e["guild_id"], e["name"]) for e in entries(s))
    geo = ring_geo(rows, names)
    digest = hashlib.sha1(json.dumps(geo, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16] \
        if geo else None
    return {"season": s, "phase": ph, "mapDigest": digest, "per": TILES_PER_GUILD,
            "geo": geo if (geo and have != digest) else None,
            "need": WINS_TO_TAKE, "myGuild": my,
            "guilds": [{"guildId": r["guildId"], "name": r["name"], "color": r["color"], "tiles": r["tiles"],
                        "defends": r["defends"], "wins": r["wins"], "score": r["score"], "rank": r["rank"]}
                       for r in table],
            "cells": cells, "adj": dict((k, sorted(v)) for k, v in adj.items()), "hit": hit}


def state(uid, now=None):
    """길드전 화면에 그릴 것 전부 (지도는 map_view 가 따로 준다)."""
    now = now or _now()
    _lock(now)
    expire(now)
    settle(now)
    s = season.SEASON
    ph, until = phase(now)
    m = guild.member(uid)
    out = {"season": s, "phase": ph, "phaseKr": PHASE_KR[ph], "endsIn": _left_sec(until, now),
           "applyDays": APPLY_DAYS, "planDays": PLAN_DAYS, "warDays": WAR_DAYS, "minMembers": MIN_MEMBERS,
           "total": TOTAL_ATTACKS, "tilesPer": TILES_PER_GUILD, "need": WINS_TO_TAKE,
           "shown": SHOWN,
           "rewards": [{"rank": k, "coins": v} for k, v in sorted(REWARD_COINS.items())]
                      + [{"rank": None, "coins": REWARD_OTHER}],
           "title": season.TITLES[TITLE], "levelCap": season.LEVEL_CAP,
           "guild": None, "entered": False, "can": {"apply": False, "team": False, "attack": False},
           "entries": [{"guildId": e["guild_id"], "name": e["name"],
                        "state": "out" if e["locked"] == -1 else ("in" if e["locked"] == 1 else "applied")}
                       for e in entries(s)],
           "ranking": scores(s) if ph in ("plan", "war", "done") else []}
    if v5():
        out["jokerMax"] = JOKER_MAX           # 길드가 없어도 규칙 칸에 적는다
    if not m:
        return out
    gid = m["guild_id"]
    e = entry(gid, s)
    members = guild._count(gid)
    manager = m["role"] in ("master", "sub")
    out["guild"] = {"id": gid, "members": members, "role": m["role"]}
    out["entered"] = bool(e) and e["locked"] != -1
    out["dropped"] = bool(e) and e["locked"] == -1
    out["can"]["apply"] = bool(ph == "apply" and manager)
    out["can"]["team"] = ph in ("apply", "plan")
    t = _row(uid, s)
    teams = {}
    for kind in KINDS:
        if t and t["locked"] == 1:
            # 전략 기간에는 고정된 팀을 그대로 보여 주되 고칠 수 있다 (set_team 이 고정된 것도 고친다)
            teams[kind] = {"fixed": ph != "plan", "set": True,
                           "mons": preview(pvp.restrict(json.loads(t["%s_team" % kind]))[0])}
        else:
            ids = _ids(t["%s_ids" % kind]) if t else []
            mons = _mons(uid, ids) if ids else []
            teams[kind] = {"fixed": False, "set": bool(mons),
                           "mons": preview(mons if mons else pvp.restrict(_default_team(uid))[0])}
    out["teams"] = teams
    if v5():
        out["contrib"] = {"win": CONTRIB_WIN, "joker": CONTRIB_JOKER, "defend": CONTRIB_DEFEND, "max": CONTRIB_MAX,
                          "earned": int(t["earned"] or 0) if t else 0}
    me = _me_in_war(uid) if ph in ("plan", "war") else None
    if t and t["locked"] == 1:
        out["attacks"] = {"total": t["attacks"], "used": t["used"],
                          "left": max(0, t["attacks"] - t["used"]) if me else 0}
    out["can"]["attack"] = bool(me and ph == "war" and me["used"] < me["attacks"])
    out["can"]["manage"] = bool(me and manager and ph == "plan")
    b = _active_battle(uid)
    if b and is_war(b["region"]):
        out["battle"] = {"id": b["id"], "region": (parse(b["region"]) or (None, None))[1]}
    if ph in ("plan", "war", "done") and e and e["locked"] == 1:
        rows = fighters(gid, s)
        where = dict((r["guard_user"], r["name"]) for r in db.q(
            "SELECT guard_user, name FROM guild_war_tile WHERE season=? AND guild_id=? AND taken_at IS NULL", (s, gid)))
        out["mates"] = [{"userId": r["user_id"], "name": r["name"], "attacks": r["attacks"], "used": r["used"],
                         "tile": where.get(r["user_id"])} for r in rows]
        if v5():
            for x, r in zip(out["mates"], rows):
                x["joker"] = bool(r["joker"])
        out["received"] = _received(s, gid)
    return out


# 옛 화면(1.13.1 까지)은 길드 정보의 war.phase 가 apply·war·done 일 때만 '길드전' 칸을 냈다 - 'plan' 을 빠뜨려서
# 전략 기간(시즌 4: 2026-10-20 0시 ~ 10-24 0시) 내내 길드장까지 모두에게 칸이 사라졌다. 업데이트하지 않은 사람도
# 칸이 보이게, 전략 기간에는 phase 를 옛 화면이 아는 'apply' 로 보낸다. 칸 안은 /api/guild/war (state) 의 진짜
# 단계로 그리므로(옛 화면도 'plan' 화면을 그릴 줄 안다) 칸만 뜨면 된다. 진짜 단계는 real 에 싣는다.
TAB_PHASE = {"plan": "apply"}


def brief(uid, now=None):
    """길드 탭의 점이 볼 것: 지금 내가 할 일이 있나. 화면은 phase 를 보고 '길드전' 칸을 낸다 (위 TAB_PHASE)."""
    out = _brief(uid, now)
    out["real"] = out["phase"]
    out["phase"] = TAB_PHASE.get(out["phase"], out["phase"])
    return out


def _brief(uid, now=None):
    try:
        ph = phase(now)[0]
        m = guild.member(uid)
        if not m or ph not in ("apply", "war"):
            return {"phase": ph, "todo": False}
        if ph == "war":
            me = _me_in_war(uid)
            return {"phase": ph, "todo": bool(me and me["used"] < me["attacks"])}
        return {"phase": ph, "todo": False}
    except Exception:                                        # noqa: BLE001
        return {"phase": "before", "todo": False}


def log(uid, limit=40):
    """내 길드가 낀 판들, 최근 것부터."""
    m = guild.member(uid)
    t = _row(uid)
    gid = m["guild_id"] if m else (t["guild_id"] if t else None)
    if gid is None:
        return []
    s = season.SEASON
    names = dict((e["guild_id"], e["name"]) for e in entries(s))
    where = dict((r["region"], r["name"]) for r in tiles(s))
    out = []
    for a in db.q("SELECT * FROM guild_war_attack WHERE season=? AND (atk_guild=? OR def_guild=?)"
                  " ORDER BY id DESC LIMIT ?", (s, gid, gid, int(limit))):
        ours = a["atk_guild"] == gid
        win = a["result"] == "win"
        out.append({"id": a["id"], "ours": ours, "atkName": a["atk_name"], "defName": a["def_name"],
                    "atkGuild": names.get(a["atk_guild"]), "defGuild": names.get(a["def_guild"]),
                    "region": a["region"], "regionName": where.get(a["region"], a["region"]),
                    "result": a["result"], "took": bool(a["took"]),
                    "good": None if a["result"] == "pending" else (win if ours else not win),
                    "at": a["created_at"]})
    return out
