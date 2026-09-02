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
"""
import math
import re
import random

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
    ("beam", ("beam", "laser", "ray", "breath"), ("광선", "레이저", "숨결"), ()),
    ("ball", ("ball", "orb", "sphere", "shot"), ("구슬",), ("weather",)),
    ("pulse", ("pulse", "wave"), ("파동", "물결"), ("terrain",)),
]


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
    """기술 하나가 어떤 연출을 쓸지 고른다.

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
    if named:
        # 자기에게 쓰는 기술인데 날아가는 연출이면 어색하다.
        # 칼춤·검무처럼 자기 강화인 것은 그대로 두고, 나머지만 되돌린다.
        if on_self and named in ("bone", "throw", "rock", "beam", "ball",
                                 "quake", "boom", "ice", "leaf"):
            pass
        else:
            return named

    # --- 2. 하는 일 ---
    if move.get("heal"):
        return "heal"
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
        return "contact"
    if cat == "status":
        return "hex"
    return "beam"


def contact_style(style):
    """때리는 쪽이 달려들어야 하는 연출인지."""
    return style in ("contact", "punch", "bite", "kick", "slash", "multi")


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
class Effect(object):
    """캔버스 위에서 도는 연출 하나. root.after 로 스스로 굴러간다."""

    def __init__(self, stage, move, src, dst, on_done, who="me"):
        self.st = stage
        self.who = who
        self.cv = stage.cv
        self.root = stage.root
        self.move = move or {}
        self.type = self.move.get("type") or "NORMAL"
        self.style = style_of(self.move)
        self.src = src
        self.dst = dst
        self.on_done = on_done
        self.items = []
        self.jobs = []
        self.dead = False

    # ---- 도구 ----
    def after(self, ms, fn):
        if self.dead:
            return
        self.jobs.append(self.root.after(ms, fn))

    def add(self, item):
        self.items.append(item)
        return item

    def clear(self):
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
        self.clear()
        if self.on_done:
            self.on_done()

    def stop(self):
        self.on_done = None
        self.finish()

    # ---- 시작 ----
    def play(self):
        fn = getattr(self, "_" + self.style, None) or self._beam
        try:
            fn()
        except Exception:
            self.finish()

    # ---- 각 연출 ----
    def _beam(self):
        """타입 색 줄기가 뿜어져 나간다 (화염방사, 냉동빔 같은)."""
        sx, sy = self.src
        tx, ty = self.dst
        n = 16

        def step(i):
            if self.dead:
                return
            if i > n:
                return self.burst()
            t = i / float(n)
            x = sx + (tx - sx) * t
            y = sy + (ty - sy) * t
            for k in range(2):
                r = 7 + 5 * math.sin(i * 0.7 + k)
                self.add(particle(self.cv, self.type,
                                  x + random.uniform(-9, 9),
                                  y + random.uniform(-9, 9), r))
            if i > 6:                        # 꼬리부터 지워서 줄기처럼 보이게
                for _ in range(2):
                    if self.items:
                        self.cv.delete(self.items.pop(0))
            self.after(26, lambda: step(i + 1))
        step(0)

    def _ball(self):
        """둥근 것이 포물선으로 날아간다."""
        sx, sy = self.src
        tx, ty = self.dst
        light, dark = colors(self.type)
        core = self.add(_blob(self.cv, sx, sy, 11, dark, light))
        n = 18

        def step(i):
            if self.dead:
                return
            if i > n:
                return self.burst()
            t = i / float(n)
            x = sx + (tx - sx) * t
            y = sy + (ty - sy) * t - 70 * (t - t * t) * 4
            self.cv.coords(core, x - 11, y - 11, x + 11, y + 11)
            trail = self.add(_blob(self.cv, x, y, 6, light))
            self.after(180, lambda it=trail: self.cv.delete(it))
            self.after(24, lambda: step(i + 1))
        step(0)

    def _pulse(self):
        """고리가 퍼지며 날아간다."""
        sx, sy = self.src
        tx, ty = self.dst
        light, dark = colors(self.type)
        n = 16

        def step(i):
            if self.dead:
                return
            if i > n:
                return self.burst()
            t = i / float(n)
            x = sx + (tx - sx) * t
            y = sy + (ty - sy) * t
            r = 10 + i * 1.6
            ring = self.add(self.cv.create_oval(x - r, y - r * 0.7, x + r, y + r * 0.7,
                                                outline=light, width=3))
            self.after(220, lambda it=ring: self.cv.delete(it))
            self.after(28, lambda: step(i + 1))
        step(0)

    def _sound(self):
        """음파가 상대 쪽으로 겹겹이 퍼진다."""
        sx, sy = self.src
        tx, _ty = self.dst
        # tkinter 의 0도는 **오른쪽**이다. 각도를 고정해 두면 누가 쓰든
        # 음파가 오른쪽으로만 나가서, 오른쪽에 선 상대가 울음소리를 쓰면
        # 나를 등지고 퍼진다. 부채꼴의 기준을 목표 방향으로 잡는다.
        base = 0 if tx >= sx else 180
        light, dark = colors(self.type)

        def wave(k):
            if self.dead:
                return
            if k >= 4:
                return self.after(220, self.burst)
            r = [0]

            def grow(i):
                if self.dead:
                    return
                if i > 12:
                    return
                rr = 14 + i * 16
                if r[0]:
                    self.cv.delete(r[0])
                r[0] = self.cv.create_arc(sx - rr, sy - rr, sx + rr, sy + rr,
                                          start=base - 50, extent=100,
                                          style="arc", outline=light, width=3)
                self.items.append(r[0])
                self.after(34, lambda: grow(i + 1))
            grow(0)
            self.after(120, lambda: wave(k + 1))
        wave(0)

    def _powder(self):
        """가루가 흩날려 내려앉는다."""
        sx, sy = self.src
        tx, ty = self.dst
        light, dark = colors(self.type)
        bits = []
        for _ in range(22):
            x = sx + random.uniform(-14, 14)
            y = sy + random.uniform(-14, 14)
            bits.append([self.add(_blob(self.cv, x, y, random.uniform(2, 4),
                                        light)), x, y,
                         random.uniform(0.6, 1.4), random.uniform(-0.4, 0.9)])

        def step(i):
            if self.dead:
                return
            if i > 26:
                return self.burst()
            for b in bits:
                item, x, y, vx, vy = b
                x += (tx - sx) / 26.0 * vx
                y += (ty - sy) / 26.0 * vx + vy
                b[1], b[2] = x, y
                r = 3
                self.cv.coords(item, x - r, y - r, x + r, y + r)
            self.after(30, lambda: step(i + 1))
        step(0)

    def _self(self):
        """자기 몸에서 기운이 피어오른다 (능력 상승, 회복, 춤)."""
        sx, sy = self.src
        light, dark = colors(self.type)
        bits = []
        for k in range(14):
            a = 2 * math.pi * k / 14
            bits.append([None, a, 0])

        def step(i):
            if self.dead:
                return
            if i > 20:
                return self.finish()
            for b in bits:
                if b[0]:
                    self.cv.delete(b[0])
                a = b[1] + i * 0.18
                rad = 16 + i * 2.2
                x = sx + math.cos(a) * rad
                y = sy + math.sin(a) * rad * 0.5 - i * 2.4
                b[0] = self.cv.create_oval(x - 4, y - 4, x + 4, y + 4,
                                           fill=light, outline=dark)
                self.items.append(b[0])
            self.after(34, lambda: step(i + 1))
        step(0)

    def _hex(self):
        """상대에게 거는 변화기. 고리가 상대를 감싼다."""
        tx, ty = self.dst
        light, dark = colors(self.type)

        def step(i):
            if self.dead:
                return
            if i > 14:
                return self.finish()
            r = 46 - i * 2.4
            ring = self.add(self.cv.create_oval(tx - r, ty - r * 0.8,
                                                tx + r, ty + r * 0.8,
                                                outline=light, width=3))
            self.after(200, lambda it=ring: self.cv.delete(it))
            self.after(34, lambda: step(i + 1))
        step(0)

    # ---- 접촉기: 때리는 쪽이 달려든 뒤 자국이 남는다 ----
    # ------------------------------------------------------------------
    # 아래는 이름으로 갈라진 연출들. 예전에는 919종 중 350종이 전부
    # 같은 'beam' 이라 뼈다귀치기와 냉동빔이 구분되지 않았다.
    # ------------------------------------------------------------------
    def _fly(self, shape, n=14, spin=0, arc=0):
        """무언가를 상대에게 날린다.

        shape(x, y, t) 가 한 프레임의 도형을 만들어 돌려준다. t 는 0~1.
        spin 을 주면 돌면서 가고, arc 를 주면 곡선을 그린다.
        """
        sx, sy = self.src
        tx, ty = self.dst
        cur = [None]

        def step(i):
            if self.dead:
                return
            if i > n:
                if cur[0]:
                    self.cv.delete(cur[0])
                return self.burst()
            t = i / float(n)
            x = sx + (tx - sx) * t
            y = sy + (ty - sy) * t - arc * (t - t * t) * 4
            if cur[0]:
                self.cv.delete(cur[0])
            cur[0] = shape(x, y, t)
            self.items.append(cur[0])
            self.after(26, lambda: step(i + 1))
        step(0)

    def _marks(self, at, maker, n=3, gap=90, done_after=260):
        """제자리에서 표시가 하나씩 뜬다 (칼자국, 화살표 같은)."""
        x, y = at

        def one(i):
            if self.dead:
                return
            if i >= n:
                return self.after(done_after, self.burst)
            it = maker(x, y, i)
            if it is not None:
                self.items.append(it)
                self.after(360, lambda v=it: self.cv.delete(v))
            self.after(gap, lambda: one(i + 1))
        one(0)

    def _claw(self):
        """발톱 자국 - 나란한 사선 세 줄, 끝으로 갈수록 가늘어진다."""
        light, dark = colors(self.type)

        def maker(x, y, i):
            o = -14 + i * 14
            return self.cv.create_line(x - 22 + o, y - 20, x + 16 + o, y + 20,
                                       fill=light, width=6 - i, capstyle="round")
        self._marks(self.dst, maker, n=3, gap=70)

    def _stab(self):
        """뾰족한 것이 돌면서 파고든다."""
        light, dark = colors(self.type)

        def shape(x, y, t):
            a = t * 900.0
            r = 12
            pts = []
            for k in range(3):
                ang = math.radians(a + k * 120)
                rr = r if k == 0 else r * 0.55
                pts += [x + rr * math.cos(ang), y + rr * math.sin(ang)]
            return self.cv.create_polygon(*pts, fill=light, outline=dark,
                                          width=2)
        self._fly(shape, n=14)

    def _bone(self):
        """뼈가 빙글빙글 돌면서 날아간다."""
        def shape(x, y, t):
            a = t * 720.0
            r = 13
            dx = r * math.cos(math.radians(a))
            dy = r * math.sin(math.radians(a)) * 0.6
            return self.cv.create_line(x - dx, y - dy, x + dx, y + dy,
                                       fill="#f0ece0", width=5,
                                       capstyle="round")
        self._fly(shape, n=16, arc=18)

    def _slash(self):
        """칼자국 세 줄이 비스듬히 그어진다."""
        def maker(x, y, i):
            o = -18 + i * 16
            return self.cv.create_line(x - 26 + o, y - 24, x + 22 + o, y + 24,
                                       fill="#ffffff", width=5, capstyle="round")
        self._marks(self.dst, maker, n=3, gap=80)

    def _kick(self):
        """발차기 - 호를 그리며 차고 충격이 튄다."""
        light, dark = colors(self.type)

        def maker(x, y, i):
            r = 20 + i * 9
            return self.cv.create_arc(x - r, y - r, x + r, y + r,
                                      start=200 + i * 20, extent=110,
                                      style="arc", outline=light, width=5)
        self._marks(self.dst, maker, n=3, gap=70)

    def _quake(self):
        """땅이 갈라진다."""
        light, dark = colors(self.type)

        def maker(x, y, i):
            w = 40 + i * 26
            pts = []
            for k in range(7):
                pts += [x - w + (2 * w) * k / 6.0,
                        y + 22 + (6 if k % 2 else -6)]
            return self.cv.create_line(*pts, fill=dark, width=5)
        self._marks(self.dst, maker, n=4, gap=90)

    def _boom(self):
        """한가운데서 터진다."""
        light, dark = colors(self.type)
        tx, ty = self.dst

        def one(i):
            if self.dead:
                return
            if i > 8:
                return self.burst()
            r = 12 + i * 11
            it = self.add(self.cv.create_oval(tx - r, ty - r, tx + r, ty + r,
                                              outline=light if i % 2 else dark,
                                              width=4))
            self.after(200, lambda v=it: self.cv.delete(v))
            self.after(34, lambda: one(i + 1))
        one(0)

    def _rock(self):
        """돌덩이가 여러 개 날아간다."""
        light, dark = colors(self.type)

        def one(k):
            if self.dead:
                return
            if k >= 4:
                return self.after(180, self.burst)
            off = random.uniform(-22, 22)

            def shape(x, y, t, o=off):
                r = 8
                return self.cv.create_polygon(
                    x - r, y + o, x, y - r + o, x + r, y + o * 0.6,
                    x + r * 0.4, y + r + o, fill=dark, outline=light, width=2)
            self._fly(shape, n=10, arc=14)
            self.after(70, lambda: one(k + 1))
        one(0)

    def _leaf(self):
        """잎이 흩날리며 날아간다."""
        light, dark = colors(self.type)

        def shape(x, y, t):
            return _leaf_shape(self.cv, x, y, 9, light, dark, t * 360)
        self._fly(shape, n=15, arc=22)

    def _ice(self):
        """얼음 조각이 박힌다."""
        light, dark = colors(self.type)

        def maker(x, y, i):
            a = -50 + i * 50
            r = 26
            dx = r * math.cos(math.radians(a))
            dy = r * math.sin(math.radians(a))
            return self.cv.create_polygon(x + dx, y + dy,
                                          x + dx * 0.3 - 7, y + dy * 0.3,
                                          x + dx * 0.3 + 7, y + dy * 0.3 + 5,
                                          fill=light, outline=dark, width=2)
        self._marks(self.dst, maker, n=4, gap=70)

    def _wind(self):
        """바람 줄기가 지나간다."""
        light, dark = colors(self.type)
        sx, sy = self.src
        tx, ty = self.dst

        def maker(x, y, i):
            o = -20 + i * 14
            return self.cv.create_line(sx, sy + o, tx, ty + o,
                                       fill=light, width=3, dash=(14, 9))
        self._marks(self.dst, maker, n=4, gap=60)

    def _flash(self):
        """화면이 번쩍인다."""
        light, dark = colors(self.type)
        tx, ty = self.dst

        def one(i):
            if self.dead:
                return
            if i > 5:
                return self.burst()
            r = 60 - i * 9
            it = self.add(_blob(self.cv, tx, ty, r, light))
            self.after(90, lambda v=it: self.cv.delete(v))
            self.after(60, lambda: one(i + 1))
        one(0)

    def _dance(self):
        """자기 둘레를 돈다. 칼춤 계열은 칼이 돈다."""
        light, dark = colors(self.type)
        sx, sy = self.src
        kr = self.move.get("kr") or ""
        sword = ("칼" in kr) or ("검" in kr)
        items = []

        def spin(i):
            if self.dead:
                return
            for it in items:
                self.cv.delete(it)
            items[:] = []
            if i > 16:
                return self.burst()
            for k in range(3):
                a = math.radians(i * 22 + k * 120)
                x = sx + 30 * math.cos(a)
                y = sy - 26 + 12 * math.sin(a)
                if sword:
                    items.append(self.cv.create_line(x, y - 11, x, y + 11,
                                                     fill="#e8ecff", width=4,
                                                     capstyle="round"))
                    items.append(self.cv.create_line(x - 6, y + 5, x + 6, y + 5,
                                                     fill=light, width=3))
                else:
                    items.append(_star(self.cv, x, y, 8, light, dark))
            self.items.extend(items)
            self.after(45, lambda: spin(i + 1))
        spin(0)

    def _sleepz(self):
        """Z 가 떠오른다."""
        light, dark = colors(self.type)
        sx, sy = self.src

        def one(i):
            if self.dead:
                return
            if i >= 3:
                return self.after(320, self.burst)
            it = self.add(self.cv.create_text(sx + 16 + i * 9, sy - 26 - i * 12,
                                              text="Z", fill=light,
                                              font=("Malgun Gothic",
                                                    13 + i * 4, "bold")))
            self.after(520, lambda v=it: self.cv.delete(v))
            self.after(150, lambda: one(i + 1))
        one(0)

    def _throw(self):
        """무언가를 던진다."""
        light, dark = colors(self.type)

        def shape(x, y, t):
            return _blob(self.cv, x, y, 8, light, dark)
        self._fly(shape, n=13, arc=26)

    def _heal(self):
        """반짝임이 떠오른다."""
        light, dark = colors(self.type)
        sx, sy = self.src

        def one(i):
            if self.dead:
                return
            if i >= 8:
                return self.after(220, self.burst)
            x = sx + random.uniform(-22, 22)
            it = self.add(_star(self.cv, x, sy + 14 - i * 5, 7, "#9dffc0", light))
            self.after(420, lambda v=it: self.cv.delete(v))
            self.after(60, lambda: one(i + 1))
        one(0)

    def _drain(self):
        """상대에게서 빨아온다. 방향이 반대다."""
        light, dark = colors(self.type)
        sx, sy = self.src
        tx, ty = self.dst

        def one(k):
            if self.dead:
                return
            if k >= 7:
                return self.after(160, self.burst)
            cur = [None]

            def step(i):
                if self.dead:
                    return
                if i > 9:
                    if cur[0]:
                        self.cv.delete(cur[0])
                    return
                t = i / 9.0
                x = tx + (sx - tx) * t
                y = ty + (sy - ty) * t - 16 * (t - t * t) * 4
                if cur[0]:
                    self.cv.delete(cur[0])
                cur[0] = _blob(self.cv, x, y, 5, light)
                self.items.append(cur[0])
                self.after(26, lambda: step(i + 1))
            step(0)
            self.after(55, lambda: one(k + 1))
        one(0)

    def _recoil(self):
        """때리고 나도 아프다. 부딪히고 터진다."""
        self.st.lunge(self.src_side(), self._boom)

    def _multi(self):
        """여러 번 때린다."""
        light, dark = colors(self.type)

        def maker(x, y, i):
            o = random.uniform(-16, 16)
            return self.cv.create_line(x - 20 + o, y - 16, x + 20 + o, y + 16,
                                       fill=light, width=4, capstyle="round")
        self._marks(self.dst, maker, n=5, gap=55, done_after=180)

    def _arrows(self, at, up, color):
        """화살표가 위/아래로 흐른다. 랭크 변화 표시."""
        x, y = at

        def one(i):
            if self.dead:
                return
            if i >= 4:
                return self.after(220, self.burst)
            slide = i * 9
            base = y + (10 - slide if up else -10 + slide)
            tip = base + (-16 if up else 16)
            it = self.add(self.cv.create_polygon(
                x - 9, base, x + 9, base, x, tip, fill=color, outline=""))
            self.after(360, lambda v=it: self.cv.delete(v))
            self.after(80, lambda: one(i + 1))
        one(0)

    def _buff(self):
        self._arrows(self.src, True, "#7bffa0")

    def _selfdown(self):
        self._arrows(self.src, False, "#ff9d9d")

    def _debuff(self):
        self._arrows(self.dst, False, "#ff9d9d")

    def _contact(self):
        self.st.lunge(self.src_side(), lambda: self.slash())

    def _punch(self):
        self.st.lunge(self.src_side(), lambda: self.fist())

    def _bite(self):
        self.st.lunge(self.src_side(), lambda: self.fangs())

    def src_side(self):
        return self.who

    def slash(self):
        """베기 자국 세 줄."""
        tx, ty = self.dst
        light, dark = colors(self.type)
        for k in range(3):
            off = (k - 1) * 16
            self.add(self.cv.create_line(tx - 30 + off, ty - 30, tx + 30 + off,
                                         ty + 30, fill=light, width=5))
            self.add(self.cv.create_line(tx - 28 + off, ty - 28, tx + 28 + off,
                                         ty + 28, fill=dark, width=2))
        self.after(200, self.burst)

    def fist(self):
        """주먹 충격."""
        tx, ty = self.dst
        light, dark = colors(self.type)
        for k in range(8):
            a = 2 * math.pi * k / 8
            self.add(self.cv.create_line(tx + math.cos(a) * 16, ty + math.sin(a) * 16,
                                         tx + math.cos(a) * 42, ty + math.sin(a) * 42,
                                         fill=light, width=4))
        self.add(_blob(self.cv, tx, ty, 15, dark, light))
        self.after(200, self.burst)

    def fangs(self):
        """이빨 자국."""
        tx, ty = self.dst
        light, dark = colors(self.type)
        for sign in (-1, 1):
            for k in range(3):
                x = tx + sign * (14 + k * 12)
                self.add(self.cv.create_polygon(
                    x, ty - sign * 6, x + 7, ty - 26 * sign, x + 14, ty - sign * 6,
                    fill=light, outline=dark))
        self.after(200, self.burst)

    # ---- 마무리 충격 ----
    def burst(self):
        self.clear()
        tx, ty = self.dst
        light, dark = colors(self.type)
        rings = []

        def step(i):
            if self.dead:
                return
            if i > 7:
                return self.finish()
            for it in rings:
                self.cv.delete(it)
            del rings[:]
            r = 12 + i * 9
            rings.append(self.cv.create_oval(tx - r, ty - r, tx + r, ty + r,
                                             outline=light if i % 2 else dark,
                                             width=max(1, 6 - i)))
            self.items.extend(rings)
            self.after(30, lambda: step(i + 1))
        step(0)
