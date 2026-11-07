# -*- coding: utf-8 -*-
"""포스크탑 올림픽. 서버를 띄우지 않는다.

    python server/test_olympics.py

규칙은 common/olympics.py, 서버는 server/app/olympics.py. 계획: design-notes/2026-11-06-olympics-plan.md

## 무엇을 못 박나

  1. 규칙: 기록 공식이 노력치 · 개체값 · 레벨 · 성격을 안 본다 · 같은 씨앗이면 같은 결과 · 조 나누기 · 일정 · 기록 글
  2. 신청: 신청 기간 밖 거절 · 내 포켓몬만 · 한 마리는 하루 한 종목 · 다시 내면 바뀐다 · 취소 · 탐험 중 거절
  3. 2시 경기: 한 번만 돈다 · 2시 뒤 신청 거절 · 순위 · 조 · 참가 리본 · 다음 날 지침
  4. 조 각본 · 순위표: 공개 전에는 순위표가 비어 있다 · 주간 최고 · 동점은 먼저 낸 쪽
  5. 폐막: 메달 칭호 · 리본 · 볼은 두 번 돌려도 한 번 · 종족 1위 리본
"""
import datetime
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-oly-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
for k in ("POKET_OLYMPICS_DAYS", "POKET_OLYMPICS_OPEN", "POKET_OLYMPICS_AT"):
    os.environ.pop(k, None)

from fastapi import HTTPException                            # noqa: E402

from common import olympics as O                             # noqa: E402
from common import pokelogic as P                            # noqa: E402
from app import achievements, db, deps, season               # noqa: E402
from app import olympics as OL                               # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc
D1, D2, D3 = O.DAYS[0], O.DAYS[1], O.DAYS[2]


def kst(day, h, mi=0, s=0):
    y, mo, d = int(day[0:4]), int(day[5:7]), int(day[8:10])
    return datetime.datetime(y, mo, d, h, mi, s, tzinfo=O.KST).astimezone(UTC)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


_n = [0]


def mkuser(name=None):
    _n[0] += 1
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'2026-10-01T00:00:00+00:00','','')",
        (name or "선수%d" % _n[0], b"x", b"x"))
    return cur.lastrowid


def mkmon(uid, species="PIKACHU", level=30, seed=3):
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(seed), shiny_rate=10 ** 9)
    m["evs"] = dict((s, 0) for s in P.STATS)
    return db.insert_mon(uid, m, "")


def refused(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except HTTPException as e:
        return e.status_code, str(e.detail)
    return None


def balls(uid):
    return db.q1("SELECT balls FROM users WHERE id=?", (uid,))["balls"]


def ribbons(pid):
    return sorted((r["kind"], r["event"]) for r in db.q(
        "SELECT kind, event FROM pokemon_ribbon WHERE pokemon_id=?", (pid,)))


# ---------------------------------------------------------------- 1. 규칙
def rules_part():
    print("\n[규칙]")
    dex = deps.dex()
    pct = O.build_pct(dex.species)
    sp = dex.get("PIKACHU")
    a = O.play("sprint", sp, "STATIC", "safe", pct, seed=77)
    b = O.play("sprint", sp, "STATIC", "safe", pct, seed=77)
    chk("같은 씨앗이면 같은 결과", a == b, (a, b))
    chk("공식은 종 · 특성 · 작전 · 응원 · 지침만 받는다 (노력치 · 개체값 칸이 없다)",
        O.play.__code__.co_varnames[:8] == ("event", "sp", "ability", "tactic", "pct", "cheer", "fatigue", "seed"))
    m = O.mods("sprint", sp, "STATIC", pct)
    chk("피카츄 100m: 전기 특기 +5%", m.get("type") == O.TYPE_B, m)
    m2 = O.mods("sprint", sp, "STATIC", pct, cheer=("ELECTRIC", "GHOST"))
    chk("응원 타입이면 +5%", abs(sum(m2.values()) - sum(m.values()) - O.CHEER_B) < 1e-9, m2)
    snor = O.mods("lift", dex.get("SNORLAX"), "THICKFAT", pct)
    chk("잠만보(460kg)도 역도 체형은 +4% 를 못 넘는다", snor["body"] <= O.BODY, snor)
    regi = O.mods("sprint", dex.get("REGIELEKI"), "TRANSISTOR", pct)
    drag = O.mods("sprint", dex.get("DRAGAPULT"), "CLEARBODY", pct)
    chk("적성 차이: 스피드 200 과 142 의 차이가 0.5% 안", abs(regi["apt"] - drag["apt"]) < 0.005, (regi, drag))
    swim = O.mods("swim", dex.get("CHARMANDER"), "BLAZE", pct)
    chk("수영: 불꽃은 물 싫어함 -3%", swim.get("dislike") == -O.DISLIKE, swim)
    chk("기록 글", (O.text("sprint", 11.84), O.text("marathon", 7395), O.text("lift", 163), O.text("ski", 121.5),
                 O.text("pole", None)) == ("11.84초", "2:03:15", "163kg", "121.5m", "기록 없음"))
    chk("낮을수록 좋은 기록 / 높을수록", O.better("sprint", 11.0, 12.0) and O.better("pole", 5.5, 5.0)
        and not O.better("pole", None, 4.0))
    hs = O.heats(list(range(19)), 5)
    chk("조: 19명 -> 3조, 크기 차이 1 이하", len(hs) == 3 and max(map(len, hs)) - min(map(len, hs)) <= 1
        and sorted(sum(hs, [])) == list(range(19)), hs)
    chk("조: 같은 씨앗이면 같은 조", O.heats(list(range(19)), 5) == hs)
    fm = O.fatigue_map({"PIKACHU": 10, "EEVEE": 1, "X": 89})
    chk("지침: 몫 10% 면 -5%, 1% 면 -1%", fm["PIKACHU"] == 0.05 and fm["EEVEE"] == 0.01, fm)
    cur = O.race_curve(9, "sprint", slip_at=0.5)
    chk("달리기 곡선: 0 에서 1 까지 늘기만", cur[0] == (0.0, 0.0) and cur[-1] == (1.0, 1.0)
        and all(b[0] >= a[0] and b[1] >= a[1] for a, b in zip(cur, cur[1:])), cur)
    chk("일정: 첫 날 신청은 11/15 0시부터", O.entry_day(kst("2026-11-15", 0, 0, 1)) == D1
        and O.entry_day(kst("2026-11-14", 23, 59)) is None)
    chk("일정: 14:00 에는 신청이 닫히고 중계", O.entry_day(kst(D1, 14)) is None and O.live_day(kst(D1, 14)) == D1
        and O.entry_day(kst(D1, 13, 59, 59)) == D1)
    chk("일정: 중계가 끝나면 다음 날 신청", O.entry_day(O.end_at(D1)) == D2 and O.live_day(O.end_at(D1)) is None)
    chk("일정: 금요일 경기 뒤 다음 경기는 월요일", O.DAYS[4] == "2026-11-20" and O.DAYS[5] == "2026-11-23"
        and O.entry_day(kst("2026-11-21", 12)) == "2026-11-23")
    chk("일정: 마지막 날 뒤 done -> 일주일 뒤 closed",
        O.phase(O.end_at(O.DAYS[-1])) == "done" and O.phase(kst("2026-12-02", 0)) == "closed")
    chk("응원 타입은 날마다 둘", all(len(O.cheer_of(d)) == 2 for d in O.DAYS))


# ---------------------------------------------------------------- 2. 신청
def entry_part():
    print("\n[신청]")
    u = mkuser("신청이")
    p1, p2 = mkmon(u, "PIKACHU"), mkmon(u, "MACHAMP")
    other = mkmon(mkuser(), "EEVEE")
    t = kst(D1, 10)
    chk("개막 전 거절", (refused(OL.enter, u, "sprint", p1, "safe", now=kst("2026-11-14", 12)) or [0])[0] == 409)
    chk("남의 포켓몬 거절", (refused(OL.enter, u, "sprint", other, "safe", now=t) or [0])[0] == 404)
    chk("없는 종목 · 작전 거절", (refused(OL.enter, u, "golf", p1, "safe", now=t) or [0])[0] == 400
        and (refused(OL.enter, u, "sprint", p1, "yolo", now=t) or [0])[0] == 400)
    r = OL.enter(u, "sprint", p1, "safe", now=t)
    chk("신청", r["entry"]["pokemon"]["id"] == p1 and r["entry"]["tactic"] == "safe", r)
    chk("한 마리는 하루 한 종목", (refused(OL.enter, u, "swim", p1, "safe", now=t) or [0, ""])[1].startswith("이 포켓몬은"),
        refused(OL.enter, u, "swim", p1, "safe", now=t))
    OL.enter(u, "sprint", p2, "bold", now=t)
    row = db.q("SELECT pokemon_id, tactic FROM olympic_entry WHERE user_id=? AND day=?", (u, D1))
    chk("같은 종목에 다시 내면 바뀐다 (한 줄)", len(row) == 1 and row[0]["pokemon_id"] == p2
        and row[0]["tactic"] == "bold", [dict(x) for x in row])
    OL.enter(u, "swim", p1, "safe", now=t)
    chk("바꾼 뒤에는 처음 포켓몬을 다른 종목에", db.q1("SELECT COUNT(*) c FROM olympic_entry WHERE user_id=?", (u,))["c"] == 2)
    OL.cancel(u, "swim", now=t)
    chk("취소", db.q1("SELECT COUNT(*) c FROM olympic_entry WHERE user_id=?", (u,))["c"] == 1)
    db.run("INSERT INTO expedition (user_id, pokemon_id, place, hours, grade, started_at, ends_at, state)"
           " VALUES (?,?,'forest',1,'C','','','out')", (u, p1))
    chk("탐험 중인 포켓몬 거절", (refused(OL.enter, u, "swim", p1, "safe", now=t) or [0])[0] == 409)
    db.run("DELETE FROM expedition WHERE user_id=?", (u,))
    st = OL.state(u, now=t)
    ev = dict((e["key"], e) for e in st["events"])
    chk("상태: 신청 중 · 내 신청이 보인다", st["phase"] == "entry" and ev["sprint"]["entry"]["pokemon"]["id"] == p2
        and ev["swim"]["entry"] is None, st["phase"])
    cands = OL.candidates(u, "sprint", now=t)["pokemon"]
    chk("후보: 내 포켓몬마다 별과 표시", len(cands) == 2 and all(1 <= c["stars"] <= 5 and c["hints"] for c in cands), cands)
    pk = [c for c in cands if c["id"] == p1][0]
    chk("후보: 피카츄는 '전기 특기'", "전기 특기" in pk["hints"], pk["hints"])
    db.run("DELETE FROM olympic_entry")


# ---------------------------------------------------------------- 3. 2시 경기
def run_part():
    print("\n[2시 경기]")
    us = [mkuser() for _ in range(11)]
    mons = {}
    t = kst(D1, 11)
    for i, u in enumerate(us):
        a = mkmon(u, "PIKACHU", seed=i)
        b = mkmon(u, "MACHAMP", level=5 + i, seed=i)
        mons[u] = (a, b)
        OL.enter(u, "sprint", a, "safe" if i % 2 else "bold", now=t)
        OL.enter(u, "lift", b, "safe", now=t)
    late = mkuser()
    lm = mkmon(late)
    OL.ensure_ran(kst(D1, 13, 59))
    chk("2시 전에는 경기를 안 한다", db.q1("SELECT COUNT(*) c FROM olympic_day")["c"] == 0)
    OL.ensure_ran(kst(D1, 14, 0, 1))
    rows = db.q("SELECT * FROM olympic_entry WHERE day=? AND event='sprint' ORDER BY rank", (D1,))
    chk("100m: 11명 모두 기록 · 순위 1..11", [r["rank"] for r in rows] == list(range(1, 12))
        and all(r["record"] for r in rows), [(r["rank"], r["record"]) for r in rows])
    chk("순위는 기록 차례", all(r1["record"] <= r2["record"] for r1, r2 in zip(rows, rows[1:])))
    chk("조: 11명 -> 2조 (6 · 5)", sorted(collections_count(r["heat"] for r in rows).values()) == [5, 6])
    before = [tuple(r) for r in db.q("SELECT id, record, rank FROM olympic_entry ORDER BY id")]
    OL._ran.clear()
    OL.ensure_ran(kst(D1, 14, 3))
    after = [tuple(r) for r in db.q("SELECT id, record, rank FROM olympic_entry ORDER BY id")]
    chk("두 번 돌려도 한 번 (결과 그대로)", before == after)
    chk("2시 뒤 신청 거절", (refused(OL.enter, late, "sprint", lm, "safe", now=kst(D1, 14, 0, 2)) or [0])[0] == 409)
    chk("참가 리본", ("oly_join", "") in ribbons(mons[us[0]][0]), ribbons(mons[us[0]][0]))
    lifts = db.q("SELECT * FROM olympic_entry WHERE day=? AND event='lift'", (D1,))
    det = json.loads(lifts[0]["detail"])
    chk("역도: 세 번 시기 · 최고가 기록", len(det["tries"]) == 3
        and lifts[0]["record"] == O.best_of("lift", [x["v"] for x in det["tries"]]), det)
    # 레벨이 다 달라도(5..15) 같은 종 · 특성 · 작전이면 기대 점수(mods)가 같다
    same = set(json.dumps(json.loads(r["detail"])["mods"], sort_keys=True) for r in lifts
               if r["ability"] == lifts[0]["ability"])
    chk("레벨 · 개체값 · 노력치가 달라도 mods 가 같다", len(same) == 1, same)
    # 다음 날: 100m 출전자 100% 가 피카츄 -> 피카츄는 지친다
    t2 = O.end_at(D1) + datetime.timedelta(minutes=5)
    u0 = us[0]
    OL.enter(u0, "sprint", mons[u0][0], "safe", now=t2)
    c = [x for x in OL.candidates(u0, "sprint", now=t2)["pokemon"] if x["id"] == mons[u0][0]][0]
    chk("다음 날: 지침 -5% 가 보인다", "지침 −5%" in c["hints"], c["hints"])
    st = OL.state(u0, now=t2)
    chk("상태: 지친 포켓몬 목록", any(f["species"] == "피카츄" for f in st["fatigue"].get("sprint", [])),
        st["fatigue"])
    return us, mons


def collections_count(it):
    out = {}
    for x in it:
        out[x] = out.get(x, 0) + 1
    return out


# ---------------------------------------------------------------- 4. 각본 · 순위표
def board_part(us, mons):
    print("\n[조 각본 · 순위표]")
    u = us[0]
    e = db.q1("SELECT * FROM olympic_entry WHERE user_id=? AND day=? AND event='sprint'", (u, D1))
    h = OL.heat(u, e["id"], now=kst(D1, 14, 0, 30))
    chk("조 각본: 같은 조 사람 모두 · 내 줄 표시", len(h["entrants"]) == db.q1(
        "SELECT COUNT(*) c FROM olympic_entry WHERE day=? AND event='sprint' AND heat=?", (D1, e["heat"]))["c"]
        and sum(1 for x in h["entrants"] if x["mine"]) == 1, h)
    chk("조 각본: 기록 글 · 씨앗 · 시기", all(x["text"] and "seed" in x and x["tries"] for x in h["entrants"]))
    chk("조 각본: 공개 전에는 전체 순위를 안 싣는다 (다른 조 결과가 새지 않게)",
        all(x["rank"] is None for x in h["entrants"]), [x["rank"] for x in h["entrants"]])
    h2 = OL.heat(u, e["id"], now=O.release_at(D1, "sprint"))
    chk("조 각본: 공개 뒤에는 전체 순위", all(x["rank"] for x in h2["entrants"]))
    other = db.q1("SELECT * FROM olympic_entry WHERE heat<>? AND day=? AND event='sprint'", (e["heat"], D1))
    chk("남의 조는 공개 전에는 못 본다", (refused(OL.heat, u, other["id"], now=kst(D1, 14, 0, 30)) or [0])[0] == 403)
    chk("공개 뒤에는 본다", OL.heat(u, other["id"], now=O.release_at(D1, "sprint"))["event"] == "sprint")
    st0 = dict((x["key"], x) for x in OL.state(u, now=kst(D1, 14, 0, 30))["events"])["sprint"]["last"]
    chk("중계 전에는 창에도 내 기록이 안 보인다", st0["text"] is None and not st0["released"], st0)
    st1 = dict((x["key"], x) for x in OL.state(u, now=O.release_at(D1, "sprint"))["events"])["sprint"]["last"]
    chk("중계 뒤에는 보인다", st1["text"] and st1["released"] and st1["rank"], st1)
    b0 = OL.board(u, "sprint", day=D1, now=kst(D1, 14, 0, 30))
    chk("공개 전 순위표는 비어 있다", b0["rows"] == [] and b0["hidden"], b0)
    b1 = OL.board(u, "sprint", day=D1, now=O.release_at(D1, "sprint"))
    chk("공개 뒤 순위표", len(b1["rows"]) == 11 and b1["rows"][0]["rank"] == 1 and b1["me"], b1["me"])
    # 둘째 날: us[1] 이 더 좋은 기록을 내면 주간 순위표에는 그 사람의 최고만 한 줄
    t2 = O.end_at(D1) + datetime.timedelta(minutes=5)
    u1 = us[1]
    OL.enter(u1, "sprint", mons[u1][0], "safe", now=t2)
    OL.ensure_ran(kst(D2, 14, 0, 1))
    wk = OL.board(u1, "sprint", now=kst(D2, 15))
    users = [r["user"] for r in wk["rows"]]
    chk("주간 순위표: 사람마다 한 줄", len(users) == len(set(users)) == 11, users)
    best1 = min(r["record"] for r in db.q("SELECT record FROM olympic_entry WHERE user_id=? AND event='sprint'", (u1,)))
    mine = [r for r in wk["rows"] if r["user"] == db.q1("SELECT username FROM users WHERE id=?", (u1,))["username"]][0]
    chk("주간 순위표: 그 사람의 최고 기록", abs(mine["record"] - best1) < 1e-9, (mine, best1))
    # 닉네임을 바꾸면 순위표에도 새 이름 (닉네임 변경권 - 순위 캐시에 옛 이름이 남지 않게)
    old = db.q1("SELECT username FROM users WHERE id=?", (u1,))["username"]
    db.run("UPDATE users SET username=? WHERE id=?", ("새이름", u1))
    names = [r["user"] for r in OL.board(u1, "sprint", now=kst(D2, 15))["rows"]]
    chk("닉네임을 바꾸면 순위표에도 새 이름", "새이름" in names and old not in names, names)
    db.run("UPDATE users SET username=? WHERE id=?", (old, u1))
    # 동점: 기록이 같으면 먼저 낸 쪽이 앞
    a, b = mkuser("동점가"), mkuser("동점나")
    for uid, at in ((b, kst(D3, 9)), (a, kst(D3, 10))):
        OL.enter(uid, "pole", mkmon(uid, "HERACROSS"), "safe", now=at)
    OL.ensure_ran(kst(D3, 14, 0, 1))
    db.run("UPDATE olympic_entry SET record=5.55 WHERE day=? AND event='pole'", (D3,))
    OL._boards_cache.clear()
    rows = OL.board(a, "pole", now=O.end_at(D3))["rows"]
    chk("동점은 먼저 낸 쪽이 앞 (주간)", [r["user"] for r in rows] == ["동점나", "동점가"], rows)


# ---------------------------------------------------------------- 5. 폐막
def close_part(us, mons):
    print("\n[폐막]")
    end = O.end_at(O.DAYS[-1]) + datetime.timedelta(seconds=1)
    # 종족 1위: 같은 종을 낸 사람이 셋이면 리본 - 시기 셋을 다 파울한 사람도 '낸 사람' 이다 (기획)
    D4 = O.DAYS[3]
    trio = [mkuser("눈여아%d" % i) for i in range(3)]
    for i, uid in enumerate(trio):
        OL.enter(uid, "ski", mkmon(uid, "FROSLASS"), "safe", now=kst(D4, 9 + i))
    OL.ensure_ran(kst(D4, 14, 0, 1))
    for uid, rec in zip(trio, (115.0, 112.0, None)):
        db.run("UPDATE olympic_entry SET record=? WHERE user_id=? AND event='ski'", (rec, uid))
    OL._boards_cache.clear()
    winners = [r["user_id"] for r, _k in OL._weekly("sprint", end)[:3]]     # board() 는 정산까지 부른다 - 그 전에 잰다
    b0 = dict((w, balls(w)) for w in winners)
    # 정산 도중 칭호 주기가 한 번 실패해도 (DB 잠김 등) 다시 돌리면 볼까지 다 받는다
    real_grant, boom = season.grant, [True]

    def grant_once_fails(*a, **kw):
        if boom[0]:
            boom[0] = False
            raise RuntimeError("database is locked")
        return real_grant(*a, **kw)
    season.grant = grant_once_fails
    try:
        OL.ensure_ran(end)                         # 마지막 날을 치르고 폐막 정산 - 첫 칭호에서 터진다
    except RuntimeError:
        pass
    season.grant = real_grant
    OL.ensure_ran(end)                             # 다시
    b1 = dict((w, balls(w)) for w in winners)
    OL._closed[0] = False
    OL.close(end)                                  # 두 번째
    OL.ensure_ran(end)
    g = winners[0]
    chk("금메달: 종목 칭호", db.q1("SELECT 1 FROM user_reward WHERE user_id=? AND kind='title' AND rid='oly_gold_sprint'",
                               (g,)) is not None)
    chk("칭호 이름이 등록돼 있다", season.TITLES.get("oly_gold_sprint") == "올림픽 100m 금메달")
    chk("메달 볼 (금 +20 · 은 +15 · 동 +10 이상 - 다른 종목 몫이 더해질 수 있다)",
        all(b1[w] - b0[w] >= n for w, n in zip(winners, (20, 15, 10))), [b1[w] - b0[w] for w in winners])
    chk("정산을 두 번 돌려도 볼은 한 번", all(balls(w) == b1[w] for w in winners))
    pid = db.q1("SELECT pokemon_id FROM olympic_final WHERE event='sprint' AND rank=1")["pokemon_id"]
    chk("금메달 리본은 그 기록을 낸 포켓몬에", ("oly_gold", "sprint") in ribbons(pid), ribbons(pid))
    chk("4~8위는 결선 진출", db.q1("SELECT COUNT(*) c FROM user_reward WHERE rid='oly_final'")["c"] >= 5)
    # 100m 출전 피카츄가 11명 -> 피카츄 중 1위에게 종족 1위 리본 (금메달과 같은 포켓몬일 수 있다)
    chk("종족 1위 리본", db.q1("SELECT COUNT(*) c FROM pokemon_ribbon WHERE kind='oly_species' AND event='sprint'")["c"] == 1)
    chk("종족 1위: 다 파울한 사람도 셋에 든다", db.q1(
        "SELECT COUNT(*) c FROM pokemon_ribbon WHERE kind='oly_species' AND event='ski' AND user_id=?",
        (trio[0],))["c"] == 1)
    st = OL.state(g, now=end)
    chk("상태: 다 끝남 · 메달 표", st["phase"] == "done" and st["medals"]["sprint"][0]["rank"] == 1
        and any(m["event"] == "sprint" for m in st["myMedals"]), st["myMedals"])
    # 업적: 첫 출전 · 7종목 · 7일 개근 · 종족 1위
    keys = set(a["key"] for a in achievements.defs())
    chk("올림픽 업적 넷", {"oly_first", "oly_all7", "oly_days7", "oly_species"} <= keys)
    achievements.check(us[0])
    got = set(r["key"] for r in db.q("SELECT key FROM achievement WHERE user_id=?", (us[0],)))
    chk("첫 출전 업적", "oly_first" in got, got)


def empty_part():
    print("\n[일정이 비었을 때]")
    old = O.DAYS
    O.DAYS = ()
    try:
        u = mkuser()
        got = OL.me_card(u)
        chk("경기 날을 비워 두면 /api/me 는 그냥 None (500 이 아니다)", got is None, got)
        st = OL.state(u)
        chk("올림픽 창도 깨지지 않는다", st["phase"] == "before" and st["openIn"] is None, st.get("phase"))
    except Exception as e:                                   # noqa: BLE001
        chk("경기 날을 비워 두면 /api/me 는 그냥 None (500 이 아니다)", False, repr(e))
    finally:
        O.DAYS = old


def main_():
    db.init()
    rules_part()
    entry_part()
    us, mons = run_part()
    board_part(us, mons)
    close_part(us, mons)
    empty_part()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
