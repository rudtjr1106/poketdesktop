# -*- coding: utf-8 -*-
"""플라티나 테마의 레이드 배틀 창 - 여럿이 보스 하나를 상대한다.

위 장면은 관장 배틀과 같은 시안의 하늘 · 발판 (battle.backdrop · platform):

    맨 위     보스 이름표 (이름표와 같은 옅은 흰 판 · 3px 테) - 이름 · Lv / 라운드, 공용 체력(진회색 홈),
              그 밑에 보호막(파랑), 아랫줄 왼쪽에 보호막 글, 가운데 상태 이상 · 능력 변화, 오른쪽에 체력 숫자
    가운데    보스 (연둣빛 발판)
    아래      참가자마다 작은 흰 판(이름 · 체력 · 고름/전멸/물러남)과 발판. 내 판은 하늘색 테.

글상자 · 아래 화면은 battle.PtLower ('기권' 자리가 '물러나기' - DP 레이드 창 그대로). 글은 기본 창의 _paint 가
고친다 - DP 레이드 창과 같은 이름의 도형을 만들어 둔다.
"""
import tkinter as tk

from ..dp import kit
from ..dp import raid_battle as DPR
from ..dp.battle import F, U, hp_colors, mix
from . import CYAN, DIM, INK, RIM, STEEL
from .battle import GROOVE, PtLower, backdrop, hp_box, hp_groove, platform

BOSS = DPR.BOSS
SHIELD, SHIELD_LO = DPR.SHIELD, DPR.SHIELD_LO


class RaidBattleWindow(PtLower, DPR.RaidBattleWindow):

    def _commands(self):
        PtLower._commands(self)
        self.leave_btn = self.forfeit_btn            # (기본 창의 동작 코드가 이 이름으로 부른다)

    # ---------------- 위 장면
    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, self.scene_h
        cv = getattr(self, "cv", None)
        if cv is None:
            cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg="#cfe9f7", highlightthickness=0)
            cv.pack(fill="x")
            self.cv = cv
        else:
            cv.delete("all")
            cv.configure(width=self.sw, height=self.sh)
        try:
            self.win.configure(bg=STEEL, highlightbackground=RIM)
        except tk.TclError:
            pass
        sw, sh = self.sw, self.sh
        backdrop(cv, sw, sh)

        # 보스 이름표 (맨 위, 창 너비만큼)
        x1, y1 = s(12), s(8)
        x2, y2 = sw - s(12), s(8) + s(64)
        hp_box(cv, x1, y1, x2, y2)
        lx, rx = x1 + s(18), x2 - s(18)
        self.boss_name = cv.create_text(lx, y1 + s(16), anchor="w", fill=INK, font=F(12), text="")
        self.round_text = cv.create_text(rx, y1 + s(16), anchor="e", fill=DIM, font=F(9), text="")
        bx0, by0, bh = lx, y1 + s(26), s(12)
        hp_groove(cv, bx0, by0, rx, by0 + bh)
        tx0 = bx0 + s(3)
        self.hp_geom = (tx0, by0 + s(3), rx - s(3) - tx0, bh - s(6))
        self.hp_bar = cv.create_rectangle(0, 0, 0, 0, fill=hp_colors(1.0)[0], outline="")
        self.hp_bar2 = cv.create_rectangle(0, 0, 0, 0, fill=hp_colors(1.0)[1], outline="")
        sy = by0 + bh + s(3)
        self.shield_geom = (tx0, sy, rx - s(3) - tx0, s(5))
        self.shield_bg = cv.create_rectangle(tx0, sy, rx - s(3), sy + s(5), fill="#c8d4e4", outline="",
                                             state="hidden")
        self.shield_bar = cv.create_rectangle(tx0, sy, rx - s(3), sy + s(5), fill=SHIELD, outline="",
                                              state="hidden")
        self.shield_text = cv.create_text(lx, y2 - s(13), anchor="w", fill=SHIELD_LO, font=F(8), text="")
        self.hp_text = cv.create_text(rx, y2 - s(13), anchor="e", fill=INK, font=F(9), text="")

        # 보스
        self.boss_pos = (sw // 2, int(sh * 0.56))
        bxp, byp = self.boss_pos
        platform(cv, bxp, byp, s(150), s(24))
        self.sprite = {BOSS: cv.create_image(bxp, byp + s(6), anchor="s")}
        self.status_text = cv.create_text(sw // 2, y2 - s(13), fill="#2860c0", font=F(9), text="")
        self.slots = {}
        self._seats()
        self.banner = []

    def _seats(self):
        """아래쪽 참가자 판 (DP 레이드 창과 같은 자리). 내 판은 하늘색 테."""
        s = U.h
        cv = self.cv
        n = max(1, self._n())
        cell = self.sw / float(n)
        for i in range(n):
            cx = int(cell * (i + 0.5))
            base = int(self.sh * 0.965)
            platform(cv, cx, base, s(46), s(10))
            self.sprite[i] = cv.create_image(cx, base + s(4), anchor="s")
            w = min(int(cell * 0.66), s(220))
            hp_y = int(self.sh * 0.705)
            top, bot = int(self.sh * 0.68) - s(12), hp_y + s(19) + s(10)
            mine = i == self.me
            hp_box(cv, cx - w // 2 - s(10), top, cx + w // 2 + s(10), bot, edge=CYAN if mine else RIM)
            name = cv.create_text(cx, int(self.sh * 0.68), fill=INK, font=F(9), text="")
            bg = cv.create_rectangle(cx - w // 2, hp_y, cx + w // 2, hp_y + s(7), fill=GROOVE, outline=GROOVE)
            bar = cv.create_rectangle(cx - w // 2, hp_y, cx + w // 2, hp_y + s(7), fill=hp_colors(1.0)[0],
                                      outline="")
            mark = cv.create_text(cx, hp_y + s(19), fill=DIM, font=F(8), text="")
            self.slots[i] = {"cx": cx, "name": name, "bar": bar, "bg": bg,
                             "mark": mark, "geom": (cx - w // 2, hp_y, w, s(7))}

    def _flash(self, text, color="#ffe6b8"):
        """알림 (라운드 시작 · 보호막 · 분노 · 메가진화): 장면 가운데의 흰 판, 테는 그 알림의 빛깔."""
        s = U.h
        cv = self.cv
        f = F(11)
        tw = max(s(260), kit.tkfont_of(cv, f).measure(text) + s(40))
        y = int(self.sh * 0.30)
        x1, x2 = self.sw // 2 - tw // 2, self.sw // 2 + tw // 2
        tag = "flash%d" % len(self.banner)
        hp_box(cv, x1, y, x2, y + s(38), tags=(tag,), edge=mix(color, "#000000", 0.35))
        kit.text(cv, self.sw // 2, y + s(19), text, f, fill=INK, anchor="center", tags=(tag,))
        self.banner.append(tag)

        def gone():
            try:
                cv.delete(tag)
            except tk.TclError:
                pass
        self.later(1500, gone)


