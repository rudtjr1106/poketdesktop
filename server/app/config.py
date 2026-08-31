# -*- coding: utf-8 -*-
"""환경변수 설정. 전부 기본값이 있어서 그냥 띄워도 돌아간다."""
import os

try:
    from common.version import VERSION
except ImportError:
    VERSION = "0.0.0"


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float(name, default):
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _bool(name, default):
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DB_PATH = os.environ.get("POKET_DB", "/data/poket.db")
POKEDEX_PATH = os.environ.get("POKET_POKEDEX", os.path.join(ROOT, "data", "pokedex.json"))

# ---- 계정 ----
TOKEN_DAYS = _int("POKET_TOKEN_DAYS", 30)
# 자동 로그인 때 IP 까지 확인할지. 도커 뒤에서는 실제 IP 가 안 보여서 자동으로 건너뛴다.
REQUIRE_IP = _bool("POKET_REQUIRE_IP", True)
# 리버스 프록시 뒤에 있을 때만 켠다. 켜면 X-Forwarded-For 를 믿는다.
TRUST_PROXY = _bool("POKET_TRUST_PROXY", False)
PW_ITERATIONS = _int("POKET_PW_ITERATIONS", 200000)
# 계정은 최대한 간단하게 — 닉네임 + 숫자 4자리.
# 4자리는 만 가지뿐이라 대신 로그인 시도 제한을 세게 건다.
MIN_USERNAME = 2
MAX_USERNAME = 12
PIN_DIGITS = _int("POKET_PIN_DIGITS", 4)
MIN_PASSWORD = PIN_DIGITS

# ---- 게임 규칙 ----
MAX_BOX = _int("POKET_MAX_BOX", 300)                   # 보유 상한
# 데리고 다니는 포켓몬 수. 이 숫자가 곧 바탕화면에 나오는 수이기도 하다.
# 넘치면 PC 박스로 들어간다.
MAX_PARTY = _int("POKET_MAX_PARTY", 6)
MAX_DESKTOP = MAX_PARTY
# 야생 레벨은 파티 수준을 따라간다.
# 고정해두면 시작하자마자 도저히 못 이기는 상대를 만나 재미가 없다.
WILD_MIN_LEVEL = _int("POKET_WILD_MIN_LEVEL", 2)      # 절대 하한
WILD_MAX_LEVEL = _int("POKET_WILD_MAX_LEVEL", 100)     # 절대 상한
# 종족값 상한 = 이 값 + 선두 레벨 * 계수.
# 레벨 5 짜리 야생인데 종족값 600 이 나오면 스타팅이 손도 못 쓰고 진다.
WILD_BST_BASE = _int("POKET_WILD_BST_BASE", 330)
WILD_BST_PER_LEVEL = _int("POKET_WILD_BST_PER_LEVEL", 8)
SHINY_RATE = _int("POKET_SHINY_RATE", 4096)

# ---- 배틀 ----
BATTLE_TTL = _int("POKET_BATTLE_TTL", 900)        # 배틀이 방치되면 정리되는 시간(초)
EXP_SHARE = _bool("POKET_EXP_SHARE", True)        # 학습장치: 파티 전원이 경험치를 받는다
EXP_SHARE_RATE = _int("POKET_EXP_SHARE_RATE", 50)  # 참가 안 한 포켓몬이 받는 비율(%)

# ---- 야생 조우 ----
# 풀숲이 돋아나기까지 걸리는 시간 (초). 이 사이에서 무작위로 정해진다.
WILD_COOLDOWN_MIN = _int("POKET_WILD_COOLDOWN_MIN", 600)    # 10분
WILD_COOLDOWN_MAX = _int("POKET_WILD_COOLDOWN_MAX", 900)    # 15분
GRASS_TTL = _int("POKET_GRASS_TTL", 90)     # 풀숲이 저절로 사라지기까지 (초)
WILD_TTL = _int("POKET_WILD_TTL", 60)       # 야생 포켓몬이 도망가기까지 (초)
# 풀숲을 놓쳤을 때 다시 돋아나기까지 (조금 짧게)
MISS_COOLDOWN = _int("POKET_MISS_COOLDOWN", 300)

# 테스트용 경험치 주입 경로를 열어 둘지. 운영에서는 반드시 0.
ALLOW_ADD_EXP = _bool("POKET_ALLOW_ADD_EXP", True)

# 서버가 뜬 뒤 빠진 도트를 뒤에서 미리 받아둘지.
# 처음 며칠은 이걸 켜두면 "그림이 안 뜨는" 일이 거의 없어진다.
WARM_SPRITES = _bool("POKET_WARM_SPRITES", True)

# ---- 도구 / 돈 ----
ITEMS_PATH = os.environ.get("POKET_ITEMS", os.path.join(ROOT, "data", "items.json"))
MONEY_START = _int("POKET_MONEY_START", 3000)     # 처음 주는 돈
# 야생을 **잡으면** 도구가 하나 떨어진다.
DROP_ON_CATCH = _float("POKET_DROP_ON_CATCH", 1.0)
# 배틀에서 **쓰러뜨려도** 떨어진다. 볼이 떨어져 아무것도 못 하는 상황을
# 막으려고 둔다 — 볼이 0개여도 배틀로는 다시 일어설 수 있어야 한다.
DROP_ON_WIN = _float("POKET_DROP_ON_WIN", 0.45)
# 이로치는 기념이니 좋은 것을 준다 (가중치가 낮은 쪽에서 다시 뽑는다).
DROP_SHINY_BONUS = _int("POKET_DROP_SHINY_BONUS", 3)
SELL_RATE = _float("POKET_SELL_RATE", 0.5)

# ---- 노력치 / 개체값 ----
EV_STAT_MAX = _int("POKET_EV_STAT_MAX", 252)      # 6세대 이후 기준
EV_TOTAL_MAX = _int("POKET_EV_TOTAL_MAX", 510)
EV_SHARE = _bool("POKET_EV_SHARE", True)          # 학습장치가 노력치도 나눠줄지
# 하이퍼트레이닝(병뚜껑) 을 쓸 수 있는 최소 레벨.
# 본가 9세대가 50 이다. 100 은 이 게임 속도로는 도달이 어렵다.
HYPER_MIN_LEVEL = _int("POKET_HYPER_MIN_LEVEL", 50)

# ---- 진화 ----
EVOLVE_AUTO = _bool("POKET_EVOLVE_AUTO", True)    # 조건이 되면 바로 진화

# ---- 몬스터볼 ----
# 수급 방식은 나중에 정하기로 하고, 지금은 가입 시 이만큼 준다.
BALLS_START = _int("POKET_BALLS_START", 10)

# ---- 스타팅 포켓몬 (1~9세대 어태커 3마리씩) ----
STARTERS = [
    (1, "BULBASAUR", "CHARMANDER", "SQUIRTLE"),
    (2, "CHIKORITA", "CYNDAQUIL", "TOTODILE"),
    (3, "TREECKO", "TORCHIC", "MUDKIP"),
    (4, "TURTWIG", "CHIMCHAR", "PIPLUP"),
    (5, "SNIVY", "TEPIG", "OSHAWOTT"),
    (6, "CHESPIN", "FENNEKIN", "FROAKIE"),
    (7, "ROWLET", "LITTEN", "POPPLIO"),
    (8, "GROOKEY", "SCORBUNNY", "SOBBLE"),
    (9, "SPRIGATITO", "FUECOCO", "QUAXLY"),
]
STARTER_SET = set(x for row in STARTERS for x in row[1:])
STARTER_LEVEL = _int("POKET_STARTER_LEVEL", 5)
