# -*- coding: utf-8 -*-
"""금·은 테마의 레이드 배틀 창 - 여럿이 보스 하나를 상대한다. 관장 배틀과 같은 시안 G 의 한 화면:

    맨 위     보스 이름표 (ㄴ자 선 - 왼쪽 · 아래): 이름 · Lv / 라운드, 금빛 'HP' 꼬리표 + 진한 테의 흰 막대,
              그 밑에 보호막(파랑 - 있을 때만), 아랫줄 왼쪽 보호막 글 · 가운데 상태 · 오른쪽 체력 숫자
    가운데    보스 (받침 없이 종이빛 위)
    아래      참가자마다 작은 이름표 (ㄴ자 선, 내 것은 빨간 선): 이름 · 체력 막대 · 고름/전멸/물러남

글상자 · 명령 상자는 battle.GBLower ('기권' 자리가 '물러나기'). 보스 이름표 · 참가자 판의 글은 기본 창의
_paint 가 고친다 - DP 와 같은 이름의 도형을 만들어 둔다 (skins/dp/raid_battle.py).
"""
import tkinter as tk

from ..dp import kit
from ..dp import raid_battle as DPR
from ..dp.battle import F, U, hp_colors
from . import DIM, INK, INK2, PAPER, RED
from .battle import GBLower, bk, hp_bar
from ._gbc import gbox

SHIELD, SHIELD_LO = "#6aa8f0", "#3a78c8"


class RaidBattleWindow(GBLower, DPR.RaidBattleWindow):

    # ---------------- 위 화면
    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, self.scene_h
        cv = getattr(self, "cv", None)
        if cv is None:
            cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg=PAPER, highlightthickness=0)
            cv.pack(fill="x")
            self.cv = cv
        else:
            cv.delete("all")
            cv.configure(width=self.sw, height=self.sh, bg=PAPER)
        try:
            self.win.configure(bg=INK, highlightbackground=INK)
        except tk.TclError:
            pass
        sw, sh = self.sw, self.sh
        cv.create_rectangle(0, 0, sw, sh, fill=PAPER, outline="")

        # 보스 이름표 (창 폭 가득, ㄴ자 선)
        x1, y1 = s(14), s(8)
        x2, y2 = sw - s(14), s(8) + s(66)
        lw = max(2, s(3))
        cv.create_rectangle(x1, y1 + s(4), x1 + lw, y2, fill=INK, outline="")
        cv.create_rectangle(x1, y2 - lw, x2, y2, fill=INK, outline="")
        lx, rx = x1 + lw + s(12), x2 - s(4)
        self.boss_name = cv.create_text(lx, y1 + s(13), anchor="w", fill=INK, font=F(13), text="")
        self.round_text = cv.create_text(rx, y1 + s(13), anchor="e", fill=INK2, font=F(10), text="")
        gx, gy, gw, gh = hp_bar(cv, lx, y1 + s(25), rx, y1 + s(39))
        self.hp_geom = (gx, gy, gw, gh)
        self.hp_bar = cv.create_rectangle(0, 0, 0, 0, fill=hp_colors(1.0)[0], outline="")
        self.hp_bar2 = cv.create_rectangle(0, 0, 0, 0, fill=hp_colors(1.0)[1], outline="")
        sy = y1 + s(41)
        self.shield_geom = (gx, sy, gw, s(5))
        self.shield_bg = cv.create_rectangle(gx, sy, gx + gw, sy + s(5), fill="#d8e0ec", outline="", state="hidden")
        self.shield_bar = cv.create_rectangle(gx, sy, gx + gw, sy + s(5), fill=SHIELD, outline="", state="hidden")
        ty = y2 - lw - s(10)
        self.shield_text = cv.create_text(lx, ty, anchor="w", fill=SHIELD_LO, font=F(8), text="")
        self.hp_text = cv.create_text(rx, ty, anchor="e", fill=INK, font=F(10), text="")

        # 보스
        self.boss_pos = (sw // 2, int(sh * 0.56))
        bxp, byp = self.boss_pos
        self.sprite = {DPR.BOSS: cv.create_image(bxp, byp + s(6), anchor="s")}
        self.status_text = cv.create_text(sw // 2, ty, fill="#2860c0", font=F(9), text="")
        self.slots = {}
        self._seats()
        self.banner = []

    def _seats(self):
        """아래쪽 참가자 이름표 (ㄴ자 선, 내 것은 빨간 선). 자리는 DP 와 같다 - 도트가 글을 안 가린다."""
        s = U.h
        cv = self.cv
        n = max(1, self._n())
        cell = self.sw / float(n)
        lw = max(2, s(2))
        for i in range(n):
            cx = int(cell * (i + 0.5))
            base = int(self.sh * 0.965)
            self.sprite[i] = cv.create_image(cx, base + s(4), anchor="s")
            w = min(int(cell * 0.66), s(220))
            hp_y = int(self.sh * 0.705)
            top, bot = int(self.sh * 0.68) - s(12), hp_y + s(19) + s(10)
            mine = i == self.me
            line = RED if mine else INK
            x1, x2 = cx - w // 2 - s(10), cx + w // 2 + s(10)
            cv.create_rectangle(x1, top, x2, bot, fill=PAPER, outline="")
            cv.create_rectangle(x1, top + s(2), x1 + lw, bot, fill=line, outline="")
            cv.create_rectangle(x1, bot - lw, x2, bot, fill=line, outline="")
            name = cv.create_text(cx, int(self.sh * 0.68), fill=INK, font=F(9), text="")
            bg = cv.create_rectangle(cx - w // 2, hp_y, cx + w // 2, hp_y + s(7), fill="#ffffff", outline=INK,
                                     width=max(1, s(1.5)))
            bar = cv.create_rectangle(cx - w // 2, hp_y, cx + w // 2, hp_y + s(7), fill=hp_colors(1.0)[0],
                                      outline="")
            mark = cv.create_text(cx, hp_y + s(19), fill=DIM, font=F(8), text="")
            self.slots[i] = {"cx": cx, "name": name, "bar": bar, "bg": bg,
                             "mark": mark, "geom": (cx - w // 2, hp_y, w, s(7))}

    def _flash(self, text, color="#ffe6b8"):
        """알림 (라운드 시작 · 보호막 · 분노 · 메가진화): 장면 가운데의 두 겹 테 상자, 금빛 줄 대신 그 알림의 빛깔."""
        s = U.h
        cv = self.cv
        f = F(11)
        tw = max(s(260), kit.tkfont_of(cv, f).measure(text) + s(48))
        y = int(self.sh * 0.30)
        x1, x2 = self.sw // 2 - tw // 2, self.sw // 2 + tw // 2
        tag = "flash%d" % len(self.banner)
        gbox(cv, x1, y, x2, y + s(40), tags=(tag,), k=bk(), inner=color)
        kit.text(cv, self.sw // 2, y + s(20), text, f, anchor="center", tags=(tag,))
        self.banner.append(tag)

        def gone():
            try:
                cv.delete(tag)
            except tk.TclError:
                pass
        self.later(1500, gone)

