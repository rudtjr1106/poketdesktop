# -*- coding: utf-8 -*-
"""포스크탑 올림픽 — 앱 쪽: 경기 시각(오후 2시) 중계 예약 · 다른 기능과 겹칠 때 · 결과 카드.

    o = OlympicsController(app)
    o.note(me["olympics"])      동기화마다: 다음 경기까지 남은 초로 2시 중계를 예약한다 (켰을 때 중계 중이면 바로)
    o.replay(entry_id, done)    올림픽 창의 '다시 보기' / '경기 보기'
    o.busy()                    중계 중인가 (그동안 풀숲 · 집중 시작 · 대전을 막는다)
    o.clear()                   로그아웃 · 세션 끊김

규칙은 common/olympics.py, 서버는 server/app/olympics.py, 중계는 olympics_show.py, 창은 ui_olympics.py.

## 2시 (사용자 결정 11/06)

평일 경기 날 14:00 이 되면 /api/olympics/live 를 부른다 - 서버가 그날 경기를 치르고 내 조 각본을 준다. 종목마다 정해진
때(프로그램: 100m 0:20 · 수영 1:40 …)에 그 조를 중계한다. 시각은 서버가 센 '몇 초 뒤' 로 받는다 - PC 시계가 틀려도 맞다.
앱이 2시에 꺼져 있었으면 켰을 때 남은 종목부터 중계하고, 지나간 것은 말풍선으로 '다시 보기' 를 알린다.

## 겹칠 때

포켓몬과 집중 · 배틀 · 투기장 · 놀러 가기 · 긴급 숨기기 중이면 그 종목 중계는 건너뛴다 (말풍선 한 번, 다시 보기로 본다).
중계 중에는 풀숲이 쉬고(wild_ui._focusing), 집중 시작 · 대전 걸기가 막힌다 (app._busy_desk).
"""
import time

from common import olympics as O
from common import tint as T

from . import config, sprite_cache, walk_cache
from .ui_common import run_async

ANIMS = ("Idle", "Hop", "Hurt")      # 선수 도트가 쓰는 동작 (걷기 말고)
LATE_SEC = 25                        # 중계 시작이 이만큼 지났으면 놓친 것 (다시 보기로)
READY_WAIT_MS = 9000                 # 도트를 받는 동안 중계를 이만큼까지 기다린다
RETRY_MS = 20000
CARD_MS = 15000
NOTICE_KEY = "olympicsNotice"        # 신청 안내 말풍선을 띄운 경기 날 (하루 한 번)
SKIP_MSG = {
    "focus": "포켓몬과 집중하는 중이라",
    "battle": "배틀 중이라",
    "arena": "대전 중이라",
    "visit": "놀러 가 있는 중이라",
    "stealth": "숨겨 둔 중이라",
    "pvp": "대전을 준비하는 중이라",
}


class OlympicsController(object):

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.card = None             # /api/me 의 olympics
        self.live = None             # 마지막으로 받은 그날 경기
        self.loaded = None           # 중계를 예약한 경기 날
        self.show = None             # 지금 중계 (olympics_show.Show)
        self.queue = []
        self.missed = []
        self.said = []               # 띄운 말 (검사 · 기록)
        self.result_card = None
        self._jobs = []
        self._start_job = None
        self._loading = False
        self._prep = False           # 중계를 준비하는 중 (각본 · 도트를 받는 중) - 이때도 바쁘다
        self._gen = 0                # clear() 마다 늘린다 - 그 전에 보낸 요청의 답은 버린다
        self._skip_said = set()

    # ---------------------------------------------------------------- 상태
    def busy(self):
        return self._prep or (self.show is not None and getattr(self.show, "alive", False))

    def on(self):
        """트레이에 줄을 둘 때인가 (신청 받는 중 · 경기 중 · 끝난 뒤 기록실)."""
        c = self.card or {}
        return c.get("phase") in ("entry", "live", "done") or (
            c.get("phase") == "before" and (c.get("openIn") or 0) <= 86400)

    def label(self):
        c = self.card or {}
        ph = c.get("phase")
        if self.busy():
            return "포스크탑 올림픽 · 중계 중"
        if ph == "live":
            return "포스크탑 올림픽 · 경기 중!"
        if ph == "entry":
            n = c.get("entries") or 0
            return "포스크탑 올림픽 (신청 %d/%d)..." % (n, len(O.KEYS))
        if ph == "done":
            return "포스크탑 올림픽 · 결과..."
        return "포스크탑 올림픽..."

    def blocked(self):
        """지금 바탕화면에서 중계를 못 하는 까닭 (없으면 None)."""
        app = self.app
        if app.overlay is None:
            return "overlay"
        f = getattr(app, "focus", None)
        if f is not None and f.active():
            return "focus"
        b = getattr(app, "battle", None)
        if b is not None and not getattr(b, "closed", False):
            return "battle"
        if getattr(app, "arena", None):
            return "arena"
        if getattr(app, "_pvp_busy", False) or getattr(app, "_match_loading", False):
            return "pvp"                         # 대전 상대를 찾는 중 · 대전을 불러오는 중 (곧 투기장이 바탕화면을 쥔다)
        v = getattr(app, "visit", None)
        if v is not None and getattr(v, "active", False):
            return "visit"
        try:
            from . import stealth
            if stealth.active():
                return "stealth"
        except Exception:                                   # noqa: BLE001
            pass
        return None

    # ---------------------------------------------------------------- 동기화
    def note(self, card):
        self.card = card
        if not card:
            return
        ph = card.get("phase")
        day = card.get("nextDay")
        if ph == "entry" and day:
            self._notice_entry(card)
        starts, end = card.get("startsIn"), card.get("endIn")
        if day and starts is not None:
            if starts <= 0 < (end or 0):
                if self.loaded != day:
                    self.load_live(day)
            elif 0 < starts <= 6 * 3600:
                self._arm(starts, day)
        if ph == "done" and card.get("medals"):
            self._notice_medals(card)

    def _arm(self, starts, day):
        """2시에 그날 경기를 부르도록 예약한다 (동기화마다 다시 맞춘다 - 잠들었다 깬 PC 도 맞게)."""
        if self._start_job is not None:
            try:
                self.root.after_cancel(self._start_job)
            except Exception:                               # noqa: BLE001
                pass
        self._start_job = self.root.after(int(starts * 1000) + 1500, lambda: self.load_live(day))

    def _after(self, ms, fn):
        job = self.root.after(max(0, int(ms)), fn)
        self._jobs.append(job)
        return job

    # ---------------------------------------------------------------- 2시
    def load_live(self, day=None):
        self._start_job = None
        if self._loading or self.app.api is None:
            return
        if day is not None and self.loaded == day:
            return
        self._loading = True
        self.loaded = day
        gen = self._gen

        def back(r, err):
            if gen != self._gen:
                return                          # 그사이 로그아웃했다 - 앞 계정의 경기를 틀지 않는다
            self._loading = False
            if err:
                config.log("올림픽 경기 받기 실패: %s" % err)
                self.loaded = None
                if getattr(err, "status", 0) == 401:
                    return
                return self._after(RETRY_MS, lambda: self.load_live(day))
            r = r or {}
            if not r.get("day"):
                self.loaded = None
                return
            self.loaded = r["day"]
            self._schedule(r)
        run_async(self.root, lambda: self.app.api.olympics_live(), back)

    def _schedule(self, r):
        self.live = r
        heats = r.get("heats") or []
        prog = dict((p["event"], p) for p in r.get("program") or [])
        ready = {"ok": not heats}               # 이 경기 날 선수 도트를 다 받았나 (조마다 같이 쓴다)
        if heats:
            self._fetch(heats, lambda: ready.update(ok=True))
        late = []
        for h in heats:
            show_in = (prog.get(h["event"]) or {}).get("showIn", 0)
            if show_in < -LATE_SEC:
                late.append(h)
            else:
                self._after(max(0, show_in) * 1000, (lambda hh: lambda: self._due(hh, ready))(h))
        self.missed += late
        n = len(heats)
        if r.get("elapsed", 0) < 90:
            if n:
                self._tell("%s! 포스크탑 올림픽 %d일째 - 오늘 내 포켓몬이 %d종목에 나가요!"
                           % (O.at_text(), r.get("dayNo") or 1, n))
            else:
                self._tell("%s! 포스크탑 올림픽 %d일째 경기가 시작됐어요." % (O.at_text(), r.get("dayNo") or 1))
        if late:
            self._tell("지나간 경기 %d개는 올림픽 창에서 다시 볼 수 있어요." % len(late))
        self._refresh_tray()

    def _due(self, heat, ready=None):
        why = self.blocked()
        if why:
            return self._skip(heat, why)
        if self.busy():
            self.queue.append((heat, ready))    # 다른 중계 · 다시 보기 준비가 끝나면
            return
        self._play(heat, ready=ready)

    def _skip(self, heat, why):
        self.missed.append(heat)
        key = (self.loaded, why)
        if why in SKIP_MSG and key not in self._skip_said:
            self._skip_said.add(key)
            self._tell("%s 올림픽 중계는 건너뛰었어요. 올림픽 창에서 다시 볼 수 있어요." % SKIP_MSG[why])

    def _play(self, heat, replay=False, ready=None, waited=0):
        """중계를 연다. **부른 순간부터 바쁨이다** (_prep) - 도트를 기다리는 9초 동안 다른 중계 · 다시 보기가 끼어들면
        Show 가 둘 동시에 돌았다 (독립 검토 #1). 기다린 뒤 겹침을 한 번 더 본다."""
        gen = self._gen
        self._prep = True
        if ready is not None and not ready.get("ok") and waited < READY_WAIT_MS:
            return self._after(500, lambda: gen == self._gen and self._play(heat, replay, ready, waited + 500))
        self._prep = False
        why = self.blocked()
        if why:                                 # 기다리는 사이 집중 · 배틀이 시작됐다
            if not replay:
                self._skip(heat, why)
            return self._next()
        from .olympics_show import Show
        wild = getattr(self.app, "wild", None)
        if wild is not None:
            try:
                wild.stop()
            except Exception:                               # noqa: BLE001
                pass
        self._close_card()
        show = Show(self.app, heat, on_done=self._done, replay=replay)
        self.show = show
        self._refresh_tray()
        try:
            show.start()                        # 준비 중 오류는 Show 가 스스로 접고 _done 을 부른다
        except Exception as e:                              # noqa: BLE001
            config.log("올림픽 중계 시작 실패: %s" % e)
            if self.show is show:
                self.show = None
                self._next()

    def _done(self, show, result):
        if show is not self.show:
            return                              # 이미 치운 중계 (로그아웃 등)
        self.show = None
        if result and not result.get("aborted") and result.get("entryId"):
            self._card(show.heat, result)
        self._next()

    def _next(self):
        """줄 선 중계가 있으면 잠깐 쉬고 다음, 없으면 풀숲을 다시 켠다."""
        if self.queue:
            nxt, ready = self.queue.pop(0)
            return self._after(1500, lambda: self._due(nxt, ready))
        if not self.busy():
            wild = getattr(self.app, "wild", None)
            if wild is not None:
                try:
                    wild.start()
                except Exception:                           # noqa: BLE001
                    pass
        self._refresh_tray()

    # ---------------------------------------------------------------- 다시 보기
    def replay(self, entry_id, done=None):
        def tell(r, err):
            if done is not None:
                try:
                    done(r, err)
                except Exception:                           # noqa: BLE001
                    pass
        why = self.blocked()
        if why:
            return tell(None, "%s 지금은 볼 수 없어요." % SKIP_MSG.get(why, "지금은"))
        if self.busy():
            return tell(None, "지금 다른 경기를 중계하고 있어요.")
        self._prep = True                       # 각본을 받는 동안에도 바쁨 (두 번 눌러도 하나)
        gen = self._gen

        def back(h, err):
            if gen != self._gen:
                return
            if err:
                self._prep = False
                tell(None, getattr(err, "message", None) or str(err))
                return self._next()
            ready = {"ok": False}
            self._fetch([h], lambda: ready.update(ok=True))
            self._play(h, replay=True, ready=ready)
            tell(h, None)
        run_async(self.root, lambda: self.app.api.olympics_heat(entry_id), back)

    # ---------------------------------------------------------------- 남의 도트 받기
    def _fetch(self, heats, done):
        """같은 조 선수들의 걷기 · 동작 도트를 받아 둔다 (작업 스레드)."""
        ov = self.app.overlay
        api = self.app.api
        want = []
        for h in heats:
            for e in h.get("entrants") or []:
                p = e.get("pokemon") or {}
                sk = T.skin({"shiny": p.get("shiny"), "tint": p.get("tint")})
                for n in (p.get("look") or p.get("num"), p.get("num")):
                    if n and (n, sk) not in want:
                        want.append((n, sk))
        if ov is None or api is None or not want:
            return done()
        have_s = dict(ov.sheets)

        def work():
            paths = sprite_cache.ensure_many(api, want)
            walks = walk_cache.ensure_many(api, want)
            sheets = {}
            for n, sk in want:
                if not (walks.get(walk_cache.key(n, sk)) or (None,))[0]:
                    continue
                for a in ANIMS:
                    k = walk_cache.sheet_key(n, a, sk)
                    if k not in have_s:
                        sheets[k] = walk_cache.ensure(api, n, a, shiny=sk)
            return paths, walks, sheets

        def back(r, err):
            if not err and r and self.app.overlay is not None:
                paths, walks, sheets = r
                o = self.app.overlay
                o.paths.update(dict((k, v) for k, v in (paths or {}).items() if v))
                o.walks.update(dict((k, v) for k, v in (walks or {}).items() if v and v[0]))
                o.sheets.update(sheets or {})
            elif err:
                config.log("올림픽 선수 도트 받기 실패: %s" % err)
            done()
        run_async(self.root, work, back)

    # ---------------------------------------------------------------- 말 · 카드
    def _target(self):
        ov = self.app.overlay
        if ov is None:
            return None
        pets = [p for p in ov.pets.values() if (p.id or 0) > 0]
        return pets[0] if pets else None

    def _tell(self, text, ms=6000):
        self.said.append(text)
        config.log("[올림픽] %s" % text)
        pet = self._target()
        if pet is None or self.busy():
            return
        try:
            from .visit import Bubble
            Bubble(self.root, pet, text, ms=ms)
        except Exception as e:                              # noqa: BLE001
            config.log("올림픽 말풍선 실패: %s" % e)

    def _notice_entry(self, card):
        day = card.get("nextDay")
        s = self.app.settings
        if s.get(NOTICE_KEY) == day or (card.get("entries") or 0) >= len(O.KEYS):
            return
        s[NOTICE_KEY] = day
        try:
            config.save_settings(s)
        except Exception:                                   # noqa: BLE001
            pass
        self._tell("포스크탑 올림픽 %d일째 신청을 받고 있어요! %s %s에 다 같이 경기해요. (트레이 → 포스크탑 올림픽)"
                   % (card.get("dayNo") or 1, "%s월 %s일" % (int(day[5:7]), int(day[8:10])), O.at_text()), 9000)

    def _notice_medals(self, card):
        s = self.app.settings
        if s.get(NOTICE_KEY) == "medals":
            return
        s[NOTICE_KEY] = "medals"
        try:
            config.save_settings(s)
        except Exception:                                   # noqa: BLE001
            pass
        self._tell("포스크탑 올림픽이 끝났어요! 메달 %d개를 땄어요. 올림픽 창에서 확인해 보세요." % card["medals"], 9000)

    def _card(self, heat, result):
        try:
            from .ui_olympics import ResultCard
            self.result_card = ResultCard(self.app, heat, result, ms=CARD_MS)
        except Exception as e:                              # noqa: BLE001
            config.log("올림픽 결과 카드 실패: %s" % e)

    def _close_card(self):
        c, self.result_card = self.result_card, None
        if c is not None:
            try:
                c.close()
            except Exception:                               # noqa: BLE001
                pass

    def _refresh_tray(self):
        try:
            self.app.refresh_tray()
        except Exception:                                   # noqa: BLE001
            pass

    # ---------------------------------------------------------------- 정리
    def clear(self):
        """로그아웃 · 세션 끊김: 예약 · 중계 · 카드를 치우고 받아 둔 것을 잊는다. **풀숲은 다시 켜지 않는다** - 중계의
        끝 처리(_done)를 끊고 멈춘다. 받는 중이던 답은 _gen 이 바뀌어 버려진다 (다른 계정에 앞 계정 경기가 안 뜬다)."""
        self._gen += 1
        for j in self._jobs + ([self._start_job] if self._start_job else []):
            try:
                self.root.after_cancel(j)
            except Exception:                               # noqa: BLE001
                pass
        self._jobs = []
        self._start_job = None
        self.queue = []
        self.loaded = None
        self.live = None
        self.card = None
        self.missed = []
        self._loading = False
        self._prep = False
        show, self.show = self.show, None
        if show is not None:
            show.on_done = None
            try:
                show.stop()
            except Exception:                               # noqa: BLE001
                pass
        self._close_card()
