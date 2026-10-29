# -*- coding: utf-8 -*-
"""유저끼리 붙는 한 판.

진행이 AI 자동이라 **양쪽 팀과 시드 하나면 결과가 정해진다.** 그래서
매칭이 성사되는 순간 여기서 끝까지 계산해 로그로 저장한다. 양쪽
클라이언트는 그 같은 로그를 재생하기만 한다.

이 방식이 없애 주는 것들:
  - 턴마다 서버를 왕복하지 않는다 (한 판에 쿼리 수백 개가 열 개쯤으로).
  - 두 화면을 맞출 필요가 없다. 각자 자기 속도로 본다.
  - 재생 도중 앱이 꺼져도 승패와 보상은 이미 확정되어 있다.
  - 클라이언트가 보낼 수 있는 전투 입력 라우트가 **아예 없다.** 속일
    대상이 없으므로 서버 권위가 구조적으로 보장된다.

로그는 항상 **a 쪽 시점**으로 저장한다(me = a). b 쪽 화면에서는
클라이언트가 재생 직전에 한 번 뒤집는다.
"""
import base64
import datetime
import gzip
import json
import random

from common import party_battle as PB
from common.version import VERSION

from . import config, db, deps, items, season

# ---- 상금 ----
# 경험치는 주지 않는다(사용자가 정했다). 돈만 준다.
#
# **이긴 판만 준다. 그리고 내가 건 판만 준다.**
# 예전에는 진 쪽도 300원을 받았고, 걸려온 쪽도 자는 사이에 돈이 들어왔다.
# 그러면 아무것도 안 하고 누워 있는 편이 이득인 구간이 생긴다 - 걸어야
# 벌리는 쪽이 맞다.
REWARD = {"win": 500, "draw": 0, "lose": 0}

# 친구 배틀은 절반. 지목해서 붙는 구조라 부계정끼리 서로 져 주면
# 돈이 무한히 나온다. 아래 하루 상한과 같이 쓴다.
FRIEND_RATE = 0.5

# 하루 20판(DAILY_BATTLES)을 넘긴 랜덤 배틀 = **연습판**의 상금 (사용자 결정: 점수판 500원의 1/5).
# 점수는 하나도 안 움직이고 돈만 조금 준다. 아래 하루 상한(DAILY_CAP)은 점수판과 **같이** 센다 -
# 연습판을 몇 판 더 친다고 하루 벌이가 6000원을 넘지 않는다.
PRACTICE_REWARD = {"win": 100, "draw": 0, "lose": 0}

# 하루에 배틀로 받을 수 있는 돈의 상한.
# 도구를 되팔면 한 번에 838원쯤 되고 몬스터볼이 200원이다. 6000원이면
# 하루치 벌이로 넉넉하되, 계속 돌린다고 끝없이 불어나지는 않는다.
DAILY_CAP = 6000

# ---- 점수 ----
# 시즌 번호와 티어·RP 규칙은 season.py 가 들고 있다. 올릴 때는 migrations 에
# 전환 한 벌을 같이 넣어야 한다 (숫자만 올리면 지난 시즌 점수가 그대로 남는다).
SEASON = season.SEASON

# 숨은 점수(MMR)의 Elo. 32면 한 판에 최대 32점이 움직인다. 시즌 2 부터 이
# 숫자는 화면에 안 나오고, RP 가 얼마나 움직일지를 정하는 데만 쓴다.
K = 32
BASE_RATING = 1000
# 이만큼 치러야 랭킹에 오른다. 한두 판 이기고 승률 100% 로 1등이 되는 걸 막는다.
PLACEMENT = 5

# ---- 도전 규칙 ----
# 상대는 접속해 있지 않아도 된다. 그 사람의 지금 파티를 가져와 붙인다.
# 그래서 자는 사람을 몇 번이고 때릴 수 있는데, 점수는 서로 주고받는
# 것이라 아침에 점수가 바닥나 있게 된다. 두 가지로 막는다.
PAIR_COOLDOWN_MIN = 30      # 같은 사람에게 다시 걸기까지
# 하루에 내가 걸 수 있는 **랜덤 배틀** 수.
#
# **친구 배틀은 안 센다.** 친구에게 한 판 걸었다고 랭크 한 판이 줄면, 친구와
# 놀려면 랭크를 포기해야 한다. 같은 상대에게는 30분에 한 번만 걸 수 있어서
# (PAIR_COOLDOWN_MIN) 둘이서 계속 붙어 점수를 몰아주는 것은 그대로 막힌다.
#
# **20판을 넘기면 막지 않고 연습판으로 친다** (사용자 결정). 하루 상한을 둔 까닭은 자는 사람의
# 점수를 몇 번이고 깎는 것이었는데, 연습판은 양쪽 다 점수(RP·숨은 점수·연승·배치·판수·하루 첫 승)가
# 하나도 안 움직이므로 그 걱정이 없다. 쿨타임(같은 상대 30분 · 랜덤 쿨타임)과 상대 고르기는 그대로다.
DAILY_BATTLES = 20

# 랜덤 배틀에서 상대를 고를 때만 쓰는 값들.
#
# **팀 전력이 비슷한 사람과 붙인다.** 시즌 1 은 파티 평균 레벨로 붙였다.
# 그런데 거는 쪽이 66.7% 를 이겼다 - 엔진은 공평했다(자리만 바꿔 2,140판:
# 50.6%). 평균 레벨은 마릿수와 종족을 안 봐서, Lv.30 세 마리가 Lv.30 여섯
# 마리와 같은 상대로 잡혔다. 판 시작 때의 두 팀으로 재어 보니 거는 쪽 전력이
# 25% 넘게 센 판이 33% 였고 그런 판은 96% 를 이겼다. 전력이 비슷하면(0.95~1.05)
# 52% 로 반반이었다.
#
# 전력 = 포켓몬마다 (종족값 합 x 레벨) 을 더한 것. 레벨은 랭크 상한(50)으로
# 자른 값이다. 가까운 띠부터 보고, 그 안에서 가장 가까운 몇 명 중에 고른다.
POWER_BANDS = (0.10, 0.25)
PICK_CLOSEST = 3
# **시즌 4 부터는 점수(RP)가 가까운 사람을 먼저 본다** (사용자 결정). 시즌 3 기록을 재어 보니
# 전력이 비슷한 판(0.95~1.05)에서도 거는 쪽이 62.8% 를 이겼고, 상대가 한 판도 안 건 사람이면
# 81%, 백 판 넘게 뛰는 사람이면 54.5% 였다 - 전력(종족값 x 레벨)은 얼마나 키웠는지를 못 본다.
# RP 는 그 사람이 이번 시즌에 실제로 이겨 온 만큼이라, 가까운 사람끼리 붙이면 그 차이가 걸러진다.
#
# RP 차이가 이 안인 사람부터 찾고, 없으면 다음 띠로 넓힌다. 맨 끝의 None 은 '전체' 다 -
# 전력 띠(POWER_BANDS)는 이제 사람을 떨어뜨리지 않고, 띠 안에서 누구를 먼저 고를지만 정한다
# (전력 차가 작은 몇 명 중 하나). 전력 차는 여전히 RP 가 움직이는 폭에 들어간다 (season.expected).
RP_BANDS = (50, 100, 200, None)
# 전력이 같으면 숨은 점수도 가까운 사람을. 400점 차이를 전력 30% 차이로 친다.
#
# **0.10 이었을 때 숨은 점수가 사실상 무시됐다.** 전력은 종족값 x 레벨만 보는데
# 랭크는 전원 Lv.50 이라 사실상 종족값 합계다 - 노력치를 꽉 채운 팀과 0 인 팀이
# 같은 전력으로 잡힌다. 그 상태에서 493점 차이가 전력 12% 로만 쳐지니 10% 띠
# 안에서 순위만 조금 밀릴 뿐 걸러지지 않았다. 1493 짜리가 1000(한 판도 안 뛴
# 기본값) 짜리를 사흘 동안 60번 만나 6턴에 전멸시킨 판이 그렇게 나왔다.
MMR_WEIGHT = 0.30 / 400.0
# **띠 안에서도 RP 가 가장 가까운 사람부터** (2026-10-17 사용자 제보: "4점·10점 차이 나는 사람도 있는데 거의
# 50점 차이 나는 사람과 붙는다"). 전에는 띠(±50) 안에서 RP 를 안 보고 전력·숨은 점수만 봤고, 하루 안에 만난
# 사람은 통째로 뒤로 뺐다 - 그래서 오늘 만난 가까운 사람을 두고 띠 끝의 처음 보는 사람이 골라졌다.
# 이제 RP 차이가 가장 작은 사람부터 본다. 하루 안에 만난 사람은 RP 가 MET_PENALTY 만큼 더 먼 것으로 치고
# (같은 얼굴만 계속 나오지 않게 - 3시간 안에 붙은 사람은 RANDOM_REPEAT_MIN 으로 아예 안 고른다),
# RP 가 거의 같은 사람들(가장 가까운 사람에서 RP_TIE 안) 가운데서만 전력·숨은 점수가 가까운 몇 명 중 하나다.
RP_TIE = 10
MET_PENALTY = 30

# 랜덤 배틀 상대를 고를 때는 최근에 붙은 사람을 이만큼 건너뛴다.
# 직접 지목하는 쪽(PAIR_COOLDOWN_MIN)보다 길게 본다 - 후보가 서른 명
# 넘게 있는데도 이레 동안 같은 사람과 열아홉 번 붙은 짝이 있었다.
RANDOM_REPEAT_MIN = 180
# 이 안에 만난 적이 없는 사람을 먼저 고른다.
FRESH_WINDOW_MIN = 60 * 24

# 다 본 대전 로그를 며칠이나 들고 있을지. 로그는 보고 나면 값이 없어지는
# 자료인데 한 판에 수십 KB 라 Turso 용량을 제일 먼저 먹는다.
KEEP_DAYS = 14
# 연습판(하루 20판 뒤) 로그는 봤든 안 봤든 이만큼 지나면 치운다. 점수가 안 걸린 판이라 다시 볼 값이 적은데,
# 20판 뒤로는 상한 없이 쌓이므로 점수판처럼 14일(그것도 양쪽이 다 본 것만) 들고 있으면 용량을 먹는다.
# 전적(battle_record) 줄은 남는다 - 화면은 canReplay 로 '다시 보기' 만 끈다.
PRACTICE_KEEP_DAYS = 2


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(t=None):
    return (t or _now()).isoformat()


# 하루는 **한국 시각 자정**에 바뀐다 (1.8.0). 예전에는 UTC 날짜를 써서 하루
# 20판·하루 상금·오늘 첫 승이 한국 시각 오전 9시에 풀렸다. 쓰는 사람이 모두
# 한국에 있는데 '하루' 가 아침 9시에 바뀌는 것은 아무도 예상하지 못한다 -
# 시즌 3 을 자정에 열었더니 0~9시가 '어제 몫' 으로 세어져서, 그때 스무 판을
# 치고 9시에 스무 판을 또 칠 수 있었다.
KST = datetime.timezone(datetime.timedelta(hours=9))


def _today():
    return _now().astimezone(KST).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- 로그
def pack(events):
    """이벤트 목록을 한 덩어리 문자열로. 그대로 넣으면 너무 크다."""
    raw = json.dumps(events, ensure_ascii=False, separators=(",", ":"))
    return base64.b64encode(gzip.compress(raw.encode("utf-8"), 6)).decode("ascii")


def unpack(blob):
    return json.loads(gzip.decompress(base64.b64decode(blob)).decode("utf-8"))


# ---------------------------------------------------------------- 점수
def _expected(mine, theirs, power_ratio=1.0):
    """숨은 점수와 전력비로 본 기대 승률. RP 와 같은 식을 쓴다 (season.expected)."""
    return season.expected(mine, theirs, power_ratio)


def _rating_row(uid):
    r = db.q1("SELECT * FROM rank_stat WHERE user_id=?", (uid,))
    if r:
        return r
    db.run("INSERT INTO rank_stat (user_id, updated_at) VALUES (?,?)"
           " ON CONFLICT(user_id) DO NOTHING", (uid, _iso()))
    return db.q1("SELECT * FROM rank_stat WHERE user_id=?", (uid,))


def _score(result):
    return {"win": 1.0, "draw": 0.5, "lose": 0.0}[result]


# ---------------------------------------------------------------- 상금
def _reward_for(uid, row, kind, result, practice=False):
    """이 판으로 받을 돈. 하루 상한에 걸리면 깎아서 준다.

    상한을 쓰는 이유는 친구끼리 서로 져 주며 돈을 찍어내는 걸 막기
    위해서다. 어느 방식으로 벌든 하루 총액이 같은 문에 걸리므로,
    나중에 배틀 종류가 늘어도 여기만 보면 된다. 연습판도 같은 문이다.
    """
    want = (PRACTICE_REWARD if practice else REWARD)[result]
    if kind == "friend":
        want = int(want * FRIEND_RATE)
    today = _today()
    used = row["earned"] if row["earned_day"] == today else 0
    left = max(0, DAILY_CAP - used)
    return min(want, left), today, used


# ---------------------------------------------------------------- 한 판
def _party(uid):
    """바탕화면에 데리고 있는 포켓몬. 친구 배틀은 이 파티로 싸운다."""
    rows = db.q("SELECT * FROM pokemon WHERE user_id=? AND on_desktop=1"
                " ORDER BY slot, id LIMIT ?", (uid, config.MAX_PARTY))
    return [db.row_to_mon(r) for r in rows]


# ---- 전설·환상 제한 ----
# 팀에는 전설·환상을 한 마리까지만. 본가 랭크 배틀의 '금지급 한 마리' 와 같은
# 생각이다. 시즌마다 1~5위가 알을 받으므로 그대로 두면 같은 사람에게 전설이
# 쌓인다. 한 마리일 때는 시뮬레이션으로 재어 보니 매칭이 상쇄해서 승률이 거의
# 안 오른다 (가장 센 종도 +5%p, 야생 한카리아스와 비슷).
#
# 시즌 2 까지는 랭크(랜덤·실시간)에만 걸었다. **시즌 3 부터 친구 배틀·관장·레이드
# 까지 모든 팀 배틀에 건다** (사용자 결정). 바탕화면 야생 배틀은 팀 대 팀이
# 아니라서 그대로 둔다.
#
# 등록한 랭크 팀은 두 마리째를 넣을 수 없다 (set_team). 바탕화면 파티로 싸우는
# 곳은 **앞에 있는 한 마리만 나가고 나머지는 쉰다** (restrict / split_restricted).
RESTRICTED_MAX = 1
# 같은 종은 한 팀에 한 마리 (10/22 사용자: "타부자고 두 마리 같은 중복 파티는 안 된다"). 전설·환상 제한과 같은 틀 -
# 등록하는 팀(랭크·길드전)은 거절하고, 바탕화면 파티로 싸우는 곳은 앞의 한 마리만 나가고 나머지는 쉰다.
SAME_SPECIES_MAX = 1


def restricted_species():
    """전설·환상 종 (내부 이름). 알의 목록과 같은 본가 분류다.

    알에서는 빼는 이벤트 종도 여기에는 들어간다 - 야생에서 잡은 것도 환상이다.
    """
    global _RESTRICTED
    if _RESTRICTED is None:
        from . import eggs
        dex = deps.dex()
        names = set()
        for n in tuple(eggs.LEGENDARY_POOL) + tuple(eggs.MYTHICAL_POOL):
            sp = dex.get(n)
            if sp:
                names.add(sp["internal"])
        _RESTRICTED = names
    return _RESTRICTED


_RESTRICTED = None


def split_restricted(mons):
    """실제로 나가는 팀과 쉬는 포켓몬. (팀, 쉬는 것 목록).

    같은 종은 앞의 한 마리만, 전설·환상은 앞에서부터 RESTRICTED_MAX 마리만 남긴다. 순서는 그대로다.
    """
    names = restricted_species()
    out, seen, benched, kinds = [], 0, [], {}
    for m in mons:
        sp = m.get("species")
        if kinds.get(sp, 0) >= SAME_SPECIES_MAX:
            benched.append(m)
            continue
        if sp in names:
            if seen >= RESTRICTED_MAX:
                benched.append(m)
                continue
            seen += 1
        kinds[sp] = kinds.get(sp, 0) + 1
        out.append(m)
    return out, benched


def too_many_same(species):
    """종 목록에 같은 종이 SAME_SPECIES_MAX 마리보다 많은가 (등록하는 팀을 거절할 때)."""
    count = {}
    for sp in species:
        count[sp] = count.get(sp, 0) + 1
    return any(n > SAME_SPECIES_MAX for n in count.values())


# ---- 같은 지닌 도구 (시즌 5, season.rules_v5) ----
# 랭크 팀 안에서 같은 도구는 한 마리만 (10/29 사용자: 기합의띠를 여러 마리에게 들려 보내는 것 막기).
# 메가스톤·Z크리스탈도 도구라 같은 것 둘이면 걸린다. 안 지닌 것(None)은 상관없다.
#
# **랭크(랜덤 배틀)에만 건다.** 친구·실시간·관장·레이드·길드전 방어팀은 그대로다 (사용자가 랭크만 말했다).
# 같은 종처럼 '뒤의 것이 쉰다' 로 하지 않는다 - 도구는 팀을 등록한 뒤에도 가방·박스에서 바꿀 수 있어서
# 쉬게 하면 모르는 사이에 팀이 다섯 마리가 된다. 그래서
#   · 등록할 때 거절한다 (set_team)
#   · 거는 쪽은 겹쳐 있으면 랜덤 배틀을 못 건다 - 무엇을 고칠지 알려 준다 (can_start / held_short)
#   · 걸려온 쪽(상대)은 후보에서 빼지 않는다. 자는 사이에 겹친 것을 고칠 길이 없는데 빼면 그 사람만
#     조용히 매칭에서 사라진다. 대신 **그 판에서만** 겹친 도구 중 뒤의 것을 안 지닌 셈으로 싸운다
#     (strip_same_held - 사본만 고친다, 원본 도구는 그대로)
# 시즌 4 에는 아무것도 바뀌지 않는다 - 모두 season.rules_v5() 를 그때그때 본다.
SAME_HELD_MAX = 1


def held_rule_on():
    """같은 도구 규칙이 켜졌나. import 때 복사하지 않는다 (검사가 season.SEASON 을 바꿔 본다)."""
    return season.rules_v5()


def _held_key(m):
    return ((m or {}).get("held") or "").upper() or None


def same_held(mons):
    """같은 도구를 둘 이상이 지녔으면 [(도구 열쇠, [포켓몬 ...]) ...]. 팀 차례, 도구도 처음 나온 차례.

    시즌을 보지 않고 센다 - 켜졌는지는 부르는 쪽이 held_rule_on 으로 가른다."""
    by, order = {}, []
    for m in mons or []:
        k = _held_key(m)
        if not k:
            continue
        if k not in by:
            by[k] = []
            order.append(k)
        by[k].append(m)
    return [(k, by[k]) for k in order if len(by[k]) > SAME_HELD_MAX]


def _mon_name(m, dex=None):
    dex = dex or deps.dex()
    return (m.get("nickname") or (dex.get(m.get("species")) or {}).get("kr")
            or m.get("species") or "?")


def same_held_text(dupes):
    """겹친 도구를 이름으로: '기합의띠(한카리아스·갸라도스), 생명의구슬(...)'."""
    dex = deps.dex()
    return ", ".join("%s(%s)" % (items.name_of(k), "·".join(_mon_name(m, dex) for m in ms))
                     for k, ms in dupes)


def same_held_ids(mons):
    """겹친 도구를 지닌 것 중 **뒤의 것**의 id (앞의 한 마리는 그대로 지녀도 된다). 화면이 표시한다."""
    out = []
    for _k, ms in same_held(mons):
        out.extend(m.get("id") for m in ms[SAME_HELD_MAX:] if m.get("id") is not None)
    return out


def strip_same_held(mons):
    """그 판에서만: 같은 도구를 지닌 것 중 뒤의 것은 안 지닌 셈으로. 사본을 돌려준다 (원본은 안 바꾼다).

    메가스톤을 내려놓으면 bonded 도 뜻이 없어지지만 남겨 둔다 - 엔진은 도구가 메가스톤일 때만 그것을 본다."""
    seen, out = {}, []
    for m in mons or []:
        k = _held_key(m)
        if k and seen.get(k, 0) >= SAME_HELD_MAX:
            m = dict(m)
            m["held"] = None
        elif k:
            seen[k] = seen.get(k, 0) + 1
        out.append(m)
    return out


def held_short(uid):
    """같은 도구 규칙(시즌 5)에 걸려 랜덤 배틀을 못 걸면 그 까닭 한 줄, 아니면(시즌 4 포함) None."""
    if not held_rule_on():
        return None
    dupes = same_held(ranked_team(uid))
    if not dupes:
        return None
    where = "랭크 팀" if team_ids(uid) else "바탕화면 파티(랭크 팀이 없어 이 파티로 싸웁니다)"
    return ("%s에서 같은 도구를 둘 이상이 지니고 있습니다: %s. 랭크전에서는 같은 도구를 %d마리만 지닐 수 있어요"
            " - 하나만 남기고 도구를 바꾸거나 빼 주세요." % (where, same_held_text(dupes), SAME_HELD_MAX))


def restrict(mons):
    """배틀에 실제로 나가는 팀. (팀, 빠진 마릿수)."""
    out, benched = split_restricted(mons)
    return out, len(benched)


def drop_counts(mons):
    """나가는 팀과 쉬는 수를 까닭별로. (팀, 전설·환상이라 쉬는 수, 같은 종이라 쉬는 수).

    나가는 팀에 같은 종이 있으면 '같은 종' 이다 - 뮤츠 둘이면 두 번째는 같은 종 까닭이다.
    """
    team, benched = split_restricted(mons)
    same = len(_same_of(benched, team))
    return team, len(benched) - same, same


def _same_of(benched, team):
    kinds = set(m.get("species") for m in team or [])
    return [m for m in benched if m.get("species") in kinds]


def battle_party(uid):
    """친구 배틀·관장·레이드가 쓰는 팀 — 바탕화면 파티에 전설·환상 제한을 건 것.
    (팀, 쉬는 것 목록)."""
    return split_restricted(_party(uid))


def bench_note(benched, team=None):
    """쉬는 포켓몬을 알리는 한 줄. 없으면 빈 문자열. 이름은 별명이 있으면 별명.

    team(나가는 팀)을 주면 같은 종이라 쉬는 것과 전설·환상이라 쉬는 것을 나눠 말한다.
    """
    if not benched:
        return ""
    dex = deps.dex()

    def names(ms):
        return "·".join(m.get("nickname") or (dex.get(m.get("species")) or {}).get("kr")
                        or m.get("species") for m in ms)
    same = _same_of(benched, team)
    legend = [m for m in benched if not any(m is s for s in same)]
    out = []
    if same:
        out.append("같은 포켓몬은 한 팀에 %d마리만 데려갈 수 있어서 %s 은(는) 이번에 쉽니다."
                   % (SAME_SPECIES_MAX, names(same)))
    if legend:
        out.append("전설·환상 포켓몬은 한 팀에 %d마리만 데려갈 수 있어서 %s 은(는) 이번에 쉽니다."
                   % (RESTRICTED_MAX, names(legend)))
    return " ".join(out)


def team_ids(uid):
    """등록한 랭크 팀의 포켓몬 id (자리 순). 없으면 빈 목록.

    내 것인지를 한 번 더 본다 - 줄은 포켓몬이 지워질 때 같이 지워지지만,
    주인이 바뀌는 길이 생겨도 남의 포켓몬으로 싸우는 일은 없어야 한다.
    """
    rows = db.q("SELECT t.pokemon_id FROM rank_team t JOIN pokemon p"
                " ON p.id=t.pokemon_id AND p.user_id=t.user_id"
                " WHERE t.user_id=? ORDER BY t.pos", (uid,))
    return [r["pokemon_id"] for r in rows]


def ranked_team(uid):
    """랜덤(랭크) 배틀에서 이 사람이 싸우는 팀.

    랭크 팀을 등록했으면 그 팀, 아니면 바탕화면 파티. 레벨은 **아직 자르지
    않은** 원래 값이다 - 자르는 것은 싸우기 직전(capped)에 한다.
    """
    return restrict(_ranked_source(uid))[0]


def _ranked_source(uid):
    """전설·환상 제한을 걸기 전의 팀 (등록한 팀, 없으면 바탕화면 파티)."""
    ids = team_ids(uid)
    if not ids:
        return _party(uid)
    marks = ",".join("?" * len(ids))
    rows = dict((r["id"], r) for r in db.q(
        "SELECT * FROM pokemon WHERE user_id=? AND id IN (%s)" % marks,
        (uid,) + tuple(ids)))
    return [db.row_to_mon(rows[i]) for i in ids if i in rows]


def set_team(uid, ids):
    """랭크 팀을 등록한다. 빈 목록이면 등록을 푼다(바탕화면 파티로 싸운다)."""
    clean = []
    for i in ids or []:
        i = int(i)
        if i not in clean:
            clean.append(i)
    if len(clean) > config.MAX_PARTY:
        raise ValueError("랭크 팀은 최대 %d마리입니다." % config.MAX_PARTY)
    if clean:
        marks = ",".join("?" * len(clean))
        rows = db.q("SELECT id, species, nickname, held FROM pokemon WHERE user_id=? AND id IN (%s)"
                    % marks, (uid,) + tuple(clean))
        if len(rows) != len(clean):
            raise ValueError("내 포켓몬만 넣을 수 있습니다.")
        from . import expedition                 # 탐험에 나가 있으면 배틀에 못 나간다 (1.10.4)
        if expedition.away_ids(uid) & set(clean):
            raise ValueError("탐험에 나가 있는 포켓몬은 랭크 팀에 넣을 수 없습니다.")
        names = restricted_species()
        if sum(1 for r in rows if r["species"] in names) > RESTRICTED_MAX:
            raise ValueError("랭크 팀에는 전설·환상 포켓몬을 %d마리까지 넣을 수 있습니다."
                             % RESTRICTED_MAX)
        if too_many_same([r["species"] for r in rows]):
            raise ValueError("같은 포켓몬은 한 팀에 %d마리만 넣을 수 있습니다." % SAME_SPECIES_MAX)
        if held_rule_on():
            # 시즌 5: 같은 지닌 도구는 한 마리만. 넣은 차례대로 보고, 누가 겹쳤는지 이름으로 알린다
            pos = dict((pid, n) for n, pid in enumerate(clean))
            dupes = same_held([dict(r) for r in sorted(rows, key=lambda r: pos[r["id"]])])
            if dupes:
                raise ValueError("랭크 팀에서는 같은 도구를 %d마리만 지닐 수 있습니다: %s."
                                 " 하나만 남기고 도구를 바꾸거나 빼 주세요."
                                 % (SAME_HELD_MAX, same_held_text(dupes)))
    db.run("DELETE FROM rank_team WHERE user_id=?", (uid,))
    for pos, pid in enumerate(clean):
        db.run("INSERT INTO rank_team (user_id, pos, pokemon_id) VALUES (?,?,?)",
               (uid, pos, pid))
    return clean


def capped(mons, cap=season.LEVEL_CAP):
    """랭크 배틀용 사본. 상한보다 높은 레벨만 상한으로 내린다.

    원본을 고치지 않는다. 경험치·배운 기술은 그대로라, 높은 레벨에서 배운
    기술을 50 에서도 쓴다 (본가 레이팅 배틀과 같다).
    """
    out = []
    for m in mons:
        m = dict(m)
        if int(m.get("level") or 1) > cap:
            m["level"] = cap
        out.append(m)
    return out


def _name(uid):
    r = db.q1("SELECT username FROM users WHERE id=?", (uid,))
    return r["username"] if r else "?"


def run_match(a_uid, b_uid, kind="random", seed=None, practice=None):
    """두 사람을 붙이고 결과를 남긴다. 부르는 순간 판이 끝난다.

    돌려주는 것: {"matchId", "winner"(user_id 또는 None), "turns", "practice",
                  "a": {...}, "b": {...}}
    양쪽의 dict 에는 result / reward / rating / delta / rp / rpDelta / practice 가 들어 있다.

    랜덤 배틀은 랭크 팀으로, 레벨 상한을 걸고 싸운다. 친구 배틀은 지금까지처럼
    바탕화면 파티를 원래 레벨 그대로 쓴다 - 키운 보람은 거기서 보여 준다.

    practice 를 안 주면 **거는 쪽(a)이 오늘 20판을 다 썼는지**로 정한다 (랜덤 배틀만).
    판은 점수판과 똑같이 싸운다 - 다른 것은 뒤처리(_settle)뿐이다. 응답 모양도 같아서
    (점수 변화가 0 일 뿐) practice 를 모르는 옛 앱 화면도 그대로 돈다.
    """
    if practice is None:
        practice = kind == "random" and is_practice(a_uid)
    practice = bool(practice) and kind == "random"
    dex = deps.dex()
    if kind == "random":
        a_mons, b_mons = capped(ranked_team(a_uid)), capped(ranked_team(b_uid))
        if held_rule_on():
            # 시즌 5: 같은 도구는 한 마리만. 거는 쪽은 can_start 가 이미 막았고, 걸려온 쪽은 후보에서 안 빼는
            # 대신 이 판에서만 뒤의 것을 안 지닌 셈으로 싸운다 (SAME_HELD_MAX 의 설명). 양쪽 다 거는 것은
            # can_start 를 거치지 않고 부르는 곳(검사·운영 손질)에서도 같은 판이 되게 하려고다.
            a_mons, b_mons = strip_same_held(a_mons), strip_same_held(b_mons)
    else:
        # 친구 배틀도 전설·환상은 한 마리 (시즌 3)
        a_mons, b_mons = battle_party(a_uid)[0], battle_party(b_uid)[0]
    if not a_mons or not b_mons:
        raise ValueError("양쪽 다 데리고 다니는 포켓몬이 있어야 합니다.")

    seed = random.randrange(1 << 30) if seed is None else int(seed)
    # 메가진화 (시즌 3): 각자 관장 8곳이면 키스톤. 스톤을 든 애가 나오면 AI 가 쓴다.
    from . import gimmick, mega
    # Z기술 (시즌 4): 조건은 키스톤과 같다. 이것도 AI 가 알아서 쓴다.
    # 시즌 5 (버전 2): 랜덤(랭크) 배틀과 그 연습판은 양쪽 다 길드전 방어 AI 로 싸운다 - 15% 무작위 없이, 라운드 도중
    # 교체도 한다 (common/party_battle.py 맨 위). 친구 배틀은 예전 그대로다 - 점수가 안 걸린 판이라 무거운 셈을
    # 돌릴 까닭이 없고, 친구끼리 해 온 판의 느낌을 바꾸지 않는다. **부를 때마다 season.rules_v5() 를 본다**
    # (시즌 번호를 올리는 순간 켜진다 - import 때 복사해 두면 시즌이 바뀌어도 그대로다).
    war_ai = kind == "random" and season.rules_v5()
    out = PB.simulate(dex, a_mons, b_mons, seed=seed,
                      keystone={"me": mega.has_keystone(a_uid),
                                "foe": mega.has_keystone(b_uid)},
                      zring=gimmick.flags(a_uid, b_uid), war_ai=war_ai)

    # 엔진은 a 시점으로 me/foe 를 말한다. 여기서 사람 쪽으로 옮긴다.
    win = out["winner"]
    res_a = {"me": "win", "foe": "lose", "draw": "draw"}[win]
    res_b = {"win": "lose", "lose": "win", "draw": "draw"}[res_a]
    winner_id = a_uid if res_a == "win" else (b_uid if res_a == "lose" else None)

    a_name, b_name = _name(a_uid), _name(b_uid)
    row_a, row_b = _rating_row(a_uid), _rating_row(b_uid)

    # a 가 건 쪽이다(run_match 를 부르는 자리에서 늘 그렇게 넘긴다).
    # b 는 걸려온 쪽이라 상금이 없다 - 계산도 하지 않는다.
    pay_a, day, used_a = _reward_for(a_uid, row_a, kind, res_a, practice)
    pay_b, used_b = 0, 0

    mid = db.run(
        "INSERT INTO pvp_match (kind, a_id, b_id, a_name, b_name, winner,"
        " turns, seed, engine, log, a_reward, b_reward, created_at, practice)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (kind, a_uid, b_uid, a_name, b_name, winner_id, out["turns"], seed,
         VERSION, pack(out["events"]), pay_a, pay_b, _iso(),
         1 if practice else 0)).lastrowid

    left_a = _left(out["events"], "me", len(a_mons))
    left_b = _left(out["events"], "foe", len(b_mons))
    lead_a = a_mons[0]["species"]
    lead_b = b_mons[0]["species"]
    # 실제로 싸운 두 팀(랭크 팀, 상한 걸린 레벨)의 전력비. 점수 기대치에 들어간다.
    ratio_a = power_ratio(a_mons, b_mons)

    fin_a = _settle(a_uid, row_a, b_uid, b_name, kind, res_a, pay_a, day,
                    used_a, out["turns"], left_a, left_b, lead_a, lead_b,
                    mid, row_b["rating"], power_ratio=ratio_a, practice=practice)
    fin_b = _settle(b_uid, row_b, a_uid, a_name, kind, res_b, pay_b, day,
                    used_b, out["turns"], left_b, left_a, lead_b, lead_a,
                    mid, row_a["rating"], started=False,
                    power_ratio=1.0 / ratio_a, practice=practice)

    return {"matchId": mid, "winner": winner_id, "turns": out["turns"],
            "kind": kind, "seed": seed, "practice": practice, "a": fin_a, "b": fin_b}


def _left(events, side, total):
    """끝났을 때 그쪽에 남은 마릿수. ko 이벤트를 세면 나온다."""
    down = sum(1 for e in events
               if e.get("t") == "ko" and e.get("side") in (side, "both"))
    return max(0, total - down)


def power_ratio(mine, theirs):
    """내 팀 전력 / 상대 팀 전력. 어느 쪽이든 못 재면 1."""
    a, b = team_power(mine), team_power(theirs)
    return (a / b) if (a > 0 and b > 0) else 1.0


def _settle(uid, row, foe_id, foe_name, kind, result, pay, day, used,
            turns, my_left, foe_left, lead, foe_lead, mid, foe_rating,
            started=True, power_ratio=1.0, practice=False):
    """한 사람 몫의 뒤처리 — 돈, 전적, 점수.

    started 는 **내가 걸었는가**다. 걸려온 쪽은 전적에 남기기만 하고
    점수도 승패도 돈도 건드리지 않는다.

    practice 는 **연습판**(하루 20판 뒤의 랜덤 배틀)이다. 건 쪽도 걸려온 쪽처럼
    점수·승패·판수·연승·하루 첫 승을 하나도 안 건드리고, 돈(하루 상한 안)만 받는다.
    전적에는 '연습' 으로 남긴다.

    상대는 접속해 있지 않아도 붙는다(자는 사람의 파티를 가져와 돌린다).
    그래서 걸려온 판까지 점수에 넣으면, 자는 동안 남이 몇 번을 걸었느냐로
    내 점수가 정해진다 - 내가 한 일이 아닌 것으로 등수가 오르내린다.
    전적에는 남겨서 '누가 나에게 걸었고 어떻게 됐는지' 는 볼 수 있게 한다.
    """
    if started and pay > 0:
        items.money_add(uid, pay)
    if not started:
        pay = 0

    # 점수는 **내가 건 랜덤 배틀**만 움직인다. 친구 배틀은 지목해서 붙는
    # 구조라 부계정끼리 승패를 몰아줄 수 있다. 전적에는 남기되 점수는
    # 그대로 둔다.
    rating = row["rating"]
    delta = 0
    rp = row["rp"] or 0
    rp_delta = 0
    peak = row["peak_rp"] or 0
    notes = []
    today = _today()
    first_win = False
    counts = started and kind == "random" and not practice
    if counts:
        # 숨은 점수도 RP 와 **같은 기대치**(숨은 점수 + 전력비)로 움직인다. 숨은
        # 점수만 전력을 모른 채 오르내리면, 전력이 센 사람의 숨은 점수에 전력이
        # 다시 쌓여서 기대치에 전력이 두 번 들어간다.
        exp = _expected(row["rating"], foe_rating, power_ratio)
        delta = int(round(K * (_score(result) - exp)))
        rating = max(0, row["rating"] + delta)
        # RP 는 **이 판 전의** 숨은 점수로 잰다. 방금 오른 점수로 재면 이긴
        # 판의 RP 가 스스로 깎인다.
        first_win = result == "win" and row["win_day"] != today
        rp, rp_delta, notes = season.rp_change(
            result, row["rating"], foe_rating, row["streak"], first_win,
            rp, peak, power_ratio)
        peak = max(peak, rp)

    db.run("INSERT INTO battle_record (user_id, foe_id, foe_name, kind,"
           " result, rating, delta, reward, turns, my_left, foe_left,"
           " lead, foe_lead, match_id, started, ended_at, rp, rp_delta, practice)"
           " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
           (uid, foe_id, foe_name, kind, result, rating, delta, pay, turns,
            my_left, foe_left, lead, foe_lead, mid, 1 if started else 0,
            _iso(), rp, rp_delta, 1 if practice else 0))

    if not started:
        # 걸려온 판은 여기서 끝. 점수·승패·하루 상한 어느 것도 안 건드린다.
        return {"userId": uid, "result": result, "reward": 0,
                "rating": rating, "delta": 0, "rp": rp, "rpDelta": 0,
                "started": False, "practice": practice,
                "myLeft": my_left, "foeLeft": foe_left}

    won = 1 if result == "win" else 0
    lost = 1 if result == "lose" else 0
    drew = 1 if result == "draw" else 0
    if practice:
        # 연습판: 하루 상금만 센다 (점수판과 같은 상한). 판수·승패·연승·RP·하루 첫 승은 그대로,
        # 길드 미션('랜덤 배틀 하기')도 안 센다 - 20판이면 이미 다 찼고, 점수 없는 판은 점수 없는 판이다.
        db.run("UPDATE rank_stat SET earned_day=?, earned=?, updated_at=? WHERE user_id=?",
               (day, used + pay, _iso(), uid))
    elif kind == "random":
        from . import guild                 # 길드 일일 미션 (1.10.0): 내가 건 랜덤 배틀만 센다
        guild.note_safe(uid, "rank")
        games = row["games"] + 1
        streak = (max(1, row["streak"] + 1) if won else
                  min(-1, row["streak"] - 1) if lost else 0)
        db.run(
            "UPDATE rank_stat SET rating=?, games=?, wins=wins+?, losses=losses+?,"
            " draws=draws+?, streak=?, best=?, ranked=?, earned_day=?, earned=?,"
            " rp=?, peak_rp=?, win_day=?, updated_at=? WHERE user_id=?",
            (rating, games, won, lost, drew, streak, max(row["best"], rating),
             1 if games >= PLACEMENT else 0, day, used + pay, rp, peak,
             today if first_win else row["win_day"], _iso(), uid))
    else:
        db.run(
            "UPDATE rank_stat SET fr_wins=fr_wins+?, fr_losses=fr_losses+?,"
            " fr_draws=fr_draws+?, earned_day=?, earned=?, updated_at=?"
            " WHERE user_id=?",
            (won, lost, drew, day, used + pay, _iso(), uid))

    out = {"userId": uid, "result": result, "reward": pay,
           "rating": rating, "delta": delta, "rp": rp, "rpDelta": rp_delta,
           "rpNotes": notes, "started": True, "practice": practice,
           "myLeft": my_left, "foeLeft": foe_left}
    if kind == "random":
        # 연습판도 지금 티어를 싣는다 (안 바뀐 그대로) - 랜덤 배틀 응답 모양을 옛 앱이 보던 그대로 둔다
        out.update(season.tier_public(season.tier_of(rp)))
    return out


# ---------------------------------------------------------------- 상대 고르기
# 전력은 포켓몬마다 (종족값 합 x 레벨) 을 1.5 제곱해서 더한다. 그냥 더하면
# 센 한 마리와 약한 다섯이 고른 여섯과 같게 잡히는데, 실제로는 센 한 마리가
# 줄줄이 쓸어 담는다. 실제 파티 900판으로 재어 보니 '전력이 높은 쪽이 이긴다'
# 가 그냥 더하면 82%, 1.5 제곱이면 86% 맞았다 (2 제곱도 86%).
POWER_EXP = 1.5
_BST = {}


def _bst(species):
    v = _BST.get(species)
    if v is None:
        sp = deps.dex().get(species) or {}
        v = sum((sp.get("base") or {}).values()) or 300
        _BST[species] = v
    return v


def team_power(mons, cap=season.LEVEL_CAP):
    """팀 전력. 레벨은 상한으로 잘라서 잰다."""
    return sum((_bst(m["species"]) * min(cap, int(m["level"] or 1))) ** POWER_EXP
               for m in mons)


def _all_teams():
    """사람마다 랭크 배틀에서 싸울 팀의 (종, 레벨) 목록. 한 번에 다 가져온다.

    쿼리 둘이면 끝난다 - 등록한 팀 한 번, 바탕화면 파티 한 번. 등록한 팀이
    있는 사람은 바탕화면 파티를 안 본다.
    """
    teams = {}
    for r in db.q("SELECT t.user_id, p.species, p.level FROM rank_team t"
                  " JOIN pokemon p ON p.id=t.pokemon_id AND p.user_id=t.user_id"
                  " ORDER BY t.user_id, t.pos"):
        teams.setdefault(r["user_id"], []).append(
            {"species": r["species"], "level": r["level"]})
    party = {}
    for r in db.q("SELECT user_id, species, level FROM pokemon"
                  " WHERE on_desktop=1 ORDER BY user_id, slot, id"):
        party.setdefault(r["user_id"], []).append(
            {"species": r["species"], "level": r["level"]})
    for uid, mons in party.items():
        if uid not in teams:
            teams[uid] = mons[:config.MAX_PARTY]
    # 싸울 때와 같은 팀으로 잰다. 빠질 전설까지 전력에 넣으면 실제보다 센
    # 상대와 붙는다.
    return dict((uid, restrict(mons)[0]) for uid, mons in teams.items())


def _last_met(uid, minutes, practice=True):
    """그 시간 안에 붙은 상대 -> 마지막으로 붙은 시각.

    practice=False 면 연습판(하루 20판 뒤) 줄은 안 본다. 상대 고르기의 '오래 안 만난 사람부터'
    (3시간 건너뛰기 · 하루 감점)는 점수판끼리의 일이다 - 밤에 연습판으로 여러 명을 만났다고
    다음 날 아침 점수판에서 RP 가 가까운 사람들을 건너뛰면 안 된다.
    """
    cut = _iso(_now() - datetime.timedelta(minutes=minutes))
    rows = db.q("SELECT foe_id, MAX(ended_at) last FROM battle_record"
                " WHERE user_id=? AND ended_at > ? AND foe_id IS NOT NULL"
                + ("" if practice else " AND practice=0") +
                " GROUP BY foe_id", (uid, cut))
    return dict((r["foe_id"], r["last"]) for r in rows)


def _recent_foes(uid, minutes=PAIR_COOLDOWN_MIN, practice=True):
    """최근에 붙은 사람들. 연달아 같은 사람을 때리지 않게.

    같은 상대 30분 쿨타임(기본값)은 **연습판도 센다** - 점수가 없어도 한 사람을 몰아 치지 못하게.
    """
    return set(_last_met(uid, minutes, practice))


def _blocked_ids(uid):
    """나를 차단했거나 내가 차단한 사람. 어느 쪽이든 안 붙인다."""
    rows = db.q("SELECT user_id, target_id FROM friend_block"
                " WHERE user_id=? OR target_id=?", (uid, uid))
    out = set()
    for r in rows:
        out.add(r["target_id"] if r["user_id"] == uid else r["user_id"])
    return out


def can_defend(my_count, foe_count):
    """상대를 받는 쪽으로 세워도 되는가 — 마릿수만 본다.

    **받는 쪽이 거는 쪽보다 적으면 안 붙인다.** 시즌 1 에서 거는 쪽 마릿수가
    더 많은 판은 거는 쪽이 93% 를 이겼다. 여섯 마리로 거는 사람은 여섯 마리
    팀만 만난다. 두 마리뿐인 사람은 두 마리 이상인 팀과 붙는다 - 받는 쪽을
    '여섯 마리만' 으로 막으면 이제 막 시작한 사람이 붙을 상대가 없다.
    """
    return foe_count >= min(config.MAX_PARTY, my_count)


def find_opponent(uid, rng=None):
    """랜덤 배틀 상대 하나. 없으면 None.

    접속 여부는 보지 않는다. 상대가 꺼져 있어도 그 사람의 랭크 팀(없으면
    지금 파티)을 가져와 붙인다 - 친구 몇 명이 하는 서버라 '둘 다 켜져 있을
    때' 를 기다리면 배틀이 거의 안 성사된다.
    """
    rng = rng or random
    teams = _all_teams()
    mine = teams.get(uid)
    if not mine or not rank_ready(mine)[0]:
        return None
    # 3시간 건너뛰기는 점수판만 본다 (_last_met). 그래도 30분 안에 만난 사람은 연습판이라도 뺀다 -
    # 안 빼면 골라 놓고 can_fight 의 같은 상대 쿨타임에 걸려 '30분에 한 번' 으로 끝난다.
    skip = (_recent_foes(uid, RANDOM_REPEAT_MIN, practice=False) | _recent_foes(uid)
            | _blocked_ids(uid))
    skip.add(uid)

    my_power = team_power(mine) or 1.0
    ratings, played, points = {}, {}, {}
    for r in db.q("SELECT user_id, rating, games, rp FROM rank_stat"):
        ratings[r["user_id"]] = r["rating"]
        played[r["user_id"]] = r["games"]
        points[r["user_id"]] = r["rp"] or 0
    my_mmr = ratings.get(uid, BASE_RATING)
    my_placed = played.get(uid, 0) >= PLACEMENT
    my_rp = points.get(uid, 0)

    pool = []
    for other, mons in teams.items():
        # 랭크전 조건(Lv.50 이상 6마리)을 못 채운 사람은 상대로도 안 뽑는다 (rank_ready)
        if other in skip or not rank_ready(mons)[0] or not can_defend(len(mine), len(mons)):
            continue
        gap = abs(team_power(mons) / my_power - 1.0)
        pool.append((gap, other))
    if not pool:
        return None
    # **배치고사를 마친 사람과 아직인 사람을 갈라 붙인다.** 전력은 노력치를
    # 안 보기 때문에, 갈라 두지 않으면 잘 키운 사람이 한 판도 안 뛴 사람만
    # 골라 만나게 된다 (6턴에 여섯 마리가 다 눕는 판이 그것이다).
    # 같은 쪽에서 못 찾으면 전체로 넓힌다 - 상대가 없어 배틀이 아예 안
    # 성사되는 것보다는 낫다.
    same = [(g, u) for g, u in pool
            if (played.get(u, 0) >= PLACEMENT) == my_placed]
    # **점수(RP)가 가까운 띠부터** (시즌 4, RP_BANDS). 띠 안에서는 지금까지처럼 오래 안 만난
    # 사람 가운데 전력이 가까운 몇 명 중 하나다 (_pick_fresh). 마지막 띠가 '전체' 라서 받을 수
    # 있는 사람이 한 명이라도 있으면 붙는다 - 기울어진 판은 RP 가 조금만 움직인다.
    #
    # **띠가 바깥, 배치는 그 띠 안에서** (10/17). 처음에는 '배치가 같은 쪽' 을 띠보다 먼저 봐서,
    # 배치가 같은 사람을 찾느라 ±50 안에 있던 사람을 두고 RP 200 차이 상대를 골랐다 (시즌 4 첫
    # 1시간 반에 3번). 이제 띠마다 배치가 같은 쪽을 먼저 보고, 없으면 그 띠 안의 누구나 고른다.
    for band in RP_BANDS:
        for stage, cands in (("same", same), ("all", pool)):
            near = [(g, u) for g, u in cands
                    if band is None or abs(points.get(u, 0) - my_rp) <= band]
            if near:
                got = _pick_fresh(uid, near, rng, ratings, my_mmr, points, my_rp)
                _log_pick(uid, stage, -1 if band is None else band, near, got, played,
                          my_placed, len(pool), len(same))
                return got
    _log_pick(uid, "none", None, [], None, played, my_placed,
              len(pool), len(same))
    return None


def _log_pick(uid, stage, band, near, got, played, my_placed, npool, nsame):
    """어느 단계에서 상대를 골랐는지 남긴다.

    **진단용이다. 원인을 잡으면 이 함수와 match_log 표를 지운다.**
    배치고사를 마친 사람끼리 붙이는 1차(same)에서 골랐는지, 거기 아무도
    없어 전체(all)로 넓혔는지를 봐야 한다 - 같은 날 같은 코드에서 어떤
    사람은 미배치 상대를 0% 만나고 어떤 사람은 65% 를 만났다.

    여기서 난 예외가 배틀을 막으면 안 된다. 전부 감싸고 조용히 넘어간다.
    """
    try:
        placed_near = sum(1 for _g, u in near
                          if played.get(u, 0) >= PLACEMENT)
        db.run(
            "INSERT INTO match_log (at, user_id, stage, band, pool, same_n,"
            " near, near_placed, my_placed, foe_id, foe_games)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (_iso(), uid, stage, band, npool, nsame, len(near), placed_near,
             1 if my_placed else 0, got,
             played.get(got, 0) if got is not None else None))
    except Exception:                                       # noqa: BLE001
        pass


def _pick_fresh(uid, cands, rng, ratings=None, my_mmr=BASE_RATING, points=None, my_rp=0):
    """띠 안에서 한 명. **RP 가 가장 가까운 사람부터** (RP_TIE · MET_PENALTY 를 보라).

    cands 는 (전력 차이, user_id) 목록이다. 하루 안에 만난 사람은 RP 가 MET_PENALTY 만큼 더 먼 것으로 친다.
    RP 가 거의 같은 사람들 가운데서는 전력·숨은 점수가 가까운 순으로 줄 세워 앞의 몇 명 중에서 고른다 -
    제일 가까운 한 명만 고르면 같은 얼굴이 계속 나온다.
    """
    ratings = ratings or {}
    points = points or {}
    met = _last_met(uid, FRESH_WINDOW_MIN, practice=False)     # 하루 감점도 점수판만 (_last_met)

    def rp_cost(c):
        return abs(points.get(c[1], 0) - my_rp) + (MET_PENALTY if c[1] in met else 0)

    def dist(c):
        gap, other = c
        return gap + abs(ratings.get(other, BASE_RATING) - my_mmr) * MMR_WEIGHT

    best = min(rp_cost(c) for c in cands)
    close = sorted((c for c in cands if rp_cost(c) <= best + RP_TIE), key=dist)
    return rng.choice(close[:PICK_CLOSEST])[1]


def random_cooldown_left(uid):
    """랜덤 배틀을 다시 걸 수 있을 때까지 남은 초. 0 이면 지금 된다.

    랜덤 배틀을 연달아 누르면 한 판을 다 보기도 전에 다음 판이 계산돼서
    하루 도전 수가 금방 동난다. 내가 건 랜덤 배틀만 센다 - 걸려온 판과
    친구 배틀은 상관없다.
    """
    wait = int(config.RANDOM_COOLDOWN_SEC)
    if wait <= 0:
        return 0
    r = db.q1("SELECT MAX(ended_at) last FROM battle_record WHERE user_id=?"
              " AND started=1 AND kind='random'", (uid,))
    last = r["last"] if r else None
    if not last:
        return 0
    try:
        t = datetime.datetime.fromisoformat(last)
    except ValueError:
        return 0
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    left = wait - (_now() - t).total_seconds()
    return max(0, int(left + 0.999))


def rank_ready(mons):
    """랭크전(랜덤 배틀)에 나갈 수 있는 팀인가 (시즌 4). (됐나, Lv.RANK_MIN_LEVEL 이상 마릿수).

    mons 는 실제로 나가는 팀이다 (전설·환상 제한 뒤 - ranked_team / _all_teams). 레벨은 상한으로 자르기
    전의 원래 레벨로 센다.
    """
    n = sum(1 for m in mons or [] if int(m.get("level") or 1) >= season.RANK_MIN_LEVEL)
    return n >= season.RANK_MIN_COUNT, n


def rank_short(uid):
    """랭크전 조건을 못 채웠으면 그 까닭 한 줄, 채웠으면 None."""
    team, dropped, same = drop_counts(_ranked_source(uid))
    ok, n = rank_ready(team)
    if ok:
        return None
    why = ("랭크전(랜덤 배틀)은 Lv.%d 이상 포켓몬 %d마리로 팀을 채워야 걸 수 있습니다 (지금 %d마리)."
           % (season.RANK_MIN_LEVEL, season.RANK_MIN_COUNT, n))
    if same:
        why += " 같은 포켓몬은 한 팀에 %d마리만 나갑니다." % SAME_SPECIES_MAX
    if dropped:
        why += " 전설·환상 포켓몬은 한 팀에 %d마리만 나갑니다." % RESTRICTED_MAX
    return why


def can_start(uid, kind="random", practice_ok=False):
    """내 쪽 조건만. 상대를 고르기 전에 먼저 본다.

    상대까지 골라 놓고 막히면, 애먼 사람의 쿨다운만 태우게 된다.

    practice_ok = 거는 앱이 연습판을 안다고 알렸나 (POST /api/pvp/random 의 practice=1).
    **안 알린 옛 앱은 20판에서 예전처럼 막는다.** 옛 앱은 연습판을 모르니 막지 않으면 21판째도
    점수판인 줄 알고 걸고, 화면에는 'RP +0' 만 남는다 - 왜 점수가 안 오르는지 알 길이 없다.
    """
    team = ranked_team(uid) if kind == "random" else _party(uid)
    if not team:
        return "데리고 다니는 포켓몬이 없습니다."
    if kind == "random":
        why = rank_short(uid) or held_short(uid)
        if why:
            return why
        # 하루 상한과 쿨타임은 **랜덤 배틀에만** 건다. 새 앱(practice_ok)은 20판을 넘겨도 막지 않는다 -
        # 그 뒤는 연습판이다 (DAILY_BATTLES 의 설명, run_match 가 is_practice 로 가른다).
        if not practice_ok and is_practice(uid):
            return "오늘은 랜덤 배틀을 %d판까지 걸 수 있습니다. 내일 다시 해주세요." % DAILY_BATTLES
        left = random_cooldown_left(uid)
        if left:
            return "랜덤 배틀은 %d초 뒤에 다시 걸 수 있습니다." % left
    return None


def can_fight(uid, other, kind="friend", practice_ok=False):
    """지금 저 사람에게 걸 수 있는가. 안 되면 이유를 돌려준다. practice_ok 는 can_start 의 것."""
    if uid == other:
        return "자기 자신과는 싸울 수 없습니다."
    why = can_start(uid, kind, practice_ok)
    if why:
        return why
    if not db.q1("SELECT 1 x FROM users WHERE id=?", (other,)):
        return "그런 트레이너가 없습니다."
    if other in _blocked_ids(uid):
        return "이 트레이너와는 싸울 수 없습니다."
    if not (ranked_team(other) if kind == "random" else _party(other)):
        return "상대가 데리고 다니는 포켓몬이 없습니다."
    if kind == "random" and not rank_ready(ranked_team(other))[0]:
        return "상대 팀이 랭크전 조건(Lv.%d 이상 %d마리)을 못 채웠습니다." % (
            season.RANK_MIN_LEVEL, season.RANK_MIN_COUNT)
    if other in _recent_foes(uid):
        return ("같은 상대에게는 %d분에 한 번만 걸 수 있습니다."
                % PAIR_COOLDOWN_MIN)
    return None


def note_fight(uid, kind="random"):
    """도전 횟수를 하나 올린다. 실제로 붙인 뒤에 부른다.

    **랜덤 배틀만 센다.** 하루 상한이 랜덤 배틀에만 걸리므로, 친구 배틀까지
    세면 화면의 '오늘 남은 판' 이 실제로 걸 수 있는 수와 어긋난다.
    """
    if kind != "random":
        return
    _rating_row(uid)                 # 줄이 없으면 만든다
    today = _today()
    # 읽고 +1 해서 쓰면 동시에 끝난 두 판이 같은 값을 써서 한 판이 빠진다 - 한 문장으로 올린다 (10/29 검토).
    db.run("UPDATE rank_stat SET fought = CASE WHEN fought_day=? THEN fought + 1 ELSE 1 END, fought_day=?"
           " WHERE user_id=?", (today, today, uid))


def is_practice(uid):
    """지금 랜덤 배틀을 걸면 연습판인가 = 오늘(한국 날짜) 20판을 다 썼나. **읽기만 한다** (fight_left 와 같은 까닭)."""
    r = db.q1("SELECT fought, fought_day FROM rank_stat WHERE user_id=?", (uid,))
    return bool(r) and r["fought_day"] == _today() and (r["fought"] or 0) >= DAILY_BATTLES


def fight_left(uid):
    """오늘 랜덤 배틀을 몇 판 더 걸 수 있나 (1.13, /api/me 에 실어 트레이 메뉴가 쓴다).

    **읽기만 한다** - fight_status 는 _rating_row 로 랭크 줄을 만들어 버리는데, /api/me 는 모두가 90초마다
    부르므로 여기서 만들면 랜덤 배틀을 한 번도 안 한 사람까지 전부 줄이 생긴다.
    """
    r = db.q1("SELECT fought, fought_day FROM rank_stat WHERE user_id=?", (uid,))
    used = r["fought"] if r and r["fought_day"] == _today() else 0
    # practice = 다 썼으니 다음 판은 연습판 (새 앱이 '연습판 (점수 없음)' 으로 적는다). 옛 서버에는 이 칸이
    # 없다 - 앱은 칸이 없으면 예전처럼 '오늘은 다 함' 으로 적는다.
    return {"left": max(0, DAILY_BATTLES - used), "dailyBattles": DAILY_BATTLES,
            "practice": used >= DAILY_BATTLES}


def fight_status(uid):
    row = _rating_row(uid)
    today = _today()
    used = row["fought"] if row["fought_day"] == today else 0
    # foughtToday/left 는 **랜덤 배틀** 기준이다 (친구 배틀은 상한이 없다). foughtToday 는 연습판까지
    # 센 오늘 건 판 수라 20 을 넘을 수 있다 - left 는 0 아래로 안 내려간다.
    return {"foughtToday": used, "dailyBattles": DAILY_BATTLES,
            "left": max(0, DAILY_BATTLES - used),
            "practice": used >= DAILY_BATTLES, "practiceReward": PRACTICE_REWARD["win"],
            "randomCooldownSec": int(config.RANDOM_COOLDOWN_SEC),
            "randomCooldownLeft": random_cooldown_left(uid)}


# ---------------------------------------------------------------- 조회
def unseen(uid, limit=10):
    """내가 아직 안 본 대전. 상대가 걸어와서 생긴 것도 여기 들어온다."""
    rows = db.q(
        "SELECT id, kind, a_id, b_id, a_name, b_name, winner, created_at"
        " FROM pvp_match WHERE (a_id=? AND a_seen=0) OR (b_id=? AND b_seen=0)"
        " ORDER BY id DESC LIMIT ?", (uid, uid, limit))
    out = []
    for m in rows:
        mine_is_a = m["a_id"] == uid
        out.append({
            "id": m["id"], "kind": m["kind"],
            "foe": m["b_name"] if mine_is_a else m["a_name"],
            # 상대 id 도 준다. 목록에서 바로 다시 걸 수 있어야 한다.
            "foeId": m["b_id"] if mine_is_a else m["a_id"],
            # 내가 건 판인가, 상대가 걸어온 판인가. 알림 문구가 달라진다.
            "attacked": mine_is_a,
            "result": ("draw" if m["winner"] is None else
                       "win" if m["winner"] == uid else "lose"),
            "at": m["created_at"]})
    return out


def unseen_count(uid):
    r = db.q1("SELECT COUNT(*) c FROM pvp_match"
              " WHERE (a_id=? AND a_seen=0) OR (b_id=? AND b_seen=0)",
              (uid, uid))
    return r["c"] if r else 0


def match_view(uid, mid):
    """재생에 필요한 것을 돌려준다. 내가 낀 판만 볼 수 있다."""
    m = db.q1("SELECT * FROM pvp_match WHERE id=?", (mid,))
    if not m or uid not in (m["a_id"], m["b_id"]):
        return None
    mine_is_a = uid == m["a_id"]
    events = unpack(m["log"])
    if not mine_is_a:
        # 저장은 a 시점이다. b 에게는 뒤집어서 준다. 한 군데서만 뒤집어야
        # 화면마다 어긋나지 않는다.
        events = PB.flip_log(events)
    result = ("draw" if m["winner"] is None else
              "win" if m["winner"] == uid else "lose")
    foe_id = m["b_id"] if mine_is_a else m["a_id"]
    foe = {"name": m["b_name"] if mine_is_a else m["a_name"]}
    # 칭호·명패·티어는 **지금** 값이다(판 때의 값을 따로 남기지 않는다).
    # 투기장 이름표에 붙는 장식이라 지난 판을 다시 볼 때 지금 것이 떠도 된다.
    d = season.deco(foe_id)
    for k in ("title", "frame", "frameColor", "tier", "tierKr"):
        if d.get(k):
            foe[k] = d[k]
    # 길드 이름도 지금 값이다 (1.10.2). 길드에 든 상대는 이름표에 티어 대신
    # [길드명] 이 붙는다 - 고르는 것은 화면이다 (arena.plate_text). 길드 쪽에서
    # 무슨 일이 나도 다시보기가 막히면 안 된다.
    try:
        from . import guild
        g = guild.name_for(foe_id)
        if g:
            foe["guild"] = g
    except Exception:                                       # noqa: BLE001
        pass
    rec = db.q1("SELECT rp_delta, rp, practice FROM battle_record WHERE match_id=?"
                " AND user_id=?", (mid, uid))
    return {
        "id": m["id"], "kind": m["kind"], "result": result,
        "turns": m["turns"], "events": events,
        "me": {"name": m["a_name"] if mine_is_a else m["b_name"]},
        "foe": foe,
        "reward": m["a_reward"] if mine_is_a else m["b_reward"],
        # 랭크 배틀은 레벨 상한을 걸고 싸웠다. 화면이 알려야 "내 Lv.80 이
        # 왜 50 이지" 가 안 된다.
        "levelCap": season.LEVEL_CAP if m["kind"] == "random" else None,
        "rpDelta": rec["rp_delta"] if rec else 0,
        "rp": rec["rp"] if rec else None,
        # 연습판 (하루 20판 뒤): 결과 화면이 '연습판 · 점수 변화 없음' 을 적는다
        "practice": bool(rec["practice"]) if rec else False,
    }


def mark_seen(uid, mid):
    """다 봤다고 표시. 양쪽이 다 보면 로그를 지워도 된다."""
    col = None
    m = db.q1("SELECT a_id, b_id FROM pvp_match WHERE id=?", (mid,))
    if not m:
        return False
    if uid == m["a_id"]:
        col = "a_seen"
    elif uid == m["b_id"]:
        col = "b_seen"
    else:
        return False
    db.run("UPDATE pvp_match SET %s=1 WHERE id=?" % col, (mid,))
    return True


def records(uid, limit=30):
    """내 전적. 화면에서 목록으로 보고 다시 붙을 수 있게 만든다.

    상대 id 와 **지금 다시 걸 수 있는지**를 같이 준다. 화면이 조건을
    다시 따지면(쿨다운·하루 상한·차단) 서버 판정과 어긋난다.
    """
    rows = db.q("SELECT * FROM battle_record WHERE user_id=?"
                " ORDER BY id DESC LIMIT ?", (uid, limit))
    s2 = _season2_opened()
    # 아직 다시 볼 수 있는 판 (1.12.1). 로그는 KEEP_DAYS 가 지나면 치워지는데(prune) 전적은 남아서,
    # 화면이 '다시 보기' 를 띄울지 날짜로 따지면 이 규칙과 어긋난다 - 로그가 있는지를 그대로 본다.
    mids = sorted(set(r["match_id"] for r in rows if r["match_id"]))
    live = set()
    if mids:
        live = set(x["id"] for x in db.q("SELECT id FROM pvp_match WHERE id IN (%s)"
                                         % ",".join("?" * len(mids)), tuple(mids)))
    # 같은 상대가 여러 번 나오므로 판정을 한 번만 하고 돌려 쓴다.
    why = {}
    out = []
    for r in rows:
        fid = r["foe_id"]
        if fid is not None and fid not in why:
            why[fid] = can_fight(uid, fid)
        # **시즌 2 판의 숨은 점수 변화는 싣지 않는다.** 1.4.1 전적 목록은 RP 변화가
        # 0 이고 RP 도 0 이면(바닥에서 진 판) delta 를 '점수 -N' 으로 적어서, 안
        # 보여야 할 숨은 점수가 드러났다. 시즌 1 판은 그때 보이던 점수라 둔다.
        hide = (r["ended_at"] or "") >= s2
        out.append({"id": r["id"], "foe": r["foe_name"], "foeId": fid,
                    "kind": r["kind"], "result": r["result"],
                    # 내가 건 판인가. 걸려온 판은 점수·승패·돈에 안 들어가서
                    # 화면에서도 그렇게 보여야 한다.
                    "started": bool(r["started"]),
                    # 연습판 (하루 20판 뒤의 랜덤 배틀) - 점수에 안 들어간 판
                    "practice": bool(r["practice"]),
                    "rating": None if hide else r["rating"],
                    "delta": 0 if hide else r["delta"],
                    "rp": r["rp"], "rpDelta": r["rp_delta"],
                    "reward": r["reward"], "turns": r["turns"],
                    "myLeft": r["my_left"], "foeLeft": r["foe_left"],
                    "matchId": r["match_id"], "at": r["ended_at"],
                    "canReplay": r["match_id"] in live,
                    "lead": r["lead"], "foeLead": r["foe_lead"],
                    "canFight": (fid is not None and why.get(fid) is None),
                    "whyNot": why.get(fid) if fid is not None
                              else "상대가 누구인지 남아 있지 않습니다."})
    return out


S2_STARTS = "2026-09-15"


def _season2_opened():
    """시즌 2 가 열린 시각 (손질 0260 이 돈 때). 모르면 시즌 2 시작 날짜.

    **season.SEASON_STARTS 가 아니다** - 그건 지금 시즌(3)의 시작이라, 그걸
    쓰면 시즌 2 판의 숨은 점수 변화가 도로 보인다."""
    try:
        r = db.q1("SELECT v FROM meta WHERE k='mig:0260-season2-open'")
    except Exception:                                        # noqa: BLE001
        r = None
    return (r["v"] if r and r["v"] else S2_STARTS)


def clear_records(uid, rid=None):
    """전적을 지운다. rid 를 주면 한 줄만.

    **점수와 승패는 그대로 둔다.** 이건 목록일 뿐이고, 점수(rank_stat)는
    따로 센다. 지운다고 등수가 오르면 진 판만 골라 지우는 사람이 나온다.

    지운 줄 수를 돌려준다.
    """
    if rid is not None:
        return db.run("DELETE FROM battle_record WHERE id=? AND user_id=?",
                      (rid, uid)).rowcount
    return db.run("DELETE FROM battle_record WHERE user_id=?", (uid,)).rowcount


def summary(uid):
    r = _rating_row(uid)
    rp = r["rp"] or 0
    tier = season.tier_for(r, season.seats())
    nxt, need = season.next_tier(rp)
    ids = team_ids(uid)
    fighting, dropped, same = drop_counts(_ranked_source(uid))
    out = {"rating": r["rating"], "games": r["games"], "wins": r["wins"],
           "losses": r["losses"], "draws": r["draws"],
           "friendWins": r["fr_wins"], "friendLosses": r["fr_losses"],
           "friendDraws": r["fr_draws"], "streak": r["streak"],
           "best": r["best"], "ranked": bool(r["ranked"]),
           "placementLeft": max(0, PLACEMENT - r["games"]),
           "earnedToday": r["earned"] if r["earned_day"] == _today() else 0,
           "dailyCap": DAILY_CAP, "season": SEASON,
           "winReward": REWARD["win"],
           # 시즌 2
           "rp": rp, "peakRp": r["peak_rp"] or 0,
           "peakTier": season.tier_of(r["peak_rp"] or 0),
           "nextTier": nxt,
           "nextTierKr": season.TIER_KR.get(nxt) if nxt else None,
           "rpToNext": need, "floorRp": season.floor_rp(r["peak_rp"] or 0),
           "firstWinToday": r["win_day"] == _today(),
           "teamRegistered": bool(ids),
           "teamSize": len(fighting),
           "restrictedMax": RESTRICTED_MAX,
           "restrictedDropped": dropped,
           "sameSpeciesMax": SAME_SPECIES_MAX,
           "sameDropped": same,
           "levelCap": season.LEVEL_CAP,
           # 랭크전 조건 (시즌 4): 실제로 나가는 팀에 Lv.50 이상이 몇 마리인가
           "rankReady": rank_ready(fighting)[0], "rankReadyCount": rank_ready(fighting)[1]}
    if held_rule_on():
        # 시즌 5 만 싣는다 - 시즌 4 응답은 예전 모양 그대로. 옛 앱은 모르는 칸이라 무시한다.
        out["sameHeldMax"] = SAME_HELD_MAX
        out["heldDupes"] = len(same_held_ids(fighting))
    out.update(season.tier_public(tier))
    return out


def ranking(limit=50, uid=None):
    """순위표. 배치를 마친 사람만 오른다. RP 순이다 (시즌 2).

    숨은 점수(rating)는 같은 RP 끼리 줄 세울 때만 쓴다.
    """
    rows = db.q(
        "SELECT r.user_id, r.rating, r.rp, r.games, r.wins, r.losses, r.draws,"
        " r.streak, u.username FROM rank_stat r JOIN users u ON u.id=r.user_id"
        " WHERE r.ranked=1 ORDER BY r.rp DESC, r.rating DESC, r.wins DESC"
        " LIMIT ?", (limit,))
    deco = season.deco_map([r["user_id"] for r in rows])
    out = []
    for i, r in enumerate(rows, 1):
        d = deco.get(r["user_id"], {})
        out.append({"rank": i, "userId": r["user_id"], "name": r["username"],
                    "rating": r["rating"], "rp": r["rp"] or 0,
                    "tier": d.get("tier"), "tierKr": d.get("tierKr"),
                    "title": d.get("title"), "frame": d.get("frame"),
                    "frameColor": d.get("frameColor"),
                    "games": r["games"],
                    "wins": r["wins"], "losses": r["losses"],
                    "draws": r["draws"], "streak": r["streak"],
                    "me": uid is not None and r["user_id"] == uid})
    return out


def prune(days=KEEP_DAYS, practice_days=PRACTICE_KEEP_DAYS):
    """오래된 대전 로그를 치운다. 전적(battle_record)은 그대로 남는다.

    연습판 로그는 봤든 안 봤든 practice_days 가 지나면 치운다 (PRACTICE_KEEP_DAYS).
    """
    cut = _iso(_now() - datetime.timedelta(days=days))
    db.run("DELETE FROM pvp_match WHERE created_at < ?"
           " AND a_seen=1 AND b_seen=1", (cut,))
    db.run("DELETE FROM pvp_match WHERE practice=1 AND created_at < ?",
           (_iso(_now() - datetime.timedelta(days=practice_days)),))
    # 주인 없는 판도 같이 치운다.
    #
    # db.run 은 끊기면 다시 해보는데(Turso 가 가끔 끊긴다) INSERT 는
    # 멱등하지 않다. 넣기는 성공했는데 응답을 못 받고 다시 넣으면 대전
    # 행이 둘이 된다. 전적 쪽은 (match_id, user_id) 에 유일 인덱스가
    # 있어서 막히지만, 여기는 막을 방법이 없다. 그렇게 생긴 행은 전적이
    # 하나도 안 달려 있으므로 그걸로 가려낸다. 아무도 못 보는 자료라
    # 지워도 잃는 게 없다.
    db.run("DELETE FROM pvp_match WHERE created_at < ? AND id NOT IN"
           " (SELECT match_id FROM battle_record WHERE match_id IS NOT NULL)",
           (cut,))
