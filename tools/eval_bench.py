# -*- coding: utf-8 -*-
"""길드전 · 랭크 AI 의 셈 설정 견주기 (2026-11-01) - 형세 평가식 · 헛수 감점.

    python tools/eval_bench.py --cand new --base old --pairs 500 --seeds 1 --jobs 7    # 랭크 판 맞대결
    python tools/eval_bench.py --cand new --base old --depth 2 --ai-seeds 2 ...        # 길드전만큼 깊게 셈하고
    python tools/eval_bench.py --proxy switcher --cand new --pairs 400 --seeds 1       # 사람 대역 상대 (war_ai_bench)
    python tools/eval_bench.py --cand new --base new --pairs 800 --feel                # 멍청해 보이는 수 세기

설정 (TrainerBattle 의 클래스 값을 쪽마다 바꿔 끼운다, CONFIGS):
  old    11/01 전: 예전 형세 평가 · 헛수 감점 없음 · 길드전 무효 공격 감점 없음 · 길드전 교체 버릇 감점 없음.
  new    지금 코드 그대로: poke-engine 형세 평가(WAR_PE_EVAL) · 헛수 감점 · 무효 공격 감점 · 길드전 교체 버릇 감점(WAR_SWITCH_HABIT).
  pe     poke-engine 형세 평가만.
  waste  예전 형세 평가 + 헛수 감점들만.

11/01 기록 (new 를 넣기 전, 예전 식 대비): poke-engine 식은 랭크 1,000판 49.5% · 길드전 깊이 600판 50.4% · 사람 대역 상대
600판 방어 64.7% -> 64.8% (모두 오차 안), 같은 판에서 수가 8.3% 갈림. 예전 식 + 빠진 항목(대타출동 · 씨뿌리기 · 혼란 ·
도구)은 50.1% · 48.8%, 수가 1.5% 만 갈림.
new (poke-engine + 헛수 · 무효 공격 · 교체 버릇 감점) 대 old: 랭크 1,000판 49.5% (±3.1) · 사람 대역 상대 600판 방어
64.7% -> 65.0% (짝지은 마진 차 -0.06 ± 0.32). 멍청해 보이는 수(--feel) 판 100개당 랭크 25.7 -> 16.8 · 길드전 48.9 -> 25.0.

맞대결은 시즌 5 랭크 판(party_battle, 양쪽 다 길드전 AI)으로 둔다. 쪽마다 설정만 다르고 나머지는 같다.
같은 쌍 · 같은 시드를 자리를 바꿔 한 번 더 둔다. 판의 셈 시간 상한은 넉넉히 둔다 - 시간이 아니라 식을 잰다.
--proxy 는 길드전 판(사람 대역이 공격, AI 가 방어)에서 방어 승률을 잰다 (tools/war_ai_bench.py 그대로).
DB · 서버를 건드리지 않는다 (계산만).
"""
import argparse
import collections
import json
import math
import multiprocessing
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ranked_war_bench as RB                                                # noqa: E402
import war_ai_bench as WB                                                    # noqa: E402

_G = {}

KEYS = ("WAR_PE_EVAL", "WAR_WASTE_PEN", "WAR_NOEFFECT_PEN", "WAR_SWITCH_HABIT")
CONFIGS = {
    "old": {"WAR_PE_EVAL": False, "WAR_WASTE_PEN": 0.0, "WAR_NOEFFECT_PEN": 0.0, "WAR_SWITCH_HABIT": False},
    "new": None,                                                            # 코드의 값 그대로 (_setup 이 채운다)
    "pe": {"WAR_PE_EVAL": True, "WAR_WASTE_PEN": 0.0, "WAR_NOEFFECT_PEN": 0.0, "WAR_SWITCH_HABIT": False},
    "waste": {"WAR_PE_EVAL": False, "WAR_WASTE_PEN": 0.3, "WAR_NOEFFECT_PEN": 0.3, "WAR_SWITCH_HABIT": True},
}


def _setup(root, depth, ai_seeds):
    RB._setup(root, 1)
    from common import abilities as A, battle as B, held as H, movecalc as MC, statusmoves as SM   # noqa: E402
    TB, PB = RB._G["TB"], RB._G["PB"]
    _G.update(A=A, B=B, H=H, MC=MC, SM=SM, TB=TB, PB=PB)
    CONFIGS["new"] = dict((k, getattr(TB.TrainerBattle, k)) for k in KEYS)
    PB.WAR_MATCH_BUDGET = 10 ** 6          # 판의 시간 상한에 걸려 셈 없이 두는 수가 섞이지 않게
    PB.WAR_TURN_CAP = 30.0
    if depth is not None:
        PB._RankedWar.WAR2_DEPTH = depth
    if ai_seeds is not None:
        PB._RankedWar.WAR2_SEEDS = ai_seeds


def _use(name):
    """TrainerBattle 에 설정을 끼운다. 거울 판(_RankedWar)은 WAR_NOEFFECT_PEN 만 따로 가져서(0.3) 그대로다."""
    for k, v in CONFIGS[name].items():
        setattr(_G["TB"].TrainerBattle, k, v)


# ---- 체감 (--feel): 사람이 보면 '아 멍청하네' 할 수 ----
def _is_setup(md):
    return bool(md.get("statSelf") and not md.get("power") and any(c > 0 for _s, c in (md.get("stat") or [])))


def dumb_move(bt, dex, user, target, own, opp, key, md):
    """이 기술이 지금 헛수인가 - 항목 이름 또는 None. 고르는 순간(턴을 열기 전)의 판을 본다."""
    A, B, MC, SM = _G["A"], _G["B"], _G["MC"], _G["SM"]
    if not key or key == B.STRUGGLE or not target.alive():
        return None
    if MC.attacks(md):
        if A.would_block(user, target, md) or B.damage(dex, md, user, target, B.EST_RNG, crit=False)[2] == 0:
            return "효과 없는 공격"
        return None
    if key in SM.HAZARD_MOVES:
        name, most = SM.HAZARD_MOVES[key]
        return "깔기를 또 깖" if (opp.get(name) or 0) >= most else None
    if key in SM.SCREENS or key in SM.SIDE_MOVES:
        name = SM.SCREENS.get(key) or SM.SIDE_MOVES[key][0]
        return "벽·순풍을 또 세움" if own.get(name) else None
    if key in SM.PROTECTS and user.cond.get("streak"):
        return "방어를 연달아"
    if _is_setup(md) and all(user.stages.get(s, 0) >= 6 for s, c in md["stat"] if c > 0):
        return "랭크가 꽉 찼는데 또 올림"
    if (md.get("heal") or 0) > 0 and user.hp >= user.maxhp:
        return "체력이 가득한데 회복"
    try:
        if bt._status_score(md, bt.best_damage(user, target), user, target) <= 0:
            return "소용없는 변화기 (엔진 판정)"
    except Exception:                                   # noqa: BLE001
        return None
    return None


class Feel(object):
    """AI 한쪽이 한 판에서 둔 수 가운데 멍청해 보이는 것을 센다."""

    def __init__(self):
        self.n = collections.Counter()
        self.came_in = {}           # 자리 -> (들어온 턴, 그때 상대) - 그다음 턴부터 싸운다
        self.went_out = {}          # 자리 -> 스스로 물러난 턴
        self.pending = None         # (항목, 포켓몬, 설명) - 그 턴이 끝났을 때 쓰러졌으면 센다
        self.samples = {}

    def note(self, label, text):
        self.n[label] += 1
        box = self.samples.setdefault(label, [])
        if len(box) < 3:
            box.append(text)

    def choice(self, bt, dex, user, target, own, opp, turn, team, cur, slot, key):
        self.n["고른 수"] += 1
        if slot is None and user.status in ("sleep", "freeze"):
            self.n["잠들거나 얼어서 못 쓰는 수"] += 1       # 화면에는 '잠들어 있다' 만 나온다 - 무엇을 골랐는지 안 보인다
            return
        if slot is not None:
            self.n["교체"] += 1
            into = team[slot]
            came, was = self.came_in.get(cur, (-99, None))
            if came == turn - 1:
                self.note("막 들어온 포켓몬을 바로 뺌", "T%d %s -> %s" % (turn, user.name, into.name))
                if was is target:
                    self.note("  그중 상대는 그대로인데", "T%d %s -> %s (상대 %s)" % (turn, user.name, into.name,
                                                                            target.name))
            if turn - self.went_out.get(slot, -99) <= 2:
                self.note("방금 뺀 포켓몬을 도로 넣음", "T%d %s -> %s" % (turn, user.name, into.name))
            self.went_out[cur], self.came_in[slot] = turn, (turn, target)
            self.pending = ("바꿔 넣자마자 쓰러짐", into, "T%d %s -> %s (상대 %s)" % (turn, user.name, into.name,
                                                                              target.name))
            return
        md = (bt.move_of(key) or {}) if key else {}
        label = dumb_move(bt, dex, user, target, own, opp, key, md)
        if label:
            self.note(label, "T%d %s 의 %s (상대 %s)" % (turn, user.name, md.get("kr") or key, target.name))
        if _is_setup(md):
            self.n["랭크업"] += 1
            self.pending = ("랭크업한 턴에 쓰러짐", user, "T%d %s 의 %s (상대 %s)" % (
                turn, user.name, md.get("kr") or key, target.name))

    def sent(self, slot, turn, target):
        self.came_in[slot] = (turn, target)

    def turn_over(self):
        if self.pending and not self.pending[1].alive():
            self.note(self.pending[0], self.pending[2])
        self.pending = None

    def dump(self):
        return {"n": dict(self.n), "samples": self.samples}


def _duel_class():
    PB = _G["PB"]

    class Duel(PB.PartyBattle):
        def _war_plan(self, who):
            if self.agree is not None and who == self.cand_side:
                # 같은 판 · 같은 난수로 base 식이면 무엇을 골랐을지 먼저 보고 되돌린다 (--agree)
                keep = (self.ai_rng.getstate(), self.war_spent, dict(self.war_stats), dict(self.war_stall[who]))
                _use(self.evals[PB._FLIP[who]])
                try:
                    alt = PB.PartyBattle._war_plan(self, who)
                finally:
                    _use("new")
                self.ai_rng.setstate(keep[0])
                self.war_spent, self.war_stats, self.war_stall[who] = keep[1], keep[2], keep[3]
                got = self._plan_real(who)
                k = "same" if got == alt else ("diff_switch" if (got[0] is not None or alt[0] is not None)
                                               else "diff_move")
                self.agree[k] = self.agree.get(k, 0) + 1
                return got
            return self._plan_real(who)

        def _plan_real(self, who):
            _use(self.evals[who])
            t0 = time.time()
            try:
                got = PB.PartyBattle._war_plan(self, who)
            finally:
                self.think[who].append(time.time() - t0)
                _use("new")
            if self.feel is not None:
                bt, other = self.bt, PB._FLIP[who]
                team, cur = (self.a, self.ia) if who == "me" else (self.b, self.ib)
                self.feel[who].choice(bt, self.dex, bt.fighter(who), bt.fighter(other), self.field.side(who),
                                      self.field.side(other), self.turns + 1, team, cur, got[0], got[1])
            return got

        def _war_turn(self, bt):
            ev = PB.PartyBattle._war_turn(self, bt)
            if self.feel is not None:
                for f in self.feel.values():
                    f.turn_over()
            return ev

        def _war_next(self, who, single):
            _use(self.evals[who])
            try:
                nxt = PB.PartyBattle._war_next(self, who, single)
            finally:
                _use("new")
            if self.feel is not None and nxt is not None:
                opp = (self.b, self.ib) if who == "me" else (self.a, self.ia)
                self.feel[who].sent(nxt, self.turns, opp[0][opp[1]])
            return nxt
    return Duel


def _proxy_hooks():
    """길드전 판(TrainerBattle, AI = foe) 에서 AI 의 수를 Feel 로 센다. 셈 사본(_sim)은 빼고."""
    if _G.get("hooked"):
        return
    _G["hooked"] = True
    cls = _G["TB"].TrainerBattle
    choice, pick, act = cls._war_choice, cls._war_pick, cls.act

    def feel(self):
        f = self.__dict__.get("_feel")
        if f is None:
            f = self._feel = Feel()
            _G["feels"].append(f)
        return f

    def war_choice(self):
        got = choice(self)
        if not getattr(self, "_sim", False):
            fld = self.bt.field
            feel(self).choice(self.bt, self.dex, self.foe, self.me, fld.side("foe"), fld.side("me"), self.turn,
                              self.foe_team, self.fi, got[0], got[1])
        return got

    def war_pick(self):
        nxt = pick(self)
        if not getattr(self, "_sim", False) and nxt is not None:
            feel(self).sent(nxt, self.turn, self.me)
        return nxt

    def act_hook(self, kind, value=None, **kw):
        ev = act(self, kind, value, **kw)
        if not getattr(self, "_sim", False) and "_feel" in self.__dict__:
            self._feel.turn_over()
        return ev
    cls._war_choice, cls._war_pick, cls.act = war_choice, war_pick, act_hook


def one(args):
    a, b, seed, cand_side, cand, base = args[:6]
    agree = args[6] if len(args) > 6 else False
    feel = args[7] if len(args) > 7 else False
    other = "foe" if cand_side == "me" else "me"
    pb = _G["Duel"](RB._G["dex"], RB.team(a), RB.team(b), seed=seed,
                    keystone={"me": True, "foe": True}, zring={"me": True, "foe": True}, war_ai=True)
    pb.evals = {cand_side: cand, other: base}
    pb.think = {"me": [], "foe": []}
    pb.cand_side = cand_side
    pb.agree = {} if agree else None
    pb.feel = {"me": Feel(), "foe": Feel()} if feel else None
    out = pb.run()
    return {"a": a, "b": b, "seed": seed, "cand_side": cand_side, "winner": out["winner"], "turns": out["turns"],
            "think_cand": pb.think[cand_side], "think_base": pb.think[other],
            "stats": dict(getattr(pb, "war_stats", None) or {}), "agree": pb.agree,
            "feel": [dict(f.dump(), eval=pb.evals[w]) for w, f in pb.feel.items()] if feel else None}


def one_proxy(args):
    name, wargs, feel = args
    _use(name)
    if feel:
        _proxy_hooks()
        _G["feels"] = []
    r = WB.one(wargs)
    if feel:
        r["feel"] = [dict(f.dump(), eval=name) for f in _G["feels"]]
    return r


def _init(root, depth, ai_seeds):
    _setup(root, depth, ai_seeds)
    _G["Duel"] = _duel_class()
    WB._setup(root)


def pairs(n):
    """서로 다른 (a, b) 쌍 n 개 (결정적). ranked_war_bench · war_ai_bench 의 pairs 는 팀 수(49)마다 되풀이돼서
    서로 다른 쌍이 48 개뿐이다 - 판을 늘려도 같은 쌍을 다시 두게 된다."""
    import random
    k = len(RB._G["teams"])
    allp = [(x, y) for x in range(k) for y in range(k) if x != y]
    random.Random(20261101).shuffle(allp)
    return allp[:n]


def _sum_agree(rows):
    out = {}
    for r in rows:
        for k, v in (r.get("agree") or {}).items():
            out[k] = out.get(k, 0) + v
    return out or None


def _sum_feel(rows):
    """평가식마다: AI 쪽 판 수, 항목별 100판당 횟수, 보기 몇 개."""
    out = {}
    for r in rows:
        for f in r.get("feel") or []:
            e = out.setdefault(f["eval"], {"ai_battles": 0, "n": collections.Counter(), "samples": {}})
            e["ai_battles"] += 1
            e["n"].update(f["n"])
            for k, xs in f["samples"].items():
                box = e["samples"].setdefault(k, [])
                box.extend(xs[:max(0, 4 - len(box))])
    for e in out.values():
        b = float(e["ai_battles"] or 1)
        e["per100"] = dict((k, round(100 * v / b, 1)) for k, v in sorted(e["n"].items()))
        e["n"] = dict(e["n"])
    return out or None


def _ms(xs, p):
    xs = sorted(xs)
    return round(1000 * xs[min(len(xs) - 1, int(p * len(xs)))], 1) if xs else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", choices=tuple(CONFIGS), default="new")
    ap.add_argument("--base", choices=tuple(CONFIGS), default="old")
    ap.add_argument("--pairs", type=int, default=60)
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--depth", type=int, help="셈 깊이 (랭크 1, 길드전 2)")
    ap.add_argument("--ai-seeds", type=int, help="사람의 수마다 굴리는 난수 수 (랭크 1, 길드전 2)")
    ap.add_argument("--proxy", choices=("greedy", "switcher"), help="맞대결 대신 사람 대역 상대 길드전 방어")
    ap.add_argument("--agree", action="store_true", help="같은 판에서 두 식이 다른 수를 고르는 비율도 잰다 (두 배 느림)")
    ap.add_argument("--feel", action="store_true", help="멍청해 보이는 수 · 교체 버릇을 센다 (체감)")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--json")
    a = ap.parse_args()
    _init(ROOT, a.depth, a.ai_seeds)
    t0 = time.time()
    if a.proxy:
        work = [(a.cand, (ROOT, "new", a.proxy, d, at, s, 50, [], False), a.feel)
                for d, at in pairs(a.pairs) for s in range(1, a.seeds + 1)]
        with multiprocessing.Pool(a.jobs, initializer=_init, initargs=(ROOT, a.depth, a.ai_seeds)) as pool:
            rows = pool.map(one_proxy, work, chunksize=1)
        out = WB.summarize(rows)
        out["feel"] = _sum_feel(rows)
        out.update({"eval": a.cand, "proxy": a.proxy, "pairs": a.pairs, "seeds": a.seeds,
                    "wall_sec": round(time.time() - t0, 1)})
        print(json.dumps(out, ensure_ascii=False))
        if a.json:
            with open(a.json, "w", encoding="utf-8") as f:
                json.dump(dict(out, rows=[dict(r, think=None) for r in rows]), f, ensure_ascii=False, indent=1)
        return
    work = [(x, y, s, side, a.cand, a.base, a.agree, a.feel) for x, y in pairs(a.pairs) for s in range(1, a.seeds + 1)
            for side in (("me",) if a.cand == a.base else ("me", "foe"))]     # 같은 식끼리면 자리 바꾼 판은 같은 판
    with multiprocessing.Pool(a.jobs, initializer=_init, initargs=(ROOT, a.depth, a.ai_seeds)) as pool:
        rows = pool.map(one, work, chunksize=1)
    n = len(rows)
    won = sum(1 for r in rows if r["winner"] == r["cand_side"])
    draws = sum(1 for r in rows if r["winner"] == "draw")
    p = (won + 0.5 * draws) / float(n or 1)
    st = {}
    for r in rows:
        for k, v in r["stats"].items():
            st[k] = st.get(k, 0) + v
    tc = [t for r in rows for t in r["think_cand"]]
    tb = [t for r in rows for t in r["think_base"]]
    out = {"cand": a.cand, "base": a.base, "battles": n, "cand_win_rate": round(p, 4),
           "ci95": round(1.96 * math.sqrt(p * (1 - p) / float(n or 1)), 4), "draws": draws,
           "turns_mean": round(sum(r["turns"] for r in rows) / float(n or 1), 1),
           "think_ms": {"cand_mean": round(1000 * sum(tc) / float(len(tc) or 1), 1), "cand_p95": _ms(tc, 0.95),
                        "base_mean": round(1000 * sum(tb) / float(len(tb) or 1), 1), "base_p95": _ms(tb, 0.95)},
           "war_stats": st, "agree": _sum_agree(rows), "feel": _sum_feel(rows), "depth": a.depth, "ai_seeds": a.ai_seeds, "wall_sec": round(time.time() - t0, 1)}
    print(json.dumps(out, ensure_ascii=False))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(dict(out, rows=[dict(r, think_cand=None, think_base=None) for r in rows]), f,
                      ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
