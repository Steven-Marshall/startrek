@echo off
rem  The split-screen UI at full size.  For the 1978 teletype:  python -m trek
rem  "%~dp0." not "%~dp0": the trailing backslash would escape the closing quote.
wt -w new --size 130,40 -d "%~dp0." pwsh -NoExit -Command "python -m trek --ui"
