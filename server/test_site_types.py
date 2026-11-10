# -*- coding: utf-8 -*-
"""안내서(docs/guide)의 타입 상성표가 게임이 쓰는 상성 그대로인가 (게시판 건의 #503). 서버를 띄우지 않는다.

    python server/test_site_types.py
    python server/test_site_types.py --guide <html> --pokedex <json>     (다른 파일로 맞대어 볼 때)

표는 tools/make_site_types.py 가 server/data/pokedex.json 의 types 로 만든다. 상성 값이 바뀌었는데 표를 다시 안 만들면
여기서 걸린다 - 그때는 `python tools/make_site_types.py` 를 돌리면 된다.

생성기를 믿지 않고 안내서의 HTML 을 따로 읽어서 pokedex.json 과 칸마다 맞대어 본다.

  1. 줄(기술 타입) · 칸(맞는 타입)이 pokedex.json 의 상성 타입 그대로다. 스텔라처럼 상성이 빈 타입은 없다.
  2. 324칸 전부: 2배는 class e2 · 글자 2, 0.5배는 eh · 0.5, 0배는 e0 · 0, 1배는 빈칸.
  3. 읽는 법의 예와 '타입이 둘이면 곱합니다' 의 예시가 그 값 · 도감의 타입으로 센 것과 같다.
  4. 위쪽 탭에서 이 장(#types)으로 갈 수 있다.
"""
import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

OK = FAIL = 0
# 안내서 칸의 표기 (배율 -> class, 글자). 생성기와 따로 적어 둔다 - 생성기가 틀려도 여기서 걸리게
WANT = {2.0: ("e2", "2"), 0.5: ("eh", "0.5"), 0.0: ("e0", "0"), 1.0: ("", "")}


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s  <- %s" % (name, got))


class Table(HTMLParser):
    """types-chart 표를 읽는다: 칸 머리 이름들, 줄마다 (줄 머리, [(class, 글자)])."""

    def __init__(self):
        HTMLParser.__init__(self)
        self.inside = 0              # types-chart 안에서의 table 깊이
        self.part = None             # thead / tbody
        self.cell = None             # 지금 읽는 칸: [태그, class, scope, 글자]
        self.head = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            if self.inside or "types-chart" in (a.get("class") or "").split():
                self.inside += 1
            return
        if not self.inside:
            return
        if tag in ("thead", "tbody"):
            self.part = tag
        elif tag == "tr" and self.part == "tbody":
            self.rows.append([None, []])
        elif tag in ("th", "td"):
            self.cell = [tag, a.get("class") or "", a.get("scope") or "", ""]

    def handle_endtag(self, tag):
        if not self.inside:
            return
        if tag == "table":
            self.inside -= 1
        elif tag in ("thead", "tbody"):
            self.part = None
        elif tag in ("th", "td") and self.cell:
            kind, cls, scope, text = self.cell
            text = text.strip()
            self.cell = None
            if self.part == "thead" and kind == "th" and "corner" not in cls.split():
                self.head.append(text)
            elif self.part == "tbody" and self.rows:
                if kind == "th" and scope == "row":
                    self.rows[-1][0] = text
                elif kind == "td":
                    self.rows[-1][1].append((cls.strip(), text))

    def handle_data(self, data):
        if self.cell is not None:
            self.cell[3] += data


def section(guide, sid):
    i = guide.find('<section id="%s">' % sid)
    if i < 0:
        return ""
    return guide[i:guide.index("</section>", i)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--guide", default=os.path.join(ROOT, "docs", "guide", "index.html"))
    ap.add_argument("--pokedex", default=os.path.join(HERE, "data", "pokedex.json"))
    a = ap.parse_args()
    with open(a.pokedex, encoding="utf-8") as f:
        dex = json.load(f)
    with open(a.guide, encoding="utf-8") as f:
        guide = f.read()

    types = dex["types"]
    real = dict((k, t) for k, t in types.items() if t.get("eff"))
    kr = dict((k, t["kr"].strip()) for k, t in real.items())
    key = dict((n, k) for k, n in kr.items())

    def eff(atk, dfn):
        return float(real[atk]["eff"].get(dfn, 1.0))

    print("=== 안내서의 타입 상성표 (docs/guide/#types) ===")
    sec = section(guide, "types")
    chk("안내서에 타입 상성 장(<section id=\"types\">)이 있다", bool(sec))
    if not sec:
        return finish()
    chk("위쪽 탭에서 이 장으로 간다", '<a href="#types">' in guide[:guide.find("<main")])
    chk("생성기 표시 두 줄이 있다", "<!-- make_site_types: 시작." in sec and "<!-- make_site_types: 끝 -->" in sec)

    t = Table()
    t.feed(sec)
    t.close()
    n = len(real)
    chk("상성 타입은 %d개 (상성이 빈 타입은 뺀다: %s)" % (n, ", ".join(sorted(set(types) - set(real))) or "없음"),
        n == 18, n)
    chk("칸 머리 = pokedex.json 의 타입 이름 그대로, 한 번씩", sorted(t.head) == sorted(kr.values()) and len(t.head) == n,
        t.head)
    rows = [r[0] for r in t.rows]
    chk("줄 머리 = pokedex.json 의 타입 이름 그대로, 한 번씩", sorted(rows) == sorted(kr.values()) and len(rows) == n, rows)
    chk("상성이 빈 타입(%s)은 표에 없다" % ", ".join(types[k]["kr"].strip() for k in types if k not in real),
        all(types[k]["kr"].strip() not in t.head + rows for k in types if k not in real))

    bad, seen = [], 0
    if len(t.head) == n and len(rows) == n and set(t.head) <= set(key) and set(rows) <= set(key):
        for rname, cells in t.rows:
            if len(cells) != n:
                bad.append("%s 줄의 칸이 %d개" % (rname, len(cells)))
                continue
            for cname, (cls, text) in zip(t.head, cells):
                v = eff(key[rname], key[cname])
                seen += 1
                if (cls, text) != WANT.get(v, ("?", "?")):
                    bad.append("%s 기술 → %s: 안내서 %s/%r, 게임 %s배" % (rname, cname, cls or "빈칸", text, "%g" % v))
    chk("%d칸이 전부 게임의 배율 그대로 (2배 · 0.5배 · 0배 · 빈칸=1배)" % (n * n), not bad and seen == n * n,
        "; ".join(bad[:5]) + (" 외 %d칸" % (len(bad) - 5) if len(bad) > 5 else "") or "읽은 칸 %d" % seen)

    # 읽는 법의 예
    m = re.search(r"<b>([^<]+)</b> 줄을 따라가다 <b>([^<]+)</b> 칸에서 만나는 (\S+) 는 \1 기술이 \2 포켓몬에게 (\S+)배로", sec)
    chk("읽는 법의 예가 표의 값과 같다", m and m.group(1) in key and m.group(2) in key
        and WANT.get(eff(key[m.group(1)], key[m.group(2)]), ("", None))[1] == m.group(3)
        and "%g" % eff(key[m.group(1)], key[m.group(2)]) == m.group(4), m and m.groups())

    # 두 타입의 예시: "<li>얼음 기술 → 망나뇽 (드래곤 · 비행): 2 × 2 = <b>4배</b></li>"
    by_kr = dict((s["kr"], s) for s in dex["species"])
    ex = re.findall(r"<li>(\S+) 기술 → (\S+) \(([^)]+)\): ([^=<]+) = <b>([^<]+)배</b></li>", sec)
    bad = []
    for mt, who, tys, parts, total in ex:
        s = by_kr.get(who)
        want_types = [kr.get(x, x) for x in (s or {}).get("types", [])]
        got_types = [x.strip() for x in tys.split("·")]
        if not s or mt not in key or got_types != want_types:
            bad.append("%s 의 타입: 안내서 %s, 도감 %s" % (who, got_types, want_types))
            continue
        nums = [eff(key[mt], key[x]) for x in got_types]
        prod = 1.0
        for x in nums:
            prod *= x
        if parts.strip() != " × ".join("%g" % x for x in nums) or total != "%g" % prod:
            bad.append("%s 기술 → %s: 안내서 %s = %s, 게임 %s = %g"
                       % (mt, who, parts.strip(), total, " × ".join("%g" % x for x in nums), prod))
    chk("두 타입 예시 %d개가 게임의 값 · 도감의 타입과 같다" % len(ex), len(ex) >= 2 and not bad, bad or len(ex))
    return finish()


def finish():
    print("\n%d 통과, %d 실패" % (OK, FAIL))
    if FAIL:
        print("표를 다시 만들려면: python tools/make_site_types.py")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
