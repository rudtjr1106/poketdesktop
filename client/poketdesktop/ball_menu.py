# -*- coding: utf-8 -*-
"""던질 볼을 고르는 메뉴.

**배율은 서버가 계산해서 이유까지 만들어 보낸다.** 여기서는 그대로
그리기만 한다. 클라이언트가 조건을 다시 보면 화면에 쓰인 값과 실제
판정이 어긋나는데, 어긋날 수밖에 없는 것들이 있다 - 물타입 판정은
내부 이름을 보는데 클라이언트가 받는 타입은 한국어고, 리피트볼은 도감
기록을, 레벨볼은 파티 선두를 봐야 한다.

가진 볼만 보여준다. 스무 줄 중 열다섯 줄이 죽은 줄이면 메뉴가 아니라
카탈로그다. 대신 '지금 제일 잘 듣는데 없는 볼' 은 맨 아래 한 줄로
알려준다 - 그런 볼이 있다는 걸 알아야 상점에서 사 온다.
"""
import tkinter as tk

from . import ui_common as U

MASTER = "MASTERBALL"


def _label(o):
    """('네트볼  3개', '×3.5 · 물·벌레라서')"""
    left = "%s  %d개" % (o["kr"], o["count"])
    right = ""
    if o["mult"] and abs(o["mult"] - 1.0) > 0.01:
        right = "x%.2g" % o["mult"]
        if o.get("why"):
            right += " · " + o["why"]
    elif o.get("why"):
        right = o["why"]
    return left, right


def build(root, options, on_pick, on_shop=None):
    """메뉴를 만들어 돌려준다. 띄우는 건 부르는 쪽에서 한다."""
    m = tk.Menu(root, tearoff=0, bg=U.BG2, fg=U.FG,
                activebackground=U.BG4, activeforeground=U.FG,
                bd=0, font=U.FONT_S)
    have = [o for o in options if o["count"] > 0 and o["id"] != MASTER]
    best = next((o for o in have if o.get("best")), None)

    if best:
        left, right = _label(best)
        m.add_command(label="추천   " + left, accelerator=right,
                      command=lambda: on_pick(best["id"]))
        m.add_separator()

    if not have:
        m.add_command(label="던질 볼이 없습니다", state="disabled")
    for o in have:
        left, right = _label(o)
        m.add_command(label=left, accelerator=right,
                      command=lambda i=o["id"]: on_pick(i))

    # 마스터볼은 구분선 뒤 맨 아래. 배율이 255라 계산상 언제나 1등이지만
    # 실수로 한 번 쓰면 돌이킬 수 없어서 추천에서 빼고 따로 둔다.
    mb = next((o for o in options if o["id"] == MASTER and o["count"] > 0),
              None)
    if mb:
        m.add_separator()
        m.add_command(label="마스터볼  %d개  (반드시 잡힘)" % mb["count"],
                      command=lambda: on_pick(MASTER))

    # 지금 제일 잘 듣는데 안 가진 볼 하나
    want = [o for o in options
            if o["count"] == 0 and o["mult"] > 1.5 and o["id"] != MASTER]
    if want:
        top = max(want, key=lambda o: o["mult"])
        m.add_separator()
        m.add_command(label="지금은 %s 이(가) 잘 듣습니다 (없음)" % top["kr"],
                      state="disabled")
        if on_shop:
            m.add_command(label="상점 열기...", command=on_shop)
    return m


def popup(root, event, options, on_pick, on_shop=None):
    m = build(root, options, on_pick, on_shop)
    try:
        m.tk_popup(event.x_root, event.y_root)
    finally:
        m.grab_release()
    return m
