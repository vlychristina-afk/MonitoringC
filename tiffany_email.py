import time
import re
import smtplib
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

# --- 설정 정보 입력 ---
send_email = "vly_christina@gmail.com"
receive_email = "chrissy7782@naver.com" # 본인 메일과 같아도 됨
app_password = "pkkbcxsbwkaxlwlt" # 띄어쓰기 없이 입력
TARGET_URL = "https://www.tiffany.kr/jewelry/rings/picasso-graffiti-18k-yellow-gold-rings-1902371474.html"
# --------------------

def send_gmail_alert(subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = send_email
        msg['To'] = receive_email

        # 지메일 서버 연결
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(send_email, app_password)
            server.sendmail(send_email, receive_email, msg.as_string())
        print("이메일 알림을 보냈습니다!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

def check_stock():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # 창이 뜨는 것을 직접 확인하세요!
        page = browser.new_page()
        
        try:
            print(f"[{time.strftime('%H:%M:%S')}] 티파니 접속 중...")
            page.goto(TARGET_URL, wait_until="commit")
            
            # 1. 숫자 6(사이즈 메뉴) 버튼이 나타날 때까지 대기 후 클릭
            page.wait_for_selector("text='6'", timeout=30000)
            page.get_by_text("6", exact=True).first.click()
            print("숫자 6 클릭 완료 - 슬라이드 창 대기 중...")
            
            # 2. 슬라이드 인 페이지가 완전히 열릴 때까지 잠시 대기
            time.sleep(3)

            # 3. 슬라이드 창 안에서 숫자 '8' 버튼 찾기
            # 숫자 8만 딱 적힌 버튼이나 요소를 타겟팅합니다.
            size_8_btn = page.locator("button, a, [role='button']").filter(has_text=re.compile(r"^8$")).first
            
            if size_8_btn.is_visible():
                print("8호 버튼 포착! 상태 분석 중...")
                
                # 4. [핵심] 8호 버튼이 클릭 가능한지(활성화) 확인
                # '재고 없음' 글자는 무시하고, 버튼 자체가 잠겨있는지(disabled)만 봅니다.
                is_disabled = size_8_btn.is_disabled() or \
                              size_8_btn.get_attribute("aria-disabled") == "true" or \
                              "disabled" in (size_8_btn.get_attribute("class") or "").lower()

                if not is_disabled:
                    print("!!! [대박] 8호 버튼이 활성화되었습니다! 구매 가능 !!!")
                    send_gmail_alert(
                        "★티파니 8호 입고!★", 
                        f"슬라이드 창에서 8호 버튼이 활성화되었습니다. 지금 바로 구매하세요!\n{TARGET_URL}"
                    )
                    return True
                else:
                    print("결과: 8호 버튼이 아직 비활성화(품절) 상태입니다.")
                    return False
            else:
                print("슬라이드 창에서 8호 버튼을 찾지 못했습니다.")
                return False

        except Exception as e:
            print(f"진행 중 오류 발생: {e}")
            return False
        finally:
            browser.close()

print("티파니 8호 슬라이드 모니터링 시작...")
while True:
    if check_stock():
        break 
    print("15분 후 다시 확인합니다...")
    time.sleep(900)