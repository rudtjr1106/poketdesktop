# -*- coding: utf-8 -*-
"""포켓몬과 집중하기 — 집중 모드 (앱 쪽).

    f = FocusController(app)
    f.start(pid, stat, done)    서버에 시작을 알리고 집중 모드로 (거절되면 done(None, 까닭))
    f.note(me["focus"])         동기화마다: 다른 PC · 다시 켠 앱이 진행 중인 집중을 이어 받는다 (없다고 하면 맥박으로 확인)
    f.stop(done)                집중 끝내기 (진행 중이던 세트는 노력치 0)
    f.on_pets_synced()          바탕화면 동기화 뒤: 집중 포켓몬이 빠졌으면 끝낸다
    f.clear()                   서버를 안 부르고 모드만 푼다 (로그인이 끊겼을 때)

규칙 숫자는 common/focus.py, 서버는 server/app/focus.py. 설계: design-notes/2026-11-04-focus-timer.md

## 집중 모드

고른 포켓몬만 바탕화면에 남고(overlay.set_only), 그 포켓몬이 동작을 하며(focus_act.Activity) 밑에 남은 시간이
보인다(focus_act.Tag). 풀숲 · 야생은 멈춘다 (wild.stop + WildController.check 가 집중 중이면 아무것도 안 한다).
업적 · 탐험 보따리 · 알 부화 알림은 끝난 뒤로 미룬다 (app.focus_quiet - 서버가 '안 본 것' 으로 남겨 둔다).

## 맥박

1분마다 POST /api/focus/beat. 서버가 지난 세트를 인정하면 그 포켓몬이 깡충 뛰고 잠깐 말풍선을 띄운다 -
**묻지 않고 다음 세트가 바로 이어진다** (사용자 결정 11/04). 세트가 끝나는 때에는 2초 뒤 한 번 더 보낸다.
맥박이 실패하면(네트워크 · 서버 오류) 모드를 그대로 두고 다음 맥박에 다시 보낸다 - **서버가 끝났다고
말할 때만 푼다.** 3분 넘게 못 보내면 서버가 '끊겼다' 로 닫는다 (게임 꺼짐 · 컴퓨터 잠듦과 같은 뜻).

## 끝나는 까닭과 말

    done       내가 끝냈다                      서버 문구 ("집중 끝! 오늘 N분 집중했어요.")
    lost       맥박이 끊겨 서버가 닫았다          서버 문구 (마지막 세트 인정 안 됨) - **한 번만**
    elsewhere  다른 PC 가 끝냈다 (동기화에 없다)   "다른 곳에서 집중을 끝냈어요"
    gone       집중 포켓몬이 바탕화면에서 빠졌다    "집중하던 포켓몬이 바탕화면에서 빠져서 집중을 끝냈어요"

끝난 집중의 번호는 기억해 둔다 - 맥박보다 먼저 받아 둔 옛 동기화가 그 집중을 또 실어 와도 다시 들어가지 않는다.
"""
import time

from common import focus as F

from . import config
from .focus_act import Activity, Tag
from .ui_common import run_async

ELSEWHERE_MSG = "다른 곳에서 집중을 끝냈어요"
GONE_MSG = "집중하던 포켓몬이 바탕화면에서 빠져서 집중을 끝냈어요"
BATTLE_MSG = "배틀이 끝난 뒤에 시작할 수 있어요."
BUBBLE_MS = 4000             # 세트 말풍선이 떠 있는 시간
END_BUBBLE_MS = 6000         # 끝났을 때 말풍선
TICK_MS = 1000
SET_END_DELAY_MS = 2000      # 세트가 끝나는 때 맥박을 이만큼 늦게 (서버 시계가 조금 늦어도 인정되게)


def mmss(sec):
    sec = max(0, int(sec))
    return "%02d:%02d" % (sec // 60, sec % 60)


def set_text(c):
    """세트가 인정됐을 때 말풍선 글. 놓아준 포켓몬(gone)이면 None."""
    stat_kr = (F.act_of(c.get("stat")) or ("?", "?"))[1]
    cap = c.get("capped")
    if cap == "gone":
        return None
    if cap == "day":
        return "오늘 받을 노력치는 다 받았어요 — 집중 시간은 계속 기록돼요"
    if cap == "full":
        if c.get("ev"):
            return "%s 노력치 +%d! 이제 꽉 찼어요" % (stat_kr, c["ev"])
        return "%s 노력치가 꽉 찼어요" % stat_kr
    return "%s 노력치 +%d! (오늘 %d/%d)" % (stat_kr, c.get("ev", 0), c.get("todayEv", 0),
                                         c.get("dailyEv", F.DAILY_EV))


class FocusController(object):

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.view = None             # 서버가 준 진행 중인 집중 (None 이면 집중 아님)
        self.pet_id = None
        self.pet = None              # 동작을 붙인 Pet (동기화가 도트를 새로 만들면 다시 붙인다)
        self.act = None
        self.tag = None
        self.said = []               # 띄운 말 (검사 · 기록)
        self._closed = set()         # 끝난 집중 번호 - 옛 동기화가 또 실어 와도 다시 안 들어간다
        self._left = None
        self._left_at = None
        self._tick_job = None
        self._beat_job = None
        self._beating = False
        self._stopping = False
        self._last_beat = 0.0
        self._fail_until = 0.0       # 맥박이 실패했다 - 이때까지는 세트 끝 맥박을 다시 안 보낸다 (장애 때 몰아치지 않게)

    # ---------------------------------------------------------------- 상태
    def active(self):
        return self.view is not None

    def left(self):
        """이번 세트 남은 초 (서버가 준 남은 초에서 센다 - PC 시계가 틀려도 맞다)."""
        if self._left is None:
            return 0
        return max(0.0, self._left - (time.monotonic() - self._left_at))

    def left_text(self):
        return mmss(self.left())

    def _set_view(self, view):
        self.view = view
        self._left = float(view.get("setLeft", F.SET_SEC))
        self._left_at = time.monotonic()
        if self.tag is not None:
            self.tag.set(self.left())

    # ---------------------------------------------------------------- 시작
    def start(self, pid, stat, done=None):
        app = self.app

        def tell(r, err):
            if done is not None:
                try:
                    done(r, err)
                except Exception:                           # noqa: BLE001
                    pass
        b = getattr(app, "battle", None)
        if (b is not None and not getattr(b, "closed", False)) or getattr(app, "arena", None):
            return tell(None, BATTLE_MSG)
        o = getattr(app, "olympics", None)
        if o is not None and o.busy():
            return tell(None, "올림픽 경기 중계가 끝난 뒤에 시작할 수 있어요.")

        def back(r, err):
            if err:
                return tell(None, getattr(err, "message", None) or str(err))
            self.begin((r or {}).get("running"))
            tell(r, None)
        run_async(self.root, lambda: app.api.focus_start(int(pid), stat), back)

    def begin(self, view):
        """집중 모드로 들어간다 (시작했을 때 · 동기화로 이어 받을 때)."""
        if not view:
            return
        if self.active():
            if view.get("id") == self.view.get("id"):
                return self._set_view(view)
            self._teardown()
        self.pet_id = (view.get("pokemon") or {}).get("id")
        self._set_view(view)
        ov = self.app.overlay
        if ov is not None:
            ov.set_only(self.pet_id)
        self._attach()
        if self.app.wild is not None:
            try:
                self.app.wild.stop()
            except Exception:                               # noqa: BLE001
                pass
        self._last_beat = time.monotonic()
        self._schedule_beat()
        self._tick()
        self._refresh_tray()

    def _attach(self):
        """집중 포켓몬에 동작과 시간표를 붙인다. 도트가 아직 없으면(첫 동기화 전) 다음 동기화에."""
        ov = self.app.overlay
        pet = ov.pets.get(self.pet_id) if ov is not None else None
        if pet is None or pet is self.pet:
            return pet
        self._detach()
        self.pet = pet
        self.act = Activity(pet, self.view["stat"])
        pet.drive = self.act
        self.tag = Tag(self.root, pet, self.view["stat"])
        self.tag.set(self.left())
        return pet

    def _detach(self):
        if self.act is not None and self.pet is not None:
            try:
                self.act.stop(self.pet)
            except Exception:                               # noqa: BLE001
                pass
        if self.tag is not None:
            self.tag.destroy()
        self.act = self.tag = self.pet = None

    # ---------------------------------------------------------------- 틱 · 맥박
    def _tick(self):
        self._tick_job = None
        if not self.active():
            return
        ov = self.app.overlay
        if ov is not None and ov.pets.get(self.pet_id) is not self.pet:
            self._attach()                 # 크기를 바꾸는 등으로 도트가 새로 만들어졌다
        if self.tag is not None:
            self.tag.set(self.left())
        now = time.monotonic()
        if (self.left() <= 0 and now - self._last_beat >= SET_END_DELAY_MS / 1000.0
                and now >= self._fail_until):
            self.beat()
        self._tick_job = self.root.after(TICK_MS, self._tick)

    def _schedule_beat(self, ms=None):
        if self._beat_job is not None:
            try:
                self.root.after_cancel(self._beat_job)
            except Exception:                               # noqa: BLE001
                pass
        if ms is None:
            ms = F.BEAT_SEC * 1000
            left_ms = int(self.left() * 1000) + SET_END_DELAY_MS
            if 0 < left_ms < ms:
                ms = left_ms                # 세트가 끝나는 때 맞춰서
        self._beat_job = self.root.after(max(200, int(ms)), self.beat)

    def beat(self):
        self._beat_job = None
        if not self.active() or self._beating:
            return
        self._beating = True
        self._last_beat = time.monotonic()
        rid = self.view.get("id")

        def back(r, err):
            self._beating = False
            if not self.active() or self.view.get("id") != rid:
                return
            if err:
                if getattr(err, "status", 0) == 401:
                    return self.app.on_session_lost()
                # 다음 정규 맥박에 다시 - 세트 끝 무렵이라고 2초마다 몰아치지 않는다 (서버 장애 때, 독립 검토)
                config.log("집중 맥박 실패 (%d초 뒤 다시): %s" % (F.BEAT_SEC, err))
                self._fail_until = time.monotonic() + F.BEAT_SEC
                return self._schedule_beat(F.BEAT_SEC * 1000)
            self._fail_until = 0.0
            self._after_server(r or {})
        run_async(self.root, lambda: self.app.api.focus_beat(), back)

    def _after_server(self, r):
        for c in r.get("sets") or []:
            text = set_text(c)
            if text:
                self._hop()
                self._say(text, BUBBLE_MS)
        if r.get("ended") == "lost":
            return self.leave("lost", r.get("message"))
        run = r.get("running")
        if not run:
            return self.leave("elsewhere")
        if run.get("id") != self.view.get("id"):
            return self.begin(run)
        self._set_view(run)
        self._schedule_beat()

    # ---------------------------------------------------------------- 동기화
    def note(self, card):
        """/api/me 의 focus. 진행 중인 것이 있으면 이어 받고, 없는데 집중 중이면 다른 곳에서 끝난 것."""
        run = (card or {}).get("running")
        if run:
            if run.get("id") in self._closed:
                return                         # 이미 끝난 것을 옛 동기화가 실어 왔다
            if not self.active() or run.get("id") != self.view.get("id"):
                self.begin(run)
                if run.get("stale"):
                    self.beat()                # 끊긴 채 남아 있다 - 맥박을 보내면 서버가 닫는다
            elif not self._beating:
                self._set_view(run)
            return
        if self.active() and not self._beating and not self._stopping:
            # **바로 풀지 않는다** (독립 검토 #2): 시작보다 먼저 읽힌 옛 동기화일 수 있다. 맥박으로 서버에 묻고,
            # 서버가 끝났다고 할 때만 푼다 (_after_server: running 이 없으면 elsewhere · lost 면 lost)
            self.beat()

    def on_pets_synced(self):
        """바탕화면 동기화 뒤. 집중 포켓몬이 바탕화면에서 빠졌으면 끝낸다 (박스로 거둠 · 다른 PC 의 파티 바꾸기)."""
        if not self.active() or self._stopping:
            return
        ov = self.app.overlay
        if ov is None:
            return
        if ov.pets.get(self.pet_id) is None:
            return self.stop(reason="gone")
        self._attach()
        ov.set_only(self.pet_id)               # 새로 생긴 도트도 숨는다

    # ---------------------------------------------------------------- 끝
    def stop(self, done=None, reason="done"):
        if not self.active() or self._stopping:
            return
        self._stopping = True

        def back(r, err):
            self._stopping = False
            if err:
                if getattr(err, "status", 0) == 401:
                    self.app.on_session_lost()
                msg = getattr(err, "message", None) or str(err)
                if reason == "gone":
                    self.leave("gone")         # 서버는 맥박이 끊기면 스스로 닫는다
                if done is not None:
                    done(None, msg)
                return
            r = r or {}
            for c in r.get("sets") or []:
                text = set_text(c)
                if text:
                    self._say(text, BUBBLE_MS)
            if r.get("ended") == "lost":
                self.leave("lost", r.get("message"))
            else:
                self.leave(reason, r.get("message"))
            if done is not None:
                done(r, None)
        run_async(self.root, lambda: self.app.api.focus_stop(), back)

    def leave(self, reason, message=None):
        """집중 모드를 푼다: 도트 · 풀숲을 되살리고, 미뤄 둔 알림을 받으러 동기화를 한 번 부른다."""
        if not self.active():
            return
        rid = self.view.get("id")
        self._closed.add(rid)
        pid = self.pet_id
        self._teardown()
        text = {"elsewhere": ELSEWHERE_MSG, "gone": GONE_MSG}.get(reason) or message
        if reason == "lost" and not text:
            text = "집중이 끝났어요."
        if text:
            self._say(text, END_BUBBLE_MS, pid=pid)
        if self.app.wild is not None:
            try:
                self.app.wild.start()
            except Exception:                               # noqa: BLE001
                pass
        try:
            self.app.request_sync()
        except Exception:                                   # noqa: BLE001
            pass

    def clear(self):
        """서버를 안 부르고 모드만 푼다 (로그인이 끊겼을 때 - 다시 로그인하면 동기화가 이어 받는다)."""
        if self.active():
            self._teardown()

    def _teardown(self):
        for j in (self._tick_job, self._beat_job):
            if j is not None:
                try:
                    self.root.after_cancel(j)
                except Exception:                           # noqa: BLE001
                    pass
        self._tick_job = self._beat_job = None
        self._detach()
        self.view = None
        self.pet_id = None
        self._left = None
        ov = self.app.overlay
        if ov is not None:
            ov.set_only(None)
        self._refresh_tray()

    # ---------------------------------------------------------------- 말
    def _target(self, pid=None):
        ov = self.app.overlay
        if ov is None:
            return None
        pid = pid if pid is not None else self.pet_id
        return ov.pets.get(pid) or next(iter(ov.pets.values()), None)

    def _hop(self):
        pet = self.pet
        if pet is not None and pet.anim_for("Hop") is not None:
            try:
                pet.play("Hop", once=True)
            except Exception:                               # noqa: BLE001
                pass

    def _say(self, text, ms, pid=None):
        self.said.append(text)
        config.log("[집중] %s" % text)
        pet = self._target(pid)
        if pet is None:
            return
        try:
            from .visit import Bubble
            Bubble(self.root, pet, text, ms=ms)
        except Exception as e:                              # noqa: BLE001
            config.log("집중 말풍선 실패: %s" % e)

    def _refresh_tray(self):
        try:
            self.app.refresh_tray()
        except Exception:                                   # noqa: BLE001
            pass
