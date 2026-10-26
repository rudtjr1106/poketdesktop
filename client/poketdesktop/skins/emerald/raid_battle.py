# -*- coding: utf-8 -*-
"""에메랄드 테마의 레이드 배틀 창 - DP 레이드 창에 시안 A 의 장면(하늘 · 땅 · 초록 받침) · 글상자 · 아래 화면
(battle.GBALower). 보스 판 · 참가자 판은 DP 배치 그대로, 빛깔만 종이 · 남색 테. '기권' 자리는 DP 처럼 '물러나기'."""
from ..dp import raid_battle as DPR
from .battle import GBALower


class RaidBattleWindow(GBALower, DPR.RaidBattleWindow):
    pass
