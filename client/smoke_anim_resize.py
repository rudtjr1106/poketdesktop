# -*- coding: utf-8 -*-
"""도트 둘레에 검은 네모가 뜨지 않는가 — 진짜 Tk 로.

    python client/smoke_anim_resize.py

## 무엇을 잡는 검사인가

윈도우의 투명색 창(-transparentcolor)은 **크기가 바뀌는 순간** 한 프레임
동안 통째로 검게 합성된다. 도트 둘레가 아니라 창 전체가 검은 네모로
번쩍인다. 1.1.2 에서 동작이 여럿이 되면서(걷기 32x32, 아픔 48x56,
뛰기 32x80) 동작을 바꿀 때마다 창 크기가 달라져 그 일이 났다.

**반투명 창(-alpha)이 그 위에 겹쳐도 같은 일이 난다.** 이름표가 도트
창 위쪽 8픽셀을 덮고 있어서 그 띠가 검게 나왔다.

세 마리를 20초 굴리며 동작을 77번 바꿔 재 보면 이랬다.

    창 크기가 안 바뀌면        검은 장수 0 / 731
    커지기만 하면              검은 장수 2 / 847
    매번 그 크기로 바꾸면       검은 장수 2 / 812
    이름표가 겹치면            검은 덩어리 920개

그래서 세 가지를 본다.
  1. 흰 판 위에서 검은 것이 안 나오는가
  2. 창 크기가 만든 뒤로 **한 번도 안 바뀌는가** (평생 한 크기)
  3. 이름표가 도트 창을 **한 픽셀도 안 덮는가**

**여러 마리로 돌려야 한다.** 한 마리로는 안 잡힌다 - 1.1.6 의 검사가
한 마리였고, 그래서 이 결함을 통과시켰다.

**윈도우 검사다.** 맥은 platform_mac.py 에 SpriteView 를 따로 갖고 있어
투명색 창을 안 쓰므로 이 결함이 날 수가 없다. CI 도 윈도우 잡에서만
돌린다 - 맥 러너는 화면을 집어오는 게 느려 촘촘히 못 본다.
"""
import os
import sys
import tempfile
import tkinter as tk

os.environ.setdefault("POKET_HOME",
                      os.path.join(tempfile.gettempdir(), "poket-smoke-anim"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from PIL import ImageGrab                                    # noqa: E402

from poketdesktop import config, overlay, walk_cache         # noqa: E402
from poketdesktop import platform_os as PLAT                 # noqa: E402
from poketdesktop import ui_common as U                      # noqa: E402

SECONDS = 12
# 지어낸 도트에는 검은 외곽선이 없어서 멀쩡하면 0 이다. 창이 검게
# 번쩍이면 수백으로 튄다. 다만 번쩍임은 짧아서 집어오는 사이로 빠져
# 나가기도 한다 - 그래서 위의 구조 검사(창 크기·이름표)가 본체다.
LIMIT = 150
BOX = (300, 200, 900, 700)

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


# 지어낼 시트. (동작, 칸 너비, 칸 높이, 프레임 수).
# **칸 크기가 서로 달라야 한다** - 그래야 옛날 판에서 창이 커졌다 작아졌다
# 하면서 이 결함이 난다.
FAKE = [("Walk", 32, 32, 4), ("Idle", 40, 36, 3), ("Hurt", 48, 56, 2),
        ("Hop", 32, 80, 3), ("Sit", 44, 40, 2), ("Sleep", 52, 30, 2),
        ("Wake", 36, 64, 3), ("Laying", 60, 28, 2)]
NUMS = [9998, 9999]
ACTS = [a for a, _w, _h, _n in FAKE if a != "Walk"]


def make_sheets(num):
    """검사용 시트를 지어 넣는다. 진짜 도트를 받아 두지 않아도 돌게.

    사용자의 캐시를 쓰지 않는다(POKET_HOME 이 임시 폴더다). 그래서 CI 처럼
    아무것도 안 받아 둔 곳에서도 이 검사가 실제로 돌아야 한다.
    """
    import json

    from PIL import Image, ImageDraw

    d = os.path.join(walk_cache.walk_dir(), "%04d" % num)
    os.makedirs(d, exist_ok=True)
    for name, fw, fh, n in FAKE:
        rows = 8
        im = Image.new("RGBA", (fw * n, fh * rows), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        for r in range(rows):
            for i in range(n):
                x, y = i * fw + fw // 4, r * fh + fh // 4
                # 가운데에 색 덩어리 하나. 둘레는 투명하게 남긴다 -
                # 그 투명한 자리가 창에서 뚫려야 하는 곳이다.
                dr.ellipse([x, y, x + fw // 2, y + fh // 2],
                           fill=(40 + r * 20, 90, 200, 255))
        im.save(os.path.join(d, "%s.png" % name))
        meta = {"ok": True, "frameW": fw, "frameH": fh, "rows": rows,
                "frames": n, "durations": [8] * n, "anim": name,
                "rowmap": {"down": 0, "downright": 1, "right": 2,
                           "upright": 3, "up": 4, "upleft": 5,
                           "left": 6, "downleft": 7}}
        with open(os.path.join(d, "%s.json" % name), "w",
                  encoding="utf-8") as f:
            json.dump(meta, f)


def main():
    for n in NUMS:
        make_sheets(n)

    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)

    # 흰 판을 깔고 그 위에서 잰다. 검은 것이 나오면 전부 결함이다.
    back = tk.Toplevel(root)
    back.overrideredirect(True)
    back.geometry("600x500+300+200")
    back.configure(bg="#ffffff")
    back.attributes("-topmost", True)
    for _ in range(10):
        root.update()

    st = dict(config.DEFAULTS)
    st["showNames"] = True                  # **이름표를 켜고 본다**
    ov = overlay.Overlay(root, st)
    ov.area = lambda: (320, 220, 880, 680)

    pets = []
    for i, num in enumerate(NUMS):
        ov.walks[num] = walk_cache.local(num, "Walk")
        for a, _w, _h, _n in FAKE:
            ov.sheets[(num, a)] = walk_cache.local(num, a)
        p = ov.make({"id": i + 1, "num": num, "shiny": False,
                     "info": {"species": "검사%d" % (i + 1),
                              "name": "검사%d" % (i + 1),
                              "level": 5, "types": []}})
        if p is None:
            print("도트를 못 만들었습니다:", num)
            return 1
        ov.pets[i + 1] = p
        p.battling = True                   # 자리는 검사가 정한다
        p.x, p.y = 400 + i * 200, 300 + i * 150
        p.place()
        pets.append(p)
    for _ in range(20):
        root.update()

    have = [a for a in ACTS if pets[0].anim_for(a) is not None]
    sizes = set()
    for a in ["Walk"] + have:
        an = pets[0].anim_for(a)
        if an is not None:
            sizes.add((an.w, an.h))
    print("도트 %d마리 · 동작 %d개 · 도트 크기 %d가지"
          % (len(pets), len(have) + 1, len(sizes)))
    chk("칸 크기가 다른 동작이 있다 (검사 전제)", len(sizes) > 1, sorted(sizes))
    chk("두 마리 이상이다 (검사 전제)", len(pets) >= 2, len(pets))

    state = {"i": 0, "worst": 0, "when": "", "shots": 0, "seen": 0,
             "stop": False, "bad": 0}
    # 창 크기는 만든 뒤로 안 바뀌어야 한다. 처음 것을 적어 둔다.
    first = [(p.win.winfo_width(), p.win.winfo_height()) for p in pets]
    grew = []
    overlaps = []

    def grab():
        if state["stop"]:
            return
        im = ImageGrab.grab(bbox=BOX).convert("RGB")
        px = im.load()
        n = seen = 0
        for yy in range(0, im.height, 2):
            for xx in range(0, im.width, 2):
                r, g, b = px[xx, yy]
                if r < 50 and g < 50 and b < 50:
                    n += 1
                elif b > 150 and r < 150 and g < 150:
                    seen += 1          # 지어낸 도트의 파란 덩어리
        state["shots"] += 1
        if seen > state["seen"]:
            state["seen"] = seen
        if n > state["worst"]:
            state["worst"] = n
            state["when"] = pets[0].anim_name
        root.after(1, grab)

    def watch():
        """창 크기와 이름표 자리를 계속 지켜본다."""
        if state["stop"]:
            return
        for i, p in enumerate(pets):
            now = (p.win.winfo_width(), p.win.winfo_height())
            if now != first[i] and (i, now) not in grew:
                grew.append((i, now))
            if p.name_win:
                nb = p.name_win.winfo_rooty() + p.name_win.winfo_height()
                top = p.win.winfo_rooty()
                if nb > top and (i, nb - top) not in overlaps:
                    overlaps.append((i, nb - top))
        root.after(20, watch)

    def switch():
        if state["stop"]:
            return
        p = pets[state["i"] % len(pets)]
        a = have[(state["i"] // len(pets)) % len(have)] if have else "Walk"
        state["i"] += 1
        if not p.play(a, once=(state["i"] % 3 == 0)):
            p.play("Walk")
        root.after(120, switch)

    def tick():
        if state["stop"]:
            return
        for p in pets:
            try:
                p.update(33)
            except Exception:                                # noqa: BLE001
                pass
        root.after(33, tick)

    def stop():
        state["stop"] = True
        root.quit()

    root.after(50, tick)
    root.after(100, watch)
    root.after(120, switch)
    root.after(200, grab)
    root.after(SECONDS * 1000, stop)
    root.mainloop()

    print("  %d장 집어옴 · 도트 %d칸 보임 · 가장 검은 값 %d (동작 %s)"
          % (state["shots"], state["seen"], state["worst"], state["when"]))
    print("  창 크기 %s · 동작 %d번 바꿈" % (first, state["i"]))
    # **도트를 못 봤으면 검은 값이 0인 것은 아무 뜻도 없다.** 화면을 못
    # 집어오는 곳에서 이 검사가 조용히 통과해 버리는 것을 막는다.
    chk("도트를 화면에서 봤다 (검사 전제)", state["seen"] > 0, state["seen"])
    chk("충분히 집어왔다 (검사 전제)", state["shots"] > 40, state["shots"])
    chk("동작을 여러 번 바꿨다 (검사 전제)", state["i"] >= 6, state["i"])
    chk("창 크기가 한 번도 안 바뀐다", not grew, grew)
    chk("이름표가 도트 창을 안 덮는다", not overlaps, overlaps)
    chk("검은 네모가 안 뜬다", state["worst"] < LIMIT, state["worst"])

    try:
        root.destroy()
    except tk.TclError:
        pass
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
