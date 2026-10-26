# -*- coding: utf-8 -*-
"""test_skin_dp.py 의 친구 칸에 쓰는 가짜 서버 · 앱 (친구 넷 · 받은 신청 · 보낸 신청 · 차단)."""


FRIENDS = [
    {"id": 2, "name": "지우", "online": True, "title": "시즌 1 챔피언", "frameColor": "#ffc043", "tier": "master",
     "tierKr": "마스터볼", "ranked": True, "rp": 1320, "wins": 12, "losses": 3, "visitable": True},
    {"id": 3, "name": "웅이", "online": False, "lastSeenAgo": 3600 * 5, "tier": "super", "tierKr": "슈퍼볼",
     "ranked": True, "rp": 410, "wins": 4, "losses": 6},
    {"id": 4, "name": "이슬", "online": True, "lastSeenAgo": 0, "ranked": False, "wins": 0, "losses": 0,
     "visitBusy": True},
    {"id": 5, "name": "알망드", "online": False, "lastSeenAgo": 86400 * 3, "ranked": True, "rating": 1210, "wins": 2,
     "losses": 1},
]


class Api(object):
    def __init__(self):
        self.calls = []

    def friends(self):
        return {"friends": FRIENDS, "incoming": [{"id": 9, "name": "로켓단"}],
                "outgoing": [{"id": 10, "name": "난천"}], "blocked": [{"id": 11, "name": "스팸"}],
                "limits": {"maxFriends": 30}}

    def friend_search(self, name):
        return {"found": True, "id": 20, "name": name, "online": True, "ranked": True, "rating": 1300,
                "relation": "none"}

    def friend_request(self, name):
        self.calls.append(("request", name))
        return {"message": "신청했습니다."}

    def friend_accept(self, uid):
        self.calls.append(("accept", uid))
        return {}

    def friend_remove(self, uid):
        self.calls.append(("remove", uid))
        return {}

    def friend_block(self, uid):
        self.calls.append(("block", uid))
        return {}

    def friend_unblock(self, uid):
        self.calls.append(("unblock", uid))
        return {}


class Visit(object):
    active = False
    guest = False

    def partner_id(self):
        return None


class App(object):
    def __init__(self, root):
        self.root = root
        self.api = Api()
        self.live_pending = {"id": 7, "foeId": 3}
        self.visit = Visit()
        self.challenged = []

    def check_live(self):
        pass

    def pvp_challenge(self, uid):
        self.challenged.append(uid)

    def live_invite(self, uid, name):
        self.challenged.append(("live", uid))

    def live_cancel(self, then):
        self.live_pending = None
        then()
