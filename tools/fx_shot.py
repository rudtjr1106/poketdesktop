# -*- coding: utf-8 -*-
"""기술 연출을 **진짜 창에서** 틀어 그 순간을 떠 온다 (맥 전용) — 흉내 낸 그림이 아니라 화면에 뜬 그대로.

    .venv/bin/python tools/fx_shot.py 결과.png raster 파괴광선:1050 화염방사:430 지진:560
    .venv/bin/python tools/fx_shot.py 결과.png shape  파괴광선:1050              # 도형 바탕으로

    둘째 인자   raster (그림 바탕) / shape (도형 바탕) / pixel (그림 바탕, 도트풍)
    기술:ms     그 기술을 틀고 ms 뒤의 화면을 뜬다. 여러 개를 주면 세 칸씩 이어 붙인다 (무대 부분만).
    SHOT=--light 환경 변수를 주면 밝은 배경(풀밭).

미리보기 창(tools/fx_gallery.py)을 띄워 틀고, 창 서버에서 **내 프로세스의 창**을 뜬다
(Quartz.CGWindowListCreateImage 에 내 창 번호 - 내 창은 화면 캡처 권한이 없어도 떠진다). 레이어(CALayer)로 올린
그림 바탕도 같이 찍힌다. 창이 잠깐 화면에 뜬다. tools/fx_preview.py 의 그림은 PIL 이 흉내 낸 것이라 도형 바탕의
가장자리가 진짜보다 매끈하다 - 확인은 이것으로 한다.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "client"))
os.chdir(ROOT)
import fx_gallery as G
from poketdesktop import battle_fx as FX, platform_mac as PM
import Quartz
from PIL import Image
FX.DEBUG = True
out = sys.argv[1]; mode = sys.argv[2]
todo = [(a.split(":")[0], int(a.split(":")[1])) for a in sys.argv[3:]]
app = G.App()
app.stage.fx_raster = None if mode == "shape" else ({"pixel": True} if mode == "pixel" else {})
if "--light" in os.environ.get("SHOT", ""):
    app.v["bg"].set("풀밭"); app.redraw()
app.root.update()
shots = []

def grab(name):
    nsw = PM.nswindow(app.root)
    cg = Quartz.CGWindowListCreateImage(Quartz.CGRectNull, Quartz.kCGWindowListOptionIncludingWindow, nsw.windowNumber(), Quartz.kCGWindowImageBoundsIgnoreFraming)
    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(cg))
    iw, ih, bpr = Quartz.CGImageGetWidth(cg), Quartz.CGImageGetHeight(cg), Quartz.CGImageGetBytesPerRow(cg)
    im = Image.frombuffer("RGBA", (iw, ih), bytes(data), "raw", "BGRA", bpr, 1).convert("RGB")
    sc = iw / float(app.root.winfo_width())
    title = ih - app.root.winfo_height() * sc
    x = (app.cv.winfo_rootx() - app.root.winfo_rootx()) * sc; y = (app.cv.winfo_rooty() - app.root.winfo_rooty()) * sc + title
    shots.append((name, im.crop((int(x), int(y), int(x + G.W * sc), int(y + G.H * sc)))))

def step():
    if app.fx is not None:
        return app.root.after(30, step)
    if not todo:
        w, h = 620, int(620 * G.H / G.W)
        cols = 3; rows = (len(shots) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * w, rows * h), (10, 12, 18))
        for i, (n, im) in enumerate(shots):
            sheet.paste(im.resize((w, h), Image.LANCZOS), ((i % cols) * w, (i // cols) * h))
        sheet.save(out); print("SHOTS", len(shots), [n for n, _ in shots], flush=True)
        return app.root.destroy()
    name, at = todo.pop(0)
    app.play(app.moves[name])
    app.root.after(at, lambda: grab(name))
    app.root.after(at + 60, step)
app.root.after(300, step)
app.root.mainloop()
