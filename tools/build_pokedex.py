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
    "move_flags.csv", "move_flag_map.csv",
    "items.csv", "item_names.csv", "item_categories.csv",
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
# 능력 변화를 누구에게 거는가. 이걸 틀리면 자기를 강화하는 기술이
# 상대를 강화한다.
#
# 위력이 있는 기술은 PokeAPI 의 분류가 대상을 그대로 알려준다.
#   damage-raise  자기 자신에게 건다. 이름과 달리 '올린다' 는 뜻이 아니라
#                 '자기에게 건다' 는 뜻이다 - 인파이트(방어/특방 하락)와
#                 리프스톰(특공 하락)도 여기 들어간다.
#   damage-lower  상대에게 건다. 깨물어부수기, 막말내뱉기 같은 것들.
#
# 위력이 없는 변화기는 분류가 net-good-stats 하나로 뭉뚱그려져 있어서
# 울음소리(상대)와 칼춤(자기)이 구분되지 않는다. 대신 target 이 정확하다.
# 저주처럼 올리기와 내리기가 섞인 기술도 target 으로만 제대로 갈린다.
SELF_TARGETS = (5, 7, 13)          # 자신 / 자신이나 아군 / 자신과 아군


def _stat_self(move_row, m, meta_cat):
    cat = meta_cat.get(as_int(m.get("meta_category_id")), "")
    if as_int(move_row["power"]):
        return cat == "damage-raise"
    return as_int(move_row["target_id"]) in SELF_TARGETS


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
    meta_cat = dict((as_int(r["id"]), r["identifier"])
                    for r in rows("move_meta_categories.csv"))
    stat_change = {}
    for r in rows("move_meta_stat_changes.csv"):
        st = MOVE_STAT_ID.get(as_int(r["stat_id"]))
        if st:
            stat_change.setdefault(as_int(r["move_id"]), []).append(
                [st, as_int(r["change"])])

    # 기술 플래그. 연출을 고르는 데 쓴다.
    #   contact 접촉 -> 달려들어 때린다 / ballistics 탄환 -> 둥근 것이 날아간다
    #   sound 소리 -> 음파가 퍼진다 / powder 가루 -> 흩날린다 / pulse 파동 -> 고리가 퍼진다
    flag_name = dict((as_int(r["id"]), r["identifier"])
                     for r in rows("move_flags.csv"))
    move_flags = {}
    for r in rows("move_flag_map.csv"):
        f = flag_name.get(as_int(r["move_flag_id"]))
        if f:
            move_flags.setdefault(as_int(r["move_id"]), []).append(f)

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
            "target": as_int(r["target_id"]),
            "flags": sorted(move_flags.get(mid, [])),
        }
        m = meta.get(mid)
        if m:
            ail = ailment.get(as_int(m.get("meta_ailment_id")), "none")
            move_out[ident].update({
                "ail": None if ail in ("none", "unknown") else ail,
                "ailChance": as_int(m.get("ailment_chance")),
                "stat": stat_change.get(mid, []),
                "statSelf": _stat_self(r, m, meta_cat),
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

    # ---- 진화 ----
    # CSV 에는 '어떤 종으로 진화하는가' 만 있고 '무엇에서' 는 없다.
    # 출발종은 pokemon_species.csv 의 evolves_from_species_id 로 이어 붙인다.
    item_ident = dict((as_int(r["id"]), norm(r["identifier"]))
                      for r in rows("items.csv"))
    move_ident = dict((as_int(r["id"]), norm(r["identifier"]))
                      for r in rows("moves.csv"))
    type_ident = dict((as_int(r["id"]), norm(r["identifier"]))
                      for r in rows("types.csv"))
    evo_from, evo_of = load_evolutions(species_row, item_ident, move_ident,
                                       type_ident)

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
            "evo": evo_from.get(sid, []),
            "height": as_int(poke_row[pid].get("height")) / 10.0,
            "weight": as_int(poke_row[pid].get("weight")) / 10.0,
            "legendary": legendary,
        })

    annotate(species, evo_of)
    return {
        "version": 2,
        "source": "PokeAPI (정석 데이터)",
        "counts": {"species": len(species), "moves": len(move_out),
                   "abilities": len(abil_out), "types": len(types_out)},
        "types": types_out, "abilities": abil_out, "moves": move_out,
        "species": species,
    }


# ---------------------------------------------------------------- 진화
# 폼 번호. pokemon.csv 에서 10000 이상은 리전폼/메가/거다이맥스다.
FORM_BASE = 10000

# 교환 진화는 이 게임에 교환이 없으니 도구 사용으로 바꾼다.
# 지닌 물건이 있는 교환진화는 그 물건을 그대로 쓰고,
# 조건 없는 순수 교환은 '연결의끈' 으로 통일한다. (본가 9세대와 같은 방식)
TRADE_ITEM = "LINKINGCORD"

# 이 게임이 실제로 처리할 수 있는 방식
MODE_LEVEL = "level"     # 레벨업
MODE_STONE = "stone"     # 도구 사용
MODE_FRIEND = "friend"   # 친밀도
MODE_SPECIAL = "special"  # 아직 못 하는 것 (자료는 남겨둔다)


def _canonical(r):
    """지금 세대에서 유효한 진화 규칙 행인지.

    is_default 가 0 인 행은 폐지된 옛 세대 규칙이다. 이걸 안 거르면
    리피아가 '이끼바위 옆에서 레벨업'(4~7세대) 으로 남아서, 리프의돌로
    진화하는 지금 규칙을 못 쓴다.

    base_form/evolved_form 이 10000 이상이면 리전폼이다. 이 게임은
    기본 폼만 다루므로 건너뛴다.
    """
    if r["is_default"] != "1":
        return False
    if as_int(r["base_form_id"]) >= FORM_BASE:
        return False
    if as_int(r["evolved_form_id"]) >= FORM_BASE:
        return False
    return True


def _branch(r, trigger, item_ident, move_ident, type_ident):
    """진화 규칙 한 줄 -> 게임이 읽을 수 있는 dict."""
    trig = trigger.get(as_int(r["evolution_trigger_id"]), "?")
    lvl = as_int(r["minimum_level"], 0)
    happy = as_int(r["minimum_happiness"], 0)
    titem = as_int(r["trigger_item_id"], 0)
    hitem = as_int(r["held_item_id"], 0)

    d = {"trigger": trig}
    if trig == "use-item" and titem:
        d["mode"] = MODE_STONE
        d["item"] = item_ident.get(titem, "")
    elif trig == "trade":
        # 교환 -> 도구 사용으로 대체
        d["mode"] = MODE_STONE
        d["item"] = item_ident.get(hitem, TRADE_ITEM) if hitem else TRADE_ITEM
        d["wasTrade"] = True
    elif trig in ("level-up", "other") and happy:
        d["mode"] = MODE_FRIEND
        d["happiness"] = happy
    elif trig in ("level-up", "other") and lvl:
        d["mode"] = MODE_LEVEL
        d["level"] = lvl
    else:
        d["mode"] = MODE_SPECIAL

    # 부가 조건. 게임이 확인할 수 있는 것만 옮긴다.
    if lvl and d["mode"] != MODE_LEVEL:
        d["level"] = lvl
    if r["time_of_day"]:
        d["time"] = r["time_of_day"]          # day | night | dusk
    g = as_int(r["gender_id"], 0)
    if g:
        d["gender"] = "F" if g == 1 else "M"  # 1 암컷 / 2 수컷
    rel = (r["relative_physical_stats"] or "").strip()
    if rel != "":
        d["stats"] = as_int(rel)              # 1 공>방 / -1 공<방 / 0 같음
    if hitem and trig != "trade":
        d["held"] = item_ident.get(hitem, "")
    km = as_int(r["known_move_id"], 0)
    if km:
        d["move"] = move_ident.get(km, "")
    kt = as_int(r["known_move_type_id"], 0)
    if kt:
        d["moveType"] = type_ident.get(kt, "")   # 번호 말고 이름으로 남긴다
    return d


def load_evolutions(species_row, item_ident, move_ident, type_ident):
    """진화표를 두 방향으로 만든다.

        evo_from : {출발종 num: [분기, ...]}   -> species["evo"]
        evo_of   : {도착종 num: 분기}          -> annotate() 의 minLevel 계산용

    출발종은 evolves_from_species_id 로만 알 수 있다. 진화표 자체에는
    '누가' 진화하는지가 안 적혀 있고 '누구로' 만 적혀 있기 때문이다.
    """
    trigger = dict((as_int(r["id"]), r["identifier"])
                   for r in rows("evolution_triggers.csv"))
    evo_from = {}
    evo_of = {}
    for r in rows("pokemon_evolution.csv"):
        if not _canonical(r):
            continue
        sid = as_int(r["evolved_species_id"])
        srow = species_row.get(sid)
        if srow is None:
            continue
        src = as_int(srow["evolves_from_species_id"], 0)
        if not src or src not in species_row:
            continue
        d = _branch(r, trigger, item_ident, move_ident, type_ident)
        d["to"] = norm(srow["identifier"])
        d["toNum"] = sid
        evo_from.setdefault(src, []).append(d)
        if sid not in evo_of:
            evo_of[sid] = d
    for lst in evo_from.values():
        lst.sort(key=lambda x: (x.get("level", 99), x["toNum"]))
    return evo_from, evo_of


NONLEVEL_GAP = 16
MAX_MIN_LEVEL = 55


def annotate(species, evo_of):
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
        # 레벨이 적힌 진화면 그 레벨, 아니면(돌·친밀도·교환) 부모보다
        # 한참 뒤에 나오도록 벌려 둔다. 야생 등장 하한을 정하는 용도다.
        br = evo_of.get(num) or {}
        minlv = br.get("level", 0)
        lv = minlv if minlv else plevel + NONLEVEL_GAP
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
