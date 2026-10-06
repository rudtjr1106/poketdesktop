# -*- coding: utf-8 -*-
"""길드 검사 (1.10.0) — 만들기·가입·관리, 채팅, 일일 미션, 코인 상점.

    python server/test_guild.py

서버를 띄우지 않고 app.guild 의 함수를 직접 부른다 (test_boxes 와 같은 방식).

무엇을 못 박나:
  1. 만드는 데 돈이 들고, **못 만들면 돈이 그대로다.** 한 사람은 한 길드에만 든다.
  2. 자유 가입은 바로, 승인 필요는 신청 → 마스터·부마스터가 받는다. 정원을 안 넘는다.
  3. 자리마다 할 수 있는 일이 다르다. 마스터 없는 길드가 생기지 않는다.
  4. 채팅은 번호 뒤의 줄만 준다. 길드 밖 사람은 못 본다. 줄이 생기거나 길드에 일이
     있으면 listeners 로 알린다 (웹소켓이 이걸 받아 민다 - 그쪽은 test_guild_ws.py).
  5. 미션을 다 하면 점수가 길드에 모이고, 단계 보상은 **한 점이라도 보탠 사람이
     하루에 한 번** 받는다. 길드를 옮겨도 같은 날 두 번 못 받는다.
  6. 코인 상점은 상점에서 파는 것만, 코인으로만 판다.
"""
import datetime
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-guild-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from fastapi import HTTPException                            # noqa: E402

from app import (achievements, config, db, deps, guild, guild_routes, gym, items,  # noqa: E402
                 mypage)

OK = FAIL = 0
T0 = datetime.datetime(2026, 10, 6, 3, 0, tzinfo=datetime.timezone.utc)      # 한국 시각 낮 12시


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def err(fn, *a, **k):
    """HTTPException 이 났으면 (상태, 문구), 아니면 None."""
    try:
        fn(*a, **k)
    except HTTPException as e:
        return e.status_code, e.detail
    return None


def mkuser(name, money=0):
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,?,'','','')",
        (name, b"x", b"x", money))
    return cur.lastrowid


def money(uid):
    return db.q1("SELECT money FROM users WHERE id=?", (uid,))["money"]


def balls(uid):
    return db.q1("SELECT balls FROM users WHERE id=?", (uid,))["balls"]


def lines(gid):
    return [r["body"] for r in db.q("SELECT body FROM guild_chat WHERE guild_id=? ORDER BY id", (gid,))]


def later(hours):
    return T0 + datetime.timedelta(hours=hours)


def main():
    db.init()
    cost = config.GUILD_CREATE_COST
    a = mkuser("가", cost + 1000)
    b = mkuser("나")
    c = mkuser("다")
    d = mkuser("라")
    e = mkuser("마", cost * 3)

    print("=== 만들기 ===")
    chk("만드는 값은 5만", cost == 50000, cost)
    chk("돈이 모자라면 못 만든다", (err(guild.create, b, "가난길드") or (0,))[0] == 400)
    chk("  길드도 안 생긴다", db.q1("SELECT COUNT(*) c FROM guild")["c"] == 0)
    for bad in ("", "가", "가" * 13, "<길드>", " "):
        chk("이름 %r 은 안 된다" % bad, (err(guild.create, a, bad) or (0,))[0] == 400)
    chk("  돈은 그대로다", money(a) == cost + 1000, money(a))
    chk("가입 방식이 이상하면 안 된다", (err(guild.create, a, "피카단", "", "secret") or (0,))[0] == 400)
    r = guild.create(a, "  피카단 ", "피카츄를 좋아하는 사람들", "open", now=T0)
    g1 = db.q1("SELECT * FROM guild WHERE name='피카단'")
    chk("만들면 돈이 빠진다", r["ok"] and money(a) == 1000, money(a))
    chk("이름 앞뒤 공백은 뗀다", g1 is not None and g1["intro"] == "피카츄를 좋아하는 사람들")
    chk("만든 사람이 마스터", guild.member(a)["role"] == "master" and g1["master_id"] == a)
    chk("같은 이름으로는 못 만든다 (대소문자·한글 그대로)",
        (err(guild.create, e, "피카단") or (0,))[0] == 409 and money(e) == cost * 3, money(e))
    chk("이미 길드가 있으면 또 못 만든다", (err(guild.create, a, "둘째길드") or (0,))[0] == 400)
    gid = g1["id"]

    print("\n=== 찾기 ===")
    guild.create(e, "Eevee Club", "", "approve", now=T0)
    g2 = db.q1("SELECT * FROM guild WHERE name='Eevee Club'")["id"]
    ls = guild.listing(b)
    chk("길드가 둘 보인다", ls["total"] == 2 and len(ls["guilds"]) == 2, ls["total"])
    row = next(x for x in ls["guilds"] if x["id"] == gid)
    chk("이름·마스터·인원·가입 방식", row["name"] == "피카단" and row["masterName"] == "가"
        and row["members"] == 1 and row["max"] == config.GUILD_MAX_MEMBERS and row["joinMode"] == "open", row)
    chk("공지 칸은 없다 (1.10.0 에서 뺐다)", "notice" not in row)
    chk("이름 일부로 찾는다", [x["name"] for x in guild.listing(b, "eevee")["guilds"]] == ["Eevee Club"])
    chk("% 는 글자 그대로 찾는다 (다 나오지 않는다)", guild.listing(b, "%")["total"] == 0)

    print("\n=== 가입: 자유 가입 ===")
    r = guild.join(b, gid, now=T0)
    chk("바로 들어간다", r["joined"] and guild.member(b)["guild_id"] == gid and guild.member(b)["role"] == "member")
    chk("채팅에 알림이 뜬다", any("나 님이 길드에 들어왔습니다" in x for x in lines(gid)), lines(gid))
    chk("이미 길드가 있으면 다른 데 못 간다", (err(guild.join, b, g2) or (0,))[0] == 400)
    chk("없는 길드", (err(guild.join, c, 9999) or (0,))[0] == 404)

    print("\n=== 가입: 승인 필요 ===")
    r = guild.join(c, g2, "잘 부탁드립니다", now=T0)
    chk("신청만 들어간다", r["joined"] is False and guild.member(c) is None)
    chk("같은 데 두 번은 못 넣는다", (err(guild.join, c, g2) or (0,))[0] == 409)
    st = guild.state(c, now=T0)
    chk("내 신청이 보인다", st["guild"] is None and [x["name"] for x in st["pending"]] == ["Eevee Club"], st["pending"])
    st = guild.state(e, now=T0)
    chk("마스터에게 신청이 보인다", [(x["name"], x["message"]) for x in st["requests"]] == [("다", "잘 부탁드립니다")],
        st["requests"])
    chk("남의 길드 신청은 못 받는다", (err(guild.decide, a, c, True) or (0,))[0] == 404)
    chk("길드원이 아니면 못 받는다", (err(guild.decide, d, c, True) or (0,))[0] == 400)
    guild.decide(e, c, False)
    chk("돌려보내면 신청이 없어진다", db.q1("SELECT COUNT(*) c FROM guild_request")["c"] == 0)
    guild.join(c, g2, now=T0)
    guild.decide(e, c, True, now=T0)
    chk("받으면 길드원이 된다", guild.member(c)["guild_id"] == g2
        and db.q1("SELECT COUNT(*) c FROM guild_request")["c"] == 0)
    guild.join(d, g2, now=T0)
    guild.cancel_request(d, g2)
    chk("신청을 거둘 수 있다", db.q1("SELECT COUNT(*) c FROM guild_request")["c"] == 0)
    # 신청을 넣어 둔 채 다른 길드에 들어가면 신청은 사라진다
    guild.join(d, g2, now=T0)
    guild.join(d, gid, now=T0)
    chk("다른 길드에 들어가면 넣어 둔 신청이 사라진다", guild.member(d)["guild_id"] == gid
        and db.q1("SELECT COUNT(*) c FROM guild_request WHERE user_id=?", (d,))["c"] == 0)

    print("\n=== 정원 ===")
    keep = config.GUILD_MAX_MEMBERS
    config.GUILD_MAX_MEMBERS = 3                  # 피카단: 가·나·라 = 3명
    f = mkuser("바")
    chk("가득 차면 못 들어간다", (err(guild.join, f, gid) or (0,))[0] == 409 and guild.member(f) is None)
    chk("목록에 가득 참으로 나온다", next(x for x in guild.listing(f)["guilds"] if x["id"] == gid)["full"])
    config.GUILD_MAX_MEMBERS = keep

    print("\n=== 자리와 권한 ===")
    chk("길드원은 내보낼 수 없다", (err(guild.kick, b, d) or (0,))[0] == 403)
    chk("길드원은 자리를 못 바꾼다", (err(guild.set_role, b, d, "sub") or (0,))[0] == 403)
    guild.set_role(a, b, "sub", now=T0)
    chk("마스터가 부마스터로 올린다", guild.member(b)["role"] == "sub")
    chk("  채팅에 알린다", any("나 님이 부마스터가 되었습니다" in x for x in lines(gid)), lines(gid)[-2:])
    chk("부마스터는 일반 길드원을 내보낼 수 있다", err(guild.kick, b, d, now=T0) is None and guild.member(d) is None)
    chk("  부마스터는 마스터를 못 내보낸다", (err(guild.kick, b, a) or (0,))[0] == 403)
    chk("  자기 자신은 못 내보낸다", (err(guild.kick, a, a) or (0,))[0] == 400)
    chk("  남의 길드원은 못 내보낸다", (err(guild.kick, a, c) or (0,))[0] == 404)
    chk("부마스터는 소개·가입 방식을 못 바꾼다", (err(guild.update, b, intro="내 길드") or (0,))[0] == 403
        and (err(guild.update, b, mode="approve") or (0,))[0] == 403)
    guild.update(a, intro="새 소개", mode="approve")
    g = guild.guild_of(gid)
    chk("마스터는 소개·가입 방식을 바꾼다", g["intro"] == "새 소개" and g["join_mode"] == "approve")
    guild.join(f, gid, now=T0)
    chk("승인 필요로 바꾸면 신청이 쌓인다", db.q1("SELECT COUNT(*) c FROM guild_request WHERE guild_id=?", (gid,))["c"] == 1)
    guild.update(a, mode="open")
    chk("자유 가입으로 되돌리면 쌓인 신청을 비운다",
        db.q1("SELECT COUNT(*) c FROM guild_request WHERE guild_id=?", (gid,))["c"] == 0)
    keep = config.GUILD_MAX_SUBS
    config.GUILD_MAX_SUBS = 1
    guild.join(f, gid, now=T0)
    chk("부마스터 수가 차면 더 못 올린다", (err(guild.set_role, a, f, "sub") or (0,))[0] == 400)
    config.GUILD_MAX_SUBS = keep
    guild.set_role(a, b, "member", now=T0)
    chk("부마스터에서 내린다", guild.member(b)["role"] == "member")

    print("\n=== 나가기·넘기기·해산 ===")
    chk("내보내진 사람은 하루 동안 다른 길드에 못 간다", (err(guild.join, d, g2, now=later(1)) or (0,))[0] == 400
        and guild.cooldown(d, now=later(1)) > 0, guild.cooldown(d, now=later(1)))
    chk("  하루가 지나면 된다", err(guild.join, d, g2, now=later(25)) is None)
    guild.cancel_request(d, g2)
    chk("사람이 남아 있으면 마스터는 못 나간다", (err(guild.leave, a) or (0,))[0] == 400 and guild.member(a) is not None)
    guild.leave(f, now=T0)
    chk("길드원은 나갈 수 있다", guild.member(f) is None and any("바 님이 길드를 나갔습니다" in x for x in lines(gid)))
    chk("  나온 사람은 새 길드도 바로 못 만든다", (err(guild.create, f, "바로길드") or (0,))[0] == 400)
    chk("남의 길드원에게는 못 넘긴다", (err(guild.transfer, a, c) or (0,))[0] == 404)
    guild.transfer(a, b, now=T0)
    chk("마스터를 넘긴다", guild.member(b)["role"] == "master" and guild.guild_of(gid)["master_id"] == b
        and guild.member(a)["role"] == "sub", (guild.member(a)["role"], guild.member(b)["role"]))
    chk("넘긴 사람은 이제 해산 못 한다", (err(guild.disband, a) or (0,))[0] == 403)
    guild.transfer(b, a, now=T0)
    chk("혼자 남은 마스터가 나가면 길드가 없어진다",
        err(guild.leave, e) is not None)          # Eevee Club 에는 다(c)가 있다
    guild.leave(c, now=T0)
    r = guild.leave(e, now=T0)
    chk("  (혼자가 된 뒤에는 나갈 수 있고 길드도 사라진다)", guild.guild_of(g2) is None and guild.member(e) is None
        and db.q1("SELECT COUNT(*) c FROM guild_chat WHERE guild_id=?", (g2,))["c"] == 0, r)

    print("\n=== 채팅 ===")
    guild._SENT.clear()
    first = guild.chat(a, now=T0)
    chk("처음에는 지금까지의 줄을 준다", len(first["messages"]) > 0 and first["last"] == first["messages"][-1]["id"])
    chk("알림 줄은 system 이다", all(m["system"] for m in first["messages"]))
    chk("길드 밖 사람은 못 보낸다", (err(guild.chat_send, c, "안녕") or (0,))[0] == 400)
    chk("길드 밖 사람에게는 빈 답", guild.chat(c)["messages"] == [] and guild.chat(c)["guild"] is None)
    chk("빈 말은 못 보낸다", (err(guild.chat_send, a, "   ") or (0,))[0] == 400)
    chk("너무 길면 못 보낸다", (err(guild.chat_send, a, "가" * (config.GUILD_CHAT_LEN + 1)) or (0,))[0] == 400)
    guild.chat_send(a, "안녕하세요\n반갑습니다", now=T0)
    guild.chat_send(b, "어서 오세요", now=T0)
    new = guild.chat(a, first["last"], now=T0)
    chk("번호 뒤의 줄만 온다", [(m["name"], m["body"]) for m in new["messages"]]
        == [("가", "안녕하세요 반갑습니다"), ("나", "어서 오세요")], new["messages"])
    chk("내가 쓴 줄에는 mine", [m["mine"] for m in new["messages"]] == [True, False])
    chk("더 없으면 빈 목록, 번호는 그대로", guild.chat(a, new["last"])["messages"] == []
        and guild.chat(a, new["last"])["last"] == new["last"])
    keep = config.GUILD_CHAT_PER_MIN
    config.GUILD_CHAT_PER_MIN = 2
    guild._SENT.clear()
    guild.chat_send(a, "하나", now=T0)
    guild.chat_send(a, "둘", now=T0)
    chk("도배는 막는다", (err(guild.chat_send, a, "셋") or (0,))[0] == 429)
    config.GUILD_CHAT_PER_MIN = keep
    guild._SENT.clear()
    s1 = guild.chat(a, new["last"])["stamp"]
    guild.join(c, gid, now=later(30))
    chk("사람이 바뀌면 stamp 가 달라진다 (화면이 다시 받을 때를 안다)", guild.chat(a, new["last"])["stamp"] != s1)

    print("\n=== 밀어 주기 (웹소켓이 받는 것) ===")
    got = []
    guild.listeners.append(lambda kind, target, payload: got.append((kind, target, payload)))
    guild.listeners.append(lambda *a2: 1 / 0)             # 받는 쪽이 터져도 하던 일은 된다
    guild.chat_send(a, "밀어 주세요", now=T0)
    chk("말을 보내면 그 길드에 새 줄을 알린다", len(got) == 1 and got[0][:2] == ("guild", gid)
        and got[0][2]["t"] == "chat" and got[0][2]["m"]["body"] == "밀어 주세요"
        and got[0][2]["m"]["userId"] == a and got[0][2]["m"]["name"] == "가"
        and got[0][2]["m"]["system"] is False, got)
    chk("  줄 번호가 폴링으로 받는 것과 같다", got[0][2]["m"]["id"] == guild.chat(a)["last"])
    del got[:]
    before = guild._stamp(gid)
    guild.update(a, intro="밀리는 소개", now=T0)
    kinds = [(k, p2["t"]) for k, _t, p2 in got]
    chk("소개를 바꾸면 '바뀌었다' 가 간다", kinds == [("guild", "changed")], kinds)
    chk("  폴링 길에서도 달라진 것을 안다 (stamp)", guild._stamp(gid) != before)
    del got[:]
    r = guild.update(a, intro="밀리는 소개", now=T0)
    chk("  같은 소개면 아무것도 안 보낸다", got == [] and "바뀐 것이 없습니다" in r["message"], got)
    del got[:]
    z = mkuser("자")
    guild.join(z, gid, now=later(30))
    chk("누가 들어오면 알림 줄과 '바뀌었다'", [p2["t"] for _k, _t, p2 in got] == ["chat", "changed"], got)
    del got[:]
    guild.kick(a, z, now=later(30))
    chk("내보내면 그 사람에게 '나왔다' 가 먼저 간다", got[0] == ("user", z, {"t": "left"})
        and [p2["t"] for _k, _t, p2 in got[1:]] == ["chat", "changed"], got)
    del got[:]
    solo = mkuser("혼자", cost)
    guild.create(solo, "혼자길드", now=T0)
    sg = guild.member(solo)["guild_id"]
    del got[:]
    guild.disband(solo)
    chk("해산하면 그 길드 모두에게 '나왔다'", got == [("guild", sg, {"t": "left"})], got)
    del guild.listeners[:]
    db.run("DELETE FROM guild_user WHERE user_id IN (?,?)", (z, solo))

    print("\n=== 일일 미션 ===")
    db.run("DELETE FROM guild_mission")
    db.run("UPDATE guild SET points=0")
    db.run("UPDATE guild_member SET points=0")
    day = later(48)                               # 새 날
    ms = guild.missions(a, now=day)
    chk("미션 다섯 가지, 다 하면 10점", len(ms["missions"]) == 5 and ms["myMax"] == 10
        and sum(m["points"] for m in ms["missions"]) == 10)
    chk("랜덤 배틀은 10판에 3점", guild.MISSION["rank"][2:] == (10, 3), guild.MISSION["rank"])
    chk("채팅은 미션이 아니다", "chat" not in guild.MISSION)
    chk("단계는 다섯", [t["need"] for t in ms["tiers"]] == [10, 25, 45, 70, 100])
    guild.note(a, "catch", now=day)
    guild.note(a, "catch", 3, now=day)
    ms = guild.missions(a, now=day)
    m = next(x for x in ms["missions"] if x["key"] == "catch")
    chk("잡은 만큼 쌓인다 (4/5), 아직 점수는 없다", m["n"] == 4 and not m["done"] and ms["myPoints"] == 0, m)
    guild.note(a, "catch", 5, now=day)
    ms = guild.missions(a, now=day)
    m = next(x for x in ms["missions"] if x["key"] == "catch")
    chk("목표를 넘겨도 5/5, 2점이 길드에 쌓인다", m["n"] == 5 and m["done"] and ms["myPoints"] == 2
        and ms["guildPoints"] == 2 and guild.guild_of(gid)["points"] == 2 and guild.member(a)["points"] == 2,
        (m, ms["guildPoints"]))
    guild.note(a, "catch", now=day)
    chk("다 한 미션은 더 안 쌓인다", guild.missions(a, now=day)["guildPoints"] == 2)
    guild.note(c, "catch", now=day)               # 길드 밖이던 사람도 들어온 뒤로는 센다
    guild.note(mkuser("밖"), "catch", now=day)
    chk("길드에 없는 사람은 아무 일도 없다", db.q1("SELECT COUNT(*) c FROM guild_mission WHERE user_id NOT IN"
                                         " (SELECT user_id FROM guild_member)")["c"] == 0)
    chk("모르는 미션은 무시한다", guild.note(a, "nope", now=day) is None)
    # 길드 화면을 열면 출석, 채팅을 보내면 채팅 미션
    st = guild.state(b, now=day)
    chk("길드 화면을 열면 출석이 된다", next(x for x in st["mission"]["missions"] if x["key"] == "attend")["done"])
    guild.chat_send(b, "출석!", now=day)
    chk("채팅을 보내도 점수는 안 오른다 (출석 1점뿐)", guild.missions(b, now=day)["myPoints"] == 1,
        guild.missions(b, now=day)["myPoints"])
    # 다른 곳에서 부르는 고리
    achievements.on_obtain(b, {"species": "PIKACHU", "shiny": 0}, "catch")
    today_n = db.q1("SELECT n FROM guild_mission WHERE user_id=? AND key='catch' AND day=?", (b, guild.today()))
    chk("포켓몬을 잡으면 미션이 오른다 (achievements.on_obtain)", today_n is not None and today_n["n"] == 1, today_n)
    gym.record_win(b, {"region": "test-1", "id": "t1", "level": 10}, 5, guild._iso())
    today_n = db.q1("SELECT n FROM guild_mission WHERE user_id=? AND key='gym' AND day=?", (b, guild.today()))
    chk("관장을 이기면 미션이 오른다 (gym.record_win)", today_n is not None and today_n["n"] == 1, today_n)
    keep_note = guild.note
    guild.note = lambda *a2, **k2: 1 / 0
    guild.note_safe(a, "catch")
    guild.note = keep_note
    chk("미션에서 오류가 나도 부른 쪽은 멀쩡하다 (note_safe)", True)
    db.run("DELETE FROM server_error")

    print("\n=== 단계 보상 ===")
    ms = guild.missions(a, now=day)
    chk("점수가 모자라면 못 받는다", (err(guild.claim, a, 1, now=day) or (0,))[0] == 400
        and not ms["tiers"][0]["canClaim"], ms["guildPoints"])
    for u in (a, b):
        for k, _n, goal, _p in guild.MISSIONS:
            guild.note(u, k, goal, now=day)
    ms = guild.missions(a, now=day)
    chk("둘이 다 하면 20점 - 1단계가 열린다", ms["guildPoints"] == 20 and ms["tiers"][0]["canClaim"]
        and not ms["tiers"][1]["reached"], ms["guildPoints"])
    chk("  단계를 넘는 순간 채팅에 알린다", sum(1 for x in lines(gid) if "1단계 달성" in x) == 1, lines(gid)[-4:])
    chk("한 점도 안 보탠 사람은 못 받는다", (err(guild.claim, c, 1, now=day) or (0,))[0] == 400
        and not guild.missions(c, now=day)["tiers"][0]["canClaim"])
    b0 = balls(a)
    r = guild.claim(a, 1, now=day)
    chk("1단계: 몬스터볼 5개", balls(a) == b0 + 5 and "몬스터볼 5개" in r["message"], r)
    chk("두 번은 못 받는다", (err(guild.claim, a, 1, now=day) or (0,))[0] == 409 and balls(a) == b0 + 5)
    chk("받은 단계는 claimed 로 나온다", guild.missions(a, now=day)["tiers"][0]["claimed"])
    chk("없는 단계", (err(guild.claim, a, 9, now=day) or (0,))[0] == 404)
    guild.note(c, "catch", 5, now=day)
    guild.note(c, "battle", 5, now=day)
    guild.note(c, "attend", now=day)              # 20 + 2 + 2 + 1 = 25
    r = guild.claim(b, 2, now=day)
    chk("2단계: 길드 코인 10개", guild.coin(b) == 10 and "길드 코인 10개" in r["message"], guild.coin(b))
    # 길드를 옮겨도 같은 날 같은 단계를 두 번 못 받는다
    guild.leave(b, now=day)
    db.run("UPDATE guild_user SET left_at=NULL WHERE user_id=?", (b,))        # 기다림은 건너뛴다
    db.run("UPDATE users SET money=? WHERE id=?", (cost, b))
    guild.create(b, "둘째길드", now=day)
    for k, _n, goal, _p in guild.MISSIONS:
        guild.note(b, k, goal, now=day)
    chk("새 길드에서 다시 10점을 모아도", guild.missions(b, now=day)["guildPoints"] == 10)
    chk("  같은 날 1단계는 한 번뿐이다 (보상은 사람에게 건다)",
        err(guild.claim, b, 1, now=day) is None and (err(guild.claim, b, 1, now=day) or (0,))[0] == 409)
    chk("날이 바뀌면 미션도 보상도 새로 시작한다", guild.missions(a, now=later(72))["guildPoints"] == 0
        and not guild.missions(a, now=later(72))["tiers"][0]["claimed"])
    chk("자정까지 남은 시간", 0 < guild.missions(a, now=day)["resetIn"] <= 86400)

    print("\n=== 코인 상점 ===")
    sh = guild.shop(b)
    ids = set(x["id"] for x in sh["items"])
    chk("볼·사탕·병뚜껑·약·깃털이 있다", {"POKEBALL", "ULTRABALL", "RARECANDY", "BOTTLECAP", "HPUP", "SWIFTWING"} <= ids,
        sorted(ids)[:8])
    chk("상점에서 안 파는 것은 없다 (금색병뚜껑)", "GOLDBOTTLECAP" not in ids)
    chk("팔아서 돈으로 바꾸는 물건은 없다 (금구슬)", "NUGGET" not in ids and guild.coin_price("NUGGET") == 0)
    chk("값은 상점 값 / %d 올림" % config.GUILD_COIN_WON,
        guild.coin_price("POKEBALL") == 1 and guild.coin_price("ULTRABALL") == 4
        and guild.coin_price("RARECANDY") == 40, (guild.coin_price("POKEBALL"), guild.coin_price("ULTRABALL"),
                                                  guild.coin_price("RARECANDY")))
    chk("코인이 모자라면 못 산다", (err(guild.buy, b, "RARECANDY", 1) or (0,))[0] == 400 and guild.coin(b) == 10)
    r = guild.buy(b, "ULTRABALL", 2)
    chk("하이퍼볼 2개 = 코인 8개", guild.coin(b) == 2 and items.bag_count(b, "ULTRABALL") == 2, (guild.coin(b), r))
    chk("없는 물건", (err(guild.buy, b, "NUGGET", 1) or (0,))[0] == 404 and (err(guild.buy, b, "없는것", 1) or (0,))[0] == 404)
    chk("코인이 한 번도 없던 사람도 오류 없이 거절", (err(guild.buy, mkuser("빈손"), "POKEBALL", 1) or (0,))[0] == 400)
    guild.leave(b, now=day)                       # 혼자라 길드가 없어진다
    chk("길드를 나와도 코인은 남는다", guild.coin(b) == 2 and guild.shop(b)["coin"] == 2 and not guild.shop(b)["inGuild"])

    print("\n=== 화면에 줄 것 ===")
    st = guild.state(a, now=day)
    chk("길드·내 자리·코인·돈", st["guild"]["name"] == "피카단" and st["role"] == "master"
        and st["can"] == {"manage": True, "master": True} and "coin" in st and "money" in st, st["role"])
    chk("길드원 목록: 마스터가 맨 위", st["members"][0]["role"] == "master" and st["members"][0]["me"]
        and len(st["members"]) == st["guild"]["members"], [x["name"] for x in st["members"]])
    chk("길드원마다 오늘 점수와 누적 점수", all("today" in x and "points" in x for x in st["members"])
        and st["members"][0]["today"] == 10, st["members"][0])
    chk("일반 길드원에게는 신청 목록이 비어 있다", guild.state(c, now=day)["requests"] == []
        and guild.state(c, now=day)["can"] == {"manage": False, "master": False})
    st = guild.state(d, now=later(100))
    chk("길드가 없는 사람: 만드는 값·정원·기다림", st["guild"] is None and st["createCost"] == cost
        and st["max"] == config.GUILD_MAX_MEMBERS and st["cooldown"] == 0, st)
    chk("정원 15명, 부마스터 1명", config.GUILD_MAX_MEMBERS == 15 and config.GUILD_MAX_SUBS == 1
        and st["limits"]["subs"] == 1, (config.GUILD_MAX_MEMBERS, config.GUILD_MAX_SUBS))
    chk("내 번호가 실려 온다 (채팅에서 내 말을 가린다)", st["me"] == d)

    print("\n=== 길드원 프로필 (마이페이지에 보이는 것) ===")
    pr = guild_routes.profile(c, ctx={"user": {"id": a, "username": "가"}})
    chk("같은 길드원의 프로필을 본다: 이름과 길드 자리", pr["user"]["name"] == "다"
        and pr["guild"]["role"] == "member" and pr["guild"]["roleKr"] == "길드원"
        and pr["guild"]["me"] is False, (pr["user"], pr["guild"]))
    chk("  포켓몬·도감·관장·레이드·시즌 기록이 실린다", set(("pokemon", "shiny", "dexCaught", "dexTotal",
        "friends")) <= set(pr["counts"]) and set(("cleared", "total")) <= set(pr["gym"])
        and "wins" in pr["raid"] and pr["seasons"] and pr["seasons"][0]["current"] is True
        and "owned" in pr["titles"], sorted(pr))
    chk("  소지금과 게시판 활동은 안 실린다 (본인만 본다)", "money" not in pr["user"]
        and "admin" not in pr["user"] and "board" not in pr, sorted(pr["user"]))
    mine = mypage.build({"id": c, "username": "다"}, deps.dex())
    chk("  내 마이페이지와 같은 숫자다", all(pr[k] == mine[k] for k in ("counts", "gym", "raid", "seasons",
        "titles")) and mine["user"]["money"] == money(c) and "board" in mine)
    me = guild_routes.profile(a, ctx={"user": {"id": a, "username": "가"}})
    chk("  내 프로필도 본다", me["guild"]["me"] is True and me["guild"]["role"] == "master")
    chk("다른 길드·길드 없는 사람의 프로필은 못 본다", (err(guild.peer, a, d) or (0,))[0] == 403
        and (err(guild.peer, a, e) or (0,))[0] == 403, err(guild.peer, a, d))
    chk("  길드가 없는 사람은 누구 것도 못 본다", err(guild.peer, d, a) is not None, err(guild.peer, d, a))

    print("\n=== 회원탈퇴 ===")
    guild.on_user_deleted(a, now=day)             # 피카단: 가(마스터)·다
    db.run("DELETE FROM users WHERE id=?", (a,))
    chk("마스터가 탈퇴하면 남은 사람이 마스터가 된다", guild.member(c)["role"] == "master"
        and guild.guild_of(gid)["master_id"] == c and guild.member(a) is None)
    guild.on_user_deleted(c, now=day)
    db.run("DELETE FROM users WHERE id=?", (c,))
    chk("혼자 남은 마스터가 탈퇴하면 길드가 없어진다", guild.guild_of(gid) is None
        and db.q1("SELECT COUNT(*) c FROM guild_member WHERE guild_id=?", (gid,))["c"] == 0)
    chk("길드에 없던 사람의 탈퇴는 아무 일도 없다", guild.on_user_deleted(d) is None)
    chk("오류 기록이 없다", db.q1("SELECT COUNT(*) c FROM server_error")["c"] == 0,
        db.q("SELECT path, detail FROM server_error LIMIT 3"))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
