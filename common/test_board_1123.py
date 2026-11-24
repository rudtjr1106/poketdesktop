# -*- coding: utf-8 -*-
"""11/23 문의 게시판 두 건 (엔진).

    python common/test_board_1123.py

#800 양양 - 랭크 배틀 마지막에 두 마리가 같이 나와 같이 쓰러졌다:
  체력 2 로 다시 나온 포켓몬이 스텔스록에 쓰러지면 그 라운드에 기술을 쓴 쪽이 없어 '쓰러졌다(faint)' 가 안 나왔다.
  화면은 그 줄을 봐야 링을 비운다 - 쓰러진 포켓몬이 다음 선수와 같이 서 있다가 같이 사라졌다.
  1. 라운드 시작에 바닥 피해로 쓰러지면 faint 가 ko 앞에 나온다 (한 번만)
  2. 여러 판을 돌려도 'ko(한쪽)' 앞에는 늘 그쪽의 faint 가 있다

#769 funji - 원시가이오가가 서 있는데 상대의 가뭄 · 모래날림이 날씨를 바꾸는 문구가 나온다:
  3. 강한 비 동안 가뭄 · 모래날림은 발동하지 않는다 (날씨 칸도 그대로)
  4. 쾌청 · 모래바람 같은 기술은 실패한다 · AI 는 그 기술을 안 고른다 (값 0)
  5. 엽록소 · 모래헤치기 같은 특성도 강한 비를 본다 (덮어쓴 날씨가 남아 있어도)
  6. 원시회귀가 나오면 그때까지의 날씨를 걷어 낸다 - 물러나면 맑음 (레이드는 그대로)
  7. 원시회귀가 없으면 예전과 같다 (가뭄 · 쾌청이 날씨를 바꾼다)
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from common import abilities as A           # noqa: E402
from common import party_battle as PB       # noqa: E402
from common import statusmoves as SM        # noqa: E402
from common import test_abilities2 as T     # noqa: E402

OK = FAIL = 0
DEX = T.DEX
mon, use, texts = T.mon, T.use, T.texts


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


# ---------------------------------------------------------------- #800
def t_hazard_faint():
    print("-- #800 나오자마자 스텔스록에 쓰러지면 faint")
    pb = PB.PartyBattle(DEX, [mon("CHARIZARD", 50, ["FLAMETHROWER"]), mon("BLASTOISE", 50, ["SURF"])],
                        [mon("SNORLAX", 50, ["TACKLE"])], seed=3)
    pb.field.side("me")["stealthrock"] = 1
    pb.a[0].hp = 2
    pb.entered = {"me": True, "foe": False}
    pb.round_no = 7
    pb.events = []
    side = pb._one_round()
    ts = [e.get("t") for e in pb.events]
    faints = [e for e in pb.events if e.get("t") == "faint"]
    chk("1. 라운드가 내 쪽 쓰러짐으로 끝난다", side == "me", side)
    chk("   스텔스록 chip 뒤에 내 faint 가 한 번", "chip" in ts and len(faints) == 1 and faints[0]["who"] == "me"
        and ts.index("chip") < ts.index("faint"), ts)
    chk("   기술은 안 나간다 (아무도 움직이지 않았다)", "move" not in ts, ts)
    chk("   faint 글", "리자몽" in (faints[0].get("text") if faints else ""), faints)

    # 2. 여러 판: 'ko(한쪽)' 앞 (그 라운드 안) 에는 그쪽 faint 가 있다 - 바닥을 까는 팀으로
    hazard = [mon("GARCHOMP", 50, ["STEALTHROCK", "SPIKES", "EARTHQUAKE"]),
              mon("SKARMORY", 50, ["SPIKES", "STEALTHROCK", "BRAVEBIRD"]),
              mon("FERROTHORN", 50, ["STEALTHROCK", "SPIKES", "POWERWHIP"])]
    weak = [mon("CHARIZARD", 50, ["FLAMETHROWER", "AIRSLASH"]), mon("VOLCARONA", 50, ["FIERYDANCE", "BUGBUZZ"]),
            mon("ARTICUNO", 50, ["ICEBEAM", "HURRICANE"]), mon("BUTTERFREE", 50, ["BUGBUZZ", "AIRSLASH"]),
            mon("GLALIE", 50, ["ICEBEAM", "CRUNCH"]), mon("DELIBIRD", 50, ["ICEPUNCH", "DRILLPECK"])]
    bad, silent_seen, games = [], 0, 0
    for seed in range(40):
        rng = random.Random(seed)
        a = [dict(m) for m in rng.sample(hazard, 3)]
        b = [dict(m) for m in rng.sample(weak, 6)]
        out = PB.PartyBattle(DEX, a, b, seed=seed, war_ai=True).run()   # (랭크 AI - 스스로 물러났다 다시 나온다)
        games += 1
        since = []
        for e in out["events"]:
            if e.get("t") == "round":
                since = []
            elif e.get("t") == "ko" and e.get("side") in ("me", "foe"):
                if not any(x.get("t") == "faint" and x.get("who") == e["side"] for x in since):
                    bad.append((seed, e))
                if any(x.get("t") == "chip" and x.get("who") == e["side"] and x.get("hp") == 0 for x in since):
                    silent_seen += 1
            else:
                since.append(e)
    chk("2. %d판: 한쪽 ko 앞에는 늘 그쪽 faint" % games, not bad, bad[:3])
    chk("   (바닥 피해로 쓰러진 일이 실제로 있었다 - 대개 턴 도중: %d번)" % silent_seen, silent_seen > 0, silent_seen)


# ---------------------------------------------------------------- #769
def t_primal_weather():
    print("-- #769 원시회귀 날씨")
    kyogre = lambda: mon("KYOGRE", 60, ["SURF"], held="BLUEORB")             # noqa: E731
    bt, me, foe = T.fight(kyogre(), mon("TORKOAL", 50, ["FLAMETHROWER", "SUNNYDAY"], ability="DROUGHT"))
    chk("3. 가뭄이 발동하지 않는다 (날씨 칸 · 문구)", bt.field.weather != "sun"
        and "햇살이 강해졌다" not in texts(bt.entry) and bt.weather() == "rain", (bt.field.weather, texts(bt.entry)))
    chk("   가뭄 특성 알림도 안 뜬다", not any(e.get("t") == "ability" and e.get("who") == "foe" for e in bt.entry),
        [e for e in bt.entry if e.get("t") == "ability"])
    # 가이오가가 먼저 서 있고 모래날림이 들어온다 (나중에 나온 쪽)
    bt, me, foe = T.fight(kyogre(), mon("TYRANITAR", 50, ["CRUNCH", "SANDSTORM"], ability="SANDSTREAM"), enter=False)
    ev = []
    for who, f in (("me", me), ("foe", foe)):
        A.on_switch_in(bt, f, who, ev)
        SM.on_enter_abilities(bt, f, who, ev)
    chk("   나중에 나온 모래날림도 발동하지 않는다", bt.field.weather != "sand" and "모래바람" not in texts(ev),
        (bt.field.weather, texts(ev)))

    ev = use(bt, "foe", "SANDSTORM")
    chk("4. 모래바람 기술은 실패한다", bt.field.weather != "sand" and "실패" in texts(ev), (bt.field.weather, texts(ev)))
    chk("   AI 값 0 (안 고른다)", SM.value(bt, "SANDSTORM", DEX.move("SANDSTORM"), foe, me, "foe", 1.0) == 0.0)

    bt, me, foe = T.fight(kyogre(), mon("VENUSAUR", 50, ["GIGADRAIN"], ability="CHLOROPHYLL"))
    bt.field.weather, bt.field.weather_turns = "sun", 5       # (예전 판처럼 날씨 칸이 덮어써져 있어도)
    chk("5. 엽록소도 강한 비를 본다 (스피드 두 배 아님)", A._weather(foe) == "rain"
        and A.stat_mult(foe, "spe") == 1.0, (A._weather(foe), A.stat_mult(foe, "spe")))
    bt, me, foe = T.fight(kyogre(), mon("LUDICOLO", 50, ["SURF"], ability="SWIFTSWIM"))
    chk("   쓱쓱은 강한 비에 두 배 (예전과 같다)", A.stat_mult(foe, "spe") == 2.0, A.stat_mult(foe, "spe"))

    bt, me, foe = T.fight(kyogre(), mon("SNORLAX", 50, ["TACKLE"]), enter=False)
    bt.field.weather, bt.field.weather_turns = "sun", 5
    ev = []
    A.on_switch_in(bt, me, "me", ev)
    SM.on_enter_abilities(bt, me, "me", ev)
    chk("6. 원시회귀가 나오면 깔려 있던 쾌청을 걷어 낸다", bt.field.weather is None and bt.weather() == "rain",
        (bt.field.weather, bt.weather()))
    me.hp = 0
    chk("   가이오가가 쓰러지면 맑음 (쾌청이 되살아나지 않는다)", bt.weather() is None, bt.weather())
    bt, me, foe = T.fight(kyogre(), mon("SNORLAX", 50, ["TACKLE"]), enter=False)
    bt.raid = object()
    bt.field.weather, bt.field.weather_turns = "sun", 5
    SM.on_enter_abilities(bt, me, "me", [])
    chk("   레이드는 보스 날씨를 그대로 둔다", bt.field.weather == "sun", bt.field.weather)

    # 11/24 (#829 '시작의바다가 작동을 안 해요'): 처음 나와 원시회귀하면 '강한 비가 내리기 시작했다!' 를 한 번 한다
    bt, me, foe = T.fight(kyogre(), mon("SNORLAX", 50, ["TACKLE"]))
    said = [e for e in bt.entry if e.get("text") == "강한 비가 내리기 시작했다!"]
    chk("8. 처음 나와 원시회귀하면 강한 비 문구가 한 번 (특성 알림과 함께)", len(said) == 1 and said[0]["who"] == "me"
        and any(e.get("t") == "ability" and e.get("who") == "me" for e in bt.entry), texts(bt.entry))
    ev = []
    A.on_switch_in(bt, me, "me", ev)
    SM.on_enter_abilities(bt, me, "me", ev)
    chk("   이미 원시회귀한 채 다시 나오면 on_switch_in 이 한 번만 말한다 (겹치지 않는다)",
        [e.get("text") for e in ev].count("강한 비가 내리기 시작했다!") == 1, texts(ev))
    bt, me, foe = T.fight(mon("GROUDON", 50, ["EARTHQUAKE"], held="REDORB"), mon("SNORLAX", 50, ["TACKLE"]))
    chk("   원시그란돈도 (햇살이 아주 강해졌다)", "햇살이 아주 강해졌다!" in texts(bt.entry), texts(bt.entry))

    bt, me, foe = T.fight(mon("SNORLAX", 50, ["TACKLE"]), mon("TORKOAL", 50, ["SANDSTORM"], ability="DROUGHT"))
    chk("7. 원시회귀가 없으면 가뭄이 그대로", bt.field.weather == "sun", bt.field.weather)
    use(bt, "foe", "SANDSTORM")
    chk("   모래바람 기술도 그대로", bt.field.weather == "sand", bt.field.weather)
    chk("   AI 값도 0 이 아니다", SM.value(bt, "SUNNYDAY", DEX.move("SUNNYDAY"), foe, me, "foe", 1.0) != 0.0)


def main():
    t_hazard_faint()
    t_primal_weather()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
