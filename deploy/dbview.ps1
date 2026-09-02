# DB 를 브라우저에서 본다. 바탕화면 바로가기가 이걸 부른다.
#
# 서버의 sqlite-web 을 켜고, SSH 터널을 뚫고, 브라우저를 연다.
# **이 창을 닫으면 터널이 끊기고 접속도 끝난다.** 그게 곧 "닫기" 다.
#
# DB 에는 닉네임과 비밀번호 해시가 들어 있다. 그래서 서버 쪽은 127.0.0.1
# 에만 묶여 있고 인터넷에서는 접속 자체가 안 된다. 이 터널로만 들어간다.
#
# 줄을 백틱으로 잇지 않는다 - Windows PowerShell 5.1 은 백틱 뒤에 공백이
# 하나라도 있으면 이어붙이지 않고, 다음 줄을 새 문장으로 읽어서
# 문자열 안의 && 를 연산자로 착각해 터진다. 실제로 그렇게 깨졌다.

$ErrorActionPreference = "Stop"
# 서버(리눅스)가 보내는 글자는 UTF-8 이다. 콘솔을 맞춰 두지 않으면
# 한글이 깨져서 "耳쒖죱?듬땲??" 처럼 나온다.
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }
$Host.UI.RawUI.WindowTitle = "포스크탑 DB"

$Target = "ubuntu@13.124.198.66"
$KeyPath = "$env:USERPROFILE\.ssh\LightsailDefaultKey-ap-northeast-2.pem"
$Port = 8081
$SshOpts = @("-i", $KeyPath, "-o", "StrictHostKeyChecking=no")

function Say($t) { Write-Host "`n== $t" -ForegroundColor Yellow }
function Ok($t) { Write-Host "   OK  $t" -ForegroundColor Green }
function Warn($t) { Write-Host "   !!  $t" -ForegroundColor Red }

if (-not (Test-Path $KeyPath)) {
    Warn "SSH 키가 없습니다: $KeyPath"
    Write-Host "   Lightsail 콘솔 > Account > SSH keys 에서 서울 리전 기본키를 받아"
    Write-Host "   위 경로에 두세요."
    Read-Host "`n엔터를 누르면 닫습니다"
    exit 1
}

Write-Host ""
Write-Host "  포스크탑 DB" -ForegroundColor Cyan
Write-Host "  -----------"
Write-Host "   1) 읽기만  (안전. 아무것도 안 바뀝니다)"
Write-Host "   2) 고치기  (행을 바꾸고 지울 수 있습니다)"
Write-Host ""
$pick = Read-Host "  고르세요 [1]"

$mode = ""
if ($pick -eq "2") {
    Write-Host ""
    Warn "고치기 모드입니다. 여기서 지운 것은 되돌릴 수 없습니다."
    $yes = Read-Host "  정말 하시겠습니까? '고칠래요' 를 그대로 입력"
    if ($yes -ne "고칠래요") {
        Write-Host "`n  그만둡니다."
        Start-Sleep 2
        exit 0
    }
    # 고치기 전에는 반드시 백업부터. 실수는 되돌릴 수 있어야 한다.
    Say "먼저 백업을 뜹니다"
    $cmd = "cd ~/poketdesktop; bash deploy/backup.sh 2>&1 | grep -E 'OK|!!'"
    & ssh @SshOpts $Target $cmd
    $mode = "--write"
}

Say "서버에서 DB 보기를 켭니다"
$cmd = "cd ~/poketdesktop; bash deploy/dbview.sh $mode 2>&1 | grep -E 'OK|!!'"
& ssh @SshOpts $Target $cmd
if ($LASTEXITCODE -ne 0) {
    Warn "서버에서 켜지 못했습니다."
    Read-Host "`n엔터를 누르면 닫습니다"
    exit 1
}

Start-Job -ScriptBlock { param($p) Start-Sleep 5; Start-Process "http://127.0.0.1:$p" } -ArgumentList $Port | Out-Null

Write-Host ""
Write-Host "  ---------------------------------------------" -ForegroundColor DarkGray
Write-Host "   http://127.0.0.1:$Port  이 곧 열립니다" -ForegroundColor Cyan
if ($mode -eq "--write") {
    Write-Host "   고치기 모드입니다" -ForegroundColor Red
} else {
    Write-Host "   읽기 전용입니다" -ForegroundColor Green
}
Write-Host ""
Write-Host "   ** 이 창을 닫으면 연결이 끊깁니다 **" -ForegroundColor Yellow
Write-Host "  ---------------------------------------------" -ForegroundColor DarkGray
Write-Host ""

# 터널을 잡고 있는다. 이 창이 살아 있는 동안만 접속된다.
& ssh @SshOpts "-N" "-L" "${Port}:127.0.0.1:${Port}" $Target

Say "연결을 끊었습니다. 서버 쪽도 끕니다"
$cmd = "cd ~/poketdesktop; bash deploy/dbview.sh --stop"
& ssh @SshOpts $Target $cmd 2>&1 | Out-Null
Ok "끝"
Start-Sleep 2
