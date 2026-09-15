# -*- coding: utf-8 -*-
"""포켓몬 알 — 바탕화면에 서고, 흔들리고, 부화를 알리는가 (1.4.0).

    python client/smoke_eggs.py

**창을 실제로 만든다.** 서버 대신 가짜 API 와 가짜 앱을 쓴다. 보는 것:

  · sync_eggs 가 알을 세우고, 목록에서 빠지면 치운다
  · 알은 걸어다니지 않는다 (몇 초를 돌려도 가로 자리만 흔들린다)
  · 누르면 남은 시간이 뜬다, 이름표는 없다
  · 부화: 알이 흔들리다 사라지고 → 창이 뜨고 → 닫으면 seen 을 부른다
  · 창을 닫기 전에 다음 동기화가 같은 알을 또 실어 와도 창은 하나다
  · clear / 숨기기 / 설정 바꿔 다시 그리기에서 알이 남거나 사라지지 않는다
"""
import os
import shutil
import sys
import tempfile
import time

HOME = tempfile.mkdtemp(prefix="poket-smoke-eggs-")
os.environ["POKET_HOME"] = HOME

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                       # noqa: E402

from poketdesktop import config, eggs_ui, item_icons       # noqa: E402
from poketdesktop import overlay as OV                     # noqa: E402
from poketdesktop import platform_os as PLAT               # noqa: E402
from poketdesktop import ui_common as U                    # noqa: E402
from poketdesktop.app import App                           # noqa: E402

OK = FAIL = 0
ERRORS = []
SPRITES = os.path.join(os.path.dirname(HERE), "server", "data", "item_sprites")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def pump(root, secs, cond=None):
    end = time.time() + secs
    while time.time() < end:
        root.update()
        if cond and cond():
            return True
        time.sleep(0.01)
    return bool(cond and cond())


class FakeApi(object):
    def __init__(self):
        self.seen = []

    def egg_seen(self, eid):
        self.seen.append(eid)
        return {"ok": True}

    def item_sprite(self, item_id):
        p = os.path.join(SPRITES, "%s.png" % item_id)
        return open(p, "rb").read() if os.path.exists(p) else None


class FakeApp(object):
    """App 의 부화 알림 메서드가 쓰는 것만."""
    announce_hatch = App.announce_hatch
    _show_hatch = App._show_hatch
    _hatch_seen = App._hatch_seen

    def __init__(self, root, ov):
        self.root = root
        self.overlay = ov
        self.api = FakeApi()
        self._quitting = False
        self.battle = None
        self.arena = None
        self.synced = 0

    def sync(self):
        self.synced += 1


def egg(eid, kind="legendary", got=3600, need=48 * 3600, hatched=False, mon=None,
        on=True):
    name = "전설의 포켓몬 알" if kind == "legendary" else "환상의 포켓몬 알"
    e = {"id": eid, "kind": kind, "name": name, "gotSec": got, "needSec": need,
         "leftSec": max(0, need - got), "hatched": hatched, "onDesktop": on}
    if mon:
        e["pokemon"] = mon
    return e


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    root.report_callback_exception = lambda *a: ERRORS.append(a)
    U.init_fonts(root)
    U.apply_theme(root)
    settings = dict(config.DEFAULTS)
    settings["showNames"] = True
    ov = OV.Overlay(root, settings)
    app = FakeApp(root, ov)

    print("=== 그림 ===")
    eggs_ui.fetch_icons(app.api, [egg(1), egg(2, "mythical")])
    chk("알 그림 둘을 받아 둔다",
        item_icons.local_path("LEGENDEGG") and item_icons.local_path("MYTHICEGG"))

    print("\n=== 세우기 ===")
    ov.sync_eggs([egg(1), egg(2, "mythical", got=47 * 3600, need=48 * 3600)])
    chk("알 둘이 선다", sorted(ov.eggs) == [1, 2], list(ov.eggs))
    p1 = ov.eggs[1]
    chk("이름표가 없다", p1.name_win is None)
    chk("pets·extra 에는 안 들어간다", not ov.pets and not ov.extra)
    ov.start()
    y0 = p1.y
    xs = set()
    end = time.time() + 3.0
    p1._wait = 1
    while time.time() < end:
        root.update()
        xs.add(int(p1.x))
        time.sleep(0.01)
    chk("걸어다니지 않는다 (세로 자리 그대로)", p1.y == y0, (y0, p1.y))
    chk("가로로 조금 흔들린다", 1 < len(xs) <= 11, sorted(xs))
    tip = p1.tip_text()
    chk("상태·남은 시간을 말한다", "전설의 포켓몬 알" in tip and "시간" in tip, tip)
    chk("곧 태어날 알은 그렇게 말한다",
        "곧 태어날" in ov.eggs[2].tip_text(), ov.eggs[2].tip_text())
    p1.on_press(None)
    pump(root, 0.3)
    chk("누르면 말풍선이 뜬다", p1.tip_win is not None)
    p1.hide_tip()

    ov.sync_eggs([egg(1, got=7200)])
    chk("목록에서 빠진 알은 치운다", sorted(ov.eggs) == [1], list(ov.eggs))
    chk("남은 알은 새 값으로", ov.eggs[1].egg["gotSec"] == 7200)
    ov.sync_eggs([egg(1, got=7200), egg(3, "mythical", on=False)])
    chk("박스에 넣어 둔 알은 바탕화면에 안 선다 (1.4.1)", sorted(ov.eggs) == [1], list(ov.eggs))
    ov.sync_eggs([egg(1, got=7200, on=False)])
    chk("데리고 다니던 알을 박스에 넣으면 치운다", ov.eggs == {}, list(ov.eggs))
    ov.sync_eggs([egg(1, got=7200)])
    chk("다시 데리고 다니면 선다", sorted(ov.eggs) == [1], list(ov.eggs))

    print("\n=== 숨기기 · 다시 그리기 ===")
    ov.set_hidden(True)
    root.update()
    chk("숨기면 알도 숨는다", ov.eggs[1].win.state() == "withdrawn")
    ov.set_hidden(False)
    root.update()
    chk("다시 보인다", ov.eggs[1].win.state() == "normal")
    ov.refresh_visuals()
    root.update()
    chk("크기를 바꿔 다시 그려도 알은 남는다", sorted(ov.eggs) == [1], list(ov.eggs))

    print("\n=== 부화 ===")
    mon = {"id": 77, "num": 150, "level": 5, "shiny": False, "onDesktop": True,
           "info": {"name": "뮤츠", "species": "뮤츠"}}
    hatched = egg(1, got=48 * 3600, hatched=True, mon=mon)
    before = set(root.winfo_children())
    ov.sync_eggs([hatched])
    app.announce_hatch([hatched])
    app.announce_hatch([hatched])          # 다음 동기화가 또 실어 와도
    pet = ov.eggs.get(1)
    got_win = pump(root, 6.0, lambda: [w for w in root.winfo_children()
                                       if w not in before and isinstance(w, tk.Toplevel)
                                       and "태어났다" in _texts(w)])
    new = [w for w in root.winfo_children() if w not in before
           and isinstance(w, tk.Toplevel) and "태어났다" in _texts(w)]
    chk("부화 창이 뜬다", got_win and len(new) == 1, len(new))
    chk("알은 흔들리다 사라진다", pet is not None and pet.hatching and 1 not in ov.eggs,
        list(ov.eggs))
    if new:
        t = _texts(new[0])
        chk("태어난 포켓몬 이름", "뮤츠이(가) 태어났다" not in t and "뮤츠가 태어났다" in t, t)
        chk("데리고 다닌다고 알린다", "데리고 다닙니다" in t, t)
    chk("창을 닫기 전에는 seen 을 안 부른다", app.api.seen == [])
    chk("다시 동기화한다", app.synced >= 1)
    ov.sync_eggs([hatched])
    chk("부화 중인 알을 다시 세우지 않는다", 1 not in ov.eggs, list(ov.eggs))
    for w in new:
        w.tk.call(w.protocol("WM_DELETE_WINDOW"))       # 닫기 단추와 같은 길
    pump(root, 2.0, lambda: app.api.seen)
    chk("닫으면 seen 을 한 번 부른다", app.api.seen == [1], app.api.seen)
    app.announce_hatch([hatched])
    pump(root, 0.8)
    chk("알린 뒤 같은 목록이 와도 다시 안 띄운다",
        len([w for w in root.winfo_children() if isinstance(w, tk.Toplevel)
             and "태어났다" in _texts(w)]) == 0)

    print("\n=== 치우기 ===")
    ov.sync_eggs([egg(5, "mythical")])
    ov.clear()
    chk("clear 하면 알도 없어진다", ov.eggs == {})

    chk("그리는 중에 난 오류가 없다", not ERRORS, [str(e[1]) for e in ERRORS][:3])
    ov.stop()
    root.destroy()
    shutil.rmtree(HOME, ignore_errors=True)
    print("\n  합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


def _all(w):
    out = []
    for c in w.winfo_children():
        out.append(c)
        out.extend(_all(c))
    return out


def _texts(w):
    out = []
    for c in _all(w):
        try:
            if "text" in c.keys():
                out.append(str(c.cget("text")))
        except tk.TclError:
            pass
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
