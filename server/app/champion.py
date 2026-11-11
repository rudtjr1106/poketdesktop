# -*- coding: utf-8 -*-
"""챔피언리그 — 독도 (2026-11-11 사용자 기획).

    GET  /api/champion                     지금 모습 (자격 · 여는 때 · 내 전적 · 기다리는 사람 · 접속 중인 참가자 ·
                                           진행 중인 판 · 순위 · 최근 판)
    POST /api/champion/seek                [상대 찾기] 를 켜고 끈다 {on}
    POST /api/champion/challenge/{uid}     접속 중인 참가자에게 직접 도전한다 (상대가 받아야 시작한다)
    GET  /api/champion/fight/{mid}         구경용 판 모습 (참가자만)
    POST /api/champion/watch               구경을 시작한다 / 아직 본다 / 그만 본다 {id, on} -> {id, n}

## 누가 나가나

관장 256곳을 **전부** 이긴 사람. 처음 다 이긴 순간 champion_member 에 한 줄 적고, 그 뒤로는 그대로 둔다 -
관장을 바꾸면 migrations 가 그 지역의 이긴 기록을 지우므로 '지금 256곳' 으로만 보면 시즌 중에 자격이 사라진다.
팀은 랭크전 조건 그대로다 (Lv.50 이상 6마리 · 같은 도구 한 마리).

## 판

실시간 배틀(live.py) 그대로다 - 둘이 동시에 고르고, 30초가 지나면 자동, Lv.50, 랭크 팀(없으면 바탕화면 파티).
live_match.kind 가 'champion' 인 것만 다르다. 배틀 창도 같은 창이다 (제목만 '챔피언리그 · 독도').

## 기록 - 점수도 보상도 없다 (사용자 결정)

끝난 판에서 몇전 몇승 몇패를 세고 **이긴 횟수**로 순위를 매긴다 (같으면 진 횟수가 적은 쪽, 그다음 먼저 자격을
얻은 쪽). 무승부는 '무' 로 세고, 아무도 안 돌아와 접힌 판 · 거절 · 취소는 안 센다.

같은 두 사람의 판은 **하루(한국 시각)에 PAIR_DAY_MAX 판까지만** 전적에 든다 - 둘이 짜고 기권을 주고받으며
이긴 횟수를 쌓는 것을 막는다. 따로 적어 두지 않고 셀 때마다 끝난 판을 번호 순으로 훑는다 (판 수가 적다 -
참가자가 열몇 명이다).

## 상대 찾기 (대기열)

[상대 찾기] 를 켜면 먼저 기다리던 사람과 **그 자리에서** 판이 열린다. 아무도 없으면 기다린다 (WAIT_SEC).
참가자가 적어서 그냥 두면 서로 엇갈린다 - **1분(NOTIFY_SEC) 기다려도 상대가 없으면** 접속 중인 다른 참가자에게
알린다 (11/11 사용자 - 곧 붙을 판까지 알려 귀찮게 하지 않게). 놀러 가기 소켓 /ws/visit 으로 민다 - 앱이 켜져 있는
동안 늘 붙어 있다. 같은 사람의 알림은 NOTIFY_GAP 에 한 번. 서버에는 따로 도는 시계가 없어서 기다리기 시작할 때
타이머를 하나 걸고(_schedule), 창이 물어올 때(state)도 때가 된 것을 본다 (_due).
기다리는 사람에게 [도전] 하면 묻지 않고 바로 시작한다 (그 사람은 아무나 기다리고 있었다).

대기열은 **메모리에** 둔다 (서버는 프로세스 하나다 - guild_ws 와 같은 전제). 서버가 다시 뜨면 비워진다.

## 관전 - 길드전처럼, 참가자끼리 (11/11 사용자)

판이 열리면 접속 중인 다른 참가자에게 '○○ vs △△ 시작' 을 민다 (fight). 구경은 바탕화면에서 한다 (친선전 ·
길드전 공격 구경과 같은 장면). 구경하는 화면은 보기 시작할 때 · 20초마다 · 그만둘 때 알리고 (watchers.py, 판의
이름은 'c' + 판 번호), 서버는 판이 넘어갈 때마다 **지금 보는 사람에게** 새 모습을 민다 (turn - 같은 장면은 두 번
안 민다). 구경꾼 수가 바뀌면 싸우는 두 사람에게 민다 (watchers) - 배틀 창이 '관전 N명' 을 적는다 (live.public
에도 실린다). **구경은 참가자만** 한다 (관장을 다 이기지 못한 사람은 판 목록만 본다).

## 알림 (서버 -> 앱, /ws/visit)

    {"t": "champion", "s": "wait",  "id": 기다리는 사람, "name": 닉네임}   독도에서 상대를 기다린다
    {"t": "champion", "s": "ask",   "id": 판, "name": 건 사람}             나에게 도전이 왔다 (앱은 /api/live 를 물어 수락을 묻는다)
    {"t": "champion", "s": "match", "id": 판}                              판이 열렸다 (앱은 /api/live 를 물어 배틀 창을 띄운다)
    {"t": "champion", "s": "fight", "id": 판, "a": 이름, "b": 이름}        다른 참가자들의 판이 열렸다 -> [관전]
    {"t": "champion", "s": "turn", "fight": {...}}                          보고 있는 판의 새 모습 (live.spectate + watchers)
    {"t": "champion", "s": "watchers", "id": 판, "n": 수}                   내 판을 보는 사람 수가 바뀌었다
"""
import datetime
import threading
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import config, db, deps, gym, live, pvp, social, visit, watchers

router = APIRouter()

KST = datetime.timezone(datetime.timedelta(hours=9))
KIND = "champion"
PAIR_DAY_MAX = 3            # 같은 두 사람의 판이 전적에 드는 것은 하루에 이만큼까지
NOTIFY_GAP = 180            # 같은 사람이 '기다린다' 는 알림은 이만큼에 한 번 (껐다 켰다 하며 도배하지 않게)
RANK_SHOW = 50              # 순위표에 싣는 줄
RECENT_SHOW = 10            # 내 최근 판
FIGHTS_SHOW = 10            # 진행 중인 판
SYNC_SEC = 300              # 관장 기록에서 참가자를 채우는 간격 (members)

_lock = threading.Lock()
_wait = {}                  # {uid: 기다리기 시작한 때 (time.monotonic)}
_told = {}                  # {uid: 마지막으로 '기다린다' 를 알린 때}
_announced = set()          # 이미 알린 기다림 (uid, 기다리기 시작한 때)
_started = set()            # '판이 열렸다' 를 이미 알린 판 번호
_synced = [0.0]             # 마지막으로 참가자를 채운 때 (time.monotonic)
_scene = {}                 # {판: 마지막으로 구경꾼에게 민 장면 (turn, step, 끝났나)}


def reset():
    """검사용: 메모리에 든 것을 비운다."""
    with _lock:
        _wait.clear()
        _told.clear()
        _announced.clear()
        _started.clear()
        _scene.clear()
        _synced[0] = 0.0


def _now(now=None):
    return now or datetime.datetime.now(datetime.timezone.utc)


def _iso(now=None):
    return _now(now).replace(microsecond=0).isoformat()


def _name(uid):
    r = db.q1("SELECT username FROM users WHERE id=?", (uid,))
    return r["username"] if r else "?"


def _push(uid, payload):
    try:
        visit.push(uid, payload)
    except Exception:                                       # noqa: BLE001
        pass                                 # 알림이 못 갔다고 판이 깨지면 안 된다 (앱은 창을 열면 다시 묻는다)


# ---------------------------------------------------------------- 여는 때
def start_at():
    t = datetime.datetime.fromisoformat(config.CHAMPION_START)
    return t if t.tzinfo else t.replace(tzinfo=KST)


def is_open(now=None):
    return _now(now) >= start_at()


def open_text():
    """'11월 16일 0시' (분이 있으면 '0시 30분')."""
    t = start_at().astimezone(KST)
    s = "%d월 %d일 %d시" % (t.month, t.day, t.hour)
    return s + (" %d분" % t.minute if t.minute else "")


# ---------------------------------------------------------------- 자격
def total():
    """관장 수 (지금 지도의 시·군·구)."""
    return len(gym.gyms()["regions"])


def cleared(uid):
    """지금 있는 관장 가운데 이긴 곳의 수."""
    regions = gym.gyms()["regions"]
    return sum(1 for r in db.q("SELECT region FROM gym_clear WHERE user_id=?", (uid,)) if r["region"] in regions)


def member_row(uid):
    return db.q1("SELECT * FROM champion_member WHERE user_id=?", (uid,))


def qualify(uid, now=None):
    """참가자인가. 아직 아니지만 지금 관장을 전부 이겼으면 그 자리에서 참가자로 적는다."""
    if member_row(uid):
        return True
    if cleared(uid) < total():
        return False
    db.run("INSERT OR IGNORE INTO champion_member (user_id, qualified_at) VALUES (?,?)", (uid, _iso(now)))
    return True


def sync_members(now=None, force=False):
    """관장을 전부 이긴 사람을 참가자로 적는다 - 아직 관장 탭 · 독도 창을 안 연 사람도 ('기다린다' 알림과 순위에
    나오게). 처음 이긴 순간은 gym.record_win 이 적지만, 리그가 생기기 전에 이미 다 이긴 사람은 그 순간이 지났다.
    SYNC_SEC 에 한 번만 센다 (창이 몇 초마다 묻는다)."""
    t = time.monotonic()
    if not force and _synced[0] and t - _synced[0] < SYNC_SEC:
        return
    _synced[0] = t
    regions = list(gym.gyms()["regions"])
    marks = ",".join("?" * len(regions))
    for r in db.q("SELECT c.user_id FROM gym_clear c LEFT JOIN champion_member m ON m.user_id = c.user_id"
                  " WHERE m.user_id IS NULL AND c.region IN (%s) GROUP BY c.user_id"
                  " HAVING COUNT(DISTINCT c.region) >= ?" % marks, tuple(regions) + (len(regions),)):
        db.run("INSERT OR IGNORE INTO champion_member (user_id, qualified_at) VALUES (?,?)", (r["user_id"], _iso(now)))


def members():
    """참가자 [(uid, 닉네임, 자격 얻은 때)] - 자격 얻은 순."""
    sync_members()
    return [(r["user_id"], r["username"], r["qualified_at"]) for r in db.q(
        "SELECT m.user_id, m.qualified_at, u.username FROM champion_member m JOIN users u ON u.id = m.user_id"
        " ORDER BY m.qualified_at, m.user_id")]


def team_why(uid, mine=True):
    """팀이 챔피언리그 조건을 못 채웠으면 그 까닭 (채웠으면 None). mine=False 면 상대 이야기로."""
    team = pvp.ranked_team(uid)
    ok, n = pvp.rank_ready(team)
    if not ok:
        if not mine:
            return "상대의 팀이 챔피언리그 조건(Lv.%d 이상 %d마리)을 못 채웠습니다." % (
                pvp.season.RANK_MIN_LEVEL, pvp.season.RANK_MIN_COUNT)
        return "챔피언리그는 Lv.%d 이상 포켓몬 %d마리로 팀을 채워야 나갈 수 있습니다 (지금 %d마리)." % (
            pvp.season.RANK_MIN_LEVEL, pvp.season.RANK_MIN_COUNT, n)
    if mine:
        return pvp.held_why(team, "랭크 팀" if pvp.team_ids(uid) else "바탕화면 파티")
    return None


def why_not(uid, now=None):
    """지금 기다리기 · 도전을 못 하는 까닭 (할 수 있으면 None)."""
    if not is_open(now):
        return "챔피언리그는 %s에 열립니다." % open_text()
    if not qualify(uid, now):
        return "관장 %d곳을 전부 이겨야 챔피언리그에 나갈 수 있습니다 (지금 %d곳)." % (total(), cleared(uid))
    if live.my_match(uid):
        return "이미 진행 중인 실시간 배틀이 있습니다."
    return team_why(uid)


# ---------------------------------------------------------------- 상대 찾기
def _sweep(t):
    for u, since in list(_wait.items()):
        if t - since > config.CHAMPION_WAIT_SEC:
            _wait.pop(u, None)
    for key in [k for k in _announced if _wait.get(k[0]) != k[1]]:
        _announced.discard(key)              # 붙었거나 그만둔 기다림


def _pick(uid, now=None):
    """기다리는 사람 가운데 나와 붙을 사람 (먼저 기다린 순). _lock 안에서 부른다. 사라진 사람은 걷는다."""
    for since, other in sorted((s, u) for u, s in _wait.items() if u != uid):
        if not social.is_online(other) or live.my_match(other) or why_not(other, now):
            _wait.pop(other, None)           # 껐거나 다른 판에 들어갔거나 팀을 바꿨다 - 더 기다리게 두지 않는다
            continue
        if social.blocked_between(uid, other):
            continue
        return other
    return None


def seek(uid, on, now=None):
    """[상대 찾기] 를 켠다 / 끈다. 켰는데 기다리던 사람이 있으면 그 자리에서 판을 열어 그 행을 돌려준다.
    아무도 없으면 기다리기 시작하고 None. 못 하면 ValueError(까닭)."""
    if not on:
        with _lock:
            _wait.pop(uid, None)
        return None
    why = why_not(uid, now)
    if why:
        raise ValueError(why)
    t = time.monotonic()
    for _ in range(5):
        with _lock:
            _sweep(t)
            other = _pick(uid, now)
            if other is None:
                fresh = uid not in _wait
                _wait[uid] = t               # 다시 누르면 기다리는 시간이 처음부터
                break
            _wait.pop(other, None)
            _wait.pop(uid, None)
        try:
            return live.open_direct(other, uid, now, kind=KIND)      # 먼저 기다린 사람이 a
        except ValueError:
            continue                         # 사이에 그 사람이 다른 판에 들어갔다 - 다음 사람
    else:
        return None
    if fresh:
        _schedule(config.CHAMPION_NOTIFY_SEC)    # 1분 뒤에도 기다리고 있으면 알린다 (_due)
    return None


def _schedule(delay):
    """delay 초 뒤에 _due 를 한 번 부른다 (검사는 이것을 바꿔 끼운다 - 진짜 시계로 기다리지 않게)."""
    tm = threading.Timer(max(0.5, float(delay) + 0.5), _due)
    tm.daemon = True
    tm.start()


def _due(t=None, now=None):
    """NOTIFY_SEC 넘게 기다리고 있는데 아직 안 알린 사람을 알린다. 알린 사람 수."""
    t = time.monotonic() if t is None else t
    with _lock:
        _sweep(t)
        ripe = [(u, s) for u, s in _wait.items()
                if t - s >= config.CHAMPION_NOTIFY_SEC and (u, s) not in _announced]
        _announced.update(ripe)
    n = 0
    for uid, _s in ripe:
        try:
            n += bool(_announce(uid, t, now))
        except Exception as e:                              # noqa: BLE001
            print("[champion] 기다림 알림 실패 %s: %r" % (uid, e))
    return n


def _announce(uid, t, now=None):
    """접속 중인 다른 참가자에게 '○○ 님이 독도에서 기다립니다' 를 민다. 알렸으면 True."""
    with _lock:
        last = _told.get(uid)
        if last is not None and t - last < NOTIFY_GAP:
            return False
        _told[uid] = t
        busy = set(_wait)
    name = _name(uid)
    for other, _n, _q in members():
        if other == uid or other in busy or not social.is_online(other) or live.my_match(other):
            continue
        if social.blocked_between(uid, other):
            continue
        _push(other, {"t": "champion", "s": "wait", "id": uid, "name": name})
    return True


def wait_left(uid):
    with _lock:
        since = _wait.get(uid)
    if since is None:
        return 0
    return max(0, int(config.CHAMPION_WAIT_SEC - (time.monotonic() - since)))


def challenge(uid, other, now=None):
    """접속 중인 참가자에게 도전한다. 그 사람이 기다리고 있었으면 바로 시작(행이 fighting), 아니면 초대(invited)."""
    why = why_not(uid, now)
    if why:
        raise ValueError(why)
    if uid == other:
        raise ValueError("자기 자신에게는 도전할 수 없습니다.")
    if not db.q1("SELECT 1 x FROM users WHERE id=?", (other,)):
        raise LookupError("그런 트레이너가 없습니다.")
    if not qualify(other, now):
        raise ValueError("상대가 아직 챔피언리그 참가자가 아닙니다.")
    if social.blocked_between(uid, other):
        raise ValueError("이 트레이너와는 싸울 수 없습니다.")
    if not social.is_online(other):
        raise ValueError("상대가 지금 접속해 있지 않습니다. 실시간 배틀은 둘 다 켜 있어야 합니다.")
    if live.my_match(other):
        raise ValueError("상대가 다른 배틀을 하고 있습니다.")
    why = team_why(other, mine=False)
    if why:
        raise ValueError(why)
    with _lock:
        waiting = _wait.pop(other, None) is not None
        _wait.pop(uid, None)                 # 직접 도전했으면 기다리기는 그만
    if waiting:
        return live.open_direct(other, uid, now, kind=KIND)
    row = live.invite_kind(uid, other, KIND, now)
    _push(other, {"t": "champion", "s": "ask", "id": row["id"], "name": _name(uid)})
    return row


def watch_key(mid):
    """구경꾼을 세는 이름 (watchers.py). 친선전(실시간 배틀 번호 그대로)과 겹치지 않게 'c' 를 붙인다."""
    return "c%s" % mid


def _on_live(row):
    """실시간 배틀의 판이 바뀌었다 (live.listeners). 챔피언리그 판이면

      * 막 열렸을 때: 두 사람에게 'match' (기다리던 사람은 창을 닫아 두었을 수 있고, 도전한 사람은 상대가 받았는지
        모른다) + 접속 중인 다른 참가자에게 'fight' (관전하라고).
      * 넘어갈 때마다: 지금 보는 사람에게 새 모습 'turn'. 끝나면 마지막 모습을 주고 구경꾼을 버린다.
    """
    if not row or live.kind_of(row) != KIND or row["state"] not in ("fighting", "done"):
        return
    mid = row["id"]
    if row["state"] == "fighting":
        with _lock:
            fresh = mid not in _started
            if fresh:
                if len(_started) > 500:
                    _started.clear()
                _started.add(mid)
        if fresh:
            players = (row["a_id"], row["b_id"])
            for uid in players:
                _push(uid, {"t": "champion", "s": "match", "id": mid})
            msg = {"t": "champion", "s": "fight", "id": mid, "a": row["a_name"], "b": row["b_name"]}
            for other, _n, _q in members():
                if other not in players and social.is_online(other):
                    _push(other, msg)
    _feed(row)


def _feed(row):
    """보고 있는 사람에게 판의 새 모습을 민다. 같은 장면은 두 번 안 민다."""
    mid = row["id"]
    key = watch_key(mid)
    eyes = watchers.who(key)
    over = row["state"] == "done"
    if eyes:
        f = live.spectate(row)
        if f is not None:
            mark = (f.get("turn"), f.get("step"), bool(f.get("over")))
            with _lock:
                same = _scene.get(mid) == mark
                _scene[mid] = mark
            if not same:
                f["kind"] = KIND
                f["watchers"] = len(eyes)
                for uid in eyes:
                    _push(uid, {"t": "champion", "s": "turn", "fight": f})
    if over:
        watchers.drop(key)
        with _lock:
            _scene.pop(mid, None)


def watch(uid, mid, on=True, now=None):
    """그 사람이 그 판을 보기 시작했다 / 아직 본다 / 그만 봤다. 구경꾼 수가 바뀌면 싸우는 두 사람에게 민다.
    {id, n}. 참가자가 아니면 PermissionError, 그런 판이 없으면 LookupError, 자기 판이면 ValueError."""
    if not qualify(uid):
        raise PermissionError("챔피언리그 참가자만 관전할 수 있습니다 (관장 %d곳을 전부 이기면)." % total())
    row = live.get(mid)
    if not row or live.kind_of(row) != KIND:
        raise LookupError("그런 챔피언리그 판이 없습니다.")
    if uid in (row["a_id"], row["b_id"]):
        raise ValueError("내 배틀은 관전하지 않습니다.")
    key = watch_key(mid)
    if row["state"] != "fighting":
        if on:
            raise LookupError("그 판은 이미 끝났습니다.")
        return {"id": mid, "n": 0}
    before = watchers.count(key, now)
    n = watchers.ping(key, uid, on, now)
    if n != before:
        for p in (row["a_id"], row["b_id"]):
            _push(p, {"t": "champion", "s": "watchers", "id": mid, "n": n})
    return {"id": mid, "n": n}


def _decorate(row, out):
    """실시간 배틀 응답(live.public)에 '관전 N명' 을 얹는다 - 챔피언리그 판일 때만 (배틀 창이 적는다)."""
    if live.kind_of(row) == KIND and row["state"] == "fighting":
        out["watchers"] = watchers.count(watch_key(row["id"]))


live.listeners.append(_on_live)
live.decorators.append(_decorate)


# ---------------------------------------------------------------- 기록
def _kst_day(iso):
    try:
        t = datetime.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return t.astimezone(KST).date().isoformat()


def finished():
    """끝난 챔피언리그 판 [(행, 전적에 드나)] - 번호 순. 같은 두 사람의 판은 하루 PAIR_DAY_MAX 판까지만 든다."""
    rows = db.q("SELECT id, a_id, b_id, a_name, b_name, result, reason, turn, created_at, updated_at"
                " FROM live_match WHERE kind=? AND state='done' AND result IN ('a','b','draw') ORDER BY id",
                (KIND,))
    seen = {}
    out = []
    for r in rows:
        key = (min(r["a_id"], r["b_id"]), max(r["a_id"], r["b_id"]), _kst_day(r["created_at"]))
        n = seen.get(key, 0)
        seen[key] = n + 1
        out.append((r, n < PAIR_DAY_MAX))
    return out


def _blank():
    return {"played": 0, "wins": 0, "losses": 0, "draws": 0}


def stats(done=None):
    """{uid: {played, wins, losses, draws}} - 전적에 드는 판만."""
    out = {}
    for r, counted in (finished() if done is None else done):
        if not counted:
            continue
        for side, uid in (("a", r["a_id"]), ("b", r["b_id"])):
            s = out.setdefault(uid, _blank())
            s["played"] += 1
            if r["result"] == "draw":
                s["draws"] += 1
            elif r["result"] == side:
                s["wins"] += 1
            else:
                s["losses"] += 1
    return out


def ranking(done=None):
    """참가자 전원의 순위 (0전도 나온다). 이긴 횟수 -> 진 횟수가 적은 쪽 -> 먼저 자격을 얻은 쪽.
    이긴 횟수와 진 횟수가 같으면 같은 등수다."""
    st = stats(done)
    rows = []
    for uid, name, since in members():
        s = dict(st.get(uid) or _blank())
        s.update({"id": uid, "name": name, "since": since})
        rows.append(s)
    rows.sort(key=lambda s: (-s["wins"], s["losses"], s["since"] or "", s["id"]))
    rank, prev = 0, None
    for i, s in enumerate(rows):
        key = (s["wins"], s["losses"])
        if key != prev:
            rank, prev = i + 1, key
        s["rank"] = rank
        s.pop("since", None)
    return rows


def recent(uid, done=None):
    """내 최근 판 (새 것부터). counted=False 는 같은 상대와 하루 PAIR_DAY_MAX 판을 넘겨 전적에 안 든 판."""
    out = []
    for r, counted in reversed(finished() if done is None else done):
        if uid not in (r["a_id"], r["b_id"]):
            continue
        me = "a" if r["a_id"] == uid else "b"
        foe = "b" if me == "a" else "a"
        res = r["result"]
        out.append({"id": r["id"], "foeId": r["%s_id" % foe], "foeName": r["%s_name" % foe],
                    "outcome": "draw" if res == "draw" else ("win" if res == me else "lose"),
                    "reason": r["reason"], "turns": r["turn"], "at": r["updated_at"], "counted": counted})
        if len(out) >= RECENT_SHOW:
            break
    return out


def fights():
    """진행 중인 챔피언리그 판 (새 것부터)."""
    return [{"id": r["id"], "turn": r["turn"], "a": {"id": r["a_id"], "name": r["a_name"]},
             "b": {"id": r["b_id"], "name": r["b_name"]}, "watchers": watchers.count(watch_key(r["id"]))}
            for r in db.q("SELECT id, a_id, b_id, a_name, b_name, turn FROM live_match"
                          " WHERE kind=? AND state='fighting' ORDER BY id DESC LIMIT ?", (KIND, FIGHTS_SHOW))]


# ---------------------------------------------------------------- 보여주기
def brief(uid, now=None):
    """관장 지도(/api/gym)에 얹는 짧은 것 - 독도를 금빛으로 칠할지."""
    return {"member": qualify(uid, now), "open": is_open(now), "opens": open_text()}


def state(uid, now=None):
    live.expire_old(now)
    member = qualify(uid, now)
    _due(now=now)                            # (타이머가 못 돌았어도 창이 물어올 때 때가 된 알림을 보낸다)
    t = time.monotonic()
    with _lock:
        _sweep(t)
        waiting = [u for u, _s in sorted(_wait.items(), key=lambda kv: kv[1])]
    done = finished()
    table = ranking(done)
    me = next((dict(r) for r in table if r["id"] == uid), None)
    names = {r["id"]: r["name"] for r in table}
    online = []
    for r in table:
        other = r["id"]
        if other == uid or not social.is_online(other) or social.blocked_between(uid, other):
            continue
        online.append({"id": other, "name": r["name"], "waiting": other in waiting,
                       "busy": live.my_match(other) is not None})
    return {
        "open": is_open(now), "startsAt": config.CHAMPION_START, "opens": open_text(),
        "total": total(), "cleared": cleared(uid), "member": member, "members": len(table),
        "why": why_not(uid, now),
        "seeking": uid in waiting, "waitLeft": wait_left(uid), "waitSec": config.CHAMPION_WAIT_SEC,
        "notifySec": config.CHAMPION_NOTIFY_SEC,
        "waiting": [{"id": u, "name": names.get(u) or _name(u)} for u in waiting if u != uid],
        "online": online, "fights": fights(), "ranking": table[:RANK_SHOW],
        "me": me, "recent": recent(uid, done) if member else [], "pairMax": PAIR_DAY_MAX,
    }


def fight(mid, uid=None):
    """구경용 판 모습. 챔피언리그 판이 아니면 None. uid 를 주면 참가자인지 본다 (아니면 PermissionError)."""
    if uid is not None and not qualify(uid):
        raise PermissionError("챔피언리그 참가자만 관전할 수 있습니다 (관장 %d곳을 전부 이기면)." % total())
    row = live.get(mid)
    if not row or live.kind_of(row) != KIND:
        return None
    if row["state"] == "fighting":
        row = live.tick(row) or row          # 두 사람이 다 사라졌어도 구경꾼의 물음이 턴을 넘긴다
    out = live.spectate(row)
    if out is not None:
        out["kind"] = KIND
        out["watchers"] = watchers.count(watch_key(mid))
    return out


# ---------------------------------------------------------------- 라우트
class SeekIn(BaseModel):
    on: bool = True


class WatchIn(BaseModel):
    id: int
    on: bool = True


@router.get("/api/champion")
def get_state(ctx=Depends(deps.current)):
    return state(ctx["user"]["id"])


@router.post("/api/champion/seek")
def post_seek(body: SeekIn, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    try:
        row = seek(uid, bool(body.on))
    except ValueError as e:
        raise HTTPException(409, str(e))
    out = state(uid)
    out["match"] = live.public(row, uid) if row else None
    return out


@router.post("/api/champion/challenge/{other}")
def post_challenge(other: int, ctx=Depends(deps.current)):
    uid = ctx["user"]["id"]
    try:
        row = challenge(uid, other)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"match": live.public(row, uid)}


@router.get("/api/champion/fight/{mid}")
def get_fight(mid: int, ctx=Depends(deps.current)):
    try:
        out = fight(mid, ctx["user"]["id"])
    except PermissionError as e:
        raise HTTPException(403, str(e))
    if out is None:
        raise HTTPException(404, "그런 챔피언리그 판이 없습니다.")
    return out


@router.post("/api/champion/watch")
def post_watch(body: WatchIn, ctx=Depends(deps.current)):
    try:
        return watch(ctx["user"]["id"], int(body.id), bool(body.on))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
