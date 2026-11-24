# -*- coding: utf-8 -*-
"""뒷모습 도트 (/api/sprite/N?back=true, 2.5.8 - 게시판 #850 '내 포켓몬이 후면이 아니라 전면을 보고 있다').

    cd server && POKET_DB=/tmp/x.db POKET_SPRITE_DIR=/tmp/s python test_sprite_back.py

밖(PokeAPI · 쇼다운)으로는 나가지 않는다 - urlopen 을 가짜로 바꿔 어디를 물었는지만 본다.
  1. 받는 곳: 쇼다운 뒷모습 gif 먼저, 없으면 정지 뒷모습 png · 이로치는 back/shiny/ · 도트를 바꾼 종 · 쇼다운 메가는 제 뒷모습
  2. 받은 것은 b 가 붙은 이름으로 남고 다음에는 다시 안 받는다 · 응답에 X-Sprite-Back
  3. 어디에도 없으면 404 + '없음' 표시 (다시 안 받는다) · 끊겨서 못 받은 것은 표시하지 않는다
  4. 이로치 뒷모습이 없으면 보통 색 뒷모습
  5. 앞모습 요청은 예전 그대로 (X-Sprite-Back 없음 · 뒷모습 파일을 앞모습으로 주지 않는다)
"""
import io
import os
import sys
import tempfile
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="poket-sprite-back-")
os.environ.setdefault("POKET_DB", os.path.join(TMP, "t.db"))
os.environ.setdefault("POKET_POKEDEX", os.path.join(HERE, "data", "pokedex.json"))
os.environ["POKET_SPRITE_DIR"] = os.path.join(TMP, "sprites")

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def main():
    import urllib.request
    from fastapi import HTTPException
    from app import main as M
    from common import sprite_fix as SF

    asked, have, down = [], {}, set()

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(target, timeout=0):
        url = target if isinstance(target, str) else target.full_url
        asked.append(url)
        if url in down:
            raise urllib.error.URLError("끊김")
        if url in have:
            return Resp(have[url])
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
    real = urllib.request.urlopen
    urllib.request.urlopen = fake
    B = M.SPRITE_BASE
    try:
        urls = [u for u, _e in M._back_urls(25, False)]
        chk("1. 받는 곳: 쇼다운 뒷모습 gif -> 정지 뒷모습 png", urls == [B + "/other/showdown/back/25.gif", B + "/back/25.png"], urls)
        chk("   이로치는 back/shiny/", [u for u, _e in M._back_urls(25, True)][0] == B + "/other/showdown/back/shiny/25.gif")
        fixed = next(iter(SF.OVERRIDE))
        chk("   도트를 바꾼 종은 같은 판의 뒷모습 먼저", "/animated/back/%d.gif" % fixed in M._back_urls(fixed, False)[0][0],
            M._back_urls(fixed, False)[0])
        site = next(iter(SF.SITE))
        chk("   쇼다운에서 받는 메가는 ani-back/", M._back_urls(site, False)[0][0].startswith(SF.SITE_BASE + "/ani-back/"),
            M._back_urls(site, False)[0])

        have[B + "/other/showdown/back/25.gif"] = b"GIF-BACK-25"
        r = M.sprite(25, back=True)
        p = os.path.join(os.environ["POKET_SPRITE_DIR"], "0025b.gif")
        chk("2. 뒷모습을 받아 내려준다 (X-Sprite-Back · 확장자)", r.body == b"GIF-BACK-25" and r.headers.get("x-sprite-back") == "1"
            and r.headers.get("x-sprite-ext") == ".gif", dict(r.headers))
        chk("   b 가 붙은 이름으로 남는다", os.path.exists(p) and open(p, "rb").read() == b"GIF-BACK-25", os.listdir(os.path.dirname(p)))
        n = len(asked)
        M.sprite(25, back=True)
        chk("   다음에는 다시 안 받는다", len(asked) == n, asked[n:])

        n = len(asked)
        try:
            M.sprite(778, back=True)
            code = None
        except HTTPException as e:
            code = e.status_code
        none = os.path.join(os.environ["POKET_SPRITE_DIR"], "0778b.none")
        chk("3. 어디에도 없으면 404 · 두 곳을 다 물었다", code == 404 and len(asked) - n == 2, (code, asked[n:]))
        chk("   '없음' 표시를 남기고 다음에는 안 받는다", os.path.exists(none), os.listdir(os.path.dirname(none)))
        n = len(asked)
        try:
            M.sprite(778, back=True)
        except HTTPException:
            pass
        chk("   (다시 물어도 밖으로 안 나간다)", len(asked) == n, asked[n:])
        down.update(u for u, _e in M._back_urls(6, False))
        try:
            M.sprite(6, back=True)
            code = None
        except HTTPException as e:
            code = e.status_code
        chk("   끊겨서 못 받은 것은 표시하지 않는다 (다음에 다시 받아 본다)",
            code == 404 and not os.path.exists(os.path.join(os.environ["POKET_SPRITE_DIR"], "0006b.none")))

        have[B + "/other/showdown/back/1.gif"] = b"GIF-BACK-1"
        r = M.sprite(1, shiny=True, back=True)
        chk("4. 이로치 뒷모습이 없으면 보통 색 뒷모습", r.body == b"GIF-BACK-1" and r.headers.get("x-sprite-back") == "1", r.body)

        have[B + "/other/showdown/25.gif"] = b"GIF-FRONT-25"
        r = M.sprite(25)
        chk("5. 앞모습 요청은 예전 그대로 (X-Sprite-Back 없음)", r.body == b"GIF-FRONT-25" and "x-sprite-back" not in r.headers,
            dict(r.headers))
        chk("   앞모습 · 뒷모습 파일이 따로다", sorted(f for f in os.listdir(os.environ["POKET_SPRITE_DIR"]) if f.startswith("0025"))
            == ["0025.gif", "0025b.gif"], os.listdir(os.environ["POKET_SPRITE_DIR"]))
    finally:
        urllib.request.urlopen = real

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
