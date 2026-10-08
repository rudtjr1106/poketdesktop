# -*- coding: utf-8 -*-
"""캐릭터 (1.10.3) — 마이페이지에서 만드는 내 캐릭터.

    GET  /api/avatar          내 캐릭터. 아직 안 만들었으면 avatar 가 None 이다
    PUT  /api/avatar          고른 것(spec)을 저장한다
    POST /api/avatar/image    직접 그린 도트를 쓸지 말지 (넣어 둔 도트가 있는 사람만)

**화면은 그림을 올리지 못한다. 고른 것만 보낸다.** 화면이 그림을 올리게 두면 남에게 보일 그림을
아무나 아무렇게나 올릴 수 있다. 캐릭터는 common/avatar_art 가 그린다 - 서버도 화면도 같은
코드라, 고른 것(머리 모양·옷·색 ...)만 오가면 어느 쪽에서든 같은 그림이 나온다.

받은 것은 믿지 않는다: 아는 열쇠·아는 값만 남기고 나머지는 기본값으로 채워 저장한다
(avatar_art.clean). 그래서 저장된 것은 언제나 그릴 수 있다.

## 직접 그린 도트

자기가 그린 도트를 쓰고 싶은 사람은 규격(common/avatar_sheet, docs/avatar/)대로 그린 PNG 를
운영자에게 보내고, **운영자가 넣어 준다** (avatar_tool.py - 서버 안에서만 돌릴 수 있다).
넣을 때 규격을 검사하고 우리 방식의 PNG 로 다시 써서 둔다. 넣어 둔 도트가 있는 사람은 그것과
꾸민 캐릭터 사이를 오갈 수 있다 (image_on). 꾸미기 창에서 저장하면 꾸민 캐릭터로 돌아가지만
넣어 둔 도트는 지워지지 않는다.

남에게는 마이페이지 카드(mypage.card)에 실려 나간다 - 길드원 프로필이 그 카드를 쓴다.
"""
import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common import avatar_art, avatar_sheet

from . import db, deps

router = APIRouter()


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def public(uid):
    """그 사람의 캐릭터. 안 만들었으면 None.

        {"spec": 고른 것, "image": 직접 그린 도트(쓰는 중일 때만) 또는 None,
         "hasImage": 넣어 둔 도트가 있나, "updatedAt": ...}
    """
    r = db.q1("SELECT spec, updated_at, image, image_on FROM avatar WHERE user_id=?", (uid,))
    if not r:
        return None
    try:
        spec = json.loads(r["spec"] or "{}")
    except ValueError:
        spec = {}
    has = bool(r["image"])
    # 저장할 때 이미 걸렀지만, 부위를 빼거나 이름을 바꾼 뒤의 옛 저장분도 그릴 수 있어야 한다.
    return {"spec": avatar_art.clean(spec), "image": r["image"] if (has and r["image_on"]) else None,
            "hasImage": has, "updatedAt": r["updated_at"]}


def save(uid, spec):
    """고른 것을 저장한다. 걸러서 저장한 것을 돌려준다.

    **꾸민 캐릭터를 쓰겠다는 뜻이다** - 직접 그린 도트를 쓰고 있었으면 꺼 둔다 (지우지는 않는다).
    """
    spec = avatar_art.clean(spec)
    text = json.dumps(spec, ensure_ascii=False, sort_keys=True)
    at = _now()
    if db.q1("SELECT 1 x FROM avatar WHERE user_id=?", (uid,)):
        db.run("UPDATE avatar SET spec=?, updated_at=?, image_on=0 WHERE user_id=?", (text, at, uid))
    else:
        db.run("INSERT INTO avatar (user_id, spec, updated_at) VALUES (?,?,?)", (uid, text, at))
    return public(uid)


def set_image(uid, data):
    """직접 그린 도트를 넣는다 (운영자가 avatar_tool 로 부른다). data = PNG bytes.

    규격에 안 맞으면 avatar_sheet.SheetError. 넣으면 바로 그 도트가 보인다.
    (캐릭터, 알릴 것 목록) 을 돌려준다.
    """
    sheet, notes = avatar_sheet.read(data)
    text, at = avatar_sheet.pack(sheet), _now()
    if db.q1("SELECT 1 x FROM avatar WHERE user_id=?", (uid,)):
        db.run("UPDATE avatar SET image=?, image_on=1, updated_at=? WHERE user_id=?", (text, at, uid))
    else:
        spec = json.dumps(dict(avatar_art.DEFAULT), ensure_ascii=False, sort_keys=True)
        db.run("INSERT INTO avatar (user_id, spec, updated_at, image, image_on) VALUES (?,?,?,?,1)",
               (uid, spec, at, text))
    return public(uid), notes


def clear_image(uid):
    """넣어 둔 도트를 지운다. 지웠으면 True."""
    cur = db.run("UPDATE avatar SET image=NULL, image_on=0, updated_at=? WHERE user_id=? AND image IS NOT NULL",
                 (_now(), uid))
    return bool(cur.rowcount)


def use_image(uid, on):
    """넣어 둔 도트를 쓸지 말지. 넣어 둔 것이 없으면 404."""
    r = db.q1("SELECT image FROM avatar WHERE user_id=?", (uid,))
    if not r or not r["image"]:
        raise HTTPException(404, "넣어 둔 도트가 없습니다. 직접 그린 도트는 운영자에게 보내면 넣어 드립니다.")
    db.run("UPDATE avatar SET image_on=?, updated_at=? WHERE user_id=?", (1 if on else 0, _now(), uid))
    return public(uid)


class AvatarIn(BaseModel):
    spec: dict = {}


class ImageIn(BaseModel):
    on: bool = True


@router.get("/api/avatar")
def mine(ctx=Depends(deps.current)):
    return {"avatar": public(ctx["user"]["id"])}


@router.put("/api/avatar")
def put(body: AvatarIn, ctx=Depends(deps.current)):
    return {"ok": True, "avatar": save(ctx["user"]["id"], body.spec),
            "message": "캐릭터를 저장했습니다."}


@router.post("/api/avatar/image")
def image(body: ImageIn, ctx=Depends(deps.current)):
    av = use_image(ctx["user"]["id"], body.on)
    return {"ok": True, "avatar": av,
            "message": "직접 그린 도트를 씁니다." if body.on else "꾸민 캐릭터를 씁니다."}
