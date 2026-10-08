# -*- coding: utf-8 -*-
"""길드 친선전 검사 (1.10.3).

    python server/test_friendly.py

서버를 띄우지 않는다 (임시 DB). 길드 웹소켓으로 나가는 것은 guild.listeners 에 걸어서 본다.

무엇을 못 박나:
  1. '상대 구함' 을 켜면 길드원에게 보이고(채팅에도 한 줄), 끄거나 시간이 지나면 사라진다.
  2. 길드원이 받으면 **그 자리에서 실시간 배틀이 열린다** (친구가 아니어도). 건 쪽 화면에는
     '배틀 창을 띄우라' 는 알림이 간다.
  3. 판이 넘어갈 때마다 구경용 모습이 길드원에게 나간다 - 같은 장면은 두 번 안 나간다.
     끝나면 목록에서 빠진다. 구경용에는 참가자만 아는 것(기술 목록·지닌 도구)이 없다.
  4. **길드원끼리의 실시간 배틀은 어떻게 열었든 길드 것이다** (친구 목록으로 열어도 구경한다).
     다른 길드 사람과의 판은 나가지 않는다.
  5. 동시에 MAX_FIGHTS 판까지만 받는다 - 넘으면 잠시 후에 해 달라고 한다.
  6. 길드원에게는 친구가 아니어도 직접 신청할 수 있다 (상대가 받아야 시작한다).
  7. 알림 없이 끝난 판(둘 다 자리를 떴다)은 살필 때 치운다.
  8. **채팅의 카드**: 상대를 구하면 채팅에 카드 한 장이 놓이고, 받으면 **같은 줄**이 '진행 중' 으로,
     끝나면 결과로 바뀐다 (줄을 새로 적지 않는다). 그만두거나 시간이 지나면 닫힌다. 지금 모습
     (view)에 그 줄 번호가 실려서, 화면이 어느 카드가 살아 있는지 안다.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-friendly-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import config, db, friendly, guild, live, main, social      # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mkuser(name, money=0):
    return db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                  " created_at, last_login, last_ip) VALUES (?,?,?,1,10,?,'','','')",
                  (name, b"x", b"x", money)).lastrowid


def mkmon(uid, species="PIKACHU", slot=0):
    return db.run(
        "INSERT INTO pokemon (user_id, species, level, exp, nature, ability, hidden_ability, gender,"
        " shiny, happiness, ivs, evs, moves, on_desktop, slot, met_level, caught_at)"
        " VALUES (?,?,20,0,'HARDY',NULL,0,'M',0,70,'{}','{}',?,1,?,5,'')",
        (uid, species, json.dumps(["TACKLE", "GROWL"]), slot)).lastrowid


class Clock(object):
    """검사가 돌리는 시계. friendly 가 재는 시각을 전부 이것으로 바꿔 끼운다 (진짜 시계와 섞이면
    '상대 구함' 이 엉뚱한 때에 만료된다)."""
    t = 1000.0

    def monotonic(self):
        return self.t


CLOCK = Clock()
friendly.time = CLOCK


def at(t):
    CLOCK.t = float(t)
    return CLOCK.t


def card_at(line):
    """채팅 줄에 적혀 있는 카드와 글 (DB 에서)."""
    r = db.q1("SELECT body, card FROM guild_chat WHERE id=?", (line,))
    return (json.loads(r["card"]) if r and r["card"] else None), (r["body"] if r else None)


def raises(kind, fn, *a):
    try:
        fn(*a)
    except kind as e:
        return str(e) or "?"
    return ""


def main_():
    db.init()
    cost = config.GUILD_CREATE_COST
    ids = dict((n, mkuser(n, cost if n in ("가람", "남길") else 0))
               for n in ("가람", "나래", "다솜", "라온", "마루", "바다", "사랑", "아름", "남길", "남원"))
    for u in ids.values():
        mkmon(u)
    a, b, c = ids["가람"], ids["나래"], ids["다솜"]
    guild.create(a, "친선단", "", "open")
    gid = guild.member(a)["guild_id"]
    for n in ("나래", "다솜", "라온", "마루", "바다", "사랑", "아름"):
        guild.join(ids[n], gid)
    guild.create(ids["남길"], "남의길드", "", "open")
    other_gid = guild.member(ids["남길"])["guild_id"]
    guild.join(ids["남원"], other_gid)
    sent = []
    guild.listeners.append(lambda kind, target, payload: sent.append((kind, target, payload)))

    def got(t, kind=None, target=None):
        return [p for k, tg, p in sent if p.get("t") == t and (kind is None or k == kind)
                and (target is None or tg == target)]

    print("=== 상대 구함 ===")
    chk("처음에는 아무도 없다", friendly.state(a) == {"seeking": [], "fights": [], "limit": friendly.MAX_FIGHTS})
    v = friendly.seek(a, True, now=at(100.0))
    chk("켜면 상대를 구하는 사람으로 보인다 (남은 시간과 함께)", [(s["id"], s["name"]) for s in v["seeking"]] == [(a, "가람")]
        and v["seeking"][0]["left"] == friendly.SEEK_SEC, v)
    chk("  길드원 화면에 바로 나간다", got("friendly", "guild", gid) and got("friendly")[-1]["seeking"][0]["id"] == a)
    cards = [p["m"] for p in got("chat") if p["m"].get("card")]
    line = cards[-1]["id"] if cards else 0
    me_a = {"id": a, "name": "가람"}
    chk("  **길드 채팅에 카드 한 장이 놓인다** (알림 줄 + 카드. 옛 화면은 글만 본다)", len(cards) == 1 and cards[0]["system"]
        and cards[0]["body"] == "가람 님이 친선전 상대를 구합니다."
        and cards[0]["card"] == {"k": "friendly", "s": "seek", "a": me_a}, cards)
    chk("  지금 모습에 그 줄 번호가 실린다 (화면이 어느 카드가 살아 있는지 안다)", v["seeking"][0]["card"] == line > 0, v)
    n_chat = len(got("chat"))
    friendly.seek(a, True, now=at(100.5))
    chk("  구하는 중에 또 구해도 카드는 그대로다", len(got("chat")) == n_chat and got("card") == [])
    friendly.seek(a, False, now=at(101.0))
    chk("  그만두면 그 카드가 닫힌다", got("card")[-1] == {"t": "card", "id": line, "card": {"k": "friendly", "s": "closed", "a": me_a}}
        and card_at(line)[0]["s"] == "closed", got("card")[-1:])
    friendly.seek(a, True, now=at(102.0))
    chk("  껐다 바로 다시 켜도 채팅을 도배하지 않는다 - **놓았던 카드를 되살린다**", len(got("chat")) == n_chat
        and got("card")[-1]["id"] == line and got("card")[-1]["card"]["s"] == "seek"
        and friendly.view(gid, at(102.0))["seeking"][0]["card"] == line, got("card")[-1:])
    chk("  남의 길드에는 안 보인다", friendly.view(other_gid, at(102.0))["seeking"] == [])
    chk("시간이 지나면 저절로 꺼진다 (카드도 닫힌다)", friendly.view(gid, at(102.0 + friendly.SEEK_SEC + 1))["seeking"] == []
        and card_at(line)[0]["s"] == "closed" and got("card")[-1]["card"]["s"] == "closed", card_at(line))
    friendly.seek(a, True, now=at(102.0 + friendly.SEEK_SEC + 2))
    chk("  한참 뒤에 다시 구하면 카드를 새로 놓는다", len(got("chat")) == n_chat + 1 and got("chat")[-1]["m"]["id"] > line
        and card_at(line)[0]["s"] == "closed")
    friendly.seek(a, False, now=at(102.0 + friendly.SEEK_SEC + 3))
    listed = dict((m["id"], m) for m in guild.chat(c)["messages"])
    chk("  채팅을 받아 올 때도 카드가 실린다 (보통 줄에는 없다)", listed[line].get("card", {}).get("s") == "closed"
        and listed[line]["system"] and not any("card" in m for m in listed.values() if "친선전" not in m["body"]), listed.get(line))
    chk("길드가 없으면 못 쓴다", "길드" in raises(LookupError, friendly.state, mkuser("떠돌이")))
    db.run("DELETE FROM pokemon WHERE user_id=?", (ids["아름"],))
    chk("데리고 다니는 포켓몬이 없으면 못 구한다", "포켓몬" in raises(ValueError, friendly.seek, ids["아름"], True))

    print("\n=== 받기 -> 바로 시작 ===")
    del sent[:]
    at(1000.0)
    friendly.seek(a, True, now=at(1200.0))
    line = friendly.view(gid, at(1200.0))["seeking"][0]["card"]
    chk("자기 것은 못 받는다", raises(ValueError, friendly.accept, a, a, at(1201.0)) != "")
    chk("상대를 구하지 않는 사람의 것은 못 받는다", "구하고 있지" in raises(ValueError, friendly.accept, a, b, at(1201.0)))
    chk("남의 길드 사람은 못 받는다", "구하고 있지" in raises(ValueError, friendly.accept, ids["남길"], a, at(1201.0))
        or "길드" in raises(ValueError, friendly.accept, ids["남길"], a, at(1201.0)))
    chk("  (둘은 친구가 아니다)", not social.is_friend(a, b))
    row = friendly.accept(b, a, now=at(1202.0))
    chk("**받으면 그 자리에서 실시간 배틀이 열린다** (구한 쪽이 a, 받은 쪽이 b)", row["state"] == "fighting"
        and (row["a_id"], row["b_id"]) == (a, b) and live.my_match(a)["id"] == row["id"])
    chk("  구한 쪽 화면에 '배틀 창을 띄우라' 고 알린다 (그쪽은 아무것도 안 눌렀다)", got("live", "user", a) == [{"t": "live"}])
    fights = got("friendly_fight", "guild", gid)
    f0 = fights[0]["fight"] if fights else {}
    chk("  길드원에게 구경용 모습이 나간다: 두 사람과 나와 있는 포켓몬·체력", len(fights) == 1 and f0.get("id") == row["id"]
        and f0["a"]["name"] == "가람" and f0["b"]["name"] == "나래" and f0["a"]["mon"]["num"] == 25
        and f0["a"]["mon"]["hp"] == f0["a"]["mon"]["maxhp"] > 0 and f0["over"] is False, fights[:1])
    texts = [e.get("text") for e in f0.get("events") or []]
    chk("  글은 누구 편도 아니다 ('상대' 가 없고 누가 내보냈는지 붙는다)", texts[:1] == ["가람 님과 나래 님의 승부!"]
        and texts[1].startswith("가람: 가랏! ") and texts[2].startswith("나래: 가랏! ") and not any("상대" in (t or "") for t in texts), texts)
    flat = json.dumps(f0, ensure_ascii=False)
    chk("  참가자만 아는 것은 없다 (기술 목록·지닌 도구·특성)", not any(k in flat for k in ('"moves"', '"held"', '"ability"', '"pp"')))
    v = friendly.state(c)
    chk("  목록: 진행 중인 판에 올라가고, '상대 구함' 에서는 빠진다", [f["id"] for f in v["fights"]] == [row["id"]] and v["seeking"] == []
        and friendly.count(gid) == 1, v)
    chk("  상금도 점수도 없다 (실시간 배틀 그대로)", db.q1("SELECT money FROM users WHERE id=?", (b,))["money"] == 0)
    me_b = {"id": b, "name": "나래"}
    card, body = card_at(line)
    chk("  **카드: 같은 줄이 '진행 중' 으로 바뀐다** (줄을 새로 적지 않는다)", card == {"k": "friendly", "s": "fight", "a": me_a, "b": me_b, "mid": row["id"]}
        and body == "가람 님과 나래 님의 친선전이 열렸습니다." and not [p for p in got("chat") if p["m"]["id"] > line]
        and got("card")[-1] == {"t": "card", "id": line, "card": card, "body": body}, (card, body))
    chk("  구경용 모습에 그 줄 번호가 실린다", f0.get("card") == line and v["fights"][0].get("card") == line, f0.get("card"))

    print("\n=== 판이 넘어갈 때 ===")
    del sent[:]
    va = live.public(live.my_match(a), a)["battle"]
    live.act(a, "move", va["me"]["moves"][0]["key"])
    chk("한쪽만 고르면 다시 내보내지 않는다 (장면이 그대로다 - 구경꾼이 같은 줄을 두 번 본다)", got("friendly_fight") == [])
    live.act(b, "move", va["me"]["moves"][0]["key"])
    f1 = got("friendly_fight")[-1]["fight"]
    chk("둘 다 고르면 턴이 돌고 일어난 일이 나간다", f1["turn"] == 1 and any(e.get("t") == "move" and e.get("move") for e in f1["events"])
        and not any("상대" in (e.get("text") or "") for e in f1["events"]), [e.get("text") for e in f1["events"]][:4])
    del sent[:]
    live.act(a, "forfeit", None)
    last = got("friendly_fight")[-1]["fight"]
    chk("끝나면 결과가 나가고 목록에서 빠진다", last["over"] is True and last["result"] in ("a", "b", "draw")
        and friendly.state(c)["fights"] == [] and friendly.count(gid) == 0, last)
    chk("  끝난 뒤의 목록이 길드원 화면에 나간다", got("friendly") and got("friendly")[-1]["fights"] == [])
    card, body = card_at(line)
    chk("  **카드에 결과가 적힌다** (가람이 기권했다 - 나래 승)", card == {"k": "friendly", "s": "over", "a": me_a, "b": me_b, "mid": row["id"], "result": "b"}
        and body == "가람 님과 나래 님의 친선전 - 나래 님 승리" and got("card")[-1]["card"] == card, (card, body))
    n_chat = db.q1("SELECT COUNT(*) c FROM guild_chat WHERE guild_id=?", (gid,))["c"]
    friendly.seek(a, True, now=at(1210.0))
    line2 = friendly.view(gid, at(1210.0))["seeking"][0]["card"]
    chk("  끝난 판의 카드는 되살리지 않는다 - 다시 구하면 새 카드다", line2 > line and card_at(line)[0]["s"] == "over"
        and db.q1("SELECT COUNT(*) c FROM guild_chat WHERE guild_id=?", (gid,))["c"] == n_chat + 1)
    friendly.seek(b, True, now=at(1211.0))
    line3 = friendly.view(gid, at(1211.0))["seeking"][-1]["card"]
    row2 = friendly.accept(b, a, now=at(1212.0))
    chk("  둘 다 구하다가 한쪽이 받으면: 건 사람의 카드가 판의 것이 되고 남는 카드는 닫힌다", card_at(line2)[0]["s"] == "fight"
        and card_at(line2)[0]["mid"] == row2["id"] and card_at(line3)[0]["s"] == "closed" and line3 > line2
        and friendly.view(gid, at(1212.0))["seeking"] == [], (card_at(line2), card_at(line3)))
    live.act(b, "forfeit", None)
    chk("  (나래가 기권했다 - 가람 승)", card_at(line2)[0]["result"] == "a" and "가람 님 승리" in card_at(line2)[1], card_at(line2))

    print("\n=== 길드원끼리의 실시간 배틀은 어떻게 열었든 길드 것이다 ===")
    del sent[:]
    chk("길드원에게는 친구가 아니어도 신청할 수 있다", live.can_invite(a, c) in (None, "상대가 지금 접속해 있지 않습니다. 실시간 배틀은 둘 다 켜 있어야 합니다."),
        live.can_invite(a, c))
    chk("  길드도 친구도 아니면 못 건다", "길드원" in (live.can_invite(a, ids["남길"]) or ""), live.can_invite(a, ids["남길"]))
    keep = social.is_online
    social.is_online = lambda uid: True
    try:
        inv = friendly.ask(a, c)
        chk("직접 신청: 평소의 초대가 생기고(상대가 받아야 시작), 상대 화면에 바로 알린다", inv["state"] == "invited"
            and got("live", "user", c) == [{"t": "live"}] and got("friendly_fight") == [], inv["state"])
        chk("  남의 길드 사람에게는 못 한다", raises(LookupError, friendly.ask, a, ids["남길"]) != "")
        live.accept(c, inv["id"])
        chk("  받으면 열리고 **길드원이 구경한다** (친선전 목록에도 뜬다)", len(got("friendly_fight")) == 1
            and [f["id"] for f in friendly.state(b)["fights"]] == [inv["id"]])
        new = [p["m"] for p in got("chat") if p["m"].get("card")]
        chk("  **'상대 구함' 없이 열린 판은 그때 카드를 새로 놓는다** ('진행 중' 으로)", len(new) == 1 and new[0]["card"]["s"] == "fight"
            and new[0]["card"]["mid"] == inv["id"] and (new[0]["card"]["a"]["name"], new[0]["card"]["b"]["name"]) == ("가람", "다솜")
            and got("friendly_fight")[0]["fight"]["card"] == new[0]["id"], new)
        live.act(c, "forfeit", None)
        del sent[:]
        x, y = ids["남길"], ids["남원"]
        rx = live.open_direct(x, y)
        chk("남의 길드의 판은 그 길드에만 나간다", [tg for k, tg, p in sent if p.get("t") == "friendly_fight"] == [other_gid])
        live.act(x, "forfeit", None)
        rz = None
        social.add_friend(a, ids["남원"]) if hasattr(social, "add_friend") else None
    finally:
        social.is_online = keep

    print("\n=== 동시에 %d판까지 ===" % friendly.MAX_FIGHTS)
    pairs = [(ids["가람"], ids["나래"]), (ids["다솜"], ids["라온"]), (ids["마루"], ids["바다"])]
    for i, (p, q) in enumerate(pairs):
        friendly.seek(p, True, now=at(300.0 + i))
        friendly.accept(q, p, now=at(300.5 + i))
    chk("세 판이 열렸다", friendly.count(gid) == friendly.MAX_FIGHTS == 3)
    mkmon(ids["아름"])
    friendly.seek(ids["사랑"], True, now=at(310.0))
    why = raises(ValueError, friendly.accept, ids["아름"], ids["사랑"], at(311.0))
    chk("**넷째는 받지 못한다 - 잠시 후에 해 달라고 한다**", "3판 진행 중" in why and "잠시 후" in why and not live.my_match(ids["사랑"]), why)
    chk("  상대 구함은 그대로 남는다", [s["id"] for s in friendly.view(gid, at(311.0))["seeking"]] == [ids["사랑"]])
    live.act(ids["다솜"], "forfeit", None)
    row4 = friendly.accept(ids["아름"], ids["사랑"], now=at(312.0))
    chk("  한 판이 끝나면 받을 수 있다", row4["state"] == "fighting" and friendly.count(gid) == 3)

    print("\n=== 알림 없이 끝난 판 ===")
    db.run("UPDATE live_match SET state='done', result='expired' WHERE id=?", (row4["id"],))
    del sent[:]
    friendly._sweep(gid, force=True)
    chk("둘 다 자리를 떠서 만료된 판은 살필 때 치운다 ('진행 중' 이 영영 남지 않게)", friendly.count(gid) == 2
        and any(p["fight"]["id"] == row4["id"] and p["fight"]["over"] for p in got("friendly_fight")), friendly.count(gid))
    ended = [p for p in got("card") if p["card"].get("mid") == row4["id"]]
    chk("  그 카드는 승패 없이 끝난 것으로 적힌다", len(ended) == 1 and ended[0]["card"]["s"] == "over" and ended[0]["card"]["result"] is None
        and ended[0]["body"] == "사랑 님과 아름 님의 친선전이 끝났습니다.", ended)
    for p, _q in pairs:
        if live.my_match(p):
            live.act(p, "forfeit", None)
    chk("다 끝나면 비어 있다", friendly.state(a)["fights"] == [])

    print("\n=== 경로 ===")
    paths = main.app.openapi()["paths"]
    chk("경로가 붙어 있다", all(p in paths for p in ("/api/guild/friendly", "/api/guild/friendly/seek",
                                              "/api/guild/friendly/accept/{other}", "/api/guild/friendly/ask/{other}")))
    chk("광장은 없다", not any("plaza" in p for p in paths) and "plaza" not in guild.state(a))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
