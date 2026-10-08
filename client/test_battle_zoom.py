# -*- coding: utf-8 -*-
"""배틀 창 크기 검사 (1.10.3, battle_zoom).

    python client/test_battle_zoom.py

**창을 진짜로 띄운다.** 실시간 배틀 창과 레이드 배틀 창을 띄우고(가짜 서버는 test_live_ui ·
test_raid_ui 의 것) **크기를 바꿔 가며** 본다. 관장 창은 test_gym_ui 가 같은 것을 본다.
기존 창 검사들을 `POKET_BATTLE_ZOOM=0.85` 처럼 걸어 돌리면 그 크기로 뜬 채 전부를 다시 본다.

  1. 배틀 창은 **다른 창처럼 가장자리를 끌어서** 크기를 바꾼다. 처음에는 예전과 같은 크기로 뜬다.
  2. 창을 키우면 장면·도트·글자·단추가 그만큼 커지고, 줄이면 작아진다. 배율은 그 창에 들어가는
     가장 큰 값이고, **장면이 남는 자리를 다 쓴다** (창이 비율에 맞춰 도로 튕기지 않는다).
  3. 어느 크기에서도 눌린 위젯이 없고, 이름표가 장면 안에 있고, 가장 긴 기술 설명도 안 잘린다.
     **포켓몬이 이름표에 가려지지 않는다** - 가장 작게 줄였을 때도 (내 포켓몬의 머리가 상대 이름표
     뒤로 들어갔었다. 그래서 기술 카드를 줄이고 장면을 가장 낮게 했을 때의 높이를 올렸다).
     글자는 7pt 아래로 안 내려간다 - 그래서 창도 어느 크기 아래로는 안 줄어든다.
  3-1. **줄인 창에서는 교체·기권 단추가 옆으로 나란히 선다** - 그 아래의 기술 설명 칸이 다섯 줄
     (윈도우에서 가장 긴 설명)을 담게. 위아래로 쌓으면 줄인 창에서 설명이 잘렸다 (글자는 7pt 아래로
     안 줄고 여백도 그대로라 그 칸만 좁아진다). 줄이지 않은 창은 예전처럼 위아래다.
  4. **크기를 바꿔도 판은 그대로다**: 나와 있는 포켓몬, 고르던 칸(기술·교체·기다리는 중·결과),
     마지막 말, 켜 둔 메가진화. 연출이 도는 중에 바꿔도 끝까지 간다 (오류 없이).
  5. 바꾼 크기는 창 종류마다 기억해서 다음 판도 그 크기로 뜬다. 화면보다 크게는 안 뜬다.
     설정 창의 '기본 크기로' 가 그것을 지운다.
"""
import json
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-zoom-")
os.environ.pop("POKET_BATTLE_ZOOM", None)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import battle_zoom as Z                   # noqa: E402
from poketdesktop import config                             # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_live_battle as LUI              # noqa: E402
from poketdesktop import ui_raid_battle as RUI              # noqa: E402
import test_live_ui as L                                    # noqa: E402
import test_raid_ui as R                                    # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def font_sizes(win):
    """창 안의 글자 크기들 (라벨과 캔버스 글자)."""
    out = []

    def walk(w):
        for c in w.winfo_children():
            try:
                if "font" in c.keys() and str(c.cget("text") if "text" in c.keys() else ""):
                    parts = c.tk.splitlist(c.cget("font"))
                    if len(parts) >= 2:
                        out.append(abs(int(parts[1])))
            except Exception:                               # noqa: BLE001
                pass
            if isinstance(c, tk.Canvas):
                for it in c.find_all():
                    if c.type(it) == "text" and c.itemcget(it, "text"):
                        parts = c.tk.splitlist(c.itemcget(it, "font"))
                        if len(parts) >= 2:
                            out.append(abs(int(parts[1])))
            walk(c)
    walk(win)
    return out


def hidden(cv, sprite, box):
    """도트(sprite)가 이름표(box)에 가려진 넓이(px). 안 겹치면 0."""
    a, b = cv.bbox(sprite), cv.bbox(box)
    if not a or not b:
        return 0
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0, w) * max(0, h)


def hint_room(label):
    """기술 설명 칸이 **윈도우 글꼴로** 다섯 줄을 담나: (받은 높이, 다섯 줄에 드는 높이).

    맥의 글꼴은 줄이 낮아서 맥에서 재면 늘 넉넉하다. 윈도우(맑은 고딕)는 한 줄이 글자 크기(pt)의
    두 배쯤이다 (8pt 두 줄이 32px 였다 - 1.6.0 의 CI). 가장 긴 설명 68자가 윈도우에서 다섯 줄이다.

    **윈도우에서는 어림하지 않는다** - 진짜 글꼴로 가장 긴 설명을 넣고 잰 것(안 잘린다)이 답이다.
    """
    if sys.platform.startswith("win"):
        return label.winfo_height(), 0
    pt = abs(int(label.tk.splitlist(label.cget("font"))[1]))
    return label.winfo_height(), 5 * 2 * pt


def side_by_side(a, b):
    """두 단추가 옆으로 나란히 섰나 (같은 줄)."""
    return abs(a.holder.winfo_rooty() - b.holder.winfo_rooty()) <= 2 and a.holder.winfo_rootx() < b.holder.winfo_rootx()


def buttons_fit(*buttons):
    """단추들이 제 줄 안에 들어가고(바라는 폭 <= 받은 폭), 글자가 단추 안에 들어가나."""
    for b in buttons:
        if b.holder.winfo_reqwidth() > b.holder.winfo_width() + 1:
            return False
        if b.label.winfo_reqwidth() > b.box.winfo_width() - 3:
            return False
    row = buttons[0].holder.master
    return row.winfo_reqwidth() <= row.winfo_width() + 1


def resize(root, w, ww, wh, sec=6.0):
    """창을 끌어 그 크기로 만든 것처럼: 크기를 바꾸고, 따라 다시 지을 때까지 기다린다."""
    w.win.geometry("%dx%d" % (int(ww), int(wh)))
    end = time.time() + sec
    while time.time() < end:
        root.update()
        try:
            now = (w.win.winfo_width(), w.win.winfo_height())
        except tk.TclError:
            return None
        if now == (int(ww), int(wh)) and w._zoom_size == now and w._zoom_job is None:
            break
        time.sleep(0.01)
    L.rest(root, 0.35)
    w.win.update_idletasks()
    return (w.win.winfo_width(), w.win.winfo_height())


def main():
    print("=== 배율 ===")
    chk("기본 크기면 배율 1 이다 (장면을 가장 낮게 했을 때의 높이로 잰다 - 넉넉하다)", Z.scale_of(1000, 600, 1000, 520) == 1.0)
    chk("폭과 높이가 같이 커지면 그만큼", abs(Z.scale_of(1300, 780, 1000, 600) - 1.3) < 1e-9
        and abs(Z.scale_of(850, 510, 1000, 600) - 0.85) < 1e-9)
    chk("**그 창에 들어가는 가장 큰 배율**: 폭만 늘리면 높이가 허락하는 데까지만", abs(Z.scale_of(2000, 660, 1000, 600) - 1.1) < 1e-9
        and Z.scale_of(1000, 2000, 1000, 600) == 1.0)
    chk("조금 모자라는 것은 줄이지 않는다 (화면이 조금 좁은 PC 에서 글자가 한 치 줄지 않게)", Z.scale_of(970, 600, 1000, 600) == 1.0
        and Z.scale_of(940, 600, 1000, 600) == 0.94)
    chk("어느 크기 아래·위로는 안 간다", Z.scale_of(100, 100, 1000, 600) == Z.MIN_K and Z.scale_of(9000, 9000, 1000, 600) == Z.MAX_K
        and Z.scale_of(0, 0, 0, 0) == 1.0, (Z.MIN_K, Z.MAX_K))

    class Holder(object):
        settings = {}
    h = Holder()
    chk("기억해 둔 크기가 없으면 None", Z.remembered(h, "live") is None and Z.remembered(None, "live") is None)
    Z.remember(h, "live", 900, 640)
    Z.remember(h, "gym", 700, 500)
    chk("창 종류마다 따로 기억한다 (설정 파일에도 남는다)", Z.remembered(h, "live") == (900, 640) and Z.remembered(h, "gym") == (700, 500)
        and Z.remembered(h, "raid") is None and config.load_settings().get("battleSize", {}).get("live") == [900, 640])
    h.settings["battleSize"]["raid"] = ["x", None]
    chk("이상한 값은 없는 것으로 친다", Z.remembered(h, "raid") is None)
    Z.forget(h)
    chk("지우면 다 기본 크기로 돌아간다", h.settings["battleSize"] == {} and Z.remembered(h, "live") is None
        and config.load_settings().get("battleSize") == {})
    chk("기본 설정에는 기억해 둔 크기가 없다", config.DEFAULTS.get("battleSize") == {})

    with open(os.path.join(L.DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
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
    sw_, sh_ = root.winfo_screenwidth(), root.winfo_screenheight()
    try:
        real_area = tuple(PLAT.work_area(sw_, sh_))
    except Exception:                                       # noqa: BLE001
        real_area = (0, 0, sw_, sh_)
    print("글꼴 %s / 본문 %dpt / 작업 영역 %s" % (U.FAMILY, U.FONT[1], real_area))
    keep_area = PLAT.work_area
    BW = U.h(LUI.W)
    REST = U.h(LUI.MSG_H) + U.h(LUI.CMD_H) + 4
    BH = U.h(LUI.SCENE_H) + REST
    BH_MIN = U.h(LUI.MIN_SCENE_H) + REST
    # **이 PC 의 화면에 들어가는 크기로만 본다** (창은 화면보다 클 수 없다 - OS 가 줄인다).
    room_w = (real_area[2] - real_area[0]) - U.h(16)
    room_h = (real_area[3] - real_area[1]) - Z.CHROME
    FIRST = (min(BW, room_w), min(BH, room_h))                          # 처음 뜨는 크기 (화면을 넘지 않는다)
    BIG = (min(int(BW * 1.3), room_w), min(int(BH * 1.3), room_h))      # 이 화면에서 가장 크게
    MID = (min(int(BW * 0.9), room_w), min(int(BH * 0.9), room_h))

    def zoom_at(size):
        return Z.scale_of(size[0], size[1], BW, BH_MIN)

    print("\n=== 글자와 칸 ===")
    Z.K = 0.85
    chk("칸은 배율만큼, 글자는 내림 (칸보다 크게 반올림되지 않는다)", Z.U.h(100) == int(round(U.h(100) * 0.85))
        and Z.px(100) == 85 and Z.U.pt(13) == int(U.pt(13) * 0.85) and Z.U.FONT_S == (U.FONT_S[0], int(U.FONT_S[1] * 0.85)),
        (Z.U.h(100), Z.U.pt(13), Z.U.FONT_S))
    chk("  7pt 아래로는 안 내려간다", Z.font(("x", 8)) == ("x", 7) and Z.font(("x", 7, "bold")) == ("x", 7, "bold") and Z.U.pt(7) == 7)
    chk("  크기가 아닌 것은 ui_common 그대로다", Z.U.BG is U.BG and Z.U.TYPE_COLOR is U.TYPE_COLOR and Z.U.wrap_to_width is U.wrap_to_width)
    Z.K = 1.0
    chk("배율 1 이면 예전과 한 치도 다르지 않다", Z.U.h(100) == U.h(100) and Z.U.pt(13) == U.pt(13) and Z.U.FONT_B == U.FONT_B
        and Z.U.FONT_XS == U.FONT_XS and Z.px(132) == 132 and Z.base_h(38) == U.h(38))

    print("\n=== 실시간 배틀 창: 처음 ===")
    api = L.FakeApi(dex)
    app = L.FakeApp(root, api, dex)
    w = LUI.LiveBattleWindow(app, api.match())
    L.pump(root, lambda: not w.busy, timeout=25)
    L.rest(root, 0.5)
    w.win.update_idletasks()
    chk("처음에는 예전과 같은 크기로 뜬다 (%d x %d - 설계 %d x %d 를 이 화면에 맞춘 것), 배율 %.2f" % (FIRST + (BW, BH, w.zoom)),
        (w.win.winfo_width(), w.win.winfo_height()) == FIRST and w.zoom == zoom_at(FIRST) and (BW > room_w or w.zoom == 1.0),
        (w.win.winfo_width(), w.win.winfo_height(), w.zoom))
    lo = w.win.minsize()
    chk("**끌어서 크기를 바꿀 수 있는 창이다** (어느 크기 아래로는 안 줄어든다)", tuple(bool(x) for x in w.win.resizable()) == (True, True)
        and tuple(lo) == (int(BW * Z.MIN_K), int(BH_MIN * Z.MIN_K)) == w.zoom_min(), (w.win.resizable(), lo))
    chk("  아직 아무것도 기억하지 않는다 (안 건드렸다)", not app.settings.get("battleSize"), app.settings.get("battleSize"))
    L.pump(root, lambda: w.anims.get("me") and w.anims.get("foe"), timeout=10)

    def shot():
        return {"mon": w.anims["me"][0][0].height() if w.anims.get("me") else 0, "font": max(font_sizes(w.win)),
                "btn": w.switch_btn.holder.winfo_height(), "bar": w.cv.coords(w.box["me"]["bar_bg"])}
    first = shot()
    names0 = (w.shown["me"]["name"], w.shown["foe"]["name"])
    said0 = w.msg.cget("text")
    moves0 = [t for t in texts(w.left) if "PP" in t]

    def look(tag, size):
        """지금 크기에서: 눌린 것 없음 · 이름표가 장면 안 · 긴 설명이 안 잘림 · 글자 7pt 이상 · 장면이 창을 채움."""
        k = zoom_at(size)
        ins = [L.inside(w.cv, w.box[who]["name"])[0] and L.inside(w.cv, w.box[who]["bg"])[0] for who in ("me", "foe")]
        bad = squeezed(w.win)
        keep = w.hint.cget("text")
        w.hint.configure(text=L.LONGEST_DESC)
        w.win.update_idletasks()
        fits = w.hint.winfo_reqheight() <= w.hint.winfo_height()
        w.hint.configure(text=keep)
        sizes = font_sizes(w.win)
        chk("  %s: 눌린 위젯 없음 · 이름표는 장면 안 · 가장 긴 기술 설명도 안 잘린다 · 글자 %d~%dpt"
            % (tag, min(sizes), max(sizes)), not bad and all(ins) and fits and min(sizes) >= 7,
            (bad[:3], ins, fits, sorted(set(sizes))))
        chk("  %s: 장면이 창을 꽉 채운다 (폭 전체, 높이는 말풍선·명령 칸을 뺀 나머지) - 배율 %.2f" % (tag, w.zoom),
            w.cv.winfo_width() >= w.win.winfo_width() - 6 and abs(w.cv.winfo_height() - w.sh) <= 1
            and abs((w.sh + Z.U.h(LUI.MSG_H) + Z.U.h(LUI.CMD_H) + 4) - w.win.winfo_height()) <= 1
            and abs(w.zoom - k) < 1e-6, (w.cv.winfo_width(), w.cv.winfo_height(), w.sh, w.win.winfo_width(), w.win.winfo_height(), w.zoom, k))
        got_h, need_h = hint_room(w.hint)
        row = side_by_side(w.switch_btn, w.forfeit_btn)
        chk("  %s: 기술 설명 칸이 윈도우 글꼴로도 다섯 줄을 담는다 (%d >= %d). 단추는 %s" % (tag, got_h, need_h, "옆으로 나란히" if row else "위아래"),
            got_h >= need_h and row == (w.zoom < 1.0) and buttons_fit(w.switch_btn, w.forfeit_btn),
            (got_h, need_h, row, w.zoom, [(b.holder.winfo_reqwidth(), b.holder.winfo_width(), b.label.winfo_reqwidth(), b.box.winfo_width())
                                          for b in (w.switch_btn, w.forfeit_btn)]))
        if not (w._result_shown or w.busy):
            L.pump(root, lambda: all(w.cv.itemcget(w.sprite[who], "image") for who in ("me", "foe")), timeout=10)
            cover = (hidden(w.cv, w.sprite["me"], w.box["foe"]["bg"]), hidden(w.cv, w.sprite["foe"], w.box["me"]["bg"]))
            chk("  %s: **포켓몬이 이름표에 가려지지 않는다** (내 포켓몬 ↔ 상대 이름표, 상대 포켓몬 ↔ 내 이름표)" % tag, cover == (0, 0),
                (cover, w.cv.bbox(w.sprite["me"]), w.cv.bbox(w.box["foe"]["bg"]), w.cv.bbox(w.sprite["foe"]), w.cv.bbox(w.box["me"]["bg"])))

    look("처음 크기", FIRST)
    cells = w.left.winfo_children()[0].winfo_children()
    chk("기술 카드는 안에 든 글의 두 배보다 낮다 (예전에는 두 배가 넘어 장면이 좁았다)", len(cells) == 4
        and cells[0].winfo_reqheight() <= cells[0].winfo_height() < cells[0].winfo_reqheight() * 2.1,
        (cells[0].winfo_height(), cells[0].winfo_reqheight()))

    print("\n=== 줄인다 ===")
    SML = w.zoom_min()
    got = resize(root, w, *SML)
    L.pump(root, lambda: w.anims.get("me") and w.anims["me"][0][0].height() < first["mon"], timeout=10)
    small = shot()
    chk("**창을 가장 작게 줄인다** (%d x %d): 그 크기 그대로 남고, 도트·글자·단추·체력 막대가 다 같이 작아진다 (배율 %.2f)"
        % (SML + (w.zoom,)), got == SML and abs(w.zoom - Z.MIN_K) < 1e-6 and small["mon"] < first["mon"]
        and small["font"] < first["font"] and small["btn"] < first["btn"]
        and (small["bar"][2] - small["bar"][0]) < (first["bar"][2] - first["bar"][0]), (got, w.zoom, small, first))
    chk("  **판은 그대로다**: 나와 있는 포켓몬, 기술 칸, 마지막 말", (w.shown["me"]["name"], w.shown["foe"]["name"]) == names0
        and [t for t in texts(w.left) if "PP" in t] == moves0 and w.msg.cget("text") == said0 and not w.busy,
        (w.shown["me"]["name"], w.msg.cget("text"), said0))
    chk("  그 크기를 기억해 둔다", app.settings.get("battleSize", {}).get("live") == list(SML)
        and config.load_settings().get("battleSize", {}).get("live") == list(SML), app.settings.get("battleSize"))
    look("가장 작게", SML)

    print("\n=== 키운다 ===")
    got = resize(root, w, *BIG)
    L.pump(root, lambda: w.anims.get("me") and w.anims["me"][0][0].height() > small["mon"], timeout=10)
    big = shot()
    chk("**창을 키우면 그 크기 그대로 남는다** (%d x %d, 도로 튕기지 않는다) - 배율 %.2f" % (BIG + (w.zoom,)), got == BIG
        and abs(w.zoom - zoom_at(BIG)) < 1e-6 and w.zoom > Z.MIN_K, (got, w.zoom))
    chk("  다 같이 커진다", big["mon"] > small["mon"] and big["font"] > small["font"] and big["btn"] > small["btn"]
        and (big["bar"][2] - big["bar"][0]) > (small["bar"][2] - small["bar"][0]), (small, big))
    look("가장 크게", BIG)
    got = resize(root, w, *MID)
    chk("그 사이 (%d x %d, 배율 %.2f)" % (MID + (w.zoom,)), got == MID and abs(w.zoom - zoom_at(MID)) < 1e-6, (got, w.zoom))
    look("그 사이", MID)

    print("\n=== 비율을 깨고 끈다 ===")
    WIDE = (room_w, SML[1] + (MID[1] - SML[1]) // 2)
    got = resize(root, w, *WIDE)
    chk("**폭만 넓힌다** (%d x %d): 높이가 허락하는 데까지만 커지고(배율 %.2f), 장면이 넓어진다" % (WIDE + (w.zoom,)), got == WIDE
        and abs(w.zoom - zoom_at(WIDE)) < 1e-6 and w.zoom < WIDE[0] / float(BW) and w.sw == WIDE[0] - 4
        and w.foe_pos[0] - w.me_pos[0] > WIDE[0] * 0.4, (got, w.zoom, w.sw))
    look("폭만", WIDE)
    TALL = (SML[0] + (MID[0] - SML[0]) // 2, room_h)
    got = resize(root, w, *TALL)
    chk("**높이만 키운다** (%d x %d): 폭이 허락하는 만큼만(배율 %.2f)이고 장면이 높아진다" % (TALL + (w.zoom,)), got == TALL
        and abs(w.zoom - zoom_at(TALL)) < 1e-6 and w.zoom < TALL[1] / float(BH_MIN)
        and w.sh > Z.U.h(LUI.MIN_SCENE_H) * 1.15, (got, w.zoom, w.sh))
    look("높이만", TALL)
    got = resize(root, w, *FIRST)
    L.pump(root, lambda: w.anims.get("me") and w.anims["me"][0][0].height() == first["mon"], timeout=10)
    back = shot()
    chk("처음 크기로 되돌리면 처음 모습 그대로다", got == FIRST and w.zoom == zoom_at(FIRST) and back == first, (got, w.zoom, back, first))

    print("\n=== 고르던 칸은 그대로다 ===")
    w.open_switch()
    root.update()
    chk("(교체 칸을 열었다)", any("누구로 바꿀까" in t for t in texts(w.left)) and w._switching)
    resize(root, w, *MID)
    chk("교체 칸을 열어 둔 채 크기를 바꾸면 교체 칸 그대로다", any("누구로 바꿀까" in t for t in texts(w.left)) and any("돌아가기" in t for t in texts(w.left)),
        texts(w.left)[:4])
    bad = squeezed(w.win)
    chk("  눌린 위젯 없음", not bad, bad[:3])
    w.show_commands()
    root.update()
    api.auto_foe = False                # 상대가 안 고른다 - 내가 고르면 '기다리는 중' 이 된다
    acts = len([c for c in api.calls if c.startswith("act")])
    w.use_move("TACKLE")
    L.pump(root, lambda: any("기다리는 중" in t for t in texts(w.left)), timeout=10)
    resize(root, w, *SML)
    chk("보내고 기다리는 중에 크기를 바꿔도 '기다리는 중' 그대로다 (다시 보내지 않는다)", any("기다리는 중" in t for t in texts(w.left)) and w.sent
        and len([c for c in api.calls if c.startswith("act")]) == acts + 1 and not [t for t in texts(w.left) if "PP" in t], texts(w.left)[:3])
    look("기다리는 중", SML)

    print("\n=== 연출이 도는 중에 바꾼다 ===")
    api.auto_foe = True
    api.lb.choose("b", *api.lb.auto_choice("b"))
    api.events = api.lb.resolve()
    api.turn = api.lb.turn
    L.pump(root, lambda: w.busy, timeout=8)             # 폴링이 턴이 돈 것을 알아채고 재생을 시작한다
    chk("(턴이 돌아 재생이 시작됐다)", w.busy, w.busy)
    L.pump(root, lambda: w.fx is not None or not w.busy, timeout=6)
    was_fx = w.fx is not None
    mid = resize(root, w, *MID)
    chk("**재생 중에 크기를 바꾼다** (기술 연출이 도는 중: %s): 새 크기로 다시 지어지고 재생은 이어진다" % was_fx, mid == MID
        and abs(w.zoom - zoom_at(MID)) < 1e-6, (mid, w.zoom))
    done = L.pump(root, lambda: not w.busy, timeout=30)
    L.rest(root, 0.5)
    chk("  끝까지 가서 다시 고를 수 있다 (오류 없이)", done and not errors and ([t for t in texts(w.left) if "PP" in t]
        or any("고르세요" in t or "기다리는" in t for t in texts(w.left))), (done, errors[:1], texts(w.left)[:3]))
    look("재생 뒤", MID)

    print("\n=== 결과 칸 ===")
    api.lb.choose("a", "forfeit", None)
    if api.lb.can_act("b"):
        api.lb.choose("b", *api.lb.auto_choice("b"))
    if api.lb.ready():
        api.events = api.lb.resolve()
    api.state = "done" if api.lb.over else api.state
    L.pump(root, lambda: w._result_shown, timeout=20)
    L.rest(root, 0.4)
    chk("(판이 끝나 결과 칸이 떴다)", w._result_shown and w._result_painted and any("닫기" in t for t in texts(w.left)) and api.seen == 1,
        (texts(w.left)[:3], api.seen))
    LAST = (MID[0] - 20, MID[1] - 14)
    resize(root, w, *LAST)
    chk("결과를 띄운 채 크기를 바꿔도 결과 그대로다 (서버에 '봤다' 를 또 보내지 않는다)", any("닫기" in t for t in texts(w.left))
        and any("실시간 배틀" in t for t in texts(w.left)) and api.seen == 1, (texts(w.left)[:4], api.seen))
    bad = squeezed(w.win)
    chk("  눌린 위젯 없음", not bad, bad[:3])
    w.close()
    chk("닫으면 걸어 둔 것이 없다", w._zoom_job is None and not w.alive)

    print("\n=== 다음 판은 그 크기로 뜬다 ===")
    api = L.FakeApi(dex)
    app2 = L.FakeApp(root, api, dex)
    app2.settings = app.settings
    w = LUI.LiveBattleWindow(app2, api.match())
    L.pump(root, lambda: not w.busy, timeout=25)
    w.win.update_idletasks()
    chk("**기억해 둔 크기로 뜬다** (%s)" % (app.settings["battleSize"]["live"],), [w.win.winfo_width(), w.win.winfo_height()]
        == app.settings["battleSize"]["live"] == list(LAST) and abs(w.zoom - zoom_at(LAST)) < 1e-6,
        (w.win.winfo_width(), w.win.winfo_height(), app.settings.get("battleSize")))
    bad = squeezed(w.win)
    chk("  눌린 위젯 없음", not bad, bad[:3])
    w.close()
    small_area = (0, 0, int(BW * 0.95), int(BH_MIN * 0.97) + Z.CHROME)
    PLAT.work_area = lambda *_a: small_area
    app2.settings["battleSize"] = {"live": [int(BW * 1.6), int(BH * 1.6)]}
    api = L.FakeApi(dex)
    app2.api = api
    w = LUI.LiveBattleWindow(app2, api.match())
    L.pump(root, lambda: not w.busy, timeout=25)
    w.win.update_idletasks()
    bad = squeezed(w.win)
    chk("**화면보다 크게는 안 뜬다** (기억해 둔 크기가 지금 화면보다 크다 - 다른 모니터에서 키웠다)", w.win.winfo_width() <= small_area[2]
        and w.win.winfo_height() <= small_area[3] - Z.CHROME and not bad and all(L.inside(w.cv, w.box[who]["bg"])[0] for who in ("me", "foe")),
        (w.win.winfo_width(), w.win.winfo_height(), small_area, bad[:3]))
    w.close()
    PLAT.work_area = keep_area

    print("\n=== 레이드 배틀 창 ===")
    # (작업 영역은 그사이 몇 픽셀 달라질 수 있다 - 맥의 독은 아이콘이 늘면 낮아진다. 지금 것으로 다시 잰다)
    try:
        now_area = tuple(PLAT.work_area(sw_, sh_))
    except Exception:                                       # noqa: BLE001
        now_area = real_area
    room_w = (now_area[2] - now_area[0]) - U.h(16)
    room_h = (now_area[3] - now_area[1]) - Z.CHROME
    api3 = R.FakeApi(dex, n=6, revealed=True)
    room = api3.begin()
    app3 = R.FakeApp(root, api3, dex)
    bw = RUI.RaidBattleWindow(app3, room)
    L.pump(root, lambda: not bw.busy, timeout=25)
    L.rest(root, 0.4)
    bw.win.update_idletasks()
    RREST = U.h(RUI.MSG_H) + U.h(RUI.CMD_H) + 4
    RW, RH, RH_MIN = U.h(RUI.W), U.h(RUI.SCENE_H) + RREST, U.h(RUI.MIN_SCENE_H) + RREST
    RFIRST = (min(RW, room_w), min(RH, room_h))
    chk("처음에는 예전 크기 (%d x %d), 끌어서 바꿀 수 있다" % RFIRST, (bw.win.winfo_width(), bw.win.winfo_height()) == RFIRST
        and tuple(bool(x) for x in bw.win.resizable()) == (True, True), (bw.win.winfo_width(), bw.win.winfo_height()))
    names0 = [bw.cv.itemcget(bw.slots[i]["name"], "text") for i in range(6)]
    boss0 = bw.cv.itemcget(bw.boss_name, "text")
    zooms = []
    for size in (bw.zoom_min(), (min(int(RW * 0.92), room_w), min(int(RH * 0.92), room_h)), RFIRST):
        got = resize(root, bw, *size)
        bad = squeezed(bw.win)
        inside = all(R.inside(bw.cv, bw.slots[i]["name"])[0] for i in range(6)) and R.inside(bw.cv, bw.boss_name)[0]
        sizes = font_sizes(bw.win)
        zooms.append(bw.zoom)
        keep = bw.hint.cget("text")
        bw.hint.configure(text=L.LONGEST_DESC)
        bw.win.update_idletasks()
        fits = bw.hint.winfo_reqheight() <= bw.hint.winfo_height()
        got_h, need_h = hint_room(bw.hint)
        row = side_by_side(bw.switch_btn, bw.leave_btn)
        bw.hint.configure(text=keep)
        chk("%s: 가장 긴 기술 설명이 안 잘리고, 줄인 창에서는 단추가 나란히 서서 설명 칸이 다섯 줄을 담는다 (%d / %d, 나란히 %s)"
            % (got, got_h, need_h, row), row == (bw.zoom < 1.0) and buttons_fit(bw.switch_btn, bw.leave_btn)
            # (줄이지 않은 레이드 창은 윈도우에서 설명 칸이 세 줄뿐이다 - 예전부터 그렇고, 줄인 창에서만 잰다)
            and (bw.zoom >= 1.0 or (fits and got_h >= need_h)), (fits, got_h, need_h, row, bw.zoom))
        L.pump(root, lambda: all(bw.cv.itemcget(bw.sprite[i], "image") for i in range(6)), timeout=10)
        tops = [bw.cv.bbox(bw.sprite[i])[1] for i in range(6) if bw.cv.bbox(bw.sprite[i])]
        marks = [bw.cv.bbox(bw.slots[i]["mark"])[3] for i in range(6) if bw.cv.bbox(bw.slots[i]["mark"])]
        chk("%s: 참가자의 도트가 제 이름·체력 막대를 가리지 않는다 (도트 꼭대기 %s, 글자 바닥 %s)" % (got, min(tops or [0]), max(marks or [0])),
            len(tops) == 6 and min(tops) >= max(marks) - 1, (tops, marks))
        chk("%s (배율 %.2f): 여섯 자리·보스 이름이 그대로 서고, 눌린 것 없음, 글자 %d~%dpt" % (got, bw.zoom, min(sizes), max(sizes)),
            got == size and abs(bw.zoom - Z.scale_of(size[0], size[1], RW, RH_MIN)) < 1e-6 and not bad and inside
            and min(sizes) >= 7 and [bw.cv.itemcget(bw.slots[i]["name"], "text") for i in range(6)] == names0
            and bw.cv.itemcget(bw.boss_name, "text") == boss0 and len(bw.sprite) == 7
            and any("PP" in t for t in texts(bw.left)), (got, size, bw.zoom, bad[:3], inside))
    chk("  작게 < 그 사이 <= 처음", zooms[0] < zooms[1] <= zooms[2], zooms)
    chk("  레이드 창의 크기는 따로 기억한다", app3.settings.get("battleSize", {}).get("raid") == list(RFIRST)
        and "live" not in app3.settings.get("battleSize", {}), app3.settings.get("battleSize"))
    bw.close()

    print("\n=== 설정 창 ===")
    from poketdesktop import ui_settings

    class App(object):
        """설정 창이 만지는 것만 갖춘 껍데기 (test_stealth 의 것과 같은 꼴)."""
        wild = None
        boss_key_error = ""

        def __init__(self):
            self.root, self.overlay = root, self
            self.settings = dict(config.DEFAULTS)

        def apply_names(self):
            pass

        def apply_alpha(self):
            pass

        def refresh_tray(self):
            pass

        def stealth_on(self):
            return False

        def boss_key(self):
            return ""

        def apply_boss_key(self, combo=None):
            return True, ""
    sapp = App()
    sapp.settings["battleSize"] = {"live": [900, 700]}
    sw = ui_settings.SettingsWindow(sapp)
    L.rest(root, 0.5)
    seen = texts(sw.win)
    chk("설정 창이 알려 준다: 배틀 창은 끌어서 크기를 바꾼다", any("가장자리를 끌어서" in t for t in seen) and "배틀 창 크기" in seen
        and sw.zoom_btn.label.cget("text") == "기본 크기로" and sw.zoom_btn.enabled, [t for t in seen if "배틀" in t][:3])
    sw.zoom_btn.command()
    root.update()
    chk("**'기본 크기로' 를 누르면 기억해 둔 크기를 지운다** (다음 배틀 창은 기본 크기로)", sapp.settings["battleSize"] == {}
        and config.load_settings().get("battleSize") == {} and not sw.zoom_btn.enabled and "기본 크기" in sw.zoom_msg.cget("text"),
        (sapp.settings.get("battleSize"), sw.zoom_msg.cget("text")))
    bad = squeezed(sw.win)
    chk("  설정 창에 눌린 위젯 없음", not bad, bad[:3])
    try:
        sw.close()
    except Exception:                                       # noqa: BLE001
        pass
    chk("도는 동안 오류 없음", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
