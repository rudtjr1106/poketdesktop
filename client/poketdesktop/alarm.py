# -*- coding: utf-8 -*-
"""포켓몬 알림 타이머 — "30분 뒤 알려줘", "15:00 회의". 서버 없이 이 PC 에만 있다.

    ac = AlarmController(app)
    ac.add(minutes=30, memo="회의", pet_id=12)    몇 분 뒤
    ac.add(clock="15:00", memo="회의")            몇 시에 (지났으면 내일)
    ac.start()                                    켤 때: 꺼져 있던 사이 지난 알림을 '놓친 알림' 으로 한 번
    AlarmWindow(app, pet)                         걸고 지우는 창
    menu_row(app, pet)                            포켓몬 오른쪽 클릭 줄 '알림 맞추기...'

알림 하나 = {"id", "at": 이 PC 시계의 초, "memo": 40자까지, "pet": 건 포켓몬 번호 | None}. 설정 파일
(settings["alarms"])에 있어서 게임을 껐다 켜도 남는다. 10개까지.

## 울릴 때

그 포켓몬이 깡충 뛰고 머리 위에 말풍선. **소리는 없다** (사용자 결정 11/04). 운영체제 알림도 안 쓴다.
**말풍선은 누를 때까지 안 사라진다** - 잠깐 자리를 비운 사이 지나가 버리면 알림이 아니다.

  · 집중하는 중이면 **집중하는 포켓몬 위에 바로** (사용자 결정 11/04 - 직접 건 알림이라 늦으면 쓸모가 없다)
  · 아니면 알림을 건 포켓몬, 그 포켓몬이 없으면 보이는 아무 포켓몬
  · 도트가 숨어 있으면(긴급 숨기기 · 배틀 숨김) 보일 때까지 기다렸다가 띄운다
"""
import time
import tkinter as tk

from common.korean import natural

from . import config
from . import ui_box
from . import ui_common as U

MAX = 10                     # 걸어 둘 수 있는 알림 수
MEMO_MAX = 40
RETRY_MS = 5000              # 도트가 숨어 있을 때 다시 보는 간격
CHECK_MS = 60000             # 다음 알림이 멀어도 이만큼마다 다시 본다 (PC 가 잠들었다 깨는 등 시계가 건너뛸 때)
STICKY_MS = 12 * 3600 * 1000  # 누를 때까지 (사실상 끝없이)


def _hhmm(at):
    return time.strftime("%H:%M", time.localtime(at))


def parse_clock(text, now=None):
    """'15:00' · '7:05' · '1500' -> 그 시각의 초 (오늘, 지났으면 내일). 틀리면 ValueError."""
    s = (text or "").strip().replace(" ", "")
    if ":" in s:
        hh, _, mm = s.partition(":")
    elif s.isdigit() and len(s) in (3, 4):
        hh, mm = s[:-2], s[-2:]
    else:
        raise ValueError("시각은 15:00 처럼 적어 주세요.")
    try:
        h, m = int(hh), int(mm)
    except ValueError:
        raise ValueError("시각은 15:00 처럼 적어 주세요.")
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("시각은 00:00 ~ 23:59 사이로 적어 주세요.")
    now = time.time() if now is None else now
    lt = time.localtime(now)
    at = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
    if at <= now:
        lt2 = time.localtime(now + 86400)
        at = time.mktime((lt2.tm_year, lt2.tm_mon, lt2.tm_mday, h, m, 0, 0, 0, -1))
    return at


def menu_row(app, pet):
    """오른쪽 클릭 메뉴 줄. 내 포켓몬에만."""
    if (getattr(pet, "id", 0) or 0) <= 0 or getattr(app, "alarms", None) is None:
        return None
    return {"text": "알림 맞추기...", "command": lambda: open_alarms(app, pet)}


def open_alarms(app, pet=None):
    old = getattr(app, "alarm_window", None)
    if old is not None and old.alive():
        old.close()
    w = AlarmWindow(app, pet)
    app.alarm_window = w
    return w


class AlarmController(object):

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self._job = None
        self._retry_job = None
        self._waiting = []           # [(알림, 놓친 것인가)] - 도트가 숨어 있어 아직 못 띄운 것
        self.bubbles = []
        self.said = []

    # ---------------------------------------------------------------- 목록
    def _all(self):
        return list(self.app.settings.get("alarms") or [])

    def items(self):
        return sorted(self._all(), key=lambda a: (a.get("at", 0), a.get("id", 0)))

    def _save(self, lst):
        self.app.settings["alarms"] = lst
        try:
            config.save_settings(self.app.settings)
        except Exception as e:                              # noqa: BLE001
            config.log("알림 저장 실패: %s" % e)

    def add(self, minutes=None, clock=None, memo="", pet_id=None, now=None):
        now = time.time() if now is None else now
        if minutes is not None and str(minutes).strip() != "":
            try:
                m = int(str(minutes).strip())
            except ValueError:
                raise ValueError("몇 분 뒤인지 숫자로 적어 주세요.")
            if m < 1:
                raise ValueError("1분 이상으로 맞춰 주세요.")
            if m > 24 * 60:
                raise ValueError("하루(1440분) 안으로 맞춰 주세요.")
            at = now + m * 60
        elif clock:
            at = parse_clock(clock, now)
        else:
            raise ValueError("몇 분 뒤인지, 몇 시인지 적어 주세요.")
        lst = self._all()
        if len(lst) >= MAX:
            raise ValueError("알림은 %d개까지 걸 수 있어요. 지난 것을 지워 주세요." % MAX)
        a = {"id": max([x.get("id", 0) for x in lst] + [0]) + 1, "at": float(at),
             "memo": (memo or "").strip()[:MEMO_MAX], "pet": int(pet_id) if pet_id else None}
        lst.append(a)
        self._save(lst)
        self._schedule()
        return a

    def remove(self, aid):
        self._save([a for a in self._all() if a.get("id") != aid])
        self._schedule()

    # ---------------------------------------------------------------- 때 맞추기
    def start(self):
        """켤 때 한 번: 지난 것은 '놓친 알림' 으로 띄우고 지운다. 다음 것을 예약한다."""
        now = time.time()
        lst = self._all()
        missed = [a for a in lst if a.get("at", 0) <= now]
        if missed:
            self._save([a for a in lst if a.get("at", 0) > now])
            for a in sorted(missed, key=lambda a: a.get("at", 0)):
                self._show(a, missed=True)
        self._schedule()

    def stop(self):
        for j in (self._job, self._retry_job):
            if j is not None:
                try:
                    self.root.after_cancel(j)
                except Exception:                           # noqa: BLE001
                    pass
        self._job = self._retry_job = None

    def _schedule(self):
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
            self._job = None
        lst = self._all()
        if not lst:
            return
        wait = max(0.0, min(a.get("at", 0) for a in lst) - time.time())
        self._job = self.root.after(int(min(wait * 1000, CHECK_MS)) + 20, self._due)

    def _due(self):
        self._job = None
        now = time.time()
        lst = self._all()
        due = [a for a in lst if a.get("at", 0) <= now]
        if due:
            self._save([a for a in lst if a.get("at", 0) > now])
            for a in sorted(due, key=lambda a: a.get("at", 0)):
                self._show(a, missed=False)
        self._schedule()

    def fire(self, alarm):
        """지금 울린다 (목록에서 빼고 띄운다)."""
        self._save([a for a in self._all() if a.get("id") != alarm.get("id")])
        self._show(alarm, missed=False)
        self._schedule()

    # ---------------------------------------------------------------- 띄우기
    def _visible(self, p):
        try:
            return p.win.state() != "withdrawn"
        except Exception:                                   # noqa: BLE001
            return False

    def _target(self, alarm):
        ov = getattr(self.app, "overlay", None)
        if ov is None or ov.hidden:
            return None
        try:
            from . import stealth
            if stealth.active():
                return None
        except Exception:                                   # noqa: BLE001
            pass
        f = getattr(self.app, "focus", None)
        if f is not None and f.active():
            p = ov.pets.get(f.pet_id)
            if p is not None and self._visible(p):
                return p
        p = ov.pets.get(alarm.get("pet"))
        if p is not None and self._visible(p):
            return p
        for p in ov.pets.values():
            if (p.id or 0) > 0 and self._visible(p):
                return p
        return None

    def _text(self, alarm, missed):
        memo = alarm.get("memo") or ""
        head = ("⏰ 놓친 알림 · %s" if missed else "⏰ %s 알림") % _hhmm(alarm.get("at", time.time()))
        return head + (" · %s" % memo if memo else "")

    def _show(self, alarm, missed):
        pet = self._target(alarm)
        if pet is None:
            self._waiting.append((alarm, missed))
            if self._retry_job is None:
                self._retry_job = self.root.after(RETRY_MS, self._retry)
            return
        text = self._text(alarm, missed)
        self.said.append(text)
        config.log("[알림] %s" % text)
        try:
            if pet.anim_for("Hop") is not None and not pet.once:
                pet.play("Hop", once=True)
        except Exception:                                   # noqa: BLE001
            pass
        from .visit import Bubble
        b = Bubble(self.root, pet, text, ms=STICKY_MS, on_gone=lambda: self._restack(pet))
        for w in (b.win, b.label):
            w.bind("<Button-1>", lambda _e, b=b: b.close())
        try:
            b.label.configure(cursor="hand2")
        except Exception:                                   # noqa: BLE001
            pass
        self.bubbles = [x for x in self.bubbles if not x.dead] + [b]
        self._restack(pet)

    def _retry(self):
        self._retry_job = None
        waiting, self._waiting = self._waiting, []
        for alarm, missed in waiting:
            self._show(alarm, missed)

    def _restack(self, pet):
        """같은 도트 위의 알림 말풍선을 아래부터 쌓는다 (먼저 울린 것이 아래)."""
        off = 0
        for b in [x for x in self.bubbles if not x.dead and x.pet is pet]:
            b.offset = off
            off += b.height() + 4
            try:
                b.kick()
            except Exception:                               # noqa: BLE001
                pass


class AlarmWindow(object):
    """알림을 걸고 지우는 창."""
    W = 400

    def __init__(self, app, pet=None):
        self.app, self.root = app, app.root
        self.pet = pet
        self.mode = "min"
        self.win, body = ui_box._shell(app.root, "알림 맞추기", self.W, U.h(380))
        if pet is not None:
            info = (pet.mon or {}).get("info") or {}
            tk.Label(body, text=natural("%s 이(가) 알려 줄게요" % info.get("name", "?")), bg=U.BG, fg=U.FG,
                     font=U.FONT_B, anchor="w").pack(fill="x")
        note = tk.Label(body, text="시간이 되면 포켓몬이 머리 위 말풍선으로 알려 줘요 (소리는 없어요). "
                                   "말풍선은 누를 때까지 남아 있어요.",
                        bg=U.BG, fg=U.FG_DIM, font=U.FONT_XS, anchor="w", justify="left")
        note.pack(fill="x", pady=(4, 10))
        U.wrap_to_width(note)
        self.seg = U.Segmented(body, [("min", "몇 분 뒤"), ("clock", "몇 시에")], "min", self.pick_mode)
        self.seg.frame.pack(anchor="w")
        row = tk.Frame(body, bg=U.BG)
        row.pack(fill="x", pady=(8, 0))
        self.amount = tk.Entry(row, width=8, font=U.FONT_S, bg=U.BG2, fg=U.FG, insertbackground=U.FG,
                               relief="flat", highlightthickness=1, highlightbackground=U.LINE)
        self.amount.pack(side="left", ipady=3)
        self.amount.insert(0, "30")
        self.unit = tk.Label(row, text="분 뒤", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S)
        self.unit.pack(side="left", padx=(6, 0))
        mrow = tk.Frame(body, bg=U.BG)
        mrow.pack(fill="x", pady=(8, 0))
        tk.Label(mrow, text="메모", bg=U.BG, fg=U.FG_DIM, font=U.FONT_S).pack(side="left", padx=(0, 6))
        self.memo = tk.Entry(mrow, font=U.FONT_S, bg=U.BG2, fg=U.FG, insertbackground=U.FG,
                             relief="flat", highlightthickness=1, highlightbackground=U.LINE)
        self.memo.pack(side="left", fill="x", expand=True, ipady=3)
        self.err = tk.Label(body, text="", bg=U.BG, fg=U.DANGER, font=U.FONT_XS, anchor="w", justify="left")
        self.err.pack(fill="x", pady=(4, 0))
        U.wrap_to_width(self.err)
        bar = tk.Frame(body, bg=U.BG)
        bar.pack(fill="x", pady=(6, 0))
        self.ok = U.PushButton(bar, "맞추기", self.submit, height=34, font=U.FONT_B)
        self.ok.pack(side="right")
        U.ghost_button(bar, "닫기", self.close, height=34).pack(side="right", padx=(0, 8))
        tk.Label(body, text="걸어 둔 알림", bg=U.BG, fg=U.FG, font=U.FONT_S, anchor="w").pack(fill="x", pady=(14, 4))
        self.list = tk.Frame(body, bg=U.BG)
        self.list.pack(fill="x")
        for seq in ("<Return>", "<KP_Enter>"):
            self.amount.bind(seq, lambda _e: self.submit())
            self.memo.bind(seq, lambda _e: self.submit())
        self._paint_list()
        self.refit()

    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except Exception:                                   # noqa: BLE001
            return False

    def close(self):
        if self.alive():
            self.win.destroy()
        if getattr(self.app, "alarm_window", None) is self:
            self.app.alarm_window = None

    def refit(self, later=True):
        if not self.alive():
            return
        try:
            self.win.update_idletasks()
            ui_box.fit(self.win, keep_pos=True)
        except Exception:                                   # noqa: BLE001
            pass
        if later:
            self.root.after(80, lambda: self.refit(later=False))

    def pick_mode(self, mode):
        self.mode = mode
        self.seg.set(mode)
        self.amount.delete(0, "end")
        if mode == "clock":
            self.amount.insert(0, time.strftime("%H:%M", time.localtime(time.time() + 3600)))
            self.unit.configure(text="에 (지났으면 내일)")
        else:
            self.amount.insert(0, "30")
            self.unit.configure(text="분 뒤")
        self.refit()

    def submit(self):
        ac = self.app.alarms
        pid = getattr(self.pet, "id", None)
        try:
            if self.mode == "clock":
                ac.add(clock=self.amount.get(), memo=self.memo.get(), pet_id=pid)
            else:
                ac.add(minutes=self.amount.get(), memo=self.memo.get(), pet_id=pid)
        except ValueError as e:
            self.err.configure(text=str(e))
            return self.refit()
        self.err.configure(text="")
        self.memo.delete(0, "end")
        self._paint_list()
        self.refit()

    def _paint_list(self):
        for w in self.list.winfo_children():
            w.destroy()
        items = self.app.alarms.items()
        if not items:
            tk.Label(self.list, text="걸어 둔 알림이 없어요.", bg=U.BG, fg=U.FG_FAINT, font=U.FONT_XS,
                     anchor="w").pack(fill="x")
        for a in items:
            row = tk.Frame(self.list, bg=U.BG2)
            row.pack(fill="x", pady=1)
            when = time.strftime("%m/%d %H:%M", time.localtime(a["at"]))
            lb = tk.Label(row, text="%s  %s" % (when, a.get("memo") or "(메모 없음)"), bg=U.BG2, fg=U.FG,
                          font=U.FONT_XS, anchor="w", justify="left")
            lb.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=3)
            U.ghost_button(row, "지우기", lambda aid=a["id"]: self._remove(aid), height=24).pack(
                side="right", padx=4, pady=2)
        full = len(items) >= MAX
        try:
            self.ok.configure(state="disabled" if full else "normal")
        except Exception:                                   # noqa: BLE001
            pass
        if full:
            self.err.configure(text="알림은 %d개까지 걸 수 있어요. 지난 것을 지워 주세요." % MAX)

    def _remove(self, aid):
        self.app.alarms.remove(aid)
        self.err.configure(text="")
        self._paint_list()
        self.refit()
