# -*- coding: utf-8 -*-
"""포켓몬 관리 창: 여러 마리 골라 한 번에 놓아주기.

    python client/test_box_release_many.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 (smoke_box_filter 의 가짜 api - 규칙은 서버와 같다: 한 마리씩
따로 보고 막힌 것은 까닭과 함께. 서버 쪽은 server/test_release_many.py 가 본다).

  1. 여러 마리 고르기(1.10.6 의 고름 그대로)에 '놓아주기 (N마리)' 단추가 있고, 고른 수를 따라간다.
  2. 누르면 확인 창 한 번: 몇 마리 · 이름 전부 · 경고 모음(숨은 특성 · 이로치 · 지닌 도구 · 탐험 중이라 빠짐).
     **한 마리 확인 창의 숨은 특성 경고가 빠지지 않는다.** 취소하면 아무 일도 없다.
  3. 확인하면 서버에 한 번. 놓아준 것은 목록과 고름에서 빠지고, 막힌 것은 고름에 남고 까닭이 적힌다.
  4. 옛 서버(그 길이 없다)면 한 마리씩 release 로 보낸다.
  5. 가장 작은 창에서도 고르기 단추 다섯이 다 보인다. 이름이 많아도 확인 창은 화면을 넘지 않는다(목록만 굴러간다).
  6. 201마리 넘게 고르면 200마리씩 나눠 보내고 결과를 합친다. 옛 서버로 한 마리씩 보내도 도구 이야기·막힌 수가 산다.
  7. 요청이 도는 동안 고르기 단추가 잠기고, 두 번 눌러도 요청은 한 번. 오류로 끝나도 목록·바탕화면을 맞추고
     고름에서 이미 사라진 것은 뺀다.
"""
import json
import os
import sys
import tempfile
import threading

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-boxrelease-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_box                             # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
import smoke_box_filter as SB                               # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402

OK = FAIL = 0
DATA = os.path.join(os.path.dirname(HERE), "server", "data")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def labels(w):
    return " ".join(str(x.cget("text")) for x in SB._walk(w) if isinstance(x, tk.Label))


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda *a: errors.append(str(a[1]))

    party = [SB.mon(dex, 7, 5001, on=True)]
    box = []
    for i, n in enumerate([25, 129, 6, 143, 3, 94, 130, 59, 65, 150]):
        m = SB.mon(dex, n, 6000 + i)
        m["box"] = 0
        box.append(m)
    box[1]["info"] = dict(box[1]["info"], ability="자기과신", hiddenAbility=True)   # 잉어킹 - 숨은 특성
    box[1]["hiddenAbility"] = True
    box[2]["shiny"] = True                                                          # 리자몽 - 이로치
    box[3]["held"], box[3]["heldKr"] = "LEFTOVERS", "먹다남은음식"                   # 잠만보 - 도구
    box[4]["away"] = True                                                           # 이상해꽃 - 탐험 중
    app = SB.FakeApp(root, dex, party + box)
    api = app.api
    win = ui_box.BoxWindow(root, app)
    win.win.geometry("990x668+20+20")
    SB.wait_for(root, lambda: getattr(win, "mons", None))
    SB.settle_rows(root, win)
    ids = [m["id"] for m in box]

    print("=== 확인 창에 적을 것 (창 없이) ===")
    head, rows, warns = ui_box.release_many_text(box[:4], [box[4]])
    w = " / ".join(warns)
    chk("몇 마리인지", head == "4마리를 놓아줄까요?", head)
    chk("이름 전부 (Lv 와 함께, 고른 차례대로)", [r[0] for r in rows] == ["%s  Lv.20" % m["info"]["name"] for m in box[:4]], rows)
    chk("**숨은 특성 경고가 빠지지 않는다** (어느 포켓몬의 어떤 특성인지)", "숨은 특성" in w and "자기과신" in w
        and box[1]["info"]["name"] in w and rows[1][1] == "숨은 특성", (w, rows[1]))
    chk("이로치도 알린다", "이로치" in w and box[2]["info"]["name"] in w and rows[2][1] == "이로치", w)
    chk("지닌 도구는 가방으로 돌아간다고", "먹다남은음식" in w and "가방" in w and rows[3][1] == "도구", w)
    chk("탐험 중인 것은 빼고 놓아준다고", "탐험" in w and box[4]["info"]["name"] in w, w)
    _h, _r, w2 = ui_box.release_many_text(box[5:7])
    chk("걸릴 것이 없으면 경고도 없다", w2 == [] and all(not r[1] for r in _r), w2)

    print("\n=== 고르기 단추 ===")
    win.enter_multi()
    SB.settle(root)
    chk("고르기를 켜면 '놓아주기 (0마리)' 가 잠긴 채 있다", win.btn_multi_release.label.cget("text") == "놓아주기 (0마리)"
        and not win.btn_multi_release.enabled and win.btn_multi_release.holder.winfo_ismapped())
    chk("  고르는 법 글이 놓아주기도 말한다", "놓아줄" in win.status.cget("text"), win.status.cget("text"))
    for i in ids[:6]:
        win.toggle_check(i)
    SB.settle(root)
    chk("고른 수를 따라간다", win.btn_multi_release.label.cget("text") == "놓아주기 (6마리)" and win.btn_multi_release.enabled)

    print("\n=== 확인 창 ===")
    asked = []
    real = ui_box.confirm_release_many

    def cancel(parent, mons, away=()):
        asked.append(([m["id"] for m in mons], [m["id"] for m in away]))
        return False
    ui_box.confirm_release_many = cancel
    n_calls = len(api.calls)
    win.release_checked()
    SB.settle(root)
    chk("한 번 묻는다: 탐험 중인 것은 빼서 넘긴다", asked == [(ids[:4] + [ids[5]], [ids[4]])], asked)
    chk("  취소하면 서버에 안 가고 고름도 그대로", len(api.calls) == n_calls and win.checked == set(ids[:6]))

    # 진짜 창을 띄워 글자와 크기를 본다 (화면 안에서 띄우고 없앤다)
    seen = {}

    def look():
        t = [x for x in root.winfo_children() if isinstance(x, tk.Toplevel) and x is not win.win][-1]
        t.update_idletasks()
        seen["t"] = labels(t)
        seen["bad"] = squeezed(t)
        seen["h"] = t.winfo_height()
        t.destroy()
    root.after(300, look)
    v = real(root, box[:4], [box[4]])
    chk("진짜 창: 몇 마리 · 이름 · 숨은 특성 · 이로치 · 되돌릴 수 없다", v is False and "4마리를 놓아줄까요?" in seen.get("t", "")
        and "자기과신" in seen["t"] and "이로치" in seen["t"] and "되돌릴 수 없습니다" in seen["t"]
        and box[0]["info"]["name"] in seen["t"], seen.get("t"))
    chk("  눌린 글자가 없다", not seen.get("bad"), seen.get("bad") and seen["bad"][:3])
    lots = [SB.mon(dex, 10 + i, 9000 + i) for i in range(120)]
    seen.clear()
    root.after(300, look)
    real(root, lots)
    chk("  120마리여도 창은 키우지 않는다 (목록만 굴러간다, 단추가 보인다)", 0 < seen.get("h", 0) <= U.h(560) + 4
        and "120마리 놓아주기" in seen.get("t", "") and not seen.get("bad"), (seen.get("h"), U.h(560)))

    print("\n=== 놓아준다 ===")
    api.busy = {ids[5]}                               # 그사이 배틀을 걸었다 - 서버가 막는다
    ui_box.confirm_release_many = lambda parent, mons, away=(): True
    try:
        win.release_checked()
        SB.wait_for(root, lambda: "보내주었습니다" in win.status.cget("text") and win._wait is None)
        SB.settle_rows(root, win)
    finally:
        ui_box.confirm_release_many = real
    sent = [c for c in api.calls if c[0] == "release"]
    left = set(m["id"] for m in api.mons)
    chk("**서버에 한 번** (탐험 중인 것은 안 보낸다)", sent == [("release", ids[:4] + [ids[5]])], sent)
    chk("  놓아준 것은 목록에서 사라진다", not (set(ids[:4]) & left) and not any(i in win.rows and i in SB.shown(win) for i in ids[:4]),
        SB.shown(win))
    chk("  막힌 것(배틀 중)·뺀 것(탐험 중)은 고름에 남는다", win.checked == {ids[4], ids[5]} and win.multi, win.checked)
    chk("  바닥에 몇 마리 · 막힌 까닭", "4마리를 보내주었습니다" in win.status.cget("text")
        and "배틀 중" in win.status.cget("text"), win.status.cget("text"))
    chk("  바탕화면도 맞춘다 (request_sync)", app.synced >= 1)
    asked = []
    ui_box.confirm_release_many = cancel
    win.clear_checks()
    win.toggle_check(ids[4])
    win.release_checked()
    ui_box.confirm_release_many = real
    chk("고른 것이 다 탐험 중이면 묻지 않고 까닭만 말한다", "탐험" in win.status.cget("text") and asked == [],
        (win.status.cget("text"), asked))

    print("\n=== 옛 서버 (한꺼번에 놓아주는 길이 없다) ===")
    from poketdesktop import api as A
    a = A.Api("http://x")
    got = []

    def old_server(method, path, body=None, **_kw):
        got.append((method, path))
        if path.endswith("/release-many"):
            raise A.ApiError("Method Not Allowed", 405)
        if path.endswith("/4"):
            raise A.ApiError("탐험에 나가 있는 포켓몬은 놓아줄 수 없습니다. 돌아온 뒤에 해 주세요.", 409)
        return {"ok": True}
    a._call = old_server
    r = a.release_many([3, 4, 5])
    chk("그 길이 없으면 한 마리씩 놓아준다 (같은 모양으로 돌려준다)",
        got[1:] == [("DELETE", "/api/pokemon/%d" % i) for i in (3, 4, 5)]
        and [x["id"] for x in r["released"]] == [3, 5] and r["failed"][0]["id"] == 4
        and "탐험" in r["failed"][0]["reason"], (got, r))

    def new_server(method, path, body=None, **_kw):
        got.append((method, path))
        raise A.ApiError("놓아줄 포켓몬을 골라 주세요.", 400)
    a._call = new_server
    del got[:]
    try:
        a.release_many([])
        chk("새 서버가 거절한 것은 한 마리씩 다시 보내지 않는다", False, got)
    except A.ApiError as e:
        chk("새 서버가 거절한 것은 한 마리씩 다시 보내지 않는다 (까닭을 그대로 올린다)", len(got) == 1 and e.status == 400, got)

    # 옛 서버: 다 막히면 '한 마리도' + 몇 마리, 한 마리 길의 글에서 도구 이야기를 건진다
    def old_all_fail(method, path, body=None, **_kw):
        if path.endswith("/release-many"):
            raise A.ApiError("Not Found", 404)
        raise A.ApiError("탐험에 나가 있는 포켓몬은 놓아줄 수 없습니다. 돌아온 뒤에 해 주세요.", 409)
    a._call = old_all_fail
    r = a.release_many([3, 4])
    chk("옛 서버에서 다 막히면 '한 마리도 놓아주지 못했습니다' + 막힌 수", r["released"] == []
        and r["message"].startswith("한 마리도 놓아주지 못했습니다.") and "2마리" in r["message"], r["message"])

    def old_held(method, path, body=None, **_kw):
        if path.endswith("/release-many"):
            raise A.ApiError("Method Not Allowed", 405)
        if path.endswith("/3"):
            return {"ok": True, "message": "잠만보 을(를) 보내주었습니다. 지니고 있던 먹다남은음식은(는) 가방에 넣었습니다."}
        return {"ok": True, "message": "피카츄 을(를) 보내주었습니다."}
    a._call = old_held
    r = a.release_many([3, 5])
    chk("  옛 서버여도 지닌 도구가 가방으로 갔다고 알린다", r["heldToBag"] == ["먹다남은음식"]
        and "먹다남은음식" in r["message"] and "가방" in r["message"] and "2마리를 보내주었습니다" in r["message"], r)

    print("\n=== 200마리 넘게 ===")
    sizes = []

    def chunky(method, path, body=None, **_kw):
        chunk = list(body["ids"])
        sizes.append(len(chunk))
        # 서버처럼 200마리까지만 받는다. 3의 배수 번호는 막혔다고 친다, 도구는 첫 마리만
        assert len(chunk) <= 200, len(chunk)
        done = [{"id": i} for i in chunk if i % 3]
        failed = [{"id": i, "reason": "배틀 중"} for i in chunk if not i % 3]
        return {"ok": True, "released": done, "failed": failed,
                "heldToBag": ["먹다남은음식"] if 1 in chunk else [], "message": "덩어리 글"}
    a._call = chunky
    many = list(range(1, 451))
    r = a.release_many(many)
    chk("450마리는 200·200·50 으로 나눠 보낸다", sizes == [200, 200, 50], sizes)
    chk("  결과를 하나로 합친다 (놓아준 것·막힌 것·도구)", len(r["released"]) == 300 and len(r["failed"]) == 150
        and r["heldToBag"] == ["먹다남은음식"], (len(r["released"]), len(r["failed"])))
    chk("  알림 글도 전체 수로", "300마리를 보내주었습니다" in r["message"] and "150마리는 못 보냈습니다" in r["message"]
        and "도구 1개" in r["message"], r["message"])
    del sizes[:]
    r = a.release_many(list(range(1, 201)))
    chk("  200마리면 한 번에, 서버 글 그대로", sizes == [200] and r["message"] == "덩어리 글", (sizes, r["message"]))
    _h, _r, _w = ui_box.release_many_text([SB.mon(dex, 10 + i % 100, 20000 + i) for i in range(230)])
    chk("  확인 창 머리말은 전체 수 그대로", _h == "230마리를 놓아줄까요?", _h)

    print("\n=== 두 번 누르기 · 도는 동안 잠금 ===")
    gate = threading.Event()
    real_rm = api.release_many
    sent = []

    def slow(ids_):
        sent.append(list(ids_))
        gate.wait(5)
        return real_rm(ids_)
    api.release_many = slow
    api.busy = set()
    win.clear_checks()
    win.toggle_check(ids[6])
    win.toggle_check(ids[7])
    ui_box.confirm_release_many = lambda parent, mons, away=(): True
    try:
        win.release_checked()
        SB.settle(root)
        locked = [not b.enabled for b in (win.btn_multi_release, win.btn_multi_move, win.btn_multi_all,
                                         win.btn_multi_clear, win.btn_multi_done)]
        chk("도는 동안 고르기 단추 다섯이 잠긴다", all(locked), locked)
        win.btn_multi_release._release(None)              # 잠긴 단추를 눌러 본다
        win.release_checked()                             # 단추를 거치지 않고 한 번 더
        SB.settle(root)
        chk("  두 번 눌러도 요청은 한 번", len(sent) == 1, sent)
        gate.set()
        SB.wait_for(root, lambda: not win._releasing and win._wait is None and "보내주었습니다" in win.status.cget("text"))
        SB.settle_rows(root, win)
    finally:
        gate.set()
        ui_box.confirm_release_many = real
    chk("  답이 오면 풀린다 (고른 것이 없으니 놓아주기만 잠긴 채)", len(sent) == 1 and win.btn_multi_all.enabled
        and win.btn_multi_done.enabled and not win.btn_multi_release.enabled and win.checked == set(), win.checked)

    print("\n=== 오류로 끝나도 맞춘다 ===")

    def cut(ids_):
        real_rm(ids_[:1])                                 # 첫 마리는 놓아진 뒤 연결이 끊겼다
        raise A.ApiError("서버에 연결할 수 없습니다.", 0)
    api.release_many = cut
    win.toggle_check(ids[8])
    win.toggle_check(ids[9])
    synced0 = app.synced
    ui_box.confirm_release_many = lambda parent, mons, away=(): True
    try:
        win.release_checked()
        SB.wait_for(root, lambda: not win._releasing and win._wait is None and "연결" in win.status.cget("text"))
        SB.settle_rows(root, win)
    finally:
        ui_box.confirm_release_many = real
        api.release_many = real_rm
    chk("오류여도 다시 불러오고 바탕화면도 맞춘다", app.synced > synced0 and "연결" in win.status.cget("text"),
        (app.synced, synced0, win.status.cget("text")))
    chk("  이미 사라진 것은 고름에서 빠지고, 남은 것은 고름에 남는다", win.checked == {ids[9]}
        and ids[8] not in SB.shown(win), win.checked)
    chk("  단추가 다시 풀린다", win.btn_multi_release.enabled and win.btn_multi_all.enabled)

    print("\n=== 가장 작은 창 ===")
    win.win.geometry("950x620")
    SB.settle(root, 20)
    win.check_all_shown()
    SB.settle(root, 20)
    kids = [b.holder for b in (win.btn_multi_move, win.btn_multi_release, win.btn_multi_all,
                               win.btn_multi_clear, win.btn_multi_done)]
    chk("고르기 단추 다섯이 제 크기로 다 보인다 (눌리지 않는다)",
        all(k.winfo_ismapped() and k.winfo_height() >= k.winfo_reqheight() and k.winfo_width() >= k.winfo_reqwidth()
            for k in kids) and kids[-1].winfo_rootx() + kids[-1].winfo_width() <= win.win.winfo_rootx() + win.win.winfo_width(),
        [(k.winfo_width(), k.winfo_reqwidth()) for k in kids])
    chk("  바닥 줄에 눌린 위젯이 없다", not squeezed(win.status.master), squeezed(win.status.master)[:3])
    win.exit_multi()
    win.close()
    SB.settle(root)
    chk("도는 동안 오류 없음", not errors, errors[:2])
    root.destroy()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
