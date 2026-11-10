# -*- coding: utf-8 -*-
"""도감 설명(본가 도감에 적힌 글)을 도감(pokedex.json)의 종마다 flavor 칸에 넣는다 (게시판 #496, 11/10).

    python tools/add_flavor.py            # 넣는다 (있으면 고쳐 쓴다)
    python tools/add_flavor.py --check    # 도감이 지금 자료와 같은지만 본다

2026-11-09 게시판 #496 (KKK3): "도감 들어가서 포켓몬 클릭하면 도감 내용이 나왔으면 좋겠어요". 도감 창은 칸을
눌러도 아무것도 안 열렸고, 도감 자료에도 본가 도감 글은 없었다 (분류 · 키 · 몸무게만).

**어디서:** PokeAPI 의 pokemon_species_flavor_text.csv (build_pokedex 와 같은 곳, tools/_cache 에 받아 둔다) 의 한국어
(언어 3) 가운데 **가장 최근 게임의 글 하나** - 소드 > 실드 > 울트라썬 > 울트라문 > 썬 > 문 > 오메가루비 > 알파사파이어
> X > Y > 레츠고 피카츄 > 레츠고 이브이. 줄바꿈은 빈칸으로 잇는다 (게임 화면 폭에 맞춰 끊어 둔 것이다).

**한국어는 898번(소드 · 실드)까지뿐이다.** 899번부터(레전드 아르세우스 · 스칼렛 · 바이올렛, 127종)는 PokeAPI 에
한국어 글이 없어 비워 둔다 - 도감 창은 '아직 도감 설명이 없다' 고 적는다. 지어내서 채우지 않는다.

build_pokedex.py 로 도감을 다시 만들면 이것도 다시 돌린다 (add_megas · add_forms · add_reminder 처럼).
"""
import csv
import io
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEX = os.path.join(ROOT, "server", "data", "pokedex.json")
CACHE = os.path.join(ROOT, "tools", "_cache")
CSV_BASE = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv"
KO = "3"
# 고르는 차례 - 앞이 최근 게임이다 (PokeAPI versions.csv 의 identifier)
ORDER = ("sword", "shield", "ultra-sun", "ultra-moon", "sun", "moon", "omega-ruby", "alpha-sapphire",
         "x", "y", "lets-go-pikachu", "lets-go-eevee")


def _csv(name):
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        print("받는 중: %s" % name)
        urllib.request.urlretrieve("%s/%s" % (CSV_BASE, name), path)
    with io.open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def clean(text):
    """게임 화면 폭에 맞춰 끊은 줄을 잇는다. 한국어 글은 줄 끝이 낱말 끝이라 빈칸으로 잇는다."""
    t = (text or "").replace("\f", " ").replace("­", "").replace("\n", " ")
    return " ".join(t.split())


def build():
    """{도감 번호: 글}."""
    ver = dict((r["id"], r["identifier"]) for r in _csv("versions.csv"))
    rank = dict((v, i) for i, v in enumerate(ORDER))
    best = {}
    for r in _csv("pokemon_species_flavor_text.csv"):
        if r["language_id"] != KO:
            continue
        v = ver.get(r["version_id"])
        if v not in rank:
            continue
        n = int(r["species_id"])
        if n not in best or rank[v] < best[n][0]:
            best[n] = (rank[v], clean(r["flavor_text"]))
    return dict((n, t) for n, (_r, t) in best.items() if t)


def _put(sp, key, value):
    """key 를 자리(가나다 차례)에 끼운다 - 도감 파일은 칸 차례를 지켜 다시 쓴다 (sort_keys 로 쓰면 진화 칸
    같은 다른 줄까지 자리가 바뀌어 차이가 커진다)."""
    items = [(k, v) for k, v in sp.items() if k != key]
    at = next((i for i, (k, _v) in enumerate(items) if k > key), len(items))
    items.insert(at, (key, value))
    sp.clear()
    sp.update(items)


def apply(dex, table):
    changed = False
    for sp in dex["species"]:
        want = table.get(int(sp["num"]))
        if want and sp.get("flavor") != want:
            _put(sp, "flavor", want)
            changed = True
        elif not want and "flavor" in sp:
            del sp["flavor"]
            changed = True
    return changed


def main():
    check = "--check" in sys.argv
    with io.open(DEX, encoding="utf-8") as f:
        dex = json.load(f)
    table = build()
    changed = apply(dex, table)
    nums = [int(sp["num"]) for sp in dex["species"]]
    print("도감 설명: %d / %d종 (없는 것 %d종: %s)" % (
        sum(1 for n in nums if n in table), len(nums), sum(1 for n in nums if n not in table),
        ", ".join(str(n) for n in nums if n not in table)[:120] + " ..."))
    if check:
        print("바뀔 것이 있다" if changed else "그대로다")
        return 1 if changed else 0
    with io.open(DEX, "w", encoding="utf-8") as f:
        json.dump(dex, f, ensure_ascii=False, indent=1)        # 칸 차례 그대로 (_put)
    print("썼다: %s" % os.path.relpath(DEX, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
