# -*- coding: utf-8 -*-
"""화면 테마 '디아루가·펄기아'(skins/dp) 검사 - 바탕화면 알림 창들 (묶음 announce).

    python client/test_skin_dp_announce.py

**창을 진짜로 띄운다.** 테마의 알림은 짓는 것만 새로 하고 동작(닫을 때 부르는 것 · 돌려주는 것 · 기다리기)은
기본 함수와 같으므로, 여기서는 'DP 로 지은 자리가 기본 동작과 맞물리나' 를 본다.

  1. POKET_SKIN=dp 면 선물 · 진화 · 부화 · 탐험 전리품 · 메가스톤 알림이 DP 판(skins/dp/announce.py)으로 뜨고,
     유대의 돌 표식은 DP 클래스(skins/dp/bond_stone.py)로 만들어진다. 기본 함수는 .base 로 남아 있다.
  2. 선물: 글상자 · 도구 줄 · 안내 · '고맙습니다' 가 닫는다. 여덟 줄까지만 그리고 '그 밖 N개'. 빈 목록은 창을 안 띄운다.
  3. 진화: 무대의 이름 꼬리표 · 글상자(배운 기술 줄) · 도트 둘이 놓인다. '좋아!' 가 닫는다. 도트를 못 받아도 예외 없이 뜬다.
  4. 부화: 창을 돌려주고(기다리지 않는다), 닫을 때 on_close 가 한 번 불린다 (단추 · 창 닫기 둘 다). 꼬리표 · 도트.
  5. 탐험 전리품: 카드(보라 띠 · 물건 줄 · 성장) · 안내 · '확인'. 창은 내용만큼만 크고, 물건이 많으면 화면 2/3 안에서
     안쪽이 굴러가며 '확인' 이 창 안에 보인다.
  6. 메가스톤: 받은 줄 · 안내 · '확인', 유대만 마친 것은 '받았습니다' 가 없다. 창을 돌려준다.
  7. 유대의 돌 표식: DP 표식이 붙고 · 반짝이고 · 누르면 기본과 같이 on_click(포켓몬, 종류) · 따라다니고 · 치우면 창이 없어진다.
  그리는 중에 난 예외가 없다.
"""
import io
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-test-skin-dp-announce-"))
os.environ["POKET_SKIN"] = "dp"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import time                                                 # noqa: E402
import tkinter as tk                                        # noqa: E402
import traceback                                            # noqa: E402

from PIL import Image, ImageDraw                            # noqa: E402

from poketdesktop import bond_stone, config, eggs_ui, overlay, skins   # noqa: E402
from poketdesktop import expedition_ui as XU                # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_bag                             # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


# ---------------------------------------------------------------- 가짜 서버
def _png(draw, size):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    draw(ImageDraw.Draw(im))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


class Api(object):
    """그림만 준다 (도트 · 도구 그림)."""

    def sprite(self, num, shiny=False):
        return _png(lambda g: g.ellipse([8, 8, 56, 56], fill=(200, 90, 60, 255), outline=(30, 30, 40, 255)),
                    (64, 64)), ".png"

    def item_sprite(self, item):
        return _png(lambda g: g.ellipse([4, 4, 28, 28], fill=(60, 110, 220, 255), outline=(30, 30, 40, 255)),
                    (32, 32))


class App(object):
    def __init__(self, api):
        self.api = api

    def notify(self, m):
        pass


def pump(root, cond, sec=5.0):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.02)
    return False


# ---------------------------------------------------------------- 창 안을 읽는다
def canvases(w):
    out = []
    for c in w.winfo_children():
        if isinstance(c, tk.Canvas):
            out.append(c)
        out.extend(canvases(c))
    return out


def said(win):
    """창 안 캔버스의 모든 글 (줄바꿈은 띄어쓰기로)."""
    out = []
    for cv in canvases(win):
        for i in cv.find_all():
            if cv.type(i) == "text":
                out.append(" ".join(str(cv.itemcget(i, "text")).split()))
    return out


def has(win, *words):
    t = " | ".join(said(win))
    return all(w in t for w in words)


def images(win):
    return sum(1 for cv in canvases(win) for i in cv.find_all() if cv.type(i) == "image")


def on_top(root, host):
    for w in host.winfo_children():
        if isinstance(w, tk.Toplevel) and w.winfo_viewable():
            return w
    return None


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        errors.append("".join(traceback.format_exception(exc, val, tb))[-400:])
    root.report_callback_exception = on_err
    host = tk.Toplevel(root)
    host.geometry("500x300+40+40")
    app = App(Api())
    scr = root.winfo_screenheight()

    def modal(call, inspect, hold=0.6):
        """모달 창을 띄우고 hold 초 뒤 inspect(창) 를 하고 닫는다. inspect 의 값."""
        box = {}

        def snap():
            w = on_top(root, host)
            if w is None:
                root.after(100, snap)
                return
            root.update_idletasks()
            try:
                box["v"] = inspect(w)
            except Exception:                               # noqa: BLE001
                box["err"] = traceback.format_exc()
            try:
                w.destroy()
            except tk.TclError:
                pass
        root.after(int(hold * 1000), snap)
        call()
        if "err" in box:
            print(box["err"])
        return box.get("v")

    print("=== 테마가 DP 로 뜬다 ===")
    v = skins.view("announce")
    chk("skins/dp/announce.py 가 읽힌다", v is not None and v.__name__.endswith("dp.announce"), v)
    chk("선물 · 진화 · 부화 · 전리품 · 스톤 알림 모두 DP 함수가 있다",
        all(hasattr(v, n) for n in ("announce_gifts", "announce_evolve", "announce_hatch", "show_loot",
                                    "announce_got")))
    chk("기본 함수는 .base 로 남는다", all(hasattr(f, "base") for f in (
        ui_bag.announce_gifts, ui_bag.announce_evolve, eggs_ui.announce_hatch, XU.show_loot,
        bond_stone.announce_got)))
    chk("유대의 돌 표식은 DP 클래스", skins.override(bond_stone.StoneBadge).__module__.endswith("dp.bond_stone"))

    print("\n=== 선물 ===")
    gifts = [
        {"kind": "item", "item": "FLOWERBALL", "count": 1, "name": "플라워볼", "title": "50명 기념 선물",
         "message": "함께해 주셔서 고맙습니다!"},
        {"kind": "money", "item": None, "count": 5000, "name": "돈"},
        {"kind": "balls", "item": None, "count": 5, "name": "몬스터볼"},
        {"kind": "egg", "item": "legendary", "count": 1, "name": "전설의 알"},
        {"kind": "title", "name": "탑 트레이너"},
    ]
    st = {}

    def look(w):
        pump(root, lambda: images(w) >= 2, 3)
        st["said"], st["size"], st["req"] = said(w), (w.winfo_width(), w.winfo_height()), w.winfo_reqheight()
        st["images"] = images(w)
        st["btn"] = [b.text for b in getattr(w, "buttons", ())]
        w.buttons[0].invoke()                                # 눌러서 닫는다
        return True
    t0 = time.time()
    modal(lambda: ui_bag.announce_gifts(host, app, gifts), look)
    t = " | ".join(st.get("said", []))
    chk("글상자 · 제목 · 메시지 · 도구 줄 · 돈은 원으로", "선물이 도착했습니다!" in t and "50명 기념 선물" in t
        and "함께해 주셔서 고맙습니다!" in t and "플라워볼 ×1" in t and "5,000원" in t and "칭호 · 탑 트레이너" in t, t)
    chk("  안내 글 (알 · 칭호)", "게임을 켜 둔 시간만큼" in t and "마이페이지에서" in t, t)
    chk("  도구 그림이 놓인다 (받아 온 것)", st.get("images", 0) >= 2, st.get("images"))
    chk("  '고맙습니다' 단추가 창을 닫는다 (기다리던 호출이 돌아온다)", st.get("btn") == ["고맙습니다"] and time.time() - t0 < 20)
    chk("  창은 내용만큼만 크고 화면 안", abs(st["size"][1] - st["req"]) <= 4 and st["size"][1] < scr,
        (st.get("size"), st.get("req"), scr))
    many = [dict(gifts[1], count=i + 1) for i in range(12)]
    modal(lambda: ui_bag.announce_gifts(host, app, many), look)
    t = " | ".join(st.get("said", []))
    chk("여덟 줄까지만 그리고 '그 밖 4개'", "8원" in t and "9원" not in t and "그 밖 4개" in t, t)
    long = [dict(gifts[0], title="아주 긴 제목을 넣어 봅니다 " * 3, message="설명도 길게 넣어 봅니다. " * 6)]
    modal(lambda: ui_bag.announce_gifts(host, app, long), look)
    chk("글이 길어도 접혀서 다 들어간다 (창은 내용만큼)", abs(st["size"][1] - st["req"]) <= 4, (st.get("size"), st.get("req")))
    ui_bag.announce_gifts(host, app, [])
    root.update_idletasks()
    chk("빈 목록이면 창을 안 띄운다", on_top(root, host) is None)

    print("\n=== 진화 ===")
    info = {"fromKr": "리자드", "toKr": "리자몽", "fromNum": 5, "toNum": 6, "learned": ["화염방사"],
            "pending": ["블래스트번"]}

    def look_ev(w):
        pump(root, lambda: images(w) >= 2, 4)
        st["said"], st["images"] = said(w), images(w)
        st["size"], st["req"] = (w.winfo_width(), w.winfo_height()), w.winfo_reqheight()
        w.buttons[0].invoke()
        return True
    modal(lambda: ui_bag.announce_evolve(host, app, info), look_ev)
    t = " | ".join(st.get("said", []))
    chk("축하 글상자 · 이름 꼬리표", "축하합니다!" in t and "리자드는 리자몽으로 진화했다!" in t
        and "리자드" in st["said"] and "리자몽" in st["said"], t)
    chk("  배운 기술 · 배우려는 기술 줄", "화염방사를 배웠다!" in t and "블래스트번을 배우려 한다." in t, t)
    chk("  진화 전 · 후 도트 둘이 놓이고 '...' 자리표시는 지워진다", st.get("images") == 2 and "..." not in st["said"],
        (st.get("images"), st["said"][:6]))
    chk("  창은 내용만큼만 크다", abs(st["size"][1] - st["req"]) <= 4, (st["size"], st["req"]))
    app0 = App(None)                                         # 도트를 못 받아도 뜬다
    modal(lambda: ui_bag.announce_evolve(host, app0, {"fromKr": "피카츄", "toKr": "라이츄", "fromNum": 25,
                                                       "toNum": 26}), lambda w: (root.update(), said(w))[1])
    chk("도트를 못 받으면 '...' 로 남고 예외 없이 뜬다", not errors, errors[:1])

    print("\n=== 부화 ===")
    closed = []
    egg = {"kind": "legendary", "name": "전설의 알",
           "pokemon": {"num": 448, "level": 5, "shiny": True, "onDesktop": False,
                       "info": {"name": "루카리오", "species": "루카리오"}}}
    w = eggs_ui.announce_hatch(host, app, egg, on_close=lambda: closed.append(1))
    chk("창을 돌려준다 (기다리지 않는다)", isinstance(w, tk.Toplevel) and w.winfo_exists())
    pump(root, lambda: images(w) >= 1, 4)
    t = " | ".join(said(w))
    chk("글상자 · 알 이름 · Lv · 색이 다른 개체 · 박스", "알이 부화했다!" in t and "루카리오가 태어났다!" in t
        and "전설의 알" in t and "Lv.5" in t and "★ 색이 다른 개체" in t and "파티가 꽉 차서 박스에 넣었습니다" in t, t)
    chk("  태어난 도트가 놓인다", images(w) == 1, images(w))
    chk("  창은 내용만큼만 크다", abs(w.winfo_height() - w.winfo_reqheight()) <= 4, (w.winfo_height(), w.winfo_reqheight()))
    w.buttons[0].invoke()
    root.update()
    chk("'반가워!' 가 창을 닫고 on_close 를 한 번 부른다", closed == [1] and not w.winfo_exists(), closed)
    w2 = eggs_ui.announce_hatch(host, app, dict(egg, pokemon=dict(egg["pokemon"], shiny=False, onDesktop=True)),
                                on_close=lambda: closed.append(2))
    root.update()
    t = " | ".join(said(w2))
    chk("데리고 다니면 그렇게 적는다 (색이 다른 개체 꼬리표 없음)", "데리고 다닙니다" in t and "★" not in t, t)
    root.tk.eval(root.tk.call("wm", "protocol", str(w2), "WM_DELETE_WINDOW"))   # 창 닫기 단추와 같다
    root.update()
    chk("창 닫기로도 on_close 가 불린다", 2 in closed and not w2.winfo_exists(), closed)

    print("\n=== 탐험 전리품 ===")
    claimed = [
        {"pokemon": {"name": "피카츄"}, "placeKr": "숲", "hours": 2, "grade": "great", "gradeKr": "대성공",
         "items": [{"id": "ORANBERRY", "kr": "오랭열매", "count": 2, "tier": "common"},
                   {"id": "LEAFSTONE", "kr": "리프의돌", "count": 1, "tier": "rare"}],
         "tm": {"label": "TM168 솔라빔"}, "growth": {"xp": 120, "level": 4, "levelBefore": 3, "rest": 86400}},
        {"pokemon": {"name": "팬텀"}, "placeKr": "동굴", "hours": 8, "grade": "good", "gradeKr": "성공",
         "items": [{"id": "CHOICEBAND", "kr": "구애머리띠", "count": 1, "tier": "held"}],
         "friend": {"name": "이브이", "level": 5, "num": 133, "new": True}},
        {"pokemon": {"name": "리자몽"}, "placeKr": "바다", "hours": 1, "grade": "normal", "items": [],
         "friendFull": True},
    ]

    def look_loot(w):
        pump(root, lambda: images(w) >= 3, 4)
        st["said"], st["images"] = said(w), images(w)
        st["size"], st["req"] = (w.winfo_width(), w.winfo_height()), w.winfo_reqheight()
        cv, scroll, h, avail = w.loot_scroll
        st["scroll"], st["h"], st["avail"] = scroll, h, avail
        b = w.buttons[0]
        foot = b.cv
        st["btn_in"] = foot.winfo_rooty() + b.box[3] <= w.winfo_rooty() + w.winfo_height()
        b.invoke()
        return True
    modal(lambda: XU.show_loot(host, app, claimed[:1]), look_loot)
    t = " | ".join(st.get("said", []))
    chk("글상자 · 요약 · 보라 띠 · 물건 줄 · 개수 · 등급 꼬리표", "탐험에서 돌아왔습니다!" in t
        and "물건 4개를 가져왔습니다." in t and "피카츄 · 숲 2시간" in t and "오랭열매 × 2" in t and "리프의돌" in t
        and "대성공" in t and "희귀" in t and "새 기술머신" in t and "TM168 솔라빔" in t, t)
    chk("  성장 줄 · 안내 · '확인'", "탐험 경험치 +120" in t and "24시간 동안 쉽니다" in t
        and "가방에 넣어 두었습니다." in t and "확인" in t, t)
    chk("  물건 그림이 놓인다", st.get("images", 0) >= 2, st.get("images"))
    chk("  창은 내용만큼만 크고 굴리지 않는다", not st["scroll"] and abs(st["size"][1] - st["req"]) <= 4
        and st["size"][1] < scr * 0.7 and st["size"][0] == XU.LOOT_W and st["btn_in"],
        (st["size"], st["req"], st["scroll"], st["btn_in"]))
    modal(lambda: XU.show_loot(host, app, claimed), look_loot)
    t = " | ".join(st.get("said", []))
    chk("여럿: 데려온 포켓몬 · 지닌 도구 · 아무것도 못 찾음", "Lv.5 이브이를 데려왔습니다!" in t and "도감에 새로 등록" in t
        and "구애머리띠" in t and "지닌 도구" in t and "물건 5개를 가져왔습니다. 포켓몬 1마리를 데려왔습니다." in t
        or ("이브이" in t and "구애머리띠" in t and "지닌 도구" in t), t[:300])
    many = [dict(claimed[i % 2], pokemon={"name": "포켓몬%d" % i}) for i in range(8)]
    modal(lambda: XU.show_loot(host, app, many), look_loot)
    chk("물건이 많으면 창을 키우는 대신 안쪽이 굴러가고 '확인' 이 창 안에 있다 (창 %d / 화면 %d)"
        % (st["size"][1], scr), st["scroll"] and st["size"][1] <= scr * 0.66 + 4 and st["h"] > st["avail"]
        and st["btn_in"], (st["size"], st["scroll"], st["h"], st["avail"], st["btn_in"]))
    ui_bag_none = XU.show_loot(host, app, [])
    chk("받은 것이 없으면 창을 안 띄운다", ui_bag_none is None and on_top(root, host) is None)

    print("\n=== 메가스톤 ===")
    w = bond_stone.announce_got(host, [
        {"pokemon": 1, "name": "리자몽", "stone": "CHARIZARDITEY", "stoneKr": "리자몽나이트Y"},
        {"pokemon": 3, "name": "아주길고긴별명의팬텀이", "stone": "GENGARITE", "stoneKr": "팬텀나이트"}])
    root.update()
    t = " | ".join(said(w))
    chk("창을 돌려준다 · 받은 스톤과 포켓몬 이름 · 안내", isinstance(w, tk.Toplevel) and "메가스톤을 받았습니다!" in t
        and "리자몽나이트Y" in t and "아주길고긴별명의팬텀이" in t and "가방에 넣어 두었습니다." in t, t)
    chk("  창은 내용만큼만 크고 화면 안", abs(w.winfo_height() - w.winfo_reqheight()) <= 4
        and w.winfo_height() < scr, (w.winfo_height(), w.winfo_reqheight()))
    w.buttons[0].invoke()
    root.update()
    chk("  '확인' 이 닫는다", not w.winfo_exists())
    w = bond_stone.announce_got(host, [{"pokemon": 5, "name": "팬텀", "stone": None, "stoneKr": None,
                                        "bondOnly": True}])
    root.update()
    t = " | ".join(said(w))
    chk("유대만 마친 알림: 스톤을 받았다고 하지 않는다", "유대 미션을 마쳤습니다!" in t and "팬텀" in t
        and "메가진화할 수 있" in t and "받았습니다" not in t, t)
    w.destroy()
    chk("빈 목록이면 None", bond_stone.announce_got(host, []) is None)

    print("\n=== 유대의 돌 표식 ===")
    import test_bond_stone as TB
    settings = dict(config.DEFAULTS)
    settings["showNames"] = True
    ov = overlay.Overlay(root, settings)
    paths = {(6, False): TB.dot()}
    bapp = TB.FakeApp(root, ov)
    bs = bond_stone.BondStones(bapp)
    ov.sync([TB.mon(1, "리자몽"), TB.mon(2, "팬텀")], paths)
    TB.settle(root)
    a, b = ov.pets[1], ov.pets[2]
    bs.sync({"ready": [1], "claim": []})
    TB.settle(root)
    badge = a.stone_badge
    chk("bond.ready 의 포켓몬에만 DP 표식", badge is not None and b.stone_badge is None
        and type(badge).__module__.endswith("dp.bond_stone"), type(badge))
    texts = [badge.label.itemcget(i, "text") for i in badge.label.find_all() if badge.label.type(i) == "text"]
    chk("  '빛나는 돌' 글씨 · 표식이 도트 위에 뜬다", "빛나는 돌" in texts and badge.win.winfo_width() > 40, texts)
    root.after_cancel(badge._job)                            # 시계를 세우고 한 칸씩 직접 돌린다 (타이밍을 안 탄다)
    badge.lit = False
    badge._paint(False)
    dark = badge.label.itemcget(badge._body, "fill")
    badge._pulse()
    root.after_cancel(badge._job)
    bright = badge.label.itemcget(badge._body, "fill")
    chk("  반짝이면 판 빛깔이 밝아지고(_pulse) 다시 어두워진다(_paint)", badge.lit and dark != bright, (dark, bright))
    badge._paint(False)
    chk("  어두운 칸은 처음 빛깔 그대로", badge.label.itemcget(badge._body, "fill") == dark)
    badge._job = root.after(650, badge._pulse)
    x1, y1, x2, y2 = ov.area()
    a.x, a.y = (x1 + x2) // 2, (y1 + y2) // 2
    a.place()
    TB.settle(root)
    g_badge, g_name, g_pet = TB.geo(badge.win), TB.geo(a.name_win), TB.geo(a.win)
    chk("  이름표 위에 있고 도트 · 이름표 창을 덮지 않는다", g_badge[1] + g_badge[3] <= g_name[1]
        and not TB.overlaps(g_badge, g_name) and not TB.overlaps(g_badge, g_pet), (g_badge, g_name, g_pet))
    got = []
    badge.on_click = lambda pid, kind: got.append((pid, kind))
    badge.label.event_generate("<ButtonRelease-1>")
    root.update()
    chk("  누르면 기본과 같이 on_click(포켓몬, 종류)", got == [(1, "ready")], got)
    bs.sync({"ready": [], "claim": [1]})
    TB.settle(root)
    cl = a.stone_badge
    texts = [cl.label.itemcget(i, "text") for i in cl.label.find_all() if cl.label.type(i) == "text"]
    chk("  고르기 종류는 '메가스톤 고르기' 로 바뀐 DP 표식", cl is not badge and "메가스톤 고르기" in texts
        and type(cl).__module__.endswith("dp.bond_stone"), texts)
    ov.set_hidden(True)
    TB.settle(root)
    cl.place()
    chk("  숨김 동안 표식도 숨는다", TB.state(cl.win) == "withdrawn", TB.state(cl.win))
    ov.set_hidden(False)
    bs.sync({"ready": [], "claim": []})
    TB.settle(root)
    chk("  목록에서 빠지면 표식 창이 없어진다", a.stone_badge is None and TB.state(cl.win) == "gone")
    ov.clear()
    TB.settle(root)

    chk("그리는 중에 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n합계 OK %d FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
