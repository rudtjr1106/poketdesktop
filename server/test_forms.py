# -*- coding: utf-8 -*-
"""폼 도구 검사 (1.13) — 가방에서 쓰면 모습이 바뀐다.

    python server/test_forms.py

서버를 띄우지 않는다. 임시 DB 에 모듈을 직접 붙여 /api/bag/use 의 함수를 부른다. 못 박는 것:

  1. 켜고 끄기 (그라시데아꽃): 쓸 때마다 스카이폼 <-> 랜드폼, 도구는 안 없어진다.
  2. 고르기 (로토무카탈로그): 고른 폼이 되고 그 폼의 기술로 갈아 끼운다. 원래 모습이면 잊는다.
  3. 꽃꿀: 정해진 스타일이 되고 꿀은 없어진다. 다홍꿀은 원래 모습으로.
  4. 맞지 않는 포켓몬에게는 못 쓴다. 합체 도구는 상점에 없다 (2026-10-17 사용자 결정).
  5. 화면에 보내는 자료: num 은 도감 번호 그대로, 그림은 formNum.
"""
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-forms-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException  # noqa: E402

from app import db, deps, items  # noqa: E402
from app import item_routes as IR  # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mkuser(name):
    cur = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at, last_login,"
                 " last_ip) VALUES (?,?,?,1,10,0,?,?,'')", (name, b"x", b"x", "2026-01-01", "2026-01-01"))
    return cur.lastrowid


def mkmon(uid, species, moves=("TACKLE",), level=50):
    d = deps.dex()
    m = d.roll_wild(level, level, random.Random(1))
    m["species"] = species
    m["moves"] = list(moves)
    m["ability"] = (d.get(species).get("abil") or [None])[0]
    pid = db.insert_mon(uid, m, "2026-01-01")
    return pid


def use(uid, item, pid, form=""):
    items.bag_add(uid, item, 1) if items.bag_count(uid, item) <= 0 else None
    return IR.use(IR.UseIn(item=item, pokemon=pid, form=form), {"user": {"id": uid}})


def row(pid):
    return db.q1("SELECT * FROM pokemon WHERE id=?", (pid,))


def refused(fn):
    try:
        fn()
    except HTTPException as e:
        return e.detail
    return None


def main():
    db.init()
    uid = mkuser("formtest")

    print("== 켜고 끄기 (그라시데아꽃)")
    sh = mkmon(uid, "SHAYMIN")
    out = use(uid, "GRACIDEA", sh)
    chk("쓰면 스카이폼", row(sh)["form"] == "SKY" and "스카이폼" in out["message"], out.get("message"))
    chk("  도구는 그대로 있다", items.bag_count(uid, "GRACIDEA") == 1, items.bag_count(uid, "GRACIDEA"))
    view = deps.decorate(db.row_to_mon(row(sh)))
    chk("  화면 자료: num 은 492 그대로, 그림은 formNum 10006", view["num"] == 492 and view["formNum"] == 10006
        and view["formKr"] == "스카이폼", (view["num"], view.get("formNum")))
    chk("  타입·특성도 폼 것", view["info"]["types"] == ["풀", "비행"] and view["info"]["form"] == "스카이폼",
        view["info"]["types"])
    use(uid, "GRACIDEA", sh)
    chk("다시 쓰면 원래 모습", row(sh)["form"] is None)
    chk("맞지 않는 포켓몬에게는 못 쓴다", refused(lambda: use(uid, "GRACIDEA", mkmon(uid, "PIKACHU"))))

    print("== 고르기 (로토무카탈로그)")
    ro = mkmon(uid, "ROTOM", ["THUNDERBOLT", "SHADOWBALL"])
    use(uid, "ROTOMCATALOG", ro, form="HEAT")
    r = row(ro)
    chk("고른 폼(히트) + 오버히트를 배운다", r["form"] == "HEAT" and "OVERHEAT" in json.loads(r["moves"]),
        (r["form"], r["moves"]))
    use(uid, "ROTOMCATALOG", ro, form="WASH")
    mv = json.loads(row(ro)["moves"])
    chk("워시로 바꾸면 오버히트 자리에 하이드로펌프", "HYDROPUMP" in mv and "OVERHEAT" not in mv, mv)
    use(uid, "ROTOMCATALOG", ro, form="")
    mv = json.loads(row(ro)["moves"])
    chk("원래 모습이면 폼 기술을 잊는다", row(ro)["form"] is None and "HYDROPUMP" not in mv, mv)
    chk("  이미 그 모습이면 안 쓴다", refused(lambda: use(uid, "ROTOMCATALOG", ro, form="")))
    chk("  없는 폼은 못 고른다", refused(lambda: use(uid, "ROTOMCATALOG", ro, form="SKY")))
    full = mkmon(uid, "ROTOM", ["THUNDERBOLT", "SHADOWBALL", "VOLTSWITCH", "WILLOWISP"])
    use(uid, "ROTOMCATALOG", full, form="MOW")
    r = row(full)
    chk("기술 칸이 차 있으면 배우려고 기다린다", "LEAFSTORM" in json.loads(r["pending"]), r["pending"])

    print("== 안 배운 폼 기술은 떠올리기로 되찾는다 (1.13.2, 게시판 #279)")
    # 워시로토무로 바꿨는데 기술 칸이 차 있어서 '하이드로펌프를 배우겠습니까' 가 떴고, 실수로 안 배웠다. 그러면
    # 떠올리기에도 기술머신에도 안 떠서 되찾을 길이 없었다 (기술머신은 본가에서도 못 배운다 - 모습을 바꿀 때만).
    from app import tm_routes as TR
    me = {"user": {"id": uid}}
    TR.learn(TR.LearnIn(pokemon=full, move="LEAFSTORM", skip=True), me)
    chk("안 배우면 기다리던 것에서 빠진다", "LEAFSTORM" not in json.loads(row(full)["pending"]), row(full)["pending"])
    got = {e["move"]: e for e in TR.remember_list(full, me)["remember"]}
    chk("커트로토무: 떠올리기 목록에 리프스톰이 무료로 뜬다", (got.get("LEAFSTORM") or {}).get("free") is True,
        got.get("LEAFSTORM"))
    chk("  어느 모습의 기술인지 적는다", (got.get("LEAFSTORM") or {}).get("form") == "커트로토무", got.get("LEAFSTORM"))
    chk("  다른 모습의 기술은 안 뜬다", not any(k in got for k in IR.ROTOM_SIGS if k != "LEAFSTORM"), sorted(got))
    out = TR.remember(TR.RememberIn(pokemon=full, move="LEAFSTORM", forget="WILLOWISP"), me)
    mv = json.loads(row(full)["moves"])
    chk("  돈 없이 떠올린다 (가진 돈 0원)", out.get("ok") and out.get("cost") == 0 and "LEAFSTORM" in mv
        and "WILLOWISP" not in mv, (out, mv))
    chk("  알고 나면 목록에서 빠진다", "LEAFSTORM" not in [e["move"] for e in TR.remember_list(full, me)["remember"]])
    names = [e["move"] for e in TR.remember_list(ro, me)["remember"]]
    chk("원래 모습 로토무에게는 폼 기술이 안 뜬다", not any(k in names for k in IR.ROTOM_SIGS), names)
    plain = {e["move"]: e for e in TR.remember_list(mkmon(uid, "PIKACHU", ["THUNDERSHOCK"], level=30), me)["remember"]}
    chk("폼이 없는 포켓몬은 예전 그대로 (값을 받고, 폼 표시 없음)",
        plain and not any(e.get("free") or e.get("form") for e in plain.values()), list(plain.values())[:2])

    print("== 꽃꿀")
    ori = mkmon(uid, "ORICORIO")
    use(uid, "PINKNECTAR", ori)
    chk("연분홍꿀: 훌라훌라스타일, 꿀은 없어진다", row(ori)["form"] == "PAU"
        and items.bag_count(uid, "PINKNECTAR") == 0, (row(ori)["form"], items.bag_count(uid, "PINKNECTAR")))
    use(uid, "REDNECTAR", ori)
    chk("다홍꿀: 원래 모습(이글이글스타일)", row(ori)["form"] is None)

    print("== 폼만의 레벨업 기술 (1.13.1, 게시판 #264)")
    from app import tm_routes as TR
    from common import pokelogic as P
    d = deps.dex()
    sky = mkmon(uid, "SHAYMIN", ["SEEDFLARE"], level=70)
    db.run("UPDATE pokemon SET form='SKY' WHERE id=?", (sky,))
    names = [mv for mv, _lv in TR.rememberable(row(sky), d.get("SHAYMIN"), d)]
    chk("스카이폼: 떠올리기에 에어슬래시(Lv.64) · 전광석화(Lv.28)", "AIRSLASH" in names and "QUICKATTACK" in names,
        names)
    chk("  랜드폼에만 있는 광합성은 안 나온다", "SYNTHESIS" not in names, names)
    land = mkmon(uid, "SHAYMIN", ["SEEDFLARE"], level=70)
    names = [mv for mv, _lv in TR.rememberable(row(land), d.get("SHAYMIN"), d)]
    chk("  랜드폼은 그대로 (광합성, 에어슬래시 없음)", "SYNTHESIS" in names and "AIRSLASH" not in names, names)
    up = mkmon(uid, "SHAYMIN", ["SEEDFLARE"], level=63)
    curve = d.get("SHAYMIN").get("growth", "medium")
    db.run("UPDATE pokemon SET form='SKY', exp=? WHERE id=?", (P.exp_for_level(curve, 63), up))
    deps.grant_exp(uid, up, P.exp_for_level(curve, 64) - P.exp_for_level(curve, 63))
    mv = json.loads(row(up)["moves"])
    chk("  스카이폼으로 Lv.64 가 되면 에어슬래시를 배운다", row(up)["level"] == 64 and "AIRSLASH" in mv, (row(up)["level"], mv))
    hoopa = mkmon(uid, "HOOPA", ["PSYCHIC"], level=85)
    db.run("UPDATE pokemon SET form='UNBOUND' WHERE id=?", (hoopa,))
    names = [mv for mv, _lv in TR.rememberable(row(hoopa), d.get("HOOPA"), d)]
    chk("굴레를 벗어난 후파: 이차원러시(Lv.85)", "HYPERSPACEFURY" in names, names)

    print("== 포켓몬 관리 창의 기술 타입 (1.13.1, 게시판 #259)")
    og = mkmon(uid, "OGERPON", ["IVYCUDGEL", "HORNLEECH"], level=50)
    db.run("UPDATE pokemon SET held='HEARTHFLAMEMASK' WHERE id=?", (og,))
    view = deps.decorate(db.row_to_mon(row(og)))
    chk("화덕의가면 오거폰: 덩굴방망이는 불꽃으로 싣는다 (우드혼은 그대로)",
        view.get("moveTypes") == ["FIRE", None], view.get("moveTypes"))
    chk("  그런 기술이 없으면 싣지 않는다", "moveTypes" not in deps.decorate(db.row_to_mon(row(sh))))

    print("== 진화하면서 정해지는 폼: 연격의 태세 우라오스 (2.1.0)")
    rs = d.get("URSHIFU_RAPIDSTRIKE") or {}
    chk("도감 forms 에 있다: 종류 evo, 그림 10191, 격투/물, 보이지않는주먹, 걷는 도트",
        rs.get("formKind") == "evo" and rs.get("num") == 10191 and rs.get("types") == ["FIGHTING", "WATER"]
        and rs.get("abil") == ["UNSEENFIST"] and rs.get("formKr") == "연격의 태세" and rs.get("walk") and rs.get("dot"),
        dict((k, rs.get(k)) for k in ("formKind", "num", "types", "abil", "walk", "dot")))
    lv0 = [mv for lv, mv in rs.get("moves") or [] if lv <= 0]
    chk("  폼 표의 진화 기술(레벨 0)은 수류연타 하나", lv0 == ["SURGINGSTRIKES"], lv0)
    chk("  다른 폼 표에는 레벨 0 이 없다 (개굴닌자 · 마이티폼은 그대로)",
        not [m["internal"] for m in d.forms if m["internal"] != "URSHIFU_RAPIDSTRIKE"
             and any(lv <= 0 for lv, _mv in (m.get("moves") or []))
             and m.get("moves") is not (d.get(m["formOf"]) or {}).get("moves")])
    ur = mkmon(uid, "URSHIFU", ["CLOSECOMBAT"], level=50)
    db.run("UPDATE pokemon SET form='RAPIDSTRIKE' WHERE id=?", (ur,))
    view = deps.decorate(db.row_to_mon(row(ur)))
    chk("  화면 자료: num 892 그대로, 그림 formNum 10191, 타입 격투/물", view["num"] == 892
        and view.get("formNum") == 10191 and view["info"]["types"] == ["격투", "물"]
        and view["info"]["form"] == "연격의 태세", (view["num"], view.get("formNum"), view["info"]["types"]))
    names = [mv for mv, _lv in TR.rememberable(row(ur), d.get("URSHIFU"), d)]
    chk("  떠올리기: 수류연타 · 아쿠아제트 (일격의 암흑강타 · 기습은 안 나온다)",
        "SURGINGSTRIKES" in names and "AQUAJET" in names and "WICKEDBLOW" not in names
        and "SUCKERPUNCH" not in names, names)
    single = mkmon(uid, "URSHIFU", ["CLOSECOMBAT"], level=50)
    names = [mv for mv, _lv in TR.rememberable(row(single), d.get("URSHIFU"), d)]
    chk("  일격의 태세는 그대로 (암흑강타 · 기습, 수류연타 없음)", "WICKEDBLOW" in names and "SUCKERPUNCH" in names
        and "SURGINGSTRIKES" not in names, names)
    chk("  폼 도구로 바꿀 수 있는 폼이 아니다 (useItem 없음)", not rs.get("useItem"))

    print("== 합체 도구는 없다")
    cat = items.catalog()
    chk("유전자쐐기·네크로플러스·유대의고삐는 상점에 없다",
        not any(k in cat for k in ("DNASPLICERS", "NSOLARIZER", "NLUNARIZER", "REINSOFUNITY")))
    chk("  합체 폼도 도감에 없다", not any(m["formKind"] == "fuse" for m in deps.dex().forms))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
