# -*- coding: utf-8 -*-
"""서버 API 통합 테스트.

    python server/test_server.py [http://127.0.0.1:8787]

임시 계정을 만들고 끝나면 전부 지운다. 기존 데이터는 건드리지 않는다.
"""
import json
import random
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787").rstrip("/")
OK = FAIL = 0


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            return r.status, json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def chk(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % label)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (label, detail))


def section(t):
    print("")
    print("=== %s ===" % t)


def main():
    user = "t%06d" % random.randrange(1000000)
    pw = "testpass1234"
    dev = "testdevice-%d" % random.randrange(10000)

    section("공개 엔드포인트")
    st, h = call("GET", "/api/health")
    chk("health 200", st == 200, h)
    chk("도감 1025종 (1~9세대 전부)", h.get("species") == 1025, h.get("species"))
    chk("야생 등장 890종 이상", (h.get("spawnable") or 0) >= 890, h.get("spawnable"))
    print("       서버가 보는 IP: %s (실제 IP 보임: %s)"
          % (h.get("observedIp"), h.get("ipVisible")))
    st, dex = call("GET", "/api/pokedex")
    chk("도감 내려받기", st == 200 and len(dex.get("species", [])) == 1025,
        len(dex.get("species", [])) if st == 200 else st)
    dexmap = dict((s["internal"], s) for s in dex.get("species", []))

    section("정석 데이터 검증 (포켓몬 위키 대조)")
    for k, kr, types in [("PIKACHU", "피카츄", ["ELECTRIC"]),
                         ("CHARIZARD", "리자몽", ["FIRE", "FLYING"]),
                         ("GENGAR", "팬텀", ["GHOST", "POISON"]),
                         ("SYLVEON", "님피아", ["FAIRY"])]:
        s = dexmap.get(k, {})
        chk("%s 타입 %s" % (kr, "/".join(types)),
            s.get("types") == types and s.get("kr") == kr,
            (s.get("kr"), s.get("types")))
    s = dexmap.get("PIKACHU", {})
    chk("피카츄 종족값 35/55/40/50/50/90",
        [s["base"][x] for x in ("hp", "atk", "def", "spa", "spd", "spe")]
        == [35, 55, 40, 50, 50, 90], s.get("base"))

    section("스타팅 목록")
    st, sdata = call("GET", "/api/starters")
    gens = sdata.get("generations", [])
    chk("9세대 전부 있음", st == 200 and len(gens) == 9, len(gens))
    chk("세대마다 3마리", all(len(g["pokemon"]) == 3 for g in gens),
        [len(g["pokemon"]) for g in gens])
    chk("전부 한글 이름", all(p["kr"] for g in gens for p in g["pokemon"]), "")
    chk("전부 도감 번호 있음", all(p["num"] for g in gens for p in g["pokemon"]), "")

    section("IP 위조 차단")
    # 프록시를 신뢰하지 않도록 설정된 상태(개발/도커 기본)에서는
    # 클라이언트가 어떤 헤더를 넣어 보내도 무시해야 한다.
    import urllib.request as _r
    base_ip = call("GET", "/api/whoami")[1].get("ip")
    for hdr, val in [("X-Forwarded-For", "203.0.113.77"),
                     ("X-Real-IP", "198.51.100.9")]:
        rq = _r.Request(BASE + "/api/whoami")
        rq.add_header(hdr, val)
        try:
            with _r.urlopen(rq, timeout=15) as rr:
                got = json.loads(rr.read().decode("utf-8")).get("ip")
        except Exception as e:
            got = "오류 %s" % e
        chk("%s 헤더를 넣어도 IP 가 안 바뀜" % hdr, got == base_ip, (base_ip, got))

    section("정식 도트 내려받기")
    import urllib.request as _u
    for num, kr in [(25, "피카츄"), (94, "팬텀"), (906, "나오하")]:
        try:
            with _u.urlopen(BASE + "/api/sprite/%d" % num, timeout=40) as rr:
                blob = rr.read()
                ext = rr.headers.get("X-Sprite-Ext")
            chk("%s 도트 (%s, %dKB)" % (kr, ext, len(blob) // 1024),
                len(blob) > 500 and (blob[:3] == b"GIF" or blob[1:4] == b"PNG"),
                len(blob))
        except Exception as e:
            chk("%s 도트" % kr, False, e)
    try:
        with _u.urlopen(BASE + "/api/sprite/25?shiny=true", timeout=40) as rr:
            sh = rr.read()
        chk("이로치 도트가 일반과 다름", len(sh) > 500 and sh != blob, len(sh))
    except Exception as e:
        chk("이로치 도트", False, e)

    section("회원가입 (5세대 주리비얀 선택)")
    st, r = call("POST", "/api/auth/register",
                 {"username": user, "password": pw, "device": dev,
                  "starter": "SNIVY"})
    chk("가입 성공", st == 200 and r.get("token"), r)
    token = r.get("token")
    chk("몬스터볼 10개 지급", r.get("balls") == 10, r.get("balls"))
    st, r2 = call("POST", "/api/auth/register",
                  {"username": user, "password": pw})
    chk("같은 아이디 재가입 거부(409)", st == 409, st)
    st, r3 = call("POST", "/api/auth/register",
                  {"username": "u%d" % random.randrange(99999), "password": "short"})
    chk("짧은 비밀번호 거부(400)", st == 400, st)

    st, p = call("GET", "/api/pokemon", token=token)
    mons = p.get("pokemon", [])
    chk("스타팅 1마리 지급", len(mons) == 1, len(mons))
    if mons:
        m = mons[0]
        chk("고른 대로 주리비얀", m["species"] == "SNIVY", m["species"])
        chk("한글 이름 주리비얀", m["info"]["species"] == "주리비얀", m["info"]["species"])
        chk("레벨 5", m["level"] == 5, m["level"])
        chk("바탕화면에 나와 있음", m["onDesktop"] is True, m["onDesktop"])
        chk("개체값 0~31", all(0 <= v <= 31 for v in m["ivs"].values()), m["ivs"])
        chk("능력치 6종", len(m["info"]["stats"]) == 6, m["info"]["stats"])
    st, meinfo = call("GET", "/api/me", token=token)
    chk("me 에 볼 개수 표시", meinfo.get("balls") == 10, meinfo.get("balls"))

    section("로그인 / 자동 로그인")
    st, r = call("POST", "/api/auth/login",
                 {"username": user, "password": "wrongpass123"})
    chk("틀린 비밀번호 거부(401)", st == 401, st)
    st, r = call("POST", "/api/auth/login",
                 {"username": user, "password": pw, "device": dev})
    chk("로그인 성공", st == 200 and r.get("token"), r)
    token = r["token"]
    st, r = call("POST", "/api/auth/auto", {"token": token, "device": dev})
    chk("자동 로그인 성공", st == 200, r)
    st, r = call("POST", "/api/auth/auto", {"token": token, "device": "other-device"})
    chk("다른 기기면 거부(401)", st == 401, st)
    st, r = call("GET", "/api/me", token="not-a-real-token")
    chk("잘못된 토큰 거부(401)", st == 401, st)
    st, r = call("GET", "/api/me")
    chk("토큰 없이 거부(401)", st == 401, st)

    section("야생 조우 — 풀숲")
    st, w = call("GET", "/api/wild?force=true", token=token)
    chk("풀숲 생성됨", st == 200 and w.get("wild"), w)
    wild = w.get("wild") or {}
    wid = wild.get("id")
    chk("상태가 grass", wild.get("state") == "grass", wild.get("state"))
    chk("풀숲 단계에선 어떤 포켓몬인지 숨김", "pokemon" not in wild,
        list(wild.keys()))
    chk("다음 조우 시각 있음", bool(w.get("nextAt")), w.get("nextAt"))

    section("야생 조우 — 모습 드러내기")
    st, r = call("POST", "/api/wild/%d/reveal" % wid, {}, token)
    chk("공개 성공", st == 200, r)
    wm = (r.get("wild") or {}).get("pokemon") or {}
    chk("포켓몬 정보 나옴", bool(wm.get("species")), wm.get("species"))
    chk("야생 표시 있음", wm.get("wild") is True, wm.get("wild"))
    chk("전설이 아님", not dexmap.get(wm.get("species"), {}).get("legendary"),
        wm.get("species"))
    chk("레벨 2~12", 2 <= wm.get("level", 0) <= 12, wm.get("level"))
    # 야생 id 와 보유 id 는 다른 테이블이라 번호가 겹칠 수 있다.
    # 잡기 전에는 보유 수가 늘지 않았는지로 확인한다.
    owned_now = call("GET", "/api/pokemon", token=token)[1]["pokemon"]
    chk("잡기 전에는 내 것이 아님 (보유 수 그대로)", len(owned_now) == 1, len(owned_now))
    print("       만난 포켓몬: %s Lv.%s (%s)"
          % (wm["info"]["species"], wm["level"], "/".join(wm["info"]["types"])))

    section("몬스터볼 던지기")
    balls_before = 10
    caught = None
    throws = 0
    for i in range(10):
        st, r = call("POST", "/api/wild/%d/catch" % wid, {"ball": "POKEBALL"}, token)
        if st != 200:
            chk("던지기 %d회차 실패" % (i + 1), False, r)
            break
        throws += 1
        if r.get("caught"):
            caught = r
            break
        if r.get("balls", 0) <= 0:
            break
    chk("볼이 실제로 줄어듦", throws > 0, throws)
    st, meinfo = call("GET", "/api/me", token=token)
    chk("남은 볼 = 10 - 던진 횟수", meinfo.get("balls") == balls_before - throws,
        (meinfo.get("balls"), throws))
    if caught:
        print("       %s (%d번 던져서 잡음)" % (caught.get("message"), throws))
        chk("잡은 포켓몬이 내 목록에 들어감",
            any(m["species"] == wm["species"]
                for m in call("GET", "/api/pokemon", token=token)[1]["pokemon"]), "")
        chk("잡은 개체값이 만났을 때와 같음",
            caught["pokemon"]["ivs"] == wm["ivs"],
            (caught["pokemon"]["ivs"], wm["ivs"]))
    else:
        print("       10번 다 던졌지만 놓쳤습니다 (확률상 정상)")
        st, r = call("POST", "/api/wild/%d/catch" % wid, {}, token)
        chk("볼이 없으면 거부(409)", st == 409, st)

    section("야생 조우 — 규칙 확인")
    st, w = call("GET", "/api/wild", token=token)
    chk("잡은 뒤에는 바로 다음 풀숲이 안 생김",
        w.get("wild") is None and w.get("nextInSeconds", 0) > 60,
        (w.get("wild"), w.get("nextInSeconds")))
    st, r = call("POST", "/api/wild/999999/reveal", {}, token)
    chk("없는 풀숲 공개 거부(404)", st == 404, st)
    st, r = call("POST", "/api/wild/999999/catch", {}, token)
    chk("없는 야생에 던지기 거부(404)", st == 404, st)

    section("야생 다수 표본 — 전설이 절대 안 나오는지")
    species_seen, legend = set(), []
    for _ in range(40):
        st, w = call("GET", "/api/wild?force=true", token=token)
        wd = (w or {}).get("wild")
        if not wd:
            continue
        st, r = call("POST", "/api/wild/%d/reveal" % wd["id"], {}, token)
        mm = (r.get("wild") or {}).get("pokemon") or {}
        if mm.get("species"):
            species_seen.add(mm["species"])
            if dexmap.get(mm["species"], {}).get("legendary"):
                legend.append(mm["species"])
        call("POST", "/api/wild/%d/flee" % wd["id"], {}, token)
    chk("40회 중 전설 0마리", not legend, legend)
    chk("서로 다른 종이 나옴", len(species_seen) >= 20, len(species_seen))
    chk("전부 등장 허용된 종",
        all(dexmap[s].get("spawnable") for s in species_seen), "")

    section("바탕화면 내보내기")
    st, p = call("GET", "/api/pokemon", token=token)
    ids = [m["id"] for m in p["pokemon"]]
    codes = [call("POST", "/api/pokemon/%d/desktop" % i, {"on": True}, token)[0]
             for i in ids[:8]]
    st, p = call("GET", "/api/pokemon/desktop", token=token)
    chk("바탕화면 6마리 이하", len(p["pokemon"]) <= 6, len(p["pokemon"]))
    chk("슬롯 중복 없음",
        len(set(m["slot"] for m in p["pokemon"])) == len(p["pokemon"]),
        [m["slot"] for m in p["pokemon"]])
    st, r = call("POST", "/api/pokemon/%d/desktop" % ids[0], {"on": False}, token)
    chk("거두기 성공", st == 200 and r["pokemon"]["onDesktop"] is False, r)

    section("별명 / 경험치 / 놓아주기")
    st, r = call("PATCH", "/api/pokemon/%d" % ids[0], {"nickname": "테스트"}, token)
    chk("별명 설정", st == 200 and r["pokemon"]["nickname"] == "테스트", r)
    st, before = call("GET", "/api/pokemon", token=token)
    tgt = [m for m in before["pokemon"] if m["id"] == ids[0]][0]
    st, r = call("POST", "/api/pokemon/%d/exp" % ids[0], {"amount": 80000}, token)
    chk("경험치 주면 레벨업", st == 200 and r["level"] > tgt["level"],
        (tgt["level"], r.get("level")))
    st, r = call("DELETE", "/api/pokemon/%d" % ids[0], token=token)
    chk("놓아주기", st == 200, r)
    st, r = call("DELETE", "/api/pokemon/%d" % ids[0], token=token)
    chk("이미 없는 포켓몬 404", st == 404, st)

    section("남의 것 건드리기 차단")
    other = "t%06d" % random.randrange(1000000)
    st, r = call("POST", "/api/auth/register",
                 {"username": other, "password": pw, "device": "dev2"})
    otoken = r.get("token")
    st, r = call("DELETE", "/api/pokemon/%d" % ids[1], token=otoken)
    chk("남의 포켓몬 삭제 거부(404)", st == 404, st)
    st, r = call("POST", "/api/pokemon/%d/desktop" % ids[1], {"on": True}, otoken)
    chk("남의 포켓몬 조작 거부(404)", st == 404, st)
    st, w2 = call("GET", "/api/wild?force=true", token=otoken)
    if w2.get("wild"):
        st, r = call("POST", "/api/wild/%d/reveal" % w2["wild"]["id"], {}, token)
        chk("남의 야생 조우 접근 거부(404)", st == 404, st)

    section("로그아웃 / 회원탈퇴")
    st, r = call("POST", "/api/auth/logout", token=token)
    chk("로그아웃", st == 200, r)
    st, r = call("GET", "/api/me", token=token)
    chk("로그아웃 후 토큰 무효(401)", st == 401, st)
    st, r = call("POST", "/api/auth/login", {"username": user, "password": pw})
    token = r.get("token")
    st, r = call("DELETE", "/api/auth/account", {"password": "wrongpw12345"}, token)
    chk("틀린 비밀번호로 탈퇴 거부(401)", st == 401, st)
    st, r = call("DELETE", "/api/auth/account", {"password": pw}, token)
    chk("회원탈퇴", st == 200, r)
    print("       %s" % r.get("message"))
    st, r = call("POST", "/api/auth/login", {"username": user, "password": pw})
    chk("탈퇴 후 로그인 불가(401)", st == 401, st)
    call("DELETE", "/api/auth/account", {"password": pw}, otoken)

    print("")
    print("=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
