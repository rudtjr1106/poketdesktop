# -*- coding: utf-8 -*-
"""길드 친선전 화면 검사 (1.10.3).

    python client/test_friendly_ui.py

**창을 진짜로 띄운다.** 서버도 웹소켓도 없다 - 가짜 서버(test_guild_ui)를 쓰고, '웹소켓이 넘겨준 것' 은
길드 창에 직접 넣는다.

  1. **친선전은 길드 채팅에서 한다** (따로 칸이 없다). 채팅에 `/친선전` 을 치면 상대를 구하고 - 말로
     보내지 않는다 - 채팅에 **카드**가 놓인다. 길드원은 그 카드의 [배틀] 을 눌러 받고(바로 내 배틀 창),
     판이 열리면 같은 카드가 [관전] 으로 바뀌고, 끝나면 결과가 적힌다. `/친선전 닉네임` 은 한 사람에게
     직접 신청, `/친선전 취소` 는 그만두기다. 안 되면 까닭을 아래 줄에 적는다.
  2. 채팅을 안 보고 있을 때 누가 상대를 구하거나 길드원의 친선전이 열리면 **화면 오른쪽 아래에 알림**이
     뜬다 (잠깐 떴다 사라진다). **채팅을 보고 있으면 안 뜬다** (눈앞에 카드가 놓였다). 내가 싸우는 판은
     알리지 않는다. 알림은 끌 수 있고, 알림 없이 바로 구경하게 할 수도 있다.
  3. 구경을 누르면 알림은 사라지고 **바탕화면 오른쪽 아래에서 야생 배틀처럼** 싸운다: 창도 배경도 없이
     걷는 도트 둘이 마주 서고(도트는 저마다 투명 창, 클릭이 통과한다), **몬스터볼에서 나와** 싸우고
     (기술 연출·체력 막대·떠오르는 글씨), 교체하고, 쓰러지고, 끝나면 결과를 띄운 뒤 스스로 사라진다.
     그 위에는 누구와 누구인지 적은 작은 이름표 하나만 뜬다 (× 로 그만 본다).
  4. 밀려오는 것이 없으면(웹소켓이 없다) 구경하는 동안 스스로 물어 온다.
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-test-friendly-ui-"))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from common import tint as T                                # noqa: E402
from poketdesktop import duel_scene as F                    # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_guild                           # noqa: E402
from poketdesktop import ui_spectate as SP                  # noqa: E402
import test_guild_ui as G                                   # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, sec=0.3):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def fake_art(pane, mon, side, done):
    """포켓몬 도트를 서버에서 받는 대신 색 네모 두 장으로 (그림을 다듬는 길은 진짜 것을 밟는다)."""
    from PIL import Image
    key = (mon.get("num"), T.skin(mon), side)
    got = pane._art.get(key)
    if isinstance(got, dict):
        return done(got)
    pane._art[key] = [done]
    col = (240, 200, 60) if side == "a" else (240, 120, 60)
    F._art_ready(pane, key, ([Image.new("RGBA", (40, 48), col + (255,)), Image.new("RGBA", (40, 48), col + (255,))],
                             [100, 100]))


def mon(num, name, hp=100, **kw):
    return dict({"species": "X", "num": num, "name": name, "level": 50, "hp": hp, "maxhp": 100, "status": None,
                 "shiny": False, "tint": None, "fainted": hp <= 0, "mega": False}, **kw)


def fight(mid, turn, a, b, a_mon, b_mon, events, **kw):
    return dict({"id": mid, "turn": turn, "step": turn, "over": False,
                 "a": {"id": a[0], "name": a[1], "left": 2, "size": 2, "mon": a_mon},
                 "b": {"id": b[0], "name": b[1], "left": 2, "size": 2, "mon": b_mon}, "events": events}, **kw)


def texts(w):
    out = []

    def walk(x):
        for c in x.winfo_children():
            try:
                if c.winfo_ismapped() and str(c.cget("text")):
                    out.append(str(c.cget("text")))
            except Exception:                               # noqa: BLE001
                pass
            walk(c)
    walk(w)
    return out


def squeezed(top, w):
    """눌린 위젯 (G.squeezed). **굴려서 칸 밖으로 나간 카드는 뺀다** - 채팅(Text)은 안 보이는 줄에 끼운
    창을 치워 두고 크기도 그때 것 그대로 둔다 (다시 보이면 제 크기로 놓는다). 그것은 눌린 것이 아니다."""
    hidden = set()

    def walk(x):
        hidden.add(("세로", x.winfo_reqheight(), x.winfo_height()))
        hidden.add(("가로", x.winfo_reqwidth(), x.winfo_width()))
        for c in x.winfo_children():
            walk(c)
    for c in w.chat_cards.values():
        if not c["frame"].winfo_ismapped():
            walk(c["frame"])
    return [b for b in G.squeezed(top) if (b[0], b[3], b[4]) not in hidden]


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    F.load_art = fake_art

    srv = G.FakeServer()
    A1 = G.Api(srv, 1)
    A1.guild_create("친선단", "", "open")
    G.Api(srv, 2).guild_join(1)
    G.Api(srv, 3).guild_join(1)
    n2, n3 = srv.names[2], srv.names[3]
    app = G.FakeApp(root, A1)
    app.user_id, app.settings, app.live_battle = 1, {}, None
    app.live_checks = app.live_waits = 0
    app.check_live = lambda: setattr(app, "live_checks", app.live_checks + 1)
    app.live_watch = lambda *a: setattr(app, "live_waits", app.live_waits + 1)
    w = ui_guild.GuildWindow(app)
    top = w.win.winfo_toplevel()
    top.deiconify()
    top.geometry("1000x700+60+40")
    G.wait(root, lambda: w.in_guild() and w.chat_box is not None)
    for m in w.data["members"]:
        pass

    def status():
        return w.status._label.cget("text")

    def send(text):
        w.chat_var.set(text)
        w.send_chat()

    def push_chat(line):
        """서버가 채팅 줄 하나를 밀어 줬다 (가짜 서버에 적힌 그 줄을)."""
        w._on_ws({"t": "chat", "m": dict(next(m for m in srv.chat if m["id"] == line), system=True)})

    def cards():
        return w.card_texts()

    print("=== 채팅에서 한다: /친선전 ===")
    G.wait(root, lambda: ("state", 1) in srv.fr_calls and w.chat_ready, 4)
    settle(root)
    fr = app.friendly
    chk("친선전 칸은 없다. 채팅을 열면 지금 모습을 받아 온다 (앱의 것 하나를 같이 쓴다)", isinstance(fr, SP.Friendly) and w.fr is fr
        and "friendly" not in [k for k, _l in ui_guild.TABS] and not hasattr(w, "_tab_friendly"))
    chk("  입력 칸 위에 무엇을 칠 수 있는지 늘 적혀 있다", w.chat_hint.winfo_ismapped() and w.chat_hint.cget("text") == SP.CMD_HINT
        and "/친선전" in SP.CMD_HINT)
    w.chat_var.set("/")
    chk("  '/' 를 치면 쓸 수 있는 명령을 다 보여 준다", w.chat_hint.cget("text") == SP.CMD_HELP and "닉네임" in SP.CMD_HELP and "취소" in SP.CMD_HELP)
    w.chat_var.set("")
    chk("  지우면 돌아온다", w.chat_hint.cget("text") == SP.CMD_HINT)
    n_chat = len(srv.chat)
    send("/친선전")
    G.wait(root, lambda: ("seek", 1, True) in srv.fr_calls and len(cards()) == 1, 5)
    settle(root, 0.2)
    line = srv.seek_card.get(1)
    chk("**/친선전 을 치면 상대를 구한다** - 말로 보내지 않는다. 입력 칸은 비워진다", ("seek", 1, True) in srv.fr_calls and fr.seeking_me()
        and w.chat_var.get() == "" and not any(m["body"].startswith("/") for m in srv.chat) and len(srv.chat) == n_chat + 1)
    c = w.chat_cards[line]
    chk("**채팅에 카드가 놓인다**: 내 것에는 '구하는 중' 이라는 말과 [취소]. 상태 글은 따로 없다 (같은 말을 두 번 적지 않는다)",
        cards().get(line) == ("", "친선전 상대를 구하는 중입니다.", "취소")
        and sorted(texts(c["frame"])) == sorted(["길드 친선전", "친선전 상대를 구하는 중입니다.", "취소"]), (cards(), texts(c["frame"])))
    chk("  어떻게 되는지는 아래 줄에 한 번 알려 준다", "[배틀] 을 누르면" in status() and "3분" in status(), status())
    root.update_idletasks()
    lo, hi = w._card_span()
    fx, fw, tw = c["frame"].winfo_x(), c["frame"].winfo_width(), w.chat_box.winfo_width()
    chk("  카드는 채팅 줄 사이에 끼어 있다 (같이 굴러간다). **말 줄처럼 왼쪽에 붙고, 내용만큼만 넓다**", c["frame"].winfo_ismapped()
        and str(c["frame"]) in w.chat_box.window_names() and fx <= 16 and abs(fw - (lo + 2)) <= 2
        and lo < hi == ui_guild.CHAT_CARD_W and fw < tw * 0.7 and "[친선전]" in w.chat_bodies()[-1], (fx, fw, tw, lo, hi))
    chk("  채팅 글로는 안 보인다 (알림 줄이 따로 또 서지 않는다)", "친선전 상대를 구합니다" not in w.chat_text(), w.chat_text()[-60:])
    bad = squeezed(top, w)
    chk("  눌린 위젯 없음", not bad, bad[:3])
    chk("  화면 구석의 알림은 안 뜬다 (내 것이다)", fr.card is None)
    send("/친선전")
    settle(root, 0.2)
    chk("구하는 중에 또 치면 그렇다고 알려 준다 (다시 구하지 않는다)", "이미 상대를 구하고" in status()
        and len([x for x in srv.fr_calls if x == ("seek", 1, True)]) == 1 and len(cards()) == 1, status())
    c["btn"].command()
    G.wait(root, lambda: ("seek", 1, False) in srv.fr_calls and cards().get(line, ("",))[0] == "마감", 5)
    chk("**카드의 [취소] 를 누르면 그만둔다**: 카드는 '마감' 이 되고 단추가 사라진다", not fr.seeking_me()
        and cards().get(line) == ("마감", "%s 님이 친선전 상대를 구했습니다." % srv.names[1], None), cards())
    send("/친선전 취소")
    settle(root, 0.2)
    chk("구하고 있지 않을 때 /친선전 취소 는 그렇다고 알려 준다", "구하고 있지 않습니다" in status()
        and len([x for x in srv.fr_calls if x == ("seek", 1, False)]) == 1, status())
    send("/친선전")
    G.wait(root, lambda: len(cards()) == 2 and fr.seeking_me(), 5)
    send("/친선전 취소")
    G.wait(root, lambda: not fr.seeking_me() and len([x for x in srv.fr_calls if x == ("seek", 1, False)]) == 2, 5)
    settle(root, 0.2)
    chk("/친선전 취소 로도 그만둔다 (새로 놓였던 카드가 닫힌다)", [v[0] for _l, v in sorted(cards().items())] == ["마감", "마감"], cards())

    print("\n=== 다른 명령 ===")
    n_chat = len(srv.chat)
    send("/춤추기")
    settle(root, 0.2)
    chk("모르는 명령은 보내지 않고 쓸 수 있는 것을 알려 준다 (친 글은 그대로 둔다)", "모르는 명령" in status() and "/친선전" in status()
        and w.chat_var.get() == "/춤추기" and len(srv.chat) == n_chat, status())
    send("/친선전 없는사람")
    chk("길드원이 아닌 이름에는 신청하지 않는다", "'없는사람' 님은 길드원이 아닙니다." in status() and not [x for x in srv.fr_calls if x[0] == "ask"], status())
    send("/친선전 %s" % srv.names[1])
    chk("자기 자신에게도", "자기 자신" in status() and not [x for x in srv.fr_calls if x[0] == "ask"], status())
    send("/친선전 %s" % n2)
    G.wait(root, lambda: ("ask", 1, 2) in srv.fr_calls and app.live_waits == 1, 4)
    chk("**/친선전 닉네임 은 그 길드원에게 직접 신청한다** (평소의 실시간 배틀 초대 - 답을 기다린다)", app.live_waits == 1
        and n2 in status() and "신청" in status() and w.chat_var.get() == "" and len(srv.chat) == n_chat, status())
    srv.fr_fail = "상대가 지금 접속해 있지 않습니다. 실시간 배틀은 둘 다 켜 있어야 합니다."
    send("/친선전 %s" % n3)
    G.wait(root, lambda: ("ask", 1, 3) in srv.fr_calls and "접속해 있지" in status(), 4)
    chk("  안 되면 까닭을 적는다 (상대가 접속해 있지 않다)", "접속해 있지" in status() and app.live_waits == 1, status())
    send("그냥 하는 말")
    G.wait(root, lambda: "그냥 하는 말" in w.chat_text(), 4)
    chk("보통 말은 그대로 간다", srv.chat[-1]["body"] == "그냥 하는 말" and srv.chat[-1]["userId"] == 1)

    print("\n=== 길드원이 상대를 구한다 -> 채팅의 카드 [배틀] ===")
    v2 = G.Api(srv, 2).guild_friendly_seek(True)
    line2 = srv.seek_card[2]
    push_chat(line2)
    w._on_ws(dict(v2, t="friendly"))
    settle(root, 0.2)
    c2 = w.chat_cards[line2]["frame"]
    chk("**길드원이 구하면 채팅에 카드가 놓인다**: 누가 구하는지와 [배틀] ('상대 구함' 이라는 상태 글은 없다)",
        cards().get(line2) == ("", "%s 님이 친선전 상대를 구합니다." % n2, "배틀")
        and sorted(texts(c2)) == sorted(["길드 친선전", "%s 님이 친선전 상대를 구합니다." % n2, "배틀"]), (cards().get(line2), texts(c2)))
    root.update_idletasks()
    wide = set(x["frame"].winfo_width() for x in w.chat_cards.values() if x["frame"].winfo_ismapped())
    chk("  카드들의 폭이 들쭉날쭉하지 않다 (짧은 이름의 카드는 다 같은 폭), 왼쪽 끝도 같다", len(wide) == 1 and c2.winfo_x() <= 16, wide)
    chk("  채팅을 보고 있으니 화면 구석의 알림은 띄우지 않는다 (같은 것을 두 번 알리지 않는다)", fr.card is None and w.chat_visible())
    w.chat_cards[line2]["btn"].command()
    G.wait(root, lambda: ("accept", 1, 2) in srv.fr_calls and app.live_checks == 1, 4)
    settle(root, 0.2)
    chk("**[배틀] 을 누르면 바로 시작한다**: 서버에 받는다고 하고, 내 배틀 창을 띄운다", app.live_checks == 1)
    mine = fight(9, 0, (2, n2), (1, srv.names[1]), mon(25, "피카츄"), mon(4, "파이리"), [], card=line2)
    w._on_ws({"t": "card", "id": line2, "card": next(m for m in srv.chat if m["id"] == line2)["card"]})
    w._on_ws({"t": "friendly_fight", "fight": mine})
    w._on_ws({"t": "friendly", "seeking": [], "fights": [mine], "limit": 3})
    settle(root, 0.2)
    chk("  같은 카드가 '진행 중' 으로 바뀐다. 내가 낀 판이라 [내 배틀] 이다 (줄이 새로 서지 않는다)",
        cards().get(line2) == ("진행 중", "%s  vs  %s" % (n2, srv.names[1]), "내 배틀") and len(cards()) == 3, cards().get(line2))
    w.chat_cards[line2]["btn"].command()
    chk("  [내 배틀] 은 닫아 둔 내 배틀 창을 다시 띄운다", app.live_checks == 2)
    over = {"k": "friendly", "s": "over", "a": srv.who(2), "b": srv.who(1), "mid": 9, "result": "b"}
    srv.card(line2, over)
    w._on_ws({"t": "card", "id": line2, "card": over, "body": "끝"})
    w._on_ws({"t": "friendly_fight", "fight": dict(mine, over=True, result="b", turn=3)})
    w._on_ws({"t": "friendly", "seeking": [], "fights": [], "limit": 3})
    settle(root, 0.2)
    chk("**끝나면 그 카드에 결과가 적힌다** (단추는 사라진다)", cards().get(line2) == ("끝", "%s  vs  %s   ·   %s 님 승리" % (n2, srv.names[1], srv.names[1]), None),
        cards().get(line2))

    v3 = G.Api(srv, 3).guild_friendly_seek(True)
    line3 = srv.seek_card[3]
    push_chat(line3)
    w._on_ws(dict(v3, t="friendly"))
    settle(root, 0.2)
    srv.fr_fail = "길드 친선전이 이미 3판 진행 중입니다. 잠시 후에 다시 해 주세요."
    w.chat_cards[line3]["btn"].command()
    G.wait(root, lambda: ("accept", 1, 3) in srv.fr_calls and "3판 진행 중" in status(), 4)
    chk("받지 못하면 까닭을 아래 줄에 적는다 (세 판이 다 찼다 - 잠시 후에). 카드는 그대로다", "잠시 후에" in status()
        and app.live_checks == 2 and cards().get(line3, ("",))[2] == "배틀", status())
    w._on_ws({"t": "friendly", "seeking": [], "fights": [], "limit": 3})
    settle(root, 0.1)
    chk("**지금 모습에 없는 카드는 단추가 없다** (시간이 지났다 / 서버가 다시 떴다 - 죽은 [배틀] 이 남지 않는다)",
        cards().get(line3) == ("마감", "%s 님이 친선전 상대를 구했습니다." % n3, None), cards().get(line3))
    G.Api(srv, 3).guild_friendly_seek(False)

    print("\n=== 채팅의 카드로 관전한다 ===")
    watch = fight(40, 2, (2, n2), (3, n3), mon(25, "피카츄", hp=70), mon(4, "파이리", hp=55), [])
    line4 = srv.say("%s 님과 %s 님의 친선전이 열렸습니다." % (n2, n3),
                    card={"k": "friendly", "s": "fight", "a": srv.who(2), "b": srv.who(3), "mid": 40})["id"]
    watch["card"] = line4
    srv.fights[:] = [watch]
    push_chat(line4)
    w._on_ws({"t": "friendly_fight", "fight": watch})
    settle(root, 0.2)
    chk("'상대 구함' 없이 열린 판(직접 신청·친구 목록)도 카드로 놓인다: [관전]", cards().get(line4) == ("진행 중", "%s  vs  %s" % (n2, n3), "관전")
        and fr.card is None and not fr.watching(), cards().get(line4))
    w.chat_cards[line4]["btn"].command()
    settle(root, 0.1)
    d0 = fr.duel
    chk("**[관전] 을 누르면 바탕화면에서 벌어진다**. 카드는 '관전 중' · [그만 보기] 가 된다", fr.watching() and d0.mid == 40
        and cards().get(line4) == ("관전 중", "%s  vs  %s" % (n2, n3), "그만 보기"), cards().get(line4))
    w.chat_cards[line4]["btn"].command()
    settle(root, 0.1)
    chk("  [그만 보기] 를 누르면 그만 보고, 카드는 [관전] 으로 돌아간다", not fr.watching() and not d0.alive
        and cards().get(line4, ("",))[2] == "관전")
    w.chat_cards[line4]["btn"].command()
    settle(root, 0.1)
    d0 = fr.duel
    d0.x.event_generate("<Button-1>")
    settle(root, 0.1)
    chk("  이름표의 × 로 그만 봐도 카드가 [관전] 으로 돌아간다", not fr.watching() and cards().get(line4, ("",))[2] == "관전")
    root.update_idletasks()
    tall = dict((ln, x["frame"].winfo_height()) for ln, x in w.chat_cards.items() if x["frame"].winfo_ismapped())
    keep_w, keep_min = ui_guild.CHAT_CARD_W, ui_guild.CHAT_CARD_MIN
    ui_guild.CHAT_CARD_W = ui_guild.CHAT_CARD_MIN = 140           # (카드가 들어갈 자리가 아주 좁다고 해 본다)
    w._paint_cards()
    settle(root, 0.3)
    shown = dict((ln, x["frame"]) for ln, x in w.chat_cards.items() if x["frame"].winfo_ismapped())
    grew = [ln for ln, f in shown.items() if ln in tall and f.winfo_height() > tall[ln]]
    plain = [f for ln, f in shown.items() if not w.chat_cards[ln]["btn"]]         # (단추가 붙은 카드는 단추만큼은 넓어야 한다)
    chk("자리가 좁으면 카드는 그 폭을 넘지 않고 **글이 줄을 바꾼다** (글씨를 줄이지 않는다 - 카드가 높아진다)", len(plain) >= 2
        and all(f.winfo_width() <= 140 + 4 for f in plain) and grew
        and all(f.winfo_width() >= f.winfo_reqwidth() for f in shown.values()),
        ([(f.winfo_width(), f.winfo_reqwidth(), f.winfo_height()) for f in shown.values()], tall))
    bad = squeezed(top, w)
    chk("  눌린 위젯 없음", not bad, bad[:3])
    w.chat_box.yview_moveto(0.0)
    settle(root, 0.3)
    again = [x["frame"] for x in w.chat_cards.values() if x["frame"].winfo_ismapped()]
    chk("  위로 굴려서 다시 보이는 카드도 제 크기로 놓인다", len(again) >= 2 and all(f.winfo_height() >= f.winfo_reqheight() for f in again),
        [(f.winfo_height(), f.winfo_reqheight()) for f in again])
    w.chat_box.see("end")
    ui_guild.CHAT_CARD_W, ui_guild.CHAT_CARD_MIN = keep_w, keep_min
    w._paint_cards()
    settle(root, 0.3)
    chk("  (되돌리면 제 폭으로)", abs(w.chat_cards[line4]["frame"].winfo_width() - (lo + 2)) <= 2, w.chat_cards[line4]["frame"].winfo_width())
    done4 = {"k": "friendly", "s": "over", "a": srv.who(2), "b": srv.who(3), "mid": 40, "result": "draw"}
    srv.card(line4, done4)
    srv.fights[:] = []
    w._on_ws({"t": "card", "id": line4, "card": done4})
    w._on_ws({"t": "friendly_fight", "fight": dict(watch, over=True, result="draw", turn=9)})
    settle(root, 0.1)
    chk("  비긴 판", cards().get(line4) == ("끝", "%s  vs  %s   ·   무승부" % (n2, n3), None), cards().get(line4))
    w.show_tab("members")
    settle(root, 0.2)
    w.show_tab("chat")
    G.wait(root, lambda: w.chat_ready and len(cards()) >= 5, 5)
    settle(root, 0.3)
    chk("채팅 칸을 다시 열어도 카드는 그대로다 (지난 카드는 결과·마감으로)", sorted(v[0] for v in cards().values()) == ["끝", "끝", "마감", "마감", "마감"],
        sorted(cards().items()))

    print("\n=== 채팅이 꽉 차 있을 때: 맨 아래의 카드 ===")
    for i in range(40):
        srv.say("채우는 말 %d" % i, 2)
    G.wait(root, lambda: "채우는 말 39" in w.chat_text(), 6)
    settle(root, 0.3)
    box_h = lambda: w.chat_box.winfo_height()               # noqa: E731
    chk("(채팅이 칸을 넘친다 - 맨 아래를 보고 있다)", w.chat_box.yview()[0] > 0.2 and w.chat_box.yview()[1] >= 0.999, w.chat_box.yview())
    v5 = G.Api(srv, 3).guild_friendly_seek(True)
    line5 = srv.seek_card[3]
    push_chat(line5)
    w._on_ws(dict(v5, t="friendly"))
    settle(root, 0.4)
    f5 = w.chat_cards[line5]["frame"]
    chk("**맨 아래에 놓인 카드는 잘리지 않고 다 보인다** (카드의 높이는 놓은 뒤에야 정해진다)", f5.winfo_ismapped()
        and f5.winfo_height() >= f5.winfo_reqheight() > 40 and f5.winfo_y() + f5.winfo_height() <= box_h(),
        (f5.winfo_y(), f5.winfo_height(), f5.winfo_reqheight(), box_h()))
    G.Api(srv, 3).guild_friendly_seek(False)
    w._on_ws({"t": "friendly", "seeking": [], "fights": [], "limit": 3})
    settle(root, 0.4)
    low = f5.winfo_height()
    chk("  닫히면 단추가 빠져 낮아진다", cards().get(line5, ("",))[0] == "마감" and low < f5.winfo_reqheight() + 1 and f5.winfo_y() + low <= box_h(), low)
    w._on_ws(dict(v5, t="friendly"))                        # (금방 다시 구해서 놓았던 카드가 되살아났다)
    settle(root, 0.4)
    chk("  **되살아나 다시 높아져도 아래가 잘리지 않는다**", cards().get(line5, ("", "", ""))[2] == "배틀" and f5.winfo_height() > low
        and f5.winfo_y() + f5.winfo_height() <= box_h(), (f5.winfo_y(), f5.winfo_height(), low, box_h()))
    w._on_ws({"t": "friendly", "seeking": [], "fights": [], "limit": 3})
    settle(root, 0.2)

    print("\n=== 채팅을 안 보고 있을 때 -> 오른쪽 아래 알림 ===")
    w.show_tab("members")
    settle(root, 0.2)
    chk("(아직 알림은 없다. 채팅 칸은 안 보인다)", fr.card is None and not w.chat_visible())
    w._on_ws({"t": "friendly", "seeking": [{"id": 2, "name": n2, "left": 170, "card": 901}], "fights": [], "limit": 3})
    settle(root)
    card = fr.card
    chk("**화면 오른쪽 아래에 알림이 뜬다**: 누가 상대를 구하는지와 '받기' 단추", card is not None and card.alive and not fr.watching()
        and card.note_text == "%s 님이 친선전 상대를 구합니다." % n2 and card.note_btn.label.cget("text") == "받기")
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    try:
        area = PLAT.work_area(sw, sh)
    except Exception:                                       # noqa: BLE001
        area = (0, 0, sw, sh)
    x, y, cw, ch = card.win.winfo_x(), card.win.winfo_y(), card.win.winfo_width(), card.win.winfo_height()
    chk("  자리는 작업 영역의 오른쪽 아래다 (화면 밖으로 안 나간다)", abs((x + cw) - (area[2] - SP.MARGIN)) <= 2
        and abs((y + ch) - (area[3] - SP.MARGIN)) <= 2 and x >= area[0] and y >= area[1], (x, y, cw, ch, area))
    chk("  테두리 없는 작은 창이다 (하던 일의 초점을 뺏지 않는다)", bool(card.win.overrideredirect()) and cw <= SP.W + 8 and ch < 120, (cw, ch))
    checks = app.live_checks
    card.note_btn.command()
    G.wait(root, lambda: len([x for x in srv.fr_calls if x == ("accept", 1, 2)]) == 2 and app.live_checks == checks + 1, 4)
    settle(root, 0.2)
    chk("**받으면 바로 시작한다**: 서버에 받는다고 하고, 내 배틀 창을 띄운다. 알림은 닫힌다", app.live_checks == checks + 1 and fr.card is None)
    w._on_ws({"t": "friendly", "seeking": [{"id": 3, "name": n3, "left": 170, "card": 902}], "fights": [], "limit": 3})
    settle(root, 0.2)
    first = fr.card
    first._gone = time.monotonic() - 0.1
    first.step(time.monotonic())
    chk("알림은 잠깐 떴다 스스로 사라진다", fr.card is None and not first.alive and not first.win.winfo_exists())
    w._on_ws({"t": "live"})
    chk("내 실시간 배틀에 일이 생기면(신청이 왔다 / 내 것을 누가 받았다) 바로 확인한다", app.live_checks == checks + 2)
    w._on_ws({"t": "friendly", "seeking": [], "fights": [], "limit": 3})

    print("\n=== 길드원의 친선전이 열린다 -> 알림 -> 구경 ===")
    start = fight(50, 0, (2, n2), (3, n3), mon(25, "피카츄"), mon(4, "파이리"), [
        {"t": "intro", "text": "%s 님과 %s 님의 승부!" % (n2, n3)},
        {"t": "switch", "who": "a", "mon": mon(25, "피카츄"), "text": "%s: 가랏! 피카츄!" % n2},
        {"t": "switch", "who": "b", "mon": mon(4, "파이리"), "text": "%s: 가랏! 파이리!" % n3}])
    w._on_ws({"t": "friendly_fight", "fight": start})
    settle(root, 0.2)
    card = fr.card
    chk("**길드원의 친선전이 열리면 오른쪽 아래에 알린다**: 누구와 누구인지와 '관전' 단추", card is not None and card.alive and not fr.watching()
        and card.note_text == "%s vs %s · 친선전 시작" % (n2, n3) and card.note_btn.label.cget("text") == "관전")
    chk("  배틀 장면이 불쑥 뜨지는 않는다 (누른 사람에게만)", fr.duel is None and not fr.watching())
    card.note_btn.command()
    duel = fr.duel
    # 여기서부터는 시각을 넣어 가며 한 틱씩 직접 돌린다 - 스스로 도는 것은 세워 둔다
    if duel._job is not None:
        root.after_cancel(duel._job)
        duel._job = None
    duel.plate.update_idletasks()
    sc, host = duel.scene, duel.host
    chk("**구경을 누르면 알림은 사라지고, 창 없이 바탕화면에서 벌어진다**", fr.watching() and duel.mid == 50 and fr.card is None
        and not card.alive and sc is not None)
    sp = F.spots(area)
    chk("  자리는 작업 영역의 오른쪽 아래다: 둘이 %d 떨어져 마주 선다 (발은 바닥에)" % F.GAP, sc.spot == sp
        and sp["b"][0] - sp["a"][0] == F.GAP and sp["a"][1] == area[3] - F.LIFT and sp["b"][0] <= area[2], (sc.spot, area))
    chk("  체력 막대·글씨·기술 연출을 그릴 투명 레이어가 깔린다 (클릭이 통과한다)", host.layer is not None
        and host.layer.click_through and host.cv is host.layer.cv)
    px, py, pw, ph = duel.plate.winfo_x(), duel.plate.winfo_y(), duel.plate.winfo_width(), duel.plate.winfo_height()
    chk("  그 위에 작은 이름표 하나: 누구와 누구인지, 그만 보기(×)", duel.names == (n2, n3) and n2 in texts(duel.plate)
        and n3 in texts(duel.plate) and "×" in texts(duel.plate) and bool(duel.plate.overrideredirect())
        and ph < 40 and py + ph < sp["a"][1] - 100 and px >= area[0] and px + pw <= area[2], (px, py, pw, ph))
    A, B = sc.sides["a"], sc.sides["b"]
    t = time.monotonic() + 1.0
    duel.step(t)
    chk("처음에는 누구와 누구의 승부인지 떠오른다 (아직 아무도 안 나왔다)", sc.said[-1] == (None, "%s 님과 %s 님의 승부!" % (n2, n3))
        and not A.out and A.sprite is None)
    duel.step(t + 0.6)
    chk("**포켓몬은 몬스터볼에서 나온다**: 바깥쪽 위에서 볼이 날아 들어온다", A.ball is not None and A.ball.visible()
        and A.ball.shown is A.balls[0] and A.ball.at == (sc.hand["a"][0], sc.hand["a"][1] + F.BALL // 2)
        and bool(A.ball.win.overrideredirect()), (A.ball and A.ball.at, sc.hand["a"]))
    chk("  볼도 도트도 **클릭이 통과하는 투명 창**이다 (그 자리의 바탕화면을 그대로 쓴다)", A.ball.through and A.sprite is not None
        and A.sprite.through and bool(A.sprite.win.overrideredirect()) and not A.sprite.visible())
    duel.step(t + 0.6 + F.THROW_S / 2)
    bx, by = A.ball.at
    chk("  볼은 포물선을 그리며 포켓몬이 설 자리로 간다", sc.hand["a"][0] < bx < sc.spot["a"][0]
        and by - F.BALL // 2 < sc.hand["a"][1], (bx, by))
    duel.step(t + 0.6 + F.THROW_S + 0.01)
    chk("  닿으면 볼이 열리고 빛이 터진다", len(sc.rays) == 6 and A.ball.shown is A.balls[1])
    duel.step(t + 0.6 + F.THROW_S + F.OPEN_S * 0.6 + 0.02)
    chk("  **흰 빛이 작게 나타나서**", A.sprite.shown is A.grow[0] and not A.out and not A.ball.visible()
        and A.sprite.at == sc.spot["a"], (A.look, A.sprite.at))
    duel.step(t + 0.6 + F.THROW_S + F.OPEN_S * 0.6 + F.GROW_S * 0.7)
    chk("  **점점 커지고** (발은 제자리에 붙은 채로 - 창의 자리와 크기는 그대로다)", A.sprite.shown is A.grow[3]
        and A.sprite.at == sc.spot["a"] and A.sprite.box == A.art["box"])
    duel.step(t + 0.6 + F.THROW_S + F.OPEN_S + F.GROW_S + 0.1)
    cv = host.cv
    chk("  **포켓몬이 된다** - 머리 위에 체력 막대가 붙는다", A.out and A.sprite.shown in A.idle and sc.rays == []
        and cv.itemcget(A.bar, "state") != "hidden" and cv.itemcget(A.fill, "state") != "hidden")
    bar = cv.coords(A.bar)
    head = host.loc(sc.spot["a"][0], sc.spot["a"][1] - A.art["size"][1])
    chk("    막대는 그 포켓몬의 머리 바로 위다", abs((bar[0] + bar[2]) / 2.0 - head[0]) <= 1 and 0 < head[1] - bar[3] < 16, (bar, head))
    for dt in (1.85, 1.85 + F.THROW_S + 0.01, 1.85 + F.THROW_S + F.OPEN_S, 3.1):
        duel.step(t + dt)
    chk("상대 포켓몬도 볼에서 나와 마주 선다", A.out and B.out and B.sprite.at == sc.spot["b"] and B.sprite.shown in B.idle)
    said = [x for _w, x in sc.said]
    chk("  누가 무엇을 내보냈는지 떠오른다", "%s: 가랏! 피카츄!" % n2 in said and "%s: 가랏! 파이리!" % n3 in said, said)
    dots = dict((k, [c.itemcget(i, "fill") for i in c.find_all()]) for k, c in duel.dot_cv.items())
    chk("  이름표에 남은 마릿수가 점으로 찍힌다", dots == {"a": [SP.BALL_ON] * 2, "b": [SP.BALL_ON] * 2}, dots)
    full = cv.coords(B.fill)
    t += 4.0
    turn1 = fight(50, 1, (2, n2), (3, n3), mon(25, "피카츄"), mon(4, "파이리", hp=40), [
        {"t": "move", "who": "a", "move": "방전", "moveType": "ELECTRIC", "cat": "special", "text": "피카츄 의 방전!"},
        {"t": "hit", "target": "b", "hp": 40, "maxhp": 100, "eff": 2}])
    w._on_ws({"t": "friendly_fight", "fight": turn1})
    w._on_ws({"t": "friendly_fight", "fight": turn1})
    chk("같은 장면이 또 와도 다시 틀지 않는다", len(sc.queue) == 2, len(sc.queue))
    duel.step(t)
    chk("**기술을 쓰면 야생 배틀과 같은 연출이 돈다** (쓴 쪽에서 맞는 쪽으로, 투명 레이어에)", sc.fx is not None and not sc.fx.dead
        and tuple(sc.fx.src) == sc.center("a") and tuple(sc.fx.dst) == sc.center("b") and sc.fx.type == "ELECTRIC"
        and sc.fx.cv is host.layer.cv)
    chk("  **기술 이름은 쓴 포켓몬 머리 위에 떠오른다**", sc.said[-1] == ("a", "방전!"), sc.said[-1])
    duel.step(t + F.FX_CAP_S + 0.1)
    duel.step(t + F.FX_CAP_S + 0.3)
    duel.step(t + F.FX_CAP_S + 0.42)
    chk("맞으면 흔들리고 (도트 창이 좌우로 떨린다)", B.off != (0.0, 0.0) and B.sprite.at[0] != sc.spot["b"][0], (B.off, B.sprite.at))
    chk("  효과가 굉장하면 그렇다고 맞은 쪽 위에 떠오른다", ("b", "효과가 굉장하다!") in sc.said)
    duel.step(t + F.FX_CAP_S + 0.8)
    half = cv.coords(B.fill)
    chk("  체력 막대가 줄어든다 (색도 바뀐다)", B.hp == 40 and (half[2] - half[0]) < (full[2] - full[0]) * 0.5
        and cv.itemcget(B.fill, "fill") == F.hp_color(0.4) and B.off == (0.0, 0.0) and B.sprite.at == sc.spot["b"], (full, half))
    w._on_ws({"t": "friendly", "seeking": [{"id": 3, "name": n3, "left": 170}], "fights": [turn1], "limit": 3})
    chk("구경하는 동안에는 다른 알림이 그 자리를 덮지 않는다", fr.card is None and fr.duel is duel)

    t += 6.0
    w._on_ws({"t": "friendly_fight", "fight": fight(50, 2, (2, n2), (3, n3), mon(26, "라이츄"), mon(4, "파이리", hp=40), [
        {"t": "recall", "who": "a", "text": "%s: 피카츄, 돌아와!" % n2},
        {"t": "switch", "who": "a", "mon": mon(26, "라이츄"), "text": "%s: 가랏! 라이츄!" % n2}])})
    old = A.sprite
    duel.step(t)
    duel.step(t + F.RECALL_S * 0.5)
    chk("**교체: 불러들이면 흰 빛으로 줄어들고** 체력 막대는 사라진다", not A.out and A.sprite.shown in A.grow
        and cv.itemcget(A.bar, "state") == "hidden")
    duel.step(t + F.RECALL_S + 0.01)
    duel.step(t + F.RECALL_S + 0.05)
    chk("  붉은 줄기가 되어 볼이 온 쪽으로 돌아간다", sc.beam is not None and cv.type(sc.beam) == "line"
        and tuple(cv.coords(sc.beam)[2:]) == host.loc(*sc.hand["a"]) and not A.sprite.visible())
    duel.step(t + F.RECALL_S + F.BEAM_S + 0.05)
    chk("  다 들어가면 그 도트 창은 없어진다", sc.beam is None and A.sprite is None and not old.win.winfo_exists())
    for dt in (0.65, 0.65 + F.THROW_S + 0.01, 0.65 + F.THROW_S + F.OPEN_S, 2.0):
        duel.step(t + dt)
    chk("  **다음 포켓몬도 볼에서 나온다**", A.out and A.mon["num"] == 26 and A.sprite is not None and A.sprite is not old
        and A.sprite.shown in A.idle and "%s: 가랏! 라이츄!" % n2 in [x for _w, x in sc.said])

    t += 4.0
    w._on_ws({"t": "friendly_fight", "fight": fight(50, 3, (2, n2), (3, n3), mon(26, "라이츄"), mon(4, "파이리", hp=0), [
        {"t": "hit", "target": "b", "hp": 0, "maxhp": 100}, {"t": "faint", "who": "b", "text": "파이리 은(는) 쓰러졌다!"},
        {"t": "over", "result": "a", "text": ""}], over=True, result="a")})
    w._on_ws({"t": "friendly", "seeking": [], "fights": [], "limit": 3})
    gone_b = B.sprite
    for dt in (0.0, 0.55, 0.7, 1.0):
        duel.step(t + dt)
    dots = [duel.dot_cv["b"].itemcget(i, "fill") for i in duel.dot_cv["b"].find_all()]
    chk("쓰러지면 가라앉아 사라지고, 이름표의 점이 하나 꺼진다", not B.out and B.sprite is None and not gone_b.win.winfo_exists()
        and sorted(dots) == sorted([SP.BALL_ON, SP.BALL_OFF]) and A.out, dots)
    for dt in (1.4, 1.5, 1.6):
        duel.step(t + dt)
    chk("끝나면 누가 이겼는지 떠오른다", sc.said[-1] == (None, "%s 님이 이겼습니다!" % n2) and fr.duel is duel)
    duel.step(t + 1.6 + F.RESULT_S + 0.2)
    chk("  결과를 다 보여 주고 나면", sc.done and duel._gone is not None)
    last_a, layer_win, plate = A.sprite, host.layer.win, duel.plate
    duel.step(t + 1.6 + F.RESULT_S + 0.2 + SP.END_SEC + 0.1)
    chk("**바탕화면에서 스스로 사라진다** (도트 창·레이어·이름표가 다 없어진다)", fr.duel is None and not duel.alive
        and not last_a.win.winfo_exists() and not layer_win.winfo_exists() and not plate.winfo_exists())
    chk("  진행 중인 판에서도 빠진다", fr.view["fights"] == [])

    print("\n=== 알리지 않는 경우 · 설정 ===")
    mine = fight(60, 0, (1, srv.names[1]), (2, n2), mon(25, "피카츄"), mon(4, "파이리"), [])
    srv.fights[:] = [mine]                # (가짜 서버도 같은 것을 알고 있다 - 물어서 받아 온 것과 어긋나지 않게)
    w._on_ws({"t": "friendly_fight", "fight": mine})
    settle(root, 0.3)
    chk("**내가 싸우는 판은 알리지 않는다** (배틀 창이 떠 있다)", fr.card is None and not fr.watching(), fr.card)
    w._on_ws({"t": "friendly_fight", "fight": dict(mine, over=True, result="a", turn=1)})
    late = fight(61, 4, (2, n2), (3, n3), mon(25, "피카츄", hp=30), mon(4, "파이리", hp=80), [{"t": "move", "who": "a", "text": "지나간 일"}])
    fr.set_setting("friendlyNotify", False)
    srv.fights[:] = [late]
    w._on_ws({"t": "friendly_fight", "fight": late})
    chk("알림을 꺼 두면 안 뜬다 (진행 중인 판으로는 들고 있다)", fr.card is None and [f["id"] for f in fr.view["fights"]] == [61]
        and app.settings["friendlyNotify"] is False)
    fr.watch(61)
    settle(root, 0.1)
    d2 = fr.duel
    d2.step(time.monotonic())
    s2 = d2.scene
    chk("진행 중이던 판을 뒤늦게 구경하면: 볼 없이 지금 모습 그대로 서 있다 (지나간 일은 틀지 않는다)", fr.watching()
        and s2.sides["a"].out and s2.sides["b"].out and s2.queue == [] and s2.sides["a"].hp == 30
        and s2.sides["a"].ball is None and s2.sides["a"].sprite.shown in s2.sides["a"].idle and s2.said == [])
    calls = len([c for c in srv.fr_calls if c == ("state", 1)])
    fr.pushed = time.monotonic() - SP.QUIET_SEC - 1
    d2.step(time.monotonic())
    G.wait(root, lambda: len([c for c in srv.fr_calls if c == ("state", 1)]) > calls, 4)
    chk("**밀려오는 것이 없으면 구경하는 동안 스스로 물어 온다** (웹소켓이 없는 환경)",
        len([c for c in srv.fr_calls if c == ("state", 1)]) == calls + 1)
    keep_api = A1.guild_friendly
    A1.guild_friendly = lambda: {"seeking": [], "fights": [], "limit": 3}      # 묻던 때의 옛 모습 (판이 없다)
    fr.refresh()
    w._on_ws({"t": "friendly_fight", "fight": dict(late, turn=5, step=5)})    # 그 사이에 새 것이 밀려왔다
    settle(root, 0.4)
    A1.guild_friendly = keep_api
    chk("묻는 사이에 새 것이 밀려왔으면, 늦게 온 옛 답으로 덮지 않는다", [f["id"] for f in fr.view["fights"]] == [61]
        and fr.view["fights"][0]["turn"] == 5, fr.view["fights"])
    wins = [s2.sides["a"].sprite.win, s2.sides["b"].sprite.win, d2.plate]
    d2.x.event_generate("<Button-1>")
    settle(root, 0.1)
    chk("이름표의 × 를 누르면 그만 본다 (다 사라진다)", fr.duel is None and not d2.alive and not any(x.winfo_exists() for x in wins))
    fr.set_setting("friendlyNotify", True)
    fr.set_setting("friendlyAuto", True)
    auto = fight(62, 0, (2, n2), (3, n3), mon(25, "피카츄"), mon(4, "파이리"), [])
    srv.fights[:] = [late, auto]
    w._on_ws({"t": "friendly_fight", "fight": auto})
    settle(root, 0.1)
    chk("'바로 구경하기' 를 켜 두면 알림 없이 바로 바탕화면에서 벌어진다", fr.watching() and fr.duel.mid == 62 and fr.card is None)
    fr.set_setting("friendlyAuto", False)
    chk("설정은 저장된다 (설정 창의 체크 상자가 이것을 본다)", app.settings["friendlyNotify"] is True and app.settings["friendlyAuto"] is False)
    bad = G.squeezed(top) + G.squeezed(fr.duel.plate)
    chk("눌린 위젯 없음 (길드 창·이름표)", not bad, bad[:3])

    print("\n=== 닫기 ===")
    w.show_tab("chat")
    settle(root, 0.2)
    chk("다른 칸으로 가도 구경은 이어진다 (창이 따로다)", fr.watching())
    w.close()
    chk("길드 창을 닫아도 구경은 이어지고, 길드 창이 걸어 둔 것은 걷힌다", fr.watching() and fr.listeners == [] and fr.chat_open is None)
    last = fr.duel
    fr.close()
    chk("앱이 치우면 구경도 끝난다", fr.duel is None and fr.card is None and not last.alive)
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
