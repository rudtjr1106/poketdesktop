# -*- coding: utf-8 -*-
"""금·은 테마의 실시간 배틀 창. DP 창 그대로, 그림만 GBC (battle.GBDuel)."""
from ..dp import live_battle as DPL
from .battle import GBDuel


class LiveBattleWindow(GBDuel, DPL.LiveBattleWindow):
    pass
