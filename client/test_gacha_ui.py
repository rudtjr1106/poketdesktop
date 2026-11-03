# -*- coding: utf-8 -*-
"""랜덤 캡슐 창 (2.1.0, ui_gacha) - 진짜 Tk.

서버 대신 정해 둔 답을 주고, 돌리기 -> 동전 -> 손잡이 -> 섞기 -> 쌓이고 하나 빠짐 -> 배출 -> 열기 -> 상품 흐름 ·
캡슐 빛깔(등급) · 코인 · 글 · 단추 · 등급별 연출 · 저절로 열기 · 오류 · 확률표 · 누르는 자리 · 상점 띠를 본다.
도구 그림은 서버 자료(server/data/item_sprites)에서 바로 읽는다.

연출이 도는 동안 root.update() 가 늦게 돌아올 수 있다 - 그래서 시간을 재지 않고 상태(state)와 연출 기록(last_fx)을
본다. 초당 그린 횟수(60fps)는 화면 환경마다 달라 여기서 보지 않는다 (win.perf 에 남는다).

    python test_gacha_ui.py            (SHOT=폴더 를 주면 창을 찍어 둔다 - 맥 Quartz)
"""
import math
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket_gacha_")

import tkinter as tk                                            # noqa: E402

from PIL import Image                                           # noqa: E402

from poketdesktop import item_icons                             # noqa: E402
from poketdesktop import platform_os as PLAT                    # noqa: E402
from poketdesktop import ui_gacha as G                          # noqa: E402

OK = FAIL = 0
SPRITES = os.path.join(os.path.dirname(HERE), "server", "data", "item_sprites")
_real_pil = item_icons.pil


def _pil(item_id):
    if item_id and item_id.startswith("deco:"):
        return _real_pil(item_id)
    p = os.path.join(SPRITES, "%s.png" % item_id)
    return Image.open(p).convert("RGBA") if os.path.exists(p) else None


item_icons.pil = _pil
item_icons.raw = lambda api, i: True


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


ODDS = [{"key": "lose", "kr": "꽝", "pct": 40.0, "tier": "lose"},
        {"key": "ball", "kr": "몬스터볼", "pct": 14.0, "tier": "common"},
        {"key": "egg", "kr": "전설·환상 알", "pct": 0.1, "tier": "jackpot"}]


class Api(object):
    def __init__(self):
        self.answers = []
        self.calls = 0

    def guild_slot(self):
        self.calls += 1
        time.sleep(0.05)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


class App(object):
    def __init__(self, root):
        self.root = root
        self.api = Api()
        self.synced = 0

    def request_sync(self):
        self.synced += 1


def pump(root, secs, until=None):
    t = time.time()
    while time.time() - t < secs:
        root.update()
        if until and until():
            return True
        time.sleep(0.005)
    return bool(until and until())


def shot(win, name):
    d = os.environ.get("SHOT")
    if not d:
        return
    try:
        sys.path.insert(0, d)
        import selfshot
        selfshot.shoot(os.path.join(d, name), "랜덤 캡슐")
    except Exception as e:                                      # noqa: BLE001
        print("  (찍기 못 함: %s)" % e)


def answer(prize, tier, coin, **kw):
    r = {"ok": True, "prize": prize, "kr": prize, "tier": tier, "reels": [prize] * 3, "coin": coin, "item": None,
         "itemKr": None, "count": 0, "deco": None, "decoKr": None, "egg": None, "message": ""}
    r.update(kw)
    return r


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    app = App(root)
    changed = []
    win = G.GachaWindow(app, root, coin=55, odds=ODDS, on_change=changed.append)
    chk("그림 준비 (작업 스레드)", pump(root, 10, lambda: win.art is not None and win.state == "idle"), win.state)
    chk("처음 글: 손잡이를 돌려", "손잡이" in win.said and "20 코인" in win.said, win.said)
    gl = win.art.globe
    chk("캡슐이 유리통에 수십 알 (모두 보인다)", len(gl.b) == G.N_CAPS and not gl.gone
        and all(win.cv.itemcget(i, "state") != "hidden" for i in win.cap_ids), len(gl.b))
    chk("쌓여 있다: 모두 유리 안 · 아래쪽", all(math.hypot(b[0] - G.GX, b[1] - G.GY) <= gl.lim + 1 for b in gl.b)
        and sum(b[1] for b in gl.b) / len(gl.b) > G.GY, [round(b[1]) for b in gl.b][:5])
    chk("돌린 그림: 캡슐 빛깔마다 %d장 · 손잡이 %d장 · 동전 %d장" % (G.N_ANG, G.N_KNOB, G.N_COIN),
        all(len(f) == G.N_ANG for f in win.art.caps) and len(win.art.knob) == G.N_KNOB
        and len(win.art.coin) == G.N_COIN)
    if G.VECTOR:
        chk("맥: 기계는 캔버스 도형 (그림 한 장이 아니다)", len(win.cv.find_withtag("back")) > 50
            and len(win.cv.find_withtag("front")) > 50)
    else:
        chk("윈도우: 기계는 그림 두 장 (뒤판 RGB · 앞판 RGBA)", win.art.back_im.mode == "RGB"
            and win.art.front_im.mode == "RGBA")
    shot(win, "gacha_idle.png")

    # 1. 드묾 (이상한사탕): 돌리기 -> 배출 -> 눌러 열기 -> 상품
    app.api.answers.append(answer("candy", "rare", 35, item="RARECANDY", itemKr="이상한사탕", count=1))
    before = [(b[0], b[1]) for b in gl.b]
    win.spin()
    chk("누르면 동전이 날아간다 (coin) · 코인은 그 자리에서 준다", win.state == "coin" and win.coin == 35
        and win.cv.itemcget(win.coin_id, "state") == "normal", (win.state, win.coin))
    cx, cy = win.cv.coords(win.coin_id)
    chk("동전은 보유 코인 자리에서 떠난다 (왼쪽 위 0,0 이 아니라)",
        abs(cx - win.art.k(G.COIN_PATH[0][0])) < 2 and abs(cy - win.art.k(G.COIN_PATH[0][1])) < 2, (cx, cy))
    chk("손잡이가 돈다 (crank)", pump(root, 4, lambda: win.state == "crank"), win.state)
    chk("섞인다 (mix)", pump(root, 4, lambda: win.state == "mix"), win.state)
    pump(root, 0.8)
    moved = sum(1 for (x, y), b in zip(before, gl.b) if math.hypot(b[0] - x, b[1] - y) > 30)
    chk("와르르: 캡슐 절반 넘게가 자리를 옮긴다", moved > len(gl.b) // 2, moved)
    chk("배출되어 열기를 기다린다", pump(root, 12, lambda: win.state == "ready"), win.state)
    chk("맨 아래 하나가 받침 속으로 빠졌다 (숨김)", len(gl.gone) == 1
        and win.cv.itemcget(win.cap_ids[list(gl.gone)[0]], "state") == "hidden", gl.gone)
    chk("동전은 구멍으로 사라졌다", win.cv.itemcget(win.coin_id, "state") == "hidden")
    chk("코인 35 · 열기 단추", win.coin == 35, win.coin)
    chk("배출 캡슐이 보인다", win.cv.itemcget(win.drop_id, "state") == "normal")
    chk("드묾 캡슐 빛깔 (보라)", str(win.cv.itemcget(win.drop_id, "image")) in [str(p) for p in win.drop_ph["rare"]])
    chk("안내: 눌러 열어 보세요", "열어" in win.said, win.said)
    shot(win, "gacha_ready.png")
    win.open_capsule()
    chk("누르면 연다 (open)", win.state == "open")
    chk("상품이 나온다", pump(root, 6, lambda: win.state == "reveal"), win.state)
    chk("상품 글", "이상한사탕 x1" in win.said, win.said)
    chk("드묾 연출: 반짝이", win.last_fx and win.last_fx["tier"] == "rare" and win.last_fx["parts"] > 0, win.last_fx)
    chk("여는 동안 기계는 숨기고 바탕 빛만 바꾼다", win.cv.itemcget(win.knob_id, "state") == "hidden"
        and all(win.cv.itemcget(i, "state") == "hidden" for i in win.cap_ids)
        and win.cv.cget("bg") == G._hex(G.BACKDROP))
    chk("상점 다시 받게 알림", changed == [35], changed)
    shot(win, "gacha_reveal.png")
    win._overlay_click()
    pump(root, 0.5)
    win._overlay_click()
    chk("누르면 닫히고 다시 돌릴 수 있다", win.state == "idle", win.state)
    chk("닫으면 기계가 돌아온다 (빠진 캡슐만 숨김)", win.cv.itemcget(win.knob_id, "state") != "hidden"
        and win.cv.cget("bg") == G._hex(G.BASE)
        and sum(1 for i in win.cap_ids if win.cv.itemcget(i, "state") == "hidden") == 1)
    chk("쌓이면 유리통이 멈춘다 (쉬는 동안 다시 그리지 않는다)", pump(root, 4, lambda: not win.globe_live),
        win.globe_live)

    # 2. 꽝 - 안 눌러도 저절로 열린다
    app.api.answers.append(answer("lose", "lose", 15))
    win.spin()
    chk("꽝도 배출", pump(root, 12, lambda: win.state == "ready"), win.state)
    chk("다음 판에는 빠졌던 캡슐이 다시 들어온다 (하나만 빠짐)", len(gl.gone) == 1, gl.gone)
    chk("꽝 캡슐 빛깔 (잿빛)", str(win.cv.itemcget(win.drop_id, "image")) in [str(p) for p in win.drop_ph["lose"]])
    chk("%g초 뒤 저절로 열린다" % G.AUTO_OPEN, pump(root, G.AUTO_OPEN + 6, lambda: win.state == "reveal"), win.state)
    chk("꽝 글 · 칩 없음", "꽝" in win.said and win.cv.itemcget(win.chip_id, "state") == "hidden", win.said)
    pump(root, 0.5)
    win._overlay_click()
    chk("코인 15 - 모자라서 못 돌린다", win.coin == 15 and win.state == "idle")
    win.spin()
    chk("코인이 모자라면 안 돈다", win.state == "idle" and app.api.calls == 2 and "모자랍니다" in win.said, win.said)

    # 3. 대박 (알)
    win.coin = 40
    app.api.answers.append(answer("egg", "jackpot", 20, egg={"kind": "legendary", "kr": "전설의 포켓몬 알"}))
    win.spin()
    pump(root, 12, lambda: win.state == "ready")
    chk("대박 캡슐 빛깔 (무지개)", str(win.cv.itemcget(win.drop_id, "image")) in [str(p) for p in win.drop_ph["jackpot"]])
    win.open_capsule()
    chk("대박이 나온다", pump(root, 6, lambda: win.state == "reveal"), win.state)
    chk("대박 글", "전설의 포켓몬 알" in win.said and "대박" in win.said, win.said)
    chk("대박 연출: 반짝이 + 꽃가루", win.last_fx and win.last_fx["tier"] == "jackpot" and win.last_fx["parts"] >= 100,
        win.last_fx)
    pump(root, 0.3)
    shot(win, "gacha_jackpot.png")
    pump(root, 3.5, lambda: not win.parts)
    win._overlay_click()

    # 4. 오류 - 서버가 거절(상태 번호 있음)하면 코인 그대로, 캡슐 안 나옴
    class Err(Exception):
        message, status = "길드 코인이 모자랍니다. (20개 필요)", 400
    n_changed = len(changed)
    app.api.answers.append(Err())
    win.spin()
    chk("오류: 동전이 나갔다가", win.coin == 0, win.coin)
    chk("오류면 섞기만 하고 멈춘다", pump(root, 10, lambda: win.state == "idle"), win.state)
    chk("오류 글 · 코인 되돌림 · 캡슐 안 빠짐 · 배출 없음", "모자랍니다" in win.said and win.coin == 20
        and not gl.gone and win.cv.itemcget(win.drop_id, "state") == "hidden", (win.said, win.coin, gl.gone))
    chk("오류여도 상점 · 가방을 다시 받게 알린다", len(changed) == n_changed + 1, changed)

    # 4b. 통신 오류(시간 초과 - 상태 번호 없음): 서버는 이미 뽑았을 수도 있다 -> 확인하라고 알린다
    class NetErr(Exception):
        message, status = "서버 응답이 없습니다.", 0
    app.api.answers.append(NetErr())
    win.spin()
    chk("통신 오류: 멈춘다", pump(root, 10, lambda: win.state == "idle"), win.state)
    chk("통신 오류 글: 가방과 코인을 확인하라", "확인" in win.said and "가방" in win.said, win.said)
    chk("통신 오류도 상점 · 가방을 다시 받게 알린다 (한 번)", len(changed) == n_changed + 2, changed)

    # 5. 꾸미기를 다 가져서 대신 받음
    app.api.answers.append(answer("deco", "epic", 0, item="RARECANDY", itemKr="이상한사탕", count=2))
    win.spin()
    pump(root, 12, lambda: win.state == "ready")
    win.open_capsule()
    pump(root, 6, lambda: win.state == "reveal")
    chk("꾸미기 대신 받은 글", "다 있어서" in win.said and "x2" in win.said, win.said)
    pump(root, 0.5)
    win._overlay_click()

    # 6. 확률표 (쉬는 동안만)
    win.toggle_odds()
    chk("확률표가 뜬다", win.odds_id is not None)
    shot(win, "gacha_odds.png")
    win.toggle_odds()
    chk("다시 누르면 닫힌다", win.odds_id is None)

    # 7. 누르는 자리 (캔버스 아무 데나): 쉴 때 손잡이 = 돌리기, 단추를 누른 그 누름은 한 번만
    class Ev(object):
        def __init__(self, x, y):
            self.x, self.y = x * win.s, y * win.s
    win.coin = 40
    win._calm_until = 0.0                                 # (바로 앞에서 확률표를 닫았다)
    win._click(Ev(G.GX, G.GY + G.GR + 120))
    chk("빈 데를 누르면 아무 일 없음", win.state == "idle", win.state)
    app.api.answers.append(answer("ball", "common", 20, item="POKEBALL", itemKr="몬스터볼", count=5))
    win._click(Ev(G.KX, G.KY))
    chk("손잡이를 누르면 돌린다", win.state == "coin", win.state)
    pump(root, 12, lambda: win.state == "ready")
    win._click(Ev(G.KX, G.KY))
    chk("배출되면 손잡이는 아무 일 없음", win.state == "ready", win.state)
    win._ui(win._button)
    win._click(Ev(G.CHUTE[0] + 5, G.CHUTE[1] + 5))
    chk("열기 단추 누름은 한 번만 (캔버스가 또 받지 않는다)", win.state == "open" and not win._ui_click, win.state)
    pump(root, 6, lambda: win.state == "reveal")
    pump(root, 0.5)
    win._click(Ev(30, 30))
    chk("상품이 뜨면 아무 데나 눌러 닫는다", win.state == "idle", win.state)
    calls = app.api.calls
    win._click(Ev(G.GX, G.GY))
    win._ui(win._button)
    chk("닫은 바로 뒤의 누름(두 번 누름 · 연타)은 돌리기가 아니다", win.state == "idle" and app.api.calls == calls,
        win.state)
    win.toggle_odds()
    win._ui(win._close_odds)
    win._click(Ev(G.GX, G.GY))
    chk("확률표를 닫은 바로 뒤 누름도 돌리기가 아니다", win.state == "idle" and app.api.calls == calls, win.state)
    pump(root, G.CALM_SEC + 0.1)
    app.api.answers.append(answer("lose", "lose", 0))
    win._click(Ev(G.GX, G.GY))
    chk("조금 지나면 유리통을 눌러 돌린다", win.state == "coin", win.state)
    pump(root, 12, lambda: win.state == "ready")
    win.close()

    # 7b. 다 보기 전에 닫아도 상점은 다시 받는다 (서버는 이미 코인을 빼고 상품을 줬다) - 한 번만
    for when in ("mix", "answer"):
        seen = []
        w3 = G.GachaWindow(app, root, coin=50, odds=ODDS, on_change=seen.append)
        pump(root, 10, lambda: w3.art is not None and w3.state == "idle")
        app.api.answers.append(answer("ball", "common", 30, item="POKEBALL", itemKr="몬스터볼", count=5))
        w3.spin()
        if when == "mix":
            pump(root, 6, lambda: w3.state == "mix")
            w3.close()
            chk("섞는 중에 닫으면 바로 상점에 알린다", seen == [30], seen)
        else:
            w3.close()                                    # 답이 오기 전에 닫는다
            pump(root, 1.0, lambda: bool(seen))
            chk("답이 오기 전에 닫아도 답이 오면 알린다", seen == [30], seen)
        pump(root, 0.3)
        chk("알림은 한 번만 (%s)" % when, len(seen) == 1, seen)
    host = tk.Toplevel(root)
    w4 = G.GachaWindow(app, host, coin=50, odds=ODDS)
    pump(root, 10, lambda: w4.art is not None and w4.state == "idle")
    host.destroy()
    pump(root, 0.2)
    chk("부모 창이 닫혀 같이 부서지면 멈춘다", not w4.alive)
    chk("닫으면 멈춘다", not win.alive)

    # 8. 상점 띠
    fr = tk.Toplevel(root)
    fr.geometry("620x120+40+40")
    shop = {"coin": 80, "slot": {"cost": 20, "odds": ODDS}}
    b = G.Banner(fr, app, lambda: shop, lambda c: None, "#202030").pack(fill="x", padx=10, pady=10)
    pump(root, 0.4)
    chk("띠가 그려진다", b.ph is not None and b._w > 100, b._w)
    b.open()
    w2 = app._gacha_win
    chk("띠를 누르면 뽑기 창 (코인 · 확률표를 넘긴다)", w2.alive and w2.coin == 80 and len(w2.odds) == 3)
    b.open()
    chk("두 번 눌러도 창은 하나", app._gacha_win is w2)
    pump(root, 10, lambda: w2.art is not None)
    w2.coin = 10                                          # 창을 띄워 둔 사이 상점에서 코인이 늘었다
    shop["coin"] = 50
    b.open()
    chk("다시 열면 상점 코인을 따른다 (쉬는 중일 때)", app._gacha_win is w2 and w2.coin == 50, w2.coin)
    w2.close()

    # 화면 높이에 맞춘 배율: 글자 '아주 크게' 여도 작업 영역을 안 넘는다
    real_area = G.PLAT.work_area
    G.PLAT.work_area = lambda w, h: (0, 25, 1440, 25 + 700)
    try:
        sc = G.fit_scale(root)
        chk("작업 영역 700 이면 창 높이가 그 안 (기계를 같은 비율로 줄인다)", G.H * sc <= 700 - 40 and sc <= G.U.h(100) / 100.0,
            sc)
    finally:
        G.PLAT.work_area = real_area

    # 9. 길드 창에 붙이기 (기본 · DP 가 같이 쓰는 고리)
    from poketdesktop import ui_guild

    class Gw(object):
        alive, mode, tab, data = True, "guild", "shop", {"coin": 0}

        def __init__(self):
            self.app, self.drawn, self.tabs = app, 0, 0

        def _draw_tab(self):
            self.tabs += 1

        def draw(self):
            self.drawn += 1

        _after_gacha = ui_guild.GuildWindow._after_gacha
    g = Gw()
    g.shop = {"coin": 40}
    chk("옛 서버(slot 없음)면 띠를 안 깐다", ui_guild.GuildWindow._gacha_banner(g, fr, "#202030") is None)
    g.shop = shop
    chk("slot 이 있으면 띠를 깐다", isinstance(ui_guild.GuildWindow._gacha_banner(g, fr, "#202030"), G.Banner))
    synced = app.synced
    ui_guild.GuildWindow._after_gacha(g, 60)
    chk("뽑은 뒤: 상점을 다시 받고(그 칸을 다시) 동기화", g.shop is None and g.tabs == 1 and app.synced == synced + 1)
    g.mode, g.shop = "coinshop", shop
    ui_guild.GuildWindow._after_gacha(g, 60)
    chk("길드 없이 코인 상점만: 코인을 고치고 다시 그린다", g.data["coin"] == 60 and g.drawn == 1)
    chk("찾기 칸에 묶음 이름을 적어도 걸린다", ui_guild.shop_match({"kr": "불꽃의돌", "group": "진화"}, "진화")
        and not ui_guild.shop_match({"kr": "몬스터볼", "group": "볼"}, "진화"))
    fr.destroy()
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
