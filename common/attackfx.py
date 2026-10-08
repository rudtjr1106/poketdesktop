# -*- coding: utf-8 -*-
"""기술에 붙은 고유 효과 — 설명에는 적혀 있는데 엔진이 안 하던 것들 (1.9.2).

제보 둘에서 시작했다: 소금절이가 절이지 않고(레이드), 사우전드애로가 떠 있는
상대를 못 맞혔다. 둘 다 **도감 자료(위력·명중·부가효과 확률)에 안 담기는 규칙**
이라 아무도 안 만들어 둔 것이었다. 같은 이유로 빠진 것을 배울 수 있는 기술
781개에서 다 훑었더니 이만큼 나왔다:

    쓰고 나면      파괴광선류는 다음 턴에 못 움직인다 · 대폭발·자폭·추억의선물은 쓰러진다
                   깜짝헤드·철제광선은 체력 절반을 잃는다 · 무릎차기류는 빗나가면 다친다
    쓸 수 있을 때  꿈먹기(잠든 상대) · 기습·질풍신뢰(공격하려는 상대) · 힘껏펀치(맞기 전)
                   비장의무기 · 폴터가이스트 · 트림 · 거대해머(연달아 못 쓴다) ...
    어느 능력치로  바디프레스(내 방어) · 속임수(상대 공격) · 사이코쇼크(상대 방어) ·
                   포톤가이저(높은 쪽) · 성스러운칼(상대 랭크 무시)
    위력           독침천발 · 분풀이 · 원수갚기 · 분함의발구르기 · 연속자르기 · 구르기 ·
                   에코보이스 · 분노의주먹 · 트리플악셀 · 변덕레이저 ...
    맞힌 뒤        칼등치기(1 남김) · 소금절이 · 시럽봄 · 도둑질 · 벌레먹기 · 불사르기 ·
                   클리어스모그 · 그림자꿰매기 · 암석액스 · 섀도스틸 · 사우전드애로 ...
    나중에         미래예지 · 파멸의소원 (두 턴 뒤)
    변화기         추억의선물 · 소울비트 · 정화 · 힘흡수 · 볼가득넣기 · 배수의진 ...
    맹독           맹독·맹독엄니·악독사슬·독사슬·맹독구슬: 턴마다 데미지가 커진다

그 뒤 **Showdown 의 기술 자료(tools/_cache/showdown_moves.json)와 기계로 대조**해서 더 찾은 것
(쓸 수 있는 기술 745개의 플래그·구조 항목을 하나씩 써 보고 비교했다):

    풀 타입        가루·포자 기술(수면가루·버섯포자·저리가루·목화포자)이 안 통한다
    얼음           불꽃 기술과 열탕류를 맞으면 녹는다 · 화염바퀴류는 얼어 있어도 쓰고 녹는다
    작아지기       짓밟기·누르기·드래곤다이브 ... 가 두 배로 들어가고 반드시 맞는다
    웅크리기       그 뒤의 구르기·아이스볼이 두 배
    숨은 상대      지진(땅속)·파도타기(물속)·바람일으키기(공중)가 두 배
    부자유친       고정 데미지 기술도 두 번, 모았다 쓰는 기술·구르기는 한 번 (본가의 조건 그대로)
    프리폴         두 턴 기술 (첫 턴에 상대를 데려가 못 움직이게 한다)
    옛노래         메로엣타가 스텝폼이 된다
    코골기         깨어 있으면 실패한다

## 규칙

- battle.py 를 import 하지 않는다 (battle 이 이걸 import 한다).
- 난수는 bt.rng 만. cond 에는 JSON 으로 저장되는 값만 넣는다.
- **야생 1:1 에서 뜻이 없는 것은 원작도 실패한다** (코칭 ...).
- 더블배틀 전용·다이맥스·Z·테라스탈은 이 게임에 없어서 뺐다.
"""
from . import abilities as A
from . import field as FD
from . import held as H
from . import movecalc as MC
from . import statusmoves as SM

# ---------------------------------------------------------------- 분류
# 빗나가거나 막히면 스스로 다친다 (최대 체력의 절반)
CRASH = {"HIGHJUMPKICK", "JUMPKICK", "AXEKICK", "SUPERCELLSLAM"}
# 쓰면 쓰러진다
SELF_KO = {"EXPLOSION", "SELFDESTRUCT", "MISTYEXPLOSION", "MEMENTO"}
# 쓰면 최대 체력의 절반을 잃는다 (올림)
SELF_HALF = {"MINDBLOWN", "STEELBEAM", "CHLOROBLAST"}
# 상대 체력을 반드시 1 은 남긴다
LEAVE_ONE = {"FALSESWIPE", "HOLDBACK"}
# 어느 능력치로 세는가
ATK_BY_DEF = {"BODYPRESS"}                               # 내 방어로 때린다
ATK_BY_FOE = {"FOULPLAY"}                                # 상대의 공격으로 때린다
HITS_DEF = {"PSYSHOCK", "PSYSTRIKE", "SECRETSWORD"}      # 특수기인데 상대의 방어로 받는다
HIGHER_STAT = {"PHOTONGEYSER", "TERABLAST", "TERASTARSTORM"}   # 공격·특수공격 중 높은 쪽
IGNORE_STAGES = {"CHIPAWAY", "DARKESTLARIAT", "SACREDSWORD", "NIHILLIGHT"}   # 상대의 방어·회피 랭크 무시
# 메가진화해 있는 동안 다른 기술로 바뀌는 기술 {메가 폼: {원래 기술: 바뀐 기술}}.
# 니힐레이저 (레전드 Z-A, 게시판 #158): 메가지가르데가 되면 코어퍼니셔가 이것으로 바뀐다 - 드래곤 기술인데
# 페어리에게도 맞고(상성은 나머지 타입만 본다), 상대의 능력 변화를 무시한다. 코어퍼니셔의 '특성을 없앤다' 는 없다.
MEGA_MOVES = {"ZYGARDE_MEGA": {"COREENFORCER": "NIHILLIGHT"}}
HITS_FAIRY = {"NIHILLIGHT"}          # 드래곤 기술이지만 페어리의 무효를 뚫는다
# 상대의 특성을 무시하고 때린다 (그 기술을 쓰는 동안만 틀깨기)
IGNORE_ABILITY = {"MOONGEISTBEAM", "SUNSTEELSTRIKE", "PHOTONGEYSER"}
# 효과가 굉장하면 위력이 더 오른다 (5461/4096)
SE_BOOST = {"COLLISIONCOURSE", "ELECTRODRIFT"}
# 맞히면 상대가 못 도망간다
TRAP_HIT = {"ANCHORSHOT", "SPIRITSHACKLE", "THOUSANDWAVES"}
STEAL = {"THIEF", "COVET"}
EAT_FOE_BERRY = {"BUGBITE", "PLUCK"}
# 쓰면 그 타입을 잃는다
LOSE_TYPE = {"BURNUP": "FIRE", "DOUBLESHOCK": "ELECTRIC"}
# 상대가 공격하려는 참이어야 한다
NEED_FOE_ATTACK = {"SUCKERPUNCH", "THUNDERCLAP"}
# 연달아 못 쓴다 (칸을 흐리게 하는 것은 statusmoves.blocked 가 한다)
NO_REPEAT = SM.NO_REPEAT
# 맞힌 자리에 깔린다
HAZARD_HIT = {"STONEAXE": "stealthrock", "CEASELESSEDGE": "spikes"}
# 두 턴 뒤에 맞는다
DELAYED = {"FUTURESIGHT": "%s 은(는) 미래를 예지했다!",
           "DOOMDESIRE": "%s 은(는) 파멸의 소원을 빌었다!"}
# 연달아 맞힐수록 세진다: (곱하는가, 상한)
CHAIN = {"FURYCUTTER": ("double", 160), "ROLLOUT": ("double", 480), "ICEBALL": ("double", 480),
         "ECHOEDVOICE": ("add", 200)}
# 맞을 때마다 위력이 오르는 3연타 (기본 위력 x 1, 2, 3)
RISING_HITS = {"TRIPLEKICK", "TRIPLEAXEL"}
# 맹독으로 거는 것 (도감에는 그냥 독으로 들어 있다)
BAD_POISON = {"TOXIC", "POISONFANG", "MALIGNANTCHAIN"}
# 그 턴에 능력이 오른 상대에게만 붙는 부가효과
IF_ROSE = {"BURNINGJEALOUSY": "burn", "ALLURINGVOICE": "confusion"}
# 타입에 따라 두 배
SALT_WEAK = ("WATER", "STEEL")
# 맞은 상대의 얼음을 녹이는 기술 (불꽃 타입 공격기는 다 녹인다. 이쪽은 불꽃이 아닌데 녹이는 것)
THAW_TARGET = {"SCALD", "STEAMERUPTION", "SCORCHINGSANDS", "HYDROSTEAM", "MATCHAGOTCHA"}
# 작아지기를 쓴 상대에게 두 배로 들어가고 반드시 맞는다
STOMPERS = {"STOMP", "BODYSLAM", "DRAGONRUSH", "FLYINGPRESS", "HEATCRASH", "HEAVYSLAM",
            "STEAMROLLER", "SUPERCELLSLAM", "MALICIOUSMOONSAULT"}
# 숨어 있는 상대에게 닿고(statusmoves.HITS_HIDDEN) **두 배로** 들어가는 기술
HIDDEN_DOUBLE = {"dig": {"EARTHQUAKE", "MAGNITUDE"}, "dive": {"SURF", "WHIRLPOOL"},
                 "fly": {"GUST", "TWISTER"}}
# 부자유친이 두 번 치지 않는 기술 (Showdown 의 noparentalbond 플래그)
NO_PARENTAL = {"DRAGONDARTS", "DYNAMAXCANNON", "ENDEAVOR", "EXPLOSION", "FINALGAMBIT", "FLING",
               "ICEBALL", "ROLLOUT", "SELFDESTRUCT"}
SKY_DROP_MAX_KG = 200.0     # 이보다 무거우면 프리폴로 못 든다
ROLLERS = {"ROLLOUT", "ICEBALL"}    # 맞히면 다섯 번째까지 묶인다 (after_use)

MEMORY_TYPE = {"FIREMEMORY": "FIRE", "WATERMEMORY": "WATER", "ELECTRICMEMORY": "ELECTRIC",
               "GRASSMEMORY": "GRASS", "ICEMEMORY": "ICE", "FIGHTINGMEMORY": "FIGHTING",
               "POISONMEMORY": "POISON", "GROUNDMEMORY": "GROUND", "FLYINGMEMORY": "FLYING",
               "PSYCHICMEMORY": "PSYCHIC", "BUGMEMORY": "BUG", "ROCKMEMORY": "ROCK",
               "GHOSTMEMORY": "GHOST", "DRAGONMEMORY": "DRAGON", "DARKMEMORY": "DARK",
               "STEELMEMORY": "STEEL", "FAIRYMEMORY": "FAIRY"}
DRIVE_TYPE = {"BURNDRIVE": "FIRE", "DOUSEDRIVE": "WATER", "SHOCKDRIVE": "ELECTRIC",
              "CHILLDRIVE": "ICE"}


def key(move):
    return MC.key(move)


def say(ev, who, text):
    ev.append({"t": "msg", "who": who, "text": text})


def is_berry(item):
    return bool(item) and str(item).endswith("BERRY")


def poisoned(f):
    return f.status in ("poison", "bad-poison")


# ---------------------------------------------------------------- 타입·분류
def move_type(move, user):
    """쓰는 포켓몬에 따라 타입이 바뀌는 기술. 아니면 None."""
    k = key(move)
    if k == "REVELATIONDANCE":
        types = user.types()
        return types[0] if types else None
    if k == "MULTIATTACK" and MC.item_on(user):
        return MEMORY_TYPE.get(user.held)
    if k == "TECHNOBLAST" and MC.item_on(user):
        return DRIVE_TYPE.get(user.held)
    if k == "AURAWHEEL" and user.cond.get("hangry"):
        return "DARK"                       # 모르페코의 배고픈 모양
    return None


def physical(move, user, target):
    """이번에 물리로 세는가. 포톤가이저·테라버스트·셸암즈는 쓸 때 정해진다."""
    k = key(move)
    base = move.get("cat") == "physical"
    if k in HIGHER_STAT:
        return user.stat("atk") > user.stat("spa")
    if k == "SHELLSIDEARM":
        phys = user.stat("atk") / float(max(1, target.stat("def")))
        spec = user.stat("spa") / float(max(1, target.stat("spd")))
        return phys > spec
    return base


# ---------------------------------------------------------------- 위력
def power(k, base, move, user, target):
    """조건에 따라 달라지는 위력. base 는 도감(또는 movecalc)이 준 값."""
    if not base:
        return base
    uc = getattr(user, "cond", None) or {}
    if k == "BARBBARRAGE" and target is not None and poisoned(target):
        return base * 2
    if k == "LASHOUT" and uc.get("fell"):
        return base * 2
    if k in ("STOMPINGTANTRUM", "TEMPERFLARE") and uc.get("lastFailed"):
        return base * 2
    if k == "RETALIATE" and _ally_fell_last_turn(user):
        return base * 2
    if k == "RAGEFIST":
        return min(350, base + 50 * int(uc.get("hitsTaken") or 0))
    ch = uc.get("chain")
    curl = 2 if k in ("ROLLOUT", "ICEBALL") and uc.get("curled") else 1    # 웅크리기를 쓴 뒤
    if k in CHAIN and ch and ch.get("move") == k:
        kind, cap = CHAIN[k]
        n = int(ch.get("n") or 0)
        if kind == "double":
            return min(cap, base * (2 ** n)) * curl
        return min(cap, base * (n + 1))
    if curl > 1:
        return base * curl
    if k == "GRAVAPPLE" and getattr(user, "field", None) is not None \
            and user.field.room("gravity"):
        return base * 3 // 2
    return base


def _ally_fell_last_turn(user):
    fl = getattr(user, "field", None)
    side = getattr(user, "side_name", None)
    if fl is None or not side:
        return False
    fell = fl.side(side).get("fellAt")
    return fell is not None and int(getattr(fl, "clock", 0)) - int(fell) == 1


def damage_mult(k, move, mtype, user, target, eff):
    """상성까지 본 뒤에 곱하는 것 (엑셀브레이크·대검돌격의 빈틈·충전)."""
    m = 1.0
    if k in SE_BOOST and eff > 1:
        m *= 5461 / 4096.0
    tc = getattr(target, "cond", None) or {}
    if tc.get("glaive"):
        m *= 2.0
    if k in STOMPERS and tc.get("minimized"):
        m *= 2.0                            # 작아진 상대를 밟는다
    if k in HIDDEN_DOUBLE.get(tc.get("invuln"), ()):
        m *= 2.0                            # 땅속의 상대에게 지진, 물속에 파도타기, 공중에 바람일으키기
    if mtype == "ELECTRIC" and (getattr(user, "cond", None) or {}).get("charged"):
        m *= 2.0
    if move.get("_pb") or (getattr(user, "cond", None) or {}).get("pierce"):
        m *= 0.25                           # 부자유친의 둘째 타격, 관통드릴로 뚫은 방어
    return m


def flying_press(dex, eff, target_types):
    """플라잉프레스: 격투이면서 비행이다 (두 상성을 곱한다). eff 는 격투로 센 값."""
    t = dex.types.get("FLYING") or {}
    table = t.get("eff") or {}
    for d in target_types:
        eff *= table.get(d, 1.0)
    return eff


def always_hits(k, user, target):
    """대검돌격을 쓰고 난 상대에게는 무엇이든 맞는다. 작아진 상대를 밟는 기술도 반드시 맞는다."""
    tc = getattr(target, "cond", None) or {}
    return bool(tc.get("glaive") or (k in STOMPERS and tc.get("minimized")))


def parental_ok(k, move, fixed_move):
    """부자유친이 이 기술을 두 번 치나 (본가의 조건 그대로).

    연타기·변화기는 부르는 쪽이 이미 걸렀다. 여기서는: 플래그로 빠진 것(대폭발·구르기 ...),
    모았다 쓰는 기술, 미래예지류, 그리고 고정 데미지 중 되받아치는 것(카운터류)을 뺀다.
    지구던지기·나이트헤드·분노의앞니 같은 **고정 데미지는 두 번 다 들어간다.**
    """
    if k in NO_PARENTAL or k in SELF_KO or k in DELAYED:
        return False
    if "charge" in SM.flags(move):
        return False
    if fixed_move:
        return k in MC.LEVEL_DAMAGE or k in MC.FLAT_DAMAGE or k in MC.HALF_HP or k == "PSYWAVE"
    return True


def powder_immune(move, user, target):
    """가루·포자 기술을 풀 타입에게 썼나 (안 통한다)."""
    return ("powder" in SM.flags(move) and target is not user and A.aims_at_foe(move)
            and "GRASS" in target.types())


def thaws_user(bt, user, key):
    """얼어붙은 채로도 쓸 수 있고 쓰면서 녹는 기술인가 (화염바퀴·플레어드라이브·열탕 ...).

    불사르기는 불꽃 타입이 아니면 어차피 실패하므로 녹지도 않는다 (본가).
    """
    if not key:
        return False
    move = bt.move_of(key)
    if "defrost" not in SM.flags(move):
        return False
    return not (MC.key(move) == "BURNUP" and "FIRE" not in user.types())


# ---------------------------------------------------------------- 쓸 수 있나
def cant_use(bt, k, move, who, user, target, tw, ev, prev_move=None):
    """조건이 안 맞아 실패하면 True (문구까지 낸다). 기술 이름은 이미 떴다."""
    def no(text="하지만 실패했다!"):
        say(ev, who, text)
        return True

    if k == "DREAMEATER" and target.status != "sleep" and not A.has(target, "COMATOSE"):
        return no()
    if k == "SNORE" and user.status != "sleep" and not A.has(user, "COMATOSE"):
        return no()                         # 코골기는 잠든 채로만 쓴다
    if k == "SKYDROP" and "FLYING" in target.types():
        # 비행 타입은 데려갔다 놓아도 다치지 않는다
        ev.append({"t": "immune", "who": who,
                   "text": "%s 에게는 효과가 없는 것 같다..." % target.name})
        return True
    if k in NEED_FOE_ATTACK or k == "UPPERHAND":
        pend = getattr(bt, "pending", None) or {}
        acted = getattr(bt, "acted", None) or set()
        if tw in acted:
            return no()                     # 상대가 이미 움직였다
        if tw in pend:                      # 상대가 무엇을 하려는지 아는 판에서만 본다
            md = bt.move_of(pend[tw]) if pend[tw] else None
            if not md or not MC.attacks(md):
                return no()
            if k == "UPPERHAND" and SM.priority(bt, target, md) <= 0:
                return no()
    if k == "FOCUSPUNCH" and MC.hurt_this_turn(user) > 0:
        return no("%s 은(는) 집중이 끊겨 기술을 쓸 수 없다!" % user.name)
    if k == "SHELLTRAP" and MC.hurt_this_turn(user, "physical") <= 0:
        return no("%s 의 트랩셸은 터지지 않았다!" % user.name)
    if k == "LASTRESORT":
        used = set(user.cond.get("usedMoves") or [])
        others = [m for m in user.moves if m != "LASTRESORT"]
        if not others or any(m not in used for m in others):
            return no()
    if k == "POLTERGEIST" and not MC.item_on(target):
        return no()
    if k == "BELCH" and not user.cond.get("ateBerry"):
        return no()
    if k in NO_REPEAT and prev_move == k:
        user.cond.pop("lastMove", None)     # 이번에는 못 썼다 - 다음 턴에는 다시 쓸 수 있다
        return no("%s 은(는) 같은 기술을 연달아 쓸 수 없다!" % user.name)
    if k in LOSE_TYPE and LOSE_TYPE[k] not in user.types():
        return no()
    if k == "STUFFCHEEKS" and not (MC.item_on(user) and is_berry(user.held)):
        return no()
    if k == "NORETREAT" and user.cond.get("noretreat"):
        return no()
    if k == "CAPTIVATE":
        g1, g2 = (user.mon or {}).get("gender"), (target.mon or {}).get("gender")
        if not (g1 in ("M", "F") and g2 in ("M", "F") and g1 != g2):
            return no()
    if k == "VENOMDRENCH" and not poisoned(target):
        return no()
    if k == "PURIFY" and not target.status:
        return no()
    if k == "CLANGOROUSSOUL" and user.hp * 3 <= user.maxhp:
        return no()
    if k == "COACHING":
        return no()                         # 같은 편에게 거는 기술이다
    if k in ("GEARUP", "MAGNETICFLUX") and not A.has(user, "PLUS", "MINUS"):
        return no()
    if k in DELAYED and bt.field.side(tw).get("future"):
        return no()
    return False


# ---------------------------------------------------------------- 프리폴
def sky_drop_fails(bt, key, move, who, user, target, ev):
    """프리폴의 첫 턴: 상대를 들 수 없으면 실패한다 (문구까지 낸다).

    무거운 상대(200kg 이상), 대타 뒤의 상대, 숨어 있는 상대는 못 든다. **레이드 보스도 못 든다** -
    들 수 있으면 여럿이 번갈아 써서 보스가 한 턴도 못 움직인다.
    """
    if (user.cond.get("charge2") or {}).get("move") == "SKYDROP":
        return False                        # 둘째 턴이다
    raid = getattr(bt, "raid", None)
    boss = raid is not None and target is getattr(raid, "boss", None)
    if not (boss or not target.alive() or target.cond.get("sub") or target.cond.get("invuln")
            or MC.kg(target, user) >= SKY_DROP_MAX_KG):
        return False
    user.pp[key] = max(0, user.pp.get(key, 0) - 1)
    user.cond["lastMove"] = key
    ev.append({"t": "move", "who": who, "name": user.name, "move": bt.move_name(key),
               "moveType": move.get("type"), "cat": move.get("cat"),
               "text": "%s 의 %s!" % (user.name, bt.move_name(key))})
    say(ev, who, "%s 은(는) 너무 무거워서 들어 올릴 수 없다!" % target.name
        if MC.kg(target, user) >= SKY_DROP_MAX_KG and not boss else "하지만 실패했다!")
    return True


def sky_drop_up(bt, target, tw, ev):
    """상대를 데리고 올라갔다. 떨어뜨릴 때까지 상대는 아무것도 못 한다."""
    target.cond["skydrop"] = int(getattr(bt.field, "clock", 0)) or 1
    say(ev, tw, "%s 은(는) 하늘로 끌려 올라갔다!" % target.name)


def sky_drop_tick(bt):
    """턴 시작: 붙잡은 쪽이 없어졌거나(쓰러짐·교체·기술이 끊김) 두 턴이 지났으면 풀려난다."""
    clock = int(getattr(bt.field, "clock", 0))
    for who in ("me", "foe"):
        f = bt.fighter(who)
        if f is None or not f.cond.get("skydrop"):
            continue
        holder = bt.fighter(SM.other(who))
        holding = holder is not None and holder.alive() \
            and (holder.cond.get("charge2") or {}).get("move") == "SKYDROP"
        if not holding or clock - int(f.cond.get("skydrop") or 0) >= 2:
            f.cond.pop("skydrop", None)


# ---------------------------------------------------------------- 맞히기 전
def before_attack(bt, k, move, who, user, target, tw, ev):
    """때리기 직전에 판을 바꾸는 것. 고친 기술을 돌려준다 (없으면 그대로)."""
    if k == "SPECTRALTHIEF" and target.alive():
        took = False
        for stat in list(target.stages):
            v = target.stages.get(stat, 0)
            if v > 0:
                target.stages[stat] = 0
                user.stages[stat] = min(6, user.stages.get(stat, 0) + v)
                took = True
        if took:
            say(ev, who, "%s 은(는) %s 의 올라간 능력을 빼앗았다!" % (user.name, target.name))
    if k == "FICKLEBEAM" and bt.rng.random() < 0.3:
        say(ev, who, "%s 은(는) 온 힘을 다해 쏘았다!" % user.name)
        return dict(move, _power=(move.get("power") or 80) * 2)
    return move


def delay(bt, k, move, who, user, target, tw, ev):
    """미래예지·파멸의소원: 지금은 예약만 한다. 예약했으면 True."""
    if k not in DELAYED:
        return False
    phys = move.get("cat") == "physical"
    bt.field.side(tw)["future"] = {
        "turns": 3, "move": k, "by": who, "name": user.name, "level": user.level,
        "atk": user.stat("atk" if phys else "spa"), "types": list(user.types()),
        "type": move.get("type"), "power": int(move.get("power") or 0), "phys": phys}
    say(ev, who, DELAYED[k] % user.name)
    return True


def land_future(bt, ev):
    """턴 끝: 예약해 둔 미래예지가 떨어질 때가 됐나."""
    import math
    for who in ("me", "foe"):
        side = bt.field.side(who)
        fut = side.get("future")
        if not fut:
            continue
        fut["turns"] = int(fut.get("turns") or 0) - 1
        if fut["turns"] > 0:
            continue
        side.pop("future", None)
        f = bt.fighter(who)
        if f is None or not f.alive():
            continue
        name = bt.move_name(fut.get("move"))
        eff = bt.dex.effectiveness(fut.get("type"), f.types()) if fut.get("type") else 1.0
        if eff == 0:
            ev.append({"t": "immune", "who": SM.other(who),
                       "text": "%s 에게는 %s 의 효과가 없는 것 같다..." % (f.name, name)})
            continue
        d = max(1, f.stat("def" if fut.get("phys") else "spd"))
        base = math.floor(math.floor(math.floor(2 * int(fut.get("level") or 1) / 5 + 2)
                                     * int(fut.get("power") or 0) * int(fut.get("atk") or 1) / d)
                          / 50) + 2
        mult = eff * bt.rng.uniform(0.85, 1.0)
        if fut.get("type") in (fut.get("types") or []):
            mult *= 1.5
        dmg = max(1, int(base * mult))
        say(ev, who, "%s 은(는) %s 의 공격을 받았다!" % (f.name, name))
        # 미래예지도 '맞는 공격' 이다 - 기합의띠·옹골참·탈이 받는다 (전에는 그냥 깎았다).
        # 예지한 포켓몬은 이미 물러났을 수 있으므로 지금 서 있는 상대를 때린 쪽으로 본다.
        by = bt.fighter(SM.other(who))
        fmove = {"type": fut.get("type"), "cat": "physical" if fut.get("phys") else "special",
                 "power": int(fut.get("power") or 0), "flags": []}
        if f.held:
            dmg = H.on_incoming(bt, f, who, fmove, eff, dmg, ev)
        if f.ability_on and by is not None:
            dmg = A.survive(bt, by, SM.other(who), f, who, fmove, dmg, ev)
        if f.cond.get("endure") and dmg >= f.hp:
            dmg = f.hp - 1
        before = f.hp
        f.hp = max(0, f.hp - dmg)
        ev.append({"t": "hit", "who": SM.other(who), "target": who, "damage": before - f.hp,
                   "crit": False, "eff": eff, "hp": f.hp, "maxhp": f.maxhp})
        if eff > 1:
            ev.append({"t": "msg", "text": "효과가 굉장했다!"})
        elif eff < 1:
            ev.append({"t": "msg", "text": "효과가 별로인 듯하다..."})


# ---------------------------------------------------------------- 맞는 순간
def cap_damage(k, dmg, target):
    """칼등치기: 체력을 1 은 남긴다."""
    if k in LEAVE_ONE and dmg >= target.hp:
        return max(0, target.hp - 1)
    return dmg


def hit_power(k, move, i):
    """i 번째(0부터) 타격의 기술. 트리플킥·트리플악셀은 맞을 때마다 세진다."""
    if k in RISING_HITS:
        return dict(move, _power=int(move.get("power") or 0) * (i + 1))
    return move


def on_hit_taken(bt, target, tw, dmg, ev):
    """한 대 맞은 쪽: 분노의주먹이 셀 것, 분노."""
    if dmg <= 0:
        return
    target.cond["hitsTaken"] = min(6, int(target.cond.get("hitsTaken") or 0) + 1)
    if target.cond.get("raging") and target.alive():
        bt._change_stat(target, "atk", 1, ev, tw, source=target)


# ---------------------------------------------------------------- 맞힌 뒤
def after_attack(bt, k, move, who, user, target, tw, total, sub_hit, ev):
    """때리고 난 뒤의 고유 효과. statusmoves.after_attack 과 나란히 불린다."""
    alive = target.alive()
    landed = bool(total) and not sub_hit        # 대타가 대신 맞았으면 상대에게는 안 붙는다

    # 얼어붙은 상대는 불꽃 기술(과 열탕류)을 맞으면 녹는다. 타입은 스킨 특성·송전까지 본 것이다.
    if landed and alive and target.status == "freeze":
        mt = move_type(move, user) or (A.move_type(user, move) if user.ability_on
                                       else move.get("type")) or move.get("type")
        if mt == "FIRE" or k in THAW_TARGET:
            target.status = None
            ev.append({"t": "cure", "who": tw, "text": "%s 의 얼음이 녹았다!" % target.name})
    if k == "RELICSONG" and total and user.alive() and (user.mon or {}).get("species") == "MELOETTA" \
            and not user.cond.get("transformed") and not user.mega:
        # 옛노래: 메로엣타가 보이스폼과 스텝폼을 오간다 (물러나면 보이스폼으로 돌아온다)
        if user.cond.get("pirouette"):
            user.cond.pop("pirouette", None)
        else:
            user.cond["pirouette"] = True
        A.update_form(bt, user, who, ev, quiet=True)
    if k == "THOUSANDARROWS" and landed and alive and not SM.forced_grounded(target):
        if not SM.grounded(target):
            say(ev, tw, "%s 은(는) 땅으로 떨어졌다!" % target.name)
        target.cond["smackdown"] = True
        target.cond.pop("magnetrise", None)
        target.cond.pop("telekinesis", None)
    if k == "SALTCURE" and landed and alive and not target.cond.get("saltcure"):
        target.cond["saltcure"] = True
        say(ev, tw, "%s 은(는) 소금에 절여졌다!" % target.name)
    if k == "SYRUPBOMB" and landed and alive and not target.cond.get("syrup"):
        target.cond["syrup"] = 3
        say(ev, tw, "%s 은(는) 끈적한 시럽을 뒤집어썼다!" % target.name)
    if k in TRAP_HIT and landed and alive and not target.cond.get("trapped") \
            and "GHOST" not in target.types():
        target.cond["trapped"] = who
        say(ev, tw, "%s 은(는) 이제 도망칠 수 없다!" % target.name)
    if k == "JAWLOCK" and landed and alive and user.alive():
        if "GHOST" not in target.types() and not target.cond.get("trapped"):
            target.cond["trapped"] = who
        if "GHOST" not in user.types() and not user.cond.get("trapped"):
            user.cond["trapped"] = tw
        say(ev, who, "서로 도망칠 수 없게 되었다!")
    if k == "CLEARSMOG" and landed and alive and any(target.stages.values()):
        for s in target.stages:
            target.stages[s] = 0
        say(ev, tw, "%s 의 능력 변화가 원래대로 돌아갔다!" % target.name)
    if k == "COREENFORCER" and landed and alive and tw in (getattr(bt, "acted", None) or ()) \
            and not target.cond.get("gastro") and target.ability not in SM.ABILITY_FIXED:
        target.cond["gastro"] = True
        say(ev, tw, "%s 의 특성이 사라졌다!" % target.name)
    if k == "EERIESPELL" and landed and alive:
        last = target.cond.get("lastMove")
        if last and target.pp.get(last, 0) > 0:
            target.pp[last] = max(0, target.pp[last] - 3)
            say(ev, tw, "%s 의 %s PP 가 줄었다!" % (target.name, bt.move_name(last)))
    if k == "PSYCHICNOISE" and landed and alive and not target.cond.get("healblock") \
            and not (A.has(target, "AROMAVEIL") and not A.breaks(user)):
        target.cond["healblock"] = 2
        say(ev, tw, "%s 은(는) 회복할 수 없게 되었다!" % target.name)
    if k == "SPARKLINGARIA" and landed and alive and target.status == "burn":
        target.status = None
        ev.append({"t": "cure", "who": tw, "text": "%s 의 화상이 나았다!" % target.name})
    if k == "DIRECLAW" and landed and alive and not target.status and bt.rng.random() < 0.5:
        bt._apply_status(target, bt.rng.choice(["poison", "paralysis", "sleep"]), ev,
                         source=user, by_move=True)
    if k in IF_ROSE and landed and alive and target.cond.get("rose"):
        if IF_ROSE[k] == "burn":
            bt._apply_status(target, "burn", ev, source=user, by_move=True)
        else:
            SM.confuse(bt, target, tw, ev, source=user, quiet=True)
    if k == "SECRETPOWER" and landed and alive and not target.status and bt.rng.random() < 0.3:
        bt._apply_status(target, "paralysis", ev, source=user, by_move=True)
    if k in HAZARD_HIT and total:
        side = bt.field.side(tw)
        hz = HAZARD_HIT[k]
        cap = 3 if hz == "spikes" else 1
        if int(side.get(hz) or 0) < cap:
            side[hz] = int(side.get(hz) or 0) + 1
            say(ev, tw, "%s 진영에 %s 이(가) 깔렸다!" % ("상대" if tw == "foe" else "우리",
                                                   FD.HAZARD_KR[hz]))
    if k == "PLASMAFISTS" and total:
        bt.field.sides["me"]["ion"] = True      # 이 턴 동안 노말 기술이 전기가 된다
        say(ev, who, "전하가 사방으로 흩어졌다!")

    # ---- 도구
    if k in STEAL and landed and user.alive() and not MC.item_on(user) and MC.item_on(target) \
            and not H.is_mega_stone(target._held) and not H.is_mega_stone(user._held) \
            and not (A.has(target, "STICKYHOLD") and not A.breaks(user)):
        # 이 판에서만 옮겨 간다 (트릭·탁쳐서떨구기와 같다 - DB 의 도구는 안 건드린다)
        got = target.held
        target.held, target.item_gone, target.used = None, True, True
        user.held, user.item_gone, user.used = got, False, False
        say(ev, who, "%s 은(는) %s 의 %s 을(를) 빼앗았다!" % (user.name, target.name, H.name(got)))
    if k in EAT_FOE_BERRY and landed and user.alive() and MC.item_on(target) \
            and is_berry(target.held) \
            and not (A.has(target, "STICKYHOLD") and not A.breaks(user)):
        berry = target.held
        target.held, target.item_gone, target.used = None, True, True
        mine, gone, used = user._held, user.item_gone, user.used
        user.held, user.item_gone, user.used = berry, False, False
        if user.held:                       # 금제·서투름이면 먹어도 효과가 없다
            SM.eat_berry(bt, user, who, ev)
            user.cond["ateBerry"] = True
        user.held, user.item_gone, user.used = mine, gone, used     # 내 도구는 그대로다
    if k == "INCINERATE" and landed and MC.item_on(target) and is_berry(target.held):
        berry = target.held
        target.held, target.item_gone, target.used = None, True, True
        say(ev, tw, "%s 의 %s 이(가) 타 버렸다!" % (target.name, H.name(berry)))

    # ---- 쓴 쪽
    if k in LOSE_TYPE and total and user.alive():
        lost = LOSE_TYPE[k]
        rest = [t for t in user.types() if t != lost]
        user.types_override = rest or ["NORMAL"]
        if not rest:
            user.cond["typeless"] = True
        say(ev, who, "%s 은(는) %s 타입이 아니게 되었다!" % (user.name, bt.dex.type_name(lost)))
    if k == "FELLSTINGER" and total and not alive and user.alive():
        bt._change_stat(user, "atk", 3, ev, who, source=user)
    if k == "SCALESHOT" and total and user.alive():
        bt._change_stat(user, "spe", 1, ev, who, source=user)
        bt._change_stat(user, "def", -1, ev, who, source=user)
    if k == "GLAIVERUSH" and user.alive():
        user.cond["glaive"] = True
    if k == "RAGE" and user.alive():
        user.cond["raging"] = True
    if k == "BEAKBLAST":
        pass


def beak_blast(bt, who, user, target, tw, move, ev):
    """부리캐논을 가열하는 동안 닿으면 데인다 (그 포켓몬이 아직 안 움직였을 때)."""
    pend = getattr(bt, "pending", None) or {}
    if tw in (getattr(bt, "acted", None) or ()) or not target.alive() or not user.alive():
        return
    md = bt.move_of(pend.get(tw)) if pend.get(tw) else None
    if md and key(md) == "BEAKBLAST" and A.is_contact(move, user) and not user.status:
        bt._apply_status(user, "burn", ev, source=target)


# ---------------------------------------------------------------- 쓰고 난 뒤 (어떻게 끝났든)
def after_use(bt, k, move, who, user, target, tw, new_ev, ev, prev_move):
    """기술 하나가 끝났다. new_ev 는 이 기술이 낸 이벤트.

    **끝난 모양(맞음·빗나감·막힘·실패)을 이벤트로 본다.** battle._use 는 중간에
    돌아가는 자리가 스무 군데쯤이라, 자리마다 손대면 하나를 빠뜨린다.
    """
    launched = any(e.get("t") == "move" and e.get("who") == who for e in new_ev)
    if not launched:
        return                              # 잠들었거나 풀이 죽어 못 썼다
    hit = any((e.get("t") == "hit" and e.get("who") == who)
              or "대신 공격을 받았다" in (e.get("text") or "") for e in new_ev)
    damp = any("기술을 쓸 수 없다" in (e.get("text") or "") for e in new_ev)
    failed = (not hit) and any(
        e.get("t") in ("miss", "immune")
        or "하지만 실패" in (e.get("text") or "") or "몸을 지켰다" in (e.get("text") or "")
        or "쓸 수 없다" in (e.get("text") or "") or "터지지 않았다" in (e.get("text") or "")
        for e in new_ev)
    c = user.cond
    c["lastFailed"] = bool(failed)

    # 비장의무기: 나온 뒤로 쓴 기술
    used = list(c.get("usedMoves") or [])
    if k not in used and k != "STRUGGLE":
        used.append(k)
        c["usedMoves"] = used

    # 연달아 맞힐수록 세지는 기술
    if k in CHAIN and hit:
        ch = c.get("chain") if (c.get("chain") or {}).get("move") == k else None
        n = int(ch.get("n") or 0) + 1 if ch else 1
        limit = 4 if CHAIN[k][0] == "double" else 5
        c["chain"] = {"move": k, "n": 0 if (k in ("ROLLOUT", "ICEBALL") and n > limit) else min(n, limit)}
    else:
        c.pop("chain", None)
    # 구르기·아이스볼: 맞히면 **다섯 번째까지 그 기술에 묶인다** (다른 기술도 교체도 못 고른다).
    # 빗나가거나 막히면 거기서 끝난다. 전에는 위력만 오르고 언제든 다른 기술을 고를 수 있었다.
    if k in ROLLERS and hit and int((c.get("chain") or {}).get("n") or 0) > 0:
        c["roll"] = {"move": k}
    else:
        c.pop("roll", None)

    if c.get("charged") and MC.attacks(move) and hit \
            and (A.move_type(user, move) if user.ability_on else move.get("type")) == "ELECTRIC":
        c.pop("charged", None)              # 충전은 전기 기술 한 번에 쓰인다
    if k != "RAGE":
        c.pop("raging", None)

    if not user.alive():
        return
    magic = A.has(user, "MAGICGUARD")
    # **레이드 보스는 스스로 쓰러지지 않는다.** 보스가 대폭발 한 번으로 판을 끝내면
    # 여럿이 깎아 온 것이 허사가 된다. 체력을 스스로 깎는 것도 보스에게는 없다.
    raid = getattr(bt, "raid", None)
    if raid is not None and user is getattr(raid, "boss", None):
        if "recharge" in SM.flags(move) and hit:
            c["recharge"] = True
        return
    if k in CRASH and failed and not magic:
        d = max(1, user.maxhp // 2)
        user.hp = max(0, user.hp - d)
        ev.append({"t": "recoil", "who": who, "amount": d, "hp": user.hp, "maxhp": user.maxhp,
                   "text": "%s 은(는) 기세를 못 이기고 땅에 부딪쳤다!" % user.name})
    if k in SELF_HALF and not damp and not (k == "CHLOROBLAST" and not hit) and not magic:
        d = (user.maxhp + 1) // 2
        user.hp = max(0, user.hp - d)
        ev.append({"t": "recoil", "who": who, "amount": d, "hp": user.hp, "maxhp": user.maxhp,
                   "text": "%s 은(는) 자신도 큰 데미지를 입었다!" % user.name})
    if k in SELF_KO and not damp and not (k == "MEMENTO" and failed):
        user.hp = 0
    if "recharge" in SM.flags(move) and hit and user.alive():
        c["recharge"] = True


def not_moved(user):
    """자기 차례에 아예 못 움직였다 (잠듦·마비·풀죽음·반동): 이어 쓰던 것이 끊긴다."""
    c = user.cond
    c.pop("roll", None)
    c.pop("chain", None)


# ---------------------------------------------------------------- 변화기
def h_memento(bt, move, who, user, target, tw, ev):
    bt._change_stat(target, "atk", -2, ev, tw, source=user)
    bt._change_stat(target, "spa", -2, ev, tw, source=user)


def h_clangoroussoul(bt, move, who, user, target, tw, ev):
    d = max(1, user.maxhp // 3)
    user.hp = max(1, user.hp - d)
    ev.append({"t": "chip", "who": who, "damage": d, "hp": user.hp, "maxhp": user.maxhp,
               "text": "%s 은(는) 체력을 깎아 힘을 끌어올렸다!" % user.name})
    for s in ("atk", "def", "spa", "spd", "spe"):
        bt._change_stat(user, s, 1, ev, who, source=user)


def h_purify(bt, move, who, user, target, tw, ev):
    target.status, target.sleep_turns = None, 0
    target.cond.pop("toxic", None)
    ev.append({"t": "cure", "who": tw, "text": "%s 의 상태이상이 나았다!" % target.name})
    SM._heal(bt, user, who, user.maxhp / 2.0, ev)


def h_strengthsap(bt, move, who, user, target, tw, ev):
    if target.stages.get("atk", 0) <= -6:
        return SM.fail(ev, who)
    amount = target.stat("atk")
    bt._change_stat(target, "atk", -1, ev, tw, source=user)
    if A.has(target, "LIQUIDOOZE"):
        A.pop(bt, target, tw, ev)
        SM._chip(user, who, amount, ev, "%s 은(는) 해감액을 흡수했다!" % user.name)
    else:
        SM._heal(bt, user, who, amount, ev)


def h_junglehealing(bt, move, who, user, target, tw, ev):
    did = False
    if user.status:
        user.status, user.sleep_turns = None, 0
        user.cond.pop("toxic", None)
        ev.append({"t": "cure", "who": who, "text": "%s 의 상태이상이 나았다!" % user.name})
        did = True
    if user.hp < user.maxhp and not user.cond.get("healblock"):
        SM._heal(bt, user, who, user.maxhp / 4.0, ev)
        did = True
    if not did:
        SM.fail(ev, who)


def h_stuffcheeks(bt, move, who, user, target, tw, ev):
    SM.eat_berry(bt, user, who, ev)
    user.cond["ateBerry"] = True
    bt._change_stat(user, "def", 2, ev, who, source=user)


def h_noretreat(bt, move, who, user, target, tw, ev):
    for s in ("atk", "def", "spa", "spd", "spe"):
        bt._change_stat(user, s, 1, ev, who, source=user)
    user.cond["noretreat"] = True
    if not user.cond.get("trapped"):
        user.cond["trapped"] = who
    say(ev, who, "%s 은(는) 이제 물러설 수 없다!" % user.name)


def h_flowershield(bt, move, who, user, target, tw, ev):
    did = False
    for f, w in ((user, who), (target, tw)):
        if f.alive() and "GRASS" in f.types():
            bt._change_stat(f, "def", 1, ev, w, source=user)
            did = True
    if not did:
        SM.fail(ev, who)


HANDLERS = {
    "MEMENTO": h_memento, "CLANGOROUSSOUL": h_clangoroussoul, "PURIFY": h_purify,
    "STRENGTHSAP": h_strengthsap, "JUNGLEHEALING": h_junglehealing,
    "STUFFCHEEKS": h_stuffcheeks, "NORETREAT": h_noretreat, "FLOWERSHIELD": h_flowershield,
}


def after_status(bt, k, move, who, user, target, tw, ev):
    """일반 처리(능력 변화)를 한 뒤에 더 하는 것."""
    if k == "CHARGE":
        user.cond["charged"] = True
        say(ev, who, "%s 은(는) 전기를 모으기 시작했다!" % user.name)
    if k == "ROOST" and "FLYING" in user.types():
        user.cond["roost"] = True           # 이 턴이 끝날 때까지 비행 타입이 아니다 (battle.Fighter.types)
    if k == "MINIMIZE":
        user.cond["minimized"] = True       # 짓밟기·누르기 ... 가 두 배로 들어오고 반드시 맞는다
    if k == "DEFENSECURL":
        user.cond["curled"] = True          # 그 뒤의 구르기·아이스볼이 두 배


# ---------------------------------------------------------------- 턴 끝
def toxic_damage(f):
    """맹독의 이번 턴 데미지 (1/16, 2/16 ... 15/16). 맹독이 아니면 None."""
    n = (f.cond or {}).get("toxic")
    if not n or f.status != "poison":
        return None
    n = max(1, min(15, int(n)))
    f.cond["toxic"] = min(15, n + 1)
    return max(1, f.maxhp * n // 16)


def end_turn(bt, ev, sides=("me", "foe"), field=True):
    """소금절이·시럽봄. 상태이상 데미지 다음, 남은 턴을 세기 전."""
    for who in sides:
        f = bt.fighter(who)
        if f is None or not f.alive():
            continue
        c = f.cond
        if c.get("saltcure") and not A.has(f, "MAGICGUARD"):
            frac = 4.0 if any(t in f.types() for t in SALT_WEAK) else 8.0
            SM._chip(f, who, f.maxhp / frac, ev,
                     "%s 은(는) 소금절이의 데미지를 입고 있다!" % f.name)
        if c.get("syrup") and f.alive():
            bt._change_stat(f, "spe", -1, ev, who, source=bt.fighter(SM.other(who)))
            c["syrup"] = int(c["syrup"]) - 1
            if c["syrup"] <= 0:
                c.pop("syrup", None)
    if field:
        land_future(bt, ev)
        for s in bt.field.sides.values():
            s.pop("ion", None)


# ---------------------------------------------------------------- AI
# 쓰면 내가 쓰러지는 기술은 궁지에 몰렸을 때만 쓴다
def ai_mult(bt, k, md, user, target):
    """이 공격기의 점수에 곱할 값. 0 이면 지금 쓰면 실패한다."""
    uc = user.cond
    if k == "DREAMEATER" and target.status != "sleep":
        return 0.0
    if k == "LASTRESORT":
        used = set(uc.get("usedMoves") or [])
        if any(m not in used for m in user.moves if m != "LASTRESORT") or len(user.moves) < 2:
            return 0.0
    if k == "POLTERGEIST" and not MC.item_on(target):
        return 0.0
    if k == "BELCH" and not uc.get("ateBerry"):
        return 0.0
    if k in NO_REPEAT and uc.get("lastMove") == k:
        return 0.0
    if k in LOSE_TYPE and LOSE_TYPE[k] not in user.types():
        return 0.0
    if k in DELAYED:
        who = "me" if user is bt.me else "foe"
        return 0.0 if bt.field.side(SM.other(who)).get("future") else 0.5
    if k == "SHELLTRAP":
        return 0.3
    if k == "FOCUSPUNCH":
        return 0.5
    if k in SELF_KO:
        return 0.9 if user.hp * 4 <= user.maxhp else 0.15
    if k in SELF_HALF:
        return 0.2 if user.hp * 2 <= user.maxhp + 1 else 0.7
    if "recharge" in SM.flags(md):
        return 0.6
    if k in CRASH:
        return 0.9
    return 1.0


def status_value(bt, k, md, user, target, base):
    """새로 만든 변화기의 값. 여기 없는 기술이면 None."""
    if k == "MEMENTO":
        return base * 0.6 if user.hp * 5 <= user.maxhp else 0.0
    if k == "CLANGOROUSSOUL":
        if user.hp * 3 <= user.maxhp or all(user.stages.get(s, 0) >= 6 for s in ("atk", "spa", "spe")):
            return 0.0
        return base * 0.6 if user.hp * 10 > user.maxhp * 7 else base * 0.15
    if k == "PURIFY":
        return 0.0 if not target.status else base * 0.3 * (1.0 - user.hp / float(user.maxhp or 1))
    if k == "STRENGTHSAP":
        if target.stages.get("atk", 0) <= -6:
            return 0.0
        return base * (0.25 + 0.5 * (1.0 - user.hp / float(user.maxhp or 1)))
    if k == "JUNGLEHEALING":
        if not user.status and user.hp >= user.maxhp:
            return 0.0
        return base * (0.3 + 0.4 * (1.0 - user.hp / float(user.maxhp or 1)))
    if k == "STUFFCHEEKS":
        return base * 0.4 if (MC.item_on(user) and is_berry(user.held)
                              and user.stages.get("def", 0) < 6) else 0.0
    if k == "NORETREAT":
        return 0.0 if user.cond.get("noretreat") else base * 0.6
    if k == "FLOWERSHIELD":
        return base * 0.2 if "GRASS" in user.types() and "GRASS" not in target.types() else 0.0
    if k == "COACHING":
        return 0.0
    if k in ("GEARUP", "MAGNETICFLUX") and not A.has(user, "PLUS", "MINUS"):
        return 0.0
    if k == "CAPTIVATE":
        g1, g2 = (user.mon or {}).get("gender"), (target.mon or {}).get("gender")
        if not (g1 in ("M", "F") and g2 in ("M", "F") and g1 != g2):
            return 0.0
    if k == "VENOMDRENCH" and not poisoned(target):
        return 0.0
    return None
