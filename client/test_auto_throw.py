# -*- coding: utf-8 -*-
"""잡힐 때까지 계속 던지기 (2.1.1, 게시판 #425 레드 36세) - 볼 메뉴 줄과 이어 던지기 판단.

    python client/test_auto_throw.py

Tk 창은 안 띄운다: 서버 답 · 볼 연출 · after 를 가짜로 바꿔 끼우고 WildController 의 판단만 본다.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-auto-throw-")

from poketdesktop import ball_menu, config, wild_ui        # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Root(object):
    def __init__(self):
        self.jobs = []

    def after(self, ms, fn):
        self.jobs.append((ms, fn))
        return len(self.jobs)

    def after_cancel(self, job):
        if 0 < job <= len(self.jobs):
            self.jobs[job - 1] = (None, None)

    def run(self):
        """걸린 일을 하나씩 (이어 던지기는 한 번에 하나만 걸린다)."""
        n = 0
        while self.jobs:
            ms, fn = self.jobs.pop(0)
            if fn is not None:
                fn()
                n += 1
        return n


class Api(object):
    def __init__(self, answers):
        self.answers = list(answers)
        self.thrown = []

    def wild_catch(self, wid, ball):
        self.thrown.append(ball)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


class App(object):
    def __init__(self, answers, balls=10, auto=True):
        self.root = Root()
        self.api = Api(answers)
        self.settings = dict(config.DEFAULTS, autoThrow=auto)
        self.balls = balls
        self.battle = None
        self.notes = []
        self.box_window = None
        self.overlay = type("O", (), {"area": lambda _s: (0, 0, 800, 600)})()
        self.float_at = lambda *a, **k: None
        self.got_tm = lambda: None
        self.float_over_pet = lambda *a, **k: None

    def notify(self, text):
        self.notes.append(text)

    def refresh_tray(self):
        pass

    def request_sync(self):
        pass


def ctl(app, options):
    w = wild_ui.WildController.__new__(wild_ui.WildController)
    w.app = app
    w.ball_options = options
    w.pet = type("P", (), {"x": 100, "y": 100, "fw": 40, "fh": 40})()
    w.wild_id = 7
    w.throwing = False
    w.auto_ball, w.auto_n, w._auto_job = None, 0, None
    w.hide_hint = lambda: None
    w.set_ball_options = lambda opts: setattr(w, "ball_options", opts or w.ball_options)
    w.show_wild_sprite = lambda: None
    w.check = lambda *a, **k: None
    w.cleared = 0

    def clear():
        w.cleared += 1
        w.stop_auto()
        w.pet, w.wild_id = None, None
    w.clear = clear
    return w


def miss(balls, great=5):
    return {"caught": False, "shakes": 1, "balls": balls, "ball": "GREATBALL", "message": "놓쳤다!",
            "ballOptions": [{"id": "POKEBALL", "count": balls}, {"id": "GREATBALL", "count": great},
                            {"id": "MASTERBALL", "count": 1}]}


def caught(balls, great=5):
    return {"caught": True, "shakes": 4, "balls": balls, "ball": "GREATBALL", "message": "잡았다!",
            "ballOptions": [{"id": "POKEBALL", "count": balls}, {"id": "GREATBALL", "count": great}],
            "pokemon": {"info": {"species": "구구"}}}


def main():
    real_async, real_ball = wild_ui.run_async, wild_ui.BallThrow
    wild_ui.run_async = lambda root, work, done: _sync(work, done)
    wild_ui.BallThrow = lambda ctl_, start, target, shakes, caught_, on_done, ball="POKEBALL": on_done()
    import poketdesktop.desktop_battle as DB
    real_news = DB.exp_news
    DB.exp_news = lambda app, exp: ([], [], None)
    try:
        run()
    finally:
        wild_ui.run_async, wild_ui.BallThrow, DB.exp_news = real_async, real_ball, real_news
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


def _sync(work, done):
    try:
        r = work()
    except Exception as e:                                  # noqa: BLE001
        return done(None, e)
    done(r, None)


OPTS = [{"id": "POKEBALL", "kr": "몬스터볼", "count": 10, "mult": 1.0},
        {"id": "GREATBALL", "kr": "슈퍼볼", "count": 5, "mult": 1.5, "best": True},
        {"id": "MASTERBALL", "kr": "마스터볼", "count": 1, "mult": 255}]


def run():
    print("=== 볼 메뉴 맨 위 줄")
    picked, toggled = [], []
    rows = ball_menu.rows(OPTS, picked.append, auto=False, on_auto=lambda: toggled.append(1))
    chk("배틀 밖: 맨 위에 '☐ 잡힐 때까지 계속 던지기' 와 구분선", rows[0]["text"] == "☐ 잡힐 때까지 계속 던지기"
        and rows[1] is None, rows[:2])
    rows[0]["command"]()
    chk("  누르면 켜고 끄는 일만 (던지지 않는다)", toggled == [1] and picked == [])
    chk("  켜져 있으면 ☑", ball_menu.rows(OPTS, picked.append, auto=True, on_auto=lambda: 0)[0]["text"].startswith("☑"))
    chk("배틀 안(auto 를 안 넘김)에는 그 줄이 없다", "잡힐 때까지" not in str(ball_menu.rows(OPTS, picked.append)))
    lim = []
    rows = ball_menu.rows(OPTS, picked.append, auto=True, on_auto=lambda: 0, limit=10, on_limit=lambda: lim.append(1))
    chk("'최대 N개까지' 줄이 계속 던지기 줄 바로 아래 (2.2.1, #460)", rows[1]["text"].strip().startswith("최대 10개까지")
        and "20개" in rows[1]["text"] and rows[2] is None, rows[:3])
    rows[1]["command"]()
    chk("  누르면 바꾸는 일만 (던지지 않는다)", lim == [1] and picked == [])
    chk("  limit 을 안 넘기면 그 줄이 없다", "최대" not in str(ball_menu.rows(OPTS, picked.append, auto=True,
                                                                     on_auto=lambda: 0)))
    chk("최대 개수: 기본 30 · 고를 수 있는 값만 · 5 -> 10 -> 20 -> 30 -> 5",
        ball_menu.auto_max({}) == 30 and ball_menu.auto_max({"autoThrowMax": 7}) == 30
        and ball_menu.auto_max({"autoThrowMax": "10"}) == 10
        and [ball_menu.next_auto_max(n) for n in (5, 10, 20, 30)] == [10, 20, 30, 5])

    print("\n=== 켜고 끄기")
    app = App([], auto=False)
    w = ctl(app, OPTS)
    w.toggle_auto()
    chk("켜면 설정에 적고 저장한다", app.settings["autoThrow"] is True
        and config.load_settings().get("autoThrow") is True, app.settings.get("autoThrow"))
    w.toggle_auto()
    chk("다시 누르면 끈다", app.settings["autoThrow"] is False and "껐습니다" in app.notes[-1], app.notes[-1:])

    print("\n=== 놓치면 같은 볼로 이어 던지고, 잡히면 멈춘다")
    app = App([miss(10, 4), miss(10, 3), caught(10, 2)])
    w = ctl(app, OPTS)
    w.throw_ball("GREATBALL")
    n = app.root.run()
    chk("슈퍼볼로 세 번 던져 잡혔다", app.api.thrown == ["GREATBALL"] * 3 and n == 2, (app.api.thrown, n))
    chk("  놓칠 때마다 몇 번째인지 알린다", any("계속 던지는 중 (2번째)" in t for t in app.notes)
        and any("(3번째)" in t for t in app.notes), app.notes)
    chk("  잡히면 이어 던지기가 꺼지고 야생을 치운다", w.auto_ball is None and w.cleared == 1 and not app.root.jobs)

    print("\n=== 멈추는 때")
    app = App([miss(10, 1), miss(10, 0)])
    w = ctl(app, [dict(o, count=2) if o["id"] == "GREATBALL" else o for o in OPTS])
    w.throw_ball("GREATBALL")
    app.root.run()
    chk("그 볼이 떨어지면 멈추고 까닭을 적는다", app.api.thrown == ["GREATBALL", "GREATBALL"] and w.auto_ball is None
        and "볼이 떨어져" in app.notes[-1], (app.api.thrown, app.notes[-1:]))

    app = App([miss(10)] * 3)
    w = ctl(app, OPTS)
    w.throw_ball("MASTERBALL")
    chk("마스터볼은 이어 던지지 않는다", app.api.thrown == ["MASTERBALL"] and w.auto_ball is None
        and not app.root.jobs, app.api.thrown)

    app = App([miss(10)] * 3, auto=False)
    w = ctl(app, OPTS)
    w.throw_ball("GREATBALL")
    chk("설정이 꺼져 있으면 한 번만", app.api.thrown == ["GREATBALL"] and not app.root.jobs)

    app = App([miss(10)])
    w = ctl(app, OPTS)
    w.throw_ball("GREATBALL")
    w.start_battle = wild_ui.WildController.start_battle.__get__(w)
    w.throwing = True                                       # (배틀 여는 길은 서버를 부르니 막아 둔다)
    w.start_battle()
    chk("배틀을 시작하면 멈춘다 (걸어 둔 다음 던지기를 지운다)", w.auto_ball is None and app.root.run() == 0)

    app = App([miss(10)])
    w = ctl(app, OPTS)
    w.throw_ball("GREATBALL")
    w.clear()
    chk("야생이 사라지면(clear) 멈춘다", w.auto_ball is None and app.root.run() == 0)

    app = App([miss(10), miss(10)])
    w = ctl(app, OPTS)
    w.throw_ball("GREATBALL")
    import poketdesktop.ball_menu as BM
    real_popup = BM.popup
    seen = {}
    BM.popup = lambda root, e, opts, on_pick, on_close=None, auto=None, on_auto=None, **kw: seen.update(auto=auto, **kw)
    try:
        w.throwing = True                                   # 볼이 날아가는 중 (이어 던지는 동안 거의 늘 이렇다)
        w.ball_menu(None)
        chk("이어 던지는 동안 오른쪽 클릭(메뉴)은 멈추기 - 볼이 날아가는 중에도", w.auto_ball is None
            and "멈췄습니다" in app.notes[-1] and not seen and app.root.run() == 0, (app.notes[-1:], seen))
        chk("  놓쳤을 때 글에 멈추는 법을 적는다", any("오른쪽 클릭" in t for t in app.notes), app.notes)
        w.throwing = False
        w.ball_menu(None)
        chk("  멈춘 뒤 다시 열면 메뉴가 뜨고 지금 설정을 넘긴다", seen.get("auto") is True, seen)
        chk("  '최대 N개까지' 줄도 넘긴다 (지금 값 · 바꾸는 일)", seen.get("limit") == w.AUTO_MAX
            and seen.get("on_limit") == w.cycle_auto_max, seen)
    finally:
        BM.popup = real_popup

    app = App([miss(10), miss(10), miss(10)])
    w = ctl(app, OPTS)
    w.throw_ball("GREATBALL")
    app.settings["autoThrow"] = False                       # 설정 초기화 등으로 그사이 꺼졌다
    app.root.run()
    chk("그사이 설정이 꺼지면 다음 볼을 던지지 않는다", app.api.thrown == ["GREATBALL"]
        and w.auto_ball is None, app.api.thrown)

    app = App([miss(10, 50)] * 40)
    w = ctl(app, [dict(o, count=50) if o["id"] == "GREATBALL" else o for o in OPTS])
    w.throw_ball("GREATBALL")
    app.root.run()
    chk("%d번에서 멈춘다" % w.AUTO_MAX, len(app.api.thrown) == w.AUTO_MAX and "멈췄습니다" in app.notes[-1],
        (len(app.api.thrown), app.notes[-1:]))

    app = App([miss(10, 50)] * 40)
    app.settings["autoThrowMax"] = 10
    w = ctl(app, [dict(o, count=50) if o["id"] == "GREATBALL" else o for o in OPTS])
    w.throw_ball("GREATBALL")
    app.root.run()
    chk("최대 10개로 골라 두면 10번에서 멈춘다 (2.2.1, #460)", len(app.api.thrown) == 10 and "10번 던져" in app.notes[-1],
        (len(app.api.thrown), app.notes[-1:]))
    w.cycle_auto_max()
    chk("  메뉴 줄을 누르면 다음 값(20)으로 바꾸고 저장 · 알린다", app.settings["autoThrowMax"] == 20
        and config.load_settings().get("autoThrowMax") == 20 and "최대 20개" in app.notes[-1],
        (app.settings.get("autoThrowMax"), app.notes[-1:]))

    class Gone(Exception):
        message = "야생 포켓몬이 이미 사라졌습니다."
    app = App([miss(10), Gone()])
    w = ctl(app, OPTS)
    w.throw_ball("GREATBALL")
    app.root.run()
    chk("서버가 거절하면(사라짐) 멈춘다", w.auto_ball is None and "사라졌습니다" in app.notes[-1]
        and len(app.api.thrown) == 2, app.notes[-1:])


if __name__ == "__main__":
    sys.exit(main())
