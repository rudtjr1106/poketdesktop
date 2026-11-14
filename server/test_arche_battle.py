# -*- coding: utf-8 -*-
"""아르케의 여섯 봉인 (2.4.0) 전설 배틀 · 볼 던지기. 서버를 띄우지 않는다.

    python server/test_arche_battle.py

계획 Task 3: 관장 판(gym_battle + TrainerBattle)을 다시 쓰고 이 판에만 볼(kind=ball)을 더한다.
의식 전 · 잡은 자리 · 앞 자리 · 이벤트 끝 → 막기 · 마스터볼은 늘 잡힘 · 볼 없음 409 · 놓치면 상대만 한 턴 ·
잡으면 판 끝 · 같은 자리 다시 409 · 아르케 판이 열려 있으면 관장 시작은 '아르케의 전설' 409 · 다시 도전은 새 체력.
**비공개 자료는 지어낸 값으로 임시로 만든다.**
"""
import datetime
import io
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-arche-b-")
ARCHE_DIR = os.path.join(TMP, "arche")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_ARCHE_DIR"] = ARCHE_DIR
os.environ["POKET_ARCHE_START"] = "2026-11-15"     # 검사는 날짜를 박아 둔다 (기본 날이 바뀌어도 그대로)

from fastapi import HTTPException                            # noqa: E402

from common import arche as A                                # noqa: E402
from common import pokelogic as P                            # noqa: E402
from common import trainer_battle as TB                      # noqa: E402
from app import arche as AR                                  # noqa: E402
from app import battle_routes, db, deps, gym, gym_routes, items   # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc
OPEN1 = A.window(1)[0]
DURING = OPEN1 + datetime.timedelta(hours=3)

SECRETS = {"salt": "시험소금-배틀-열여섯-글자보다-길게", "npc": "",
           "chapters": {"1": {"keys": {"k": {"answers": ["시험"]}}, "ritual": {"key": "k"},
                              "marks": [[1], [2], [3]], "caption": "지어낸 사진 글"}}}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def refused(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except HTTPException as e:
        return e.status_code, str(e.detail)
    return None


_n = [0]


def mkuser(balls=10):
    _n[0] += 1
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,?,0,'2026-10-01T00:00:00+00:00','','')",
        ("전설%d" % _n[0], b"x", b"x", balls))
    return cur.lastrowid


def ctx(uid):
    return {"user": dict(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


def mkmon(uid, species, level, seed, slot):
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(seed), force_shiny=False)
    pid = db.insert_mon(uid, m, "")
    db.run("UPDATE pokemon SET on_desktop=1, slot=? WHERE id=?", (slot, pid))
    return pid


def setup(ritual=True):
    u = mkuser()
    mkmon(u, "GARCHOMP", 60, 1, 0)
    mkmon(u, "ALAKAZAM", 55, 2, 1)
    if ritual:
        db.run("INSERT INTO arche_progress (user_id, chapter, ritual_at, first) VALUES (?,1,?,0)",
               (u, OPEN1.isoformat()))
    return u


def act(uid, bid, **kw):
    return gym_routes.act(bid, gym_routes.ActIn(**kw), ctx=ctx(uid))


def foe_mon(bid):
    return json.loads(db.q1("SELECT data FROM gym_battle WHERE id=?", (bid,))["data"])["foe"][0]


def t_막기():
    print("[막기]")
    u = setup(ritual=False)
    got = refused(AR.start_battle, u, 1, 0, now=DURING)
    chk("의식 전 → 409", got and got[0] == 409 and "봉인" in got[1], got)
    u = setup()
    chk("없는 자리 → 400", (refused(AR.start_battle, u, 1, 3, now=DURING) or (0,))[0] == 400)
    chk("없는 장 → 400", (refused(AR.start_battle, u, 7, 0, now=DURING) or (0,))[0] == 400)
    got = refused(AR.start_battle, u, 1, 1, now=DURING)
    chk("앞 자리를 안 잡았으면 → 409", got and got[0] == 409 and "앞 자리" in got[1], got)
    got = refused(AR.start_battle, u, 1, 0, now=A.event_window()[1])
    chk("이벤트가 끝나면 → 409", got and got[0] == 409, got)
    v = setup()
    db.run("UPDATE pokemon SET on_desktop=0 WHERE user_id=?", (v,))
    chk("파티가 없으면 → 409", (refused(AR.start_battle, v, 1, 0, now=DURING) or (0,))[0] == 409)


def t_판():
    print("[판 열기 · 이어 하기 · 다른 판 막기]")
    u = setup()
    out = AR.start_battle(u, 1, 0, now=DURING)
    sp = AR.legend_species(u, 1, 0)
    num = deps.dex().get(sp)["num"]
    chk("region · 장소 · 전설 번호 (동굴 후보)", out["region"] == "arche:1:0" and out["place"] == "cave"
        and out["legend"] == num and num in A.POOLS["cave"], (out["region"], out.get("legend")))
    chk("전설 = 사람별 뽑기 (소금 섞은 legends_for)", num == A.legends_for(u, 1, SECRETS["salt"])[0])
    foe = out["battle"]["foe"]["team"][0]
    chk("레벨 = 바탕화면 파티 최고 (60)", foe["level"] == 60, foe["level"])
    chk("마주친 포켓몬 (wild) · 메가 없음", out["battle"]["trainer"].get("wild") is True)
    opts = out.get("ballOptions") or []
    chk("볼 목록이 같이 온다 (야생 메뉴와 같은 꼴)", isinstance(opts, list) and opts
        and all("id" in o and "count" in o for o in opts), opts[:2])
    mon = foe_mon(out["id"])["mon"]
    chk("개체값 31 은 셋 이상 (나머지 무작위) · 노력치 0 · 도구 없음",
        sum(1 for v in mon["ivs"].values() if v == 31) >= 3 and not any(mon["evs"].values()) and not mon.get("held"),
        mon["ivs"])
    again = AR.legend_mon(u, 1, 0, sp, 60)
    chk("개체값 · 성격 · 특성 · 이로치는 사람 · 자리로 정해진다 (다시 열어도 같다)",
        (again["ivs"], again["nature"], again["ability"], again["shiny"]) ==
        (mon["ivs"], mon["nature"], mon["ability"], mon["shiny"]))
    chk("arche_mon met", db.q1("SELECT state FROM arche_mon WHERE user_id=? AND slot=0", (u,))["state"] == "met")
    st = AR.state(u, now=DURING)
    chk("state 자리 0: ready + 만난 전설 번호", st["chapters"][0]["encounters"][0] == {"slot": 0, "state": "ready", "num": num},
        st["chapters"][0]["encounters"][0])
    re_ = AR.start_battle(u, 1, 0, now=DURING)
    chk("같은 자리를 다시 열면 이어 준다 (resumed)", re_["id"] == out["id"] and re_.get("resumed"), re_.get("resumed"))
    chk("/api/gym/battle 도 아르케 판을 이어 준다", gym_routes.current(ctx=ctx(u))["region"] == "arche:1:0")
    region = sorted(gym.gyms()["_by_region"])[0]
    got = refused(gym_routes.start, region, ctx=ctx(u))
    chk("아르케 판이 열려 있으면 관장 시작 → 409 '아르케의 전설'", got and got[0] == 409 and "아르케의 전설" in got[1], got)
    # (잡힌 자리에 남은 판은 접힌다 - t_리뷰. 여기서는 아직 안 잡은 자리의 판이 열려 있을 때 다른 장의 자리를 연다)
    db.run("INSERT INTO arche_progress (user_id, chapter, ritual_at, first) VALUES (?,2,?,0)", (u, DURING.isoformat()))
    got = refused(AR.start_battle, u, 2, 0, now=DURING)
    chk("다른 자리를 열려 해도 → 409 '아르케의 전설'", got and got[0] == 409 and "아르케의 전설" in got[1], got)
    db.run("DELETE FROM arche_progress WHERE user_id=? AND chapter=2", (u,))
    # 관장 판에는 볼을 못 던진다
    v = setup()
    g = gym_routes.start(region, ctx=ctx(v))
    got = refused(act, v, g["id"], kind="ball", ball="MASTERBALL")
    chk("관장 판에 볼 → 409", got and got[0] == 409, got)
    got = refused(AR.start_battle, v, 1, 0, now=DURING)
    chk("관장 판이 열려 있으면 아르케 시작 → 409 (관장 이름)", got and got[0] == 409 and "아르케" not in got[1], got)
    return u, out["id"]


def t_볼(u, bid):
    print("[볼 · 놓침 · 잡음]")
    db.run("UPDATE users SET balls=0 WHERE id=?", (u,))
    got = refused(act, u, bid, kind="ball", ball="POKEBALL")
    chk("볼이 없으면 → 409", got and got[0] == 409 and "없습니다" in got[1], got)
    db.run("UPDATE users SET balls=5 WHERE id=?", (u,))
    before = db.q1("SELECT turn, rev FROM gym_battle WHERE id=?", (bid,))
    foe_hp = foe_mon(bid)["hp"]
    old = AR.P.catch_attempt
    try:
        AR.P.catch_attempt = lambda *a, **k: (False, 2)
        out = act(u, bid, kind="ball", ball="POKEBALL")
    finally:
        AR.P.catch_attempt = old
    ev = out["events"]
    chk("놓침: caught False · shakes · 문구 · 남은 볼", out["caught"] is False and out["shakes"] == 2
        and out["message"] and out["balls"] == 4 and out["ball"] == "POKEBALL", out.get("message"))
    chk("놓침: 첫 사건은 볼, 그다음 전설만 기술을 쓴다", ev[0]["t"] == "ball" and ev[0]["caught"] is False
        and [e.get("who") for e in ev if e.get("t") == "move"] == ["foe"], [e.get("t") for e in ev])
    after = db.q1("SELECT turn, rev, state FROM gym_battle WHERE id=?", (bid,))
    chk("놓침: 턴 하나 · rev 하나 · 판은 이어진다", after["turn"] == before["turn"] + 1 and after["rev"] == before["rev"] + 1
        and after["state"] == "active" and foe_mon(bid)["hp"] == foe_hp, dict(after))
    chk("놓침 응답도 관장 판 꼴 (id · region · rev · battle · events)",
        all(k in out for k in ("id", "region", "rev", "battle", "events")))
    chk("놓침 응답에 새 볼 목록 (몬스터볼 4개)", any(o.get("id") == "POKEBALL" and o.get("count") == 4
                                                for o in out.get("ballOptions") or []), out.get("ballOptions"))
    # 기권 → 다시 도전은 새 체력
    act(u, bid, kind="move", move=out["battle"]["me"]["team"][0]["moves"][0]["key"])
    out = act(u, bid, kind="forfeit")
    chk("기권: 그 판만 끝 · 다시 도전할 수 있다는 말", out["battle"]["over"] and out["reward"]["arche"]
        and any("다시 도전" in x for x in out["reward"]["lines"]), out.get("reward"))
    new = AR.start_battle(u, 1, 0, now=DURING)
    chk("다시 도전: 새 판 · 전설은 새 체력", new["id"] != bid and not new.get("resumed")
        and foe_mon(new["id"])["hp"] == new["battle"]["foe"]["team"][0]["maxhp"], new["id"])
    bid = new["id"]
    items.bag_add(u, "MASTERBALL", 1)
    out = act(u, bid, kind="ball", ball="MASTERBALL")
    sp = AR.legend_species(u, 1, 0)
    chk("마스터볼: 잡힌다", out["caught"] is True and out["shakes"] == 4 and out["pokemon"]["species"] == sp,
        out.get("message"))
    chk("잡으면 파티(자리 있음) · 다음 자리 안내", out["where"] == "party" and out["next"] == {"chapter": 1, "slot": 1},
        (out.get("where"), out.get("next")))
    chk("마스터볼은 가방에서 빠졌다", items.bag_count(u, "MASTERBALL") == 0)
    row = db.q1("SELECT state, result FROM gym_battle WHERE id=?", (bid,))
    chk("판은 done/caught", (row["state"], row["result"]) == ("done", "caught"), dict(row))
    m = db.q1("SELECT * FROM arche_mon WHERE user_id=? AND slot=0", (u,))
    chk("자리 0 caught · 포켓몬 번호", m["state"] == "caught" and m["pokemon_id"] == out["pokemon"]["id"], dict(m))
    chk("포켓몬은 내 것 · 바탕화면", db.q1("SELECT on_desktop FROM pokemon WHERE id=? AND user_id=?",
                                       (m["pokemon_id"], u))["on_desktop"] == 1)
    chk("도감에 잡은 것으로", items.has_caught(u, sp))
    got = refused(AR.start_battle, u, 1, 0, now=DURING)
    chk("잡은 자리는 다시 못 연다 → 409", got and got[0] == 409 and "이미 잡" in got[1], got)
    got = refused(act, u, bid, kind="ball", ball="POKEBALL")
    chk("끝난 판에 볼 → 409", got and got[0] == 409, got)
    enc = AR.state(u, now=DURING)["chapters"][0]["encounters"]
    chk("state: 자리 0 caught · 자리 1 ready · 자리 2 locked", [e["state"] for e in enc] == ["caught", "ready", "locked"]
        and enc[0]["num"] == deps.dex().get(sp)["num"], enc)
    chk("state: 잡은 자리에 한국어 이름", enc[0].get("name") == deps.dex().get(sp)["kr"], enc[0])
    ch1 = AR.state(u, now=DURING)["chapters"][0]
    chk("state: 일지 사진의 판 글자 · 사진 글", ch1.get("marks") == [[1], [2], [3]] and ch1.get("caption") == "지어낸 사진 글",
        (ch1.get("marks"), ch1.get("caption")))
    nxt = AR.start_battle(u, 1, 1, now=DURING)
    chk("더 안쪽 자리 (1) 를 연다 · 다른 전설", nxt["region"] == "arche:1:1"
        and nxt["legend"] == A.legends_for(u, 1, SECRETS["salt"])[1], nxt.get("legend"))
    act(u, nxt["id"], kind="forfeit")


def t_닫힌_장():
    print("[닫힌 장 · 이벤트 끝까지]")
    u = setup()
    later = A.window(4)[0]
    out = AR.start_battle(u, 1, 0, now=later)
    chk("1장이 닫힌 뒤(4장 때)에도 의식을 마친 장의 전설에게 간다", out["region"] == "arche:1:0")
    act(u, out["id"], kind="forfeit")


def _poke(bid, fn):
    """저장된 판을 불러 fn(tb) 로 손대고 다시 적는다 (숨기 · 모으기 같은 상태를 만들려고)."""
    row = db.q1("SELECT data FROM gym_battle WHERE id=?", (bid,))
    tb = TB.TrainerBattle.load(deps.dex(), json.loads(row["data"]))
    fn(tb)
    db.run("UPDATE gym_battle SET data=? WHERE id=?", (json.dumps(tb.dump()), bid))


def t_리뷰():
    print("[리뷰: 숨은 채 볼 · 숨은 전설 · 잡힌 자리의 남은 판 · 경험치 없음]")
    u = setup()
    out = AR.start_battle(u, 1, 0, now=DURING)
    bid = out["id"]
    items.bag_add(u, "MASTERBALL", 2)
    _poke(bid, lambda tb: tb.me.cond.update(invuln="dig", charge2={"move": "DIG"}))
    got = refused(act, u, bid, kind="ball", ball="MASTERBALL")
    chk("구멍파기로 숨은 채로는 볼을 못 던진다 → 409", got and got[0] == 409 and "볼을 던질 수 없다" in got[1], got)
    chk("…볼은 그대로 (안 빠졌다)", items.bag_count(u, "MASTERBALL") == 2)
    _poke(bid, lambda tb: (tb.me.cond.pop("invuln", None), tb.me.cond.pop("charge2", None),
                           tb.foe.cond.update(invuln="fly")))
    r = act(u, bid, kind="ball", ball="MASTERBALL")
    chk("하늘에 숨은 전설에게는 마스터볼도 빗나간다", r["caught"] is False and r["shakes"] == 0 and "빗나갔다" in r["message"],
        r.get("message"))
    # 잡힌 자리에 판이 남은 경우 (창이 두 번 열렸던 판): 다음 자리를 열면 접힌다
    db.run("UPDATE arche_mon SET state='caught' WHERE user_id=? AND chapter=1 AND slot=0", (u,))
    nxt = AR.start_battle(u, 1, 1, now=DURING)
    chk("잡힌 자리의 남은 판은 접고 다음 자리를 연다", nxt["region"] == "arche:1:1"
        and db.q1("SELECT state FROM gym_battle WHERE id=?", (bid,))["state"] == "done", nxt.get("region"))
    act(u, nxt["id"], kind="forfeit")
    region = sorted(gym.gyms()["_by_region"])[0]
    g = gym_routes.start(region, ctx=ctx(u))
    chk("그 뒤 관장 도전이 막히지 않는다", g.get("region") == region, g.get("region"))
    act(u, g["id"], kind="forfeit")
    # 경험치 없음: 전설이 쓰러지는 판을 만든다 (체력 1)
    v = setup()
    o = AR.start_battle(v, 1, 0, now=DURING)
    _poke(o["id"], lambda tb: setattr(tb.foe, "hp", 1))
    called = []
    old = battle_routes.award
    try:
        battle_routes.award = lambda *a, **k: called.append(a) or [{"x": 1}]
        mv = o["battle"]["me"]["team"][0]["moves"][0]["key"]
        for _ in range(4):
            r = act(v, o["id"], kind="move", move=mv)
            if r["battle"]["over"]:
                break
    finally:
        battle_routes.award = old
    # 플레이테스트: 바탕화면에 약한 포켓몬만 두고 약한 전설을 부르는 길 막기 - 레벨은 계정 전체의 최고 레벨
    w = setup()
    pid = mkmon(w, "MAGIKARP", 85, 9, 5)
    db.run("UPDATE pokemon SET on_desktop=0, slot=NULL WHERE id=?", (pid,))
    o2 = AR.start_battle(w, 1, 0, now=DURING)
    chk("전설 레벨 = 내 포켓몬 전체에서 가장 높은 레벨 (박스 포함)", o2["battle"]["foe"]["team"][0]["level"] == 85,
        o2["battle"]["foe"]["team"][0]["level"])
    act(w, o2["id"], kind="forfeit")
    chk("전설을 쓰러뜨려도 경험치는 없다 (끝까지 다시 도전 - 경험치 밭 막기)", r["battle"]["over"] and not called
        and not r.get("exp"), (r["battle"].get("result"), len(called)))


def main():
    db.init()
    os.makedirs(ARCHE_DIR, exist_ok=True)
    with io.open(os.path.join(ARCHE_DIR, "secrets.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(SECRETS, ensure_ascii=False))
    t_막기()
    u, bid = t_판()
    t_볼(u, bid)
    t_닫힌_장()
    t_리뷰()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
