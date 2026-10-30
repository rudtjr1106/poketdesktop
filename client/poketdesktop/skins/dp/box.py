# -*- coding: utf-8 -*-
"""DP 테마 - 포켓몬 (PC 박스).

DP 의 PC '포켓몬 맡기기' 화면을 본뜬다:

    ┌ 요약 (원작의 위 화면) ─────┐┌ 파티 [파티1|…|파티5] [이름 바꾸기]          보유 N마리 [새로고침] ┐
    │ 도트 무대 · 이름 띠 · 타입  ││ (◀)  [  박스 이름   12/30 ▾  ]  (▶)   [이름 바꾸기]               │
    │ 특성 · 성격 · 지닌 도구     ││ [타입: 전체]  찾기 [        ]          [도감|이름|Lv|종족값]     │
    │ 경험치 · 친밀도 · 진화      ││ ┌ 파티 ┐ ┌ 벽지 위의 6 × 5 칸 ───────────────────────────────┐  │
    │ 메가진화 · 능력치           ││ │ 6칸  │ │  (누르면 고른다 · 끌어서 맞바꾼다 · 여러 마리 고르기)  │  │
    │ 기술 (DP 기술 단추)          ││ └──────┘ └────────────────────────────────────────────────────┘  │
    │                             ││ [데리고 다니기] [별명] [박스 옮기기] [색 고르기] [놓아주기]       │
    └─────────────────────────────┘└ 메시지 상자 ─────────────────────────────────────────────────────┘

**동작은 기본 창(ui_box.BoxWindow)의 것을 그대로 쓴다** - 박스 넘기기 · 거르기 · 줄 세우기 · 여러 마리 고르기 ·
맞바꾸기(_apply_drop) · 별명 · 데리고 다니기 · 놓아주기 · 지닌 도구 · 기술 떠올리기 · 유대 미션.
여기서는 그 창이 칠하라고 부르는 자리만 DP 로 그린다.
"""
import tkinter as tk

from PIL import ImageTk

from common import legends as L
from common import movetext as MT
from common import pokelogic as P
from common import tint as Tn
from common.korean import natural

from ... import box_filter, item_icons, sprite_cache, sprites
from ... import ui_bond as BD
from ... import ui_box as BX
from ... import ui_common as U
from . import (CUR, DIM, HOV, INK, INK2, LINE, LINE_D, PANEL, SEL, SEP, TAGC, WIN_BG, font, tone)
from . import kit as K
from .scene import Scene, Slot, T

D = ("dscene",)                # 요약 칸 캔버스의 항목
G = ("gscene",)                # 박스 칸 캔버스의 항목

SORTS = [("num", "도감"), ("name", "이름"), ("level", "Lv"), ("bst", "종족값")]
WALL = ("#7cc06a", "#6cb05c", "#5a9a4c")      # 벽지 (DP 의 '숲' 벽지처럼 초록 격자)


class ArtSlot(object):
    """요약 칸의 도트 자리. 기본 창의 도트 코드(load_art · play_anim)가 Label 처럼 configure 를 부른다."""

    def __init__(self, view):
        self.view = view
        self.image = None
        self.text = ""
        self.fg = DIM
        self.ids = None

    def configure(self, image=None, text=None, fg=None, **_kw):
        if image is not None:
            self.image = image or None
        if text is not None:
            self.text = text
        if fg is not None:
            self.fg = fg
        if self.ids:
            cv = self.view.dcv
            try:
                cv.itemconfigure(self.ids[0], image=self.image or "")
                cv.itemconfigure(self.ids[1], text="" if self.image else self.text, fill=tone(self.fg))
            except tk.TclError:
                pass

    config = configure


# ---------------------------------------------------------------- 메가진화 · 유대 미션
class Bond(BD.BondPanel):
    """기본 메가진화 칸(ui_bond.BondPanel)의 동작 그대로 - 서버에서 카드 받기 · 미션 시작 · 스톤 받기.
    그리는 것만 '줄 목록' 으로 모아 두고 요약 칸이 그린다."""

    def __init__(self, box):
        self.box = box
        self.width = 0
        self.before = None
        self.token = 0
        self.card = None
        self.pid = None
        self.btn = None
        self.visible = False
        self.lines = []            # [(종류, ...)] - 요약 칸이 이 차례로 그린다
        self.btn_spec = None
        self.previews = []

    def show(self, m):
        self.token += 1
        self.card = None
        self.pid = m.get("id")
        dex = self.box.app.dex
        forms = ((getattr(dex, "mega_of", None) or {}).get(m.get("species")) or []) if dex else []
        self.visible = bool(forms) and not m.get("isEgg")
        self.lines = []
        self.btn_spec = None
        self.previews = []
        if not self.visible:
            return
        self._preview(m)
        if not any(f.get("megaStone") for f in forms):
            self._lines([("화룡점정을 알고 있으면 스톤 없이 메가진화합니다. 키스톤은 있어야 합니다.", U.FG_DIM)])
            return
        self._lines([("불러오는 중...", U.FG_FAINT)])
        tok, pid = self.token, self.pid
        api = self.box.app.api
        U.run_async(self.box.root, lambda: api.bond(pid), lambda r, err: self._got(tok, r, err))

    def _preview(self, m):
        dex = self.box.app.dex
        self.previews = []
        for form in BD.forms_for(dex, m):
            pv = BD.mega_preview(dex, m, form)
            if pv:
                pv["needBond"] = bool(pv.get("stoneKr") and not pv.get("move") and m.get("bonded") is False)
                self.previews.append(pv)

    def _clear(self):
        self.lines = []

    def _lines(self, rows):
        self.lines = [("text", t, c) for t, c in rows]
        self.box._repaint_detail()

    def _button(self, spec):
        self.btn_spec = spec
        self.box._repaint_detail()

    def render(self, c):
        self.card = c
        key = c.get("keystone") or {}
        has_key = bool(key.get("has"))
        missing = set(c.get("missing") or [])
        out = [("kv", "키스톤", "있음" if has_key else "관장 %d / %d곳" % (key.get("gyms", 0), key.get("need", 8)),
                U.GOOD if has_key else U.FG_DIM)]
        names = ["%s%s" % (s.get("kr") or s["id"], "" if s["id"] in missing else " (받음)")
                 for s in c.get("stones") or []]
        out.append(("kv", "스톤", "  ·  ".join(names), BD.MEGA if missing else U.GOOD))
        btn = None
        if not c.get("started"):
            now, need = int(c.get("happiness") or 0), int(c.get("need") or 255)
            out.append(("bar", "유대", "%d / %d" % (now, need), now / float(need or 1), "#e858a0"))
            reward = "메가스톤을 받습니다." if missing else "이 포켓몬도 메가진화할 수 있어요."
            if not has_key:
                msg, fg = "관장 8곳을 이기면 키스톤을 받습니다. 키스톤이 있어야 메가진화할 수 있어요.", U.FG_DIM
            elif now < need:
                msg, fg = ("데리고 다니며 유대를 끝까지 채우면 바탕화면에 빛나는 돌이 나타납니다. "
                           "누르면 유대 미션이 시작돼요."), U.FG_DIM
                if not missing:
                    msg = "이 종의 메가스톤은 이미 있지만, 메가진화는 유대 미션을 마친 포켓몬만 할 수 있어요. " + msg
            else:
                msg, fg, btn = "유대가 가득 찼습니다! 미션 셋을 마치면 " + reward, BD.MEGA, ("미션 시작", self.do_start)
            out.append(("text", msg, fg))
        else:
            for i, ms in enumerate(c.get("missions") or []):
                v, t = int(ms.get("value") or 0), int(ms.get("target") or 1)
                done = v >= t
                out.append(("bar", "%s %s" % ("①②③"[i] if i < 3 else "·", ms.get("text") or ""), "%d / %d" % (v, t),
                            v / float(t or 1), "#2c9a4c" if done else "#8a6ae0"))
            if c.get("claimable"):
                msg, fg, btn = "미션을 다 채웠습니다! 메가스톤을 받으세요.", BD.MEGA, ("메가스톤 받기", self.do_claim)
            elif c.get("stone"):
                kr = next((s.get("kr") for s in c.get("stones") or [] if s["id"] == c["stone"]), c["stone"])
                msg, fg = "%s 을(를) 받았습니다. 지니게 하고 배틀에서 메가진화를 켜 보세요." % kr, U.GOOD
            elif c.get("bondOnly"):
                msg, fg = "유대 미션을 마쳤습니다! 이 포켓몬은 이제 메가진화할 수 있어요. 메가스톤을 지니게 하세요.", U.GOOD
            elif c.get("done"):
                msg, fg = "미션을 마쳤습니다.", U.GOOD
            else:
                msg, fg = ("세 가지를 다 채우면 %s" % ("메가스톤을 받습니다." if missing
                                                 else "이 포켓몬도 메가진화할 수 있어요.")), U.FG_DIM
            out.append(("text", msg, fg))
        self.lines = out
        self.btn_spec = btn
        self.box._repaint_detail()


# ---------------------------------------------------------------- 박스 창
class BoxWindow(Scene, BX.BoxWindow):

    DW_PX = 330            # 요약 칸 폭
    PARTY_PX = 150         # 파티 칸 폭
    THUMB = 40             # 칸에 놓는 도트 높이

    def _build(self):
        self.inner = True                      # 기본 창의 _refilter 가 '목록이 있나' 를 이것으로 본다
        self._party_list = []
        self._page_mons = []
        self._hover = None
        self._target = None
        self._thumbs = {}
        self._thumb_busy = set()
        self._cells = {}                       # pid -> (x1, y1, x2, y2) 칸 캔버스 위치
        self._pslots = {}                      # pid -> (x1, y1, x2, y2) 판(scene) 위치
        self._boxes = {}                       # 이름 -> 판 위치 (드롭다운을 그 아래에 연다)
        self._count_text = ""
        self._page_text = ""
        self._page_state = (False, False, False)
        self._d = None                         # 요약 칸에 그릴 것
        self._move_pick = None
        self._dpage = "info"                   # 요약의 쪽 (정보 · 능력 · 기술 · 메가진화)
        self._dcv_h = 0
        self._job_d = None
        self.f_type = None
        self.type_choices = []
        self.f_query = tk.StringVar()

        self._scene_init()
        self.win.configure(bg=WIN_BG)
        self.cv.configure(bg=WIN_BG)
        self.f_query.trace_add("write", lambda *_a: self._query_changed())
        self.find_box = K.entry(self.cv, self.f_query, width=10)
        # 요약 칸 - 길어서 따로 굴러가는 캔버스
        # 요약 칸: 흰 판 (가는 테) - 길어서 따로 굴러가는 캔버스
        self.dframe = tk.Frame(self.cv, bg=PANEL, bd=0, highlightthickness=1, highlightbackground=LINE)
        self.dcv = tk.Canvas(self.dframe, bg=PANEL, highlightthickness=0, bd=0, yscrollincrement=1)
        self.dsb = K.Scroll(self.dframe, self.dcv, PANEL)
        self.dsb.pack(side="right", fill="y", pady=U.h(6))
        self.dcv.pack(side="left", fill="both", expand=True, padx=(U.h(12), U.h(4)), pady=U.h(12))
        self.dcv.configure(yscrollcommand=self.dsb.set)
        U.scrollable(self.dcv, 3)
        self.dcv.bind("<Configure>", lambda _e: self._repaint_detail())
        # 박스 칸 - 벽지 위의 6 × 5 칸 (찾는 중이면 그 아래로 길어진다)
        self.gframe = tk.Frame(self.cv, bg=PANEL, bd=0, highlightthickness=0)
        self.gcv = tk.Canvas(self.gframe, bg=PANEL, highlightthickness=0, bd=0, yscrollincrement=1)
        self.gsb = K.Scroll(self.gframe, self.gcv, PANEL)
        self.gsb.pack(side="right", fill="y")
        self.gcv.pack(side="left", fill="both", expand=True)
        self.gcv.configure(yscrollcommand=self.gsb.set)
        U.scrollable(self.gcv, 3)
        self.gcv.bind("<Configure>", lambda _e: self._paint_grid())
        for cv in (self.gcv, self.cv):
            cv.bind("<Motion>", self._motion, add="+")
        self.gcv.bind("<Leave>", lambda _e: self._set_hover(None))
        self.gcv.bind("<ButtonPress-1>", self._grid_press)
        self.gcv.bind("<B1-Motion>", self._drag_move)
        self.gcv.bind("<ButtonRelease-1>", self._drag_release)
        self.cv.tag_bind("pslot", "<ButtonPress-1>", self._party_press)
        self.cv.tag_bind("pslot", "<B1-Motion>", self._drag_move)
        self.cv.tag_bind("pslot", "<ButtonRelease-1>", self._drag_release)

        self.d_art = ArtSlot(self)
        self.bond = Bond(self)
        # 기본 창의 동작 코드가 configure 로 켜고 끄는 단추들
        self.btn_party = K.CButton(self.cv, "데리고 다니기", self.toggle_party, "blue", font(11))
        self.btn_nick = K.CButton(self.cv, "별명 짓기", self.do_nickname, "gray", font(10))
        self.btn_move = K.CButton(self.cv, "박스 옮기기", self.move_box, "gray", font(10))
        self.btn_tint = K.CButton(self.cv, "색 고르기", self.do_tint, "gray", font(10))
        self.btn_release = K.CButton(self.cv, "놓아주기", self.do_release, "red", font(10))
        self.btn_multi_move = K.CButton(self.cv, "옮기기 (0마리)", self.move_checked, "blue", font(11))
        # 고른 것을 한 번에 놓아준다 (기본 창의 release_checked · 확인 창 그대로). 평소의 '놓아주기' 와 같은 붉은 단추
        self.btn_multi_release = K.CButton(self.cv, "놓아주기 (0마리)", self.release_checked, "red", font(10))
        self.btn_multi_all = K.CButton(self.cv, "이 화면 전부", self.check_all_shown, "gray", font(10))
        self.btn_multi_clear = K.CButton(self.cv, "고르기 풀기", self.clear_checks, "gray", font(10))
        self.btn_multi_done = K.CButton(self.cv, "그만", self.exit_multi, "gray", font(10))
        self.btn_prev = K.CButton(self.cv, "◀", lambda: self._page(-1), "gray", font(11))
        self.btn_next = K.CButton(self.cv, "▶", lambda: self._page(1), "gray", font(11))
        self.btn_rename = K.CButton(self.cv, "이름 바꾸기", self.rename_box, "gray", font(9))
        self.btn_party_name = K.CButton(self.cv, "이름 바꾸기", self.rename_party, "gray", font(9))
        self.btn_reload = K.CButton(self.cv, "새로고침", self.reload, "gray", font(9))
        self.btn_hold = K.CButton(self.dcv, "지니게 하기", self.do_hold, "blue", font(9))
        self.btn_unhold = K.CButton(self.dcv, "벗기기", self.do_unhold, "gray", font(9))
        self.btn_remember = K.CButton(self.dcv, "기술 떠올리기", self.do_remember, "blue", font(9))
        self.btn_bond = K.CButton(self.dcv, "", self._bond_click, "red", font(9))
        self.btn_type = Slot("타입: 전체", self._soon)
        self.lbl_page = "page"                 # open_box_menu 가 _menu 에 넘기는 '단추' - 판 위치 이름
        self.set_buttons(False)

    # ---------------- 기본 창의 칠하는 자리 ----------------
    def say(self, msg, color=None):
        text = natural(msg or "")
        self._say(text, color if color in (U.DANGER, U.GOOD, U.INFO) else None)
        if not text and self._msg_ids:
            try:
                a, b = self._msg_ids
                self.cv.itemconfigure(b, text=self._count_text, fill=DIM)
                if a:
                    self.cv.itemconfigure(a, text=self._count_text)
            except tk.TclError:
                pass

    def fit_scroll(self):
        pass

    def _paint_party(self):
        self._soon()

    def _paint_sort(self):
        self._soon()

    def _paint_page(self, total):
        if self._searching():
            self._page_text = "찾는 중 · %d마리" % total
            self._page_state = (False, False, False)
        elif self.sort:
            size, pages = self.box_size(), self.rank_pages(total)
            first = self.rank_page * size + 1
            form = "%d~%d위 / %d" if self.sort == "bst" else "%d~%d / %d마리"
            self._page_text = (form % (first, min(total, first + size - 1), total)) if total else "0마리"
            self._page_state = (self.rank_page > 0, self.rank_page < pages - 1, False)
        else:
            self._page_text = "%s   %d/%d ▾" % (self.box_name(self.box_no), self.box_used(self.box_no),
                                               self.box_size())
            self._page_state = (self.box_no > 0, self.box_no < self.box_count() - 1, True)
        prev, nxt, ren = self._page_state
        self.btn_prev.configure(state="normal" if prev else "disabled")
        self.btn_next.configure(state="normal" if nxt else "disabled")
        self.btn_rename.configure(state="normal" if ren else "disabled")
        self._soon()

    def enter_multi(self):
        if self.multi:
            return
        self.multi = True
        self._last_check = None
        self._paint_multi()
        self.say("옮기거나 놓아줄 포켓몬을 눌러 고르세요. Shift 를 누른 채 누르면 사이의 것까지 고릅니다.", U.FG_DIM)
        self._soon()

    def exit_multi(self):
        if not self.multi:
            return
        self.multi = False
        self.checked = set()
        self._last_check = None
        self._sync_checks()
        self.say("")
        if self.sel is not None:
            self.select(self.sel)
        self._soon()

    def _sync_checks(self):
        self._paint_grid()
        self._soon()

    def _render(self, keep=None):
        self._stop_rows()
        self._by_id = dict((m["id"], m) for m in self.mons)
        self.checked = set(i for i in self.checked if self._can_check(self._by_id.get(i)))
        self._show(keep)

    def _show(self, keep=None):
        self._stop_rows()
        party, _box, page_box, _all, _filtered = self._view_lists()
        self._party_list = list(party)
        self._page_mons = list(page_box)
        ids = [m["id"] for m in party] + [m["id"] for m in page_box]
        self.rows = dict((i, None) for i in ids)          # 지금 보이는 것 (select 가 '있나' 를 본다)
        self._count_text = self.count_text(party)
        self._load_thumbs(party + page_box)
        try:
            self.gcv.yview_moveto(0)
        except tk.TclError:
            pass
        self._paint_grid()
        self._soon()
        if keep and keep in self.rows:
            self.select(keep)
        elif ids:
            self.select(ids[0])

    def select(self, pid):
        BX.BoxWindow.select(self, pid)
        self._paint_grid()
        self._soon()

    def _menu(self, btn, rows, below=False):
        """드롭다운 - 그 단추(판 위의 자리) 아래에."""
        box = None
        if isinstance(btn, str):
            box = self._boxes.get(btn)
        elif isinstance(btn, K.CButton) and btn.box:
            box = btn.box
            cv = btn.cv
        if box is not None:
            cv = btn.cv if isinstance(btn, K.CButton) else self.cv
            try:
                x = cv.winfo_rootx() + int(box[0])
                y = cv.winfo_rooty() + (int(box[3]) + 2 if below or btn == "page" else int(box[1]) - U.h(20))
            except tk.TclError:
                return None
        else:
            try:
                x, y = self.win.winfo_rootx() + 80, self.win.winfo_rooty() + 120
            except tk.TclError:
                return None
        return U.PopupMenu(self.root, rows, x, y, width=220)

    def _open_type_menu(self):
        return self._menu("type", self._type_rows(), below=True)

    # ---------------- 칸 도트 ----------------
    def _thumb_key(self, m):
        return (m.get("formNum") or m.get("num"), Tn.skin(m))

    def _thumb(self, m):
        if m.get("isEgg"):
            from ... import eggs_ui
            return item_icons.photo(eggs_ui.EGG_ITEM.get((m.get("egg") or {}).get("kind"), "LEGENDEGG"), 32)
        return self._thumbs.get(self._thumb_key(m))

    def _load_thumbs(self, mons):
        want = []
        for m in mons:
            if m.get("isEgg"):
                continue
            k = self._thumb_key(m)
            if k[0] and k not in self._thumbs and k not in self._thumb_busy and k not in want:
                want.append(k)
        if not want:
            return
        self._thumb_busy.update(want)
        api = self.app.api
        size = U.h(self.THUMB)

        def work():
            out = {}
            for num, skin in want:
                try:
                    path = sprite_cache.ensure(api, num, skin)
                    if not path:
                        continue
                    anim = sprites.load_animation(path, target_height=size, min_scale=0.2, max_scale=3.0,
                                                  max_frames=1, max_size=(int(size * 1.3), size))
                    out[(num, skin)] = sprites.to_rgba(anim.frames[sprites.RIGHT][0], anim.key)
                except Exception:                           # noqa: BLE001
                    pass
            return out

        def done(imgs, err):
            self._thumb_busy.difference_update(want)
            if err or not imgs or not self._alive():
                return
            for k, img in imgs.items():
                try:
                    self._thumbs[k] = ImageTk.PhotoImage(img)
                except Exception:                           # noqa: BLE001
                    pass
            self._paint_grid()
            self._soon()
        U.run_async(self.root, work, done)

    # ---------------- 고르기 · 끌기 ----------------
    def _cell_at(self, x, y):
        cy = self.gcv.canvasy(y)
        for pid, (x1, y1, x2, y2) in self._cells.items():
            if x1 <= x <= x2 and y1 <= cy <= y2:
                return pid
        return None

    def _grid_press(self, e):
        pid = self._cell_at(e.x, e.y)
        if pid is not None:
            self._drag_press(pid, e)

    def _party_press(self, e):
        pid = self._pslot_at(e.x, e.y)
        if pid is not None:
            self._drag_press(pid, e)

    def _pslot_at(self, x, y):
        for pid, (x1, y1, x2, y2) in self._pslots.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return pid
        return None

    def _row_at(self, e):
        """손가락 아래의 포켓몬 (파티 칸 또는 박스 칸). 기본 창의 끌기 코드가 부른다."""
        try:
            gx, gy = e.x_root - self.gcv.winfo_rootx(), e.y_root - self.gcv.winfo_rooty()
            if 0 <= gx <= self.gcv.winfo_width() and 0 <= gy <= self.gcv.winfo_height():
                return self._cell_at(gx, gy)
            sx, sy = e.x_root - self.cv.winfo_rootx(), e.y_root - self.cv.winfo_rooty()
            return self._pslot_at(sx, sy)
        except tk.TclError:
            return None

    def _show_line(self, pid):
        if pid != self._target:
            self._target = pid if pid != (self._drag or {}).get("pid") else None
            self._paint_grid()
            self._soon()

    def _hide_line(self):
        if self._target is not None:
            self._target = None
            self._paint_grid()
            self._soon()

    def _motion(self, e):
        if self._drag:
            return
        pid = None
        if e.widget is self.gcv:
            pid = self._cell_at(e.x, e.y)
        else:
            pid = self._pslot_at(e.x, e.y)
        self._set_hover(pid)

    def _set_hover(self, pid):
        if pid != self._hover:
            self._hover = pid
            self._paint_grid()
            self._soon()

    # ---------------- 판 전체 ----------------
    def _paint(self):
        self._job = None
        cv = self.cv
        try:
            W, H = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if W < 200 or H < 200:
            return
        cv.delete("scene")
        self._msg_ids = None
        s = U.h
        DW = s(self.DW_PX)
        self._place("detail", self.dframe, s(10), s(10), DW, H - s(20))
        self._paint_right(cv, DW + s(22), W - s(12), H)

    def _paint_right(self, cv, x0, x2, H):
        s = U.h
        y = s(10)
        # 1) 박스 이름 (◀ 이름 ▶) · 이름 바꾸기 · 새로고침
        bh = s(34)
        aw = s(36)
        self.btn_prev.layout(x0, y, x0 + aw, y + bh)
        nx1 = x0 + aw + s(6)
        nw = max(s(170), K.tkfont_of(cv, font(12)).measure(self._page_text) + s(40))
        nx2 = nx1 + nw
        K.rrect(cv, nx1, y, nx2, y + bh, 7, fill=PANEL, outline=LINE_D, width=2, tags=T + ("page",))
        cv.create_text((nx1 + nx2) // 2, y + bh // 2, text=self._page_text, fill=INK, font=font(12),
                       anchor="center", tags=T + ("page",))
        self._boxes["page"] = (nx1, y, nx2, y + bh)
        cv.tag_bind("page", "<Button-1>", lambda _e: self.open_box_menu())
        self._hand("page")
        self.btn_next.layout(nx2 + s(6), y, nx2 + s(6) + aw, y + bh)
        rw = self.btn_rename.want_width(s(20))
        rx = nx2 + s(12) + aw
        self.btn_rename.layout(rx, y + s(3), rx + rw, y + bh - s(3))
        bw = self.btn_reload.want_width(s(20))
        self.btn_reload.layout(x2 - bw, y + s(3), x2, y + bh - s(3))
        # 2) 타입 · 찾기 · 줄 세우기
        y += bh + s(8)
        th = s(30)
        tw = K.tkfont_of(cv, font(10)).measure(self.btn_type.text + " ▾") + s(24)
        K.rrect(cv, x0, y, x0 + tw, y + th, th // 2, fill=PANEL, outline=LINE, tags=T + ("tsel",))
        cv.create_text(x0 + tw // 2, y + th // 2, text=self.btn_type.text + " ▾", fill=INK, font=font(10),
                       anchor="center", tags=T + ("tsel",))
        self._boxes["type"] = (x0, y, x0 + tw, y + th)
        cv.tag_bind("tsel", "<Button-1>", lambda _e: self._open_type_menu())
        self._hand("tsel")
        right = K.tabs(cv, x2, y, th, SORTS, self.sort, "bsort", spec=font(10), align="right", tags=T)
        for key, _b in right:
            cv.tag_bind("bsort" + key, "<Button-1>", lambda _e, k=key: self.set_sort(k))
        self._hand("bsort")
        fx = x0 + tw + s(12)
        cv.create_text(fx, y + th // 2, text="찾기", fill=INK2, font=font(10), anchor="w", tags=T)
        fx += K.tkfont_of(cv, font(10)).measure("찾기") + s(8)
        self._place("find", self.find_box, fx, y, max(s(90), right[0][1][0] - fx - s(12)), th)
        # 3) 데리고 다니는 포켓몬 + 박스 칸
        y += th + s(10)
        BOT = s(92)
        gy2 = H - BOT
        PW = s(self.PARTY_PX)
        self._paint_party_slots(cv, x0, y, x0 + PW, gy2)
        gx1 = x0 + PW + s(10)
        K.panel(cv, gx1, y, x2, gy2, tags=T)
        self._place("grid", self.gframe, gx1 + 2, y + 2, x2 - gx1 - 4, gy2 - y - 4)
        # 4) 단추 줄 + 글상자
        by = gy2 + s(10)
        bh2 = s(34)
        if self.multi:
            btns = [self.btn_multi_move, self.btn_multi_release, self.btn_multi_all, self.btn_multi_clear,
                    self.btn_multi_done]
            hide = [self.btn_party, self.btn_nick, self.btn_move, self.btn_tint, self.btn_release]
        else:
            btns = [self.btn_party, self.btn_nick, self.btn_move, self.btn_tint, self.btn_release]
            hide = [self.btn_multi_move, self.btn_multi_release, self.btn_multi_all, self.btn_multi_clear,
                    self.btn_multi_done]
        for b in hide:
            b.hide()
        self._button_row(btns, x0, x2, by, by + bh2, s(24), s(6))
        text, color = self.msg
        shown = text or self._count_text
        tid = K.msgbox(cv, x0, by + bh2 + s(6), x2, H - s(8), shown,
                       (tone(color) if color else (INK if text else INK2)), tags=T)
        self._msg_ids = (None, tid)

    def _button_row(self, btns, x0, x2, y1, y2, pad, gap, first_pad=None):
        """단추 줄을 x0 부터 붙여 놓는다. x2 를 넘으면 단추 안 여백과 사이만 같은 비율로 줄인다 - 글씨는 그대로.

        여러 마리 고르기는 단추가 다섯이고 '놓아주기 (120마리)' 처럼 글이 길어서, 작은 창 · 큰 글자에서 판을 넘는다.
        자리가 넉넉하면 여백 · 사이가 그대로라 줄이 바뀌지 않는다.
        """
        pads = [pad] * len(btns)
        if btns and first_pad is not None:
            pads[0] = first_pad
        text = sum(b.want_width(0) for b in btns)
        give = sum(pads) + gap * max(0, len(btns) - 1)
        k = 1.0
        if give and text + give > x2 - x0:
            k = max(0.0, float(x2 - x0 - text) / give)
        x = x0
        for b, p in zip(btns, pads):
            w = b.want_width(0) + int(p * k)
            b.layout(x, y1, x + w, y2)
            x += w + int(gap * k)

    def _paint_party_slots(self, cv, x1, y1, x2, y2):
        """데리고 다니는 포켓몬 여섯 자리 (+ 위에 파티 고르기)."""
        s = U.h
        K.panel(cv, x1, y1, x2, y2, tags=T)
        hy = y1 + s(8)
        cv.create_text(x1 + s(10), hy + s(10), text="데리고 다니는", fill=INK2, font=font(9), anchor="w", tags=T)
        rows = self.party_presets()
        top = hy + s(24)
        if rows:
            name = next((p.get("name") or "파티 %d" % p.get("no") for p in rows if p.get("no") == self.party_active()),
                        "파티")
            pw = x2 - x1 - s(16)
            K.rrect(cv, x1 + s(8), top, x1 + s(8) + pw, top + s(26), s(13), fill=WIN_BG, outline=LINE,
                    tags=T + ("preset",))
            cv.create_text(x1 + s(8) + pw // 2, top + s(13), text=_clamp(cv, name, font(10), pw - s(30), 1) + " ▾",
                           fill=INK, font=font(10), anchor="center", tags=T + ("preset",))
            self._boxes["preset"] = (x1 + s(8), top, x1 + s(8) + pw, top + s(26))
            cv.tag_bind("preset", "<Button-1>", lambda _e: self._open_preset_menu())
            self._hand("preset")
            top += s(34)
        self.btn_party_name.hide()
        n = 6
        gap = s(4)
        sh = (y2 - top - s(8) - gap * (n - 1)) / float(n)
        self._pslots = {}
        for i in range(n):
            sy1 = top + i * (sh + gap)
            sy2 = sy1 + sh
            sx1, sx2 = x1 + s(6), x2 - s(6)
            m = self._party_list[i] if i < len(self._party_list) else None
            mid = (sy1 + sy2) / 2
            if m is None:
                K.rrect(cv, sx1, sy1, sx2, sy2, 6, fill="#f4f6f9", tags=T)
                cv.create_text((sx1 + sx2) / 2, mid, text="빈 자리", fill=DIM, font=font(9), tags=T)
                continue
            pid = m["id"]
            sel, tgt, chk = pid == self.sel, pid == self._target, pid in self.checked
            tg = T + ("pslot",)
            fill = SEL if sel else ("#e8f6e0" if chk else (HOV if pid == self._hover or tgt else PANEL))
            K.rrect(cv, sx1, sy1, sx2, sy2, 6, fill=fill, outline=CUR if (sel or tgt) else SEP,
                    width=2 if (sel or tgt) else 1, tags=tg)
            ph = self._thumb(m)
            if ph is not None:
                cv.create_image(sx1 + s(22), mid, image=ph, tags=tg)
            info = m.get("info") or {}
            name = "알" if m.get("isEgg") else info.get("name", m.get("species", "?"))
            if m.get("shiny"):
                name = "★" + name
            cv.create_text(sx1 + s(44), mid - s(8), text=_clamp(cv, name, font(10), sx2 - sx1 - s(50), 1),
                           fill=INK, font=font(10), anchor="w", tags=tg)
            cv.create_text(sx1 + s(44), mid + s(9), anchor="w", font=font(9), fill=INK2, tags=tg,
                           text=("%d%%" % box_filter.egg_progress(m.get("egg") or {})[0]) if m.get("isEgg")
                           else "Lv.%d" % m.get("level", 0))
            self._pslots[pid] = (sx1, sy1, sx2, sy2)
        self._hand("pslot")

    def _open_preset_menu(self):
        rows = []
        for p in self.party_presets():
            no = p.get("no")
            rows.append({"text": p.get("name") or "파티 %d" % no, "checked": no == self.party_active(),
                         "command": (lambda n=no: self.use_party(n))})
        rows.append(None)
        rows.append({"text": "지금 파티 이름 바꾸기…", "command": self.rename_party})
        return self._menu("preset", rows, below=True)

    # ---------------- 박스 칸 (6 × 5) ----------------
    def _paint_grid(self):
        cv = self.gcv
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w <= 1:
            return
        cv.delete("all")
        s = U.h
        cols = 6
        n = len(self._page_mons)
        rows = max(5, -(-n // cols))
        pad = s(6)
        cw = (w - pad) / float(cols)
        ch = max(s(56), (h - pad) / 5.0)
        total = max(h, int(ch * rows + pad))
        cv.configure(scrollregion=(0, 0, w, total))
        self._cells = {}
        for i in range(rows * cols):
            r, c = divmod(i, cols)
            x1, y1 = pad + c * cw, pad + r * ch
            x2, y2 = x1 + cw - pad, y1 + ch - pad
            if i >= n:
                K.rrect(cv, x1, y1, x2, y2, 6, fill="#f4f6f9")
                continue
            m = self._page_mons[i]
            pid = m["id"]
            sel, tgt, chk, hov = pid == self.sel, pid == self._target, pid in self.checked, pid == self._hover
            fill = SEL if sel else ("#e8f6e0" if chk else (HOV if (hov or tgt) else "#f4f6f9"))
            K.rrect(cv, x1, y1, x2, y2, 6, fill=fill, outline=CUR if sel else ("#f08020" if tgt else ""),
                    width=2 if (sel or tgt) else 1)
            ph = self._thumb(m)
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if ph is not None:
                cv.create_image(mx, my, image=ph)
            else:
                cv.create_oval(mx - 6, my - 6, mx + 6, my + 6, fill=PANEL, outline=LINE)
            if m.get("shiny"):
                cv.create_text(x1 + 5, y1 + 3, text="★", fill="#d0a000", font=font(9), anchor="nw")
            kind = None if m.get("isEgg") else L.kind_of(m.get("num"))
            if kind:
                cv.create_text(x2 - 4, y1 + 3, text="◆" if kind == "legendary" else "✦", fill="#a050c0",
                               font=font(8), anchor="ne")
            if m.get("away"):
                cv.create_text(mx, y2 - 3, text="탐험 중", fill="#2860c0", font=font(8), anchor="s")
            if chk:
                cv.create_text(x2 - 4, y2 - 2, text="✓", fill="#2c8a3c", font=font(12), anchor="se")
            self._cells[pid] = (x1, y1, x2, y2)
        # 마우스가 올라간 포켓몬의 이름
        m = self._by_id.get(self._hover) if self._hover else None
        box = self._cells.get(self._hover) if m is not None else None
        if box:
            info = m.get("info") or {}
            name = "알" if m.get("isEgg") else info.get("name", m.get("species", "?"))
            tip = "%s  Lv.%s" % (name, "-" if m.get("isEgg") else m.get("level", "?"))
            f = K.tkfont_of(cv, font(9))
            tw = f.measure(tip) + s(16)
            tx = min(max(tw / 2 + 2, (box[0] + box[2]) / 2), w - tw / 2 - 2)
            ty = max(s(22), box[1] - 2)
            K.rrect(cv, tx - tw / 2, ty - s(20), tx + tw / 2, ty, 5, fill=PANEL, outline=LINE_D, width=1)
            cv.create_text(tx, ty - s(10), text=tip, fill=INK, font=font(9))

    # ---------------- 요약 칸 ----------------
    def set_buttons(self, on):
        BX.BoxWindow.set_buttons(self, on)

    def show_detail(self, m):
        dex = self.app.dex
        info = m.get("info", {}) or {}
        d = {"m": m}
        if m.get("isEgg"):
            from ... import eggs_ui
            e = m.get("egg") or {}
            kind = e.get("kind")
            pct, _h = box_filter.egg_progress(e)
            need = max(1, int(e.get("needSec") or 1))
            got = max(0, min(need, int(e.get("gotSec") or 0)))
            d.update(egg=True, num="알", name=e.get("name") or "포켓몬 알", name_fg=BX._egg_color(kind),
                     gender="", lv="%d%%" % pct, sub=BX.EGG_SUB.get(kind, "무엇이 태어날까?"),
                     chips=[(BX.EGG_KIND.get(kind, "알"), BX._egg_color(kind))],
                     mood=eggs_ui.mood(e), ratio=got / float(need), egg_color=BX._egg_color(kind),
                     time="켜 둔 시간 %s / %s  (%d%%)" % (BX._hm(got), BX._hm(need), pct),
                     left=eggs_ui.hours_text(e.get("leftSec")),
                     where=("데리고 다니는 중 - 게임을 켜 둔 시간만큼 자랍니다." if e.get("onDesktop") else
                            natural("박스에 있어 자라지 않습니다. 데리고 다녀야 부화까지의 시간이 흐릅니다.")),
                     where_ok=bool(e.get("onDesktop")), day=BX._local_day(e.get("createdAt")))
            self._d = d
            self._egg_art(kind)
            return self._repaint_detail(top=True)
        sp = BX._species_of(dex, m)
        bits = [(sp or {}).get("kind", "")]
        if m.get("formKr"):
            bits.append(m["formKr"])
        if m.get("shiny"):
            bits.append("★ 색이 다른 개체")
        chips = [(dex.type_name(t), U.TYPE_COLOR.get(t, "#a0a0a8")) for t in (sp or {}).get("types", [])] if dex else []
        kind_ = L.kind_of(m.get("num"))
        if kind_:
            chips.append((BX.EGG_KIND[kind_], BX._egg_color(kind_)))
        hidden = info.get("hiddenAbility")
        held = m.get("held")
        # 경험치
        gotx, needx = info.get("expInLevel"), info.get("expToNext")
        if gotx is None or needx is None:
            exp = (0.0, "")
        elif not needx:
            exp = (1.0, "최대 레벨")
        else:
            exp = (max(0.0, min(1.0, gotx / float(needx))),
                   "%s / %s  ·  다음까지 %s" % (format(gotx, ","), format(needx, ","), format(max(0, needx - gotx), ",")))
        # 친밀도
        fr = m.get("friendship")
        friend = None
        if fr:
            now, need = fr["now"], fr["need"]
            hearts = int(round(5.0 * min(1.0, now / float(need or 1))))
            if now >= need:
                msg = "곧 진화합니다"
            elif fr["hours"] >= 1:
                msg = "%.0f시간쯤 더 데리고 다니면 진화합니다" % fr["hours"]
            else:
                msg = "조금만 더 데리고 다니면 진화합니다"
            if fr.get("luxury"):
                msg += "  (럭셔리볼 2배)"
            if fr.get("soothe"):
                msg += "  (평온의방울 1.5배)"
            friend = ("♥" * hearts + "♡" * (5 - hearts), "%d / %d" % (now, need), msg)
        # 능력치
        stats = info.get("stats", {})
        ivs = info.get("ivs") or m.get("ivs", {})
        evs = info.get("evs") or {}
        hyper = info.get("hyper") or {}
        mx = max(list(stats.values()) or [1])
        rows = []
        for k, label in BX.STAT_ROWS:
            iv = int(ivs.get(k, 0))
            rows.append((label, int(stats.get(k, 0)), iv, bool(hyper.get(k)), mx))
        bst = sum((sp or {}).get("base", {}).get(k, 0) for k in ("hp", "atk", "def", "spa", "spd", "spe"))
        ivsum = "종족값 %d  ·  개체값 %d / 186" % (bst, info.get("ivTotal", 0))
        if any(hyper.values()):
            ivsum += "   (✦ 병뚜껑으로 31 로 쳐줌)"
        gotev = [(lab, int(evs.get(k, 0))) for k, lab in BX.STAT_ROWS if evs.get(k)]
        if gotev:
            evsum = "노력치 %d / %d   ·   %s" % (info.get("evTotal", 0), P.EV_TOTAL_MAX,
                                              "  ".join("%s %d" % (lab, v) for lab, v in gotev))
        else:
            evsum = "노력치 0 / %d   ·   배틀에서 쓰러뜨리면 쌓입니다" % P.EV_TOTAL_MAX
        # 기술
        kr_moves = self._moves_by_kr(dex)
        shown_t = list(m.get("moveTypes") or [])
        moves = []
        for i, mv in enumerate((info.get("moves") or [])[:4]):
            md = kr_moves.get(mv) if dex else None
            if i < len(shown_t) and shown_t[i] and md:
                md = dict(md, type=shown_t[i])
            moves.append((mv, md))
        pending = [dex.move_name(x) if dex else x for x in (m.get("pending") or [])]
        lines = BX.evo_lines(dex, m, self._item_kr)
        if lines and self._item_kr is None and BX.evo_items(dex, m):
            self._load_item_names()
        d.update(egg=False, num="No.%04d" % m.get("num", 0), name=info.get("name", m["species"]),
                 name_fg="#fff4c0" if m.get("shiny") else "#ffffff", gender=U.gender_mark(m.get("gender")),
                 gender_fg=U.gender_color(m.get("gender")), lv="Lv.%d" % m["level"],
                 sub="  ·  ".join(x for x in bits if x.strip()), chips=chips,
                 ability=(info.get("ability") or "?") + ("  (숨은 특성)" if hidden else ""),
                 ability_note=natural(info.get("abilityNote") or "알려진 설명이 없습니다."),
                 nature=(info.get("nature") or "?") + " 성격",
                 nature_note=natural(info.get("natureNote") or "알려진 설명이 없습니다."),
                 held=held, held_text=((m.get("heldKr") or held) + ("\n" + m["heldDesc"] if m.get("heldDesc") else ""))
                 if held else "없음. 가방의 도구를 지니게 하면 배틀에서 효과가 납니다.",
                 exp=exp, friend=friend, evo=lines, rows=rows, ivsum=ivsum, evsum=evsum, moves=moves,
                 pending=natural("배우려던 기술: %s  ·  기술 떠올리기에서 무료로 배울 수 있습니다." % ", ".join(pending))
                 if pending else "")
        self.btn_unhold.configure(state="normal" if held else "disabled")
        self._d = d
        self._move_pick = None
        self.bond.show(m)
        self.load_art(m)
        self._repaint_detail(top=True)

    def _show_egg(self, m):
        return self.show_detail(m)

    def _egg_art(self, kind):
        from ... import eggs_ui
        self.stop_anim()
        self._art_gen += 1
        try:
            ph = item_icons.photo(eggs_ui.EGG_ITEM.get(kind, "LEGENDEGG"), BX.ART_H - 20)
        except Exception:                                   # noqa: BLE001
            ph = None
        self.d_art.configure(image=ph or "", text="" if ph else "알", fg=BX._egg_color(kind))

    def _evolution(self, m):
        """도구 이름을 받아 온 뒤 진화 칸을 다시 적는다 (기본 창의 _load_item_names 가 부른다)."""
        if self._d and self._d.get("m") is m and not self._d.get("egg"):
            self._d["evo"] = BX.evo_lines(self.app.dex, m, self._item_kr)
            self._repaint_detail()

    def pick_move(self, idx, md, name):
        self._move_pick = None if idx is None else (idx, md or {}, name)
        self._repaint_detail()

    def _bond_click(self):
        spec = self.bond.btn_spec
        if spec:
            self.bond.btn = self.btn_bond
            spec[1]()

    def _pick_dpage(self, key):
        if key != self._dpage:
            self._dpage = key
            self._move_pick = None
            self._repaint_detail(top=True)

    def _repaint_detail(self, top=False):
        if self._job_d is None:
            try:
                self._job_d = self.dcv.after_idle(lambda: self._paint_detail(top))
            except tk.TclError:
                pass

    def _paint_detail(self, top=False):
        """요약: 도트 · 이름 · 타입은 늘 위에, 그 아래는 쪽 하나 (정보 · 능력 · 기술 - DP 요약 화면처럼)."""
        self._job_d = None
        cv = self.dcv
        try:
            w, vh = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w <= 1:
            return
        cv.delete("all")
        for b in (self.btn_hold, self.btn_unhold, self.btn_remember, self.btn_bond):
            b.hide()
        s = U.h
        d = self._d
        x1, x2 = 0, w - s(2)
        if not d:
            cv.create_text(w // 2, s(80), text="포켓몬을 고르세요", fill=INK2, font=font(12), anchor="n", tags=D)
            return
        y = 0
        # 도트 무대
        sh = s(118)
        K.rrect(cv, x1, y, x2, y + sh, 8, fill="#f2f6fa", outline=LINE, tags=D)
        cv.create_oval(w // 2 - s(64), y + sh - s(30), w // 2 + s(64), y + sh - s(10), fill="#e2e9df",
                       outline="", tags=D)
        cv.create_text(x1 + s(10), y + s(8), text=d["num"], fill=INK2, font=font(9), anchor="nw", tags=D)
        a = cv.create_image(w // 2, y + sh // 2 + s(2), image=self.d_art.image or "", tags=D)
        b = cv.create_text(w // 2, y + sh // 2, text="" if self.d_art.image else self.d_art.text,
                           fill=tone(self.d_art.fg), font=font(11), tags=D)
        self.d_art.ids = (a, b)
        y += sh + s(8)
        # 이름 · 성별 · Lv
        t = cv.create_text(x1 + s(4), y + s(12), text=d["name"], fill="#b07800" if d["m"].get("shiny") else INK,
                           font=font(14), anchor="w", tags=D)
        bb = cv.bbox(t)
        if d.get("gender") and bb:
            cv.create_text(bb[2] + s(6), y + s(12), text=d["gender"], fill=d.get("gender_fg", INK2), font=font(12),
                           anchor="w", tags=D)
        cv.create_text(x2 - s(4), y + s(12), text=d["lv"], fill=INK, font=font(12), anchor="e", tags=D)
        y += s(28)
        if d.get("sub"):
            _a, t2 = K.text(cv, x1 + s(4), y, d["sub"], font(9), fill=INK2, tags=D, width=x2 - x1 - s(8))
            y = cv.bbox(t2)[3] + s(6)
        cx = x1 + s(4)
        for label, col in d.get("chips") or []:
            f = K.tkfont_of(cv, font(9))
            cw = f.measure(label) + s(16)
            K.rrect(cv, cx, y, cx + cw, y + s(22), 5, fill=col, tags=D)
            cv.create_text(cx + cw // 2, y + s(11), text=label, fill=K.look_of(col)[3], font=font(9),
                           anchor="center", tags=D)
            cx += cw + s(5)
        y += s(30)
        if d.get("egg"):
            y = self._d_egg(cv, d, x1, x2, y)
        else:
            pages = [("info", "정보"), ("stats", "능력"), ("moves", "기술")]
            if self.bond.visible:
                pages.append(("mega", "메가진화"))
            if self._dpage not in dict(pages):
                self._dpage = "info"
            K.tabs(cv, x1, y, s(30), pages, self._dpage, "dpg", spec=font(11), tags=D)
            for key, _lb in pages:
                cv.tag_bind("dpg" + key, "<Button-1>", lambda _e, k=key: self._pick_dpage(k))
                cv.tag_bind("dpg" + key, "<Enter>", lambda _e: cv.configure(cursor="hand2"))
                cv.tag_bind("dpg" + key, "<Leave>", lambda _e: cv.configure(cursor=""))
            y += s(30)
            cv.create_line(x1, y, x2, y, fill=LINE, tags=D)
            y += s(10)
            y = {"info": self._d_info, "stats": self._d_stats, "moves": self._d_moves,
                 "mega": self._d_bond}[self._dpage](cv, d, x1 + s(4), x2 - s(4), y)
        total = y + s(12)
        cv.configure(scrollregion=(0, 0, w, max(total, vh)))
        if top:
            cv.yview_moveto(0)
        for b in (self.btn_hold, self.btn_unhold, self.btn_remember, self.btn_bond):
            if b.box:
                b.draw()

    def _wrap(self, cv, x, y, text, spec, fill=INK, width=100):
        t = cv.create_text(x, y, text=K.wrap(cv, text, spec, width), fill=fill, font=spec, anchor="nw", tags=D)
        b = cv.bbox(t)
        return b[3] if b else y

    def _label(self, cv, x, y, text):
        cv.create_text(x, y, text=text, fill=TAGC, font=font(9), anchor="nw", tags=D)

    def _d_info(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        for title, name, note in (("특성", d["ability"], d["ability_note"]), ("성격", d["nature"], d["nature_note"])):
            self._label(cv, x1, y, title)
            y = self._wrap(cv, x1 + s(40), y, name, font(10), width=iw - s(40))
            y = self._wrap(cv, x1 + s(40), y + 2, note, font(9), fill=INK2, width=iw - s(40)) + s(10)
        # 지닌 도구
        self._label(cv, x1, y, "도구")
        bw1, bw2 = self.btn_hold.want_width(s(14)), self.btn_unhold.want_width(s(14))
        self.btn_unhold.layout(x2 - bw2, y - s(4), x2, y + s(20))
        self.btn_hold.layout(x2 - bw2 - s(6) - bw1, y - s(4), x2 - bw2 - s(6), y + s(20))
        y += s(24)
        tx = x1 + s(40)
        if d["held"]:
            ph = item_icons.photo(d["held"], 24)
            if ph is not None:
                cv.create_image(x1 + s(14), y + s(10), image=ph, tags=D)
        y = self._wrap(cv, tx, y, d["held_text"], font(9), fill=INK if d["held"] else INK2, width=iw - s(40)) + s(10)
        # 경험치
        ratio, text = d["exp"]
        self._label(cv, x1, y, "경험치")
        cv.create_text(x2, y, text=text, fill=INK2, font=font(8), anchor="ne", tags=D)
        y += s(18)
        cv.create_rectangle(x1, y, x2, y + s(8), fill="#dde2e8", outline="", tags=D)
        fw = int((x2 - x1) * ratio)
        if fw > 0:
            cv.create_rectangle(x1, y, x1 + fw, y + s(8), fill="#3a9ae8", outline="", tags=D)
        y += s(16)
        if d.get("friend"):
            hearts, num, msg = d["friend"]
            self._label(cv, x1, y, "친밀도")
            cv.create_text(x1 + s(48), y - 1, text=hearts, fill="#e04888", font=font(10), anchor="nw", tags=D)
            cv.create_text(x2, y, text=num, fill=INK2, font=font(9), anchor="ne", tags=D)
            y = self._wrap(cv, x1, y + s(18), msg, font(9), fill=INK2, width=iw) + s(10)
        if d.get("evo"):
            self._label(cv, x1, y, "진화")
            y += s(18)
            for line in d["evo"]:
                y = self._wrap(cv, x1, y, line, font(9), width=iw) + s(3)
        return y

    def _d_stats(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        y = self._wrap(cv, x1, y, d["ivsum"], font(9), fill="#2c8a3c", width=iw) + s(8)
        for label, v, iv, hy, mx in d["rows"]:
            cv.create_text(x1, y, text=label, fill=INK2, font=font(9), anchor="nw", tags=D)
            cv.create_text(x1 + s(84), y, text=str(v), fill=INK, font=font(10), anchor="ne", tags=D)
            bx1, bx2 = x1 + s(92), x2 - s(66)
            cv.create_rectangle(bx1, y + 4, bx2, y + s(12), fill="#dde2e8", outline="", tags=D)
            col = "#3cb868" if iv == 31 else ("#f0a020" if iv >= 26 else "#9aa2b0")
            fw = int((bx2 - bx1) * v / float(mx or 1))
            if fw > 0:
                cv.create_rectangle(bx1, y + 4, bx1 + fw, y + s(12), fill=col, outline="", tags=D)
            cv.create_text(x2, y, text="개체 %d%s" % (iv, "✦" if hy else ""),
                           fill="#2c8a3c" if iv == 31 else INK2, font=font(8), anchor="ne", tags=D)
            y += s(22)
        y = self._wrap(cv, x1, y + s(4), d["evsum"], font(9), fill=INK2, width=iw)
        return y

    def _d_moves(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        dex = self.app.dex
        mh = s(44)
        for i, (mv, md) in enumerate(d["moves"]):
            col = U.TYPE_COLOR.get((md or {}).get("type"), "#a0a0a8")
            tg = D + ("mv%d" % i,)
            picked = bool(self._move_pick and self._move_pick[0] == i)
            K.rrect(cv, x1, y, x2, y + mh, 7, fill=SEL if picked else PANEL, outline=CUR if picked else LINE,
                    width=2 if picked else 1, tags=tg)
            cv.create_rectangle(x1 + s(6), y + s(8), x1 + s(10), y + mh - s(8), fill=col, outline="", tags=tg)
            cv.create_text(x1 + s(20), y + s(14), text=mv, fill=INK, font=font(11), anchor="w", tags=tg)
            sub = "%s · %s" % (dex.type_name((md or {}).get("type")) if dex else "", MT.short_line(md))
            cv.create_text(x1 + s(20), y + mh - s(12), text=sub, fill=INK2, font=font(9), anchor="w", tags=tg)
            cv.tag_bind("mv%d" % i, "<Button-1>", lambda _e, n=i, dd=md, t=mv: self.pick_move(n, dd, t))
            cv.tag_bind("mv%d" % i, "<Enter>", lambda _e: cv.configure(cursor="hand2"))
            cv.tag_bind("mv%d" % i, "<Leave>", lambda _e: cv.configure(cursor=""))
            y += mh + s(6)
        if self._move_pick:
            _i, md, name = self._move_pick
            y = self._wrap(cv, x1, y + s(2), MT.stat_line(md, name or "?"), font(9), fill="#b05a10", width=iw)
            y = self._wrap(cv, x1, y + s(2), MT.desc(md), font(9), fill=INK2, width=iw) + s(6)
        if d.get("pending"):
            y = self._wrap(cv, x1, y + s(2), d["pending"], font(9), fill="#2c8a3c", width=iw) + s(6)
        rw = self.btn_remember.want_width(s(20))
        self.btn_remember.layout(x2 - rw, y + s(4), x2, y + s(32))
        return y + s(36)

    def _d_bond(self, cv, d, x1, x2, y):
        s = U.h
        iw = x2 - x1
        b = self.bond
        if b.btn_spec:
            self.btn_bond.configure(text=b.btn_spec[0], state="normal")
            bw = self.btn_bond.want_width(s(20))
            self.btn_bond.layout(x2 - bw, y, x2, y + s(28))
            y += s(36)
        for row in b.lines:
            if row[0] == "kv":
                _k, label, val, col = row
                self._label(cv, x1, y, label)
                y = self._wrap(cv, x1 + s(48), y, val, font(9), fill=tone(col) if col != BD.MEGA else "#7a4ad0",
                               width=iw - s(48)) + s(4)
            elif row[0] == "bar":
                _k, label, num, ratio, col = row
                y2 = self._wrap(cv, x1, y, label, font(9), width=iw - s(60))
                cv.create_text(x2, y, text=num, fill=INK2, font=font(8), anchor="ne", tags=D)
                cv.create_rectangle(x1, y2 + 3, x2, y2 + s(10), fill="#dde2e8", outline="", tags=D)
                fw = int((x2 - x1) * min(1.0, ratio))
                if fw > 0:
                    cv.create_rectangle(x1, y2 + 3, x1 + fw, y2 + s(10), fill=col, outline="", tags=D)
                y = y2 + s(16)
            else:
                _k, text, col = row
                y = self._wrap(cv, x1, y, text, font(9), fill="#7a4ad0" if col == BD.MEGA else tone(col),
                               width=iw) + s(4)
        dex = self.app.dex
        for pv in b.previews:
            cv.create_line(x1, y + s(4), x2, y + s(4), fill=SEP, tags=D)
            y += s(12)
            t = cv.create_text(x1, y, text=pv["name"], fill="#7a4ad0", font=font(11), anchor="nw", tags=D)
            bb = cv.bbox(t)
            cv.create_text((bb[2] if bb else x1) + s(8), y + 2, text="메가진화하면", fill=INK2, font=font(8),
                           anchor="nw", tags=D)
            y += s(22)
            cx = x1
            for tp in pv["types"]:
                label = dex.type_name(tp) if dex else tp
                f = K.tkfont_of(cv, font(8))
                cw = f.measure(label) + s(14)
                col = U.TYPE_COLOR.get(tp, "#a0a0a8")
                K.rrect(cv, cx, y, cx + cw, y + s(18), 4, fill=col, tags=D)
                cv.create_text(cx + cw // 2, y + s(9), text=label, fill=K.look_of(col)[3], font=font(8),
                               anchor="center", tags=D)
                cx += cw + s(4)
            y += s(24)
            if pv.get("abilityKr"):
                y = self._wrap(cv, x1, y, "특성 %s (%s)" % (pv["abilityKr"], "바뀜" if pv["abilityChanged"] else "그대로"),
                               font(9), width=iw) + s(2)
            for _k, label, now, after, dlt in pv["rows"]:
                cv.create_text(x1, y, text=label, fill=INK2, font=font(8), anchor="nw", tags=D)
                cv.create_text(x1 + s(110), y, text="%d → %d" % (now, after), fill=INK if dlt else DIM,
                               font=font(8), anchor="ne", tags=D)
                cv.create_text(x2, y, text=BD.delta_text(dlt),
                               fill="#2c8a3c" if dlt > 0 else ("#d02828" if dlt < 0 else DIM), font=font(8),
                               anchor="ne", tags=D)
                y += s(16)
        return y

    def _d_egg(self, cv, d, x1, x2, y):
        s = U.h
        x1, x2 = x1 + s(4), x2 - s(4)
        iw = x2 - x1
        self._label(cv, x1, y, "알의 상태")
        y = self._wrap(cv, x1, y + s(18), d["mood"], font(9), width=iw) + s(6)
        cv.create_rectangle(x1, y, x2, y + s(8), fill="#dde2e8", outline="", tags=D)
        fw = int((x2 - x1) * d["ratio"])
        if fw > 0:
            cv.create_rectangle(x1, y, x1 + fw, y + s(8), fill=d["egg_color"], outline="", tags=D)
        y += s(14)
        y = self._wrap(cv, x1, y, d["time"], font(9), fill=INK2, width=iw) + s(4)
        y = self._wrap(cv, x1, y, d["left"], font(10), width=iw) + s(10)
        self._label(cv, x1, y, "자라는 곳")
        y = self._wrap(cv, x1, y + s(18), d["where"], font(9), fill="#2c8a3c" if d["where_ok"] else "#d02828",
                       width=iw) + s(4)
        y = self._wrap(cv, x1, y, natural("알도 데리고 다니는 여섯 자리 중 하나를 차지합니다. 알을 데리고 다니는 동안에는 "
                                          "포켓몬이 그만큼 적게 따라다닙니다."), font(8), fill=DIM, width=iw) + s(4)
        if d.get("day"):
            y = self._wrap(cv, x1, y, "받은 날 %s" % d["day"], font(8), fill=DIM, width=iw)
        return y


# ---------------------------------------------------------------- 지닌 도구 고르기
# 지닌 도구 고르기 창(HeldPicker)은 held.py 로 옮겼다 - 스킨은 이 모듈에서 HeldPicker 를 찾으므로 다시 내보낸다.
# _clamp 도 같이: 위 BoxWindow 가 이 모듈의 _clamp 를 쓴다 (예전에 이 자리에 있던 것).
from .held import HeldPicker, _clamp  # noqa: E402,F401
