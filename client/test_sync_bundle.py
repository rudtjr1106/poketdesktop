# -*- coding: utf-8 -*-
"""2.5.4 동기화 묶음 (App._sync_fetch) - 화면 없이.

    python client/test_sync_bundle.py

  1. 새 서버: /api/sync 한 번으로 바탕화면 · me · 친구를 받는다 (따로 부르지 않는다).
  2. 옛 서버(404): 그 뒤로는 셋을 따로 부르고 다시 묶음을 묻지 않는다.
  3. 묶음이 다른 이유(500 · 끊김)로 실패: 이번만 따로, 다음에 다시 묶음을 묻는다.
  4. 401(세션 끊김)은 그대로 올린다 - 동기화가 세션 끊김으로 처리한다.
  5. 묶음의 me · 친구가 null 이면 None (예전에 따로 부를 때 실패한 것과 같다).
  6. api 에 sync_bundle 이 없으면(검사용 가짜 · 옛 api) 예전처럼 따로.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from poketdesktop.api import ApiError           # noqa: E402
from poketdesktop.app import App                # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Api(object):
    def __init__(self, bundle=None, error=None):
        self.calls = []
        self.bundle = bundle
        self.error = error

    def sync_bundle(self):
        self.calls.append("sync")
        if self.error is not None:
            raise self.error
        return self.bundle

    def desktop(self):
        self.calls.append("desktop")
        return [{"id": 9, "num": 25}]

    def me(self):
        self.calls.append("me")
        return {"balls": 3}

    def friends(self):
        self.calls.append("friends")
        return {"friends": []}


class OldApi(object):
    def __init__(self):
        self.calls = []

    def desktop(self):
        self.calls.append("desktop")
        return []

    def me(self):
        self.calls.append("me")
        return {}


def app_with(api):
    a = App.__new__(App)
    a.api = api
    a._bundle_ok = None
    return a


def main():
    print("=== 동기화 묶음 (2.5.4)")
    api = Api(bundle={"pokemon": [{"id": 1, "num": 1}], "me": {"balls": 5}, "friends": {"friends": [{"id": 2}]}})
    a = app_with(api)
    mons, me, friends, bundled = a._sync_fetch()
    chk("1. 새 서버: 요청 한 번 (sync) 으로 셋", api.calls == ["sync"] and bundled and mons == [{"id": 1, "num": 1}]
        and me == {"balls": 5} and friends == {"friends": [{"id": 2}]}, (api.calls, mons, me, friends))
    chk("   서버가 묶음을 안다고 기억", a._bundle_ok is True)

    api = Api(error=ApiError("Not Found", 404))
    a = app_with(api)
    mons, me, friends, bundled = a._sync_fetch()
    chk("2. 옛 서버(404): 따로 (desktop · me), 친구는 부르는 쪽이 따로", api.calls == ["sync", "desktop", "me"]
        and not bundled and friends is None and mons == [{"id": 9, "num": 25}], (api.calls, bundled))
    api.calls = []
    a._sync_fetch()
    chk("   다음 동기화에는 묶음을 다시 묻지 않는다", api.calls == ["desktop", "me"] and a._bundle_ok is False, api.calls)

    api = Api(error=ApiError("boom", 500))
    a = app_with(api)
    a._sync_fetch()
    chk("3. 500: 이번만 따로", api.calls == ["sync", "desktop", "me"] and a._bundle_ok is None, (api.calls, a._bundle_ok))
    api.error = None
    api.bundle = {"pokemon": [], "me": None, "friends": None}
    api.calls = []
    mons, me, friends, bundled = a._sync_fetch()
    chk("   다음에는 다시 묶음 · me/친구 null 은 None (5)", api.calls == ["sync"] and bundled and me is None
        and friends is None and mons == [], (api.calls, me, friends))

    api = Api(error=ApiError("세션", 401))
    a = app_with(api)
    try:
        a._sync_fetch()
        raised = False
    except ApiError as e:
        raised = e.status == 401
    chk("4. 401 은 그대로 올린다 (세션 끊김 처리)", raised and api.calls == ["sync"], api.calls)

    old = OldApi()
    a = app_with(old)
    mons, me, friends, bundled = a._sync_fetch()
    chk("6. sync_bundle 이 없는 api: 예전처럼 따로", old.calls == ["desktop", "me"] and not bundled, old.calls)

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
