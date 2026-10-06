# -*- coding: utf-8 -*-
"""마이페이지 (1.9.0) — 내 정보와 내가 한 일을 한 화면에.

    GET /api/mypage

여기저기 흩어져 있던 것을 모은다. 새로 세는 것은 없고, 각 기능이 이미
적어 두는 표를 읽기만 한다:

  · 나       — 이름, 가입일, 달고 있는 칭호·명패, 지금 티어
  · 모은 것  — 포켓몬 수, 색이 다른 포켓몬, 도감, 친구
  · 관장     — 이긴 곳 수 / 전체 (gym_clear)
  · 칭호     — 가진 칭호 (achievements.titles 와 같은 목록에서 가진 것만)
  · 시즌     — 지금 시즌(rank_stat)과 지난 시즌들(season_result)
  · 레이드   — 참가한 판, 이긴 판
  · 게시판   — 쓴 글·댓글·받은 좋아요·알림의 수와 첫 쪽 (board.mine / mine_page).
               나머지 쪽은 GET /api/board/mine 으로 받는다 - 활동이 쌓여도 화면이 안 길어진다

창을 열 때만 부른다 (폴링하지 않는다).
"""
import datetime

from fastapi import APIRouter, Depends

from . import achievements, board, db, deps, gym, pvp, season

router = APIRouter()


def _days_since(iso, now=None):
    try:
        t = datetime.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return max(1, (now - t).days + 1)                # 가입한 날이 1일째


def _seasons(uid):
    """지금 시즌이 맨 앞, 그 뒤로 지난 시즌을 최근 것부터."""
    out = []
    s = pvp.summary(uid)
    rank = None
    if s.get("ranked"):
        r = db.q1(
            "SELECT COUNT(*) c FROM rank_stat a JOIN rank_stat b ON b.user_id=?"
            " WHERE a.ranked=1 AND (a.rp > b.rp OR (a.rp = b.rp AND a.rating > b.rating)"
            " OR (a.rp = b.rp AND a.rating = b.rating AND a.wins > b.wins))", (uid,))
        rank = int(r["c"]) + 1
    out.append({"season": season.SEASON, "current": True, "endsAt": season.SEASON_ENDS,
                "ranked": bool(s.get("ranked")), "placementLeft": s.get("placementLeft", 0),
                "rank": rank, "tier": s.get("tier"), "tierKr": s.get("tierKr"),
                "rp": s.get("rp", 0), "peakRp": s.get("peakRp", 0),
                "games": s.get("games", 0), "wins": s.get("wins", 0),
                "losses": s.get("losses", 0), "draws": s.get("draws", 0),
                "title": None})
    for r in db.q("SELECT * FROM season_result WHERE user_id=? ORDER BY season DESC", (uid,)):
        n = r["season"]
        out.append({"season": n, "current": False, "ranked": True, "rank": r["rank"],
                    # 시즌 1 은 숨은 점수뿐이던 시즌이다 (RP·티어가 없다)
                    "tier": r["tier"] if n >= 2 else None,
                    "tierKr": season.TIER_KR.get(r["tier"]) if n >= 2 and r["tier"] else None,
                    "rp": r["rp"] if n >= 2 else None,
                    "rating": r["rating"],
                    "games": r["games"], "wins": r["wins"], "losses": r["losses"],
                    "draws": r["draws"],
                    "title": season.TITLES.get(r["title"]) if r["title"] else None})
    return out


def _raid(uid):
    try:
        r = db.q1(
            "SELECT COUNT(*) c, SUM(CASE WHEN r.result='won' THEN 1 ELSE 0 END) w,"
            " SUM(m.damage) d FROM raid_member m JOIN raid_room r ON r.id=m.room_id"
            " WHERE m.user_id=? AND r.state='done'"
            " AND r.result IN ('won','lost','timeout')", (uid,))
        return {"games": int(r["c"] or 0), "wins": int(r["w"] or 0),
                "damage": int(r["d"] or 0)}
    except Exception:                                        # noqa: BLE001
        return {"games": 0, "wins": 0, "damage": 0}


def card(uid, dex, now=None):
    """마이페이지에서 **남에게 보여 줘도 되는 부분.** 없는 사람이면 None.

    길드원 프로필(GET /api/guild/members/{uid}/profile)이 쓴다. 소지금과 게시판
    활동(알림·내 글)은 싣지 않는다 - 그건 본인만 본다 (build 가 덧붙인다).
    """
    u = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    if not u:
        return None
    deco = season.deco(uid)
    mons = db.q1("SELECT COUNT(*) c, SUM(shiny) s, MAX(level) lv FROM pokemon WHERE user_id=?",
                 (uid,))
    seen = db.q1("SELECT COUNT(*) c, SUM(CASE WHEN caught>0 THEN 1 ELSE 0 END) k"
                 " FROM seen WHERE user_id=?", (uid,))
    st = db.q1("SELECT * FROM wild_state WHERE user_id=?", (uid,))
    friends = db.q1("SELECT COUNT(*) c FROM friend WHERE (a_id=? OR b_id=?)"
                    " AND state='accepted'", (uid, uid))
    g = gym.gyms()
    clears = gym.clears(uid)
    t = achievements.titles(uid)
    own = [{"id": c["id"], "name": c["name"], "group": c["group"], "how": c["how"]}
           for c in t["titles"] if c["owned"]]
    return {
        "user": {"id": uid, "name": u["username"], "createdAt": u["created_at"],
                 "days": _days_since(u["created_at"], now),
                 "title": deco.get("title"), "frameColor": deco.get("frameColor"),
                 "tier": deco.get("tier"), "tierKr": deco.get("tierKr")},
        "counts": {"pokemon": int(mons["c"] or 0), "shiny": int(mons["s"] or 0),
                   "topLevel": int(mons["lv"] or 0),
                   "dexCaught": int(seen["k"] or 0), "dexSeen": int(seen["c"] or 0),
                   "dexTotal": len(dex.species),
                   "encounters": st["encounters"] if st else 0,
                   "caught": st["caught"] if st else 0,
                   "friends": int(friends["c"] or 0)},
        "gym": {"cleared": len(clears), "total": len(g["regions"]),
                "wins": sum(int(c["wins"] or 0) for c in clears.values())},
        "titles": {"owned": own, "count": len(own), "total": t["total"],
                   "equipped": deco.get("title")},
        "seasons": _seasons(uid),
        "raid": _raid(uid),
    }


def build(user, dex, now=None):
    uid = user["id"]
    out = card(uid, dex, now)
    u = db.q1("SELECT money FROM users WHERE id=?", (uid,))
    out["user"]["admin"] = board.is_admin(user)
    out["user"]["money"] = u["money"]
    # 게시판 활동은 **수와 첫 쪽만** 싣는다. 나머지는 화면이 탭을 누르거나
    # 쪽을 넘길 때 /api/board/mine 으로 받는다 - 활동이 쌓여도 길어지지 않게.
    # 안 본 알림이 있으면 그 탭부터, 없으면 내 글부터 보여 준다.
    out["board"] = _board(uid, now)
    return out


def _board(uid, now=None):
    counts = board.mine(uid)
    first = board.mine_page(uid, "notify" if counts["unseen"] else "posts", 1, now)
    out = dict(counts)
    out["first"] = first
    out["pageSize"] = board.MINE_PAGE
    return out


@router.get("/api/mypage")
def mypage(ctx=Depends(deps.current)):
    return build(ctx["user"], deps.dex())
