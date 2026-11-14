# -*- coding: utf-8 -*-
"""챔피언리그 — 독도 (관장 256곳을 다 이긴 사람끼리 실시간 배틀).

관장 탭의 전국 지도에서 독도를 누르면 이 창이 뜬다 (서버 champion.py).

  · **League** - 앱에 하나 (app.league). 놀러 가기 소켓(/ws/visit)으로 오는 리그 알림을 받는다:
      wait   누가 독도에서 상대를 기다린다 -> 화면 오른쪽 아래 알림 [도전] (설정 championNotify)
      ask    나에게 도전이 왔다 -> 앱이 /api/live 를 물어 수락을 묻는다 (보통 실시간 초대와 같은 길)
      match  판이 열렸다 -> 앱이 /api/live 를 물어 배틀 창을 띄운다
      fight  다른 참가자들의 판이 열렸다 -> 오른쪽 아래 알림 [관전] (길드전 공격 구경처럼)
      turn   보고 있는 판의 새 모습 -> 바탕화면 장면에 넘긴다
      watchers  내 판을 보는 사람 수 -> 배틀 창의 '관전 N명'
    구경(관전)도 여기서 한다 - 길드 친선전 구경(ui_spectate.DesktopDuel)을 그대로 쓰고, League 가 그 ctl 노릇을 한다.
    보는 동안 20초마다 서버에 '아직 본다' 를 알리고(그래야 판이 넘어갈 때 밀어 준다), 밀려오는 것이 끊기면 스스로
    묻는다. **관전은 참가자만** 한다 (서버도 막는다).
  · **LeagueWindow** - 창. 내 전적 · [상대 찾기] · 접속 중인 참가자 [도전] · 진행 중인 판 [관전] · 순위 · 내 최근 판.
    열려 있는 동안 POLL_MS 마다 다시 묻고, **모습이 바뀌었을 때만** 다시 그린다 (기다리는 시간은 제자리에서 센다).

배틀은 실시간 배틀 창(ui_live_battle) 그대로다 - 제목만 '챔피언리그 · 독도'. 점수 · 상금은 없고 전적만 남는다.
"""
import json
import time
import tkinter as tk

from . import skins
from . import ui_common as U
from .ui_common import run_async

W = 520
POLL_MS = 3000              # 창이 열려 있는 동안 다시 묻는 간격
TITLE = "챔피언리그 · 독도"
REASON = {"forfeit": "기권", "ko": "", "turns": "턴 끝"}


# ---------------------------------------------------------------- 글 (검사가 직접 본다)
def record_text(me):
    """'12전 8승 4패' (무승부가 있으면 ' 1무')."""
    me = me or {}
    s = "%d전 %d승 %d패" % (int(me.get("played") or 0), int(me.get("wins") or 0), int(me.get("losses") or 0))
    if me.get("draws"):
        s += " %d무" % int(me["draws"])
    return s


def clock_text(sec):
    sec = max(0, int(sec or 0))
    return "%d:%02d" % (sec // 60, sec % 60)


def outcome_text(r, pair_max=3):
    """최근 판 한 줄: '승 · 나래 · 기권' (전적에 안 든 판은 뒤에 표시)."""
    word = {"win": "승", "lose": "패", "draw": "무"}.get(r.get("outcome"), "?")
    parts = [word, r.get("foeName") or "?"]
    why = REASON.get(r.get("reason") or "", "")
    if why:
        parts.append(why)
    s = " · ".join(parts)
    if r.get("counted") is False:
        s += "  (전적 제외 - 같은 상대 하루 %d판 넘음)" % int(pair_max or 3)
    return s


def headline(st):
    """창 위쪽 한 줄: 열리기 전 / 참가자의 전적 / 아직 자격이 없는 사람."""
    st = st or {}
    if not st.get("open"):
        return "%s에 열립니다." % (st.get("opens") or "곧")
    if st.get("member"):
        me = st.get("me") or {}
        return "내 전적  %s · %d위" % (record_text(me), int(me.get("rank") or 0))
    return "관장 %d / %d · 전부 이기면 참가할 수 있습니다." % (int(st.get("cleared") or 0), int(st.get("total") or 256))


def shape_of(st):
    """다시 그릴지 가르는 열쇠 - 흐르는 값(기다리는 남은 시간)은 뺀다."""
    st = dict(st or {})
    st.pop("waitLeft", None)
    st.pop("match", None)
    return json.dumps(st, sort_keys=True, ensure_ascii=False)


def seek_label(st):
    """[상대 찾기] 단추 글과 누를 수 있나, 그 옆의 안내."""
    st = st or {}
    if st.get("seeking"):
        return "그만 찾기", True, "상대를 찾는 중 · %s 남음" % clock_text(st.get("waitLeft"))
    if st.get("why"):
        return "상대 찾기", False, st["why"]
    return "상대 찾기", True, ("누르면 기다리던 사람과 바로 붙습니다. 아무도 없으면 %d분 기다리고, %d분이 지나도 "
                              "상대가 없으면 접속 중인 다른 참가자에게 알립니다." % (
                                  int(st.get("waitSec") or 600) // 60, max(1, int(st.get("notifySec") or 60) // 60)))


def wrap(label):
    """글이 받은 폭에 맞춰 접히게 한다 (처음 wraplength 는 어림값). 창 폭은 테두리 · 여백 · 굴림 막대가 있느냐로
    달라져서 숫자로 맞추면 몇십 px 씩 넘쳐 오른쪽이 잘렸다 - 글꼴을 줄이지 않고 받은 폭으로 접는다."""
    def fit(e):
        w = max(40, e.width - 2)
        try:
            if abs(int(label.cget("wraplength")) - w) > 1:
                label.configure(wraplength=w)
        except (tk.TclError, ValueError):
            pass
    label.bind("<Configure>", fit, add="+")
    return label


# ---------------------------------------------------------------- 앱에 하나
class League(object):
    """챔피언리그의 알림 · 구경 · 창을 들고 있는 것 (app.league)."""

    def __init__(self, app):
        self.app = app
        self.root = getattr(app, "root", None)
        self.card = None              # 오른쪽 아래 알림 (ui_spectate.SpectateCard)
        self.duel = None              # 구경하는 장면 (ui_spectate.DesktopDuel)
        self.win = None               # 리그 창
        self.pushed = 0.0             # 마지막으로 판이 밀려온 때 - DesktopDuel 이 보고, 끊기면 스스로 묻는다
        self._asking = False
        self._beat = None             # 관전하는 동안 '아직 본다' 를 알리는 예약

    @property
    def me(self):
        return getattr(self.app, "user_id", None)

    def setting(self, key, default):
        return bool((getattr(self.app, "settings", None) or {}).get(key, default))

    def _notify(self, text):
        fn = getattr(self.app, "notify", None)
        if fn is not None:
            try:
                fn(text)
            except Exception:                               # noqa: BLE001
                pass

    # ---- 소켓 (visit.Visit.on_event 가 넘긴다)
    def on_event(self, ev):
        s = (ev or {}).get("s")
        if s == "wait":
            uid, name = ev.get("id"), ev.get("name") or "?"
            if uid != self.me and self.setting("championNotify", True) and not self._busy():
                self.notice("%s 님이 독도에서 상대를 기다립니다." % name, "도전",
                            lambda u=uid, n=name: self.challenge(u, n))
        elif s in ("ask", "match"):
            self.close_card()
            fn = getattr(self.app, "check_live", None)
            if fn is not None:
                fn()                         # 수락을 묻거나 배틀 창을 띄운다 (app.announce_live)
        elif s == "fight":
            mid = ev.get("id")
            if mid is not None and self.setting("championNotify", True) and not self._busy():
                self.notice("%s  vs  %s · 챔피언리그 배틀이 시작됐습니다." % (ev.get("a") or "?", ev.get("b") or "?"),
                            "관전", lambda m=mid: self.watch(m))
        elif s == "turn":
            f = ev.get("fight") or {}
            self.pushed = time.monotonic()
            d = self.duel
            if d is not None and d.alive and str(d.mid) == str(f.get("id")):
                d.feed(f)
            return True                      # 창은 다시 묻지 않는다 (턴마다 오니까)
        elif s == "watchers":
            win = getattr(self.app, "live_battle", None)
            fn = getattr(win, "set_watchers", None)
            if fn is not None and getattr(win, "alive", True):
                try:
                    fn(ev.get("id"), int(ev.get("n") or 0))
                except Exception:                           # noqa: BLE001
                    pass
            return True
        self.refresh_window()
        return True

    def _busy(self):
        """알림을 띄우지 않을 때: 배틀 중 · 구경 중 · 이 창을 보고 있다 (창에 이미 보인다)."""
        if getattr(self.app, "live_battle", None) or self.watching():
            return True
        return self.win is not None and self.win.alive

    # ---- 오른쪽 아래 알림 (SpectateCard 의 ctl 노릇: app · root · close_card)
    def notice(self, text, button, command):
        from .ui_spectate import SpectateCard
        if self.card is None or not self.card.alive:
            self.card = SpectateCard(self)
            try:
                self.card.title.configure(text=TITLE)
            except tk.TclError:
                pass

        def go():
            self.close_card()
            command()
        self.card.notice(text, button, go)

    def close_card(self):
        c, self.card = self.card, None
        if c is not None:
            c.close()

    # ---- 할 것
    def challenge(self, uid, name="", then=None):
        """그 참가자에게 도전한다. 기다리던 사람이면 바로 배틀 창, 아니면 상대가 받을 때까지 기다린다."""
        api = getattr(self.app, "api", None)
        if api is None:
            return

        def done(r, err):
            if err:
                msg = getattr(err, "message", str(err))
                self._notify(msg)
                if self.win is not None and self.win.alive:
                    self.win.say(msg, U.DANGER)
                return
            m = (r or {}).get("match") or {}
            if m.get("state") == "fighting":
                self.app.open_live_battle(m)
            else:
                self.app.live_pending = m
                self._notify("%s 님에게 도전했습니다. 받으면 바로 시작합니다." % (name or m.get("foeName") or "상대"))
                watch = getattr(self.app, "live_watch", None)
                if watch is not None:
                    watch(2000)
            self.refresh_window()
            if then:
                then()
        run_async(self.root, lambda: api.champion_challenge(uid), done)

    # ---- 구경 (DesktopDuel 의 ctl 노릇: app · root · pushed · refresh · stop_watch)
    def watching(self):
        return self.duel is not None and self.duel.alive

    def _away(self):
        vis = getattr(self.app, "visit", None)
        return bool(vis is not None and getattr(vis, "guest", False))

    def watch(self, mid):
        """그 판을 바탕화면에서 구경한다 (친선전 구경과 같은 장면). 길드 친선전을 구경하고 있었으면 그것은 닫는다."""
        if self._away():
            self._notify("친구 집에 놀러 가 있는 동안에는 구경할 수 없습니다. 돌아온 뒤에 봐 주세요.")
            return
        api = getattr(self.app, "api", None)
        if api is None:
            return

        def done(f, err):
            if err or not isinstance(f, dict):
                msg = getattr(err, "message", "") or "그 판은 이미 끝났습니다."
                self._notify(msg)
                return
            fr = getattr(self.app, "friendly", None)
            if fr is not None and fr.watching():
                fr.stop_watch()
            self.stop_watch()
            from .ui_spectate import DesktopDuel
            self.duel = DesktopDuel(self, f)
            self._tell(mid, True)            # 서버가 판이 넘어갈 때마다 밀어 주고, 싸우는 사람에게 '관전 N명'
        run_async(self.root, lambda: api.champion_fight(mid), done)

    def _tell(self, mid, on):
        """서버에 '보기 시작했다 / 아직 본다 / 그만 봤다' 를 알린다. 보는 동안에는 PING_MS 마다 다시."""
        from .ui_spectate import PING_MS
        api, root = getattr(self.app, "api", None), self.root
        if self._beat is not None and root is not None:
            try:
                root.after_cancel(self._beat)
            except Exception:                               # noqa: BLE001
                pass
            self._beat = None
        if api is None or mid is None:
            return
        try:
            run_async(root, lambda: api.champion_watch(mid, on), lambda _r, _e: None)
        except Exception:                                   # noqa: BLE001
            return
        if on and root is not None:
            def again():
                self._beat = None
                if self.watching() and str(self.duel.mid) == str(mid):
                    self._tell(mid, True)
            try:
                self._beat = root.after(PING_MS, again)
            except Exception:                               # noqa: BLE001
                self._beat = None

    def refresh(self):
        """구경 중인 판을 다시 묻는다 (DesktopDuel 이 POLL_MS 마다 부른다)."""
        d = self.duel
        api = getattr(self.app, "api", None)
        if d is None or not d.alive or api is None or self._asking:
            return
        self._asking = True
        mid = d.mid

        def done(f, err):
            self._asking = False
            if self.duel is not d or not d.alive:
                return
            if err and getattr(err, "status", None) == 404:
                return self.stop_watch()
            if isinstance(f, dict):
                d.feed(f)
        run_async(self.root, lambda: api.champion_fight(mid), done)

    def stop_watch(self):
        d, self.duel = self.duel, None
        if d is not None:
            d.close()
            self._tell(d.mid, False)

    # ---- 창
    def open_window(self, parent=None):
        """독도 창을 띄운다. 이미 떠 있으면 앞으로.

        **'떠 있다' 는 창이 실제로 있는지까지 본다** (2.5.0, 게시판 #542 '독도에 안 들어가져요'). 독도 창은 관장
        창의 자식이라 관장 창을 닫으면 같이 사라지는데, 예전에는 그때 alive 가 그대로 남아 그 뒤로 독도를 누를
        때마다 없는 창을 앞으로 꺼내려다 조용히 끝났다 - 앱을 다시 켤 때까지. 이제 사라지는 순간(<Destroy>)
        스스로 정리하고, 그래도 남아 있으면 여기서 한 번 더 본다.
        """
        w = self.win
        if w is not None and w.alive and w.exists():
            w.focus()
            return w
        if w is not None:
            w.gone()                   # 사라졌는데 정리가 안 됐다 - 지금 정리하고 새로 띄운다
        self.win = LeagueWindow(self, parent)
        return self.win

    def refresh_window(self):
        if self.win is not None and self.win.alive:
            self.win.reload()

    def close(self):
        self.close_card()
        self.stop_watch()
        w, self.win = self.win, None
        if w is not None:
            w.close()


# ---------------------------------------------------------------- 창
@skins.skinnable
class LeagueWindow(object):
    """독도 창. league 는 League, parent 는 띄울 자리(관장 창)."""

    def __init__(self, league, parent=None):
        from . import ui_box
        self.league = league
        self.app = league.app
        self.root = league.root
        self.alive = True
        self.st = None
        self._shape = None
        self._job = None
        self._tick_job = None
        self._wait_until = None       # 기다리기가 끝나는 때 (time.monotonic) - 창이 제자리에서 센다
        self._busy = False
        self.seek_btn = None
        self.seek_note = None
        self.top, f = ui_box._shell(parent or self.root, TITLE, U.wide(W), U.h(320))
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        # 관장 창(부모)을 닫으면 이 창도 같이 사라진다 - 그때 스스로 정리한다 (open_window 를 보라, 게시판 #542)
        self.top.bind("<Destroy>", lambda e: self.gone() if e.widget is self.top else None, add="+")
        self.status = tk.Label(f, text=" ", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS, anchor="w",
                               justify="left", wraplength=U.wide(W) - 48)
        self.status.pack(side="bottom", fill="x", pady=(6, 0))
        self.body, cv = ui_box.scroll_body(f)
        self._scroll = (cv, self.body)
        tk.Label(self.body, text="불러오는 중...", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(pady=24)
        self._fit()
        self.reload()
        self._tick()

    # ---- 틀
    def _fit(self):
        from . import ui_box
        try:
            hi = min(U.work_size(self.top)[1], U.h(680))
            ui_box.fit(self.top, hi=hi, scroll=self._scroll)
        except tk.TclError:
            pass

    def focus(self):
        try:
            self.top.deiconify()
            self.top.lift()
            self.top.focus_force()
        except tk.TclError:
            pass

    def say(self, text, color=None):
        try:
            self.status.configure(text=text or " ", fg=color or U.FG_FAINT)
        except tk.TclError:
            pass

    def exists(self):
        """창이 아직 화면에 있나 (부모와 같이 사라졌으면 False)."""
        try:
            return bool(self.top.winfo_exists())
        except tk.TclError:
            return False

    def gone(self):
        """창이 사라졌다 (닫았든 부모와 같이 사라졌든) - 타이머를 멈추고 League 가 이 창을 놓게 한다."""
        if not self.alive:
            return
        self.alive = False
        for j in (self._job, self._tick_job):
            if j is not None:
                try:
                    self.root.after_cancel(j)
                except Exception:                           # noqa: BLE001
                    pass
        self._job = self._tick_job = None
        if self.league.win is self:
            self.league.win = None

    def close(self):
        if not self.alive:
            return
        self.gone()
        try:
            self.top.destroy()
        except tk.TclError:
            pass

    # ---- 불러오기
    def reload(self):
        if not self.alive or self._busy:
            return
        self._busy = True

        def done(r, err):
            self._busy = False
            if not self.alive:
                return
            if err:
                self.say("불러오지 못했습니다. %s" % getattr(err, "message", err), U.DANGER)
            else:
                self.apply(r)
            self._later()
        run_async(self.root, self.app.api.champion, done)

    def _later(self):
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
        self._job = self.root.after(POLL_MS, self._poll)

    def _poll(self):
        self._job = None
        if self.alive:
            self.reload()

    def apply(self, st):
        """서버가 준 모습을 받는다. 모습이 바뀌었을 때만 다시 그린다."""
        if not isinstance(st, dict):
            return
        self.st = st
        left = int(st.get("waitLeft") or 0)
        self._wait_until = time.monotonic() + left if st.get("seeking") and left else None
        key = shape_of(st)
        if key != self._shape:
            self._shape = key
            self.paint()
        else:
            self._paint_seek()

    def _tick(self):
        """기다리는 남은 시간을 제자리에서 센다 (1초마다)."""
        self._tick_job = None
        if not self.alive:
            return
        if self._wait_until is not None and self.st:
            self.st["waitLeft"] = max(0, int(round(self._wait_until - time.monotonic())))
            self._paint_seek()
        self._tick_job = self.root.after(1000, self._tick)

    # ---- 그리기
    def paint(self):
        st = self.st or {}
        for w in self.body.winfo_children():
            w.destroy()
        self.seek_btn = self.seek_note = None
        wl = U.wide(W) - 60
        member = bool(st.get("member"))

        head = tk.Frame(self.body, bg=U.BG2, highlightthickness=2,
                        highlightbackground=U.ACCENT if member and st.get("open") else U.LINE)
        head.pack(fill="x")
        top = tk.Frame(head, bg=U.BG2)
        top.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(top, text="독도", bg=U.BG2, fg=U.FG, font=(U.FAMILY_BLACK, U.pt(16))).pack(side="left")
        tk.Label(top, text="챔피언리그", bg=U.BG2, fg=U.ACCENT, font=U.FONT_B).pack(side="left", padx=(10, 0),
                                                                                pady=(6, 0))
        wrap(tk.Label(head, text="관장 %d곳을 모두 이긴 트레이너끼리 겨루는 실시간 배틀입니다. 포켓몬은 모두 Lv.50, "
                                 "한 턴은 30초. 점수와 상금은 없고 전적만 남습니다 (같은 상대와는 하루 %d판까지)."
                                 % (int(st.get("total") or 256), int(st.get("pairMax") or 3)),
                      bg=U.BG2, fg=U.FG_DIM, font=U.FONT_S, anchor="w", justify="left",
                      wraplength=wl)).pack(fill="x", padx=14, pady=(4, 0))
        wrap(tk.Label(head, text=headline(st), bg=U.BG2, fg=U.FG if member else U.FG_DIM,
                      font=(U.FAMILY, U.BASE_PT + 1, "bold"), anchor="w", justify="left",
                      wraplength=wl)).pack(fill="x", padx=14, pady=(8, 10))

        # [상대 찾기]
        row = tk.Frame(self.body, bg=U.BG)
        row.pack(fill="x", pady=(12, 0))
        text, can, note = seek_label(st)
        maker = U.ghost_button if st.get("seeking") else U.PushButton
        self.seek_btn = maker(row, text, self.toggle_seek, height=36)
        self.seek_btn.pack(side="right")
        if not can:
            self.seek_btn.configure(state="disabled")
        self.seek_note = wrap(tk.Label(row, text=note, bg=U.BG, fg=U.ACCENT if st.get("seeking") else U.FG_DIM,
                                       font=U.FONT_S, anchor="w", justify="left", wraplength=wl - U.h(150)))
        self.seek_note.pack(side="left", fill="x", expand=True, padx=(0, 10))

        my_why = st.get("why") if not st.get("seeking") else None
        # 접속 중인 참가자
        online = st.get("online") or []
        box = self._section("접속 중인 참가자 %d명" % len(online))
        if not online:
            self._empty(box, "지금 접속한 다른 참가자가 없습니다.")
        for i, o in enumerate(online):
            r = self._row(box, i)
            tag, color = (("기다리는 중", U.ACCENT) if o.get("waiting") else
                          ("배틀 중", U.FG_FAINT) if o.get("busy") else ("", U.FG_DIM))
            b = U.ghost_button(r, "도전", lambda u=o["id"], n=o.get("name"): self.league.challenge(u, n), height=28)
            b.pack(side="right")
            if o.get("busy") or my_why:
                b.configure(state="disabled")
            if tag:
                tk.Label(r, text=tag, bg=U.BG2, fg=color, font=U.FONT_XS).pack(side="right", padx=(0, 10))
            tk.Label(r, text=o.get("name") or "?", bg=U.BG2, fg=U.FG, font=U.FONT_S, anchor="w").pack(
                side="left", fill="x", expand=True)

        # 진행 중인 판
        fights = st.get("fights") or []
        if fights:
            box = self._section("진행 중인 판")
            for i, f in enumerate(fights):
                r = self._row(box, i)
                mine = self.league.me in ((f.get("a") or {}).get("id"), (f.get("b") or {}).get("id"))
                if not mine and member:      # 관전은 참가자만 (서버도 막는다)
                    U.ghost_button(r, "관전", lambda m=f["id"]: self.league.watch(m), height=28).pack(side="right")
                if f.get("watchers"):
                    tk.Label(r, text="관전 %d명" % int(f["watchers"]), bg=U.BG2, fg=U.FG_DIM,
                             font=U.FONT_XS).pack(side="right", padx=(0, 10))
                tk.Label(r, text="%s  vs  %s · %d턴" % ((f.get("a") or {}).get("name") or "?",
                                                       (f.get("b") or {}).get("name") or "?", int(f.get("turn") or 0)),
                         bg=U.BG2, fg=U.FG, font=U.FONT_S, anchor="w").pack(side="left", fill="x", expand=True)

        # 순위
        table = st.get("ranking") or []
        box = self._section("순위 · 이긴 횟수 (참가자 %d명)" % int(st.get("members") or len(table)))
        if not table:
            self._empty(box, "아직 참가자가 없습니다.")
        for i, t in enumerate(table):
            me = t.get("id") == self.league.me
            r = self._row(box, i, bg=U.ACCENT_SOFT if me else U.BG2)
            bg = r["bg"]
            tk.Label(r, text="%d" % int(t.get("rank") or 0), bg=bg, fg=U.ACCENT if int(t.get("rank") or 0) <= 3
                     else U.FG_DIM, font=U.FONT_B, width=3, anchor="w").pack(side="left")
            tk.Label(r, text=record_text(t), bg=bg, fg=U.FG_DIM, font=U.FONT_S).pack(side="right")
            tk.Label(r, text=t.get("name") or "?", bg=bg, fg=U.ACCENT_TEXT if me else U.FG,
                     font=U.FONT_B if me else U.FONT_S, anchor="w").pack(side="left", fill="x", expand=True)

        # 내 최근 판
        recent = st.get("recent") or []
        if recent:
            box = self._section("내 최근 판")
            for i, g in enumerate(recent):
                r = self._row(box, i)
                color = {"win": U.GOOD, "lose": U.DANGER}.get(g.get("outcome"), U.FG_DIM)
                wrap(tk.Label(r, text=outcome_text(g, st.get("pairMax")), bg=U.BG2,
                              fg=color if g.get("counted", True) else U.FG_FAINT,
                              font=U.FONT_S, anchor="w", justify="left", wraplength=wl - U.h(20))).pack(
                    side="left", fill="x", expand=True)
        self.top.after_idle(self._fit)

    def _section(self, title):
        U.marker_label(self.body, title, bg=U.BG).pack(fill="x", pady=(14, 6))
        box = tk.Frame(self.body, bg=U.BG2, highlightthickness=1, highlightbackground=U.LINE)
        box.pack(fill="x")
        return box

    def _empty(self, box, text):
        tk.Label(box, text=text, bg=U.BG2, fg=U.FG_FAINT, font=U.FONT_S, anchor="w").pack(fill="x", padx=12,
                                                                                        pady=8)

    def _row(self, box, i, bg=None):
        if i:
            tk.Frame(box, bg=U.LINE, height=1).pack(fill="x", padx=10)
        bg = bg or U.BG2
        r = tk.Frame(box, bg=bg)
        r.pack(fill="x", padx=0, pady=0, ipady=2)
        inner = tk.Frame(r, bg=bg)
        inner.pack(fill="x", padx=12, pady=4)
        return inner

    def _paint_seek(self):
        """[상대 찾기] 줄만 고친다 (남은 시간이 흐를 때)."""
        if self.seek_btn is None or self.seek_note is None:
            return
        text, can, note = seek_label(self.st)
        try:
            self.seek_note.configure(text=note)
            self.seek_btn.configure(text=text, state="normal" if can else "disabled")
        except tk.TclError:
            pass

    # ---- 단추
    def toggle_seek(self):
        st = self.st or {}
        on = not st.get("seeking")

        def done(r, err):
            if not self.alive:
                return
            if err:
                return self.say(getattr(err, "message", str(err)), U.DANGER)
            m = (r or {}).get("match")
            self.say("상대를 찾았습니다!" if m else ("상대를 기다립니다." if on else "그만 찾았습니다."),
                     U.ACCENT if m or on else None)
            self.apply(r)
            if m and m.get("state") == "fighting":
                self.app.open_live_battle(m)
        run_async(self.root, lambda: self.app.api.champion_seek(on), done)

