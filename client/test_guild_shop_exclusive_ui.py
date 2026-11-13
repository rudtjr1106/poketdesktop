# -*- coding: utf-8 -*-
"""코인 상점의 '길드 전용' 묶음 (시즌 7~) — 진짜 Tk 로 확인. 서버 없이 돈다.

    python3 client/test_guild_shop_exclusive_ui.py
    POKET_SKIN=dp python3 client/test_guild_shop_exclusive_ui.py

설계: design-notes/2026-11-12-guild-war-rewards.md '길드 전용 상품'. 서버(server/app/guild.py shop · buy)는 시즌 7 부터
상점 groups 맨 앞에 '길드 전용' 을 싣고, 그 상품에 exclusive · limit(시즌마다 수) · left(이번 시즌 남은 수) 를 붙인다.
시즌 수를 넘겨 사면 409 '... 이번 시즌에 N개까지 ... 다음 시즌에 다시 살 수 있습니다.' 규칙(값 · 수 · 동시에 사기)은
서버 검사(server/test_guild_shop_exclusive.py)가 본다. 여기서는 **화면**을 본다:

  1. '길드 전용' 묶음이 맨 앞 (머리글 · 전용 상품), 그 아래 나머지 도구 머리글과 도구.
  2. 상품마다 '이번 시즌 left / limit개 남음', 다 샀으면 '다음 시즌에 다시' 글 · 사기 단추가 죽는다.
     전용 상품은 '1개 사기' 하나뿐 (10개 단추가 없다 - 남은 수를 넘지 않게).
  3. 사면 서버로 간다 (도구 · 개수), 다시 받아 남은 수가 준다.
  4. 다른 창에서 이미 사서 서버가 409 로 막으면: 서버 글을 띄우고 상점을 다시 받아 남은 수를 고친다.
  5. groups 에 '길드 전용' 이 없으면(옛 서버 · 시즌 6) 예전 그대로 - 머리글 없이, 모든 도구에 1개 · 10개 단추.
  어느 테마(기본 · DP)에서도 글이 잘리지 않고 Tk 오류가 없다.

서버 흉내 · 창 여는 법은 test_guild_ui 의 FakeServer / Api / FakeApp 을 그대로 쓴다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-guild-shop-ex-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import test_guild_ui as TG                                  # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_box, ui_common as U, ui_guild   # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402

OK = FAIL = 0
GROUPS = ["볼", "성장", "진화", "지닌 도구"]
REST = " · ".join(GROUPS)
# (도구, 이름, 코인, 시즌마다 수, 설명) - 서버 SHOP_EXCLUSIVE 의 값
EXCLUSIVE = (("MASTERBALL", "마스터볼", 600, 1, "반드시 잡히는 가장 좋은 볼. 팔 수 없다."),
             ("GOLDBOTTLECAP", "금색병뚜껑", 200, 2, "포켓몬 한 마리의 개체값을 모두 최고로 만든다."))
EX_MSG = "%s 은(는) 이번 시즌에 %d개까지 살 수 있습니다 (이미 %d개). 다음 시즌에 다시 살 수 있습니다."


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Server(TG.FakeServer):
    def __init__(self):
        TG.FakeServer.__init__(self)
        self.season = 7
        self.bought = {}              # {(사람, 도구): 이번 시즌 산 수}
        self.bag = {}                 # 산 전용 상품

    def left(self, me, iid, limit):
        return max(0, limit - self.bought.get((me, iid), 0))


class Api(TG.Api):
    """test_guild_ui 의 가짜 api + 시즌 7 상점 (길드 전용 묶음 · 시즌 수)."""

    def guild_shop(self):
        s, me = self.s, self.me
        s.calls.append(("shop",))
        r = TG.Api.guild_shop(self)
        for it in r["items"]:
            it["group"] = "볼" if it.get("cat") == "ball" else "성장"
        groups = list(GROUPS)
        if s.season >= 7:
            ex = [{"id": iid, "kr": kr, "cat": "ball" if iid == "MASTERBALL" else "misc", "coin": price,
                   "group": "길드 전용", "exclusive": True, "limit": limit, "left": s.left(me, iid, limit), "note": note}
                  for iid, kr, price, limit, note in EXCLUSIVE]
            r["items"] = ex + r["items"]
            groups = ["길드 전용"] + groups
        r["groups"] = groups
        r["bag"] = dict(r.get("bag") or {}, **dict((k[1], n) for k, n in s.bag.items() if k[0] == me))
        return r

    def guild_buy(self, item, count=1):
        s, me = self.s, self.me
        s.calls.append(("buy", item, count))
        ex = dict((e[0], e) for e in EXCLUSIVE) if s.season >= 7 else {}
        if item not in ex:
            return TG.Api.guild_buy(self, item, count)
        _iid, kr, price, limit, _note = ex[item]
        had = s.bought.get((me, item), 0)
        if count > limit:
            s.fail("%s 은(는) 시즌마다 %d개까지 살 수 있습니다." % (kr, limit), 409)
        if had + count > limit:
            s.fail(EX_MSG % (kr, limit, had), 409)
        if s.coin[me] < price * count:
            s.fail("길드 코인이 모자랍니다. (%d개 필요)" % (price * count))
        s.coin[me] -= price * count
        s.bought[(me, item)] = had + count
        s.bag[(me, item)] = s.bag.get((me, item), 0) + count
        return {"ok": True, "spent": price * count, "coin": s.coin[me], "message": "%s %d개를 샀습니다." % (kr, count)}


def norm(t):
    return "".join(str(t).split())


def scan(w):
    """창 안에 보이는 글 (위에서부터): 라벨 글과 캔버스에 그린 글 (DP 는 상점을 캔버스에 그린다). [(y, x, 글)]"""
    out = []

    def walk(x):
        for c in x.winfo_children():
            try:
                cls = c.winfo_class()
                if cls == "Canvas" and c.winfo_ismapped():
                    top = int(c.canvasy(0))
                    for i in c.find_all():
                        if c.type(i) != "text":
                            continue
                        t, b = c.itemcget(i, "text"), c.bbox(i)
                        if t and b and b[1] > -9000:
                            out.append((c.winfo_rooty() + b[1] - top, c.winfo_rootx() + b[0], t))
                elif cls == "Label" and c.winfo_ismapped():
                    t = str(c.cget("text"))
                    if t:
                        out.append((c.winfo_rooty(), c.winfo_rootx(), t))
            except tk.TclError:
                pass
            walk(c)
    walk(w)
    return sorted(out)


def y_of(rows, text):
    """그 글이 들어간 첫 줄의 y (없으면 None). 띄어쓰기 · 줄바꿈은 안 가린다."""
    k = norm(text)
    return next((y for y, _x, t in rows if k in norm(t)), None)


def has(rows, text):
    return y_of(rows, text) is not None


def overflow(w):
    """캔버스 밖으로 나간 그린 글 (DP 상점 판) - [(글, 오른쪽 끝, 캔버스 폭)]."""
    out = []

    def walk(x):
        for c in x.winfo_children():
            if c.winfo_class() == "Canvas" and c.winfo_ismapped():
                cw = c.winfo_width()
                for i in c.find_all():
                    if c.type(i) == "text":
                        b = c.bbox(i)
                        if b and b[0] > -9000 and b[2] > cw + 1:
                            out.append((c.itemcget(i, "text")[:20], b[2], cw))
            walk(c)
    walk(w)
    return out


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda *a: errors.append(a)
    ui_guild.CHAT_MS = 150
    ui_box.confirm = lambda *a, **k: True
    print("테마 %s · 글꼴 %s / 본문 %dpt" % (skins.active(), U.FAMILY, U.FONT[1]))

    srv = Server()
    srv.g = {"name": "피카단", "intro": "", "mode": "open", "master": 1, "points": 0}
    srv.roles = {1: "master", 2: "member"}
    srv.coin[1] = 700
    srv.balls[1] = 7                                # (가진 것 7 - 마스터볼 '가진 것 1' 과 헷갈리지 않게)
    srv.bought[(1, "GOLDBOTTLECAP")] = 2           # 금색병뚜껑은 이번 시즌에 이미 다 샀다
    app = TG.FakeApp(root, Api(srv, 1))
    w = ui_guild.GuildWindow(app)
    top = w.win.winfo_toplevel()
    top.deiconify()
    top.geometry("1000x680+60+40")
    TG.wait(root, lambda: w.data is not None and w.mode == "guild")
    said, real_say = [], w.say
    w.say = lambda text, color=U.GOOD: (said.append(text), real_say(text, color))

    def open_shop():
        w.shop = None
        if w.tab == "shop":
            w._draw_tab()
        else:
            w.show_tab("shop")
        TG.wait(root, lambda: w.shop is not None, 4)
        TG.settle(root, 0.4)
        return scan(w.content)

    print("=== 시즌 7: '길드 전용' 묶음이 맨 앞 ===")
    rows = open_shop()
    ids = [it["id"] for it in w.shop_shown()]
    chk("전용 상품이 맨 앞 (마스터볼 · 금색병뚜껑, 그 뒤 돈 상점 도구)", ids[:2] == ["MASTERBALL", "GOLDBOTTLECAP"]
        and ids[2:] == ["POKEBALL", "ULTRABALL", "RARECANDY"], ids)
    ys = [y_of(rows, t) for t in ("길드 전용", "마스터볼", REST, "몬스터볼")]
    chk("화면 차례: '길드 전용' 머리글 → 전용 상품 → '%s' 머리글 → 다른 도구" % REST,
        None not in ys and ys == sorted(ys) and len(set(ys)) == 4, ys)
    chk("  전용 묶음 설명 (돈 상점에 없음 · 시즌마다 수)", has(rows, ui_guild.SHOP_EX_NOTE))
    chk("남은 수: '이번 시즌 1 / 1개 남음' (마스터볼)", has(rows, "이번 시즌 1 / 1개 남음"), [t for _y, _x, t in rows if "시즌" in t])
    chk("  다 샀으면 '이번 시즌 0 / 2개 남음 - 다음 시즌에 다시 살 수 있습니다' (금색병뚜껑)",
        has(rows, "이번 시즌 0 / 2개 남음 - 다음 시즌에 다시 살 수 있습니다"), [t for _y, _x, t in rows if "시즌" in t])
    chk("  값은 서버가 준 대로 (코인 600 · 코인 200)", has(rows, "코인 600") and has(rows, "코인 200"))
    b = w.shop_btns
    chk("단추: 전용 상품은 '1개 사기' 하나 (10개 없음), 다른 도구는 1개 · 10개 그대로",
        ("MASTERBALL", 10) not in b and ("GOLDBOTTLECAP", 10) not in b and ("POKEBALL", 10) in b
        and ("RARECANDY", 1) in b, sorted(b))
    chk("  다 산 금색병뚜껑은 단추가 죽고, 코인이 되는 마스터볼은 산다", not b[("GOLDBOTTLECAP", 1)].enabled
        and b[("MASTERBALL", 1)].enabled and b[("POKEBALL", 10)].enabled)
    chk("눌린 위젯 없음", not squeezed(top), squeezed(top)[:3])
    if getattr(w, "shop_inner", None) is not None and w.shop_inner.winfo_exists():
        chk("  카드 안에 옆으로 잘린 글이 없다 (기본 테마)", not TG.clipped_wide(w.shop_inner), TG.clipped_wide(w.shop_inner)[:3])
    chk("  판 밖으로 나간 그린 글이 없다", not overflow(w.content), overflow(w.content)[:3])

    print("\n=== 사기: 서버로 간다 ===")
    n_shop = srv.calls.count(("shop",))
    b[("MASTERBALL", 1)].command()
    TG.wait(root, lambda: srv.calls.count(("shop",)) > n_shop and w.shop is not None, 4)
    TG.settle(root, 0.4)
    rows = scan(w.content)
    chk("'1개 사기' -> 서버로 (마스터볼, 1개) · 코인 700 -> 100", ("buy", "MASTERBALL", 1) in srv.calls
        and srv.coin[1] == 100 and w.h_coin.cget("text") == "길드 코인 100개", (srv.calls[-3:], w.h_coin.cget("text")))
    chk("  다시 받아 '이번 시즌 0 / 1개 남음 - 다음 시즌에 다시' · 단추가 죽는다",
        has(rows, "이번 시즌 0 / 1개 남음 - 다음 시즌에 다시 살 수 있습니다") and not w.shop_btns[("MASTERBALL", 1)].enabled,
        [t for _y, _x, t in rows if "시즌" in t])
    chk("  가진 것 1 이 보인다", has(rows, "가진 것 1"))

    print("\n=== 다른 창에서 이미 샀다: 서버가 409 ===")
    srv.coin[1] = 1000
    srv.bought[(1, "GOLDBOTTLECAP")] = 1           # 화면은 1개 남았다고 받는다
    rows = open_shop()
    chk("남은 수 1 · 단추가 산다", has(rows, "이번 시즌 1 / 2개 남음") and w.shop_btns[("GOLDBOTTLECAP", 1)].enabled)
    srv.bought[(1, "GOLDBOTTLECAP")] = 2           # 그사이 다른 창(다른 PC)에서 마지막 하나를 샀다
    n_shop = srv.calls.count(("shop",))
    del said[:]
    w.shop_btns[("GOLDBOTTLECAP", 1)].command()
    TG.wait(root, lambda: srv.calls.count(("shop",)) > n_shop and w.shop is not None, 4)
    TG.settle(root, 0.4)
    rows = scan(w.content)
    msg = EX_MSG % ("금색병뚜껑", 2, 2)
    chk("서버 글을 그대로 띄운다 (다음 시즌에 다시)", ("buy", "GOLDBOTTLECAP", 1) in srv.calls and msg in said
        and srv.coin[1] == 1000, (said, srv.coin[1]))
    chk("  상점을 다시 받아 '0 / 2개 남음' · 단추가 죽는다", has(rows, "이번 시즌 0 / 2개 남음")
        and not w.shop_btns[("GOLDBOTTLECAP", 1)].enabled, [t for _y, _x, t in rows if "시즌" in t])
    n_shop = srv.calls.count(("shop",))
    srv.coin[1] = 0
    w.buy("RARECANDY", 1)                          # 전용이 아닌 도구가 막히면 예전 그대로 (글만, 다시 받지 않는다)
    TG.wait(root, lambda: any("모자랍니다" in x for x in said), 4)
    TG.settle(root, 0.3)
    chk("  다른 도구가 막히면 예전 그대로 (글만 · 상점을 다시 받지 않는다)", srv.calls.count(("shop",)) == n_shop
        and any("모자랍니다" in x for x in said), srv.calls[-3:])

    print("\n=== 찾기 ===")
    w.shop_q.set("길드 전용")
    TG.settle(root, 0.3)
    rows = scan(w.content)
    chk("'길드 전용' 으로 찾으면 전용 상품만 (나머지 머리글도 안 보인다)",
        [it["id"] for it in w.shop_shown()] == ["MASTERBALL", "GOLDBOTTLECAP"] and not has(rows, REST)
        and not has(rows, "몬스터볼"), [it["id"] for it in w.shop_shown()])
    w.shop_q.set("몬스터")
    TG.settle(root, 0.3)
    rows = scan(w.content)
    chk("  다른 도구만 맞으면 전용 머리글은 안 보인다", [it["id"] for it in w.shop_shown()] == ["POKEBALL"]
        and not has(rows, "길드 전용") and has(rows, REST), [t for _y, _x, t in rows][:12])
    w.shop_q.set("")
    TG.settle(root, 0.2)

    print("\n=== 시즌 6 · 옛 서버: groups 에 '길드 전용' 이 없다 ===")
    srv.season = 6
    srv.coin[1] = 12
    rows = open_shop()
    chk("전용 상품 · 머리글 · 남은 수 글이 없다", [it["id"] for it in w.shop_shown()] == ["POKEBALL", "ULTRABALL", "RARECANDY"]
        and not has(rows, "길드 전용") and not has(rows, REST) and not has(rows, "남음"), [t for _y, _x, t in rows][:12])
    b = w.shop_btns
    chk("  모든 도구에 1개 · 10개 단추 (예전 그대로), 코인 12개로 살 수 있는 것만 산다",
        sorted(b) == sorted((i, n) for i in ("POKEBALL", "ULTRABALL", "RARECANDY") for n in (1, 10))
        and dict((k, v.enabled) for k, v in b.items()) == {
            ("POKEBALL", 1): True, ("POKEBALL", 10): True, ("ULTRABALL", 1): True, ("ULTRABALL", 10): False,
            ("RARECANDY", 1): False, ("RARECANDY", 10): False}, dict((k, v.enabled) for k, v in b.items()))
    if getattr(w, "shop_inner", None) is not None and w.shop_inner.winfo_exists():
        first = w.shop_cards[0][1]
        chk("  (기본 테마) 머리글 없이 카드가 첫 줄부터", getattr(w, "shop_heads", None) is None
            and int(first.grid_info().get("row", -1)) == 0, first.grid_info())
    chk("눌린 위젯 없음", not squeezed(top), squeezed(top)[:3])

    chk("Tk 콜백에서 난 오류가 없다", not errors, errors[:2])
    w.close()
    root.update()
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
