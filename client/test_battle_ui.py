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

    def place(self):
        pass


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


def main():
    for fn in (t_체력을_그대로_반영한다, t_교체하면_새_포켓몬_체력으로_바뀐다,
               t_숨은_도트의_체력바는_안_그린다, t_맞는_순간_그_쪽만_준다,
               t_틱은_창_순서를_안_올린다, t_투기장_틱도_창_순서를_안_올린다):
        print("-- %s" % fn.__name__[2:])
        fn()
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
