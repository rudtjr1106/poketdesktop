# -*- coding: utf-8 -*-
"""[시범] 그림 바탕 — 연출을 캔버스 도형이 아니라 **그림 한 장**으로 그린다.

도형 바탕(fx_kit.Pen)은 Tk 캔버스에 다각형 · 원 · 선을 올린다. 반투명도 빛 번짐도 없고, 윈도우에서는 가장자리가
계단진다. 여기서는 장마다 PIL 로 그림 한 장을 그려 캔버스의 그림 항목 하나에 갈아 끼운다.

    Surface          한 편이 쓰는 그림판. begin() 이 붓을 주고, end() 가 그린 것을 한 장으로 합쳐 내보낸다
    RasterPen        fx_kit.Pen 과 같은 모양의 붓 (poly · line · oval · arc · text) - 연출 코드가 그대로 돈다.
                     거기에 그림 바탕에서만 되는 것: glow / glow_poly / glow_line (빛 층에 그린다)
    한 장이 되는 길   도형 층(또렷하다, 2배로 그려 줄여서 가장자리가 매끈하다)
                     + 빛 층(4분의 1 크기에 그려 흐린다 - 연출이 직접 그린 빛 + 도형 층에서 번져 나온 빛)
                     -> 빛을 도형 아래에 깔고(둘레의 후광), 위에도 옅게 한 번 더 얹는다(눈부심)

무대가 fx_raster 를 주면 battle_fx.Effect 가 이 바탕을 쓴다 (안 주면 지금까지의 도형 바탕 그대로):

    stage.fx_raster = {}                         배틀 창: 캔버스 전체를 덮는 그림 항목 하나
    stage.fx_raster = {"pixel": True}            도트풍: 무대 좌표 크기로 그려 점을 키운다 (번짐은 그대로)
    stage.fx_raster = {"k": 2.0, "present": fn}  미리보기: 그린 그림을 fn(img) 으로 받는다

**시범이다.** 바탕화면 레이어(맥은 Tk 그림이 안 그려지고 윈도우는 색을 뚫는 창이라 반투명이 안 된다)는 아직
다루지 않는다. 속도는 관장 배틀 창 크기(860x296)에서 한 장 7~9ms 를 쟀다 (이 맥, 화면에 옮기는 비용 제외).
"""
import math
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

BLOOM = 0.5                     # 도형에서 번져 나오는 빛의 세기
VEIL = 0.16                     # 빛을 도형 위에 한 번 더 얹는 세기 (눈부심)
LAYER_MS = 16                   # 레이어로 올릴 때의 장 간격 (초당 60장까지 - 못 따라가면 장을 건너뛴다)
_RGB = {}
_FONTS = {}


def rgb(c):
    got = _RGB.get(c)
    if got is None:
        h = c.lstrip("#")
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        got = _RGB[c] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return got


def _font(px):
    px = max(6, int(px))
    if px not in _FONTS:
        for path in ("/System/Library/Fonts/AppleSDGothicNeo.ttc", "C:/Windows/Fonts/malgunbd.ttf",
                     "C:/Windows/Fonts/malgun.ttf"):
            try:
                _FONTS[px] = ImageFont.truetype(path, px)
                break
            except Exception:                               # noqa: BLE001
                continue
        else:
            _FONTS[px] = ImageFont.load_default()
    return _FONTS[px]


def _spline(xy, closed):
    """Tk 의 smooth=True 와 같은 곡선: 꼭짓점을 조절점으로, 변의 가운데를 지나는 2차 곡선."""
    n = len(xy)
    if n < 3:
        return xy
    out = []

    def quad(a, c, b):
        for i in range(6):
            t = i / 5.0
            out.append(((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0],
                        (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1]))

    def mid(a, b):
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    if closed:
        for i in range(n):
            quad(mid(xy[i - 1], xy[i]), xy[i], mid(xy[i], xy[(i + 1) % n]))
    else:
        out.append(xy[0])
        for i in range(1, n - 1):
            quad(xy[0] if i == 1 else mid(xy[i - 1], xy[i]), xy[i], xy[-1] if i == n - 2 else mid(xy[i], xy[i + 1]))
    return out


class RasterPen(object):
    """그림에 그리는 붓. fx_kit.Pen 과 부르는 법이 같다."""
    raster = True

    def __init__(self, sf):
        self.sf = sf
        self.s = sf.ds                          # 무대 좌표 -> 도형 층의 점
        self.g = sf.ls                          # 무대 좌표 -> 빛 층의 점
        self.d = ImageDraw.Draw(sf.base)
        self.ld = ImageDraw.Draw(sf.light)
        self.ids = []                           # (도형 바탕의 붓과 모양을 맞춘다 - 여기서는 안 쓴다)

    def _xy(self, pts, k):
        return [(pts[i] * k, pts[i + 1] * k) for i in range(0, len(pts) - 1, 2)]

    # ---- fx_kit.Pen 과 같은 것 ----
    def poly(self, pts, fill, outline="", width=1, smooth=False):
        if len(pts) < 6:
            return
        xy = self._xy(pts, self.s)
        if smooth:
            xy = _spline(xy, True)
        if fill:
            self.d.polygon(xy, fill=rgb(fill) + (255,))
        if outline:
            self.d.line(xy + [xy[0]], fill=rgb(outline) + (255,), width=max(1, int(round(width * self.s))), joint="curve")

    def line(self, pts, fill, width=2, smooth=False, cap="round"):
        if len(pts) < 4 or not fill:
            return
        xy = self._xy(pts, self.s)
        if smooth:
            xy = _spline(xy, False)
        w = max(1, int(round(width * self.s)))
        col = rgb(fill) + (255,)
        self.d.line(xy, fill=col, width=w, joint="curve")
        if cap == "round" and w > 2:
            for x, y in (xy[0], xy[-1]):
                self.d.ellipse([x - w / 2.0, y - w / 2.0, x + w / 2.0, y + w / 2.0], fill=col)

    def oval(self, x, y, rx, ry=None, fill="", outline="", width=1):
        ry = rx if ry is None else ry
        s = self.s
        if rx * s < 0.5 or ry * s < 0.5:
            return
        self.d.ellipse([(x - rx) * s, (y - ry) * s, (x + rx) * s, (y + ry) * s],
                       fill=(rgb(fill) + (255,)) if fill else None, outline=(rgb(outline) + (255,)) if outline else None,
                       width=max(1, int(round(width * s))) if outline else 0)

    def arc(self, x, y, rx, ry, start, extent, outline, width=2):
        s = self.s
        if rx * s < 1 or ry * s < 1:
            return
        if extent < 0:
            start, extent = start + extent, -extent
        self.d.arc([(x - rx) * s, (y - ry) * s, (x + rx) * s, (y + ry) * s], -(start + extent), -start,
                   fill=rgb(outline) + (255,), width=max(1, int(round(width * s))))

    def text(self, x, y, s, fill, font):
        size = (font[1] if isinstance(font, tuple) and len(font) > 1 else 10) * 1.33 * self.s
        self.d.text((x * self.s, y * self.s), str(s), fill=rgb(fill) + (255,), font=_font(size), anchor="mm")

    # ---- 그림 바탕에서만 되는 것: 빛 ----
    def _lit(self, col, a):
        r, g, b = rgb(col)
        return (int(r * a), int(g * a), int(b * a))

    def glow(self, x, y, r, col, a=1.0, sy=1.0):
        """부드러운 빛 덩이 (빛 층에 그린다 - 흐려져서 후광이 된다)."""
        g = self.g
        if r * g < 0.5:
            return
        # 가운데가 밝고 바깥으로 옅어지게 세 겹으로 (한 겹이면 가장자리가 원반처럼 보인다)
        for kr, ka in ((1.0, 0.28), (0.68, 0.6), (0.4, 1.0)):
            rr = r * kr
            self.ld.ellipse([(x - rr) * g, (y - rr * sy) * g, (x + rr) * g, (y + rr * sy) * g],
                            fill=self._lit(col, a * ka))

    def glow_poly(self, pts, col, a=1.0):
        if len(pts) >= 6:
            self.ld.polygon(self._xy(pts, self.g), fill=self._lit(col, a))

    def glow_line(self, pts, col, width=4, a=1.0):
        if len(pts) >= 4:
            self.ld.line(self._xy(pts, self.g), fill=self._lit(col, a), width=max(1, int(round(width * self.g))),
                         joint="curve")


class Surface(object):
    """연출 한 편의 그림판. w, h 는 무대 좌표 크기, k 는 화면 배율 (관장 배틀 창은 2 x 창 크기 배율)."""

    def __init__(self, w, h, k, present, close=None, pixel=False, ss=2):
        self.w, self.h, self.k = w, h, k
        self.size = (max(1, int(round(w * k))), max(1, int(round(h * k))))        # 화면에 올릴 크기
        self.pixel = pixel
        if pixel:                               # 도트풍: 무대 좌표 크기로 그려서 점을 키운다
            self.ds = 1.0
            self.draw_size = (max(1, int(w)), max(1, int(h)))
            self.out_size = self.draw_size
        else:                                   # 매끈하게: ss 배로 그려서 줄인다
            self.ds = k * ss
            self.draw_size = (self.size[0] * ss, self.size[1] * ss)
            self.out_size = self.size
        self.lsize = (max(1, self.out_size[0] // 4), max(1, self.out_size[1] // 4))
        self.ls = self.ds * self.lsize[0] / float(self.draw_size[0])
        self.blur = max(0.8, 6.0 * (self.out_size[0] / float(w)) / 4.0)       # 무대 좌표로 6쯤 번진다
        self._present, self._close = present, close
        self.base = self.light = None
        self.frames = 0
        self.how = ""                           # 화면에 올리는 길: layer(맥) / photo(Tk 그림 항목)
        self.tick_ms = 30                       # 한 장의 간격 (레이어로 올리면 더 촘촘히 - LAYER_MS)

    def begin(self):
        self.base = Image.new("RGBA", self.draw_size, (0, 0, 0, 0))
        self.light = Image.new("RGB", self.lsize, (0, 0, 0))
        return RasterPen(self)

    def end(self):
        """그린 것을 한 장으로 합쳐 내보낸다."""
        base = self.base if self.base.size == self.out_size else self.base.resize(self.out_size, Image.BOX)
        # 도형에서 번져 나오는 빛 (미리 곱한 알파로 줄여서 가장자리가 검게 물들지 않는다)
        r, g, b, _a = base.convert("RGBa").resize(self.lsize, Image.BILINEAR).split()
        lut = [int(v * BLOOM) for v in range(256)]
        halo = Image.merge("RGB", (r.point(lut), g.point(lut), b.point(lut)))
        light = ImageChops.add(self.light, halo).filter(ImageFilter.GaussianBlur(self.blur))
        light = light.resize(self.out_size, Image.BILINEAR)
        r, g, b = light.split()
        a = ImageChops.lighter(r, ImageChops.lighter(g, b))
        under = Image.merge("RGBa", (r, g, b, a)).convert("RGBA")
        out = Image.alpha_composite(under, base)
        veil = [int(v * VEIL) for v in range(256)]
        over = Image.merge("RGBa", (r.point(veil), g.point(veil), b.point(veil), a.point(veil))).convert("RGBA")
        out = Image.alpha_composite(out, over)
        if out.size != self.size:
            out = out.resize(self.size, Image.NEAREST)
        self.frames += 1
        self._present(out)
        return out

    def clear(self):
        self._present(Image.new("RGBA", self.size, (0, 0, 0, 0)))

    def close(self):
        if self._close:
            self._close()
            self._close = None


def open_surface(fx, opts):
    """무대의 fx_raster 로 그림판을 연다. 못 열면 None (그러면 도형 바탕으로 그린다)."""
    opts = opts if isinstance(opts, dict) else {}
    cv = fx.cv
    k_cv = float(getattr(cv, "k", 1.0) or 1.0)
    k = float(opts.get("k") or k_cv)
    try:
        w, h = cv.winfo_width() / k_cv, cv.winfo_height() / k_cv
    except Exception:                                       # noqa: BLE001
        return None
    if w < 8 or h < 8:
        return None
    present = opts.get("present")
    if present is not None:
        return Surface(w, h, k, present, pixel=bool(opts.get("pixel")))
    raw = getattr(cv, "_cv", cv)
    sf = Surface(w, h, k, None, pixel=bool(opts.get("pixel")))
    # 맥: Tk 의 그림 항목은 큰 그림을 갈아 끼울 때마다 화면에 옮기는 데 0.03~0.05초가 걸린다 (초당 20장이 고작이다).
    # 도트를 그리는 것과 같은 길(CALayer)로 올리면 Tk 는 아무것도 다시 그리지 않는다.
    if sys.platform == "darwin" and opts.get("layer", True):
        got = _mac_layer(raw, sf)
        if got:
            sf._present, sf._close, sf.how = got[0], got[1], "layer"
            sf.tick_ms = int(opts.get("tick") or LAYER_MS)
            return sf
    # 그 밖 (윈도우 · 레이어를 못 붙인 맥): 캔버스의 그림 항목 하나를 두고 장마다 갈아 끼운다
    from PIL import ImageTk
    sf.how = "photo"
    photo = ImageTk.PhotoImage(Image.new("RGBA", sf.size, (0, 0, 0, 0)))
    item = raw.create_image(0, 0, image=photo, anchor="nw")
    sf._present = photo.paste

    def close():
        try:
            raw.delete(item)
        except Exception:                                   # noqa: BLE001
            pass
    sf._close = close
    sf.photo = photo                            # (들고 있지 않으면 그림이 사라진다)
    return sf


def _mac_layer(raw, sf):
    """캔버스 자리에 CALayer 를 얹는다. (present, close) 를 돌려주고, 못 하면 None.

    레이어는 창의 내용 뷰에 붙는다 - Tk 가 그린 것 위에 떠서, 연출이 도는 동안 그 자리의 글씨 · 체력바를 덮는다.
    그림은 창 좌표(점)로 올라가고 레티나에서는 레이어가 키워 그린다 (Tk 의 그림 항목도 그렇게 보인다).
    """
    try:
        from Quartz import CALayer, CATransaction
        from . import platform_mac as PM
        top = raw.winfo_toplevel()
        nsw = PM.nswindow(top)
        if nsw is None:
            return None
        view = nsw.contentView()
        view.setWantsLayer_(True)
        root = view.layer()
        if root is None:
            return None
        x = raw.winfo_rootx() - top.winfo_rootx()
        y = raw.winfo_rooty() - top.winfo_rooty()
        w, h = sf.size
        vh = view.bounds().size.height
        lay = CALayer.layer()
        lay.setFrame_(((x, y if view.isFlipped() else vh - y - h), (w, h)))
        lay.setContentsScale_(1.0)
        if sf.pixel:
            lay.setMagnificationFilter_("nearest")
        lay.setZPosition_(100.0)
        root.addSublayer_(lay)
    except Exception:                                       # noqa: BLE001
        return None

    def present(img):
        cg = PM._cgimage(img.convert("RGBa"))               # (CGImage 는 알파를 미리 곱한 것을 받는다)
        CATransaction.begin()
        CATransaction.setDisableActions_(True)              # 안 끄면 장마다 0.2초짜리 겹침이 붙는다
        try:
            lay.setContents_(cg)
        finally:
            CATransaction.commit()

    def close():
        try:
            lay.removeFromSuperlayer()
        except Exception:                                   # noqa: BLE001
            pass
    sf.layer = lay
    return present, close


def blob_points(x, y, r, seed, wob, n, jag, noise):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r * (1.0 - jag + 2.0 * jag * noise(seed * 31 + i * 7) + 0.5 * jag * math.sin(wob + i * 2.1))
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
    return pts
