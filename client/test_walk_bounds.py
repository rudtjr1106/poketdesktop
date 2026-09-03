# -*- coding: utf-8 -*-
"""활동 영역이 바뀌었을 때 도트가 어떻게 구는가.

    python client/test_walk_bounds.py

창을 안 만드는 순수 계산이라 화면 없이 돌아간다.

## 왜 이 검사가 있나

노트북을 닫았다 열면(또는 모니터를 뺐다 꽂으면) 화면 구성이 바뀌고
활동 영역도 같이 줄어든다. 그때 도트가 새 영역 **밖에** 남는데,
예전 코드는 튕기기만 해서 영영 못 돌아왔다.

    if nx < 왼쪽 or nx > 오른쪽:   vx = -vx;  return

vx 를 뒤집어도 여전히 밖이라 다음 틱에 또 튕긴다. 그게 끝없이 반복되며
**제자리에서 좌우로 고개만 흔든다.** 실제로 그랬다.

윈도우에서도 해상도를 바꾸면 같은 일이 난다.
"""
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-test-bounds"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop.overlay import Pet                       # noqa: E402
from poketdesktop.sprites import LEFT, RIGHT               # noqa: E402

OK = FAIL = 0
SETTINGS = {"areaMargin": 8, "walkSpeed": 2.0}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def section(t):
    print("-- %s" % t)


class FakeOv(object):
    def __init__(self, rect):
        self.rect = rect
        self.settings = SETTINGS

    def area(self):
        return self.rect


class FakePet(object):
    """창을 안 만들고 움직임 로직만 돌린다."""

    walking_sprite = False

    def __init__(self, ov, x, y, vx=1.0, vy=0.0):
        self.ov = ov
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = vx, vy
        self.fw = self.fh = 48
        self.state = "walk"
        self.battling = False
        self.timer = 10 ** 9          # 상태가 안 바뀌게 아주 크게
        self.walked = 0.0
        self.facing = RIGHT
        self.frame = 0
        self.elapsed = 0
        self.turns = 0
        self.places = 0

    # 화면을 안 만들므로 그리는 것은 전부 비운다
    def advance(self, ms):
        pass

    def redraw(self):
        pass

    def place(self):
        self.places += 1

    def pick_move(self):
        pass

    def turn_to(self, vx, vy):
        self.turns += 1
        Pet.turn_to(self, vx, vy)

    clamp = Pet.clamp
    update = Pet.update


def run(pet, n=60):
    for _ in range(n):
        pet.update(33)


def t_stuck_outside():
    section("영역이 줄어 밖에 남았을 때 (노트북을 닫았다 열면 이렇게 된다)")
    # 1920 짜리 화면에서 놀다가, 1440 짜리만 남은 상황
    ov = FakeOv((0, 30, 1440, 804))
    pet = FakePet(ov, 1700, 400)          # 오른쪽 밖
    start = (pet.x, pet.y)
    run(pet)
    chk("제자리에 안 갇힌다", (pet.x, pet.y) != start, (pet.x, pet.y))
    chk("영역 안으로 들어온다",
        8 <= pet.x <= 1440 - 48 - 8, pet.x)
    chk("고개만 흔들지 않는다 (방향 전환 몇 번 안 한다)",
        pet.turns <= 2, pet.turns)


def t_outside_every_side():
    section("어느 쪽으로 나가 있어도 돌아온다")
    ov = FakeOv((0, 30, 1440, 804))
    for name, (x, y) in (("오른쪽", (1700, 400)), ("왼쪽", (-300, 400)),
                         ("위", (500, -100)), ("아래", (500, 1500)),
                         ("오른쪽 아래", (2000, 1600))):
        pet = FakePet(ov, x, y)
        run(pet, 5)
        inside = (8 <= pet.x <= 1440 - 48 - 8
                  and 30 + 8 <= pet.y <= 804 - 48 - 8)
        chk("%s 밖에서 돌아온다" % name, inside, (pet.x, pet.y))


def t_normal_walk_unchanged():
    section("평소 걷기는 그대로다")
    ov = FakeOv((0, 30, 1440, 804))
    pet = FakePet(ov, 700, 400, vx=1.0, vy=0.0)
    run(pet, 10)
    chk("한가운데서는 그냥 걷는다", pet.x > 700, pet.x)
    chk("걸은 거리가 쌓인다", pet.walked > 0, pet.walked)
    chk("괜히 방향을 안 바꾼다", pet.turns == 0, pet.turns)


def t_bounce_at_edge():
    section("가장자리에서는 튕긴다")
    ov = FakeOv((0, 30, 1440, 804))
    # 오른쪽 끝 바로 앞에서 오른쪽으로 걷는 중
    pet = FakePet(ov, 1440 - 48 - 8 - 1, 400, vx=1.0, vy=0.0)
    run(pet, 3)
    chk("방향이 뒤집힌다", pet.vx < 0, pet.vx)
    chk("왼쪽을 본다", pet.facing == LEFT, pet.facing)
    chk("영역 안에 있다", pet.x <= 1440 - 48 - 8, pet.x)


def t_edge_walking_in():
    section("가장자리에 붙어 안쪽으로 갈 때는 안 튕긴다")
    ov = FakeOv((0, 30, 1440, 804))
    # 왼쪽 끝에 딱 붙어 있는데 오른쪽(안쪽)으로 가려는 중
    pet = FakePet(ov, 8, 400, vx=1.0, vy=0.0)
    v0 = pet.vx
    run(pet, 3)
    chk("방향을 안 뒤집는다", pet.vx == v0, pet.vx)
    chk("안쪽으로 움직인다", pet.x > 8, pet.x)


def t_area_smaller_than_pet():
    section("영역이 도트보다 작아도 안 죽는다")
    ov = FakeOv((0, 30, 40, 60))          # 도트(48)보다 좁다
    pet = FakePet(ov, 500, 500)
    try:
        run(pet, 5)
        chk("죽지 않는다", True)
    except Exception as e:                                  # noqa: BLE001
        chk("죽지 않는다", False, repr(e))


def main():
    for fn in (t_stuck_outside, t_outside_every_side, t_normal_walk_unchanged,
               t_bounce_at_edge, t_edge_walking_in, t_area_smaller_than_pet):
        fn()
    print()
    print("=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
