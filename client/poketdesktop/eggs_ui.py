# -*- coding: utf-8 -*-
"""포켓몬 알 — 바탕화면에 놓이고, 켜 둔 시간만큼 자라서 부화한다.

알은 서버가 센다(켜 둔 시간, 부화). 여기서 하는 일은 셋이다.

  · 알을 바탕화면에 세워 두고, 가끔 흔들린다. 곧 태어날 것 같으면 자주
    흔들린다. 마우스를 올리거나 누르면 남은 시간이 뜬다.
  · 서버가 부화했다고 알려 오면(/api/me 의 eggs[].hatched) 알이 크게
    흔들리다 사라지고, 태어난 포켓몬을 창으로 보여준다.
  · 다 보여준 뒤 /api/eggs/{id}/seen 을 부른다. 그전에 앱이 꺼지면 다음에
    켤 때 다시 보여준다.

알은 걸어다니지 않고, 이름표·오른쪽 메뉴·배틀이 없다. 다만 1.4.1 부터는
포켓몬처럼 파티 한 자리를 차지하고 박스에 넣을 수 있다 (포켓몬 관리 창,
box_filter.egg_row). 박스에 넣은 알은 바탕화면에 안 서고 자라지도 않는다.
"""
import random
import tkinter as tk

from common.korean import natural

from . import item_icons, sprite_cache, sprites
from . import ui_common as U
from .overlay import Pet

EGG_ITEM = {"legendary": "LEGENDEGG", "mythical": "MYTHICEGG"}
EGG_COLOR = {"legendary": "#ffd35c", "mythical": "#e3b8ff"}

SHAKE = [-2, 2, -2, 2, -1, 1, 0]
SHAKE_BIG = [-5, 5, -5, 5, -4, 4, -3, 3, -2, 2, 0]


def hours_text(sec):
    sec = max(0, int(sec or 0))
    h = sec / 3600.0
    if sec <= 0:
        return "곧 태어날 것 같다!"
    if h < 1:
        return "부화까지 %d분" % max(1, sec // 60)
    return "부화까지 약 %d시간" % int(round(h))


def mood(egg):
    """알의 상태를 한 줄로. 본가의 '알의 상태' 말투를 따른다."""
    need = max(1, int(egg.get("needSec") or 1))
    got = int(egg.get("gotSec") or 0)
    r = got / float(need)
    if r >= 0.9:
        return "안에서 소리가 들린다! 곧 태어날 것 같다!"
    if r >= 0.6:
        return "가끔 움직이는 것 같다."
    if r >= 0.3:
        return "무엇이 태어날까? 아직 시간이 걸릴 것 같다."
    return "태어나려면 아직 한참 걸릴 것 같다."


class EggPet(Pet):
    """바탕화면의 알 하나. overlay.eggs 에 들어간다 (pets·extra 와 따로)."""

    def __init__(self, overlay, egg, anim):
        self.egg = egg
        self.hatching = False
        self._shake = None
        self._wait = random.randint(120, 260)
        Pet.__init__(self, overlay, {"id": -3000 - int(egg.get("id") or 0),
                                     "num": None, "shiny": False,
                                     "info": {"name": egg.get("name")}}, anim)
        self.battling = True           # 혼자 돌아다니지 않는다
        self.facing = next(iter(self.photos.keys()))
        self.redraw()

    # 알은 칸 크기가 변하지 않는다. Pet 의 것은 도감 번호로 동작 시트를 본다.
    def reserve_box(self):
        fn = getattr(self.view, "reserve", None)
        if fn is not None:
            fn(self.fw, self.fh)

    def make_nameplate(self):
        return None                    # 알에는 이름표가 없다

    def tip_text(self):
        e = self.egg
        return "%s\n%s\n%s\n(데리고 다니는 동안 켜 둔 시간만큼 자랍니다)" % (
            e.get("name") or "알", mood(e), hours_text(e.get("leftSec")))

    def set_egg(self, egg):
        self.egg = egg

    # ---- 입력: 누르면 상태만 보여준다 ----
    def on_press(self, e):
        self.show_tip()

    def on_release(self, e):
        pass

    def on_menu(self, e):
        self.show_tip()

    def on_double(self, e):
        pass

    # ---- 흔들기 ----
    def update(self, ms):
        if self._shake is not None:
            seq, i, hx, done = self._shake
            if i >= len(seq):
                self.x = hx
                self._shake = None
                self.place()
                if done:
                    done()
                return
            self.x = hx + seq[i]
            self._shake = (seq, i + 1, hx, done)
            self.place()
            return
        if self.hatching:
            return
        self._wait -= 1
        if self._wait <= 0:
            need = max(1, int(self.egg.get("needSec") or 1))
            near = int(self.egg.get("gotSec") or 0) / float(need) >= 0.9
            self._wait = random.randint(40, 90) if near else random.randint(180, 420)
            self.shake(SHAKE)

    def shake(self, seq, done=None):
        self._shake = (list(seq), 0, self.x, done)

    def hatch(self, done):
        """크게 세 번 흔들린 뒤 사라진다. 다 끝나면 done()."""
        self.hatching = True
        self.hide_tip()
        left = [3]

        def again():
            left[0] -= 1
            if left[0] <= 0:
                try:
                    self.win.withdraw()
                except tk.TclError:
                    pass
                return done()
            self.ov.root.after(260, lambda: self.shake(SHAKE_BIG, again))
        self.shake(SHAKE_BIG, again)


def egg_anim(overlay, kind):
    """알 그림. 받아 둔 것이 없으면 None (다음 동기화 때 다시 본다)."""
    path = item_icons.local_path(EGG_ITEM.get(kind, "LEGENDEGG"))
    if not path:
        return None
    h = int(overlay.settings.get("targetHeight", 56) * 0.8)
    try:
        return sprites.load_animation(path, max(32, h), 0.5, 4.0)
    except Exception:                                      # noqa: BLE001
        return None


def fetch_icons(api, eggs):
    """작업 스레드에서. 알 그림을 받아 둔다."""
    for kind in set((e or {}).get("kind") for e in eggs or []):
        if kind in EGG_ITEM:
            try:
                item_icons.raw(api, EGG_ITEM[kind])
            except Exception:                              # noqa: BLE001
                pass


# ---------------------------------------------------------------- 부화 알림
def announce_hatch(parent, app, egg, on_close=None):
    """알에서 태어난 포켓몬을 보여준다."""
    from . import ui_box
    mon = egg.get("pokemon") or {}
    info = mon.get("info") or {}
    name = info.get("name") or info.get("species") or "포켓몬"
    win, f = ui_box._shell(parent, "알이 부화했다", 400, U.h(360))
    color = EGG_COLOR.get(egg.get("kind"), U.ACCENT)

    def close():
        try:
            win.destroy()
        except tk.TclError:
            pass
        if on_close:
            on_close()
    # **단추 줄을 맨 먼저 아래에 붙인다.** 나중에 담으면 위의 내용이 자리를
    # 다 먹고 단추가 창 밖으로 잘린다 (실제로 그랬다).
    row = tk.Frame(f, bg=U.BG)
    row.pack(fill="x", side="bottom")
    U.PushButton(row, "반가워!", close, height=34,
                 font=U.FONT_B).pack(side="right")
    win.protocol("WM_DELETE_WINDOW", close)

    tk.Label(f, text="알이 부화했다!", bg=U.BG, fg=color,
             font=(U.FAMILY_BLACK, U.pt(18))).pack(anchor="w")
    tk.Label(f, text=egg.get("name") or "", bg=U.BG, fg=U.FG_DIM,
             font=U.FONT_S).pack(anchor="w", pady=(2, 0))
    slot = tk.Frame(f, bg=U.BG, width=U.h(110), height=U.h(100))
    slot.pack(pady=(8, 2))
    slot.pack_propagate(False)
    art = tk.Label(slot, bg=U.BG)
    art.pack(expand=True)
    tk.Label(f, text=natural("%s이(가) 태어났다!" % name), bg=U.BG, fg=U.FG,
             font=U.FONT_H).pack()
    bits = ["Lv.%d" % int(mon.get("level") or 0)] if mon else []
    if mon.get("shiny"):
        bits.append("★ 색이 다른 개체")
    if mon:
        bits.append("데리고 다닙니다" if mon.get("onDesktop")
                    else "파티가 꽉 차서 박스에 넣었습니다")
    tk.Label(f, text="  ·  ".join(bits), bg=U.BG,
             fg=U.SHINY if mon.get("shiny") else U.FG_FAINT,
             font=U.FONT_XS).pack(pady=(4, 0))

    num = mon.get("num")
    if num:
        def work():
            return sprite_cache.ensure(app.api, num, mon.get("shiny"))

        def done(path, err):
            if err or not path:
                return
            try:
                from PIL import ImageTk
                a = sprites.load_animation(path, 88, 1.0, 3.0, max_frames=1)
                ph = ImageTk.PhotoImage(sprites.to_rgba(a.frames[sprites.RIGHT][0],
                                                        a.key))
                # 창에 붙여 둔다. 지역 변수에만 두면 이 함수가 끝나는 순간
                # 그림이 지워져 빈칸이 된다 (tk 가 PhotoImage 를 붙들지 않는다).
                art.image = ph
                art.configure(image=ph)
            except Exception:                              # noqa: BLE001
                pass
        U.run_async(parent, work, done)
    return win
