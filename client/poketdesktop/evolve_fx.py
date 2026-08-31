# -*- coding: utf-8 -*-
"""바탕화면 그 자리에서 벌어지는 진화 연출.

본가에서 진화는 **화면 전환 없이** 그 포켓몬이 서 있던 자리에서 벌어진다.
그래서 여기서도 창을 새로 띄우지 않는다. 이미 바탕화면을 걸어다니던
Pet 의 도트를 그대로 붙잡아서, 그 자리에서 흰 실루엣으로 바꾸고 깜빡이게
한다. 새 창을 띄우면 "진화 화면이 떴다" 가 되어버려서 본가의 느낌이 죽는다.

흐름은 본가 그대로다.

    1. 멈춘다            돌아다니던 걸 세우고 프레임도 고정한다
    2. 깜빡인다          흰 실루엣 ↔ 원래 모습, 점점 빨라진다
    3. 모습이 바뀐다      실루엣이 새 종의 실루엣으로 넘어가며 커졌다 작아진다
    4. 빛이 퍼진다        고리·빛줄기·불티가 사방으로
    5. 새 모습이 드러난다  Pet 의 도트를 새 종의 것으로 갈아끼운다
    6. 축하 문구          도트 위에 떠오른다

## 왜 이렇게 만들었나

**흰 실루엣은 그림을 새로 그리지 않는다.** 이미 있는 도트에서 불투명한
픽셀만 흰색으로 칠하면 된다. sprites.to_rgba 로 알파(모양)를 얻고, 그
모양대로 흰색을 찍는다. 900종에 실루엣 그림을 따로 둘 수는 없다.

**투명색은 처음부터 끝까지 원래 도트의 것 하나로 통일한다.** Pet 의 창은
`-transparentcolor` 방식이라 창마다 투명색이 하나뿐이다. 새 종의 도트는
투명색이 다를 수 있으므로, 연출 중에 쓰는 실루엣은 전부 **원래 도트의
투명색** 위에 만든다. 진짜 새 도트로 갈아끼우는 마지막 순간에만 창의
투명색까지 같이 바꾼다.

**새 종의 도트는 반드시 미리 받아둔다.** 연출 도중에 내려받으면 그 동안
tk 가 멈춰서 애써 만든 애니메이션이 뚝 끊긴다. run_async 로 먼저 받고,
PIL 로 실루엣까지 다 만들어 둔 뒤에야 연출을 시작한다. 받는 동안 포켓몬은
그냥 멈춰 서 있는데, 이게 오히려 "무언가 일어나려 한다" 로 보인다.

**빛과 불티는 fx_layer 의 투명 캔버스에 그린다.** 도트는 각자 자기 창에
있어서 그 위에 뭔가를 겹쳐 그릴 수 없다. battle_fx 가 쓰는 방식 그대로다.

**시간은 전부 root.after 로 흘린다.** time.sleep 을 쓰면 그 순간 화면 전체가
얼어붙는다(돌아다니던 다른 포켓몬까지 같이 멈춘다).

공개 함수:

    play(app, pet, info, on_done=None)
        info = {"fromKr":.., "toKr":.., "fromNum":.., "toNum":..}
    swap_sprite(pet, anim)
        Pet 의 도트만 새 것으로 갈아끼운다 (연출 없이)
"""
import math
import random

from PIL import Image, ImageTk

from common.korean import josa

from . import sprite_cache, sprites
from . import ui_common as U
from .fx_layer import FloatText, FxLayer
from .sprites import LEFT, RIGHT

# ---------------------------------------------------------------- 박자
HOLD_MS = 260            # 멈춰 서서 뜸 들이는 시간
BLINK_STEPS = 16         # 깜빡이는 횟수 (실루엣/원래모습 한 번씩)
BLINK_SLOW = 160         # 첫 깜빡임 간격
BLINK_FAST = 45          # 마지막 깜빡임 간격
BURST_STEPS = 10         # 빛 고리 개수
BURST_MS = 34            # 빛 고리 간격
FLASH_STEPS = 7          # 새 모습을 덮었다 걷히는 흰 빛
TEXT_MS = 1300           # 축하 문구가 떠 있는 시간

# 멈춤 0.26 + 깜빡임 1.64 + 변신 0.63 + 빛 0.43 + 드러남 0.28 = 약 3.2초.
# 여기까지가 '연출' 이고 on_done 도 이때 나간다. 축하 문구는 그 뒤로
# 1.3초 더 떠 있다가 조용히 사라진다.

# 실루엣을 미리 만들어 둘 크기 단계. 0 번은 반드시 원래 크기여야 한다
# (마지막에 진짜 도트로 갈아끼울 때 크기가 튀지 않게).
SCALES = (1.0, 1.13, 1.26, 1.40)

# 실루엣이 커졌다 작아지며 새 종으로 넘어가는 차례.
# (새것인가, 크기단계, 머무는 ms)
MORPH = [
    (0, 1, 60), (0, 2, 60), (0, 3, 70),
    (1, 3, 65), (0, 3, 55), (1, 3, 95),      # 꼭대기에서 두 모습이 겹쳐 깜빡인다
    (1, 2, 70), (1, 1, 70), (1, 0, 85),
]


# ---------------------------------------------------------------- 그림 만들기
def silhouette(img, src_key, out_key):
    """도트 한 장을 흰 실루엣으로 바꾼다.

    to_rgba 로 '어디가 몸이고 어디가 배경인지'(알파)를 받아온 다음, 그
    모양대로만 흰색을 찍는다. 알파는 0 아니면 255 라서 가장자리에 어중간한
    색이 남지 않는다 — 남으면 투명색과 섞여서 테두리에 자홍색 실이 낀다.
    """
    rgba = sprites.to_rgba(img, src_key)
    mask = rgba.split()[3]
    out = Image.new("RGB", img.size, tuple(out_key))
    out.paste(Image.new("RGB", img.size, (255, 255, 255)), (0, 0), mask)
    return out


def scaled(img, factor):
    """도트를 키운다. 흐려지면 안 되니 NEAREST 로만 늘린다.

    LANCZOS 로 늘리면 흰색과 투명색이 섞인 픽셀이 생겨서, 그 부분이
    투명해지지 않고 지저분한 테두리로 남는다.
    """
    if abs(factor - 1.0) < 0.01:
        return img
    w = max(4, int(round(img.width * factor)))
    h = max(4, int(round(img.height * factor)))
    return img.resize((w, h), Image.NEAREST)


# ---------------------------------------------------------------- 도트 갈아끼우기
def swap_sprite(pet, anim):
    """Pet 이 들고 있는 도트를 새 종의 것으로 갈아끼운다.

    Overlay.sync() 는 id 가 같으면 도트를 다시 만들지 않는다(mon 만 바꾼다).
    진화는 id 가 그대로인 채 종만 바뀌는 일이라, 이렇게 직접 갈아끼우지
    않으면 새 모습이 영영 안 나온다.

    발밑 한가운데를 기준으로 자리를 맞춘다. 왼쪽 위를 기준으로 두면
    커진 만큼 아래로 자라나서 땅에 박힌 것처럼 보인다.
    """
    cx = pet.x + pet.fw / 2.0
    by = pet.y + pet.fh

    pet.anim = anim
    pet.fw, pet.fh = anim.w, anim.h
    pet.photos = {
        RIGHT: [ImageTk.PhotoImage(f) for f in anim.frames[RIGHT]],
        LEFT: [ImageTk.PhotoImage(f) for f in anim.frames[LEFT]],
    }
    # 투명색은 그림마다 다르다. 창까지 같이 바꿔주지 않으면 새 도트 배경이
    # 그대로 남아 네모난 판이 하나 떠다닌다.
    hexkey = "#%02x%02x%02x" % anim.key
    try:
        pet.win.attributes("-transparentcolor", hexkey)
    except Exception:
        pass
    try:
        pet.win.configure(bg=hexkey)
        pet.label.configure(bg=hexkey)
    except Exception:
        pass

    pet.frame = 0
    pet.elapsed = 0
    pet.x = cx - pet.fw / 2.0
    pet.y = by - pet.fh
    pet.clamp()
    pet.redraw()
    pet.place()


def refresh_nameplate(pet):
    """이름표를 새 이름으로 다시 만든다."""
    if pet.name_win:
        try:
            pet.name_win.destroy()
        except Exception:
            pass
        pet.name_win = None
    try:
        if pet.ov.settings.get("showNames"):
            pet.make_nameplate()
    except Exception:
        pass
    pet.place()


# ---------------------------------------------------------------- 연출 본체
class Evolution(object):
    """진화 한 번. root.after 로 스스로 굴러간다."""

    def __init__(self, app, pet, info, on_done=None):
        self.app = app
        self.root = app.root
        self.pet = pet
        self.info = info or {}
        self.on_done = on_done

        self.dead = False
        self.jobs = []
        self.items = []              # 캔버스에 그린 것들
        self.texts = []
        self.layer = None
        self.keep = None             # 라벨에 올린 그림 참조 (놓으면 지워진다)

        self.sil_old = []            # 크기 단계별 흰 실루엣 (지금 모습)
        self.sil_new = []            # 크기 단계별 흰 실루엣 (진화 후 모습)
        self.anim_new = None
        self.path_new = None

        self.saved_battling = False
        self.saved_state = None

        # 연출 내내 쓸 기준점. 멈춰 있으니 처음 한 번만 재면 된다.
        self.cx = pet.x + pet.fw / 2.0
        self.cy = pet.y + pet.fh / 2.0
        self.by = pet.y + pet.fh
        self.w0 = pet.fw
        self.h0 = pet.fh

    # ---------------- 시작 ----------------
    def start(self):
        self.freeze()
        base = self.base_frame()
        if base is None:
            return self.finish()
        base_key = self.pet.anim.key
        ov = self.app.overlay
        s = ov.settings if ov else self.app.settings
        api = self.app.api
        num = self.info.get("toNum")
        shiny = bool(self.pet.mon.get("shiny"))
        facing = self.pet.facing

        def work():
            """도트 받기와 PIL 작업은 전부 여기서 끝낸다 (작업 스레드)."""
            old = [scaled(silhouette(base, base_key, base_key), f)
                   for f in SCALES]
            path = anim = None
            new = []
            if num:
                path = sprite_cache.ensure(api, num, shiny)
                if path:
                    anim = sprites.load_animation(
                        path, s["targetHeight"], s["minScale"], s["maxScale"])
                    src = anim.frames[facing][0]
                    base_new = silhouette(src, anim.key, base_key)
                    new = [scaled(base_new, f) for f in SCALES]
            return path, anim, old, new

        def done(r, err):
            if not self.alive():
                return self.finish()
            if err or not r:
                return self.reveal()          # 못 받았어도 축하는 해준다
            self.path_new, self.anim_new, old, new = r
            # ImageTk 는 tk 스레드에서만 만들 수 있다
            try:
                self.sil_old = [ImageTk.PhotoImage(i) for i in old]
                self.sil_new = [ImageTk.PhotoImage(i) for i in new]
            except Exception:
                return self.reveal()
            # 나중에 설정이 바뀌어 도트를 다시 만들 때를 대비해 경로를 등록해 둔다.
            # 이게 없으면 Overlay.refresh_visuals() 에서 새 종의 그림을 못 찾아
            # 포켓몬이 화면에서 사라진다.
            if self.path_new and self.app.overlay is not None:
                self.app.overlay.paths[(num, shiny)] = self.path_new
            self.open_layer()
            self.after(HOLD_MS, lambda: self.blink(0))

        U.run_async(self.root, work, done)

    def base_frame(self):
        """지금 보고 있는 그 프레임. 실루엣의 밑그림이 된다."""
        try:
            row = self.pet.anim.frames[self.pet.facing]
            return row[self.pet.frame % len(row)]
        except Exception:
            return None

    def open_layer(self):
        try:
            area = self.app.overlay.area()
        except Exception:
            area = (self.pet.x - 200, self.pet.y - 200,
                    self.pet.x + 200, self.pet.y + 200)
        try:
            self.layer = FxLayer(self.root, area)
        except Exception:
            self.layer = None

    # ---------------- 멈춰 세우기 ----------------
    def freeze(self):
        """돌아다니는 것도, 제자리 애니메이션도 멈춘다.

        battling 만 켜면 걸음은 멈추지만 Pet.update() 가 advance() 를 계속
        불러서 도트가 꿈틀거린다. 그래서 advance 를 인스턴스에서 잠깐
        빈 함수로 덮어쓴다. 끝나면 지워서 원래 메서드로 되돌린다.
        """
        pet = self.pet
        self.saved_battling = getattr(pet, "battling", False)
        self.saved_state = pet.state
        pet.battling = True
        pet.state = "idle"
        pet.advance = lambda ms: None
        pet.hide_tip()
        pet.cancel_tip()
        if pet.name_win:                       # 이름표는 잠시 치운다
            try:
                pet.name_win.withdraw()
            except Exception:
                pass

    def thaw(self):
        pet = self.pet
        try:
            del pet.advance                    # 인스턴스에서 지우면 원래 것이 돌아온다
        except Exception:
            pass
        try:
            pet.battling = self.saved_battling
            pet.state = self.saved_state or "idle"
            pet.timer = random.randint(30, 90)
        except Exception:
            pass

    # ---------------- 2. 깜빡임 ----------------
    def blink(self, i):
        if not self.alive():
            return self.finish()
        if i >= BLINK_STEPS or not self.sil_old:
            return self.morph(0)
        # 뒤로 갈수록 간격이 짧아진다 — 이게 "무언가 커지고 있다" 는 느낌을 낸다
        t = i / float(max(1, BLINK_STEPS - 1))
        gap = int(BLINK_SLOW + (BLINK_FAST - BLINK_SLOW) * t)
        if i % 2 == 0:
            self.show(self.sil_old[0])
        else:
            self.show_normal()
        if i % 3 == 0:
            self.spark()
        self.after(gap, lambda: self.blink(i + 1))

    # ---------------- 3. 모습이 바뀐다 ----------------
    def morph(self, i):
        if not self.alive():
            return self.finish()
        if not self.sil_new:                   # 새 도트가 없으면 바로 넘어간다
            return self.burst()
        if i >= len(MORPH):
            return self.burst()
        which, level, ms = MORPH[i]
        row = self.sil_new if which else self.sil_old
        self.show(row[min(level, len(row) - 1)])
        if i in (2, 5):
            self.spark()
        self.after(ms, lambda: self.morph(i + 1))

    # ---------------- 4. 빛이 퍼진다 ----------------
    def burst(self):
        if not self.alive():
            return self.finish()
        self.rays()
        self.rings(0)
        self.dust()
        self.after(BURST_STEPS * BURST_MS + 90, self.reveal)

    # ---------------- 5. 새 모습 ----------------
    def reveal(self):
        if not self.alive():
            return self.finish()
        if self.anim_new is not None:
            try:
                swap_sprite(self.pet, self.anim_new)
                self.update_mon()
                refresh_nameplate(self.pet)
            except Exception:
                pass
        else:
            self.show_normal()
        self.keep = None
        if self.pet.name_win:
            try:
                self.pet.name_win.deiconify()
            except Exception:
                pass
        self.flash(0)

    def flash(self, i):
        """새 모습을 덮고 있던 흰 빛이 걷힌다."""
        if not self.alive() or not self.layer:
            return self.congrats()
        if i >= FLASH_STEPS:
            return self.congrats()
        cv = self.layer.cv
        x, y = self.at(self.cx, self.cy)
        r = max(self.pet.fw, self.pet.fh) * (0.95 - i * 0.13) + 6
        if r > 2:
            oval = cv.create_oval(x - r, y - r * 1.05, x + r, y + r * 1.05,
                                  fill="#ffffff", outline="")
            self.items.append(oval)
            self.after(46, lambda it=oval: self.kill(it))
        self.after(40, lambda: self.flash(i + 1))

    # ---------------- 6. 축하 문구 ----------------
    def congrats(self):
        """도트 위에 축하 문구를 띄운다.

        조사는 natural() 로 문장을 훑는 대신 josa() 로 직접 붙인다. 여기서
        붙일 자리는 두 곳뿐이고, 이름이 그대로 들어오는 게 확실하기 때문이다.
        ('풀' 처럼 ㄹ 받침으로 끝나면 '으로' 가 아니라 '로' 인데, 그 판단도
        josa() 가 한다.)

        연출은 여기서 끝난 것으로 보고 on_done 을 지금 부른다. 문구가 다
        떠오를 때까지 기다리게 하면 부르는 쪽의 갱신이 괜히 늦어진다.
        """
        from_kr = self.info.get("fromKr") or "포켓몬"
        to_kr = self.info.get("toKr") or "새로운 모습"
        line = "축하합니다! %s%s %s%s 진화했다!" % (
            from_kr, josa(from_kr, "은"), to_kr, josa(to_kr, "으로"))
        if self.layer and self.alive():
            try:
                self.texts.append(
                    FloatText(self.layer, self.cx, self.pet.y - 10, line,
                              U.ACCENT, ms=TEXT_MS))
            except Exception:
                pass
        try:
            self.app.notify(line)
        except Exception:
            pass
        self.notify_done()
        self.after(TEXT_MS, self.finish)

    def update_mon(self):
        """서버 동기화가 오기 전까지 쓸 정보를 미리 맞춰둔다.

        이름을 안 바꿨으면(별명이 없으면) 이름도 새 종 이름으로 따라간다.
        별명을 지어준 아이라면 이름은 그대로 두는 게 맞다.
        """
        mon = self.pet.mon
        info = mon.get("info") or {}
        from_kr = self.info.get("fromKr")
        to_kr = self.info.get("toKr")
        if self.info.get("toNum"):
            mon["num"] = self.info["toNum"]
        # 도감 키도 같이 바꾼다. 번호만 바꿔 두면 다음 동기화 전까지
        # dex.get(mon["species"]) 가 진화 전 종을 돌려줘서, 타입이나
        # 능력치를 물어보는 곳이 엉뚱한 답을 받는다.
        if self.info.get("to"):
            mon["species"] = self.info["to"]
        if to_kr:
            if not info.get("name") or info.get("name") == from_kr:
                info["name"] = to_kr
            info["species"] = to_kr
        mon["info"] = info

    # ---------------- 도트에 그림 올리기 ----------------
    def show(self, photo):
        """실루엣 한 장을 Pet 라벨에 올린다.

        크기가 제각각이라 창이 같이 커졌다 작아진다. 발밑 한가운데를 붙잡아
        둬야 커질 때 아래로 자라 보이지 않는다.
        """
        pet = self.pet
        try:
            pet.label.configure(image=photo)
        except Exception:
            return
        self.keep = photo                      # 참조를 놓으면 그림이 지워진다
        w, h = photo.width(), photo.height()
        try:
            pet.win.geometry("+%d+%d" % (int(self.cx - w / 2.0),
                                         int(self.by - h)))
        except Exception:
            pass

    def show_normal(self):
        try:
            self.pet.redraw()
            self.pet.place()
        except Exception:
            pass

    # ---------------- 빛 조각들 ----------------
    def at(self, sx, sy):
        """화면 좌표 -> 이펙트 캔버스 좌표."""
        return self.layer.to_local(sx, sy) if self.layer else (sx, sy)

    def spark(self):
        """발밑에서 불티 하나가 떠오른다."""
        if not self.layer:
            return
        cv = self.layer.cv
        sx = self.cx + random.uniform(-self.w0 * 0.65, self.w0 * 0.65)
        x, y = self.at(sx, self.by + random.uniform(-4, 6))
        r = random.uniform(2, 4)
        col = U.ACCENT if random.random() < 0.6 else "#ffffff"
        item = cv.create_oval(x - r, y - r, x + r, y + r, fill=col, outline="")
        self.items.append(item)

        def rise(i):
            if not self.alive() or not self.layer:
                return
            if i > 11:
                return self.kill(item)
            try:
                cv.move(item, 0, -6)
            except Exception:
                return
            self.after(38, lambda: rise(i + 1))
        rise(0)

    def rings(self, i):
        """빛 고리가 겹겹이 퍼져 나간다."""
        if not self.alive() or not self.layer:
            return
        if i >= BURST_STEPS:
            return
        cv = self.layer.cv
        x, y = self.at(self.cx, self.cy)
        r = 16 + i * 17
        col = "#ffffff" if i % 2 == 0 else U.ACCENT
        ring = cv.create_oval(x - r, y - r * 0.92, x + r, y + r * 0.92,
                              outline=col, width=max(1, 7 - i))
        self.items.append(ring)
        self.after(170, lambda it=ring: self.kill(it))
        self.after(BURST_MS, lambda: self.rings(i + 1))

    def rays(self):
        """사방으로 뻗는 빛줄기."""
        if not self.layer:
            return
        cv = self.layer.cv
        cx, cy = self.at(self.cx, self.cy)
        n = 14
        lines = []
        for k in range(n):
            a = 2 * math.pi * k / n + random.uniform(-0.12, 0.12)
            it = cv.create_line(cx, cy, cx, cy, fill="#ffffff", width=4)
            self.items.append(it)
            lines.append((it, a))

        def step(i):
            if not self.alive() or not self.layer:
                return
            if i > 9:
                for it, _a in lines:
                    self.kill(it)
                return
            inner = 8 + i * 11
            outer = inner + 30
            for it, a in lines:
                ca, sa = math.cos(a), math.sin(a)
                try:
                    cv.coords(it, cx + ca * inner, cy + sa * inner,
                              cx + ca * outer, cy + sa * outer)
                    cv.itemconfigure(it, width=max(1, 4 - i // 3),
                                     fill="#ffffff" if i < 6 else U.ACCENT)
                except Exception:
                    return
            self.after(32, lambda: step(i + 1))
        step(0)

    def dust(self):
        """작은 빛 알갱이가 사방으로 튄다."""
        if not self.layer:
            return
        cv = self.layer.cv
        cx, cy = self.at(self.cx, self.cy)
        bits = []
        for _ in range(18):
            a = random.uniform(0, 2 * math.pi)
            sp = random.uniform(5.0, 11.0)
            r = random.uniform(2, 4)
            it = cv.create_oval(cx - r, cy - r, cx + r, cy + r,
                                fill=U.ACCENT if random.random() < 0.5
                                else "#ffffff", outline="")
            self.items.append(it)
            bits.append([it, math.cos(a) * sp, math.sin(a) * sp * 0.8])

        def step(i):
            if not self.alive() or not self.layer:
                return
            if i > 12:
                for b in bits:
                    self.kill(b[0])
                return
            for it, vx, vy in bits:
                try:
                    cv.move(it, vx, vy + i * 0.35)   # 조금씩 내려앉는다
                except Exception:
                    return
            self.after(34, lambda: step(i + 1))
        step(0)

    # ---------------- 도구 ----------------
    def alive(self):
        if self.dead:
            return False
        try:
            return bool(self.pet.win.winfo_exists())
        except Exception:
            return False

    def after(self, ms, fn):
        if self.dead:
            return None
        j = self.root.after(ms, fn)
        self.jobs.append(j)
        return j

    def kill(self, item):
        if not self.layer:
            return
        try:
            self.layer.cv.delete(item)
        except Exception:
            pass

    def notify_done(self):
        """끝났다고 알린다. 몇 번을 불러도 한 번만 나간다."""
        if self.on_done:
            cb, self.on_done = self.on_done, None
            try:
                cb()
            except Exception:
                pass

    # ---------------- 정리 ----------------
    def finish(self):
        if self.dead:
            return
        self.dead = True
        for j in self.jobs:
            try:
                self.root.after_cancel(j)
            except Exception:
                pass
        self.jobs = []
        for t in self.texts:
            try:
                t.stop()
            except Exception:
                pass
        self.texts = []
        if self.layer:
            self.layer.destroy()
            self.layer = None
        self.items = []
        self.keep = None
        self.thaw()
        try:
            if self.pet.name_win:
                self.pet.name_win.deiconify()
            self.pet.place()
        except Exception:
            pass
        try:
            setattr(self.pet, "evolving", False)
        except Exception:
            pass
        self.notify_done()

    def stop(self):
        """밖에서 강제로 끊을 때 (로그아웃, 종료)."""
        self.on_done = None
        self.finish()


# ---------------------------------------------------------------- 공개 함수
def play(app, pet, info, on_done=None):
    """바탕화면의 그 자리에서 진화 연출을 한 번 재생한다.

    info = {"fromKr":.., "toKr":.., "fromNum":.., "toNum":..}
    전부 root.after 로 도는 비동기라 이 함수는 바로 돌아온다.
    연출이 끝나면(또는 도중에 포켓몬이 사라지면) on_done() 을 부른다.
    """
    if pet is None or not info:
        if on_done:
            on_done()
        return None
    if getattr(pet, "evolving", False):        # 두 번 겹쳐 돌지 않게
        if on_done:
            on_done()
        return None
    pet.evolving = True
    ev = Evolution(app, pet, info, on_done)
    try:
        ev.start()
    except Exception:
        ev.finish()
    return ev
