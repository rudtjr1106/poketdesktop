# -*- coding: utf-8 -*-
"""금·은 테마의 로그인 창 - DP 화면 그대로, 위 화면의 밤하늘(파랑 그러데이션)만 밤빛 갈색으로.

DP 는 그러데이션을 셈해서 칠하므로 (derive 의 빛깔 옮기기에 안 걸린다) 이 테마일 때 그 단계 빛깔만 바꿔 끼운다.
"""
from ..dp import login as _dp
from . import BAND, INK

_dp.SKY = ((0.0, INK), (0.6, "#4e3214"), (1.0, BAND))

globals().update(dict((k, v) for k, v in vars(_dp).items() if not k.startswith("__")))
