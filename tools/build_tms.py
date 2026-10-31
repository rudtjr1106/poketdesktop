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

기술머신이 없는 기술은 여전히 못 배운다 (기술머신을 새로 만들지 않는다) - 그런 알 기술은 1.13.3 부터
기술 떠올리기로 배운다 (tools/add_reminder.py).

## 가르침 기술 (1.13.3)

**본가 최신작에서 가르치기(기술 가르침)로 배우는 기술도 그 기술의 기술머신으로 배운다.** 2026-10-20 전수 검사
(tools/learn_audit.py)에서 최신작이 소드실드 · 울트라썬문인 132종이 그 게임의 가르침 기술 56가지를 못 배웠다
(메테오빔 · 용성군 · 코골기 …). 기술머신이 있는 43가지는 여기서, 없는 13가지는 떠올리기로 메운다.
**최신작 것만** 넣는다 (사용자 결정) - 전 세대 가르침을 다 합치면 722종 2,758줄이 늘어 흉내내기 · 탁쳐서떨구기
같은 기술이 대거 풀린다. '최신작' 은 tools/learn_ref.py 가 고른다.

## 레전즈 Z-A 에만 있는 기술머신 (1.13.4)

**레전즈 Z-A · 메가디멘션에만 있는 기술머신 18개는 Z-A 에서 그 기술머신으로 배우는 포켓몬이 배운다.**
2026-10-22 게시판 #313 (Leica) '더블촙 기술머신을 배울 수 있는 포켓몬이 없다'. 기술머신 목록은 모든 판의
machines.csv 를 합쳐 만드는데, PokeAPI 에는 Z-A 의 '누가 기술머신으로 배우나' 가 비어 있어서 이 18개는 알 기술 ·
가르침 기술로 우연히 붙은 것뿐이었다 - 더블촙 · 마그넷봄 0종, 절대영도 1종 … (쇼다운 Z-A 학습표보다 416줄 적었다).
쇼다운의 Z-A 학습표(learn_ref.za_codes)에서 그 기술이 기술머신("9M")인 종을 붙인다. 본편에도 있는 기술머신은
건드리지 않는다 (본편 자료로 이미 덮인다). 폼(영원의 꽃 플라엣테 등)은 원래 종 이름이 아니라서 빠진다.

## 떠올리기 기술 (2.0)

**떠올리기로 배우는 기술(도감의 remind - tools/add_reminder.py)에 기술머신이 있으면 그 기술머신으로도 배운다.**
2026-10-30 게시판 #382 '번치코 떠올리기에는 드레인펀치가 있는데 드레인펀치 기술머신에는 번치코가 안 나온다' - 메가 종에
Z-A 학습표 기술을 떠올리기로 넣으면서(1.13.4) 기술머신 표와 어긋났다 (77종 253줄). 이미 떠올리기로 배울 수 있는
기술이라 새로 배우는 기술은 없다 (사용자 결정 - Z-A 기술머신 줄 955개를 다 여는 쪽은 안 함).
그래서 **add_reminder 다음에도 돌린다**: build_tms -> add_reminder -> build_tms. 이렇게 들어간 줄은 fromRemind 에
적어서 add_reminder 가 기술머신으로 치지 않는다 (치면 떠올리기에서 빠지고, 그러면 이 줄도 빠진다).

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import learn_ref                                            # noqa: E402

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
    src = {}            # 기술 id -> 그 기술머신이 있는 판 번호들
    for r in rows("machines.csv"):
        mid = as_int(r["move_id"])
        src.setdefault(mid, set()).add(as_int(r["version_group_id"]))
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

    # ---- 가르침 기술 (1.13.3): 본가 최신작에서 가르치기로 배우는 것은 그 기술머신으로 ----
    tutor_rows = 0
    ref = learn_ref.reference(rows("pokemon_moves.csv"), rows("version_groups.csv"))
    for num, mvs in sorted(ref.items()):
        if not 1 <= num <= MAX_DEX:
            continue                      # 폼은 별도 id - 기술머신은 원래 종 번호로 본다
        for mid, how in mvs.items():
            no = no_of_move.get(mid)
            if learn_ref.TUTOR in how and no is not None and no not in learn.get(num, set()):
                learn.setdefault(num, set()).add(no)
                tutor_rows += 1

    # ---- 레전즈 Z-A 에만 있는 기술머신 (1.13.4): Z-A 에서 그 기술머신으로 배우는 종 ----
    za_rows, za_only = 0, []
    za = learn_ref.za_codes()
    num_of = dict((s["internal"], s["num"]) for s in dex["species"])
    for mid, no in sorted(no_of_move.items(), key=lambda kv: kv[1]):
        vgs = src.get(mid, set())
        if not (vgs & learn_ref.ZA_VG) or any(v not in learn_ref.SIDE_VG for v in vgs):
            continue                      # Z-A 기술머신이 아니거나, 본편에도 있는 기술머신
        za_only.append(no)
        key = by_id[mid][0]
        for sp in sorted(za):
            num = num_of.get(sp)
            if num and "9M" in za[sp].get(key, ()) and no not in learn.get(num, set()):
                learn.setdefault(num, set()).add(no)
                za_rows += 1

    # ---- 떠올리기 기술 (2.0): 떠올리기로 배우는 기술은 그 기술의 기술머신으로도 ----
    remind_rows, from_remind = 0, {}
    for s in dex["species"]:
        num = s["num"]
        for key in s.get("remind") or []:
            no = no_of_move.get((dex["moves"].get(key) or {}).get("id"))
            if no is None or no in learn.get(num, set()):
                continue
            learn.setdefault(num, set()).add(no)
            from_remind.setdefault(str(num), []).append(no)
            remind_rows += 1

    out_learn = dict((str(k), sorted(v)) for k, v in sorted(learn.items()))

    if skipped:
        sys.stderr.write("  도감에 없어서 뺀 기술 %d개\n" % len(skipped))

    return {
        "version": 2,
        "source": "PokeAPI (전 세대 기술머신 합집합 + 알 기술 + 최신작 가르침 기술) + 쇼다운 Z-A 학습표 (Z-A 전용 기술머신)"
                  " + 도감의 떠올리기 기술",
        "counts": {
            "tms": len(tms),
            "species": len(out_learn),
            "rows": sum(len(v) for v in out_learn.values()),
            "eggRows": egg_rows,          # 그 가운데 알 기술이라서 들어간 줄
            "tutorRows": tutor_rows,      # 그 가운데 최신작 가르침 기술이라서 들어간 줄 (1.13.3)
            "zaRows": za_rows,            # 그 가운데 Z-A 전용 기술머신이라서 들어간 줄 (1.13.4)
            "remindRows": remind_rows,    # 그 가운데 떠올리기로 배우는 기술이라서 들어간 줄 (2.0)
        },
        "tms": tms,
        "learn": out_learn,
        # Z-A 전용 기술머신 번호 (1.13.4). add_reminder 가 본다 - 메가 종의 Z-A 떠올리기 기술은 이 기술머신으로
        # 배울 수 있게 됐다고 빼지 않는다 (먼저 떠올리기로 줬고, 기술머신은 잡아야 나온다).
        "zaOnly": sorted(za_only),
        # 떠올리기 기술이라서 들어간 줄 {도감번호: [번호들]} (2.0). add_reminder 가 본다 - 이 줄을 기술머신으로 치면
        # '기술머신으로 배운다' 고 떠올리기에서 빼고, 그러면 다음 build_tms 에서 이 줄도 사라진다 (서로 지운다).
        "fromRemind": dict((k, sorted(v)) for k, v in sorted(from_remind.items())),
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
    print("  기술머신 %d개 · %d종 · 학습 %d줄 (그 가운데 알 기술 %d줄 · 가르침 기술 %d줄 · Z-A 전용 %d줄 · 떠올리기 %d줄)"
          "  (%s, %.1fMB)" % (c["tms"], c["species"], c["rows"], c["eggRows"], c["tutorRows"], c["zaRows"],
                              c["remindRows"], a.out, mb))
    sv = sum(1 for t in data["tms"].values() if t["sv"] is not None)
    print("  스칼렛/바이올렛 번호 그대로 %d개, 옛 세대에서 가져온 것 %d개"
          % (sv, c["tms"] - sv))
    none = [n for n in range(1, MAX_DEX + 1) if str(n) not in data["learn"]]
    print("  기술머신을 하나도 못 쓰는 종 %d마리: %s"
          % (len(none), ", ".join(str(n) for n in none)))


if __name__ == "__main__":
    main()
