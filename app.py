import streamlit as st
from supabase import create_client
import base64
import html
import io
import os
from datetime import datetime, date, timezone, timedelta
from pathlib import Path

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    import pandas as pd
except Exception:
    pd = None


# =========================================================
# 1. 기본 설정
# =========================================================

st.set_page_config(
    page_title="안전제보시스템",
    page_icon="🦺",
    layout="wide"
)


# ★ 사용하실 모델명으로 이 한 줄만 바꾸시면 됩니다.
AI_모델 = "gpt-4o-mini"


# =========================================================
# 2. Supabase 연결
# =========================================================

supabase = create_client(
    st.secrets["connections"]["supabase"]["url"],
    st.secrets["connections"]["supabase"]["key"]
)


# =========================================================
# 2-1. OpenAI 연결
# =========================================================

def AI_키가져오기():

    키 = os.getenv("OPENAI_API_KEY")

    if 키 and 키.strip():
        return 키.strip()

    try:
        값 = st.secrets["openai"]["api_key"]
        if 값 and str(값).strip():
            return str(값).strip()
    except Exception:
        pass

    try:
        값 = st.secrets["OPENAI_API_KEY"]
        if 값 and str(값).strip():
            return str(값).strip()
    except Exception:
        pass

    return None


def AI_클라이언트():

    if OpenAI is None:
        return None, "openai 패키지가 설치되지 않았습니다. pip install openai 를 실행한 뒤 앱을 다시 시작해주세요."

    키 = AI_키가져오기()

    if not 키:
        return None, "API 키를 찾을 수 없습니다. app.py 와 같은 폴더의 .env 파일에 OPENAI_API_KEY=sk-... 형식으로 저장되어 있는지 확인해주세요."

    try:
        return OpenAI(api_key=키), None
    except Exception as e:
        return None, f"OpenAI 연결에 실패했습니다: {e}"


def AI_조치방안(부서, 단위작업, 위험유형, 내용):

    클라이언트, 연결오류 = AI_클라이언트()

    if 클라이언트 is None:
        return None, 연결오류

    시스템 = """당신은 CNC 공작기계를 생산하는 국내 제조공장의 안전관리 실무자입니다.

[공장 개요]
- 주요 부서: 가공팀, UNIT팀, 생산1팀
- 단위작업: FS 가공(AF-16), FS 가공(AF-30), UNIT 가공, UNIT 조립(Head·Turret), UNIT 조립(RT), UNIT 보수, 총조립, 출하
- 주요 취급물: 공작기계 주요 구조물, 헤드, 터렛, 회전테이블(RT) 등 중량물
- 주요 설비: 절삭 가공기, 크레인, 지게차, 조립 지그, 유압·공압 장치

[작성 규칙]
- 접수된 유해·위험요인에 대해 조치 항목을 정확히 3개 제시한다.
- 각 항목은 "1. " "2. " "3. " 으로 시작하고, 항목당 1~2문장으로 쓴다.
- 1번은 오늘 바로 할 수 있는 즉시조치, 2번은 설비·환경 개선, 3번은 관리·절차 개선 순으로 쓴다.
- 현장에서 바로 실행할 수 있도록 구체적으로 쓴다. "안전교육 실시", "주의 요망" 같은 막연한 표현은 쓰지 않는다.
- 법령 조항 번호나 고시 번호는 절대 인용하지 않는다.
- 제보 내용에 없는 사실을 지어내지 않는다. 정보가 부족하면 무엇을 먼저 확인해야 하는지를 조치로 제시한다.
- 머리말, 맺음말, 제목 없이 3개 항목만 출력한다."""

    사용자 = f"""[접수된 안전제보]
부서: {부서}
단위작업: {단위작업}
위험유형: {위험유형}
내용: {내용}

위 제보에 대한 조치 항목 3개를 작성해주세요."""

    try:
        응답 = 클라이언트.chat.completions.create(
            model=AI_모델,
            messages=[
                {"role": "system", "content": 시스템},
                {"role": "user", "content": 사용자}
            ],
            temperature=0.3,
            max_tokens=700
        )

        결과 = 응답.choices[0].message.content

        if not 결과 or not 결과.strip():
            return None, "AI 응답이 비어 있습니다. 다시 시도해주세요."

        return 결과.strip(), None

    except Exception as e:
        return None, f"AI 호출 중 오류가 발생했습니다: {e}"


# =========================================================
# 3. 세션 상태
# =========================================================

if "화면" not in st.session_state:
    st.session_state.화면 = "홈"

if "관리자로그인" not in st.session_state:
    st.session_state.관리자로그인 = False

if "상세제보ID" not in st.session_state:
    st.session_state.상세제보ID = None

if "현황상세ID" not in st.session_state:
    st.session_state.현황상세ID = None


# =========================================================
# 4. 이미지 불러오기
# =========================================================

def 이미지_base64(파일명):
    경로 = Path(__file__).parent / 파일명

    if not 경로.exists():
        return None

    try:
        with open(경로, "rb") as f:
            데이터 = base64.b64encode(f.read()).decode()

        확장자 = 경로.suffix.lower()

        if 확장자 == ".png":
            타입 = "image/png"
        elif 확장자 in [".jpg", ".jpeg"]:
            타입 = "image/jpeg"
        elif 확장자 == ".webp":
            타입 = "image/webp"
        else:
            타입 = "image/png"

        return f"data:{타입};base64,{데이터}"

    except Exception:
        return None


worker_image = 이미지_base64("worker.png")
admin_image = 이미지_base64("admin.png")
logo_image = 이미지_base64("화천로고.jpg") or 이미지_base64("logo.jpg")


# =========================================================
# 5. 디자인 (화천 UI 컬러 시스템)
# =========================================================

st.markdown(
    """
    <style>

    /* ===== 컬러 토큰 ===== */
    :root {
        --hc-blue:        #005CAB;
        --hc-blue-dark:   #00477F;
        --hc-blue-soft:   #E9F2FA;
        --hc-blue-line:   #CFE0EF;
        --hc-gray:        #717073;
        --hc-gray-soft:   #F1F3F5;
        --hc-line:        #E3E7EB;
        --hc-ink:         #1A1D21;
        --hc-bg:          #FFFFFF;
        --hc-red:         #D93025;
        --hc-amber:       #C97A0A;
        --hc-green:       #1E8E3E;
    }

    /* ===== 기본 ===== */
    .stApp {
        background-color: var(--hc-bg);
    }

    .block-container {
        max-width: 1180px;
        padding-top: 2.2rem;
        padding-bottom: 4rem;
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    h1, h2, h3 {
        color: var(--hc-blue) !important;
        font-weight: 700 !important;
        letter-spacing: -0.4px;
    }

    hr {
        border-color: var(--hc-line) !important;
    }

    /* ===== 버튼 ===== */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        min-height: 46px;
        border: 1px solid var(--hc-line);
        background-color: #FFFFFF;
        color: var(--hc-gray);
        transition: all 0.15s ease;
    }

    .stButton > button:hover {
        border-color: var(--hc-blue);
        color: var(--hc-blue);
        background-color: var(--hc-blue-soft);
    }

    .stButton > button[kind="primary"] {
        background-color: var(--hc-blue) !important;
        color: #FFFFFF !important;
        border: 1px solid var(--hc-blue) !important;
        box-shadow: 0 2px 6px rgba(0, 92, 171, 0.22);
    }

    .stButton > button[kind="primary"]:hover {
        background-color: var(--hc-blue-dark) !important;
        border-color: var(--hc-blue-dark) !important;
        box-shadow: 0 4px 12px rgba(0, 92, 171, 0.28);
    }

    /* ===== 입력 요소 ===== */
    .stTextInput input,
    .stTextArea textarea {
        border-radius: 8px !important;
    }

    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border-color: var(--hc-blue) !important;
        box-shadow: 0 0 0 2px rgba(0, 92, 171, 0.15) !important;
    }

    div[data-baseweb="select"] > div {
        border-radius: 8px !important;
    }

    div[data-baseweb="select"] > div:focus-within {
        border-color: var(--hc-blue) !important;
        box-shadow: 0 0 0 2px rgba(0, 92, 171, 0.15) !important;
    }

    .stTextInput label,
    .stTextArea label,
    .stSelectbox label {
        color: var(--hc-gray) !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }

    /* ===== 컨테이너 카드 ===== */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF;
        border-radius: 12px !important;
        border: 1px solid var(--hc-line) !important;
        box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
    }

    /* ===== 페이지 헤더 ===== */
    .page-head {
        display: flex;
        align-items: center;
        gap: 16px;
        background-color: #FFFFFF;
        border: 1px solid var(--hc-line);
        border-left: 6px solid var(--hc-blue);
        border-radius: 12px;
        padding: 18px 24px;
        margin-bottom: 22px;
        box-shadow: 0 1px 4px rgba(16, 24, 40, 0.04);
    }

    .page-head img {
        height: 40px;
        object-fit: contain;
    }

    .page-head .ph-title {
        color: var(--hc-blue);
        font-size: 26px;
        font-weight: 700;
        line-height: 1.25;
        letter-spacing: -0.5px;
    }

    .page-head .ph-sub {
        color: var(--hc-gray);
        font-size: 14px;
        margin-top: 3px;
    }

    /* ===== 홈 헤더 ===== */
    .home-header {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 14px;
        margin-bottom: 14px;
        flex-wrap: wrap;
    }

    .home-header img {
        height: 44px;
        object-fit: contain;
    }

    .home-header .home-div {
        width: 1px;
        height: 42px;
        background-color: #C3CFDB;
        margin: 0 6px;
    }

    .home-header .home-title {
        color: var(--hc-blue);
        font-size: 44px;
        font-weight: 800;
        line-height: 1.2;
        letter-spacing: -1.6px;
        margin: 0;
    }

    .home-info {
        text-align: center;
        color: var(--hc-gray);
        font-size: 16.5px;
        line-height: 1.75;
        margin-bottom: 34px;
    }

    /* ===== 홈 진입 카드 ===== */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-card-mark) {
        border: 2px solid #BCD5EA !important;
        border-radius: 18px !important;
        background-color: #FFFFFF;
        box-shadow: 0 4px 16px rgba(0, 92, 171, 0.10);
    }

    .home-card-mark {
        display: none;
    }

    .home-photo {
        width: 100%;
        aspect-ratio: 4 / 3;
        border-radius: 12px;
        overflow: hidden;
        background-color: var(--hc-blue-soft);
        display: flex;
        justify-content: center;
        align-items: center;
        font-size: 90px;
        margin-bottom: 4px;
    }

    .home-photo img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }

    .st-key-worker_button button,
    .st-key-admin_button button {
        min-height: 74px !important;
    }

    .st-key-worker_button button p,
    .st-key-admin_button button p,
    .st-key-worker_button button div,
    .st-key-admin_button button div {
        font-size: 30px !important;
        font-weight: 500 !important;
        letter-spacing: 5px !important;
        line-height: 1.3 !important;
        margin: 0 !important;
    }

    /* ===== 근로자 메뉴 카드버튼 ===== */
    .st-key-menu_report button,
    .st-key-menu_status button {
        min-height: 176px !important;
        font-size: 16px !important;
        font-weight: 500 !important;
        letter-spacing: 0 !important;
        line-height: 1.6 !important;
        white-space: pre-line !important;
        padding: 26px 24px !important;
        border: 2px solid var(--hc-blue-line) !important;
        border-top: 5px solid var(--hc-blue) !important;
        border-radius: 16px !important;
        background-color: #FFFFFF !important;
        color: var(--hc-blue) !important;
        box-shadow: 0 3px 12px rgba(0, 92, 171, 0.08) !important;
    }

    .st-key-menu_report button:hover,
    .st-key-menu_status button:hover {
        background-color: var(--hc-blue) !important;
        color: #FFFFFF !important;
        border-color: var(--hc-blue) !important;
        box-shadow: 0 6px 18px rgba(0, 92, 171, 0.25) !important;
    }

    /* 카드버튼 제목 (마크다운 굵게 부분) */
    .st-key-menu_report button strong,
    .st-key-menu_status button strong {
        display: block;
        font-size: 30px !important;
        font-weight: 800 !important;
        letter-spacing: -0.5px !important;
        line-height: 1.3 !important;
        margin-bottom: 10px;
    }

    /* 카드버튼 설명 문구 */
    .st-key-menu_report button p,
    .st-key-menu_status button p {
        font-size: 16px !important;
        font-weight: 500 !important;
        line-height: 1.6 !important;
        margin: 0 !important;
        opacity: 0.85;
    }

    .st-key-menu_report button p:has(strong),
    .st-key-menu_status button p:has(strong) {
        opacity: 1;
    }

    /* ===== 통계 카드 ===== */
    .stat-wrap {
        background-color: #FFFFFF;
        border: 1px solid var(--hc-line);
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
    }

    .stat-wrap .stat-label {
        color: var(--hc-gray);
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.3px;
        display: flex;
        align-items: center;
        gap: 7px;
    }

    .stat-wrap .stat-dot {
        width: 9px;
        height: 9px;
        border-radius: 999px;
        display: inline-block;
    }

    .stat-wrap .stat-value {
        font-size: 30px;
        font-weight: 800;
        line-height: 1.2;
        margin-top: 8px;
        letter-spacing: -1px;
    }

    /* ===== 목록 행 ===== */
    .row-top {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 8px;
    }

    .chip {
        font-size: 12px;
        font-weight: 700;
        padding: 4px 11px;
        border-radius: 999px;
        white-space: nowrap;
        letter-spacing: 0.2px;
    }

    .chip-status {
        color: #FFFFFF;
    }

    .chip-id {
        background-color: var(--hc-blue-soft);
        color: var(--hc-blue);
    }

    .chip-tag {
        background-color: var(--hc-gray-soft);
        color: var(--hc-gray);
    }

    .row-body {
        color: var(--hc-ink);
        font-size: 15.5px;
        font-weight: 500;
        line-height: 1.6;
        word-break: break-word;
    }

    .row-meta {
        color: var(--hc-gray);
        font-size: 12.5px;
        margin-top: 9px;
        margin-bottom: 6px;
    }

    .row-top {
        margin-top: 2px;
    }

    /* ===== 정보 카드 ===== */
    .info-card {
        border: 1px solid var(--hc-line);
        border-top: 5px solid var(--hc-blue);
        border-radius: 14px;
        background-color: #FFFFFF;
        padding: 22px 28px 8px 28px;
        box-shadow: 0 1px 6px rgba(16, 24, 40, 0.05);
        margin-bottom: 12px;
    }

    .info-card-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 14px;
        border-bottom: 2px solid var(--hc-gray-soft);
        margin-bottom: 4px;
    }

    .info-card-title {
        color: var(--hc-blue);
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.3px;
    }

    .info-badge {
        color: #FFFFFF;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.8px;
        padding: 6px 16px;
        border-radius: 999px;
        white-space: nowrap;
    }

    .info-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        column-gap: 40px;
    }

    .info-item {
        display: flex;
        align-items: baseline;
        gap: 14px;
        padding: 14px 2px;
        border-bottom: 1px solid var(--hc-gray-soft);
    }

    .info-item.full {
        grid-column: 1 / -1;
        border-bottom: none;
    }

    .info-item.last {
        border-bottom: none;
    }

    .info-item .k {
        color: var(--hc-gray);
        font-size: 12.5px;
        font-weight: 700;
        letter-spacing: 0.4px;
        width: 88px;
        flex-shrink: 0;
    }

    .info-item .v {
        color: var(--hc-ink);
        font-size: 16.5px;
        font-weight: 600;
        word-break: break-word;
    }

    /* ===== 내용 / 결과 박스 ===== */
    .text-box {
        border: 1px solid var(--hc-line);
        border-left: 5px solid var(--hc-gray);
        border-radius: 10px;
        background-color: #FFFFFF;
        padding: 18px 22px;
        margin-bottom: 10px;
    }

    .text-box.blue {
        border-left-color: var(--hc-blue);
        border-color: var(--hc-blue-line);
        background-color: #F8FBFE;
    }

    .text-box.green {
        border-left-color: var(--hc-green);
        border-color: #D7EADD;
        background-color: #F6FBF7;
    }

    .text-box .tb-head {
        font-size: 12.5px;
        font-weight: 700;
        letter-spacing: 0.6px;
        margin-bottom: 10px;
        color: var(--hc-gray);
    }

    .text-box.blue .tb-head {
        color: var(--hc-blue);
    }

    .text-box.green .tb-head {
        color: var(--hc-green);
    }

    .text-box .tb-body {
        color: var(--hc-ink);
        font-size: 16px;
        line-height: 1.85;
        white-space: pre-line;
        word-break: break-word;
    }

    .ai-warn {
        color: var(--hc-amber);
        background-color: #FFF8EE;
        border: 1px solid #F2DFC2;
        border-radius: 8px;
        padding: 11px 15px;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 14px;
    }

    /* ===== 섹션 제목 ===== */
    .sec-title {
        color: var(--hc-blue);
        font-size: 18px;
        font-weight: 700;
        letter-spacing: -0.3px;
        margin: 26px 0 12px 0;
        padding-left: 12px;
        border-left: 4px solid var(--hc-blue);
        line-height: 1.3;
    }

    .login-space {
        height: 11vh;
        min-height: 40px;
    }

    .list-count {
        color: var(--hc-gray);
        font-size: 13.5px;
        font-weight: 600;
        margin: 4px 0 12px 0;
    }

    /* ===== 모바일 ===== */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 16px;
            padding-bottom: 2rem;
        }

        .home-header img {
            height: 29px;
        }

        .home-header .home-title {
            font-size: 27px;
        }

        .home-photo {
            font-size: 66px;
        }

        .home-header .home-div {
            height: 28px;
        }

        .st-key-worker_button button,
        .st-key-admin_button button {
            min-height: 62px !important;
        }

        .st-key-worker_button button p,
        .st-key-admin_button button p,
        .st-key-worker_button button div,
        .st-key-admin_button button div {
            font-size: 24px !important;
            letter-spacing: 3px !important;
        }

        .st-key-menu_report button,
        .st-key-menu_status button {
            min-height: 140px !important;
            padding: 20px 16px !important;
        }

        .st-key-menu_report button strong,
        .st-key-menu_status button strong {
            font-size: 23px !important;
            margin-bottom: 7px;
        }

        .st-key-menu_report button p,
        .st-key-menu_status button p {
            font-size: 14px !important;
        }

        .page-head {
            padding: 14px 16px;
            gap: 12px;
        }

        .page-head img {
            height: 30px;
        }

        .page-head .ph-title {
            font-size: 20px;
        }

        .info-card {
            padding: 18px 16px 6px 16px;
        }

        .info-grid {
            grid-template-columns: 1fr;
        }

        .stat-wrap .stat-value {
            font-size: 24px;
        }

        .login-space {
            height: 3vh;
            min-height: 12px;
        }
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# 6. 공통 함수
# =========================================================

def 안전(값):
    return html.escape(str(값 if 값 is not None else "-"))


# 한국 표준시 (UTC+9)
KST = timezone(timedelta(hours=9))


def 시간표시(값, 짧게=False):

    if not 값:
        return "-"

    글자 = str(값).strip().replace("Z", "+00:00")

    try:
        시각 = datetime.fromisoformat(글자)

        if 시각.tzinfo is None:
            시각 = 시각.replace(tzinfo=timezone.utc)

        시각 = 시각.astimezone(KST)

        if 짧게:
            return 시각.strftime("%Y-%m-%d %H:%M")

        return 시각.strftime("%Y-%m-%d %H:%M:%S")

    except Exception:
        정리 = 글자.replace("T", " ")
        return 정리[:16] if 짧게 else 정리[:19]


def 날짜파싱(값):

    if not 값:
        return None

    try:
        return date.fromisoformat(str(값)[:10])
    except Exception:
        return None


def 날짜표시(값):

    변환 = 날짜파싱(값)

    if 변환 is None:
        return None

    return 변환.strftime("%Y-%m-%d")


def 일정섹션(제보):

    예정 = 날짜표시(제보.get("planned_date"))
    완료 = 날짜표시(제보.get("completed_date"))

    if not 예정 and not 완료:
        return

    섹션("조치 일정")

    if 완료:
        텍스트박스("조치일", 완료, "green")

    if 예정:
        텍스트박스("조치 예정일", 예정, "blue")


def 엑셀만들기(목록):

    if pd is None:
        return None, "pandas 가 설치되지 않았습니다. pip install pandas openpyxl 을 실행해주세요."

    행목록 = []

    for 제보 in 목록:

        행목록.append({
            "제보번호": 제보.get("id"),
            "제보시간": 시간표시(제보.get("created_at")),
            "부서": 제보.get("department") or "",
            "단위작업": 제보.get("location") or "",
            "위험유형": 제보.get("risk_type") or "",
            "제보내용": 제보.get("description") or "",
            "제보자": (제보.get("reporter_name") or "").strip() or "익명",
            "처리상태": 제보.get("status") or "",
            "처리내용": 제보.get("action_detail") or "",
            "조치 예정일": 날짜표시(제보.get("planned_date")) or "",
            "조치일": 날짜표시(제보.get("completed_date")) or ""
        })

    표 = pd.DataFrame(행목록)

    버퍼 = io.BytesIO()

    try:
        with pd.ExcelWriter(버퍼, engine="openpyxl") as 작성기:

            표.to_excel(작성기, index=False, sheet_name="안전제보")

            시트 = 작성기.sheets["안전제보"]

            열너비 = {
                "A": 10, "B": 20, "C": 12, "D": 22, "E": 15,
                "F": 55, "G": 12, "H": 12, "I": 55, "J": 14, "K": 14
            }

            for 열, 너비 in 열너비.items():
                시트.column_dimensions[열].width = 너비

            시트.freeze_panes = "A2"

    except Exception as e:
        return None, f"엑셀 생성 중 오류가 발생했습니다: {e}"

    return 버퍼.getvalue(), None


def 홈으로():
    st.session_state.화면 = "홈"
    st.session_state.관리자로그인 = False
    st.session_state.상세제보ID = None
    st.session_state.현황상세ID = None
    st.rerun()


def 상태표시(상태):
    if 상태 == "미조치":
        return "🔴 미조치"
    elif 상태 == "조치중":
        return "🟡 조치중"
    elif 상태 == "조치완료":
        return "🟢 조치완료"
    return 상태


def 상태색(상태):
    return {
        "미조치": "#D93025",
        "조치중": "#C97A0A",
        "조치완료": "#1E8E3E"
    }.get(상태, "#717073")


def 페이지헤더(제목, 부제=""):

    로고 = f'<img src="{logo_image}">' if logo_image else ""

    st.markdown(
        f"""
        <div class="page-head">
            {로고}
            <div>
                <div class="ph-title">{안전(제목)}</div>
                <div class="ph-sub">{안전(부제)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def 섹션(제목):
    st.markdown(
        f'<div class="sec-title">{안전(제목)}</div>',
        unsafe_allow_html=True
    )


def 통계카드(라벨, 값, 색):
    st.markdown(
        f"""
        <div class="stat-wrap">
            <div class="stat-label">
                <span class="stat-dot" style="background-color:{색};"></span>
                {안전(라벨)}
            </div>
            <div class="stat-value" style="color:{색};">{값}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def 통계바(목록):

    전체수 = len(목록)

    미조치수 = sum(1 for x in 목록 if x.get("status") == "미조치")
    조치중수 = sum(1 for x in 목록 if x.get("status") == "조치중")
    조치완료수 = sum(1 for x in 목록 if x.get("status") == "조치완료")

    s1, s2, s3, s4 = st.columns(4)

    with s1:
        통계카드("전체 제보", 전체수, "#005CAB")

    with s2:
        통계카드("미조치", 미조치수, "#D93025")

    with s3:
        통계카드("조치중", 조치중수, "#C97A0A")

    with s4:
        통계카드("조치완료", 조치완료수, "#1E8E3E")


def 제보정보카드(제보, 제보자표시=False):

    생성시간 = 시간표시(제보.get("created_at"))

    카드상태 = 제보.get("status", "미조치")

    장소값 = 안전(제보.get("location", "-"))
    위험값 = 안전(제보.get("risk_type", "-"))

    if 제보자표시:

        제보자값 = (제보.get("reporter_name") or "").strip()

        if not 제보자값:
            제보자값 = "익명"

        끝줄 = f"""
                <div class="info-item last">
                    <span class="k">위험유형</span>
                    <span class="v">{위험값}</span>
                </div>
                <div class="info-item last">
                    <span class="k">제보자</span>
                    <span class="v">{안전(제보자값)}</span>
                </div>"""

    else:

        끝줄 = f"""
                <div class="info-item last">
                    <span class="k">위험유형</span>
                    <span class="v">{위험값}</span>
                </div>"""

    st.markdown(
        f"""
        <div class="info-card">
            <div class="info-card-head">
                <span class="info-card-title">제보 정보</span>
                <span class="info-badge" style="background-color:{상태색(카드상태)};">{안전(카드상태)}</span>
            </div>
            <div class="info-grid">
                <div class="info-item">
                    <span class="k">제보번호</span>
                    <span class="v">#{안전(제보.get("id", "-"))}</span>
                </div>
                <div class="info-item">
                    <span class="k">제보시간</span>
                    <span class="v">{안전(생성시간)}</span>
                </div>
                <div class="info-item">
                    <span class="k">부서</span>
                    <span class="v">{안전(제보.get("department", "-"))}</span>
                </div>
                <div class="info-item">
                    <span class="k">단위작업</span>
                    <span class="v">{장소값}</span>
                </div>{끝줄}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def 텍스트박스(제목, 본문, 색="basic"):
    st.markdown(
        f"""
        <div class="text-box {색}">
            <div class="tb-head">{안전(제목)}</div>
            <div class="tb-body">{안전(본문)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def 제보행(제보, 버튼키, 부서표시=True, 요약길이=110):

    제보ID = 제보.get("id")
    상태 = 제보.get("status", "미조치")

    생성시간 = 시간표시(제보.get("created_at"), 짧게=True)

    내용 = 제보.get("description", "-") or "-"

    if len(내용) > 요약길이:
        내용 = 내용[:요약길이] + " ..."

    태그 = f'<span class="chip chip-tag">{안전(제보.get("risk_type", "-"))}</span>'

    if 부서표시:
        태그 += f'<span class="chip chip-tag">{안전(제보.get("department", "-"))}</span>'

    눌림 = False

    with st.container(border=True):

        c1, c2 = st.columns([6, 1], vertical_alignment="center")

        with c1:
            st.markdown(
                f"""
                <div class="row-top">
                    <span class="chip chip-status" style="background-color:{상태색(상태)};">{안전(상태)}</span>
                    <span class="chip chip-id">#{안전(제보ID)}</span>
                    {태그}
                </div>
                <div class="row-body">{안전(내용)}</div>
                <div class="row-meta">{안전(제보.get("location", "-"))} · {안전(생성시간)}</div>
                """,
                unsafe_allow_html=True
            )

        with c2:
            눌림 = st.button(
                "상세",
                key=버튼키,
                use_container_width=True
            )

    return 눌림


부서목록 = [
    "가공팀",
    "UNIT팀",
    "생산1팀"
]

# 부서별로 선택 가능한 단위작업
부서별_단위작업 = {
    "가공팀": [
        "FS 가공(AF-16)",
        "FS 가공(AF-30)"
    ],
    "UNIT팀": [
        "UNIT 가공",
        "UNIT 조립(Head·Turret)",
        "UNIT 조립(RT)",
        "UNIT 보수"
    ],
    "생산1팀": [
        "총조립",
        "출하"
    ]
}

# 전체 단위작업 (검색·필터용)
단위작업목록 = [
    단위작업
    for 부서 in 부서목록
    for 단위작업 in 부서별_단위작업[부서]
]

위험유형목록 = [
    "끼임",
    "추락",
    "충돌",
    "화재·폭발",
    "감전",
    "미끄러짐·넘어짐",
    "화학물질",
    "중량물",
    "작업환경",
    "기타"
]

상태목록 = [
    "미조치",
    "조치중",
    "조치완료"
]


# =========================================================
# 7. 첫 화면
# =========================================================

if st.session_state.화면 == "홈":

    if logo_image:
        st.markdown(
            f"""
            <div class="home-header">
                <img src="{logo_image}">
                <span class="home-div"></span>
                <span class="home-title">안전제보시스템</span>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.title("안전제보시스템")

    st.markdown(
        """
        <div class="home-info">
        현장에서 발견한 유해·위험요인을 누구나 쉽고 빠르게 제보할 수 있습니다.
        </div>
        """,
        unsafe_allow_html=True
    )

    여백L, col1, col2, 여백R = st.columns([0.5, 4, 4, 0.5], gap="medium")

    with col1:

        with st.container(border=True):

            사진 = f'<img src="{worker_image}">' if worker_image else "👷"

            st.markdown(
                f'<div class="home-card-mark"></div><div class="home-photo">{사진}</div>',
                unsafe_allow_html=True
            )

            if st.button(
                "근로자",
                type="primary",
                use_container_width=True,
                key="worker_button"
            ):
                st.session_state.화면 = "근로자메뉴"
                st.rerun()

    with col2:

        with st.container(border=True):

            사진 = f'<img src="{admin_image}">' if admin_image else "🔐"

            st.markdown(
                f'<div class="home-card-mark"></div><div class="home-photo">{사진}</div>',
                unsafe_allow_html=True
            )

            if st.button(
                "관리자",
                type="primary",
                use_container_width=True,
                key="admin_button"
            ):
                st.session_state.화면 = "관리자"
                st.rerun()


# =========================================================
# 7-1. 근로자 메뉴
# =========================================================

elif st.session_state.화면 == "근로자메뉴":

    페이지헤더("근로자", "하시려는 작업을 선택해주세요.")

    m1, m2 = st.columns(2, gap="large")

    with m1:

        if st.button(
            "**제보하기**\n\n유해·위험요인을 새로 접수합니다.",
            use_container_width=True,
            key="menu_report"
        ):
            st.session_state.화면 = "제보"
            st.rerun()

    with m2:

        if st.button(
            "**처리현황 확인**\n\n접수된 제보의 처리 결과를 봅니다.",
            use_container_width=True,
            key="menu_status"
        ):
            st.session_state.화면 = "처리현황"
            st.session_state.현황상세ID = None
            st.rerun()

    st.write("")

    if st.button(
        "처음 화면으로",
        key="menu_home",
        use_container_width=True
    ):
        홈으로()


# =========================================================
# 8. 근로자 안전제보
# =========================================================

elif st.session_state.화면 == "제보":

    페이지헤더("안전제보", "현장에서 발견한 유해·위험요인을 입력해주세요.")

    with st.container(border=True):

        f1, f2 = st.columns(2)

        with f1:
            부서 = st.selectbox(
                "부서",
                부서목록,
                key="report_dept"
            )

        with f2:
            단위작업 = st.selectbox(
                "단위작업",
                부서별_단위작업.get(부서, 단위작업목록),
                key=f"report_task_{부서}"
            )

        제보자 = st.text_input(
            "성명 (선택)",
            placeholder="입력하지 않으면 익명으로 접수됩니다.",
            max_chars=20
        )

        st.caption(
            "성명은 안전관리자만 확인할 수 있으며, 처리현황 화면에는 공개되지 않습니다."
        )

        위험유형 = st.selectbox("위험유형", 위험유형목록)

        내용 = st.text_area(
            "유해·위험요인 내용",
            placeholder="발견한 위험요인을 구체적으로 작성해주세요.\n예) UNIT 조립장 통로에서 지게차 후진 시 벽과의 간격이 좁아 통행 중 끼일 위험이 있습니다.",
            height=190
        )

        st.caption(
            "접수된 제보는 전 직원이 볼 수 있습니다. 개인을 특정하는 표현은 피해주세요."
        )

        st.write("")

        if st.button(
            "안전제보 등록",
            type="primary",
            use_container_width=True,
            key="submit_report"
        ):

            if not 내용.strip():
                st.warning("유해·위험요인 내용을 입력해주세요.")

            else:
                try:

                    데이터 = {
                        "department": 부서,
                        "location": 단위작업,
                        "risk_type": 위험유형,
                        "description": 내용.strip(),
                        "status": "미조치",
                        "reporter_name": 제보자.strip() or None
                    }

                    결과 = (
                        supabase
                        .table("reports")
                        .insert(데이터)
                        .execute()
                    )

                    if 결과.data:
                        st.success("안전제보가 정상적으로 등록되었습니다.")
                        st.info(
                            "관리자가 확인 후 처리상태를 변경합니다. 처리현황 확인 메뉴에서 진행 상황을 볼 수 있습니다."
                        )
                    else:
                        st.error("제보 등록 결과를 확인할 수 없습니다.")

                except Exception as e:
                    st.error("제보 등록 중 오류가 발생했습니다.")
                    st.code(str(e))

    st.write("")

    b1, b2 = st.columns(2)

    with b1:
        if st.button("← 근로자 메뉴", key="report_back", use_container_width=True):
            st.session_state.화면 = "근로자메뉴"
            st.rerun()

    with b2:
        if st.button("처음 화면으로", key="worker_home", use_container_width=True):
            홈으로()


# =========================================================
# 8-1. 처리현황 확인
# =========================================================

elif st.session_state.화면 == "처리현황":

    # -----------------------------------------------------
    # 8-1-1. 처리현황 상세
    # -----------------------------------------------------

    if st.session_state.현황상세ID is not None:

        현황ID = st.session_state.현황상세ID

        try:
            상세결과 = (
                supabase
                .table("reports")
                .select("*")
                .eq("id", 현황ID)
                .execute()
            )

            제보 = 상세결과.data[0] if 상세결과.data else None

        except Exception as e:
            st.error("제보 정보를 불러오는 중 오류가 발생했습니다.")
            st.code(str(e))
            제보 = None

        페이지헤더("처리결과 상세", f"제보 #{현황ID} 의 처리 진행 상황입니다.")

        if st.button(
            "← 처리현황 목록으로",
            use_container_width=True,
            key="status_detail_back"
        ):
            st.session_state.현황상세ID = None
            st.rerun()

        if 제보 is None:

            st.warning("해당 제보를 찾을 수 없습니다.")

        else:

            제보정보카드(제보)

            섹션("제보 내용")

            텍스트박스(
                "접수된 내용",
                제보.get("description", "-") or "-",
                "blue"
            )

            섹션("처리 결과")

            현재상태 = 제보.get("status", "미조치")
            처리내용 = (제보.get("action_detail") or "").strip()

            if not 처리내용:

                if 현재상태 == "미조치":
                    st.warning("아직 조치가 시작되지 않았습니다. 관리자가 확인 중입니다.")
                else:
                    st.warning(
                        f"현재 상태는 '{현재상태}' 이며, 등록된 처리내용이 아직 없습니다."
                    )

            else:

                텍스트박스("조치 내용", 처리내용, "green")

            일정섹션(제보)

    # -----------------------------------------------------
    # 8-1-2. 처리현황 목록
    # -----------------------------------------------------

    else:

        페이지헤더(
            "안전제보 처리현황",
            "접수된 전체 안전제보와 처리 진행 상황입니다."
        )

        try:

            결과 = (
                supabase
                .table("reports")
                .select("*")
                .order("id", desc=True)
                .execute()
            )

            현황목록 = 결과.data if 결과.data else []

        except Exception as e:

            st.error("제보 데이터를 불러오는 중 오류가 발생했습니다.")
            st.code(str(e))
            현황목록 = []

        통계바(현황목록)

        섹션("조회 조건")

        with st.container(border=True):

            현황검색어 = st.text_input(
                "검색어",
                placeholder="키워드를 검색하세요.",
                key="status_keyword"
            )

            f1, f2, f3, f4 = st.columns(4)

            with f1:
                현황부서필터 = st.selectbox(
                    "부서",
                    ["전체"] + 부서목록,
                    key="status_dept_filter"
                )

            if 현황부서필터 == "전체":
                선택가능작업 = 단위작업목록
            else:
                선택가능작업 = 부서별_단위작업.get(현황부서필터, 단위작업목록)

            with f2:
                현황장소필터 = st.selectbox(
                    "단위작업",
                    ["전체"] + 선택가능작업,
                    key=f"status_task_filter_{현황부서필터}"
                )

            with f3:
                현황위험필터 = st.selectbox(
                    "위험유형",
                    ["전체"] + 위험유형목록,
                    key="status_risk_filter"
                )

            with f4:
                현황상태필터 = st.selectbox(
                    "처리상태",
                    ["전체"] + 상태목록,
                    key="status_filter"
                )

        현황결과 = []

        for 제보 in 현황목록:

            if (
                현황부서필터 != "전체"
                and 제보.get("department") != 현황부서필터
            ):
                continue

            if (
                현황위험필터 != "전체"
                and 제보.get("risk_type") != 현황위험필터
            ):
                continue

            if (
                현황상태필터 != "전체"
                and 제보.get("status") != 현황상태필터
            ):
                continue

            if (
                현황장소필터 != "전체"
                and 제보.get("location") != 현황장소필터
            ):
                continue

            if 현황검색어.strip():

                현황검색대상 = " ".join(
                    [
                        str(제보.get("department", "")),
                        str(제보.get("location", "")),
                        str(제보.get("risk_type", "")),
                        str(제보.get("description", "")),
                        str(제보.get("action_detail", "") or ""),
                        str(제보.get("status", ""))
                    ]
                )

                if 현황검색어.strip().lower() not in 현황검색대상.lower():
                    continue

            현황결과.append(제보)

        섹션("제보 목록")

        st.markdown(
            f'<div class="list-count">조회 결과 {len(현황결과)}건</div>',
            unsafe_allow_html=True
        )

        if not 현황결과:

            st.info("조건에 맞는 제보가 없습니다.")

        else:

            for 제보 in 현황결과:

                if 제보행(
                    제보,
                    f"status_detail_{제보.get('id')}",
                    부서표시=False
                ):
                    st.session_state.현황상세ID = 제보.get("id")
                    st.rerun()

        st.write("")

        b1, b2 = st.columns(2)

        with b1:
            if st.button("← 근로자 메뉴", key="status_back", use_container_width=True):
                st.session_state.화면 = "근로자메뉴"
                st.rerun()

        with b2:
            if st.button("처음 화면으로", key="status_home", use_container_width=True):
                홈으로()


# =========================================================
# 9. 관리자 로그인
# =========================================================

elif (
    st.session_state.화면 == "관리자"
    and not st.session_state.관리자로그인
):

    페이지헤더("관리자 로그인", "관리자 계정으로 로그인해주세요.")

    st.markdown('<div class="login-space"></div>', unsafe_allow_html=True)

    l1, l2, l3 = st.columns([1, 2, 1])

    with l2:

        with st.container(border=True):

            관리자ID = st.text_input("관리자 ID", placeholder="관리자 ID")

            관리자비밀번호 = st.text_input(
                "비밀번호",
                type="password",
                placeholder="비밀번호"
            )

            st.write("")

            if st.button(
                "로그인",
                type="primary",
                use_container_width=True,
                key="login_button"
            ):

                if 관리자ID == "admin" and 관리자비밀번호 == "1234":
                    st.session_state.관리자로그인 = True
                    st.rerun()
                else:
                    st.error("ID 또는 비밀번호가 올바르지 않습니다.")

        st.write("")

        if st.button("처음 화면으로", key="admin_home", use_container_width=True):
            홈으로()


# =========================================================
# 10. 관리자
# =========================================================

elif (
    st.session_state.화면 == "관리자"
    and st.session_state.관리자로그인
):

    # =====================================================
    # 10-1. 상세 화면
    # =====================================================

    if st.session_state.상세제보ID is not None:

        상세ID = st.session_state.상세제보ID

        처리내용키 = f"action_detail_{상세ID}"
        AI결과키 = f"ai_result_{상세ID}"
        예정일키 = f"planned_date_{상세ID}"
        조치일키 = f"completed_date_{상세ID}"

        try:
            상세결과 = (
                supabase
                .table("reports")
                .select("*")
                .eq("id", 상세ID)
                .execute()
            )

            제보 = 상세결과.data[0] if 상세결과.data else None

        except Exception as e:
            st.error("제보 정보를 불러오는 중 오류가 발생했습니다.")
            st.code(str(e))
            제보 = None

        if 제보 is None:

            페이지헤더("안전제보 상세", "제보를 찾을 수 없습니다.")

            st.warning("해당 제보를 찾을 수 없습니다.")

            if st.button("목록으로 돌아가기", use_container_width=True):
                st.session_state.상세제보ID = None
                st.rerun()

        else:

            페이지헤더(
                "안전제보 상세",
                f"제보 #{상세ID} 의 내용을 확인하고 조치를 등록합니다."
            )

            if st.button(
                "← 제보 목록으로",
                use_container_width=True,
                key="detail_back"
            ):
                st.session_state.pop(처리내용키, None)
                st.session_state.pop(AI결과키, None)
                st.session_state.pop(예정일키, None)
                st.session_state.pop(조치일키, None)
                st.session_state.상세제보ID = None
                st.rerun()

            제보정보카드(제보, 제보자표시=True)

            섹션("제보 내용")

            텍스트박스(
                "접수된 내용",
                제보.get("description", "-") or "-",
                "blue"
            )

            # -------------------------------------------------
            # AI 조치방안 추천
            # -------------------------------------------------

            섹션("AI 조치방안 추천")

            st.markdown(
                """
                <div class="ai-warn">
                AI가 생성한 참고 초안입니다. 반드시 안전관리자가 검토·수정한 후 저장하세요.
                </div>
                """,
                unsafe_allow_html=True
            )

            a1, a2 = st.columns(2)

            with a1:

                if st.button(
                    "AI 조치방안 생성",
                    type="primary",
                    use_container_width=True,
                    key=f"ai_gen_{상세ID}"
                ):

                    with st.spinner("조치방안을 작성하는 중입니다."):

                        결과텍스트, 오류 = AI_조치방안(
                            제보.get("department", ""),
                            제보.get("location", ""),
                            제보.get("risk_type", ""),
                            제보.get("description", "")
                        )

                    if 오류:
                        st.error(오류)
                    else:
                        st.session_state[AI결과키] = 결과텍스트
                        st.rerun()

            with a2:

                if st.button(
                    "처리내용란에 넣기",
                    use_container_width=True,
                    key=f"ai_apply_{상세ID}",
                    disabled=(AI결과키 not in st.session_state)
                ):

                    st.session_state[처리내용키] = st.session_state.get(AI결과키, "")
                    st.rerun()

            if AI결과키 in st.session_state:

                텍스트박스(
                    "AI 제안 조치방안",
                    st.session_state[AI결과키],
                    "blue"
                )

            # -------------------------------------------------
            # 처리 관리
            # -------------------------------------------------

            섹션("처리 관리")

            with st.container(border=True):

                현재상태 = 제보.get("status", "미조치")

                if 현재상태 not in 상태목록:
                    현재상태 = "미조치"

                새로운상태 = st.selectbox(
                    "처리상태",
                    상태목록,
                    index=상태목록.index(현재상태),
                    format_func=상태표시,
                    key=f"detail_status_{상세ID}"
                )

                if 처리내용키 not in st.session_state:
                    st.session_state[처리내용키] = 제보.get("action_detail", "") or ""

                처리내용 = st.text_area(
                    "처리내용",
                    placeholder="어떻게 조치했는지 작성해주세요.",
                    height=230,
                    key=처리내용키
                )

                조치예정일 = None
                조치일 = None

                if 새로운상태 == "조치중":

                    if 예정일키 not in st.session_state:
                        st.session_state[예정일키] = (
                            날짜파싱(제보.get("planned_date")) or date.today()
                        )

                    조치예정일 = st.date_input(
                        "조치 예정일",
                        key=예정일키
                    )

                    st.caption("언제까지 조치할 예정인지 선택해주세요.")

                elif 새로운상태 == "조치완료":

                    if 조치일키 not in st.session_state:
                        st.session_state[조치일키] = (
                            날짜파싱(제보.get("completed_date")) or date.today()
                        )

                    조치일 = st.date_input(
                        "조치일",
                        key=조치일키
                    )

                    st.caption("실제로 조치를 완료한 날짜를 선택해주세요.")

                st.write("")

                if st.button(
                    "처리내용 및 상태 저장",
                    type="primary",
                    use_container_width=True,
                    key=f"detail_save_{상세ID}"
                ):

                    try:

                        저장데이터 = {
                            "status": 새로운상태,
                            "action_detail": 처리내용.strip()
                        }

                        if 새로운상태 == "미조치":
                            저장데이터["planned_date"] = None
                            저장데이터["completed_date"] = None

                        elif 새로운상태 == "조치중":
                            저장데이터["planned_date"] = (
                                조치예정일.isoformat() if 조치예정일 else None
                            )
                            저장데이터["completed_date"] = None

                        elif 새로운상태 == "조치완료":
                            저장데이터["completed_date"] = (
                                조치일.isoformat() if 조치일 else None
                            )

                        (
                            supabase
                            .table("reports")
                            .update(저장데이터)
                            .eq("id", 상세ID)
                            .execute()
                        )

                        st.success("처리상태와 처리내용이 저장되었습니다.")
                        st.rerun()

                    except Exception as e:

                        st.error("저장 중 오류가 발생했습니다.")
                        st.code(str(e))

            st.write("")

            with st.expander("제보 삭제"):

                st.caption(
                    "삭제한 제보는 되돌릴 수 없습니다. 신중하게 진행해주세요."
                )

                if st.button(
                    "🗑 제보 삭제",
                    use_container_width=True,
                    key=f"detail_delete_{상세ID}"
                ):

                    try:

                        (
                            supabase
                            .table("reports")
                            .delete()
                            .eq("id", 상세ID)
                            .execute()
                        )

                        st.success(f"제보 #{상세ID}가 삭제되었습니다.")

                        st.session_state.pop(처리내용키, None)
                        st.session_state.pop(AI결과키, None)
                        st.session_state.pop(예정일키, None)
                        st.session_state.pop(조치일키, None)
                        st.session_state.상세제보ID = None
                        st.rerun()

                    except Exception as e:

                        st.error("제보 삭제 중 오류가 발생했습니다.")
                        st.code(str(e))


    # =====================================================
    # 10-2. 관리자 목록
    # =====================================================

    else:

        페이지헤더(
            "안전제보 관리자",
            "접수된 제보를 확인하고 처리상태를 관리합니다."
        )

        try:

            결과 = (
                supabase
                .table("reports")
                .select("*")
                .order("id", desc=True)
                .execute()
            )

            제보목록 = 결과.data if 결과.data else []

        except Exception as e:

            st.error("제보 데이터를 불러오는 중 오류가 발생했습니다.")
            st.code(str(e))
            제보목록 = []

        통계바(제보목록)

        섹션("제보 검색")

        with st.container(border=True):

            검색어 = st.text_input(
                "검색어",
                placeholder="키워드를 검색하세요."
            )

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                부서필터 = st.selectbox(
                    "부서",
                    ["전체"] + 부서목록,
                    key="admin_dept_filter"
                )

            if 부서필터 == "전체":
                관리자선택가능작업 = 단위작업목록
            else:
                관리자선택가능작업 = 부서별_단위작업.get(부서필터, 단위작업목록)

            with col2:
                작업필터 = st.selectbox(
                    "단위작업",
                    ["전체"] + 관리자선택가능작업,
                    key=f"admin_task_filter_{부서필터}"
                )

            with col3:
                위험필터 = st.selectbox(
                    "위험유형",
                    ["전체"] + 위험유형목록,
                    key="admin_risk_filter"
                )

            with col4:
                상태필터 = st.selectbox(
                    "처리상태",
                    ["전체"] + 상태목록,
                    key="admin_status_filter"
                )

        필터결과 = []

        for 제보 in 제보목록:

            if (
                부서필터 != "전체"
                and 제보.get("department") != 부서필터
            ):
                continue

            if (
                작업필터 != "전체"
                and 제보.get("location") != 작업필터
            ):
                continue

            if (
                위험필터 != "전체"
                and 제보.get("risk_type") != 위험필터
            ):
                continue

            if (
                상태필터 != "전체"
                and 제보.get("status") != 상태필터
            ):
                continue

            if 검색어.strip():

                검색대상 = " ".join(
                    [
                        str(제보.get("department", "")),
                        str(제보.get("location", "")),
                        str(제보.get("risk_type", "")),
                        str(제보.get("description", "")),
                        str(제보.get("status", ""))
                    ]
                )

                if 검색어.strip().lower() not in 검색대상.lower():
                    continue

            필터결과.append(제보)

        섹션("안전제보 목록")

        목록1, 목록2 = st.columns([3, 1], vertical_alignment="center")

        with 목록1:
            st.markdown(
                f'<div class="list-count">검색 결과 {len(필터결과)}건</div>',
                unsafe_allow_html=True
            )

        with 목록2:

            if 필터결과:

                엑셀데이터, 엑셀오류 = 엑셀만들기(필터결과)

                if 엑셀오류:
                    st.caption(엑셀오류)
                else:
                    st.download_button(
                        "엑셀 다운로드",
                        data=엑셀데이터,
                        file_name=f"안전제보_{datetime.now(KST).strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="excel_download"
                    )

        if not 필터결과:

            st.info("조건에 맞는 제보가 없습니다.")

        else:

            for 제보 in 필터결과:

                if 제보행(
                    제보,
                    f"detail_{제보.get('id')}",
                    부서표시=True
                ):
                    st.session_state.상세제보ID = 제보.get("id")
                    st.rerun()

        st.write("")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("처음 화면", key="dashboard_home", use_container_width=True):
                홈으로()

        with col2:
            if st.button("관리자 로그아웃", key="logout", use_container_width=True):
                st.session_state.관리자로그인 = False
                st.session_state.화면 = "홈"
                st.session_state.상세제보ID = None
                st.rerun()
