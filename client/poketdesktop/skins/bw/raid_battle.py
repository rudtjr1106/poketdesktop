# -*- coding: utf-8 -*-
"""블랙·화이트 테마의 레이드 배틀 창 - 여럿이 보스 하나를 상대한다.

시안 H 의 배틀 장면을 그대로 쓴다: 어두운 장면(위 가운데 하늘빛) · 어두운 받침 · 검정 반투명 이름표.

    맨 위     보스 판 - 이름 · Lv / 라운드, 가는 체력 막대, 그 밑에 보호막(하늘 파랑), 아랫줄에 보호막 글 ·
              상태 이상 · 능력 변화 · 체력 숫자
    가운데    보스 (어두운 받침)
    아래      참가자마다 작은 이름표(이름 · 체력 · 고름/전멸/물러남)와 받침. 내 판은 하늘빛 테.

글상자 · 아래 화면은 battle.BWLower ('기권' 자리가 '물러나기'). 보스 판 · 참가자 판의 글은 기본 창의 _paint 가
고친다 - 같은 이름의 도형을 만들어 두고 빛깔만 BW 로 칠한다. 흐름은 DP 레이드 창 그대로다.
"""
import tkinter as tk

from ..dp import kit
from ..dp import raid_battle as DPR
from . import BG, CYAN, DEEP, DIMT, HP_TRACK, LINE, PANEL_HI, PLATE_BG, STAGE_TOP, TEXT, mix
from ..dp.battle import hp_colors
from .battle import F, U, BWLower, name_plate, pad, stage_photo

SHIELD, SHIELD_INK = "#5aa6f2", "#8fc4f7"


class RaidBattleWindow(BWLower, DPR.RaidBattleWindow):

    def _commands(self):
        BWLower._commands(self)
        self.leave_btn = self.forfeit_btn            # (기본 창의 동작 코드가 이 이름으로 부른다)

    # ---------------- 위 화면
    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, self.scene_h
        cv = getattr(self, "cv", None)
        if cv is None:
            cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg=STAGE_TOP, highlightthickness=0)
            cv.pack(fill="x")
            self.cv = cv
        else:
            cv.delete("all")
            cv.configure(width=self.sw, height=self.sh)
        try:
            self.win.configure(bg=BG, highlightbackground=DEEP)
        except tk.TclError:
            pass
        sw, sh = self.sw, self.sh
        self._stage = stage_photo(sw, sh)
        cv.create_image(0, 0, image=self._stage, anchor="nw")

        # 보스 판 (맨 위, 창 너비만큼)
        x1, y1 = s(12), s(8)
        x2, y2 = sw - s(12), s(8) + s(63)
        name_plate(cv, x1, y1, x2, y2)
        lx, rx = x1 + s(16), x2 - s(16)
        self.boss_name = cv.create_text(lx, y1 + s(15), anchor="w", fill=TEXT, font=F(12), text="")
        self.round_text = cv.create_text(rx, y1 + s(15), anchor="e", fill=DIMT, font=F(9), text="")
        bx0, by0, bh = lx, y1 + s(27), s(8)
        bw = rx - lx
        kit.rrect(cv, bx0, by0, bx0 + bw, by0 + bh, s(4), fill=HP_TRACK)
        tx0 = bx0 + s(1)
        self.hp_geom = (tx0, by0 + s(1), bw - s(2), bh - s(2))
        self.hp_bar = cv.create_rectangle(0, 0, 0, 0, fill=hp_colors(1.0)[0], outline="")
        self.hp_bar2 = cv.create_rectangle(0, 0, 0, 0, fill=hp_colors(1.0)[1], outline="")
        # 보호막: 체력 막대 바로 밑의 가는 막대 (있을 때만)
        sy = by0 + bh + s(3)
        self.shield_geom = (tx0, sy, bw - s(2), s(5))
        self.shield_bg = cv.create_rectangle(tx0, sy, tx0 + bw - s(2), sy + s(5), fill=PANEL_HI, outline="",
                                             state="hidden")
        self.shield_bar = cv.create_rectangle(tx0, sy, tx0 + bw - s(2), sy + s(5), fill=SHIELD, outline="",
                                              state="hidden")
        self.shield_text = cv.create_text(lx, y2 - s(11), anchor="w", fill=SHIELD_INK, font=F(8), text="")
        self.hp_text = cv.create_text(rx, y2 - s(11), anchor="e", fill=TEXT, font=F(9), text="")

        # 보스
        self.boss_pos = (sw // 2, int(sh * 0.56))
        bxp, byp = self.boss_pos
        pad(cv, bxp, byp, s(150), s(24))
        self.sprite = {DPR.BOSS: cv.create_image(bxp, byp + s(6), anchor="s")}
        self.status_text = cv.create_text(sw // 2, y2 - s(11), fill="#7aa8f5", font=F(9), text="")
        self.slots = {}
        self._seats()
        self.banner = []

    def _seats(self):
        """아래쪽 참가자 판. 인원수에 맞춰 나눈다 (기본 창과 같은 자리 - 도트가 글을 안 가린다)."""
        s = U.h
        cv = self.cv
        n = max(1, self._n())
        cell = self.sw / float(n)
        for i in range(n):
            cx = int(cell * (i + 0.5))
            base = int(self.sh * 0.965)
            pad(cv, cx, base, s(46), s(10))
            self.sprite[i] = cv.create_image(cx, base + s(4), anchor="s")
            w = min(int(cell * 0.66), s(220))
            hp_y = int(self.sh * 0.705)
            top, bot = int(self.sh * 0.68) - s(12), hp_y + s(19) + s(10)
            mine = i == self.me
            name_plate(cv, cx - w // 2 - s(10), top, cx + w // 2 + s(10), bot, edge=CYAN if mine else LINE)
            name = cv.create_text(cx, int(self.sh * 0.68), fill=TEXT, font=F(9), text="")
            bg = cv.create_rectangle(cx - w // 2, hp_y, cx + w // 2, hp_y + s(7), fill=HP_TRACK, outline="")
            bar = cv.create_rectangle(cx - w // 2, hp_y, cx + w // 2, hp_y + s(7), fill=hp_colors(1.0)[0],
                                      outline="")
            mark = cv.create_text(cx, hp_y + s(19), fill=DIMT, font=F(8), text="")
            self.slots[i] = {"cx": cx, "name": name, "bar": bar, "bg": bg,
                             "mark": mark, "geom": (cx - w // 2, hp_y, w, s(7))}

    def _flash(self, text, color="#ffe6b8"):
        """알림 (라운드 시작 · 보호막 · 분노 · 메가진화): 장면 가운데의 어두운 판, 테는 그 알림의 빛깔."""
        s = U.h
        cv = self.cv
        f = F(11)
        tw = max(s(260), kit.tkfont_of(cv, f).measure(text) + s(40))
        y = int(self.sh * 0.30)
        x1, x2 = self.sw // 2 - tw // 2, self.sw // 2 + tw // 2
        tag = "flash%d" % len(self.banner)
        color = mix(color, "#ffffff", 0.04)     # (DP 빛깔 표에 든 빛깔이면 어두운 테마 쪽으로 옮겨지므로 살짝 비켜 둔다)
        kit.rrect(cv, x1 - s(3), y - s(3), x2 + s(3), y + s(39), s(12), fill=mix(PLATE_BG, color, 0.25), tags=(tag,))
        kit.rrect(cv, x1, y, x2, y + s(36), s(10), fill=PLATE_BG, outline=color, width=2, tags=(tag,))
        cv.create_text(self.sw // 2, y + s(18), text=text, fill=TEXT, font=f, anchor="center", tags=(tag,))
        self.banner.append(tag)

        def gone():
            try:
                cv.delete(tag)
            except tk.TclError:
                pass
        self.later(1500, gone)
