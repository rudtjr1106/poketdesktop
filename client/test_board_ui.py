# -*- coding: utf-8 -*-
"""게시판 화면 검사 (1.8.0).

    python client/test_board_ui.py
    python client/run_as_windows.py client/test_board_ui.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 - 가짜 api 가 server/app/board.py 와
같은 모양으로 답한다 (권한·답글 한 단계·지운 댓글의 자리까지).

## 무엇을 못 박나

  1. 목록: 공지가 맨 위, 줄마다 **누가 썼는지**(이름·운영자 표시·칭호)와 댓글 수.
  2. [전체 | 공지 | 자유] 로 거르고, 쪽을 넘긴다.
  3. 글: 내용, 댓글, 들여 쓴 답글. 지운 댓글은 자리만 남는다.
  4. **댓글이 많아도 입력칸과 단추가 창 안에 보이고**, 목록은 굴린다.
  5. 답글: 누르면 누구에게 다는지 알려 주고, 그 댓글 번호와 함께 보낸다.
  6. 쓰기: 공지 고르기는 운영자에게만 보인다. 빈 제목·내용은 안 보낸다.
  7. 내 글만 수정·삭제 단추가 보인다. 서버가 거절하면 그 말을 적는다.
  8. 목록을 보면 '새 공지' 표시를 끈다.
  9. 긴 글(2000자)도 굴려서 보고, 눌린 위젯이 없다.
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-test-board-"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_board, ui_box                   # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop.api import ApiError                       # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0
ADMIN = "나여조경석"


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class FakeApi(object):
    """server/app/board.py 와 같은 모양. 한 사람(me)의 눈으로 답한다."""
    PAGE = 15

    def __init__(self, me, uid):
        self.me, self.uid = me, uid
        self.posts = []          # {id, kind, uid, author, title, body, ago}
        self.comments = []       # {id, post, parent, uid, author, body, deleted}
        self.titles = {}         # 이름 -> 칭호
        self.calls = []
        self.fail = None
        self._id = 0

    def _next(self):
        self._id += 1
        return self._id

    def seed_post(self, kind, author, uid, title, body="내용", ago=60):
        p = {"id": self._next(), "kind": kind, "uid": uid, "author": author,
             "title": title, "body": body, "ago": ago, "edited": False}
        self.posts.append(p)
        return p["id"]

    def seed_comment(self, pid, author, uid, body, parent=None, deleted=False):
        c = {"id": self._next(), "post": pid, "parent": parent, "uid": uid,
             "author": author, "body": body, "deleted": deleted}
        self.comments.append(c)
        return c["id"]

    def _who(self, x):
        return {"author": x["author"], "authorId": x["uid"],
                "authorAdmin": x["author"] == ADMIN,
                "authorTitle": self.titles.get(x["author"]), "authorColor": None}

    def _row(self, p):
        admin = self.me == ADMIN
        out = {"id": p["id"], "kind": p["kind"],
               "kindKr": {"notice": "공지", "free": "자유"}[p["kind"]],
               "title": p["title"], "agoSec": p["ago"], "edited": p["edited"],
               "comments": len([c for c in self.comments
                                if c["post"] == p["id"] and not c["deleted"]]),
               "mine": p["uid"] == self.uid,
               "canDelete": p["uid"] == self.uid or admin,
               "canEdit": p["uid"] == self.uid}
        out.update(self._who(p))
        return out

    def board(self, kind="all", page=1):
        self.calls.append(("list", kind, page))
        want = "free" if kind == "all" else kind
        rows = sorted([p for p in self.posts if p["kind"] == want], key=lambda p: -p["id"])
        pages = max(1, (len(rows) + self.PAGE - 1) // self.PAGE)
        page = max(1, min(pages, page))
        pinned = []
        if kind == "all":
            pinned = sorted([p for p in self.posts if p["kind"] == "notice"],
                            key=lambda p: -p["id"])[:3]
        return {"kind": kind, "page": page, "pages": pages, "total": len(rows),
                "pinned": [self._row(p) for p in pinned],
                "posts": [self._row(p) for p in rows[(page - 1) * self.PAGE:page * self.PAGE]],
                "canNotice": self.me == ADMIN,
                "limits": {"title": 40, "body": 2000, "comment": 300}}

    def board_post(self, pid):
        self.calls.append(("post", pid))
        p = next((x for x in self.posts if x["id"] == pid), None)
        if p is None:
            raise ApiError("없는 글이거나 지워진 글입니다.", 404)
        out = self._row(p)
        out["body"] = p["body"]
        admin = self.me == ADMIN

        def one(c):
            o = {"id": c["id"], "agoSec": 30, "deleted": c["deleted"],
                 "body": "" if c["deleted"] else c["body"],
                 "mine": c["uid"] == self.uid and not c["deleted"],
                 "canDelete": (c["uid"] == self.uid or admin) and not c["deleted"]}
            o.update(self._who(c))
            if c["deleted"]:
                o.update({"author": "", "authorAdmin": False, "authorTitle": None})
            return o
        tops = []
        for c in self.comments:
            if c["post"] == pid and c["parent"] is None:
                item = one(c)
                item["replies"] = [one(r) for r in self.comments
                                   if r["parent"] == c["id"] and not r["deleted"]]
                if not c["deleted"] or item["replies"]:
                    tops.append(item)
        out["commentList"] = tops
        out["canComment"] = True
        return out

    def board_write(self, kind, title, body):
        self.calls.append(("write", kind, title, body))
        if self.fail:
            raise ApiError(self.fail, 403)
        if kind == "notice" and self.me != ADMIN:
            raise ApiError("공지는 운영자만 쓸 수 있습니다.", 403)
        return self.board_post(self.seed_post(kind, self.me, self.uid, title, body, ago=0))

    def board_edit(self, pid, title, body):
        self.calls.append(("edit", pid, title, body))
        p = next(x for x in self.posts if x["id"] == pid)
        p.update({"title": title, "body": body, "edited": True})
        return self.board_post(pid)

    def board_delete(self, pid):
        self.calls.append(("delete", pid))
        self.posts = [p for p in self.posts if p["id"] != pid]
        return {"ok": True}

    def board_comment(self, pid, body, parent=0):
        self.calls.append(("comment", pid, body, parent))
        if self.fail:
            raise ApiError(self.fail, 403)
        par = next((c for c in self.comments if c["id"] == parent), None)
        top = (par["parent"] or par["id"]) if par else None
        self.seed_comment(pid, self.me, self.uid, body, parent=top)
        return self.board_post(pid)

    def board_comment_delete(self, cid):
        self.calls.append(("comment_delete", cid))
        c = next(x for x in self.comments if x["id"] == cid)
        c["deleted"] = True
        return self.board_post(c["post"])


class FakeApp(object):
    def __init__(self, root, api):
        self.root = root
        self.api = api
        self.settings = {}
        self.board_window = None
        self.seen = []

    def mark_notice_seen(self, n):
        self.seen.append(n)


def wait(root, cond, sec=6.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.01)
    return cond()


def settle(root, sec=0.25):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def inside(w, top):
    """위젯이 창 안에 온전히 보이나."""
    w.update_idletasks()
    return (w.winfo_ismapped() and w.winfo_rooty() >= top.winfo_rooty()
            and w.winfo_rooty() + w.winfo_height() <= top.winfo_rooty() + top.winfo_height()
            and w.winfo_height() >= w.winfo_reqheight())


def seed(api):
    n1 = api.seed_post("notice", ADMIN, 1, "시즌 3 안내", "메가진화가 열렸습니다.")
    for i in range(20):
        api.seed_post("free", "이슬" if i % 2 else "지우", 3 if i % 2 else 2,
                      "자유 글 %02d" % i)
    n2 = api.seed_post("notice", ADMIN, 1, "점검 안내")
    talk = api.seed_post("free", "지우", 2, "레이드 같이 하실 분",
                         "오늘 21시 레이드 같이 가요.\n\n코드는 댓글로 남길게요.")
    c1 = api.seed_comment(talk, "이슬", 3, "저요!")
    api.seed_comment(talk, "지우", 2, "코드 AB12CD 입니다", parent=c1)
    api.seed_comment(talk, ADMIN, 1, "즐거운 레이드 되세요", parent=c1)
    c2 = api.seed_comment(talk, "웅", 4, "지운 댓글", deleted=True)
    api.seed_comment(talk, "이슬", 3, "지운 댓글에 단 답글", parent=c2)
    api.seed_comment(talk, "웅", 4, "답글 없는 지운 댓글", deleted=True)
    api.titles["이슬"] = "시즌 2 마스터볼"
    return n1, n2, talk, c1


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-400:])
    root.report_callback_exception = on_err
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)" % (U.FAMILY, U.FONT[1], U.BASE_PT))
    real_confirm = ui_box.confirm
    ui_box.confirm = lambda *a, **kw: True

    # ---------------------------------------------------------- 보통 유저
    api = FakeApi("지우", 2)
    n1, n2, talk, c1 = seed(api)
    app = FakeApp(root, api)
    w = ui_board.BoardWindow(app)
    top = w.win

    print("=== 목록 ===")
    chk("목록을 받아 온다", wait(root, lambda: w.data is not None), api.calls)
    settle(root)
    t = texts(top)
    chk("공지 둘이 맨 위 (최신부터)", t.index("점검 안내") < t.index("시즌 3 안내")
        < t.index("레이드 같이 하실 분"), [x for x in t if "안내" in x or "레이드" in x])
    chk("누가 썼는지: 이름", "지우" in t and "이슬" in t and ADMIN in t)
    chk("  운영자 표시", "운영자" in t)
    chk("  칭호", "시즌 2 마스터볼" in t)
    chk("댓글 수 (지운 것은 빼고 답글은 넣는다)", "댓글 4" in t,
        [x for x in t if x.startswith("댓글")])
    chk("쪽: 1 / 2", w.page_lbl.cget("text") == "1 / 2", w.page_lbl.cget("text"))
    chk("새 공지를 봤다고 알린다 (가장 최근 공지 번호)", app.seen and app.seen[-1] == n2, app.seen)
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])
    first, last = w.cv.yview()
    chk("목록이 길면 굴린다", last - first < 0.999, (first, last))

    print("\n=== 거르기·쪽 넘기기 ===")
    w.pick_kind("notice")
    wait(root, lambda: w.data.get("kind") == "notice")
    settle(root)
    t = texts(top)
    chk("공지만", "시즌 3 안내" in t and "레이드 같이 하실 분" not in t, t[:14])
    w.pick_kind("free")
    wait(root, lambda: w.data.get("kind") == "free")
    w.turn(1)
    wait(root, lambda: w.data.get("page") == 2)
    settle(root)
    chk("자유 둘째 쪽", w.page_lbl.cget("text") == "2 / 2" and "자유 글 00" in texts(top),
        w.page_lbl.cget("text"))
    chk("  마지막 쪽에서는 ▶ 가 꺼진다", not w.next_btn.enabled and w.prev_btn.enabled)
    w.pick_kind("all")
    wait(root, lambda: w.data.get("kind") == "all")

    print("\n=== 글과 댓글 ===")
    w.open_post(talk)
    chk("글을 연다", wait(root, lambda: w.post is not None and w.view == "post"))
    settle(root)
    t = texts(top)
    chk("제목·내용", "레이드 같이 하실 분" in t and any("코드는 댓글로" in x for x in t), t[:10])
    chk("댓글과 답글", "저요!" in t and "코드 AB12CD 입니다" in t and "즐거운 레이드 되세요" in t)
    chk("지운 댓글은 자리만 (답글이 있을 때)", "삭제된 댓글입니다." in t
        and "지운 댓글에 단 답글" in t and "지운 댓글" not in t)
    chk("답글 없는 지운 댓글은 안 보인다", "답글 없는 지운 댓글" not in t
        and t.count("삭제된 댓글입니다.") == 1, t.count("삭제된 댓글입니다."))
    chk("내 글이라 수정·삭제 단추", "수정" in t and "삭제" in t)
    chk("입력칸과 등록 단추가 창 안에", inside(w.input, top) and inside(w.send_btn.holder, top))
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])

    print("\n=== 답글 ===")
    c = w.post["commentList"][0]
    w.set_reply(c)
    settle(root, 0.1)
    chk("누구에게 다는지 알려 준다", "이슬 님의 댓글에 답글을 답니다" in texts(top), texts(top)[-8:])
    chk("  단추가 '답글 등록'", w.send_btn.label.cget("text") == "답글 등록")
    w.input.insert("1.0", "저도 갑니다")
    w.send_comment()
    chk("그 댓글 번호와 함께 보낸다",
        wait(root, lambda: ("comment", talk, "저도 갑니다", c1) in api.calls), api.calls[-2:])
    settle(root)
    reps = w.post["commentList"][0]["replies"]
    chk("답글이 그 댓글 아래에 붙는다", reps[-1]["body"] == "저도 갑니다" and len(reps) == 3)
    chk("입력칸이 비고 답글 표시가 풀린다", w.input.get("1.0", "end-1c") == ""
        and w.reply_to is None and w.send_btn.label.cget("text") == "댓글 등록")
    w.set_reply(w.post["commentList"][0])
    w.set_reply(None)
    chk("답글 취소", w.reply_to is None and not w.reply_bar.winfo_manager())

    print("\n=== 댓글 ===")
    w.send_comment()
    chk("빈 댓글은 안 보낸다", "댓글을 적어 주세요" in w.status._label.cget("text"),
        w.status._label.cget("text"))
    w.input.insert("1.0", "새 댓글")
    api.fail = "댓글은 5초에 하나씩 쓸 수 있습니다."
    w.send_comment()
    wait(root, lambda: "5초" in w.status._label.cget("text"))
    chk("서버가 거절하면 그 말을 적고 글은 남긴다", "5초" in w.status._label.cget("text")
        and w.input.get("1.0", "end-1c") == "새 댓글" and w.send_btn.enabled,
        w.status._label.cget("text"))
    api.fail = None
    w.send_comment()
    wait(root, lambda: any(c[0] == "comment" and c[2] == "새 댓글" and c[3] == 0
                           for c in api.calls))
    settle(root)
    chk("댓글이 달리고 맨 아래로 굴러간다", w.post["commentList"][-1]["body"] == "새 댓글"
        and w.cv.yview()[1] >= 0.99, w.cv.yview())
    mine = w.post["commentList"][-1]
    w.delete_comment(mine["id"])
    wait(root, lambda: ("comment_delete", mine["id"]) in api.calls)
    settle(root)
    chk("내 댓글을 지운다", "새 댓글" not in texts(top))

    print("\n=== 댓글이 많을 때 ===")
    for i in range(40):
        api.seed_comment(talk, "이슬", 3, "댓글 %02d - 길게 적은 댓글입니다. " % i * 3)
    w.open_post(talk)
    wait(root, lambda: w.post is not None and len(w.post["commentList"]) > 40)
    settle(root)
    chk("댓글 칸은 굴린다", w.cv.yview()[1] - w.cv.yview()[0] < 0.5, w.cv.yview())
    chk("입력칸과 등록 단추는 그대로 창 안에", inside(w.input, top) and inside(w.send_btn.holder, top))
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])

    print("\n=== 쓰기 (보통 유저) ===")
    w.show_list()
    wait(root, lambda: w.view == "list")
    w.show_write()
    settle(root, 0.15)
    t = texts(top)
    chk("공지 고르기가 안 보인다", "공지는 운영자만 쓸 수 있습니다." not in t and "종류" not in t, t[:12])
    w.submit_post()
    chk("빈 제목은 안 보낸다", "제목을 적어 주세요" in w.status._label.cget("text")
        and not any(c[0] == "write" for c in api.calls))
    w.title_var.set("가" * 45)
    settle(root, 0.1)
    chk("제목 글자 수 (넘으면 빨강)", w.title_count.cget("text") == "45 / 40"
        and w.title_count.cget("fg") == U.DANGER, w.title_count.cget("text"))
    w.title_var.set("오늘의 자랑")
    w.text.insert("1.0", "이로치 잡았어요!\n" + "가나다라마바사 " * 240)
    w._count_post()
    settle(root, 0.15)
    bad = squeezed(top)
    chk("긴 글을 쓰는 중에도 눌린 위젯 없음 · 등록 단추가 창 안에",
        not bad and inside(w.post_btn.holder, top), bad[:3])
    w.submit_post()
    chk("자유 글로 보낸다", wait(root, lambda: any(c[0] == "write" and c[1] == "free"
                                             and c[2] == "오늘의 자랑" for c in api.calls)))
    wait(root, lambda: w.view == "post" and w.post and w.post["title"] == "오늘의 자랑")
    settle(root)
    chk("올린 글이 바로 열린다", "오늘의 자랑" in texts(top) and "글을 올렸습니다" in w.status._label.cget("text"))
    chk("긴 글은 굴려서 본다", w.cv.yview()[1] < 0.999, w.cv.yview())
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])
    new_id = w.post["id"]

    print("\n=== 수정·삭제 ===")
    w.show_edit()
    settle(root, 0.15)
    chk("고칠 때는 제목·내용이 채워져 있다", w.title_var.get() == "오늘의 자랑"
        and w.text.get("1.0", "end-1c").startswith("이로치 잡았어요!"))
    w.title_var.set("오늘의 자랑 (수정)")
    w.submit_post()
    wait(root, lambda: any(c[0] == "edit" and c[1] == new_id for c in api.calls))
    wait(root, lambda: w.view == "post")
    settle(root)
    chk("고친 글", "오늘의 자랑 (수정)" in texts(top) and any("고침" in x for x in texts(top)))
    w.delete_post()
    wait(root, lambda: ("delete", new_id) in api.calls and w.view == "list")
    wait(root, lambda: w.data is not None)
    settle(root)
    chk("지우면 목록으로 돌아가고 글이 없다", "오늘의 자랑 (수정)" not in texts(top))
    other = next(p["id"] for p in api.posts if p["author"] == "이슬")
    w.open_post(other)
    wait(root, lambda: w.post is not None and w.post["id"] == other)
    settle(root)
    chk("남의 글에는 수정·삭제 단추가 없다", "수정" not in texts(top) and "삭제" not in texts(top),
        [x for x in texts(top) if x in ("수정", "삭제")])
    w.close()
    settle(root, 0.2)

    # ---------------------------------------------------------- 운영자
    print("\n=== 운영자 ===")
    api2 = FakeApi(ADMIN, 1)
    seed(api2)
    app2 = FakeApp(root, api2)
    w2 = ui_board.BoardWindow(app2)
    wait(root, lambda: w2.data is not None)
    w2.show_write()
    settle(root, 0.15)
    t = texts(w2.win)
    chk("운영자에게는 공지 고르기가 보인다", "종류" in t and "공지" in t, t[:12])
    w2._pick_post_kind("notice")
    w2.title_var.set("새 공지")
    w2.text.insert("1.0", "공지 내용")
    w2.submit_post()
    chk("공지로 보낸다", wait(root, lambda: any(c[0] == "write" and c[1] == "notice"
                                            for c in api2.calls)), api2.calls[-2:])
    wait(root, lambda: w2.view == "post" and w2.post and w2.post["title"] == "새 공지")
    settle(root)
    chk("올린 공지에 운영자 표시", "운영자" in texts(w2.win) and "공지" in texts(w2.win))
    other = next(p["id"] for p in api2.posts if p["author"] == "이슬")
    w2.open_post(other)
    wait(root, lambda: w2.post is not None and w2.post["id"] == other)
    settle(root)
    chk("운영자는 남의 글도 지울 수 있다 (수정은 못 한다)",
        "삭제" in texts(w2.win) and "수정" not in texts(w2.win))
    bad = squeezed(w2.win)
    chk("눌린 위젯 없음", not bad, bad[:3])
    w2.close()

    ui_box.confirm = real_confirm
    settle(root, 0.3)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
