# -*- coding: utf-8 -*-
"""배틀 화면 검사 — 도트도 서버도 없이 로직만.

    python client/test_battle_ui.py

체력바가 어느 포켓몬 것인지가 전부다. 여기가 틀리면 멀쩡한 포켓몬이
빈사로 보이거나, 다 죽어가는 애가 멀쩡해 보인다. 눈에는 잘 띄는데
버그로는 잡기 어려운 종류다 - 다음 턴이 끝나면 저절로 맞아 버려서
"가끔 그런다" 로 남는다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = os.path.join(tempfile.gettempdir(),
                                        "poket-test-battleui")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import arena as AR                         # noqa: E402
from poketdesktop import desktop_battle as DB                # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class 가짜바(object):
    """HpBar 와 같은 계약만 흉내낸다."""

    def __init__(self):
        self.ratio = 1.0
        self.shown = 1.0
        self.그린곳 = []
        self.지운수 = 0

    def set(self, hp, maxhp):
        self.ratio = max(0.0, min(1.0, hp / float(maxhp or 1)))

    def ease(self):
        self.shown = self.ratio

    def draw(self, x, y):
        self.그린곳.append((x, y))

    def clear(self):
        self.지운수 += 1


class 가짜도트(object):
    def __init__(self, pid):
        self.id = pid
        self.x = self.y = 0
        self.fw = self.fh = 32
        self.ax = self.ay = 16
        self.battling = False

        class W(object):
            보임 = 1

            def deiconify(self):
                self.보임 = 1

            def withdraw(self):
                self.보임 = 0

            def winfo_viewable(self):
                return self.보임
        self.win = W()
        # 진짜 Pet 처럼 이름표 창도 따로 있다. badge_win 은 없다 - 야생만
        # 표식을 단다.
        self.name_win = W()

    def place(self):
        pass

    def clamp(self):
        pass

    def play(self, name, once=False, then=None):
        return False                  # 그 동작이 없는 종처럼


class 가짜앱(object):
    def __init__(self, pets):
        class OV(object):
            pass
        self.overlay = OV()
        self.overlay.pets = pets
        self.말 = []

    def notify(self, m):
        self.말.append(m)


class 가짜배틀(object):
    """DesktopBattle 에서 검사할 메서드만 빌려 끼운다.

    __init__ 은 도트와 서버를 요구하므로 부르지 않는다.
    """

    def __init__(self, b, pets, mine):
        self.b = b
        self.app = 가짜앱(pets)
        self.root = None
        self.closed = False
        self.busy = False
        self.mine = mine
        self.foe = 가짜도트(999)
        self.bars = (가짜바(), 가짜바())
        self.saved_home = (0, 0)
        self.예약 = []
        self.layer = self          # tick_bars 가 있는지만 본다
        self.root = self
        self.올린수 = 0             # 창 순서를 올린 횟수
        self.살린수 = 0             # 클릭 통과를 다시 건 횟수

    def raise_above(self):
        self.올린수 += 1

    def keep_alive(self):
        self.살린수 += 1

    def after(self, ms, fn):
        self.예약.append((ms, fn))

    tick_bars = DB.DesktopBattle.tick_bars
    sync_bars = DB.DesktopBattle.sync_bars
    apply_hp = DB.DesktopBattle.apply_hp
    switch_to = DB.DesktopBattle.switch_to
    _safe = DB.DesktopBattle._safe
    approach = lambda self: None


def t_체력을_그대로_반영한다():
    b = {"me": {"id": 1, "name": "파이리", "hp": 30, "maxhp": 60},
         "foe": {"id": 9, "name": "구구", "hp": 10, "maxhp": 40}}
    d = 가짜배틀(b, {1: 가짜도트(1)}, 가짜도트(1))
    d.sync_bars()
    chk("내 쪽 절반", abs(d.bars[0].ratio - 0.5) < 1e-9, d.bars[0].ratio)
    chk("상대 쪽 1/4", abs(d.bars[1].ratio - 0.25) < 1e-9, d.bars[1].ratio)
    chk("snap 없으면 표시값은 그대로", d.bars[0].shown == 1.0)

    d.sync_bars(snap=True)
    chk("snap 이면 표시값도 바로 맞는다",
        d.bars[0].shown == d.bars[0].ratio == 0.5, d.bars[0].shown)


def t_교체하면_새_포켓몬_체력으로_바뀐다():
    """**이게 원래 버그다.**

    앞 포켓몬이 쓰러지면 바는 0 을 들고 있는데, 다음 포켓몬이 나올 때
    그걸 안 바꿔 줬다. 그래서 멀쩡한 포켓몬이 체력 0 인 채로 걸어 나왔고,
    다음 턴이 끝나 turn_done 의 sync_bars 가 돌 때까지 그대로였다.
    """
    쓰러진애, 다음애 = 가짜도트(1), 가짜도트(2)
    d = 가짜배틀({"me": {"id": 1, "name": "파이리", "hp": 0, "maxhp": 60},
                  "foe": {"id": 9, "name": "구구", "hp": 40, "maxhp": 40}},
                 {1: 쓰러진애, 2: 다음애}, 쓰러진애)
    d.sync_bars(snap=True)
    chk("쓰러졌으니 0", d.bars[0].ratio == 0.0)

    새배틀 = {"me": {"id": 2, "name": "꼬부기", "hp": 55, "maxhp": 55},
              "foe": {"id": 9, "name": "구구", "hp": 40, "maxhp": 40}}

    real = DB.run_async
    DB.run_async = lambda _root, work, done: done({"battle": 새배틀}, None)
    try:
        d.switch_to({"id": 2})
    finally:
        DB.run_async = real

    chk("다음 포켓몬으로 바뀌었다", d.mine is 다음애)
    chk("체력바가 가득 찼다", d.bars[0].ratio == 1.0, d.bars[0].ratio)
    # 스르륵 차오르면 새로 나온 포켓몬이 회복하는 것처럼 보인다
    chk("차오르지 않고 곧바로 맞는다",
        d.bars[0].shown == 1.0, d.bars[0].shown)
    chk("상대 체력은 그대로", d.bars[1].ratio == 1.0)
    chk("싸울 준비가 됐다", d.mine.battling is True)
    chk("쓰러진 애는 배틀에서 빠졌다", 쓰러진애.battling is False)


def t_숨은_도트의_체력바는_안_그린다():
    """볼에 들어가거나 쓰러지면 **창만 숨고 Pet 객체는 그대로 남는다.**

    좌표도 멀쩡하게 남아서, 이걸 안 보면 체력바만 아무것도 없는 자리에
    떠 있는다 - 볼을 던지는 1~2초 동안 흔들리는 볼 위 허공에 남는다.
    """
    내도트, 야생 = 가짜도트(1), 가짜도트(9)
    d = 가짜배틀({"me": {"id": 1, "name": "파이리", "hp": 60, "maxhp": 60},
                  "foe": {"id": 9, "name": "구구", "hp": 40, "maxhp": 40}},
                 {1: 내도트}, 내도트)
    d.foe = 야생
    d.tick_bars()
    chk("둘 다 보이면 둘 다 그린다",
        len(d.bars[0].그린곳) == 1 and len(d.bars[1].그린곳) == 1,
        (d.bars[0].그린곳, d.bars[1].그린곳))

    야생.win.withdraw()             # 볼에 들어갔다
    d.tick_bars()
    chk("숨은 쪽은 안 그린다", len(d.bars[1].그린곳) == 1, d.bars[1].그린곳)
    chk("숨은 쪽은 지운다", d.bars[1].지운수 == 1, d.bars[1].지운수)
    chk("보이는 쪽은 계속 그린다", len(d.bars[0].그린곳) == 2)

    야생.win.deiconify()            # 튀어나왔다
    d.tick_bars()
    chk("다시 보이면 다시 그린다", len(d.bars[1].그린곳) == 2)

    # 창을 이미 없앴으면 TclError 가 난다. 그것도 "안 보인다" 다.
    class 죽은창(object):
        def winfo_viewable(self):
            raise RuntimeError("이미 없앴다")
    내도트.win = 죽은창()
    d.tick_bars()
    chk("없어진 창은 조용히 넘긴다", len(d.bars[0].그린곳) == 3,
        d.bars[0].그린곳)


def t_맞는_순간_그_쪽만_준다():
    """누구 체력인지는 이벤트마다 다르다.

    hit 은 맞은 쪽(target), chip/heal/recoil 은 겪는 쪽(who) 이다.
    바꿔 읽으면 때린 쪽 체력이 줄어드는 것처럼 보인다.
    """
    d = 가짜배틀({"me": {"id": 1, "name": "파이리", "hp": 60, "maxhp": 60},
                  "foe": {"id": 9, "name": "구구", "hp": 40, "maxhp": 40}},
                 {1: 가짜도트(1)}, 가짜도트(1))
    d.sync_bars(snap=True)

    d.apply_hp({"t": "hit", "who": "me", "target": "foe",
                "hp": 20, "maxhp": 40})
    chk("hit 은 맞은 쪽이 준다", d.bars[1].ratio == 0.5, d.bars[1].ratio)
    chk("때린 쪽은 그대로", d.bars[0].ratio == 1.0)

    d.apply_hp({"t": "chip", "who": "me", "hp": 30, "maxhp": 60})
    chk("chip 은 겪는 쪽이 준다", d.bars[0].ratio == 0.5, d.bars[0].ratio)

    before = (d.bars[0].ratio, d.bars[1].ratio)
    d.apply_hp({"t": "move", "who": "me"})              # hp 가 없다
    chk("hp 가 없는 이벤트는 건드리지 않는다",
        (d.bars[0].ratio, d.bars[1].ratio) == before)
    d.apply_hp({"t": "hit", "target": "nobody", "hp": 1, "maxhp": 1})
    chk("모르는 쪽이면 아무것도 안 한다",
        (d.bars[0].ratio, d.bars[1].ratio) == before)


def t_틱은_창_순서를_안_올린다():
    """**1.0.20 에서 고친 버그.**

    체력바 틱이 0.5초마다 레이어를 맨 위로 올렸다. 볼 고르는 메뉴가 떠
    있는 동안에도 계속 올라와서 메뉴 위에 체력바가 찍혔다. 도트는 만들
    때 한 번만 올리니까 메뉴 뒤로 얌전히 들어갔고, 레이어만 메뉴를 뚫고
    나왔다.

    틱은 순서를 건드리면 안 된다. 맥에서 풀리는 클릭 통과만 다시 건다.
    순서는 창이 다시 보이는 순간(switch_to)에만 맞춘다.
    """
    d = 가짜배틀({"me": {"id": 1, "name": "파이리", "hp": 60, "maxhp": 60},
                  "foe": {"id": 9, "name": "구구", "hp": 40, "maxhp": 40}},
                 {1: 가짜도트(1), 2: 가짜도트(2)}, 가짜도트(1))
    for _ in range(60):                       # 2초어치
        d.tick_bars()
    chk("틱 60번에 창 순서를 한 번도 안 올린다", d.올린수 == 0, d.올린수)
    chk("클릭 통과는 몇 틱마다 다시 건다", d.살린수 >= 2, d.살린수)

    # 교체로 도트가 다시 보이는 순간에는 올려야 한다. 안 그러면 새
    # 포켓몬의 체력바가 도트 뒤로 숨는다.
    새배틀 = {"me": {"id": 2, "name": "꼬부기", "hp": 55, "maxhp": 55},
              "foe": {"id": 9, "name": "구구", "hp": 40, "maxhp": 40}}
    real = DB.run_async
    DB.run_async = lambda _root, work, done: done({"battle": 새배틀}, None)
    try:
        d.switch_to({"id": 2})
    finally:
        DB.run_async = real
    chk("교체 직후에는 딱 한 번 올린다", d.올린수 == 1, d.올린수)

    for _ in range(60):
        d.tick_bars()
    chk("그 뒤 틱은 다시 안 올린다", d.올린수 == 1, d.올린수)


class 가짜투기장(object):
    """Arena._tick_bars 만 빌려 끼운다. 레이어 노릇도 같이 한다."""

    def __init__(self):
        self.closed = False
        self.layer = self
        self.bars = {}
        self.active = {"me": None, "foe": None}
        self.root = self
        self.bar_job = None
        self.올린수 = 0
        self.살린수 = 0

    def raise_above(self):
        self.올린수 += 1

    def keep_alive(self):
        self.살린수 += 1

    def after(self, ms, fn):
        return None

    _tick_bars = AR.Arena._tick_bars


def t_투기장_틱도_창_순서를_안_올린다():
    """투기장 쪽도 같은 틱을 갖고 있었다. 트레이 메뉴를 열어도 그 위로
    체력바가 올라왔다."""
    a = 가짜투기장()
    for _ in range(60):
        a._tick_bars()
    chk("투기장 틱 60번에 창 순서를 안 올린다", a.올린수 == 0, a.올린수)
    chk("투기장도 클릭 통과는 다시 건다", a.살린수 >= 2, a.살린수)


class 가짜시계(object):
    """root.after 를 쌓아 두었다가 run() 에서 차례로 돌린다."""

    def __init__(self):
        self.jobs = {}
        self.n = 0

    def after(self, ms, fn):
        self.n += 1
        self.jobs[self.n] = fn
        return self.n

    def after_cancel(self, j):
        self.jobs.pop(j, None)

    def run(self, limit=500):
        k = 0
        while self.jobs and k < limit:
            fn = self.jobs.pop(min(self.jobs))
            fn()
            k += 1


class 가짜오버레이(object):
    """이름표를 몇 번 막고 풀었는지만 센다."""

    def __init__(self):
        self.pets = {}
        self.extra = []
        self.locked = True
        self.settings = {"areaMargin": 4}
        self.막은수 = 0
        self.푼수 = 0
        self.풀때 = None           # 풀 때 부를 것 (그 순간의 화면을 본다)

    def area(self):
        return (0, 0, 800, 600)

    def block_names(self):
        self.막은수 += 1

    def release_names(self):
        self.푼수 += 1
        if self.풀때:
            self.풀때()


class 가짜판앱(object):
    def __init__(self, ov):
        self.overlay = ov
        self.battle = "싸우는 중"
        self.wild = None
        self.말 = []

    def notify(self, m):
        self.말.append(m)

    def request_sync(self):
        pass


class 가짜판(object):
    """begin / finish_cleanup / after 를 진짜 그대로 빌려 끼운다.

    레이어는 없다(open_layer 를 None 으로 바꿔 끼운다). 레이어를 못 만든
    PC 에서 도는 길과 같다.
    """

    def __init__(self, ov):
        self.app = 가짜판앱(ov)
        self.root = 가짜시계()
        self.b = {"id": 1, "me": {"id": 1, "name": "파이리"}}
        self.closed = False
        self.busy = False
        self.jobs = []
        self.fx = None
        self.texts = []
        self.layer = None
        self.bars = None
        self.bar_job = None
        self.mine = 가짜도트(1)
        self.foe = 가짜도트(9)
        self.saved_home = None
        self._names_ov = None

    after = DB.DesktopBattle.after
    _safe = DB.DesktopBattle._safe
    abort = DB.DesktopBattle.abort
    begin = DB.DesktopBattle.begin
    finish_cleanup = DB.DesktopBattle.finish_cleanup
    close = DB.DesktopBattle.close
    _release_names = DB.DesktopBattle._release_names
    clear_bars = DB.DesktopBattle.clear_bars
    sync_bars = DB.DesktopBattle.sync_bars
    tick_bars = DB.DesktopBattle.tick_bars
    faint = DB.DesktopBattle.faint
    approach = lambda self: None


def 판_시작(ov=None):
    real = DB.open_layer
    DB.open_layer = lambda root, area: None
    try:
        d = 가짜판(ov or 가짜오버레이())
        d.begin(None)
    finally:
        DB.open_layer = real
    return d


def t_배틀_동안_이름표를_막고_끝나면_한_번_푼다():
    """체력바와 대미지 글자가 이름표 줄에 그려져서 글자끼리 포개졌다.

    막는 것만큼 **반드시 한 번 푸는 것**이 중요하다. 못 풀면 이름표가
    로그아웃할 때까지 안 돌아오고, 두 번 풀면 다음 배틀에서 안 숨는다.
    """
    d = 판_시작()
    ov = d.app.overlay
    chk("배틀이 시작되면 이름표를 막는다", ov.막은수 == 1, ov.막은수)
    chk("아직 안 풀었다", ov.푼수 == 0, ov.푼수)
    d.begin(None)
    chk("begin 을 또 불러도 한 번만 막는다", ov.막은수 == 1, ov.막은수)

    # 쓰러져서 숨은 채로 끝났다. 창을 먼저 보인 뒤에 풀어야 그 도트의
    # 이름표도 돌아온다 (Overlay 는 창이 숨은 도트를 건너뛴다).
    d.mine.win.withdraw()
    본것 = []
    ov.풀때 = lambda: 본것.append(d.mine.win.보임)
    d.finish_cleanup()
    chk("끝나면 푼다", ov.푼수 == 1, ov.푼수)
    chk("내 포켓몬 창을 보인 뒤에 푼다", 본것 == [1], 본것)
    chk("app.battle 을 비운다", d.app.battle is None, d.app.battle)
    d.finish_cleanup()
    d.close()
    chk("끝내기를 여러 번 불러도 한 번만 푼다", ov.푼수 == 1, ov.푼수)


def t_막기_전에_끝나면_안_푼다():
    """setup 에서 곧바로 접힌 배틀(야생이 사라졌다)은 막은 적이 없다.
    그런데 풀면 다른 쪽(투기장)이 막아 둔 것까지 풀린다."""
    ov = 가짜오버레이()
    d = 가짜판(ov)
    d.abort("야생 포켓몬이 사라졌습니다.")
    chk("막은 적 없으면 안 푼다", ov.푼수 == 0, ov.푼수)


def t_연출이_터져도_배틀을_접는다():
    """after 사슬의 한 고리가 터지면 거기서 조용히 끊겼다.

    finish_cleanup 에 영영 안 닿아서 app.battle 이 남고(야생을 눌러도
    반응이 없다), 치워 둔 이름표도 로그아웃할 때까지 안 돌아왔다.
    """
    d = 판_시작()
    ov = d.app.overlay

    def 터짐():
        raise RuntimeError("연출이 터졌다")
    d.after(30, 터짐)
    d.root.run()
    chk("터지면 배틀을 접는다", d.closed is True)
    chk("이름표를 푼다", ov.푼수 == 1, ov.푼수)
    chk("app.battle 을 비운다", d.app.battle is None, d.app.battle)
    chk("멈췄다고 알린다", any("멈췄" in m for m in d.app.말), d.app.말)

    # 서버 응답을 받아 이어가는 자리(run_async 의 done)도 같은 사슬이다.
    d2 = 판_시작()
    d2._safe(lambda r, err: {}["없는 키"], {"events": []}, None)
    chk("응답 처리에서 터져도 접는다",
        d2.closed is True and d2.app.overlay.푼수 == 1,
        (d2.closed, d2.app.overlay.푼수))

    # 이미 끝난 뒤에 터진 것은 남기기만 한다. 또 알리면 끝난 배틀이
    # 멈췄다는 말이 뒤늦게 뜬다.
    n = len(d.app.말)
    d._safe(터짐)
    chk("끝난 뒤에 터진 것은 다시 안 알린다", len(d.app.말) == n, d.app.말)


def t_내_도트_창이_없어져도_정리는_끝난다():
    """배틀 중에 그 도트가 바탕화면에서 내려가면(sync 가 창을 없애면)
    제자리로 옮기는 place() 가 터진다. 거기서 멈추면 이름표도 안 풀리고
    app.battle 도 남는다."""
    d = 판_시작()

    def 없는창():
        raise RuntimeError("invalid command name")
    d.mine.place = 없는창
    try:
        d.finish_cleanup()
        chk("터지지 않는다", True)
    except Exception as e:                                  # noqa: BLE001
        chk("터지지 않는다", False, e)
    chk("그래도 이름표를 푼다", d.app.overlay.푼수 == 1, d.app.overlay.푼수)
    chk("그래도 app.battle 을 비운다", d.app.battle is None)


def t_쓰러지면_이름표도_치운다():
    """예전에는 창과 badge_win 만 숨겼다. 내 포켓몬(Pet)에는 badge_win 이
    없어서 AttributeError 가 났고 except 가 삼켰다 - 쓰러진 자리 허공에
    이름표만 남았다."""
    d = 판_시작()
    끝 = []
    pet = 가짜도트(1)
    d.faint(pet, lambda: 끝.append(True))
    d.root.run()
    chk("도트 창이 숨는다", pet.win.보임 == 0)
    chk("이름표도 숨는다", pet.name_win.보임 == 0)
    chk("다음으로 넘어간다", 끝 == [True], 끝)

    야생 = 가짜도트(9)
    야생.name_win = None             # 야생에는 이름표가 없다
    야생.badge_win = type(pet.win)()
    d.faint(야생, lambda: 끝.append(True))
    d.root.run()
    chk("야생은 표식이 숨는다", 야생.badge_win.보임 == 0)


class 가짜투기장정리(object):
    """Arena.cleanup 만 빌려 끼운다."""

    def __init__(self, ov):
        self.closed = False
        self.root = 가짜시계()
        self.jobs = []
        self.bar_job = None
        self.app = 가짜판앱(ov)
        self.foes = []
        self.mine = [가짜도트(1), 가짜도트(2)]
        self.home = {}
        self.bars = {}
        self.texts = []
        self.layer = None
        self.on_done = None
        self._names_ov = ov

    _cancel_jobs = AR.Arena._cancel_jobs
    _release_names = AR.Arena._release_names
    cleanup = AR.Arena.cleanup


def t_투기장은_제자리로_돌아온_뒤에_한_번_푼다():
    """예전에는 선수마다 설정을 보고 이름표를 따로 다시 띄웠다. 막고 푸는
    곳을 Overlay 하나로 모았으니 cleanup 에서 한 번만 푼다."""
    ov = 가짜오버레이()
    a = 가짜투기장정리(ov)
    쓰러진애 = a.mine[1]
    쓰러진애.win.withdraw()
    본것 = []
    ov.풀때 = lambda: 본것.append((쓰러진애.win.보임, ov.locked))
    a.cleanup()
    chk("투기장이 끝나면 푼다", ov.푼수 == 1, ov.푼수)
    chk("쓰러진 선수 창을 보인 뒤, 잠금을 풀기 전에 푼다",
        본것 == [(1, True)], 본것)
    chk("잠금도 푼다", ov.locked is False)
    a.closed = False                  # 강제로 한 번 더 돌려 본다
    a.cleanup()
    chk("다시 불러도 한 번만 푼다", ov.푼수 == 1, ov.푼수)


def main():
    for fn in (t_체력을_그대로_반영한다, t_교체하면_새_포켓몬_체력으로_바뀐다,
               t_숨은_도트의_체력바는_안_그린다, t_맞는_순간_그_쪽만_준다,
               t_틱은_창_순서를_안_올린다, t_투기장_틱도_창_순서를_안_올린다,
               t_배틀_동안_이름표를_막고_끝나면_한_번_푼다,
               t_막기_전에_끝나면_안_푼다, t_연출이_터져도_배틀을_접는다,
               t_내_도트_창이_없어져도_정리는_끝난다, t_쓰러지면_이름표도_치운다,
               t_투기장은_제자리로_돌아온_뒤에_한_번_푼다):
        print("-- %s" % fn.__name__[2:])
        fn()
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
