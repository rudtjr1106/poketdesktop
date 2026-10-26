# -*- coding: utf-8 -*-
"""소드·실드 테마의 관장 배틀 창 (악당 · 길드전 공격도 이 창). 위 장면 · 글상자 · 아래 칸 모두 battle.SwDuel
(시안 K 의 배틀 - 남색 빗금 장면 · 남색 이름표 · 오른쪽 세로 기술 · 분홍 원). 흐름은 DP 관장 창 그대로."""
from ..dp import gym_battle as DPG
from .battle import SwDuel


class GymBattleWindow(SwDuel, DPG.GymBattleWindow):
    pass
