# -*- coding: utf-8 -*-
"""풀숲 부스트 (2.1.1): 타입 스프레이 · 버닝 부스터.

사람마다 '언제까지' 를 wild_state 칸에 둔다 (따로 표를 두지 않는다 - /api/wild · /api/me 가 이미 그 줄을 읽는다).

    버닝 부스터    burn_until               이때까지 풀숲 간격이 BURN_MIN~BURN_MAX 초 (보통 5~7분 -> 2~3분)
    타입 스프레이  lure_type · lure_until   이때까지 풀숲 LURE_SHARE 몫은 그 타입 종에서만 뽑는다 (roll_boost)

한 번 쓰면 도구에 적힌 분(1시간)만큼 켜진다. 켜져 있을 때 또 쓰면 남은 시간에 더한다 - 다만 남은 시간이
MAX_LEFT_MIN(3시간)을 넘게는 안 쌓인다 (넘으면 쓰기 전에 거절 - 도구가 헛되이 사라지지 않게). 스프레이는 같은
타입이면 더하고, **다른 타입이면 새 타입으로 바꾸고 지금부터 다시 센다** (화면이 먼저 묻는다).

풀숲 간격을 정하는 곳은 둘이었다 (main._cooldown · battle_routes.reschedule) - 둘 다 cooldown() 을 부른다.
"""
import datetime

from . import auth, config, db

BURN_MIN, BURN_MAX = 120, 180         # 버닝 중 풀숲 간격 (초)
# 스프레이: 풀숲 둘에 하나는 고른 타입 종에서만 뽑고, 나머지는 평소대로 (거기서도 그 타입이 나올 수 있다).
# 가중치 배수로 하면 드문 타입일수록 약했다 - x8 로 얼음 4% -> 21%, 드래곤 2% -> 14%. 이렇게 하면 어느 타입이든
# 절반 남짓 (평소 몫 2~18% 의 절반이 더해져 51~59%).
LURE_SHARE = 0.5
MAX_LEFT_MIN = 180                    # 쌓아 둘 수 있는 남은 시간 (분)


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(t):
    return t.replace(microsecond=0).isoformat()


def _left(iso_s, now):
    if not iso_s:
        return 0
    try:
        t = auth.parse_iso(iso_s)
    except Exception:                                       # noqa: BLE001
        return 0
    return max(0, int((t - now).total_seconds()))


def state(uid, now=None):
    """{"burnLeft": 초, "lureLeft": 초, "lureType": 타입 열쇠 또는 None} - 화면에도 그대로 싣는다."""
    now = now or _now()
    try:
        r = db.q1("SELECT burn_until, lure_type, lure_until FROM wild_state WHERE user_id=?", (uid,))
    except Exception:                                       # noqa: BLE001
        r = None                                            # (칸이 아직 없는 옛 DB - init 이 붙인다)
    burn = _left(r["burn_until"] if r else None, now)
    lure = _left(r["lure_until"] if r else None, now)
    return {"burnLeft": burn, "lureLeft": lure, "lureType": (r["lure_type"] if r and lure else None)}


def cooldown(uid, rng, now=None):
    """다음 풀숲까지 (초). 버닝 중이면 2~3분, 아니면 5~7분."""
    if uid is not None and state(uid, now)["burnLeft"] > 0:
        return rng.randint(BURN_MIN, BURN_MAX)
    return rng.randint(config.WILD_COOLDOWN_MIN, config.WILD_COOLDOWN_MAX)


def spawn_boost(uid, now=None):
    """타입 스프레이가 켜져 있으면 ((타입,), 0) - 배수 0 은 '그 타입 종만' (pokelogic.spawn_pool).
    할로윈과 같은 꼴이다 (튜플이라야 출현 풀 캐시 열쇠가 된다 - 타입마다 하나씩만 생긴다)."""
    s = state(uid, now)
    if s["lureLeft"] > 0 and s["lureType"]:
        return ((s["lureType"],), 0)
    return None


def roll_boost(uid, rng, now=None):
    """이번 풀숲이 스프레이 차례면 spawn_boost, 아니면 None (평소 표 - 할로윈은 부르는 쪽이 얹는다)."""
    b = spawn_boost(uid, now)
    if b and rng.random() < LURE_SHARE:
        return b
    return None


def room(left_secs, minutes):
    """지금 남은 시간에 minutes 를 더해도 되나 (MAX_LEFT_MIN 안)."""
    return left_secs + minutes * 60 <= MAX_LEFT_MIN * 60


def burn(uid, minutes, rng, now=None):
    """버닝을 켠다 (남아 있으면 더한다). 이미 5~7분 뒤로 잡혀 있는 다음 풀숲 시각을 2~3분 안으로 당긴다.
    새로 남은 초를 돌려준다."""
    now = now or _now()
    secs = min(MAX_LEFT_MIN * 60, state(uid, now)["burnLeft"] + minutes * 60)   # (거의 동시에 두 번 써도 3시간까지)
    until = _iso(now + datetime.timedelta(seconds=secs))
    db.run("INSERT INTO wild_state (user_id, burn_until) VALUES (?,?)"
           " ON CONFLICT(user_id) DO UPDATE SET burn_until=?", (uid, until, until))
    r = db.q1("SELECT next_at FROM wild_state WHERE user_id=?", (uid,))
    soon = now + datetime.timedelta(seconds=rng.randint(BURN_MIN, BURN_MAX))
    cur = None
    if r and r["next_at"]:
        try:
            cur = auth.parse_iso(r["next_at"])
        except Exception:                                   # noqa: BLE001
            cur = None
    if cur is None or cur > soon:
        db.run("UPDATE wild_state SET next_at=? WHERE user_id=?", (_iso(soon), uid))
    return secs


def lure(uid, type_key, minutes, now=None):
    """타입 스프레이를 켠다. 같은 타입이 켜져 있으면 더하고, 다른 타입이면 바꾸고 지금부터. 새로 남은 초."""
    now = now or _now()
    s = state(uid, now)
    base = s["lureLeft"] if s["lureType"] == type_key else 0
    secs = min(MAX_LEFT_MIN * 60, base + minutes * 60)
    until = _iso(now + datetime.timedelta(seconds=secs))
    db.run("INSERT INTO wild_state (user_id, lure_type, lure_until) VALUES (?,?,?)"
           " ON CONFLICT(user_id) DO UPDATE SET lure_type=?, lure_until=?",
           (uid, type_key, until, type_key, until))
    return secs
