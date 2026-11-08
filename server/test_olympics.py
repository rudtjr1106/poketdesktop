# -*- coding: utf-8 -*-
"""포스크탑 올림픽. 서버를 띄우지 않는다.

    python server/test_olympics.py

규칙은 common/olympics.py, 서버는 server/app/olympics.py. 계획: design-notes/2026-11-06-olympics-plan.md

## 무엇을 못 박나 (하루 한 종목 · 라운드 - design-notes/2026-11-08-olympics-rounds.md)

  1. 규칙: 기록 공식이 노력치 · 개체값 · 레벨 · 성격을 안 본다 · 같은 씨앗이면 같은 결과 · 기록 글
  2. 신청: 11/15 부터 일곱 종목 · 종목마다 그 날 14:00 에 닫힘 · 같은 포켓몬 여러 종목 · 다시 내면 바뀐다 · 취소 ·
     탐험 중 거절 · 지침 = 그 종목 신청자 중 같은 종 몫
  3. 경기 치르기: 그날 종목만 · 한 번만 · 라운드 · 조 줄 · 순위 · 참가 리본 · 신청 0 인 날
  4. 공개 · 각본: 내 조 + 결승 중계 · 진출(Q/q) 은 다음 라운드 시작 때 · 남의 조는 공개 뒤 · 최종 순위는 그날 끝
  5. 정산: 그 종목 중계가 끝나면 · 메달 칭호 · 리본 · 볼은 두 번 돌려도 한 번 · 종족 1위 리본
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
D1, D2, D3 = O.DAYS[0], O.DAYS[1], O.DAYS[2]          # 100m · 봅슬레이 · 장대


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
    snor = O.mods("bobsled", dex.get("SNORLAX"), "THICKFAT", pct)
    chk("잠만보(460kg)도 봅슬레이 체형은 +4% 를 못 넘는다", snor["body"] <= O.BODY, snor)
    regi = O.mods("sprint", dex.get("REGIELEKI"), "TRANSISTOR", pct)
    drag = O.mods("sprint", dex.get("DRAGAPULT"), "CLEARBODY", pct)
    chk("적성 차이: 스피드 200 과 142 의 차이가 0.5% 안", abs(regi["apt"] - drag["apt"]) < 0.005, (regi, drag))
    chk("종목 일곱 (11/07 사용자 결정)", O.KEYS == ("sprint", "bobsled", "pole", "archery", "discus", "ski", "marathon"))
    owl = O.mods("archery", dex.get("DECIDUEYE"), "KEENEYE", pct)
    chk("모크나이퍼 양궁: 고스트 특기 +5% · 날카로운눈 +3%", owl.get("type") == O.TYPE_B and owl.get("abil") == O.ABIL_B, owl)
    chk("기록 글", (O.text("sprint", 11.84), O.text("marathon", 7395), O.text("bobsled", 49.87), O.text("ski", 121.5),
                 O.text("pole", None)) == ("11.84초", "2:03:15", "49.87초", "121.5m", "기록 없음"))
    fm = O.fatigue_map({"PIKACHU": 10, "EEVEE": 1, "X": 89})
    chk("지침: 몫 10% 면 -5%, 1% 면 -1%", fm["PIKACHU"] == 0.05 and fm["EEVEE"] == 0.01, fm)


# ---------------------------------------------------------------- 2. 신청
def entry_part():
    print("\n[신청]")
    u = mkuser("신청이")
    p1, p2 = mkmon(u, "PIKACHU"), mkmon(u, "MACHAMP")
    other = mkmon(mkuser(), "EEVEE")
    t = kst("2026-11-15", 10)
    chk("11/15 전에는 거절", (refused(OL.enter, u, "sprint", p1, "safe", now=kst("2026-11-14", 12)) or [0])[0] == 409)
    chk("남의 포켓몬 거절", (refused(OL.enter, u, "sprint", other, "safe", now=t) or [0])[0] == 404)
    chk("없는 종목 · 작전 거절", (refused(OL.enter, u, "golf", p1, "safe", now=t) or [0])[0] == 400
        and (refused(OL.enter, u, "sprint", p1, "yolo", now=t) or [0])[0] == 400)
    r = OL.enter(u, "sprint", p1, "safe", now=t)
    chk("신청 (날 = 그 종목 날)", r["entry"]["pokemon"]["id"] == p1 and r["day"] == D1, r)
    r2 = OL.enter(u, "bobsled", p1, "bold", now=t)
    chk("같은 포켓몬을 다른 종목에도 (11/08)", r2["day"] == D2 and r2["entry"]["pokemon"]["id"] == p1, r2)
    OL.enter(u, "sprint", p2, "bold", now=t)
    row = db.q("SELECT pokemon_id, tactic FROM olympic_entry WHERE user_id=? AND event='sprint'", (u,))
    chk("같은 종목에 다시 내면 바뀐다 (한 줄)", len(row) == 1 and row[0]["pokemon_id"] == p2 and row[0]["tactic"] == "bold",
        [dict(x) for x in row])
    OL.cancel(u, "bobsled", now=t)
    chk("취소", db.q1("SELECT COUNT(*) c FROM olympic_entry WHERE user_id=?", (u,))["c"] == 1)
    db.run("INSERT INTO expedition (user_id, pokemon_id, place, hours, grade, started_at, ends_at, state)"
           " VALUES (?,?,'forest',1,'C','','','out')", (u, p1))
    chk("탐험 중인 포켓몬 거절", (refused(OL.enter, u, "bobsled", p1, "safe", now=t) or [0])[0] == 409)
    db.run("DELETE FROM expedition WHERE user_id=?", (u,))
    chk("그 종목 날 14:00 뒤에는 거절", (refused(OL.enter, u, "sprint", p1, "safe", now=kst(D1, 14, 0, 1)) or [0])[0] == 409)
    chk("  뒷날 종목은 그때도 받는다", OL.enter(u, "ski", p1, "safe", now=kst(D1, 14, 0, 1))["day"] == O.day_of("ski"))
    chk("  취소도 그 종목 날 14:00 뒤에는 안 된다", (refused(OL.cancel, u, "sprint", now=kst(D1, 14, 0, 1)) or [0])[0] == 409)
    st = OL.state(u, now=t)
    ev = dict((e["key"], e) for e in st["events"])
    chk("상태: 일곱 종목 줄 · 날 · 신청 중 · 내 신청", st["phase"] == "entry" and len(st["events"]) == 7
        and ev["sprint"]["day"] == D1 and ev["sprint"]["status"] == "entry" and ev["sprint"]["canEnter"]
        and ev["sprint"]["entry"]["pokemon"]["id"] == p2 and ev["bobsled"]["entry"] is None, ev["sprint"])
    chk("상태: 종목마다 응원 타입", [c["type"] for c in ev["sprint"]["cheer"]] == ["FAIRY", "WATER"], ev["sprint"]["cheer"])
    # 지침: 그 종목 신청자 4명 중 3명이 피카츄 -> 피카츄 -5%
    for i in range(3):
        x = mkuser("피카%d" % i)
        OL.enter(x, "pole", mkmon(x, "PIKACHU", seed=10 + i), "safe", now=t)
    y = mkuser("헤라")
    OL.enter(y, "pole", mkmon(y, "HERACROSS"), "safe", now=t)
    cands = OL.candidates(u, "pole", now=t)
    pk = [c for c in cands["pokemon"] if c["id"] == p1][0]
    chk("후보: 내 포켓몬마다 별과 표시", all(1 <= c["stars"] <= 5 and c["hints"] for c in cands["pokemon"]), cands["pokemon"])
    chk("후보: 지침 = 지금 그 종목 신청자 중 같은 종 몫 (피카츄 75% -> −5%)", "지침 −5%" in pk["hints"], pk["hints"])
    chk("후보: 지금 몫 상위 (피카츄 75%)", cands["share"] and cands["share"][0]["species"] == "피카츄"
        and cands["share"][0]["pct"] == 75, cands.get("share"))
    db.run("DELETE FROM olympic_entry")


# ---------------------------------------------------------------- 3. 경기 치르기
BALLS0 = {}                 # 경기 직후 볼 (정산 전)
SPECIES = ("PIKACHU", "RAICHU", "JOLTEON", "ZERAORA", "ARCANINE", "RAPIDASH", "PIKACHU", "ELECTRODE")


def run_part():
    print("\n[경기 치르기]")
    us, mons = [], {}
    for i in range(30):
        u = mkuser("달려%02d" % i)
        m = mkmon(u, SPECIES[i % len(SPECIES)], seed=i)
        us.append(u)
        mons[u] = m
        OL.enter(u, "sprint", m, "safe" if i % 2 else "bold", now=kst("2026-11-15", 9) + datetime.timedelta(minutes=i))
    late = mkuser("늦음")
    lm = mkmon(late)
    OL.ensure_ran(kst(D1, 13, 59))
    chk("14:00 전에는 경기를 안 한다", db.q1("SELECT COUNT(*) c FROM olympic_day")["c"] == 0)
    OL.ensure_ran(kst(D1, 14, 0, 1))
    day = db.q1("SELECT * FROM olympic_day WHERE day=?", (D1,))
    chk("그날 종목 하나 (100m) 를 치렀다", day is not None and day["event"] == "sprint" and day["n"] == 30, dict(day or {}))
    info = OL.day_info(D1)
    chk("시각표: 30명 -> 예선 · 준결승 · 결승", [r["key"] for r in info["rounds"]] == ["r1", "semi", "final"]
        and len(info["program"]) == 3 and info["end"] > 0, info)
    heats = db.q("SELECT round, heat FROM olympic_heat WHERE event='sprint' ORDER BY round, heat")
    chk("조 줄: 예선 4조 · 준결승 3조 · 결승 1조", [r["round"] for r in heats] == [1] * 4 + [2] * 3 + [3],
        [(r["round"], r["heat"]) for r in heats])
    rows = db.q("SELECT * FROM olympic_entry WHERE event='sprint' ORDER BY rank")
    chk("순위 1..30 · 기록 · 간 라운드", [r["rank"] for r in rows] == list(range(1, 31)) and all(r["record"] for r in rows)
        and [r["reached"] for r in rows[:8]] == [3] * 8 and rows[-1]["reached"] == 1, [(r["rank"], r["reached"]) for r in rows])
    before = [tuple(r) for r in db.q("SELECT id, record, rank FROM olympic_entry ORDER BY id")]
    OL._ran.clear()
    OL.ensure_ran(kst(D1, 14, 3))
    after = [tuple(r) for r in db.q("SELECT id, record, rank FROM olympic_entry ORDER BY id")]
    chk("두 번 돌려도 한 번", before == after and db.q1("SELECT COUNT(*) c FROM olympic_heat")["c"] == len(heats))
    chk("14:00 뒤 그 종목 신청 거절", (refused(OL.enter, late, "sprint", lm, "safe", now=kst(D1, 14, 0, 2)) or [0])[0] == 409)
    chk("참가 리본", ("oly_join", "") in ribbons(mons[us[0]]), ribbons(mons[us[0]]))
    return us, mons


# ---------------------------------------------------------------- 4. 공개 · 각본
def reveal_part(us, mons):
    print("\n[공개 · 각본]")
    info = OL.day_info(D1)
    prog = info["program"]
    at = lambda sec: O.start_at(D1) + datetime.timedelta(seconds=sec)          # noqa: E731
    champ = db.q1("SELECT user_id FROM olympic_entry WHERE event='sprint' AND rank=1")["user_id"]
    out = db.q1("SELECT user_id, id FROM olympic_entry WHERE event='sprint' AND reached=1")
    lv = OL.live(champ, now=at(5))
    chk("중계: 시각표 셋 (예선 · 준결승 · 결승) · 첫 라운드 내 조 각본", [p["round"] for p in lv["program"]] == [1, 2, 3]
        and lv["program"][-1]["medal"] and lv["first"] and lv["first"]["round"]["no"] == 1
        and [p["showIn"] for p in lv["program"]] == sorted(p["showIn"] for p in lv["program"]), lv["program"])
    chk("  2라운드 각본은 앞 라운드 중계가 끝나기 전에는 안 준다 (진출이 먼저 드러나지 않게)",
        (refused(OL.show, champ, 2, now=at(30)) or [0])[0] == 409)
    s2 = OL.show(champ, 2, now=at(prog[1]["at"] - 5))
    s3 = OL.show(champ, 3, now=at(prog[2]["at"] - 5))
    chk("중계: 결승까지 간 사람은 준결승 · 결승 내 조", s2["script"]["round"]["no"] == 2 and s3["script"]["round"]["no"] == 3
        and any(e["mine"] for e in s3["script"]["entrants"]))
    o2 = OL.show(out["user_id"], 2, now=at(prog[1]["at"] - 5))
    o3 = OL.show(out["user_id"], 3, now=at(prog[2]["at"] - 5))
    chk("중계: 예선에서 떨어진 사람은 준결승 없이 결승만", o2["script"] is None and o3["script"]["round"]["kr"] == "결승"
        and not any(e["mine"] for e in o3["script"]["entrants"]), (o2, o3["script"] and o3["script"]["round"]))
    watcher = mkuser("구경꾼")
    chk("중계: 신청 안 한 사람은 없음", OL.live(watcher, now=at(5))["first"] is None
        and OL.show(watcher, 3, now=at(prog[2]["at"]))["script"] is None)
    lv2 = OL.live(out["user_id"], now=at(5))
    sc = lv2["first"]
    chk("각본: 형식 · 라운드 · 조 · 출전자(레인 · 결과 · 기록 글)", sc["format"] == "race" and sc["round"]["kr"] == "예선"
        and sc["round"]["of"] == 3 and sc["heat"] >= 1 and all(e["res"] and e["text"] and e["lane"] for e in sc["entrants"])
        and sum(1 for e in sc["entrants"] if e["mine"]) == 1, sc["round"])
    chk("각본: 진출 표시는 다음 라운드 전에는 없다", all(e.get("q") is None for e in sc["entrants"]))
    sc2 = OL.heat(out["user_id"], "sprint", 1, sc["heat"], now=at(prog[1]["at"]))
    chk("  다음 라운드가 시작되면 Q/q 가 보인다", any(e.get("q") in ("Q", "q") for e in sc2["entrants"]))
    others = [h["heat"] for h in db.q("SELECT heat FROM olympic_heat WHERE event='sprint' AND round=1 AND heat<>?",
                                       (sc["heat"],))]
    chk("남의 조는 그 라운드 공개 전에는 403", (refused(OL.heat, out["user_id"], "sprint", 1, others[0], now=at(30)) or [0])[0]
        == 403)
    chk("  공개 뒤에는 본다", OL.heat(out["user_id"], "sprint", 1, others[0], now=at(prog[1]["at"]))["heat"] == others[0])
    b0 = OL.board(champ, "sprint", now=at(30))
    chk("결과표: 공개 전 라운드는 없음 · 최종 순위 감춤", b0["rounds"] == [] and b0["standings"] == [] and b0["hidden"], b0)
    b1 = OL.board(champ, "sprint", now=at(prog[1]["at"]))
    chk("결과표: 예선 공개 뒤 예선 조들", len(b1["rounds"]) == 1 and len(b1["rounds"][0]["heats"]) == 4
        and b1["standings"] == [], [len(r["heats"]) for r in b1["rounds"]])
    old_top = OL.BOARD_TOP
    OL.BOARD_TOP = 3                              # 조가 하나인 종목(마라톤 · 봅슬레이 …)은 한 조가 수백 줄 - 위 N줄 + 내 줄만
    bt = OL.board(out["user_id"], "sprint", now=at(prog[1]["at"]))
    OL.BOARD_TOP = old_top
    rows1 = [h["rows"] for h in bt["rounds"][0]["heats"]]
    chk("결과표: 조마다 위 BOARD_TOP 줄 + 내 줄만 (긴 목록이 화면을 무겁게 하지 않게)",
        all(len(r) <= 4 for r in rows1) and any(x["mine"] for r in rows1 for x in r)
        and all(len([x for x in r if not x["mine"]]) <= 3 for r in rows1), [len(r) for r in rows1])
    end = at(info["end"])
    OL.board(champ, "sprint", now=end - datetime.timedelta(seconds=1))
    BALLS0.update((u, balls(u)) for u in us)                # 정산 바로 전 (중계 · 업적 볼은 이미 받았다)
    chk("중계가 끝나기 전에는 정산하지 않는다", db.q1("SELECT COUNT(*) c FROM olympic_final")["c"] == 0)
    b2 = OL.board(champ, "sprint", now=end)
    chk("결과표: 그날 끝나면 최종 순위 · 내 줄", len(b2["rounds"]) == 3 and b2["standings"][0]["rank"] == 1
        and b2["me"]["rank"] == 1 and not b2["hidden"], b2["me"])
    st0 = dict((e["key"], e) for e in OL.state(champ, now=at(30))["events"])["sprint"]
    chk("상태: 중계 중에는 내 결과를 감춘다", st0["status"] == "live" and st0["result"] is None, st0)
    st1 = dict((e["key"], e) for e in OL.state(champ, now=end)["events"])["sprint"]
    chk("상태: 끝나면 내 순위 · 기록", st1["status"] == "done" and st1["result"]["rank"] == 1 and st1["result"]["text"], st1)
    chk("페이즈: 그날 end 까지 live", OL.state(champ, now=end - datetime.timedelta(seconds=2))["phase"] == "live"
        and OL.state(champ, now=end)["phase"] == "entry")
    card = OL.me_card(champ, now=at(30))
    chk("/api/me 카드: 중계 중 · 끝나는 때", card["phase"] == "live" and abs(card["endIn"] - (info["end"] - 30)) <= 1, card)


# ---------------------------------------------------------------- 5. 정산
def settle_part(us, mons):
    print("\n[정산]")
    info = OL.day_info(D1)
    end = O.start_at(D1) + datetime.timedelta(seconds=info["end"])
    top = [r["user_id"] for r in db.q("SELECT user_id FROM olympic_entry WHERE event='sprint' ORDER BY rank LIMIT 3")]
    OL._settled.clear()
    OL.ensure_ran(end + datetime.timedelta(minutes=1))       # 두 번째 (결과표 검사 때 한 번 돌았다)
    chk("1~3위: 그 종목 칭호 (종목마다 하나 - 100m 는 '%s')" % O.TITLE["sprint"],
        all(db.q1("SELECT 1 FROM user_reward WHERE user_id=? AND kind='title' AND rid='oly_sprint'", (w,)) is not None
            for w in top) and season.TITLES.get("oly_sprint") == O.TITLE["sprint"])
    chk("칭호 이름은 종목 특징 (금메달 · 은메달 같은 이름 없음, 일곱 종목 다 다르다)",
        len(set(O.TITLE[e["key"]] for e in O.EVENTS)) == 7 and not any("메달" in O.TITLE[e["key"]] for e in O.EVENTS)
        and not any(k.startswith("oly_gold") or k in ("oly_silver", "oly_bronze") for k in season.TITLES), O.TITLE)
    gifts = [[r["item_id"] for r in db.q("SELECT item_id FROM gift WHERE user_id=? AND kind='deco'", (w,))] for w in top]
    chk("메달 꾸미기: 금 · 은 · 동 하나씩 선물함으로 (두 번 돌려도 한 번)",
        gifts == [["medal_gold"], ["medal_silver"], ["medal_bronze"]], gifts)
    g1 = db.q1("SELECT title, message FROM gift WHERE user_id=? AND kind='deco'", (top[0],))
    chk("메달 선물 글: 종목 · 메달 · 칭호 이름", g1 and "100m" in g1["title"] and "금메달" in g1["title"]
        and O.TITLE["sprint"] in g1["message"], dict(g1 or {}))
    from app import deco as DECO, items as ITEMS
    got = ITEMS.gift_claim(top[0])
    chk("메달 선물을 받으면 꾸미기 주머니에 금메달 (목에 걸 수 있다)",
        DECO.owned(top[0]).get("medal_gold") == 1 and any(g.get("name") == "금메달" for g in got), got)
    fourth = db.q1("SELECT user_id FROM olympic_entry WHERE event='sprint' AND rank=4")["user_id"]
    chk("4위는 메달 꾸미기 없음", db.q1("SELECT COUNT(*) c FROM gift WHERE user_id=? AND kind='deco'", (fourth,))["c"] == 0)
    chk("메달 볼 금 +20 · 은 +15 · 동 +10 (두 번 돌려도 한 번)", [balls(w) - BALLS0[w] for w in top] == [20, 15, 10],
        [balls(w) - BALLS0[w] for w in top])
    tl = dict((t["id"], t) for t in achievements.titles(top[1])["titles"])
    chk("도감 칭호 목록: 종목 칭호 일곱 + 결선 · 은메달도 100m 칭호를 가졌다",
        all(tl.get("oly_" + e["key"], {}).get("name") == O.TITLE[e["key"]] for e in O.EVENTS)
        and tl["oly_sprint"]["owned"] and "1~3위" in tl["oly_ski"]["how"] and "oly_final" in tl,
        [(k, v["name"]) for k, v in tl.items() if k.startswith("oly")])
    pid = db.q1("SELECT pokemon_id FROM olympic_final WHERE event='sprint' AND rank=1")["pokemon_id"]
    chk("금메달 리본은 그 포켓몬에", ("oly_gold", "sprint") in ribbons(pid), ribbons(pid))
    chk("4~8위 결선 진출 칭호 다섯", db.q1("SELECT COUNT(*) c FROM user_reward WHERE rid='oly_final'")["c"] == 5)
    chk("종족 1위 리본: 셋 넘게 나온 종마다 하나 (피카츄 · 라이츄 …)",
        db.q1("SELECT COUNT(*) c FROM pokemon_ribbon WHERE kind='oly_species' AND event='sprint'")["c"] == len(
            [s for s in set(SPECIES) if sum(1 for i in range(30) if SPECIES[i % len(SPECIES)] == s) >= O.SPECIES_MIN]))
    st = OL.state(top[0], now=end)
    chk("상태: 그 종목 메달 표 · 내 메달", st["medals"]["sprint"][0]["rank"] == 1
        and any(m["event"] == "sprint" for m in st["myMedals"]), st["medals"].get("sprint"))
    OL.ensure_ran(kst(D2, 14, 0, 1))
    d2 = db.q1("SELECT * FROM olympic_day WHERE day=?", (D2,))
    chk("신청 0 인 날(봅슬레이)도 멈추지 않는다", d2 is not None and d2["n"] == 0 and OL.day_info(D2)["end"] == 0
        and OL.board(us[0], "bobsled", now=kst(D2, 15))["rounds"] == [], dict(d2 or {}))
    # 정산 도중 칭호 주기가 한 번 실패해도 (DB 잠김 등) 다시 돌리면 볼까지 다 받는다 - 장대(셋째 날)로
    vs = []
    for i in range(9):
        u = mkuser("장대%d" % i)
        vs.append(u)
        OL.enter(u, "pole", mkmon(u, "HERACROSS", seed=40 + i), "safe", now=kst(D2, 15) + datetime.timedelta(minutes=i))
    OL.ensure_ran(kst(D3, 14, 0, 1))
    end3 = O.start_at(D3) + datetime.timedelta(seconds=OL.day_info(D3)["end"])
    tp = [r["user_id"] for r in db.q("SELECT user_id FROM olympic_entry WHERE event='pole' ORDER BY rank LIMIT 3")]
    p0 = dict((w, balls(w)) for w in tp)
    real_grant, boom = season.grant, [True]

    def grant_once_fails(*a, **kw):
        if boom[0]:
            boom[0] = False
            raise RuntimeError("database is locked")
        return real_grant(*a, **kw)
    season.grant = grant_once_fails
    try:
        OL.ensure_ran(end3)                     # 첫 칭호에서 터진다
    except RuntimeError:
        pass
    season.grant = real_grant
    OL.ensure_ran(end3)
    OL._settled.clear()
    OL.ensure_ran(end3 + datetime.timedelta(minutes=1))
    chk("정산이 한 번 실패해도 다시 돌리면 볼 · 칭호를 받고, 볼은 한 번", [balls(w) - p0[w] for w in tp] == [20, 15, 10]
        and db.q1("SELECT 1 FROM user_reward WHERE user_id=? AND rid='oly_pole'", (tp[0],)) is not None
        and db.q1("SELECT COUNT(*) c FROM gift WHERE user_id=? AND kind='deco' AND item_id='medal_gold'",
                  (tp[0],))["c"] == 1,
        [balls(w) - p0[w] for w in tp])
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
        chk("올림픽 탭도 깨지지 않는다", st["phase"] == "before", st.get("phase"))
    except Exception as e:                                   # noqa: BLE001
        chk("경기 날을 비워 두면 /api/me 는 그냥 None (500 이 아니다)", False, repr(e))
    finally:
        O.DAYS = old


def main_():
    db.init()
    want = set(sys.argv[1:])
    rules_part()
    entry_part()
    us, mons = run_part()
    reveal_part(us, mons)
    settle_part(us, mons)
    empty_part()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
