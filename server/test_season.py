# -*- coding: utf-8 -*-
"""랭크 시즌 2 — RP·티어, 랭크 팀, 전력 매칭, 칭호·명패, 이로치사탕, 알, 시즌 전환.

    python server/test_season.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙인다. 못 박는 것:

  1. **RP 는 한 만큼 오른다.** 비슷한 상대면 이기면 +20, 지면 -15. 슈퍼볼에
     한 번 오르면 그 아래로 안 떨어진다. 하루 첫 승·연패 보호.
  2. **받는 쪽이 거는 쪽보다 적으면 안 붙인다.** 전력이 비슷한 사람과 붙인다.
  3. **랭크 배틀은 Lv.50 상한, 친구 배틀은 원래 레벨.**
  4. 랭크 팀이 있으면 그 팀으로, 놓아준 포켓몬은 팀에서 빠진다.
  5. 칭호·명패는 선물로 받아 달 수 있고, 가진 것만 달 수 있다.
  6. 이로치사탕은 한 번 쓰면 이로치가 되고, 이미 이로치면 안 쓴다.
  7. 시즌 전환은 순위대로 보상을 넣고, 두 번 돌아도 두 번 안 준다.
     1위 전설의 알, 2~5위 환상의 알, 이로치사탕은 1~10위에 하나씩, 31위부터 없음.
  8. 알은 켜 둔 시간(walk.settle)만큼만 자라고, 다 차면 한 번만 부화한다.
"""
import json
import os
import random
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-season-")
# **setdefault 로 두지 않는다** (test_evolution 과 같은 까닭 - 서버 컨테이너
# 안에서는 POKET_DB 가 돌고 있는 서버의 DB 를 가리킨다).
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                          # noqa: E402

from app import config, db, deps, eggs, items, migrations, pvp, season, social  # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(name, mons=0, level=30, species=None):
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,?,?,'')",
        (name, b"x", b"x", "2026-01-01", "2026-01-01"))
    uid = cur.lastrowid
    d = deps.dex()
    rng = random.Random(zlib.crc32(name.encode("utf-8")))
    for i in range(mons):
        m = d.roll_wild(level, level, rng)
        if species:
            m["species"] = species
        pid = db.insert_mon(uid, m, "2026-01-01")
        db.run("UPDATE pokemon SET on_desktop=1, slot=?, level=? WHERE id=?",
               (i, level, pid))
    return uid


def status_of(fn):
    try:
        fn()
    except HTTPException as e:
        return e.status_code
    return None


def stat(uid):
    return pvp._rating_row(uid)


def main():
    db.init()

    print("=== RP 한 판 ===")
    new, d, notes = season.rp_change("win", 1000, 1000, 0, False, 0, 0)
    chk("비슷한 상대를 이기면 +20", d == 20, d)
    new, d, notes = season.rp_change("lose", 1000, 1000, 0, False, 100, 100)
    chk("비슷한 상대에게 지면 -15", d == -15, d)
    new, d, notes = season.rp_change("win", 1000, 1000, 0, True, 0, 0)
    chk("오늘 첫 승이면 +10 더", d == 30 and notes, (d, notes))
    new, d, notes = season.rp_change("win", 1400, 1000, 0, False, 0, 0)
    chk("훨씬 약한 상대를 이기면 조금만 (10~20)", 10 <= d < 20, d)
    new, d, notes = season.rp_change("win", 1000, 1400, 0, False, 0, 0)
    chk("훨씬 센 상대를 이기면 많이 (20~30)", 20 < d <= 30, d)
    new, d, notes = season.rp_change("lose", 1000, 1000, -3, False, 100, 100)
    chk("3연패 뒤에는 절반만 깎인다", d == -8 and notes, (d, notes))
    new, d, notes = season.rp_change("lose", 1000, 1000, 0, False, 5, 5)
    chk("0 아래로는 안 내려간다", new == 0 and d == -5, (new, d))
    new, d, notes = season.rp_change("lose", 1000, 1000, 0, False, 160, 170)
    chk("슈퍼볼에 올랐으면 150 아래로 안 내려간다", new == 150, new)
    new, d, notes = season.rp_change("lose", 1000, 1000, 0, False, 360, 370)
    chk("하이퍼볼에서는 슈퍼볼로 떨어질 수 있다", new == 345, new)
    new, d, notes = season.rp_change("draw", 1000, 1000, 0, False, 50, 50)
    chk("비기면 그대로", d == 0 and new == 50, (new, d))

    print("\n=== 기대 승률에 두 팀 전력 ===")
    import math as _m

    def logit(p):
        return _m.log(p / (1 - p))
    chk("전력이 같으면 예전 식과 같다 (반반)", abs(season.expected(1000, 1000, 1.0) - 0.5) < 1e-12)
    chk("전력비를 안 주면 1 로 본다",
        season.expected(1200, 1000) == season.expected(1200, 1000, 1.0)
        == 1.0 / (1.0 + 10 ** (-200 / 400.0)))
    e125 = season.expected(1000, 1000, 1.25)
    chk("전력비 1.25 면 센 쪽 기대치 약 83%", 0.82 < e125 < 0.835, e125)
    chk("한쪽을 뒤집으면 합이 1 (숨은 점수 · 전력비 둘 다 뒤집어서)",
        abs(season.expected(1100, 950, 1.2) + season.expected(950, 1100, 1 / 1.2) - 1) < 1e-12)
    chk("숨은 점수와 전력은 로짓으로 더해진다",
        abs(logit(season.expected(1100, 1000, 1.1))
            - logit(season.expected(1100, 1000, 1.0)) - logit(season.expected(1000, 1000, 1.1))) < 1e-9)
    chk("전력비가 0 · 음수 · None · 글자이면 1 로 본다",
        all(season.expected(1000, 1000, x) == 0.5 for x in (0, -2, None, "x", float("nan"))))
    chk("몇백만 배 차이가 와도 안 넘치고 0~1 안",
        0.0 <= season.expected(0, 5000, 1e9) <= 1.0 and 0.0 <= season.expected(5000, 0, 1e-9) <= 1.0)
    new, d, _ = season.rp_change("win", 1000, 1000, 0, False, 0, 0, 1.14)
    chk("약한 팀(전력 0.88배)을 이기면 덜 받는다 (+20 -> +16)", d == 16, d)
    new, d, _ = season.rp_change("lose", 1000, 1000, 0, False, 100, 100, 1.14)
    chk("약한 팀에게 지면 더 잃는다 (-15 -> -19)", d == -19, d)
    new, d, _ = season.rp_change("win", 1000, 1000, 0, False, 0, 0, 1 / 1.15)
    chk("센 팀을 이기면 더 받는다 (+25)", d == 25, d)
    new, d, _ = season.rp_change("lose", 1000, 1000, 0, False, 100, 100, 1 / 1.15)
    chk("센 팀에게 지면 덜 잃는다 (-10)", d == -10, d)
    lo_w = season.rp_change("win", 1000, 1000, 0, False, 0, 0, 1000.0)[1]
    hi_w = season.rp_change("win", 1000, 1000, 0, False, 0, 0, 0.001)[1]
    lo_l = season.rp_change("lose", 1000, 1000, 0, False, 100, 100, 0.001)[1]
    hi_l = season.rp_change("lose", 1000, 1000, 0, False, 100, 100, 1000.0)[1]
    chk("범위는 그대로 (+10~30, -5~25)", (lo_w, hi_w, lo_l, hi_l) == (10, 30, -5, -25),
        (lo_w, hi_w, lo_l, hi_l))
    new, d, _ = season.rp_change("win", 1000, 1000, 0, True, 0, 0, 1.14)
    chk("첫 승 보너스는 전력과 상관없이 +10", d == 26, d)
    new, d, _ = season.rp_change("lose", 1000, 1000, -3, False, 100, 100, 1.14)
    chk("연패 보호도 그대로 (절반)", d == -10, d)
    chk("규칙표에 전력 무게가 실린다", season.rules_public()["rp"]["powerK"] == season.POWER_K)

    print("\n=== 티어 ===")
    chk("0 은 몬스터볼", season.tier_of(0) == "monster")
    chk("149 는 몬스터볼, 150 은 슈퍼볼",
        season.tier_of(149) == "monster" and season.tier_of(150) == "super")
    chk("350 하이퍼볼 · 600 마스터볼",
        season.tier_of(350) == "hyper" and season.tier_of(600) == "master")
    chk("다음 티어까지 남은 RP", season.next_tier(100) == ("super", 50),
        season.next_tier(100))
    chk("화면에 가는 규칙표도 같은 경계",
        [t.get("rp") for t in season.rules_public()["tiers"][:4]] == [0, 150, 350, 600]
        and season.rules_public()["safeRp"] == 150)
    chk("마스터볼 위는 자리라 RP 로 안 오른다", season.next_tier(5000) == (None, 0))

    print("\n=== 랭크 배틀은 Lv.50 상한, 친구 배틀은 그대로 ===")
    hi = mkuser("ss_hi", 6, 80)
    hi2 = mkuser("ss_hi2", 6, 80)
    r = pvp.run_match(hi, hi2, kind="random", seed=5)
    v = pvp.match_view(hi, r["matchId"])
    teams = [e for e in v["events"] if e["t"] == "teams"][0]
    lv = [m["level"] for m in teams["me"] + teams["foe"]]
    chk("랭크 배틀 명단의 레벨이 전부 50", set(lv) == {50}, lv)
    chk("다시보기에 상한이 실려 온다", v["levelCap"] == 50, v.get("levelCap"))
    chk("원래 포켓몬은 Lv.80 그대로",
        db.q1("SELECT MIN(level) m FROM pokemon WHERE user_id=?", (hi,))["m"] == 80)
    db.run("INSERT INTO friend (a_id, b_id, state, asked_by, created_at)"
           " VALUES (?,?,'accepted',?,'2026-01-01')", (min(hi, hi2), max(hi, hi2), hi))
    r2 = pvp.run_match(hi, hi2, kind="friend", seed=6)
    v2 = pvp.match_view(hi, r2["matchId"])
    teams = [e for e in v2["events"] if e["t"] == "teams"][0]
    chk("친구 배틀은 원래 레벨(80)로 싸운다",
        set(m["level"] for m in teams["me"]) == {80})
    chk("친구 배틀 다시보기에는 상한이 없다", v2["levelCap"] is None)

    print("\n=== 랜덤 배틀 30초 쿨타임 ===")
    chk("쿨타임은 30초", config.RANDOM_COOLDOWN_SEC == 30, config.RANDOM_COOLDOWN_SEC)
    left = pvp.random_cooldown_left(hi)
    chk("방금 랜덤 배틀을 걸었으면 남은 초가 있다", 0 < left <= 30, left)
    why = pvp.can_start(hi, "random")
    chk("다시 걸면 막히고 몇 초 남았는지 알려준다", why and "초 뒤에" in why, why)
    chk("친구 배틀은 쿨타임과 상관없다", pvp.can_start(hi, "friend") is None,
        pvp.can_start(hi, "friend"))
    chk("걸려온 쪽(hi2)은 쿨타임이 없다", pvp.random_cooldown_left(hi2) == 0)
    import datetime as _dt
    old = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(seconds=31)).isoformat()
    db.run("UPDATE battle_record SET ended_at=? WHERE user_id=? AND kind='random'",
           (old, hi))
    chk("30초가 지나면 다시 걸 수 있다", pvp.can_start(hi, "random") is None,
        pvp.can_start(hi, "random"))
    fs = pvp.fight_status(hi)
    chk("남은 도전 정보에 쿨타임", fs["randomCooldownSec"] == 30
        and fs["randomCooldownLeft"] == 0, fs)

    print("\n=== 랜덤 배틀 뒤처리 — RP ===")
    rs = stat(hi)
    chk("건 쪽 RP 가 결과대로 움직였다",
        (r["a"]["result"] == "win" and rs["rp"] >= 20)
        or (r["a"]["result"] != "win" and rs["rp"] == 0), (r["a"], rs["rp"]))
    chk("RP 가 결과에 실려 온다", r["a"]["rp"] == rs["rp"], r["a"])
    ratio_hi = pvp.power_ratio(pvp.capped(pvp.ranked_team(hi)), pvp.capped(pvp.ranked_team(hi2)))
    if r["a"]["result"] == "win":
        want = season.rp_change("win", 1000, 1000, 0, True, 0, 0, ratio_hi)[1]
        chk("첫 승이라 첫 승 보너스가 붙었다 (전력비 %.2f 로 잰 값)" % ratio_hi,
            r["a"]["rpDelta"] == want and want >= 20
            and rs["win_day"] == pvp._today(), (r["a"]["rpDelta"], want, rs["win_day"]))
    chk("걸려온 쪽 RP 는 그대로", stat(hi2)["rp"] == 0, stat(hi2)["rp"])
    chk("최고 RP 를 기억한다", rs["peak_rp"] == rs["rp"], (rs["peak_rp"], rs["rp"]))
    rec = pvp.records(hi)
    rand = [x for x in rec if x["kind"] == "random"][0]
    chk("전적에 RP 변화가 남는다", rand["rpDelta"] == r["a"]["rpDelta"], rand)
    chk("친구 배틀은 RP 를 안 건드린다", r2["a"]["rpDelta"] == 0, r2["a"])

    print("\n=== 전력비가 RP 와 숨은 점수에 들어간다 (run_match) ===")
    strong = mkuser("ss_pw_strong", 6, 50, species="GARCHOMP")
    weak = mkuser("ss_pw_weak", 6, 47, species="GARCHOMP")
    ratio = pvp.power_ratio(pvp.capped(pvp.ranked_team(strong)),
                            pvp.capped(pvp.ranked_team(weak)))
    chk("같은 종 Lv.50 여섯 vs Lv.47 여섯 = 전력비 (50/47)^1.5",
        abs(ratio - (50 / 47.0) ** 1.5) < 1e-9, ratio)
    # 진 판의 RP 도 보이게 바닥(0)에서 떼어 둔다. 안 그러면 진 판은 늘 0 == 0 이다.
    for u in (strong, weak):
        stat(u)
        db.run("UPDATE rank_stat SET rp=100, peak_rp=100 WHERE user_id=?", (u,))
    seen = {}
    # 같은 종이면 레벨 높은 쪽이 늘 이겨서 네 길(센/약한 x 승/패)이 다 안 나온다.
    # 엔진은 그대로 돌리고 **승패만 정해 준다** - 점수 뒤처리는 winner 만 본다.
    real_sim = pvp.PB.simulate

    def forced_sim(winner):
        def sim(*a, **kw):
            out = real_sim(*a, **kw)
            out["winner"] = winner
            return out
        return sim
    plan = [(att, dfn, rr, w) for w in ("me", "foe", "me", "foe")
            for att, dfn, rr in ((strong, weak, ratio), (weak, strong, 1 / ratio))]
    for i, (att, dfn, rr, w) in enumerate(plan):
        if True:
            before, before_d = stat(att), stat(dfn)
            db.run("UPDATE rank_stat SET win_day='2000-01-01', streak=0, rp=100, peak_rp=100"
                   " WHERE user_id=?", (att,))
            before = stat(att)
            pvp.PB.simulate = forced_sim(w)
            try:
                res = pvp.run_match(att, dfn, kind="random", seed=4000 + i)
            finally:
                pvp.PB.simulate = real_sim
            e = season.expected(before["rating"], before_d["rating"], rr)
            got = res["a"]
            want_mmr = int(round(pvp.K * (pvp._score(got["result"]) - e)))
            want_rp = season.rp_change(got["result"], before["rating"], before_d["rating"], 0,
                                       got["result"] == "win", before["rp"] or 0,
                                       before["peak_rp"] or 0, rr)[1]
            key = ("strong" if att == strong else "weak", got["result"])
            ok = got["delta"] == want_mmr and got["rpDelta"] == want_rp
            seen.setdefault(key, []).append((ok, got["rpDelta"], want_rp, got["delta"], want_mmr))
            chk_ok = ok and res["b"]["delta"] == 0 and stat(dfn)["rating"] == before_d["rating"]
            if not chk_ok:
                chk("판마다 RP·숨은 점수가 전력비 넣은 식과 같다 (%s)" % (key,), False,
                    (got, want_rp, want_mmr))
                break
    chk("판마다 RP·숨은 점수가 전력비 넣은 식과 같다 (%d판, 걸려온 쪽은 그대로)"
        % sum(len(v) for v in seen.values()),
        all(ok for v in seen.values() for ok, *_ in v), seen)
    chk("넷 다 나왔다 (센 팀 승·패, 약한 팀 승·패) - 식 비교가 네 길을 다 지난다",
        sorted(seen) == [("strong", "lose"), ("strong", "win"), ("weak", "lose"), ("weak", "win")],
        sorted(seen))
    sw = seen.get(("strong", "win"), [])
    chk("센 팀이 약한 팀을 이기면 첫 승을 빼고 +20 보다 적게",
        sw and all(rpd - 10 < 20 for _ok, rpd, *_ in sw), sw)
    sl = seen.get(("strong", "lose"), [])
    chk("센 팀이 약한 팀에게 지면 -15 보다 더 잃는다",
        sl and all(rpd < -15 for _ok, rpd, *_ in sl), sl)
    wl = seen.get(("weak", "lose"), [])
    chk("약한 팀이 센 팀에게 지면 -15 보다 덜 잃는다",
        wl and all(-15 < rpd < 0 for _ok, rpd, *_ in wl), wl)
    ww = seen.get(("weak", "win"), [])
    chk("약한 팀이 센 팀을 이기면 첫 승을 빼고 +20 보다 많이",
        ww and all(rpd - 10 > 20 for _ok, rpd, *_ in ww), ww)
    fr = pvp.run_match(strong, weak, kind="friend", seed=99)
    chk("친구 배틀은 여전히 점수를 안 건드린다", fr["a"]["delta"] == 0 and fr["a"]["rpDelta"] == 0)

    print("\n=== 전적 목록에 시즌 2 숨은 점수를 싣지 않는다 ===")
    floor_u = mkuser("ss_floor", 6, 40, species="GARCHOMP")
    stat(floor_u)
    lost = None
    for i in range(10):
        db.run("UPDATE rank_stat SET rp=0, peak_rp=0 WHERE user_id=?", (floor_u,))
        res = pvp.run_match(floor_u, strong, kind="random", seed=7000 + i)
        if res["a"]["result"] == "lose":
            lost = res
            break
    stored = db.q1("SELECT delta, rp, rp_delta FROM battle_record WHERE user_id=?"
                   " AND started=1 ORDER BY id DESC LIMIT 1", (floor_u,))
    rec0 = pvp.records(floor_u)[0]
    chk("바닥(RP 0)에서 진 판: 기록에는 숨은 점수 변화가 있고 RP 변화는 0",
        lost is not None and stored["delta"] != 0 and stored["rp_delta"] == 0, dict(stored))
    chk("전적 목록에는 숨은 점수 변화·숨은 점수를 싣지 않는다 ('점수 -N' 이 안 뜬다)",
        rec0["delta"] == 0 and rec0["rating"] is None and rec0["rpDelta"] == 0, rec0)
    db.run("INSERT INTO battle_record (user_id, foe_id, foe_name, kind, result, rating, delta,"
           " reward, turns, my_left, foe_left, started, ended_at, rp, rp_delta)"
           " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
           (floor_u, strong, "옛상대", "random", "win", 1016, 16, 0, 5, 1, 0, 1,
            "2026-09-01T00:00:00+00:00", 0, 0))
    old = [x for x in pvp.records(floor_u) if x["at"].startswith("2026-09-01")]
    chk("시즌 1 판은 그때 보이던 점수를 그대로", old and old[0]["delta"] == 16
        and old[0]["rating"] == 1016, old)

    print("\n=== 친구 찾기 카드의 점수는 RP ===")
    db.run("UPDATE rank_stat SET rating=1450, rp=234, ranked=1 WHERE user_id=?", (strong,))
    found = social.find(weak, "ss_pw_strong")
    chk("찾기 결과의 점수 칸은 숨은 점수가 아니라 RP", found.get("rating") == 234
        and found.get("rp") == 234 and found.get("tierKr"), found)

    print("\n=== 랭크 팀 ===")
    t = mkuser("ss_team", 6, 20)
    extra = [db.insert_mon(t, dict(deps.dex().roll_wild(40, 40, random.Random(i)),
                                   level=40), "2026-01-01") for i in range(3)]
    chk("등록 안 했으면 바탕화면 파티로 싸운다",
        [m["level"] for m in pvp.ranked_team(t)] == [20] * 6)
    pvp.set_team(t, [extra[2], extra[0], extra[1]])
    chk("등록한 팀이 그 순서대로 나온다",
        [m["id"] for m in pvp.ranked_team(t)] == [extra[2], extra[0], extra[1]])
    other = mkuser("ss_other", 1, 10)
    theirs = db.q1("SELECT id FROM pokemon WHERE user_id=?", (other,))["id"]
    try:
        pvp.set_team(t, [extra[0], theirs])
        chk("남의 포켓몬은 못 넣는다", False, "예외가 안 났다")
    except ValueError:
        chk("남의 포켓몬은 못 넣는다", True)
    try:
        pvp.set_team(t, list(range(1, 8)))
        chk("일곱 마리는 못 넣는다", False)
    except ValueError:
        chk("일곱 마리는 못 넣는다", True)
    chk("실패해도 원래 팀은 그대로", len(pvp.team_ids(t)) == 3, pvp.team_ids(t))
    db.run("DELETE FROM pokemon WHERE id=?", (extra[0],))
    chk("놓아준 포켓몬은 팀에서 빠진다", pvp.team_ids(t) == [extra[2], extra[1]],
        pvp.team_ids(t))
    teams = pvp._all_teams()
    chk("매칭도 등록한 팀으로 본다", len(teams[t]) == 2, len(teams.get(t, [])))
    pvp.set_team(t, [])
    chk("빈 목록이면 등록이 풀린다", pvp.team_ids(t) == []
        and len(pvp.ranked_team(t)) == 6)

    print("\n=== 전설·환상은 1마리까지 ===")
    lg = mkuser("ss_legend", 6, 40)
    rows = db.q("SELECT id FROM pokemon WHERE user_id=? ORDER BY slot", (lg,))
    ids = [r["id"] for r in rows]
    db.run("UPDATE pokemon SET species='MEWTWO' WHERE id=?", (ids[1],))
    db.run("UPDATE pokemon SET species='MEW' WHERE id=?", (ids[3],))
    db.run("UPDATE pokemon SET species=? WHERE id=?", (config.EVENT_SPECIES, ids[4]))
    names = pvp.restricted_species()
    chk("전설·환상 목록은 94종 (이벤트 종 포함)", len(names) == 94
        and config.EVENT_SPECIES in names and "MEWTWO" in names, len(names))
    chk("울트라비스트·패러독스는 제한이 아니다",
        "NIHILEGO" not in names and "GREATTUSK" not in names)
    team = pvp.ranked_team(lg)
    chk("바탕화면 파티로 싸우면 앞의 전설 하나만 나간다",
        [m["id"] for m in team] == [ids[0], ids[1], ids[2], ids[5]],
        [m["id"] for m in team])
    sm = pvp.summary(lg)
    chk("요약에 빠진 마릿수", sm["restrictedDropped"] == 2 and sm["teamSize"] == 4, sm)
    chk("매칭 전력도 빠진 팀으로 잰다", len(pvp._all_teams()[lg]) == 4)
    try:
        pvp.set_team(lg, [ids[0], ids[1], ids[3]])
        chk("랭크 팀에 전설·환상 두 마리는 못 넣는다", False, "예외가 안 났다")
    except ValueError as e:
        chk("랭크 팀에 전설·환상 두 마리는 못 넣는다", "1마리" in str(e), str(e))
    chk("실패하면 등록이 안 된다", pvp.team_ids(lg) == [])
    pvp.set_team(lg, [ids[0], ids[1], ids[2]])
    chk("한 마리면 된다", pvp.team_ids(lg) == [ids[0], ids[1], ids[2]])
    r = pvp.run_match(lg, hi, kind="random", seed=9)
    v = pvp.match_view(lg, r["matchId"])
    tm = [e for e in v["events"] if e["t"] == "teams"][0]["me"]
    chk("판에 나간 전설·환상도 하나", sum(1 for m in tm if m["species"] in names) == 1, tm)
    pvp.set_team(lg, [])
    from app import pvp_routes
    tv = pvp_routes._team_view(lg)
    chk("팀 창에 제한 정보", tv["restrictedMax"] == 1 and 150 in tv["restrictedNums"]
        and tv["restrictedDropped"] == 2 and len(tv["ids"]) == 6, tv["restrictedDropped"])

    print("\n=== 받는 쪽 마릿수 ===")
    chk("여섯으로 걸면 여섯만 받는다",
        pvp.can_defend(6, 6) and not pvp.can_defend(6, 5))
    chk("두 마리로 걸면 두 마리 이상이면 받는다",
        pvp.can_defend(2, 2) and pvp.can_defend(2, 6) and not pvp.can_defend(2, 1))

    print("\n=== 전력 매칭 ===")
    chk("레벨이 높을수록 전력이 크다",
        pvp.team_power([{"species": "PIKACHU", "level": 30}])
        > pvp.team_power([{"species": "PIKACHU", "level": 20}]))
    chk("전력도 Lv.50 에서 자른다",
        pvp.team_power([{"species": "PIKACHU", "level": 90}])
        == pvp.team_power([{"species": "PIKACHU", "level": 50}]))
    # 한 마리 센 팀이 약한 여러 마리보다 세게 잡힌다 (1.5 제곱)
    chk("센 한 마리가 같은 레벨 합의 둘보다 세게 잡힌다",
        pvp.team_power([{"species": "PIKACHU", "level": 40}])
        > pvp.team_power([{"species": "PIKACHU", "level": 20}] * 2))
    # 이 DB 에 사람을 더 넣고 고른 사람이 규칙을 지키는지만 본다.
    for i in range(4):
        mkuser("ss_mm6_%d" % i, 6, 30 + i)
    for i in range(3):
        mkuser("ss_mm2_%d" % i, 2, 12 + i)
    a6 = mkuser("ss_att6", 6, 31)
    a2 = mkuser("ss_att2", 2, 13)
    teams = pvp._all_teams()
    for att in (a6, a2):
        mine = teams[att]
        seen_ops = set()
        for k in range(12):
            op = pvp.find_opponent(att, random.Random(k))
            if op is None:
                continue
            seen_ops.add(op)
            gap = abs(pvp.team_power(teams[op]) / pvp.team_power(mine) - 1)
            if gap > pvp.POWER_BANDS[-1] or not pvp.can_defend(len(mine), len(teams[op])):
                chk("고른 상대가 규칙 안에 있다 (%s)" % att, False, (op, gap, len(teams[op])))
                break
        else:
            chk("%d마리로 걸 때 고른 상대가 전부 규칙 안 (전력 %d%% · 마릿수)"
                % (len(mine), int(pvp.POWER_BANDS[-1] * 100)), bool(seen_ops), seen_ops)
    chk("두 마리 초보도 상대를 찾는다", pvp.find_opponent(a2) is not None)
    lonely = mkuser("ss_lonely", 6, 100, species="ARCEUS")
    op = pvp.find_opponent(lonely)
    chk("전력이 동떨어지면 안 붙인다",
        op is None or abs(pvp.team_power(pvp._all_teams()[op])
                          / pvp.team_power(pvp._all_teams()[lonely]) - 1)
        <= pvp.POWER_BANDS[-1], op)

    print("\n=== 자리 (사천왕·챔피언) ===")
    seat_users = []
    for i, rp in enumerate((1500, 1400, 1300, 1250, 1210, 1205, 500)):
        u = mkuser("ss_seat_%d" % i)
        pvp._rating_row(u)
        db.run("UPDATE rank_stat SET rp=?, peak_rp=?, ranked=1, games=10"
               " WHERE user_id=?", (rp, rp, u))
        seat_users.append(u)
    seats = season.seats()
    chk("RP 1등이 챔피언", seats.get(seat_users[0]) == "champion", seats)
    chk("2~5등이 사천왕",
        [seats.get(u) for u in seat_users[1:5]] == ["elite"] * 4, seats)
    chk("6등은 마스터볼이어도 자리가 없다", seat_users[5] not in seats)
    board = pvp.ranking(10)
    chk("순위표는 RP 순", [x["rp"] for x in board] == sorted(
        [x["rp"] for x in board], reverse=True), [x["rp"] for x in board])
    chk("순위표에 티어가 실린다", board[0]["tier"] == "champion"
        and board[0]["tierKr"] == "챔피언", board[0])
    sm = pvp.summary(seat_users[6])
    chk("내 요약에 티어·다음 티어", sm["tier"] == "hyper"
        and sm["nextTier"] == "master" and sm["rpToNext"] == 100, sm)

    print("\n=== 칭호·명패 선물 ===")
    g = mkuser("ss_gift")
    now = "2026-09-15T00:00:00+00:00"
    for kind, rid, n in (("title", "s1_elite", 1), ("frame", "silver", 1),
                         ("item", "SHINYCANDY", 2)):
        db.run("INSERT INTO gift (user_id, kind, item_id, count, title, message,"
               " created_at) VALUES (?,?,?,?,?,?,?)",
               (g, kind, rid, n, "시즌 1 보상", "말", now))
    got = items.gift_claim(g)
    chk("세 줄이 지급됐다", len(got) == 3, got)
    chk("칭호 이름이 실려 온다", got[0]["name"] == "시즌 1 사천왕", got[0])
    chk("명패 이름이 실려 온다", got[1]["name"] == "은빛 명패", got[1])
    titles, frames = season.owned(g)
    chk("칭호를 가졌다", [x["id"] for x in titles] == ["s1_elite"], titles)
    chk("명패를 가졌다", [x["id"] for x in frames] == ["silver"], frames)
    chk("받은 시즌이 남는다", titles[0]["season"] == 1, titles)
    chk("이로치사탕은 가방으로", items.bag_count(g, "SHINYCANDY") == 2)
    dd = season.deco(g)
    chk("처음 받은 칭호·명패는 바로 단다",
        dd["title"] == "시즌 1 사천왕" and dd["frame"] == "silver", dd)
    chk("두 번 받지 않는다", items.gift_claim(g) == [])
    season.grant(g, "title", "s1_top10", 1)
    chk("이미 달고 있으면 새 칭호로 안 바꾼다", season.deco(g)["title"] == "시즌 1 사천왕")
    season.equip(g, title="s1_top10")
    chk("고르면 바뀐다", season.deco(g)["title"] == "시즌 1 TOP 10")
    try:
        season.equip(g, title="s1_champion")
        chk("안 가진 칭호는 못 단다", False)
    except ValueError:
        chk("안 가진 칭호는 못 단다", True)
    season.equip(g, title="", frame="")
    dd = season.deco(g)
    chk("빈 글자면 뗀다", dd["title"] is None and dd["frame"] is None, dd)

    print("\n=== 이로치사탕 ===")
    from app import item_routes as R
    pid = db.insert_mon(g, deps.dex().roll_wild(20, 20, random.Random(3)), now)
    db.run("UPDATE pokemon SET shiny=0 WHERE id=?", (pid,))
    me = {"user": {"id": g}}
    out = R.use(R.UseIn(item="SHINYCANDY", pokemon=pid), me)
    chk("쓰면 이로치가 된다",
        db.q1("SELECT shiny FROM pokemon WHERE id=?", (pid,))["shiny"] == 1, out)
    chk("사탕이 하나 줄었다", items.bag_count(g, "SHINYCANDY") == 1)
    chk("이미 이로치면 400",
        status_of(lambda: R.use(R.UseIn(item="SHINYCANDY", pokemon=pid), me)) == 400)
    chk("막혀도 사탕은 그대로", items.bag_count(g, "SHINYCANDY") == 1)
    it = items.get("SHINYCANDY")
    chk("상점에서 안 판다", items.buy_price("SHINYCANDY") == 0 and it.get("buyable") is False)
    chk("드랍표에 없다", "SHINYCANDY" not in [x[0] for x in items.data()["dropTable"]])
    chk("그림이 있다", os.path.exists(os.path.join(HERE, "data", "item_sprites",
                                                   "SHINYCANDY.png")))

    print("\n=== 시즌 1 -> 2 전환 ===")
    # 시즌 1 이 끝난 상태를 만든다: 서른다섯 명이 배치를 마쳤고, 한 명은 못 마쳤다.
    db.run("DELETE FROM rank_stat")
    db.run("DELETE FROM gift")
    s1 = []
    for i in range(35):
        u = mkuser("s1_%02d" % i)
        pvp._rating_row(u)
        db.run("UPDATE rank_stat SET rating=?, best=?, games=20, wins=?, losses=?,"
               " ranked=1, rp=0, fr_wins=3, earned=700, earned_day='2026-09-15'"
               " WHERE user_id=?", (1800 - i * 20, 1800 - i * 20, 15 - i // 5, 5, u))
        s1.append(u)
    un = mkuser("s1_unranked")
    pvp._rating_row(un)
    db.run("UPDATE rank_stat SET rating=900, games=3, ranked=0 WHERE user_id=?", (un,))
    conn = db.connect()
    note = migrations._season2_open(conn)
    conn.commit()
    print("  (%s)" % note)
    res = dict((r["user_id"], r) for r in db.q("SELECT * FROM season_result WHERE season=1"))
    chk("배치를 마친 35명만 보관", len(res) == 35 and un not in res, len(res))
    chk("1등이 1위로", res[s1[0]]["rank"] == 1 and res[s1[0]]["title"] == "s1_champion")
    chk("그때의 점수가 남는다", res[s1[0]]["rating"] == 1800, res[s1[0]]["rating"])

    def gifts_of(u):
        return [(r["kind"], r["item_id"], r["count"]) for r in
                db.q("SELECT * FROM gift WHERE user_id=? ORDER BY id", (u,))]
    chk("1위: 전설의 알 + 챔피언 칭호 + 금빛 명패 + 사탕 1",
        gifts_of(s1[0]) == [("egg", "legendary", 1), ("title", "s1_champion", 1),
                            ("frame", "gold", 1), ("item", "SHINYCANDY", 1)],
        gifts_of(s1[0]))
    chk("2~5위: 환상의 알 + 사천왕 + 은빛 + 사탕 1",
        all(gifts_of(u) == [("egg", "mythical", 1), ("title", "s1_elite", 1),
                            ("frame", "silver", 1), ("item", "SHINYCANDY", 1)]
            for u in s1[1:5]), gifts_of(s1[4]))
    chk("6~10위: TOP 10 + 동빛 + 사탕 1",
        all(gifts_of(u) == [("title", "s1_top10", 1), ("frame", "bronze", 1),
                            ("item", "SHINYCANDY", 1)] for u in s1[5:10]), gifts_of(s1[9]))
    chk("11~30위: 상위권 칭호만 (사탕 없음)",
        all(gifts_of(u) == [("title", "s1_top30", 1)] for u in s1[10:30]),
        gifts_of(s1[29]))
    chk("31위부터: 보상 없음",
        all(gifts_of(u) == [] for u in s1[30:]), gifts_of(s1[30]))
    chk("31위부터도 순위는 보관한다", res[s1[34]]["rank"] == 35, dict(res[s1[34]]))
    n_candy = db.q1("SELECT SUM(count) c FROM gift WHERE item_id='SHINYCANDY'")["c"]
    chk("이로치사탕은 모두 10개 (1~10위에 하나씩)", n_candy == 10, n_candy)
    chk("배치를 못 마친 사람은 없다", gifts_of(un) == [])
    msg = db.q1("SELECT message FROM gift WHERE user_id=?", (s1[12],))["message"]
    chk("안내에 순위가 들어간다", "13위" in msg and "명패" not in msg, msg)
    msg = db.q1("SELECT message FROM gift WHERE user_id=?", (s1[0],))["message"]
    chk("알을 받은 사람에게는 알 안내", "전설의 포켓몬 알" in msg and "켜 둔 시간" in msg,
        msg)
    st = stat(s1[0])
    chk("숨은 점수는 절반만 남는다 (1800 -> 1400)", st["rating"] == 1400, st["rating"])
    chk("1000 아래도 절반 (900 -> 950)", stat(un)["rating"] == 950, stat(un)["rating"])
    chk("판수·승패·RP 는 0", (st["games"], st["wins"], st["losses"], st["rp"],
                           st["ranked"]) == (0, 0, 0, 0, 0), dict(st))
    chk("최고 점수도 새 점수로", st["best"] == 1400, st["best"])
    chk("친구 전적·오늘 상금은 그대로", st["fr_wins"] == 3 and st["earned"] == 700)
    n_gift = db.q1("SELECT COUNT(*) c FROM gift")["c"]
    migrations._season2_open(conn)
    conn.commit()
    chk("두 번 돌아도 선물을 또 넣지 않는다",
        db.q1("SELECT COUNT(*) c FROM gift")["c"] == n_gift, n_gift)
    got = items.gift_claim(s1[0])
    chk("1위가 켜면 네 줄을 받는다",
        [x["kind"] for x in got] == ["egg", "title", "frame", "item"], got)
    chk("알 이름이 실려 온다", got[0]["name"] == "전설의 포켓몬 알", got[0])
    chk("받자마자 칭호가 달린다", season.deco(s1[0])["title"] == "시즌 1 챔피언")
    e = eggs.public(s1[0])
    chk("전설의 알이 하나 생겼다", len(e) == 1 and e[0]["kind"] == "legendary", e)
    hall = season.hall(1)
    chk("명예의 전당 10명", len(hall) == 10 and hall[0]["name"] == "s1_00", hall[:1])

    print("\n=== 규칙표 ===")
    rules = season.rules_public()
    chk("티어 여섯 칸", [t["tier"] for t in rules["tiers"]] ==
        ["monster", "super", "hyper", "master", "elite", "champion"])
    chk("보상표: 챔피언은 전설의 알 + 사탕 1",
        rules["rewards"][0]["egg"] == "전설의 포켓몬 알"
        and rules["rewards"][0]["shiny"] == 1, rules["rewards"][0])
    chk("보상표: 사천왕은 환상의 알",
        rules["rewards"][1]["egg"] == "환상의 포켓몬 알", rules["rewards"][1])
    chk("보상표: 사탕은 한 사람에 하나까지",
        all(r["shiny"] <= 1 for r in rules["rewards"]), rules["rewards"])
    chk("보상표: 몬스터볼은 보상 없음",
        "monster" not in [r["tier"] for r in rules["rewards"]])

    print("\n=== 포켓몬 알 ===")
    from app import walk
    eg = mkuser("ss_egg", 4, 20)
    rng = random.Random(4)
    lid = eggs.give(eg, "legendary", rng)
    mid_ = eggs.give(eg, "mythical", rng)
    rows = dict((r["id"], r) for r in db.q("SELECT * FROM egg WHERE user_id=?", (eg,)))
    chk("자리가 있으면 알은 데리고 다닌다 (4마리 + 알 둘)",
        rows[lid]["on_desktop"] == 1 and rows[mid_]["on_desktop"] == 1
        and {rows[lid]["slot"], rows[mid_]["slot"]} == {4, 5},
        [(rows[i]["on_desktop"], rows[i]["slot"]) for i in (lid, mid_)])
    chk("알도 파티 한 자리를 차지한다", deps.party_count(eg) == 6
        and deps.free_slot(eg) is None, deps.party_count(eg))
    third = eggs.give(eg, "legendary", rng)
    chk("파티가 꽉 차면 알은 박스로",
        db.q1("SELECT on_desktop FROM egg WHERE id=?", (third,))["on_desktop"] == 0)
    try:
        eggs.set_desktop(eg, third, True)
        chk("꽉 찼으면 박스 알을 못 올린다", False, "예외가 안 났다")
    except ValueError as e:
        chk("꽉 찼으면 박스 알을 못 올린다", "알까지 합쳐" in str(e), str(e))
    party_mon = db.q1("SELECT id FROM pokemon WHERE user_id=? AND on_desktop=1", (eg,))["id"]
    cid = db.run("INSERT INTO pokemon (user_id, species, level, exp, nature, ivs, evs,"
                 " moves, met_level, caught_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (eg, "PIKACHU", 5, 0, "HARDY", "{}", "{}", "[]", 5, "2026")).lastrowid
    from app import main as _main
    try:
        _main.set_desktop(cid, _main.DesktopIn(on=True), {"user": {"id": eg}})
        chk("알 둘 + 포켓몬 넷이면 포켓몬도 못 올린다", False, "막히지 않았다")
    except HTTPException as e:
        chk("알 둘 + 포켓몬 넷이면 포켓몬도 못 올린다 (409)", e.status_code == 409, e.status_code)
    listed = _main.list_pokemon({"user": {"id": eg}})
    chk("포켓몬 목록에 알이 따로 실린다 (안 깬 셋)",
        sorted(e["id"] for e in listed["eggs"]) == sorted([lid, mid_, third])
        and all("species" not in e for e in listed["eggs"]), listed["eggs"])
    _main.set_order(_main.OrderIn(ids=[-mid_, party_mon]), {"user": {"id": eg}})
    chk("순서 목록의 음수는 알 (알이 맨 앞 자리로)",
        db.q1("SELECT slot FROM egg WHERE id=?", (mid_,))["slot"] == 0, None)
    db.run("UPDATE egg SET slot=5 WHERE id=?", (mid_,))
    db.run("UPDATE pokemon SET slot=0 WHERE id=?", (party_mon,))
    rows = dict((r["id"], r) for r in db.q("SELECT * FROM egg WHERE user_id=?", (eg,)))
    chk("전설의 알 속은 전설 목록에서", rows[lid]["species"] in eggs.pool("legendary"),
        rows[lid]["species"])
    chk("환상의 알 속은 환상 목록에서", rows[mid_]["species"] in eggs.pool("mythical"),
        rows[mid_]["species"])
    chk("이벤트 종은 알에서 안 나온다",
        config.EVENT_SPECIES not in eggs.pool("mythical") + eggs.pool("legendary"))
    chk("목록의 종이 전부 도감에 있다",
        len(eggs.pool("legendary")) == len(eggs.LEGENDARY_POOL)
        and len(eggs.pool("mythical")) >= len(eggs.MYTHICAL_POOL) - 1,
        (len(eggs.pool("legendary")), len(eggs.pool("mythical"))))
    chk("본가의 전설 71종 · 환상 23종 전부",
        len(set(eggs.LEGENDARY_POOL)) == 71 and len(set(eggs.MYTHICAL_POOL)) == 23)
    chk("전설과 환상이 겹치지 않는다",
        not set(eggs.LEGENDARY_POOL) & set(eggs.MYTHICAL_POOL))
    dexd = deps.dex()
    flagged = set(sp["num"] for sp in dexd.species if sp.get("legendary"))
    chk("둘 다 도감에서 전설 표시가 있는 종", set(eggs.LEGENDARY_POOL + eggs.MYTHICAL_POOL)
        <= flagged)
    # 도감의 전설 표시 중 알에 없는 것은 울트라비스트·패러독스뿐이어야 한다.
    # 새 전설이 도감에 들어오면 여기서 빨개진다 - 목록에 넣을지 정하라는 뜻이다.
    rest = sorted(flagged - set(eggs.LEGENDARY_POOL) - set(eggs.MYTHICAL_POOL))
    ub_paradox = set(list(range(793, 800)) + list(range(803, 807))
                     + list(range(984, 996)) + [1005, 1006, 1009, 1010]
                     + list(range(1020, 1024)))
    chk("빠진 것은 울트라비스트 11종 · 패러독스 20종뿐", set(rest) == ub_paradox,
        sorted(set(rest) ^ ub_paradox))
    picks = set(eggs.give_species("legendary", random.Random(k)) for k in range(400))
    chk("여러 번 뽑으면 여러 종이 나온다 (400번에 50종 넘게)", len(picks) > 50, len(picks))
    from common import pokelogic as P
    no_moves = [sp for sp in eggs.pool("legendary") + eggs.pool("mythical")
                if not P.make_pokemon(dexd.get(sp), eggs.HATCH_LEVEL,
                                      random.Random(1))["moves"]]
    chk("어느 종이 태어나도 Lv.5 에 쓸 기술이 있다", not no_moves, no_moves)
    pub = eggs.public(eg)
    chk("화면에 가는 목록에 알 속 종이 없다",
        all("species" not in e and "pokemon" not in e for e in pub), pub)
    chk("전설 48시간 · 환상 36시간",
        [e["needSec"] for e in pub] == [48 * 3600, 36 * 3600, 48 * 3600], pub)

    # 켜 둔 시간: walk.settle 이 20분 단위로 준다. 걸음 시각을 과거로 돌려 흉내 낸다.
    import datetime as DT
    def ago(sec):
        return (DT.datetime.now(DT.timezone.utc) - DT.timedelta(seconds=sec)).isoformat()
    walk.settle(eg)                       # 처음이면 시각만 적는다
    db.run("UPDATE wild_state SET walk_at=? WHERE user_id=?", (ago(3 * 3600), eg))
    walk.settle(eg)
    got = dict((e["id"], e["gotSec"]) for e in eggs.public(eg))
    chk("한 번에 몰아 주는 것은 40분까지 (앱을 꺼 둔 시간은 안 쳐준다)",
        got[lid] == 2 * walk.TICK, got)
    chk("박스에 넣어 둔 알은 안 자란다", got[third] == 0, got)
    chk("아직 부화 안 함", eggs.hatch_ready(eg) == [])
    db.run("UPDATE egg SET got_sec = need_sec - 600 WHERE id=?", (mid_,))
    db.run("UPDATE wild_state SET walk_at=? WHERE user_id=?", (ago(1300), eg))
    walk.settle(eg)
    chk("다 차면 need 에서 멈춘다",
        db.q1("SELECT got_sec, need_sec FROM egg WHERE id=?", (mid_,))["got_sec"]
        == 36 * 3600)
    n_before = db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (eg,))["c"]
    hatched = eggs.hatch_ready(eg, rng)
    chk("다 자란 알만 부화한다", hatched == [mid_], hatched)
    chk("두 번 불러도 한 마리", eggs.hatch_ready(eg, rng) == [] and
        db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (eg,))["c"] == n_before + 1)
    r = db.q1("SELECT * FROM egg WHERE id=?", (mid_,))
    mon = db.row_to_mon(db.q1("SELECT * FROM pokemon WHERE id=?", (r["pokemon_id"],)))
    chk("알에 정해 둔 종이 태어난다", mon["species"] == r["species"], (mon["species"], r["species"]))
    chk("Lv.5 로 태어난다", mon["level"] == eggs.HATCH_LEVEL, mon["level"])
    chk("개체값 셋 이상이 최고", sum(1 for v in mon["ivs"].values() if v == 31) >= 3,
        mon["ivs"])
    chk("친밀도 120 이상", mon["happiness"] >= 120, mon["happiness"])
    chk("알이 있던 자리에서 태어난다 (자리 5)", mon["onDesktop"] and mon["slot"] == 5,
        (mon["onDesktop"], mon["slot"]))
    chk("도감에 잡음으로 오른다", items.has_caught(eg, mon["species"]))
    pub = eggs.public(eg)
    h = [e for e in pub if e["id"] == mid_][0]
    chk("부화한 알은 알릴 때까지 목록에 남고 태어난 포켓몬이 붙는다",
        h["hatched"] and h["pokemon"]["species"] == mon["species"], h)
    chk("알리면 목록에서 빠진다", eggs.mark_announced(eg, mid_)
        and [e["id"] for e in eggs.public(eg)] == [lid, third])
    eggs.set_desktop(eg, lid, False)
    chk("알을 박스에 넣을 수 있다",
        db.q1("SELECT on_desktop, slot FROM egg WHERE id=?", (lid,))["on_desktop"] == 0)
    eggs.set_desktop(eg, third, True)
    chk("자리가 나면 박스 알을 데리고 다닌다",
        db.q1("SELECT on_desktop FROM egg WHERE id=?", (third,))["on_desktop"] == 1)
    chk("안 부화한 알은 알림 표시가 안 된다", not eggs.mark_announced(eg, lid))
    chk("남의 알은 못 건드린다", not eggs.mark_announced(g, mid_))
    free = mkuser("ss_egg_free", 2, 20)
    fid = eggs.give(free, "legendary", rng)
    db.run("UPDATE egg SET got_sec=need_sec WHERE id=?", (fid,))
    eggs.hatch_ready(free, rng)
    pid = db.q1("SELECT pokemon_id FROM egg WHERE id=?", (fid,))["pokemon_id"]
    chk("자리가 있으면 바로 데리고 다닌다",
        db.q1("SELECT on_desktop FROM pokemon WHERE id=?", (pid,))["on_desktop"] == 1)
    db.run("INSERT INTO gift (user_id, kind, item_id, count, title, message,"
           " created_at) VALUES (?,?,?,?,?,?,?)",
           (free, "egg", "nope", 1, "t", "m", "2026-09-15"))
    chk("모르는 알 선물은 지급하지 않는다", items.gift_claim(free) == [])

    print("\n=== 숨은 점수 1000 으로 맞추기 (손질 0280) ===")
    db.run("UPDATE rank_stat SET rating=1404, best=1500, rp=321, peak_rp=400 WHERE user_id=?",
           (strong,))
    before_rows = dict((r["user_id"], (r["rp"], r["peak_rp"], r["wins"], r["losses"], r["streak"]))
                       for r in db.q("SELECT * FROM rank_stat"))
    conn = db.connect()
    note = migrations._mmr_recenter(conn)
    conn.commit()
    print("  (%s)" % note)
    rows = db.q("SELECT * FROM rank_stat")
    chk("모두 숨은 점수 1000", rows and all(r["rating"] == 1000 and r["best"] == 1000 for r in rows),
        [(r["user_id"], r["rating"]) for r in rows if r["rating"] != 1000][:5])
    chk("RP · 최고 RP · 승패 · 연승은 그대로",
        all(before_rows[r["user_id"]] == (r["rp"], r["peak_rp"], r["wins"], r["losses"], r["streak"])
            for r in rows))
    chk("손질 목록에 올라 있다 (0270 뒤)",
        [n for n, _f in migrations.ONCE][-2:] == ["0270-egg-slots", "0280-mmr-recenter"])

    print("\n=== 1.4.0 알에 자리 주기 (손질 0270) ===")
    full = mkuser("ss_egg_old_full", 6, 20)
    roomy = mkuser("ss_egg_old_roomy", 2, 20)
    for u in (full, roomy):
        db.run("INSERT INTO egg (user_id, kind, species, need_sec, got_sec, created_at,"
               " on_desktop, slot) VALUES (?,?,?,?,?,?,1,NULL)",
               (u, "mythical", "MEW", 36 * 3600, 3600, "2026-09-15"))
    conn = db.connect()
    note = migrations._egg_slots(conn)
    conn.commit()
    print("  (%s)" % note)
    ef = db.q1("SELECT on_desktop, slot FROM egg WHERE user_id=?", (full,))
    er = db.q1("SELECT on_desktop, slot FROM egg WHERE user_id=?", (roomy,))
    chk("여섯 마리를 데리고 다니던 사람의 알은 박스로 (포켓몬을 안 내린다)",
        ef["on_desktop"] == 0 and ef["slot"] is None, dict(ef))
    chk("자리가 있으면 빈 자리를 준다", er["on_desktop"] == 1 and er["slot"] == 2, dict(er))
    chk("손질 목록에 올라 있다",
        any(n == "0270-egg-slots" for n, _f in migrations.ONCE))

    # 맨 끝에 둔다 - run() 은 앞의 손질(시즌 전환 등)까지 이 DB 에 전부 돌린다.
    print("\n=== 손질은 run() 으로 한 번만 돈다 (0280) ===")
    # 앞의 손질은 끝났다고 적어 두고 0280 만 돌게 한다 (0190 이 점수를 1000 으로
    # 돌려놓으면 0280 이 안 돌아도 이 검사가 통과해 버린다).
    for n, _f in migrations.ONCE:
        if n != "0280-mmr-recenter":
            db.run("INSERT OR IGNORE INTO meta (k, v) VALUES (?, 'test')", ("mig:" + n,))
    db.run("DELETE FROM meta WHERE k='mig:0280-mmr-recenter'")
    stat(strong)                        # 앞 절(시즌 전환)이 줄을 비웠을 수 있다
    db.run("UPDATE rank_stat SET rating=1234 WHERE user_id=?", (strong,))
    chk("준비: 숨은 점수 1234 인 사람이 있다", stat(strong)["rating"] == 1234, stat(strong)["rating"])
    migrations.run()
    chk("run() 뒤 0280 이 끝났다고 적혀 있다",
        db.q1("SELECT v FROM meta WHERE k='mig:0280-mmr-recenter'") is not None)
    chk("run() 이 숨은 점수를 1000 으로 맞췄다", stat(strong)["rating"] == 1000, stat(strong)["rating"])
    db.run("UPDATE rank_stat SET rating=1234 WHERE user_id=?", (strong,))
    migrations.run()
    chk("다시 켜도(run 한 번 더) 안 돈다", stat(strong)["rating"] == 1234, stat(strong)["rating"])

    print("\n======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
