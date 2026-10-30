# -*- coding: utf-8 -*-
"""게시판 이미지 (버전 2, board.py 의 '이미지'). 서버를 띄우지 않는다.

    python server/test_board_images.py

못 박는 것:

  1. 다시 저장: 사진의 위치 정보(EXIF)가 지워진다 · 투명은 PNG, 사진은 JPG · 긴 변 1280 으로 줄인다 ·
     휴대폰 사진의 돌린 방향이 그림에 반영된다 · 작은 움직이는 GIF 는 움직이는 채로, 큰 것은 줄여서.
  2. 거른다: 그림이 아닌 파일 · 깨진 파일 · 압축 폭탄(머리만 보고 거른다) · 8MB 넘는 원본 · 하루 40장.
  3. 붙이기: 글 하나에 4장 · 남의 그림 · 다른 글에 붙은 그림은 못 붙인다 · 고칠 때 목록대로 바뀌고 빠진 것은
     파일까지 지운다 · 옛 앱(images 없음)이 고치면 그대로 · 목록에 수 · 글에 차례대로.
  4. 보기: 안 붙은 것은 올린 사람만 · 붙은 것은 누구나 · 글을 지우면 아무도 못 보고 파일도 없어진다 ·
     하루 넘게 안 붙은 것은 치운다.
  5. 길: base64 가 아니면 400 · 너무 크면 413 · 파일을 그대로 돌려준다.
  6. (10/30 검토) 뒤 프레임을 크게 적은 GIF 폭탄은 풀기 전에 거른다 · 큰 프레임이 많은 GIF 는 첫 장만 (빠르게) ·
     폰 사진(MPO) · 움직이는 GIF 의 설명 글을 지운다 · 실패한 시도도 하루 한도에 든다 · 지운 그림으로 한도가
     돌아오지 않는다 · 안 붙은 그림은 다른 사람이 올릴 때도 치운다 · 계정을 지우면 그림 파일도.
"""
import datetime
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-board-img-")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ["POKET_BOARD_IMG_DIR"] = os.path.join(TMP, "img")
os.environ.pop("POKET_TURSO_URL", None)
os.environ.pop("POKET_BOARD_ADMINS", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")

import base64                                                # noqa: E402

from fastapi import HTTPException                            # noqa: E402
from PIL import Image                                        # noqa: E402

from app import board, board_routes, db                      # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def err(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except (ValueError, PermissionError, LookupError) as e:
        return type(e).__name__, str(e)
    except HTTPException as e:
        return e.status_code, e.detail
    return None


def mkuser(name):
    uid = db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, created_at) VALUES (?,?,?,1,'')",
                 (name, b"x", b"x")).lastrowid
    return {"id": uid, "username": name}


def png(w=40, h=30, alpha=True):
    im = Image.new("RGBA" if alpha else "RGB", (w, h), (255, 0, 0, 128) if alpha else (0, 120, 255))
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def jpg_with_gps(w=300, h=200, orient=None):
    im = Image.new("RGB", (w, h), (10, 200, 30))
    ex = Image.Exif()
    ex[0x8825] = {2: (37.0, 33.0, 1.0)}              # GPSInfo - 위도
    ex[0x010F] = "PhoneMaker"                         # Make
    if orient:
        ex[0x0112] = orient
    out = io.BytesIO()
    im.save(out, "JPEG", exif=ex.tobytes())
    return out.getvalue()


def gif(frames=4, side=32):
    fs = [Image.new("RGB", (side, side), (i * 60, 0, 255 - i * 60)) for i in range(frames)]
    out = io.BytesIO()
    fs[0].save(out, "GIF", save_all=True, append_images=fs[1:], duration=90, loop=0)
    return out.getvalue()


def reopen(data):
    return Image.open(io.BytesIO(data))


def files():
    d = os.environ["POKET_BOARD_IMG_DIR"]
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


def main():
    db.init()
    a, b = mkuser("그림쟁이"), mkuser("구경꾼")

    print("=== 1. 다시 저장 ===")
    data, fmt, w, h, n = board.encode_image(png())
    chk("투명이 있으면 PNG", fmt == "png" and reopen(data).mode in ("RGBA", "P") and (w, h) == (40, 30), (fmt, w, h))
    raw = jpg_with_gps()
    chk("  (준비: 원본에 위치 정보가 있다)", 0x8825 in reopen(raw).getexif())
    data, fmt, w, h, n = board.encode_image(raw)
    ex = reopen(data).getexif()
    chk("사진은 JPG · 위치 정보 · 기기 이름이 지워진다", fmt == "jpg" and 0x8825 not in ex and 0x010F not in ex, dict(ex))
    data, fmt, w, h, n = board.encode_image(jpg_with_gps(300, 200, orient=6))
    chk("돌려 찍은 사진은 그림을 돌려 저장 (300x200 -> 200x300)", (w, h) == (200, 300), (w, h))
    data, fmt, w, h, n = board.encode_image(png(3000, 1500, alpha=False))
    chk("긴 변 1280 으로 줄인다 (3000x1500 -> 1280x640)", (w, h) == (1280, 640) and reopen(data).size == (1280, 640),
        (w, h))
    data, fmt, w, h, n = board.encode_image(gif(5))
    chk("작은 움직이는 GIF 는 움직이는 채로 (5프레임)", fmt == "gif" and n == 5
        and getattr(reopen(data), "n_frames", 1) == 5, (fmt, n))
    data, fmt, w, h, n = board.encode_image(gif(3, side=900))
    chk("큰 움직이는 GIF 는 640 으로 줄여서 움직이는 채로", fmt == "gif" and max(w, h) == 640 and n == 3, (fmt, w, h, n))

    print("\n=== 2. 거른다 ===")
    chk("그림이 아닌 파일", err(board.encode_image, b"hello, not an image")[0] == "ValueError")
    chk("깨진 PNG", err(board.encode_image, png()[:40])[0] == "ValueError")
    bomb = io.BytesIO()
    Image.new("1", (7000, 7000)).save(bomb, "PNG")          # 4900만 칸 - 압축하면 작다
    e = err(board.encode_image, bomb.getvalue())
    chk("압축 폭탄은 머리만 보고 거른다", e and e[0] == "ValueError" and "너무 큽니다" in e[1], e)
    e = err(board.upload_image, a, b"x" * (board.IMG_BYTES_MAX + 1))
    chk("8MB 넘는 원본", e and "8MB" in e[1], e)
    real = board.IMG_PER_DAY
    board.IMG_PER_DAY = 2
    try:
        x1 = board.upload_image(b, png())
        x2 = board.upload_image(b, png())
        e = err(board.upload_image, b, png())
        chk("하루 한도 (검사용 2장)", x1["id"] and x2["id"] and e and e[0] == "PermissionError", e)
    finally:
        board.IMG_PER_DAY = real

    print("\n=== 3. 붙이기 ===")
    up = [board.upload_image(a, png(20 + i, 20)) for i in range(5)]
    chk("올리면 번호 · 크기 · 파일", all(u["id"] for u in up) and len(files()) >= 5 and up[0]["w"] == 20)
    e = err(board.create, a, "free", "제목", "내용", images=[u["id"] for u in up])
    chk("글 하나에 4장까지", e and "4장" in e[1], e)
    e = err(board.create, b, "free", "남의 그림", "내용", images=[up[0]["id"]])
    chk("남의 그림은 못 붙인다", e and e[0] == "ValueError", e)
    pid = board.create(a, "free", "그림 글", "내용", images=[up[2]["id"], up[0]["id"], up[1]["id"]])
    d = board.detail(a, pid)
    chk("글에 차례대로 붙는다", [i["id"] for i in d["images"]] == [up[2]["id"], up[0]["id"], up[1]["id"]]
        and d["images"][0]["w"] == 22, d["images"])
    lst = board.listing(a, "all")
    row = [p for p in lst["posts"] if p["id"] == pid][0]
    chk("목록에 이미지 수 · 한도", row["images"] == 3 and lst["limits"]["images"] == 4, row.get("images"))
    board._now = lambda: datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=40)
    try:
        e = err(board.create, a, "free", "두 번째", "내용", images=[up[0]["id"]])
        chk("다른 글에 붙은 그림은 못 붙인다", e and e[0] == "ValueError", e)
    finally:
        board._now = lambda: datetime.datetime.now(datetime.timezone.utc)
    gone = board._img_path({"id": up[0]["id"], "fmt": "png"})
    board.edit(a, pid, "그림 글", "내용", images=[up[1]["id"], up[3]["id"]])
    d = board.detail(a, pid)
    chk("고치면 목록대로 · 빠진 것은 파일까지 지운다", [i["id"] for i in d["images"]] == [up[1]["id"], up[3]["id"]]
        and not os.path.exists(gone), [i["id"] for i in d["images"]])
    board.edit(a, pid, "그림 글", "내용 고침")
    chk("옛 앱이 고치면(images 없음) 그대로", len(board.detail(a, pid)["images"]) == 2)

    print("\n=== 4. 보기 ===")
    e = err(board.image_file, b, up[4]["id"])
    chk("안 붙은 그림은 남이 못 본다", e and e[0] == "LookupError", e)
    chk("  올린 사람은 본다 (글 쓰기 전 미리보기)", board.image_file(a, up[4]["id"])[1] == "image/png")
    path, mime = board.image_file(b, up[1]["id"])
    chk("붙은 그림은 누구나", os.path.exists(path) and mime == "image/png")
    files_of = [board._img_path({"id": i, "fmt": "png"}) for i in (up[1]["id"], up[3]["id"])]
    board.remove(a, pid)
    chk("글을 지우면 아무도 못 보고 파일도 없다", err(board.image_file, a, up[1]["id"])
        and not any(os.path.exists(f) for f in files_of))
    old = board.upload_image(a, png())
    db.run("UPDATE board_image SET created_at=? WHERE id=?", ("2000-01-01T00:00:00+00:00", old["id"]))
    board.upload_image(a, png())
    chk("하루 넘게 안 붙은 것은 다음에 올릴 때 치운다", not db.q1("SELECT 1 FROM board_image WHERE id=?", (old["id"],))
        and not os.path.exists(board._img_path({"id": old["id"], "fmt": "png"})))

    print("\n=== 5. 길 ===")
    ctx = {"user": b}                         # a 는 방금 글을 써서 30초 막혀 있다
    e = err(board_routes.upload_image, board_routes.ImageIn(data="!!!not base64!!!"), ctx=ctx)
    chk("base64 가 아니면 400", e and e[0] == 400, e)
    e = err(board_routes.upload_image, board_routes.ImageIn(data="A" * (board.IMG_BYTES_MAX * 4 // 3 + 100)), ctx=ctx)
    chk("너무 크면 413", e and e[0] == 413, e)
    r = board_routes.upload_image(board_routes.ImageIn(data=base64.b64encode(gif(3)).decode()), ctx=ctx)
    chk("올리기 응답 {id, w, h, fmt, frames}", r["fmt"] == "gif" and r["frames"] == 3 and r["w"] == 32, r)
    resp = board_routes.image(r["id"], ctx=ctx)
    chk("파일을 그대로 · 캐시 머리글", resp.media_type == "image/gif" and resp.body[:3] == b"GIF"
        and "max-age" in resp.headers.get("cache-control", ""), resp.media_type)
    p2 = board_routes.create(board_routes.PostIn(kind="free", title="길로 쓴 글", body="내용", images=[r["id"]]),
                             ctx=ctx)
    chk("글 쓰기 길에 images", [i["id"] for i in p2["images"]] == [r["id"]], p2.get("images"))

    print("\n=== 6. 검토가 잡은 것 (10/30) ===")
    import time
    small = io.BytesIO()
    Image.new("P", (1, 1), 0).save(small, "GIF")
    sm = small.getvalue()
    big = io.BytesIO()
    Image.new("P", (9000, 9000), 0).save(big, "GIF")
    bg = big.getvalue()
    blk = bg[bg.index(b"\x2c"):-1]
    bomb_gif = sm[:-1] + b"\x21\xf9\x04\x00\x0a\x00\x00\x00" + blk + b"\x3b"
    chk("  (준비: 화면은 1x1 이라고 적힌 GIF)", Image.open(io.BytesIO(bomb_gif)).size == (1, 1))
    t = time.time()
    e = err(board.encode_image, bomb_gif)
    chk("뒤 프레임을 크게 적은 GIF 폭탄은 풀기 전에 거른다", e and "너무 큽니다" in e[1] and time.time() - t < 1.0, e)
    many = io.BytesIO()
    fs = [Image.new("P", (2000, 2000), k % 2) for k in range(20)]
    fs[0].save(many, "GIF", save_all=True, append_images=fs[1:], duration=50)
    t = time.time()
    data, fmt, w, h, n = board.encode_image(many.getvalue())
    chk("큰 프레임이 많은 GIF 는 첫 장만 (빠르게)", n == 1 and fmt == "png" and time.time() - t < 5.0,
        (fmt, n, round(time.time() - t, 2)))
    mpo = io.BytesIO()
    Image.new("RGB", (80, 60), (200, 10, 10)).save(mpo, "MPO", save_all=True,
                                                     append_images=[Image.new("RGB", (80, 60))])
    chk("  (준비: MPO 로 열린다)", Image.open(io.BytesIO(mpo.getvalue())).format == "MPO")
    data, fmt, w, h, n = board.encode_image(mpo.getvalue())
    chk("폰 사진(MPO)도 받는다 - JPG 로", fmt == "jpg" and (w, h) == (80, 60), (fmt, w, h))
    cm = io.BytesIO()
    fs = [Image.new("RGB", (16, 16), (k * 80, 0, 0)) for k in range(3)]
    fs[0].save(cm, "GIF", save_all=True, append_images=fs[1:], duration=80, comment=b"home 37.5N 127.0E")
    data, fmt, w, h, n = board.encode_image(cm.getvalue())
    chk("움직이는 GIF 의 설명 글을 지운다", fmt == "gif" and n == 3 and b"37.5N" not in data, (fmt, n))
    c = mkuser("한도시험")
    real = board.IMG_PER_DAY
    board.IMG_PER_DAY = 3
    try:
        for _ in range(2):
            err(board.upload_image, c, b"not an image")
        ok1 = board.upload_image(c, png())
        e = err(board.upload_image, c, png())
        chk("실패한 시도도 하루 한도에 든다 (실패 둘 + 성공 하나 = 셋)", ok1["id"] and e and e[0] == "PermissionError", e)
        db.run("DELETE FROM board_upload WHERE user_id=?", (c["id"],))
        x = board.upload_image(c, png())
        board._drop_image(db.q1("SELECT * FROM board_image WHERE id=?", (x["id"],)))
        board.upload_image(c, png())
        board.upload_image(c, png())
        e = err(board.upload_image, c, png())
        chk("지운 그림으로 한도가 돌아오지 않는다", e and e[0] == "PermissionError", e)
    finally:
        board.IMG_PER_DAY = real
    lone = board.upload_image(mkuser("안올림"), png())
    db.run("UPDATE board_image SET created_at=? WHERE id=?", ("2000-01-01T00:00:00+00:00", lone["id"]))
    board.upload_image(b, png())
    chk("안 붙은 그림은 다른 사람이 올릴 때도 치운다", not db.q1("SELECT 1 FROM board_image WHERE id=?", (lone["id"],)))
    gone_user = mkuser("탈퇴")
    g1 = board.upload_image(gone_user, png())
    board.drop_user_images(gone_user["id"])
    chk("계정을 지우면 그림 줄과 파일도", not db.q1("SELECT 1 FROM board_image WHERE id=?", (g1["id"],))
        and not os.path.exists(board._img_path({"id": g1["id"], "fmt": "png"})))
    import inspect
    from app import main as M
    chk("  계정 지우기 길이 drop_user_images 를 부른다", "drop_user_images" in inspect.getsource(M.delete_account))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
