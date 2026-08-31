# -*- coding: utf-8 -*-
"""포켓 데스크톱 실행 파일. pythonw 로 열면 콘솔 없이 백그라운드로 돈다."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poketdesktop.app import main

if __name__ == "__main__":
    main()
