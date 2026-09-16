# -*- coding: utf-8 -*-
"""기술 떠올리기 — 진짜 Tk 로 확인.

    python client/smoke_remember.py

서버 없이 돈다. **창을 진짜로 띄운다**(CI 의 맥·윈도우 잡).

## 무엇을 못 박나

  1. 떠올리기 창에 받은 기술이 전부, 설명까지 **눌리지 않고** 나온다.
     가장 긴 설명들을 몰아넣어 잰다(ui_learn 검사와 같은 까닭).
  2. 줄 꼬리표가 맞다 - Lv.N / 진화 / 배우려던 기술, 공짜면 '무료'.
  3. **말없이 무시하지 않는다.** 고르기 전에 누르거나 돈이 모자라면
     창을 닫지 않고 까닭을 적는다. 기술을 못 배운다는 신고가 실제로
     그렇게 왔다('결정' 이 아무 반응 없었다).
  4. 떠올릴 게 없으면 그렇게 말하고 '닫기' 만 있다.
  5. 포켓몬 관리 창: 단추는 포켓몬을 골라야 켜지고, 배우려던 기술이 있으면
     기술 칸 아래에 적힌다. 누르면 목록 -> 고르기 -> (네 개면) 잊을 기술 ->
     서버 순서로 가고, 도중에 닫으면 서버에 아무것도 안 보낸다.
     결과 말은 다시 불러온 뒤에도 남는다.
"""
import json
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-smoke-remember-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_box, ui_learn, ui_remember      # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402

import smoke_box_filter as SB                               # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0
DEX_PATH = os.path.join(HERE, "..", "server", "data", "pokedex.json")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, n=8):
    for _ in range(n):
        root.update()


def wait_for(root, cond, secs=5):
    end = time.time() + secs
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.02)
    return cond()


def entry(dex, move, level, free=False):
    return {"move": move, "kr": dex.move_name(move), "level": level, "free": free}


def run_dialog(root, d, action, hold=400):
    """창을 띄우고 hold ms 뒤 action(d) 을 부른다. 그때의 모습과 답을 돌려준다."""
    box = {}

    def go():
        if not d.win.winfo_exists():
            return
        root.update_idletasks()
        box["sq"] = squeezed(d.win)
        box["size"] = (d.win.winfo_width(), d.win.winfo_height())
        box["texts"] = texts(d.win)
        box["seen"] = d.canvas.winfo_height()
        box["need"] = d.box.winfo_reqheight()
        action(d, box)
    root.after(hold, go)
    box["result"] = d.show()
    return box


def dialog_checks(root, dex):
    print("\n=== 떠올리기 창 - 가장 긴 설명 다섯 개")
    moves = dex.moves
    longest = sorted(moves, key=lambda k: -len(moves[k].get("desc") or ""))[:5]
    ents = [entry(dex, longest[0], 1), entry(dex, longest[1], 0),
            entry(dex, longest[2], 44, free=True), entry(dex, longest[3], None, free=True),
            entry(dex, longest[4], 30)]
    d = ui_remember.RememberAsk(root, "메꾸리", ents, 5000, 12000, dex)
    got = run_dialog(root, d, lambda d, b: d._cancel())
    chk("창이 떴다", got["size"][0] > 100 and got["size"][1] > 100, got["size"])
    chk("눌린 것이 없다", not got["sq"], got["sq"][:4])
    chk("다섯 줄이 다 있다", len(d.rows) == 5, list(d.rows))
    for k in longest:
        chk("%s 설명이 실렸다" % moves[k]["kr"], moves[k]["desc"] in got["texts"])
    tx = got["texts"]
    chk("값과 가진 돈이 보인다",
        any("5,000원" in t and "12,000원" in t for t in tx), tx[:4])
    chk("공짜 안내가 보인다 (공짜 기술이 있을 때)", any("무료입니다" in t for t in tx))
    for want in ("Lv.1", "진화", "Lv.44 · 무료", "배우려던 기술 · 무료", "Lv.30"):
        chk("꼬리표 '%s'" % want, want in tx, want)
    cap = root.winfo_screenheight() - ui_learn.SCREEN_PAD
    if got["size"][1] < cap:
        chk("다섯 줄이 다 보인다 (굴릴 필요 없다)", got["seen"] >= got["need"],
            (got["seen"], got["need"]))
    chk("창이 화면 안에 있다", got["size"][1] <= root.winfo_screenheight(), got["size"])
    chk("그냥 닫으면 None", got["result"] is None, got["result"])

    print("\n=== 떠올리기 창 - 고르기와 돈")
    ents = [entry(dex, "GROWL", 1), entry(dex, "TAKEDOWN", 44, free=True),
            entry(dex, "AIRSLASH", 0)]
    chk("공짜가 없으면 공짜 안내도 없다",
        not any("무료입니다" in t for t in texts(
            ui_remember.RememberAsk(root, "리자몽", ents[:1], 5000, 0, dex).win)))
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            w.destroy()

    def press_empty(d, b):
        d._ok()
        b["open"] = d.win.winfo_exists()
        b["hint"] = d.hint.cget("text")
        d._cancel()
    got = run_dialog(root, ui_remember.RememberAsk(root, "리자몽", ents, 5000, 12000, dex),
                     press_empty)
    chk("고르기 전에 누르면 닫히지 않는다", got["open"])
    chk("  까닭을 적는다", "고르세요" in got["hint"], got["hint"])

    def pick_paid(d, b):
        d._pick("GROWL")
        b["hint"] = d.hint.cget("text")
        d._ok()
    got = run_dialog(root, ui_remember.RememberAsk(root, "리자몽", ents, 5000, 12000, dex),
                     pick_paid)
    chk("돈이 되면 고른 기술을 돌려준다", got["result"] == "GROWL", got["result"])
    chk("  고르면 낼 돈을 적는다", "5,000원" in got["hint"], got["hint"])

    def poor(d, b):
        d._pick("AIRSLASH")
        d._ok()
        b["open"] = d.win.winfo_exists()
        b["hint"] = d.hint.cget("text")
        d._pick("TAKEDOWN")
        b["free_hint"] = d.hint.cget("text")
        d._ok()
    got = run_dialog(root, ui_remember.RememberAsk(root, "메꾸리", ents, 5000, 3000, dex),
                     poor)
    chk("돈이 모자라면 닫히지 않는다", got["open"])
    chk("  얼마가 모자란지 적는다", "2,000원 모자랍니다" in got["hint"], got["hint"])
    chk("  공짜 기술은 돈이 모자라도 고를 수 있다", got["result"] == "TAKEDOWN", got["result"])
    chk("  공짜라고 적는다", "무료" in got["free_hint"], got["free_hint"])

    print("\n=== 떠올리기 창 - 떠올릴 게 없다")

    def close_empty(d, b):
        b["btn"] = d.ok_btn.label.cget("text")
        d.ok_btn.command()
    got = run_dialog(root, ui_remember.RememberAsk(root, "피츄", [], 5000, 0, dex), close_empty)
    chk("없다고 말한다", any("떠올릴 수 있는 기술이 없습니다" in t for t in got["texts"]))
    chk("  단추는 '닫기'", got["btn"] == "닫기", got["btn"])
    chk("  닫으면 None", got["result"] is None, got["result"])
    chk("  눌린 것이 없다", not got["sq"], got["sq"][:4])

    print("\n=== 무엇을 버릴까 창도 말없이 무시하지 않는다")
    fa = ui_learn.ForgetAsk(root, "메꾸리", "TAKEDOWN",
                            ["ICEFANG", "ICYWIND", "FLAIL", "ICESHARD"], dex)

    def forget_empty(d, b):
        d._ok()
        b["open"] = d.win.winfo_exists()
        b["hint"] = d.hint.cget("text")
        d._pick("FLAIL")
        d._ok()
    got = run_dialog(root, fa, forget_empty)
    chk("고르기 전에 '결정' 을 누르면 까닭을 적는다", got["open"] and "고르세요" in got["hint"],
        got.get("hint"))
    chk("  고르고 누르면 그 기술", got["result"] == "FLAIL", got["result"])
    chk("  눌린 것이 없다", not got["sq"], got["sq"][:4])

    print("\n=== 꼬리표")
    chk("Lv.7", ui_remember.tag_text({"level": 7}) == "Lv.7")
    chk("진화", ui_remember.tag_text({"level": 0}) == "진화")
    chk("레벨 없음", ui_remember.tag_text({"level": None, "free": True}) == "배우려던 기술 · 무료")


class Api(SB.FakeApi):
    def __init__(self, mons, dex):
        SB.FakeApi.__init__(self, mons)
        self.dex = dex
        self.money = 12000
        self.fail = None

    def remember_list(self, pid):
        self.calls.append(("remember_list", pid))
        m = next(x for x in self.mons if x["id"] == pid)
        ents = [entry(self.dex, "GROWL", 1), entry(self.dex, "EMBER", 4)]
        ents += [entry(self.dex, k, None, free=True) for k in m.get("pending") or []]
        return {"pokemon": pid, "name": m["info"]["name"], "moves": list(m["moves"]),
                "remember": ents, "cost": 5000, "money": self.money}

    def remember(self, pid, move, forget=""):
        self.calls.append(("remember", pid, move, forget))
        if self.fail:
            from poketdesktop.api import ApiError
            raise ApiError(self.fail, 400)
        m = next(x for x in self.mons if x["id"] == pid)
        kr = self.dex.move_name(move)
        if forget:
            m["moves"] = [move if x == forget else x for x in m["moves"]]
        else:
            m["moves"] = m["moves"] + [move]
        cost = 0 if move in (m.get("pending") or []) else 5000
        m["pending"] = [x for x in m.get("pending") or [] if x != move]
        self.money -= cost
        return {"ok": True, "moves": m["moves"], "cost": cost, "money": self.money,
                "message": "%s은(는) %s을(를) 떠올렸다!" % (m["info"]["name"], kr)}


def box_mon(dex, num, pid, moves, pending=()):
    m = SB.mon(dex, num, pid, on=True)
    m["moves"] = list(moves)
    m["pending"] = list(pending)
    m["info"] = dex.describe(dict(m, exp=m["info"].get("exp", 0)))
    m["info"]["name"] = dex.get(num)["kr"]
    return m


def box_checks(root, dex):
    print("\n=== 포켓몬 관리 창")
    mons = [box_mon(dex, 6, 1, ["SCRATCH"]),
            box_mon(dex, 221, 2, ["ICEFANG", "ICYWIND", "FLAIL", "ICESHARD"],
                    pending=["TAKEDOWN"])]
    app = SB.FakeApp(root, dex, mons)
    app.api = Api(mons, dex)
    real_ensure = ui_box.sprite_cache.ensure
    ui_box.sprite_cache.ensure = lambda api, num, shiny=False: None
    real_remember, real_forget = ui_remember.ask_remember, ui_learn.ask_forget
    try:
        app.api.gate.clear()             # 불러오기를 붙잡아 '고르기 전' 을 본다
        win = ui_box.BoxWindow(root, app)
        btn = win.btn_remember
        settle(root)
        chk("단추 글씨 '기술 떠올리기'", btn.label.cget("text") == "기술 떠올리기",
            btn.label.cget("text"))
        chk("포켓몬을 고르기 전에는 꺼져 있다", win.sel is None and not btn.enabled,
            (win.sel, btn.enabled))
        app.api.gate.set()
        wait_for(root, lambda: getattr(win, "mons", None))
        SB.settle_rows(root, win)
        chk("불러오면 첫 포켓몬이 골라지고 켜진다", win.sel == 1 and btn.enabled,
            (win.sel, btn.enabled))
        win.select(1)
        settle(root)
        hold = btn.holder
        chk("단추 글씨가 안 잘린다",
            hold.winfo_width() >= btn.label.winfo_reqwidth() + 8,
            (hold.winfo_width(), btn.label.winfo_reqwidth()))
        head = hold.master
        chk("단추가 머리줄 안에 있다",
            hold.winfo_x() >= 0 and hold.winfo_x() + hold.winfo_width() <= head.winfo_width(),
            (hold.winfo_x(), hold.winfo_width(), head.winfo_width()))
        chk("배우려던 기술이 없으면 안내도 없다", not win.d_pending.winfo_manager())

        win.select(2)
        settle(root)
        chk("배우려던 기술이 기술 칸 아래에 적힌다",
            win.d_pending.winfo_manager() and "돌진" in win.d_pending.cget("text")
            and "무료" in win.d_pending.cget("text"), win.d_pending.cget("text"))
        chk("  안내가 눌리지 않는다",
            win.d_pending.winfo_height() >= win.d_pending.winfo_reqheight() - 1,
            (win.d_pending.winfo_height(), win.d_pending.winfo_reqheight()))
        win.select(1)
        settle(root)
        chk("다른 포켓몬을 고르면 안내가 빠진다", not win.d_pending.winfo_manager())

        print("-- 자리가 남은 리자몽: 목록 -> 고르기 -> 서버")
        seen = {}

        def fake_remember(parent, name, ents, cost, money, dex=None):
            seen.update(name=name, moves=[e["move"] for e in ents], cost=cost, money=money)
            return "GROWL"
        ui_remember.ask_remember = fake_remember
        ui_learn.ask_forget = lambda *a, **k: seen.setdefault("forget_asked", True) and None
        api = app.api
        api.calls[:] = []
        win.do_remember()
        wait_for(root, lambda: ("remember", 1, "GROWL", "") in api.calls)
        wait_for(root, lambda: "떠올렸다" in win.status.cget("text"), 3)
        settle(root, 20)
        chk("목록을 서버에 묻는다", ("remember_list", 1) in api.calls, api.calls)
        chk("  받은 이름·값·돈을 창에 준다",
            seen.get("name") == "리자몽" and seen.get("cost") == 5000
            and seen.get("money") == 12000, seen)
        chk("기술이 하나라 잊을 기술은 안 묻는다", "forget_asked" not in seen, seen)
        chk("고른 기술로 떠올린다", ("remember", 1, "GROWL", "") in api.calls, api.calls)
        st = win.status.cget("text")
        chk("다시 불러온 뒤에도 결과 말이 남는다 (값까지)",
            "떠올렸다" in st and "5,000원" in st, st)
        chk("  앱에도 알린다 (돈이 바뀌었다)", app.synced >= 1, app.synced)

        print("-- 기술이 네 개인 메꾸리: 잊을 기술까지")
        win.select(2)
        settle(root)
        ui_remember.ask_remember = lambda *a, **k: "TAKEDOWN"
        asked = {}

        def fake_forget(parent, name, new, known, dex=None):
            asked.update(new=new, known=list(known))
            return "FLAIL"
        ui_learn.ask_forget = fake_forget
        api.calls[:] = []
        win.do_remember()
        wait_for(root, lambda: any(c[0] == "remember" for c in api.calls))
        settle(root, 20)
        chk("네 개면 잊을 기술을 묻는다",
            asked.get("new") == "TAKEDOWN"
            and asked.get("known") == ["ICEFANG", "ICYWIND", "FLAIL", "ICESHARD"], asked)
        chk("  고른 기술을 잊고 떠올린다", ("remember", 2, "TAKEDOWN", "FLAIL") in api.calls,
            api.calls)

        print("-- 도중에 그만두면 서버에 아무것도 안 보낸다")
        mons[1]["moves"] = ["ICEFANG", "ICYWIND", "TAKEDOWN", "ICESHARD"]
        for pick, forget, why in ((None, "FLAIL", "떠올리기 창을 닫았다"),
                                  ("GROWL", None, "잊을 기술 창을 닫았다"),
                                  ("GROWL", "", "잊을 기술 창에서 떠올릴 기술을 골랐다")):
            ui_remember.ask_remember = lambda *a, _p=pick, **k: _p
            ui_learn.ask_forget = lambda *a, _f=forget, **k: _f
            api.calls[:] = []
            win.do_remember()
            wait_for(root, lambda: ("remember_list", 2) in api.calls)
            settle(root, 20)
            chk(why, not any(c[0] == "remember" for c in api.calls), api.calls)

        print("-- 서버가 거절하면 그 말을 적는다")
        ui_remember.ask_remember = lambda *a, **k: "GROWL"
        ui_learn.ask_forget = lambda *a, **k: "ICEFANG"
        api.fail = "골드가 부족합니다. 5,000원이 필요한데 2,000원 있습니다."
        win.do_remember()
        wait_for(root, lambda: "골드가 부족" in win.status.cget("text"))
        chk("거절 말이 보인다", "골드가 부족" in win.status.cget("text"),
            win.status.cget("text"))
        chk("  빨간 글씨", win.status.cget("fg") == U.DANGER, win.status.cget("fg"))
        api.fail = None

        print("-- 진짜 창으로 한 번 (고르고 '떠올리기')")
        ui_remember.ask_remember = real_remember
        ui_learn.ask_forget = real_forget
        win.select(1)
        settle(root)
        box = {}
        real_cls = ui_remember.RememberAsk

        class Spy(real_cls):
            def __init__(self, *a, **k):
                real_cls.__init__(self, *a, **k)
                box["d"] = self
                self.win.after(400, lambda: (self._pick("EMBER"), self._ok()))
        ui_remember.RememberAsk = Spy
        api.calls[:] = []
        win.do_remember()
        wait_for(root, lambda: any(c[0] == "remember" for c in api.calls), 6)
        settle(root, 20)
        ui_remember.RememberAsk = real_cls
        chk("관리 창에서 떠올리기 창이 뜬다", "d" in box)
        chk("  고른 기술이 서버로 간다", ("remember", 1, "EMBER", "") in api.calls, api.calls)
        win.close()
    finally:
        ui_box.sprite_cache.ensure = real_ensure
        ui_remember.ask_remember = real_remember
        ui_learn.ask_forget = real_forget


def main():
    with open(DEX_PATH, encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    print("글꼴 %s / 본문 %dpt" % (U.FAMILY, U.FONT[1]))
    try:
        dialog_checks(root, dex)
        box_checks(root, dex)
    finally:
        try:
            root.destroy()
        except Exception:                                   # noqa: BLE001
            pass
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
