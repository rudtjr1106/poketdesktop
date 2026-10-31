# -*- coding: utf-8 -*-
"""기술머신 — 자료, 소유, 배우기, 그리고 기다리는 기술.

여기서 못 박는 것은 다섯이다.

  1. **못 배우는 기술은 못 배운다.** 클라이언트를 믿으면 아무 포켓몬에게
     아무 기술이나 붙일 수 있다.
  2. **안 가진 기술머신은 못 쓴다.**
  3. **써도 없어지지 않는다.** 영구제라 개수를 깎지 않는다.
  4. **팔거나 살 수 없다.** 상점 목록에 아예 없다.
  5. 네 개가 차 있으면 **말없이 밀어내지 않는다.** 기다렸다 물어본다.
  6. 기술 떠올리기는 **지금 레벨 이하 기술만, 한 번에 5,000원**. 거절하면
     돈을 안 받고, 기다리던 기술은 공짜다.

서버를 띄우지 않는다. DB 와 모듈만 직접 쓴다.
"""
import io
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-tm-")
os.environ.setdefault("POKET_DB", os.path.join(TMP, "t.db"))
os.environ.setdefault("POKET_POKEDEX", os.path.join(HERE, "data", "pokedex.json"))

from app import db, deps, items, tms                       # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def mkuser(name):
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,?,?,'')",
        (name, b"x", b"x", "2026-01-01", "2026-01-01"))
    return cur.lastrowid


def mkmon(uid, species, moves, level=50):
    return db.insert_mon(uid, {
        "species": species, "level": level, "exp": 0, "nature": "HARDY",
        "ability": "OVERGROW", "hiddenAbility": False, "gender": "M",
        "shiny": False, "happiness": 70, "ivs": {}, "evs": {},
        "moves": list(moves), "hyper": {}, "noEvolve": False,
        "luxury": False, "held": None}, "2026-01-01")


def za_level_gaps(d):
    """메가가 있는 종의 Z-A 레벨업 기술 가운데 이 게임에서 그 레벨까지 못 배우는 것 [(종, 기술, Z-A 레벨)].
    Z-A 학습표 캐시가 없으면 None."""
    path = os.path.join(os.path.dirname(HERE), "tools", "_cache", "showdown_gen9legends_learnsets.ts")
    if not os.path.exists(path):
        return None
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
    import add_reminder                                    # noqa: E402
    za = add_reminder.za_learnsets(path)
    out = []
    for name in sorted(set(m["megaOf"] for m in d.raw.get("megas") or [] if m.get("megaOf"))):
        sp = d.get(name)
        level, cur, seen = {}, sp, set()
        while cur and cur["num"] not in seen:
            seen.add(cur["num"])
            for lv, mv in cur.get("moves") or []:
                level[mv] = min(level.get(mv, lv), lv)
            cur = d.get(cur["prevo"]) if cur.get("prevo") else None
        remind = set(sp.get("remind") or [])
        for mv, zlv in sorted((za.get(name) or {}).items()):
            if zlv is None or mv not in d.raw["moves"] or mv in remind:
                continue
            if not (mv in level and level[mv] <= max(zlv, 1)):
                out.append((name, mv, zlv))
    return out


def refused(fn, code=400):
    """HTTPException(code) 로 거절되나."""
    try:
        fn()
    except Exception as e:                                  # noqa: BLE001
        return getattr(e, "status_code", None) == code
    return False


def remember_checks(d, R, Body):
    """기술 떠올리기 - 5,000원, 지금 레벨 이하 기술만, 기다리던 기술은 공짜."""
    from app import config

    print("\n=== 기술 떠올리기 ===")
    cost = config.REMEMBER_COST
    chk("한 번에 5,000원", cost == 5000, cost)
    uid = mkuser("remember")
    me = {"user": {"id": uid}}
    money = lambda: items.money(uid)                       # noqa: E731
    row = lambda pid: db.q1("SELECT * FROM pokemon WHERE id=?", (pid,))  # noqa: E731
    moves_of = lambda pid: json.loads(row(pid)["moves"])   # noqa: E731

    sp = d.get("BULBASAUR")
    low = set(mv for lv, mv in sp["moves"] if lv <= 34)
    high = set(mv for lv, mv in sp["moves"] if lv > 34) - low
    pid = mkmon(uid, "BULBASAUR", ["TACKLE"], level=34)

    lst = R.remember_list(pid, me)
    got = [x["move"] for x in lst["remember"]]
    # 떠올리기 전용 기술(remind - 1.13.3 부터 기술머신이 없는 알 기술도: 이상해씨 뿌리박기)은 레벨과 상관없이 나온다
    remind = set(sp.get("remind") or [])
    chk("지금 레벨 이하 기술 + 떠올리기 전용 기술이 전부 나온다",
        sorted(got) == sorted((low | remind) - {"TACKLE"}), (got, sorted(low), sorted(remind)))
    chk("아는 기술은 안 나온다", "TACKLE" not in got, got)
    chk("높은 레벨 기술은 안 나온다", not (high & set(got)), high & set(got))
    lvs = [x["level"] for x in lst["remember"]]
    chk("레벨 순서", lvs == sorted(lvs), lvs)
    chk("한글 이름이 붙는다",
        all(x["kr"] == d.move_name(x["move"]) for x in lst["remember"]))
    chk("값과 가진 돈을 같이 준다", lst["cost"] == cost and lst["money"] == 0,
        (lst["cost"], lst["money"]))
    chk("기다리던 기술이 없으면 공짜도 없다",
        not any(x["free"] for x in lst["remember"]))
    chk("남의 포켓몬은 못 본다",
        refused(lambda: R.remember_list(pid, {"user": {"id": uid + 999}}), 404))

    first = got[0]
    chk("돈이 없으면 못 떠올린다",
        refused(lambda: R.remember(Body(pokemon=pid, move=first, forget=""), me)))
    chk("  기술도 그대로", moves_of(pid) == ["TACKLE"], moves_of(pid))

    items.money_add(uid, 12000)
    r = R.remember(Body(pokemon=pid, move=first, forget=""), me)
    chk("자리가 있으면 그냥 떠올린다",
        r["ok"] and moves_of(pid) == ["TACKLE", first], (r, moves_of(pid)))
    chk("5,000원을 받는다", money() == 7000 and r["money"] == 7000, money())
    chk("  받은 값을 알려준다", r["cost"] == cost, r.get("cost"))
    chk("떠올렸다는 말", "떠올렸다" in r["message"], r["message"])

    if high:
        up = sorted(high)[0]
        chk("레벨이 모자란 기술은 못 떠올린다",
            refused(lambda: R.remember(Body(pokemon=pid, move=up, forget=""), me)))
    chk("이미 아는 기술은 못 떠올린다",
        refused(lambda: R.remember(Body(pokemon=pid, move=first, forget=""), me)))
    chk("도감에 없는 기술은 못 떠올린다",
        refused(lambda: R.remember(Body(pokemon=pid, move="NOPE", forget=""), me)))
    chk("  거절에는 돈을 안 받는다", money() == 7000, money())

    rest = [m for m in got if m != first]
    four = ["TACKLE", first, rest[0], rest[1]]
    db.run("UPDATE pokemon SET moves=? WHERE id=?", (json.dumps(four), pid))
    target = rest[2]
    r = R.remember(Body(pokemon=pid, move=target, forget=""), me)
    chk("네 개면 무엇을 잊을지 묻는다", r.get("needForget") and not r["ok"], r)
    chk("  묻기만 하고 돈은 안 받는다", money() == 7000, money())
    chk("  기술도 그대로", moves_of(pid) == four, moves_of(pid))
    chk("없는 기술을 잊으라면 거절",
        refused(lambda: R.remember(Body(pokemon=pid, move=target,
                                        forget="HYPERBEAM"), me)))
    chk("  돈은 그대로", money() == 7000, money())

    r = R.remember(Body(pokemon=pid, move=target, forget="TACKLE"), me)
    chk("잊고 떠올린다",
        moves_of(pid) == [target, first, rest[0], rest[1]], moves_of(pid))
    chk("  자리는 잊은 기술 자리", r["moves"][0] == target, r["moves"])
    chk("  잊은 기술을 알려준다", r["forgot"] == d.move_name("TACKLE"), r["forgot"])
    chk("  5,000원을 또 받는다", money() == 2000, money())

    chk("돈이 모자라면 못 떠올린다",
        refused(lambda: R.remember(Body(pokemon=pid, move="TACKLE",
                                        forget=first), me)))
    chk("  기술도 돈도 그대로",
        money() == 2000 and moves_of(pid) == [target, first, rest[0], rest[1]])

    print("\n=== 떠올리기로만 배우는 기술 (1.13 - '오거폰 떠올리기에 우드혼이 없다') ===")
    og = mkmon(uid, "OGERPON", ["IVYCUDGEL"], level=70)
    names = [x["move"] for x in R.remember_list(og, me)["remember"]]
    chk("오거폰: 우드혼 · 두번차기가 나온다 (본가 SV 의 떠올리기 목록)",
        {"HORNLEECH", "DOUBLEKICK"} <= set(names), names)
    chk("  레벨업 표에는 없다 (새로 생기는 포켓몬의 처음 기술은 그대로)",
        "HORNLEECH" not in [m for _lv, m in d.get("OGERPON")["moves"]])
    items.money_add(uid, cost)
    r = R.remember(Body(pokemon=og, move="HORNLEECH", forget=""), me)
    chk("  실제로 떠올린다", r["ok"] and "HORNLEECH" in moves_of(og), moves_of(og))
    # 1.13.0 에는 아기 포켓몬의 알 기술을 뺐다. 1.13.3 부터 교배가 없는 대신 **기술머신이 없는 알 기술은 전부
    # 떠올리기로** 배운다 (2026-10-20 사용자 결정, tools/add_reminder.py) - 피츄도.
    chk("기술머신이 없는 알 기술은 아기 포켓몬도 떠올리기로 (피츄 바라기 · 1.13.3)",
        "WISH" in (d.get("PICHU").get("remind") or []), d.get("PICHU").get("remind"))
    chk("  돈은 떠올린 만큼만", money() == 2000, money())
    # 1.13.4 (게시판 #291 니뉴, 사용자 결정 '메가 있는 종만'): 메가진화하는 종은 레전즈 Z-A 학습표에서 배울 길이
    # 없던 기술도 떠올리기로 - 메가픽시는 Z-A 의 메가라 픽시 Lv.52 에어슬래시를 바탕으로 짜였다.
    cf = mkmon(uid, "CLEFABLE", ["MOONBLAST"], level=10)
    names = [x["move"] for x in R.remember_list(cf, me)["remember"]]
    chk("메가가 있는 종: Z-A 학습표 기술도 떠올리기로 (픽시 에어슬래시 · 레벨 10 이어도)", "AIRSLASH" in names, names)
    fl = mkmon(uid, "FLOETTE", ["FAIRYWIND"], level=20)
    chk("플라엣테: 메가플라엣테의 전용기 파멸의빛을 떠올리기로 (게시판 #312 · 영원의 꽃 플라엣테를 합쳐 두었다)",
        "LIGHTOFRUIN" in [x["move"] for x in R.remember_list(fl, me)["remember"]])
    chk("  메가가 없는 종에는 안 붙는다 (삐삐 · 메가가 있는 종으로만 좁혔다)",
        "AIRSLASH" not in (d.get("CLEFAIRY").get("remind") or []), d.get("CLEFAIRY").get("remind"))
    chk("  옛 메가의 종도 (메가리자몽 - 리자몽 더블윙)", "DUALWINGBEAT" in (d.get("CHARIZARD").get("remind") or []),
        d.get("CHARIZARD").get("remind"))
    # 같은 날 니뉴 대댓글: 매지컬리프 · 매지컬플레임 · 이판사판태클은 Z-A 에서 픽시의 레벨업 기술인데, 이 게임에서는
    # 픽시가 그 기술머신으로 배울 수 있어서 떠올리기에서 뺐다 - 기술머신이 없으면 못 배운다. 레벨업 기술은 넣는다.
    chk("  Z-A 레벨업 기술은 기술머신으로 배울 수 있어도 떠올리기로 (픽시 매지컬리프 · 매지컬플레임 · 이판사판태클)",
        {"MAGICALLEAF", "MYSTICALFIRE", "DOUBLEEDGE"} <= set(names), names)
    gaps = za_level_gaps(d)
    if gaps is None:                                       # Z-A 학습표는 git 에 없는 캐시 - CI 에서는 위 대표 사례만
        print("  --   Z-A 학습표 캐시가 없어 전수 확인은 건너뜀 (tools/_cache/showdown_gen9legends_learnsets.ts)")
    else:
        chk("  메가가 있는 종의 Z-A 레벨업 기술은 빠짐없이 그 레벨까지 배울 수 있다 (레벨업 · 떠올리기)",
            not gaps, gaps[:5])

    print("\n=== 떠올리기 - 기다리던 기술은 공짜 ===")
    owed = rest[3]
    db.run("UPDATE pokemon SET pending=? WHERE id=?",
           (json.dumps([owed, "SPLASH"]), pid))
    lst = R.remember_list(pid, me)
    free = dict((x["move"], x) for x in lst["remember"] if x["free"])
    chk("기다리던 기술은 공짜로 표시", owed in free, sorted(free))
    chk("지금 표에 없는 기다리던 기술도 나온다 (레벨 없음)",
        "SPLASH" in free and free["SPLASH"]["level"] is None, free.get("SPLASH"))
    r = R.remember(Body(pokemon=pid, move=owed, forget=first), me)
    chk("돈이 모자라도 기다리던 기술은 떠올린다", r["ok"] and owed in r["moves"], r)
    chk("  돈을 안 받는다", money() == 2000 and r["cost"] == 0, (money(), r["cost"]))
    chk("  기다리는 목록에서 빠진다",
        json.loads(row(pid)["pending"]) == ["SPLASH"], row(pid)["pending"])

    print("\n=== 떠올리기 - 그사이 기술이 바뀌면 돈을 돌려준다 ===")
    items.money_add(uid, 8000)
    stale = row(pid)
    before = money()
    db.run("UPDATE pokemon SET moves=? WHERE id=?",
           (json.dumps(["TACKLE", "GROWL"]), pid))
    real_mon = R._mon
    R._mon = lambda _uid, _pid: stale
    try:
        cand = [x["move"] for x in R.remember_list(pid, me)["remember"]
                if not x["free"] and x["move"] not in ("TACKLE", "GROWL")][0]
        ok = refused(lambda: R.remember(Body(pokemon=pid, move=cand,
                                             forget=target), me), 409)
    finally:
        R._mon = real_mon
    chk("두 번 누른 것처럼 어긋나면 거절 (409)", ok)
    chk("  돈을 돌려준다", money() == before, (money(), before))
    chk("  기술은 바뀐 그대로", moves_of(pid) == ["TACKLE", "GROWL"], moves_of(pid))

    print("\n=== 떠올리기 - 진화할 때 배우는 기술 ===")
    zard = d.get("CHARIZARD")
    evo = [mv for lv, mv in zard["moves"] if lv == 0]
    cz = mkmon(uid, "CHARIZARD", ["SCRATCH"], level=36)
    got = dict((x["move"], x["level"]) for x in R.remember_list(cz, me)["remember"])
    chk("레벨 0(진화) 기술도 떠올린다",
        evo and all(got.get(m) == 0 for m in evo), (evo, got))


def fresh_checks(R, Body):
    """새 기술머신 (1.11.0) - 받은 것은 가방에서 볼 때까지 '새 것', 옛 것은 처음부터 본 것."""
    import sqlite3

    print("\n=== 새 기술머신 (1.11.0) ===")
    uid = mkuser("tm_new")
    me = {"user": {"id": uid}}
    chk("처음에는 새 것이 없다", tms.new_count(uid) == 0 and tms.unseen(uid) == set())
    tms.give(uid, 7)
    tms.give(uid, 9)
    chk("받은 것은 새 것이다 (둘)", tms.new_count(uid) == 2 and tms.unseen(uid) == {7, 9},
        tms.unseen(uid))
    tms.give(uid, 7)
    chk("  이미 가진 것을 또 받아도 늘지 않는다", tms.new_count(uid) == 2)
    r = R.my_tms(me)
    rows = dict((t["no"], t) for t in r["tms"])
    chk("/api/tms: 새 것에 new 가 붙는다", rows[7]["new"] and rows[9]["new"] and r["newCount"] == 2, r["newCount"])
    chk("  안 가진 것·다른 것에는 안 붙는다", not rows[1]["new"] and not rows[8]["new"])
    out = R.seen(Body(nos=[7]), me)
    chk("하나를 보면 그것만 꺼진다", out["newCount"] == 1 and tms.unseen(uid) == {9}, out)
    out = R.seen(Body(nos=[7, 7]), me)
    chk("  또 봐도 그대로 (본 것은 본 것)", out["newCount"] == 1, out)
    out = R.seen(Body(nos=[123]), me)
    chk("  안 가진 번호를 봐도 아무 일 없다", out["newCount"] == 1 and not tms.has(uid, 123), out)
    other = mkuser("tm_new2")
    tms.give(other, 9)
    R.seen(Body(nos=[9]), me)
    chk("  내가 본 것은 남의 것을 끄지 않는다", tms.new_count(other) == 1 and tms.new_count(uid) == 0,
        (tms.new_count(other), tms.new_count(uid)))
    tms.give(uid, 11)
    tms.give(uid, 12)
    out = R.seen(Body(nos=None), me)
    chk("nos 가 없으면 전부 본 것으로", out["newCount"] == 0 and tms.new_count(uid) == 0, out)
    chk("본다고 기술머신이 없어지지 않는다", tms.owned(uid) == {7, 9, 11, 12}, tms.owned(uid))
    chk("너무 많은 번호는 거절한다", refused(lambda: R.seen(Body(nos=list(range(400))), me)))

    # 1.10.x 의 DB: seen 칸이 없다. 붙이면 **옛 행은 본 것** - 올리자마자 가진 것 전부에 점이 뜨면 안 된다
    sql = [m[2] for m in db.MIGRATIONS if m[0] == "tm_owned" and m[1] == "seen"]
    chk("seen 칸을 붙이는 손질이 있다", len(sql) == 1, sql)
    old = sqlite3.connect(":memory:")
    old.execute("CREATE TABLE tm_owned (user_id INTEGER NOT NULL, no INTEGER NOT NULL,"
                " got_at TEXT NOT NULL, PRIMARY KEY (user_id, no))")
    old.execute("INSERT INTO tm_owned VALUES (1, 5, '2026-10-01')")
    old.execute(sql[0])
    chk("  옛 행은 seen=1 (새 것이 아니다)",
        old.execute("SELECT seen FROM tm_owned").fetchone()[0] == 1)

    # /api/me 에 수가 실린다 (가방 탭의 점)
    import inspect
    from app import main as M
    src = inspect.getsource(M.me)
    chk("/api/me 에 tmNew 가 실린다", '"tmNew": tms.new_count(uid)' in src)


def main():
    db.init()
    d = deps.dex()

    print("=== 자료 ===")
    n = tms.count()
    chk("기술머신이 358개", n == 358, n)
    chk("1번이 있다", tms.get(1) is not None)
    chk("없는 번호는 None", tms.get(9999) is None)
    t1 = tms.get(1)
    chk("기술 내부이름이 도감에 있다", t1["move"] in d.moves, t1["move"])
    bad = [no for no, t in tms.all_tms().items() if t["move"] not in d.moves]
    chk("358개가 전부 도감에 있는 기술", not bad, bad[:5])
    chk("이름이 읽을 만하다", tms.label(1).startswith("기술머신001"), tms.label(1))

    print("\n=== 알 기술도 그 기술의 기술머신으로 배운다 (1.10.3, 게시판 #156) ===")
    roost = [no for no, t in tms.all_tms().items() if t["move"] == "ROOST"]
    chk("날개쉬기 기술머신이 있다", len(roost) == 1, roost)
    r = roost[0]
    chk("**아머까오가 날개쉬기를 배운다** (원작에서는 파라꼬의 알 기술 - 교배가 없으니 기술머신으로)",
        tms.can_learn(823, r))
    chk("  진화 전 단계의 알 기술은 진화형도 배운다 (파라꼬 -> 파크로우 -> 아머까오)", tms.can_learn(821, r) and tms.can_learn(822, r))
    chk("  팽도리 계열·윽우지·떨구새도", all(tms.can_learn(n, r) for n in (393, 394, 395, 845, 962)))
    chk("  원작에서 어떤 길로도 못 배우는 종은 여전히 못 배운다 (갸라도스·레쿠쟈)", not tms.can_learn(130, r) and not tms.can_learn(384, r))
    c = tms.data()["counts"]
    chk("  자료에 알 기술 · 가르침 기술 · Z-A 전용 · 떠올리기로 들어간 줄 수가 적혀 있다 (전 세대 기술머신 61463줄 + 알 기술 + "
        "최신작 가르침 1.13.3 + Z-A 전용 기술머신 1.13.4 + 떠올리기 기술 2.0)",
        c.get("eggRows", 0) > 1000 and c.get("tutorRows", 0) > 200 and c.get("zaRows", 0) > 400
        and c.get("remindRows", 0) > 200
        and c["rows"] == 61463 + c["eggRows"] + c["tutorRows"] + c["zaRows"] + c["remindRows"], c)
    chk("  기술머신의 수는 그대로다 (새 기술머신을 만들지 않는다)", tms.count() == 358)

    # 1.13.4 (게시판 #313 Leica '더블촙 기술머신을 배울 수 있는 포켓몬이 없다'): 레전즈 Z-A · 메가디멘션에만 있는
    # 기술머신 18개는 PokeAPI 에 호환 자료가 없어 더블촙 · 마그넷봄은 0종이었다 - 쇼다운 Z-A 학습표의 기술머신 기록으로.
    learners = {}
    for num, nos in tms.data()["learn"].items():
        for no in nos:
            learners.setdefault(no, set()).add(int(num))
    by_move = dict((t["move"], no) for no, t in tms.all_tms().items())
    za_only = tms.data().get("zaOnly") or []
    chk("Z-A 전용 기술머신 18개가 적혀 있다", len(za_only) == 18, za_only)
    chk("  배울 수 있는 포켓몬이 없는 기술머신이 없다 (더블촙 · 마그넷봄이 0종이었다)",
        all(learners.get(no) for no in tms.all_tms()), [no for no in tms.all_tms() if not learners.get(no)])
    chk("  괴력몬 · 루카리오가 더블촙, 라이츄 · 로토무가 마그넷봄을 기술머신으로 (Z-A 의 기술머신)",
        tms.can_learn(68, by_move["DUALCHOP"]) and tms.can_learn(448, by_move["DUALCHOP"])
        and tms.can_learn(26, by_move["MAGNETBOMB"]) and tms.can_learn(479, by_move["MAGNETBOMB"]))
    chk("  본편 기술머신은 안 건드린다 (킬가르도는 폴터가이스트를 여전히 못 배운다 - 본편 최신작 · Z-A 둘 다 못 배운다)",
        not tms.can_learn(681, by_move["POLTERGEIST"]))

    # 2.0 (게시판 #382 '번치코 떠올리기에는 드레인펀치가 있는데 기술머신에는 번치코가 안 나온다'): 떠올리기로 배우는
    # 기술에 기술머신이 있으면 그 기술머신으로도 배운다 (tools/build_tms.py '떠올리기 기술'). 새로 배우는 기술은 없다.
    print("\n=== 떠올리기 기술은 그 기술머신으로도 (2.0, 게시판 #382) ===")
    chk("번치코가 드레인펀치 기술머신으로 배운다 (떠올리기에 있다)",
        "DRAINPUNCH" in (d.get("BLAZIKEN").get("remind") or []) and tms.can_learn(257, by_move["DRAINPUNCH"]))
    gap = [(s["internal"], mv) for s in d.raw["species"] for mv in s.get("remind") or []
           if mv in by_move and not tms.can_learn(s["num"], by_move[mv])]
    chk("  떠올리기 기술인데 그 기술머신으로 못 배우는 종이 없다", not gap, gap[:5])
    fr = tms.data().get("fromRemind") or {}
    chk("  그렇게 들어간 줄이 fromRemind 에 적혀 있다 (add_reminder 가 기술머신으로 치지 않게)",
        sum(len(v) for v in fr.values()) == c["remindRows"] and 73 in fr.get("257", []), (len(fr), c["remindRows"]))
    chk("  떠올리기에 없는 기술은 안 연다 (영치코 · 아차모는 드레인펀치를 여전히 못 배운다)",
        not tms.can_learn(256, by_move["DRAINPUNCH"]) and not tms.can_learn(255, by_move["DRAINPUNCH"]))

    print("\n=== 누가 배울 수 있나 ===")
    # 이상해씨(1) 는 배울 게 많고, 메타몽(132) 은 하나도 못 배운다.
    chk("이상해씨는 배울 게 있다", len(tms.learnable(1)) > 10,
        len(tms.learnable(1)))
    chk("메타몽은 하나도 못 배운다", tms.learnable(132) == [],
        tms.learnable(132))
    chk("모르는 종은 빈 목록", tms.learnable(99999) == [])
    some = tms.learnable(1)[0]
    chk("배울 수 있다고 나온다", tms.can_learn(1, some))
    cant = [n for n in range(1, 359) if n not in set(tms.learnable(1))]
    chk("못 배우는 것은 못 배운다고 나온다", not tms.can_learn(1, cant[0]))

    print("\n=== 갖고 있는가 ===")
    uid = mkuser("tm_a")
    chk("처음에는 하나도 없다", tms.owned(uid) == set())
    chk("주면 True", tms.give(uid, 5) is True)
    chk("갖고 있다", tms.has(uid, 5))
    chk("또 주면 False (두 번 세지 않는다)", tms.give(uid, 5) is False)
    chk("여전히 하나", tms.owned(uid) == {5}, tms.owned(uid))

    print("\n=== 상점에 안 뜬다 ===")
    shop = items.public_list()
    ids = set(x["id"] for x in shop)
    tmish = [i for i in ids if i.upper().startswith("TM")]
    chk("도구 목록에 기술머신이 없다", not tmish, tmish[:5])
    chk("드랍표에도 없다",
        not [i for i, _w in items.data()["dropTable"]
             if i.upper().startswith("TM")])

    print("\n=== 배우기 ===")
    from app import tm_routes as R

    class Body(object):
        def __init__(self, **kw):
            self.__dict__.update(kw)

    me = {"user": {"id": uid}}
    # 이상해씨가 배울 수 있는 것 하나를 고른다
    no = tms.learnable(1)[0]
    tms.give(uid, no)
    mv = tms.get(no)["move"]

    pid = mkmon(uid, "BULBASAUR", ["TACKLE"])
    r = R.use(Body(no=no, pokemon=pid, forget=""), me)
    chk("자리가 있으면 그냥 배운다", r["ok"] and mv in r["moves"], r)
    chk("기술이 두 개가 됐다", len(r["moves"]) == 2, r["moves"])

    # 써도 없어지지 않는다
    chk("쓴 뒤에도 갖고 있다 (영구제)", tms.has(uid, no))

    # 같은 것을 또
    try:
        R.use(Body(no=no, pokemon=pid, forget=""), me)
        ok = False
    except Exception as e:
        ok = "이미" in str(e)
    chk("이미 아는 기술은 막는다", ok)

    print("\n=== 네 개가 차 있으면 물어본다 ===")
    pid2 = mkmon(uid, "BULBASAUR", ["TACKLE", "GROWL", "VINEWHIP", "GROWTH"])
    r = R.use(Body(no=no, pokemon=pid2, forget=""), me)
    chk("바로 안 배우고 물어본다",
        r.get("needForget") is True and not r.get("ok"), r)
    row = db.q1("SELECT moves FROM pokemon WHERE id=?", (pid2,))
    chk("아직 안 바뀌었다", json.loads(row["moves"]) == [
        "TACKLE", "GROWL", "VINEWHIP", "GROWTH"], row["moves"])

    r = R.use(Body(no=no, pokemon=pid2, forget="GROWL"), me)
    chk("고른 것을 잊고 배운다",
        r["ok"] and mv in r["moves"] and "GROWL" not in r["moves"], r["moves"])
    chk("여전히 네 개", len(r["moves"]) == 4, r["moves"])
    chk("고르지 않은 것은 그대로",
        "TACKLE" in r["moves"] and "VINEWHIP" in r["moves"], r["moves"])

    try:
        R.use(Body(no=no, pokemon=pid2, forget="NOSUCHMOVE"), me)
        ok = False
    except Exception:
        ok = True
    chk("갖고 있지 않은 기술은 못 잊는다", ok)

    print("\n=== 서버가 막아야 하는 것 ===")
    # 안 가진 기술머신
    notmine = [n for n in range(1, 359) if n not in tms.owned(uid)][0]
    try:
        R.use(Body(no=notmine, pokemon=pid, forget=""), me)
        ok = False
    except Exception as e:
        ok = "갖고 있지" in str(e)
    chk("안 가진 기술머신은 못 쓴다", ok)

    # 그 종이 못 배우는 기술
    cant_no = [n for n in range(1, 359)
               if not tms.can_learn(1, n)][0]
    tms.give(uid, cant_no)
    try:
        R.use(Body(no=cant_no, pokemon=pid, forget=""), me)
        ok = False
    except Exception as e:
        ok = "배울 수 없" in str(e)
    chk("그 종이 못 배우는 기술은 막는다", ok)

    # 남의 포켓몬
    other = mkuser("tm_b")
    opid = mkmon(other, "BULBASAUR", ["TACKLE"])
    try:
        R.use(Body(no=no, pokemon=opid, forget=""), me)
        ok = False
    except Exception:
        ok = True
    chk("남의 포켓몬에는 못 쓴다", ok)

    print("\n=== 레벨업: 말없이 밀어내지 않는다 ===")
    sp = d.get("BULBASAUR")
    pid3 = mkmon(uid, "BULBASAUR", ["TACKLE", "GROWL", "VINEWHIP", "GROWTH"],
                 level=1)
    moves, learned, pending = deps._learn(
        sp, ["TACKLE", "GROWL", "VINEWHIP", "GROWTH"], 1, 50, [])
    chk("기술은 그대로 네 개", len(moves) == 4, moves)
    chk("아무것도 안 잊었다",
        moves == ["TACKLE", "GROWL", "VINEWHIP", "GROWTH"], moves)
    chk("배울 것이 기다린다", len(pending) > 0, pending)
    chk("방금 배운 것은 없다", learned == [], learned)

    # 자리가 있으면 그냥 배운다
    moves, learned, pending = deps._learn(sp, ["TACKLE"], 1, 50, [])
    chk("자리가 있으면 채운다", len(moves) == 4, moves)
    chk("배운 것을 알려준다", len(learned) == 3, learned)
    chk("네 개를 채운 뒤 남은 것은 기다린다", len(pending) > 0, pending)

    # 같은 기술이 두 번 들어가지 않는다
    moves, learned, pending = deps._learn(sp, ["TACKLE"], 1, 50, [])
    chk("중복이 없다", len(set(moves)) == len(moves), moves)
    chk("기다리는 것에도 중복이 없다", len(set(pending)) == len(pending), pending)
    chk("기다리는 것이 이미 아는 기술이 아니다",
        not (set(pending) & set(moves)), (pending, moves))

    print("\n=== 기다리던 것 고르기 ===")
    db.run("UPDATE pokemon SET moves=?, pending=? WHERE id=?",
           (json.dumps(["TACKLE", "GROWL", "VINEWHIP", "GROWTH"]),
            json.dumps(["SOLARBEAM"]), pid3))
    r = R.learn(Body(pokemon=pid3, move="SOLARBEAM", forget="GROWL",
                     skip=False), me)
    chk("잊고 배운다",
        "SOLARBEAM" in r["moves"] and "GROWL" not in r["moves"], r["moves"])
    chk("기다리는 것이 비었다", r["pending"] == [], r["pending"])

    # 안 배우기
    db.run("UPDATE pokemon SET moves=?, pending=? WHERE id=?",
           (json.dumps(["TACKLE", "GROWL", "VINEWHIP", "GROWTH"]),
            json.dumps(["SOLARBEAM"]), pid3))
    r = R.learn(Body(pokemon=pid3, move="SOLARBEAM", forget="", skip=True), me)
    chk("안 배우면 기술이 그대로",
        r["moves"] == ["TACKLE", "GROWL", "VINEWHIP", "GROWTH"], r["moves"])
    chk("그래도 기다리는 목록에서는 빠진다", r["pending"] == [], r["pending"])

    try:
        R.learn(Body(pokemon=pid3, move="SOLARBEAM", forget="", skip=True), me)
        ok = False
    except Exception:
        ok = True
    chk("기다리지 않는 기술은 못 배운다", ok)

    print("\n=== 배울 수 있는 포켓몬을 한 번에 ===")
    # 마리마다 물어보면 예순 마리면 예순 번이다.
    r = R.learners(no, me)
    ids = [x["id"] for x in r["learners"]]
    chk("배울 수 있는 애만 나온다", pid in ids and pid2 in ids, ids)
    allmons = db.q("SELECT id FROM pokemon WHERE user_id=?", (uid,))
    chk("못 배우는 애는 빠진다", len(ids) <= len(allmons), (len(ids), len(allmons)))
    chk("이미 배웠는지 알려준다",
        any(x["known"] for x in r["learners"]), r["learners"][:2])
    chk("남의 포켓몬은 안 나온다", opid not in ids, ids)
    try:
        R.learners(9999, me)
        ok = False
    except Exception:
        ok = True
    chk("없는 번호는 막는다", ok)

    print("\n=== 드랍 ===")
    rng = random.Random(1)
    uid2 = mkuser("tm_c")
    got = [tms.roll_drop(rng, species_num=1, uid=uid2) for _ in range(4000)]
    hits = [g for g in got if g is not None]
    rate = len(hits) / 4000.0
    chk("확률이 설정값 근처 (%.3f)" % rate,
        abs(rate - tms.DROP_CHANCE) < 0.02, rate)
    allno = set(tms.all_tms())
    chk("358개 전체에서 나온다 (종으로 안 좁힌다)",
        all(h in allno for h in hits) and len(set(hits)) > 60,
        len(set(hits)))
    can = set(tms.learnable(1))
    chk("잡은 종이 못 배우는 것도 나온다",
        any(h not in can for h in hits))

    # 이미 가진 것은 안 나온다
    for h in set(hits):
        tms.give(uid2, h)
    again = [tms.roll_drop(rng, species_num=1, uid=uid2) for _ in range(2000)]
    dup = [g for g in again if g is not None and tms.has(uid2, g)]
    chk("이미 가진 것은 다시 안 나온다", not dup, dup[:5])

    # 다 모으면 안 나온다
    uid3 = mkuser("tm_d")
    for n in tms.all_tms():
        tms.give(uid3, n)
    full = [tms.roll_drop(rng, species_num=1, uid=uid3) for _ in range(500)]
    chk("다 모았으면 안 나온다", all(f is None for f in full))

    fresh_checks(R, Body)
    remember_checks(d, R, Body)

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
