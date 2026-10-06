# -*- coding: utf-8 -*-
"""도감 업적 (시즌 3).

## 무엇을 하나

도감을 채우면 칭호를 준다. 작은 단계에는 몬스터볼을 조금. **업적은 시즌과
상관없이 영구히 남는다** (user_reward 의 season 을 0 으로 적는다).

## 해금

도감에는 있지만 **어떤 방법으로도 얻을 수 없던 31종**(울트라비스트 11 ·
패러독스 20)이 있다. 도감 파일은 이들을 '전설' 로 묶지만 알 목록(legends)
에서는 빠져 있고 야생에도 안 나온다. 그래서 도감 100% 가 불가능했다.

    7세대에서 평소 얻을 수 있는 종의 80% -> 울트라비스트가 풀숲에 나온다
    9세대에서 평소 얻을 수 있는 종의 80% -> 패러독스가 풀숲에 나온다

**'세대 전체의 80%' 가 아니다.** 7세대는 평소 놀이로 69%(61/88), 9세대는
73%(88/120)까지만 채워진다 - 나머지가 알 전용 전설이거나 바로 이 해금
대상이라서다. 전체 기준이면 아무도 못 연다.

## 판정 시점

포켓몬을 얻는 곳(야생 잡기·배틀 중 잡기·부화·진화·스타팅)에서 부른다.
처음 보는 사람은 /api/me 에서 한 번 몰아서 센다 - 이미 쌓인 기록이 있어서
켜자마자 여러 개가 한꺼번에 달성된다. 알리는 것은 화면이 알아서 묶는다.

## 알림

운영체제 알림은 쓰지 않는다. 게임 안의 일이라서다(app.toast 의 규칙:
"잡을 때마다 튀어나오면 결국 프로그램을 끄게 된다"). 안 본 업적을 me 에
실어 보내고, 화면이 게임 안에서 알린 뒤 seen 을 부른다.
"""
import datetime
import math

from common import legends as L
from common import pokelogic as P

from . import config, db, deps, season

# 지방 이름. 세대 번호 -> 지방.
REGION = {1: "관동", 2: "성도", 3: "호연", 4: "신오", 5: "하나",
          6: "칼로스", 7: "알로라", 8: "가라르", 9: "팔데아"}

# 해금
UNLOCK_PCT = 0.8            # 그 세대의 평소 얻을 수 있는 종 중 이만큼
UNLOCK_CHANCE = 0.02        # 풀숲 하나에 나올 확률
UNLOCK_LEVEL = 50           # 레벨 고정 (쉐이미처럼 야생 추첨을 안 거친다)
# 해금 종 중에는 포획률이 5·10 인 것이 여덟이다. 그대로면 보통 볼로 거의
# 안 잡혀서 해금한 보람이 없다. 울트라비스트(45)만큼은 쳐준다.
UNLOCK_CATCH_FLOOR = 45
UNLOCKS = {7: ("unlock_ultra", "울트라홀"), 9: ("unlock_paradox", "패러독스")}

TYPE_TARGET = 20            # 타입 수집가: 그 타입을 이만큼


# ---------------------------------------------------------------- 도감에서 뽑는 목록
_cache = {}


def _data():
    """도감에서 한 번 뽑아 두는 목록. 도감이 바뀌면(서버 재시작) 다시 만든다."""
    d = deps.dex()
    if _cache.get("dex") is d:
        return _cache
    sp = d.species
    wild = set(s["internal"] for s in sp if s.get("spawnable"))
    event = config.EVENT_SPECIES
    # 아예 못 얻던 것 = 야생에도 없고 알에도 없고 이벤트도 아닌 것
    locked = [s for s in sp if s["internal"] not in wild
              and not L.kind_of(s["num"]) and s["internal"] != event]
    unlock_pool = {}
    for s in locked:
        unlock_pool.setdefault(s["gen"], []).append(s["internal"])
    # 지방 도감 완성 목표: 전설·환상(알 전용)과 이벤트를 뺀 나머지.
    # 해금 대상은 **들어간다** - 풀리면 채울 수 있다.
    region = {}
    for s in sp:
        if L.kind_of(s["num"]) or s["internal"] == event:
            continue
        region.setdefault(s["gen"], set()).add(s["internal"])
    # 해금 문턱: 그 세대의 '평소 얻을 수 있는' 종 = 야생
    gen_wild = {}
    for s in sp:
        if s["internal"] in wild:
            gen_wild.setdefault(s["gen"], set()).add(s["internal"])
    # 진화 계열: 진화로 이어진 무리 중 **전부 야생에서 얻을 수 있는** 것만.
    adj = {}
    for s in sp:
        for e in s.get("evo") or []:
            t = e.get("to")
            if t and t in d.by_internal:
                adj.setdefault(s["internal"], set()).add(t)
                adj.setdefault(t, set()).add(s["internal"])
    families, seen = [], set()
    for k in adj:
        if k in seen:
            continue
        stack, comp = [k], set()
        while stack:
            x = stack.pop()
            if x in comp:
                continue
            comp.add(x)
            stack.extend(adj.get(x, set()) - comp)
        seen |= comp
        if len(comp) >= 2 and comp <= wild:
            families.append(frozenset(comp))
    types = {}
    for s in sp:
        for t in s.get("types") or []:
            types.setdefault(t, set()).add(s["internal"])
    _cache.clear()
    _cache.update({"dex": d, "wild": wild, "unlock_pool": unlock_pool,
                   "unlock_all": set(s["internal"] for s in locked),
                   "region": region, "gen_wild": gen_wild,
                   "families": families, "types": types})
    return _cache


# ---------------------------------------------------------------- 업적 목록
def _defs():
    """(열쇠, 갈래, 이름, 설명, 무엇을 세나, 목표, 칭호 id, 볼, 숨김).

    칭호 id 가 있으면 칭호를 준다 (season.TITLES 에 등록된다).
    """
    d = deps.dex()
    data = _data()
    out = []

    def add(key, group, name, desc, stat, target, title=None, balls=0, hidden=False):
        out.append({"key": key, "group": group, "name": name, "desc": desc,
                    "stat": stat, "target": int(target), "title": title,
                    "balls": int(balls), "hidden": hidden})

    # 도감 수집
    for n, balls, title in ((50, 5, None), (100, 10, None), (200, 10, None),
                            (400, 0, "도감 조사원"), (600, 20, None),
                            (800, 0, "도감 연구원"), (900, 0, "도감 박사")):
        add("dex_%d" % n, "도감 수집", "%d종" % n, "포켓몬 %d종을 잡아 도감에 올리기" % n,
            "dex", n, title, balls)
    # 지방 도감 완성
    for g in sorted(data["region"]):
        name = "%s 도감 완성" % REGION.get(g, "%d세대" % g)
        add("region_%d" % g, "지방 도감", name,
            "%s 지방 포켓몬을 모두 잡기 (전설·환상 제외)" % REGION.get(g, ""),
            "region_%d" % g, len(data["region"][g]), name)
    # 타입 수집가
    for t in sorted(data["types"]):
        tk = d.type_name(t)
        add("type_%s" % t, "타입 수집가", "%s 수집가" % tk,
            "%s 타입 포켓몬 %d종 잡기" % (tk, TYPE_TARGET),
            "type_%s" % t, TYPE_TARGET, "%s 수집가" % tk)
    # 이로치
    for n, title in ((1, "이로치 발견"), (5, "이로치 수집가"), (10, "이로치 마스터")):
        add("shiny_%d" % n, "이로치", title, "색이 다른 포켓몬 %d마리 얻기" % n,
            "shiny", n, title)
    # 전설·환상
    for n, title in ((10, "전설을 만난 자"), (30, "전설의 수집가")):
        add("legend_%d" % n, "전설·환상", title, "전설의 포켓몬 %d종 얻기" % n,
            "legendary", n, title)
    for n, title in ((5, "환상을 본 자"), (15, "환상의 수집가")):
        add("myth_%d" % n, "전설·환상", title, "환상의 포켓몬 %d종 얻기" % n,
            "mythical", n, title)
    # 진화 계열
    for n, title in ((10, "진화 탐구가"), (50, "진화 박사")):
        add("family_%d" % n, "진화 계열", title,
            "한 진화 계열의 모든 모습을 잡기 %d계열" % n, "family", n, title)
    # 해금
    for g, (key, what) in sorted(UNLOCKS.items()):
        need = int(math.ceil(len(data["gen_wild"].get(g, ())) * UNLOCK_PCT))
        title = "%s 개척자" % what if g == 7 else "%s 연구자" % what
        add(key, "해금", title,
            "%s 지방에서 평소 만날 수 있는 포켓몬 %d종 잡기 - %s 포켓몬이 풀숲에 "
            "나타나기 시작한다" % (REGION[g], need, what),
            "unlock_%d" % g, need, title)
    # 숨은 업적 (달성하기 전에는 이름만 가린다)
    add("hidden_midnight", "숨은 업적", "한밤의 만남", "자정(0시)에 포켓몬 잡기",
        "midnight", 1, "한밤의 만남", hidden=True)
    add("hidden_lux", "숨은 업적", "고급스러운 인연", "럭셔리볼로 전설의 포켓몬 잡기",
        "lux_legend", 1, "고급스러운 인연", hidden=True)
    add("hidden_twin", "숨은 업적", "쌍둥이 별", "같은 종 이로치 2마리 갖기",
        "twin_shiny", 1, "쌍둥이 별", hidden=True)
    add("hidden_nick", "숨은 업적", "똑같은 이름",
        "데리고 다니는 여섯 마리의 별명을 모두 같게 짓기",
        "same_nick", 1, "똑같은 이름", hidden=True)
    add("hidden_types", "숨은 업적", "타입 여행자", "18가지 타입을 모두 한 종 이상 잡기",
        "all_types", 18, "타입 여행자", hidden=True)
    return out


_defs_cache = {}


def defs():
    d = deps.dex()
    if _defs_cache.get("dex") is not d:
        _defs_cache.clear()
        _defs_cache["dex"] = d
        _defs_cache["list"] = _defs()
        _register_titles(_defs_cache["list"])
    return _defs_cache["list"]


def title_id(key):
    return "ach_%s" % key


def _register_titles(items):
    """업적 칭호를 season.TITLES 에 올린다. 칭호 창·랭킹·친구 목록이 그대로
    이름을 찾는다."""
    for a in items:
        if a["title"]:
            season.TITLES[title_id(a["key"])] = a["title"]


# ---------------------------------------------------------------- 세기
def _stat(uid, key):
    r = db.q1("SELECT n FROM user_stat WHERE user_id=? AND key=?", (uid, key))
    return int(r["n"]) if r else None


def _set_stat(uid, key, n):
    db.run("INSERT INTO user_stat (user_id, key, n) VALUES (?,?,?)"
           " ON CONFLICT(user_id, key) DO UPDATE SET n=excluded.n", (uid, key, int(n)))


def _add_stat(uid, key, by=1):
    db.run("INSERT INTO user_stat (user_id, key, n) VALUES (?,?,?)"
           " ON CONFLICT(user_id, key) DO UPDATE SET n=n+excluded.n", (uid, key, int(by)))


def _ensure_shiny(uid):
    """이로치 수를 처음 셀 때는 **지금 가진 이로치**로 시작한다.

    그동안 이로치를 따로 적어 두지 않았다. 놓아준 것은 셀 수 없다.
    """
    if _stat(uid, "shiny") is None:
        r = db.q1("SELECT COUNT(*) AS n FROM pokemon WHERE user_id=? AND shiny=1", (uid,))
        _set_stat(uid, "shiny", r["n"] if r else 0)


def progress(uid):
    """업적마다 세는 값. {stat: 지금 값}."""
    data = _data()
    d = data["dex"]
    caught = set(r["species"] for r in db.q(
        "SELECT species FROM seen WHERE user_id=? AND caught=1", (uid,)))
    out = {"dex": len(caught)}
    for g, target in data["region"].items():
        out["region_%d" % g] = len(caught & target)
    for t, members in data["types"].items():
        out["type_%s" % t] = len(caught & members)
    out["all_types"] = sum(1 for members in data["types"].values() if caught & members)
    leg = myth = 0
    for k in caught:
        s = d.by_internal.get(k)
        kind = L.kind_of(s["num"]) if s else None
        if kind == "legendary":
            leg += 1
        elif kind == "mythical":
            myth += 1
    out["legendary"], out["mythical"] = leg, myth
    out["family"] = sum(1 for f in data["families"] if f <= caught)
    for g in UNLOCKS:
        out["unlock_%d" % g] = len(caught & data["gen_wild"].get(g, set()))
    _ensure_shiny(uid)
    out["shiny"] = _stat(uid, "shiny") or 0
    out["midnight"] = _stat(uid, "midnight") or 0
    out["lux_legend"] = _stat(uid, "lux_legend") or 0
    twin = db.q1("SELECT COUNT(*) AS n FROM (SELECT species FROM pokemon"
                 " WHERE user_id=? AND shiny=1 GROUP BY species HAVING COUNT(*)>=2)",
                 (uid,))
    out["twin_shiny"] = 1 if twin and twin["n"] else 0
    party = db.q("SELECT nickname FROM pokemon WHERE user_id=? AND on_desktop=1", (uid,))
    nicks = [(r["nickname"] or "").strip() for r in party]
    out["same_nick"] = 1 if (len(nicks) >= config.MAX_PARTY and nicks[0]
                             and len(set(nicks)) == 1) else 0
    return out


# ---------------------------------------------------------------- 주기
def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


KST = datetime.timezone(datetime.timedelta(hours=9))


def _kst_hour(now=None):
    """한국 시각의 '시'. now(ISO 문자열)를 주면 그 시각으로 본다."""
    t = None
    if now:
        try:
            t = datetime.datetime.fromisoformat(str(now))
        except ValueError:
            t = None
    if t is None:
        t = datetime.datetime.now(datetime.timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return t.astimezone(KST).hour


def check(uid, now=None):
    """새로 달성한 업적을 적고 보상을 준다. 새로 받은 업적 목록."""
    items = defs()
    have = set(r["key"] for r in db.q(
        "SELECT key FROM achievement WHERE user_id=?", (uid,)))
    if len(have) >= len(items):
        return []
    prog = progress(uid)
    now = now or _now_iso()
    new = []
    for a in items:
        if a["key"] in have or prog.get(a["stat"], 0) < a["target"]:
            continue
        # **먼저 적고 그다음에 준다.** 두 요청이 겹쳐도 보상은 한 번이다.
        cur = db.run("INSERT INTO achievement (user_id, key, got_at, seen)"
                     " VALUES (?,?,?,0) ON CONFLICT(user_id, key) DO NOTHING",
                     (uid, a["key"], now))
        if getattr(cur, "rowcount", 1) == 0:
            continue
        if a["title"]:
            # 달고 있는 칭호를 멋대로 바꾸지 않는다 - 한꺼번에 여럿 달성되면
            # 어느 것이 달릴지 제멋대로다. 칭호 창에서 고른다.
            season.grant(uid, "title", title_id(a["key"]), 0,
                         equip_if_empty=False, now=now)
        if a["balls"]:
            db.run("UPDATE users SET balls=balls+? WHERE id=?", (a["balls"], uid))
        new.append(a)
    return new


def safe_check(uid, now=None):
    """check 와 같되 **실패해도 부른 쪽을 깨지 않는다.** 진화·별명·동기화처럼
    업적과 상관없는 일이 업적 때문에 실패하면 안 된다."""
    try:
        return check(uid, now)
    except Exception as e:                                   # noqa: BLE001
        from . import errors
        errors.record("ACH", "achievements.check", e)
        return []


def on_obtain(uid, mon, how, ball=None, now=None):
    """포켓몬을 얻었다 (catch / hatch / evolve / starter). 새 업적 목록.

    이로치 수와 숨은 업적(자정·럭셔리볼 전설)은 **얻는 순간에만** 알 수
    있어서 여기서 적는다. 나머지는 도감(seen)으로 센다.
    """
    if how == "catch":
        from . import guild                 # 길드 일일 미션 (1.10.0). 잡는 길은 다 여기를 지난다.
        guild.note_safe(uid, "catch")
    try:
        _ensure_shiny(uid)
        if mon.get("shiny") and how in ("catch", "hatch"):
            _add_stat(uid, "shiny")
        if how == "catch":
            if _kst_hour(now) == 0:
                _set_stat(uid, "midnight", 1)
            sp = deps.dex().get(mon.get("species")) or {}
            if ball == "LUXURYBALL" and sp.get("legendary"):
                _set_stat(uid, "lux_legend", 1)
        return check(uid, now)
    except Exception as e:                                   # noqa: BLE001
        # 업적 때문에 잡기가 실패하면 안 된다. 적어만 두고 넘어간다.
        from . import errors
        errors.record("ACH", "achievements.on_obtain", e)
        return []


# ---------------------------------------------------------------- 보여주기
def unseen(uid):
    rows = db.q("SELECT key FROM achievement WHERE user_id=? AND seen=0"
                " ORDER BY got_at, key", (uid,))
    by = dict((a["key"], a) for a in defs())
    return [_card(by[r["key"]]) for r in rows if r["key"] in by]


def me_card(uid):
    """/api/me 에 싣는다. 처음 보는 사람은 여기서 한 번 몰아서 센다.

    **여기서 터지면 동기화 전체가 멈춘다** - 실패하면 빈 것을 준다.
    """
    try:
        if _stat(uid, "ach_init") is None:
            check(uid)
            _set_stat(uid, "ach_init", 1)
        return {"unseen": unseen(uid)}
    except Exception as e:                                   # noqa: BLE001
        from . import errors
        errors.record("ACH", "achievements.me_card", e)
        return {"unseen": []}


def mark_seen(uid):
    db.run("UPDATE achievement SET seen=1 WHERE user_id=? AND seen=0", (uid,))


def _card(a, got_at=None, value=None):
    out = {"key": a["key"], "group": a["group"], "name": a["name"],
           "desc": a["desc"], "target": a["target"], "title": a["title"],
           "balls": a["balls"], "hidden": a["hidden"]}
    if got_at is not None:
        out["gotAt"] = got_at
    if value is not None:
        out["value"] = min(int(value), a["target"])
    return out


def public(uid):
    """업적 화면. 숨은 업적은 달성하기 전까지 이름·설명을 가린다."""
    check(uid)
    got = dict((r["key"], r["got_at"]) for r in db.q(
        "SELECT key, got_at FROM achievement WHERE user_id=?", (uid,)))
    prog = progress(uid)
    out = []
    for a in defs():
        c = _card(a, got.get(a["key"]), prog.get(a["stat"], 0))
        if a["hidden"] and a["key"] not in got:
            c["name"], c["desc"], c["title"] = "???", "숨은 업적", None
            c.pop("value", None)
        out.append(c)
    return {"achievements": out, "done": len(got), "total": len(out),
            "unlocks": dict(("unlock_%d" % g, UNLOCKS[g][0] in got) for g in UNLOCKS)}


# ---------------------------------------------------------------- 칭호 목록
# 남이 단 칭호를 보고 "저건 어떻게 얻나" 를 알 길이 없었다. 업적 칸은 업적을
# 보여 주지 칭호를 보여 주지 않고, 랭킹전 칭호는 어디에도 조건이 없었다.
# 도감 탭의 '칭호' 가 이걸 그린다 (1.8.1).
_SEAT_HOW = {"champion": "챔피언 자리(마스터볼 티어의 RP 1위)",
             "elite": "사천왕 자리(마스터볼 티어의 RP 2~5위)"}


def _season_titles():
    """랭킹전 칭호와 조건. (id, 묶음, 조건, 지금 얻을 수 있나)"""
    out = []
    tier_rp = dict((k, rp) for k, _n, rp in season.TIERS)
    now = season.SEASON

    def tier_rows(no, rewards):
        group = "랭킹전 시즌 %d" % no if no == now else "지난 시즌 (다시 얻을 수 없음)"
        for tier, title, _frame, _n, _egg in rewards:
            if tier in _SEAT_HOW:
                how = "시즌 %d 을 %s로 마치기" % (no, _SEAT_HOW[tier])
            else:
                how = ("시즌 %d 에서 %s 티어(RP %d)에 오르기 - 시즌이 끝날 때 받는다"
                       % (no, season.TIER_KR.get(tier, tier), tier_rp.get(tier, 0)))
            out.append((title, group, how, no == now))
    tier_rows(3, season.S3_REWARDS)
    tier_rows(2, season.S2_REWARDS)
    for lo, hi, title, _frame, _n, _egg in season.S1_REWARDS:
        rank = "%d위" % lo if lo == hi else "%d~%d위" % (lo, hi)
        out.append((title, "지난 시즌 (다시 얻을 수 없음)",
                    "시즌 1 을 %s로 마치기" % rank, False))
    return out


def titles(uid):
    """칭호 전부와 얻는 조건. 숨은 업적의 칭호는 얻기 전까지 가린다."""
    check(uid)
    own = set(r["rid"] for r in db.q(
        "SELECT rid FROM user_reward WHERE user_id=? AND kind='title'", (uid,)))
    prog = progress(uid)
    out = []
    for a in defs():
        if not a["title"]:
            continue
        tid = title_id(a["key"])
        mine = tid in own
        c = {"id": tid, "name": a["title"], "group": a["group"], "how": a["desc"],
             "owned": mine, "open": True}
        if a["hidden"] and not mine:
            c["name"], c["how"] = "???", "숨은 업적 - 달성하면 알 수 있다"
        elif not mine and a["target"] > 1:
            c["value"] = min(int(prog.get(a["stat"], 0)), a["target"])
            c["target"] = a["target"]
        out.append(c)
    for tid, group, how, is_open in _season_titles():
        out.append({"id": tid, "name": season.TITLES.get(tid, tid), "group": group,
                    "how": how, "owned": tid in own, "open": is_open})
    return {"titles": out, "owned": sum(1 for c in out if c["owned"]), "total": len(out),
            "season": season.SEASON, "seasonEnds": season.SEASON_ENDS}


def top(uid, n=3):
    """친구 프로필에 보일 대표 업적. 칭호가 있는 것 중 최근 것."""
    by = dict((a["key"], a) for a in defs())
    rows = db.q("SELECT key, got_at FROM achievement WHERE user_id=?"
                " ORDER BY got_at DESC, key LIMIT 50", (uid,))
    out = []
    for r in rows:
        a = by.get(r["key"])
        if a and a["title"]:
            out.append({"key": a["key"], "name": a["name"], "gotAt": r["got_at"]})
        if len(out) >= n:
            break
    return out


# ---------------------------------------------------------------- 해금 출현
def unlocked_pool(uid):
    """이 사람에게 풀숲에서 나올 수 있게 된 해금 종."""
    data = _data()
    got = set(r["key"] for r in db.q(
        "SELECT key FROM achievement WHERE user_id=? AND key IN (%s)"
        % ",".join("?" * len(UNLOCKS)), (uid,) + tuple(k for k, _w in UNLOCKS.values())))
    out = []
    for g, (key, _what) in UNLOCKS.items():
        if key in got:
            out.extend(data["unlock_pool"].get(g, []))
    return out


def unlock_mon(uid, rng):
    """풀숲에 해금 포켓몬을 숨길까. 아니면 None.

    쉐이미처럼 **야생 추첨을 안 거친다.** 야생 종족값 상한(330 + 레벨 x 8)에
    걸려서 파티 레벨이 낮은 사람에게는 영영 안 나오기 때문이다.
    """
    try:
        pool = unlocked_pool(uid)
        if not pool or rng.random() >= UNLOCK_CHANCE:
            return None
        sp = deps.dex().get(rng.choice(pool))
        if not sp:
            return None
        return P.make_pokemon(sp, UNLOCK_LEVEL, rng, shiny_rate=config.SHINY_RATE)
    except Exception as e:                                   # noqa: BLE001
        # 풀숲이 안 돋으면 게임이 멈춘 것처럼 보인다. 해금 종만 거른다.
        from . import errors
        errors.record("ACH", "achievements.unlock_mon", e)
        return None


def catch_species(sp):
    """포획 판정에 넘길 종 자료. 해금 종이면 포획률 하한을 둔다."""
    try:
        if not sp or sp.get("internal") not in _data()["unlock_all"]:
            return sp
    except Exception:                                        # noqa: BLE001
        return sp
    if (sp.get("catch") or 45) >= UNLOCK_CATCH_FLOOR:
        return sp
    out = dict(sp)
    out["catch"] = UNLOCK_CATCH_FLOOR
    return out
