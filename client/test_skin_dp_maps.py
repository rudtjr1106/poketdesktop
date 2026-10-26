# -*- coding: utf-8 -*-
"""DP 테마 v2 - 지도 묶음(관장 · 길드전 지도 · 악당 출현 · 탐험)이 '무늬 없이 · 읽히고 · 기본 크기 그대로' 인가.

    python client/test_skin_dp_maps.py
"""
import json
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-dpmaps-")
os.environ["POKET_SKIN"] = "dp"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import test_big_lists as TBL                                # noqa: E402
from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins, ui_common as U              # noqa: E402

OK = FAIL = 0
ROOT = os.path.dirname(HERE)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def gym(root, dex):
    import test_gym_ui as TG
    from poketdesktop import ui_gym
    from poketdesktop.skins.dp import WIN_BG
    from poketdesktop.skins.dp import gym as DG
    gyms = json.load(open(os.path.join(TG.DATA, "gyms.json"), encoding="utf-8"))
    kmap = json.load(open(os.path.join(TG.DATA, "korea_map.json"), encoding="utf-8"))
    api = TG.FakeApi(dex, gyms, kmap, [TG.mon(dex, "MEWTWO", 100, ["PSYSTRIKE"], "PRESSURE", 11)])
    app = TG.FakeApp(root, api, dex)
    app.settings = {}
    gw = ui_gym.GymWindow(root, app)
    gw.win.geometry("1040x700+20+20")
    TG.pump(root, lambda: gw.data is not None and gw.map is not None, 20)
    TBL.settle(root, 0.5)
    chk("관장: 바다는 무늬 없는 한 빛깔", gw.cv.cget("bg") == DG.SEA and not gw.cv.find_withtag("sea"), gw.cv.cget("bg"))
    chk("관장: 오른쪽 바탕은 무늬 없는 한 빛깔 (줄무늬 사각형 없음)", gw.scv.cget("bg") == WIN_BG
        and not [i for i in gw.scv.find_withtag("side") if gw.scv.type(i) == "rectangle"
                 and gw.scv.itemcget(i, "fill") in ("#d6f3fb", "#c0e9f7")], gw.scv.cget("bg"))
    chk("관장: 보통 줄 높이는 기본 탭과 같다", gw.ROW_H == ui_gym.ROW_H, (gw.ROW_H, ui_gym.ROW_H))
    gw.enter_sido("11")
    TBL.settle(root, 0.6)
    cv = gw.cv
    labels = [i for i in cv.find_withtag("label") if cv.type(i) == "text" and cv.itemcget(i, "text").endswith("구")
              and cv.itemcget(i, "fill") not in WIN_BG]
    whites = [i for i in labels if cv.itemcget(i, "fill") == "#ffffff"]
    chk("관장: 어두운 땅(레벨 높은 곳) 위의 이름은 흰 글씨", bool(whites), len(labels))
    gw.close()


def war_map(root):
    import test_guild_ui as TG
    import test_guild_war_ui as TW
    from poketdesktop import ui_guild, ui_guild_war
    from poketdesktop.skins.dp import war_map as WMD
    real = ui_guild_war.WarTab._open_battle
    ui_guild_war.WarTab._open_battle = lambda self, data: None
    srv = TG.FakeServer()
    srv.war = TW.War()
    srv.war.phase = "war"
    srv.war.entered = True
    srv.g = {"name": "피카단", "intro": "같이 이겨요", "mode": "open", "master": 1, "points": 0}
    srv.roles = {1: "master", 2: "member", 3: "member"}
    app = TW.App(root, TW.Api(srv, 1))
    w = ui_guild.GuildWindow(app)
    w.win.winfo_toplevel().geometry("1000x680")
    TBL.wait(root, lambda: w.data is not None and w.mode == "guild", 10)
    war = TW.open_war(root, w)
    TBL.wait(root, lambda: war.wide and war.map.items, 5)
    TBL.settle(root, 0.4)
    cv = war.map.cv
    chk("길드전 지도: 무늬 없는 바다 (바탕 도형은 테 하나)", cv.cget("bg") == WMD.SEA and len(cv.find_withtag("bg")) == 1,
        len(cv.find_withtag("bg")))
    texts = [i for i in cv.find_withtag("label") if cv.type(i) == "text"]
    chk("길드전 지도: 이름표는 진한 글씨(흰 이름표 위)", texts and all(cv.itemcget(i, "fill") != "#ffffff" for i in texts),
        [cv.itemcget(i, "fill") for i in texts][:3])
    # 칸 선(line)을 다시 올려도 이름표는 그 위에 있다 (recolor 뒤)
    war.map.recolor()
    order = list(cv.find_all())
    last_line = max(i for i in order if "line" in cv.gettags(i))
    first_label = min(i for i in order if "label" in cv.gettags(i))
    chk("길드전 지도: recolor 뒤에도 이름표가 칸 선 위", order.index(first_label) > order.index(last_line),
        (order.index(first_label), order.index(last_line)))
    w.close()
    ui_guild_war.WarTab._open_battle = real


def boss(root, dex):
    import test_boss_ui as TBo
    import test_gym_ui as TG
    from poketdesktop import ui_gym
    gyms = json.load(open(os.path.join(TG.DATA, "gyms.json"), encoding="utf-8"))
    kmap = json.load(open(os.path.join(TG.DATA, "korea_map.json"), encoding="utf-8"))
    party = [TG.mon(dex, "GARCHOMP", 100, ["EARTHQUAKE", "DRAGONCLAW"], "ROUGHSKIN", 12)]
    api = TBo.BossApi(dex, gyms, kmap, party)
    api.on, api.stage = True, 1
    app = TG.FakeApp(root, api, dex)
    app.settings = {}
    gw = ui_gym.GymWindow(root, app)
    gw.win.geometry("1040x700+20+20")
    TG.pump(root, lambda: gw.data is not None and gw.map is not None, 20)
    gw.open_boss()
    bw = gw.boss_win
    TBL.wait(root, lambda: bw.card is not None and bw.rows, 5)
    TBL.settle(root, 0.3)
    root.update()
    # 기본 창(같은 자료)의 높이를 쟀을 때 480 px(맥 · 기본 글꼴)였다 - 그보다 키우지 않는다
    chk("악당 창: 내용 높이가 기본 창을 넘지 않는다 (<= 480)", bw.body.winfo_height() <= 480, bw.body.winfo_height())
    chk("악당 창: 승부 단추가 창 안에 다 든다", bw.go_btn.box[2] <= bw.cv.winfo_width(), (bw.go_btn.box, bw.cv.winfo_width()))
    api.on = False
    bw.card = {"active": False}
    bw.paint()
    root.update()
    chk("악당 창(없을 때): 높이가 기본 창 이하 (<= 64)", bw.body.winfo_height() <= 64, bw.body.winfo_height())
    bw.close()
    gw.close()


def expedition(root, dex):
    import test_expedition_ui as TE
    from poketdesktop import expedition_ui as XU
    from poketdesktop import ui_expedition as UE
    api = TE.FakeApi(dex, 60)
    box = [m for m in api.mons if not m.get("onDesktop")]
    api.expedition_send(box[0]["id"], "forest", 2)
    app = TE.FakeApp(root, api, dex)
    app.expedition = XU.Desk(app)
    w = UE.ExpeditionWindow(app)
    w.win.geometry("1060x680+20+20")
    TBL.wait(root, lambda: w.state is not None and w._wait is None and bool(w.vl.rows), 10)
    TBL.settle(root, 0.5)
    chk("탐험: 목록 줄 높이는 기본 탭과 같다", w.ROW_H == UE.ROW_H and all(h == UE.ROW_H for h, _d in w.vl.rows),
        (w.ROW_H, UE.ROW_H))
    chk("탐험: 왼쪽 · 가운데 칸 폭은 기본 탭과 같다 (오른쪽 목록을 좁히지 않는다)",
        w.cv.coords(w._wins["vl"])[0] >= UE.LEFT_W + UE.MID_W and w.cv.coords(w._wins["vl"])[0] < UE.LEFT_W + UE.MID_W + 40,
        w.cv.coords(w._wins["vl"]))
    sb, gb = w.send_btn.box, w.grow_btn.box
    chk("탐험: 성장 · 보내기가 요약 글과 한 줄 (기본 탭과 같은 자리)", sb and gb and sb[1] == gb[1] and sb[3] == gb[3], (sb, gb))
    vy = w.cv.coords(w._wins["vl"])[1] + int(w.cv.itemcget(w._wins["vl"], "height"))
    chk("탐험: 목록이 단추 줄 위에서 끝난다", vy < sb[1], (vy, sb))
    w.close()


def main():
    dex = P.Pokedex(json.load(open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8")))
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append("%s: %s" % (e.__name__, v))
    for title, fn in (("관장", lambda: gym(root, dex)), ("길드전 지도", lambda: war_map(root)),
                      ("악당 출현", lambda: boss(root, dex)), ("탐험", lambda: expedition(root, dex))):
        print(title)
        fn()
    chk("그리는 중에 난 예외가 없다", not errors, errors[:3])
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
