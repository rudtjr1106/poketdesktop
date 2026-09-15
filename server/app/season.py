# -*- coding: utf-8 -*-
"""랭크 시즌 — 티어, 랭크 포인트(RP), 칭호와 명패.

시즌 2 부터 숫자가 둘로 나뉜다.

  · **숨은 점수(MMR)** — rank_stat.rating. 전과 같은 Elo 다. 화면에는 안
    보이고, 한 판에서 RP 가 얼마나 움직일지를 정하는 데만 쓴다.
  · **랭크 포인트(RP)** — rank_stat.rp. 보이는 숫자이고 티어를 정한다.
    이기면 크게 오르고 지면 조금 내려간다. 반반으로 싸우면 판마다 조금씩
    오르므로, 판을 한 만큼 올라간다.

시즌 1 은 한 숫자로 둘 다 하려고 했다. 그러면 '나와 비슷한 사람과 반반으로
싸우는 재미' 와 '한 만큼 올라가는 보람' 이 서로를 깎는다 - 공평하게 붙이면
점수가 안 오르고, 점수가 오르게 두면 약한 사람만 골라 때리게 된다.

위쪽의 자랑은 주로 **보이는 것**으로 준다(칭호·명패·이로치사탕). 배틀에서
유리해지는 것을 넓게 주면 격차가 굳어서 아래쪽이 떠난다. 예외는 맨 위 다섯
자리의 알(eggs.py)이다 - 전설·환상은 Lv.5 로 태어나서 키워야 쓸모가 있다.
"""
import datetime

from . import db

SEASON = 2
# 화면에 적는 날짜. 시즌은 운영자가 migrations 로 닫는다 - 이 날짜가 지났다고
# 저절로 닫히지 않는다.
SEASON_STARTS = "2026-09-15"
SEASON_ENDS = "2026-10-01"

# 랜덤(랭크) 배틀에서만 쓴다. 이보다 높은 포켓몬은 이 레벨로 싸운다.
# 모두를 50 으로 올리지는 않는다 - 아래쪽은 키운 만큼 강해지는 재미가 그대로
# 남고, 위쪽은 전부 50 에서 만나 팀 구성과 기술로 갈린다.
LEVEL_CAP = 50

# ---- 티어 ----
# (열쇠, 이름, 오르는 RP). 위의 두 칸(사천왕·챔피언)은 RP 가 아니라 자리다.
TIERS = [
    ("monster", "몬스터볼", 0),
    ("super", "슈퍼볼", 300),
    ("hyper", "하이퍼볼", 700),
    ("master", "마스터볼", 1200),
]
TIER_KR = dict((k, n) for k, n, _ in TIERS)
TIER_KR.update({"elite": "사천왕", "champion": "챔피언"})
# 슈퍼볼에 한 번 오르면 그 아래로는 안 내려간다. 아래 두 칸이 안 떨어져야
# 처음 하는 사람이 부담 없이 붙는다.
SAFE_RP = 300
# 마스터볼 안에서 RP 1등이 챔피언, 2~5등이 사천왕. 자리 수가 정해져 있어서
# 오래 해도 모두가 앉을 수는 없다 - 여기가 우월감의 자리다.
ELITE_SEATS = 4

# ---- RP ----
# 이기면 10~30, 지면 5~25. 기대 승률(숨은 점수로 잰다)에 따라 갈린다.
# 비슷한 상대면 +20 / -15 라 반반만 해도 판마다 2.5 씩 오른다.
WIN_BASE, WIN_SWING = 10, 20
LOSS_BASE, LOSS_SWING = 5, 20
# 하루 첫 승. 하루 한 판만 해도 의미가 있게.
FIRST_WIN_RP = 10
# 이만큼 연달아 진 뒤에는 져도 절반만 깎는다.
LOSS_GUARD = 3

# ---- 칭호 · 명패 ----
TITLES = {
    "s1_champion": "시즌 1 챔피언",
    "s1_elite": "시즌 1 사천왕",
    "s1_top10": "시즌 1 TOP 10",
    "s1_top30": "시즌 1 상위권",
    "s2_champion": "시즌 2 챔피언",
    "s2_elite": "시즌 2 사천왕",
    "s2_master": "시즌 2 마스터볼",
    "s2_hyper": "시즌 2 하이퍼볼",
    "s2_super": "시즌 2 슈퍼볼",
}
# 이름 둘레의 색. 랭킹·친구·투기장에서 남에게 보인다.
FRAMES = {
    "gold": ("금빛 명패", "#ffc043"),
    "silver": ("은빛 명패", "#c9d1e6"),
    "bronze": ("동빛 명패", "#d08a52"),
    "master": ("마스터볼 명패", "#b57bff"),
}

SHINY_ITEM = "SHINYCANDY"
EGG_KR = {"legendary": "전설의 포켓몬 알", "mythical": "환상의 포켓몬 알"}

# 보상의 급을 가르는 것은 **알**이다. 1위는 전설, 2~5위는 환상. 이로치사탕은
# 한 사람에 하나까지만, 위쪽에만 준다 - 많이 뿌리면 이로치가 흔해진다.
#
# 시즌 1 은 티어가 없던 시즌이라 마지막 순위로 나눈다. 이미 끝난 시즌의 표라
# 실제로 나가는 숫자는 migrations 에 적혀 있다 (여기는 보여 주기용이다).
# (첫 등수, 끝 등수, 칭호, 명패, 이로치사탕, 알)
S1_REWARDS = [
    (1, 1, "s1_champion", "gold", 1, "legendary"),
    (2, 5, "s1_elite", "silver", 1, "mythical"),
    (6, 10, "s1_top10", "bronze", 1, None),
    (11, 30, "s1_top30", None, 0, None),
]

# 시즌 2 가 끝날 때 줄 것. **도달한 최고 티어**로 준다 - 마지막 점수로 주면
# 막판에 안 하고 버티게 된다. 사천왕·챔피언은 자리라 끝날 때의 자리로 본다.
# 몬스터볼에 머문 사람은 보상이 없다.
# (티어, 칭호, 명패, 이로치사탕, 알)
S2_REWARDS = [
    ("champion", "s2_champion", "gold", 1, "legendary"),
    ("elite", "s2_elite", "silver", 1, "mythical"),
    ("master", "s2_master", "master", 1, None),
    ("hyper", "s2_hyper", None, 0, None),
    ("super", "s2_super", None, 0, None),
]


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()


# ---------------------------------------------------------------- 티어
def tier_of(rp):
    """RP 로만 정하는 볼 티어. 사천왕·챔피언은 seats() 가 따로 정한다."""
    key = TIERS[0][0]
    for k, _n, need in TIERS:
        if rp >= need:
            key = k
    return key


def next_tier(rp):
    """다음 티어와 남은 RP. 마스터볼이면 (None, 0)."""
    for k, n, need in TIERS:
        if rp < need:
            return k, need - rp
    return None, 0


def floor_rp(peak):
    """이 아래로는 안 내려간다."""
    return SAFE_RP if peak >= SAFE_RP else 0


def expected(mine, theirs):
    return 1.0 / (1.0 + 10 ** ((theirs - mine) / 400.0))


def rp_change(result, my_mmr, foe_mmr, streak, first_win, rp, peak):
    """한 판으로 움직일 RP. (새 RP, 변화량, 붙은 말들) 을 돌려준다.

    streak 은 **이 판 전의** 연승(+)/연패(-) 다.
    """
    exp = expected(my_mmr, foe_mmr)
    notes = []
    if result == "win":
        d = WIN_BASE + int(round(WIN_SWING * (1.0 - exp)))
        if first_win:
            d += FIRST_WIN_RP
            notes.append("오늘 첫 승 +%d" % FIRST_WIN_RP)
    elif result == "lose":
        d = -(LOSS_BASE + int(round(LOSS_SWING * exp)))
        if streak <= -LOSS_GUARD:
            d = -int(round(abs(d) / 2.0))
            notes.append("연패 보호")
    else:
        d = 0
    new = max(floor_rp(peak), rp + d)
    return new, new - rp, notes


def seats(limit=1 + ELITE_SEATS):
    """지금 챔피언·사천왕 자리에 앉은 사람. {user_id: "champion"/"elite"}.

    마스터볼 안에서 RP 순. 마스터볼이 한 명도 없으면 자리는 비어 있다.
    """
    need = TIERS[-1][2]
    rows = db.q("SELECT user_id FROM rank_stat WHERE ranked=1 AND rp >= ?"
                " ORDER BY rp DESC, rating DESC, wins DESC LIMIT ?",
                (need, limit))
    out = {}
    for i, r in enumerate(rows):
        out[r["user_id"]] = "champion" if i == 0 else "elite"
    return out


def tier_for(row, seat_map):
    """rank_stat 행 하나의 지금 티어 (자리까지 본다)."""
    if row is None:
        return TIERS[0][0]
    seat = seat_map.get(row["user_id"])
    return seat or tier_of(row["rp"] or 0)


def tier_public(key):
    return {"tier": key, "tierKr": TIER_KR.get(key, key)}


# ---------------------------------------------------------------- 칭호 · 명패
def owned(uid):
    """가진 칭호와 명패."""
    rows = db.q("SELECT kind, rid, season, got_at FROM user_reward"
                " WHERE user_id=? ORDER BY got_at, rid", (uid,))
    titles, frames = [], []
    for r in rows:
        if r["kind"] == "title" and r["rid"] in TITLES:
            titles.append({"id": r["rid"], "name": TITLES[r["rid"]],
                           "season": r["season"]})
        elif r["kind"] == "frame" and r["rid"] in FRAMES:
            name, color = FRAMES[r["rid"]]
            frames.append({"id": r["rid"], "name": name, "color": color,
                           "season": r["season"]})
    return titles, frames


def grant(uid, kind, rid, season, equip_if_empty=True, now=None):
    """칭호나 명패를 준다. 이미 있으면 아무 일도 없다. 새로 받았으면 True.

    달고 있는 것이 없으면 받은 것을 바로 단다. 칭호가 새로 생긴 기능이라
    처음부터 비어 있던 자리다 - 누가 고른 것을 덮어쓰는 일은 없다.
    """
    table = TITLES if kind == "title" else FRAMES if kind == "frame" else None
    if table is None or rid not in table:
        return False
    cur = db.run("INSERT INTO user_reward (user_id, kind, rid, season, got_at)"
                 " VALUES (?,?,?,?,?) ON CONFLICT(user_id, kind, rid) DO NOTHING",
                 (uid, kind, rid, season, now or _now_iso()))
    got = getattr(cur, "rowcount", 1) > 0
    if equip_if_empty:
        col = "title" if kind == "title" else "frame"
        db.run("UPDATE users SET %s=? WHERE id=? AND %s IS NULL" % (col, col),
               (rid, uid))
    return got


def equip(uid, title=None, frame=None):
    """단다. None 은 그대로, "" 은 뗀다. 가진 것만 달 수 있다."""
    titles, frames = owned(uid)
    if title is not None:
        if title and title not in set(t["id"] for t in titles):
            raise ValueError("가지고 있지 않은 칭호입니다.")
        db.run("UPDATE users SET title=? WHERE id=?", (title or None, uid))
    if frame is not None:
        if frame and frame not in set(f["id"] for f in frames):
            raise ValueError("가지고 있지 않은 명패입니다.")
        db.run("UPDATE users SET frame=? WHERE id=?", (frame or None, uid))


def deco_map(ids):
    """이름 옆에 붙일 것 — 칭호·명패·티어. {user_id: {...}}.

    목록 화면(랭킹·친구)이 사람마다 따로 묻지 않게 한 번에 만든다.
    """
    ids = [int(i) for i in set(ids) if i is not None]
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    users = dict((r["id"], r) for r in db.q(
        "SELECT id, title, frame FROM users WHERE id IN (%s)" % marks,
        tuple(ids)))
    stats = dict((r["user_id"], r) for r in db.q(
        "SELECT user_id, rp, ranked, games FROM rank_stat WHERE user_id IN (%s)"
        % marks, tuple(ids)))
    seat_map = seats()
    out = {}
    for uid in ids:
        u = users.get(uid)
        st = stats.get(uid)
        title = u["title"] if u is not None and "title" in u.keys() else None
        frame = u["frame"] if u is not None and "frame" in u.keys() else None
        d = {"title": TITLES.get(title) if title else None,
             "frame": frame if frame in FRAMES else None,
             "frameColor": FRAMES[frame][1] if frame in FRAMES else None,
             "rp": (st["rp"] or 0) if st else 0,
             "ranked": bool(st["ranked"]) if st else False}
        d.update(tier_public(tier_for(st, seat_map) if st else TIERS[0][0]))
        out[uid] = d
    return out


def deco(uid):
    return deco_map([uid]).get(int(uid), {})


# ---------------------------------------------------------------- 보여 줄 표
def rules_public():
    """랭킹 화면에 적을 규칙과 보상. 숫자는 여기 한 곳에만 둔다."""
    return {
        "season": SEASON, "startsAt": SEASON_STARTS, "endsAt": SEASON_ENDS,
        "levelCap": LEVEL_CAP,
        "tiers": [{"tier": k, "tierKr": n, "rp": need} for k, n, need in TIERS]
                 + [{"tier": "elite", "tierKr": TIER_KR["elite"],
                     "seats": ELITE_SEATS},
                    {"tier": "champion", "tierKr": TIER_KR["champion"],
                     "seats": 1}],
        "safeRp": SAFE_RP,
        "rp": {"win": [WIN_BASE, WIN_BASE + WIN_SWING],
               "lose": [LOSS_BASE, LOSS_BASE + LOSS_SWING],
               "firstWin": FIRST_WIN_RP, "lossGuard": LOSS_GUARD},
        "rewards": [{"tier": t, "tierKr": TIER_KR[t],
                     "title": TITLES[title],
                     "frame": FRAMES[frame][0] if frame else None,
                     "frameColor": FRAMES[frame][1] if frame else None,
                     "shiny": n, "egg": EGG_KR.get(egg)}
                    for t, title, frame, n, egg in S2_REWARDS],
    }


def hall(season, limit=10):
    """지난 시즌 순위표 (명예의 전당)."""
    rows = db.q("SELECT * FROM season_result WHERE season=?"
                " ORDER BY rank LIMIT ?", (season, limit))
    return [{"rank": r["rank"], "userId": r["user_id"], "name": r["name"],
             "rating": r["rating"], "games": r["games"], "wins": r["wins"],
             "losses": r["losses"],
             "title": TITLES.get(r["title"]) if r["title"] else None}
            for r in rows]


def s1_reward_for(rank):
    for lo, hi, title, frame, n, egg in S1_REWARDS:
        if lo <= rank <= hi:
            return title, frame, n, egg
    return None, None, 0, None
