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
    learn    도감번호 -> [배울 수 있는 번호들]    1017종

**모든 세대의 기술머신을 합친다.** 스칼렛/바이올렛만 쓰면 229개인데,
팔데아에 안 나오는 종(캐터피 계열, 아보 등 288종)은 줄이 아예 없어서
기술머신을 하나도 못 쓰게 된다. 세대를 합치면 1016종(알 기술까지 1017종)을 덮는다.

번호는 **스칼렛/바이올렛 것을 먼저** 그대로 쓰고(1~229), 거기 없는 것을
뒤에 잇는다(230~358). 최신판을 해 본 사람에게 번호가 익숙한 편이 낫다.

기술머신을 아예 못 쓰는 종이 8마리 있다(뿔충이·딱충이·메타몽·루브도·
개무소 계열·코스모그). 자료가 없는 게 아니라 원래 그렇다. (두루지벌레는 알 기술 하나로 빠졌다.)

## 알 기술 (1.10.3)

**원작에서 알 기술로 배우는 것도 그 기술의 기술머신으로 배울 수 있다.** 이 게임에는 교배가 없어서
알 기술은 배울 길이 아예 없었다 - 아머까오의 날개쉬기가 그랬다 (원작에서는 파라꼬의 알 기술이다.
게시판 #156). 알 기술은 진화해도 남으므로 **진화 전 단계의 알 기술은 진화형도 배운다**
(자료에는 알 기술이 대개 맨 처음 단계에만 적혀 있다).

기술머신이 없는 기술은 여전히 못 배운다 (기술머신을 새로 만들지 않는다). 가르침 기술도 넣지 않았다.

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
EGG = 2              # 알 기술 (교배가 없으니 기술머신으로 배우게 한다)
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
    egg = {}            # 도감번호 -> 알 기술로 배우는 번호들 (기술머신이 있는 기술만)
    for r in rows("pokemon_moves.csv"):
        how = as_int(r["pokemon_move_method_id"])
        if how not in (MACHINE, EGG):
            continue
        num = as_int(r["pokemon_id"])
        if not 1 <= num <= MAX_DEX:
            continue          # 리전폼은 별도 id 라 여기서 걸러진다
        no = no_of_move.get(as_int(r["move_id"]))
        if no is None:
            continue
        (learn if how == MACHINE else egg).setdefault(num, set()).add(no)

    # ---- 알 기술: 그 기술의 기술머신으로 배운다. 진화 전 단계의 것은 진화형도 ----
    prevo = dict((s["num"], s.get("prevo")) for s in dex["species"])
    egg_rows = 0
    for num in sorted(prevo):
        got, cur, seen_nums = set(), num, set()
        while cur and cur not in seen_nums:               # 자기와 진화 전 단계들을 거슬러 올라간다
            seen_nums.add(cur)
            got |= egg.get(cur, set())
            cur = prevo.get(cur)
        add = got - learn.get(num, set())
        if add:
            learn.setdefault(num, set()).update(add)
            egg_rows += len(add)

    out_learn = dict((str(k), sorted(v)) for k, v in sorted(learn.items()))

    if skipped:
        sys.stderr.write("  도감에 없어서 뺀 기술 %d개\n" % len(skipped))

    return {
        "version": 2,
        "source": "PokeAPI (전 세대 기술머신 합집합 + 알 기술)",
        "counts": {
            "tms": len(tms),
            "species": len(out_learn),
            "rows": sum(len(v) for v in out_learn.values()),
            "eggRows": egg_rows,          # 그 가운데 알 기술이라서 들어간 줄
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
    print("  기술머신 %d개 · %d종 · 학습 %d줄 (그 가운데 알 기술 %d줄)  (%s, %.1fMB)"
          % (c["tms"], c["species"], c["rows"], c["eggRows"], a.out, mb))
    sv = sum(1 for t in data["tms"].values() if t["sv"] is not None)
    print("  스칼렛/바이올렛 번호 그대로 %d개, 옛 세대에서 가져온 것 %d개"
          % (sv, c["tms"] - sv))
    none = [n for n in range(1, MAX_DEX + 1) if str(n) not in data["learn"]]
    print("  기술머신을 하나도 못 쓰는 종 %d마리: %s"
          % (len(none), ", ".join(str(n) for n in none)))


if __name__ == "__main__":
    main()
