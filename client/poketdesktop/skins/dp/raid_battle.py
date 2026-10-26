# -*- coding: utf-8 -*-
"""DP 테마의 레이드 배틀 창 - 여럿이 보스 하나를 상대한다.

위 화면은 관장 배틀과 같은 하늘 · 풀밭이다.

    맨 위     흰 판 하나 - 보스 이름 · Lv / 라운드, 공용 체력 막대(진회색 통 · 'HP'), 그 밑에 보호막(파랑),
              아랫줄 왼쪽에 보호막 글, 가운데 상태 이상 · 능력 변화, 오른쪽에 체력 숫자
    가운데    보스 (황토 받침)
    아래      참가자마다 작은 흰 판(이름 · 체력 · 고름/전멸/물러남)과 받침. 내 판은 주황 테.

글상자 · 아래 화면은 battle.DPLower 그대로 ('기권' 자리가 '물러나기').
보스 이름표 · 참가자 판의 글은 기본 창의 _paint 가 고친다 - 같은 이름의 도형을 만들어 두고, 색만 DP 로 다시 칠한다.
"""
import tkinter as tk

from ... import ui_raid_battle as RB
from . import DIM, INK, PLATE_SEL, kit, tone
from .battle import (BAR_CASE, BAR_LABEL, BAR_TRACK, F, PLATE_EDGE, PLATE_FILL, DPLower, U, backdrop, hp_colors,
                     mix, platform)

BOSS = RB.BOSS
SHIELD, SHIELD_LO = "#6aa8f0", "#3a78c8"


class RaidBattleWindow(DPLower, RB.RaidBattleWindow):
    FORFEIT_TEXT = "물러나기"
    DONE_TEXT = "닫기"
    SWITCH_ASK = "누구로 바꿀까? 교체한 라운드에는 공격하지 못합니다."

    def _run_action(self):
        return self.leave

    def _commands(self):
        DPLower._commands(self)
        self.leave_btn = self.forfeit_btn            # (기본 창의 동작 코드가 이 이름으로 부른다)

    # ---------------- 위 화면
    def _scene(self):
        s = U.h
        self.sw, self.sh = self.ww - 4, self.scene_h
        cv = getattr(self, "cv", None)
        if cv is None:
            cv = tk.Canvas(self.win, width=self.sw, height=self.sh, bg="#5cb9a4", highlightthickness=0)
            cv.pack(fill="x")
            self.cv = cv
        else:
            cv.delete("all")
            cv.configure(width=self.sw, height=self.sh)
        try:
            self.win.configure(bg="#23262d", highlightbackground="#121418")
        except tk.TclError:
            pass
        sw, sh = self.sw, self.sh
        backdrop(cv, sw, sh)

        # 보스 판 (맨 위, 창 너비만큼)
        x1, y1 = s(10), s(6)
        x2, y2 = sw - s(10), s(6) + s(63)
        kit.rrect(cv, x1, y1, x2, y2, s(12), fill=PLATE_EDGE)
        kit.rrect(cv, x1 + s(3), y1 + s(3), x2 - s(3), y2 - s(3), s(9), fill=PLATE_FILL)
        lx, rx = x1 + s(16), x2 - s(16)
        self.boss_name = cv.create_text(lx, y1 + s(15), anchor="w", fill=INK, font=F(12), text="")
        self.round_text = cv.create_text(rx, y1 + s(15), anchor="e", fill="#606068", font=F(9), text="")
        bx0, by0, bh = lx, y1 + s(25), s(12)
        bw = rx - lx
        kit.rrect(cv, bx0, by0, bx0 + bw, by0 + bh, s(3), fill=BAR_CASE)
        cv.create_text(bx0 + s(5), by0 + bh / 2.0, text="HP", anchor="w", fill=BAR_LABEL, font=F(7))
        tx0 = bx0 + s(26)
        self.hp_geom = (tx0, by0 + s(3), bx0 + bw - s(3) - tx0, bh - s(6))
        cv.create_rectangle(tx0, by0 + s(3), bx0 + bw - s(3), by0 + bh - s(3), fill=BAR_TRACK, outline="")
        self.hp_bar = cv.create_rectangle(0, 0, 0, 0, fill=hp_colors(1.0)[0], outline="")
        self.hp_bar2 = cv.create_rectangle(0, 0, 0, 0, fill=hp_colors(1.0)[1], outline="")
        # 보호막: 체력 막대 바로 밑의 가는 파란 막대 (있을 때만)
        sy = by0 + bh + s(3)
        self.shield_geom = (tx0, sy, bx0 + bw - s(3) - tx0, s(5))
        self.shield_bg = cv.create_rectangle(tx0, sy, bx0 + bw - s(3), sy + s(5), fill="#c8d4e4", outline="",
                                             state="hidden")
        self.shield_bar = cv.create_rectangle(tx0, sy, bx0 + bw - s(3), sy + s(5), fill=SHIELD, outline="",
                                              state="hidden")
        self.shield_text = cv.create_text(lx, y2 - s(12), anchor="w", fill=SHIELD_LO, font=F(8), text="")
        self.hp_text = cv.create_text(rx, y2 - s(12), anchor="e", fill=INK, font=F(9), text="")

        # 보스
        self.boss_pos = (sw // 2, int(sh * 0.56))
        bxp, byp = self.boss_pos
        platform(cv, bxp, byp, s(150), s(24))
        self.sprite = {BOSS: cv.create_image(bxp, byp + s(6), anchor="s")}
        # 보스의 상태 이상 · 능력 변화는 보스 판 아랫줄 가운데 (받침 밑에 두면 가운데 참가자 판과 겹친다)
        self.status_text = cv.create_text(sw // 2, y2 - s(12), fill="#2860c0", font=F(9), text="")
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
            platform(cv, cx, base, s(46), s(10))
            self.sprite[i] = cv.create_image(cx, base + s(4), anchor="s")
            w = min(int(cell * 0.66), s(220))
            hp_y = int(self.sh * 0.705)
            top, bot = int(self.sh * 0.68) - s(12), hp_y + s(19) + s(10)
            mine = i == self.me
            kit.rrect(cv, cx - w // 2 - s(10), top, cx + w // 2 + s(10), bot, s(8),
                      fill=PLATE_SEL if mine else PLATE_EDGE)
            kit.rrect(cv, cx - w // 2 - s(10) + s(2), top + s(2), cx + w // 2 + s(10) - s(2), bot - s(2), s(6),
                      fill=PLATE_FILL)
            name = cv.create_text(cx, int(self.sh * 0.68), fill=INK, font=F(9), text="")
            bg = cv.create_rectangle(cx - w // 2, hp_y, cx + w // 2, hp_y + s(7), fill=BAR_TRACK, outline=BAR_CASE)
            bar = cv.create_rectangle(cx - w // 2, hp_y, cx + w // 2, hp_y + s(7), fill=hp_colors(1.0)[0],
                                      outline="")
            mark = cv.create_text(cx, hp_y + s(19), fill=DIM, font=F(8), text="")
            self.slots[i] = {"cx": cx, "name": name, "bar": bar, "bg": bg,
                             "mark": mark, "geom": (cx - w // 2, hp_y, w, s(7))}

    def _paint(self, key, hp=None):
        RB.RaidBattleWindow._paint(self, key, hp)
        it = self.slots.get(key) if key != BOSS else None
        if it:
            try:
                self.cv.itemconfigure(it["mark"], fill=tone(self.cv.itemcget(it["mark"], "fill")))
            except tk.TclError:
                pass

    def _boss_bar(self, hp, maxhp):
        x0, y0, bw, bh = self.hp_geom
        frac = max(0.0, min(1.0, float(hp) / float(maxhp or 1)))
        top, bot = hp_colors(frac)
        x1 = x0 + max(0, int(bw * frac))
        mid = y0 + bh // 2
        self.cv.coords(self.hp_bar, x0, y0, x1, mid)
        self.cv.coords(self.hp_bar2, x0, mid, x1, y0 + bh)
        self.cv.itemconfigure(self.hp_bar, fill=top, state="normal" if x1 > x0 else "hidden")
        self.cv.itemconfigure(self.hp_bar2, fill=bot, state="normal" if x1 > x0 else "hidden")
        self.cv.itemconfigure(self.hp_text, text="%s / %s" % (format(max(0, int(hp)), ","), format(int(maxhp), ",")))

    def _mon_bar(self, key, hp, maxhp):
        it = self.slots.get(key)
        if not it:
            return
        x0, y0, bw, bh = it["geom"]
        frac = max(0.0, min(1.0, float(hp) / float(maxhp or 1)))
        self.cv.coords(it["bar"], x0 + 1, y0 + 1, x0 + max(1, int(bw * frac)), y0 + bh)
        self.cv.itemconfigure(it["bar"], fill=hp_colors(frac)[1], state="normal" if frac > 0 else "hidden")

    def _flash(self, text, color="#ffe6b8"):
        """알림 (라운드 시작 · 보호막 · 분노 · 메가진화): 장면 가운데의 흰 판, 테두리는 그 알림의 색."""
        s = U.h
        cv = self.cv
        f = F(11)
        tw = max(s(260), kit.tkfont_of(cv, f).measure(text) + s(40))
        y = int(self.sh * 0.30)
        x1, x2 = self.sw // 2 - tw // 2, self.sw // 2 + tw // 2
        tag = "flash%d" % len(self.banner)
        edge = mix(color, "#000000", 0.35)
        kit.rrect(cv, x1, y, x2, y + s(36), s(10), fill=edge, tags=(tag,))
        kit.rrect(cv, x1 + s(3), y + s(3), x2 - s(3), y + s(33), s(8), fill=PLATE_FILL, tags=(tag,))
        kit.text(cv, self.sw // 2, y + s(18), text, f, anchor="center", tags=(tag,))
        self.banner.append(tag)

        def gone():
            try:
                cv.delete(tag)
            except tk.TclError:
                pass
        self.later(1500, gone)

    # ---------------- 아래 화면에 넘겨 주는 것
    def _paint_count(self, text):
        me = self.view.get("me") or {}
        self._teams = (me.get("team") or [], None)
        self._turn_text = text
        self._draw_strip()
