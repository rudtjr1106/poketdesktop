# -*- coding: utf-8 -*-
"""도구 그림을 받아서 server/data/item_sprites/ 에 넣는다.

포켓몬 도트와 달리 도구 그림은 개당 1~2KB 라서, 필요할 때마다 받아오지
않고 **저장소에 같이 넣어 둔다.** 그러면 서버가 깃허브에 기대지 않아도
되고 처음 열 때 비어 보이는 일이 없다.

두 군데를 본다.

    1) PokeAPI sprites — 포켓몬 도트와 같은 출처라 화풍이 맞는다
    2) pokesprite     — PokeAPI 에 없는 것 보충. 이름 규칙이 달라서
                        (poke-ball -> ball/poke.png) 맞춰 준다

둘 다 없는 것은 분류에 맞는 색으로 간단한 아이콘을 그린다. 8세대 DLC 와
9세대에서 새로 나온 진화 도구 열 몇 개가 여기 해당한다.

    python tools/build_item_sprites.py
"""
import argparse
import io
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

POKEAPI = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/%s.png"
POKESPRITE = "https://raw.githubusercontent.com/msikma/pokesprite/master/items/%s.png"
INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_pokesprite_index.json")

# 그림이 없을 때 쓸 분류별 색 (테두리, 안쪽)
CAT_COLOR = {
    "ball": ("#c8402f", "#f0f2f7"),
    "stone": ("#7a52c0", "#d8c8f2"),
    "ev": ("#2f8fc8", "#c8e6f7"),
    "iv": ("#c8a02f", "#f7ecc8"),
    "heal": ("#2fa85a", "#cdf0da"),
    "misc": ("#6b7280", "#dfe3ea"),
}


def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "poketdesktop"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
        return data if data and len(data) > 60 else None
    except Exception:
        return None


def pokesprite_candidates(ident, index):
    """pokesprite 안에서 이 도구가 있을 만한 경로들."""
    names = [ident]
    for suf in ("-ball", "-berry", "-stone"):
        if ident.endswith(suf):
            names.append(ident[:-len(suf)])
    names.append(ident.replace("-", ""))
    out = []
    for n in names:
        folder = index.get(n)
        if folder:
            out.append("%s/%s" % (folder, n))
    return out


def placeholder(ident, cat, size=32):
    """그림이 없을 때 쓸 아이콘을 직접 그린다.

    빈칸으로 두면 '깨진 것' 처럼 보인다. 분류 색을 가진 동그란 표식을
    그려 두면 적어도 무슨 종류인지는 보인다.
    """
    from PIL import Image, ImageDraw
    edge, fill = CAT_COLOR.get(cat, CAT_COLOR["misc"])
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = 3
    d.ellipse([m, m, size - m - 1, size - m - 1], fill=fill, outline=edge, width=2)
    # 가운데 가로줄 — 몬스터볼 느낌의 단순한 표식
    d.line([m + 2, size // 2, size - m - 3, size // 2], fill=edge, width=2)
    d.ellipse([size // 2 - 4, size // 2 - 4, size // 2 + 4, size // 2 + 4],
              fill=fill, outline=edge, width=2)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="server/data/items.json")
    ap.add_argument("--out", default="server/data/item_sprites")
    ap.add_argument("--force", action="store_true", help="이미 있어도 다시 받는다")
    a = ap.parse_args()

    items = json.load(io.open(a.items, encoding="utf-8"))["items"]
    index = {}
    if os.path.exists(INDEX):
        index = json.load(io.open(INDEX, encoding="utf-8"))
    else:
        sys.stderr.write("  경고: %s 가 없어 pokesprite 보충을 건너뜁니다.\n" % INDEX)

    if not os.path.isdir(a.out):
        os.makedirs(a.out)

    def one(it):
        path = os.path.join(a.out, it["id"] + ".png")
        if os.path.exists(path) and not a.force:
            return it["id"], "이미 있음"
        data = fetch(POKEAPI % it["ident"])
        src = "PokeAPI"
        if data is None:
            for cand in pokesprite_candidates(it["ident"], index):
                data = fetch(POKESPRITE % cand)
                if data:
                    src = "pokesprite"
                    break
        if data is None:
            data = placeholder(it["ident"], it["cat"])
            src = "직접 그림"
        with open(path, "wb") as f:
            f.write(data)
        return it["id"], src

    with ThreadPoolExecutor(max_workers=16) as ex:
        res = list(ex.map(one, items.values()))

    from collections import Counter
    c = Counter(src for _i, src in res)
    total = sum(os.path.getsize(os.path.join(a.out, f))
                for f in os.listdir(a.out) if f.endswith(".png"))
    print("\n도구 그림 %d개" % len(res))
    for k, v in c.most_common():
        print("  %-12s %3d개" % (k, v))
    drawn = [i for i, s in res if s == "직접 그림"]
    if drawn:
        print("  (직접 그린 것: %s)" % ", ".join(items[i]["kr"] for i in drawn))
    print("  전부 합쳐 %.0fKB" % (total / 1024.0))


if __name__ == "__main__":
    main()
