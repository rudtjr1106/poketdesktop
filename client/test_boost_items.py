# -*- coding: utf-8 -*-
"""타입 스프레이 · 닉네임 변경권 가방 화면 검사 (2.1.1).

    python client/test_boost_items.py
    python client/run_as_windows.py client/test_boost_items.py

**창을 진짜로 띄운다.** 못 박는 것:

  1. 타입 스프레이: 포켓몬을 안 고르고, 쓰기 전에 타입을 묻는다 (스텔라 빼고 열여덟). 켜져 있는 타입에는 남은 시간,
     설명 끝에는 '지금 켜져 있다'. 창을 닫으면 안 쓴다. 풀숲 간격은 그대로라 풀숲 확인을 다시 걸지 않는다.
  2. 스프레이가 거절되면(3시간까지만 쌓인다) 서버 말을 보여 준다. (버닝 부스터는 만들었다가 11/04 에 뺐다)
  3. 닉네임 변경권: 새 닉네임을 묻고 한 번 더 확인한 뒤 쓴다. 바뀌면 앱 · 자동 로그인 세션의 이름도 바뀐다.
     취소 · 같은 이름 · 확인 거절이면 안 쓰고, 서버가 거절하면 이름은 그대로다.
  4. 상점 설명이 '아직 쓸 수 없는 물건' 이 아니다.
"""
import json
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-boostitems-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import config                             # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import sprite_cache                       # noqa: E402
from poketdesktop import ui_bag, ui_box, ui_shop            # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
import smoke_box_filter as SB                               # noqa: E402
import test_big_lists as BL                                 # noqa: E402

OK = FAIL = 0
DATA = os.path.join(ROOT, "server", "data")
IDS = ("TYPESPRAY", "RENAMETICKET")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Api(BL.Api):
    def __init__(self, mons, items, boosts):
        BL.Api.__init__(self, mons, items)
        self.boosts = boosts
        self.uses = []
        self.refuse = None

    def shop(self):
        out = BL.Api.shop(self)
        if self.boosts is not None:
            out["boosts"] = dict(self.boosts)
        return out

    def use_item(self, item, pid, stat="", hour=None, form="", tm_type="", name=""):
        self.uses.append((item, pid, tm_type, name))
        if self.refuse:
            from poketdesktop.api import ApiError
            raise ApiError(self.refuse, 409)
        self.bag[item] = self.bag.get(item, 0) - 1
        if item == "RENAMETICKET":
            return {"ok": True, "won": True, "username": name,
                    "message": "닉네임이 '%s' 이(가) 되었습니다." % name}
        return {"ok": True, "won": True, "message": "앞으로 1시간 동안 켜진다!"}


class Wild(object):
    def __init__(self):
        self.checks = 0

    def check(self, force=False):
        self.checks += 1


class App(BL.App):
    def __init__(self, root, api, dex):
        BL.App.__init__(self, root, api, dex)
        self.username = "옛이름"
        self.wild = Wild()
        self.trays = 0

    def refresh_tray(self):
        self.trays += 1


def bag(root, dex, boosts):
    raw = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))["items"]
    items = [dict(i) for i in (raw.values() if isinstance(raw, dict) else raw) if i["id"] in IDS]
    mons = [SB.mon(dex, 25, 1)]
    api = Api(mons, items, boosts)
    app = App(root, api, dex)
    w = ui_bag.BagWindow(root, app)
    top = w.win.winfo_toplevel()
    top.geometry("1000x664+40+40")
    top.deiconify()
    BL.wait(root, lambda: w.mons and w._wait is None)
    return w, api, app


def status(w):
    return w.status._label.cget("text")


def run_spray(root, dex):
    print("=== 타입 스프레이")
    w, api, app = bag(root, dex, {"lureLeft": 1500, "lureType": "FIRE"})
    w.pick_item("TYPESPRAY")
    BL.settle(root, 0.3)
    note = w.mon_note.cget("text")
    chk("포켓몬 목록 대신 설명이 뜬다", not w._mon_list_on and "고른 타입" in note, note)
    chk("  설명 끝에 지금 켜진 타입과 남은 시간", "지금 켜져 있다: 불꽃 타입 · 25분 남음" in note, note)
    chk("  쓰기 단추가 켜져 있다", w.use_btn.enabled, w.use_btn.label.cget("text"))

    asked = []
    real = ui_box.ask_choice

    def fake(parent, title, message, options, answer="WATER"):
        asked.append((title, message, list(options)))
        return answer
    ui_box.ask_choice = fake
    try:
        w.do_use()
        BL.wait(root, lambda: api.uses and w._wait is None)
        BL.settle(root, 0.3)
        opts = asked[-1][2] if asked else []
        chk("쓰기 전에 타입을 묻는다 (스텔라 빼고 열여덟)", len(opts) == 18
            and "STELLAR" not in [k for k, _l, _s in opts], len(opts))
        chk("  켜진 타입에만 남은 시간", [(k, s) for k, _l, s in opts if s] == [("FIRE", "켜져 있음 · 25분 남음")],
            [(k, s) for k, _l, s in opts if s])
        chk("  다른 타입을 고르면 남은 시간이 사라진다고 미리 말한다", asked and "남은 시간은 사라지고" in asked[-1][1],
            asked[-1][1] if asked else "")
        chk("고른 타입으로, 포켓몬 없이 쓴다", api.uses == [("TYPESPRAY", 0, "WATER", "")], api.uses)
        chk("  풀숲 간격은 그대로라 풀숲 확인을 다시 걸지 않는다", app.wild.checks == 0, app.wild.checks)
        chk("  서버 말을 보여 준다", "1시간 동안" in status(w), status(w))

        ui_box.ask_choice = lambda *a, **k: None
        w.pick_item("TYPESPRAY")
        w.do_use()
        BL.settle(root, 0.2)
        chk("창을 닫으면 안 쓴다", len(api.uses) == 1, api.uses)
    finally:
        ui_box.ask_choice = real
    w.close()

    w, api, app = bag(root, dex, None)
    w.pick_item("TYPESPRAY")
    BL.settle(root, 0.2)
    chk("옛 서버(부스트 정보 없음)면 '지금 켜져 있다' 를 안 적는다", "지금 켜져" not in w.mon_note.cget("text"),
        w.mon_note.cget("text"))
    w.close()


def run_refuse(root, dex):
    print("\n=== 스프레이가 거절될 때")
    w, api, app = bag(root, dex, {"lureLeft": 10200, "lureType": "FIRE"})
    api.refuse = "이미 2시간 50분 남아 있습니다 (3시간까지만 쌓입니다)."
    real = ui_box.ask_choice
    ui_box.ask_choice = lambda *a, **k: "FIRE"
    try:
        w.pick_item("TYPESPRAY")
        w.do_use()
        BL.wait(root, lambda: api.uses and w._wait is None)
        BL.settle(root, 0.3)
    finally:
        ui_box.ask_choice = real
    chk("거절되면 서버 말을 보여 준다", "3시간까지만" in status(w), status(w))
    chk("  쓰기 단추가 다시 켜진다", w.use_btn.enabled, w.use_btn.label.cget("text"))
    w.close()


def run_rename(root, dex):
    print("\n=== 닉네임 변경권")
    config.save_session({"token": "tok", "username": "옛이름", "expiresAt": None})
    w, api, app = bag(root, dex, {})
    w.pick_item("RENAMETICKET")
    BL.settle(root, 0.3)
    note = w.mon_note.cget("text")
    chk("설명: 로그인 아이디가 바뀐다 · 운영자는 못 쓴다", "로그인 아이디" in note and "운영자" in note, note)

    real_text, real_ok = ui_box.ask_text, ui_box.confirm
    said = {}

    def ask(parent, title, message, hint="", initial=""):
        said["initial"] = initial
        return said.get("answer")

    def confirm(parent, title, message, danger=True, ok_text="확인"):
        said["confirm"] = message
        return said.get("ok", True)
    ui_box.ask_text, ui_box.confirm = ask, confirm
    try:
        for answer, ok, why in ((None, True, "창을 닫으면"), ("옛이름", True, "지금과 같은 이름이면"),
                                ("새이름", False, "확인에서 그만두면")):
            said.update(answer=answer, ok=ok)
            w.pick_item("RENAMETICKET")
            w.do_use()
            BL.settle(root, 0.2)
            chk("%s 안 쓴다" % why, not api.uses and app.username == "옛이름", api.uses)
        chk("  입력 칸에는 지금 닉네임이 채워져 있다", said.get("initial") == "옛이름", said.get("initial"))

        said.update(answer="  새   이름 ", ok=True)
        api.refuse = "이미 쓰는 닉네임입니다."
        w.do_use()
        BL.wait(root, lambda: api.uses and w._wait is None)
        BL.settle(root, 0.3)
        chk("겹친 공백을 하나로 줄여 보낸다", api.uses == [("RENAMETICKET", 0, "", "새 이름")], api.uses)
        chk("서버가 거절하면 이유를 보여 주고 이름은 그대로", "이미 쓰는" in status(w) and app.username == "옛이름"
            and config.load_session().get("username") == "옛이름", (status(w), app.username))

        api.refuse = None
        w.do_use()
        BL.wait(root, lambda: len(api.uses) == 2 and w._wait is None)
        BL.settle(root, 0.3)
        chk("바뀌면 확인 창이 새 이름을 말했고", "새 이름" in said.get("confirm", ""), said.get("confirm"))
        chk("  앱 · 트레이 · 자동 로그인 세션의 이름이 바뀐다", app.username == "새 이름" and app.trays == 1
            and config.load_session().get("username") == "새 이름"
            and config.load_session().get("token") == "tok", (app.username, config.load_session()))
        chk("  서버 말을 보여 준다", "새 이름" in status(w), status(w))
    finally:
        ui_box.ask_text, ui_box.confirm = real_text, real_ok
    w.close()


def run_shop():
    print("\n=== 상점 설명")
    raw = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))["items"]
    items = dict((i["id"], i) for i in (raw.values() if isinstance(raw, dict) else raw) if i["id"] in IDS)
    for iid in IDS:
        it = items[iid]
        text, note = ui_shop.effect_text(it), ui_shop.effect_note(it)
        chk("%s: 효과 글과 덧말이 있다" % it["kr"], text and "아직 쓸 수 없는" not in text and note, (text, note))
    chk("가방 설명도 '아직 쓸 수 없는 도구' 가 아니다", all("아직 쓸 수 없는" not in ui_bag.item_desc(items[i])
                                                    for i in IDS))
    chk("남은 시간 글: 59초=1분 · 60분=1시간 · 61분=1시간 1분",
        [ui_bag.left_kr(s) for s in (59, 3600, 3660)] == ["1분", "1시간", "1시간 1분"])


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-600:])
    root.report_callback_exception = on_err
    real = sprite_cache.ensure
    sprite_cache.ensure = lambda api, num, shiny=False: None
    try:
        run_spray(root, dex)
        run_refuse(root, dex)
        run_rename(root, dex)
        run_shop()
    finally:
        sprite_cache.ensure = real
    chk("콜백 예외가 없다", not errors, errors[:2])
    try:
        root.destroy()
    except tk.TclError:
        pass
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
