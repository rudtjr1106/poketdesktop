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

## 이미지 (버전 2)

글 하나에 IMG_MAX 장. 먼저 올리고(/api/board/images - 번호를 받는다) 글을 쓰거나 고칠 때 그 번호들을
붙인다. 올라온 그림은 **늘 다시 저장한다** - 사진 속 위치 정보(EXIF)·덧붙은 자료가 지워지고, 그림인 척하는
파일과 터무니없이 큰 그림(압축 폭탄)이 걸러진다. 긴 변은 IMG_SIDE 로 줄인다. 움직이는 GIF 는 작으면
(GIF_SIDE · GIF_FRAMES · GIF_OUT_MAX) 움직이는 채로 두고, 크면 첫 장만 남긴다.

그림은 DB 가 아니라 파일이다 (config.BOARD_IMG_DIR). 글을 지우면 그 글의 그림도 지운다. 올리고 글에 안 붙인
것은 하루 뒤 치운다 (그 사람이 다음에 올릴 때). 하루 IMG_PER_DAY 장까지 (운영자는 제한 없음).
보는 것은 로그인한 사람만 - 붙은 글이 지워졌으면 아무도 못 본다, 아직 안 붙은 것은 올린 사람만.
"""
import datetime
import io
import os
import threading

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
# 이미지 (위 '이미지')
IMG_MAX = 4                          # 글 하나에
IMG_BYTES_MAX = 8 * 1024 * 1024      # 올리는 원본 (휴대폰 사진도 들어오게)
IMG_SIDE = 1280                      # 저장할 때 긴 변
GIF_SIDE = 640                       # 움직이는 채로 두는 GIF 의 긴 변 · 프레임 · 저장 크기
GIF_FRAMES = 120
GIF_OUT_MAX = 4 * 1024 * 1024
IMG_PIXELS_MAX = 40000000            # 열기 전에 막는 가로x세로 (압축 폭탄) - 프레임마다 본다
ANIM_PIXELS_MAX = 30000000           # 움직이는 GIF 를 움직이는 채로 풀 때 프레임 전부의 칸 합 (넘으면 첫 장만)
IMG_PER_DAY = 40                     # 하루 올리기 시도 (실패한 것 · 나중에 지운 것도 센다)
ENCODE_AT_ONCE = 2                   # 동시에 푸는 그림 수 - 서버 하나가 배틀까지 다 맡는다
ENCODE_WAIT = 20                     # 자리가 안 나면 이만큼(초) 기다리다 503
ORPHAN_HOURS = 24                    # 글에 안 붙은 채 이만큼 지나면 치운다
MIME = {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif"}


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
    imgs = _img_counts([r["id"] for r in both])

    def row(r):
        out = _post_row(r, authors, uid, admin, now, counts, likes)
        out["images"] = imgs.get(r["id"], 0)
        return out
    return {"kind": kind, "page": page, "pages": pages, "total": total, "q": q,
            "pinned": [row(r) for r in pinned],
            "posts": [row(r) for r in rows],
            "canNotice": admin,
            "limits": {"title": TITLE_MAX, "body": BODY_MAX, "comment": COMMENT_MAX,
                       "search": SEARCH_MAX, "images": IMG_MAX, "imageBytes": IMG_BYTES_MAX}}


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
    post["images"] = [_img_view(i) for i in db.q(
        "SELECT * FROM board_image WHERE post_id=? ORDER BY pos, id", (pid,))]

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
def create(user, kind, title, body, now=None, images=None):
    if kind not in KINDS:
        raise ValueError("글의 종류를 알 수 없습니다.")
    if kind == "patch":
        raise PermissionError("패치노트는 새 버전이 나올 때 자동으로 올라옵니다.")
    if kind == "notice" and not is_admin(user):
        raise PermissionError("공지는 운영자만 쓸 수 있습니다.")
    title = clean(title, TITLE_MAX, "제목", one_line=True)
    body = clean(body, BODY_MAX, "내용")
    ids = _check_images(user["id"], images, None)
    if not is_admin(user):
        _throttle(user["id"], "board_post", POST_COOLDOWN, POSTS_PER_DAY, "글", now)
    cur = db.run("INSERT INTO board_post (kind, user_id, author, title, body, created_at)"
                 " VALUES (?,?,?,?,?,?)",
                 (kind, user["id"], user["username"], title, body, _iso(now)))
    pid = cur.lastrowid
    if ids:
        _attach(user["id"], pid, ids)
    return pid


def edit(user, pid, title, body, now=None, images=None):
    """images 가 None 이면 그림은 그대로 둔다 (그림 칸을 모르는 옛 앱). 목록이면 그대로 바꾼다 - 빠진 것은 지운다."""
    r = _post(pid)
    if not r:
        raise LookupError("없는 글이거나 지워진 글입니다.")
    if r["user_id"] != user["id"]:
        raise PermissionError("내가 쓴 글만 고칠 수 있습니다.")
    if r["kind"] == "patch":
        raise PermissionError("패치노트는 고칠 수 없습니다.")
    title = clean(title, TITLE_MAX, "제목", one_line=True)
    body = clean(body, BODY_MAX, "내용")
    ids = _check_images(user["id"], images, pid) if images is not None else None
    db.run("UPDATE board_post SET title=?, body=?, updated_at=? WHERE id=?",
           (title, body, _iso(now), pid))
    if ids is not None:
        _attach(user["id"], pid, ids)
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
    for r in db.q("SELECT * FROM board_image WHERE post_id=?", (pid,)):
        _drop_image(r)                        # 글을 지우면 그림도 (올린 사람이 지운 것을 남겨 두지 않는다)


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
    """버전마다 패치노트 글 하나 (너무 긴 판은 둘 - patchnotes.as_posts). 없는 것만 올린다. 올린 버전 목록을 돌려준다.

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
        put = False
        # 나눠 올리는 판(2.0.0)은 (2) 를 먼저 넣는다 - 목록이 새 글부터라 (1) 이 위에 온다.
        for tail, title, body in reversed(patchnotes.as_posts(ver)):
            ref = "patch:" + ver + tail
            if ref in have:
                continue
            db.run("INSERT INTO board_post (kind, user_id, author, title, body, created_at, ref)"
                   " VALUES ('patch',?,?,?,?,?,?)",
                   (admin["id"], admin["username"], title, body, _patch_time(ver, now), ref))
            put = True
        if put:
            made.append(ver)
    return made


# ---------------------------------------------------------------- 이미지 (버전 2)
def img_dir():
    d = config.BOARD_IMG_DIR
    os.makedirs(d, exist_ok=True)
    return d


def _img_path(row):
    return os.path.join(img_dir(), "%d.%s" % (int(row["id"]), row["fmt"]))


def _img_view(r):
    return {"id": r["id"], "w": r["w"], "h": r["h"], "fmt": r["fmt"], "frames": r["frames"]}


def _img_counts(ids):
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    return dict((r["post_id"], r["c"]) for r in db.q(
        "SELECT post_id, COUNT(*) c FROM board_image WHERE post_id IN (%s) GROUP BY post_id" % marks,
        tuple(ids)))


def _drop_image(r):
    """줄과 파일을 지운다. 파일이 이미 없어도 그만이다."""
    db.run("DELETE FROM board_image WHERE id=?", (r["id"],))
    try:
        os.remove(_img_path(r))
    except OSError:
        pass


def _sweep_images(now=None, limit=50):
    """글에 안 붙인 채 ORPHAN_HOURS 가 지난 그림을 치운다 (누구의 것이든 - 다시 안 올리는 사람 것도). 한 번에 limit 개."""
    cut = ((now or _now()) - datetime.timedelta(hours=ORPHAN_HOURS)).replace(microsecond=0).isoformat()
    for r in db.q("SELECT * FROM board_image WHERE post_id IS NULL AND created_at < ? ORDER BY id LIMIT ?",
                  (cut, int(limit))):
        _drop_image(r)
    db.run("DELETE FROM board_upload WHERE created_at < ?",
           (((now or _now()) - datetime.timedelta(days=2)).replace(microsecond=0).isoformat(),))


def drop_user_images(uid):
    """계정을 지울 때 - 그 사람이 올린 그림 줄과 파일을 다 지운다 (글은 users 와 함께 지워진다)."""
    for r in db.q("SELECT * FROM board_image WHERE user_id=?", (uid,)):
        _drop_image(r)
    db.run("DELETE FROM board_upload WHERE user_id=?", (uid,))


def encode_image(raw):
    """올라온 바이트 -> (저장할 바이트, 형식, 폭, 높이, 프레임 수). 그림이 아니면 ValueError.

    **늘 다시 저장한다.** 그대로 두면 휴대폰 사진의 위치 정보(EXIF)가 남에게 그대로 간다.
    """
    from PIL import Image, ImageOps
    bad = ValueError("이미지 파일이 아니거나 열 수 없는 형식입니다. (PNG · JPG · GIF · WEBP)")
    try:
        probe = Image.open(io.BytesIO(raw))
        # MPO = 요즘 폰 사진 (JPEG 뒤에 HDR · 미리보기 그림이 붙었다). 첫 장만 쓴다.
        fmt_in = (probe.format or "").upper()
        if fmt_in not in ("PNG", "JPEG", "MPO", "GIF", "WEBP", "BMP"):
            raise bad
        # 크기는 머리만 읽고 본다 - 풀기 전에 막아야 압축 폭탄이 메모리를 먹지 않는다
        _too_big(probe.size)
        probe.verify()                                   # 깨진 파일
        im = Image.open(io.BytesIO(raw))
        if fmt_in == "GIF":
            # 프레임 수와 크기는 파일 구조만 읽고 센다 (Pillow 로 넘기면 앞 프레임을 다 풀어 버린다)
            frames, cw, ch = gif_scan(raw)
            _too_big((cw, ch))
            if 1 < frames <= GIF_FRAMES and frames * cw * ch <= ANIM_PIXELS_MAX:
                got = _animated(im, Image)
                if got:
                    return got
        im.seek(0)
        _too_big(im.size)                                # 첫 프레임이 화면보다 크게 적혀 있을 수 있다
        if fmt_in in ("JPEG", "MPO"):
            # 큰 사진은 줄여서 푼다 (1/2 · 1/4 · 1/8) - 5천만 화소도 가볍게
            im.draft("RGB", (IMG_SIDE, IMG_SIDE))
        im = ImageOps.exif_transpose(im)                 # 휴대폰 사진의 돌린 방향을 그림에 반영
        alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
        im = im.convert("RGBA" if alpha else "RGB")
        if max(im.size) > IMG_SIDE:
            im.thumbnail((IMG_SIDE, IMG_SIDE), Image.LANCZOS)
        out = io.BytesIO()
        if alpha or fmt_in in ("PNG", "GIF", "BMP"):
            im.save(out, "PNG", optimize=True)
            fmt = "png"
            if not alpha and out.tell() > 2500000:       # 큰 사진을 PNG 로 받았다 - JPG 가 훨씬 작다
                out = io.BytesIO()
                im.save(out, "JPEG", quality=88, optimize=True)
                fmt = "jpg"
        else:
            im.save(out, "JPEG", quality=88, optimize=True)
            fmt = "jpg"
        return out.getvalue(), fmt, im.width, im.height, 1
    except ValueError:
        raise
    except Exception:                                    # noqa: BLE001 - PIL 은 갖가지 오류를 낸다
        raise bad


def _too_big(size):
    w, h = size
    if w < 1 or h < 1 or w * h > IMG_PIXELS_MAX:
        raise ValueError("이미지가 너무 큽니다 (%d x %d)." % (w, h))


def gif_scan(raw):
    """GIF 를 풀지 않고 (프레임 수, 그림판 폭, 높이) 를 센다. 그림판 = 화면 크기와 프레임마다 적힌 끝자리 가운데 큰 것.

    **프레임마다 끝자리를 본다.** 화면 크기(맨 앞 머리)는 1x1 인데 뒤 프레임을 12000x12000 으로 적으면 Pillow 가
    그 프레임을 풀 때 그림을 키운다 - 앞의 검사를 지나 메모리 2GB 를 먹었다 (10/30 검토). Pillow 로 프레임을
    넘기며 크기를 보면 앞 프레임을 다 풀어서 그것만으로 CPU 를 먹는다 - 그래서 블록을 직접 건너뛴다.
    GIF_FRAMES 를 넘으면 거기서 센다를 멈춘다 (움직이는 채로 두지 않으니 더 셀 까닭이 없다).
    """
    bad = ValueError("이미지 파일이 아니거나 열 수 없는 형식입니다. (PNG · JPG · GIF · WEBP)")
    n = len(raw)
    if n < 13 or raw[:3] != b"GIF":
        raise bad
    cw, ch = raw[6] | raw[7] << 8, raw[8] | raw[9] << 8
    flags = raw[10]
    i = 13 + (3 * (2 << (flags & 7)) if flags & 0x80 else 0)

    def skip_sub(i):
        while True:
            if i >= n:
                raise bad
            size = raw[i]
            i += 1
            if size == 0:
                return i
            i += size

    frames = 0
    while i < n:
        b = raw[i]
        if b == 0x3B:                                    # 끝
            break
        if b == 0x21:                                    # 덧붙임 블록
            i = skip_sub(i + 2)
            continue
        if b != 0x2C or i + 10 > n:                      # 그림 블록이 아니면 깨진 파일
            raise bad
        x, y = raw[i + 1] | raw[i + 2] << 8, raw[i + 3] | raw[i + 4] << 8
        w, h = raw[i + 5] | raw[i + 6] << 8, raw[i + 7] | raw[i + 8] << 8
        lflags = raw[i + 9]
        cw, ch = max(cw, x + w), max(ch, y + h)
        i += 10 + (3 * (2 << (lflags & 7)) if lflags & 0x80 else 0)
        i = skip_sub(i + 1)                              # LZW 첫 길이 한 칸 + 자료 덩어리
        frames += 1
        if frames > GIF_FRAMES:
            break
    return frames, cw, ch


def _animated(im, Image):
    """움직이는 GIF 를 움직이는 채로 다시 저장한다. 너무 크면 None (첫 장만 남긴다)."""
    from PIL import ImageSequence
    frames, durs = [], []
    for fr in ImageSequence.Iterator(im):
        _too_big(fr.size)
        f = fr.convert("RGBA")
        f.info.clear()                                   # 설명 글(comment) 같은 덧붙은 자료를 옮기지 않는다
        if max(f.size) > GIF_SIDE:
            k = GIF_SIDE / float(max(f.size))
            f = f.resize((max(1, int(f.width * k)), max(1, int(f.height * k))), Image.NEAREST)
        frames.append(f)
        durs.append(max(20, int(fr.info.get("duration", 100) or 100)))
    out = io.BytesIO()
    frames[0].save(out, "GIF", save_all=True, append_images=frames[1:], duration=durs, loop=0, disposal=2)
    if out.tell() > GIF_OUT_MAX:
        return None
    return out.getvalue(), "gif", frames[0].width, frames[0].height, len(frames)


_encode_slots = threading.BoundedSemaphore(ENCODE_AT_ONCE)


def upload_image(user, raw, now=None):
    """그림 하나를 올린다 (아직 글에 안 붙었다). {id, w, h, fmt, frames}"""
    uid = user["id"]
    now = now or _now()
    if not raw:
        raise ValueError("이미지가 비어 있습니다.")
    if len(raw) > IMG_BYTES_MAX:
        raise ValueError("이미지는 한 장에 %dMB 까지 올릴 수 있습니다." % (IMG_BYTES_MAX // (1024 * 1024)))
    _sweep_images(now)
    if not is_admin(user):
        # 푸는 **앞에** 시도를 적는다 - 실패한 것 · 나중에 지운 것도 세고, 셈과 적기가 한 문장이라 동시에 보내도
        # 한도를 못 넘는다.
        since = (now - datetime.timedelta(days=1)).replace(microsecond=0).isoformat()
        cur = db.run("INSERT INTO board_upload (user_id, created_at) SELECT ?, ?"
                     " WHERE (SELECT COUNT(*) FROM board_upload WHERE user_id=? AND created_at > ?) < ?",
                     (uid, _iso(now), uid, since, IMG_PER_DAY))
        if getattr(cur, "rowcount", 1) == 0:
            raise PermissionError("하루에 올릴 수 있는 이미지 수(%d장)를 넘었습니다." % IMG_PER_DAY)
    if not _encode_slots.acquire(timeout=ENCODE_WAIT):
        raise RuntimeError("이미지를 올리는 사람이 많습니다. 잠시 후 다시 올려 주세요.")
    try:
        data, fmt, w, h, frames = encode_image(raw)
    finally:
        _encode_slots.release()
    cur = db.run("INSERT INTO board_image (user_id, fmt, w, h, bytes, frames, created_at) VALUES (?,?,?,?,?,?,?)",
                 (uid, fmt, w, h, len(data), frames, _iso(now)))
    row = {"id": cur.lastrowid, "fmt": fmt, "w": w, "h": h, "frames": frames}
    path = _img_path(row)
    try:
        with open(path + ".part", "wb") as f:
            f.write(data)
        os.replace(path + ".part", path)
    except OSError:
        db.run("DELETE FROM board_image WHERE id=?", (row["id"],))
        raise RuntimeError("이미지를 저장하지 못했습니다. 잠시 후 다시 올려 주세요.")
    return _img_view(row)


def _check_images(uid, images, pid):
    """글에 붙일 그림 번호들을 다듬고 본다 (붙이기 전에 - 글이 반쯤 써지는 일이 없게). [번호]"""
    ids = []
    for i in images or []:
        try:
            i = int(i)
        except (TypeError, ValueError):
            raise ValueError("이미지 번호를 알 수 없습니다.")
        if i not in ids:
            ids.append(i)
    if len(ids) > IMG_MAX:
        raise ValueError("이미지는 글 하나에 %d장까지 붙일 수 있습니다." % IMG_MAX)
    if ids:
        marks = ",".join("?" * len(ids))
        rows = dict((r["id"], r) for r in db.q("SELECT * FROM board_image WHERE id IN (%s)" % marks, tuple(ids)))
        for i in ids:
            r = rows.get(i)
            if not r or r["user_id"] != uid or (r["post_id"] is not None and r["post_id"] != pid):
                raise ValueError("붙일 수 없는 이미지가 있습니다. 다시 올려 주세요.")
    return ids


def _attach(uid, pid, ids):
    """그림 번호들을 이 글에 이 차례로 붙인다. 이 글에 붙어 있던 것 가운데 빠진 것은 지운다."""
    for r in db.q("SELECT * FROM board_image WHERE post_id=?", (pid,)):
        if r["id"] not in ids:
            _drop_image(r)
    for pos, i in enumerate(ids):
        cur = db.run("UPDATE board_image SET post_id=?, pos=? WHERE id=? AND user_id=?"
                     " AND (post_id IS NULL OR post_id=?)", (pid, pos, i, uid, pid))
        if getattr(cur, "rowcount", 1) == 0:
            raise ValueError("붙일 수 없는 이미지가 있습니다. 다시 올려 주세요.")


def image_file(user, iid):
    """보여 줄 그림 파일 (경로, MIME). 붙은 글이 살아 있으면 누구나, 아직 안 붙었으면 올린 사람만."""
    r = db.q1("SELECT * FROM board_image WHERE id=?", (int(iid),))
    if not r:
        raise LookupError("없는 이미지입니다.")
    if r["post_id"] is None:
        if r["user_id"] != user["id"] and not is_admin(user):
            raise LookupError("없는 이미지입니다.")
    elif not _post(r["post_id"]):
        raise LookupError("지워진 글의 이미지입니다.")
    path = _img_path(r)
    if not os.path.exists(path):
        raise LookupError("이미지 파일이 없습니다.")
    return path, MIME.get(r["fmt"], "application/octet-stream")
