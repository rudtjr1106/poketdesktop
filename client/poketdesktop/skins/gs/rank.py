# -*- coding: utf-8 -*-
"""금·은 테마의 랭킹 탭 - DP 화면 그대로, 머리 띠만 다른 화면과 같은 밤빛 갈색 (BAND).

DP 랭킹은 머리 띠에 보라 상수(PURPLE)를 쓰는데, 그 상수는 가방 · 상점의 설명 띠도 같이 쓴다 (금·은: 진한 밤빛).
그래서 상수는 그대로 두고 **랭킹 화면이 읽는 자리만** 이 테마일 때 바꿔 끼운다 (DP 파일은 안 고친다).
"""
from ..dp import rank as _dp
from . import BAND, BAND_LO

_dp.PURPLE, _dp.PURPLE_LO = BAND, BAND_LO

globals().update(dict((k, v) for k, v in vars(_dp).items() if not k.startswith("__")))
