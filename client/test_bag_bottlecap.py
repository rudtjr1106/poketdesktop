# -*- coding: utf-8 -*-
"""가방: 되돌릴 수 없는 도구(은색 · 금색병뚜껑, 이로치사탕)는 직접 누른 포켓몬에게만 쓴다 (게시판 #704).

    python client/test_bag_bottlecap.py

**창을 진짜로 띄운다** (가짜 서버). 기본 테마와 DP 계열 테마 여섯을 하나씩 따로 띄워 본다 (test_tm_find 와 같은 식).

#704: 따라큐에게 쓰려던 금색병뚜껑이 가디안에게 갔다. 가방을 열면 맨 앞 도구(메가스톤 가디안나이트)가 골라지고,
그것을 받을 수 있는 하나뿐인 포켓몬(유대 미션을 마친 가디안)이 저절로 골라진다. 금색병뚜껑을 눌러도 고르던 포켓몬이
그대로 남았고, 쓰기 단추에도 확인 창에도 대상 이름이 없었다. 못 박는 것:

  1. 가방을 열면 가디안나이트 · 유대 미션을 마친 가디안이 골라진다 (이번 일의 출발점 - 바뀌지 않았다).
  2. 그 상태에서 금색병뚜껑 · 은색병뚜껑 · 이로치사탕을 누르면 대상이 비고 쓰기 단추가 꺼진다. 찾기로 하나만
     남겨도 저절로 고르지 않는다. 이상한사탕 같은 다른 도구는 지금처럼 이어받는다.
  3. 직접 누르면 쓸 수 있고, 쓰기를 누르면 대상 이름 · 레벨 · 바뀔 능력이 든 확인 창이 뜬다. 취소하면 서버에 안 간다.
     금색은 남은 능력 모두, 은색은 고른 능력 하나. 조사도 맞다 ('공격이', '스피드가', 'HP가').
     쓴 뒤 다시 불러와도 직접 고른 포켓몬은 그대로다 (은색을 이어서 쓸 때). 다른 도구로 갔다 오면 다시 눌러야 한다.
  4. 다 단련된 포켓몬 · Lv.50 미만은 계속 막힌다 (눌러도 안 골라진다).
  5. 진짜 확인 창(테마마다 다르다)에 이름이 보이고, 닫으면(취소) 쓰지 않는다.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-test-bottlecap-"))
SKIN = os.environ.get("POKET_BOTTLECAP_SKIN", "default")
os.environ["POKET_SKIN"] = SKIN
THEMES = ("dp", "pt", "gs", "bw", "swsh", "emerald")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins, ui_bag, ui_bag_tabs, ui_box  # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
import smoke_box_filter as SB                               # noqa: E402
import test_big_lists as BL                                 # noqa: E402

OK = FAIL = 0
DATA = os.path.join(ROOT, "server", "data")
ITEMS = ("GARDEVOIRITE", "GOLDBOTTLECAP", "BOTTLECAP", "SHINYCANDY", "RARECANDY")

DRAGAPULT, GROWLITHE, GARDE, MIMIKYU, GARCHOMP, GARDE2, GARDE3, INFERNAPE = (
    39001, 39002, 45765, 57668, 39072, 114030, 94702, 36531)
ALL6 = ("hp", "atk", "def", "spa", "spd", "spe")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, sec=0.25):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.005)


def mon(dex, num, pid, level, ivs, hyper=(), bonded=None):
    m = SB.mon(dex, num, pid)
    m.update(level=level, ivs=dict(ivs), hyper=dict((s, True) for s in hyper))
    sp = dex.get(num)
    m["info"] = dex.describe(dict(m, exp=P.exp_for_level(sp.get("growth", "medium"), level)))
    m["info"]["name"] = sp["kr"]
    if bonded is not None:
        m["bonded"] = bonded                     # 서버가 보내는 유대 여부 (메가진화하는 종만)
    return m


def account(dex):
    """#704 계정을 닮게: 파티 맨 앞 드래펄트, Lv.48 가디, 유대 미션을 마친 가디안 하나와 못 마친 가디안 둘, 따라큐,
    다 단련된 한카리아스 · 개체값이 다 31 인 초염몽."""
    return [
        mon(dex, 887, DRAGAPULT, 100, dict(hp=20, atk=30, spa=27, spd=31, spe=31, **{"def": 0})),
        mon(dex, 58, GROWLITHE, 48, dict(hp=3, atk=4, spa=5)),
        mon(dex, 282, GARDE, 100, dict(hp=20, atk=5, spa=25, spd=12, spe=0, **{"def": 10}),
            hyper=("hp", "spa", "def", "spd"), bonded=True),
        mon(dex, 778, MIMIKYU, 100, dict(hp=7, atk=8, spa=24, spd=19, spe=21, **{"def": 16})),
        mon(dex, 445, GARCHOMP, 100, dict(hp=1, atk=2, spa=3), hyper=ALL6),
        mon(dex, 282, GARDE2, 100, dict(hp=9), bonded=False),
        mon(dex, 282, GARDE3, 70, dict(hp=9), bonded=False),
        mon(dex, 392, INFERNAPE, 100, dict((s, 31) for s in ALL6)),
    ]


class Api(BL.Api):
    """쓴 도구 · 대상 · 능력을 적어 둔다."""

    def use_item(self, item, pid, stat="", hour=None):
        self.used.append((item, pid, stat))
        self.bag[item] = self.bag.get(item, 0) - 1
        return {"ok": True, "message": "썼다."}

    def hold(self, pid, item):
        self.used.append(("hold", item, pid))
        return {"ok": True, "message": "지니게 했다."}


class App(BL.App):
    tm_new = 0

    def note_tms(self, *_a, **_kw):
        pass


class Asked(object):
    """ui_box.confirm 대신 - 무엇을 물었는지 적고 정해 둔 답을 한다."""

    def __init__(self):
        self.seen = []
        self.answer = False

    def __call__(self, parent, title, message, danger=True, ok_text="확인"):
        self.seen.append((title, message))
        return self.answer


def btn_text(b):
    t = getattr(b, "text", None)
    return t if isinstance(t, str) else b.label.cget("text")


def listing(w):
    """'누구에게' 자리에 포켓몬 목록이 보이나 (안내 글이 아니라)."""
    if hasattr(w, "_mon_note"):                  # DP 계열: None 이면 판 목록
        return w._mon_note is None
    return bool(w._mon_list_on)


def stat_hint(w):
    """은색병뚜껑 능력 칸 위의 안내."""
    if isinstance(getattr(w, "_stat", None), tuple):         # DP 계열: (안내, 칸들)
        return w._stat[0]
    return w.stat_hint.cget("text")


def toplevels(w):
    out = []
    for c in w.winfo_children():
        if isinstance(c, tk.Toplevel):
            out.append(c)
        out.extend(toplevels(c))
    return out


def click_mon(w, pid):
    """사용자가 그 포켓몬 줄(기본) · 판(DP 계열)을 누른다."""
    m = next(m for m in w.mons if m["id"] == pid)
    if hasattr(w, "_plate_click"):
        return w._plate_click(m)
    row = dict(w.shown_mons()).get(pid)
    if row is not None:
        return row._click(None)
    return w.pick_mon(pid)


def click_item(w, iid):
    """사용자가 왼쪽 도구 줄을 누른다."""
    it = next(i for i in w.items if i["id"] == iid)
    if hasattr(w, "_click_item"):
        return w._click_item(("item", it), 0, 0, 0)
    row = dict(w.shown_items()).get(iid)
    if row is not None:
        return row._click(None)
    return w.pick_item(iid)


def all_text(w):
    """창 안의 모든 글 - 라벨과 캔버스 글 (DP 계열의 묻는 창은 캔버스에 쓴다)."""
    out = []

    def walk(c):
        try:
            if "text" in c.keys() and str(c.cget("text")):
                out.append(str(c.cget("text")))
        except tk.TclError:
            pass
        if isinstance(c, tk.Canvas):
            for i in c.find_all():
                if c.type(i) == "text":
                    out.append(c.itemcget(i, "text"))
        for k in c.winfo_children():
            walk(k)
    walk(w)
    return out


def pure():
    print("== 묻는 말 (hyper_ask)")
    it_g = {"kr": "금색병뚜껑", "effect": {"kind": "iv", "count": 6}}
    it_s = {"kr": "은색병뚜껑", "effect": {"kind": "iv", "count": 1}}

    def m(name, level, ivs, hyper=()):
        return {"level": level, "info": {"name": name, "ivs": dict(ivs),
                                         "hyper": dict((s, True) for s in hyper)}}
    garde = m("가디안", 100, dict(hp=31, atk=5, spa=31, spd=31, spe=0, **{"def": 31}), ("hp", "spa", "def", "spd"))
    chk("금색: 남은 능력만, STATS 순서로 (#704 의 가디안)", ui_bag.hyper_ask(it_g, garde) ==
        "가디안(Lv.100)에게 금색병뚜껑을 씁니다. 공격 · 스피드가 31로 단련됩니다. 되돌릴 수 없습니다.",
        ui_bag.hyper_ask(it_g, garde))
    chk("  hyper_left 는 서버 _use_iv 와 같은 식 (31 미만 · 단련 안 함)",
        [s for s, _l in ui_bag.hyper_left(garde["info"])] == ["atk", "spe"], ui_bag.hyper_left(garde["info"]))
    nick = m("뀨뀨", 77, dict(hp=7, atk=8, spa=24, spd=19, spe=21, **{"def": 16}))
    chk("  별명이 있으면 별명, 여섯이 다 남았으면 여섯", ui_bag.hyper_ask(it_g, nick) ==
        "뀨뀨(Lv.77)에게 금색병뚜껑을 씁니다. HP · 공격 · 방어 · 특수공격 · 특수방어 · 스피드가 31로 단련됩니다. "
        "되돌릴 수 없습니다.", ui_bag.hyper_ask(it_g, nick))
    chk("  끝 능력이 '공격' 이면 '공격이'", "공격이 31로" in ui_bag.hyper_ask(
        it_g, m("가", 60, dict(hp=31, atk=1, spa=31, spd=31, spe=31, **{"def": 31}))))
    chk("은색: 고른 능력 하나 ('스피드가')", ui_bag.hyper_ask(it_s, nick, "spe") ==
        "뀨뀨(Lv.77)에게 은색병뚜껑을 씁니다. 스피드가 31로 단련됩니다. 되돌릴 수 없습니다.",
        ui_bag.hyper_ask(it_s, nick, "spe"))
    chk("  'HP가' ('HP이' 가 아니다) · '특수공격이' · '방어가'",
        "HP가 31로" in ui_bag.hyper_ask(it_s, nick, "hp") and "특수공격이 31로" in ui_bag.hyper_ask(it_s, nick, "spa")
        and "방어가 31로" in ui_bag.hyper_ask(it_s, nick, "def"), ui_bag.hyper_ask(it_s, nick, "hp"))
    chk("되돌릴 수 없는 도구는 병뚜껑 · 이로치사탕", ui_bag.BY_HAND == ("iv", "shiny"), ui_bag.BY_HAND)


def behave(root, dex):
    print("== 테마: %s" % SKIN)
    chk("이번 실행의 테마", skins.active() == SKIN, skins.active())
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append("%s: %s" % (e.__name__, v))
    raw = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))["items"]
    items = [dict(raw[k]) for k in ITEMS]
    api = Api(account(dex), items)
    app = App(root, api, dex)
    top = tk.Toplevel(root)
    top.geometry("1040x640+30+30")
    tabs = ui_bag_tabs.BagTabs(root, app, top)
    tabs.win.pack(fill="both", expand=True)
    w = tabs.bag
    BL.wait(root, lambda: bool(w.mons) and w._wait is None, 15)
    settle(root, 0.5)
    asked = Asked()
    real_confirm = ui_box.confirm
    ui_box.confirm = asked

    try:
        print("1. 가방을 연다")
        chk("처음 고른 도구는 맨 앞 메가스톤 (가디안나이트)", w.item_id == "GARDEVOIRITE", w.item_id)
        chk("  대상은 유대 미션을 마친 가디안 - 저절로 골라진다", w.mon_id == GARDE, w.mon_id)
        chk("  다른 가디안은 '유대 미션 전', 다른 종은 '메가진화 안 함'", w._states[GARDE2][1] and
            w._states[GARDE2][2] == "유대 미션 전" and w._states[MIMIKYU][2] == "메가진화 안 함",
            (w._states[GARDE2], w._states[MIMIKYU]))

        print("2. 금색병뚜껑을 누른다 (#704)")
        click_item(w, "GOLDBOTTLECAP")
        settle(root, 0.3)
        chk("**고르던 가디안을 이어받지 않는다** - 대상이 빈다", w.item_id == "GOLDBOTTLECAP" and w.mon_id is None
            and w.current_mon() is None, (w.item_id, w.mon_id))
        chk("  쓰기 단추가 꺼진다", not w.use_btn.enabled, (w.use_btn.enabled, btn_text(w.use_btn)))
        chk("  목록은 그대로 보인다 (안내로 바뀌지 않는다)", listing(w), SKIN)
        chk("  가디안 · 따라큐는 막히지 않는다", w._states[GARDE][:3] == (False, False, "2곳 남음")
            and not w._states[MIMIKYU][1], (w._states[GARDE], w._states[MIMIKYU]))
        w.do_use()
        settle(root, 0.2)
        chk("  그대로 쓰기를 불러도 아무 일 없다 (묻지도 않는다)", not api.used and not asked.seen, (api.used, asked.seen))
        w.find.q.set("따라큐")
        settle(root, 0.3)
        chk("  찾기로 하나만 남겨도 저절로 고르지 않는다", [m["id"] for m in w._view] == [MIMIKYU] and w.mon_id is None,
            ([m["id"] for m in w._view], w.mon_id))
        w.find.q.set("")
        settle(root, 0.3)

        print("3. 은색병뚜껑 · 이로치사탕도, 다른 도구는 그대로")
        for iid in ("BOTTLECAP", "SHINYCANDY"):
            click_item(w, "GARDEVOIRITE")
            settle(root, 0.2)
            back = w.mon_id
            click_item(w, iid)
            settle(root, 0.2)
            chk("가디안나이트(가디안 골라짐) -> %s: 대상이 빈다 · 쓰기 꺼짐" % iid, back == GARDE and w.mon_id is None
                and not w.use_btn.enabled, (back, w.mon_id, w.use_btn.enabled))
            if iid == "BOTTLECAP":
                chk("  은색은 능력 칸이 '먼저 포켓몬을 고르세요'", "먼저 포켓몬을" in stat_hint(w), stat_hint(w))
        click_item(w, "GARDEVOIRITE")
        settle(root, 0.2)
        click_item(w, "RARECANDY")
        settle(root, 0.2)
        chk("가디안나이트 -> 이상한사탕: 지금처럼 이어받는다", w.mon_id == GARDE and w.use_btn.enabled, w.mon_id)

        print("4. 금색병뚜껑 - 직접 누르고 쓴다")
        click_item(w, "GOLDBOTTLECAP")
        settle(root, 0.2)
        click_mon(w, MIMIKYU)
        settle(root, 0.2)
        chk("따라큐를 누르면 골라지고 쓰기 단추가 켜진다", w.mon_id == MIMIKYU and w.use_btn.enabled
            and "금색병뚜껑" in btn_text(w.use_btn), (w.mon_id, btn_text(w.use_btn)))
        asked.answer = False
        w.do_use()
        settle(root, 0.2)
        want = ("따라큐(Lv.100)에게 금색병뚜껑을 씁니다. HP · 공격 · 방어 · 특수공격 · 특수방어 · 스피드가 31로 "
                "단련됩니다. 되돌릴 수 없습니다.")
        chk("쓰기 -> 이름 · 레벨 · 바뀔 능력을 적어 묻는다", asked.seen == [("금색병뚜껑", want)], asked.seen)
        chk("  취소하면 서버에 안 간다", not api.used, api.used)
        click_mon(w, GARDE)
        settle(root, 0.2)
        del asked.seen[:]
        w.do_use()
        settle(root, 0.2)
        chk("  가디안이면 '공격 · 스피드가' (남은 것만)", asked.seen and asked.seen[-1][1] ==
            "가디안(Lv.100)에게 금색병뚜껑을 씁니다. 공격 · 스피드가 31로 단련됩니다. 되돌릴 수 없습니다.",
            asked.seen)
        click_mon(w, MIMIKYU)
        settle(root, 0.2)
        asked.answer = True
        w.do_use()
        BL.wait(root, lambda: bool(api.used) and w._wait is None, 8)
        settle(root, 0.4)
        chk("확인하면 그 포켓몬에게 쓴다", api.used == [("GOLDBOTTLECAP", MIMIKYU, "")], api.used)
        chk("  다시 불러와도 금색병뚜껑 · 따라큐 그대로 (직접 고른 것)", w.item_id == "GOLDBOTTLECAP"
            and w.bag.get("GOLDBOTTLECAP") == 2 and w.mon_id == MIMIKYU and w.use_btn.enabled,
            (w.item_id, w.bag.get("GOLDBOTTLECAP"), w.mon_id))
        click_item(w, "RARECANDY")
        settle(root, 0.2)
        mid = w.mon_id
        click_item(w, "GOLDBOTTLECAP")
        settle(root, 0.2)
        chk("  이상한사탕에 갔다 오면 (따라큐가 이어졌어도) 다시 눌러야 한다", mid == MIMIKYU and w.mon_id is None
            and not w.use_btn.enabled, (mid, w.mon_id))

        print("5. 은색병뚜껑 - 고른 능력 하나")
        click_item(w, "BOTTLECAP")
        settle(root, 0.2)
        click_mon(w, MIMIKYU)
        settle(root, 0.2)
        chk("따라큐를 누르면 능력을 고르기 전엔 꺼져 있다", w.mon_id == MIMIKYU and not w.use_btn.enabled, w.mon_id)
        asked.answer = False
        for key, part in (("spe", "스피드가 31로"), ("atk", "공격이 31로"), ("hp", "HP가 31로")):
            w.pick_stat(key)
            del asked.seen[:]
            w.do_use()
            settle(root, 0.1)
            chk("  %s -> '%s'" % (key, part), w.use_btn.enabled and len(asked.seen) == 1
                and asked.seen[0][0] == "은색병뚜껑" and asked.seen[0][1].startswith("따라큐(Lv.100)에게 은색병뚜껑을 씁니다.")
                and part in asked.seen[0][1], asked.seen)
        chk("  취소하면 서버에 안 간다", api.used == [("GOLDBOTTLECAP", MIMIKYU, "")], api.used)
        asked.answer = True
        w.do_use()
        BL.wait(root, lambda: len(api.used) >= 2 and w._wait is None, 8)
        settle(root, 0.4)
        chk("  확인하면 그 능력으로 쓴다", api.used[1:] == [("BOTTLECAP", MIMIKYU, "hp")], api.used)
        chk("  다시 불러와도 따라큐 그대로 - 능력만 다시 고른다 (은색을 이어서 쓸 때)", w.item_id == "BOTTLECAP"
            and w.mon_id == MIMIKYU and w.stat is None and not w.use_btn.enabled, (w.item_id, w.mon_id, w.stat))

        print("6. 이로치사탕 (원래 확인 창)")
        click_item(w, "SHINYCANDY")
        settle(root, 0.2)
        click_mon(w, MIMIKYU)
        settle(root, 0.2)
        asked.answer = False
        del asked.seen[:]
        w.do_use()
        settle(root, 0.2)
        chk("직접 누르고 쓰기 -> 따라큐 이름으로 묻고, 취소하면 안 쓴다", len(asked.seen) == 1
            and asked.seen[0][0] == "이로치사탕" and "따라큐" in asked.seen[0][1] and len(api.used) == 2,
            (asked.seen, api.used))

        print("7. 막힌 포켓몬은 그대로 막힌다")
        for iid in ("GOLDBOTTLECAP", "BOTTLECAP"):
            click_item(w, iid)
            settle(root, 0.2)
            st = w._states
            chk("%s: 다 단련된 한카리아스 · 개체값이 다 31 인 초염몽은 '이미 다 단련됨'" % iid,
                st[GARCHOMP][1] and st[GARCHOMP][2] == "이미 다 단련됨" and st[INFERNAPE][1]
                and st[INFERNAPE][2] == "이미 다 단련됨", (st[GARCHOMP], st[INFERNAPE]))
            chk("  Lv.48 가디는 'Lv.50 부터'", st[GROWLITHE][1] and st[GROWLITHE][2] == "Lv.50 부터", st[GROWLITHE])
            for pid in (GARCHOMP, INFERNAPE, GROWLITHE):
                click_mon(w, pid)
                settle(root, 0.1)
            chk("  눌러도 안 골라지고 쓰기는 꺼져 있다", w.mon_id is None and not w.use_btn.enabled, w.mon_id)
            click_mon(w, MIMIKYU)
            settle(root, 0.1)
            click_mon(w, GARCHOMP)
            settle(root, 0.1)
            chk("  골라 둔 따라큐가 막힌 줄을 눌렀다고 풀리지 않는다", w.mon_id == MIMIKYU, w.mon_id)

        print("8. 진짜 확인 창")
        ui_box.confirm = real_confirm
        click_item(w, "GOLDBOTTLECAP")
        settle(root, 0.2)
        click_mon(w, MIMIKYU)
        settle(root, 0.2)
        before = set(str(t) for t in toplevels(root))
        seen = {}

        def grab(n=[0]):
            new = [t for t in toplevels(root) if str(t) not in before]
            if not new:
                n[0] += 1
                if n[0] < 60:
                    return root.after(100, grab)
                return
            seen["text"] = "".join(all_text(new[-1])).replace("\n", "").replace(" ", "")
            for t in new:
                t.destroy()                      # 닫기 = 취소
        root.after(300, grab)
        used = len(api.used)
        w.do_use()
        settle(root, 0.2)
        text = seen.get("text") or ""
        chk("확인 창에 따라큐(Lv.100) · 금색병뚜껑 · 되돌릴 수 없습니다", "따라큐(Lv.100)에게금색병뚜껑을씁니다" in text
            and "되돌릴수없습니다" in text, text)
        chk("  닫으면 쓰지 않는다", len(api.used) == used, api.used)
    finally:
        ui_box.confirm = real_confirm
    chk("그리는 중에 난 예외가 없다", not errors, errors[:3])
    tabs.close()
    try:
        top.destroy()
    except tk.TclError:
        pass


def reload_switch(root, dex):
    """다 써서 다른 도구로 넘어가는 사이 '직접 고름' 이 되살아나지 않는다 (#704 리뷰).

    은색 1 · 이상한사탕 1. 은색으로 따라큐를 직접 눌러 쓴다 -> 다 써서 이상한사탕으로 넘어가고 따라큐를 이어받는다
    -> 그사이 은색을 새로 얻는다(상점 등) -> 이어받은 따라큐에게 이상한사탕을 그대로 쓴다 -> 다 써서 다시 은색으로.
    이때 따라큐가 저절로 골라지면 안 된다 (이어받은 것이지 은색으로 직접 누른 것이 아니다)."""
    print("9. 다 써서 도구가 바뀌어 가도 직접 고름이 되살아나지 않는다")
    raw = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))["items"]
    api = Api(account(dex), [dict(raw[k]) for k in ("BOTTLECAP", "RARECANDY")])
    api.bag = {"BOTTLECAP": 1, "RARECANDY": 1}
    app = App(root, api, dex)
    top = tk.Toplevel(root)
    top.geometry("1040x640+30+30")
    tabs = ui_bag_tabs.BagTabs(root, app, top)
    tabs.win.pack(fill="both", expand=True)
    w = tabs.bag
    BL.wait(root, lambda: bool(w.mons) and w._wait is None, 15)
    settle(root, 0.5)
    real_confirm = ui_box.confirm
    ui_box.confirm = lambda *a, **k: True
    try:
        click_item(w, "BOTTLECAP")
        settle(root, 0.2)
        click_mon(w, MIMIKYU)
        settle(root, 0.2)
        w.pick_stat("spe")
        w.do_use()
        BL.wait(root, lambda: len(api.used) >= 1 and w._wait is None, 8)
        settle(root, 0.4)
        chk("  은색을 다 쓰면 이상한사탕으로 넘어가고 따라큐를 이어받는다", w.item_id == "RARECANDY"
            and w.mon_id == MIMIKYU, (w.item_id, w.mon_id))
        api.bag["BOTTLECAP"] = 1                 # 다른 탭(상점)에서 새로 샀다 - 가방은 아직 안 불러옴
        w.do_use()                               # 이어받은 따라큐에게 이상한사탕 (누르지 않음)
        BL.wait(root, lambda: len(api.used) >= 2 and w._wait is None, 8)
        settle(root, 0.4)
        chk("  다시 은색으로 넘어가도 따라큐가 저절로 골라지지 않는다", w.item_id == "BOTTLECAP"
            and w.mon_id is None and not w.use_btn.enabled, (w.item_id, w.mon_id, w.use_btn.enabled))
    finally:
        ui_box.confirm = real_confirm
    tabs.close()
    try:
        top.destroy()
    except tk.TclError:
        pass


def main():
    dex = P.Pokedex(json.load(open(os.path.join(DATA, "pokedex.json"), encoding="utf-8")))
    if SKIN == "default":
        pure()
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    behave(root, dex)
    reload_switch(root, dex)
    try:
        root.destroy()
    except tk.TclError:
        pass


if __name__ == "__main__":
    main()
    if SKIN == "default" and not os.environ.get("POKET_BOTTLECAP_CHILD"):
        for key in THEMES:
            env = dict(os.environ, POKET_BOTTLECAP_SKIN=key, POKET_BOTTLECAP_CHILD="1",
                       POKET_HOME=os.path.join(os.environ["POKET_HOME"], key))
            out = subprocess.run([sys.executable, os.path.abspath(__file__)], env=env, capture_output=True, text=True)
            for line in out.stdout.splitlines():
                if line.startswith("  ") or line.startswith("==") or line[:2].rstrip(".").isdigit():
                    print(line)
                if line.startswith("합계"):
                    bits = line.split()
                    OK += int(bits[2])
                    FAIL += int(bits[4])
            if out.returncode != 0 or "합계" not in out.stdout:
                FAIL += 1
                print("  FAIL %s 검사가 끝나지 않았다\n%s" % (key, out.stderr[-1500:]))
    print("합계 OK %d FAIL %d" % (OK, FAIL))
    sys.exit(1 if FAIL else 0)
