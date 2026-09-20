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

# ---- Turso (libSQL) ----
# 이게 있으면 SQLite 파일 대신 Turso 를 쓴다.
# Render 처럼 재시작하면 디스크가 날아가는 곳에서는 파일 DB 를 쓸 수 없다.
#   POKET_TURSO_URL   libsql://이름-계정.turso.io
#   POKET_TURSO_TOKEN turso db tokens create 로 만든 토큰
TURSO_URL = os.environ.get("POKET_TURSO_URL", "")
TURSO_TOKEN = os.environ.get("POKET_TURSO_TOKEN", "")
# 붙박이 복제본을 둘 로컬 경로. 읽기가 로컬에서 끝나 훨씬 빠르다.
# 비우면 매번 Turso 로 왕복한다(느리지만 디스크가 필요 없다).
TURSO_REPLICA = os.environ.get("POKET_TURSO_REPLICA", "")
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
# 랜덤 배틀을 한 판 걸고 다음 판을 걸기까지 (초). 1.4.1
RANDOM_COOLDOWN_SEC = _int("POKET_RANDOM_COOLDOWN_SEC", 30)
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
WILD_COOLDOWN_MIN = _int("POKET_WILD_COOLDOWN_MIN", 300)    # 5분
WILD_COOLDOWN_MAX = _int("POKET_WILD_COOLDOWN_MAX", 420)    # 7분
GRASS_TTL = _int("POKET_GRASS_TTL", 90)     # 풀숲이 저절로 사라지기까지 (초)
WILD_TTL = _int("POKET_WILD_TTL", 60)       # 야생 포켓몬이 도망가기까지 (초)
# 풀숲을 놓쳤을 때 다시 돋아나기까지 (조금 짧게)
MISS_COOLDOWN = _int("POKET_MISS_COOLDOWN", 150)

# 테스트용 뒷문 둘. **기본값은 꺼짐이다.**
# 예전에는 경험치 주입이 기본으로 열려 있어서, 배포 설정이 0 으로 덮어
# 주는 데만 의존하고 있었다. 그 설정을 빠뜨린 곳에 올리면 그대로 열린다.
# 이런 건 기본이 잠겨 있고 필요한 쪽에서 여는 게 맞다.
ALLOW_ADD_EXP = _bool("POKET_ALLOW_ADD_EXP", False)

# 오류 기록을 읽을 수 있는 열쇠. 비어 있으면 그 경로가 아예 없다.
# 개수는 /api/health 로 누구나 보지만, 역추적은 서버 안쪽 구조를 드러내므로
# 이 열쇠를 아는 사람만 본다.
ADMIN_KEY = os.environ.get("POKET_ADMIN_KEY", "")

# ---------------------------------------------------------------- 이벤트
# 50명 기념. 업데이트 뒤 **처음 돋는 풀숲**에 이 종이 숨어 있다.
#
# 기간이 없다. 앞으로 가입하는 사람도 첫 풀숲에서 만나므로, 성격이
# '기념' 이라기보다 **가입 선물**에 가깝다. 그렇게 하기로 정했다.
EVENT_SPECIES = os.environ.get("POKET_EVENT_SPECIES", "SHAYMIN")

# 레벨은 고정. roll_wild 를 안 거치므로 종족값 상한(330 + 레벨x8)에
# 걸리지 않는다 - 그냥 굴리면 파티 최저 레벨 34 이상인 사람만 만난다.
EVENT_LEVEL = _int("POKET_EVENT_LEVEL", 30)

# 이벤트 볼. **이걸 가진 사람에게만 이벤트 풀숲이 돋는다.**
#
# 운영자가 선물로 넣어 준 사람 = 이벤트 대상이다. 따로 명단을 두지
# 않는 이유가 그것이다 - 볼을 준 것 자체가 명단이라, 둘이 어긋날 수 없다.
EVENT_BALL = os.environ.get("POKET_EVENT_BALL", "FLOWERBALL")

# 그냥 놀다가 만날 확률. **이벤트 볼이 없는 모든 사람에게 해당한다** -
# 새로 가입한 사람도, 이미 잡은 사람도 이 확률로 만난다.
#
# 이 종은 이벤트가 끝나도 게임에 계속 남는다. 다만 아주 귀하다.
#
# 조우가 5~7분에 한 번(평균 6분)이라 하루 8시간 켜 두면 주 560회다.
# 0.2% 면 주 1.1회 - "일주일에 한 번" 쯤이다. 종일 켜 두는 사람은
# 주 서너 번이 된다.
EVENT_RESPAWN = _float("POKET_EVENT_RESPAWN", 0.002)

# 조우 간격을 무시하고 풀숲을 바로 돋울지. 테스트에서만 쓴다.
# 이게 없으면 야생이 걸린 테스트를 돌릴 수가 없다(첫 조우까지 기다려야 한다).
# 운영에서 열리면 5~7분 간격이 아무 의미가 없어진다.
ALLOW_FORCE_WILD = _bool("POKET_ALLOW_FORCE_WILD", False)

# 서버가 뜬 뒤 빠진 도트를 뒤에서 미리 받아둘지.
# 처음 며칠은 이걸 켜두면 "그림이 안 뜨는" 일이 거의 없어진다.
WARM_SPRITES = _bool("POKET_WARM_SPRITES", True)

# ---- 관장 도전 ----
GYMS_PATH = os.environ.get("POKET_GYMS", os.path.join(ROOT, "data", "gyms.json"))
KOREA_MAP_PATH = os.environ.get("POKET_KOREA_MAP", os.path.join(ROOT, "data", "korea_map.json"))
TRAINER_SPRITE_DIR = os.environ.get("POKET_TRAINER_SPRITES",
                                    os.path.join(ROOT, "data", "trainer_sprites"))
# 처음 이기면 레벨 x 50원 (Lv.20 1,000원 ~ Lv.100 5,000원). 원작 상금 느낌.
# 다시 이기면 레벨 x 5원을 **하루 한 번** 준다. 약한 곳을 돌며 돈을 찍어
# 내는 것을 막으면서도, 다시 붙을 이유는 남긴다.
GYM_PRIZE_PER_LEVEL = _int("POKET_GYM_PRIZE_PER_LEVEL", 50)
GYM_REPEAT_PER_LEVEL = _int("POKET_GYM_REPEAT_PER_LEVEL", 5)
# 손을 놓고 이만큼 지나면 판을 접는다(초). 앱을 끄고 사라져도 판이 영원히
# 남아 새 도전을 막지 않게.
GYM_BATTLE_TTL = _int("POKET_GYM_BATTLE_TTL", 3600)
# 경험치 배율. 원작 트레이너전은 야생의 1.5배지만, 여기서는 여섯 마리를 연달아
# 잡는 판이라 레벨이 너무 빨리 올랐다. 1.5 -> 1.2 (1.3.0 배포 뒤) -> 1.0 (1.3.2 배포 뒤,
# 야생과 같다).
GYM_EXP_RATE = _float("POKET_GYM_EXP_RATE", 1.0)

# ---- 도구 / 돈 ----
ITEMS_PATH = os.environ.get("POKET_ITEMS", os.path.join(ROOT, "data", "items.json"))
MONEY_START = _int("POKET_MONEY_START", 3000)     # 처음 주는 돈
# 야생을 **잡으면** 도구가 하나 떨어진다.
# 잡을 때마다 무조건 주면 도구가 너무 쉽게 쌓인다. 재보니 조우가 시간당
# 열 번쯤이고 드랍 하나의 평균 판매가가 855원이라, 잡기만 해도 시간당
# 8,500원(몬스터볼 42개어치)이 들어왔다.
# 잡으면 포켓몬이라는 보상이 이미 있으므로, 이기는 쪽(0.45)보다 낮게 둔다.
DROP_ON_CATCH = _float("POKET_DROP_ON_CATCH", 0.30)
# 배틀에서 **쓰러뜨려도** 떨어진다. 볼이 떨어져 아무것도 못 하는 상황을
# 막으려고 둔다 — 볼이 0개여도 배틀로는 다시 일어설 수 있어야 한다.
DROP_ON_WIN = _float("POKET_DROP_ON_WIN", 0.45)
# 이로치는 기념이니 좋은 것을 준다 (가중치가 낮은 쪽에서 다시 뽑는다).
DROP_SHINY_BONUS = _int("POKET_DROP_SHINY_BONUS", 3)
SELL_RATE = _float("POKET_SELL_RATE", 0.5)
# 기술 떠올리기 한 번 값. 본가 9세대는 공짜지만 여기서는 돈을 쓸 곳으로 둔다.
# 이상한사탕(10,000원)의 절반. 레벨업 때 자리가 없어 못 배운 기술(pending)은
# 이미 받을 몫이라 안 받는다.
REMEMBER_COST = _int("POKET_REMEMBER_COST", 5000)

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


# ---------------------------------------------------------------- 레이드
# 전설·환상 레이드 (1.5.0). 정해진 시간에 3~6인이 모여 보스를 잡고,
# 성공하면 **그 보스의 알**을 받는다. 알 종류가 무작위인 시즌 보상과 달리
# 무엇이 나올지 알고 들어간다.
#
# 날짜·시각은 전부 **한국시간(KST)** 이다. 서버는 도커 안이라 UTC 로 돌고
# pvp 의 하루 계산도 UTC 지만, 이벤트는 사람이 모이는 시각이 전부라
# 여기서는 KST 로 잰다 (raid.kst_now).
RAID_START = os.environ.get("POKET_RAID_START", "2026-09-22")   # 이날부터 (포함)
RAID_END = os.environ.get("POKET_RAID_END", "2026-10-06")       # 이날까지 (포함)
# 하루에 여는 회차 (KST 시각). 운영 자료상 11시가 가장 붐비고, 21시는
# 저녁에 오는 사람을 위한 자리다.
RAID_HOURS = tuple(int(x) for x in
                   os.environ.get("POKET_RAID_HOURS", "11,21").split(",") if x.strip())
RAID_OPEN_SEC = _int("POKET_RAID_OPEN_SEC", 300)      # 정각 몇 초 전부터 모이나 (5분)
RAID_GRACE_SEC = _int("POKET_RAID_GRACE_SEC", 120)    # 정각에 모자라면 더 기다리는 시간 (2분)
RAID_REVEAL_SEC = _int("POKET_RAID_REVEAL_SEC", 3600)  # 보스를 미리 알리는 시간 (1시간 전)

RAID_MIN_PLAYERS = _int("POKET_RAID_MIN_PLAYERS", 3)
RAID_MAX_PLAYERS = _int("POKET_RAID_MAX_PLAYERS", 6)
RAID_MIN_PARTY = _int("POKET_RAID_MIN_PARTY", 2)      # 데리고 와야 하는 최소 마릿수

# 레벨은 **전원 같게 맞춘다** (raid_battle.leveled). 높은 쪽은 내리고 낮은
# 쪽은 올린다 - Lv.30 과 Lv.100 이 한 방에 서는 판이라, 안 맞추면 낮은 쪽이
# 한 대에 쓰러져 구경만 한다. 개체값·노력치·성격·도구·기술은 그대로라
# 잘 키운 사람이 여전히 세다.
RAID_TEAM_LEVEL = _int("POKET_RAID_TEAM_LEVEL", 50)
RAID_BOSS_LEVEL = _int("POKET_RAID_BOSS_LEVEL", 60)
# 보스 체력 배율 = 기본 + 사람당. tools/sim_raid.py 로 쟀다
# (봇 기준 3인 68% · 4인 70% · 5인 73% · 6인 98%).
RAID_HP_BASE = _float("POKET_RAID_HP_BASE", 2.0)
RAID_HP_PER = _float("POKET_RAID_HP_PER", 1.6)
RAID_ROUNDS = _int("POKET_RAID_ROUNDS", 15)           # 이 안에 못 잡으면 실패
RAID_DOUBLE_FROM = _int("POKET_RAID_DOUBLE_FROM", 4)  # 몇 명부터 보스가 두 번 움직이나
RAID_ROUND_SEC = _int("POKET_RAID_ROUND_SEC", 25)     # 한 라운드 고르는 시간
RAID_TTL = _int("POKET_RAID_TTL", 1800)               # 아무도 안 오면 판을 접는다

# 보상. 알은 **확률**이다 - 참가 횟수를 막지 않는 대신 이걸로 조절한다.
# 3개 상한을 두면 사흘이면 다 채운 사람이 안 와서 3인이 안 모인다.
RAID_EGG_CHANCE = _float("POKET_RAID_EGG_CHANCE", 0.7)
RAID_PRIZE = _int("POKET_RAID_PRIZE", 3000)           # 이기면 전원
RAID_FAIL_PRIZE = _int("POKET_RAID_FAIL_PRIZE", 500)  # 져도 준다
RAID_TOP_PRIZE = (3000, 2000, 1000)                   # 기여 1~3위 덤


# ---------------------------------------------------------------- 실시간 배틀
# 친구끼리 **둘 다 접속한 채로** 두는 1:1. 지금까지의 유저 배틀은 매칭
# 순간 서버가 판 전체를 돌려 로그로 남기는 비동기였다(party_battle) -
# 그건 그대로 두고, 이쪽을 따로 둔다. 상대가 자고 있어도 붙을 수 있는
# 길은 남아 있어야 한다.
LIVE_LEVEL = _int("POKET_LIVE_LEVEL", 50)        # 양쪽 다 이 레벨로 맞춘다
LIVE_TURN_SEC = _int("POKET_LIVE_TURN_SEC", 30)  # 한 턴 고르는 시간
# 초대가 살아 있는 시간. **90초보다 넉넉해야 한다** - 상대가 초대를 알게
# 되는 가장 늦은 때가 다음 동기화(syncSeconds, 기본 90초)이기 때문이다.
# 친구 탭을 열어 두고 있으면 그 자리에서 바로 뜬다.
LIVE_INVITE_SEC = _int("POKET_LIVE_INVITE_SEC", 180)
LIVE_TTL = _int("POKET_LIVE_TTL", 900)           # 아무도 안 돌아오면 판을 접는다
LIVE_MAX_TURNS = _int("POKET_LIVE_MAX_TURNS", 150)
