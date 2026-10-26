# -*- coding: utf-8 -*-
"""블랙·화이트 테마의 관장 배틀 창 (악당 · 길드전 공격도 이 창으로 싸운다).

그림은 battle.BWDuel 이 시안 H 대로 그린다 (어두운 장면 · 어두운 이름표 · 타입 띠 기술 카드 · 알약 단추).
판의 흐름(재생 · 보내기 · 결과의 줄)은 DP 관장 배틀 창 · 기본 창 그대로다.
"""
from ..dp import gym_battle as DPG
from .battle import BWDuel


class GymBattleWindow(BWDuel, DPG.GymBattleWindow):
    pass
