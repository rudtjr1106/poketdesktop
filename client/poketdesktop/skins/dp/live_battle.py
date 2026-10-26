# -*- coding: utf-8 -*-
"""DP 테마의 실시간 배틀 창 (상대도 사람이다).

그림은 battle.DPDuel 이 그린다. 관장 배틀과 다른 것만 여기에:

  · 이름표 둘째 줄 오른쪽에 '나' / '상대 · 고름' (상대가 이번 턴을 골랐나)
  · 아래 화면 위 띠에 턴 · 남은 포켓몬 수 · 남은 시간 (5초 아래면 빨갛다)
  · 내가 고른 뒤에는 '○○ 님을 기다리는 중...' 판 (기권은 그대로 누를 수 있다)
  · 교체는 서버가 준 자리(me["switches"])만 고를 수 있다
"""
from ... import ui_live_battle as LB
from .battle import DPDuel


class LiveBattleWindow(DPDuel, LB.LiveBattleWindow):
    DONE_TEXT = "닫기"
    FOE_HP = False              # 상대 체력 숫자는 기본 창처럼 숨긴다 (막대만)

    def turn_text(self, view):
        me = view.get("me") or {}
        foe = view.get("foe") or {}
        return "%d턴 · %s · %d : %d" % (view.get("turn", 0), foe.get("name") or "상대",
                                       me.get("left", 0), foe.get("left", 0))

    def _plate_note(self, who, mon):
        return self.who_tag(who)

    def _plate_ok(self, i, m):
        side, _forced = self._switch
        return i in (side.get("switches") or [])

    def _paint_switch(self, me, forced, ask):
        DPDuel._paint_switch(self, me, forced, ask)
        if forced:
            self._peek(ask)                  # (이 창은 쓰러졌을 때 따로 말하지 않는다 - 글상자에 띄운다)
