# -*- coding: utf-8 -*-
"""포켓몬과 집중하기 — 규칙 숫자 (서버와 앱이 같이 읽는다).

집중 타이머를 켜면 고른 포켓몬 하나만 바탕화면에 남아 고른 능력의 동작(헬스 · 공부 · 달리기 …)을 한다.
**25분(한 세트)마다 그 능력의 노력치가 5 오른다.** 세트는 '집중 끝내기' 를 누를 때까지 저절로 이어진다.

  · 하루(KST)에 집중으로 받는 노력치는 40 까지. 그 뒤 세트는 시간만 기록된다 (영양제 10,000원 = +10 기준 4만 원어치).
  · 시간은 서버 시계다. 집중 중인 앱은 1분마다 맥박을 보낸다. **맥박 사이가 3분을 넘으면** 게임이 꺼졌거나
    컴퓨터가 잠들었던 것으로 보고 그 집중을 끝낸다 - 진행 중이던 세트는 인정하지 않는다 (사용자 결정 11/04).
  · 세트 중간에 끝내면 그 세트의 노력치는 0. 그 자투리 시간(1분 이상)은 달력에만 남는다.

설계: design-notes/2026-11-04-focus-timer.md
"""
import calendar
import datetime
import os

# 한 세트의 길이 (초). 검사 · 데모 화면만 환경값으로 줄인다 - 운영은 기본값.
SET_SEC = int(os.environ.get("POKET_FOCUS_SET_SEC", 1500))
EV_PER_SET = 5              # 세트마다 오르는 노력치
DAILY_EV = 40               # 하루(KST)에 집중으로 받는 노력치 상한
BEAT_SEC = 60               # 앱이 맥박을 보내는 간격
GAP_SEC = 180               # 맥박 사이가 이보다 길면 집중이 끊긴 것 (맥박 한두 번이 네트워크로 빠져도 버틴다)
PART_MIN_SEC = 60           # 끝내기 전 자투리를 달력에 남기는 최소 길이

# (능력, 동작, 능력 이름). 고르는 창에 이 순서로 나온다.
# 공격 · 특공 · 스피드는 사용자가 정했고 나머지 셋은 기획 제안 (11/04).
ACTS = (("atk", "헬스", "공격"), ("spa", "공부", "특공"), ("spe", "달리기", "스피드"),
        ("hp", "스트레칭", "체력"), ("def", "버티기", "방어"), ("spd", "명상", "특방"))
_ACT = dict((s, (a, k)) for s, a, k in ACTS)

KST = datetime.timezone(datetime.timedelta(hours=9))


def act_of(stat):
    """(동작, 능력 이름). 없는 능력이면 None."""
    return _ACT.get(stat)


def _kst(t):
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return t.astimezone(KST)


def kst_day(t):
    """그 시각의 한국 날짜 'YYYY-MM-DD'. tz 가 없으면 UTC 로 본다."""
    return _kst(t).strftime("%Y-%m-%d")


def kst_hour(t):
    return _kst(t).hour


def _date(s):
    return datetime.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))


def streaks(days, today):
    """(지금 연속 일수, 최고 연속 일수). days = 집중한 날 'YYYY-MM-DD' 모음 (겹쳐도 · 순서가 달라도 된다).

    지금 = 오늘로 끝나는 연속. 오늘 아직 안 했으면 어제로 끝나는 연속 (아직 끊긴 것이 아니다).
    """
    ds = sorted(set(_date(d) for d in days))
    if not ds:
        return 0, 0
    best = run = 1
    for a, b in zip(ds, ds[1:]):
        run = run + 1 if (b - a).days == 1 else 1
        best = max(best, run)
    have = set(ds)
    t = _date(today)
    end = t if t in have else t - datetime.timedelta(days=1)
    cur = 0
    while end in have:
        cur += 1
        end -= datetime.timedelta(days=1)
    return cur, best


def month_grid(ym):
    """'YYYY-MM' 달력: (1일이 몇 번째 칸인지 - 일요일 0, 그 달의 날 수)."""
    y, m = int(ym[0:4]), int(ym[5:7])
    wd, n = calendar.monthrange(y, m)           # wd: 월요일 0
    return (wd + 1) % 7, n
