# -*- coding: utf-8 -*-
"""잡았을 때의 경험치 (1.8.1). 서버를 띄우지 않는다.

    python server/test_catch_exp.py

그동안 야생을 잡으면 경험치가 없었다 - 키우려면 잡지 말고 쓰러뜨려야 했다.
이제 잡아도 쓰러뜨렸을 때의 절반을 받는다.

## 무엇을 못 박나

  1. 받는 양은 쓰러뜨렸을 때의 config.CATCH_EXP_RATE 배 (절반). 학습장치 몫도 절반.
  2. 싸우던 포켓몬이 있으면 그 포켓몬이, 볼만 던졌으면 **파티 맨 앞**이 받는다.
  3. 노력치는 안 준다 (경험치만).
  4. 방금 잡힌 포켓몬은 자기가 잡힌 경험치를 나눠 받지 않는다.
  5. 파티가 비었거나 배율이 0 이면 아무 일도 없다.
  6. **요청이 exp 를 보냈을 때만** 준다 - 옛 화면은 잡은 답에 실린 레벨업·진화를
     못 그려서 바탕화면 도트가 옛 모습으로 남는다.
"""
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-catchexp-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from common import battle as B                               # noqa: E402
from common import pokelogic as P                            # noqa: E402
from app import battle_routes as BR                          # noqa: E402
from app import config, db, deps, main                       # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mkuser(name):
    return db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')",
        (name, b"x", b"x")).lastrowid


def mkmon(uid, species, level, slot=None):
    dex = deps.dex()
    m = P.make_pokemon(dex.get(species), level, random.Random(3), shiny_rate=10 ** 9)
    m["noEvolve"] = True                 # 검사 중에 진화해 버리면 셈이 흐려진다
    pid = db.insert_mon(uid, m, "")
    if slot is not None:
        db.run("UPDATE pokemon SET on_desktop=1, slot=? WHERE id=?", (slot, pid))
    return pid


def row(pid):
    return db.q1("SELECT exp, level, evs FROM pokemon WHERE id=?", (pid,))


def main_():
    db.init()
    dex = deps.dex()
    uid = mkuser("잡는사람")
    lead = mkmon(uid, "SNORLAX", 30, slot=0)
    second = mkmon(uid, "ONIX", 30, slot=1)
    boxed = mkmon(uid, "PIKACHU", 30)                       # 박스에 있다 - 안 받는다
    wild = P.make_pokemon(dex.get("RATTATA"), 20, random.Random(9), shiny_rate=10 ** 9)
    foe = B.Fighter(dex, wild)

    print("=== 받는 양 ===")
    full = B.exp_gain(dex, foe, 30)
    share = int(B.exp_gain(dex, foe, 30, shared=True) * config.EXP_SHARE_RATE / 50.0)
    before = dict((p, dict(row(p))) for p in (lead, second, boxed))
    got = BR.catch_exp(dex, uid, wild)                      # 싸우지 않고 볼만 던졌다
    by = dict((g["id"], g) for g in got)
    chk("배율은 절반", config.CATCH_EXP_RATE == 0.5, config.CATCH_EXP_RATE)
    chk("파티 맨 앞이 쓰러뜨렸을 때의 절반을 받는다", by[lead]["gained"] == int(full * 0.5)
        and not by[lead]["shared"], (by[lead]["gained"], full))
    chk("  실제로 경험치가 쌓였다", row(lead)["exp"] == before[lead]["exp"] + int(full * 0.5))
    chk("나머지는 학습장치 몫의 절반", by[second]["gained"] == int(share * 0.5)
        and by[second]["shared"], (by[second]["gained"], share))
    chk("박스에 있는 포켓몬은 안 받는다", boxed not in by
        and row(boxed)["exp"] == before[boxed]["exp"])
    chk("노력치는 안 준다 (경험치만)", all("evs" not in g for g in got)
        and all(row(p)["evs"] == before[p]["evs"] for p in (lead, second)),
        [g.get("evs") for g in got])

    print("\n=== 싸우다가 잡았을 때 ===")
    b2 = dict((p, row(p)["exp"]) for p in (lead, second))
    got = BR.catch_exp(dex, uid, foe, second)               # 싸우던 것은 둘째
    by = dict((g["id"], g) for g in got)
    chk("싸우던 포켓몬이 큰 몫을 받는다", by[second]["gained"] == int(full * 0.5)
        and not by[second]["shared"] and by[lead]["shared"],
        (by[second]["gained"], by[lead]["gained"]))
    chk("  쓰러뜨렸을 때는 그 두 배", BR.award(dex, uid, foe, second)[0]["gained"] == full)

    print("\n=== 잡힌 포켓몬은 자기 경험치를 안 받는다 ===")
    wild2 = P.make_pokemon(dex.get("PIDGEY"), 12, random.Random(4), shiny_rate=10 ** 9)
    got = BR.catch_exp(dex, uid, wild2)
    caught, where = BR.store_caught(uid, wild2)
    cid = caught["id"]
    chk("잡은 뒤에 파티에 들어간다", where != "box" and db.q1(
        "SELECT on_desktop FROM pokemon WHERE id=?", (cid,))["on_desktop"] == 1, where)
    chk("경험치를 받은 것은 원래 있던 둘뿐", sorted(g["id"] for g in got) == sorted([lead, second]),
        [g["id"] for g in got])
    chk("  잡힌 포켓몬의 경험치는 그대로", row(cid)["level"] == 12)

    print("\n=== 아무 일도 없어야 할 때 ===")
    lonely = mkuser("빈파티")
    chk("데리고 다니는 포켓몬이 없으면 빈 목록", BR.catch_exp(dex, lonely, wild) == [])
    real = config.CATCH_EXP_RATE
    try:
        config.CATCH_EXP_RATE = 0.0
        e0 = row(lead)["exp"]
        chk("배율이 0 이면 안 준다", BR.catch_exp(dex, uid, wild) == [] and row(lead)["exp"] == e0)
    finally:
        config.CATCH_EXP_RATE = real

    print("\n=== 요청이 원할 때만 ===")
    chk("볼 던지기 요청의 기본값은 '안 받는다' (옛 화면)", main.CatchIn().exp is False
        and BR.BallIn().exp is False)
    chk("새 화면은 exp 를 보낸다", main.CatchIn(exp=True).exp is True and BR.BallIn(exp=True).exp is True)
    src = open(os.path.join(HERE, "app", "main.py"), encoding="utf-8").read()
    src2 = open(os.path.join(HERE, "app", "battle_routes.py"), encoding="utf-8").read()
    chk("두 경로 모두 잡은 포켓몬을 넣기 전에 준다",
        src.index("battle_routes.catch_exp(") < src.index("got, where = battle_routes.store_caught(")
        and src2.index('out["exp"] = catch_exp(') < src2.index("caught_mon, where = store_caught("))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
