# -*- coding: utf-8 -*-
"""기술 연출.

기술마다 그림을 따로 그리는 건 900개라 불가능하다. 대신 PokeAPI 가 주는
**기술 플래그**와 **타입**을 조합해서 연출을 고른다. 본가도 결국
'접촉기는 달려들고, 원거리 특수기는 뭔가 날아간다' 는 규칙을 따른다.

    contact / punch / bite   달려들어 때린다 (주먹·이빨·베기 자국)
    ballistics               둥근 것이 포물선으로 날아간다
    pulse                    고리가 퍼지며 날아간다
    sound                    음파가 겹겹이 퍼진다
    powder                   가루가 흩날려 내려앉는다
    dance / heal / 자기대상    자기 몸에서 기운이 피어오른다
    그 외 특수기              타입 색의 줄기가 뿜어져 나간다 (화염방사 같은)

타입은 색과 모양을 정한다. 불꽃은 일렁이는 불덩이, 물은 물방울,
전기는 지그재그, 풀은 잎사귀... 하는 식이다.

전부 Canvas 도형으로 그린다. 이미지가 아니라서 크기를 바꿔도 깨지지 않고,
저작권 있는 그림을 쓰지 않는다.

**이 파일은 갈래를 고르는 일과 뼈대(Effect), 그리고 예전부터 있던 수수한 연출을
맡는다.** 많이 쓰이는 기술의 전용 연출(문포스의 달, 화염방사의 불길, 지진의 갈라진
땅 ...)과 맞는 순간의 타입별 충격은 move_fx.py 에 있다 (1.10.0). style_of 가 먼저
여기서 갈래를 고르고, move_fx.pick 이 그 기술만의 연출이 있으면 바꾼다.
"""
import math
import re
import time

# 타입별 색 (밝은색, 어두운색)
TYPE_FX = {
    "NORMAL":   ("#f2f0e4", "#b9b5a0"),
    "FIRE":     ("#ffd24a", "#ff5b2e"),
    "WATER":    ("#8ec9ff", "#2f7fd6"),
    "ELECTRIC": ("#fff27a", "#f2c400"),
    "GRASS":    ("#a8e86a", "#3f9e3a"),
    "ICE":      ("#d8fbff", "#63c8d8"),
    "FIGHTING": ("#ff9a7a", "#c33a52"),
    "POISON":   ("#e5a8ff", "#8f3fbf"),
    "GROUND":   ("#e8cf9a", "#b07a35"),
    "FLYING":   ("#e6ecff", "#8fa9de"),
    "PSYCHIC":  ("#ffb3d9", "#f0537a"),
    "BUG":      ("#d4f07a", "#7ba316"),
    "ROCK":     ("#ded0a8", "#9c8248"),
    "DARK":     ("#8f86a8", "#3a3348"),
    "DRAGON":   ("#9fb8ff", "#3352c4"),
    "STEEL":    ("#e0eaf0", "#7f9aa8"),
    "FAIRY":    ("#ffd6f2", "#e88fd0"),
    "GHOST":    ("#b9a8e0", "#5a4a8f"),
}
DEFAULT_FX = ("#f0f0f0", "#9a9a9a")

# 검사에서만 켠다. 켜면 연출 중의 예외를 삼키지 않고 그대로 올린다.
DEBUG = False


def annotate(events):
    """사건 줄의 '기술' 마다 그 뒤 '맞음' 의 급소 · 효과를 달아 둔다 (ev['_hit'], 1.13.2).

    연출(Effect)은 기술 사건 하나만 받아서, 이 한 방이 급소였는지 효과가 굉장했는지 몰랐다. 맞는 순간
    (move_fx.impact)을 그만큼 세게 그리려고 배틀 화면이 사건 줄을 받을 때 한 번 훑어 둔다. 여러 번
    때리는 기술은 가장 센 효과, 한 번이라도 급소면 급소다. 다음 기술이 나오면 거기서 끊는다.
    """
    cur = None
    for e in events or []:
        if not isinstance(e, dict):
            continue
        t = e.get("t")
        if t == "move":
            cur = e
        elif t in ("miss", "immune") and cur is not None and "_hit" not in cur:
            cur["_miss" if t == "miss" else "_immune"] = True     # 빗나갔다 · 효과가 없다 (연출이 비켜 가거나 조용해진다)
        elif t == "hit" and cur is not None:
            got = cur.setdefault("_hit", {"crit": False, "eff": 0.0})
            got["crit"] = got["crit"] or bool(e.get("crit"))
            try:
                got["eff"] = max(got["eff"], float(e.get("eff") if e.get("eff") is not None else 1.0))
            except (TypeError, ValueError):
                pass
    return events


def colors(mtype):
    return TYPE_FX.get(mtype, DEFAULT_FX)


# 이름으로 고르는 연출. **영문 이름의 낱말**을 먼저 본다.
#
# 한글은 부분문자열로만 볼 수 있어서 사고가 난다 - "꽃" 이 "불꽃" 에 걸려
# 불꽃 기술 9종이 잎으로 갔다. "풀" 은 화풀이·분풀이를, "발" 은 도발·묵사발을
# 데려왔다. 영문은 낱말로 끊을 수 있어서 그런 일이 없다.
#
# 919종 전부 영문 이름이 있다. 한글은 영문으로 못 잡은 것만 보조로 쓴다.
#
# **위에서부터 먼저 걸린다.** "Fire Fang" 처럼 두 갈래에 걸리는 이름이
# 있어서 순서가 곧 우선순위다.
NAME_STYLES = [
    # (갈래, 영문 낱말 앞부분, 한글 부분문자열, 안 걸릴 영문 낱말)
    ("quake", ("earthquake", "fissure", "magnitude", "bulldoze", "dig"),
     ("지진", "땅가르기", "구멍파기"), ()),
    ("bone", ("bone",), ("뼈",), ()),
    ("sleepz", ("rest", "hypnosis", "yawn"), ("잠자기", "최면"), ()),
    ("boom", ("explosion", "burst", "eruption", "blast", "bomb", "cannon"),
     ("폭발", "폭탄", "자폭", "분화"), ()),
    ("dance", ("dance",), ("춤",), ()),
    ("slash", ("sword", "blade", "cut", "slash", "slice", "razor", "guillotine",
               "knife", "scissor", "cleave", "sever"),
     ("칼", "베기", "자르기", "가위", "썰기"), ()),
    ("claw", ("claw", "scratch", "rake", "swipe", "shred"), ("할퀴", "발톱"), ()),
    ("bite", ("bite", "fang", "crunch", "chomp"), ("물기", "이빨", "깨물"), ()),
    ("punch", ("punch", "fist", "chop"), ("펀치", "주먹", "당수"), ()),
    ("kick", ("kick", "stomp", "trample", "stamp"), ("킥", "차기", "밟기"), ()),
    ("stab", ("horn", "drill", "peck", "spear", "lance"),
     ("뿔", "드릴", "쪼기", "찌르기"), ()),
    ("throw", ("throw", "fling", "toss", "present"),
     ("던지기", "투척", "뿌리기"), ()),
    ("rock", ("rock", "stone", "boulder"), ("바위", "스톤", "암석", "돌떨"), ()),
    ("leaf", ("leaf", "petal", "bloom", "flower", "vine", "seed", "grass"),
     ("잎", "덩굴", "새싹"), ()),
    ("ice", ("freeze", "frost", "blizzard", "glaciate", "avalanche", "icicle",
             "ice", "hail"), ("냉동", "눈보라", "서리", "고드름"), ("petal",)),
    ("wind", ("wing", "gust", "hurricane", "tornado", "twister", "air",
              "aeroblast", "whirlwind", "feather", "storm", "bounce", "fly"),
     ("날개", "회오리", "공중", "깃털", "폭풍"), ("throw",)),
    ("flash", ("flash", "shine", "dazzling", "glitter", "sparkle", "swift",
               "gleam", "luster", "star"), ("섬광", "플래시", "반짝"), ()),
    ("sound", ("song", "sing", "roar", "howl", "cry", "screech", "noise",
               "echo", "chatter", "voice", "shout", "boomburst", "snore",
               "uproar", "growl"), ("노래", "울음", "음파", "외침", "함성"),
     ("poisongas",)),
    ("powder", ("powder", "dust", "spore"), ("가루", "포자", "분진"), ()),
    ("laser", ("beam", "laser", "ray"), ("광선", "레이저"), ()),
    ("ball", ("ball", "orb", "sphere", "shot"), ("구슬",), ("weather",)),
    ("pulse", ("pulse", "wave"), ("파동", "물결"), ("terrain",)),
]


# 변화기가 이름에서 받는 '전하는 법' (나머지 이름 갈래는 공격기만 쓴다) · 그중 상대에게 날아가는 것
STATUS_WAYS = ("sleepz", "dance", "sound", "powder", "wind", "flash", "leaf", "throw", "rock")
STATUS_FLY = ("flash", "leaf", "throw", "rock")


def _toks(en):
    return re.findall(r"[a-z]+", (en or "").lower())


def _by_name(move):
    """이름으로 갈래를 고른다. 못 고르면 None.

    영문은 **낱말 앞부분**으로 본다 ("punching" 도 "punch" 로 잡힌다).
    한글은 부분문자열이라 두 글자 이상만 쓴다.
    """
    en = move.get("en") or ""
    kr = move.get("kr") or ""
    ts = _toks(en)
    flat = en.lower().replace(" ", "")
    for style, words, krw, skip in NAME_STYLES:
        if skip and any(x in flat for x in skip):
            continue
        if any(t.startswith(w) for t in ts for w in words):
            return style
        if any(w in kr for w in krw):
            return style
    return None


def style_of(move):
    """기술 하나가 쓸 연출 이름.

    먼저 아래 _base_style 로 갈래를 고르고, move_fx 가 그 기술만의 연출이
    있으면 그것으로 바꾼다 (문포스·화염방사·지진 ...).
    """
    from . import move_fx                    # 저쪽이 이 모듈의 도형을 쓴다 - 부를 때 불러온다
    return move_fx.pick(move, _base_style(move))


def _base_style(move):
    """기술 하나가 어떤 갈래인지 고른다.

    세 겹으로 고른다. 위에서 걸리면 아래는 안 본다.
      1. **이름의 낱말** - 칼춤이면 칼, 뼈다귀면 뼈. 눈에 띄는 기술들이
         여기서 자기 모양을 갖는다.
      2. **하는 일** - 회복·흡수·랭크변화처럼 자료에 적힌 것.
      3. **타입과 분류** - 나머지 전부. 예전부터 쓰던 갈래다.

    예전에는 3번만 있어서 919종 중 350종(38%)이 전부 같은 'beam' 이었다.
    뼈다귀치기와 냉동빔과 파괴광선이 구분이 안 됐다.
    """
    flags = set(move.get("flags") or [])
    cat = move.get("cat") or "status"
    target = move.get("target") or 10
    kr = move.get("kr") or ""
    # target 6 은 **상대 진영**이다(압정뿌리기·스텔스록). 자기 쪽으로
    # 치면 자기 발밑에서 터진다.
    on_self = target in (7, 5, 3, 13, 15, 4)

    # --- 1. 이름 ---
    named = _by_name(move)
    if named and cat == "status":
        # 변화기는 때리지 않는다. 이름에서는 '전하는 법'(소리 · 가루 · 춤 · 바람 · 던지기 ...)만 받고, 무기 모양
        # (광선 · 칼 · 발톱 · 지진 ...)은 버린다 - 이상한빛이 파괴광선처럼 나가고 손톱갈기가 상대를 할퀴었다.
        # 자기에게 쓰는 기술이 날아가는 것도 어색하다.
        if named not in STATUS_WAYS or (on_self and named in STATUS_FLY):
            named = None
    if named:
        # 자기에게 쓰는 기술인데 날아가는 연출이면 어색하다.
        if on_self and named in ("bone", "throw", "rock", "laser", "ball",
                                 "quake", "boom", "ice", "leaf"):
            pass
        else:
            return named

    # --- 2. 하는 일 ---
    if (move.get("heal") or 0) > 0 and cat == "status":
        return "heal"                       # (발버둥은 heal 이 음수다 - 반동이지 회복이 아니다)
    drain = move.get("drain") or 0
    if drain > 0:
        return "drain"
    if drain < 0:
        return "recoil"
    stats = move.get("stat") or []
    if stats and cat == "status":
        up = any(c > 0 for _s, c in stats)
        if move.get("statSelf"):
            return "buff" if up else "selfdown"
        return "debuff"
    hits = move.get("hits") or [1, 1]
    if len(hits) > 1 and hits[1] > 1:
        return "multi"
    if move.get("ail") and cat == "status":
        return "hex"

    # --- 3. 타입과 분류 ---
    if on_self or "dance" in flags or "heal" in flags:
        return "self"
    if "powder" in flags:
        return "powder"
    if "sound" in flags:
        return "sound"
    if "punch" in flags:
        return "punch"
    if "bite" in flags:
        return "bite"
    if "pulse" in flags:
        return "pulse"
    if "ballistics" in flags:
        return "ball"
    if "contact" in flags:
        return "hit"
    if cat == "status":
        return "hex"
    if cat == "physical":
        # 닿지 않는 물리기는 타입의 것을 던진다. 플래그도 이름도 모르는 기술(도감에 없는 것)은 달려들어 친다
        return "shot" if (flags or move.get("en")) else "hit"
    return "stream"


# ---------------------------------------------------------------- 도형 조각
def _blob(cv, x, y, r, fill, outline=""):
    return cv.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline=outline)


def _flame(cv, x, y, r, light, dark):
    """불꽃 모양 조각."""
    pts = []
    n = 9
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r * (1.35 if i % 2 == 0 else 0.62)
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr * 1.15 - r * 0.25]
    return cv.create_polygon(pts, fill=dark, outline=light, width=1, smooth=True)


def _drop(cv, x, y, r, light, dark):
    """물방울."""
    return cv.create_polygon(
        x, y - r * 1.5, x + r, y + r * 0.4, x, y + r, x - r, y + r * 0.4,
        fill=dark, outline=light, width=1, smooth=True)


def _bolt(cv, x, y, r, light, dark):
    """번개 지그재그."""
    return cv.create_line(x - r, y - r, x + r * 0.3, y - r * 0.2,
                          x - r * 0.3, y + r * 0.2, x + r, y + r,
                          fill=light, width=max(2, int(r * 0.5)))


def _leaf_shape(cv, x, y, r, light, dark, ang=0.0):
    """잎 하나. ang 을 주면 그만큼 돌린다.

    Canvas 는 도형을 돌리는 기능이 없다. 좌표를 직접 돌려서 다각형을 만든다.
    """
    a = math.radians(ang)
    c, s_ = math.cos(a), math.sin(a)
    pts = []
    for dx, dy in ((-r, 0), (0, -r * 0.7), (r, 0), (0, r * 0.7)):
        pts += [x + dx * c - dy * s_, y + dx * s_ + dy * c]
    return cv.create_polygon(*pts, fill=light, outline=dark, width=2)


def _leaf(cv, x, y, r, light, dark):
    return cv.create_polygon(x - r, y, x, y - r * 0.8, x + r, y, x, y + r * 0.8,
                             fill=dark, outline=light, width=1, smooth=True)


def _shard(cv, x, y, r, light, dark):
    return cv.create_polygon(x, y - r * 1.3, x + r * 0.7, y, x, y + r * 1.3,
                             x - r * 0.7, y, fill=light, outline=dark, width=1)


def _star(cv, x, y, r, light, dark):
    pts = []
    for i in range(10):
        a = math.pi * i / 5 - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.45
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
    return cv.create_polygon(pts, fill=light, outline=dark, width=1)


PARTICLE = {
    "FIRE": _flame, "WATER": _drop, "ELECTRIC": _bolt, "GRASS": _leaf,
    "ICE": _shard, "PSYCHIC": _star, "FAIRY": _star, "BUG": _leaf,
    "DRAGON": _shard, "GHOST": _blob, "POISON": _blob,
}


def particle(cv, mtype, x, y, r):
    light, dark = colors(mtype)
    fn = PARTICLE.get(mtype)
    if fn is None:
        return _blob(cv, x, y, r, dark, light)
    return fn(cv, x, y, r, light, dark)


# ---------------------------------------------------------------- 연출 재생
# ---- 이빨 (물기·깨물어부수기·불꽃엄니 ...) ----
FANG_TEETH = 4                  # 윗니 수 (아랫니는 하나 적게, 반 칸 비켜 선다)
FANG_GAP = 18                   # 이빨 사이
FANG_W = 12                     # 이빨 밑변
FANG_H = 22                     # 이빨 길이
FANG_BITE = 4                   # 다 닫혔을 때 끝이 가운데를 넘는 만큼 (맞물린다)
FANG_OPEN = (36, 26, 16, 7, 0)  # 벌어진 정도 - 한 칸씩 닫힌다
FANG_STEP_MS = 30
FANG_HOLD_MS = 90


def fang_rows(tx, ty, gap=0):
    """윗니·아랫니 다각형 좌표. gap 은 다 닫힌 자리에서 벌어진 만큼(px).

    **두 줄 다 과녁(tx) 가운데에 선다.** 윗니는 위에서 아래를, 아랫니는
    아래에서 위를 보고, 아랫니는 반 칸 비켜 서서 윗니 사이로 들어간다.
    각 이빨은 (밑 왼쪽, 끝, 밑 오른쪽) 세 점.
    """
    half = (FANG_TEETH - 1) * FANG_GAP / 2.0
    up_tip = ty + FANG_BITE - gap
    lo_tip = ty - FANG_BITE + gap
    upper = []
    for k in range(FANG_TEETH):
        x = tx - half + k * FANG_GAP
        base = up_tip - FANG_H
        upper.append((x - FANG_W / 2.0, base, x, up_tip, x + FANG_W / 2.0, base))
    lower = []
    for k in range(FANG_TEETH - 1):
        x = tx - half + FANG_GAP / 2.0 + k * FANG_GAP
        base = lo_tip + FANG_H
        lower.append((x - FANG_W / 2.0, base, x, lo_tip, x + FANG_W / 2.0, base))
    return upper, lower


# ---------------------------------------------------------------- 숨는 기술 (2.0)
OTHER = {"me": "foe", "foe": "me", "a": "b", "b": "a"}


class Hiding(object):
    """숨는 기술로 지금 모습을 감춘 포켓몬 - 공중날기·뛰어오르다·프리폴·구멍파기·다이빙·고스트다이브·섀도다이브.

    서버가 두 턴 기술의 **첫 턴** 기술 사건에 charge 를 단다: 숨는 자리('fly' 'dig' 'dive' 'vanish'),
    숨지 않고 모으기만 하면 'power' (솔라빔·로켓박치기 ...). 프리폴은 carry 도 단다 - 상대를 데리고 올라간다.
    그 턴에는 공격 연출 대신 숨는 연출을 틀고(vanish_fx), 숨은 포켓몬은 **그 쪽이 다음 기술을 쓸 때** 다시
    나타난다. 둘째 턴에 마비 등으로 못 움직이면 엔진도 숨긴 채로 두므로 화면도 그대로 둔다.

    배틀 화면마다 하나 둔다. 키는 그 화면이 포켓몬을 가리키는 것 그대로다 ("me"/"foe", 구경은 "a"/"b",
    레이드는 자리). show(key, on) 은 화면이 준다 - 그 도트를 바로 보이거나 감춘다. 바뀔 때만 부른다 -
    바탕화면 도트는 다시 보일 때 창을 다시 띄우므로(PLAT.show_again) 괜히 부르면 안 된다.

    화면이 할 일: 새 포켓몬이 나오거나(교체·불러들임) 쓰러지면 forget, 도트를 다시 그렸으면(창 크기·폼)
    apply, 판이 끝나면 forget_all.
    """

    def __init__(self, show):
        self.show = show
        self.kind = {}            # key -> 숨은 자리
        self.held = {}            # 프리폴: 데려간 쪽 key -> 끌려간 쪽 key
        self.vis = {}             # key -> 마지막으로 건 보임 (모르면 보이는 것)

    def hidden(self, key):
        return self.kind.get(key)

    def hide(self, key, kind):
        self.kind[key] = kind
        self.set(key, False)

    def come_out(self, key):
        """다시 나온다 - 기록만 지운다 (보이게 하는 것은 연출이 한다). 데려간 상대도 같이 나온다.

        나오는 쪽들을 [(key, 숨었던 자리)] 로 돌려준다.
        """
        out = []
        kind = self.kind.pop(key, None)
        if kind:
            out.append((key, kind))
        carried = self.held.pop(key, None)
        if carried is not None and self.kind.get(carried):
            out.append((carried, self.kind.pop(carried)))
        return out

    def forget(self, key):
        """새 포켓몬이 나오거나 쓰러졌다 - 숨김을 풀고 바로 보이게 한다. 그 쪽이 데려간 상대도 놓인다."""
        keys = [key]
        if key in self.held:
            keys.append(self.held.pop(key))
        for k, v in list(self.held.items()):
            if v == key:
                self.held.pop(k)
        for k in keys:
            if self.kind.pop(k, None):
                self.set(k, True)

    def forget_all(self):
        for k in list(self.kind):
            self.forget(k)
        self.held = {}

    def apply(self, key):
        """도트를 다시 그렸다 (창 크기를 바꿨다·폼이 바뀌었다) - 숨김을 다시 건다."""
        self.set(key, not self.kind.get(key), force=True)

    def sync(self, key):
        """숨김 기록대로 보이거나 감춘다 (연출이 끝날 때)."""
        self.set(key, not self.kind.get(key))

    def set(self, key, on, force=False):
        if not force and self.vis.get(key, True) == on:
            return
        self.vis[key] = on
        try:
            self.show(key, on)
        except Exception:                                   # noqa: BLE001
            if DEBUG:
                raise


class Effect(object):
    """캔버스 위에서 도는 연출 하나. 시간표(fx_kit.Show) 하나로 스스로 굴러간다.

    부르는 쪽과의 약속 (배틀 화면들이 다 이대로 쓴다):

        Effect(stage, move, src, dst, on_done, who=, ev=, keys=).play()   /   stop()   /   dead
        stage.cv · stage.root · stage.lunge(who, done)      꼭 있어야 한다
        stage.fx_shift(key, dx, dy) · fx_box(key) · hiding  있으면 도트를 밀고 · 숨긴다 (없으면 그 연출만 뺀다)
        stage.fx_clock()                                    (있으면) 지금 시각 ms - 미리보기의 느린 재생

    on_done 은 꼭 한 번 온다 (stop 하면 안 온다). 이 연출이 옮기거나 감춘 도트는 끝날 때(멈출 때도) 제자리로 돌린다.
    keys = (쓰는 쪽, 맞는 쪽) 을 무대가 부르는 이름. 안 주면 who 와 그 맞은편이다.

    숨는 기술 (2.0): 무대에 hiding(Hiding)이 있으면 숨는 · 다시 나오는 연출을 튼다 (vanish_fx).
    """

    def __init__(self, stage, move, src, dst, on_done, who="me", ev=None, keys=None):
        from . import fx_kit
        self.st = stage
        self.who = who
        self.cv = stage.cv
        self.root = stage.root
        self.move = move or {}
        self.type = self.move.get("type") or "NORMAL"
        self.c = fx_kit.tone(self.type)
        self.style = style_of(self.move)
        # 센 기술일수록 크게 그린다 (변화기는 1.0)
        p = self.move.get("power") or 0
        self.big = 1.0 if not p else 0.85 if p < 60 else 1.0 if p < 100 else 1.18 if p < 130 else 1.35
        self.src = src
        self.dst = dst
        self.on_done = on_done
        self.items = []
        self.jobs = []
        self.dead = False
        # 그 기술 사건 (1.13.2). 급소 · 효과(annotate 가 달아 둔 것)와 Z기술인지를 본다 - 없으면 보통으로 그린다.
        ev = ev if isinstance(ev, dict) else {}
        hit = ev.get("_hit") or {}
        self.crit = bool(hit.get("crit"))
        self.eff = float(hit.get("eff") or 1.0)
        self.miss = bool(ev.get("_miss"))           # 빗나갔다 - 과녁 옆에 떨어지고 도트는 안 밀린다
        self.immune = bool(ev.get("_immune"))       # 효과가 없다 - 맞아도 꿈쩍 않는다
        self.zmove = bool(ev.get("z"))
        self.label = ev.get("move") or self.move.get("kr") or ""
        self.charge = ev.get("charge")              # 두 턴 기술의 첫 턴 (Hiding)
        self.carry = bool(ev.get("carry"))          # 프리폴 - 상대도 데리고 간다
        self.stay = bool(ev.get("stay"))            # 숨은 채로 따라 쓴 기술 (춤추기 ...) - 숨은 채 둔다
        self.keys = tuple(keys) if keys else (who, OTHER.get(who, "foe"))
        self.hiding = getattr(stage, "hiding", None)
        self.moved = {}                             # key -> [dx, dy] 이 연출이 옮겨 둔 도트
        self.touched = set()                        # 이 연출이 보이고 감춘 도트
        if self.miss:                               # 과녁을 비켜 간다 (머리 위 뒤쪽)
            dx = dst[0] - src[0]
            self.dst = (dst[0] + (22 if dx >= 0 else -22), dst[1] - 36)
        # 시각. 느린 PC 에서도 길어지지 않게 실제 시각으로 굴린다 (검사 · 미리보기는 제 시계를 준다)
        clk = getattr(stage, "fx_clock", None)
        if clk is None:
            if isinstance(getattr(self.root, "now", None), (int, float)):
                clk = lambda r=self.root: r.now                         # noqa: E731  (검사의 흉내 시계)
            else:
                clk = lambda: time.monotonic() * 1000.0                 # noqa: E731
        self.clock = clk
        self._show = None
        self._geo = None
        # 그림 바탕: 도형 대신 그림 한 장으로 그린다 (fx_raster). 못 쓰는 무대는 지금까지처럼 도형으로 그린다.
        self.surface = None
        try:
            from . import fx_raster
            # 배틀 창의 무대는 fx_raster 로 말한다. 말이 없는 무대(바탕화면 배틀)는 캔버스를 보고 정한다
            ras = stage.fx_raster if hasattr(stage, "fx_raster") else fx_raster.for_canvas(self.cv)
        except Exception:                                   # noqa: BLE001
            ras = None
        if ras is not None and ras is not False:
            try:
                self.surface = fx_raster.open_surface(self, ras)
            except Exception:                               # noqa: BLE001
                if DEBUG:
                    raise

    # ---- 시간표 · 길 ----
    @property
    def show(self):
        if self._show is None:
            from . import fx_kit
            self._show = fx_kit.Show(self)
        return self._show

    @property
    def geo(self):
        if self._geo is None:
            from . import fx_kit
            self._geo = fx_kit.Geo(self)
        return self._geo

    @staticmethod
    def debug():
        return DEBUG

    # ---- 도트 (숨는 기술 · 맞고 밀리는 몸) ----
    def body_move(self, key, dx, dy):
        fn = getattr(self.st, "fx_shift", None)
        if fn is None or (not dx and not dy):
            return
        try:
            fn(key, dx, dy)
        except Exception:                                   # noqa: BLE001
            if DEBUG:
                raise
            return
        m = self.moved.setdefault(key, [0.0, 0.0])
        m[0] += dx
        m[1] += dy

    def body_home(self, key):
        m = self.moved.pop(key, None)
        if m and (m[0] or m[1]):
            fn = getattr(self.st, "fx_shift", None)
            try:
                fn(key, -m[0], -m[1])
            except Exception:                               # noqa: BLE001
                if DEBUG:
                    raise

    def body_show(self, key, on):
        if self.hiding is not None:
            self.touched.add(key)
            self.hiding.set(key, on)

    def body_box(self, key):
        """그 도트의 테두리 (x0, y0, x1, y1). 모르면 None."""
        fn = getattr(self.st, "fx_box", None)
        try:
            return fn(key) if fn else None
        except Exception:                                   # noqa: BLE001
            return None

    def hidden(self, key):
        """그 도트가 지금 숨어 있나 (공중날기 · 구멍파기 ...)."""
        return bool(self.hiding is not None and self.hiding.hidden(key))

    # ---- 도구 ----
    def after(self, ms, fn):
        if self.dead:
            return
        self.jobs.append(self.root.after(ms, fn))

    def add(self, item):
        self.items.append(item)
        return item

    def clear(self):
        if self._show is not None:
            self._show.wipe()
        for i in self.items:
            try:
                self.cv.delete(i)
            except Exception:
                pass
        self.items = []

    def finish(self):
        if self.dead:
            return
        self.dead = True
        for j in self.jobs:
            try:
                self.root.after_cancel(j)
            except Exception:
                pass
        self.jobs = []
        if self._show is not None:
            self._show.stop()
        if self.surface is not None:
            try:
                self.surface.clear()
                self.surface.close()
            except Exception:                               # noqa: BLE001
                pass
        self.clear()
        # 옮긴 도트를 제자리로, 보임은 숨김 기록대로 (도중에 멈춰도 어긋난 채로 남지 않게)
        for key in list(self.moved):
            self.body_home(key)
        if self.hiding is not None:
            for key in self.touched:
                self.hiding.sync(key)
        if self.on_done:
            self.on_done()

    def stop(self):
        self.on_done = None
        self.finish()

    # ---- 시작 ----
    def play(self):
        # 숨는 기술 (2.0): 첫 턴이면 공격 대신 숨는·모으는 연출, 숨어 있던 쪽이면 다시 나온 뒤에 공격
        from . import vanish_fx
        if vanish_fx.takes(self):
            try:
                return vanish_fx.play(self, self._play_move)
            except Exception:
                if DEBUG:
                    raise
                return self.finish()
        return self._play_move()

    def _play_move(self):
        # **쏘는 자세(Shoot/Charge)는 안 넣는다.** 동작마다 칸 크기가 달라서 창이 커졌다 작아지는데, 이 연출은
        # 도트 좌표를 잡아 두고 그리는 것이라 그 사이에 그림이 튄다.
        from . import move_fx
        fn = move_fx.STYLES.get(self.style) or move_fx.STYLES[move_fx.FALLBACK]
        if self.surface is not None:                # [시범] 그림 바탕에 맞춰 다시 그린 연출이 있으면 그것을
            from . import fx_raster_demo
            fn = fx_raster_demo.STYLES.get(self.style, fn)

        def go():
            if self.dead:
                return
            try:
                self.show.rebase()
                fn(self)
                self.show.kick()                # 아무것도 안 넣은 연출도 끝은 난다
            except Exception:
                if DEBUG:
                    raise
                self.finish()
        # Z기술 · 아주 센 기술은 쓰기 직전에 띠가 지나가며 기술 이름이 뜬다 (move_fx.cutin, 1.13.2)
        if move_fx.wants_cutin(self):
            try:
                return move_fx.cutin(self, go)
            except Exception:
                if DEBUG:
                    raise
        go()

    def src_side(self):
        return self.who

    # ---- 마무리 충격 ----
    def burst(self):
        """맞는 순간. 그리던 것을 걷고 타입에 맞는 충격을 얹는다 (fx_kit.impact)."""
        self.clear()
        from . import fx_kit
        self.show.rebase()
        fx_kit.impact(self)
