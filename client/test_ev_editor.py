# -*- coding: utf-8 -*-
"""노력치 조정 창 검사 (2.1.3, 게시판 #450) - 기본 테마, 그다음 DP 계열 테마 여섯을 하나씩 따로 띄워 같이 본다.

    python client/test_ev_editor.py

**창을 진짜로 띄운다.** 못 박는 것:

  1. 열면 지금 노력치가 줄마다(지금 N · 막대 · 칸) 보이고 합계가 맞다. 바꾼 것이 없으면 서버에 안 묻고 '적용' 은 잠김.
     창은 내용만큼 (안쪽이 눌리거나 잘리지 않는다).
  2. 막대를 끌면 칸 · 차이 · 합계가 따라오고, 잠깐 멈추면 서버에 계획을 **한 번** 묻는다 (dry). 계획 글에 가방에서
     쓸 것 · 사서 쓸 것 · 값.
  3. 합계 510 은 못 넘는다: 막대는 넘는 만큼 멈추고, 칸에 적어 넘기면 빨갛게 알리고 '적용' 을 잠그고 묻지 않는다.
     0~252 가 아닌 글도 마찬가지. 되돌리기는 지금 값으로.
  4. 모자란 도구가 있으면 '부족한 도구 N개를 X원에 사서 쓸까요?' 를 묻는다 - 아니오면 아무것도 안 보내고,
     예면 buy · 물어본 값(cost)을 같이 보낸다. 다 가진 것이면 묻지 않는다. 결과로 '지금' 이 바뀌고 박스에 알린다.
     서버가 거절하면 그 말을 빨갛게.
  5. 포켓몬 관리 창의 능력치 머리에 '노력치 조정' 단추 - 누르면 고른 포켓몬의 창이 뜬다.
  6. 테마(DP 와 그것을 이어 쓰는 다섯): 요약의 '능력' 쪽 노력치 줄 아래 '노력치 조정 ›' 을 누르면 같은 창이 뜬다.
     DP 에서는 창 검사(1~4)도 한 번 더 돈다 - 테마의 위젯 빛깔에서도 창이 돈다.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-evs-")
SKIN = os.environ.get("POKET_EVED_SKIN", "default")
os.environ["POKET_SKIN"] = SKIN

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins, ui_box, ui_evs              # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

import smoke_box_filter as SB                               # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402

OK = FAIL = 0
STATS = [k for k, _l in ui_box.STAT_ROWS]


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def tone(c):
    """테마에서 보이는 글자 빛깔 - DP 는 기본 화면이 만든 위젯의 빛깔을 옮긴다 (skins/dp/widgets.py)."""
    if SKIN == "default":
        return c
    from poketdesktop.skins.dp import widgets as W
    return W.FG_MAP.get(c, c)


def wait(root, cond, sec=6.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.005)
    return cond()


def settle(root, sec=0.2):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.005)


class Refused(Exception):
    def __init__(self, message, status=409):
        Exception.__init__(self, message)
        self.message, self.status = message, status


class EvApi(object):
    """서버 /api/pokemon/{pid}/evs 흉내. 계획은 능력마다 한 줄(차이만큼 개수), 가방에 있으면 먼저, 하나 100원."""

    def __init__(self, evs, bag=None, money=50000):
        self.evs = dict(evs)
        self.bag = dict(bag or {})
        self.money = money
        self.calls = []
        self.fail = None

    def set_evs(self, pid, evs, buy=False, dry=True, cost=None):
        self.calls.append({"pid": pid, "evs": dict(evs), "buy": buy, "dry": dry, "cost": cost})
        time.sleep(0.01)
        plan = []
        for k in STATS:
            d = int(evs.get(k, 0)) - int(self.evs.get(k, 0))
            if d:
                n = abs(d)
                own = min(n, self.bag.get(k, 0))
                plan.append({"item": "EV_" + k, "kr": "%s약" % k, "stat": k, "amount": 1 if d > 0 else -1,
                             "count": n, "owned": own, "buy": n - own, "price": 100})
        cost = sum(x["buy"] * 100 for x in plan)
        out = {"ok": True, "dry": dry, "evs": dict(evs), "plan": plan, "count": sum(x["count"] for x in plan),
               "owned": sum(x["owned"] for x in plan), "buyCount": sum(x["buy"] for x in plan), "cost": cost,
               "buyable": True, "affordable": self.money >= cost, "money": self.money}
        if dry:
            return out
        if self.fail:
            raise Refused(self.fail)
        self.evs = dict(evs)
        self.money -= cost
        out.update(money=self.money, message="노력치를 맞췄다! 도구 %d개를 썼다." % out["count"],
                   pokemon={"id": pid, "info": {"evs": dict(evs)}})
        return out

    def __getattr__(self, name):
        raise AttributeError(name)


class App(object):
    def __init__(self, root, api):
        self.root, self.api = root, api
        self.box_window = None


def mon(evs):
    return {"id": 7, "species": "PIKACHU", "level": 50, "info": {"name": "피카츄", "evs": dict(evs)}}


def nondry(api):
    return [c for c in api.calls if not c["dry"]]


def editor(root):
    print("1. 열기")
    start = {"hp": 4, "atk": 252, "def": 0, "spa": 0, "spd": 0, "spe": 252}
    api = EvApi(start, bag={"atk": 500, "spe": 500})
    app = App(root, api)
    done = []
    ed = ui_evs.open_editor(app, root, mon(start), on_done=done.append)
    settle(root, 0.6)
    chk("줄마다 지금 값 · 막대 · 칸", all(ed.now_lb[k].cget("text") == "지금 %d" % start[k]
                                     and int(ed.scales[k].get()) == start[k] and ed.vars[k].get() == str(start[k])
                                     for k in STATS), [(ed.now_lb[k].cget("text"), ed.vars[k].get()) for k in STATS])
    chk("  합계 508 / 510", ed.total_lb.cget("text") == "합계 508 / 510", ed.total_lb.cget("text"))
    chk("  바꾼 것이 없으면 묻지 않고 '적용' 잠김", api.calls == [] and not ed.btn_apply.enabled
        and not ed.btn_reset.enabled, api.calls)
    win = ed.win
    chk("  창은 내용만큼 (안쪽이 다 보이고 빈칸이 없다)", ed.cv.winfo_height() >= ed.inner.winfo_reqheight()
        and win.winfo_height() <= win.winfo_reqheight() + 4, (ed.cv.winfo_height(), ed.inner.winfo_reqheight(),
                                                              win.winfo_height(), win.winfo_reqheight()))
    chk("  눌리거나 잘린 위젯이 없다 (가로 · 세로)", not squeezed(win) and not squeezed(ed.inner)
        and ed.inner.winfo_width() >= ed.inner.winfo_reqwidth(), (squeezed(win), squeezed(ed.inner)))

    print("2. 막대")
    for v in (200, 150, 100):                               # 끄는 동안 여러 번 바뀌어도
        ed.scales["atk"].set(v)
        root.update()
    settle(root, 0.05)
    chk("칸 · 차이 · 합계가 따라온다", ed.vars["atk"].get() == "100" and ed.diff_lb["atk"].cget("text") == "−152"
        and ed.total_lb.cget("text") == "합계 356 / 510", (ed.vars["atk"].get(), ed.diff_lb["atk"].cget("text"),
                                                         ed.total_lb.cget("text")))
    wait(root, lambda: api.calls and ed.plan is not None)
    settle(root, ui_evs.PLAN_MS / 1000.0 + 0.2)
    chk("  멈추면 계획을 한 번만 묻는다 (dry)", len(api.calls) == 1 and api.calls[0]["dry"]
        and api.calls[0]["evs"]["atk"] == 100 and api.calls[0]["pid"] == 7, api.calls)
    chk("  계획 글: 가방에서 쓸 것 · 가진 돈", "가방에서: atk약 152개" in ed.plan_lb.cget("text")
        and "살 것 없음" in ed.plan_lb.cget("text"), ed.plan_lb.cget("text"))
    chk("  '적용' 이 켜진다", ed.btn_apply.enabled)

    print("3. 합계 510")
    ed.scales["hp"].set(252)
    settle(root, 0.05)
    chk("막대는 510 에서 멈춘다 (HP 158)", ed.vars["hp"].get() == "158" and int(ed.scales["hp"].get()) == 158
        and ed.total_lb.cget("text") == "합계 510 / 510", (ed.vars["hp"].get(), ed.total_lb.cget("text")))
    wait(root, lambda: len(api.calls) == 2)
    n = len(api.calls)
    ed.vars["hp"].set("200")
    settle(root, ui_evs.PLAN_MS / 1000.0 + 0.3)
    chk("칸에 적어 넘기면 빨간 합계 · '적용' 잠김 · 묻지 않는다", "넘었습니다" in ed.total_lb.cget("text")
        and ed.total_lb.cget("fg") == tone(U.DANGER) and not ed.btn_apply.enabled and len(api.calls) == n
        and "510" in ed.plan_lb.cget("text"), (ed.total_lb.cget("text"), len(api.calls), n, ed.plan_lb.cget("text")))
    chk("  칸에 적은 값은 고치지 않는다 (막대만 따라간다)", ed.vars["hp"].get() == "200"
        and int(ed.scales["hp"].get()) == 200, ed.vars["hp"].get())
    for bad in ("abc", "300", ""):
        ed.vars["spa"].set(bad)
        settle(root, 0.05)
        chk("'%s' 은 0~252 가 아니다: 빨갛게 · 잠김" % bad, ed.diff_lb["spa"].cget("text") == "0~252"
            and not ed.btn_apply.enabled and "0~252" in ed.plan_lb.cget("text"), ed.plan_lb.cget("text"))
    ed.reset()
    settle(root, ui_evs.PLAN_MS / 1000.0 + 0.2)
    chk("되돌리기: 지금 값으로 · 묻지 않는다", ed.want == ed.cur and ed.vars["spa"].get() == "0"
        and ed.vars["hp"].get() == "4" and len(api.calls) == n and not ed.btn_apply.enabled, ed.want)

    print("4. 적용")
    asked = []
    real = ui_box.confirm
    answer = [False]

    def confirm(parent, title, message, danger=True, ok_text="확인"):
        asked.append(message)
        return answer[0]
    ui_box.confirm = confirm
    try:
        ed.vars["spe"].set("200")
        ed.vars["spd"].set("50")                            # 가방에 spd 약이 없다 - 50개를 사야 한다 (5,000원)
        wait(root, lambda: ed.plan is not None and ed.plan_for == ed.want)
        chk("계획 글에 사서 쓸 것 · 값", "사서 쓸 것: spd약 50개" in ed.plan_lb.cget("text")
            and "5,000원" in ed.plan_lb.cget("text"), ed.plan_lb.cget("text"))
        ed.apply()
        settle(root, 0.1)
        chk("모자라면 묻는다: '부족한 도구 50개를 5,000원에 사서 쓸까요?'",
            asked == ["부족한 도구 50개를 5,000원에 사서 쓸까요?"], asked)
        chk("  아니오면 아무것도 안 보낸다", nondry(api) == [], nondry(api))
        answer[0] = True
        ed.apply()
        wait(root, lambda: nondry(api) and not ed.busy)
        c = (nondry(api) or [{}])[0]
        chk("  예면 buy · 물어본 값을 같이 보낸다", c.get("buy") is True and c.get("cost") == 5000
            and c.get("evs", {}).get("spd") == 50 and c.get("evs", {}).get("spe") == 200, c)
        chk("  결과: 지금 값이 바뀌고 '적용' 잠김", ed.now_lb["spd"].cget("text") == "지금 50"
            and ed.now_lb["spe"].cget("text") == "지금 200" and ed.cur["spd"] == 50 and not ed.btn_apply.enabled,
            ed.now_lb["spd"].cget("text"))
        chk("  알림 글 (초록) · 박스에 알린다", "노력치를 맞췄다" in ed.say_lb.cget("text")
            and ed.say_lb.cget("fg") == tone(U.GOOD) and len(done) == 1 and done[0]["evs"]["spd"] == 50,
            (ed.say_lb.cget("text"), done))
        asked[:] = []
        ed.vars["atk"].set("240")                           # 가방에 atk 약이 넉넉하다
        wait(root, lambda: ed.plan is not None and ed.plan_for == ed.want)
        ed.apply()
        wait(root, lambda: len(nondry(api)) == 2 and not ed.busy)
        c = nondry(api)[-1]
        chk("다 가진 것이면 묻지 않고 buy 없이", asked == [] and c["buy"] is False and c["cost"] == 0
            and ed.cur["atk"] == 240, (asked, c))
        api.fail = "그사이 노력치가 바뀌었습니다. 다시 해 주세요."
        ed.vars["def"].set("6")
        wait(root, lambda: ed.plan is not None and ed.plan_for == ed.want)
        ed.apply()
        wait(root, lambda: len(nondry(api)) == 3 and not ed.busy)
        settle(root, 0.1)
        chk("서버가 거절하면 그 말을 빨갛게, 값은 그대로", "그사이 노력치가 바뀌었습니다" in ed.say_lb.cget("text")
            and ed.say_lb.cget("fg") == tone(U.DANGER) and ed.cur["def"] == 0 and ed.want["def"] == 6,
            ed.say_lb.cget("text"))
    finally:
        ui_box.confirm = real
    ed.close()
    chk("닫으면 앱에서 떼어 낸다", app.ev_editor is None and ed.closed)


def box_button(root):
    print("5. 포켓몬 관리 창의 '노력치 조정'")
    dex = P.Pokedex(json.load(open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8")))
    m = SB.mon(dex, 25, 1, on=True)
    m["info"]["evs"] = {"hp": 0, "atk": 12, "def": 0, "spa": 0, "spd": 0, "spe": 0}
    app = SB.FakeApp(root, dex, [m, SB.mon(dex, 4, 2)])
    app.api.set_evs = EvApi(m["info"]["evs"]).set_evs
    win = ui_box.BoxWindow(root, app)
    SB.wait_for(root, lambda: getattr(win, "mons", None))
    SB.settle_rows(root, win)
    win.select(1)
    settle(root, 0.3)
    btn = win.btn_evs
    chk("능력치 머리에 단추, 고르면 켜진다", btn.holder.winfo_ismapped() and btn.enabled
        and btn.label.cget("text") == "노력치 조정")
    btn._release(None)
    settle(root, 0.3)
    ed = getattr(app, "ev_editor", None)
    chk("  누르면 그 포켓몬의 창", ed is not None and ed.mon["id"] == 1 and ed.cur["atk"] == 12, ed and ed.cur)
    win.close()
    settle(root, 0.2)
    chk("  관리 창을 닫으면 같이 닫힌다", ed is not None and ed.closed and app.ev_editor is None)


def theme_link(root):
    print("6. 테마 요약의 '노력치 조정 ›'")
    dex = P.Pokedex(json.load(open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8")))
    m = SB.mon(dex, 25, 1, on=True)
    m["info"]["evs"] = {"hp": 0, "atk": 12, "def": 0, "spa": 0, "spd": 0, "spe": 0}
    app = SB.FakeApp(root, dex, [m, SB.mon(dex, 4, 2)])
    app.api.set_evs = EvApi(m["info"]["evs"]).set_evs
    win = ui_box.BoxWindow(root, app)
    top = win.win.winfo_toplevel()
    top.geometry("1180x760+20+20")
    top.deiconify()
    SB.wait_for(root, lambda: getattr(win, "mons", None))
    settle(root, 0.5)
    win.select(1)
    settle(root, 0.3)
    cv = win.dcv
    chk("이 테마의 박스 (DP 를 이어 쓴다)", type(win).__module__.endswith("%s.box" % SKIN), type(win).__module__)
    chk("  정보 쪽에는 없다", not cv.find_withtag("evlink"))
    win._pick_dpage("stats")
    settle(root, 0.3)
    ids = cv.find_withtag("evlink")
    texts = [cv.itemcget(i, "text") for i in ids if cv.type(i) == "text"]
    chk("  능력 쪽 노력치 줄 아래 '노력치 조정 ›' (밑줄)", texts == ["노력치 조정 ›"]
        and any(cv.type(i) == "line" for i in ids), texts)
    ev_y = max(cv.bbox(i)[3] for i in cv.find_all() if cv.type(i) == "text" and "노력치 " in cv.itemcget(i, "text")
               and "조정" not in cv.itemcget(i, "text"))
    chk("  노력치 줄 바로 아래", cv.bbox(ids[0])[1] >= ev_y if ids else False, (ids and cv.bbox(ids[0]), ev_y))
    cv.yview_moveto(1.0)
    settle(root, 0.1)
    x1, y1, x2, y2 = cv.bbox(texts and ids[0] or "evlink")
    x, y = int((x1 + x2) / 2 - cv.canvasx(0)), int((y1 + y2) / 2 - cv.canvasy(0))
    cv.event_generate("<Motion>", x=x, y=y)
    cv.event_generate("<Button-1>", x=x, y=y)
    cv.event_generate("<ButtonRelease-1>", x=x, y=y)
    settle(root, 0.3)
    ed = getattr(app, "ev_editor", None)
    chk("  누르면 노력치 조정 창", ed is not None and ed.mon["id"] == 1 and ed.cur["atk"] == 12)
    if ed is not None:
        chk("  테마에서도 안쪽이 눌리지 않는다", not squeezed(ed.win) and not squeezed(ed.inner),
            (squeezed(ed.win), squeezed(ed.inner)))
    win.close()
    settle(root, 0.2)


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append("%s: %s" % (e.__name__, v))
    print("== 테마: %s" % SKIN)
    chk("이번 실행의 테마", skins.active() == SKIN, skins.active())
    if SKIN == "default":
        editor(root)
        box_button(root)
    else:
        if SKIN == "dp":
            editor(root)                                    # DP 의 위젯 빛깔(widgets.install)에서도 창이 돈다
        theme_link(root)
    chk("그리는 중에 난 예외가 없다", not errors, errors[:3])
    try:
        root.destroy()
    except tk.TclError:
        pass


if __name__ == "__main__":
    main()
    if SKIN == "default":
        for key in ("dp", "swsh", "bw", "pt", "gs", "emerald"):
            env = dict(os.environ, POKET_EVED_SKIN=key)
            env.pop("POKET_HOME", None)
            out = subprocess.run([sys.executable, os.path.abspath(__file__)], env=env, capture_output=True, text=True)
            for line in out.stdout.splitlines():
                if line.startswith("  ") or line.startswith("==") or line[:2] in ("1.", "4.", "6."):
                    print(line)
                if line.startswith("합계"):
                    bits = line.split()
                    OK += int(bits[2])
                    FAIL += int(bits[4])
            if out.returncode != 0 or "합계" not in out.stdout:
                FAIL += 1
                print("  FAIL %s 테마 검사가 끝나지 않았다\n%s" % (key, out.stderr[-1500:]))
    print("합계 OK %d FAIL %d" % (OK, FAIL))
    sys.exit(1 if FAIL else 0)
