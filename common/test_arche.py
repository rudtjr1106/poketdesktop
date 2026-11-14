# -*- coding: utf-8 -*-
"""아르케의 여섯 봉인 (2.4.0) 공용 규칙 검사. 서버도 화면도 띄우지 않는다.

    python common/test_arche.py

장 표 · 장소 후보 67종 · 장 경계 시각 · 사람마다 전설 뽑기 · 말 정규화 · 브라우저 창 제목 꼬리 · 제목 해시.
**수수께끼 글 · 정답은 여기 없다** - 검사에 쓰는 말은 지어낸 것이다.
"""
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

os.environ.pop("POKET_ARCHE_START", None)

from common import arche as A                     # noqa: E402
from common import legends                        # noqa: E402

OK = FAIL = 0
UTC = datetime.timezone.utc


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def at(y, mo, d, h=0, mi=0, s=0):
    return datetime.datetime(y, mo, d, h, mi, s, tzinfo=UTC)


def t_장_표():
    print("[장 표]")
    keys = [c["key"] for c in A.CHAPTERS]
    chk("여섯 장 · 장소 열쇠", keys == ["cave", "volcano", "abyss", "sky", "castle", "throne"], keys)
    chk("장 번호 1~6", [c["n"] for c in A.CHAPTERS] == [1, 2, 3, 4, 5, 6])
    chk("장 길이 2·2·2·3·2·3", [c["days"] for c in A.CHAPTERS] == [2, 2, 2, 3, 2, 3])
    chk("자리 수 3·1·1·1·2·1", [c["slots"] for c in A.CHAPTERS] == [3, 1, 1, 1, 2, 1])
    chk("시작 날 차이는 앞 장들의 길이 합", [c["offset"] for c in A.CHAPTERS] == [0, 2, 4, 6, 9, 11])
    chk("이름 · 장소 이름은 한국어", all(c["kr"] and c["placeKr"] for c in A.CHAPTERS))


def t_후보():
    print("[전설 후보]")
    allp = [n for k in A.POOLS for n in A.POOLS[k]]
    want = set(legends.LEGENDARY) - set(A.EXCLUDED)
    chk("후보 합집합 = 전설 - 진화 전 넷 (67)", set(allp) == want and len(want) == 67, (len(set(allp)), len(want)))
    chk("장소끼리 겹치지 않는다", len(allp) == len(set(allp)), len(allp))
    chk("장소별 수 13·10·8·13·17·6",
        [len(A.POOLS[c["key"]]) for c in A.CHAPTERS] == [13, 10, 8, 13, 17, 6])
    chk("진화 전 넷은 없다", not (set(allp) & set(A.EXCLUDED)))
    chk("환상은 없다", not (set(allp) & set(legends.MYTHICAL)))


def t_시각():
    print("[장 경계]")
    chk("시작 날 기본 2026-11-16", A.start_day() == datetime.date(2026, 11, 16), A.start_day())
    chk("1장 = 11/15 15:00Z ~ 11/17 15:00Z", A.window(1) == (at(2026, 11, 15, 15), at(2026, 11, 17, 15)), A.window(1))
    chk("6장 닫힘 = 11/29 15:00Z (11/30 0시 KST)", A.window(6)[1] == at(2026, 11, 29, 15), A.window(6))
    chk("이벤트 = 1장 열림 ~ 6장 닫힘", A.event_window() == (A.window(1)[0], A.window(6)[1]))
    chk("열리기 1초 전은 0", A.chapter_at(at(2026, 11, 15, 14, 59, 59)) == 0)
    chk("열린 순간은 1장", A.chapter_at(at(2026, 11, 15, 15)) == 1)
    chk("1장 마지막 초는 1장", A.chapter_at(at(2026, 11, 17, 14, 59, 59)) == 1)
    chk("1장 닫힌 순간은 2장", A.chapter_at(at(2026, 11, 17, 15)) == 2)
    chk("4장(3일)은 11/22 ~ 11/25", A.window(4) == (at(2026, 11, 21, 15), at(2026, 11, 24, 15)), A.window(4))
    chk("끝난 순간은 0", A.chapter_at(at(2026, 11, 29, 15)) == 0)
    chk("모르는 장의 창은 None", A.window(0) is None and A.window(7) is None)
    os.environ["POKET_ARCHE_START"] = "2026-11-10"
    try:
        chk("POKET_ARCHE_START 로 통째로 민다", A.window(1)[0] == at(2026, 11, 9, 15)
            and A.chapter_at(at(2026, 11, 10, 3)) == 1, A.window(1))
        os.environ["POKET_ARCHE_START"] = "엉터리"
        chk("값이 깨졌으면 기본 날", A.start_day() == datetime.date(2026, 11, 16), A.start_day())
    finally:
        os.environ.pop("POKET_ARCHE_START", None)


def t_전설_뽑기():
    print("[사람마다 전설]")
    a = A.legends_for(7, 1, salt="소금")
    chk("같은 입력 같은 출력", a == A.legends_for(7, 1, salt="소금"), a)
    chk("1장 셋 · 서로 다름 · 동굴 후보 안", len(a) == 3 and len(set(a)) == 3 and set(a) <= set(A.POOLS["cave"]), a)
    chk("5장 둘 · 고성 후보 안", len(A.legends_for(7, 5, "소금")) == 2
        and set(A.legends_for(7, 5, "소금")) <= set(A.POOLS["castle"]))
    chk("6장 하나 · 왕좌 후보 안", len(A.legends_for(7, 6, "소금")) == 1
        and A.legends_for(7, 6, "소금")[0] in A.POOLS["throne"])
    chk("소금이 다르면 (대개) 다르다",
        sum(A.legends_for(u, 1, "가") != A.legends_for(u, 1, "나") for u in range(1, 21)) >= 15)
    seen = set(tuple(A.legends_for(u, 1, "소금")) for u in range(1, 60))
    chk("사람마다 다르게 퍼진다 (59명에 40가지 넘게)", len(seen) > 40, len(seen))
    chk("모르는 장은 빈 목록", A.legends_for(7, 0, "소금") == [] and A.legends_for(7, 9, "소금") == [])


def t_말():
    print("[말 정규화 · 창 제목]")
    chk("공백 · 문장부호를 뗀다", A.normalize("  돌은, 기억한다! ") == "돌은기억한다", A.normalize("  돌은, 기억한다! "))
    chk("소문자 · 영문 숫자", A.normalize("Hello  World-42") == "helloworld42", A.normalize("Hello  World-42"))
    chk("NFD 로 들어와도 같다", A.normalize("돌은".encode("utf-8").decode("utf-8")) ==
        A.normalize(__import__("unicodedata").normalize("NFD", "돌은")))
    chk("None · 빈 말", A.normalize(None) == "" and A.normalize(" ,. ") == "")
    chk("크롬 꼬리", A.title_core("돌은 기억한다 - Google Chrome") == "돌은 기억한다",
        A.title_core("돌은 기억한다 - Google Chrome"))
    chk("엣지 꼬리 (프로필 · 보이지 않는 칸)",
        A.title_core("돌은 기억한다 - 개인 - Microsoft​ Edge") == "돌은 기억한다",
        A.title_core("돌은 기억한다 - 개인 - Microsoft​ Edge"))
    chk("파이어폭스 꼬리 (긴 줄표)", A.title_core("돌은 기억한다 — Mozilla Firefox") == "돌은 기억한다")
    chk("웨일 꼬리", A.title_core("돌은 기억한다 - Whale") == "돌은 기억한다")
    chk("꼬리 없는 제목은 그대로", A.title_core("메모장 - 제목 없음") == "메모장 - 제목 없음")
    chk("None", A.title_core(None) == "")
    h1 = A.key_hash("s", "돌은 기억한다")
    chk("제목 해시는 공백 차이에 같은 값", h1 == A.key_hash("s", "돌은기억한다 ") and len(h1) == 64, h1)
    chk("소금이 다르면 다른 값", h1 != A.key_hash("t", "돌은 기억한다"))


def main():
    t_장_표()
    t_후보()
    t_시각()
    t_전설_뽑기()
    t_말()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
