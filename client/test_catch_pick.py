# -*- coding: utf-8 -*-
"""잡기 모드 '고른 포켓몬만' (catchMode pick) - 판단과 서버에 보내는 값.

    python client/test_catch_pick.py

창을 안 만든다. 고르는 창은 test_catch_pick_ui.py 가 진짜 Tk 로 본다.

  1. 고른 종이면 always, 아니면 off 로 바꿔 보낸다 (서버는 pick 을 모른다 - 옛 서버도 그대로 알아듣는다).
  2. **색이 다른 포켓몬은 고르지 않았어도 멈춘다** (always).
  3. 폼·메가는 원래 종으로 맞춘다 (로토무 히트 -> 로토무). 도감이 없어도 맞춘다.
  4. 설정 값이 이상해도 깨지지 않는다 (모드는 기본 new, 목록은 빈 것).
  5. 다른 모드(new/always/off)는 예전 그대로 보낸다.
  6. 배틀이 턴마다 이 판단으로 보낸다 (desktop_battle.next_turn), 판이 끝나 볼이 안 나간 글.
  7. 목록 거르기 (찾기·고른 것만), '기본값으로' 가 고른 종을 지우지 않는다.
"""
import json
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-catchpick-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from common import pokelogic as P                           # noqa: E402
from poketdesktop import config                             # noqa: E402
from poketdesktop import desktop_battle as DB               # noqa: E402
from poketdesktop import ui_catch_pick as CP                # noqa: E402
from poketdesktop import ui_settings                        # noqa: E402

OK = FAIL = 0
DEX = P.Pokedex.load(os.path.join(ROOT, "server", "data", "pokedex.json"))


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def pick(*names):
    return {"catchMode": "pick", "catchPick": list(names)}


def t_고른_종만_멈춘다():
    s = pick("PIKACHU", "EEVEE")
    chk("고른 종 -> always", config.catch_for(s, {"species": "PIKACHU"}, DEX) == "always")
    chk("안 고른 종 -> off", config.catch_for(s, {"species": "RATTATA"}, DEX) == "off")
    chk("소문자로 적어 둬도 맞춘다", config.catch_for(pick("pikachu"), {"species": "PIKACHU"}) == "always")
    chk("아무것도 안 골랐으면 늘 off", config.catch_for(pick(), {"species": "PIKACHU"}, DEX) == "off")


def t_이로치는_늘_멈춘다():
    s = pick("PIKACHU")
    chk("안 고른 종이어도 색이 다르면 always",
        config.catch_for(s, {"species": "RATTATA", "shiny": True}, DEX) == "always")
    chk("아무것도 안 골랐어도 색이 다르면 always",
        config.catch_for(pick(), {"species": "RATTATA", "shiny": True}) == "always")
    chk("종을 몰라도 색이 다르면 always", config.catch_for(s, {"shiny": True}) == "always")


def t_폼은_원래_종으로():
    s = pick("ROTOM", "CHARIZARD")
    chk("로토무 히트 -> 로토무", config.base_species("ROTOM_HEAT", DEX) == "ROTOM")
    chk("메가 -> 원래 종", config.base_species("CHARIZARD_MEGA_X", DEX) == "CHARIZARD")
    chk("원래 종은 그대로", config.base_species("PIKACHU", DEX) == "PIKACHU")
    chk("폼 야생도 멈춘다", config.catch_for(s, {"species": "ROTOM_WASH"}, DEX) == "always")
    chk("도감이 없어도 밑줄 앞으로 맞춘다", config.catch_for(s, {"species": "ROTOM_WASH"}, None) == "always")
    chk("폼만 골라 둬도(옛 자료) 그 폼은 멈춘다",
        config.catch_for(pick("ROTOM_WASH"), {"species": "ROTOM_WASH"}, DEX) == "always")
    # 도감 1025종 이름에 밑줄이 없어야 '밑줄 앞' 이 맞는다 (도감 없을 때의 길)
    chk("도감 종 이름에 밑줄이 없다", not [s["internal"] for s in DEX.species if "_" in s["internal"]])
    chk("폼 자료는 다 '원래종_' 으로 시작한다",
        all(f["internal"].startswith(f["formOf"] + "_") for f in DEX.forms)
        and all(m["internal"].startswith(m["megaOf"] + "_") for m in DEX.megas))


def t_이상한_설정():
    chk("모르는 모드는 new", config.catch_mode({"catchMode": "pickk"}) == "new")
    chk("pick 은 아는 모드다", config.catch_mode({"catchMode": "pick"}) == "pick")
    for bad in (None, "PIKACHU", 3, {"PIKACHU": 1}, [None, 3, "", " "]):
        chk("목록이 %r 이면 빈 것" % (bad,), config.catch_pick({"catchPick": bad}) == frozenset())
    chk("섞여 있으면 글만 남긴다", config.catch_pick({"catchPick": ["PIKACHU", 3, None]}) == {"PIKACHU"})
    chk("목록이 이상해도 off", config.catch_for({"catchMode": "pick", "catchPick": "PIKACHU"},
                                            {"species": "PIKACHU"}) == "off")
    chk("야생 자료가 없으면 off", config.catch_for(pick("PIKACHU"), None) == "off"
        and config.catch_for(pick("PIKACHU"), {"species": None}) == "off")
    chk("설정이 None 이어도 new", config.catch_for(None, {"species": "PIKACHU"}) == "new")


def t_다른_모드는_그대로():
    for mode in ("new", "always", "off"):
        s = {"catchMode": mode, "catchPick": ["RATTATA"]}
        chk("%s 는 그대로 보낸다" % mode, config.catch_for(s, {"species": "PIKACHU", "shiny": True}, DEX) == mode)


def t_기본값():
    path = os.path.join(os.environ["POKET_HOME"], "settings.json")
    if os.path.exists(path):
        os.remove(path)
    s = config.load_settings()
    chk("기본 목록은 비어 있다", s["catchPick"] == [])
    chk("CATCH_CHOICES 에 '고른 포켓몬만'",
        ("pick", "고른 포켓몬만") in ui_settings.SettingsWindow.CATCH_CHOICES)


# ---------------------------------------------------------------- 배틀이 보내는 값
class 서버(object):
    def __init__(self):
        self.moves = []

    def battle_move(self, bid, move, catch="", finish=False):
        self.moves.append(catch)
        return {"events": [], "battle": {"id": bid, "over": False}}


class 앱(object):
    def __init__(self, settings):
        self.api = 서버()
        self.settings = settings
        self.dex = DEX
        self.말 = []

    def notify(self, m):
        self.말.append(m)


class 판(object):
    def __init__(self, settings, foe):
        self.app = 앱(settings)
        self.root = None
        self.b = {"id": 7, "over": False, "foe": foe}
        self.closed = self.busy = self.playing = self.menu_open = self.holding = self.finish = False
        self.pending_ball = None

    next_turn = DB.DesktopBattle.next_turn
    _late_ball = DB.DesktopBattle._late_ball

    def play(self, events, r):
        pass

    def _safe(self, fn, *a):
        fn(*a)


def t_배틀이_턴마다_보낸다():
    real = DB.run_async
    DB.run_async = lambda root, fn, cb: cb(fn(), None)
    try:
        for foe, want in (({"species": "PIKACHU"}, "always"), ({"species": "RATTATA"}, "off"),
                          ({"species": "RATTATA", "shiny": True}, "always"),
                          ({"species": "ROTOM_FAN"}, "always")):
            d = 판(pick("PIKACHU", "ROTOM"), foe)
            d.next_turn()
            chk("야생 %s -> 서버에 %s" % (foe, want), d.app.api.moves == [want], d.app.api.moves)
        d = 판({"catchMode": "new"}, {"species": "PIKACHU"})
        d.next_turn()
        chk("new 모드는 예전처럼 new", d.app.api.moves == ["new"], d.app.api.moves)
        # 안내 글은 그 판에 실제로 off 를 보냈을 때만 붙는다
        for foe, want_note in (({"species": "RATTATA"}, True), ({"species": "PIKACHU"}, False),
                               ({"species": "RATTATA", "shiny": True}, False)):
            d = 판(pick("PIKACHU"), foe)
            d.next_turn()
            d._late_ball("판이 끝났다")
            got = bool(d.app.말) and "고르지 않은 포켓몬" in d.app.말[0]
            chk("%s: 볼이 안 나갔을 때 '고를 수 있다' 안내 %s" % (foe, "있음" if want_note else "없음"),
                got == want_note, (d.app.말, d.app.api.moves))
        d = 판(pick("PIKACHU"), {"species": "RATTATA"})
        d._late_ball("판이 끝났다")          # 한 번도 안 보냈다 (첫 턴 전)
        chk("아직 아무것도 안 보냈으면 안내를 안 붙인다", d.app.말 and "고르지 않은 포켓몬" not in d.app.말[0], d.app.말)
    finally:
        DB.run_async = real


# ---------------------------------------------------------------- 목록·기본값으로
def t_목록_거르기():
    sp = DEX.species
    chk("다 보인다", len(CP.rows_for(sp, set())) == 1025)
    got = CP.rows_for(sp, set(), "피카")
    chk("한글로 찾는다", [s["internal"] for s in got] == ["PIKACHU"], [s["internal"] for s in got])
    chk("번호로 찾는다", [s["num"] for s in CP.rows_for(sp, set(), "0025")] == [25])
    picked = {"PIKACHU", "EEVEE", "NOT_A_MON"}
    only = CP.rows_for(sp, picked, "", True)
    chk("고른 것만 (도감 순서, 없는 이름은 안 보인다)",
        [s["internal"] for s in only] == ["PIKACHU", "EEVEE"], [s["internal"] for s in only])
    chk("고른 것 + 찾기", [s["internal"] for s in CP.rows_for(sp, picked, "이브", True)] == ["EEVEE"])


class 설정창앱(object):
    def __init__(self):
        self.settings = config.load_settings()
        self.overlay = None
        self.wild = None

    def set_size(self, px):
        pass

    def refresh_tray(self):
        pass


def t_기본값으로_해도_고른_것은_남는다():
    app = 설정창앱()
    app.settings.update({"catchMode": "pick", "catchPick": ["PIKACHU"], "walkSpeed": 2.5})

    class 창(object):
        reset = ui_settings.SettingsWindow.reset
        _save = ui_settings.SettingsWindow._save
        _repaint_pick_window = ui_settings.SettingsWindow._repaint_pick_window

        def _paint_catch_pick(self):
            self.painted = True

        def _paint_area(self):
            pass

    w = 창()
    w.app = app
    w.status = None
    w.boss = None
    real = ui_settings.U.set_status
    ui_settings.U.set_status = lambda *a, **k: None
    try:
        w.reset()
    finally:
        ui_settings.U.set_status = real
    chk("모드는 기본으로", app.settings["catchMode"] == "new")
    chk("기본값으로 하면 설정 창의 '고른 N종' 도 다시 칠한다", getattr(w, "painted", False))
    chk("고른 종은 그대로", app.settings["catchPick"] == ["PIKACHU"], app.settings["catchPick"])
    with open(config.SETTINGS_PATH, encoding="utf-8") as f:
        chk("파일에도 남는다", json.load(f).get("catchPick") == ["PIKACHU"])
    chk("기본값 리스트는 그대로 비어 있다", config.DEFAULTS["catchPick"] == [])


def main():
    for fn in (t_고른_종만_멈춘다, t_이로치는_늘_멈춘다, t_폼은_원래_종으로, t_이상한_설정, t_다른_모드는_그대로,
               t_기본값, t_배틀이_턴마다_보낸다, t_목록_거르기, t_기본값으로_해도_고른_것은_남는다):
        print("-- %s" % fn.__name__[2:])
        fn()
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
