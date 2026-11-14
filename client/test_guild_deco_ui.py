# -*- coding: utf-8 -*-
"""길드 코인 상점 '길드 전용' 꾸미기 (2.5.0) - 앱 쪽. 진짜 Tk 로 확인한다. 서버 없이 돈다.

    python3 client/test_guild_deco_ui.py
    POKET_SKIN=dp python3 client/test_guild_deco_ui.py

규칙(값 · 수 · 고르기 · decoFlag)은 server/test_guild_deco_shop.py 가 본다. 여기서는 **그림과 화면**을 본다:
  1. 깃대 깃발 그림 (deco_art.banner): 깃대 쪽 · 깃발 칸이 그린 그대로(뒤집지 않음) · 펄럭임은 한 칸 안 · 빈 그림은 None.
  2. 효과 창(deco_fx.Trail)이 그리는 자리: 깃발 들기 + decoFlag 면 몸 뒤쪽에 깃대가 서고 깃발 위 끝이 머리보다 위,
     옆으로 걸은 쪽에 따라 깃대가 반대편으로, decoFlag 가 없거나 깃발 들기를 안 쓰면 아무것도 안 그린다.
  3. 꾸미기 창(ui_deco): 깃발 들기는 '깃발' 줄에, 꾸미기 선택권 [고르기...] → 고르는 창 → 서버로 고른 열쇠,
     고를 것이 없으면 단추가 죽는다.
  4. 가방 꾸미기 주머니(ui_bag.deco_items): 꾸미기 선택권이 도구처럼 (장수 · 고를 것).
  5. 길드 코인 상점: 깃발 들기 '한 번 사면 계속 · 아직 없음' → 사면 '가지고 있음' 으로 단추가 죽는다 ·
     꾸미기 선택권 '이번 시즌 1 / 1개 남음' · 두 줄 다 그림이 있다 · 판 밖으로 나간 글 없음 · Tk 오류 없음.
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-guild-deco-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import test_guild_shop_exclusive_ui as GX                   # noqa: E402  (코인 상점 '길드 전용' 흉내)
import test_guild_ui as TG                                  # noqa: E402
from common import deco as C                                # noqa: E402
from common import flag as F                                # noqa: E402
from poketdesktop import deco_art as ART                    # noqa: E402
from poketdesktop import deco_fx                            # noqa: E402
from poketdesktop import item_icons                         # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_bag, ui_box, ui_common as U, ui_deco, ui_guild   # noqa: E402
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


def settle(root, sec):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def art():
    """시험 깃발: 왼쪽 위 칸만 9번(초록), 오른쪽 아래 칸만 3번 - 뒤집히면 자리가 바뀐다."""
    px = F.BLANK
    px = F.put(px, 0, 0, 9)
    px = F.put(px, F.SIZE - 1, F.SIZE - 1, 3)
    for x in range(1, F.SIZE - 1):
        px = F.put(px, x, 5, 20)
    return px


def rgb(c):
    return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), 255)


FLAG = art()
GREEN, CORNER = rgb(F.PALETTE[9]), rgb(F.PALETTE[3])


def find(im, color):
    """그림에서 그 빛깔 칸들의 x 목록."""
    w, h = im.size
    px = im.load()
    return [(x, y) for y in range(h) for x in range(w) if px[x, y] == color]


# ---------------------------------------------------------------- 1. 깃대 깃발 그림
def banner_part():
    print("=== 1. 깃대 깃발 그림 ===")
    im = ART.banner(FLAG, 40, 1, 0)
    chk("깃대 오른쪽으로 날리는 그림: 폭 = 깃대 2 + 깃발 24 + 1, 높이 = 구슬 3 + 깃대 40",
        im is not None and im.size == (27, 43), im and im.size)
    chk("  깃대가 왼쪽 두 칸 (아래 끝까지)", im.getpixel((0, 42))[3] == 255 and im.getpixel((1, 42))[3] == 255
        and im.getpixel((2, 42))[3] == 0)
    chk("  깃발 왼쪽 위 칸(9번)이 깃대 바로 옆 · 오른쪽 아래 칸(3번)이 먼 끝 - 그린 그대로",
        find(im, GREEN) == [(2, ART.KNOB_H)] and find(im, CORNER)[0][0] == 2 + F.SIZE - 1, (find(im, GREEN), find(im, CORNER)))
    im2 = ART.banner(FLAG, 40, -1, 0)
    chk("반대쪽: 깃대가 오른쪽 두 칸, 깃발은 **뒤집지 않고** 깃대 왼쪽 (9번이 왼쪽 위 그대로)",
        im2.getpixel((26, 42))[3] == 255 and im2.getpixel((0, 42))[3] == 0
        and find(im2, GREEN) == [(1, ART.KNOB_H)] and find(im2, CORNER)[0][0] == F.SIZE, (find(im2, GREEN),))
    ys = set()
    for wave in range(4):
        w = ART.banner(FLAG, 40, 1, wave)
        ys.update(y for _x, y in find(w, rgb(F.PALETTE[20])))
    chk("펄럭임: 가운데 줄이 위아래로 한 칸 안에서만", ys and max(ys) - min(ys) <= 2 and min(ys) >= ART.KNOB_H + 4, sorted(ys))
    chk("  깃대 쪽 줄은 안 흔들린다 (9번 칸 자리 그대로)",
        all(find(ART.banner(FLAG, 40, 1, wv), GREEN) == [(2, ART.KNOB_H)] for wv in range(4)))
    chk("빈 그림 · 틀린 그림 · 없음 → None", ART.banner(F.BLANK, 40) is None and ART.banner("x" * 5, 40) is None
        and ART.banner(None, 40) is None)
    chk("깃대가 깃발보다 짧게 오면 깃발 + 4 로 늘린다", ART.banner(FLAG, 3).size[1] == ART.KNOB_H + F.SIZE + 4)
    chk("칸 그림: 깃발 들기 · 꾸미기 선택권", ART.item_icon("guild_flag", 40) is not None
        and ART.item_icon(C.PICK_DECO, 40) is not None and ART.icon("guild_flag") is not None)


# ---------------------------------------------------------------- 2. 효과 창이 그리는 자리
class Pet(object):
    def __init__(self, flag):
        self.fw, self.fh = 40, 48
        self.mon = {"decoFlag": flag}


def trail(keys, flag, side=1):
    t = deco_fx.Trail.__new__(deco_fx.Trail)
    t.pet, t.keys, t.parts, t.tick, t.k = Pet(flag), tuple(keys), [], 0, 1
    t.W, t.H, t.ox, t.oy, t.flag_side = 320, 200, 0, 0, side
    return t


def trail_part():
    print("\n=== 2. 효과 창이 그리는 자리 ===")
    fx, fy = 160.0, 150.0
    t = trail(("guild_flag",), FLAG)
    chk("flag(): 깃발 들기 + decoFlag → 그 깃발", t.flag() == FLAG)
    chk("  깃발 들기를 안 쓰면 None", trail(("fx_paw",), FLAG).flag() is None)
    chk("  decoFlag 가 없으면 (길드 깃발 없음) None", trail(("guild_flag",), None).flag() is None)
    im = t.compose(fx, fy, False, FLAG)
    g = find(im, GREEN)
    pole = fx + max(6.0, 40 * deco_fx.FLAG_BACK)
    chk("몸 뒤쪽(오른쪽)에 깃대 · 깃발이 깃대 바로 옆", g and abs(g[0][0] - (pole + 1)) <= 2, (g, pole))
    top = min(y for _x, y in find(im, rgb(F.PALETTE[20])) + g)
    chk("  깃발 위 끝이 몸 칸 위 끝보다 위 (머리 위로 보인다)", top < fy - 48, (top, fy - 48))
    corner = find(im, CORNER)
    chk("  깃발이 깃대에서 바깥쪽으로 (몸을 덮지 않는 쪽)", corner and corner[0][0] > g[0][0], (corner, g))
    t2 = trail(("guild_flag",), FLAG, side=-1)
    im2 = t2.compose(fx, fy, False, FLAG)
    g2, c2 = find(im2, GREEN), find(im2, CORNER)
    chk("오른쪽으로 걸으면(몸 뒤 = 왼쪽) 깃대가 왼쪽 · 깃발은 그린 그대로 (9번이 왼쪽)",
        g2 and c2 and c2[0][0] < fx and g2[0][0] < c2[0][0], (g2, c2))
    empty = trail(("guild_flag",), None).compose(fx, fy, False, None)
    chk("decoFlag 가 없으면 아무것도 안 그린다", empty.getbbox() is None, empty.getbbox())
    t.tick = deco_fx.WAVE_TICKS
    chk("펄럭임 박자가 바뀌면 다른 그림", t.compose(fx, fy, False, FLAG).tobytes() != im.tobytes())


# ---------------------------------------------------------------- 3. 꾸미기 창
class DecoApi(object):
    def __init__(self, owned, dpicks, choices):
        self.owned = set(owned)
        self.dpicks = dpicks
        self.choices = list(choices)
        self.calls = []

    def deco_state(self):
        return {"items": [{"key": k, "kr": d["kr"], "slot": d["slot"], "owned": k in self.owned, "wornBy": None,
                           "effect": d["slot"] in C.EFFECTS} for k, d in C.DECOS.items()],
                "picks": 0, "choices": [], "worn": {},
                "decoPicks": self.dpicks,
                "decoChoices": [{"key": k, "kr": C.name(k), "slot": C.slot_of(k),
                                 "slotKr": C.SLOT_KR[C.slot_of(k)]} for k in self.choices if k not in self.owned]}

    def deco_pick_one(self, key):
        self.calls.append(("pickone", key))
        self.dpicks -= 1
        self.owned.add(key)
        out = self.deco_state()
        out["got"] = [C.name(key)]
        return out


class MiniApp(object):
    def __init__(self, root, api):
        self.root, self.api = root, api


def deco_window_part(root):
    print("\n=== 3. 꾸미기 창 (테마 %s) ===" % skins.active())
    api = DecoApi(["guild_flag", "bow"], 1, C.pick_pool())
    m = {"id": 1, "num": 25, "species": "PIKACHU", "deco": {}, "info": {"name": "피카츄"}}
    w = ui_deco.DecoWindow(MiniApp(root, api), m)
    settle(root, 0.4)
    chk("깃발 들기 칸이 있다 (가진 것)", "guild_flag" in w.cells and "bow" in w.cells, sorted(w.cells))
    titles = [c.cget("text") for c in w.grid.winfo_children() if c.winfo_class() == "Label"]
    chk("  '깃발' 줄 머리 (장식 · 깃발)", "깃발" in titles and "장식" in titles, titles)
    chk("꾸미기 선택권 띠 · [고르기...] 단추", w.pick_box.winfo_ismapped() and w.b_pick_deco is not None
        and enabled(w.b_pick_deco))
    asked = []
    real = ui_box.ask_choice

    def fake(parent, title, msg, opts):
        asked.append((title, [o[0] for o in opts]))
        return "fx_snow"
    ui_box.ask_choice = fake
    try:
        w.b_pick_deco.command()
        settle(root, 0.4)
    finally:
        ui_box.ask_choice = real
    chk("  누르면 고르는 창 - 아직 없는 것만 (가진 리본은 없다)", asked and asked[0][0] == C.PICK_DECO_KR
        and "bow" not in asked[0][1] and "fx_snow" in asked[0][1] and "guild_flag" not in asked[0][1], asked)
    chk("  고른 열쇠가 서버로 · 받은 것을 알린다 · 띠가 사라진다", api.calls == [("pickone", "fx_snow")]
        and "눈송이" in w.status.cget("text") and not w.pick_box.winfo_ismapped(), (api.calls, w.status.cget("text")))
    w.desc.configure(text="")
    w.show_desc("guild_flag")
    chk("  깃발 들기 설명 (깃발 칸)", "깃발 들기 (깃발)" in w.desc.cget("text"), w.desc.cget("text"))
    w.close()
    full = DecoApi(list(C.pick_pool()), 1, C.pick_pool())
    w2 = ui_deco.DecoWindow(MiniApp(root, full), dict(m))
    settle(root, 0.4)
    chk("고를 꾸미기가 없으면 [고르기...] 가 죽는다 · 그렇다고 적는다", w2.b_pick_deco is not None
        and not enabled(w2.b_pick_deco)
        and any("남지 않았" in str(x.cget("text")) for r in w2.pick_box.winfo_children()
                for x in r.winfo_children() if x.winfo_class() == "Label"))
    chk("  where(): 꾸미기 선택권 · 길드 코인 상점", "꾸미기 선택권" in ui_deco.where("shades")
        and "길드 코인 상점" in ui_deco.where("guild_flag") and "랜덤 캡슐" not in ui_deco.where("guild_flag"))
    w2.close()


# ---------------------------------------------------------------- 4. 가방 꾸미기 주머니
def bag_part():
    print("\n=== 4. 가방 꾸미기 주머니 ===")
    st = DecoApi(["guild_flag"], 2, C.pick_pool()).deco_state()
    items, bag, _worn = ui_bag.deco_items(st)
    ids = dict((it["id"], it) for it in items)
    pk = ids.get(ART.ITEM_PREFIX + C.PICK_DECO)
    chk("꾸미기 선택권이 도구처럼 · 장수 2", pk is not None and bag[pk["id"]] == 2 and pk["kr"] == C.PICK_DECO_KR, bag)
    chk("  쓰면 고르는 것 (decopick · one · 고를 것)", pk and pk["effect"]["kind"] == "decopick"
        and pk["effect"]["one"] is True and len(pk["effect"]["choices"]) == len(C.pick_pool()))
    chk("  깃발 들기도 주머니에 (깃발 칸 설명)", ART.ITEM_PREFIX + "guild_flag" in ids
        and "깃발" in ids[ART.ITEM_PREFIX + "guild_flag"]["note"])
    chk("  둘 다 그림이 있다", item_icons._deco_key(pk["id"]) == C.PICK_DECO
        and ART.item_icon(item_icons._deco_key(pk["id"]), 32) is not None)


# ---------------------------------------------------------------- 5. 길드 코인 상점
class Api(GX.Api):
    """GX(마스터볼 · 금색병뚜껑) + 깃발 들기 · 꾸미기 선택권 줄 (서버 guild._deco_row 꼴)."""

    def guild_shop(self):
        r = GX.Api.guild_shop(self)
        s, me = self.s, self.me
        rows = [{"id": "deco:guild_flag", "kr": "깃발 들기", "cat": "deco", "sell": 0, "coin": 300,
                 "group": "길드 전용", "exclusive": True, "limit": 1, "left": 0 if s.deco.get(me) else 1,
                 "forever": True, "deco": "guild_flag", "note": C.DECOS["guild_flag"]["desc"] + " 한 번 사면 계속 쓴다."},
                {"id": "deco:pick_deco", "kr": C.PICK_DECO_KR, "cat": "deco", "sell": 0, "coin": 400,
                 "group": "길드 전용", "exclusive": True, "limit": 1, "left": 1, "forever": False,
                 "deco": C.PICK_DECO, "note": "랜덤 캡슐에서 나오는 꾸미기 가운데 아직 없는 것 하나를 고른다."}]
        n = len([x for x in r["items"] if x.get("exclusive")])
        r["items"] = r["items"][:n] + rows + r["items"][n:]
        return r

    def guild_buy(self, item, count=1):
        s, me = self.s, self.me
        if item != "deco:guild_flag":
            return GX.Api.guild_buy(self, item, count)
        s.calls.append(("buy", item, count))
        s.coin[me] -= 300
        s.deco[me] = True
        return {"ok": True, "spent": 300, "coin": s.coin[me], "message": "깃발 들기 을(를) 샀습니다!"}


def shop_part(root):
    print("\n=== 5. 길드 코인 상점 (테마 %s) ===" % skins.active())
    srv = GX.Server()
    srv.deco = {}
    srv.g = {"name": "피카단", "intro": "", "mode": "open", "master": 1, "points": 0}
    srv.roles = {1: "master", 2: "member"}
    srv.coin[1] = 900
    app = TG.FakeApp(root, Api(srv, 1))
    w = ui_guild.GuildWindow(app)
    top = w.win.winfo_toplevel()
    top.deiconify()
    top.geometry("1000x680+60+40")
    TG.wait(root, lambda: w.data is not None and w.mode == "guild")
    w.shop = None
    w.show_tab("shop")
    TG.wait(root, lambda: w.shop is not None, 4)
    settle(root, 0.4)
    rows = GX.scan(w.content)
    ids = [it["id"] for it in w.shop_shown()]
    chk("'길드 전용': 마스터볼 · 금색병뚜껑 · 깃발 들기 · 꾸미기 선택권", ids[:4] == ["MASTERBALL", "GOLDBOTTLECAP",
                                                                          "deco:guild_flag", "deco:pick_deco"], ids)
    b = w.shop_btns
    chk("깃발 들기: '한 번 사면 계속 · 아직 없음' · [1개 사기]", GX.has(rows, "한 번 사면 계속 · 아직 없음")
        and btn_text(b[("deco:guild_flag", 1)]) == "1개 사기" and enabled(b[("deco:guild_flag", 1)]),
        [t for t in rows if "계속" in t])
    chk("꾸미기 선택권: '이번 시즌 1 / 1개 남음'", GX.has(rows, "이번 시즌 1 / 1개 남음"), [t for t in rows if "시즌" in t])
    chk("  두 줄 다 그림 (꾸미기 그림을 앱이 그린다)", item_icons.photo("deco:guild_flag", 40) is not None
        and item_icons.photo("deco:pick_deco", 40) is not None)
    chk("  눌린 위젯 없음 · 판 밖으로 나간 것 없음", not squeezed(top) and not GX.overflow(w.win),
        (squeezed(top)[:3], GX.overflow(w.win)[:3]))
    n = srv.calls.count(("shop",))
    b[("deco:guild_flag", 1)].command()
    TG.wait(root, lambda: srv.calls.count(("shop",)) > n and w.shop is not None, 4)
    settle(root, 0.4)
    rows = GX.scan(w.content)
    b = w.shop_btns
    chk("사면: '한 번 사면 계속 · 가지고 있음' · 단추가 '가지고 있음' 으로 죽는다",
        ("buy", "deco:guild_flag", 1) in srv.calls and GX.has(rows, "한 번 사면 계속 · 가지고 있음")
        and btn_text(b[("deco:guild_flag", 1)]) == "가지고 있음" and not enabled(b[("deco:guild_flag", 1)]),
        [t for t in rows if "계속" in t])
    w.close()


def btn_text(b):
    return getattr(b, "text", None) or b.label.cget("text")


def enabled(b):
    got = getattr(b, "enabled", None)
    if got is not None:
        return bool(got)
    return str(b.cget("state")) != "disabled"


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
    banner_part()
    trail_part()
    deco_window_part(root)
    bag_part()
    shop_part(root)
    chk("Tk 콜백에서 난 오류가 없다", not errors, errors[:2])
    root.update()
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
