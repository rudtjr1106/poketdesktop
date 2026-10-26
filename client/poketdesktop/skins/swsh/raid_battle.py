# -*- coding: utf-8 -*-
"""소드·실드 테마의 레이드 배틀 창 - 시안 K 의 배틀 언어로 (DP 레이드 창의 배치 그대로).

    위 화면    차분한 남색 (빗금 없음) + 왼쪽 위 작은 하늘색 모서리. 맨 위 보스 판은 남색 판 · 흰 테 (흰 이름 · 옅은 라운드,
               남빛 홈의 체력 막대 · 그 밑 보호막(하늘색), 아랫줄에 보호막 글 · 상태 · 체력 숫자).
               보스 · 참가자 발밑은 옅은 그림자 (받침 대신). 참가자 판은 작은 남색 판 (내 판은 분홍 테).
    알림       장면 가운데의 남색 판 (테는 그 알림의 빛깔).
    글상자 · 아래 화면은 battle.SwLower ('기권' 자리는 '물러나기' - DP 레이드 창 그대로).

보스 이름표 · 참가자 판의 글은 기본 창의 _paint 가 고친다 - 같은 이름의 도형을 만들어 둔다.
"""
import tkinter as tk

from ..dp import raid_battle as DPR
from ..dp.battle import HP_COLORS
from ..dp import kit
from . import CYAN, MAG, NAVY, ON_NAVY_DIM
from .battle import F, TRACK, U, SwLower, hp_colors, mix, navy_plate, scene_bg, shadow

BOSS = DPR.BOSS


class RaidBattleWindow(SwLower, DPR.RaidBattleWindow):

    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, self.scene_h
        cv = getattr(self, "cv", None)
        if cv is None:
            cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg=NAVY, highlightthickness=0)
            cv.pack(fill="x")
            self.cv = cv
        else:
            cv.delete("all")
            cv.configure(width=self.sw, height=self.sh, bg=NAVY)
        try:
            self.win.configure(bg=NAVY, highlightbackground=NAVY)
        except tk.TclError:
            pass
        sw, sh = self.sw, self.sh
        scene_bg(cv, sw, sh, sh + U.h(self.ZOOM_MSG) + U.h(self.ZOOM_CMD))

        # 보스 판 (맨 위, 창 너비만큼)
        x1, y1 = s(14), s(8)
        x2, y2 = sw - s(14), s(8) + s(64)
        navy_plate(cv, x1, y1, x2, y2, s(12))
        lx, rx = x1 + s(18), x2 - s(18)
        self.boss_name = cv.create_text(lx, y1 + s(16), anchor="w", fill="#ffffff", font=F(12), text="")
        self.round_text = cv.create_text(rx, y1 + s(16), anchor="e", fill=ON_NAVY_DIM, font=F(9), text="")
        bx0, by0, bh = lx, y1 + s(28), s(9)
        kit.rrect(cv, bx0, by0, rx, by0 + bh, bh // 2, fill=TRACK)
        tx0 = bx0 + s(2)
        self.hp_geom = (tx0, by0 + s(2), rx - s(2) - tx0, bh - s(4))
        self.hp_bar = cv.create_rectangle(0, 0, 0, 0, fill=hp_colors(1.0)[0], outline="")
        self.hp_bar2 = cv.create_rectangle(0, 0, 0, 0, fill=hp_colors(1.0)[1], outline="")
        # 보호막: 체력 막대 바로 밑의 가는 하늘색 막대 (있을 때만)
        sy = by0 + bh + s(3)
        self.shield_geom = (tx0, sy, rx - s(2) - tx0, s(5))
        self.shield_bg = cv.create_rectangle(tx0, sy, rx - s(2), sy + s(5), fill=TRACK, outline="",
                                             state="hidden")
        self.shield_bar = cv.create_rectangle(tx0, sy, rx - s(2), sy + s(5), fill=CYAN, outline="",
                                              state="hidden")
        self.shield_text = cv.create_text(lx, y2 - s(12), anchor="w", fill="#8fdcf8", font=F(8), text="")
        self.hp_text = cv.create_text(rx, y2 - s(12), anchor="e", fill="#ffffff", font=F(9), text="")

        # 보스
        self.boss_pos = (sw // 2, int(sh * 0.56))
        bxp, byp = self.boss_pos
        shadow(cv, bxp, byp, s(96), s(12))
        self.sprite = {BOSS: cv.create_image(bxp, byp + s(6), anchor="s")}
        self.status_text = cv.create_text(sw // 2, y2 - s(12), fill="#8fdcf8", font=F(9), text="")
        self.slots = {}
        self._seats()
        self.banner = []

    def _seats(self):
        """아래쪽 참가자 판 (작은 남색 판, 내 판은 분홍 테). 자리는 DP 와 같다 - 도트가 글을 안 가린다."""
        s = U.h
        cv = self.cv
        n = max(1, self._n())
        cell = self.sw / float(n)
        for i in range(n):
            cx = int(cell * (i + 0.5))
            base = int(self.sh * 0.965)
            shadow(cv, cx, base, s(40), s(8))
            self.sprite[i] = cv.create_image(cx, base + s(4), anchor="s")
            w = min(int(cell * 0.66), s(220))
            hp_y = int(self.sh * 0.705)
            top, bot = int(self.sh * 0.68) - s(13), hp_y + s(19) + s(10)
            mine = i == self.me
            navy_plate(cv, cx - w // 2 - s(12), top, cx + w // 2 + s(12), bot, s(10), line=MAG if mine else "#ffffff")
            name = cv.create_text(cx, int(self.sh * 0.68), fill="#ffffff", font=F(9), text="")
            bg = cv.create_rectangle(cx - w // 2, hp_y, cx + w // 2, hp_y + s(7), fill=TRACK, outline="")
            bar = cv.create_rectangle(cx - w // 2, hp_y, cx + w // 2, hp_y + s(7), fill=HP_COLORS[0][1],
                                      outline="")
            mark = cv.create_text(cx, hp_y + s(19), fill=ON_NAVY_DIM, font=F(8), text="")
            self.slots[i] = {"cx": cx, "name": name, "bar": bar, "bg": bg,
                             "mark": mark, "geom": (cx - w // 2, hp_y, w, s(7))}

    def _flash(self, text, color="#ffe6b8"):
        """알림 (라운드 시작 · 보호막 · 분노 · 메가진화): 장면 가운데의 남색 판, 테는 그 알림의 빛깔."""
        s = U.h
        cv = self.cv
        f = F(11)
        tw = max(s(260), kit.tkfont_of(cv, f).measure(text) + s(40))
        y = int(self.sh * 0.30)
        x1, x2 = self.sw // 2 - tw // 2, self.sw // 2 + tw // 2
        tag = "flash%d" % len(self.banner)
        navy_plate(cv, x1, y, x2, y + s(38), s(19), line=mix(color, "#ffffff", 0.2), tags=(tag,))
        kit.text(cv, self.sw // 2, y + s(19), text, f, fill="#ffffff", anchor="center", tags=(tag,))
        self.banner.append(tag)

        def gone():
            try:
                cv.delete(tag)
            except tk.TclError:
                pass
        self.later(1500, gone)
