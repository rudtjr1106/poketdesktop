# -*- coding: utf-8 -*-
"""아르케 (2.4.0) — 브라우저 창 제목으로 열쇠 알아채기 (윈도우).

서버가 그 장의 **제목 열쇠 해시**(`sha256(소금 + 정규화한 말)`)와 소금을 준다. 여기서는 몇 초마다 **맨 앞 창의
제목 하나만** 읽어 (PLAT.foreground_title - 윈도우만, 다른 OS 는 None) 브라우저 꼬리를 떼고 정규화해 해시를 견준다.

    맞을 때만     on_hit(맞은 말) - 부르는 쪽(컨트롤러)이 그 말을 서버에 보낸다
    안 맞으면     아무 데도 안 남기고 안 보낸다. 지난 제목도 **글자가 아니라 지문(sha256)으로만** 들고 있다
                  (같은 제목을 3초마다 다시 셈하지 않으려고)
    해시가 비면   (이벤트 밖 · 제목 열쇠 없는 장 · 이미 의식을 마침) 제목을 읽지도 않는다
    설정이 꺼지면 ('브라우저 단서 찾기') 읽지 않는다

정답은 앱에 없다 - 해시만 있다. 말 정규화 · 꼬리 떼기 · 해시는 서버와 같은 common/arche.py 를 쓴다.
"""
import hashlib
import re

from . import config
from . import platform_os as PLAT

EVERY_MS = 3000
# 사이트 이름이 붙은 제목 ('문서 이름 - 사이트 - Chrome') 은 꼬리를 뗀 뒤 ' - ' 같은 칸막이로 나눈 조각도 본다.
# 조각도 해시로만 견주므로 맞는 말이 아니면 아무것도 안 나간다.
SPLIT = re.compile(r"\s+[-–—|·:]\s+")
MAX_PARTS = 6


def _fp(title):
    """제목의 지문 - 같은 제목인지 알아보는 데만 쓴다 (글자는 남기지 않는다)."""
    return hashlib.sha256(title.encode("utf-8", "replace")).hexdigest()


def candidates(title):
    """견줄 말들: 꼬리 뗀 제목 전체 → ' - ' 로 나눈 조각들 (앞에서부터, 겹치면 한 번)."""
    from common import arche as CA
    core = CA.title_core(title or "")
    out = []
    for c in [core] + SPLIT.split(core)[:MAX_PARTS]:
        c = (c or "").strip()
        if c and c not in out:
            out.append(c)
    return out


class TitleWatch(object):
    """맨 앞 창 제목 감시.

    get_hashes() - 지금 맞춰 볼 열쇠 해시 (컨트롤러가 state 에서 꺼낸다). 두 꼴을 받는다:
                     (소금, [hex, ...])                     -> on_hit(말)
                     [(장 번호, 소금, [hex, ...]), ...]      -> on_hit(장 번호, 말)   (열린 장마다 소금이 다르다)
                   비었거나 None 이면 제목을 읽지 않는다.
    on_hit       - 맞은 말 (꼬리 뗀 제목 또는 그 조각). 같은 제목이 이어지면 한 번만.
    read         - 제목 읽기 (검사가 가짜를 넘긴다). 기본 PLAT.foreground_title.
    enabled      - 설정 스위치 ('브라우저 단서 찾기'). 기본 늘 켬.
    """

    def __init__(self, root, get_hashes, on_hit, every_ms=EVERY_MS, read=None, enabled=None):
        self.root = root
        self.get_hashes = get_hashes
        self.on_hit = on_hit
        self.every = max(250, int(every_ms))
        self.read = read or PLAT.foreground_title
        self.enabled = enabled or (lambda: True)
        self.job = None
        self.live = False          # start 뒤 stop 전 (on_hit 안에서 stop 하면 다시 예약하지 않는다)
        self._last = None          # 지난 제목의 지문 (_fp)

    # ---------------- 켜고 끄기 ----------------
    def start(self):
        self.live = True
        if self.job is None:
            self._schedule()

    def stop(self):
        self.live = False
        job, self.job = self.job, None
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:                               # noqa: BLE001
                pass
        self._last = None

    def running(self):
        return self.job is not None

    def _schedule(self):
        try:
            self.job = self.root.after(self.every, self._run)
        except Exception:                                   # noqa: BLE001  (root 가 이미 닫혔다)
            self.job = None

    def _run(self):
        self.job = None
        try:
            self.tick()
        finally:
            if self.live and self.job is None:
                self._schedule()

    # ---------------- 한 번 보기 ----------------
    def _groups(self):
        """[(장 번호 또는 None, 소금, {hex})] - 해시가 있는 것만."""
        try:
            got = self.get_hashes()
        except Exception as e:                              # noqa: BLE001
            config.log("아르케 제목 감시: 열쇠 해시를 못 받았습니다: %s" % e)
            return []
        if not got:
            return []
        if isinstance(got, tuple) and len(got) == 2 and isinstance(got[0], str):
            got = [(None, got[0], got[1])]
        out = []
        try:
            for tag, salt, hashes in got:
                hs = set(h for h in (hashes or ()) if h)
                if hs and salt is not None:
                    out.append((tag, salt, hs))
        except Exception as e:                              # noqa: BLE001
            config.log("아르케 제목 감시: 열쇠 해시 꼴이 이상합니다: %s" % e)
            return []
        return out

    def tick(self):
        """한 번 본다. 맞으면 on_hit. 무엇이 터져도 조용히 넘어간다 (다음 틱이 또 본다)."""
        try:
            if not self.enabled():
                self._last = None
                return
        except Exception:                                   # noqa: BLE001
            return
        groups = self._groups()
        if not groups:
            self._last = None
            return
        try:
            title = self.read()
        except Exception:                                   # noqa: BLE001
            return
        if not title or not isinstance(title, str):
            self._last = None
            return
        fp = _fp(title)
        if fp == self._last:
            return                                          # 같은 제목 - 이미 셈했다
        self._last = fp
        hit = self._match(groups, title)
        title = None                                        # 제목 글자는 여기서 버린다
        if hit is None:
            return
        tag, text = hit
        try:
            if tag is None:
                self.on_hit(text)
            else:
                self.on_hit(tag, text)
        except Exception as e:                              # noqa: BLE001
            config.log("아르케 제목 감시: 알림 처리 실패: %s" % e)

    def _match(self, groups, title):
        """맞은 (장 번호, 말) 또는 None."""
        try:
            from common import arche as CA
            for c in candidates(title):
                for tag, salt, hashes in groups:
                    if CA.key_hash(salt, c) in hashes:
                        return tag, c
        except Exception as e:                              # noqa: BLE001
            config.log("아르케 제목 감시: 견주기 실패: %s" % e)
        return None
