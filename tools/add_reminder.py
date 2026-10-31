# -*- coding: utf-8 -*-
"""'기술 떠올리기' 로만 배우는 기술을 도감(pokedex.json)의 종마다 remind 칸에 넣는다 (1.13).

    python tools/add_reminder.py            # 넣는다 (있으면 고쳐 쓴다)
    python tools/add_reminder.py --check    # 도감이 지금 자료와 같은지만 본다

2026-10-17 사용자 제보: "오거폰 기술 떠올리기에는 우드혼이 없다". 본가(SV)에서 오거폰의 우드혼 · 두번차기는
**기술 떠올리기로 배운다** (PokémonDB · Serebii 의 오거폰 '떠올리기' 목록). 그런데 PokeAPI 는 알을 낳지 못하는
종의 이런 기술을 '알 기술' 로 적어 두어서, 레벨업 표만 읽는 build_pokedex 가 빠뜨렸다 - 이 게임에는 교배가
없고 알 기술은 같은 기술의 기술머신으로만 배우는데, 우드혼은 기술머신이 없어 어디서도 못 배웠다.

**무엇을 넣나:** 알을 낳지 못하는 종(알 그룹 no-eggs) 가운데 **아기 포켓몬이 아닌 것**의 SV 알 기술 전부.
아기 포켓몬(피츄 · 리오르 …)의 알 기술은 본가에서도 진화형의 교배로 물려받는 진짜 알 기술이라 넣지 않는다.

**손으로 넣는 것 (MANUAL):** 본가에서도 교배로만 배우는데, 이 게임에서는 그 기술이 있어야 쓰는 것이 있어서
빠지면 안 되는 기술. 피카츄의 볼트태클이 그렇다 - 피카츄Z(필살피카슛)의 바탕 기술이다 (2026-10-19 게시판 #277).
기술이 있어야 쓰는 것(전용 Z크리스탈 · 기술 메가진화 · 기술 폼 · 기술 진화)은 server/test_move_needs.py 가 이
게임에서 배울 수 있는지 본다 - 못 배우는 것이 생기면 그 검사가 떨어지고, 여기에 넣으면 된다.

**본가 최신작의 알 기술 · 가르침 기술 가운데 기술머신이 없는 것 (1.13.3, 사용자 결정):** 2026-10-20 전수 검사
(tools/learn_audit.py)에서 교배가 없어 알 기술 1,619줄, 가르침 기술 69줄(기술머신이 없는 13가지)을 어디서도 못
배웠다. 기술머신이 있는 것은 build_tms 가 기술머신 호환에 넣고(알 기술 · 최신작 가르침), 없는 것은 여기서
떠올리기로 넣는다. **알 기술은 진화 전 단계의 것도 물려받는다** - SV 자료는 대개 진화형에도 알 기술을 적지만,
아기 포켓몬이 있는 계열은 아기에게만 적는다 (피츄 7개 · 피카츄 0개). '최신작' 은 tools/learn_ref.py 가 고른다.
**build_tms.py 를 먼저 돌린다** (기술머신이 있는지를 server/data/tms.json 에서 본다). **그리고 다시 한 번
돌린다** - 떠올리기 기술은 그 기술머신으로도 배운다 (2.0, build_tms 의 '떠올리기 기술').

**메가진화하는 종은 레전즈 Z-A 의 학습표도 (1.13.4, 사용자 결정 '메가 있는 종만'):** 2026-10-20 게시판 #291 (니뉴) -
메가픽시는 Z-A 에서 나온 메가라 Z-A 학습표(픽시 Lv.52 에어슬래시)를 바탕으로 짜였는데, 이 게임은 SV 학습표만 따라서
못 배웠다. 메가진화가 있는 종(도감의 megas 의 megaOf, 옛 메가 포함 87종)에 한해 Z-A 학습표의 기술을 떠올리기로 넣는다
(레벨과 상관없이). 다른 종까지 넓히면 기술 폭이 너무 바뀐다.
  · **Z-A 에서 레벨업으로 배우는 기술은 기술머신이 있어도 넣는다** (1.13.4 고침, 같은 날 니뉴 대댓글 '매지컬리프 ·
    매지컬플레임 · 이판사판태클을 못 배운다'). 처음에는 그 종이 이 게임의 기술머신으로 배울 수 있으면 뺐는데, 기술머신은
    잡아야 나오니 없으면 못 배운다 - 본가 Z-A 에서는 기술머신 없이 레벨업으로 배운다. 이 게임 레벨업(진화 전 단계 포함)
    으로 Z-A 와 같거나 더 이른 레벨에 배우는 것만 뺀다 (더 늦게 배우면 넣는다 - 앱솔 칼춤 Z-A Lv.20 · 여기 Lv.45).
  · Z-A 에서 기술머신으로만 배우는 기술은 이 게임에서 그 종이 그 기술머신으로도 레벨업으로도 못 배울 때만 넣는다.
    이때 'Z-A 전용 기술머신'(tms.json 의 zaOnly, 1.13.4 에 Z-A 학습표로 호환을 채운 18개)은 기술머신으로 치지 않는다 -
    채우기 전에 떠올리기로 넣어 준 101개를 기술머신이 생겼다고 도로 빼지 않는다 (기술머신은 잡아야 나온다).
자료는 쇼다운의 Z-A 학습표 (없으면 멈춘다):
  tools/_cache/showdown_gen9legends_learnsets.ts
  https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/mods/gen9legends/learnsets.ts

레벨업 표(moves)에는 넣지 않는다 - 거기 넣으면 새로 생기는 포켓몬(알 · 레이드 · 악당 전설)의 처음 기술이
바뀐다. 기술 떠올리기(server/app/tm_routes.rememberable)만 이 칸을 본다.

**build_pokedex.py 를 다시 돌리면 이것도 다시 돌려야 한다** (add_megas · add_forms 와 같다).
"""
import csv
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import learn_ref                                            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "tools", "_cache")
DEX = os.path.join(ROOT, "server", "data", "pokedex.json")
TMS = os.path.join(ROOT, "server", "data", "tms.json")
ZA_LEARNSETS = learn_ref.ZA_LEARNSETS
SV = "scarlet-violet"
EGG = "2"           # pokemon_move_methods: egg


def _rows(name):
    with io.open(os.path.join(CACHE, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


# {종 내부 이름: [기술, ...]} - 위의 '손으로 넣는 것'.
MANUAL = {
    # 볼트태클: 본가에서는 전기구슬을 지닌 피카츄 · 라이츄로 교배한 피츄만 배우는 특별한 알 기술이다.
    # 교배도 볼트태클 기술머신도 없는 이 게임에서는 어디서도 못 배워서, 상점에서 파는 피카츄Z 를 쓸 수 없었다.
    "PIKACHU": ["VOLTTACKLE"],
    # 본가 최신작(SV)에서는 빠졌지만 옛 작품에서 그 계열만 쓰던 전용기 (1.13.3, 사용자 결정). 기술은 게임에 있다.
    "ETERNATUS": ["ETERNABEAM"],            # 무한다이빔 - 소드실드 Lv.88 (SV 는 그 자리에 역린)
    "VESPIQUEN": ["HEALORDER"],             # 회복지령 - 7세대까지 Lv.29
    "EXEGGCUTE": ["BARRAGE"],               # 구슬던지기 - 7세대까지
    "EXEGGUTOR": ["BARRAGE", "GROWTH"],     # 성장 - SV Lv.1 (쇼다운 9L1). PokeAPI SV 자료에 빠져 있다 (#291 대조)
    "CUBONE": ["BONECLUB"],                 # 뼈다귀치기 - 6세대까지
    "MAROWAK": ["BONECLUB"],
    # 파멸의빛 - 메가플라엣테의 전용기 (1.13.4, 게시판 #312 윤종녕 · 사용자 결정). 본가(Z-A)에서는 '영원의 꽃 플라엣테' 만
    # 메가진화하고 Lv.50 에 배우는데, 이 게임은 한 종에 모습이 하나라 그 플라엣테를 플라엣테에 합쳐 두었다 - 그래서
    # 플라엣테가 메가진화는 하는데 파멸의빛은 어디서도 못 배웠다.
    "FLOETTE": ["LIGHTOFRUIN"],
}


def key(ident):
    return re.sub(r"[^A-Za-z0-9]", "", ident).upper()


def za_learnsets(path=ZA_LEARNSETS):
    """쇼다운 Z-A 학습표 -> {종 열쇠(CLEFABLE): {기술 열쇠: 레벨업 레벨(가장 이른 것) 또는 None(기술머신만)}}."""
    out = {}
    for sp, mvs in learn_ref.za_codes(path).items():
        out[sp] = {}
        for mv, codes in mvs.items():
            lv = [int(c[2:]) for c in codes if re.match(r"^9L\d+$", c)]
            out[sp][mv] = min(lv) if lv else None
    return out


def build(dex):
    """{종 내부 이름: [기술 열쇠, ...]}"""
    vg = next((r["id"] for r in _rows("version_groups.csv") if r["identifier"] == SV), "25")
    moves = dict((r["id"], key(r["identifier"])) for r in _rows("moves.csv"))
    by_num = dict((s["num"], s) for s in dex["species"])
    out = {}
    for r in _rows("pokemon_moves.csv"):
        if r["version_group_id"] != vg or r["pokemon_move_method_id"] != EGG:
            continue
        sp = by_num.get(int(r["pokemon_id"]))          # 기본 모습(번호 = 도감 번호)만
        if not sp or sp.get("egg") != ["no-eggs"] or sp.get("isBaby"):
            continue
        mv = moves.get(r["move_id"])
        if not mv or mv not in dex["moves"]:
            continue
        lst = out.setdefault(sp["internal"], [])
        if mv not in lst:
            lst.append(mv)
    # ---- 1.13.3: 본가 최신작의 알 기술(진화 전 단계 것 포함) · 가르침 기술 가운데 기술머신이 없는 것 ----
    with io.open(TMS, encoding="utf-8") as f:
        tm_moves = set(t["move"] for t in json.load(f)["tms"].values())
    ref = learn_ref.reference(_rows("pokemon_moves.csv"), _rows("version_groups.csv"))

    def ref_moves(num, how):
        return set(moves.get(str(mid)) for mid, hs in (ref.get(num) or {}).items() if how in hs)

    for sp in dex["species"]:
        want, cur, seen = ref_moves(sp["num"], learn_ref.TUTOR), sp, set()
        while cur and cur["num"] not in seen:          # 알 기술은 진화 전 단계 것도 물려받는다
            seen.add(cur["num"])
            want |= ref_moves(cur["num"], learn_ref.EGG)
            p = cur.get("prevo")
            cur = by_num.get(p) if isinstance(p, int) else None
        level = set(mv for _lv, mv in sp.get("moves") or [])
        for mv in sorted(m for m in want if m):
            if mv not in dex["moves"] or mv in tm_moves or mv in level:
                continue
            lst = out.setdefault(sp["internal"], [])
            if mv not in lst:
                lst.append(mv)
    # ---- 1.13.4: 메가진화하는 종은 레전즈 Z-A 학습표에서 배울 길이 없는 것 ----
    za = za_learnsets()
    learn_tm = json.load(io.open(TMS, encoding="utf-8"))
    tm_no = dict((no, t["move"]) for no, t in learn_tm["tms"].items())
    by_name = dict((s["internal"], s) for s in dex["species"])
    for name in sorted(set(m["megaOf"] for m in dex.get("megas") or [] if m.get("megaOf"))):
        sp = by_name.get(name)
        if sp is None or name not in za:
            continue
        level, cur, seen = {}, sp, set()
        while cur and cur["num"] not in seen:           # 레벨업 (진화 전 단계 것도 떠올리기에 나온다)
            seen.add(cur["num"])
            for lv, mv in cur.get("moves") or []:
                level[mv] = min(level.get(mv, lv), lv)
            p = cur.get("prevo")
            cur = by_num.get(p) if isinstance(p, int) else None
        za_only = set(learn_tm.get("zaOnly") or [])
        # 떠올리기 기술이라서 build_tms 가 넣은 기술머신 줄(fromRemind, 2.0)도 치지 않는다 - 치면 서로 지운다.
        mine = set((learn_tm.get("fromRemind") or {}).get(str(sp["num"])) or [])
        tm = set(tm_no.get(str(no)) for no in learn_tm["learn"].get(str(sp["num"]), [])
                 if no not in za_only and no not in mine)
        lst = out.setdefault(name, [])
        for mv, zlv in sorted(za[name].items()):
            if mv not in dex["moves"] or mv in lst:
                continue
            if zlv is not None:                         # Z-A 레벨업: 여기서 그 레벨까지 레벨업으로 못 배우면 넣는다
                if mv in level and level[mv] <= max(zlv, 1):
                    continue
            elif mv in level or mv in tm:               # Z-A 기술머신만: 여기서 배울 길이 없을 때만
                continue
            lst.append(mv)
    names = set(s["internal"] for s in dex["species"])
    for sp, mvs in MANUAL.items():
        if sp not in names:
            continue
        lst = out.setdefault(sp, [])
        for mv in mvs:
            if mv in dex["moves"] and mv not in lst:
                lst.append(mv)
    return dict((k, sorted(v)) for k, v in out.items())


def apply(dex, table):
    changed = False
    for sp in dex["species"]:
        want = table.get(sp["internal"])
        if want and sp.get("remind") != want:
            sp["remind"] = want
            changed = True
        elif not want and "remind" in sp:
            del sp["remind"]
            changed = True
    return changed


def main():
    check = "--check" in sys.argv
    with io.open(DEX, encoding="utf-8") as f:
        dex = json.load(f)
    table = build(dex)
    changed = apply(dex, table)
    print("떠올리기 전용 기술: %d종 %d개" % (len(table), sum(len(v) for v in table.values())))
    for k, v in sorted(table.items()):
        print("  %-12s %s" % (k, ", ".join(v)))
    if check:
        print("바뀔 것이 있다" if changed else "그대로다")
        return 1 if changed else 0
    with io.open(DEX, "w", encoding="utf-8") as f:
        json.dump(dex, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("썼다: %s" % os.path.relpath(DEX, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
