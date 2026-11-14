# -*- coding: utf-8 -*-
"""길드 깃발 (2.5.0, 시즌 6) - 서버 쪽. design-notes/2026-11-14-guild-flag.md 의 '검사' 줄.

    .venv-server/bin/python server/test_guild_flag.py

  1~2. 사는 것이 아니다 (11/15 사용자 "코인을 안 쓰고 그냥 길마, 부마가 관리에서"): 도구 목록 · 코인 상점에 길드 깃발이
     없다 (시즌 6 '길드 전용' 은 마스터볼 · 금색병뚜껑 둘, 시즌마다 수 그대로).
  3. 그리기 권한: 길드 없음 400 · 길드원 403 · 마스터 · 부마스터는 바로 그린다. /api/guild 의 canFlag.
  4. 꼴 검사: 577자 400 (권한을 보기 전에) · 모자란 길이 · 모르는 글자 400 · 맞으면 저장 · 채팅 알림 · stamp 가 바뀐다.
  5. 빈 그림 = 내림 (NULL · 채팅 '내렸습니다') · 빈 글자도 내림 · 없는 깃발을 또 내리면 아무 일 없음.
  6. 운영진 지우기: 운영진이 아니면 403 · 없는 길드 404 · 지우면 NULL + 채팅 '운영진이' · 이미 없으면 removed False.
  7. 응답의 flag 칸: /api/guild guild.flag · 다른 길드 목록 · 랭킹 줄 · 랭킹 me · 친구 목록 줄 ·
     길드전 1:1 match 의 target/from/own · matches[].guilds[].
  8. 이름 옆 깃발은 '지금 든 길드에 깃발이 있을 때' (길드원 누구나) - 길드를 옮기면 새 길드 깃발 · 깃발 없는 길드면 None.
서버를 띄우지 않는다. 임시 DB.
"""
import datetime
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

TMP = tempfile.mkdtemp(prefix="poket-gflag-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                             # noqa: E402

from app import config, db, guild, guild_routes, items, pvp, pvp_routes, season, social   # noqa: E402
from app import guild_war_match as GM                         # noqa: E402
from common import flag as FLAG                               # noqa: E402

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


def mkuser(name, coins=0):
    uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at, last_login, last_ip)"
                 " VALUES (?,?,?,1,10,0,'','','')", (name, b"x", b"x")).lastrowid
    if coins:
        guild._coin_add(uid, coins)
    return uid


def mkguild(name, master):
    gid = db.run("INSERT INTO guild (name, intro, join_mode, master_id, created_at) VALUES (?,?,?,?,?)",
                 (name, "", "open", master, "2026-11-14T00:00:00+00:00")).lastrowid
    db.run("INSERT INTO guild_member (user_id, guild_id, role, joined_at) VALUES (?,?,?,?)",
           (master, gid, "master", "2026-11-14T00:00:00+00:00"))
    return gid


def put_in(uid, gid, role="member"):
    db.run("DELETE FROM guild_member WHERE user_id=?", (uid,))
    db.run("INSERT INTO guild_member (user_id, guild_id, role, joined_at) VALUES (?,?,?,?)",
           (uid, gid, role, "2026-11-14T00:00:00+00:00"))


def ranked(uid, rp):
    db.run("INSERT INTO rank_stat (user_id, rating, games, ranked, rp, updated_at) VALUES (?,?,?,?,?,?)",
           (uid, 1000, 20, 1, rp, "2026-11-14T00:00:00+00:00"))


def befriend(a, b):
    x, y = min(a, b), max(a, b)
    db.run("INSERT INTO friend (a_id, b_id, state, asked_by, created_at, decided_at) VALUES (?,?,?,?,?,?)",
           (x, y, "accepted", a, "2026-11-14T00:00:00+00:00", "2026-11-14T00:00:00+00:00"))


def row(sh, iid):
    return next((x for x in sh["items"] if x["id"] == iid), None)


def chat_bodies(gid):
    return [r["body"] for r in db.q("SELECT body FROM guild_chat WHERE guild_id=? ORDER BY id", (gid,))]


def art(ch="5", n=FLAG.SIZE * FLAG.SIZE):
    """한 빛깔로 반쯤 칠한 그림 (나머지는 투명)."""
    half = n // 2
    return ch * half + FLAG.EMPTY * (n - half)


def main():
    db.init()
    real, real_admins = season.SEASON, config.BOARD_ADMINS
    try:
        print("=== 1~2. 길드 깃발은 사는 것이 아니다 ===")
        season.SEASON = 6
        u = mkuser("오", 5000)
        sh = guild.shop(u)
        ex = [x["id"] for x in sh["items"] if x.get("exclusive")]
        chk("도구 목록에 길드 깃발 없음", items.get("GUILDFLAG") is None)
        chk("  코인 상점 '길드 전용' 도구 = 마스터볼 · 금색병뚜껑 (깃발 없음 - 꾸미기 줄 'deco:' 은 test_guild_deco_shop)",
            [i for i in ex if not i.startswith(guild.DECO_PREFIX)] == ["MASTERBALL", "GOLDBOTTLECAP"]
            and row(sh, "GUILDFLAG") is None and guild.coin_price("GUILDFLAG") == 0, ex)
        chk("  시즌마다 수 그대로 (마스터볼 1 · 금색병뚜껑 2, forever 칸 없음)", row(sh, "MASTERBALL")["limit"] == 1
            and row(sh, "GOLDBOTTLECAP")["limit"] == 2 and "forever" not in row(sh, "MASTERBALL"), row(sh, "MASTERBALL"))
        c = code_of(lambda: guild.buy(u, "GUILDFLAG", 1))
        chk("  사려 하면 404 · 코인 그대로", c and c[0] == 404 and guild.coin(u) == 5000, c)

        print("\n=== 3. 그리기 권한 ===")
        boss = mkuser("마스터")
        sub = mkuser("부마")
        mem = mkuser("길드원")
        lone = mkuser("혼자")
        ga = mkguild("깃발단", boss)
        put_in(sub, ga, "sub")
        put_in(mem, ga, "member")
        pic = art("5")
        c = code_of(lambda: guild.set_flag(lone, pic))
        chk("길드 없음 → 400", c and c[0] == 400, c)
        st = guild.state(boss)
        chk("  마스터: 사는 것 없이 canFlag True · 아직 guild.flag None · flagItem 칸 없음",
            st["canFlag"] is True and st["guild"]["flag"] is None and "flagItem" not in st,
            (st["canFlag"], st["guild"].get("flag"), "flagItem" in st))
        c = code_of(lambda: guild.set_flag(mem, pic))
        st = guild.state(mem)
        chk("  일반 길드원 → 403 · canFlag False", c and c[0] == 403 and st["canFlag"] is False, (c, st["canFlag"]))
        st = guild.state(lone)
        chk("  길드 없는 사람의 /api/guild 에도 canFlag 칸 (False)", st["guild"] is None and st["canFlag"] is False)
        chk("  부마스터: canFlag True", guild.state(sub)["canFlag"] is True)

        print("\n=== 4. 꼴 검사 · 저장 ===")
        big = "0" * (FLAG.SIZE * FLAG.SIZE + 1)
        c = code_of(lambda: guild.set_flag(lone, big))
        chk("577자 → 400 (길드 없는 사람도 권한보다 먼저 크기로 막힌다)", c and c[0] == 400 and "너무 큽니다" in c[1], c)
        c = code_of(lambda: guild_routes.flag(guild_routes.FlagIn(pixels="1" * 100000), ctx={"user": {"id": sub}}))
        chk("  길(POST /api/guild/flag)에서도 큰 그림 400", c and c[0] == 400, c)
        c = code_of(lambda: guild.set_flag(sub, "1" * 575))
        chk("  575자 → 400 '올바르지'", c and c[0] == 400 and "올바르지" in c[1], c)
        c = code_of(lambda: guild.set_flag(sub, "w" * 576))
        chk("  모르는 글자(w) → 400", c and c[0] == 400, c)
        chk("  아무것도 안 바뀜", guild.flag_of(ga) is None)
        stamp0 = guild._stamp(ga)
        n0 = len(chat_bodies(ga))
        out = guild.set_flag(sub, pic)
        chk("부마스터가 그림 → 저장 · 응답은 /api/guild 꼴 + ok · message", out["ok"] and out["guild"]["flag"] == pic
            and guild.flag_of(ga) == pic and "members" in out and out["canFlag"] is True and out["message"], out.get("message"))
        g = guild.guild_of(ga)
        chk("  flag_by · flag_at 적힘", g["flag_by"] == sub and g["flag_at"], (g["flag_by"], g["flag_at"]))
        bodies = chat_bodies(ga)
        chk("  채팅 '부마 님이 길드 깃발을 새로 그렸습니다'", len(bodies) == n0 + 1 and bodies[-1] == "부마 님이 길드 깃발을 새로 그렸습니다.",
            bodies[-1:])
        chk("  stamp 가 바뀐다 (폴링 화면도 다시 받는다)", guild._stamp(ga) != stamp0)
        out = guild.set_flag(sub, pic)
        chk("  같은 그림 또 저장 → '바뀐 것이 없습니다' · 채팅 안 늘어남", out["message"] == "바뀐 것이 없습니다."
            and len(chat_bodies(ga)) == n0 + 1, out["message"])
        pic2 = art("r")
        n2 = len(chat_bodies(ga))
        out = guild.set_flag(boss, pic2)
        chk("  마스터가 곧바로 다시 그리면 바뀐다 (길드에 하나) · 10분 안이라 채팅은 그대로", guild.flag_of(ga) == pic2
            and len(chat_bodies(ga)) == n2 and out["message"] == "길드 깃발을 그렸습니다!", chat_bodies(ga)[-1:])
        later = guild._now() + datetime.timedelta(seconds=guild.FLAG_SAY_GAP + 60)
        guild.set_flag(boss, art("g"), now=later)
        chk("  10분 넘어 다시 그리면 채팅 '새로 그렸습니다'", guild.flag_of(ga) == art("g") and len(chat_bodies(ga)) == n2 + 1
            and chat_bodies(ga)[-1] == "마스터 님이 길드 깃발을 새로 그렸습니다.", chat_bodies(ga)[-1:])

        print("\n=== 5. 빈 그림 = 내림 ===")
        out = guild.set_flag(boss, FLAG.BLANK)
        chk("다 지운 그림 → NULL · 채팅 '내렸습니다'", guild.flag_of(ga) is None and out["guild"]["flag"] is None
            and chat_bodies(ga)[-1] == "마스터 님이 길드 깃발을 내렸습니다.", chat_bodies(ga)[-1:])
        n1 = len(chat_bodies(ga))
        out = guild.set_flag(boss, FLAG.BLANK)
        chk("  없는 깃발을 또 내리면 '내릴 깃발이 없습니다' · 채팅 그대로", out["message"] == "내릴 깃발이 없습니다."
            and len(chat_bodies(ga)) == n1, out["message"])
        guild.set_flag(boss, pic)
        guild.set_flag(boss, "")
        chk("  빈 글자도 내림", guild.flag_of(ga) is None)
        guild.set_flag(boss, pic)

        print("\n=== 6. 운영진 지우기 ===")
        admin = mkuser("운영자님")
        config.BOARD_ADMINS = ("운영자님",)
        c = code_of(lambda: guild.clear_flag(boss, ga))
        chk("운영진이 아니면 403 (그 길드 마스터라도)", c and c[0] == 403 and guild.flag_of(ga) == pic, c)
        c = code_of(lambda: guild.clear_flag(admin, 99999))
        chk("  없는 길드 → 404", c and c[0] == 404, c)
        out = guild.clear_flag(admin, ga)
        chk("  운영진이 지움 → NULL · removed · 채팅 '운영진이 길드 깃발을 내렸습니다'", out["removed"] is True
            and guild.flag_of(ga) is None and chat_bodies(ga)[-1] == "운영진이 길드 깃발을 내렸습니다.", out)
        chk("  flag_by = 운영진", guild.guild_of(ga)["flag_by"] == admin)
        out = guild.clear_flag(admin, ga)
        chk("  이미 없으면 removed False", out["removed"] is False and out["ok"], out)
        out = guild_routes.clear_flag(ga, ctx={"user": {"id": admin}})
        chk("  길(DELETE /api/admin/guild/{gid}/flag)도 같다", out["ok"] and out["guildId"] == ga, out)
        guild.set_flag(boss, pic)

        print("\n=== 7. 응답의 flag 칸 ===")
        other = mkuser("남의마스터")
        gb = mkguild("민무늬단", other)
        lst = dict((x["id"], x) for x in guild.listing(lone)["guilds"])
        chk("다른 길드 목록 줄: 깃발 있는 길드 = 문자열 · 없는 길드 = None", lst[ga]["flag"] == pic and lst[gb]["flag"] is None,
            (lst[ga].get("flag") == pic, lst[gb].get("flag")))
        chk("  /api/guild 의 guild.flag 는 길드원 누구에게나", guild.state(mem)["guild"]["flag"] == pic
            and guild.state(other)["guild"]["flag"] is None)
        late = mkuser("새길드원")
        put_in(late, ga)
        for x, rp in ((boss, 300), (mem, 200), (late, 100), (other, 50)):
            ranked(x, rp)
        rk = dict((x["userId"], x) for x in pvp.ranking(50, boss))
        chk("랭킹 줄: 깃발 있는 길드의 길드원 누구나 → 깃발 · 깃발 없는 길드 → None",
            rk[boss]["flag"] == pic and rk[mem]["flag"] == pic and rk[late]["flag"] == pic and rk[other]["flag"] is None,
            [(rk[k].get("name"), bool(rk[k].get("flag"))) for k in rk])
        ctx = {"user": {"id": boss, "username": "마스터"}}
        rr = pvp_routes.ranking(50, ctx=ctx)
        chk("  랭킹 me.flag (내 이름 옆)", rr["me"]["flag"] == pic, rr["me"].get("flag"))
        rr = pvp_routes.ranking(50, ctx={"user": {"id": late, "username": "새길드원"}})
        chk("  일반 길드원의 me.flag 도 길드 깃발", rr["me"]["flag"] == pic, rr["me"].get("flag"))
        rr = pvp_routes.ranking(50, ctx={"user": {"id": other, "username": "남의마스터"}})
        chk("  깃발 없는 길드 사람의 me.flag = None", rr["me"]["flag"] is None, rr["me"].get("flag"))
        me = mkuser("친구주인")
        for x in (boss, late, other, lone):
            befriend(me, x)
        fr = dict((x["id"], x) for x in social.listing(me)["friends"])
        chk("친구 목록 줄: 깃발 있는 길드 사람 → 깃발 · 깃발 없는 길드 · 길드 없음 → None", fr[boss]["flag"] == pic
            and fr[late]["flag"] == pic and fr[other]["flag"] is None and fr[lone]["flag"] is None, [(fr[k]["name"], fr[k].get("flag") is not None) for k in fr])

        s = season.SEASON
        third = mkuser("셋째마스터")
        gc = mkguild("셋째단", third)
        for gid, name in ((ga, "깃발단"), (gb, "민무늬단"), (gc, "셋째단")):
            db.run("INSERT INTO guild_war_entry (season, guild_id, name, applied_by, applied_at, locked) VALUES (?,?,?,?,?,1)",
                   (s, gid, name, 1, "2026-11-14T00:00:00+00:00"))
        # 삼각 순환전: 깃발단 → 민무늬단 → 셋째단 → 깃발단
        for gid, tgt, frm in ((ga, gb, gc), (gb, gc, ga), (gc, ga, gb)):
            db.run("INSERT INTO guild_war_pair (season, guild_id, target_guild, from_guild, kind, cap) VALUES (?,?,?,?,?,?)",
                   (s, gid, tgt, frm, "tri", 5))
        pic3 = "0" * 50 + FLAG.EMPTY * (FLAG.SIZE * FLAG.SIZE - 50)
        guild.set_flag(third, pic3)
        sm = GM._match_summary(s, gb, "war")
        chk("길드전 1:1 match: own(민무늬단) None · target(셋째단) · from(깃발단) 깃발",
            sm["own"]["flag"] is None and sm["target"]["flag"] == pic3 and sm["from"]["flag"] == pic,
            (sm["own"].get("flag"), bool(sm["target"].get("flag")), bool(sm["from"].get("flag"))))
        sm = GM._match_summary(s, ga, "war")
        chk("  우리 길드(own) 깃발도", sm["own"]["flag"] == pic and sm["target"]["flag"] is None)
        ms = GM.matches(s, ga, "war")
        gs = dict((x["guildId"], x) for x in ms[0]["guilds"])
        chk("  matches[].guilds[] 의 flag", len(ms) == 1 and gs[ga]["flag"] == pic
            and gs[gb]["flag"] is None and gs[gc]["flag"] == pic3, [(k, bool(v.get("flag"))) for k, v in gs.items()])

        print("\n=== 8. 길드를 옮기면 이름 옆 깃발도 ===")
        chk("깃발단의 마스터 = 깃발단 깃발", guild.name_flag(boss) == pic)
        mover = mkuser("이사")
        put_in(mover, ga)
        chk("  이사(일반 길드원) 깃발단 → 깃발단 깃발", guild.name_flag(mover) == pic)
        guild.leave(mover)
        chk("  길드를 나오면 None", guild.name_flag(mover) is None)
        db.run("UPDATE guild_user SET left_at=NULL WHERE user_id=?", (mover,))
        guild.join(mover, gc)
        chk("  셋째단에 들어가면 셋째단 깃발", guild.name_flag(mover) == pic3)
        db.run("DELETE FROM guild_member WHERE user_id=?", (mover,))
        put_in(mover, gb)
        chk("  깃발 없는 민무늬단이면 None", guild.name_flag(mover) is None)
        chk("  name_flags 는 여럿을 한 번에 (깃발 있는 길드에 든 사람만)",
            guild.name_flags([boss, mem, late, mover, third, lone, None]) == {boss: pic, mem: pic, late: pic, third: pic3})
    finally:
        season.SEASON = real
        config.BOARD_ADMINS = real_admins
    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
