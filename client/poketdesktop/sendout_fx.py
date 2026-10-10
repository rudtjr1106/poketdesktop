# -*- coding: utf-8 -*-
"""배틀 창에서 포켓몬이 **몬스터볼에서 나오고 들어가는** 연출 (1.10.4).

실시간 배틀 창에서는 포켓몬이 그냥 '뿅' 하고 바뀌었다. 길드 친선전을 바탕화면에서 구경할 때는
(duel_scene) 볼이 날아와 열리고 흰 빛이 커져 포켓몬이 되는데, 정작 싸우는 사람의 창에는 없었다.
같은 모양을 배틀 창의 캔버스에 그린다 (실시간 배틀과 관장 배틀이 같이 쓴다):

    내보낼 때    볼이 포물선으로 날아온다 -> 열리며 빛이 여섯 갈래로 터진다 -> 흰 윤곽이 커져서 포켓몬이 된다
    불러들일 때  흰 윤곽으로 줄어든다 -> 붉은 줄기가 되어 돌아간다

## 창이 갖춰야 하는 것 (stage)

    cv                   장면 캔버스
    sprite[who]          그쪽 포켓몬의 그림 항목 (anchor="s" - 발이 제자리에 닿는다)
    me_pos / foe_pos     발의 자리
    sw / sh              장면 크기
    later(ms, fn)        창이 닫히면 같이 사라지는 after
    alive
    sendout_hand(who)    (있으면) 볼이 날아오는 곳. None 을 주면 기본 자리(화면 밖)다.
                         관장 배틀은 상대의 볼이 **관장의 손에서** 나온다.

## 그림은 뒤에서 온다

포켓몬 그림은 작업 스레드가 불러온다 (set_mon). 볼이 먼저 떨어졌으면 열린 채로 기다렸다가 그림이
오는 대로 커지고, 그림이 먼저 왔으면 볼이 떨어지는 대로 커진다 (throw / arrive 어느 쪽이 먼저든 된다).

창 크기를 바꾸면 장면을 통째로 다시 그린다 (battle_zoom) - 그리던 항목이 사라지므로 연출은 거기서
그만두고(cancel), 창이 들고 있던 포켓몬을 그대로 세운다.
"""
import math
import time
import tkinter as tk

from PIL import Image, ImageTk

from . import effects, sprites

THROW_S = 0.46                # 볼이 날아가는 시간
OPEN_S = 0.16                 # 볼이 열려 빛이 터지는 시간
GROW_S = 0.34                 # 흰 윤곽이 포켓몬만큼 커지는 시간
RECALL_S = 0.26               # 흰 윤곽으로 줄어드는 시간
BEAM_S = 0.16                 # 붉은 줄기가 돌아가는 시간
SEND_S = THROW_S + OPEN_S + GROW_S
BACK_S = RECALL_S + BEAM_S
GROW = (0.2, 0.4, 0.6, 0.8, 1.0)   # 흰 윤곽이 커지는 단계 (바탕화면 구경 장면과 같다)
SPIN = 8                      # 날아가는 볼의 회전 그림 수
KEY = (255, 0, 255)
WHITE = "#ffffff"
BEAM = "#ff5a4f"


def arc(p0, p1, t, lift):
    """p0 에서 p1 로 포물선을 그리며 가는 점 (t = 0..1). lift 는 가운데에서 떠오르는 높이."""
    x = p0[0] + (p1[0] - p0[0]) * t
    y = p0[1] + (p1[1] - p0[1]) * t - lift * 4.0 * t * (1.0 - t)
    return x, y


def stage_of(t, n):
    """0..1 을 n 단계 가운데 몇째로."""
    return max(0, min(n - 1, int(t * n)))


def white_frames(first):
    """포켓몬의 윤곽을 희게 칠해 GROW 단계로 키운 그림들. 발(아래 가운데)을 맞춰 그리므로 칸은 안 맞춘다."""
    white = Image.new("RGBA", first.size, (255, 255, 255, 0))
    white.putalpha(first.getchannel("A"))
    out = []
    for k in GROW:
        size = (max(1, int(round(first.width * k))), max(1, int(round(first.height * k))))
        out.append(white if size == first.size else white.resize(size, Image.NEAREST))
    return out


def hand(who, sw, sh, ball):
    """볼이 날아오는 곳 = 트레이너의 손. 내 쪽은 왼쪽 아래 화면 밖, 상대는 오른쪽 위 화면 밖."""
    if who == "me":
        return (-ball, sh * 0.78)
    return (sw + ball, sh * 0.16)


class _Roll(object):
    """연출 한 토막을 굴린다: dur 초 동안 fn(0..1) 을 부르고, 끝나면 end().

    ## 왜 클로저로 안 굴리나

    처음에는 `def step(): ...; later(16, step)` 로 굴렸다. step 이 자기 자신을 품으므로(순환 참조)
    연출이 끝나도 fn 이 쥔 그림(ImageTk.PhotoImage - 흰 윤곽 다섯 장)이 바로 안 놓이고, 나중에
    가비지 컬렉터가 치운다. 그런데 그 컬렉터는 **아무 스레드에서나** 돈다 - 서버 답을 받는 작업
    스레드에서 돌면 그림을 지우는 Tk 호출이 그 스레드에서 나가고, Tk 스레드가 받아 줄 때까지 한 장씩
    기다린다. 관장 배틀 한 판(볼 수십 번)을 끝낸 뒤 지도를 다시 불러오는 데 10초가 걸렸다.

    그래서 자기를 품지 않는 것으로 굴리고, 끝나거나 그만둘 때 쥔 것을 그 자리에서 놓는다(drop).
    그림은 늘 Tk 스레드에서, 연출이 끝나는 순간에 지워진다.
    """
    __slots__ = ("so", "who", "gen", "t0", "dur", "fn", "end")

    def __init__(self, so, who, dur, fn, end):
        self.so, self.who, self.gen = so, who, so.gen[who]
        self.t0, self.dur, self.fn, self.end = time.monotonic(), dur, fn, end

    def drop(self):
        self.so = self.fn = self.end = None

    def step(self):
        so = self.so
        if so is None:
            return
        if not getattr(so.w, "alive", True) or so.gen[self.who] != self.gen:
            return self.drop()
        t = min(1.0, (time.monotonic() - self.t0) / self.dur) if self.dur > 0 else 1.0
        try:
            self.fn(t)
        except tk.TclError:
            return self.drop()                     # 장면을 다시 그렸다 (창 크기를 바꿨다)
        if t >= 1.0:
            end = self.end
            self.drop()
            if end is not None:
                end()
            return
        so.w.later(16, self.step)


class SendOut(object):
    """볼을 던져 포켓몬을 내보내고(throw + arrive), 불러들인다(recall)."""

    def __init__(self, stage):
        self.w = stage
        self.state = {"me": None, "foe": None}    # 나오는 중: {"landed", "art", "start", "growing", "open_at"}
        self.art = {"me": None, "foe": None}      # 서 있는 포켓몬의 첫 그림 (불러들일 때 윤곽으로 쓴다)
        self.gen = {"me": 0, "foe": 0}            # 연출의 세대. 바뀌면 굴리던 것은 그만둔다
        self.keep = {"me": [], "foe": []}         # PhotoImage 는 들고 있지 않으면 사라진다
        self._balls = {}                          # {(크기, 무엇): PhotoImage}
        # 무슨 일이 어떤 차례로 일어났나 (던졌다 · 떨어졌다 · 커진다 · 섰다 / 줄어든다 · 줄기 · 사라졌다).
        # 연출은 시간으로 굴러가서 느린 컴퓨터에서는 그림을 건너뛴다 - 검사는 화면을 찍어 세지 않고 이것을 본다.
        self.trace = {"me": [], "foe": []}

    # ---- 재료
    def ball_size(self):
        return max(14, int(self.w.sh * 0.085))

    def _ball(self, what):
        """what: 0 ~ SPIN-1 = 도는 볼, "open" = 열린 볼."""
        size = self.ball_size()
        got = self._balls.get((size, what))
        if got is None:
            if what == "open":
                im = effects.ball_image(size, KEY, open_top=True)
            else:
                im = effects.ball_image(size, KEY, tilt=-360.0 * what / SPIN)
            got = self._balls[(size, what)] = ImageTk.PhotoImage(sprites.to_rgba(im, KEY))
        return got

    def hand_of(self, who):
        """볼이 날아오는 곳. 창이 따로 정해 주면(sendout_hand) 그 자리, 아니면 화면 밖."""
        fn = getattr(self.w, "sendout_hand", None)
        if fn is not None:
            p = fn(who)
            if p is not None:
                return p
        return hand(who, self.w.sw, self.w.sh, self.ball_size())

    def spot(self, who):
        """볼이 떨어지는 곳 (발 자리에서 볼 하나만큼 위)."""
        x, y = self.w.me_pos if who == "me" else self.w.foe_pos
        return (x, y - self.ball_size() * 0.6)

    def _tag(self, who):
        return "sendout_" + who

    def _mark(self, who, what):
        log = self.trace[who]
        log.append(what)
        del log[:-40]

    # ---- 굴리기
    def _run(self, who, dur, fn, end=None):
        """dur 초 동안 fn(0..1) 을 부르고 끝나면 end(). 세대가 바뀌거나 그릴 것이 사라지면 그만둔다."""
        _Roll(self, who, dur, fn, end).step()

    def cancel(self, who):
        """그쪽의 연출을 그만둔다 (그리던 볼·빛도 지운다). 서 있는 포켓몬의 그림은 그대로 안다."""
        self.gen[who] += 1
        self.state[who] = None
        self.keep[who] = []
        try:
            self.w.cv.delete(self._tag(who))
        except tk.TclError:
            pass

    def forget(self, who):
        """그쪽에 서 있던 포켓몬이 없어졌다 (쓰러졌다)."""
        self.cancel(who)
        self.art[who] = None

    def close(self):
        """창을 닫는다. 들고 있던 그림을 **여기서(Tk 스레드에서)** 놓는다 (_Roll 의 설명을 보라)."""
        for who in ("me", "foe"):
            self.gen[who] += 1
            self.state[who] = None
            self.keep[who] = []
            self.art[who] = None
        self._balls = {}

    def busy(self, who):
        return self.state[who] is not None

    # ---- 내보내기
    def throw(self, who):
        """볼을 던진다. 그림은 arrive 로 온다 (먼저 와 있어도 된다)."""
        self.cancel(who)
        st = self.state[who] = {"landed": False, "art": None, "start": None, "growing": False, "open_at": 0.0}
        cv = self.w.cv
        p0, p1 = self.hand_of(who), self.spot(who)
        lift = self.w.sh * (0.26 if who == "me" else 0.14)
        try:
            cv.itemconfigure(self.w.sprite[who], image="")
            item = cv.create_image(p0[0], p0[1], image=self._ball(0), tags=("sendout", self._tag(who)))
        except tk.TclError:
            self.state[who] = None
            return
        st["ball"] = item
        self._mark(who, "throw")
        turns = 2.0 if who == "me" else -2.0       # 날아가는 쪽으로 구른다

        def fly(t):
            x, y = arc(p0, p1, t, lift)
            cv.coords(item, x, y)
            cv.itemconfigure(item, image=self._ball(int(t * turns * SPIN) % SPIN))

        def landed():
            st["landed"] = True
            st["open_at"] = time.monotonic()
            try:
                cv.coords(item, p1[0], p1[1])
                cv.itemconfigure(item, image=self._ball("open"))
            except tk.TclError:
                return
            self._mark(who, "landed")
            self._burst(who, p1)
            self.w.later(int(OPEN_S * 600), lambda: self._maybe_grow(who, st))
        self._run(who, THROW_S, fly, landed)

    def arrive(self, who, first, start):
        """그쪽 포켓몬의 그림이 왔다. first = 첫 그림(RGBA), start() = 평소 움직임을 시작하는 일.

        나오는 연출이 돌고 있으면 **연출이 끝난 뒤에** start 를 부르고 True 를 준다.
        아니면 아무것도 안 하고 False 를 준다 (부른 쪽이 바로 시작한다).
        """
        self.art[who] = first
        st = self.state[who]
        if st is None:
            return False
        st["art"], st["start"] = first, start
        self._maybe_grow(who, st)
        return True

    def _maybe_grow(self, who, st):
        if self.state[who] is not st or st["growing"] or not st["landed"] or st["art"] is None:
            return
        wait = st["open_at"] + OPEN_S * 0.6 - time.monotonic()
        if wait > 0.005:
            # 빛이 터지는 중이다. **남은 만큼 뒤에 다시 본다** - 그냥 돌아가면, 예약해 둔 것이 조금 일찍
            # 불렸을 때 다시 불러 줄 것이 없어서 볼이 열린 채로 멈춘다.
            self.w.later(int(wait * 1000) + 1, lambda: self._maybe_grow(who, st))
            return
        st["growing"] = True
        cv = self.w.cv
        try:
            cv.delete(st.get("ball"))
        except tk.TclError:
            pass
        frames = [ImageTk.PhotoImage(f) for f in white_frames(st["art"])]
        self.keep[who] = frames
        self._mark(who, "grow")

        def grow(t):
            cv.itemconfigure(self.w.sprite[who], image=frames[stage_of(t, len(frames))])

        def standing():
            self.state[who] = None
            self._mark(who, "standing")
            start = st["start"]
            if start is not None:
                start()                            # 첫 그림으로 바뀐다 (frames 는 그 뒤에 버려도 된다)
            self.keep[who] = []
        self._run(who, GROW_S, grow, standing)

    def _burst(self, who, at):
        """볼이 열릴 때 터지는 흰 빛 (여섯 갈래)."""
        cv = self.w.cv
        r = float(self.ball_size())
        try:
            rays = [cv.create_line(0, 0, 0, 0, fill=WHITE, width=max(2, int(r / 9)),
                                   tags=("sendout", self._tag(who))) for _i in range(6)]
        except tk.TclError:
            return

        def spread(t):
            for i, item in enumerate(rays):
                ang = math.pi / 3.0 * i + 0.3
                r0, r1 = r * (0.3 + 1.0 * t), r * (0.7 + 1.5 * t)
                cv.coords(item, at[0] + math.cos(ang) * r0, at[1] + math.sin(ang) * r0,
                          at[0] + math.cos(ang) * r1, at[1] + math.sin(ang) * r1)

        def gone():
            for item in rays:
                try:
                    cv.delete(item)
                except tk.TclError:
                    pass
        self._run(who, OPEN_S + 0.08, spread, gone)

    # ---- 불러들이기
    def recall(self, who, done=None):
        """흰 윤곽으로 줄어든다 -> 붉은 줄기가 되어 손으로 돌아간다. 끝나면 done()."""
        self.cancel(who)
        art, self.art[who] = self.art[who], None
        cv = self.w.cv

        def finish():
            if done is not None:
                done()
        if art is None:                            # 그림이 아직 안 왔다 - 그냥 치운다
            try:
                cv.itemconfigure(self.w.sprite[who], image="")
            except tk.TclError:
                pass
            return finish()
        frames = [ImageTk.PhotoImage(f) for f in white_frames(art)]
        self.keep[who] = frames
        self._mark(who, "recall")
        p0 = (self.spot(who)[0], self.spot(who)[1])
        p1 = self.hand_of(who)

        def shrink(t):
            cv.itemconfigure(self.w.sprite[who], image=frames[len(frames) - 1 - stage_of(t, len(frames))])

        def beam_start():
            try:
                cv.itemconfigure(self.w.sprite[who], image="")
                beam = cv.create_line(p0[0], p0[1], p1[0], p1[1], fill=BEAM, width=max(3, self.ball_size() // 7),
                                      tags=("sendout", self._tag(who)))
            except tk.TclError:
                return finish()
            self.keep[who] = []
            self._mark(who, "beam")

            def pull(t):
                cv.coords(beam, p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, p1[0], p1[1])

            def beam_end():
                try:
                    cv.delete(beam)
                except tk.TclError:
                    pass
                self._mark(who, "gone")
                finish()
            self._run(who, BEAM_S, pull, beam_end)
        self._run(who, RECALL_S, shrink, beam_start)
