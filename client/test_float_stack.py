# -*- coding: utf-8 -*-
"""떠오르는 글씨가 겹치지 않는가 — 화면 없이 돈다.

    python client/test_float_stack.py

배틀이 끝나면 '+120 exp' 와 주운 도구가 같은 자리에 같이 떴다. 한 방에
'급소!', '효과가 굉장하다!', '-38' 이 한꺼번에 뜨기도 한다. 셋 다 도트
머리 위 같은 좌표에서 시작해서 글씨가 포개져 아무것도 못 읽었다.

가짜 층(layer)을 만들어 Tk 없이 좌표만 본다. 진짜 캔버스가 필요 없는
계산이라 CI 의 '계산만 하는 검사' 에서 돈다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

os.environ.setdefault("POKET_HOME",
                      os.path.join(os.environ.get("TEMP", "/tmp"),
                                   "poket-float"))

from poketdesktop.fx_layer import FloatText                 # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class FakeCanvas(object):
    def __init__(self):
        self.n = 0
        self.at = {}

    def create_text(self, x, y, **kw):
        self.n += 1
        self.at[self.n] = (x, y)
        return self.n

    def move(self, it, dx, dy):
        x, y = self.at[it]
        self.at[it] = (x + dx, y + dy)

    def delete(self, it):
        self.at.pop(it, None)


class FakeRoot(object):
    """after 를 직접 돌린다. 부를 때까지 아무 일도 안 일어난다."""

    def __init__(self):
        self.jobs = []

    def after(self, _ms, fn):
        self.jobs.append(fn)
        return len(self.jobs)

    def after_cancel(self, _j):
        pass

    def run(self, n):
        for _ in range(n):
            jobs, self.jobs = self.jobs, []
            if not jobs:
                return
            for f in jobs:
                f()


class FakeLayer(object):
    def __init__(self):
        self.root = FakeRoot()
        self.cv = FakeCanvas()
        self.floats = []

    def to_local(self, sx, sy):
        return sx, sy                    # 좌표를 그대로 쓴다


def tops(ts):
    """지금 떠 있는 높이들."""
    return [t.y() for t in ts]


def main():
    print("=== 같은 자리에 한꺼번에 띄운다 ===")
    L = FakeLayer()
    ts = [FloatText(L, 500, 300, s) for s in
          ("급소!", "효과가 굉장하다!", "-38", "+120 exp")]
    ys = tops(ts)
    print("   시작 높이:", ys)
    chk("네 개가 다 다른 높이에서 시작한다", len(set(ys)) == 4, ys)
    gaps = [abs(a - b) for i, a in enumerate(ys) for b in ys[i + 1:]]
    chk("어느 둘도 %dpx 안쪽으로 안 붙는다" % FloatText.GAP,
        min(gaps) >= FloatText.GAP, sorted(gaps))

    print()
    print("=== 올라가는 동안에도 안 겹친다 ===")
    worst = 99
    for _ in range(14):
        L.root.run(1)
        ys = tops(ts)
        for i, a in enumerate(ys):
            for b in ys[i + 1:]:
                worst = min(worst, abs(a - b))
    print("   올라가는 내내 가장 가까웠던 거리: %dpx" % worst)
    chk("올라가는 내내 %dpx 이상 떨어져 있다" % FloatText.GAP,
        worst >= FloatText.GAP, worst)

    print()
    print("=== 멀리 떨어진 자리는 안 밀린다 ===")
    L2 = FakeLayer()
    a = FloatText(L2, 100, 300, "여기")
    b = FloatText(L2, 100 + FloatText.NEAR + 10, 300, "저기")
    chk("가로로 멀면 원래 높이 그대로", a.y() == b.y() == 300,
        (a.y(), b.y()))

    print()
    print("=== 끝난 글씨는 자리를 안 차지한다 ===")
    L3 = FakeLayer()
    old = FloatText(L3, 200, 300, "먼저")
    L3.root.run(20)                      # 다 올라가 사라진다
    chk("먼저 것이 끝났다", not old.items, old.items)
    new = FloatText(L3, 200, 300, "나중")
    chk("끝난 것 때문에 밀리지 않는다", new.y() == 300, new.y())
    chk("떠 있는 목록도 정리된다", len(L3.floats) == 1, L3.floats)

    print()
    print("=== 층에 floats 가 없어도 죽지 않는다 ===")
    L4 = FakeLayer()
    del L4.floats
    t = FloatText(L4, 10, 20, "옛 층")
    chk("옛 층에서도 뜬다", t.y() == 20, t.y())

    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
