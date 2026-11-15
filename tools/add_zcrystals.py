# -*- coding: utf-8 -*-
"""Z크리스탈 (시즌 4) · 테라피스 (2.5.0) 를 items.json 에 넣고, common/zmoves.py 가 쓰는 표를 뽑는다.

    python tools/add_zcrystals.py            items.json 에 넣는다 (있으면 고쳐 쓴다)
    python tools/add_zcrystals.py --tables   common/zmoves.py 에 붙여 넣을 표를 찍는다
    python tools/add_zcrystals.py --check    items.json 이 지금 자료와 같은지만 본다
    python tools/add_zcrystals.py --sprites  도구 그림을 채운다 (Z크리스탈은 받고, 테라피스는 그린다)

**build_items.py 를 다시 돌리면 이것도 다시 돌려야 한다** (add_megas.py 와 같다 - build_items 는
PokeAPI 의 '지닐 수 있는 도구' 목록으로 items.json 을 통째로 새로 쓴다).

자료는 전부 tools/_cache 에 이미 있는 것이다 (PokeAPI 의 items.csv·item_names.csv·
item_flavor_text.csv, 쇼다운의 moves.json). 새로 받지 않는다.

  · Z크리스탈 이름·설명      PokeAPI (한국어)
  · 기술마다의 Z위력 예외     쇼다운 moves.json 의 zMove.basePower
  · 변화기의 Z효과           쇼다운 moves.json 의 zMove.boost / zMove.effect
"""
import csv
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "tools", "_cache")
ITEMS = os.path.join(ROOT, "server", "data", "items.json")
DEX = os.path.join(ROOT, "server", "data", "pokedex.json")
sys.path.insert(0, ROOT)

from common import zmoves as ZM          # noqa: E402

KO = "3"                                 # PokeAPI 의 한국어
with io.open(DEX, encoding="utf-8") as _f:
    TYPE_KR = dict((k, v["kr"]) for k, v in json.load(_f)["types"].items())
Z_COST, Z_COST_OWN = 20000, 30000        # 타입 크리스탈 / 전용 크리스탈 (사용자 결정)
SHARD_COST = Z_COST                      # 테라피스 - 타입 Z크리스탈과 같은 값 (11/15 사용자 "Z기술이랑 동일한 가격")


def _rows(name):
    with io.open(os.path.join(CACHE, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _key(s):
    return "".join(c for c in str(s).upper() if c.isalnum())


def _names():
    out = {}
    for r in _rows("item_names.csv"):
        out.setdefault(r["item_id"], {})[r["local_language_id"]] = r["name"]
    return out


def _flavor():
    """도구마다 가장 나중 판의 한국어 설명."""
    best = {}
    for r in _rows("item_flavor_text.csv"):
        if r["language_id"] != KO:
            continue
        vg = int(r["version_group_id"])
        if r["item_id"] not in best or vg >= best[r["item_id"]][0]:
            best[r["item_id"]] = (vg, " ".join(r["flavor_text"].split()))
    return dict((k, v[1]) for k, v in best.items())


def crystals():
    """items.json 에 넣을 Z크리스탈 줄들. 이 게임에 그 폼이 없는 전용 크리스탈은 뺀다."""
    names, flavor = _names(), _flavor()
    out = []
    for r in _rows("items.csv"):
        ident = r["identifier"]
        if not ident.endswith("-z--held"):
            continue
        en = (names.get(r["id"]) or {}).get("9") or ident
        iid = _key(en)
        if iid not in ZM.CRYSTALS:
            continue                                   # 지우피카Z·알로라이Z·울트라네크로Z
        kr = (names.get(r["id"]) or {}).get(KO) or en
        own = ZM.EXCLUSIVE.get(iid)
        # 분류는 'held' 가 아니라 따로 둔다 (메가스톤과 같다). 'held' 는 common/held.py 의 효과표에
        # 든 121종만의 것이라, 거기 넣으면 그 목록과 어긋난다 (common/test_held.py 가 지킨다).
        # 지닐 수 있는지는 분류가 아니라 held.normalize 가 정한다.
        it = {"cat": "zcrystal", "chance": 0, "cost": Z_COST_OWN if own else Z_COST,
              "desc": flavor.get(r["id"]) or "",
              "effect": {"kind": "held"}, "en": en, "id": iid, "ident": ident[:-len("--held")],
              "kr": kr, "rarity": "epic",
              "sell": (Z_COST_OWN if own else Z_COST) // 2, "weight": 0}
        if own:
            it["zFor"] = list(own["species"])
            it["zBase"] = own["base"]
            it["zMove"] = own["move"]
        else:
            it["zType"] = ZM.CRYSTAL_TYPE[iid]
        out.append(it)
    return out


def shards():
    """테라피스 18종 (2.5.0). 스텔라는 안 넣는다. 상점에서만 산다 (드랍 0)."""
    names, flavor = _names(), _flavor()
    out = []
    for r in _rows("items.csv"):
        ident = r["identifier"]
        if not ident.endswith("-tera-shard"):
            continue
        t = _key(ident[:-len("-tera-shard")])
        if t not in ZM.TYPE_Z:                          # 스텔라는 안 넣는다
            continue
        en = (names.get(r["id"]) or {}).get("9") or ident
        kr = (names.get(r["id"]) or {}).get(KO) or en
        # PokeAPI 에 한국어 설명이 없다. 이 게임에서 하는 일을 적는다.
        desc = flavor.get(r["id"]) or ("포켓몬 1마리의 테라 타입을 %s 타입으로 바꾼다. 테라스탈하면 그 타입이 된다."
                                       % TYPE_KR[t])
        out.append({"cat": "misc", "chance": 0, "cost": SHARD_COST,
                    "desc": desc,
                    "effect": {"kind": "tera", "type": t}, "en": en, "id": _key(en),
                    "ident": ident, "kr": kr, "rarity": "epic",
                    "sell": SHARD_COST // 2, "weight": 0})
    return out


def patch(data):
    """items.json 의 자료(dict)에 넣는다. 드랍표는 안 건드린다 - 주워서는 안 나온다."""
    items = data["items"]
    for it in crystals() + shards():
        items[it["id"]] = it
    return data


def _dump(data):
    # 원래 파일과 같은 형식 (sort_keys, 들여쓰기 1, 끝 줄바꿈 없음 - build_items·add_megas 와 같다)
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)


# ---------------------------------------------------------------- 표 뽑기
def tables():
    with io.open(os.path.join(CACHE, "showdown_moves.json"), encoding="utf-8") as f:
        sd = dict((_key(k), v) for k, v in json.load(f).items())
    with io.open(DEX, encoding="utf-8") as f:
        moves = json.load(f)["moves"]
    power, groups = {}, {}
    for k in sorted(moves):
        z = (sd.get(k) or {}).get("zMove") or {}
        if moves[k]["cat"] != "status":
            bp = z.get("basePower")
            if bp and bp != ZM.table_power(moves[k].get("power") or 0):
                power[k] = bp
            elif bp and not moves[k].get("power"):
                power[k] = bp
            continue
        if z.get("boost"):
            b = dict((dict(accuracy="acc", evasion="eva").get(s, s), n) for s, n in z["boost"].items())
            tag = ",".join("%s%+d" % (s, b[s]) for s in ("atk", "def", "spa", "spd", "spe", "acc", "eva")
                           if s in b)
        elif z.get("effect"):
            tag = z["effect"]
        else:
            continue
        groups.setdefault(tag, []).append(k)
    out = ["Z_POWER = {"]
    line = "   "
    for k in sorted(power):
        bit = ' "%s": %d,' % (k, power[k])
        if len(line) + len(bit) > 104:
            out.append(line)
            line = "   "
        line += bit
    out.append(line)
    out.append("}")
    out.append("")
    out.append("_Z_STATUS = (")
    for tag in sorted(groups, key=lambda t: (-len(groups[t]), t)):
        out.append('    ("%s",' % tag)
        line = '     "'
        for k in groups[tag]:
            if len(line) + len(k) + 1 > 104:
                out.append(line.rstrip() + ' "')
                line = '     "'
            line += k + " "
        out.append(line.rstrip() + '"),')
    out.append(")")
    return "\n".join(out)


# ---------------------------------------------------------------- 그림
SPRITES = os.path.join(ROOT, "server", "data", "item_sprites")
Z_SPRITE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/%s--bag.png"
# 테라피스는 공개 도트 저장소(PokeAPI·pokesprite)에 그림이 없다. 타입 색 조각을 직접 그린다.
# Z크리스탈 그림을 못 받았을 때도 같은 조각을 그린다.
TYPE_RGB = {
    "NORMAL": (168, 167, 122), "FIRE": (238, 129, 48), "WATER": (99, 144, 240),
    "ELECTRIC": (247, 208, 44), "GRASS": (122, 199, 76), "ICE": (150, 217, 214),
    "FIGHTING": (194, 46, 40), "POISON": (163, 62, 161), "GROUND": (226, 191, 101),
    "FLYING": (169, 143, 243), "PSYCHIC": (249, 85, 135), "BUG": (166, 185, 26),
    "ROCK": (182, 161, 54), "GHOST": (115, 87, 151), "DRAGON": (111, 53, 252),
    "DARK": (112, 87, 70), "STEEL": (183, 183, 206), "FAIRY": (214, 133, 173),
}


def _fetch(url):
    """그림 한 장. 이 맥의 파이썬에는 인증서가 없어 urllib 이 실패한다 - 그때는 curl 로 받는다."""
    import subprocess
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "poketdesktop"}),
                                    timeout=20) as r:
            data = r.read()
    except Exception:                                        # noqa: BLE001
        try:
            data = subprocess.run(["curl", "-fsSL", "--max-time", "20", url], capture_output=True,
                                  check=True).stdout
        except Exception:                                    # noqa: BLE001
            return None
    return data if data and data[:4] == b"\x89PNG" else None


def shard_png(rgb, size=32):
    """테라피스: 타입 색의 뾰족한 결정 조각 (Z크리스탈 그림을 못 받았을 때도)."""
    from PIL import Image, ImageDraw
    big = size * 4                                           # 크게 그려 줄인다 (가장자리가 매끈해진다)
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    dark = tuple(int(c * 0.45) for c in rgb) + (255,)
    mid = tuple(rgb) + (255,)
    lite = tuple(min(255, int(c + (255 - c) * 0.55)) for c in rgb) + (255,)
    u = big / 32.0
    body = [(16, 2), (25, 11), (22, 27), (12, 30), (6, 14)]
    d.polygon([(x * u, y * u) for x, y in body], fill=mid, outline=dark)
    d.polygon([(x * u, y * u) for x, y in [(16, 2), (25, 11), (16, 14)]], fill=lite)
    d.polygon([(x * u, y * u) for x, y in [(16, 14), (22, 27), (12, 30)]], fill=dark[:3] + (120,))
    d.line([(x * u, y * u) for x, y in body + body[:1]], fill=dark, width=int(u * 1.6))
    d.line([(16 * u, 2 * u), (16 * u, 14 * u)], fill=dark, width=int(u))
    d.line([(6 * u, 14 * u), (16 * u, 14 * u), (25 * u, 11 * u)], fill=dark, width=int(u))
    out = io.BytesIO()
    img.resize((size, size), Image.LANCZOS).save(out, "PNG")
    return out.getvalue()


def sprites(force=False):
    """Z크리스탈은 받고(못 받으면 그 타입 색 조각), 테라피스는 그린다."""
    got = drawn = kept = 0
    for it in crystals() + shards():
        path = os.path.join(SPRITES, it["id"] + ".png")
        if os.path.exists(path) and not force:
            kept += 1
            continue
        data = None
        if it["id"] in ZM.CRYSTALS:
            data = _fetch(Z_SPRITE % it["ident"])
        if data:
            got += 1
        else:
            t = it.get("zType") or (it.get("effect") or {}).get("type") or "NORMAL"
            data = shard_png(TYPE_RGB.get(t, TYPE_RGB["NORMAL"]))
            drawn += 1
        with open(path, "wb") as f:
            f.write(data)
    print("그림: 받음 %d, 직접 그림 %d, 이미 있음 %d" % (got, drawn, kept))


def main():
    if "--tables" in sys.argv:
        print(tables())
        return 0
    if "--sprites" in sys.argv:
        sprites("--force" in sys.argv)
        return 0
    with io.open(ITEMS, encoding="utf-8") as f:
        raw = f.read()
    data = patch(json.loads(raw))
    new = _dump(data)
    n_z = sum(1 for it in data["items"].values() if it["id"] in ZM.CRYSTALS)
    n_t = sum(1 for it in data["items"].values() if (it.get("effect") or {}).get("kind") == "tera")
    if "--check" in sys.argv:
        ok = new == raw
        print("items.json: Z크리스탈 %d개, 테라피스 %d개 - %s" % (n_z, n_t, "같다" if ok else "다르다 (다시 돌릴 것)"))
        return 0 if ok else 1
    with io.open(ITEMS, "w", encoding="utf-8") as f:
        f.write(new)
    print("items.json: Z크리스탈 %d개, 테라피스 %d개를 넣었다 (도구 %d개)" % (n_z, n_t, len(data["items"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
