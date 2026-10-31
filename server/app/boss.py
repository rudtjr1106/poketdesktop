# -*- coding: utf-8 -*-
"""악당 출현 (시즌 4) — 관장 탭에 하루 한 번 나타나는 악당 조직과, 그 뒤의 전설.

## 얼개

**하루에 한 번, 한 곳.** 한국 시각 09:00~12:00 사이의 어느 때에 악당 조직 하나가 시·도 한 곳에
나타나 그날 밤 11시까지 머문다 (2026-10-15 사용자 결정). **시즌이 시작한 날부터 2주 동안만** 나온다
(EVENT_DAYS - 길드전과 같은 2주). 언제·어디에·누가 나오는지는 **날짜로 정해진다** (plan) - 서버가
따로 돌리는 시계도, 적어 두는 표도 없다. 그 시각이 되기 전에는 아무것도 알려 주지 않는다.
밤 11시 전에 시작한 판은 그 뒤에 끝나도 그날 것으로 센다 (region 에 날짜가 적혀 있다).

**사람마다 따로 싸운다** (boss_run). 간부 셋을 차례로 이기면 전설의 포켓몬과 마주친다. **그 전설은
사람마다 다르다** (legend_of - 도감의 전설 중 날짜와 사람으로 정해진다, 2026-10-17 사용자 결정, **10/18 부터**.
그전에는 조직마다 정해 둔 전설 중 날짜로 하나여서 그날은 모두 같았다 - 10/17 은 모두 미라이돈).

    간부   마릿수 = 내 파티 수, 레벨 = 내 파티 레벨(높은 순으로 맞춘다), 개체값 전부 31.
           종·기술·특성·도구·노력치는 관장 자료(gyms.json)의 그 트레이너 것 그대로.
           지면 그 간부부터 다시 도전한다. 이긴 상금은 관장 재도전 상금과 같은 식.
    전설   한 마리 (사람마다 다르다). 레벨 = 내 파티의 가장 높은 레벨, 개체값 31. **볼은 못 던진다.**
           이길 때까지 다시 도전할 수 있고, 쓰러뜨리면 그날 한 번 70% 로 그 전설의 알.

배틀 자체는 관장 배틀과 **같은 판**이다 (common/trainer_battle, gym_battle 표, 같은 창).
gym_battle.region 에 "boss:날짜:자리" 를 적어 두고, 끝났을 때 gym_routes.act 가 이쪽(on_win)
으로 넘긴다. 자리 0~2 는 간부, 3 은 전설.
"""
import datetime
import hashlib
import json
import random

from common import pokelogic as P
from common import trainer_battle as TB

from . import config, db, deps, eggs, gym, items, season

KST = datetime.timezone(datetime.timedelta(hours=9))
START_HOUR, LAST_HOUR = 9, 12           # 이 사이의 어느 때에 나타난다 (한국 시각)
LEAVE_HOUR = 23                         # 그날 밤 11시에 떠난다 (전설을 쓰러뜨린 사람에게는 그 전에 사라진다)
EVENT_DAYS = 14                         # 시즌이 시작한 날부터 이만큼만 나온다
EVENT_SEASONS = (4,)                    # 나오는 시즌 (2026-10-31 사용자 결정 '시즌 5 엔 끄기')
EGG_RATE = 0.70                         # 전설을 쓰러뜨렸을 때 알이 나올 확률
ADMINS = 3
LEGEND_STAGE = ADMINS                   # region 의 자리 번호: 0~2 간부, 3 전설
PREFIX = "boss:"

_TABLE = None
_SIDO = None


def table():
    global _TABLE
    if _TABLE is None:
        with open(config.VILLAINS_PATH, encoding="utf-8") as f:
            _TABLE = json.load(f)
    return _TABLE


def sidos():
    """시·도 코드 -> 이름. 관장이 있는 곳만 (지도에 그릴 수 있는 곳)."""
    global _SIDO
    if _SIDO is None:
        with open(config.KOREA_MAP_PATH, encoding="utf-8") as f:
            names = dict((s["code"], s["name"]) for s in json.load(f)["sido"])
        codes = sorted(set(code[:2] for code in gym.gyms()["regions"]))
        _SIDO = dict((c, names.get(c, c)) for c in codes)
    return _SIDO


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def day_of(now=None):
    return (now or _now()).astimezone(KST).date().isoformat()


def _h(day, salt):
    return int(hashlib.sha256(("boss:%s:%s" % (day, salt)).encode("utf-8")).hexdigest()[:12], 16)


def plan(day):
    """그날의 출현. 날짜만으로 정해진다 - 같은 날은 언제 물어도 같다."""
    teams = table()["teams"]
    team = teams[_h(day, "team") % len(teams)]
    codes = sorted(sidos())
    rng = random.Random(_h(day, "members"))
    pool = list(team["pool"])
    rng.shuffle(pool)
    members = pool[:ADMINS - 1] + [team["boss"]] if team.get("boss") else pool[:ADMINS]
    span = (LAST_HOUR - START_HOUR) * 60
    return {
        "day": day, "team": team, "sido": codes[_h(day, "sido") % len(codes)],
        "minute": _h(day, "minute") % span,            # START_HOUR 부터 몇 분 뒤에 나타나나
        "members": members,
    }


PER_USER_FROM = "2026-10-18"     # 이날부터 사람마다 (사용자: "내일부터 적용되도록 (오늘은 미라이돈)")


def team_legend(day):
    """조직마다 정해 둔 전설 중 날짜로 하나 - 그날은 모두 같다 (PER_USER_FROM 전까지의 규칙)."""
    legends = plan(day)["team"]["legends"]
    return legends[_h(day, "legend") % len(legends)]


def legend_of(day, uid):
    """그날 그 사람이 만나는 전설 (2026-10-17 사용자 결정: 사람마다 따로, 도감의 모든 전설 중에서).

    날짜와 사람으로 정해진다 - 같은 날 같은 사람은 언제 물어도 같고, 다음 날이면 다시 뽑는다.
    목록은 알 목록(eggs.pool)과 같다 - 본가 분류의 전설(환상·울트라비스트·패러독스·이벤트 포켓몬은
    빠진다)이라, 70% 로 받는 알도 그 종이다.
    """
    if day < PER_USER_FROM:
        return team_legend(day)                     # 10/17 은 예전처럼 모두 같다 (이미 싸운 사람이 있다)
    pool = eggs.pool("legendary")
    return pool[_h(day, "legend:%s" % uid) % len(pool)]


def appears_at(day):
    """그날 나타나는 시각 (한국 시각)."""
    y, m, d = (int(x) for x in day.split("-"))
    base = datetime.datetime(y, m, d, START_HOUR, 0, tzinfo=KST)
    return base + datetime.timedelta(minutes=plan(day)["minute"])


def leaves_at(day):
    """그날 떠나는 시각 (한국 시각 밤 11시)."""
    y, m, d = (int(x) for x in day.split("-"))
    return datetime.datetime(y, m, d, LEAVE_HOUR, 0, tzinfo=KST)


def in_event(day):
    """이날이 악당이 나오는 2주 안인가 (시즌이 시작한 날부터 EVENT_DAYS 일). EVENT_SEASONS 밖의 시즌에는 안 나온다."""
    if season.SEASON not in EVENT_SEASONS:
        return False
    first = datetime.date.fromisoformat(season.SEASON_STARTS)
    return first <= datetime.date.fromisoformat(day) < first + datetime.timedelta(days=EVENT_DAYS)


def active(now=None):
    """지금 나타나 있으면 그날의 출현(plan). 아직 안 나왔거나 떠났거나 기간이 아니면 None."""
    now = now or _now()
    day = day_of(now)
    if not in_event(day):
        return None
    return plan(day) if appears_at(day) <= now < leaves_at(day) else None


def ends_in(now=None):
    """밤 11시(악당이 떠나는 때)까지 남은 초."""
    k = (now or _now()).astimezone(KST)
    return max(0, int(LEAVE_HOUR * 3600 - (k.hour * 3600 + k.minute * 60 + k.second)))


# ---------------------------------------------------------------- 진행
def run(uid, day):
    """그날 그 사람의 진행. 줄이 없으면 처음이다."""
    r = db.q1("SELECT * FROM boss_run WHERE user_id=? AND day=?", (uid, day))
    return {"stage": r["stage"] if r else 0, "legend": bool(r["legend"]) if r else False,
            "egg": (r["egg"] if r else None), "paid": r["paid"] if r else 0}


def _ensure(uid, day):
    """그날의 줄을 만들어 둔다 (있으면 그대로). 아래의 조건 건 UPDATE 가 이 줄을 고친다."""
    db.run("INSERT INTO boss_run (user_id, day, stage, legend, egg, paid, updated_at)"
           " VALUES (?,?,0,0,NULL,0,?) ON CONFLICT(user_id, day) DO NOTHING",
           (uid, day, _now().replace(microsecond=0).isoformat()))


def region_of(day, stage):
    return "%s%s:%d" % (PREFIX, day, stage)


def is_boss(region):
    return str(region or "").startswith(PREFIX)


def parse(region):
    """"boss:2026-10-17:2" -> ("2026-10-17", 2). 아니면 None."""
    if not is_boss(region):
        return None
    try:
        _p, day, stage = region.split(":")
        return day, int(stage)
    except ValueError:
        return None


# ---------------------------------------------------------------- 상대 만들기
def _levels(party):
    """내 파티의 레벨, 높은 순."""
    return sorted((int(m.get("level") or 1) for m in party), reverse=True)


def admin_trainer(tid, party):
    """간부 한 명을 내 파티에 맞춘 것 (TrainerBattle 이 먹는 꼴).

    전설·환상은 뺀다 - 보스들의 자료에는 뮤츠·그란돈이 들어 있는데, 그건 다 이긴 뒤에 만난다.
    """
    t = gym.trainer(tid)
    if not t:
        raise LookupError("그런 트레이너가 없습니다.")
    d = deps.dex()
    levels = _levels(party)
    team = [m for m in t["team"]
            if not (d.get(m["species"]) or {}).get("legendary")
            and not (d.get(m["species"]) or {}).get("mythical")]
    out = []
    for i, m in enumerate(team[:len(levels)]):
        e = dict(m)
        e["level"] = levels[i]
        e["iv"] = P.IV_MAX
        out.append(e)
    return {"id": t["id"], "name": t["name"], "role": t["role"], "sprite": t["sprite"],
            "battleSprite": t.get("battleSprite"), "level": levels[0] if levels else 1, "team": out,
            # 높은 관장은 한 마리에게 메가스톤을 쥐여 주는데(trainer_battle.give_mega_stone),
            # 악당은 안 받는다 - 도구가 자료 그대로여야 한다.
            "noMega": True}


def legend_trainer(species, party):
    """전설 한 마리. 트레이너가 없는 판이라 이름·역할 칸에 포켓몬을 적는다."""
    d = deps.dex()
    sp = d.get(species)
    if not sp:
        raise LookupError("그런 포켓몬이 없습니다.")
    level = max(_levels(party) or [1])
    abil = (sp.get("abil") or [None])[0]
    return {"id": "legend:" + species, "name": sp["kr"], "role": "전설의 포켓몬", "sprite": None,
            "level": level, "wild": True,
            "team": [{"species": species, "level": level, "iv": P.IV_MAX, "evs": {},
                      "nature": "HARDY", "ability": abil, "moves": P.default_moveset(sp, level),
                      "held": None, "gender": "N"}]}


# ---------------------------------------------------------------- 보여주기
def brief(uid, now=None):
    """관장 탭의 개요에 싣는다. 지도를 검게 칠할 곳과, 내가 어디까지 했나.

    안 나와 있으면 event 만 싣는다 - 오늘이 악당이 나오는 기간인가. 언제 나오는지는 여전히 안 알려 주고,
    관장 탭은 그 기간이면 09:00~12:00 동안 몇 분마다 다시 물어본다 (ui_gym.boss_watch_in).
    """
    p = active(now)
    if not p:
        return {"active": False, "event": in_event(day_of(now))}
    r = run(uid, p["day"])
    return {"active": True, "day": p["day"], "sido": p["sido"], "sidoName": sidos().get(p["sido"]),
            "team": p["team"]["name"], "stage": r["stage"], "legend": r["legend"],
            "done": bool(r["legend"]), "endsIn": ends_in(now)}


def card(uid, now=None):
    """악당 창에 그릴 것 전부."""
    p = active(now)
    if not p:
        return {"active": False}
    d = deps.dex()
    r = run(uid, p["day"])
    members = []
    for i, tid in enumerate(p["members"]):
        t = gym.trainer(tid) or {}
        members.append({"id": tid, "name": t.get("name"), "role": t.get("role"),
                        "sprite": t.get("sprite"),
                        "state": "won" if i < r["stage"] else ("next" if i == r["stage"] else "locked")})
    species = legend_of(p["day"], uid)
    sp = d.get(species) or {}
    open_ = r["stage"] >= ADMINS
    legend = {"open": open_, "done": r["legend"], "egg": r["egg"]}
    if open_:                               # 간부를 다 이기기 전에는 누구인지 안 알려 준다
        legend.update({"species": species, "name": sp.get("kr"), "num": sp.get("num"),
                       "types": [d.type_name(t) for t in sp.get("types") or []]})
    act = db.q1("SELECT id, region FROM gym_battle WHERE user_id=? AND state='active'"
                " ORDER BY id DESC LIMIT 1", (uid,))
    return {"active": True, "day": p["day"], "sido": p["sido"], "sidoName": sidos().get(p["sido"]),
            "team": p["team"]["name"], "teamId": p["team"]["id"], "members": members,
            "legend": legend, "stage": r["stage"], "done": r["legend"], "endsIn": ends_in(now),
            "eggRate": int(round(EGG_RATE * 100)),
            "battle": ({"id": act["id"]} if act and is_boss(act["region"]) else None)}


# ---------------------------------------------------------------- 싸우기
def next_fight(uid, party, now=None):
    """지금 싸울 상대. (region, trainer id, TrainerBattle 이 먹는 트레이너)"""
    p = active(now)
    if not p:
        raise LookupError("지금은 악당이 나타나 있지 않습니다.")
    r = run(uid, p["day"])
    if r["legend"]:
        raise ValueError("오늘의 악당은 이미 물리쳤습니다.")
    if r["stage"] < ADMINS:
        tid = p["members"][r["stage"]]
        return region_of(p["day"], r["stage"]), tid, admin_trainer(tid, party)
    t = legend_trainer(legend_of(p["day"], uid), party)
    return region_of(p["day"], LEGEND_STAGE), t["id"], t


def rebuild(region, trainer_id, party):
    """진행 중이던 판의 트레이너를 다시 만든다 (이름표가 필요한 곳이 쓴다)."""
    got = parse(region)
    if not got:
        return None
    if got[1] >= LEGEND_STAGE:
        return legend_trainer(str(trainer_id).split(":", 1)[-1], party)
    return admin_trainer(trainer_id, party)


def on_win(uid, region, trainer_id, level, rng=None, now=None):
    """이긴 뒤. 진행을 올리고 상금·알을 준다. 화면에 띄울 것을 돌려준다 ({"lines": [...]}).

    **같은 자리를 두 번 이겨도 한 번만 센다** - 진행이 이미 그 뒤로 가 있으면 아무것도 안 준다
    (창 두 개로 같은 판을 끝내는 일은 gym_battle 의 rev 가 막지만, 여기서도 한 번 더 본다).
    """
    got = parse(region)
    if not got:
        return None
    day, stage = got
    rng = rng or random.SystemRandom()
    stamp = _now().replace(microsecond=0).isoformat()
    _ensure(uid, day)
    lines = []
    # **진행은 조건을 건 UPDATE 한 문장으로 올린다.** 읽어 보고 쓰면, 같은 자리의 판 둘을 같은
    # 순간에 끝냈을 때 둘 다 '아직 안 이겼다' 로 읽고 상금·알을 두 번 받는다. 한 줄이 바뀌었을
    # 때만 준다.
    if stage < ADMINS:
        prize = int(level) * config.GYM_REPEAT_PER_LEVEL
        cur = db.run("UPDATE boss_run SET stage=stage+1, paid=paid+?, updated_at=?"
                     " WHERE user_id=? AND day=? AND stage=?", (prize, stamp, uid, day, stage))
        if getattr(cur, "rowcount", 1) == 0:
            return {"lines": ["이미 이긴 상대다."], "boss": True}
        items.money_add(uid, prize)
        lines.append("상금 %s원" % format(prize, ","))
        left = ADMINS - (stage + 1)
        lines.append("간부가 %d명 남았다." % left if left
                     else "악당을 모두 물리쳤다! 전설의 포켓몬이 모습을 드러낸다...")
        return {"lines": lines, "boss": True, "prize": prize, "money": items.money(uid),
                "stage": stage + 1}
    cur = db.run("UPDATE boss_run SET legend=1, updated_at=? WHERE user_id=? AND day=?"
                 " AND legend=0 AND stage>=?", (stamp, uid, day, ADMINS))
    if getattr(cur, "rowcount", 1) == 0:
        return {"lines": ["이미 끝난 승부다."], "boss": True}
    species = str(trainer_id).split(":", 1)[-1]
    d = deps.dex()
    name = (d.get(species) or {}).get("kr") or species
    egg = 0
    if rng.random() < EGG_RATE:
        try:
            eggs.give(uid, "legendary", species=species)
            egg = 1
        except Exception as e:                                # noqa: BLE001
            from . import errors
            errors.record("BOSS", "boss.on_win egg", e)
    db.run("UPDATE boss_run SET egg=? WHERE user_id=? AND day=?", (egg, uid, day))
    if egg:
        lines.append("%s 이(가) 알을 남기고 사라졌다! 전설의 포켓몬 알을 얻었다." % name)
        lines.append("알은 바탕화면에 나타나고, 게임을 켜 둔 시간만큼 자라서 부화한다.")
    else:
        lines.append("%s 은(는) 아무것도 남기지 않고 사라졌다..." % name)
        lines.append("내일 또 악당이 나타난다.")
    return {"lines": lines, "boss": True, "egg": bool(egg), "species": species, "legend": True}


def start(uid, party, zring=False, keystone=False, rng=None, now=None):
    """새 판을 만든다. (region, trainer id, TrainerBattle, 시작 이벤트)"""
    region, tid, trainer = next_fight(uid, party, now)
    if not trainer["team"]:
        raise ValueError("상대가 내보낼 포켓몬이 없습니다.")
    tb = TB.TrainerBattle(deps.dex(), party, trainer, rng or random.Random())
    tb.keystone["me"] = keystone
    tb.zring["me"] = zring                             # 악당 쪽은 Z기술을 쓰지 않는다
    return region, tid, tb, tb.start()
