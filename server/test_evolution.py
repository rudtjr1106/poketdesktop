# -*- coding: utf-8 -*-
"""교환진화 — 교환이 없는 게임이라 도구 쓰기로 바뀌어 있다.

조건 없는 통신교환은 '연결의끈', 지닌 물건이 있던 교환은 그 물건을
가방에서 쓰면 진화한다 (tools/build_pokedex.py). 여기서 못 박는 것은 넷이다.

  1. **통신교환 갈래는 전부 살 수 있는 도구로 이어진다.** 도구가 목록에서
     빠지거나 못 사게 되면 그 종은 영영 진화하지 못한다.
  2. **맞는 도구만 진화시킨다.** 윤겔라에게 금속코트는 아무 일도 없다.
  3. **쓰면 진화하고 도구는 딱 하나 준다.** 안 맞으면 안 준다.
  4. **지니게 한 도구로는 못 쓴다.** 가방에서 빠져 있기 때문이다 - 그래서
     클라이언트가 지니게 할 때 미리 말해 준다 (ui_box.HeldPicker).

서버를 띄우지 않는다. DB 와 모듈만 직접 쓴다.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-evo-")
# **setdefault 로 두지 않는다.** 서버 컨테이너 안에서 돌리면 POKET_DB 가
# 이미 서버 DB 로 잡혀 있어서, 그걸 따르면 돌고 있는 서버의 DB 에 사용자를
# 만든다. 원격 DB(Turso)도 같은 까닭으로 끈다.
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
# 도감·도구 목록도 이 저장소 것을 본다. 이미지에 구워 둔 옛 자료를 보면
# 여기서 고친 자료를 검사하지 못한다.
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                          # noqa: E402

from app import db, deps, evolution, items                 # noqa: E402

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


def mkmon(uid, species, held=None):
    return db.insert_mon(uid, {
        "species": species, "level": 30, "exp": 0, "nature": "HARDY",
        "ability": "SYNCHRONIZE", "hiddenAbility": False, "gender": "M",
        "shiny": False, "happiness": 70, "ivs": {}, "evs": {},
        "moves": ["TACKLE"], "hyper": {}, "noEvolve": False,
        "luxury": False, "held": held}, "2026-01-01")


def bare(species):
    """DB 없이 check_item 에 넘길 포켓몬. 성별·기술·능력 조건이 없는 갈래만 본다."""
    return {"species": species, "level": 30, "gender": "M", "moves": ["TACKLE"],
            "ivs": {}, "evs": {}, "nature": "HARDY"}


def species_of(pid):
    return db.q1("SELECT species FROM pokemon WHERE id=?", (pid,))["species"]


def status_of(fn):
    """HTTPException 이 나면 그 상태 코드, 안 나면 None."""
    try:
        fn()
    except HTTPException as e:
        return e.status_code
    return None


def main():
    db.init()
    d = deps.dex()
    cat = items.catalog()
    shop = dict((x["id"], x) for x in items.public_list())

    print("=== 통신교환 갈래는 전부 살 수 있는 도구로 ===")
    trade = [(sp, b) for sp in d.species for b in (sp.get("evo") or [])
             if b.get("wasTrade")]
    chk("통신교환 갈래가 26개", len(trade) == 26, len(trade))

    def tag(sp, b):
        return "%s->%s(%s)" % (sp["kr"], d.name(b["to"]), b.get("item"))

    bad = [tag(sp, b) for sp, b in trade
           if b.get("mode") != "stone" or b.get("item") not in cat]
    chk("전부 '돌' 갈래이고 도구가 목록에 있다", not bad, bad[:5])
    # 가방의 '쓰기' 는 effect.kind 로 갈린다. 'stone' 이 아니면 _use_stone
    # 까지 가지도 못한다.
    bad = [tag(sp, b) for sp, b in trade
           if (cat.get(b.get("item")) or {}).get("cat") != "stone"
           or ((cat.get(b.get("item")) or {}).get("effect") or {}).get("kind") != "stone"]
    chk("그 도구는 전부 cat=stone 이고 쓰면 진화 도구로 돈다", not bad, bad[:5])
    bad = [tag(sp, b) for sp, b in trade
           if not (shop.get(b.get("item")) or {}).get("buyable")
           or items.buy_price(b.get("item")) <= 0]
    chk("그 도구는 전부 상점에서 살 수 있다", not bad, bad[:5])
    # 가방은 도구의 evolves 에 종 이름이 있어야 그 포켓몬을 '진화할 수 있다'
    # 로 짚는다 (ui_bag). 빠지면 도구를 가져도 누구에게 쓸지 모른다.
    bad = [tag(sp, b) for sp, b in trade
           if sp["kr"] not in ((cat.get(b.get("item")) or {}).get("evolves") or [])]
    chk("가방이 그 종을 '진화할 수 있다' 로 짚는다 (evolves)", not bad, bad[:5])
    bad = [tag(sp, b) for sp, b in trade
           if (evolution.check_item(d, bare(sp["internal"]), b["item"], hour=12)
               or {}).get("to") != b["to"]]
    chk("그 도구를 쓰면 26갈래 모두 그 종으로 진화한다", not bad, bad[:5])

    print("\n=== 맞는 도구만 진화시킨다 ===")
    for sp_key, item, to in (("KADABRA", "LINKINGCORD", "ALAKAZAM"),
                             ("ONIX", "METALCOAT", "STEELIX"),
                             ("POLIWHIRL", "KINGSROCK", "POLITOED"),
                             # 원래 쪼마리와 맞바꾸던 것. 상대 종은 안 본다.
                             ("KARRABLAST", "LINKINGCORD", "ESCAVALIER")):
        b = evolution.check_item(d, bare(sp_key), item, hour=12)
        chk("%s + %s -> %s" % (d.name(sp_key), items.name_of(item), d.name(to)),
            b is not None and b["to"] == to, b)
    chk("윤겔라 + 금속코트 -> 아무 일도 없다",
        evolution.check_item(d, bare("KADABRA"), "METALCOAT", hour=12) is None)

    print("\n=== _use_stone 이 진화시킨다 ===")
    from app import item_routes as R

    uid = mkuser("evo_a")
    me = {"user": {"id": uid}}
    pid = mkmon(uid, "POLIWHIRL")
    out = R._use_stone(uid, items.get("KINGSROCK"), R._mon(uid, pid), d, 12)
    chk("슈륙챙이 + 왕의징표석 -> 왕구리로 진화했다고 답한다",
        out.get("ok") and out["evolve"]["to"] == "POLITOED", out)
    chk("DB 에서도 왕구리", species_of(pid) == "POLITOED", species_of(pid))

    print("\n=== 가방에서 쓰면 진화하고 도구는 딱 하나 준다 ===")
    pid = mkmon(uid, "KADABRA")
    items.bag_add(uid, "LINKINGCORD", 2)
    r = R.use(R.UseIn(item="LINKINGCORD", pokemon=pid, hour=12), me)
    chk("윤겔라 + 연결의끈 -> 후딘", (r.get("evolve") or {}).get("to") == "ALAKAZAM",
        r.get("evolve"))
    chk("DB 에서도 후딘", species_of(pid) == "ALAKAZAM", species_of(pid))
    chk("연결의끈이 하나만 줄었다 (2 -> 1)",
        items.bag_count(uid, "LINKINGCORD") == 1, items.bag_count(uid, "LINKINGCORD"))
    chk("답에 실린 가방도 1", (r.get("bag") or {}).get("LINKINGCORD") == 1, r.get("bag"))
    code = status_of(lambda: R.use(R.UseIn(item="LINKINGCORD", pokemon=pid,
                                           hour=12), me))
    chk("후딘에게 또 쓰면 아무 일도 없다 (400)", code == 400, code)
    chk("그때는 안 준다", items.bag_count(uid, "LINKINGCORD") == 1,
        items.bag_count(uid, "LINKINGCORD"))

    items.bag_add(uid, "METALCOAT", 1)
    wrong = mkmon(uid, "KADABRA")
    code = status_of(lambda: R.use(R.UseIn(item="METALCOAT", pokemon=wrong,
                                           hour=12), me))
    chk("윤겔라에게 금속코트는 400", code == 400, code)
    chk("안 맞으면 도구가 그대로", items.bag_count(uid, "METALCOAT") == 1,
        items.bag_count(uid, "METALCOAT"))
    chk("윤겔라도 그대로", species_of(wrong) == "KADABRA", species_of(wrong))
    onix = mkmon(uid, "ONIX")
    r = R.use(R.UseIn(item="METALCOAT", pokemon=onix, hour=12), me)
    chk("롱스톤 + 금속코트 -> 강철톤", species_of(onix) == "STEELIX", species_of(onix))
    chk("금속코트가 하나만 줄었다 (1 -> 0)", items.bag_count(uid, "METALCOAT") == 0,
        items.bag_count(uid, "METALCOAT"))

    print("\n=== 지니게 한 도구로는 못 쓴다 ===")
    # 본가 버릇대로 롱스톤에게 금속코트를 지니게 하면 가방에서 빠진다.
    # 서버는 가방에 있는 것만 쓰므로 진화하지 않는다 - 벗겨서 가방으로
    # 돌린 뒤 써야 한다. 클라이언트는 지니게 할 때 이걸 미리 알린다.
    uid2 = mkuser("evo_b")
    held = mkmon(uid2, "ONIX", held="METALCOAT")
    code = status_of(lambda: R.use(R.UseIn(item="METALCOAT", pokemon=held,
                                           hour=12), {"user": {"id": uid2}}))
    chk("지니고만 있으면 쓸 수 없다 (400)", code == 400, code)
    chk("롱스톤 그대로", species_of(held) == "ONIX", species_of(held))

    print()
    print("=== 진화한 종도 도감에 올라간다 ===")
    # 도감(seen)은 잡을 때만 올리고 있어서 키워서 얻은 종이 빠졌다.
    def seen_row(u, sp):
        return db.q1("SELECT caught, first_at FROM seen WHERE user_id=? AND species=?",
                     (u, sp))

    uid3 = mkuser("evo_dex")
    me3 = {"user": {"id": uid3}}
    items.bag_add(uid3, "LINKINGCORD", 1)
    kad = mkmon(uid3, "KADABRA")
    R.use(R.UseIn(item="LINKINGCORD", pokemon=kad, hour=12), me3)
    row = seen_row(uid3, "ALAKAZAM")
    chk("가방에서 도구로 진화하면 후딘이 도감에 '잡음' 으로",
        bool(row) and row["caught"] == 1, dict(row) if row else row)

    # 레벨업 진화는 deps.try_evolve 가 now="" 로 부른다. 빈 시각이 그대로
    # first_at 에 박히면 안 된다.
    char = mkmon(uid3, "CHARMANDER")
    mon = db.row_to_mon(db.q1("SELECT * FROM pokemon WHERE id=?", (char,)))
    br = evolution.check_level(d, mon, 12)
    chk("Lv30 파이리는 레벨 진화 갈래가 있다", bool(br), br)
    if br:
        evolution.apply(uid3, mon, br, d, "")
        row = seen_row(uid3, br["to"])
        chk("레벨업 진화도 도감에 '잡음' 으로", bool(row) and row["caught"] == 1,
            dict(row) if row else row)
        chk("시각이 비어 있지 않다", bool(row) and bool(row["first_at"]),
            dict(row) if row else row)

    print()
    print("=== 이미 진화해 둔 사람 몫을 채운다 (migrations) ===")
    from app import migrations
    uid4 = mkuser("evo_old")
    old1 = mkmon(uid4, "VENUSAUR")                 # 도감 줄이 아예 없다
    mkmon(uid4, "IVYSAUR")                         # '봄' 으로만 있다
    db.run("INSERT INTO seen (user_id, species, caught, first_at) VALUES (?,?,0,?)",
           (uid4, "IVYSAUR", "2025-12-31"))
    other = mkuser("evo_other")                    # 남의 도감은 안 건드린다
    db.run("INSERT INTO seen (user_id, species, caught, first_at) VALUES (?,?,0,?)",
           (other, "MEW", "2025-12-31"))
    conn = db.connect()
    note = migrations._dex_evolved(conn)
    conn.commit()
    chk("손질이 무엇을 했는지 적는다", "도감" in (note or ""), note)
    row = seen_row(uid4, "VENUSAUR")
    chk("없던 종은 '잡음' 으로 생긴다", bool(row) and row["caught"] == 1,
        dict(row) if row else row)
    chk("시각은 그 포켓몬을 가진 시각", bool(row) and row["first_at"] == "2026-01-01",
        dict(row) if row else row)
    row = seen_row(uid4, "IVYSAUR")
    chk("'봄' 으로만 있던 종은 '잡음' 으로 오른다",
        bool(row) and row["caught"] == 1, dict(row) if row else row)
    chk("원래 처음 본 시각은 그대로", bool(row) and row["first_at"] == "2025-12-31",
        dict(row) if row else row)
    row = seen_row(other, "MEW")
    chk("가지지 않은 종은 그대로 '봄'", bool(row) and row["caught"] == 0,
        dict(row) if row else row)
    n1 = db.q1("SELECT COUNT(*) AS n FROM seen")["n"]
    conn = db.connect()
    migrations._dex_evolved(conn)
    conn.commit()
    n2 = db.q1("SELECT COUNT(*) AS n FROM seen")["n"]
    chk("두 번 돌아도 줄이 안 는다", n1 == n2, (n1, n2))
    chk("손질 목록에 올라 있다",
        any(name == "0250-dex-evolved" for name, _fn in migrations.ONCE),
        [name for name, _fn in migrations.ONCE])
    del old1

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
