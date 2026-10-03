# -*- coding: utf-8 -*-
"""배틀 도트를 바꿔 쓰는 종. 서버와 클라이언트가 같이 본다.

서버는 PokeAPI 의 쇼다운 움직이는 도트(other/showdown)를 받아 쓴다. 그런데
몇몇은 3D 모델을 정면에서 찍은 그림이라 알아볼 수 없게 납작하다.

  618 스토마  98x15. 눈이 선 한 줄로 보였다 - 관장 카밀레의 스토마가 '찌부' 로
              보인다는 제보. 5세대(블랙·화이트) 움직이는 도트는 60x46 에 얼굴이 보인다.

**캐시 이름에 판(rev)을 붙인다.** 서버(/data/sprites)와 클라이언트(sprites 폴더)
둘 다 한 번 받은 도트를 계속 쓰므로, 이름이 같으면 옛 납작한 그림을 영영 쓴다.
판을 올리면 새 이름으로 다시 받는다.
"""

# 도감 번호 -> (PokeAPI sprites/pokemon 아래 경로 틀, 판)
# 경로 틀의 %s 는 이로치면 "shiny/", %d 는 도감 번호.
OVERRIDE = {
    618: ("versions/generation-v/black-white/animated/%s%d.gif", "r2"),
}


# ---------------------------------------------------------------- 쇼다운에서 직접 받는 메가 폼 (1.9.1)
# 레전드 Z-A 에서 새로 나온 메가 폼은 PokeAPI 저장소에 배틀 도트가 없다. 그래서
# 아이콘이나 일러스트가 대신 나왔고, 바탕화면에서는 메가 모습이 될 수 없었다
# (제보: "메가진화로 걸어다니기 안 되는 포켓몬이 여럿 있다"). 쇼다운 사이트에는
# 그 사이 도트가 올라왔다 - 22폼. **걷는 도트는 어디에도 없다**: 이 폼들은 배틀
# 도트로 서서 좌우로 움직인다 (걷는 도트가 없는 종과 같은 방식).
#
# 메가 번호 -> (쇼다운 sprites 아래 경로, 이로치 그림이 있는가)
# 이로치가 없는 폼은 이로치 개체도 보통 색 도트를 쓴다.
SITE_BASE = "https://play.pokemonshowdown.com/sprites"
SITE_REV = "sd1"
SITE = {
    10288: ("ani/scolipede-mega.gif", False),       # 메가펜드라
    10291: ("ani/chandelure-mega.gif", False),      # 메가샹델라
    10292: ("ani/chesnaught-mega.gif", False),      # 메가브리가론
    10293: ("ani/delphox-mega.gif", False),         # 메가마폭시
    10294: ("ani/greninja-mega.gif", False),        # 메가개굴닌자
    10295: ("ani/pyroar-mega.gif", False),          # 메가화염레오
    10297: ("ani/malamar-mega.gif", False),         # 메가칼라마네로
    10298: ("ani/barbaracle-mega.gif", False),      # 메가거북손데스
    10303: ("ani/falinks-mega.gif", False),         # 메가대여르
    10304: ("ani/raichu-megax.gif", False),         # 메가라이츄X
    10305: ("ani/raichu-megay.gif", False),         # 메가라이츄Y
    10306: ("ani/chimecho-mega.gif", False),        # 메가치렁
    10307: ("gen5/absol-megaz.png", True),          # 메가앱솔Z
    10308: ("ani/staraptor-mega.gif", False),       # 메가찌르호크
    10309: ("gen5/garchomp-megaz.png", True),       # 메가한카리아스Z
    10310: ("gen5/lucario-megaz.png", True),        # 메가루카리오Z
    10313: ("ani/golurk-mega.gif", False),          # 메가골루그
    10315: ("ani/crabominable-mega.gif", False),    # 메가모단단게
    10316: ("gen5/golisopod-mega.png", True),       # 메가갑주무사
    10320: ("ani/scovillain-mega.gif", False),      # 메가스코빌런
    10321: ("ani/glimmora-mega.gif", False),        # 메가킬라플로르
    10325: ("gen5/baxcalibur-mega.png", True),      # 메가드닐레이브
}


def site(num, shiny=False):
    """이 폼의 배틀 도트를 쇼다운 사이트에서 받을 주소와 확장자. 아니면 (None, None).

    이로치 그림이 따로 있으면 'ani-shiny/…' 처럼 폴더 이름에 -shiny 가 붙는다.
    """
    got = SITE.get(int(num or 0))
    if not got:
        return None, None
    path, has_shiny = got
    if shiny and has_shiny:
        folder, name = path.split("/", 1)
        path = "%s-shiny/%s" % (folder, name)
    return "%s/%s" % (SITE_BASE, path), "." + path.rsplit(".", 1)[1]


def rev(num):
    """캐시 이름에 붙일 판. 바꾼 적 없는 종은 빈 글자.

    쇼다운에서 받는 메가 폼도 판을 붙인다 - 그 전에 받아 둔 아이콘·일러스트가
    서버와 클라이언트의 캐시에 남아 있어서, 이름이 같으면 그걸 계속 쓴다.
    """
    n = int(num or 0)
    got = OVERRIDE.get(n)
    if got:
        return got[1]
    return SITE_REV if n in SITE else ""


def source(num):
    """이 종만 먼저 볼 경로 틀. 없으면 None."""
    got = OVERRIDE.get(int(num or 0))
    return got[0] if got else None
