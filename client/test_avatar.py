# -*- coding: utf-8 -*-
"""캐릭터 꾸미기 창의 계산 검사 (1.10.3). 창을 만들지 않는다.

    python client/test_avatar.py

화면(ui_avatar.Editor)이 그리는 일을 뺀 나머지 - 무엇을 고를 수 있고, 고르면 무엇이 바뀌고,
되돌리면 어디로 가는가 - 를 본다. 창이 실제로 뜨는지는 test_avatar_ui.py 가 본다.

  1. 탭 여덟: 피부 + 일곱 부위. 탭마다 종류와 색 칸이 나온다.
  2. 고르면 그것만 바뀐다. 모르는 값은 안 받는다. 같은 것을 다시 고르면 되돌릴 것이 안 쌓인다.
  3. 되돌리기는 한 걸음씩, 무작위도 되돌릴 수 있다.
  4. 처음 만드는 사람은 아무것도 안 바꿔도 저장할 수 있다. 저장된 것을 그대로 두면 저장할 것이 없다.
  5. 글꼴이 커서 칸이 넓어지면 한 줄에 놓는 수가 줄어든다 (글자를 줄이지 않는다).
  6. 그림: PIL 로 바뀌고, 자리 그림(그림자)은 모양이 같고 색이 하나다.
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from common import avatar_art as A                           # noqa: E402
from poketdesktop import ui_avatar as UA                     # noqa: E402

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
    print("=== 탭 ===")
    keys = [k for k, _n in UA.TABS]
    chk("피부 + 일곱 부위", keys == ["skin", "hair", "hat", "glasses", "top", "bottom", "shoes", "bag"], keys)
    chk("이름은 전부 두 글자 (탭 줄이 한 줄에 들어간다)", all(len(n) == 2 for _k, n in UA.TABS), UA.TABS)
    chk("피부는 종류가 없고 색만 있다", UA.options_of("skin") == [] and len(UA.swatches("skin")) == 6)
    chk("머리는 13가지, 색 13", len(UA.options_of("hair")) == 13 and len(UA.swatches("hair")) == 13)
    chk("모자·안경·가방의 첫 칸은 '없음'", all(UA.options_of(t)[0] == ("", "없음") for t in ("hat", "glasses", "bag")))
    chk("색이 적히는 열쇠", [UA.color_key(k) for k in keys] == ["skin", "hairColor", "hatColor", "glassesColor",
                                                        "topColor", "bottomColor", "shoeColor", "bagColor"])
    sw = UA.swatches("top")
    chk("색 칸은 '#rrggbb'", len(sw) == 16 and all(len(h) == 7 and h[0] == "#" and int(h[1:], 16) >= 0 for _n, h in sw), sw[:2])
    chk("색 칸의 순서는 색표 그대로", [n for n, _h in sw] == list(A.CLOTH))
    chk("모르는 탭은 빈 목록", UA.options_of("zzz") == [] and UA.swatches("zzz") == [] and UA.color_key("zzz") is None)
    chk("이름이 긴 종류가 없다 (칸이 넓어진다) - 여덟 글자까지",
        max(len(l) for t in keys for _v, l in UA.options_of(t)) <= 8,
        sorted(((len(l), l) for t in keys for _v, l in UA.options_of(t)), reverse=True)[:2])

    print("\n=== 칠할 곳 ===")
    chk("모자가 없으면 모자 색은 고를 것이 없다", not UA.paintable(A.DEFAULT, "hat")
        and UA.paintable(dict(A.DEFAULT, hat="cap"), "hat"))
    chk("피부·머리·윗옷은 늘 칠할 곳이 있다", all(UA.paintable(A.DEFAULT, t) for t in ("skin", "hair", "top", "bottom", "shoes")))

    print("\n=== 고르기 ===")
    m = UA.Model()
    chk("처음 만드는 사람은 기본 캐릭터에서 시작한다", m.spec == A.DEFAULT and m.saved is None)
    chk("  아무것도 안 바꿔도 저장할 것이 있다", m.dirty)
    chk("고르면 그것만 바뀐다", m.pick("hair", "pony") and m.spec == dict(A.DEFAULT, hair="pony"))
    chk("색도 고른다", m.pick("hairColor", "pink") and m.spec["hairColor"] == "pink" and m.spec["hair"] == "pony")
    chk("피부", m.pick("skin", "tan") and m.spec["skin"] == "tan")
    chk("'없음' 으로도 고를 수 있다", m.pick("hat", "cap") and m.pick("hat", "") and m.spec["hat"] == "")
    n = len(m.history)
    chk("같은 것을 다시 고르면 아무 일도 없다 (되돌릴 것이 안 쌓인다)", m.pick("hair", "pony") is False and len(m.history) == n)
    before = dict(m.spec)
    chk("모르는 값은 안 받는다", m.pick("hair", "없는머리") is False and m.pick("zzz", "x") is False
        and m.pick("topColor", "무지개") is False and m.spec == before and len(m.history) == n)
    chk("고른 것은 늘 그릴 수 있다", A.clean(m.spec) == m.spec and len(A.walk_sheet(m.spec)) == 128)

    print("\n=== 되돌리기 ===")
    m = UA.Model()
    chk("처음에는 되돌릴 것이 없다", m.undo() is False and not m.history)
    m.pick("top", "hoodie")
    m.pick("topColor", "red")
    chk("한 걸음씩 되돌아간다", m.undo() and m.spec == dict(A.DEFAULT, top="hoodie") and m.undo() and m.spec == A.DEFAULT
        and m.undo() is False)
    rng = random.Random(3)
    m.pick("hair", "bun")
    kept = dict(m.spec)
    chk("무작위는 다른 캐릭터를 낸다", m.randomize(rng) and m.spec != kept and A.clean(m.spec) == m.spec)
    chk("  되돌리면 무작위 전으로", m.undo() and m.spec == kept)
    for i in range(UA.HISTORY + 25):
        m.pick("topColor", list(A.CLOTH)[i % 16])
    chk("되돌릴 것은 %d개까지만 기억한다" % UA.HISTORY, len(m.history) == UA.HISTORY, len(m.history))

    print("\n=== 초기화 ===")
    m = UA.Model(dict(A.DEFAULT, hair="twin", hat="beret", topColor="purple", skin="dark"))
    was = dict(m.spec)
    chk("꾸민 캐릭터는 기본이 아니다", not m.plain)
    chk("초기화하면 기본 캐릭터가 된다", m.reset() and m.spec == A.DEFAULT and m.plain)
    chk("  저장을 눌러야 반영된다 (저장할 것이 생긴다)", m.dirty and m.saved == was)
    chk("  되돌리기로 무를 수 있다", m.undo() and m.spec == was and not m.dirty)
    m = UA.Model()
    chk("이미 기본이면 아무 일도 없다 (되돌릴 것이 안 쌓인다)", m.plain and m.reset() is False and not m.history)
    m.pick("hair", "bun")
    chk("하나만 바꿔도 초기화할 것이 생긴다", not m.plain and m.reset() and m.plain)

    print("\n=== 저장된 것 ===")
    saved = dict(A.DEFAULT, hair="twin", hat="beret", topColor="purple")
    m = UA.Model(saved)
    chk("저장된 것에서 시작한다", m.spec == saved and m.saved == saved)
    chk("  그대로면 저장할 것이 없다", not m.dirty)
    m.pick("bag", "backpack")
    chk("  바꾸면 저장할 것이 생긴다", m.dirty)
    m.pick("bag", "")
    chk("  도로 돌려놓으면 다시 없다", not m.dirty)
    m.pick("shoes", "boots")
    m.mark_saved()
    chk("저장하고 나면 그것이 저장된 것이다", not m.dirty and m.saved["shoes"] == "boots")
    m = UA.Model({"hair": "없어진머리", "top": "tank", "junk": 1})
    chk("옛 저장분의 모르는 값은 기본값으로 읽는다", m.spec == dict(A.DEFAULT, top="tank"), m.spec)
    chk("빈 사전은 '안 만든 사람' 이다", UA.Model({}).saved is None and UA.Model(None).saved is None)

    print("\n=== 한 줄에 몇 칸 ===")
    chk("칸 86 이면 다섯", UA.columns(86) == 5, (UA.columns(86), UA.AVAIL))
    chk("글꼴이 1.5배라 칸이 123 이면 줄어든다 (셋)", UA.columns(123) == 3, UA.columns(123))
    chk("아무리 넓어도 한 칸은 놓는다", UA.columns(5000) == 1)
    chk("다섯을 넘기지 않는다", UA.columns(10) == UA.COLS)
    chk("쓸 수 있는 폭이 창보다 좁다", 300 < UA.AVAIL < UA.W - UA.PREVIEW_W, UA.AVAIL)

    print("\n=== 그림 ===")
    im = UA.to_pil(A.front(A.DEFAULT))
    chk("PIL 그림: 96x96 RGBA", im.size == (96, 96) and im.mode == "RGBA", (im.size, im.mode))
    src = A.cell(A.DEFAULT, "down", "stand")
    y, x = [(y, x) for y, row in enumerate(src) for x, px in enumerate(row) if px[3]][40]
    chk("  점이 그대로 옮겨진다", UA.to_pil(src).getpixel((x, y)) == tuple(src[y][x]))
    sil = UA.silhouette(src, (46, 54, 76))
    chk("자리 그림은 모양이 같다", [[bool(px[3]) for px in row] for row in sil] == [[bool(px[3]) for px in row] for row in src])
    chk("  색은 하나뿐이다", set(px for row in sil for px in row if px[3]) == {(46, 54, 76, 255)})
    chk("걷는 미리보기는 왼발·서기·오른발·서기", UA.WALK == ("a", "stand", "b", "stand")
        and all(f in A.FRAMES for f in UA.WALK))
    chk("가방은 옆에서 본다 (앞에서는 끈만 보인다)", UA.THUMB_DIR.get("bag") == "left"
        and len(set(repr(A.cell(dict(A.DEFAULT, bag=v), "left", "stand")) for v, _l in UA.options_of("bag"))) == 4)

    print("\n=== 직접 그린 도트를 쓰는 사람 ===")
    from common import avatar_sheet as SH
    mine = dict(A.DEFAULT, hair="bun", top="jacket")
    drawn = A.walk_sheet(dict(A.DEFAULT, hair="twin", hat="bucket", topColor="red"))
    av = {"spec": mine, "image": SH.pack(drawn), "hasImage": True}
    chk("그 도트의 앞모습이 나온다 (꾸민 캐릭터가 아니라)", UA.front_of(av) == SH.front(drawn) and UA.front_of(av) != A.front(mine))
    chk("  크기도 고를 수 있다 (프로필은 두 배)", len(UA.front_of(av, 2)) == 64)
    chk("  걷기 시트도 그 도트다", UA.sheet_of(av) == drawn)
    off = dict(av, image=None)
    chk("꺼 두면 꾸민 캐릭터가 나온다", UA.front_of(off) == A.front(mine) and UA.sheet_of(off) == A.walk_sheet(mine))
    chk("도트가 깨져 있으면 꾸민 캐릭터로 넘어간다 (빈칸이 되지 않는다)",
        UA.front_of(dict(av, image="깨진 글")) == A.front(mine) and UA.sheet_of(dict(av, image="x")) == A.walk_sheet(mine))
    chk("아무것도 없어도 기본 캐릭터", UA.front_of(None) == A.front(A.DEFAULT) and UA.front_of({}) == A.front(A.DEFAULT))

    print("\n=== 고르는 칸의 그림 ===")
    busy = dict(A.DEFAULT, hair="pony", hat="cap", glasses="round", top="hoodie", bag="backpack")
    rng = random.Random(11)
    same = []
    for spec in [A.DEFAULT, busy] + [A.random_spec(rng) for _ in range(30)]:
        for tab, _name in UA.TABS:
            opts = UA.options_of(tab)
            pics = [repr(A.cell(UA.thumb_spec(spec, tab, v), UA.THUMB_DIR.get(tab, "down"), "stand")) for v, _l in opts]
            if len(set(pics)) != len(pics):
                same.append((tab, spec.get("hat"), spec.get("hair"), len(set(pics)), len(pics)))
    chk("무엇을 입고 있어도 한 탭의 칸들은 서로 다르게 보인다", not same, same[:4])
    chk("  머리 칸은 모자를 벗겨서 그린다 (모자가 머리를 가린다)", UA.thumb_spec(busy, "hair", "bun")["hat"] == ""
        and UA.thumb_spec(busy, "hair", "bun")["hair"] == "bun" and UA.thumb_spec(busy, "top", "tee")["hat"] == "cap")
    chk("  고른 것 자체는 안 건드린다", busy["hat"] == "cap" and busy["hair"] == "pony")

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
