# -*- coding: utf-8 -*-
"""이로치 색 고르기 — 도트 색조·캐시·바탕화면·고르기 창 검사 (1.8.0).

    python client/test_tint_ui.py
    python client/run_as_windows.py client/test_tint_ui.py

**창을 진짜로 띄운다.** 도트는 서버 없이 여기서 그린다 (기본 = 빨강,
이로치 = 파랑). 값의 규칙과 서버 쪽은 server/test_tint.py 가 본다.

## 무엇을 못 박나

  1. 색조 돌리기: 색이 바뀌고, 투명한 곳과 무채색(검은 테두리)은 그대로다.
     움직이는 도트는 장수와 박자가 그대로 남는다.
  2. 배틀 도트 캐시: "s090" 은 이로치 도트에서, "n090" 은 기본 도트에서 만든다.
     한 번 만들면 다시 안 만든다. 이로치 도트를 못 받아 기본이 대신 왔으면
     색을 입히지 않는다 (틀린 색을 파일로 굳히지 않는다).
  3. 걷는 도트 캐시: 색마다 옆 폴더에 따로 둔다. 열쇠가 색마다 다르다.
  4. 바탕화면: 고른 색의 도트로 선다. 동기화로 색이 바뀌면 **같은 창에서**
     갈아 입는다. '기본 색' 이면 기본 도트다 (그래도 이름표의 ★ 는 남는다).
  5. 고르기 창: 16칸, 지금 색에 표시, 누르면 고른 표시만 바뀌고 '이 색으로' 를
     눌러야 서버에 간다. 실패하면 창에 까닭이 남는다. 눌린 글자가 없다.
  6. 포켓몬 관리 창의 '색 고르기' 단추는 이로치일 때만 눌린다.
"""
import colorsys
import json
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-tint-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

import smoke_box_filter as SB                               # noqa: E402
from common import pokelogic as P                           # noqa: E402
from common import tint as T                                # noqa: E402
from poketdesktop import config, overlay, sprites           # noqa: E402
from poketdesktop import sprite_cache, sprite_tint          # noqa: E402
from poketdesktop import ui_box, ui_tint, walk_cache        # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop.app import App                            # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0
HOME = os.environ["POKET_HOME"]
RED, BLUE, BLACK = (220, 40, 40), (40, 60, 220), (16, 16, 16)
NUM = 6


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def wait(root, cond, sec=6.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.01)
    return cond()


def settle(root, sec=0.15):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def hue_of(rgb):
    return round(colorsys.rgb_to_hsv(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)[0] * 360)


def near(a, b, tol=14):
    d = abs(a - b) % 360
    return min(d, 360 - d) <= tol


# ---------------------------------------------------------------- 재료
def gif_bytes(color):
    """두 장짜리 배틀 도트. 몸통 색 + 검은 테두리 한 줄."""
    frames = []
    for dx in (0, 3):
        im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        im.paste(Image.new("RGBA", (18, 24), BLACK + (255,)), (10 + dx, 8))
        im.paste(Image.new("RGBA", (14, 20), color + (255,)), (12 + dx, 10))
        frames.append(im)
    p = os.path.join(HOME, "tmp.gif")
    frames[0].save(p, save_all=True, append_images=frames[1:], duration=[90, 130],
                   loop=0, disposal=2)
    with open(p, "rb") as f:
        return f.read()


def sheet_bytes(color, cell=32):
    im = Image.new("RGBA", (cell * 2, cell * 8), (0, 0, 0, 0))
    for row in range(8):
        for col in range(2):
            im.paste(Image.new("RGBA", (cell // 2, cell - 10), color + (255,)),
                     (col * cell + cell // 4, row * cell + 5))
    p = os.path.join(HOME, "tmp.png")
    im.save(p)
    with open(p, "rb") as f:
        return f.read()


META = {"ok": True, "frameW": 32, "frameH": 32, "durations": [8, 8]}


class FakeApi(object):
    """도트 서버 노릇. 이로치를 못 주는 때(shiny_ok=False)도 흉내 낸다."""

    def __init__(self):
        self.shiny_ok = True
        self.calls = []
        self.fail = None

    def sprite(self, num, shiny=False):
        self.calls.append(("sprite", num, bool(shiny)))
        if shiny and not self.shiny_ok:
            return None, None
        return gif_bytes(BLUE if shiny else RED), ".gif"

    def anim_meta(self, num, name="Walk", shiny=False):
        if name != "Walk" or (shiny and not self.shiny_ok):
            return {"ok": False}
        return dict(META, shiny=bool(shiny))

    def anim_sheet(self, num, name="Walk", shiny=False):
        self.calls.append(("sheet", num, bool(shiny)))
        return sheet_bytes(BLUE if shiny else RED)

    def set_tint(self, pid, tint):
        self.calls.append(("tint", pid, tint))
        if self.fail:
            e = Exception(self.fail)
            e.message = self.fail
            raise e
        return {"ok": True, "pokemon": {"id": pid, "tint": tint, "shiny": True}}


def body_color(path, frame=0):
    """그림 한가운데(몸통)의 색."""
    frames, _d = sprites.read_frames(path)
    im = frames[frame]
    bb = im.getbbox()
    return im.getpixel(((bb[0] + bb[2]) // 2, (bb[1] + bb[3]) // 2))[:3]


def pet_color(pet):
    """바탕화면 도트가 지금 입은 그림의 몸통 색."""
    anim = pet.anim
    fr = next(iter(anim.frames.values()))[0]
    rgba = sprites.to_rgba(fr, anim.key)
    bb = rgba.getbbox()
    return rgba.getpixel(((bb[0] + bb[2]) // 2, (bb[1] + bb[3]) // 2))[:3]


def mon(pid, shiny=True, tint=None, name="리자몽"):
    return {"id": pid, "num": NUM, "species": "CHARIZARD", "shiny": shiny, "tint": tint,
            "info": {"name": name, "species": "리자몽", "level": 50, "types": []}}


# ---------------------------------------------------------------- 1. 색조
def shift_part():
    print("=== 색조 돌리기 ===")
    im = Image.new("RGBA", (4, 1), (0, 0, 0, 0))
    im.putpixel((0, 0), RED + (255,))
    im.putpixel((1, 0), BLACK + (255,))
    im.putpixel((2, 0), (255, 255, 255, 255))
    out = sprite_tint.shift(im, 90)
    chk("색이 90도 돈다", near(hue_of(out.getpixel((0, 0))[:3]), hue_of(RED) + 90),
        out.getpixel((0, 0)))
    chk("검은 테두리는 그대로", max(abs(a - b) for a, b in zip(out.getpixel((1, 0))[:3], BLACK)) <= 3,
        out.getpixel((1, 0)))
    chk("흰색도 그대로", min(out.getpixel((2, 0))[:3]) >= 250, out.getpixel((2, 0)))
    chk("투명한 곳은 투명하다", out.getpixel((3, 0))[3] == 0 and out.getpixel((0, 0))[3] == 255)
    chk("0도면 그대로", sprite_tint.shift(im, 0).getpixel((0, 0))[:3] == RED)

    src = os.path.join(HOME, "src.gif")
    with open(src, "wb") as f:
        f.write(gif_bytes(RED))
    dst = os.path.join(HOME, "out", "dst.png")
    chk("움직이는 도트를 만든다 (없는 폴더도 만든다)", sprite_tint.make(src, dst, 180)
        and os.path.exists(dst))
    f0, d0 = sprites.read_frames(src)
    f1, d1 = sprites.read_frames(dst)
    chk("  장수와 박자가 그대로", len(f1) == len(f0) == 2 and d1 == d0, (len(f1), d1, d0))
    chk("  둘째 장도 움직인 자리 그대로", f1[1].getbbox() == f0[1].getbbox(),
        (f1[1].getbbox(), f0[1].getbbox()))
    chk("  색이 180도 돌았다", near(hue_of(body_color(dst)), hue_of(RED) + 180), body_color(dst))
    chk("없는 파일은 False (예외를 안 낸다)", sprite_tint.make(src + ".x", dst + ".y", 90) is False
        and not os.path.exists(dst + ".y.part"))


# ---------------------------------------------------------------- 2·3. 캐시
def cache_part(api):
    print("\n=== 배틀 도트 캐시 ===")
    p = sprite_cache.ensure(api, NUM, "s090")
    chk("이로치 도트에서 만든다", p and os.path.basename(p) == "0006s-h090.png", p)
    chk("  파랑에서 90도 돈 색", near(hue_of(body_color(p)), hue_of(BLUE) + 90), body_color(p))
    n = len(api.calls)
    chk("두 번째는 만들어 둔 것을 준다 (서버에 안 묻는다)",
        sprite_cache.ensure(api, NUM, "s090") == p and len(api.calls) == n)
    q = sprite_cache.ensure(api, NUM, "n090")
    chk("기본 도트에서 만든다", q and os.path.basename(q) == "0006-h090.png"
        and near(hue_of(body_color(q)), hue_of(RED) + 90), (q, body_color(q)))
    chk("'기본 색' 은 기본 도트 그대로", sprite_cache.ensure(api, NUM, T.skin(mon(1, True, "normal")))
        == sprite_cache.find_local(NUM, False))
    chk("안 골랐으면 이로치 도트 그대로", sprite_cache.ensure(api, NUM, T.skin(mon(1, True)))
        == sprite_cache.find_local(NUM, True))
    got = sprite_cache.ensure_many(api, [(NUM, "s090"), (NUM, True), (NUM, False)])
    chk("여러 개 받기의 열쇠가 색마다 다르다", set(got) == {(NUM, "s090"), (NUM, True), (NUM, False)}
        and len(set(got.values())) == 3, got)

    api.shiny_ok = False
    r = sprite_cache.ensure(api, 7, "s135")
    chk("이로치 도트를 못 받으면 기본 도트를 그대로 준다 (색을 안 입힌다)",
        r and os.path.basename(r) == "0007.gif", r)
    chk("  틀린 색을 파일로 굳히지 않는다", sprite_cache.find_local(7, "s135") is None)
    api.shiny_ok = True

    print("\n=== 걷는 도트 캐시 ===")
    chk("열쇠: 기본은 번호, 이로치는 (번호, True), 고른 색은 (번호, 값)",
        walk_cache.key(NUM, False) == NUM and walk_cache.key(NUM, True) == (NUM, True)
        and walk_cache.key(NUM, "s090") == (NUM, "s090")
        and walk_cache.key(NUM, "normal") == NUM, "")
    chk("동작 시트의 열쇠도", walk_cache.sheet_key(NUM, "Idle", "n045") == (NUM, "Idle", "n045")
        and walk_cache.sheet_key(NUM, "Idle") == (NUM, "Idle"))
    sheet, meta = walk_cache.ensure(api, NUM, "Walk", "s090")
    chk("색마다 옆 폴더에 둔다", sheet and sheet.replace(os.sep, "/").endswith("0006s-h090/Walk.png")
        and meta and meta.get("ok"), sheet)
    chk("  자르는 값(meta)도 같이 둔다", os.path.exists(os.path.join(os.path.dirname(sheet), "Walk.json")))
    im = Image.open(sheet).convert("RGBA")
    chk("  파랑에서 90도 돈 색", near(hue_of(im.getpixel((12, 12))[:3]), hue_of(BLUE) + 90),
        im.getpixel((12, 12)))
    n = len(api.calls)
    chk("두 번째는 받아 둔 것", walk_cache.ensure(api, NUM, "Walk", "s090")[0] == sheet
        and len(api.calls) == n)
    many = walk_cache.ensure_many(api, [(NUM, "s090"), (NUM, "n090"), (NUM, True), (NUM, False)])
    chk("여러 개 받기", set(many) == {(NUM, "s090"), (NUM, "n090"), (NUM, True), NUM}
        and all(v[0] for v in many.values()), list(many))
    api.shiny_ok = False
    s2, m2 = walk_cache.ensure(api, 8, "Walk", "s090")
    chk("이로치 시트가 없는 종은 기본 시트로 걷는다 (색을 안 입힌다)",
        s2 and s2.replace(os.sep, "/").endswith("0008/Walk.png"), s2)
    api.shiny_ok = True


# ---------------------------------------------------------------- 4. 바탕화면
def fetch(api, mons):
    want = [(m["num"], T.skin(m)) for m in mons]
    return sprite_cache.ensure_many(api, want), walk_cache.ensure_many(api, want)


def overlay_part(root, api):
    print("\n=== 바탕화면 ===")
    settings = dict(config.DEFAULTS)
    settings["showNames"] = True
    ov = overlay.Overlay(root, settings)
    a, b, c = mon(1, True, "s090", "색조"), mon(2, True, None, "이로치"), mon(3, False, None, "보통")
    paths, walks = fetch(api, [a, b, c])
    ov.sync([a, b, c], paths, walks)
    settle(root)
    pa, pb, pc = ov.pets[1], ov.pets[2], ov.pets[3]
    chk("고른 색의 도트로 선다", near(hue_of(pet_color(pa)), hue_of(BLUE) + 90), pet_color(pa))
    chk("  걷는 도트다 (배틀 도트로 굳지 않는다)", isinstance(pa.anim, sprites.WalkAnimation))
    chk("안 고른 이로치는 이로치 색", near(hue_of(pet_color(pb)), hue_of(BLUE)), pet_color(pb))
    chk("이로치가 아니면 기본 색", near(hue_of(pet_color(pc)), hue_of(RED)), pet_color(pc))
    chk("지금 입은 색을 기억한다", (pa.skin, pb.skin, pc.skin) == ("s090", True, False),
        (pa.skin, pb.skin, pc.skin))

    b2 = dict(b, tint="n180")
    paths, walks = fetch(api, [a, b2, c])
    ov.sync([a, b2, c], paths, walks)
    settle(root)
    chk("동기화로 색이 바뀌면 갈아 입는다", near(hue_of(pet_color(pb)), hue_of(RED) + 180)
        and pb.skin == "n180", (pet_color(pb), pb.skin))
    chk("  같은 창을 그대로 쓴다", ov.pets[2] is pb)
    chk("  이름표의 ★ 는 남는다 (여전히 이로치다)", "★" in pb.nameplate_text(), pb.nameplate_text())
    b3 = dict(b, tint="normal")
    paths, walks = fetch(api, [a, b3, c])
    ov.sync([a, b3, c], paths, walks)
    settle(root)
    chk("'기본 색' 이면 기본 도트", near(hue_of(pet_color(pb)), hue_of(RED)) and pb.skin is False,
        (pet_color(pb), pb.skin))
    chk("  그래도 ★", "★" in pb.nameplate_text())
    b4 = dict(b, tint=None)
    paths, walks = fetch(api, [a, b4, c])
    ov.sync([a, b4, c], paths, walks)
    settle(root)
    chk("되돌리면 이로치 색", near(hue_of(pet_color(pb)), hue_of(BLUE)) and pb.skin is True,
        (pet_color(pb), pb.skin))
    before = pet_color(pa)
    ov.sync([a, b4, c], {})
    chk("색이 그대로면 손대지 않는다", pet_color(pa) == before and ov.pets[1] is pa)
    ov.refresh_visuals()
    settle(root)
    chk("크기를 바꿔도 (전부 다시 만들어도) 고른 색", near(hue_of(pet_color(ov.pets[1])),
                                              hue_of(BLUE) + 90), pet_color(ov.pets[1]))
    return ov


# ---------------------------------------------------------------- 5. 고르기 창
class MiniApp(object):
    open_tint = App.open_tint

    def __init__(self, root, api, ov=None):
        self.root = root
        self.api = api
        self.overlay = ov
        self.arena = None
        self.battle = None
        self.box_window = None
        self.synced = 0

    def request_sync(self):
        self.synced += 1


def picker_part(root, api):
    print("\n=== 고르기 창 ===")
    app = MiniApp(root, api)
    m = mon(9, True, "s090", "불꽃이")
    done = []
    w = ui_tint.TintPicker(app, m, on_done=lambda p: done.append(p))
    chk("16칸 (이로치 계열 8 + 기본 계열 8)", len(w.cells) == 16
        and None in w.cells and "normal" in w.cells, sorted(map(str, w.cells)))
    chk("미리보기가 뜬다", wait(root, lambda: len(w.photos) == 16), len(w.photos))
    settle(root, 0.2)
    t = texts(w.win)
    chk("누구의 색인지, 남에게도 보인다는 것을 알린다",
        any("불꽃이" in x for x in t) and any("상대" in x for x in t), t[:6])
    bad = squeezed(w.win)
    chk("눌린 위젯이 없다", not bad, bad[:3])
    chk("지금 색(s090)이 골라져 있다", w.picked == "s090"
        and w.cells["s090"][0].cget("highlightbackground") == U.ACCENT)
    chk("  바꾼 것이 없으면 '이 색으로' 는 안 눌린다", w.ok_btn.enabled is False)
    n = len(api.calls)
    w.cells["n135"][1].event_generate("<Button-1>")
    root.update()
    chk("칸을 누르면 고른 표시만 바뀐다", w.picked == "n135"
        and w.cells["n135"][0].cget("highlightbackground") == U.ACCENT
        and w.cells["s090"][0].cget("highlightbackground") != U.ACCENT)
    chk("  이제 '이 색으로' 가 눌린다", w.ok_btn.enabled is True)
    chk("  아직 서버에 안 간다", len(api.calls) == n and not done)

    api.fail = "이로치 포켓몬만 색을 고를 수 있습니다."
    w.apply()
    chk("실패하면 창에 까닭이 남는다", wait(root, lambda: "이로치" in w.status.cget("text")),
        w.status.cget("text"))
    chk("  창은 그대로, 끝났다고 알리지 않는다", w.alive and not done)
    api.fail = None
    w.apply()
    chk("'이 색으로' 를 누르면 서버에 간다", wait(root, lambda: done) and api.calls[-1] == ("tint", 9, "n135"),
        api.calls[-1])
    chk("  창이 닫힌다", not w.alive)
    chk("  손에 든 포켓몬 값도 바뀐다", m["tint"] == "n135")

    print("\n=== 이로치 색으로 되돌리기 ===")
    done[:] = []
    w = ui_tint.TintPicker(app, m, on_done=lambda p: done.append(p))
    wait(root, lambda: len(w.photos) == 16)
    w.pick(None)
    w.apply()
    chk("맨 앞 칸(이로치 색)은 None 을 보낸다", wait(root, lambda: done)
        and api.calls[-1] == ("tint", 9, None), api.calls[-1])

    print("\n=== 바탕화면 우클릭에서 ===")
    class Pet(object):
        pass
    pet = Pet()
    pet.mon, pet.id = mon(9, True, None), 9
    before = set(root.winfo_children())
    app.open_tint(pet)
    root.update()
    new = [c for c in root.winfo_children() if c not in before]
    chk("창이 열린다", len(new) == 1, new)
    for c in new:
        c.destroy()
    pet.mon = mon(9, False)
    before = set(root.winfo_children())
    app.open_tint(pet)
    chk("이로치가 아니면 안 열린다", set(root.winfo_children()) == before)
    pet.mon = mon(9, True)
    app.battle = object()
    app.open_tint(pet)
    chk("배틀 중에는 안 열린다", set(root.winfo_children()) == before)
    app.battle = None


# ---------------------------------------------------------------- 6. 관리 창
def box_part(root):
    print("\n=== 포켓몬 관리 창의 단추 ===")
    with open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    plain, shiny = SB.mon(dex, 4, 1, on=True), SB.mon(dex, 6, 2, on=True)
    shiny["shiny"] = True
    shiny["info"]["shiny"] = True
    app = SB.FakeApp(root, dex, [plain, shiny])
    win = ui_box.BoxWindow(root, app)
    SB.wait_for(root, lambda: getattr(win, "mons", None))
    SB.settle_rows(root, win)
    chk("단추가 있다", "색 고르기" in texts(win.win), texts(win.win)[-12:])
    win.select(1)
    root.update()
    chk("이로치가 아니면 안 눌린다", win.btn_tint.enabled is False)
    win.select(2)
    root.update()
    chk("이로치면 눌린다", win.btn_tint.enabled is True)
    bad = squeezed(win.btn_tint.holder.master)
    chk("바닥 줄에 눌린 위젯이 없다 (단추를 하나 더 넣었다)", not bad, bad[:3])
    before = set(win.win.winfo_children())
    win.do_tint()
    root.update()
    new = [c for c in win.win.winfo_children() if c not in before]
    chk("누르면 고르기 창이 열린다", len(new) == 1, new)
    for c in new:
        c.destroy()
    win.close()
    root.update()


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-500:])
    root.report_callback_exception = on_err
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)" % (U.FAMILY, U.FONT[1], U.BASE_PT))

    api = FakeApi()
    shift_part()
    cache_part(api)
    ov = overlay_part(root, api)
    picker_part(root, api)
    ov.clear()
    box_part(root)
    settle(root, 0.3)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
