# -*- coding: utf-8 -*-
"""DP 테마 v2 - 사교 묶음(길드 · 길드전 · 친구 · 게시판 · 랭킹)의 '읽기 쉽게 다시 짠 것'. 진짜 Tk 로 확인한다.

    python client/test_skin_dp_social.py

기능(누르면 서버로 간다 ...)은 test_skin_dp.py 의 15 · 16 · 17 · 20 · 21 구역이 본다. 여기는 v2 에서 바꾼 것만:
본문에 테두리 글씨가 없다 · 방 아이콘은 본가 도구 그림(poke_icons) · 길드전 방에서 기둥을 접어 지도가 넓다 ·
친구 줄의 글이 단추 밑으로 들어가지 않는다 · 줄 높이가 기본 화면보다 높지 않다 · 긴 알림은 칸을 키운다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-dpsocial-")
os.environ["POKET_SKIN"] = "dp"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import test_big_lists as TBL                                # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins, ui_common as U              # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def outlined(cv):
    """테두리 글씨 (같은 글을 몇 픽셀씩 비켜 여러 겹 찍은 것) 의 글들."""
    items = []
    for i in cv.find_all():
        if cv.type(i) != "text":
            continue
        t = cv.itemcget(i, "text")
        if t.strip():
            x, y = cv.coords(i)[:2]
            items.append((t, x, y))
    out = set()
    for t, x, y in items:
        near = [1 for t2, x2, y2 in items if t2 == t and abs(x2 - x) <= 3 and abs(y2 - y) <= 3]
        if len(near) >= 3:
            out.add(t)
    return sorted(out)


def guild(root):
    import test_guild_ui as TG
    from poketdesktop import ui_guild
    from poketdesktop.skins.dp import guild as DG
    srv = TG.FakeServer()
    A, B = TG.Api(srv, 1), TG.Api(srv, 2)
    A.guild_create("포켓탐험대", "매일 미션 같이 해요!", "open")
    B.guild_join(A.guild()["guild"]["id"])
    srv.say("안녕하세요!", uid=2)
    app = TG.FakeApp(root, A)
    w = ui_guild.GuildWindow(app)
    w.win.winfo_toplevel().geometry("%dx%d" % (ui_guild.W, ui_guild.H))
    TBL.wait(root, lambda: w.data is not None and w.mode == "guild", 10)
    TBL.settle(root, 0.5)
    cv = w.side_cv
    rooms = list(w.seg.order)
    no_icon = [k for k in rooms if not any(cv.type(i) == "image" for i in cv.find_withtag("room_" + k))]
    from poketdesktop.skins.dp import poke_icons
    chk("방마다 아이콘은 본가 도구 그림 (선 · 원으로 그리지 않는다)", not no_icon, no_icon)
    chk("방 아이콘이 모두 poke_icons 의 이름이다 (pixelarticons 없음)",
        all(DG.ROOM_ICON.get(k) in poke_icons.NAMES for k in rooms), [DG.ROOM_ICON.get(k) for k in rooms])
    chk("방 아이콘이 서로 다르다", len(set(DG.ROOM_ICON.get(k) for k in rooms)) == len(rooms))
    chk("기둥에 테두리 글씨가 없다", not outlined(cv), outlined(cv))
    chk("고른 방에 빨간 ▶ 커서", any(cv.type(i) == "polygon" for i in cv.find_withtag("room_chat"))
        and w.seg.current == "chat")
    for tab in ("members", "mission", "manage"):
        w.show_tab(tab)
        TBL.settle(root, 0.4)
        chk("'%s' 칸에 테두리 글씨가 없다" % tab, not outlined(w.dpage.cv), outlined(w.dpage.cv))
    w.show_tab("mission")
    TBL.settle(root, 0.3)
    marks = [i for i in w.dpage.cv.find_all() if w.dpage.cv.type(i) == "text"
             and w.dpage.cv.itemcget(i, "text") in ("☑", "☐")]
    chk("미션: 체크 표시는 글자 ☑ ☐ (아이콘 그림이 아니다)", len(marks) >= 3, len(marks))
    # 긴 알림은 줄을 바꾸고 칸을 키운다 (글꼴은 그대로)
    w.say("아주 긴 알림입니다. " * 12)
    TBL.settle(root, 0.3)
    chk("긴 알림은 아래 글상자를 키운다", w.stcv.winfo_height() > U.h(38), w.stcv.winfo_height())
    w.say("짧은 알림")
    TBL.settle(root, 0.3)
    chk("짧아지면 다시 한 줄 높이", int(w.stcv.cget("height")) == U.h(38), w.stcv.cget("height"))
    w.say("")
    TBL.settle(root, 0.3)
    chk("할 말이 없으면 아래 글상자를 접는다 (빈 상자를 두지 않는다)", int(w.stcv.cget("height")) <= 1,
        w.stcv.cget("height"))
    w.close()


def guild_war(root):
    import test_guild_ui as TG
    import test_guild_war_ui as TW
    from poketdesktop import ui_guild, ui_guild_war
    from poketdesktop.skins.dp import guild as DG
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
    w.win.winfo_toplevel().geometry("%dx%d" % (ui_guild.W, ui_guild.H))     # 기본 창 크기 그대로
    TBL.wait(root, lambda: w.data is not None and w.mode == "guild", 10)
    TBL.settle(root, 0.4)
    chk("다른 방에서는 기둥이 넓다 (깃발 판 + 방 목록)", w.info.winfo_width() == U.h(DG.SIDE_W), w.info.winfo_width())
    war = TW.open_war(root, w)
    TBL.wait(root, lambda: war.wide and war.map.items, 5)
    TBL.settle(root, 0.5)
    chk("길드전 방에서는 기둥을 아이콘 줄로 접는다", w.info.winfo_width() == U.h(DG.RAIL_W), w.info.winfo_width())
    mw = war.map.cv.winfo_width()
    chk("기본 창 크기에서도 지도가 넉넉하다 (1차는 손가락 두 개 폭이었다)", mw >= U.h(220), mw)
    chk("접은 기둥에도 방이 다 있다", all(w.side_cv.find_withtag("room_" + k) for k in w.seg.order))
    cards = [c for c in war.inner.winfo_children() if isinstance(c, tk.Frame)]
    chk("오른쪽 판은 한 겹의 가는 테", cards and all(int(c.cget("highlightthickness")) == 1 for c in cards),
        [c.cget("highlightthickness") for c in cards][:3])
    w.show_tab("chat")
    TBL.settle(root, 0.4)
    chk("다른 방으로 가면 기둥이 다시 넓어진다", w.info.winfo_width() == U.h(DG.SIDE_W), w.info.winfo_width())
    w.close()
    ui_guild_war.WarTab._open_battle = real


def friends(root):
    import importlib.util
    spec = importlib.util.spec_from_file_location("friendfake", os.path.join(HERE, "test_skin_dp_friends.py"))
    FF = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(FF)
    from poketdesktop import ui_friends
    app = FF.App(root)
    app.live_pending = {"id": 7, "foeId": 3}                 # 줄 오른쪽에 글까지 붙는 경우
    fw = ui_friends.FriendsWindow(app)
    TBL.wait(root, lambda: bool(fw._items) and not fw.busy, 10)
    TBL.settle(root, 0.4)
    hts = dict((d[0], h) for h, d in fw.vl.rows)
    chk("친구 줄은 기본 화면의 줄(카드 54 + 틈 6)보다 낮다", hts.get("friend", 999) <= U.h(54), hts.get("friend"))
    cv = fw.vl.cv
    over = []
    for n, (kind, d) in enumerate(fw._items):
        if kind != "friend":
            continue
        fw.vl.see(n)
        TBL.settle(root, 0.1)
        hits = fw._hits.get((kind, id(d)), [])
        left = min(h[0] for h in hits) if hits else 10 ** 6
        for i in cv.find_withtag("row%d" % n):
            # (왼쪽에 붙인 글만 - 단추 글자는 단추 가운데, 오른쪽 글은 단추 옆에 붙인다)
            if cv.type(i) == "text" and cv.itemcget(i, "anchor") == "w" and cv.bbox(i)[2] > left:
                over.append((d["name"], cv.itemcget(i, "text")))
    chk("친구 줄의 글이 단추 밑으로 들어가지 않는다", not over, over[:4])
    chk("목록에 테두리 글씨가 없다", not outlined(cv), outlined(cv))
    fw.q.set("빛나")
    fw.do_search()
    TBL.wait(root, lambda: bool(fw._found_hits), 5)
    chk("찾기 칸에 테두리 글씨가 없다", not outlined(fw.scv), outlined(fw.scv))
    chk("돋보기 아이콘을 쓰지 않는다 (찾기 단추 글자)", not any(fw.scv.type(i) == "image" for i in fw.scv.find_all()))
    fw.close()


def board(root):
    import test_board_ui as TB
    from poketdesktop import ui_board
    api = TB.FakeApi("지우", 2)
    _n1, _n2, talk, _c1 = TB.seed(api)
    app = TB.FakeApp(root, api)
    w = ui_board.BoardWindow(app)
    TBL.wait(root, lambda: w.data is not None and bool(w._rows), 10)
    TBL.settle(root, 0.3)
    lw = w.lcv.winfo_width()
    full = [i for i in w.lcv.find_withtag("frame") if w.lcv.type(i) == "rectangle"
            and w.lcv.coords(i)[0] <= 0 and w.lcv.coords(i)[2] >= lw]
    chk("목록 바탕에 줄무늬가 없다 (폭 가득한 바탕 네모가 하나)", len(full) == 1, len(full))
    chk("목록에 테두리 글씨가 없다", not outlined(w.vl.cv) and not outlined(w.lcv), outlined(w.vl.cv))
    w.open_post(talk)
    TBL.wait(root, lambda: w.view == "post" and w.post is not None, 5)
    TBL.settle(root, 0.3)
    chk("글에 테두리 글씨가 없다", not outlined(w.pcv), outlined(w.pcv))
    chk("좋아요 단추의 하트는 글자 ♥ ♡ (아이콘 그림이 아니다)",
        any(w.pcv.type(i) == "text" and w.pcv.itemcget(i, "text")[:1] in ("♥", "♡") for i in w.pcv.find_withtag("like"))
        and not any(w.pcv.type(i) == "image" for i in w.pcv.find_withtag("like")))
    w.close()


def rank(root):
    import smoke_season as SS
    from poketdesktop import ui_rank
    app = SS.FakeApp(root)
    rw = ui_rank.RankWindow(app)
    TBL.wait(root, lambda: bool(rw._items) and not rw.busy, 10)
    TBL.settle(root, 0.4)
    chk("본문 바탕에 줄무늬가 없다 (흰 판 한 장)", len(rw.bcv.find_withtag("body")) == 1,
        len(rw.bcv.find_withtag("body")))
    chk("목록에 테두리 글씨가 없다", not outlined(rw.vl.cv), outlined(rw.vl.cv))
    hts = dict((d[0], h) for h, d in rw.vl.rows)
    chk("순위 줄은 기본 화면의 줄보다 낮다", hts.get("rank", 999) <= U.h(58), hts.get("rank"))
    rw.close()


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    errs = []
    root.report_callback_exception = lambda e, v, tb: errs.append(repr(v))
    U.init_fonts(root)
    U.apply_theme(root)
    for title, run in (("길드", guild), ("길드전", guild_war), ("친구", friends), ("게시판", board),
                       ("랭킹", rank)):
        print(title)
        run(root)
    chk("그리는 중에 난 예외가 없다", not errs, errs[:3])
    root.destroy()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
