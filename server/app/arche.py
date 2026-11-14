# -*- coding: utf-8 -*-
"""아르케의 여섯 봉인 (시즌 6 이벤트, 2.4.0) — 서버 쪽 본체. 길은 arche_routes.py, 규칙은 common/arche.py.

설계 design-notes/2026-11-09-arche.md · 계획 2026-11-09-arche-plan.md.

## 비공개 자료

**수수께끼 글 · 정답 · 의식 조건 · 현상 시각 · 숨은 페이지는 저장소에 없다.** 운영 볼륨의 config.ARCHE_DIR
(`/data/arche/secrets.json` · `pages/` · `img/`)에만 있다. 이 파일은 그 자료를 읽어 판정하는 '도구' 일 뿐이다.

- 파일은 **mtime 으로 다시 읽는다** - 운영자가 실마리를 더하면 다음 요청에 그대로 올라간다 (secrets).
- 파일이 없거나 깨졌으면 이벤트는 `ready: False` ('준비 중') 로만 보이고 아무것도 깨지지 않는다.

## 판정은 서버가

앱은 "이 말을 안다" · "이걸 했다" 만 보낸다. 의식(ritual)은 조건을 묶은 것이고 (`all` / `any`), 조건 종류는
_cond 에 있다 (값은 비공개). 판정은 그 장이 **열려 있는 동안에만** - 지난 장은 닫힌다. 의식을 마친 장의 전설은
**이벤트 끝까지** 다시 도전할 수 있다 (장 마감 직전에 의식을 마친 사람이 배틀을 못 끝내 잃지 않게).

## 전설 배틀

관장 판(gym_battle + common/trainer_battle)을 다시 쓴다. region = `arche:<장>:<자리>`. 진행은 /api/gym/battle/{id}/act
그대로이고, 이 판에만 **볼 던지기**(kind=ball)가 더해진다 (throw_ball). 놓치면 전설만 한 턴 움직인다 (act("pass")).
포획률 하한 45 · 마스터볼 됨. 전설의 개체값(셋만 31) · 성격 · 특성 · 이로치는 사람 · 장 · 자리로 정해진다 -
판을 다시 열어 이로치를 다시 굴릴 수 없다 (레벨만 그때 파티에 맞춘다).

## 보상

**돈벌이가 아니다.** 잡은 전설 + 칭호 둘 ('아르케의 발견자' - 어느 장이든 가장 먼저 의식을 마친 사람,
'여섯 봉인의 증인' - 여섯 장 의식을 모두 마친 사람). 장 선물은 그 장의 열쇠 아이템 (팔 수 없다).
"""
import datetime
import hashlib
import io
import json
import os
import random
import re
import threading
import time

from fastapi import HTTPException

from common import arche as A
from common import korean
from common import pokelogic as P
from common import statusmoves as SM
from common import trainer_battle as TB

from . import config, db, deps, items, season

KST = A.KST
UTC = A.UTC
POLL = 60                      # 앱이 state 를 부르는 간격 (초)
TITLE_MIN = 10                 # 창 제목 열쇠로 해시를 내줄 답의 최소 길이 (정규화한 글자 수) - 리뷰 C1
KEY_TRIES_PER_HOUR = 20        # 열쇠 적기 한도 (마구 넣어 보기 막기)
KEY_TRIES_PER_IP = 60          # 같은 IP 의 여러 계정을 합친 시간당 한도 (부계정으로 마구 넣기 막기)
KEY_TEXT_MAX = 200
LEAD = 90                      # 현상을 이만큼 앞뒤로 준다 (초) - 폴링 간격보다 길게
CARD_BEFORE_DAYS = 7           # 이벤트 이만큼 전부터 /api/me 에 카드를 싣는다
CARD_AFTER_DAYS = 1
CATCH_FLOOR = 45               # 포획률 하한 (해금 종의 하한과 같은 값 - achievements.catch_species)
PERFECT_IVS = 3                # 개체값 31 인 능력 수 (본편 전설 규칙)
PREFIX = "arche:"
POST_EVERY = 30                # 게시글 · 실마리를 이만큼(초)에 한 번만 본다 (프로세스 안)
NPC_ROLE = "고고학자"
# 게시판에 글을 쓰는 계정들: 비공개 자료의 열쇠 -> 그 계정 이름 (npc = 고고학자 · traveler = 또 다른 계정)
NPC_ROLES = ("npc", "traveler")

TITLES = {"arche_first": "아르케의 발견자", "arche_six": "여섯 봉인의 증인"}
season.TITLES.update(TITLES)

PLACE_WORD = {"cave": "동굴", "volcano": "화산", "abyss": "심해", "sky": "하늘", "castle": "고성", "throne": "왕좌의 방"}


def _now(now=None):
    return (now or datetime.datetime.now(UTC)).replace(microsecond=0)


def _iso(t):
    return t.astimezone(UTC).replace(microsecond=0).isoformat()


def _parse_kst(s):
    """시간대가 없으면 KST 로 읽는다 (운영자가 손으로 적는 값 - '2026-11-19T10:12')."""
    try:
        t = datetime.datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return (t if t.tzinfo else t.replace(tzinfo=KST)).astimezone(UTC)


def _parse(s):
    try:
        t = datetime.datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return (t if t.tzinfo else t.replace(tzinfo=UTC)).astimezone(UTC)


# ---------------------------------------------------------------- 비공개 자료
_cache = {"key": None, "data": None}
_cache_lock = threading.Lock()


def _path(*parts):
    return os.path.join(config.ARCHE_DIR, *parts)


def secrets():
    """secrets.json (dict) 또는 None. **mtime · 크기가 바뀌면 다시 읽는다** - 운영자 손질이 다음 요청에 든다."""
    path = _path("secrets.json")
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (path, st.st_mtime_ns, st.st_size)
    fresh = False
    with _cache_lock:
        if _cache["key"] == key:
            return _cache["data"]
        fresh = True
        data = None
        try:
            with io.open(path, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict) and isinstance(raw.get("chapters"), dict):
                data = _clean(raw)
            else:
                print("[arche] secrets.json 에 chapters 가 없습니다")
        except Exception as e:                                  # noqa: BLE001
            print("[arche] secrets.json 을 읽지 못했습니다: %r" % e)
        _cache["key"], _cache["data"] = key, data
    if fresh and data is not None:
        # 고고학자 계정을 바로 만들어 둔다 (리뷰 I5 - 비공개 자료를 올린 순간 이름을 잡아 둬야, 장이 열리기 전에
        # 누가 그 이름으로 가입해 게시판 일지가 통째로 안 올라가는 일이 없다). 잠금 밖에서 (npc_user 가 secrets 를 다시 부른다).
        for role in NPC_ROLES:
            try:
                if str(data.get(role) or "").strip():
                    npc_user(role=role)
            except Exception as e:                              # noqa: BLE001
                print("[arche] 게시판 계정(%s) 만들기 실패: %r" % (role, e))
    return data


SALT_MIN = 16                  # 소금이 이보다 짧으면 준비 안 됨 - 공개 코드(legends_for)로 전설을 미리 셀 수 있다

_LISTS_OF_DICTS = ("journal", "hints", "phenomena")
_LISTS_OF_STR = ("gift", "pages", "images")
_DICTS = ("items", "dig", "post")


def _clean_chapter(n, ch):
    """한 장의 비공개 자료를 앞으로 쓸 모양으로 거른다 (리뷰 I2 - 운영 중 손질하다 모양이 틀려도 state 가 500 이 안 나게).
    틀린 칸은 버리고 남긴 것만 돌려준다. 버린 것은 로그에 적는다."""
    if not isinstance(ch, dict):
        print("[arche] %s 장 자료가 dict 가 아니라 버립니다" % n)
        return None
    out = dict(ch)
    dropped = []
    for k in _LISTS_OF_DICTS:
        if k in out:
            v = out[k] if isinstance(out[k], list) else []
            keep = [x for x in v if isinstance(x, dict)]
            if len(keep) != (len(out[k]) if isinstance(out[k], list) else -1):
                dropped.append(k)
            out[k] = keep
    for k in _LISTS_OF_STR:
        if k in out:
            v = out[k] if isinstance(out[k], list) else []
            keep = [str(x) for x in v if isinstance(x, (str, int))]
            if not isinstance(out[k], list) or len(keep) != len(out[k]):
                dropped.append(k)
            out[k] = keep
    for k in _DICTS:
        if k in out and not isinstance(out[k], dict):
            dropped.append(k)
            out.pop(k)
    keys = out.get("keys")
    if keys is not None:
        good = {}
        for name, kk in (keys.items() if isinstance(keys, dict) else []):
            if isinstance(kk, dict) and isinstance(kk.get("answers"), list):
                good[str(name)] = dict(kk, answers=[str(a) for a in kk["answers"] if isinstance(a, (str, int))])
        if not isinstance(keys, dict) or len(good) != len(keys):
            dropped.append("keys")
        out["keys"] = good
    if "ritual" in out and not isinstance(out["ritual"], dict):
        dropped.append("ritual")
        out.pop("ritual")                          # 의식이 깨졌으면 아무도 못 연다 (열리는 쪽보다 낫다)
    marks = out.get("marks")
    if marks is not None:
        ok = isinstance(marks, list) and all(isinstance(m, list) and all(isinstance(g, int) for g in m) for m in marks)
        if not ok:
            dropped.append("marks")
            out.pop("marks")
    for k in ("caption", "inscription", "photo", "minClient"):
        if k in out and not isinstance(out[k], str):
            dropped.append(k)
            out.pop(k)
    if dropped:
        print("[arche] %s 장 자료에서 모양이 틀린 칸을 버렸습니다: %s" % (n, ", ".join(sorted(set(dropped)))))
    return out


def _clean(raw):
    chs = {}
    for n, ch in (raw.get("chapters") or {}).items():
        c = _clean_chapter(n, ch)
        if c is not None:
            chs[str(n)] = c
    out = dict(raw, chapters=chs)
    if "posts" in out:
        posts = out["posts"] if isinstance(out["posts"], list) else []
        keep = [p for p in posts if isinstance(p, dict) and str(p.get("ref") or "").startswith("arche:")]
        if len(keep) != (len(out["posts"]) if isinstance(out["posts"], list) else -1):
            print("[arche] 예약 글(posts)에서 모양이 틀린 것을 버렸습니다")
        out["posts"] = keep
    return out


def ready():
    s = secrets()
    if s is None:
        return False
    if len(str(s.get("salt") or "")) < SALT_MIN:
        print("[arche] 소금이 %d 글자보다 짧아 이벤트를 열지 않습니다" % SALT_MIN)
        return False
    return True


def _sec(n):
    """n 장의 비공개 자료 (없으면 빈 dict)."""
    ch = ((secrets() or {}).get("chapters") or {}).get(str(n))
    return ch if isinstance(ch, dict) else {}


def _salt():
    return str((secrets() or {}).get("salt") or "")


def title_salt(n):
    """창 제목 해시에 쓰는 소금. **비밀 소금을 그대로 내주지 않는다** - 그것으로는 전설 뽑기(legends_for)를 미리 셀 수 있다."""
    return hashlib.sha256(("arche-title:%s:%d" % (_salt(), int(n))).encode("utf-8")).hexdigest()[:16]


def _open(n, now):
    w = A.window(n)
    return bool(w) and w[0] <= now < w[1]


def _hm(text):
    try:
        h, m = str(text).split(":")
        return int(h) * 60 + int(m)
    except (TypeError, ValueError):
        return None


def _in_span(t, span):
    """KST 시각이 [시작, 끝) 안인가. 끝이 시작보다 이르면 자정을 넘는다."""
    try:
        a, b = _hm(span[0]), _hm(span[1])
    except (TypeError, IndexError, KeyError):
        return False
    if a is None or b is None:
        return False
    k = t.astimezone(KST)
    x = k.hour * 60 + k.minute
    return a <= x < b if a <= b else (x >= a or x < b)


# ---------------------------------------------------------------- 조건
def _types(species):
    return list((deps.dex().get(species) or {}).get("types") or [])


def _party(uid):
    return db.q("SELECT species, held FROM pokemon WHERE user_id=? AND on_desktop=1 ORDER BY slot, id", (uid,))


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _cond(uid, n, c, now):
    """조건 하나가 참인가. 모르는 것 · 깨진 것은 거짓 (설계 '의식과 판정')."""
    if not isinstance(c, dict) or not c:
        return False
    try:
        if "all" in c:
            subs = c.get("all") or []
            return bool(subs) and all(_cond(uid, n, s, now) for s in subs)
        if "any" in c:
            return any(_cond(uid, n, s, now) for s in c.get("any") or [])
        if "key" in c:
            return db.q1("SELECT 1 FROM arche_key WHERE user_id=? AND chapter=? AND key=?",
                         (uid, int(n), str(c["key"]))) is not None
        if "time" in c:
            return _in_span(now, c["time"])
        if "when" in c:
            # 날짜까지 정한 구간 목록 [[시작, 끝], ...] (날마다 다른 정한 때). 하나라도 들면 참, 끝은 안 든다.
            for span in c.get("when") or []:
                try:
                    lo, hi = _parse_kst(span[0]), _parse_kst(span[1])
                except (TypeError, IndexError, KeyError):
                    continue
                if lo is not None and hi is not None and lo <= now < hi:
                    return True
            return False
        if "partyTypes" in c:
            want = list(c["partyTypes"] or [])
            party = _party(uid)
            if not want or len(party) < len(want):
                return False
            return all(t in _types(party[i]["species"]) for i, t in enumerate(want))
        if "partyHas" in c:
            spec = c["partyHas"] or {}
            need = max(1, _int(spec.get("count"), 1))
            hit = 0
            for r in _party(uid):
                if spec.get("type") and spec["type"] not in _types(r["species"]):
                    continue
                if spec.get("held") and (r["held"] or "") != spec["held"]:
                    continue
                hit += 1
            return hit >= need
        if "itemUsed" in c:
            spec = c["itemUsed"] or {}
            since = _iso(now - datetime.timedelta(minutes=_int(spec.get("withinMin"), 10)))
            return db.q1("SELECT 1 FROM arche_use WHERE user_id=? AND item=? AND at>=? AND at<=?",
                         (uid, str(spec.get("item") or ""), since, _iso(now))) is not None
        if "focusRun" in c:
            need = max(1, _int((c["focusRun"] or {}).get("sets"), 1))
            lo = _iso(A.window(n)[0])
            r = db.q1("SELECT MAX(c) m FROM (SELECT COUNT(*) c FROM focus_set WHERE user_id=? AND full=1"
                      " AND at>=? AND at<=? GROUP BY run_id)", (uid, lo, _iso(now)))
            return bool(r and (r["m"] or 0) >= need)
        if "visitMutual" in c:
            since = _iso(now - datetime.timedelta(minutes=_int((c["visitMutual"] or {}).get("withinMin"), 30)))
            # 상대는 이벤트가 시작하기 전에 만든 계정이어야 한다 (혼자 부계정으로 여는 길 막기 - 플레이테스트 11/09)
            return db.q1("SELECT 1 FROM visit_log a JOIN visit_log b ON b.guest=a.host AND b.host=a.guest"
                         " JOIN users p ON p.id=a.host"
                         " WHERE a.guest=? AND a.at>=? AND b.at>=? AND p.created_at<? LIMIT 1",
                         (uid, since, since, _iso(A.event_window()[0]))) is not None
        if "expedition" in c:
            spec = c["expedition"] or {}
            lo, hi = A.window(n)
            rows = db.q("SELECT e.started_at, p.species FROM expedition e LEFT JOIN pokemon p ON p.id=e.pokemon_id"
                        " WHERE e.user_id=? AND e.place=? AND e.started_at>=? AND e.started_at<?",
                        (uid, str(spec.get("place") or ""), _iso(lo), _iso(min(hi, now + datetime.timedelta(seconds=1)))))
            for r in rows:
                if spec.get("type") and spec["type"] not in _types(r["species"]):
                    continue
                if spec.get("time") and not _in_span(_parse(r["started_at"]) or now, spec["time"]):
                    continue
                return True
            return False
    except Exception as e:                                       # noqa: BLE001
        print("[arche] 조건을 보다 실패 %s: %r" % (c, e))
    return False


# ---------------------------------------------------------------- 의식
def _grant(uid, rid, now):
    try:
        season.grant(uid, "title", rid, 0, equip_if_empty=False, now=_iso(now))
    except Exception as e:                                       # noqa: BLE001
        print("[arche] 칭호 실패 %s %s: %r" % (uid, rid, e))


def _record(uid, n, now):
    """의식을 마쳤다고 적는다 (한 번만). 그 장의 첫 사람이면 표시 · 칭호. 여섯 장이면 칭호. 새로 적었으면 True."""
    cur = db.run("INSERT INTO arche_progress (user_id, chapter, ritual_at, first) VALUES (?,?,?,0)"
                 " ON CONFLICT(user_id, chapter) DO NOTHING", (uid, int(n), _iso(now)))
    if not getattr(cur, "rowcount", 1):
        return False
    # 첫 사람은 한 문장으로 - 같은 순간에 둘이 마쳐도 한 사람만 1 이 된다
    cur = db.run("UPDATE arche_progress SET first=1 WHERE user_id=? AND chapter=?"
                 " AND NOT EXISTS (SELECT 1 FROM arche_progress WHERE chapter=? AND first=1)", (uid, int(n), int(n)))
    if getattr(cur, "rowcount", 0):
        _grant(uid, "arche_first", now)
    if db.q1("SELECT COUNT(*) c FROM arche_progress WHERE user_id=?", (uid,))["c"] >= len(A.CHAPTERS):
        _grant(uid, "arche_six", now)
    return True


def check(uid, now=None):
    """지금 열린 장의 의식을 본다. 새로 마친 장 번호 목록 ([] 이거나 [n]).

    **열린 장만** - 닫힌 장은 조건이 맞아도 안 된다. 이미 마쳤으면 조건을 보지도 않는다.
    """
    now = _now(now)
    n = A.chapter_at(now)
    if not n or not ready():
        return []
    ritual = _sec(n).get("ritual")
    if not ritual:
        return []
    if db.q1("SELECT 1 FROM arche_progress WHERE user_id=? AND chapter=?", (uid, n)) is not None:
        return []
    if _cond(uid, n, ritual, now) and _record(uid, n, now):
        return [n]
    return []


# ---------------------------------------------------------------- 열쇠
def submit_key(uid, n, text, via="type", now=None, ip=None):
    """떠오른 말 (via: type = 일지에 적음 / title = 브라우저 창 제목). {ok, key?, new, message, state}.

    시간당 KEY_TRIES_PER_HOUR 번 - 넘으면 맞는 말이어도 429 (마구 넣어 보기 막기). 맞으면 그 자리에서 의식을 본다.
    """
    now = _now(now)
    c = A.chapter(n)
    if c is None:
        raise HTTPException(400, "그런 장은 없어요.")
    n = c["n"]
    if not ready():
        raise HTTPException(409, "고고학자의 일지가 아직 준비 중이에요.")
    if not _open(n, now):
        raise HTTPException(409, "이 장은 지금 열려 있지 않아요.")
    raw = str(text or "")
    if len(raw) > KEY_TEXT_MAX:
        raise HTTPException(400, "말이 너무 길어요 (%d자까지)." % KEY_TEXT_MAX)
    said = A.normalize(raw)
    if not said:
        raise HTTPException(400, "떠오른 말을 적어 주세요.")
    via = via if via in ("type", "title") else "type"
    hour_ago = _iso(now - datetime.timedelta(hours=1))
    db.run("DELETE FROM arche_try WHERE user_id=? AND at<?", (uid, hour_ago))
    # 세기와 적기를 한 문장으로 - 동시에 보내도 한도를 못 넘는다 (게시판 이미지 한도와 같은 틀)
    cur = db.run("INSERT INTO arche_try (user_id, at) SELECT ?, ?"
                 " WHERE (SELECT COUNT(*) FROM arche_try WHERE user_id=? AND at>=?) < ?",
                 (uid, _iso(now), uid, hour_ago, KEY_TRIES_PER_HOUR))
    if not getattr(cur, "rowcount", 1):
        raise HTTPException(429, "너무 많이 적었어요. 한 시간쯤 뒤에 다시 적어 주세요.")
    if ip:
        db.run("DELETE FROM arche_try_ip WHERE at<?", (hour_ago,))
        cur = db.run("INSERT INTO arche_try_ip (ip, at) SELECT ?, ?"
                     " WHERE (SELECT COUNT(*) FROM arche_try_ip WHERE ip=? AND at>=?) < ?",
                     (str(ip), _iso(now), str(ip), hour_ago, KEY_TRIES_PER_IP))
        if not getattr(cur, "rowcount", 1):
            raise HTTPException(429, "너무 많이 적었어요. 한 시간쯤 뒤에 다시 적어 주세요.")
    found = None
    for name, k in (_sec(n).get("keys") or {}).items():
        answers = (k or {}).get("answers") or []
        if any(A.normalize(a) == said for a in answers):
            found = name
            break
    new = False
    if found:
        cur = db.run("INSERT INTO arche_key (user_id, chapter, key, via, at) VALUES (?,?,?,?,?)"
                     " ON CONFLICT(user_id, chapter, key) DO NOTHING", (uid, n, found, via, _iso(now)))
        new = bool(getattr(cur, "rowcount", 1))
        msg = "그 말이 일지에 새겨졌다." if new else "이미 알아낸 말이다."
    else:
        msg = "아무 일도 일어나지 않았다..."
    out = {"ok": bool(found), "new": new, "message": msg, "state": state(uid, now)}
    if found:
        out["key"] = found
    return out


# ---------------------------------------------------------------- state
def _rows_by(sql, args, key):
    return dict((key(r), r) for r in db.q(sql, args))


def _revealed():
    """올라간 실마리 {(장, 번호): 시각} (meta 'arche:hint:<장>:<번호>')."""
    out = {}
    for r in db.q("SELECT k, v FROM meta WHERE k LIKE 'arche:hint:%'"):
        try:
            _a, _b, n, i = r["k"].split(":")
            out[(int(n), int(i))] = r["v"]
        except ValueError:
            continue
    return out


def _journal(n, now, revealed):
    lo = A.window(n)[0]
    out = []
    for j in _sec(n).get("journal") or []:
        try:
            at = lo + datetime.timedelta(hours=float(j.get("after") or 0))
        except (TypeError, ValueError):
            continue
        if at <= now:
            out.append({"at": _iso(at), "text": str(j.get("text") or "")})
    for i, h in enumerate(_sec(n).get("hints") or [], 1):
        if (n, i) in revealed:
            out.append({"at": revealed[(n, i)], "text": str((h or {}).get("text") or ""), "hint": i})
    out.sort(key=lambda x: x["at"])
    return out


def _phenomena(now):
    out = []
    lo, hi = now - datetime.timedelta(seconds=LEAD), now + datetime.timedelta(seconds=LEAD)
    for c in A.CHAPTERS:
        for p in _sec(c["n"]).get("phenomena") or []:
            at = _parse((p or {}).get("at"))
            if at is None:
                continue
            until = at + datetime.timedelta(seconds=max(1, _int(p.get("dur"), 30)))
            if lo <= at <= hi or at <= now < until:
                out.append({"id": str(p.get("id") or _iso(at)), "at": _iso(at), "until": _iso(until),
                            "kind": str(p.get("kind") or ""), "data": p.get("data") or {}})
    out.sort(key=lambda x: x["at"])
    return out


def _kr_of(species):
    sp = deps.dex().get(species) or {}
    return sp.get("kr") or species


def _ball_opts(uid, tb, hour=None):
    """전설 배틀의 볼 목록 (야생 배틀 메뉴와 같은 꼴 - 마스터볼도 들어 있다). 못 만들면 None (앱은 몬스터볼만)."""
    try:
        u = db.q1("SELECT balls FROM users WHERE id=?", (uid,))
        view = dict(tb.foe.mon)
        view["status"] = "SLP" if tb.foe.status == "sleep" else (tb.foe.status or "")
        return items.ball_options(uid, deps.dex(), view, int(u["balls"] if u else 0),
                                  mine=tb.me.mon, turn=tb.turn, hour=hour)
    except Exception as e:                                       # noqa: BLE001
        print("[arche] 볼 목록 실패 %s: %r" % (uid, e))
        return None


def _num_of(species):
    return (deps.dex().get(species) or {}).get("num")


def state(uid, now=None):
    """일지 창 · 컨트롤러가 그리는 것 전부 (계획 'state 모양'). 열린 장의 의식도 여기서 본다 (60초 폴링)."""
    now = _now(now)
    ok = ready()
    if ok:
        try:
            check(uid, now)
        except Exception as e:                                   # noqa: BLE001
            print("[arche] 판정 실패 %s: %r" % (uid, e))
    s, e = A.event_window()
    cur = A.chapter_at(now)
    out = {"active": s <= now < e, "ready": ok, "now": _iso(now), "start": _iso(s), "end": _iso(e),
           "chapter": cur, "poll": POLL, "chapters": [], "phenomena": _phenomena(now) if ok else []}
    mine = _rows_by("SELECT * FROM arche_progress WHERE user_id=?", (uid,), lambda r: r["chapter"]) if ok else {}
    keys = {}
    mons = {}
    solved, firsts, revealed = {}, {}, {}
    if ok:
        for r in db.q("SELECT chapter, key FROM arche_key WHERE user_id=? ORDER BY at", (uid,)):
            keys.setdefault(r["chapter"], []).append(r["key"])
        for r in db.q("SELECT * FROM arche_mon WHERE user_id=?", (uid,)):
            mons[(r["chapter"], r["slot"])] = r
        solved = dict((r["chapter"], r["c"]) for r in db.q(
            "SELECT chapter, COUNT(*) c FROM arche_progress GROUP BY chapter"))
        firsts = dict((r["chapter"], r["username"]) for r in db.q(
            "SELECT p.chapter, u.username FROM arche_progress p JOIN users u ON u.id=p.user_id WHERE p.first=1"))
        revealed = _revealed()
    for c in A.CHAPTERS:
        n = c["n"]
        lo, hi = A.window(n)
        row = {"n": n, "title": c["kr"], "place": c["place"], "placeKr": c["placeKr"],
               "opensAt": _iso(lo), "closesAt": _iso(hi), "open": lo <= now < hi, "past": now >= hi,
               "future": now < lo, "slots": c["slots"]}
        sec = _sec(n)
        if sec.get("minClient"):
            row["minClient"] = str(sec["minClient"])
        if row["future"] or not ok:
            row["journal"] = []
            out["chapters"].append(row)
            continue
        try:
            prog = mine.get(n)
            row.update({"journal": _journal(n, now, revealed), "inscription": sec.get("inscription"),
                        "photo": sec.get("photo") or c["place"],
                        # 일지 사진: 판에 새긴 아르케 글자 번호 · 사진 아래 한 줄 (비공개 데이터 그대로 - 모두 보는 것)
                        "marks": sec.get("marks"), "caption": sec.get("caption"),
                        "ritual": prog is not None, "ritualAt": prog["ritual_at"] if prog else None,
                        "solvers": solved.get(n, 0), "first": firsts.get(n),
                        "keys": keys.get(n, []), "keyCount": len(sec.get("keys") or {})})
            if row["open"] and prog is None:
                have = set(keys.get(n, []))
                salt = title_salt(n)
                hashes = []
                for name, k in (sec.get("keys") or {}).items():
                    if (k or {}).get("title") and name not in have:
                        for a in k.get("answers") or []:
                            # 리뷰 C1: 짧은 답의 해시는 집에서 사전으로 대입해 풀 수 있다 (시간당 20번 한도를 비켜 간다).
                            # 열 글자 아래 답은 창 제목 열쇠로 안 낸다 - 일지에 적는 열쇠로만 받는다.
                            if len(A.normalize(a)) >= TITLE_MIN:
                                hashes.append(A.key_hash(salt, a))
                if hashes:
                    row["titleSalt"], row["titleHashes"] = salt, hashes
            enc = []
            prev_caught = True
            for slot in range(c["slots"]):
                m = mons.get((n, slot))
                e_ = {"slot": slot}
                if m is not None and m["state"] == "caught":
                    e_.update(state="caught", num=_num_of(m["species"]), name=_kr_of(m["species"]),
                              shiny=bool(m["shiny"]))
                elif prog is not None and prev_caught and now < e:
                    e_["state"] = "ready"
                    if m is not None:
                        e_["num"] = _num_of(m["species"])       # 한 번 만나 본 전설
                else:
                    e_["state"] = "locked"
                prev_caught = e_["state"] == "caught"
                enc.append(e_)
            row["encounters"] = enc
        except Exception as e:                               # noqa: BLE001
            # 리뷰 I2: 한 장이 터져도 일지 전체가 500 이 되지 않게 그 장만 빈 채로
            print("[arche] %d 장 state 실패 (uid %s): %r" % (n, uid, e))
            row = {k: row[k] for k in ("n", "title", "place", "placeKr", "opensAt", "closesAt", "open", "past",
                                       "future", "slots") if k in row}
            row.update(journal=[], ritual=False, solvers=0, keys=[], encounters=[])
        out["chapters"].append(row)
    return out


def me_card(uid, now=None):
    """/api/me 에 싣는 짧은 것. 이벤트 일주일 전 ~ 끝난 하루 뒤에만 (그 밖은 None - 질의도 없다).

    앱은 이걸 보고 60초 폴링(GET /api/arche)을 켠다. 여기서 게시글 · 실마리도 본다 (POST_EVERY 초에 한 번).
    """
    now = _now(now)
    s, e = A.event_window()
    if now < s - datetime.timedelta(days=CARD_BEFORE_DAYS) or now >= e + datetime.timedelta(days=CARD_AFTER_DAYS):
        return None
    ok = ready()
    n = A.chapter_at(now)
    out = {"active": s <= now < e, "ready": ok, "chapter": n, "poll": POLL,
           "startsIn": max(0, int((s - now).total_seconds())), "endsIn": max(0, int((e - now).total_seconds()))}
    if ok and n:
        if _sec(n).get("minClient"):
            out["minClient"] = str(_sec(n)["minClient"])
        ensure_posts(now)
    return out


def give_gift(uid, now=None):
    """열린 장의 선물(열쇠 아이템)을 선물함에 넣는다 - 한 사람 · 한 장에 한 번. 넣은 줄 수.

    /api/me 가 items.gift_claim **앞에** 부른다 (같은 요청에서 받는다).
    """
    now = _now(now)
    n = A.chapter_at(now)
    if not n or not ready():
        return 0
    gift = [str(g) for g in (_sec(n).get("gift") or []) if items.get(str(g))]
    if not gift:
        return 0
    if db.q1("SELECT 1 FROM arche_gift WHERE user_id=? AND chapter=?", (uid, n)) is not None:
        return 0                                   # /api/me 마다 쓰기 잠금을 잡지 않는다 (리뷰)
    cur = db.run("INSERT INTO arche_gift (user_id, chapter, at) VALUES (?,?,?)"
                 " ON CONFLICT(user_id, chapter) DO NOTHING", (uid, n, _iso(now)))
    if not getattr(cur, "rowcount", 1):
        return 0
    c = A.chapter(n)
    for g in gift:
        db.run("INSERT INTO gift (user_id, kind, item_id, count, title, message, created_at)"
               " VALUES (?,?,?,?,?,?,?)",
               (uid, "item", g, 1, "고고학자의 꾸러미",
                "「%s」 장과 함께 발굴 현장에서 무언가가 왔다." % c["kr"], _iso(now)))
    return len(gift)


# ---------------------------------------------------------------- 게시글 (고고학자 계정)
_posts_at = [0.0]
_posts_lock = threading.Lock()


def npc_user(now=None, role="npc"):
    """고고학자 계정 (없으면 만든다). **로그인할 수 없다** - 비밀번호 해시가 비어 있어 어떤 비밀번호도 안 맞는다.
    role="traveler" 면 또 다른 게시판 계정 (비공개 자료의 traveler) - 나머지는 같다.

    운영자 목록(BOARD_ADMINS)에 넣지 않는다 - 남의 글을 지우거나 공지를 쓸 수 없다. 도배 제한은 글을
    board.create 가 아니라 여기서 바로 넣어서 비켜 간다 (패치노트 글과 같은 길). 그 이름을 진짜 사람이
    이미 쓰고 있으면 None (남의 이름으로 글을 올리지 않는다).
    """
    role = role if role in NPC_ROLES else "npc"
    name = str((secrets() or {}).get(role) or "").strip()
    if not name:
        print("[arche] 게시판 계정 이름(%s)이 없어 글을 올리지 않습니다" % role)
        return None
    r = db.q1("SELECT id, username, pw_hash FROM users WHERE username=?", (name,))
    if r is None:
        db.run("INSERT OR IGNORE INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at)"
               " VALUES (?,?,?,1,0,0,?)", (name, b"", b"", _iso(_now(now))))
        r = db.q1("SELECT id, username, pw_hash FROM users WHERE username=?", (name,))
    if r is None or len(r["pw_hash"] or b""):
        print("[arche] 고고학자 이름 '%s' 을(를) 진짜 사람이 쓰고 있어 게시판 일지를 올리지 않습니다 - 이름을 바꾸세요" % name)
        return None
    return r


def _attach_images(npc, pid, names, now):
    from . import board
    for pos, name in enumerate(names or []):
        name = str(name)
        if not _IMG_RE.match(name):
            continue
        try:
            with open(_path("img", name), "rb") as f:
                data, fmt, w, h, frames = board.encode_image(f.read())
            cur = db.run("INSERT INTO board_image (user_id, post_id, pos, fmt, w, h, bytes, frames, created_at)"
                         " VALUES (?,?,?,?,?,?,?,?,?)", (npc["id"], pid, pos, fmt, w, h, len(data), frames, _iso(now)))
            path = board._img_path({"id": cur.lastrowid, "fmt": fmt})
            with open(path + ".part", "wb") as f:
                f.write(data)
            os.replace(path + ".part", path)
        except Exception as e:                                   # noqa: BLE001
            print("[arche] 게시글 사진 실패 %s: %r" % (name, e))


def _post(ref, title, body, images, now, role="npc"):
    """고고학자(또는 role 계정) 이름으로 글 하나 (ref 가 이미 있으면 아무것도 안 한다 - 지운 글도 '있는 것'). 올렸으면 True."""
    npc = npc_user(now, role=role)
    if npc is None or not str(body or "").strip():          # 빈칸뿐인 글은 안 올린다 (2.4.0 traveler_posts 와 같게)
        return False
    cur = db.run("INSERT INTO board_post (kind, user_id, author, title, body, created_at, ref)"
                 " SELECT 'free', ?, ?, ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM board_post WHERE ref=?)",
                 (npc["id"], npc["username"], str(title)[:80], str(body), _iso(now), ref, ref))
    if not getattr(cur, "rowcount", 1):
        return False
    if images:
        _attach_images(npc, cur.lastrowid, images, now)
    return True


def _solvers(n):
    return db.q1("SELECT COUNT(*) c FROM arche_progress WHERE chapter=?", (int(n),))["c"]


def _scheduled_posts(now):
    """비공개 자료의 예약 글 중 때가 된 것을 올린다 (ref 마다 한 번). 이벤트 끝난 뒤 하루까지만 본다."""
    sec = secrets() or {}
    if now >= A.event_window()[1] + datetime.timedelta(days=1):
        return
    for p in sec.get("posts") or []:
        try:
            at = _parse(p.get("at"))
            if at is None or now < at:
                continue
            role = str(p.get("by") or "npc")
            _post(str(p["ref"]), str(p.get("title") or "")[:80] or "아르케", str(p.get("body") or ""),
                  p.get("images"), now, role=role if role in NPC_ROLES else "npc")
        except Exception as e:                                   # noqa: BLE001
            print("[arche] 예약 글 실패 %s: %r" % (p.get("ref"), e))


def reserved_name(name):
    """게시판 계정 이름(비공개 자료의 npc · traveler)과 같은 닉네임인가 (빈칸 무시). 가입 · 닉네임 바꾸기에서 막는다."""
    key = str(name or "").replace(" ", "")
    if not key:
        return False
    sec = secrets() or {}
    return any(key == str(sec.get(r) or "").replace(" ", "") for r in NPC_ROLES if sec.get(r))


def ensure_posts(now=None, force=False):
    """열린 장의 일지 글과 실마리 사다리. 요청 때 확인해 한 번만 (프로세스 안에서는 POST_EVERY 초에 한 번).

    · 장 열림 글 ref='arche:<장>' - 비공개 자료의 post.title · post.body (없으면 일지 첫 글) · post.images
    · 예약 글 (비공개 자료 맨 위 posts: {ref, at, by, title, body, images?}) - at 이 지났으면 by 계정(npc · traveler)으로.
      **장과 상관없이** 본다 - 이벤트 전 · 이벤트 끝 무렵 글도 (11/11).
    · 실마리 i 번 ref='arche:<장>:h<i>' - 장이 열리고 after 시간이 지났는데 의식을 마친 사람이 minSolvers 보다 적으면.
      일지에 올라간 것은 meta 'arche:hint:<장>:<i>' 로 적는다 (게시판 글이 안 올라가도 일지에는 남는다).
      닫힌 장에는 더 안 올린다. 단계마다 따로 본다 (앞 단계가 필요 없었으면 건너뛴다).
    """
    now = _now(now)
    if not force and time.monotonic() - _posts_at[0] < POST_EVERY:
        return
    if not _posts_lock.acquire(blocking=False):
        return
    try:
        _posts_at[0] = time.monotonic()
        _scheduled_posts(now)
        n = A.chapter_at(now)
        if not n or not ready():
            return
        sec = _sec(n)
        c = A.chapter(n)
        post = sec.get("post") or {}
        title = post.get("title") or "발굴 일지 · %s" % c["kr"]
        body = post.get("body") or "\n\n".join(str(j.get("text") or "") for j in sec.get("journal") or []
                                               if _int(j.get("after"), 0) <= 0)
        _post("arche:%d" % n, title, body, post.get("images"), now)
        lo = A.window(n)[0]
        solvers = None
        for i, h in enumerate(sec.get("hints") or [], 1):
            h = h or {}
            try:
                due = lo + datetime.timedelta(hours=float(h.get("after") or 0))
            except (TypeError, ValueError):
                continue
            if now < due:
                continue
            if solvers is None:
                solvers = _solvers(n)
            if solvers >= _int(h.get("minSolvers"), 0):
                continue
            cur = db.run("INSERT INTO meta (k, v) VALUES (?,?) ON CONFLICT(k) DO NOTHING",
                         ("arche:hint:%d:%d" % (n, i), _iso(now)))
            if not getattr(cur, "rowcount", 1):
                continue
            _post("arche:%d:h%d" % (n, i), h.get("title") or "%s · 덧붙임 %d" % (title, i),
                  str(h.get("text") or ""), h.get("images"), now)
    except Exception as e:                                       # noqa: BLE001
        print("[arche] 게시글 실패: %r" % e)
    finally:
        _posts_lock.release()


# ---------------------------------------------------------------- 숨은 페이지 · 그림
_SLUG_RE = re.compile(r"^[a-z0-9-]{4,40}$")
_IMG_RE = re.compile(r"^[a-z0-9-]+\.png$")


def _asset_chapter(kind, name):
    """이 그림 · 페이지를 쓰는 장 (비공개 자료의 pages / images / post.images · 힌트 images). 어느 장에도 없으면 None."""
    for key, ch in ((secrets() or {}).get("chapters") or {}).items():
        if kind == "page":
            names = ch.get("pages") or []
        else:
            names = list(ch.get("images") or []) + list((ch.get("post") or {}).get("images") or [])
            for h in ch.get("hints") or []:
                names += [str(x) for x in (h.get("images") or []) if isinstance(x, (str, int))]
        if name in names:
            try:
                return int(key)
            except ValueError:
                return None
    return None


def _asset_open(kind, name, now):
    """리뷰 I4: 그 장이 열린 뒤에만 내준다 (이름을 짐작해 다음 장 것을 미리 받지 못하게). 어느 장에도 없으면 안 준다."""
    n = _asset_chapter(kind, name)
    return n is not None and A.chapter(n) is not None and _now(now) >= A.window(n)[0]


def page_path(slug, now=None):
    """숨은 페이지 파일 (없거나 이름이 틀리거나 그 장이 아직이면 None)."""
    if not _SLUG_RE.match(str(slug or "")) or not _asset_open("page", slug, now):
        return None
    p = _path("pages", slug + ".html")
    return p if os.path.isfile(p) else None


def img_path(name, now=None):
    if not _IMG_RE.match(str(name or "")) or not _asset_open("img", name, now):
        return None
    p = _path("img", name)
    return p if os.path.isfile(p) else None


# ---------------------------------------------------------------- 아이템 · 발굴지
def item_desc(item_id, now=None):
    """열쇠 아이템 설명을 비공개 자료의 것으로 덮는다 (열린 장까지 중 가장 늦은 장의 것). 없으면 None (기본 설명)."""
    if not str(item_id or "").startswith("ARCHE") or not ready():
        return None
    now = _now(now)
    out = None
    for c in A.CHAPTERS:
        if now < A.window(c["n"])[0]:
            break
        d = (_sec(c["n"]).get("items") or {}).get(item_id)
        if d:
            out = str(d)
    return out


def use_item(uid, item_id, now=None):
    """가방에서 열쇠 아이템을 '쓴다' - 없어지지 않는다 (keep). 쓴 때를 적고 의식을 본다 (조건 itemUsed)."""
    now = _now(now)
    it = items.get(item_id) or {}
    # 쉬는 시간 (비공개 자료의 그 장 cooldown, 분): 한 번 울리면 그동안 조용하다 - 아무 때나 계속 써서 시간 창을
    # 맞히는 길 막기 (플레이테스트 11/09). 쉬는 동안 쓴 것은 적지 않는다.
    n_open = A.chapter_at(now)
    cool = _int(((_sec(n_open).get("cooldown") or {}) if n_open else {}).get(item_id), 0)
    if cool > 0:
        last = db.q1("SELECT at FROM arche_use WHERE user_id=? AND item=? ORDER BY at DESC LIMIT 1", (uid, item_id))
        if last is not None and _parse(last["at"]) and _parse(last["at"]) > now - datetime.timedelta(minutes=cool):
            return {"ok": False, "keep": True, "arche": {"ritual": []},
                    "message": korean.natural("%s 은(는) 아직 조용하다. 한 번 울리면 한동안 소리를 내지 않는 것 같다."
                                              % (it.get("kr") or item_id))}
    db.run("DELETE FROM arche_use WHERE user_id=? AND at<?", (uid, _iso(now - datetime.timedelta(days=2))))
    db.run("INSERT INTO arche_use (user_id, item, at) VALUES (?,?,?)", (uid, item_id, _iso(now)))
    done = check(uid, now)
    msg = "%s 을(를) 꺼내 들었다. 희미하게 무언가가 울린다..." % (it.get("kr") or item_id)
    if done:
        msg += " 봉인이 반응했다!"
    return {"ok": True, "keep": True, "message": korean.natural(msg), "arche": {"ritual": done}}


def dig_report(at):
    """'아르케 발굴지' 에서 돌아온 시각(at)의 발굴 보고서 한 줄 (그 장의 비공개 dig). 없으면 None.

    dig 의 열쇠: "H" (그 시) · "H-H" (앞은 들고 끝은 안 든다, 자정을 넘어도 된다) · "*" (나머지). 파일 차례대로 처음 맞는 것.
    """
    at = _parse(at) if isinstance(at, str) else at
    if at is None or not ready():
        return None
    n = A.chapter_at(at)
    if not n:
        return None
    dig = _sec(n).get("dig") or {}
    hour = at.astimezone(KST).hour
    for k, text in dig.items():
        k = str(k).strip()
        if k == "*":
            continue
        try:
            if "-" in k:
                a, b = (int(x) for x in k.split("-", 1))
                hit = a <= hour < b if a <= b else (hour >= a or hour < b)
            else:
                hit = hour == int(k)
        except ValueError:
            continue
        if hit:
            return str(text)
    return str(dig["*"]) if dig.get("*") else None


# ---------------------------------------------------------------- 칭호 목록
def title_rows(now=None):
    """도감 탭 '칭호' 목록에 올릴 것. (id, 묶음, 조건, 지금 얻을 수 있나) - olympics.title_rows 와 같은 꼴."""
    is_open = _now(now) < A.event_window()[1]
    group = "아르케의 여섯 봉인" if is_open else "지난 이벤트 (다시 얻을 수 없음)"
    return [("arche_first", group, "어느 장이든 가장 먼저 의식을 마치기", is_open),
            ("arche_six", group, "여섯 장의 의식을 모두 마치기", is_open)]


# ---------------------------------------------------------------- 전설 배틀
def is_arche(region):
    return str(region or "").startswith(PREFIX)


def region_of(n, slot):
    return "%s%d:%d" % (PREFIX, int(n), int(slot))


def parse(region):
    """"arche:1:2" -> (1, 2). 아니면 None."""
    if not is_arche(region):
        return None
    try:
        _p, n, slot = str(region).split(":")
        return int(n), int(slot)
    except ValueError:
        return None


def legend_species(uid, n, slot):
    """그 사람 · 장 · 자리의 전설 (내부 이름). 없으면 None."""
    nums = A.legends_for(uid, n, _salt())
    if not 0 <= int(slot) < len(nums):
        return None
    sp = deps.dex().by_num.get(nums[int(slot)])
    return sp["internal"] if sp else None


def legend_mon(uid, n, slot, species, level):
    """전설 한 마리 (포켓몬 dict). 개체값 셋만 31 · 성격 · 특성(숨은 특성 확률 그대로) · 이로치 확률 그대로 · 노력치 0 ·
    도구 없음 · 기술 = 그 레벨 기본. **레벨 말고는 사람 · 장 · 자리로 정해진다** (판을 다시 열어도 같다)."""
    sp = deps.dex().get(species)
    seed = int(hashlib.sha256(("arche-mon:%s:%d:%d:%d" % (_salt(), int(uid), int(n), int(slot))).encode("utf-8"))
               .hexdigest(), 16)
    rng = random.Random(seed)
    perfect = set(rng.sample(list(P.STATS), PERFECT_IVS))
    ivs = dict((s, P.IV_MAX if s in perfect else rng.randint(0, P.IV_MAX)) for s in P.STATS)
    mon = P.make_pokemon(sp, level, rng, shiny_rate=config.SHINY_RATE, ivs=ivs)
    mon["held"] = None
    return mon


def legend_trainer(uid, n, slot, species, level):
    """TrainerBattle 이 먹는 꼴 (boss.legend_trainer 를 본떴다). 트레이너가 없는 판이라 이름 · 역할에 포켓몬을 적는다."""
    sp = deps.dex().get(species) or {}
    return {"id": "arche:" + species, "name": sp.get("kr") or species, "role": "전설의 포켓몬", "sprite": None,
            "level": level, "wild": True, "noMega": True, "team": [legend_mon(uid, n, slot, species, level)]}


def _busy_name(region):
    from . import boss, guild_war, gym
    if is_arche(region):
        return "아르케의 전설"
    if boss.is_boss(region):
        return "악당"
    if guild_war.is_war(region):
        return "길드전 상대"
    return (gym.trainer_at(region) or {}).get("name") or "다른 트레이너"


def start_battle(uid, n, slot, now=None):
    """전설과의 판을 연다 (같은 자리의 판이 열려 있으면 이어서). 관장 판 _out 꼴 + {place, placeKr, legend, chapter, slot}."""
    from . import gimmick, gym_routes, mega, pvp
    now = _now(now)
    c = A.chapter(n)
    if c is None or not 0 <= _int(slot, -1) < c["slots"]:
        raise HTTPException(400, "그런 자리는 없어요.")
    n, slot = c["n"], int(slot)
    if not ready():
        raise HTTPException(409, "고고학자의 일지가 아직 준비 중이에요.")
    if now >= A.event_window()[1]:
        raise HTTPException(409, "아르케의 봉인은 다시 닫혔어요. 이벤트가 끝났어요.")
    if db.q1("SELECT 1 FROM arche_progress WHERE user_id=? AND chapter=?", (uid, n)) is None:
        raise HTTPException(409, "아직 이 장의 봉인이 풀리지 않았어요.")
    mons = dict((r["slot"], r) for r in db.q("SELECT * FROM arche_mon WHERE user_id=? AND chapter=?", (uid, n)))
    # 리뷰 I3: 남은 판부터 본다. 잡힌 자리에 열려 있는 판(두 번 열렸던 창 · 겹친 요청)은 접는다 -
    # 안 접으면 그 판이 한 시간 동안 관장 · 악당 시작을 막는데, '이미 잡았어요' 때문에 들어가 끝낼 길도 없다.
    stale = gym_routes._active(uid)
    if stale is not None and is_arche(stale["region"]):
        got = parse(stale["region"])
        done = got and db.q1("SELECT state FROM arche_mon WHERE user_id=? AND chapter=? AND slot=?",
                             (uid, got[0], got[1]))
        if done is not None and done and done["state"] == "caught":
            db.run("UPDATE gym_battle SET state='done', result='expired' WHERE id=? AND state='active'", (stale["id"],))
    if mons.get(slot) is not None and mons[slot]["state"] == "caught":
        raise HTTPException(409, "이 자리의 전설은 이미 잡았어요.")
    if any((mons.get(k) is None or mons[k]["state"] != "caught") for k in range(slot)):
        raise HTTPException(409, "앞 자리의 전설을 먼저 잡아야 더 안쪽으로 들어갈 수 있어요.")
    region = region_of(n, slot)
    extra = {"place": c["place"], "placeKr": c["placeKr"], "chapter": n, "slot": slot}
    old = gym_routes._active(uid)
    if old:
        if old["region"] != region:
            raise HTTPException(409, "%s 과(와)의 승부가 아직 끝나지 않았습니다." % _busy_name(old["region"]))
        tb = TB.TrainerBattle.load(deps.dex(), json.loads(old["data"]))
        extra.update(resumed=True, legend=_num_of(str(old["trainer"]).split(":", 1)[-1]),
                     ballOptions=_ball_opts(uid, tb))
        return gym_routes._out(old, tb, extra=extra)
    desk = gym_routes._party(uid)
    party, benched = pvp.split_restricted(desk)
    if not party:
        raise HTTPException(409, "데리고 다니는 포켓몬이 없습니다.")
    species = legend_species(uid, n, slot)
    if not species:
        raise HTTPException(500, "전설을 찾지 못했어요.")
    # 레벨 = 내 포켓몬 **전체**(박스 포함)의 최고 레벨 - 바탕화면에 약한 포켓몬만 두고 약한 전설을 부르는 길 막기
    top = db.q1("SELECT MAX(level) lv FROM pokemon WHERE user_id=?", (uid,))
    level = max([int(m.get("level") or 1) for m in desk] + [int((top["lv"] if top else 0) or 0), 1])
    tb = TB.TrainerBattle(deps.dex(), party, legend_trainer(uid, n, slot, species, level), random.Random())
    tb.keystone["me"] = mega.has_keystone(uid)
    tb.zring["me"] = gimmick.has_zring(uid)
    events = tb.start()
    if benched:
        at = 1 if events and events[0].get("t") == "intro" else 0
        events.insert(at, {"t": "note", "text": pvp.bench_note(benched, party)})
    db.run("INSERT INTO arche_mon (user_id, chapter, slot, species, state) VALUES (?,?,?,?,'met')"
           " ON CONFLICT(user_id, chapter, slot) DO NOTHING", (uid, n, slot, species))
    cur = db.run("INSERT INTO gym_battle (user_id, region, trainer, state, turn, rev, data, created_at, updated_at)"
                 " VALUES (?,?,?,?,?,?,?,?,?)",
                 (uid, region, "arche:" + species, "active", 0, 0, json.dumps(tb.dump()), _iso(now),
                  datetime.datetime.now(UTC).isoformat()))
    row = db.q1("SELECT * FROM gym_battle WHERE id=?", (cur.lastrowid,))
    extra["legend"] = _num_of(species)
    extra["ballOptions"] = _ball_opts(uid, tb)
    return gym_routes._out(row, tb, events, extra)


MISS = ["앗! 포켓몬이 튀어나와버렸다!", "이런! 포켓몬이 볼에서 나와버렸다!",
        "아앗! 조금만 더 하면 잡을 수 있었는데!", "아깝다! 다 잡았다고 생각했는데!"]


def throw_ball(uid, user, row, tb, want, hour=None):
    """아르케 판에서 볼을 던진다 (gym_routes.act 의 kind=ball). 관장 판 _out 꼴 + {caught, shakes, message, ball, balls,
    pokemon?, where?}. 놓치면 전설만 한 턴 움직인다 (act("pass")). 잡으면 판 끝 · 그 자리 끝."""
    from . import achievements, auth, battle_routes, gym_routes
    got = parse(row["region"])
    if not got:
        raise HTTPException(409, "이 승부에서는 볼을 던질 수 없습니다.")
    n, slot = got
    if tb.need_switch:
        raise HTTPException(409, "다음 포켓몬을 먼저 골라 주세요.")
    # 리뷰 I1: 두 턴 기술을 모으는 중 · 숨은 중(구멍파기 · 공중날기) · 반동 · 날뛰는 중에는 가방을 못 쓴다 (본가와 같다).
    # 안 막으면 숨은 채로 볼만 던져 전설의 공격을 한 대도 안 맞고 잡을 수 있었다.
    if SM.must_stay(tb.me) or (tb.me.cond or {}).get("invuln"):
        raise HTTPException(409, "%s 이(가) 기술을 쓰는 중이라 지금은 볼을 던질 수 없다!" % tb.me.name)
    foe = tb.foe
    if not foe.alive():
        raise HTTPException(409, "상대가 이미 쓰러졌습니다.")
    done = db.q1("SELECT state FROM arche_mon WHERE user_id=? AND chapter=? AND slot=?", (uid, n, slot))
    if done is not None and done["state"] == "caught":
        raise HTTPException(409, "이 자리의 전설은 이미 잡았어요.")
    d = deps.dex()
    wild_view = dict(foe.mon)
    wild_view["status"] = "SLP" if foe.status == "sleep" else (foe.status or "")
    ball, bonus, balls = battle_routes._take_ball(uid, user["balls"], want, wild_view, tb.me.mon, tb.turn, hour)
    sp = achievements.catch_species(d.get(foe.mon["species"])) or {}
    sp = dict(sp, catch=max(CATCH_FLOOR, int(sp.get("catch") or 0)))
    hp_ratio = foe.hp / float(foe.maxhp) if foe.maxhp else 1.0
    status_bonus = 2.0 if foe.status in ("sleep", "freeze") else \
        (1.5 if foe.status in ("paralysis", "poison", "burn") else 1.0)
    hidden = bool((foe.cond or {}).get("invuln"))
    if hidden:
        caught, shakes = False, 0                      # 하늘 · 땅속 · 물속에 숨은 전설에게는 볼이 빗나간다 (마스터볼도)
    else:
        caught, shakes = P.catch_attempt(sp, foe.mon, tb.rng, bonus, hp_ratio, status_bonus)
    extra = {"caught": caught, "shakes": shakes, "ball": ball, "balls": balls}
    if not caught:
        msg = "볼이 빗나갔다! %s 은(는) 보이지 않는 곳에 있다." % foe.name if hidden else MISS[min(shakes, 3)]
        kos_before = len(tb.kos)
        events = [{"t": "ball", "ball": ball, "shakes": shakes, "caught": False, "text": msg}] + tb.act("pass")
        state_ = "done" if tb.over else "active"
        cur = db.run("UPDATE gym_battle SET data=?, turn=?, rev=rev+1, state=?, result=?, updated_at=?"
                     " WHERE id=? AND rev=?", (json.dumps(tb.dump()), tb.turn, state_, tb.result,
                                               datetime.datetime.now(UTC).isoformat(), row["id"], row["rev"]))
        if getattr(cur, "rowcount", 1) == 0:
            raise HTTPException(409, "다른 곳에서 먼저 움직였습니다. 다시 불러오세요.")
        # 전설을 쓰러뜨려도 경험치는 없다 (리뷰: 끝까지 다시 도전할 수 있어 경험치 밭이 된다 - 받는 것은 잡은 전설 + 칭호)
        extra["message"] = msg
        extra["ballOptions"] = _ball_opts(uid, tb, hour)       # 타이머볼처럼 턴마다 배율이 바뀐다
        if tb.over:
            extra["reward"] = on_end(uid, row, tb)
        row = db.q1("SELECT * FROM gym_battle WHERE id=?", (row["id"],))
        return gym_routes._out(row, tb, events, extra)

    # 잡았다. 판을 먼저 닫는다 (rev - 같은 판에 두 요청이 겹치면 하나만), 그다음 자리를 닫는다 (한 자리 한 번).
    tb.over, tb.result = True, "caught"
    cur = db.run("UPDATE gym_battle SET data=?, turn=?, rev=rev+1, state='done', result='caught', updated_at=?"
                 " WHERE id=? AND rev=? AND state='active'",
                 (json.dumps(tb.dump()), tb.turn, datetime.datetime.now(UTC).isoformat(), row["id"], row["rev"]))
    if getattr(cur, "rowcount", 1) == 0:
        raise HTTPException(409, "다른 곳에서 먼저 움직였습니다. 다시 불러오세요.")
    now = _now()
    mon = dict((k, v) for k, v in foe.mon.items() if not str(k).startswith("_") and k != "id")
    happy = items.ball_extra(ball).get("happiness")
    if happy:
        mon["happiness"] = happy
    cur = db.run("UPDATE arche_mon SET state='caught', shiny=?, caught_at=? WHERE user_id=? AND chapter=? AND slot=?"
                 " AND state<>'caught'", (1 if mon.get("shiny") else 0, _iso(now), uid, n, slot))
    if getattr(cur, "rowcount", 1) == 0:
        raise HTTPException(409, "이 자리의 전설은 이미 잡았어요.")
    caught_mon, where = battle_routes.store_caught(uid, mon)
    db.run("UPDATE arche_mon SET pokemon_id=? WHERE user_id=? AND chapter=? AND slot=?",
           (caught_mon.get("id"), uid, n, slot))
    items.mark_seen(uid, mon["species"], True, auth.now_iso())
    try:
        achievements.on_obtain(uid, mon, "catch", ball=ball)
    except Exception as e:                                       # noqa: BLE001
        print("[arche] 업적 실패 %s: %r" % (uid, e))
    msg = "신난다! %s 을(를) 잡았다!" % foe.name
    if where == "box":
        msg += " 자리가 없어서 PC 박스로 보냈다."
    c = A.chapter(n)
    nxt = {"chapter": n, "slot": slot + 1} if slot + 1 < c["slots"] else None
    extra.update(message=msg, pokemon=caught_mon, where=where, next=nxt)
    events = [{"t": "ball", "ball": ball, "shakes": shakes, "caught": True, "text": msg},
              {"t": "over", "result": "caught", "text": msg}]
    row = db.q1("SELECT * FROM gym_battle WHERE id=?", (row["id"],))
    return gym_routes._out(row, tb, events, extra)


def on_end(uid, row, tb):
    """아르케 판이 볼 말고 끝났다 (쓰러뜨림 · 짐 · 도망). 그 판만 끝 - 이벤트 끝까지 다시 도전할 수 있다. 상금은 없다."""
    name = (tb.trainer or {}).get("name") or "전설의 포켓몬"
    got = parse(row["region"]) or (1, 0)
    word = PLACE_WORD.get((A.chapter(got[0]) or {}).get("place"), "봉인")
    if tb.result == "won":
        lines = ["%s 은(는) 쓰러져 %s 깊은 곳으로 모습을 감췄다..." % (name, word),
                 "봉인은 그대로다. 이벤트가 끝날 때까지 다시 도전할 수 있다."]
    else:
        lines = ["%s 은(는) 아직 %s에 머물러 있다." % (name, word),
                 "다시 도전할 수 있다."]
    return {"lines": [korean.natural(x) for x in lines], "arche": True, "result": tb.result}
