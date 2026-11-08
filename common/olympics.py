# -*- coding: utf-8 -*-
"""포스크탑 올림픽 — 규칙 (서버와 앱이 같이 읽는다).

평일 7번(11/16~11/24), **하루 한 종목, 오후 2시(KST)에 그 종목의 예선부터 결승까지 다 치른다** (사용자 결정 11/06 ·
11/08). 11/15 부터 종목마다 포켓몬과 작전을 신청해 두면 그 종목 날 2시에 서버가 실제 올림픽처럼 참가 수에 맞춰 라운드 ·
조를 배정해 한꺼번에 치르고(common/olympics_rounds.py), 앱은 내 포켓몬이 뛰는 조와 결승을 바탕화면에서 중계한다.
메달은 그날 결승 순위다.

## 기록 = 기본값 x (1 + 아래를 더한 것) - 노력치 · 개체값 · 레벨 · 성격 · 도구 · 이로치는 안 본다

    적성        ±5%   그 종목 능력의 종족값이 1025종 가운데 몇 번째인지(백분위) - 극단적으로 높아도 이득이 거의 없다
    체형        ±4%   몸무게가 그 종목의 알맞은 무게에 가까울수록 (log 거리)
    특기 타입    +5%   특기 특성 +3%   싫어하는 타입 -3% (지금은 쓰는 종목이 없다)
    오늘의 응원  +5%   종목마다 두 타입 (CHEER - 그 종목 특기 타입과 안 겹친다)
    지침        0~-5%  그 종목 신청자 중 같은 종의 몫이 5% 이상이면 -5%, 적으면 몫에 비례 (2시에 확정)
    작전        안정: 운 표준편차 6% · 실수 5%   승부수: +3% · 운 11% · 실수 15%
    운          최대 ±20% 로 자른다. 실수는 달리기형 -8% · 시기형 파울(그 시기 기록 없음)

설계: design-notes/2026-11-05-olympics.md · 2026-11-08-olympics-rounds.md (하루 한 종목 · 라운드)
"""
import bisect
import datetime
import math
import os
import random

KST = datetime.timezone(datetime.timedelta(hours=9))
UTC = datetime.timezone.utc

# ---------------------------------------------------------------- 일정
# 경기 날 (KST). 검사 · 데모만 환경값으로 바꾼다.
DAYS = tuple(d.strip() for d in os.environ.get(
    "POKET_OLYMPICS_DAYS",
    "2026-11-16,2026-11-17,2026-11-18,2026-11-19,2026-11-20,2026-11-23,2026-11-24").split(",") if d.strip())
OPEN = os.environ.get("POKET_OLYMPICS_OPEN", "2026-11-15")      # 첫 경기 날 신청을 받기 시작하는 날 (00:00 KST)
AT = os.environ.get("POKET_OLYMPICS_AT", "14:00")               # 경기 시각 (KST)
ARCHIVE_DAYS = 7            # 마지막 경기 뒤 이만큼은 올림픽 창 · 다시 보기를 열어 둔다

# 종목 (경기 순서). stats = 보는 능력 (atkspa = 공격 · 특공 중 높은 쪽), kg0 = 알맞은 몸무게, width = 체형 폭(log10),
# base = 점수 1.00 의 기록, low = 낮을수록 좋은 기록(시간), tries = 시기 수 (3 이면 최고 기록)
EVENTS = (
    {"key": "sprint", "kr": "100m 달리기", "short": "100m", "stats": ("spe",), "statKr": "스피드",
     "kg0": 30, "width": 1.5, "types": ("ELECTRIC", "FIRE"),
     "abil": ("RUNAWAY", "QUICKFEET", "SPEEDBOOST", "UNBURDEN"), "dislike": (),
     "base": 13.0, "low": True, "tries": 1},
    # 봅슬레이 (11/07, 수영 대신): 한 대씩 내려오는 단독 주행 (TRIALS). 무거울수록 · 밀기 출발(공격 · 스피드)
    {"key": "bobsled", "kr": "봅슬레이", "short": "봅슬레이", "stats": ("atk", "spe"), "statKr": "공격 · 스피드",
     "kg0": 150, "width": 1.6, "types": ("STEEL", "ICE"),
     "abil": ("HEAVYMETAL", "SNOWCLOAK", "SOLIDROCK"), "dislike": (),
     "base": 50.0, "low": True, "tries": 1},
    {"key": "pole", "kr": "장대높이뛰기", "short": "장대", "stats": ("atk", "spe"), "statKr": "공격 · 스피드",
     "kg0": 10, "width": 1.2, "types": ("FIGHTING", "BUG"),
     "abil": ("LIMBER",), "dislike": (),
     "base": 5.0, "low": False, "tries": 3},
    # 양궁 (11/07, 역도 대신): 화살 세 발 점수의 합 (sum). 특기 = 고스트 · 악 (모크나이퍼), 눈 · 겨냥 특성
    {"key": "archery", "kr": "양궁", "short": "양궁", "stats": ("spa", "spd"), "statKr": "특공 · 특방",
     "kg0": 50, "width": 2.2, "types": ("GHOST", "DARK"),
     "abil": ("KEENEYE", "COMPOUNDEYES", "SNIPER", "LONGREACH"), "dislike": (),
     "base": 10.0, "low": False, "tries": 3, "sum": True},
    {"key": "discus", "kr": "원반던지기", "short": "원반", "stats": ("atkspa",), "statKr": "공격 · 특공 중 높은 쪽",
     "kg0": 60, "width": 1.4, "types": ("PSYCHIC", "GROUND"),
     "abil": ("HUSTLE", "STEELWORKER", "TECHNICIAN"), "dislike": (),
     "base": 55.0, "low": False, "tries": 3},
    {"key": "ski", "kr": "스키점프", "short": "스키점프", "stats": ("spe", "spd"), "statKr": "스피드 · 특방",
     "kg0": 15, "width": 1.3, "types": ("ICE", "FLYING"),
     "abil": ("LEVITATE", "SLUSHRUSH", "ICEBODY"), "dislike": (),
     "base": 110.0, "low": False, "tries": 3},
    {"key": "marathon", "kr": "마라톤", "short": "마라톤", "stats": ("hp", "spd"), "statKr": "체력 · 특방",
     "kg0": 30, "width": 1.5, "types": ("NORMAL", "GRASS"),
     "abil": ("REGENERATOR", "NATURALCURE", "STAMINA", "THICKFAT"), "dislike": (),
     "base": 7800.0, "low": True, "tries": 1},
)
EV = dict((e["key"], e) for e in EVENTS)
KEYS = tuple(e["key"] for e in EVENTS)
RACES = ("sprint", "marathon")                  # 8마리가 같이 달린다
TRIALS = ("bobsled",)                           # 한 마리씩 한 번 (시간) - 나머지는 차례로 세 번씩 시기

# 하루 한 종목 (11/08 사용자 "하루 한 종목", "예선~결승을 하루에 다"): 경기 날 차례 = 종목 차례.
EVENT_DAY = dict(zip(KEYS, DAYS))
DAY_EVENT = dict((d, e) for e, d in EVENT_DAY.items())
# 그날 중계가 끝나는 때(14:00 부터 초)를 아직 모를 때 쓰는 값. 실제 값은 그날 경기를 치를 때 서버가 정한다
# (라운드 수에 따라 다르다 - common/olympics_rounds.program). 넉넉히 잡아 '중계 중' 을 일찍 끝내지 않는다.
DEFAULT_END = 900

# 오늘의 응원 타입 (종목마다). 짝 일곱 개는 1차 그대로이고, **그날 종목의 특기 타입과 겹치지 않게** 차례만 맞췄다
# (11/08 검토 - 예전 차례면 100m 날 응원 '불꽃' 이 100m 특기 '불꽃' 과 겹쳐 불꽃 타입만 +10%).
# 특기 종목이 없는 독 · 고스트 · 드래곤 · 악 · 페어리가 한 번씩 나온다.
CHEER = {"sprint": ("FAIRY", "WATER"), "bobsled": ("GHOST", "FIRE"), "pole": ("DRAGON", "ELECTRIC"),
         "archery": ("POISON", "GRASS"), "discus": ("DARK", "ICE"), "ski": ("NORMAL", "ROCK"),
         "marathon": ("FIGHTING", "PSYCHIC")}

# ---------------------------------------------------------------- 공식 숫자
APT, BODY, TYPE_B, ABIL_B, DISLIKE, CHEER_B = 0.05, 0.04, 0.05, 0.03, 0.03, 0.05
FATIGUE_MAX, FATIGUE_AT = 0.05, 0.05
SLIP = 0.08
LUCK_CAP = 0.20
TACTICS = {"safe": {"kr": "안정", "plus": 0.0, "sd": 0.06, "slip": 0.05},
           "bold": {"kr": "승부수", "plus": 0.03, "sd": 0.11, "slip": 0.15}}
HEAT = 8                    # 한 조

# 메달 · 입상 (최종 순위)
MEDALS = ((1, "gold", "금메달"), (2, "silver", "은메달"), (3, "bronze", "동메달"))
# 1~3위 상: 목에 거는 메달 꾸미기(common/deco.py) + 그 종목 칭호. 칭호는 '금메달' 같은 이름이 아니라 종목 특징에 맞는
# 이름 (사용자 11/08 - '스키점프는 영화 Butterfly 같은 것'). 종목마다 하나, 1~3위가 같이 받는다
MEDAL_DECO = {1: "medal_gold", 2: "medal_silver", 3: "medal_bronze"}
TITLE = {
    "sprint": "라이트닝 볼트",        # 우사인 볼트의 별명
    "bobsled": "쿨 러닝",             # 자메이카 봅슬레이 팀 영화
    "pole": "날개 없는 새",           # 장대로 나는 '인간새' 부브카
    "archery": "신궁",                # 한국 양궁 선수들을 부르는 말
    "discus": "원반 던지는 사람",     # 미론의 조각상
    "ski": "Butterfly",               # 영화 '국가대표' 의 노래
    "marathon": "백만불짜리 다리",    # 영화 '말아톤' 의 대사
}
FINAL_TO = 8                # 4~8위 = 결선 진출
SPECIES_MIN = 3             # 종족 1위 리본은 그 종 출전자가 이만큼 이상일 때


# ---------------------------------------------------------------- 시간
def _date(s):
    return datetime.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))


def _hm():
    h, m = AT.split(":")
    return int(h), int(m)


def start_at(day):
    """그 경기 날의 경기 시각 (UTC aware)."""
    h, m = _hm()
    d = _date(day)
    return datetime.datetime(d.year, d.month, d.day, h, m, tzinfo=KST).astimezone(UTC)


def end_at(day, end=None):
    """그 경기 날 중계가 끝나는 때. end = 14:00 부터 초 (서버가 그날 경기를 치를 때 정한 값), 모르면 DEFAULT_END."""
    return start_at(day) + datetime.timedelta(seconds=int(end if end is not None else DEFAULT_END))


def open_at(day=None):
    """신청을 받기 시작하는 때 = OPEN 00:00 KST. 일곱 종목 모두 같다 (하루 한 종목 - 11/08)."""
    d = _date(OPEN)
    return datetime.datetime(d.year, d.month, d.day, tzinfo=KST).astimezone(UTC)


def day_of(event):
    """그 종목의 경기 날."""
    return EVENT_DAY.get(event)


def event_of(day):
    """그 경기 날의 종목 (경기 날이 아니면 None)."""
    return DAY_EVENT.get(day)


def _aware(t):
    if t is None:
        return datetime.datetime.now(UTC)
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _end(day, ends):
    return end_at(day, (ends or {}).get(day))


def entry_open(event, now=None):
    """그 종목 신청을 지금 받나 - OPEN 00:00 부터 그 종목 날 14:00 전까지 (바꾸기 · 취소도 같다)."""
    day = day_of(event)
    if not day:
        return False
    now = _aware(now)
    return open_at() <= now < start_at(day)


def open_events(now=None):
    """지금 신청을 받는 종목들 (차례대로)."""
    return [e for e in KEYS if entry_open(e, now)]


def live_day(now=None, ends=None):
    """지금 중계 중인 경기 날 (14:00 ~ 그날 end). ends = {날: 14:00 부터 초} (모르면 DEFAULT_END)."""
    now = _aware(now)
    for d in DAYS:
        if start_at(d) <= now < _end(d, ends):
            return d
    return None


def ran_days(now=None):
    """경기 시각이 지난 경기 날들 (차례대로)."""
    now = _aware(now)
    return [d for d in DAYS if start_at(d) <= now]


def next_day(now=None, ends=None):
    """아직 끝나지 않은 첫 경기 날 (신청 중이거나 중계 중). 다 끝났으면 None."""
    now = _aware(now)
    for d in DAYS:
        if now < _end(d, ends):
            return d
    return None


def phase(now=None, ends=None):
    """before(신청 전) · entry(신청 중) · live(중계 중) · done(다 끝남, 기록실) · closed(올림픽 탭 기록도 닫음)."""
    now = _aware(now)
    if not DAYS or now < open_at():
        return "before"
    if live_day(now, ends):
        return "live"
    if open_events(now):
        return "entry"
    if now >= _end(DAYS[-1], ends) + datetime.timedelta(days=ARCHIVE_DAYS):
        return "closed"
    return "done"


def finished(now=None, ends=None):
    """마지막 경기 날 중계가 끝났나."""
    return bool(DAYS) and _aware(now) >= _end(DAYS[-1], ends)


def at_text(at=None):
    """경기 시각을 말로: '14:00' -> '오후 2시', '09:30' -> '오전 9시 30분'."""
    h, m = (int(x) for x in (at or AT).split(":"))
    ap = "오전" if h < 12 else "오후"
    hh = h if h <= 12 else h - 12
    return "%s %d시%s" % (ap, hh or 12, " %d분" % m if m else "")


def day_no(day):
    return DAYS.index(day) + 1 if day in DAYS else 0


def cheer_of(day):
    """그날의 응원 타입 둘 (그날 종목의 것)."""
    return CHEER.get(event_of(day), ())


def prev_day(day):
    i = DAYS.index(day) if day in DAYS else -1
    return DAYS[i - 1] if i > 0 else None


# ---------------------------------------------------------------- 공식
def _combo(sp, stats):
    b = sp.get("base") or {}
    if stats == ("atkspa",):
        return max(b.get("atk", 0), b.get("spa", 0))
    return sum(b.get(k, 0) for k in stats) / float(len(stats))


def build_pct(species):
    """{종목: {종 internal: 백분위 0~1}}. 도감 전체(species 목록)로 한 번 만든다. 같은 값은 가운데 순위."""
    out = {}
    for e in EVENTS:
        vals = sorted(_combo(s, e["stats"]) for s in species)
        n = float(len(vals)) or 1.0
        out[e["key"]] = dict(
            (s["internal"], (bisect.bisect_left(vals, _combo(s, e["stats"]))
                             + bisect.bisect_right(vals, _combo(s, e["stats"]))) / 2.0 / n)
            for s in species)
    return out


def body_mod(event, kg):
    e = EV[event]
    d = abs(math.log10(max(float(kg or 0.1), 0.1)) - math.log10(e["kg0"])) / e["width"]
    return BODY - 2 * BODY * min(1.0, d)


def fatigue_map(counts):
    """{종: 깎는 몫}. counts = 그 종목 신청자의 {종: 수}."""
    tot = float(sum(counts.values()))
    if tot <= 0:
        return {}
    return dict((k, round(FATIGUE_MAX * min(1.0, (c / tot) / FATIGUE_AT), 4)) for k, c in counts.items() if c)


def mods(event, sp, ability, pct, cheer=(), fatigue=0.0):
    """기록에 더하는 것들 {항목: 몫}. 노력치 · 개체값 · 레벨 · 성격 · 도구 · 이로치는 받지도 않는다."""
    e = EV[event]
    types = set(sp.get("types") or ())
    p = (pct.get(event) or {}).get(sp.get("internal"), 0.5)
    out = {"apt": APT * (p - 0.5) * 2, "body": body_mod(event, sp.get("kg"))}
    if types & set(e["types"]):
        out["type"] = TYPE_B
    if ability and ability in e["abil"]:
        out["abil"] = ABIL_B
    if types & set(e["dislike"]):
        out["dislike"] = -DISLIKE
    if types & set(cheer or ()):
        out["cheer"] = CHEER_B
    if fatigue:
        out["fatigue"] = -abs(float(fatigue))
    return out


def expect(m):
    """기대 점수 (작전 · 운 빼고)."""
    return 1.0 + sum(m.values())


def tries(event, m, tactic, rng):
    """시기들. [{'r': 점수 또는 None(파울), 'slip': 실수했나, 'at': 실수한 때(달리기형, 0~1)}]."""
    e = EV[event]
    t = TACTICS.get(tactic) or TACTICS["safe"]
    base = expect(m) + t["plus"]
    out = []
    for _ in range(e["tries"]):
        luck = max(-LUCK_CAP, min(LUCK_CAP, rng.gauss(0, t["sd"])))
        slip = rng.random() < t["slip"]
        at = round(rng.uniform(0.25, 0.8), 3)
        if slip and e["tries"] > 1:
            out.append({"r": None, "slip": True})           # 파울
        elif slip:
            out.append({"r": base - SLIP + luck, "slip": True, "at": at})
        else:
            out.append({"r": base + luck, "slip": False})
    return out


# 양궁 화살 하나: 점수(r)가 ARROW_TOP 이상이면 10점, 그 아래로 ARROW_RING 만큼 내려갈 때마다 한 링씩 (1점까지).
# ARROW_X 이상이면 10점 가운데의 X (같은 합이면 X 가 많은 쪽이 앞 - 기록 = 합 + X 수 x 0.01).
ARROW_TOP, ARROW_RING, ARROW_X = 1.12, 0.05, 1.15


def arrow_points(r):
    """화살 하나의 점수 (1~10)."""
    return max(1, min(10, 10 - int(math.floor(max(0.0, ARROW_TOP - float(r)) / ARROW_RING))))


def archery_total(tries):
    """양궁 기록 = 세 발 점수 합 + X 수 x 0.01 (빗나감 M 은 0점)."""
    return round(sum((t.get("v") or 0) for t in tries) + 0.01 * sum(1 for t in tries if t.get("x")), 2)


def record_of(event, r):
    """점수 -> 기록 (반올림까지 마친 수). None 이면 None. 양궁은 화살 하나의 점수."""
    if r is None:
        return None
    e = EV[event]
    r = max(0.3, float(r))
    if event == "marathon":
        return int(round(e["base"] / r))
    if e["low"]:
        return round(e["base"] / r, 2)
    if event == "archery":
        return arrow_points(r)
    if event == "ski":
        return round(e["base"] * r * 2) / 2.0
    return round(e["base"] * r, 2)


def best_of(event, recs):
    vals = [x for x in recs if x is not None]
    if not vals:
        return None
    return min(vals) if EV[event]["low"] else max(vals)


def rank_key(event, rec):
    """작을수록 앞. 기록 없음(다 파울)은 맨 뒤."""
    if rec is None:
        return float("inf")
    return rec if EV[event]["low"] else -rec


def better(event, a, b):
    """a 가 b 보다 좋은 기록인가 (같으면 아니다)."""
    return rank_key(event, a) < rank_key(event, b)


def text(event, rec):
    """기록 글."""
    if rec is None:
        return "기록 없음"
    if event == "marathon":
        s = int(rec)
        return "%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60)
    if EV[event]["low"]:
        return "%.2f초" % rec
    if event == "archery":
        pts = int(rec + 1e-6)
        x = int(round((rec - pts) * 100))
        return "%d점" % pts + (" (X %d)" % x if x else "")
    if event == "ski":
        return "%.1fm" % rec
    return "%.2fm" % rec


def play(event, sp, ability, tactic, pct, cheer=(), fatigue=0.0, seed=None):
    """한 번 경기한다. {'record', 'tries': [{'v': 기록 또는 None, 'slip', 'at'}], 'mods', 'seed'}."""
    if seed is None:
        seed = random.randrange(1 << 30)
    rng = random.Random(seed)
    m = mods(event, sp, ability, pct, cheer, fatigue)
    ts = tries(event, m, tactic, rng)
    out_t = []
    for t in ts:
        row = {"v": record_of(event, t["r"]), "slip": bool(t["slip"])}
        if "at" in t:
            row["at"] = t["at"]
        if event == "archery" and t["r"] is not None and t["r"] >= ARROW_X:
            row["x"] = True                     # 10점 가운데 X
        out_t.append(row)
    rec = archery_total(out_t) if EV[event].get("sum") else best_of(event, [t["v"] for t in out_t])
    return {"record": rec, "tries": out_t,
            "mods": dict((k, round(v, 4)) for k, v in m.items()), "seed": seed}


# ---------------------------------------------------------------- 고르는 창의 알기 쉬운 표시
def stars(m):
    """기대 점수(작전 · 운 빼고)를 별 1~5 로."""
    s = sum(m.values())
    for n, lim in ((1, -0.04), (2, 0.0), (3, 0.04), (4, 0.08)):
        if s < lim:
            return n
    return 5


def hints(event, sp, m, type_name=None, ability_name=None):
    """숫자 대신 붙이는 짧은 말들. 모두에게 같은 정보를 보여 준다 (계산 잘하는 사람만 유리하지 않게)."""
    e = EV[event]
    tn = type_name or (lambda t: t)
    out = []
    b = m.get("body", 0.0)
    heavy = float(sp.get("kg") or 0) > e["kg0"]
    if b >= 0.03:
        out.append("체형 딱 맞음")
    elif b < -0.02:
        out.append("너무 무거움" if heavy else "너무 가벼움")
    elif b < 0.01:
        out.append("조금 무거움" if heavy else "조금 가벼움")
    a = m.get("apt", 0.0)
    if a >= APT * 0.5:
        out.append("%s 좋음" % e["statKr"])
    elif a <= -APT * 0.5:
        out.append("%s 부족" % e["statKr"])
    for t in sp.get("types") or ():
        if t in e["types"]:
            out.append("%s 특기" % tn(t))
    if "abil" in m:
        out.append("특성 %s" % (ability_name or "맞음"))
    if "dislike" in m:
        out.append("물 싫어함")
    if "cheer" in m:
        out.append("오늘 응원 타입!")
    if "fatigue" in m:
        out.append("지침 −%d%%" % int(round(-m["fatigue"] * 100)))
    return out


# ---------------------------------------------------------------- 조 · 중계 각본
def heats(ids, seed):
    """신청 번호들을 섞어 조로 나눈다. [[번호, ...], ...] - 조 크기 차이는 1 이하."""
    ids = list(ids)
    random.Random(seed).shuffle(ids)
    n = max(1, int(math.ceil(len(ids) / float(HEAT))))
    out = [[] for _ in range(n)]
    for i, x in enumerate(ids):
        out[i % n].append(x)
    return [h for h in out if h]


def race_curve(seed, event, slip_at=None, steps=8):
    """달리기형의 '시간 몫 -> 거리 몫' 점들 [(t, d), ...]. 처음 (0,0) 끝 (1,1), d 는 늘기만 한다.

    같은 씨앗이면 앱 어디서든 같은 곡선이다 (다시 보기 · 같은 조의 다른 사람 화면). 실수했으면 그 때 잠깐 멈춘다.
    """
    rng = random.Random((int(seed) * 7919 + 17) & 0x7fffffff)
    spread = 0.35 if event == "marathon" else 0.18
    w = [max(0.25, 1.0 + rng.uniform(-spread, spread)) for _ in range(steps)]
    if event != "marathon":
        w[0] *= 0.7                     # 출발은 천천히
    seg = [(1.0 / steps, x) for x in w]  # (걸린 시간 몫, 간 거리 무게)
    if slip_at is not None:
        k = min(steps - 1, int(slip_at * steps))
        seg.insert(k + 1, (0.07, 0.0))  # 넘어져 멈춘 동안
    tt = sum(s[0] for s in seg)
    dd = sum(s[1] for s in seg) or 1.0
    pts, t, d = [(0.0, 0.0)], 0.0, 0.0
    for dt, dw in seg:
        t += dt / tt
        d += dw / dd
        pts.append((round(t, 4), round(d, 4)))
    pts[-1] = (1.0, 1.0)
    return pts


def at_curve(pts, t):
    """곡선에서 시간 몫 t 의 거리 몫."""
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    for (t0, d0), (t1, d1) in zip(pts, pts[1:]):
        if t <= t1:
            if t1 <= t0:
                return d1
            return d0 + (d1 - d0) * (t - t0) / (t1 - t0)
    return 1.0
