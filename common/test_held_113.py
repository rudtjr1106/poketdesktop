# -*- coding: utf-8 -*-
"""1.13 에 넣은 지닌 도구·폼 검사 — 엔진만. 서버 없이 돈다.

    python common/test_held_113.py

사용자 요청 "아직 미추가된 도구들 전부 구현해서 추가해줘 / 포켓몬들의 폼체인지까지" (2026-10-17).
도구 하나하나가 본가대로 뭔가 하는지, 폼이 타입·특성·종족값·기술을 바꾸는지를 본다. 도구가 없는 판이
그대로인지는 test_held 의 요약값이 본다.
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import battle as B              # noqa: E402
from common import held as H                # noqa: E402
from common import movecalc as MC           # noqa: E402
from common import statusmoves as SM        # noqa: E402
from common import abilities as A           # noqa: E402
from common import test_abilities2 as T     # noqa: E402

OK = FAIL = 0
DEX = T.DEX
mon, use, eot, texts, hits = T.mon, T.use, T.eot, T.texts, T.hits


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def fight(a, b, seed=1, enter=True):
    return T.fight(a, b, seed=seed, enter=enter)


def with_switcher(bt):
    calls = []

    def sw(who, mode, ev, key, state=None):
        calls.append((who, mode))
        return True
    bt.switcher = sw
    return calls


# ---------------------------------------------------------------- 맞는 쪽 도구
def t_hit_items():
    print("-- 맞는 쪽 도구")
    bt, me, foe = fight(mon("SNORLAX", 50, ["TACKLE", "SHADOWBALL"]), mon("SNORLAX", 50, ["TACKLE"], held="ROCKYHELMET"))
    hp = me.hp
    use(bt, "me", "TACKLE")
    chk("울퉁불퉁멧: 닿는 기술로 때리면 최대 HP 1/6", hp - me.hp == me.maxhp // 6, (hp, me.hp, me.maxhp))
    hp = me.hp
    use(bt, "me", "SHADOWBALL")
    chk("  안 닿는 기술은 안 다친다", me.hp == hp)
    bt, me, foe = fight(mon("SNORLAX", 50, ["TACKLE"], held="PROTECTIVEPADS"),
                        mon("SNORLAX", 50, ["TACKLE"], held="ROCKYHELMET"))
    hp = me.hp
    use(bt, "me", "TACKLE")
    chk("  방호패드를 끼면 안 다친다", me.hp == hp)

    bt, me, foe = fight(mon("SNORLAX", 50, ["ICEBEAM"]), mon("GARCHOMP", 50, ["TACKLE"], held="WEAKNESSPOLICY"))
    use(bt, "me", "ICEBEAM")
    chk("약점보험: 굉장한 기술에 맞으면 공격·특수공격 +2 (한 번)",
        foe.stages["atk"] == 2 and foe.stages["spa"] == 2 and foe.used, (foe.stages, foe.used))

    for item, mv, stat in (("ABSORBBULB", "WATERGUN", "spa"), ("CELLBATTERY", "THUNDERSHOCK", "atk"),
                           ("LUMINOUSMOSS", "WATERGUN", "spd"), ("SNOWBALL", "ICEBEAM", "atk"),
                           ("KEEBERRY", "TACKLE", "def"), ("MARANGABERRY", "WATERGUN", "spd")):
        bt, me, foe = fight(mon("SNORLAX", 50, [mv]), mon("SNORLAX", 50, ["TACKLE"], held=item))
        use(bt, "me", mv)
        chk("%s: 맞으면 %s +1 (한 번)" % (H.name(item), stat), foe.stages[stat] == 1 and foe.used, foe.stages)

    bt, me, foe = fight(mon("SNORLAX", 50, ["EARTHQUAKE", "TACKLE"]), mon("SNORLAX", 50, ["TACKLE"], held="AIRBALLOON"))
    chk("풍선: 나오면 떠 있다고 알린다", "풍선" in texts(bt.entry), texts(bt.entry))
    ev = use(bt, "me", "EARTHQUAKE")
    chk("  땅 기술이 안 맞는다", not hits(ev), texts(ev))
    use(bt, "me", "TACKLE")
    ev = use(bt, "me", "EARTHQUAKE")
    chk("  다른 기술에 맞으면 터지고, 그 뒤로는 땅 기술이 맞는다", foe.used and hits(ev), texts(ev))


def t_switch_items():
    print("-- 교체 도구 (교체할 포켓몬이 있는 배틀에서만)")
    bt, me, foe = fight(mon("SNORLAX", 50, ["TACKLE"]), mon("SNORLAX", 50, ["TACKLE"], held="EJECTBUTTON"))
    calls = with_switcher(bt)
    use(bt, "me", "TACKLE")
    chk("탈출버튼: 맞으면 그쪽이 물러난다", calls == [("foe", "out")], calls)
    bt, me, foe = fight(mon("SNORLAX", 50, ["TACKLE"]), mon("SNORLAX", 50, ["TACKLE"], held="REDCARD"))
    calls = with_switcher(bt)
    use(bt, "me", "TACKLE")
    chk("레드카드: 때린 쪽이 끌려 나간다", calls == [("me", "drag")], calls)
    bt, me, foe = fight(mon("SNORLAX", 50, ["GROWL"]), mon("SNORLAX", 50, ["TACKLE"], held="EJECTPACK"))
    calls = with_switcher(bt)
    use(bt, "me", "GROWL")
    chk("탈출팩: 능력이 떨어지면 물러난다", calls == [("foe", "out")], calls)
    bt, me, foe = fight(mon("SNORLAX", 50, ["TACKLE"]), mon("SNORLAX", 50, ["TACKLE"], held="EJECTBUTTON"))
    use(bt, "me", "TACKLE")
    chk("  야생(교체기가 없다)에서는 아무 일도 없다 (판이 안 끝난다)", not bt.over and not foe.used, (bt.over, foe.used))


def t_status_items():
    print("-- 상태·능력 도구")
    bt, me, foe = fight(mon("SNORLAX", 50, ["TACKLE", "GROWL"], held="ASSAULTVEST"), mon("SNORLAX", 50, ["TACKLE"]))
    base = B.Fighter(DEX, mon("SNORLAX", 50, ["TACKLE"])).stat("spd")
    chk("돌격조끼: 특수방어 1.5배", me.stat("spd") == int(base * 1.5), (me.stat("spd"), base))
    chk("  변화기를 못 쓴다", SM.restricted(bt, me, "GROWL") and "GROWL" not in bt.usable(me),
        SM.restricted(bt, me, "GROWL"))
    pichu = B.Fighter(DEX, mon("PICHU", 50, held="EVIOLITE"))
    raw = B.Fighter(DEX, mon("PICHU", 50))
    chk("진화의휘석: 진화 전이면 방어 1.5배", pichu.stat("def") == int(raw.stat("def") * 1.5))
    snor = B.Fighter(DEX, mon("SNORLAX", 50, held="EVIOLITE"))
    chk("  다 진화했으면 그대로", snor.stat("def") == B.Fighter(DEX, mon("SNORLAX", 50)).stat("def"))

    bt, me, foe = fight(mon("SNORLAX", 50, ["ICYWIND"]), mon("SNORLAX", 50, ["TACKLE"], held="COVERTCLOAK"))
    use(bt, "me", "ICYWIND")
    chk("은밀망토: 추가 효과(스피드 하락 100%)를 안 받는다", foe.stages["spe"] == 0, foe.stages)
    bt, me, foe = fight(mon("SNORLAX", 50, ["GROWL"]), mon("SNORLAX", 50, ["TACKLE"], held="CLEARAMULET"))
    use(bt, "me", "GROWL")
    chk("클리어참: 상대가 떨어뜨리는 능력 하락을 막는다", foe.stages["atk"] == 0, foe.stages)
    bt, me, foe = fight(mon("GYARADOS", 50, ["TACKLE"], ability="INTIMIDATE"),
                        mon("SNORLAX", 50, ["TACKLE"], held="ADRENALINEORB"))
    chk("주눅구슬: 위협을 받으면 스피드 +1", foe.stages["spe"] == 1 and foe.used, foe.stages)
    bt, me, foe = fight(mon("SNORLAX", 50, ["SWORDSDANCE"]), mon("SNORLAX", 50, ["TACKLE"], held="MIRRORHERB"))
    use(bt, "me", "SWORDSDANCE")
    chk("흉내허브: 상대가 올린 만큼 따라 올린다", foe.stages["atk"] == 2 and foe.used, foe.stages)
    bt, me, foe = fight(mon("SNORLAX", 50, ["HYPERVOICE"], held="THROATSPRAY"), mon("SNORLAX", 50))
    use(bt, "me", "HYPERVOICE")
    chk("목스프레이: 소리 기술을 쓰면 특수공격 +1", me.stages["spa"] == 1 and me.used, me.stages)
    bt, me, foe = fight(mon("SNORLAX", 50, ["TACKLE"], held="BLUNDERPOLICY"), mon("SNORLAX", 50))
    real = B.accuracy_check
    B.accuracy_check = lambda *a, **k: False
    try:
        use(bt, "me", "TACKLE")
    finally:
        B.accuracy_check = real
    chk("허탕보험: 빗나가면 스피드 +2", me.stages["spe"] == 2 and me.used, me.stages)
    bt, me, foe = fight(mon("SNORLAX", 50, ["TRICKROOM"]), mon("SNORLAX", 50, held="ROOMSERVICE"))
    use(bt, "me", "TRICKROOM")
    chk("룸서비스: 트릭룸이 깔리면 스피드 -1", foe.stages["spe"] == -1 and foe.used, foe.stages)
    bt, me, foe = fight(mon("GREATTUSK", 50, ["TACKLE"], held="BOOSTERENERGY", ability="PROTOSYNTHESIS"),
                        mon("SNORLAX", 50))
    chk("부스트에너지: 햇살 없이도 고대활성이 켜진다",
        me.cond.get("booster") and me.used and A.stat_mult(me, "atk") > 1.0, (me.cond, texts(bt.entry)))
    bt, me, foe = fight(mon("SNORLAX", 50, ["TAUNT"]), mon("SNORLAX", 50, ["TACKLE"], held="MENTALHERB"))
    use(bt, "me", "TAUNT")
    chk("멘탈허브: 도발이 바로 풀린다", not foe.cond.get("taunt") and foe.used, foe.cond)
    bt, me, foe = fight(mon("SNORLAX", 50, ["CONFUSERAY"]), mon("SNORLAX", 50, ["TACKLE"], held="PERSIMBERRY"))
    use(bt, "me", "CONFUSERAY")
    chk("시몬열매: 혼란이 바로 풀린다", not foe.cond.get("confused") and foe.used, foe.cond)
    bt, me, foe = fight(mon("SNORLAX", 50, ["ATTRACT"], gender="M"),
                        mon("SNORLAX", 50, ["TACKLE"], held="DESTINYKNOT", gender="F"))
    use(bt, "me", "ATTRACT")
    chk("빨간실: 헤롱헤롱하면 상대도 헤롱헤롱", foe.cond.get("attract") and me.cond.get("attract"),
        (foe.cond, me.cond))
    bt, me, foe = fight(mon("SNORLAX", 50, ["TACKLE"]), mon("GENGAR", 50, held="RINGTARGET"))
    ev = use(bt, "me", "TACKLE")
    chk("겨냥표적: 효과가 없던 기술(노말 → 고스트)이 맞는다", hits(ev), texts(ev))
    bt, me, foe = fight(mon("SNORLAX", 50, ["SPORE"]), mon("SNORLAX", 50, held="SAFETYGOGGLES"))
    use(bt, "me", "SPORE")
    chk("방진고글: 가루·포자 기술이 안 통한다", foe.status != "sleep", foe.status)


def t_field_items():
    print("-- 날씨·필드·벽·구속·압정")
    for item, mv, w in (("DAMPROCK", "RAINDANCE", "rain"), ("SMOOTHROCK", "SANDSTORM", "sand")):
        bt, me, foe = fight(mon("SNORLAX", 50, [mv], held=item), mon("SNORLAX", 50))
        use(bt, "me", mv)
        chk("%s: 날씨 8턴" % H.name(item), bt.field.weather == w and bt.field.weather_turns == 8, bt.field.weather_turns)
    bt, me, foe = fight(mon("SNORLAX", 50, ["RAINDANCE"]), mon("SNORLAX", 50))
    use(bt, "me", "RAINDANCE")
    chk("  바위가 없으면 5턴", bt.field.weather_turns == 5)
    bt, me, foe = fight(mon("SNORLAX", 50, ["ELECTRICTERRAIN"], held="TERRAINEXTENDER"),
                        mon("SNORLAX", 50, held="ELECTRICSEED"))
    use(bt, "me", "ELECTRICTERRAIN")
    chk("그라운드코트: 필드 8턴", bt.field.terrain_turns == 8)
    chk("일렉트릭시드: 일렉트릭필드가 깔리면 방어 +1", foe.stages["def"] == 1 and foe.used, foe.stages)
    bt, me, foe = fight(mon("SNORLAX", 50, ["REFLECT"], held="LIGHTCLAY"), mon("SNORLAX", 50))
    use(bt, "me", "REFLECT")
    chk("빛의점토: 리플렉터 8턴", bt.field.side("me").get("reflect") == 8, bt.field.side("me"))
    bt, me, foe = fight(mon("SNORLAX", 50, ["WRAP"], held="GRIPCLAW"), mon("SNORLAX", 50))
    for _ in range(5):
        use(bt, "me", "WRAP")
        if foe.cond.get("bound"):
            break
    ticks = 0
    for _ in range(12):
        hp = foe.hp
        eot(bt)
        ticks += hp > foe.hp
        if not foe.cond.get("bound"):
            break
    chk("끈기갈고리손톱: 조이기 데미지 7번 (본가와 같다)", ticks == 7, ticks)
    bt, me, foe = fight(mon("SNORLAX", 50, ["WRAP"], held="BINDINGBAND"), mon("SNORLAX", 50))
    for _ in range(5):
        use(bt, "me", "WRAP")
        if foe.cond.get("bound"):
            break
    hp = foe.hp
    eot(bt)
    chk("조임밴드: 조임 데미지 1/6", hp - foe.hp == int(foe.maxhp / 6.0) or hp - foe.hp == foe.maxhp // 6,
        (hp - foe.hp, foe.maxhp))
    bt, me, foe = fight(mon("SNORLAX", 50, held="HEAVYDUTYBOOTS"), mon("SNORLAX", 50))
    bt.field.side("me")["stealthrock"] = True
    hp = me.hp
    SM.enter(bt, "me", [])
    chk("통굽부츠: 스텔스록을 안 밟는다", me.hp == hp)
    bt, me, foe = fight(mon("SNORLAX", 50, ["SANDSTORM"]), mon("SNORLAX", 50, held="SAFETYGOGGLES"))
    use(bt, "me", "SANDSTORM")
    hp_me, hp_foe = me.hp, foe.hp
    eot(bt)
    chk("방진고글: 모래바람 데미지를 안 받는다", foe.hp == hp_foe and me.hp < hp_me, (foe.hp, hp_foe, me.hp, hp_me))
    bt, me, foe = fight(mon("SNORLAX", 50, held="SHEDSHELL"), mon("SNORLAX", 50))
    me.cond["trapped"] = "foe"
    chk("아름다운허물: 붙잡혀 있어도 바꿀 수 있다", not SM.trapped(bt, me))
    light = B.Fighter(DEX, mon("SNORLAX", 50, held="FLOATSTONE"))
    chk("가벼운돌: 몸무게 절반", MC.kg(light) == round(MC.kg(B.Fighter(DEX, mon("SNORLAX", 50))) / 2.0, 1),
        MC.kg(light))


def t_power_items():
    print("-- 위력·급소·연속기")
    bt, me, foe = fight(mon("SNORLAX", 50, ["FLAMETHROWER"], held="FIREGEM"), mon("SNORLAX", 50))
    ev = use(bt, "me", "FLAMETHROWER")
    chk("불꽃주얼: 처음 쓸 때 알리고 사라진다", "불꽃주얼" in texts(ev) and me.used, texts(ev))
    plain = B.Fighter(DEX, mon("SNORLAX", 50, ["FLAMETHROWER"]))
    m = dict(DEX.move("FLAMETHROWER"), _gem=True)
    gem_user = B.Fighter(DEX, mon("SNORLAX", 50, ["FLAMETHROWER"], held="FIREGEM"))
    tgt = B.Fighter(DEX, mon("SNORLAX", 50))
    a = B.damage(DEX, m, gem_user, tgt, random.Random(3), crit=False)[0]
    b = B.damage(DEX, DEX.move("FLAMETHROWER"), plain, tgt, random.Random(3), crit=False)[0]
    chk("  위력 1.3배", abs(a / float(b) - 1.3) < 0.05, (a, b))
    pika = B.Fighter(DEX, mon("PIKACHU", 50, held="LIGHTBALL"))
    chk("전기구슬: 피카츄 공격·특수공격 2배", pika.stat("spa") == B.Fighter(DEX, mon("PIKACHU", 50)).stat("spa") * 2)
    rai = B.Fighter(DEX, mon("RAICHU", 50, held="LIGHTBALL"))
    chk("  라이츄는 그대로", rai.stat("spa") == B.Fighter(DEX, mon("RAICHU", 50)).stat("spa"))
    chk("럭키펀치: 럭키 급소 +2", H.crit_stages(B.Fighter(DEX, mon("CHANSEY", 50, held="LUCKYPUNCH"))) == 2)
    lat = B.Fighter(DEX, mon("LATIOS", 50, ["DRACOMETEOR"], held="SOULDEW"))
    chk("마음의물방울: 라티오스의 드래곤 1.2배", abs(H.damage_mult(lat, DEX.move("DRACOMETEOR"), 1.0) - 1.2) < 1e-6)
    chk("요정의깃털·정령플레이트: 페어리 1.2배",
        abs(H.damage_mult(B.Fighter(DEX, mon("SNORLAX", 50, held="FAIRYFEATHER")), DEX.move("DAZZLINGGLEAM"), 1.0) - 1.2) < 1e-6
        and MC.PLATE_TYPE.get("PIXIEPLATE") == "FAIRY")
    bt, me, foe = fight(mon("SNORLAX", 50, ["BULLETSEED"], held="LOADEDDICE"), mon("SNORLAX", 50))
    counts = set()
    for seed in range(8):
        bt.rng = random.Random(seed)
        foe.hp = foe.maxhp
        ev = use(bt, "me", "BULLETSEED")
        counts.add(len(hits(ev)))
    chk("속임수주사위: 2~5번 기술이 4~5번", counts <= {4, 5} and counts, counts)
    sil = B.Fighter(DEX, mon("SILVALLY", 50, ["MULTIATTACK"], held="FIREMEMORY"))
    from common import attackfx as AF
    chk("파이어메모리: 실버디의 멀티어택이 불꽃", AF.move_type(DEX.move("MULTIATTACK"), sil) == "FIRE")
    gen = B.Fighter(DEX, mon("GENESECT", 50, ["TECHNOBLAST"], held="CHILLDRIVE"))
    chk("프리즈카세트: 테크노버스터가 얼음", AF.move_type(DEX.move("TECHNOBLAST"), gen) == "ICE")
    bt, me, foe = fight(mon("SNORLAX", 50, ["SOLARBEAM"], held="POWERHERB"), mon("SNORLAX", 50))
    ev = use(bt, "me", "SOLARBEAM")
    chk("파워풀허브: 솔라빔이 한 턴에 나간다 (지닐 수 있게 됐다)", hits(ev) and me.used, texts(ev))


def t_forms():
    print("-- 폼")
    gi = B.Fighter(DEX, mon("GIRATINA", 50, ["SHADOWBALL"], held="GRISEOUSCORE"))
    chk("큰백금옥: 기라티나 오리진폼 (특성 부유, 공격 종족값 120)",
        gi.species["internal"] == "GIRATINA_ORIGIN" and gi.ability == "LEVITATE"
        and gi.species["num"] == 10007, (gi.species.get("internal"), gi.ability))
    chk("  지니지 않으면 어나더폼", B.Fighter(DEX, mon("GIRATINA", 50)).species["internal"] == "GIRATINA")
    za = B.Fighter(DEX, mon("ZACIAN", 70, ["IRONHEAD"], held="RUSTEDSWORD"))
    chk("녹슨검: 검왕 자시안, 아이언헤드가 거수참", za.species["internal"] == "ZACIAN_CROWNED"
        and za.moves == ["BEHEMOTHBLADE"] and za.alias.get("IRONHEAD") == "BEHEMOTHBLADE", (za.moves, za.alias))
    # 불굴의검·불요의방패: 한 판에 한 번 (본가 9세대, 2026-10-17 사용자 결정)
    bt, me, foe = fight(mon("ZACIAN", 70, ["IRONHEAD"], held="RUSTEDSWORD", ability="INTREPIDSWORD"),
                        mon("ZAMAZENTA", 70, ["IRONHEAD"], held="RUSTEDSHIELD", ability="DAUNTLESSSHIELD"))
    chk("불굴의검 · 불요의방패: 처음 나오면 공격 · 방어 +1", me.stages["atk"] == 1 and foe.stages["def"] == 1,
        (me.stages["atk"], foe.stages["def"]))
    for f, who in ((me, "me"), (foe, "foe")):
        f.clear_volatile()
        f.stages = dict((k, 0) for k in f.stages)            # 물러나면 랭크는 풀린다
        A.on_switch_in(bt, f, who, [])
    chk("  물러났다 다시 나오면 안 오른다 (8세대처럼 매번 오르지 않는다)",
        me.stages["atk"] == 0 and foe.stages["def"] == 0, (me.stages["atk"], foe.stages["def"]))
    again = B.Fighter(DEX, mon("ZACIAN", 70, ["IRONHEAD"], ability="INTREPIDSWORD"))
    again.ability_on = True
    A.load(again, A.state(me))                               # 관장 · 실시간 판은 턴마다 저장했다 다시 읽는다
    A.on_switch_in(bt, again, "me", [])
    chk("  저장했다 다시 읽어도 한 번 쓴 것을 기억한다", again.stages["atk"] == 0, again.stages["atk"])
    og = B.Fighter(DEX, mon("OGERPON", 50, ["IVYCUDGEL"], held="WELLSPRINGMASK"))
    from common import attackfx as AF
    chk("우물의가면: 오거폰 풀/물, 특성 저수, 덩굴방망이 물", og.types() == ["GRASS", "WATER"]
        and og.ability == "WATERABSORB" and AF.move_type(DEX.move("IVYCUDGEL"), og) == "WATER",
        (og.types(), og.ability))
    chk("  가면은 기술 위력 1.2배", abs(H.damage_mult(og, DEX.move("IVYCUDGEL"), 1.0) - 1.2) < 1e-6)
    # 기술 단추에 적는 타입 (1.13.1, 게시판 #259 '화덕의가면 오거폰의 덩굴방망이가 풀로 보인다')
    hearth = B.Fighter(DEX, mon("OGERPON", 50, ["IVYCUDGEL"], held="HEARTHFLAMEMASK"))
    chk("기술 단추 타입: 화덕의가면 덩굴방망이는 불꽃 (도감 타입 풀이 아니라)",
        B.shown_type(DEX.move("IVYCUDGEL"), hearth) == "FIRE", B.shown_type(DEX.move("IVYCUDGEL"), hearth))
    chk("  플레이트를 지닌 아르세우스의 심판의뭉치는 플레이트 타입",
        B.shown_type(DEX.move("JUDGMENT"), B.Fighter(DEX, mon("ARCEUS", 50, ["JUDGMENT"], held="FLAMEPLATE")))
        == "FIRE")
    chk("  가면이 없으면 풀 그대로", B.shown_type(DEX.move("IVYCUDGEL"),
                                         B.Fighter(DEX, mon("OGERPON", 50, ["IVYCUDGEL"]))) == "GRASS")
    from common import trainer_battle as TB
    gym = {"id": "t", "name": "t", "role": "t", "sprite": None, "level": 5,
           "team": [{"species": "MAGIKARP", "level": 5, "moves": ["SPLASH"]}]}
    tb = TB.TrainerBattle(DEX, [mon("OGERPON", 50, ["IVYCUDGEL"], held="HEARTHFLAMEMASK")], gym, random.Random(1))
    tb.start()
    btn = [m for m in tb.view()["me"]["team"][0]["moves"] if m["key"] == "IVYCUDGEL"][0]
    chk("  관장 배틀 창의 기술 단추에도 불꽃으로 간다", btn["type"] == "FIRE" and btn["typeKr"] == DEX.type_name("FIRE"),
        btn)
    sky = mon("SHAYMIN", 50)
    sky["form"] = "SKY"
    f = B.Fighter(DEX, sky)
    chk("스카이폼(써서 바꾼 폼): 풀/비행", f.types() == ["GRASS", "FLYING"] and f.species["num"] == 10006, f.types())
    bt, me, foe = fight(mon("SNORLAX", 50, ["TRICK"], held="CHOICESCARF"),
                        mon("OGERPON", 50, ["TACKLE"], held="WELLSPRINGMASK"))
    ev = use(bt, "me", "TRICK")
    chk("가면은 트릭으로 못 뺏는다", foe._held == "WELLSPRINGMASK", texts(ev))
    chk("플레이트는 아르세우스가 지녔을 때만 잠긴다",
        H.stuck("FLAMEPLATE", B.Fighter(DEX, mon("ARCEUS", 50, held="FLAMEPLATE")))
        and not H.stuck("FLAMEPLATE", B.Fighter(DEX, mon("SNORLAX", 50, held="FLAMEPLATE"))))
    # 원시회귀
    bt, me, foe = fight(mon("KYOGRE", 60, ["SURF"], held="BLUEORB"), mon("SNORLAX", 50, ["FLAMETHROWER"]))
    chk("쪽빛구슬: 가이오가가 나오면 원시회귀 (시작의바다)",
        me.mega == "KYOGRE_PRIMAL" and me.ability == "PRIMORDIALSEA", (me.mega, me.ability, texts(bt.entry)))
    chk("  원시회귀 사건에 '원시회귀!' 가 실린다", any(e.get("label") == "원시회귀!" for e in bt.entry))
    chk("  강한 비", bt.weather() == "rain" and SM.weather(foe) == "rain")
    ev = use(bt, "foe", "FLAMETHROWER")
    chk("  불꽃 공격이 사라진다", not hits(ev) and "사라졌다" in texts(ev), texts(ev))
    bt, me, foe = fight(mon("GROUDON", 50, ["PRECIPICEBLADES"], held="REDORB"), mon("BLASTOISE", 50, ["SURF", "BITE"]))
    chk("  AI 는 사라질 기술을 안 고른다 (끝의대지에 파도타기 대신 물기)",
        bt.choose_for(foe, me, "trainer") == "BITE" and bt.estimate(foe, me, "SURF") == 0,
        (bt.choose_for(foe, me, "trainer"), bt.estimate(foe, me, "SURF")))
    bt, me, foe = fight(mon("GROUDON", 50, ["PRECIPICEBLADES"]), mon("BLASTOISE", 50, ["SURF", "BITE"]))
    chk("  원시회귀가 아니면 그대로 파도타기", bt.choose_for(foe, me, "trainer") == "SURF")
    # 배틀 중 폼
    bt, me, foe = fight(mon("DARMANITAN", 50, ["FLAMETHROWER"], ability="ZENMODE"), mon("SNORLAX", 50))
    me.hp = me.maxhp // 3
    ev = eot(bt)
    chk("달마모드: 도트 번호(look)가 실린다", any(e.get("look") == 10017 for e in ev), [e for e in ev if e.get("form")])
    bt, me, foe = fight(mon("GRENINJA", 60, ["DARKPULSE"], ability="BATTLEBOND"), mon("CATERPIE", 5))
    use(bt, "me", "DARKPULSE")
    chk("유대변화: 쓰러뜨리면 지우개굴닌자", me.cond.get("form") == "ash" and me.cond.get("look") == 10117, me.cond)
    from common import attackfx as AF2
    chk("  지우개굴닌자의 물수리검: 위력 20", AF2.power("WATERSHURIKEN", 15, DEX.move("WATERSHURIKEN"), me, foe) == 20)
    bt, me, foe = fight(mon("GRENINJA", 60, ["WATERSHURIKEN"], ability="BATTLEBOND"), mon("SNORLAX", 80))
    me.ab["ash"] = True
    ev = use(bt, "me", "WATERSHURIKEN")
    chk("  늘 3번 친다", len(hits(ev)) == 3, hits(ev))
    bt, me, foe = fight(mon("ZYGARDE", 60, ["THOUSANDARROWS"], ability="POWERCONSTRUCT"), mon("SNORLAX", 50))
    mx = me.maxhp
    me.hp = mx // 2
    eot(bt)
    chk("스웜체인지: 체력 절반 이하면 퍼펙트폼, 최대 체력이 오른다",
        me.cond.get("form") == "complete" and me.maxhp > mx, (me.cond.get("form"), mx, me.maxhp))


def main():
    t_hit_items()
    t_switch_items()
    t_status_items()
    t_field_items()
    t_power_items()
    t_forms()
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
