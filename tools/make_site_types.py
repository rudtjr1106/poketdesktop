# -*- coding: utf-8 -*-
"""사이트 안내서의 '타입 상성' 장(docs/guide/#types)에 싣는 상성표를 만든다 (게시판 건의 #503).

    python tools/make_site_types.py        docs/guide/index.html 의 표시 사이를 새로 쓴다

**값은 게임 엔진이 쓰는 그대로다.** server/data/pokedex.json 의 types[타입].eff 가 '그 타입 기술로 때릴 때 맞는
타입마다의 배율' 이고 (common/pokelogic.Pokedex.effectiveness 가 이것을 곱한다), 이름은 types[타입].kr 이다.
eff 가 빈 타입(스텔라)은 상성표에 없는 타입이라 뺀다. 두 타입의 예시도 같은 값과 도감(species)의 타입으로 센다.

줄 · 칸의 색 띠는 게임의 타입 색(client/poketdesktop/ui_common.py 의 TYPE_COLOR)이다. tkinter 를 불러오지 않으려고
그 파일에서 표만 읽는다.

pokedex.json 의 상성이 바뀌면 이것을 다시 돌린다. 안 돌리면 server/test_site_types.py 가 CI 에서 걸린다.
안내서에서 표시('make_site_types: 시작' ~ 'make_site_types: 끝') 사이는 손으로 고치지 말 것 - 다시 돌리면 덮어쓴다.
"""
import ast
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEX = os.path.join(ROOT, "server", "data", "pokedex.json")
GUIDE = os.path.join(ROOT, "docs", "guide", "index.html")
UI_COMMON = os.path.join(ROOT, "client", "poketdesktop", "ui_common.py")

START = "<!-- make_site_types: 시작."
END = "<!-- make_site_types: 끝 -->"
INDENT = "    "                                      # <section> 안 덩어리의 들여쓰기

# 줄 · 칸의 차례: 본가 상성표에서 늘 보던 차례 (게임의 TYPE_COLOR 도 이 차례다)
ORDER = ("NORMAL", "FIRE", "WATER", "ELECTRIC", "GRASS", "ICE", "FIGHTING", "POISON", "GROUND",
         "FLYING", "PSYCHIC", "BUG", "ROCK", "GHOST", "DRAGON", "DARK", "STEEL", "FAIRY")
# 칸에 적는 것: 배율 -> (칸의 class, 글자, 풀어 쓴 말). 1배는 빈칸
MARK = {2.0: ("e2", "2", "2배"), 0.5: ("eh", "0.5", "0.5배"), 0.0: ("e0", "0", "0배")}
# '타입이 둘이면 곱합니다' 의 예시: (기술 타입, 맞는 포켓몬). 4배 · 서로 지워 1배 · 한쪽이 0 이라 0배
EXAMPLES = (("ICE", "DRAGONITE"), ("GRASS", "GYARADOS"), ("ELECTRIC", "SWAMPERT"))


def num(x):
    """2.0 -> '2', 0.5 -> '0.5', 0.25 -> '0.25'"""
    return "%g" % x


def load(path=DEX):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def chart(dex):
    """-> (차례대로 [(열쇠, 한글 이름)], {공격: {방어: 배율}}). eff 가 빈 타입은 뺀다."""
    types = dex["types"]
    have = set(k for k, t in types.items() if t.get("eff"))
    if have != set(ORDER):
        sys.exit("타입이 ORDER 와 다릅니다 - 더 생긴 것 %s, 없어진 것 %s. ORDER 를 고치세요."
                 % (sorted(have - set(ORDER)), sorted(set(ORDER) - have)))
    names = [(k, types[k]["kr"].strip()) for k in ORDER]
    eff = {}
    for a in ORDER:
        row = types[a]["eff"]
        eff[a] = {}
        for d in ORDER:
            v = float(row.get(d, 1.0))
            if v != 1.0 and v not in MARK:
                sys.exit("%s -> %s 배율 %s 는 표에 적는 법이 없습니다 (MARK)" % (a, d, v))
            eff[a][d] = v
    return names, eff


def type_colors(path=UI_COMMON):
    """게임의 TYPE_COLOR 를 파일에서 읽는다 (불러오면 tkinter 까지 딸려 온다). 못 읽으면 빈 것."""
    try:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError):
        return {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "TYPE_COLOR" for t in node.targets):
            return ast.literal_eval(node.value)
    return {}


def build(dex, colors=None):
    """안내서의 표시 사이에 들어갈 글 (줄마다 들여쓰기까지)."""
    names, eff = chart(dex)
    kr = dict(names)
    colors = type_colors() if colors is None else colors
    by = dict((s["internal"], s) for s in dex["species"])
    e = html.escape

    def tc(k):
        c = colors.get(k)
        return ' style="--tc:%s"' % c if c else ""

    # 읽는 법의 예: 차례에서 처음 나오는 2배 칸
    ra, rd = next((a, d) for a in ORDER for d in ORDER if eff[a][d] == 2.0)
    out = [
        START + " tools/make_site_types.py 가 server/data/pokedex.json 의 types 로 만든다 - 끝 표시까지 손으로 고치지 말 것 -->",
        '<div class="blk">',
        "  <h3>표 읽는 법</h3>",
        "  <p>상성표에서 왼쪽 줄은 <b>기술의 타입</b>, 위 칸은 <b>맞는 포켓몬의 타입</b>입니다. <b>%s</b> 줄을 따라가다 <b>%s</b> 칸에서 "
        "만나는 2 는 %s 기술이 %s 포켓몬에게 2배로 들어간다는 뜻입니다. 빈칸은 1배입니다.</p>"
        % (e(kr[ra]), e(kr[rd]), e(kr[ra]), e(kr[rd])),
        '  <p class="eff-key">',
        '    <span><b class="eff e2">2</b>2배 · 효과가 굉장했다</span>',
        '    <span><b class="eff eh">0.5</b>0.5배 · 효과가 별로인 듯하다</span>',
        '    <span><b class="eff e0">0</b>0배 · 효과가 없는 것 같다</span>',
        '    <span><b class="eff"></b>빈칸 · 1배</span>',
        "  </p>",
        "</div>",
        "",
        '<div class="blk wide">',
        "  <h3>%d타입 상성표</h3>" % len(names),
        '  <p class="types-hint">좁은 화면에서는 표를 옆으로 밀어서 봅니다. 왼쪽의 기술 타입 줄은 그대로 붙어 있습니다.</p>',
        '  <div class="tbl"><table class="types-chart" aria-label="타입 상성표. 줄은 기술의 타입, 칸은 맞는 포켓몬의 타입">',
        '    <thead><tr><th class="corner" scope="col"><span>맞는 쪽 →</span><span>기술 ↓</span></th>'
        + "".join('<th scope="col"%s>%s</th>' % (tc(k), e(n)) for k, n in names) + "</tr></thead>",
        "    <tbody>",
    ]
    for a, an in names:
        cells = []
        for d, dn in names:
            v = eff[a][d]
            if v == 1.0:
                cells.append("<td></td>")
            else:
                cls, mark, said = MARK[v]
                cells.append('<td class="%s" title="%s 기술 → %s: %s">%s</td>' % (cls, e(an), e(dn), said, mark))
        out.append('      <tr><th scope="row"%s>%s</th>%s</tr>' % (tc(a), e(an), "".join(cells)))
    out += [
        "    </tbody>",
        "  </table></div>",
        "</div>",
        "",
        '<div class="blk">',
        "  <h3>타입이 둘이면 곱합니다</h3>",
        "  <p>타입이 둘인 포켓몬에게는 두 칸의 배율을 곱한 만큼 들어갑니다. 그래서 4배와 0.25배도 나오고, "
        "한쪽이 0 이면 다른 쪽이 2 여도 0배입니다.</p>",
        "  <ul>",
    ]
    for mt, sp in EXAMPLES:
        s = by[sp]
        parts = [eff[mt][t] for t in s["types"]]
        total = 1.0
        for p in parts:
            total *= p
        out.append("    <li>%s 기술 → %s (%s): %s = <b>%s배</b></li>"
                   % (e(kr[mt]), e(s["kr"]), " · ".join(e(kr[t]) for t in s["types"]),
                      " × ".join(num(p) for p in parts), num(total)))
    out += ["  </ul>", "</div>", END]
    return "\n".join((INDENT + ln) if ln else "" for ln in out)


def splice(guide, block):
    """안내서 글에서 표시 사이(표시 포함)를 block 으로 바꾼다."""
    i = guide.find(START)
    j = guide.find(END)
    if i < 0 or j < i:
        sys.exit("안내서에 표시가 없습니다: '%s' ... '%s'\n<section id=\"types\"> 안에 두 줄을 먼저 넣으세요." % (START, END))
    i = guide.rfind("\n", 0, i) + 1                  # 그 줄의 처음부터 (들여쓰기까지)
    return guide[:i] + block + guide[j + len(END):]


def main():
    dex = load()
    with open(GUIDE, encoding="utf-8") as f:
        old = f.read()
    new = splice(old, build(dex))
    if new == old:
        print("  %s  그대로 (pokedex.json 과 같다)" % os.path.relpath(GUIDE))
        return
    with open(GUIDE, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("  %s  상성표를 새로 썼다 (%d타입)" % (os.path.relpath(GUIDE), len(chart(dex)[0])))


if __name__ == "__main__":
    main()
