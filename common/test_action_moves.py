# -*- coding: utf-8 -*-
"""액션 배틀 기술 꼴 표 검사.

    python common/test_action_moves.py

도감 920기술 전부에 꼴이 있고, 수치가 말이 되고, 이름난 기술이 규칙대로 갈리는지 본다.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import action_moves as AM                 # noqa: E402
from common import pokelogic as P                     # noqa: E402

DEX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "server", "data", "pokedex.json")
OK = FAIL = 0
DEX = None


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def contract():
    print("== 약속한 이름 (서버 · 웹 화면이 그대로 쓴다)")
    chk("KINDS", AM.KINDS == ("proj", "beam", "melee", "dash", "burst", "cone", "strike", "leap", "self", "heal",
                              "guard", "counter", "hazard", "status", "none"), AM.KINDS)
    chk("STYLES", tuple(AM.STYLES) == ("orb", "flame", "jet", "zap", "leaf", "shard", "psy", "rock", "ghost", "dark",
                                       "fairy", "poison", "wind", "sound", "punch", "slash", "bite", "beam", "wave",
                                       "quake", "heal", "buff", "shield", "powder", "web"), AM.STYLES)
    k = AM.kit(DEX, "TACKLE")
    want = {"kind", "wind", "act", "rec", "cd", "pp", "range", "w", "speed", "n", "spread", "home", "lock", "sty",
            "ok", "why"}
    chk("kit 열쇠가 약속 그대로", set(k) == want, sorted(set(k) ^ want))
    chk("kit 은 JSON 으로 나간다", json.loads(json.dumps(k)) == k)
    chk("캐시: 두 번 불러도 같은 것", AM.kit(DEX, "TACKLE") is k)
    u = AM.kit(DEX, "NOTAMOVE")
    chk("모르는 기술은 못 쓰는 칸", u["kind"] == "none" and not u["ok"] and u["why"], u)


def every_move():
    print("== 920기술 전부")
    keys = sorted(DEX.moves)
    chk("기술 920개", len(keys) == 920, len(keys))
    bad = []
    for key in keys:
        k = AM.kit(DEX, key)
        nums = [k[f] for f in ("wind", "act", "rec", "cd", "range", "w", "speed")]
        good = (k["kind"] in AM.KINDS and k["sty"] in AM.STYLES
                and all(isinstance(v, (int, float)) and v > 0 for v in nums)
                and isinstance(k["pp"], int) and k["pp"] >= 1 and isinstance(k["n"], int) and k["n"] >= 1
                and k["spread"] >= 0 and k["home"] >= 0 and 0 <= k["lock"] <= 1
                and isinstance(k["ok"], bool) and isinstance(k["why"], str)
                and (k["ok"] == (k["kind"] != "none")) and (bool(k["why"]) == (not k["ok"])))
        if not good:
            bad.append((key, k))
    chk("꼴 · 모양 · 수치가 다 말이 된다 (못 쓰면 까닭이 있다)", not bad, bad[:3])
    pp_bad = [key for key in keys if AM.kit(DEX, key)["pp"] != max(1, int(math.ceil(DEX.move(key)["pp"] / 2.0)))]
    chk("PP = 본가 PP 의 절반 (올림)", not pp_bad, pp_bad[:5])
    slow = [key for key in keys if AM.kit(DEX, key)["cd"] < AM.kit(DEX, key)["wind"] + AM.kit(DEX, key)["act"]
            + AM.kit(DEX, key)["rec"]]
    chk("대기시간이 한 번 쓰는 시간보다 길다", not slow, slow[:5])
    fast = [key for key in keys if AM.kit(DEX, key)["kind"] in ("proj", "status")
            and (AM.kit(DEX, key)["speed"] > 1200 or AM.kit(DEX, key)["w"] > 70)]
    chk("탄은 옆으로 비켜 피할 수 있다 (너무 빠르거나 크지 않다)", not fast, fast[:5])

    status = [key for key in keys if DEX.move(key)["cat"] == "status"]
    none = [key for key in status if AM.kit(DEX, key)["kind"] == "none"]
    chk("못 쓰는 변화기가 35%% 이하 (%d / %d)" % (len(none), len(status)), len(none) <= 0.35 * len(status),
        len(none))
    s = AM.summary(DEX)
    chk("summary: 꼴별 개수가 920 을 채운다", sum(s["kinds"].values()) == 920, s["kinds"])
    chk("summary: 못 쓰는 목록 = none 꼴", sorted(s["none"]) == sorted(
        key for key in keys if AM.kit(DEX, key)["kind"] == "none"), len(s["none"]))
    chk("summary: 모든 꼴이 한 번은 나온다", all(s["kinds"].get(kd) for kd in AM.KINDS), s["kinds"])


def named():
    print("== 이름난 기술")
    want = {
        "FLAMETHROWER": "cone",          # 화염방사는 날리기가 아니다 (뿜는 불길)
        "QUICKATTACK": "dash", "EXTREMESPEED": "dash", "AQUAJET": "dash",
        "EARTHQUAKE": "burst", "SURF": "burst", "DISCHARGE": "burst", "EXPLOSION": "burst",
        "SWORDSDANCE": "self", "DRAGONDANCE": "self", "NASTYPLOT": "self", "REFLECT": "self",
        "RECOVER": "heal", "ROOST": "heal",
        "PROTECT": "guard", "DETECT": "guard",
        "THUNDERWAVE": "status", "WILLOWISP": "status", "HYPNOSIS": "status", "TOXIC": "status",
        "LEECHSEED": "status",
        "SOLARBEAM": "beam", "HYPERBEAM": "beam", "ICEBEAM": "beam",
        "FLY": "leap", "DIG": "leap",
        "COUNTER": "counter", "MIRRORCOAT": "counter",
        "STEALTHROCK": "hazard", "SPIKES": "hazard",
        "BATONPASS": "none", "PERISHSONG": "none", "TRANSFORM": "none",
        "SHADOWBALL": "proj", "WATERGUN": "proj", "THUNDERBOLT": "proj", "AURASPHERE": "proj",
        "BULLETSEED": "proj", "ICESHARD": "proj",
        "THUNDER": "strike", "ROCKSLIDE": "strike", "FISSURE": "strike",
        "HEATWAVE": "cone", "BLIZZARD": "cone", "HYPERVOICE": "cone", "ICYWIND": "cone", "LEER": "cone",
        "GROWL": "burst",                # 소리로 내리는 것은 둘레로
        "TACKLE": "melee", "CRUNCH": "melee", "MACHPUNCH": "dash", "AERIALACE": "melee", "DOUBLESLAP": "melee",
    }
    wrong = [(k, AM.kit(DEX, k)["kind"], v) for k, v in sorted(want.items()) if AM.kit(DEX, k)["kind"] != v]
    chk("꼴이 규칙대로 (%d개)" % len(want), not wrong, wrong)
    chk("못 쓰는 칸엔 까닭이 있다 (바톤터치)", "턴" in AM.kit(DEX, "BATONPASS")["why"], AM.kit(DEX, "BATONPASS")["why"])
    chk("솔라빔은 1.1초 모은다", abs(AM.kit(DEX, "SOLARBEAM")["wind"] - 1.1) < 1e-9, AM.kit(DEX, "SOLARBEAM"))
    chk("일격기는 1.5초 모은다", abs(AM.kit(DEX, "FISSURE")["wind"] - 1.5) < 1e-9, AM.kit(DEX, "FISSURE"))
    chk("광선 · 내려찍기는 준비가 눈에 보일 만큼 길다",
        AM.kit(DEX, "ICEBEAM")["wind"] >= 0.5 and AM.kit(DEX, "THUNDER")["wind"] >= 0.6)
    chk("광선 · 회복은 준비 중 못 움직인다",
        AM.kit(DEX, "ICEBEAM")["lock"] == 0 and AM.kit(DEX, "RECOVER")["lock"] == 0)
    chk("날리기는 준비 중 조금 움직인다", AM.kit(DEX, "WATERGUN")["lock"] == 0.35)
    chk("반드시 맞는 기술은 살짝 따라간다 (파동탄 · 제비반환)",
        AM.kit(DEX, "AURASPHERE")["home"] > 0 and AM.kit(DEX, "AERIALACE")["home"] > 0
        and AM.kit(DEX, "WATERGUN")["home"] == 0)
    chk("여러 번 치는 기술은 여러 발 부채꼴", AM.kit(DEX, "BULLETSEED")["n"] == 5 and AM.kit(DEX, "BULLETSEED")["spread"] > 0,
        AM.kit(DEX, "BULLETSEED"))
    chk("연속 근접은 여러 대", AM.kit(DEX, "DOUBLESLAP")["n"] == 5)
    chk("공 기술(섀도볼)은 크고 느리다",
        AM.kit(DEX, "SHADOWBALL")["w"] > AM.kit(DEX, "DARKPULSE")["w"]
        and AM.kit(DEX, "SHADOWBALL")["speed"] < AM.kit(DEX, "DARKPULSE")["speed"])
    chk("센 기술일수록 대기가 길다", AM.kit(DEX, "HYDROPUMP")["cd"] > AM.kit(DEX, "WATERGUN")["cd"])
    chk("돌진은 길게 달린다", AM.kit(DEX, "EXTREMESPEED")["range"] > AM.kit(DEX, "QUICKATTACK")["range"] >= 300)
    melee = [k for k in sorted(DEX.moves) if AM.kit(DEX, k)["kind"] == "melee"]
    off = [(k, AM.kit(DEX, k)["range"], AM.kit(DEX, k)["w"]) for k in melee
           if not (160 <= AM.kit(DEX, k)["range"] <= 240 and AM.kit(DEX, k)["w"] == AM.MELEE_W)]
    chk("근접은 앞으로 달려들며 친다: 거리 160~240 · 너비 %d (%d개)" % (AM.MELEE_W, len(melee)), melee and not off,
        off[:5])
    chk("센 근접일수록 멀리 달린다", AM.kit(DEX, "DRAGONCLAW")["range"] > AM.kit(DEX, "SCRATCH")["range"],
        (AM.kit(DEX, "DRAGONCLAW")["range"], AM.kit(DEX, "SCRATCH")["range"]))
    slow = [k for k in melee if abs(AM.kit(DEX, k)["range"] / AM.kit(DEX, k)["speed"] - AM.RUSH_SEC) > 0.01]
    chk("근접 달려들기는 %.2f초 만에 끝난다" % AM.RUSH_SEC, not slow, slow[:5])
    chk("발동 시간은 달려들기 + 연속 타격", AM.kit(DEX, "DRAGONCLAW")["act"] >= AM.RUSH_SEC
        and AM.kit(DEX, "DOUBLEKICK")["act"] > AM.kit(DEX, "DRAGONCLAW")["act"], AM.kit(DEX, "DOUBLEKICK"))
    chk("돌진은 근접보다 길고 빠르다", AM.kit(DEX, "QUICKATTACK")["range"] > 240
        and AM.kit(DEX, "QUICKATTACK")["speed"] > max(AM.kit(DEX, k)["speed"] for k in melee))
    chk("변화기 대기는 6~14초", all(6 <= AM.kit(DEX, k)["cd"] <= 14 for k in
                                ("SWORDSDANCE", "THUNDERWAVE", "STEALTHROCK", "REFLECT", "LEER", "RECOVER",
                                 "SHELLSMASH", "SPORE")))
    chk("PP 절반: 파괴광선 5 → 3, 화염방사 15 → 8",
        AM.kit(DEX, "HYPERBEAM")["pp"] == 3 and AM.kit(DEX, "FLAMETHROWER")["pp"] == 8)


def styles():
    print("== 이펙트 모양")
    want = {"FLAMETHROWER": "flame", "THUNDERBOLT": "zap", "SURF": "wave", "SPORE": "powder", "HYPERVOICE": "sound",
            "MACHPUNCH": "punch", "CRUNCH": "bite", "XSCISSOR": "slash", "HURRICANE": "wind", "HYPERBEAM": "beam",
            "EARTHQUAKE": "quake", "PROTECT": "shield", "REFLECT": "shield", "SWORDSDANCE": "buff",
            "RECOVER": "heal", "STICKYWEB": "web", "SHADOWBALL": "ghost", "DARKPULSE": "wave",
            "MOONBLAST": "fairy", "SLUDGEBOMB": "poison", "STONEEDGE": "rock", "ICESHARD": "shard",
            "PSYCHIC": "psy", "ENERGYBALL": "leaf", "SWIFT": "orb", "WATERGUN": "jet", "NIGHTSLASH": "slash"}
    wrong = [(k, AM.style_of(DEX.move(k)), v) for k, v in sorted(want.items()) if AM.style_of(DEX.move(k)) != v]
    chk("모양이 기술답다 (%d개)" % len(want), not wrong, wrong)
    chk("kit 의 sty 는 style_of 그대로", AM.kit(DEX, "THUNDERBOLT")["sty"] == "zap")


def move_data():
    print("== 도감에 없는 효과 채우기 (move_of)")
    bd = AM.move_of(DEX, "BELLYDRUM")
    chk("배북: 공격 +6 · 체력 절반", bd["stat"] == [["atk", 6]] and bd["heal"] == -50, bd.get("stat"))
    chk("도감 원본은 그대로", DEX.move("BELLYDRUM").get("stat") == [])
    chk("고칠 것이 없으면 도감 것 그대로", AM.move_of(DEX, "TACKLE") is DEX.move("TACKLE"))
    chk("하품은 잠듦을 건다", AM.move_of(DEX, "YAWN")["ail"] == "sleep")
    chk("모르는 기술은 None", AM.move_of(DEX, "NOTAMOVE") is None)


def main():
    global DEX
    DEX = P.Pokedex.load(DEX_PATH)
    contract()
    every_move()
    named()
    styles()
    move_data()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
