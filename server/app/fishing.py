# -*- coding: utf-8 -*-
"""낚시 (시즌 7) 서버.

낚인 포켓몬은 따로 표를 두지 않고 지금 야생 표(wild)에 src='fish' 로 넣는다 - 배틀 · 볼 · 포획 경로를 그대로 쓴다.
야생이 끝나는 곳은 deps.end_wild 하나로 모였고, fish 면 풀숲 다음 시각을 건드리지 않는다.

## 한 판 (fish_state - 사람마다 한 줄)

    idle --cast--> cast --(입질 시각이 지나고 앱이 bite)--> bite --hook (쭉 안)--> hooked (wild 에 src='fish')
                                                            bite --hook 헛챔질 · 늦음--> idle
    reel: cast 면 미끼를 돌려주고 idle, bite 면 그냥 idle (미끼는 입질이 열릴 때 쓰였다).

hooked 는 낚인 야생이 사라지면(잡기 · 놓아주기 · 만료 · 배틀) **저절로 idle 로 읽힌다** (_state). 야생이 끝나는 열 곳이
이 표를 몰라도 되게 - 하나라도 되돌리기를 빠뜨리면 다시는 못 던지는 사람이 생긴다. 쭉 + 여유가 지난 bite 도 같다.

## 시각은 서버만 안다

입질 시각(bite_at)은 앱에 절대 안 준다 - 알려 주면 고친 앱이 '짧게 나올 때까지 던졌다 거두기' 를 한다. 카드는 ready
(이미 지났나)만 싣고, 지나면 알림(push_once, 소켓)을 한 번 보낸다. 콕콕 · 쭉 · 완벽 판정은 **요청이 닿은 서버 시각**.

## 한 사람에 야생은 늘 하나

풀숲 돋기(main.wild_state) · 입질 열기 · 챔질을 사람마다 잠금(user_lock) 안에서 한다 (uvicorn 한 프로세스).
입질이 다가오면(FISH_HOLD 초 안 ~ 지나서 FISH_HOLD_LATE 초까지) · 입질 중 · 낚인 야생이 있으면 풀숲이 미뤄지고(holds_grass), 반대로 야생이 있으면
입질이 안 열린다. 챔질은 `UPDATE … WHERE state='bite'` 가 1줄일 때만 야생을 넣는다 (잠금이 없어도 두 마리가 안 된다).

## 순위 · 정산

잡을 때(battle_routes.store_caught) fish_catch 한 줄 - 주는 **낚은 순간**의 주 (mon 의 fishWeek). 한 사람 한 줄 · 배율 >
그램 > 먼저 잡은 사람. 월 00:20 KST 뒤 지난주 1~30위에게 선물 (settle - 사람마다 '줬다' 를 먼저 적어 두 번 안 준다).

규칙 숫자 · 순수 계산은 common/fishing.py. 설계: design-notes/2026-11-26-fishing.md
"""
import datetime
import json
import threading
import time
import types

from common import fishing as F
from common import korean

from . import auth, config, db, deps, items, season, visit

UTC = datetime.timezone.utc
GRASS_RETRY = 60            # 풀숲을 미뤘으면 이만큼 뒤에 다시 본다 (main.wild_state)
SETTLE_AFTER = datetime.timedelta(minutes=20)   # 월 0시가 지나고 이만큼 뒤에 정산 - 일 23:59 에 낚은 것을 잡을 틈
TOP = 30                    # 순위 줄 수 (= 보상 받는 자리)
# 순위 보상 (첫 자리, 끝 자리, 도구, 개수). 낚시는 도구를 안 떨구므로 이 정도면 눈에 띈다 (설계).
REWARDS = ((1, 1, "BIGNUGGET", 1), (2, 3, "NUGGET", 2), (4, 10, "NUGGET", 1), (11, 30, "BIGPEARL", 1))
PUSH_EVERY = 5              # 입질 알림 스레드가 이만큼마다 본다 (초)


class Refused(Exception):
    """요청을 받을 수 없다 - 라우트가 그 상태 번호 · 글로 돌려준다."""

    def __init__(self, status, text):
        Exception.__init__(self, text)
        self.status = status
        self.text = text


def is_open():
    """열렸나. 시즌 번호를 그때그때 본다 (tower.is_open 과 같다)."""
    return season.SEASON >= config.FISH_FROM


def closed_text():
    return "낚시는 시즌 %d에 열립니다." % config.FISH_FROM


def grass_exclude():
    """풀숲 표(main._make_grass)에서 뺄 종. 열린 뒤에만 낚시 위주 종을 뺀다 - 열리기 전 풀숲은 지금 표 그대로."""
    return F.FISH_ONLY if is_open() else frozenset()


# ---------------------------------------------------------------- 시각 · 잠금
def _now():
    return datetime.datetime.now(UTC)


def iso(dt):
    """fish_state 의 시각 칸. 밀리초까지 늘 같은 길이라 글자로 견줘도 순서가 맞다 (push_once 의 bite_at<=?)."""
    return dt.astimezone(UTC).isoformat(timespec="milliseconds")


def _wild_iso(dt):
    """wild 표의 시각 꼴 (초까지 - main.iso(main.now()) 와 같다). 만료 견주기(_sweep)가 글자로 견준다."""
    return dt.astimezone(UTC).replace(microsecond=0).isoformat()


def _t(s):
    return auth.parse_iso(s) if s else None


def _left(s, now):
    return round(max(0.0, (_t(s) - now).total_seconds()), 2)


_locks = {}
_locks_guard = threading.Lock()


def user_lock(uid):
    """사람마다 잠금 하나 (풀숲 돋기 · 입질 열기 · 챔질 · 던지기 · 거두기). 다시 들어가지 않는다 - 안에서 또 잡지 말 것."""
    with _locks_guard:
        lk = _locks.get(uid)
        if lk is None:
            lk = _locks[uid] = threading.Lock()
        return lk


# ---------------------------------------------------------------- 상태 읽기
def _row(uid):
    return db.q1("SELECT * FROM fish_state WHERE user_id=?", (uid,))


def _live_wild(uid, now, src=None):
    """아직 만료되지 않은 야생 (아직 안 치운 만료 행은 없는 것으로 본다)."""
    sql, args = "SELECT * FROM wild WHERE user_id=? AND expires_at>=?", [uid, _wild_iso(now)]
    if src:
        sql += " AND src=?"
        args.append(src)
    return db.q1(sql + " ORDER BY id DESC LIMIT 1", tuple(args))


def _hooked_wild(uid, row, now):
    if not row or not row["wild_id"]:
        return None
    return db.q1("SELECT * FROM wild WHERE id=? AND user_id=? AND src='fish' AND expires_at>=?",
                 (row["wild_id"], uid, _wild_iso(now)))


def _state(row, now):
    """지금 읽히는 state. 쭉 + 여유가 지난 bite · 낚인 야생이 사라진 hooked 는 idle (머리말 - 따로 되돌리지 않는다)."""
    if row is None:
        return "idle"
    st = row["state"]
    if st == "bite" and now > _t(row["strike_end"]) + datetime.timedelta(seconds=config.FISH_GRACE):
        return "idle"
    if st == "hooked" and _hooked_wild(row["user_id"], row, now) is None:
        return "idle"
    return st


def _user(uid):
    return db.q1("SELECT * FROM users WHERE id=?", (uid,))


def card(uid, user_row=None, now=None):
    """낚시 카드 (GET /api/fish · /api/me 의 fish). 열리기 전이면 None. user_row 는 볼 목록(볼 수)에 쓴다."""
    if not is_open():
        return None
    now = now or _now()
    return _card(uid, _row(uid), now, user_row)


def _card(uid, row, now, user_row=None):
    st = _state(row, now)
    out = {"open": True, "state": st, "ready": False, "nibbleLeft": None, "strikeLeft": None,
           "bait": None, "baitLeft": 0, "wait": None, "wild": None, "ballOptions": None}
    if st in ("cast", "bite") and row["bait"]:
        out["bait"] = row["bait"]
        out["baitLeft"] = items.bag_count(uid, row["bait"])
    if st == "cast":
        # 지났나만 - 남은 초는 절대 안 준다 (머리말)
        out["ready"] = now >= _t(row["bite_at"])
        if out["ready"] and _live_wild(uid, now) is not None:
            out["wait"] = "wild"                 # 화면에 야생이 있어 못 연다 - 끝나면 앱이 다시 bite
    elif st == "bite":
        out["nibbleLeft"] = _left(row["nibble_end"], now)
        out["strikeLeft"] = _left(row["strike_end"], now)     # 서버 여유(FISH_GRACE)는 빼고 보낸다
    elif st == "hooked":
        # 재시작한 앱 · 풀숲을 꺼 둔 사람도 이것으로 낚인 야생을 되살린다
        from . import main                       # main 이 이 모듈을 부른다 - 쓸 때 늦게 (공개 모양 · 볼 목록)
        w = _hooked_wild(uid, row, now)
        out["wild"] = main._wild_public(w, True)
        out["ballOptions"] = main._ball_options(uid, user_row or _user(uid), w)
    return out


def holds_grass(uid, now=None):
    """풀숲을 미룰 때인가 - 입질이 FISH_HOLD 초 안으로 다가왔거나(지나서 FISH_HOLD_LATE 초 안 - 앱이 곧 열 것) · 입질 중 ·
    낚인 야생이 살아 있다. 풀숲과 낚인 포켓몬이 한꺼번에 둘이 되지 않게 (main.wild_state 가 잠금 안에서 부른다)."""
    if not is_open():
        return False
    now = now or _now()
    row = _row(uid)
    st = _state(row, now)
    # 지난 쪽에도 끝을 둔다. 연못을 숨겼거나 · 다른 PC 거나 · 앱을 꺼서 아무도 입질을 안 열면 cast 가 그대로 남는다 -
    # 끝이 없으면 그 사람 풀숲이 영영 안 돋는다. 창이 지나면 풀숲은 보통대로 돋고, 미뤄 둔 입질은 그 야생 뒤에서
    # 기다린다 (bite · 카드가 wait 'wild' 로 알린다 - 야생이 끝나면 앱이 다시 연다)
    if st == "cast" and -config.FISH_HOLD_LATE < (_t(row["bite_at"]) - now).total_seconds() < config.FISH_HOLD:
        return True
    if st == "bite":
        return True
    return _live_wild(uid, now, "fish") is not None


# ---------------------------------------------------------------- 던지기 · 입질 · 챔질 · 거두기
def is_bait(item_id):
    """미끼가 되나 - 지닌 열매만 (cat 'held' + 이름이 BERRY 로 끝남). 노력치 내리는 열매(cat 'ev')는 상점 80원이라 뺀다."""
    it = items.get(item_id)
    return bool(it) and it.get("cat") == "held" and str(it.get("id") or item_id).upper().endswith("BERRY")


def _idle(uid):
    db.run("UPDATE fish_state SET state='idle', nibble_end=NULL, strike_end=NULL, bait=NULL, warned=0, wild_id=NULL"
           " WHERE user_id=?", (uid,))


def cast(uid, bait=None, now=None):
    """찌를 던진다. 미끼는 여기서 가방에서 빼고, 입질 전에 거두면 돌려준다. 카드를 준다."""
    now = now or _now()
    bait = str(bait or "").strip().upper() or None
    if bait and not is_bait(bait):
        raise Refused(400, "미끼로는 지닌 열매만 달 수 있습니다.")
    with user_lock(uid):
        row = _row(uid)
        if _state(row, now) != "idle":
            raise Refused(409, "이미 찌를 던져 두었습니다.")
        n = db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (uid,))["c"]
        if n >= config.MAX_BOX:
            # 낚아도 넣을 자리가 없다 - 풀숲이 안 돋는 것과 같은 까닭 (main.wild_state 의 boxFull)
            raise Refused(409, "포켓몬이 %d마리로 가득 차서 낚시를 할 수 없습니다."
                               " 관리 창에서 놓아주거나 정리해 주세요." % config.MAX_BOX)
        if bait and not items.bag_take(uid, bait, 1):
            raise Refused(400, korean.natural("%s 이(가) 없습니다." % items.name_of(bait)))
        lo, hi = ((config.FISH_BAIT_MIN, config.FISH_BAIT_MAX) if bait
                  else (config.FISH_BITE_MIN, config.FISH_BITE_MAX))
        bite_at = now + datetime.timedelta(seconds=deps.RNG.uniform(lo, hi))
        db.run("INSERT INTO fish_state (user_id, state, cast_at, bite_at, bait) VALUES (?,'cast',?,?,?)"
               " ON CONFLICT(user_id) DO UPDATE SET state='cast', cast_at=excluded.cast_at,"
               " bite_at=excluded.bite_at, nibble_end=NULL, strike_end=NULL, bait=excluded.bait,"
               " pushed=0, warned=0, wild_id=NULL",
               (uid, iso(now), iso(bite_at), bait))
        return _card(uid, _row(uid), now)


def bite(uid, now=None):
    """앱이 '지금 보여 줄 수 있다' 며 입질을 연다. 아직이거나 야생이 있으면 그대로 (카드가 ready · wait 로 알린다)."""
    now = now or _now()
    with user_lock(uid):
        row = _row(uid)
        st = _state(row, now)
        if st == "bite":
            return _card(uid, row, now)          # 알림과 동기화가 겹쳐 두 번 와도 그대로 - 새로 굴리지 않는다
        if st != "cast":
            raise Refused(409, "던져 둔 찌가 없습니다.")
        if now < _t(row["bite_at"]) or _live_wild(uid, now) is not None:
            return _card(uid, row, now)
        nibble_end = now + datetime.timedelta(seconds=deps.RNG.uniform(config.FISH_NIBBLE_MIN, config.FISH_NIBBLE_MAX))
        strike_end = nibble_end + datetime.timedelta(seconds=config.FISH_STRIKE)
        db.run("UPDATE fish_state SET state='bite', nibble_end=?, strike_end=?, warned=0 WHERE user_id=? AND state='cast'",
               (iso(nibble_end), iso(strike_end), uid))
        return _card(uid, _row(uid), now)


def hook(uid, user_row=None, hour=None, now=None):
    """챔질. {"result": early|spooked|hooked|missed, "card"} + hooked 면 perfect · src · wild · ballOptions.

    early = 콕콕 중 첫 클릭 (경고만), spooked = 같은 콕콕의 두 번째 (idle), missed = 쭉 + 여유가 지남 (idle).
    종 · 크기는 여기서 굴린다 - 미리 굴려 두면 입질 전에 무엇이 걸렸는지 샐 길이 생긴다.
    """
    now = now or _now()
    with user_lock(uid):
        row = _row(uid)
        if row is None or row["state"] != "bite":
            raise Refused(409, "지금은 챔질할 때가 아닙니다.")
        nibble_end, strike_end = _t(row["nibble_end"]), _t(row["strike_end"])
        if now < nibble_end:
            if not row["warned"]:
                db.run("UPDATE fish_state SET warned=1 WHERE user_id=? AND state='bite'", (uid,))
                return {"result": "early", "card": _card(uid, _row(uid), now)}
            _idle(uid)
            return {"result": "spooked", "card": _card(uid, _row(uid), now)}
        if now > strike_end + datetime.timedelta(seconds=config.FISH_GRACE):
            _idle(uid)
            return {"result": "missed", "card": _card(uid, _row(uid), now)}
        perfect = now <= nibble_end + datetime.timedelta(seconds=config.FISH_PERFECT)

        from . import main                       # 레벨 · 공개 모양 · 볼 목록은 풀숲과 같은 것을 쓴다
        lo, hi, cap = main._wild_levels(uid)
        d = deps.dex()
        mon = d.roll_fish(lo, hi, deps.RNG, max_bst=cap, shiny_rate=config.SHINY_RATE)
        if mon is None:                          # 그 레벨에 물 타입이 하나도 없다 (도감이 비지 않는 한 안 일어난다)
            _idle(uid)
            return {"result": "missed", "card": _card(uid, _row(uid), now)}
        ratio = F.roll_ratio(deps.RNG, F.big_chance(bait=bool(row["bait"]), perfect=perfect))
        sp = d.get(mon["species"]) or {}
        # 잡는 길(볼 · 배틀 중 볼)까지 야생 자료에 실려 간다 - store_caught 가 이것으로 기록 · pokemon.fish_* 를 적는다
        mon.update({"fishG": F.grams(sp.get("kg") or 0, ratio), "fishRatio": ratio, "fishSpecies": mon["species"],
                    "fishWeek": F.week_key(now), "fishBadge": F.badge(ratio)})
        cur = db.run("UPDATE fish_state SET state='hooked', wild_id=NULL WHERE user_id=? AND state='bite'", (uid,))
        if getattr(cur, "rowcount", 0) != 1:
            raise Refused(409, "지금은 챔질할 때가 아닙니다.")     # 다른 요청이 먼저 챘다 - 야생은 그쪽 한 마리
        t0 = now.replace(microsecond=0)
        wid = db.run("INSERT INTO wild (user_id, state, species, data, throws, created_at, expires_at, src)"
                     " VALUES (?,'revealed',?,?,0,?,?,'fish')",
                     (uid, mon["species"], json.dumps(mon), _wild_iso(t0),
                      _wild_iso(t0 + datetime.timedelta(seconds=config.WILD_TTL)))).lastrowid
        db.run("UPDATE fish_state SET wild_id=? WHERE user_id=?", (wid, uid))
        # 만난 수는 챔질 때 센다 (풀숲은 돋을 때). 도감엔 '봤다' - 드러낸 풀숲(wild_reveal)과 같다
        db.run("INSERT INTO wild_state (user_id, encounters) VALUES (?,1)"
               " ON CONFLICT(user_id) DO UPDATE SET encounters=encounters+1", (uid,))
        items.mark_seen(uid, mon["species"], False, auth.now_iso())
        w = db.q1("SELECT * FROM wild WHERE id=?", (wid,))
        user_row = user_row or _user(uid)
        when = types.SimpleNamespace(hour=hour) if isinstance(hour, int) and 0 <= hour <= 23 else None
        return {"result": "hooked", "perfect": perfect, "src": "fish",
                "wild": main._wild_public(w, True),
                "ballOptions": main._ball_options(uid, user_row, w, when),
                "card": _card(uid, _row(uid), now, user_row)}


def reel(uid, now=None):
    """줄을 거둔다. 입질 전(cast)이면 미끼를 돌려준다 - 입질이 열리면 쓰인 것. 거둘 게 없으면 카드만."""
    now = now or _now()
    with user_lock(uid):
        row = _row(uid)
        st = _state(row, now)
        if st == "cast":
            cur = db.run("UPDATE fish_state SET state='idle', bait=NULL, warned=0, wild_id=NULL"
                         " WHERE user_id=? AND state='cast'", (uid,))
            if row["bait"] and getattr(cur, "rowcount", 0) == 1:
                items.bag_add(uid, row["bait"], 1)
        elif st == "bite":
            _idle(uid)
        return _card(uid, _row(uid), now)


# ---------------------------------------------------------------- 기록 · 순위
def record(uid, mon, pid, now=None):
    """잡은 낚시 포켓몬 한 줄 (battle_routes.store_caught - 잡는 길 둘이 다 거기를 지난다). 주는 낚은 순간의 주."""
    now = now or _now()
    db.run("INSERT INTO fish_catch (user_id, week, species, g, ratio, shiny, pokemon_id, at) VALUES (?,?,?,?,?,?,?,?)",
           (uid, mon.get("fishWeek") or F.week_key(now), mon.get("fishSpecies") or mon["species"],
            int(mon["fishG"]), float(mon.get("fishRatio") or 0), int(bool(mon.get("shiny"))), pid, _wild_iso(now)))


def _prev(week):
    return (datetime.date.fromisoformat(week) - datetime.timedelta(days=7)).isoformat()


def _ranked(week):
    """그 주 순위 - 한 사람 한 줄 (그 사람의 가장 큰 것). 배율 > 그램 > 먼저 잡은 사람."""
    out, seen = [], set()
    for r in db.q("SELECT * FROM fish_catch WHERE week=? ORDER BY ratio DESC, g DESC, at ASC, id ASC", (week,)):
        if r["user_id"] in seen:
            continue
        seen.add(r["user_id"])
        out.append(r)
    return out


def _names(uids):
    uids = sorted(set(uids))
    if not uids:
        return {}
    return dict((r["id"], r["username"]) for r in db.q(
        "SELECT id, username FROM users WHERE id IN (%s)" % ",".join("?" * len(uids)), tuple(uids)))


def _line(r, d, rank=None, names=None):
    sp = d.get(r["species"]) or {}
    out = {"species": r["species"], "num": sp.get("num"), "kr": d.name(r["species"]),
           "g": r["g"], "ratio": r["ratio"], "at": r["at"]}
    if rank is not None:
        out = dict({"rank": rank, "name": (names or {}).get(r["user_id"]), "shiny": bool(r["shiny"])}, **out)
    return out


def board(uid, which="this", now=None):
    """주간 대물 순위 (GET /api/fish/board). which = this | last."""
    now = now or _now()
    week = F.week_key(now)
    if which == "last":
        week = _prev(week)
    start = F.week_start_utc(week)
    ranked = _ranked(week)
    podium = _ranked(_prev(week))[:3]
    mine_at = next((i for i, r in enumerate(ranked) if r["user_id"] == uid), None)
    names = _names([r["user_id"] for r in ranked[:TOP] + podium]
                   + ([uid] if mine_at is not None else []))
    d = deps.dex()
    best, seen = [], set()
    for r in db.q("SELECT * FROM fish_catch WHERE user_id=? ORDER BY ratio DESC, g DESC, at ASC, id ASC", (uid,)):
        if r["species"] not in seen:
            seen.add(r["species"])
            best.append(_line(r, d))
    return {"week": week, "weekStart": start.isoformat(),
            "endsIn": max(0, int((start + datetime.timedelta(days=7) - now).total_seconds())),
            "top": [_line(r, d, i + 1, names) for i, r in enumerate(ranked[:TOP])],
            "me": _line(ranked[mine_at], d, mine_at + 1, names) if mine_at is not None else None,
            "last": [_line(r, d, i + 1, names) for i, r in enumerate(podium)],
            "mine": best}


# ---------------------------------------------------------------- 정산
_settle_lock = threading.Lock()


def _reward(rank):
    for lo, hi, item, n in REWARDS:
        if lo <= rank <= hi:
            return item, n
    return None, 0


def _mark(key, value):
    """meta 에 표시. 이미 있으면 False (누가 먼저 했다) - guild_war._mark 와 같다."""
    cur = db.run("INSERT INTO meta (k, v) VALUES (?,?) ON CONFLICT(k) DO NOTHING", (key, value))
    return getattr(cur, "rowcount", 1) > 0


def settle(now=None):
    """지난주 순위 보상을 선물함으로. 월 00:20 KST 전이면 0. 몇 번을 불러도 한 사람에 한 번 - 준 사람 수.

    한 시간마다 도는 집안일(housekeep)과 순위 창 요청이 부른다. 사람마다 '줬다' 를 **먼저** 적고 선물을 넣는다
    (도중에 끊겨 다시 돌아도 두 번 안 준다), 다 주면 '정산 끝' 을 적어 다음부터는 한 번만 묻고 끝난다.
    """
    if not is_open():
        return 0
    now = now or _now()
    this = F.week_key(now)
    if now < F.week_start_utc(this) + SETTLE_AFTER:
        return 0
    week = _prev(this)
    done = "fish:settled:%s" % week
    at = _wild_iso(now)
    with _settle_lock:
        if db.q1("SELECT 1 FROM meta WHERE k=?", (done,)) is not None:
            return 0
        d0 = datetime.date.fromisoformat(week)
        span = "%d/%d~%d/%d" % (d0.month, d0.day, (d0 + datetime.timedelta(days=6)).month,
                                (d0 + datetime.timedelta(days=6)).day)
        paid = 0
        for i, r in enumerate(_ranked(week)[:TOP]):
            item, n = _reward(i + 1)
            if not item or not _mark("fish:paid:%s:%d" % (week, r["user_id"]), at):
                continue
            msg = korean.natural("낚시 대물 순위 (%s) %d위 - 표준의 %.2f배 %s. %s %d개를 드립니다."
                                 % (span, i + 1, r["ratio"], deps.dex().name(r["species"]), items.name_of(item), n))
            db.run("INSERT INTO gift (user_id, kind, item_id, count, title, message, created_at) VALUES (?,?,?,?,?,?,?)",
                   (r["user_id"], "item", item, n, "낚시 대물 순위 보상", msg, at))
            paid += 1
        _mark(done, at)
    if paid:
        print("[fishing] %s 주 순위 보상 %d명" % (week, paid))
    return paid


# ---------------------------------------------------------------- 입질 준비 알림
def push_once(now=None):
    """입질 시각이 지난 cast 에 '입질 준비' 를 한 번 밀어 보낸다 (/ws/visit). 보낸 수.

    못 받은 앱(소켓이 끊겼다)은 90초 동기화 카드의 ready 로 안다 - 그래서 보냈는지 못 받았는지 따지지 않는다."""
    if not is_open():
        return 0
    now = now or _now()
    n = 0
    for r in db.q("SELECT user_id FROM fish_state WHERE state='cast' AND pushed=0 AND bite_at<=?", (iso(now),)):
        cur = db.run("UPDATE fish_state SET pushed=1 WHERE user_id=? AND state='cast' AND pushed=0", (r["user_id"],))
        if getattr(cur, "rowcount", 0) != 1:
            continue
        visit.push(r["user_id"], {"t": "fish", "s": "ready"})
        n += 1
    return n


_pusher_started = False


def _push_loop():
    while True:
        time.sleep(PUSH_EVERY)
        try:
            push_once()
        except Exception as e:                              # noqa: BLE001
            print("[fishing] 입질 알림 실패: %r" % (e,))


def start_pusher():
    """서버가 뜰 때 한 번 (main._startup). 5초마다 도는 배경 스레드 (자기 DB 커넥션을 쓴다)."""
    global _pusher_started
    if _pusher_started or not config.FISH_PUSH:
        return
    _pusher_started = True
    threading.Thread(target=_push_loop, name="fish-push", daemon=True).start()
