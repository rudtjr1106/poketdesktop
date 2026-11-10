# -*- coding: utf-8 -*-
"""아르케의 여섯 봉인 (2.4.0) 서버. 서버를 띄우지 않는다.

    python server/test_arche.py

설계 design-notes/2026-11-09-arche.md · 계획 2026-11-09-arche-plan.md (Task 2 · 4).
**비공개 secrets.json 은 여기서 지어낸 값으로 임시로 만든다** - 진짜 수수께끼 · 정답은 저장소에 없다.

    준비 안 됨 (파일 없음 · 깨짐) · 다시 읽기 (mtime) · 장 경계 · 열쇠 (맞음 · 틀림 · 정규화 · 시간당 20번) ·
    조건 종류마다 참/거짓 · 의식 (첫 사람 · 칭호 · 장이 닫힌 뒤 · 닫힌 장의 전설은 이벤트 끝까지) · 현상 창 ·
    제목 해시 · 게시글 (한 번만 · 실마리 사다리 · NPC) · 숨은 페이지 · 장 선물 ·
    발굴지 (기간 · 보고서) · 열쇠 아이템 (설명 덮기 · 쓰기) · 서로 놀러 가기
"""
import datetime
import io
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="poket-arche-")
ARCHE_DIR = os.path.join(TMP, "arche")
os.environ["POKET_DB"] = os.path.join(TMP, "t.db")
os.environ.pop("POKET_TURSO_URL", None)
os.environ["POKET_POKEDEX"] = os.path.join(HERE, "data", "pokedex.json")
os.environ["POKET_ITEMS"] = os.path.join(HERE, "data", "items.json")
os.environ["POKET_ARCHE_DIR"] = ARCHE_DIR
os.environ["POKET_BOARD_IMG_DIR"] = os.path.join(TMP, "board_img")
os.environ["POKET_BOARD_ADMINS"] = "시험운영자"
os.environ["POKET_ARCHE_START"] = "2026-11-15"     # 검사는 날짜를 박아 둔다 (기본 날이 바뀌어도 그대로)

from fastapi import HTTPException                            # noqa: E402

from common import arche as A                                # noqa: E402
from common import expedition as X                           # noqa: E402
from common import pokelogic as P                            # noqa: E402
from app import arche as AR                                  # noqa: E402
from app import arche_routes                                 # noqa: E402
from app import auth, db, deps, expedition, item_routes, items, season, visit   # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc
KST = datetime.timezone(datetime.timedelta(hours=9))
OPEN1 = datetime.datetime(2026, 11, 14, 15, 0, tzinfo=UTC)       # 1장 열림 (11/15 0시 KST)


def kst(mo, d, h, mi=0, s=0):
    return datetime.datetime(2026, mo, d, h, mi, s, tzinfo=KST).astimezone(UTC)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def refused(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except HTTPException as e:
        return e.status_code, str(e.detail)
    return None


_n = [0]


def mkuser(name=None):
    _n[0] += 1
    cur = db.run(
        "INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money,"
        " created_at, last_login, last_ip) VALUES (?,?,?,1,10,0,'2026-10-01T00:00:00+00:00','','')",
        (name or "아르케%d" % _n[0], b"x", b"x"))
    return cur.lastrowid


def user(uid):
    return db.q1("SELECT * FROM users WHERE id=?", (uid,))


def mkmon(uid, species="PIKACHU", level=30, seed=3, desk=True, slot=None, held=None):
    m = P.make_pokemon(deps.dex().get(species), level, random.Random(seed), force_shiny=False)
    m["held"] = held
    pid = db.insert_mon(uid, m, "")
    db.run("UPDATE pokemon SET on_desktop=?, slot=? WHERE id=?", (1 if desk else 0, slot, pid))
    return pid


# 지어낸 비공개 자료 (모양만 진짜와 같다)
SECRETS = {
    "salt": "시험소금-열여섯-글자보다-훨씬-길게-적는다", "npc": "시험고고학자",
    "chapters": {
        "1": {
            "minClient": "2.4.0",
            "journal": [{"after": 0, "text": "첫 일지 글"}, {"after": 5, "text": "다섯 시간 뒤 글"}],
            "hints": [{"after": 18, "minSolvers": 3, "text": "실마리 하나"},
                      {"after": 30, "minSolvers": 1, "text": "실마리 둘"},
                      {"after": 40, "minSolvers": 30, "text": "실마리 셋"}],
            "inscription": "시험 새김글", "photo": "cave",
            "keys": {"k1": {"answers": ["푸른 사과가 바다 위로 떠오른다"], "title": True},
                     "k2": {"answers": ["노란 바나나", "바나나"]}},
            "ritual": {"all": [{"key": "k1"}, {"time": ["23:50", "05:30"]}]},
            "phenomena": [
                {"id": "p-now", "at": "2026-11-15T03:00:00+09:00", "dur": 40, "kind": "unown", "data": {"glyph": 2}},
                {"id": "p-long", "at": "2026-11-15T02:58:00+09:00", "dur": 300, "kind": "stars", "data": {}},
                {"id": "p-later", "at": "2026-11-15T03:10:00+09:00", "dur": 40, "kind": "relic", "data": {}},
                {"id": "p-old", "at": "2026-11-15T02:00:00+09:00", "dur": 40, "kind": "drip", "data": {}}],
            "items": {"ARCHESTONE": "시험 설명 하나"}, "gift": ["ARCHESTONE"],
            "dig": {"0-6": "새벽 보고서", "22-2": "자정 무렵 보고서", "12": "정오 보고서", "*": "보통 보고서"},
            "post": {"title": "시험 일지 1", "images": ["t1.png"]}, "pages": ["abc-12"],
        },
        "2": {"journal": [{"after": 0, "text": "둘째 장 글"}], "pages": ["def-34"], "images": ["t2.png"],
              "keys": {"k9": {"answers": ["불꽃"]}}, "ritual": {"key": "k9"},
              "items": {"ARCHESTONE": "둘째 장 설명"}, "post": {"title": "시험 일지 2"}},
        "6": {"keys": {"z": {"answers": ["끝"]}}, "ritual": {"key": "z"}},
    },
}


def write_secrets(obj=None, raw=None, bump=0):
    os.makedirs(ARCHE_DIR, exist_ok=True)
    path = os.path.join(ARCHE_DIR, "secrets.json")
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(raw if raw is not None else json.dumps(obj, ensure_ascii=False))
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + bump * 1000000000))


def drop_secrets():
    try:
        os.remove(os.path.join(ARCHE_DIR, "secrets.json"))
    except OSError:
        pass


def ch(state, n):
    return state["chapters"][n - 1]


# ---------------------------------------------------------------- 준비 안 됨
def t_준비_안_됨():
    print("[secrets 없음 · 깨짐]")
    u = mkuser()
    drop_secrets()
    st = AR.state(u, now=OPEN1 + datetime.timedelta(hours=1))
    chk("파일 없음: ready False · 장 여섯 · 500 없음", st["ready"] is False and len(st["chapters"]) == 6
        and st["active"] and st["chapter"] == 1 and st["phenomena"] == [], st)
    chk("파일 없음: 일지 · 열쇠는 비어 있다", not ch(st, 1)["journal"] and not ch(st, 1).get("titleHashes"))
    card = AR.me_card(u, now=OPEN1 + datetime.timedelta(hours=1))
    chk("파일 없음: /api/me 카드도 ready False", card and card["ready"] is False and card["active"], card)
    chk("이벤트 열흘 전에는 카드가 None (질의 없음)", AR.me_card(u, now=OPEN1 - datetime.timedelta(days=10)) is None)
    chk("이벤트 이틀 뒤에는 카드가 None", AR.me_card(u, now=A.event_window()[1] + datetime.timedelta(days=2)) is None)
    chk("파일 없음: 열쇠는 409", (refused(AR.submit_key, u, 1, "아무 말", "type",
                                     now=OPEN1 + datetime.timedelta(hours=1)) or (0,))[0] == 409)
    write_secrets(raw="{깨진 json", bump=1)
    st = AR.state(u, now=OPEN1 + datetime.timedelta(hours=1))
    chk("깨진 파일: ready False · 500 없음", st["ready"] is False, st["ready"])
    write_secrets(raw=json.dumps({"salt": "x"}), bump=2)
    chk("chapters 가 없는 파일: ready False", AR.state(u, now=OPEN1)["ready"] is False)
    chk("_arche_card 감싸개가 터져도 None", _card_wrapper_ok())


def _card_wrapper_ok():
    from app import main
    old = AR.me_card
    try:
        def boom(*_a, **_k):
            raise RuntimeError("시험")
        AR.me_card = boom
        return main._arche_card(1) is None
    finally:
        AR.me_card = old


# ---------------------------------------------------------------- 다시 읽기 · 장 경계
def t_다시_읽기_장_경계():
    print("[다시 읽기 · 장 경계]")
    u = mkuser()
    write_secrets(SECRETS, bump=3)
    st = AR.state(u, now=OPEN1 - datetime.timedelta(seconds=1))
    chk("열리기 1초 전: active False · 장 0 · 1장 future", not st["active"] and st["chapter"] == 0
        and ch(st, 1)["future"] and not ch(st, 1)["open"], (st["chapter"], ch(st, 1)))
    chk("미래 장은 일지 · 새김글 · 사진이 없다", not ch(st, 1).get("journal") and "inscription" not in ch(st, 1)
        and ch(st, 1)["title"] == "돌의 문" and ch(st, 1)["place"] == "cave")
    st = AR.state(u, now=OPEN1)
    c1 = ch(st, 1)
    chk("열린 순간: 1장 open · ready True · 폴링 60", st["ready"] and st["chapter"] == 1 and c1["open"]
        and st["poll"] == 60, st["chapter"])
    chk("일지는 after 0 것만", [j["text"] for j in c1["journal"]] == ["첫 일지 글"], c1["journal"])
    chk("새김글 · 사진 · minClient", c1["inscription"] == "시험 새김글" and c1["photo"] == "cave"
        and c1["minClient"] == "2.4.0", c1)
    chk("일지 시각은 열림 + after", c1["journal"][0]["at"] == OPEN1.isoformat(), c1["journal"][0])
    st = AR.state(u, now=OPEN1 + datetime.timedelta(hours=5))
    chk("다섯 시간 뒤 글이 올라온다", [j["text"] for j in ch(st, 1)["journal"]] == ["첫 일지 글", "다섯 시간 뒤 글"])
    chk("2장은 아직 future", ch(st, 2)["future"] and not ch(st, 2).get("journal"))
    st = AR.state(u, now=A.window(2)[0])
    chk("1장이 닫힌 순간 = 2장 open · 1장 past (일지 그대로)", st["chapter"] == 2 and ch(st, 1)["past"]
        and ch(st, 2)["open"] and len(ch(st, 1)["journal"]) == 2, (st["chapter"], ch(st, 1)["past"]))
    # 운영자가 고치면 다음 요청 때
    s2 = json.loads(json.dumps(SECRETS))
    s2["chapters"]["1"]["inscription"] = "고친 새김글"
    write_secrets(s2, bump=4)
    chk("운영자가 고친 파일을 다음 요청에 읽는다 (mtime)", ch(AR.state(u, now=OPEN1), 1)["inscription"] == "고친 새김글")
    write_secrets(SECRETS, bump=5)


# ---------------------------------------------------------------- 열쇠
def t_열쇠():
    print("[열쇠]")
    now = kst(11, 15, 12, 0)                       # 의식 시각(23:50~05:30) 밖 - 여기서는 의식이 안 된다
    u = mkuser()
    out = AR.submit_key(u, 1, "초록 사과", "type", now=now)
    chk("틀린 말: ok False · 열쇠 없음", out["ok"] is False and not ch(out["state"], 1)["keys"], out.get("message"))
    out = AR.submit_key(u, 1, "  푸른, 사과가 바다 위로   떠오른다!! ", "type", now=now)
    chk("맞는 말 (공백 · 문장부호 달라도): ok · k1", out["ok"] and out["key"] == "k1"
        and ch(out["state"], 1)["keys"] == ["k1"], out)
    chk("적은 길이 남는다 (via)", db.q1("SELECT via FROM arche_key WHERE user_id=? AND key='k1'", (u,))["via"] == "type")
    out = AR.submit_key(u, 1, "바나나", "title", now=now)
    chk("답이 여럿인 열쇠 · 창 제목으로", out["ok"] and out["key"] == "k2"
        and db.q1("SELECT via FROM arche_key WHERE user_id=? AND key='k2'", (u,))["via"] == "title")
    out = AR.submit_key(u, 1, "푸른사과가바다위로떠오른다", "type", now=now)
    chk("이미 알아낸 말: ok · new False", out["ok"] and out["new"] is False, out)
    chk("빈 말은 400", (refused(AR.submit_key, u, 1, " !? ", "type", now=now) or (0,))[0] == 400)
    chk("모르는 장은 400", (refused(AR.submit_key, u, 9, "푸른 사과가 바다 위로 떠오른다", "type", now=now) or (0,))[0] == 400)
    chk("열리지 않은 장(2장)은 409", (refused(AR.submit_key, u, 2, "불꽃", "type", now=now) or (0,))[0] == 409)
    chk("다른 장의 답은 이 장 열쇠가 아니다", AR.submit_key(u, 1, "불꽃", "type", now=now)["ok"] is False)
    # 시간당 20번
    v = mkuser()
    for i in range(20):
        AR.submit_key(v, 1, "아무말%d" % i, "type", now=now + datetime.timedelta(seconds=i))
    got = refused(AR.submit_key, v, 1, "푸른 사과가 바다 위로 떠오른다", "type", now=now + datetime.timedelta(minutes=5))
    chk("21번째는 맞는 말이어도 429", got and got[0] == 429, got)
    chk("429 뒤에는 열쇠가 안 들어갔다", db.q1("SELECT COUNT(*) c FROM arche_key WHERE user_id=?", (v,))["c"] == 0)
    out = AR.submit_key(v, 1, "푸른 사과가 바다 위로 떠오른다", "type", now=now + datetime.timedelta(minutes=61))
    chk("한 시간 지나면 다시 적을 수 있다", out["ok"], out.get("message"))


# ---------------------------------------------------------------- 조건
def t_조건():
    print("[조건 종류]")
    now = OPEN1 + datetime.timedelta(hours=3)
    u = mkuser()
    db.run("INSERT INTO arche_key (user_id, chapter, key, via, at) VALUES (?,1,'k1','type',?)", (u, now.isoformat()))
    chk("key 참", AR._cond(u, 1, {"key": "k1"}, now))
    chk("key 거짓 (안 알아낸 것)", not AR._cond(u, 1, {"key": "k2"}, now))
    chk("key 거짓 (다른 장)", not AR._cond(u, 2, {"key": "k1"}, now))
    t = kst(11, 15, 5, 10)
    chk("time 안", AR._cond(u, 1, {"time": ["05:00", "05:30"]}, t))
    chk("time 끝은 안 든다", not AR._cond(u, 1, {"time": ["05:00", "05:10"]}, t))
    chk("time 자정 넘김 (23:50~00:20) 00:05", AR._cond(u, 1, {"time": ["23:50", "00:20"]}, kst(11, 16, 0, 5)))
    chk("time 자정 넘김 23:55", AR._cond(u, 1, {"time": ["23:50", "00:20"]}, kst(11, 15, 23, 55)))
    # when: 날짜까지 정한 구간 목록 (날마다 다른 정한 때) - 하나라도 들면 참, 끝은 안 든다
    spans = [["2026-11-15T10:00:00+09:00", "2026-11-15T10:40:00+09:00"],
             ["2026-11-16T11:00:00+09:00", "2026-11-16T11:40:00+09:00"]]
    chk("when 첫 구간 안", AR._cond(u, 1, {"when": spans}, kst(11, 15, 10, 20)))
    chk("when 둘째 구간 안", AR._cond(u, 1, {"when": spans}, kst(11, 16, 11, 39)))
    chk("when 끝은 안 든다 · 다른 날 같은 시각은 아니다", not AR._cond(u, 1, {"when": spans}, kst(11, 15, 10, 40))
        and not AR._cond(u, 1, {"when": spans}, kst(11, 16, 10, 20)))
    chk("when 깨진 값은 거짓 (500 아님)", not AR._cond(u, 1, {"when": [["아무거나"], None, 3]}, kst(11, 15, 10, 20)))
    chk("time 자정 넘김 밖 (12:00)", not AR._cond(u, 1, {"time": ["23:50", "00:20"]}, kst(11, 15, 12, 0)))
    # 파티: 슬롯 차례
    mkmon(u, "GEODUDE", 20, seed=1, slot=2)        # 바위 · 땅
    mkmon(u, "SNORUNT", 20, seed=2, slot=0)        # 얼음
    mkmon(u, "MAGNEMITE", 20, seed=3, slot=1, held="LEFTOVERS")      # 전기 · 강철
    mkmon(u, "ONIX", 20, seed=4, desk=False)       # 박스 - 안 센다
    chk("partyTypes 슬롯 차례 (얼음 · 강철 · 바위)", AR._cond(u, 1, {"partyTypes": ["ICE", "STEEL", "ROCK"]}, now))
    chk("partyTypes 순서가 다르면 거짓", not AR._cond(u, 1, {"partyTypes": ["ROCK", "ICE", "STEEL"]}, now))
    chk("partyTypes 앞에서부터 (얼음 하나)", AR._cond(u, 1, {"partyTypes": ["ICE"]}, now))
    chk("partyTypes 파티보다 길면 거짓", not AR._cond(u, 1, {"partyTypes": ["ICE", "STEEL", "ROCK", "ROCK"]}, now))
    chk("partyHas 바위 1", AR._cond(u, 1, {"partyHas": {"type": "ROCK", "count": 1}}, now))
    chk("partyHas 바위 2 (박스는 안 센다) 거짓", not AR._cond(u, 1, {"partyHas": {"type": "ROCK", "count": 2}}, now))
    chk("partyHas 도구", AR._cond(u, 1, {"partyHas": {"held": "LEFTOVERS"}}, now))
    chk("partyHas 없는 도구 거짓", not AR._cond(u, 1, {"partyHas": {"held": "CHOICESCARF"}}, now))
    # 아이템 쓰기
    chk("itemUsed 아직 거짓", not AR._cond(u, 1, {"itemUsed": {"item": "ARCHESTONE", "withinMin": 10}}, now))
    db.run("INSERT INTO arche_use (user_id, item, at) VALUES (?,?,?)",
           (u, "ARCHESTONE", (now - datetime.timedelta(minutes=5)).isoformat()))
    chk("itemUsed 5분 전 · 10분 안 참", AR._cond(u, 1, {"itemUsed": {"item": "ARCHESTONE", "withinMin": 10}}, now))
    chk("itemUsed 3분 안 거짓", not AR._cond(u, 1, {"itemUsed": {"item": "ARCHESTONE", "withinMin": 3}}, now))
    # 집중 한 번에 N세트
    for i in range(3):
        db.run("INSERT INTO focus_set (user_id, run_id, pokemon_id, stat, at, day, minutes, full, ev)"
               " VALUES (?,?,?,?,?,?,25,1,0)", (u, 77, 1, "atk",
                                                 (OPEN1 + datetime.timedelta(minutes=30 * (i + 1))).isoformat(), "2026-11-15"))
    db.run("INSERT INTO focus_set (user_id, run_id, pokemon_id, stat, at, day, minutes, full, ev)"
           " VALUES (?,?,?,?,?,?,25,1,0)", (u, 76, 1, "atk",
                                             (OPEN1 - datetime.timedelta(minutes=30)).isoformat(), "2026-11-14"))
    db.run("INSERT INTO focus_set (user_id, run_id, pokemon_id, stat, at, day, minutes, full, ev)"
           " VALUES (?,?,?,?,?,?,10,0,0)", (u, 77, 1, "atk",
                                             (OPEN1 + datetime.timedelta(minutes=100)).isoformat(), "2026-11-15"))
    chk("focusRun 같은 집중 3세트 참", AR._cond(u, 1, {"focusRun": {"sets": 3}}, now))
    chk("focusRun 4세트 거짓 (자투리 · 장 열리기 전 세트는 안 센다)", not AR._cond(u, 1, {"focusRun": {"sets": 4}}, now))
    # 서로 놀러 가기
    w = mkuser()
    visit.log_visit(u, w, now - datetime.timedelta(minutes=20))
    chk("visitMutual 한쪽만 거짓", not AR._cond(u, 1, {"visitMutual": {"withinMin": 30}}, now))
    visit.log_visit(w, u, now - datetime.timedelta(minutes=5))
    chk("visitMutual 서로 30분 안 참", AR._cond(u, 1, {"visitMutual": {"withinMin": 30}}, now))
    chk("visitMutual 상대 쪽에서도 참", AR._cond(w, 1, {"visitMutual": {"withinMin": 30}}, now))
    chk("visitMutual 10분 안은 거짓", not AR._cond(u, 1, {"visitMutual": {"withinMin": 10}}, now))
    # 플레이테스트: 이벤트가 시작한 뒤 만든 계정(부계정)과의 방문은 안 센다 (혼자 두 계정으로 여는 길 막기)
    alt = mkuser()
    db.run("UPDATE users SET created_at=? WHERE id=?", ((OPEN1 + datetime.timedelta(minutes=5)).isoformat(), alt))
    v = mkuser()
    visit.log_visit(v, alt, now - datetime.timedelta(minutes=8))
    visit.log_visit(alt, v, now - datetime.timedelta(minutes=4))
    chk("visitMutual: 이벤트 뒤에 만든 계정과는 거짓", not AR._cond(v, 1, {"visitMutual": {"withinMin": 30}}, now))
    # 탐험
    box = mkmon(u, "GEODUDE", 30, seed=8, desk=False)
    db.run("INSERT INTO expedition (user_id, pokemon_id, place, hours, grade, score, started_at, ends_at, state)"
           " VALUES (?,?,?,?,?,?,?,?,'out')", (u, box, "arche", 2, "good", 50,
                                               kst(11, 15, 1, 10).isoformat(), kst(11, 15, 3, 10).isoformat()))
    chk("expedition 곳 참", AR._cond(u, 1, {"expedition": {"place": "arche"}}, now))
    chk("expedition 다른 곳 거짓", not AR._cond(u, 1, {"expedition": {"place": "cave"}}, now))
    chk("expedition 타입 참 (바위)", AR._cond(u, 1, {"expedition": {"place": "arche", "type": "ROCK"}}, now))
    chk("expedition 타입 거짓 (물)", not AR._cond(u, 1, {"expedition": {"place": "arche", "type": "WATER"}}, now))
    chk("expedition 시각대 참", AR._cond(u, 1, {"expedition": {"place": "arche", "time": ["01:00", "02:00"]}}, now))
    chk("expedition 시각대 거짓", not AR._cond(u, 1, {"expedition": {"place": "arche", "time": ["02:00", "03:00"]}}, now))
    chk("expedition 다른 장 동안 보낸 것은 거짓", not AR._cond(u, 2, {"expedition": {"place": "arche"}},
                                                    A.window(2)[0] + datetime.timedelta(hours=1)))
    # 묶음
    chk("all 참", AR._cond(u, 1, {"all": [{"key": "k1"}, {"partyHas": {"type": "ICE"}}]}, now))
    chk("all 하나 거짓", not AR._cond(u, 1, {"all": [{"key": "k1"}, {"key": "k2"}]}, now))
    chk("any 하나 참", AR._cond(u, 1, {"any": [{"key": "k2"}, {"key": "k1"}]}, now))
    chk("any 다 거짓", not AR._cond(u, 1, {"any": [{"key": "k2"}, {"partyHas": {"type": "FIRE"}}]}, now))
    chk("모르는 조건은 거짓", not AR._cond(u, 1, {"dance": 3}, now) and not AR._cond(u, 1, None, now))


# ---------------------------------------------------------------- 의식
def t_의식():
    print("[의식 · 첫 사람 · 칭호]")
    a, b, c = mkuser("첫발견"), mkuser(), mkuser()
    t = kst(11, 15, 3, 0)                          # 23:50 ~ 05:30 안
    AR.submit_key(a, 1, "푸른 사과가 바다 위로 떠오른다", "type", now=kst(11, 15, 12, 0))     # 창 밖에 적었다 - 아직
    chk("열쇠만으로는 안 된다 (시각 밖)", ch(AR.state(a, now=kst(11, 15, 12, 1)), 1)["ritual"] is False)
    st = AR.state(a, now=kst(11, 15, 23, 55))
    chk("시각 안에 폴링하면 의식이 된다", ch(st, 1)["ritual"] is True and ch(st, 1)["ritualAt"], ch(st, 1))
    row = db.q1("SELECT * FROM arche_progress WHERE user_id=? AND chapter=1", (a,))
    chk("첫 사람 표시 · 칭호 '아르케의 발견자'", row and row["first"] == 1
        and db.q1("SELECT 1 FROM user_reward WHERE user_id=? AND rid='arche_first'", (a,)) is not None)
    chk("칭호 이름이 등록됐다", season.TITLES.get("arche_first") == "아르케의 발견자"
        and season.TITLES.get("arche_six") == "여섯 봉인의 증인")
    chk("장에 이름이 남는다 · 푼 사람 1", ch(st, 1)["first"] == "첫발견" and ch(st, 1)["solvers"] == 1, ch(st, 1))
    out = AR.submit_key(b, 1, "푸른 사과가 바다 위로 떠오른다", "type", now=t + datetime.timedelta(hours=24))   # 11/16 03:00 - 창 안
    chk("열쇠를 적은 그 자리에서 판정한다", ch(out["state"], 1)["ritual"] is True)
    chk("두 번째 사람은 first 0 · 칭호 없음", db.q1("SELECT first FROM arche_progress WHERE user_id=?", (b,))["first"] == 0
        and db.q1("SELECT 1 FROM user_reward WHERE user_id=? AND rid='arche_first'", (b,)) is None)
    chk("두 번 판정해도 줄은 하나", AR.check(b, now=t + datetime.timedelta(hours=24, minutes=1)) == []
        and db.q1("SELECT COUNT(*) c FROM arche_progress WHERE user_id=?", (b,))["c"] == 1)
    # 장 경계 (1장 마지막 초 · 닫힌 뒤)
    db.run("INSERT INTO arche_key (user_id, chapter, key, via, at) VALUES (?,1,'k1','type',?)",
           (c, OPEN1.isoformat()))
    d = mkuser()
    db.run("INSERT INTO arche_key (user_id, chapter, key, via, at) VALUES (?,1,'k1','type',?)",
           (d, OPEN1.isoformat()))
    last = A.window(1)[1] - datetime.timedelta(seconds=1)
    chk("1장 마지막 초 (23:59:59) 에 의식이 된다", AR.check(c, now=last) == [1])
    chk("닫힌 1초 뒤에는 1장 의식이 안 된다", AR.check(d, now=A.window(1)[1] + datetime.timedelta(seconds=1)) == []
        and db.q1("SELECT 1 FROM arche_progress WHERE user_id=?", (d,)) is None)
    st = AR.state(c, now=A.window(3)[0])
    enc = ch(st, 1)["encounters"]
    chk("닫힌 장의 전설 자리는 이벤트 끝까지 ready (첫 자리)", [e["state"] for e in enc] == ["ready", "locked", "locked"], enc)
    st = AR.state(d, now=A.window(3)[0])
    chk("의식 못 한 사람은 locked", all(e["state"] == "locked" for e in ch(st, 1)["encounters"]))
    # 여섯 장
    e = mkuser()
    for n in range(1, 6):
        db.run("INSERT INTO arche_progress (user_id, chapter, ritual_at, first) VALUES (?,?,?,1)",
               (e, n, OPEN1.isoformat()))
    db.run("INSERT INTO arche_key (user_id, chapter, key, via, at) VALUES (?,6,'z','type',?)",
           (e, OPEN1.isoformat()))
    chk("6장 의식 → 여섯 장 모두", AR.check(e, now=A.window(6)[0] + datetime.timedelta(hours=1)) == [6]
        and db.q1("SELECT 1 FROM user_reward WHERE user_id=? AND rid='arche_six'", (e,)) is not None)
    rows = dict((r[0], r[3]) for r in AR.title_rows(now=OPEN1))
    chk("칭호 목록 (도감 '칭호' 탭용)", set(rows) == {"arche_first", "arche_six"} and all(rows.values()), rows)


# ---------------------------------------------------------------- 현상 · 제목 해시
def t_현상_제목():
    print("[현상 창 · 제목 해시]")
    u = mkuser()
    now = kst(11, 15, 3, 0, 30)
    ids = [p["id"] for p in AR.state(u, now=now)["phenomena"]]
    chk("지금 것 · 아직 이어지는 것만 (미래 · 지난 것 없음)", sorted(ids) == ["p-long", "p-now"], ids)
    one = [p for p in AR.state(u, now=now)["phenomena"] if p["id"] == "p-now"][0]
    chk("현상: at · until (UTC) · kind · data", one["kind"] == "unown" and one["data"] == {"glyph": 2}
        and one["until"] == (kst(11, 15, 3, 0) + datetime.timedelta(seconds=40)).isoformat(), one)
    ids = [p["id"] for p in AR.state(u, now=kst(11, 15, 3, 8, 40))["phenomena"]]
    chk("90초 앞까지는 미리 준다", "p-later" in ids, ids)
    c1 = ch(AR.state(u, now=OPEN1 + datetime.timedelta(hours=1)), 1)
    salt = c1["titleSalt"]
    chk("제목 해시: 제목 열쇠(k1) 답 하나만", c1["titleHashes"] == [A.key_hash(salt, "푸른 사과가 바다 위로 떠오른다")], c1["titleHashes"])
    chk("제목 소금은 비밀 소금이 아니다", salt and salt != SECRETS["salt"] and "시험소금" not in salt)
    chk("제목 해시: 정규화해서 맞춘다", A.key_hash(salt, A.title_core("푸른  사과가 바다 위로 떠오른다 - Google Chrome")) in c1["titleHashes"])
    AR.submit_key(u, 1, "푸른 사과가 바다 위로 떠오른다", "title", now=kst(11, 15, 12, 0))      # 의식 시각 밖 - 의식 전 그대로
    c1 = ch(AR.state(u, now=kst(11, 15, 12, 1)), 1)
    chk("알아낸 열쇠의 해시는 더 안 준다 (의식 전이어도)", c1["ritual"] is False and not c1.get("titleHashes"),
        (c1["ritual"], c1.get("titleHashes")))
    w = mkuser()
    db.run("INSERT INTO arche_progress (user_id, chapter, ritual_at, first) VALUES (?,1,?,0)", (w, OPEN1.isoformat()))
    chk("의식을 마치면 제목 해시가 없다", not ch(AR.state(w, now=kst(11, 15, 12, 1)), 1).get("titleHashes"))
    v = mkuser()
    st = AR.state(v, now=A.window(2)[0])
    chk("지난 장에는 제목 해시가 없다", not ch(st, 1).get("titleHashes"))
    chk("열려 있어도 제목 열쇠가 없는 장은 비어 있다", not ch(st, 2).get("titleHashes"))


# ---------------------------------------------------------------- 게시글
def t_게시글():
    print("[게시글 · NPC · 실마리 사다리]")
    from PIL import Image
    os.makedirs(os.path.join(ARCHE_DIR, "img"), exist_ok=True)
    Image.new("RGB", (8, 6), (10, 20, 30)).save(os.path.join(ARCHE_DIR, "img", "t1.png"))
    db.run("DELETE FROM meta WHERE k LIKE 'arche:%'")
    db.run("DELETE FROM board_post WHERE ref LIKE 'arche:%'")
    db.run("DELETE FROM arche_progress")
    AR.ensure_posts(now=OPEN1 + datetime.timedelta(minutes=1), force=True)
    AR.ensure_posts(now=OPEN1 + datetime.timedelta(minutes=2), force=True)
    posts = db.q("SELECT * FROM board_post WHERE ref LIKE 'arche:%' ORDER BY id")
    chk("장 열림 글은 한 번만", [p["ref"] for p in posts] == ["arche:1"], [p["ref"] for p in posts])
    npc = db.q1("SELECT * FROM users WHERE username=?", ("시험고고학자",))
    chk("NPC 계정이 생겼다 · 글쓴이", npc is not None and posts[0]["user_id"] == npc["id"]
        and posts[0]["author"] == "시험고고학자" and posts[0]["title"] == "시험 일지 1", posts[0]["title"] if posts else None)
    chk("NPC 는 로그인할 수 없다 (빈 해시)", not auth.verify_password("", npc["pw_hash"], npc["pw_salt"], npc["pw_iter"])
        and not auth.verify_password("0000", npc["pw_hash"], npc["pw_salt"], npc["pw_iter"]))
    chk("NPC 는 운영자가 아니다 (지우기 · 공지 못 함)", not __import__("app.board", fromlist=["x"]).is_admin(dict(npc)))
    chk("본문은 일지 첫 글", "첫 일지 글" in posts[0]["body"], posts[0]["body"])
    img = db.q("SELECT * FROM board_image WHERE post_id=?", (posts[0]["id"],))
    chk("사진이 글에 붙는다 (파일까지)", len(img) == 1 and img[0]["w"] == 8
        and os.path.exists(os.path.join(os.environ["POKET_BOARD_IMG_DIR"], "%d.%s" % (img[0]["id"], img[0]["fmt"]))), img)
    # 실마리: 18시간 · 푼 사람 < 3 → 올라감
    AR.ensure_posts(now=OPEN1 + datetime.timedelta(hours=17, minutes=59), force=True)
    chk("18시간 전에는 실마리 없음", db.q1("SELECT COUNT(*) c FROM board_post WHERE ref LIKE 'arche:1:h%'")["c"] == 0)
    AR.ensure_posts(now=OPEN1 + datetime.timedelta(hours=18, minutes=1), force=True)
    AR.ensure_posts(now=OPEN1 + datetime.timedelta(hours=18, minutes=2), force=True)
    chk("18시간 · 푼 사람 0 < 3 → 실마리 하나 (한 번만)",
        [r["ref"] for r in db.q("SELECT ref FROM board_post WHERE ref LIKE 'arche:1:h%'")] == ["arche:1:h1"])
    u = mkuser()
    st = AR.state(u, now=OPEN1 + datetime.timedelta(hours=19))
    chk("일지에도 실마리가 올라간다", [j.get("hint") for j in ch(st, 1)["journal"]] == [None, None, 1]
        and ch(st, 1)["journal"][-1]["text"] == "실마리 하나", ch(st, 1)["journal"])
    # 둘째 실마리 기준 1명: 한 명이 풀었으면 안 올라감
    db.run("INSERT INTO arche_progress (user_id, chapter, ritual_at, first) VALUES (?,1,?,1)",
           (u, (OPEN1 + datetime.timedelta(hours=20)).isoformat()))
    AR.ensure_posts(now=OPEN1 + datetime.timedelta(hours=31), force=True)
    chk("30시간 · 푼 사람 1 ≥ 1 → 둘째 실마리 없음",
        db.q1("SELECT 1 FROM board_post WHERE ref='arche:1:h2'") is None)
    AR.ensure_posts(now=OPEN1 + datetime.timedelta(hours=41), force=True)
    refs = [r["ref"] for r in db.q("SELECT ref FROM board_post WHERE ref LIKE 'arche:1:h%' ORDER BY id")]
    chk("40시간 · 1 < 30 → 셋째 실마리 (둘째는 건너뜀)", refs == ["arche:1:h1", "arche:1:h3"], refs)
    AR.ensure_posts(now=A.window(2)[0] + datetime.timedelta(minutes=1), force=True)
    chk("2장이 열리면 2장 글", db.q1("SELECT 1 FROM board_post WHERE ref='arche:2'") is not None)
    chk("닫힌 1장에는 실마리를 더 안 올린다", len(db.q("SELECT ref FROM board_post WHERE ref LIKE 'arche:1:h%'")) == 2)
    # NPC 이름을 진짜 사람이 쓰고 있으면 글을 안 올린다 (터지지도 않는다)
    s2 = json.loads(json.dumps(SECRETS))
    s2["npc"] = "남의이름"
    mkuser("남의이름")
    write_secrets(s2, bump=6)
    db.run("DELETE FROM meta WHERE k='arche:post:2'")
    db.run("DELETE FROM board_post WHERE ref='arche:2'")
    AR.ensure_posts(now=A.window(2)[0] + datetime.timedelta(minutes=3), force=True)
    chk("이름이 남의 것이면 올리지 않는다", db.q1("SELECT 1 FROM board_post WHERE ref='arche:2'") is None)
    write_secrets(SECRETS, bump=7)


def t_예약글():
    print("[예약 글 · 둘째 계정 (이벤트 전) · 마지막 날 글 · 5장 혼자 길]")
    s3 = json.loads(json.dumps(SECRETS))
    s3["traveler"] = "시험방랑자"
    s3["posts"] = [{"ref": "arche:pre1", "at": (OPEN1 - datetime.timedelta(days=2)).isoformat(), "by": "traveler",
                    "title": "지어낸 떡밥", "body": "지어낸 본문"},
                   {"ref": "arche:end", "at": (A.window(6)[1] - datetime.timedelta(hours=4)).isoformat(), "by": "npc",
                    "title": "지어낸 끝", "body": "끝 본문"},
                   {"ref": "nope", "at": (OPEN1 - datetime.timedelta(days=3)).isoformat(), "title": "x", "body": "x"},
                   "문자열"]
    write_secrets(s3, bump=8)
    db.run("DELETE FROM board_post WHERE ref LIKE 'arche:pre%' OR ref='arche:end' OR ref='nope'")
    AR.ensure_posts(now=OPEN1 - datetime.timedelta(days=2, minutes=1), force=True)
    chk("때가 안 된 예약 글은 없다", db.q1("SELECT COUNT(*) c FROM board_post WHERE ref LIKE 'arche:pre%'")["c"] == 0)
    AR.ensure_posts(now=OPEN1 - datetime.timedelta(days=1), force=True)
    AR.ensure_posts(now=OPEN1 - datetime.timedelta(hours=23), force=True)
    rows = db.q("SELECT * FROM board_post WHERE ref LIKE 'arche:pre%'")
    chk("이벤트 전에도 둘째 계정 글이 한 번 올라간다", [r["ref"] for r in rows] == ["arche:pre1"]
        and rows[0]["author"] == "시험방랑자" and rows[0]["body"] == "지어낸 본문", [dict(r) for r in rows])
    trav = db.q1("SELECT * FROM users WHERE username=?", ("시험방랑자",))
    chk("둘째 계정은 로그인할 수 없다 (빈 해시)", trav is not None
        and not auth.verify_password("", trav["pw_hash"], trav["pw_salt"], trav["pw_iter"]))
    chk("둘째 계정 이름(빈칸 섞어도)으로는 가입 못 한다", auth.check_username("시험방랑자")[0] is None
        and auth.check_username("시험 방랑자")[0] is None, auth.check_username("시험 방랑자"))
    chk("비슷한 다른 이름은 된다", auth.check_username("방랑자팬")[0] == "방랑자팬")
    chk("모양이 틀린 예약 글은 버린다 (ref 가 arche: 로 시작 안 함)",
        db.q1("SELECT 1 FROM board_post WHERE ref='nope'") is None)
    AR.ensure_posts(now=A.window(6)[1] - datetime.timedelta(hours=3), force=True)
    end = db.q1("SELECT * FROM board_post WHERE ref='arche:end'")
    chk("마지막 날 글은 고고학자 이름으로 (한 번)", end is not None and end["author"] == "시험고고학자", end and dict(end))
    # 5장 혼자 길: 둘이 서로 놀러 가거나 / (정한 때 안에) 모래시계를 쓰거나
    u = mkuser()
    span = [[(kst(11, 20, 0)).isoformat(), (kst(11, 21, 0)).isoformat()]]
    cond = {"any": [{"visitMutual": {"withinMin": 30}},
                    {"all": [{"when": span}, {"itemUsed": {"item": "ARCHESAND", "withinMin": 30}}]}]}
    now = kst(11, 20, 12)
    chk("혼자 길: 모래시계를 안 썼으면 거짓", not AR._cond(u, 5, cond, now))
    db.run("INSERT INTO arche_use (user_id, item, at) VALUES (?,?,?)",
           (u, "ARCHESAND", (now - datetime.timedelta(minutes=5)).isoformat()))
    chk("혼자 길: 정한 때 안에 쓰면 참", AR._cond(u, 5, cond, now))
    chk("혼자 길: 정한 때 밖이면 거짓", not AR._cond(u, 5, cond, kst(11, 21, 0, 10)))
    write_secrets(SECRETS, bump=9)


# ---------------------------------------------------------------- 숨은 페이지
def t_페이지():
    print("[숨은 페이지]")
    old_now = AR._now
    AR._now = lambda now=None: now or (OPEN1 + datetime.timedelta(hours=1))
    try:
        _t_페이지()
    finally:
        AR._now = old_now
    # 리뷰 I4: 다음 장 것 · 어느 장에도 없는 것은 그 장이 열리기 전에 안 준다
    for name in ("def-34.html", "t2.png", "zzz-99.html"):
        sub = "pages" if name.endswith(".html") else "img"
        with io.open(os.path.join(ARCHE_DIR, sub, name), "w", encoding="utf-8") as f:
            f.write("x")
    chk("2장 페이지: 1장 동안엔 없음 · 2장이 열리면 있음",
        AR.page_path("def-34", now=OPEN1 + datetime.timedelta(hours=1)) is None
        and AR.page_path("def-34", now=A.window(2)[0]) is not None)
    chk("2장 그림: 1장 동안엔 없음 · 2장이 열리면 있음",
        AR.img_path("t2.png", now=OPEN1 + datetime.timedelta(hours=1)) is None
        and AR.img_path("t2.png", now=A.window(2)[0]) is not None)
    chk("어느 장에도 없는 페이지는 늘 없음", AR.page_path("zzz-99", now=A.window(6)[0]) is None)
    chk("열리기 전엔 1장 것도 없음", AR.page_path("abc-12", now=OPEN1 - datetime.timedelta(hours=1)) is None)


def _t_페이지():
    os.makedirs(os.path.join(ARCHE_DIR, "pages"), exist_ok=True)
    with io.open(os.path.join(ARCHE_DIR, "pages", "abc-12.html"), "w", encoding="utf-8") as f:
        f.write("<html><body>시험 페이지</body></html>")
    r = arche_routes.page("abc-12")
    chk("있는 페이지: HTML", r.status_code == 200 and "시험 페이지" in r.body.decode("utf-8")
        and r.media_type.startswith("text/html"))
    for bad in ("../secrets", "ABCD", "abc", "a" * 41, "abc-12.html", "없는-페이지x"):
        got = refused(arche_routes.page, bad)
        chk("막는다: %s → 404" % bad[:12], got and got[0] == 404, got)
    r = arche_routes.image("t1.png")
    chk("그림: png", r.status_code == 200 and r.media_type == "image/png")
    for bad in ("../t1.png", "T1.png", "t1.jpg", "nothere.png"):
        got = refused(arche_routes.image, bad)
        chk("그림 막기: %s → 404" % bad, got and got[0] == 404, got)


# ---------------------------------------------------------------- 리뷰 (11/09)
def t_플레이테스트():
    print("[플레이테스트: 비석 쉬는 시간 · IP 한도 · 고고학자 이름]")
    from app import auth
    s2 = json.loads(json.dumps(SECRETS))
    s2["chapters"]["1"]["cooldown"] = {"ARCHESTONE": 360}
    write_secrets(s2, bump=21)
    u = mkuser()
    items.bag_add(u, "ARCHESTONE", 1)
    t = OPEN1 + datetime.timedelta(hours=2)
    a = AR.use_item(u, "ARCHESTONE", now=t)
    b = AR.use_item(u, "ARCHESTONE", now=t + datetime.timedelta(minutes=25))
    n_use = db.q1("SELECT COUNT(*) c FROM arche_use WHERE user_id=?", (u,))["c"]
    chk("비석은 한 번 울리면 여섯 시간 조용하다 (계속 쓰기로 시각 맞추기 막기)", a.get("ok") and not b.get("ok") and n_use == 1
        and "조용" in b.get("message", ""), (a.get("ok"), b, n_use))
    c = AR.use_item(u, "ARCHESTONE", now=t + datetime.timedelta(hours=6, minutes=1))
    chk("여섯 시간 뒤엔 다시 울린다", c.get("ok") and db.q1("SELECT COUNT(*) c FROM arche_use WHERE user_id=?", (u,))["c"] == 2)
    write_secrets(SECRETS, bump=22)
    # 같은 IP 에서 여러 계정으로 마구 넣기: IP 마다 시간당 60번
    when = OPEN1 + datetime.timedelta(hours=3)
    hit = None
    for i in range(4):
        acc = mkuser()
        for j in range(20):
            try:
                AR.submit_key(acc, 1, "틀린 말 %d %d" % (i, j), "type", now=when, ip="10.0.0.9")
            except HTTPException as e:
                hit = (i, j, e.status_code)
                break
        if hit:
            break
    chk("같은 IP 의 여러 계정은 합쳐서 시간당 60번 (부계정 대입 막기)", hit == (3, 0, 429), hit)
    other = mkuser()
    ok = AR.submit_key(other, 1, "틀린 말", "type", now=when, ip="10.0.0.10")
    chk("다른 IP 는 따로 센다", ok.get("ok") is False)
    chk("'고고학자' 가 든 닉네임은 가입할 수 없다 (사칭 막기)", auth.check_username("진짜고고학자")[1]
        and auth.check_username("고고학자 리안")[1] and auth.check_username("발굴단원")[1] is None)


def t_리뷰():
    print("[리뷰: 짧은 제목 열쇠 · 깨진 모양 · 소금 · when 시간대]")
    u = mkuser()
    s2 = json.loads(json.dumps(SECRETS))
    s2["chapters"]["1"]["keys"]["k3"] = {"answers": ["짧은말"], "title": True}
    write_secrets(s2, bump=11)
    c1 = ch(AR.state(u, now=OPEN1 + datetime.timedelta(hours=1)), 1)
    salt = c1.get("titleSalt")
    chk("짧은 답(열 글자 아래)은 제목 해시로 안 준다", salt and A.key_hash(salt, "짧은말") not in (c1.get("titleHashes") or [])
        and A.key_hash(salt, "푸른 사과가 바다 위로 떠오른다") in c1["titleHashes"], c1.get("titleHashes"))
    bad = json.loads(json.dumps(SECRETS))
    bad["chapters"]["1"].update(journal=["글만"], hints=[3, None], keys=["x"], phenomena=["y", {"at": "아무거나"}],
                                marks="판", ritual=["z"], gift="ARCHESTONE", dig=["d"])
    bad["chapters"]["2"] = "망가진 장"
    write_secrets(bad, bump=12)
    try:
        st = AR.state(u, now=OPEN1 + datetime.timedelta(hours=1))
        ok = True
    except Exception as e:                                   # noqa: BLE001
        st, ok = repr(e), False
    chk("모양이 깨진 비공개 자료: state 가 터지지 않는다", ok and ch(st, 1)["journal"] == [], st if not ok else ch(st, 1)["journal"])
    chk("깨진 자료: 의식 · 선물 · 보고서도 안 터진다", AR.check(u, now=OPEN1 + datetime.timedelta(hours=1)) in (None, False, True, [], 0)
        and AR.give_gift(u, now=OPEN1 + datetime.timedelta(hours=1)) == 0
        and AR.dig_report(OPEN1 + datetime.timedelta(hours=1)) is None)
    s3 = json.loads(json.dumps(SECRETS))
    s3["salt"] = "짧음"
    write_secrets(s3, bump=13)
    chk("소금이 짧으면 준비 안 됨 (공개 코드로 전설을 미리 셀 수 없게)", not AR.ready())
    write_secrets(SECRETS, bump=14)
    s4 = json.loads(json.dumps(SECRETS))
    s4["npc"] = "새고고학자"
    write_secrets(s4, bump=15)
    AR.secrets()
    chk("비공개 자료를 읽는 순간 고고학자 계정을 잡아 둔다 (장이 열리기 전)",
        db.q1("SELECT 1 FROM users WHERE username='새고고학자'") is not None)
    write_secrets(SECRETS, bump=16)
    chk("when: 시간대 없는 값은 KST", AR._cond(u, 1, {"when": [["2026-11-15T10:00:00", "2026-11-15T10:40:00"]]},
                                        kst(11, 15, 10, 20)))


# ---------------------------------------------------------------- 장 선물 · 아이템
def t_선물_아이템():
    print("[장 선물 · 열쇠 아이템]")
    u = mkuser()
    chk("열리기 전에는 선물 없음", AR.give_gift(u, now=OPEN1 - datetime.timedelta(hours=1)) == 0)
    chk("열린 장의 선물은 한 번", AR.give_gift(u, now=OPEN1 + datetime.timedelta(hours=1)) == 1
        and AR.give_gift(u, now=OPEN1 + datetime.timedelta(hours=2)) == 0)
    got = items.gift_claim(u)
    chk("선물함으로 받는다 (ARCHESTONE)", [g["item"] for g in got] == ["ARCHESTONE"] and items.bag_count(u, "ARCHESTONE") == 1, got)
    cat = items.catalog()
    chk("열쇠 아이템 여섯 · custom · effect arche · 드랍 없음",
        all(cat.get(k, {}).get("custom") and cat[k]["effect"]["kind"] == "arche" and not cat[k].get("rarity")
            for k in ("ARCHESTONE", "ARCHESHELL", "ARCHESTAR", "ARCHESAND", "ARCHECROWN", "ARCHELAMP")))
    chk("아이콘 PNG 여섯", all(os.path.exists(os.path.join(HERE, "data", "item_sprites", k + ".png"))
                           for k in ("ARCHESTONE", "ARCHESHELL", "ARCHESTAR", "ARCHESAND", "ARCHECROWN", "ARCHELAMP")))
    base = cat["ARCHESTONE"]["desc"]
    chk("설명 덮기: 이벤트 전엔 기본 설명", AR.item_desc("ARCHESTONE", now=OPEN1 - datetime.timedelta(hours=1)) is None)
    chk("설명 덮기: 1장", AR.item_desc("ARCHESTONE", now=OPEN1 + datetime.timedelta(hours=1)) == "시험 설명 하나")
    chk("설명 덮기: 2장이 열리면 2장 것", AR.item_desc("ARCHESTONE", now=A.window(2)[0]) == "둘째 장 설명")
    chk("설명 덮기: 다른 아이템은 None", AR.item_desc("ARCHELAMP", now=OPEN1 + datetime.timedelta(hours=1)) is None
        and AR.item_desc("POKEBALL") is None)
    old_now = AR._now
    try:
        AR._now = lambda now=None: now or (OPEN1 + datetime.timedelta(hours=1))
        lst = dict((x["id"], x) for x in items.public_list())
        chk("상점 · 가방 목록에 덮은 설명", lst["ARCHESTONE"]["desc"] == "시험 설명 하나", lst["ARCHESTONE"]["desc"])
        drop_secrets()
        lst = dict((x["id"], x) for x in items.public_list())
        chk("secrets 없으면 기본 설명", lst["ARCHESTONE"]["desc"] == base and base)
        write_secrets(SECRETS, bump=8)
        # 가방에서 쓰기
        me = {"user": dict(user(u))}
        out = item_routes.use(item_routes.UseIn(item="ARCHESTONE"), me=me)
        chk("가방에서 쓰기: 메시지 · 없어지지 않는다", out.get("message") and items.bag_count(u, "ARCHESTONE") == 1, out)
        chk("쓰기 → arche_use 줄 → itemUsed 참",
            db.q1("SELECT 1 FROM arche_use WHERE user_id=? AND item='ARCHESTONE'", (u,)) is not None
            and AR._cond(u, 1, {"itemUsed": {"item": "ARCHESTONE", "withinMin": 5}}, OPEN1 + datetime.timedelta(hours=1)))
        got = refused(item_routes.use, item_routes.UseIn(item="ARCHELAMP"), me=me)
        chk("없는 열쇠 아이템은 쓸 수 없다", got and got[0] == 400, got)
    finally:
        AR._now = old_now


# ---------------------------------------------------------------- 발굴지
def t_발굴지():
    print("[아르케 발굴지]")
    chk("발굴지는 물건 곳 여섯 · 곳 일곱에 안 섞인다", len(X.ITEM_PLACES) == 6 and len(X.PLACES) == 7
        and X.place("arche") and X.place("arche")["kr"] == "아르케 발굴지")
    chk("place_open: 이벤트 밖 거짓 · 안 참 · 다른 곳은 늘 참",
        not X.place_open("arche", OPEN1 - datetime.timedelta(seconds=1)) and X.place_open("arche", OPEN1)
        and not X.place_open("arche", A.event_window()[1]) and X.place_open("cave", OPEN1 - datetime.timedelta(days=30)))
    chk("places(): 이벤트 동안만 발굴지가 끼인다",
        "arche" not in [p["id"] for p in X.places(OPEN1 - datetime.timedelta(days=1))]
        and "arche" in [p["id"] for p in X.places(OPEN1)])
    u = mkuser()
    pid = mkmon(u, "GEODUDE", 40, seed=11, desk=False)
    got = refused(expedition.send, u, pid, "arche", 2, now=OPEN1 - datetime.timedelta(minutes=1))
    chk("이벤트 밖에 보내면 409", got and got[0] == 409, got)
    out = expedition.send(u, pid, "arche", 2, now=kst(11, 15, 1, 0))
    chk("이벤트 안에는 보낸다", out.get("ok"), out.get("message"))
    out = expedition.claim(u, now=kst(11, 15, 4, 0), rng=random.Random(3))
    rep = out["claimed"][0].get("report") if out.get("claimed") else None
    chk("돌아온 시각(03시)의 보고서", rep == "새벽 보고서", rep)
    chk("dig_report: 자정 넘는 시각대 23시", AR.dig_report(kst(11, 15, 23, 0)) == "자정 무렵 보고서")
    chk("dig_report: 01시는 앞 시각대 (0-6)", AR.dig_report(kst(11, 16, 1, 0)) == "새벽 보고서")
    chk("dig_report: 정각 한 시", AR.dig_report(kst(11, 15, 12, 30)) == "정오 보고서")
    chk("dig_report: 나머지는 *", AR.dig_report(kst(11, 15, 15, 0)) == "보통 보고서")
    chk("dig_report: 보고서 없는 장 · 이벤트 밖은 None", AR.dig_report(A.window(2)[0]) is None
        and AR.dig_report(OPEN1 - datetime.timedelta(hours=1)) is None)


def main():
    db.init()
    t_준비_안_됨()
    t_다시_읽기_장_경계()
    t_열쇠()
    t_조건()
    t_의식()
    t_현상_제목()
    t_게시글()
    t_예약글()
    t_페이지()
    t_리뷰()
    t_플레이테스트()
    t_선물_아이템()
    t_발굴지()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
