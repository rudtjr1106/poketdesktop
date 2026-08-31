# -*- coding: utf-8 -*-
"""poketdesktop 클라이언트."""
import os
import sys


def _find_common():
    """common 패키지를 import 할 수 있게 경로를 맞춘다.

    - 저장소에서 그냥 실행할 때: 저장소 루트를 sys.path 에 넣는다
    - exe 로 묶였을 때: PyInstaller 가 이미 넣어뒀으므로 아무것도 안 해도 된다
    """
    if getattr(sys, "frozen", False):
        return
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    if root not in sys.path:
        sys.path.insert(0, root)


_find_common()

try:
    from common.version import VERSION as __version__
except ImportError:                       # 최악의 경우에도 뜨기는 해야 한다
    __version__ = "0.0.0"
