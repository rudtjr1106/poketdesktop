# -*- coding: utf-8 -*-
"""공습 (2.3.0) — 하루 한 번 낙하산을 타고 내려온 야생 포켓몬 무리와 바탕화면 파티가 각개전투를 한다.

설계: design-notes/2026-11-08-airraid.md (사용자 결정 11/08: 이긴 쪽이 다음 상대 · 경험치 + 볼 · 골드 · 못 잡음).

## 뽑기

    마리 수   파티 수 + 2 또는 3
    레벨      파티 평균 - (2~5), 야생 최저 레벨 아래로는 안 간다. **파티가 작으면 더 낮게** (1마리 -12~15 · 2마리
              -7~10 · 3마리 -4~7) - 혼자는 서너 마리를 체력 하나로 차례로 이겨야 해서 같은 차로는 승률이 24% 였다
              (tools/airraid_sim.py 1,920판: 막 잡은 파티 54~86% · 키운 파티 68~90% 로 고르게)
    종        그 레벨의 야생 표 (Pokedex.roll_wild - 종족값 상한 330 + 8 x 레벨, 전설 X), 이로치 없음

## 싸움 — 이긴 쪽이 다음 상대

battle.Battle(1:1)을 짝마다 하나씩 세운다. 고치지 않고 감싸기만 한다 (party_battle · raid_battle 과 같은 원칙).

  1. 처음엔 내 포켓몬마다 공습 포켓몬 한 마리씩 짝 (나머지 공습 포켓몬은 기다린다).
  2. **전역 턴**마다 살아 있는 짝이 모두 한 턴씩 싸운다 (짝 번호 차례 - 결과가 시드 하나로 정해진다).
  3. 짝이 끝나면 이긴 쪽이 남은 체력으로 다음 상대를 찾는다:
       내 포켓몬 -> 기다리는 공습 포켓몬 (없으면 쉬고 있는 공습 포켓몬 = 짝을 이기고 남은 것)
       공습 포켓몬 -> 쉬고 있는 내 포켓몬 (없으면 기다린다)
  4. 공습 포켓몬이 다 쓰러지면 승리, 내 쪽이 다 쓰러지면 패배.

체력 · 상태이상은 Fighter 에 남아 다음 짝으로 이어진다. 날씨 · 필드는 짝마다 새로 (다른 짝의 비가 옮겨 오지 않게).
한 짝이 짝 턴 상한(PAIR_TURNS)까지 가면 체력 몫이 적은 쪽이 물러난다(쓰러진 것으로 친다, 같으면 공습 쪽). 전역 턴
상한(TURN_CAP)에 닿으면 남은 머릿수로 가른다 (같으면 공습 쪽 승 - 막지 못했다).

## 로그 (앱 airraid_show 가 바탕화면에서 재생)

    {"t": "teams", "me": [...], "foe": [...]}                         명단 (party_battle._side_view 꼴)
    {"t": "pair", "d": 판, "mi": 내 i, "fi": 공습 i, "me": {hp, maxhp}, "foe": {hp, maxhp}}
    {"t": "turn", "n": 전역 턴}
    {... Battle 이벤트 ..., "d": 판}                                    who/target 은 그 판 기준 me / foe
    {"t": "end", "d": 판, "win": "me"|"foe"|"both", "mi", "fi"}       both = 둘 다 쓰러짐
    {"t": "raid", "result": "win"|"lose", "turns": n}

kos = [[공습 i, 내 i], ...] - 공습 포켓몬을 쓰러뜨린 내 포켓몬 (서버가 경험치를 준다).
"""
import random

from common import battle as B
from common import field as FD
from common import party_battle as PB

EXTRA = (2, 3)               # 파티보다 이만큼 더
LEVEL_GAP = (2, 5)           # 파티 평균보다 이만큼 낮게 (4마리 이상)
GAP_BY_SIZE = {1: (12, 15), 2: (7, 10), 3: (4, 7)}     # 작은 파티는 더 낮게 (위 머리말)
MIN_LEVEL = 2                # 야생 최저 레벨 (server config.WILD_MIN_LEVEL 과 같다)
TURN_CAP = 400               # 전역 턴 상한 (회복 · 방어만 하는 짝이 끝나지 않는 판)
PAIR_TURNS = 40              # 짝 하나의 턴 상한


def bst_cap(level):
    """야생과 같은 종족값 상한 (server main._wild_levels: WILD_BST_BASE 330 + 레벨 x WILD_BST_PER_LEVEL 8)."""
    return 330 + int(level) * 8


def raid_size(n_party, rng):
    return int(n_party) + rng.choice(EXTRA)


def raid_level(avg, rng, lo=MIN_LEVEL, n_party=4):
    return max(int(lo), int(round(avg)) - rng.randint(*GAP_BY_SIZE.get(int(n_party), LEVEL_GAP)))


def roll_raiders(dex, levels, rng, lo=MIN_LEVEL):
    """파티 레벨들 -> 공습 포켓몬 목록 (못 잡으니 이로치 없음). 파티가 없으면 []."""
    levels = [int(x) for x in levels or () if x]
    if not levels:
        return []
    avg = sum(levels) / float(len(levels))
    out = []
    for _ in range(raid_size(len(levels), rng)):
        lv = raid_level(avg, rng, lo, len(levels))
        mon = dex.roll_wild(lv, lv, rng, max_bst=bst_cap(lv), force_shiny=False)
        if mon is not None:
            out.append(mon)
    return out


def _no_switch(who, mode, ev, key, state=None):
    return False


class AirRaid(object):
    """    out = AirRaid(dex, 내 포켓몬들, 공습 포켓몬들, seed).run()"""

    def __init__(self, dex, mine, foes, seed=None, turn_cap=TURN_CAP):
        if not mine or not foes:
            raise ValueError("양쪽 다 최소 한 마리는 있어야 합니다.")
        self.dex = dex
        self.seed = random.randrange(1 << 30) if seed is None else int(seed)
        self.rng = random.Random(self.seed)
        self.a = [PB.PartyBattle._fighter(dex, m) for m in mine]
        self.b = [PB.PartyBattle._fighter(dex, m) for m in foes]
        self.turn_cap = int(turn_cap)
        self.events = []
        self.kos = []
        self.turns = 0

    # ---------------- 짝 ----------------
    def _pair(self, d, mi, fi):
        bt = B.Battle(self.dex, self.a[mi], self.b[fi], self.rng, ai="wild", field=FD.Field())
        bt.max_turns = PAIR_TURNS
        bt.kind = "pvp"                  # 교체가 없는 1:1 (야생처럼 도망가지 않는다)
        # 바꿀 동료가 없는 1:1 - 울부짖기 · 날려버리기는 실패, 드래곤테일 · 배대뒤치기는 데미지만, 순간이동도 실패
        # (switcher 가 없으면 엔진이 야생처럼 '날려가 버렸다' 로 판을 끝내서 체력 몫이 적은 쪽이 쓰러진 것으로 쳐졌다 -
        # 독립 검토). 탈출버튼 · 레드카드는 이 판 안에서만 발동 · 소모된다 (공습 판의 개체는 저장하지 않는다)
        bt.switcher = _no_switch
        self.events.append({"t": "pair", "d": d, "mi": mi, "fi": fi,
                            "me": {"hp": self.a[mi].hp, "maxhp": self.a[mi].maxhp},
                            "foe": {"hp": self.b[fi].hp, "maxhp": self.b[fi].maxhp}})
        ev = []
        for who in ("me", "foe"):
            bt.enter(who, ev)
        self.events.extend(dict(e, d=d) for e in ev if e.get("t") != "over")
        return {"d": d, "mi": mi, "fi": fi, "bt": bt, "turns": 0}

    def _end(self, duel):
        a, b = self.a[duel["mi"]], self.b[duel["fi"]]
        if a.alive() and b.alive():      # 짝 턴 상한 - 체력 몫이 적은 쪽이 물러난다 (같으면 공습 쪽)
            if a.hp * b.maxhp >= b.hp * a.maxhp:
                b.hp = 0
            else:
                a.hp = 0
        win = "both" if not a.alive() and not b.alive() else ("me" if a.alive() else "foe")
        if not b.alive() and a is not None:
            self.kos.append([duel["fi"], duel["mi"]])
        self.events.append({"t": "end", "d": duel["d"], "win": win, "mi": duel["mi"], "fi": duel["fi"]})

    # ---------------- 한 판 ----------------
    def run(self):
        self.events.append({"t": "teams", "me": [PB._side_view(f) for f in self.a],
                            "foe": [PB._side_view(f) for f in self.b]})
        duels = []
        busy_a, busy_b = set(), set()
        waiting = list(range(len(self.b)))          # 아직 안 싸운 공습 포켓몬 (내린 차례)
        d_no = [0]

        def start(mi, fi):
            busy_a.add(mi)
            busy_b.add(fi)
            duels.append(self._pair(d_no[0], mi, fi))
            d_no[0] += 1

        def match():
            free_a = [i for i, f in enumerate(self.a) if f.alive() and i not in busy_a]
            for mi in free_a:
                if waiting:
                    start(mi, waiting.pop(0))
                    continue
                rest = [j for j, f in enumerate(self.b) if f.alive() and j not in busy_b and j not in waiting]
                if rest:
                    start(mi, rest[0])
        match()
        while duels and self.turns < self.turn_cap:
            self.turns += 1
            self.events.append({"t": "turn", "n": self.turns})
            for duel in list(duels):
                bt = duel["bt"]
                ev = bt.take_turn(bt.choose_mine())
                duel["turns"] += 1
                self.events.extend(dict(e, d=duel["d"]) for e in ev if e.get("t") != "over")
                if bt.over or not bt.me.alive() or not bt.foe.alive() or duel["turns"] >= PAIR_TURNS:
                    self._end(duel)
                    duels.remove(duel)
                    busy_a.discard(duel["mi"])
                    busy_b.discard(duel["fi"])
            match()
        left_a = sum(1 for f in self.a if f.alive())
        left_b = sum(1 for f in self.b if f.alive())
        # 공습을 다 쓰러뜨리고 하나라도 남았으면 승리. 전역 턴 상한에서 끊겼으면 남은 머릿수 (같으면 막지 못한 것)
        result = "win" if left_a > 0 and (left_b == 0 or left_a > left_b) else "lose"
        self.events.append({"t": "raid", "result": result, "turns": self.turns})
        return {"result": result, "events": self.events, "kos": self.kos, "turns": self.turns, "seed": self.seed}
