# -*- coding: utf-8 -*-
"""모습을 바꾸는 폼(폼체인지)을 도감 자료에 끼워 넣는다.

    python tools/add_forms.py          # 고친다
    python tools/add_forms.py --check  # 바뀔 것이 있는지만 본다

**도감을 통째로 다시 만들지 않는다** (add_megas 와 같은 까닭). 원본(tools/_cache, PokeAPI CSV)
에서 폼만 뽑아 `pokedex.json` 의 **forms** 에 넣는다. species 에 섞지 않는다 - 도감 1025종을
세고 도는 곳(도감·업적·야생 추첨·알·관장 명단·전설 제한)이 흔들린다. Pokedex.get 이 이름·번호로
찾을 때만 forms 까지 본다.

## 포켓몬은 종을 그대로 두고 폼을 따로 적는다

pokemon.form 칸에 폼 열쇠(ORIGIN, SKY …)를 적는다. 지니면 바뀌는 폼은 적지 않고 지닌 도구로
정한다 (common/forms.py). 종을 폼 이름으로 바꾸면 전설 한 마리 제한·도감·업적처럼 종으로
판단하는 곳이 모두 흔들린다.

## 폼마다 적는 것

  internal  GIRATINA_ORIGIN       도감 열쇠 (원래 종 + _ + 폼 열쇠)
  num       10007                 도트 번호 (PokeAPI 의 pokemon id)
  kr        기라티나               이름은 원래 종 그대로 (본가도 이름은 그대로다)
  formKr    오리진폼               폼 이름
  formOf    GIRATINA, form ORIGIN
  kind      held   지니면 그 모습 (도구를 빼면 돌아온다)
            primal 지니고 배틀에 나오면 원시회귀 (배틀 중에만)
            use    도구를 쓰면 바뀐다 (다시 쓰면 돌아온다 / 고른다)
            battle 배틀 중에만 (특성)
            move   그 기술을 알면 그 모습 (도트만)
            evo    진화할 때 그 모습으로 정해진다 (물의 족자로 진화한 연격의 태세 우라오스, 2.1.0)
  items / useItem / formMoves   kind 에 따라
  base·types·abil·hidden                 원본 그대로
  walk / dot                              바탕화면 도트 (add_megas 와 같은 뜻)

배우는 기술은 적지 않는다 - 불러올 때 원래 종의 것을 같이 쓴다 (Pokedex.__init__).
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
C = os.path.join(HERE, "_cache")
DEX = os.path.join(ROOT, "server", "data", "pokedex.json")
STAT = {"1": "hp", "2": "atk", "3": "def", "4": "spa", "5": "spd", "6": "spe"}
KO = "3"

# (PokeAPI 이름, 폼 열쇠, 종류, 덧붙임). 덧붙임: items(held/primal), useItem(use),
# formMoves({"sig": 그 폼의 기술}), formKr(원본에 이름이 없을 때).
FORMS = [
    # ---- 지니면 바뀐다 (도구를 빼면 돌아온다)
    ("giratina-origin", "ORIGIN", "held", {"items": ["GRISEOUSORB", "GRISEOUSCORE"]}),
    ("dialga-origin", "ORIGIN", "held", {"items": ["ADAMANTCRYSTAL"], "formKr": "오리진폼"}),
    ("palkia-origin", "ORIGIN", "held", {"items": ["LUSTROUSGLOBE"], "formKr": "오리진폼"}),
    ("zacian-crowned", "CROWNED", "held", {"items": ["RUSTEDSWORD"]}),
    ("zamazenta-crowned", "CROWNED", "held", {"items": ["RUSTEDSHIELD"]}),
    ("ogerpon-wellspring-mask", "WELLSPRING", "held", {"items": ["WELLSPRINGMASK"]}),
    ("ogerpon-hearthflame-mask", "HEARTHFLAME", "held", {"items": ["HEARTHFLAMEMASK"]}),
    ("ogerpon-cornerstone-mask", "CORNERSTONE", "held", {"items": ["CORNERSTONEMASK"]}),
    # ---- 지니고 배틀에 나오면 (배틀 중에만)
    ("kyogre-primal", "PRIMAL", "primal", {"items": ["BLUEORB"]}),
    ("groudon-primal", "PRIMAL", "primal", {"items": ["REDORB"]}),
    # ---- 도구를 쓰면 바뀐다
    ("shaymin-sky", "SKY", "use", {"useItem": "GRACIDEA"}),
    ("tornadus-therian", "THERIAN", "use", {"useItem": "REVEALGLASS"}),
    ("thundurus-therian", "THERIAN", "use", {"useItem": "REVEALGLASS"}),
    ("landorus-therian", "THERIAN", "use", {"useItem": "REVEALGLASS"}),
    ("enamorus-therian", "THERIAN", "use", {"useItem": "REVEALGLASS", "formKr": "영물폼"}),
    ("hoopa-unbound", "UNBOUND", "use", {"useItem": "PRISONBOTTLE"}),
    ("rotom-heat", "HEAT", "use", {"useItem": "ROTOMCATALOG", "formMoves": {"sig": "OVERHEAT"}}),
    ("rotom-wash", "WASH", "use", {"useItem": "ROTOMCATALOG", "formMoves": {"sig": "HYDROPUMP"}}),
    ("rotom-frost", "FROST", "use", {"useItem": "ROTOMCATALOG", "formMoves": {"sig": "BLIZZARD"}}),
    ("rotom-fan", "FAN", "use", {"useItem": "ROTOMCATALOG", "formMoves": {"sig": "AIRSLASH"}}),
    ("rotom-mow", "MOW", "use", {"useItem": "ROTOMCATALOG", "formMoves": {"sig": "LEAFSTORM"}}),
    ("deoxys-attack", "ATTACK", "use", {"useItem": "METEORITE"}),
    ("deoxys-defense", "DEFENSE", "use", {"useItem": "METEORITE"}),
    ("deoxys-speed", "SPEED", "use", {"useItem": "METEORITE"}),
    ("oricorio-pom-pom", "POMPOM", "use", {"useItem": "YELLOWNECTAR"}),
    ("oricorio-pau", "PAU", "use", {"useItem": "PINKNECTAR"}),
    ("oricorio-sensu", "SENSU", "use", {"useItem": "PURPLENECTAR"}),
    ("zygarde-10", "TEN", "use", {"useItem": "ZYGARDECUBE"}),
    # 합체(블랙큐레무 · 황혼의 갈기 네크로즈마 · 백마 탄 버드렉스)와 울트라버스트는 넣지 않는다 - 사용자 결정
    # (2026-10-17 "합체하는 아이템은 빼줘"). 울트라네크로즈마는 합체한 네크로즈마만 될 수 있어 같이 뺐다.
    # ---- 배틀 중에만 (특성·도구)
    ("greninja-ash", "ASH", "battle", {"ability": "BATTLEBOND"}),
    ("zygarde-complete", "COMPLETE", "battle", {"ability": "POWERCONSTRUCT"}),
    ("meloetta-pirouette", "PIROUETTE", "battle", {"move": "RELICSONG"}),
    # 그동안 문구만 나오던 배틀 중 폼 (특성). 이제 도트도 바뀐다 - abilities.form_look 이 이 번호를 싣는다.
    ("darmanitan-zen", "ZEN", "battle", {"ability": "ZENMODE"}),
    ("aegislash-blade", "BLADE", "battle", {"ability": "STANCECHANGE"}),
    ("wishiwashi-school", "SCHOOL", "battle", {"ability": "SCHOOLING"}),
    ("minior-red", "CORE", "battle", {"ability": "SHIELDSDOWN"}),
    ("mimikyu-busted", "BUSTED", "battle", {"ability": "DISGUISE"}),
    ("castform-sunny", "SUNNY", "battle", {"ability": "FORECAST"}),
    ("castform-rainy", "RAINY", "battle", {"ability": "FORECAST"}),
    ("castform-snowy", "SNOWY", "battle", {"ability": "FORECAST"}),
    ("eiscue-noice", "NOICE", "battle", {"ability": "ICEFACE"}),
    ("morpeko-hangry", "HANGRY", "battle", {"ability": "HUNGERSWITCH"}),
    ("palafin-hero", "HERO", "battle", {"ability": "ZEROTOHERO", "formKr": "마이티폼"}),
    ("terapagos-terastal", "TERASTAL", "battle", {"ability": "TERASHIFT", "formKr": "테라스탈폼"}),
    # ---- 그 기술을 알면 그 모습 (도트만)
    ("keldeo-resolute", "RESOLUTE", "move", {"move": "SECRETSWORD"}),
    # ---- 진화할 때 정해진다 (도감 species 의 evo 갈래에 "form" 을 적는다, 2.1.0)
    # 치고마가 악의 족자를 쓰면 일격의 태세(원래 종), 물의 족자를 쓰면 연격의 태세. 한 번 정하면 못 바꾼다 (본가대로).
    ("urshifu-rapid-strike", "RAPIDSTRIKE", "evo", {"formKr": "연격의 태세"}),
]
# 걷는 도트: SpriteCollab 에서 이 이름의 폴더를 찾는다 (여러 개면 앞의 것부터).
COLLAB = {
    "giratina-origin": ["Origin"], "dialga-origin": ["Origin"], "palkia-origin": ["Origin"],
    "zacian-crowned": ["Crowned_Sword"], "zamazenta-crowned": ["Crowned_Shield"],
    "ogerpon-wellspring-mask": ["Wellspring_Mask", "Wellspring"],
    "ogerpon-hearthflame-mask": ["Hearthflame_Mask", "Hearthflame"],
    "ogerpon-cornerstone-mask": ["Cornerstone_Mask", "Cornerstone"],
    "kyogre-primal": ["Primal"], "groudon-primal": ["Primal"], "shaymin-sky": ["Sky"],
    "tornadus-therian": ["Therian"], "thundurus-therian": ["Therian"], "landorus-therian": ["Therian"],
    "enamorus-therian": ["Therian"], "hoopa-unbound": ["Unbound"],
    "rotom-heat": ["Heat"], "rotom-wash": ["Wash"], "rotom-frost": ["Frost"], "rotom-fan": ["Fan"],
    "rotom-mow": ["Mow"], "deoxys-attack": ["Attack"], "deoxys-defense": ["Defense"],
    "deoxys-speed": ["Speed"], "oricorio-pom-pom": ["Pom_Pom"], "oricorio-pau": ["Pa_U"],
    "oricorio-sensu": ["Sensu"], "zygarde-10": ["10"], "greninja-ash": ["Ash"],
    "zygarde-complete": ["Complete"],
    "meloetta-pirouette": ["Pirouette"], "keldeo-resolute": ["Resolute"],
    "darmanitan-zen": ["Zen"], "aegislash-blade": ["Blade"], "wishiwashi-school": ["School"],
    "minior-red": ["Red"], "mimikyu-busted": ["Busted"], "castform-sunny": ["Sunny"],
    "castform-rainy": ["Rainy"], "castform-snowy": ["Snowy"], "eiscue-noice": ["Noice"],
    "morpeko-hangry": ["Hangry"], "palafin-hero": ["Hero"], "terapagos-terastal": ["Terastal"],
    "urshifu-rapid-strike": ["Rapid_Strike"],
}
# 레벨 0(진화할 때 배우는 기술)까지 싣는 폼. 다른 폼은 진화로 되는 게 아니라 레벨 0 을 거른다
# (개굴닌자 · 마이티폼의 레벨 0 은 원래 종의 진화 기술이라 폼 표에 넣으면 안 된다).
# 연격의 태세는 진화하면서 수류연타를 배운다 - evolution.apply 가 폼 표의 레벨 0 을 본다.
EVO_MOVES = {"urshifu-rapid-strike"}


def rows(name):
    with open(os.path.join(C, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def key(ident):
    return re.sub(r"[^A-Za-z0-9]", "", ident).upper()


def build(dex):
    by_num = dict((s["num"], s) for s in dex["species"])
    poke = dict((r["identifier"], r) for r in rows("pokemon.csv"))
    stats = rows("pokemon_stats.csv")
    ptypes = rows("pokemon_types.csv")
    pabil = rows("pokemon_abilities.csv")
    types_csv = dict((r["id"], r["identifier"]) for r in rows("types.csv"))
    abil_csv = dict((r["id"], r["identifier"]) for r in rows("abilities.csv"))
    pforms = dict((r["pokemon_id"], r) for r in rows("pokemon_forms.csv"))
    fname = dict((r["pokemon_form_id"], r["form_name"]) for r in rows("pokemon_form_names.csv")
                 if r["local_language_id"] == KO)
    tracker = showdown = None
    tp = os.path.join(C, "spritecollab_tracker.json")
    if os.path.exists(tp):
        with open(tp, encoding="utf-8") as f:
            tracker = json.load(f)
    sp = os.path.join(C, "form_showdown.json")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            showdown = json.load(f)
    old = dict((m["internal"], m) for m in dex.get("forms") or [])
    # 폼만의 레벨업 기술 (1.13.1, 게시판 #264 '쉐이미 스카이폼은 Lv.64 에 에어슬래시를 배운다는데 떠올리기에 없다').
    # SV 표에서 원래 종과 다른 폼(테오키스 셋 · 스카이폼 · 굴레를 벗어난 후파)만 moves 를 따로 적는다.
    # 나머지는 지금처럼 원래 종의 표를 같이 쓴다 (Pokedex.__init__ 이 물려준다).
    sv = next((r["id"] for r in rows("version_groups.csv") if r["identifier"] == "scarlet-violet"), "25")
    move_ident = dict((r["id"], key(r["identifier"])) for r in rows("moves.csv"))
    keep0 = set(poke[i]["id"] for i in EVO_MOVES if i in poke)
    learn = {}
    for r in rows("pokemon_moves.csv"):
        if r["version_group_id"] == sv and r["pokemon_move_method_id"] == "1" \
                and (int(r["level"] or 0) > 0 or r["pokemon_id"] in keep0):
            learn.setdefault(r["pokemon_id"], []).append((int(r["level"]), move_ident.get(r["move_id"])))
    out, notes = [], []
    for ident, fkey, kind, extra in FORMS:
        r = poke.get(ident)
        if not r:
            notes.append("원본에 없음: %s" % ident)
            continue
        pid = r["id"]
        base = by_num.get(int(r["species_id"]))
        if not base:
            notes.append("원래 종을 못 찾음: %s" % ident)
            continue
        st = dict((STAT[s["stat_id"]], int(s["base_stat"])) for s in stats if s["pokemon_id"] == pid)
        tys = [key(types_csv[t["type_id"]]) for t in
               sorted((t for t in ptypes if t["pokemon_id"] == pid), key=lambda t: int(t["slot"]))]
        ab = sorted((a for a in pabil if a["pokemon_id"] == pid), key=lambda a: int(a["slot"]))
        normal = [key(abil_csv[a["ability_id"]]) for a in ab if a["is_hidden"] == "0"]
        hidden = [key(abil_csv[a["ability_id"]]) for a in ab if a["is_hidden"] == "1"]
        missing = [a for a in normal + hidden if a not in dex["abilities"]]
        if missing:
            notes.append("도감에 없는 특성 %s: %s - 원래 종 것을 쓴다" % (ident, ",".join(missing)))
        normal = [a for a in normal if a in dex["abilities"]] or list(base.get("abil") or [])
        hidden = [a for a in hidden if a in dex["abilities"]]
        pf = pforms.get(pid) or {}
        fkr = extra.get("formKr") or fname.get(pf.get("id")) or fkey.title()
        entry = {
            "internal": base["internal"] + "_" + fkey, "num": int(pid),
            "kr": base["kr"], "en": base.get("en"), "formKr": fkr,
            "formOf": base["internal"], "form": fkey, "formKind": kind,
            "base": st, "types": tys, "abil": normal,
            "hidden": hidden[0] if hidden else base.get("hidden"),
            "kg": round(float(r["weight"]) / 10.0, 1), "height": round(float(r["height"]) / 10.0, 1),
            "spawnable": False, "evo": [], "prevo": None,
        }
        for k in ("items", "useItem", "formMoves", "ability", "move"):
            if k in extra:
                entry[k] = extra[k]
        own = sorted((lv, mv) for lv, mv in learn.get(pid, []) if mv in dex["moves"])
        if own and set(mv for _lv, mv in own) != set(mv for _lv, mv in base.get("moves") or []):
            entry["moves"] = [[lv, mv] for lv, mv in own]
        # 바탕화면 도트
        prev = old.get(entry["internal"]) or {}
        walk, dot = prev.get("walk"), bool(prev.get("dot"))
        if tracker is not None:
            walk = None
            subs = (tracker.get("%04d" % base["num"]) or {}).get("subgroups") or {}
            for want in COLLAB.get(ident, []):
                hit = [k for k, v in sorted(subs.items())
                       if v.get("name") == want and "Walk" in (v.get("sprite_files") or {})]
                if hit:
                    walk = "%04d/%s" % (base["num"], hit[0])
                    break
        if showdown is not None:
            dot = bool(showdown.get(str(pid)))
        if walk:
            entry["walk"] = walk
        entry["dot"] = dot
        out.append(entry)
    out.sort(key=lambda m: m["num"])
    n_walk = sum(1 for m in out if m.get("walk"))
    n_dot = sum(1 for m in out if m["dot"])
    notes.append("바탕화면 도트: 걷는 도트 %d폼 · 배틀 도트 %d폼 · 둘 다 없음 %d폼"
                 % (n_walk, n_dot, sum(1 for m in out if not m.get("walk") and not m["dot"])))
    return out, notes


def main():
    check = "--check" in sys.argv
    with open(DEX, encoding="utf-8") as f:
        dex = json.load(f)
    forms, notes = build(dex)
    changed = dex.get("forms") != forms
    print("폼 %d개 (지니기 %d · 원시회귀 %d · 쓰기 %d · 배틀 %d · 기술 %d · 진화 %d)" % (
        len(forms), *[sum(1 for m in forms if m["formKind"] == k)
                      for k in ("held", "primal", "use", "battle", "move", "evo")]))
    for n in notes:
        print("  -", n)
    if check:
        print("바뀔 것이 있다" if changed else "그대로다")
        return 1 if changed else 0
    dex["forms"] = forms
    with open(DEX, "w", encoding="utf-8") as f:
        json.dump(dex, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("썼다: %s" % os.path.relpath(DEX, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
