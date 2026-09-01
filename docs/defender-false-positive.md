# 백신(Windows Defender) 오탐 신고하는 법

PyInstaller 로 만든 단일 exe 는 실행할 때 자기를 임시 폴더에 풀고 돌린다.
그 동작이 악성코드 패커와 똑같이 생겨서 Defender 가 종종 악성으로 판정한다.
프로그램에 문제가 있는 게 아니라 **오탐**이다.

신고하면 보통 1~3일 안에 풀리고, 한 번 풀리면 **모든 사람의 PC 에서** 안 뜬다.

## 신고 순서

1. https://www.microsoft.com/en-us/wdsi/filesubmission 에 들어간다
2. **"Submit a file for malware analysis"** 를 고른다
3. 로그인 방식은 **Individual (개인)** 로 충분하다. 마이크로소프트 계정이 필요하다
4. 이렇게 채운다

   | 항목 | 넣을 값 |
   |---|---|
   | Submission type | **Software developer (소프트웨어 개발자)** |
   | Company / Product | `Poket Desktop` |
   | File | 릴리스에서 받은 exe (또는 zip 안의 exe) |
   | Detection name | Defender 가 뭐라고 했는지. 모르면 비워도 된다 |
   | **Do you believe this file is...** | **Incorrectly detected (오탐)** |

5. **Additional information** 칸에 이렇게 적는다 (영문)

```
This is a false positive. The file is a PyInstaller one-file executable for an
open-source, non-commercial fan project. The full source code and the exact
build script are public:

  https://github.com/rudtjr1106/poketdesktop
  Build script: tools/build_exe.py

The executable only:
  - draws Pokemon sprites on the desktop (tkinter)
  - talks to its own HTTPS API at https://poketdesktop.onrender.com
  - stores its settings under %APPDATA%\poketdesktop

It does not modify system settings, does not install anything, does not
persist outside %APPDATA%, and has no network activity other than its own API
and public sprite files on GitHub.

The detection is almost certainly the generic PyInstaller one-file unpacking
behaviour. Please re-evaluate.
```

6. 보내고 기다린다. 결과는 메일로 온다

## 그동안 친구가 쓰려면

**릴리스의 `.zip` (폴더형)** 을 받게 하면 대개 그냥 된다.
단일 exe 와 달리 임시 폴더에 푸는 동작이 없어서 오탐이 훨씬 적다.

그래도 막히면, 받은 사람이 직접 풀어줄 수 있다.

1. **Windows 보안** 열기
2. **바이러스 및 위협 방지** → **보호 기록**
3. 차단된 항목을 찾아 **작업 → 장치에서 허용**

## 파일을 보낼 때

카카오톡·메일로 보낸 파일은 출처가 불분명해서 더 엄격하게 검사받는다.
**릴리스 주소를 알려주고 직접 받게 하는 편이 훨씬 덜 걸린다.**

  https://github.com/rudtjr1106/poketdesktop/releases/latest
