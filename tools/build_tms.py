# -*- coding: utf-8 -*-
"""기술머신 자료를 만든다. `server/data/tms.json` 하나로 떨어진다.

## 왜 파일을 따로 두나

도감(pokedex.json)과 도구(items.json)에 나눠 넣을 수도 있었다. 그런데
기술머신은 **둘 다에 걸친다** - 도구이면서(가방에 들어간다) 종별 학습
자료이기도 하다(누가 무엇을 배울 수 있나). 한쪽에 욱여넣으면 다른 쪽을
고칠 때마다 같이 흔들린다. 게다가 학습 자료만 6만 줄이라, 도감에 섞으면
도감을 읽는 모든 곳이 그만큼 무거워진다.

## 무엇이 들어가나

    tms      번호 -> {기술, 이름, 세대}          358개
    learn    도감번호 -> [배울 수 있는 번호들]    1016종

**모든 세대의 기술머신을 합친다.** 스칼렛/바이올렛만 쓰면 229개인데,
팔데아에 안 나오는 종(캐터피 계열, 아보 등 288종)은 줄이 아예 없어서
기술머신을 하나도 못 쓰게 된다. 세대를 합치면 1016종까지 덮는다.

번호는 **스칼렛/바이올렛 것을 먼저** 그대로 쓰고(1~229), 거기 없는 것을
뒤에 잇는다(230~358). 최신판을 해 본 사람에게 번호가 익숙한 편이 낫다.

기술머신을 아예 못 쓰는 종이 9마리 있다(단데기·번데기·메타몽·루브도·
개무소 계열·코스모그·두르봉). 자료가 없는 게 아니라 원래 그렇다.

## 돌리는 법

    python tools/build_tms.py

받은 CSV 는 tools/_cache 에 남는다. pokemon_moves.csv 가 10MB 라
매번 받으면 오래 걸린다.
"""
import argparse
import csv
import io
import json
import os
import sys
import urllib.request

CSV_BASE = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")
NEEDED = ["machines.csv", "pokemon_moves.csv", "version_groups.csv",
          "moves.csv"]

KO = 3
MACHINE = 4          # pokemon_move_methods: 기술머신으로 배움
SV = "25"            # version_groups: scarlet-violet
MAX_DEX = 1025


def fetch(name):
    if not os.path.isdir(CACHE):
        os.makedirs(CACHE)
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        sys.stderr.write("  받는 중 %s\n" % name)
        with urllib.request.urlopen(CSV_BASE + "/" + name, timeout=600) as r:
            io.open(path, "wb").write(r.read())
    return path


def rows(name):
    with io.open(fetch(name), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            yield r


def as_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def build(pokedex_path):
    dex = json.load(io.open(pokedex_path, encoding="utf-8"))
    # 도감의 기술은 {내부이름: {...}} 다. 기술 id 로 찾을 수 있게 뒤집는다.
    by_id = {}
    for key, m in dex["moves"].items():
        by_id[m["id"]] = (key, m)

    gen_of = {}
    for r in rows("version_groups.csv"):
        gen_of[r["id"]] = as_int(r["generation_id"])

    # ---- 어떤 기술이 기술머신인가 -------------------------------------
    sv_no = {}          # 기술 id -> 스칼렛/바이올렛 번호
    seen = {}           # 기술 id -> (가장 높은 세대, 그 세대의 번호)
    for r in rows("machines.csv"):
        mid = as_int(r["move_id"])
        g = gen_of.get(r["version_group_id"], 0)
        if r["version_group_id"] == SV:
            sv_no[mid] = as_int(r["machine_number"])
        if mid not in seen or g > seen[mid][0]:
            seen[mid] = (g, as_int(r["machine_number"]))

    # 스칼렛/바이올렛 번호 순으로 먼저, 나머지는 세대·번호 순으로 뒤에.
    order = sorted(sv_no, key=lambda m: sv_no[m])
    rest = sorted((m for m in seen if m not in sv_no),
                  key=lambda m: (-seen[m][0], seen[m][1], m))
    order += rest

    tms = {}
    no_of_move = {}     # 기술 id -> 우리 번호
    skipped = []
    for i, mid in enumerate(order, 1):
        got = by_id.get(mid)
        if not got:
            # 도감에 없는 기술. 그런 기술머신은 낼 수 없다.
            skipped.append(mid)
            continue
        key, m = got
        tms[str(i)] = {
            "no": i,
            "move": key,
            "kr": m["kr"],
            "type": m["type"],
            "cat": m["cat"],
            "gen": seen[mid][0],
            # 스칼렛/바이올렛에 있는 번호. 없으면 우리가 새로 매긴 것이다.
            "sv": sv_no.get(mid),
        }
        no_of_move[mid] = i

    # ---- 누가 배울 수 있나 ---------------------------------------------
    learn = {}
    for r in rows("pokemon_moves.csv"):
        if as_int(r["pokemon_move_method_id"]) != MACHINE:
            continue
        num = as_int(r["pokemon_id"])
        if not 1 <= num <= MAX_DEX:
            continue          # 리전폼은 별도 id 라 여기서 걸러진다
        no = no_of_move.get(as_int(r["move_id"]))
        if no is None:
            continue
        learn.setdefault(num, set()).add(no)

    out_learn = dict((str(k), sorted(v)) for k, v in sorted(learn.items()))

    if skipped:
        sys.stderr.write("  도감에 없어서 뺀 기술 %d개\n" % len(skipped))

    return {
        "version": 1,
        "source": "PokeAPI (전 세대 기술머신 합집합)",
        "counts": {
            "tms": len(tms),
            "species": len(out_learn),
            "rows": sum(len(v) for v in out_learn.values()),
        },
        "tms": tms,
        "learn": out_learn,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="server/data/tms.json")
    ap.add_argument("--pokedex", default="server/data/pokedex.json")
    a = ap.parse_args()

    data = build(a.pokedex)
    d = os.path.dirname(os.path.abspath(a.out))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)

    c = data["counts"]
    mb = os.path.getsize(a.out) / 1048576.0
    print("  기술머신 %d개 · %d종 · 학습 %d줄  (%s, %.1fMB)"
          % (c["tms"], c["species"], c["rows"], a.out, mb))
    sv = sum(1 for t in data["tms"].values() if t["sv"] is not None)
    print("  스칼렛/바이올렛 번호 그대로 %d개, 옛 세대에서 가져온 것 %d개"
          % (sv, c["tms"] - sv))
    none = [n for n in range(1, MAX_DEX + 1) if str(n) not in data["learn"]]
    print("  기술머신을 하나도 못 쓰는 종 %d마리: %s"
          % (len(none), ", ".join(str(n) for n in none)))


if __name__ == "__main__":
    main()
