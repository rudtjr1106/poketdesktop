# -*- coding: utf-8 -*-
"""부적절한 닉네임 거르기 (2.5.8, 2026-11-24).

초성 욕 닉네임 계정이 생겼다 (운영자가 닉네임 변경권을 주고 바꿔 달라고 했다). 닉네임은 랭킹 · 게시판 · 길드 · 대전에서
남에게 보인다 - 가입 · 닉네임 변경 때 서버가 거른다 (auth.check_username 이 여기를 본다 - 가입 · 가입 화면의 확인 ·
닉네임 변경 세 곳이 다 그 함수를 쓴다).

    bad(name) -> bool            걸리나
    why(name) -> 까닭 | None     "profanity" 욕설 · "sexual" 성적인 말 · "hate" 혐오 표현 · "staff" 운영진 사칭

## 보는 모습 셋

닉네임에는 한글 · 낱자모 · 영문 · 숫자 · 공백 · _ - . 만 들어온다 (auth.USERNAME_RE). 금지어 사이에 그런 것을 끼워
넣는 변형을 같이 잡으려고, 이름을 세 모습으로 바꿔 본다.

    한글   소문자로, 공백 · _ - . · 숫자를 뺀다                   '시1발' · 'ㅅ ㅂ' · '씨.발'
    영어   1->i 0->o 3->e 4->a 5->s 7->t 로 바꾼 뒤 글자만         'sh1t' · 'f.u.c.k' · '5ex'
    자모   **이름에 낱자모가 있을 때만**, 글자를 자모로 풀어서      'ㅅㅣㅂㅏㄹ' (낱자모로 친 욕)

영어는 두 갈래다: 어디에 들어 있든 막는 말(EN_ANY)과 **낱말 하나로** 있을 때만 막는 말(EN_WORD - 'ass' 는 막고
'assassin' · 'bass' 는 둔다, 'GM철수' · 'admin_kim' 은 막고 'Sigma' · 'badminton' 은 둔다 - rename 이 하던 그대로).

## 무해한 말 (OK_*)

금지어가 우연히 든 무해한 말(시바견 · 시발점 · 보지마 · 새끼고양이 · 무지개같은 · Essex ...)은 **먼저 지우고** 본다.
그래도 오탐은 남는다 - 그때는 예외에 더한다. 반대로 빠져나가는 변형이 보이면 금지어에 더한다. 낱말을 고르는 기준은
'남이 봤을 때 욕 · 음란 · 혐오로 읽히나' 다. 가볍게 놀리는 말(바보 · 멍청이)이나 뜻이 여럿인 말(고추 · 성기 · 운지)은 넣지 않았다.

## 하지 않는 것

  · **이미 있는 계정은 건드리지 않는다.** 로그인은 닉네임을 다시 검사하지 않는다 - 걸리는 기존 닉네임은
    tools/bad_names.py 로 뽑아 운영자가 본다.
  · 거절 문구는 어떤 말에 걸렸는지 알려 주지 않는다 (auth: "쓸 수 없는 닉네임입니다.") - 알려 주면 피해 가는 법을 가르친다.
  · 길드 이름 · 포켓몬 별명은 아직 안 건다 (걸려면 bad() 를 부르면 된다).
"""
import re

# ---------------------------------------------------------------- 한글 (한글 모습에 들어 있으면 막는다)
PROFANITY_KO = (
    "시발", "씨발", "씨바", "시바", "씨팔", "시팔", "씨빨", "씨벌", "쓰발", "쉬발", "슈발", "씹", "좆", "좃", "존나", "좆나",
    "지랄", "병신", "븅신", "빙신", "새끼", "새키", "색히", "썅", "쌍년", "쌍놈", "염병", "엿먹", "꺼져", "닥쳐",
    "미친놈", "미친년", "미친새", "개같", "개년", "개놈", "개자식", "느금", "니애미", "애미없", "엠창", "앰창",
    "창녀", "창놈", "걸레년", "화냥", "후레자식", "호로새",
)
# 초성 · 낱자모 욕. 한글 모습(풀지 않은 것)에서만 본다 - 풀어 놓은 글자에서 찾으면 멀쩡한 말이 다 걸린다.
PROFANITY_JAMO = ("ㅅㅂ", "ㅆㅂ", "ㅅㅍ", "ㅆㅍ", "ㅂㅅ", "ㅄ", "ㅈㄹ", "ㅈㄴ", "ㅈㄲ", "ㅅㄲ", "ㄲㅈ", "ㅗ")
SEXUAL_KO = (
    "섹스", "쎅스", "섹쓰", "보지", "자지", "불알", "부랄", "딸딸이", "자위행위", "야동", "야설", "포르노", "강간",
    "성폭행", "성추행", "몰카", "애널", "젖꼭지", "젖탱",
)
HATE_KO = ("한남충", "김치녀", "맘충", "틀딱", "짱깨", "쪽바리", "깜둥이", "일베충")
# 운영진으로 보일 수 있는 이름 (2.1.1 의 rename.BANNED - 닉네임 변경 때만 막던 것을 가입에도 건다)
STAFF_KO = ("운영자", "운영진", "관리자", "개발자", "포스크탑")
# 금지어가 우연히 든 무해한 말 - 먼저 지운다
OK_KO = (
    "시바견", "시바이누", "시바스", "시바개", "시바타", "시발점", "시발역",
    "보지마", "보지못", "보지않", "보지도", "보지는", "해보지", "가보지", "돌보지", "어보지", "아보지",
    "자지마", "자지않", "자지도", "자지러", "잠자지", "안자지",
    "새끼손", "새끼발", "새끼줄", "새끼고양이", "새끼강아지",
    "씹어", "씹는", "씹다", "씹고", "씹을", "무지개같", "애널리스트", "꺼져있", "꺼져가",
)

# ---------------------------------------------------------------- 영어
# 어디에 들어 있든 막는다 (영어 모습 - 숫자로 바꿔 쓴 것을 되돌리고 글자만 남긴 것). 뒤의 넷은 쿼티로 친 한글 욕.
PROFANITY_EN = ("fuck", "shit", "bitch", "cunt", "whore", "slut", "asshole", "sibal", "ssibal",
                "tlqkf", "qudtls", "wlfkf", "whssk")
SEXUAL_EN = ("sex", "porn", "pussy", "dildo", "penis", "vagina", "hentai", "blowjob")
HATE_EN = ("nigger", "nigga")
OK_EN = ("essex", "sussex", "middlesex", "unisex", "sextant", "sexton", "scunthorpe")
# 낱말 하나로 있을 때만 막는다 (원래 이름을 글자 아닌 것에서 끊은 낱말)
SEXUAL_WORD = ("ass", "cock", "dick", "cum")
HATE_WORD = ("fag",)
STAFF_WORD = ("admin", "gm")

LEET = str.maketrans("103457", "ioeast")
_DROP = re.compile(r"[\s_.\-0-9]+")
_LETTERS = re.compile(r"[^a-z]+")
_JAMO = re.compile(r"[ㄱ-ㅎㅏ-ㅣ]")
CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JONG = ("", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ",
        "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ")


def _spell(s):
    """한글 글자를 자모로 푼다 ('시발' -> 'ㅅㅣㅂㅏㄹ'). 다른 글자는 그대로."""
    out = []
    for ch in s:
        i = ord(ch) - 0xAC00
        if 0 <= i < 11172:
            out.append(CHO[i // 588] + JUNG[(i % 588) // 28] + JONG[i % 28])
        else:
            out.append(ch)
    return "".join(out)


def _strip(s, words):
    for w in words:
        s = s.replace(w, "")
    return s


_KO = (("profanity", PROFANITY_KO), ("sexual", SEXUAL_KO), ("hate", HATE_KO), ("staff", STAFF_KO))
_KO_SPELLED = tuple((why_, tuple(_spell(w) for w in words)) for why_, words in _KO)
_EN = (("profanity", PROFANITY_EN), ("sexual", SEXUAL_EN), ("hate", HATE_EN))
_WORD = (("sexual", SEXUAL_WORD), ("hate", HATE_WORD), ("staff", STAFF_WORD))


def why(name):
    """이 닉네임이 걸리는 까닭 ("profanity" · "sexual" · "hate" · "staff"). 괜찮으면 None."""
    low = (name or "").lower()
    if not low:
        return None
    ko = _strip(_DROP.sub("", low), OK_KO)
    for reason, words in _KO:
        if any(w in ko for w in words):
            return reason
    if any(w in ko for w in PROFANITY_JAMO):
        return "profanity"
    if _JAMO.search(ko):
        # 낱자모로 친 말 ('ㅅㅣㅂㅏㄹ'). 이름에 낱자모가 있을 때만 푼다 - 늘 풀면 글자 경계를 넘어 멀쩡한 말이 걸린다 ('가시밭')
        spelled = _spell(ko)
        for reason, words in _KO_SPELLED:
            if any(w in spelled for w in words):
                return reason
    en = _strip(_LETTERS.sub("", low.translate(LEET)), OK_EN)
    for reason, words in _EN:
        if any(w in en for w in words):
            return reason
    tokens = set(_LETTERS.split(low))
    for reason, words in _WORD:
        if tokens & set(words):
            return reason
    return None


def bad(name):
    """부적절한 닉네임인가 (why 가 까닭을 준다)."""
    return why(name) is not None
