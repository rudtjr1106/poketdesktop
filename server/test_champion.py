# -*- coding: utf-8 -*-
"""챔피언리그 (독도) 검사.

    python server/test_champion.py

서버를 띄우지 않는다 (임시 DB). 앱으로 나가는 알림(visit.push)은 가로채서 본다.

무엇을 못 박나:
  1. 자격: 관장을 전부 이겨야 참가자다. 한 번 참가자가 되면 관장이 바뀌어 255곳이 돼도 빠지지 않는다.
     마지막 관장을 이기는 순간(gym.record_win) 참가자로 적힌다.
  2. 여는 때 전에는 기다리기 · 도전이 막힌다. 팀이 랭크전 조건(Lv.50 이상 6마리)을 못 채워도 막힌다.
  3. [상대 찾기]: 먼저 기다리던 사람과 그 자리에서 판이 열린다 (kind=champion, 먼저 기다린 사람이 a).
     아무도 없으면 기다리고, **1분 기다려도 상대가 없으면** 접속 중인 다른 참가자에게 '기다린다' 가 간다
     (한 번만, 껐다 켜도 3분에 한 번. 1분 안에 붙으면 안 간다).
     꺼진 사람 · 다른 판에 들어간 사람은 대기열에서 걷힌다. 동시에 눌러도 판은 하나다.
  4. 직접 도전: 상대가 받아야 시작한다 (보통 실시간 초대와 같은 길). 기다리던 사람에게 걸면 바로 시작한다.
     판이 열리면 두 사람에게 '열렸다' 가 한 번 간다.
  5. 기록: 점수 · 보상 없이 몇전 몇승 몇패. 이긴 횟수로 순위 (같으면 진 횟수, 승패가 같으면 같은 등수).
     같은 두 사람의 판은 하루 3판까지만 전적에 든다. 접힌 판 · 거절은 안 센다. 상금이 안 나간다.
  6. 관전 (길드전처럼, 참가자만): 판이 열리면 접속 중인 다른 참가자에게 알리고, 보는 사람에게 턴마다 새 모습을
     민다 (같은 장면은 한 번). 구경꾼 수가 바뀌면 싸우는 두 사람에게 '관전 N명'. 참가자가 아니면 못 본다.
     친구 · 길드 판은 이 길로 안 보인다. 길드원끼리의 리그 판은 친선전 카드로 안 나간다.
  7. 화면에 주는 모습(state)과 관장 지도에 얹는 것(brief).
"""
import datetime
import json
import os
import random
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-champion-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_CHAMPION_START"] = "2020-01-01T00:00:00+09:00"     # 검사는 열린 리그에서 (닫힌 것은 따로 본다)

from common.pokelogic import make_pokemon                            # noqa: E402

from app import champion, config, db, deps, friendly, gym, live, visit   # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc
TEAM = ("PIKACHU", "BULBASAUR", "CHARMANDER", "SQUIRTLE", "EEVEE", "MACHOP")

PUSHED = []


def _fake_push(uid, payload):
    PUSHED.append((uid, payload))


visit.push = _fake_push
SCHED = []
champion._schedule = lambda delay: SCHED.append(delay)     # 진짜 타이머 대신 - 검사가 _due 를 시각을 주고 부른다


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mkuser(name, level=50, mons=6, online=True):
    now = live._iso()
    uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                 " created_at, last_login, last_ip) VALUES (?,?,?,1,10,1000,?,?,'')",
                 (name, b"x", b"x", now, now)).lastrowid
    seen = now if online else "2020-01-01T00:00:00+00:00"
    db.run("INSERT INTO sessions (token_hash, user_id, ip, device, created_at, last_seen, expires_at)"
           " VALUES (?,?,'','t',?,?,?)", ("tok-%d" % uid, uid, now, seen, now))
    d = deps.dex()
    rng = random.Random(uid)
    for i, sp in enumerate(TEAM[:mons]):
        m = make_pokemon(d.get(sp), level, rng)
        db.run("INSERT INTO pokemon (user_id, species, level, exp, nature, ability, hidden_ability, gender,"
               " shiny, happiness, ivs, evs, moves, on_desktop, slot, met_level, caught_at)"
               " VALUES (?,?,?,0,?,?,0,?,0,70,?,?,?,1,?,?,?)",
               (uid, m["species"], level, m["nature"], m.get("ability"), m.get("gender", "M"),
                json.dumps(m["ivs"]), json.dumps(m.get("evs", {})), json.dumps(m["moves"]), i, level, now))
    return uid


def set_online(uid, on):
    db.run("UPDATE sessions SET last_seen=? WHERE user_id=?",
           (live._iso() if on else "2020-01-01T00:00:00+00:00", uid))


def clear_all(uid, skip=0):
    """관장을 전부 (skip 곳 빼고) 이긴 것으로 적는다."""
    now = live._iso()
    codes = sorted(gym.gyms()["regions"])
    for code in codes[skip:]:
        db.run("INSERT INTO gym_clear (user_id, region, trainer, wins, best_turns, first_at, last_at, paid_on)"
               " VALUES (?,?,?,1,5,?,?,'')", (uid, code, gym.gyms()["regions"][code], now, now))
    return codes[:skip]


def make_member(name, **kw):
    uid = mkuser(name, **kw)
    clear_all(uid)
    champion.qualify(uid)
    return uid


def pushed(uid, s=None):
    return [p for u, p in PUSHED if u == uid and p.get("t") == "champion" and (s is None or p.get("s") == s)]


def finish(row, loser):
    """loser 가 기권해서 끝낸다."""
    live.act(loser, "forfeit", None)
    return live.get(row["id"])


def ctx(uid):
    return {"user": {"id": uid}}


def main():
    db.init()
    champion.reset()

    print("=== 자격 ===")
    a = mkuser("가람")
    left = clear_all(a, skip=1)
    chk("255곳이면 참가자가 아니다", champion.qualify(a) is False)
    chk("  까닭에 몇 곳인지", "255" in (champion.why_not(a) or ""), champion.why_not(a))
    t = gym.trainer_at(left[0])
    gym.record_win(a, t, 5, live._iso())
    chk("마지막 관장을 이기는 순간 참가자로 적힌다", champion.member_row(a) is not None)
    db.run("DELETE FROM gym_clear WHERE user_id=? AND region=?", (a, left[0]))
    chk("관장이 바뀌어 255곳이 돼도 그대로 참가자", champion.qualify(a) is True and champion.cleared(a) == 255,
        champion.cleared(a))
    chk("참가자는 기다릴 수 있다", champion.why_not(a) is None, champion.why_not(a))
    weak = mkuser("약한팀", level=30)
    clear_all(weak)
    chk("팀이 Lv.50 6마리가 아니면 막힌다", "Lv.50" in (champion.why_not(weak) or ""), champion.why_not(weak))
    try:
        champion.seek(weak, True)
        chk("  기다리기도 막힌다", False)
    except ValueError:
        chk("  기다리기도 막힌다", True)
    old = config.CHAMPION_START
    config.CHAMPION_START = "2099-11-16T00:00:00+09:00"
    chk("여는 때 전에는 막힌다", "11월 16일 0시" in (champion.why_not(a) or ""), champion.why_not(a))
    chk("  여는 때 전 모습: open=False", champion.state(a)["open"] is False)
    config.CHAMPION_START = old

    print("=== 상대 찾기 ===")
    b = make_member("나래")
    c = mkuser("다솜")
    clear_all(c)                             # 관장은 다 이겼지만 관장 탭 · 독도 창을 아직 안 열었다
    almost = mkuser("거의")
    clear_all(almost, skip=1)
    champion.sync_members(force=True)
    chk("다 이긴 사람은 창을 안 열었어도 참가자로 채워진다", champion.member_row(c) is not None)
    chk("  255곳은 안 채운다", champion.member_row(almost) is None)
    off = make_member("꺼둠", online=False)
    stranger = mkuser("구경꾼")                   # 참가자가 아니다
    PUSHED[:] = []
    r = champion.seek(a, True)
    chk("아무도 없으면 기다린다", r is None and champion.state(a)["seeking"] is True)
    chk("  남은 시간이 보인다", 0 < champion.state(a)["waitLeft"] <= config.CHAMPION_WAIT_SEC)
    chk("  1분 뒤 알림 타이머를 건다", SCHED == [60] and config.CHAMPION_NOTIFY_SEC == 60, SCHED)
    chk("바로는 아무에게도 안 알린다", not pushed(b, "wait") and not pushed(c, "wait"), PUSHED)
    t0 = champion._wait[a]
    chk("  59초에도 아직", champion._due(t=t0 + 59) == 0 and not pushed(b, "wait"), PUSHED)
    chk("1분이 지나도 상대가 없으면 접속 중인 다른 참가자에게 '기다린다' 가 간다", champion._due(t=t0 + 60) == 1
        and any(p.get("id") == a and p.get("name") == "가람" for p in pushed(b, "wait")) and pushed(c, "wait"),
        PUSHED)
    chk("  꺼져 있는 참가자 · 참가자가 아닌 사람에게는 안 간다", not pushed(off) and not pushed(stranger))
    chk("  한 번만 (다시 때가 와도)", champion._due(t=t0 + 300) == 0 and len(pushed(b, "wait")) == 1, PUSHED)
    champion.seek(a, False)
    chk("끄면 빠진다", champion.state(a)["seeking"] is False)
    PUSHED[:] = []
    champion.seek(a, True)
    champion._due(t=champion._wait[a] + 61)
    chk("껐다 켜도 3분 안에는 다시 안 알린다", not pushed(b, "wait"), PUSHED)
    st = champion.state(b)
    chk("다른 사람 화면에 기다리는 사람이 보인다", [w["name"] for w in st["waiting"]] == ["가람"], st["waiting"])
    chk("  접속 중인 참가자 목록에 '기다림' 으로", any(o["id"] == a and o["waiting"] for o in st["online"]),
        st["online"])
    PUSHED[:] = []
    row = champion.seek(b, True)
    chk("기다리던 사람이 있으면 그 자리에서 판이 열린다", row is not None and row["state"] == "fighting",
        row and row["state"])
    chk("  챔피언리그 판이다", live.kind_of(row) == "champion")
    chk("  먼저 기다린 사람이 a", row["a_id"] == a and row["b_id"] == b, (row["a_id"], row["b_id"]))
    chk("  둘 다 대기열에서 빠진다", not champion.state(c)["waiting"], champion.state(c)["waiting"])
    chk("  두 사람에게 '열렸다' 가 한 번씩", len(pushed(a, "match")) == 1 and len(pushed(b, "match")) == 1, PUSHED)
    chk("  붙은 기다림은 1분이 지나도 안 알린다", champion._due(t=time.monotonic() + 120) == 0 and not pushed(c, "wait"),
        PUSHED)
    v = live.public(row, a)
    chk("  배틀 창이 받는 판에 kind", v["kind"] == "champion", v.get("kind"))
    chk("  /api/me 의 실시간 카드에도 kind", (live.me_card(b) or {}).get("kind") == "champion")
    chk("진행 중이면 기다리기 막힘", "진행 중" in (champion.why_not(a) or ""))
    chk("진행 중인 판 목록", [f["id"] for f in champion.state(c)["fights"]] == [row["id"]])
    live.act(a, "move", live.public(row, a)["battle"]["me"]["moves"][0]["key"])
    chk("턴이 넘어가도 '열렸다' 는 또 안 간다", len(pushed(a, "match")) == 1)
    row = finish(row, b)
    chk("기권하면 끝", row["state"] == "done" and row["result"] == "a", (row["state"], row["result"]))

    print("=== 대기열 정리 ===")
    champion.seek(c, True)
    set_online(c, False)
    row = champion.seek(a, True)
    chk("꺼진 사람과는 안 붙는다 (그 사람은 걷힌다)", row is None
        and [w["id"] for w in champion.state(b)["waiting"]] == [a], champion.state(b)["waiting"])
    set_online(c, True)
    champion.seek(a, False)
    champion.reset()

    # 동시에 눌러도 판은 하나
    d1, d2 = make_member("동시하나"), make_member("동시둘")
    gate = threading.Barrier(2)
    out = []

    def press(uid):
        gate.wait()
        try:
            out.append(champion.seek(uid, True))
        except Exception as e:                              # noqa: BLE001
            out.append(e)
    ts = [threading.Thread(target=press, args=(u,)) for u in (d1, d2)]
    [x.start() for x in ts]
    [x.join() for x in ts]
    opened = [x for x in out if isinstance(x, dict) or hasattr(x, "keys")]
    chk("둘이 동시에 눌러도 판은 하나 열린다", len(opened) == 1 and not champion.state(a)["waiting"], out)
    if opened:
        finish(live.my_match(d1), d1)

    print("=== 직접 도전 ===")
    champion.reset()
    PUSHED[:] = []
    for who, foe, word in ((a, a, "자기 자신"), (a, stranger, "참가자가 아닙니다"), (a, off, "접속")):
        try:
            champion.challenge(who, foe)
            chk("못 건다: %s" % word, False)
        except (ValueError, LookupError) as e:
            chk("못 건다: %s" % word, word in str(e), str(e))
    row = champion.challenge(a, c)
    chk("도전하면 초대가 생긴다 (상대가 받아야 시작)", row["state"] == "invited" and live.kind_of(row) == "champion",
        row["state"])
    chk("  상대에게 '도전이 왔다' 가 간다", pushed(c, "ask") and pushed(c, "ask")[0]["name"] == "가람", PUSHED)
    try:
        champion.challenge(b, c)
        chk("초대를 받은 사람에게 또 못 건다", False)
    except ValueError as e:
        chk("초대를 받은 사람에게 또 못 건다", "다른 배틀" in str(e), str(e))
    row = live.answer(c, row["id"], True)
    chk("받으면 판이 열린다", row["state"] == "fighting")
    chk("  두 사람에게 '열렸다'", pushed(a, "match") and pushed(c, "match"))
    row = finish(row, a)
    chk("  다솜 승", row["result"] == "b", row["result"])
    champion.seek(b, True)
    row = champion.challenge(c, b)
    chk("기다리던 사람에게 걸면 묻지 않고 바로 시작", row["state"] == "fighting" and row["a_id"] == b,
        (row["state"], row["a_id"]))
    chk("  대기열에서 빠진다", not champion.state(a)["waiting"])
    finish(row, b)
    row = champion.challenge(a, b)
    live.answer(b, row["id"], False)
    chk("거절한 판은 기록에 안 든다", all(r["id"] != row["id"] for r, _c in champion.finished()))

    print("=== 기록 · 순위 ===")
    st = champion.stats()
    chk("가람 2전 1승 1패 (나래에게 이기고 다솜에게 기권)", st[a] == {"played": 2, "wins": 1, "losses": 1, "draws": 0},
        st.get(a))
    chk("나래 2전 0승 2패", st[b] == {"played": 2, "wins": 0, "losses": 2, "draws": 0}, st.get(b))
    chk("다솜 2전 2승 0패", st[c] == {"played": 2, "wins": 2, "losses": 0, "draws": 0}, st.get(c))
    table = champion.ranking()
    names = [r["name"] for r in table]
    chk("이긴 횟수 순, 같으면 진 횟수가 적은 쪽 (다솜 2승 > 동시둘 1승0패 > 가람 1승1패)",
        names[:3] == ["다솜", "동시둘", "가람"], names)
    chk("  0전도 목록에 나온다", "꺼둠" in names and "약한팀" in names, names)
    zero = [r for r in table if r["played"] == 0]
    chk("  승패가 같으면 같은 등수", len(set(r["rank"] for r in zero)) == 1, [(r["name"], r["rank"]) for r in zero])
    chk("  나래는 0승 2패라 0전보다 아래", table[-1]["name"] == "나래", names)
    chk("돈은 안 나간다", db.q1("SELECT money FROM users WHERE id=?", (c,))["money"] == 1000)

    # 같은 두 사람은 하루 3판까지
    for i in range(4):
        row = champion.challenge(a, b)
        live.answer(b, row["id"], True)
        finish(live.get(row["id"]), b)
    st = champion.stats()
    chk("같은 두 사람의 판은 하루 3판까지만 센다 (가람-나래 오늘 다섯 판 -> 두 판 더)",
        st[a]["played"] == 4 and st[a]["wins"] == 3, st.get(a))
    rec = champion.recent(a)
    chk("최근 판: 새 것부터, 넘친 판은 counted=False", rec[0]["counted"] is False and rec[0]["outcome"] == "win",
        rec[:2])
    chk("  상대 이름 · 결과", rec[0]["foeName"] == "나래")
    tomorrow = (datetime.datetime.now(UTC) + datetime.timedelta(days=1)).replace(microsecond=0).isoformat()
    db.run("UPDATE live_match SET created_at=? WHERE id=?", (tomorrow, rec[0]["id"]))
    chk("  다음 날 판은 다시 센다", champion.stats()[a]["played"] == 5, champion.stats()[a])

    # 무승부 · 접힌 판
    row = champion.challenge(a, c)
    live.answer(c, row["id"], True)
    db.run("UPDATE live_match SET state='done', result='draw', reason='turns' WHERE id=?", (row["id"],))
    chk("무승부는 '무'", champion.stats()[c]["draws"] == 1, champion.stats()[c])
    row = champion.challenge(a, c)
    live.answer(c, row["id"], True)
    db.run("UPDATE live_match SET state='done', result='expired' WHERE id=?", (row["id"],))
    chk("아무도 안 돌아와 접힌 판은 안 센다", champion.stats()[c]["played"] == 3, champion.stats()[c])

    print("=== 관전 (참가자만, 길드전처럼) ===")
    PUSHED[:] = []
    row = champion.challenge(a, c)
    live.answer(c, row["id"], True)
    mid = row["id"]
    fs = pushed(b, "fight")
    chk("판이 열리면 접속 중인 다른 참가자에게 'fight' (가람 vs 다솜)",
        fs and fs[0]["id"] == mid and (fs[0]["a"], fs[0]["b"]) == ("가람", "다솜"), PUSHED)
    chk("  싸우는 두 사람 · 꺼진 참가자 · 참가자가 아닌 사람에게는 안 간다",
        not pushed(a, "fight") and not pushed(c, "fight") and not pushed(off) and not pushed(stranger), PUSHED)
    f = champion.fight(mid, b)
    chk("참가자는 판을 본다", f and f["a"]["name"] == "가람" and f["b"]["name"] == "다솜" and f["kind"] == "champion", f)
    chk("  기술 목록은 안 실린다", "moves" not in json.dumps(f), f)
    for what, fn in (("판 모습", lambda: champion.fight(mid, stranger)), ("관전", lambda: champion.watch(stranger, mid))):
        try:
            fn()
            chk("참가자가 아니면 %s 막힘" % what, False)
        except PermissionError as e:
            chk("참가자가 아니면 %s 막힘" % what, "참가자만" in str(e), str(e))
    try:
        champion.watch(a, mid)
        chk("내 판은 관전하지 않는다", False)
    except ValueError:
        chk("내 판은 관전하지 않는다", True)
    PUSHED[:] = []
    out = champion.watch(b, mid)
    chk("관전을 시작하면 1명", out == {"id": mid, "n": 1}, out)
    chk("  싸우는 두 사람에게 '관전 1명'", [p["n"] for p in pushed(a, "watchers")] == [1]
        and [p["n"] for p in pushed(c, "watchers")] == [1], PUSHED)
    chk("  배틀 창이 받는 판(live.public)에도 '관전 1명'", live.public(live.get(mid), a).get("watchers") == 1)
    chk("  독도 창 목록에도", [x["watchers"] for x in champion.fights() if x["id"] == mid] == [1])
    PUSHED[:] = []
    champion.watch(b, mid)
    chk("'아직 본다' 는 수가 그대로라 다시 안 민다", not pushed(a, "watchers"))
    live.act(a, "move", live.public(live.get(mid), a)["battle"]["me"]["moves"][0]["key"])
    live.act(c, "move", live.public(live.get(mid), c)["battle"]["me"]["moves"][0]["key"])
    ts = pushed(b, "turn")
    chk("턴이 넘어가면 보는 사람에게 새 모습 'turn'", ts and ts[-1]["fight"]["id"] == mid
        and ts[-1]["fight"]["turn"] >= 1 and ts[-1]["fight"]["watchers"] == 1, [t["fight"].get("turn") for t in ts])
    chk("  안 보는 사람에게는 안 간다", not pushed(stranger, "turn") and not pushed(a, "turn"))
    n = len(pushed(b, "turn"))
    champion._feed(live.get(mid))
    chk("  같은 장면은 두 번 안 민다", len(pushed(b, "turn")) == n)
    finish(live.get(mid), a)
    ts = pushed(b, "turn")
    chk("끝나면 마지막 모습(over)을 민다", ts and ts[-1]["fight"]["over"] is True, ts[-1:] if ts else ts)
    chk("  구경꾼을 버린다", champion.watchers.count(champion.watch_key(mid)) == 0)
    try:
        champion.watch(b, mid)
        chk("끝난 판은 관전 못 한다", False)
    except LookupError:
        chk("끝난 판은 관전 못 한다", True)
    chk("  그만 보기는 끝난 판에도 조용히", champion.watch(b, mid, on=False) == {"id": mid, "n": 0})
    # 친구 실시간 배틀은 구경 길로 못 본다
    db.run("INSERT INTO friend (a_id, b_id, state, asked_by, created_at, decided_at)"
           " VALUES (?,?,'accepted',?,?,?)", (min(a, b), max(a, b), a, live._iso(), live._iso()))
    lrow = live.accept(b, live.invite(a, b)["id"])
    chk("친구 실시간 배틀은 이 길로 안 보인다", champion.fight(lrow["id"]) is None)
    finish(lrow, a)
    chk("  친구 판은 리그 기록에 안 든다", all(r["id"] != lrow["id"] for r, _c in champion.finished()))

    # 같은 길드 두 사람의 리그 판은 친선전 카드로 안 나간다
    now = live._iso()
    gid = db.run("INSERT INTO guild (name, master_id, created_at) VALUES ('독도길드',?,?)", (a, now)).lastrowid
    for u in (a, c):
        db.run("INSERT INTO guild_member (user_id, guild_id, role, joined_at) VALUES (?,?,'member',?)", (u, gid, now))
    row = champion.challenge(a, c)
    row = live.answer(c, row["id"], True)
    chk("길드원끼리의 리그 판은 친선전으로 안 잡힌다", all(row["id"] not in fs for fs in friendly._fights.values()),
        friendly._fights)
    finish(row, c)

    print("=== 화면에 주는 것 ===")
    from app import champion as CH
    out = CH.post_seek(CH.SeekIn(on=True), ctx(a))
    chk("POST /seek 이 모습을 돌려준다", out["seeking"] is True and out["match"] is None, out.get("seeking"))
    out = CH.post_seek(CH.SeekIn(on=True), ctx(c))
    chk("  짝이 나면 match 에 판", out["match"] and out["match"]["kind"] == "champion" and out["seeking"] is False,
        out.get("match"))
    finish(live.my_match(a), a)
    st = CH.get_state(ctx(a))
    for k in ("open", "opens", "total", "cleared", "member", "members", "why", "seeking", "waitLeft", "waiting",
              "online", "fights", "ranking", "me", "recent", "pairMax"):
        chk("  state 에 %s" % k, k in st)
    chk("  내 줄에 등수 · 전적", st["me"]["rank"] >= 1 and st["me"]["played"] >= 1, st["me"])
    chk("  접속 중인 참가자에 나는 없다", all(o["id"] != a for o in st["online"]))
    chk("  꺼진 참가자는 접속 중이 아니다", all(o["id"] != off for o in st["online"]))
    st = CH.get_state(ctx(stranger))
    chk("참가자가 아니어도 순위는 본다", st["member"] is False and st["ranking"] and st["recent"] == [])
    chk("  까닭에 관장 몇 곳", "관장" in (st["why"] or ""), st["why"])
    chk("관장 지도에 얹는 것", CH.brief(a) == {"member": True, "open": True, "opens": CH.open_text()}
        and CH.brief(stranger)["member"] is False)
    try:
        CH.get_fight(999999, ctx(a))
        chk("없는 판 구경은 404", False)
    except Exception as e:                                  # noqa: BLE001
        chk("없는 판 구경은 404", getattr(e, "status_code", None) == 404, e)
    try:
        CH.get_fight(999999, ctx(stranger))
        chk("참가자가 아니면 구경은 403", False)
    except Exception as e:                                  # noqa: BLE001
        chk("참가자가 아니면 구경은 403", getattr(e, "status_code", None) == 403, e)
    try:
        CH.post_watch(CH.WatchIn(id=999999, on=True), ctx(a))
        chk("없는 판 관전은 404", False)
    except Exception as e:                                  # noqa: BLE001
        chk("없는 판 관전은 404", getattr(e, "status_code", None) == 404, e)
    try:
        CH.post_challenge(stranger, ctx(a))
        chk("참가자가 아닌 사람 도전은 409", False)
    except Exception as e:                                  # noqa: BLE001
        chk("참가자가 아닌 사람 도전은 409", getattr(e, "status_code", None) == 409, e)

    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
