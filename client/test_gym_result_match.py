# -*- coding: utf-8 -*-
"""관장 배틀 창 결과 칸: 길드전 1:1 (시즌 7) 판은 져도 서버가 준 줄(별 · 길드 코인)을 적는다.

    python client/test_gym_result_match.py

예전에는 이겼을 때만 서버 줄(reward.lines)을 적어서, 지고도 ★ 을 얻은 1:1 판의 '길드 코인 20개' 가 안 보였다 (11/12).
지도전 · 관장 판은 그대로 (졌을 때 서버 줄을 안 적는다). 창은 띄우지 않는다 - 결과 칸을 그리는 함수만 부른다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-gymres-")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import ui_gym_battle as G                  # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def lines_of(result, reward):
    cls = next(v for v in vars(G).values() if isinstance(v, type) and "_paint_result" in vars(v))
    w = object.__new__(cls)
    got = {}
    w.zoom_use = lambda: None
    w.hide_commands = lambda: None
    w.say = lambda *a, **k: None
    w._paint_result_panel = lambda res, title, lines: got.update(lines=lines)
    w.view = {"result": result, "trainer": {"name": "로켓_03", "role": "[로켓단]"}}
    w.reward = reward
    w.exp = []
    w._paint_result()
    return got["lines"]


def main():
    srv = ["★☆☆  로켓_03 님에게서 별 1개 (6마리 중 3마리 쓰러뜨림).", "길드 코인 20개 - 이번 시즌 20 / 300개."]
    ls = lines_of("lost", {"lines": srv, "war": {"mode": "match", "stars": 1}})
    chk("1:1 판을 져도 서버 줄(별 · 길드 코인)이 나온다", any("길드 코인 20개" in x for x in ls)
        and any("별 1개" in x for x in ls), ls)
    ls = lines_of("forfeit", {"lines": ["☆☆☆  로켓_03 님에게서 별 0개 (6마리 중 0마리 쓰러뜨림)."], "war": {"mode": "match"}})
    chk("  기권해도 서버 줄이 나온다", any("별 0개" in x for x in ls), ls)
    ls = lines_of("won", {"lines": srv, "war": {"mode": "match", "stars": 3}})
    chk("  이기면 예전처럼 '이겼다' + 서버 줄 (두 번 안 나온다)", sum(1 for x in ls if "길드 코인 20개" in x) == 1
        and any("이겼다" in x for x in ls), ls)
    ls = lines_of("lost", {"lines": ["지도전 줄"], "war": {"region": "c07", "wins": 1, "need": 3}})
    chk("지도전 판은 그대로 (졌을 때 서버 줄 없음)", not any("지도전 줄" in x for x in ls), ls)
    ls = lines_of("lost", None)
    chk("관장 판은 그대로 (보상 없음)", ls and "쓰러졌다" in ls[0], ls)
    print("\n%d OK, %d FAIL" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
