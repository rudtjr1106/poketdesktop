# -*- coding: utf-8 -*-
"""DP 테마의 관장 배틀 창 (악당 · 길드전 공격도 이 창으로 싸운다).

그림은 battle.DPDuel 이 그린다. 판의 흐름(재생 · 보내기 · 결과의 줄)은 기본 창 그대로다.
"""
from ... import ui_gym_battle as GB
from .battle import DPDuel


class GymBattleWindow(DPDuel, GB.GymBattleWindow):

    def turn_text(self, view):
        return "%d턴 · %s" % (view.get("turn", 0), view["trainer"].get("name", ""))
