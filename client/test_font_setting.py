# -*- coding: utf-8 -*-
"""설정에서 고르는 전체 글꼴 — 저장값 읽기와 어느 글꼴을 쓸지 정하는 셈.

    python client/test_font_setting.py

창을 안 만든다. 글꼴을 고르는 규칙은 Tk 없이 도는 _resolve_families 로
빼 두었으므로 '설치된 글꼴' 을 이름 묶음으로 꾸며서 그대로 부른다.

## 왜 이 검사가 있나

    자동은 예전 그대로   글꼴을 고르지 않은 사람(대부분)에게는 아무것도
                         바뀌면 안 된다. 후보 순서가 하나만 틀어져도 윈도우
                         에서 뽑히는 글꼴이 달라지는데, 눈으로는 알아채기 어렵다.

    없는 글꼴            다른 PC 에서 옮겨 온 설정이나 손으로 고친 설정 파일에
                         설치 안 된 이름·숫자·null 이 들어 있어도 앱이 떠야 하고,
                         그때는 자동과 똑같아야 한다.
"""
import json
import os
import sys
import tempfile

TMP = os.path.join(tempfile.gettempdir(), "poket-test-fontsetting")
os.environ.setdefault("POKET_HOME", TMP)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import config                            # noqa: E402
from poketdesktop import ui_common as U                    # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s  -> %r" % (name, got))


def test_font_family():
    print("config.font_family")
    for label, settings in (("키 없음", {}), ("None", {"fontFamily": None}),
                            ("숫자", {"fontFamily": 12}), ("공백만", {"fontFamily": "   "}),
                            ("목록", {"fontFamily": ["Arial"]}), ("설정 자체가 None", None)):
        got = config.font_family(settings)
        chk("%s -> 자동(\"\")" % label, got == "", got)
    got = config.font_family({"fontFamily": "Pretendard"})
    chk("정상 이름은 그대로", got == "Pretendard", got)
    got = config.font_family({"fontFamily": "  나눔고딕 "})
    chk("앞뒤 공백은 지운다", got == "나눔고딕", got)
    chk("기본값은 자동(\"\")", config.DEFAULTS.get("fontFamily") == "", config.DEFAULTS.get("fontFamily"))


def test_load_old_settings():
    print("옛 settings.json")
    os.makedirs(os.path.dirname(config.SETTINGS_PATH), exist_ok=True)
    with open(config.SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump({"targetHeight": 64}, f)          # fontFamily 가 없던 때의 파일
    s = config.load_settings()
    chk("키가 없던 파일에 fontFamily=\"\" 를 채운다", s.get("fontFamily") == "", s.get("fontFamily"))
    chk("원래 값은 그대로", s.get("targetHeight") == 64, s.get("targetHeight"))
    for bad in (None, 12, "없는 글꼴 이름"):
        with open(config.SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump({"fontFamily": bad}, f)
        s = config.load_settings()
        chk("이상한 저장값(%r)도 읽힌다, 지우지 않는다" % (bad,), s.get("fontFamily") == bad, s.get("fontFamily"))
        want = bad.strip() if isinstance(bad, str) else ""
        chk("  font_family 는 %r" % want, config.font_family(s) == want, config.font_family(s))


def test_resolve():
    print("_resolve_families")
    keys = ("FAMILY", "FAMILY_LIGHT", "FAMILY_MEDIUM", "FAMILY_BLACK")
    full = {"Noto Sans KR", "Noto Sans KR DemiLight", "Noto Sans KR Medium",
            "Noto Sans KR Black", "Pretendard", "Arial", "맑은 고딕"}

    got = U._resolve_families(full, "Arial", "SYS")
    chk("고른 글꼴이 있으면 네 굵기 모두 그것", all(got[k] == "Arial" for k in keys), got)
    chk("돌려주는 키는 넷", sorted(got) == sorted(keys), sorted(got))

    for have in (full, {"Pretendard"}, set()):
        auto = U._resolve_families(have, "", "SYS")
        miss = U._resolve_families(have, "Comic Sans 없는거", "SYS")
        chk("설치 안 된 글꼴은 자동과 같다 (%d개 설치)" % len(have), miss == auto, (miss, auto))

    # 자동은 예전 후보 순서 그대로 (윈도우에서 뽑히는 글꼴이 예전과 같아야 한다)
    got = U._resolve_families(full, "", "SYS")
    chk("자동: 맨 앞 후보(Noto Sans KR)", got["FAMILY"] == "Noto Sans KR", got)
    chk("자동: 가는 글꼴은 DemiLight", got["FAMILY_LIGHT"] == "Noto Sans KR DemiLight", got)
    chk("자동: 중간 굵기는 Medium", got["FAMILY_MEDIUM"] == "Noto Sans KR Medium", got)
    chk("자동: 굵은 글꼴은 Black", got["FAMILY_BLACK"] == "Noto Sans KR Black", got)
    got = U._resolve_families({"Pretendard", "Pretendard Medium", "맑은 고딕"}, "", "SYS")
    chk("자동: Noto 가 없으면 다음 후보(Pretendard)",
        got == {"FAMILY": "Pretendard", "FAMILY_LIGHT": "Pretendard",
                "FAMILY_MEDIUM": "Pretendard Medium", "FAMILY_BLACK": "Pretendard"}, got)
    got = U._resolve_families(set(), "", "SYS")
    chk("자동: 후보가 하나도 없으면 OS 기본 글꼴", all(got[k] == "SYS" for k in keys), got)

    # 후보 목록을 차례로 하나씩만 깔아 봐도, 고르는 것은 늘 그 앞쪽 후보다
    cands = U._FAMILY_CANDIDATES
    for i, c in enumerate(cands):
        have = set(cands[i:])
        got = U._resolve_families(have, "", "SYS")["FAMILY"]
        chk("자동: 후보 %d번째부터 깔린 PC 에서는 %s" % (i + 1, c), got == c, got)
    chk("후보 순서의 머리는 예전 그대로",
        cands[:5] == ["Noto Sans KR", "Pretendard", "SUIT", "IBM Plex Sans KR", "나눔고딕"], cands[:5])


def test_font_choices_without_tk():
    print("font_choices")
    got = U.font_choices(None)       # 기본 root 가 없으면 Tk 를 못 쓴다
    chk("Tk 를 못 쓰면 빈 목록 (예외가 안 난다)", isinstance(got, list), got)


def main():
    test_font_family()
    test_load_old_settings()
    test_resolve()
    test_font_choices_without_tk()
    print()
    print("통과 %d, 실패 %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
