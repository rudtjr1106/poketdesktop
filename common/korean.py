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


def josa(word, kind="을"):
    """단어 뒤에 붙일 조사 하나를 고른다."""
    pair = PAIRS.get(kind)
    if not pair:
        return kind
    b = has_batchim(word)
    if b is None:                       # 판단할 수 없으면 원래 표기를 지킨다
        return pair[0]
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
            r"|이\(가\)|가\(이\)|와\(과\)|과\(와\)|으로\(로\)|로\(으로\))")

    def rep(m):
        word, pair = m.group(1), m.group(2)
        return word + josa(word, pair[0])
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
