# -*- coding: utf-8 -*-
"""길드 친선전: 채팅의 카드 · 알림 · 구경 (1.10.3).

**친선전은 길드 채팅에서 한다.** 채팅에 `/친선전` 을 치면 상대를 구하는 카드가 채팅에 놓이고,
길드원이 그 카드의 [배틀] 을 누르면 바로 시작한다. 판이 열리면 같은 카드가 [관전] 으로 바뀐다
(카드를 그리는 것은 길드 탭 ui_guild 이고, 무엇을 그릴지는 여기 chat_card 가 정한다).

채팅을 안 보고 있는 길드원에게는, 길드원끼리 실시간 배틀이 열리면

    ┌ 길드 친선전 ─────────── × ┐       누르면       (알림은 사라지고, 바탕화면 오른쪽 아래에서)
    │ 가람 vs 나래   [ 구경 ]    │   ──────────▶        가람 ●●○ vs ○●● 나래  ×
    └───────────────────────────┘                          ▇▇▇▇      ▇▇▇
                                                          (도트)  ↔  (도트)

    Friendly        길드 웹소켓이 넘겨준 것을 받아 '지금 누가 상대를 구하나, 어느 판이 진행 중인가' 를
                    들고 있다. 길드 채팅의 카드와 아래의 둘이 이것을 본다. 앱에 하나.
    SpectateCard    오른쪽 아래의 알림 (한 줄 + 단추). 잠깐 떴다 사라진다.
    DesktopDuel     구경. **창이 아니다** - 바탕화면에서 야생 배틀처럼 포켓몬 둘이 마주 서서 싸운다
                    (duel_scene). 그 위에 누구와 누구인지 적은 작은 이름표 하나만 뜬다 (× 로 그만 본다).

**먼저 묻고 띄운다.** 일하다 옆에 켜 두는 프로그램이라, 남의 배틀이 열렸다고 화면에 불쑥 나타나면
방해가 된다. 알림은 잠깐 떴다 사라지고, 구경은 누른 사람에게만 뜬다 (설정으로 바로 뜨게 할 수 있다).
알림 자체도 끌 수 있다. 내가 싸우는 판은 알리지 않는다 - 배틀 창이 떠 있다. **길드 채팅을 보고
있을 때도 알리지 않는다** - 눈앞의 채팅에 카드가 놓였다.

웹소켓을 못 쓰는 환경이면 알림은 오지 않는다 (길드 채팅을 열면 카드는 보인다). 구경하는 동안에는
밀려오는 것이 없으면 스스로 물어 온다 (POLL_MS).
"""
import time
import tkinter as tk

from . import duel_scene as DS
from . import platform_os as PLAT
from . import ui_common as U
from .ui_common import run_async

PAD = 8
W = 336                       # 알림의 폭
MARGIN = 14                   # 화면 가장자리에서 띄우는 간격
NOTICE_SEC = 14.0             # 알림이 떠 있는 시간
END_SEC = 3.5                 # 판이 끝나고 구경을 닫기까지
PLATE_UP = 150                # 이름표를 포켓몬의 발에서 이만큼 위에 둔다
TICK_MS = 15
POLL_MS = 2500                # 구경 중에 밀려오는 것이 없을 때 스스로 물어보는 간격
QUIET_SEC = 4.0               # 이만큼 아무것도 안 밀려오면 물어본다
BALL_ON, BALL_OFF = "#f05a50", "#59607a"
# 채팅에 치는 명령. '/친선전' 하나로 구하고, 뒤에 붙인 말로 그만두거나 한 사람에게 신청한다.
CMD_NAMES = ("친선전", "친선", "배틀")
CMD_OFF = ("취소", "그만", "끝")
CMD_HINT = "/친선전 을 치면 친선전 상대를 구합니다"
CMD_HELP = "/친선전  상대 구하기   ·   /친선전 닉네임  직접 신청   ·   /친선전 취소"


# ---------------------------------------------------------------- 계산 (창 없이 검사한다)
def corner(area, w, h, margin=MARGIN):
    """작업 영역(x1, y1, x2, y2)의 오른쪽 아래에 w x h 를 놓을 자리 (왼쪽 위)."""
    x1, y1, x2, y2 = area
    return max(x1, x2 - w - margin), max(y1, y2 - h - margin)


def work_area(win):
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    try:
        return tuple(PLAT.work_area(sw, sh))
    except Exception:                                       # noqa: BLE001
        return (0, 0, sw, sh)


def title_of(fight):
    return "%s vs %s" % (((fight or {}).get("a") or {}).get("name") or "?",
                         ((fight or {}).get("b") or {}).get("name") or "?")


def players(fight):
    return (((fight or {}).get("a") or {}).get("id"), ((fight or {}).get("b") or {}).get("id"))


def merge_fights(fights, fight):
    """진행 중인 판 목록에 새 모습을 끼운다 (끝난 판은 뺀다). 새 목록을 돌려준다."""
    mid = fight.get("id")
    out = [f for f in fights if f.get("id") != mid]
    if not fight.get("over"):
        out.append(fight)
    return out


def fresh_seekers(old, new, me):
    """새로 상대를 구하기 시작한 남 (알릴 사람들)."""
    had = set(s.get("id") for s in old or [])
    return [s for s in new or [] if s.get("id") not in had and s.get("id") != me]


def command(text, members=(), me=None):
    """채팅에 친 글이 명령인가. 명령이 아니면 None (그대로 말로 보낸다).

        ("seek",)            /친선전            상대를 구한다
        ("cancel",)          /친선전 취소       그만둔다
        ("ask", 번호, 이름)  /친선전 닉네임     그 길드원에게 직접 신청한다
        ("error", 까닭)      모르는 명령이거나 그런 길드원이 없다

    접속해 있는지는 여기서 보지 않는다 (들고 있는 길드원 목록은 조금 전 것이다) - 서버가 본다.
    """
    text = " ".join((text or "").split())
    if not text.startswith("/"):
        return None
    name, _sp, arg = text[1:].partition(" ")
    arg = arg.strip()
    if name not in CMD_NAMES:
        return ("error", "모르는 명령입니다.   " + CMD_HELP)
    if not arg:
        return ("seek",)
    if arg in CMD_OFF:
        return ("cancel",)
    hit = [m for m in members or [] if (m.get("name") or "") == arg] \
        or [m for m in members or [] if (m.get("name") or "").lower() == arg.lower()]
    if not hit:
        return ("error", "'%s' 님은 길드원이 아닙니다." % arg)
    if hit[0].get("me") or (me is not None and hit[0].get("id") == me):
        return ("error", "자기 자신에게는 신청할 수 없습니다.")
    return ("ask", hit[0].get("id"), hit[0].get("name"))


def is_card(m):
    """그 채팅 줄이 친선전 카드인가. (모르는 종류의 카드는 보통 알림 줄로 그린다)"""
    c = (m or {}).get("card")
    return isinstance(c, dict) and c.get("k") == "friendly"


def chat_card(card, line, view, me, watching=None):
    """채팅에 놓인 친선전 카드(줄 번호 line)가 지금 어떻게 보여야 하나.

        {"tag": 상태 글(없으면 ""), "tone": "seek"|"fight"|"done"|"off", "text": 한 줄,
         "button": 단추 글 | None, "act": "accept"|"cancel"|"watch"|"unwatch"|"mine"|None, "arg": ..}

    상대를 구하는 카드에는 상태 글이 없다 - 본문이 이미 '상대를 구합니다' 다 (같은 말을 두 번 적지 않는다).

    **단추는 지금 모습(view)에 그 줄 번호가 있을 때만 붙는다.** 카드에 적힌 상태만 믿으면, 서버가
    다시 떠서 '상대 구함' 을 잃었을 때 죽은 카드에 [배틀] 이 남는다. 거꾸로 view 에 있으면 카드에
    적힌 것이 옛 것이어도(카드가 바뀌었다는 소식을 못 받는 폴링 화면) 지금 모습대로 그린다.
    """
    card, view = card or {}, view or {}
    a, b = card.get("a") or {}, card.get("b") or {}
    an, bn = a.get("name") or "?", b.get("name") or "?"

    def out(tag, tone, text, button=None, act=None, arg=None):
        return {"tag": tag, "tone": tone, "text": text, "button": button, "act": act, "arg": arg}
    f = next((x for x in view.get("fights") or [] if x.get("card") == line and not x.get("over")), None)
    if f is not None:
        text = "%s  vs  %s" % ((f.get("a") or {}).get("name") or an, (f.get("b") or {}).get("name") or bn)
        if me is not None and me in players(f):
            return out("진행 중", "fight", text, "내 배틀", "mine")
        if watching is not None and watching == f.get("id"):
            return out("관전 중", "fight", text, "그만 보기", "unwatch")
        return out("진행 중", "fight", text, "관전", "watch", f.get("id"))
    s = next((x for x in view.get("seeking") or [] if x.get("card") == line), None)
    if s is not None:
        if s.get("id") == me:
            return out("", "seek", "친선전 상대를 구하는 중입니다.", "취소", "cancel")
        return out("", "seek", "%s 님이 친선전 상대를 구합니다." % (s.get("name") or an),
                   "배틀", "accept", s.get("id"))
    if card.get("s") in ("fight", "over"):
        r = card.get("result") if card.get("s") == "over" else None
        tail = {"a": "%s 님 승리" % an, "b": "%s 님 승리" % bn, "draw": "무승부"}.get(r)
        return out("끝", "done", "%s  vs  %s" % (an, bn) + ("   ·   %s" % tail if tail else ""))
    return out("마감", "off", "%s 님이 친선전 상대를 구했습니다." % an)


# ---------------------------------------------------------------- 들고 있는 것
class Friendly(object):
    """길드 친선전의 지금 모습. 앱에 하나 (app.friendly)."""

    def __init__(self, app):
        self.app = app
        self.root = getattr(app, "root", None)
        self.view = {"seeking": [], "fights": [], "limit": 3}
        self.card = None              # 오른쪽 아래의 알림
        self.duel = None              # 구경하는 장면 (바탕화면)
        self.known = set()            # 알림을 이미 띄운(또는 내가 낀) 판
        self.listeners = []           # 모습이 바뀌면 부를 함수들 (길드 탭)
        self.error = None             # 마지막으로 실패한 까닭 (길드 탭이 한 번 보여 주고 지운다)
        self.pushed = 0.0             # 마지막으로 무언가 밀려온 때
        self.pushes = 0               # 밀려온 횟수 (묻는 사이에 밀려왔는지 가린다 - 시계로는 못 가린다)
        self.chat_open = None         # 길드 채팅을 지금 보고 있나 (길드 탭이 넣는 함수) - 보고 있으면 알리지 않는다
        self._due = None              # '상대 구함' 의 시간이 다 될 때 서버에 다시 묻는 예약

    # ---- 설정
    def setting(self, key, default):
        return bool((getattr(self.app, "settings", None) or {}).get(key, default))

    def set_setting(self, key, on):
        s = getattr(self.app, "settings", None)
        if s is None:
            return
        s[key] = bool(on)
        try:
            from . import config
            config.save_settings(s)
        except Exception:                                   # noqa: BLE001
            pass

    @property
    def me(self):
        return getattr(self.app, "user_id", None)

    def seeking_me(self):
        return any(s.get("id") == self.me for s in self.view.get("seeking") or [])

    def in_chat(self):
        """길드 채팅을 보고 있나. 보고 있으면 화면 구석의 알림은 띄우지 않는다 (채팅에 카드가 놓였다)."""
        try:
            return bool(self.chat_open is not None and self.chat_open())
        except Exception:                                   # noqa: BLE001
            return False

    def _arm(self):
        """'상대 구함' 은 시간이 지나면 꺼진다 - 그때 서버에 다시 물어서 카드를 닫는다.

        서버는 누가 물어볼 때만 지난 것을 걷는다 (따로 도는 시계가 없다). 웹소켓으로만 받는 화면은
        묻는 일이 없어서, 아무도 안 받은 카드에 [배틀] 이 영영 남는다.
        """
        root = self.root
        if root is None:
            return
        if self._due is not None:
            try:
                root.after_cancel(self._due)
            except Exception:                               # noqa: BLE001
                pass
            self._due = None
        left = [int(s.get("left") or 0) for s in self.view.get("seeking") or []]
        if not left:
            return

        def go():
            self._due = None
            self.refresh()
        try:
            self._due = root.after((min(left) + 1) * 1000, go)
        except Exception:                                   # noqa: BLE001
            self._due = None

    # ---- 길드 웹소켓이 넘겨준 것 (앱의 소켓이든 길드 탭의 소켓이든 여기로 온다)
    def on_event(self, ev):
        t = (ev or {}).get("t")
        if t == "live":
            fn = getattr(self.app, "check_live", None)
            if fn is not None:
                fn()                         # 내 실시간 배틀에 일이 생겼다 (신청이 왔다 / 내 것을 누가 받았다)
            return True
        if t == "friendly":
            self.pushed = time.monotonic()
            self.pushes += 1
            self.set_view(ev)
            return True
        if t == "friendly_fight":
            self.pushed = time.monotonic()
            self.pushes += 1
            self.fight(ev.get("fight") or {})
            return True
        if t == "left":
            self.reset()
        return False

    def reset(self):
        self.view = {"seeking": [], "fights": [], "limit": 3}
        self.known = set()
        self._arm()
        self.close_card()
        self.stop_watch()
        self._changed()

    def set_view(self, v, tell=True):
        old = self.view
        self.view = {"seeking": list(v.get("seeking") or []), "fights": list(v.get("fights") or []),
                     "limit": int(v.get("limit") or 3)}
        self._arm()
        if tell and self.setting("friendlyNotify", True) and not self.watching() \
                and not getattr(self.app, "live_battle", None) and not self.in_chat():
            new = fresh_seekers(old.get("seeking"), self.view["seeking"], self.me)
            if new:
                s = new[-1]
                self.notice("%s 님이 친선전 상대를 구합니다." % s.get("name"), "받기",
                            lambda uid=s.get("id"): self.accept(uid))
        for f in self.view["fights"]:
            if self.duel is not None and self.duel.mid == f.get("id"):
                self.duel.feed(f)            # (물어서 받아 온 것 - 밀려온 것을 놓쳤을 때)
        self._changed()

    def fight(self, fight):
        """판의 새 모습이 밀려왔다."""
        mid = fight.get("id")
        if mid is None:
            return
        self.view["fights"] = merge_fights(self.view["fights"], fight)
        mine = self.me in players(fight)
        if self.duel is not None and self.duel.mid == mid:
            self.duel.feed(fight)
        elif mid not in self.known and not fight.get("over") and not mine:
            if self.setting("friendlyAuto", False) and not self.watching():
                self.watch(mid, fight)
            elif self.setting("friendlyNotify", True) and not self.watching() and not self.in_chat():
                self.notice("%s · 친선전 시작" % title_of(fight), "관전", lambda m=mid: self.watch(m))
        self.known.add(mid)
        self._changed()

    def _changed(self):
        for fn in list(self.listeners):
            try:
                fn()
            except Exception:                               # noqa: BLE001
                pass

    # ---- 창
    def watching(self):
        return self.duel is not None and self.duel.alive

    def _card(self):
        if self.card is None or not self.card.alive:
            self.card = SpectateCard(self)
        return self.card

    def notice(self, text, button, command):
        self._card().notice(text, button, command)

    def watch(self, mid, fight=None):
        """그 판을 구경한다: 바탕화면 오른쪽 아래에서 포켓몬 둘이 싸운다. 알림은 닫는다."""
        fight = fight or next((f for f in self.view["fights"] if f.get("id") == mid), None)
        if fight is None:
            self.error = "그 친선전은 이미 끝났습니다."
            return self._changed()
        self.close_card()
        self.stop_watch()
        self.duel = DesktopDuel(self, fight)
        self._changed()

    def close_card(self):
        c, self.card = self.card, None
        if c is not None:
            c.close()

    def stop_watch(self):
        d, self.duel = self.duel, None
        if d is not None:
            d.close()
            self._changed()                  # 채팅의 카드가 '관전 중' 에서 [관전] 으로 돌아간다

    def card_do(self, act, arg=None):
        """채팅의 카드에서 단추를 눌렀다 (chat_card 가 정한 act)."""
        if act == "accept":
            self.accept(arg)
        elif act == "cancel":
            self.seek(False)
        elif act == "watch":
            self.watch(arg)
        elif act == "unwatch":
            self.stop_watch()
        elif act == "mine":
            fn = getattr(self.app, "check_live", None)
            if fn is not None:
                fn()                         # 닫아 둔 내 배틀 창을 다시 띄운다

    # ---- 서버에 묻고 시키기
    def refresh(self):
        api = getattr(self.app, "api", None)
        if api is None:
            return

        # **번호로 가린다.** 시각으로 가렸더니(밀려온 때 > 물은 때) 윈도우에서 틀렸다: 그쪽 시계는
        # 16ms 씩 뛰어서, 묻자마자 밀려온 것이 '같은 때' 로 찍혀 늦게 온 옛 답이 새 모습을 덮었다.
        seq = self.pushes

        def done(r, err):
            if err or not isinstance(r, dict):
                return
            if self.pushes != seq:
                return                       # 묻는 사이에 새 것이 밀려왔다 - 묻던 때의 옛 모습으로 덮지 않는다
            self.set_view(r, tell=False)
        run_async(self.root, api.guild_friendly, done)

    def _do(self, call, after=None):
        def done(r, err):
            if err:
                self.error = getattr(err, "message", None) or str(err)
            elif isinstance(r, dict) and "seeking" in r:
                self.set_view(r, tell=False)
            if not err and after is not None:
                after(r)
            self._changed()
        run_async(self.root, call, done)

    def seek(self, on):
        api = self.app.api
        self._do(lambda: api.guild_friendly_seek(bool(on)))

    def accept(self, uid):
        api = self.app.api

        def started(_r):
            self.close_card()
            fn = getattr(self.app, "check_live", None)
            if fn is not None:
                fn()                         # 내 배틀 창을 띄운다
            self.refresh()
        self._do(lambda: api.guild_friendly_accept(uid), started)

    def ask(self, uid):
        api = self.app.api

        def sent(_r):
            fn = getattr(self.app, "live_watch", None)
            if fn is not None:
                fn()                         # 답을 기다린다 (평소의 초대와 같다)
        self._do(lambda: api.guild_friendly_ask(uid), sent)

    def close(self):
        self.listeners = []
        self.chat_open = None
        self.view = {"seeking": [], "fights": [], "limit": 3}
        self._arm()                          # (걸어 둔 예약을 푼다)
        self.close_card()
        self.stop_watch()


# ---------------------------------------------------------------- 오른쪽 아래의 알림
class SpectateCard(object):
    """알림 한 줄과 단추 (테두리 없는 작은 창). 잠깐 떴다 스스로 사라진다."""

    def __init__(self, ctl):
        self.ctl = ctl
        self.app = ctl.app
        self.root = ctl.root
        self.alive = True
        self._job = None
        self._gone = None
        self.note_text, self.note_btn = "", None
        win = self.win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.configure(bg=U.LINE2)
        box = tk.Frame(win, bg=U.BG)
        box.pack(fill="both", expand=True, padx=2, pady=2)
        head = tk.Frame(box, bg=U.BG)
        head.pack(fill="x", padx=PAD, pady=(6, 0))
        self.title = tk.Label(head, text="길드 친선전", bg=U.BG, fg=U.ACCENT, font=U.FONT_B, anchor="w")
        self.title.pack(side="left")
        self.x = tk.Label(head, text="×", bg=U.BG, fg=U.FG_DIM, font=U.FONT_B, cursor="hand2", padx=4)
        self.x.pack(side="right")
        self.x.bind("<Button-1>", lambda _e: self.ctl.close_card())
        self.body = tk.Frame(box, bg=U.BG)
        self.body.pack(fill="both", expand=True, padx=PAD, pady=(4, PAD))
        self._tick()

    def _place(self):
        try:
            self.win.update_idletasks()
            w, h = max(W + 4, self.win.winfo_reqwidth()), self.win.winfo_reqheight()
            x, y = corner(work_area(self.win), w, h)
            self.win.geometry("%dx%d+%d+%d" % (w, h, x, y))
            PLAT.raise_above(self.win)
        except tk.TclError:
            pass

    def notice(self, text, button, command):
        for c in self.body.winfo_children():
            c.destroy()
        row = tk.Frame(self.body, bg=U.BG)
        row.pack(fill="x")
        self.note_btn = U.PushButton(row, button, command, height=30, font=U.FONT_B)
        self.note_btn.pack(side="right")
        lb = tk.Label(row, text=text, bg=U.BG, fg=U.FG, font=U.FONT_S, anchor="w", justify="left",
                      wraplength=W - 110)
        lb.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.note_text = text
        self._gone = time.monotonic() + NOTICE_SEC
        self._place()

    def _tick(self):
        self._job = None
        if not self.alive:
            return
        try:
            self.step(time.monotonic())
        except tk.TclError:
            return
        if self.alive:
            self._job = self.root.after(250, self._tick)

    def step(self, now):
        if self._gone is not None and now >= self._gone:
            self.ctl.close_card()

    def close(self):
        if not self.alive:
            return
        self.alive = False
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
            self._job = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------- 구경: 바탕화면에서
class DesktopDuel(object):
    """구경하는 판 하나. 포켓몬과 연출은 duel_scene 이 바탕화면에 세우고, 여기는 그것을 굴리고
    그 위에 **이름표 하나**(누구와 누구인지, 남은 마릿수, 그만 보기)만 띄운다."""

    def __init__(self, ctl, fight):
        self.ctl = ctl
        self.app = ctl.app
        self.root = ctl.root
        self.alive = True
        self.mid = fight.get("id")
        self.mark = None              # 마지막으로 받은 장면
        self._job = None
        self._gone = None             # 끝난 판을 닫을 때
        self._asked = 0.0
        self._dots = None             # 이름표에 찍어 둔 남은 마릿수
        self.host = DS.SceneHost(self.app, self.root, work_area(self.root))
        self.scene = DS.FightScene(self.host, self.mid)
        self._plate(fight)
        # 막 열린 판(아직 첫 턴 전)이면 볼에서 나오는 것부터 보여 준다. 진행 중이던 판은 지금 모습 그대로.
        self.feed(fight, replay=not fight.get("turn"))
        self._job = self.root.after(TICK_MS, self._tick)

    # ---- 이름표
    def _plate(self, fight):
        """포켓몬들 위의 작은 이름표: 가람 ●●○ vs ○●● 나래 ×. 이것만은 누를 수 있다 (× 로 그만 본다)."""
        win = self.plate = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.configure(bg=U.LINE2)
        row = tk.Frame(win, bg="#11141c")
        row.pack(padx=1, pady=1)
        a, b = fight.get("a") or {}, fight.get("b") or {}
        self.names = (a.get("name") or "?", b.get("name") or "?")

        def name(text):
            return tk.Label(row, text=text, bg="#11141c", fg=U.FG, font=U.FONT_S)

        def dots():
            return tk.Canvas(row, width=1, height=10, bg="#11141c", highlightthickness=0, bd=0)
        name(self.names[0]).pack(side="left", padx=(8, 4), pady=3)
        self.dot_cv = {"a": dots(), "b": dots()}
        self.dot_cv["a"].pack(side="left")
        tk.Label(row, text="vs", bg="#11141c", fg=U.FG_FAINT, font=U.FONT_XS).pack(side="left", padx=6)
        self.dot_cv["b"].pack(side="left")
        name(self.names[1]).pack(side="left", padx=(4, 6), pady=3)
        self.x = tk.Label(row, text="×", bg="#11141c", fg=U.FG_DIM, font=U.FONT_B, cursor="hand2", padx=5)
        self.x.pack(side="left")
        self.x.bind("<Button-1>", lambda _e: self.ctl.stop_watch())
        self._paint_dots()
        self._place_plate()

    def _place_plate(self):
        try:
            self.plate.update_idletasks()
            w, h = self.plate.winfo_reqwidth(), self.plate.winfo_reqheight()
            area = work_area(self.plate)
            cx = (self.host.spot["a"][0] + self.host.spot["b"][0]) / 2.0
            x = int(max(area[0], min(area[2] - w - 4, cx - w / 2.0)))
            y = int(max(area[1], self.host.spot["a"][1] - PLATE_UP - h))
            self.plate.geometry("%dx%d+%d+%d" % (w, h, x, y))
            PLAT.raise_above(self.plate)
        except tk.TclError:
            pass

    def _paint_dots(self):
        """남은 마릿수를 점으로 (쓰러진 것은 회색). 바뀌었을 때만 다시 그린다."""
        now = tuple((self.scene.sides[s].left, self.scene.sides[s].size) for s in ("a", "b"))
        if now == self._dots:
            return
        grew = self._dots is None or [n for _l, n in now] != [n for _l, n in self._dots]
        self._dots = now
        for s, (left, size) in zip(("a", "b"), now):
            cv = self.dot_cv[s]
            cv.delete("all")
            cv.configure(width=max(1, size * 9))
            for i in range(size):
                on = (i < left) if s == "a" else (i >= size - left)
                cv.create_oval(i * 9 + 1, 1, i * 9 + 8, 8, fill=BALL_ON if on else BALL_OFF, outline="#14141a")
        if grew:
            self._place_plate()              # 점의 수가 정해져 폭이 바뀌었다

    # ---- 판
    def feed(self, fight, replay=True):
        if not self.alive or fight.get("id") != self.mid:
            return
        mark = (fight.get("turn"), fight.get("step"), bool(fight.get("over")))
        if mark == self.mark:
            return                           # 같은 장면이 또 왔다 - 다시 틀지 않는다
        self.mark = mark
        self.scene.feed(fight, time.monotonic(), replay)

    # ---- 돌리기
    def _tick(self):
        self._job = None
        if not self.alive:
            return
        try:
            self.step(time.monotonic())
        except tk.TclError:
            return
        except Exception:                                   # noqa: BLE001
            pass
        if self.alive:
            self._job = self.root.after(TICK_MS, self._tick)

    def step(self, now):
        self.host.now = now
        self.scene.tick(now)
        self._paint_dots()
        if self.scene.done and self._gone is None:
            self._gone = now + END_SEC
        if now - self.ctl.pushed > QUIET_SEC and now - self._asked > POLL_MS / 1000.0:
            self._asked = now
            self.ctl.refresh()               # 밀려오는 것이 없다 (웹소켓이 없거나 끊겼다) - 물어본다
        if self._gone is not None and now >= self._gone:
            self.ctl.stop_watch()

    def close(self):
        if not self.alive:
            return
        self.alive = False
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
            self._job = None
        self.scene.close()
        self.host.close()
        try:
            self.plate.destroy()
        except tk.TclError:
            pass
