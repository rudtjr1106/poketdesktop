# -*- coding: utf-8 -*-
"""파티 프리셋 검사 (1.10.3).

    python server/test_party.py

서버를 띄우지 않고 app.party 의 함수를 직접 부른다.

무엇을 못 박나:
  1. 프리셋은 다섯. 아무것도 안 한 사람은 1번을 쓰고 있고, 1번의 내용은 **지금 데리고 다니는 것**이다.
  2. 한 번도 안 쓴 번호로 가면 지금 파티를 그대로 들고 간다 (바탕화면이 비지 않는다).
  3. 번호를 오가도 잃는 것이 없다: 떠날 때 지금 파티가 그 번호에 적히고, 돌아오면 순서까지 그대로다.
  4. 박스로 돌아가는 포켓몬은 원래 박스로 간다. 박스가 꽉 차 있어도 맞바꿀 수 있다.
  5. 알은 프리셋에 안 들어가고 자리를 지킨다. 알까지 합쳐 여섯을 넘으면 갈아타지 않는다 (아무것도 안 바뀐다).
  6. 놓아준 포켓몬은 조용히 빠진다. 남의 포켓몬은 섞여 들어오지 않는다.
  7. 이름: 네 자까지, 비우면 기본 이름. 이름만 붙인 번호는 여전히 '안 쓴 번호' 다.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-party-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                            # noqa: E402

from app import config, db, main, party                      # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def err(fn, *a, **k):
    try:
        fn(*a, **k)
    except HTTPException as e:
        return e.status_code, e.detail
    return None


def mkuser(name):
    return db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                  " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')",
                  (name, b"x", b"x")).lastrowid


def mkmon(uid, slot=None, box=0, species="PIKACHU"):
    """slot 을 주면 데리고 다니는 포켓몬, 아니면 그 박스에."""
    return db.run(
        "INSERT INTO pokemon (user_id, species, level, exp, nature, ability, hidden_ability, gender,"
        " shiny, happiness, ivs, evs, moves, on_desktop, slot, box, met_level, caught_at)"
        " VALUES (?,?,5,0,'HARDY',NULL,0,'M',0,70,'{}','{}','[]',?,?,?,5,'')",
        (uid, species, 0 if slot is None else 1, slot, box)).lastrowid


def mkegg(uid, slot):
    """데리고 다니는 (아직 안 깬) 알."""
    return db.run("INSERT INTO egg (user_id, kind, species, need_sec, got_sec, created_at, on_desktop, slot)"
                  " VALUES (?,'legendary','MEW',9999,0,'',1,?)", (uid, slot)).lastrowid


def desk(uid):
    return [(r["id"], r["slot"]) for r in db.q(
        "SELECT id, slot FROM pokemon WHERE user_id=? AND on_desktop=1 ORDER BY slot, id", (uid,))]


def where(pid):
    r = db.q1("SELECT on_desktop, slot, box FROM pokemon WHERE id=?", (pid,))
    return ("desk", r["slot"]) if r["on_desktop"] else ("box", r["box"])


def main_():
    db.init()
    me, other = mkuser("주인공"), mkuser("남")
    a = [mkmon(me, slot=i, box=i % 3) for i in range(6)]        # 지금 파티 여섯 (원래 박스는 0·1·2)
    b = [mkmon(me, box=3) for _ in range(6)]                     # 박스 3 에 여섯
    theirs = mkmon(other, slot=0)

    print("=== 아무것도 안 한 사람 ===")
    st = party.state(me)
    chk("프리셋은 다섯, 지금 번호는 1", st["count"] == 5 and st["active"] == 1 and len(st["presets"]) == 5
        and [p["no"] for p in st["presets"]] == [1, 2, 3, 4, 5], st["active"])
    chk("1번의 내용은 지금 데리고 다니는 것", st["presets"][0]["ids"] == a and st["presets"][0]["size"] == 6
        and st["presets"][0]["active"] and st["presets"][0]["saved"])
    chk("나머지는 안 쓴 번호", all(not p["saved"] and p["ids"] == [] and not p["active"] for p in st["presets"][1:]))
    chk("기본 이름은 '파티 N'", [p["name"] for p in st["presets"]] == ["파티 %d" % i for i in range(1, 6)]
        and not any(p["named"] for p in st["presets"]))
    chk("아직 표에 적힌 것이 없다 (읽기만 했다)", db.q1("SELECT COUNT(*) c FROM party_preset")["c"] == 0)
    chk("없는 번호", (err(party.use, me, 0) or (0,))[0] == 404 and (err(party.use, me, 6) or (0,))[0] == 404
        and (err(party.rename, me, 9, "x") or (0,))[0] == 404)
    r = party.use(me, 1)
    chk("지금 번호를 다시 누르면 아무 일도 없다", r["ok"] and r["changed"] is False and desk(me) == [(p, i) for i, p in enumerate(a)]
        and db.q1("SELECT COUNT(*) c FROM party_preset")["c"] == 0)

    print("\n=== 처음 쓰는 번호 ===")
    r = party.use(me, 2)
    chk("지금 파티를 그대로 들고 간다 (바탕화면이 비지 않는다)", r["active"] == 2 and r["changed"] is False
        and desk(me) == [(p, i) for i, p in enumerate(a)] and "그대로" in r["message"], r["message"])
    chk("1번에는 떠나기 전의 파티가 적혀 있다", r["presets"][0]["ids"] == a and r["presets"][0]["saved"]
        and not r["presets"][0]["active"] and r["presets"][1]["active"])

    print("\n=== 2번을 다른 여섯으로 바꾼다 ===")
    for p in a:
        main.deps.to_box(me, p, prefer=db.q1("SELECT box FROM pokemon WHERE id=?", (p,))["box"])
    order = [b[2], b[0], b[5], b[1]]                              # 넷만, 순서도 내 마음대로
    for i, p in enumerate(order):
        db.run("UPDATE pokemon SET on_desktop=1, slot=? WHERE id=?", (i, p))
    st = party.state(me)
    chk("지금 번호(2)의 내용이 따라 바뀐다 - 저장 단추가 없다", st["presets"][1]["ids"] == order and st["presets"][1]["size"] == 4
        and st["presets"][0]["ids"] == a, st["presets"][1]["ids"])

    print("\n=== 오가기 ===")
    r = party.use(me, 1)
    chk("1번으로 돌아오면 그 여섯이 순서대로 나온다", desk(me) == [(p, i) for i, p in enumerate(a)] and r["changed"] is True
        and r["active"] == 1 and "파티 1" in r["message"], (desk(me), r["message"]))
    chk("  2번의 넷은 원래 있던 박스(3)로 돌아갔다", all(where(p) == ("box", 3) for p in order))
    chk("  2번에는 떠나기 전의 넷이 순서대로 적혀 있다", r["presets"][1]["ids"] == order and r["presets"][1]["size"] == 4)
    r = party.use(me, 2)
    chk("2번으로 가면 그 넷이 그 순서로", desk(me) == [(p, i) for i, p in enumerate(order)], desk(me))
    chk("  1번의 여섯은 저마다 원래 박스(0·1·2)로", [where(p) for p in a] == [("box", i % 3) for i in range(6)],
        [where(p) for p in a])
    party.use(me, 1)
    party.use(me, 2)
    party.use(me, 1)
    chk("몇 번을 오가도 그대로다", desk(me) == [(p, i) for i, p in enumerate(a)]
        and party.state(me)["presets"][1]["ids"] == order)
    chk("포켓몬 수는 그대로 (없어지거나 늘지 않는다)", db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=?", (me,))["c"] == 12)

    print("\n=== 겹치는 포켓몬 ===")
    party.use(me, 3)                                              # 처음 쓰는 번호: 1번의 여섯을 들고 온다
    main.deps.to_box(me, a[5], prefer=2)
    db.run("UPDATE pokemon SET on_desktop=1, slot=5 WHERE id=?", (b[0],))    # 3번 = a0..a4 + b0
    mix = a[:5] + [b[0]]
    chk("(준비) 3번 = 1번의 다섯 + 2번의 하나", party.state(me)["presets"][2]["ids"] == mix)
    party.use(me, 2)
    chk("한 포켓몬이 여러 번호에 들어 있어도 된다 (2번에도 b0 가 나온다)", [p for p, _s in desk(me)] == order)
    party.use(me, 3)
    chk("  3번으로 오면 섞인 여섯이 그대로", [p for p, _s in desk(me)] == mix, desk(me))
    chk("  같이 쓰는 포켓몬은 박스에 다녀오지 않는다 (자리만 바뀐다)", where(b[0]) == ("desk", 5))

    print("\n=== 박스가 꽉 차 있어도 ===")
    full = mkuser("꽉찬사람")
    keep_size, keep_count = config.BOX_SIZE, config.BOX_COUNT
    config.BOX_SIZE, config.BOX_COUNT = 3, 2                      # 박스 둘, 셋씩 = 여섯 자리
    fa = [mkmon(full, slot=i, box=i % 2) for i in range(6)]
    party.use(full, 2)
    for p in fa:
        main.deps.to_box(full, p, prefer=db.q1("SELECT box FROM pokemon WHERE id=?", (p,))["box"])
    fb = [mkmon(full, slot=i, box=0) for i in range(6)]          # 박스는 fa 로 꽉 찼다, 2번 = fb
    chk("(준비) 박스 여섯 자리가 다 찼다", db.q1("SELECT COUNT(*) c FROM pokemon WHERE user_id=? AND on_desktop=0",
                                        (full,))["c"] == 6)
    party.use(full, 1)
    per = dict((r["box"], r["n"]) for r in db.q("SELECT box, COUNT(*) n FROM pokemon WHERE user_id=? AND on_desktop=0"
                                                " GROUP BY box", (full,)))
    chk("여섯과 여섯을 맞바꾼다 (꺼내는 일이 먼저라 자리가 난다)", [p for p, _s in desk(full)] == fa
        and per == {0: 3, 1: 3}, (desk(full), per))
    config.BOX_SIZE, config.BOX_COUNT = keep_size, keep_count

    print("\n=== 알 ===")
    egg = mkuser("알가진사람")
    ea = [mkmon(egg, slot=i) for i in range(4)]
    eg = mkegg(egg, 5)
    party.use(egg, 2)                                             # 2번 = 지금의 넷
    for p in ea[2:]:
        main.deps.to_box(egg, p)                                  # 2번 = 둘
    r = party.use(egg, 1)
    slots = desk(egg)
    chk("알은 프리셋에 들지 않는다", all(eg not in p["ids"] for p in r["presets"]))
    chk("갈아타도 알은 제자리(5)에 있다", db.q1("SELECT on_desktop, slot FROM egg WHERE id=?", (eg,))["slot"] == 5
        and db.q1("SELECT on_desktop FROM egg WHERE id=?", (eg,))["on_desktop"] == 1)
    chk("  포켓몬은 알의 자리를 피해 앉는다", [p for p, _s in slots] == ea and 5 not in [s for _p, s in slots], slots)
    mkegg(egg, 4)
    party.use(egg, 2)                                             # 둘 + 알 둘 = 넷: 된다
    eb = [mkmon(egg, slot=i + 2) for i in range(2)]               # 2번 = 넷(포켓몬) + 알 둘 = 여섯
    party.use(egg, 3)                                             # 3번 = 지금의 넷
    mkegg(egg, None)                                              # 자리 번호 없는 옛 알 하나 더 (알 셋)
    before = (desk(egg), party.state(egg)["active"])
    e = err(party.use, egg, 1)                                    # 1번은 넷 + 알 셋 = 일곱
    chk("알까지 합쳐 여섯을 넘으면 갈아타지 않는다 (까닭을 알린다)", e is not None and e[0] == 409 and "알" in e[1]
        and "4마리" in e[1], e)
    chk("  아무것도 안 바뀐다", (desk(egg), party.state(egg)["active"]) == before and len(eb) == 2)

    print("\n=== 놓아준 포켓몬·남의 포켓몬 ===")
    party.use(me, 1)
    db.run("DELETE FROM pokemon WHERE id=?", (order[1],))         # 2번에 있던 b0 을 놓아줬다
    st = party.state(me)
    chk("놓아준 포켓몬은 목록에서 빠진다", st["presets"][1]["ids"] == [order[0], order[2], order[3]]
        and st["presets"][1]["size"] == 3 and b[0] not in st["presets"][2]["ids"], st["presets"][1]["ids"])
    party.use(me, 2)
    chk("  갈아타면 남은 셋이 빈 번호 없이 앉는다", desk(me) == [(order[0], 0), (order[2], 1), (order[3], 2)], desk(me))
    db.run("UPDATE party_preset SET ids=? WHERE user_id=? AND no=1", (json.dumps([theirs] + a[:2] + ["x", a[0]]), me))
    r = party.use(me, 1)
    chk("남의 포켓몬·엉뚱한 값·같은 것 두 번은 걸러진다", [p for p, _s in desk(me)] == a[:2]
        and where(theirs) == ("desk", 0) and db.q1("SELECT user_id FROM pokemon WHERE id=?", (theirs,))["user_id"] == other,
        desk(me))
    db.run("UPDATE party_preset SET ids='깨진 글' WHERE user_id=? AND no=2", (me,))
    r = party.use(me, 2)
    chk("깨진 저장분은 빈 파티로 읽는다 (터지지 않는다)", desk(me) == [] and "비어" in r["message"], r["message"])
    party.use(me, 1)

    print("\n=== 이름 ===")
    r = party.rename(me, 2, "  랭크  ")
    chk("이름을 붙인다 (앞뒤 빈칸은 뗀다)", r["presets"][1]["name"] == "랭크" and r["presets"][1]["named"], r["presets"][1])
    chk("네 자까지 ('바탕화면' 은 된다)", party.rename(me, 3, "바탕화면")["presets"][2]["name"] == "바탕화면"
        and (err(party.rename, me, 3, "바탕화면용") or (0,))[0] == 400 and party.state(me)["nameMax"] == 4)
    chk("비우면 기본 이름으로", party.rename(me, 2, "")["presets"][1]["name"] == "파티 2"
        and not party.state(me)["presets"][1]["named"])
    chk("이름을 바꿔도 내용과 지금 번호는 그대로", party.state(me)["active"] == 1 and [p for p, _s in desk(me)] == a[:2])
    new = mkuser("새사람")
    n1 = mkmon(new, slot=0)
    r = party.rename(new, 4, "레이드")
    chk("이름만 붙인 번호는 여전히 '안 쓴 번호' 다", r["presets"][3]["name"] == "레이드" and not r["presets"][3]["saved"]
        and r["active"] == 1 and r["presets"][0]["ids"] == [n1], (r["active"], r["presets"][3]))
    r = party.use(new, 4)
    chk("  거기로 가면 지금 파티를 들고 가고, 이름은 남아 있다", r["active"] == 4 and desk(new) == [(n1, 0)]
        and r["presets"][3]["name"] == "레이드" and "레이드" in r["message"], r["message"])
    r = party.rename(new, 4, "보스")
    chk("지금 번호의 이름도 바꿀 수 있다", r["presets"][3]["name"] == "보스" and r["active"] == 4)

    print("\n=== 경로 ===")
    api = main.app.openapi()["paths"]
    chk("GET /api/party, POST …/use, POST …/name", "get" in api.get("/api/party", {})
        and "post" in api.get("/api/party/{no}/use", {}) and "post" in api.get("/api/party/{no}/name", {}), sorted(k for k in api if "party" in k))
    chk("계정이 지워지면 프리셋도 지워진다", db.run("DELETE FROM users WHERE id=?", (new,)) is not None
        and db.q1("SELECT COUNT(*) c FROM party_preset WHERE user_id=?", (new,))["c"] == 0)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
