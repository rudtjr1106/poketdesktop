# -*- coding: utf-8 -*-
"""서버와 주고받는 부분. 실패하면 ApiError 로 통일해서 던진다."""
import json
import os

import requests

from . import config

TIMEOUT = 15


class ApiError(Exception):
    def __init__(self, message, status=0):
        Exception.__init__(self, message)
        self.message = message
        self.status = status


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
    def health(self):
        return self._call("GET", "/api/health", auth=False)

    def pokedex_meta(self):
        return self._call("GET", "/api/pokedex/meta", auth=False)

    def pokedex(self):
        """1MB 가 넘어서 requests 가 알아서 gzip 을 풀어준다."""
        return self._call("GET", "/api/pokedex", auth=False, timeout=60)

    def starters(self):
        return self._call("GET", "/api/starters", auth=False)

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
        d = self._call("POST", "/api/auth/register", auth=False, body={
            "username": username, "password": password,
            "device": config.device_id(), "starter": starter})
        self.token = d["token"]
        return d

    def login(self, username, password):
        d = self._call("POST", "/api/auth/login", auth=False, body={
            "username": username, "password": password,
            "device": config.device_id()})
        self.token = d["token"]
        return d

    def auto_login(self, token):
        d = self._call("POST", "/api/auth/auto", auth=False, body={
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
        return self._call("POST", "/api/wild/%d/catch" % wid, {"ball": ball})

    def wild_flee(self, wid):
        return self._call("POST", "/api/wild/%d/flee" % wid, {})


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
