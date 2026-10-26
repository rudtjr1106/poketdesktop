# -*- coding: utf-8 -*-
"""블랙·화이트 테마의 실시간 배틀 창 (상대도 사람이다).

DP 실시간 배틀 창 그대로 (상대 체력 숫자 숨김 · 기다림 판 · 서버가 준 교체 자리), 그림만 battle.BWDuel 이 그린다.
"""
from ..dp import live_battle as DPL
from .battle import BWDuel


class LiveBattleWindow(BWDuel, DPL.LiveBattleWindow):
    pass
