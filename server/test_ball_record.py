# -*- coding: utf-8 -*-
"""잡은 볼 기록 (pokemon.ball, 2.5.8 - 게시판 #909 '마스터볼이 사라졌다': 어디에 썼는지 남은 것이 없었다).

    cd server && POKET_DB=/tmp/x.db python test_ball_record.py

  1. 옛 DB 에도 칸이 붙는다 (마이그레이션 - 새 DB 도 같은 길)
  2. store_caught(uid, mon, ball) 이 그 볼을 적는다 · 볼 없이(알 · 탐험 · 선물) 넣으면 NULL · 이상한 글은 안 적는다
  3. 넣은 포켓몬 dict 는 그대로다 ('_ball' 이 남지 않는다 - 화면 · 배틀에 새지 않게)
  4. 잡는 길 셋(야생 볼 · 바탕화면 배틀 · 아르케 전설)이 다 던진 볼을 넘긴다
"""
import inspect
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("POKET_DB", os.path.join(tempfile.mkdtemp(prefix="poket-ball-"), "t.db"))
os.environ.setdefault("POKET_POKEDEX", os.path.join(HERE, "data", "pokedex.json"))

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def main():
    # pokemon 표를 만드는 글(CREATE TABLE)에는 ball 칸이 없다 - 마이그레이션이 붙인다 (옛 DB 와 같은 길)
    from app import db, battle_routes, deps, main as M, arche
    from common import pokelogic as P
    import random
    db.init()
    conn = db.connect()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(pokemon)")]
    chk("1. pokemon 표에 ball 칸이 있다", "ball" in cols, cols)
    uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at, last_login, last_ip)"
                 " VALUES ('볼기록', ?, ?, 1, 30, 0, '2026-11-25T00:00:00+00:00', '2026-11-25T00:00:00+00:00', '')",
                 (b"x", b"x")).lastrowid
    d = deps.dex()
    rng = random.Random(1)

    def mk(sp):
        return P.make_pokemon(d.get(sp), 30, rng)
    m1 = mk("PIKACHU")
    got, _w = battle_routes.store_caught(uid, m1, "MASTERBALL")
    r = db.q1("SELECT ball FROM pokemon WHERE id=?", (got["id"],))
    chk("2. 잡은 볼이 남는다 (MASTERBALL)", r["ball"] == "MASTERBALL", dict(r))
    got2, _w = battle_routes.store_caught(uid, mk("EEVEE"))
    chk("   볼 없이 넣으면 NULL", db.q1("SELECT ball FROM pokemon WHERE id=?", (got2["id"],))["ball"] is None)
    got3, _w = battle_routes.store_caught(uid, mk("ODDISH"), "ultraball")
    chk("   열쇠는 대문자로", db.q1("SELECT ball FROM pokemon WHERE id=?", (got3["id"],))["ball"] == "ULTRABALL")
    got4, _w = battle_routes.store_caught(uid, mk("ZUBAT"), "x'; DROP TABLE pokemon; --")
    chk("   열쇠 꼴이 아닌 글은 적지 않는다", db.q1("SELECT ball FROM pokemon WHERE id=?", (got4["id"],))["ball"] is None)
    chk("3. 넣은 포켓몬 dict 에 '_ball' 이 남지 않는다", "_ball" not in m1 and "_ball" not in got, (sorted(m1), sorted(got)))
    eid = db.insert_mon(uid, mk("MEW"), "2026-11-25T00:00:00+00:00")
    chk("   알 · 탐험 · 선물처럼 insert_mon 을 바로 부르면 NULL", db.q1("SELECT ball FROM pokemon WHERE id=?", (eid,))["ball"] is None)

    src_main = inspect.getsource(M)
    src_bt = inspect.getsource(battle_routes)
    src_ar = inspect.getsource(arche.throw_ball)
    chk("4. 야생 볼 던지기가 던진 볼을 넘긴다", "store_caught(uid, mon, ball_id)" in src_main)
    chk("   바탕화면 배틀에서 잡기도", "store_caught(uid, foe.mon, ball)" in src_bt)
    chk("   아르케 전설 잡기도", "store_caught(uid, mon, ball)" in src_ar)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
