# -*- coding: utf-8 -*-
"""금·은 테마의 관장 배틀 창 (악당 · 길드전 공격도 이 창으로 싸운다). DP 창 그대로, 그림만 GBC (battle.GBDuel)."""
from ..dp import gym_battle as DPG
from .battle import GBDuel


class GymBattleWindow(GBDuel, DPG.GymBattleWindow):
    pass
