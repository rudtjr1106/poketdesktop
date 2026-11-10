# -*- coding: utf-8 -*-
"""도감 업적 화면 검사 (시즌 3). 진짜 Tk 로 띄운다.

    python client/test_achievements_ui.py

  1. 달성 알림 창: 하나면 '업적 달성!', 여럿이면 '지금까지의 기록으로' 로
     묶고 여덟 줄 넘게는 '그 밖 N개'. 칭호·볼 보상을 적는다. 눌린 위젯 없음.
  2. 업적 칸: 갈래로 묶고, 안 한 것은 진행 막대, 한 것은 달성 날짜.
     숨은 업적은 서버가 가려 보낸 그대로(???).
  3. 도감 탭의 '업적' 단추로 격자와 번갈아 본다.
  4. 같은 업적이 다음 동기화에 또 실려 와도 **두 번 띄우지 않는다.**
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-ach-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_achievements as UA              # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def pump(root, cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return False


def ach(key, name, group="도감 수집", title=None, balls=0, got=False, value=0,
        target=50, hidden=False):
    a = {"key": key, "group": group, "name": name, "desc": "%s 설명" % name,
         "target": target, "title": title, "balls": balls, "hidden": hidden}
    if got:
        a["gotAt"] = "2026-10-02T00:10:00+00:00"
    else:
        a["value"] = value
    return a


PUBLIC = {
    "done": 2, "total": 5,
    "unlocks": {"unlock_7": True, "unlock_9": False},
    "achievements": [
        ach("dex_50", "50종", balls=5, got=True),
        ach("dex_400", "400종", title="도감 조사원", value=120, target=400),
        ach("region_1", "관동 도감 완성", group="지방 도감", title="관동 도감 완성",
            value=100, target=146),
        ach("unlock_ultra", "울트라홀 개척자", group="해금", title="울트라홀 개척자",
            got=True, target=49),
        {"key": "hidden_nick", "group": "숨은 업적", "name": "???", "desc": "숨은 업적",
         "target": 1, "title": None, "balls": 0, "hidden": True},
    ],
}


class FakeApi(object):
    def __init__(self):
        self.calls = []

    def achievements(self):
        self.calls.append("list")
        return PUBLIC

    def titles(self):
        self.calls.append("titles")
        return {"owned": 1, "total": 5, "season": 3, "seasonEnds": "2026-10-16", "titles": [
            {"id": "ach_dex_400", "name": "도감 조사원", "group": "도감 수집",
             "how": "포켓몬 400종을 잡아 도감에 올리기", "owned": False, "open": True,
             "value": 120, "target": 400},
            {"id": "ach_region_1", "name": "관동 도감 완성", "group": "지방 도감",
             "how": "관동 지방 포켓몬을 모두 잡기 (전설·환상 제외)", "owned": True, "open": True},
            {"id": "ach_hidden_midnight", "name": "???", "group": "숨은 업적",
             "how": "숨은 업적 - 달성하면 알 수 있다", "owned": False, "open": True},
            {"id": "s3_master", "name": "시즌 3 마스터볼", "group": "랭킹전 시즌 3",
             "how": "시즌 3 에서 마스터볼 티어(RP 600)에 오르기 - 시즌이 끝날 때 받는다",
             "owned": False, "open": True},
            {"id": "s2_super", "name": "시즌 2 슈퍼볼", "group": "지난 시즌 (다시 얻을 수 없음)",
             "how": "시즌 2 에서 슈퍼볼 티어(RP 150)에 오르기 - 시즌이 끝날 때 받는다",
             "owned": False, "open": False}]}

    def achievements_seen(self):
        self.calls.append("seen")
        return {"ok": True}


class FakeApp(object):
    def __init__(self, root):
        self.root = root
        self.api = FakeApi()
        self.dex = None
        self.notes = []

    def notify(self, message):
        self.notes.append(message)


def close_toplevels(root):
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            try:
                w.destroy()
            except tk.TclError:
                pass


def entry_dialog(root, real_dex, DexApi, FakeApp):
    """도감 칸을 누르면 그 포켓몬의 도감 글 창 (게시판 #496, 11/10).

    잡은 종은 본가 도감 글, 본 것만이면 '잡으면 볼 수 있다', 한국어 글이 없는 종(899번부터)은 '아직 없다'.
    본 적 없는 칸은 안 열린다. 한 번에 한 창. 창은 내용만큼이고 눌린 위젯이 없다.
    """
    from poketdesktop import ui_dex
    print("\n=== 도감 칸을 누르면 도감 글 (게시판 #496) ===")

    class Api(DexApi):
        def dexbook(self):
            return {"seen": [1, 25, 906], "caught": [25, 906], "gens": {}, "total": 1025}
    app = FakeApp(root)
    app.api = Api()
    app.dex = real_dex
    dw = ui_dex.DexWindow(app)
    pump(root, lambda: len(dw.rows) > 900 and dw.seen)
    root.update()

    def click(n):
        """칸 n 의 가운데를 진짜로 누른다 (굴려서 보이게 한 뒤)."""
        i = next(k for k, sp in enumerate(dw.rows) if sp["num"] == n)
        cw, ch = ui_dex.CELL_W + ui_dex.PAD, ui_dex.CELL_H + ui_dex.PAD
        x = ui_dex.PAD + (i % dw.cols) * cw + ui_dex.CELL_W // 2
        y = ui_dex.PAD + (i // dw.cols) * ch + ui_dex.CELL_H // 2
        total = float(dw.cv.bbox("all")[3] if dw.cv.bbox("all") else 1)
        dw.cv.yview_moveto(max(0.0, (y - 40) / total))
        root.update()
        dw.cv.event_generate("<Button-1>", x=x, y=int(y - dw.cv.canvasy(0)))
        root.update()
        return dw._entry

    def body_text(win):
        return " ".join(" ".join(texts(win)).split())

    pika = real_dex.get(25)["flavor"]
    w = click(25)
    chk("잡은 칸(피카츄)을 누르면 도감 글 창", w is not None and w.winfo_exists())
    if w is None:
        dw.close()
        return
    t = body_text(w)
    chk("  번호 · 이름 · 분류 · 타입 · 키 · 몸무게 · 세대", all(s in t for s in ("No.0025", "피카츄", "쥐포켓몬", "전기",
                                                                     "키 0.4m", "몸무게 6kg", "1세대")), t[:160])
    chk("  본가 도감 글 (소드)", " ".join(pika.split()) in t, (pika, t[-120:]))
    lab = w.entry_text
    chk("  글은 창 폭 안에서 접힌다", lab.winfo_x() + lab.winfo_width() <= lab.master.winfo_width() + 1
        and lab.winfo_reqwidth() <= lab.master.winfo_width() + 1, (lab.winfo_reqwidth(), lab.master.winfo_width()))
    chk("  창은 내용만큼 (모자라지도 남지도 않는다)", abs(w.winfo_height() - w.winfo_reqheight()) <= 2,
        (w.winfo_height(), w.winfo_reqheight()))
    chk("  눌린 위젯이 없다", not squeezed(w), squeezed(w)[:3])
    w2 = click(906)
    chk("한국어 도감 글이 없는 종(906)은 '아직 없다' - 창은 하나만", "아직 이 포켓몬의 도감 설명이 없다" in body_text(w2)
        and not w.winfo_exists() and w2.winfo_exists(), body_text(w2)[-60:])
    w3 = click(1)
    chk("본 것만(이상해씨)이면 '잡으면 볼 수 있다' - 글은 안 보인다", "잡으면 도감 설명을 볼 수 있다" in body_text(w3)
        and (real_dex.get(1)["flavor"][:8] not in body_text(w3)), body_text(w3)[-60:])
    dw._close_entry()
    root.update()
    chk("본 적 없는 칸(파이리)은 안 열린다", click(4) is None)
    w4 = click(25)
    dw.close()
    root.update()
    chk("도감을 닫으면 도감 글 창도 닫힌다", not w4.winfo_exists())


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    print("글꼴 %s / 본문 %dpt" % (U.FAMILY, U.BASE_PT))
    app = FakeApp(root)

    print("=== 알림 창 — 하나 ===")
    shot = {}
    orig_wait = root.wait_window

    def spy_wait(win):
        root.update()
        win.update_idletasks()
        shot["t"] = " ".join(texts(win))
        shot["bad"] = squeezed(win)
        win.destroy()
    root.wait_window = spy_wait
    UA.announce(root, app, [ach("dex_400", "400종", title="도감 조사원", got=True)])
    chk("'업적 달성!'", "업적 달성!" in shot["t"], shot["t"][:80])
    chk("칭호 보상을 적는다", "도감 조사원" in shot["t"], shot["t"][:120])
    chk("칭호를 어디서 다는지 알려준다 (마이페이지, 1.12.1)", "마이페이지" in shot["t"])
    chk("눌린 위젯 없음", not shot["bad"], shot["bad"][:3])

    print("\n=== 알림 창 — 여럿 (처음 켠 사람) ===")
    many = [ach("k%d" % i, "업적%d" % i, balls=5 if i % 2 else 0,
                title=None if i % 2 else "칭호%d" % i, got=True) for i in range(12)]
    UA.announce(root, app, many)
    chk("한 창에 묶는다", "지금까지의 기록으로 업적 12개" in shot["t"], shot["t"][:80])
    chk("여덟 줄 넘게는 '그 밖'", "그 밖 4개" in shot["t"], shot["t"][-120:])
    chk("볼 보상도 적는다", "몬스터볼 5개" in shot["t"])
    chk("눌린 위젯 없음", not shot["bad"], shot["bad"][:3])
    root.wait_window = orig_wait

    print("\n=== 업적 칸 ===")
    host = tk.Toplevel(root)
    host.geometry("900x620+40+40")
    p = UA.AchievementPanel(host, app)
    p.pack(fill="both", expand=True)
    p.reload()
    pump(root, lambda: p.data is not None)
    root.update()
    t = " ".join(texts(host))
    chk("달성 수", "달성 2 / 5" in t, t[:80])
    chk("갈래로 묶는다", "도감 수집  1/2" in t and "지방 도감  0/1" in t, t[:300])
    chk("한 것은 날짜", "2026-10-02 달성" in t, t[:300])
    chk("안 한 것은 진행 수", "120 / 400" in t and "100 / 146" in t, t[:400])
    chk("숨은 업적은 가려진 채로", "???" in t)
    chk("열린 해금을 알려준다", "열림: 울트라홀" in t, t[:200])
    bad = squeezed(host)
    chk("눌린 위젯 없음", not bad, bad[:3])
    host.destroy()

    print("\n=== 도감 탭에서 번갈아 보기 ===")
    from poketdesktop import ui_dex

    class DexApi(FakeApi):
        def dexbook(self):
            return {"seen": [], "caught": [], "gens": {}, "total": 0}
    app2 = FakeApp(root)
    app2.api = DexApi()
    try:
        dw = ui_dex.DexWindow(app2)
    except Exception as e:                                  # noqa: BLE001
        dw = None
        chk("도감 창이 뜬다", False, e)
    if dw is not None:
        root.update()
        chk("처음엔 격자", dw.dex_body.winfo_manager() and dw.ach is None)
        dw.toggle_achievements()
        pump(root, lambda: dw.ach is not None and dw.ach.data is not None)
        root.update()
        chk("누르면 업적 칸", dw.ach.f.winfo_manager() and not dw.dex_body.winfo_manager())
        chk("단추가 '도감으로'", "도감으로" in dw.ach_btn.label.cget("text"),
            dw.ach_btn.label.cget("text"))
        dw.toggle_achievements()
        root.update()
        chk("다시 누르면 격자", dw.dex_body.winfo_manager() and not dw.ach.f.winfo_manager())
        chk("단추에 업적 수", "업적 2/5" in dw.ach_btn.label.cget("text"),
            dw.ach_btn.label.cget("text"))
        bad = squeezed(dw.win)
        chk("머리줄 눌림 없음", not bad, bad[:3])

        print("\n=== 도감 탭의 이름 찾기 (1.10.6) ===")
        # (위의 창은 도감 자료 없이 띄웠다. 찾기는 진짜 도감으로 본다.)
        import json
        from common import pokelogic as P
        with open(os.path.join(os.path.dirname(HERE), "server", "data", "pokedex.json"), encoding="utf-8") as f:
            real_dex = P.Pokedex(json.load(f))
        app3 = FakeApp(root)
        app3.api = DexApi()
        app3.dex = real_dex
        dq = ui_dex.DexWindow(app3)
        pump(root, lambda: len(dq.rows) > 900)
        root.update()
        total = len(dq.rows)
        # **칸의 글이 바뀌면 바로 찾는다** - 키를 뗀 때가 아니다. 한글은 조합이 끝나야 칸에 들어가고
        # 그때는 키 이벤트가 안 온다 (제보 #194: 도감 탭에서 검색이 안 된다).
        dq.qv.set("피카")
        root.update()
        got = [sp["kr"] for sp in dq.rows]
        chk("글이 들어가면 키를 누르지 않아도 걸러진다 (피카 -> 피카츄)", dq.q == "피카" and "피카츄" in got
            and 0 < len(got) < 10 and all("피카" in n for n in got), got)
        dq.qv.set("25")
        root.update()
        nums = [sp["num"] for sp in dq.rows]
        chk("도감 번호로도 찾는다 (25 -> 25번과 250번대)", 25 in nums and 250 in nums and 125 not in nums
            and 1025 not in nums, nums[:14])
        dq.qv.set("0025")
        root.update()
        chk("  네 자리로 치면 그 번호만", [sp["num"] for sp in dq.rows] == [25], [sp["num"] for sp in dq.rows])
        dq.qv.set(" PIKA chu ")
        root.update()
        chk("영어 이름으로도 (대소문자·빈칸은 안 가린다)", [sp["kr"] for sp in dq.rows] == ["피카츄"], [sp["kr"] for sp in dq.rows])
        dq.qv.set("없는포켓몬이름")
        root.update()
        chk("맞는 것이 없으면 빈 격자", dq.rows == [])
        dq.qv.set("")
        root.update()
        chk("지우면 전부 돌아온다", len(dq.rows) == total and total > 900, (len(dq.rows), total))
        Q = ui_dex.query_hit
        pika = {"kr": "피카츄", "en": "Pikachu", "num": 25}
        chk("찾기 규칙: 이름의 일부 · 번호의 앞부분", Q(pika, "카츄") and Q(pika, "2") and Q(pika, "025") and Q(pika, "")
            and not Q(pika, "5") and not Q(pika, "125") and not Q(pika, "꼬부기") and not Q({"kr": None, "num": 0}, "x"))
        dq.close()                                  # (아래 휠 검사가 화면의 그 자리를 본다 - 창을 남기지 않는다)
        root.update()
        entry_dialog(root, real_dex, DexApi, FakeApp)

        # ---- 칭호 목록 (1.8.1): 칭호마다 얻는 조건 ----
        print("\n=== 도감 탭의 칭호 목록 ===")
        chk("'칭호' 단추가 있다", dw.title_btn.label.cget("text") == "칭호",
            dw.title_btn.label.cget("text"))
        dw.toggle_titles()
        pump(root, lambda: dw.titles is not None and dw.titles.data is not None)
        root.update()
        chk("누르면 칭호 목록", dw.titles.f.winfo_manager() and not dw.dex_body.winfo_manager())
        chk("  단추가 '도감으로'", dw.title_btn.label.cget("text") == "도감으로")
        got = []

        def walk(w):
            for c in w.winfo_children():
                try:
                    t = c.cget("text")
                    if t:
                        got.append(str(t))
                except tk.TclError:
                    pass
                walk(c)
        walk(dw.titles.f)
        chk("가진 수를 적는다", "가진 칭호 1 / 5" in got, got[:4])
        chk("칭호 이름과 얻는 조건이 같이 보인다",
            "「도감 조사원」" in got and any("400종" in t for t in got), got[:12])
        chk("가진 칭호에는 별과 '가지고 있음'", "★ 「관동 도감 완성」" in got and "가지고 있음" in got, got)
        chk("못 얻은 것은 진행을 보여 준다", "120 / 400" in got, got)
        chk("숨은 칭호는 가린다", "「???」" in got and any("숨은 업적" in t for t in got))
        chk("랭킹전 칭호의 조건", any("마스터볼 티어(RP 600)" in t for t in got), got)
        chk("지난 시즌 칭호는 '지금은 얻을 수 없음'", "지금은 얻을 수 없음" in got
            and any(t.startswith("지난 시즌") for t in got), got)
        bad = squeezed(dw.win)
        chk("  눌린 위젯 없음", not bad, bad[:3])
        dw.toggle_achievements()
        pump(root, lambda: dw.ach.f.winfo_manager())
        root.update()
        chk("업적을 누르면 칭호 목록은 숨는다 (셋 중 하나만 보인다)",
            dw.ach.f.winfo_manager() and not dw.titles.f.winfo_manager()
            and not dw.dex_body.winfo_manager())
        chk("  칭호 단추는 다시 '칭호'", dw.title_btn.label.cget("text") == "칭호")
        dw.toggle_titles()
        root.update()
        dw.toggle_titles()
        root.update()
        chk("칭호에서 다시 누르면 격자", dw.dex_body.winfo_manager()
            and not dw.titles.f.winfo_manager() and not dw.ach.f.winfo_manager())

        # 칭호는 실제로 예순 개쯤 된다. 창보다 길어도 **굴려서 끝까지 본다** (잘리면 안 된다).
        print("\n=== 칭호가 많을 때 (굴리기) ===")
        many = dict(app2.api.titles())
        many["titles"] = [dict(many["titles"][i % 5], id="t%d" % i,
                               name="칭호 %02d" % i) for i in range(60)]
        many["total"] = 60
        app2.api.titles = lambda: many
        dw.toggle_titles()
        pump(root, lambda: dw.titles.data is not None and dw.titles.data.get("total") == 60)
        for _ in range(40):
            root.update()
            time.sleep(0.01)
        tp = dw.titles
        rows = [w for w in tp.body.winfo_children() if w.winfo_children()
                and w.cget("highlightthickness") in (1, "1")]
        chk("예순 줄이 다 그려진다", len(rows) == 60, len(rows))
        view_h, all_h = tp.cv.winfo_height(), tp.body.winfo_reqheight()
        chk("내용이 창보다 길다 (검사 전제)", all_h > view_h * 2, (all_h, view_h))
        region = [float(x) for x in str(tp.cv.cget("scrollregion")).split()]
        chk("굴리는 영역이 내용 전체를 덮는다", len(region) == 4 and region[3] >= all_h - 2,
            (region, all_h))
        chk("휠로 굴릴 수 있게 걸려 있다", getattr(tp.cv, "wheel_div", 0) > 0)
        lo, hi = tp.cv.yview()
        chk("처음엔 맨 위, 일부만 보인다", lo == 0.0 and hi < 0.6, (lo, hi))
        # 진짜 휠 사건을 목록 위에서 낸다
        x = tp.cv.winfo_rootx() + 40
        y = tp.cv.winfo_rooty() + 40
        for _ in range(6):
            dw.win.event_generate("<MouseWheel>", delta=-120, rootx=x, rooty=y)
            root.update()
        chk("휠을 내리면 아래로 굴러간다", tp.cv.yview()[0] > 0.0, tp.cv.yview())
        tp.cv.yview_moveto(1.0)
        root.update()
        last = rows[-1]
        bottom = last.winfo_rooty() + last.winfo_height()
        chk("끝까지 굴리면 마지막 줄이 통째로 보인다 (안 잘린다)",
            tp.cv.yview()[1] >= 0.999 and last.winfo_rooty() >= tp.cv.winfo_rooty()
            and bottom <= tp.cv.winfo_rooty() + view_h + 1,
            (tp.cv.yview(), last.winfo_rooty(), bottom, tp.cv.winfo_rooty() + view_h))
        chk("  마지막 줄의 글자도 보인다", "「칭호 59」" in [
            c.cget("text") for w in last.winfo_children() for f in w.winfo_children()
            for c in f.winfo_children() if c.winfo_class() == "Label"],
            [c.cget("text") for w in last.winfo_children() for f in w.winfo_children()
             for c in f.winfo_children() if c.winfo_class() == "Label"][:3])
        dw.close()

    print("\n=== 같은 업적을 두 번 안 띄운다 ===")
    from poketdesktop import app as APP

    class Mini(object):
        announce_achievements = APP.App.announce_achievements
        _show_achievements = APP.App._show_achievements

        def __init__(self, root):
            self.root = root
            self.api = FakeApi()
            self._ach_queue, self._ach_known = [], set()
            self._ach_showing = False
            self._quitting = False
            self._gift_showing = False
            self.battle = self.arena = None
            self.shown = []
    m = Mini(root)
    real = UA.announce
    UA.announce = lambda parent, a, items: m.shown.append([x["key"] for x in items])
    try:
        items = [ach("dex_50", "50종", got=True), ach("dex_100", "100종", got=True)]
        m.announce_achievements(items)
        pump(root, lambda: "seen" in m.api.calls, timeout=5)
        m.announce_achievements(items)          # 다음 동기화에 또 실려 왔다
        root.update()
        chk("한 번만 띄운다", m.shown == [["dex_50", "dex_100"]], m.shown)
        chk("본 뒤 서버에 알린다", "seen" in m.api.calls, m.api.calls)
        m.battle = object()                     # 배틀 중이면 기다린다
        m.announce_achievements([ach("dex_200", "200종", got=True)])
        root.update()
        chk("배틀 중에는 기다린다", m.shown == [["dex_50", "dex_100"]], m.shown)
        m.battle = None
        pump(root, lambda: len(m.shown) == 2, timeout=5)
        chk("끝나면 띄운다", m.shown[-1:] == [["dex_200"]], m.shown)
    finally:
        UA.announce = real

    close_toplevels(root)
    root.destroy()
    print()
    print("합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
