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

    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
