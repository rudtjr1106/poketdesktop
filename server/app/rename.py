# -*- coding: utf-8 -*-
"""닉네임 변경권 (2.1.1). 닉네임은 **로그인 아이디**이기도 하다 - 바꾸면 다음 수동 로그인부터 새 닉네임 + 같은 비밀번호.
세션(자동 로그인)은 user_id 로 묶여 있어 그대로 산다.

## 한 트랜잭션으로 고치는 줄 (2026-10-20 운영 DB 로 손수 바꿀 때와 같은 범위)

    users.username                  (UNIQUE COLLATE NOCASE - 동시에 같은 이름을 노리면 하나만 된다)
    board_post.author · board_comment.author   쓸 때 이름을 복사해 둔다 - 찾기(author LIKE)가 옛 이름에 걸리지 않게
    guild_chat.name                 길드 채팅 줄
    bag                             변경권 한 장 (같은 트랜잭션에서 뺀다 - 이름만 바뀌고 표가 남거나 그 반대가 없게)

지난 대전 · 레이드 · 시즌 결과 · 길드전 기록의 이름은 **그때의 이름**으로 둔다 (기록이다). 랭킹 · 친구 · 길드원 ·
마이페이지는 users 에서 그때그때 읽으므로 따로 고칠 것이 없다.

## 막는 것

  · 운영자(config.BOARD_ADMINS)는 바꿀 수 없다 - 운영자는 닉네임으로 정해진다. 바꾸면 권한을 잃고, 비워 둔 운영자
    이름을 남이 가져가면 그 사람이 운영자가 된다. 같은 까닭으로 운영자 이름 · '운영자' 같은 말이 든 이름도 막는다.
  · 규칙은 가입과 같다 (auth.check_username: 2~12자, 한글 · 영문 · 숫자 · _ - . · 공백 하나 - 대괄호는 길드 이름표처럼
    보여서 이미 막힌다). 지금과 똑같은 이름은 거절, 대소문자만 바꾸는 것은 된다.
"""
import re

from fastapi import HTTPException

from . import auth, config, db

TICKET = "RENAMETICKET"
# 운영진으로 보일 수 있는 이름. 한글 말은 들어 있으면 막고, 영어 말은 **낱말 하나로** 있을 때만 막는다
# ('GM철수' · 'admin_kim' 은 막고 'Sigma' · 'badminton' 은 둔다).
BANNED = ("운영자", "운영진", "관리자", "개발자", "포스크탑")
BANNED_EN = ("admin", "gm")


def check(uid, new_name):
    """바꿀 수 있으면 (새 이름, 지금 이름). 아니면 HTTPException."""
    name, err = auth.check_username(new_name)
    if err:
        raise HTTPException(400, err)
    row = db.q1("SELECT username FROM users WHERE id=?", (uid,))
    if not row:
        raise HTTPException(404, "계정이 없습니다.")
    old = row["username"]
    if old in config.BOARD_ADMINS:
        raise HTTPException(403, "운영자 계정은 닉네임을 바꿀 수 없습니다.")
    if name == old:
        raise HTTPException(400, "지금과 같은 닉네임입니다.")
    low = name.lower()
    if (low in set(a.lower() for a in config.BOARD_ADMINS if a) or any(b in low for b in BANNED)
            or set(re.findall(r"[a-z]+", low)) & set(BANNED_EN)):
        raise HTTPException(400, "쓸 수 없는 닉네임입니다.")
    if db.q1("SELECT 1 FROM users WHERE username=? AND id<>?", (name, uid)):
        raise HTTPException(409, "이미 쓰는 닉네임입니다.")
    return name, old


def apply(uid, new_name):
    """변경권 한 장을 쓰고 닉네임을 바꾼다. {"username", "old"} 를 돌려준다."""
    name, old = check(uid, new_name)
    conn = db.connect()
    try:
        cur = conn.execute("UPDATE bag SET count = count - 1 WHERE user_id=? AND item=? AND count >= 1",
                           (uid, TICKET))
        if cur.rowcount <= 0:
            raise HTTPException(400, "닉네임 변경권이 없습니다.")
        conn.execute("UPDATE users SET username=? WHERE id=?", (name, uid))
        conn.execute("UPDATE board_post SET author=? WHERE user_id=?", (name, uid))
        conn.execute("UPDATE board_comment SET author=? WHERE user_id=?", (name, uid))
        conn.execute("UPDATE guild_chat SET name=? WHERE user_id=?", (name, uid))
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()                                 # 열린 트랜잭션을 남기지 않는다 (쓰기 잠금, db.run 주석)
        except Exception:                                   # noqa: BLE001
            pass
        if isinstance(e, HTTPException):
            raise
        if "UNIQUE" in str(e).upper():                      # 그사이 누가 같은 이름으로 가입했다
            raise HTTPException(409, "이미 쓰는 닉네임입니다.")
        raise
    return {"username": name, "old": old}
