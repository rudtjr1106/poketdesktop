# -*- coding: utf-8 -*-
"""투기장 좌표 검사.

    python client/test_layout.py

창을 하나도 안 만드는 순수 계산이라 화면 없이 돌아간다. 노트북부터
4K, 세로 모니터, 아주 작은 창까지 넣어 본다. 여기가 깨지면 도트가 화면
밖으로 나가거나 서로 겹쳐서 누가 누군지 안 보인다.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.poketdesktop import arena_layout as L      # noqa: E402

OK = FAIL = 0

SCREENS = [
    ("노트북 1366x768", 1366, 768),
    ("FHD 1920x1080", 1920, 1080),
    ("QHD 2560x1440", 2560, 1440),
    ("4K 3840x2160", 3840, 2160),
    ("세로 1080x1920", 1080, 1920),
    ("울트라와이드 3440x1440", 3440, 1440),
    ("작은 창 1024x600", 1024, 600),
    ("아주 작음 800x480", 800, 480),
    ("초저해상 640x400", 640, 400),
]
HEIGHTS = [40, 48, 64, 72, 96, 120]      # settings['targetHeight'] 범위


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


tight = [0]


def main():
    print("%-22s %6s %6s %7s %7s" % ("화면 (도트 72)", "반지름", "벌림",
                                     "어긋냄", "최소간격"))
    for name, w, h in SCREENS:
        for sh in HEIGHTS:
            rect = L.stage_rect((0, 0, w, h - 48))       # 작업표시줄 48px 가정
            ring = L.ring_of(rect, sh)
            for n in (1, 2, 3, 6):
                seats = [(s, i, L.seat_point(ring, s, i, n))
                         for s in ("me", "foe") for i in range(n)]
                spots = [p for _s, _i, p in seats] + list(L.duel_points(ring))
                for (sx, sy) in spots:
                    x, y = L.feet_to_topleft(sx, sy, sh, sh)
                    chk("%s h=%d n=%d 화면 안" % (name, sh, n),
                        -2 <= x and -2 <= y and x + sh <= w + 2
                        and y + sh <= h + 2, (round(x), round(y)))
                if n < 2:
                    continue
                # 겹치지 않는 것보다 화면 안에 있는 것이 먼저다.
                # 640x400 에 120px 도트 열두 마리는 물리적으로 안
                # 들어간다. 그런 조합은 겹침을 받아들이기로 했으므로,
                # 들어갈 수 있는 크기일 때만 겹침을 따진다.
                if L.fit_height(rect, sh, n) < sh - 0.5:
                    tight[0] += 1
                    continue
                for side in ("me", "foe"):
                    col = [L.seat_point(ring, side, i, n) for i in range(n)]
                    d = min(math.hypot(col[i + 1][0] - col[i][0],
                                       col[i + 1][1] - col[i][1])
                            for i in range(n - 1))
                    chk("%s h=%d n=%d 같은 편 안 겹침(%s)" % (name, sh, n, side),
                        d >= sh * 0.5, "최소 %.1f (필요 %.1f)" % (d, sh * 0.5))
                for i in range(n):
                    a = L.seat_point(ring, "me", i, n)
                    b = L.seat_point(ring, "foe", i, n)
                    chk("%s h=%d 좌우 안 겹침" % (name, sh),
                        abs(a[0] - b[0]) >= sh * 0.6, round(abs(a[0] - b[0])))
                    chk("%s 거울" % name,
                        abs((ring["cx"] - a[0]) - (b[0] - ring["cx"])) < 1e-6)
                    chk("%s 높이 같음" % name, abs(a[1] - b[1]) < 1e-6)
                # 위에서 아래로 순서가 뒤집히지 않아야 한다
                ys = [L.seat_point(ring, "me", i, n)[1] for i in range(n)]
                chk("%s h=%d 자리 순서" % (name, sh),
                    all(ys[i] < ys[i + 1] for i in range(n - 1)), ys)
            a, b = L.duel_points(ring)
            chk("%s h=%d 링 두 자리 간격" % (name, sh),
                b[0] - a[0] >= max(96, sh * 2.0), round(b[0] - a[0]))
            e = L.entry_point(ring, "foe", 0, 6)
            chk("%s 등장 지점은 화면 밖" % name, e[0] > rect[2], e)
            if sh == 72:
                col = [L.seat_point(ring, "me", i, 6) for i in range(6)]
                d = min(math.hypot(col[i + 1][0] - col[i][0],
                                   col[i + 1][1] - col[i][1]) for i in range(5))
                print("%-22s %6.0f %6.2f %7.1f %7.1f"
                      % (name, ring["r"], L.spread_for(6, ring["r"], sh),
                         L.stagger_for(6, ring["r"], sh), d))

    print("  (도트가 화면에 비해 너무 커서 겹침을 허용한 조합 %d개 —"
          " 화면 밖으로 나가지 않는 것만 확인했다)" % tight[0])
    print("\n======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
