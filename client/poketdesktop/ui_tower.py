# -*- coding: utf-8 -*-
"""배틀타워 탭 (시즌 7) — 1층부터 차례로 오르는 상시 PvE. 허브의 모험 묶음, 관장 다음.

세븐나이츠 무한의 탑을 본떴다 (서버 tower.py). 층마다 정해진 트레이너와 팀이 있고, 아래층을 이겨야 다음 층이
열린다. 보상은 층마다 처음 이긴 한 번뿐이고, 져도 잃는 것이 없어 몇 번이든 다시 도전한다.

    ┌ 배틀타워 ──────────────────── 내 기록 12층 / 50층 · 다음 큰 보상 15층 은색병뚜껑 ×2 ┐
    │  20 ★ 이브이…   Lv.68 │  13층  초능력 연구실                                        │
    │  …                    │  [도트] 관장 초련                                           │
    │ ▶13 초능력 연구실      │  (도트) 후딘 Lv.54 · 에스퍼     (도트) 슬리퍼 Lv.54 · 에스퍼   │
    │ ✓12 얼음 동굴         │  첫 클리어 보상   상금 4,000원 · 하이퍼볼 ×3                  │
    │ ✓11 유령의 방         │  지면 몇 번이든 다시 도전할 수 있습니다.        [ 도전하기 ]   │
    └───────────────────────┴──────────────────────────────────────────────────────────┘

  · 왼쪽은 위가 높은 층인 목록이다. 이긴 층 ✓, 다음에 오를 층 ▶, 그 위는 흐리게 (잠김). 5의 배수는 관문 ◆,
    10의 배수는 층주 ★.
  · 오른쪽 카드는 다음 층과 이긴 층만 상대(종 · 레벨 · 타입)를 보여 준다. 기술 · 도구 · 특성은 서버가 안 보낸다.
    **잠긴 층은 서버에 카드를 묻지 않는다** (409 가 온다) - 개요에 실려 온 이름 · 보상만 그린다.
  · 승부는 관장 배틀 창(ui_gym_battle)이 그대로 한다 - 여기서는 열기만 하고, 창 제목 · 끝 단추 · 닫기 물음만
    배틀타워 것으로 바꿔 넘긴다 (battle_texts). 화면 테마의 배틀 창이 그대로 입혀진다.
  · **앱은 서버보다 먼저 나간다.** 닫힌 시즌({"open": false})과 배틀타워를 모르는 옛 서버(404)는 같은 글로 보인다.

화면 테마 전용 파일은 없다 - 기본 위젯으로만 그려서 테마의 widgets.py 가 입힌다.
"""
import time
import tkinter as tk

from PIL import ImageTk

from . import skins
from . import ui_common as U
from .ui_common import run_async

W, H = 980, 640
LIST_W = 300                    # 왼쪽 층 목록의 폭
THUMB = 40                      # 상대 포켓몬 도트 칸
SPRITE = 92                     # 트레이너 도트 칸
STALE_SEC = 120                 # 탭을 다시 골랐을 때 이보다 오래된 것이면 다시 불러온다 (관장 탭과 같다)
FROM_DEFAULT = 7                # 옛 서버(404)는 언제 여는지 못 알려 준다 - 시즌 7 이다
CLOSED_TEXT = "배틀타워는 시즌 %d에 열립니다."
KIND = {"boss": ("★", "층주"), "gate": ("◆", "관문"), "normal": ("", "")}
MARK = {"cleared": "✓", "next": "▶", "locked": ""}


def battle_texts(n, name):
    """관장 배틀 창에 얹어 넘길 글귀 (ui_gym_battle.GymBattleWindow 의 TITLE_FMT · DONE_TEXT · LEAVE_TEXT 자리)."""
    return {"title": "배틀타워 %d층 — %s" % (n, name), "done": "타워로 돌아가기",
            "leave": "승부는 그대로 남습니다. 배틀타워에서 그 층을 누르면 이어서 할 수 있어요."}


def floor_of(region):
    """"tower:13" -> 13. 아니면 None (이어서 받은 판이 몇 층 것인지 볼 때)."""
    try:
        head, n = str(region or "").split(":", 1)
        return int(n) if head == "tower" else None
    except ValueError:
        return None


def goal_text(data):
    """머리줄의 '다음 큰 보상' - 아직 안 오른 가장 가까운 관문 · 층주."""
    high = data.get("top") or 0
    for f in data.get("floors") or []:
        if f["floor"] > high and f["kind"] != "normal":
            gifts = [ln for ln in f["reward"] if not ln.startswith("상금")] or f["reward"]
            return "다음 큰 보상  %d층 %s" % (f["floor"], " · ".join(gifts))
    return "열린 층을 모두 올랐습니다 - 다음 층을 기다려 주세요"


def action_of(row, active, high):
    """지금 누를 수 있는 것. (단추 글, 누를 수 있나, 그 옆 한 줄)"""
    if not row:
        return "", False, ""
    if row["state"] == "locked":
        return "도전하기", False, "%d층부터 차례로 올라야 합니다." % (high + 1)
    if active:
        return "이어서 하기", True, "%d층에서 하던 승부가 남아 있습니다." % (active.get("floor") or 0)
    if row["state"] == "cleared":
        return "다시 도전", True, "이미 오른 층입니다. 다시 이겨도 보상은 없습니다."
    return "도전하기", True, "지면 몇 번이든 다시 도전할 수 있습니다."


@skins.skinnable
class TowerWindow(object):

    def __init__(self, root, app, parent=None):
        self.root = root
        self.app = app
        self.alive = True
        self.data = None             # 서버 개요 (열려 있을 때만)
        self.closed = False          # 닫힌 시즌 · 옛 서버
        self.rows = {}               # 층 -> {"state", "frame", "labels"}
        self.order = []              # 목록에 그린 차례 (위가 높은 층)
        self.selected = None
        self.card_floor = None       # 카드에 **다 그려진** 층 (불러오는 동안은 None)
        self.go_btn = None
        self.battle = None
        self.busy = False
        self.photos = {}
        self._cards = {}             # 층 -> 서버 카드 (다시 불러오면 비운다 - 상태가 바뀐다)
        self._loading = False
        self._loaded_at = 0.0
        self._list_cv = None

        self.win = U.panel(parent, root, "포스크탑 — 배틀타워", W, H, 860, 560, self.close)
        self.win.configure(bg=U.BG, highlightthickness=2, highlightbackground=U.LINE2)
        if not U.is_embedded(self.win):
            U.install_wheel(self.win)
        self._header()
        # 아래 알림 줄을 몸통보다 먼저 담는다 - 창이 작아지면 나중에 담은 것부터 잘린다
        self.status = tk.Label(self.win, text=" ", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w")
        self.status.pack(side="bottom", fill="x", padx=16, pady=(0, 8))
        self.body = tk.Frame(self.win, bg=U.BG)
        self.body.pack(fill="both", expand=True, padx=16, pady=(0, 6))
        self.card = None
        tk.Label(self.body, text="불러오는 중...", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(pady=24)
        self.reload()

    # ---------------- 틀 ----------------
    def _header(self):
        head = tk.Frame(self.win, bg=U.BG)
        head.pack(fill="x", padx=16, pady=(12, 8))
        tk.Label(head, text="배틀타워", bg=U.BG, fg=U.FG, font=(U.FAMILY_BLACK, U.pt(18))).pack(side="left")
        self.record = tk.Label(head, text="", bg=U.BG, fg=U.ACCENT, font=U.FONT_B)
        self.record.pack(side="left", padx=(14, 0))
        self.goal = tk.Label(head, text="", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S)
        self.goal.pack(side="right")

    def say(self, text, color=None):
        try:
            self.status.configure(text=text or " ", fg=color or U.FG_FAINT)
        except tk.TclError:
            pass

    def _clear_body(self):
        for w in self.body.winfo_children():
            w.destroy()
        self.rows, self.order, self.card, self.go_btn, self._list_cv = {}, [], None, None, None
        self.photos = {}

    # ---------------- 불러오기 ----------------
    def reload(self):
        if self._loading:
            return
        self._loading = True

        def done(r, err):
            self._loading = False
            if not self.alive:
                return
            self._loaded_at = time.time()
            if err is not None:
                if getattr(err, "status", None) == 404:
                    return self._show_closed(FROM_DEFAULT)      # 배틀타워를 모르는 옛 서버 (머리말)
                return self.say("불러오지 못했습니다. %s" % getattr(err, "message", err), U.RED)
            if not r.get("open"):
                return self._show_closed(r.get("from") or FROM_DEFAULT)
            self.closed = False
            self.data = r
            self._cards = {}
            self._paint()
        run_async(self.root, self.app.api.tower, done)

    def on_shown(self):
        """허브에서 이 탭을 다시 골랐다. 불러온 지 오래면 다시 불러온다 (다른 곳에서 올랐을 수 있다)."""
        if self.alive and not self._loading and time.time() - self._loaded_at > STALE_SEC \
                and not (self.battle and self.battle.alive):
            self.reload()

    def _show_closed(self, season):
        self.closed = True
        self.data = None
        self.selected = self.card_floor = None
        self._clear_body()
        self.record.configure(text="")
        self.goal.configure(text="")
        box = tk.Frame(self.body, bg=U.BG2, highlightthickness=2, highlightbackground=U.LINE)
        box.pack(fill="x", pady=(8, 0))
        tk.Label(box, text=CLOSED_TEXT % season, bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY, U.BASE_PT + 2, "bold"), anchor="w").pack(fill="x", padx=16, pady=(14, 2))
        tk.Label(box, text="1층부터 차례로 오르는 도전입니다. 층마다 처음 이겼을 때 한 번 보상을 받고, "
                           "져도 잃는 것 없이 몇 번이든 다시 도전할 수 있습니다.",
                 bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left",
                 wraplength=U.wide(W) - 80).pack(fill="x", padx=16, pady=(0, 14))
        self.say("")

    # ---------------- 그리기 ----------------
    def _summary(self, n):
        return next((f for f in (self.data or {}).get("floors") or [] if f["floor"] == n), None)

    def _paint(self):
        from . import ui_box
        d = self.data
        self._clear_body()
        self.record.configure(text="내 기록  %d층 / %d층" % (d.get("top") or 0, d.get("total") or 0))
        self.goal.configure(text=goal_text(d))

        left = tk.Frame(self.body, bg=U.BG, width=U.wide(LIST_W))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        inner, cv = ui_box.scroll_body(left)
        self._list_cv = cv
        for f in sorted(d.get("floors") or [], key=lambda x: -x["floor"]):
            self.order.append(f["floor"])
            self.rows[f["floor"]] = self._row(inner, f)
        self.card = tk.Frame(self.body, bg=U.BG2, highlightthickness=2, highlightbackground=U.LINE)
        self.card.pack(side="left", fill="both", expand=True, padx=(12, 0))

        high = d.get("top") or 0
        want = high + 1 if (high + 1) in self.rows else (high if high in self.rows else None)
        if want is not None:
            self.select(want)
            self.root.after_idle(self._scroll_to, want)
        self.say("")

    def _row(self, box, f):
        n, state = f["floor"], f["state"]
        mark, _kind = KIND.get(f["kind"], KIND["normal"])
        fg = {"cleared": U.FG_DIM, "next": U.FG, "locked": U.FG_FAINT}[state]
        row = tk.Frame(box, bg=U.BG, cursor="hand2")
        row.pack(fill="x")
        a = tk.Label(row, text=MARK[state], bg=U.BG, fg=U.GOOD if state == "cleared" else U.ACCENT,
                     font=U.FONT_B, width=2, anchor="e")
        a.pack(side="left", padx=(4, 0), pady=5)
        b = tk.Label(row, text="%d층" % n, bg=U.BG, fg=fg, font=U.FONT_B, width=4, anchor="e")
        b.pack(side="left")
        e = tk.Label(row, text="Lv.%d" % f["level"], bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS)
        e.pack(side="right", padx=(0, 8))
        c = tk.Label(row, text=("%s " % mark if mark else "") + f["name"], bg=U.BG,
                     fg=U.ACCENT if mark and state != "locked" else fg, font=U.FONT_S, anchor="w")
        c.pack(side="left", fill="x", expand=True, padx=(8, 4))
        labels = [a, b, c, e]
        for w in [row] + labels:
            w.bind("<Button-1>", lambda _e, n=n: self.select(n))
        return {"state": state, "frame": row, "labels": labels}

    def _scroll_to(self, n):
        """목록을 굴려 그 층이 보이게 한다 (위에 몇 줄 남기고)."""
        try:
            i = self.order.index(n)
            self._list_cv.update_idletasks()
            self._list_cv.yview_moveto(max(0.0, (i - 5) / float(len(self.order) or 1)))
        except (ValueError, tk.TclError, AttributeError):
            pass

    def _highlight(self):
        for n, r in self.rows.items():
            bg = U.BG3 if n == self.selected else U.BG
            try:
                r["frame"].configure(bg=bg)
                for w in r["labels"]:
                    w.configure(bg=bg)
            except tk.TclError:
                pass

    # ---------------- 카드 ----------------
    def select(self, n):
        row = self._summary(n)
        if not row or self.card is None:
            return
        self.selected = n
        self.card_floor = None
        self._highlight()
        if row["state"] == "locked" or n in self._cards:
            return self._paint_card(n, self._cards.get(n))     # 잠긴 층은 서버에 묻지 않는다 (머리말)
        self._card_note("불러오는 중...")

        def done(r, err):
            if not self.alive or self.selected != n or self.card is None:
                return
            if err:
                return self._card_note("불러오지 못했습니다. %s" % getattr(err, "message", err), U.RED)
            self._cards[n] = r
            self._paint_card(n, r)
        run_async(self.root, lambda: self.app.api.tower_floor(n), done)

    def _card_note(self, text, color=None):
        for w in self.card.winfo_children():
            w.destroy()
        self.go_btn = None
        tk.Label(self.card, text=text, bg=U.BG2, fg=color or U.FG_DIM, font=U.FONT_S).pack(pady=24)

    def _paint_card(self, n, card):
        """한 층의 카드. card 가 없으면 잠긴 층이다 - 개요의 이름 · 보상만 그린다."""
        row = self._summary(n)
        for w in self.card.winfo_children():
            w.destroy()
        self.go_btn = None
        self.photos = {}
        pad = tk.Frame(self.card, bg=U.BG2)
        pad.pack(fill="both", expand=True, padx=18, pady=14)
        mark, kind = KIND.get(row["kind"], KIND["normal"])

        head = tk.Frame(pad, bg=U.BG2)
        head.pack(fill="x")
        tk.Label(head, text="%d층" % n, bg=U.BG2, fg=U.ACCENT if kind else U.FG,
                 font=(U.FAMILY_BLACK, U.pt(20))).pack(side="left")
        tk.Label(head, text=row["name"], bg=U.BG2, fg=U.FG,
                 font=(U.FAMILY, U.BASE_PT + 3, "bold")).pack(side="left", padx=(10, 0))
        if kind:
            tk.Label(head, text="%s %s" % (mark, kind), bg=U.BG2, fg=U.ACCENT, font=U.FONT_B).pack(side="right")
        tk.Label(pad, text="상대 Lv.%d · %d마리" % (row["level"], row["size"]), bg=U.BG2, fg=U.FG_DIM,
                 font=U.FONT_S, anchor="w").pack(fill="x", pady=(2, 10))

        # 아래 줄(단추 · 한마디)을 가운데보다 먼저 담는다 - 창이 작으면 가운데가 줄어든다
        text, can, note = action_of(row, (self.data or {}).get("active"), (self.data or {}).get("top") or 0)
        foot = tk.Frame(pad, bg=U.BG2)
        foot.pack(side="bottom", fill="x", pady=(10, 0))
        self.go_btn = U.PushButton(foot, text, lambda: self.challenge(n), height=38)
        self.go_btn.pack(side="right")
        if not can:
            self.go_btn.configure(state="disabled")
        tk.Label(foot, text=note, bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left",
                 wraplength=U.wide(W - LIST_W) - 260).pack(side="left", fill="x", expand=True)

        thumbs = []
        if card:
            t = card.get("trainer") or {}
            who = tk.Frame(pad, bg=U.BG2)
            who.pack(fill="x")
            holder = tk.Frame(who, bg=U.BG3, width=U.h(SPRITE), height=U.h(SPRITE))
            holder.pack_propagate(False)
            holder.pack(side="left")
            pic = tk.Label(holder, bg=U.BG3, bd=0, padx=0, pady=0, highlightthickness=0)
            pic.pack(expand=True)
            thumbs.append((pic, "trainer", t.get("sprite"), U.h(SPRITE) - 6))
            mid = tk.Frame(who, bg=U.BG2)
            mid.pack(side="left", fill="x", expand=True, padx=(14, 0))
            tk.Label(mid, text=t.get("role") or "", bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w").pack(fill="x")
            tk.Label(mid, text=t.get("name") or "", bg=U.BG2, fg=U.FG,
                     font=(U.FAMILY, U.BASE_PT + 2, "bold"), anchor="w").pack(fill="x")
            if card.get("bestTurns"):
                tk.Label(mid, text="가장 적은 턴  %d턴" % card["bestTurns"], bg=U.BG2, fg=U.FG_FAINT,
                         font=U.FONT_XS, anchor="w").pack(fill="x", pady=(4, 0))

            team = tk.Frame(pad, bg=U.BG2)
            team.pack(fill="x", pady=(12, 0))
            team.columnconfigure(0, weight=1, uniform="team")
            team.columnconfigure(1, weight=1, uniform="team")
            for i, m in enumerate(card.get("team") or []):
                cell = tk.Frame(team, bg=U.BG2)
                cell.grid(row=i // 2, column=i % 2, sticky="ew", pady=2)
                box = tk.Frame(cell, bg=U.BG3, width=U.h(THUMB), height=U.h(THUMB))
                box.pack_propagate(False)
                box.pack(side="left")
                pic = tk.Label(box, bg=U.BG3, bd=0, padx=0, pady=0, highlightthickness=0)
                pic.pack(expand=True)
                thumbs.append((pic, "mon", m.get("num"), U.h(THUMB) - 4))
                txt = tk.Frame(cell, bg=U.BG2)
                txt.pack(side="left", fill="x", expand=True, padx=(8, 4))
                tk.Label(txt, text="%s  Lv.%d" % (m.get("kr") or m.get("species") or "?", m.get("level") or 0),
                         bg=U.BG2, fg=U.FG, font=U.FONT_B, anchor="w").pack(fill="x")
                tk.Label(txt, text=" · ".join(m.get("types") or []), bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_XS,
                         anchor="w").pack(fill="x")
        else:
            tk.Label(pad, text="상대는 아래층을 오르면 보입니다.", bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_S,
                     anchor="w").pack(fill="x")

        got = row["state"] == "cleared"
        gift = tk.Frame(pad, bg=U.BG2)
        gift.pack(fill="x", pady=(14, 0))
        tk.Label(gift, text="첫 클리어 보상" + (" · 받았습니다" if got else ""), bg=U.BG2,
                 fg=U.FG_FAINT if got else U.ACCENT, font=U.FONT_B, anchor="w").pack(fill="x")
        tk.Label(gift, text=" · ".join(row.get("reward") or []), bg=U.BG2, fg=U.FG_DIM if got else U.FG,
                 font=U.FONT_S, anchor="w", justify="left",
                 wraplength=U.wide(W - LIST_W) - 90).pack(fill="x", pady=(2, 0))

        self.card_floor = n
        if thumbs:
            self._thumbs(n, thumbs)

    def _thumbs(self, n, jobs):
        """트레이너와 포켓몬의 도트를 받아 붙인다. 못 받아도 카드는 그대로다."""
        api = self.app.api

        def work():
            from PIL import Image

            from .ui_gym import mon_thumb, trainer_photo
            out = []
            for pic, kind, key, size in jobs:
                try:
                    if not key:
                        continue
                    img = trainer_photo(api, key, scale=1) if kind == "trainer" else mon_thumb(api, key, size)
                    if img is None:
                        continue
                    k = min(size / float(img.width), size / float(img.height))
                    if kind == "trainer" and k != 1.0:
                        img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.NEAREST)
                    out.append((pic, img))
                except Exception:                           # noqa: BLE001
                    continue
            return out

        def done(out, err):
            if not self.alive or err or not out or self.card_floor != n:
                return
            for i, (pic, img) in enumerate(out):
                try:
                    ph = ImageTk.PhotoImage(img)
                    self.photos[i] = ph
                    pic.configure(image=ph)
                except tk.TclError:
                    pass
        run_async(self.root, work, done)

    # ---------------- 승부 ----------------
    def challenge(self, n=None):
        n = self.selected if n is None else n
        if self.battle and self.battle.alive:
            return self.battle.focus()
        row = self._summary(n)
        if self.busy or not row or row["state"] == "locked":
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
            # 하던 판을 이어서 받았으면 그 판의 층이다 (다른 층을 눌렀어도 서버는 하던 판을 준다)
            floor = floor_of(r.get("region")) or n
            name = ((r.get("battle") or {}).get("trainer") or {}).get("name") or ""
            r["texts"] = battle_texts(floor, name)
            self.battle = GymBattleWindow(self.app, r, on_close=self._battle_closed)
            self.say("")
        run_async(self.root, lambda: self.app.api.tower_start(n), done)

    def _battle_closed(self):
        self.battle = None
        if self.alive:
            self.reload()                    # 이겼으면 그 층이 ✓ 가 되고 다음 층이 열린다

    def focus(self):
        try:
            if not U.is_embedded(self.win):
                self.win.lift()
                self.win.focus_force()
        except tk.TclError:
            pass

    def close(self):
        self.alive = False
        try:
            self.win.destroy()
        except tk.TclError:
            pass
