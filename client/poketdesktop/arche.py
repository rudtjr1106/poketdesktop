# -*- coding: utf-8 -*-
"""아르케의 여섯 봉인 (시즌 6, 2.4.0) — 앱 쪽 진행.

서버(server/app/arche.py)가 장 · 정답 · 의식 · 전설을 쥔다. 여기서는

    * 이벤트 기간에만 60초마다 `/api/arche` 를 묻는다 (`/api/me` 카드가 켜고 끈다)
    * 지금 일어날 바탕화면 현상을 받아 그 시각에 띄운다 (arche_desktop) - **미리 받지 않는다**
    * 본 현상은 앱 안 기록(POKET_HOME/arche_seen.json)에 남긴다 - 일지의 '내가 본 것'
    * 브라우저 창 제목 (윈도우, 설정 '브라우저 단서 찾기'): 열린 장의 제목 해시와 맞을 때만 서버로 (arche_title)
    * 의식이 새로 맞으면: 일지 창 → 도장 → 사진이 창 가득 → 입장 장면 → 전설 배틀 (막혀 있으면 풀릴 때까지 미룬다)
    * 새 장이 열리면 게임 안 알림

화면은 ui_arche (일지) · arche_battle (전설 배틀) · arche_desktop (현상) 이 그린다.
"""
import datetime
import hashlib
import json
import os
import time

from . import config
from .ui_common import run_async

POLL = 60                 # 기본 폴링 (초) - 서버가 state.poll 로 바꿀 수 있다
RETRY = 120               # 서버가 답하지 않을 때
ENTRY_RETRY = 20          # 의식이 맞았는데 지금 바탕화면이 막혀 있을 때 다시 보는 간격 (초)
LOCAL = "arche_local%s.json"     # 계정마다 따로 (같은 PC 다른 계정과 섞이지 않게 - 리뷰)
SEEN = "arche_seen%s.json"
SEEN_MAX = 400


def _parse(iso):
    try:
        t = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=datetime.timezone.utc)
        return t.timestamp()
    except Exception:                                       # noqa: BLE001
        return None


def _path(name):
    return os.path.join(config.data_dir(), name)


def _load(name, default):
    try:
        with open(_path(name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:                                       # noqa: BLE001
        return default


def _save(name, obj):
    try:
        p = _path(name)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception as e:                                  # noqa: BLE001
        config.log("아르케 기록 저장 실패: %s" % e)


class ArcheController(object):

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.card = None
        self.state = None
        self.job = None
        self.skew = 0.0                  # 서버 시각 - 내 시각 (초)
        self._gen = 0                    # clear() 가 올린다 - 그 전에 부른 답은 버린다
        self.pending = {}                # 현상 id -> after job
        self.shows = []                  # 돌고 있는 현상 연출
        self.title = None                # arche_title.TitleWatch
        self.window = None               # ui_arche.JournalWindow
        self.battle = None               # arche_battle.ArcheBattleWindow
        self.entry_job = None
        self.told_entry = set()
        self._opening = False            # 배틀 판을 여는 중 (자동 입장과 단추가 겹쳐도 한 번만 - 리뷰 I3)
        who = str(getattr(app, "username", "") or "")
        tag = ("_" + hashlib.sha1(who.encode("utf-8")).hexdigest()[:10]) if who else ""
        self.f_local, self.f_seen = LOCAL % tag, SEEN % tag
        self.local = _load(self.f_local, {}) or {}
        self.local.setdefault("entered", [])        # 입장 연출을 이미 본 장
        self.local.setdefault("done", [])           # 이미 띄운 현상 id
        self.local.setdefault("chapter", 0)         # 마지막으로 알린 장
        self.seen = _load(self.f_seen, []) or []

    # ---------------------------------------------------------------- 상태
    def on(self):
        c = self.card or {}
        return bool(c.get("active"))

    PASSIVE = ("relic", "stars")         # 바탕화면에 가만히 놓여 있는 현상 (누르기 · 보기를 기다린다) - 무엇도 막지 않는다

    def busy(self):
        """움직이는 현상(안농이 걷는 중 등)이 돌거나 전설 배틀 창이 열려 있다 (다른 기능의 막힘 판정이 본다).
        유물 · 별처럼 놓여서 기다리는 것은 셈하지 않는다 - 15분 남아 있는 유물이 입장을 막았다 (11/09 시연)."""
        self.shows = [s for s in self.shows if not getattr(s, "closed", False)]
        b = self.battle
        moving = [s for s in self.shows if getattr(s, "kind", None) not in self.PASSIVE]
        return bool(moving) or (b is not None and getattr(b, "alive", False))

    def battle_open(self):
        b = self.battle
        return b is not None and getattr(b, "alive", False)

    def label(self):
        st = self.state or {}
        n = st.get("chapter") or 0
        return "아르케의 일지 (제%d장)" % n if n else "아르케의 일지"

    def blocked(self):
        """지금 바탕화면에 현상을 띄우거나 입장을 열 수 없는 까닭 (공습과 같은 기준). 없으면 None."""
        app = self.app
        r = getattr(app, "airraid", None)
        if r is not None and hasattr(r, "blocked"):
            why = r.blocked()
            if why:
                return why
            if r.busy():
                return "raid"
        elif getattr(app, "overlay", None) is None:
            return "overlay"
        return None

    def now(self):
        return time.time() + self.skew

    def chapter(self, n):
        for c in (self.state or {}).get("chapters") or []:
            if int(c.get("n") or 0) == int(n):
                return c
        return None

    # ---------------------------------------------------------------- 폴링
    def note(self, card):
        """/api/me 카드 (옛 서버는 없다). 기간이면 폴링을 켜고, 아니면 끈다."""
        self.card = card or None
        if self.on():
            if self.job is None:
                self.poll()
        else:
            self._stop_poll()
            self._stop_title()

    def poll(self):
        self._stop_poll()
        gen = self._gen
        api = getattr(self.app, "api", None)
        if api is None:
            return

        def done(st, err):
            if gen != self._gen:
                return
            if err or not isinstance(st, dict):
                self._next(RETRY)
                return
            self._got(st)
            self._next(int(st.get("poll") or POLL))

        run_async(self.root, api.arche_state, done)

    def check(self):
        """열쇠 아이템을 썼다 · 집중 세트가 끝났다 - 의식을 지금 다시 본다."""
        if not self.on():
            return
        gen = self._gen
        api = self.app.api

        def done(st, err):
            if gen != self._gen or err or not isinstance(st, dict):
                return
            self._got(st)

        run_async(self.root, api.arche_check, done)

    def _next(self, sec):
        self._stop_poll()
        if self.on():
            self.job = self.root.after(max(5, int(sec)) * 1000, self.poll)

    def _stop_poll(self):
        if self.job is not None:
            try:
                self.root.after_cancel(self.job)
            except Exception:                               # noqa: BLE001
                pass
        self.job = None

    def _got(self, st):
        """서버 state 를 받았다."""
        now_srv = _parse(st.get("now"))
        if now_srv:
            self.skew = now_srv - time.time()
        self.state = st
        if not st.get("active") or not st.get("ready", True):
            self._stop_title()
            self._refresh_window()
            return
        self._phenomena(st.get("phenomena") or [])
        self._titles()
        self._new_chapter(st)
        self._rituals()
        self._refresh_window()

    # ---------------------------------------------------------------- 현상
    def _phenomena(self, items):
        done = set(self.local.get("done") or [])
        for ph in items:
            pid = ph.get("id")
            if not pid or pid in done or pid in self.pending:
                continue
            at = _parse(ph.get("at")) or self.now()
            until = _parse(ph.get("until")) or (at + 60)
            if self.now() > until:
                continue
            delay = max(0.0, at - self.now())
            self.pending[pid] = self.root.after(int(delay * 1000) + 50, lambda p=ph: self._fire(p))

    def _fire(self, ph):
        pid = ph.get("id")
        self.pending.pop(pid, None)
        until = _parse(ph.get("until")) or self.now()
        why = self.blocked()
        if why:
            if self.now() + 5 < until:                       # 그 현상이 끝나기 전이면 조금 뒤에 다시
                self.pending[pid] = self.root.after(5000, lambda p=ph: self._fire(p))
            return
        self._mark_done(pid)
        try:
            from . import arche_desktop
            ph = dict(ph, left=max(1.0, until - self.now()))     # 남은 시간은 서버 시계로 (PC 시계가 틀려도)
            show = arche_desktop.play(self.app, ph, self._seen)
            if show is not None:
                self.shows.append(show)
        except Exception as e:                              # noqa: BLE001
            config.log("아르케 현상 실패 (%s): %s" % (ph.get("kind"), e))

    def _mark_done(self, pid):
        done = list(self.local.get("done") or [])
        if pid not in done:
            done.append(pid)
            self.local["done"] = done[-500:]
            _save(self.f_local, self.local)

    def _seen(self, ph, img=None):
        """현상을 실제로 봤다 - 일지의 '내가 본 것' 에 남긴다 (앱 안에만)."""
        data = ph.get("data") or {}
        if data.get("parade"):
            return self._seen_parade(ph, data)
        row = {"id": ph.get("id"), "kind": ph.get("kind"), "at": time.time() + self.skew,
               "glyph": data.get("glyph"), "text": data.get("text"),
               "pts": data.get("pts") if ph.get("kind") == "stars" else None}
        if any(r.get("id") == row["id"] for r in self.seen):
            return
        self.seen.append(row)
        self.seen = self.seen[-SEEN_MAX:]
        _save(self.f_seen, self.seen)
        self._refresh_window()

    def _seen_parade(self, ph, data):
        """안농 행렬(줄지어 한 번에 걷는 글자들 - 혼자서도 깰 수 있게, 11/11)은 행렬 하나를 '내가 본 것' 한 줄로 모은다.
        글자는 행렬 안 자리(pos)에 넣는다 - 놓친 자리는 빈칸으로 남는다."""
        rid = "parade:%s" % data.get("parade")
        try:
            of, pos = max(0, int(data.get("of") or 0)), int(data.get("pos"))
        except (TypeError, ValueError):
            return
        if not 0 < of <= 64 or not 0 <= pos < of:
            return
        row = next((r for r in self.seen if r.get("id") == rid), None)
        if row is None:
            row = {"id": rid, "kind": "parade", "at": time.time() + self.skew, "glyphs": [None] * of}
            self.seen.append(row)
        gl = list(row.get("glyphs") or [])
        gl += [None] * (of - len(gl))
        if gl[pos] is not None:
            return
        gl[pos] = data.get("glyph")
        row["glyphs"] = gl
        self.seen = self.seen[-SEEN_MAX:]
        _save(self.f_seen, self.seen)
        self._refresh_window()

    def seen_in(self, n):
        """n 장이 열려 있던 동안 본 것들 (시각 차례)."""
        c = self.chapter(n) or {}
        a, b = _parse(c.get("opensAt")), _parse(c.get("closesAt"))
        out = []
        for r in self.seen:
            t = r.get("at") or 0
            if (a is None or t >= a) and (b is None or t < b):
                out.append(r)
        return sorted(out, key=lambda r: r.get("at") or 0)

    # ---------------------------------------------------------------- 창 제목
    def _title_hashes(self):
        out = []
        for c in (self.state or {}).get("chapters") or []:
            hs = c.get("titleHashes") or []
            if c.get("open") and not c.get("ritual") and hs:
                out.append((int(c["n"]), c.get("titleSalt") or "", set(hs)))
        return out

    def _titles(self):
        want = bool(self._title_hashes()) and bool(self.app.settings.get("archeTitle", True))
        if not want:
            return self._stop_title()
        if self.title is None:
            try:
                from . import arche_title
                self.title = arche_title.TitleWatch(self.root, self._title_hashes, self._title_hit,
                                                    enabled=lambda: bool(self.app.settings.get("archeTitle", True)))
                self.title.start()
            except Exception as e:                          # noqa: BLE001
                config.log("아르케 창 제목 읽기를 못 켰다: %s" % e)
                self.title = None

    def _stop_title(self):
        if self.title is not None:
            try:
                self.title.stop()
            except Exception:                               # noqa: BLE001
                pass
        self.title = None

    def _title_hit(self, n, text):
        """브라우저 맨 앞 창 제목이 n 장의 열쇠와 맞았다 (앱 안에서 해시로 비교한 뒤)."""
        self.send_key(n, text, via="title")

    def send_key(self, n, text, via="type", done=None):
        """떠오른 말을 서버에 보낸다. done(r, err) 는 일지 창이 결과 글을 쓰려고 준다."""
        gen = self._gen

        def back(r, err):
            if gen != self._gen:
                return
            if not err and isinstance(r, dict):
                if r.get("state"):
                    self._got(r["state"])
                if r.get("ok") and via == "title":
                    self._react()
            if done:
                done(r, err)

        run_async(self.root, lambda: self.app.api.arche_key(n, text, via), back)

    def _react(self):
        """창 제목이 맞았을 때 바탕화면이 응답한다 (포켓몬들이 잠깐 떨고 한 줄)."""
        self.app.notify("브라우저 너머에서 무언가가 응답했다… 바탕화면의 포켓몬들이 술렁인다.")
        if self.blocked():
            return
        try:
            from . import arche_desktop
            s = arche_desktop.play(self.app, {"id": "react-%d" % int(time.time()), "kind": "tremor",
                                              "data": {"dir": 1}}, None)
            if s is not None:
                self.shows.append(s)
        except Exception:                                   # noqa: BLE001
            pass

    # ---------------------------------------------------------------- 장 · 의식
    def _new_chapter(self, st):
        n = int(st.get("chapter") or 0)
        if n and n > int(self.local.get("chapter") or 0):
            self.local["chapter"] = n
            _save(self.f_local, self.local)
            c = self.chapter(n) or {}
            self.app.notify("고고학자의 일지가 새로 쓰였다 — 제%d장 「%s」. 트레이 메뉴의 '아르케의 일지'에서 볼 수 있어요."
                            % (n, c.get("title") or "?"))

    def _rituals(self):
        for c in (self.state or {}).get("chapters") or []:
            n = int(c.get("n") or 0)
            if c.get("ritual") and n not in self.local.get("entered", []):
                if any(e.get("state") == "ready" for e in c.get("encounters") or []):
                    self._want_entry(n)
                    return

    def _want_entry(self, n):
        if self.entry_job is not None:
            return
        # 바탕화면 현상은 입장을 막지 않는다 (일지 · 배틀은 창이다). 집중 · 숨기기 · 다른 배틀 같은 것만 기다린다.
        why = self.blocked()
        if why or self.battle_open():
            if n not in self.told_entry:
                self.told_entry.add(n)
                self.app.notify("봉인이 풀렸다! 지금 하던 것이 끝나면 아르케의 일지가 열려요.")
            self.entry_job = self.root.after(ENTRY_RETRY * 1000, lambda: self._retry_entry(n))
            return
        self.local["entered"] = sorted(set(self.local.get("entered", [])) | {n})
        _save(self.f_local, self.local)
        w = self.open_window(n)
        if w is not None:
            w.unsealed(n)

    def _retry_entry(self, n):
        self.entry_job = None
        self._want_entry(n)

    # ---------------------------------------------------------------- 창
    def open_window(self, n=None):
        from . import ui_arche
        w = self.window
        if w is None or not w.alive:
            self.window = w = ui_arche.JournalWindow(self.app, self)
        else:
            w.focus()
        if n:
            w.show_chapter(n)
        return w

    def _refresh_window(self):
        w = self.window
        if w is not None and w.alive:
            try:
                w.refresh()
            except Exception as e:                          # noqa: BLE001
                config.log("아르케 일지 다시 그리기 실패: %s" % e)

    def open_battle(self, n, slot, geometry=None, on_close=None):
        """전설과의 판을 연다 (일지 창이 부른다). 여는 중이거나 이미 열려 있으면 또 열지 않는다 (리뷰 I3)."""
        if self._opening or self.battle_open():
            return
        self._opening = True
        gen = self._gen
        c = self.chapter(n) or {}

        def done(data, err):
            self._opening = False
            if gen != self._gen:
                return
            if err:
                if on_close:
                    on_close(getattr(err, "message", str(err)))
                return
            from .arche_battle import ArcheBattleWindow
            place = data.get("place") or c.get("place") or "cave"

            def closed():
                self.battle = None
                if on_close:
                    on_close(None)
                self.poll()

            def nxt(info, geo=None):
                """'더 안쪽으로' (다음 석실) - 배틀 창이 자리를 넘겨준다."""
                info = info or {}
                self.open_battle(info.get("chapter", n), info.get("slot", slot + 1), geo or geometry, on_close)

            self.battle = ArcheBattleWindow(self.app, data, place, geometry=geometry, on_close=closed, on_next=nxt)

        run_async(self.root, lambda: self.app.api.arche_battle(n, slot), done)

    # ---------------------------------------------------------------- 정리
    def clear(self):
        """로그아웃 · 세션 끊김: 예약 · 연출 · 창을 치운다."""
        self._gen += 1
        self._stop_poll()
        self._stop_title()
        for job in list(self.pending.values()):
            try:
                self.root.after_cancel(job)
            except Exception:                               # noqa: BLE001
                pass
        self.pending = {}
        if self.entry_job is not None:
            try:
                self.root.after_cancel(self.entry_job)
            except Exception:                               # noqa: BLE001
                pass
            self.entry_job = None
        for s in self.shows:
            try:
                s.cleanup()
            except Exception:                               # noqa: BLE001
                pass
        self.shows = []
        for w in (self.window, self.battle):
            if w is not None:
                try:
                    w.close()
                except Exception:                           # noqa: BLE001
                    pass
        self.window = None
        self.battle = None
        self.card = None
        self.state = None
