# -*- coding: utf-8 -*-
"""길드 창의 길드 깃발 (2.5.0, 시즌 6) — 진짜 Tk 로 확인. 서버 없이 돈다.

    python3 client/test_guild_flag_ui.py
    POKET_SKIN=dp python3 client/test_guild_flag_ui.py

설계: design-notes/2026-11-14-guild-flag.md '앱'. 서버는 /api/guild 의 guild 에 flag(문자열|null) · canFlag(마스터 ·
부마스터 - 사는 것 없이, 11/15 사용자), 다른 길드 목록 줄에 flag 를 싣는다. 규칙은 server/test_guild_flag.py 가 본다. 여기서는 **길드 창**을 본다 (그리기 창 자체는 test_flag_editor_ui.py):

  1. 머리의 길드 이름 옆에 깃발 (없으면 이름만, 자리를 비우지 않는다).
  2. 다른 길드 목록의 이름 옆에 그 길드 깃발 (있는 길드만).
  3. '관리' 탭: 마스터 · 부마스터(canFlag)는 [깃발 그리기], 일반 길드원은 안내 ("길드 마스터 · 부마스터가 그립니다").
     옛 서버(canFlag 가 없다)면 칸 자체가 없다.
  4. [깃발 그리기] -> 지금 깃발로 시작하는 그리기 창 (하나만) -> 저장하면 서버로 576자, 길드 창을 다시 받아 깃발이 바뀐다.
  기본 · DP 테마 둘 다. Tk 오류 없음.

서버 흉내 · 창 여는 법은 test_guild_ui 의 FakeServer / Api / FakeApp 을 쓴다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-guild-flag-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import test_guild_ui as TG                                  # noqa: E402
from common import flag as F                               # noqa: E402
from poketdesktop import flag_art                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_box, ui_common as U, ui_guild   # noqa: E402
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


def art(seed):
    """시험용 깃발: 대각선 한 줄 + 왼쪽 위 네모 (seed 번 빛깔)."""
    px = F.BLANK
    for i in range(F.SIZE):
        px = F.put(px, i, i, seed % 32)
    for x in range(4):
        for y in range(4):
            px = F.put(px, x, y, (seed + 5) % 32)
    return px


FLAG1, FLAG2, OTHER = art(1), art(9), art(20)


class Server(TG.FakeServer):
    def __init__(self):
        TG.FakeServer.__init__(self)
        self.flag = None              # 우리 길드 깃발
        self.old = False              # 옛 서버 (flag · canFlag 를 안 싣는다)


class Api(TG.Api):
    """test_guild_ui 의 가짜 api + 길드 깃발 (2.5.0)."""

    def guild(self):
        s, me = self.s, self.me
        r = TG.Api.guild(self)
        if s.old or not r.get("guild"):
            return r
        r["guild"]["flag"] = s.flag
        r["canFlag"] = r["role"] in ("master", "sub")
        return r

    def guild_list(self, q="", page=1):
        r = TG.Api.guild_list(self, q, page)
        for g in r["guilds"]:
            if g["id"] == 1 and not self.s.old:
                g["flag"] = self.s.flag
        return r

    def guild_flag(self, pixels):
        s, me = self.s, self.me
        s.calls.append(("flag", pixels))
        if s.roles.get(me) not in ("master", "sub"):
            s.fail("길드 깃발은 마스터 · 부마스터만 그릴 수 있습니다.", 403)
        if not F.valid(pixels):
            s.fail("깃발 그림이 올바르지 않습니다.")
        s.flag = None if F.is_blank(pixels) else pixels
        return self.guild()


def norm(t):
    return "".join(str(t).split())


def scan(w):
    """창 안에 보이는 글 (라벨 · 캔버스에 그린 글)."""
    out = []

    def walk(x):
        for c in x.winfo_children():
            try:
                cls = c.winfo_class()
                if cls == "Canvas" and c.winfo_ismapped():
                    for i in c.find_all():
                        if c.type(i) == "text" and c.itemcget(i, "text"):
                            out.append(c.itemcget(i, "text"))
                elif cls == "Label" and c.winfo_ismapped() and str(c.cget("text")):
                    out.append(str(c.cget("text")))
            except tk.TclError:
                pass
            if cls != "Toplevel":
                walk(c)
    walk(w)
    return out


def has(rows, text):
    k = norm(text)
    return any(k in norm(t) for t in rows)


def images(w):
    """창 안의 그림 이름들 (라벨의 그림 · 캔버스의 그림). 다른 창(그리기 창)은 안 본다."""
    out = []

    def walk(x):
        for c in x.winfo_children():
            try:
                cls = c.winfo_class()
                if cls == "Toplevel":
                    continue
                if cls == "Label" and c.winfo_ismapped() and str(c.cget("image")):
                    out.append(str(c.cget("image")))
                elif cls == "Canvas" and c.winfo_ismapped():
                    out.extend(c.itemcget(i, "image") for i in c.find_all() if c.type(i) == "image")
            except tk.TclError:
                pass
            walk(c)
    walk(w)
    return out


def overflow(w):
    """캔버스 밖으로 나간 그린 글 (DP 의 깃발 판 · 목록 · 관리 · 상점) - [(글, 오른쪽 끝, 캔버스 폭)]."""
    out = []

    def walk(x):
        for c in x.winfo_children():
            if c.winfo_class() == "Toplevel":
                continue
            if c.winfo_class() == "Canvas" and c.winfo_ismapped():
                cw = c.winfo_width()
                for i in c.find_all():
                    if c.type(i) in ("text", "image"):
                        b = c.bbox(i)
                        if b and b[0] > -9000 and b[2] > cw + 1:
                            out.append((c.itemcget(i, "text")[:20] if c.type(i) == "text" else "그림", b[2], cw))
            walk(c)
    walk(w)
    return out


def img(root, pixels, scale=1):
    return str(flag_art.image(root, pixels, scale))


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda *a: errors.append(a)
    ui_guild.CHAT_MS = 150
    ui_box.confirm = lambda *a, **k: True
    print("테마 %s · 글꼴 %s / 본문 %dpt" % (skins.active(), U.FAMILY, U.FONT[1]))

    srv = Server()
    srv.g = {"name": "피카단", "intro": "", "mode": "open", "master": 1, "points": 0}
    srv.roles = {1: "master", 2: "member"}
    srv.coin[1] = 1200
    srv.flag = FLAG1
    srv.others = [{"id": 2, "name": "꼬부기단", "intro": "", "joinMode": "open", "masterName": "다솜", "members": 3,
                   "max": 15, "points": 10, "full": False, "flag": OTHER},
                  {"id": 3, "name": "깃발없는단", "intro": "", "joinMode": "open", "masterName": "누구", "members": 1,
                   "max": 15, "points": 0, "full": False, "flag": None}]
    app = TG.FakeApp(root, Api(srv, 1))
    w = ui_guild.GuildWindow(app)
    top = w.win.winfo_toplevel()
    top.deiconify()
    top.geometry("1000x680+60+40")
    TG.wait(root, lambda: w.data is not None and w.mode == "guild")
    TG.settle(root, 0.4)

    def reload():
        n = srv.calls.count("guild")
        w.load()
        TG.wait(root, lambda: srv.calls.count("guild") > n, 4)
        TG.settle(root, 0.4)

    print("=== 1. 머리의 길드 이름 옆 깃발 ===")
    chk("깃발이 있으면 이름 옆에 (1배 24px)", img(root, FLAG1) in images(w.win), images(w.win))
    if skins.active() == "default":
        chk("  (기본 테마) 이름 바로 왼쪽", w.flag_head is not None and str(w.flag_head.cget("image")) == img(root, FLAG1)
            and w.flag_head.winfo_reqwidth() == 24)
    srv.g["name"] = "가나다라마바사아자차카타"                     # 가장 긴 이름 (12자) + 깃발
    reload()
    chk("  가장 긴 이름에 깃발이 붙어도 판 밖으로 안 나간다", img(root, FLAG1) in images(w.win) and not overflow(w.win),
        overflow(w.win)[:3])
    chk("  눌린 위젯 없음", not squeezed(top), squeezed(top)[:3])
    srv.g["name"] = "피카단"
    srv.flag = None
    reload()
    chk("  깃발이 없으면 이름만 (깃발 그림 없음)", img(root, FLAG1) not in images(w.win)
        and not any(i in images(w.win) for i in (img(root, FLAG2), img(root, OTHER))), images(w.win))
    srv.flag = FLAG1
    reload()

    print("\n=== 2. 다른 길드 목록 ===")
    w.show_tab("guilds")
    TG.wait(root, lambda: w.found is not None, 4)
    TG.settle(root, 0.4)
    ims = images(w.content)
    chk("깃발이 있는 길드는 이름 옆에 그 깃발 (우리 길드 · 꼬부기단)", img(root, FLAG1) in ims and img(root, OTHER) in ims,
        ims)
    chk("  판 밖으로 나간 글 · 그림이 없다", not overflow(w.win), overflow(w.win)[:3])
    chk("  깃발이 없는 길드는 그림 없이 (깃발 그림 2개뿐)",
        len([i for i in ims if i in (img(root, FLAG1), img(root, OTHER))]) == 2 and has(scan(w.content), "깃발없는단"),
        ims)

    print("\n=== 3. 관리 탭 ===")
    w.show_tab("manage")
    TG.settle(root, 0.4)
    rows = scan(w.content)
    chk("마스터는 사는 것 없이 [깃발 그리기] · 설명 · 지금 깃발 2배",
        w.b_flag is not None and has(rows, "길드 깃발") and has(rows, ui_guild.GuildWindow.FLAG_CAN)
        and img(root, FLAG1, 2) in images(w.content), (w.b_flag, [t for t in rows if "깃발" in t]))
    chk("  눌린 위젯 없음 · 판 밖으로 나간 것 없음", not squeezed(top) and not overflow(w.win),
        (squeezed(top)[:3], overflow(w.win)[:3]))
    srv.roles[1] = "sub"
    srv.g["master"] = 2
    srv.roles[2] = "master"
    reload()
    rows = scan(w.content)
    chk("부마스터도 [깃발 그리기]", w.b_flag is not None and has(rows, ui_guild.GuildWindow.FLAG_CAN),
        (w.b_flag, [t for t in rows if "깃발" in t]))
    srv.roles[1] = "member"
    srv.flag = None
    reload()
    rows = scan(w.content)
    chk("길드원: 단추 없이 안내 · 깃발이 없으면 '아직 길드 깃발이 없습니다'", w.b_flag is None
        and has(rows, ui_guild.GuildWindow.FLAG_NONE + ui_guild.GuildWindow.FLAG_NOTE), [t for t in rows if "깃발" in t])
    srv.old = True
    reload()
    rows = scan(w.content)
    chk("옛 서버 (canFlag 없음): 길드 깃발 칸이 없다", w.b_flag is None and not has(rows, "길드 깃발")
        and has(rows, "길드 나가기"), [t for t in rows if "깃발" in t])
    srv.old = False
    srv.roles = {1: "master", 2: "member"}
    srv.g["master"] = 1
    srv.flag = FLAG1
    reload()

    print("\n=== 4. 깃발 그리기 -> 저장 -> 다시 받기 ===")
    w.b_flag.command()
    TG.settle(root, 0.4)
    ed = w.flag_win
    chk("[깃발 그리기]: 지금 깃발로 시작하는 그리기 창", ed is not None and ed.alive and ed.pixels == FLAG1
        and ed.win.winfo_exists())
    chk("  한 번 더 눌러도 창은 하나 (앞으로)", w.flag_editor() is ed)
    ed.pick_color(9)
    ed.set_tool("fill")
    ed.press_cell(23, 0)                                        # 투명 칸을 모두 9번으로
    ed.set_tool("pen")
    ed.press_cell(5, 5)
    ed.drag_cell(7, 5)
    ed.end_stroke()
    new = ed.pixels
    n_guild = srv.calls.count("guild")
    ed.save()
    TG.wait(root, lambda: srv.calls.count("guild") > n_guild + 1, 4)   # 저장 답(길드 정보) + 길드 창이 다시 받음
    TG.settle(root, 0.4)
    sent = [c[1] for c in srv.calls if isinstance(c, tuple) and c[0] == "flag"]
    chk("저장: 서버로 576자 (그린 그대로)", sent == [new] and len(new) == 576 and new != FLAG1, [len(x) for x in sent])
    chk("  길드 창을 다시 받아 머리 깃발이 바뀐다", img(root, new) in images(w.win) and img(root, FLAG1) not in images(w.win),
        images(w.win))
    chk("  관리 칸의 2배 깃발도 새 그림", img(root, new, 2) in images(w.content) and w.tab == "manage")
    chk("  그리기 창은 그대로 (안 저장한 것 없음)", ed.alive and not ed.dirty())
    ed.close()
    TG.settle(root, 0.2)

    chk("Tk 콜백에서 난 오류가 없다", not errors, errors[:2])
    w.close()
    root.update()
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
