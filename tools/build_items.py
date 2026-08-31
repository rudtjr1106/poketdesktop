# -*- coding: utf-8 -*-
"""도구 목록(items.json)을 만든다.

이름과 가격은 **PokeAPI 공식 CSV** 에서 그대로 가져온다. 손으로 옮겨
적으면 반드시 틀린다 — 실제로 사전 조사에서 달콤한사과/새콤한사과가
뒤바뀌고, 향기주머니와 휘핑팝의 진화 대상이 서로 틀렸다. 그래서 여기서는
'어떤 도구를 넣을지' 만 사람이 정하고, 이름·가격은 CSV 가 정하게 한다.

진화의 돌 목록도 손으로 적지 않는다. pokedex.json 의 진화 자료를 읽어서
**실제로 쓰이는 도구만** 넣는다. 그러면 상점에 팔지만 아무 데도 안 쓰이는
돌이 생기지 않는다.

    python tools/build_items.py --out server/data/items.json
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import urllib.request

CSV_BASE = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")
NEEDED = ["items.csv", "item_names.csv", "item_categories.csv"]
KO = 3
EN = 9

# ---------------------------------------------------------------- 등급
# 드랍은 등급을 먼저 뽑고, 그 안에서 도구를 고른다.
# 흔한 것이 자주 나와야 "잡을 때마다 뭔가 나온다" 는 느낌이 끊기지 않고,
# 좋은 것이 드물어야 값어치가 생긴다.
RARITY = ["common", "uncommon", "rare", "epic", "legendary"]
RARITY_KR = {"common": "흔함", "uncommon": "보통", "rare": "희귀",
             "epic": "매우 희귀", "legendary": "전설"}

# 등급별로 균등하게 뽑으면 안 된다. 진화의 돌만 41종이라, 등급 안에서
# 균등 추첨하면 특정 돌 하나가 병뚜껑보다 귀해진다. 그래서 도구마다
# 가중치를 주고 전체에서 한 번에 뽑는다.
WEIGHT = {"common": 100, "uncommon": 45, "rare": 14,
          "epic": 5, "legendary": 1.2}

# 그래도 따로 맞춰야 하는 것들.
# 병뚜껑은 한 마리를 완성하려면 여러 개가 필요해서 조금 넉넉히 준다.
# 마스터볼은 한 개만 있어도 판이 바뀌므로 아주 인색하게 준다.
WEIGHT_OVERRIDE = {
    "bottle-cap": 34,        # 은색: 6개 모으면 6V
    "gold-bottle-cap": 9,    # 금색: 한 방에 6V
    "rare-candy": 20,
    "master-ball": 2,
    "sacred-ash": 4,
    "big-nugget": 8,
    "comet-shard": 6,
}

# 파는 값은 사는 값의 절반. 본가 프렌들리샵과 같다.
SELL_RATE = 0.5

# 비매품(cost 0)이라 값을 우리가 정해야 하는 것들
PRICE_OVERRIDE = {
    "level-ball": 1000, "moon-ball": 1000, "fast-ball": 1000,
    "heavy-ball": 1000, "love-ball": 1000, "friend-ball": 1000,
    "dream-ball": 1500, "master-ball": 0,          # 마스터볼은 상점 판매 금지
    "black-augurite": 3000, "peat-block": 3000, "metal-alloy": 3000,
    "scroll-of-darkness": 5000, "scroll-of-waters": 5000,
    "linking-cord": 8000,
}

# 상점에서 팔지 않는 것 (드랍으로만 얻는다)
NO_BUY = {"master-ball", "gold-bottle-cap"}


def _ball(mult, cond=None, note=""):
    d = {"kind": "ball", "mult": mult}
    if cond:
        d["cond"] = cond
    if note:
        d["note"] = note
    return d


# ---------------------------------------------------------------- 카탈로그
# (identifier, 분류, 등급, 효과)
# 이름과 가격은 여기 적지 않는다. CSV 가 채운다.
CATALOG = [
    # ---- 몬스터볼 ----
    ("poke-ball", "ball", "common", _ball(1.0)),
    ("premier-ball", "ball", "common", _ball(1.0, note="몬스터볼과 성능이 같다")),
    ("great-ball", "ball", "uncommon", _ball(1.5)),
    ("heal-ball", "ball", "uncommon", _ball(1.0, note="잡으면 완전 회복")),
    ("net-ball", "ball", "uncommon", _ball(3.5, "water_or_bug")),
    ("nest-ball", "ball", "uncommon", _ball(4.0, "low_level")),
    ("timer-ball", "ball", "uncommon", _ball(4.0, "many_turns")),
    ("quick-ball", "ball", "uncommon", _ball(5.0, "first_turn")),
    ("dusk-ball", "ball", "uncommon", _ball(3.0, "night")),
    ("level-ball", "ball", "uncommon", _ball(8.0, "level_gap")),
    ("moon-ball", "ball", "uncommon", _ball(4.0, "moon_family")),
    ("fast-ball", "ball", "uncommon", _ball(4.0, "fast_species")),
    ("heavy-ball", "ball", "uncommon", _ball(1.0, "heavy")),
    ("love-ball", "ball", "uncommon", _ball(8.0, "same_species_other_gender")),
    ("friend-ball", "ball", "uncommon", _ball(1.0, note="잡으면 친밀도 200")),
    ("dream-ball", "ball", "uncommon", _ball(4.0, "asleep")),
    ("repeat-ball", "ball", "uncommon", _ball(3.5, "already_caught")),
    ("luxury-ball", "ball", "rare", _ball(1.0, note="잡은 뒤 친밀도가 두 배로 오른다")),
    ("ultra-ball", "ball", "rare", _ball(2.0)),
    ("master-ball", "ball", "legendary", _ball(255.0, note="반드시 잡는다")),

    # ---- 노력치: 깃털(+1) ----
    ("health-wing", "ev", "common", {"kind": "ev", "stat": "hp", "amount": 1}),
    ("muscle-wing", "ev", "common", {"kind": "ev", "stat": "atk", "amount": 1}),
    ("resist-wing", "ev", "common", {"kind": "ev", "stat": "def", "amount": 1}),
    ("genius-wing", "ev", "common", {"kind": "ev", "stat": "spa", "amount": 1}),
    ("clever-wing", "ev", "common", {"kind": "ev", "stat": "spd", "amount": 1}),
    ("swift-wing", "ev", "common", {"kind": "ev", "stat": "spe", "amount": 1}),

    # ---- 노력치: 열매(-10) ----
    ("pomeg-berry", "ev", "common", {"kind": "ev", "stat": "hp", "amount": -10}),
    ("kelpsy-berry", "ev", "common", {"kind": "ev", "stat": "atk", "amount": -10}),
    ("qualot-berry", "ev", "common", {"kind": "ev", "stat": "def", "amount": -10}),
    ("hondew-berry", "ev", "common", {"kind": "ev", "stat": "spa", "amount": -10}),
    ("grepa-berry", "ev", "common", {"kind": "ev", "stat": "spd", "amount": -10}),
    ("tamato-berry", "ev", "common", {"kind": "ev", "stat": "spe", "amount": -10}),

    # ---- 노력치: 영양제(+10) ----
    # 드랍에 넣지 않는다. 한 스탯 252 를 채우려면 26개가 필요해서, 드랍으로
    # 주면 몇십 일이 걸린다. 본가처럼 상점에서 사게 한다. 이게 "도구를 팔아
    # 번 돈" 의 쓰임새가 되어 경제가 돈다.
    ("hp-up", "ev", None, {"kind": "ev", "stat": "hp", "amount": 10}),
    ("protein", "ev", None, {"kind": "ev", "stat": "atk", "amount": 10}),
    ("iron", "ev", None, {"kind": "ev", "stat": "def", "amount": 10}),
    ("calcium", "ev", None, {"kind": "ev", "stat": "spa", "amount": 10}),
    ("zinc", "ev", None, {"kind": "ev", "stat": "spd", "amount": 10}),
    ("carbos", "ev", None, {"kind": "ev", "stat": "spe", "amount": 10}),

    # ---- 개체값 ----
    ("bottle-cap", "iv", "epic", {"kind": "iv", "count": 1}),
    ("gold-bottle-cap", "iv", "legendary", {"kind": "iv", "count": 6}),

    # ---- 그 밖에 쓰는 것 ----
    ("rare-candy", "misc", "epic", {"kind": "level", "amount": 1}),
    ("everstone", "misc", "uncommon", {"kind": "noevolve"}),

    # ---- 회복약: 지금은 파는 용도 ----
    # 이 게임에는 배틀 밖에서 체력이 남지 않는다(배틀이 끝나면 원래대로).
    # 그래서 회복약은 아직 쓸 데가 없고, 팔아서 돈으로 바꾸는 물건이다.
    # 나중에 체력이 이어지거나 트레이너전이 생기면 그때 살아난다.
    ("potion", "heal", "common", {"kind": "sell"}),
    ("super-potion", "heal", "common", {"kind": "sell"}),
    ("antidote", "heal", "common", {"kind": "sell"}),
    ("burn-heal", "heal", "common", {"kind": "sell"}),
    ("ice-heal", "heal", "common", {"kind": "sell"}),
    ("awakening", "heal", "common", {"kind": "sell"}),
    ("paralyze-heal", "heal", "common", {"kind": "sell"}),
    ("hyper-potion", "heal", "uncommon", {"kind": "sell"}),
    ("revive", "heal", "uncommon", {"kind": "sell"}),
    ("full-heal", "heal", "uncommon", {"kind": "sell"}),
    ("ether", "heal", "uncommon", {"kind": "sell"}),
    ("max-potion", "heal", "rare", {"kind": "sell"}),
    ("full-restore", "heal", "rare", {"kind": "sell"}),
    ("max-revive", "heal", "rare", {"kind": "sell"}),
    ("sacred-ash", "heal", "legendary", {"kind": "sell"}),

    # ---- 팔려고 있는 것 ----
    ("tiny-mushroom", "misc", "common", {"kind": "sell"}),
    ("pretty-wing", "misc", "common", {"kind": "sell"}),
    ("stardust", "misc", "common", {"kind": "sell"}),
    ("pearl", "misc", "common", {"kind": "sell"}),
    ("nugget", "misc", "uncommon", {"kind": "sell"}),
    ("big-pearl", "misc", "uncommon", {"kind": "sell"}),
    ("big-mushroom", "misc", "uncommon", {"kind": "sell"}),
    ("rare-bone", "misc", "uncommon", {"kind": "sell"}),
    ("star-piece", "misc", "rare", {"kind": "sell"}),
    ("big-nugget", "misc", "epic", {"kind": "sell"}),
    ("comet-shard", "misc", "epic", {"kind": "sell"}),
]

# 진화의 돌은 값이 비싼 것만 따로 등급을 올린다. 나머지는 rare.
STONE_EPIC_OVER = 6000


def norm(s):
    return re.sub(r"[^0-9A-Z]", "", (s or "").upper())


def fetch(name):
    if not os.path.isdir(CACHE):
        os.makedirs(CACHE)
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        sys.stderr.write("  받는 중 %s\n" % name)
        with urllib.request.urlopen(CSV_BASE + "/" + name, timeout=180) as r:
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


def stones_from_pokedex(path):
    """도감의 진화 자료에서 '실제로 쓰이는 도구' 만 뽑는다."""
    if not os.path.exists(path):
        sys.stderr.write("  경고: %s 가 없어 진화의 돌을 넣지 못했습니다.\n" % path)
        return {}
    dex = json.load(io.open(path, encoding="utf-8"))
    used = {}
    for s in dex.get("species", []):
        for b in s.get("evo", []):
            it = b.get("item")
            if it:
                used.setdefault(it, []).append(s["kr"])
    return used


def build(pokedex_path):
    ident_of = {}
    cost_of = {}
    cat_of = {}
    for r in rows("items.csv"):
        i = as_int(r["id"])
        ident_of[r["identifier"]] = i
        cost_of[i] = as_int(r["cost"])
        cat_of[i] = as_int(r["category_id"])

    kr = {}
    en = {}
    for r in rows("item_names.csv"):
        i = as_int(r["item_id"])
        lang = as_int(r["local_language_id"])
        if lang == KO:
            kr[i] = r["name"]
        elif lang == EN:
            en[i] = r["name"]

    used_stones = stones_from_pokedex(pokedex_path)
    by_internal = dict((norm(k), k) for k in ident_of)

    entries = list(CATALOG)
    # 진화에 실제로 쓰이는 도구를 카탈로그에 더한다
    already = set(x[0] for x in entries)
    stone_ids = []
    for internal in sorted(used_stones):
        ident = by_internal.get(internal)
        if not ident:
            sys.stderr.write("  경고: 진화에 쓰이는데 items.csv 에 없음: %s\n" % internal)
            continue
        stone_ids.append(ident)
        if ident in already:
            continue
        iid = ident_of[ident]
        price = PRICE_OVERRIDE.get(ident, cost_of.get(iid, 0))
        rar = "epic" if price >= STONE_EPIC_OVER else "rare"
        entries.append((ident, "stone", rar, {"kind": "stone"}))

    out = {}
    missing = []
    for ident, cat, rar, eff in entries:
        iid = ident_of.get(ident)
        if iid is None:
            missing.append(ident)
            continue
        cost = PRICE_OVERRIDE.get(ident, cost_of.get(iid, 0))
        name = kr.get(iid) or en.get(iid) or ident
        d = {
            "id": norm(ident),
            "ident": ident,
            "kr": name,
            "en": en.get(iid, ident.title()),
            "cat": cat,
            "cost": cost,
            "sell": int(cost * SELL_RATE),
            "effect": eff,
        }
        if rar:
            d["rarity"] = rar
        if ident in NO_BUY or cost <= 0:
            d["buyable"] = False
        if cat == "stone":
            d["evolves"] = sorted(used_stones.get(norm(ident), []))
        out[d["id"]] = d

    if missing:
        sys.stderr.write("  경고: items.csv 에 없는 항목 %s\n" % ", ".join(missing))

    # 드랍표: (도구 id, 가중치). 서버는 가중치 합에서 한 번 뽑으면 된다.
    table = []
    for d in sorted(out.values(), key=lambda x: x["id"]):
        r = d.get("rarity")
        if not r:
            continue
        w = WEIGHT_OVERRIDE.get(d["ident"], WEIGHT[r])
        d["weight"] = w
        table.append([d["id"], w])
    total = sum(w for _i, w in table)
    for d in out.values():
        if "weight" in d:
            d["chance"] = round(d["weight"] / total, 6)

    return {
        "version": 1,
        "source": "PokeAPI (이름·가격은 공식 CSV 그대로)",
        "sellRate": SELL_RATE,
        "rarityKr": RARITY_KR,
        "dropTable": table,
        "dropTotal": total,
        "items": out,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="server/data/items.json")
    ap.add_argument("--pokedex", default="server/data/pokedex.json")
    a = ap.parse_args()

    data = build(a.pokedex)
    d = os.path.dirname(os.path.abspath(a.out))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)

    items = data["items"]
    print("\n도구 %d종" % len(items))
    for r in RARITY:
        got = [x for x in items.values() if x.get("rarity") == r]
        if not got:
            continue
        tier = sum(x["chance"] for x in got)
        lo = min(x["chance"] for x in got)
        hi = max(x["chance"] for x in got)
        print("  %-10s %2d종  등급 합계 %5.2f%%   개당 %.3f~%.3f%%"
              % (RARITY_KR[r], len(got), tier * 100, lo * 100, hi * 100))

    print("\n  눈여겨볼 것 (하루 55드랍 기준)")
    for ident in ("poke-ball", "ultra-ball", "fire-stone", "bottle-cap",
                  "gold-bottle-cap", "rare-candy", "master-ball"):
        x = next((v for v in items.values() if v["ident"] == ident), None)
        if not x or not x.get("chance"):
            continue
        per_day = x["chance"] * 55
        pace = ("하루 %.1f개" % per_day) if per_day >= 1 \
            else ("%.1f일에 1개" % (1.0 / per_day))
        print("    %-12s %6.3f%%   %s" % (x["kr"], x["chance"] * 100, pace))

    shop = [d for d in data["items"].values() if d.get("buyable") is not False]
    print("  상점 판매 %d종 / 드랍 전용 %d종"
          % (len(shop), len(data["items"]) - len(shop)))


if __name__ == "__main__":
    main()
