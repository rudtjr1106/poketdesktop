# -*- coding: utf-8 -*-
"""정석 도감(pokedex.json)을 만든다.

타입/종족값/특성/기술/성장곡선/포획률은 **PokeAPI 공식 데이터**를 쓴다.
포켓몬 Z 같은 팬게임은 자체적으로 값을 손봐놓기 때문에 그대로 쓰면 안 된다.
한국어 이름도 PokeAPI 의 공식 한글 명칭을 쓴다.

도트도 정식 이미지를 쓴다(서버가 PokeAPI 스프라이트를 받아 캐시한다).
팬게임 도트는 타입이 바뀐 종을 색까지 고쳐놔서 쓰지 않는다.

    python tools/build_pokedex.py --out server/data/pokedex.json
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

NEEDED = [
    "pokemon_species.csv", "pokemon_species_names.csv", "pokemon.csv",
    "pokemon_types.csv", "types.csv", "type_names.csv", "type_efficacy.csv",
    "pokemon_stats.csv", "stats.csv", "pokemon_abilities.csv", "abilities.csv",
    "ability_names.csv", "moves.csv", "move_names.csv", "move_damage_classes.csv",
    "growth_rates.csv", "egg_groups.csv", "pokemon_egg_groups.csv",
    "pokemon_moves.csv", "pokemon_evolution.csv", "evolution_triggers.csv",
    "move_meta.csv", "move_meta_stat_changes.csv", "move_meta_ailments.csv",
]

KO = 3          # PokeAPI 언어 id: 한국어
EN = 9          # 영어
LEVEL_UP = 1    # pokemon_move_methods: 레벨업으로 배움
MAX_DEX = 1025  # 9세대까지

GROWTH = {
    "slow": "slow", "medium": "medium", "fast": "fast",
    "medium-slow": "medium_slow",
    "slow-then-very-fast": "erratic",
    "fast-then-very-slow": "fluctuating",
}
STAT_ID = {1: "hp", 2: "atk", 3: "def", 4: "spa", 5: "spd", 6: "spe"}
# 기술의 능력 변화는 명중률/회피율까지 다룬다
MOVE_STAT_ID = dict(STAT_ID)
MOVE_STAT_ID.update({7: "acc", 8: "eva"})

# 울트라비스트와 패러독스는 PokeAPI 가 전설로 표시하지 않는 경우가 있다.
# 야생에 흔히 나오면 곤란하므로 전설과 같이 취급한다.
EXTRA_RESTRICTED = """
nihilego buzzwole pheromosa xurkitree celesteela kartana guzzlord
poipole naganadel stakataka blacephalon
great-tusk scream-tail brute-bonnet flutter-mane slither-wing sandy-shocks
roaring-moon walking-wake gouging-fire raging-bolt
iron-treads iron-bundle iron-hands iron-jugulis iron-moth iron-thorns
iron-valiant iron-leaves iron-boulder iron-crown
"""


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def fetch(name):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, name)
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        sys.stderr.write("  받는 중: %s\n" % name)
        with urllib.request.urlopen(CSV_BASE + "/" + name, timeout=180) as r:
            data = r.read()
        with open(p, "wb") as f:
            f.write(data)
    return p


def rows(name):
    with io.open(fetch(name), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            yield r


def as_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- 본작업
def build():
    restricted = set(norm(x) for x in EXTRA_RESTRICTED.split() if x.strip())

    # ---- 이름 ----
    kr_name, kr_genus, en_name = {}, {}, {}
    for r in rows("pokemon_species_names.csv"):
        sid, lang = as_int(r["pokemon_species_id"]), as_int(r["local_language_id"])
        if lang == KO:
            kr_name[sid] = r["name"]
            kr_genus[sid] = r.get("genus") or ""
        elif lang == EN:
            en_name[sid] = r["name"]

    # ---- 성장곡선 / 알그룹 / 타입 / 능력치 이름 ----
    growth = dict((as_int(r["id"]), GROWTH.get(r["identifier"], "medium"))
                  for r in rows("growth_rates.csv"))
    egg_ident = dict((as_int(r["id"]), r["identifier"]) for r in rows("egg_groups.csv"))
    egg_of = {}
    for r in rows("pokemon_egg_groups.csv"):
        egg_of.setdefault(as_int(r["species_id"]), []).append(
            egg_ident.get(as_int(r["egg_group_id"]), "?"))

    type_ident = dict((as_int(r["id"]), r["identifier"].upper())
                      for r in rows("types.csv") if as_int(r["id"]) < 10000)
    type_kr = {}
    for r in rows("type_names.csv"):
        if as_int(r["local_language_id"]) == KO:
            type_kr[as_int(r["type_id"])] = r["name"]

    # 타입 상성표: 공격타입 -> {방어타입: 배율}
    chart = {}
    for r in rows("type_efficacy.csv"):
        a, d = as_int(r["damage_type_id"]), as_int(r["target_type_id"])
        if a in type_ident and d in type_ident:
            chart.setdefault(type_ident[a], {})[type_ident[d]] = \
                as_int(r["damage_factor"]) / 100.0

    types_out = {}
    for tid, ident in type_ident.items():
        types_out[ident] = {"id": tid, "en": ident.title(),
                            "kr": type_kr.get(tid, ident.title()),
                            "eff": chart.get(ident, {})}

    # ---- 특성 ----
    abil_ident = dict((as_int(r["id"]), r["identifier"].upper().replace("-", ""))
                      for r in rows("abilities.csv"))
    abil_kr = {}
    for r in rows("ability_names.csv"):
        if as_int(r["local_language_id"]) == KO:
            abil_kr[as_int(r["ability_id"])] = r["name"]
    abil_out = {}
    for aid, ident in abil_ident.items():
        abil_out[ident] = {"id": aid, "en": ident.title(),
                           "kr": abil_kr.get(aid, ident.title())}

    # ---- 기술 ----
    dmg_class = dict((as_int(r["id"]), r["identifier"])
                     for r in rows("move_damage_classes.csv"))
    move_kr = {}
    for r in rows("move_names.csv"):
        if as_int(r["local_language_id"]) == KO:
            move_kr[as_int(r["move_id"])] = r["name"]
    # 기술 효과 (상태이상, 능력변화, 흡수, 풀죽음, 연속타)
    ailment = dict((as_int(r["id"]), r["identifier"])
                   for r in rows("move_meta_ailments.csv"))
    meta = dict((as_int(r["move_id"]), r) for r in rows("move_meta.csv"))
    stat_change = {}
    for r in rows("move_meta_stat_changes.csv"):
        st = MOVE_STAT_ID.get(as_int(r["stat_id"]))
        if st:
            stat_change.setdefault(as_int(r["move_id"]), []).append(
                [st, as_int(r["change"])])

    move_ident, move_out = {}, {}
    for r in rows("moves.csv"):
        mid = as_int(r["id"])
        if mid >= 10000:
            continue
        ident = r["identifier"].upper().replace("-", "")
        move_ident[mid] = ident
        move_out[ident] = {
            "id": mid, "en": r["identifier"].replace("-", " ").title(),
            "kr": move_kr.get(mid, ident.title()),
            "type": type_ident.get(as_int(r["type_id"]), "NORMAL"),
            "cat": dmg_class.get(as_int(r["damage_class_id"]), "status"),
            "power": as_int(r["power"]), "acc": as_int(r["accuracy"]),
            "pp": as_int(r["pp"]), "pri": as_int(r["priority"]),
            "eff": as_int(r["effect_chance"]),
        }
        m = meta.get(mid)
        if m:
            ail = ailment.get(as_int(m.get("meta_ailment_id")), "none")
            move_out[ident].update({
                "ail": None if ail in ("none", "unknown") else ail,
                "ailChance": as_int(m.get("ailment_chance")),
                "stat": stat_change.get(mid, []),
                "statChance": as_int(m.get("stat_chance")),
                "drain": as_int(m.get("drain")),       # 양수=흡수, 음수=반동
                "heal": as_int(m.get("healing")),
                "crit": as_int(m.get("crit_rate")),
                "flinch": as_int(m.get("flinch_chance")),
                "hits": [as_int(m.get("min_hits"), 1) or 1,
                         as_int(m.get("max_hits"), 1) or 1],
            })

    # ---- 종 기본 ----
    species_row = {}
    for r in rows("pokemon_species.csv"):
        sid = as_int(r["id"])
        if 1 <= sid <= MAX_DEX:
            species_row[sid] = r

    # 기본 폼만 (메가/리전폼 제외)
    poke_of_species, poke_row = {}, {}
    for r in rows("pokemon.csv"):
        sid = as_int(r["species_id"])
        if sid in species_row and r.get("is_default") == "1":
            pid = as_int(r["id"])
            poke_of_species[sid] = pid
            poke_row[pid] = r
    pid_to_sid = dict((v, k) for k, v in poke_of_species.items())

    # ---- 타입/능력치/특성 ----
    ptypes, pstats, pevs, pabil = {}, {}, {}, {}
    for r in rows("pokemon_types.csv"):
        pid = as_int(r["pokemon_id"])
        if pid in pid_to_sid:
            ptypes.setdefault(pid, []).append(
                (as_int(r["slot"]), type_ident.get(as_int(r["type_id"]), "NORMAL")))
    for r in rows("pokemon_stats.csv"):
        pid, st = as_int(r["pokemon_id"]), as_int(r["stat_id"])
        if pid in pid_to_sid and st in STAT_ID:
            pstats.setdefault(pid, {})[STAT_ID[st]] = as_int(r["base_stat"])
            pevs.setdefault(pid, {})[STAT_ID[st]] = as_int(r["effort"])
    for r in rows("pokemon_abilities.csv"):
        pid = as_int(r["pokemon_id"])
        if pid in pid_to_sid:
            pabil.setdefault(pid, []).append(
                (as_int(r["slot"]), abil_ident.get(as_int(r["ability_id"]), ""),
                 r["is_hidden"] == "1"))

    # ---- 레벨업 기술 (가장 최신 버전그룹 기준) ----
    sys.stderr.write("  레벨업 기술 집계 중 (파일이 큽니다)...\n")
    best_vg, tmp = {}, {}
    for r in rows("pokemon_moves.csv"):
        if as_int(r["pokemon_move_method_id"]) != LEVEL_UP:
            continue
        pid = as_int(r["pokemon_id"])
        if pid not in pid_to_sid:
            continue
        vg, lv, mid = as_int(r["version_group_id"]), as_int(r["level"]), as_int(r["move_id"])
        if lv <= 0 or mid not in move_ident:
            continue
        if vg > best_vg.get(pid, -1):
            best_vg[pid] = vg
            tmp[pid] = []
        if vg == best_vg[pid]:
            tmp[pid].append((lv, move_ident[mid]))
    lvmoves = {}
    for pid, lst in tmp.items():
        seen, out = set(), []
        for lv, mv in sorted(lst):
            if mv not in seen:
                seen.add(mv)
                out.append([lv, mv])
        lvmoves[pid] = out

    # ---- 진화 (최소 레벨 계산용) ----
    trigger = dict((as_int(r["id"]), r["identifier"])
                   for r in rows("evolution_triggers.csv"))
    evo_info = {}
    for r in rows("pokemon_evolution.csv"):
        sid = as_int(r["evolved_species_id"])
        if sid in species_row and sid not in evo_info:
            evo_info[sid] = (trigger.get(as_int(r["evolution_trigger_id"]), "?"),
                             as_int(r["minimum_level"], 0))

    # ---- 조립 ----
    species = []
    for sid in sorted(species_row):
        r = species_row[sid]
        pid = poke_of_species.get(sid)
        if not pid:
            continue
        ident = r["identifier"]
        internal = norm(ident)
        gender_rate = as_int(r["gender_rate"], -1)
        legendary = (r["is_legendary"] == "1" or r["is_mythical"] == "1"
                     or internal in restricted)

        abils = sorted(pabil.get(pid, []))
        species.append({
            "num": sid,
            "internal": internal,
            "en": en_name.get(sid, ident.title()),
            "kr": kr_name.get(sid) or en_name.get(sid, ident.title()),
            "kind": kr_genus.get(sid, ""),
            "gen": as_int(r["generation_id"]),
            "types": [t for _s, t in sorted(ptypes.get(pid, []))] or ["NORMAL"],
            "base": pstats.get(pid, {}),
            "ev": pevs.get(pid, {}),
            "femaleRatio": (None if gender_rate < 0 else gender_rate / 8.0),
            "growth": growth.get(as_int(r["growth_rate_id"]), "medium"),
            "baseExp": as_int(poke_row[pid].get("base_experience"), 0),
            "catch": as_int(r["capture_rate"], 45),
            "happiness": as_int(r["base_happiness"], 70),
            "abil": [a for _s, a, h in abils if not h and a],
            "hidden": next((a for _s, a, h in abils if h and a), None),
            "moves": lvmoves.get(pid, []),
            "egg": egg_of.get(sid, []),
            "isBaby": r["is_baby"] == "1",
            "prevo": as_int(r["evolves_from_species_id"], 0) or None,
            "height": as_int(poke_row[pid].get("height")) / 10.0,
            "weight": as_int(poke_row[pid].get("weight")) / 10.0,
            "legendary": legendary,
        })

    annotate(species, evo_info)
    return {
        "version": 2,
        "source": "PokeAPI (정석 데이터)",
        "counts": {"species": len(species), "moves": len(move_out),
                   "abilities": len(abil_out), "types": len(types_out)},
        "types": types_out, "abilities": abil_out, "moves": move_out,
        "species": species,
    }


NONLEVEL_GAP = 16
MAX_MIN_LEVEL = 55


def annotate(species, evo_info):
    """진화 단계, 최소 등장 레벨, 야생 등장 가중치."""
    by = dict((s["num"], s) for s in species)

    def resolve(num, seen=None):
        s = by.get(num)
        if s is None:
            return 0, 1
        if "stage" in s:
            return s["stage"], s["minLevel"]
        seen = seen or set()
        if num in seen:
            s["stage"], s["minLevel"] = 0, 1
            return 0, 1
        seen.add(num)
        p = s.get("prevo")
        if not p or p not in by:
            s["stage"], s["minLevel"] = 0, 1
            return 0, 1
        pstage, plevel = resolve(p, seen)
        trig, minlv = evo_info.get(num, ("?", 0))
        if trig == "level-up" and minlv:
            lv = minlv
        elif minlv:
            lv = minlv
        else:
            lv = plevel + NONLEVEL_GAP
        lv = max(2, min(MAX_MIN_LEVEL, max(lv, plevel + 1)))
        s["stage"], s["minLevel"] = pstage + 1, lv
        return s["stage"], s["minLevel"]

    for s in species:
        resolve(s["num"])
    for s in species:
        s["spawnable"] = not s["legendary"]
        s["weight"] = max(3, s["catch"]) if s["spawnable"] else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--refresh", action="store_true", help="받아둔 CSV 를 다시 받는다")
    a = ap.parse_args()

    if a.refresh:
        for n in NEEDED:
            p = os.path.join(CACHE, n)
            if os.path.exists(p):
                os.remove(p)

    data = build()
    outdir = os.path.dirname(os.path.abspath(a.out))
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    sp = data["species"]
    print("")
    print("포켓몬 %d  기술 %d  특성 %d  타입 %d"
          % (len(sp), len(data["moves"]), len(data["abilities"]), len(data["types"])))
    print("전설/환상/UB/패러독스: %d마리 (야생 제외)"
          % sum(1 for s in sp if s["legendary"]))
    print("야생 등장 가능: %d마리" % sum(1 for s in sp if s["spawnable"]))
    print("세대별: " + "  ".join(
        "%d세대 %d" % (g, sum(1 for s in sp if s["gen"] == g)) for g in range(1, 10)))


if __name__ == "__main__":
    main()
