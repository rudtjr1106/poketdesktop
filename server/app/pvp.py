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
# 전력이 같으면 숨은 점수도 가까운 사람을. 400점 차이를 전력 10% 차이로 친다.
MMR_WEIGHT = 0.10 / 400.0

# 랜덤 배틀 상대를 고를 때는 최근에 붙은 사람을 이만큼 건너뛴다.
# 직접 지목하는 쪽(PAIR_COOLDOWN_MIN)보다 길게 본다 - 후보가 서른 명
# 넘게 있는데도 이레 동안 같은 사람과 열아홉 번 붙은 짝이 있었다.
RANDOM_REPEAT_MIN = 180
# 이 안에 만난 적이 없는 사람을 먼저 고른다.
FRESH_WINDOW_MIN = 60 * 24

# 다 본 대전 로그를 며칠이나 들고 있을지. 로그는 보고 나면 값이 없어지는
# 자료인데 한 판에 수십 KB 라 Turso 용량을 제일 먼저 먹는다.
KEEP_DAYS = 14


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(t=None):
    return (t or _now()).isoformat()


def _today():
    return _now().strftime("%Y-%m-%d")


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
def _reward_for(uid, row, kind, result):
    """이 판으로 받을 돈. 하루 상한에 걸리면 깎아서 준다.

    상한을 쓰는 이유는 친구끼리 서로 져 주며 돈을 찍어내는 걸 막기
    위해서다. 어느 방식으로 벌든 하루 총액이 같은 문에 걸리므로,
    나중에 배틀 종류가 늘어도 여기만 보면 된다.
    """
    want = REWARD[result]
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
# 랭크 배틀에 나가는 팀에는 전설·환상을 한 마리까지만. 본가 랭크 배틀의 '금지급
# 한 마리' 와 같은 생각이다. 시즌마다 1~5위가 알을 받으므로 그대로 두면 같은
# 사람에게 전설이 쌓인다. 한 마리일 때는 시뮬레이션으로 재어 보니 매칭이
# 상쇄해서 승률이 거의 안 오른다 (가장 센 종도 +5%p, 야생 한카리아스와 비슷).
#
# 등록한 랭크 팀은 두 마리째를 넣을 수 없다 (set_team). 등록하지 않아서 바탕화면
# 파티로 싸우는 사람은 **앞에 있는 한 마리만 나가고 나머지는 빠진다** (restrict).
RESTRICTED_MAX = 1


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


def restrict(mons):
    """랭크 배틀에 실제로 나가는 팀. (팀, 빠진 마릿수).

    전설·환상은 앞에서부터 RESTRICTED_MAX 마리만 남긴다. 순서는 그대로다.
    """
    names = restricted_species()
    out, seen, dropped = [], 0, 0
    for m in mons:
        if m.get("species") in names:
            if seen >= RESTRICTED_MAX:
                dropped += 1
                continue
            seen += 1
        out.append(m)
    return out, dropped


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
        rows = db.q("SELECT id, species FROM pokemon WHERE user_id=? AND id IN (%s)"
                    % marks, (uid,) + tuple(clean))
        if len(rows) != len(clean):
            raise ValueError("내 포켓몬만 넣을 수 있습니다.")
        names = restricted_species()
        if sum(1 for r in rows if r["species"] in names) > RESTRICTED_MAX:
            raise ValueError("랭크 팀에는 전설·환상 포켓몬을 %d마리까지 넣을 수 있습니다."
                             % RESTRICTED_MAX)
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


def run_match(a_uid, b_uid, kind="random", seed=None):
    """두 사람을 붙이고 결과를 남긴다. 부르는 순간 판이 끝난다.

    돌려주는 것: {"matchId", "winner"(user_id 또는 None), "turns",
                  "a": {...}, "b": {...}}
    양쪽의 dict 에는 result / reward / rating / delta / rp / rpDelta 가 들어 있다.

    랜덤 배틀은 랭크 팀으로, 레벨 상한을 걸고 싸운다. 친구 배틀은 지금까지처럼
    바탕화면 파티를 원래 레벨 그대로 쓴다 - 키운 보람은 거기서 보여 준다.
    """
    dex = deps.dex()
    if kind == "random":
        a_mons, b_mons = capped(ranked_team(a_uid)), capped(ranked_team(b_uid))
    else:
        a_mons, b_mons = _party(a_uid), _party(b_uid)
    if not a_mons or not b_mons:
        raise ValueError("양쪽 다 데리고 다니는 포켓몬이 있어야 합니다.")

    seed = random.randrange(1 << 30) if seed is None else int(seed)
    out = PB.simulate(dex, a_mons, b_mons, seed=seed)

    # 엔진은 a 시점으로 me/foe 를 말한다. 여기서 사람 쪽으로 옮긴다.
    win = out["winner"]
    res_a = {"me": "win", "foe": "lose", "draw": "draw"}[win]
    res_b = {"win": "lose", "lose": "win", "draw": "draw"}[res_a]
    winner_id = a_uid if res_a == "win" else (b_uid if res_a == "lose" else None)

    a_name, b_name = _name(a_uid), _name(b_uid)
    row_a, row_b = _rating_row(a_uid), _rating_row(b_uid)

    # a 가 건 쪽이다(run_match 를 부르는 자리에서 늘 그렇게 넘긴다).
    # b 는 걸려온 쪽이라 상금이 없다 - 계산도 하지 않는다.
    pay_a, day, used_a = _reward_for(a_uid, row_a, kind, res_a)
    pay_b, used_b = 0, 0

    mid = db.run(
        "INSERT INTO pvp_match (kind, a_id, b_id, a_name, b_name, winner,"
        " turns, seed, engine, log, a_reward, b_reward, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (kind, a_uid, b_uid, a_name, b_name, winner_id, out["turns"], seed,
         VERSION, pack(out["events"]), pay_a, pay_b, _iso())).lastrowid

    left_a = _left(out["events"], "me", len(a_mons))
    left_b = _left(out["events"], "foe", len(b_mons))
    lead_a = a_mons[0]["species"]
    lead_b = b_mons[0]["species"]
    # 실제로 싸운 두 팀(랭크 팀, 상한 걸린 레벨)의 전력비. 점수 기대치에 들어간다.
    ratio_a = power_ratio(a_mons, b_mons)

    fin_a = _settle(a_uid, row_a, b_uid, b_name, kind, res_a, pay_a, day,
                    used_a, out["turns"], left_a, left_b, lead_a, lead_b,
                    mid, row_b["rating"], power_ratio=ratio_a)
    fin_b = _settle(b_uid, row_b, a_uid, a_name, kind, res_b, pay_b, day,
                    used_b, out["turns"], left_b, left_a, lead_b, lead_a,
                    mid, row_a["rating"], started=False,
                    power_ratio=1.0 / ratio_a)

    return {"matchId": mid, "winner": winner_id, "turns": out["turns"],
            "kind": kind, "seed": seed, "a": fin_a, "b": fin_b}


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
            started=True, power_ratio=1.0):
    """한 사람 몫의 뒤처리 — 돈, 전적, 점수.

    started 는 **내가 걸었는가**다. 걸려온 쪽은 전적에 남기기만 하고
    점수도 승패도 돈도 건드리지 않는다.

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
    counts = started and kind == "random"
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
           " lead, foe_lead, match_id, started, ended_at, rp, rp_delta)"
           " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
           (uid, foe_id, foe_name, kind, result, rating, delta, pay, turns,
            my_left, foe_left, lead, foe_lead, mid, 1 if started else 0,
            _iso(), rp, rp_delta))

    if not started:
        # 걸려온 판은 여기서 끝. 점수·승패·하루 상한 어느 것도 안 건드린다.
        return {"userId": uid, "result": result, "reward": 0,
                "rating": rating, "delta": 0, "rp": rp, "rpDelta": 0,
                "started": False, "myLeft": my_left, "foeLeft": foe_left}

    won = 1 if result == "win" else 0
    lost = 1 if result == "lose" else 0
    drew = 1 if result == "draw" else 0
    if kind == "random":
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
           "rpNotes": notes, "started": True,
           "myLeft": my_left, "foeLeft": foe_left}
    if counts:
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


def _last_met(uid, minutes):
    """그 시간 안에 붙은 상대 -> 마지막으로 붙은 시각."""
    cut = _iso(_now() - datetime.timedelta(minutes=minutes))
    rows = db.q("SELECT foe_id, MAX(ended_at) last FROM battle_record"
                " WHERE user_id=? AND ended_at > ? AND foe_id IS NOT NULL"
                " GROUP BY foe_id", (uid, cut))
    return dict((r["foe_id"], r["last"]) for r in rows)


def _recent_foes(uid, minutes=PAIR_COOLDOWN_MIN):
    """최근에 붙은 사람들. 연달아 같은 사람을 때리지 않게."""
    return set(_last_met(uid, minutes))


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
    if not mine:
        return None
    skip = _recent_foes(uid, RANDOM_REPEAT_MIN) | _blocked_ids(uid)
    skip.add(uid)

    my_power = team_power(mine) or 1.0
    ratings = dict((r["user_id"], r["rating"]) for r in
                   db.q("SELECT user_id, rating FROM rank_stat"))
    my_mmr = ratings.get(uid, BASE_RATING)

    pool = []
    for other, mons in teams.items():
        if other in skip or not can_defend(len(mine), len(mons)):
            continue
        gap = abs(team_power(mons) / my_power - 1.0)
        pool.append((gap, other))
    if not pool:
        return None
    # 가까운 띠부터. 넓혀도 없으면 안 붙인다 - 기울어진 판을 억지로
    # 만드는 것보다 '지금은 상대가 없다' 가 낫다.
    for band in POWER_BANDS:
        near = [(g, u) for g, u in pool if g <= band]
        if near:
            return _pick_fresh(uid, near, rng, ratings, my_mmr)
    return None


def _pick_fresh(uid, cands, rng, ratings=None, my_mmr=BASE_RATING):
    """오래 안 만난 사람 중에서, 가장 가까운 몇 명 중 하나.

    cands 는 (전력 차이, user_id) 목록이다. 하루 안에 만난 적 없는 사람이
    먼저다. 가까운 순으로 줄 세우고 앞의 몇 명 중에서 고른다 - 제일 가까운
    한 명만 고르면 같은 얼굴이 계속 나오고, 아무나 고르면 띠 끝의 기울어진
    판이 잦아진다.
    """
    ratings = ratings or {}
    met = _last_met(uid, FRESH_WINDOW_MIN)

    def dist(c):
        gap, other = c
        return gap + abs(ratings.get(other, BASE_RATING) - my_mmr) * MMR_WEIGHT

    fresh = sorted((c for c in cands if c[1] not in met), key=dist)
    if fresh:
        return rng.choice(fresh[:PICK_CLOSEST])[1]
    # 다 만나 본 사람뿐이면 그중 가장 오래된 쪽
    return min((c[1] for c in cands), key=lambda u: met.get(u) or "")


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


def can_start(uid, kind="random"):
    """내 쪽 조건만. 상대를 고르기 전에 먼저 본다.

    상대까지 골라 놓고 막히면, 애먼 사람의 쿨다운만 태우게 된다.
    """
    team = ranked_team(uid) if kind == "random" else _party(uid)
    if not team:
        return "데리고 다니는 포켓몬이 없습니다."
    if kind == "random":
        # 하루 상한과 쿨타임은 **랜덤 배틀에만** 건다 (DAILY_BATTLES 의 설명).
        row = _rating_row(uid)
        used = row["fought"] if row["fought_day"] == _today() else 0
        if used >= DAILY_BATTLES:
            return "오늘은 랜덤 배틀을 %d판까지 걸 수 있습니다. 내일 다시 해주세요." % DAILY_BATTLES
        left = random_cooldown_left(uid)
        if left:
            return "랜덤 배틀은 %d초 뒤에 다시 걸 수 있습니다." % left
    return None


def can_fight(uid, other, kind="friend"):
    """지금 저 사람에게 걸 수 있는가. 안 되면 이유를 돌려준다."""
    if uid == other:
        return "자기 자신과는 싸울 수 없습니다."
    why = can_start(uid, kind)
    if why:
        return why
    if not db.q1("SELECT 1 x FROM users WHERE id=?", (other,)):
        return "그런 트레이너가 없습니다."
    if other in _blocked_ids(uid):
        return "이 트레이너와는 싸울 수 없습니다."
    if not (ranked_team(other) if kind == "random" else _party(other)):
        return "상대가 데리고 다니는 포켓몬이 없습니다."
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
    row = _rating_row(uid)
    today = _today()
    used = row["fought"] if row["fought_day"] == today else 0
    db.run("UPDATE rank_stat SET fought_day=?, fought=? WHERE user_id=?",
           (today, used + 1, uid))


def fight_status(uid):
    row = _rating_row(uid)
    today = _today()
    used = row["fought"] if row["fought_day"] == today else 0
    # foughtToday/left 는 **랜덤 배틀** 기준이다 (친구 배틀은 상한이 없다).
    return {"foughtToday": used, "dailyBattles": DAILY_BATTLES,
            "left": max(0, DAILY_BATTLES - used),
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
    rec = db.q1("SELECT rp_delta, rp FROM battle_record WHERE match_id=?"
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
                    "rating": None if hide else r["rating"],
                    "delta": 0 if hide else r["delta"],
                    "rp": r["rp"], "rpDelta": r["rp_delta"],
                    "reward": r["reward"], "turns": r["turns"],
                    "myLeft": r["my_left"], "foeLeft": r["foe_left"],
                    "matchId": r["match_id"], "at": r["ended_at"],
                    "lead": r["lead"], "foeLead": r["foe_lead"],
                    "canFight": (fid is not None and why.get(fid) is None),
                    "whyNot": why.get(fid) if fid is not None
                              else "상대가 누구인지 남아 있지 않습니다."})
    return out


def _season2_opened():
    """시즌 2 가 열린 시각 (손질 0260 이 돈 때). 모르면 시즌 시작 날짜."""
    try:
        r = db.q1("SELECT v FROM meta WHERE k='mig:0260-season2-open'")
    except Exception:                                        # noqa: BLE001
        r = None
    return (r["v"] if r and r["v"] else season.SEASON_STARTS)


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
    fighting, dropped = restrict(_ranked_source(uid))
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
           "levelCap": season.LEVEL_CAP}
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


def prune(days=KEEP_DAYS):
    """오래된 대전 로그를 치운다. 전적(battle_record)은 그대로 남는다."""
    cut = _iso(_now() - datetime.timedelta(days=days))
    db.run("DELETE FROM pvp_match WHERE created_at < ?"
           " AND a_seen=1 AND b_seen=1", (cut,))
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
