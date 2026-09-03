# -*- coding: utf-8 -*-
"""1.0.13 에서 들어온 창 셋이 제 크기로 만들어지는가.

    python client/smoke_new_windows.py

**창을 실제로 만든다.** 화면에 띄우지는 않지만(withdraw) tk 가 위젯을
배치하고 크기를 재기까지 한다. 그래서 화면이 있는 러너에서만 돈다.

## 왜 이 검사가 있나

정해 둔 창 높이가 내용보다 작으면 **아래가 잘려 나간다.** 그런데 잘리는
것은 맨 아래에 담은 것 - 단추다. 단추가 안 보이면 사용자가 할 수 있는
일은 창을 닫는 것뿐이다.

실제로 그랬다. 설정 창에 손잡이 둘을 더 넣고 나니 13px 이 모자라
'기본값으로 / 닫기' 줄이 잘렸고, 새 버전을 묻는 창은 릴리스 본문이 길면
91px 이 모자라 '지금 받기' 가 화면 밖으로 나갔다. 눈으로 열어 보기
전에는 알 수 없는 종류의 고장이라, 높이를 여기서 숫자로 견준다.

새 버전 창은 아예 내용에 맞춰 늘어나게 고쳤다(NewVersionAsk._fit).
릴리스마다 줄거리 길이가 달라서, 정해 둔 숫자로는 늘 어느 쪽이든 틀린다.
"""
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-smoke-newwin"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                       # noqa: E402

from common import patchnotes                              # noqa: E402
from common.version import VERSION                         # noqa: E402
from poketdesktop import config, ui_settings, ui_update    # noqa: E402
from poketdesktop import ui_common as U                    # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


class FakeWild(object):
    def __init__(self):
        self.calls = []

    def set_enabled(self, on):
        self.calls.append(bool(on))


class FakeApp(object):
    """설정 창이 만지는 것만 갖춘 껍데기."""

    def __init__(self, root):
        self.root = root
        self.settings = dict(config.DEFAULTS)
        self.overlay = None
        self.wild = FakeWild()
        self.settings_win = None
        self.tray = None
        self.said = []

    def refresh_tray(self):
        pass

    def set_size(self, px):
        pass

    def set_autostart(self, on):
        return True, "ok"

    def set_show_grass(self, on):
        self.settings["showGrass"] = bool(on)
        self.wild.set_enabled(bool(on))
        return bool(on)

    def notify(self, msg):
        self.said.append(msg)


def height_of(win):
    """지금 정해진 창 높이 (geometry 가 '460x380+..' 꼴이다)."""
    win.update_idletasks()
    return int(win.geometry().split("+")[0].split("x")[1])


def main():
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    app = FakeApp(root)

    # ---------------- 설정 창 ----------------
    print("설정 창")
    sw = ui_settings.SettingsWindow(app)
    sw.win.update_idletasks()
    need = sw.win.winfo_reqheight()
    print("  필요 %dpx / 정한 높이 %dpx" % (need, ui_settings.H))
    chk("아래가 잘리지 않는다", need <= ui_settings.H,
        "%dpx 모자란다 - ui_settings.H 를 올려라" % (need - ui_settings.H))

    # 손잡이가 실제로 이어져 있는가 (표시만 바뀌고 아무 일도 안 하면
    # 사용자는 껐다고 믿는데 풀숲이 계속 돋는다)
    sw.grass.set(False)
    sw._toggle_grass("showGrass", sw.grass)
    chk("풀숲 손잡이가 야생 쪽으로 간다", app.wild.calls == [False],
        "calls=%r" % app.wild.calls)
    app.settings["showGrass"] = True
    sw.show_grass()
    chk("트레이에서 바꾼 것을 표시가 따라온다", sw.grass.get() is True)
    sw.notif.set(False)
    sw._toggle_plain("notifyImportant", sw.notif)
    chk("알림 손잡이가 저장된다",
        app.settings["notifyImportant"] is False,
        "설정=%r" % app.settings["notifyImportant"])
    sw.close()

    # ---------------- 패치노트 창 ----------------
    print("새로운 기능 창")
    entry = patchnotes.entry(VERSION) or patchnotes.latest()
    chk("보여줄 패치노트가 있다", entry is not None)
    if entry:
        pn = ui_update.PatchNotes(root, entry, greet=True)
        pn.win.update_idletasks()
        lines = int(pn.txt.index("end-1c").split(".")[0])
        print("  본문 %d줄" % lines)
        # 항목마다 제목 한 줄, 설명 있으면 한 줄. 적어도 항목 수만큼은 있다.
        chk("항목이 본문에 다 들어갔다", lines >= len(entry["items"]),
            "lines=%d items=%d" % (lines, len(entry["items"])))
        chk("스크롤이 달려 있다", pn.txt.cget("yscrollcommand") != "")
        pn.close()

    # ---------------- 새 버전 묻는 창 ----------------
    print("새 버전 묻는 창")
    body = open(os.path.join(os.path.dirname(HERE), ".github",
                             "release-notes.md"), encoding="utf-8").read()
    for label, info in (
            ("긴 본문", {"version": "9.9.9", "size": 41 * 1048576,
                          "notes": body}),
            ("줄거리 없음", {"version": "9.9.9", "size": 0, "notes": ""}),
            ("크기 모름", {"version": "9.9.9", "notes": body})):
        ask = ui_update.NewVersionAsk(root, info)
        need = ask.win.winfo_reqheight()
        got = height_of(ask.win)
        print("  %s: 필요 %dpx / 실제 %dpx" % (label, need, got))
        chk("%s - 단추가 잘리지 않는다" % label, got >= need,
            "%dpx 모자란다" % (need - got))
        ask.finish()

    root.destroy()
    print()
    print("통과 %d, 실패 %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
