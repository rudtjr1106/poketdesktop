# -*- coding: utf-8 -*-
"""마이페이지 화면 검사 (1.9.0).

    python client/test_mypage_ui.py
    python client/run_as_windows.py client/test_mypage_ui.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 - 가짜 api 가 /api/mypage 와 같은
모양으로 답한다.

  1. '설정' 탭 자리에 '마이페이지' 가 있다. 설정 탭은 없다.
  2. 내 정보(이름·칭호·티어·가입 며칠째), 모은 것(포켓몬·도감·관장…),
     칭호, 시즌 기록, 게시판 활동이 보인다.
  3. 칭호가 많아도 줄을 바꿔 다 보인다 (글자를 줄이지 않는다).
  4. 게시판 활동은 [알림 | 내 글 | 내 댓글] 탭으로 한 번에 한 종류, **한 쪽에
     다섯 줄**만 보인다. ◀ ▶ 로 넘긴다. 활동이 아무리 쌓여도 칸 높이가 같다.
     줄을 누르면 게시판의 그 글을 연다. **본 알림은 없어진다** - 알림 탭에는
     안 본 것만 있고, '모두 읽음' 으로 한꺼번에 치울 수 있다.
  5. 톱니바퀴를 누르면 설정 화면으로 바뀌고, '← 마이페이지' 로 돌아온다.
     설정 화면에는 '포켓몬 투명도' 손잡이가 있다.
  6. 길어지면 굴려서 보고, 눌린 위젯이 없다.
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-test-mypage-"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import config                             # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_hub, ui_mypage                  # noqa: E402
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


def payload(titles=3):
    own = [{"id": "t%d" % i, "name": "칭호 %d번 수집가" % i, "group": "도감", "how": "…"}
           for i in range(titles)]
    return {
        "user": {"id": 1, "name": "나여조경석", "createdAt": "2026-09-08T03:00:00+00:00",
                 "days": 25, "title": own[1]["name"] if titles > 1 else None,
                 "frameColor": "#ffd447", "tier": "super", "tierKr": "슈퍼볼", "admin": True,
                 "money": 48200},
        "counts": {"pokemon": 9, "shiny": 2, "topLevel": 70, "dexCaught": 192, "dexSeen": 241,
                   "dexTotal": 1025, "encounters": 500, "caught": 200, "friends": 2},
        "gym": {"cleared": 37, "total": 256, "wins": 67},
        "titles": {"owned": own, "count": len(own), "total": 60,
                   "equipped": own[1]["name"] if titles > 1 else None},
        "seasons": [
            {"season": 3, "current": True, "ranked": True, "placementLeft": 0, "rank": 2,
             "tier": "poke", "tierKr": "몬스터볼", "rp": 134, "peakRp": 150, "games": 23,
             "wins": 14, "losses": 9, "draws": 0, "title": None},
            {"season": 2, "current": False, "ranked": True, "rank": 4, "tier": "hyper",
             "tierKr": "하이퍼볼", "rp": 412, "rating": 1190, "games": 86, "wins": 52,
             "losses": 34, "draws": 0, "title": "시즌 2 챔피언"},
            {"season": 1, "current": False, "ranked": True, "rank": 2, "tier": None,
             "tierKr": None, "rp": None, "rating": 1265, "games": 60, "wins": 41, "losses": 19,
             "draws": 1, "title": None}],
        "raid": {"games": 5, "wins": 3, "damage": 12345},
        # 게시판 활동은 수와 **첫 쪽만** 온다 (안 본 알림이 있으면 알림 쪽부터)
        "board": dict(COUNTS, pageSize=5, first=mine_page("notify", 1)),
    }


# 서버의 board.mine_page 와 같은 모양. 내 글 12개, 내 댓글 1개, 알림 2개(본 알림은 서버가 지운다).
POSTS = [{"id": 100 + i, "postId": 100 + i, "kind": "qna" if i % 3 == 0 else "free",
          "kindKr": "Q&A" if i % 3 == 0 else "자유", "title": "내가 쓴 글 %02d" % i,
          "agoSec": 3600 * (13 - i), "comments": i % 4, "likes": i % 3}
         for i in range(12, 0, -1)]
COMMENTS = [{"id": 31, "postId": 21, "title": "남의 글", "snippet": "내가 단 댓글", "agoSec": 3600}]
NOTIFY = [{"id": 5, "kind": "reply", "actor": "웅이", "postId": 41, "title": "레이드 같이 하실 분",
           "snippet": "운영자님도 오시네요", "agoSec": 600, "seen": False},
          {"id": 4, "kind": "comment", "actor": "지우", "postId": 112, "title": "내가 쓴 글 12",
           "snippet": "새 댓글입니다", "agoSec": 6000, "seen": False}]
COUNTS = {"postCount": 12, "commentCount": 1, "likes": 7, "notifyCount": 2, "unseen": 2}


def mine_page(what, page, size=5, rows=None, counts=None):
    rows = rows if rows is not None else {"posts": POSTS, "comments": COMMENTS,
                                         "notify": NOTIFY}[what]
    pages = max(1, (len(rows) + size - 1) // size)
    page = max(1, min(pages, page))
    return {"what": what, "page": page, "pages": pages, "total": len(rows), "size": size,
            "items": rows[(page - 1) * size:page * size], "counts": dict(counts or COUNTS)}


class FakeApi(object):
    def __init__(self):
        self.calls = 0
        self.data = payload()
        self.fail = None

    def mypage(self):
        self.calls += 1
        if self.fail:
            raise RuntimeError(self.fail)
        return self.data

    def board_mine(self, what="posts", page=1):
        self.mine_calls = getattr(self, "mine_calls", []) + [(what, page)]
        if self.fail:
            raise RuntimeError(self.fail)
        # 알림은 이 가짜 서버가 들고 있는 목록에서 (글을 열거나 '모두 읽음' 하면 줄어든다)
        notify = getattr(self, "notify", None)
        counts = dict(getattr(self, "counts", None) or COUNTS)
        if notify is not None:
            counts.update({"notifyCount": len(notify), "unseen": len(notify)})
        rows = notify if (what == "notify" and notify is not None) else None
        return mine_page(what, page, rows=rows, counts=counts)

    def board_notify_seen(self):
        self.cleared = getattr(self, "cleared", 0) + 1
        self.notify = []
        return {"items": [], "unseen": 0}


class FakeApp(object):
    def __init__(self, root):
        self.root = root
        self.api = FakeApi()
        self.settings = dict(config.DEFAULTS)
        self.overlay = None
        self.wild = None
        self.hub = None
        self.mypage_window = None
        self.settings_win = None
        self.opened = []
        self.sized = []

    def open_board(self, post=None, kind=None):
        self.opened.append((post, kind))
        # 서버처럼: 그 글을 열면 그 글에 걸린 내 알림이 없어진다
        if post and getattr(self.api, "notify", None) is not None:
            self.api.notify = [x for x in self.api.notify if x["postId"] != post]

    def set_board_unseen(self, n):
        self.unseen_told = getattr(self, "unseen_told", []) + [n]

    def set_size(self, px):
        self.sized.append(px)

    def refresh_tray(self):
        pass

    def set_autostart(self, on):
        return True, ""

    def set_show_grass(self, on):
        self.settings["showGrass"] = bool(on)

    def screen_choices(self):
        return []

    def logout(self):
        self.account = getattr(self, "account", []) + ["logout"]

    def delete_account(self):
        self.account = getattr(self, "account", []) + ["delete"]


def wait(root, cond, sec=6.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.01)
    return cond()


def settle(root, sec=0.3):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def click(w):
    w.event_generate("<Button-1>", x=2, y=2)


def find(win, text):
    out = []

    def walk(w):
        for c in w.winfo_children():
            try:
                if "text" in c.keys() and str(c.cget("text")) == text:
                    out.append(c)
            except Exception:                               # noqa: BLE001
                pass
            walk(c)
    walk(win)
    return out


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    app = FakeApp(root)

    print("=== 탭 ===")
    keys = [t[0] for t in ui_hub.TABS]
    labels = [t[1] for t in ui_hub.TABS]
    chk("'마이페이지' 탭이 맨 끝에 있다", keys[-1] == "my" and labels[-1] == "마이페이지", keys)
    chk("'설정' 탭은 없다 (톱니바퀴 안으로 들어갔다)", "settings" not in keys and "설정" not in labels)
    chk("게시판 탭은 그대로", "board" in keys)

    print("\n=== 내 정보 ===")
    w = ui_mypage.MyPageWindow(app)
    top = w.win.winfo_toplevel()
    top.deiconify()
    wait(root, lambda: w.data is not None)
    settle(root)
    tx = texts(top)
    chk("서버에 한 번 묻는다", app.api.calls == 1, app.api.calls)
    chk("이름·운영자·티어·칭호", all(x in tx for x in ("나여조경석", "운영자", "슈퍼볼")), tx[:12])
    chk("가입한 지 며칠째와 가입일", any("함께한 지 25일째" in x and "2026.09.08 가입" in x
                                 and "48,200원" in x for x in tx), [x for x in tx if "함께" in x])
    for name, value in (("포켓몬", "9마리"), ("색이 다른 포켓몬", "2마리"), ("도감", "192 / 1025"),
                        ("이긴 관장", "37 / 256"), ("레이드", "3승"), ("친구", "2명")):
        chk("  %s %s" % (name, value), name in tx and value in tx)
    chk("덧붙임: 가장 높은 레벨·본 종·이긴 횟수·참가",
        all(x in tx for x in ("가장 높은 레벨 70", "본 종 241", "모두 67번 승리", "5판 참가")))

    print("\n=== 칭호 ===")
    chk("가진 수 / 전체", "3 / 60" in tx)
    chips = [find(top, "칭호 %d번 수집가" % i) for i in range(3)]
    chk("가진 칭호가 다 보인다", all(len(c) >= 1 for c in chips))
    on = [c for c in find(top, "칭호 1번 수집가") if c.cget("bg") == U.ACCENT]
    chk("달고 있는 칭호는 금색", len(on) == 1)

    print("\n=== 시즌 기록 ===")
    chk("지금 시즌", ui_mypage.season_line(app.api.data["seasons"][0])
        == ("시즌 3 (진행 중)", "2위 · 몬스터볼 · RP 134 · 23전 14승 9패"),
        ui_mypage.season_line(app.api.data["seasons"][0]))
    chk("시즌 2: 받은 칭호까지", ui_mypage.season_line(app.api.data["seasons"][1])
        == ("시즌 2", "4위 · 하이퍼볼 · RP 412 · 86전 52승 34패 · 칭호 '시즌 2 챔피언'"))
    chk("시즌 1: RP 가 없던 시즌은 점수로, 무승부도 적는다",
        ui_mypage.season_line(app.api.data["seasons"][2])
        == ("시즌 1", "2위 · 점수 1265 · 60전 41승 19패 1무"),
        ui_mypage.season_line(app.api.data["seasons"][2]))
    chk("배치 전", ui_mypage.season_line({"season": 3, "current": True, "ranked": False, "games": 0})
        == ("시즌 3 (진행 중)", "아직 랭크 배틀을 하지 않았습니다."))
    chk("배치 중", "2판 더" in ui_mypage.season_line(
        {"season": 3, "current": True, "ranked": False, "games": 3, "wins": 2, "losses": 1,
         "placementLeft": 2})[1])
    chk("화면에 세 시즌이 다 있다", all(x in tx for x in ("시즌 3 (진행 중)", "시즌 2", "시즌 1")))

    print("\n=== 게시판 활동 ===")
    chk("받은 좋아요", "받은 좋아요 7" in tx, [x for x in tx if "받은" in x])
    chk("탭 셋에 수가 적혀 있다", [w.b_seg.cells[k].cget("text") for k in ui_mypage.TABS]
        == ["알림 2", "내 글 12", "내 댓글 1"], [w.b_seg.cells[k].cget("text") for k in ui_mypage.TABS])
    chk("안 본 알림이 있으면 알림 탭부터 (서버를 따로 부르지 않는다)", w.b_what == "notify"
        and w.b_seg.current == "notify" and not getattr(app.api, "mine_calls", []))
    rows = [c for c in w.b_list.winfo_children()]
    chk("안 본 알림이 줄로 보인다", len(rows) == 2 and "웅이 님의 답글" in tx and "지우 님의 댓글" in tx,
        [x for x in tx if "님의" in x])
    chk("한 쪽뿐이면 넘길 수 없다", w.b_lbl.cget("text") == "1 / 1" and not w.b_prev.enabled
        and not w.b_next.enabled, w.b_lbl.cget("text"))
    chk("알림이 있으면 '모두 읽음' 이 보인다", w.b_clear.holder.winfo_ismapped() == 1)
    app.api.notify = [dict(x) for x in NOTIFY]
    old = ui_mypage.RELOAD_MS
    ui_mypage.RELOAD_MS = 60
    click(find(top, "웅이 님의 답글")[0])
    chk("알림을 누르면 그 글을 연다", app.opened == [(41, None)], app.opened)
    wait(root, lambda: getattr(app.api, "mine_calls", []) == [("notify", 1)]
         and "웅이 님의 답글" not in texts(top))
    settle(root)
    ui_mypage.RELOAD_MS = old
    tx = texts(top)
    chk("**본 알림은 없어진다** (글을 열고 나면 그 줄이 사라진다)", "웅이 님의 답글" not in tx
        and "지우 님의 댓글" in tx and len(w.b_list.winfo_children()) == 1, [x for x in tx if "님의" in x])
    chk("탭의 수도 준다", w.b_seg.cells["notify"].cget("text") == "알림 1",
        w.b_seg.cells["notify"].cget("text"))
    chk("게시판 탭의 점·트레이의 수를 바로 맞춘다", getattr(app, "unseen_told", [])[-1:] == [1],
        getattr(app, "unseen_told", None))
    w.clear_notify()
    wait(root, lambda: getattr(app.api, "cleared", 0) == 1 and "지우 님의 댓글" not in texts(top))
    settle(root)
    tx = texts(top)
    chk("'모두 읽음' 을 누르면 알림이 다 사라진다", w.b_list.winfo_children().__len__() == 1
        and any("새 알림이 없습니다" in x for x in tx)
        and w.b_seg.cells["notify"].cget("text") == "알림", [x for x in tx if "알림" in x])
    chk("알림이 없으면 '모두 읽음' 도 없다", w.b_clear.holder.winfo_ismapped() == 0)
    chk("트레이의 수도 0 으로", app.unseen_told[-1] == 0, app.unseen_told)
    app.api.mine_calls = []

    click(w.b_seg.cells["posts"])
    wait(root, lambda: w.b_what == "posts" and len(w.b_list.winfo_children()) == 5)
    settle(root)
    tx = texts(top)
    chk("'내 글' 을 누르면 그 종류의 첫 쪽을 받는다", app.api.mine_calls == [("posts", 1)],
        app.api.mine_calls)
    chk("**한 쪽에 다섯 줄만** 그린다 (12개여도)", len(w.b_list.winfo_children()) == 5
        and "내가 쓴 글 12" in tx and "내가 쓴 글 08" in tx and "내가 쓴 글 07" not in tx,
        [x for x in tx if x.startswith("내가 쓴 글")])
    chk("쪽 표시와 넘기기", w.b_lbl.cget("text") == "1 / 3" and not w.b_prev.enabled and w.b_next.enabled,
        w.b_lbl.cget("text"))
    chk("글마다 좋아요·댓글 수", any(x.startswith("좋아요 2 · 댓글 3") for x in tx),
        [x for x in tx if "좋아요" in x])
    chk("알림 줄은 치워졌다", "웅이 님의 답글" not in tx)
    h1 = w.b_list.winfo_parent() and w.b_strut.winfo_height()
    box_h = w.b_list.master.winfo_height()
    w.turn(1)
    wait(root, lambda: w.b_page == 2 and "내가 쓴 글 07" in texts(top))
    settle(root)
    chk("▶ 로 다음 쪽", app.api.mine_calls[-1] == ("posts", 2) and w.b_lbl.cget("text") == "2 / 3"
        and w.b_prev.enabled and w.b_next.enabled and "내가 쓴 글 12" not in texts(top))
    w.turn(1)
    wait(root, lambda: w.b_page == 3 and "내가 쓴 글 01" in texts(top))
    settle(root)
    chk("마지막 쪽에는 남은 두 줄", len(w.b_list.winfo_children()) == 2 and not w.b_next.enabled
        and w.b_lbl.cget("text") == "3 / 3", len(w.b_list.winfo_children()))
    chk("줄 수가 줄어도 칸 높이는 그대로 (출렁이지 않는다)", w.b_list.master.winfo_height() == box_h,
        (box_h, w.b_list.master.winfo_height()))
    n = len(app.api.mine_calls)
    w.turn(1)
    settle(root, 0.1)
    chk("끝에서 더 넘기면 아무 일도 없다", len(app.api.mine_calls) == n and w.b_page == 3)
    click(find(top, "내가 쓴 글 02")[0])
    chk("글을 누르면 게시판의 그 글을 연다", app.opened[-1] == (102, None), app.opened)
    w.turn(-1)
    wait(root, lambda: w.b_page == 2)

    click(w.b_seg.cells["comments"])
    wait(root, lambda: w.b_what == "comments" and "내가 단 댓글" in texts(top))
    settle(root)
    tx = texts(top)
    chk("'내 댓글' 은 첫 쪽부터", app.api.mine_calls[-1] == ("comments", 1) and w.b_page == 1
        and w.b_lbl.cget("text") == "1 / 1")
    chk("내 댓글과 어느 글인지", "내가 단 댓글" in tx and any(x.startswith("남의 글") for x in tx))
    click(find(top, "내가 단 댓글")[0])
    chk("댓글을 누르면 그 댓글이 달린 글을 연다", app.opened[-1] == (21, None), app.opened)

    app.api.notify = [dict(NOTIFY[0])]                # 그사이 새 알림이 하나 왔다
    click(w.b_seg.cells["notify"])
    wait(root, lambda: w.b_what == "notify" and "웅이 님의 답글" in texts(top))
    settle(root)
    chk("서버가 준 수로 탭 이름을 고친다", w.b_seg.cells["notify"].cget("text") == "알림 1"
        and w.b_clear.holder.winfo_ismapped() == 1, w.b_seg.cells["notify"].cget("text"))
    app.api.notify = None

    print("\n=== 굴리기·눌림 ===")
    chk("길면 굴려서 본다", w.cv.yview()[1] < 0.999, w.cv.yview())
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])

    print("\n=== 빈 활동 ===")
    empty = payload()
    zero = {"postCount": 0, "commentCount": 0, "likes": 0, "notifyCount": 0, "unseen": 0}
    empty["board"] = dict(zero, pageSize=5, first=mine_page("posts", 1, rows=[], counts=zero))
    app.api.data = empty
    before = app.api.calls
    w.load()
    wait(root, lambda: app.api.calls == before + 1 and w.b_what == "posts"
         and w.b_seg.cells["posts"].cget("text") == "내 글 0")
    settle(root)
    chk("아무것도 없으면 내 글 탭에 안내 한 줄", "아직 쓴 글이 없습니다." in texts(top)
        and w.b_lbl.cget("text") == "1 / 1" and w.b_seg.cells["notify"].cget("text") == "알림",
        [x for x in texts(top) if "아직" in x])

    print("\n=== 칭호가 많을 때 ===")
    app.api.data = payload(titles=40)
    w.load()
    wait(root, lambda: (w.data or {}).get("titles", {}).get("count") == 40)
    settle(root, 0.5)
    flow = w.flows[0]
    ys = sorted(set(c.winfo_y() for c in flow.items))
    chk("줄을 바꿔 가며 다 놓는다", len(ys) >= 3 and len(flow.items) == 40, (len(ys), len(flow.items)))
    width = flow.frame.winfo_width()
    chk("칸 밖으로 나간 칭호가 없다", all(c.winfo_x() + c.winfo_width() <= width for c in flow.items),
        [(c.winfo_x(), c.winfo_width()) for c in flow.items if c.winfo_x() + c.winfo_width() > width][:3])
    last = max(c.winfo_y() + c.winfo_height() for c in flow.items)
    chk("칸 높이가 줄 수만큼 늘어난다 (잘리지 않는다)", flow.frame.winfo_height() >= last,
        (flow.frame.winfo_height(), last))
    chk("글자 크기는 그대로다", all(str(c.cget("font")) == str(flow.items[0].cget("font"))
                             for c in flow.items))
    w.cv.yview_moveto(1.0)
    settle(root, 0.1)
    chk("맨 아래까지 굴려진다", w.cv.yview()[1] >= 0.999, w.cv.yview())
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])

    print("\n=== 새로고침·실패 ===")
    app.api.fail = "서버에 연결할 수 없습니다."
    w.load()
    wait(root, lambda: "연결할 수 없습니다" in w.status._label.cget("text"))
    chk("실패하면 아래 줄에 적고 보던 화면은 그대로", "연결할 수 없습니다" in w.status._label.cget("text")
        and "나여조경석" in texts(top))
    app.api.fail = None

    print("\n=== 계정 (1.9.2: 트레이 메뉴에서 옮겨 왔다) ===")
    tx = texts(top)
    chk("맨 아래에 '계정' 칸", "계정" in tx and tx.index("계정") > tx.index("시즌 기록"), tx[-12:])
    chk("로그아웃·회원탈퇴 단추가 있다",
        sorted(w.account_btns) == ["로그아웃", "회원탈퇴"]
        and all(b.holder.winfo_ismapped() for b in w.account_btns.values()),
        sorted(w.account_btns))
    chk("무슨 일이 일어나는지 적혀 있다",
        any("로그인 화면으로 돌아갑니다" in x for x in tx)
        and any("되돌릴 수 없습니다" in x for x in tx))
    w.account_btns["로그아웃"]._release(None)
    chk("로그아웃 단추는 앱의 로그아웃을 부른다", getattr(app, "account", []) == ["logout"],
        getattr(app, "account", []))
    w.account_btns["회원탈퇴"]._release(None)
    chk("회원탈퇴 단추는 앱의 탈퇴를 부른다 (확인·비밀번호는 거기서 묻는다)",
        app.account == ["logout", "delete"], app.account)
    from poketdesktop import tray as TRAY
    menu = [it for it in TRAY.TrayBase(app).spec() if it is not TRAY.SEP]
    names = [it.text for it in menu if not callable(it.text)]
    chk("트레이 메뉴에는 로그아웃·회원탈퇴가 없다",
        "로그아웃" not in names and "회원탈퇴" not in names and "종료" in names, names)
    chk("'종료' 바로 위는 설정이다", names[names.index("종료") - 1] == "설정",
        names[-4:])
    bad = squeezed(top)
    chk("눌린 위젯 없음 (계정 칸까지)", not bad, bad[:3])

    print("\n=== 톱니바퀴 = 설정 ===")
    chk("머리줄에 톱니바퀴와 '설정' 글자", w.gear.winfo_ismapped() == 1 and "설정" in texts(top))
    click(w.gear)
    settle(root, 0.4)
    tx = texts(top)
    chk("설정 화면으로 바뀐다", w.view == "settings" and w.settings is not None
        and "포켓몬 크기" in tx and "걷는 속도" in tx, tx[:8])
    chk("머리줄 제목이 '설정' 한 번만", w.title.cget("text") == "설정" and tx.count("설정") == 2,
        tx.count("설정"))                 # 제목 + 톱니바퀴 옆 글자
    chk("'포켓몬 투명도' 손잡이가 있다 (1.9.0)", "포켓몬 투명도" in tx and "0%" in tx)
    chk("알림 스위치에 게시판이 적혀 있다", any("게시판 댓글 알림" in x for x in tx))
    chk("마이페이지 내용은 숨는다", w.page.winfo_ismapped() == 0)
    chk("'← 마이페이지' 가 보인다", w.back_btn.holder.winfo_ismapped() == 1)
    chk("앱이 설정 화면을 찾을 수 있다 (트레이에서 바꿨을 때 표시를 맞춘다)",
        app.settings_win is w.settings)
    w.settings._set_alpha(45)
    chk("투명도를 바꾸면 저장된다", app.settings["petOpacity"] == 55
        and config.load_settings().get("petOpacity") == 55, app.settings["petOpacity"])
    w.settings._set_alpha(99)
    chk("투명도는 99% 까지 올릴 수 있다", app.settings["petOpacity"] == 1
        and abs(config.pet_alpha(app.settings) - 0.01) < 1e-9, app.settings["petOpacity"])
    w.settings._set_alpha(100)
    chk("100% (아예 안 보임)는 안 된다", app.settings["petOpacity"] == 1)
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])
    w.show_page()
    settle(root, 0.3)
    chk("돌아오면 마이페이지가 그대로", w.view == "page" and w.page.winfo_ismapped() == 1
        and w.title.cget("text") == "마이페이지" and "나여조경석" in texts(top))
    calls = app.api.calls
    w.show_settings()
    settle(root, 0.2)
    chk("다시 열어도 설정 화면을 새로 만들지 않는다", w.settings is app.settings_win
        and app.api.calls == calls)
    w.toggle_settings()
    settle(root, 0.2)
    chk("톱니바퀴를 다시 누르면 돌아온다", w.view == "page")

    w.close()
    chk("닫으면 설정 화면도 치운다", w.settings is None and app.settings_win is None)
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
