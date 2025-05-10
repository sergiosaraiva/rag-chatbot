@echo off
setlocal enabledelayedexpansion

REM Base URL for the API
set API_URL=https://backend-production-7a6b.up.railway.app/api/kb/load

echo Uploading files from kb_files\clean directory...
for %%f in (kb_files\clean\*.txt) do (
    echo Uploading %%f...
    curl -X POST %API_URL% -F "files=@%%f"
    echo.
    echo -----------------------------------
    echo.
)

REM echo Uploading files from kb_files\enhance directory...
REM for %%f in (kb_files\enhance\*.txt) do (
REM     echo Uploading %%f...
REM     curl -X POST %API_URL% -F "files=@%%f"
REM     echo.
REM     echo -----------------------------------
REM     echo.
REM )

echo Upload complete!
pause
