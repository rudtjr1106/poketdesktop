# -*- coding: utf-8 -*-
"""야생 배틀 저장본 — 기술이 남긴 상태가 턴을 넘어가도 남는가.

야생 배틀은 요청마다 DB 에서 두 포켓몬을 되살리고(_fighters) 끝나면 다시
적는다(_dump). 여기에 빠진 것은 **다음 턴에 사라진다.** 씨뿌리기를 넣을 때
저장본에 안 적으면 한 턴 뒤에 씨앗이 없어진다.

    씨뿌리기   seeded
    참기       bide (남은 턴, 모은 데미지)
    비축하기   stockpile
    내던지기   itemGone (던진 도구는 이 판에서 다시 못 쓴다)

옛 저장본(vol 이 없는 것)도 그대로 읽혀야 한다 - 배포하는 순간 진행 중인 판이 있다.

서버를 띄우지 않는다. 모듈만 직접 쓴다.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-bstate-")
# 서버 컨테이너 안에서 돌려도 돌고 있는 서버의 DB 를 건드리지 않게 (test_evolution 과 같다)
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

import random                                               # noqa: E402

from common import battle as B                             # noqa: E402
from common import pokelogic as P                          # noqa: E402

from common import statusmoves as SM                       # noqa: E402

from app import battle_routes as R                         # noqa: E402
from app import deps                                       # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mon(dex, species, level, moves, held=None):
    m = P.make_pokemon(dex.get(species), level, random.Random(1), shiny_rate=10 ** 9)
    m["moves"] = moves
    m["held"] = held
    return m


def row_of(me, foe):
    return {"me": json.dumps(R._dump(me)), "foe": json.dumps(R._dump(foe))}


def main():
    dex = deps.dex()
    me = B.Fighter(dex, mon(dex, "SWALOT", 40, ["STOCKPILE", "FLING", "BIDE"], held="IRONBALL"))
    foe = B.Fighter(dex, mon(dex, "RATTATA", 40, ["TACKLE"]))
    bt = B.Battle(dex, me, foe, random.Random(3))
    foe.seeded = True
    me.stockpile = 2
    me.item_gone = True
    me.bide = {"left": 1, "sum": 17}

    me2, foe2 = R._fighters(dex, row_of(me, foe))
    chk("씨뿌리기가 남는다", foe2.seeded and not me2.seeded, (foe2.seeded, me2.seeded))
    chk("비축 횟수가 남는다", me2.stockpile == 2, me2.stockpile)
    chk("던진 도구는 없는 채로 남는다 (효과도 없다)", me2.item_gone and me2.held is None
        and me2.mon.get("held") == "IRONBALL", (me2.item_gone, me2.held))
    chk("참기(남은 턴·모은 데미지)가 남는다", me2.bide == {"left": 1, "sum": 17}, me2.bide)

    # 되살린 판으로 한 턴 돌리면 씨앗이 체력을 빼앗는다
    bt2 = B.Battle(dex, me2, foe2, random.Random(3))
    before = foe2.hp
    ev = []
    bt2._end_of_turn(ev)
    chk("되살린 판에서도 턴 끝에 빼앗는다", foe2.hp == before - max(1, foe2.maxhp // 8), (before, foe2.hp))

    # 옛 저장본 (vol 칸이 없다)
    old = {"me": json.dumps({k: v for k, v in R._dump(me).items() if k != "vol"}),
           "foe": json.dumps({k: v for k, v in R._dump(foe).items() if k != "vol"})}
    me3, foe3 = R._fighters(dex, old)
    chk("옛 저장본도 읽는다 (씨앗·비축 없음)", not foe3.seeded and me3.stockpile == 0 and not me3.item_gone)
    chk("아무것도 안 걸렸으면 vol 은 비워 둔다", R._dump(B.Fighter(dex, mon(dex, "PIKACHU", 5, ["TACKLE"])))["vol"] is None)

    # 변화기가 남긴 것: 혼란·대타출동(포켓몬) + 날씨·압정(판). 날씨와 압정은 야생 쪽 저장본에 같이 적는다.
    from common import field as FD
    me = B.Fighter(dex, mon(dex, "GENGAR", 40, ["CONFUSERAY", "SUBSTITUTE", "SUNNYDAY", "SPIKES"]))
    foe = B.Fighter(dex, mon(dex, "RATTATA", 40, ["TACKLE"]))
    bt = B.Battle(dex, me, foe, random.Random(3))
    ev = []
    for k in ("SUBSTITUTE", "SUNNYDAY", "SPIKES"):
        bt._use("me", me, foe, k, ev)
    foe.cond["confused"] = 3
    foe_dump = R._dump(foe)
    foe_dump["field"] = bt.field.dump()
    row = {"me": json.dumps(R._dump(me)), "foe": json.dumps(foe_dump), "turn": 4}
    me4, foe4 = R._fighters(dex, row)
    bt4 = R._battle(dex, row, me4, foe4)
    chk("대타출동·혼란이 남는다", me4.cond.get("sub") and foe4.cond.get("confused") == 3, (me4.cond, foe4.cond))
    chk("날씨(쾌청)와 압정이 남는다", bt4.field.weather == "sun" and bt4.field.side("foe").get("spikes") == 1,
        bt4.field.dump())
    chk("되살린 포켓몬이 되살린 판에 붙는다 (날씨가 능력치·데미지에 반영된다)", me4.field is bt4.field)
    chk("판 턴 수도 이어진다", bt4.turn_no == 4)
    old_row = {"me": json.dumps(R._dump(me)), "foe": json.dumps(R._dump(foe)), "turn": 1}
    chk("날씨 칸이 없는 옛 저장본도 읽는다", R._battle(dex, old_row, *R._fighters(dex, old_row)).field.weather is None)

    # 야생이 울부짖기·순간이동을 쓰면 판이 끝난다 (볼을 던진 턴에도)
    me = B.Fighter(dex, mon(dex, "PIKACHU", 40, ["TACKLE"]))
    foe = B.Fighter(dex, mon(dex, "ABRA", 40, ["TELEPORT"]))
    bt = B.Battle(dex, me, foe, random.Random(1))
    ev = []
    R.foe_only_turn(bt, ev)
    chk("볼을 던진 턴에 캐이시가 순간이동하면 판이 끝난다", bt.over and bt.result == "fled", [e.get("text") for e in ev])
    me = B.Fighter(dex, mon(dex, "PIKACHU", 40, ["TACKLE"]))
    foe = B.Fighter(dex, mon(dex, "UMBREON", 40, ["MEANLOOK"]))
    bt = B.Battle(dex, me, foe, random.Random(1))
    bt._use("foe", foe, me, "MEANLOOK", [])
    chk("검은눈빛에 걸리면 도망칠 수 없다", SM.trapped(bt, me))

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
