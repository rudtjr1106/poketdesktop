# -*- coding: utf-8 -*-
"""기술 학습 전수 검사 - 본가 최신작 학습표(PokeAPI 로컬 캐시) vs 이 게임에서 배울 수 있는 길 (1.13.3).

    python tools/learn_audit.py          # 요약을 찍고, 못 배우는 줄 전부를 tools/_cache/learn_audit_missing.tsv 로

2026-10-20 사용자 요청('기술 배우는 게 구현 안 된 것들 전수 검사')으로 만들었다. 데이터(build_tms · add_reminder ·
build_pokedex)를 다시 만들면 이것으로 구멍이 없는지 본다. 캐시(tools/_cache)가 git 에 없어서 CI 에서는 못 돌린다 -
CI 는 server/test_move_needs.py 가 대표 사례를 본다.

이 게임의 길: 레벨업 표(moves) · 떠올리기 전용(remind) · 기술머신(tms.json learn, 종 번호) · 진화 전 단계 ·
폼의 자기 표 · 폼 전용 기술(formMoves.sig = 떠올리기 무료).
본가 기준: tools/learn_ref.py (그 종이 나온 가장 최근 본편, 외전 · 일본판 재발매 제외).

첫 결과 (10/20, 고치기 전): 못 배우는 (종, 기술) 1,975 = 레벨업 0 · 기술머신 1 · 가르침 355 · 알 1,619,
옛 전용기 5. -> 가르침은 최신작 것만 기술머신/떠올리기로, 알 기술은 떠올리기로, 옛 전용기 4개는 떠올리기로
(사용자 결정). 남은 것: 테오키스 스피드폼의 망각술 (폼만 기술머신으로 배운다 - 기술머신은 원래 종 번호로 본다).
"""
import collections
import csv
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "tools", "_cache")
OUT = os.path.join(ROOT, "tools", "_cache")
raw = json.load(open(os.path.join(ROOT, "server/data/pokedex.json"), encoding="utf-8"))
tmd = json.load(open(os.path.join(ROOT, "server/data/tms.json"), encoding="utf-8"))
sys.path.insert(0, ROOT)
from common import zmoves as ZM    # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "tools"))
import learn_ref                    # noqa: E402


def rows(name):
    with io.open(os.path.join(CACHE, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def key(ident):
    return re.sub(r"[^A-Za-z0-9]", "", ident).upper()


METHOD = {1: "레벨업", 2: "알", 3: "가르치기", 4: "기술머신", 6: "특별(전기구슬 알)", 10: "폼체인지", 11: "지가르데큐브"}
move_key = dict((int(r["id"]), key(r["identifier"])) for r in rows("moves.csv"))
game_moves = raw["moves"]

# ---- 본가 학습표: tools/learn_ref (가장 최근 본편)
_ref = learn_ref.reference(rows("pokemon_moves.csv"), rows("version_groups.csv"))
_ref_vg = learn_ref.ref_vg(rows("pokemon_moves.csv"), rows("version_groups.csv"))
learn_vg = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(set)))
for r in rows("pokemon_moves.csv"):                 # 전용기 판정은 모든 본편을 본다
    vg = int(r["version_group_id"])
    if vg in learn_ref.SIDE_VG:
        continue
    learn_vg[int(r["pokemon_id"])][vg][move_key.get(int(r["move_id"]), "?")].add(int(r["pokemon_move_method_id"]))


def mainline(pid):
    """(기준 판, {기술: 방법들})"""
    if pid not in _ref:
        return None, {}
    vg = _ref_vg[pid]
    return ("SV" if vg == 25 else str(vg)), dict((move_key.get(mid, "?"), set(hs)) for mid, hs in _ref[pid].items())


# ---- 이 게임에서 배울 수 있는 것
by_int = dict((s["internal"], s) for s in raw["species"])
by_num = dict((s["num"], s) for s in raw["species"])
tm_move = dict((int(no), t["move"]) for no, t in tmd["tms"].items())


def tm_of(num):
    return set(tm_move[int(n)] for n in tmd["learn"].get(str(num), []) if int(n) in tm_move)


def own(s):
    return set(mv for _lv, mv in s.get("moves") or []) | set(s.get("remind") or []) | tm_of(s["num"])


def game_learn(s, form=None):
    got, cur, seen = set(), s, set()
    while cur and cur["internal"] not in seen:
        seen.add(cur["internal"])
        got |= own(cur)
        p = cur.get("prevo")
        cur = by_num.get(p) if isinstance(p, int) else by_int.get(p)
    if form:
        got |= set(mv for _lv, mv in form.get("moves") or [])
        sig = (form.get("formMoves") or {}).get("sig")
        if sig:
            got.add(sig)
    return got


PRI = [1, 4, 3, 10, 6, 11, 2]
missing = []          # (종 kr, internal, 기술, 방법들, 기준판)
no_tm = []
not_in_game = collections.Counter()
targets = [(s, None, s["num"]) for s in raw["species"]]
targets += [(by_int[f["formOf"]], f, f["num"]) for f in raw["forms"] if f.get("formKind") in ("use", "held", "move", "evo")]
for s, form, pid in targets:
    ref, ml = mainline(pid)
    if not ml:
        continue
    have = game_learn(s, form)
    name = s["kr"] + (" (%s)" % form.get("formKr") if form else "")
    if not form and any(4 in ms for ms in ml.values()) and not tm_of(s["num"]):
        no_tm.append(name)
    for mv, ms in ml.items():
        if mv not in game_moves:
            not_in_game[mv] += 1
            continue
        if mv in have:
            continue
        missing.append((name, (form or s)["internal"], mv, sorted(ms, key=PRI.index), ref))

# ---- 요약
print("== 본가 기준표에는 있는데 이 게임에서 어느 길로도 못 배우는 (종, 기술): %d" % len(missing))
first = collections.Counter(METHOD.get(m[3][0], m[3][0]) for m in missing)
for k, n in first.most_common():
    print("  %-14s %5d" % (k, n))
by_method = collections.defaultdict(list)
for m in missing:
    by_method[m[3][0]].append(m)
for meth in (1, 4, 3, 10, 6, 11):
    lst = by_method.get(meth) or []
    if not lst:
        continue
    print("\n== [%s] %d줄 · 기술 %d가지 · 종 %d" % (METHOD[meth], len(lst), len(set(m[2] for m in lst)), len(set(m[1] for m in lst))))
    cnt = collections.Counter(m[2] for m in lst)
    for mv, n in cnt.most_common(25):
        who = [m[0] for m in lst if m[2] == mv][:6]
        print("  %-16s %-10s %3d종  예: %s" % (mv, game_moves[mv].get("kr", ""), n, ", ".join(who)))

# ---- 전용기: 본가 전 세대에서 한 진화 계열만 배우는 기술
family = {}
for s in raw["species"]:
    cur, seen = s, set()
    while cur and cur["internal"] not in seen:
        seen.add(cur["internal"])
        p = cur.get("prevo")
        nxt = by_num.get(p) if isinstance(p, int) else by_int.get(p)
        if not nxt:
            break
        cur = nxt
    family[s["num"]] = cur["num"]
pid_species = dict((int(r["id"]), int(r["species_id"])) for r in rows("pokemon.csv"))
move_fams = collections.defaultdict(set)
for pid, vgs in learn_vg.items():
    sid = pid_species.get(pid)
    if sid not in family:
        continue
    for v, mvs in vgs.items():
        for mv in mvs:
            move_fams[mv].add(family[sid])
sig_missing = []
for mv, fams in move_fams.items():
    if len(fams) != 1 or mv not in game_moves:
        continue
    root = next(iter(fams))
    members = [s for s in raw["species"] if family[s["num"]] == root]
    if not any(mv in game_learn(s) for s in members):
        sig_missing.append((mv, game_moves[mv].get("kr"), [s["kr"] for s in members]))
print("\n== 전용기(본가 전 세대에서 한 진화 계열만 배운다)인데 그 계열이 이 게임에서 못 배운다: %d" % len(sig_missing))
for mv, kr, mem in sorted(sig_missing):
    print("  %-16s %-10s %s" % (mv, kr, "/".join(mem)))

# ---- 게임에 있는데 아무도 못 배우는 기술
all_have = set()
for s in raw["species"]:
    all_have |= game_learn(s)
for f in raw["forms"]:
    all_have |= set(mv for _lv, mv in f.get("moves") or []) | set(filter(None, [(f.get("formMoves") or {}).get("sig")]))
zbases = set(c["base"] for c in ZM.EXCLUSIVE.values())
orphans = sorted(m for m in game_moves if m not in all_have)
print("\n== 게임 기술 %d개 가운데 어느 종도 배울 수 없는 것: %d" % (len(game_moves), len(orphans)))
print("  " + ", ".join("%s(%s)" % (m, game_moves[m].get("kr")) for m in orphans[:80]))
print("\n== 기술머신을 하나도 못 배우는 종 (본가는 배운다): %d  %s" % (len(no_tm), ", ".join(no_tm[:30])))
print("\n== 본가 학습표에는 있지만 게임 기술 목록에 아예 없는 기술: %d가지 (상위) %s"
      % (len(not_in_game), ", ".join("%s×%d" % kv for kv in not_in_game.most_common(15))))

with io.open(os.path.join(OUT, "learn_audit_missing.tsv"), "w", encoding="utf-8") as f:
    f.write("종\t내부\t기술\t한글\t본가 방법\t기준판\n")
    for name, internal, mv, ms, ref in sorted(missing, key=lambda m: (PRI.index(m[3][0]), m[2], m[1])):
        f.write("%s\t%s\t%s\t%s\t%s\t%s\n" % (name, internal, mv, game_moves[mv].get("kr", ""),
                                              "/".join(METHOD.get(x, str(x)) for x in ms), ref))
print("\n(자세한 목록: %s)" % os.path.join(OUT, "learn_audit_missing.tsv"))

# ======================== 2차: 걸러 보기
print("\n\n######## 2차")
default_pid = dict((int(r["id"]), int(r["is_default"])) for r in rows("pokemon.csv"))
game_form_pids = set(f["num"] for f in raw["forms"])
fams2 = collections.defaultdict(set)
for pid, vgs in learn_vg.items():
    sid = pid_species.get(pid)
    if sid not in family:
        continue
    if not default_pid.get(pid) and pid not in game_form_pids:
        continue                    # 이 게임에 없는 폼 (가라르 · 히스이 · 알로라 · 합체 …) 의 기술은 뺀다
    for v, mvs in vgs.items():
        for mv in mvs:
            fams2[mv].add(family[sid])


def fam_learn(root):
    got = set()
    for s in raw["species"]:
        if family[s["num"]] == root:
            got |= game_learn(s)
            for f in raw["forms"]:
                if f["formOf"] == s["internal"]:
                    got |= game_learn(s, f)
    return got


sig2 = []
for mv, fams in fams2.items():
    if len(fams) == 1 and mv in game_moves:
        root = next(iter(fams))
        if mv not in fam_learn(root):
            sig2.append((mv, game_moves[mv].get("kr"), "/".join(s["kr"] for s in raw["species"] if family[s["num"]] == root)))
print("== 전용기(이 게임에 있는 모습 기준)인데 못 배운다: %d" % len(sig2))
for row in sorted(sig2):
    print("  %-16s %-10s %s" % row)

zkeys = set()
for c in ZM.EXCLUSIVE.values():
    zkeys.add(key(c.get("z") or c.get("move") or ""))
real_orphans = [m for m in orphans if not (game_moves[m].get("z") or game_moves[m].get("isZ") or m.endswith("PHYSICAL")
                                             or m.endswith("SPECIAL"))]
print("\n== 아무도 못 배우는 기술에서 Z기술(…PHYSICAL/SPECIAL) 을 뺀 것: %d" % len(real_orphans))
print("  " + ", ".join("%s(%s)" % (m, game_moves[m].get("kr")) for m in real_orphans))

tm_moves = set(tm_move.values())
tut = by_method.get(3) or []
with_tm = [m for m in tut if m[2] in tm_moves]
print("\n== [가르치기] 355줄 가운데 그 기술의 기술머신이 이 게임에 있는 줄: %d (기술 %d가지) · 없는 줄: %d (기술 %d가지)"
      % (len(with_tm), len(set(m[2] for m in with_tm)), len(tut) - len(with_tm), len(set(m[2] for m in tut if m[2] not in tm_moves))))
print("  기술머신 없는 가르치기 기술:", ", ".join(sorted(set("%s(%s)" % (m[2], game_moves[m[2]].get("kr")) for m in tut if m[2] not in tm_moves))))
print("  기준판 분포:", collections.Counter(m[4] for m in tut))
