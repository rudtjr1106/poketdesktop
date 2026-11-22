# -*- coding: utf-8 -*-
"""그동안 없던 지닌 도구와 폼을 바꾸는 도구를 items.json 에 넣는다 (1.13).

    python tools/add_held.py            # 넣는다 (있으면 고쳐 쓴다)
    python tools/add_held.py --check    # items.json 이 지금 자료와 같은지만 본다

사용자 요청 "아직 미추가된 도구들 전부 구현해서 추가해줘 / 포켓몬들의 폼체인지까지" (2026-10-17).
**상점에서만 판다** (사용자 결정) - 드랍·탐험 보상에는 안 넣는다 (weight 0).

**build_items.py 를 다시 돌리면 이것도 다시 돌려야 한다** (add_megas·add_zcrystals 와 같다).

  · 지닌 도구 (cat held)  common/held.KR 에 있는데 items.json 에 없는 것 전부. 효과는 common/held.py.
  · 폼 도구 (cat form)     가방에서 포켓몬에게 쓰면 모습이 바뀐다 (common/forms 자료: 도감 forms 의 useItem).

이름·설명은 PokeAPI 한국어 그대로 (tools/_cache). 설명이 없으면 held.effect_note 로 채운다.
"""
import csv
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "tools", "_cache")
ITEMS = os.path.join(ROOT, "server", "data", "items.json")
DEX = os.path.join(ROOT, "server", "data", "pokedex.json")
sys.path.insert(0, ROOT)

from common import held as H            # noqa: E402

KO = "3"
# 값 (사용자 결정: 전설 전용·폼 도구는 비싸게 → 2026-10-17 "전설급은 5만원 이상으로"). build_items._held_price
# 의 띠를 따르고, 아래만 따로 정한다. 전설급은 하는 일의 크기로 셋으로 나눈다.
LEGEND_TOP = 100000     # 모습이 바뀌고 판을 뒤집는 것: 원시회귀 구슬(주홍·쪽빛), 녹슨검·녹슨방패
LEGEND_FORM = 80000     # 모습이 바뀌고 위력도 오르는 것: 큰금강옥·큰백옥·큰백금옥, 오거폰의 가면
LEGEND = 50000          # 위력만 오르는 것(금강옥·백옥·백금옥·마음의물방울), 전설·환상의 폼 도구
FORM_PLAIN = 30000      # 전설이 아닌 포켓몬의 폼 도구 (로토무카탈로그)
GAME_CHANGER = 15000    # 판을 바꾸는 것 (구애·생명의구슬과 같은 값)
SPECIES_ONLY = 10000    # 그 포켓몬만 크게 강해지는 것 (전기구슬 2배 …)
NECTAR = 3000           # 꽃꿀 (쓰면 없어진다)
GEM_COST = 1500         # 주얼 (한 번 쓰면 그 판에서는 사라진다)
BERRY = 1000

LEGEND_PRICE = {"REDORB": LEGEND_TOP, "BLUEORB": LEGEND_TOP, "RUSTEDSWORD": LEGEND_TOP, "RUSTEDSHIELD": LEGEND_TOP,
                "ADAMANTCRYSTAL": LEGEND_FORM, "LUSTROUSGLOBE": LEGEND_FORM, "GRISEOUSCORE": LEGEND_FORM,
                "WELLSPRINGMASK": LEGEND_FORM, "HEARTHFLAMEMASK": LEGEND_FORM, "CORNERSTONEMASK": LEGEND_FORM,
                "ADAMANTORB": LEGEND, "LUSTROUSORB": LEGEND, "GRISEOUSORB": LEGEND, "SOULDEW": LEGEND}
GAME_CHANGERS = {"ASSAULTVEST", "ROCKYHELMET", "WEAKNESSPOLICY", "EVIOLITE", "BOOSTERENERGY", "HEAVYDUTYBOOTS",
                 "LOADEDDICE", "COVERTCLOAK", "CLEARAMULET"}
SPECIES_ITEMS = {"LIGHTBALL", "THICKCLUB", "LUCKYPUNCH", "STICK", "METALPOWDER", "QUICKPOWDER"}
# 폼 도구: PokeAPI 이름 -> 우리 열쇠. 쓰는 법은 도감 forms 의 useItem 이 정한다.
# 합체 도구(유전자쐐기·네크로플러스솔/루나·유대의고삐)는 넣지 않는다 (2026-10-17 사용자 결정).
FORM_ITEMS = {"gracidea": "GRACIDEA", "reveal-glass": "REVEALGLASS", "prison-bottle": "PRISONBOTTLE",
              "rotom-catalog": "ROTOMCATALOG", "meteorite": "METEORITE", "zygarde-cube": "ZYGARDECUBE",
              "red-nectar": "REDNECTAR", "yellow-nectar": "YELLOWNECTAR",
              "pink-nectar": "PINKNECTAR", "purple-nectar": "PURPLENECTAR"}
NECTARS = {"REDNECTAR", "YELLOWNECTAR", "PINKNECTAR", "PURPLENECTAR"}
# 원본에 한국어 이름이 비어 있는 것
KR_FIX = {"ROSELIBERRY": "로셀열매"}
# 원본 설명만으로는 오해하는 것 (게시판 #689 11/19: 지가르데큐브를 강해지는 도구로 알고 5만원에 샀다 - 10%폼은
# 약해지는 쪽이고 퍼펙트폼과는 관계없다). 켜기/끄기 안내는 앱이 덧말(ui_bag.form_note)로 따로 붙이니 여기는 뺀다.
DESC_FIX = {
    "ZYGARDECUBE": "포켓몬 지가르데의 코어와 셀이 모여있는 도구. 10%폼은 50%폼보다 빠르지만 HP와 방어, 특수공격, "
                   "특수방어는 낮다. 퍼펙트폼과는 관계없다 (퍼펙트폼은 지가르데나이트를 지닌 지가르데가 배틀에서 "
                   "체력 절반 이하로 턴을 마치면 된다).",
}


def _rows(name):
    with io.open(os.path.join(CACHE, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def key(ident):
    return re.sub(r"[^A-Za-z0-9]", "", ident.split("--")[0]).upper()


def _rarity(cost):
    if cost >= LEGEND:
        return "legendary"
    if cost >= GAME_CHANGER:
        return "epic"
    if cost >= 5000:
        return "rare"
    if cost <= BERRY:
        return "common"
    return "uncommon"


def _held_cost(iid, csv_cost):
    if iid in LEGEND_PRICE:
        return LEGEND_PRICE[iid]
    if iid in GAME_CHANGERS:
        return GAME_CHANGER
    if iid in SPECIES_ITEMS:
        return SPECIES_ONLY
    if iid in H.GEM:
        return GEM_COST
    if iid in H.MEMORY or iid in H.DRIVE or iid in H.TYPE_BOOST:
        return 3000                      # 메모리·카세트·요정의깃털·정령플레이트 = 다른 타입 강화 도구와 같은 값
    if iid.endswith("BERRY"):
        return BERRY
    if csv_cost <= 100:
        return BERRY
    if csv_cost <= 2000:
        return csv_cost * 3
    return min(csv_cost * 2, 12000)


def build(items):
    rows = _rows("items.csv")
    by_key = {}
    for r in rows:
        by_key.setdefault(key(r["identifier"]), r)
    by_ident = dict((r["identifier"], r) for r in rows)
    ko = dict((r["item_id"], r["name"]) for r in _rows("item_names.csv") if r["local_language_id"] == KO)
    en = dict((r["item_id"], r["name"]) for r in _rows("item_names.csv") if r["local_language_id"] == "9")
    flavor = {}
    for r in _rows("item_flavor_text.csv"):
        if r["language_id"] == KO:
            prev = flavor.get(r["item_id"])
            if prev is None or int(r["version_group_id"]) >= prev[0]:
                flavor[r["item_id"]] = (int(r["version_group_id"]), " ".join(r["flavor_text"].split()))
    with io.open(DEX, encoding="utf-8") as f:
        forms = json.load(f).get("forms") or []
    have = items["items"]
    out, notes = [], []

    def entry(iid, r, cat, cost, effect):
        kr = KR_FIX.get(iid) or ko.get(r["id"]) or H.KR.get(iid) or iid
        desc = DESC_FIX.get(iid) or (flavor.get(r["id"]) or (0, ""))[1] or H.effect_note(iid)
        if not desc:
            notes.append("설명 없음: %s" % iid)
        return {"id": iid, "ident": r["identifier"].split("--")[0], "kr": kr, "en": en.get(r["id"]) or iid.title(),
                "cat": cat, "cost": cost, "sell": cost // 2, "chance": 0, "weight": 0,
                "rarity": _rarity(cost), "desc": desc, "effect": effect}

    # ---- 지닌 도구
    for iid in sorted(H.KR):
        if iid in have and have[iid].get("cat") != "held":
            continue                     # 진화의 돌이면서 지닐 수도 있는 것 (금속코트·심해의이빨 …)
        r = by_key.get(iid)
        if r is None:
            notes.append("원본에 없음: %s" % iid)
            continue
        cost = have[iid]["cost"] if iid in have else _held_cost(iid, int(r["cost"] or 0))
        it = entry(iid, r, "held", cost, {"kind": "held"})
        if iid in have:
            # 그동안 있던 것은 그대로 둔다 (드랍 확률·가격이 이미 정해져 있다)
            continue
        out.append(it)
    # ---- 폼 도구
    for ident, iid in FORM_ITEMS.items():
        r = by_ident.get(ident)
        if r is None:
            notes.append("원본에 없음: %s" % ident)
            continue
        targets = [m["internal"] for m in forms if m.get("useItem") == iid]
        cost = NECTAR if iid in NECTARS else (FORM_PLAIN if iid == "ROTOMCATALOG" else LEGEND)
        eff = {"kind": "form", "forms": targets}
        if iid in NECTARS:
            eff["consume"] = True
        if not targets and iid != "REDNECTAR":
            notes.append("이 도구로 바뀌는 폼이 없음: %s" % iid)
        if iid == "REDNECTAR":
            eff["forms"] = ["ORICORIO"]          # 다홍꿀 = 원래 모습(이글이글스타일)으로
        out.append(entry(iid, r, "form", cost, eff))
    return out, notes


def main():
    check = "--check" in sys.argv
    with io.open(ITEMS, encoding="utf-8") as f:
        items = json.load(f)
    add, notes = build(items)
    new_items = dict(items["items"])
    for it in add:
        new_items[it["id"]] = it
    changed = new_items != items["items"]
    print("넣을 도구 %d개 (지닌 도구 %d · 폼 도구 %d)" % (
        len(add), sum(1 for i in add if i["cat"] == "held"), sum(1 for i in add if i["cat"] == "form")))
    for n in notes:
        print("  -", n)
    if check:
        print("바뀔 것이 있다" if changed else "그대로다")
        return 1 if changed else 0
    items["items"] = new_items
    with io.open(ITEMS, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("썼다: %s" % os.path.relpath(ITEMS, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
