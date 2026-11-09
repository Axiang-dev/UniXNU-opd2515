@echo off
rem ---------------------------------------------------------------------------
rem  Read the UniXNU boot log out of the last 4 MiB of userdata.
rem
rem    read-log.cmd
rem
rem  Requires the tablet booted into recovery (TWRP) with ADB available.
rem  Reads the raw block device; nothing is mounted or modified.
rem ---------------------------------------------------------------------------
setlocal EnableExtensions
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "OUT=%ROOT%\outputs\opd2515-build\logs"
if not exist "%OUT%" mkdir "%OUT%"

where adb >nul 2>nul || (echo ERROR: adb not found on PATH. & exit /b 1)

rem "adb wait-for-device" only accepts the Android "device" state; a device in
rem recovery never satisfies it, so just list and let the push report failure.
echo Devices:
adb devices
echo.
echo Device:
adb shell id || exit /b 1

rem Android sh is 32-bit; a 491 GB partition overflows there, so do the maths
rem here and pass the exact 4 KiB block offset to dd.
set "SIZEFILE=%TEMP%\unixnu-userdata-size.txt"
adb shell blockdev --getsize64 /dev/block/by-name/userdata > "%SIZEFILE%" 2>nul
set "SIZE="
for /f "usebackq" %%S in ("%SIZEFILE%") do set "SIZE=%%S"
if not defined SIZE (echo ERROR: cannot read the userdata size. & exit /b 1)
set "SKIP="
for /f %%K in ('powershell -NoProfile -Command "[uint64]$s=%SIZE%; if ($s -le 4194304 -or ($s %% 4096) -ne 0) { exit 1 }; ($s-4194304)/4096"') do set "SKIP=%%K"
if not defined SKIP (echo ERROR: cannot compute the log offset. & exit /b 1)
echo userdata %SIZE% bytes.
echo Log window at block %SKIP% (4096-byte blocks) in userdata.

adb push "%ROOT%\tools\read-log-device.sh" /tmp/unixnu-read-log.sh >nul || exit /b 1
adb shell sh /tmp/unixnu-read-log.sh %SKIP% || exit /b 1

set "TS=%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%-%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "TS=%TS: =0%"
set "BIN=%OUT%\unixnu-log-%TS%.bin"
adb pull /tmp/unixnu-log.bin "%BIN%" || exit /b 1

echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\tools\decode-boot-log.ps1" "%BIN%"
exit /b 0
