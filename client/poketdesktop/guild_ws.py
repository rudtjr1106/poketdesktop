# -*- coding: utf-8 -*-
"""길드 웹소켓 (1.10.0) — 서버가 밀어 주는 새 채팅과 길드 소식을 받는다.

서버의 /ws/guild 에 붙어서 받기만 한다 (말을 보내는 것은 POST /api/guild/chat).

    hello    붙었다              chat     새 줄
    changed  길드에 바뀐 것이 있다   left     이 길드에서 나왔다

여기서 두 가지를 더 만들어 넘긴다:

    {"t": "open"}     붙었다 (hello 를 받았다)
    {"t": "closed"}   끊겼다 - 화면은 2초 폴링으로 돌아간다

**받는 일은 따로 스레드에서 하고, 넘기는 일은 Tk 스레드에서 한다.** Tk 는 다른 스레드에서
건드리면 죽는다. 그래서 받은 것을 줄(queue)에 쌓고 Tk 의 after 로 꺼낸다.

**끊기면 스스로 다시 붙는다** (1 → 2 → 4 ... 최대 30초 간격). 서버를 새로 올릴 때마다
연결이 끊기는데, 그때마다 사용자가 창을 다시 열어야 하면 안 된다. 다만 서버가 "토큰이
틀렸다(4401)" · "길드가 없다(4404)" · "너무 많이 붙었다(4429)" 로 끊었으면 다시 붙어 봐야
소용없으므로 거기서 멈춘다.

**웹소켓이 안 되는 곳도 있다** (회사·학교 망이 막거나, 라이브러리가 없는 옛 빌드). 그때는
connected 가 계속 False 라 화면이 폴링으로 돈다 - 채팅이 안 되는 일은 없다.
"""
import json
import queue
import struct
import threading

try:
    import websocket                    # websocket-client
except Exception:                                           # noqa: BLE001
    websocket = None

DRAIN_MS = 120              # 받은 것을 Tk 로 넘기는 간격
PING_EVERY = 25             # 이 초 동안 아무것도 안 오면 ping 을 보낸다
RETRY = (1, 2, 4, 8, 15, 30)
GIVE_UP = (4401, 4404, 4429)


def available():
    return websocket is not None


def ws_url(base):
    """'https://host' -> 'wss://host/ws/guild'."""
    base = (base or "").rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[8:] + "/ws/guild"
    if base.startswith("http://"):
        return "ws://" + base[7:] + "/ws/guild"
    return base + "/ws/guild"


def _ssl_options():
    """인증서 묶음. 묶어 낸 exe 에는 시스템 인증서가 없을 수 있다 (requests 와 같은 것을 쓴다)."""
    try:
        import certifi
        return {"ca_certs": certifi.where()}
    except Exception:                                       # noqa: BLE001
        return {}


class GuildSocket(object):

    def __init__(self, root, base, token, on_event):
        self.root = root
        self.url = ws_url(base)
        self.token = token
        self.on_event = on_event
        self.connected = False
        self.gave_up = None           # 서버가 '다시 오지 마라' 로 끊은 번호
        self._q = queue.Queue()
        self._stop = threading.Event()
        self._ws = None
        self._thread = None
        self._job = None

    # ---------------- 켜고 끄기 ----------------
    def start(self):
        if self._thread is not None or not available():
            return self
        self._thread = threading.Thread(target=self._run, name="guild-ws", daemon=True)
        self._thread.start()
        self._drain()
        return self

    def stop(self):
        self._stop.set()
        self.connected = False
        ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except Exception:                               # noqa: BLE001
                pass
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:                               # noqa: BLE001
                pass
            self._job = None

    # ---------------- Tk 쪽 ----------------
    def _drain(self):
        if self._stop.is_set():
            return
        try:
            while True:
                ev = self._q.get_nowait()
                if ev.get("t") == "open":
                    self.connected = True
                elif ev.get("t") == "closed":
                    self.connected = False
                try:
                    self.on_event(ev)
                except Exception:                           # noqa: BLE001
                    pass
        except queue.Empty:
            pass
        try:
            self._job = self.root.after(DRAIN_MS, self._drain)
        except Exception:                                   # noqa: BLE001
            self._job = None

    # ---------------- 받는 스레드 ----------------
    def _run(self):
        tries = 0
        while not self._stop.is_set():
            opened = self._once()
            if self._stop.is_set() or self.gave_up:
                break
            tries = 0 if opened else tries + 1
            self._stop.wait(RETRY[min(tries, len(RETRY) - 1)])

    def _once(self):
        """한 번 붙어서 끊길 때까지 받는다. 붙기는 했으면 True."""
        opened = False
        ws = None
        try:
            ws = websocket.create_connection(
                self.url, timeout=10, header=["Authorization: Bearer %s" % self.token],
                sslopt=_ssl_options() if self.url.startswith("wss://") else None)
            self._ws = ws
            ws.settimeout(PING_EVERY)
            while not self._stop.is_set():
                try:
                    op, frame = ws.recv_data_frame(True)
                except websocket.WebSocketTimeoutException:
                    ws.send("ping")          # 조용하면 살아 있는지 두드려 본다
                    continue
                if op == websocket.ABNF.OPCODE_CLOSE:
                    code = struct.unpack("!H", frame.data[:2])[0] if len(frame.data) >= 2 else 1000
                    if code in GIVE_UP:
                        self.gave_up = code
                    break
                if op != websocket.ABNF.OPCODE_TEXT:
                    continue
                text = frame.data.decode("utf-8", "replace")
                if text == "pong":
                    continue
                try:
                    ev = json.loads(text)
                except ValueError:
                    continue
                if not isinstance(ev, dict):
                    continue
                if ev.get("t") == "hello":
                    opened = True
                    self._q.put({"t": "open", "userId": ev.get("userId"), "guild": ev.get("guild"),
                                 "last": ev.get("last")})
                else:
                    self._q.put(ev)
        except Exception:                                   # noqa: BLE001
            pass                             # 못 붙었거나 끊겼다 - 밖에서 다시 해 본다
        finally:
            self._ws = None
            if ws is not None:
                try:
                    ws.close()
                except Exception:                           # noqa: BLE001
                    pass
            if opened and not self._stop.is_set():
                self._q.put({"t": "closed"})
        return opened
