# -*- coding: utf-8 -*-
"""시즌 5 랭크(양쪽 다 길드전 AI) 벤치마크 - 한 판에 걸리는 시간과 옛 AI 와의 승률 (2026-10-29).

    python tools/ranked_war_bench.py --mode time --pairs 24 --seeds 2            # 한 판 시간 (양쪽 새 AI)
    python tools/ranked_war_bench.py --mode time --slow 3                        # 3배 느린 서버인 셈 치고
    python tools/ranked_war_bench.py --mode versus --pairs 24 --seeds 2 --jobs 6 # 새 AI(한쪽) 대 옛 AI(한쪽)
    python tools/ranked_war_bench.py --mode vsplain --pairs 24 --seeds 2 --jobs 6 # 새 AI 대 셈 없는 관장 AI 의 수 (셈의 몫)
    python tools/ranked_war_bench.py --mode old                                  # 옛 판(시즌 4)만 - 비교 기준

팀은 관장 자료(gyms.json)의 챔피언 · 사천왕 · 프런티어브레인 팀을 Lv.50 개체값 31 로 (tools/war_ai_bench.py 와 같다).
양쪽 다 키스톤 · Z링이 있다. versus 는 같은 쌍을 자리를 바꿔 한 번 더 둔다 (a 가 먼저 고르는 몫을 지운다).

--slow K: 셈이 보는 시계를 K 배로 빨리 간다 = K 배 느린 기계에서 시간 상한이 걸리는 모양. 나오는 시간도 K 배로 적는다.
DB · 서버를 건드리지 않는다 (계산만).
"""
import argparse
import json
import multiprocessing
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLES = ("챔피언", "사천왕", "프런티어브레인")
STALL_EXTRA = ("SUBSTITUTE", "WISH", "REST")

_G = {}


class _FastClock(object):
    """time 모듈 대신 - time() 만 K 배로 간다."""

    def __init__(self, k):
        self.k = k
        self.t0 = time.time()

    def time(self):
        return self.t0 + (time.time() - self.t0) * self.k

    def __getattr__(self, name):
        return getattr(time, name)


def _setup(root, slow):
    if root not in sys.path:
        sys.path.insert(0, root)
    from common import party_battle as PB, pokelogic as P, trainer_battle as TB      # noqa: E402
    if slow and slow != 1:
        PB.time = TB.time = _FastClock(slow)
    data = os.path.join(root, "server", "data")
    _G.update(PB=PB, TB=TB, dex=P.Pokedex.load(os.path.join(data, "pokedex.json")))
    with open(os.path.join(data, "gyms.json"), encoding="utf-8") as f:
        gyms = json.load(f)
    _G["teams"] = [(t["name"], t["team"]) for t in gyms["trainers"] if t.get("role") in ROLES]


def team(i):
    TB = _G["TB"]
    return [TB.trainer_mon(dict(e, level=50, iv=31)) for e in _G["teams"][i][1]]


def pairs(n):
    k = len(_G["teams"])
    out, i = [], 0
    while len(out) < n:
        d, a = i % k, (i * 7 + 3) % k
        if d != a:
            out.append((a, d))
        i += 1
    return out


def classify(bt, f, slot, key):
    from common import statusmoves as SM                                     # noqa: E402
    if slot is not None:
        return "switch"
    md = bt.move_of(key) or {} if key else {}
    if key in SM.HAZARD_MOVES:
        return "hazard"
    if md.get("statSelf") and any(c > 0 for _s, c in (md.get("stat") or [])) and not md.get("power"):
        return "setup"
    if (md.get("heal") or 0) > 0 and not md.get("power") or key in SM.PROTECTS or key in STALL_EXTRA:
        return "stall"
    return "attack"


def _battle_class(old_side, plain=False):
    """old_side 쪽만 예전 랭크 AI(choose_for · 상성 교체)로 두는 PartyBattle. None 이면 양쪽 새 AI 그대로.

    plain: old_side 를 예전 AI 대신 '셈 없는 관장 AI 의 수'(판 시간 상한을 다 썼을 때 두는 수)로 - 셈의 몫만 잰다.
    """
    PB = _G["PB"]

    class Bench(PB.PartyBattle):
        def _war_plan(self, who):
            if who == old_side and plain:
                m = self._mirror(who)
                m.turn += 1
                slot = m._foe_wants_switch()
                out = (slot, None) if slot is not None else (None, m._foe_move())
            elif who == old_side:
                bt = self.bt
                key = bt.choose_for(bt.fighter(who), bt.fighter(PB._FLIP[who]), "trainer")
                out = (None, key)
            else:
                out = PB.PartyBattle._war_plan(self, who)
            k = classify(self.bt, self.bt.fighter(who), *out)
            box = self.kinds if who != old_side else self.kinds_old
            box[k] = box.get(k, 0) + 1
            return out

        def _war_next(self, who, single):
            if who == old_side and plain:
                m = self._mirror(who)
                return m._pick(m.foe_team, m.me)
            if who == old_side:
                team = self.a if who == "me" else self.b
                opp = (self.b if who == "me" else self.a)[self.ib if who == "me" else self.ia]
                return self._pick_against(team, opp)
            return PB.PartyBattle._war_next(self, who, single)

        def _move_switch(self, who, mode, ev, key, state=None):
            if who != old_side or mode == "drag" or plain:
                return PB.PartyBattle._move_switch(self, who, mode, ev, key, state)
            war, self.war_ai = self.war_ai, False          # 옛 쪽은 옛 고르기 (상성)
            try:
                return PB.PartyBattle._move_switch(self, who, mode, ev, key, state)
            finally:
                self.war_ai = war
    return Bench


def one(args):
    root, mode, a, b, seed, slow, new_side = args
    if "PB" not in _G:
        _setup(root, slow)
    PB = _G["PB"]
    old_side = None if mode not in ("versus", "vsplain") else ("foe" if new_side == "me" else "me")
    cls = _battle_class(old_side, plain=mode == "vsplain")
    pb = cls(_G["dex"], team(a), team(b), seed=seed, keystone={"me": True, "foe": True},
             zring={"me": True, "foe": True}, war_ai=mode != "old")
    pb.kinds, pb.kinds_old = {}, {}
    t0 = time.time()
    out = pb.run()
    wall = (time.time() - t0) * (slow or 1)
    ev = out["events"]
    timeouts = sum(1 for e in ev if e.get("t") == "flee")
    return {"a": a, "b": b, "seed": seed, "winner": out["winner"], "turns": out["turns"], "wall": wall,
            "new_side": new_side, "kinds": pb.kinds, "kinds_old": pb.kinds_old, "timeouts": timeouts,
            "rounds": [e for e in ev if e.get("t") == "match"][0]["rounds"],
            "stats": getattr(pb, "war_stats", None), "spent": getattr(pb, "war_spent", 0.0) * (slow or 1)}


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else 0.0


def summarize(rows, mode):
    walls = [r["wall"] for r in rows]
    out = {"mode": mode, "battles": len(rows),
           "wall_sec": {"median": round(pct(walls, 0.5), 3), "p95": round(pct(walls, 0.95), 3),
                        "max": round(max(walls or [0]), 3), "mean": round(sum(walls) / float(len(walls) or 1), 3)},
           "turns_mean": round(sum(r["turns"] for r in rows) / float(len(rows) or 1), 1),
           "turns_max": max([r["turns"] for r in rows] or [0]),
           "round_timeouts": sum(r["timeouts"] for r in rows),
           "draws": sum(1 for r in rows if r["winner"] == "draw")}
    kinds = {}
    for r in rows:
        for k, n in (r["kinds"] or {}).items():
            kinds[k] = kinds.get(k, 0) + n
    out["new_ai_moves"] = kinds
    old = {}
    for r in rows:
        for k, n in (r.get("kinds_old") or {}).items():
            old[k] = old.get(k, 0) + n
    if old:
        out["old_ai_moves"] = old            # versus: 옛 AI 쪽 (vsplain: 셈 없는 관장 AI 쪽)
    st = {}
    for r in rows:
        for k, n in (r["stats"] or {}).items():
            st[k] = st.get(k, 0) + n
    out["war_stats"] = st
    if mode in ("versus", "vsplain"):
        won = sum(1 for r in rows if r["winner"] == r["new_side"])
        out["new_win_rate"] = round((won + 0.5 * out["draws"]) / float(len(rows) or 1), 4)
    else:
        out["a_win_rate"] = round(sum(1 for r in rows if r["winner"] == "me") / float(len(rows) or 1), 4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("time", "versus", "vsplain", "old"), default="time")
    ap.add_argument("--pairs", type=int, default=24)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--jobs", type=int, default=1, help="시간을 잴 때는 1 (여럿이면 서로 CPU 를 뺏는다)")
    ap.add_argument("--slow", type=float, default=1.0)
    ap.add_argument("--set", action="append", default=[], help="실험: party_battle 의 상수 NAME=VALUE")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--json")
    a = ap.parse_args()
    _setup(a.root, a.slow)
    _apply(a.set)
    sides = ("me", "foe") if a.mode in ("versus", "vsplain") else ("me",)
    work = [(a.root, a.mode, x, y, s, a.slow, side) for x, y in pairs(a.pairs) for s in range(1, a.seeds + 1)
            for side in sides]
    if a.jobs > 1:
        with multiprocessing.Pool(a.jobs, initializer=_init_worker, initargs=(a.root, a.slow, a.set)) as pool:
            rows = pool.map(one, work, chunksize=1)
    else:
        rows = [one(w) for w in work]
    out = summarize(rows, a.mode)
    out.update({"pairs": a.pairs, "seeds": a.seeds, "slow": a.slow, "set": a.set})
    print(json.dumps(out, ensure_ascii=False))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(dict(out, rows=rows), f, ensure_ascii=False, indent=1)


def _apply(sets):
    """WAR2_* 는 거울 판(_RankedWar)의 셈 양, 나머지는 party_battle 의 상수."""
    for kv in sets:
        k, v = kv.split("=", 1)
        if k.startswith("WAR2_"):
            setattr(_G["PB"]._RankedWar, k, int(v) if k.endswith(("DEPTH", "SEEDS")) else float(v))
        else:
            setattr(_G["PB"], k, float(v))


def _init_worker(root, slow, sets):
    _setup(root, slow)
    _apply(sets)


if __name__ == "__main__":
    main()
