# -*- coding: utf-8 -*-
"""걷기 말고 다른 동작들 — 자르기와 상태 고르기.

여기서 보는 것은 셋이다.

1. **시트를 바르게 자르는가.** 동작마다 칸 크기가 크게 다르고
   (걷기 32x40, 공격 80x80) Sleep 은 방향이 아예 없는 1행짜리다.
   행이 모자란 것을 모르고 자르면 시트 밖을 긁어서 빈 그림이 나온다.

2. **동작을 바꿔도 몸이 안 튀는가.** 창 왼쪽 위를 그대로 두면
   그림 크기가 바뀌는 만큼 포켓몬이 순간이동한다. 칸 한가운데를
   기준점으로 잡아야 제자리에 선다.

3. **여덟 방향을 각도에서 바르게 고르는가.**

그림은 시험용으로 여기서 만든다. 네트워크도 서버도 필요 없다 -
CI 에서 매번 GitHub 을 두드릴 이유가 없다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from PIL import Image                                       # noqa: E402

from poketdesktop import sprites as S                       # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def make_sheet(path, fw, fh, frames, rows):
    """행마다 다른 색으로 칠한 시트. 어느 행을 잘랐는지 색으로 안다."""
    im = Image.new("RGBA", (fw * frames, fh * rows), (0, 0, 0, 0))
    for r in range(rows):
        for c in range(frames):
            # 행 = 빨강, 프레임 = 초록. 가장자리 2px 는 비워 둔다
            # (union_bbox 가 잘라내는 여백을 흉내낸다).
            box = Image.new("RGBA", (fw - 4, fh - 4),
                            (20 + r * 25, 20 + c * 25, 200, 255))
            im.paste(box, (c * fw + 2, r * fh + 2))
    im.save(path)
    return path


def blanks(anim):
    """전부 투명색인 프레임 수. 시트 밖을 자르면 이렇게 나온다.

    '색 종류가 적으면 빈 것' 으로 세면 안 된다 - 여기 시험용 그림은
    칸마다 단색이라 멀쩡한데도 색이 하나뿐이다. 투명색과 견준다.
    """
    n = 0
    for fr in anim.frames.values():
        for f in fr:
            px = f.tobytes()
            if set(px) <= set(bytes(anim.key)):
                n += 1
    return n


def meta(fw, fh, durs, rows, src="pmd"):
    rowmap = (S.ROW_OF if src == "pmd" else None)
    m = {"ok": True, "frameW": fw, "frameH": fh, "durations": durs,
         "frames": len(durs), "rows": rows, "src": src}
    if src == "pmd":
        m["rowmap"] = {"down": 0, "downright": 1, "right": 2, "upright": 3,
                       "up": 4, "upleft": 5, "left": 6, "downleft": 7}
    else:
        m["rowmap"] = {"down": 0, "left": 1, "right": 2, "up": 3}
    return m


def main():
    import tempfile
    d = tempfile.mkdtemp(prefix="poket-anim-")

    print("=== 8방향 시트 ===")
    p = make_sheet(os.path.join(d, "walk.png"), 32, 40, 4, 8)
    walk = S.load_walk(p, meta(32, 40, [8, 10, 8, 10], 8), target_height=48)
    chk("여덟 방향이 다 나온다", len(walk.frames) == 8, len(walk.frames))
    chk("프레임 수가 맞다", walk.count() == 4, walk.count())
    uniq = len(set(f[0].tobytes() for f in walk.frames.values()))
    chk("방향마다 그림이 다르다", uniq == 8, uniq)
    chk("배율이 목표 높이에 맞다", abs(walk.h - 48) <= 2, walk.h)

    print("\n=== 1행짜리 (Sleep) ===")
    p = make_sheet(os.path.join(d, "sleep.png"), 32, 40, 2, 1)
    sl = S.load_walk(p, meta(32, 40, [30, 35], 1), scale=walk.scale,
                     name="Sleep")
    chk("여덟 방향을 다 준다", len(sl.frames) == 8, len(sl.frames))
    uniq = len(set(f[0].tobytes() for f in sl.frames.values()))
    chk("행이 하나뿐이라 방향이 다 같다", uniq == 1, uniq)
    chk("시트 밖을 긁지 않는다 (빈 그림 없음)", blanks(sl) == 0, blanks(sl))

    print("\n=== 배율은 한 종에서 하나 ===")
    p = make_sheet(os.path.join(d, "atk.png"), 80, 80, 10, 8)
    atk = S.load_walk(p, meta(80, 80, [2] * 10, 8), scale=walk.scale,
                      name="Attack")
    chk("걷기와 같은 배율을 쓴다", abs(atk.scale - walk.scale) < 1e-9,
        (atk.scale, walk.scale))
    chk("칸이 크면 그림도 크다", atk.h > walk.h, (atk.h, walk.h))
    # 배율을 안 물려주면 둘 다 목표 높이가 되어 공격할 때 몸이 작아진다
    solo = S.load_walk(p, meta(80, 80, [2] * 10, 8), target_height=48,
                       name="Attack2")
    chk("배율을 안 물려주면 같은 높이가 된다 (그래서 물려줘야 한다)",
        abs(solo.h - walk.h) <= 3, (solo.h, walk.h))

    print("\n=== 기준점 — 동작을 바꿔도 제자리 ===")
    # 창 왼쪽 위 = 기준점 - anchor. 기준점을 고정하면 창이 옮겨간다.
    cx, cy = 500.0, 300.0
    wx, wy = cx - walk.ax, cy - walk.ay
    ax_, ay_ = cx - atk.ax, cy - atk.ay
    chk("칸 한가운데가 같은 자리에 있다",
        abs((wx + walk.ax) - (ax_ + atk.ax)) < 1e-6
        and abs((wy + walk.ay) - (ay_ + atk.ay)) < 1e-6)
    # 왼쪽 위를 그대로 두면 얼마나 튀는지 (이게 우리가 피한 것)
    jump = ((walk.w - atk.w) ** 2 + (walk.h - atk.h) ** 2) ** 0.5 / 2
    chk("기준점을 안 쓰면 실제로 튄다 (%dpx)" % jump, jump > 10, jump)

    print("\n=== 4행짜리 출처 (followers) ===")
    p = make_sheet(os.path.join(d, "f.png"), 32, 32, 4, 4)
    fw_ = S.load_walk(p, meta(32, 32, [9] * 4, 4, src="follow"),
                      target_height=48)
    chk("여덟 방향을 다 준다", len(fw_.frames) == 8, len(fw_.frames))
    chk("시트 밖을 긁지 않는다", blanks(fw_) == 0, blanks(fw_))
    same = (fw_.frames[S.DOWNRIGHT][0].tobytes()
            == fw_.frames[S.RIGHT][0].tobytes())
    chk("대각선은 좌우로 때운다", same)

    print("\n=== 각도 -> 방향 ===")
    cases = [
        ((1, 0), S.RIGHT, "오른쪽"),
        ((-1, 0), S.LEFT, "왼쪽"),
        ((0, 1), S.DOWN, "아래"),
        ((0, -1), S.UP, "위"),
        ((1, 1), S.DOWNRIGHT, "아래오른쪽"),
        ((1, -1), S.UPRIGHT, "위오른쪽"),
        ((-1, 1), S.DOWNLEFT, "아래왼쪽"),
        ((-1, -1), S.UPLEFT, "위왼쪽"),
    ]
    for (vx, vy), want, label in cases:
        got = S.dir_from(vx, vy)
        chk("%s" % label, got == want, "%s 가 나왔다" % got)
    chk("멈춰 있으면 아래", S.dir_from(0, 0) == S.DOWN)
    # 가로를 우대한다 - 조금 기울었다고 대각선으로 넘어가면 부산스럽다
    chk("살짝 기운 것은 그대로 가로", S.dir_from(1, 0.3) == S.RIGHT,
        S.dir_from(1, 0.3))

    print("\n=== 네 방향만 쓰는 곳 ===")
    chk("dir_four 는 대각선을 안 준다",
        S.dir_four(1, 1) in (S.RIGHT, S.DOWN), S.dir_four(1, 1))

    print("\n=== 나중에 도착한 시트를 집어 드는가 ===")
    # 시트는 포켓몬이 나온 뒤에 뒷줄에서 받는다. 아직 안 온 것을
    # '없다' 로 굳혀 버리면 다 받고 나서도 영영 걷기만 한다.
    # 실제로 그랬다 - Idle 만 끝내 안 나왔다.
    from poketdesktop.overlay import Pet

    class FakeOv(object):
        def __init__(self):
            self.sheets = {}
            self.settings = {"targetHeight": 48}

    class FakePet(object):
        pass

    ov = FakeOv()
    fp = FakePet()
    fp.ov = ov
    fp.mon = {"num": 25}
    fp.walking_sprite = True
    fp.anims = {"Walk": walk}
    fp.miss = set()
    fp.base_scale = walk.scale

    chk("아직 안 온 것은 None (아직 판정 안 함)",
        Pet.anim_for(fp, "Idle") is None)
    chk("없다고 굳히지 않았다", (25, "Idle") not in fp.miss, fp.miss)

    p2 = make_sheet(os.path.join(d, "idle.png"), 40, 56, 6, 8)
    ov.sheets[(25, "Idle")] = (p2, meta(40, 56, [40, 2, 3, 3, 3, 2], 8))
    got = Pet.anim_for(fp, "Idle")
    chk("시트가 오면 그때 집어 든다", got is not None)
    chk("걷기 배율을 물려받았다",
        got is not None and abs(got.scale - walk.scale) < 1e-9)

    chk("두 번째부터는 기억해 둔 것을 준다",
        Pet.anim_for(fp, "Idle") is got)

    ov.sheets[(25, "Faint")] = (None, None)
    chk("정말 없는 것은 None", Pet.anim_for(fp, "Faint") is None)
    chk("그건 없다고 굳힌다 (매번 다시 안 본다)",
        (25, "Faint") in fp.miss, fp.miss)

    fp.walking_sprite = False
    fp.anims = {}
    fp.miss = set()
    chk("배틀 도트로 대신하는 종은 아무 동작도 없다",
        Pet.anim_for(fp, "Idle") is None)

    print("\n=== 오래 안 건드리면 쉰다 ===")
    # **이게 한 번 조용히 망가져 있었다.** 서 있은 틱을 셌는데, 상태
    # 기계가 idle 에서 반드시 walk 로 넘어가서 서 있는 시간이 길어야
    # 150틱이었다. 잠들기에는 영영 못 닿았다 - 111분을 돌려도 최고
    # 기록이 150틱. 그래서 시간으로 센다.
    from poketdesktop import overlay as O

    class SleepPet(object):
        """Pet.update 의 판단만 돌린다. 창도 그림도 안 만든다."""

        walking_sprite = True

        def __init__(self, have=("Sleep", "Sit", "Laying", "Idle", "Wake")):
            self.have = set(have)
            self.once = None
            self.state = "idle"
            self.battling = False
            self.timer = 10 ** 9        # 상태가 안 바뀌게
            self.calm_ms = 0
            self.sleeping = False
            self.rest_pose = None
            self.anim_name = "Walk"
            self.played = []
            self.moves = 0
            self.ov = type("O", (), {"settings": {"walkSpeed": 1,
                                                  "areaMargin": 0}})()

        def advance(self, ms):
            pass

        def pick_move(self):
            self.moves += 1

        def anim_for(self, name):
            return object() if name in self.have else None

        def play(self, name, once=False, then=None):
            if self.anim_for(name) is None:
                return False
            self.anim_name = name
            self.played.append(name)
            return True

        rest_anim = O.Pet.rest_anim
        wake = O.Pet.wake
        update = O.Pet.update

    MS = 33                                   # 30fps
    chk("30분이 지나야 쉰다", O.SLEEP_AFTER_MS == 1800000, O.SLEEP_AFTER_MS)

    p = SleepPet()
    for _ in range(int(O.SLEEP_AFTER_MS / MS) - 5):
        p.update(MS)
    chk("30분 전에는 안 쉰다", not p.sleeping)
    chk("그 전에는 앉지도 눕지도 않는다",
        not set(p.played) & {"Sit", "Laying", "Sleep"}, set(p.played))
    for _ in range(10):
        p.update(MS)
    chk("30분이 지나면 쉰다", p.sleeping)
    chk("앉기·눕기·자기 중 하나를 골랐다",
        p.rest_pose in ("Sit", "Laying", "Sleep"), p.rest_pose)
    chk("고른 그 자세를 돌린다", p.anim_name == p.rest_pose,
        (p.anim_name, p.rest_pose))

    x = len(p.played)
    for _ in range(300):
        p.update(MS)
    chk("쉬는 동안은 그 자세 그대로", p.sleeping and p.anim_name == p.rest_pose)
    chk("쉬면서 걷지 않는다", "Walk" not in p.played[x:], p.played[x:])

    # 셋 중에서 고르는지 (한 번 돌려서는 알 수 없다)
    seen = set()
    for i in range(60):
        q = SleepPet()
        for _ in range(int(O.SLEEP_AFTER_MS / MS) + 5):
            q.update(MS)
        seen.add(q.rest_pose)
    chk("셋이 다 나온다", seen == {"Sit", "Laying", "Sleep"}, seen)

    print("\n=== 만지면 일어나서 걷는다 ===")
    p.wake()
    chk("깬다", not p.sleeping)
    chk("깨는 모습을 보여준다", p.played[-1] == "Wake", p.played[-1])
    chk("일어나서 걷는다", p.state == "walk", p.state)
    chk("갈 곳을 새로 고른다", p.moves > 0, p.moves)
    chk("시계가 되돌아간다", p.calm_ms == 0)
    chk("자세를 놓는다", p.rest_pose is None, p.rest_pose)

    # Wake 가 끝나면 걷기로 돌아간다 (end_once 가 state 를 본다)
    chk("한 번짜리가 끝나면 걷기로 (state 가 walk 라서)",
        p.state == "walk")

    p2 = SleepPet(have=("Sleep", "Idle"))     # Wake 가 없는 종
    p2.sleeping = True
    p2.rest_pose = "Sleep"
    p2.wake()
    chk("Wake 가 없으면 그냥 걷는다",
        not p2.sleeping and p2.anim_name == "Walk", p2.anim_name)

    # 쉴 줄 모르는 종 (앉기·눕기·자기가 다 없다)
    p3 = SleepPet(have=("Idle",))
    for _ in range(int(O.SLEEP_AFTER_MS / MS) + 200):
        p3.update(MS)
    chk("쉬는 도트가 없는 종은 안 쉰다", not p3.sleeping)
    chk("그래도 숨은 쉰다", p3.anim_name == "Idle", p3.anim_name)

    # 배틀이 시작되면 조용히 깬다
    p4 = SleepPet()
    p4.sleeping = True
    p4.rest_pose = "Laying"
    p4.battling = True
    p4.update(MS)
    chk("배틀이 시작되면 깬다", not p4.sleeping)
    chk("그때는 깨는 모습을 안 낀다 (연출을 밀지 않게)",
        "Wake" not in p4.played, p4.played)

    print("\n=== 걷다 잠깐 서는 것과는 다르다 ===")
    p5 = SleepPet()
    p5.rest_pose = None
    chk("안 쉬는 중이면 그냥 숨쉬기", p5.rest_anim() == "Idle")
    p5.rest_pose = "Sit"
    chk("자세를 골랐어도 쉬는 중이 아니면 숨쉬기",
        p5.rest_anim() == "Idle", p5.rest_anim())
    p5.sleeping = True
    chk("쉬는 중이라야 그 자세", p5.rest_anim() == "Sit")
    p6 = SleepPet(have=("Idle", "Sleep"))
    p6.sleeping = True
    p6.rest_pose = "Sit"                      # 이 종에는 없는 자세
    chk("없는 자세를 골랐어도 숨은 쉰다", p6.rest_anim() == "Idle")
    chk("고를 수 있는 것은 앉기·눕기·자기",
        set(O.REST_POSES) == {"Sit", "Laying", "Sleep"}, O.REST_POSES)

    print("\n=== 배틀에서 동작이 튀지 않는가 ===")
    # 할퀴기 같은 접촉기를 쓸 때 도트가 튀었다. 배틀 연출은 좌표를
    # 잡아 뒀다가 되돌리는데, 그 사이에 동작이 끝나면서 창 크기가
    # 바뀌면 그 차이만큼 옆으로 밀린다.
    from poketdesktop import desktop_battle as DB, battle_fx as FX, app as APP
    import inspect

    for name in ("Attack", "Shoot", "Charge"):
        src = inspect.getsource(DB) + inspect.getsource(FX)
        chk("배틀이 %s 를 안 돌린다" % name, '"%s"' % name not in src)
        chk("%s 를 받아 두지도 않는다" % name, name not in APP.App.ANIM_ORDER)

    # 남긴 것(Hurt/Faint)은 기준점으로 되돌려야 한다. 왼쪽 위를 되돌리면
    # 크기가 바뀐 만큼 밀린다.
    for fn in ("lunge", "shake", "faint"):
        src = inspect.getsource(getattr(DB.DesktopBattle, fn))
        chk("%s 가 기준점을 쓴다" % fn, "pet.ax" in src or "pet.ay" in src)
        chk("%s 가 왼쪽 위를 그대로 되돌리지 않는다" % fn,
            "= hx" not in src and "= hy" not in src)

    # 실제로 얼마나 밀리는지 - 기준점을 안 쓰면 이만큼 튄다
    class P(object):
        pass
    walk_w, walk_h, hurt_w, hurt_h = 48, 48, 72, 70
    p_ = P()
    p_.x, p_.ax = 100.0, walk_w / 2.0
    cx = p_.x + p_.ax
    p_.ax = hurt_w / 2.0                       # 맞는 동작으로 바뀌었다
    good = cx - p_.ax
    bad = 100.0                                # 왼쪽 위를 그대로 되돌린 것
    chk("기준점으로 되돌리면 안 밀린다 (안 쓰면 %.0fpx 밀린다)"
        % abs(good - bad), abs((good + hurt_w / 2.0) - cx) < 1e-9)

    print("\n=== 이빨 연출 (물기·깨물어부수기·엄니) ===")
    # 예전에는 윗니 줄을 과녁 왼쪽에, 아랫니 줄을 오른쪽에 두고 서로 반대쪽을
    # 보게 그려서, 두 줄이 대각선으로 이어져 보였다 (사용자 제보).
    tx, ty = 200.0, 120.0
    up, lo = FX.fang_rows(tx, ty, 0)
    tips_u = [p_[2] for p_ in up]
    tips_l = [p_[2] for p_ in lo]
    chk("윗니 줄이 과녁 가운데에 선다 (대각선이 아니다)",
        abs(sum(tips_u) / len(tips_u) - tx) < 1e-6, tips_u)
    chk("아랫니 줄도 가운데에 선다", abs(sum(tips_l) / len(tips_l) - tx) < 1e-6, tips_l)
    chk("윗니는 위에, 아랫니는 아래에 있다",
        max(p_[1] for p_ in up) < ty < min(p_[1] for p_ in lo))
    chk("윗니는 아래를, 아랫니는 위를 본다 (서로 마주 본다)",
        all(p_[3] > p_[1] for p_ in up) and all(p_[3] < p_[1] for p_ in lo))
    chk("다 닫히면 맞물린다 (끝이 가운데를 넘는다)",
        min(p_[3] for p_ in up) > ty and max(p_[3] for p_ in lo) < ty)
    chk("아랫니는 윗니 사이로 들어간다",
        all(tips_u[i] < x < tips_u[i + 1] for i, x in enumerate(tips_l)))
    chk("벌어진 데서 한 칸씩 닫힌다",
        list(FX.FANG_OPEN) == sorted(FX.FANG_OPEN, reverse=True)
        and FX.FANG_OPEN[-1] == 0 and len(set(FX.FANG_OPEN)) == len(FX.FANG_OPEN))
    far = max(abs(v - ty) for p_ in sum(FX.fang_rows(tx, ty, FX.FANG_OPEN[0]), [])
              for v in p_[1::2])
    chk("가장 벌어져도 마무리 충격(반지름 75)보다 안쪽", far <= 75, far)

    print("\n=== 걷는 도트가 없는 종 (배틀 도트로 걷는다) ===")
    # 쇼다운 배틀 도트처럼 **왼쪽을 보는** 그림: 부리(빨강)가 왼쪽 끝에 있다.
    # 크라파 제보 - 오른쪽으로 걸을 때 왼쪽을 봐서 뒷걸음질로 보였다.
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    for y in range(10, 34):
        for x in range(12, 30):
            im.putpixel((x, y), (40, 40, 40, 255))          # 몸
    for y in range(16, 20):
        for x in range(2, 12):
            im.putpixel((x, y), (220, 40, 40, 255))         # 부리 (왼쪽)
    bp = os.path.join(d, "battle_left.gif")
    im.save(bp)

    def beak_side(frame, key):
        rgba = S.to_rgba(frame, key)
        w = rgba.width
        reds = [x for y in range(rgba.height) for x in range(w)
                if rgba.getpixel((x, y))[0] > 180 and rgba.getpixel((x, y))[1] < 90]
        return "left" if reds and max(reds) < w / 2 else ("right" if reds else "?")

    fight = S.load_animation(bp, 48)
    chk("관장 창용(load_animation) RIGHT 는 원본 그대로 왼쪽을 본다",
        beak_side(fight.frames[S.RIGHT][0], fight.key) == "left")
    walker = S.load_battle_walker(bp, 48)
    chk("걷기용 RIGHT 는 오른쪽을 본다 (오른쪽으로 걸을 때 앞을 본다)",
        beak_side(walker.frames[S.RIGHT][0], walker.key) == "right")
    chk("걷기용 LEFT 는 왼쪽을 본다",
        beak_side(walker.frames[S.LEFT][0], walker.key) == "left")
    chk("관장 창이 캐시한 그림은 그대로다 (좌우를 안 바꿨다)",
        beak_side(S.load_animation(bp, 48).frames[S.RIGHT][0], fight.key) == "left")
    chk("크기·배율은 같다", (walker.w, walker.h, walker.scale) == (fight.w, fight.h, fight.scale))

    print("\n=== 바꾼 배틀 도트는 캐시 이름이 다르다 (common/sprite_fix) ===")
    from poketdesktop import sprite_cache as SC
    chk("스토마는 판이 붙는다 (옛 납작한 그림을 안 쓴다)", SC._stem(618, False) == "0618-r2", SC._stem(618, False))
    chk("  이로치도", SC._stem(618, True) == "0618s-r2", SC._stem(618, True))
    chk("안 바꾼 종은 예전 이름", SC._stem(25, False) == "0025" and SC._stem(25, True) == "0025s")

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
