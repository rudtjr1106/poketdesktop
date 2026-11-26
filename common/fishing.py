# -*- coding: utf-8 -*-
"""낚시 (시즌 7) — 규칙 숫자와 순수 계산 (서버가 읽고, 앱도 읽을 수 있다).

  · 낚시 위주 종 (FISH_ONLY): 풀숲에서는 빠지고(열린 뒤) 낚시 표에서는 가중치 x3. 탐험 '바다' · 공습에는 그대로 남는다
    (낚시를 안 하는 사람도 도감을 채울 길이 남게 - 설계 '사용자에게 물을 것' 4).
  · 크기 배율: 보통 0.80~1.20 (가운데가 많게), 대물 1.30~1.60, 왕대물(대물의 열에 하나) 1.60~2.00.
    순위는 무게가 아니라 이 배율로 겨룬다 (고래왕 398kg 이 잉어킹 10kg 을 늘 이기지 않게).
  · 주는 한국 시각 월요일 0시에 바뀐다. 주 열쇠 = 그 월요일 날짜 "YYYY-MM-DD".

설계: design-notes/2026-11-26-fishing.md
"""
import datetime

KST = datetime.timezone(datetime.timedelta(hours=9))
UTC = datetime.timezone.utc

# 낚시 위주 종 (설계 목록, 내부 이름). 진화 갈래를 통째로 넣는다 - 풀숲 야생은 레벨에 맞게 진화한 모습으로 나오므로
# (Pokedex.grown_form) 한 단계만 빼면 진화한 쪽이 풀숲에 남는다. 장침바루(악 · 독)는 물 타입이 아니라 뺀다.
FISH_ONLY = frozenset((
    "MAGIKARP", "GYARADOS",                       # 잉어킹 · 갸라도스
    "GOLDEEN", "SEAKING",                         # 콘치 · 왕콘치
    "HORSEA", "SEADRA", "KINGDRA",                # 쏘드라 · 시드라 · 킹드라
    "CHINCHOU", "LANTURN",                        # 초라기 · 랜턴
    "QWILFISH",                                   # 침바루
    "REMORAID", "OCTILLERY",                      # 총어 · 대포무노
    "MANTYKE", "MANTINE",                         # 타만타 · 만타인
    "CARVANHA", "SHARPEDO",                       # 샤프니아 · 샤크니아
    "WAILMER", "WAILORD",                         # 고래왕자 · 고래왕
    "BARBOACH", "WHISCASH",                       # 미꾸리 · 메깅
    "FEEBAS", "MILOTIC",                          # 빈티나 · 밀로틱
    "LUVDISC",                                    # 사랑동이
    "RELICANTH",                                  # 시라칸
    "FINNEON", "LUMINEON",                        # 형광어 · 네오라이트
    "BASCULIN", "BASCULEGION",                    # 배쓰나이 · 대쓰여너
    "ALOMOMOLA",                                  # 맘복치
    "WISHIWASHI",                                 # 약어리
    "BRUXISH",                                    # 치갈기
    "ARROKUDA", "BARRASKEWDA",                    # 찌로꼬치 · 꼬치조
    "FINIZEN", "PALAFIN",                         # 맨돌핀 · 돌핀맨
    "VELUZA",                                     # 가비루사
    "DONDOZO",                                    # 어써러셔
    "TATSUGIRI",                                  # 싸리용
))
FISH_ONLY_MULT = 3          # 낚시 표에서 낚시 위주 종의 가중치 배수

# 크기 배율
NORMAL_LO, NORMAL_MID, NORMAL_HI = 0.80, 1.00, 1.20
BIG_LO, BIG_HI = 1.30, 1.60
HUGE_LO, HUGE_HI = 1.60, 2.00
HUGE_SHARE = 0.10           # 대물 가운데 왕대물 몫
BIG_BASE = 0.04             # 대물 확률 - 기본
BIG_BAIT = 0.04             #   + 미끼를 달았으면
BIG_PERFECT = 0.04          #   + 완벽한 챔질이면


def big_chance(bait=False, perfect=False):
    """대물 확률. 기본 4% · 미끼 +4% · 완벽한 챔질 +4%."""
    # 소수 셋째 자리에서 끊는다 - 0.04 + 0.04 + 0.04 가 0.12000000000000001 이 되지 않게 (표에 그대로 보인다)
    return round(BIG_BASE + (BIG_BAIT if bait else 0) + (BIG_PERFECT if perfect else 0), 3)


def roll_ratio(rng, big_chance):
    """크기 배율 하나. 원래 값(반올림 안 함) - 순위가 이 값으로 줄을 세운다."""
    if rng.random() < big_chance:
        if rng.random() < HUGE_SHARE:
            return rng.uniform(HUGE_LO, HUGE_HI)
        return rng.uniform(BIG_LO, BIG_HI)
    return rng.triangular(NORMAL_LO, NORMAL_HI, NORMAL_MID)


def badge(ratio):
    """'huge' (1.6배 이상, 왕대물) · 'big' (1.3배 이상, 대물) · None."""
    if ratio is None:
        return None
    if ratio >= HUGE_LO:
        return "huge"
    if ratio >= BIG_LO:
        return "big"
    return None


def grams(kg, ratio):
    """잰 무게 (그램). 표준은 종의 kg - 도감의 weight 는 출현 가중치라 헷갈리지 않게 이름으로 받는다."""
    return int(round(float(kg) * 1000 * float(ratio)))


# ---------------------------------------------------------------- 주
def week_key(dt_utc):
    """그 시각이 든 주의 열쇠 - 한국 시각 월요일 날짜 "YYYY-MM-DD". 시간대 없는 값은 UTC 로 본다."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=UTC)
    d = dt_utc.astimezone(KST).date()
    return (d - datetime.timedelta(days=d.weekday())).isoformat()


def week_start_utc(key):
    """주 열쇠의 시작 시각 (월 00:00 KST) 을 UTC 로."""
    d = datetime.date.fromisoformat(key)
    return datetime.datetime(d.year, d.month, d.day, tzinfo=KST).astimezone(UTC)
