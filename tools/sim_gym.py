# -*- coding: utf-8 -*-
"""관장 난이도를 잰다 — 256명 전부에게 '유저 팀' 을 붙여 승률을 본다.

    python tools/sim_gym.py                 한 사람당 4판
    python tools/sim_gym.py 8               한 사람당 8판
    python tools/sim_gym.py 4 --gyms a.json 다른 관장 자료로 (고치기 전과 비교할 때)

사람이 두는 수를 흉내 내는 봇을 둘 둔다.

    보통 유저   그 레벨에 잡을 수 있는 종을 아무거나. 개체값·성격은 잡힌 그대로,
                노력치 0, 기술은 레벨업으로 배운 마지막 넷.
    키운 유저   같은 레벨에서 종족값이 높은 쪽 절반. 노력치 510 을 공격 쪽과
                스피드에, 성격도 맞춰 주고, 기술은 타입이 겹치지 않게 고른다.

봇은 늘 제일 아픈 기술을 쓰고(급소·난수 없이 계산), 지금 붙은 상대에게
한 방에 쓰러질 판이면 버틸 수 있는 포켓몬으로 바꾼다. 사람만큼 영리하진
않지만, **고치기 전과 뒤를 같은 봇으로 재면** 얼마나 어려워졌는지는 나온다.

레벨은 트레이너 레벨과 같게 둔다 (+N 으로 올려 볼 수 있다: --plus 5).
"""
import argparse
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from common import abilities as A              # noqa: E402
from common import battle as B                 # noqa: E402
from common import pokelogic as P              # noqa: E402
from common import trainer_battle as TB        # noqa: E402

import build_gyms as G                         # noqa: E402

DATA = os.path.join(ROOT, "server", "data")


# ---------------------------------------------------------------- 유저 팀
def _legal(dex, level):
    return [s for s in dex.species
            if s.get("spawnable") and not s.get("legendary") and s.get("minLevel", 1) <= level]


def _final_ok(dex, s, level):
    """그 레벨이면 이미 진화했을 종은 뺀다 (Lv.60 의 꼬렛 같은 것)."""
    for e in s.get("evo") or []:
        if e.get("mode") == "level" and e.get("level") and e["level"] <= level:
            return False
    return True


def casual_team(dex, level, rng):
    pool = [s for s in _legal(dex, level) if _final_ok(dex, s, level)]
    team = []
    for s in rng.sample(pool, 6):
        m = P.make_pokemon(s, level, rng, shiny_rate=10 ** 9)
        m["held"] = None
        team.append(m)
    return team


SPREAD_NATURE = {("atk", "spe"): "JOLLY", ("spa", "spe"): "TIMID"}


def trained_team(dex, gdex, level, rng):
    pool = [s for s in _legal(dex, level) if _final_ok(dex, s, level)]
    pool.sort(key=lambda s: -P.Pokedex.bst(s))
    pool = pool[:max(12, len(pool) // 2)]
    team = []
    for s in rng.sample(pool, 6):
        m = P.make_pokemon(s, level, rng, shiny_rate=10 ** 9)
        atk = "atk" if s["base"]["atk"] >= s["base"]["spa"] else "spa"
        m["evs"] = dict((k, 0) for k in P.STATS)
        m["evs"][atk] = 252
        m["evs"]["spe"] = 252
        m["evs"]["hp"] = 6
        m["nature"] = SPREAD_NATURE[(atk, "spe")]
        m["moves"] = G.moveset(gdex, s, level, None)
        m["held"] = None
        team.append(m)
    return team


# ---------------------------------------------------------------- 유저 봇
def est(bt, user, target, key):
    md = bt.move_of(key)
    if not md.get("power"):
        return 0.0
    if user.ability_on and A.would_block(user, target, md):
        return 0.0
    d, _c, _e = B.damage(bt.dex, md, user, target, B.EST_RNG, crit=False)
    lo, hi = ((md.get("hits") or [1, 1]) + [1, 1])[:2]
    if hi > 1:
        d *= B.HITS_AVG if (lo, hi) == (2, 5) else (lo + hi) / 2.0
    return d * ((md.get("acc") or 100) / 100.0)


def best_hit(bt, user, target):
    moves = bt.usable(user)
    return max((est(bt, user, target, k), k) for k in moves)


def pick_move(tb):
    bt = tb.bt
    dmg, key = best_hit(bt, tb.me, tb.foe)
    if dmg <= 0:
        return bt.usable(tb.me)[0]
    return key


def threat(tb, mine):
    """상대가 지금 이 포켓몬에게 줄 수 있는 가장 큰 데미지 비율."""
    d, _k = best_hit(tb.bt, tb.foe, mine)
    return d / float(mine.hp or 1)


def pick_switch(tb, forced):
    best, best_sc = None, None
    for i in tb.valid_switches() if not forced else [i for i, f in enumerate(tb.me_team) if f.alive()]:
        f = tb.me_team[i]
        taken = threat(tb, f)
        dealt = best_hit(tb.bt, f, tb.foe)[0] / float(tb.foe.hp or 1)
        sc = dealt - taken * 0.8
        if best_sc is None or sc > best_sc:
            best, best_sc = i, sc
    return best


def play(tb, rng):
    tb.start()
    n = 0
    while not tb.over and n < 600:
        n += 1
        if tb.need_switch:
            tb.act("switch", pick_switch(tb, True))
            continue
        me, foe = tb.me, tb.foe
        # 한 방에 쓰러질 판인데 내가 먼저 못 쓰러뜨리면, 버틸 포켓몬으로 바꾼다
        slower = foe.stat("spe") >= me.stat("spe")
        my_ko = best_hit(tb.bt, me, foe)[0] >= foe.hp
        if threat(tb, me) >= 1.0 and slower and not my_ko and tb.valid_switches():
            slot = pick_switch(tb, False)
            if slot is not None and threat(tb, tb.me_team[slot]) < 0.5:
                tb.act("switch", slot)
                continue
        tb.act("move", pick_move(tb))
    return tb.result, sum(1 for f in tb.me_team if f.alive())


# ---------------------------------------------------------------- 재기
def run(dex, gdex, gyms, games, plus, seed=20260915):
    rows = collections.defaultdict(lambda: {"casual": [0, 0, 0], "trained": [0, 0, 0]})
    for ti, t in enumerate(gyms["trainers"]):
        lv = t["level"] + plus
        band = (t["level"] // 20) * 20
        for g in range(games):
            for kind in ("casual", "trained"):
                rng = random.Random("%s-%d-%d-%s" % (seed, ti, g, kind))
                party = (casual_team(dex, lv, rng) if kind == "casual"
                         else trained_team(dex, gdex, lv, rng))
                tb = TB.TrainerBattle(dex, party, t, random.Random(rng.random()))
                res, left = play(tb, rng)
                r = rows[band][kind]
                r[0] += 1
                r[1] += res == "won"
                r[2] += left if res == "won" else 0
    return rows


def report(rows):
    tot = {"casual": [0, 0, 0], "trained": [0, 0, 0]}
    print("  레벨대      보통 유저 승률 (이긴 판 남은 수)    키운 유저 승률 (남은 수)")
    for band in sorted(rows):
        r = rows[band]
        cells = []
        for kind in ("casual", "trained"):
            n, w, left = r[kind]
            for i in range(3):
                tot[kind][i] += r[kind][i]
            cells.append("%5.1f%%  (%.1f)" % (100.0 * w / max(1, n), left / float(max(1, w))))
        print("  Lv.%3d~     %-32s %s" % (band, cells[0], cells[1]))
    cells = []
    for kind in ("casual", "trained"):
        n, w, left = tot[kind]
        cells.append("%5.1f%%  (%.1f)" % (100.0 * w / max(1, n), left / float(max(1, w))))
    print("  전체        %-32s %s" % (cells[0], cells[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("games", nargs="?", type=int, default=4)
    ap.add_argument("--gyms", default=os.path.join(DATA, "gyms.json"))
    ap.add_argument("--plus", type=int, default=0, help="유저 레벨을 트레이너보다 이만큼 높게")
    a = ap.parse_args()
    raw = json.load(open(os.path.join(DATA, "pokedex.json"), encoding="utf-8"))
    dex = P.Pokedex(raw)
    gdex = G.Dex(raw)
    gyms = json.load(open(a.gyms, encoding="utf-8"))
    print("관장 %d명 x %d판 x 2종류, 유저 레벨 = 트레이너 레벨%+d" % (len(gyms["trainers"]), a.games, a.plus))
    report(run(dex, gdex, gyms, a.games, a.plus))


if __name__ == "__main__":
    main()
