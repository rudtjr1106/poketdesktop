# -*- coding: utf-8 -*-
"""지닌 도구 검사 — 엔진만. 서버 없이 돈다.

    python common/test_held.py

세 가지를 본다.

1. **도구가 없으면 로그가 한 글자도 안 달라진다.** 도구를 넣기 전 엔진으로
   뜬 요약값과 같아야 한다. PvP 는 저장된 로그를 재생하는 구조라 옛 판이
   달라지면 안 되고, 도구 없는 사람이 대다수다.
2. 카탈로그(items.json)와 held.KR 이 서로 맞는다. 한쪽에만 있는 도구는
   '지녔는데 아무 일도 안 하는' 물건이 된다.
3. 도구 하나하나가 정말로 뭔가 한다. 시드를 박아 두고 있는/없는 판을
   비교하거나, 훅을 직접 부른다.

상대는 **한 방에 안 죽는 것**으로 고른다. 처음에는 Lv.45 잠만보를 상대로
세웠는데 Lv.40 스타팅을 첫 턴에 보내 버려서, 턴 끝 회복도 열매 발동도
볼 기회가 없었다. 검사가 빨갛게 되면 먼저 판이 몇 턴 갔는지 보라.
"""
import hashlib
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import battle as B                              # noqa: E402
from common import held as H                                # noqa: E402
from common import party_battle as PB                       # noqa: E402
from common import pokelogic as P                           # noqa: E402

OK = FAIL = 0

# 도구 코드가 판에 손대지 않는지 보는 값. 같은 파티·같은 시드다.
#
# 처음 값은 도구를 넣기 **전** 엔진(1.0.20)으로 떴다
#   c59229ab... / 67bf05ec...
# 1.3.2 뒤에 **원작 공식 기술과 씨뿌리기**를 넣으면서 판이 달라져 다시 떴다 (ffadc218 / 16b4532b).
# 이 파티의 이상해씨가 씨뿌리기를 든다 - 예전에는 턴만 버리던 기술이다. movecalc 를 옛 동작
# (위력 0 이면 안 때린다)으로 되돌리고 씨뿌리기를 빼면 옛 값 둘이 그대로 나오는 것을 확인했다.
#
# 그 뒤 **변화기 144개**(statusmoves)를 넣으면서 또 달라졌다. 옛 엔진(git HEAD)과 같은 판을
# 나란히 돌려 처음 어긋나는 곳을 보니 파티전 13판·야생전 8판 전부가 새로 동작하는 기술에서
# 갈라졌다: 캐이시의 순간이동(유저 배틀에서 교체할 동료가 없으면 실패 / 야생은 도망),
# 식스테일의 이상한빛(AI 가 이제 값을 매겨 고른다), 롱스톤의 조이기(붙잡기).
#
# 1.4.3 뒤에 **급소 확률을 원작 표로** 고치면서 또 달라졌다 (dc9bdeb5 / eedbdbe3 에서).
# 예전 식은 1단계 1/12·2단계 1/6·3단계 이상 1/3 이었고 원작은 1/8·1/2·반드시다
# (battle.CRIT_BY_STAGE). 이 파티의 파이리가 급소율이 높은 베어가르기를 든다. 같은 때
# 도감에 8·9세대 공격기 효과를 채웠는데, 그것만 넣었을 때는 옛 값이 그대로였고,
# CRIT_BY_STAGE 를 옛 값 (24, 12, 6, 3) 으로 되돌리면 옛 값 둘이 그대로 나오는 것을 확인했다.
#
# 1.8.1 에서 **1세대 151종의 학습표를 적청에서 스칼렛·바이올렛으로** 바꾸면서 또 달라졌다
# (05ceafd2 / 2d085a96 에서). 이 파티가 전부 1세대라 들고 나오는 기술이 통째로 바뀐다 -
# 엔진이 아니라 자료가 바뀐 것이다. 같은 때 고친 치유파동·검은오물은 이 판들에 안 나온다:
# 옛 엔진(git HEAD)에 새 도감만 끼워 돌려도 아래 두 값이 그대로 나오는 것을 확인했다.
#
# 그 뒤 **레전드 아르세우스 표를 쓰던 53종을 본편 표와 합치면서** 한 번 더 달라졌다
# (df4c35fb / e270fbf7 에서). 상대 파티의 롱스톤(95)이 그 53종이라 들고 나오는 기술이
# 바뀐다. 이때는 엔진을 한 줄도 안 고쳤다 (도감과 tools/build_pokedex.py 만 바뀜).
#
# 1.9.2 에서 **기술을 본가 규칙에 맞추면서** 파티전 값만 달라졌다 (9b26cd0a 에서. 1:1 값은 그대로).
# 옛 엔진(git HEAD)과 같은 30판을 나란히 돌려 처음 어긋나는 곳을 보니 20판이 달라졌고 까닭은 둘뿐이다:
#   · 17판 - 상대 꼬마돌의 **자폭**. 예전에는 쓰고도 안 쓰러지는 위력 200 짜리라 AI 가 매번 골랐다.
#     이제 쓰면 쓰러지므로(attackfx.SELF_KO) 그 자리에서 록블라스트를 고른다.
#   · 3판 - 고라파덕의 **급소**. 예전에는 급소가 맞는 쪽의 방어 '하락' 을 없던 일로 했다
#     (꼬리흔들기로 깎아 둔 방어가 급소에서만 되돌아왔다). 원작은 방어 '상승' 만 무시한다.
#
# 1.13.3 에서 **발버둥의 이름만** '몸부림' -> '발버둥'(공식 이름)으로 바꿔 파티전 값이 달라졌다 (판에 발버둥이
# 나온다). 이름을 '몸부림' 으로 되돌려 재면 옛 값(69b68798…)과 똑같다 - 엔진은 그대로다.
# 1.13.3 에서 **쓰러뜨린 턴에도 턴 끝이 오게** 하면서 파티전 값이 또 달라졌다 (#295 - 상대를 쓰러뜨린 턴의 독 ·
# 화상 데미지 · 가속이 이제 들어간다). party_battle._still_on 을 끄고 재면 바로 위 값(5463…)과 똑같다.
# 11/19 **조이기류가 본가처럼 4~5번 깎게**(held.bind_turns 5~6 · 끈기갈고리손톱 8) 고치면서 두 값이 다 달라졌다
# (게시판 #664 를 보다 찾음 - 전에는 3~4번). 상대 파티의 롱스톤이 조이기를 든다. bind_turns 만 옛것(4~5 · 7)으로
# 되돌려 재면 바로 위 값 둘(ecf38229… / a702a422…)이 그대로 나온다. 같은 때 고친 씨뿌리기(#657 - 심은 쪽이
# 쓰러졌으면 안 빼앗는다)는 이 60판 어디에도 안 걸린다 (그것만 옛것으로 되돌려도 아래 값 그대로).
# 같은 날 **랭크에서 묶은 쪽이 쓰러지면 묶기가 풀리게**(party_battle._advance 가 SM.on_leave) 고치면서 파티전 값만 또
# 달라졌다 (c3287ad8… -> 아래). 롱스톤이 조여 둔 채 쓰러지면 전에는 다음에 나온 상대까지 계속 깎였다. _advance 의
# on_leave 만 끄고 재면 c3287ad8… 가 그대로 나온다. 묶기를 주 효과로 바꾼 것(#664 - 인분 · 은밀망토 · 우격다짐)은
# 특성이 꺼져 있고 지닌 도구가 없는 이 판들에는 안 걸린다.
PARTY_DIGEST = "bdfc142d3c78a0c2fdfd389b74da92bffb761866694bf1fc9f6c3a69834b2b2a"
SOLO_DIGEST = "28fdb6f16d8b6d7ef861dd11ce76fe1e6020c6575682ab30b84a5627b90772b4"


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def load_dex():
    p = os.path.join(HERE, "..", "server", "data", "pokedex.json")
    with open(p, encoding="utf-8") as f:
        return P.Pokedex(json.load(f))


def party(dex, seed, nums, lv):
    rng = random.Random(seed)
    return [P.make_pokemon(dex.get(n), lv, rng) for n in nums]


def solo(dex, a, b, seed, ai="trainer", turns=None):
    """1:1 한 판. 이벤트 목록과 배틀을 돌려준다."""
    rng = random.Random(seed)
    me, foe = B.Fighter(dex, a), B.Fighter(dex, b)
    bt = B.Battle(dex, me, foe, rng, ai=ai)
    evs = []
    n = 0
    while not bt.over and (turns is None or n < turns):
        evs.extend(bt.take_turn(bt.choose_mine()))
        n += 1
    return evs, bt


def texts(evs):
    return " | ".join(e.get("text", "") for e in evs if e.get("text"))


def with_item(mon, item):
    m = dict(mon)
    m["held"] = item
    return m


def pair(dex, a, b, seed=1):
    """훅을 직접 부를 때 쓰는 배틀. a 가 me."""
    me, foe = B.Fighter(dex, a), B.Fighter(dex, b)
    return B.Battle(dex, me, foe, random.Random(seed)), me, foe


# ---------------------------------------------------------------- 1. 회귀
def t_도구_없으면_그대로(dex):
    print("-- 도구 없는 판은 예전과 같다")
    A = party(dex, 101, [4, 25, 133, 7, 1, 52], 32)
    Bm = party(dex, 202, [52, 54, 95, 37, 63, 74], 30)
    # **특성은 끄고 잰다.** PvP 에 특성을 켠 뒤로는(1.2.x) 판이 달라지는 게 맞다.
    # 이 검사가 보려는 것은 '도구가 없으면 도구 코드가 판에 손대지 않는가' 다.
    h = hashlib.sha256()
    old = PB.ABILITIES
    try:
        PB.ABILITIES = False
        for s in range(1, 31):
            out = PB.simulate(dex, A, Bm, seed=s)
            h.update(json.dumps(out["events"], sort_keys=True,
                                ensure_ascii=False).encode())
    finally:
        PB.ABILITIES = old
    chk("파티전 30판 요약값이 그대로다", h.hexdigest() == PARTY_DIGEST,
        h.hexdigest())
    h2 = hashlib.sha256()
    for s in range(1, 31):
        rng = random.Random(1000 + s)
        me, foe = B.Fighter(dex, A[s % 6]), B.Fighter(dex, Bm[(s * 5) % 6])
        bt = B.Battle(dex, me, foe, rng, ai="wild")
        evs = []
        while not bt.over:
            evs.extend(bt.take_turn(bt.choose_mine()))
        h2.update(json.dumps(evs, sort_keys=True, ensure_ascii=False).encode())
    chk("야생전 30판 요약값이 그대로다", h2.hexdigest() == SOLO_DIGEST,
        h2.hexdigest())
    f = B.Fighter(dex, A[0])
    chk("held 가 None", f.held is None and f.held_state() is None)
    chk("모르는 값은 None 으로", H.normalize("NOTANITEM") is None
        and H.normalize("") is None)
    chk("소문자·하이픈도 알아듣는다", H.normalize("quick-claw") == "QUICKCLAW")


# ---------------------------------------------------------------- 2. 카탈로그
def t_카탈로그와_맞는다():
    print("-- items.json 과 held.KR")
    p = os.path.join(HERE, "..", "server", "data", "items.json")
    with open(p, encoding="utf-8") as f:
        it = json.load(f)["items"]
    # 테라피스(2.5.1)는 '지닌 도구' 칸이지만 배틀 효과가 아니라 테라스탈의 열쇠다 - 메가스톤 · Z크리스탈처럼 KR 밖
    held_cat = set(k for k, v in it.items() if v["cat"] == "held" and not v.get("teraType"))
    chk("held 분류 도구가 전부 held.KR 에 있다 (효과 없는 도구 금지 - 테라피스는 빼고)",
        not (held_cat - set(H.KR)), sorted(held_cat - set(H.KR)))
    shards = set(k for k, v in it.items() if v.get("teraType"))
    chk("테라피스 18종은 지닐 수 있고 · 종류순 묶음은 '테라피스'",
        len(shards) == 18 and all(H.normalize(k) == k and H.group(k) == "tera" for k in shards), sorted(shards))
    chk("held.KR 의 도구가 전부 카탈로그에 있다", not (set(H.KR) - set(it)),
        sorted(set(H.KR) - set(it)))
    bad = [(k, H.KR[k], it[k]["kr"]) for k in H.KR if k in it
           and it[k]["kr"] != H.KR[k]]
    chk("한글 이름이 PokeAPI 와 같다", not bad, bad[:5])
    chk("지닌 도구는 설명이 있다",
        all(it[k].get("desc") for k in held_cat),
        [k for k in held_cat if not it[k].get("desc")][:5])
    both = sorted((set(H.KR) & set(it)) - held_cat)
    # 1.13: 심해의이빨·심해의비늘(진주몽 전용)도 지니는 효과가 생겼다 - 진화 도구로 남는다
    chk("돌이면서 지닐 수 있는 여섯은 돌로 남는다",
        both == ["DEEPSEASCALE", "DEEPSEATOOTH", "KINGSROCK", "METALCOAT", "RAZORCLAW", "RAZORFANG"], both)
    chk("도구 종류가 233 이다 (1.13 에 112 종을 더했다)", len(H.KR) == 233, len(H.KR))


# ---------------------------------------------------------------- 3. 효과
def t_효과(dex):
    print("-- 도구가 실제로 뭔가 한다")
    rng = random.Random(7)
    pika = P.make_pokemon(dex.get(25), 40, rng)
    char = P.make_pokemon(dex.get(4), 40, rng)
    wall = P.make_pokemon(dex.get(95), 40, rng)       # 오닉스: 단단하고 선공기 없음
    bag = P.make_pokemon(dex.get(143), 30, rng)       # 잠만보 Lv.30: 오래 맞아 준다
    tank = P.make_pokemon(dex.get(143), 45, rng)      # 잠만보 Lv.45: 오래 산다
    # **기술은 여기서 못 박는다.** 아래 판들은 '이 기술들로 몇 턴이 간다' 를 전제로
    # 시드까지 골라 둔 것이다. 도감의 학습표를 따라가게 두면 표가 바뀔 때(1.8.1 에
    # 1세대가 적청 -> 스칼렛·바이올렛) 판이 통째로 달라져 전제가 깨진다.
    for m, moves in ((pika, ["THUNDERWAVE", "QUICKATTACK", "SWIFT", "AGILITY"]),
                     (char, ["LEER", "RAGE", "SLASH", "FLAMETHROWER"]),
                     (wall, ["BIND", "ROCKTHROW", "RAGE", "SLAM"]),
                     (bag, ["AMNESIA", "HEADBUTT", "REST"]),
                     (tank, ["HEADBUTT", "REST", "BODYSLAM", "HARDEN"])):
        m["moves"] = list(moves)

    # 먹다남은음식: 턴 끝에 회복 이벤트가 난다 (잠만보 vs 오닉스는 여러 턴 간다)
    evs, bt = solo(dex, with_item(tank, "LEFTOVERS"), wall, 1, turns=4)
    chk("판이 여러 턴 간다 (검사 전제)", bt.turn_no >= 3, bt.turn_no)
    chk("먹다남은음식이 턴 끝에 회복한다",
        any("먹다남은음식" in e.get("text", "") for e in evs), texts(evs)[:240])
    evs0, _ = solo(dex, tank, wall, 1, turns=4)
    chk("도구가 없으면 그 문구가 없다",
        not any("먹다남은음식" in e.get("text", "") for e in evs0))

    # 선제공격손톱: 느린 잠만보가 오닉스 상대로 여러 판 중 몇 번은 먼저 움직인다
    first = 0
    for s in range(1, 25):
        evs, _ = solo(dex, with_item(tank, "QUICKCLAW"), wall, s, turns=6)
        if any("선제공격손톱" in e.get("text", "") for e in evs):
            first += 1
    chk("선제공격손톱이 발동한다 (24판 중, 턴당 20%%)", 6 <= first <= 24, first)

    # 구애머리띠: 첫 기술만 계속 쓴다 (샌드백 잠만보 Lv.30 상대로 여러 턴).
    # 시드 3 은 급소 확률을 원작대로(베어가르기 1/8) 고친 뒤 두 턴 만에 끝나서
    # '세 번 이상 썼다' 는 전제가 깨졌다. 시드 1 은 네 번 쓰고, 도구가 없으면 같은
    # 판에서 기술을 바꿔 쓴다 - 잠금을 가장 또렷이 보여 준다.
    evs, bt = solo(dex, with_item(char, "CHOICEBAND"), bag, 1, turns=6)
    used = [e["move"] for e in evs if e.get("t") == "move" and e.get("who") == "me"]
    chk("구애머리띠는 처음 쓴 기술만 쓴다", len(set(used)) == 1 and len(used) >= 3,
        used)
    chk("구애 잠금이 기억된다", bt.me.locked is not None, bt.me.locked)
    evs0, _ = solo(dex, char, bag, 1, turns=6)
    used0 = [e["move"] for e in evs0 if e.get("t") == "move" and e.get("who") == "me"]
    chk("(같은 시드에서 도구 없이는 기술을 바꿔 쓴다 - 검사 전제)",
        len(used0) >= 2 and len(set(used0)) >= 2, used0)
    f0 = B.Fighter(dex, char)
    f1 = B.Fighter(dex, with_item(char, "CHOICEBAND"))
    chk("구애머리띠는 공격 1.5배", f1.stat("atk") == int(f0.stat("atk") * 1.5),
        (f0.stat("atk"), f1.stat("atk")))
    chk("구애스카프는 스피드 1.5배",
        B.Fighter(dex, with_item(char, "CHOICESCARF")).stat("spe")
        == int(f0.stat("spe") * 1.5))
    chk("검은철구는 스피드 절반",
        B.Fighter(dex, with_item(char, "IRONBALL")).stat("spe")
        == int(f0.stat("spe") * 0.5))
    chk("사람이 고른 기술도 구애 잠금을 받는다 (야생 배틀)",
        (lambda f: (setattr(f, "locked", f.moves[0]),
                    H.force_move(f, f.moves[-1], [], "me") == f.moves[0])[1])(
            B.Fighter(dex, with_item(char, "CHOICEBAND"))))

    # 기합의띠: 만피에서 한 방에 안 죽는다
    weak = P.make_pokemon(dex.get(10), 3, rng)          # 캐터피 Lv.3
    strong = P.make_pokemon(dex.get(6), 60, rng)        # 리자몽 Lv.60
    evs, bt = solo(dex, with_item(weak, "FOCUSSASH"), strong, 5, turns=1)
    chk("기합의띠로 버틴다", any("기합의띠" in e.get("text", "") for e in evs)
        and bt.me.hp == 1, (bt.me.hp, texts(evs)[:160]))
    evs2, bt2 = solo(dex, weak, strong, 5, turns=1)
    chk("띠가 없으면 쓰러진다", bt2.me.hp == 0, bt2.me.hp)

    # 회복 열매: 훅을 직접 부른다 - 체력이 반 아래로 내려간 순간
    bt, me, _ = pair(dex, with_item(tank, "ORANBERRY"), wall)
    me.hp = me.maxhp // 2 - 1
    ev = []
    H.check_hp(bt, me, "me", ev)
    chk("오랭열매가 반 이하에서 10 회복", me.hp == me.maxhp // 2 - 1 + 10 and me.used,
        (me.hp, me.maxhp, texts(ev)))
    H.check_hp(bt, me, "me", ev)
    chk("열매는 한 판에 한 번", sum(1 for e in ev if e.get("t") == "heal") == 1)
    bt, me, _ = pair(dex, with_item(tank, "SITRUSBERRY"), wall)
    me.hp = me.maxhp // 2
    H.check_hp(bt, me, "me", [])
    chk("자뭉열매는 1/4 회복", me.hp == me.maxhp // 2 + max(1, int(me.maxhp * 0.25)))
    bt, me, _ = pair(dex, with_item(tank, "ORANBERRY"), wall)
    me.hp = me.maxhp - 1
    H.check_hp(bt, me, "me", [])
    chk("체력이 많으면 안 먹는다", not me.used and me.hp == me.maxhp - 1)
    # 위기 열매: 1/4 이하에서 능력이 오른다
    bt, me, _ = pair(dex, with_item(tank, "LIECHIBERRY"), wall)
    me.hp = me.maxhp // 4
    ev = []
    H.check_hp(bt, me, "me", ev)
    chk("치리열매로 공격 +1", me.stages["atk"] == 1 and me.used, (me.stages, texts(ev)))
    # 배틀 안에서도 발동한다. 시나리오에 기대지 않는다: 어느 판이든 체력이
    # 반 아래로 **살아서** 내려간 순간이 있으면 그 뒤에 자뭉열매 회복이
    # 반드시 따라와야 한다.
    mid = P.make_pokemon(dex.get(6), 50, rng)
    crossed = fired = 0
    for s in range(1, 9):
        evs, bt = solo(dex, with_item(tank, "SITRUSBERRY"), mid, s, turns=14)
        half = bt.me.maxhp / 2.0
        idx = next((i for i, e in enumerate(evs)
                    if e.get("t") in ("hit", "chip") and e.get("target", e.get("who")) == "me"
                    and 0 < e.get("hp", 999) <= half), None)
        if idx is None:
            continue
        crossed += 1
        if any("자뭉열매" in e.get("text", "") for e in evs[idx:]):
            fired += 1
    chk("반 아래로 내려간 판이 있다 (검사 전제)", crossed >= 1, crossed)
    chk("그런 판마다 자뭉열매가 발동했다", fired == crossed, (fired, crossed))

    # 타입 강화: 목탄을 든 파이리의 불꽃 기술이 1.2배 (같은 시드, 같은 기술)
    def first_hit(mon):
        evs, _ = solo(dex, mon, bag, 21, turns=1)
        hits = [e for e in evs if e.get("t") == "hit" and e.get("who") == "me"]
        mv = [e for e in evs if e.get("t") == "move" and e.get("who") == "me"]
        return (hits[0]["damage"] if hits else 0), (mv[0]["moveType"] if mv else None)
    d0, t0 = first_hit(char)
    d1, t1 = first_hit(with_item(char, "CHARCOAL"))
    chk("같은 기술을 쓴다 (검사 전제)", t0 == t1 and d0 > 0, (t0, t1, d0))
    if t0 == "FIRE":
        chk("목탄이 불꽃 기술을 1.2배로", abs(d1 / float(d0) - 1.2) < 0.08, (d0, d1))
    else:
        chk("목탄은 불꽃이 아닌 기술에는 그대로", d1 == d0, (t0, d0, d1))
        d2, _ = first_hit(with_item(char, "FLAMEPLATE" if t0 == "FIRE" else "SILKSCARF"))
        chk("타입이 맞는 도구는 1.2배", t0 != "NORMAL" or abs(d2 / float(d0) - 1.2) < 0.08,
            (t0, d0, d2))

    # 생명의구슬: 때리면 내 체력이 깎인다
    evs, bt = solo(dex, with_item(char, "LIFEORB"), bag, 21, turns=1)
    chk("생명의구슬 반동", any("생명의구슬" in e.get("text", "") for e in evs)
        and bt.me.hp < bt.me.maxhp, texts(evs)[:160])

    # 고치는 열매 (파이리는 불꽃이라 화상 면역 - 화상은 피카츄로 본다)
    bt, f, _ = pair(dex, with_item(char, "CHERIBERRY"), pika)
    ev = []
    bt._apply_status(f, "paralysis", ev)
    chk("버치열매가 마비를 고친다", f.status is None and f.used, (f.status, texts(ev)))
    bt, f, _ = pair(dex, with_item(pika, "CHERIBERRY"), char)
    bt._apply_status(f, "burn", [])
    chk("버치열매는 화상은 안 고친다", f.status == "burn" and not f.used, f.status)
    bt, f, _ = pair(dex, with_item(pika, "LUMBERRY"), char)
    bt._apply_status(f, "burn", [])
    chk("리샘열매는 뭐든 고친다", f.status is None and f.used)

    # 하양허브: 능력이 떨어지면 되돌린다
    bt, f, _ = pair(dex, with_item(char, "WHITEHERB"), pika)
    ev = []
    bt._change_stat(f, "atk", -2, ev, "me")
    chk("하양허브가 하락을 되돌린다", f.stages["atk"] == 0 and f.used, (f.stages, texts(ev)))
    # 하양허브 (11/17): 한 기술로 둘 이상 떨어지면 기술이 끝난 뒤 한꺼번에 되돌린다 (본가와 같다). 전에는 첫 하락만.
    r2 = random.Random(1117)                              # 위의 rng 를 안 건드린다 (뒤 검사의 포켓몬이 그대로)
    cloy = P.make_pokemon(dex.get(91), 50, r2)            # 파르셀: 껍질깨기 (방어 · 특방 -1, 공격 · 특공 · 스피드 +2)
    cloy["moves"] = ["SHELLSMASH"]
    bt, f, foe = pair(dex, with_item(cloy, "WHITEHERB"), pika)
    ev = []
    bt._use("me", f, foe, "SHELLSMASH", ev)
    chk("껍질깨기: 방어 · 특방 둘 다 되돌리고 오른 것은 그대로",
        f.stages["def"] == 0 and f.stages["spd"] == 0 and f.stages["atk"] == 2 and f.stages["spe"] == 2 and f.used,
        (f.stages, texts(ev)))
    chk("  되돌린 문구는 한 번, 기술 문구들 뒤에", texts(ev).count("하양허브") == 1
        and [e.get("text", "") for e in ev if e.get("text")][-1].endswith("하양허브로 능력 하락을 되돌렸다!"), texts(ev))
    champ = P.make_pokemon(dex.get(68), 50, r2)           # 괴력몬: 인파이트 (방어 · 특방 -1)
    champ["moves"] = ["CLOSECOMBAT"]
    tough = P.make_pokemon(dex.get(143), 100, r2)         # 잠만보 Lv.100: 맞고도 버틴다
    bt, f, foe = pair(dex, with_item(champ, "WHITEHERB"), tough)
    ev = []
    bt._use("me", f, foe, "CLOSECOMBAT", ev)
    chk("인파이트: 방어 · 특방 둘 다 되돌린다", f.stages["def"] == 0 and f.stages["spd"] == 0 and f.used,
        (f.stages, texts(ev)))
    weak = P.make_pokemon(dex.get(10), 5, r2)             # 캐터피 Lv.5: 한 방에 쓰러진다
    bt, f, foe = pair(dex, with_item(champ, "WHITEHERB"), weak)
    ev = []
    bt._use("me", f, foe, "CLOSECOMBAT", ev)
    chk("  상대를 쓰러뜨려 판이 끝나도 되돌린다 (살아남은 쪽은 다음 라운드로 간다)",
        not foe.alive() and f.stages["def"] == 0 and f.stages["spd"] == 0 and f.used, (foe.hp, f.stages, texts(ev)))
    bt, f, foe = pair(dex, with_item(tough, "WHITEHERB"), champ)
    f.cond["octolock"] = "foe"                            # 문어굳히기: 턴 끝에 방어 · 특방 -1
    ev = []
    bt._end_of_turn(ev)
    chk("문어굳히기(턴 끝): 둘 다 되돌린다", f.stages["def"] == 0 and f.stages["spd"] == 0 and f.used,
        (f.stages, texts(ev)))
    bt, f, foe = pair(dex, with_item(char, "WHITEHERB"), dict(pika, moves=["GROWL"]))
    f.used = True                                          # 이미 쓴 하양허브는 다시 안 돈다
    ev = []
    bt._use("foe", foe, f, "GROWL", ev)
    chk("  이미 쓴 하양허브는 기술 뒤에도 안 돈다", "하양허브" not in texts(ev), texts(ev))

    # 맹독구슬: 턴 끝에 독에 걸린다 (독 타입은 안 걸린다)
    evs, bt = solo(dex, with_item(tank, "TOXICORB"), wall, 1, turns=1)
    chk("맹독구슬로 독에 걸린다", bt.me.status == "poison", (bt.me.status, bt.turn_no))
    weez = P.make_pokemon(dex.get(109), 40, rng)          # 또가스(독)
    evs, bt = solo(dex, with_item(weez, "TOXICORB"), wall, 1, turns=1)
    chk("독 타입은 맹독구슬에 안 걸린다", bt.me.status is None, bt.me.status)
    evs, bt = solo(dex, with_item(tank, "FLAMEORB"), wall, 1, turns=1)
    chk("화염구슬로 화상에 걸린다", bt.me.status == "burn", bt.me.status)

    # 연막탄: 반드시 도망친다
    bt, _, _ = pair(dex, with_item(tank, "SMOKEBALL"), pika)
    chk("연막탄이면 반드시 도망친다", bt.try_run() is True)

    # 반감 열매: 물 기술을 든 파이리가 꼬시개열매로 절반만 맞는다
    water = P.make_pokemon(dex.get(7), 40, rng)           # 꼬부기
    bt, me, foe = pair(dex, water, with_item(char, "PASSHOBERRY"))
    mv = {"type": "WATER", "cat": "special", "power": 40}
    ev = []
    got = H.on_incoming(bt, foe, "foe", mv, 2.0, 40, ev)
    chk("꼬시개열매가 효과 굉장한 물 기술을 반감", got == 20 and foe.used, (got, texts(ev)))
    got2 = H.on_incoming(bt, foe, "foe", mv, 2.0, 40, [])
    chk("한 번 먹으면 끝", got2 == 40)
    bt, me, foe = pair(dex, water, with_item(char, "PASSHOBERRY"))
    got3 = H.on_incoming(bt, foe, "foe", {"type": "WATER", "cat": "special"}, 1.0, 40, [])
    chk("효과가 굉장하지 않으면 안 먹는다", got3 == 40 and not foe.used)

    # 파티전에서도 도구가 산다
    A = [with_item(tank, "LEFTOVERS")] + party(dex, 5, [25, 4], 40)
    Bm = party(dex, 9, [95, 9, 3], 42)
    out = PB.simulate(dex, A, Bm, seed=4)
    chk("파티전 로그에 도구 문구가 나온다",
        any("먹다남은음식" in e.get("text", "") for e in out["events"]),
        texts(out["events"])[:200])
    hits = [e for e in out["events"] if "먹다남은음식" in e.get("text", "")]
    if hits:
        i = out["events"].index(hits[0])
        chk("시점을 뒤집으면 who 가 foe", PB.flip_log(out["events"])[i].get("who") == "foe")

    # 저장·복원 (야생 배틀은 턴 사이에 DB 에 잔다)
    f = B.Fighter(dex, with_item(char, "CHOICEBAND"))
    f.locked = "EMBER"
    f.used = True
    f.metro = 2
    g = B.Fighter(dex, with_item(char, "CHOICEBAND"))
    g.load_held(f.held_state())
    chk("held 상태가 저장·복원된다", (g.locked, g.used, g.metro) == ("EMBER", True, 2))
    chk("snapshot 에도 들어간다", f.snapshot()["heldState"]["locked"] == "EMBER")

    # 서버 쪽 훅
    chk("행복의알은 경험치 1.5배", H.exp_mult("LUCKYEGG") == 1.5 and H.exp_mult(None) == 1.0)
    chk("교정깁스는 노력치 2배", H.ev_yield("MACHOBRACE", {"atk": 2}) == {"atk": 4})
    chk("파워리스트는 공격 +8", H.ev_yield("POWERBRACER", {"spe": 1}) == {"spe": 1, "atk": 8})
    chk("도구 없으면 그대로", H.ev_yield(None, {"spe": 1}) == {"spe": 1})
    chk("평온의방울은 친밀도 1.5배", H.happiness_mult("SOOTHEBELL") == 1.5)


def t_설명():
    """가방·상점에 붙는 '몇 배인가' 한 줄이 실제 표와 같은가."""
    print("-- 설명 (지녔을 때 몇 배인가)")
    chk("목탄: 불꽃 20% (1.2배)", H.effect_note("CHARCOAL") == "불꽃 타입 기술의 위력이 20% 올라간다 (1.2배)",
        H.effect_note("CHARCOAL"))
    chk("주먹플레이트: 격투 20%", "격투" in H.effect_note("FISTPLATE") and "20%" in H.effect_note("FISTPLATE"))
    # 표의 배율을 바꾸면 설명도 따라 바뀐다 (숫자를 따로 적지 않았다)
    old = H.TYPE_BOOST_MULT
    try:
        H.TYPE_BOOST_MULT = 1.3
        chk("배율을 바꾸면 설명도 바뀐다", "30%" in H.effect_note("CHARCOAL"), H.effect_note("CHARCOAL"))
    finally:
        H.TYPE_BOOST_MULT = old
    chk("구애스카프 조사", H.effect_note("CHOICESCARF").startswith("스피드가 50%"), H.effect_note("CHOICESCARF"))
    no_note = sorted(k for k in H.ALL if not H.effect_note(k))
    # 연막탄은 배틀에서 하는 일이 없다 (도망은 이 게임에 없다)
    chk("지닐 수 있는 도구는 연막탄 말고 모두 설명이 있다", no_note == ["SMOKEBALL"], no_note)
    chk("모르는 도구는 빈 글자", H.effect_note("NOPE") == "" and H.effect_note(None) == "")


def t_종류():
    """가방의 '종류순' 묶음 (1.13.4, 게시판 #323 '이름순 / 특성순'). 지닌 도구를 하는 일로 묶는다."""
    print("-- 종류 (가방의 종류순)")
    p = os.path.join(HERE, "..", "server", "data", "items.json")
    with open(p, encoding="utf-8") as f:
        held = [v["id"] for v in json.load(f)["items"].values() if v.get("cat") == "held"]
    keys = [k for k, _l in H.GROUPS]
    got = dict((i, H.group(i)) for i in held)
    chk("지닌 도구는 모두 묶음 하나에 든다", all(g in keys for g in got.values()),
        [(i, g) for i, g in got.items() if g not in keys][:5])
    etc = sorted(i for i, g in got.items() if g == "etc")
    chk("  '기타' 는 열 남짓 (%d종)" % len(etc), len(etc) <= 12, etc)
    named = set().union(*[v for v in (H.ATTACK, H.RECOVER, H.ONCE, H.GUARD)])
    chk("  묶음에 적은 이름이 도구 목록에 다 있다 (오타 없음)", named <= set(H.KR), named - set(H.KR))
    for item, want in (("ORANBERRY", "berry"), ("CHARCOAL", "type"), ("FLAMEPLATE", "type"), ("FIREGEM", "type"),
                       ("CHOICEBAND", "attack"), ("LIFEORB", "attack"), ("LEFTOVERS", "recover"),
                       ("FOCUSSASH", "recover"), ("WEAKNESSPOLICY", "once"), ("WHITEHERB", "once"),
                       ("HEAVYDUTYBOOTS", "guard"), ("FLAMEORB", "guard"), ("DAMPROCK", "field"),
                       ("LIGHTCLAY", "field"), ("POWERBRACER", "train"), ("LUCKYEGG", "train"),
                       ("LIGHTBALL", "species"), ("WELLSPRINGMASK", "species"), ("IRONBALL", "etc"),
                       ("NOPE", "etc")):
        chk("  %s -> %s" % (item, want), H.group(item) == want, H.group(item))
    chk("  묶음 이름 (화면에 쓰는 말)", H.group_kr("berry") == "열매" and H.group_kr("etc") == "기타")


def t_구애_변화기(dex):
    """구애 도구를 지닌 AI 는 변화기를 고르지 않는다 (1.13.2, 게시판 #284 하늬바람).

    자동 배틀은 매 턴 15% 로 아무 기술이나 고르고, 점수로도 칼춤이 뽑힌다. 구애스카프를 지닌 채 첫 기술로 칼춤을
    쓰면 그 기술에 묶여 쓰러질 때까지 칼춤만 썼다 (한카리아스 400판 중 12판, 4번 내리). 본가에서도 묶이는 것은
    맞다 - 그래서 AI 가 묶이기 전에 변화기를 안 고른다. 트릭 · 체인지는 도구를 상대에게 넘기니 괜찮다.
    """
    print("-- 구애 도구를 지닌 AI 는 변화기에 묶이지 않는다 (#284)")
    sets = ["SWORDSDANCE", "EARTHQUAKE", "DRAGONCLAW", "STONEEDGE"]

    def mk(sp, moves, held, seed):
        m = P.make_pokemon(dex.get(sp), 50, random.Random(seed))
        m["moves"], m["held"] = list(moves), held
        return m

    def firsts(held, ai):
        out = []
        for s in range(200):
            me = B.Fighter(dex, mk("GARCHOMP", sets, held, s))
            foe = B.Fighter(dex, mk("SNORLAX", ["BODYSLAM", "REST", "CRUNCH", "EARTHQUAKE"], None, s + 999))
            bt = B.Battle(dex, me, foe, random.Random(s), ai="trainer")
            out.append(bt.choose_for(me, foe, ai))
        return out

    plain = firsts(None, "trainer")
    chk("(도구가 없으면 200판 중 몇 판은 첫 기술이 칼춤 - 검사 전제)", "SWORDSDANCE" in plain, plain.count("SWORDSDANCE"))
    for held in ("CHOICESCARF", "CHOICEBAND", "CHOICESPECS"):
        for ai in ("trainer", "wild"):
            got = firsts(held, ai)
            chk("%s · %s: 첫 기술로 칼춤을 안 고른다" % (held, ai), "SWORDSDANCE" not in got, got.count("SWORDSDANCE"))
    f = B.Fighter(dex, mk("GARCHOMP", ["TRICK", "SWORDSDANCE", "EARTHQUAKE", "PROTECT"], "CHOICESCARF", 1))
    is_hit = lambda k: k in ("EARTHQUAKE",)                                     # noqa: E731
    chk("트릭은 남긴다 (구애 도구를 상대에게 넘긴다)",
        H.choice_pool(f, ["TRICK", "SWORDSDANCE", "EARTHQUAKE", "PROTECT"], is_hit) == ["TRICK", "EARTHQUAKE"])
    f.locked = "SWORDSDANCE"
    chk("이미 묶였으면 (야생 배틀에서 사람이 골랐다) 그 기술 그대로",
        H.choice_pool(f, ["SWORDSDANCE"], is_hit) == ["SWORDSDANCE"])
    f.locked = None
    chk("변화기만 있으면 그대로 (몸부림으로 빠지지 않게)",
        H.choice_pool(f, ["SWORDSDANCE", "PROTECT"], is_hit) == ["SWORDSDANCE", "PROTECT"])
    f.held = "LEFTOVERS"
    chk("구애 도구가 아니면 그대로", H.choice_pool(f, ["SWORDSDANCE", "EARTHQUAKE"], is_hit) == ["SWORDSDANCE", "EARTHQUAKE"])

    # 관장 · 악당 · 길드전 AI (trainer_battle) 도 같은 규칙. 상대 쪽이 구애스카프 한카리아스.
    from common import trainer_battle as TB
    got = []
    for s in range(60):
        mine = [mk("SNORLAX", ["BODYSLAM", "REST", "CRUNCH", "EARTHQUAKE"], None, s)]
        t = {"name": "검사", "team": [{"species": "GARCHOMP", "level": 50, "moves": sets, "held": "CHOICESCARF"}]}
        tb = TB.TrainerBattle(dex, mine, t, random.Random(s))
        got.append(tb._foe_move())
    chk("관장 AI 도 구애스카프면 칼춤을 안 고른다 (60판)", "SWORDSDANCE" not in got and got, got.count("SWORDSDANCE"))


def t_구애_잠금이_막히면_발버둥(dex):
    """구애 도구로 묶인 기술을 못 쓰게 되면 발버둥 (1.13.3, 본가 · Showdown 과 같다).

    구애스카프로 지진에 묶인 채 사슬묶기를 맞으면, 고르는 쪽(lock_pool)은 잠금을 풀어 드래곤크루를 골랐는데 쓰는
    쪽(force_move)이 다시 지진으로 되돌려 사슬묶기에 막혔다 - 풀릴 때까지 3턴을 그냥 날리는 샌드백이었다 (사람이
    고르는 관장 배틀도 같았다). PP 가 다 떨어졌을 때도 본가는 발버둥이다 (예전에는 잠금을 풀어 줬다).
    """
    print("-- 구애 잠금이 막히면 발버둥 (사슬묶기 · 도발 · PP 0)")
    from common import trainer_battle as TB

    def mk(sp, moves, held=None, lv=50, seed=1):
        m = P.make_pokemon(dex.get(sp), lv, random.Random(seed))
        m["moves"], m["held"] = list(moves), held
        return m

    def locked_then(foe_move, my_moves=("EARTHQUAKE", "DRAGONCLAW", "STONEEDGE", "SWORDSDANCE"), first="EARTHQUAKE"):
        me = B.Fighter(dex, mk("GARCHOMP", my_moves, "CHOICESCARF"))
        foe = B.Fighter(dex, mk("BLISSEY", ["DISABLE", "TAUNT", "SOFTBOILED", "SEISMICTOSS"], None, 70))
        bt = B.Battle(dex, me, foe, random.Random(3), ai="trainer")
        bt.choose_ai = lambda: foe_move
        bt.take_turn(first)
        bt.choose_ai = lambda: "SOFTBOILED"
        return bt, me

    bt, me = locked_then("DISABLE")
    chk("(검사 전제) 지진에 묶인 채 지진이 사슬묶기됐다", me.locked == "EARTHQUAKE"
        and (me.cond.get("disable") or {}).get("move") == "EARTHQUAKE", (me.locked, me.cond.get("disable")))
    chk("자동 배틀은 발버둥을 고른다", bt.choose_mine() == B.STRUGGLE, bt.choose_mine())
    evs = bt.take_turn(bt.choose_mine())
    used = [e.get("move") for e in evs if e.get("t") == "move" and e.get("who") == "me"]
    hit = [e for e in evs if e.get("t") == "hit" and e.get("target") == "foe"]
    chk("  실제로 발버둥이 나가 상대를 때린다 (턴을 날리지 않는다)", used == ["발버둥"] and hit, (used, texts(evs)))
    bt2, me2 = locked_then("DISABLE")
    evs = bt2.take_turn("DRAGONCLAW")                   # 사람이 고른 기술 (관장 배틀)
    chk("사람이 다른 기술을 골라도 발버둥 (막힌 지진으로 되돌리지 않는다)",
        not any("사슬묶기로 쓸 수 없다" in e.get("text", "") for e in evs) and bt2.foe.hp < bt2.foe.maxhp,
        texts(evs))
    chk("  왜 발버둥인지 알린다", any("구애스카프" in e.get("text", "") and "발버둥" in e.get("text", "") for e in evs),
        texts(evs))
    for _ in range(4):
        if (me2.cond.get("disable") or {}).get("move"):
            bt2.take_turn("DRAGONCLAW")
    chk("사슬묶기가 풀리면 다시 묶인 지진", not me2.cond.get("disable") and bt2.choose_mine() == "EARTHQUAKE",
        (me2.cond.get("disable"), bt2.choose_mine()))

    bt3, me3 = locked_then("TAUNT", first="SWORDSDANCE")
    chk("칼춤에 묶인 채 도발을 맞으면 발버둥", me3.locked == "SWORDSDANCE" and bt3.choose_mine() == B.STRUGGLE,
        (me3.locked, me3.cond.get("taunt"), bt3.choose_mine()))
    bt4, me4 = locked_then("SOFTBOILED")
    me4.pp["EARTHQUAKE"] = 0
    chk("묶인 기술의 PP 가 다 떨어지면 발버둥 (본가와 같다)", bt4.choose_mine() == B.STRUGGLE
        and H.force_move(me4, "DRAGONCLAW", [], "me", bt4) == B.STRUGGLE, bt4.choose_mine())
    me4.pp["EARTHQUAKE"] = 10
    me4.held = None
    chk("도구가 없어지면(탁쳐서떨구기 · 트릭) 잠금도 없다", bt4.choose_mine() != B.STRUGGLE
        and H.force_move(me4, "DRAGONCLAW", [], "me", bt4) == "DRAGONCLAW")

    t = {"name": "검사", "team": [{"species": "GARCHOMP", "level": 50, "held": "CHOICESCARF",
                                  "moves": ["EARTHQUAKE", "DRAGONCLAW", "STONEEDGE", "SWORDSDANCE"]}]}
    tb = TB.TrainerBattle(dex, [mk("BLISSEY", ["DISABLE", "SOFTBOILED", "SEISMICTOSS", "TOXIC"], lv=70)], t,
                          random.Random(1))
    tb.foe.locked = "EARTHQUAKE"
    tb.foe.cond["disable"] = {"move": "EARTHQUAKE", "turns": 3}
    chk("관장 · 악당 · 길드전 AI 도 발버둥", tb._foe_move() == B.STRUGGLE, tb._foe_move())


def t_파티배틀_쓰러뜨린_턴에도_턴끝(dex):
    """랭크 · 랜덤 · 친구 배틀(party_battle)에서 상대를 쓰러뜨린 턴에도 턴 끝이 온다 (1.13.3, 게시판 #295 slovena).

    라운드마다 1:1 배틀을 이어 붙이는데, 1:1 배틀은 누가 쓰러지면 '판이 끝났다' 로 턴 끝 처리를 건너뛰었다. 그래서
    화염구슬을 지닌 다투곰이 상대를 한 방에 쓰러뜨리는 동안 화상이 안 걸려 '2~3턴 뒤에 걸린다' 로 보였고 근성도
    그만큼 늦게 켜졌다 (먹다남은음식 · 독 데미지 · 가속도 같다). 본가는 쓰러진 턴에도 턴 끝 효과가 온 뒤에 다음
    포켓몬이 나온다. 관장 · 실시간 배틀은 원래 그렇게 했다. **마지막 포켓몬이 쓰러지면 판이 끝나므로 턴 끝은 없다.**
    """
    print("-- 파티 배틀: 쓰러뜨린 턴에도 턴 끝 (#295 다투곰 화염구슬)")

    def mk(sp, moves, held=None, ab=None, lv=50, seed=1):
        m = P.make_pokemon(dex.get(sp), lv, random.Random(seed))
        m["moves"], m["held"] = list(moves), held
        if ab:
            m["ability"] = ab
        return m

    def first_burn(out):
        """다투곰이 화상이 된 때: 몇 번째 라운드 안에서인가 (처음 쓰러뜨린 사건 뒤인가)."""
        rnd, fell = 0, False
        for e in out["events"]:
            if e.get("t") == "round":
                rnd += 1
            if e.get("t") == "faint" and e.get("who") == "foe":
                fell = True
            if e.get("t") == "ailment" and e.get("who") == "me" and e.get("status") == "burn":
                return rnd, fell
        return None, fell

    ursa = mk("URSALUNA", ["FACADE", "HEADLONGRUSH", "CRUNCH", "PROTECT"], "FLAMEORB", "GUTS", lv=70)
    weak = mk("CATERPIE", ["TACKLE"], lv=5, seed=2)
    wall = mk("BLISSEY", ["SEISMICTOSS", "SOFTBOILED", "PROTECT", "DEFENSECURL"], lv=100, seed=3)
    out = PB.simulate(dex, [ursa], [weak, wall], seed=7)
    got = first_burn(out)
    chk("상대를 한 방에 쓰러뜨린 첫 턴에 화염구슬로 화상 (다음 상대가 나오기 전)", got == (1, True), got)
    out = PB.simulate(dex, [mk("URSALUNA", ["FACADE"], "FLAMEORB", "GUTS", lv=70)], [mk("CATERPIE", ["TACKLE"], lv=5)],
                      seed=7)
    chk("  마지막 포켓몬을 쓰러뜨렸으면 판이 끝나 턴 끝은 없다", first_burn(out)[0] is None and out["winner"] == "me",
        (first_burn(out), out["winner"]))
    hurt = mk("SNORLAX", ["BODYSLAM", "REST", "CURSE", "PROTECT"], "LEFTOVERS", lv=80)
    # 꼬렛의 전광석화(선제)에 조금 깎인 뒤 잠만보가 쓰러뜨린다 - 깎인 게 있어야 먹다남은음식이 회복한다
    out = PB.simulate(dex, [hurt], [mk("RATTATA", ["QUICKATTACK"], lv=20), mk("METAPOD", ["HARDEN"], lv=5)], seed=3)
    rnd, healed = 0, None
    for e in out["events"]:
        if e.get("t") == "round":
            rnd += 1
        if e.get("t") == "heal" and "먹다남은음식" in (e.get("text") or "") and healed is None:
            healed = rnd
    chk("  먹다남은음식도 쓰러뜨린 턴에 회복 (잠만보가 첫 상대를 쓰러뜨린 1라운드에)", healed == 1, healed)
    blaz = mk("BLAZIKEN", ["FLAREBLITZ"], None, "SPEEDBOOST", lv=70)
    pb = PB.PartyBattle(dex, [blaz], [mk("BLISSEY", ["SOFTBOILED"], lv=100, seed=3)], seed=7)
    pb.run()
    first = []
    for e in pb.events:
        if e.get("t") == "move" and e.get("who") == "me":
            first.append("move")
        if e.get("t") == "stat" and e.get("who") == "me" and "스피드" in (e.get("text") or ""):
            first.append("boost")
    chk("가속: 판이 시작된 첫 턴 끝에도 오른다 (라운드 시작에 나온 것은 '이번 턴에 나온 것' 이 아니다)",
        first[:2] == ["move", "boost"], first[:4])
    pb = PB.PartyBattle(dex, [mk("CATERPIE", ["STRINGSHOT"], lv=2, seed=5), mk("BLAZIKEN", ["FLAREBLITZ"], None,
                                                                              "SPEEDBOOST", lv=70)],
                        [mk("RATTATA", ["TACKLE"], lv=20, seed=6),
                         mk("BLISSEY", ["SOFTBOILED"], lv=100, seed=3)], seed=7)
    pb.run()
    seq, rnd = [], 0
    for e in pb.events:
        if e.get("t") == "round":
            rnd += 1
        if rnd >= 2 and e.get("who") == "me" and (e.get("t") == "move" or "스피드" in (e.get("text") or "")):
            seq.append("boost" if e.get("t") == "stat" else "move")
    chk("  쓰러진 포켓몬 대신 나온 것도 그 다음 첫 턴 끝에 오른다", seq[:2] == ["move", "boost"], seq[:4])


def main():
    dex = load_dex()
    t_도구_없으면_그대로(dex)
    t_카탈로그와_맞는다()
    t_효과(dex)
    t_설명()
    t_종류()
    t_구애_변화기(dex)
    t_구애_잠금이_막히면_발버둥(dex)
    t_파티배틀_쓰러뜨린_턴에도_턴끝(dex)
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
