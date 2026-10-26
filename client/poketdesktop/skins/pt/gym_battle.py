# -*- coding: utf-8 -*-
"""플라티나 테마의 관장 배틀 창 (악당 · 길드전 공격도 이 창으로 싸운다).

위 장면 · 글상자 · 아래 화면은 battle.PtDuel (시안 B), 판의 흐름은 DP 관장 창 → 기본 창 그대로다.
"""
from ..dp import gym_battle as DPG
from .battle import PtDuel


class GymBattleWindow(PtDuel, DPG.GymBattleWindow):
    pass
