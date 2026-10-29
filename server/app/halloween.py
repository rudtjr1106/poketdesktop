# -*- coding: utf-8 -*-
"""할로윈 이벤트 (2026-10-31 하루). 서버만 바뀐다 - 앱은 그대로다.

  · 야생: 고스트 타입 종이 HALLOWEEN_GHOST_MULT 배 잘 나온다 (main._make_grass -> roll_wild 의 boost)
  · 드랍: 이상한사탕이 HALLOWEEN_CANDY_MULT 배 잘 떨어진다 (items.roll_drop)

날짜는 한국시간으로 잰다. 서버는 도커 안이라 UTC 로 도는데, 그대로 두면 31일 아침 9시에 시작해서
11월 1일 아침 9시에 끝난다. 풀숲은 돋을 때 무엇이 숨을지 정하고, 드랍은 이기거나 잡은 순간에 굴린다.
"""
import datetime

from . import config

KST = datetime.timedelta(hours=9)
GHOST = ("GHOST",)
CANDY = "RARECANDY"


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def today(now=None):
    """한국시간 오늘 날짜 'YYYY-MM-DD'."""
    t = now or _now()
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return (t.astimezone(datetime.timezone.utc) + KST).date().isoformat()


def on(now=None):
    """오늘이 할로윈 이벤트 날인가."""
    return config.HALLOWEEN_START <= today(now) <= config.HALLOWEEN_END


def spawn_boost(now=None):
    """야생을 굴릴 때 넘길 boost - (타입들, 배수). 이벤트가 아니면 None (평소 그대로)."""
    if not on(now) or config.HALLOWEEN_GHOST_MULT <= 1:
        return None
    return (GHOST, config.HALLOWEEN_GHOST_MULT)


def drop_boost(now=None):
    """드랍표에 곱할 것 {도구 id: 배수}. 이벤트가 아니면 빈 dict."""
    if not on(now) or config.HALLOWEEN_CANDY_MULT <= 1:
        return {}
    return {CANDY: config.HALLOWEEN_CANDY_MULT}
