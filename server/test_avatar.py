# -*- coding: utf-8 -*-
"""캐릭터 저장 검사 (1.10.3).

    python server/test_avatar.py

서버를 띄우지 않고 app.avatar 의 함수를 직접 부른다.

무엇을 못 박나:
  1. 안 만든 사람은 None 이다 (기본 캐릭터를 지어내 주지 않는다 - 화면이 '만들기' 를 보여 줘야 한다).
  2. 저장하면 그대로 읽힌다. 다시 저장하면 덮어쓴다 (한 사람에 하나).
  3. **보내온 것은 믿지 않는다**: 모르는 열쇠·값은 저장되지 않는다. 저장된 것은 언제나 그릴 수 있다.
  4. 마이페이지 카드에 실린다 - 내 것은 내 카드에, 남의 것은 남의 카드에.
  5. 계정이 지워지면 캐릭터도 지워진다.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-avatar-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

from app import avatar, db, deps, main, mypage              # noqa: E402
from common import avatar_art, avatar_sheet                  # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def mkuser(name):
    cur = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
                 " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'2026-09-23T03:00:00+00:00','','')",
                 (name, b"x", b"x"))
    return {"id": cur.lastrowid, "username": name}


def ctx(user):
    return {"user": user, "session": {}, "token": "t"}


def main_():
    db.init()
    dex = deps.dex()
    me, other = mkuser("주인공"), mkuser("남")
    uid = me["id"]

    print("=== 안 만든 사람 ===")
    chk("없으면 None", avatar.public(uid) is None)
    chk("GET /api/avatar 도 None 을 준다", avatar.mine(ctx(me)) == {"avatar": None})
    chk("마이페이지 카드에도 None", mypage.card(uid, dex)["avatar"] is None)

    print("\n=== 저장 ===")
    pick = dict(avatar_art.DEFAULT, hair="pony", hairColor="pink", hat="beanie", hatColor="red",
                glasses="round", top="hoodie", topColor="green", bottom="skirt", shoes="boots", bag="satchel",
                skin="tan")
    out = avatar.put(avatar.AvatarIn(spec=pick), ctx(me))
    chk("저장하면 고른 것이 그대로 돌아온다", out["ok"] and out["avatar"]["spec"] == pick, out)
    got = avatar.public(uid)
    chk("다시 읽어도 같다", got and got["spec"] == pick and got["updatedAt"] and got["image"] is None
        and got["hasImage"] is False, got)
    chk("읽은 것으로 그림이 그려진다 (96x128 걷기 시트)", len(avatar_art.walk_sheet(got["spec"])) == 128)
    again = dict(pick, hair="bun", top="jacket")
    avatar.save(uid, again)
    n = db.q1("SELECT COUNT(*) c FROM avatar WHERE user_id=?", (uid,))["c"]
    chk("다시 저장하면 덮어쓴다 (한 사람에 하나)", n == 1 and avatar.public(uid)["spec"] == again, n)

    print("\n=== 보내온 것은 믿지 않는다 ===")
    avatar.save(uid, {"hair": "<script>", "top": "hoodie", "hairColor": ["x"], "zzz": "x" * 5000, "skin": 7})
    raw = db.q1("SELECT spec FROM avatar WHERE user_id=?", (uid,))["spec"]
    stored = json.loads(raw)
    chk("모르는 열쇠는 저장되지 않는다", set(stored) == set(avatar_art.DEFAULT), sorted(set(stored) ^ set(avatar_art.DEFAULT)))
    chk("모르는 값은 기본값이 된다, 아는 값은 남는다", stored["hair"] == avatar_art.DEFAULT["hair"]
        and stored["top"] == "hoodie" and stored["skin"] == avatar_art.DEFAULT["skin"], stored)
    chk("저장되는 글은 작다 (500자 안쪽)", len(raw) < 500, len(raw))
    for junk in (None, [], "문자열", 3, {"spec": {"hair": "pony"}}):
        avatar.save(uid, junk)
    chk("이상한 것을 넣어도 기본 캐릭터가 저장될 뿐이다", avatar.public(uid)["spec"] == avatar_art.DEFAULT)
    try:
        avatar.AvatarIn(spec="문자열")
        bad = False
    except Exception:                                           # noqa: BLE001
        bad = True
    chk("spec 이 사전이 아니면 요청부터 걸러진다 (422)", bad)
    chk("spec 없이 보내면 기본 캐릭터", avatar.put(avatar.AvatarIn(), ctx(me))["avatar"]["spec"] == avatar_art.DEFAULT)

    print("\n=== 옛 저장분 ===")
    db.run("UPDATE avatar SET spec=? WHERE user_id=?", ('{"hair":"없어진머리","top":"tank"}', uid))
    got = avatar.public(uid)
    chk("부위가 없어진 뒤의 저장분도 그릴 수 있게 읽힌다", got["spec"]["hair"] == avatar_art.DEFAULT["hair"]
        and got["spec"]["top"] == "tank" and set(got["spec"]) == set(avatar_art.DEFAULT), got)
    db.run("UPDATE avatar SET spec=? WHERE user_id=?", ("깨진 글", uid))
    chk("깨진 저장분은 기본 캐릭터로 읽힌다 (터지지 않는다)", avatar.public(uid)["spec"] == avatar_art.DEFAULT)

    print("\n=== 마이페이지 카드 ===")
    avatar.save(uid, pick)
    mine = mypage.build(me, dex)
    chk("내 마이페이지에 실린다", mine["avatar"] and mine["avatar"]["spec"] == pick, mine.get("avatar"))
    chk("남의 카드에는 남의 것이 (안 만들었으면 None)", mypage.card(other["id"], dex)["avatar"] is None)
    avatar.save(other["id"], dict(avatar_art.DEFAULT, hat="cap"))
    chk("  만들면 그 사람 카드에 그 사람 것", mypage.card(other["id"], dex)["avatar"]["spec"]["hat"] == "cap"
        and mypage.card(uid, dex)["avatar"]["spec"] == pick)

    print("\n=== 경로 ===")
    api = main.app.openapi()["paths"].get("/api/avatar") or {}
    chk("GET·PUT /api/avatar 가 붙어 있다", sorted(api) == ["get", "put"], sorted(api))

    print("\n=== 직접 그린 도트 (운영자가 넣어 준다) ===")
    art = mkuser("그림쟁이")["id"]
    sheet = avatar_art.walk_sheet(dict(avatar_art.DEFAULT, hair="twin", hat="bucket", top="jacket"))
    png = avatar_art.png(sheet)
    chk("화면이 그림을 올리는 길은 없다 (경로는 켜고 끄기뿐)", sorted(main.app.openapi()["paths"].get("/api/avatar/image") or {}) == ["post"]
        and "image" not in avatar.AvatarIn.model_fields)
    e = None
    try:
        avatar.use_image(art, True)
    except Exception as ex:                                     # noqa: BLE001
        e = getattr(ex, "status_code", None)
    chk("넣어 둔 도트가 없으면 켤 수 없다 (404)", e == 404)
    av, notes = avatar.set_image(art, png)
    chk("넣으면 바로 그 도트가 보인다 (캐릭터를 안 만든 사람에게도)", av["image"] and av["hasImage"]
        and avatar_sheet.unpack(av["image"]) == sheet and notes == [] and av["spec"] == avatar_art.DEFAULT)
    chk("  마이페이지 카드에 실린다 (남이 보는 프로필에도)", mypage.card(art, dex)["avatar"]["image"] == av["image"])
    chk("  둔 것은 우리 방식으로 다시 쓴 PNG 다 (보내온 바이트를 그대로 두지 않는다)",
        db.q1("SELECT image FROM avatar WHERE user_id=?", (art,))["image"] == avatar_sheet.pack(sheet))
    bad = None
    try:
        avatar.set_image(art, avatar_art.png([row[:64] for row in sheet[:64]]))
    except avatar_sheet.SheetError as ex:
        bad = str(ex)
    chk("규격에 안 맞는 것은 넣지 않는다 (있던 도트는 그대로)", bad is not None and "96 x 128" in bad
        and avatar.public(art)["image"] == av["image"], bad)
    r = avatar.image(avatar.ImageIn(on=False), ctx({"id": art}))
    chk("끄면 꾸민 캐릭터가 보인다 - 넣어 둔 도트는 남아 있다", r["avatar"]["image"] is None and r["avatar"]["hasImage"]
        and "꾸민 캐릭터" in r["message"], r)
    r = avatar.image(avatar.ImageIn(), ctx({"id": art}))
    chk("다시 켤 수 있다", r["avatar"]["image"] == av["image"] and "직접 그린 도트" in r["message"])
    saved = avatar.save(art, dict(avatar_art.DEFAULT, hair="bun"))
    chk("꾸미기 창에서 저장하면 꾸민 캐릭터로 돌아간다 (도트는 지워지지 않는다)", saved["image"] is None
        and saved["hasImage"] and saved["spec"]["hair"] == "bun"
        and db.q1("SELECT image FROM avatar WHERE user_id=?", (art,))["image"] == av["image"])
    # 운영자 도구
    import io as _io
    from app import avatar_tool

    def tool(*argv, **kw):
        out = _io.StringIO()
        code = avatar_tool.main(list(argv), stdin=_io.BytesIO(kw.get("data", b"")), out=out)
        return code, out.getvalue()
    code, text = tool("check", data=png)
    chk("도구: 규격만 본다 (check)", code == 0 and "규격에 맞습니다" in text, text)
    code, text = tool("check", data=b"hello")
    chk("  안 맞으면 까닭을 말하고 1 로 끝난다", code == 1 and "PNG 파일이 아닙니다" in text, text)
    code, text = tool("show", "그림쟁이")
    chk("도구: 지금 무엇을 쓰나 (show)", code == 0 and "꾸민 캐릭터를 쓰는 중" in text and "있음" in text, text)
    code, text = tool("set", "그림쟁이", data=png)
    chk("도구: 넣는다 (set) - 닉네임으로", code == 0 and "넣었습니다" in text and avatar.public(art)["image"], text)
    code, text = tool("set", "그림쟁이", data=avatar_art.png(avatar_art.scale(sheet, 2)))
    chk("  규격에 안 맞으면 넣지 않는다", code == 1 and "넣지 않았습니다" in text and "192 x 256" in text, text)
    try:
        tool("set", "없는사람", data=png)
        missing = False
    except SystemExit as ex:
        missing = "그런 닉네임이 없습니다" in str(ex)
    chk("  없는 닉네임이면 멈춘다", missing)
    code, text = tool("clear", "그림쟁이")
    chk("도구: 지운다 (clear) - 꾸민 캐릭터로 돌아간다", code == 0 and avatar.public(art)["image"] is None
        and not avatar.public(art)["hasImage"] and avatar.public(art)["spec"]["hair"] == "bun", text)
    code, text = tool()
    chk("도구: 쓰는 법", code == 2 and "avatar_tool set" in text)

    print("\n=== 계정이 지워지면 ===")
    db.run("DELETE FROM users WHERE id=?", (other["id"],))
    chk("캐릭터도 같이 지워진다", db.q1("SELECT 1 x FROM avatar WHERE user_id=?", (other["id"],)) is None)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main_())
