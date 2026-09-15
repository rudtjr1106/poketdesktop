# -*- coding: utf-8 -*-
"""특성 — 배틀 안에서 무엇을 하는지.

## 켜는 판과 안 켜는 판

**Fighter.ability_on 이 True 인 판에서만** 여기 있는 것이 돈다. 지금은 관장
도전(trainer_battle)만 켠다. 야생·PvP 는 끈 채로 둔다 - 끄면 이 파일은
아무것도 하지 않고 난수도 안 쓰므로, 예전 판의 로그가 한 글자도 안
달라진다(common/test_held.py 의 요약값이 그걸 지킨다).

## 무엇을 넣었나

날씨와 필드는 엔진에 없다(사용자가 빼기로 했다). 그래서 날씨를 부르거나
날씨에 기대는 특성(가뭄·잔비·쓱쓱·엽록소·모래숨기 ...)은 **아무 일도 안
한다.** 교체·더블배틀·도구 뺏기처럼 이 엔진에 없는 개념에 걸린 것도 뺐다.
IMPLEMENTED 에 들어 있는 것만 동작한다.

## 규칙

  · 각 훅은 먼저 특성이 켜져 있는지 보고, 아니면 바로 돌아간다.
  · 틀깨기(MOLDBREAKER 류)를 쓰는 쪽이 때릴 때는 **맞는 쪽의 방어 특성**을
    무시한다. 무시할 수 없는 것(스펙터가드·프리즘아머·메탈프로텍트)은 따로 둔다.
  · 특성이 발동하면 {"t": "ability"} 이벤트를 먼저 낸다. 화면이 "[갸라도스의
    위협]" 처럼 띄운다.
"""
from . import movecalc as MC

MOLD_BREAKERS = {"MOLDBREAKER", "TERAVOLT", "TURBOBLAZE"}

# 틀깨기로 무시되는 방어 특성
IGNORABLE = {
    "LEVITATE", "FLASHFIRE", "WATERABSORB", "VOLTABSORB", "LIGHTNINGROD", "STORMDRAIN",
    "MOTORDRIVE", "SAPSIPPER", "DRYSKIN", "EARTHEATER", "WELLBAKEDBODY", "WINDRIDER",
    "BULLETPROOF", "SOUNDPROOF", "OVERCOAT", "WONDERGUARD", "GOODASGOLD", "THICKFAT",
    "HEATPROOF", "WATERBUBBLE", "PURIFYINGSALT", "FILTER", "SOLIDROCK", "MULTISCALE",
    "FLUFFY", "ICESCALES", "PUNKROCK", "FURCOAT", "MARVELSCALE", "STURDY", "DISGUISE",
    "BATTLEARMOR", "SHELLARMOR", "CLEARBODY", "WHITESMOKE", "HYPERCUTTER", "BIGPECKS",
    "KEENEYE", "CONTRARY", "SIMPLE", "UNAWARE", "LIMBER", "INSOMNIA", "VITALSPIRIT",
    "IMMUNITY", "WATERVEIL", "MAGMAARMOR", "INNERFOCUS", "SHIELDDUST", "WONDERSKIN",
    "SWEETVEIL", "PASTELVEIL", "THERMALEXCHANGE", "MINDSEYE",
}

# 트레이스로 못 베끼는 것
UNTRACEABLE = {"TRACE", "MULTITYPE", "STANCECHANGE", "SCHOOLING", "COMATOSE", "SHIELDSDOWN",
               "DISGUISE", "RKSSYSTEM", "BATTLEBOND", "POWERCONSTRUCT", "ICEFACE",
               "GULPMISSILE", "NEUTRALIZINGGAS", "HUNGERSWITCH", "ZEROTOHERO", "COMMANDER",
               "PROTOSYNTHESIS", "QUARKDRIVE", "WONDERGUARD", "IMPOSTER", "ILLUSION",
               "FLOWERGIFT", "FORECAST", "ZENMODE", "RECEIVER", "POWEROFALCHEMY"}

# 도감의 기술 flags 에 없는 구분 (9세대 기준)
SLICING = {"AERIALACE", "AIRCUTTER", "AIRSLASH", "AQUACUTTER", "BEHEMOTHBLADE", "BITTERBLADE",
           "CEASELESSEDGE", "CROSSPOISON", "CUT", "FURYCUTTER", "KOWTOWCLEAVE", "LEAFBLADE",
           "MIGHTYCLEAVE", "NIGHTSLASH", "POPULATIONBOMB", "PSYBLADE", "PSYCHOCUT", "RAZORLEAF",
           "RAZORSHELL", "SACREDSWORD", "SECRETSWORD", "SLASH", "SOLARBLADE", "STONEAXE",
           "TACHYONCUTTER", "XSCISSOR"}
WIND = {"AIRCUTTER", "BLEAKWINDSTORM", "BLIZZARD", "FAIRYWIND", "GUST", "HEATWAVE", "HURRICANE",
        "ICYWIND", "PETALBLIZZARD", "SANDSEARSTORM", "SANDSTORM", "SPRINGTIDESTORM", "TAILWIND",
        "TWISTER", "WHIRLWIND", "WILDBOLTSTORM"}

ATE = {"PIXILATE": "FAIRY", "AERILATE": "FLYING", "REFRIGERATE": "ICE", "GALVANIZE": "ELECTRIC"}
PINCH = {"BLAZE": "FIRE", "TORRENT": "WATER", "OVERGROW": "GRASS", "SWARM": "BUG"}
TYPE_BOOST = {"STEELWORKER": ("STEEL", 1.5), "STEELYSPIRIT": ("STEEL", 1.5),
              "TRANSISTOR": ("ELECTRIC", 1.3), "DRAGONSMAW": ("DRAGON", 1.5),
              "ROCKYPAYLOAD": ("ROCK", 1.5), "WATERBUBBLE": ("WATER", 2.0)}
FLAG_BOOST = {"IRONFIST": ("punch", 1.2), "STRONGJAW": ("bite", 1.5),
              "MEGALAUNCHER": ("pulse", 1.5), "TOUGHCLAWS": ("contact", 1.3),
              "PUNKROCK": ("sound", 1.3)}

# (특성, 흡수하는 타입, 하는 일)
ABSORB = {
    "WATERABSORB": ("WATER", "heal"), "DRYSKIN": ("WATER", "heal"),
    "VOLTABSORB": ("ELECTRIC", "heal"), "EARTHEATER": ("GROUND", "heal"),
    "LIGHTNINGROD": ("ELECTRIC", ("spa", 1)), "STORMDRAIN": ("WATER", ("spa", 1)),
    "MOTORDRIVE": ("ELECTRIC", ("spe", 1)), "SAPSIPPER": ("GRASS", ("atk", 1)),
    "WELLBAKEDBODY": ("FIRE", ("def", 2)), "FLASHFIRE": ("FIRE", "flash"),
    "LEVITATE": ("GROUND", "immune"),
}
STATUS_IMMUNE = {
    "LIMBER": {"paralysis"}, "INSOMNIA": {"sleep"}, "VITALSPIRIT": {"sleep"},
    "SWEETVEIL": {"sleep"}, "IMMUNITY": {"poison"}, "PASTELVEIL": {"poison"},
    "WATERVEIL": {"burn"}, "WATERBUBBLE": {"burn"}, "THERMALEXCHANGE": {"burn"},
    "MAGMAARMOR": {"freeze"},
    "COMATOSE": {"burn", "paralysis", "poison", "sleep", "freeze"},
    "PURIFYINGSALT": {"burn", "paralysis", "poison", "sleep", "freeze"},
}
BLOCK_DROPS = {"CLEARBODY": None, "WHITESMOKE": None, "FULLMETALBODY": None,
               "HYPERCUTTER": "atk", "BIGPECKS": "def", "KEENEYE": "acc",
               "MINDSEYE": "acc", "ILLUMINATE": "acc"}
INTIMIDATE_IMMUNE = {"CLEARBODY", "WHITESMOKE", "FULLMETALBODY", "HYPERCUTTER",
                     "INNERFOCUS", "OBLIVIOUS", "OWNTEMPO", "SCRAPPY"}

IMPLEMENTED = (
    set(MOLD_BREAKERS) | set(ATE) | set(PINCH) | set(TYPE_BOOST) | set(FLAG_BOOST)
    | set(ABSORB) | set(STATUS_IMMUNE) | set(BLOCK_DROPS)
    | {"INTIMIDATE", "DOWNLOAD", "TRACE", "INTREPIDSWORD", "DAUNTLESSSHIELD", "PRESSURE",
       "UNNERVE", "SLOWSTART", "SUPREMEOVERLORD", "REGENERATOR", "NATURALCURE",
       "HUGEPOWER", "PUREPOWER", "GUTS", "HUSTLE", "GORILLATACTICS", "MARVELSCALE",
       "FURCOAT", "QUICKFEET", "UNBURDEN", "PRANKSTER", "GALEWINGS", "TRIAGE",
       "COMPOUNDEYES", "VICTORYSTAR", "NOGUARD", "WONDERSKIN", "UNAWARE",
       "SUPERLUCK", "BATTLEARMOR", "SHELLARMOR", "MERCILESS", "SNIPER",
       "NORMALIZE", "LIQUIDVOICE", "ADAPTABILITY", "PROTEAN", "LIBERO",
       "TECHNICIAN", "SHARPNESS", "RECKLESS", "SHEERFORCE", "TINTEDLENS", "ANALYTIC",
       "TOXICBOOST", "FLAREBOOST", "NEUROFORCE", "ELECTROMORPHOSIS", "WINDPOWER",
       "THICKFAT", "HEATPROOF", "PURIFYINGSALT", "FILTER", "SOLIDROCK", "PRISMARMOR",
       "MULTISCALE", "SHADOWSHIELD", "FLUFFY", "ICESCALES", "SCRAPPY",
       "BULLETPROOF", "SOUNDPROOF", "OVERCOAT", "WONDERGUARD", "GOODASGOLD", "WINDRIDER",
       "STATIC", "FLAMEBODY", "POISONPOINT", "EFFECTSPORE", "ROUGHSKIN", "IRONBARBS",
       "GOOEY", "TANGLINGHAIR", "MUMMY", "LINGERINGAROMA", "POISONTOUCH", "STAMINA",
       "WEAKARMOR", "JUSTIFIED", "RATTLED", "WATERCOMPACTION", "STEAMENGINE",
       "ANGERPOINT", "COTTONDOWN", "BERSERK", "ANGERSHELL", "STURDY", "DISGUISE",
       "MOXIE", "CHILLINGNEIGH", "GRIMNEIGH", "BEASTBOOST", "SYNCHRONIZE", "EARLYBIRD",
       "CORROSION", "CONTRARY", "SIMPLE", "MIRRORARMOR", "DEFIANT", "COMPETITIVE",
       "SERENEGRACE", "SHIELDDUST", "INNERFOCUS", "STEADFAST", "STENCH", "SKILLLINK",
       "ROCKHEAD", "MAGICGUARD", "SPEEDBOOST", "POISONHEAL", "SHEDSKIN", "MOODY",
       "GUARDDOG", "OWNTEMPO", "OBLIVIOUS"})

STAGE_STATS = ("atk", "def", "spa", "spd", "spe")

# 상대를 겨누는 기술의 target 값 (PokeAPI move-target). 자기에게 거는
# 충전(전기) 같은 기술이 상대의 축전에 빨려 들어가면 안 된다.
OPP_TARGETS = {6, 8, 9, 10, 11, 14}


# ---------------------------------------------------------------- 도우미
def on(f):
    return bool(f is not None and getattr(f, "ability_on", False) and f.ability)


def has(f, *keys):
    return on(f) and f.ability in keys


def breaks(user):
    return has(user, *MOLD_BREAKERS)


def guard(user, target):
    """맞는 쪽 특성. 때리는 쪽이 틀깨기면 무시할 수 있는 것은 None."""
    if not on(target):
        return None
    if breaks(user) and target.ability in IGNORABLE:
        return None
    return target.ability


def pop(bt, f, who, ev):
    # 한 번 드러난 특성은 화면에 계속 보여 준다 (상대 특성은 그 전까지 모른다)
    f.ab["shown"] = True
    ev.append({"t": "ability", "who": who, "ability": f.ability,
               "abilityKr": bt.dex.ability_name(f.ability),
               "text": "[%s의 %s]" % (f.name, bt.dex.ability_name(f.ability))})


def other(bt, who):
    return (bt.foe, "foe") if who == "me" else (bt.me, "me")


def flags(move):
    return set(move.get("flags") or [])


def is_contact(move):
    return "contact" in flags(move)


def aims_at_foe(move):
    t = move.get("target")
    return t is None or t in OPP_TARGETS


def is_status(move):
    return (move.get("cat") == "status") or not MC.attacks(move)


def has_secondary(move):
    return bool((move.get("ail") and move.get("ailChance"))
                or (move.get("stat") and move.get("statChance"))
                or move.get("flinch"))


def key_of(move):
    """기술 dict 에 이름 키가 없어서 영어 이름으로 되짚는다."""
    return "".join(c for c in (move.get("en") or "").upper() if c.isalnum())


# ---------------------------------------------------------------- 타입
def move_type(user, move):
    t = move.get("type")
    if not on(user):
        return t
    a = user.ability
    if a in ATE and t == "NORMAL":
        return ATE[a]
    if a == "NORMALIZE":
        return "NORMAL"
    if a == "LIQUIDVOICE" and "sound" in flags(move):
        return "WATER"
    return t


def type_power_mult(user, move):
    a = user.ability if on(user) else None
    if a in ATE and move.get("type") == "NORMAL":
        return 1.2
    if a == "NORMALIZE":
        return 1.2
    return 1.0


def stab(user):
    return 2.0 if has(user, "ADAPTABILITY") else 1.5


def ghost_bypass(user, mtype):
    """배짱·심안: 노말·격투 기술이 고스트에게 맞는다."""
    return has(user, "SCRAPPY", "MINDSEYE") and mtype in ("NORMAL", "FIGHTING")


# ---------------------------------------------------------------- 능력치
def stat_mult(f, key):
    if not on(f):
        return 1.0
    a = f.ability
    st = getattr(f, "ab", {})
    if key == "atk":
        if a in ("HUGEPOWER", "PUREPOWER"):
            return 2.0
        if a in ("HUSTLE", "GORILLATACTICS"):
            return 1.5
        if a == "GUTS" and f.status:
            return 1.5
        if a == "SLOWSTART" and st.get("slow", 0) > 0:
            return 0.5
    if key == "def":
        if a == "MARVELSCALE" and f.status:
            return 1.5
        if a == "FURCOAT":
            return 2.0
    if key == "spe":
        if a == "QUICKFEET" and f.status:
            return 1.5
        if a == "UNBURDEN" and getattr(f, "used", False):
            return 2.0
        if a == "SLOWSTART" and st.get("slow", 0) > 0:
            return 0.5
    return 1.0


def ignores_para_speed(f):
    return has(f, "QUICKFEET")


def ignores_burn(f):
    return has(f, "GUTS")


# ---------------------------------------------------------------- 순서
def priority_bonus(f, move):
    if not on(f):
        return 0
    a = f.ability
    if a == "PRANKSTER" and is_status(move):
        return 1
    if a == "GALEWINGS" and move.get("type") == "FLYING" and f.hp >= f.maxhp:
        return 1
    if a == "TRIAGE" and (move.get("heal") or (move.get("drain") or 0) > 0):
        return 3
    return 0


# ---------------------------------------------------------------- 명중
def always_hit(user, target):
    return has(user, "NOGUARD") or has(target, "NOGUARD")


def acc_mult(user, target, move):
    m = 1.0
    if has(user, "COMPOUNDEYES"):
        m *= 1.3
    if has(user, "VICTORYSTAR"):
        m *= 1.1
    if has(user, "HUSTLE") and move.get("cat") == "physical":
        m *= 0.8
    g = guard(user, target)
    if g == "WONDERSKIN" and is_status(move) and (move.get("acc") or 0) > 50:
        m *= 50.0 / move["acc"]
    return m


def ignore_evasion(user):
    return has(user, "KEENEYE", "MINDSEYE", "UNAWARE", "ILLUMINATE")


# ---------------------------------------------------------------- 급소
def crit_bonus(user):
    return 1 if has(user, "SUPERLUCK") else 0


def crit_blocked(user, target):
    return guard(user, target) in ("BATTLEARMOR", "SHELLARMOR")


def crit_forced(user, target):
    return has(user, "MERCILESS") and target.status in ("poison", "bad-poison")


def crit_mult(user):
    return 1.5 if has(user, "SNIPER") else 1.0


# ---------------------------------------------------------------- 데미지 보정
def attack_mult(user, target, move, mtype, eff):
    if not on(user):
        return 1.0
    a = user.ability
    m = 1.0
    power = move.get("power") or 0
    fl = flags(move)
    if a == "TECHNICIAN" and 0 < power <= 60:
        m *= 1.5
    if a in FLAG_BOOST and FLAG_BOOST[a][0] in fl:
        m *= FLAG_BOOST[a][1]
    if a == "SHARPNESS" and key_of(move) in SLICING:
        m *= 1.5
    if a == "RECKLESS" and (move.get("drain") or 0) < 0:
        m *= 1.2
    if a == "SHEERFORCE" and has_secondary(move):
        m *= 1.3
    if a in PINCH and mtype == PINCH[a] and user.hp * 3 <= user.maxhp:
        m *= 1.5
    if a == "TINTEDLENS" and 0 < eff < 1:
        m *= 2.0
    if a == "ANALYTIC" and getattr(user, "moved_second", False):
        m *= 1.3
    if a in TYPE_BOOST and mtype == TYPE_BOOST[a][0]:
        m *= TYPE_BOOST[a][1]
    st = getattr(user, "ab", {})
    if a == "FLASHFIRE" and st.get("flash") and mtype == "FIRE":
        m *= 1.5
    if a == "TOXICBOOST" and move.get("cat") == "physical" and user.status in ("poison", "bad-poison"):
        m *= 1.5
    if a == "FLAREBOOST" and move.get("cat") == "special" and user.status == "burn":
        m *= 1.5
    if a == "NEUROFORCE" and eff > 1:
        m *= 1.25
    if a == "SUPREMEOVERLORD":
        m *= 1.0 + 0.1 * min(5, st.get("down", 0))
    if a in ("ELECTROMORPHOSIS", "WINDPOWER") and st.get("charged") and mtype == "ELECTRIC":
        m *= 2.0
    return m


def defense_mult(user, target, move, mtype, eff):
    g = guard(user, target)
    if not g:
        return 1.0
    m = 1.0
    fl = flags(move)
    if g == "THICKFAT" and mtype in ("FIRE", "ICE"):
        m *= 0.5
    if g in ("HEATPROOF", "WATERBUBBLE") and mtype == "FIRE":
        m *= 0.5
    if g == "PURIFYINGSALT" and mtype == "GHOST":
        m *= 0.5
    if g in ("FILTER", "SOLIDROCK") and eff > 1:
        m *= 0.75
    if g == "MULTISCALE" and target.hp >= target.maxhp:
        m *= 0.5
    if g == "FLUFFY":
        if "contact" in fl:
            m *= 0.5
        if mtype == "FIRE":
            m *= 2.0
    if g == "ICESCALES" and move.get("cat") == "special":
        m *= 0.5
    if g == "PUNKROCK" and "sound" in fl:
        m *= 0.5
    if g == "DRYSKIN" and mtype == "FIRE":
        m *= 1.25
    # 틀깨기로도 못 무시하는 것
    if on(target) and target.ability == "PRISMARMOR" and eff > 1:
        m *= 0.75
    if on(target) and target.ability == "SHADOWSHIELD" and target.hp >= target.maxhp:
        m *= 0.5
    return m


def unaware_attack(user, target):
    """맞는 쪽이 천진이면 때리는 쪽의 공격 랭크를 안 본다."""
    return guard(user, target) == "UNAWARE"


def unaware_defense(user):
    """때리는 쪽이 천진이면 맞는 쪽의 방어 랭크를 안 본다."""
    return has(user, "UNAWARE")


# ---------------------------------------------------------------- 기술을 받기 전
def blocks(bt, user, uwho, target, twho, move, key, ev):
    """이 기술이 특성 때문에 막히거나 흡수되면 True. 메시지까지 낸다."""
    if not on(user) and not on(target):
        return False
    if not aims_at_foe(move):
        return False
    mtype = move_type(user, move)
    # 짓궂은마음 변화기는 악 타입에게 안 통한다
    if (has(user, "PRANKSTER") and is_status(move) and not move.get("statSelf")
            and "DARK" in target.types() and move.get("target") in (10, 11)):
        ev.append({"t": "immune", "who": uwho, "text": "%s 에게는 효과가 없는 것 같다..." % target.name})
        return True
    g = guard(user, target)
    if not g:
        return False
    fl = flags(move)
    wk = key_of(move)
    if g in ABSORB and mtype == ABSORB[g][0]:
        what = ABSORB[g][1]
        if what == "immune":
            if is_status(move):
                return False
            pop(bt, target, twho, ev)
            ev.append({"t": "immune", "who": uwho,
                       "text": "%s 에게는 효과가 없는 것 같다..." % target.name})
            return True
        pop(bt, target, twho, ev)
        if what == "heal":
            if target.hp < target.maxhp:
                amount = max(1, target.maxhp // 4)
                target.hp = min(target.maxhp, target.hp + amount)
                ev.append({"t": "heal", "who": twho, "amount": amount, "hp": target.hp,
                           "maxhp": target.maxhp,
                           "text": "%s 은(는) 체력을 회복했다!" % target.name})
            else:
                ev.append({"t": "immune", "who": uwho,
                           "text": "%s 에게는 효과가 없는 것 같다..." % target.name})
        elif what == "flash":
            target.ab["flash"] = True
            ev.append({"t": "msg", "who": twho,
                       "text": "%s 의 불꽃 위력이 올라갔다!" % target.name})
        else:
            bt._change_stat(target, what[0], what[1], ev, twho, source=target)
        return True
    if g == "WINDRIDER" and wk in WIND:
        pop(bt, target, twho, ev)
        bt._change_stat(target, "atk", 1, ev, twho, source=target)
        return True
    if ((g == "BULLETPROOF" and "ballistics" in fl) or (g == "SOUNDPROOF" and "sound" in fl)
            or (g == "OVERCOAT" and "powder" in fl)):
        pop(bt, target, twho, ev)
        ev.append({"t": "immune", "who": uwho, "text": "%s 에게는 효과가 없는 것 같다..." % target.name})
        return True
    if g == "GOODASGOLD" and is_status(move) and not move.get("statSelf"):
        pop(bt, target, twho, ev)
        ev.append({"t": "immune", "who": uwho, "text": "%s 에게는 효과가 없는 것 같다..." % target.name})
        return True
    return False


def wonder_guard_blocks(user, target, eff, move):
    return guard(user, target) == "WONDERGUARD" and not is_status(move) and eff <= 1


def would_block(user, target, move):
    """AI 가 점수를 매길 때 쓴다. 메시지·부작용 없이 막히는지만."""
    g = guard(user, target)
    if not g or not aims_at_foe(move):
        return False
    mtype = move_type(user, move)
    fl = flags(move)
    if g in ABSORB and mtype == ABSORB[g][0]:
        return not (ABSORB[g][1] == "immune" and is_status(move))
    if g == "WINDRIDER" and key_of(move) in WIND:
        return True
    if (g == "BULLETPROOF" and "ballistics" in fl) or (g == "SOUNDPROOF" and "sound" in fl):
        return True
    if g == "OVERCOAT" and "powder" in fl:
        return True
    if g == "GOODASGOLD" and is_status(move) and not move.get("statSelf"):
        return True
    return False


# ---------------------------------------------------------------- 등장 / 퇴장
def on_switch_in(bt, f, who, ev):
    if not on(f):
        return
    f.ab.pop("flash", None)
    f.ab.pop("charged", None)
    f.ab["protean"] = False
    f.ab["fresh"] = True        # 나온 턴에는 가속이 안 붙는다
    a = f.ability
    foe, fwho = other(bt, who)
    if a == "INTIMIDATE" and foe is not None and foe.alive():
        pop(bt, f, who, ev)
        if has(foe, *INTIMIDATE_IMMUNE):
            pop(bt, foe, fwho, ev)
            ev.append({"t": "msg", "who": fwho, "text": "%s 의 공격은 떨어지지 않았다!" % foe.name})
        elif has(foe, "GUARDDOG"):
            pop(bt, foe, fwho, ev)
            bt._change_stat(foe, "atk", 1, ev, fwho, source=foe)
        else:
            bt._change_stat(foe, "atk", -1, ev, fwho, source=f)
            if has(foe, "RATTLED"):
                pop(bt, foe, fwho, ev)
                bt._change_stat(foe, "spe", 1, ev, fwho, source=foe)
    elif a == "DOWNLOAD" and foe is not None and foe.alive():
        pop(bt, f, who, ev)
        stat = "atk" if foe.stat("def") < foe.stat("spd") else "spa"
        bt._change_stat(f, stat, 1, ev, who, source=f)
    elif a == "TRACE" and foe is not None and on(foe) and foe.ability not in UNTRACEABLE:
        pop(bt, f, who, ev)
        f.ability = foe.ability
        ev.append({"t": "msg", "who": who,
                   "text": "%s 은(는) %s 의 %s 을(를) 트레이스했다!"
                           % (f.name, foe.name, bt.dex.ability_name(foe.ability))})
        if f.ability != "TRACE":
            on_switch_in(bt, f, who, ev)
    elif a == "INTREPIDSWORD":
        pop(bt, f, who, ev)
        bt._change_stat(f, "atk", 1, ev, who, source=f)
    elif a == "DAUNTLESSSHIELD":
        pop(bt, f, who, ev)
        bt._change_stat(f, "def", 1, ev, who, source=f)
    elif a in ("PRESSURE", "UNNERVE") or a in MOLD_BREAKERS:
        pop(bt, f, who, ev)
    elif a == "SLOWSTART":
        f.ab["slow"] = 5
        pop(bt, f, who, ev)
        ev.append({"t": "msg", "who": who, "text": "%s 은(는) 제대로 힘을 쓰지 못한다!" % f.name})
    elif a == "SUPREMEOVERLORD" and f.ab.get("down"):
        pop(bt, f, who, ev)
        ev.append({"t": "msg", "who": who,
                   "text": "%s 은(는) 쓰러진 동료의 몫까지 힘이 넘친다!" % f.name})


def on_switch_out(f):
    if not on(f):
        return
    if f.ability == "REGENERATOR" and f.alive() and f.hp < f.maxhp:
        f.hp = min(f.maxhp, f.hp + f.maxhp // 3)
    if f.ability == "NATURALCURE" and f.status:
        f.status = None
        f.sleep_turns = 0


# ---------------------------------------------------------------- 기술을 쓸 때
def before_move(bt, user, uwho, move, ev):
    """변환자재·리베로: 쓰는 기술의 타입으로 바뀐다(나올 때마다 한 번)."""
    if not has(user, "PROTEAN", "LIBERO") or user.ab.get("protean"):
        return
    t = move_type(user, move)
    if not t or user.types() == [t]:
        return
    user.types_override = [t]
    user.ab["protean"] = True
    pop(bt, user, uwho, ev)
    ev.append({"t": "msg", "who": uwho,
               "text": "%s 은(는) %s 타입이 되었다!" % (user.name, bt.dex.type_name(t))})


def pp_cost(user, target):
    return 2 if has(target, "PRESSURE") else 1


def hit_count(user, lo, hi):
    return hi if has(user, "SKILLLINK") else None


def survive(bt, user, uwho, target, twho, move, dmg, ev):
    """옹골참·탈: 맞기 전에 데미지를 고친다."""
    g = guard(user, target)
    if not g:
        return dmg
    if g == "DISGUISE" and not target.ab.get("busted") and dmg > 0:
        target.ab["busted"] = True
        pop(bt, target, twho, ev)
        chip = max(1, target.maxhp // 8)
        ev.append({"t": "msg", "who": twho, "text": "탈이 대신 공격을 받았다!"})
        target.hp = max(1, target.hp - chip)
        return 0
    if g == "STURDY" and target.hp >= target.maxhp and dmg >= target.hp:
        pop(bt, target, twho, ev)
        ev.append({"t": "msg", "who": twho, "text": "%s 은(는) 공격을 버텼다!" % target.name})
        return target.hp - 1
    return dmg


def after_hit(bt, user, uwho, target, twho, move, dmg, eff, crit, hp_before, ev):
    """한 대 맞은 뒤. 접촉 반응과 맞는 쪽의 능력 변화."""
    if dmg <= 0:
        return
    mtype = move_type(user, move)
    contact = is_contact(move)
    rng = bt.rng
    # ---- 맞는 쪽이 접촉에 반응
    if contact and on(target) and user.alive():
        t = target.ability
        if t in ("STATIC", "FLAMEBODY", "POISONPOINT", "EFFECTSPORE") and rng.random() < 0.3:
            ail = {"STATIC": "paralysis", "FLAMEBODY": "burn", "POISONPOINT": "poison"}.get(t)
            if t == "EFFECTSPORE":
                if "GRASS" in user.types() or has(user, "OVERCOAT"):
                    ail = None
                else:
                    ail = rng.choice(["poison", "paralysis", "sleep"])
            if ail and not user.status:
                pop(bt, target, twho, ev)
                bt._apply_status(user, ail, ev, source=target)
        elif t in ("ROUGHSKIN", "IRONBARBS") and not has(user, "MAGICGUARD"):
            pop(bt, target, twho, ev)
            d = max(1, user.maxhp // 8)
            user.hp = max(0, user.hp - d)
            ev.append({"t": "chip", "who": uwho, "damage": d, "hp": user.hp, "maxhp": user.maxhp,
                       "text": "%s 은(는) 상처를 입었다!" % user.name})
        elif t in ("GOOEY", "TANGLINGHAIR"):
            pop(bt, target, twho, ev)
            bt._change_stat(user, "spe", -1, ev, uwho, source=target)
        elif t in ("MUMMY", "LINGERINGAROMA") and on(user) and user.ability not in UNTRACEABLE \
                and user.ability != t:
            pop(bt, target, twho, ev)
            user.ability = t
            ev.append({"t": "msg", "who": uwho,
                       "text": "%s 의 특성이 %s 이(가) 되었다!" % (user.name, bt.dex.ability_name(t))})
    # ---- 때리는 쪽
    if contact and has(user, "POISONTOUCH") and target.alive() and not target.status \
            and rng.random() < 0.3:
        pop(bt, user, uwho, ev)
        bt._apply_status(target, "poison", ev, source=user)
    # ---- 맞는 쪽의 능력 변화 (살아 있을 때만)
    if not target.alive() or not on(target):
        return
    t = target.ability
    half = target.maxhp / 2.0
    crossed = hp_before > half >= target.hp
    if t == "STAMINA":
        pop(bt, target, twho, ev)
        bt._change_stat(target, "def", 1, ev, twho, source=target)
    elif t == "WEAKARMOR" and move.get("cat") == "physical":
        pop(bt, target, twho, ev)
        bt._change_stat(target, "def", -1, ev, twho, source=target)
        bt._change_stat(target, "spe", 2, ev, twho, source=target)
    elif t == "JUSTIFIED" and mtype == "DARK":
        pop(bt, target, twho, ev)
        bt._change_stat(target, "atk", 1, ev, twho, source=target)
    elif t == "RATTLED" and mtype in ("BUG", "GHOST", "DARK"):
        pop(bt, target, twho, ev)
        bt._change_stat(target, "spe", 1, ev, twho, source=target)
    elif t == "WATERCOMPACTION" and mtype == "WATER":
        pop(bt, target, twho, ev)
        bt._change_stat(target, "def", 2, ev, twho, source=target)
    elif t == "STEAMENGINE" and mtype in ("FIRE", "WATER"):
        pop(bt, target, twho, ev)
        bt._change_stat(target, "spe", 6, ev, twho, source=target)
    elif t == "THERMALEXCHANGE" and mtype == "FIRE":
        pop(bt, target, twho, ev)
        bt._change_stat(target, "atk", 1, ev, twho, source=target)
    elif t == "ANGERPOINT" and crit:
        pop(bt, target, twho, ev)
        bt._change_stat(target, "atk", 12, ev, twho, source=target)
    elif t == "COTTONDOWN" and user.alive():
        pop(bt, target, twho, ev)
        bt._change_stat(user, "spe", -1, ev, uwho, source=target)
    elif t in ("ELECTROMORPHOSIS", "WINDPOWER") and (t == "ELECTROMORPHOSIS" or key_of(move) in WIND):
        pop(bt, target, twho, ev)
        target.ab["charged"] = True
        ev.append({"t": "msg", "who": twho, "text": "%s 은(는) 전기를 모았다!" % target.name})
    elif t == "BERSERK" and crossed:
        pop(bt, target, twho, ev)
        bt._change_stat(target, "spa", 1, ev, twho, source=target)
    elif t == "ANGERSHELL" and crossed:
        pop(bt, target, twho, ev)
        for s, c in (("def", -1), ("spd", -1), ("atk", 1), ("spa", 1), ("spe", 1)):
            bt._change_stat(target, s, c, ev, twho, source=target)


def after_ko(bt, user, uwho, ev):
    """상대를 쓰러뜨렸을 때 (자기과신·비스트부스트)."""
    if not on(user) or not user.alive():
        return
    a = user.ability
    if a in ("MOXIE", "CHILLINGNEIGH"):
        pop(bt, user, uwho, ev)
        bt._change_stat(user, "atk", 1, ev, uwho, source=user)
    elif a == "GRIMNEIGH":
        pop(bt, user, uwho, ev)
        bt._change_stat(user, "spa", 1, ev, uwho, source=user)
    elif a == "BEASTBOOST":
        best = max(STAGE_STATS, key=lambda s: user.base.get(s, 0))
        pop(bt, user, uwho, ev)
        bt._change_stat(user, best, 1, ev, uwho, source=user)


def use_after_electric(user, mtype):
    """충전은 전기 기술을 한 번 쓰면 풀린다."""
    if on(user) and user.ab.get("charged") and mtype == "ELECTRIC":
        user.ab["charged"] = False


# ---------------------------------------------------------------- 부가 효과
def secondary_mult(user):
    return 2.0 if has(user, "SERENEGRACE") else 1.0


def secondary_off(user, target):
    """(내 부가효과가 사라지나, 상대에게 거는 해로운 부가효과가 막히나)"""
    return has(user, "SHEERFORCE"), guard(user, target) == "SHIELDDUST"


def flinch_immune(user, target):
    return guard(user, target) == "INNERFOCUS"


def stench(user, move):
    return has(user, "STENCH") and MC.attacks(move) and not move.get("flinch")


def on_flinch(bt, f, who, ev):
    if has(f, "STEADFAST"):
        pop(bt, f, who, ev)
        bt._change_stat(f, "spe", 1, ev, who, source=f)


def no_recoil(user):
    return has(user, "ROCKHEAD", "MAGICGUARD")


# ---------------------------------------------------------------- 상태이상
def status_blocked(f, ail, source=None):
    if not on(f):
        return False
    if source is not None and breaks(source) and f.ability in IGNORABLE:
        return False
    return ail in STATUS_IMMUNE.get(f.ability, ())


def can_poison_types(source):
    return has(source, "CORROSION")


def on_status(bt, f, who, ail, source, ev):
    """싱크로: 독·마비·화상을 건 상대에게 그대로 돌려준다."""
    if not has(f, "SYNCHRONIZE") or source is None or source is f or not source.alive():
        return
    if ail not in ("burn", "paralysis", "poison") or source.status:
        return
    pop(bt, f, who, ev)
    bt._apply_status(source, ail, ev, source=None)


def sleep_ticks(f):
    return 2 if has(f, "EARLYBIRD") else 1


# ---------------------------------------------------------------- 능력 변화
def adjust_stat_change(bt, f, stat, change, source, who, ev):
    """(바뀐 변화량, 막혔는가). 막혔으면 메시지까지 낸다."""
    if not on(f):
        return change, False
    a = f.ability
    if source is not None and source is not f and breaks(source) and a in IGNORABLE:
        return change, False
    if a == "CONTRARY":
        change = -change
    if a == "SIMPLE":
        change *= 2
    by_foe = source is not None and source is not f
    if by_foe and change < 0:
        if a in BLOCK_DROPS and (BLOCK_DROPS[a] is None or BLOCK_DROPS[a] == stat):
            pop(bt, f, who, ev)
            ev.append({"t": "msg", "who": who,
                       "text": "%s 의 능력은 떨어지지 않았다!" % f.name})
            return 0, True
        if a == "MIRRORARMOR" and source.alive() and not has(source, "MIRRORARMOR"):
            pop(bt, f, who, ev)
            swho = "foe" if who == "me" else "me"
            bt._change_stat(source, stat, change, ev, swho, source=f)
            return 0, True
    return change, False


def after_drop(bt, f, who, source, ev):
    """오기·승기: 상대 때문에 능력이 떨어지면 크게 오른다."""
    if source is None or source is f or not on(f):
        return
    if f.ability == "DEFIANT":
        pop(bt, f, who, ev)
        bt._change_stat(f, "atk", 2, ev, who, source=f)
    elif f.ability == "COMPETITIVE":
        pop(bt, f, who, ev)
        bt._change_stat(f, "spa", 2, ev, who, source=f)


# ---------------------------------------------------------------- 턴 끝
def status_chip(f, kind):
    """상태이상 데미지를 어떻게 받나: 'normal' / 'none' / 'heal' / 'less'"""
    if not on(f):
        return "normal"
    if f.ability == "MAGICGUARD":
        return "none"
    if kind == "poison" and f.ability == "POISONHEAL":
        return "heal"
    if kind == "burn" and f.ability == "HEATPROOF":
        return "less"
    return "normal"


def end_of_turn(bt, f, who, ev):
    if not on(f) or not f.alive():
        return
    a = f.ability
    st = f.ab
    if a == "SPEEDBOOST" and not st.get("fresh"):
        pop(bt, f, who, ev)
        bt._change_stat(f, "spe", 1, ev, who, source=f)
    elif a == "SHEDSKIN" and f.status and bt.rng.random() < 0.3:
        pop(bt, f, who, ev)
        f.status = None
        f.sleep_turns = 0
        ev.append({"t": "cure", "who": who, "text": "%s 의 상태이상이 나았다!" % f.name})
    elif a == "MOODY":
        up = [s for s in STAGE_STATS if f.stages.get(s, 0) < 6]
        if up:
            pop(bt, f, who, ev)
            s1 = bt.rng.choice(up)
            bt._change_stat(f, s1, 2, ev, who, source=f)
            down = [s for s in STAGE_STATS if s != s1 and f.stages.get(s, 0) > -6]
            if down:
                bt._change_stat(f, bt.rng.choice(down), -1, ev, who, source=f)
    if st.get("slow", 0) > 0:
        st["slow"] -= 1
        if st["slow"] == 0:
            ev.append({"t": "msg", "who": who, "text": "%s 은(는) 드디어 제 힘을 되찾았다!" % f.name})
    st["fresh"] = False


def state(f):
    return {"ability": f.ability, "ab": dict(f.ab), "types": f.types_override}


def load(f, d):
    if not d:
        return
    f.ability = d.get("ability", f.ability)
    f.ab = dict(d.get("ab") or {})
    f.types_override = d.get("types")
