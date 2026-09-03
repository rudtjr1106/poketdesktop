# -*- coding: utf-8 -*-
"""진화한 뒤에 어떤 도트를 들고 있는가.

    python client/test_evolve_sprite.py

창을 안 만든다. tk 가 필요한 부분(그림 올리기, 연출 타이머)만 가짜로
바꿔 끼우고, 도트를 고르는 계산은 진짜 코드를 그대로 돌린다.

## 왜 이 검사가 있나

바탕화면의 포켓몬은 거의 다 **걷는 도트**(4방향, 위로 가면 등이 보임)를
쓴다. 걷는 도트가 없는 종만 배틀 도트(좌우 2방향, 정면 고정)로 대신한다.

그런데 진화 연출은 새 모습을 받을 때 배틀 도트만 찾았다. 그래서 진화한
그 순간부터 그 한 마리만 정면으로 굳어서 안 걷고, 옆에서는 다른 애들이
계속 걸어다녔다. 실제로 그랬다.

고친 뒤에도 한 번 더 자빠졌다. 걷는 도트를 찾는 코드를 넣으면서
walk_cache 를 **들여오지 않았다**. work() 는 작업 스레드에서 돌고
run_async 가 예외를 잡아 done(None, err) 로 넘기기 때문에, NameError 가
화면에 아무 흔적도 남기지 않고 "도트를 못 받았다" 로만 보였다. 그래서
이 검사는 도트 종류까지 확인한다 - 안 터졌다는 것만으로는 모자란다.
"""
import os
import sys
import tempfile

TMP = os.path.join(tempfile.gettempdir(), "poket-test-evolve")
os.environ.setdefault("POKET_HOME", TMP)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from PIL import Image                                      # noqa: E402

from poketdesktop import evolve_fx, sprites                 # noqa: E402
from poketdesktop.sprites import DOWN, LEFT, RIGHT, UP      # noqa: E402

OK = FAIL = 0
SETTINGS = {"targetHeight": 48, "minScale": 0.25, "maxScale": 2.5,
            "showNames": False}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


# ---------------------------------------------------------------- 재료
def make_sheet(path):
    """걷는 도트 시트. 8행(아래/오른쪽/위/왼쪽 x 2) x 2칸, 칸은 32x32."""
    im = Image.new("RGBA", (32 * 2, 32 * 8), (0, 0, 0, 0))
    for row in range(8):
        for col in range(2):
            # 행마다 다른 색을 둬서 방향이 섞이면 알아볼 수 있게 한다.
            c = (40 + row * 25, 90, 200 - row * 20, 255)
            box = Image.new("RGBA", (14, 20), c)
            im.paste(box, (col * 32 + 9, row * 32 + 6))
    im.save(path)
    return path, {"ok": True, "frameW": 32, "frameH": 32, "durations": [8, 8]}


def make_battle(path):
    """배틀 도트 한 장."""
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", (18, 24), (220, 60, 60, 255)), (11, 8))
    im.save(path)
    return path


# ---------------------------------------------------------------- 가짜들
class FakeView(object):
    def __init__(self):
        self.size = None

    def resize(self, w, h):
        self.size = (w, h)

    def frames(self, pil_frames, key):
        # 진짜는 ImageTk.PhotoImage 목록. 길이만 맞춰준다.
        return ["photo%d" % i for i in range(len(pil_frames))]


class FakeWin(object):
    """Evolution.alive() 는 창이 아직 있는지로 살아있음을 판단한다."""

    def winfo_exists(self):
        return 1

    def withdraw(self):
        pass

    def destroy(self):
        pass


class FakeOverlay(object):
    def __init__(self):
        self.settings = dict(SETTINGS)
        self.paths = {}
        self.walks = {}

    def area(self):
        return (0, 0, 800, 600)


class FakePet(object):
    """Pet 에서 진화 연출이 실제로 만지는 것만 갖춘 껍데기."""

    def __init__(self, anim, overlay):
        self.ov = overlay
        self.anim = anim
        self.mon = {"id": 7, "num": 1, "shiny": False}
        self.x, self.y = 100.0, 100.0
        self.fw, self.fh = anim.w, anim.h
        self.facing = DOWN if isinstance(anim, sprites.WalkAnimation) else RIGHT
        self.frame = 0
        self.elapsed = 0
        self.state = "walk"
        self.battling = False
        self.walking_sprite = isinstance(anim, sprites.WalkAnimation)
        self.name_win = None
        self.win = FakeWin()
        self.label = None
        self.view = FakeView()
        self.photos = {}

    def hide_tip(self):
        pass

    def cancel_tip(self):
        pass

    def clamp(self):
        pass

    def redraw(self):
        pass

    def place(self):
        pass


class FakeApp(object):
    def __init__(self, overlay):
        self.root = None
        self.api = object()
        self.overlay = overlay
        self.settings = dict(SETTINGS)


# ---------------------------------------------------------------- 실행기
def run_evolution(pre_anim, walk_for_new, battle_path, to_num=2):
    """진화 연출의 도트 받기 단계만 끝까지 돌리고 결과를 돌려준다."""
    overlay = FakeOverlay()
    pet = FakePet(pre_anim, overlay)
    app = FakeApp(overlay)

    saved = (evolve_fx.U.run_async, evolve_fx.sprite_cache.ensure,
             evolve_fx.walk_cache.ensure)

    def run_async(root, fn, on_done):
        # 진짜와 같은 계약: work 가 터지면 결과 대신 예외를 넘긴다.
        try:
            on_done(fn(), None)
        except Exception as e:                              # noqa: BLE001
            on_done(None, e)

    evolve_fx.U.run_async = run_async
    evolve_fx.sprite_cache.ensure = lambda api, num, shiny: battle_path
    evolve_fx.walk_cache.ensure = lambda api, num: walk_for_new
    try:
        ev = evolve_fx.Evolution(app, pet, {"toNum": to_num, "toKr": "이상해풀"})
        ev.open_layer = lambda: None          # 캔버스는 안 만든다
        ev.after = lambda ms, fn: None        # 타이머도 안 건다
        ev.start()
    finally:
        (evolve_fx.U.run_async, evolve_fx.sprite_cache.ensure,
         evolve_fx.walk_cache.ensure) = saved
    return ev, pet, overlay


# ---------------------------------------------------------------- 검사
def main():
    os.makedirs(TMP, exist_ok=True)
    # 이것부터 본다. 안 들여온 채로 두면 아래 검사들은 도트를 바꿔 끼울
    # 자리조차 못 찾아서, 무슨 일인지 모를 예외로 끝난다.
    if not hasattr(evolve_fx, "walk_cache"):
        print("  FAIL evolve_fx 가 walk_cache 를 안 본다 - 진화할 때"
              " 걷는 도트를 아예 안 찾거나 NameError 로 죽는다")
        print()
        print("통과 0, 실패 1")
        return 1

    sheet_a, meta_a = make_sheet(os.path.join(TMP, "walk_a.png"))
    sheet_b, meta_b = make_sheet(os.path.join(TMP, "walk_b.png"))
    battle = make_battle(os.path.join(TMP, "battle.png"))

    pre = sprites.load_walk(sheet_a, meta_a, 48, 0.25, 2.5)

    print("걷는 도트가 있는 종으로 진화")
    ev, pet, ov = run_evolution(pre, (sheet_b, meta_b), battle)
    chk("걷는 도트를 골랐다",
        isinstance(ev.anim_new, sprites.WalkAnimation),
        "got %r" % type(ev.anim_new).__name__)
    chk("배틀 도트로 때우지 않았다", not isinstance(ev.anim_new, sprites.Animation))
    chk("Overlay 에 걷는 도트를 등록했다", ov.walks.get(2) == (sheet_b, meta_b),
        "walks=%r" % (ov.walks,))
    chk("배틀 도트 경로도 챙겼다", ov.paths.get((2, False)) == battle)

    if ev.anim_new is not None:
        evolve_fx.swap_sprite(pet, ev.anim_new)
        chk("네 방향을 다 옮겼다",
            set(pet.photos) == {DOWN, RIGHT, UP, LEFT},
            "photos=%r" % sorted(pet.photos))
        chk("걷는 도트라고 표시했다", pet.walking_sprite is True)
        chk("보던 방향을 그대로 본다", pet.facing == DOWN, "facing=%r" % pet.facing)

    print("걷는 도트가 없는 종으로 진화 (57마리)")
    ev2, pet2, ov2 = run_evolution(pre, (None, None), battle, to_num=3)
    chk("배틀 도트로 대신했다",
        isinstance(ev2.anim_new, sprites.Animation)
        and not isinstance(ev2.anim_new, sprites.WalkAnimation),
        "got %r" % type(ev2.anim_new).__name__)
    chk("걷는 도트는 등록하지 않았다", 3 not in ov2.walks, "walks=%r" % (ov2.walks,))

    if ev2.anim_new is not None:
        evolve_fx.swap_sprite(pet2, ev2.anim_new)
        chk("좌우 두 벌만 있다", set(pet2.photos) == {RIGHT, LEFT},
            "photos=%r" % sorted(pet2.photos))
        chk("걷는 도트가 아니라고 표시했다", pet2.walking_sprite is False)
        # 아래를 보고 있었는데 좌우뿐이다. 없는 방향을 들고 있으면
        # redraw() 가 KeyError 로 죽는다.
        chk("없는 방향에 머물지 않는다", pet2.facing in pet2.photos,
            "facing=%r" % pet2.facing)

    # 걷는 도트가 없는 종(배틀 도트로 서 있던 애)이 걷는 종으로 진화하는
    # 경우. 방향이 2개에서 4개로 늘어난다.
    print("배틀 도트였다가 걷는 종으로 진화")
    pre_battle = sprites.load_animation(battle, 48, 0.25, 2.5)
    ev3, pet3, ov3 = run_evolution(pre_battle, (sheet_b, meta_b), battle,
                                   to_num=4)
    chk("걷는 도트로 올라탔다",
        isinstance(ev3.anim_new, sprites.WalkAnimation),
        "got %r" % type(ev3.anim_new).__name__)
    if ev3.anim_new is not None:
        evolve_fx.swap_sprite(pet3, ev3.anim_new)
        chk("방향이 넷으로 늘었다", set(pet3.photos) == {DOWN, RIGHT, UP, LEFT},
            "photos=%r" % sorted(pet3.photos))
        chk("이제 걷는 도트다", pet3.walking_sprite is True)
        chk("보던 방향을 유지한다", pet3.facing == RIGHT,
            "facing=%r" % pet3.facing)

    print()
    print("통과 %d, 실패 %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
