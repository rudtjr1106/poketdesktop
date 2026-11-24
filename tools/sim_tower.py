# -*- coding: utf-8 -*-
"""배틀타워 난이도를 잰다 — 1~50층 전부에 '유저 팀' 을 붙여 승률을 본다.

    python tools/sim_tower.py              한 층에 8판
    python tools/sim_tower.py 16           한 층에 16판
    python tools/sim_tower.py 8 --floor 37 한 층만 (팀을 고친 뒤 그 층만 다시 볼 때)
    python tools/sim_tower.py 16 --floor 31-50   층 범위 (--floor 는 여러 번 줄 수 있다)
    python tools/sim_tower.py 12 --floor 21-30 --matched   베테랑을 그 층 레벨로 낮춰서 (3구역의 모양을 볼 때)

봇은 tools/sim_gym.py 의 것이다 - 늘 제일 아픈 기술을 쓰고, 한 방에 쓰러질 판이면 버틸 포켓몬으로 바꾼다.
사람만큼 영리하진 않고 **한 팀으로 모든 층을 돈다** (사람은 상대를 보고 팀을 바꾼다). 그래서 숫자는 눈금이다 -
봇이 20% 면 층에 맞춰 팀을 짜는 사람은 깬다.

    키운 유저   1 · 2구역.  그 층 레벨, 종족값 위쪽 절반, 노력치 510, 도구 없음 (sim_gym.trained_team 그대로)
    베테랑      3~5구역.    Lv.100, 노력치 510, 실전 도구, 전설 하나, 메가진화 하나 (관장 Lv.100 을 무난히 깨는 팀)

## 맞출 눈금 (design-notes/2026-11-24-battle-tower.md, 2026-11-24)

    1구역 85% 이상 · 2구역 60~85%  (키운 유저)
    3구역 80% 이상 · 4구역 50~80% · 5구역 20~50% · 50층 10% 이상  (베테랑)
    같은 봇 안에서 구역 평균은 위로 갈수록 내려가고, 층주는 그 구역 보통 층 평균보다 낮다.

벗어난 층은 tools/build_tower.py 의 FLOORS 에서 팀(종 · 기술 · 도구)을 고친다. 레벨 식 · 마릿수 · 보상은 안 건드린다.

## 봇이 못 보는 것 (숫자를 읽을 때)

  · **받이를 못 뚫는다** (독 · 도발 · 랭크업을 안 쓴다) - 재생력 순환 같은 층이 사람보다 낮게 나온다.
  · **기합의띠를 못 벗긴다** (스텔스록 · 연속기 · 날씨를 일부러 쓰지 않는다) - 띠 부대가 사람보다 낮게 나온다.
  · **3구역은 천장이다.** Lv.100 베테랑에게 Lv.70~88 은 거의 다 100% 라 층끼리 견줄 수 없다 - 그때는 --matched 로
    베테랑을 그 층 레벨로 낮춰 모양(관문 · 층주가 더 어려운가)만 본다. 구역 눈금은 Lv.100 으로 잰 값에 건다.
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from common import pokelogic as P              # noqa: E402
from common import statusmoves as SM           # noqa: E402
from common import trainer_battle as TB        # noqa: E402

import build_gyms as G                         # noqa: E402
import build_tower as BT                       # noqa: E402
import sim_gym as S                            # noqa: E402

DATA = os.path.join(ROOT, "server", "data")
# (구역, 낮은 쪽, 높은 쪽) - 구역 평균 승률이 들어야 하는 폭
TARGET = {0: (0.85, 1.0), 1: (0.60, 0.85), 2: (0.80, 1.0), 3: (0.50, 0.80), 4: (0.20, 0.50)}
LAST_FLOOR_MIN = 0.10

# 베테랑의 팀: 전설 하나 + 메가진화 하나 + 넷. (종, 도구, 특성, 성격, 노력치, 기술)
# 봇은 때리는 기술만 쓰므로 넷 다 공격기다. 랭크 상위에서 흔한 구성이지 '층마다 맞춘' 팀이 아니다.
LEGENDS = [
    ("MEWTWO", "LIFEORB", "PRESSURE", "TIMID", "spa/spe", ["PSYSTRIKE", "ICEBEAM", "AURASPHERE", "FLAMETHROWER"]),
    ("KYOGRE", "CHOICESPECS", "DRIZZLE", "MODEST", "spa/spe", ["WATERSPOUT", "SURF", "ICEBEAM", "THUNDER"]),
    ("GROUDON", "LIFEORB", "DROUGHT", "ADAMANT", "atk/spe", ["PRECIPICEBLADES", "STONEEDGE", "FIREPUNCH", "DRAGONCLAW"]),
    ("RAYQUAZA", "LIFEORB", "AIRLOCK", "JOLLY", "atk/spe", ["DRAGONCLAW", "EXTREMESPEED", "EARTHQUAKE", "WATERFALL"]),
]
MEGAS = [
    ("METAGROSS", "METAGROSSITE", "CLEARBODY", "JOLLY", "atk/spe", ["METEORMASH", "ZENHEADBUTT", "EARTHQUAKE", "ICEPUNCH"]),
    ("GARCHOMP", "GARCHOMPITE", "ROUGHSKIN", "JOLLY", "atk/spe", ["EARTHQUAKE", "DRAGONCLAW", "STONEEDGE", "FIREFANG"]),
    ("GYARADOS", "GYARADOSITE", "INTIMIDATE", "JOLLY", "atk/spe", ["WATERFALL", "CRUNCH", "EARTHQUAKE", "ICEFANG"]),
    ("SCIZOR", "SCIZORITE", "TECHNICIAN", "ADAMANT", "hp/atk", ["BULLETPUNCH", "UTURN", "KNOCKOFF", "SUPERPOWER"]),
    ("GENGAR", "GENGARITE", "CURSEDBODY", "TIMID", "spa/spe", ["SHADOWBALL", "SLUDGEBOMB", "FOCUSBLAST", "THUNDERBOLT"]),
]
REST = [
    ("TYRANITAR", "CHOICEBAND", "SANDSTREAM", "ADAMANT", "hp/atk", ["STONEEDGE", "CRUNCH", "EARTHQUAKE", "ICEPUNCH"]),
    ("DRAGONITE", "LIFEORB", "MULTISCALE", "ADAMANT", "atk/spe", ["DRAGONCLAW", "EXTREMESPEED", "EARTHQUAKE", "FIREPUNCH"]),
    ("TOGEKISS", "LEFTOVERS", "SERENEGRACE", "TIMID", "spa/spe", ["AIRSLASH", "DAZZLINGGLEAM", "FLAMETHROWER", "AURASPHERE"]),
    ("VOLCARONA", "LIFEORB", "FLAMEBODY", "TIMID", "spa/spe", ["FIERYDANCE", "BUGBUZZ", "GIGADRAIN", "PSYCHIC"]),
    ("EXCADRILL", "FOCUSSASH", "MOLDBREAKER", "JOLLY", "atk/spe", ["EARTHQUAKE", "IRONHEAD", "ROCKSLIDE", "XSCISSOR"]),
    ("MAMOSWINE", "LIFEORB", "THICKFAT", "JOLLY", "atk/spe", ["EARTHQUAKE", "ICICLECRASH", "ICESHARD", "STONEEDGE"]),
    ("HYDREIGON", "CHOICESPECS", "LEVITATE", "TIMID", "spa/spe", ["DRACOMETEOR", "DARKPULSE", "FLAMETHROWER", "EARTHPOWER"]),
    ("AZUMARILL", "CHOICEBAND", "HUGEPOWER", "ADAMANT", "hp/atk", ["PLAYROUGH", "LIQUIDATION", "AQUAJET", "KNOCKOFF"]),
    ("LUCARIO", "LIFEORB", "INNERFOCUS", "JOLLY", "atk/spe", ["CLOSECOMBAT", "METEORMASH", "EXTREMESPEED", "ICEPUNCH"]),
    ("GRENINJA", "EXPERTBELT", "PROTEAN", "TIMID", "spa/spe", ["HYDROPUMP", "DARKPULSE", "ICEBEAM", "EXTRASENSORY"]),
]


def _mon(dex, spec, rng, level=100):
    species, held, ability, nature, evs, moves = spec
    m = P.make_pokemon(dex.get(species), level, rng, shiny_rate=10 ** 9)
    m.update({"ivs": dict((s, 31) for s in P.STATS), "evs": BT.parse_evs(evs), "nature": nature,
              "ability": ability, "moves": list(moves), "held": held})
    return m


def veteran_team(dex, rng, level=100):
    """전설 하나 + 메가 하나 + 넷 (같은 종은 한 마리 - 사람 팀의 규칙). 메가는 맨 앞에 선다."""
    mega = rng.choice(MEGAS)
    rest = [r for r in REST if r[0] != mega[0]]
    picks = [mega, rng.choice(LEGENDS)] + rng.sample(rest, 4)
    return [_mon(dex, p, rng, level) for p in picks]


def check_pool(dex):
    """베테랑 풀의 종 · 기술 · 도구가 도감에 있는가 (오타가 있으면 조용히 약한 팀이 된다)."""
    items = BT.ref()[3]
    bad = []
    for species, held, ability, nature, _evs, moves in LEGENDS + MEGAS + REST:
        sp = dex.get(species)
        if not sp:
            bad.append("종 %s" % species)
            continue
        if held not in items:
            bad.append("%s 도구 %s" % (species, held))
        if ability not in list(sp.get("abil") or []) + [sp.get("hidden")]:
            bad.append("%s 특성 %s" % (species, ability))
        if nature not in P.NATURE_BY_NAME:
            bad.append("%s 성격 %s" % (species, nature))
        bad += ["%s 기술 %s" % (species, k) for k in moves if not dex.move(k)]
    return bad


# ---------------------------------------------------------------- 한 판
def play(tb, mega=False):
    """sim_gym.play 와 같은 봇. 다른 점 둘: 메가진화를 될 때 한 번 하고, 엔진이 거절한 수(날뛰는 중의 교체 ·
    구애 도구로 묶인 기술)는 받아넘겨 다른 수를 둔다 - sim_gym 은 그 자리에서 죽는다."""
    tb.keystone["me"] = bool(mega)
    tb.start()
    n = 0
    while not tb.over and n < 600:
        n += 1
        if tb.need_switch:
            tb.act("switch", S.pick_switch(tb, True))
            continue
        me, foe = tb.me, tb.foe
        slower = foe.stat("spe") >= me.stat("spe")
        my_ko = S.best_hit(tb.bt, me, foe)[0] >= foe.hp
        if S.threat(tb, me) >= 1.0 and slower and not my_ko and tb.valid_switches() \
                and not SM.trapped(tb.bt, me):
            slot = S.pick_switch(tb, False)
            if slot is not None and S.threat(tb, tb.me_team[slot]) < 0.5:
                try:
                    tb.act("switch", slot)
                    continue
                except ValueError:
                    pass                           # 기술을 쓰는 중이라 못 바꾼다 - 그냥 때린다
        go_mega = bool(mega and tb.view().get("canMega"))
        try:
            tb.act("move", S.pick_move(tb), mega=go_mega)
        except ValueError:
            tb.act("move", tb.bt.usable(tb.me)[0], mega=go_mega)
    return tb.result, sum(1 for f in tb.me_team if f.alive())


def run(dex, gdex, floors, games, seed=20261124, matched=False):
    rows = []
    for f in floors:
        n, t = f["floor"], f["trainer"]
        veteran = BT.zone_of(n) >= 2
        won = left = 0
        for g in range(games):
            rng = random.Random("%s-%d-%d" % (seed, n, g))
            party = (veteran_team(dex, rng, t["level"] if matched else 100) if veteran
                     else S.trained_team(dex, gdex, t["level"], rng))
            tb = TB.TrainerBattle(dex, party, t, random.Random(rng.random()))
            res, alive = play(tb, mega=veteran)
            won += res == "won"
            left += alive if res == "won" else 0
        rows.append({"floor": n, "name": f["name"], "kind": f["kind"], "bot": "베테랑" if veteran else "키운 유저",
                     "rate": won / float(games), "left": left / float(won) if won else 0.0})
    return rows


def judge(rows, zones=True):
    """눈금을 벗어난 것. 글줄 목록 - 비면 다 맞는다. zones=False 면 구역 눈금은 안 본다 (--matched: 봇이 다르다)."""
    out = []
    by_zone = {}
    for r in rows:
        by_zone.setdefault(BT.zone_of(r["floor"]), []).append(r)
    avg = dict((z, sum(r["rate"] for r in rs) / len(rs)) for z, rs in by_zone.items())
    for z, rs in sorted(by_zone.items()):
        if len(rs) < 10:
            continue                               # 한 층만 잴 때는 구역 눈금을 안 본다
        lo, hi = TARGET[z]
        if zones and not lo <= avg[z] <= hi:
            out.append("%d구역 평균 %.0f%% - 눈금은 %.0f~%.0f%%" % (z + 1, avg[z] * 100, lo * 100, hi * 100))
        normal = [r["rate"] for r in rs if r["kind"] == "normal"]
        boss = next(r for r in rs if r["kind"] == "boss")
        if sum(normal) / len(normal) >= 0.95:
            continue                               # 천장 - 봇이 너무 세서 층주와 견줄 수 없다 (머리말, --matched 로 본다)
        if boss["rate"] > sum(normal) / len(normal):
            out.append("%d층(층주) %.0f%% 가 그 구역 보통 층 평균 %.0f%% 보다 높다"
                       % (boss["floor"], boss["rate"] * 100, 100 * sum(normal) / len(normal)))
    for a, b in ((0, 1), (2, 3), (3, 4)) if zones else ():     # 같은 봇 안에서만 견준다
        if a in avg and b in avg and len(by_zone[a]) == len(by_zone[b]) == 10 and avg[b] > avg[a]:
            out.append("%d구역 평균이 %d구역보다 높다 (%.0f%% > %.0f%%)" % (b + 1, a + 1, avg[b] * 100, avg[a] * 100))
    last = next((r for r in rows if r["floor"] == BT.TOTAL), None)
    if last and last["rate"] < LAST_FLOOR_MIN:
        out.append("%d층 %.0f%% - 벽이면 안 된다 (%.0f%% 이상)" % (BT.TOTAL, last["rate"] * 100, LAST_FLOOR_MIN * 100))
    return out, avg


def report(rows, games, zones=True):
    mark = {"boss": "★", "gate": "◆", "normal": " "}
    print("  층    이름                   봇         승률    이긴 판 남은 수")
    for r in rows:
        print("  %2d %s %-20s %-8s %5.0f%%   %.1f" % (r["floor"], mark[r["kind"]], r["name"], r["bot"],
                                                     r["rate"] * 100, r["left"]))
    bad, avg = judge(rows, zones)
    print()
    for z in sorted(avg):
        lo, hi = TARGET[z]
        print("  %d구역 평균 %5.1f%%   %s" % (z + 1, avg[z] * 100,
                                        "(눈금 %.0f~%.0f%%)" % (lo * 100, hi * 100) if zones else "(레벨을 맞춘 봇 - 눈금 없음)"))
    print()
    for line in bad:
        print("  벗어남: " + line)
    print("  %d층 x %d판 - %s" % (len(rows), games, "눈금에 맞는다" if not bad else "%d곳이 눈금을 벗어났다" % len(bad)))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("games", nargs="?", type=int, default=8)
    ap.add_argument("--floor", action="append", help="이 층만: 37 또는 31-50 (여러 번 줄 수 있다)")
    ap.add_argument("--tower", default=os.path.join(DATA, "tower.json"))
    ap.add_argument("--matched", action="store_true", help="베테랑을 그 층 레벨로 낮춘다 (모양만 본다 - 구역 눈금은 안 건다)")
    a = ap.parse_args()
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as fh:
        raw = json.load(fh)
    dex, gdex = P.Pokedex(raw), G.Dex(raw)
    wrong = check_pool(dex)
    if wrong:
        print("베테랑 풀이 도감과 안 맞는다: %s" % " / ".join(wrong))
        return 2
    with open(a.tower, encoding="utf-8") as fh:
        floors = json.load(fh)["floors"]
    if a.floor:
        want = set()
        for part in a.floor:
            lo, _dash, hi = part.partition("-")
            want.update(range(int(lo), int(hi or lo) + 1))
        floors = [f for f in floors if f["floor"] in want]
    bad = report(run(dex, gdex, floors, a.games, matched=a.matched), a.games, zones=not a.matched)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
