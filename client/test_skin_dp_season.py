# -*- coding: utf-8 -*-
"""화면 테마 '디아루가·펄기아'(skins/dp) 검사 - 랭크 팀 · 길드전 팀 · 칭호 명패 (skins/dp/season.py).

    python client/test_skin_dp_season.py

**창을 진짜로 띄운다** (가짜 서버는 smoke_season 의 것). DP 화면은 짓기만 새로 하고 고르기 규칙 · 저장 ·
알릴 말은 기본 창(ui_season)의 것을 그대로 쓰므로, 'DP 로 지은 자리가 기본 동작과 맞물리나' 를 본다.

  1. POKET_SKIN=dp 면 TeamWindow · RewardsWindow 가 DP 클래스로 뜬다 (skins.skinnable).
  2. 랭크 팀: 판 여섯 (고른 것만 하늘색 판) · 목록 줄 순서 · 머리(등록 상태 · n / 6마리) · 설명 띠 · 아래 글상자.
     목록 줄을 누르면 넣고, 파티 판을 누르면 뺀다. 판에 올리면 주황 테. 전설·환상 두 마리째는 막고 왜 안 되는지 말한다.
     찾기 · '맞는 포켓몬이 없다' · 바탕화면 파티로 채우기 · 비우기 · 등록(고른 순서) · 등록 풀기(빈 목록).
  3. 랭크전 조건(시즌 4): 설명 · 글상자에 몇 마리 채웠는지.
  4. 길드전 팀(spec): 제목 · 설명 · 저장이 spec 의 것, '등록 풀기' 는 없다.
  5. 칭호 · 명패: 달고 있는 것이 골라져 있고, 줄을 누르면 고르고 미리 보기가 바뀐다. '달기' 는 고른 것을 보낸다.
     칭호가 많으면 창을 키우지 않고 목록을 굴리며, 달고 있는 칭호까지 굴려 둔다. 적으면 창이 내용만큼.
  6. 그리는 중에 난 예외가 없다.
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-skin-dp-season-")
os.environ["POKET_SKIN"] = "dp"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import smoke_season as SS                                   # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_season                          # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def wait(root, cond, sec=8.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.005)
    return cond()


def settle(root, sec=0.25):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.005)


def center(box):
    x1, y1, x2, y2 = box
    return int((x1 + x2) / 2), int((y1 + y2) / 2)


def row_y(vl, pid):
    """목록(VList) 에서 그 포켓몬 줄의 가운데 y (화면 기준)."""
    for (hgt, d), top in zip(vl.rows, vl.tops):
        if d == pid:
            return int(top + hgt / 2 - vl.cv.canvasy(0))
    return None


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append(
        "".join(__import__("traceback").format_exception(e, v, tb)))
    app = SS.FakeApp(root)
    app.username = "나여조경석"
    from poketdesktop.skins.dp import season as DS

    print("1. DP 클래스로 뜬다")
    tw = ui_season.TeamWindow(app)
    chk("랭크 팀 = skins/dp/season.TeamWindow", type(tw) is DS.TeamWindow, type(tw))
    wait(root, lambda: len(tw.rows) == 6)
    settle(root, 0.4)

    print("2. 랭크 팀")
    order = [1, 3, 5, 6, 2, 4]                     # 레벨 높은 순 (80·55·50·40·30·5)
    chk("목록 줄은 레벨 높은 순 (기본 창이 정한 visible 그대로)",
        [d for _h, d in tw.vl.rows] == order == tw.visible, [d for _h, d in tw.vl.rows])
    chk("처음에는 지금 파티가 골라져 있다", tw.picked == [1, 2], tw.picked)
    chk("머리: 등록 상태 · 2 / 6마리", tw.state_parts() == ("등록 안 함 · 바탕화면 파티로 싸움", "2 / 6마리"),
        tw.state_parts())
    chk("판은 고른 두 자리만 하늘색 판 (나머지는 빈 자리)", sorted(tw._pboxes) == [0, 1], sorted(tw._pboxes))
    chk("설명 띠에 랭크 팀 규칙", "Lv.50 넘는 포켓몬은 Lv.50" in tw._note, tw._note)
    chk("글상자에 기본 창이 정한 말 (2마리 팀)", "2마리 팀에는" in tw.msg[0], tw.msg)
    chk("찾은 수", tw._found == "6마리", tw._found)
    chk("'등록 풀기' 는 등록 안 했으면 안 보인다", tw.unreg_btn.box is None, tw.unreg_btn.box)
    y = row_y(tw.vl, 3)
    tw.vl.cv.event_generate("<Button-1>", x=40, y=y)
    settle(root, 0.2)
    chk("목록 줄을 누르면 팀에 넣는다 (리자몽)", tw.picked == [1, 2, 3], tw.picked)
    chk("  판이 셋", sorted(tw._pboxes) == [0, 1, 2], sorted(tw._pboxes))
    tw.toggle(5)
    tw.toggle(6)
    settle(root, 0.2)
    chk("전설·환상 두 마리째는 안 들어간다", 5 in tw.picked and 6 not in tw.picked, tw.picked)
    chk("  왜 안 되는지 글상자에", "1마리까지" in tw.msg[0], tw.msg)
    i5 = tw.picked.index(5)
    cx, cy = center(tw._pboxes[i5])
    tw.cv.event_generate("<Motion>", x=cx, y=cy)
    settle(root, 0.1)
    outer = tw._pitems[i5][0]
    chk("판에 올리면 주황 테", tw.cv.itemcget(outer, "fill").lower() == DS.PLATE_SEL.lower(),
        tw.cv.itemcget(outer, "fill"))
    tw.cv.event_generate("<Button-1>", x=cx, y=cy)
    settle(root, 0.2)
    chk("파티 판을 누르면 팀에서 뺀다 (뮤츠)", tw.picked == [1, 2, 3], tw.picked)
    tw.cv.event_generate("<Motion>", x=2, y=2)
    settle(root, 0.1)
    chk("  판 밖으로 나가면 올림이 풀린다", tw._phover is None, tw._phover)

    tw.q.set("뮤")
    settle(root, 0.3)
    chk("찾기: 이름 일부 (뮤츠 · 뮤)", tw.visible == [5, 6] and [d for _h, d in tw.vl.rows] == [5, 6]
        and tw._found == "6마리 중 2마리", (tw.visible, tw._found))
    tw.q.set("없는이름")
    settle(root, 0.3)
    st = tw.cv.itemcget(tw._wins["list"], "state")
    chk("맞는 것이 없으면 목록 대신 그렇다고 적는다", "없는이름" in tw._nomatch and st == "hidden", (tw._nomatch, st))
    tw.q.set("")
    settle(root, 0.3)
    chk("지우면 전부 다시, 순서 그대로", [d for _h, d in tw.vl.rows] == order and not tw._nomatch
        and tw.cv.itemcget(tw._wins["list"], "state") == "normal")
    chk("  고른 것은 찾기 동안에도 그대로", tw.picked == [1, 2, 3], tw.picked)

    tw.clear_btn.invoke()
    settle(root, 0.1)
    chk("비우기", tw.picked == [] and tw._pboxes == {}, (tw.picked, tw._pboxes))
    tw.save_btn.invoke()
    chk("  비운 채 등록하면 막고 말한다", "한 마리 이상" in tw.msg[0] and not app.api.sent_team, tw.msg)
    tw.fill_btn.invoke()
    settle(root, 0.1)
    chk("바탕화면 파티로 채우기", tw.picked == [1, 2], tw.picked)
    tw.clear_btn.invoke()
    for pid in (2, 3, 1, 4):
        tw.toggle(pid)
    tw.save_btn.invoke()
    wait(root, lambda: app.api.sent_team)
    settle(root, 0.3)
    chk("등록은 고른 순서 그대로 서버로", app.api.sent_team[-1] == [2, 3, 1, 4], app.api.sent_team)
    chk("  등록하면 '등록됨' · '등록 풀기' 가 보인다 · 글상자에 알림",
        tw.state_parts()[0] == "등록됨" and tw.unreg_btn.box is not None and "등록했습니다" in tw.msg[0],
        (tw.state_parts(), tw.unreg_btn.box, tw.msg))
    tw.unreg_btn.invoke()
    wait(root, lambda: len(app.api.sent_team) == 2)
    settle(root, 0.3)
    chk("등록 풀기는 빈 목록 · 단추가 다시 숨는다", app.api.sent_team[-1] == [] and tw.unreg_btn.box is None,
        (app.api.sent_team, tw.unreg_btn.box))
    tw.close()
    settle(root, 0.1)

    print("3. 랭크전 조건 (시즌 4)")
    app.api.rank_min = {"count": 6, "level": 50}
    tw = ui_season.TeamWindow(app)
    wait(root, lambda: len(tw.rows) == 6)
    settle(root, 0.3)
    chk("설명 띠에 조건", "Lv.50 이상 포켓몬 6마리로 채워야" in tw._note, tw._note)
    chk("글상자에 몇 마리 채웠는지 (피카츄 80 · 이브이 30 -> 1마리)", "지금 1마리" in tw.msg[0], tw.msg)
    tw.close()
    app.api.rank_min = None

    print("4. 길드전 팀 (spec)")
    saved = []
    gw = ui_season.TeamWindow(app, spec={
        "title": "길드전 방어팀", "note": "길드전 설명 - 앞의 3마리만 미리 보입니다.",
        "load": lambda: (app.api.pvp_team(), app.api.pokemon()),
        "save": lambda ids: saved.append(list(ids)) or {"registered": True, "ids": ids}, "saved": "짰습니다"})
    chk("길드전 팀도 DP 클래스", type(gw) is DS.TeamWindow, type(gw))
    wait(root, lambda: len(gw.rows) == 6)
    settle(root, 0.3)
    chk("제목 · 설명이 spec 의 것", gw.win.title() == "길드전 방어팀" and gw._note == "길드전 설명 - 앞의 3마리만 미리 보입니다.",
        (gw.win.title(), gw._note))
    chk("머리: '아직 안 짬'", gw.state_parts()[0].startswith("아직 안 짬"), gw.state_parts())
    gw.toggle(3)
    gw.save_btn.invoke()
    wait(root, lambda: saved)
    settle(root, 0.3)
    chk("저장은 spec 의 save 로, 알림은 spec 의 saved", saved[-1] == [1, 2, 3] and gw.msg[0] == "짰습니다",
        (saved, gw.msg))
    chk("  '짜 둠' · '등록 풀기' 는 없다", gw.state_parts()[0] == "짜 둠" and gw.unreg_btn.box is None,
        (gw.state_parts(), gw.unreg_btn.box))
    gw.close()

    print("5. 칭호 · 명패")
    ew = ui_season.RewardsWindow(app)
    chk("칭호 · 명패 = skins/dp/season.RewardsWindow", type(ew) is DS.RewardsWindow, type(ew))
    wait(root, lambda: ew.cv is not None and ew._hits)
    settle(root, 0.4)
    chk("달고 있는 칭호가 골라져 있다", ew.title_var.get() == "s1_top30", ew.title_var.get())
    keys = [(h[2] is ew.title_var, h[3]) for h in ew._hits]
    chk("줄: 칭호(달지 않기 · 가진 것) · 명패(달지 않기 · 가진 것)",
        keys == [(True, ui_season.NONE), (True, "s1_top30"), (False, ui_season.NONE), (False, "bronze")], keys)
    texts = [ew.pcv.itemcget(i, "text") for i in ew.pcv.find_all() if ew.pcv.type(i) == "text"]
    chk("미리 보기: 내 이름 · 칭호", "나여조경석" in texts and any("시즌 1 상위권" in t for t in texts), texts)
    chk("칭호가 적으면 창이 목록 만큼 (안 굴린다)", ew.cv.yview() == (0.0, 1.0), ew.cv.yview())
    hit = [h for h in ew._hits if h[2] is ew.frame_var and h[3] == "bronze"][0]
    ew.cv.event_generate("<Button-1>", x=60, y=int((hit[0] + hit[1]) / 2 - ew.cv.canvasy(0)))
    settle(root, 0.2)
    chk("명패 줄을 누르면 고른다", ew.frame_var.get() == "bronze", ew.frame_var.get())
    fills = [ew.pcv.itemcget(i, "fill") for i in ew.pcv.find_all() if ew.pcv.type(i) == "text"]
    chk("  미리 보기 이름이 명패 빛깔", "#d08a52" in fills, fills)
    hit = [h for h in ew._hits if h[2] is ew.title_var and h[3] == ui_season.NONE][0]
    ew.cv.event_generate("<Button-1>", x=60, y=int((hit[0] + hit[1]) / 2 - ew.cv.canvasy(0)))
    settle(root, 0.2)
    chk("'달지 않기' 를 누르면 칭호를 뗀다", ew.title_var.get() == ui_season.NONE, ew.title_var.get())
    ew.save_btn.invoke()
    wait(root, lambda: app.api.sent_equip)
    settle(root, 0.2)
    chk("'달기' 는 고른 것을 보낸다 (칭호 떼기 + 명패)", app.api.sent_equip[-1] == ("", "bronze"), app.api.sent_equip)
    chk("  글상자에 '달았습니다.'", ew._msg[0] == "달았습니다.", ew._msg)
    ew.close_btn.invoke()
    settle(root, 0.1)
    chk("'닫기' 는 창을 닫는다", not ew.win.winfo_exists())

    print("   칭호가 많을 때")
    many = [{"id": "ach_%d" % i, "name": "업적 칭호 %d" % i, "season": 0} for i in range(46)]
    real = app.api.rewards
    app.api.rewards = lambda: {"titles": many, "frames": [{"id": "bronze", "name": "동빛 명패", "color": "#d08a52"}],
                               "equipped": {"title": "ach_40", "frame": None}}
    try:
        mw = ui_season.RewardsWindow(app)
        wait(root, lambda: mw.cv is not None and mw._hits)
        settle(root, 0.5)
        lo, hi = mw.cv.yview()
        chk("목록은 창을 키우지 않고 굴린다", hi - lo < 0.999 and mw.cv.winfo_height() <= U.h(mw.MAX_LIST) + 2,
            (lo, hi, mw.cv.winfo_height()))
        hit = [h for h in mw._hits if h[2] is mw.title_var and h[3] == "ach_40"][0]
        top = mw.cv.canvasy(0)
        chk("달고 있는 칭호(41번째)까지 굴려 둔다", top <= hit[0] and hit[1] <= top + mw.cv.winfo_height(),
            (top, hit[:2], mw.cv.winfo_height()))
        by = mw.bcv.winfo_rooty() + mw.bcv.winfo_height()
        wy = mw.win.winfo_rooty() + mw.win.winfo_height()
        chk("'달기' 줄이 창 안에 다 보인다", mw.bcv.winfo_ismapped() and by <= wy, (by, wy))
        mw.cv.yview_moveto(1.0)
        settle(root, 0.1)
        chk("끝까지 굴리면 명패 칸", mw.cv.yview()[1] >= 0.999, mw.cv.yview())
        mw.title_var.set("ach_3")
        mw.save_btn.invoke()
        wait(root, lambda: app.api.sent_equip[-1][0] == "ach_3")
        chk("고른 칭호를 보낸다", app.api.sent_equip[-1] == ("ach_3", ""), app.api.sent_equip[-1])
        mw.close()
    finally:
        app.api.rewards = real

    settle(root, 0.2)
    print("6. 그리는 중 예외")
    chk("Tk 콜백에서 난 오류가 없다", not errors, errors[:2])
    root.destroy()
    print("\n  합계  OK %d   FAIL %d" % (OK, FAIL))
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
