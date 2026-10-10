# -*- coding: utf-8 -*-
"""탐험 파견 (1.10.4) — 박스의 포켓몬을 몇 시간 보내 두면 도구를 가져온다.

서버와 화면이 같이 쓰는 **규칙**만 여기 둔다 (어디로, 얼마나, 누가 잘하나, 몇 개를 가져오나).
무엇이 나올지 굴리는 것은 서버가 한다 (server/app/expedition.py).

## 왜

박스가 960칸인데 박스의 포켓몬은 할 일이 없었다. 타입마다 잘하는 곳이 달라서 여러 타입을 모을
까닭이 생기고, 켜 두기만 하는 사람도 하루 몇 번 들어올 까닭이 생긴다.

## 규칙

- 칸은 SLOTS 개. 한 칸에 한 마리가 나간다.
- 시간은 HOURS 중에서 고른다. **서버 시계로 흐른다** - 프로그램을 꺼도 간다.
- 갈 곳(PLACES)마다 잘 맞는 타입이 셋 있다. **타입이 맞고 레벨이 높을수록 성공도가 오른다.**
  성공도는 보낼 때 정해진다 (운이 아니다 - 보내기 전에 화면이 미리 보여 준다).

        점수 = 레벨 x 0.6  +  타입이 하나 맞으면 30 (둘 다 맞으면 40)
        75 이상 = 대성공 · 45 이상 = 성공 · 그 아래 = 보통

  Lv.75 에 타입이 맞으면 대성공이다. 타입이 안 맞으면 Lv.100 이어도 성공까지다.

- 가져오는 물건의 수는 시간과 성공도로 정해진다 (ITEMS). 길게, 잘 보낼수록 귀한 것이 잘 나온다 (TIER).
- 물건마다 등급을 먼저 뽑고(TIER), 그 등급에서 그곳의 특산물이 SPECIAL_RATE 로 나온다.
  나머지는 탐험 전용 표(LOOT)에서 나온다. 기술머신은 따로 한 번 굴린다 (TM_CHANCE).
- **돈벌이가 아니다.** 나오는 것은 노력치 열매·깃털·볼·진화의 돌, 드물게 병뚜껑이다 - 키우는 데 쓰는
  것들이고 팔아도 얼마 안 된다. 야생에서 떨어지는 표는 쓰지 않는다 (LOOT 의 설명).
  **지닌 도구는 아주 드물게만** 나온다 (HELD - 8시간 대성공도 물건 하나에 2% 가 안 된다).
  금구슬처럼 팔기만 하는 물건은 안 나온다.
- 나가 있는 포켓몬은 데리고 다닐 수 없고 (배틀에 못 나간다), 놓아줄 수 없다.
  불러들이면 빈손으로 돌아온다.
"""

SLOTS = 3
HOURS = (2, 4, 8)

GRADES = ("normal", "good", "great")
GRADE_KR = {"normal": "보통", "good": "성공", "great": "대성공"}
GREAT_AT = 75
GOOD_AT = 45
LEVEL_WEIGHT = 0.6          # 레벨 100 이 60점
MATCH_ONE = 30
MATCH_TWO = 40

# 가져오는 물건의 수: {시간: (보통, 성공, 대성공)}
ITEMS = {2: (1, 1, 1), 4: (1, 1, 2), 8: (1, 2, 3)}

# 물건 하나의 등급 확률(%): {시간: (평범, 쓸만, 희귀, 특별)}. 길수록 귀한 것이 잘 나온다.
# 다섯째 등급 '지닌 도구' 의 확률은 따로 적는다 (HELD). 평범은 나머지다.
TIERS = ("common", "uncommon", "rare", "epic", "held")
TIER_KR = {"common": "평범", "uncommon": "쓸만", "rare": "희귀", "epic": "특별", "held": "지닌 도구"}
# (맨 앞의 '평범' 은 읽기 좋으라고 적어 둔 값이다 - 실제로는 나머지가 전부 평범이다.)
TIER = {2: (87.0, 11.0, 1.5, 0.2), 4: (81.5, 15.0, 2.9, 0.5), 8: (74.6, 18.0, 5.2, 1.0)}
# 성공도가 높으면 희귀·특별·지닌 도구가 이만큼 잘 나온다 (늘어난 만큼은 평범에서 뺀다)
GRADE_LUCK = {"normal": 1.0, "good": 1.25, "great": 1.6}
SPECIAL_RATE = 0.4          # 그 등급에 특산물이 있을 때, 특산물이 나올 확률

# **지닌 도구** (사용자 결정, 2026-10-10: "지닌 도구류는 있어야 한다, 정말 희귀한 확률로. 금구슬류는 없어도 된다").
# 물건 하나가 지닌 도구일 확률(%). 무엇이 나오는지는 야생에서 떨어지는 지닌 도구 가운데 HELD_RARITIES 인
# 것을 그 가중치대로 뽑는다 - 타입 강화 도구(검은띠·플레이트 ...)가 대부분이고, 파워 시리즈·기합의머리띠가
# 가끔, 구애 시리즈·생명의구슬·먹다남은음식은 그 안에서도 60번에 한 번이다. (배틀용 열매는 야생에서
# 흔하게 떨어지므로 뺐다.) 평균 2,260원어치라, 이만큼 넣은 대신 TIER 의 희귀·쓸만을 조금 깎아
# 하루 최대(칸 셋 x 8시간 대성공 x 세 번)를 1만 원어치 안쪽으로 그대로 뒀다.
HELD = {2: 0.3, 4: 0.6, 8: 1.2}
HELD_RARITIES = ("uncommon", "rare", "epic")

# 탐험에서 나오는 물건: {등급: [(도구 id, 가중치)]}. ('지닌 도구' 등급은 위의 HELD 를 보라.)
#
# **야생에서 떨어지는 표를 쓰지 않는다** (사용자 결정, 2026-10-10: "수치가 너무 후하다. 나중에 성격민트·
# 특성패치가 뽑기로 생기는데 돈이 너무 쉽게 벌리면 다들 돈으로 해결한다"). 처음에는 그 표를 등급으로
# 나눠 썼더니 지닌 도구(팔면 500 ~ 7,500원)가 흔하게 섞여 8시간 대성공 한 번이 4천 원어치, 하루 최대
# 4만 원어치였다. 네 등급에서는 여기 적은 것만 나온다 - 키우는 데 쓰는 것들이고, 팔았을 때의 값은
#
#     평범 40 ~ 250원 (노력치 열매, 작은버섯)      쓸만 300 ~ 500원 (노력치 깃털, 볼)
#     희귀 1,000 ~ 2,500원 (진화의 돌)             특별 2,500 ~ 5,000원 (병뚜껑)
#
# 그래서 8시간 대성공 한 번이 1천 원어치쯤, 칸 셋을 하루 세 번 다 돌려도 1만 원어치가 안 된다
# (야생 드랍 하나의 평균이 1,030원이다). 값을 더 낮추려면 ITEMS 와 TIER 를 만진다.
_BERRIES = ("POMEGBERRY", "KELPSYBERRY", "QUALOTBERRY", "HONDEWBERRY", "GREPABERRY", "TAMATOBERRY")
_WINGS = ("HEALTHWING", "MUSCLEWING", "RESISTWING", "GENIUSWING", "CLEVERWING", "SWIFTWING")
_STONES = ("FIRESTONE", "WATERSTONE", "THUNDERSTONE", "LEAFSTONE", "MOONSTONE", "SUNSTONE", "ICESTONE",
           "DUSKSTONE", "DAWNSTONE", "SHINYSTONE")
LOOT = {
    "common": [(i, 10) for i in _BERRIES] + [("TINYMUSHROOM", 6)],
    "uncommon": [(i, 10) for i in _WINGS] + [("GREATBALL", 8), ("ULTRABALL", 4)],
    "rare": [(i, 10) for i in _STONES],
    "epic": [("BOTTLECAP", 10), ("GOLDBOTTLECAP", 2)],
}

# 기술머신 한 장을 얹어 올 확률 (아직 없는 것 중에서). 곳마다 곱이 다르다 (유적이 높다).
# 기술머신은 사고팔 수 없는 물건이라 돈과는 상관없다.
TM_CHANCE = {2: 0.03, 4: 0.06, 8: 0.12}
TM_LUCK = {"normal": 1.0, "good": 1.25, "great": 1.5}

# 갈 곳. types = 잘 맞는 타입 (열여덟 타입이 한 곳씩). special = 그곳의 특산물 {등급: [도구 id]}.
PLACES = [
    {"id": "forest", "kr": "숲", "types": ["GRASS", "BUG", "POISON"], "tm": 1.0,
     "hint": "노력치 열매 · 버섯 · 리프의돌",
     "special": {"common": list(_BERRIES) + ["TINYMUSHROOM"],
                 "rare": ["LEAFSTONE", "SUNSTONE", "SWEETAPPLE", "TARTAPPLE", "SYRUPYAPPLE"]}},
    {"id": "cave", "kr": "동굴", "types": ["ROCK", "GROUND", "FIGHTING"], "tm": 1.0,
     "hint": "달의돌 · 어둠의돌 · 프로텍터",
     "special": {"rare": ["MOONSTONE", "DUSKSTONE", "OVALSTONE", "PROTECTOR", "KINGSROCK", "RAZORFANG"]}},
    {"id": "sea", "kr": "바다", "types": ["WATER", "FLYING", "ELECTRIC"], "tm": 1.0,
     "hint": "깃털 · 물의돌 · 천둥의돌",
     "special": {"uncommon": ["HEALTHWING", "SWIFTWING"],
                 "rare": ["WATERSTONE", "THUNDERSTONE", "DEEPSEATOOTH", "DEEPSEASCALE", "PRISMSCALE",
                          "DRAGONSCALE"]}},
    {"id": "volcano", "kr": "화산", "types": ["FIRE", "DRAGON", "STEEL"], "tm": 1.0,
     "hint": "깃털 · 불꽃의돌 · 금속코트",
     "special": {"uncommon": ["MUSCLEWING", "RESISTWING"],
                 "rare": ["FIRESTONE", "MAGMARIZER", "ELECTIRIZER", "METALCOAT", "METALALLOY"]}},
    {"id": "snow", "kr": "설산", "types": ["ICE", "NORMAL", "FAIRY"], "tm": 1.0,
     "hint": "깃털 · 얼음의돌 · 빛의돌",
     "special": {"uncommon": ["GENIUSWING", "CLEVERWING"],
                 "rare": ["ICESTONE", "SHINYSTONE", "DAWNSTONE", "RAZORCLAW"]}},
    {"id": "ruins", "kr": "유적", "types": ["PSYCHIC", "GHOST", "DARK"], "tm": 1.6,
     "hint": "기술머신 · 영계의천 · 업그레이드",
     "special": {"rare": ["REAPERCLOTH", "DUBIOUSDISC", "UPGRADE", "SCROLLOFDARKNESS"]}},
]
_BY_ID = dict((p["id"], p) for p in PLACES)


def place(place_id):
    return _BY_ID.get(place_id)


def matches(types, place_id):
    """그 포켓몬의 타입 가운데 그곳과 맞는 것의 수 (0 ~ 2)."""
    p = place(place_id) or {}
    good = set(p.get("types") or ())
    return len([t for t in dict.fromkeys(types or ()) if t in good])


def score(level, types, place_id):
    """성공도 점수 (0 ~ 100). 레벨과 타입으로만 정해진다."""
    n = matches(types, place_id)
    bonus = MATCH_TWO if n >= 2 else (MATCH_ONE if n == 1 else 0)
    return int(min(100, max(0, int(level or 0)) * LEVEL_WEIGHT + bonus))


def grade(points):
    if points >= GREAT_AT:
        return "great"
    return "good" if points >= GOOD_AT else "normal"


def grade_of(level, types, place_id):
    return grade(score(level, types, place_id))


def item_count(hours, grade_id):
    """보따리에 든 물건의 수."""
    row = ITEMS.get(int(hours))
    if not row:
        return 0
    return row[GRADES.index(grade_id) if grade_id in GRADES else 0]


def tier_odds(hours, grade_id):
    """물건 하나의 등급 확률 [(등급, 확률)] - 합은 1.0."""
    h = int(hours) if int(hours) in TIER else HOURS[0]
    base = TIER[h]
    luck = GRADE_LUCK.get(grade_id, 1.0)
    rare, epic, held = base[2] * luck, base[3] * luck, HELD.get(h, 0.0) * luck
    common = max(0.0, 100.0 - base[1] - rare - epic - held)
    return [("common", common / 100.0), ("uncommon", base[1] / 100.0), ("rare", rare / 100.0),
            ("epic", epic / 100.0), ("held", held / 100.0)]


def tm_chance(hours, grade_id, place_id):
    p = place(place_id) or {}
    return min(1.0, TM_CHANCE.get(int(hours), 0.0) * TM_LUCK.get(grade_id, 1.0) * float(p.get("tm", 1.0)))


def hours_text(sec):
    """남은 시간을 사람 말로: '3시간 20분', '12분', '곧'."""
    sec = int(max(0, sec))
    if sec < 60:
        return "곧" if sec > 0 else "돌아옴"
    h, m = sec // 3600, (sec % 3600) // 60
    if h and m:
        return "%d시간 %d분" % (h, m)
    return "%d시간" % h if h else "%d분" % m
