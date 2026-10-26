# -*- coding: utf-8 -*-
"""DP 테마의 기술 떠올리기 창 - 배우기 창과 같은 DP 기술 판 (skins/dp/learn.py 의 MoveRows).

떠올릴 값 · 무료 표시 · 결정은 기본 창(ui_remember.RememberAsk) 그대로다.
"""
from ... import ui_remember as RM
from .learn import MoveRows


class RememberAsk(MoveRows, RM.RememberAsk):
    pass
