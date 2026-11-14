# -*- coding: utf-8 -*-
"""길드 코인 상점 '길드 전용' 꾸미기 (2.5.0, 11/15 사용자 '1,2 반영') - 서버 쪽.

    .venv-server/bin/python server/test_guild_deco_shop.py

  1. 시즌 5 엔 없다 (상점 줄 없음 · 사면 404).
  2. 시즌 6 상점 줄: 마스터볼 · 금색병뚜껑 뒤에 'deco:guild_flag'(300코인 · 한 번 사면 계속) ·
     'deco:pick_deco'(400코인 · 시즌마다 1장). cat deco · 되팔 값 0 · 설명(note).
  3. 깃발 들기 사기: 코인 모자람 400 · 사면 꾸미기 주머니에 · 남은 0 · 또 사면 409 · 한 번에 2개 409.
  4. 꾸미기 선택권: 사면 장수 +1 · 이번 시즌 또 사면 409 · 다음 시즌 다시 1장 · 고르기(순위 · 메달 · 깃발 들기 ·
     모르는 것 400, 가진 것 409, 고르면 가짐 · 장수 -1 · 목록에서 빠짐, 장 없으면 409) · 길(POST /api/deco/pick {deco}).
  5. 고를 것이 안 남았으면(아직 안 고른 장까지 셈해서) 남은 0 · 사면 409 · 코인 그대로.
  6. 랜덤 캡슐 · 선택권 후보에 깃발 들기 없음, 순위 · 메달 없음.
  7. 깃발 들기를 쓴 포켓몬의 응답에 decoFlag = 주인이 든 길드 깃발 (깃발 없는 길드 · 길드 없음 · 안 쓴 포켓몬이면
     None, 다시 그리면 새 그림) · 놀러 가기(손님 포켓몬 · 주인 파티)에도 실린다.
서버를 띄우지 않는다. 임시 DB (test_guild_war_v5 의 도우미).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import test_guild_war_v5 as T5                                 # noqa: E402  (임시 DB · 사용자 도우미)

from fastapi import HTTPException                              # noqa: E402

from app import db, deco, deco_routes, guild, season, visit    # noqa: E402
from common import deco as C                                   # noqa: E402
from common import flag as FLAG                                # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def code_of(fn):
    try:
        fn()
    except HTTPException as e:
        return e.status_code, e.detail
    return None


def row(sh, iid):
    return next((x for x in sh["items"] if x["id"] == iid), None)


def art(ch):
    n = FLAG.SIZE * FLAG.SIZE
    return ch * (n // 2) + FLAG.EMPTY * (n - n // 2)


def mkguild(name, master):
    gid = db.run("INSERT INTO guild (name, intro, join_mode, master_id, created_at) VALUES (?,?,?,?,?)",
                 (name, "", "open", master, "2026-11-14T00:00:00+00:00")).lastrowid
    db.run("INSERT INTO guild_member (user_id, guild_id, role, joined_at) VALUES (?,?,?,?)",
           (master, gid, "master", "2026-11-14T00:00:00+00:00"))
    return gid


FLAG_ID = "deco:guild_flag"
PICK_ID = "deco:" + C.PICK_DECO


def main():
    db.init()
    real = season.SEASON
    try:
        print("=== 1. 시즌 5: 없음 ===")
        season.SEASON = 5
        u = T5.mkuser("꾸미기상점_가", "PIKACHU", 30)
        guild._coin_add(u, 2000)
        sh = guild.shop(u)
        chk("상점 줄 없음", row(sh, FLAG_ID) is None and row(sh, PICK_ID) is None, [x["id"] for x in sh["items"][:4]])
        c = code_of(lambda: guild.buy(u, FLAG_ID, 1))
        chk("  사면 404 · 코인 그대로", c and c[0] == 404 and guild.coin(u) == 2000, c)

        print("\n=== 2. 시즌 6 상점 줄 ===")
        season.SEASON = 6
        sh = guild.shop(u)
        ex = [x["id"] for x in sh["items"] if x.get("exclusive")]
        chk("'길드 전용' = 마스터볼 · 금색병뚜껑 · 깃발 들기 · 꾸미기 선택권 (차례대로)",
            ex == ["MASTERBALL", "GOLDBOTTLECAP", FLAG_ID, PICK_ID], ex)
        f, p = row(sh, FLAG_ID), row(sh, PICK_ID)
        chk("깃발 들기: 300코인 · limit 1 · left 1 · forever · cat deco · 되팔 값 0 · 설명",
            f["coin"] == 300 and f["limit"] == 1 and f["left"] == 1 and f["forever"] is True and f["cat"] == "deco"
            and f["sell"] == 0 and f["group"] == guild.EXCLUSIVE_GROUP and "깃발" in f["note"] and f["kr"] == "깃발 들기", f)
        chk("꾸미기 선택권: 400코인 · 시즌마다 1장 · forever 아님 · 설명에 고를 꾸미기",
            p["coin"] == 400 and p["limit"] == 1 and p["left"] == 1 and p["forever"] is False
            and p["kr"] == C.PICK_DECO_KR and "선글라스" in p["note"] and "금관" not in p["note"], p)

        print("\n=== 3. 깃발 들기 사기 ===")
        poor = T5.mkuser("꾸미기상점_가난", "PIKACHU", 30)
        guild._coin_add(poor, 299)
        c = code_of(lambda: guild.buy(poor, FLAG_ID, 1))
        chk("코인이 모자라면 400 · 안 가짐 · 코인 그대로", c and c[0] == 400 and not deco.owned(poor).get("guild_flag")
            and guild.coin(poor) == 299, c)
        c = code_of(lambda: guild.buy(u, FLAG_ID, 2))
        chk("  한 번에 2개 → 409 · 코인 그대로", c and c[0] == 409 and guild.coin(u) == 2000, c)
        r = guild.buy(u, FLAG_ID, 1)
        chk("사면 코인 -300 · 꾸미기 주머니에 깃발 들기 · 남은 0 · '가지고 있음' 꼴",
            r["spent"] == 300 and guild.coin(u) == 1700 and deco.owned(u).get("guild_flag") == 1
            and row(guild.shop(u), FLAG_ID)["left"] == 0, (r, guild.coin(u)))
        c = code_of(lambda: guild.buy(u, FLAG_ID, 1))
        chk("  또 사면 409 '이미' · 코인 그대로", c and c[0] == 409 and "이미" in c[1] and guild.coin(u) == 1700, c)
        season.SEASON = 7
        chk("  다음 시즌에도 남은 0 (한 번 사면 계속)", row(guild.shop(u), FLAG_ID)["left"] == 0)
        season.SEASON = 6
        chk("  끼울 수 있다 (깃발 칸)", deco.equip(u, T5_pid(u, 0), "guild_flag") == {"flag": "guild_flag"})

        print("\n=== 4. 꾸미기 선택권 ===")
        r = guild.buy(u, PICK_ID, 1)
        st = deco.state(u)
        chk("사면 코인 -400 · 선택권 1장 · 고를 것 = 후보 전부(가진 것 없음)",
            r["spent"] == 400 and guild.coin(u) == 1300 and st["decoPicks"] == 1
            and [x["key"] for x in st["decoChoices"]] == list(C.pick_pool()), (r, st["decoPicks"]))
        chk("  고를 것 줄에 이름 · 칸", all(x["kr"] and x["slotKr"] for x in st["decoChoices"]), st["decoChoices"][:2])
        c = code_of(lambda: guild.buy(u, PICK_ID, 1))
        chk("  이번 시즌 또 사면 409 '이번 시즌' · 코인 그대로", c and c[0] == 409 and "이번 시즌" in c[1]
            and guild.coin(u) == 1300 and row(guild.shop(u), PICK_ID)["left"] == 0, c)
        for bad in ("crown_gold", "medal_gold", "guild_flag", "없는것"):
            c = code_of(lambda b=bad: deco.pick_one(u, b))
            chk("  %s 은(는) 못 고른다 (400)" % bad, c and c[0] == 400, c)
        deco.grant(u, "shades")
        c = code_of(lambda: deco.pick_one(u, "shades"))
        chk("  가진 꾸미기는 409 '이미' · 장 그대로", c and c[0] == 409 and "이미" in c[1]
            and deco.state(u)["decoPicks"] == 1, c)
        got = deco.pick_one(u, "fx_notes")
        st = deco.state(u)
        chk("고르면 가짐 · 장 0 · 고를 것에서 빠짐", got == ["음표"] and deco.owned(u).get("fx_notes") == 1
            and st["decoPicks"] == 0 and C.PICK_DECO not in deco.owned(u)
            and "fx_notes" not in [x["key"] for x in st["decoChoices"]]
            and "shades" not in [x["key"] for x in st["decoChoices"]], (got, st["decoPicks"]))
        c = code_of(lambda: deco.pick_one(u, "bow"))
        chk("  장이 없으면 409", c and c[0] == 409, c)
        season.SEASON = 7
        chk("다음 시즌엔 다시 1장 살 수 있다", row(guild.shop(u), PICK_ID)["left"] == 1)
        guild.buy(u, PICK_ID, 1)
        out = deco_routes.pick(deco_routes.PickIn(deco="bowtie"), ctx={"user": {"id": u}})
        chk("길 POST /api/deco/pick {deco}: 고르고 창 꼴 + got", out["got"] == ["나비넥타이"]
            and out["decoPicks"] == 0 and deco.owned(u).get("bowtie") == 1, out.get("got"))
        deco.grant(u, C.PICK)
        out = deco_routes.pick(deco_routes.PickIn(bundle="join_bow"), ctx={"user": {"id": u}})
        chk("  {bundle} 은 예전 그대로 (참가 묶음)", out["got"] == ["분홍 리본", "발자국"], out.get("got"))
        season.SEASON = 6

        print("\n=== 5. 고를 것이 안 남았으면 ===")
        full = T5.mkuser("꾸미기상점_다가짐", "PIKACHU", 30)
        guild._coin_add(full, 1000)
        pool = list(C.pick_pool())
        for k in pool[:-1]:
            deco.grant(full, k)
        chk("하나 남았으면 남은 1", row(guild.shop(full), PICK_ID)["left"] == 1)
        deco.grant(full, C.PICK_DECO)                     # 아직 안 고른 장 하나 - 남은 하나를 그 장이 가져간다
        chk("  안 고른 장까지 셈하면 남은 0", row(guild.shop(full), PICK_ID)["left"] == 0)
        c = code_of(lambda: guild.buy(full, PICK_ID, 1))
        chk("  사면 409 '남지 않았습니다' · 코인 그대로 · 산 수 안 늘어남", c and c[0] == 409 and "남지 않았" in c[1]
            and guild.coin(full) == 1000 and guild.bought(full, PICK_ID) == 0, c)

        print("\n=== 6. 후보 ===")
        chk("랜덤 캡슐 · 선택권 후보에 깃발 들기 없음", "guild_flag" not in C.slot_pool() and "guild_flag" not in C.pick_pool())
        chk("  순위 · 메달도 없음", not set(C.RANK_ONLY) & set(C.pick_pool()))
        chk("  깃발 칸 · 효과로 그린다 (장식이 아니라 효과 창)", C.slot_of("guild_flag") == "flag" and "flag" in C.EFFECTS
            and C.parts({"flag": "guild_flag", "trail": "fx_paw"}) == ((), ("fx_paw", "guild_flag")),
            C.parts({"flag": "guild_flag", "trail": "fx_paw"}))

        print("\n=== 7. decoFlag ===")
        pid = T5_pid(u, 0)
        other_pid = T5_pid(u, 1)
        mon = lambda i: db._row_to_mon(db.q1("SELECT * FROM pokemon WHERE id=?", (i,)))     # noqa: E731
        chk("길드가 없으면 None", mon(pid)["decoFlag"] is None, mon(pid).get("decoFlag"))
        gid = mkguild("깃발들기단", u)
        chk("  깃발 없는 길드면 None", mon(pid)["decoFlag"] is None)
        pic = art("5")
        guild.set_flag(u, pic)
        chk("깃발 들기를 쓴 포켓몬 = 주인 길드 깃발", mon(pid)["decoFlag"] == pic)
        chk("  안 쓴 포켓몬은 None", mon(other_pid)["decoFlag"] is None)
        pic2 = art("r")
        guild.set_flag(u, pic2)
        chk("  다시 그리면 새 그림", mon(pid)["decoFlag"] == pic2)
        chk("놀러 간 포켓몬(손님)에도", visit._public_mon(mon(pid))["decoFlag"] == pic2)
        party = visit._clean_party([{"id": pid, "num": 25}, {"id": other_pid, "num": 25}], u)
        chk("  주인 파티(손님 화면)에도 - 깃발 칸을 쓴 포켓몬만", party[0].get("decoFlag") == pic2
            and "decoFlag" not in party[1], party)
        deco.equip(u, pid, "guild_flag", on=False)
        chk("빼면 None", mon(pid)["decoFlag"] is None)
        db.run("DELETE FROM guild_member WHERE guild_id=?", (gid,))
    finally:
        season.SEASON = real
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


def T5_pid(uid, i):
    return [r["id"] for r in db.q("SELECT id FROM pokemon WHERE user_id=? ORDER BY id", (uid,))][i]


if __name__ == "__main__":
    sys.exit(main())
