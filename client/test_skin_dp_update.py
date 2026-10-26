# -*- coding: utf-8 -*-
"""DP 테마 검사 - 업데이트 창(받는 창 · 묻는 창)과 '불러오는 중'(덮는 판 · 작은 창).

    python client/test_skin_dp_update.py          (DP)
    python client/test_skin_dp_update.py default  (기본 테마로도 같은 동작인지)

  1. 테마 클래스로 뜬다 (dp = skins.dp.*, default = 기본 모듈).
  2. 묻는 창: '지금 받기' → "now", '나중에' · Esc · 닫기 → "later". DP 는 위아래 · Enter 로도 고른다.
  3. 받는 창: say · progress 가 에러 없이 되고, '나중에' 는 "skip", 받기 실패는 "failed" · 성공은 "updated".
  4. 덮는 판: say · close 가 되고 close 뒤에 다시 그리지 않는다. 오래 걸리면 까닭이 붙는다. 작은 창은 close 로 닫힌다.
  5. 그리는 중 예외가 없다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-skin-dp-update-")
SKIN = sys.argv[1] if len(sys.argv) > 1 else "dp"
os.environ["POKET_SKIN"] = SKIN

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import time                                                 # noqa: E402
import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT               # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_loading, ui_update, updater     # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


PLAT.before_tk()
skins.register_fonts()
root = tk.Tk()
root.withdraw()
U.init_fonts(root)
U.apply_theme(root)
errs = []
root.report_callback_exception = lambda e, v, tb: errs.append("".join(__import__("traceback").format_exception(e, v, tb)))
host = tk.Toplevel(root)
host.geometry("500x360+40+40")

DP = SKIN == "dp"
want_mod = "poketdesktop.skins.dp." if DP else "poketdesktop.ui_"
INFO = {"version": "9.9.9", "size": 5 * 1048576, "url": "x",
        "notes": "## 바뀐 것\n\n- 길드 채팅이 빨라졌습니다\n- 도감 찾기를 고쳤습니다\n"}


def pump(ms=120):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def key(win, name):
    win.event_generate("<%s>" % name)
    root.update()


# ---------------------------------------------------------------- 묻는 창
print("묻는 창")


def run_ask(act):
    ask = ui_update.NewVersionAsk(host, INFO)
    root.after(150, lambda: act(ask))
    return ask, ask.show()


ask, res = run_ask(lambda a: a.on_now())
chk("테마 클래스로 뜬다", type(ask).__module__.startswith(want_mod), type(ask).__module__)
chk("지금 받기 → now", res == "now", res)
ask, res = run_ask(lambda a: a.on_later())
chk("나중에 → later", res == "later", res)
ask, res = run_ask(lambda a: a.win.protocol("WM_DELETE_WINDOW") and a.win.tk.call(a.win.protocol("WM_DELETE_WINDOW")))
chk("닫기 → later", res == "later", res)
if DP:
    ask, res = run_ask(lambda a: (a.win.focus_force(), key(a.win, "Down"), key(a.win, "Return")))
    chk("DP: 아래 · Enter → later", res == "later", res)
    ask, res = run_ask(lambda a: (a.win.focus_force(), key(a.win, "Return")))
    chk("DP: Enter 만 → now (커서는 지금 받기에서 시작)", res == "now", res)
    ask, res = run_ask(lambda a: (a.win.focus_force(), key(a.win, "Escape")))
    chk("DP: Esc → later", res == "later", res)
    ask, res = run_ask(lambda a: a.choice.items and a.choice._click(type("E", (), {"x": a.choice.box[0] + 40,
                                      "y": a.choice.box[1] + U.h(8) + a.choice.row_h + 5})()))
    chk("DP: '나중에' 줄을 누르면 later", res == "later", res)
ask2 = ui_update.NewVersionAsk(host, {"version": "9.9.9", "size": 0, "notes": ""})
need, got = ask2.win.winfo_reqheight(), ask2.win.winfo_height()
pump(100)
chk("줄거리 없어도 단추가 안 잘린다", ask2.win.winfo_height() >= ask2.win.winfo_reqheight() - 2,
    (ask2.win.winfo_height(), ask2.win.winfo_reqheight()))
ask2.finish()

# ---------------------------------------------------------------- 받는 창
print("받는 창")
w = ui_update.UpdateWindow(host, INFO)
chk("테마 클래스로 뜬다", type(w).__module__.startswith(want_mod), type(w).__module__)
w.say("새 버전을 받고 있습니다")
w.progress(0.2, "1.0 / 5.0 MB")
w.progress(0.7, "3.5 / 5.0 MB")
w.progress(5, "넘침")
w.progress(-1, "")
pump(150)
chk("몬스터볼 도는 일이 걸려 있다", bool(w.spin_job))
w.finish()
chk("끝내면 도는 일이 멈춘다", w.spin_job is None and w.done_flag)

w = ui_update.UpdateWindow(host, INFO)
root.after(150, w.on_skip)
res = w.show(quiet=True)
chk("나중에 → skip", res == ("skip", None), res)

# 받기 성공 / 실패 (가짜 updater)
real = (updater.temp_zip, updater.download, updater.extract, updater.parent_dir)
try:
    updater.temp_zip = lambda v: "/nonexistent/z.zip"
    updater.parent_dir = lambda: "/nonexistent"

    def dl_ok(url, path, cb):
        cb(1 << 20, 5 << 20)
        cb(5 << 20, 5 << 20)

    def ex_ok(z, d, v, cb):
        cb(1, 2)
        cb(2, 2)
        return "/nonexistent/new.exe"
    updater.download, updater.extract = dl_ok, ex_ok
    box = {}

    def go_ok():                  # 작업 스레드가 root.after 를 부르므로 mainloop 안에서 돌린다
        w = ui_update.UpdateWindow(host, INFO)
        box["ok"] = w.show(quiet=True)
        root.quit()
    root.after(0, go_ok)
    root.mainloop()
    res = box["ok"]
    chk("받기 성공 → updated + 새 실행 파일", res == ("updated", "/nonexistent/new.exe"), res)

    def dl_bad(url, path, cb):
        raise IOError("끊김")
    updater.download = dl_bad

    def go_bad():
        w = ui_update.UpdateWindow(host, INFO)
        box["bad"] = w.show(quiet=True)
        root.quit()
    root.after(0, go_bad)
    root.mainloop()
    res = box["bad"]
    chk("받기 실패 → failed", res[0] == "failed", res)
finally:
    updater.temp_zip, updater.download, updater.extract, updater.parent_dir = real

# ---------------------------------------------------------------- 불러오는 중
print("불러오는 중")
ov = ui_loading.Overlay(host, "불러오는 중")
chk("테마 클래스로 뜬다", type(ov).__module__.startswith(want_mod), type(ov).__module__)
pump(200)
ov.say("다른 글")
pump(100)
ov.t0 -= 10                                   # 오래 기다린 척
pump(200)
if DP:
    pump(500)
    chk("DP: 오래 걸리면 까닭이 붙는다", "초" in ov._note, ov._note)
    chk("DP: 점이 늘어난다", ov._dots in (0, 1, 2, 3))
else:
    chk("오래 걸리면 까닭이 붙는다", "초" in ov.note.cget("text"), ov.note.cget("text"))
ov.close()
ov.close()
chk("close 는 두 번 불러도 된다", ov.done)
pump(150)

pp = ui_loading.Popup(host, "불러오는 중", slow="느립니다 (%d초)")
chk("작은 창이 뜬다", pp.win.winfo_exists() == 1)
chk("작은 창 안이 테마 클래스", type(pp.body).__module__.startswith(want_mod), type(pp.body).__module__)
pump(150)
pp.say("바꾼 글")
pump(100)
pp.close()
chk("close 로 닫힌다", not pp.win.winfo_exists())

chk("그리는 중 난 예외가 없다", not errs, errs[:1])
print("합계 OK %d FAIL %d" % (OK, FAIL))
sys.exit(1 if FAIL else 0)
