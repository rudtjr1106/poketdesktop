# -*- coding: utf-8 -*-
"""게시판 — 공지와 자유 글, 댓글과 대댓글 (1.8.0).

1.9.0 에서 넷이 붙었다: **패치노트**(서버가 올린다), **좋아요**, **검색**,
**알림**(내 글에 댓글·내 댓글에 답글). 아래 각 절에 적었다.

## 글의 종류

  · **공지(notice)** — 운영자만 쓴다. 운영자는 닉네임으로 정한다
    (config.BOARD_ADMINS, 기본 '나여조경석'). 닉네임은 계정마다 하나뿐이라
    남이 같은 이름을 쓸 수 없다. 비슷하게 생긴 이름으로 흉내 내는 것은
    화면의 '운영자' 표시로 가린다 - 그 표시는 여기서 붙인다.
  · **자유(free)** · **Q&A(qna)** — 누구나 쓴다.
  · **패치노트(patch)** — 사람이 쓰지 않는다. 서버가 뜰 때 common/patchnotes
    의 버전마다 글 하나씩을 올린다 (ensure_patch_posts). 같은 버전을 두 번
    올리지 않으려고 ref('patch:1.9.0')를 본다. 댓글과 좋아요는 달 수 있다.

## 좋아요

글마다 한 사람이 한 번. 다시 누르면 취소된다 (board_like). 댓글에는 없다.

## 검색

제목·내용·쓴 사람 이름에 그 말이 들어 있는 글. '전체' 에서 찾으면 공지와
패치노트까지 같이 찾는다 (평소의 '전체' 는 자유와 Q&A 만 흐른다).

## 알림

누가 **내 글에 댓글**을 달거나 **내 댓글에 답글**을 달면 내 앞으로 한 줄이
생긴다 (board_notify). /api/me 에 실려 가고, 화면이 운영체제 알림으로
알린다. **그 글을 열어 보면 그 알림은 없어진다** - 본 알림을 쌓아 두지 않는다
(목록에는 아직 안 본 것만 있다). 내가 나에게 단 것은 없다.

## 댓글

댓글과, 댓글에 다는 답글(대댓글) **한 단계**까지다. 답글에 다시 답글을 달면
같은 댓글 아래에 나란히 붙는다 - 더 깊어지면 좁은 창에서 읽을 수가 없다.

## 지우기

글과 댓글은 쓴 사람과 운영자가 지운다. 줄을 없애지 않고 deleted 로 표시만
한다. 답글이 달린 댓글을 지우면 '삭제된 댓글입니다' 로 자리를 남긴다 -
없애 버리면 답글이 무엇에 대한 말인지 알 수 없다.

## 도배

글은 30초, 댓글은 5초에 하나. 하루 글 20개·댓글 200개까지. 같은 사람이
연달아 쓰는 것만 막는다 - 내용 검열은 하지 않고, 문제 글은 운영자가 지운다.

## 시각

'몇 분 전' 은 **서버가 센 초**로 준다(agoSec). 시각을 받아 화면이 자기
시계로 빼면 PC 시계가 틀어진 사람에게 엉뚱하게 보인다 (korean.ago 의 규칙).
"""
import datetime

from common import patchnotes

from . import config, db, season

# 공지는 운영자만 쓴다. 자유와 Q&A(1.8.1)는 누구나 쓴다 - 질문이 자유 글에 섞여
# 묻히지 않게 따로 둔 칸일 뿐, 규칙은 자유 글과 같다. 패치노트(1.9.0)는 서버가 올린다.
KINDS = ("notice", "free", "qna", "patch")
KIND_KR = {"notice": "공지", "free": "자유", "qna": "Q&A", "patch": "패치노트"}
# '전체' 에 흐르는 글. 공지는 맨 위에 따로 붙고, 패치노트는 자기 칸에만 있다.
FLOW = ("free", "qna")
SEARCH_MAX = 30               # 찾는 말 길이
NOTIFY_KEEP = 30              # 알림 목록에 보이는 수
NOTIFY_CARD = 5               # /api/me 에 싣는 안 본 알림 수
TITLE_MAX = 40
BODY_MAX = 2000
COMMENT_MAX = 300
PAGE = 15
PINNED = 3                    # '전체' 목록 맨 위에 늘 보이는 공지 수
POST_COOLDOWN = 30            # 초
COMMENT_COOLDOWN = 5
POSTS_PER_DAY = 20
COMMENTS_PER_DAY = 200


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(now=None):
    return (now or _now()).replace(microsecond=0).isoformat()


def _ago(iso, now=None):
    try:
        t = datetime.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return max(0, int(((now or _now()) - t).total_seconds()))


def is_admin(user):
    name = (user or {}).get("username") if isinstance(user, dict) else \
        (user["username"] if user is not None else None)
    return bool(name) and name in config.BOARD_ADMINS


def _admin_ids():
    if not config.BOARD_ADMINS:
        return set()
    marks = ",".join("?" * len(config.BOARD_ADMINS))
    return set(r["id"] for r in db.q(
        "SELECT id FROM users WHERE username IN (%s)" % marks,
        tuple(config.BOARD_ADMINS)))


def clean(text, limit, what, one_line=False):
    """글자를 다듬고 길이를 본다. 비었거나 길면 ValueError."""
    s = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    # 보이지 않는 제어 글자를 뺀다 (줄바꿈·탭은 둔다)
    s = "".join(ch for ch in s if ch in "\n\t" or ord(ch) >= 32)
    if one_line:
        s = " ".join(s.split())
    else:
        lines = [ln.rstrip() for ln in s.split("\n")]
        out, blank = [], 0
        for ln in lines:                      # 빈 줄은 두 줄까지만
            blank = blank + 1 if not ln else 0
            if blank <= 2:
                out.append(ln)
        s = "\n".join(out).strip("\n")
    s = s.strip()
    if not s:
        raise ValueError("%s을(를) 적어 주세요." % what)
    if len(s) > limit:
        raise ValueError("%s은(는) %d자까지 쓸 수 있습니다. (지금 %d자)"
                         % (what, limit, len(s)))
    return s


def _throttle(uid, table, cooldown, per_day, what, now=None):
    now = now or _now()
    last = db.q1("SELECT MAX(created_at) t FROM %s WHERE user_id=?" % table, (uid,))
    gone = _ago(last["t"], now) if last and last["t"] else None
    if gone is not None and gone < cooldown:
        raise PermissionError("%s은(는) %d초에 하나씩 쓸 수 있습니다. %d초 뒤에 다시 해주세요."
                              % (what, cooldown, cooldown - gone))
    since = (now - datetime.timedelta(days=1)).replace(microsecond=0).isoformat()
    n = db.q1("SELECT COUNT(*) c FROM %s WHERE user_id=? AND created_at > ?" % table,
              (uid, since))["c"]
    if n >= per_day:
        raise PermissionError("하루에 쓸 수 있는 %s 수(%d개)를 넘었습니다." % (what, per_day))


# ---------------------------------------------------------------- 보여 주기
def _authors(ids):
    """이름·칭호·명패. {user_id: {...}}. 목록 하나에 한 번만 묻는다."""
    ids = [i for i in set(ids) if i is not None]
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    names = dict((r["id"], r["username"]) for r in db.q(
        "SELECT id, username FROM users WHERE id IN (%s)" % marks, tuple(ids)))
    deco = season.deco_map(ids)
    admins = _admin_ids()
    out = {}
    for i in ids:
        d = deco.get(i) or {}
        out[i] = {"name": names.get(i), "title": d.get("title"),
                  "frameColor": d.get("frameColor"), "admin": i in admins}
    return out


def _who(row, authors):
    a = authors.get(row["user_id"]) or {}
    return {"authorId": row["user_id"],
            # 닉네임은 지금 것을 쓴다. 계정이 없어졌으면 쓸 때 이름.
            "author": a.get("name") or row["author"],
            "authorTitle": a.get("title"), "authorColor": a.get("frameColor"),
            "authorAdmin": bool(a.get("admin"))}


def _post_row(r, authors, uid, admin, now, counts, likes=None):
    n_like, mine_like = likes or ({}, set())
    patch = r["kind"] == "patch"
    out = {"id": r["id"], "kind": r["kind"], "kindKr": KIND_KR.get(r["kind"], r["kind"]),
           "title": r["title"], "createdAt": r["created_at"],
           "agoSec": _ago(r["created_at"], now), "edited": bool(r["updated_at"]),
           "comments": counts.get(r["id"], 0),
           "likes": n_like.get(r["id"], 0), "liked": r["id"] in mine_like,
           "mine": r["user_id"] == uid,
           # 패치노트는 서버가 올린 글이다. 고치면 다음 판과 모양이 갈린다.
           "canDelete": (r["user_id"] == uid or admin) and not patch,
           "canEdit": r["user_id"] == uid and not patch}
    out.update(_who(r, authors))
    return out


def _likes(ids, uid):
    """({글: 좋아요 수}, 내가 누른 글들)."""
    if not ids:
        return {}, set()
    marks = ",".join("?" * len(ids))
    n = dict((r["post_id"], r["c"]) for r in db.q(
        "SELECT post_id, COUNT(*) c FROM board_like WHERE post_id IN (%s)"
        " GROUP BY post_id" % marks, tuple(ids)))
    mine = set(r["post_id"] for r in db.q(
        "SELECT post_id FROM board_like WHERE user_id=? AND post_id IN (%s)" % marks,
        (uid,) + tuple(ids)))
    return n, mine


def _counts(ids):
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    return dict((r["post_id"], r["c"]) for r in db.q(
        "SELECT post_id, COUNT(*) c FROM board_comment WHERE deleted=0 AND post_id IN (%s)"
        " GROUP BY post_id" % marks, tuple(ids)))


def _like_arg(q):
    """LIKE 에 넣을 말. % 와 _ 는 글자 그대로 찾는다."""
    q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return "%" + q + "%"


def listing(user, kind="all", page=1, now=None, q=None):
    """목록 한 쪽. '전체' 는 최근 공지 몇 개를 맨 위에 붙이고 나머지 글(자유·Q&A)을 넘긴다.

    q 가 있으면 **찾기**다: 제목·내용·쓴 사람에 그 말이 든 글만. 이때는 맨 위에
    붙는 공지가 없고, '전체' 는 공지·패치노트까지 다 뒤진다.
    """
    uid = user["id"]
    admin = is_admin(user)
    now = now or _now()
    kind = kind if kind in KINDS else "all"
    page = max(1, int(page or 1))
    q = " ".join((q or "").split())[:SEARCH_MAX]
    if kind == "all" and q:
        where, args = "deleted=0", ()
    elif kind == "all":
        # 공지는 맨 위에 따로 붙으므로 뺀다. 자유와 Q&A 가 함께 흐른다.
        where = "deleted=0 AND kind IN (%s)" % ",".join("?" * len(FLOW))
        args = tuple(FLOW)
    else:
        where, args = "deleted=0 AND kind=?", (kind,)
    if q:
        where += " AND (title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\'" \
                 " OR author LIKE ? ESCAPE '\\')"
        args = args + (_like_arg(q),) * 3
    total = db.q1("SELECT COUNT(*) c FROM board_post WHERE " + where, args)["c"]
    pages = max(1, (total + PAGE - 1) // PAGE)
    page = min(page, pages)
    rows = list(db.q("SELECT * FROM board_post WHERE " + where
                     + " ORDER BY id DESC LIMIT ? OFFSET ?",
                     args + (PAGE, (page - 1) * PAGE)))
    pinned = []
    if kind == "all" and not q:
        pinned = list(db.q("SELECT * FROM board_post WHERE deleted=0 AND kind='notice'"
                           " ORDER BY id DESC LIMIT ?", (PINNED,)))
    both = pinned + rows
    authors = _authors([r["user_id"] for r in both])
    counts = _counts([r["id"] for r in both])
    likes = _likes([r["id"] for r in both], uid)
    return {"kind": kind, "page": page, "pages": pages, "total": total, "q": q,
            "pinned": [_post_row(r, authors, uid, admin, now, counts, likes) for r in pinned],
            "posts": [_post_row(r, authors, uid, admin, now, counts, likes) for r in rows],
            "canNotice": admin,
            "limits": {"title": TITLE_MAX, "body": BODY_MAX, "comment": COMMENT_MAX,
                       "search": SEARCH_MAX}}


def _post(pid):
    return db.q1("SELECT * FROM board_post WHERE id=? AND deleted=0", (pid,))


def detail(user, pid, now=None):
    """글 하나와 댓글. 댓글은 [댓글 {…, replies: [답글…]}] 로 묶는다.

    열어 본 것이므로 이 글에 걸린 내 알림은 지운다 (본 알림은 남기지 않는다).
    """
    uid = user["id"]
    admin = is_admin(user)
    now = now or _now()
    r = _post(pid)
    if not r:
        raise LookupError("없는 글이거나 지워진 글입니다.")
    db.run("DELETE FROM board_notify WHERE user_id=? AND post_id=?", (uid, pid))
    rows = list(db.q("SELECT * FROM board_comment WHERE post_id=? ORDER BY id", (pid,)))
    authors = _authors([r["user_id"]] + [c["user_id"] for c in rows])
    post = _post_row(r, authors, uid, admin, now, _counts([pid]), _likes([pid], uid))
    post["body"] = r["body"]

    def one(c):
        out = {"id": c["id"], "createdAt": c["created_at"],
               "agoSec": _ago(c["created_at"], now),
               "deleted": bool(c["deleted"]),
               "body": "" if c["deleted"] else c["body"],
               "mine": c["user_id"] == uid and not c["deleted"],
               "canDelete": (c["user_id"] == uid or admin) and not c["deleted"]}
        out.update(_who(c, authors))
        if c["deleted"]:                      # 누가 썼는지도 가린다
            out.update({"author": "", "authorTitle": None, "authorColor": None,
                        "authorAdmin": False})
        return out

    tops, by_id = [], {}
    for c in rows:
        if c["parent_id"] is None:
            item = one(c)
            item["replies"] = []
            by_id[c["id"]] = item
            tops.append(item)
    for c in rows:
        if c["parent_id"] is not None and not c["deleted"]:
            parent = by_id.get(c["parent_id"])
            if parent is not None:
                parent["replies"].append(one(c))
    # 지운 댓글은 답글이 남아 있을 때만 자리를 둔다
    post["commentList"] = [t for t in tops if not t["deleted"] or t["replies"]]
    post["canComment"] = True
    return post


# ---------------------------------------------------------------- 쓰기
def create(user, kind, title, body, now=None):
    if kind not in KINDS:
        raise ValueError("글의 종류를 알 수 없습니다.")
    if kind == "patch":
        raise PermissionError("패치노트는 새 버전이 나올 때 자동으로 올라옵니다.")
    if kind == "notice" and not is_admin(user):
        raise PermissionError("공지는 운영자만 쓸 수 있습니다.")
    title = clean(title, TITLE_MAX, "제목", one_line=True)
    body = clean(body, BODY_MAX, "내용")
    if not is_admin(user):
        _throttle(user["id"], "board_post", POST_COOLDOWN, POSTS_PER_DAY, "글", now)
    cur = db.run("INSERT INTO board_post (kind, user_id, author, title, body, created_at)"
                 " VALUES (?,?,?,?,?,?)",
                 (kind, user["id"], user["username"], title, body, _iso(now)))
    return cur.lastrowid


def edit(user, pid, title, body, now=None):
    r = _post(pid)
    if not r:
        raise LookupError("없는 글이거나 지워진 글입니다.")
    if r["user_id"] != user["id"]:
        raise PermissionError("내가 쓴 글만 고칠 수 있습니다.")
    if r["kind"] == "patch":
        raise PermissionError("패치노트는 고칠 수 없습니다.")
    title = clean(title, TITLE_MAX, "제목", one_line=True)
    body = clean(body, BODY_MAX, "내용")
    db.run("UPDATE board_post SET title=?, body=?, updated_at=? WHERE id=?",
           (title, body, _iso(now), pid))
    return pid


def remove(user, pid):
    r = _post(pid)
    if not r:
        raise LookupError("없는 글이거나 지워진 글입니다.")
    if r["user_id"] != user["id"] and not is_admin(user):
        raise PermissionError("내가 쓴 글만 지울 수 있습니다.")
    if r["kind"] == "patch":
        raise PermissionError("패치노트는 지울 수 없습니다.")
    db.run("UPDATE board_post SET deleted=1 WHERE id=?", (pid,))
    db.run("DELETE FROM board_notify WHERE post_id=?", (pid,))


def like(user, pid, now=None):
    """좋아요를 누르거나 취소한다. 누른 상태가 됐으면 True."""
    if not _post(pid):
        raise LookupError("없는 글이거나 지워진 글입니다.")
    uid = user["id"]
    if db.q1("SELECT 1 FROM board_like WHERE post_id=? AND user_id=?", (pid, uid)):
        db.run("DELETE FROM board_like WHERE post_id=? AND user_id=?", (pid, uid))
        return False
    db.run("INSERT INTO board_like (post_id, user_id, created_at) VALUES (?,?,?)"
           " ON CONFLICT(post_id, user_id) DO NOTHING", (pid, uid, _iso(now)))
    return True


def comment(user, pid, body, parent=None, now=None):
    post = _post(pid)
    if not post:
        raise LookupError("없는 글이거나 지워진 글입니다.")
    body = clean(body, COMMENT_MAX, "댓글")
    parent_id, target = None, None
    if parent:
        p = db.q1("SELECT id, post_id, parent_id, user_id, deleted FROM board_comment"
                  " WHERE id=?", (int(parent),))
        if not p or p["post_id"] != pid:
            raise LookupError("답글을 달 댓글이 없습니다.")
        # 답글에 다는 답글은 같은 댓글 아래에 나란히 붙인다 (한 단계까지)
        parent_id = p["parent_id"] or p["id"]
        target = None if p["deleted"] else p["user_id"]      # 누구의 댓글에 다는가
    if not is_admin(user):
        _throttle(user["id"], "board_comment", COMMENT_COOLDOWN, COMMENTS_PER_DAY, "댓글", now)
    cur = db.run("INSERT INTO board_comment (post_id, parent_id, user_id, author, body,"
                 " created_at) VALUES (?,?,?,?,?,?)",
                 (pid, parent_id, user["id"], user["username"], body, _iso(now)))
    cid = cur.lastrowid
    try:
        _notify(user, post, cid, target, now)
    except Exception:                                        # noqa: BLE001
        pass                    # 알림은 있으면 좋은 것이다. 댓글은 이미 달렸다.
    return cid


def _notify(user, post, cid, target, now=None):
    """알림을 남긴다. 답글이면 그 댓글을 쓴 사람에게, 그리고 글쓴이에게.

    한 사람에게 한 줄만 간다 - 내 글의 내 댓글에 답글이 달리면 '답글' 하나다.
    내가 쓴 것은 나에게 알리지 않는다. 패치노트는 서버가 올린 글이라 글쓴이
    (운영자)에게 댓글마다 알리지 않는다 - 답글만 알린다.
    """
    me = user["id"]
    who = []
    if target is not None and target != me:
        who.append((target, "reply"))
    if post["user_id"] != me and post["kind"] != "patch" \
            and post["user_id"] not in [u for u, _k in who]:
        who.append((post["user_id"], "comment"))
    for uid, kind in who:
        db.run("INSERT INTO board_notify (user_id, post_id, comment_id, kind, actor,"
               " created_at) VALUES (?,?,?,?,?,?)",
               (uid, post["id"], cid, kind, user["username"], _iso(now)))


def remove_comment(user, cid):
    c = db.q1("SELECT * FROM board_comment WHERE id=? AND deleted=0", (cid,))
    if not c:
        raise LookupError("없는 댓글이거나 지워진 댓글입니다.")
    if c["user_id"] != user["id"] and not is_admin(user):
        raise PermissionError("내가 쓴 댓글만 지울 수 있습니다.")
    db.run("UPDATE board_comment SET deleted=1 WHERE id=?", (cid,))
    db.run("DELETE FROM board_notify WHERE comment_id=?", (cid,))    # 지운 댓글은 알리지 않는다
    return c["post_id"]


# ---------------------------------------------------------------- 알림
def _notify_rows(uid, only_unseen, limit, now=None, offset=0):
    now = now or _now()
    rows = db.q(
        "SELECT n.id, n.kind, n.actor, n.created_at, n.seen, n.post_id, n.comment_id,"
        " p.title, c.body FROM board_notify n"
        " JOIN board_post p ON p.id=n.post_id AND p.deleted=0"
        " JOIN board_comment c ON c.id=n.comment_id AND c.deleted=0"
        " WHERE n.user_id=?" + (" AND n.seen=0" if only_unseen else "")
        + " ORDER BY n.id DESC LIMIT ? OFFSET ?", (uid, limit, int(offset or 0)))
    out = []
    for r in rows:
        body = " ".join((r["body"] or "").split())
        out.append({"id": r["id"], "kind": r["kind"], "actor": r["actor"],
                    "postId": r["post_id"], "commentId": r["comment_id"],
                    "title": r["title"],
                    "snippet": body if len(body) <= 40 else body[:40] + "…",
                    "agoSec": _ago(r["created_at"], now), "seen": bool(r["seen"])})
    return out


def notifications(uid, now=None):
    """알림 목록 (최근 것부터). 본 알림은 지워지므로 여기 있는 것은 다 안 본 것이다."""
    items = _notify_rows(uid, True, NOTIFY_KEEP, now)
    return {"items": items, "unseen": mine(uid)["unseen"]}


def notify_seen(uid):
    """알림을 다 본 것으로 한다 = 다 지운다 ('모두 읽음')."""
    db.run("DELETE FROM board_notify WHERE user_id=?", (uid,))


def me_card(uid=None):
    """/api/me 에 싣는다.

    notice / patch — 가장 최근 공지·패치노트 글의 번호. 화면이 '새 글' 을 표시한다.
    notify — 안 본 알림 수와 최근 몇 개. 화면이 운영체제 알림으로 알린다.
    """
    out = {"notice": 0, "patch": 0, "notify": {"count": 0, "items": []}}
    try:
        for r in db.q("SELECT kind, MAX(id) m FROM board_post WHERE deleted=0"
                      " AND kind IN ('notice','patch') GROUP BY kind"):
            out[r["kind"]] = int(r["m"] or 0)
        if uid is not None:
            n = db.q1(
                "SELECT COUNT(*) c FROM board_notify n"
                " JOIN board_post p ON p.id=n.post_id AND p.deleted=0"
                " JOIN board_comment c ON c.id=n.comment_id AND c.deleted=0"
                " WHERE n.user_id=? AND n.seen=0", (uid,))["c"]
            if n:
                out["notify"] = {"count": n,
                                 "items": _notify_rows(uid, True, NOTIFY_CARD)}
    except Exception:                                        # noqa: BLE001
        pass
    return out


# ---------------------------------------------------------------- 내 활동 (마이페이지)
MINE_PAGE = 5                 # 마이페이지의 한 쪽
MINE_WHAT = ("notify", "posts", "comments")


def mine(uid):
    """내 활동의 **수**만: 쓴 글, 단 댓글, 받은 좋아요, 알림(전체·안 본 것)."""
    total = db.q1("SELECT COUNT(*) c FROM board_post WHERE user_id=? AND deleted=0"
                  " AND kind<>'patch'", (uid,))["c"]
    ctotal = db.q1("SELECT COUNT(*) c FROM board_comment c JOIN board_post p"
                   " ON p.id=c.post_id AND p.deleted=0 WHERE c.user_id=? AND c.deleted=0",
                   (uid,))["c"]
    got = db.q1("SELECT COUNT(*) c FROM board_like l JOIN board_post p ON p.id=l.post_id"
                " WHERE p.user_id=? AND p.deleted=0 AND p.kind<>'patch'", (uid,))["c"]
    n = db.q1("SELECT COUNT(*) c FROM board_notify n"
              " JOIN board_post p ON p.id=n.post_id AND p.deleted=0"
              " JOIN board_comment c ON c.id=n.comment_id AND c.deleted=0"
              " WHERE n.user_id=? AND n.seen=0", (uid,))
    # 본 알림은 지워지므로 알림 수 = 안 본 수다 (열쇠 둘은 화면이 쓰던 이름 그대로 둔다)
    return {"postCount": total, "commentCount": ctotal, "likes": got,
            "notifyCount": int(n["c"] or 0), "unseen": int(n["c"] or 0)}


def mine_page(uid, what="posts", page=1, now=None, size=MINE_PAGE):
    """내 활동 한 쪽 (마이페이지). what = notify / posts / comments.

    **쪽으로 나눠 준다.** 활동은 계속 쌓이는데 한 번에 다 주면 화면이 끝없이
    길어진다. 화면은 한 쪽(5개)만 그리고 ◀ ▶ 로 넘긴다 - 글이 천 개여도
    마이페이지의 높이는 같다.
    """
    now = now or _now()
    what = what if what in MINE_WHAT else "posts"
    counts = mine(uid)
    total = {"posts": counts["postCount"], "comments": counts["commentCount"],
             "notify": counts["notifyCount"]}[what]
    pages = max(1, (total + size - 1) // size)
    page = max(1, min(pages, int(page or 1)))
    off = (page - 1) * size
    items = []
    if what == "posts":
        rows = list(db.q("SELECT * FROM board_post WHERE user_id=? AND deleted=0"
                         " AND kind<>'patch' ORDER BY id DESC LIMIT ? OFFSET ?",
                         (uid, size, off)))
        ids = [r["id"] for r in rows]
        n_cm, likes = _counts(ids), _likes(ids, uid)
        items = [{"id": r["id"], "postId": r["id"], "kind": r["kind"],
                  "kindKr": KIND_KR.get(r["kind"], r["kind"]), "title": r["title"],
                  "agoSec": _ago(r["created_at"], now),
                  "comments": n_cm.get(r["id"], 0), "likes": likes[0].get(r["id"], 0)}
                 for r in rows]
    elif what == "comments":
        for r in db.q("SELECT c.id, c.post_id, c.body, c.created_at, p.title"
                      " FROM board_comment c JOIN board_post p ON p.id=c.post_id AND p.deleted=0"
                      " WHERE c.user_id=? AND c.deleted=0 ORDER BY c.id DESC LIMIT ? OFFSET ?",
                      (uid, size, off)):
            body = " ".join((r["body"] or "").split())
            items.append({"id": r["id"], "postId": r["post_id"], "title": r["title"],
                          "snippet": body if len(body) <= 50 else body[:50] + "…",
                          "agoSec": _ago(r["created_at"], now)})
    else:
        items = _notify_rows(uid, True, size, now, off)
    return {"what": what, "page": page, "pages": pages, "total": total, "size": size,
            "items": items, "counts": counts}


# ---------------------------------------------------------------- 패치노트 글
def _patch_time(version, now=None):
    return patchnotes.RELEASED.get(version) or _iso(now)


def ensure_patch_posts(now=None, upto=None):
    """버전마다 패치노트 글 하나. 없는 것만 올린다. 올린 버전 목록을 돌려준다.

    **서버가 뜰 때 한 번 부른다.** 새 판을 배포하면 그 판의 글이 그때 생긴다.
    옛 버전은 처음 한 번 몰아서 올라가는데, 날짜는 그 판이 나온 때로 적는다
    (patchnotes.RELEASED). 오래된 판부터 넣어서 번호도 나온 순서다.

    글쓴이는 운영자다. 운영자 계정이 아직 없으면(새 DB) 아무것도 안 하고,
    다음에 뜰 때 다시 본다. 지워진 글도 '있는 것' 으로 쳐서 되살리지 않는다.

    upto 는 여기까지의 버전만 (검사용).
    """
    admin = None
    for name in config.BOARD_ADMINS:
        admin = db.q1("SELECT id, username FROM users WHERE username=?", (name,))
        if admin:
            break
    if not admin:
        return []
    have = set(r["ref"] for r in db.q(
        "SELECT ref FROM board_post WHERE ref LIKE 'patch:%'"))
    made = []
    for n in reversed(patchnotes.NOTES):                   # 오래된 판부터
        ver = n["version"]
        if upto and patchnotes._key(ver) > patchnotes._key(upto):
            continue
        ref = "patch:" + ver
        if ref in have:
            continue
        title, body = patchnotes.as_post(ver)
        db.run("INSERT INTO board_post (kind, user_id, author, title, body, created_at, ref)"
               " VALUES ('patch',?,?,?,?,?,?)",
               (admin["id"], admin["username"], title, body, _patch_time(ver, now), ref))
        made.append(ver)
    return made
