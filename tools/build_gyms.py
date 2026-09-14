# -*- coding: utf-8 -*-
"""관장 도전 — 시·군·구 256곳의 트레이너와 팀을 만든다.

    python tools/build_gyms.py            # server/data/gyms.json
    python tools/build_gyms.py --report roster.md

## 규칙 (사용자가 정했다)

  · 256곳에 한 명씩. 겹치지 않는다.
  · 레벨은 20 ~ 100, 5 단위 17단계. **팀 여섯의 평균이 그 레벨**이다.
  · 모두 여섯 마리.
  · 유명한 트레이너(관장, 난천 같은)는 **트레이드마크 포켓몬**을 넣는다.

## 어디서 가져오나

PokeAPI 에는 트레이너 자료가 없다. 불바피디아의 인물 문서에서 **본편
게임의 파티 틀**({{Party}} + {{Pokémon}})을 읽는다. 스타디움·마스터즈
같은 외전은 버린다. 받은 원문은 tools/_cache/bulbapedia/pages.json 에
있다(없으면 --fetch 로 다시 받는다).

한국어 이름도 같은 문서의 이름 표에서 읽는다(웅, 난천, 모야모).

## 팀을 어떻게 고르나

1. 그 인물이 본편에서 쓴 포켓몬을 **모든 파티에 걸쳐** 센다.
2. 가장 강한 파티의 에이스(가장 높은 레벨, 같으면 마지막에 나온 것)를
   **반드시 넣고 맨 뒤에 둔다.** 난천의 한카리아스, 웅의 롱스톤.
3. 같은 진화 계열은 하나만(꼬마돌·딱구리·딱구리를 다 넣지 않는다).
4. 여섯이 안 차면 **그 사람의 전문 타입**으로 채운다. 데뷔 세대의 종을
   먼저 쓴다 - 웅은 1세대 바위 타입으로 채운다.
5. 레벨에 맞지 않는 진화형은 낮춘다. Lv.20 에 한카리아스(48에 진화)는
   딥상어동으로 나온다.

기술은 원작 파티에 적힌 것을 우선 쓰고, 도감에 없거나 모자라면 그
레벨까지 배우는 기술 중 위력이 좋은 것으로 채운다. 자폭·대폭발 같은
자기를 쓰러뜨리는 기술은 넣지 않는다 - AI 가 쓰면 스스로 한 마리를
날린다.

## 레벨을 어떻게 나누나

인물마다 '원작에서 얼마나 강했나' 를 잰다. 관장은 **첫 체육관 전투**의
평균 레벨(재대결은 빼고), 챔피언·사천왕은 가장 강한 본편 파티, 라이벌은
여러 번 싸우므로 가운데 값. 여기에 역할 가산점을 더해 줄을 세우고
17단계에 고르게(15~16명씩) 나눈다. 몇 명은 손으로 박는다(레드·난천은 100).

## 어디에 두나

손으로 박은 곳이 먼저다(평창=스노보더 그루샤, 대전 중구=빵집 단풍,
인천 영종구=파일럿 풍란...). 이유를 PIN 에 같이 적었다. 나머지는 전문
타입과 지역의 특징(바다에 닿는가, 섬, 구/군)을 보고 정한다. 한 시·도에
높은 레벨만 몰리지 않게 높은 레벨부터 시·도마다 고르게 채운다.
"""
import argparse
import collections
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from common import held as H          # noqa: E402
from common import pokelogic as P     # noqa: E402

CACHE = os.path.join(ROOT, "tools", "_cache", "bulbapedia")
DEX_PATH = os.path.join(ROOT, "server", "data", "pokedex.json")
MAP_PATH = os.path.join(ROOT, "server", "data", "korea_map.json")
OUT_PATH = os.path.join(ROOT, "server", "data", "gyms.json")

TIERS = list(range(20, 101, 5))                      # 17단계
TEAM = 6
OFFSETS = [-3, -2, -1, 1, 2, 3]                       # 합이 0 -> 평균이 정확히 그 레벨
SELF_KO = {"SELFDESTRUCT", "EXPLOSION", "MEMENTO", "FINALGAMBIT", "HEALINGWISH",
           "LUNARDANCE", "MISTYEXPLOSION", "DESTINYBOND", "PERISHSONG"}
SOURCE = "Bulbapedia (CC BY-NC-SA 2.5) — 본편 게임의 트레이너 파티"

# ---------------------------------------------------------------- 사람
# 역할 이름. 불바피디아 분류로 먼저 정하고, 여기 적힌 사람은 이걸 쓴다.
# **챔피언은 분류가 아니라 이 명단으로 정한다.** 불바피디아의 Champions
# 분류에는 외전(마스터즈)에서 챔피언을 했던 사람까지 들어 있어서, 호연
# 사천왕 넷이 전부 챔피언으로 붙었다.
CHAMPIONS = {"Red (game)", "Blue (game)", "Lance", "Steven Stone", "Wallace", "Cynthia",
             "Alder", "Iris", "Diantha", "Professor Kukui", "Leon", "Geeta", "Nemona",
             "Kieran", "Ash Ketchum"}
ROLE_BY_CAT = [
    ("Elite Four Trainers", "사천왕"), ("Gym Leaders", "관장"),
    ("Villainous team leaders", "조직 보스"), ("Frontier Brains", "프런티어브레인"),
    ("Island Kahunas", "섬킹"), ("Trial Captains", "캡틴"), ("Team Star", "스타단"),
    ("Rival characters", "라이벌"), ("Wardens", "히스이 트레이너"),
    ("Legends: Arceus characters", "히스이 트레이너"),
]
ROLE = {
    "Giovanni": "로켓단 보스", "Maxie": "마그마단 리더", "Archie": "아쿠아단 리더",
    "Cyrus": "갤럭시단 보스", "Ghetsis": "플라즈마단", "N": "플라즈마단 왕",
    "Colress": "플라즈마단 과학자", "Lysandre": "플레어단 보스", "Guzma": "스컬단 보스",
    "Lusamine": "에테르재단 대표", "Rose": "매크로코스모스 회장", "Oleana": "매크로코스모스 비서",
    "Archer": "로켓단 간부", "Ariana": "로켓단 간부", "Proton": "로켓단 간부", "Petrel": "로켓단 간부",
    "Tabitha": "마그마단 간부", "Courtney": "마그마단 간부", "Matt": "아쿠아단 간부",
    "Shelly": "아쿠아단 간부", "Mars": "갤럭시단 간부", "Jupiter": "갤럭시단 간부",
    "Saturn": "갤럭시단 간부", "Zinzolin": "플라즈마단", "Xerosic": "플레어단 간부",
    "Plumeria": "스컬단 간부", "Faba": "에테르재단 지부장", "Sordward": "갈라 왕가",
    "Shielbert": "갈라 왕가", "Penny": "스타단", "Emmet": "서브웨이마스터",
    "Ingo": "서브웨이마스터", "Benga": "블랙타워", "Palmer": "타워타이쿤",
    "Dahlia": "아케이드스타", "Darach": "캐슬발레", "Hala": "섬킹", "Nanu": "섬킹",
    "Olivia": "섬퀸", "Hapu": "섬퀸", "Professor Kukui": "박사 · 챔피언",
    "Professor Sycamore": "박사", "Clavell": "아카데미 교장", "Tyme": "관장 · 교사",
    "Dendra": "아카데미 교사", "Jacq": "아카데미 교사", "Miriam": "아카데미 교사",
    "Raifort": "아카데미 교사", "Salvatore": "아카데미 교사", "Kieran": "블루베리 챔피언",
    "Carmine": "블루베리 아카데미", "Perrin": "북신의 고장", "AZ": "칼로스의 옛 왕",
    "Zinnia": "용의 전승자", "Emma": "미르시티 트레이너", "Dexio": "플라타느 조수",
    "Sina": "플라타느 조수", "Ryuki": "로켓단 레인보우", "Mustard": "전 챔피언",
    "Peony": "전 챔피언", "Klara": "도장 제자", "Avery": "도장 제자", "Eusine": "수호자",
    "Trace (game)": "라이벌", "Cheren": "관장 · 라이벌", "Bede": "관장 · 라이벌",
    "Marnie": "관장 · 라이벌", "Hop": "라이벌", "Blue (game)": "챔피언 · 라이벌",
    "Red (game)": "전설의 트레이너", "Wally": "라이벌", "Taunie": "라이벌",
    "Brendan (game)": "라이벌", "May (game)": "라이벌", "Dawn (game)": "라이벌",
    "Lucas (game)": "라이벌", "Serena (game)": "라이벌", "Calem (game)": "라이벌",
    "Urbain": "라이벌", "Nate (game)": "주인공", "Rosa (game)": "주인공",
    "Akari (game)": "주인공", "Rei (game)": "주인공",
    "Adaman": "금강단 리더", "Irida": "진주단 리더", "Clover": "진주단",
    "Kamado": "은하단 단장", "Beni": "은하단", "Zisu": "은하단", "Volo": "상인",
    "Mai": "히스이 지킴이", "Lian": "히스이 지킴이", "Arezu": "히스이 지킴이",
    "Melli": "히스이 지킴이", "Gaeric": "히스이 지킴이", "Sabi": "히스이 지킴이",
    "Naveen": "미르시티 트레이너", "Lida": "미르시티 트레이너", "Canari": "미르시티 트레이너",
    "Corbeau": "미르시티 트레이너", "Gwynn": "미르시티 트레이너", "Ivor": "미르시티 트레이너",
    "Grisham": "미르시티 트레이너", "Lebanne": "미르시티 트레이너",
    "Jacinthe": "미르시티 트레이너", "Tarragon": "미르시티 트레이너",
}
KR_OVERRIDE = {"Steven Stone": "성호", "Tate and Liza": "풍&란", "N": "N", "AZ": "AZ",
               "Professor Kukui": "쿠쿠이 박사", "Professor Sycamore": "플라타느 박사"}
SPRITE_OVERRIDE = {"Steven Stone": "steven", "Professor Kukui": "kukui",
                   "Professor Sycamore": "sycamore", "Tate and Liza": "tate"}

# 겹치는 쌍(주인공 남녀는 팀이 같다)이나 이름만 있는 사람은 뺀다.
EXCLUDE = {
    "Evice", "Carmen", "Harrington",
    "Kiyo", "Koichi", "Ress", "Youssef", "Andi", "Asami", "Griselle", "Josée", "Mani", "Philippe",
    "Rintaro", "Vinnie", "Xavi", "Yvon", "Zach", "James", "Jessie", "Lily (Kanto)", "Coin (Hisui)",
    "Charm (Hisui)",
}

# 주인공 남녀는 원작 파티가 같다(고른 스타팅만 다르다). 그대로 두면 똑같은
# 팀이 둘 생기므로 **서로 다른 스타팅을 에이스로** 박고, 같은 세대의 다른
# 스타팅 계열은 뺀다.
FORCE_ACE = {
    # 원작 수치로 뽑으면 어긋나는 대표 포켓몬
    "Red (game)": "PIKACHU", "Blue (game)": "BLASTOISE", "Silver (game)": "FERALIGATR",
    "Hop": "ZAMAZENTA",
    "Brendan (game)": "SWAMPERT", "May (game)": "BLAZIKEN",
    "Dawn (game)": "EMPOLEON", "Lucas (game)": "INFERNAPE",
    "Serena (game)": "DELPHOX", "Calem (game)": "GRENINJA",
    "Nate (game)": "SAMUROTT", "Rosa (game)": "SERPERIOR",
    "Taunie": "MEGANIUM", "Urbain": "FERALIGATR",
    "Akari (game)": "DECIDUEYE", "Rei (game)": "TYPHLOSION",
}
# 스타팅을 하나만 두는 사람. 레드는 셋을 다 데리고 있어서 빼지 않는다.
KEEP_STARTERS = {"Red (game)"}
# 한 팀에 같이 있으면 안 되는 쌍 (버전마다 하나만 받는다)
NOT_TOGETHER = [{"ZACIAN", "ZAMAZENTA"}, {"RESHIRAM", "ZEKROM"}, {"XERNEAS", "YVELTAL"},
                {"SOLGALEO", "LUNALA"}, {"KORAIDON", "MIRAIDON"}]
# 문서의 파티가 그때그때 달라서(N 은 매번 그 지역 포켓몬을 쓴다) 뽑으면
# 원래 모습이 안 나오는 사람. 블랙·화이트 마지막 대결의 팀이다.
TEAM_OVERRIDE = {
    "N": ["CARRACOSTA", "VANILLUXE", "ARCHEOPS", "KLINKLANG", "ZOROARK", "ZEKROM"],
    # 모란은 이브이 진화형이 트레이드마크다. 문서에서 가장 센 파티는 DLC 의
    # 전설 팀이라 그대로 뽑으면 이벨타르·다크라이가 나왔다.
    "Penny": ["UMBREON", "VAPOREON", "JOLTEON", "FLAREON", "LEAFEON", "SYLVEON"],
    # 게치스의 에이스는 삼삼드래. 레인보우로켓 판의 전설이 끼어들었다.
    "Ghetsis": ["COFAGRIGUS", "BOUFFALANT", "SEISMITOAD", "BISHARP", "EELEKTROSS", "HYDREIGON"],
}
STARTERS = {"BULBASAUR", "CHARMANDER", "SQUIRTLE", "CHIKORITA", "CYNDAQUIL", "TOTODILE",
            "TREECKO", "TORCHIC", "MUDKIP", "TURTWIG", "CHIMCHAR", "PIPLUP", "SNIVY", "TEPIG",
            "OSHAWOTT", "CHESPIN", "FENNEKIN", "FROAKIE", "ROWLET", "LITTEN", "POPPLIO",
            "GROOKEY", "SCORBUNNY", "SOBBLE", "SPRIGATITO", "FUECOCO", "QUAXLY"}

# 문서에 파티가 없는 사람은 손으로 적는다. (에이스를 마지막에)
SPECIAL = {
    # 이스터에그. 포스크탑을 만든 사람이 의정부시에 개발자로 숨어 있다.
    # 전설 여섯은 타입이 안 겹치게 골랐다. 디아루가는 본인이 꼭 넣어 달라고
    # 했고, 아르세우스도 본인이 골랐다(제르네아스 대신). 아르세우스만 종족값
    # 720 이고 나머지는 670~680 이다. 멀티타입은 이 엔진에서 효과가 없어
    # 노말 타입으로 나온다.
    # 시간의포효·지오컨트롤처럼 모으거나 쉬어야 하는 기술은 뺐다 - 이 엔진은
    # 모으기·반동 턴이 없어서 그대로 넣으면 위력 150 을 매 턴 쏜다.
    # 아르세우스에게 명상은 안 준다. HP회복과 같이 두면 끝없이 쌓는다.
    # 도트는 본인이 준 그림 두 장이다 (server/data/trainer_sprites/easter-egg*.png).
    # 관장 탭 카드에는 렌트라와 같이 선 것, 배틀 화면에는 혼자 선 것.
    "Easter Egg": {
        "kr": "나여조경석", "role": "개발자", "sprite": "easter-egg", "battle_sprite": "easter-egg-solo",
        "gen": 4, "score": 400,
        # 에이스는 렌트라(본인 선택, 칠색조 자리에 디아루가). 렌트라는 종족값 523 이라
        # 능력치를 1.22배 해서 합계를 나머지 전설 다섯의 평균(Lv.100 에서 1815)에 맞췄다.
        "team": [("ARCEUS", ["JUDGMENT", "EARTHPOWER", "SHADOWBALL", "RECOVER"]),
                 ("KYOGRE", ["ORIGINPULSE", "ICEBEAM", "THUNDER", "CALMMIND"]),
                 ("GROUDON", ["PRECIPICEBLADES", "STONEEDGE", "FIREPUNCH", "SWORDSDANCE"]),
                 ("DIALGA", ["DRACOMETEOR", "FLASHCANNON", "EARTHPOWER", "THUNDERBOLT"]),
                 ("MEWTWO", ["PSYSTRIKE", "AURASPHERE", "ICEBEAM", "RECOVER"]),
                 ("LUXRAY", ["WILDCHARGE", "CRUNCH", "ICEFANG", "FIREFANG"],
                  {"ability": "INTIMIDATE", "boost": 1.22})]},
    "Professor Oak": {
        "kr": "오박사", "role": "포켓몬 박사", "sprite": "oak", "gen": 1, "score": 58,
        "team": [("KINGLER", []), ("MUK", []), ("NIDOKING", []), ("TAUROS", []),
                 ("ARCANINE", []), ("DRAGONITE", [])]},
    "Alain": {
        "kr": "알랭", "role": "칼로스의 트레이너", "sprite": "alain", "gen": 6, "score": 70,
        "team": [("UNFEZANT", []), ("WEAVILE", []), ("BISHARP", []), ("TYRANITAR", []),
                 ("METAGROSS", []), ("CHARIZARD", ["FLAMETHROWER", "DRAGONCLAW", "BLASTBURN", "FLAREBLITZ"])]},
    "Ethan (game)": {
        "kr": "심향", "role": "주인공", "sprite": "ethan", "gen": 2, "score": 38,
        "team": [("AMPHAROS", []), ("TOGEKISS", []), ("HERACROSS", []), ("LAPRAS", []),
                 ("SCIZOR", []), ("TYPHLOSION", [])]},
    "Lyra (game)": {
        "kr": "금선", "role": "주인공", "sprite": "lyra", "gen": 2, "score": 36,
        "team": [("AZUMARILL", []), ("WIGGLYTUFF", []), ("NOCTOWL", []), ("ESPEON", []),
                 ("MILTANK", []), ("MEGANIUM", [])]},
    "Hilbert (game)": {
        "kr": "투지", "role": "주인공", "sprite": "hilbert", "gen": 5, "score": 40,
        "team": [("ZEBSTRIKA", []), ("EXCADRILL", []), ("BRAVIARY", []), ("SCRAFTY", []),
                 ("GALVANTULA", []), ("EMBOAR", [])]},
    "Hilda (game)": {
        "kr": "투희", "role": "주인공", "sprite": "hilda", "gen": 5, "score": 40,
        "team": [("LILLIGANT", []), ("ZOROARK", []), ("SWANNA", []), ("CHANDELURE", []),
                 ("KROOKODILE", []), ("SAMUROTT", [])]},
    "Elio (game)": {
        "kr": "영태", "role": "주인공", "sprite": "elio", "gen": 7, "score": 42,
        "team": [("TOUCANNON", []), ("LYCANROC", []), ("MIMIKYU", []), ("SALAZZLE", []),
                 ("VIKAVOLT", []), ("INCINEROAR", [])]},
    "Selene (game)": {
        "kr": "미월", "role": "주인공", "sprite": "selene", "gen": 7, "score": 42,
        "team": [("RIBOMBEE", []), ("ARAQUANID", []), ("TSAREENA", []), ("TOXAPEX", []),
                 ("KOMMOO", []), ("PRIMARINA", [])]},
    "Victor (game)": {
        "kr": "승재", "role": "주인공", "sprite": "victor", "gen": 8, "score": 44,
        "team": [("CORVIKNIGHT", []), ("CENTISKORCH", []), ("TOXTRICITY", []), ("BOLTUND", []),
                 ("APPLETUN", []), ("CINDERACE", [])]},
    "Gloria (game)": {
        "kr": "우리", "role": "주인공", "sprite": "gloria", "gen": 8, "score": 44,
        "team": [("DREDNAW", []), ("GRIMMSNARL", []), ("HATTERENE", []), ("FROSMOTH", []),
                 ("DURALUDON", []), ("INTELEON", [])]},
    # 지우는 원작 지우가 아니라 본인이 정한 캐릭터다 (도트도 본인이 준 그림).
    # 종족값이 낮은 둘은 조금 올렸다 - 마임맨(460)은 팀 평균(1461)에, 에이스 따라큐(476)는
    # 마스카나(1507)에 맞춰 능력치를 1.07·1.08배. 개체값은 Lv.100 이라 이미 31(최대)이다.
    "Ash Ketchum": {
        "kr": "지우", "role": "월드 챔피언", "sprite": "jiwoo", "gen": 1, "score": 110,
        "team": [("MEOWSCARADA", ["FLOWERTRICK", "KNOCKOFF", "PLAYROUGH", "UTURN"], {"ability": "PROTEAN"}),
                 ("ALAKAZAM", ["PSYCHIC", "SHADOWBALL", "FOCUSBLAST", "ENERGYBALL"], {"ability": "MAGICGUARD"}),
                 ("MRMIME", ["PSYCHIC", "DAZZLINGGLEAM", "THUNDERBOLT", "NASTYPLOT"],
                  {"ability": "FILTER", "boost": 1.07}),
                 ("GENGAR", ["SHADOWBALL", "SLUDGEBOMB", "FOCUSBLAST", "THUNDERBOLT"]),
                 ("DRIFBLIM", ["SHADOWBALL", "AIRSLASH", "THUNDERBOLT", "WILLOWISP"], {"ability": "UNBURDEN"}),
                 ("MIMIKYU", ["PLAYROUGH", "SHADOWCLAW", "SWORDSDANCE", "DRAINPUNCH"],
                  {"ability": "DISGUISE", "boost": 1.08})]},
    "Jessie and James": {
        "kr": "로사&로이", "role": "로켓단", "sprite": "jessiejames-gen1", "gen": 1, "score": 24,
        "team": [("ARBOK", []), ("WEEZING", []), ("VICTREEBEL", []),
                 ("WOBBUFFET", []), ("SEVIPER", []), ("MEOWTH", [])]},
}

# 원작 수치로 줄을 세우면 어긋나는 사람만 레벨을 박는다.
TIER_PIN = {"Red (game)": 100, "Ash Ketchum": 100, "Cynthia": 100, "Leon": 100,
            "Steven Stone": 100, "Geeta": 100, "Easter Egg": 100}

# 손으로 박은 자리 (시도 앞글자, 시군구, 이유)
PIN = {
    "Cynthia": ("서울", "종로구", "고고학자 — 궁궐과 유적 한가운데"),
    "Rose": ("서울", "중구", "회장 — 서울 도심의 기업가"),
    "Lenora": ("서울", "용산구", "박물관장 — 국립중앙박물관"),
    "Elesa": ("서울", "강남구", "톱모델 — 패션 거리"),
    "Diantha": ("서울", "서초구", "배우 — 예술의전당"),
    "Ryme": ("서울", "마포구", "래퍼 — 홍대 앞 무대"),
    "Larry": ("서울", "영등포구", "직장인 — 여의도 사무실"),
    "Leon": ("서울", "송파구", "무패의 챔피언 — 잠실 주경기장"),
    "Bea": ("서울", "노원구", "격투가 — 태릉선수촌"),
    "Burgh": ("서울", "성북구", "화가 — 성북동 예술가 마을"),
    "Winona": ("서울", "강서구", "비행 타입 — 김포공항"),
    "Molayne": ("서울", "구로구", "기술자 — 구로디지털단지"),
    "Grant": ("서울", "강북구", "암벽 등반가 — 북한산 인수봉"),
    "Professor Sycamore": ("서울", "관악구", "박사 — 대학 연구실"),
    "Nessa": ("부산", "수영구", "모델이자 물 타입 — 광안리"),
    "Misty": ("부산", "영도구", "물 타입 — 섬 하나가 통째로 구"),
    "Juan": ("경상남", "통영시", "물의 예술가 — 한려수도"),
    "Wallace": ("전남광주", "여수시", "물의 예술가 — 여수 밤바다"),
    "Skyla": ("인천", "영종구", "파일럿 — 인천국제공항"),
    "Archie": ("인천", "제물포구", "아쿠아단 — 인천항"),
    "Lysandre": ("인천", "연수구", "미래 도시를 꿈꾸는 — 송도 국제도시"),
    "AZ": ("인천", "강화군", "3000년을 산 왕 — 강화 고인돌"),
    "Kofu": ("인천", "남동구", "생선 가게 — 소래포구 어시장"),
    "Lana": ("인천", "옹진군", "낚시하는 캡틴 — 섬 서른세 개"),
    "Blaine": ("대구", "중구", "불꽃 타입 — 대프리카"),
    "Kabu": ("대구", "동구", "불꽃 타입 — 대프리카"),
    "Chili": ("대구", "서구", "불꽃 타입 — 대프리카"),
    "Flint": ("대구", "남구", "불꽃 타입 — 대프리카"),
    "Kiawe": ("대구", "북구", "불꽃 타입 — 대프리카"),
    "Malva": ("대구", "수성구", "불꽃 타입 — 대프리카"),
    "Crispin": ("대구", "달서구", "불꽃 타입 — 대프리카"),
    "Mela": ("대구", "달성군", "불꽃 타입 — 대프리카"),
    "Tabitha": ("대구", "군위군", "마그마단 — 대프리카"),
    "Flannery": ("충청남", "아산시", "용암 온천 마을 — 온양온천"),
    "Roxie": ("울산", "남구", "독 타입 — 석유화학단지"),
    "Byron": ("울산", "동구", "강철 — 조선소"),
    "Poppy": ("울산", "북구", "강철 — 자동차 공장"),
    "Steven Stone": ("경상북", "포항시남구", "강철·돌 수집가 — 제철소"),
    "Geeta": ("세종", "세종시", "리그 위원장 — 행정수도"),
    "Clemont": ("대전", "유성구", "발명가 — 대덕연구단지"),
    "Katy": ("대전", "중구", "빵집 주인 — 성심당"),
    "Emmet": ("대전", "동구", "서브웨이마스터 — 대전역"),
    "Colress": ("대전", "대덕구", "과학자 — 대덕산업단지"),
    "Brassius": ("전남광주", "순천시", "정원 예술가 — 순천만국가정원"),
    "Gardenia": ("전남광주", "보성군", "풀 타입 — 녹차밭"),
    "Erika": ("전남광주", "담양군", "풀 타입 — 대나무숲"),
    "Tate and Liza": ("전남광주", "고흥군", "우주센터가 있는 섬 — 나로우주센터"),
    "Wattson": ("전남광주", "영광군", "발전소 — 한빛원전"),
    "Volkner": ("전남광주", "나주시", "전기 — 한국전력 본사"),
    "Hapu": ("전남광주", "해남군", "땅 타입 농부 — 땅끝마을 배추밭"),
    "Nanu": ("전남광주", "완도군", "섬킹 — 섬 예순두 개"),
    "Olivia": ("전북", "익산시", "보석 가게 — 보석박물관"),
    "Mallow": ("전북", "전주시완산구", "요리하는 캡틴 — 비빔밥"),
    "Chuck": ("전북", "무주군", "무술가 — 태권도원"),
    "Arven": ("전북", "순창군", "매운 스코빌런 — 고추장"),
    "Milo": ("전북", "김제시", "농부 — 지평선 쌀"),
    "Lt. Surge": ("경기", "평택시", "군인 출신 — 미군기지"),
    "Lucian": ("경기", "파주시", "책벌레 사천왕 — 출판도시"),
    "Wikstrom": ("경기", "수원시팔달구", "기사 — 수원화성"),
    "Clay": ("경기", "광명시", "광산주 — 광명동굴"),
    "Gordie": ("경기", "포천시", "돌 타입 — 채석장 아트밸리"),
    "Ingo": ("경기", "의왕시", "서브웨이마스터 — 철도박물관"),
    "Brycen": ("경기", "부천시원미구", "영화배우 — 판타스틱영화제"),
    "Professor Kukui": ("경기", "과천시", "박사 — 국립과천과학관"),
    "Iono": ("경기", "성남시분당구", "스트리머 — 판교"),
    "Grusha": ("강원", "평창군", "전 스노보더 — 올림픽"),
    "Candice": ("강원", "강릉시", "얼음 타입 — 빙상경기장"),
    "Wulfric": ("강원", "철원군", "얼음 타입 — 남한에서 가장 추운 곳"),
    "Glacia": ("강원", "인제군", "얼음 사천왕 — 설악의 겨울"),
    "Roark": ("강원", "태백시", "탄광 관장 — 탄광 도시"),
    "Marlon": ("강원", "양양군", "서퍼 — 서핑의 성지"),
    "Pryce": ("강원", "화천군", "얼음 타입 — 산천어축제"),
    "Whitney": ("강원", "횡성군", "밀탱크 — 한우"),
    "Giovanni": ("강원", "정선군", "게임코너 주인 — 카지노"),
    "Bruno": ("충청남", "논산시", "수련 — 육군훈련소"),
    "Marshal": ("충청남", "계룡시", "무도가 — 계룡대"),
    "Morty": ("경상북", "경주시", "역사 도시의 수행자 — 천년 고도"),
    "Olympia": ("경상북", "영천시", "별을 읽는 — 보현산천문대"),
    "Maxie": ("경상북", "울릉군", "땅을 넓히려는 — 화산섬"),
    "Sophocles": ("경상북", "구미시", "기계광 — 전자산업단지"),
    "Kahili": ("경상남", "사천시", "비행 타입 — 항공우주산업"),
    "Red (game)": ("제주", "서귀포시", "은빛산 정상 — 한라산"),
    "Easter Egg": ("경기", "의정부시", "이스터에그 — 포스크탑 개발자"),
    "Hala": ("제주", "제주시", "섬킹 — 섬"),
}

ROLE_RANK = {"챔피언": 0, "사천왕": 1, "관장": 2, "조직 보스": 3, "프런티어브레인": 4,
             "라이벌": 5, "섬킹": 6, "캡틴": 6, "스타단": 7, "히스이 트레이너": 9, "트레이너": 10}


# ---------------------------------------------------------------- 받기
UA = "poketdesktop-gyms/1.0"


def api(**q):
    q.update(format="json")
    url = "https://bulbapedia.bulbagarden.net/w/api.php?" + urllib.parse.urlencode(q)
    for i in range(5):
        r = subprocess.run(["curl", "-s", "-m", "90", "-A", UA, url], capture_output=True)
        try:
            return json.loads(r.stdout.decode())
        except Exception:                                  # noqa: BLE001
            time.sleep(3 + 3 * i)
    raise SystemExit("받지 못했습니다: " + url)


def fetch(titles):
    pages = {}
    for i in range(0, len(titles), 40):
        d = api(action="query", prop="revisions", rvprop="content", rvslots="main",
                redirects=1, titles="|".join(titles[i:i + 40]))
        for p in d["query"]["pages"].values():
            if "revisions" in p:
                pages[p["title"]] = p["revisions"][0]["slots"]["main"]["*"]
        time.sleep(1.5)
    return pages


# ---------------------------------------------------------------- 문서 읽기
H2 = re.compile(r"^==\s*([^=].*?)\s*==\s*$", re.M)
HEAD = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$", re.M)
FACILITY = re.compile(
    r"rematch|battle tree|battle tower|battle agency|world tournament|leaders tournament|"
    r"type expert|master class|battle subway|battle maison|battle frontier|battle hall|"
    r"battle factory|battle castle|battle arcade|battle pyramid|battle arena|battle dome|"
    r"battle palace|battle pike|trade|given away|pokémon stadium|round \d|multi battle|"
    r"tag battle|academy ace tournament|league club|ace tournament|union circle", re.I)
# 트레이너 자신의 팀이 아닌 것. 포켓우드(Pokéstar Studios)는 영화 배역이라
# 담죽이 '브라이센맨' 역으로 쓰는 악 타입 팀이 들어 있다. 레벨이 높아서
# 그대로 두면 에이스와 팀을 통째로 차지한다(얼음 관장이 마닉스·샤크니아를 들고 나왔다).
NOT_OWN = re.compile(r"pokéstar studios", re.I)


def core_section(w):
    heads = [(m.start(), m.group(1)) for m in H2.finditer(w)]
    for i, (pos, t) in enumerate(heads):
        if re.search(r"in the (core series )?games|in the core series",
                     re.sub(r"\[\[|\]\]", "", t), re.I):
            return w[pos:heads[i + 1][0] if i + 1 < len(heads) else len(w)]
    return ""


def params(body):
    """틀의 | 키 = 값. 값 안의 {{tt|77|..}} 때문에 바깥 단계 | 에서만 자른다."""
    inner = body[2:-2] if body.startswith("{{") and body.endswith("}}") else body
    parts, depth, cur, i = [], 0, [], 0
    while i < len(inner):
        two = inner[i:i + 2]
        if two in ("{{", "[["):
            depth += 1
            cur.append(two)
            i += 2
            continue
        if two in ("}}", "]]"):
            depth -= 1
            cur.append(two)
            i += 2
            continue
        if inner[i] == "|" and depth == 0:
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(inner[i])
        i += 1
    parts.append("".join(cur))
    out = {}
    for p in parts[1:]:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        k = k.strip()
        if re.match(r"^[A-Za-z0-9_]+$", k) and k not in out:
            out[k] = re.sub(r"<!--.*?-->", "", v, flags=re.S).strip()
    return out


def plain(v):
    v = re.sub(r"\{\{tt\|([^|}]*)\|[^}]*\}\}", r"\1", v)
    v = re.sub(r"\{\{(?:m|p|a|i|type|t)\|([^|}]*)(?:\|[^}]*)?\}\}", r"\1", v)
    v = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", v)
    return re.sub(r"<[^>]+>", "", v).strip()


def templates(text, name):
    i = 0
    while True:
        j = text.find("{{" + name, i)
        if j < 0:
            return
        k = j + 2 + len(name)
        if k < len(text) and text[k] not in "\n |}":
            i = k
            continue
        depth, p = 0, j
        while p < len(text):
            if text.startswith("{{", p):
                depth += 1
                p += 2
                continue
            if text.startswith("}}", p):
                depth -= 1
                p += 2
                if depth == 0:
                    break
                continue
            p += 1
        yield j, p, text[j:p]
        i = p


def parse_parties(w):
    sec = core_section(w)
    if not sec:
        return []
    heads = [(m.start(), len(m.group(1)), re.sub(r"\{\{|\}\}|\[\[|\]\]", "", m.group(2)))
             for m in HEAD.finditer(sec)]
    parties = []
    for j, p, block in templates(sec, "Party"):
        hp = params(block)
        end = sec.find("{{Party/end}}", p)
        if end < 0:
            continue
        body = sec[p:end]
        path = {}
        for pos, lvl, t in heads:
            if pos < j:
                path[lvl] = t
                for deeper in [x for x in path if x > lvl]:
                    del path[deeper]
        heading = " / ".join(path[k] for k in sorted(path))
        if NOT_OWN.search(heading):
            continue
        facility = bool(FACILITY.search(heading)) or "BP" in hp.get("prize", "")
        mons = []
        for _, _, mb in templates(body, "Pokémon"):
            mp = params(mb)
            if not mp.get("pokemon"):
                continue
            # "58-62" · "{{tt|77|첫 대결}}/{{tt|82|재대결}}" -> 첫 숫자 = 첫 대결
            nums = [int(x) for x in re.findall(r"\d+", mp.get("level", "")) if 1 <= int(x) <= 100]
            lvl = nums[0] if nums else (50 if facility else 0)
            if not lvl:
                continue
            nd = re.sub(r"[^0-9]", "", mp.get("ndex", ""))
            mons.append({"en": plain(mp["pokemon"]), "ndex": int(nd or 0),
                         "form": plain(mp.get("form", "")), "level": lvl,
                         "ability": plain(mp.get("ability", "")), "held": plain(mp.get("held", "")),
                         "moves": [plain(mp.get("move%d" % i, "")) for i in range(1, 5)
                                   if plain(mp.get("move%d" % i, ""))]})
        if not mons:
            # 배틀시설 표: {{lop/facility|game=3|번호|종|도구|기술|타입|...}}
            for fm in re.finditer(r"\{\{lop/facility\|([^\n]*)\}\}", body):
                cells = [c.strip() for c in fm.group(1).split("|") if not c.strip().startswith("game=")]
                if len(cells) < 3 or not cells[0].isdigit():
                    continue
                mons.append({"en": plain(cells[1]), "ndex": int(cells[0]), "form": "", "level": 50,
                             "ability": "", "held": plain(cells[2]),
                             "moves": [plain(cells[k]) for k in (3, 5, 7, 9)
                                       if k < len(cells) and plain(cells[k])]})
        if mons:
            parties.append({"game": hp.get("game", ""), "heading": heading, "facility": facility,
                            "mons": mons, "avg": sum(m["level"] for m in mons) / len(mons)})
    return parties


def korean(w):
    ls = w.splitlines()
    for i, l in enumerate(ls):
        cells = [c.strip() for c in l.split("|")]
        if cells and cells[-1] == "Korean" and i + 1 < len(ls):
            v = ls[i + 1].strip().lstrip("|").strip()
            v = re.sub(r"\{\{ruby\|([^|}]*)\|[^}]*\}\}", r"\1", v)
            v = re.split(r"''|<|\(|\{\{", v)[0].strip()
            if v:
                return v
    return ""


# ---------------------------------------------------------------- 도감 도우미
def key(name):
    return re.sub(r"[^A-Z0-9]", "", (name or "").upper().replace("É", "E"))


class Dex(object):
    def __init__(self, raw):
        self.raw = raw
        self.by_num = {s["num"]: s for s in raw["species"]}
        self.by_key = {s["internal"]: s for s in raw["species"]}
        self.moves = raw["moves"]
        self.abilities = raw["abilities"]

    def species(self, mon):
        """문서의 한 줄 -> 우리 도감의 종. 지역 폼은 본래 폼으로."""
        return self.by_num.get(mon.get("ndex")) or self.by_key.get(key(mon.get("en")))

    def prevo(self, sp):
        """진화 전 종. 도감의 prevo 는 **이름이 아니라 번호**다."""
        p = sp.get("prevo")
        return self.by_num.get(p) if isinstance(p, int) else self.by_key.get(p)

    def family(self, sp):
        seen = 0
        while self.prevo(sp) and seen < 4:
            sp = self.prevo(sp)
            seen += 1
        return sp["internal"]

    def legal_at(self, sp, level):
        """그 레벨에 있을 법한 진화 단계로 낮춘다."""
        seen = 0
        while self.prevo(sp) and seen < 4:
            pre = self.prevo(sp)
            need = None
            for e in pre.get("evo") or []:
                if e.get("to") == sp["internal"]:
                    need = e.get("level") if e.get("mode") == "level" and e.get("level") else 30
            if need is None or level >= need:
                break
            sp = pre
            seen += 1
        return sp

    def bst(self, sp):
        return sum(sp["base"].values())


# ---------------------------------------------------------------- 팀
def pick_team(dex, title, parties, special=None):
    """(에이스를 맨 뒤에 둔) 종 목록과, 종마다 원작에 있던 기술·특성·도구."""
    info = collections.OrderedDict()
    if special:
        for row in special["team"]:
            sp_key, mv = row[0], row[1]
            opt = row[2] if len(row) > 2 else {}
            info[sp_key] = {"moves": mv, "ability": opt.get("ability", ""), "held": opt.get("held", ""),
                            "gender": "", "boost": opt.get("boost")}
        order = [row[0] for row in special["team"]]
        return order, info, [], dex.by_key[order[-1]]["types"][0]

    count = collections.Counter()
    last_seen = {}
    types = collections.Counter()
    gens = collections.Counter()
    for pi, party in enumerate(parties):
        for mi, m in enumerate(party["mons"]):
            sp = dex.species(m)
            if not sp:
                continue
            k = sp["internal"]
            count[k] += 1
            last_seen[k] = (pi, mi)
            for t in sp["types"]:
                types[t] += 1
            gens[sp["gen"]] += 1
            # 가장 레벨 높은 등장의 기술을 쓴다
            if k not in info or m["level"] >= info[k]["level"]:
                info[k] = {"level": m["level"], "moves": m["moves"], "ability": m["ability"],
                           "held": m["held"], "gender": m.get("gender", "")}
    if not count:
        return [], info, [], None
    main = [p for p in parties if not p["facility"]] or parties
    best = max(main, key=lambda p: (p["avg"], len(p["mons"])))
    ace_mon = max(enumerate(best["mons"]), key=lambda im: (im[1]["level"], im[0]))[1]
    ace_sp = dex.species(ace_mon)
    ace = ace_sp["internal"] if ace_sp else count.most_common(1)[0][0]
    best_keys = {dex.species(m)["internal"] for m in best["mons"] if dex.species(m)}
    forced = FORCE_ACE.get(title)
    if forced:
        ace = forced
        count[ace] = count.get(ace, 0)
        last_seen.setdefault(ace, (-1, -1))
        # 다른 스타팅 계열은 후보에서 뺀다
        if title not in KEEP_STARTERS and dex.family(dex.by_key[ace]) in STARTERS:
            for k in list(count):
                if k != ace and dex.family(dex.by_key[k]) in STARTERS:
                    del count[k]
    for pair in NOT_TOGETHER:
        if ace in pair:
            for k in pair - {ace}:
                count.pop(k, None)
    if title in TEAM_OVERRIDE:
        order = list(TEAM_OVERRIDE[title])
        for k in order:
            info.setdefault(k, {"moves": [], "ability": "", "held": "", "gender": ""})
        spec = types.most_common(1)[0][0] if types else dex.by_key[order[-1]]["types"][0]
        return order, info, [spec, dex.by_key[order[-1]]["gen"]], spec

    def score(k):
        return (count[k] + (3 if k in best_keys else 0), last_seen[k])

    chosen, fams = [], set()
    for k in [ace] + sorted(count, key=score, reverse=True):
        f = dex.family(dex.by_key[k])
        if f in fams or len(chosen) >= TEAM:
            continue
        if any(k in pair and (pair - {k}) & set(chosen) for pair in NOT_TOGETHER):
            continue
        # 스타팅은 한 마리만 (레드는 셋 다 데리고 다닌다)
        if (title not in KEEP_STARTERS and f in STARTERS
                and any(dex.family(dex.by_key[c]) in STARTERS for c in chosen)):
            continue
        fams.add(f)
        chosen.append(k)
    rest = [k for k in chosen if k != ace]
    order = rest + [ace]
    spec = types.most_common(1)[0][0]
    debut_gen = gens.most_common(1)[0][0]
    return order, info, [spec, debut_gen], spec


def filler(dex, spec, gen, level, taken_fams, n, legendary_ok=False):
    """전문 타입으로 모자란 자리를 채운다."""
    cap = 330 + level * 8
    out = []
    pool = []
    for sp in dex.raw["species"]:
        if spec not in sp["types"] or sp.get("isBaby"):
            continue
        if sp.get("legendary") and not legendary_ok:
            continue
        if sp.get("evo"):                     # 최종형만 후보로 (레벨에 맞게 낮추는 건 뒤에서)
            continue
        f = dex.family(sp)
        if f in taken_fams:
            continue
        at = dex.legal_at(sp, level)
        b = dex.bst(at)
        if b > cap:
            continue
        pool.append((0 if sp["gen"] == gen else 1, abs(b - cap * 0.92), sp["num"], sp["internal"], f))
    pool.sort()
    for _, _, _, k, f in pool:
        if f in taken_fams:
            continue
        taken_fams.add(f)
        out.append(k)
        if len(out) >= n:
            break
    return out


def moveset(dex, sp, level, canon):
    moves = []
    for mv in canon or []:
        k = key(mv)
        if k in dex.moves and k not in moves and k not in SELF_KO:
            moves.append(k)
        if len(moves) == 4:
            return moves
    stab = set(sp["types"])
    cands = []
    for k in P.learnable_moves(sp, level):
        md = dex.moves.get(k)
        if not md or k in moves or k in SELF_KO:
            continue
        pw = md.get("power") or 0
        acc = md.get("acc") or 100
        if md.get("cat") == "status":
            cands.append((0, 1, k, None))
        else:
            val = pw * acc / 100.0 * (1.5 if md["type"] in stab else 1.0)
            cands.append((1, val, k, md["type"]))
    dmg = sorted([c for c in cands if c[0] == 1], key=lambda c: -c[1])
    used_types = {dex.moves[m]["type"] for m in moves if dex.moves[m].get("cat") != "status"}
    for _, _, k, t in dmg:
        if len(moves) >= 3:
            break
        if t in used_types:
            continue
        moves.append(k)
        used_types.add(t)
    for _, _, k, _ in dmg:
        if len(moves) >= 4:
            break
        if k not in moves:
            moves.append(k)
    status = [c[2] for c in cands if c[0] == 0]
    for k in reversed(status):
        if len(moves) >= 4:
            break
        moves.append(k)
    return moves[:4]


def ability_of(dex, sp, canon):
    k = key(canon)
    allowed = list(sp.get("abil") or []) + ([sp["hidden"]] if sp.get("hidden") else [])
    if k and k in allowed:
        return k
    return allowed[0] if allowed else None


def levels_for(tier):
    return [min(100, tier + o) for o in OFFSETS] if tier < 100 else [100] * TEAM


# ---------------------------------------------------------------- 줄 세우기
CHAMPION_ROLES = ("챔피언", "전설의 트레이너", "월드 챔피언", "블루베리 챔피언", "박사 · 챔피언",
                  "챔피언 · 라이벌")
TOP_ROLES = ("사천왕", "전 챔피언", "프런티어브레인", "타워타이쿤", "아케이드스타", "캐슬발레",
             "서브웨이마스터", "블랙타워")


def strength(role, parties, special):
    """줄 세우기 점수.

    **역할로 먼저 층을 나눈다.** 원작 레벨만으로 세우면 게임마다 기준이
    달라서, 블루베리 사천왕(Lv.80대)이 목호·윤진(Lv.50대 챔피언)보다
    위로 올라갔다. 챔피언 > 사천왕·배틀시설·조직 보스 > 나머지 순으로
    층을 두고, 같은 층 안에서만 원작 레벨로 줄을 세운다.
    """
    if special:
        lv = special["score"]
    else:
        main = [p for p in parties if not p["facility"]] or parties
        avgs = [p["avg"] for p in main]
        debut, mx, med = avgs[0], max(avgs), statistics.median(avgs)
    if role in CHAMPION_ROLES or role.startswith("챔피언"):
        return 300 + (lv if special else mx)
    if role in TOP_ROLES or role.startswith("사천왕"):
        return 200 + (lv if special else (75 if not main[0]["facility"] and mx < 60 and role not in ("사천왕", "전 챔피언") else mx))
    if role.endswith(("보스", "리더", "회장", "대표")) or role in ("플라즈마단 왕",):
        return 200 + (lv if special else mx)
    if special:
        return lv
    if role.startswith("관장"):
        return debut
    if role.startswith(("라이벌", "섬킹", "섬퀸", "주인공")):
        return med
    if "교사" in role or "교장" in role:
        return debut - 15
    if "간부" in role or role in ("플라즈마단", "갈라 왕가"):
        return med - 3
    if "히스이" in role or "미르시티" in role:
        return med - 5
    return debut


def assign_tiers(people):
    caps = []
    for k in range(len(TIERS)):
        caps.append(((k + 1) * len(people)) // len(TIERS) - (k * len(people)) // len(TIERS))
    tier_of = {}
    for p in people:
        t = TIER_PIN.get(p["title"])
        if t:
            tier_of[p["title"]] = t
            caps[TIERS.index(t)] -= 1
    rest = sorted((p for p in people if p["title"] not in tier_of),
                  key=lambda p: (p["score"], -ROLE_RANK.get(p["role"], 8), p["title"]))
    k = 0
    for p in rest:
        while caps[k] <= 0:
            k += 1
        tier_of[p["title"]] = TIERS[k]
        caps[k] -= 1
    return tier_of


# ---------------------------------------------------------------- 자리
AFFINITY = {
    "WATER": lambda d: 3 * d["coast"] + 2 * (d["islands"] > 0),
    "ICE": lambda d: 3 * d["sidonm"].startswith("강원") + d["sidonm"].startswith(("충청북", "경상북")),
    "FIRE": lambda d: 2 * d["sidonm"].startswith("대구"),
    "GRASS": lambda d: 2 * (d["kind"] == "군") + d["sidonm"].startswith(("전", "경상남")),
    "BUG": lambda d: 2 * (d["kind"] == "군"),
    "GROUND": lambda d: 2 * (not d["coast"] and d["kind"] != "구"),
    "ROCK": lambda d: 2 * (not d["coast"] and d["kind"] != "구") + d["sidonm"].startswith(("강원", "경상북")),
    "STEEL": lambda d: (d["kind"] == "시") + d["sidonm"].startswith(("울산", "경상북")),
    "ELECTRIC": lambda d: 2 * (d["kind"] == "구"),
    "PSYCHIC": lambda d: 2 * (d["kind"] == "구"),
    "GHOST": lambda d: (d["kind"] == "구") + (d["kind"] == "군"),
    "DARK": lambda d: 2 * (d["kind"] == "구"),
    "POISON": lambda d: 2 * (d["kind"] == "구"),
    "FIGHTING": lambda d: (d["kind"] == "구") + (d["kind"] == "시"),
    "FLYING": lambda d: 2 * d["coast"],
    "DRAGON": lambda d: 2 * d["coast"] + d["sidonm"].startswith("강원"),
    "NORMAL": lambda d: 1,
    "FAIRY": lambda d: (d["kind"] == "구"),
}


def find_district(districts, sido_prefix, name):
    for d in districts:
        if d["sidonm"].startswith(sido_prefix) and d["name"] == name:
            return d
    raise SystemExit("PIN 의 자리가 지도에 없습니다: %s %s" % (sido_prefix, name))


def place(people, districts):
    where = {}
    taken = set()
    for p in people:
        pin = PIN.get(p["title"])
        if not pin:
            continue
        d = find_district(districts, pin[0], pin[1])
        if d["code"] in taken:
            raise SystemExit("PIN 이 겹칩니다: %s" % d["name"])
        where[p["title"]] = (d, pin[2])
        taken.add(d["code"])
    size = collections.Counter(d["sidonm"] for d in districts)
    filled = collections.Counter(where[t][0]["sidonm"] for t in where)
    rest = sorted((p for p in people if p["title"] not in where),
                  key=lambda p: (-p["tier"], p["title"]))
    for p in rest:
        best = None
        for d in districts:
            if d["code"] in taken:
                continue
            aff = AFFINITY.get(p["spec"], lambda _d: 0)(d)
            fill = filled[d["sidonm"]] / float(size[d["sidonm"]])
            tie = int(hashlib.md5((p["title"] + d["code"]).encode()).hexdigest()[:6], 16) / 16 ** 6
            s = aff * 1.0 - fill * 4.0 + tie * 0.5
            if best is None or s > best[0]:
                best = (s, d)
        d = best[1]
        where[p["title"]] = (d, "")
        taken.add(d["code"])
        filled[d["sidonm"]] += 1
    return where


# ---------------------------------------------------------------- 만들기
def slug(title):
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"\s*\(game\)$", "", title).lower()).strip("-")


def build(pages, cats, dex, districts, sprites):
    people = []
    skipped = []
    titles = sorted(set(pages) | set(SPECIAL))
    for title in titles:
        if (title in EXCLUDE and title not in SPECIAL) or re.search(r"Squad's Base", title):
            continue
        special = SPECIAL.get(title)
        parties = [] if special else parse_parties(pages[title])
        if not special and not parties:
            continue
        roles = [kr for cat, kr in ROLE_BY_CAT if title in cats.get(cat, [])]
        if title in CHAMPIONS:
            roles = ["챔피언"] + roles
        role = special["role"] if special else ROLE.get(title, roles[0] if roles else "트레이너")
        base = re.sub(r"\s*\(game\)$", "", title).replace("Professor ", "").replace(" Stone", "")
        sk = special["sprite"] if special else SPRITE_OVERRIDE.get(title)
        if not sk:
            k = re.sub(r"[^a-z0-9]", "", base.lower())
            sk = k if k in sprites else next((s for s in sorted(sprites) if s.startswith(k + "-")), "")
        if not sk:
            skipped.append((title, "도트 없음"))
            continue
        kr = special["kr"] if special else (KR_OVERRIDE.get(title) or korean(pages[title]))
        if not kr:
            skipped.append((title, "한국어 이름 없음"))
            continue
        order, info, extra, spec = pick_team(dex, title, parties, special)
        if not order:
            skipped.append((title, "도감에 맞는 포켓몬 없음"))
            continue
        people.append({"title": title, "kr": kr, "role": role, "sprite": sk, "parties": parties,
                       "battle_sprite": (special or {}).get("battle_sprite"),
                       "order": order, "info": info, "spec": spec,
                       "gen": special["gen"] if special else extra[1],
                       "score": strength(role, parties, special), "special": bool(special),
                       "nparties": len(parties)})

    # 256명으로 맞춘다. 넘치면 덜 유명한 쪽(역할 순위·파티 수)부터 뺀다.
    need = len(districts)
    if len(people) > need:
        people.sort(key=lambda p: (0 if p["title"] in PIN or p["title"] in TIER_PIN or p["special"] else 1,
                                   ROLE_RANK.get(p["role"], 8), -p["nparties"], p["title"]))
        for p in people[need:]:
            skipped.append((p["title"], "256명 초과"))
        people = people[:need]
    if len(people) < need:
        raise SystemExit("사람이 모자랍니다: %d / %d" % (len(people), need))

    tier_of = assign_tiers(people)
    for p in people:
        p["tier"] = tier_of[p["title"]]

    trainers = []
    for p in people:
        tier = p["tier"]
        lv = levels_for(tier)
        order = list(p["order"])
        # 레벨에 맞게 진화 단계를 낮추고, 같은 계열이 겹치면 뺀다
        fams, species_final = set(), []
        for i, k in enumerate(order):
            level = lv[len(order) - len(order) + i] if len(order) == TEAM else None
            species_final.append(k)
        chosen = []
        for k in order:
            f = dex.family(dex.by_key[k])
            if f in fams:
                continue
            fams.add(f)
            chosen.append(k)
        if len(chosen) < TEAM:
            add = filler(dex, p["spec"], p["gen"], tier, fams, TEAM - len(chosen),
                         legendary_ok=tier >= 80)
            chosen = add + chosen                      # 채운 것은 앞에, 에이스는 여전히 뒤
        chosen = chosen[-TEAM:]
        team = []
        iv = min(31, 6 + (tier - 20) * 25 // 80)
        ev = 0 if tier < 60 else int(round((tier - 60) / 40.0 * 85))
        for i, k in enumerate(chosen):
            level = lv[i]
            sp = dex.legal_at(dex.by_key[k], level)
            canon = p["info"].get(k, {})
            item = H.normalize(canon.get("held"))
            team.append({
                "species": sp["internal"], "level": level,
                "ability": ability_of(dex, sp, canon.get("ability")),
                "moves": moveset(dex, sp, level, canon.get("moves") if sp["internal"] == k else canon.get("moves")),
                "held": item, "iv": iv, "ev": ev, "nature": "HARDY",
                "gender": ("N" if sp.get("femaleRatio") is None
                           else ("F" if sp.get("femaleRatio", 0.5) >= 0.5 else "M")),
            })
            if canon.get("boost"):
                # 능력치 배율 (common/battle.Fighter 가 계산한 능력치에 곱한다)
                team[-1]["boost"] = canon["boost"]
        trainers.append({
            "id": slug(p["title"]), "name": p["kr"], "en": p["title"], "role": p["role"],
            "sprite": p["sprite"], "level": tier, "type": p["spec"], "team": team,
        })
        if p.get("battle_sprite"):
            trainers[-1]["battleSprite"] = p["battle_sprite"]

    by_title = {t["en"]: t for t in trainers}
    where = place([dict(p, tier=p["tier"]) for p in people], districts)
    regions = {}
    for title, (d, why) in where.items():
        by_title[title]["region"] = d["code"]
        by_title[title]["why"] = why
        regions[d["code"]] = by_title[title]["id"]
    return trainers, regions, skipped


def check(trainers, regions, dex, districts):
    errs = []
    ids = [t["id"] for t in trainers]
    if len(set(ids)) != len(ids):
        errs.append("id 가 겹칩니다")
    if len(regions) != len(districts):
        errs.append("자리 수가 다릅니다 %d / %d" % (len(regions), len(districts)))
    tiers = collections.Counter(t["level"] for t in trainers)
    for t in trainers:
        team = t["team"]
        if len(team) != TEAM:
            errs.append("%s 팀이 %d마리" % (t["name"], len(team)))
        avg = sum(m["level"] for m in team) / float(len(team))
        if abs(avg - t["level"]) > 1e-9:
            errs.append("%s 평균 %.2f != %d" % (t["name"], avg, t["level"]))
        if len({dex.family(dex.by_key[m["species"]]) for m in team}) != len(team):
            errs.append("%s 같은 계열이 겹칩니다" % t["name"])
        for m in team:
            if m["species"] not in dex.by_key:
                errs.append("%s 모르는 종 %s" % (t["name"], m["species"]))
            if not m["moves"]:
                errs.append("%s %s 기술 없음" % (t["name"], m["species"]))
            for mv in m["moves"]:
                if mv not in dex.moves:
                    errs.append("%s 모르는 기술 %s" % (t["name"], mv))
    return errs, tiers


def report(trainers, dex, districts, path):
    by_code = {d["code"]: d for d in districts}
    kr = lambda k: dex.by_key[k]["kr"]          # noqa: E731
    lines = ["# 관장 도전 — 256곳 로스터", "",
             "레벨은 팀 여섯의 평균이다. 포켓몬 목록의 **맨 뒤가 에이스**다.", ""]
    for sido in collections.OrderedDict((d["sidonm"], 1) for d in districts):
        rows = sorted((t for t in trainers if by_code[t["region"]]["sidonm"] == sido),
                      key=lambda t: [d["code"] for d in districts].index(t["region"]))
        lines += ["## %s (%d곳)" % (sido, len(rows)), "",
                  "| 시군구 | 트레이너 | Lv | 포켓몬 | 배치 |", "|---|---|---|---|---|"]
        for t in rows:
            mons = " · ".join("%s" % kr(m["species"]) for m in t["team"])
            lines.append("| %s | **%s** (%s) | %d | %s | %s |"
                         % (by_code[t["region"]]["name"], t["name"], t["role"], t["level"],
                            mons, t.get("why", "")))
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_PATH)
    ap.add_argument("--report", default="")
    ap.add_argument("--fetch", action="store_true", help="불바피디아 원문을 다시 받는다")
    a = ap.parse_args()

    pages_path = os.path.join(CACHE, "pages.json")
    cats = json.load(open(os.path.join(CACHE, "categories.json"), encoding="utf-8"))
    if a.fetch or not os.path.exists(pages_path):
        titles = sorted(set(t for v in cats.values() for t in v))
        os.makedirs(CACHE, exist_ok=True)
        json.dump(fetch(titles), open(pages_path, "w", encoding="utf-8"), ensure_ascii=False)
    pages = json.load(open(pages_path, encoding="utf-8"))
    dex = Dex(json.load(open(DEX_PATH, encoding="utf-8")))
    districts = json.load(open(MAP_PATH, encoding="utf-8"))["sgg"]
    sprites_path = os.path.join(CACHE, "showdown_trainers.txt")
    if not os.path.exists(sprites_path):
        r = subprocess.run(["curl", "-s", "-m", "60", "https://play.pokemonshowdown.com/sprites/trainers/"],
                           capture_output=True)
        names = sorted(set(re.findall(r'href="([^"/]+)\.png"', r.stdout.decode())))
        open(sprites_path, "w").write("\n".join(names))
    sprites = set(open(sprites_path).read().split())

    trainers, regions, skipped = build(pages, cats, dex, districts, sprites)
    errs, tiers = check(trainers, regions, dex, districts)
    if errs:
        print("\n".join("  !! " + e for e in errs[:40]))
        return 1

    body = {"version": 1, "source": SOURCE, "tiers": TIERS, "trainers": trainers, "regions": regions}
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    body["digest"] = hashlib.sha256(raw.encode()).hexdigest()[:16]
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("  트레이너 %d명 · 자리 %d곳 · %.0fKB -> %s"
          % (len(trainers), len(regions), os.path.getsize(a.out) / 1024, a.out))
    print("  레벨별 인원: %s" % " ".join("%d:%d" % (k, tiers[k]) for k in TIERS))
    print("  뺀 사람 %d명: %s" % (len(skipped), ", ".join("%s(%s)" % s for s in skipped[:30])))
    if a.report:
        report(trainers, dex, districts, a.report)
        print("  로스터 -> %s" % a.report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
