# -*- coding: utf-8 -*-
"""맥에서 **윈도우 칸 높이**로 화면 검사를 돌린다.

    python client/run_as_windows.py client/test_raid_ui.py

맥은 본문이 12pt, 윈도우는 10pt 라 U.h() 가 1.2배 / 1.0배로 갈린다.
그래서 맥에서만 재면 고정 높이(머리줄·막대)가 윈도우에서 눌리는 것을
못 본다 - 관장(1.3.0) · 레이드(1.5.0) · 실시간(1.6.0) · 레이드 머리줄
(1.6.3) 이 전부 같은 자리에서 CI 윈도우 잡이 빨개진 뒤에야 드러났다.

**글꼴은 맥 것 그대로다.** 글자 폭이 달라서 생기는 줄바꿈·잘림은 여기서
못 본다 - 그건 CI 윈도우 잡이 봐야 한다. 여기서 보는 것은 칸 높이 산수뿐이다.
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import ui_common as U                     # noqa: E402


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    U.BASE_PT = 10                      # 윈도우와 같은 배율
    target = sys.argv[1]
    sys.argv = sys.argv[1:]
    runpy.run_path(target, run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
