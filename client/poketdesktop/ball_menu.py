# -*- coding: utf-8 -*-
"""던질 볼을 고르는 메뉴.

**배율은 서버가 계산해서 이유까지 만들어 보낸다.** 여기서는 그대로
그리기만 한다. 클라이언트가 조건을 다시 보면 화면에 쓰인 값과 실제
판정이 어긋나는데, 어긋날 수밖에 없는 것들이 있다 - 물타입 판정은
내부 이름을 보는데 클라이언트가 받는 타입은 한국어고, 리피트볼은 도감
기록을, 레벨볼은 파티 선두를 봐야 한다.

가진 볼만 보여준다. 스무 줄 중 열다섯 줄이 죽은 줄이면 메뉴가 아니라
카탈로그다. 대신 '지금 제일 잘 듣는데 없는 볼' 은 맨 아래 한 줄로
알려준다 - 그런 볼이 있다는 걸 알아야 다음에 상점에서 사 온다.

**상점으로 가는 줄은 없다** (1.12.1). 있었을 때는 야생을 앞에 두고(배틀
중에도) 상점에서 볼을 사 와서 바로 던질 수 있었다.

**맨 위의 '잡힐 때까지 계속 던지기' (2.1.1, 게시판 #425)** 는 auto 를 넘길 때 나온다 - 배틀 밖 야생, 그리고 2.1.3 부터
배틀 중에도 (게시판 #446). 켜고 끄는 줄일 뿐 던지지는 않는다 - 켜 두면 볼을 던졌을 때 같은 볼로 잡힐 때까지 이어
던진다 (배틀 밖은 wild_ui, 배틀 중은 멈춘 동안만 desktop_battle).
"""

AUTO_TEXT = "잡힐 때까지 계속 던지기"
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


def build(root, options, on_pick, auto=None, on_auto=None):
    """메뉴를 만들어 돌려준다. 띄우는 건 부르는 쪽에서 한다. auto = 계속 던지기가 켜져 있나 (None 이면 그 줄 없음)."""
    m = tk.Menu(root, tearoff=0, bg=U.BG2, fg=U.FG,
                activebackground=U.BG4, activeforeground=U.FG,
                bd=0, font=U.FONT_S)
    if auto is not None and on_auto:
        m.add_command(label=("☑ " if auto else "☐ ") + AUTO_TEXT, command=on_auto)
        m.add_separator()
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
    return m


def rows(options, on_pick, auto=None, on_auto=None):
    """`build` 와 같은 내용을 ui_common.PopupMenu 가 받는 줄 목록으로.

    맥에서는 `tk.Menu` 를 쓸 수 없다. aqua 에서 그것은 NSMenu 이고,
    NSMenu 가 열리면 중첩 런루프가 돌면서 Tk 의 after 타이머와 부딪혀
    앱이 통째로 죽는다 (tray_mac 의 첫 주석을 보라).

    tk.Menu 의 accelerator(오른쪽 끝에 붙는 작은 글씨)는 없으므로 배율과
    이유를 라벨 뒤에 이어 붙인다.
    """
    def line(left, right):
        return left + ("   " + right if right else "")

    have = [o for o in options if o["count"] > 0 and o["id"] != MASTER]
    best = next((o for o in have if o.get("best")), None)
    out = []
    if auto is not None and on_auto:
        out.append({"text": ("☑ " if auto else "☐ ") + AUTO_TEXT, "command": on_auto})
        out.append(None)
    if best:
        out.append({"text": "추천   " + line(*_label(best)), "bold": True,
                    "command": (lambda i=best["id"]: on_pick(i))})
        out.append(None)
    if not have:
        out.append({"text": "던질 볼이 없습니다", "enabled": False})
    for o in have:
        out.append({"text": line(*_label(o)),
                    "command": (lambda i=o["id"]: on_pick(i))})

    mb = next((o for o in options if o["id"] == MASTER and o["count"] > 0),
              None)
    if mb:
        out.append(None)
        out.append({"text": "마스터볼  %d개  (반드시 잡힘)" % mb["count"],
                    "command": lambda: on_pick(MASTER)})

    want = [o for o in options
            if o["count"] == 0 and o["mult"] > 1.5 and o["id"] != MASTER]
    if want:
        top = max(want, key=lambda o: o["mult"])
        out.append(None)
        out.append({"text": "지금은 %s 이(가) 잘 듣습니다 (없음)" % top["kr"],
                    "enabled": False})
    return out


def popup(root, event, options, on_pick, on_close=None, auto=None, on_auto=None):
    """on_close: 메뉴가 닫히면(골랐든 안 골랐든) 한 번 부른다. 배틀이 그동안 멈춘다.
    auto · on_auto: 맨 위 '잡힐 때까지 계속 던지기' 줄 (배틀 밖 야생 · 2.1.3 부터 배틀 중에도)."""
    from . import platform_os as PLAT
    if not PLAT.NATIVE_MENU:
        # 맥. tk.Menu 는 NSMenu 라 여는 순간 앱이 죽는다.
        return U.PopupMenu(root, rows(options, on_pick, auto, on_auto),
                           event.x_root, event.y_root, width=290,
                           on_close=on_close)
    m = build(root, options, on_pick, auto, on_auto)
    try:
        # 윈도우의 tk_popup 은 메뉴가 닫힐 때까지 돌아오지 않는다
        m.tk_popup(event.x_root, event.y_root)
    finally:
        m.grab_release()
        if on_close:
            on_close()
    return m
