"""
티파니 Picasso Graffiti Sterling Silver Ring
사이즈 5, 8 구매 가능 여부 모니터링

사용법:
  python monitor_size_5_8.py          → 무한 반복 (재고 나올 때까지 10분마다 확인)
  python monitor_size_5_8.py --once    → 한 번만 확인 후 종료 (매일 10시 스케줄용)
"""
import os
import sys
import time
import re
import smtplib
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

# --- [설정] ---
TARGET_URL = "https://www.tiffany.kr/jewelry/rings/picasso-graffiti-sterling-silver-rings-1912170779.html"
SIZES_TO_CHECK = [5, 8]  # 모니터링할 사이즈

# 이메일: 환경 변수 우선 (TIFFANY_SEND_EMAIL, TIFFANY_RECEIVE_EMAIL, TIFFANY_APP_PASSWORD)
# Gmail 앱 비밀번호: 16자 그대로 붙여넣기 (띄어쓰기 없음). 예: abcdabcdabcdabcd
send_email = (os.environ.get("TIFFANY_SEND_EMAIL", "vly_christina@gmail.com") or "").strip()
receive_email = (os.environ.get("TIFFANY_RECEIVE_EMAIL", "chrissy7782@naver.com") or "").strip()
app_password = (os.environ.get("TIFFANY_APP_PASSWORD", "wgprjywxmjofikgl") or "").strip().replace(" ", "").replace("\n", "")

CHECK_INTERVAL_SEC = 600   # 확인 주기(초) - 10분
HEADLESS = False           # True면 브라우저 창 숨김
PAGE_LOAD_TIMEOUT_MS = 60000   # 페이지 로드 대기(ms) - 60초
DEBUG_PANEL = True         # True면 슬라이드인 패널에서 가져온 텍스트를 출력
# ------------------


def send_gmail_alert(subject: str, body: str) -> None:
    try:
        pw = app_password.strip().replace(" ", "").replace("\n", "")
        if not pw or len(pw) != 16:
            print("이메일 발송 실패: 앱 비밀번호가 16자가 아닙니다. 공백 제거 후 다시 확인하세요.")
            return
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = send_email
        msg["To"] = receive_email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(send_email, pw)
            server.sendmail(send_email, receive_email, msg.as_string())
        print("이메일 알림을 보냈습니다!")
    except Exception as e:
        err = str(e)
        print(f"이메일 발송 실패: {e}")
        if "535" in err or "BadCredentials" in err or "Username and Password" in err:
            print("  → 발송 주소(send_email)가 앱 비밀번호 발급한 Gmail과 정확히 같은지 확인하세요. (예: vly_christina vs vly.christina)")


def open_size_panel_and_scroll(page) -> bool:
    """
    '사이즈' / '사이즈 가이드' 옆에 있는 숫자(6)를 클릭해 슬라이드인 패널을 연 뒤,
    패널 안을 스크롤해서 모든 사이즈가 보이게 함.
    """
    try:
        # 1) "사이즈 가이드" 또는 "사이즈"가 있는 영역이 로드될 때까지 대기
        try:
            page.get_by_text("사이즈 가이드", exact=False).first.wait_for(state="visible", timeout=10000)
            size_label = "사이즈 가이드"
        except Exception:
            page.get_by_text("사이즈", exact=False).first.wait_for(state="visible", timeout=10000)
            size_label = "사이즈"
        time.sleep(1)

        # 2) 그 영역과 같은 블록에 있는 숫자만 클릭 (다른 곳의 6이 아닌, 사이즈 선택용 6)
        size_row = (
            page.locator("div, section, li, span")
            .filter(has=page.get_by_text(size_label, exact=False))
            .filter(has=page.get_by_text("6", exact=True))
            .first
        )
        size_row.wait_for(state="visible", timeout=5000)
        # 같은 행 안에서 6 클릭 → 슬라이드인 패널 오픈
        size_row.get_by_text("6", exact=True).first.click()
        print("사이즈 행에서 6 클릭 → 슬라이드인 패널 열기 시도...")
        time.sleep(2)

        # 3) 슬라이드인 패널이 떴는지 확인 (재고 문구 또는 사이즈 목록이 보이면 성공)
        try:
            page.get_by_text("재고", exact=False).first.wait_for(state="visible", timeout=8000)
        except Exception:
            # "재고" 없이 사이즈만 나오는 경우: 패널 안에 숫자 여러 개 보이면 성공으로 간주
            page.get_by_text("5", exact=True).first.wait_for(state="visible", timeout=5000)
        print("슬라이드인 패널 열림. 스크롤 중...")
        time.sleep(1)

        # 4) 패널 내부 스크롤 (패널이 보통 오른쪽/중앙에 뜨므로 그 근처에서 휠)
        page.mouse.move(700, 400)
        for _ in range(4):
            page.mouse.wheel(0, 800)
            time.sleep(0.6)
        time.sleep(1)
        return True
    except Exception as e:
        print(f"패널 열기/스크롤 실패: {e}")
        return False


def get_slide_in_panel(page):
    """슬라이드인 패널(재고 현황이 뜨는 영역) 로케이터. 없으면 None."""
    # "재고" + 사이즈 숫자가 함께 있는 컨테이너 = 재고 패널
    try:
        panel = (
            page.locator("div, section, aside")
            .filter(has=page.get_by_text("재고", exact=False))
            .filter(has=page.get_by_text("5", exact=True))
            .first
        )
        if panel.count() > 0:
            return panel
    except Exception:
        pass
    return None


def is_size_available_from_panel_text(panel_text: str, size: int) -> bool:
    """
    패널 텍스트는 순서: 티파니사이즈 → 재고여부 → 대한민국사이즈 → 안쪽직경 (반복).
    해당 티파니 사이즈 다음 줄이 "재고 없음"이면 품절, 비어있거나 숫자면 재고 있음.
    같은 숫자(예: 8)가 대한민국 사이즈에도 나오므로, 마지막 매칭 행을 사용(티파니 사이즈는 4~8 순).
    """
    lines = [ln.strip() for ln in panel_text.splitlines()]
    size_str = str(size)
    last_match = None
    for i, ln in enumerate(lines):
        if ln == size_str:
            last_match = i
    if last_match is None:
        return False
    next_ln = lines[last_match + 1].strip() if last_match + 1 < len(lines) else ""
    if next_ln == "재고 없음":
        return False  # 품절
    return True  # 재고 여부 행이 비어있거나 숫자 → 재고 있음


def check_stock() -> list[int]:
    """
    페이지 접속 후 사이즈 패널을 열고, SIZES_TO_CHECK 각각 재고 여부 확인.
    구매 가능한 사이즈 번호 리스트 반환 (없으면 []).
    """
    available = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()

        try:
            page.set_default_timeout(PAGE_LOAD_TIMEOUT_MS)
            print(f"[{time.strftime('%H:%M:%S')}] 접속 중: {TARGET_URL}")
            # networkidle은 타임아웃 잘 남 → domcontentloaded + 필요 시 요소 대기
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
            # "사이즈" / "사이즈 가이드" 라인이 보일 때까지 대기 (슬라이드 열기 전 필수)
            try:
                page.get_by_text("사이즈 가이드", exact=False).first.wait_for(state="visible", timeout=12000)
            except Exception:
                page.get_by_text("사이즈", exact=False).first.wait_for(state="visible", timeout=12000)
            time.sleep(2)

            if not open_size_panel_and_scroll(page):
                return available

            time.sleep(1)
            # 슬라이드인 패널 안에서만 재고 확인 (메인 페이지의 다른 숫자 제외)
            panel = get_slide_in_panel(page)
            scope = panel if panel and panel.count() > 0 else page

            try:
                panel_text = scope.inner_text()
            except Exception:
                panel_text = ""

            if DEBUG_PANEL:
                print("\n" + "=" * 60)
                print("[슬라이드인 패널에서 가져온 정보]")
                print("=" * 60)
                print(panel_text if panel_text else "(텍스트 없음)")
                print("=" * 60 + "\n")

            for size in SIZES_TO_CHECK:
                if is_size_available_from_panel_text(panel_text, size):
                    print(f"  >>> 사이즈 {size} 구매 가능!")
                    available.append(size)
                else:
                    print(f"  >>> 사이즈 {size} 품절")

            return available

        except Exception as e:
            print(f"오류: {e}")
            return []
        finally:
            browser.close()


def main(run_once: bool = False):
    print("티파니 Picasso Graffiti Sterling Silver — 사이즈 5, 8 모니터링 시작")
    if run_once:
        print("모드: 한 번만 확인 후 종료 (--once)")
    else:
        print(f"확인 주기: {CHECK_INTERVAL_SEC}초")
    print("-" * 50)

    while True:
        available = check_stock()

        if available:
            sizes_str = ", ".join(str(s) for s in available)
            subject = f"★ 티파니 링 사이즈 {sizes_str} 구매 가능!"
            body = (
                f"다음 사이즈가 구매 가능합니다: {sizes_str}\n\n"
                f"링크: {TARGET_URL}"
            )
            send_gmail_alert(subject, body)
            print("알림 발송 완료. 프로그램을 종료합니다.")
            break

        if run_once:
            print("재고 없음. 한 번 확인 완료 후 종료합니다.")
            break

        print(f"{CHECK_INTERVAL_SEC}초 후 다시 확인합니다...")
        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    run_once = "--once" in sys.argv or os.environ.get("TIFFANY_RUN_ONCE", "").strip().lower() in ("1", "true", "yes")
    main(run_once=run_once)
