# -*- coding: utf-8 -*-
"""독도 팀 (2.5.8, 게시판 #858) - 앱 쪽, 화면 없이.

    python client/test_champion_team_ui.py

  1. api: GET · PUT /api/champion/team
  2. 독도 창의 [독도 팀] 줄: 따로 정했으면 '독도 팀으로', 아니면 지금 싸우는 팀(랭크 팀 · 바탕화면 파티)으로 - 조사도 맞게
  3. [독도 팀 정하기] 는 랭크 팀 창을 독도 팀 spec 으로 연다 (불러오기 · 저장이 독도 팀 길로, 등록 풀기 단추가 있다)
  4. 팀 창의 '등록 풀기': 랭크 팀 창 · 독도 팀 창에는 있고, 길드전 팀 창에는 없다 (예전과 같다)
"""
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-champion-team-ui-"))

from poketdesktop import api as APIM                        # noqa: E402
from poketdesktop import ui_champion as UC                  # noqa: E402
from poketdesktop import ui_season as US                    # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def main():
    print("=== 독도 팀 (#858) - 앱")
    calls = []
    a = APIM.Api.__new__(APIM.Api)
    a._call = lambda method, path, body=None, **k: (calls.append((method, path, body)), {"registered": True, "ids": [3, 1]})[1]
    a.champion_team()
    a.champion_set_team(["3", 1])
    chk("1. api: GET · PUT /api/champion/team (id 는 숫자로)", calls == [("GET", "/api/champion/team", None),
                                                                ("PUT", "/api/champion/team", {"ids": [3, 1]})], calls)

    chk("2. 따로 정했으면 '독도 팀으로'", UC.team_text({"teamSet": True, "teamLabel": "독도 팀"}) == "독도에서는 독도 팀으로 싸웁니다.")
    chk("   아니면 지금 싸우는 팀 (조사도 맞게)", "랭크 팀으로 싸웁니다" in UC.team_text({"teamSet": False, "teamLabel": "랭크 팀"})
        and "바탕화면 파티로 싸웁니다" in UC.team_text({"teamSet": False, "teamLabel": "바탕화면 파티"}),
        (UC.team_text({"teamLabel": "랭크 팀"}), UC.team_text({"teamLabel": "바탕화면 파티"})))

    made = []

    class FakeTeamWindow(object):
        def __init__(self, app, on_saved=None, spec=None):
            made.append((app, on_saved, spec))
    real = US.TeamWindow
    US.TeamWindow = FakeTeamWindow
    try:
        api_calls = []
        api = types.SimpleNamespace(
            champion_team=lambda: (api_calls.append("get"), {"registered": False})[1],
            champion_set_team=lambda ids: (api_calls.append(("put", list(ids))), {"registered": bool(ids), "ids": list(ids),
                                                                                   "pokemon": []})[1],
            pokemon=lambda: (api_calls.append("pokemon"), [])[1])
        w = UC.LeagueWindow.__new__(UC.LeagueWindow)
        w.app = types.SimpleNamespace(api=api)
        w.reload = lambda: None
        w.pick_team()
        app, on_saved, spec = made[-1]
        chk("3. 랭크 팀 창을 독도 팀 spec 으로 연다", spec["title"] == "독도 팀" and on_saved == w.reload and "랭크 팀" in spec["note"])
        spec["load"]()
        chk("   불러오기는 독도 팀 · 내 포켓몬", api_calls == ["get", "pokemon"], api_calls)
        got = spec["save"]([5, 2])
        chk("   저장은 독도 팀 길로 (등록함 · 고른 순서만 돌려준다)", api_calls[-1] == ("put", [5, 2]) and got == {"registered": True, "ids": [5, 2]},
            (api_calls[-1], got))
        chk("   등록 풀기 단추가 있고, 풀면 랭크 팀으로 싸운다고 알린다", "랭크 팀으로" in (spec.get("unreg") or ""), spec.get("unreg"))
    finally:
        US.TeamWindow = real

    t = US.TeamWindow.__new__(US.TeamWindow)
    t.spec = {}
    rank = t._can_unreg()
    t.spec = {"title": "길드전 방어팀", "save": lambda ids: None}
    war = t._can_unreg()
    t.spec = {"title": "독도 팀", "unreg": "풀었다"}
    dokdo = t._can_unreg()
    chk("4. 등록 풀기: 랭크 팀 창 · 독도 팀 창에는 있고 길드전 팀 창에는 없다", rank and dokdo and not war, (rank, war, dokdo))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
