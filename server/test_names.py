# -*- coding: utf-8 -*-
"""부적절한 닉네임 거르기 (app/names.py, 2.5.8 - 11/24 초성 욕 닉네임 계정이 생겼다).

    cd server && POKET_DB=/tmp/x.db python test_names.py

  1. 욕설 · 초성 욕 · 낱자모로 친 욕을 막는다 - 사이에 낀 공백 · _ - . · 숫자도 (시1발 · ㅅ ㅂ)
  2. 성적인 말 · 혐오 표현 · 영어 욕(숫자로 바꿔 쓴 것도) · 쿼티로 친 한글 욕을 막는다
  3. 운영진으로 보이는 이름을 막는다 (닉네임 변경 때만 막던 것 - 이제 가입에도)
  4. 무해한 말은 통과한다 (시바견 · 시발점 · 보지마 · badminton · assassin ...)
  5. 가입 · 가입 화면의 확인 · 닉네임 변경이 다 거른다 - 문구는 "쓸 수 없는 닉네임입니다." (어떤 말인지 안 알린다)
  6. 운영자 계정 이름 그대로는 통과한다 · 이미 있는 계정의 로그인은 닉네임을 다시 검사하지 않는다
"""
import inspect
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("POKET_DB", os.path.join(tempfile.mkdtemp(prefix="poket-names-"), "t.db"))
os.environ.setdefault("POKET_POKEDEX", os.path.join(HERE, "data", "pokedex.json"))
os.environ["POKET_BOARD_ADMINS"] = "운영왕,GM보스"

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


PROFANITY = ["뭐ㅅㅂ", "시발", "씨발놈", "시1발", "씨.발", "시 발", "ㅅ ㅂ", "ㅅ_ㅂ", "병신", "병1신", "ㅂㅅ", "좆같네",
             "지랄마", "ㅈㄹ", "존나쎔", "ㅈㄴ쎔", "개새끼", "ㅅㄲ", "썅", "ㅗ", "ㅗㅗ", "닥쳐", "꺼져라", "느금마", "니애미",
             "미친놈", "시바", "ㅅㅣㅂㅏㄹ", "ㅂㅕㅇㅅㅣㄴ"]
SEXUAL = ["섹스왕", "보지", "자지", "야동맨", "sex", "sexking", "SEX_GOD", "s e x", "porn99", "5ex"]
ENGLISH = ["fuck", "FuckYou", "f.u.c.k", "sh1t", "b1tch", "sibal", "tlqkf"]
HATE = ["한남충", "김치녀", "짱깨", "nigger"]
STAFF = ["운영자", "운영자123", "관리자님", "GM철수", "admin_kim", "포스크탑짱", "개발자"]
FINE = ["지우", "피카츄", "나여조경석", "시바견", "검은시바견", "시바이누", "시발점", "보지마", "해보지뭐", "자지마",
        "새끼고양이", "껌씹는소", "무지개같은날", "애널리스트", "불꺼져있음", "Sigma", "badminton", "Essex", "classic", "assassin",
        "bass", "cocktail", "Dickens", "cucumber", "고추장", "성기훈", "미니미니", "행운지수", "제일베스트", "가시밭길",
        "십자가", "ㅋㅋㅋ", "ㅎㅇ", "Pikachu25", "poke_master", "a.b-c"]


def main():
    from app import names
    print("=== 부적절한 닉네임")
    bad = [n for n in PROFANITY if names.why(n) != "profanity"]
    chk("1. 욕설 · 초성 욕 · 낱자모 욕 · 변형 %d가지를 막는다" % len(PROFANITY), not bad, [(n, names.why(n)) for n in bad])
    bad = [n for n in SEXUAL if names.why(n) != "sexual"]
    chk("2. 성적인 말 %d가지" % len(SEXUAL), not bad, [(n, names.why(n)) for n in bad])
    bad = [n for n in ENGLISH if names.why(n) != "profanity"]
    chk("   영어 욕 · 숫자로 바꿔 쓴 것 · 쿼티로 친 한글 욕 %d가지" % len(ENGLISH), not bad, [(n, names.why(n)) for n in bad])
    bad = [n for n in HATE if names.why(n) != "hate"]
    chk("   혐오 표현 %d가지" % len(HATE), not bad, [(n, names.why(n)) for n in bad])
    bad = [n for n in STAFF if names.why(n) != "staff"]
    chk("3. 운영진으로 보이는 이름 %d가지" % len(STAFF), not bad, [(n, names.why(n)) for n in bad])
    bad = [n for n in FINE if names.bad(n)]
    chk("4. 무해한 이름 %d가지는 통과" % len(FINE), not bad, [(n, names.why(n)) for n in bad])
    chk("   빈 값 · None 은 통과 (길이는 다른 검사가 본다)", not names.bad("") and not names.bad(None))
    chk("   bad 는 why 와 같다", all(names.bad(n) for n in PROFANITY + SEXUAL + ENGLISH + HATE + STAFF))

    from app import auth, db, main as M, rename
    db.init()
    MSG = "쓸 수 없는 닉네임입니다."
    chk("5. 가입 검사가 거른다 (문구에 어떤 말인지 없다)", auth.check_username("뭐ㅅㅂ") == (None, MSG)
        and auth.check_username("섹스왕") == (None, MSG), (auth.check_username("뭐ㅅㅂ"), auth.check_username("섹스왕")))
    chk("   운영진 사칭도 가입에서 막힌다 (전에는 닉네임 변경 때만)", auth.check_username("운영자") == (None, MSG)
        and auth.check_username("GM철수") == (None, MSG))
    chk("   무해한 이름은 그대로 통과", auth.check_username(" 시바견 ") == ("시바견", None) and auth.check_username("Sigma") == ("Sigma", None))
    chk("   길이 · 글자 규칙의 문구는 예전 그대로", "자여야" in (auth.check_username("가")[1] or "")
        and "쓸 수 있습니다" in (auth.check_username("이름!")[1] or ""), (auth.check_username("가"), auth.check_username("이름!")))
    r = M.check_name("뭐ㅅㅂ")
    chk("   가입 화면의 확인(/api/auth/check)도", r["available"] is False and r["reason"] == MSG, r)
    r = M.check_name("괜찮은이름")
    chk("   괜찮은 이름은 쓸 수 있다고 답한다", r["available"] is True, r)

    def mkuser(name):
        return db.run("INSERT INTO users (username, pw_hash, pw_salt, pw_iter, balls, money, created_at, last_login, last_ip)"
                      " VALUES (?, ?, ?, 1, 30, 0, '2026-11-24T00:00:00+00:00', '2026-11-24T00:00:00+00:00', '')",
                      (name, b"x", b"x")).lastrowid
    uid = mkuser("바꿀사람")
    codes = {}
    for new in ("병신왕", "ㅅㅂ", "운영자", "admin_kim", "GM보스", "gm보스"):
        try:
            rename.check(uid, new)
            codes[new] = None
        except Exception as e:                              # noqa: BLE001
            codes[new] = (getattr(e, "status_code", None), getattr(e, "detail", str(e)))
    chk("   닉네임 변경도 거른다 (욕설 · 사칭 · 운영자 계정 이름)", all(v == (400, MSG) for v in codes.values()), codes)
    chk("   닉네임 변경: 무해한 이름은 된다", rename.check(uid, "badminton") == ("badminton", "바꿀사람"))

    chk("6. 운영자 계정 이름 그대로는 가입 검사를 통과한다 (금지어가 들어 있어도)",
        auth.check_username("GM보스") == ("GM보스", None) and auth.check_username("운영왕") == ("운영왕", None),
        (auth.check_username("GM보스"), auth.check_username("운영왕")))
    old = mkuser("뭐ㅅㅂ")
    chk("   이미 있는 계정은 그대로다 (로그인은 닉네임을 다시 검사하지 않는다)", auth.name_taken("뭐ㅅㅂ") and old
        and "check_username" not in inspect.getsource(M.login))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
