# -*- coding: utf-8 -*-
"""지닌 도구 — 배틀 안에서 무엇을 하는지.

PokeAPI 는 도구의 **이름·설명·가격**만 준다. 무엇을 하는지는 구조화된
자료가 없어서 여기 손으로 적는다. 목록은 PokeAPI 가 '지닐 수 있고 배틀에
관여한다(holdable-passive/active)' 고 표시한 141종에서, 이 엔진에 없는
개념(날씨·벽·교체·이중 배틀·콘테스트)에 걸린 20종을 뺀 121종이었다.
어느 것을 왜 뺐는지는 tools/build_items.py 의 HELD_SKIP 에 있다.
1.13 에서 그동안 뺐던 것과 빠져 있던 것(울퉁불퉁멧·돌격조끼·주얼·시드·메모리·전설의 구슬·
오거폰의 가면 …)을 전부 넣었다 - 상점에서만 판다 (tools/add_held.py).

**규칙 둘.**

1. 도구가 없으면 이 파일은 아무것도 하지 않는다. 난수도 안 쓴다.
   PvP 는 시드 하나로 로그를 다시 만들 수 있어야 하고(party_battle),
   지금까지 저장된 판들은 도구 없이 계산된 것이라 그 로그가 한 글자도
   달라지면 안 된다. common/test_held.py 가 이걸 요약값으로 지킨다.
2. 열매처럼 한 번 쓰면 사라지는 도구는 **그 판에서만** 사라진다.
   판이 끝나면 다시 들고 있다. 본가와 다르지만, 비동기 PvP 에서 열매가
   진짜로 없어지려면 로그를 재생하는 쪽이 아니라 계산하는 쪽이 가방까지
   고쳐야 하고, 그러면 '자는 동안 열매를 다 뺏겼다' 가 된다.

훅은 battle.Battle 이 정해진 자리에서 부른다. 각 훅은 먼저 도구가
있는지만 보고 없으면 바로 돌아간다 - 위 규칙 1 이다.
"""
from . import movecalc as MC
from . import tera as TR
from . import zmoves as ZM

# 도구 id -> 한글 이름. 로그의 문구에 쓴다. 서버의 items.json 과 같은
# 출처(PokeAPI CSV)라 build_items 가 어긋나면 검사에서 잡힌다.
KR = {
    "CHERIBERRY": "버치열매", "CHESTOBERRY": "유루열매", "PECHABERRY": "복슝열매",
    "RAWSTBERRY": "복분열매", "ASPEARBERRY": "배리열매", "LEPPABERRY": "과사열매",
    "ORANBERRY": "오랭열매", "LUMBERRY": "리샘열매", "SITRUSBERRY": "자뭉열매",
    "FIGYBERRY": "무화열매", "WIKIBERRY": "위키열매", "MAGOBERRY": "마고열매",
    "AGUAVBERRY": "아바열매", "IAPAPABERRY": "파야열매", "OCCABERRY": "오카열매",
    "PASSHOBERRY": "꼬시개열매", "WACANBERRY": "초나열매", "RINDOBERRY": "린드열매",
    "YACHEBERRY": "플카열매", "CHOPLEBERRY": "로플열매", "KEBIABERRY": "으름열매",
    "SHUCABERRY": "슈캐열매", "COBABERRY": "바코열매", "PAYAPABERRY": "야파열매",
    "TANGABERRY": "리체열매", "CHARTIBERRY": "루미열매", "KASIBBERRY": "수불열매",
    "HABANBERRY": "하반열매", "COLBURBERRY": "마코열매", "BABIRIBERRY": "바리비열매",
    "CHILANBERRY": "카리열매", "LIECHIBERRY": "치리열매", "GANLONBERRY": "용아열매",
    "SALACBERRY": "캄라열매", "PETAYABERRY": "야타비열매", "APICOTBERRY": "규살열매",
    "LANSATBERRY": "랑사열매", "STARFBERRY": "스타열매", "ENIGMABERRY": "의문열매",
    "MICLEBERRY": "미클열매", "CUSTAPBERRY": "애슈열매", "JABOCABERRY": "자보열매",
    "ROWAPBERRY": "애터열매", "BRIGHTPOWDER": "반짝가루", "WHITEHERB": "하양허브",
    "MACHOBRACE": "교정깁스", "QUICKCLAW": "선제공격손톱", "SOOTHEBELL": "평온의방울",
    "CHOICEBAND": "구애머리띠", "KINGSROCK": "왕의징표석", "SILVERPOWDER": "은빛가루",
    "SMOKEBALL": "연막탄", "FOCUSBAND": "기합의머리띠", "LUCKYEGG": "행복의알",
    "SCOPELENS": "초점렌즈", "METALCOAT": "금속코트", "LEFTOVERS": "먹다남은음식",
    "SOFTSAND": "부드러운모래", "HARDSTONE": "딱딱한돌", "MIRACLESEED": "기적의씨",
    "BLACKGLASSES": "검은안경", "BLACKBELT": "검은띠", "MAGNET": "자석",
    "MYSTICWATER": "신비의물방울", "SHARPBEAK": "예리한부리", "POISONBARB": "독바늘",
    "NEVERMELTICE": "녹지않는얼음", "SPELLTAG": "저주의부적", "TWISTEDSPOON": "휘어진스푼",
    "CHARCOAL": "목탄", "DRAGONFANG": "용의이빨", "SILKSCARF": "실크스카프",
    "SHELLBELL": "조개껍질방울", "SEAINCENSE": "바닷물향로", "LAXINCENSE": "무사태평향로",
    "WIDELENS": "광각렌즈", "MUSCLEBAND": "힘의머리띠", "WISEGLASSES": "박식안경",
    "EXPERTBELT": "달인의띠", "LIFEORB": "생명의구슬", "TOXICORB": "맹독구슬",
    "FLAMEORB": "화염구슬", "FOCUSSASH": "기합의띠", "ZOOMLENS": "포커스렌즈",
    "METRONOME": "메트로놈", "IRONBALL": "검은철구", "LAGGINGTAIL": "느림보꼬리",
    "BLACKSLUDGE": "검은오물", "CHOICESCARF": "구애스카프", "STICKYBARB": "끈적끈적바늘",
    "POWERBRACER": "파워리스트", "POWERBELT": "파워벨트", "POWERLENS": "파워렌즈",
    "POWERBAND": "파워밴드", "POWERANKLET": "파워앵클릿", "POWERWEIGHT": "파워웨이트",
    "BIGROOT": "큰뿌리", "CHOICESPECS": "구애안경", "FLAMEPLATE": "불구슬플레이트",
    "SPLASHPLATE": "물방울플레이트", "ZAPPLATE": "우레플레이트", "MEADOWPLATE": "초록플레이트",
    "ICICLEPLATE": "고드름플레이트", "FISTPLATE": "주먹플레이트", "TOXICPLATE": "맹독플레이트",
    "EARTHPLATE": "대지플레이트", "SKYPLATE": "푸른하늘플레이트", "MINDPLATE": "이상한플레이트",
    "INSECTPLATE": "비단벌레플레이트", "STONEPLATE": "암석플레이트",
    "SPOOKYPLATE": "원령플레이트", "DRACOPLATE": "용의플레이트", "DREADPLATE": "공포플레이트",
    "IRONPLATE": "강철플레이트", "ODDINCENSE": "괴상한향로", "ROCKINCENSE": "암석향로",
    "FULLINCENSE": "만복향로", "WAVEINCENSE": "잔물결향로", "ROSEINCENSE": "꽃향로",
    "RAZORCLAW": "예리한손톱", "RAZORFANG": "예리한이빨",
}
# 1.13: 그동안 없던 지닌 도구 (사용자 요청 "아직 미추가된 도구들 전부"). 이름은 PokeAPI 한국어 그대로.
# 예전에 HELD_SKIP 으로 뺐던 것(날씨 바위·빛의점토·파워풀허브·멘탈허브·끈기갈고리손톱·아름다운허물·빨간실·
# 시몬열매)도 넣는다 - 그 뒤로 엔진에 날씨·필드·벽·교체·충전 기술·구속·혼란이 다 생겼다.
KR.update({
    # 배틀 도구
    "MENTALHERB": "멘탈허브", "LIGHTCLAY": "빛의점토", "POWERHERB": "파워풀허브", "DESTINYKNOT": "빨간실",
    "ICYROCK": "차가운바위", "SMOOTHROCK": "보송보송바위", "HEATROCK": "뜨거운바위", "DAMPROCK": "축축한바위",
    "GRIPCLAW": "끈기갈고리손톱", "SHEDSHELL": "아름다운허물", "EVIOLITE": "진화의휘석", "FLOATSTONE": "가벼운돌",
    "ROCKYHELMET": "울퉁불퉁멧", "AIRBALLOON": "풍선", "REDCARD": "레드카드", "RINGTARGET": "겨냥표적",
    "BINDINGBAND": "조임밴드", "ABSORBBULB": "구근", "CELLBATTERY": "충전지", "EJECTBUTTON": "탈출버튼",
    "WEAKNESSPOLICY": "약점보험", "ASSAULTVEST": "돌격조끼", "LUMINOUSMOSS": "빛이끼", "SNOWBALL": "눈덩이",
    "SAFETYGOGGLES": "방진고글", "ADRENALINEORB": "주눅구슬", "TERRAINEXTENDER": "그라운드코트",
    "PROTECTIVEPADS": "방호패드", "ELECTRICSEED": "일렉트릭시드", "PSYCHICSEED": "사이코시드",
    "MISTYSEED": "미스트시드", "GRASSYSEED": "그래스시드", "THROATSPRAY": "목스프레이", "EJECTPACK": "탈출팩",
    "HEAVYDUTYBOOTS": "통굽부츠", "BLUNDERPOLICY": "허탕보험", "ROOMSERVICE": "룸서비스",
    "UTILITYUMBRELLA": "만능우산", "BOOSTERENERGY": "부스트에너지", "ABILITYSHIELD": "특성가드",
    "CLEARAMULET": "클리어참", "MIRRORHERB": "흉내허브", "PUNCHINGGLOVE": "펀치글러브", "COVERTCLOAK": "은밀망토",
    "LOADEDDICE": "속임수주사위", "FAIRYFEATHER": "요정의깃털",
    "PERSIMBERRY": "시몬열매", "ROSELIBERRY": "로셀열매", "KEEBERRY": "악키열매", "MARANGABERRY": "타라프열매",
    # 그 포켓몬 전용 (전설·환상 포함)
    "LIGHTBALL": "전기구슬", "LUCKYPUNCH": "럭키펀치", "METALPOWDER": "금속파우더", "THICKCLUB": "굵은뼈",
    "STICK": "대파", "QUICKPOWDER": "스피드파우더", "DEEPSEATOOTH": "심해의이빨", "DEEPSEASCALE": "심해의비늘",
    "SOULDEW": "마음의물방울", "ADAMANTORB": "금강옥", "LUSTROUSORB": "백옥", "GRISEOUSORB": "백금옥",
    "ADAMANTCRYSTAL": "큰금강옥", "LUSTROUSGLOBE": "큰백옥", "GRISEOUSCORE": "큰백금옥",
    "RUSTEDSWORD": "녹슨검", "RUSTEDSHIELD": "녹슨방패", "PIXIEPLATE": "정령플레이트",
    "DOUSEDRIVE": "아쿠아카세트", "SHOCKDRIVE": "번개카세트", "BURNDRIVE": "블레이즈카세트", "CHILLDRIVE": "프리즈카세트",
    "WELLSPRINGMASK": "우물의가면", "HEARTHFLAMEMASK": "화덕의가면", "CORNERSTONEMASK": "주춧돌의가면",
    "REDORB": "주홍구슬", "BLUEORB": "쪽빛구슬",
    # 메모리 (실버디: 타입·멀티어택)
    "FIGHTINGMEMORY": "파이팅메모리", "FLYINGMEMORY": "플라잉메모리", "POISONMEMORY": "포이즌메모리",
    "GROUNDMEMORY": "그라운드메모리", "ROCKMEMORY": "록메모리", "BUGMEMORY": "버그메모리",
    "GHOSTMEMORY": "고스트메모리", "STEELMEMORY": "스틸메모리", "FIREMEMORY": "파이어메모리",
    "WATERMEMORY": "워터메모리", "GRASSMEMORY": "그래스메모리", "ELECTRICMEMORY": "일렉트릭메모리",
    "PSYCHICMEMORY": "사이킥메모리", "ICEMEMORY": "아이스메모리", "DRAGONMEMORY": "드래곤메모리",
    "DARKMEMORY": "다크메모리", "FAIRYMEMORY": "페어리메모리",
    # 주얼 (그 타입 첫 공격 1.3배, 한 번)
    "FIREGEM": "불꽃주얼", "WATERGEM": "물주얼", "ELECTRICGEM": "전기주얼", "GRASSGEM": "풀주얼",
    "ICEGEM": "얼음주얼", "FIGHTINGGEM": "격투주얼", "POISONGEM": "독주얼", "GROUNDGEM": "땅주얼",
    "FLYINGGEM": "비행주얼", "PSYCHICGEM": "에스퍼주얼", "BUGGEM": "벌레주얼", "ROCKGEM": "바위주얼",
    "GHOSTGEM": "고스트주얼", "DARKGEM": "악주얼", "STEELGEM": "강철주얼", "DRAGONGEM": "드래곤주얼",
    "NORMALGEM": "노말주얼", "FAIRYGEM": "페어리주얼",
})

# ---------------------------------------------------------------- 분류표
# 그 타입 기술의 위력 1.2배 (타입 강화 도구 22 + 플레이트 16)
TYPE_BOOST = {
    "SILVERPOWDER": "BUG", "METALCOAT": "STEEL", "SOFTSAND": "GROUND",
    "HARDSTONE": "ROCK", "MIRACLESEED": "GRASS", "BLACKGLASSES": "DARK",
    "BLACKBELT": "FIGHTING", "MAGNET": "ELECTRIC", "MYSTICWATER": "WATER",
    "SHARPBEAK": "FLYING", "POISONBARB": "POISON", "NEVERMELTICE": "ICE",
    "SPELLTAG": "GHOST", "TWISTEDSPOON": "PSYCHIC", "CHARCOAL": "FIRE",
    "DRAGONFANG": "DRAGON", "SILKSCARF": "NORMAL", "SEAINCENSE": "WATER",
    "ODDINCENSE": "PSYCHIC", "ROCKINCENSE": "ROCK", "WAVEINCENSE": "WATER",
    "ROSEINCENSE": "GRASS",
    "FLAMEPLATE": "FIRE", "SPLASHPLATE": "WATER", "ZAPPLATE": "ELECTRIC",
    "MEADOWPLATE": "GRASS", "ICICLEPLATE": "ICE", "FISTPLATE": "FIGHTING",
    "TOXICPLATE": "POISON", "EARTHPLATE": "GROUND", "SKYPLATE": "FLYING",
    "MINDPLATE": "PSYCHIC", "INSECTPLATE": "BUG", "STONEPLATE": "ROCK",
    "SPOOKYPLATE": "GHOST", "DRACOPLATE": "DRAGON", "DREADPLATE": "DARK",
    "IRONPLATE": "STEEL",
    "FAIRYFEATHER": "FAIRY", "PIXIEPLATE": "FAIRY",          # 1.13: 페어리에도 강화 도구가 생겼다
}
TYPE_BOOST_MULT = 1.2

# 그 타입의 효과가 굉장한 기술을 한 번 반감 (카리열매는 노말이면 언제나)
RESIST_BERRY = {
    "OCCABERRY": "FIRE", "PASSHOBERRY": "WATER", "WACANBERRY": "ELECTRIC",
    "RINDOBERRY": "GRASS", "YACHEBERRY": "ICE", "CHOPLEBERRY": "FIGHTING",
    "KEBIABERRY": "POISON", "SHUCABERRY": "GROUND", "COBABERRY": "FLYING",
    "PAYAPABERRY": "PSYCHIC", "TANGABERRY": "BUG", "CHARTIBERRY": "ROCK",
    "KASIBBERRY": "GHOST", "HABANBERRY": "DRAGON", "COLBURBERRY": "DARK",
    "BABIRIBERRY": "STEEL", "CHILANBERRY": "NORMAL", "ROSELIBERRY": "FAIRY",
}

# 상태이상에 걸리는 순간 고친다. "*" 는 무엇이든.
CURE_BERRY = {
    "CHERIBERRY": "paralysis", "CHESTOBERRY": "sleep", "PECHABERRY": "poison",
    "RAWSTBERRY": "burn", "ASPEARBERRY": "freeze", "LUMBERRY": "*",
}

# 체력이 (비율) 이하가 되면 회복. ("flat", n) 은 n 만큼, ("frac", r) 은 최대체력의 r.
HEAL_BERRY = {
    "ORANBERRY": (0.5, "flat", 10),
    "SITRUSBERRY": (0.5, "frac", 0.25),
    "FIGYBERRY": (0.25, "frac", 1 / 3.0), "WIKIBERRY": (0.25, "frac", 1 / 3.0),
    "MAGOBERRY": (0.25, "frac", 1 / 3.0), "AGUAVBERRY": (0.25, "frac", 1 / 3.0),
    "IAPAPABERRY": (0.25, "frac", 1 / 3.0),
}

# 체력이 1/4 이하가 되면 발동. 애슈열매(먼저 움직임)는 순서 훅에서 본다.
PINCH_BERRY = {
    "LIECHIBERRY": ("stat", "atk"), "GANLONBERRY": ("stat", "def"),
    "SALACBERRY": ("stat", "spe"), "PETAYABERRY": ("stat", "spa"),
    "APICOTBERRY": ("stat", "spd"), "STARFBERRY": ("random", None),
    "LANSATBERRY": ("crit", None), "MICLEBERRY": ("acc", None),
}

# 구애: 그 능력 1.5배, 대신 처음 쓴 기술만 계속 쓴다 (판이 끝날 때까지).
CHOICE = {"CHOICEBAND": "atk", "CHOICESPECS": "spa", "CHOICESCARF": "spe"}

# 파워 시리즈: 쓰러뜨렸을 때 그 노력치 +8, 대신 스피드 절반.
POWER_EV = {"POWERBRACER": "atk", "POWERBELT": "def", "POWERLENS": "spa",
            "POWERBAND": "spd", "POWERANKLET": "spe", "POWERWEIGHT": "hp"}

SLOW = set(POWER_EV) | {"IRONBALL", "MACHOBRACE"}        # 스피드 절반
LAST = {"LAGGINGTAIL", "FULLINCENSE"}                      # 같은 우선도면 나중에
CRIT_UP = {"SCOPELENS": 1, "RAZORCLAW": 1}                 # 급소 단계 +1
FLINCH_10 = {"KINGSROCK", "RAZORFANG"}                     # 10% 풀죽음
EVADE = {"BRIGHTPOWDER", "LAXINCENSE"}                     # 상대 명중 0.9

# 배틀 밖에서만 뜻이 있는 것들. 서버가 본다.
EXP_ITEMS = {"LUCKYEGG": 1.5}
HAPPINESS_ITEMS = {"SOOTHEBELL": 1.5}

# ---------------------------------------------------------------- 1.13 의 분류표
# 맞으면 그 능력이 오르는 것 (한 번): 그 타입에 맞으면
HIT_TYPE_BOOST = {"ABSORBBULB": ("WATER", "spa"), "CELLBATTERY": ("ELECTRIC", "atk"),
                  "LUMINOUSMOSS": ("WATER", "spd"), "SNOWBALL": ("ICE", "atk")}
# 맞으면 그 능력이 오르는 열매 (한 번): 그 분류의 기술에 맞으면
HIT_CAT_BERRY = {"KEEBERRY": ("physical", "def"), "MARANGABERRY": ("special", "spd")}
# 그 필드가 깔려 있으면 그 능력이 한 단계 (한 번)
SEED = {"ELECTRICSEED": ("electric", "def"), "GRASSYSEED": ("grassy", "def"),
        "MISTYSEED": ("misty", "spd"), "PSYCHICSEED": ("psychic", "spd")}
# 그 날씨를 부르면 8턴
WEATHER_ROCK = {"ICYROCK": ("hail", "snow"), "SMOOTHROCK": ("sand",), "HEATROCK": ("sun",), "DAMPROCK": ("rain",)}
# 주얼: 그 타입 기술을 처음 쓸 때 위력 1.3배 (한 번)
GEM = dict((k, k[:-3]) for k in KR if k.endswith("GEM"))
GEM_MULT = 1.3
# 그 포켓몬이 지니면 능력치 x배: 도구 -> (종들, 능력들, 배율). 메타몽 것은 변신하지 않았을 때만.
SPECIES_STAT = {
    "LIGHTBALL": ({"PIKACHU"}, ("atk", "spa"), 2.0),
    "THICKCLUB": ({"CUBONE", "MAROWAK"}, ("atk",), 2.0),
    "DEEPSEATOOTH": ({"CLAMPERL"}, ("spa",), 2.0),
    "DEEPSEASCALE": ({"CLAMPERL"}, ("spd",), 2.0),
    "METALPOWDER": ({"DITTO"}, ("def",), 2.0),
    "QUICKPOWDER": ({"DITTO"}, ("spe",), 2.0),
}
# 그 포켓몬이 지니면 급소 +2
SPECIES_CRIT = {"LUCKYPUNCH": {"CHANSEY"}, "STICK": {"FARFETCHD", "SIRFETCHD"}}
# 그 포켓몬이 지니면 그 타입 기술 1.2배 (전설의 옥·마음의물방울)
SPECIES_POWER = {
    "SOULDEW": ({"LATIOS", "LATIAS"}, ("DRAGON", "PSYCHIC")),
    "ADAMANTORB": ({"DIALGA"}, ("DRAGON", "STEEL")), "ADAMANTCRYSTAL": ({"DIALGA"}, ("DRAGON", "STEEL")),
    "LUSTROUSORB": ({"PALKIA"}, ("DRAGON", "WATER")), "LUSTROUSGLOBE": ({"PALKIA"}, ("DRAGON", "WATER")),
    "GRISEOUSORB": ({"GIRATINA"}, ("DRAGON", "GHOST")), "GRISEOUSCORE": ({"GIRATINA"}, ("DRAGON", "GHOST")),
}
# 오거폰의 가면: 기술 위력 1.2배, 덩굴방망이가 그 타입 (폼은 도감 forms 가 바꾼다)
MASK = {"WELLSPRINGMASK": "WATER", "HEARTHFLAMEMASK": "FIRE", "CORNERSTONEMASK": "ROCK"}
MASK_MULT = 1.2
MEMORY = dict((k, k[:-6]) for k in KR if k.endswith("MEMORY"))
DRIVE = {"DOUSEDRIVE": "WATER", "SHOCKDRIVE": "ELECTRIC", "BURNDRIVE": "FIRE", "CHILLDRIVE": "ICE"}
PLATES = set(k for k in KR if k.endswith("PLATE"))
# 뺏기지도 떨어지지도 않는 것 (메가스톤·Z크리스탈 말고). 폼이 걸린 도구다.
LOCKED = {"WELLSPRINGMASK", "HEARTHFLAMEMASK", "CORNERSTONEMASK", "GRISEOUSCORE", "ADAMANTCRYSTAL",
          "LUSTROUSGLOBE", "RUSTEDSWORD", "RUSTEDSHIELD", "REDORB", "BLUEORB", "BOOSTERENERGY"}
# 그 포켓몬이 지녔을 때만 잠긴다 (플레이트 = 아르세우스, 메모리 = 실버디, 카세트 = 게노세크트)
LOCKED_FOR = dict([(k, "ARCEUS") for k in PLATES] + [(k, "SILVALLY") for k in MEMORY]
                  + [(k, "GENESECT") for k in DRIVE])
MENTAL_CONDS = ("attract", "taunt", "encore", "torment", "disable", "healblock")

ALL = frozenset(KR)

# ---- 종류 (1.13.4, 게시판 #323 '도구가 많아져 정렬이 마구잡이 - 이름순 / 특성순') ----
# 가방의 '종류순' 이 지닌 도구를 하는 일로 묶어 이 차례로 보여 준다. 위의 효과 표로 먼저 가르고,
# 거기 없는 것은 아래 네 묶음에 적는다. 어디에도 없으면 '기타' (새 도구가 생기면 여기도 적을 것).
GROUPS = (("berry", "열매"), ("type", "타입 강화"), ("attack", "공격 강화"), ("recover", "회복 · 버티기"),
          ("once", "한 번 발동"), ("guard", "상태 · 방어"), ("field", "날씨 · 필드"), ("train", "육성"),
          ("species", "전용 도구"), ("tera", "테라피스"), ("etc", "기타"))      # 테라피스 (2.5.1 - 지니는 도구)
ATTACK = {"CHOICEBAND", "CHOICESPECS", "CHOICESCARF", "LIFEORB", "EXPERTBELT", "MUSCLEBAND", "WISEGLASSES",
          "METRONOME", "SCOPELENS", "WIDELENS", "ZOOMLENS", "LOADEDDICE", "PUNCHINGGLOVE", "QUICKCLAW"}
RECOVER = {"LEFTOVERS", "BLACKSLUDGE", "SHELLBELL", "BIGROOT", "FOCUSSASH", "FOCUSBAND", "ASSAULTVEST",
           "EVIOLITE", "ROCKYHELMET"}
ONCE = {"WEAKNESSPOLICY", "BLUNDERPOLICY", "WHITEHERB", "MENTALHERB", "POWERHERB", "MIRRORHERB",
        "ADRENALINEORB", "THROATSPRAY", "ROOMSERVICE", "EJECTBUTTON", "EJECTPACK", "REDCARD", "AIRBALLOON"}
GUARD = {"FLAMEORB", "TOXICORB", "SAFETYGOGGLES", "COVERTCLOAK", "CLEARAMULET", "ABILITYSHIELD",
         "HEAVYDUTYBOOTS", "PROTECTIVEPADS", "UTILITYUMBRELLA", "SHEDSHELL", "BRIGHTPOWDER", "LAXINCENSE"}
_GROUP_KR = dict(GROUPS)


def group(item):
    """지닌 도구의 종류 열쇠 (GROUPS 의 하나). 모르는 도구는 'etc'."""
    item = item or ""
    if TR.is_shard(item):
        return "tera"
    if item.endswith("BERRY"):
        return "berry"
    if item in SPECIES_STAT or item in SPECIES_CRIT or item in SPECIES_POWER or item in LOCKED \
            or item in MEMORY or item in DRIVE or item in MASK:
        return "species"
    if item in TYPE_BOOST or item in PLATES or item in GEM:
        return "type"
    if item in ATTACK:
        return "attack"
    if item in RECOVER:
        return "recover"
    if item in ONCE or item in HIT_TYPE_BOOST:
        return "once"
    if item in GUARD:
        return "guard"
    if item in WEATHER_ROCK or item in SEED or item in ("LIGHTCLAY", "TERRAINEXTENDER"):
        return "field"
    if item in POWER_EV or item in EXP_ITEMS or item in HAPPINESS_ITEMS or item == "MACHOBRACE":
        return "train"
    return "etc"


def group_kr(key):
    return _GROUP_KR.get(key, key)

# 메가스톤 (시즌 3). 배틀 효과는 없고 메가진화의 열쇠다. 도감의 megas 에서
# 채운다(register_megas) - 여기 없으면 normalize 가 버려서, 들리지도 못하고
# 배틀에서도 사라진다.
MEGA = {}


def register_megas(dex):
    for m in getattr(dex, "megas", None) or []:
        sid = m.get("megaStone")
        if sid:
            MEGA[sid] = m.get("megaStoneKr") or sid


def is_mega_stone(item):
    return bool(item) and item in MEGA


def stuck(item, f=None):
    """뺏기지도 떨어지지도 않는 도구 - 메가스톤과 Z크리스탈 (본가와 같다), 폼이 걸린 도구 (1.13),
    테라피스 (2.5.1 - 지니는 동안 테라스탈한다. Z크리스탈처럼 잠근다).

    트릭·바꿔치기·탁쳐서떨구기·도둑질·나쁜손버릇·매지션이 이것을 본다. f(그 도구를 지닌 포켓몬)를
    주면 플레이트·메모리·카세트는 그 전용 포켓몬(아르세우스·실버디·게노세크트)이 지녔을 때만 잠근다.
    """
    if not item:
        return False
    if is_mega_stone(item) or ZM.is_crystal(item) or TR.is_shard(item) or item in LOCKED:
        return True
    sp = LOCKED_FOR.get(item)
    return bool(sp and f is not None and _species(f) == sp)


def _species(f):
    return (getattr(f, "mon", None) or {}).get("species")


def normalize(v):
    """DB 나 요청에서 온 값을 도구 id 로. 모르는 것은 None."""
    if not v:
        return None
    k = "".join(c for c in str(v).upper() if c.isalnum())
    return k if (k in ALL or k in MEGA or k in ZM.CRYSTALS or TR.is_shard(k)) else None


def name(item):
    if TR.is_shard(item):
        return "테라피스 " + _TYPE_KR.get(TR.shard_type(item), "")
    return KR.get(item) or MEGA.get(item) or ZM.CRYSTALS.get(item) or (item or "")


# ---------------------------------------------------------------- 도우미
def _say(ev, who, text):
    ev.append({"t": "msg", "who": who, "text": text})


def _heal(f, who, amount, ev, text):
    amount = max(1, int(amount))
    if f.hp >= f.maxhp:
        return 0
    amount = min(amount, f.maxhp - f.hp)
    f.hp += amount
    ev.append({"t": "heal", "who": who, "amount": amount, "hp": f.hp,
               "maxhp": f.maxhp, "text": text})
    return amount


def _chip(f, who, amount, ev, text):
    amount = max(1, int(amount))
    f.hp = max(0, f.hp - amount)
    ev.append({"t": "chip", "who": who, "damage": amount, "hp": f.hp,
               "maxhp": f.maxhp, "text": text})
    return amount


def _consume(f):
    """이 판에서는 사라진다. 판이 끝나면 돌아온다 (머리말 규칙 2)."""
    if str(f._held or "").endswith("BERRY"):
        f.cond["ateBerry"] = True          # 트림은 나무열매를 먹은 뒤에만 쓸 수 있다
        f.cond["lastBerry"] = f._held      # 수확·되새김질이 다시 꺼낸다
        f.cond["cudNew"] = f._held         # 되새김질: 다음 턴 끝에 한 번 더 먹는다
    f.used = True


def _ready(f):
    """도구가 있고, 한 번 쓰는 것이라면 아직 안 썼는가."""
    return bool(f.held) and not f.used


# ---------------------------------------------------------------- 능력치
def stat_mult(f, key):
    """능력치에 곱할 값. Fighter.stat() 이 랭크·마비 다음에 곱한다."""
    h = f.held
    if not h:
        return 1.0
    if key == "spe":
        if h in SLOW:
            return 0.5
        if h == "CHOICESCARF":
            return 1.5
    elif key == "atk" and h == "CHOICEBAND":
        return 1.5
    elif key == "spa" and h == "CHOICESPECS":
        return 1.5
    elif key == "spd" and h == "ASSAULTVEST":
        return 1.5                                 # 돌격조끼 (대신 변화기를 못 쓴다)
    if h == "EVIOLITE" and key in ("def", "spd") and _can_evolve(f):
        return 1.5                                 # 진화의휘석: 아직 진화할 수 있는 포켓몬
    spec = SPECIES_STAT.get(h)
    if spec and key in spec[1] and _species(f) in spec[0] and not (f.cond or {}).get("transformed"):
        return spec[2]                             # 전기구슬·굵은뼈·심해의이빨 … 그 포켓몬만
    return 1.0


def _can_evolve(f):
    dex = getattr(f, "_dex", None)
    sp = dex.get(_species(f)) if dex is not None else None
    return bool(sp and sp.get("evo"))


# ---------------------------------------------------------------- 순서
def order_bias(bt, f, who, ev):
    """같은 우선도 안에서 순서를 당기면 +1, 미루면 -1, 아니면 0.

    선제공격손톱만 난수를 쓴다 - 도구가 없으면 난수를 건드리지 않는다.
    """
    h = f.held
    if not h:
        return 0
    if h in LAST:
        return -1
    if h == "QUICKCLAW":
        if bt.rng.random() < 0.2:
            _say(ev, who, "%s 의 선제공격손톱이 발동했다!" % f.name)
            return 1
        return 0
    if h == "CUSTAPBERRY" and not f.used and f.hp * 4 <= f.maxhp:
        _consume(f)
        _say(ev, who, "%s 은(는) 애슈열매로 먼저 움직인다!" % f.name)
        return 1
    return 0


def choice_locked(f):
    """구애 도구가 묶어 둔 기술. 도구가 없어졌거나 그 기술을 더는 안 가졌으면(변신이 풀림 ...) None."""
    if f.held in CHOICE and f.locked and f.locked in f.pp:
        return f.locked
    return None


def lock_pool(f, pool):
    """구애 도구를 들었으면 처음 쓴 기술만 남긴다. pool 은 지금 쓸 수 있는 기술 (Battle.usable).

    **묶인 기술을 지금 못 쓰면 발버둥** (1.13.3, 본가 · Showdown 과 같다) - PP 가 없다 · 사슬묶기 · 도발 · 트집 ·
    회복봉인 …. 예전에는 여기서 잠금을 풀어 다른 기술을 골랐는데 force_move 가 다시 묶인 기술로 되돌려서, 사슬묶기가
    풀릴 때까지 턴을 그냥 날렸다 (샌드백).
    """
    k = choice_locked(f)
    if k is None:
        return pool
    return [k] if k in pool else ["STRUGGLE"]


# 구애 도구를 지닌 채 써도 되는 변화기 - 도구를 상대에게 넘기니 묶이지 않는다
CHOICE_PASS = ("TRICK", "SWITCHEROO")


def choice_pool(f, pool, attacks):
    """구애 도구를 지녔고 아직 안 묶였으면, AI 는 공격 기술(과 트릭 · 체인지)만 고른다. attacks(기술) -> 공격기인가.

    1.13.2 (게시판 #284): 자동 배틀은 매 턴 15% 로 아무 기술이나 고르고, 점수로도 칼춤이 뽑힌다. 구애스카프를
    지닌 채 첫 기술로 칼춤을 쓰면 그 기술에 묶여 쓰러질 때까지 칼춤만 썼다. 묶이는 것은 본가 규칙이라 그대로
    두고, AI 가 묶이기 전에 변화기를 안 고르게 한다. 이미 묶였으면(lock_pool 이 하나만 남겼다) 그대로 둔다.
    공격 기술이 하나도 없으면 그대로 둔다 (몸부림으로 빠지지 않게).
    """
    if f.held not in CHOICE or len(pool) <= 1 or (f.locked and f.locked in pool):
        return pool
    out = [k for k in pool if k in CHOICE_PASS or attacks(k)]
    return out or pool


def force_move(f, key, ev, who, bt=None):
    """사람이 고른 기술도 구애 잠금을 받는다 (관장 · 레이드 · 실시간 배틀). 바꿨으면 그 기술.

    bt (Battle) 를 주면 묶인 기술을 지금 쓸 수 있는지(사슬묶기 · 도발 …)까지 보고, 못 쓰면 **발버둥** (1.13.3).
    """
    k = choice_locked(f)
    if k is None or key == k:
        return key
    usable = f.pp.get(k, 0) > 0 and (bt is None or k in bt.usable(f))
    if usable:
        if key != "STRUGGLE":
            _say(ev, who, "%s 은(는) %s 때문에 %s 밖에 쓸 수 없다!"
                 % (f.name, name(f.held), f.dex_move_name(k)))
        return k
    _say(ev, who, "%s 은(는) %s 때문에 %s 밖에 쓸 수 없는데 지금은 쓸 수 없어서 발버둥을 친다!"
         % (f.name, name(f.held), f.dex_move_name(k)))
    return "STRUGGLE"


def note_move(f, key):
    """기술을 쓴 뒤 기억할 것 - 구애 잠금, 메트로놈 연속 횟수."""
    if not f.held:
        return
    if f.held in CHOICE and f.locked is None and key in f.pp:
        f.locked = key
    if f.held == "METRONOME":
        f.metro = (f.metro + 1) if key == f.last_move else 0
    f.last_move = key


# ---------------------------------------------------------------- 명중 · 급소
def acc_mult(user, target):
    m = 1.0
    h = user.held
    if h == "WIDELENS":
        m *= 1.1
    elif h == "ZOOMLENS" and user.moved_second:
        m *= 1.2
    elif h == "MICLEBERRY" and user.armed:
        m *= 1.2
        user.armed = False                      # 한 번 쓰고 끝
    if target.held in EVADE:
        m *= 0.9
    return m


def crit_stages(f):
    s = CRIT_UP.get(f.held, 0)
    if f.held == "LANSATBERRY" and f.armed:
        s += 2
    if f.held in SPECIES_CRIT and _species(f) in SPECIES_CRIT[f.held]:
        s += 2                                     # 럭키펀치(럭키)·대파(파오리·창파나이트)
    return s


# ---------------------------------------------------------------- 데미지
def damage_mult(user, move, eff):
    """공격하는 쪽 도구가 위력에 곱하는 값."""
    h = user.held
    if not h:
        return 1.0
    m = 1.0
    t = TYPE_BOOST.get(h)
    if t and move.get("type") == t:
        m *= TYPE_BOOST_MULT
    cat = move.get("cat")
    if h == "MUSCLEBAND" and cat == "physical":
        m *= 1.1
    elif h == "WISEGLASSES" and cat == "special":
        m *= 1.1
    elif h == "EXPERTBELT" and eff > 1:
        m *= 1.2
    elif h == "LIFEORB":
        m *= 1.3
    elif h == "METRONOME" and user.metro:
        m *= min(2.0, 1.0 + 0.2 * user.metro)
    elif h == "PUNCHINGGLOVE" and "punch" in (move.get("flags") or ()):
        m *= 1.1                                   # 펀치글러브 (닿지도 않는다 - abilities.is_contact)
    if move.get("_gem"):
        m *= GEM_MULT                              # 주얼 (before_damage 가 붙인 표시)
    sp = SPECIES_POWER.get(h)
    if sp and _species(user) in sp[0] and move.get("type") in sp[1]:
        m *= 1.2                                   # 금강옥·백옥·백금옥·마음의물방울
    if h in MASK and _species(user) == "OGERPON":
        m *= MASK_MULT                             # 오거폰의 가면
    return m


def on_incoming(bt, target, who_t, move, eff, dmg, ev):
    """맞는 쪽 도구. 반감 열매를 먹고, 쓰러질 데미지면 1 을 남기고 버틴다."""
    h = target.held
    if not h:
        return dmg
    t = RESIST_BERRY.get(h)
    if t and not target.used and move.get("type") == t \
            and (eff > 1 or h == "CHILANBERRY"):
        _consume(target)
        dmg = max(1, dmg // 2)
        _say(ev, who_t, "%s 의 %s이(가) 데미지를 줄였다!" % (target.name, name(h)))
    if dmg >= target.hp and target.hp > 0:
        if h == "FOCUSSASH" and not target.used and target.hp == target.maxhp:
            _consume(target)
            _say(ev, who_t, "%s 은(는) 기합의띠로 버텼다!" % target.name)
            return target.hp - 1
        if h == "FOCUSBAND" and bt.rng.random() < 0.1:
            _say(ev, who_t, "%s 은(는) 기합의머리띠로 버텼다!" % target.name)
            return target.hp - 1
    return dmg


def after_hit(bt, user, who, target, who_t, move, eff, total, ev):
    """기술이 다 맞은 뒤. 공격한 쪽과 맞은 쪽 도구를 차례로 본다."""
    h = user.held
    if h and total > 0:
        if h == "LIFEORB" and user.alive():
            _chip(user, who, user.maxhp // 10, ev,
                  "%s 은(는) 생명의구슬로 체력이 조금 깎였다!" % user.name)
        elif h == "SHELLBELL":
            _heal(user, who, total // 8, ev,
                  "%s 은(는) 조개껍질방울로 체력을 조금 회복했다!" % user.name)
    ht = target.held
    if ht and not target.used and target.alive() and total > 0:
        cat = move.get("cat")
        if (ht == "JABOCABERRY" and cat == "physical") or \
                (ht == "ROWAPBERRY" and cat == "special"):
            _consume(target)
            if user.alive():
                _chip(user, who, user.maxhp // 8, ev,
                      "%s 은(는) %s 의 %s 때문에 데미지를 입었다!"
                      % (user.name, target.name, name(ht)))
        elif ht == "ENIGMABERRY" and eff > 1:
            _consume(target)
            _heal(target, who_t, target.maxhp // 4, ev,
                  "%s 은(는) 의문열매로 체력을 회복했다!" % target.name)
        else:
            _react(bt, user, who, target, who_t, move, eff, ev)


def flinch(bt, user, target, move):
    """왕의징표석·예리한이빨. 기술에 이미 풀죽음이 있으면 안 겹친다."""
    if user.held in FLINCH_10 and target.alive() and MC.attacks(move) \
            and not move.get("flinch") and bt.rng.random() < 0.1:
        target.flinched = True


def drain_mult(f):
    return 1.3 if f.held == "BIGROOT" else 1.0


def restore_pp(f, key, maxpp, who, ev):
    """과사열매: 기술의 PP 가 바닥나면 10 회복. 한 번."""
    if f.held == "LEPPABERRY" and not f.used and key in f.pp \
            and f.pp.get(key, 0) <= 0:
        _consume(f)
        f.pp[key] = min(10, maxpp or 10)
        _say(ev, who, "%s 은(는) 과사열매로 %s 의 PP 를 회복했다!"
             % (f.name, f.dex_move_name(key)))


# ---------------------------------------------------------------- 체력 · 상태
def check_hp(bt, f, who, ev):
    """체력이 바뀐 뒤. 열매가 발동할 때인지 본다."""
    if not _ready(f) or not f.alive():
        return
    h = f.held
    # 먹보: 1/4 에 먹는 열매를 절반에서 먹는다. 숙성: 회복량이 두 배.
    pinch = 0.5 if _has(f, "GLUTTONY") else 0.25
    ripen = 2.0 if _has(f, "RIPEN") else 1.0
    spec = HEAL_BERRY.get(h)
    if spec:
        thr, kind, amt = spec
        if thr <= 0.25:
            thr = max(thr, pinch)
        if f.hp <= f.maxhp * thr and f.hp < f.maxhp:
            _consume(f)
            heal = (amt if kind == "flat" else f.maxhp * amt) * ripen
            _heal(f, who, heal, ev, "%s 은(는) %s로 체력을 회복했다!"
                  % (f.name, name(h)))
            _cheek_pouch(bt, f, who, ev)
        return
    spec = PINCH_BERRY.get(h)
    if spec and f.hp <= f.maxhp * pinch:
        kind, stat = spec
        _consume(f)
        if kind == "stat":
            _say(ev, who, "%s 은(는) %s를 먹었다!" % (f.name, name(h)))
            bt._change_stat(f, stat, 1, ev, who)
        elif kind == "random":
            stat = bt.rng.choice(["atk", "def", "spa", "spd", "spe"])
            _say(ev, who, "%s 은(는) 스타열매를 먹었다!" % f.name)
            bt._change_stat(f, stat, 2, ev, who)
        elif kind == "crit":
            f.armed = True
            _say(ev, who, "%s 은(는) 랑사열매를 먹고 급소를 노린다!" % f.name)
        elif kind == "acc":
            f.armed = True
            _say(ev, who, "%s 은(는) 미클열매를 먹고 다음 기술의 명중률이 올랐다!"
                 % f.name)
        _cheek_pouch(bt, f, who, ev)


def _has(f, key):
    """특성 확인. held 는 abilities 를 안 들여오므로 여기서 한 번만 본다."""
    from . import abilities as A
    return A.has(f, key)


def _cheek_pouch(bt, f, who, ev):
    """볼주머니: 어떤 나무열매를 먹어도 최대 체력의 1/3 을 더 회복한다."""
    if not _has(f, "CHEEKPOUCH") or f.hp >= f.maxhp or not f.alive():
        return
    from . import abilities as A
    A.pop(bt, f, who, ev)
    _heal(f, who, f.maxhp / 3.0, ev, "%s 은(는) 볼주머니로 체력을 회복했다!" % f.name)


def end_of_turn(bt, f, who, ev):
    """턴 끝. 상태이상 데미지 다음에 온다."""
    h = f.held
    if not h or not f.alive():
        return
    if h == "LEFTOVERS":
        _heal(f, who, f.maxhp // 16, ev,
              "%s 은(는) 먹다남은음식으로 체력을 조금 회복했다!" % f.name)
    elif h == "BLACKSLUDGE":
        # **지금 타입**으로 본다. 종족 기본 타입을 보면 변환자재·리베로·물붓기로
        # 타입이 바뀐 것을 놓친다 (독 타입이 된 포켓몬이 깎이고, 독이 아니게 된
        # 포켓몬이 회복했다).
        if "POISON" in f.types():
            _heal(f, who, f.maxhp // 16, ev,
                  "%s 은(는) 검은오물로 체력을 조금 회복했다!" % f.name)
        else:
            _chip(f, who, f.maxhp // 8, ev,
                  "%s 은(는) 검은오물 때문에 데미지를 입었다!" % f.name)
    elif h == "STICKYBARB":
        _chip(f, who, f.maxhp // 8, ev,
              "%s 은(는) 끈적끈적바늘 때문에 데미지를 입었다!" % f.name)
    elif h == "TOXICORB" and not f.status:
        # 맹독으로 건다 (1.9.2 - 예전에는 엔진에 맹독이 없어서 그냥 독이었다).
        # 독 타입이면 _apply_status 가 막는다.
        bt._apply_status(f, "bad-poison", ev)
    elif h == "FLAMEORB" and not f.status:
        bt._apply_status(f, "burn", ev)
    check_hp(bt, f, who, ev)


def on_status(bt, f, who, ev):
    """상태이상에 걸린 직후. 고치는 열매."""
    if not _ready(f) or not f.status:
        return
    want = CURE_BERRY.get(f.held)
    if want and (want == "*" or want == f.status):
        cured = f.status
        f.status = None
        f.sleep_turns = 0
        _consume(f)
        ev.append({"t": "cure", "who": who,
                   "text": "%s 은(는) %s로 %s 상태를 고쳤다!"
                           % (f.name, name(f.held), bt.status_kr(cured))})


def on_stat_drop(bt, f, who, ev):
    """능력이 떨어진 직후. 하양허브, 탈출팩."""
    if f.held == "WHITEHERB" and not f.used \
            and any(v < 0 for v in f.stages.values()):
        for k, v in f.stages.items():
            if v < 0:
                f.stages[k] = 0
        _consume(f)
        _say(ev, who, "%s 은(는) 하양허브로 능력 하락을 되돌렸다!" % f.name)
    elif f.held == "EJECTPACK" and not f.used and f.alive() and _can_leave(bt):
        _consume(f)
        f.cond["eject"] = "out"                    # 기술이 끝난 뒤에 물러난다 (settle)
        _say(ev, who, "%s 은(는) 탈출팩으로 돌아가려 한다!" % f.name)


def flee_sure(f):
    return f.held == "SMOKEBALL"


# ---------------------------------------------------------------- 1.13 의 훅
# 규칙 1 그대로: 도구가 없으면 아무것도 안 하고 난수도 안 쓴다. 부르는 쪽(battle·statusmoves·
# attackfx·abilities)이 정해진 자리에서 부른다.

def _stat_up(bt, f, who, stat, n, ev):
    bt._change_stat(f, stat, n, ev, who)


def _can_leave(bt):
    """물러날 곳이 있는 배틀인가 (관장·유저·레이드는 교체기가 붙어 있다). 야생은 없다 - 탈출버튼·
    레드카드·탈출팩이 야생 배틀을 끝내 버리면 안 된다."""
    return getattr(bt, "switcher", None) is not None


def _react(bt, user, who, target, who_t, move, eff, ev):
    """맞은 쪽 도구의 반응 (after_hit 가 부른다 - 한 번 쓰는 것들)."""
    ht = target.held
    mtype, cat = move.get("type"), move.get("cat")
    fixed = move.get("_fixed") is not None or MC.key(move) in MC.FIXED
    if ht == "WEAKNESSPOLICY" and eff > 1 and not fixed:
        _consume(target)
        _say(ev, who_t, "%s 의 약점보험이 발동했다!" % target.name)
        _stat_up(bt, target, who_t, "atk", 2, ev)
        _stat_up(bt, target, who_t, "spa", 2, ev)
    elif ht in HIT_TYPE_BOOST and mtype == HIT_TYPE_BOOST[ht][0]:
        _consume(target)
        _say(ev, who_t, _josa("%s의 %s이(가) 반응했다!" % (target.name, name(ht))))
        _stat_up(bt, target, who_t, HIT_TYPE_BOOST[ht][1], 1, ev)
    elif ht in HIT_CAT_BERRY and cat == HIT_CAT_BERRY[ht][0]:
        _consume(target)
        _say(ev, who_t, "%s 은(는) %s를 먹었다!" % (target.name, name(ht)))
        _stat_up(bt, target, who_t, HIT_CAT_BERRY[ht][1], 1, ev)
    elif ht == "EJECTBUTTON" and _can_leave(bt):
        _consume(target)
        target.cond["eject"] = "out"               # 기술이 끝난 뒤에 물러난다 (settle)
        _say(ev, who_t, "%s 은(는) 탈출버튼으로 돌아가려 한다!" % target.name)
    elif ht == "REDCARD" and user.alive() and _can_leave(bt):
        _consume(target)
        user.cond["eject"] = "drag"                # 때린 쪽이 끌려 나간다 (settle)
        _say(ev, who_t, "%s 은(는) %s 에게 레드카드를 내밀었다!" % (target.name, user.name))


def on_each_hit(bt, user, who, target, who_t, move, dmg, ev):
    """한 대 맞을 때마다 (연속기면 대마다). 울퉁불퉁멧, 풍선이 터진다."""
    ht = target.held
    if not ht or dmg <= 0:
        return
    if ht == "ROCKYHELMET" and user.alive() and contact_hurts(move, user) and not _has(user, "MAGICGUARD"):
        _chip(user, who, user.maxhp // 6, ev, "%s 은(는) 울퉁불퉁멧에 다쳤다!" % user.name)
    elif ht == "AIRBALLOON" and not target.used:
        target.used = True
        _say(ev, who_t, "%s 의 풍선이 터졌다!" % target.name)


def contact_hurts(move, user):
    """닿아서 다치는 것(까칠한피부·울퉁불퉁멧·정전기 …)이 일어나는가. 방호패드면 안 일어난다."""
    from . import abilities as A
    return A.is_contact(move, user) and getattr(user, "held", None) != "PROTECTIVEPADS"


def before_damage(bt, user, who, move, ev):
    """주얼: 그 타입 공격기를 처음 쓸 때 위력 1.3배 (한 번). 표시를 붙인 기술을 돌려준다."""
    t = GEM.get(user.held)
    if not t or user.used or not MC.attacks(move) or move.get("type") != t \
            or move.get("_fixed") is not None or MC.key(move) in MC.FIXED:
        return move
    _consume(user)
    _say(ev, who, "%s로 %s의 위력이 올라갔다!" % (name(t + "GEM"), move.get("kr") or "기술"))
    return dict(move, _gem=True)


def on_miss(bt, user, who, ev):
    """명중 판정에서 빗나갔다. 허탕보험: 스피드 +2 (한 번)."""
    if user.held == "BLUNDERPOLICY" and not user.used and user.alive():
        _consume(user)
        _say(ev, who, "%s 의 허탕보험이 발동했다!" % user.name)
        _stat_up(bt, user, who, "spe", 2, ev)


def after_move(bt, user, who, move, ev):
    """기술을 다 쓴 뒤. 목스프레이: 소리 기술을 쓰면 특수공격 +1 (한 번)."""
    if user.held == "THROATSPRAY" and not user.used and user.alive() \
            and "sound" in (move.get("flags") or ()):
        _consume(user)
        _say(ev, who, "%s 의 목스프레이가 발동했다!" % user.name)
        _stat_up(bt, user, who, "spa", 1, ev)


def blocks_status(f, move):
    """돌격조끼: 변화기를 못 쓴다. 못 쓰면 까닭(문구), 아니면 None."""
    if f.held == "ASSAULTVEST" and move and not MC.attacks(move):
        return "%s 은(는) 돌격조끼 때문에 변화 기술을 쓸 수 없다!" % f.name
    return None


def floating(f):
    """풍선을 지녀서 떠 있는가 (땅 기술이 안 맞고 압정·필드도 안 닿는다). 맞으면 터진다."""
    return f.held == "AIRBALLOON" and not f.used


def on_entry(bt, f, who, ev):
    """나온 순간 (등장 특성과 같은 자리). 풍선, 시드, 룸서비스, 부스트에너지."""
    h = f.held
    if not h or not f.alive():
        return
    if h == "AIRBALLOON" and not f.used and not f.cond.get("balloonSaid"):
        f.cond["balloonSaid"] = True
        _say(ev, who, "%s 은(는) 풍선으로 떠 있다!" % f.name)
    elif h in SEED:
        _seed(bt, f, who, ev)
    elif h == "ROOMSERVICE":
        _room_service(bt, f, who, ev)
    elif h == "BOOSTERENERGY" and not f.used:
        from . import statusmoves as SM
        sun = SM.weather(f) == "sun"
        elec = SM.terrain(f) == "electric"
        if (_has(f, "PROTOSYNTHESIS") and not sun) or (_has(f, "QUARKDRIVE") and not elec):
            _consume(f)
            f.cond["booster"] = True
            _say(ev, who, "%s 은(는) 부스트에너지로 %s이(가) 발동했다!"
                 % (f.name, "고대활성" if _has(f, "PROTOSYNTHESIS") else "쿼크차지"))


def _seed(bt, f, who, ev):
    spec = SEED.get(f.held)
    if not spec or f.used or not f.alive() or bt.field.terrain != spec[0]:
        return
    _consume(f)
    _say(ev, who, "%s 은(는) %s를 썼다!" % (f.name, name(f.held)))
    _stat_up(bt, f, who, spec[1], 1, ev)


def _room_service(bt, f, who, ev):
    if f.held != "ROOMSERVICE" or f.used or not f.alive() or not bt.field.room("trickroom"):
        return
    _consume(f)
    _say(ev, who, "%s 은(는) 룸서비스를 썼다!" % f.name)
    bt._change_stat(f, "spe", -1, ev, who)


def on_terrain(bt, ev):
    """필드가 새로 깔렸다. 시드를 지닌 쪽이 쓴다."""
    for who in ("me", "foe"):
        f = bt.fighter(who)
        if f is not None and f.held in SEED:
            _seed(bt, f, who, ev)


def on_room(bt, room, ev):
    """트릭룸이 새로 깔렸다. 룸서비스."""
    if room != "trickroom":
        return
    for who in ("me", "foe"):
        f = bt.fighter(who)
        if f is not None and f.held == "ROOMSERVICE":
            _room_service(bt, f, who, ev)


def weather_turns(f, w):
    """날씨를 부른 쪽의 도구: 맞는 바위면 8턴, 아니면 5턴."""
    return 8 if f is not None and w in WEATHER_ROCK.get(f.held, ()) else 5


def terrain_turns(f):
    return 8 if f is not None and f.held == "TERRAINEXTENDER" else 5


def screen_turns(f):
    return 8 if f is not None and f.held == "LIGHTCLAY" else 5


def bind_turns(f, rng):
    """조이기·김밥말이 … 를 건 쪽의 도구: 끈기갈고리손톱이면 7턴 (난수를 안 쓴다)."""
    return 7 if f is not None and f.held == "GRIPCLAW" else rng.randint(4, 5)


def bind_frac(f):
    """조임 데미지: 건 쪽이 조임밴드면 1/6, 아니면 1/8."""
    return 6.0 if f is not None and f.held == "BINDINGBAND" else 8.0


def no_hazards(f):
    """통굽부츠: 압정·스텔스록·독압정·끈적끈적네트를 안 밟는다."""
    return f.held == "HEAVYDUTYBOOTS"


def weather_safe(f):
    """방진고글: 모래바람·싸라기눈 데미지를 안 받는다."""
    return f.held == "SAFETYGOGGLES"


def powder_safe(f):
    """방진고글: 가루·포자 기술이 안 통한다."""
    return f.held == "SAFETYGOGGLES"


def umbrella(f):
    """만능우산: 쾌청·비의 영향을 안 받는다 (그 포켓몬이 쓰는 기술도, 맞는 기술도)."""
    return f is not None and f.held == "UTILITYUMBRELLA"


def cloaked(f):
    """은밀망토: 상대 기술의 추가 효과(풀죽음·능력 하락·상태이상 확률)를 안 받는다."""
    return f.held == "COVERTCLOAK"


def clear_amulet(f, source):
    """클리어참: 상대가 떨어뜨리는 능력 하락을 막는다."""
    return f.held == "CLEARAMULET" and source is not None and source is not f


def ability_locked(f):
    """특성가드: 특성이 바뀌거나 지워지지 않는다."""
    return f.held == "ABILITYSHIELD"


def ring_target(f):
    """겨냥표적: 타입 상성으로 안 맞던 기술(효과 없음)이 맞는다."""
    return f.held == "RINGTARGET"


def shed_shell(f):
    """아름다운허물: 붙잡혀 있어도 교체할 수 있다."""
    return f.held == "SHEDSHELL"


def weight_mult(f):
    return 0.5 if f.held == "FLOATSTONE" else 1.0


def dice_hits(f, lo, hi, rng):
    """속임수주사위: 2~5번 치는 기술이 4~5번. 해당이 없으면 None (난수를 안 쓴다)."""
    if f.held == "LOADEDDICE" and (lo, hi) == (2, 5):
        return rng.choice((4, 5))
    return None


def on_intimidated(bt, f, who, ev):
    """위협을 받았다. 주눅구슬: 스피드 +1 (한 번)."""
    if f.held == "ADRENALINEORB" and not f.used and f.alive():
        _consume(f)
        _say(ev, who, "%s 의 주눅구슬이 발동했다!" % f.name)
        _stat_up(bt, f, who, "spe", 1, ev)


def on_foe_boost(bt, f, who, stat, n, ev):
    """맞은편이 능력을 올렸다. 흉내허브: 그만큼 따라 올린다 (한 번)."""
    if f is None or f.held != "MIRRORHERB" or f.used or not f.alive() or n <= 0:
        return
    _consume(f)
    _say(ev, who, "%s 은(는) 흉내허브로 상대의 능력 변화를 따라 했다!" % f.name)
    bt._change_stat(f, stat, n, ev, who)


def settle(bt, ev):
    """기술 하나가 끝날 때마다 (그리고 턴 끝에). 걸린 것을 고치는 도구와, 물러나는 도구.

    멘탈허브(헤롱헤롱·도발·앵콜·트집·사슬묶기·회복봉인), 시몬열매(혼란), 빨간실(헤롱헤롱을 되돌려 준다),
    탈출버튼·레드카드·탈출팩(물러난다 / 끌려 나간다). 걸리는 자리가 여기저기라 한 곳에서 본다 -
    싱글 배틀에서는 걸린 쪽이 그다음에 움직이므로 본가와 같다.
    """
    for who in ("me", "foe"):
        f = bt.fighter(who)
        if f is None or not f.alive():
            continue
        c = f.cond
        h = f.held
        if h == "DESTINYKNOT" and c.get("attract") and not f.used:
            rival = bt.fighter("foe" if who == "me" else "me")
            if rival is not None and rival.alive() and not rival.cond.get("attract"):
                _consume(f)
                rival.cond["attract"] = who
                _say(ev, who, "%s 의 빨간실이 %s 을(를) 헤롱헤롱하게 만들었다!" % (f.name, rival.name))
        if h == "MENTALHERB" and not f.used and any(c.get(k) for k in MENTAL_CONDS):
            _consume(f)
            for k in MENTAL_CONDS:
                c.pop(k, None)
            _say(ev, who, "%s 은(는) 멘탈허브로 정신을 차렸다!" % f.name)
        if h == "PERSIMBERRY" and not f.used and c.get("confused"):
            _consume(f)
            c.pop("confused", None)
            _say(ev, who, "%s 은(는) 시몬열매로 혼란이 풀렸다!" % f.name)
    for who in ("me", "foe"):
        f = bt.fighter(who)
        mode = f.cond.pop("eject", None) if f is not None else None
        if mode and f.alive() and not bt.over:
            # 탈출버튼·탈출팩 = 스스로 물러난다, 레드카드 = 끌려 나간다 (울부짖기와 같다)
            bt.request_switch(who, mode, ev, None)


# ---------------------------------------------------------------- 배틀 밖 (서버)
def exp_mult(held):
    return EXP_ITEMS.get(normalize(held), 1.0)


def happiness_mult(held):
    return HAPPINESS_ITEMS.get(normalize(held), 1.0)


def ev_yield(held, yields):
    """쓰러뜨렸을 때 받는 노력치를 도구에 맞게 고친다."""
    h = normalize(held)
    if not h:
        return yields
    out = dict(yields or {})
    if h == "MACHOBRACE":
        return dict((k, v * 2) for k, v in out.items())
    stat = POWER_EV.get(h)
    if stat:
        out[stat] = out.get(stat, 0) + 8
    return out


# ---------------------------------------------------------------- 저장 · 복원
# 야생 배틀은 턴마다 서버를 오가서 Fighter 가 DB 에 잤다 깬다. 먹은
# 열매·구애 잠금이 턴 사이에 잊히면 열매를 매 턴 먹는다.
def state(f):
    # 금제·매직룸 동안에는 f.held 가 None 이다. 그래도 먹은 열매·잠금은 남겨야 한다.
    if not getattr(f, "_held", f.held):
        return None
    return {"used": f.used, "locked": f.locked, "last": f.last_move,
            "metro": f.metro, "armed": f.armed}


def load(f, d):
    if not d or not getattr(f, "_held", f.held):
        return
    f.used = bool(d.get("used"))
    f.locked = d.get("locked")
    f.last_move = d.get("last")
    f.metro = int(d.get("metro") or 0)
    f.armed = bool(d.get("armed"))


# ---------------------------------------------------------------- 설명
_TYPE_KR = {"NORMAL": "노말", "FIRE": "불꽃", "WATER": "물", "ELECTRIC": "전기", "GRASS": "풀",
            "ICE": "얼음", "FIGHTING": "격투", "POISON": "독", "GROUND": "땅", "FLYING": "비행",
            "PSYCHIC": "에스퍼", "BUG": "벌레", "ROCK": "바위", "GHOST": "고스트", "DRAGON": "드래곤",
            "DARK": "악", "STEEL": "강철", "FAIRY": "페어리"}
_STAT_KR = {"hp": "HP", "atk": "공격", "def": "방어", "spa": "특수공격", "spd": "특수방어", "spe": "스피드"}
_STATUS_KR = {"paralysis": "마비", "sleep": "잠듦", "poison": "독", "burn": "화상", "freeze": "얼음",
              "*": "모든 상태이상"}


def _josa(text):
    from .korean import natural
    return natural(text)


def _pct(mult):
    return int(round((mult - 1.0) * 100))


def effect_note(item_id):
    """지녔을 때 **실제로 몇 배인지** 한 줄. 모르는 도구는 빈 글자.

    가방·상점의 설명은 본가 문장이라 "위력이 올라간다" 까지만 있다. 얼마나
    오르는지는 이 파일의 표에만 있어서, 표를 그대로 읽어 말로 만든다 -
    숫자를 설명에 따로 적어 두면 표를 고칠 때 설명과 어긋난다.
    """
    h = normalize(item_id)
    if not h:
        return ""
    if TR.is_shard(h):
        return ("지니면 테라스탈할 때 %s 타입이 된다 (한 판에 한 번, 테라오브 필요). 테라피스를 지니지 않은 포켓몬은 "
                "테라스탈하지 못한다" % _TYPE_KR.get(TR.shard_type(h), TR.shard_type(h)))
    if ZM.is_crystal(h):
        own = ZM.EXCLUSIVE.get(h)
        if own:
            return "정해진 포켓몬이 정해진 기술을 전용 Z기술로 쓴다 (한 판에 한 번, Z링 필요)"
        return ("%s 타입 기술 하나를 Z기술로 쓴다 (한 판에 한 번, Z링 필요). 반드시 맞고 방어도 뚫는다"
                % _TYPE_KR.get(ZM.CRYSTAL_TYPE[h], ZM.CRYSTAL_TYPE[h]))
    t = TYPE_BOOST.get(h)
    if t:
        return "%s 타입 기술의 위력이 %d%% 올라간다 (%.1f배)" % (_TYPE_KR.get(t, t), _pct(TYPE_BOOST_MULT),
                                                     TYPE_BOOST_MULT)
    fixed = {
        "MUSCLEBAND": "물리 기술의 위력이 10% 올라간다 (1.1배)",
        "WISEGLASSES": "특수 기술의 위력이 10% 올라간다 (1.1배)",
        "EXPERTBELT": "효과가 굉장한 기술의 위력이 20% 올라간다 (1.2배)",
        "LIFEORB": "기술의 위력이 30% 올라간다 (1.3배). 대신 공격할 때마다 최대 HP의 10%가 줄어든다",
        "METRONOME": "같은 기술을 이어 쓸 때마다 위력이 20%씩 올라간다 (최대 2배)",
        "LEFTOVERS": "매 턴 끝에 최대 HP의 1/16(약 6%)을 회복한다",
        "BLACKSLUDGE": "독 타입이면 매 턴 최대 HP의 1/16을 회복하고, 아니면 1/8이 줄어든다",
        "STICKYBARB": "매 턴 끝에 최대 HP의 1/8이 줄어든다",
        "SHELLBELL": "상대에게 준 데미지의 1/8만큼 회복한다",
        "BIGROOT": "HP를 흡수하는 기술의 회복량이 30% 늘어난다 (1.3배)",
        "WIDELENS": "기술의 명중률이 10% 올라간다 (1.1배)",
        "ZOOMLENS": "상대보다 나중에 움직이면 명중률이 20% 올라간다 (1.2배)",
        "QUICKCLAW": "20% 확률로 같은 우선도에서 먼저 움직인다",
        "FOCUSBAND": "쓰러질 데미지를 받아도 10% 확률로 HP 1이 남는다",
        "FOCUSSASH": "HP가 가득할 때 쓰러질 데미지를 받으면 한 번 HP 1로 버틴다",
        "TOXICORB": "턴 끝에 스스로 독 상태가 된다",
        "FLAMEORB": "턴 끝에 스스로 화상 상태가 된다",
        "WHITEHERB": "능력치가 떨어지면 한 번 원래대로 되돌린다",
        "LEPPABERRY": "기술의 PP가 바닥나면 한 번 10 회복한다",
        "ENIGMABERRY": "효과가 굉장한 기술에 맞으면 최대 HP의 1/4을 회복한다 (한 번)",
        "JABOCABERRY": "물리 기술에 맞으면 상대 최대 HP의 1/8만큼 되갚는다 (한 번)",
        "ROWAPBERRY": "특수 기술에 맞으면 상대 최대 HP의 1/8만큼 되갚는다 (한 번)",
        "CUSTAPBERRY": "HP가 1/4 이하일 때 한 번 먼저 움직인다",
        "LUCKYEGG": "배틀에서 받는 경험치가 %d%% 늘어난다 (%.1f배)" % (_pct(EXP_ITEMS["LUCKYEGG"]), EXP_ITEMS["LUCKYEGG"]),
        "SOOTHEBELL": "친밀도가 %d%% 더 오른다 (%.1f배)" % (_pct(HAPPINESS_ITEMS["SOOTHEBELL"]),
                                                   HAPPINESS_ITEMS["SOOTHEBELL"]),
        "LAGGINGTAIL": "같은 우선도에서 늘 나중에 움직인다",
        "FULLINCENSE": "같은 우선도에서 늘 나중에 움직인다",
        "IRONBALL": "스피드가 절반이 된다",
        "MACHOBRACE": "쓰러뜨리면 받는 노력치가 2배가 된다. 대신 스피드가 절반이 된다",
    }
    if h in fixed:
        return fixed[h]
    if h in CHOICE:
        return _josa("%s이(가) 50%% 올라간다 (1.5배). 대신 처음 쓴 기술만 계속 쓸 수 있다" % _STAT_KR[CHOICE[h]])
    if h in POWER_EV:
        return "쓰러뜨리면 %s 노력치가 8 더 오른다. 대신 스피드가 절반이 된다" % _STAT_KR[POWER_EV[h]]
    if h in CRIT_UP:
        return "급소에 맞을 확률이 한 단계 올라간다"
    if h in FLINCH_10:
        return "공격할 때 10% 확률로 상대를 풀죽게 한다"
    if h in EVADE:
        return "상대 기술의 명중률이 10% 떨어진다 (0.9배)"
    t = RESIST_BERRY.get(h)
    if t:
        if h == "CHILANBERRY":
            return "노말 타입 기술의 데미지를 한 번 절반으로 줄인다"
        return "효과가 굉장한 %s 타입 기술의 데미지를 한 번 절반으로 줄인다" % _TYPE_KR.get(t, t)
    c = CURE_BERRY.get(h)
    if c:
        return "%s에 걸리면 바로 고친다 (한 번)" % _STATUS_KR.get(c, c)
    spec = HEAL_BERRY.get(h)
    if spec:
        thr, kind, amt = spec
        when = "HP가 절반 이하" if thr == 0.5 else "HP가 1/4 이하"
        how = ("HP를 %d 회복한다" % amt) if kind == "flat" else \
            ("최대 HP의 %s을 회복한다" % ("1/4" if abs(amt - 0.25) < 1e-6 else "1/3"))
        return "%s가 되면 %s (한 번)" % (when, how)
    spec = PINCH_BERRY.get(h)
    if spec:
        kind, stat = spec
        if kind == "stat":
            return _josa("HP가 1/4 이하가 되면 %s이(가) 한 단계 올라간다 (한 번)" % _STAT_KR[stat])
        if kind == "random":
            return "HP가 1/4 이하가 되면 능력 하나가 두 단계 올라간다 (한 번)"
        if kind == "crit":
            return "HP가 1/4 이하가 되면 급소에 맞을 확률이 두 단계 올라간다"
        if kind == "acc":
            return "HP가 1/4 이하가 되면 다음 기술의 명중률이 20% 올라간다"
    return _note_113(h)


# 1.13 의 도구들. 가방·상점에 나오는 한 줄 (본가 설명이 없는 9세대 도구는 이것이 설명이다).
NOTE_113 = {
    "MENTALHERB": "헤롱헤롱·도발·앵콜·트집·사슬묶기·회복봉인에 걸리면 한 번 바로 풀린다",
    "LIGHTCLAY": "리플렉터·빛의장막·오로라베일이 5턴이 아니라 8턴 간다",
    "POWERHERB": "두 턴에 걸쳐 쓰는 기술을 한 번 바로 쓴다",
    "DESTINYKNOT": "헤롱헤롱에 걸리면 상대도 한 번 헤롱헤롱하게 만든다",
    "GRIPCLAW": "조이기·김밥말이 같은 기술이 7턴 간다",
    "SHEDSHELL": "붙잡혀 있어도 교체할 수 있다",
    "EVIOLITE": "아직 진화할 수 있는 포켓몬이 지니면 방어·특수방어가 50% 올라간다 (1.5배)",
    "FLOATSTONE": "몸무게가 절반이 된다 (안다리걸기·풀묶기에 덜 아프다)",
    "ROCKYHELMET": "닿는 기술에 맞으면 때린 상대의 최대 HP 1/6을 깎는다",
    "AIRBALLOON": "떠 있어서 땅 타입 기술을 안 맞는다. 공격에 한 번 맞으면 터진다",
    "REDCARD": "기술에 맞으면 때린 상대를 교체시킨다 (한 번, 교체할 포켓몬이 있는 배틀에서만)",
    "RINGTARGET": "타입 상성으로 효과가 없던 기술도 맞는다",
    "BINDINGBAND": "조이기 같은 기술의 매 턴 데미지가 최대 HP의 1/8이 아니라 1/6이 된다",
    "EJECTBUTTON": "기술에 맞으면 교체한다 (한 번, 교체할 포켓몬이 있는 배틀에서만)",
    "EJECTPACK": "능력이 떨어지면 교체한다 (한 번, 교체할 포켓몬이 있는 배틀에서만)",
    "WEAKNESSPOLICY": "효과가 굉장한 기술에 맞으면 공격·특수공격이 크게 오른다 (한 번)",
    "ASSAULTVEST": "특수방어가 50% 올라간다 (1.5배). 대신 변화 기술을 쓸 수 없다",
    "SAFETYGOGGLES": "모래바람·싸라기눈 데미지와 가루·포자 기술을 안 받는다",
    "ADRENALINEORB": "위협을 받으면 스피드가 오른다 (한 번)",
    "TERRAINEXTENDER": "필드가 5턴이 아니라 8턴 간다",
    "PROTECTIVEPADS": "닿는 기술로 때려도 까칠한피부·울퉁불퉁멧 같은 반격을 안 받는다",
    "THROATSPRAY": "소리 기술을 쓰면 특수공격이 오른다 (한 번)",
    "HEAVYDUTYBOOTS": "압정·스텔스록·독압정·끈적끈적네트를 안 밟는다",
    "BLUNDERPOLICY": "기술이 빗나가면 스피드가 크게 오른다 (한 번)",
    "ROOMSERVICE": "트릭룸이 깔리면 스피드가 떨어진다 (한 번)",
    "UTILITYUMBRELLA": "쾌청·비가 기술의 위력에 끼어들지 않는다 (쓰는 기술도, 맞는 기술도)",
    "BOOSTERENERGY": "고대활성·쿼크차지가 날씨·필드 없이도 한 번 발동한다",
    "ABILITYSHIELD": "특성이 바뀌거나 지워지지 않는다 (스킬스왑·위액 …)",
    "CLEARAMULET": "상대가 떨어뜨리는 능력 하락을 막는다",
    "MIRRORHERB": "상대가 능력을 올리면 그만큼 따라 올린다 (한 번)",
    "PUNCHINGGLOVE": "펀치 기술의 위력이 10% 올라가고 상대에게 닿지 않는다",
    "COVERTCLOAK": "상대 기술의 추가 효과(풀죽음·능력 하락·상태이상 확률)를 안 받는다",
    "LOADEDDICE": "2~5번 치는 기술이 늘 4번이나 5번 친다",
    "PERSIMBERRY": "혼란에 걸리면 바로 고친다 (한 번)",
    "RUSTEDSWORD": "자시안이 지니면 검왕의 모습이 된다. 아이언헤드가 거수참이 된다",
    "RUSTEDSHIELD": "자마젠타가 지니면 방패왕의 모습이 된다. 아이언헤드가 거수탄이 된다",
    "REDORB": "그란돈이 지니고 배틀에 나오면 원시회귀한다 (끝의대지: 강한 햇살)",
    "BLUEORB": "가이오가가 지니고 배틀에 나오면 원시회귀한다 (시작의바다: 강한 비)",
}


def _note_113(h):
    if h in NOTE_113:
        return NOTE_113[h]
    t = HIT_TYPE_BOOST.get(h)
    if t:
        return _josa("%s 타입 기술에 맞으면 %s이(가) 오른다 (한 번)" % (_TYPE_KR.get(t[0], t[0]), _STAT_KR[t[1]]))
    t = HIT_CAT_BERRY.get(h)
    if t:
        return _josa("%s 기술에 맞으면 %s이(가) 오른다 (한 번)"
                     % ("물리" if t[0] == "physical" else "특수", _STAT_KR[t[1]]))
    t = SEED.get(h)
    if t:
        fk = {"electric": "일렉트릭필드", "grassy": "그래스필드", "misty": "미스트필드", "psychic": "사이코필드"}[t[0]]
        return _josa("%s가 깔려 있으면 %s이(가) 오른다 (한 번)" % (fk, _STAT_KR[t[1]]))
    t = WEATHER_ROCK.get(h)
    if t:
        wk = {"hail": "싸라기눈·설경", "sand": "모래바람", "sun": "쾌청", "rain": "비"}[t[0]]
        return _josa("%s을(를) 부르면 5턴이 아니라 8턴 간다" % wk)
    t = GEM.get(h)
    if t:
        return "%s 타입 기술을 처음 쓸 때 위력이 30%% 올라간다 (1.3배, 한 번)" % _TYPE_KR.get(t, t)
    t = SPECIES_STAT.get(h)
    if t:
        who = {"LIGHTBALL": "피카츄", "THICKCLUB": "탕구리·텅구리", "DEEPSEATOOTH": "진주몽",
               "DEEPSEASCALE": "진주몽", "METALPOWDER": "메타몽(변신 전)", "QUICKPOWDER": "메타몽(변신 전)"}.get(h, "")
        return _josa("%s이(가) 지니면 %s이(가) 2배" % (who, "·".join(_STAT_KR[k] for k in t[1])))
    if h in SPECIES_CRIT:
        who = {"LUCKYPUNCH": "럭키", "STICK": "파오리·창파나이트"}[h]
        return _josa("%s이(가) 지니면 급소에 맞을 확률이 두 단계 올라간다" % who)
    t = SPECIES_POWER.get(h)
    if t:
        who = {"SOULDEW": "라티오스·라티아스", "ADAMANTORB": "디아루가", "ADAMANTCRYSTAL": "디아루가",
               "LUSTROUSORB": "펄기아", "LUSTROUSGLOBE": "펄기아", "GRISEOUSORB": "기라티나",
               "GRISEOUSCORE": "기라티나"}[h]
        text = _josa("%s이(가) 지니면 %s 타입 기술의 위력이 20%% 올라간다 (1.2배)"
                     % (who, "·".join(_TYPE_KR.get(x, x) for x in t[1])))
        if h in ("ADAMANTCRYSTAL", "LUSTROUSGLOBE", "GRISEOUSCORE", "GRISEOUSORB"):
            text += ". 오리진폼이 된다"
        return text
    t = MASK.get(h)
    if t:
        return ("오거폰이 지니면 그 가면을 쓴 모습(%s 타입)이 되고, 기술의 위력이 20%% 올라간다. "
                "덩굴방망이도 %s 타입이 된다" % (_TYPE_KR.get(t, t), _TYPE_KR.get(t, t)))
    t = MEMORY.get(h)
    if t:
        return "실버디가 지니면 %s 타입이 되고, 멀티어택도 %s 타입이 된다" % (_TYPE_KR.get(t, t), _TYPE_KR.get(t, t))
    t = DRIVE.get(h)
    if t:
        return "게노세크트가 지니면 테크노버스터가 %s 타입이 된다" % _TYPE_KR.get(t, t)
    if h == "PIXIEPLATE":
        return "페어리 타입 기술의 위력이 20% 올라간다 (1.2배). 아르세우스가 지니면 페어리 타입이 된다"
    return ""
