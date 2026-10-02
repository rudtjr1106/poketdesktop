# -*- coding: utf-8 -*-
"""게시판 — 공지와 자유 글, 댓글과 대댓글 (1.8.0).

## 글 두 가지

  · **공지(notice)** — 운영자만 쓴다. 운영자는 닉네임으로 정한다
    (config.BOARD_ADMINS, 기본 '나여조경석'). 닉네임은 계정마다 하나뿐이라
    남이 같은 이름을 쓸 수 없다. 비슷하게 생긴 이름으로 흉내 내는 것은
    화면의 '운영자' 표시로 가린다 - 그 표시는 여기서 붙인다.
  · **자유(free)** — 누구나 쓴다.

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

from . import config, db, season

KINDS = ("notice", "free")
KIND_KR = {"notice": "공지", "free": "자유"}
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


def _post_row(r, authors, uid, admin, now, counts):
    out = {"id": r["id"], "kind": r["kind"], "kindKr": KIND_KR.get(r["kind"], r["kind"]),
           "title": r["title"], "createdAt": r["created_at"],
           "agoSec": _ago(r["created_at"], now), "edited": bool(r["updated_at"]),
           "comments": counts.get(r["id"], 0),
           "mine": r["user_id"] == uid,
           "canDelete": r["user_id"] == uid or admin,
           "canEdit": r["user_id"] == uid}
    out.update(_who(r, authors))
    return out


def _counts(ids):
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    return dict((r["post_id"], r["c"]) for r in db.q(
        "SELECT post_id, COUNT(*) c FROM board_comment WHERE deleted=0 AND post_id IN (%s)"
        " GROUP BY post_id" % marks, tuple(ids)))


def listing(user, kind="all", page=1, now=None):
    """목록 한 쪽. '전체' 는 최근 공지 몇 개를 맨 위에 붙이고 자유 글을 넘긴다."""
    uid = user["id"]
    admin = is_admin(user)
    now = now or _now()
    kind = kind if kind in KINDS else "all"
    page = max(1, int(page or 1))
    where = "deleted=0 AND kind=?"
    args = ("free" if kind == "all" else kind,)
    total = db.q1("SELECT COUNT(*) c FROM board_post WHERE " + where, args)["c"]
    pages = max(1, (total + PAGE - 1) // PAGE)
    page = min(page, pages)
    rows = list(db.q("SELECT * FROM board_post WHERE " + where
                     + " ORDER BY id DESC LIMIT ? OFFSET ?",
                     args + (PAGE, (page - 1) * PAGE)))
    pinned = []
    if kind == "all":
        pinned = list(db.q("SELECT * FROM board_post WHERE deleted=0 AND kind='notice'"
                           " ORDER BY id DESC LIMIT ?", (PINNED,)))
    both = pinned + rows
    authors = _authors([r["user_id"] for r in both])
    counts = _counts([r["id"] for r in both])
    return {"kind": kind, "page": page, "pages": pages, "total": total,
            "pinned": [_post_row(r, authors, uid, admin, now, counts) for r in pinned],
            "posts": [_post_row(r, authors, uid, admin, now, counts) for r in rows],
            "canNotice": admin,
            "limits": {"title": TITLE_MAX, "body": BODY_MAX, "comment": COMMENT_MAX}}


def _post(pid):
    return db.q1("SELECT * FROM board_post WHERE id=? AND deleted=0", (pid,))


def detail(user, pid, now=None):
    """글 하나와 댓글. 댓글은 [댓글 {…, replies: [답글…]}] 로 묶는다."""
    uid = user["id"]
    admin = is_admin(user)
    now = now or _now()
    r = _post(pid)
    if not r:
        raise LookupError("없는 글이거나 지워진 글입니다.")
    rows = list(db.q("SELECT * FROM board_comment WHERE post_id=? ORDER BY id", (pid,)))
    authors = _authors([r["user_id"]] + [c["user_id"] for c in rows])
    post = _post_row(r, authors, uid, admin, now, _counts([pid]))
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
    db.run("UPDATE board_post SET deleted=1 WHERE id=?", (pid,))


def comment(user, pid, body, parent=None, now=None):
    if not _post(pid):
        raise LookupError("없는 글이거나 지워진 글입니다.")
    body = clean(body, COMMENT_MAX, "댓글")
    parent_id = None
    if parent:
        p = db.q1("SELECT id, post_id, parent_id, deleted FROM board_comment WHERE id=?",
                  (int(parent),))
        if not p or p["post_id"] != pid:
            raise LookupError("답글을 달 댓글이 없습니다.")
        # 답글에 다는 답글은 같은 댓글 아래에 나란히 붙인다 (한 단계까지)
        parent_id = p["parent_id"] or p["id"]
    if not is_admin(user):
        _throttle(user["id"], "board_comment", COMMENT_COOLDOWN, COMMENTS_PER_DAY, "댓글", now)
    cur = db.run("INSERT INTO board_comment (post_id, parent_id, user_id, author, body,"
                 " created_at) VALUES (?,?,?,?,?,?)",
                 (pid, parent_id, user["id"], user["username"], body, _iso(now)))
    return cur.lastrowid


def remove_comment(user, cid):
    c = db.q1("SELECT * FROM board_comment WHERE id=? AND deleted=0", (cid,))
    if not c:
        raise LookupError("없는 댓글이거나 지워진 댓글입니다.")
    if c["user_id"] != user["id"] and not is_admin(user):
        raise PermissionError("내가 쓴 댓글만 지울 수 있습니다.")
    db.run("UPDATE board_comment SET deleted=1 WHERE id=?", (cid,))
    return c["post_id"]


def me_card():
    """/api/me 에 싣는다: 가장 최근 공지의 번호. 화면이 '새 공지' 를 표시한다."""
    try:
        r = db.q1("SELECT MAX(id) m FROM board_post WHERE deleted=0 AND kind='notice'")
        return {"notice": int(r["m"] or 0)}
    except Exception:                                        # noqa: BLE001
        return {"notice": 0}
