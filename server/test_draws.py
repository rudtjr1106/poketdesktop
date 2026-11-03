# -*- coding: utf-8 -*-
"""뽑기 검사 (2.1.1): 상점의 기술머신 뽑기 · 랜덤 기술머신 뽑기권 판매 · 랜덤 캡슐 10회. 서버를 띄우지 않는다.

    python server/test_draws.py

못 박는 것 (사용자 결정 11/04):

  1. 랜덤 기술머신 뽑기권을 상점에서 10,000원에 판다 (상점이 숨기는 custom 표시가 없다). 되팔기는 0원,
     길드 코인 상점에는 없다.
  2. 상점 기술머신 뽑기: 1번 10,000원 · 10번 100,000원. 아직 없는 기술머신만, 10번 안에서도 겹치지 않는다.
     돈이 모자라거나 · 남은 기술머신이 모자라거나 · 다 모았거나 · 횟수가 1 · 10 이 아니면 거절하고 돈은 그대로.
     /api/shop 답에 한 번 값과 남은 수가 실린다.
  3. 랜덤 캡슐 10회: 코인 200개를 한꺼번에 빼고 열 판을 굴려 각각 준다 (기록도 열 줄). 가장 좋은 등급과
     등급마다 몇 개인지 말한다. 코인이 모자라면 거절하고 그대로. 한 번은 2.1.0 과 같은 답 모양.
     주다가 터지면 아직 안 굴린 판의 코인을 돌려준다.
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

from app import db, guild, item_routes, items, tms               # noqa: E402

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


def draw(uid, n):
    try:
        return item_routes.tm_draw(item_routes.TmDrawIn(count=n), me(uid)), None
    except HTTPException as e:
        return None, (e.status_code, e.detail)


def spin(uid, n, rng=None):
    try:
        return guild.slot(uid, rng=rng or random.Random(5), count=n), None
    except HTTPException as e:
        return None, (e.status_code, e.detail)


def ticket():
    print("-- 1. 랜덤 기술머신 뽑기권")
    it = items.get("RANKTICKETTM")
    row = next(r for r in items.public_list() if r["id"] == "RANKTICKETTM")
    chk("상점 값 10,000원 · 살 수 있다 · 숨김(custom) 아님", items.buy_price("RANKTICKETTM") == 10000
        and row["buyable"] and not row["custom"], row)
    chk("  되팔기 0원 · 길드 코인 상점에는 없다", it["sell"] == 0 and guild.coin_price("RANKTICKETTM") == 0)
    uid = mkuser("표사기", 25000)
    r = item_routes.buy(item_routes.BuyIn(item="RANKTICKETTM", count=2), me(uid))
    chk("  두 장 사면 20,000원이 빠지고 가방에 두 장", items.money(uid) == 5000
        and items.bag_count(uid, "RANKTICKETTM") == 2, (items.money(uid), r.get("message")))


def tm_draw():
    print("-- 2. 상점 기술머신 뽑기")
    total = len(tms.all_tms())
    uid = mkuser("뽑는이", 150000)
    s = item_routes.shop(me(uid))
    chk("/api/shop 에 한 번 값 · 남은 수", s.get("tmDraw") == {"price": 10000, "counts": [1, 10], "left": total},
        s.get("tmDraw"))
    r, err = draw(uid, 1)
    chk("1번: 10,000원, 아직 없던 기술머신 하나", r and r["count"] == 1 and items.money(uid) == 140000
        and len(tms.owned(uid)) == 1 and r["money"] == 140000, (r, err))
    first = set(tms.owned(uid))
    r, err = draw(uid, 10)
    got = [t["no"] for t in (r or {}).get("tms", [])]
    chk("10번: 100,000원, 기술머신 10개", r and r["count"] == 10 and items.money(uid) == 40000
        and len(tms.owned(uid)) == 11, (err, items.money(uid)))
    chk("  열 개가 서로 다르고 이미 가진 것은 없다", len(set(got)) == 10 and not (set(got) & first), got)
    chk("  새 기술머신 점 수 · 말", r and r["tmNew"] == 11 and "10개" in r["message"], r and r["message"])
    r, err = draw(uid, 10)
    chk("돈이 모자라면(40,000원) 거절하고 돈 · 기술머신은 그대로", err and "모자랍니다" in err[1]
        and items.money(uid) == 40000 and len(tms.owned(uid)) == 11, err)
    for bad in (0, 2, 5, 11):
        r, err = draw(uid, bad)
        chk("%d번은 거절" % bad, err and err[0] == 400 and items.money(uid) == 40000, err)

    rich = mkuser("거의다", 1000000)
    every = sorted(tms.all_tms())
    for no in every[:-3]:
        tms.give(rich, no)
    r, err = draw(rich, 10)
    chk("남은 기술머신이 3개뿐이면 10번은 돈을 빼기 전에 거절", err and "3개뿐" in err[1]
        and items.money(rich) == 1000000, err)
    for _ in range(3):
        draw(rich, 1)
    r, err = draw(rich, 1)
    chk("다 모았으면 1번도 거절, 돈은 그대로", err and "다 모아서" in err[1] and items.money(rich) == 970000,
        (err, items.money(rich)))
    chk("  /api/shop 의 남은 수 0", item_routes.shop(me(rich))["tmDraw"]["left"] == 0)


def capsule():
    print("-- 3. 랜덤 캡슐 10회")
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


def main():
    db.init()
    ticket()
    tm_draw()
    capsule()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
