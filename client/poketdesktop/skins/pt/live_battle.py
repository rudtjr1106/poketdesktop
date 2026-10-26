# -*- coding: utf-8 -*-
"""플라티나 테마의 실시간 배틀 창 - DP 실시간 창(이름표의 '나' · 상대, 기다리는 판, 교체 자리)에
시안 B 의 장면 · 글상자 · 아래 화면(battle.PtDuel)."""
from ..dp import live_battle as DPL
from .battle import PtDuel


class LiveBattleWindow(PtDuel, DPL.LiveBattleWindow):
    pass
