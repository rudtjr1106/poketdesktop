# -*- coding: utf-8 -*-
"""서버와 주고받는 부분. 실패하면 ApiError 로 통일해서 던진다."""
import json
import os

import requests

from . import config

TIMEOUT = 15
# 무료 호스팅(Render 등)은 한동안 요청이 없으면 서버를 재운다.
# 다시 깨어나는 데 1분쯤 걸려서, 15초로는 로그인이 무조건 실패한다.
# 처음 붙는 요청만 넉넉히 기다린다.
WAKE_TIMEOUT = 90


class ApiError(Exception):
    def __init__(self, message, status=0):
        Exception.__init__(self, message)
        self.message = message
        self.status = status


def _hour():
    """지금 몇 시인지. 낮/밤을 봐야 하는 것들(다크볼, 이브이 진화)에 쓴다."""
    import datetime
    return datetime.datetime.now().hour


class Api(object):
    def __init__(self, base, token=None):
        self.base = (base or "").rstrip("/")
        self.token = token
        self.session = requests.Session()

    # ---------------- 내부 ----------------
    def _call(self, method, path, body=None, auth=True, timeout=TIMEOUT):
        url = self.base + path
        headers = {"Accept": "application/json"}
        if auth and self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            r = self.session.request(method, url, json=body, headers=headers,
                                     timeout=timeout)
        except requests.exceptions.ConnectionError:
            raise ApiError("서버에 연결할 수 없습니다.\n%s" % self.base)
        except requests.exceptions.Timeout:
            raise ApiError("서버 응답이 없습니다. 잠시 후 다시 시도해 주세요.")
        except requests.RequestException as e:
            raise ApiError("통신 오류: %s" % e)

        if r.status_code == 204 or not r.content:
            return {}
        try:
            data = r.json()
        except ValueError:
            raise ApiError("서버 응답을 이해할 수 없습니다. (%d)" % r.status_code)
        if r.status_code >= 400:
            raise ApiError(data.get("error") or "요청이 거부되었습니다. (%d)"
                           % r.status_code, r.status_code)
        return data

    # ---------------- 공개 ----------------
    def health(self, wake=False):
        """서버가 살아 있는지. wake=True 면 자고 있는 서버를 깨울 때까지 기다린다."""
        return self._call("GET", "/api/health", auth=False,
                          timeout=WAKE_TIMEOUT if wake else TIMEOUT)

    def wake(self, on_progress=None):
        """자고 있을지 모르는 서버를 깨운다.

        무료 호스팅은 15분쯤 놀면 서버를 재우고, 다시 깨는 데 1분쯤 걸린다.
        그동안 오는 요청은 그냥 실패하므로, 로그인 전에 한 번 두드려 둔다.
        """
        import time
        deadline = time.time() + WAKE_TIMEOUT
        last = None
        tries = 0
        while time.time() < deadline:
            tries += 1
            try:
                return self._call("GET", "/api/health", auth=False, timeout=20)
            except ApiError as e:
                last = e
                if on_progress:
                    on_progress(tries)
                time.sleep(2)
        raise last or ApiError("서버가 응답하지 않습니다.")

    def pokedex_meta(self):
        # 앱이 켜지고 가장 먼저 부르는 것 중 하나다. 서버가 자고 있으면
        # 여기서 깨어난다.
        return self._call("GET", "/api/pokedex/meta", auth=False,
                          timeout=WAKE_TIMEOUT)

    def pokedex(self):
        """1MB 가 넘어서 requests 가 알아서 gzip 을 풀어준다."""
        return self._call("GET", "/api/pokedex", auth=False, timeout=60)

    def check_name(self, name):
        """닉네임을 쓸 수 있는지 물어본다 (회원가입 화면에서 타이핑 중)."""
        import urllib.parse
        return self._call("GET", "/api/auth/check?name=" +
                          urllib.parse.quote(name), auth=False, timeout=8)

    def starters(self):
        return self._call("GET", "/api/starters", auth=False,
                          timeout=WAKE_TIMEOUT)

    def sprite(self, num, shiny=False):
        """정식 도트 원본 바이트. (내용, 확장자) 를 돌려준다."""
        url = "%s/api/sprite/%d%s" % (self.base, int(num), "?shiny=true" if shiny else "")
        try:
            r = self.session.get(url, timeout=40)
        except requests.RequestException as e:
            raise ApiError("도트를 받지 못했습니다: %s" % e)
        if r.status_code != 200:
            return None, None
        ext = r.headers.get("X-Sprite-Ext")
        if not ext:
            ext = ".png" if "png" in (r.headers.get("Content-Type") or "") else ".gif"
        return r.content, ext

    # ---------------- 계정 ----------------
    def register(self, username, password, starter=""):
        d = self._call("POST", "/api/auth/register", auth=False,
                       timeout=WAKE_TIMEOUT, body={
            "username": username, "password": password,
            "device": config.device_id(), "starter": starter})
        self.token = d["token"]
        return d

    def login(self, username, password):
        d = self._call("POST", "/api/auth/login", auth=False,
                       timeout=WAKE_TIMEOUT, body={
            "username": username, "password": password,
            "device": config.device_id()})
        self.token = d["token"]
        return d

    def auto_login(self, token):
        d = self._call("POST", "/api/auth/auto", auth=False,
                       timeout=WAKE_TIMEOUT, body={
            "token": token, "device": config.device_id()})
        self.token = d["token"]
        return d

    def logout(self):
        try:
            return self._call("POST", "/api/auth/logout")
        finally:
            self.token = None

    def delete_account(self, password):
        d = self._call("DELETE", "/api/auth/account", body={"password": password})
        self.token = None
        return d

    def me(self):
        return self._call("GET", "/api/me")

    # ---------------- 포켓몬 ----------------
    def pokemon(self):
        return self._call("GET", "/api/pokemon")["pokemon"]

    def desktop(self):
        return self._call("GET", "/api/pokemon/desktop")["pokemon"]

    def spawn(self, force=False):
        q = "?force=true" if force else ""
        return self._call("POST", "/api/pokemon/spawn" + q)["pokemon"]

    def set_desktop(self, pid, on):
        return self._call("POST", "/api/pokemon/%d/desktop" % pid, {"on": bool(on)})

    def set_nickname(self, pid, nickname):
        return self._call("PATCH", "/api/pokemon/%d" % pid, {"nickname": nickname})

    def release(self, pid):
        return self._call("DELETE", "/api/pokemon/%d" % pid)

    def add_exp(self, pid, amount):
        return self._call("POST", "/api/pokemon/%d/exp" % pid, {"amount": int(amount)})

    # ---------------- 야생 조우 ----------------
    def wild(self, force=False):
        return self._call("GET", "/api/wild" + ("?force=true" if force else ""))

    def wild_reveal(self, wid):
        return self._call("POST", "/api/wild/%d/reveal" % wid, {})

    def wild_catch(self, wid, ball="POKEBALL"):
        # 시각을 같이 보낸다. 다크볼처럼 밤인지 봐야 하는 볼이 있고,
        # 서버는 도커 안이라 UTC 라서 사용자의 밤을 알 수 없다.
        return self._call("POST", "/api/wild/%d/catch" % wid,
                          {"ball": ball, "hour": _hour()})

    def wild_flee(self, wid):
        return self._call("POST", "/api/wild/%d/flee" % wid, {})

    # ---------------- 배틀 ----------------
    def battle_start(self, wid):
        return self._call("POST", "/api/wild/%d/battle" % wid, {})

    def battle_current(self):
        return self._call("GET", "/api/battle")

    def battle_move(self, bid, move):
        return self._call("POST", "/api/battle/%d/move" % bid,
                          {"move": move, "hour": _hour()})

    def battle_switch(self, bid, pid):
        return self._call("POST", "/api/battle/%d/switch" % bid, {"pokemon": pid})

    def battle_ball(self, bid, ball="POKEBALL"):
        return self._call("POST", "/api/battle/%d/ball" % bid,
                          {"ball": ball, "hour": _hour()})

    def battle_run(self, bid):
        return self._call("POST", "/api/battle/%d/run" % bid, {})

    def item_sprite(self, item_id):
        """도구 그림 원본 바이트. 없으면 None."""
        url = "%s/api/item-sprite/%s" % (self.base, item_id)
        try:
            r = self.session.get(url, timeout=20)
        except requests.RequestException:
            return None
        return r.content if r.status_code == 200 and r.content else None

    def walk_meta(self, num):
        """걷는 도트가 있는지, 있으면 어떻게 잘라야 하는지."""
        return self._call("GET", "/api/walk/%d.json" % int(num), auth=False,
                          timeout=30)

    def walk_sheet(self, num):
        """걷기 스프라이트시트 원본 바이트. 없으면 None."""
        url = "%s/api/walk/%d.png" % (self.base, int(num))
        try:
            r = self.session.get(url, timeout=40)
        except requests.RequestException:
            return None
        return r.content if r.status_code == 200 and r.content else None

    # ---------------- 친구 ----------------
    # 전부 창을 열었을 때만 부른다. 폴링을 붙이지 않는다 - Turso 는
    # 왕복 하나가 곧 비용이라, 항상 도는 폴링은 하나로 몰기로 했다.
    def friends(self):
        return self._call("GET", "/api/friends")

    def friend_search(self, name):
        import urllib.parse
        return self._call("GET", "/api/friends/search?name="
                          + urllib.parse.quote(name or ""))

    def friend_request(self, username):
        return self._call("POST", "/api/friends/request",
                          {"username": username})

    def friend_accept(self, uid):
        return self._call("POST", "/api/friends/%d/accept" % uid, {})

    def friend_remove(self, uid):
        """거절 · 취소 · 삭제가 전부 이 하나다."""
        return self._call("DELETE", "/api/friends/%d" % uid)

    def friend_block(self, uid):
        return self._call("POST", "/api/friends/%d/block" % uid, {})

    def friend_unblock(self, uid):
        return self._call("DELETE", "/api/friends/%d/block" % uid)

    def profile(self, uid):
        return self._call("GET", "/api/users/%d/profile" % uid)

    # ---------------- 유저 배틀 ----------------
    def pvp_records(self, limit=30):
        return self._call("GET", "/api/pvp/records?limit=%d" % limit)

    def pvp_ranking(self, limit=50):
        return self._call("GET", "/api/pvp/ranking?limit=%d" % limit)

    def pvp_match(self, mid):
        return self._call("GET", "/api/pvp/match/%d" % mid)

    def pvp_seen(self, mid):
        return self._call("POST", "/api/pvp/match/%d/seen" % mid, {})

    def pvp_random(self):
        """아무나 골라 붙는다. 상대는 접속해 있지 않아도 된다."""
        return self._call("POST", "/api/pvp/random", {})

    def pvp_challenge(self, uid):
        """친구를 지목해서 붙는다. 수락을 기다리지 않는다."""
        return self._call("POST", "/api/pvp/challenge/%d" % uid, {})

    def pvp_pending(self):
        return self._call("GET", "/api/pvp/pending")

    # ---------------- 가방 · 상점 ----------------
    def bag(self):
        return self._call("GET", "/api/bag")

    def shop(self):
        return self._call("GET", "/api/shop")

    def buy(self, item, count=1):
        return self._call("POST", "/api/shop/buy", {"item": item, "count": count})

    def sell(self, item, count=1):
        return self._call("POST", "/api/shop/sell", {"item": item, "count": count})

    def use_item(self, item, pokemon=0, stat=""):
        return self._call("POST", "/api/bag/use",
                          {"item": item, "pokemon": pokemon, "stat": stat,
                           "hour": _hour()})


# ---------------------------------------------------------------- 도감 캐시
def load_pokedex(api):
    """서버 도감을 받아 캐시한다. 이미 같은 버전이면 캐시를 쓴다."""
    cached = None
    if os.path.exists(config.POKEDEX_CACHE):
        try:
            with open(config.POKEDEX_CACHE, encoding="utf-8") as f:
                cached = json.load(f)
        except (OSError, ValueError):
            cached = None
    try:
        meta = api.pokedex_meta()
    except ApiError:
        if cached:
            return cached, "캐시"
        raise
    if cached and cached.get("_digest") == meta.get("digest"):
        return cached, "캐시"
    data = api.pokedex()
    data["_digest"] = meta.get("digest")
    tmp = config.POKEDEX_CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, config.POKEDEX_CACHE)
    return data, "내려받음"
