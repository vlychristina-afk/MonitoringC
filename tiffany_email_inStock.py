import time
import smtplib
import re
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

# --- [설정 부분] ---
TARGET_URL = "https://www.tiffany.kr/jewelry/rings/picasso-graffiti-sterling-silver-rings-1912170779.html"
send_email = "vly_christina@gmail.com"
receive_email = "chrissy7782@naver.com"
app_password = "pkkbcxsbw" 
# ------------------

def send_gmail_alert(subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = send_email
        msg['To'] = receive_email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(send_email, app_password)
            server.sendmail(send_email, receive_email, msg.as_string())
        print("이메일 알림을 보냈습니다!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

def check_stock():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        page = browser.new_page()
        
        try:
            print(f"[{time.strftime('%H:%M:%S')}] 티파니 정밀 추적 (마지막 시도)...")
            page.goto(TARGET_URL, wait_until="networkidle") # 완전히 다 뜰 때까지 대기
            
            # 1. 사이즈 메뉴(6) 클릭
            page.get_by_text("6", exact=True).first.click()
            print("슬라이드 창 열림. 5호를 찾기 위해 화면을 끝까지 내립니다.")
            time.sleep(5) 

            # 2. [가장 강력한 스크롤] 슬라이드 창 내부 끝까지 내리기
            # 특정 요소를 찾지 않고 그냥 마우스 휠을 확 굴려버립니다.
            page.mouse.move(900, 500) # 마우스를 슬라이드 창 위치로 이동
            for _ in range(3):
                page.mouse.wheel(0, 1000)
                time.sleep(1)

            # 3. [전수 조사] 화면에 보이는 모든 "5"라는 글자를 다 찾습니다.
            # 버튼, 글자, 링크 가리지 않고 다 가져옵니다.
            elements = page.get_by_text(re.compile(r"^5$"), exact=True).all()
            
            if not elements:
                print("여전히 '5'을 찾지 못했습니다. 글자가 이미지로 되어 있을 수 있습니다.")
                return False

            for el in elements:
                if el.is_visible():
                    # 그 요소가 속한 '진짜 버튼' 혹은 '부모 칸'을 찾습니다.
                    # 티파니는 보통 숫자를 누르는 게 아니라 숫자가 들어있는 '원'을 눌러야 합니다.
                    container = el.locator("..") 
                    
                    print("5호 추정 버튼 발견! 상태 분석 중...")
                    
                    # 4. 재고 유무 판독 (주부님 방식: 클릭이 가능한가?)
                    # '재고 없음' 글자가 없고, 버튼이 흐릿하지(disabled) 않으면 성공!
                    is_disabled = el.is_disabled() or container.is_disabled() or \
                                  "disabled" in (el.get_attribute("class") or "").lower() or \
                                  "disabled" in (container.get_attribute("class") or "").lower()
                    
                    # 화면 텍스트 전체에서 '재고 없음'이 이 칸 근처에 있는지 확인
                    row_text = container.locator("..").inner_text()
                    is_out = "재고 없음" in row_text

                    if not is_disabled and not is_out:
                        print("!!! [대박] 5호 재고 발견! 클릭 가능 상태입니다 !!!")
                        send_gmail_alert("★티파니 5호 입고!★", f"지금 바로 구매하세요! 5호가 열렸습니다.\n{TARGET_URL}")
                        return True
                    else:
                        print(f"결과: 5호는 보이지만 아직 '품절' 상태입니다.")
                        # 품절이라도 5호를 찾았으니 일단 이 루프는 성공입니다.
                        return False
            
            return False

        except Exception as e:
            print(f"오류 발생: {e}")
            return False
        finally:
            browser.close()

# --- 코드 맨 마지막에 추가 ---
if __name__ == "__main__":
    # 무한 반복하며 체크하고 싶다면 아래와 같이 작성합니다.
    while True:
        success = check_stock()
        if success:
            print("재고를 확인하여 알림을 보냈습니다. 프로그램을 종료합니다.")
            break
        
        print("10분 후 다시 확인합니다...")
        time.sleep(600)  # 600초(10분) 대기