# -*- coding: utf-8 -*-
"""대전 다시 보기: 'faint' 없이 쓰러진 포켓몬을 ko 에서 쓰러뜨린다 (11/23 게시판 #800 양양) - 화면 없이.

    python client/test_arena_silent_faint.py

2.5.4 까지의 서버는 나오자마자 스텔스록 · 압정에 쓰러지면 'faint' 를 안 냈다. 그 판을 다시 보면 쓰러진 포켓몬이
링에 남아 다음 선수와 같이 서 있다가 같이 사라졌다 ('두 마리가 같이 나와서 같이 쓰러졌다'). 이제는

  1. 체력 0 (chip) 인데 아직 서 있으면 ko 에서 쓰러지는 연출을 하고 자리를 비운다
  2. faint 를 받아 이미 쓰러졌으면 ko 가 또 쓰러뜨리지 않는다 (예전과 같다)
  3. 턴 상한 무승부(both, 체력 남음)는 쓰러뜨리지 않는다 (물러나는 것 - 예전과 같다)
  4. 새 라운드의 체력으로 다시 센다 (앞 선수의 0 이 다음 선수에게 남지 않는다)
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-arena-faint-"))

from poketdesktop import arena as AR                       # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Pet(object):
    def __init__(self, name):
        self.name = name
        self.down = False


def arena():
    a = AR.Arena.__new__(AR.Arena)
    a.closed = False
    a.layer = None
    a.bars = {}
    a.hiding = None
    a.scale = 1.0
    a.active = {"me": Pet("누리레느"), "foe": Pet("리자몽")}
    a.slot = {"me": 0, "foe": 1}
    a.down = {"me": set(), "foe": set()}
    a.fainted = []

    def faint(pet, done):
        a.fainted.append(pet.name)
        pet.down = True
        done()
    a._faint = faint
    a.after = lambda ms, fn: fn()
    return a


def main():
    print("=== 다시 보기: faint 없이 쓰러진 포켓몬 (#800)")
    a = arena()
    nuri = a.active["me"]
    a._apply_hp({"t": "chip", "who": "me", "damage": 23, "hp": 0, "maxhp": 186})
    done = []
    a._on_ko({"t": "ko", "side": "me"}, lambda: done.append(1))
    chk("1. 체력 0 인데 서 있으면 ko 에서 쓰러뜨린다", a.fainted == ["누리레느"] and nuri.down, a.fainted)
    chk("   자리를 비우고 다음으로 간다", a.active["me"] is None and 0 in a.down["me"] and done == [1], (a.active, done))

    a = arena()
    a._apply_hp({"t": "hit", "who": "foe", "target": "me", "damage": 99, "hp": 0, "maxhp": 186})
    a.active["me"].down = True                       # (faint 를 받아 이미 쓰러졌다)
    a._on_ko({"t": "ko", "side": "me"}, lambda: None)
    chk("2. faint 로 이미 쓰러졌으면 또 안 쓰러뜨린다", a.fainted == [] and a.active["me"] is None, a.fainted)

    a = arena()
    a._apply_hp({"t": "hit", "who": "me", "target": "foe", "hp": 70, "maxhp": 154})
    a._apply_hp({"t": "hit", "who": "foe", "target": "me", "hp": 40, "maxhp": 186})
    a._on_ko({"t": "ko", "side": "both"}, lambda: None)
    chk("3. 턴 상한 무승부(both, 체력 남음)는 쓰러뜨리지 않는다", a.fainted == [] and a.active == {"me": None, "foe": None},
        (a.fainted, a.active))

    # 4. 새 라운드의 체력으로 다시 센다: 앞 선수가 0 으로 끝났어도 같은 자리에 서 있는 선수(연전)는 round 의 체력이다
    a = arena()
    me, foe = a.active["me"], a.active["foe"]
    a.roster = {"me": [me], "foe": [None, foe]}
    a._pet_at = lambda side, i: a.active[side]       # (둘 다 그 자리에 그대로 서 있다 - 연전)
    a._hp_now()["me"] = 0                            # (앞에서 본 값)
    a._on_round({"t": "round", "n": 8, "mi": 0, "fi": 1, "me": {"hp": 150, "maxhp": 186},
                 "foe": {"hp": 38, "maxhp": 154}}, lambda: None)
    chk("4. round 가 그 선수의 체력을 다시 넣는다", a._hp_now() == {"me": 150, "foe": 38}, a._hp_now())
    a._on_ko({"t": "ko", "side": "foe"}, lambda: None)
    chk("   체력이 남은 쪽은 ko 에서 쓰러뜨리지 않는다", a.fainted == [], a.fainted)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
