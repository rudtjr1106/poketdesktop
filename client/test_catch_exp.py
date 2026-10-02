# -*- coding: utf-8 -*-
"""잡았을 때의 경험치 — 화면 쪽 (1.8.1).

    python client/test_catch_exp.py

서버는 server/test_catch_exp.py 가 본다. 여기는 **받은 것을 화면이 제대로 다루는가**다.
경험치를 받으면 레벨업·기술 배우기·진화가 따라오는데, 잡았을 때는 그동안 그럴
일이 없어서 그 길이 아예 없었다. 빠뜨리면 진화한 포켓몬이 바탕화면에 옛 모습으로 남는다.

## 무엇을 못 박나

  1. 볼을 던질 때 "경험치를 받겠다" 를 같이 보낸다 (서버는 그래야 준다).
  2. exp_news: 알릴 말 · 배울 기술 줄 세우기 · 진화 목록 · 싸운 포켓몬의 몫.
  3. 배틀 중에 잡았을 때: 내 포켓몬 위에 '+N exp', 진화는 정리 뒤에.
  4. 싸우지 않고 잡았을 때: 파티 맨 앞 포켓몬 위에 '+N exp', 진화 연출을 튼다.
  5. 경험치가 안 실려 온 답(옛 서버)은 예전처럼 돈다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-catchexp-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import api as apimod                      # noqa: E402
from poketdesktop import desktop_battle as DB               # noqa: E402
from poketdesktop import wild_ui                            # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


GRANTS = [
    {"id": 7, "name": "리자드", "gained": 240, "level": 36, "levelBefore": 35,
     "leveledUp": True, "learned": ["화염방사"], "pending": [], "pendingIds": [],
     "shared": False,
     "evolve": {"from": "CHARMELEON", "to": "CHARIZARD", "fromKr": "리자드",
                "toKr": "리자몽", "fromNum": 5, "toNum": 6}},
    {"id": 8, "name": "피카츄", "gained": 60, "level": 20, "levelBefore": 20,
     "leveledUp": False, "learned": [], "pending": ["10만볼트"], "pendingIds": ["THUNDERBOLT"],
     "shared": True},
]


class Root(object):
    def __init__(self):
        self.jobs = []

    def after(self, ms, fn):
        self.jobs.append((ms, fn))
        return len(self.jobs)


class App(object):
    def __init__(self):
        self.root = Root()
        self.notes, self.learn, self.floats = [], [], []
        self.synced = 0
        self.box_window = None
        self.balls = 5
        self.overlay = type("Ov", (), {"area": lambda self: (0, 0, 800, 600)})()

    def notify(self, m):
        self.notes.append(m)

    def want_learn(self, pid, name=""):
        self.learn.append((pid, name))

    def float_over_pet(self, pid, text, color="#7bffa0", ms=1100):
        self.floats.append((pid, text))
        return True

    def request_sync(self):
        self.synced += 1


def api_part():
    print("=== 볼을 던질 때 ===")
    a = apimod.Api("http://127.0.0.1:1")
    sent = []
    a._call = lambda method, path, body=None, **kw: sent.append((path, body)) or {}
    a.wild_catch(12, "GREATBALL")
    a.battle_ball(34, "POKEBALL")
    chk("야생에 던질 때 exp 를 보낸다", sent[0][0] == "/api/wild/12/catch"
        and sent[0][1].get("exp") is True and sent[0][1]["ball"] == "GREATBALL", sent[0])
    chk("배틀 중에 던질 때도", sent[1][0] == "/api/battle/34/ball" and sent[1][1].get("exp") is True,
        sent[1])


def news_part():
    print("\n=== 받은 것에서 할 일 뽑기 ===")
    app = App()
    msgs, evolves, main = DB.exp_news(app, GRANTS)
    chk("레벨업과 배운 기술을 알린다", any("리자드 레벨 36" in m for m in msgs)
        and any("화염방사" in m and "배웠다" in m for m in msgs), msgs)
    chk("못 배운 기술은 줄을 세운다 (나중에 물어본다)", app.learn == [(8, "피카츄")]
        and any("10만볼트" in m and "배우려" in m for m in msgs), (app.learn, msgs))
    chk("진화는 어느 포켓몬인지(id)와 함께", evolves == [dict(GRANTS[0]["evolve"], pokemonId=7)],
        evolves)
    chk("싸운 포켓몬의 몫 (나눠 받은 것이 아닌 것)", main is GRANTS[0])
    chk("아무것도 안 왔으면 빈 것", DB.exp_news(App(), None) == ([], [], None)
        and DB.exp_news(App(), []) == ([], [], None))
    only_shared = [dict(GRANTS[1])]
    chk("나눠 받은 것만 있으면 몫은 없다", DB.exp_news(App(), only_shared)[2] is None)


class Pet(object):
    def __init__(self):
        self.played = []

    def play(self, name, once=False):
        self.played.append(name)


def battle_part():
    print("\n=== 배틀 중에 잡았을 때 ===")
    app = App()
    b = object.__new__(DB.DesktopBattle)
    b.app, b.closed, b.mine, b.foe = app, False, Pet(), object()
    b.pending_evolve = None
    floats, waits = [], []
    b.float_over = lambda pet, text, color: floats.append(text)
    b.after = lambda ms, fn: waits.append((ms, fn))
    b.after_ball({"caught": True, "message": "신난다! 꼬렛을 잡았다!", "exp": GRANTS})
    chk("잡았다는 말에 레벨업을 붙여 알린다", app.notes and "꼬렛을 잡았다" in app.notes[0]
        and "리자드 레벨 36" in app.notes[0], app.notes)
    chk("내 포켓몬 위에 받은 경험치", floats == ["+240 exp"], floats)
    chk("진화는 정리가 끝난 뒤에 튼다", b.pending_evolve == [dict(GRANTS[0]["evolve"], pokemonId=7)])
    chk("글씨가 뜰 시간을 두고 정리한다", waits and waits[0][0] >= 1000
        and waits[0][1] == b.finish_cleanup, waits and waits[0][0])
    chk("배울 기술을 줄 세운다", app.learn == [(8, "피카츄")])
    chk("야생은 볼에 들어갔다 · 내 포켓몬이 뛴다", b.foe is None and b.mine.played == ["Hop"])

    app2 = App()
    b2 = object.__new__(DB.DesktopBattle)
    b2.app, b2.closed, b2.mine, b2.foe = app2, False, Pet(), object()
    floats2, waits2 = [], []
    b2.float_over = lambda pet, text, color: floats2.append(text)
    b2.after = lambda ms, fn: waits2.append((ms, fn))
    b2.after_ball({"caught": True, "message": "잡았다!"})        # 옛 서버: exp 가 없다
    chk("경험치가 안 온 답은 예전처럼 (바로 정리)", app2.notes == ["잡았다!"] and floats2 == []
        and waits2[0][0] == 500 and b2.pending_evolve == [], (app2.notes, waits2[0][0]))


def wild_part():
    print("\n=== 싸우지 않고 잡았을 때 ===")
    app = App()
    w = object.__new__(wild_ui.WildController)
    w.app, w.throwing = app, True
    w.pet = type("P", (), {"x": 100, "y": 100, "fw": 40, "fh": 40})()
    cleared, checked, played = [], [], []
    w.clear = lambda: cleared.append(1)
    w.check = lambda *a, **k: checked.append(1)
    w._thrown = lambda r: "POKEBALL"
    real_ball, real_play = wild_ui.BallThrow, DB.play_evolutions
    # 볼 연출은 건너뛰고 끝났을 때 하는 일만 본다
    wild_ui.BallThrow = lambda ctl, start, target, shakes, caught, on_done, ball="POKEBALL": on_done()
    DB.play_evolutions = lambda a, infos: played.append(list(infos))
    try:
        w.play_throw({"caught": True, "shakes": 4, "message": "신난다! 구구를 잡았다!",
                      "pokemon": {"info": {}}, "exp": GRANTS})
        chk("잡았다는 말에 레벨업을 붙여 알린다", app.notes and "구구를 잡았다" in app.notes[0]
            and "리자드 레벨 36" in app.notes[0], app.notes)
        chk("파티 맨 앞 포켓몬 위에 받은 경험치", app.floats == [(7, "+240 exp")], app.floats)
        chk("배울 기술을 줄 세운다", app.learn == [(8, "피카츄")])
        chk("진화 연출을 예약한다 (볼 연출이 끝난 뒤에)", len(app.root.jobs) == 1
            and app.root.jobs[0][0] >= 500, app.root.jobs)
        app.root.jobs[0][1]()
        chk("  그 진화를 튼다", played == [[dict(GRANTS[0]["evolve"], pokemonId=7)]], played)
        chk("  동기화는 진화 연출이 부른다 (먼저 부르지 않는다)", app.synced == 0, app.synced)
        chk("풀숲을 치우고 다음 야생을 본다", cleared and checked and w.throwing is False)

        app3 = App()
        w.app, w.throwing = app3, True
        w.pet = type("P", (), {"x": 100, "y": 100, "fw": 40, "fh": 40})()
        w.play_throw({"caught": True, "shakes": 4, "message": "잡았다!",
                      "exp": [dict(GRANTS[1])]})
        chk("진화가 없으면 바로 동기화한다", app3.synced == 1 and app3.root.jobs == [])
        chk("  나눠 받기만 했으면 글씨는 안 띄운다", app3.floats == [])

        app4 = App()
        w.app, w.throwing = app4, True
        w.pet = type("P", (), {"x": 100, "y": 100, "fw": 40, "fh": 40})()
        w.play_throw({"caught": True, "shakes": 4, "message": "잡았다!"})   # 옛 서버
        chk("경험치가 안 온 답은 예전처럼", app4.notes == ["잡았다!"] and app4.synced == 1
            and app4.floats == [] and app4.learn == [])
    finally:
        wild_ui.BallThrow, DB.play_evolutions = real_ball, real_play


def main():
    api_part()
    news_part()
    battle_part()
    wild_part()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
