# -*- coding: utf-8 -*-
"""에메랄드 테마의 관장 배틀 창 (악당 · 길드전 공격도 이 창으로 싸운다).

장면 · 이름표 · 글상자 · 아래 화면을 시안 A 대로 (battle.GBADuel). 판의 흐름은 DP · 기본 창 그대로다.
"""
from ..dp import gym_battle as DPG
from .battle import GBADuel


class GymBattleWindow(GBADuel, DPG.GymBattleWindow):
    pass
