# -*- coding: utf-8 -*-
"""도감 업적 검사 (시즌 3).

    python server/test_achievements.py

서버를 띄우지 않고 app.achievements 를 직접 부른다 (test_boxes 와 같은 방식).

무엇을 못 박나:
  1. 문턱을 넘으면 업적을 주고, **두 번 부르면 보상이 두 번 가지 않는다.**
  2. 칭호는 season.TITLES 로 주되 **달고 있는 칭호를 멋대로 바꾸지 않는다.**
  3. 해금 문턱은 '세대 전체' 가 아니라 **평소 얻을 수 있는 종** 기준이다
     (전체 기준이면 아무도 못 연다). 열리면 풀숲에 나오고 포획률 하한이 붙는다.
  4. 이로치는 처음 셀 때 지금 가진 것으로 시작하고, 얻을 때마다 는다.
  5. 숨은 업적은 달성 전까지 이름을 가린다.
  6. 처음 켠 사람은 /api/me 에서 한 번 몰아서 세고, 안 본 것만 싣는다.
"""
import json
import math
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-ach-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from common import legends as L                              # noqa: E402

from app import achievements as A                            # noqa: E402
from app import config, db, deps, season                     # noqa: E402

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
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'','','')",
        (name, b"x", b"x"))
    return cur.lastrowid


def catch(uid, keys):
    for k in keys:
        db.run("INSERT INTO seen (user_id, species, caught, first_at) VALUES (?,?,1,'')"
               " ON CONFLICT(user_id, species) DO UPDATE SET caught=1", (uid, k))


def mon_row(uid, species, shiny=0, on=0, nick=None):
    db.run("INSERT INTO pokemon (user_id, species, nickname, level, exp, nature, ability,"
           " hidden_ability, gender, shiny, happiness, ivs, evs, moves,"
           " on_desktop, slot, met_level, caught_at)"
           " VALUES (?,?,?,5,0,'HARDY',NULL,0,'M',?,70,'{}','{}','[\"TACKLE\"]',?,NULL,5,'')",
           (uid, species, nick, shiny, on))


def balls(uid):
    return db.q1("SELECT balls FROM users WHERE id=?", (uid,))["balls"]


def got(uid):
    return set(r["key"] for r in db.q("SELECT key FROM achievement WHERE user_id=?", (uid,)))


def main():
    db.init()
    d = deps.dex()
    data = A._data()
    wild = sorted(data["wild"])

    print("=== 목록 ===")
    defs = A.defs()
    keys = [a["key"] for a in defs]
    chk("업적 50개", len(defs) == 50, len(defs))
    chk("열쇠가 겹치지 않는다", len(set(keys)) == len(keys))
    chk("칭호가 season.TITLES 에 올라간다",
        all(A.title_id(a["key"]) in season.TITLES for a in defs if a["title"]))
    chk("못 얻던 종은 31 (울트라비스트 11 + 패러독스 20)",
        len(data["unlock_all"]) == 31
        and len(data["unlock_pool"].get(7, [])) == 11
        and len(data["unlock_pool"].get(9, [])) == 20,
        (len(data["unlock_all"]), {g: len(v) for g, v in data["unlock_pool"].items()}))
    for a in defs:
        if a["stat"].startswith("type_"):
            if len(data["types"][a["stat"][5:]] & data["wild"]) < a["target"]:
                chk("타입 수집가 %s 는 채울 수 있다" % a["key"], False)
    chk("타입 수집가는 전부 야생만으로 채울 수 있다", True)

    print("\n=== 도감 수집 · 보상은 한 번 ===")
    uid = mkuser("업적가")
    before = balls(uid)
    catch(uid, wild[:50])
    new = A.check(uid)
    chk("50종에 첫 업적", "dex_50" in [a["key"] for a in new], [a["key"] for a in new])
    chk("볼 5개를 준다", balls(uid) == before + 5, (before, balls(uid)))
    again = A.check(uid)
    chk("다시 불러도 또 안 준다", again == [] and balls(uid) == before + 5,
        ([a["key"] for a in again], balls(uid)))

    print("\n=== 칭호 · 달고 있는 것은 그대로 ===")
    db.run("UPDATE users SET title='s1_top30' WHERE id=?", (uid,))
    catch(uid, wild[:400])
    A.check(uid)
    r = db.q1("SELECT rid FROM user_reward WHERE user_id=? AND rid=?",
              (uid, A.title_id("dex_400")))
    chk("400종 칭호를 준다", r is not None)
    chk("업적 칭호는 시즌 0 (영구)",
        db.q1("SELECT season FROM user_reward WHERE user_id=? AND rid=?",
              (uid, A.title_id("dex_400")))["season"] == 0)
    chk("달고 있던 칭호를 안 바꾼다",
        db.q1("SELECT title FROM users WHERE id=?", (uid,))["title"] == "s1_top30")
    owned, _f = season.owned(uid)
    chk("칭호 창에 이름이 뜬다", any(t["id"] == A.title_id("dex_400")
                                    and t["name"] == "도감 조사원" for t in owned),
        [t for t in owned if t["id"].startswith("ach_")][:3])

    print("\n=== 지방 도감 완성 ===")
    u2 = mkuser("관동러")
    target = sorted(data["region"][1])
    catch(u2, target[:-1])
    A.check(u2)
    chk("하나 모자라면 아직", "region_1" not in got(u2))
    catch(u2, target[-1:])
    A.check(u2)
    chk("다 채우면 관동 도감 완성", "region_1" in got(u2))
    chk("전설·환상은 완성 목표에 없다",
        not any(L.kind_of(d.get(k)["num"]) for k in data["region"][1]))

    print("\n=== 해금 — 평소 얻을 수 있는 종 기준 ===")
    u3 = mkuser("울트라")
    g7 = sorted(data["gen_wild"][7])
    need = int(math.ceil(len(g7) * A.UNLOCK_PCT))
    chk("7세대 문턱은 평소 얻을 수 있는 %d종 중 %d종" % (len(g7), need),
        need <= len(g7) and len(g7) < len([s for s in d.species if s["gen"] == 7]),
        (need, len(g7)))
    catch(u3, g7[:need - 1])
    A.check(u3)
    chk("하나 모자라면 안 열린다", "unlock_ultra" not in got(u3) and not A.unlocked_pool(u3))
    catch(u3, g7[need - 1:need])
    A.check(u3)
    pool = A.unlocked_pool(u3)
    chk("채우면 울트라홀이 열린다", "unlock_ultra" in got(u3) and len(pool) == 11, len(pool))
    chk("패러독스는 아직", not any(d.get(k)["gen"] == 9 for k in pool))

    class Always(random.Random):
        def random(self):
            return 0.0
    m = A.unlock_mon(u3, Always(1))
    chk("풀숲에 해금 포켓몬이 나온다 (Lv.%d)" % A.UNLOCK_LEVEL,
        m is not None and m["species"] in pool and m["level"] == A.UNLOCK_LEVEL,
        m and (m["species"], m["level"]))

    class Never(random.Random):
        def random(self):
            return 0.99
    chk("확률에 안 걸리면 안 나온다", A.unlock_mon(u3, Never(1)) is None)
    chk("안 연 사람에게는 안 나온다", A.unlock_mon(uid, Always(1)) is None)
    low = [k for k in data["unlock_all"] if (d.get(k).get("catch") or 45) < A.UNLOCK_CATCH_FLOOR]
    chk("포획률이 낮은 해금 종이 있다 (%d종)" % len(low), len(low) > 0)
    chk("해금 종은 포획률 하한을 둔다",
        all(A.catch_species(d.get(k))["catch"] == A.UNLOCK_CATCH_FLOOR for k in low))
    chk("  원래 자료는 안 바꾼다", all((d.get(k).get("catch") or 45) < A.UNLOCK_CATCH_FLOOR
                                    for k in low))
    chk("다른 종은 그대로", A.catch_species(d.get("PIKACHU")) is d.get("PIKACHU"))

    print("\n=== 이로치 · 숨은 업적 ===")
    u4 = mkuser("반짝이")
    mon_row(u4, "PIKACHU", shiny=1)
    A.check(u4)
    chk("처음 셀 때 지금 가진 이로치로 시작", A._stat(u4, "shiny") == 1
        and "shiny_1" in got(u4), (A._stat(u4, "shiny"), sorted(got(u4))))
    A.on_obtain(u4, {"species": "EEVEE", "shiny": True}, "catch")
    chk("잡으면 는다", A._stat(u4, "shiny") == 2)
    A.on_obtain(u4, {"species": "EEVEE", "shiny": True}, "evolve")
    chk("진화는 새 이로치가 아니다", A._stat(u4, "shiny") == 2)
    mon_row(u4, "PIKACHU", shiny=1)
    A.check(u4)
    chk("같은 종 이로치 둘 -> 쌍둥이 별", "hidden_twin" in got(u4))

    u5 = mkuser("한밤")
    A.on_obtain(u5, {"species": "PIKACHU"}, "catch", now="2026-10-01T15:30:00+00:00")
    chk("자정(한국 0시)에 잡으면", "hidden_midnight" in got(u5))
    u6 = mkuser("낮")
    A.on_obtain(u6, {"species": "PIKACHU"}, "catch", now="2026-10-01T03:00:00+00:00")
    chk("낮에는 아니다", "hidden_midnight" not in got(u6))
    ub = sorted(data["unlock_pool"][7])[0]
    A.on_obtain(u6, {"species": ub}, "catch", ball="LUXURYBALL")
    chk("럭셔리볼로 전설 표시 포켓몬", "hidden_lux" in got(u6))

    u7 = mkuser("똑같이")
    for _ in range(config.MAX_PARTY):
        mon_row(u7, "PIKACHU", on=1, nick="피카")
    A.check(u7)
    chk("여섯 마리 별명이 모두 같으면", "hidden_nick" in got(u7))

    print("\n=== 화면에 줄 것 ===")
    u8 = mkuser("처음")
    catch(u8, wild[:120])
    card = A.me_card(u8)
    names = [c["key"] for c in card["unseen"]]
    chk("처음 켜면 몰아서 센다", "dex_50" in names and "dex_100" in names, names)
    A.mark_seen(u8)
    chk("본 뒤에는 안 싣는다", A.me_card(u8)["unseen"] == [])
    pub = A.public(u8)
    hid = [c for c in pub["achievements"] if c["hidden"] and "gotAt" not in c]
    shown = [c for c in pub["achievements"] if c["hidden"] and "gotAt" in c]
    chk("숨은 업적은 달성 전까지 이름을 가린다",
        hid and all(c["name"] == "???" and "value" not in c for c in hid), hid[:1])
    chk("달성한 숨은 업적은 이름이 드러난다 (120종이면 타입 여행자)",
        any(c["key"] == "hidden_types" and c["name"] == "타입 여행자" for c in shown),
        [c["key"] for c in shown])
    chk("진행 값을 싣는다", next(c for c in pub["achievements"]
                                if c["key"] == "dex_200")["value"] == 120)
    chk("해금 여부", pub["unlocks"] == {"unlock_7": False, "unlock_9": False}, pub["unlocks"])
    top = A.top(uid)
    chk("대표 업적은 칭호 있는 것만", top and all(t["name"] for t in top), top)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
