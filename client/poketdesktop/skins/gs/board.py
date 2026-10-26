# -*- coding: utf-8 -*-
"""금·은 테마의 게시판 탭 - DP 화면 그대로, 머리 띠만 다른 화면과 같은 밤빛 갈색 (BAND).

DP 게시판은 머리 띠에 꼬리표 테 상수(TAG_LINE)를 쓰는데, 그 상수는 묻는 창의 머리 줄 같은 데서도 같이 쓴다.
그래서 상수는 그대로 두고 **게시판 화면이 읽는 자리만** 이 테마일 때 바꿔 끼운다 (DP 파일은 안 고친다).
"""
from ..dp import board as _dp
from . import BAND

_dp.TAG_LINE = BAND

globals().update(dict((k, v) for k, v in vars(_dp).items() if not k.startswith("__")))
