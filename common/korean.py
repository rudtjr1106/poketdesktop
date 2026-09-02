# -*- coding: utf-8 -*-
"""한국어 조사 붙이기.

"파이리 을(를) 잡았다!" 처럼 괄호로 도망가지 않으려고 만들었다.
마지막 글자에 받침이 있는지 보고 알맞은 조사를 고른다.

    josa("파이리", "을")  -> "를"     (받침 없음)
    josa("팬텀", "을")    -> "을"     (받침 있음)
    with_josa("파이리", "을")  -> "파이리를"
"""

# (받침 있을 때, 받침 없을 때)
PAIRS = {
    "을": ("을", "를"), "를": ("을", "를"),
    "은": ("은", "는"), "는": ("은", "는"),
    "이": ("이", "가"), "가": ("이", "가"),
    "과": ("과", "와"), "와": ("과", "와"),
    "으로": ("으로", "로"), "로": ("으로", "로"),
    "아": ("아", "야"), "야": ("아", "야"),
}


def has_batchim(word):
    """마지막 글자에 받침이 있는지. 한글이 아니면 None."""
    for ch in reversed(word or ""):
        if ch.isspace():
            continue
        if "가" <= ch <= "힣":
            return (ord(ch) - 0xAC00) % 28 != 0
        if ch.isdigit():
            # 숫자는 읽는 소리로 판단한다 (1 일, 2 이, 3 삼 ...)
            return ch in "0136780"
        if ch.isalpha():
            # 영문은 흔한 경우만. 애매하면 받침 있는 쪽으로 둔다.
            return ch.lower() not in "aeiouy"
        return None
    return None


def _rieul(word):
    """마지막 글자의 받침이 'ㄹ' 인지. (이상해풀, 물, 서울 ...)"""
    for ch in reversed(word or ""):
        if ch.isspace():
            continue
        if "가" <= ch <= "힣":
            return (ord(ch) - 0xAC00) % 28 == 8
        return False
    return False


def josa(word, kind="을"):
    """단어 뒤에 붙일 조사 하나를 고른다."""
    pair = PAIRS.get(kind)
    if not pair:
        return kind
    b = has_batchim(word)
    if b is None:                       # 판단할 수 없으면 원래 표기를 지킨다
        return pair[0]
    # 'ㄹ' 받침은 '으로' 가 아니라 '로' 다 — 이상해풀로, 서울로, 물로.
    if b and pair == ("으로", "로") and _rieul(word):
        return "로"
    return pair[0] if b else pair[1]


def with_josa(word, kind="을"):
    """단어와 조사를 붙여서 돌려준다."""
    return "%s%s" % (word, josa(word, kind))


_PAIR_RE = None


def natural(text):
    """이미 만들어진 문장에서 '파이리 을(를)' 같은 부분을 알맞게 고친다.

    서버가 보낸 메시지까지 화면에 나가기 직전에 한 번만 통과시키면 되도록
    만들었다. 문장마다 조사를 신경 쓸 필요가 없다.
    """
    global _PAIR_RE
    if _PAIR_RE is None:
        import re
        _PAIR_RE = re.compile(
            r"(\S+?)\s*(을\(를\)|를\(을\)|은\(는\)|는\(은\)"
            r"|이\(가\)|가\(이\)|와\(과\)|과\(와\)|으로\(로\)|로\(으로\)"
            r"|\(으\)로)")

    def rep(m):
        word, pair = m.group(1), m.group(2)
        # 앞쪽 표기가 곧 조사 이름이다. 한 글자만 떼면 '으로(로)' 가
        # '으' 가 되어버려서 "리자드으" 같은 글자가 남는다.
        kind = "으로" if pair == "(으)로" else pair.split("(")[0]
        return word + josa(word, kind)
    try:
        return _PAIR_RE.sub(rep, text or "")
    except Exception:
        return text


def fmt(template, word, **kw):
    """'{name}{을} 잡았다!' 같은 틀을 채운다.

    {을} {는} {가} {와} {로} 자리에 알맞은 조사가 들어간다.
    """
    values = {"name": word}
    for k in ("을", "를", "은", "는", "이", "가", "과", "와", "으로", "로", "아", "야"):
        values[k] = josa(word, k)
    values.update(kw)
    return template.format(**values)


# ---------------------------------------------------------------- 지난 시간
def ago(seconds):
    """몇 초 전인지를 사람 말로. "방금" · "12분 전" · "3주 전".

    **이 값은 센 쪽에서 받아야 한다.** 시각을 받아 내 시계로 빼면, 몇 분
    틀어진 PC 에서 방금 접속한 사람이 "3시간 전" 으로 보이거나 아예 미래로
    나온다. 사람들 PC 시계는 생각보다 잘 틀어져 있다.

    모르면(None) 빈 문자열이다. 틀린 값을 보여주느니 비워 둔다.

    며칠·몇 달을 딱 잘라 세지 않는다. "3주 전" 이 "21일 전" 보다 읽기 쉽고,
    이 화면에서 하루 이틀 차이는 아무 의미가 없다.
    """
    if seconds is None:
        return ""
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return ""
    if s < 60:
        return "방금"               # 음수(시계가 앞선 경우)도 여기로 온다
    m = s // 60
    if m < 60:
        return "%d분 전" % m
    h = m // 60
    if h < 24:
        return "%d시간 전" % h
    d = h // 24
    if d < 7:
        return "%d일 전" % d
    if d < 30:
        return "%d주 전" % (d // 7)
    if d < 365:
        return "%d달 전" % (d // 30)
    y = d // 365
    return "%d년 전" % y if y < 10 else "오래전"
