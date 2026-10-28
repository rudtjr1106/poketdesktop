# -*- coding: utf-8 -*-
"""연습판 화면 (하루 20판 뒤의 랜덤 배틀) - 랭킹 단추 · 머리줄 · 규칙 · 대전 기록 · 트레이 줄. 진짜 Tk 로 본다.

    python client/test_practice_ui.py

서버(server/test_pvp.py 의 '연습판')는 20판 뒤에도 받고 fight.practice 를 싣는다. 화면은
  · 새 서버: 단추가 '연습판 (점수 없음)', 머리줄 '이제 연습판 (점수 없음)', 트레이 '(연습판 · 점수 없음)'
  · 옛 서버(practice 칸 없음): 예전 글 그대로 ('오늘은 다 했습니다', '오늘은 다 함') - 옛 서버는 정말 막는다
  · 대전 기록 · 결과: '연습판 · 점수 변화 없음'
기본 화면을 본 뒤 같은 검사를 DP 테마(단추가 캔버스에 그린 CButton)로 한 번 더 돈다 (자식 프로세스).
"""
import os
import subprocess
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-practice-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins, ui_rank                     # noqa: E402
from poketdesktop import tray as TRAY                       # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


RULES = {"season": 4, "endsAt": "2026-11-27", "levelCap": 50,
         "practice": {"after": 20, "win": 100}}


class FakeApi(object):
    def __init__(self):
        self.mode = "practice"          # practice | normal | old

    def pvp_ranking(self):
        fight = {"foughtToday": 23, "dailyBattles": 20, "left": 0, "practice": True}
        rules = dict(RULES)
        if self.mode == "normal":
            fight = {"foughtToday": 8, "dailyBattles": 20, "left": 12, "practice": False}
        elif self.mode == "old":
            fight = {"foughtToday": 20, "dailyBattles": 20, "left": 0}
            rules.pop("practice")
        me = {"rp": 320, "tier": "super", "tierKr": "슈퍼볼", "ranked": False, "placementLeft": 2,
              "games": 3, "wins": 2, "losses": 1, "fight": fight}
        return {"ranking": [], "me": me, "season": 4, "placement": 5, "rules": rules, "hall": {}}

    def pvp_records(self, limit=30):
        return {"summary": {"games": 3, "wins": 2, "losses": 1},
                "records": [
                    {"id": 1, "foe": "연습상대", "foeId": 9, "kind": "random", "result": "win",
                     "started": True, "practice": True, "rp": 320, "rpDelta": 0, "reward": 100,
                     "turns": 8, "myLeft": 2, "foeLeft": 0, "matchId": None,
                     "at": "2026-10-29T01:00:00+00:00"},
                    {"id": 2, "foe": "걸어온연습", "foeId": 8, "kind": "random", "result": "lose",
                     "started": False, "practice": True, "rp": 320, "rpDelta": 0, "reward": 0,
                     "turns": 6, "myLeft": 0, "foeLeft": 1, "matchId": None,
                     "at": "2026-10-29T00:30:00+00:00"},
                    {"id": 3, "foe": "점수상대", "foeId": 7, "kind": "random", "result": "win",
                     "started": True, "rp": 320, "rpDelta": 18, "reward": 500,
                     "turns": 9, "myLeft": 3, "foeLeft": 0, "matchId": None,
                     "at": "2026-10-28T23:00:00+00:00"}]}


class FakeApp(object):
    def __init__(self, root):
        self.root = root
        self.api = FakeApi()
        self.rank_window = None

    def pvp_random(self, on_done=None, on_found=None):
        if on_found:
            on_found({"matchId": 1, "practice": self.api.mode == "practice"})


def pump(root, cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def btn_text(rw):
    b = rw.random_btn
    return b.label.cget("text") if hasattr(b, "label") else b.text


def head_sub(rw):
    return rw._rank_head()[1]


def status(rw):
    return rw.status._label.cget("text") if hasattr(rw, "status") else rw._status_msg[0]


def ui_checks(root):
    app = FakeApp(root)
    rw = ui_rank.RankWindow(app)
    pump(root, lambda: not rw.busy and rw.me)
    pump(root, lambda: False, 0.2)
    chk("20판 뒤(새 서버): 단추가 '연습판 (점수 없음)'", btn_text(rw) == "연습판 (점수 없음)", btn_text(rw))
    chk("  머리줄에 '이제 연습판 (점수 없음)'", "오늘 20판 끝 · 이제 연습판 (점수 없음)" in head_sub(rw),
        head_sub(rw))
    rules = rw._rules_data() or {}
    rtext = str(rules.get("text") or "")
    chk("  규칙에 연습판 한 줄 (이기면 100원)", "연습판 - 점수 변화 없음, 이기면 100원" in rtext, rtext[:300])
    if hasattr(rw, "sub"):
        rw.sub.update_idletasks()
        chk("  머리줄 글이 잘리지 않는다 (단추 글이 길어져도)", rw.sub.winfo_width() >= rw.sub.winfo_reqwidth(),
            (rw.sub.winfo_width(), rw.sub.winfo_reqwidth()))
    rw._random()
    pump(root, lambda: "연습판" in status(rw), 1.0)
    chk("  거는 중 글: 점수는 그대로", status(rw) == "연습판 대전 중... 점수는 그대로입니다", status(rw))

    app.api.mode = "normal"
    rw.reload()
    pump(root, lambda: not rw.busy and btn_text(rw) == "랜덤 배틀")
    chk("20판 전: 단추는 '랜덤 배틀'", btn_text(rw) == "랜덤 배틀", btn_text(rw))
    chk("  머리줄은 '오늘 12판 가능'", "오늘 12판 가능" in head_sub(rw), head_sub(rw))
    rw._random()
    pump(root, lambda: "대전 중" in status(rw), 1.0)
    chk("  거는 중 글은 예전 그대로", status(rw) == "대전 중... 끝나면 점수가 반영됩니다", status(rw))

    app.api.mode = "old"
    rw.reload()
    pump(root, lambda: not rw.busy and "다 했습니다" in head_sub(rw))
    chk("옛 서버(practice 없음): 단추·머리줄 예전 그대로", btn_text(rw) == "랜덤 배틀"
        and "오늘은 다 했습니다 (20판)" in head_sub(rw), (btn_text(rw), head_sub(rw)))
    rules = rw._rules_data() or {}
    chk("  규칙에 연습판 줄이 없다", "연습판" not in str(rules))

    app.api.mode = "practice"
    rw._toggle_mode()
    pump(root, lambda: not rw.busy and rw.records)
    rows = [rw._record_data(r) for r in rw.records]
    chk("대전 기록: 연습판 줄에 '연습판 · 점수 변화 없음'", "연습판 · 점수 변화 없음" in rows[0]["bits"]
        and "100원" in rows[0]["bits"] and "RP" not in rows[0]["bits"], rows[0]["bits"])
    chk("  걸려온 연습판도 연습판이라고 (점수·승패 글 대신)", "연습판 · 점수 변화 없음" in rows[1]["bits"]
        and "점수·승패에 안 들어감" not in rows[1]["bits"], rows[1]["bits"])
    chk("  점수판 줄은 그대로", "연습판" not in rows[2]["bits"] and "RP +18" in rows[2]["bits"], rows[2]["bits"])
    # 맥 Tk 8.6.17: 화면 밖에서 안 그려진 창을 바로 없애면 update() 가 돌아오지 않는다 - 화면 안에서 없앤다
    try:
        rw.win.geometry("+40+40")
        root.update()
    except tk.TclError:
        pass
    rw.close()
    root.update()


def tray_checks():
    import types
    a = types.SimpleNamespace(fight_left=0, fight_practice=True)
    chk("트레이: 20판 뒤(새 서버)는 '연습판 · 점수 없음'", TRAY.random_label(a) == "랜덤 배틀  (연습판 · 점수 없음)",
        TRAY.random_label(a))
    a.fight_practice = None
    chk("  옛 서버(모름)는 예전 그대로 '오늘은 다 함'", TRAY.random_label(a) == "랜덤 배틀  (오늘은 다 함)")
    a.fight_left, a.fight_practice = 3, False
    chk("  남았으면 'N판 남음'", TRAY.random_label(a) == "랜덤 배틀  (3판 남음)")
    chk("today_text: 옛 서버 글 그대로", ui_rank.today_text({"left": 0, "dailyBattles": 20}) == "오늘은 다 했습니다 (20판)")
    chk("  새 서버 다 쓴 날", ui_rank.today_text({"left": 0, "dailyBattles": 20, "practice": True})
        == "오늘 20판 끝 · 이제 연습판 (점수 없음)")
    # 서버는 이 표시가 있을 때만 20판 뒤에도 받는다 (없으면 옛 앱으로 보고 막는다). 랭킹 단추·트레이 둘 다
    # app.pvp_random -> api.pvp_random 하나로 가므로 여기만 보면 된다.
    from poketdesktop import api as API
    sent = []
    cli = API.Api("http://127.0.0.1:1")
    cli._call = lambda method, path, body=None, **kw: sent.append((method, path, body)) or {}
    cli.pvp_random()
    chk("랜덤 배틀 요청에 '연습판을 안다' 표시 (practice=1)",
        sent == [("POST", "/api/pvp/random", {"practice": 1})], sent)


def main():
    print("=== 테마: %s ===" % skins.active())
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    ui_checks(root)
    if skins.active() == skins.DEFAULT:
        tray_checks()
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    bad = 1 if FAIL else 0
    if not os.environ.get("POKET_SKIN"):
        # 같은 검사를 DP 테마로 (단추가 캔버스 CButton 이라 글을 바꾸는 길이 다르다)
        env = dict(os.environ, POKET_SKIN="dp")
        bad |= subprocess.call([sys.executable, os.path.abspath(__file__)], env=env)
    return bad


if __name__ == "__main__":
    sys.exit(main())
