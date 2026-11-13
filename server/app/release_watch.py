# -*- coding: utf-8 -*-
"""새 앱 판이 나오면 붙어 있는 앱 모두에 바로 알린다 (놀러 가기 소켓).

앱은 켤 때와, 켜 둔 동안 한 시간마다 깃허브에 새 판이 있는지 묻는다 (app.UPDATE_EVERY_HOURS). 그래서
새 판을 내도 한 시간 가까이 옛 판이 돈다 - 서버는 이미 새 판에 맞춰 바뀐 채로. 여기서 깃허브의 최신
릴리스를 config.RELEASE_WATCH_SEC 마다 보고, 판이 바뀌면 {"t": "update", "v": 판} 을 모두에게 민다.
그때 끊겨 있던 앱은 다시 붙을 때 hello 의 latest 로 안다 (visit._hello). 받은 앱은 늘 하던 확인
(updater.check)을 그 자리에서 한다 - 자기보다 새 판일 때만, 그리고 저마다 조금씩 늦춰서.

**판 번호만 보낸다.** 받을 파일은 앱이 깃허브에서 직접 찾는다 (updater.ALLOW_PREFIX - 서버가 알려 주는
주소는 따라가지 않는다). 그래서 이 알림이 틀려도 앱이 엉뚱한 것을 받는 일은 없다 - 확인을 한 번 더 할 뿐이다.

**초안은 안 본다.** releases/latest 는 초안·미리보기 릴리스를 빼고 준다. 동시 배포(초안 릴리스 → 서버 배포
→ 공개)에서는 공개하는 순간부터 알린다.

깃허브 API 는 로그인 없이 IP 하나에 시간당 60번이다. **로그인 없이 물으면 304(안 바뀌었다)도 그 수에 든다**
(11/14 운영 서버에서 재 봄: ETag 를 실은 두 번째 요청이 304 인데 남은 횟수가 59 -> 58). 그래서 1분마다 물으면
한도를 다 쓴다 - 2분(시간당 30번)으로 두고 MIN_SEC 보다 줄이지 않는다. ETag 는 그래도 싣는다 (안 바뀌면 본문이 안 온다).

운영 서버에서만 켠다 (config.RELEASE_WATCH, deploy/docker-compose.prod.yml) - 검사 서버가 깃허브를 두드리지 않게.
"""
import json
import re
import threading
import time
import urllib.error
import urllib.request

from . import config

API = "https://api.github.com/repos/%s/releases/latest"
TIMEOUT = 15
MIN_SEC = 90
_VER = re.compile(r"^\d+(\.\d+){1,3}$")

_lock = threading.Lock()
_state = {"latest": None, "etag": None}
_started = [False]


def latest():
    """지금 아는 최신 앱 판 ('2.5.1'). 아직 못 읽었으면 None."""
    with _lock:
        return _state["latest"]


def reset():
    """검사용."""
    with _lock:
        _state.update(latest=None, etag=None)


def tag_of(data):
    """릴리스 자료 -> '2.5.1'. 판 번호 꼴이 아니면 None (이상한 글자를 앱에 밀지 않는다)."""
    tag = str((data or {}).get("tag_name") or "").strip().lstrip("vV")
    return tag if _VER.match(tag) else None


def note(ver):
    """새로 읽은 판을 적는다. 아는 것과 다르면 True (= 알려야 한다). 서버가 뜬 뒤 처음 읽은 것도 True -
    그 사이에 붙은 앱은 hello 에 latest 가 없었다. 자기 판과 같은 앱은 받아도 그냥 넘긴다."""
    if not ver:
        return False
    with _lock:
        if ver == _state["latest"]:
            return False
        _state["latest"] = ver
        return True


def fetch(opener=None):
    """깃허브에 한 번 묻는다. 새로 받은 판, 안 바뀌었거나(304) 실패하면 None."""
    opener = opener or urllib.request.urlopen
    req = urllib.request.Request(API % config.RELEASE_REPO, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "poketdesktop-server",
    })
    with _lock:
        etag = _state["etag"]
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with opener(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
            tag = r.headers.get("ETag")
    except urllib.error.HTTPError as e:
        if e.code != 304:
            print("[release] 깃허브 확인 실패: HTTP %s" % e.code)
        return None
    except Exception as e:                                  # noqa: BLE001
        print("[release] 깃허브 확인 실패: %r" % (e,))
        return None
    ver = tag_of(data)
    if ver and tag:
        with _lock:
            _state["etag"] = tag
    return ver


def check_once(opener=None):
    """한 번 보고, 판이 바뀌었으면 모두에게 민다. 민 판 (안 밀었으면 None)."""
    ver = fetch(opener)
    if not note(ver):
        return None
    try:
        from . import visit
        n = visit.push_all({"t": "update", "v": ver})
    except Exception as e:                                  # noqa: BLE001
        print("[release] 알림 실패: %r" % (e,))
        return ver
    print("[release] 최신 앱 판 %s - 붙어 있는 %d명에게 알렸습니다" % (ver, n))
    return ver


def _run():
    while True:
        try:
            check_once()
        except Exception as e:                              # noqa: BLE001
            print("[release] %r" % (e,))
        time.sleep(max(MIN_SEC, config.RELEASE_WATCH_SEC))


def start():
    """뒤에서 돌기 시작한다. 두 번 불러도 하나만 돈다."""
    with _lock:
        if _started[0]:
            return False
        _started[0] = True
    threading.Thread(target=_run, name="release-watch", daemon=True).start()
    return True
