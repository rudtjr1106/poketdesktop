# -*- coding: utf-8 -*-
"""에메랄드 테마의 실시간 배틀 창 - DP 실시간 창에 시안 A 의 장면 · 이름표 · 글상자 · 아래 화면 (battle.GBADuel)."""
from ..dp import live_battle as DPL
from .battle import GBADuel


class LiveBattleWindow(GBADuel, DPL.LiveBattleWindow):
    pass
