# -*- coding: utf-8 -*-
"""동작이 바뀔 때 도트 둘레에 검은 테두리가 뜨지 않는가 — 진짜 Tk 로.

    python client/smoke_anim_resize.py [도감번호]

## 무엇을 잡는 검사인가

1.1.2 에서 동작이 여럿이 되면서(걷기 32x32, 아픔 48x56, 뛰기 32x80)
동작을 바꿀 때마다 창 크기가 달라졌다. 그림부터 걸면 Label 이 커지면서
창이 따라 커지는데, **새로 드러난 자리는 아직 아무도 안 칠했다.**
투명색 창(-transparentcolor)에서 그 자리는 투명색이 아니라 검게 합성되어,
도트 둘레에 검은 테두리가 깜빡였다 (1.1.6 에서 고침).

앞선 재현이 root.update() 로는 안 잡혔다 - 바로 그려 버려서다. 그래서
여기서는 **게임과 같은 리듬(root.after)** 으로 돌리고 그 사이를 촘촘히
집어온다. 그렇게 해야 나타난다.

흰 판을 깔고 그 위에서 재므로, 도트 자체의 검은 외곽선 말고는 검은 것이
나오면 안 된다. 고치기 전에는 1066, 고친 뒤에는 121(외곽선)이었다.
지어낸 시트로 돌리면 외곽선이 없어서 675 -> 0 이 된다.

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

X, Y, PAD = 420, 320, 120
SECONDS = 10
# 도트 외곽선만 남으면 이 아래다. 테두리가 뜨면 여덟 배로 튄다.
LIMIT = 400

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


# 지어낼 시트. (동작, 칸 너비, 칸 높이, 프레임 수).
# **칸 크기가 서로 달라야 한다** - 그래야 창이 커지고, 그때 이 버그가 난다.
FAKE = [("Walk", 32, 32, 4), ("Hurt", 48, 56, 2), ("Hop", 32, 80, 3)]
FAKE_NUM = 9999


def make_sheets():
    """검사용 시트를 지어 넣는다. 진짜 도트를 받아 두지 않아도 돌게.

    사용자의 캐시를 쓰지 않는다(POKET_HOME 이 임시 폴더다). 그래서 CI 처럼
    아무것도 안 받아 둔 곳에서도 이 검사가 실제로 돌아야 한다.
    """
    import json
    from PIL import Image, ImageDraw
    d = os.path.join(walk_cache.walk_dir(), "%04d" % FAKE_NUM)
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
    return FAKE_NUM


def main():
    num = int(sys.argv[1]) if len(sys.argv) > 1 else make_sheets()

    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    back = tk.Toplevel(root)
    back.overrideredirect(True)
    back.geometry("760x640+%d+%d" % (X - 220, Y - 220))
    back.configure(bg="#ffffff")
    back.attributes("-topmost", True)
    for _ in range(10):
        root.update()

    ov = overlay.Overlay(root, dict(config.DEFAULTS))
    ov.walks[num] = walk_cache.local(num, "Walk")
    names = ("Hurt", "Hop", "Idle", "Sleep", "Sit", "Laying", "Wake")
    # 지어낸 시트는 Walk/Hurt/Hop 셋뿐이다. 나머지는 (None, None) 이라
    # anim_for 가 "이 종에 그 동작이 없다" 로 넘긴다 - 진짜와 같은 길이다.
    for a in names:
        ov.sheets[(num, a)] = walk_cache.local(num, a)

    pet = ov.make({"id": 1, "num": num, "shiny": False,
                   "info": {"species": "검사", "level": 20, "types": []}})
    if pet is None:
        print("도트를 못 만들었습니다:", num)
        return 1
    ov.pets[1] = pet
    pet.x, pet.y = X, Y
    pet.battling = True                 # 자리를 고정한다
    pet.place()

    have = [a for a in names if pet.anim_for(a) is not None]
    sizes = set()
    for a in ["Walk"] + have:
        an = pet.anim_for(a)
        if an is not None:
            sizes.add((an.w, an.h))
    print("#%04d  동작 %d개  창 크기 %d가지" % (num, len(have) + 1, len(sizes)))
    chk("칸 크기가 다른 동작이 있다 (검사 전제)", len(sizes) > 1, sorted(sizes))

    box = (X - PAD, Y - PAD, X + 220 + PAD, Y + 220 + PAD)
    state = {"i": 0, "worst": 0, "when": "", "shots": 0, "seen": 0,
         "stop": False}

    def grab():
        if state["stop"]:
            return
        im = ImageGrab.grab(bbox=box).convert("RGB")
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
            state["when"] = pet.anim_name
        root.after(1, grab)

    def switch():
        if state["stop"]:
            return
        if have:
            a = have[state["i"] % len(have)]
            state["i"] += 1
            if not pet.play(a):
                pet.play("Walk")
        root.after(240, back_to_walk)

    def back_to_walk():
        if state["stop"]:
            return
        pet.play("Walk")
        root.after(240, switch)

    def tick():
        if state["stop"]:
            return
        try:
            pet.update(33)
        except Exception:                                    # noqa: BLE001
            pass
        root.after(33, tick)

    def stop():
        state["stop"] = True
        root.quit()

    root.after(50, tick)
    root.after(120, switch)
    root.after(200, grab)
    root.after(SECONDS * 1000, stop)
    root.mainloop()

    print("  %d장 집어옴 · 도트 %d칸 보임 · 가장 검은 값 %d (동작 %s)"
          % (state["shots"], state["seen"], state["worst"], state["when"]))
    # **도트를 못 봤으면 검은 값이 0인 것은 아무 뜻도 없다.** 화면을 못
    # 집어오는 곳에서 이 검사가 조용히 통과해 버리는 것을 막는다.
    chk("도트를 화면에서 봤다 (검사 전제)", state["seen"] > 0, state["seen"])
    chk("충분히 집어왔다 (검사 전제)", state["shots"] > 40, state["shots"])
    chk("동작을 여러 번 바꿨다 (검사 전제)", state["i"] >= 3, state["i"])
    chk("도트 둘레에 검은 테두리가 없다", state["worst"] < LIMIT, state["worst"])

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
