# -*- coding: utf-8 -*-
"""에메랄드 테마의 '위젯 빛깔' - DP 의 것(skins/dp/widgets.py)을 그대로 걸고, 두 가지를 더한다.

    1. DP 부품(kit)을 시안 A 의 GBA 모양으로 바꿔 끼운다 (gba.patch_kit) - 판 · 글상자 · 단추 · 입력칸 ·
       굴림 막대. 따로 그리지 않은 화면(길드 · 게시판 · 박스 · 상점 …)도 남색 테의 종이 창이 된다.
    2. ttk 빛깔(묻는 창의 바탕 등)을 이 테마 바탕으로. (ttk 는 derive 의 빛깔 옮기기 자리를 안 지난다)

뜨는 메뉴(ui_common.PopupMenu)는 DP 처럼 기본 테마 그대로 둔다.
"""
import tkinter as tk

from ..dp import widgets as DPW
from . import INK_A, LIGHT, NAVY, PAPER, RED, SELY, WIN
from . import gba


def install(root, style):
    gba.patch_kit()
    DPW.install(root, style)
    try:
        style.configure(".", background=WIN, foreground=INK_A)
        style.configure("TFrame", background=WIN)
        style.configure("TLabel", background=WIN, foreground=INK_A)
        style.configure("TScrollbar", background="#56648a", troughcolor="#dce8f0", arrowcolor=NAVY)
        style.map("TScrollbar", background=[("active", NAVY)])
        style.configure("TNotebook", background=WIN, bordercolor=WIN, lightcolor=WIN, darkcolor=WIN)
        style.configure("TNotebook.Tab", background="#c2e2d6", foreground=INK_A, bordercolor=NAVY, darkcolor=WIN)
        style.map("TNotebook.Tab", background=[("selected", PAPER), ("active", SELY)],
                  foreground=[("selected", RED), ("active", INK_A)],
                  lightcolor=[("selected", PAPER), ("", LIGHT)])
    except tk.TclError:
        pass
