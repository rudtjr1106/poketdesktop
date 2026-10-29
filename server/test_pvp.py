# -*- coding: utf-8 -*-
"""유저 배틀 코어 검사.

    python server/test_pvp.py [http://127.0.0.1:8788]

매칭(대기열/도전장)은 아직 없다. 여기서는 서버 안에서 run_match 를 직접
불러 '판이 제대로 끝나고 뒤처리가 맞는가' 만 본다. 그래서 이 검사는
**서버와 같은 기계에서** 돌려야 한다 - 컨테이너 안에서 돌린다.

돈이 오가고 점수가 움직이는 곳이라 숫자를 하나하나 맞춰 본다.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import db, items, pvp                        # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(name, mons=3, level=30, rank=False):
    """계정 하나와 바탕화면에 데리고 다니는 포켓몬 몇 마리.

    rank=True 면 랭크전 조건(Lv.50 이상 6마리)을 채운다 - 같은 종·전설·환상은 한 팀에 한 마리라
    겹치지 않는 보통 종으로 여섯 마리 (can_start · can_fight 를 지나가려면 이게 있어야 한다)."""
    import random
    import zlib
    from app import deps
    d = deps.dex()
    # hash(name) 을 쓰면 안 된다. 문자열 hash 는 프로세스마다 달라져서
    # (PYTHONHASHSEED) 파티가 매번 바뀌고, 그러면 아래 '하루 상한' 검사가
    # a 가 몇 판 이기느냐에 따라 세 번에 한 번쯤 헛되이 빨갛게 된다
    # (1.1.1 CI 에서 걸렸다: 7승 = 3500원). crc32 는 언제나 같은 값이다.
    rng = random.Random(zlib.crc32(name.encode("utf-8")))
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,?,?,'')",
        (name, b"x", b"x", pvp._iso(), pvp._iso()))
    uid = cur.lastrowid
    rolls = []
    if rank:
        bad, seen = set(pvp.restricted_species()), set()
        while len(rolls) < 6:
            m = d.roll_wild(50, 50, rng)
            if m["species"] not in bad and m["species"] not in seen:
                seen.add(m["species"])
                rolls.append(m)
    for i in range(len(rolls) if rank else mons):
        m = rolls[i] if rank else d.roll_wild(level, level, rng)
        db.run(
            "INSERT INTO pokemon (user_id, species, level, exp, nature, ability,"
            " hidden_ability, gender, shiny, happiness, ivs, evs, moves,"
            " on_desktop, slot, met_level, caught_at)"
            " VALUES (?,?,?,?,?,?,0,?,0,?,?,?,?,1,?,?,?)",
            (uid, m["species"], m["level"], m.get("exp", 0), m["nature"],
             m.get("ability"), m.get("gender", "M"), m.get("happiness", 70),
             json.dumps(m["ivs"]), json.dumps(m.get("evs", {})),
             json.dumps(m["moves"]), i, m["level"], pvp._iso()))
    return uid


def money(uid):
    return items.money(uid)


STAT_COLS = ("rating", "games", "wins", "losses", "draws", "streak", "best", "ranked",
             "rp", "peak_rp", "win_day")


def _stat(uid):
    """점수 쪽 칸만 (돈·하루 판수는 뺀다) - 연습판이 이 중 하나라도 바꾸면 안 된다."""
    r = pvp._rating_row(uid)
    return dict((k, r[k]) for k in STAT_COLS)


def practice_checks():
    """연습판: 하루 20판 뒤의 랜덤 배틀. 점수는 양쪽 다 그대로, 이기면 100원 (하루 상한 안)."""
    # 거는 쪽을 훨씬 세게 - 이긴 판의 상금을 봐야 한다 (랭크는 Lv.50 으로 자르므로 받는 쪽을 낮춘다)
    a = mkuser("zz_pr_a", rank=True)
    b = mkuser("zz_pr_b", 1, 3)
    c = mkuser("zz_pr_c", 1, 3)
    # 점수판 한 판으로 점수 줄을 만들어 둔다 (RP·연승·하루 첫 승이 0 이 아닌 상태에서 보려고)
    pvp.run_match(a, c, kind="random", seed=4242)
    db.run("UPDATE rank_stat SET earned=0 WHERE user_id=?", (a,))
    chk("점수판은 점수판 (20판 전)", not pvp.is_practice(a))
    for _ in range(pvp.DAILY_BATTLES - 1):
        pvp.note_fight(a, "random")
    chk("19판까지는 아직 점수판", not pvp.is_practice(a))
    pvp.note_fight(a, "random")
    chk("20판을 쓰면 다음 판은 연습판", pvp.is_practice(a))
    before_a, before_b = _stat(a), _stat(b)
    m0 = money(a)
    normal_keys = set(pvp.run_match(a, c, kind="random", seed=1, practice=False)["a"])
    # (위 한 판은 응답 모양을 견주려고 일부러 점수판으로 친 것 - 점수를 되돌려 둔다)
    db.run("UPDATE rank_stat SET rating=?, games=?, wins=?, losses=?, draws=?, streak=?, best=?,"
           " ranked=?, rp=?, peak_rp=?, win_day=?, earned=0 WHERE user_id=?",
           tuple(before_a[k] for k in STAT_COLS) + (a,))
    m0 = money(a)

    win = None
    for seed in range(30):
        r = pvp.run_match(a, b, kind="random", seed=7000 + seed)
        if r["a"]["result"] == "win":
            win = r
            break
    if win is None:
        # 서른 판을 다 못 이겼다 (팀을 뽑는 난수가 바뀌었을 때). 아래 상금·전적 검사는 이긴 판이 있어야 해서
        # TypeError 로 멈추지 말고 FAIL 하나로 남기고 넘어간다 - 쿨타임·기억·정리 검사는 그대로 돈다.
        chk("연습판으로 이긴 판을 찾았다 (시드 30개)", False, "30판 다 못 이김 - 상금·전적 검사 건너뜀")
    else:
        _practice_win_checks(a, b, win, m0, normal_keys, before_a, before_b)

    # 옛 앱 보호: 연습판은 새 앱이 알릴 때만 (POST /api/pvp/random 의 practice=1 -> practice_ok)
    chk("옛 앱(표시 없음)은 20판에서 예전처럼 막힌다", "20판까지" in (pvp.can_start(a, "random") or ""),
        pvp.can_start(a, "random"))
    d = mkuser("zz_pr_d", rank=True)
    chk("  상대를 지목해도 (can_fight) 막힌다", "20판까지" in (pvp.can_fight(a, d, "random") or ""),
        pvp.can_fight(a, d, "random"))
    why = pvp.can_start(a, "random", practice_ok=True)
    chk("  새 앱(practice_ok)은 받는다 (랜덤 쿨타임만 남을 수 있다)", why is None or "초 뒤" in why, why)
    chk("  20판 전에는 표시가 없어도 걸 수 있다 (옛 앱의 점수판)", pvp.can_start(d, "random") is None,
        pvp.can_start(d, "random"))

    # 쿨타임은 그대로: 같은 상대 30분 · 랜덤 쿨타임 (받는 쪽도 랭크전 조건을 채워야 그 검사까지 간다)
    why = pvp.can_fight(a, d, "random", practice_ok=True)
    chk("  (쿨타임 보기 전) 처음 보는 상대는 막히지 않는다 (랜덤 쿨타임만 남을 수 있다)",
        why is None or "초 뒤" in why, why)
    rd = pvp.run_match(a, d, kind="random", seed=31)
    chk("  연습판", rd["practice"] is True and _stat(a) == before_a, rd.get("practice"))
    why = pvp.can_fight(a, d, "random", practice_ok=True) or ""
    chk("같은 상대 30분 쿨타임은 그대로", "분에 한 번" in why or "초 뒤" in why, why)
    pvp.config.RANDOM_COOLDOWN_SEC, keep = 0, pvp.config.RANDOM_COOLDOWN_SEC
    try:
        why = pvp.can_fight(a, d, "random", practice_ok=True) or ""
        chk("  (랜덤 쿨타임을 끄고 보면) 30분 쪽에 걸린다", "분에 한 번" in why, why)
    finally:
        pvp.config.RANDOM_COOLDOWN_SEC = keep
    if int(pvp.config.RANDOM_COOLDOWN_SEC) > 0:
        why = pvp.can_start(a, "random", practice_ok=True) or ""
        chk("랜덤 쿨타임도 연습판에 걸린다", pvp.random_cooldown_left(a) > 0 and "초 뒤" in why, why)

    # 상대 고르기 기억: 3시간 건너뛰기 · 하루 감점은 점수판만 본다. 30분 쿨타임은 연습판도 센다.
    met = pvp._last_met(a, pvp.FRESH_WINDOW_MIN, practice=False)
    chk("하루 감점(_last_met)은 연습판 상대를 안 본다", c in met and b not in met and d not in met,
        (sorted(met), b, c, d))
    skip3 = pvp._recent_foes(a, pvp.RANDOM_REPEAT_MIN, practice=False)
    chk("  3시간 건너뛰기도 점수판 상대만", c in skip3 and b not in skip3 and d not in skip3, sorted(skip3))
    near = pvp._recent_foes(a)
    chk("  같은 상대 30분 쿨타임은 연습판 상대도 센다", b in near and d in near, sorted(near))

    # 하루 상한(6000원)은 점수판과 같이 센다
    db.run("UPDATE rank_stat SET earned_day=?, earned=? WHERE user_id=?",
           (pvp._today(), pvp.DAILY_CAP - 30, a))
    m1 = money(a)
    got = None
    for seed in range(30):
        r = pvp.run_match(a, b, kind="random", seed=8000 + seed)
        if r["a"]["result"] == "win":
            got = r
            break
    chk("하루 상한에 걸리면 깎아서 준다 (남은 30원)", got and got["a"]["reward"] == 30
        and money(a) == m1 + 30, got and got["a"]["reward"])
    chk("  상한까지 찼다", pvp.summary(a)["earnedToday"] == pvp.DAILY_CAP, pvp.summary(a)["earnedToday"])
    chk("  그래도 점수는 그대로", _stat(a) == before_a, _stat(a))
    fresh_practice = r["matchId"]           # 방금 친 연습판 - 아래 정리에서 남아야 한다
    chk("practice 를 안 넘기면 하루 판수로 정한다 (20판 전은 점수판)",
        pvp.run_match(c, b, kind="random", seed=5)["practice"] is False)
    chk("친구 배틀은 연습판이 아니다", pvp.run_match(a, b, kind="friend", seed=6)["practice"] is False)

    # 프로필 최근 전적에는 연습판을 안 싣는다 (social.profile 의 recent)
    from app import social
    recs = pvp.records(a, 100)
    n_score = sum(1 for x in recs if not x["practice"])
    recent = social.profile(a, a)["recent"]
    chk("프로필 최근 전적에서 연습판은 빠진다", n_score < len(recs) and len(recent) == min(10, n_score),
        (len(recent), n_score, len(recs)))

    # 저장 공간: 연습판 로그는 봤든 안 봤든 이틀이면 치운다. 전적 줄은 남고 '다시 보기' 만 꺼진다.
    old_t = pvp._iso(pvp._now() - __import__("datetime").timedelta(days=pvp.PRACTICE_KEEP_DAYS + 1))
    pm = rd["matchId"]
    db.run("UPDATE pvp_match SET created_at=?, a_seen=0, b_seen=0 WHERE id=?", (old_t, pm))
    scored = [x["matchId"] for x in recs if not x["practice"] and x["kind"] == "random" and x["matchId"]]
    db.run("UPDATE pvp_match SET created_at=?, b_seen=0 WHERE id=?", (old_t, scored[-1]))
    chk("  (정리 전) 연습판 로그가 연습판으로 남아 있다",
        (db.q1("SELECT practice FROM pvp_match WHERE id=?", (pm,)) or {"practice": 0})["practice"] == 1)
    pvp.prune()
    gone = db.q1("SELECT 1 x FROM pvp_match WHERE id=?", (pm,)) is None
    chk("이틀 지난 연습판 로그는 안 봤어도 지운다", gone)
    chk("  전적 줄은 양쪽 다 남는다",
        db.q1("SELECT COUNT(*) n FROM battle_record WHERE match_id=?", (pm,))["n"] == 2)
    row = [x for x in pvp.records(a, 100) if x["matchId"] == pm]
    chk("  전적 화면은 '다시 보기' 를 끈다 (canReplay)", len(row) == 1 and row[0]["canReplay"] is False, row)
    chk("  다시보기를 불러도 없다", pvp.match_view(a, pm) is None)
    chk("  갓 친 연습판 로그는 남는다",
        db.q1("SELECT 1 x FROM pvp_match WHERE id=?", (fresh_practice,)) is not None)
    chk("  같은 날짜의 점수판 로그는 그대로 (14일 · 둘 다 봐야)",
        db.q1("SELECT 1 x FROM pvp_match WHERE id=?", (scored[-1],)) is not None)


def _practice_win_checks(a, b, win, m0, normal_keys, before_a, before_b):
    """연습판으로 이긴 한 판의 상금·점수·전적·다시보기."""
    chk("연습판으로 쳤다", win["practice"] is True
        and win["a"]["practice"] is True and win["b"]["practice"] is True, win.get("practice"))
    chk("  이기면 100원", win["a"]["reward"] == pvp.PRACTICE_REWARD["win"] == 100, win["a"]["reward"])
    chk("  실제 잔액에도", money(a) == m0 + 100, (m0, money(a)))
    chk("  걸려온 쪽은 0원", win["b"]["reward"] == 0 and money(b) == 0, (win["b"]["reward"], money(b)))
    chk("  점수 변화 0 (RP·숨은 점수)", win["a"]["rpDelta"] == 0 and win["a"]["delta"] == 0
        and win["b"]["rpDelta"] == 0 and win["b"]["delta"] == 0, (win["a"], win["b"]))
    chk("  응답 모양은 점수판과 같다 (옛 앱)", normal_keys <= set(win["a"]), normal_keys - set(win["a"]))
    chk("  거는 쪽 점수 기록이 하나도 안 바뀐다 (RP·MMR·연승·배치·판수·하루 첫 승)",
        _stat(a) == before_a, (before_a, _stat(a)))
    chk("  걸려온 쪽도 그대로", _stat(b) == before_b, (before_b, _stat(b)))
    chk("  하루 상금에는 같이 센다", pvp.summary(a)["earnedToday"] == 100, pvp.summary(a)["earnedToday"])
    chk("  순위표에도 안 오른다 (배치 1판 그대로)", not any(x["name"] == "zz_pr_a" for x in pvp.ranking(100)))

    rec = [x for x in pvp.records(a, 100) if x["matchId"] == win["matchId"]]
    chk("전적에는 남는다 - 연습으로", len(rec) == 1 and rec[0]["practice"] is True
        and rec[0]["rpDelta"] == 0 and rec[0]["reward"] == 100, rec)
    recb = [x for x in pvp.records(b, 100) if x["matchId"] == win["matchId"]]
    chk("  걸려온 쪽 전적에도 연습으로", len(recb) == 1 and recb[0]["practice"] is True, recb)
    old = [x for x in pvp.records(a, 100) if x["foe"] == "zz_pr_c"]
    chk("  점수판 전적은 연습이 아니다", old and all(x["practice"] is False for x in old), old)
    v = pvp.match_view(a, win["matchId"])
    chk("다시보기에 연습판 표시 (양쪽)", v["practice"] is True and v["rpDelta"] == 0
        and pvp.match_view(b, win["matchId"])["practice"] is True, v.get("practice"))
    if old:
        vo = pvp.match_view(a, old[0]["matchId"])
        chk("  점수판 다시보기는 아니다", vo["practice"] is False)
        chk("  대전 로그에도 표시 (pvp_match.practice - 정리가 이것으로 가린다)",
            db.q1("SELECT practice FROM pvp_match WHERE id=?", (win["matchId"],))["practice"] == 1
            and db.q1("SELECT practice FROM pvp_match WHERE id=?", (old[0]["matchId"],))["practice"] == 0)


def war_ai_checks():
    """시즌 5 (버전 2): 랜덤(랭크) 배틀 · 연습판만 양쪽 다 길드전 AI (PB.simulate 의 war_ai). 시즌 4 는 그대로.

    season.rules_v5() 를 **부를 때마다** 보는지까지 본다 - SEASON 을 바꾸면 바로 따라와야 한다.
    """
    from app import season
    a, b = mkuser("zz_s5_a", rank=True), mkuser("zz_s5_b", rank=True)
    real_sim, seen = pvp.PB.simulate, []

    def spy(*args, **kw):
        seen.append(kw.get("war_ai"))
        return real_sim(*args, **dict(kw, war_ai=False))      # 판은 가볍게 (무엇을 넘겼는지만 본다)
    old = season.SEASON
    pvp.PB.simulate = spy
    try:
        season.SEASON = 4
        pvp.run_match(a, b, kind="random", seed=41)
        pvp.run_match(a, b, kind="random", seed=42, practice=True)
        chk("시즌 4: 랜덤 배틀 · 연습판은 예전 AI (war_ai 거짓)", seen == [False, False], seen)
        del seen[:]
        season.SEASON = 5
        pvp.run_match(a, b, kind="random", seed=43)
        pvp.run_match(a, b, kind="random", seed=44, practice=True)
        pvp.run_match(a, b, kind="friend", seed=45)
        chk("시즌 5: 랜덤 배틀 · 연습판은 길드전 AI, 친구 배틀은 예전 그대로", seen == [True, True, False], seen)
        del seen[:]
        season.SEASON = 4
        pvp.run_match(a, b, kind="random", seed=46)
        chk("SEASON 을 되돌리면 바로 예전 AI (import 때 복사해 두지 않는다)", seen == [False], seen)
        # 진짜로 한 판 (시즌 5): 저장된 로그가 예전 꼴 그대로 풀리고, 남은 마릿수 · 판정이 그 로그와 맞는다
        pvp.PB.simulate = real_sim
        season.SEASON = 5
        r = pvp.run_match(a, b, kind="random", seed=47)
        row = db.q1("SELECT log, winner FROM pvp_match WHERE id=?", (r["matchId"],))
        ev = pvp.unpack(row["log"])
        chk("시즌 5 랭크 한 판: 로그가 teams 로 시작해 match 로 끝난다",
            ev and ev[0]["t"] == "teams" and ev[-1]["t"] == "match", (ev[:1], ev[-1:]))
        want = {"me": a, "foe": b, "draw": None}[ev[-1]["winner"]]
        chk("  저장된 승자가 로그의 승자와 같다", row["winner"] == want, (row["winner"], want))
        chk("  over 이벤트가 새지 않는다", not any(e.get("t") == "over" for e in ev))
    finally:
        pvp.PB.simulate = real_sim
        season.SEASON = old


def main():
    db.init()
    print("=== 준비 ===")
    # a 를 열 레벨 위로 둔다. 아래 '하루 상한' 검사는 a 가 25판 중 열두 판은
    # 이겨야 상한(6000원)에 닿는다. 같은 레벨이면 crc32 시드의 파티로는
    # 네 판밖에 못 이긴다. 다른 검사는 누가 이기든 통과하게 짜여 있다.
    a = mkuser("zz_pvp_a", 3, 40)
    b = mkuser("zz_pvp_b", 3, 30)
    chk("두 계정을 만들었다", a and b and a != b, (a, b))
    chk("돈은 0 에서 시작", money(a) == 0 and money(b) == 0,
        (money(a), money(b)))

    try:
        print("\n=== 한 판 ===")
        r = pvp.run_match(a, b, kind="random", seed=777)
        chk("판이 끝났다", r["matchId"] > 0, r)
        chk("승자가 둘 중 하나이거나 무승부",
            r["winner"] in (a, b, None), r["winner"])
        chk("결과가 서로 반대", {
            ("win", "lose"), ("lose", "win"), ("draw", "draw")
        }.__contains__((r["a"]["result"], r["b"]["result"])),
            (r["a"]["result"], r["b"]["result"]))

        print("\n=== 돈 — 건 쪽이 이겼을 때만 ===")
        pa, pb = r["a"]["reward"], r["b"]["reward"]
        # a 가 건 쪽이다. 이기면 500, 지면 0.
        want_a = 500 if r["a"]["result"] == "win" else 0
        chk("건 쪽은 이기면 500원, 지면 0원", pa == want_a, (r["a"]["result"], pa))
        # **걸려온 쪽은 한 푼도 없다.** 자는 사이에 돈이 들어오면
        # 아무것도 안 하는 편이 이득인 구간이 생긴다.
        chk("걸려온 쪽은 이기든 지든 0원", pb == 0, (r["b"]["result"], pb))
        chk("실제 잔액에 반영됐다", money(a) == pa and money(b) == 0,
            (money(a), pa, money(b)))

        print("\n=== 점수 — 건 쪽만 ===")
        chk("건 쪽 점수가 움직였다",
            r["a"]["delta"] != 0 or r["a"]["result"] == "draw", r["a"]["delta"])
        # 걸려온 쪽은 남이 건 것으로 등수가 오르내리면 안 된다.
        chk("걸려온 쪽은 점수가 안 움직인다", r["b"]["delta"] == 0, r["b"]["delta"])
        chk("걸려온 쪽 점수는 그대로",
            pvp.summary(b)["rating"] == pvp.BASE_RATING, pvp.summary(b))
        chk("걸려온 쪽은 판수도 안 는다", pvp.summary(b)["games"] == 0,
            pvp.summary(b)["games"])
        chk("걸려온 쪽은 승패도 안 는다",
            pvp.summary(b)["wins"] + pvp.summary(b)["losses"] == 0,
            pvp.summary(b))
        chk("started 로 구분된다",
            r["a"]["started"] is True and r["b"]["started"] is False,
            (r["a"]["started"], r["b"]["started"]))
        sa = pvp.summary(a)
        chk("배치가 남아 있다 (5판 중 1판)", sa["placementLeft"] == 4,
            sa["placementLeft"])
        chk("아직 랭킹에 안 오른다", not sa["ranked"], sa)
        chk("순위표가 비어 있다", pvp.ranking() == [], pvp.ranking())

        print("\n=== 다시보기 ===")
        va = pvp.match_view(a, r["matchId"])
        vb = pvp.match_view(b, r["matchId"])
        chk("양쪽 다 볼 수 있다", va and vb)
        chk("이벤트 수가 같다", len(va["events"]) == len(vb["events"]),
            (len(va["events"]), len(vb["events"])))
        chk("결과가 서로 반대로 보인다",
            {va["result"], vb["result"]} in ({"win", "lose"}, {"draw"}),
            (va["result"], vb["result"]))
        chk("상대 이름이 서로 바뀌어 보인다",
            va["foe"]["name"] == vb["me"]["name"], (va["foe"], vb["me"]))
        m1 = [e for e in va["events"] if e["t"] == "match"][0]
        m2 = [e for e in vb["events"] if e["t"] == "match"][0]
        chk("로그의 승자도 뒤집힌다",
            m2["winner"] == {"me": "foe", "foe": "me", "draw": "draw"}[m1["winner"]],
            (m1["winner"], m2["winner"]))
        c = mkuser("zz_pvp_c", 1, 5)
        chk("남의 대전은 못 본다", pvp.match_view(c, r["matchId"]) is None)

        print("\n=== 전적 ===")
        rec = pvp.records(a)
        chk("전적이 한 줄 남았다", len(rec) == 1, len(rec))
        chk("상대 이름이 남았다", rec[0]["foe"] == "zz_pvp_b", rec[0])
        chk("받은 돈이 남았다", rec[0]["reward"] == pa, rec[0])
        chk("내가 건 판으로 남는다", rec[0]["started"] is True, rec[0])
        # 점수엔 안 들어가도 **목록에는 남아야** 누가 걸어왔는지 볼 수 있다.
        recb = pvp.records(b)
        chk("걸려온 쪽도 목록에는 남는다", len(recb) == 1, len(recb))
        chk("걸려온 판으로 표시된다", recb[0]["started"] is False, recb[0])
        chk("걸려온 판은 상금 0 으로 남는다", recb[0]["reward"] == 0, recb[0])
        # 1.12.1: 로그가 남아 있는 판만 '다시 보기' (prune 이 로그를 치워도 전적은 남는다)
        chk("로그가 있으면 다시 볼 수 있다 (양쪽)", rec[0]["canReplay"] is True
            and recb[0]["canReplay"] is True, (rec[0].get("canReplay"), recb[0].get("canReplay")))
        saved = db.q1("SELECT * FROM pvp_match WHERE id=?", (r["matchId"],))
        db.run("DELETE FROM pvp_match WHERE id=?", (r["matchId"],))
        chk("  로그가 치워지면 못 본다 (전적은 그대로)", pvp.records(a)[0]["canReplay"] is False
            and len(pvp.records(a)) == 1)
        cols = list(saved.keys())
        db.run("INSERT INTO pvp_match (%s) VALUES (%s)" % (",".join(cols), ",".join("?" * len(cols))),
               tuple(saved[k] for k in cols))
        chk("  되돌려 두면 다시 볼 수 있다", pvp.records(a)[0]["canReplay"] is True)

        print("\n=== 배치 5판 ===")
        for i in range(4):
            pvp.run_match(a, b, kind="random", seed=100 + i)
        sa = pvp.summary(a)
        chk("5판을 채웠다", sa["games"] == 5, sa["games"])
        chk("랭킹에 올랐다", sa["ranked"], sa)
        board = pvp.ranking()
        # b 는 걸려오기만 했으니 한 판도 안 친 것으로 친다.
        chk("건 사람만 순위표에 오른다", [x["name"] for x in board] == ["zz_pvp_a"],
            board)
        chk("걸려온 쪽은 배치가 안 찬다", pvp.summary(b)["games"] == 0,
            pvp.summary(b)["games"])
        chk("시즌 번호가 실려 온다", pvp.summary(a)["season"] == pvp.SEASON,
            pvp.summary(a).get("season"))

        print("\n=== 하루 상한 ===")
        before = money(a)
        for i in range(20):
            pvp.run_match(a, b, kind="random", seed=500 + i)
        sa = pvp.summary(a)
        chk("하루 상한을 넘지 않는다", sa["earnedToday"] <= pvp.DAILY_CAP,
            sa["earnedToday"])
        chk("상한에 도달했다", sa["earnedToday"] == pvp.DAILY_CAP,
            sa["earnedToday"])
        gained = money(a) - before
        chk("상한 뒤로는 돈이 안 늘어난다",
            money(a) - before <= pvp.DAILY_CAP, gained)

        print("\n=== 친구 배틀 ===")
        d1 = mkuser("zz_pvp_d", 2, 30)
        e1 = mkuser("zz_pvp_e", 2, 30)
        fr = pvp.run_match(d1, e1, kind="friend", seed=900)
        chk("친구 배틀은 점수를 건드리지 않는다",
            fr["a"]["delta"] == 0 and fr["b"]["delta"] == 0,
            (fr["a"]["delta"], fr["b"]["delta"]))
        chk("친구 배틀도 건 쪽만, 이겼으면 절반인 250원",
            fr["a"]["reward"] == (250 if fr["a"]["result"] == "win" else 0),
            (fr["a"]["result"], fr["a"]["reward"]))
        chk("친구 배틀도 걸려온 쪽은 0원", fr["b"]["reward"] == 0,
            fr["b"]["reward"])
        sd = pvp.summary(d1)
        chk("배치 판수에는 안 들어간다", sd["games"] == 0, sd["games"])
        chk("친구 전적에는 남는다",
            sd["friendWins"] + sd["friendLosses"] + sd["friendDraws"] == 1, sd)
        se = pvp.summary(e1)
        chk("친구 배틀도 걸려온 쪽은 전적에 안 남는다",
            se["friendWins"] + se["friendLosses"] + se["friendDraws"] == 0, se)

        print("\n=== 하루 상한은 랜덤 배틀에만 ===")
        # 제보: "친구와의 배틀도 20판 제한에 포함되나?" - 그랬다. 이제 안 센다.
        g1 = mkuser("zz_pvp_cap", rank=True)
        h1 = mkuser("zz_pvp_cap2", 2, 30)
        # 실제 경로로 스무 판을 채운다. rank_stat 줄은 첫 판 때 생기므로
        # UPDATE 로 미리 넣으면 아무 줄도 안 바뀐다.
        for _ in range(pvp.DAILY_BATTLES):
            pvp.note_fight(g1, "random")
        # 20판 뒤에는 막지 않고 연습판으로 받는다 (점수 없이 계속) - **새 앱이 알릴 때만** (practice_ok).
        # 표시가 없는 옛 앱은 예전처럼 막힌다. 아래 '연습판' 에서 자세히 본다.
        chk("랜덤은 상한에 걸린다 (옛 앱 - 표시 없음)", "랜덤 배틀" in (pvp.can_start(g1, "random") or ""),
            pvp.can_start(g1, "random"))
        chk("20판을 다 써도 새 앱의 랜덤 배틀은 막히지 않는다 (연습판)",
            pvp.can_start(g1, "random", practice_ok=True) is None, pvp.can_start(g1, "random", practice_ok=True))
        chk("  다음 판이 연습판이라고 알려 준다", pvp.is_practice(g1)
            and pvp.fight_status(g1)["practice"] is True and pvp.fight_left(g1)["practice"] is True,
            (pvp.fight_status(g1), pvp.fight_left(g1)))
        chk("친구 배틀은 상한과 상관없다", pvp.can_start(g1, "friend") is None,
            pvp.can_start(g1, "friend"))
        chk("  친구에게 걸 수 있다", pvp.can_fight(g1, h1, "friend") is None,
            pvp.can_fight(g1, h1, "friend"))
        before = pvp.fight_status(g1)["foughtToday"]
        pvp.note_fight(g1, "friend")
        chk("친구 배틀은 오늘 판수를 안 쓴다",
            pvp.fight_status(g1)["foughtToday"] == before,
            (before, pvp.fight_status(g1)["foughtToday"]))
        i1 = mkuser("zz_pvp_cap3", 2, 30)
        n0 = pvp.fight_status(i1)["foughtToday"]
        pvp.note_fight(i1, "random")
        st = pvp.fight_status(i1)
        chk("랜덤 배틀은 한 판을 쓴다", st["foughtToday"] == n0 + 1, st)
        chk("  남은 판수도 그만큼 준다", st["left"] == pvp.DAILY_BATTLES - st["foughtToday"], st)
        chk("/api/me 의 남은 판(fight_left)도 같다 (트레이 메뉴, 1.13)",
            pvp.fight_left(i1) == {"left": st["left"], "dailyBattles": pvp.DAILY_BATTLES,
                                   "practice": False}, pvp.fight_left(i1))
        j1 = mkuser("zz_pvp_cap4", 2, 30)
        db.run("DELETE FROM rank_stat WHERE user_id=?", (j1,))
        chk("  랭크 줄이 없는 사람은 상한 그대로, 줄을 만들지 않는다 (읽기만)",
            pvp.fight_left(j1)["left"] == pvp.DAILY_BATTLES
            and db.q1("SELECT 1 FROM rank_stat WHERE user_id=?", (j1,)) is None)

        print("\n=== 연습판 (하루 20판 뒤) ===")
        practice_checks()

        print("\n=== 매칭 전력 (깍두기로 전력 깎기) ===")
        # 시즌 2 부터 평균 레벨이 아니라 팀 전력으로 붙인다. Lv.1 을 끼워 넣어도
        # 전력은 거의 그대로라 아래 사람과 붙지 못한다.
        pad = mkuser("zz_pvp_pad", 5, 60)
        db.run("UPDATE pokemon SET level=60 WHERE user_id=?", (pad,))
        filler = mkuser("zz_pvp_pad_filler", 1, 1)
        db.run("UPDATE pokemon SET user_id=?, slot=5 WHERE user_id=?", (pad, filler))
        teams = pvp._all_teams()
        full = pvp.team_power(teams[pad])
        five = pvp.team_power(teams[pad][:5] if teams[pad][0]["level"] > 1
                              else teams[pad][1:])
        chk("Lv.1 하나를 끼워도 전력은 1% 도 안 는다", full / five < 1.01, full / five)
        chk("여섯 마리가 됐으니 여섯 마리 팀과 붙을 수 있다",
            pvp.can_defend(len(teams[pad]), 6))

        print("\n=== 못 붙이는 경우 ===")
        f1 = mkuser("zz_pvp_f", 0)
        try:
            pvp.run_match(a, f1)
            chk("포켓몬이 없으면 거부한다", False, "예외가 안 났다")
        except ValueError:
            chk("포켓몬이 없으면 거부한다", True)

        print("\n=== 전적 지우기 ===")
        rating_before = pvp.summary(a)["rating"]
        games_before = pvp.summary(a)["games"]
        n_rec = len(pvp.records(a, 100))
        chk("지우기 전에 전적이 있다", n_rec > 1, n_rec)
        one = pvp.records(a, 100)[0]
        chk("한 줄만 지울 수 있다", pvp.clear_records(a, one["id"]) == 1)
        chk("그 줄이 사라졌다", len(pvp.records(a, 100)) == n_rec - 1,
            len(pvp.records(a, 100)))
        chk("남의 전적은 못 지운다", pvp.clear_records(b, one["id"]) == 0)
        removed = pvp.clear_records(a)
        chk("통째로 지울 수 있다", removed == n_rec - 1, removed)
        chk("전적이 비었다", pvp.records(a, 100) == [], pvp.records(a, 100))
        # **점수는 목록과 따로 센다.** 지운다고 등수가 오르면 진 판만
        # 골라 지우는 사람이 나온다.
        chk("지워도 점수는 그대로", pvp.summary(a)["rating"] == rating_before,
            (rating_before, pvp.summary(a)["rating"]))
        chk("지워도 판수는 그대로", pvp.summary(a)["games"] == games_before,
            (games_before, pvp.summary(a)["games"]))
        chk("지워도 순위표에 그대로 있다",
            any(x["name"] == "zz_pvp_a" for x in pvp.ranking()), pvp.ranking())

        print("\n=== 상대 고르기 ===")
        # 자세한 규칙은 test_match_rp.py 가 본다 (시즌 4: 점수가 가까운 사람부터).
        # 여기서는 방금 붙은 사람을 다시 안 고르는 것만.
        lo = mkuser('zz_mm_lo', 3, 10)
        lo2 = mkuser('zz_mm_lo2', 3, 10)
        pvp.run_match(lo, lo2, kind='random', seed=11)
        op = pvp.find_opponent(lo)
        chk('방금 붙은 사람은 다시 안 고른다', op != lo2, op)
        teams = pvp._all_teams()
        chk('그래도 규칙 밖의 사람을 데려오지는 않는다 (받는 쪽 마릿수)',
            op is None or pvp.can_defend(len(teams[lo]), len(teams[op])), op)

        print("\n=== 시즌 5: 랭크는 길드전 AI ===")
        war_ai_checks()

        print("\n=== 로그 정리 ===")
        n0 = db.q1("SELECT COUNT(*) c FROM pvp_match")["c"]
        pvp.prune(days=0)
        n1 = db.q1("SELECT COUNT(*) c FROM pvp_match")["c"]
        chk("아직 안 본 판은 안 지운다", n1 == n0, (n0, n1))
        for m in db.q("SELECT id FROM pvp_match"):
            pvp.mark_seen(a, m["id"])
            pvp.mark_seen(b, m["id"])
        pvp.prune(days=0)
        n2 = db.q1("SELECT COUNT(*) c FROM pvp_match")["c"]
        chk("양쪽이 다 본 판은 지운다", n2 < n1, (n1, n2))
        # a 의 전적은 위에서 통째로 지웠다. b 쪽으로 확인한다.
        chk("로그를 지워도 전적은 그대로 남는다", len(pvp.records(b, 100)) >= 5,
            len(pvp.records(b, 100)))
        print("\n=== 계산 중에는 같은 사람이 또 못 건다 · 판수는 한 문장으로 오른다 (10/29 검토) ===")
        from fastapi import HTTPException
        from app import pvp_routes
        busy = mkuser("zz_busy", rank=True)
        pvp_routes._busy.add(busy)
        try:
            pvp_routes.random_battle(None, {"user": {"id": busy}})
            code = None
        except HTTPException as e:
            code = e.status_code
        finally:
            pvp_routes._busy.discard(busy)
        chk("앞선 랜덤 배틀을 계산하는 동안 또 걸면 409", code == 409, code)
        try:
            pvp_routes.random_battle(None, {"user": {"id": busy}})
        except HTTPException:
            pass                      # 상대가 없거나 막혀도 된다 - 아래는 표가 비었는지만 본다
        chk("  끝나면(막혀도) 계산 중 표에서 빠진다", busy not in pvp_routes._busy, sorted(pvp_routes._busy))
        db.run("UPDATE rank_stat SET fought_day=?, fought=7 WHERE user_id=?", ("2000-01-01", busy))
        pvp.note_fight(busy)
        r = pvp._rating_row(busy)
        chk("  지난 날의 판수는 1 부터 다시", (r["fought_day"], r["fought"]) == (pvp._today(), 1), dict(r))
        pvp.note_fight(busy)
        pvp.note_fight(busy, "friend")
        chk("  같은 날은 하나씩 오르고 친구 배틀은 안 센다", pvp._rating_row(busy)["fought"] == 2,
            pvp._rating_row(busy)["fought"])
    finally:
        for n in ("zz_busy", "zz_pvp_a", "zz_pvp_b", "zz_pvp_c", "zz_pvp_d",
                  "zz_pvp_e", "zz_pvp_f", "zz_mm_lo", "zz_mm_lo2",
                  "zz_mm_mid", "zz_mm_hi", "zz_pvp_pad", "zz_pvp_pad_filler",
                  "zz_pvp_cap", "zz_pvp_cap2", "zz_pvp_cap3", "zz_pvp_cap4",
                  "zz_pr_a", "zz_pr_b", "zz_pr_c", "zz_pr_d", "zz_s5_a", "zz_s5_b"):
            db.run("DELETE FROM users WHERE username=?", (n,))

    print("\n======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
