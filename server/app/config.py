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
MIN_USERNAME = 3
MAX_USERNAME = 16
MIN_PASSWORD = 8

# ---- 게임 규칙 ----
MAX_BOX = _int("POKET_MAX_BOX", 300)                   # 보유 상한
MAX_DESKTOP = _int("POKET_MAX_DESKTOP", 6)             # 바탕화면 동시 표시 상한
WILD_MIN_LEVEL = _int("POKET_WILD_MIN_LEVEL", 2)
WILD_MAX_LEVEL = _int("POKET_WILD_MAX_LEVEL", 12)
SHINY_RATE = _int("POKET_SHINY_RATE", 4096)

# ---- 야생 조우 ----
# 풀숲이 돋아나기까지 걸리는 시간 (초). 이 사이에서 무작위로 정해진다.
WILD_COOLDOWN_MIN = _int("POKET_WILD_COOLDOWN_MIN", 600)    # 10분
WILD_COOLDOWN_MAX = _int("POKET_WILD_COOLDOWN_MAX", 900)    # 15분
GRASS_TTL = _int("POKET_GRASS_TTL", 90)     # 풀숲이 저절로 사라지기까지 (초)
WILD_TTL = _int("POKET_WILD_TTL", 60)       # 야생 포켓몬이 도망가기까지 (초)
# 풀숲을 놓쳤을 때 다시 돋아나기까지 (조금 짧게)
MISS_COOLDOWN = _int("POKET_MISS_COOLDOWN", 300)

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
