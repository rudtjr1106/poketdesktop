# -*- coding: utf-8 -*-
"""포스크탑 올림픽 공식 점검 — 모의 실험 (common/olympics.py 의 공식을 그대로 쓴다).

    python tools/olympic_sim.py [종보유.tsv 사람별종수.tsv] [--weeks N] [--players N]

공식 숫자를 바꿀 때마다 돌린다. **종목마다 한 종의 금메달 몫이 30% 를 넘으면 실패(종료 코드 1).**

입력(없으면 야생에 나오는 종을 고르게 가진다고 본다):
  종보유.tsv       '종 internal<TAB>그 종을 가진 사람 수' - 운영 DB 에서 읽은 것 (prodq.sh, 읽기만)
  사람별종수.tsv    '사람<TAB>가진 종 수'
운영 자료 파일은 저장소에 넣지 않는다.

가정: 절반은 기대 기록이 가장 좋은 포켓몬을 고르는 '계산형', 절반은 아끼는 7마리 중에서 고르는 '애정형'.
경기 날마다 70% 가 나오고, 나온 날 종목마다 60% 가 신청한다. 응원 타입 · 지침은 실제 일정 그대로.
"""
import argparse
import collections
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from common import olympics as O            # noqa: E402

LIMIT = 0.30


def load_tsv(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 2 and parts[1].strip().isdigit():
                out.append((parts[0].strip(), int(parts[1])))
    return out


def make_players(rng, sp, own, uk, n):
    names = [k for k, _ in own]
    weights = [w for _, w in own]
    players = []
    for _ in range(n):
        k = min(rng.choice(uk), len(names))
        owned = set()
        while len(owned) < k:
            owned.update(rng.choices(names, weights=weights, k=k - len(owned)))
        mons = []
        for x in owned:
            s = sp[x]
            abil = list(s.get("abil") or []) + ([s["hidden"]] if s.get("hidden") else [])
            mons.append((s, rng.choice(abil) if abil else None))
        players.append({"owned": mons, "fav": rng.sample(mons, min(7, len(mons))),
                        "style": "opt" if rng.random() < 0.5 else "fav",
                        "tactic": rng.choice(("safe", "bold"))})
    return players


def week(rng, players, pct):
    best = dict((e, {}) for e in O.KEYS)
    prev = {}
    for day in O.DAYS:
        cheer = O.cheer_of(day)
        fat = dict((ev, O.fatigue_map(c)) for ev, c in prev.items())
        counts = dict((e, collections.Counter()) for e in O.KEYS)
        for pi, p in enumerate(players):
            if rng.random() > 0.7:
                continue
            used = set()
            for ev in O.KEYS:
                if rng.random() > 0.6:
                    continue
                pool = p["owned"] if p["style"] == "opt" else p["fav"]
                cand = [(s, a) for s, a in pool if s["internal"] not in used]
                if not cand:
                    continue
                if p["style"] == "opt":
                    s, a = max(cand, key=lambda c: O.expect(
                        O.mods(ev, c[0], c[1], pct, cheer, fat.get(ev, {}).get(c[0]["internal"], 0.0))))
                else:
                    s, a = rng.choice(cand)
                used.add(s["internal"])
                counts[ev][s["internal"]] += 1
                got = O.play(ev, s, a, p["tactic"], pct, cheer, fat.get(ev, {}).get(s["internal"], 0.0),
                             seed=rng.randrange(1 << 30))
                rec = got["record"]
                if rec is None:
                    continue
                cur = best[ev].get(pi)
                if cur is None or O.better(ev, rec, cur[0]):
                    best[ev][pi] = (rec, s["internal"], p["style"])
        prev = dict((ev, dict(c)) for ev, c in counts.items())
    return dict((ev, sorted(best[ev].values(), key=lambda x: O.rank_key(ev, x[0]))[:3]) for ev in O.KEYS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--weeks", type=int, default=30)
    ap.add_argument("--players", type=int, default=240)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    dex = json.load(open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8"))
    sp = dict((s["internal"], s) for s in dex["species"])
    pct = O.build_pct(dex["species"])
    if len(a.files) == 2:
        own = [(k, n) for k, n in load_tsv(a.files[0]) if k in sp]
        uk = [n for _, n in load_tsv(a.files[1])]
        src = "운영 자료 (%d종, %d명)" % (len(own), len(uk))
    else:
        own = [(s["internal"], 1) for s in dex["species"] if s.get("spawnable")]
        rr = random.Random(1)
        uk = [rr.randint(15, 120) for _ in range(300)]
        src = "고르게 가졌다고 가정 (운영 자료 없음)"
    rng = random.Random(a.seed)
    golds = dict((e, collections.Counter()) for e in O.KEYS)
    pod = collections.Counter()
    fav = total = 0
    for _ in range(a.weeks):
        med = week(rng, make_players(rng, sp, own, uk, a.players), pct)
        for ev in O.KEYS:
            if med[ev]:
                golds[ev][med[ev][0][1]] += 1
            for _rec, s, style in med[ev]:
                pod[s] += 1
                total += 1
                fav += style == "fav"
    print("== %s · %d주 · %d명 · 메달 %d개" % (src, a.weeks, a.players, total))
    print("  메달을 딴 서로 다른 종 %d종 · 가장 많이 딴 5종 몫 %.0f%% · 애정형 메달 %.0f%%"
          % (len(pod), 100.0 * sum(c for _, c in pod.most_common(5)) / max(1, total), 100.0 * fav / max(1, total)))
    bad = []
    for ev in O.KEYS:
        g = golds[ev]
        n = sum(g.values()) or 1
        top_k, top_c = (g.most_common(1) or [("-", 0)])[0]
        share = top_c / float(n)
        names = ", ".join("%s %d" % (sp[k]["kr"], c) for k, c in g.most_common(3))
        flag = "  <-- 30%% 넘음" if share > LIMIT else ""
        print("  %-10s 금 %d번 · 서로 다른 종 %d · 한 종 최대 %.0f%% (%s)%s"
              % (O.EV[ev]["kr"], n, len(g), share * 100, names, flag))
        if share > LIMIT:
            bad.append(ev)
    if bad:
        print("실패: %s" % ", ".join(O.EV[e]["kr"] for e in bad))
        return 1
    print("통과: 종목마다 한 종의 금메달 몫이 %d%% 이하" % int(LIMIT * 100))
    return 0


if __name__ == "__main__":
    sys.exit(main())
