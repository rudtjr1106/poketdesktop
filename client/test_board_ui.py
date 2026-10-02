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
 10. (1.9.0) 좋아요: 목록에 수가 보이고, 글에서 누르면 켜지고 다시 누르면 꺼진다.
     누른 뒤에 글을 다시 그리지 않는다 (읽던 자리가 안 튄다).
 11. (1.9.0) 찾기: 말을 넣으면 그 말이 든 글만. '전체 보기' 로 돌아온다.
 12. (1.9.0) 패치노트 칸: 서버가 올린 글. 본문의 주소를 누를 수 있고, 수정·삭제는 없다.
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
        self.likes = {}          # 글 번호 -> 누른 사람들 (1.9.0)

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
        patch = p["kind"] == "patch"
        who = self.likes.get(p["id"], set())
        out = {"id": p["id"], "kind": p["kind"],
               "kindKr": {"notice": "공지", "free": "자유", "qna": "Q&A",
                          "patch": "패치노트"}[p["kind"]],
               "title": p["title"], "agoSec": p["ago"], "edited": p["edited"],
               "comments": len([c for c in self.comments
                                if c["post"] == p["id"] and not c["deleted"]]),
               "likes": len(who), "liked": self.uid in who,
               "mine": p["uid"] == self.uid,
               "canDelete": (p["uid"] == self.uid or admin) and not patch,
               "canEdit": p["uid"] == self.uid and not patch}
        out.update(self._who(p))
        return out

    def board(self, kind="all", page=1, q=""):
        self.calls.append(("list", kind, page) + ((q,) if q else ()))
        # 서버와 같다: '전체' 는 자유·Q&A 만 흐른다 (공지는 맨 위, 패치노트는 자기 칸).
        # 찾을 때의 '전체' 는 공지·패치노트까지 다 뒤진다.
        if kind == "all":
            rows = [p for p in self.posts if q or p["kind"] in ("free", "qna")]
        else:
            rows = [p for p in self.posts if p["kind"] == kind]
        if q:
            rows = [p for p in rows if q in p["title"] or q in p["body"] or q in p["author"]]
        rows = sorted(rows, key=lambda p: -p["id"])
        pages = max(1, (len(rows) + self.PAGE - 1) // self.PAGE)
        page = max(1, min(pages, page))
        pinned = []
        if kind == "all" and not q:
            pinned = sorted([p for p in self.posts if p["kind"] == "notice"],
                            key=lambda p: -p["id"])[:3]
        return {"kind": kind, "page": page, "pages": pages, "total": len(rows), "q": q,
                "pinned": [self._row(p) for p in pinned],
                "posts": [self._row(p) for p in rows[(page - 1) * self.PAGE:page * self.PAGE]],
                "canNotice": self.me == ADMIN,
                "limits": {"title": 40, "body": 2000, "comment": 300, "search": 30}}

    def board_like(self, pid):
        self.calls.append(("like", pid))
        if self.fail:
            raise ApiError(self.fail, 403)
        who = self.likes.setdefault(pid, set())
        if self.uid in who:
            who.discard(self.uid)
        else:
            who.add(self.uid)
        return self.board_post(pid)

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

    def mark_patch_seen(self, n):
        self.patch_seen = getattr(self, "patch_seen", []) + [n]


def t_190(root, top, w, api, app, new_id):
    """1.9.0: 좋아요, 찾기, 패치노트."""
    print("\n=== 좋아요 (1.9.0) ===")
    api.likes[new_id] = {901, 902}
    w.data = None
    w.show_kind("free")
    wait(root, lambda: w.view == "list" and w.data is not None and w.data.get("kind") == "free")
    settle(root)
    row = [p for p in w.data["posts"] if p["id"] == new_id][0]
    chk("목록의 글에 좋아요 수가 실려 온다", row["likes"] == 2 and row["liked"] is False, row)
    thumbs = [c for c in all_widgets(w.list) if isinstance(c, tk.Canvas)]
    chk("목록에 엄지척 그림과 수가 보인다", len(thumbs) >= 1 and "2" in texts(w.list), texts(w.list)[:8])
    w.open_post(new_id)
    wait(root, lambda: w.view == "post" and w.post is not None and w.post["id"] == new_id)
    settle(root)
    chk("글에 좋아요 단추가 있다", "좋아요 2" in texts(top), [t for t in texts(top) if "좋아요" in t])
    w.cv.yview_moveto(0.6)
    settle(root, 0.1)
    before = w.cv.yview()
    gen = w._gen
    w.toggle_like()
    wait(root, lambda: ("like", new_id) in api.calls and w.post.get("liked") is True)
    settle(root, 0.2)
    chk("누르면 켜지고 수가 는다", w.post["likes"] == 3 and w.like_lbl.cget("text") == "좋아요 3"
        and w.like_lbl.cget("fg") == ui_board.LIKE_ON, (w.post["likes"], w.like_lbl.cget("text")))
    chk("글을 다시 그리지 않는다 (읽던 자리 그대로)", w._gen == gen and w.cv.yview() == before,
        (gen, w._gen, before, w.cv.yview()))
    chk("아래 줄에 알려 준다", "좋아요를 눌렀습니다" in w.status._label.cget("text"))
    w.toggle_like()
    wait(root, lambda: api.calls.count(("like", new_id)) == 2 and w.post.get("liked") is False)
    settle(root, 0.2)
    chk("다시 누르면 꺼진다", w.post["likes"] == 2 and w.like_lbl.cget("text") == "좋아요 2"
        and "취소" in w.status._label.cget("text"), w.like_lbl.cget("text"))
    api.fail = "잠시 뒤에 다시 해주세요."
    w.toggle_like()
    wait(root, lambda: api.calls.count(("like", new_id)) == 3 and not w.like_busy)
    settle(root, 0.2)
    chk("서버가 거절하면 그 말을 적고 수는 그대로", "잠시 뒤에" in w.status._label.cget("text")
        and w.like_lbl.cget("text") == "좋아요 2", w.status._label.cget("text"))
    api.fail = None
    bad = squeezed(top)
    chk("  눌린 위젯 없음", not bad, bad[:3])

    print("\n=== 찾기 (1.9.0) ===")
    w.show_kind("all")
    wait(root, lambda: w.view == "list" and w.data is not None and w.data.get("kind") == "all")
    settle(root)
    chk("찾기 칸과 단추가 있다", "찾기" in texts(top) and w.q_entry.winfo_ismapped() == 1)
    chk("빈 칸에는 안내 글이 보인다", w.q_hint.winfo_ismapped() == 1)
    chk("평소에는 '전체 보기' 가 없다", "전체 보기" not in texts(top) or not w.clear_btn.holder.winfo_ismapped())
    w.q_var.set("  메가진화  ")
    w.search()
    wait(root, lambda: w.data is not None and w.data.get("q") == "메가진화")
    settle(root)
    chk("다듬은 말로 서버에 묻는다", ("list", "all", 1, "메가진화") in api.calls,
        [c for c in api.calls if c[0] == "list"][-2:])
    found = [x for x in api.posts if "메가진화" in x["title"] + x["body"] + x["author"]]
    chk("그 말이 든 글만 나온다", 1 <= w.data["total"] == len(found) < len(api.posts)
        and "메가진화 어떻게 해요?" in [p["title"] for p in w.data["posts"]]
        and set(p["id"] for p in w.data["posts"]) == set(x["id"] for x in found),
        [p["title"] for p in w.data["posts"]])
    chk("머리줄이 찾은 수를 적는다", w.count.cget("text") == "찾은 글 %d개" % len(found),
        w.count.cget("text"))
    chk("'전체 보기' 가 보인다", w.clear_btn.holder.winfo_ismapped() == 1)
    bad = squeezed(top)
    chk("  눌린 위젯 없음", not bad, bad[:3])
    w.q_var.set("없는말없는말")
    w.search()
    wait(root, lambda: w.data is not None and w.data.get("q") == "없는말없는말")
    settle(root)
    chk("없으면 없다고 적는다", any("들어간 글이 없습니다" in t for t in texts(top)), texts(top)[-6:])
    w.clear_search()
    wait(root, lambda: w.data is not None and w.data.get("q") == "" and w.data["total"] > 1)
    settle(root)
    chk("'전체 보기' 로 평소 목록에 돌아온다", w.q == "" and w.q_var.get() == ""
        and not w.clear_btn.holder.winfo_ismapped() and w.count.cget("text").startswith("글 "),
        (w.q, w.count.cget("text")))

    print("\n=== 패치노트 (1.9.0) ===")
    pid = api.seed_post("patch", ADMIN, 1, "v1.9.0 업데이트",
                        "마이페이지가 생겼습니다\n\n■ 받는 곳\nhttps://example.com/releases", ago=30)
    w.pick_kind("patch")
    wait(root, lambda: w.data is not None and w.data.get("kind") == "patch")
    settle(root)
    chk("패치노트 칸에 그 글이 있다", [p["id"] for p in w.data["posts"]] == [pid]
        and "v1.9.0 업데이트" in texts(top) and "패치노트" in texts(top), w.data["posts"])
    chk("열어 보면 '새 패치노트' 표시를 끈다", getattr(app, "patch_seen", []) == [pid],
        getattr(app, "patch_seen", None))
    w.pick_kind("all")
    wait(root, lambda: w.data is not None and w.data.get("kind") == "all")
    chk("'전체' 에는 안 섞인다", pid not in [p["id"] for p in w.data["posts"]])
    w.open_post(pid)
    wait(root, lambda: w.view == "post" and w.post is not None and w.post["id"] == pid)
    settle(root)
    links = [c for c in all_widgets(top) if isinstance(c, tk.Label)
             and str(c.cget("text")).startswith("https://")]
    chk("패치노트의 주소는 누를 수 있다", len(links) == 1 and links[0].cget("cursor") == "hand2",
        [c.cget("text") for c in links])
    chk("수정·삭제 단추가 없다 (운영자 글이어도)", "수정" not in texts(top), texts(top)[:10])
    chk("좋아요와 댓글 칸은 있다", "좋아요 0" in texts(top) and "댓글 등록" in texts(top))
    w.show_kind("patch")
    wait(root, lambda: w.view == "list" and w.data is not None and w.data.get("kind") == "patch")
    chk("밖에서 그 칸을 열 수 있다 (트레이의 '패치노트 보기')", w.kind == "patch" and w.seg.current == "patch")
    w.show_kind("all")
    wait(root, lambda: w.view == "list" and w.data is not None and w.data.get("kind") == "all")
    settle(root)


def all_widgets(w):
    out = []
    for c in w.winfo_children():
        out.append(c)
        out.extend(all_widgets(c))
    return out


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
    chk("공지 고르기가 안 보인다", "공지는 운영자만 쓸 수 있습니다." not in t
        and list(w.kind_seg.cells) == ["free", "qna"],
        list(w.kind_seg.cells))
    chk("  자유·Q&A 중에 고른다 (기본은 자유)", "종류" in t and "Q&A" in t and w.kind_var == "free", t[:12])
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

    print("\n=== Q&A (1.8.1) ===")
    w.show_list()
    wait(root, lambda: w.view == "list")
    settle(root, 0.2)
    chk("목록 위에 Q&A 가 있다 (1.9.0 부터 패치노트도)",
        list(w.seg.cells) == ["all", "notice", "free", "qna", "patch"], list(w.seg.cells))
    w.pick_kind("qna")
    wait(root, lambda: w.data is not None and w.data.get("kind") == "qna")
    settle(root)
    chk("아직 질문이 없으면 빈 목록", w.data["total"] == 0, w.data["total"])
    w.show_write()
    settle(root, 0.15)
    chk("Q&A 를 보다가 쓰면 Q&A 가 골라져 있다", w.kind_var == "qna")
    w.title_var.set("메가진화 어떻게 해요?")
    w.text.insert("1.0", "키스톤은 어디서 얻나요")
    w._count_post()
    settle(root, 0.2)
    bad = squeezed(top)
    chk("  쓰는 화면에 눌린 위젯 없음", not bad, bad[:3])
    w.submit_post()
    chk("Q&A 로 보낸다", wait(root, lambda: any(c[0] == "write" and c[1] == "qna"
                                            and c[2] == "메가진화 어떻게 해요?" for c in api.calls)),
        [c for c in api.calls if c[0] == "write"][-1:])
    wait(root, lambda: w.view == "post" and w.post and w.post["title"] == "메가진화 어떻게 해요?")
    settle(root)
    chk("올린 질문이 바로 열리고 Q&A 표시가 붙는다", w.view == "post" and w.post is not None
        and w.post["kind"] == "qna" and "Q&A" in texts(top), (w.view, texts(top)[:8]))
    qid = w.post["id"]
    w.show_list()
    wait(root, lambda: w.view == "list" and w.data is not None and w.data.get("kind") == "qna"
         and w.data["total"] == 1)
    settle(root)
    chk("Q&A 탭에는 질문만", [p["id"] for p in w.data["posts"]] == [qid]
        and "메가진화 어떻게 해요?" in texts(top), [p["id"] for p in w.data["posts"]])
    w.pick_kind("free")
    wait(root, lambda: w.data is not None and w.data.get("kind") == "free")
    chk("자유 탭에는 안 나온다", qid not in [p["id"] for p in w.data["posts"]])
    w.pick_kind("all")
    wait(root, lambda: w.data is not None and w.data.get("kind") == "all")
    settle(root)
    chk("전체에는 자유 글과 함께 나온다", qid in [p["id"] for p in w.data["posts"]]
        and any(p["kind"] == "free" for p in w.data["posts"]), [p["kind"] for p in w.data["posts"]][:6])
    bad = squeezed(top)
    chk("  눌린 위젯 없음", not bad, bad[:3])
    t_190(root, top, w, api, app, new_id)
    # 아래 절은 방금 올린 자유 글을 열어 둔 데서 이어진다
    w.open_post(new_id)
    wait(root, lambda: w.view == "post" and w.post is not None and w.post["id"] == new_id)
    settle(root)

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

    print("\n=== 공지의 링크 (1.8.1) ===")
    URL = "https://github.com/rudtjr1106/poketdesktop/releases"
    chk("주소를 가른다 (바로 붙은 한글에서 끝난다)",
        ui_board.split_links("받는 곳: %s에서 받으세요." % URL)
        == [("text", "받는 곳: "), ("link", URL), ("text", "에서 받으세요.")],
        ui_board.split_links("받는 곳: %s에서 받으세요." % URL))
    chk("  문장 끝의 마침표·괄호는 주소가 아니다",
        ui_board.split_links("(%s)." % URL)[1] == ("link", URL), ui_board.split_links("(%s)." % URL))
    chk("  주소가 없으면 그대로 한 덩이", ui_board.split_links("그냥 글\n둘째 줄")
        == [("text", "그냥 글\n둘째 줄")])
    chk("  http·https 가 아니면 열지 않는다", ui_board.open_url("file:///etc/passwd") is False
        and ui_board.open_url("javascript:alert(1)") is False)
    opened = []
    real_open = ui_board.open_url
    ui_board.open_url = lambda u: opened.append(u) or True
    body = "새 버전이 나왔습니다.\n%s\n위 주소에서 받아 주세요." % URL
    nid = api2.seed_post("notice", ADMIN, 1, "링크가 든 공지", body)
    fid = api2.seed_post("free", "이슬", 3, "링크가 든 자유 글", body)

    def links(win):
        out = []

        def walk(w):
            for c in w.winfo_children():
                if c.winfo_class() == "Label" and str(c.cget("cursor")) == "hand2" \
                        and str(c.cget("text")).startswith("http"):
                    out.append(c)
                walk(c)
        walk(win)
        return out
    w2.open_post(nid)
    wait(root, lambda: w2.post is not None and w2.post["id"] == nid)
    settle(root)
    ls = links(w2.win)
    chk("공지의 주소는 누를 수 있다", len(ls) == 1 and ls[0].cget("text") == URL,
        [c.cget("text") for c in ls])
    chk("  앞뒤 글은 그대로 보인다", "새 버전이 나왔습니다." in texts(w2.win)
        and "위 주소에서 받아 주세요." in texts(w2.win), texts(w2.win)[-8:])
    ls[0].event_generate("<Button-1>")
    root.update()
    chk("  누르면 그 주소를 연다", opened == [URL], opened)
    bad = squeezed(w2.win)
    chk("  눌린 위젯 없음", not bad, bad[:3])
    w2.open_post(fid)
    wait(root, lambda: w2.post is not None and w2.post["id"] == fid)
    settle(root)
    chk("자유 글의 주소는 그냥 글자다 (누를 수 없다)", not links(w2.win)
        and any(URL in t for t in texts(w2.win)), [t for t in texts(w2.win) if "http" in t])
    ui_board.open_url = real_open

    print("\n=== 한글 자판에서 붙여넣기 (1.8.1) ===")
    mac = root.tk.call("tk", "windowingsystem") == "aqua"
    chk("영문 자판이면 손대지 않는다 (Tk 가 한다)",
        U.edit_event_for("v", "v", (9 << 24) | ord("v"), True) is None
        and U.edit_event_for("v", "\x16", 86, False) is None)
    chk("맥: 한글 자판의 Cmd+ㅍ 은 붙여넣기",
        U.edit_event_for("Hangul_Phieuf", "", (9 << 24) | 0x314D, True) == "<<Paste>>")
    chk("맥: ㅊ 복사 · ㅌ 잘라내기 · ㅁ 전체 선택",
        [U.edit_event_for("", "", (vk << 24) | ord(ch), True) for vk, ch in ((8, "ㅊ"), (7, "ㅌ"), (0, "ㅁ"))]
        == ["<<Copy>>", "<<Cut>>", "<<SelectAll>>"])
    chk("윈도우: 글쇠 이름이 깨져도 자리(VK)로 안다",
        [U.edit_event_for("??", "", vk, False) for vk in (86, 67, 88, 65)]
        == ["<<Paste>>", "<<Copy>>", "<<Cut>>", "<<SelectAll>>"])
    chk("상관없는 글쇠는 None", U.edit_event_for("b", "b", (11 << 24) | 98, True) is None
        and U.edit_event_for("??", "", 66, False) is None)
    # 진짜 입력칸에서: 클립보드의 글이 들어온다
    w2.show_write()
    settle(root, 0.2)
    root.clipboard_clear()
    root.clipboard_append("붙여 넣은 글")
    root.update()
    w2.text.delete("1.0", "end")
    w2.text.focus_force()
    root.update()
    seq, code = ("<Mod1-KeyPress>", (9 << 24) | 0x314D) if mac else ("<Control-KeyPress>", 86)
    w2.text.event_generate(seq, keycode=code)
    root.update()
    chk("글쓰기 칸: 한글 자판으로 붙여 넣는다", w2.text.get("1.0", "end-1c") == "붙여 넣은 글",
        w2.text.get("1.0", "end-1c"))
    w2.close()

    ui_box.confirm = real_confirm
    settle(root, 0.3)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
