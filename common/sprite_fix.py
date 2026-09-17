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


def rev(num):
    """캐시 이름에 붙일 판. 바꾼 적 없는 종은 빈 글자."""
    got = OVERRIDE.get(int(num or 0))
    return got[1] if got else ""


def source(num):
    """이 종만 먼저 볼 경로 틀. 없으면 None."""
    got = OVERRIDE.get(int(num or 0))
    return got[0] if got else None
