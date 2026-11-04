# -*- coding: utf-8 -*-
"""뽑기 검사 (2.1.1): 랜덤 캡슐 10회 · 상점에서 돈으로 돌리는 랜덤 캡슐. 서버를 띄우지 않는다.

    python server/test_draws.py

못 박는 것 (사용자 결정 11/04):

  1. 랜덤 기술머신 뽑기권은 **팔지 않는다** (2.1.0 그대로 - 보상으로만). 돈으로 기술머신을 뽑는 길도 없다.
     (11/04 '랜덤 뽑기권' 을 기술머신 뽑기권으로 잘못 읽어 5분 동안 팔았다가 서버를 닫고 뺐다)
  2. 랜덤 캡슐 10회 (길드 코인): 코인 200개를 한꺼번에 빼고 열 판을 굴려 각각 준다 (기록도 열 줄). 가장 좋은 등급과
     등급마다 몇 개인지 말한다. 코인이 모자라면 거절하고 그대로. 한 번은 2.1.0 과 같은 답 모양.
     주다가 터지면 아직 안 굴린 판의 코인을 돌려준다.
  3. 상점의 랜덤 캡슐 (돈): 한 번 10,000원 · 10번 100,000원, 상품 · 확률은 코인 것과 같다. 코인은 그대로이고
     돈만 빠진다. 기록의 cost 는 10,000. 모자라면 거절, 터지면 안 굴린 판의 돈을 돌려준다. /api/shop 에 값 · 확률표.
"""
import datetime
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="poket-draws-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_HOUSEKEEP"] = "0"

from fastapi import HTTPException                                # noqa: E402

from app import db, guild, item_routes, items                    # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def mkuser(name, money=0):
    return db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at, last_login, last_ip)"
                  " VALUES (?, x'00', x'00', 1, 10, ?, ?, ?, '')", (name, money, iso(), iso())).lastrowid


def me(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def buy_capsule(uid, n):
    try:
        return item_routes.capsule(item_routes.CapsuleIn(count=n), me(uid)), None
    except HTTPException as e:
        return None, (e.status_code, e.detail)


def spin(uid, n, rng=None):
    try:
        return guild.slot(uid, rng=rng or random.Random(5), count=n), None
    except HTTPException as e:
        return None, (e.status_code, e.detail)


def ticket():
    print("-- 1. 랜덤 기술머신 뽑기권은 팔지 않는다")
    it = items.get("RANKTICKETTM")
    chk("상점 값 없음 · 살 수 없음 · 상점에서 숨김(custom) - 2.1.0 그대로", items.buy_price("RANKTICKETTM") <= 0
        and it.get("buyable") is False and it.get("custom") is True and it["sell"] == 0, it)
    uid = mkuser("표사기", 25000)
    try:
        item_routes.buy(item_routes.BuyIn(item="RANKTICKETTM", count=1), me(uid))
        chk("  사려고 하면 거절", False)
    except HTTPException as e:
        chk("  사려고 하면 거절하고 돈은 그대로", e.status_code == 400 and items.money(uid) == 25000, e.detail)
    chk("돈으로 기술머신을 뽑는 길(/api/shop/tmdraw)은 없다", not hasattr(item_routes, "tm_draw")
        and not any(getattr(r, "path", "") == "/api/shop/tmdraw" for r in item_routes.router.routes))
    s = item_routes.shop(me(uid))
    chk("  /api/shop 에 tmDraw 가 없다 (2.1.1 앱의 기술머신 뽑기 띠가 숨는다)", "tmDraw" not in s, sorted(s))


def money_capsule():
    print("-- 3. 상점의 랜덤 캡슐 (돈)")
    uid = mkuser("돈캡슐", 125000)
    guild._coin_add(uid, 7)
    s = item_routes.shop(me(uid))
    chk("/api/shop 에 값 · 횟수 · 확률표", s.get("capsule", {}).get("price") == 10000
        and s["capsule"]["counts"] == [1, 10] and s["capsule"]["odds"] == guild.slot_odds(), s.get("capsule"))
    n0 = db.q1("SELECT COUNT(*) c FROM guild_slot_log WHERE user_id=?", (uid,))["c"]
    r, err = buy_capsule(uid, 1)
    chk("1번: 10,000원, 코인은 그대로 (한 판 답 모양 + 지갑)", r and "prize" in r and items.money(uid) == 115000
        and r["money"] == 115000 and guild.coin(uid) == 7, (err, items.money(uid)))
    r, err = buy_capsule(uid, 10)
    chk("10번: 100,000원, 열 판", r and len(r["results"]) == 10 and items.money(uid) == 15000
        and r["money"] == 15000 and guild.coin(uid) == 7, (err, items.money(uid)))
    logs = db.q("SELECT cost FROM guild_slot_log WHERE user_id=? ORDER BY rowid", (uid,))[n0:]
    chk("  기록 열한 줄, cost 는 10,000 (원)", len(logs) == 11 and all(x["cost"] == 10000 for x in logs),
        [x["cost"] for x in logs][:3])
    r, err = buy_capsule(uid, 10)
    chk("돈이 모자라면(15,000원) 거절하고 그대로", err and "100,000원" in err[1] and items.money(uid) == 15000, err)
    for bad in (0, 3):
        r, err = buy_capsule(uid, bad)
        chk("%d번은 거절" % bad, err and err[0] == 400 and items.money(uid) == 15000, err)

    u2 = mkuser("돈터짐", 100000)
    real = guild._slot_give
    calls = []

    def boom(uid_, row, rng, now):
        calls.append(1)
        if len(calls) == 3:
            raise RuntimeError("주다가 터짐")
        return real(uid_, row, rng, now)
    guild._slot_give = boom
    try:
        try:
            guild.slot(u2, rng=random.Random(2), count=10, pay="money")
            chk("주다가 터지면 오류", False)
        except RuntimeError:
            pass
    finally:
        guild._slot_give = real
    chk("  아직 안 굴린 여덟 판의 돈(80,000원)을 돌려준다", items.money(u2) == 80000, items.money(u2))


def capsule():
    print("-- 2. 랜덤 캡슐 10회 (길드 코인)")
    uid = mkuser("캡슐러")
    guild._coin_add(uid, 230)
    n0 = db.q1("SELECT COUNT(*) c FROM guild_slot_log WHERE user_id=?", (uid,))["c"]
    r, err = spin(uid, 10)
    logs = db.q1("SELECT COUNT(*) c FROM guild_slot_log WHERE user_id=?", (uid,))["c"] - n0
    chk("10회: 코인 200개를 빼고 열 판", r and r["count"] == 10 and len(r["results"]) == 10 and guild.coin(uid) == 30
        and r["coin"] == 30 and r["cost"] == 200, (err, guild.coin(uid)))
    chk("  기록도 열 줄", logs == 10, logs)
    order = guild.TIER_ORDER
    best = max((x["tier"] for x in r["results"]), key=order.index)
    chk("  가장 좋은 등급을 알려 준다", r["tier"] == best, (r["tier"], best))
    chk("  등급마다 몇 개인지 말한다", r["message"].startswith("10번 뽑았습니다:")
        and sum(int(p.split()[-1]) for p in r["message"].split(":", 1)[1].split("·")) == 10, r["message"])
    chk("  한 판마다 상품 · 등급 · 이름", all("prize" in x and "tier" in x and "message" in x for x in r["results"]))
    r, err = spin(uid, 10)
    chk("코인이 모자라면(30) 거절하고 그대로", err and "200" in err[1] and guild.coin(uid) == 30, err)
    r, err = spin(uid, 1)
    chk("1회는 2.1.0 과 같은 답 모양 (results 없음)", r and "prize" in r and "results" not in r and guild.coin(uid) == 10,
        r and sorted(r))
    for bad in (0, 3):
        r, err = spin(uid, bad)
        chk("%d회는 거절" % bad, err and err[0] == 400 and guild.coin(uid) == 10, err)

    u2 = mkuser("터짐")
    guild._coin_add(u2, 200)
    real = guild._slot_give
    calls = []

    def boom(uid_, row, rng, now):
        calls.append(1)
        if len(calls) == 4:
            raise RuntimeError("주다가 터짐")
        return real(uid_, row, rng, now)
    guild._slot_give = boom
    try:
        try:
            guild.slot(u2, rng=random.Random(1), count=10)
            chk("주다가 터지면 오류", False)
        except RuntimeError:
            pass
    finally:
        guild._slot_give = real
    chk("  아직 안 굴린 일곱 판의 코인(140)을 돌려준다", guild.coin(u2) == 140, guild.coin(u2))


def history():
    print("-- 4. 최근 기록 (2.1.2)")
    uid = mkuser("기록러", 30000)
    guild._coin_add(uid, 260)
    chk("처음에는 비어 있다", item_routes.capsule_history(me(uid))["history"] == [])
    r1, _e = spin(uid, 10)
    r2, _e = buy_capsule(uid, 1)
    h = item_routes.capsule_history(me(uid))["history"]
    chk("최근 10번만, 새것부터 (돈 판이 맨 위)", len(h) == 10 and h[0]["paid"] == "money"
        and all(x["paid"] == "coin" for x in h[1:]), [x["paid"] for x in h])
    chk("  뽑기 답에도 같은 기록이 실린다", r2 and r2.get("history") == h and r1 and len(r1["history"]) == 10,
        r2 and len(r2.get("history") or []))
    chk("  줄마다 등급 · 이름 (꽝은 '꽝')", all(x["tier"] in guild.TIER_ORDER and x["label"] for x in h)
        and all(x["label"] == "꽝" for x in h if x["tier"] == "lose"), h[:3])
    want = r2["itemKr"] or r2.get("decoKr") or (r2.get("egg") or {}).get("kr") or "꽝"
    chk("  맨 위 줄은 방금 돈으로 뽑은 것", h[0]["label"].startswith(want) or (want == "꽝" and h[0]["label"] == "꽝"),
        (h[0], want))
    other = mkuser("남의기록")
    chk("남의 기록은 안 보인다", item_routes.capsule_history(me(other))["history"] == [])


def main():
    db.init()
    ticket()
    capsule()
    money_capsule()
    history()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
