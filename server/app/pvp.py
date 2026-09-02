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

from . import config, db, deps, items

# ---- 상금 ----
# 경험치는 주지 않는다(사용자가 정했다). 돈만 준다.
# 진 쪽도 조금 준다 - 아무것도 못 받으면 지고 나서 다시 걸 이유가 없다.
REWARD = {"win": 1000, "draw": 500, "lose": 300}

# 친구 배틀은 절반. 지목해서 붙는 구조라 부계정끼리 서로 져 주면
# 돈이 무한히 나온다. 아래 하루 상한과 같이 쓴다.
FRIEND_RATE = 0.5

# 하루에 배틀로 받을 수 있는 돈의 상한.
# 도구를 되팔면 한 번에 838원쯤 되고 몬스터볼이 200원이다. 6000원이면
# 하루치 벌이로 넉넉하되, 계속 돌린다고 끝없이 불어나지는 않는다.
DAILY_CAP = 6000

# ---- 점수 ----
# 흔히 쓰는 값. 32면 한 판에 최대 32점이 움직인다.
K = 32
BASE_RATING = 1000
# 이만큼 치러야 랭킹에 오른다. 한두 판 이기고 승률 100% 로 1등이 되는 걸 막는다.
PLACEMENT = 5

# ---- 도전 규칙 ----
# 상대는 접속해 있지 않아도 된다. 그 사람의 지금 파티를 가져와 붙인다.
# 그래서 자는 사람을 몇 번이고 때릴 수 있는데, 점수는 서로 주고받는
# 것이라 아침에 점수가 바닥나 있게 된다. 두 가지로 막는다.
PAIR_COOLDOWN_MIN = 30      # 같은 사람에게 다시 걸기까지
DAILY_BATTLES = 20          # 하루에 내가 걸 수 있는 도전 수

# 레벨대. 파티 평균 레벨을 20 단위로 끊는다. 같은 칸끼리 먼저 붙이고,
# 없으면 옆 칸으로, 그래도 없으면 아무나. 친구 몇 명이 하는 서버라
# '상대가 없습니다' 만 뜨는 것보다는 조금 기울어도 붙는 쪽이 낫다.
TIER_SIZE = 20
MAX_TIER = 4

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
def _expected(mine, theirs):
    return 1.0 / (1.0 + 10 ** ((theirs - mine) / 400.0))


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
    """바탕화면에 데리고 있는 포켓몬. 이게 곧 배틀 파티다."""
    rows = db.q("SELECT * FROM pokemon WHERE user_id=? AND on_desktop=1"
                " ORDER BY slot, id LIMIT ?", (uid, config.MAX_PARTY))
    return [db.row_to_mon(r) for r in rows]


def _name(uid):
    r = db.q1("SELECT username FROM users WHERE id=?", (uid,))
    return r["username"] if r else "?"


def run_match(a_uid, b_uid, kind="random", seed=None):
    """두 사람을 붙이고 결과를 남긴다. 부르는 순간 판이 끝난다.

    돌려주는 것: {"matchId", "winner"(user_id 또는 None), "turns",
                  "a": {...}, "b": {...}}
    양쪽의 dict 에는 result / reward / rating / delta 가 들어 있다.
    """
    dex = deps.dex()
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

    pay_a, day, used_a = _reward_for(a_uid, row_a, kind, res_a)
    pay_b, _d, used_b = _reward_for(b_uid, row_b, kind, res_b)

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

    fin_a = _settle(a_uid, row_a, b_uid, b_name, kind, res_a, pay_a, day,
                    used_a, out["turns"], left_a, left_b, lead_a, lead_b,
                    mid, row_b["rating"])
    fin_b = _settle(b_uid, row_b, a_uid, a_name, kind, res_b, pay_b, day,
                    used_b, out["turns"], left_b, left_a, lead_b, lead_a,
                    mid, row_a["rating"])

    return {"matchId": mid, "winner": winner_id, "turns": out["turns"],
            "kind": kind, "seed": seed, "a": fin_a, "b": fin_b}


def _left(events, side, total):
    """끝났을 때 그쪽에 남은 마릿수. ko 이벤트를 세면 나온다."""
    down = sum(1 for e in events
               if e.get("t") == "ko" and e.get("side") in (side, "both"))
    return max(0, total - down)


def _settle(uid, row, foe_id, foe_name, kind, result, pay, day, used,
            turns, my_left, foe_left, lead, foe_lead, mid, foe_rating):
    """한 사람 몫의 뒤처리 — 돈, 전적, 점수."""
    if pay > 0:
        items.money_add(uid, pay)

    # 점수는 랜덤 배틀만 움직인다. 친구 배틀은 지목해서 붙는 구조라
    # 부계정끼리 승패를 몰아줄 수 있다. 전적에는 남기되 점수는 그대로 둔다.
    rating = row["rating"]
    delta = 0
    if kind == "random":
        exp = _expected(row["rating"], foe_rating)
        delta = int(round(K * (_score(result) - exp)))
        rating = max(0, row["rating"] + delta)

    db.run("INSERT INTO battle_record (user_id, foe_id, foe_name, kind,"
           " result, rating, delta, reward, turns, my_left, foe_left,"
           " lead, foe_lead, match_id, ended_at)"
           " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
           (uid, foe_id, foe_name, kind, result, rating, delta, pay, turns,
            my_left, foe_left, lead, foe_lead, mid, _iso()))

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
            " updated_at=? WHERE user_id=?",
            (rating, games, won, lost, drew, streak, max(row["best"], rating),
             1 if games >= PLACEMENT else 0, day, used + pay, _iso(), uid))
    else:
        db.run(
            "UPDATE rank_stat SET fr_wins=fr_wins+?, fr_losses=fr_losses+?,"
            " fr_draws=fr_draws+?, earned_day=?, earned=?, updated_at=?"
            " WHERE user_id=?",
            (won, lost, drew, day, used + pay, _iso(), uid))

    return {"userId": uid, "result": result, "reward": pay,
            "rating": rating, "delta": delta,
            "myLeft": my_left, "foeLeft": foe_left}


# ---------------------------------------------------------------- 상대 고르기
def _tier(level):
    return max(0, min(MAX_TIER, int(level) // TIER_SIZE))


def _avg_levels():
    """사람마다 데리고 다니는 포켓몬의 평균 레벨. 한 번에 다 가져온다."""
    return dict((r["user_id"], r["lv"]) for r in db.q(
        "SELECT user_id, AVG(level) lv, COUNT(*) n FROM pokemon"
        " WHERE on_desktop=1 GROUP BY user_id HAVING n > 0"))


def _recent_foes(uid):
    """최근에 붙은 사람들. 연달아 같은 사람을 때리지 않게."""
    cut = _iso(_now() - datetime.timedelta(minutes=PAIR_COOLDOWN_MIN))
    rows = db.q("SELECT foe_id FROM battle_record WHERE user_id=?"
                " AND ended_at > ? AND foe_id IS NOT NULL", (uid, cut))
    return set(r["foe_id"] for r in rows)


def _blocked_ids(uid):
    """나를 차단했거나 내가 차단한 사람. 어느 쪽이든 안 붙인다."""
    rows = db.q("SELECT user_id, target_id FROM friend_block"
                " WHERE user_id=? OR target_id=?", (uid, uid))
    out = set()
    for r in rows:
        out.add(r["target_id"] if r["user_id"] == uid else r["user_id"])
    return out


def find_opponent(uid, rng=None):
    """랜덤 배틀 상대 하나. 없으면 None.

    접속 여부는 보지 않는다. 상대가 꺼져 있어도 그 사람의 지금 파티를
    가져와 붙인다 - 친구 몇 명이 하는 서버라 '둘 다 켜져 있을 때' 를
    기다리면 배틀이 거의 안 성사된다.
    """
    rng = rng or random
    levels = _avg_levels()
    if uid not in levels:
        return None
    skip = _recent_foes(uid) | _blocked_ids(uid)
    skip.add(uid)

    my = _tier(levels[uid])
    pool = [(u, _tier(lv)) for u, lv in levels.items() if u not in skip]
    if not pool:
        return None
    # 같은 칸 -> 옆 칸 -> 아무나. 넓혀 가며 처음 걸리는 데서 멈춘다.
    for gap in range(0, MAX_TIER + 1):
        near = [u for u, t in pool if abs(t - my) <= gap]
        if near:
            return rng.choice(near)
    return None


def can_start(uid):
    """내 쪽 조건만. 상대를 고르기 전에 먼저 본다.

    상대까지 골라 놓고 막히면, 애먼 사람의 쿨다운만 태우게 된다.
    """
    if not _party(uid):
        return "데리고 다니는 포켓몬이 없습니다."
    row = _rating_row(uid)
    used = row["fought"] if row["fought_day"] == _today() else 0
    if used >= DAILY_BATTLES:
        return "오늘은 %d판까지 걸 수 있습니다. 내일 다시 해주세요." % DAILY_BATTLES
    return None


def can_fight(uid, other):
    """지금 저 사람에게 걸 수 있는가. 안 되면 이유를 돌려준다."""
    if uid == other:
        return "자기 자신과는 싸울 수 없습니다."
    why = can_start(uid)
    if why:
        return why
    if not db.q1("SELECT 1 x FROM users WHERE id=?", (other,)):
        return "그런 트레이너가 없습니다."
    if other in _blocked_ids(uid):
        return "이 트레이너와는 싸울 수 없습니다."
    if not _party(other):
        return "상대가 데리고 다니는 포켓몬이 없습니다."
    if other in _recent_foes(uid):
        return ("같은 상대에게는 %d분에 한 번만 걸 수 있습니다."
                % PAIR_COOLDOWN_MIN)
    return None


def note_fight(uid):
    """도전 횟수를 하나 올린다. 실제로 붙인 뒤에 부른다."""
    row = _rating_row(uid)
    today = _today()
    used = row["fought"] if row["fought_day"] == today else 0
    db.run("UPDATE rank_stat SET fought_day=?, fought=? WHERE user_id=?",
           (today, used + 1, uid))


def fight_status(uid):
    row = _rating_row(uid)
    today = _today()
    used = row["fought"] if row["fought_day"] == today else 0
    return {"foughtToday": used, "dailyBattles": DAILY_BATTLES,
            "left": max(0, DAILY_BATTLES - used)}


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
    return {
        "id": m["id"], "kind": m["kind"], "result": result,
        "turns": m["turns"], "events": events,
        "me": {"name": m["a_name"] if mine_is_a else m["b_name"]},
        "foe": {"name": m["b_name"] if mine_is_a else m["a_name"]},
        "reward": m["a_reward"] if mine_is_a else m["b_reward"],
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
    # 같은 상대가 여러 번 나오므로 판정을 한 번만 하고 돌려 쓴다.
    why = {}
    out = []
    for r in rows:
        fid = r["foe_id"]
        if fid is not None and fid not in why:
            why[fid] = can_fight(uid, fid)
        out.append({"foe": r["foe_name"], "foeId": fid,
                    "kind": r["kind"], "result": r["result"],
                    "rating": r["rating"], "delta": r["delta"],
                    "reward": r["reward"], "turns": r["turns"],
                    "myLeft": r["my_left"], "foeLeft": r["foe_left"],
                    "matchId": r["match_id"], "at": r["ended_at"],
                    "lead": r["lead"], "foeLead": r["foe_lead"],
                    "canFight": (fid is not None and why.get(fid) is None),
                    "whyNot": why.get(fid) if fid is not None
                              else "상대가 누구인지 남아 있지 않습니다."})
    return out


def summary(uid):
    r = _rating_row(uid)
    return {"rating": r["rating"], "games": r["games"], "wins": r["wins"],
            "losses": r["losses"], "draws": r["draws"],
            "friendWins": r["fr_wins"], "friendLosses": r["fr_losses"],
            "friendDraws": r["fr_draws"], "streak": r["streak"],
            "best": r["best"], "ranked": bool(r["ranked"]),
            "placementLeft": max(0, PLACEMENT - r["games"]),
            "earnedToday": r["earned"] if r["earned_day"] == _today() else 0,
            "dailyCap": DAILY_CAP}


def ranking(limit=50, uid=None):
    """순위표. 배치를 마친 사람만 오른다."""
    rows = db.q(
        "SELECT r.user_id, r.rating, r.games, r.wins, r.losses, r.draws,"
        " r.streak, u.username FROM rank_stat r JOIN users u ON u.id=r.user_id"
        " WHERE r.ranked=1 ORDER BY r.rating DESC, r.wins DESC LIMIT ?",
        (limit,))
    out = []
    for i, r in enumerate(rows, 1):
        out.append({"rank": i, "userId": r["user_id"], "name": r["username"],
                    "rating": r["rating"], "games": r["games"],
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
