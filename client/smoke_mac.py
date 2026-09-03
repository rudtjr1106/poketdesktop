# -*- coding: utf-8 -*-
"""맥 전용 - 투명 창에 도트가 진짜로 그려지는지 본다.

    python client/smoke_mac.py

화면이 필요하다. 창을 잠깐 띄웠다가 스스로 끈다.

**눈으로 보는 대신 화면에 합성된 결과를 그대로 읽는다.** 자기 프로세스의
창은 CGWindowListCreateImage 로 찍을 수 있어서, 도트가 실제로 보이는지
모서리가 투명한지를 숫자로 확인할 수 있다.

여기가 깨지면 맥에서 포켓몬이 안 보이거나 네모난 판 위에 뜬다.
"""
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-smoke-mac"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                       # noqa: E402

from poketdesktop import effects                           # noqa: E402
from poketdesktop import platform_os as PLAT               # noqa: E402
from poketdesktop import ui_common as U                    # noqa: E402

OK = FAIL = 0
SIZE = 64
KEY = (255, 0, 255)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


def section(t):
    print("-- %s" % t)


def screen_locked():
    """화면이 잠겨 있는가.

    잠겨 있으면 우리 창이 화면에 합성되지 않는다. 그러면 캡처는 전부
    투명하게 나오고 '어느 창이 클릭을 받는가' 물으면 잠금 화면이
    답한다 - 검사가 전부 실패하는데 **코드는 멀쩡하다.** 그 상태를
    실패로 보고하면 없는 버그를 찾느라 시간을 버린다.
    """
    try:
        import Quartz
        d = Quartz.CGSessionCopyCurrentDictionary() or {}
        return bool(d.get("CGSSessionScreenIsLocked"))
    except Exception:                                       # noqa: BLE001
        return False


def grab(nswin):
    """이 창이 화면에 어떻게 합성됐는지 그대로 읽는다. (w, h, 픽셀함수)"""
    import Quartz

    num = nswin.windowNumber()
    img = Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull,
        Quartz.kCGWindowListOptionIncludingWindow, num,
        Quartz.kCGWindowImageBoundsIgnoreFraming
        | Quartz.kCGWindowImageShouldBeOpaque * 0)
    if img is None:
        return None
    w = Quartz.CGImageGetWidth(img)
    h = Quartz.CGImageGetHeight(img)
    row = Quartz.CGImageGetBytesPerRow(img)
    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(img))
    buf = bytes(data)
    info = Quartz.CGImageGetAlphaInfo(img)

    def px(x, y):
        i = y * row + x * 4
        b, g, r, a = buf[i], buf[i + 1], buf[i + 2], buf[i + 3]
        return r, g, b, a

    return w, h, px, info


def real_pet(root):
    """진짜 도트로 진짜 Pet 을 하나 만들어 본다.

    위의 검사는 몬스터볼 그림으로 뼈대만 봤다. 여기서는 실제 GIF 를
    sprites 가 처리한 결과를 overlay.Pet 이 그대로 띄운다 - 앱이 하는
    것과 같은 길이다. 도트 파일은 인자로 준다.

        python client/smoke_mac.py <도트.gif>
    """
    from poketdesktop import platform_mac as M
    from poketdesktop.overlay import Overlay

    path = sys.argv[1] if len(sys.argv) > 1 else None
    section("진짜 도트로 만든 Pet")
    if not path or not os.path.exists(path):
        print("   (도트 파일을 안 줘서 건너뜁니다: "
              "python client/smoke_mac.py <도트.gif>)")
        return

    from poketdesktop import config
    ov = Overlay(root, config.load_settings())
    mon = {"id": 1, "num": 1, "shiny": False,
           "info": {"name": "시험몬", "level": 5, "types": ["풀"]}}
    ov.paths[(1, False)] = path
    pet = ov.make(mon)
    chk("Pet 이 만들어졌다", pet is not None)
    if pet is None:
        return
    pet.x, pet.y = 320, 320
    pet.place()
    pet.redraw()

    # 도트 밑에 평범한 창을 하나 깔아 둔다. 빈 자리를 눌렀을 때 클릭이
    # 여기까지 오는지 보려는 것이다.
    import tkinter as tk
    bottom = tk.Toplevel(root)
    bottom.geometry("240x240+300+300")
    bottom.configure(bg="#3050a0")

    got = {}

    def shoot():
        nsw = M.nswindow(pet.win)
        got["nsw"] = nsw
        got["shot"] = grab(nsw) if nsw is not None else None
        got["bottom"] = _nswin_number(bottom)
        got["pet"] = nsw.windowNumber() if nsw is not None else None

        # 지금 그려진 그림에서 몸이 있는 점과 빈 점을 하나씩 고른다
        fr = pet.view._cur
        solid = hole = None
        if fr is not None and fr.mask is not None:
            w, h = fr.width(), fr.height()
            for y in range(h):
                for x in range(w):
                    if fr.mask[y * w + x]:
                        if solid is None:
                            solid = (x, y)
                    elif hole is None:
                        hole = (x, y)
            got["solid"], got["hole"] = solid, hole
            if hole is not None:
                sx, sy = int(pet.x) + hole[0], int(pet.y) + hole[1]
                pet.view.update_hit(hole[0], hole[1])
                got["hole_ok"] = settle(root, sx, sy, got["bottom"])
                got["hole_hit"] = who_gets_the_click(sx, sy)
            if solid is not None:
                sx, sy = int(pet.x) + solid[0], int(pet.y) + solid[1]
                pet.view.update_hit(solid[0], solid[1])
                got["solid_ok"] = settle(root, sx, sy, got["pet"])
                got["solid_hit"] = who_gets_the_click(sx, sy)
            # 창 밖이면 도로 막아 둬야 한다
            pet.view.update_hit(None, None)
            root.update()
            got["outside_ignoring"] = pet.view._ignoring
        root.quit()

    root.after(1500, shoot)
    root.mainloop()

    chk("Pet 창의 NSWindow 를 찾았다", got.get("nsw") is not None)
    if got.get("nsw") is not None:
        chk("Pet 창이 불투명하지 않다", not got["nsw"].isOpaque())
    shot = got.get("shot")
    chk("Pet 창을 찍었다", shot is not None)
    if shot:
        w, h, px, _ = shot
        chk("크기가 도트 크기와 맞다", w >= pet.fw and h >= pet.fh,
            "%dx%d vs %dx%d" % (w, h, pet.fw, pet.fh))
        chk("모서리가 투명하다", px(1, 1)[3] == 0, px(1, 1))
        drawn = sum(1 for y in range(0, h, 2) for x in range(0, w, 2)
                    if px(x, y)[3] > 40)
        chk("도트가 실제로 그려져 있다", drawn > 50, drawn)
        # 색빼기 색이 화면에 남으면 안 된다 (도트마다 다르므로 여러 색을 본다)
        key = pet.anim.key
        leak = sum(1 for y in range(h) for x in range(w)
                   if px(x, y)[3] > 200 and (px(x, y)[0], px(x, y)[1],
                                             px(x, y)[2]) == key)
        chk("투명색이 화면에 안 남는다", leak == 0, leak)

    section("도트 둘레의 빈 자리로 클릭이 지나가는가")
    chk("몸이 있는 점을 찾았다", got.get("solid") is not None, got.get("solid"))
    chk("빈 점을 찾았다", got.get("hole") is not None, got.get("hole"))
    if got.get("hole") is not None:
        chk("빈 자리를 누르면 아래 창으로 간다", got.get("hole_ok"),
            "받는 창=%s, 아래 창=%s" % (got.get("hole_hit"), got.get("bottom")))
    if got.get("solid") is not None:
        chk("도트 위를 누르면 포켓몬이 받는다", got.get("solid_ok"),
            "받는 창=%s, 도트 창=%s" % (got.get("solid_hit"), got.get("pet")))
    chk("커서가 창 밖이면 도로 막는다", got.get("outside_ignoring") is False,
        got.get("outside_ignoring"))

    try:
        bottom.destroy()
    except Exception:                                       # noqa: BLE001
        pass
    try:
        pet.destroy()
    except Exception:                                       # noqa: BLE001
        pass


def fx_layer_check(root):
    """이펙트 레이어 - 클릭이 통과하는가, 그림이 보이는가."""
    from poketdesktop import fx_layer as FL
    from poketdesktop import platform_mac as M

    section("이펙트 레이어")
    # 레이어 밑에 평범한 창을 하나 깔아 둔다. 클릭이 정말 레이어를
    # 지나 이 창까지 가는지 보려는 것이다.
    import tkinter as tk
    bottom = tk.Toplevel(root)
    bottom.title("아래 창")
    bottom.geometry("200x150+400+400")
    bottom.configure(bg="#3050a0")

    area = (300, 300, 700, 600)
    layer = FL.open_layer(root, area)
    chk("레이어가 열린다 (클릭 통과에 성공했다)", layer is not None)
    if layer is None:
        print("   클릭 통과를 못 걸어서 레이어를 안 띄웠다. "
              "이러면 배틀 이펙트와 체력바가 통째로 빠진다.")
        return

    nsw = M.nswindow(layer.win)
    chk("NSWindow 를 찾았다", nsw is not None)
    if nsw is not None:
        chk("마우스가 통과한다", bool(nsw.ignoresMouseEvents()))
        chk("불투명하지 않다", not nsw.isOpaque())

    # 이펙트는 그림이 아니라 선과 글자다. 맥에서도 투명 배경 위에
    # 그대로 그려져야 한다 (그림만 안 그려진다).
    cx, cy = layer.to_local(500, 450)
    layer.cv.create_oval(cx - 40, cy - 40, cx + 40, cy + 40,
                         fill="#ffcc33", outline="")
    FL.FloatText(layer, 500, 380, "100 데미지!", "#ff5566", ms=8000)

    got = {}

    def shoot():
        got["shot"] = grab(nsw) if nsw is not None else None
        got["bottom"] = _nswin_number(bottom)
        got["hit_through"] = who_gets_the_click(500, 450)
        # 대조 실험 - 통과를 끄면 레이어 자신이 잡혀야 한다. 이게 없으면
        # "원래부터 아래 창이었다" 와 구분이 안 된다.
        if nsw is not None:
            nsw.setIgnoresMouseEvents_(False)
            got["blocked_ok"] = settle(root, 500, 450, nsw.windowNumber())
            got["hit_blocked"] = who_gets_the_click(500, 450)
            nsw.setIgnoresMouseEvents_(True)
            got["again_ok"] = settle(root, 500, 450, got["bottom"])
        root.quit()

    root.after(1500, shoot)
    root.mainloop()

    if nsw is not None:
        chk("마우스가 레이어를 지나 아래 창으로 간다",
            got.get("hit_through") == got.get("bottom"),
            "받는 창=%s, 아래 창=%s, 레이어=%s"
            % (got.get("hit_through"), got.get("bottom"), nsw.windowNumber()))
        # 대조군. 통과를 끄면 레이어가 잡혀야 한다 - 안 그러면 위 검사는
        # 아무것도 증명하지 않는다.
        chk("통과를 끄면 레이어가 클릭을 먹는다",
            got.get("hit_blocked") == nsw.windowNumber(),
            got.get("hit_blocked"))
        chk("다시 켜면 도로 통과한다", got.get("again_ok"))

    shot = got.get("shot")
    chk("레이어를 찍었다", shot is not None)
    if shot:
        w, h, px, _ = shot
        chk("아무것도 없는 자리는 투명하다", px(2, 2)[3] == 0, px(2, 2))
        drawn = sum(1 for y in range(0, h, 3) for x in range(0, w, 3)
                    if px(x, y)[3] > 40)
        chk("이펙트(원과 글자)가 그려져 있다", drawn > 100, drawn)

    # withdraw/deiconify 뒤에도 클릭 통과가 유지되는지 (풀리는 자리다)
    if nsw is not None:
        layer.win.withdraw()
        layer.win.deiconify()
        root.update_idletasks()
        before = bool(nsw.ignoresMouseEvents())
        layer.raise_above()
        chk("숨겼다 켜면 통과가 풀린다 (알고 있는 함정)", not before, before)
        chk("raise_above 가 다시 걸어 준다",
            bool(nsw.ignoresMouseEvents()))
    layer.destroy()
    try:
        bottom.destroy()
    except Exception:                                       # noqa: BLE001
        pass


def who_gets_the_click(x, y):
    """그 화면 좌표에서 마우스를 받을 창의 번호.

    창 서버에 직접 묻는 것이라 ignoresMouseEvents 가 그대로 반영된다.
    AppKit 은 화면 왼쪽 **아래**가 원점이라 y 를 뒤집어 준다.
    """
    import AppKit
    h = AppKit.NSScreen.screens()[0].frame().size.height
    return AppKit.NSWindow.windowNumberAtPoint_belowWindowWithWindowNumber_(
        AppKit.NSMakePoint(x, h - y), 0)


def settle(root, x, y, want, tries=40):
    """바꾼 것이 창 서버에 반영될 때까지 이벤트 루프를 돌린다.

    그냥 기다리면 안 바뀐다 - **루프가 돌아야** 반영된다. 보통 20~30ms.
    """
    for _ in range(tries):
        root.update()
        if who_gets_the_click(x, y) == want:
            return True
    return False


def _nswin_number(win):
    from poketdesktop import platform_mac as M
    w = M.nswindow(win)
    return w.windowNumber() if w is not None else None


def main():
    if sys.platform != "darwin":
        print("맥에서만 하는 검사입니다.")
        return 0
    if not PLAT.NAME == "platform_mac":
        print("맥 구현이 안 잡혔습니다: %s" % PLAT.NAME)
        return 1

    from poketdesktop import platform_mac as M
    if not M.available():
        print("pyobjc 가 없습니다. pip install pyobjc-framework-Cocoa "
              "pyobjc-framework-Quartz")
        return 1
    if screen_locked():
        print("화면이 잠겨 있습니다. 이 검사는 화면에 실제로 그려진 것을")
        print("읽어서 보는 것이라, 잠금을 풀고 다시 돌려 주세요.")
        return 0

    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    print("고른 글꼴: %s" % U.FAMILY)

    # 몬스터볼 두 장 - 색빼기로 칠해 둔 평범한 RGB 그림이다.
    # (실제 도트도 sprites 가 같은 형태로 만든다.)
    red = effects.ball_image(SIZE, KEY, ball="POKEBALL")
    other = effects.ball_image(SIZE, KEY, ball="ULTRABALL")

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    bg = PLAT.transparent_window(win, "#%02x%02x%02x" % KEY)
    view = PLAT.SpriteView(win, bg, SIZE, SIZE)
    frames = view.frames([red, other], KEY)
    view.show(frames[0])
    win.geometry("+%d+%d" % (200, 200))
    PLAT.raise_above(win)

    print("-- 창이 투명하게 만들어졌는가")
    nsw = M.nswindow(win)
    chk("NSWindow 를 찾았다", nsw is not None)
    if nsw is None:
        return 1
    chk("불투명하지 않다", not nsw.isOpaque())
    chk("창 그림자가 꺼져 있다", not nsw.hasShadow())
    chk("항상 위에 있다", nsw.level() > 0, nsw.level())
    chk("CALayer 가 붙었다", view.layer is not None)

    out = {}

    def shot(tag, then):
        got = grab(nsw)
        out[tag] = got
        root.after(700, then)

    def step1():
        shot("first", step2)

    def step2():
        view.show(frames[1])
        root.after(700, lambda: shot("second", finish))

    def finish():
        root.quit()

    root.after(1200, step1)
    root.mainloop()

    print("-- 화면에 합성된 결과")
    first = out.get("first")
    chk("창을 찍었다", first is not None)
    if first:
        w, h, px, _info = first
        chk("찍힌 크기가 도트 크기와 맞다", w >= SIZE and h >= SIZE,
            "%dx%d" % (w, h))
        # 모서리는 도트가 없는 자리다. 투명해야 한다.
        corner = px(1, 1)
        chk("모서리가 투명하다 (네모난 판이 아니다)", corner[3] == 0, corner)
        # 가운데는 몬스터볼이다. 무언가 그려져 있어야 한다.
        mid = px(w // 2, h // 2)
        chk("가운데에 도트가 그려져 있다", mid[3] > 0, mid)
        # 위쪽 절반은 빨간 몬스터볼이다.
        top = px(w // 2, h // 4)
        chk("몬스터볼 위쪽이 빨갛다", top[0] > top[1] + 40 and top[0] > top[2] + 40,
            top)
        # 색빼기 색(자홍)이 그대로 남아 있으면 안 된다.
        magenta = [1 for y in range(h) for x in range(w)
                   if px(x, y)[3] > 200 and px(x, y)[0] > 200
                   and px(x, y)[2] > 200 and px(x, y)[1] < 60]
        chk("투명색(자홍)이 화면에 안 남는다", not magenta, len(magenta))

    second = out.get("second")
    if first and second:
        w, h, px1, _ = first
        _w2, _h2, px2, _ = second
        a = px1(w // 2, h // 4)
        b = px2(w // 2, h // 4)
        chk("프레임을 바꾸면 화면도 바뀐다 (애니메이션이 돈다)", a != b,
            "%s == %s" % (a, b))

    try:
        view.destroy()
        win.destroy()
    except Exception:                                       # noqa: BLE001
        pass

    real_pet(root)
    fx_layer_check(root)

    try:
        root.destroy()
    except Exception:                                       # noqa: BLE001
        pass

    print()
    print("=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
