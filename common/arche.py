# -*- coding: utf-8 -*-
"""아르케의 여섯 봉인 (시즌 6 이벤트, 2.4.0) — 서버와 화면이 같이 쓰는 규칙.

설계 design-notes/2026-11-09-arche.md. **이 파일은 공개 저장소에 있다** - 수수께끼 글 · 정답 · 의식 조건 ·
숨은 페이지 이름은 여기 없다 (운영 볼륨의 비공개 secrets.json 에만). 여기 있는 것은

    장 표 (CHAPTERS) · 장소마다 전설 후보 (POOLS) · 장 경계 시각 (window · chapter_at)
    사람마다 전설 뽑기 (legends_for - 시드에 비공개 소금을 섞어 미리 셈해 볼 수 없다)
    말 정규화 (normalize) · 브라우저 창 제목 꼬리 떼기 (title_core) · 제목 해시 (key_hash)

## 시각

시작 날은 POKET_ARCHE_START (기본 2026-11-16, KST 0시 - 시즌 6 시작 날, 11/11 사용자). 검사 · 시연 때 통째로 민다 - 시즌 번호에 묶지 않는다.
장은 이어서 열린다 (2 · 2 · 2 · 3 · 2 · 3 일). 열린 순간은 그 장, 닫힌 순간은 다음 장이다.
"""
import datetime
import hashlib
import os
import random
import re
import unicodedata

KST = datetime.timezone(datetime.timedelta(hours=9))
UTC = datetime.timezone.utc
DEFAULT_START = datetime.date(2026, 11, 16)

# 장 표. offset = 시작 날에서 며칠 뒤에 열리나 (앞 장들의 길이 합), slots = 한 사람이 만나는 전설 수.
_RAW = [
    (1, "cave", "돌의 문", "동굴", 2, 3),
    (2, "volcano", "불의 산", "화산", 2, 1),
    (3, "abyss", "가라앉은 신전", "심해", 2, 1),
    (4, "sky", "하늘의 탑", "구름 위", 3, 1),
    (5, "castle", "두 영웅의 성", "모래 속 고성", 2, 2),
    (6, "throne", "거인의 왕좌", "왕좌", 3, 1),
]
CHAPTERS = []
_off = 0
for _n, _key, _kr, _pkr, _days, _slots in _RAW:
    CHAPTERS.append({"n": _n, "key": _key, "kr": _kr, "place": _key, "placeKr": _pkr,
                     "offset": _off, "days": _days, "slots": _slots})
    _off += _days
TOTAL_DAYS = _off
_BY_N = dict((c["n"], c) for c in CHAPTERS)

# 진화 전 전설 넷 (타입:널 · 코스모그 · 코스모움 · 치고마) - 의식 끝에 나오면 허무하다 (설계 '내가 정한 것').
EXCLUDED = (772, 789, 790, 891)

# 장소마다 전설 후보 (전국도감 번호, 설계 문서 표 그대로). 환상은 없다. 장소끼리 겹치지 않는다 (모두 67종).
POOLS = {
    # 뮤츠 · 레지락 · 레지아이스 · 레지스틸 · 유크시 · 엠라이트 · 아그놈 · 지가르데 · 네크로즈마 · 레지에레키 · 레지드래고 · 딩루 · 테라파고스
    "cave": (150, 377, 378, 379, 480, 481, 482, 718, 800, 894, 895, 1003, 1024),
    # 파이어 · 앤테이 · 칠색조 · 그란돈 · 히드런 · 테라키온 · 랜드로스 · 우라오스 · 위유이 · 코라이돈
    "volcano": (146, 244, 250, 383, 485, 639, 645, 892, 1004, 1007),
    # 프리져 · 스이쿤 · 루기아 · 가이오가 · 크레세리아 · 카푸느지느 · 블리자포스 · 파오젠
    "abyss": (144, 245, 249, 382, 488, 788, 896, 1002),
    # 썬더 · 라이코 · 라티아스 · 라티오스 · 레쿠쟈 · 토네로스 · 볼트로스 · 이벨타르 · 카푸꼬꼬꼭 · 솔가레오 · 루나아라 · 러브로스 · 미라이돈
    "sky": (145, 243, 380, 381, 384, 641, 642, 717, 785, 791, 792, 905, 1008),
    # 코바르온 · 비리디온 · 레시라무 · 제크로무 · 큐레무 · 실버디 · 카푸나비나 · 카푸브루루 · 자시안 · 자마젠타 ·
    # 레이스포스 · 버드렉스 · 총지엔 · 조타구 · 이야후 · 기로치 · 오거폰
    "castle": (638, 640, 643, 644, 646, 773, 786, 787, 888, 889, 897, 898, 1001, 1014, 1015, 1016, 1017),
    # 디아루가 · 펄기아 · 레지기가스 · 기라티나 · 제르네아스 · 무한다이노
    "throne": (483, 484, 486, 487, 716, 890),
}


def chapter(n):
    """장 번호 -> 장 표의 한 줄 (없으면 None)."""
    try:
        return _BY_N.get(int(n))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- 시각
def start_day():
    """1장이 열리는 날 (KST). POKET_ARCHE_START 로 민다 - 값이 깨졌으면 기본 날."""
    raw = (os.environ.get("POKET_ARCHE_START") or "").strip()
    if raw:
        try:
            return datetime.date.fromisoformat(raw)
        except ValueError:
            pass
    return DEFAULT_START


def _kst_midnight(day):
    return datetime.datetime(day.year, day.month, day.day, tzinfo=KST).astimezone(UTC)


def window(n):
    """n 장이 열려 있는 때 (열림, 닫힘) - UTC aware. 닫힘 순간은 이미 다음 장이다. 모르는 장은 None."""
    c = chapter(n)
    if c is None:
        return None
    first = start_day()
    opens = _kst_midnight(first + datetime.timedelta(days=c["offset"]))
    closes = _kst_midnight(first + datetime.timedelta(days=c["offset"] + c["days"]))
    return opens, closes


def event_window():
    """이벤트 전체 (1장 열림, 6장 닫힘)."""
    return window(CHAPTERS[0]["n"])[0], window(CHAPTERS[-1]["n"])[1]


def chapter_at(now):
    """지금 열려 있는 장 번호 (1~6). 이벤트 밖이면 0."""
    for c in CHAPTERS:
        lo, hi = window(c["n"])
        if lo <= now < hi:
            return c["n"]
    return 0


# ---------------------------------------------------------------- 사람마다 전설
def legends_for(uid, n, salt=""):
    """그 사람이 n 장에서 만나는 전설 (전국도감 번호, 길이 = 그 장의 자리 수).

    시드 = sha256("arche:<소금>:<uid>:<장>") - **소금은 비공개라** 이 코드를 읽어도 남의 · 나의 전설을 미리 셀 수 없다.
    그 장소 후보에서 겹치지 않게 뽑는다. 같은 사람 · 같은 장이면 늘 같다 (다시 들어가도 안 바뀐다).
    """
    c = chapter(n)
    if c is None:
        return []
    seed = int(hashlib.sha256(("arche:%s:%s:%d" % (salt or "", int(uid), c["n"])).encode("utf-8")).hexdigest(), 16)
    pool = list(POOLS[c["key"]])
    return random.Random(seed).sample(pool, min(c["slots"], len(pool)))


# ---------------------------------------------------------------- 말 · 창 제목
def normalize(text):
    """비교용 말: NFC · 소문자 · 글자와 숫자만 (공백 · 문장부호 · 기호를 뗀다)."""
    s = unicodedata.normalize("NFC", str(text or "")).lower()
    return "".join(ch for ch in s if unicodedata.category(ch)[0] in ("L", "N"))


# 브라우저 창 제목의 꼬리 (" - Google Chrome" ...). 줄표는 -, –, — 다 받는다.
_BROWSERS = ("google chrome", "chrome", "microsoft edge", "edge", "mozilla firefox", "firefox",
             "naver whale", "whale", "네이버 웨일", "웨일", "opera", "brave", "vivaldi", "safari")
_TAIL = re.compile(r"\s+[-–—]\s+(%s)\s*$" % "|".join(re.escape(b) for b in _BROWSERS), re.IGNORECASE)
# 엣지는 브라우저 이름 앞에 프로필 이름을 하나 더 붙인다 ("제목 - 개인 - Microsoft Edge")
_PROFILE = re.compile(r"\s+[-–—]\s+(개인|업무|personal|work|inprivate)\s*$", re.IGNORECASE)
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


def title_core(title):
    """맨 앞 창 제목에서 브라우저 꼬리를 뗀 것. 꼬리가 없으면 그대로 (앞뒤 공백만 뗀다)."""
    s = unicodedata.normalize("NFC", str(title or "")).translate(_INVISIBLE).strip()
    m = _TAIL.search(s)
    if not m:
        return s
    s = s[:m.start()]
    if "edge" in m.group(1).lower():
        s = _PROFILE.sub("", s)
    return s.strip()


def key_hash(salt, text):
    """sha256(소금 + 정규화한 말) 16진수. 화면은 서버가 준 해시와 창 제목의 이것만 비교한다 (제목은 안 보낸다)."""
    return hashlib.sha256(((salt or "") + normalize(text)).encode("utf-8")).hexdigest()
