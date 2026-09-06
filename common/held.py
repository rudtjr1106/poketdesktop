# -*- coding: utf-8 -*-
"""지닌 도구 — 배틀 안에서 무엇을 하는지.

PokeAPI 는 도구의 **이름·설명·가격**만 준다. 무엇을 하는지는 구조화된
자료가 없어서 여기 손으로 적는다. 목록은 PokeAPI 가 '지닐 수 있고 배틀에
관여한다(holdable-passive/active)' 고 표시한 141종에서, 이 엔진에 없는
개념(날씨·벽·교체·이중 배틀·콘테스트)에 걸린 20종을 뺀 121종이다.
어느 것을 왜 뺐는지는 tools/build_items.py 의 HELD_SKIP 에 있다.

**규칙 둘.**

1. 도구가 없으면 이 파일은 아무것도 하지 않는다. 난수도 안 쓴다.
   PvP 는 시드 하나로 로그를 다시 만들 수 있어야 하고(party_battle),
   지금까지 저장된 판들은 도구 없이 계산된 것이라 그 로그가 한 글자도
   달라지면 안 된다. common/test_held.py 가 이걸 요약값으로 지킨다.
2. 열매처럼 한 번 쓰면 사라지는 도구는 **그 판에서만** 사라진다.
   판이 끝나면 다시 들고 있다. 본가와 다르지만, 비동기 PvP 에서 열매가
   진짜로 없어지려면 로그를 재생하는 쪽이 아니라 계산하는 쪽이 가방까지
   고쳐야 하고, 그러면 '자는 동안 열매를 다 뺏겼다' 가 된다.

훅은 battle.Battle 이 정해진 자리에서 부른다. 각 훅은 먼저 도구가
있는지만 보고 없으면 바로 돌아간다 - 위 규칙 1 이다.
"""

# 도구 id -> 한글 이름. 로그의 문구에 쓴다. 서버의 items.json 과 같은
# 출처(PokeAPI CSV)라 build_items 가 어긋나면 검사에서 잡힌다.
KR = {
    "CHERIBERRY": "버치열매", "CHESTOBERRY": "유루열매", "PECHABERRY": "복슝열매",
    "RAWSTBERRY": "복분열매", "ASPEARBERRY": "배리열매", "LEPPABERRY": "과사열매",
    "ORANBERRY": "오랭열매", "LUMBERRY": "리샘열매", "SITRUSBERRY": "자뭉열매",
    "FIGYBERRY": "무화열매", "WIKIBERRY": "위키열매", "MAGOBERRY": "마고열매",
    "AGUAVBERRY": "아바열매", "IAPAPABERRY": "파야열매", "OCCABERRY": "오카열매",
    "PASSHOBERRY": "꼬시개열매", "WACANBERRY": "초나열매", "RINDOBERRY": "린드열매",
    "YACHEBERRY": "플카열매", "CHOPLEBERRY": "로플열매", "KEBIABERRY": "으름열매",
    "SHUCABERRY": "슈캐열매", "COBABERRY": "바코열매", "PAYAPABERRY": "야파열매",
    "TANGABERRY": "리체열매", "CHARTIBERRY": "루미열매", "KASIBBERRY": "수불열매",
    "HABANBERRY": "하반열매", "COLBURBERRY": "마코열매", "BABIRIBERRY": "바리비열매",
    "CHILANBERRY": "카리열매", "LIECHIBERRY": "치리열매", "GANLONBERRY": "용아열매",
    "SALACBERRY": "캄라열매", "PETAYABERRY": "야타비열매", "APICOTBERRY": "규살열매",
    "LANSATBERRY": "랑사열매", "STARFBERRY": "스타열매", "ENIGMABERRY": "의문열매",
    "MICLEBERRY": "미클열매", "CUSTAPBERRY": "애슈열매", "JABOCABERRY": "자보열매",
    "ROWAPBERRY": "애터열매", "BRIGHTPOWDER": "반짝가루", "WHITEHERB": "하양허브",
    "MACHOBRACE": "교정깁스", "QUICKCLAW": "선제공격손톱", "SOOTHEBELL": "평온의방울",
    "CHOICEBAND": "구애머리띠", "KINGSROCK": "왕의징표석", "SILVERPOWDER": "은빛가루",
    "SMOKEBALL": "연막탄", "FOCUSBAND": "기합의머리띠", "LUCKYEGG": "행복의알",
    "SCOPELENS": "초점렌즈", "METALCOAT": "금속코트", "LEFTOVERS": "먹다남은음식",
    "SOFTSAND": "부드러운모래", "HARDSTONE": "딱딱한돌", "MIRACLESEED": "기적의씨",
    "BLACKGLASSES": "검은안경", "BLACKBELT": "검은띠", "MAGNET": "자석",
    "MYSTICWATER": "신비의물방울", "SHARPBEAK": "예리한부리", "POISONBARB": "독바늘",
    "NEVERMELTICE": "녹지않는얼음", "SPELLTAG": "저주의부적", "TWISTEDSPOON": "휘어진스푼",
    "CHARCOAL": "목탄", "DRAGONFANG": "용의이빨", "SILKSCARF": "실크스카프",
    "SHELLBELL": "조개껍질방울", "SEAINCENSE": "바닷물향로", "LAXINCENSE": "무사태평향로",
    "WIDELENS": "광각렌즈", "MUSCLEBAND": "힘의머리띠", "WISEGLASSES": "박식안경",
    "EXPERTBELT": "달인의띠", "LIFEORB": "생명의구슬", "TOXICORB": "맹독구슬",
    "FLAMEORB": "화염구슬", "FOCUSSASH": "기합의띠", "ZOOMLENS": "포커스렌즈",
    "METRONOME": "메트로놈", "IRONBALL": "검은철구", "LAGGINGTAIL": "느림보꼬리",
    "BLACKSLUDGE": "검은오물", "CHOICESCARF": "구애스카프", "STICKYBARB": "끈적끈적바늘",
    "POWERBRACER": "파워리스트", "POWERBELT": "파워벨트", "POWERLENS": "파워렌즈",
    "POWERBAND": "파워밴드", "POWERANKLET": "파워앵클릿", "POWERWEIGHT": "파워웨이트",
    "BIGROOT": "큰뿌리", "CHOICESPECS": "구애안경", "FLAMEPLATE": "불구슬플레이트",
    "SPLASHPLATE": "물방울플레이트", "ZAPPLATE": "우레플레이트", "MEADOWPLATE": "초록플레이트",
    "ICICLEPLATE": "고드름플레이트", "FISTPLATE": "주먹플레이트", "TOXICPLATE": "맹독플레이트",
    "EARTHPLATE": "대지플레이트", "SKYPLATE": "푸른하늘플레이트", "MINDPLATE": "이상한플레이트",
    "INSECTPLATE": "비단벌레플레이트", "STONEPLATE": "암석플레이트",
    "SPOOKYPLATE": "원령플레이트", "DRACOPLATE": "용의플레이트", "DREADPLATE": "공포플레이트",
    "IRONPLATE": "강철플레이트", "ODDINCENSE": "괴상한향로", "ROCKINCENSE": "암석향로",
    "FULLINCENSE": "만복향로", "WAVEINCENSE": "잔물결향로", "ROSEINCENSE": "꽃향로",
    "RAZORCLAW": "예리한손톱", "RAZORFANG": "예리한이빨",
}

# ---------------------------------------------------------------- 분류표
# 그 타입 기술의 위력 1.2배 (타입 강화 도구 22 + 플레이트 16)
TYPE_BOOST = {
    "SILVERPOWDER": "BUG", "METALCOAT": "STEEL", "SOFTSAND": "GROUND",
    "HARDSTONE": "ROCK", "MIRACLESEED": "GRASS", "BLACKGLASSES": "DARK",
    "BLACKBELT": "FIGHTING", "MAGNET": "ELECTRIC", "MYSTICWATER": "WATER",
    "SHARPBEAK": "FLYING", "POISONBARB": "POISON", "NEVERMELTICE": "ICE",
    "SPELLTAG": "GHOST", "TWISTEDSPOON": "PSYCHIC", "CHARCOAL": "FIRE",
    "DRAGONFANG": "DRAGON", "SILKSCARF": "NORMAL", "SEAINCENSE": "WATER",
    "ODDINCENSE": "PSYCHIC", "ROCKINCENSE": "ROCK", "WAVEINCENSE": "WATER",
    "ROSEINCENSE": "GRASS",
    "FLAMEPLATE": "FIRE", "SPLASHPLATE": "WATER", "ZAPPLATE": "ELECTRIC",
    "MEADOWPLATE": "GRASS", "ICICLEPLATE": "ICE", "FISTPLATE": "FIGHTING",
    "TOXICPLATE": "POISON", "EARTHPLATE": "GROUND", "SKYPLATE": "FLYING",
    "MINDPLATE": "PSYCHIC", "INSECTPLATE": "BUG", "STONEPLATE": "ROCK",
    "SPOOKYPLATE": "GHOST", "DRACOPLATE": "DRAGON", "DREADPLATE": "DARK",
    "IRONPLATE": "STEEL",
}
TYPE_BOOST_MULT = 1.2

# 그 타입의 효과가 굉장한 기술을 한 번 반감 (카리열매는 노말이면 언제나)
RESIST_BERRY = {
    "OCCABERRY": "FIRE", "PASSHOBERRY": "WATER", "WACANBERRY": "ELECTRIC",
    "RINDOBERRY": "GRASS", "YACHEBERRY": "ICE", "CHOPLEBERRY": "FIGHTING",
    "KEBIABERRY": "POISON", "SHUCABERRY": "GROUND", "COBABERRY": "FLYING",
    "PAYAPABERRY": "PSYCHIC", "TANGABERRY": "BUG", "CHARTIBERRY": "ROCK",
    "KASIBBERRY": "GHOST", "HABANBERRY": "DRAGON", "COLBURBERRY": "DARK",
    "BABIRIBERRY": "STEEL", "CHILANBERRY": "NORMAL",
}

# 상태이상에 걸리는 순간 고친다. "*" 는 무엇이든.
CURE_BERRY = {
    "CHERIBERRY": "paralysis", "CHESTOBERRY": "sleep", "PECHABERRY": "poison",
    "RAWSTBERRY": "burn", "ASPEARBERRY": "freeze", "LUMBERRY": "*",
}

# 체력이 (비율) 이하가 되면 회복. ("flat", n) 은 n 만큼, ("frac", r) 은 최대체력의 r.
HEAL_BERRY = {
    "ORANBERRY": (0.5, "flat", 10),
    "SITRUSBERRY": (0.5, "frac", 0.25),
    "FIGYBERRY": (0.25, "frac", 1 / 3.0), "WIKIBERRY": (0.25, "frac", 1 / 3.0),
    "MAGOBERRY": (0.25, "frac", 1 / 3.0), "AGUAVBERRY": (0.25, "frac", 1 / 3.0),
    "IAPAPABERRY": (0.25, "frac", 1 / 3.0),
}

# 체력이 1/4 이하가 되면 발동. 애슈열매(먼저 움직임)는 순서 훅에서 본다.
PINCH_BERRY = {
    "LIECHIBERRY": ("stat", "atk"), "GANLONBERRY": ("stat", "def"),
    "SALACBERRY": ("stat", "spe"), "PETAYABERRY": ("stat", "spa"),
    "APICOTBERRY": ("stat", "spd"), "STARFBERRY": ("random", None),
    "LANSATBERRY": ("crit", None), "MICLEBERRY": ("acc", None),
}

# 구애: 그 능력 1.5배, 대신 처음 쓴 기술만 계속 쓴다 (판이 끝날 때까지).
CHOICE = {"CHOICEBAND": "atk", "CHOICESPECS": "spa", "CHOICESCARF": "spe"}

# 파워 시리즈: 쓰러뜨렸을 때 그 노력치 +8, 대신 스피드 절반.
POWER_EV = {"POWERBRACER": "atk", "POWERBELT": "def", "POWERLENS": "spa",
            "POWERBAND": "spd", "POWERANKLET": "spe", "POWERWEIGHT": "hp"}

SLOW = set(POWER_EV) | {"IRONBALL", "MACHOBRACE"}        # 스피드 절반
LAST = {"LAGGINGTAIL", "FULLINCENSE"}                      # 같은 우선도면 나중에
CRIT_UP = {"SCOPELENS": 1, "RAZORCLAW": 1}                 # 급소 단계 +1
FLINCH_10 = {"KINGSROCK", "RAZORFANG"}                     # 10% 풀죽음
EVADE = {"BRIGHTPOWDER", "LAXINCENSE"}                     # 상대 명중 0.9

# 배틀 밖에서만 뜻이 있는 것들. 서버가 본다.
EXP_ITEMS = {"LUCKYEGG": 1.5}
HAPPINESS_ITEMS = {"SOOTHEBELL": 1.5}

ALL = frozenset(KR)


def normalize(v):
    """DB 나 요청에서 온 값을 도구 id 로. 모르는 것은 None."""
    if not v:
        return None
    k = "".join(c for c in str(v).upper() if c.isalnum())
    return k if k in ALL else None


def name(item):
    return KR.get(item, item or "")


# ---------------------------------------------------------------- 도우미
def _say(ev, who, text):
    ev.append({"t": "msg", "who": who, "text": text})


def _heal(f, who, amount, ev, text):
    amount = max(1, int(amount))
    if f.hp >= f.maxhp:
        return 0
    amount = min(amount, f.maxhp - f.hp)
    f.hp += amount
    ev.append({"t": "heal", "who": who, "amount": amount, "hp": f.hp,
               "maxhp": f.maxhp, "text": text})
    return amount


def _chip(f, who, amount, ev, text):
    amount = max(1, int(amount))
    f.hp = max(0, f.hp - amount)
    ev.append({"t": "chip", "who": who, "damage": amount, "hp": f.hp,
               "maxhp": f.maxhp, "text": text})
    return amount


def _consume(f):
    """이 판에서는 사라진다. 판이 끝나면 돌아온다 (머리말 규칙 2)."""
    f.used = True


def _ready(f):
    """도구가 있고, 한 번 쓰는 것이라면 아직 안 썼는가."""
    return bool(f.held) and not f.used


# ---------------------------------------------------------------- 능력치
def stat_mult(f, key):
    """능력치에 곱할 값. Fighter.stat() 이 랭크·마비 다음에 곱한다."""
    h = f.held
    if not h:
        return 1.0
    if key == "spe":
        if h in SLOW:
            return 0.5
        if h == "CHOICESCARF":
            return 1.5
    elif key == "atk" and h == "CHOICEBAND":
        return 1.5
    elif key == "spa" and h == "CHOICESPECS":
        return 1.5
    return 1.0


# ---------------------------------------------------------------- 순서
def order_bias(bt, f, who, ev):
    """같은 우선도 안에서 순서를 당기면 +1, 미루면 -1, 아니면 0.

    선제공격손톱만 난수를 쓴다 - 도구가 없으면 난수를 건드리지 않는다.
    """
    h = f.held
    if not h:
        return 0
    if h in LAST:
        return -1
    if h == "QUICKCLAW":
        if bt.rng.random() < 0.2:
            _say(ev, who, "%s 의 선제공격손톱이 발동했다!" % f.name)
            return 1
        return 0
    if h == "CUSTAPBERRY" and not f.used and f.hp * 4 <= f.maxhp:
        _consume(f)
        _say(ev, who, "%s 은(는) 애슈열매로 먼저 움직인다!" % f.name)
        return 1
    return 0


def lock_pool(f, pool):
    """구애 도구를 들었으면 처음 쓴 기술만 남긴다. PP 가 없으면 풀어 준다."""
    if f.held in CHOICE and f.locked in pool:
        return [f.locked]
    return pool


def force_move(f, key, ev, who):
    """사람이 고른 기술도 구애 잠금을 받는다 (야생 배틀). 바꿨으면 그 기술."""
    if f.held in CHOICE and f.locked and key != f.locked \
            and f.pp.get(f.locked, 0) > 0:
        _say(ev, who, "%s 은(는) %s 때문에 %s 밖에 쓸 수 없다!"
             % (f.name, name(f.held), f.dex_move_name(f.locked)))
        return f.locked
    return key


def note_move(f, key):
    """기술을 쓴 뒤 기억할 것 - 구애 잠금, 메트로놈 연속 횟수."""
    if not f.held:
        return
    if f.held in CHOICE and f.locked is None and key in f.pp:
        f.locked = key
    if f.held == "METRONOME":
        f.metro = (f.metro + 1) if key == f.last_move else 0
    f.last_move = key


# ---------------------------------------------------------------- 명중 · 급소
def acc_mult(user, target):
    m = 1.0
    h = user.held
    if h == "WIDELENS":
        m *= 1.1
    elif h == "ZOOMLENS" and user.moved_second:
        m *= 1.2
    elif h == "MICLEBERRY" and user.armed:
        m *= 1.2
        user.armed = False                      # 한 번 쓰고 끝
    if target.held in EVADE:
        m *= 0.9
    return m


def crit_stages(f):
    s = CRIT_UP.get(f.held, 0)
    if f.held == "LANSATBERRY" and f.armed:
        s += 2
    return s


# ---------------------------------------------------------------- 데미지
def damage_mult(user, move, eff):
    """공격하는 쪽 도구가 위력에 곱하는 값."""
    h = user.held
    if not h:
        return 1.0
    m = 1.0
    t = TYPE_BOOST.get(h)
    if t and move.get("type") == t:
        m *= TYPE_BOOST_MULT
    cat = move.get("cat")
    if h == "MUSCLEBAND" and cat == "physical":
        m *= 1.1
    elif h == "WISEGLASSES" and cat == "special":
        m *= 1.1
    elif h == "EXPERTBELT" and eff > 1:
        m *= 1.2
    elif h == "LIFEORB":
        m *= 1.3
    elif h == "METRONOME" and user.metro:
        m *= min(2.0, 1.0 + 0.2 * user.metro)
    return m


def on_incoming(bt, target, who_t, move, eff, dmg, ev):
    """맞는 쪽 도구. 반감 열매를 먹고, 쓰러질 데미지면 1 을 남기고 버틴다."""
    h = target.held
    if not h:
        return dmg
    t = RESIST_BERRY.get(h)
    if t and not target.used and move.get("type") == t \
            and (eff > 1 or h == "CHILANBERRY"):
        _consume(target)
        dmg = max(1, dmg // 2)
        _say(ev, who_t, "%s 의 %s이(가) 데미지를 줄였다!" % (target.name, name(h)))
    if dmg >= target.hp and target.hp > 0:
        if h == "FOCUSSASH" and not target.used and target.hp == target.maxhp:
            _consume(target)
            _say(ev, who_t, "%s 은(는) 기합의띠로 버텼다!" % target.name)
            return target.hp - 1
        if h == "FOCUSBAND" and bt.rng.random() < 0.1:
            _say(ev, who_t, "%s 은(는) 기합의머리띠로 버텼다!" % target.name)
            return target.hp - 1
    return dmg


def after_hit(bt, user, who, target, who_t, move, eff, total, ev):
    """기술이 다 맞은 뒤. 공격한 쪽과 맞은 쪽 도구를 차례로 본다."""
    h = user.held
    if h and total > 0:
        if h == "LIFEORB" and user.alive():
            _chip(user, who, user.maxhp // 10, ev,
                  "%s 은(는) 생명의구슬로 체력이 조금 깎였다!" % user.name)
        elif h == "SHELLBELL":
            _heal(user, who, total // 8, ev,
                  "%s 은(는) 조개껍질방울로 체력을 조금 회복했다!" % user.name)
    ht = target.held
    if ht and not target.used and target.alive() and total > 0:
        cat = move.get("cat")
        if (ht == "JABOCABERRY" and cat == "physical") or \
                (ht == "ROWAPBERRY" and cat == "special"):
            _consume(target)
            if user.alive():
                _chip(user, who, user.maxhp // 8, ev,
                      "%s 은(는) %s 의 %s 때문에 데미지를 입었다!"
                      % (user.name, target.name, name(ht)))
        elif ht == "ENIGMABERRY" and eff > 1:
            _consume(target)
            _heal(target, who_t, target.maxhp // 4, ev,
                  "%s 은(는) 의문열매로 체력을 회복했다!" % target.name)


def flinch(bt, user, target, move):
    """왕의징표석·예리한이빨. 기술에 이미 풀죽음이 있으면 안 겹친다."""
    if user.held in FLINCH_10 and target.alive() and move.get("power") \
            and not move.get("flinch") and bt.rng.random() < 0.1:
        target.flinched = True


def drain_mult(f):
    return 1.3 if f.held == "BIGROOT" else 1.0


def restore_pp(f, key, maxpp, who, ev):
    """과사열매: 기술의 PP 가 바닥나면 10 회복. 한 번."""
    if f.held == "LEPPABERRY" and not f.used and key in f.pp \
            and f.pp.get(key, 0) <= 0:
        _consume(f)
        f.pp[key] = min(10, maxpp or 10)
        _say(ev, who, "%s 은(는) 과사열매로 %s 의 PP 를 회복했다!"
             % (f.name, f.dex_move_name(key)))


# ---------------------------------------------------------------- 체력 · 상태
def check_hp(bt, f, who, ev):
    """체력이 바뀐 뒤. 열매가 발동할 때인지 본다."""
    if not _ready(f) or not f.alive():
        return
    h = f.held
    spec = HEAL_BERRY.get(h)
    if spec:
        thr, kind, amt = spec
        if f.hp <= f.maxhp * thr and f.hp < f.maxhp:
            _consume(f)
            heal = amt if kind == "flat" else f.maxhp * amt
            _heal(f, who, heal, ev, "%s 은(는) %s로 체력을 회복했다!"
                  % (f.name, name(h)))
        return
    spec = PINCH_BERRY.get(h)
    if spec and f.hp * 4 <= f.maxhp:
        kind, stat = spec
        _consume(f)
        if kind == "stat":
            _say(ev, who, "%s 은(는) %s를 먹었다!" % (f.name, name(h)))
            bt._change_stat(f, stat, 1, ev, who)
        elif kind == "random":
            stat = bt.rng.choice(["atk", "def", "spa", "spd", "spe"])
            _say(ev, who, "%s 은(는) 스타열매를 먹었다!" % f.name)
            bt._change_stat(f, stat, 2, ev, who)
        elif kind == "crit":
            f.armed = True
            _say(ev, who, "%s 은(는) 랑사열매를 먹고 급소를 노린다!" % f.name)
        elif kind == "acc":
            f.armed = True
            _say(ev, who, "%s 은(는) 미클열매를 먹고 다음 기술의 명중률이 올랐다!"
                 % f.name)


def end_of_turn(bt, f, who, ev):
    """턴 끝. 상태이상 데미지 다음에 온다."""
    h = f.held
    if not h or not f.alive():
        return
    if h == "LEFTOVERS":
        _heal(f, who, f.maxhp // 16, ev,
              "%s 은(는) 먹다남은음식으로 체력을 조금 회복했다!" % f.name)
    elif h == "BLACKSLUDGE":
        if "POISON" in ((f.species or {}).get("types") or []):
            _heal(f, who, f.maxhp // 16, ev,
                  "%s 은(는) 검은오물로 체력을 조금 회복했다!" % f.name)
        else:
            _chip(f, who, f.maxhp // 8, ev,
                  "%s 은(는) 검은오물 때문에 데미지를 입었다!" % f.name)
    elif h == "STICKYBARB":
        _chip(f, who, f.maxhp // 8, ev,
              "%s 은(는) 끈적끈적바늘 때문에 데미지를 입었다!" % f.name)
    elif h == "TOXICORB" and not f.status:
        # 엔진에 맹독이 없어서 독으로 건다. 독 타입이면 _apply_status 가 막는다.
        bt._apply_status(f, "poison", ev)
    elif h == "FLAMEORB" and not f.status:
        bt._apply_status(f, "burn", ev)
    check_hp(bt, f, who, ev)


def on_status(bt, f, who, ev):
    """상태이상에 걸린 직후. 고치는 열매."""
    if not _ready(f) or not f.status:
        return
    want = CURE_BERRY.get(f.held)
    if want and (want == "*" or want == f.status):
        cured = f.status
        f.status = None
        f.sleep_turns = 0
        _consume(f)
        ev.append({"t": "cure", "who": who,
                   "text": "%s 은(는) %s로 %s 상태를 고쳤다!"
                           % (f.name, name(f.held), bt.status_kr(cured))})


def on_stat_drop(bt, f, who, ev):
    """능력이 떨어진 직후. 하양허브."""
    if f.held == "WHITEHERB" and not f.used \
            and any(v < 0 for v in f.stages.values()):
        for k, v in f.stages.items():
            if v < 0:
                f.stages[k] = 0
        _consume(f)
        _say(ev, who, "%s 은(는) 하양허브로 능력 하락을 되돌렸다!" % f.name)


def flee_sure(f):
    return f.held == "SMOKEBALL"


# ---------------------------------------------------------------- 배틀 밖 (서버)
def exp_mult(held):
    return EXP_ITEMS.get(normalize(held), 1.0)


def happiness_mult(held):
    return HAPPINESS_ITEMS.get(normalize(held), 1.0)


def ev_yield(held, yields):
    """쓰러뜨렸을 때 받는 노력치를 도구에 맞게 고친다."""
    h = normalize(held)
    if not h:
        return yields
    out = dict(yields or {})
    if h == "MACHOBRACE":
        return dict((k, v * 2) for k, v in out.items())
    stat = POWER_EV.get(h)
    if stat:
        out[stat] = out.get(stat, 0) + 8
    return out


# ---------------------------------------------------------------- 저장 · 복원
# 야생 배틀은 턴마다 서버를 오가서 Fighter 가 DB 에 잤다 깬다. 먹은
# 열매·구애 잠금이 턴 사이에 잊히면 열매를 매 턴 먹는다.
def state(f):
    if not f.held:
        return None
    return {"used": f.used, "locked": f.locked, "last": f.last_move,
            "metro": f.metro, "armed": f.armed}


def load(f, d):
    if not d or not f.held:
        return
    f.used = bool(d.get("used"))
    f.locked = d.get("locked")
    f.last_move = d.get("last")
    f.metro = int(d.get("metro") or 0)
    f.armed = bool(d.get("armed"))
