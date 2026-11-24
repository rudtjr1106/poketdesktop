# -*- coding: utf-8 -*-
"""배틀타워 (시즌 7) — 1~50층의 트레이너와 팀을 만든다.

    python tools/build_tower.py            # server/data/tower.json 을 쓴다
    python tools/build_tower.py --check    # 파일이 아래 명세와 같은지만 본다 (다르면 1)

## 규칙 (사용자가 정했다, 2026-11-24)

  · 세븐나이츠 무한의 탑처럼 1층부터 차례로 오르고, 층마다 처음 이긴 한 번만 보상을 받는다.
  · **상대 팀은 같은 종 · 같은 도구가 겹쳐도 된다.** 사람 팀에는 못 하는 구성이다 (pvp.split_restricted · rules_v5).
  · 층마다 다른 포켓몬을 꺼내 쓰게 되도록 테마가 다 다르고, 위로 갈수록 어렵다.
  · 처음은 50층. 뒤에 계속 붙인다 - 50층이 끝판왕일 필요는 없다 (능력치 배율 boost 는 51층부터 쓸 손잡이로 남긴다).
  · 칭호는 주지 않는다. 보상은 돈 · 도구 · 알.

## 층 번호가 정하는 것

    레벨      min(100, 28 + 2 x 층)            1층 30 … 36층부터 100
    마릿수    1~4층 3 · 5~9층 4 · 10~20층 5 · 21층부터 6
    종류      5의 배수 = 관문(gate) · 10의 배수 = 층주(boss) · 나머지 normal
    AI        1~40층 관장 AI (ai="gym", 얕은 셈 · 레벨이 낮으면 실수) · 41층부터 길드전 AI (ai="war", 깊은 셈)
    노력치    1구역(1~10) 0 · 무보정 / 2구역(11~20) 주 능력 252 / 3구역부터 510 다

깊은 셈은 서버 CPU 를 먹는다 (11/23~24 부하 줄이기). 41층부터만 쓰는 까닭 - 거기까지 온 사람이 적다.

## 명세 (FLOORS)

층마다 (층, 이름, 인물, [포켓몬 ...]) 한 줄이다. 인물은 gyms.json 의 트레이너 id - 이름 · 역할 · 도트만 빌리고
팀은 여기 적은 것이다 (본가의 배틀타워 · PWT 처럼 초청된 사람들). **층주 다섯은 인물이 먼저**(프런티어 브레인 -
그 사람의 원작 포켓몬을 넣는다), **나머지는 테마가 먼저**다.

포켓몬은 M(종, 도구, 특성, 성격, 노력치, 기술). 뒤를 비우면 build_gyms 의 고르는 법(그 레벨까지 배우는 기술 중
위력 좋은 것 · 기술에 맞춘 성격)으로 채운다 - 1 · 2구역이 그렇다. 3구역부터는 전부 적는다.
노력치는 "atk/spe" 처럼 적는다 (둘에 252씩, 남는 6은 HP - HP 가 그 둘 안에 있으면 방어 쪽).

## 엔진이 요구하는 깃발 (자료에 적어 둔다 - 서버는 그대로 넘긴다)

    noMega     메가스톤을 쥔 포켓몬이 없는 층. trainer_battle.give_mega_stone 이 Lv.80 이상 트레이너의 첫 포켓몬
               도구를 메가스톤으로 바꿔 버리는 것을 막는다.
    keystone   메가스톤을 쥔 포켓몬이 있는 층 (길드전 AI 는 이 값을 봐야 메가진화한다).
    zring      Z크리스탈을 쥔 포켓몬이 있는 층.  orb  테라피스를 쥔 포켓몬이 있는 층.

고친 뒤에는 tools/sim_tower.py 로 승률을 다시 잰다 (design-notes/2026-11-24-battle-tower.md 의 눈금).
"""
import argparse
import difflib
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import movecalc as MC          # noqa: E402
from common import pokelogic as P           # noqa: E402
from common import trainer_battle as TB    # noqa: E402

import build_gyms as G                      # noqa: E402

DATA = os.path.join(ROOT, "server", "data")
OUT_PATH = os.path.join(DATA, "tower.json")
VERSION = 1
TOTAL = 50
BOSSES = {10: "greta", 20: "lucy", 30: "tucker", 40: "anabel", 50: "palmer"}
VITAMINS = ["HPUP", "PROTEIN", "IRON", "CALCIUM", "ZINC", "CARBOS"]


# ---------------------------------------------------------------- 층 번호가 정하는 것
def level_for(n):
    return min(100, 28 + 2 * n)


def size_for(n):
    return 3 if n <= 4 else 4 if n <= 9 else 5 if n <= 20 else 6


def kind_for(n):
    return "boss" if n % 10 == 0 else "gate" if n % 5 == 0 else "normal"


def ai_for(n):
    return "gym" if n <= 40 else "war"


def zone_of(n):
    """구역 0~4 (1~10층이 0)."""
    return (n - 1) // 10


GATE_ITEMS = {5: [["RARECANDY", 1]], 15: [["BOTTLECAP", 2]], 25: [["RANKTICKETTM", 1]],
              35: [["GOLDBOTTLECAP", 1]], 45: [["RANKTICKETTMTYPE", 1]]}
BOSS_ITEMS = {10: [["RARECANDY", 2]], 20: [["RANKTICKETTM", 1], ["GOLDBOTTLECAP", 1]], 30: [["MASTERBALL", 1]],
              40: [["SHINYCANDY", 1], ["GOLDBOTTLECAP", 1]], 50: [["RANKTICKETTMTYPE", 1]]}


def reward_for(n):
    """처음 이겼을 때 한 번 받는 것. 돈은 구역마다 2,000원씩 오르고 관문은 두 배, 층주는 세 배.

    합계 390,000원 (관장 256곳 첫 승 합계 770,250원의 절반쯤). 귀한 것은 전부 한 번뿐이다:
    금색병뚜껑 3 · 랜덤 기술머신 뽑기권 2 · 타입 확정 기술머신 뽑기권 2 · 마스터볼 1 · 이로치사탕 1 · 전설의 알 1.
    """
    z = zone_of(n)
    base = 2000 * (z + 1)
    kind = kind_for(n)
    if kind == "boss":
        return {"money": base * 3, "items": [list(x) for x in BOSS_ITEMS[n]], "egg": "legendary" if n == 50 else None}
    if kind == "gate":
        return {"money": base * 2, "items": [list(x) for x in GATE_ITEMS[n]], "egg": None}
    if z == 2:
        # 영양제 여섯 가지를 보통 층 차례로 돌린다 (21 · 22 · 23 · 24 · 26 · 27 · 28 · 29)
        order = [f for f in range(21, 31) if kind_for(f) == "normal"]
        items = [[VITAMINS[order.index(n) % len(VITAMINS)], 1]]
    else:
        items = [[["POKEBALL", 5]], [["ULTRABALL", 3]], None, [["BOTTLECAP", 1]], [["RARECANDY", 1]]][z]
    return {"money": base, "items": [list(x) for x in items], "egg": None}


# ---------------------------------------------------------------- 명세
def M(species, held=None, ability=None, nature=None, evs=None, moves=None):
    return {"species": species, "held": held, "ability": ability, "nature": nature, "evs": evs, "moves": moves}


FLOORS = [
    # ===== 1구역 입문 (Lv.30~48) - 노력치 0, 도구 없음 (관문 · 층주만 열매) =====
    (1, "풀숲", "erika", [M("IVYSAUR"), M("GLOOM"), M("WEEPINBELL")]),
    (2, "불씨", "flannery", [M("PONYTA"), M("MAGMAR"), M("TORKOAL")]),
    (3, "물가", "misty", [M("STARMIE"), M("GOLDUCK"), M("SEAKING")]),
    (4, "전기 울타리", "lt-surge", [M("RAICHU"), M("MAGNETON"), M("ELECTABUZZ")]),
    (5, "노말의 벽", "whitney", [M("MILTANK", "SITRUSBERRY"), M("URSARING", "CHESTOBERRY"),
                              M("KANGASKHAN", "ORANBERRY"), M("TAUROS", "LUMBERRY")]),
    # 같은 종이 처음 겹치는 층
    (6, "벌레 떼", "bugsy", [M("BEEDRILL"), M("BEEDRILL"), M("VESPIQUEN"), M("PINSIR")]),
    (7, "돌과 땅", "brock", [M("ONIX"), M("GOLEM"), M("RHYDON"), M("SANDSLASH")]),
    (8, "독안개", "janine", [M("WEEZING"), M("MUK"), M("CROBAT"), M("ARIADOS")]),
    (9, "격투 도장", "chuck", [M("POLIWRATH"), M("PRIMEAPE"), M("HITMONLEE"), M("HITMONCHAN")]),
    # 층주 나리 (배틀아레나): 헤라크로스 · 블래키 · 껍질몬 / 버섯모 · 팬텀
    (10, "배틀아레나", "greta", [M("HERACROSS", "SALACBERRY"), M("UMBREON", "SITRUSBERRY"),
                              M("SHEDINJA", "LUMBERRY"), M("BRELOOM", "CHESTOBERRY"), M("GENGAR", "ORANBERRY")]),

    # ===== 2구역 수련 (Lv.50~68) - 주 능력 252, 기본 도구 =====
    (11, "유령의 방", "morty", [M("COFAGRIGUS", "SPELLTAG"), M("MISMAGIUS", "WISEGLASSES"), M("DUSCLOPS", "EVIOLITE"),
                             M("BANETTE", "MUSCLEBAND"), M("DRIFBLIM", "SITRUSBERRY")]),
    (12, "얼음 동굴", "pryce", [M("MAMOSWINE", "NEVERMELTICE"), M("LAPRAS", "SITRUSBERRY"), M("DEWGONG", "LEFTOVERS"),
                             M("GLALIE", "BRIGHTPOWDER"), M("FROSLASS", "WISEGLASSES")]),
    (13, "초능력 연구실", "sabrina", [M("ALAKAZAM", "TWISTEDSPOON"), M("HYPNO", "LEFTOVERS"), M("ESPEON", "WISEGLASSES"),
                                 M("MRMIME", "LIGHTCLAY"), M("XATU", "SITRUSBERRY")]),
    (14, "뒷골목", "karen", [M("HOUNDOOM", "CHARCOAL"), M("HONCHKROW", "BLACKGLASSES"), M("WEAVILE", "MUSCLEBAND"),
                          M("ABSOL", "SCOPELENS"), M("SHARPEDO", "MYSTICWATER")]),
    # 같은 도구가 처음 겹치는 층 - 다섯 다 먹다남은음식
    (15, "강철 요새", "jasmine", [M("STEELIX", "LEFTOVERS"), M("SKARMORY", "LEFTOVERS"), M("PROBOPASS", "LEFTOVERS"),
                              M("FORRETRESS", "LEFTOVERS"), M("BRONZONG", "LEFTOVERS")]),
    (16, "요정의 숲", "valerie", [M("TOGEKISS", "SITRUSBERRY"), M("AZUMARILL", "MYSTICWATER"), M("GRANBULL", "MUSCLEBAND"),
                              M("FLORGES", "LEFTOVERS"), M("CLEFABLE", "FAIRYFEATHER")]),
    (17, "용의 둥지", "clair", [M("KINGDRA", "DRAGONFANG"), M("ALTARIA", "SITRUSBERRY"), M("FLYGON", "SOFTSAND"),
                             M("DRUDDIGON", "ROCKYHELMET"), M("NOIVERN", "WISEGLASSES")]),
    # 같은 종 둘씩
    (18, "쌍둥이 층", "tate-and-liza", [M("SOLROCK", "HARDSTONE"), M("SOLROCK", "SITRUSBERRY"),
                                    M("LUNATONE", "TWISTEDSPOON"), M("LUNATONE", "SITRUSBERRY"),
                                    M("CLAYDOL", "LEFTOVERS")]),
    (19, "하늘길", "winona", [M("SWELLOW", "FLAMEORB", "GUTS"), M("STARAPTOR", "SHARPBEAK"), M("TROPIUS", "SITRUSBERRY"),
                           M("GLISCOR", "TOXICORB", "POISONHEAL"), M("BRAVIARY", "MUSCLEBAND")]),
    # 층주 다슬 (배틀튜브 - 독 · 마비 · 화상): 세비퍼 · 단단지 · 밀로틱 / 강철톤 · 갸라도스
    (20, "배틀튜브", "lucy", [
        M("SEVIPER", "BLACKSLUDGE", "SHEDSKIN", moves=["GLARE", "SLUDGEBOMB", "EARTHQUAKE", "GIGADRAIN"]),
        M("SHUCKLE", "LEFTOVERS", "STURDY", moves=["TOXIC", "ROCKSLIDE", "KNOCKOFF", "STEALTHROCK"]),
        M("MILOTIC", "FLAMEORB", "MARVELSCALE", moves=["SCALD", "RECOVER", "ICEBEAM", "TOXIC"]),
        M("STEELIX", "SITRUSBERRY", "STURDY", moves=["EARTHQUAKE", "IRONHEAD", "TOXIC", "ROCKSLIDE"]),
        M("GYARADOS", "LUMBERRY", "INTIMIDATE", moves=["WATERFALL", "THUNDERWAVE", "EARTHQUAKE", "ICEFANG"])]),

    # ===== 3구역 전술 (Lv.70~88) - 노력치 510, 날씨 · 필드 · 트릭룸 =====
    (21, "장맛비", "juan", [
        M("POLITOED", "DAMPROCK", "DRIZZLE", "BOLD", "hp/def", ["SCALD", "ICEBEAM", "HYPNOSIS", "ENCORE"]),
        M("LUDICOLO", "LIFEORB", "SWIFTSWIM", "MODEST", "spa/spe", ["HYDROPUMP", "GIGADRAIN", "ICEBEAM", "RAINDANCE"]),
        M("KABUTOPS", "CHOICEBAND", "SWIFTSWIM", "ADAMANT", "atk/spe", ["WATERFALL", "STONEEDGE", "AQUAJET", "KNOCKOFF"]),
        M("OMASTAR", "WISEGLASSES", "SWIFTSWIM", "MODEST", "spa/spe", ["HYDROPUMP", "ICEBEAM", "EARTHPOWER", "ANCIENTPOWER"]),
        M("TOXICROAK", "BLACKSLUDGE", "DRYSKIN", "ADAMANT", "atk/spe", ["DRAINPUNCH", "GUNKSHOT", "SUCKERPUNCH", "SWORDSDANCE"]),
        M("SEISMITOAD", "LEFTOVERS", "SWIFTSWIM", "MODEST", "spa/spe", ["HYDROPUMP", "EARTHPOWER", "SLUDGEWAVE", "FOCUSBLAST"])]),
    (22, "가뭄", "blaine", [
        M("NINETALES", "HEATROCK", "DROUGHT", "TIMID", "spa/spe", ["FLAMETHROWER", "SOLARBEAM", "NASTYPLOT", "WILLOWISP"]),
        M("VENUSAUR", "LIFEORB", "CHLOROPHYLL", "MODEST", "spa/spe", ["GIGADRAIN", "SLUDGEBOMB", "WEATHERBALL", "GROWTH"]),
        M("EXEGGUTOR", "SITRUSBERRY", "CHLOROPHYLL", "MODEST", "spa/spe", ["PSYCHIC", "GIGADRAIN", "SLEEPPOWDER", "FLAMETHROWER"]),
        M("LEAVANNY", "FOCUSSASH", "CHLOROPHYLL", "JOLLY", "atk/spe", ["LEAFBLADE", "XSCISSOR", "SWORDSDANCE", "POISONJAB"]),
        M("ARCANINE", "CHOICEBAND", "INTIMIDATE", "ADAMANT", "atk/spe", ["FLAREBLITZ", "EXTREMESPEED", "WILDCHARGE", "CLOSECOMBAT"]),
        M("HELIOLISK", "CHOICESPECS", "SOLARPOWER", "TIMID", "spa/spe", ["THUNDERBOLT", "HYPERVOICE", "FOCUSBLAST", "VOLTSWITCH"])]),
    (23, "모래폭풍", "bertha", [
        M("HIPPOWDON", "SMOOTHROCK", "SANDSTREAM", "IMPISH", "hp/def", ["EARTHQUAKE", "SLACKOFF", "STEALTHROCK", "WHIRLWIND"]),
        M("EXCADRILL", "LIFEORB", "SANDRUSH", "ADAMANT", "atk/spe", ["EARTHQUAKE", "IRONHEAD", "ROCKSLIDE", "SWORDSDANCE"]),
        M("LYCANROC", "CHOICEBAND", "SANDRUSH", "JOLLY", "atk/spe", ["STONEEDGE", "ACCELEROCK", "CLOSECOMBAT", "CRUNCH"]),
        M("STOUTLAND", "SILKSCARF", "SANDRUSH", "ADAMANT", "atk/spe", ["RETURN", "CRUNCH", "PLAYROUGH", "SUPERPOWER"]),
        M("CRADILY", "LEFTOVERS", "STORMDRAIN", "CAREFUL", "hp/spd", ["ROCKSLIDE", "GIGADRAIN", "RECOVER", "TOXIC"]),
        M("AGGRON", "HARDSTONE", "ROCKHEAD", "ADAMANT", "hp/atk", ["HEADSMASH", "IRONHEAD", "EARTHQUAKE", "ICEPUNCH"])]),
    (24, "눈보라", "candice", [
        M("ABOMASNOW", "LIGHTCLAY", "SNOWWARNING", "MODEST", "hp/spa", ["BLIZZARD", "GIGADRAIN", "AURORAVEIL", "ICESHARD"]),
        M("BEARTIC", "LIFEORB", "SLUSHRUSH", "ADAMANT", "atk/spe", ["ICICLECRASH", "SUPERPOWER", "AQUAJET", "SWORDSDANCE"]),
        M("CETITAN", "SITRUSBERRY", "SLUSHRUSH", "ADAMANT", "atk/spe", ["ICICLECRASH", "EARTHQUAKE", "ICESHARD", "BELLYDRUM"]),
        M("WALREIN", "LEFTOVERS", "ICEBODY", "BOLD", "hp/def", ["SURF", "BLIZZARD", "PROTECT", "TOXIC"]),
        M("VANILLUXE", "ICYROCK", "SNOWWARNING", "MODEST", "spa/spe", ["BLIZZARD", "FLASHCANNON", "FREEZEDRY", "AURORAVEIL"]),
        M("CRYOGONAL", "NEVERMELTICE", "LEVITATE", "TIMID", "spa/spe", ["FREEZEDRY", "FLASHCANNON", "RECOVER", "HAZE"])]),
    # 관문: 트릭룸. 거는 포켓몬 둘 + 느리고 아픈 넷 (선공기 둘 - 트릭룸이 안 걸려도 맞는다). 처음 구성(텅구리 ·
    # 슈바르고 · 야도킹 · 야느와르몽)은 레벨을 맞춘 봇에게 83% 로 구역에서 가장 쉬웠다 - 11/24 sim_tower --matched
    (25, "뒤틀린 시간", "caitlin", [
        M("HATTERENE", "LIFEORB", "MAGICBOUNCE", "QUIET", "hp/spa", ["TRICKROOM", "DAZZLINGGLEAM", "PSYCHIC", "MYSTICALFIRE"]),
        M("REUNICLUS", "LEFTOVERS", "MAGICGUARD", "QUIET", "hp/spa", ["TRICKROOM", "PSYCHIC", "FOCUSBLAST", "SHADOWBALL"]),
        M("AZUMARILL", "ASSAULTVEST", "HUGEPOWER", "BRAVE", "hp/atk", ["AQUAJET", "PLAYROUGH", "LIQUIDATION", "KNOCKOFF"]),
        M("CONKELDURR", "FLAMEORB", "GUTS", "BRAVE", "hp/atk", ["DRAINPUNCH", "MACHPUNCH", "KNOCKOFF", "ICEPUNCH"]),
        M("URSALUNA", "TOXICORB", "GUTS", "BRAVE", "hp/atk", ["FACADE", "HEADLONGRUSH", "CRUNCH", "ICEPUNCH"]),
        M("CRAWDAUNT", "CHOICEBAND", "ADAPTABILITY", "BRAVE", "hp/atk", ["CRABHAMMER", "KNOCKOFF", "AQUAJET", "SUPERPOWER"])]),
    (26, "가시밭길", "olivia", [
        M("FERROTHORN", "ROCKYHELMET", "IRONBARBS", "RELAXED", "hp/def", ["SPIKES", "LEECHSEED", "POWERWHIP", "KNOCKOFF"]),
        M("ROSERADE", "BLACKSLUDGE", "NATURALCURE", "TIMID", "spa/spe", ["TOXICSPIKES", "SLUDGEBOMB", "GIGADRAIN", "SPIKES"]),
        M("DONPHAN", "LEFTOVERS", "STURDY", "IMPISH", "hp/def", ["STEALTHROCK", "EARTHQUAKE", "KNOCKOFF", "ICESHARD"]),
        M("AERODACTYL", "FOCUSSASH", "PRESSURE", "JOLLY", "atk/spe", ["STEALTHROCK", "STONEEDGE", "EARTHQUAKE", "ROAR"]),
        M("QWILFISH", "ROCKYHELMET", "INTIMIDATE", "IMPISH", "hp/def", ["TOXICSPIKES", "SPIKES", "WATERFALL", "POISONJAB"]),
        M("MANDIBUZZ", "LEFTOVERS", "OVERCOAT", "IMPISH", "hp/def", ["WHIRLWIND", "FOULPLAY", "ROOST", "KNOCKOFF"])]),
    # 해피너스 둘 - 받이로만 짠 팀
    (27, "철벽", "larry", [
        M("BLISSEY", "LEFTOVERS", "NATURALCURE", "BOLD", "hp/def", ["SEISMICTOSS", "SOFTBOILED", "TOXIC", "THUNDERWAVE"]),
        M("BLISSEY", "LEFTOVERS", "NATURALCURE", "CALM", "def/spd", ["FLAMETHROWER", "SOFTBOILED", "TOXIC", "ICEBEAM"]),
        M("QUAGSIRE", "LEFTOVERS", "UNAWARE", "RELAXED", "hp/def", ["SCALD", "EARTHQUAKE", "RECOVER", "TOXIC"]),
        M("CORVIKNIGHT", "ROCKYHELMET", "PRESSURE", "IMPISH", "hp/def", ["BRAVEBIRD", "IRONHEAD", "ROOST", "UTURN"]),
        M("DONDOZO", "LEFTOVERS", "UNAWARE", "IMPISH", "hp/def", ["LIQUIDATION", "EARTHQUAKE", "BODYPRESS", "YAWN"]),
        M("GARGANACL", "LEFTOVERS", "PURIFYINGSALT", "CAREFUL", "hp/spd", ["SALTCURE", "RECOVER", "EARTHQUAKE", "STEALTHROCK"])]),
    # 기합의띠 셋 · 구애스카프 셋
    (28, "속도전", "blue", [
        M("NINJASK", "FOCUSSASH", "SPEEDBOOST", "ADAMANT", "atk/spe", ["SWORDSDANCE", "XSCISSOR", "AERIALACE", "NIGHTSLASH"]),
        M("DUGTRIO", "FOCUSSASH", "ARENATRAP", "JOLLY", "atk/spe", ["EARTHQUAKE", "STONEEDGE", "SUCKERPUNCH", "SHADOWCLAW"]),
        M("SALAZZLE", "FOCUSSASH", "CORROSION", "TIMID", "spa/spe", ["NASTYPLOT", "FLAMETHROWER", "SLUDGEBOMB", "DRAGONPULSE"]),
        M("INFERNAPE", "CHOICESCARF", "IRONFIST", "JOLLY", "atk/spe", ["CLOSECOMBAT", "FLAREBLITZ", "UTURN", "THUNDERPUNCH"]),
        M("TALONFLAME", "CHOICESCARF", "GALEWINGS", "JOLLY", "atk/spe", ["BRAVEBIRD", "FLAREBLITZ", "UTURN", "STEELWING"]),
        M("MIENSHAO", "CHOICESCARF", "REGENERATOR", "JOLLY", "atk/spe", ["HIGHJUMPKICK", "UTURN", "KNOCKOFF", "STONEEDGE"])]),
    (29, "필드 술사", "mina", [
        M("PINCURCHIN", "TERRAINEXTENDER", "ELECTRICSURGE", "MODEST", "hp/spa", ["RISINGVOLTAGE", "SCALD", "SPIKES", "RECOVER"]),
        M("INDEEDEE", "CHOICESPECS", "PSYCHICSURGE", "TIMID", "spa/spe", ["EXPANDINGFORCE", "HYPERVOICE", "MYSTICALFIRE", "SHADOWBALL"]),
        M("RILLABOOM", "CHOICEBAND", "GRASSYSURGE", "ADAMANT", "atk/spe", ["GRASSYGLIDE", "WOODHAMMER", "KNOCKOFF", "UTURN"]),
        M("HAWLUCHA", "ELECTRICSEED", "UNBURDEN", "JOLLY", "atk/spe", ["ACROBATICS", "CLOSECOMBAT", "SWORDSDANCE", "STONEEDGE"]),
        M("ARMAROUGE", "PSYCHICSEED", "FLASHFIRE", "MODEST", "spa/spe", ["EXPANDINGFORCE", "ARMORCANNON", "AURASPHERE", "ENERGYBALL"]),
        M("GALVANTULA", "FOCUSSASH", "COMPOUNDEYES", "TIMID", "spa/spe", ["THUNDER", "BUGBUZZ", "STICKYWEB", "VOLTSWITCH"])]),
    # 층주 하인즈 (배틀돔): 대짱이 · 보만다 · 리자몽 / 메타그로스
    (30, "배틀돔", "tucker", [
        M("SWAMPERT", "LEFTOVERS", "TORRENT", "RELAXED", "hp/def", ["EARTHQUAKE", "WATERFALL", "STEALTHROCK", "ICEPUNCH"]),
        M("SALAMENCE", "LIFEORB", "INTIMIDATE", "JOLLY", "atk/spe", ["DRAGONDANCE", "DRAGONCLAW", "EARTHQUAKE", "FIREFANG"]),
        M("CHARIZARD", "HEAVYDUTYBOOTS", "BLAZE", "TIMID", "spa/spe", ["FLAMETHROWER", "AIRSLASH", "FOCUSBLAST", "ROOST"]),
        M("METAGROSS", "ASSAULTVEST", "CLEARBODY", "ADAMANT", "hp/atk", ["METEORMASH", "ZENHEADBUTT", "EARTHQUAKE", "BULLETPUNCH"]),
        M("ELECTIVIRE", "EXPERTBELT", "MOTORDRIVE", "JOLLY", "atk/spe", ["WILDCHARGE", "ICEPUNCH", "EARTHQUAKE", "CROSSCHOP"]),
        M("GARDEVOIR", "CHOICESCARF", "TRACE", "TIMID", "spa/spe", ["MOONBLAST", "PSYCHIC", "FOCUSBLAST", "THUNDERBOLT"])]),

    # ===== 4구역 정예 (Lv.90~100) - 실전 세트, 35 · 40층 메가, 40층 Z =====
    (31, "이브이 일가", "trace", [
        M("VAPOREON", "LEFTOVERS", "WATERABSORB", "BOLD", "hp/def", ["SCALD", "WISH", "PROTECT", "ICEBEAM"]),
        M("JOLTEON", "CHOICESPECS", "VOLTABSORB", "TIMID", "spa/spe", ["THUNDERBOLT", "VOLTSWITCH", "SHADOWBALL", "HYPERVOICE"]),
        M("FLAREON", "TOXICORB", "GUTS", "ADAMANT", "hp/atk", ["FLAREBLITZ", "FACADE", "SUPERPOWER", "QUICKATTACK"]),
        M("LEAFEON", "LIFEORB", "CHLOROPHYLL", "JOLLY", "atk/spe", ["SWORDSDANCE", "LEAFBLADE", "KNOCKOFF", "XSCISSOR"]),
        M("GLACEON", "NEVERMELTICE", "SNOWCLOAK", "MODEST", "hp/spa", ["ICEBEAM", "FREEZEDRY", "SHADOWBALL", "WATERPULSE"]),
        M("SYLVEON", "PIXIEPLATE", "PIXILATE", "MODEST", "hp/spa", ["HYPERVOICE", "MYSTICALFIRE", "PSYSHOCK", "CALMMIND"])]),
    (32, "600족의 방", "lance", [
        M("TYRANITAR", "SMOOTHROCK", "SANDSTREAM", "ADAMANT", "hp/atk", ["STONEEDGE", "CRUNCH", "EARTHQUAKE", "STEALTHROCK"]),
        M("HYDREIGON", "CHOICESPECS", "LEVITATE", "TIMID", "spa/spe", ["DRACOMETEOR", "DARKPULSE", "FLAMETHROWER", "FLASHCANNON"]),
        M("GOODRA", "ASSAULTVEST", "SAPSIPPER", "MODEST", "hp/spa", ["DRAGONPULSE", "FLAMETHROWER", "THUNDERBOLT", "SLUDGEBOMB"]),
        M("KOMMOO", "LUMBERRY", "BULLETPROOF", "JOLLY", "atk/spe", ["DRAGONDANCE", "CLOSECOMBAT", "DRAGONCLAW", "POISONJAB"]),
        M("BAXCALIBUR", "LOADEDDICE", "THERMALEXCHANGE", "ADAMANT", "atk/spe", ["ICICLESPEAR", "SCALESHOT", "EARTHQUAKE", "DRAGONDANCE"]),
        M("DRAGONITE", "WEAKNESSPOLICY", "MULTISCALE", "ADAMANT", "hp/atk", ["DRAGONDANCE", "DRAGONCLAW", "EARTHQUAKE", "EXTREMESPEED"])]),
    (33, "스타팅 올스타", "professor-oak", [
        M("BLAZIKEN", "LIFEORB", "SPEEDBOOST", "ADAMANT", "atk/spe", ["SWORDSDANCE", "FLAREBLITZ", "CLOSECOMBAT", "STONEEDGE"]),
        M("SCEPTILE", "MIRACLESEED", "OVERGROW", "TIMID", "spa/spe", ["LEAFSTORM", "DRAGONPULSE", "FOCUSBLAST", "GIGADRAIN"]),
        M("GRENINJA", "EXPERTBELT", "PROTEAN", "TIMID", "spa/spe", ["HYDROPUMP", "DARKPULSE", "ICEBEAM", "UTURN"]),
        M("EMPOLEON", "LEFTOVERS", "TORRENT", "MODEST", "hp/spa", ["SCALD", "FLASHCANNON", "ICEBEAM", "STEALTHROCK"]),
        M("SERPERIOR", "LEFTOVERS", "CONTRARY", "TIMID", "spa/spe", ["LEAFSTORM", "DRAGONPULSE", "GLARE", "GIGADRAIN"]),
        M("CINDERACE", "HEAVYDUTYBOOTS", "LIBERO", "JOLLY", "atk/spe", ["PYROBALL", "HIGHJUMPKICK", "UTURN", "SUCKERPUNCH"])]),
    (34, "치고 빠지기", "volkner", [
        M("ROTOM", "LEFTOVERS", "LEVITATE", "TIMID", "spa/spe", ["VOLTSWITCH", "THUNDERBOLT", "SHADOWBALL", "WILLOWISP"]),
        M("SCIZOR", "CHOICEBAND", "TECHNICIAN", "ADAMANT", "hp/atk", ["UTURN", "BULLETPUNCH", "KNOCKOFF", "SUPERPOWER"]),
        M("INCINEROAR", "HEAVYDUTYBOOTS", "INTIMIDATE", "CAREFUL", "hp/spd", ["UTURN", "FLAREBLITZ", "KNOCKOFF", "EARTHQUAKE"]),
        M("EELEKTROSS", "ASSAULTVEST", "LEVITATE", "QUIET", "hp/spa", ["VOLTSWITCH", "FLAMETHROWER", "GIGADRAIN", "UTURN"]),
        M("BARRASKEWDA", "CHOICEBAND", "SWIFTSWIM", "ADAMANT", "atk/spe", ["FLIPTURN", "LIQUIDATION", "CLOSECOMBAT", "CRUNCH"]),
        M("MEOWSCARADA", "CHOICESCARF", "PROTEAN", "JOLLY", "atk/spe", ["UTURN", "FLOWERTRICK", "KNOCKOFF", "PLAYROUGH"])]),
    (35, "메가진화의 층", "korrina", [
        M("LUCARIO", "LUCARIONITE", "INNERFOCUS", "JOLLY", "atk/spe", ["SWORDSDANCE", "CLOSECOMBAT", "METEORMASH", "BULLETPUNCH"]),
        M("MACHAMP", "ASSAULTVEST", "NOGUARD", "ADAMANT", "hp/atk", ["DYNAMICPUNCH", "STONEEDGE", "KNOCKOFF", "BULLETPUNCH"]),
        M("MEDICHAM", "LIFEORB", "PUREPOWER", "JOLLY", "atk/spe", ["HIGHJUMPKICK", "ZENHEADBUTT", "ICEPUNCH", "BULLETPUNCH"]),
        M("PANGORO", "CHOICEBAND", "IRONFIST", "ADAMANT", "hp/atk", ["KNOCKOFF", "DRAINPUNCH", "GUNKSHOT", "BULLETPUNCH"]),
        M("GALLADE", "LUMBERRY", "STEADFAST", "JOLLY", "atk/spe", ["SWORDSDANCE", "CLOSECOMBAT", "PSYCHOCUT", "NIGHTSLASH"]),
        M("SCRAFTY", "LEFTOVERS", "INTIMIDATE", "CAREFUL", "hp/spd", ["DRAGONDANCE", "DRAINPUNCH", "KNOCKOFF", "ICEPUNCH"])]),
    # 구애 도구 여섯 (머리띠 둘 · 스카프 둘 · 안경 둘)
    (36, "구애 부대", "norman", [
        M("SLAKING", "CHOICEBAND", "TRUANT", "ADAMANT", "atk/spe", ["DOUBLEEDGE", "EARTHQUAKE", "KNOCKOFF", "PLAYROUGH"]),
        M("DARMANITAN", "CHOICEBAND", "SHEERFORCE", "JOLLY", "atk/spe", ["FLAREBLITZ", "EARTHQUAKE", "ROCKSLIDE", "UTURN"]),
        M("HAXORUS", "CHOICESCARF", "MOLDBREAKER", "JOLLY", "atk/spe", ["OUTRAGE", "EARTHQUAKE", "POISONJAB", "IRONTAIL"]),
        M("CHANDELURE", "CHOICESCARF", "FLASHFIRE", "TIMID", "spa/spe", ["FIREBLAST", "SHADOWBALL", "ENERGYBALL", "PSYCHIC"]),
        M("PORYGONZ", "CHOICESPECS", "ADAPTABILITY", "TIMID", "spa/spe", ["TRIATTACK", "SHADOWBALL", "ICEBEAM", "THUNDERBOLT"]),
        M("EXPLOUD", "CHOICESPECS", "SCRAPPY", "MODEST", "hp/spa", ["BOOMBURST", "FLAMETHROWER", "FOCUSBLAST", "SURF"])]),
    # 기합의띠 여섯 (사람 팀에는 막힌 구성 - 10/29). **랭크업 · 잠재우기는 넣지 않는다**: 띠로 번 한 턴에 껍질깨기 ·
    # 나비춤 · 칼춤을 쌓게 두면 베테랑 봇 승률이 6% 인 벽이었다 (11/24 sim_tower). 여섯 다 '한 번 더 때리는' 것만으로 충분히 맵다.
    (37, "띠 부대", "guzma", [
        M("CLOYSTER", "FOCUSSASH", "SKILLLINK", "JOLLY", "atk/spe", ["ICICLESPEAR", "ROCKBLAST", "DRILLRUN", "LIQUIDATION"]),
        M("LILLIGANT", "FOCUSSASH", "CHLOROPHYLL", "TIMID", "spa/spe", ["GIGADRAIN", "ENERGYBALL", "PETALDANCE", "HYPERBEAM"]),
        M("MIMIKYU", "FOCUSSASH", "DISGUISE", "JOLLY", "atk/spe", ["PLAYROUGH", "SHADOWSNEAK", "SHADOWCLAW", "DRAINPUNCH"]),
        M("FLOATZEL", "FOCUSSASH", "SWIFTSWIM", "JOLLY", "atk/spe", ["LIQUIDATION", "ICEPUNCH", "CRUNCH", "AQUAJET"]),
        M("ZOROARK", "FOCUSSASH", "ILLUSION", "TIMID", "spa/spe", ["DARKPULSE", "FLAMETHROWER", "SLUDGEBOMB", "FOCUSBLAST"]),
        M("ARCHEOPS", "FOCUSSASH", "DEFEATIST", "JOLLY", "atk/spe", ["ACROBATICS", "STONEEDGE", "EARTHQUAKE", "UTURN"])]),
    # 재생력 다섯 - 야도란 둘 · 뽀록나 둘 (검은진흙 셋)
    (38, "재생력 순환", "siebold", [
        M("SLOWBRO", "ROCKYHELMET", "REGENERATOR", "BOLD", "hp/def", ["SCALD", "SLACKOFF", "PSYCHIC", "THUNDERWAVE"]),
        M("SLOWBRO", "HEAVYDUTYBOOTS", "REGENERATOR", "RELAXED", "hp/def", ["SCALD", "SLACKOFF", "ICEBEAM", "TOXIC"]),
        M("AMOONGUSS", "BLACKSLUDGE", "REGENERATOR", "CALM", "hp/spd", ["SPORE", "GIGADRAIN", "SLUDGEBOMB", "CLEARSMOG"]),
        M("AMOONGUSS", "BLACKSLUDGE", "REGENERATOR", "BOLD", "hp/def", ["SPORE", "GIGADRAIN", "FOULPLAY", "SYNTHESIS"]),
        M("TOXAPEX", "BLACKSLUDGE", "REGENERATOR", "BOLD", "hp/def", ["SCALD", "RECOVER", "TOXIC", "HAZE"]),
        M("ALOMOMOLA", "LEFTOVERS", "REGENERATOR", "IMPISH", "hp/def", ["SCALD", "WISH", "PROTECT", "KNOCKOFF"])]),
    (39, "쌍둥이 에이스", "iris", [
        M("GARCHOMP", "ROCKYHELMET", "ROUGHSKIN", "IMPISH", "hp/def", ["EARTHQUAKE", "DRAGONCLAW", "STEALTHROCK", "FIREFANG"]),
        M("GARCHOMP", "SOFTSAND", "ROUGHSKIN", "JOLLY", "atk/spe", ["EARTHQUAKE", "DRAGONCLAW", "FIREFANG", "POISONJAB"]),
        M("GENGAR", "SPELLTAG", "CURSEDBODY", "TIMID", "spa/spe", ["SHADOWBALL", "SLUDGEBOMB", "FOCUSBLAST", "THUNDERBOLT"]),
        M("GENGAR", "BLACKSLUDGE", "CURSEDBODY", "TIMID", "spa/spe", ["SHADOWBALL", "SLUDGEWAVE", "DAZZLINGGLEAM", "WILLOWISP"]),
        M("BISHARP", "EVIOLITE", "DEFIANT", "ADAMANT", "hp/atk", ["NIGHTSLASH", "IRONHEAD", "SUCKERPUNCH", "LOWKICK"]),
        M("BISHARP", "EVIOLITE", "DEFIANT", "ADAMANT", "hp/atk", ["NIGHTSLASH", "IRONHEAD", "SUCKERPUNCH", "STEALTHROCK"])]),
    # 층주 리라 (살롱 메이든): 후딘 · 앤테이 · 잠만보 / 라이코 · 라티오스. 메가 + Z
    (40, "살롱 메이든", "anabel", [
        M("ALAKAZAM", "ALAKAZITE", "MAGICGUARD", "TIMID", "spa/spe", ["PSYCHIC", "SHADOWBALL", "FOCUSBLAST", "CALMMIND"]),
        M("ENTEI", "CHOICEBAND", "PRESSURE", "ADAMANT", "atk/spe", ["SACREDFIRE", "EXTREMESPEED", "STONEEDGE", "STOMPINGTANTRUM"]),
        M("SNORLAX", "LEFTOVERS", "THICKFAT", "CAREFUL", "hp/spd", ["CURSE", "BODYSLAM", "EARTHQUAKE", "REST"]),
        M("RAIKOU", "ELECTRIUMZ", "PRESSURE", "TIMID", "spa/spe", ["THUNDERBOLT", "CALMMIND", "SHADOWBALL", "SCALD"]),
        M("LATIOS", "SOULDEW", "LEVITATE", "TIMID", "spa/spe", ["DRACOMETEOR", "PSYSHOCK", "SURF", "RECOVER"]),
        M("WEAVILE", "FOCUSSASH", "PRESSURE", "JOLLY", "atk/spe", ["SWORDSDANCE", "ICICLECRASH", "KNOCKOFF", "ICESHARD"])]),

    # ===== 5구역 전설 (Lv.100) - 길드전 AI, 메가 · Z, 45층부터 테라스탈 =====
    # 차례는 tools/sim_tower.py 로 잰 승률 순이다 (11/24). 처음 적은 차례에서는 울트라비스트 · 패러독스가 43 · 44층에서
    # 벽(베테랑 봇 0 · 6%)이고 그 위의 테라스탈 · 무한의 용이 쉬웠다 (81 · 69%).
    # 칸토의 새 셋을 둘씩 (통굽부츠 셋)
    (41, "전설의 새", "skyla", [
        M("ARTICUNO", "HEAVYDUTYBOOTS", "PRESSURE", "TIMID", "spa/spe", ["FREEZEDRY", "HURRICANE", "ROOST", "HAZE"]),
        M("ARTICUNO", "LEFTOVERS", "PRESSURE", "BOLD", "hp/def", ["ICEBEAM", "HURRICANE", "ROOST", "UTURN"]),
        M("ZAPDOS", "HEAVYDUTYBOOTS", "STATIC", "TIMID", "spa/spe", ["THUNDERBOLT", "HURRICANE", "ROOST", "VOLTSWITCH"]),
        M("ZAPDOS", "LIFEORB", "STATIC", "TIMID", "spa/spe", ["THUNDERBOLT", "HEATWAVE", "HURRICANE", "UTURN"]),
        M("MOLTRES", "HEAVYDUTYBOOTS", "FLAMEBODY", "TIMID", "spa/spe", ["FLAMETHROWER", "HURRICANE", "ROOST", "WILLOWISP"]),
        M("MOLTRES", "CHOICESCARF", "FLAMEBODY", "TIMID", "spa/spe", ["FIREBLAST", "HURRICANE", "SCORCHINGSANDS", "UTURN"])]),
    # 라티오스 둘 · 라티아스 둘 (마음의물방울 둘)
    (42, "무한의 용", "zinnia", [
        M("LATIOS", "LATIOSITE", "LEVITATE", "TIMID", "spa/spe", ["DRACOMETEOR", "PSYSHOCK", "AURASPHERE", "RECOVER"]),
        M("LATIOS", "SOULDEW", "LEVITATE", "TIMID", "spa/spe", ["DRAGONPULSE", "PSYCHIC", "THUNDERBOLT", "CALMMIND"]),
        M("LATIAS", "SOULDEW", "LEVITATE", "TIMID", "hp/spe", ["CALMMIND", "DRAGONPULSE", "PSYSHOCK", "RECOVER"]),
        M("LATIAS", "LEFTOVERS", "LEVITATE", "BOLD", "hp/def", ["MISTBALL", "AURASPHERE", "RECOVER", "THUNDERWAVE"]),
        M("RAYQUAZA", "LIFEORB", "AIRLOCK", "JOLLY", "atk/spe", ["OUTRAGE", "EXTREMESPEED", "EARTHQUAKE", "SWORDSDANCE"]),
        M("ZYGARDE", "LEFTOVERS", "AURABREAK", "ADAMANT", "hp/atk", ["THOUSANDARROWS", "DRAGONDANCE", "EXTREMESPEED", "GLARE"])]),
    (43, "성도의 개와 호연의 거인", "eusine", [
        M("RAIKOU", "LIFEORB", "PRESSURE", "TIMID", "spa/spe", ["THUNDERBOLT", "VOLTSWITCH", "SHADOWBALL", "EXTRASENSORY"]),
        M("ENTEI", "HEAVYDUTYBOOTS", "PRESSURE", "JOLLY", "atk/spe", ["SACREDFIRE", "EXTREMESPEED", "STONEEDGE", "FLAREBLITZ"]),
        M("SUICUNE", "LEFTOVERS", "PRESSURE", "BOLD", "hp/def", ["SCALD", "CALMMIND", "ICEBEAM", "REST"]),
        M("REGIROCK", "LEFTOVERS", "CLEARBODY", "IMPISH", "hp/def", ["STONEEDGE", "EARTHQUAKE", "BODYPRESS", "STEALTHROCK"]),
        M("REGICE", "ASSAULTVEST", "CLEARBODY", "MODEST", "hp/spa", ["ICEBEAM", "THUNDERBOLT", "FOCUSBLAST", "FLASHCANNON"]),
        M("REGISTEEL", "LEFTOVERS", "CLEARBODY", "CAREFUL", "hp/spd", ["IRONHEAD", "BODYPRESS", "CURSE", "REST"])]),
    (44, "섬의 수호신", "hapu", [
        M("TAPUKOKO", "LIFEORB", "ELECTRICSURGE", "TIMID", "spa/spe", ["THUNDERBOLT", "DAZZLINGGLEAM", "VOLTSWITCH", "ROOST"]),
        M("TAPULELE", "CHOICESPECS", "PSYCHICSURGE", "TIMID", "spa/spe", ["PSYCHIC", "MOONBLAST", "FOCUSBLAST", "SHADOWBALL"]),
        M("TAPUBULU", "CHOICEBAND", "GRASSYSURGE", "ADAMANT", "hp/atk", ["WOODHAMMER", "HORNLEECH", "SUPERPOWER", "STONEEDGE"]),
        M("TAPUFINI", "LEFTOVERS", "MISTYSURGE", "BOLD", "hp/def", ["MOONBLAST", "SCALD", "CALMMIND", "TAUNT"]),
        M("PRIMARINA", "PRIMARIUMZ", "TORRENT", "MODEST", "hp/spa", ["SPARKLINGARIA", "MOONBLAST", "PSYCHIC", "ENERGYBALL"]),
        M("DECIDUEYE", "SPELLTAG", "LONGREACH", "ADAMANT", "atk/spe", ["SPIRITSHACKLE", "LEAFBLADE", "SWORDSDANCE", "SHADOWSNEAK"])]),
    # 관문: 테라피스 셋 (한 판에 한 번이지만 누가 할지는 AI 가 고른다)
    (45, "테라스탈의 층", "geeta", [
        M("GLIMMORA", "FOCUSSASH", "TOXICDEBRIS", "TIMID", "spa/spe", ["POWERGEM", "SLUDGEWAVE", "EARTHPOWER", "STEALTHROCK"]),
        M("ESPATHRA", "FAIRYTERASHARD", "SPEEDBOOST", "TIMID", "spa/spe", ["LUMINACRASH", "DAZZLINGGLEAM", "CALMMIND", "ROOST"]),
        M("SKELEDIRGE", "WATERTERASHARD", "UNAWARE", "BOLD", "hp/def", ["TORCHSONG", "SHADOWBALL", "SLACKOFF", "WILLOWISP"]),
        M("ANNIHILAPE", "LEFTOVERS", "DEFIANT", "CAREFUL", "hp/spd", ["BULKUP", "DRAINPUNCH", "RAGEFIST", "TAUNT"]),
        M("GHOLDENGO", "CHOICESPECS", "GOODASGOLD", "TIMID", "spa/spe", ["MAKEITRAIN", "SHADOWBALL", "FOCUSBLAST", "THUNDERBOLT"]),
        M("KINGAMBIT", "DARKTERASHARD", "SUPREMEOVERLORD", "ADAMANT", "hp/atk", ["SWORDSDANCE", "KOWTOWCLEAVE", "SUCKERPUNCH", "IRONHEAD"])]),
    (46, "울트라비스트", "lusamine", [
        M("NIHILEGO", "FOCUSSASH", "BEASTBOOST", "TIMID", "spa/spe", ["POWERGEM", "SLUDGEWAVE", "THUNDERBOLT", "STEALTHROCK"]),
        M("BUZZWOLE", "LEFTOVERS", "BEASTBOOST", "ADAMANT", "hp/atk", ["DRAINPUNCH", "LEECHLIFE", "ICEPUNCH", "EARTHQUAKE"]),
        M("XURKITREE", "MAGNET", "BEASTBOOST", "TIMID", "spa/spe", ["THUNDERBOLT", "ENERGYBALL", "DAZZLINGGLEAM", "VOLTSWITCH"]),
        M("CELESTEELA", "ASSAULTVEST", "BEASTBOOST", "SASSY", "hp/spd", ["HEAVYSLAM", "FLAMETHROWER", "AIRSLASH", "EARTHQUAKE"]),
        M("GUZZLORD", "LEFTOVERS", "BEASTBOOST", "ADAMANT", "hp/atk", ["KNOCKOFF", "DRAGONCLAW", "EARTHQUAKE", "HEAVYSLAM"]),
        M("STAKATAKA", "ROCKYHELMET", "BEASTBOOST", "BRAVE", "hp/atk", ["GYROBALL", "STONEEDGE", "EARTHQUAKE", "BODYPRESS"])]),
    (47, "네 재앙", "raifort", [
        M("WOCHIEN", "LEFTOVERS", "TABLETSOFRUIN", "BOLD", "hp/def", ["GIGADRAIN", "FOULPLAY", "KNOCKOFF", "BODYPRESS"]),
        M("CHIENPAO", "LEFTOVERS", "SWORDOFRUIN", "IMPISH", "hp/def", ["ICICLECRASH", "CRUNCH", "SACREDSWORD", "ICESHARD"]),
        M("TINGLU", "LEFTOVERS", "VESSELOFRUIN", "IMPISH", "hp/spd", ["EARTHQUAKE", "RUINATION", "STONEEDGE", "STEALTHROCK"]),
        M("CHIYU", "WISEGLASSES", "BEADSOFRUIN", "TIMID", "spa/spe", ["FLAMETHROWER", "DARKPULSE", "PSYCHIC", "WILLOWISP"]),
        M("CERULEDGE", "LIFEORB", "FLASHFIRE", "JOLLY", "atk/spe", ["BITTERBLADE", "SHADOWSNEAK", "POLTERGEIST", "CLOSECOMBAT"]),
        M("QUAQUAVAL", "SITRUSBERRY", "TORRENT", "JOLLY", "atk/spe", ["LIQUIDATION", "CLOSECOMBAT", "ICESPINNER", "UTURN"])]),
    # 부스트에너지 여섯. 랭크업은 뺐다 - 부스트에너지로 빨라진 채 쌓으면 봇 승률이 6% 였다 (11/24)
    (48, "패러독스", "arven", [
        M("GREATTUSK", "BOOSTERENERGY", "PROTOSYNTHESIS", "IMPISH", "hp/def", ["HEADLONGRUSH", "CLOSECOMBAT", "ICESPINNER", "KNOCKOFF"]),
        M("BRUTEBONNET", "BOOSTERENERGY", "PROTOSYNTHESIS", "ADAMANT", "hp/atk", ["SEEDBOMB", "CRUNCH", "SUCKERPUNCH", "CLOSECOMBAT"]),
        M("SANDYSHOCKS", "BOOSTERENERGY", "PROTOSYNTHESIS", "TIMID", "spa/spe", ["THUNDERBOLT", "EARTHPOWER", "VOLTSWITCH", "FLASHCANNON"]),
        M("IRONVALIANT", "BOOSTERENERGY", "QUARKDRIVE", "JOLLY", "hp/spe", ["CLOSECOMBAT", "SPIRITBREAK", "KNOCKOFF", "ICEPUNCH"]),
        M("IRONTREADS", "BOOSTERENERGY", "QUARKDRIVE", "IMPISH", "hp/def", ["EARTHQUAKE", "IRONHEAD", "KNOCKOFF", "ICESPINNER"]),
        M("IRONHANDS", "BOOSTERENERGY", "QUARKDRIVE", "ADAMANT", "hp/atk", ["DRAINPUNCH", "THUNDERPUNCH", "ICEPUNCH", "EARTHQUAKE"])]),
    (49, "시간과 공간", "cyrus", [
        M("DIALGA", "ADAMANTORB", "PRESSURE", "MODEST", "hp/spa", ["DRACOMETEOR", "FLASHCANNON", "FIREBLAST", "EARTHPOWER"]),
        M("PALKIA", "DRAGONIUMZ", "PRESSURE", "TIMID", "spa/spe", ["SPACIALREND", "HYDROPUMP", "FIREBLAST", "THUNDER"]),
        M("GIRATINA", "LEFTOVERS", "PRESSURE", "BOLD", "hp/def", ["SHADOWBALL", "DRAGONPULSE", "WILLOWISP", "CALMMIND"]),
        M("RESHIRAM", "CHOICESPECS", "TURBOBLAZE", "TIMID", "spa/spe", ["BLUEFLARE", "DRACOMETEOR", "EARTHPOWER", "FOCUSBLAST"]),
        M("ZEKROM", "CHOICEBAND", "TERAVOLT", "ADAMANT", "atk/spe", ["BOLTSTRIKE", "OUTRAGE", "DRAGONCLAW", "STONEEDGE"]),
        M("KYUREM", "ICETERASHARD", "PRESSURE", "TIMID", "spa/spe", ["ICEBEAM", "FREEZEDRY", "EARTHPOWER", "DRAGONPULSE"])]),
    # 층주 종수 (타워타이쿤): 밀로틱 · 거대코뿌리 · 망나뇽 / 히드런 · 크레세리아 · 레지기가스. 메가 + Z + 테라스탈
    (50, "타워타이쿤", "palmer", [
        M("MILOTIC", "LEFTOVERS", "MARVELSCALE", "MODEST", "hp/spa", ["HYDROPUMP", "ICEBEAM", "RECOVER", "SCALD"]),
        M("RHYPERIOR", "GROUNDIUMZ", "SOLIDROCK", "ADAMANT", "hp/atk", ["EARTHQUAKE", "STONEEDGE", "MEGAHORN", "ICEPUNCH"]),
        M("DRAGONITE", "NORMALTERASHARD", "MULTISCALE", "ADAMANT", "atk/spe", ["DRAGONDANCE", "EXTREMESPEED", "EARTHQUAKE", "ROOST"]),
        M("HEATRAN", "HEATRANITE", "FLASHFIRE", "TIMID", "spa/spe", ["MAGMASTORM", "EARTHPOWER", "FLASHCANNON", "STEALTHROCK"]),
        M("CRESSELIA", "LEFTOVERS", "LEVITATE", "BOLD", "hp/def", ["CALMMIND", "MOONBLAST", "PSYSHOCK", "MOONLIGHT"]),
        M("REGIGIGAS", "LEFTOVERS", "SLOWSTART", "ADAMANT", "hp/atk", ["BODYSLAM", "KNOCKOFF", "EARTHQUAKE", "THUNDERWAVE"])]),
]


# ---------------------------------------------------------------- 자료
_REF = None


def ref():
    """(원본 도감, 게임 도감, 관장용 도감, 도구, 관장 자료). 한 번만 읽는다."""
    global _REF
    if _REF is None:
        with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
            raw = json.load(f)
        with open(os.path.join(DATA, "items.json"), encoding="utf-8") as f:
            items = dict(json.load(f)["items"])
        with open(os.path.join(DATA, "gyms.json"), encoding="utf-8") as f:
            gyms = dict((t["id"], t) for t in json.load(f)["trainers"])
        _REF = (raw, P.Pokedex(raw), G.Dex(raw), items, gyms)
    return _REF


def parse_evs(spec):
    """"atk/spe" -> 둘에 252씩, 남는 6은 HP (HP 가 그 둘 안에 있으면 방어 쪽). dict 면 그대로."""
    evs = dict((s, 0) for s in P.STATS)
    if isinstance(spec, dict):
        evs.update(spec)
        return evs
    a, b = spec.split("/")
    evs[a] = evs[b] = 252
    rest = "hp" if "hp" not in (a, b) else ("spd" if "def" in (a, b) else "def")
    evs[rest] = 6
    return evs


def gender_of(sp):
    r = sp.get("femaleRatio")
    if r is None or r < 0:
        return "N"
    return "F" if r >= 0.5 else "M"


def stones_of(species):
    """그 종이 쥐면 메가진화하는 메가스톤들."""
    return set(m.get("megaStone") for m in ref()[0]["megas"] if m.get("megaOf") == species and m.get("megaStone"))


def fill(spec, n):
    """명세 한 줄 -> tower.json 의 포켓몬 (trainer_battle.trainer_mon 이 먹는 꼴)."""
    _raw, pdex, gdex, _items, _gyms = ref()
    sp = pdex.get(spec["species"])
    if not sp:
        raise LookupError("%d층: 도감에 없는 종 %s%s" % (n, spec["species"], near(spec["species"], pdex.by_internal)))
    level, z = level_for(n), zone_of(n)
    moves = list(spec["moves"]) if spec["moves"] else G.moveset(gdex, sp, level, None)
    known = [k for k in moves if k in gdex.moves]
    evs, nature = G.spread(gdex, sp, known, 1.0)
    if z == 0:
        evs, nature = dict((s, 0) for s in P.STATS), "HARDY"           # 입문 구역: 노력치 0 · 무보정
    elif z == 1 and not spec["evs"]:
        main = "atk" if evs["atk"] == 252 else "spa" if evs["spa"] == 252 else "hp"
        evs = dict((s, 252 if s == main else 0) for s in P.STATS)      # 수련 구역: 주 능력만
    if z >= 1:
        if spec["evs"]:
            evs = parse_evs(spec["evs"])
        nature = spec["nature"] or nature
    return {"species": spec["species"], "level": level, "iv": 31, "evs": evs, "nature": nature,
            "ability": spec["ability"] or G.ability_of(gdex, sp, None), "moves": moves,
            "held": spec["held"], "gender": gender_of(sp)}


def flags(team):
    """엔진에 넘길 깃발 (머리말). 팀이 쥔 도구로 정해진다."""
    items = ref()[3]
    mega = any(m["held"] and m["held"] in stones_of(m["species"]) for m in team)
    return {"noMega": not mega, "keystone": mega,
            "zring": any((items.get(m["held"]) or {}).get("cat") == "zcrystal" for m in team),
            "orb": any(str(m["held"] or "").endswith("TERASHARD") for m in team)}


def build():
    gyms = ref()[4]
    floors = []
    for n, name, who, mons in FLOORS:
        t = gyms.get(who)
        if not t:
            raise LookupError("%d층: 관장 자료에 없는 인물 %s%s" % (n, who, near(who, gyms)))
        team = [fill(m, n) for m in mons]
        trainer = {"id": "tower-%d" % n, "name": t["name"], "role": t["role"], "sprite": t["sprite"],
                   "level": level_for(n), "ai": ai_for(n), "team": team}
        trainer.update(flags(team))
        floors.append({"floor": n, "name": name, "kind": kind_for(n), "trainer": trainer, "reward": reward_for(n)})
    body = json.dumps(floors, ensure_ascii=False, sort_keys=True)
    return {"version": VERSION, "digest": hashlib.sha256(body.encode("utf-8")).hexdigest()[:16], "floors": floors}


# ---------------------------------------------------------------- 검사
def near(word, pool):
    got = difflib.get_close_matches(str(word), [str(k) for k in pool], 3, 0.6)
    return " (혹시 %s?)" % " · ".join(got) if got else ""


def check(data):
    """자료가 약속을 지키는가. 어긴 것마다 글 한 줄 - 빈 목록이면 통과."""
    raw, pdex, gdex, items, _gyms = ref()
    bad = []
    floors = data.get("floors") or []
    if [f.get("floor") for f in floors] != list(range(1, TOTAL + 1)):
        bad.append("층이 1~%d 로 빠짐없이 있지 않다" % TOTAL)
    last = 0
    for f in floors:
        n, t = f["floor"], f["trainer"]
        team = t["team"]
        if len(team) != size_for(n):
            bad.append("%d층: %d마리여야 하는데 %d마리" % (n, size_for(n), len(team)))
        if f["kind"] != kind_for(n) or t["ai"] != ai_for(n) or t["level"] != level_for(n):
            bad.append("%d층: 종류 · AI · 레벨이 층 번호와 안 맞는다" % n)
        if n in BOSSES and t["sprite"] != ref()[4][BOSSES[n]]["sprite"]:
            bad.append("%d층: 층주는 %s 이어야 한다" % (n, BOSSES[n]))
        if dict((k, t.get(k)) for k in ("noMega", "keystone", "zring", "orb")) != flags(team):
            bad.append("%d층: 깃발이 팀의 도구와 안 맞는다" % n)
        if sum(1 for m in team if m["held"] and m["held"] in stones_of(m["species"])) > 1:
            bad.append("%d층: 메가스톤을 쥔 포켓몬이 둘 이상 (한 판에 한 번뿐이다)" % n)
        if t["level"] < last:
            bad.append("%d층: 레벨이 아래층보다 낮다" % n)
        last = t["level"]
        if zone_of(n) == 0 and f["kind"] == "normal" and any(m["held"] for m in team):
            bad.append("%d층: 입문 구역의 보통 층은 도구가 없다" % n)
        for m in team:
            who = "%d층 %s" % (n, m["species"])
            sp = pdex.get(m["species"])
            if not sp:
                bad.append("%s: 도감에 없는 종%s" % (who, near(m["species"], pdex.by_internal)))
                continue
            if m["level"] != level_for(n) or m.get("iv") != 31 or m.get("boost"):
                bad.append("%s: 레벨 · 개체값 · 배율" % who)
            mv = m["moves"]
            if not 1 <= len(mv) <= 4 or len(set(mv)) != len(mv):
                bad.append("%s: 기술은 겹치지 않게 1~4개 %s" % (who, mv))
            for k in mv:
                md = gdex.moves.get(k)
                if not md:
                    bad.append("%s: 도감에 없는 기술 %s%s" % (who, k, near(k, gdex.moves)))
                elif k in G.SELF_KO or k in G.AI_UNUSABLE:
                    bad.append("%s: AI 가 쓰면 안 되는 기술 %s" % (who, k))
                elif not TB.works(md):
                    bad.append("%s: 이 엔진에서 아무 일도 안 하는 기술 %s" % (who, k))
            if not any(MC.attacks(gdex.moves[k]) for k in mv if k in gdex.moves):
                bad.append("%s: 때리는 기술이 없다" % who)
            allowed = list(sp.get("abil") or []) + ([sp["hidden"]] if sp.get("hidden") else [])
            if m["ability"] not in allowed:
                bad.append("%s: 그 종의 특성이 아니다 %s (가능: %s)" % (who, m["ability"], " · ".join(allowed)))
            if m["held"] and m["held"] not in items:
                bad.append("%s: 없는 도구 %s%s" % (who, m["held"], near(m["held"], items)))
            if (items.get(m["held"]) or {}).get("cat") == "megastone" and m["held"] not in stones_of(m["species"]):
                bad.append("%s: 제 메가스톤이 아니다 %s" % (who, m["held"]))
            evs = m["evs"]
            if set(evs) != set(P.STATS) or any(not 0 <= v <= P.EV_MAX for v in evs.values()) \
                    or sum(evs.values()) > P.EV_TOTAL_MAX:
                bad.append("%s: 노력치 %s" % (who, evs))
            if m["nature"] not in P.NATURE_BY_NAME:
                bad.append("%s: 없는 성격 %s" % (who, m["nature"]))
        r = f["reward"]
        if r != reward_for(n):
            bad.append("%d층: 보상이 표와 다르다" % n)
        for iid, cnt in r["items"]:
            if iid not in items or cnt < 1:
                bad.append("%d층: 보상 도구 %s x%s" % (n, iid, cnt))
    return bad


def _text(data):
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="쓰지 않고, 파일이 명세와 같은지만 본다")
    a = ap.parse_args()
    data = build()
    bad = check(data)
    for line in bad:
        print("  " + line)
    if bad:
        print("%d곳이 어긋났다 - 쓰지 않았다." % len(bad))
        return 1
    if a.check:
        with open(OUT_PATH, encoding="utf-8") as f:
            same = f.read() == _text(data)
        print("tower.json 은 명세와 %s." % ("같다" if same else "다르다 - python tools/build_tower.py 로 다시 낸다"))
        return 0 if same else 1
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(_text(data))
    species = set(m["species"] for fl in data["floors"] for m in fl["trainer"]["team"])
    print("%d층 · %d종 -> %s" % (len(data["floors"]), len(species), os.path.relpath(OUT_PATH, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
