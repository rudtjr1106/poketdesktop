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

# 도구를 넣기 **전** 엔진(1.0.20)으로 뜬 값. 같은 파티·같은 시드다.
PARTY_DIGEST = "c59229ab7dcfaeff764a290d45fb8f00ca2e9082cd04c49f162ef128a7f956f5"
SOLO_DIGEST = "67bf05ec978317a0b3ce9314c18d2975e43cb9bb46344b26e28382e38a795758"


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
    h = hashlib.sha256()
    for s in range(1, 31):
        out = PB.simulate(dex, A, Bm, seed=s)
        h.update(json.dumps(out["events"], sort_keys=True,
                            ensure_ascii=False).encode())
    chk("파티전 30판 요약값이 1.0.20 과 같다", h.hexdigest() == PARTY_DIGEST,
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
    chk("야생전 30판 요약값이 1.0.20 과 같다", h2.hexdigest() == SOLO_DIGEST,
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
    held_cat = set(k for k, v in it.items() if v["cat"] == "held")
    chk("held 분류 도구가 전부 held.KR 에 있다 (효과 없는 도구 금지)",
        not (held_cat - set(H.KR)), sorted(held_cat - set(H.KR)))
    chk("held.KR 의 도구가 전부 카탈로그에 있다", not (set(H.KR) - set(it)),
        sorted(set(H.KR) - set(it)))
    bad = [(k, H.KR[k], it[k]["kr"]) for k in H.KR if k in it
           and it[k]["kr"] != H.KR[k]]
    chk("한글 이름이 PokeAPI 와 같다", not bad, bad[:5])
    chk("지닌 도구는 설명이 있다",
        all(it[k].get("desc") for k in held_cat),
        [k for k in held_cat if not it[k].get("desc")][:5])
    both = sorted((set(H.KR) & set(it)) - held_cat)
    chk("돌이면서 지닐 수 있는 넷은 돌로 남는다",
        both == ["KINGSROCK", "METALCOAT", "RAZORCLAW", "RAZORFANG"], both)
    chk("도구 종류가 121 이다", len(H.KR) == 121, len(H.KR))


# ---------------------------------------------------------------- 3. 효과
def t_효과(dex):
    print("-- 도구가 실제로 뭔가 한다")
    rng = random.Random(7)
    pika = P.make_pokemon(dex.get(25), 40, rng)
    char = P.make_pokemon(dex.get(4), 40, rng)
    wall = P.make_pokemon(dex.get(95), 40, rng)       # 오닉스: 단단하고 선공기 없음
    bag = P.make_pokemon(dex.get(143), 30, rng)       # 잠만보 Lv.30: 오래 맞아 준다
    tank = P.make_pokemon(dex.get(143), 45, rng)      # 잠만보 Lv.45: 오래 산다

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

    # 구애머리띠: 첫 기술만 계속 쓴다 (샌드백 잠만보 Lv.30 상대로 여러 턴)
    evs, bt = solo(dex, with_item(char, "CHOICEBAND"), bag, 3, turns=6)
    used = [e["move"] for e in evs if e.get("t") == "move" and e.get("who") == "me"]
    chk("구애머리띠는 처음 쓴 기술만 쓴다", len(set(used)) == 1 and len(used) >= 3,
        used)
    chk("구애 잠금이 기억된다", bt.me.locked is not None, bt.me.locked)
    evs0, _ = solo(dex, char, bag, 3, turns=6)
    used0 = [e["move"] for e in evs0 if e.get("t") == "move" and e.get("who") == "me"]
    chk("(같은 시드에서 도구 없이도 판이 두 턴은 간다 - 검사 전제)",
        len(used0) >= 2, used0)
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


def main():
    dex = load_dex()
    t_도구_없으면_그대로(dex)
    t_카탈로그와_맞는다()
    t_효과(dex)
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
