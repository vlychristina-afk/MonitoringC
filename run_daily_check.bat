@echo off
REM 매일 오전 10시에 작업 스케줄러로 실행할 때 사용
REM 티파니 재고 한 번 확인 후 종료 (재고 있으면 메일 발송)
cd /d "%~dp0"
python monitor_size_5_8.py --once
REM 수동 실행 시 결과 확인용: 아래 주석 해제 후 pause 넣기
REM pause
