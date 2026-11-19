# -*- coding: utf-8 -*-
"""관장 이사 손질 0380 (시즌 5 챔피언 지우: 청주시 상당구 -> 동대문구, 동백: 동대문구 -> 청주시 상당구).

    python server/test_gym_move.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙인다. 못 박는 것:

  1. 동대문구(11230)에서 동백을 이긴 기록은 청주시 상당구(43111)로 옮겨 간다 (승수 · 최단 턴 · 날짜 그대로).
  2. 새 동대문구 지우는 모두가 다시 깬다 - 동대문구 기록은 하나도 안 남는다.
  3. 청주시 상당구에서 옛 지우를 이긴 기록은 지운다 (동백을 이긴 사람은 옮겨 온 기록이 대신 남는다).
  4. 다른 지역 기록은 그대로. 두 자리에서 하던 판은 접고, 다른 판은 그대로.
  5. gyms.json 도 그렇게 바뀌어 있다 (지우 11230, 동백 43111, 옛 지우 없음).
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-gym-move-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import db, migrations  # noqa: E402

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
    return db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,?,?,'')",
        (name, b"x", b"x", "2026-01-01", "2026-01-01")).lastrowid


def clear(uid, region, trainer, wins=1, turns=20):
    db.run("INSERT INTO gym_clear (user_id, region, trainer, wins, best_turns, first_at, last_at, paid_on)"
           " VALUES (?,?,?,?,?,?,?,?)", (uid, region, trainer, wins, turns, "2026-11-01", "2026-11-10", "2026-11-10"))


def fight(uid, region, trainer, state="active"):
    return db.run("INSERT INTO gym_battle (user_id, region, trainer, state, turn, rev, data, created_at, updated_at)"
                  " VALUES (?,?,?,?,0,0,'{}',?,?)", (uid, region, trainer, state, "2026-11-18", "2026-11-18")).lastrowid


def regions_of(uid):
    return {r["region"]: dict(r) for r in db.q("SELECT * FROM gym_clear WHERE user_id=?", (uid,))}


def main():
    db.init()
    print("=== 관장 이사 0380 ===")
    only_melli = mkuser("동백만")          # 동대문구 동백만 이겼다
    only_ash = mkuser("옛지우만")          # 청주시 상당구 옛 지우만 이겼다
    both = mkuser("둘다")                  # 둘 다 이겼다
    other = mkuser("딴데")                 # 다른 곳만
    stale = mkuser("옛배치")               # 동대문구에 그 전 배치의 다른 관장 기록
    clear(only_melli, "11230", "melli", wins=3, turns=11)
    clear(only_melli, "11110", "cynthia")
    clear(only_ash, "43111", "ash-ketchum")
    clear(both, "11230", "melli", wins=2, turns=9)
    clear(both, "43111", "ash-ketchum", wins=5, turns=30)
    clear(other, "11110", "cynthia")
    clear(stale, "11230", "someone-old")
    f_melli = fight(other, "11230", "melli")
    f_ash = fight(only_melli, "43111", "ash-ketchum")
    f_else = fight(only_ash, "11110", "cynthia")
    f_done = fight(both, "11230", "melli", state="done")

    conn = db.connect()
    note = migrations._gym_move_jiwoo(conn)
    conn.commit()
    print("  ", note)

    r = regions_of(only_melli)
    chk("동백만 이긴 사람: 청주시 상당구가 클리어 (기록 그대로), 동대문구는 미클리어",
        "43111" in r and "11230" not in r and r["43111"]["trainer"] == "melli"
        and r["43111"]["wins"] == 3 and r["43111"]["best_turns"] == 11 and r["43111"]["first_at"] == "2026-11-01", r)
    chk("  다른 지역은 그대로", "11110" in r, r)
    r = regions_of(only_ash)
    chk("옛 지우만 이긴 사람: 청주시 상당구도 동대문구도 미클리어", "43111" not in r and "11230" not in r, r)
    r = regions_of(both)
    chk("둘 다 이긴 사람: 청주시 상당구는 동백 기록으로, 동대문구는 미클리어",
        set(r) == {"43111"} and r["43111"]["trainer"] == "melli" and r["43111"]["wins"] == 2, r)
    chk("다른 곳만 이긴 사람은 그대로", set(regions_of(other)) == {"11110"}, regions_of(other))
    chk("동대문구의 그 전 배치 기록도 지운다 (새 지우는 모두 다시)", not regions_of(stale), regions_of(stale))
    chk("동대문구 기록은 하나도 없다", not db.q("SELECT 1 FROM gym_clear WHERE region='11230'"))
    chk("청주시 상당구 기록은 모두 동백", {x["trainer"] for x in db.q("SELECT trainer FROM gym_clear WHERE region='43111'")}
        == {"melli"})

    st = {i: db.q1("SELECT state, result FROM gym_battle WHERE id=?", (i,)) for i in (f_melli, f_ash, f_else, f_done)}
    chk("두 자리에서 하던 판은 접는다", all(st[i]["state"] == "done" and st[i]["result"] == "expired" for i in (f_melli, f_ash)),
        {i: dict(v) for i, v in st.items()})
    chk("다른 판 · 끝난 판은 그대로", st[f_else]["state"] == "active" and st[f_done]["result"] is None,
        {i: dict(v) for i, v in st.items()})
    chk("손질 목록에 들어 있다 (서버가 뜰 때 한 번)", ("0380-gym-move-jiwoo", migrations._gym_move_jiwoo) in migrations.ONCE)

    g = json.load(open(os.path.join(HERE, "data", "gyms.json"), encoding="utf-8"))
    by = {t["id"]: t for t in g["trainers"]}
    chk("gyms.json: 동대문구 = 지우, 청주시 상당구 = 동백, 옛 지우 없음",
        g["regions"].get("11230") == "jiwoo" and g["regions"].get("43111") == "melli"
        and by["melli"]["region"] == "43111" and "ash-ketchum" not in by, (g["regions"].get("11230"), g["regions"].get("43111")))
    # 앱은 트레이너 그림을 이름으로 PC 에 남겨 두고 다시 받지 않는다 (ui_gym._trainer_file) - 옛 지우 그림 이름(jiwoo)을
    # 다시 쓰면 옛 지우를 본 사람에게는 새 카드 대신 옛 그림이 나온다. 그림 셋 모두 새 이름이고 파일이 있어야 한다.
    keys = [by["jiwoo"].get(k) for k in ("sprite", "battleSprite", "entrySprite")]
    chk("지우 그림 이름은 옛 지우(jiwoo)와 다르고, 파일이 다 있다",
        "jiwoo" not in keys and all(k and os.path.exists(os.path.join(HERE, "data", "trainer_sprites", k + ".png")) for k in keys),
        keys)

    print("\n  합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
