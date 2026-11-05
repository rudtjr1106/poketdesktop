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
        self.pending_ball = None   # 이번 턴 뒤에 던질 볼 (진짜 배틀은 늘 갖고 있다)
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
    _retry_next = DB.DesktopBattle._retry_next
    _enter_next = DB.DesktopBattle._enter_next
    _cancel_hold_jobs = DB.DesktopBattle._cancel_hold_jobs
    stop_auto = DB.DesktopBattle.stop_auto        # (2.1.3 계속 던지기 - show_result 가 부른다)
    holding = False
    hold_job = hint_job = None
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
    d.finish = True                       # 앞 포켓몬 때 '끝까지 싸우기' 로 바뀌어 있었다
    try:
        d.switch_to({"id": 2})
    finally:
        DB.run_async = real

    chk("다음 포켓몬으로 바뀌었다", d.mine is 다음애)
    chk("새 포켓몬은 다시 잡기 모드로 싸운다 ('끝까지 싸우기' 를 푼다, 게시판 #222)", d.finish is False)
    chk("체력바가 가득 찼다", d.bars[0].ratio == 1.0, d.bars[0].ratio)
    # 스르륵 차오르면 새로 나온 포켓몬이 회복하는 것처럼 보인다
    chk("차오르지 않고 곧바로 맞는다",
        d.bars[0].shown == 1.0, d.bars[0].shown)
    chk("상대 체력은 그대로", d.bars[1].ratio == 1.0)
    chk("싸울 준비가 됐다", d.mine.battling is True)
    chk("쓰러진 애는 배틀에서 빠졌다", 쓰러진애.battling is False)


def t_교체한_포켓몬이_아직_화면에_없으면_다시_찾는다():
    """게시판 #266-1 (레드 36세): 셋째 포켓몬이 나온 뒤 배틀이 통째로 사라졌다.

    서버는 괴력몬으로 바꿔 놓았는데(PP 그대로) 화면이 판을 접었다. 바탕화면에서 그 도트를 바로 못 찾으면
    예전에는 그 자리에서 접었다 - 배틀을 시작할 때처럼 목록을 맞추고 몇 번 더 찾는다.
    """
    쓰러진애, 다음애 = 가짜도트(1), 가짜도트(2)
    pets = {1: 쓰러진애}
    d = 가짜배틀({"me": {"id": 1, "name": "갸라도스", "hp": 0, "maxhp": 60},
                  "foe": {"id": 9, "name": "거대코뿌리", "hp": 40, "maxhp": 40}}, pets, 쓰러진애)
    접음 = []
    d.abort = lambda msg: 접음.append(msg)
    맞춤 = []
    d.app.request_sync = lambda: 맞춤.append(1)
    새배틀 = {"me": {"id": 2, "name": "괴력몬", "hp": 55, "maxhp": 55},
              "foe": {"id": 9, "name": "거대코뿌리", "hp": 40, "maxhp": 40}}
    real = DB.run_async
    DB.run_async = lambda _root, work, done: done({"battle": 새배틀}, None)
    try:
        d.switch_to({"id": 2})
    finally:
        DB.run_async = real
    chk("바로 접지 않는다", not 접음, 접음)
    chk("  목록을 맞추라고 한다", 맞춤 == [1], 맞춤)
    chk("  0.5초 뒤에 다시 찾기로 해 둔다", d.예약 and d.예약[-1][0] == 500, d.예약)
    pets[2] = 다음애                          # 그사이 도트가 생겼다
    ms, again = d.예약.pop()
    again()
    chk("찾으면 이어서 싸운다", d.mine is 다음애 and 다음애.battling and not 접음, (d.mine, 접음))
    chk("  체력바도 새 포켓몬 것", d.bars[0].ratio == 1.0, d.bars[0].ratio)
    # 끝내 없으면 그때 접는다 (여섯 번)
    d2 = 가짜배틀({"me": {"id": 1, "name": "갸라도스", "hp": 0, "maxhp": 60},
                   "foe": {"id": 9, "name": "거대코뿌리", "hp": 40, "maxhp": 40}}, {1: 쓰러진애}, 쓰러진애)
    접음2 = []
    d2.abort = lambda msg: 접음2.append(msg)
    DB.run_async = lambda _root, work, done: done({"battle": 새배틀}, None)
    try:
        d2.switch_to({"id": 2})
    finally:
        DB.run_async = real
    for _ in range(10):
        if not d2.예약:
            break
        d2.예약.pop()[1]()
    chk("끝내 못 찾으면 그때 접는다 (여섯 번 찾은 뒤)", 접음2 == ["다음 포켓몬을 화면에서 찾지 못했습니다."], 접음2)


def t_날려가서_끝나면_까닭을_알린다():
    """게시판 #266 (레드 36세, 10/19 14:44): 트래피더의 배대뒤치기에 갸라도스가 날려가 판이 끝났는데(본가와 같은
    규칙), 화면은 아무것도 안 띄우고 '야생 포켓몬이 떠나버렸다.' 만 알려서 배틀이 증발한 것처럼 보였다."""
    mine = 가짜도트(1)
    d = 가짜배틀({"me": {"id": 1, "name": "갸라도스", "hp": 200, "maxhp": 250},
                  "foe": {"id": 9, "name": "트래피더", "hp": 118, "maxhp": 250}}, {1: mine}, mine)
    뜬글 = []
    d.float_over = lambda pet, text, color: 뜬글.append((pet, text))
    d.finish_cleanup = lambda: None
    d.show_result = DB.DesktopBattle.show_result.__get__(d)
    d.render = DB.DesktopBattle.render.__get__(d)
    ev = [{"t": "move", "who": "me", "text": "갸라도스 의 깨물어부수기!"},
          {"t": "move", "who": "foe", "text": "트래피더 의 배대뒤치기!"},
          {"t": "flee", "who": "me", "text": "갸라도스 은(는) 날려가 버렸다!"}]
    끝 = []
    d.render(ev[-1], lambda: 끝.append(1))
    chk("날려간 포켓몬 머리 위에 '날려가 버렸다!'", 뜬글 == [(mine, "날려가 버렸다!")], 뜬글)
    chk("  읽을 틈을 준다 (0.9초 뒤에 다음으로)", d.예약 and d.예약[-1][0] == 900 and not 끝, d.예약)
    d.예약[-1][1]()
    chk("  그다음 사건으로 넘어간다", 끝 == [1])
    d.show_result({"battle": {"over": True, "result": "fled"}, "events": ev})
    chk("알림은 무엇이 판을 끝냈는지: 기술 + 날려갔다",
        d.app.말 and d.app.말[-1] == "트래피더의 배대뒤치기! 갸라도스는 날려가 버렸다!", d.app.말)
    d.show_result({"battle": {"over": True, "result": "fled"},
                   "events": [{"t": "flee", "who": "foe", "text": "야생 고라파덕 은(는) 흥미를 잃고 떠나버렸다."}]})
    chk("  흥미를 잃고 떠났으면 그 말 (기술은 안 붙인다)", d.app.말[-1] == "야생 고라파덕은 흥미를 잃고 떠나버렸다.", d.app.말[-1])
    d.show_result({"battle": {"over": True, "result": "fled"}})
    chk("  끝낸 사건이 없으면 예전 말 그대로", d.app.말[-1] == "야생 포켓몬이 떠나버렸다.", d.app.말[-1])
    mine.win.보임 = 0
    뜬글.clear()
    끝.clear()
    d.render(ev[-1], lambda: 끝.append(1))
    chk("  도트가 숨어 있으면 허공에 안 띄운다 (바로 다음으로)", not 뜬글, 뜬글)


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
    left_party = DB.DesktopBattle.left_party
    begin = DB.DesktopBattle.begin
    finish_cleanup = DB.DesktopBattle.finish_cleanup
    stop_auto = DB.DesktopBattle.stop_auto
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


def t_싸우던_포켓몬이_파티에서_빠지면_바로_접는다():
    """게시판 #218: 배틀 중에 파티를 바꿔 싸우던 포켓몬이 박스로 가면, 그 도트가 없어진 채 연출이 돌다
    터져서야 접혔고, 다시 '대결' 을 누르면 서버가 그 판을 이어 줘서 영영 못 싸웠다.
    이제 동기화 직후 앱이 보고 바로 접는다 (서버는 그 판을 이어 주지 않는다 - test_battle)."""
    from poketdesktop import app as APP

    class 앱(object):
        _check_battle_mine = APP.App._check_battle_mine

        def __init__(self, d):
            self.battle, self.overlay = d, d.app.overlay

    d = 판_시작()
    ov = d.app.overlay
    ov.pets = {1: d.mine}
    a = 앱(d)
    chk("싸우던 도트가 그대로 있으면 아무것도 안 한다", a._check_battle_mine() is False and not d.closed)
    ov.pets = {2: 가짜도트(2)}                    # 파티를 바꿨다 - 1번은 박스로
    chk("빠졌으면 바로 접는다", a._check_battle_mine() is True and d.closed and d.app.battle is None)
    chk("  까닭을 알린다 (다시 누르면 지금 파티 맨 앞이 싸운다)", any("파티에서 빠져" in m for m in d.app.말), d.app.말)
    chk("  이름표도 푼다", ov.푼수 == 1, ov.푼수)
    chk("이미 접힌 배틀이면 다시 안 접는다", a._check_battle_mine() is False)
    a.battle = None
    chk("배틀이 없으면 아무것도 안 한다", a._check_battle_mine() is False)


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


# ---------------------------------------------------------------- 잡기 모드
class 시간시계(object):
    """after 를 시각 순서대로 돌리는 시계. advance(ms) 만큼 시간을 흘린다."""

    def __init__(self):
        self.now = 0
        self.jobs = {}
        self.n = 0

    def after(self, ms, fn):
        self.n += 1
        self.jobs[self.n] = (self.now + ms, self.n, fn)
        return self.n

    def after_cancel(self, j):
        self.jobs.pop(j, None)

    def advance(self, ms):
        end = self.now + ms
        while True:
            due = [v for v in self.jobs.values() if v[0] <= end]
            if not due:
                break
            t, n, fn = min(due)
            self.jobs.pop(n)
            self.now = max(self.now, t)
            fn()
        self.now = end


class 가짜서버(object):
    def __init__(self):
        self.moves = []            # (catch, finish)
        self.balls = []
        self.move_answers = []
        self.ball_answers = []

    def battle_move(self, bid, move, catch="", finish=False):
        self.moves.append((catch, finish))
        if self.move_answers:
            return self.move_answers.pop(0)
        return {"events": [{"t": "move", "who": "me"}], "battle": {"id": bid, "over": False}}

    def battle_ball(self, bid, ball):
        self.balls.append(ball)
        if self.ball_answers:
            return self.ball_answers.pop(0)
        return {"caught": False, "balls": 5, "events": [], "battle": {"id": bid, "over": False}}


class 가짜야생(object):
    def __init__(self, app=None):
        self.app = app
        self.toggled = 0

    def play_catch(self, r, on_done=None):
        on_done()

    def toggle_auto(self):                      # 볼 메뉴 맨 위 '잡힐 때까지 계속 던지기' (wild_ui 와 같은 설정)
        self.toggled += 1
        self.app.settings["autoThrow"] = not self.app.settings.get("autoThrow")

    def cycle_auto_max(self):                   # 그 아래 '최대 N개까지' (2.2.1, #460)
        from poketdesktop import ball_menu
        self.app.settings["autoThrowMax"] = ball_menu.next_auto_max(ball_menu.auto_max(self.app.settings))


class 가짜잡기앱(object):
    def __init__(self, mode="new"):
        self.api = 가짜서버()
        self.settings = {"catchMode": mode, "lastBall": "POKEBALL"}
        self.balls = 5
        self.wild = 가짜야생(self)
        self.말 = []

    def notify(self, m):
        self.말.append(m)

    def refresh_tray(self):
        pass

    def open_shop(self):
        pass


class 잡기판(object):
    """next_turn 부터 볼 던지기까지 진짜 메서드를 그대로 빌려 끼운다. 연출은 바로 끝난다."""

    def __init__(self, mode="new"):
        self.app = 가짜잡기앱(mode)
        self.root = 시간시계()
        self.b = {"id": 7, "over": False}
        self.ball_opts = [{"id": "POKEBALL", "count": 5}]
        self.closed = False
        self.busy = False
        self.jobs = []
        self.fx = None
        self.texts = []
        self.layer = None
        self.bars = None
        self.mine = 가짜도트(1)
        self.foe = 가짜도트(9)
        self.떠오른글씨 = []
        self.결과 = []
        self.menu_open = self.holding = self.finish = self.playing = self.stalled = False
        self.hold_job = self.hint_job = None
        self.pending_ball = None

    for _name in ("next_turn", "play", "turn_done", "start_hold", "_hint", "_cancel_hold_jobs",
                  "fight_on", "_menu_opened", "_menu_closed", "throw_ball", "_do_throw",
                  "after_ball", "after", "_safe", "abort", "_late_ball",
                  "_auto_setting", "stop_auto", "_ball_left", "_auto_again", "_auto_throw"):
        locals()[_name] = getattr(DB.DesktopBattle, _name)

    def render(self, ev, done):
        done()

    def sync_bars(self, snap=False):
        pass

    def float_over(self, pet, text, color, ms=None):
        self.떠오른글씨.append(text)

    def show_result(self, result):
        self.결과.append(result)

    def finish_cleanup(self):
        self.closed = True


class 이벤트(object):
    x_root = y_root = 10


def 잡기_준비(mode="new"):
    menus = []
    real_async, real_popup = DB.run_async, DB.ball_menu.popup
    DB.run_async = lambda root, fn, cb: cb(fn(), None)
    DB.ball_menu.popup = lambda root, e, opts, pick, on_close=None, **kw: menus.append((pick, on_close, kw))

    def 되돌리기():
        DB.run_async, DB.ball_menu.popup = real_async, real_popup
    return 잡기판(mode), menus, 되돌리기


def t_턴마다_잡기_설정을_보낸다():
    for mode, want in (("new", "new"), ("off", "off"), ("이상한값", "new")):
        d, _m, undo = 잡기_준비(mode)
        try:
            d.next_turn()
        finally:
            undo()
        chk("설정 %s -> 서버에 %s" % (mode, want), d.app.api.moves[:1] == [(want, False)], d.app.api.moves)


def t_멈추라고_하면_10초_기다렸다가_끝까지_싸운다():
    d, _m, undo = 잡기_준비()
    try:
        d.app.api.move_answers = [{"events": [{"t": "move", "who": "me"}], "hold": "low",
                                   "battle": {"id": 7, "over": False}}]
        d.next_turn()
        chk("멈춘다", d.holding, d.holding)
        chk("던지라고 알린다", any("던지세요" in m for m in d.app.말), d.app.말)
        d.root.advance(9900)
        chk("10초 안에는 다음 턴을 안 보낸다", len(d.app.api.moves) == 1, d.app.api.moves)
        chk("멈춘 동안 '지금 던지세요' 를 되풀이해 띄운다", d.떠오른글씨.count("지금 던지세요!") >= 3, d.떠오른글씨)
        d.root.advance(200 + 120)
        chk("10초가 지나면 끝까지 싸우기로 (finish) 다시 부른다",
            len(d.app.api.moves) == 2 and d.app.api.moves[1] == ("new", True), d.app.api.moves)
        chk("더는 멈춰 있지 않다", not d.holding)
        d.root.advance(5000)
        chk("그 뒤로도 finish 로 싸운다", all(f for _c, f in d.app.api.moves[1:]), d.app.api.moves)
    finally:
        undo()


def t_왼쪽_클릭하면_바로_싸운다():
    d, _m, undo = 잡기_준비()
    try:
        d.app.api.move_answers = [{"events": [], "hold": "nosafe", "battle": {"id": 7, "over": False}}]
        d.next_turn()
        chk("쓰러뜨릴 것 같다고 알린다", any("쓰러뜨릴 것 같다" in m for m in d.app.말), d.app.말)
        d.fight_on()
        d.root.advance(200)
        chk("바로 finish 로 부른다", d.app.api.moves[-1] == ("new", True), d.app.api.moves)
    finally:
        undo()


def t_볼_메뉴가_열린_동안은_싸우지_않는다():
    d, menus, undo = 잡기_준비()
    try:
        d.next_turn()                                   # 한 턴 -> 620ms 뒤 다음 턴이 걸려 있다
        d.throw_ball(이벤트())
        chk("메뉴가 뜬다", len(menus) == 1, menus)
        d.root.advance(5000)
        chk("메뉴가 열린 동안 턴을 안 보낸다", len(d.app.api.moves) == 1, d.app.api.moves)
        pick, on_close, _kw = menus[0]
        on_close()                                      # 안 고르고 닫았다
        d.root.advance(200)
        chk("닫으면 다시 싸운다", len(d.app.api.moves) == 2, d.app.api.moves)

        d.throw_ball(이벤트())
        pick, on_close, _kw = menus[1]
        on_close()                                      # PopupMenu 는 닫고 나서 고른 명령을 부른다
        pick("GREATBALL")
        chk("고르면 그 볼을 던진다", d.app.api.balls == ["GREATBALL"], d.app.api.balls)
    finally:
        undo()


def t_바쁠_때_던진_볼은_턴이_끝나고_던진다():
    d, _m, undo = 잡기_준비()
    try:
        d.busy = True
        d._do_throw("ULTRABALL")
        chk("서버를 기다리는 중이면 예약만 한다", d.pending_ball == "ULTRABALL" and not d.app.api.balls,
            (d.pending_ball, d.app.api.balls))
        d.busy = False
        d.turn_done({"battle": {"id": 7, "over": False}})
        d.root.advance(200)
        chk("턴이 끝나면 예약한 볼을 던진다", d.app.api.balls == ["ULTRABALL"], d.app.api.balls)
        chk("볼을 던지는 동안 턴을 끼워 보내지 않았다", d.app.api.moves == [], d.app.api.moves)

        d.playing = True
        d._do_throw(None)
        chk("연출 중에 두 번 클릭해도 예약 (마지막에 쓴 하이퍼볼)", d.pending_ball == "ULTRABALL", d.pending_ball)
        d.next_turn()
        chk("연출 중에는 턴을 안 보낸다", d.app.api.moves == [], d.app.api.moves)
    finally:
        undo()


def t_멈춘_채_던졌다가_놓치면_10초를_새로_센다():
    d, menus, undo = 잡기_준비()
    try:
        d.app.api.move_answers = [{"events": [], "hold": "low", "battle": {"id": 7, "over": False}}]
        d.next_turn()
        d.root.advance(6000)
        d.throw_ball(이벤트())
        d.root.advance(20000)
        chk("볼을 고르는 동안은 10초를 안 센다", len(d.app.api.moves) == 1 and d.holding, d.app.api.moves)
        pick, on_close, _kw = menus[0]
        on_close()
        pick("POKEBALL")
        chk("놓쳤다", d.app.api.balls == ["POKEBALL"] and d.holding, (d.app.api.balls, d.holding))
        d.root.advance(9500)
        chk("놓친 뒤 다시 10초를 기다린다", len(d.app.api.moves) == 1, d.app.api.moves)
        d.root.advance(1000)
        chk("그래도 안 던지면 끝까지 싸운다", d.app.api.moves[-1] == ("new", True), d.app.api.moves)
    finally:
        undo()


def t_놓친_뒤_야생이_숨으면_멈추지_않고_넘긴다():
    """게시판 #436: 멈춘 채 던졌다가 놓쳤는데 야생이 그 턴에 구멍파기로 숨었다. 숨은 동안은 도트 창이 숨어 볼도
    바로 싸우기도 못 누른다 - 계속 멈춰 있으면 10초 뒤 끝까지 싸우기로 올라온 야생을 쓰러뜨린다. 이제 멈춘 것을
    풀고(끝까지 싸우기가 아니다) 다음 턴을 부른다 (서버가 숨은 상대에게 안 닿는 기술로 한 턴을 넘긴다)."""
    class 숨음(object):
        def __init__(self):
            self.on = False

        def hidden(self, who):
            return self.on and who == "foe"

        def apply(self, who):                           # 놓친 볼이 도로 띄운 도트를 다시 숨긴다 (after_ball)
            pass

    d, menus, undo = 잡기_준비()
    try:
        d.hiding = 숨음()
        d.app.api.move_answers = [{"events": [], "hold": "low", "battle": {"id": 7, "over": False}}]
        d.next_turn()
        d.throw_ball(이벤트())
        pick, on_close, _kw = menus[0]
        on_close()
        d.hiding.on = True                              # 놓친 볼 뒤 야생이 구멍파기로 들어갔다
        pick("POKEBALL")
        chk("놓친 뒤 야생이 숨었으면 멈춘 것을 푼다", not d.holding and not d.finish, (d.holding, d.finish))
        d.root.advance(700)
        chk("  10초를 안 기다리고 다음 턴을 잡기 모드로 (finish 아님)", d.app.api.moves[1:] == [("new", False)],
            d.app.api.moves)
        d.hiding.on = False
        d.app.api.move_answers = [{"events": [], "hold": "low", "battle": {"id": 7, "over": False}}]
        d.root.advance(700)
        chk("  올라온 뒤 서버가 멈추라면 다시 멈춘다", d.holding and len(d.app.api.moves) == 3, (d.holding, d.app.api.moves))
        d.app.api.move_answers = []
        d.hiding.on = True
        d.turn_done({"hold": "low", "battle": {"id": 7, "over": False}})
        chk("  서버가 멈추라고 하면 숨어 있어도 멈춘다 (넘길 기술이 없을 때 - 서버를 끝없이 부르지 않게)", d.holding)
    finally:
        undo()


def t_배틀_중에도_잡힐_때까지_계속_던진다():
    """게시판 #446 (우가우가, 2.1.3): '지금 던지세요!' 가 떠야 안 잡은 포켓몬인 줄 아는데, 그때는 배틀이 시작된 뒤라
    '잡힐 때까지 계속 던지기' 를 켤 수 없었다. 이제 배틀의 볼 메뉴에도 그 줄이 있고, 켜 두고 던지면 멈춘 동안 놓칠
    때마다 10초를 기다리지 않고 같은 볼을 다시 던진다."""
    d, menus, undo = 잡기_준비()
    try:
        d.app.api.move_answers = [{"events": [], "hold": "low", "battle": {"id": 7, "over": False}}]
        d.next_turn()
        d.throw_ball(이벤트())
        pick, on_close, kw = menus[0]
        chk("배틀의 볼 메뉴에도 '계속 던지기' 줄 (꺼져 있음)", kw.get("auto") is False and kw.get("on_auto") is not None, kw)
        kw["on_auto"]()
        chk("  그 줄로 켠다 (배틀 밖과 같은 설정)", d.app.settings.get("autoThrow") is True)
        on_close()
        d.app.api.ball_answers = [{"caught": False, "balls": 4, "events": [], "battle": {"id": 7, "over": False}},
                                  {"caught": False, "balls": 3, "events": [], "battle": {"id": 7, "over": False}}]
        pick("POKEBALL")
        chk("놓쳤다 - 멈춘 그대로 (끝까지 싸우기 아님)", d.holding and not d.finish and d.app.api.balls == ["POKEBALL"],
            (d.holding, d.finish, d.app.api.balls))
        d.root.advance(400)
        chk("  10초를 기다리지 않고 같은 볼을 다시 던진다", d.app.api.balls == ["POKEBALL"] * 2, d.app.api.balls)
        chk("  싸우는 턴은 안 보낸다", len(d.app.api.moves) == 1, d.app.api.moves)
        chk("  몇 번째인지 알린다", any("계속 던지는 중 (2번째)" in m for m in d.app.말), d.app.말[-3:])
        d.app.api.ball_answers = [{"caught": True, "balls": 2, "events": [], "battle": {"id": 7, "over": True}}]
        d.root.advance(400)
        chk("  잡힐 때까지 (세 번째에 잡혔다)", d.app.api.balls == ["POKEBALL"] * 3, d.app.api.balls)
        d.root.advance(5000)
        chk("  잡히면 더 안 던진다", d.app.api.balls == ["POKEBALL"] * 3 and d.auto_ball is None, d.app.api.balls)
    finally:
        undo()

    # 왼쪽 클릭(바로 싸우기)이면 멈춘다 · 볼이 떨어지면 멈춘다 · 설정을 꺼 두면 예전처럼 10초
    d, menus, undo = 잡기_준비()
    try:
        d.app.settings["autoThrow"] = True
        d.app.api.move_answers = [{"events": [], "hold": "low", "battle": {"id": 7, "over": False}}]
        d.next_turn()
        d._do_throw("POKEBALL")
        chk("두 번 클릭으로 던져도 계속 던지기가 걸린다", d.auto_ball == "POKEBALL" and d.app.api.balls == ["POKEBALL"],
            (d.auto_ball, d.app.api.balls))
        d.fight_on()
        d.root.advance(1000)
        chk("왼쪽 클릭(바로 싸우기)이면 멈춘다", d.auto_ball is None and d.app.api.balls == ["POKEBALL"]
            and d.app.api.moves[-1] == ("new", True), (d.auto_ball, d.app.api.balls, d.app.api.moves))
    finally:
        undo()
    d, menus, undo = 잡기_준비()
    try:
        d.app.settings["autoThrow"] = True
        d.app.balls = 1
        d.app.api.move_answers = [{"events": [], "hold": "low", "battle": {"id": 7, "over": False}}]
        d.next_turn()
        d.app.api.ball_answers = [{"caught": False, "balls": 0, "events": [], "battle": {"id": 7, "over": False}}]
        d._do_throw("POKEBALL")
        d.root.advance(1000)
        chk("볼이 떨어지면 멈추고 알린다", d.app.api.balls == ["POKEBALL"] and d.auto_ball is None
            and any("볼이 떨어져" in m for m in d.app.말), d.app.말[-2:])
        chk("  그 뒤는 예전처럼 멈춰 기다린다 (10초)", d.holding and len(d.app.api.moves) == 1, d.app.api.moves)
    finally:
        undo()
    d, menus, undo = 잡기_준비()
    try:
        d.app.api.move_answers = [{"events": [], "hold": "low", "battle": {"id": 7, "over": False}}]
        d.next_turn()
        d._do_throw("POKEBALL")
        d.root.advance(3000)
        chk("설정이 꺼져 있으면 예전처럼 놓친 뒤 멈춰 기다린다", d.app.api.balls == ["POKEBALL"] and d.holding
            and getattr(d, "auto_ball", None) is None, d.app.api.balls)
        d.app.settings["autoThrow"] = True
        d.app.api.ball_answers = [{"caught": False, "balls": 5, "events": [], "battle": {"id": 7, "over": False}}] * 3
        d._do_throw("MASTERBALL")
        d.root.advance(3000)
        chk("마스터볼은 이어 던지지 않는다", d.app.api.balls == ["POKEBALL", "MASTERBALL"], d.app.api.balls)
    finally:
        undo()


def t_싸우는_중에_던져도_이어_던진다():
    """게시판 #466 (우가우가, 2.2.1): 계속 던지기를 켜 두고 **싸우는 중에**(멈추기 전에) 던지면 한 번 던지고 다시
    싸웠다 - 이어 던지기가 '지금 던지세요!' 로 멈춘 동안에만 됐다. 이제 그때부터 싸움을 멈추고 잡힐 때까지 던진다.
    게시판 #460 (다람): 한 번에 던지는 최대 개수를 볼 메뉴 '최대 N개까지' 로 고른다 (5 · 10 · 20 · 30, 기본 30)."""
    d, menus, undo = 잡기_준비()
    try:
        d.app.settings["autoThrow"] = True
        d.next_turn()                                    # 멈추지 않은 보통 턴 (서버가 hold 를 안 줬다)
        chk("싸우는 중이다 (멈추지 않았다)", not d.holding and len(d.app.api.moves) == 1, d.app.api.moves)
        d.throw_ball(이벤트())
        pick, on_close, kw = menus[-1]
        chk("배틀 메뉴에 '최대 N개까지' 줄 (기본 30)", kw.get("limit") == 30 and kw.get("on_limit") is not None, kw)
        for _ in range(2):
            kw["on_limit"]()
        chk("  누를 때마다 5 -> 10 -> 20 -> 30 -> 5 ... (30 에서 두 번 = 10)", d.app.settings.get("autoThrowMax") == 10,
            d.app.settings.get("autoThrowMax"))
        d.app.settings["autoThrowMax"] = 5
        on_close()
        d.app.api.ball_answers = [{"caught": False, "balls": 30, "events": [{"t": "move", "who": "foe"}],
                                   "battle": {"id": 7, "over": False}}] * 10
        moves = len(d.app.api.moves)
        pick("POKEBALL")
        chk("싸우는 중에 던지면 그때부터 멈춘다 (끝까지 싸우기도 풀린다)", d.holding and not d.finish, (d.holding, d.finish))
        d.root.advance(5000)
        chk("  싸우는 턴 없이 이어 던진다 - 최대 5개에서 멈추고 알린다", d.app.api.balls == ["POKEBALL"] * 5
            and len(d.app.api.moves) == moves and any("5번 던져" in m for m in d.app.말),
            (d.app.api.balls, d.app.api.moves[moves:], d.app.말[-2:]))
        chk("  다 던진 뒤에는 예전처럼 멈춰 기다린다 (10초 뒤 바로 싸우기)", d.holding and d.auto_ball is None)
    finally:
        undo()

    # 바쁠 때(턴을 기다리는 중) 던져 둔 볼 - 이어 던지기가 대신 던지고, 줄 서 있던 볼이 바로 싸우기를 막지 않는다
    d, menus, undo = 잡기_준비()
    try:
        d.app.settings["autoThrow"] = True
        d.busy = True
        d._do_throw("POKEBALL")
        chk("기다리는 중에 던지면 줄 세우고 멈춘다", d.pending_ball == "POKEBALL" and d.holding, (d.pending_ball, d.holding))
        d.busy = False
        d.app.api.ball_answers = [{"caught": False, "balls": 30, "events": [], "battle": {"id": 7, "over": False}}] * 3
        d.turn_done({"battle": {"id": 7, "over": False}})
        d.root.advance(400)
        chk("  턴이 끝나면 이어 던지기가 그 볼을 던진다 (줄 선 볼은 비운다)", d.app.api.balls[:1] == ["POKEBALL"]
            and d.pending_ball is None, (d.app.api.balls, d.pending_ball))
        d.fight_on()
        d.root.advance(1500)
        n = len(d.app.api.balls)
        chk("  왼쪽 클릭(바로 싸우기)이 먹는다 - 멈추고 끝까지 싸운다", not d.holding and d.finish and d.auto_ball is None
            and d.app.api.moves and d.app.api.moves[-1] == ("new", True), (d.holding, d.finish, d.app.api.moves[-1:]))
        d.root.advance(2000)
        chk("  그 뒤로는 안 던진다", len(d.app.api.balls) == n, d.app.api.balls)
    finally:
        undo()

    # 계속 던지기 중에 상대가 숨었다가 올라왔다 - 잡기 모드가 꺼져 있어 서버가 멈추라고 하지 않아도 이어 던진다
    class 숨음(object):
        def __init__(self):
            self.on = False

        def hidden(self, who):
            return self.on and who == "foe"

        def apply(self, who):
            pass
    d, menus, undo = 잡기_준비("off")
    try:
        d.hiding = 숨음()
        d.app.settings["autoThrow"] = True
        d.app.api.ball_answers = [{"caught": False, "balls": 30, "events": [], "battle": {"id": 7, "over": False}}] * 5
        d.hiding.on = True                              # 놓친 볼 뒤 상대가 땅속으로
        d._do_throw("POKEBALL")
        d.root.advance(700)                             # (풀고 TURN_GAP 뒤에 다음 턴)
        chk("숨으면 멈춘 것을 풀고 한 턴 넘긴다 (잡기 모드 꺼짐)", not d.holding and d.auto_ball == "POKEBALL"
            and len(d.app.api.moves) >= 1, (d.holding, d.auto_ball, d.app.api.moves))
        d.hiding.on = False                             # 올라왔다 (서버는 hold 를 안 준다)
        n = len(d.app.api.balls)
        d.root.advance(1500)
        chk("  올라오면 이어 던진다", len(d.app.api.balls) > n and d.holding, (len(d.app.api.balls), n, d.holding))
    finally:
        undo()


def t_볼이_흔들리는_동안_왼쪽_클릭은_싸우기가_아니다():
    """게시판 #222: 볼이 날아가거나 흔들리는 동안 '바로 싸우기' 가 먹으면 놓친 뒤에 그대로 쓰러뜨린다."""
    d, _m, undo = 잡기_준비()
    try:
        d.app.api.move_answers = [{"events": [], "hold": "low", "battle": {"id": 7, "over": False}}]
        d.next_turn()
        d.playing = True                                # 볼이 흔들리는 중
        d.fight_on()
        chk("흔들리는 동안에는 멈춘 그대로 ('끝까지 싸우기' 로 안 바뀐다)", d.holding and not d.finish,
            (d.holding, d.finish))
        d.playing = False
        d.pending_ball = "POKEBALL"                     # 던질 볼이 줄 서 있다
        d.fight_on()
        chk("  던질 볼이 줄 서 있어도 마찬가지", d.holding and not d.finish, (d.holding, d.finish))
        d.pending_ball = None
        d.fight_on()
        chk("  아무 일 없을 때의 왼쪽 클릭은 그대로 '바로 싸우기'", not d.holding and d.finish)
    finally:
        undo()


def t_두_번_클릭의_두_번째_뗌은_싸우기가_아니다():
    """게시판 #222: 멈춰 있을 때 두 번 클릭(바로 던지기)하면, 두 번째 클릭을 뗄 때 '왼쪽 클릭 = 바로 싸우기' 가
    또 예약돼서 볼이 날아가는 사이 '끝까지 싸우기' 로 바뀌었다."""
    import time as _time
    from poketdesktop import wild_ui as W
    배틀 = 가짜던지는배틀()
    배틀.holding = True
    ctl = 가짜야생조종(배틀)
    pet = W.WildPet.__new__(W.WildPet)
    pet.ctl = ctl
    pet._battle_job = None
    real_press, real_release = W.Pet.on_press, W.Pet.on_release
    W.Pet.on_press = lambda self, e: None
    W.Pet.on_release = lambda self, e: None
    ev = 이벤트()
    try:
        pet.on_press(ev)
        pet.on_release(ev)
        chk("첫 클릭은 '바로 싸우기' 를 조금 뒤로 예약한다 (두 번 클릭을 기다린다)", len(ctl.app.root.예약) == 1)
        pet.on_press(ev)
        pet.on_double(ev)
        chk("  두 번째 클릭은 그 예약을 지우고 볼을 던진다", not ctl.app.root.예약 and 배틀.메뉴 == [None],
            (ctl.app.root.예약, 배틀.메뉴))
        pet.on_release(ev)
        chk("  두 번째 클릭을 떼도 '바로 싸우기' 를 다시 예약하지 않는다", not ctl.app.root.예약, ctl.app.root.예약)
        pet._double_at = _time.time() - 5
        pet.on_press(ev)
        pet.on_release(ev)
        chk("  한참 뒤의 한 번 클릭은 그대로 '바로 싸우기'", len(ctl.app.root.예약) == 1)
    finally:
        W.Pet.on_press, W.Pet.on_release = real_press, real_release


def t_잡으면_끝낸다():
    d, _m, undo = 잡기_준비()
    try:
        d.app.api.move_answers = [{"events": [], "hold": "low", "battle": {"id": 7, "over": False}}]
        d.app.api.ball_answers = [{"caught": True, "balls": 4, "message": "신난다!"}]
        d.next_turn()
        d._do_throw("POKEBALL")
        d.root.advance(1000)
        chk("  '잡았다!' 를 읽을 틈을 두고 (1초 뒤에는 아직)", not d.closed, d.closed)
        d.root.advance(1000)
        chk("잡으면 배틀을 정리한다", d.closed, d.closed)
        chk("  연출이 터져서 접은 것이 아니다", not any("멈췄습니다" in m for m in d.app.말), d.app.말)
        chk("  내 포켓몬 위에 '잡았다!' (notify 는 화면에 안 뜬다, 1.13.2 게시판 #266)", "잡았다!" in d.떠오른글씨,
            d.떠오른글씨)
        chk("잡은 뒤에는 턴을 안 보낸다", len(d.app.api.moves) == 1, d.app.api.moves)
    finally:
        undo()


def t_볼을_기다리던_턴에_판이_끝나면_말없이_버리지_않는다():
    """게시판 #280 (니뉴, 10/19 18:54 · 18:59): 배틀이 시작되자마자 볼을 골랐는데, 이미 보낸 첫 턴에 메가망나뇽이
    한 방에 쓰러뜨렸다 (이미 잡은 종이라 잡기 모드 '아직 안 잡은 포켓몬만' 이 안 걸린다 - 그건 본래 규칙). 이번 턴
    뒤에 던지려던 볼은 말없이 버려졌고, app.notify 는 화면에 안 뜨니 '볼을 던지자 포켓몬이 증발했다' 로 보였다."""
    def 준비():
        d, menus, undo = 잡기_준비()
        d.show_result = DB.DesktopBattle.show_result.__get__(d)
        d.뜬글 = []
        d.app.float_over_pet = lambda pid, text, color="", ms=0: d.뜬글.append((pid, text))
        d.b = {"id": 7, "over": False, "me": {"id": 1, "name": "망나뇽"}}
        return d, menus, undo

    d, menus, undo = 준비()
    try:
        d.busy = True                                   # 첫 턴을 보내 놓고 답을 기다리는 중
        d.throw_ball(이벤트())                          # 오른쪽 클릭 -> 볼 메뉴
        menus[-1][0]("POKEBALL")                        # 몬스터볼을 고른다
        menus[-1][1]()                                  # 메뉴가 닫힌다
        chk("(답을 기다리는 중이라 볼은 예약만 - 검사 전제)", d.pending_ball == "POKEBALL" and not d.app.api.balls,
            (d.pending_ball, d.app.api.balls))
        d.busy = False
        d.turn_done({"battle": {"id": 7, "over": True, "result": "won", "foe": {"name": "아이스크"},
                                "me": {"id": 1, "name": "망나뇽"}}})
        d.root.advance(4000)
        chk("볼은 서버에 안 갔다 (줄지 않는다)", d.app.api.balls == [], d.app.api.balls)
        chk("배틀이 끝난 뒤 내 포켓몬 머리 위에 '볼을 던지기 전에 쓰러뜨렸다'",
            d.closed and (1, "볼을 던지기 전에 쓰러뜨렸다") in d.뜬글, (d.closed, d.뜬글))
        chk("  예약은 비운다", d.pending_ball is None, d.pending_ball)
        chk("  기록에는 볼이 그대로라는 것과 잡기 모드 안내까지",
            any("볼은 그대로" in m and "항상" in m for m in d.app.말), d.app.말)
    finally:
        undo()

    d, menus, undo = 준비()
    try:
        d.throw_ball(이벤트())
        d.closed = True                                 # 메뉴가 열린 사이에 판이 끝났다 (맥은 메뉴가 열려도 턴이 돈다)
        menus[-1][0]("ULTRABALL")
        chk("메뉴가 열린 사이에 끝났으면 고른 볼도 말없이 버리지 않는다",
            (1, "배틀이 끝나서 볼을 던지지 않았다") in d.뜬글 and d.app.api.balls == [], (d.뜬글, d.app.api.balls))
    finally:
        undo()

    d, menus, undo = 준비()
    try:
        나옴 = []
        d.switch_to = lambda mon: 나옴.append(mon)
        d.pending_ball = "POKEBALL"
        d.turn_done({"battle": {"id": 7, "over": True, "result": "lost", "me": {"id": 1, "name": "망나뇽"}},
                     "canSwitch": True, "party": [{"id": 2}]})
        chk("내 포켓몬이 쓰러져 다음 포켓몬이 나오면 판은 이어진다 - 볼 예약도 그대로",
            나옴 == [{"id": 2}] and d.pending_ball == "POKEBALL" and not d.뜬글, (나옴, d.pending_ball, d.뜬글))
    finally:
        undo()


def t_배틀을_접으면_서버에_알린다():
    """1.13.3: 앱이 배틀을 접은 까닭이 사용자 PC 의 poketdesktop.log 에만 남아서, 제보가 오면 그 파일을 열어 달라고
    해야 했다 (#266 레드 36세 · #280 니뉴). 이제 서버의 trouble 표로 보낸다 (trouble.py)."""
    from common.version import VERSION
    from poketdesktop import trouble
    real_run = trouble.RUN
    trouble.RUN = lambda fn: fn()                       # 뒤에서 보내는 것을 바로 부른다
    trouble._sent[:] = []
    d, _m, undo = 잡기_준비()
    try:
        보냄 = []
        d.app.api.report_trouble = lambda body: 보냄.append(body)
        d.b = {"id": 7, "over": False, "me": {"id": 1, "name": "이상해꽃"}}
        d.pending_ball = "POKEBALL"
        d.abort("다음 포켓몬을 화면에서 찾지 못했습니다.")
        chk("접으면 서버에 알린다 (무엇 · 어느 판 · 까닭 · 버전)", len(보냄) == 1 and 보냄[0]["kind"] == "battle_abort"
            and 보냄[0]["ref"] == 7 and 보냄[0]["message"] == "다음 포켓몬을 화면에서 찾지 못했습니다."
            and 보냄[0]["version"] == VERSION and 보냄[0]["os"], 보냄)
        chk("  그때의 상태를 같이 (내 포켓몬 · 화면의 도트 · 던질 볼 …)", 보냄 and all(
            k in 보냄[0]["detail"] for k in ("판 7", "내 포켓몬 1", "화면의 도트", "던질 볼 POKEBALL")), 보냄 and 보냄[0]["detail"])
        chk("  배틀은 그대로 접는다", d.closed)

        d2, _m2, undo2 = 잡기_준비()
        try:
            d2.app.api.report_trouble = lambda body: 보냄.append(body)

            def 터짐():
                raise KeyError("me")
            d2._safe(터짐)
            got = 보냄[-1]
            chk("연출이 터져 접으면 오류 내용(역추적)도 보낸다", got["message"] == "배틀을 이어가지 못해 멈췄습니다."
                and "KeyError" in got["detail"] and "터짐" in got["detail"], got["detail"][-300:])
            chk("  경로는 파일 이름만 (사용자 이름이 새지 않는다)", "test_battle_ui.py" in got["detail"]
                and HERE not in got["detail"] and os.sep + "test_battle_ui.py" not in got["detail"], got["detail"][-300:])
        finally:
            undo2()

        clean = trouble.clean
        chk("윈도우 경로 · 한글 사용자 이름", clean('File "C:\\Users\\홍길동\\AppData\\Local\\poketdesktop\\app\\desktop_battle.py", line 3')
            == 'File "desktop_battle.py", line 3', clean('File "C:\\Users\\홍길동\\AppData\\x.py"'))
        chk("  띄어쓰기가 있는 경로도 (따옴표 안)", clean("No such file: 'C:\\Program Files\\홍 길동\\poket.db'")
            == "No such file: 'poket.db'", clean("No such file: 'C:\\Program Files\\홍 길동\\poket.db'"))
        chk("  맥 경로 (따옴표 없이)", clean("at /Users/seok/Library/poketdesktop/x.py line 2") == "at x.py line 2",
            clean("at /Users/seok/Library/poketdesktop/x.py line 2"))
        chk("  경로가 아닌 글은 그대로", clean("HP 3/50 · 1/2 확률") == "HP 3/50 · 1/2 확률", clean("HP 3/50 · 1/2 확률"))

        trouble._sent[:] = []
        n = len(보냄)
        for _ in range(trouble.LIMIT_PER_HOUR + 3):
            trouble.send(d.app, "battle_abort", 7, "같은 오류")
        chk("한 시간에 %d개까지만 보낸다 (같은 오류가 되풀이돼도)" % trouble.LIMIT_PER_HOUR,
            len(보냄) - n == trouble.LIMIT_PER_HOUR, len(보냄) - n)
        trouble._sent[:] = []
        del d.app.api.report_trouble
        chk("알릴 길이 없는 api(옛 가짜)면 조용히 넘어간다", trouble.send(d.app, "battle_abort", 7, "x") is False)
    finally:
        trouble.RUN = real_run
        trouble._sent[:] = []
        undo()


def t_상대_이름표는_두_줄이다():
    """랜덤 배틀의 링 위 이름표 (1.10.2). 첫 줄에 [길드명] 닉네임 · 칭호, 둘째 줄에 티어."""
    full = {"name": "bro2000", "tierKr": "챔피언", "title": "시즌 1 챔피언", "guild": "나여"}
    chk("첫 줄 [길드명] 닉네임 · 칭호, 둘째 줄 티어",
        AR.plate_text(full) == "[나여] bro2000  ·  시즌 1 챔피언\n챔피언", AR.plate_text(full))
    chk("  칭호가 없으면 그 부분만 빠진다",
        AR.plate_text({"name": "bro2000", "tierKr": "챔피언", "guild": "나여"})
        == "[나여] bro2000\n챔피언")
    solo = {"name": "bro2000", "tierKr": "챔피언", "title": "시즌 1 챔피언"}
    chk("길드가 없으면 첫 줄은 닉네임 · 칭호",
        AR.plate_text(solo) == "bro2000  ·  시즌 1 챔피언\n챔피언", AR.plate_text(solo))
    chk("  빈 길드 이름도 없는 것으로 친다",
        AR.plate_text(dict(solo, guild="")) == AR.plate_text(solo)
        and AR.plate_text(dict(solo, guild=None)) == AR.plate_text(solo))
    chk("티어가 없으면 한 줄",
        AR.plate_text({"name": "bro2000", "title": "칭호", "guild": "나여"}) == "[나여] bro2000  ·  칭호")
    chk("아무것도 없으면 이름만, 이름도 없으면 '상대'",
        AR.plate_text({"name": "친구"}) == "친구" and AR.plate_text({}) == "상대"
        and AR.plate_text(None) == "상대")

    class Cv(object):
        """캔버스 흉내 - 글을 어떻게 그리라고 했는지만 적어 둔다."""
        def __init__(self):
            self.texts, self.rects, self.lowered = [], [], []

        def create_text(self, x, y, **kw):
            self.texts.append((x, y, kw))
            return 1

        def bbox(self, _item):
            return (100, 50, 300, 90)

        def create_rectangle(self, *xy, **kw):
            self.rects.append(xy)
            return 2

        def tag_lower(self, a, b):
            self.lowered.append((a, b))

    class Ring(object):
        _plate = AR.Arena._plate

        def __init__(self):
            self.cv, self.plates = Cv(), []

        def to_local(self, x, y):
            return x, y

    ring = Ring()
    ring._plate(490, 290, AR.plate_text(full), "#ffc043", anchor="se")
    kw = ring.cv.texts[0][2]
    chk("둘째 줄(티어)은 첫 줄의 가운데에 온다", kw.get("justify") == "center", kw)
    chk("  이름표는 그대로 링 오른쪽 아래에 붙고, 뒤에 판을 깐다",
        kw.get("anchor") == "se" and ring.cv.rects == [(94, 47, 306, 93)]
        and ring.cv.lowered == [(2, 1)] and ring.plates == [2, 1], (kw, ring.cv.rects))


# ---------------------------------------------------------------- 배틀 밖의 볼이 배틀로 간다 (1.10.4)
class 가짜던지는배틀(object):
    closed = False
    holding = False

    def __init__(self):
        self.던진것 = []
        self.메뉴 = []

    def _do_throw(self, ball=None):
        self.던진것.append(ball)

    def throw_ball(self, e=None):
        self.메뉴.append(e)


class 가짜뿌리(object):
    def __init__(self):
        self.예약 = {}
        self.n = 0

    def after(self, ms, fn):
        self.n += 1
        self.예약[self.n] = fn
        return self.n

    def after_cancel(self, j):
        self.예약.pop(j, None)


class 가짜야생조종(object):
    """WildController 에서 throw_ball 이 보는 것만."""

    def __init__(self, battle):
        self.app = type("앱", (), {})()
        self.app.battle = battle
        self.app.root = 가짜뿌리()
        self.app.balls = 5
        self.app.settings = {}
        self.throwing = False
        self.pet = object()
        self.wild_id = 7
        self.서버로 = []
        self.메뉴 = []

    def ball_menu(self, e):
        self.메뉴.append(e)


def t_배틀이_걸려_있으면_배틀_안에서_던진다():
    """볼 메뉴를 연 뒤에 배틀이 시작되면, 고른 볼이 배틀 밖의 길(/wild/catch)로 나갔다.

    야생은 잡혔는데 서버의 배틀은 안 끝나서 '배틀 중' 판정이 남았다 (게시판 #174).
    """
    from poketdesktop import wild_ui as W
    배틀 = 가짜던지는배틀()
    ctl = 가짜야생조종(배틀)
    W.WildController.throw_ball(ctl, "QUICKBALL")
    chk("배틀이 있으면 그 볼을 배틀에 넘긴다", 배틀.던진것 == ["QUICKBALL"] and not ctl.throwing, (배틀.던진것, ctl.throwing))
    배틀.closed = True
    ctl2 = 가짜야생조종(배틀)
    ctl2.throwing = True                       # 서버를 부르기 전에 멈추게 (여기서는 길만 본다)
    W.WildController.throw_ball(ctl2, "QUICKBALL")
    chk("끝난 배틀에는 안 넘긴다", 배틀.던진것 == ["QUICKBALL"], 배틀.던진것)


def t_볼_메뉴를_열면_예약해_둔_배틀을_취소한다():
    """왼쪽 클릭은 조금 기다렸다가 배틀을 건다 (두 번 클릭을 기다린다). 그 사이에 오른쪽 클릭으로
    볼 메뉴를 열면 메뉴 밑에서 배틀이 시작됐다."""
    from poketdesktop import wild_ui as W
    ctl = 가짜야생조종(None)
    pet = W.WildPet.__new__(W.WildPet)
    pet.ctl = ctl
    pet._battle_job = ctl.app.root.after(300, lambda: None)
    W.WildPet.on_menu(pet, "e")
    chk("예약이 지워졌다", pet._battle_job is None and not ctl.app.root.예약, ctl.app.root.예약)
    chk("  볼 메뉴는 그대로 뜬다", ctl.메뉴 == ["e"], ctl.메뉴)
    배틀 = 가짜던지는배틀()
    ctl.app.battle = 배틀
    W.WildPet.on_menu(pet, "e2")
    chk("  배틀 중이면 배틀의 볼 메뉴가 뜬다", 배틀.메뉴 == ["e2"] and ctl.메뉴 == ["e"], (배틀.메뉴, ctl.메뉴))
    pet2 = W.WildPet.__new__(W.WildPet)
    pet2.mon = {"shiny": False, "info": {"species": "꼬부기", "level": 5}}
    chk("표식에 '야생' 이라고 적지 않는다", W.WildPet.badge_text(pet2) == "꼬부기 Lv.5", W.WildPet.badge_text(pet2))
    pet2.mon["shiny"] = True
    chk("  색이 다른 개체는 별을 붙인다", W.WildPet.badge_text(pet2) == "★ 꼬부기 Lv.5", W.WildPet.badge_text(pet2))


def main():
    for fn in (t_체력을_그대로_반영한다, t_교체하면_새_포켓몬_체력으로_바뀐다, t_교체한_포켓몬이_아직_화면에_없으면_다시_찾는다,
               t_날려가서_끝나면_까닭을_알린다,
               t_숨은_도트의_체력바는_안_그린다, t_맞는_순간_그_쪽만_준다,
               t_틱은_창_순서를_안_올린다, t_투기장_틱도_창_순서를_안_올린다,
               t_배틀_동안_이름표를_막고_끝나면_한_번_푼다,
               t_막기_전에_끝나면_안_푼다, t_연출이_터져도_배틀을_접는다,
               t_싸우던_포켓몬이_파티에서_빠지면_바로_접는다,
               t_내_도트_창이_없어져도_정리는_끝난다, t_쓰러지면_이름표도_치운다,
               t_투기장은_제자리로_돌아온_뒤에_한_번_푼다,
               t_턴마다_잡기_설정을_보낸다, t_멈추라고_하면_10초_기다렸다가_끝까지_싸운다,
               t_왼쪽_클릭하면_바로_싸운다, t_볼_메뉴가_열린_동안은_싸우지_않는다,
               t_바쁠_때_던진_볼은_턴이_끝나고_던진다, t_멈춘_채_던졌다가_놓치면_10초를_새로_센다,
               t_놓친_뒤_야생이_숨으면_멈추지_않고_넘긴다,
               t_배틀_중에도_잡힐_때까지_계속_던진다,
               t_싸우는_중에_던져도_이어_던진다,
               t_볼이_흔들리는_동안_왼쪽_클릭은_싸우기가_아니다, t_두_번_클릭의_두_번째_뗌은_싸우기가_아니다,
               t_잡으면_끝낸다, t_볼을_기다리던_턴에_판이_끝나면_말없이_버리지_않는다, t_배틀을_접으면_서버에_알린다,
               t_상대_이름표는_두_줄이다,
               t_배틀이_걸려_있으면_배틀_안에서_던진다, t_볼_메뉴를_열면_예약해_둔_배틀을_취소한다):
        print("-- %s" % fn.__name__[2:])
        fn()
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
