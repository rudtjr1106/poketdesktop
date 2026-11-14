# -*- coding: utf-8 -*-
"""길드 깃발 그리기 창 (2.5.0, ui_flag) — 진짜 Tk 로 확인. 서버 없이 돈다.

    python3 client/test_flag_editor_ui.py
    POKET_SKIN=dp python3 client/test_flag_editor_ui.py

설계: design-notes/2026-11-14-guild-flag.md '앱'. 규칙(누가 그리나 · 꼴 검사 · 빈 그림 = 내림)은 서버 검사
(server/test_guild_flag.py)가 본다. 여기서는 **창**을 본다:

  1. 지금 길드 깃발을 불러와 시작한다 (칸 · 미리보기 1배 · 2배). 처음엔 저장 · 되돌리기가 죽어 있다.
  2. 펜 (누르기 · 누른 채 끌기 - 빨리 끌어 칸을 건너뛰어도 이어서 칠한다) · 지우개 · 채우기 · 스포이드.
  3. 되돌리기 · 다시 하기 (단추 · 맥 ⌘Z/⌘⇧Z · 윈도우 Ctrl+Z/Ctrl+Y · 한글 자판) · 모두 지우기.
  4. 칠할 때 캔버스 도형을 지우고 다시 그리지 않는다 (576칸 그대로, 빛깔만 바뀐다 - 맥 Tk 캔버스 비용).
  5. 저장 = 서버로 576자 그대로 · 다 지우고 저장하면 묻고 576자 '.' · 서버가 막으면 그 글을 띄우고 안 저장한 채로.
  6. 닫기: 안 저장한 것이 있으면 묻는다 (아니오면 그대로), 없으면 바로 닫는다.
  7. 창은 내용만큼 (눌린 위젯 없음), Tk 오류 없음.
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-flag-editor-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from common import flag as F                               # noqa: E402
from poketdesktop import api as apimod                      # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_box, ui_flag                    # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Api(object):
    def __init__(self):
        self.sent = []
        self.fail = None

    def guild_flag(self, pixels):
        self.sent.append(pixels)
        if self.fail:
            raise apimod.ApiError(self.fail, 403)
        return {"guild": {"id": 1, "name": "피카단", "flag": None if F.is_blank(pixels) else pixels}, "canFlag": True}


class App(object):
    def __init__(self, root):
        self.root, self.api = root, Api()


def settle(root, sec=0.25):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def wait(root, cond, sec=4.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.01)
    return cond()


def start_flag():
    """시작 깃발: 왼쪽 위 3x3 은 9번(연두), (10,10) 에 21번(흰색) 한 칸, 나머지 투명."""
    px = F.BLANK
    for x in range(3):
        for y in range(3):
            px = F.put(px, x, y, 9)
    return F.put(px, 10, 10, 21)


def center(ed, x, y):
    c = ed.cell
    return x * c + c // 2, y * c + c // 2


def click(ed, x, y):
    px, py = center(ed, x, y)
    ed.board.event_generate("<ButtonPress-1>", x=px, y=py)
    ed.board.event_generate("<ButtonRelease-1>", x=px, y=py)


def drag(ed, path):
    (x0, y0), rest = path[0], path[1:]
    px, py = center(ed, x0, y0)
    ed.board.event_generate("<ButtonPress-1>", x=px, y=py)
    for x, y in rest:
        px, py = center(ed, x, y)
        ed.board.event_generate("<B1-Motion>", x=px, y=py)
    ed.board.event_generate("<ButtonRelease-1>", x=px, y=py)


def fill_of(ed, x, y):
    return ed.board.itemcget(ed.rects[y * F.SIZE + x], "fill")


def p1_at(ed, x, y):
    """미리보기 1배 그림의 그 점: '#rrggbb' 또는 None (투명)."""
    img = ed.p1
    if img.transparency_get(x, y):
        return None
    return "#%02x%02x%02x" % tuple(img.get(x, y))


def p2_at(ed, x, y):
    """2배 그림의 그 칸 (네 점이 다 같아야 한다)."""
    img = ed.p2
    pts = [(2 * x + dx, 2 * y + dy) for dx in (0, 1) for dy in (0, 1)]
    vals = set(None if img.transparency_get(a, b) else "#%02x%02x%02x" % tuple(img.get(a, b)) for a, b in pts)
    return vals.pop() if len(vals) == 1 else ("섞임", vals)


class Key(object):
    def __init__(self, keysym, char="", keycode=0, state=0):
        self.keysym, self.char, self.keycode, self.state = keysym, char, keycode, state


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda *a: errors.append(a)
    asked = []
    answer = {"v": True}

    def fake_confirm(parent, title, message, danger=True, ok_text="확인"):
        asked.append(message)
        return answer["v"]
    ui_box.confirm = fake_confirm
    print("테마 %s · 글꼴 %s / 본문 %dpt" % (skins.active(), U.FAMILY, U.FONT[1]))

    app = App(root)
    saved = []
    start = start_flag()
    ed = ui_flag.FlagEditor(root, app, start, on_saved=saved.append)
    settle(root, 0.4)
    n_items = len(ed.board.find_all())

    print("=== 1. 지금 깃발을 불러와 시작 ===")
    green, white = F.PALETTE[9], F.PALETTE[21]
    chk("칸: 불러온 그림 그대로 (576자)", ed.pixels == start and len(ed.pixels) == 576)
    chk("  판 빛깔: (1,1) 연두 · (10,10) 흰색 · 투명 칸은 바둑판", fill_of(ed, 1, 1) == green and fill_of(ed, 10, 10) == white
        and fill_of(ed, 5, 5) in ui_flag.CHECK, (fill_of(ed, 1, 1), fill_of(ed, 10, 10), fill_of(ed, 5, 5)))
    chk("  미리보기 1배 · 2배도 같다 (투명 칸은 비친다)", p1_at(ed, 1, 1) == green and p1_at(ed, 10, 10) == white
        and p1_at(ed, 5, 5) is None and p2_at(ed, 1, 1) == green and p2_at(ed, 5, 5) is None,
        (p1_at(ed, 1, 1), p1_at(ed, 5, 5), p2_at(ed, 1, 1)))
    chk("  미리보기 바탕 둘 (밝은 · 어두운), 각각 1배 · 2배 그림",
        [bg for bg, _a, _b in ed.previews] == [ui_flag.LIGHT_BG, ui_flag.DARK_BG]
        and all(str(a.cget("image")) == str(ed.p1) and str(b.cget("image")) == str(ed.p2) for _bg, a, b in ed.previews)
        and ed.p1.width() == 24 and ed.p2.width() == 48)
    chk("  처음엔 저장 · 되돌리기 · 다시 하기가 죽어 있고 모두 지우기는 산다",
        not ed.b_save.enabled and not ed.b_undo.enabled and not ed.b_redo.enabled and ed.b_clear.enabled)
    chk("  팔레트 32색 + 투명, 고른 빛깔에 금테", len(ed.swatches) == 33
        and ed.swatches[ui_flag.START_COLOR].cget("highlightbackground") == U.ACCENT)

    print("\n=== 2. 펜 · 끌기 · 지우개 · 채우기 · 스포이드 ===")
    red = F.PALETTE[ui_flag.START_COLOR]
    click(ed, 3, 4)
    settle(root, 0.05)
    chk("펜: 누른 칸이 고른 빛깔 (빨강) · 미리보기도", ed.pixels[4 * 24 + 3] == F.DIGITS[ui_flag.START_COLOR]
        and fill_of(ed, 3, 4) == red and p1_at(ed, 3, 4) == red and p2_at(ed, 3, 4) == red)
    chk("  저장 · 되돌리기가 살아난다 (안 저장한 것이 있다)", ed.b_save.enabled and ed.b_undo.enabled and ed.dirty())
    ed.pick_color(17)
    drag(ed, [(0, 12), (2, 12), (9, 12), (9, 15)])                # 2 -> 9, 9 -> 15 는 칸을 건너뛰며 끈다
    settle(root, 0.05)
    want = [(x, 12) for x in range(10)] + [(9, y) for y in range(12, 16)]
    chk("누른 채 끌기: 건너뛴 칸까지 이어서 칠한다 (가로 10칸 + 세로 4칸)",
        all(ed.pixels[y * 24 + x] == F.DIGITS[17] for x, y in want)
        and sum(1 for ch in ed.pixels if ch == F.DIGITS[17]) == len(set(want)),
        sum(1 for ch in ed.pixels if ch == F.DIGITS[17]))
    chk("  한 번 끈 것이 되돌리기 한 걸음", len(ed.undo_stack) == 2, len(ed.undo_stack))
    ed.set_tool("eraser")
    click(ed, 3, 4)
    settle(root, 0.05)
    chk("지우개: 그 칸이 투명 (판은 바둑판, 미리보기는 비친다)", ed.pixels[4 * 24 + 3] == F.EMPTY
        and fill_of(ed, 3, 4) in ui_flag.CHECK and p1_at(ed, 3, 4) is None and p2_at(ed, 3, 4) is None)
    ed.set_tool("picker")
    click(ed, 1, 1)
    settle(root, 0.05)
    chk("스포이드: 그 칸의 빛깔(9번)을 집고 펜으로 돌아간다", ed.color == 9 and ed.tool == "pen"
        and ed.seg.current == "pen" and ed.swatches[9].cget("highlightbackground") == U.ACCENT, (ed.color, ed.tool))
    chk("  스포이드는 그림을 안 바꾼다 (되돌리기 걸음 그대로)", len(ed.undo_stack) == 3, len(ed.undo_stack))
    ed.set_tool("picker")
    click(ed, 6, 6)
    chk("  투명 칸을 집으면 투명 (펜이 지운다)", ed.color is None and ed.tool == "pen", ed.color)
    ed.pick_color(26)
    ed.set_tool("fill")
    before = ed.pixels
    click(ed, 20, 2)                                             # 이어진 투명 칸 전부
    settle(root, 0.05)
    chk("채우기: 이어진 같은 빛깔 칸만 (common.flag.fill 과 같다)", ed.pixels == F.fill(before, 20, 2, 26)
        and ed.pixels[1 * 24 + 1] == F.DIGITS[9] and ed.pixels[12 * 24 + 0] == F.DIGITS[17]
        and fill_of(ed, 23, 23) == F.PALETTE[26] and p1_at(ed, 23, 23) == F.PALETTE[26])
    chk("  채우기도 한 걸음", len(ed.undo_stack) == 4, len(ed.undo_stack))
    chk("칠해도 캔버스 도형을 다시 만들지 않는다 (576칸 그대로)", len(ed.board.find_all()) == n_items == 576,
        (len(ed.board.find_all()), n_items))
    ed.pick_color(5)
    ed.set_tool("eraser")
    ed.pick_color(8)
    chk("지우개를 들고 빛깔을 고르면 펜으로", ed.tool == "pen" and ed.color == 8)

    print("\n=== 3. 되돌리기 · 다시 하기 · 모두 지우기 ===")
    filled = ed.pixels
    ed.b_undo.command()
    chk("되돌리기 단추: 채우기 앞으로 · 판 빛깔도", ed.pixels == before and fill_of(ed, 23, 23) in ui_flag.CHECK
        and p1_at(ed, 23, 23) is None and ed.b_redo.enabled)
    ed.b_redo.command()
    chk("  다시 하기 단추: 채운 그림으로", ed.pixels == filled and not ed.b_redo.enabled)
    mac = ed.mac
    mod = ui_flag.key_action
    chk("글쇠: 맥 ⌘Z 되돌리기 · ⌘⇧Z 다시 하기 · ⌘Y 다시 하기", mod("z", "z", 0, False, True) == "undo"
        and mod("Z", "Z", 0, True, True) == "redo" and mod("y", "y", 0, False, True) == "redo")
    chk("  윈도우 Ctrl+Z · Ctrl+Y · Ctrl+Shift+Z", mod("z", "\x1a", 90, False, False) == "undo"
        and mod("y", "\x19", 89, False, False) == "redo" and mod("Z", "", 90, True, False) == "redo")
    chk("  한글 자판 (ㅋ = Z 자리 · ㅛ = Y 자리, 글자 · 자리로)", mod("ㅋ", "ㅋ", 0, False, True) == "undo"
        and mod("??", "", (16 << 24) | ord("ㅛ"), False, True) == "redo"
        and mod("??", "", 6 << 24, True, True) == "redo" and mod("Hangul", "", 90, False, False) == "undo")
    chk("  다른 글쇠는 아무것도 아니다 (⌘C 등)", mod("c", "c", 8 << 24, False, True) is None
        and mod("v", "\x16", 86, False, False) is None)
    st = 0x1                                                     # Shift
    r1 = ed._on_key(Key("z", "z", 90 if not mac else (6 << 24) | ord("z")))
    chk("창의 글쇠: Z = 되돌리기", r1 == "break" and ed.pixels == before, r1)
    r2 = ed._on_key(Key("Z", "Z", 90 if not mac else (6 << 24) | ord("Z"), state=st))
    chk("  Shift+Z = 다시 하기", r2 == "break" and ed.pixels == filled, r2)
    r3 = ed._on_key(Key("c", "c", 67 if not mac else (8 << 24) | ord("c")))
    chk("  다른 글쇠는 그냥 둔다", r3 is None and ed.pixels == filled)
    binds = ed.win.bind()
    chk("  창에 글쇠가 걸려 있다 (%s)" % ("⌘" if mac else "Ctrl"),
        any(("Mod1-Key" if mac else "Control-Key") in b for b in binds), binds)
    ed.b_clear.command()
    settle(root, 0.05)
    chk("모두 지우기: 576칸 다 투명 · 모두 지우기가 죽는다", ed.pixels == F.BLANK and not ed.b_clear.enabled
        and all(fill_of(ed, x, y) in ui_flag.CHECK for x, y in ((0, 0), (9, 12), (23, 23))))
    ed.undo()
    chk("  되돌리면 돌아온다", ed.pixels == filled and ed.b_clear.enabled)
    k = len(ed.undo_stack)
    ed.b_clear.command()
    ed.b_clear.command()                                         # 빈 판을 또 지워도 걸음이 늘지 않는다
    chk("  빈 판을 또 지워도 걸음이 늘지 않는다", len(ed.undo_stack) == k + 1, (k, len(ed.undo_stack)))
    ed.undo()
    chk("도형 수 그대로 (되돌리기 · 지우기도 빛깔만)", len(ed.board.find_all()) == 576)

    print("\n=== 4. 저장 ===")
    chk("창이 내용만큼 (눌린 위젯 없음)", not squeezed(ed.win), squeezed(ed.win)[:3])
    ed.win.update_idletasks()
    chk("  창 크기 >= 내용이 바라는 크기", ed.win.winfo_width() >= ed.win.winfo_reqwidth() - 1
        and ed.win.winfo_height() >= ed.win.winfo_reqheight() - 1,
        (ed.win.winfo_width(), ed.win.winfo_reqwidth(), ed.win.winfo_height(), ed.win.winfo_reqheight()))
    ed.b_save.command()
    wait(root, lambda: saved)
    settle(root, 0.1)
    chk("저장: 서버로 576자 그대로 (api.guild_flag)", app.api.sent == [filled] and len(app.api.sent[0]) == 576
        and F.valid(app.api.sent[0]), [len(x) for x in app.api.sent])
    chk("  저장한 뒤: 안 저장한 것 없음 · 저장이 죽고 '저장했습니다' · on_saved(서버 답)",
        not ed.dirty() and not ed.b_save.enabled and "저장했습니다" in ed.status._label.cget("text")
        and saved and saved[0]["guild"]["flag"] == filled, ed.status._label.cget("text"))
    ed.save()
    settle(root, 0.1)
    chk("  바뀐 것이 없으면 안 보낸다 (길드 채팅에 괜히 안 뜨게)", len(app.api.sent) == 1
        and "바뀐 것이 없습니다" in ed.status._label.cget("text"))
    app.api.fail = "길드 깃발은 마스터 · 부마스터만 그릴 수 있습니다."
    click(ed, 0, 23)
    ed.save()
    wait(root, lambda: len(app.api.sent) == 2)
    settle(root, 0.2)
    chk("서버가 막으면 그 글을 띄우고 안 저장한 채로 (저장 단추 산다)",
        app.api.fail in ed.status._label.cget("text") and ed.dirty() and ed.b_save.enabled and len(saved) == 1,
        ed.status._label.cget("text"))
    app.api.fail = None
    ed.b_clear.command()
    del asked[:]
    answer["v"] = False
    ed.save()
    settle(root, 0.1)
    chk("다 지우고 저장: 먼저 묻는다 (깃발이 내려간다) - 아니오면 안 보낸다",
        len(asked) == 1 and "내려" in asked[0] and len(app.api.sent) == 2, asked)
    answer["v"] = True
    ed.save()
    wait(root, lambda: len(app.api.sent) == 3)
    settle(root, 0.1)
    chk("  예면 576자 '.' 를 보낸다 · '내렸습니다'", app.api.sent[-1] == "." * 576
        and "내렸습니다" in ed.status._label.cget("text") and not ed.dirty())

    print("\n=== 5. 닫기 ===")
    click(ed, 5, 5)
    del asked[:]
    answer["v"] = False
    ed.b_close.command()
    settle(root, 0.1)
    chk("안 저장한 것이 있으면 묻고, 아니오면 그대로", len(asked) == 1 and asked[0] == ui_flag.UNSAVED
        and ed.alive and ed.win.winfo_exists())
    answer["v"] = True
    ed.close()
    settle(root, 0.1)
    chk("  예면 닫힌다", not ed.alive and not ed.win.winfo_exists())
    del asked[:]
    ed2 = ui_flag.FlagEditor(root, app, "틀린 깃발")
    settle(root, 0.2)
    chk("틀린 깃발이면 빈 판으로 시작", ed2.pixels == F.BLANK and not ed2.dirty())
    ed2.close()
    settle(root, 0.1)
    chk("  안 저장한 것이 없으면 묻지 않고 닫힌다", not asked and not ed2.alive)

    chk("Tk 콜백에서 난 오류가 없다", not errors, errors[:2])
    root.update()
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
