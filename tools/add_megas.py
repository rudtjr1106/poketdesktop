# -*- coding: utf-8 -*-
"""메가진화 폼과 메가스톤을 도감·도구 자료에 끼워 넣는다 (시즌 3).

    python tools/add_megas.py          # 고친다
    python tools/add_megas.py --check  # 바뀔 것이 있는지만 본다

**도감을 통째로 다시 만들지 않는다.** build_pokedex 를 다시 돌리면 그동안
손으로 끼워 넣은 기술·특성이 섞여 들어간다(메모리의 함정). 그래서 원본
(tools/_cache, PokeAPI CSV)에서 메가만 뽑아 붙인다.

## 어디에 넣나

메가 폼은 `pokedex.json` 의 **species 가 아니라 megas** 에 넣는다. species 는
도감 1025종을 세고 도는 모든 곳(도감 표시·업적·야생 추첨·알·관장 명단)이
쓴다. 거기 섞으면 그 모두가 흔들린다. Pokedex.get 이 이름·번호로 찾을 때만
megas 까지 본다.

## 폼 고르기

이 게임은 한 종에 모습이 하나다. 그래서
  · 냐오닉스 - 수컷·암컷 메가를 둘 다 넣고 성별로 고른다.
  · 싸리용 - 젖힌 모습만 (도감의 싸리용이 그 모습이다).
  · 마기아나 - 보통 색만 (500년 전의 색은 뺀다).
  · 원시회귀(가이오가·그란돈)는 메가가 아니라 뺀다.
  · 레쿠쟈는 스톤이 없다. 화룡점정을 알면 메가진화한다 (megaMove).

## 바탕화면에서 걸어다닐 도트 (1.8.0)

메가 폼마다 두 가지를 적어 둔다. 화면은 이것만 보고 '메가 모습으로 걷기' 를
보일지 정한다 - 받아 보고 판단하면 일러스트(도트가 아닌 것)까지 걸어다닌다.

  · walk — SpriteCollab 에 걷는 도트가 있으면 그 경로 ("0006/0001").
           8방향으로 걷는다. 94폼 중 41폼.
  · dot  — showdown 배틀 도트(gif)가 있는가. 걷는 도트가 없으면 이걸로
           선다 (정면 고정 - 걷는 도트가 없는 57종과 같은 방식).

둘 다 없으면(Z-A 신규 대부분) 바탕화면에서는 메가 모습이 안 된다.
자료는 tools/_cache 의 두 파일에서 온다 (없으면 지금 도감의 값을 그대로 둔다):
  spritecollab_tracker.json  https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/tracker.json
  mega_showdown.json         {메가 번호: showdown gif 가 있는가}

## 특성

원본에 특성이 없는 폼이 있다(Z-A 에서 새로 나온 것들). 그때는 **원래 종의
첫 특성**을 쓰고 megaAbilityGuess 를 적어 둔다 - 나중에 자료가 나오면
여기만 고치면 된다.
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
C = os.path.join(HERE, "_cache")
DEX = os.path.join(ROOT, "server", "data", "pokedex.json")
ITEMS = os.path.join(ROOT, "server", "data", "items.json")

STAT = {"1": "hp", "2": "atk", "3": "def", "4": "spa", "5": "spd", "6": "spe"}
SKIP = {"tatsugiri-droopy-mega", "tatsugiri-stretchy-mega", "magearna-original-mega"}
STONE_RE = re.compile(r"ite(-[xyz])?$")
NOT_STONES = {"meteorite", "eviolite"}
KO = "3"            # PokeAPI 언어 번호: 한국어


def rows(name):
    with open(os.path.join(C, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def key(ident):
    """PokeAPI 식 이름 -> 도감 열쇠 (tough-claws -> TOUGHCLAWS)."""
    return re.sub(r"[^A-Za-z0-9]", "", ident).upper()


def split(ident):
    """charizard-mega-x -> ('charizard', 'x'). meowstic-female-mega -> ('meowstic-female', '')."""
    base, _, rest = ident.partition("-mega")
    return base, rest.strip("-")


def prefix_score(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def build(dex, items):
    by_int = dict((s["internal"], s) for s in dex["species"])
    by_num = dict((s["num"], s) for s in dex["species"])
    poke = rows("pokemon.csv")
    stats = rows("pokemon_stats.csv")
    ptypes = rows("pokemon_types.csv")
    pabil = rows("pokemon_abilities.csv")
    types_csv = dict((r["id"], r["identifier"]) for r in rows("types.csv"))
    abil_csv = dict((r["id"], r["identifier"]) for r in rows("abilities.csv"))
    item_rows = rows("items.csv")
    item_ko = dict((r["item_id"], r["name"]) for r in rows("item_names.csv")
                   if r["local_language_id"] == KO)
    stones = [r for r in item_rows
              if STONE_RE.search(r["identifier"]) and r["identifier"] not in NOT_STONES]

    megas, stone_items, notes = [], {}, []
    for r in poke:
        ident = r["identifier"]
        if "-mega" not in ident or ident in SKIP:
            continue
        base_ident, suf = split(ident)
        head = base_ident.split("-")[0]              # meowstic-female -> meowstic
        base = by_num.get(int(r["species_id"]))
        if not base:
            notes.append("원래 종을 못 찾음: %s" % ident)
            continue
        pid = r["id"]
        st = dict((STAT[s["stat_id"]], int(s["base_stat"]))
                  for s in stats if s["pokemon_id"] == pid)
        tys = [key(types_csv[t["type_id"]]) for t in
               sorted((t for t in ptypes if t["pokemon_id"] == pid),
                      key=lambda t: int(t["slot"]))]
        ab = [a for a in pabil if a["pokemon_id"] == pid and a["is_hidden"] == "0"]
        ab_key = key(abil_csv[ab[0]["ability_id"]]) if ab else None
        guess = False
        if not ab_key or ab_key not in dex["abilities"]:
            ab_key = (base.get("abil") or [None])[0]
            guess = True
        letter = suf.upper() if suf in ("x", "y", "z") else ""
        female = "female" in base_ident
        internal = base["internal"] + "_MEGA" + ("_" + letter if letter else "") \
            + ("_F" if female else "")
        entry = dict(base)
        entry.update({
            "internal": internal, "num": int(pid),
            "kr": "메가" + base["kr"] + letter, "en": "Mega " + base["en"]
                                                  + (" " + letter if letter else ""),
            "base": st, "types": tys, "abil": [ab_key] if ab_key else [],
            # 메가는 배틀 중에만 되는 모습이라 배우는 기술 목록이 필요 없다.
            # 원래 종 것을 그대로 두면 94벌이 복사되어 도감이 1만 줄 는다.
            "moves": [],
            "hidden": None, "spawnable": False, "evo": [], "prevo": None,
            "kg": round(float(r["weight"]) / 10.0, 1),
            "height": round(float(r["height"]) / 10.0, 1),
            "mega": True, "megaOf": base["internal"],
        })
        if female:
            entry["megaGender"] = "F"
        if guess:
            entry["megaAbilityGuess"] = True
            notes.append("특성을 원래 종 것으로 대신: %s -> %s" % (entry["kr"], ab_key))
        # 스톤
        if base["internal"] == "RAYQUAZA":
            entry["megaStone"] = None
            entry["megaMove"] = "DRAGONASCENT"
        else:
            want_suf = "-" + suf if suf in ("x", "y", "z") else ""
            cands = [s for s in stones if (s["identifier"].endswith(want_suf) if want_suf
                                           else not re.search(r"-[xyz]$", s["identifier"]))]
            best = max(cands, key=lambda s: prefix_score(head, s["identifier"]), default=None)
            if not best or prefix_score(head, best["identifier"]) < 4:
                notes.append("스톤을 못 찾음: %s" % ident)
                continue
            sid = key(best["identifier"])
            entry["megaStone"] = sid
            if sid not in stone_items:
                kr = item_ko.get(best["id"])
                if not kr:
                    kr = base["kr"] + "나이트" + letter
                    notes.append("스톤 이름을 지음: %s -> %s" % (best["identifier"], kr))
                stone_items[sid] = {
                    "id": sid, "ident": best["identifier"], "kr": kr,
                    "en": best["identifier"].replace("-", " ").title(),
                    "cat": "megastone", "cost": 0, "sell": 0, "chance": 0, "weight": 0,
                    "rarity": "legendary", "effect": {"kind": "held"},
                    "megaFor": base["internal"],
                    "desc": "%s에게 지니게 하면 배틀 중에 메가진화할 수 있다. "
                            "키스톤이 있어야 하고, 한 판에 한 번만 쓸 수 있다."
                            % base["kr"],
                }
        if entry.get("megaStone"):
            # 엔진(common)은 items.json 을 안 읽는다. 메시지에 스톤 이름을 쓰려고 싣는다.
            entry["megaStoneKr"] = stone_items[entry["megaStone"]]["kr"]
        megas.append(entry)
    megas.sort(key=lambda m: m["num"])
    notes.extend(annotate_sprites(megas, dex, by_int))
    return megas, sorted(stone_items.values(), key=lambda i: i["id"]), notes


def annotate_sprites(megas, dex, by_int):
    """메가 폼마다 walk / dot 을 적는다 (머리말의 '바탕화면에서 걸어다닐 도트')."""
    notes = []
    old = dict((m["internal"], m) for m in dex.get("megas") or [])
    tracker = showdown = None
    tp = os.path.join(C, "spritecollab_tracker.json")
    sp = os.path.join(C, "mega_showdown.json")
    if os.path.exists(tp):
        with open(tp, encoding="utf-8") as f:
            tracker = json.load(f)
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            showdown = json.load(f)
    if tracker is None or showdown is None:
        notes.append("도트 자료(tools/_cache)가 없어 walk/dot 은 지금 도감 값을 그대로 둔다")
    n_walk = n_dot = 0
    for m in megas:
        prev = old.get(m["internal"]) or {}
        walk = prev.get("walk")
        dot = bool(prev.get("dot"))
        if tracker is not None:
            base = by_int[m["megaOf"]]
            suffix = m["internal"].split("_MEGA", 1)[1]            # "", "_X", "_Y", "_Z", "_F"
            want = "Mega" + (suffix if suffix in ("_X", "_Y", "_Z") else "")
            walk = None
            subs = (tracker.get("%04d" % base["num"]) or {}).get("subgroups") or {}
            for key_, form in sorted(subs.items()):
                if form.get("name") == want and "Walk" in (form.get("sprite_files") or {}) \
                        and not m.get("megaGender"):
                    walk = "%04d/%s" % (base["num"], key_)
                    break
        if showdown is not None:
            dot = bool(showdown.get(str(m["num"])))
        m.pop("walk", None)
        if walk:
            m["walk"] = walk
            n_walk += 1
        m["dot"] = dot
        n_dot += 1 if dot else 0
    notes.append("바탕화면 도트: 걷는 도트 %d폼 · 배틀 도트 %d폼 · 둘 다 없음 %d폼"
                 % (n_walk, n_dot, sum(1 for m in megas if not m.get("walk") and not m["dot"])))
    return notes


def main():
    check = "--check" in sys.argv
    with open(DEX, encoding="utf-8") as f:
        dex = json.load(f)
    with open(ITEMS, encoding="utf-8") as f:
        items = json.load(f)
    megas, stones, notes = build(dex, items)
    # items.json 의 items 는 {id: 도구} 사전이다.
    new_items = dict((k, v) for k, v in items["items"].items()
                     if v.get("cat") != "megastone")
    for st in stones:
        new_items[st["id"]] = st
    changed = dex.get("megas") != megas or items["items"] != new_items
    print("메가 폼 %d개 · 메가스톤 %d개 · 레쿠쟈는 화룡점정" % (len(megas), len(stones)))
    for n in notes:
        print("  -", n)
    if check:
        print("바뀔 것이 있다" if changed else "그대로다")
        return 1 if changed else 0
    dex["megas"] = megas
    items["items"] = new_items
    # 원래 파일과 **같은 형식**으로 쓴다(sort_keys, 들여쓰기 1, 끝 줄바꿈 없음).
    # 다르면 한 줄도 안 바뀐 곳까지 전부 바뀐 것처럼 보인다.
    with open(DEX, "w", encoding="utf-8") as f:
        json.dump(dex, f, ensure_ascii=False, indent=1, sort_keys=True)
    with open(ITEMS, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("썼다: %s, %s" % (os.path.relpath(DEX, ROOT), os.path.relpath(ITEMS, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
