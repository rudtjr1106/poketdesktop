# -*- coding: utf-8 -*-
"""기술머신.

## 다른 도구와 무엇이 다른가

- **팔지도 사지도 않는다.** 상점 목록에 아예 안 올라간다.
- **쓴다고 없어지지 않는다.** 한 번 얻으면 계속 쓴다. 그래서 개수가 없다.
- **잡을 때 떨어지는 것으로만 얻는다.**

개수가 없으니 가방(bag) 표에 넣지 않는다. 거기는 (사용자, 도구, 개수)
인데 기술머신에는 개수라는 개념이 없다. 있으면 있고 없으면 없다.
`tm_owned` 에 있으면 가진 것이다.

## 자료

`server/data/tms.json` 은 tools/build_tms.py 가 만든다. 전 세대 기술머신을
합쳐 358개, 배울 수 있는 종이 1016마리다. 스칼렛/바이올렛만 쓰면 229개인데
팔데아에 안 나오는 288종이 하나도 못 배우게 된다.
"""
import datetime
import io
import json
import os
import threading

from . import db


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


_lock = threading.Lock()
_data = None

PATH = os.environ.get(
    "POKET_TMS",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "data", "tms.json"))

# 잡거나 쓰러뜨렸을 때 기술머신이 떨어질 확률.
#
# 도구 드랍과 **따로 굴린다.** 같은 표에 넣으면 358개가 한꺼번에 들어가서
# 도구 드랍이 기술머신 잔치가 된다. 여기서 안 나오면 평소처럼 도구가 나온다.
#
# 5%면 스무 마리에 하나쯤이다. 358개를 다 모으려면 한참 걸리는데, 그게
# 맞다 - 살 수 없는 물건이라 모으는 것 자체가 할 일이 된다.
DROP_CHANCE = float(os.environ.get("POKET_TM_DROP", "0.05"))

# 이로치를 잡으면 여러 번 굴린다. 도구 드랍과 같은 대접이다.
SHINY_ROLLS = 3


def data():
    global _data
    if _data is None:
        with _lock:
            if _data is None:
                with io.open(PATH, encoding="utf-8") as f:
                    _data = json.load(f)
    return _data


def all_tms():
    """{번호(int): {no, move, kr, type, cat, gen, sv}}"""
    return dict((int(k), v) for k, v in data()["tms"].items())


def get(no):
    return data()["tms"].get(str(int(no)))


def count():
    return len(data()["tms"])


def learnable(species_num):
    """이 종이 배울 수 있는 기술머신 번호들. 없으면 빈 목록."""
    return data()["learn"].get(str(int(species_num)), [])


def can_learn(species_num, no):
    return int(no) in set(learnable(species_num))


# ---------------------------------------------------------------- 가진 것
def owned(uid):
    """가진 기술머신 번호 집합."""
    rows = db.q("SELECT no FROM tm_owned WHERE user_id=?", (uid,))
    return set(int(r["no"]) for r in rows)


def has(uid, no):
    r = db.q1("SELECT 1 FROM tm_owned WHERE user_id=? AND no=?",
              (uid, int(no)))
    return r is not None


def give(uid, no, now=None):
    """준다. 이미 있으면 False (같은 것을 두 번 세지 않는다)."""
    if has(uid, no):
        return False
    db.run("INSERT INTO tm_owned (user_id, no, got_at) VALUES (?,?,?)"
           " ON CONFLICT(user_id, no) DO NOTHING",
           (uid, int(no), now or _now()))
    return True


def roll_drop(rng, species_num=None, shiny=False, uid=None):
    """떨어질 기술머신 하나. 안 떨어지면 None.

    **이미 가진 것은 안 준다.** 살 수도 팔 수도 없는 물건이라, 중복이
    나오면 아무 일도 안 일어난 것과 같다. 다 모았으면 그때부터는 평소처럼
    도구만 나온다.

    종을 주면 **그 종이 배울 수 있는 것**에서 고른다. 방금 잡은 애가 못
    쓰는 기술머신이 나오면 무엇을 얻은 건지 와닿지 않는다. 그 종이 배울
    게 없으면 전체에서 고른다.
    """
    rolls = SHINY_ROLLS if shiny else 1
    if rng.random() > 1.0 - (1.0 - DROP_CHANCE) ** rolls:
        return None

    pool = None
    if species_num:
        pool = [n for n in learnable(species_num)]
    if not pool:
        pool = sorted(all_tms())
    if uid is not None:
        got = owned(uid)
        left = [n for n in pool if n not in got]
        if not left:
            # 이 종 것은 다 모았다. 전체에서 못 모은 것을 본다.
            left = [n for n in sorted(all_tms()) if n not in got]
        if not left:
            return None          # 358개를 다 모았다
        pool = left
    return rng.choice(pool)


def public(no):
    """드랍 알림에 실어 보낼 꼴."""
    t = get(no)
    if not t:
        return None
    return {"no": int(no), "kr": t["kr"], "type": t["type"],
            "cat": t["cat"], "label": label(no)}


def label(no):
    """`기술머신042 냉동빔` 처럼 보여줄 이름."""
    t = get(no)
    if not t:
        return "기술머신%03d" % int(no)
    return "기술머신%03d %s" % (int(no), t["kr"])
