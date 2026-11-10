# -*- coding: utf-8 -*-
"""공습 (2.3.0) — 그날 시각에 공습을 연다 (서버 server/app/airraid.py · 장면 airraid_show.py).

/api/me 의 'airraid' 카드 {day, dueIn, done} 를 받아(note) 그 시각 + 30~120초 뒤에 연다(fire). 그날 이미 했으면
아무것도 안 한다. 열 때:

  1. 막힘(blocked) - 집중 · 배틀 · 대전 · 놀러 가기 · 숨기기 · 올림픽 중계 중이면 1분 뒤 다시 본다 (서버를 안 부른다)
  2. 서버에 시작(POST /api/airraid/start) - 결과 · 보상은 여기서 정해진다
  3. 공습 포켓몬의 걷는 도트를 받아 두고(작업 스레드) 바탕화면에서 튼다
  4. 끝나면 결과 알림 · 경험치(레벨 · 기술 · 진화) · 동기화

서버가 '이미 했다'(already - 다른 PC · 다시 켬)고 하면 틀지 않고 알리기만 한다. 거절(아직 · 포켓몬이 없다)하면
10분 뒤 다시.
"""
import datetime
import random
import time

from . import config
from .ui_common import run_async

DELAY = (30, 120)            # 그 시각이 지나고 이만큼(초) 뒤에 - 켜자마자 덮치지 않게
RETRY = 60                   # 막혔으면 이만큼 뒤 다시
RETRY_REFUSED = 600          # 서버가 거절했으면


class AirRaidController(object):

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.job = None
        self.wait = None
        self.day = None
        self.jobs_made = 0
        self.tries = 0
        self.show = None
        self._prep = False
        self.rng = random.Random()
        self._gen = 0                # clear() 가 올린다 - 그 전에 부른 서버 답 · 도트 받기 답은 버린다 (로그아웃 뒤)
        self.fire_at = None          # 예약이 울릴 벽시계 (잠자기 뒤 다시 맞추기)
        self.offset = 0.0            # 그날 고른 30~120초
        self.told = None             # 결과를 알린 날 (같은 날 두 번 안 알린다)

    # ---------------------------------------------------------------- 상태
    def busy(self):
        return self._prep or (self.show is not None and not getattr(self.show, "closed", True))

    def blocked(self):
        """지금 바탕화면에서 공습을 못 여는 까닭 (없으면 None)."""
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
            return "pvp"
        v = getattr(app, "visit", None)
        if v is not None and getattr(v, "active", False):
            return "visit"
        o = getattr(app, "olympics", None)
        if o is not None and (o.busy() or (hasattr(o, "on_air") and o.on_air())):
            return "olympics"                    # 중계 중 · 그날 중계 시간 (2시 3분 전 ~ 끝)
        w = getattr(app, "wild", None)
        if w is not None and (getattr(w, "throwing", False) or getattr(w, "pet", None) is not None):
            return "wild"                        # 야생 포켓몬이 나와 있다 (누르기 전 · 던지는 중) - 빼앗지 않는다
        if any(getattr(p, "evolving", False) for p in (getattr(app.overlay, "pets", None) or {}).values()):
            return "evolve"                      # 진화 · 메가 연출 중인 도트를 빼앗지 않는다
        if getattr(app.overlay, "hidden", False):
            return "hidden"
        a = getattr(app, "arche", None)
        if a is not None and hasattr(a, "busy") and a.busy():
            return "arche"                       # 아르케 현상(안농이 걷는 중) · 전설 배틀 창 (2.4.0)
        try:
            from . import stealth
            if stealth.active():
                return "stealth"
        except Exception:                                   # noqa: BLE001
            pass
        return None

    # ---------------------------------------------------------------- 예약
    def note(self, card):
        """/api/me 카드. 그날 것을 한 번만 예약한다."""
        if not card:
            return
        day = card.get("day")
        if card.get("done"):
            self._cancel()
            self.day = day
            if card.get("result") and self.told != day and not self.busy():
                # 다른 PC 에서 했거나, 재생 중 앱을 껐거나 서버 답을 놓쳤다 - 결과만 한 번 (설계)
                self.told = day
                from .airraid_show import result_text
                self.app.notify("오늘 " + result_text({"result": card["result"],
                                                     "reward": card.get("reward")}))
            return
        if card.get("party") == 0:               # 바탕화면에 포켓몬이 없다 - 서버가 거절할 것이라 부르지 않는다
            self._cancel()
            return
        if self.busy():
            return
        due = max(0, int(card.get("dueIn") or 0))
        if self.job is not None and self.day == day:
            # 같은 날 이미 예약했다. 잠자기 · 시계 조정으로 울릴 때가 2분 넘게 어긋났을 때만 다시 맞춘다
            want = time.time() + due + self.offset
            if self.fire_at is None or abs(self.fire_at - want) <= 120:
                return
            return self._schedule(max(0.0, want - time.time()))
        self._cancel()
        self.day = day
        self.offset = self.rng.uniform(*DELAY)
        self._schedule(due + self.offset)

    def _schedule(self, sec):
        self._cancel()
        self.wait = sec
        self.fire_at = time.time() + sec
        self.jobs_made += 1
        self.job = self.root.after(max(1, int(sec * 1000)), self.fire)

    def _cancel(self):
        if self.job is not None:
            try:
                self.root.after_cancel(self.job)
            except Exception:                               # noqa: BLE001
                pass
        self.job = None

    def fire(self):
        """그 시각이 됐다. 막혔으면 미루고, 아니면 서버에 시작을 부른다."""
        self._cancel()                          # 손으로 불렀을 때 걸려 있던 예약도 지운다 (안 지우면 clear 가 못 찾는다)
        self.tries += 1
        if self.busy():
            return
        why = self.blocked()
        if why:
            config.log("[공습] %s - %d초 뒤 다시" % (why, RETRY))
            return self._schedule(RETRY)
        self._prep = True
        hour = datetime.datetime.now().hour
        gen = self._gen

        def back(view, err):
            if gen != self._gen:
                return                           # 그새 로그아웃 (clear) - 늦게 온 답은 버린다
            try:
                if err or not isinstance(view, dict) or not view.get("events"):
                    self._prep = False
                    config.log("[공습] 시작 거절: %s" % (getattr(err, "message", None) or err or "답이 이상하다"))
                    return self._schedule(RETRY_REFUSED)
                if view.get("already"):
                    self._prep = False
                    self.told = self.day
                    from .airraid_show import result_text
                    return self.app.notify("오늘 공습은 이미 끝났어요. " + result_text(view))
                self._fetch(view, lambda: gen == self._gen and self._play(view))
            except Exception as e:                  # noqa: BLE001  (바쁨에 갇히지 않게 - 독립 검토)
                self._prep = False
                config.log("[공습] 답 처리 실패: %s" % e)
                self._schedule(RETRY_REFUSED)
        run_async(self.root, lambda: self.app.api.airraid_start(hour), back)

    # ---------------------------------------------------------------- 재생
    def _fetch(self, view, done):
        """공습 포켓몬의 걷는 도트를 받아 둔다 (작업 스레드). 실패해도 튼다 - 도트가 없는 것은 안 그린다."""
        ov = self.app.overlay
        api = self.app.api
        teams = (view.get("events") or [{}])[0]
        want = []
        for f in (teams.get("foe") or []) + (teams.get("me") or []):
            n = f.get("num")
            if n and (n, False) not in want:
                want.append((n, False))
        if ov is None or not want:
            return done()

        def work():
            from . import sprite_cache, walk_cache
            paths = sprite_cache.ensure_many(api, want)
            walks = walk_cache.ensure_many(api, want)
            return paths, walks

        def back(r, err):
            o = self.app.overlay
            try:
                if not err and r and o is not None:
                    paths, walks = r
                    o.paths.update(dict((k, v) for k, v in (paths or {}).items() if v))
                    o.walks.update(dict((k, v) for k, v in (walks or {}).items() if v and v[0]))
                elif err:
                    config.log("[공습] 도트 받기 실패: %s" % err)
            except Exception as e:                  # noqa: BLE001
                config.log("[공습] 도트 받기 답 처리 실패: %s" % e)
            try:
                done()
            except Exception as e:                  # noqa: BLE001  (바쁨에 갇히지 않게)
                self._prep = False
                config.log("[공습] 장면을 못 열었습니다: %s" % e)
        run_async(self.root, work, back)

    def _play(self, view):
        from .airraid_show import AirRaidShow
        self._prep = False
        if self.app.overlay is None:
            return
        why = self.blocked()
        if why:                                             # 도트를 받는 사이 배틀 · 집중이 시작됐다 - 알리기만
            return self._finish(view)
        self._wild(False)                       # 풀숲을 멈춘다 - 공습 중 만료 · 폴링이 예약을 잃는다 (독립 검토)
        self.show = AirRaidShow(self.app, view, on_done=lambda: self._finish(view))
        self.show.start()

    def _wild(self, on):
        w = getattr(self.app, "wild", None)
        if w is None:
            return
        try:
            w.start() if on else w.stop()
        except Exception as e:                              # noqa: BLE001
            config.log("[공습] 풀숲 %s 실패: %s" % ("켜기" if on else "멈추기", e))

    def _finish(self, view):
        """결과 알림 · 경험치 · 진화 · 동기화. 장면이 끝나든 못 틀든 한 번."""
        self.show = None
        self.told = self.day
        self._wild(True)
        from .airraid_show import result_text
        try:
            self.app.notify(result_text(view))
        except Exception:                                   # noqa: BLE001
            pass
        evolves = []
        try:
            from . import desktop_battle as DB
            msgs, evolves, _main = DB.exp_news(self.app, merge_grants(view.get("exp") or []))
            for m in msgs[:6]:
                self.app.notify(m)
        except Exception as e:                              # noqa: BLE001
            config.log("[공습] 경험치 알림 실패: %s" % e)
        if evolves:
            try:
                from . import desktop_battle as DB
                return DB.play_evolutions(self.app, evolves)   # 끝나면 동기화한다
            except Exception as e:                          # noqa: BLE001
                config.log("[공습] 진화 연출 실패: %s" % e)
        self.app.request_sync()

    def clear(self):
        """로그아웃 · 세션 끊김: 예약 · 장면을 치운다. 오고 있는 서버 답은 버린다(_gen)."""
        self._gen += 1
        self._cancel()
        self._prep = False
        self.day = None
        s, self.show = self.show, None
        if s is not None:
            s.on_done = None
            s.cleanup()


def merge_grants(grants):
    """경험치 결과를 포켓몬마다 하나로 (공습은 쓰러뜨릴 때마다 학습장치 몫까지 받아 한 포켓몬이 여러 번 나온다 -
    '레벨 N!' 이 겹치고 앞 여섯 줄에서 배운 기술 알림이 잘렸다, 독립 검토). 마지막 레벨 · 배운 기술 합침 ·
    배우려는 기술 합침 · 진화는 마지막 것. 싸운 몫(shared=False)이 하나라도 있으면 그 포켓몬은 싸운 쪽."""
    out, by = [], {}
    for g in grants or []:
        k = g.get("id")
        m = by.get(k)
        if m is None:
            m = by[k] = dict(g, learned=list(g.get("learned") or []), pending=list(g.get("pending") or []),
                             pendingIds=list(g.get("pendingIds") or []))
            out.append(m)
            continue
        m["leveledUp"] = bool(m.get("leveledUp") or g.get("leveledUp"))
        m["level"] = max(m.get("level") or 0, g.get("level") or 0)
        m["gained"] = (m.get("gained") or 0) + (g.get("gained") or 0)
        for key in ("learned", "pending", "pendingIds"):
            for x in g.get(key) or []:
                if x not in m[key]:
                    m[key].append(x)
        if g.get("evolve"):
            m["evolve"] = g["evolve"]
        if not g.get("shared"):
            m["shared"] = False
    return out
