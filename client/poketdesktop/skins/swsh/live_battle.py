# -*- coding: utf-8 -*-
"""소드·실드 테마의 실시간 배틀 창. 그림은 battle.SwDuel (남은 시간은 왼쪽 위 남색 판에), 흐름은 DP 실시간 창 그대로."""
from ..dp import live_battle as DPL
from .battle import SwDuel


class LiveBattleWindow(SwDuel, DPL.LiveBattleWindow):
    pass
