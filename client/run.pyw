# -*- coding: utf-8 -*-
"""포켓 데스크톱 실행 파일. pythonw 로 열면 콘솔 없이 백그라운드로 돈다.

`--action-view` 를 달면 맥의 액션 배틀 창(웹뷰 자식 프로세스, 2.6.0)만 띄운다 - 앱이 자기를 그렇게 한 번 더
부른다 (action_launch). 그때는 Tk · 한 번만 실행 잠금(single) · 앱을 불러오지 않는다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    from poketdesktop import action_view
    if action_view.FLAG in sys.argv:
        sys.exit(action_view.main())
    from poketdesktop.app import main
    main()
