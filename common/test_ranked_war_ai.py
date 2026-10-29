# -*- coding: utf-8 -*-
"""시즌 5 랭크 - 양쪽 다 길드전 방어 AI 로 싸우는 파티전 (party_battle war_ai=True) 검사. 서버 없이 돈다.

    python common/test_ranked_war_ai.py

본다:

1. **끄면 예전 판 그대로.** war_ai 를 안 주거나 False 면 시즌 4 의 로그와 한 글자도 다르지 않다 - 아래 요약값은
   이 기능을 넣기 전의 코드(ui/revamp 8b91f13)로 같은 24판을 돌려 얻은 것이다. 이게 바뀌면 시즌 4 판정이 바뀐 것이다.
2. **켜면 로그 꼴이 같다.** 앱의 투기장 · 다시 보기가 읽는 이벤트만 나오고(teams · round · ko · match 와 Battle 의
   이벤트), "over" 가 안 새고, 스스로 바꾸면 'msg(물러났다) -> round(살아 있는 선수)' 로 나간다. 뒤집기(flip)가 맞는다.
3. **15% 무작위가 없다.** 진짜 판의 Battle 은 기술을 스스로 고르지 않는다 (길드전 AI 가 고른 것을 쓴다).
4. **시간 상한 안에 끝난다.** 판 상한을 줄이면 그만큼만 셈하고 나머지는 셈 없는 수로 둔다. 버티기만 하는 팀끼리도 끝난다.
5. **상한에 안 걸리면 같은 시드 = 같은 판.**
6. **거울 판이 진영을 바로 옮긴다.** a 쪽을 AI 자리에 앉히면 팀 · 자리 · 깔기가 통째로 뒤집힌다.
"""
import hashlib
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import battle as B               # noqa: E402
from common import party_battle as PB        # noqa: E402
from common import pokelogic as P            # noqa: E402
from common import trainer_battle as TB      # noqa: E402

OK = FAIL = 0

# 넣기 전 코드(8b91f13)로 아래 old_log_digest 의 24판을 돌린 요약값 (2026-10-29)
OLD_DIGEST = "8e5824d926a966f1e73fc4b19b0b243bc93797094485dd8aa762b55de2dedf84"
# 그때의 자료(도감 · 관장 · 도구) 요약값. 위 값은 판정 규칙뿐 아니라 자료에도 묶여 있다 - 학습표 · 도구를 고치기만 해도
# 어긋난다. 자료가 바뀌었으면 이 비교는 건너뛴다 (그때 덮어쓰면 검사의 뜻이 사라진다). 다시 박으려면: 8b91f13 의
# common/party_battle.py 로 바꿔 끼운 작업 폴더에서 old_log_digest 를 돌려 두 값을 같이 새로 적는다.
OLD_DATA = "84792eca680d43d88712abf4b4bbc352bdc8f4f436457b9124e143ad03106342"


def data_digest():
    h = hashlib.sha256()
    for name in ("pokedex.json", "gyms.json", "items.json"):
        with open(os.path.join(ROOT, "server", "data", name), "rb") as f:
            h.update(f.read())
    return h.hexdigest()
# 켠 판의 이벤트 종류는 **끈 판(예전 판)에 나오는 것**만이어야 한다 - 투기장(client/poketdesktop/arena.py) · 다시 보기가
# 이미 그리는 것들이다. 아래 예전 판 24판에서 모으고, 그 24판에 우연히 안 나온 Battle 의 것 몇을 더한다.
EXTRA_TYPES = {"mega", "zpower", "weather", "flee"}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def load():
    dex = P.Pokedex.load(os.path.join(ROOT, "server", "data", "pokedex.json"))
    with open(os.path.join(ROOT, "server", "data", "gyms.json"), encoding="utf-8") as f:
        gyms = json.load(f)
    teams = [[TB.trainer_mon(dict(e, level=50, iv=31)) for e in t["team"]]
             for t in gyms["trainers"] if t.get("role") in ("챔피언", "사천왕", "프런티어브레인")]
    return dex, teams


def mon(dex, species, level, moves, held=None, ability=None):
    m = P.make_pokemon(dex.get(species), level, random.Random(1), shiny_rate=10 ** 9,
                       ivs=dict((s, 31) for s in P.STATS))
    m["nature"] = "HARDY"
    m["moves"] = list(moves)
    m["held"] = held
    if ability:
        m["ability"] = ability
    return m


def old_log_digest(dex, teams, **kw):
    """관장 자료 팀 12판(키스톤 · Z링 섞어서) + 야생으로 뽑은 팀 12판의 로그 전체를 한 요약값으로. (요약값, 이벤트 종류)"""
    h = hashlib.sha256()
    types = set()
    for i in range(12):
        a, b = teams[i % len(teams)], teams[(i * 7 + 3) % len(teams)]
        out = PB.simulate(dex, a, b, seed=100 + i, keystone={"me": True, "foe": i % 2 == 0},
                          zring={"me": i % 3 == 0, "foe": True}, **kw)
        h.update(json.dumps(out, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        types.update(e["t"] for e in out["events"])
    rng = random.Random(5)
    for i in range(12):
        a = [dex.roll_wild(30, 50, rng) for _ in range(6)]
        b = [dex.roll_wild(30, 50, rng) for _ in range(6)]
        out = PB.simulate(dex, a, b, seed=200 + i, **kw)
        h.update(json.dumps(out, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        types.update(e["t"] for e in out["events"])
    return h.hexdigest(), types


class Budget(object):
    """판 상한 · 수 상한을 잠깐 바꾼다."""

    def __init__(self, match, turn):
        self.v = (match, turn)

    def __enter__(self):
        self.old = (PB.WAR_MATCH_BUDGET, PB.WAR_TURN_CAP)
        PB.WAR_MATCH_BUDGET, PB.WAR_TURN_CAP = self.v

    def __exit__(self, *_a):
        PB.WAR_MATCH_BUDGET, PB.WAR_TURN_CAP = self.old


def run(dex, a, b, seed, **kw):
    pb = PB.PartyBattle(dex, a, b, seed=seed, keystone={"me": True, "foe": True},
                        zring={"me": True, "foe": True}, war_ai=True, **kw)
    t0 = time.time()
    out = pb.run()
    return pb, out, time.time() - t0


EVENT_TYPES = set()


def shape_ok(ev, na, nb):
    """로그 꼴. 문제가 있으면 그 까닭(글), 없으면 None."""
    if not ev or ev[0].get("t") != "teams" or len(ev[0]["me"]) != na or len(ev[0]["foe"]) != nb:
        return "맨 앞이 teams 가 아니다"
    if ev[-1].get("t") != "match" or ev[-1].get("winner") not in ("me", "foe", "draw"):
        return "맨 끝이 match 가 아니다"
    for i, e in enumerate(ev):
        t = e.get("t")
        if t == "over":
            return "over 가 샜다 (%d)" % i
        if t not in EVENT_TYPES:
            return "모르는 이벤트 %r" % t
        for k in ("who", "side", "target"):
            if k in e and e[k] not in ("me", "foe", "both", None):
                return "진영 이름이 이상하다 %r" % e
        if t == "round":
            if not (0 <= e["mi"] < na and 0 <= e["fi"] < nb) or not e.get("me") or not e.get("foe"):
                return "round 의 자리가 이상하다 %r" % e
    return None


def main():
    dex, teams = load()

    print("=== 1. 끄면 예전 판 그대로 (시즌 4) ===")
    digest, types = old_log_digest(dex, teams)
    if data_digest() == OLD_DATA:
        chk("war_ai 를 안 주면 넣기 전 코드와 로그가 같다 (24판 요약값)", digest == OLD_DIGEST, digest)
    else:
        print("  건너뜀 넣기 전 코드와 견주기 - 자료(도감·관장·도구)가 그때와 달라 요약값이 원래 다르다")
    chk("war_ai=False 는 war_ai 를 안 준 것과 같다", old_log_digest(dex, teams, war_ai=False)[0] == digest)
    EVENT_TYPES.update(types | EXTRA_TYPES)
    # 위 24판이 '기술로 바뀌는 길'(_move_switch -> _bring_in, 이번에 나눈 곳)을 정말 지나는지
    seen_mid = 0
    rng = random.Random(5)
    for i in range(12):
        a = [dex.roll_wild(30, 50, rng) for _ in range(6)]
        b = [dex.roll_wild(30, 50, rng) for _ in range(6)]
        ev = PB.simulate(dex, a, b, seed=200 + i)["events"]
        seen_mid += sum(1 for j, e in enumerate(ev) if e.get("t") == "round" and j > 1
                        and ev[j - 1].get("t") != "ko")
    pb = PB.PartyBattle(dex, [mon(dex, "SCIZOR", 50, ["UTURN"]), mon(dex, "SNORLAX", 50, ["BODYSLAM"])],
                        [mon(dex, "BLISSEY", 50, ["POUND"])], seed=3)
    ev = pb.run()["events"]
    seen_mid += sum(1 for j, e in enumerate(ev) if e.get("t") == "round" and j > 1 and ev[j - 1].get("t") != "ko")
    chk("예전 판에서도 유턴으로 라운드 도중에 바뀐다 (나눈 _bring_in 을 지난다)", seen_mid > 0, seen_mid)

    print("\n=== 2~3. 켜면: 로그 꼴 · 스스로 교체 · 무작위 없음 ===")
    slips = []
    real = B.Battle.choose_for

    def spy(self, user, target, ai):
        # 진짜 판(_Planned)의 Battle 이 난수를 쥔 채 고르면 15% 무작위가 살아 있는 것이다
        if isinstance(self, PB._Planned) and self.rng is not PB._NoSlip:
            slips.append(ai)
        return real(self, user, target, ai)
    B.Battle.choose_for = spy
    bad, swaps, walls = [], 0, []
    try:
        for i in range(8):
            a, b = teams[i % len(teams)], teams[(i * 5 + 2) % len(teams)]
            pb, out, dt = run(dex, a, b, seed=300 + i)
            walls.append(dt)
            why = shape_ok(out["events"], len(a), len(b))
            if why:
                bad.append((i, why))
            ev = out["events"]
            for j, e in enumerate(ev):
                if e.get("t") == "msg" and (e.get("text") or "").endswith("물러났다!"):
                    nxt = ev[j + 1] if j + 1 < len(ev) else {}
                    side = e["who"]
                    if nxt.get("t") != "round" or not (nxt.get(side) or {}).get("hp"):
                        bad.append((i, "물러난 뒤 round 가 아니다 %r" % nxt))
                    swaps += 1
            back = PB.flip_log(PB.flip_log(ev))
            if back != ev:
                bad.append((i, "두 번 뒤집으면 제자리가 아니다"))
            if pb.war_stats["error"]:
                bad.append((i, "셈 오류 %r" % pb.war_stats))
    finally:
        B.Battle.choose_for = real
    chk("8판 다 로그 꼴이 맞다 (teams · round 자리 · match · over 없음 · 아는 이벤트만)", not bad, bad[:3])
    chk("라운드 도중에 스스로 바꾼다 (물러났다 -> round)", swaps > 0, swaps)
    chk("진짜 판의 Battle 은 기술을 스스로 고르지 않는다 (15% 무작위 없음)", not slips, slips[:5])
    print("     (이 맥: 판당 %.2f초 중앙값, 최대 %.2f초)" % (sorted(walls)[len(walls) // 2], max(walls)))

    print("\n=== 4. 시간 상한 · 끝나는가 ===")
    with Budget(0.3, 0.25):
        pb, out, dt = run(dex, teams[1], teams[9], seed=5)
    st = pb.war_stats
    chk("판 상한(0.3초)을 넘으면 남은 수는 셈 없이 둔다", st["plain"] > 0 and st["searched"] > 0, st)
    # 상한을 넘긴 뒤의 '셈 없는 수' 도 거울 판을 만드는 데 조금씩 든다 (한 수 1~2ms) - CI 러너가 느려도 넉넉하게
    chk("셈에 쓴 시간은 상한 + 한 수 남짓", pb.war_spent < 0.3 + 0.25 + 0.45, pb.war_spent)
    chk("그래도 판은 끝나고 로그 꼴이 맞다", shape_ok(out["events"], 6, 6) is None, shape_ok(out["events"], 6, 6))
    with Budget(0.0, 0.25):
        pb, out, dt = run(dex, teams[2], teams[7], seed=6)
    chk("상한 0 이면 전부 셈 없는 수 (관장 AI 의 수) - 그래도 끝난다",
        pb.war_stats["searched"] == 0 and out["events"][-1]["t"] == "match", pb.war_stats)
    # 버티기만 하는 팀끼리: 라운드 30턴 상한 x 16라운드 안에서 끝나야 한다 (무한 루프 없음)
    wall = [mon(dex, "BLISSEY", 50, ["SOFTBOILED", "PROTECT", "TOXIC", "SEISMICTOSS"], held="LEFTOVERS"),
            mon(dex, "TOXAPEX", 50, ["RECOVER", "PROTECT", "HAZE", "TOXIC"], held="BLACKSLUDGE")]
    wall2 = [mon(dex, "CHANSEY", 50, ["SOFTBOILED", "PROTECT", "SPLASH", "SEISMICTOSS"], held="EVIOLITE"),
             mon(dex, "SHUCKLE", 50, ["REST", "PROTECT", "SLEEPTALK", "TOXIC"], held="LEFTOVERS")]
    with Budget(0.5, 0.05):
        pb, out, dt = run(dex, wall, wall2, seed=9)
    chk("버티기 팀끼리도 끝난다 (턴 <= 라운드 상한 x 라운드 수)",
        out["events"][-1]["t"] == "match" and out["turns"] <= PB.MAX_ROUNDS * PB.ROUND_TURNS, out["turns"])
    chk("  로그 꼴도 맞다", shape_ok(out["events"], 2, 2) is None, shape_ok(out["events"], 2, 2))
    print("     (버티기 판: %d턴 %.2f초)" % (out["turns"], dt))

    # 스스로 바꿔 들어오다 스텔스록에 쓰러지면: 쓰러짐을 알리고, 남은 쪽의 턴 끝(먹다남은음식)은 **한 번만** 돈다
    zard = mon(dex, "CHARIZARD", 50, ["EMBER"])
    pb = PB.PartyBattle(dex, [mon(dex, "SNORLAX", 50, ["BODYSLAM"]), zard, mon(dex, "MEW", 50, ["POUND"])],
                        [mon(dex, "BLISSEY", 50, ["SPLASH"], held="LEFTOVERS")], seed=2, war_ai=True)
    bt = pb._round_battle()
    pb.a[1].hp = 1
    pb.b[0].hp = pb.b[0].maxhp // 2
    pb.field.side("me")["stealthrock"] = 1
    ev = pb._switch_turn(bt, {"me": (1, None), "foe": (None, "SPLASH")})
    if bt.over and pb._still_on(bt):                    # _one_round 가 하는 그대로
        bt.over = False
        bt._end_of_turn(ev)
        bt.over = True
    kinds = [e.get("t") for e in ev]
    chk("바꿔 들어오다 쓰러졌다: msg -> round -> faint", kinds[:2] == ["msg", "round"] and "faint" in kinds, kinds)
    chk("  남은 쪽의 먹다남은음식은 한 번만", sum(1 for e in ev if e.get("t") == "heal" and e.get("who") == "foe") == 1,
        [e for e in ev if e.get("t") == "heal"])

    print("\n=== 5. 상한에 안 걸리면 같은 시드 = 같은 판 ===")
    with Budget(10 ** 6, 10 ** 6):
        _pb, o1, _ = run(dex, teams[3], teams[11], seed=77)
        _pb, o2, _ = run(dex, teams[3], teams[11], seed=77)
        _pb, o3, _ = run(dex, teams[3], teams[11], seed=78)
    chk("같은 시드 두 번 = 같은 로그", o1["events"] == o2["events"])
    chk("시드가 다르면 (대개) 다른 판", o1["events"] != o3["events"])

    print("\n=== 6. 거울 판 ===")
    pb = PB.PartyBattle(dex, teams[0], teams[4], seed=1, war_ai=True)
    pb.ia, pb.ib = 2, 3
    pb.field.side("me")["stealthrock"] = 1
    pb.mega_done.add("me")
    pb._round_battle()
    m = pb._mirror("me")
    chk("a 를 AI 자리에: 팀 · 자리가 뒤집힌다",
        [f.name for f in m.foe_team] == [f.name for f in pb.a] and m.fi == 2 and m.mi == 3,
        (m.fi, m.mi))
    chk("  a 쪽에 깔린 스텔스록은 거울 판의 AI(foe) 쪽", m.bt.field.side("foe").get("stealthrock") == 1
        and not m.bt.field.side("me").get("stealthrock"))
    chk("  a 가 메가진화를 썼다 = 거울 판의 AI 가 썼다", m.mega_done == {"foe"}, m.mega_done)
    m2 = pb._mirror("foe")
    chk("b 를 AI 자리에: 그대로", [f.name for f in m2.foe_team] == [f.name for f in pb.b] and m2.fi == 3
        and m2.bt.field.side("me").get("stealthrock") == 1, m2.fi)
    chk("  거울 판은 길드전 방어 AI 다 (실수 0 · 늘 바꿀 줄 안다)", m.war and m.mistake() == 0 and m.smartness() == 1)
    before = json.dumps([TB.TrainerBattle._dump_fighter(f) for f in pb.a + pb.b], sort_keys=True)
    m.bt.foe.hp = 0
    m.foe_team[0].pp = {}
    after = json.dumps([TB.TrainerBattle._dump_fighter(f) for f in pb.a + pb.b], sort_keys=True)
    chk("  거울 판을 고쳐도 진짜 판은 그대로", before == after)

    print("\n======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
