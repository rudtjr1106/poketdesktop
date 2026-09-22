# -*- coding: utf-8 -*-
"""레이드 난이도를 잰다 — 3~6인이 보스를 잡을 수 있나.

    python tools/sim_raid.py                  기본 설정으로 인원별 40판
    python tools/sim_raid.py 100              인원별 100판
    python tools/sim_raid.py 40 --boss-level 55 --hp-per 1.2
    python tools/sim_raid.py 40 --sweep       몇 가지 설정을 한꺼번에

사람 봇은 sim_gym 과 같은 생각을 한다 — 제일 아픈 기술을 쓰고, 한 방에
쓰러질 판이면 버틸 포켓몬으로 바꾼다. 팀은 '보통 유저'(아무 종, 노력치 0)와
'키운 유저'(종족값 상위 절반, 노력치 510, 성격·기술 맞춤)를 섞는다 —
운영 자료를 보면 레이드 한 방에 둘이 같이 들어온다.
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

from common import battle as B                 # noqa: E402
from common import pokelogic as P              # noqa: E402
from common import raid_battle as R            # noqa: E402
from common import statusmoves as SM           # noqa: E402

import build_gyms as G                         # noqa: E402
import sim_gym as SG                           # noqa: E402

DATA = os.path.join(ROOT, "server", "data")

# 알에서 나오는 전설·환상 그대로 (server/app/eggs.py). 여기서는 자료를
# 안 읽고 몇 마리만 골라 본다 - 세기가 목적이라 전부 돌릴 필요는 없다.
SAMPLE = ["MEWTWO", "LUGIA", "RAYQUAZA", "DIALGA", "GIRATINA", "RESHIRAM",
          "XERNEAS", "SOLGALEO", "ZACIAN", "KORAIDON", "MEW", "CELEBI",
          "JIRACHI", "DARKRAI", "GENESECT", "MAGEARNA", "ZARUDE",
          "ARTICUNO", "RAIKOU", "REGICE", "CRESSELIA", "COBALION",
          "TAPUKOKO", "REGIELEKI", "ENAMORUS"]


def boss_mon(dex, name, level, rng, ev=0):
    sp = dex.get(name)
    m = P.make_pokemon(sp, level, rng, shiny_rate=10 ** 9)
    m["ivs"] = dict((s, 31) for s in P.STATS)
    m["evs"] = dict((s, ev) for s in P.STATS)
    m["nature"] = "HARDY"
    m["moves"] = G.moveset(dex, sp, level, None)
    m["held"] = None
    return m


def best_hit(bt, user, target):
    return max((SG.est(bt, user, target, k), k) for k in bt.usable(user))


def bot_turn(rb, i):
    """이 사람이 이번 라운드에 할 것."""
    p = rb.players[i]
    bt = p.bt
    me, foe = p.mon, rb.boss
    dmg, key = best_hit(bt, me, foe)
    taken = best_hit(bt, foe, me)[0]
    others = [s for s in p.alive_slots() if s != p.slot]
    # 한 방에 쓰러질 판이면 버틸 포켓몬으로 바꾼다
    if taken >= me.hp and others and not SM.trapped(bt, me):
        best, sc = None, None
        for s in others:
            f = p.team[s]
            hurt = best_hit(bt, foe, f)[0] / float(f.hp or 1)
            give = best_hit(bt, f, foe)[0]
            v = give / float(foe.maxhp) - hurt * 0.5
            if sc is None or v > sc:
                best, sc = s, v
        if best is not None and best_hit(bt, foe, p.team[best])[0] < p.team[best].hp:
            return ("switch", best)
    if dmg <= 0:
        return ("move", bt.usable(me)[0])
    return ("move", key)


def one(dex, boss_name, n, kinds, opt, seed):
    rng = random.Random(seed)
    boss = boss_mon(dex, boss_name, opt.boss_level, rng, opt.boss_ev)
    players = []
    for i in range(n):
        kind = kinds[i % len(kinds)]
        team = (SG.casual_team(dex, opt.team_level, rng) if kind == "casual"
                else SG.trained_team(dex, dex, opt.team_level, rng))
        players.append((i + 1, "P%d" % (i + 1),
                        [R.leveled(m, opt.team_level) for m in team]))
    rb = R.RaidBattle(dex, boss, players, hp_mult=opt.hp_base + opt.hp_per * n,
                      max_rounds=opt.rounds, double_from=opt.double_from,
                      rng=random.Random(rng.random()))
    rb.start()
    while not rb.over:
        for i, p in enumerate(rb.players):
            if p.playing():
                rb.choose(i, *bot_turn(rb, i))
        rb.resolve()
    left = rb.boss.hp / float(rb.boss.maxhp)
    return rb.result, rb.round, left


def run(dex, opt):
    rows = collections.defaultdict(lambda: [0, 0, 0, 0.0])
    for n in range(opt.min_players, opt.max_players + 1):
        for g in range(opt.games):
            name = SAMPLE[g % len(SAMPLE)]
            kinds = ("casual", "trained") if opt.mix else (opt.mix_kind,)
            res, rounds, left = one(dex, name, n, kinds, opt,
                                    "raid-%d-%d-%s" % (n, g, opt.seed))
            r = rows[n]
            r[0] += 1
            r[1] += res == "won"
            r[2] += rounds
            r[3] += left
    return rows


def report(rows, title):
    print("  %s" % title)
    print("   인원   판수   승률     평균 라운드   진 판의 남은 보스 체력")
    for n in sorted(rows):
        cnt, won, rounds, left = rows[n]
        lost = cnt - won
        print("   %d인   %4d   %5.1f%%   %6.1f        %s"
              % (n, cnt, 100.0 * won / max(1, cnt), rounds / float(max(1, cnt)),
                 ("%5.1f%%" % (100.0 * left / lost)) if lost else "   —"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("games", nargs="?", type=int, default=20)
    ap.add_argument("--boss-level", type=int, default=60)
    ap.add_argument("--team-level", type=int, default=50)
    ap.add_argument("--hp-base", type=float, default=2.0)
    ap.add_argument("--hp-per", type=float, default=1.6)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--double-from", type=int, default=4)
    ap.add_argument("--min-players", type=int, default=3)
    ap.add_argument("--max-players", type=int, default=6)
    ap.add_argument("--mix", action="store_true", default=True)
    # **이게 늘 '섞어서' 로 돌았다.** 기본값이 "trained" 인데 아래에서
    # "trained 가 아니면 섞지 않는다" 로 봐서, --only trained 를 줘도 섞였다.
    # 레이드에 오는 사람은 키운 팀일 공산이 커서 따로 잴 수 있어야 한다.
    ap.add_argument("--only", dest="mix_kind", default=None,
                    choices=("casual", "trained"))
    ap.add_argument("--boss-ev", type=int, default=96,
                    help="보스 노력치 (능력마다). server/app/config.RAID_BOSS_EV 와 같게")
    ap.add_argument("--seed", default="20260919")
    ap.add_argument("--sweep", action="store_true")
    opt = ap.parse_args()
    if opt.mix_kind:
        opt.mix = False
    dex = P.Pokedex.load(os.path.join(DATA, "pokedex.json"))
    if not opt.sweep:
        who = {"casual": "보통 유저만", "trained": "키운 유저만"}.get(opt.mix_kind, "섞어서")
        report(run(dex, opt), "%s · 보스 Lv.%d 노력치 %d · 팀 Lv.%d · 체력 x(%.1f + %.1f x 인원) · %d라운드"
               % (who, opt.boss_level, opt.boss_ev, opt.team_level, opt.hp_base,
                  opt.hp_per, opt.rounds))
        return
    for lv in (55, 60):
        for per in (0.8, 1.1, 1.4):
            opt.boss_level, opt.hp_per = lv, per
            report(run(dex, opt), "보스 Lv.%d · 체력 x(%.1f + %.1f x 인원)"
                   % (lv, opt.hp_base, per))
            print()


if __name__ == "__main__":
    main()
