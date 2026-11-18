# -*- coding: utf-8 -*-
"""액션 배틀 (2.6.0) 의 판 굴리기 - /ws/action.

    WS /ws/action      첫 메시지 {"t": "auth", "ticket": "..."} (AUTH_SEC 안에)

**입장권은 첫 메시지로만 받는다** - 주소 쿼리나 머리말에 실으면 Caddy · uvicorn 로그에 남는다 (action.py 의 설명).

    화면 -> 서버   {"t": "pick", "slots": [0, 2, 5]}         고르기 (6마리 중 3)
                  {"t": "in", "s": 12, "x": 0.7, "y": -0.7}  이동 (−1~1). s = 내 입력 번호 - 스냅숏의 ack 로 돌아온다
                  {"t": "act", "s": 13, "k": "m0"}           누름 (KEYS)
                  {"t": "ff"}                                기권
                  {"t": "png", "c": 7}                       시계 맞추기 -> {"t": "pong", "c": 7, "ts": 판 시각}
                  "ping"                                     -> "pong"
    서버 -> 화면   엔진의 intro ({"t": "hello", ...})          들어오자마자 (다시 들어와도)
                  {"t": "wait"}                              상대가 아직 안 들어왔다 (1초마다)
                  엔진의 snapshot + {"ev": [이벤트]}          판이 돌면 틱마다 (30번/초). hit.dmg 는 맞은 사람에게만
                  {"t": "over", "winner", "reason"}          끝났다 (OVER_LINGER 초 뒤에 닫는다). 기록 없이 접힌
                                                             판은 winner 가 null, reason 이 noshow / error /
                                                             cancel (상대를 기다리다 기권했다)

## 끊는 번호

    4401    입장권이 틀렸다 · 늦었다 · 이미 썼다 (다시 붙어 봐야 소용없다 - 앱에서 새로 받는다)
    4409    이미 끝난 판 · 다른 창에서 다시 들어왔다
    4429    방이 다 찼다 (config.ACTION_ROOMS)

## 한 판 = 방 하나 = asyncio 작업 하나

첫 사람이 들어올 때 방을 만들고 작업을 띄운다. 둘 다 들어올 때까지 기다리고 (받은 때로부터 ACTION_JOIN_SEC - 못
오면 기록 없이 접는다 · 먼저 온 사람이 기다리다 기권하면 바로 기록 없이 cancel 로 접는다), 다 오면 판을
fighting 으로 적고 고정 스텝(엔진 TICK)으로 굴린다. loop.time() 으로 밀린 만큼
따라잡되 한 번에 CATCHUP 스텝까지 - 그보다 밀리면 버린다 (판이 잠깐 느려질 뿐 몰아서 빨라지지 않는다). 판이
끝나면 over 를 보내고 전적을 적고 (action.finish) 닫고 방을 지운다. **판은 판이 있을 때만 돈다.**

입력은 받는 즉시 엔진에 넣는다 (같은 이벤트 루프라 잠글 것이 없다). 한 사람에게서 1초에 IN_PER_SEC 개, 그중
누름은 ACT_PER_SEC 개까지만 받고 나머지는 버린다 (매크로 막기 - 쿨타임 · PP · 상태는 엔진이 본다). 보내는 것은
한 사람씩 SEND_SEC 안에 - 못 보내면 끊긴 것으로 본다 (느린 한 사람이 판을 붙잡지 않게).

끊기면 그 자리에 선다 (이동 0). ACTION_GRACE 초 안에 새 입장권으로 다시 들어오면 이어 하고, 못 오면 기권이다.

**DB 는 이벤트 루프에서 부르지 않는다** (run_in_threadpool). 방 작업이 터지면 그 판만 기록 없이 접고(error) 서버는
그대로 돈다. 서버를 다시 켜면 방은 없어지고 줄은 aborted 가 된다 (main 의 시작 - action.abort_all).

서버는 **프로세스 하나**로 돈다 (server/Dockerfile 의 uvicorn 한 줄). 방을 이 모듈의 사전에 들고 있다 - 워커를
여럿으로 늘리면 두 사람이 다른 워커에 붙어 한 방에서 못 만난다 (guild_ws 와 같은 까닭).
"""
import asyncio
import datetime
import json
import math
import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from . import action, config, deps

router = APIRouter()

AUTH_SEC = 5.0               # 붙은 뒤 입장권을 보내기까지
CATCHUP = 5                  # 밀렸을 때 한 번에 따라잡는 스텝
IN_PER_SEC = 90              # 한 사람에게서 1초에 받는 메시지
ACT_PER_SEC = 20             # 그 가운데 누름 (act)
WAIT_EVERY = 1.0             # 상대를 기다리는 동안 wait 를 보내는 간격
OVER_LINGER = 3.0            # over 를 보내고 닫기까지
SEND_SEC = 2.0               # 한 번 보내기가 이보다 오래 걸리면 끊긴 것으로 본다
MSG_MAX = 512                # 화면이 보내는 한 줄의 글자 수 (입장권 줄도 - 읽기 전에 길이부터 본다)
ERR_EVERY = 10.0             # 입력이 엔진에서 터졌을 때 로그를 남기는 간격 (방마다) - 화면이 로그를 채우지 못하게
NUM_MAX = 2 ** 53            # 받는 정수의 크기 (float 로 바꿔도 정확한 데까지 - 더 크면 버린다)
KEYS = ("m0", "m1", "m2", "m3", "dodge", "sw0", "sw1", "sw2")
SIDES = ("a", "b")
WAIT = json.dumps({"t": "wait"})

_rooms = {}                  # {판 번호: Room}


def _engine():
    """판 엔진 (common/action_battle.py). 처음 방을 열 때 읽는다 - 엔진이 깨져도 서버의 다른 일은 돈다."""
    from common import action_battle
    return action_battle


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


class Seat(object):
    """방의 한 자리에 붙은 연결."""
    __slots__ = ("ws", "lock", "win", "n", "acts")

    def __init__(self, ws):
        self.ws, self.lock = ws, asyncio.Lock()
        self.win, self.n, self.acts = 0.0, 0, 0

    def allow(self, now, act):
        """1초 창 안에서 더 받을 수 있나 (IN_PER_SEC, 누름은 ACT_PER_SEC)."""
        if now - self.win >= 1.0:
            self.win, self.n, self.acts = now, 0, 0
        self.n += 1
        self.acts += 1 if act else 0
        return self.n <= IN_PER_SEC and (not act or self.acts <= ACT_PER_SEC)

    async def send(self, text):
        """보낸다 (방 작업과 소켓 작업이 같이 보내도 한 줄씩). 못 보냈으면 False."""
        try:
            async with self.lock:
                await asyncio.wait_for(self.ws.send_text(text), SEND_SEC)
            return True
        except Exception:                                   # noqa: BLE001 - 끊겼다 · 너무 느리다
            return False


class Room(object):
    """한 판. 엔진과 두 자리, 끊긴 때, 고른 것."""

    def __init__(self, mid, battle, deadline):
        self.mid, self.battle, self.deadline = mid, battle, deadline
        self.seats = {"a": None, "b": None}
        self.gone = {"a": None, "b": None}         # 끊긴 때 (loop.time) - 싸우는 동안 ACTION_GRACE 를 센다
        self.seq = {"a": 0, "b": 0}                # 받은 입력 번호 가운데 가장 큰 것
        self.picks = {}                            # {쪽: 고른 칸} - 전적의 선봉
        self.wake = asyncio.Event()                # 누가 들어왔다 · 기다리는 동안 기권했다
        self.ended = False
        self.err_at = None                         # 입력이 터진 로그를 마지막으로 남긴 때 (ERR_EVERY)
        teams = battle.intro("a")["teams"]
        self.kr = dict((s, [m.get("kr") or "" for m in teams[s]]) for s in SIDES)
        self.task = None                           # 방의 작업 (쥐고 있어야 도중에 거둬지지 않는다)

    def full(self):
        return all(self.seats[s] is not None for s in SIDES)

    def attach(self, side, seat):
        """그 자리에 앉힌다. 앞에 앉아 있던 연결(다른 창)을 돌려준다."""
        old, self.seats[side] = self.seats[side], seat
        self.gone[side] = None
        self.wake.set()
        return old

    def detach(self, side, seat):
        """그 연결이 나갔다 (다른 창으로 바뀐 뒤면 아무것도 안 한다). 그 자리에 서서 기다린다."""
        if self.seats[side] is not seat:
            return
        self.seats[side] = None
        self.gone[side] = asyncio.get_running_loop().time()
        self.battle.set_move(side, 0.0, 0.0, self.seq[side])

    def lead(self, side):
        """선봉 이름 (처음 고른 것, 안 골랐으면 맨 앞)."""
        names = self.kr[side]
        i = (self.picks.get(side) or [0])[0]
        return names[i] if 0 <= i < len(names) else ""


# ---------------------------------------------------------------- 받은 것
def _finite(v):
    """JSON 이 준 수인가 (참 · 거짓 · NaN · 무한 · NUM_MAX 보다 큰 정수는 아니다). 무엇을 받아도 예외 없이 답한다
    - JSON 은 400자리 정수도 읽고, 그런 정수는 math.isfinite 가 OverflowError 를 던진다."""
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return -NUM_MAX <= v <= NUM_MAX
    return isinstance(v, float) and math.isfinite(v)


def _num(v):
    """이동 값 하나 (−1~1). 숫자가 아니면 None."""
    return max(-1.0, min(1.0, float(v))) if _finite(v) else None


def _seq(v):
    """입력 번호 · 칸 번호 (0 이상 정수). 아니면 None."""
    return v if _finite(v) and isinstance(v, int) and 0 <= v < 2 ** 31 else None


def _echo(c):
    """시계 맞추기에 실려 온 값 (그대로 돌려준다) - 숫자나 짧은 글자만."""
    if isinstance(c, str):
        return c if len(c) <= 32 else None
    return c if _finite(c) else None


def _apply(room, side, msg):
    """메시지 하나를 엔진에 넣는다. 돌려보낼 것이 있으면 그 글."""
    b, t = room.battle, msg.get("t")
    if t == "in":
        x, y, s = _num(msg.get("x")), _num(msg.get("y")), _seq(msg.get("s"))
        if None not in (x, y, s):
            room.seq[side] = max(room.seq[side], s)
            b.set_move(side, x, y, s)
    elif t == "act":
        s = _seq(msg.get("s"))
        if msg.get("k") in KEYS and s is not None:
            room.seq[side] = max(room.seq[side], s)
            b.press(side, msg["k"], s)
    elif t == "pick":
        slots = msg.get("slots")
        if isinstance(slots, list) and len(slots) <= action.TEAM_MAX \
                and all(_seq(x) is not None for x in slots) and b.pick(side, list(slots)):
            room.picks[side] = list(slots)
    elif t == "ff":
        if b.phase != "over":
            b.forfeit(side)
            room.wake.set()                                 # 상대를 기다리는 중이면 기다림을 끝낸다 (_gather)
    elif t == "png":
        c = _echo(msg.get("c"))
        if c is not None:
            return _dump({"t": "pong", "c": c, "ts": b.t})
    return None


def _on_text(room, side, seat, text, now):
    """화면이 보낸 한 줄. 돌려보낼 것이 있으면 그 글. 너무 잦은 것 · 모르는 것은 버린다."""
    if text == "ping":
        return "pong" if seat.allow(now, False) else None
    if len(text) > MSG_MAX or room.ended:
        return None
    try:
        msg = json.loads(text)
    except ValueError:
        return None
    if not isinstance(msg, dict) or not seat.allow(now, msg.get("t") == "act"):
        return None
    try:
        return _apply(room, side, msg)
    except Exception:                                       # noqa: BLE001
        # 그 입력만 버린다 (사람을 내쫓지 않는다). 엔진이 정말 깨졌으면 다음 step 에서 방이 접는다.
        # 로그는 방마다 ERR_EVERY 에 한 번만 - 같은 입력을 1초에 IN_PER_SEC 번 보내도 로그가 넘치지 않게.
        if room.err_at is None or now - room.err_at >= ERR_EVERY:
            room.err_at = now
            print("[action] 판 %d 의 입력을 넣지 못했습니다 %r\n%s" % (room.mid, msg, traceback.format_exc()))
        return None


# ---------------------------------------------------------------- 보내기
def _for(e, side):
    """그 사람에게 보낼 이벤트. hit.dmg 는 맞은 사람에게만 (상대의 정확한 체력을 숨긴다)."""
    if e.get("e") == "hit" and "dmg" in e and e.get("v") != side:
        e = dict(e)
        e.pop("dmg")
    return e


async def _send(room, side, text):
    seat = room.seats[side]
    if seat is not None and not await seat.send(text):
        room.detach(side, seat)
        await _close(seat.ws, 1011)


async def _send_all(room, text):
    await asyncio.gather(*[_send(room, s, text) for s in SIDES])


async def _tick_out(room):
    """쌓인 이벤트를 꺼내 두 사람에게 각자의 모습(snapshot) + ev 를 보낸다."""
    b = room.battle
    ev = b.drain_events()
    out = []
    for side in SIDES:
        if room.seats[side] is not None:
            snap = b.snapshot(side)
            snap["ev"] = [_for(e, side) for e in ev]
            out.append(_send(room, side, _dump(snap)))
    await asyncio.gather(*out)


async def _close(ws, code):
    try:
        await ws.close(code=code)
    except Exception:                                       # noqa: BLE001
        pass                                                # 이미 끊겼다


async def _close_all(room, code):
    for side in SIDES:
        seat, room.seats[side] = room.seats[side], None
        if seat is not None:
            await _close(seat.ws, code)


# ---------------------------------------------------------------- 방의 일생
async def _gather(room):
    """둘 다 들어올 때까지 기다린다 (방의 deadline 까지). 먼저 온 사람에게는 1초마다 wait.
    다 왔으면 True, 못 왔으면 False, 기다리는 동안 기권했으면 None (판을 열지 않고 기록 없이 접는다)."""
    loop = asyncio.get_running_loop()
    while True:
        room.wake.clear()
        if room.battle.phase == "over":
            return None
        if room.full():
            return True
        left = room.deadline - loop.time()
        if left <= 0:
            return False
        await _send_all(room, WAIT)
        try:
            await asyncio.wait_for(room.wake.wait(), min(WAIT_EVERY, left))
        except asyncio.TimeoutError:
            pass


def _forfeit_gone(room, now):
    """ACTION_GRACE 넘게 끊겨 있는 쪽은 기권 (먼저 끊긴 쪽부터)."""
    gone = sorted((t, s) for s, t in room.gone.items() if t is not None)
    for t, side in gone:
        if now - t >= config.ACTION_GRACE and room.battle.phase != "over":
            room.battle.forfeit(side)


async def _fight(room):
    """판을 고정 스텝으로 끝까지 굴린다. 스텝을 밟은 틱마다 두 사람에게 보낸다."""
    tick = _engine().TICK
    b = room.battle
    loop = asyncio.get_running_loop()
    last, acc = loop.time(), 0.0
    while b.phase != "over":
        await asyncio.sleep(max(0.0, tick - acc))
        now = loop.time()
        acc += now - last
        last = now
        _forfeit_gone(room, now)
        n = 0
        while acc >= tick and n < CATCHUP and b.phase != "over":
            b.step()
            acc -= tick
            n += 1
        if acc >= tick:
            acc = 0.0                                       # CATCHUP 보다 밀렸다 - 따라잡지 않고 버린다
        if n:
            await _tick_out(room)


async def _finish(room):
    """끝났다: 마지막 모습, over, 전적 (action.finish). OVER_LINGER 뒤에 닫는다."""
    room.ended = True
    b = room.battle
    await _tick_out(room)
    res = b.result
    await _send_all(room, _dump({"t": "over", "winner": res["winner"], "reason": res["reason"]}))
    left = dict((s, b.left(s)) for s in SIDES)
    lead = dict((s, room.lead(s)) for s in SIDES)
    try:
        await run_in_threadpool(action.finish, room.mid, res["winner"], res["reason"], left, lead, b.fight_secs())
    except Exception as e:                                  # noqa: BLE001
        print("[action] 판 %d 의 결과를 적지 못했습니다: %r" % (room.mid, e))
    await asyncio.sleep(OVER_LINGER)
    await _close_all(room, 1000)


async def _fold(room, reason):
    """판을 기록 없이 접는다 (아무도 안 왔다 · 터졌다). 붙어 있는 사람에게 알리고 닫는다."""
    room.ended = True
    try:
        await run_in_threadpool(action.abort, room.mid, reason)
    except Exception as e:                                  # noqa: BLE001
        print("[action] 판 %d 을 접지 못했습니다: %r" % (room.mid, e))
    await _send_all(room, _dump({"t": "over", "winner": None, "reason": reason}))
    await _close_all(room, 1000)


async def _run(room):
    """방 하나의 일생: 기다림 -> 판 -> 끝. 무슨 일이 나도 방은 치우고 나간다 (서버는 그대로 돈다)."""
    try:
        came = await _gather(room)
        if came is None:
            await _fold(room, "cancel")                     # 상대를 기다리다 기권했다 - 싸우지 않았으니 기록 없이
        elif not came:
            await _fold(room, "noshow")
        elif not await run_in_threadpool(action.start_fight, room.mid):
            room.ended = True                               # 사이에 접혔다 (expire_old)
            await _close_all(room, 4409)
        else:
            await _fight(room)
            await _finish(room)
    except asyncio.CancelledError:
        raise                                               # 서버가 내려간다 - 줄은 다음 시작이 접는다
    except Exception:                                       # noqa: BLE001
        print("[action] 판 %d 이 멈췄습니다 - 기록 없이 접습니다\n%s" % (room.mid, traceback.format_exc()))
        await _fold(room, "error")
    finally:
        room.ended = True
        _rooms.pop(room.mid, None)


def _clocks():
    """검사 서버가 준 판 길이 (config.ACTION_*_SEC). 안 줬으면 엔진 값."""
    kw = {"pick_sec": config.ACTION_PICK_SEC, "ready_sec": config.ACTION_READY_SEC,
          "fight_sec": config.ACTION_FIGHT_SEC}
    return dict((k, v) for k, v in kw.items() if v is not None)


def _battle(row):
    """받은 판(open)의 엔진. 스레드풀에서 부른다 - 처음엔 엔진 · 기술 표를 읽느라 루프를 붙잡지 않게."""
    data = json.loads(row["data"])
    return _engine().ActionBattle(deps.dex(), data["a"], data["b"], data["seed"],
                                  names=(row["a_name"], row["b_name"]), **_clocks())


def _open(row, battle):
    """방을 두고 작업을 띄운다. 둘이 들어오기를 기다리는 시간은 받은 때(updated_at)로부터 센다."""
    age = (datetime.datetime.now(datetime.timezone.utc)
           - datetime.datetime.fromisoformat(row["updated_at"])).total_seconds()
    room = Room(row["id"], battle, asyncio.get_running_loop().time() + max(0.0, config.ACTION_JOIN_SEC - age))
    _rooms[row["id"]] = room
    room.task = asyncio.create_task(_run(room))


async def _room_for(mid):
    """그 판의 방 (없으면 연다) -> (방, None). 못 들어가면 (None, 끊는 번호)."""
    if mid not in _rooms:
        row = await run_in_threadpool(action.get, mid)
        if not row or row["state"] != "open":
            return None, 4409
        try:
            battle = await run_in_threadpool(_battle, row)
        except Exception:                                   # noqa: BLE001
            print("[action] 판 %d 을 열지 못했습니다 - 기록 없이 접습니다\n%s" % (mid, traceback.format_exc()))
            await run_in_threadpool(action.abort, mid, "error")
            return None, 4409
        if mid not in _rooms:                               # 기다리는 사이에 상대가 열었을 수 있다
            if len(_rooms) >= config.ACTION_ROOMS:
                return None, 4429
            _open(row, battle)
    room = _rooms.get(mid)
    if room is None or room.ended:                          # 기다리는 사이에 끝나서 치웠다
        return None, 4409
    return room, None


async def _auth(ws):
    """첫 메시지의 입장권 -> (판, 사람, 쪽). 틀렸거나 AUTH_SEC 안에 안 왔으면 None.

    **길이부터 본다** (MSG_MAX) - 입장권을 보기 전이라 아무나 보낼 수 있고, 압축해 보낸 큰 줄을 JSON 으로 읽으면
    이벤트 루프가 그동안 멈춘다 (모든 판이 같이 멈춘다)."""
    try:
        text = await asyncio.wait_for(ws.receive_text(), AUTH_SEC)
    except Exception:                                       # noqa: BLE001 - 늦었다 · 끊겼다 · 글자가 아니다
        return None
    if not isinstance(text, str) or len(text) > MSG_MAX:
        return None
    try:
        msg = json.loads(text)
    except Exception:                                       # noqa: BLE001 - JSON 이 아니다
        return None
    if not isinstance(msg, dict) or msg.get("t") != "auth":
        return None
    return action.redeem(msg.get("ticket"))


@router.websocket("/ws/action")
async def action_socket(ws: WebSocket):
    await ws.accept()               # 받아 준 뒤에 끊어야 끊는 번호가 화면까지 간다
    got = await _auth(ws)
    if got is None:
        return await _close(ws, 4401)
    mid, _uid, side = got
    room, code = await _room_for(mid)
    if room is None:
        return await _close(ws, code)
    seat = Seat(ws)
    old = room.attach(side, seat)
    if old is not None:
        await _close(old.ws, 4409)
    loop = asyncio.get_running_loop()
    try:
        await seat.send(_dump(room.battle.intro(side)))
        while True:
            reply = _on_text(room, side, seat, await ws.receive_text(), loop.time())
            if reply is not None:
                await seat.send(reply)
    except WebSocketDisconnect:
        pass
    except Exception:                                       # noqa: BLE001
        pass                                                # 끊긴 연결 · 글자가 아닌 것 - 나간 것으로 본다
    finally:
        room.detach(side, seat)
