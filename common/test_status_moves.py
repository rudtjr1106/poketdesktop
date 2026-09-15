# -*- coding: utf-8 -*-
"""변화기 144개 검사 — 혼란·방어·대타출동·도발·날씨·필드·방·진영·압정·교체 ... 서버 없이 돈다.

    python common/test_status_moves.py

배울 수 있는 기술 중 144개가 이 엔진에서 아무 일도 안 했다 (전부 변화기). 원작대로 만든
것이 정말 무언가 하는지, 실패할 때 실패하는지, 저장했다 되살려도 남는지, 무작위로 섞어
돌려도 터지지 않고 같은 시드면 같은 로그인지 본다.
"""
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import battle as B              # noqa: E402
from common import field as FD              # noqa: E402
from common import party_battle as PB       # noqa: E402
from common import pokelogic as P           # noqa: E402
from common import statusmoves as SM        # noqa: E402
from common import trainer_battle as TB     # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Sure(random.Random):
    """명중·부가효과 판정이 늘 성공하는 rng (uniform 이 늘 아래 끝)."""

    def uniform(self, a, b):
        return a


def load_dex():
    with open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8") as f:
        return P.Pokedex(json.load(f))


def mon(dex, species, level, moves, ability=None, gender=None, held=None, iv=31):
    m = P.make_pokemon(dex.get(species), level, random.Random(1), shiny_rate=10 ** 9,
                       ivs=dict((s, iv) for s in P.STATS))
    m["nature"] = "HARDY"
    m["moves"] = list(moves)
    m["held"] = held
    if ability:
        m["ability"] = ability
    if gender:
        m["gender"] = gender
    return m


def fight(dex, a, b, rng=None, abilities=False):
    me, foe = B.Fighter(dex, a), B.Fighter(dex, b)
    me.ability_on = foe.ability_on = abilities
    bt = B.Battle(dex, me, foe, rng or Sure(1), ai="trainer")
    return bt, me, foe


def use(bt, who, key):
    ev = []
    user, target = (bt.me, bt.foe) if who == "me" else (bt.foe, bt.me)
    bt._use(who, user, target, key, ev)
    return ev


def eot(bt):
    ev = []
    bt._end_of_turn(ev)
    return ev


def texts(ev):
    return " | ".join(e.get("text", "") for e in ev if e.get("text"))


def gym(dex, level, team, party, rng=None):
    trainer = {"id": "t", "name": "시험", "role": "관장", "sprite": "t", "level": level,
               "team": [{"species": m["species"], "level": m["level"], "moves": m["moves"],
                         "ability": m["ability"], "held": m.get("held"), "iv": 31, "evs": {},
                         "nature": "HARDY", "gender": m.get("gender") or "M"} for m in team]}
    tb = TB.TrainerBattle(dex, party, trainer, rng or Sure(3))
    tb.start()
    return tb


# ---------------------------------------------------------------- 0. 빠진 것이 없다
def t_빠진것(dex):
    print("-- 빠진 것")
    raw = dex.raw
    learn = set(k for s in raw["species"] for _lv, k in s.get("moves", []))
    with open(os.path.join(ROOT, "server", "data", "tms.json"), encoding="utf-8") as f:
        learn |= set(v["move"] for v in json.load(f)["tms"].values())
    dead = sorted(k for k in learn if raw["moves"][k].get("cat") == "status"
                  and not raw["moves"][k].get("heal") and not raw["moves"][k].get("stat")
                  and raw["moves"][k].get("ail") not in B.HANDLED_STATUS
                  and raw["moves"][k].get("ail") != "leech-seed")
    missing = [k for k in dead if k not in SM.HANDLERS]
    chk("효과가 없던 변화기가 모두 처리된다 (%d개)" % len(dead), not missing, missing)
    chk("HANDLERS 에 적은 기술이 도감에 다 있다", all(k in raw["moves"] for k in SM.HANDLERS
                                               if k not in ("SPIDERWEB", "FORESIGHT", "MIRACLEEYE", "SPOTLIGHT",
                                                            "HOLDHANDS", "MAXGUARD")),
        [k for k in SM.HANDLERS if k not in raw["moves"]])


# ---------------------------------------------------------------- 1. 포켓몬에 붙는 것
def t_혼란(dex):
    print("-- 혼란")
    bt, me, foe = fight(dex, mon(dex, "GENGAR", 50, ["CONFUSERAY", "SWAGGER"]), mon(dex, "MACHAMP", 50, ["TACKLE"]))
    ev = use(bt, "me", "CONFUSERAY")
    chk("이상한빛: 혼란 2~5턴", 2 <= (foe.cond.get("confused") or 0) <= 5 and "혼란에 빠졌다" in texts(ev), texts(ev))
    ev = use(bt, "me", "CONFUSERAY")
    chk("이미 혼란이면 안 걸린다", "이미 혼란" in texts(ev), texts(ev))
    hit_self = 0
    for s in range(60):
        bt2, a, b = fight(dex, mon(dex, "MACHAMP", 50, ["TACKLE"]), mon(dex, "SNORLAX", 50, ["TACKLE"]), rng=random.Random(s))
        a.cond["confused"] = 5
        ev = use(bt2, "me", "TACKLE")
        hit_self += a.hp < a.maxhp
    chk("혼란: 1/3 쯤 스스로를 때린다 (%d/60)" % hit_self, 10 <= hit_self <= 32)
    bt, me, foe = fight(dex, mon(dex, "GENGAR", 50, ["SWAGGER"]), mon(dex, "SLOWBRO", 50, ["TACKLE"], ability="OWNTEMPO"),
                        abilities=True)
    ev = use(bt, "me", "SWAGGER")
    chk("뽐내기: 공격 +2 에 혼란, 마이페이스는 혼란만 막는다",
        foe.stages["atk"] == 2 and not foe.cond.get("confused"), (foe.stages, texts(ev)))
    bt, me, foe = fight(dex, mon(dex, "BUTTERFREE", 50, ["PSYBEAM"]), mon(dex, "SNORLAX", 50, ["TACKLE"]))
    use(bt, "me", "PSYBEAM")
    chk("사이케광선: 부가효과로 혼란 (판정 성공)", foe.cond.get("confused"))
    bt, me, foe = fight(dex, mon(dex, "GENGAR", 50, ["CONFUSERAY"]), mon(dex, "SNORLAX", 50, ["TACKLE"]))
    bt.field.side("foe")["safeguard"] = 5
    use(bt, "me", "CONFUSERAY")
    chk("신비의부적이 혼란을 막는다", not foe.cond.get("confused"))


def t_방어(dex):
    print("-- 방어·버티기·대타출동")
    bt, me, foe = fight(dex, mon(dex, "SNORLAX", 50, ["PROTECT", "SPIKYSHIELD", "KINGSSHIELD", "ENDURE", "SUBSTITUTE"]),
                        mon(dex, "MACHAMP", 50, ["CROSSCHOP", "THUNDERWAVE", "GROWL", "FEINT"]))
    use(bt, "me", "PROTECT")
    ev = use(bt, "foe", "CROSSCHOP")
    chk("방어: 공격을 막는다", me.hp == me.maxhp and "지켰다" in texts(ev), texts(ev))
    fails = 0
    for s in range(40):
        bt2, a, b = fight(dex, mon(dex, "SNORLAX", 50, ["PROTECT"]), mon(dex, "MACHAMP", 50, ["TACKLE"]), rng=random.Random(s))
        use(bt2, "me", "PROTECT")
        bt2.begin_turn()
        fails += "실패" in texts(use(bt2, "me", "PROTECT"))
    chk("방어를 연달아 쓰면 2/3 쯤 실패한다 (%d/40)" % fails, 18 <= fails <= 36)
    bt.begin_turn()
    me.cond.pop("streak", None)
    use(bt, "me", "SPIKYSHIELD")
    hp = foe.hp
    use(bt, "foe", "CROSSCHOP")
    chk("니들가드: 접촉한 상대가 1/8 을 입는다", hp - foe.hp == foe.maxhp // 8, (hp, foe.hp))
    bt.begin_turn()
    me.cond.pop("streak", None)
    use(bt, "me", "KINGSSHIELD")
    use(bt, "foe", "THUNDERWAVE")
    chk("킹실드: 변화기는 못 막는다 (전기자석파가 들어간다)", me.status == "paralysis", me.status)
    me.status = None
    bt.begin_turn()
    me.cond.pop("streak", None)
    use(bt, "me", "PROTECT")
    ev = use(bt, "foe", "FEINT")
    chk("페인트: 방어를 뚫는다", me.hp < me.maxhp and "풀렸다" in texts(ev), texts(ev))
    me.hp = 10
    bt.begin_turn()
    me.cond.pop("streak", None)
    use(bt, "me", "ENDURE")
    use(bt, "foe", "CROSSCHOP")
    chk("버티기: 체력 1 로 버틴다", me.hp == 1, me.hp)

    bt, me, foe = fight(dex, mon(dex, "SNORLAX", 50, ["SUBSTITUTE"]), mon(dex, "MACHAMP", 50, ["TACKLE", "THUNDERWAVE", "GROWL"]))
    use(bt, "me", "SUBSTITUTE")
    chk("대타출동: 체력 1/4 을 쓴다", me.hp == me.maxhp - me.maxhp // 4 and me.cond.get("sub") == me.maxhp // 4)
    hp = me.hp
    ev = use(bt, "foe", "TACKLE")
    chk("대타가 공격을 대신 받는다", me.hp == hp and "대신 공격" in texts(ev), texts(ev))
    ev = use(bt, "foe", "THUNDERWAVE")
    chk("대타가 있으면 전기자석파가 실패한다", me.status is None and "실패" in texts(ev), texts(ev))
    use(bt, "foe", "GROWL")
    chk("소리 기술(울음소리)은 대타를 뚫는다", me.stages["atk"] == -1, me.stages)
    ev = use(bt, "me", "SUBSTITUTE")
    chk("대타가 있으면 또 못 만든다", "실패" in texts(ev), texts(ev))


def t_제한(dex):
    print("-- 도발·사슬묶기·트집·앙코르·봉인·회복봉인")
    bt, me, foe = fight(dex, mon(dex, "GENGAR", 50, ["TAUNT", "DISABLE", "TORMENT", "ENCORE", "IMPRISON", "HEALBLOCK"]),
                        mon(dex, "SLOWBRO", 50, ["RECOVER", "PSYCHIC", "CALMMIND", "GENGAR" and "TACKLE"]))
    use(bt, "me", "TAUNT")
    chk("도발: 변화기를 못 쓴다", bool(SM.restricted(bt, foe, "RECOVER")) and not SM.restricted(bt, foe, "PSYCHIC"))
    chk("쓸 수 있는 기술 목록에서 빠진다", "RECOVER" not in bt.usable(foe) and "CALMMIND" not in bt.usable(foe), bt.usable(foe))
    for _ in range(3):
        eot(bt)
    chk("도발은 3턴 뒤 풀린다", not foe.cond.get("taunt"))
    use(bt, "foe", "PSYCHIC")
    use(bt, "me", "DISABLE")
    chk("사슬묶기: 방금 쓴 기술(사이코키네시스)을 막는다", bool(SM.restricted(bt, foe, "PSYCHIC")))
    foe.cond.clear()
    use(bt, "foe", "TACKLE")
    use(bt, "me", "TORMENT")
    chk("트집: 같은 기술을 연달아 못 쓴다", bool(SM.restricted(bt, foe, "TACKLE")) and not SM.restricted(bt, foe, "PSYCHIC"))
    foe.cond.clear()
    use(bt, "foe", "CALMMIND")
    use(bt, "me", "ENCORE")
    chk("앙코르: 명상만 쓸 수 있다", bool(SM.restricted(bt, foe, "PSYCHIC")) and not SM.restricted(bt, foe, "CALMMIND"))
    ev = []
    bt._use("foe", foe, me, "PSYCHIC", ev)
    chk("앙코르를 받으면 다른 기술을 골라도 앙코르 기술이 나간다", "명상" in texts(ev), texts(ev))
    foe.cond.clear()
    me.moves = ["IMPRISON", "PSYCHIC"]
    use(bt, "me", "IMPRISON")
    chk("봉인: 내가 아는 기술을 상대가 못 쓴다", bool(SM.restricted(bt, foe, "PSYCHIC")))
    me.cond.pop("imprison", None)
    use(bt, "me", "HEALBLOCK")
    chk("회복봉인: 회복기를 못 쓴다", bool(SM.restricted(bt, foe, "RECOVER")))


def t_시간차(dex):
    print("-- 하품·악몽·저주·멸망의노래·뿌리박기·아쿠아링")
    bt, me, foe = fight(dex, mon(dex, "SLOWKING", 50, ["YAWN"]), mon(dex, "SNORLAX", 50, ["TACKLE"]))
    use(bt, "me", "YAWN")
    eot(bt)
    chk("하품: 그 턴에는 안 잠든다", foe.status is None)
    eot(bt)
    chk("하품: 다음 턴 끝에 잠든다", foe.status == "sleep", foe.status)
    bt, me, foe = fight(dex, mon(dex, "GENGAR", 50, ["NIGHTMARE", "CURSE"]), mon(dex, "SNORLAX", 50, ["TACKLE"]))
    ev = use(bt, "me", "NIGHTMARE")
    chk("악몽: 잠들지 않았으면 실패", "실패" in texts(ev), texts(ev))
    foe.status, foe.sleep_turns = "sleep", 3
    use(bt, "me", "NIGHTMARE")
    hp = foe.hp
    eot(bt)
    chk("악몽: 잠든 동안 턴마다 1/4", hp - foe.hp == foe.maxhp // 4, (hp, foe.hp))
    mhp = me.hp
    use(bt, "me", "CURSE")
    chk("고스트의 저주: 내 체력 반, 상대는 저주", mhp - me.hp == me.maxhp // 2 and foe.cond.get("cursed"))
    bt, me, foe = fight(dex, mon(dex, "SNORLAX", 50, ["CURSE"]), mon(dex, "RATTATA", 50, ["TACKLE"]))
    use(bt, "me", "CURSE")
    chk("고스트가 아니면: 공격·방어 +1, 스피드 -1", (me.stages["atk"], me.stages["def"], me.stages["spe"]) == (1, 1, -1))
    bt, me, foe = fight(dex, mon(dex, "LAPRAS", 50, ["PERISHSONG", "INGRAIN", "AQUARING"]), mon(dex, "RATTATA", 50, ["TACKLE"]))
    use(bt, "me", "PERISHSONG")
    for _ in range(3):
        eot(bt)
    chk("멸망의노래: 3턴 뒤 둘 다 쓰러진다", not me.alive() and not foe.alive(), (me.hp, foe.hp))
    bt, me, foe = fight(dex, mon(dex, "LAPRAS", 50, ["INGRAIN", "AQUARING"]), mon(dex, "RATTATA", 50, ["TACKLE"]))
    use(bt, "me", "INGRAIN")
    use(bt, "me", "AQUARING")
    me.hp = 10
    eot(bt)
    chk("뿌리박기·아쿠아링: 턴마다 1/16 씩", me.hp == 10 + 2 * (me.maxhp // 16), me.hp)
    chk("뿌리박기: 붙잡혀서 교체·도망을 못 한다", SM.trapped(bt, me))


def t_헤롱헤롱과_잠김(dex):
    print("-- 헤롱헤롱·검은눈빛·문어굳히기·조이기")
    bt, me, foe = fight(dex, mon(dex, "CLEFABLE", 50, ["ATTRACT"], gender="F"), mon(dex, "MACHAMP", 50, ["TACKLE"], gender="F"))
    chk("헤롱헤롱: 같은 성별이면 실패", "실패" in texts(use(bt, "me", "ATTRACT")))
    bt, me, foe = fight(dex, mon(dex, "CLEFABLE", 50, ["ATTRACT"], gender="F"), mon(dex, "MACHAMP", 50, ["TACKLE"], gender="M"))
    use(bt, "me", "ATTRACT")
    chk("헤롱헤롱: 다른 성별이면 걸린다", foe.cond.get("attract") == "me")
    stuck = 0
    for s in range(60):
        bt2, a, b = fight(dex, mon(dex, "MACHAMP", 50, ["TACKLE"]), mon(dex, "SNORLAX", 50, ["TACKLE"]), rng=random.Random(s))
        a.cond["attract"] = "foe"
        stuck += "기술을 쓸 수 없었다" in texts(use(bt2, "me", "TACKLE"))
    chk("헤롱헤롱: 반쯤 못 움직인다 (%d/60)" % stuck, 18 <= stuck <= 42)
    bt, me, foe = fight(dex, mon(dex, "UMBREON", 50, ["MEANLOOK", "OCTOLOCK"]), mon(dex, "SNORLAX", 50, ["TACKLE"]))
    use(bt, "me", "MEANLOOK")
    chk("검은눈빛: 붙잡는다", SM.trapped(bt, foe))
    foe.cond.clear()
    use(bt, "me", "OCTOLOCK")
    eot(bt)
    chk("문어굳히기: 턴마다 방어·특방 -1", foe.stages["def"] == -1 and foe.stages["spd"] == -1)
    bt, me, foe = fight(dex, mon(dex, "ARBOK", 50, ["WRAP"]), mon(dex, "SNORLAX", 50, ["TACKLE"]))
    use(bt, "me", "WRAP")
    hp = foe.hp
    eot(bt)
    chk("김밥말이: 붙잡고 턴마다 1/8", foe.cond.get("bound") and hp - foe.hp == foe.maxhp // 8, (hp, foe.hp))
    SM.on_leave(bt, "me")
    chk("건 쪽이 물러나면 풀린다", not foe.cond.get("bound"))


def t_특성과_타입(dex):
    print("-- 위액·고민씨·스킬스왑·물붓기·핼러윈·변신·흉내내기·스케치")
    bt, me, foe = fight(dex, mon(dex, "MUK", 50, ["GASTROACID", "EARTHQUAKE"]), mon(dex, "GENGAR", 50, ["TACKLE"], ability="LEVITATE"),
                        abilities=True)
    hp = foe.hp
    use(bt, "me", "EARTHQUAKE")
    chk("부유: 지진이 안 맞는다", foe.hp == hp)
    use(bt, "me", "GASTROACID")
    use(bt, "me", "EARTHQUAKE")
    chk("위액을 맞으면 부유가 사라져 지진이 맞는다", foe.hp < hp, (hp, foe.hp))
    bt, me, foe = fight(dex, mon(dex, "JUMPLUFF", 50, ["WORRYSEED", "SKILLSWAP", "SOAK", "TRICKORTREAT"], ability="CHLOROPHYLL"),
                        mon(dex, "SNORLAX", 50, ["REST"], ability="THICKFAT"), abilities=True)
    use(bt, "me", "WORRYSEED")
    chk("고민씨: 특성이 불면", foe.ability == "INSOMNIA")
    use(bt, "me", "SKILLSWAP")
    chk("스킬스왑: 특성을 맞바꾼다", me.ability == "INSOMNIA" and foe.ability == "CHLOROPHYLL")
    use(bt, "me", "SOAK")
    chk("물붓기: 순수 물 타입", foe.types() == ["WATER"])
    use(bt, "me", "TRICKORTREAT")
    chk("핼러윈: 고스트 타입이 더해진다", foe.types() == ["WATER", "GHOST"], foe.types())
    foe.clear_volatile()
    chk("물러나면 특성·타입이 원래대로", foe.ability == "THICKFAT" and foe.types() == ["NORMAL"], (foe.ability, foe.types()))

    bt, me, foe = fight(dex, mon(dex, "DITTO", 50, ["TRANSFORM"]), mon(dex, "DRAGONITE", 60, ["DRAGONCLAW", "EXTREMESPEED"]))
    base_hp = me.maxhp
    use(bt, "me", "TRANSFORM")
    chk("변신: 기술·타입·능력치를 베낀다", me.moves == ["DRAGONCLAW", "EXTREMESPEED"] and me.types() == foe.types()
        and me.base["atk"] == foe.base["atk"] and me.maxhp == base_hp, (me.moves, me.types()))
    chk("변신한 기술은 PP 5", me.pp["DRAGONCLAW"] == 5)
    saved = B.Fighter(dex, me.mon, me.hp, me.pp, me.status)
    saved.load_volatile(json.loads(json.dumps(me.volatile())))
    chk("저장했다 되살려도 변신한 채", saved.moves == me.moves and saved.base["atk"] == me.base["atk"])
    me.clear_volatile()
    chk("물러나면 메타몽으로", me.moves == ["TRANSFORM"] and me.types() == ["NORMAL"], (me.moves, me.types()))

    bt, me, foe = fight(dex, mon(dex, "SMEARGLE", 50, ["SKETCH", "MIMIC"]), mon(dex, "PIKACHU", 50, ["THUNDERBOLT"]))
    use(bt, "foe", "THUNDERBOLT")
    use(bt, "me", "MIMIC")
    chk("흉내내기: 그 판에서만 상대 기술", "THUNDERBOLT" in me.moves and "MIMIC" not in me.moves
        and me.mon["moves"] == ["SKETCH", "MIMIC"], (me.moves, me.mon["moves"]))
    before = me.pp["SKETCH"]
    me.pp["SKETCH"] = before - 3                    # 흉내 낸 동안 스케치를 세 번 썼다고 치자
    me.clear_volatile()
    chk("흉내내기가 풀려도 그동안 쓴 다른 기술의 PP 는 돌아오지 않는다",
        me.moves == ["SKETCH", "MIMIC"] and me.pp["SKETCH"] == before - 3, me.pp)
    use(bt, "foe", "THUNDERBOLT")
    use(bt, "me", "SKETCH")
    chk("스케치(야생의 내 포켓몬): 영원히 배운다 (포켓몬 자료가 바뀐다)",
        me.mon["moves"][0] == "THUNDERBOLT" and me.mon.get("_sketched"), me.mon)


def t_능력(dex):
    print("-- 랭크·능력치를 다루는 기술")
    bt, me, foe = fight(dex, mon(dex, "ALAKAZAM", 50, ["PSYCHUP", "HAZE", "TOPSYTURVY", "HEARTSWAP", "POWERSPLIT",
                                                        "SPEEDSWAP", "POWERTRICK"]),
                        mon(dex, "SHUCKLE", 50, ["TACKLE"]))
    foe.stages.update({"atk": 2, "spe": 1})
    use(bt, "me", "PSYCHUP")
    chk("자기암시: 상대 랭크를 베낀다", me.stages["atk"] == 2 and me.stages["spe"] == 1)
    use(bt, "me", "HAZE")
    chk("흑안개: 모두 0", not any(me.stages.values()) and not any(foe.stages.values()))
    foe.stages["def"] = 3
    use(bt, "me", "TOPSYTURVY")
    chk("뒤집어엎기: 랭크를 뒤집는다", foe.stages["def"] == -3)
    me.stages["spa"] = 2
    use(bt, "me", "HEARTSWAP")
    chk("하트스왑: 랭크를 맞바꾼다", foe.stages["spa"] == 2 and me.stages["def"] == -3)
    a, b = me.base["atk"], foe.base["atk"]
    use(bt, "me", "POWERSPLIT")
    chk("파워셰어: 공격을 평균낸다", me.base["atk"] == foe.base["atk"] == (a + b) // 2)
    sa, sb = me.base["spe"], foe.base["spe"]
    use(bt, "me", "SPEEDSWAP")
    chk("스피드스왑: 스피드를 맞바꾼다", me.base["spe"] == sb and foe.base["spe"] == sa)
    at, df = me.base["atk"], me.base["def"]
    use(bt, "me", "POWERTRICK")
    chk("파워트릭: 공격과 방어를 바꾼다", me.base["atk"] == df and me.base["def"] == at)

    bt, me, foe = fight(dex, mon(dex, "SNORLAX", 50, ["BELLYDRUM", "FILLETAWAY", "ACUPRESSURE", "TAKEHEART"]),
                        mon(dex, "RATTATA", 50, ["TACKLE"]))
    use(bt, "me", "BELLYDRUM")
    chk("배북: 체력 반, 공격 최대", me.stages["atk"] == 6 and me.hp == me.maxhp - me.maxhp // 2)
    chk("배북: 체력이 반 이하면 실패", "실패" in texts(use(bt, "me", "BELLYDRUM")))
    me.status = "burn"
    use(bt, "me", "TAKEHEART")
    chk("브레이브차지: 상태이상을 고치고 특공·특방 +1", me.status is None and me.stages["spa"] == 1)
    use(bt, "me", "ACUPRESSURE")
    chk("경혈찌르기: 어느 하나 +2", sum(me.stages.values()) == 6 + 1 + 1 + 2, me.stages)


def t_회복(dex):
    print("-- 아픔나누기·치료방울·사이코시프트·잠자기·희망사항·치유소원·회생의기도")
    bt, me, foe = fight(dex, mon(dex, "GENGAR", 50, ["PAINSPLIT", "PSYCHOSHIFT", "REST", "WISH"]), mon(dex, "SNORLAX", 50, ["TACKLE"]))
    me.hp = 20
    total = me.hp + foe.hp
    use(bt, "me", "PAINSPLIT")
    chk("아픔나누기: 체력을 똑같이", me.hp == foe.hp == total // 2, (me.hp, foe.hp))
    me.status = "poison"
    use(bt, "me", "PSYCHOSHIFT")
    chk("사이코시프트: 내 독을 상대에게", me.status is None and foe.status == "poison", (me.status, foe.status))
    me.hp = 5
    use(bt, "me", "REST")
    chk("잠자기: 가득 회복하고 2턴 잠든다", me.hp == me.maxhp and me.status == "sleep" and me.sleep_turns == 2)
    me.status, me.sleep_turns = None, 0
    chk("잠자기: 가득하면 실패", "실패" in texts(use(bt, "me", "REST")))
    me.hp = 10
    me.status = None
    use(bt, "me", "WISH")
    eot(bt)
    chk("희망사항: 그 턴에는 아직", me.hp == 10)
    eot(bt)
    chk("희망사항: 다음 턴 끝에 반 회복", me.hp == 10 + me.maxhp // 2, me.hp)

    party = [mon(dex, "BLISSEY", 50, ["HEALBELL", "HEALINGWISH", "REVIVALBLESSING"]), mon(dex, "RATTATA", 50, ["TACKLE"]),
             mon(dex, "PIDGEY", 50, ["TACKLE"])]
    tb = gym(dex, 50, [mon(dex, "SNORLAX", 50, ["TACKLE"])], party)
    tb.me_team[1].status = "burn"
    ev = []
    tb.bt._use("me", tb.me, tb.foe, "HEALBELL", ev)
    chk("치료방울: 벤치의 동료까지 고친다", tb.me_team[1].status is None)
    tb.me_team[2].hp = 0
    ev = []
    tb.bt._use("me", tb.me, tb.foe, "REVIVALBLESSING", ev)
    chk("회생의기도: 쓰러진 동료가 반으로 되살아난다", tb.me_team[2].hp == tb.me_team[2].maxhp // 2, texts(ev))
    tb.me_team[1].hp = 3
    ev = []
    tb.bt._use("me", tb.me, tb.foe, "HEALINGWISH", ev)
    chk("치유소원: 나는 쓰러진다", not tb.me.alive())
    tb.bt._check_faint(ev)
    tb._settle(ev)
    tb.act("switch", 1)
    chk("치유소원: 다음에 나온 포켓몬이 가득 회복", tb.me.hp == tb.me.maxhp, tb.me.hp)


def t_길동무와_튕기기(dex):
    print("-- 길동무·원념·원한·가로채기·매직코트·지휘")
    bt, me, foe = fight(dex, mon(dex, "GENGAR", 30, ["DESTINYBOND", "GRUDGE"]), mon(dex, "TYRANITAR", 80, ["CRUNCH", "DRAGONDANCE"]))
    use(bt, "me", "DESTINYBOND")
    use(bt, "foe", "CRUNCH")
    chk("길동무: 쓰러뜨린 상대도 쓰러진다", not me.alive() and not foe.alive(), (me.hp, foe.hp))
    bt, me, foe = fight(dex, mon(dex, "GENGAR", 30, ["GRUDGE", "SPITE", "SNATCH", "MAGICCOAT"]), mon(dex, "TYRANITAR", 80, ["CRUNCH", "DRAGONDANCE", "THUNDERWAVE"]))
    use(bt, "me", "GRUDGE")
    use(bt, "foe", "CRUNCH")
    chk("원념: 쓰러뜨린 기술의 PP 가 0", foe.pp["CRUNCH"] == 0, foe.pp)
    bt, me, foe = fight(dex, mon(dex, "SABLEYE", 50, ["SPITE", "SNATCH", "MAGICCOAT"]), mon(dex, "TYRANITAR", 50, ["CRUNCH", "DRAGONDANCE", "THUNDERWAVE"]))
    use(bt, "foe", "CRUNCH")
    pp = foe.pp["CRUNCH"]
    use(bt, "me", "SPITE")
    chk("원한: PP 4 줄인다", foe.pp["CRUNCH"] == pp - 4)
    bt.begin_turn()
    use(bt, "me", "SNATCH")
    use(bt, "foe", "DRAGONDANCE")
    chk("가로채기: 용의춤을 빼앗는다", me.stages["atk"] == 1 and foe.stages["atk"] == 0, (me.stages, foe.stages))
    bt.begin_turn()
    use(bt, "me", "MAGICCOAT")
    use(bt, "foe", "THUNDERWAVE")
    chk("매직코트: 전기자석파를 튕긴다", foe.status == "paralysis" and me.status is None, (foe.status, me.status))


def t_부르기(dex):
    print("-- 손가락흔들기·흉내쟁이·따라하기·자연의힘·잠꼬대")
    bt, me, foe = fight(dex, mon(dex, "CLEFAIRY", 50, ["METRONOME", "COPYCAT", "MIRRORMOVE", "NATUREPOWER", "SLEEPTALK", "TACKLE"]),
                        mon(dex, "SNORLAX", 30, ["BODYSLAM"]), rng=random.Random(5))
    ev = use(bt, "me", "METRONOME")
    moves = [e for e in ev if e.get("t") == "move"]
    chk("손가락흔들기: 다른 기술이 나간다", len(moves) >= 2 and moves[1]["move"] != "손가락흔들기", texts(ev))
    use(bt, "foe", "BODYSLAM")
    ev = use(bt, "me", "COPYCAT")
    chk("흉내쟁이: 방금 쓰인 기술(누르기)", "누르기" in texts(ev), texts(ev))
    ev = use(bt, "me", "MIRRORMOVE")
    chk("따라하기: 상대가 쓴 기술", "누르기" in texts(ev), texts(ev))
    ev = use(bt, "me", "NATUREPOWER")
    chk("자연의힘: 필드가 없으면 트라이어택", "트라이어택" in texts(ev), texts(ev))
    bt.field.terrain, bt.field.terrain_turns = "electric", 5
    ev = use(bt, "me", "NATUREPOWER")
    chk("자연의힘: 일렉트릭필드면 10만볼트", "10만볼트" in texts(ev), texts(ev))
    me.status, me.sleep_turns = "sleep", 3
    ev = use(bt, "me", "SLEEPTALK")
    chk("잠꼬대: 잠든 채로 다른 기술을 쓴다", len([e for e in ev if e.get("t") == "move"]) >= 2, texts(ev))


def t_도구(dex):
    print("-- 트릭·리사이클·다과회·금제")
    bt, me, foe = fight(dex, mon(dex, "ALAKAZAM", 50, ["TRICK", "RECYCLE", "TEATIME", "EMBARGO"], held="CHOICESCARF"),
                        mon(dex, "SNORLAX", 50, ["TACKLE"], held="LEFTOVERS"))
    use(bt, "me", "TRICK")
    chk("트릭: 도구를 맞바꾼다", me.held == "LEFTOVERS" and foe.held == "CHOICESCARF")
    back = B.Fighter(dex, foe.mon, foe.hp, foe.pp, foe.status)
    back.load_volatile(json.loads(json.dumps(foe.volatile())))
    chk("바꾼 도구가 저장본에 남는다 (DB 의 도구는 그대로)", back.held == "CHOICESCARF" and foe.mon["held"] == "LEFTOVERS")
    use(bt, "me", "EMBARGO")
    chk("금제: 도구가 없는 것처럼", foe.held is None and foe.cond.get("embargo") == 5)
    for _ in range(5):
        eot(bt)
    chk("금제는 5턴 뒤 풀린다", foe.held == "CHOICESCARF")
    bt, me, foe = fight(dex, mon(dex, "SNORLAX", 50, ["RECYCLE", "TEATIME"], held="SITRUSBERRY"), mon(dex, "RATTATA", 50, ["TACKLE"]))
    me.hp = me.maxhp // 3
    hp = me.hp
    use(bt, "me", "TEATIME")
    chk("다과회: 조건 없이 열매를 먹는다", me.hp > hp and me.used)
    use(bt, "me", "RECYCLE")
    chk("리사이클: 먹은 열매를 되살린다", not me.used and me.held == "SITRUSBERRY")


# ---------------------------------------------------------------- 2. 판 전체
def t_날씨(dex):
    print("-- 날씨")
    bt, me, foe = fight(dex, mon(dex, "CHARIZARD", 50, ["SUNNYDAY", "FLAMETHROWER", "SANDSTORM", "HAIL", "SNOWSCAPE", "RAINDANCE",
                                                         "SOLARBEAM", "MOONLIGHT"]),
                        mon(dex, "SNORLAX", 50, ["TACKLE"]))
    plain = bt.estimate(me, foe, "FLAMETHROWER")
    use(bt, "me", "SUNNYDAY")
    chk("쾌청: 햇살", bt.field.weather == "sun" and bt.field.weather_turns == 5)
    chk("쾌청: 불꽃 1.5배", abs(bt.estimate(me, foe, "FLAMETHROWER") - plain * 1.5) <= 2, (plain, bt.estimate(me, foe, "FLAMETHROWER")))
    me.hp = 10
    use(bt, "me", "MOONLIGHT")
    chk("달빛: 쾌청이면 2/3", me.hp == 10 + int(me.maxhp * 66 / 100.0), me.hp)
    use(bt, "me", "RAINDANCE")
    chk("비바라기: 불꽃 반감", bt.estimate(me, foe, "FLAMETHROWER") < plain * 0.6)
    use(bt, "me", "SANDSTORM")
    hp = foe.hp
    eot(bt)
    chk("모래바람: 바위·땅·강철이 아니면 1/16", hp - foe.hp == foe.maxhp // 16, (hp, foe.hp))
    for _ in range(5):
        eot(bt)
    chk("날씨는 5턴 뒤 그친다", bt.field.weather is None)
    bt, me, foe = fight(dex, mon(dex, "LAPRAS", 50, ["SNOWSCAPE", "BLIZZARD"]), mon(dex, "GLACEON", 50, ["TACKLE"]))
    d0 = foe.stat("def")
    use(bt, "me", "SNOWSCAPE")
    chk("설경: 얼음 타입 방어 1.5배", foe.stat("def") == int(d0 * 1.5), (d0, foe.stat("def")))
    chk("설경: 눈보라가 반드시 맞는다", SM.accuracy(dex.move("BLIZZARD"), me, foe) == 0)
    party = [mon(dex, "KYOGRE", 70, ["SURF"], ability="DRIZZLE")]
    tb = gym(dex, 50, [mon(dex, "TYRANITAR", 50, ["CRUNCH"], ability="SANDSTREAM")], party)
    chk("잔비·모래날림: 나오면 날씨를 부른다 (나중에 나온 쪽이 이긴다)", tb.bt.field.weather in ("rain", "sand"), tb.bt.field.weather)


def t_필드와_방(dex):
    print("-- 필드·방")
    bt, me, foe = fight(dex, mon(dex, "PIKACHU", 50, ["ELECTRICTERRAIN", "THUNDERBOLT", "GRASSYTERRAIN", "MISTYTERRAIN", "PSYCHICTERRAIN",
                                                       "QUICKATTACK", "TRICKROOM", "WONDERROOM"]),
                        mon(dex, "SNORLAX", 50, ["SPORE", "EARTHQUAKE", "QUICKATTACK"]))
    plain = bt.estimate(me, foe, "THUNDERBOLT")
    use(bt, "me", "ELECTRICTERRAIN")
    chk("일렉트릭필드: 전기 1.3배", abs(bt.estimate(me, foe, "THUNDERBOLT") - plain * 1.3) <= 2)
    bt._apply_status(me, "sleep", [], source=foe)
    chk("일렉트릭필드: 땅에 붙어 있으면 잠들지 않는다", me.status is None)
    use(bt, "me", "MISTYTERRAIN")
    bt._apply_status(me, "burn", [], source=foe)
    chk("미스트필드: 상태이상이 안 걸린다", me.status is None)
    use(bt, "me", "PSYCHICTERRAIN")
    ev = use(bt, "foe", "QUICKATTACK")
    chk("사이코필드: 선공기가 안 통한다", me.hp == me.maxhp and "사이코필드" in texts(ev), texts(ev))
    use(bt, "me", "GRASSYTERRAIN")
    me.hp = 10
    eot(bt)
    chk("그래스필드: 턴마다 1/16 회복", me.hp == 10 + me.maxhp // 16, me.hp)
    use(bt, "me", "TRICKROOM")
    chk("트릭룸: 느린 쪽(잠만보)이 먼저", bt._order("THUNDERBOLT", "EARTHQUAKE") == ["foe", "me"])
    use(bt, "me", "TRICKROOM")
    chk("트릭룸을 다시 쓰면 풀린다", not bt.field.room("trickroom"))
    d, sd = foe.stat("def"), foe.stat("spd")
    use(bt, "me", "WONDERROOM")
    chk("원더룸: 방어와 특수방어가 뒤바뀐다", foe.stat("def") == sd and foe.stat("spd") == d)
    bt, me, foe = fight(dex, mon(dex, "BRONZONG", 50, ["GRAVITY", "MAGNETRISE", "MAGICROOM", "MUDSPORT"], ability="LEVITATE"),
                        mon(dex, "DUGTRIO", 50, ["EARTHQUAKE", "THUNDERSHOCK"], held="LEFTOVERS"), abilities=True)
    use(bt, "me", "MAGNETRISE")
    hp = me.hp
    use(bt, "foe", "EARTHQUAKE")
    chk("전자부유: 땅 기술이 안 맞는다", me.hp == hp)
    use(bt, "me", "GRAVITY")
    chk("중력: 전자부유가 풀린다", not me.cond.get("magnetrise"))
    use(bt, "foe", "EARTHQUAKE")
    chk("중력: 부유여도 지진이 맞는다", me.hp < hp, (hp, me.hp))
    chk("중력: 전자부유를 못 쓴다", bool(SM.restricted(bt, me, "MAGNETRISE")))
    use(bt, "me", "MAGICROOM")
    chk("매직룸: 도구가 없는 것처럼", foe.held is None)
    e0 = bt.estimate(foe, me, "THUNDERSHOCK")
    use(bt, "me", "MUDSPORT")
    chk("흙놀이: 전기 1/3", bt.estimate(foe, me, "THUNDERSHOCK") <= e0 / 2.5 + 1, (e0, bt.estimate(foe, me, "THUNDERSHOCK")))


def t_진영(dex):
    print("-- 리플렉터·빛의장막·오로라베일·신비의부적·흰안개·순풍")
    bt, me, foe = fight(dex, mon(dex, "ALAKAZAM", 50, ["REFLECT", "LIGHTSCREEN", "AURORAVEIL", "SAFEGUARD", "MIST", "TAILWIND"]),
                        mon(dex, "MACHAMP", 50, ["CROSSCHOP", "BRICKBREAK", "THUNDERWAVE", "GROWL", "FOCUSBLAST"]))
    plain = bt.estimate(foe, me, "CROSSCHOP")
    use(bt, "me", "REFLECT")
    chk("리플렉터: 물리 반감", abs(bt.estimate(foe, me, "CROSSCHOP") - plain * 0.5) <= 2)
    chk("급소면 리플렉터를 무시한다", SM.field_mult(dex.move("CROSSCHOP"), "FIGHTING", foe, me, True) == 1.0)
    chk("오로라베일: 싸라기눈·설경이 아니면 실패", "실패" in texts(use(bt, "me", "AURORAVEIL")))
    ev = use(bt, "foe", "BRICKBREAK")
    chk("깨트리기: 리플렉터를 깬다", not bt.field.side("me").get("reflect") and "깨졌다" in texts(ev), texts(ev))
    use(bt, "me", "SAFEGUARD")
    use(bt, "foe", "THUNDERWAVE")
    chk("신비의부적: 상태이상을 막는다", me.status is None)
    use(bt, "me", "MIST")
    use(bt, "foe", "GROWL")
    chk("흰안개: 능력 하락을 막는다", me.stages["atk"] == 0)
    s0 = bt.speed("me")
    use(bt, "me", "TAILWIND")
    chk("순풍: 스피드 두 배", bt.speed("me") == s0 * 2)
    for _ in range(4):
        eot(bt)
    chk("순풍은 4턴", not bt.field.side("me").get("tailwind"))


def t_압정과_교체(dex):
    print("-- 압정·스텔스록·독압정·끈적끈적네트·고속스핀·코트체인지·울부짖기·배턴터치·유턴")
    team = [mon(dex, "SKARMORY", 50, ["SPIKES", "STEALTHROCK", "TOXICSPIKES", "STICKYWEB", "ROAR", "COURTCHANGE"]),
            mon(dex, "BLISSEY", 50, ["TACKLE"])]
    party = [mon(dex, "RATTATA", 50, ["TACKLE", "RAPIDSPIN"]), mon(dex, "CHARIZARD", 50, ["TACKLE"]),
             mon(dex, "RATICATE", 50, ["TACKLE"])]
    tb = gym(dex, 50, team, party)
    bt = tb.bt
    for k in ("STEALTHROCK", "SPIKES", "TOXICSPIKES", "STICKYWEB"):
        ev = []
        bt._use("foe", tb.foe, tb.me, k, ev)
    side = bt.field.side("me")
    chk("상대 진영에 넷을 깐다", side.get("stealthrock") and side.get("spikes") == 1 and side.get("toxicspikes") == 1
        and side.get("stickyweb"), side)
    ev = []
    tb._switch("me", 1, ev)
    zard = tb.me
    rock = zard.maxhp * 4 // 8
    chk("스텔스록: 리자몽(바위 4배)은 절반을 잃는다, 비행이라 압정·독압정·네트는 안 밟는다",
        zard.maxhp - zard.hp == rock and zard.status is None and zard.stages["spe"] == 0, (zard.maxhp - zard.hp, rock, texts(ev)))
    ev = []
    tb._switch("me", 2, ev)
    rat = tb.me
    chk("땅에 붙은 포켓몬: 스텔스록 1/8 + 압정 1/8, 독, 스피드 -1",
        rat.maxhp - rat.hp == rat.maxhp // 8 + rat.maxhp // 8 and rat.status == "poison" and rat.stages["spe"] == -1,
        (rat.maxhp - rat.hp, rat.status, rat.stages, texts(ev)))
    ev = []
    tb._switch("me", 0, ev)
    ev = []
    bt._use("me", tb.me, tb.foe, "RAPIDSPIN", ev)
    chk("고속스핀: 내 진영의 압정을 치운다", not any(bt.field.side("me").get(h) for h in FD.HAZARDS), bt.field.side("me"))
    bt.field.side("foe")["spikes"] = 2
    bt.field.side("me")["reflect"] = 3
    ev = []
    bt._use("foe", tb.foe, tb.me, "COURTCHANGE", ev)
    chk("코트체인지: 진영 효과를 맞바꾼다", bt.field.side("me").get("spikes") == 2 and bt.field.side("foe").get("reflect") == 3)
    before = tb.mi
    ev = []
    bt._use("foe", tb.foe, tb.me, "ROAR", ev)
    chk("울부짖기(관장): 내 포켓몬을 끌어낸다", tb.mi != before and "끌려 나갔다" in texts(ev), texts(ev))

    bt2, a, b = fight(dex, mon(dex, "ARCANINE", 50, ["ROAR", "TELEPORT"]), mon(dex, "RATTATA", 50, ["TACKLE"]))
    ev = use(bt2, "me", "ROAR")
    chk("울부짖기(야생): 판이 끝난다", bt2.over and bt2.result == "fled", texts(ev))
    bt3, a, b = fight(dex, mon(dex, "ABRA", 50, ["TELEPORT"]), mon(dex, "RATTATA", 50, ["TACKLE"]))
    use(bt3, "foe", "TACKLE")
    ev = use(bt3, "me", "TELEPORT")
    chk("순간이동(야생): 도망친다", bt3.over and bt3.result == "fled")

    # 상대 AI 의 배턴터치: 랭크를 넘긴다
    team = [mon(dex, "NINJASK", 50, ["BATONPASS", "SWORDSDANCE"]), mon(dex, "SCIZOR", 50, ["XSCISSOR"])]
    tb = gym(dex, 50, team, [mon(dex, "SNORLAX", 50, ["TACKLE"])])
    tb.foe.stages["atk"] = 4
    tb.foe.cond["focus"] = True
    ev = []
    tb.bt._use("foe", tb.foe, tb.me, "BATONPASS", ev)
    chk("배턴터치: 다음 포켓몬이 랭크·기충전을 받는다", tb.fi == 1 and tb.foe.stages["atk"] == 4 and tb.foe.cond.get("focus"),
        (tb.fi, tb.foe.stages, texts(ev)))
    # 내 유턴: 턴이 끝나면 고른다
    party = [mon(dex, "SCIZOR", 50, ["UTURN"]), mon(dex, "SNORLAX", 50, ["TACKLE"])]
    tb = gym(dex, 50, [mon(dex, "BLISSEY", 50, ["SOFTBOILED"])], party)
    ev = tb.act("move", "UTURN")
    chk("유턴(내 포켓몬): 턴 끝에 교체할 포켓몬을 묻는다", tb.need_switch and tb.me.alive() and "고르세요" in texts(ev), texts(ev))
    back = TB.TrainerBattle.load(dex, json.loads(json.dumps(tb.dump())))
    ev = back.act("switch", 1)
    chk("저장했다 되살려도 이어서 교체된다", back.mi == 1 and not back.need_switch, texts(ev))

    # 유저 배틀: 라운드 도중에 끌려 나가면 round 이벤트로 바뀐다 (ko 는 없다)
    a = [mon(dex, "SKARMORY", 50, ["WHIRLWIND"]), mon(dex, "BLISSEY", 50, ["TACKLE"])]
    b = [mon(dex, "DRAGONITE", 50, ["DRAGONDANCE", "OUTRAGE"]), mon(dex, "RATTATA", 50, ["TACKLE"])]
    out = PB.simulate(dex, a, b, seed=4)
    rounds = [e for e in out["events"] if e.get("t") == "round"]
    chk("유저 배틀: 날려버리기로 바뀌면 라운드 이벤트가 더 나온다",
        len(rounds) > sum(1 for e in out["events"] if e.get("t") == "ko") + 1 or any("날려" in (e.get("text") or "") or "끌려" in (e.get("text") or "")
                                                                                   for e in out["events"]),
        [e.get("text") for e in out["events"] if e.get("t") in ("round", "ko", "move")][:20])


def t_싱글에서_실패(dex):
    print("-- 1:1 에서 원작도 실패하는 것")
    bt, me, foe = fight(dex, mon(dex, "CLEFABLE", 50, ["HELPINGHAND", "FOLLOWME", "AFTERYOU", "ALLYSWITCH", "SPLASH"]),
                        mon(dex, "SNORLAX", 50, ["TACKLE"]))
    for k in ("HELPINGHAND", "FOLLOWME", "AFTERYOU", "ALLYSWITCH", "QUASH", "RAGEPOWDER", "AROMATICMIST", "DRAGONCHEER"):
        me.moves = [k]
        me.pp[k] = 10
        chk("%s: 실패" % k, "실패" in texts(use(bt, "me", k)))
    chk("튀어오르기: 아무 일도 없다", "아무 일도" in texts(use(bt, "me", "SPLASH")))


# ---------------------------------------------------------------- 3. 저장·AI·무작위
def t_저장(dex):
    print("-- 저장했다 되살리기")
    party = [mon(dex, "GENGAR", 50, ["CONFUSERAY", "TAUNT", "SUBSTITUTE", "SUNNYDAY"]), mon(dex, "SNORLAX", 50, ["TACKLE"])]
    tb = gym(dex, 50, [mon(dex, "MACHAMP", 50, ["BULKUP", "CROSSCHOP"]), mon(dex, "RATTATA", 50, ["TACKLE"])], party)
    for k in ("SUBSTITUTE", "CONFUSERAY", "SUNNYDAY"):
        ev = []
        tb.bt._use("me", tb.me, tb.foe, k, ev)
    tb.bt.field.side("foe")["spikes"] = 2
    back = TB.TrainerBattle.load(dex, json.loads(json.dumps(tb.dump())))
    chk("대타·혼란이 남는다", back.me.cond.get("sub") and back.foe.cond.get("confused"))
    chk("날씨·압정이 남는다", back.bt.field.weather == "sun" and back.bt.field.side("foe").get("spikes") == 2)
    chk("되살린 판에서도 날씨가 데미지에 반영된다", back.me.field is back.bt.field)


def t_AI(dex):
    print("-- 관장 AI")
    team = [mon(dex, "SKARMORY", 50, ["STEALTHROCK", "DRILLPECK"]), mon(dex, "RATTATA", 50, ["TACKLE"])]
    party = [mon(dex, "SNORLAX", 50, ["TACKLE"]), mon(dex, "PIKACHU", 50, ["TACKLE"]), mon(dex, "EEVEE", 50, ["TACKLE"])]
    tb = gym(dex, 100, team, party)
    chk("상대 파티가 남아 있으면 스텔스록을 깐다", tb._foe_move() == "STEALTHROCK", tb._foe_move())
    tb.bt.field.side("me")["stealthrock"] = 1
    chk("이미 깔려 있으면 안 깐다", tb._foe_move() == "DRILLPECK", tb._foe_move())
    team = [mon(dex, "ALAKAZAM", 50, ["REFLECT", "PSYCHIC"])]
    tb = gym(dex, 100, team, [mon(dex, "MACHAMP", 50, ["CROSSCHOP"])])
    tb.foe.hp = tb.foe.maxhp
    chk("물리형 상대에게 리플렉터", tb._foe_move() in ("REFLECT", "PSYCHIC"))
    tb.bt.field.side("foe")["reflect"] = 3
    chk("리플렉터가 있으면 또 안 쓴다", tb._foe_move() == "PSYCHIC")
    bt, me, foe = fight(dex, mon(dex, "ARCANINE", 50, ["ROAR", "FLAMETHROWER"]), mon(dex, "RATTATA", 50, ["TACKLE"]),
                        rng=random.Random(1))
    picks = collections.Counter(bt.choose_mine() for _ in range(30))
    chk("야생에서 내 자동 전투는 울부짖기(판이 끝난다)를 안 쓴다", not picks["ROAR"], picks)


def t_무작위(dex):
    print("-- 무작위로 섞어 돌리기")
    raw = dex.raw
    status = sorted(SM.HANDLERS)
    status = [k for k in status if k in raw["moves"]]
    learn = sorted(set(k for s in raw["species"] for _lv, k in s.get("moves", [])))
    errors = []
    nondet = 0
    for n in range(120):
        rng = random.Random(n)
        lv = rng.randint(20, 80)

        def mk():
            m = dex.roll_wild(lv, lv, rng)
            m["moves"] = [rng.choice(status), rng.choice(status), rng.choice(status), rng.choice(learn)]
            m["held"] = rng.choice([None, "LEFTOVERS", "SITRUSBERRY", "CHOICESCARF"])
            return m
        try:
            a = [mk() for _ in range(3)]
            b = [mk() for _ in range(3)]
            e1 = PB.simulate(dex, a, b, seed=n)["events"]
            e2 = PB.simulate(dex, a, b, seed=n)["events"]
            nondet += json.dumps(e1, sort_keys=True) != json.dumps(e2, sort_keys=True)
            me, foe = B.Fighter(dex, mk()), B.Fighter(dex, mk())
            bt = B.Battle(dex, me, foe, random.Random(n), ai="wild")
            t = 0
            while not bt.over and t < 60:
                t += 1
                bt.take_turn(bt.choose_mine())
                json.dumps([me.volatile(), foe.volatile(), bt.field.dump()])
        except Exception as e:                                          # noqa: BLE001
            errors.append((n, repr(e)))
    chk("120판: 예외가 없다", not errors, errors[:3])
    chk("유저 배틀: 같은 시드면 같은 로그", nondet == 0, nondet)


def main():
    dex = load_dex()
    for fn in (t_빠진것, t_혼란, t_방어, t_제한, t_시간차, t_헤롱헤롱과_잠김, t_특성과_타입, t_능력, t_회복,
               t_길동무와_튕기기, t_부르기, t_도구, t_날씨, t_필드와_방, t_진영, t_압정과_교체, t_싱글에서_실패,
               t_저장, t_AI, t_무작위):
        fn(dex)
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
