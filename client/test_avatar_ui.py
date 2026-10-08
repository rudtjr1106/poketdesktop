# -*- coding: utf-8 -*-
"""캐릭터 만들기 화면 검사 (1.10.3).

    python client/test_avatar_ui.py

**창을 진짜로 띄운다.** 서버는 안 띄운다 - 가짜 api 가 PUT /api/avatar 와 같은 모양으로 답한다.

  1. 마이페이지의 닉네임 **왼쪽**에 캐릭터가 선다. 안 만든 사람에게는 그림자와 '캐릭터 만들기'.
  2. 꾸미기 창: 탭 여덟이 다 보이고, 미리보기(앞·옆·뒤)가 걷는다. 칸을 누르면 바로 바뀐다.
  3. 탭을 바꿔도 창 크기가 그대로다. 칸이 옆으로도 아래로도 넘치지 않는다 (글자를 줄이지 않고).
  4. 모자·안경·가방이 '없음' 이면 색 칸 대신 안내가 보인다.
  5. 무작위·되돌리기·초기화(기본 캐릭터로). 저장하면 서버에 **고른 것만** 가고, 마이페이지의 그림이 바뀐다.
  6. 저장에 실패하면 까닭이 보이고 창이 남는다. 취소하면 서버를 부르지 않는다.
  7. 직접 그린 도트를 넣어 둔 사람: 그 도트가 보이고, 꾸민 캐릭터와 오가는 단추가 있다.
"""
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-test-avatar-"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from common import avatar_art as A                          # noqa: E402
from common import avatar_sheet as SHEET                    # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_avatar as UA                    # noqa: E402
from poketdesktop import ui_mypage                          # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402
from test_mypage_ui import FakeApp, click, find, settle, wait   # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def press(btn):
    """PushButton 을 진짜 마우스처럼 누른다."""
    btn.label.event_generate("<ButtonPress-1>", x=3, y=3)
    btn.label.event_generate("<ButtonRelease-1>", x=3, y=3)


def gold(w):
    return str(w.cget("highlightbackground")) == U.ACCENT


def on_top(ed, tab):
    """겹쳐 둔 탭 가운데 맨 위에 올라와 있는 것이 그 탭인가 (winfo_children 은 아래부터 센다)."""
    return str(ed.inner.winfo_children()[-1]) == str(ed.pages[tab])


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    app = FakeApp(root)
    api = app.api
    api.saved = []
    api.save_fail = None

    def avatar_save(spec):
        if api.save_fail:
            raise RuntimeError(api.save_fail)
        api.saved.append(dict(spec))
        return {"ok": True, "avatar": {"spec": A.clean(spec), "updatedAt": "t"},
                "message": "캐릭터를 저장했습니다."}
    api.avatar_save = avatar_save

    print("=== 보류 중: 기본으로는 안 보인다 ===")
    from poketdesktop import ui_avatar as _UA
    chk("캐릭터는 보류 중이다 (광장을 접으면서 화면에서 숨겼다)", _UA.ENABLED is False)
    w0 = ui_mypage.MyPageWindow(app)
    w0.win.winfo_toplevel().deiconify()
    wait(root, lambda: w0.data is not None)
    settle(root)
    chk("  마이페이지에 캐릭터 그림도 '캐릭터 만들기' 단추도 없다", w0.av_art is None and w0.av_btn is None
        and not find(w0.win.winfo_toplevel(), "캐릭터 만들기"))
    w0.close()
    settle(root, 0.2)
    api.calls = 0                         # (위에서 한 번 받아 온 것은 세지 않는다)
    _UA.ENABLED = True                    # 아래는 **다시 켰을 때**의 동작이다 (코드는 그대로 남겨 두었다)

    print("\n=== 마이페이지: 아직 안 만든 사람 ===")
    w = ui_mypage.MyPageWindow(app)
    top = w.win.winfo_toplevel()
    top.deiconify()
    wait(root, lambda: w.data is not None)
    settle(root)
    name = find(top, "나여조경석")[0]
    chk("자리 그림이 96x96 으로 서 있다", w.av_art.winfo_ismapped() == 1 and w.av_art.winfo_width() >= 96
        and w.av_art.winfo_height() >= 96, (w.av_art.winfo_width(), w.av_art.winfo_height()))
    chk("닉네임의 **왼쪽**에 있다", w.av_art.winfo_rootx() + w.av_art.winfo_width() <= name.winfo_rootx(),
        (w.av_art.winfo_rootx(), w.av_art.winfo_width(), name.winfo_rootx()))
    chk("  같은 칸 안이다 (닉네임이 그림의 위아래 사이에 있다)", w.av_art.winfo_rooty() <= name.winfo_rooty()
        <= w.av_art.winfo_rooty() + w.av_art.winfo_height())
    chk("단추는 '캐릭터 만들기'", len(find(top, "캐릭터 만들기")) == 1 and not find(top, "캐릭터 바꾸기"))
    chk("나머지 내 정보는 그대로 보인다", any("함께한 지 25일째" in x and "48,200원" in x for x in texts(top))
        and "슈퍼볼" in texts(top))
    bad = squeezed(top)
    chk("눌린 위젯 없음", not bad, bad[:3])
    blank = str(w.av_art.cget("image"))

    print("\n=== 꾸미기 창 ===")
    click(w.av_art)
    settle(root, 0.5)
    ed = w.editor
    chk("그림을 누르면 창이 뜬다", ed is not None and ed.alive and ed.win.winfo_exists() == 1)
    chk("처음이면 제목은 '캐릭터 만들기'", ed.win.title() == "캐릭터 만들기", ed.win.title())
    chk("창 폭은 정해 둔 대로, 높이는 넘지 않는다", ed.win.winfo_width() == UA.W
        and ed.win.winfo_height() <= UA.MAX_H, (ed.win.winfo_width(), ed.win.winfo_height()))
    seg = ed.seg.frame
    chk("탭 여덟이 잘리지 않고 다 보인다", len(ed.seg.cells) == 8 and seg.winfo_width() >= seg.winfo_reqwidth()
        and seg.winfo_rootx() + seg.winfo_width() <= ed.win.winfo_rootx() + ed.win.winfo_width(),
        (seg.winfo_width(), seg.winfo_reqwidth()))
    chk("미리보기: 앞 128, 옆·뒤 64", (ed.big.winfo_width(), ed.side.winfo_width(), ed.rear.winfo_width())
        == (128, 64, 64), (ed.big.winfo_width(), ed.side.winfo_width(), ed.rear.winfo_width()))
    seen = set()
    for _ in range(8):
        seen.add(str(ed.big.cget("image")))
        settle(root, UA.STEP_MS / 1000.0)
    chk("미리보기가 걷는다 (왼발·서기·오른발)", len(seen) == 3, len(seen))
    chk("머리 탭부터 보인다", ed.tab == "hair" and ed.seg.current == "hair" and on_top(ed, "hair"))
    tiles = ed.tiles["hair"]
    chk("머리 13칸, 칸마다 그림(64)이 있다", len(tiles) == 13 and all(t[1].winfo_width() == 64 for t in tiles.values()),
        [t[1].winfo_width() for t in tiles.values()][:4])
    chk("지금 고른 칸에만 금테", [v for v, t in tiles.items() if gold(t[0])] == [A.DEFAULT["hair"]])
    chk("색 칸에도 지금 색에만 금테", [n for n, d in ed.dots["hair"].items() if gold(d)] == [A.DEFAULT["hairColor"]])
    chk("칸이 굴리지 않아도 다 보인다", ed.inner.winfo_reqheight() <= ed.cv.winfo_height() + 1,
        (ed.inner.winfo_reqheight(), ed.cv.winfo_height()))
    chk("처음에는 되돌릴 것이 없다 (단추가 꺼져 있다)", ed.undo_btn.enabled is False)
    chk("'초기화' 단추가 있다. 기본 캐릭터일 때는 꺼져 있다", len(find(ed.win, "초기화")) == 1
        and ed.reset_btn.enabled is False)
    chk("안내: 저장하면 어디에 보이는지", "닉네임 옆" in ed.note.cget("text"), ed.note.cget("text"))
    bad = squeezed(ed.win)
    chk("눌린 위젯 없음", not bad, bad[:3])

    print("\n=== 고르기 ===")
    before = str(ed.big.cget("image"))
    click(tiles["pony"][1])
    settle(root, 0.1)
    chk("칸을 누르면 바로 바뀐다", ed.model.spec["hair"] == "pony" and gold(tiles["pony"][0])
        and not gold(tiles[A.DEFAULT["hair"]][0]))
    chk("  미리보기 그림도 새로 그린다", str(ed.big.cget("image")) != before)
    click(ed.dots["hair"]["pink"])
    settle(root, 0.1)
    chk("색 칸을 누르면 색이 바뀐다", ed.model.spec["hairColor"] == "pink" and gold(ed.dots["hair"]["pink"])
        and not gold(ed.dots["hair"][A.DEFAULT["hairColor"]]))
    chk("되돌리기가 켜진다", ed.undo_btn.enabled is True)
    chk("초기화도 켜진다 (기본에서 벗어났다)", ed.reset_btn.enabled is True)

    print("\n=== 탭 ===")
    size0 = (ed.win.winfo_width(), ed.win.winfo_height())
    sizes, raised, painted, wide, tall = set(), [], [], [], []
    for tab, _name in UA.TABS:
        click(ed.seg.cells[tab])
        settle(root, 0.15)
        sizes.add((ed.win.winfo_width(), ed.win.winfo_height()))
        if not (ed.tab == tab and ed.seg.current == tab and on_top(ed, tab)):
            raised.append(tab)
        if any(t[1].winfo_width() != 64 for t in ed.tiles[tab].values()):
            painted.append(tab)
        page = ed.pages[tab]
        if page.winfo_reqwidth() > ed.cv.winfo_width() + 1:
            wide.append((tab, page.winfo_reqwidth(), ed.cv.winfo_width()))
        for cell, _art, lb in ed.tiles[tab].values():
            if lb.winfo_reqwidth() > lb.winfo_width() + 1 or cell.winfo_reqwidth() > cell.winfo_width() + 1:
                wide.append((tab, lb.cget("text"), lb.winfo_reqwidth(), lb.winfo_width()))
        if page.winfo_reqheight() > ed.cv.winfo_height() + 1:
            tall.append((tab, page.winfo_reqheight(), ed.cv.winfo_height()))
    chk("탭을 누르면 그 탭이 맨 위로 올라온다", not raised, raised)
    chk("탭을 바꿔도 창 크기가 그대로다", sizes == {size0}, sizes)
    chk("탭마다 칸에 그림이 그려진다", not painted, painted)
    chk("어느 탭도 옆으로 넘치지 않는다 (이름이 잘리지 않는다)", not wide, wide[:3])
    chk("어느 탭도 아래로 넘치지 않는다", not tall, tall[:3])
    chk("칸 수: 머리 13 · 모자 7 · 안경 5 · 윗옷 9 · 바지 3 · 신발 2 · 가방 4 · 피부 0",
        [len(ed.tiles[t]) for t, _n in UA.TABS] == [0, 13, 7, 5, 9, 3, 2, 4], [len(ed.tiles[t]) for t, _n in UA.TABS])
    chk("피부는 색 여섯 칸만", len(ed.dots["skin"]) == 6 and not ed.tiles["skin"])

    print("\n=== '없음' 일 때의 색 ===")
    click(ed.seg.cells["hat"])
    settle(root, 0.15)
    row, hint = ed.dot_rows["hat"]
    chk("모자가 없으면 색 칸 대신 안내가 보인다", ed.model.spec["hat"] == "" and row.winfo_ismapped() == 0
        and hint.winfo_ismapped() == 1 and hint.cget("text") == "모자를 고르면 색을 바꿀 수 있습니다.", hint.cget("text"))
    click(ed.tiles["hat"]["cap"][0])
    settle(root, 0.15)
    chk("모자를 고르면 색 칸이 나온다", ed.model.spec["hat"] == "cap" and row.winfo_ismapped() == 1
        and hint.winfo_ismapped() == 0)
    click(ed.dots["hat"]["red"])
    settle(root, 0.1)
    chk("  그 색이 모자에 칠해진다", ed.model.spec["hatColor"] == "red")
    chk("안경·가방의 안내는 조사가 맞다", ed.dot_rows["glasses"][1].cget("text") == "안경을 고르면 색을 바꿀 수 있습니다."
        and ed.dot_rows["bag"][1].cget("text") == "가방을 고르면 색을 바꿀 수 있습니다.",
        (ed.dot_rows["glasses"][1].cget("text"), ed.dot_rows["bag"][1].cget("text")))
    chk("창 크기는 여전히 그대로", (ed.win.winfo_width(), ed.win.winfo_height()) == size0)

    print("\n=== 무작위·되돌리기 ===")
    kept = dict(ed.model.spec)
    press(ed.random_btn)
    settle(root, 0.1)
    chk("무작위는 다른 캐릭터를 낸다", ed.model.spec != kept and A.clean(ed.model.spec) == ed.model.spec)
    press(ed.undo_btn)
    settle(root, 0.1)
    chk("되돌리기 단추를 누르면 무작위 전으로", ed.model.spec == kept, ed.model.spec)
    print("\n=== 초기화 ===")
    press(ed.reset_btn)
    settle(root, 0.15)
    chk("초기화를 누르면 기본 캐릭터로 돌아간다", ed.model.spec == A.DEFAULT and ed.reset_btn.enabled is False)
    chk("  보고 있던 탭(모자)의 금테가 '없음' 으로 간다", ed.tab == "hat"
        and [v for v, t in ed.tiles["hat"].items() if gold(t[0])] == [""], ed.tab)
    click(ed.seg.cells["hair"])
    settle(root, 0.15)
    chk("  머리 탭으로 가 봐도 금테가 기본에", [v for v, t in ed.tiles["hair"].items() if gold(t[0])] == [A.DEFAULT["hair"]]
        and [n for n, d in ed.dots["hair"].items() if gold(d)] == [A.DEFAULT["hairColor"]])
    chk("  저장을 눌러야 반영된다고 알려 준다", "기본 캐릭터로" in ed.note.cget("text") and "저장" in ed.note.cget("text"),
        ed.note.cget("text"))
    chk("  아직 서버에 보내지 않았다", api.saved == [])
    press(ed.undo_btn)
    settle(root, 0.15)
    chk("  되돌리기로 무를 수 있다", ed.model.spec == kept and ed.reset_btn.enabled is True)
    bad = squeezed(ed.win)
    chk("눌린 위젯 없음 (단추 다섯이 한 줄에 다 들어간다)", not bad, bad[:3])

    print("\n=== 저장 실패 ===")
    api.save_fail = "서버에 닿지 못했습니다."
    press(ed.save_btn)
    wait(root, lambda: not ed.busy and "닿지" in ed.note.cget("text"), 4)
    chk("까닭이 빨갛게 보이고 창이 남는다", ed.alive and ed.win.winfo_exists() == 1
        and ed.note.cget("text") == "서버에 닿지 못했습니다." and str(ed.note.cget("fg")) == U.DANGER, ed.note.cget("text"))
    chk("  저장 단추를 다시 누를 수 있다", ed.save_btn.enabled is True)
    chk("  마이페이지는 그대로 (그림자)", str(w.av_art.cget("image")) == blank and w.avatar() is None)
    api.save_fail = None

    print("\n=== 저장 ===")
    want = dict(ed.model.spec)
    press(ed.save_btn)
    wait(root, lambda: api.saved and not ed.alive, 4)
    settle(root, 0.2)
    chk("서버에는 고른 것만 간다 (그림을 보내지 않는다)", api.saved == [want] and set(want) == set(A.DEFAULT), api.saved)
    chk("창이 닫힌다", ed.alive is False and ed.win.winfo_exists() == 0)
    chk("마이페이지의 그림이 내 캐릭터로 바뀐다", str(w.av_art.cget("image")) != blank
        and w.avatar() and w.avatar()["spec"] == want)
    chk("  단추는 '캐릭터 바꾸기' 가 된다", len(find(top, "캐릭터 바꾸기")) == 1 and not find(top, "캐릭터 만들기"))
    chk("  서버를 다시 부르지 않고 그 자리에서 바꾼다", api.calls == 1, api.calls)
    chk("  그림 크기는 그대로 96", w.av_art.winfo_width() >= 96 and w.av_art.winfo_height() >= 96)
    bad = squeezed(top)
    chk("  눌린 위젯 없음", not bad, bad[:3])

    print("\n=== 다시 열기 ===")
    press(w.av_btn)
    settle(root, 0.5)
    ed2 = w.editor
    chk("단추로도 열린다. 제목은 '캐릭터 바꾸기'", ed2 is not ed and ed2.alive and ed2.win.title() == "캐릭터 바꾸기")
    chk("저장된 것에서 시작한다", ed2.model.spec == want and not ed2.model.dirty
        and "지금 쓰고 있는" in ed2.note.cget("text"), ed2.note.cget("text"))
    chk("  머리 탭의 금테도 저장된 것에", [v for v, t in ed2.tiles["hair"].items() if gold(t[0])] == [want["hair"]])
    chk("한 번 더 눌러도 창을 하나 더 띄우지 않는다", w.open_avatar() is ed2 and w.editor is ed2)
    click(ed2.seg.cells["top"])
    settle(root, 0.15)
    click(ed2.tiles["top"]["hoodie"][0])
    settle(root, 0.1)
    chk("바꾸면 다시 '저장하면...' 안내", ed2.model.dirty and "닉네임 옆" in ed2.note.cget("text"))
    n = len(api.saved)
    press(ed2.cancel_btn)
    settle(root, 0.2)
    chk("취소하면 서버를 부르지 않고 닫힌다", len(api.saved) == n and ed2.win.winfo_exists() == 0
        and w.avatar()["spec"] == want)

    print("\n=== 직접 그린 도트를 넣어 둔 사람 ===")
    chk("넣어 둔 도트가 없는 사람에게는 오가는 단추가 없다", w.av_swap.holder.winfo_ismapped() == 0)
    drawn = A.walk_sheet(dict(A.DEFAULT, hair="twin", hat="bucket", topColor="red"))
    packed = SHEET.pack(drawn)
    api.swaps = []

    def avatar_image(on):
        api.swaps.append(bool(on))
        api.data["avatar"] = dict(api.data["avatar"], image=packed if on else None)
        return {"ok": True, "avatar": dict(api.data["avatar"]),
                "message": "직접 그린 도트를 씁니다." if on else "꾸민 캐릭터를 씁니다."}
    api.avatar_image = avatar_image
    api.data["avatar"] = {"spec": dict(want), "image": packed, "hasImage": True, "updatedAt": "t"}
    drew = []
    keep_photo = UA.to_photo
    UA.to_photo = lambda img: (drew.append(img), keep_photo(img))[1]
    n0 = api.calls
    w.load()
    wait(root, lambda: api.calls == n0 + 1 and (w.avatar() or {}).get("image"))
    settle(root, 0.3)
    chk("닉네임 옆에 **그 도트**가 보인다 (꾸민 캐릭터가 아니라)", drew and drew[-1] == SHEET.front(drawn)
        and drew[-1] != A.front(want) and w.av_art.winfo_width() >= 96)
    chk("  '꾸민 캐릭터 쓰기' 단추가 생긴다", w.av_swap.holder.winfo_ismapped() == 1
        and w.av_swap.label.cget("text") == "꾸민 캐릭터 쓰기")
    bad = squeezed(top)
    chk("  눌린 위젯 없음", not bad, bad[:3])
    press(w.av_swap)
    wait(root, lambda: api.swaps == [False] and not w.avatar().get("image"), 4)
    settle(root, 0.2)
    chk("누르면 꾸민 캐릭터로 바뀐다 (서버에 끄라고 보낸다)", api.swaps == [False] and drew[-1] == A.front(want)
        and w.av_swap.label.cget("text") == "직접 그린 도트 쓰기", (api.swaps, w.av_swap.label.cget("text")))
    chk("  아래에 무엇으로 바꿨는지 적힌다", "꾸민 캐릭터" in w.status._label.cget("text"), w.status._label.cget("text"))
    press(w.av_swap)
    wait(root, lambda: api.swaps == [False, True] and w.avatar().get("image"), 4)
    settle(root, 0.2)
    chk("다시 누르면 도트로 돌아온다", drew[-1] == SHEET.front(drawn) and w.av_swap.label.cget("text") == "꾸민 캐릭터 쓰기")
    edd = w.open_avatar()
    settle(root, 0.4)
    chk("도트를 쓰는 중에 꾸미기 창을 열면 '저장하면 꾸민 캐릭터로 바뀐다' 고 알린다",
        "직접 그린 도트를 쓰고 있습니다" in edd.note.cget("text") and "남아" in edd.note.cget("text"), edd.note.cget("text"))
    n = len(api.saved)
    press(edd.save_btn)
    wait(root, lambda: len(api.saved) == n + 1 and not edd.alive, 4)
    chk("  아무것도 안 바꾸고 저장해도 서버에 보낸다 (꾸민 캐릭터로 돌아가겠다는 뜻이다)", len(api.saved) == n + 1)
    UA.to_photo = keep_photo

    print("\n=== 새로고침 ===")
    api.data["avatar"] = {"spec": dict(want, hair="bun"), "updatedAt": "t"}
    w.load()
    wait(root, lambda: api.calls == 2 and (w.avatar() or {}).get("spec", {}).get("hair") == "bun")
    settle(root, 0.3)
    chk("서버가 준 캐릭터가 보인다", w.avatar()["spec"]["hair"] == "bun" and w.av_art.winfo_width() >= 96
        and len(find(top, "캐릭터 바꾸기")) == 1)
    ed3 = w.open_avatar()
    settle(root, 0.3)
    w.close()
    settle(root, 0.2)
    chk("마이페이지를 닫으면 꾸미기 창도 닫힌다", ed3.alive is False and ed3.win.winfo_exists() == 0 and w.editor is None)

    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
