# -*- coding: utf-8 -*-
"""팀 고르기 창(랭크 팀 · 길드전 방어팀 · 공격팀): 고른 자리를 끌어 다른 자리에 놓으면 순서가 바뀐다 (게시판 #516).

    python client/test_team_reorder.py        # 기본 테마, 끝나면 DP 테마로 한 번 더

예전에는 선두를 바꾸려면 여섯 마리를 다 빼고 차례대로 다시 넣어야 했다.
  1. move_slot: 3번 → 1번 (사이는 한 칸씩 밀림) · 빈 자리에 놓으면 맨 끝 · 같은 자리 · 없는 자리는 그대로.
  2. 옮기면 아래 줄에 "OO 을(를) 1번 자리로 옮겼습니다 - 먼저 나갑니다." · 목록 줄의 고른 차례 숫자도 바뀐다.
  3. 할 말이 없고 두 마리 이상이면 아래 줄에 순서 바꾸는 법 (MOVE_HINT). 겹친 도구 같은 진짜 까닭이 있으면 그것.
  4. 기본 테마: 고른 자리(글자 칸)만 끌 수 있고, 손을 뗀 자리로 옮긴다. 같은 자리 · 밖에서 떼면 그대로.
  5. DP 테마: 판을 눌렀다 같은 판에서 떼면 예전처럼 뺀다, 다른 판에서 떼면 옮긴다 (빈 판이면 맨 끝).
진짜 Tk 창을 띄운다. 서버는 test_held_rank_ui 의 가짜 api 를 쓴다.
"""
import os
import subprocess
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-team-reorder-")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import test_held_rank_ui as H                               # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins, ui_season                   # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0
ERRORS = []


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Ev(object):
    def __init__(self, x=0, y=0, under=None):
        self.x, self.y, self.x_root, self.y_root = x, y, 0, 0
        self.widget = self
        self._under = under

    def winfo_containing(self, _x, _y):
        return self._under


def open_team(root, app):
    tw = ui_season.TeamWindow(app, spec={"title": "길드전 방어팀", "note": "설명",
                                         "load": lambda: (app.api.pvp_team(), app.api.pokemon()),
                                         "save": app.api.pvp_set_team, "saved": "짰습니다"})
    H.pump(root, lambda: tw.mons and tw._wait is None)
    H.pump(root, lambda: False, 0.2)
    return tw


def order_marks(tw):
    """목록 줄의 고른 차례 숫자 (기본 테마만 - 글자 칸)."""
    out = {}
    for pid, (_f, _line, mark) in tw.rows.items():
        t = mark.cget("text")
        if t:
            out[pid] = int(t)
    return out


def main():
    print("=== 테마: %s ===" % (skins.active() or "기본"))
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    root.report_callback_exception = lambda *a: ERRORS.append(a)
    U.init_fonts(root)
    U.apply_theme(root)
    app = H.FakeApp(root)
    app.api.v5 = False                      # 겹친 도구 줄이 없게 (그 줄이 있으면 그것이 먼저 뜬다)

    print("-- 1. move_slot")
    tw = open_team(root, app)
    dp = not hasattr(tw, "slots")           # DP 계열은 자리를 캔버스 판으로 그린다
    chk("처음 팀 1 · 2 · 3", tw.picked == [1, 2, 3], tw.picked)
    chk("할 말이 없고 두 마리 이상이면 아래 줄에 순서 바꾸는 법", tw.team_hint()[0] == ui_season.MOVE_HINT,
        tw.team_hint())
    chk("3번 → 1번: 메타그로스가 선두, 나머지는 한 칸씩 밀림", tw.move_slot(2, 0) is True and tw.picked == [3, 1, 2],
        tw.picked)
    msg = H.status(tw)
    chk("  아래 줄: '메타그로스 을(를)…' 이 아니라 자연스럽게 + 1번 자리 · 먼저 나갑니다",
        "메타그로스를 1번 자리로 옮겼습니다" in msg and "먼저 나갑니다" in msg, msg)
    if not dp:
        chk("  목록 줄의 고른 차례 숫자도 바뀐다", order_marks(tw) == {3: 1, 1: 2, 2: 3}, order_marks(tw))
        chk("  자리 글도 그 차례", H.slots_text(tw).startswith("1. 메타그로스\n2. 한카리아스\n3. 갸라도스"),
            H.slots_text(tw))
    chk("빈 자리(6번)에 놓으면 맨 끝으로", tw.move_slot(0, 5) is True and tw.picked == [1, 2, 3], tw.picked)
    chk("같은 자리 · 없는 자리는 그대로", tw.move_slot(1, 1) is False and tw.move_slot(7, 0) is False
        and tw.move_slot(None, 0) is False and tw.picked == [1, 2, 3], tw.picked)

    if not dp:
        print("-- 2. 기본 테마: 끌어 놓기")
        H.pump(root, lambda: False, 0.1)
        labels = tw._slot_labels
        chk("고른 자리만 끌 수 있다 (fleur · 빈 자리는 아님)", [str(lb.cget("cursor")) for lb in labels]
            == ["fleur"] * 3 + [""] * 3, [str(lb.cget("cursor")) for lb in labels])
        tw._slot_press(2)
        chk("  누르면 그 자리에 표시", str(labels[2].cget("highlightbackground")) == U.ACCENT)
        tw._slot_release(Ev(under=labels[0]))
        chk("3번을 1번 자리에 놓으면 옮겨진다", tw.picked == [3, 1, 2], tw.picked)
        tw._slot_press(0)
        tw._slot_release(Ev(under=tw._slot_labels[0]))
        chk("  같은 자리에서 떼면 그대로", tw.picked == [3, 1, 2], tw.picked)
        tw._slot_press(1)
        tw._slot_release(Ev(under=None))
        chk("  자리 밖에서 떼면 그대로 · 표시는 거둔다", tw.picked == [3, 1, 2]
            and str(tw._slot_labels[1].cget("highlightbackground")) != U.ACCENT, tw.picked)
        tw._slot_press(0)
        tw._slot_release(Ev(under=tw._slot_labels[4]))
        chk("  빈 자리에 놓으면 맨 끝", tw.picked == [1, 2, 3], tw.picked)
    else:
        print("-- 2. DP 테마: 판 끌어 놓기")
        H.pump(root, lambda: len(getattr(tw, "_pboxes", {})) + len(getattr(tw, "_eboxes", {})) == 6, 3)

        def at(i):
            x1, y1, x2, y2 = tw._pboxes.get(i) or tw._eboxes[i]
            return Ev((x1 + x2) // 2, (y1 + y2) // 2)
        tw._press(at(2))
        tw._release(at(0))
        chk("3번 판을 1번 판에 놓으면 옮겨진다", tw.picked == [3, 1, 2], tw.picked)
        H.pump(root, lambda: False, 0.1)
        tw._press(at(0))
        tw._release(at(5))
        chk("  빈 판에 놓으면 맨 끝", tw.picked == [1, 2, 3], tw.picked)
        H.pump(root, lambda: False, 0.1)
        tw._press(at(1))
        tw._release(at(1))
        chk("  눌렀다 같은 판에서 떼면 예전처럼 뺀다", tw.picked == [1, 3], tw.picked)
        H.pump(root, lambda: False, 0.1)
        tw._press(at(4))
        tw._release(at(0))
        chk("  빈 판을 끌어도 아무 일 없음", tw.picked == [1, 3], tw.picked)
        tw._release(at(0))
        chk("  누르지 않고 떼기만 하면 아무 일 없음", tw.picked == [1, 3], tw.picked)

    print("-- 3. 진짜 까닭이 있으면 그것이 먼저")
    app.api.v5 = True
    H.close(root, tw)
    tw = open_team(root, app)
    hint = tw.team_hint()[0]
    chk("겹친 도구가 있으면 그 줄 (순서 안내 아님)", "같은 지닌 도구가 겹칩니다" in hint, hint)
    tw.picked = [1]
    chk("한 마리면 순서 안내 없음", tw.team_hint()[0] != ui_season.MOVE_HINT, tw.team_hint())
    H.close(root, tw)

    chk("창 오류 없음", not ERRORS, ERRORS[:2])
    root.destroy()
    print("\n%d OK, %d FAIL" % (OK, FAIL))
    bad = 1 if FAIL else 0
    if not os.environ.get("POKET_SKIN"):
        bad |= subprocess.call([sys.executable, os.path.abspath(__file__)], env=dict(os.environ, POKET_SKIN="dp"))
    return bad


if __name__ == "__main__":
    sys.exit(main())
