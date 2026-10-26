# -*- coding: utf-8 -*-
"""악당 출현 창 (시즌 4) — 관장 탭의 지도에서 검게 칠해진 곳을 누르면 뜬다.

하루에 한 번, 시·도 한 곳에 악당 조직이 나타난다 (서버 boss.py). 이 창은 그날의 간부 셋과
그 뒤에 숨은 전설, 그리고 내가 어디까지 했는지를 보여 주고 다음 승부를 연다.

  · 간부는 위에서부터 차례로 싸운다. 이긴 간부는 '이김', 지금 싸울 상대는 '도전', 나머지는 '잠김'.
  · 셋을 다 이기기 전에는 전설이 누구인지 안 보인다 ("???").
  · 승부는 관장 배틀 창(ui_gym_battle)이 그대로 한다 - 여기서는 열기만 한다.
    하던 판이 있으면 같은 단추가 '이어서 하기' 가 된다.

창은 내용만큼만 크다 (ui_box._shell + fit).
"""
import tkinter as tk

from PIL import ImageTk

from . import skins
from . import ui_common as U
from .ui_common import run_async

W = 500
THUMB = 56
DARK = "#0b0d13"            # 악당이 차지한 곳의 색 (지도도 이 색으로 칠한다)
EVIL = "#e5484d"
STATE = {"won": ("이김", U.GOOD), "next": ("도전", EVIL), "locked": ("잠김", U.FG_FAINT)}


def left_text(sec):
    """밤 11시(악당이 떠나는 때)까지 남은 시간."""
    sec = max(0, int(sec or 0))
    h, m = sec // 3600, (sec % 3600) // 60
    if h:
        return "%d시간 %d분" % (h, m)
    return "%d분" % max(1, m)


def action_of(card):
    """지금 누를 수 있는 것. (단추 글, 누를 수 있나, 그 아래 한 줄)"""
    if not card or not card.get("active"):
        return "", False, "지금은 악당이 나타나 있지 않습니다."
    lg = card.get("legend") or {}
    if card.get("done"):
        if lg.get("egg"):
            return "", False, "오늘의 악당을 물리치고 %s 의 알을 얻었다." % (lg.get("name") or "전설")
        return "", False, "오늘의 악당을 물리쳤다. 알은 나오지 않았다 - 내일 또 나타난다."
    if card.get("battle"):
        return "이어서 하기", True, "하던 승부가 남아 있습니다."
    if lg.get("open"):
        return "%s 와(과) 맞서기" % (lg.get("name") or "전설의 포켓몬"), True, \
            "볼은 던질 수 없다. 쓰러뜨리면 %d%% 로 알을 남긴다 (하루 한 번)." % int(card.get("eggRate") or 70)
    nxt = next((m for m in card.get("members") or [] if m.get("state") == "next"), None)
    if nxt:
        return "%s 와(과) 승부" % (nxt.get("name") or "간부"), True, \
            "상대의 포켓몬은 내 파티와 마릿수·레벨이 같고 개체값이 전부 31 이다."
    return "", False, ""


@skins.skinnable
class BossWindow(object):
    """gw 는 관장 창(GymWindow). 승부가 끝나면 이 창과 지도를 같이 다시 받는다."""

    def __init__(self, gw):
        from . import ui_box
        self.gw = gw
        self.app = gw.app
        self.root = gw.root
        self.alive = True
        self.card = None
        self.battle = None
        self.busy = False
        self.photos = {}
        self.go_btn = None
        self.top, f = ui_box._shell(gw.win.winfo_toplevel(), "악당 출현", W, U.h(260))
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.body = tk.Frame(f, bg=U.BG)
        self.body.pack(fill="both", expand=True)
        self.status = tk.Label(f, text=" ", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w",
                               justify="left", wraplength=W - 48)
        self.status.pack(fill="x", pady=(6, 0))
        self._loading()
        self.reload()

    # ---------------- 불러오기 ----------------
    def _loading(self):
        tk.Label(self.body, text="불러오는 중...", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(pady=24)

    def say(self, text, color=None):
        try:
            self.status.configure(text=text or " ", fg=color or U.FG_FAINT)
        except tk.TclError:
            pass

    def reload(self):
        def done(r, err):
            if not self.alive:
                return
            if err:
                return self.say("불러오지 못했습니다. %s" % getattr(err, "message", err), U.RED)
            self.card = r
            self.paint()
        run_async(self.root, self.app.api.boss, done)

    # ---------------- 그리기 ----------------
    def paint(self):
        from . import ui_box
        for w in self.body.winfo_children():
            w.destroy()
        self.go_btn = None
        c = self.card or {}
        if not c.get("active"):
            lab = tk.Label(self.body, text="지금은 악당이 나타나 있지 않습니다.\n악당은 시즌이 시작한 날부터 "
                                           "2주 동안, 하루에 한 번 오전 9시부터 낮 12시 사이에\n"
                                           "나타나 밤 11시까지 머뭅니다.",
                           bg=U.BG, fg=U.FG_DIM, font=U.FONT_S, justify="left", anchor="w")
            lab.pack(fill="x", pady=(4, 8))
            ui_box.fit(self.top)
            return
        head = tk.Frame(self.body, bg=DARK, highlightthickness=2, highlightbackground=EVIL)
        head.pack(fill="x")
        tk.Label(head, text=c.get("team") or "악당", bg=DARK, fg="#ffffff",
                 font=(U.FAMILY_BLACK, U.pt(16))).pack(anchor="w", padx=14, pady=(10, 0))
        tk.Label(head, text="%s 에 나타났다 · 밤 11시까지 %s" % (c.get("sidoName") or "", left_text(c.get("endsIn"))),
                 bg=DARK, fg="#c9cfdf", font=U.FONT_S).pack(anchor="w", padx=14, pady=(2, 10))

        box = tk.Frame(self.body, bg=U.BG2, highlightthickness=2, highlightbackground=U.LINE)
        box.pack(fill="x", pady=(10, 0))
        self.rows = []
        for i, m in enumerate(c.get("members") or []):
            if i:
                tk.Frame(box, bg=U.LINE, height=1).pack(fill="x", padx=12)
            self.rows.append(self._row(box, m.get("sprite"), m.get("role") or "", m.get("name") or "",
                                       m.get("state")))
        tk.Frame(box, bg=U.LINE, height=1).pack(fill="x", padx=12)
        lg = c.get("legend") or {}
        if lg.get("open"):
            state = "won" if lg.get("done") else "next"
            sub = " · ".join(lg.get("types") or []) or "전설의 포켓몬"
            self.rows.append(self._row(box, None, sub, lg.get("name") or "?", state, legend=lg))
        else:
            self.rows.append(self._row(box, None, "간부를 모두 이기면 모습을 드러낸다", "???", "locked"))

        text, can, note = action_of(c)
        foot = tk.Frame(self.body, bg=U.BG)
        foot.pack(fill="x", pady=(12, 0))
        if text:
            self.go_btn = U.PushButton(foot, text, self.challenge, height=38)
            self.go_btn.pack(side="right")
            if not can:
                self.go_btn.configure(state="disabled")
        lab = tk.Label(foot, text=note, bg=U.BG, fg=U.FG if c.get("done") else U.FG_DIM, font=U.FONT_S,
                       anchor="w", justify="left", wraplength=W - 48 - (190 if text else 0))
        lab.pack(side="left", fill="x", expand=True)
        self._thumbs()
        ui_box.fit(self.top)

    def _row(self, box, sprite, role, name, state, legend=None):
        row = tk.Frame(box, bg=U.BG2)
        row.pack(fill="x", padx=12, pady=8)
        # 도트 칸은 그림이 오기 전에도 같은 크기다 (그림이 뜨면서 줄이 밀리지 않게)
        holder = tk.Frame(row, bg=U.BG3, width=U.h(THUMB), height=U.h(THUMB))
        holder.pack_propagate(False)
        holder.pack(side="left")
        pic = tk.Label(holder, bg=U.BG3, bd=0, padx=0, pady=0, highlightthickness=0)
        pic.pack(expand=True)
        text, color = STATE.get(state, STATE["locked"])
        chip = tk.Label(row, text=text, bg=U.BG2, fg=color, font=U.FONT_B)
        chip.pack(side="right")
        mid = tk.Frame(row, bg=U.BG2)
        mid.pack(side="left", fill="x", expand=True, padx=(12, 8))
        tk.Label(mid, text=name, bg=U.BG2, fg=U.FG if state != "locked" else U.FG_DIM,
                 font=(U.FAMILY, U.BASE_PT + 1, "bold"), anchor="w").pack(fill="x")
        tk.Label(mid, text=role, bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w").pack(fill="x")
        return {"pic": pic, "sprite": sprite, "legend": legend, "name": name, "state": state, "chip": chip}

    def _thumbs(self):
        """간부의 도트와 전설의 도트를 받아 붙인다. 못 받아도 창은 그대로다."""
        api = self.app.api
        size = U.h(THUMB) - 6                # 칸 안쪽에 조금 여유를 둔다 (꽉 채우면 라벨이 눌린다)
        jobs = [(i, r) for i, r in enumerate(self.rows) if r["sprite"] or (r["legend"] or {}).get("num")]

        def work():
            from PIL import Image
            from .ui_gym import trainer_photo
            out = {}
            for i, r in jobs:
                try:
                    if r["sprite"]:
                        img = trainer_photo(api, r["sprite"], scale=1)
                    else:
                        from . import sprite_cache, sprites
                        path = sprite_cache.ensure(api, r["legend"]["num"], False)
                        anim = sprites.load_animation(path, size, 0.2, 2.0, max_frames=1)
                        img = sprites.to_rgba(anim.frames[sprites.LEFT][0], anim.key)
                    if img is None:
                        continue
                    k = min(size / float(img.width), size / float(img.height))
                    if k != 1.0:
                        img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))),
                                         Image.NEAREST)
                    out[i] = img
                except Exception:                           # noqa: BLE001
                    continue
            return out

        def done(out, err):
            if not self.alive or err or not out:
                return
            for i, img in out.items():
                if i < len(self.rows):
                    try:
                        ph = ImageTk.PhotoImage(img)
                        self.photos[i] = ph
                        self.rows[i]["pic"].configure(image=ph)
                    except tk.TclError:
                        pass
        if jobs:
            run_async(self.root, work, done)

    # ---------------- 승부 ----------------
    def challenge(self):
        if self.battle and self.battle.alive:
            return self.battle.focus()
        if self.busy:
            return
        self.busy = True
        if self.go_btn is not None:
            self.go_btn.configure(state="disabled")
        self.say("승부를 준비하는 중...")

        def done(r, err):
            self.busy = False
            if not self.alive:
                return
            if err:
                if self.go_btn is not None:
                    self.go_btn.configure(state="normal")
                return self.say(getattr(err, "message", str(err)), U.RED)
            from .ui_gym_battle import GymBattleWindow
            self.battle = GymBattleWindow(self.app, r, on_close=self._battle_closed)
            self.say("")
        run_async(self.root, self.app.api.boss_start, done)

    def _battle_closed(self):
        self.battle = None
        if self.alive:
            self.reload()
        try:
            if self.gw.alive:
                self.gw.reload()             # 지도의 검은 곳과 위쪽 단추를 다시 맞춘다
        except Exception:                                   # noqa: BLE001
            pass

    def focus(self):
        try:
            self.top.lift()
            self.top.focus_force()
        except tk.TclError:
            pass

    def close(self):
        self.alive = False
        try:
            self.top.destroy()
        except tk.TclError:
            pass
