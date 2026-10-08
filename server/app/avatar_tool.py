# -*- coding: utf-8 -*-
"""직접 그린 캐릭터 도트를 넣는 운영자 도구 (1.10.3).

**서버 안에서만 돌린다.** 화면에서 그림을 올리는 길은 일부러 만들지 않았다 (avatar.py).

    python -m app.avatar_tool set   <닉네임> < sheet.png     넣는다 (규격을 검사한다)
    python -m app.avatar_tool show  <닉네임>                 지금 무엇을 쓰고 있나
    python -m app.avatar_tool clear <닉네임>                 넣어 둔 도트를 지운다 (꾸민 캐릭터로 돌아간다)
    python -m app.avatar_tool check < sheet.png              넣지 않고 규격만 본다

운영 서버에서는 컨테이너 안에서:

    ssh ... 'docker exec -i poketdesktop-server python -m app.avatar_tool set 닉네임' < sheet.png

규격은 common/avatar_sheet.py 와 docs/avatar/ 의 안내서에 있다.
"""
import sys

from common import avatar_sheet

from . import avatar, db


def _user(name):
    r = db.q1("SELECT id, username FROM users WHERE username=?", (name,))
    if not r:
        raise SystemExit("그런 닉네임이 없습니다: %s" % name)
    return r["id"], r["username"]


def main(argv=None, stdin=None, out=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    out = out or sys.stdout
    say = lambda text: out.write(text + "\n")                # noqa: E731
    cmd = argv[0] if argv else ""
    if cmd == "check":
        data = (stdin or sys.stdin.buffer).read()
        try:
            _sheet, notes = avatar_sheet.read(data)
        except avatar_sheet.SheetError as e:
            say("규격에 맞지 않습니다: %s" % e)
            return 1
        say("규격에 맞습니다.")
        for n in notes:
            say("  참고: %s" % n)
        return 0
    if cmd not in ("set", "show", "clear") or len(argv) < 2:
        say((__doc__ or "").strip())
        return 2
    db.init()
    uid, name = _user(argv[1])
    if cmd == "show":
        av = avatar.public(uid)
        if not av:
            say("%s: 캐릭터를 아직 만들지 않았습니다." % name)
        else:
            say("%s: %s 쓰는 중 (넣어 둔 도트 %s)" % (
                name, "직접 그린 도트를" if av["image"] else "꾸민 캐릭터를",
                "있음" if av["hasImage"] else "없음"))
        return 0
    if cmd == "clear":
        say("%s: %s" % (name, "넣어 둔 도트를 지웠습니다." if avatar.clear_image(uid) else "넣어 둔 도트가 없습니다."))
        return 0
    data = (stdin or sys.stdin.buffer).read()
    try:
        _av, notes = avatar.set_image(uid, data)
    except avatar_sheet.SheetError as e:
        say("넣지 않았습니다. 규격에 맞지 않습니다: %s" % e)
        return 1
    say("%s: 직접 그린 도트를 넣었습니다. 지금부터 마이페이지와 길드원 프로필에 이 도트가 보입니다." % name)
    for n in notes:
        say("  참고: %s" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
