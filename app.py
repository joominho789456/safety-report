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

def 관리자계정():

    아이디 = os.getenv("ADMIN_ID")
    비밀번호 = os.getenv("ADMIN_PW")

    if 아이디 and 비밀번호:
        return 아이디.strip(), 비밀번호.strip()

    try:
        아이디 = st.secrets["admin"]["id"]
        비밀번호 = st.secrets["admin"]["password"]

        if 아이디 and 비밀번호:
            return str(아이디).strip(), str(비밀번호).strip()

    except Exception:
        pass

    return None, None


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


AI자동분류 = "🤖 AI 자동 분류"


def AI_위험유형분류(부서, 단위작업, 내용):

    # 위험유형목록 중 하나만 돌려줍니다. 실패하면 "기타"로 접수해서 제보 자체는 막히지 않게 합니다.

    클라이언트, 연결오류 = AI_클라이언트()

    if 클라이언트 is None:
        return "기타"

    선택지 = ", ".join(위험유형목록)

    시스템 = f"""당신은 제조공장의 안전제보를 위험유형별로 분류하는 담당자입니다.

[선택지]
{선택지}

[분류 기준]
- 끼임: 회전체·척·롤러·지그·문 사이 등에 신체가 끼이거나 말려들어감
- 절단·베임·찔림: 공구 날, 칩(절삭 부스러기), 날카로운 모서리·판재에 베이거나 찔림
- 추락: 높은 곳(사다리, 설비 상부, 개구부, 작업발판)에서 떨어짐
- 충돌: 사람이 지게차·대차·설비·돌출물과 부딪힘
- 맞음(낙하·비래): 위에서 떨어지는 물체, 튀어나오는 공작물·공구·칩에 맞음
- 깔림·뒤집힘: 무거운 구조물·부품·지게차 등에 깔리거나 넘어지는 물체에 눌림
- 무너짐: 적재물·랙·가설물이 무너짐
- 미끄러짐·넘어짐: 바닥 기름·절삭유·물, 통로 장애물, 단차
- 중량물: 크레인·호이스트 인양, 슬링·체결 상태 등 중량물 취급 작업 전반으로 위 유형 하나로 특정하기 어려운 경우
- 무리한 동작(근골격계): 무거운 물건을 손으로 들기, 반복 동작, 부자연스러운 자세
- 화재·폭발: 불꽃, 인화물, 가스, 과열, 압력용기 파열
- 감전: 전선 피복 손상, 누전, 분전반, 젖은 전기설비
- 이상온도 접촉(화상): 뜨거운 공작물·설비 표면, 열처리, 용접부 접촉
- 화학물질: 절삭유 증기, 세척제, 도료, 유해물질 누출·노출
- 작업환경: 소음, 조명, 분진, 온열, 환기
- 기타: 위에 해당하지 않음

[규칙]
- 가장 직접적인 사고 형태 하나만 고른다.
- 선택지에 있는 단어 중 하나만 그대로 출력한다. 설명, 따옴표, 마침표를 붙이지 않는다."""

    사용자 = f"부서: {부서}\n단위작업: {단위작업}\n내용: {내용}"

    try:
        응답 = 클라이언트.chat.completions.create(
            model=AI_모델,
            messages=[
                {"role": "system", "content": 시스템},
                {"role": "user", "content": 사용자}
            ],
            temperature=0,
            max_tokens=20
        )

        결과 = (응답.choices[0].message.content or "").strip().strip('".。. ')

        if 결과 in 위험유형목록:
            return 결과

        # 출력이 조금 달라도 선택지 단어가 들어 있으면 인정
        for 유형 in 위험유형목록:
            if 유형 in 결과:
                return 유형

        return "기타"

    except Exception:
        return "기타"


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

def 파일찾기(파일명):

    폴더 = Path(__file__).parent
    경로 = 폴더 / 파일명

    if 경로.exists():
        return 경로

    # 대소문자가 달라도 찾도록 (리눅스 서버 대응)
    목표 = 파일명.lower()

    try:
        for 후보 in 폴더.iterdir():
            if 후보.is_file() and 후보.name.lower() == 목표:
                return 후보
    except Exception:
        pass

    return None


def 이미지_base64(파일명):

    경로 = 파일찾기(파일명)

    if 경로 is None:
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

    /* =====================================================
       포털형(구글·네이버 계열) 디자인
       - 장식(왼쪽 색 띠, 그라데이션, 무거운 그림자) 제거
       - 얇지만 또렷한 선 + 넉넉한 여백 + 둥근 알약 버튼
       - 상태는 연한 바탕 + 진한 글씨(톤 칩)
       ===================================================== */

    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");

    :root {
        --hc-blue:        #005CAB;
        --hc-blue-dark:   #00477F;
        --hc-blue-tonal:  #E3EEF8;
        --hc-blue-line:   #B9D3EC;

        --hc-ink:         #1F1F1F;
        --hc-ink-2:       #444746;
        --hc-gray:        #5E6368;
        --hc-outline:     #747775;   /* 입력칸 테두리 (구글 입력칸과 같은 진한 회색) */
        --hc-line:        #C4C7C5;   /* 카드 테두리 */
        --hc-line-soft:   #E3E5E8;   /* 구분선 */
        --hc-surface-2:   #F6F8FA;   /* 연회색 면 */

        --hc-red:         #D93025;
        --hc-red-ink:     #B3261E;
        --hc-red-tonal:   #FCE8E6;
        --hc-amber-ink:   #9A5B00;
        --hc-amber-tonal: #FEF3D6;
        --hc-green-ink:   #137333;
        --hc-green-tonal: #E6F4EA;

        --hc-bg:          #FFFFFF;
        --hc-card:        #FFFFFF;
        --hc-radius:      16px;
        --hc-hover-shadow: 0 1px 3px rgba(60, 64, 67, 0.15), 0 4px 12px rgba(60, 64, 67, 0.10);
    }

    /* ===== 기본 ===== */
    html, body, .stApp, button, input, textarea, select {
        font-family: "Pretendard", -apple-system, BlinkMacSystemFont, "Malgun Gothic", sans-serif !important;
    }

    .stApp {
        background-color: var(--hc-bg);
    }

    .block-container {
        max-width: 1040px;
        padding-top: 1.4rem;
        padding-bottom: 4rem;
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    h1, h2, h3 {
        color: var(--hc-ink) !important;
        font-weight: 700 !important;
        letter-spacing: -0.4px;
    }

    /* ===== 버튼 공통: 알약 모양 ===== */
    .stButton > button,
    .stDownloadButton > button {
        border-radius: 999px;
        min-height: 44px;
        border: 1px solid var(--hc-line);
        background-color: #FFFFFF;
        color: var(--hc-ink-2);
        box-shadow: none;
        transition: background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
    }

    .stButton > button p,
    .stDownloadButton > button p {
        font-weight: 600 !important;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        border-color: var(--hc-line);
        color: var(--hc-blue);
        background-color: var(--hc-surface-2);
    }

    .stButton > button[kind="primary"] {
        background-color: var(--hc-blue) !important;
        color: #FFFFFF !important;
        border: 1px solid var(--hc-blue) !important;
        box-shadow: none !important;
    }

    .stButton > button[kind="primary"]:hover {
        background-color: var(--hc-blue-dark) !important;
        border-color: var(--hc-blue-dark) !important;
        box-shadow: 0 1px 3px rgba(0, 71, 127, 0.3) !important;
    }

    .stButton > button:disabled {
        opacity: 0.45;
    }

    /* ===== 상단 이동 바 ===== */
    .nav-line {
        height: 1px;
        background-color: var(--hc-line-soft);
        margin: 12px 0 28px 0;
    }

    .nav-line.bottom {
        margin: 32px 0 14px 0;
    }

    .crumb {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 2px;
        font-size: 14px;
        color: var(--hc-gray);
        padding-left: 4px;
    }

    .crumb .sep {
        color: #A8ADB3;
        margin: 0 6px;
    }

    .crumb .now {
        color: var(--hc-ink);
        font-weight: 700;
    }

    /* ← 이전: 연한 파란 면(톤 버튼) */
    div[class*="st-key-navback"] button {
        background-color: var(--hc-blue-tonal) !important;
        color: var(--hc-blue) !important;
        border: 1px solid var(--hc-blue-tonal) !important;
        min-height: 44px !important;
    }

    div[class*="st-key-navback"] button:hover {
        background-color: #D3E3F4 !important;
        border-color: #D3E3F4 !important;
    }

    /* 🏠 처음 화면: 테두리 버튼 */
    div[class*="st-key-navhome"] button {
        background-color: #FFFFFF !important;
        color: var(--hc-ink-2) !important;
        border: 1px solid var(--hc-outline) !important;
        min-height: 44px !important;
    }

    div[class*="st-key-navhome"] button:hover {
        background-color: var(--hc-surface-2) !important;
        color: var(--hc-blue) !important;
    }

    div[class*="st-key-navlogout"] button {
        background-color: #FFFFFF !important;
        color: var(--hc-gray) !important;
        border: 1px solid var(--hc-line) !important;
        min-height: 44px !important;
    }

    div[class*="st-key-navlogout"] button:hover {
        color: var(--hc-red-ink) !important;
        border-color: var(--hc-red) !important;
        background-color: var(--hc-red-tonal) !important;
    }

    div[class*="st-key-navback"] button p,
    div[class*="st-key-navhome"] button p,
    div[class*="st-key-navlogout"] button p {
        font-size: 15px !important;
        font-weight: 600 !important;
    }

    /* ===== 입력 요소 (구글형 테두리 입력칸) =====
       신버전(1.6x): stTextInputRootElement / stTextAreaRootElement / .stSelectbox [role=group]
       구버전: data-baseweb="input" / "textarea" / "select"                                   */
    div[data-testid="stTextInputRootElement"],
    div[data-testid="stTextAreaRootElement"],
    .stSelectbox div[role="group"],
    .stDateInput div[role="group"],
    div[data-baseweb="input"],
    div[data-baseweb="textarea"],
    div[data-baseweb="select"] > div {
        border: 1px solid var(--hc-outline) !important;
        border-radius: 12px !important;
        background-color: #FFFFFF !important;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }

    div[data-testid="stTextInputRootElement"] *,
    div[data-testid="stTextAreaRootElement"] *,
    .stSelectbox div[role="group"] *,
    div[data-baseweb="input"] *,
    div[data-baseweb="textarea"] * {
        background-color: transparent !important;
    }

    div[data-testid="stTextInputRootElement"]:hover,
    div[data-testid="stTextAreaRootElement"]:hover,
    .stSelectbox div[role="group"]:hover {
        border-color: var(--hc-ink) !important;
    }

    /* 입력 중: 파란 테두리를 두 겹으로(구글 방식) */
    div[data-testid="stTextInputRootElement"]:focus-within,
    div[data-testid="stTextAreaRootElement"]:focus-within,
    .stSelectbox div[role="group"]:focus-within,
    .stDateInput div[role="group"]:focus-within,
    div[data-baseweb="input"]:focus-within,
    div[data-baseweb="textarea"]:focus-within,
    div[data-baseweb="select"] > div:focus-within {
        border-color: var(--hc-blue) !important;
        box-shadow: 0 0 0 1px var(--hc-blue) !important;
    }

    div[data-testid="stTextInputRootElement"] input,
    div[data-testid="stTextAreaRootElement"] textarea,
    .stSelectbox div[role="group"] input,
    .stSelectbox div[role="group"] span,
    .stDateInput div[role="group"] input,
    div[data-baseweb="input"] input,
    div[data-baseweb="textarea"] textarea,
    div[data-baseweb="select"] div {
        font-size: 17px !important;
        color: var(--hc-ink) !important;
    }

    div[data-testid="stTextInputRootElement"] input::placeholder,
    div[data-testid="stTextAreaRootElement"] textarea::placeholder {
        color: #8A8F94 !important;
    }

    [role="listbox"] [role="option"],
    ul[role="listbox"] li,
    ul[role="listbox"] li div {
        font-size: 16.5px !important;
    }

    [data-testid="stWidgetLabel"] p,
    .stTextInput label,
    .stTextArea label,
    .stSelectbox label,
    .stDateInput label {
        color: var(--hc-ink-2) !important;
        font-weight: 600 !important;
        font-size: 15px !important;
    }

    /* ===== 카드 (key="card_...") : 얇고 또렷한 선, 그림자 없음 ===== */
    div[class*="st-key-card_"],
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: var(--hc-card);
        border-radius: var(--hc-radius) !important;
        border: 1px solid var(--hc-line) !important;
        box-shadow: none;
    }

    /* 제보 입력·처리 관리처럼 큰 입력 카드는 안쪽 여백 넉넉하게 */
    div[class*="st-key-card_report_form"],
    div[class*="st-key-card_process"],
    div[class*="st-key-card_login"],
    div[class*="st-key-card_status_filter"],
    div[class*="st-key-card_admin_filter"] {
        padding: 24px 26px !important;
    }

    div[class*="st-key-card_row_"] {
        padding: 18px 20px !important;
    }

    /* 입력칸 높이 (구글처럼 넉넉하게) */
    div[data-testid="stTextInputRootElement"],
    .stSelectbox div[role="group"],
    div[data-baseweb="input"],
    div[data-baseweb="select"] > div {
        min-height: 50px !important;
    }

    div[data-testid="stTextInputRootElement"] input,
    .stSelectbox div[role="group"] input {
        padding-left: 14px !important;
    }

    /* 목록 카드: 마우스 올리면 살짝 떠오름 */
    div[class*="st-key-card_row_"] {
        transition: box-shadow 0.15s ease, border-color 0.15s ease;
    }

    div[class*="st-key-card_row_"]:hover {
        box-shadow: var(--hc-hover-shadow);
        border-color: transparent !important;
    }

    /* ===== 페이지 제목: 상자 없이 글자로만 ===== */
    .page-head {
        display: flex;
        align-items: center;
        gap: 16px;
        margin: 0 0 24px 0;
        padding: 0;
        background: none;
        border: none;
        box-shadow: none;
    }

    .page-head img {
        height: 30px;
        object-fit: contain;
    }

    .page-head .ph-div {
        width: 1px;
        height: 30px;
        background-color: var(--hc-line);
    }

    .page-head .ph-title {
        color: var(--hc-ink);
        font-size: 28px;
        font-weight: 700;
        line-height: 1.25;
        letter-spacing: -0.8px;
    }

    .page-head .ph-sub {
        color: var(--hc-gray);
        font-size: 15px;
        margin-top: 4px;
    }

    /* ===== 홈 ===== */
    .home-header {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 18px;
        margin: 18px 0 30px 0;
        flex-wrap: wrap;
    }

    .home-header img {
        height: 42px;
        object-fit: contain;
    }

    .home-header .home-div {
        width: 1px;
        height: 38px;
        background-color: var(--hc-line);
    }

    .home-header .home-title {
        color: var(--hc-ink);
        font-size: 42px;
        font-weight: 800;
        line-height: 1.2;
        letter-spacing: -1.6px;
        margin: 0;
    }

    div[class*="st-key-card_home"] {
        border: 1px solid var(--hc-line) !important;
        border-radius: 24px !important;
        background-color: #FFFFFF;
        box-shadow: none;
        transition: box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
    }

    div[class*="st-key-card_home"]:hover {
        border-color: transparent !important;
        box-shadow: 0 2px 6px rgba(60, 64, 67, 0.15), 0 8px 24px rgba(60, 64, 67, 0.12);
        transform: translateY(-2px);
    }

    .home-photo {
        width: 100%;
        aspect-ratio: 4 / 3;
        border-radius: 16px;
        overflow: hidden;
        background-color: var(--hc-surface-2);
        display: flex;
        justify-content: center;
        align-items: center;
        font-size: 90px;
    }

    .home-photo img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }

    .home-card-desc {
        text-align: center;
        color: var(--hc-gray);
        font-size: 14.5px;
        margin: 6px 0 2px 0;
    }

    .home-card-mark {
        display: none;
    }

    .st-key-worker_button button,
    .st-key-admin_button button {
        min-height: 60px !important;
    }

    .st-key-worker_button button p,
    .st-key-admin_button button p {
        font-size: 22px !important;
        font-weight: 700 !important;
        letter-spacing: 2px !important;
        margin: 0 !important;
    }

    /* ===== 근로자 메뉴 카드버튼 ===== */
    .st-key-menu_report button,
    .st-key-menu_status button {
        min-height: 170px !important;
        white-space: pre-line !important;
        padding: 28px 24px !important;
        border: 1px solid var(--hc-line) !important;
        border-radius: 24px !important;
        background-color: #FFFFFF !important;
        color: var(--hc-ink) !important;
        box-shadow: none !important;
        transition: box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease !important;
    }

    .st-key-menu_report button:hover,
    .st-key-menu_status button:hover {
        background-color: #FFFFFF !important;
        color: var(--hc-ink) !important;
        border-color: transparent !important;
        box-shadow: 0 2px 6px rgba(60, 64, 67, 0.15), 0 8px 24px rgba(60, 64, 67, 0.12) !important;
        transform: translateY(-2px);
    }

    .st-key-menu_report button strong,
    .st-key-menu_status button strong {
        display: block;
        font-size: 26px !important;
        font-weight: 700 !important;
        letter-spacing: -0.6px !important;
        line-height: 1.3 !important;
        margin-bottom: 8px;
        color: var(--hc-blue);
    }

    .st-key-menu_report button p,
    .st-key-menu_status button p {
        font-size: 15.5px !important;
        font-weight: 500 !important;
        line-height: 1.6 !important;
        margin: 0 !important;
        color: var(--hc-gray);
    }

    /* 등록·로그인 버튼 */
    .st-key-submit_report button,
    .st-key-login_button button {
        min-height: 54px !important;
    }

    .st-key-submit_report button p,
    .st-key-login_button button p {
        font-size: 18px !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px !important;
    }

    /* ===== 통계: 연회색 면 타일 ===== */
    .stat-wrap {
        background-color: var(--hc-surface-2);
        border: none;
        border-radius: var(--hc-radius);
        padding: 18px 20px;
    }

    .stat-wrap .stat-bar {
        display: none;
    }

    .stat-wrap .stat-label {
        color: var(--hc-gray);
        font-size: 14px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .stat-wrap .stat-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        display: inline-block;
    }

    .stat-wrap .stat-value {
        font-size: 32px;
        font-weight: 700;
        line-height: 1.15;
        margin-top: 8px;
        letter-spacing: -1px;
    }

    .stat-wrap .stat-unit {
        font-size: 15px;
        font-weight: 500;
        margin-left: 3px;
        color: var(--hc-gray);
    }

    /* ===== 목록 행 ===== */
    .row-wrap {
        padding-left: 4px;
    }

    .row-top {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-wrap: wrap;
        margin: 2px 0 10px 0;
    }

    .chip {
        font-size: 12.5px;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 8px;
        white-space: nowrap;
    }

    .chip-status {
        font-weight: 700;
    }

    .chip-id {
        background-color: transparent;
        color: var(--hc-gray);
        padding-left: 4px;
        padding-right: 4px;
    }

    .chip-tag {
        background-color: var(--hc-surface-2);
        color: var(--hc-ink-2);
        border: 1px solid var(--hc-line-soft);
    }

    .row-body {
        color: var(--hc-ink);
        font-size: 16px;
        font-weight: 500;
        line-height: 1.6;
        word-break: break-word;
    }

    .row-meta {
        color: var(--hc-gray);
        font-size: 13px;
        margin-top: 8px;
        margin-bottom: 2px;
    }

    /* ===== 정보 카드 ===== */
    .info-card {
        border: 1px solid var(--hc-line);
        border-radius: var(--hc-radius);
        background-color: #FFFFFF;
        padding: 22px 26px 8px 26px;
        margin-bottom: 12px;
    }

    .info-card-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 14px;
        border-bottom: 1px solid var(--hc-line-soft);
        margin-bottom: 4px;
    }

    .info-card-title {
        color: var(--hc-ink);
        font-size: 19px;
        font-weight: 700;
        letter-spacing: -0.3px;
    }

    .info-badge {
        font-size: 13.5px;
        font-weight: 700;
        padding: 6px 14px;
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
        border-bottom: 1px solid var(--hc-line-soft);
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
        font-size: 13.5px;
        font-weight: 500;
        width: 80px;
        flex-shrink: 0;
    }

    .info-item .v {
        color: var(--hc-ink);
        font-size: 16.5px;
        font-weight: 600;
        word-break: break-word;
    }

    /* ===== 내용 / 결과 박스: 색 띠 없이 연한 면 ===== */
    .text-box {
        border: none;
        border-radius: var(--hc-radius);
        background-color: var(--hc-surface-2);
        padding: 18px 22px;
        margin-bottom: 10px;
    }

    .text-box.blue {
        background-color: #F1F6FC;
    }

    .text-box.green {
        background-color: var(--hc-green-tonal);
    }

    .text-box .tb-head {
        font-size: 13px;
        font-weight: 700;
        margin-bottom: 8px;
        color: var(--hc-gray);
    }

    .text-box.blue .tb-head {
        color: var(--hc-blue);
    }

    .text-box.green .tb-head {
        color: var(--hc-green-ink);
    }

    .text-box .tb-body {
        color: var(--hc-ink);
        font-size: 16px;
        line-height: 1.8;
        white-space: pre-line;
        word-break: break-word;
    }

    .ai-warn {
        color: var(--hc-amber-ink);
        background-color: var(--hc-amber-tonal);
        border: none;
        border-radius: 12px;
        padding: 12px 16px;
        font-size: 13.5px;
        font-weight: 600;
        margin-bottom: 14px;
    }

    /* ===== 섹션 제목: 막대 없이 글자로만 ===== */
    .sec-title {
        color: var(--hc-ink);
        font-size: 19px;
        font-weight: 700;
        letter-spacing: -0.4px;
        margin: 34px 0 12px 2px;
        padding: 0;
        border: none;
        line-height: 1.3;
    }

    .login-space {
        height: 7vh;
        min-height: 30px;
    }

    /* ===== 긴급 연락처: 연한 빨강 면 + 알약 버튼 ===== */
    .emg-box {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 20px;
        background-color: var(--hc-red-tonal);
        border: none;
        border-radius: 20px;
        padding: 14px 14px 14px 26px;
        margin: 4px 0 20px 0;
    }

    .emg-box .emg-title {
        display: flex;
        align-items: center;
        gap: 10px;
        color: var(--hc-red-ink);
        font-size: 21px;
        font-weight: 700;
        letter-spacing: -0.5px;
        line-height: 1.3;
    }

    .emg-box .emg-call {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        flex-shrink: 0;
        background-color: var(--hc-red);
        color: #FFFFFF !important;
        text-decoration: none !important;
        font-size: 20px;
        font-weight: 700;
        letter-spacing: 0.3px;
        padding: 8px 22px 8px 8px;
        border-radius: 999px;
        white-space: nowrap;
        transition: background-color 0.15s ease, box-shadow 0.15s ease;
    }

    .emg-box .emg-icon {
        width: 36px;
        height: 36px;
        border-radius: 999px;
        background-color: #FFFFFF;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }

    .emg-box .emg-icon svg {
        width: 19px;
        height: 19px;
        fill: var(--hc-red);
    }

    .emg-box .emg-call:hover {
        background-color: var(--hc-red-ink);
        box-shadow: 0 2px 8px rgba(179, 38, 30, 0.35);
    }

    .list-count {
        color: var(--hc-gray);
        font-size: 14px;
        font-weight: 500;
        margin: 4px 0 12px 2px;
    }

    .list-count b {
        color: var(--hc-ink);
        font-weight: 700;
    }

    /* ===== Streamlit 알림창(등록 완료 등)도 같은 톤으로 ===== */
    div[data-testid="stAlert"] {
        border-radius: 12px !important;
    }

    /* ===== 폴더형 탭 (근로자 화면) =====
       왼쪽: 색인 탭 / 오른쪽: 폴더 본문
       제보하기 = 회사 파랑, 처리현황 = 초록                              */
    .st-key-folder_tabs {
        gap: 10px !important;
        padding-top: 22px;
    }

    .st-key-tab_report button,
    .st-key-tab_status button {
        min-height: 74px !important;
        border-radius: 16px 0 0 16px !important;
        border: 1px solid var(--hc-line) !important;
        border-right: none !important;
        background-color: var(--hc-surface-2) !important;
        color: var(--hc-gray) !important;
        padding-left: 20px !important;
        position: relative;
        transition: background-color 0.15s ease, color 0.15s ease !important;
    }

    .st-key-tab_report button div,
    .st-key-tab_status button div {
        justify-content: flex-start !important;
    }

    .st-key-tab_report button p,
    .st-key-tab_status button p {
        font-size: 17px !important;
        font-weight: 700 !important;
        text-align: left !important;
        white-space: nowrap;
    }

    /* 선택 안 된 탭: 왼쪽에 탭 색 표시 */
    .st-key-tab_report button[kind="secondary"] {
        box-shadow: inset 5px 0 0 var(--hc-blue) !important;
    }

    .st-key-tab_status button[kind="secondary"] {
        box-shadow: inset 5px 0 0 #188038 !important;
    }

    .st-key-tab_report button[kind="secondary"]:hover,
    .st-key-tab_status button[kind="secondary"]:hover {
        background-color: #ECEFF3 !important;
        color: var(--hc-ink) !important;
    }

    /* 선택된 탭: 탭 색으로 채우고 오른쪽 본문까지 이어지게 */
    .st-key-tab_report button[kind="primary"],
    .st-key-tab_status button[kind="primary"] {
        color: #FFFFFF !important;
        width: calc(100% + 18px) !important;
        margin-right: -18px;
        z-index: 2;
        box-shadow: none !important;
    }

    .st-key-tab_report button[kind="primary"] {
        background-color: var(--hc-blue) !important;
        border-color: var(--hc-blue) !important;
    }

    .st-key-tab_status button[kind="primary"] {
        background-color: #188038 !important;
        border-color: #188038 !important;
    }

    /* 마우스를 올려도 선택된 탭 색이 유지되도록 */
    .stButton.st-key-tab_report > button[kind="primary"]:hover,
    .st-key-tab_report button[kind="primary"]:hover {
        background-color: var(--hc-blue) !important;
        border-color: var(--hc-blue) !important;
        box-shadow: none !important;
    }

    .stButton.st-key-tab_status > button[kind="primary"]:hover,
    .st-key-tab_status button[kind="primary"]:hover {
        background-color: #188038 !important;
        border-color: #188038 !important;
        box-shadow: none !important;
    }

    /* 폴더 본문: 선택된 탭과 같은 색 테두리 */
    .st-key-folder_panel_report,
    .st-key-folder_panel_status {
        border: 2px solid var(--hc-blue);
        border-radius: 22px;
        padding: 30px 32px 32px 32px !important;
        background-color: #FFFFFF;
        min-height: 620px;
    }

    .st-key-folder_panel_status {
        border-color: #188038;
    }

    /* 폴더 안에서는 상자 안의 상자가 생기지 않도록 안쪽 카드 테두리 제거 */
    .st-key-folder_panel_report div[class*="st-key-card_report_form"] {
        border: none !important;
        padding: 0 !important;
        box-shadow: none !important;
    }

    .st-key-folder_panel_status div[class*="st-key-card_status_filter"] {
        border: none !important;
        background-color: var(--hc-surface-2) !important;
    }

    .st-key-status_back_list button {
        background-color: var(--hc-surface-2) !important;
        border: none !important;
        padding: 0 20px !important;
    }

    /* ===== 모바일 ===== */
    @media (max-width: 768px) {

        /* 폴더 탭: 휴대폰에서는 위쪽 가로 탭 */
        .st-key-folder_tabs {
            flex-direction: row !important;
            padding-top: 0;
            gap: 8px !important;
        }

        .st-key-folder_tabs > div {
            flex: 1 1 0 !important;
            width: auto !important;
        }

        .st-key-tab_report button,
        .st-key-tab_status button,
        .st-key-tab_report button[kind="primary"],
        .st-key-tab_status button[kind="primary"] {
            min-height: 54px !important;
            width: 100% !important;
            margin-right: 0;
            border-radius: 14px !important;
            border-right: 1px solid var(--hc-line) !important;
            padding-left: 12px !important;
        }

        .st-key-tab_report button div,
        .st-key-tab_status button div {
            justify-content: center !important;
        }

        .st-key-tab_report button[kind="secondary"] {
            box-shadow: inset 0 -4px 0 var(--hc-blue) !important;
        }

        .st-key-tab_status button[kind="secondary"] {
            box-shadow: inset 0 -4px 0 #188038 !important;
        }

        .st-key-tab_report button p,
        .st-key-tab_status button p {
            font-size: 16px !important;
        }

        .st-key-folder_panel_report,
        .st-key-folder_panel_status {
            padding: 20px 16px !important;
            min-height: 0;
            border-radius: 18px;
        }

        .block-container {
            padding-top: 14px;
            padding-bottom: 2rem;
        }

        .crumb {
            justify-content: center;
            padding: 4px 0;
            font-size: 13px;
        }

        .home-header img {
            height: 28px;
        }

        .home-header .home-title {
            font-size: 28px;
        }

        .home-header .home-div {
            height: 26px;
        }

        .home-photo {
            font-size: 66px;
        }

        .st-key-worker_button button,
        .st-key-admin_button button {
            min-height: 54px !important;
        }

        .st-key-worker_button button p,
        .st-key-admin_button button p {
            font-size: 20px !important;
        }

        .st-key-menu_report button,
        .st-key-menu_status button {
            min-height: 130px !important;
            padding: 20px 16px !important;
        }

        .st-key-menu_report button strong,
        .st-key-menu_status button strong {
            font-size: 22px !important;
        }

        .st-key-menu_report button p,
        .st-key-menu_status button p {
            font-size: 14px !important;
        }

        .page-head {
            gap: 12px;
        }

        .page-head img {
            height: 24px;
        }

        .page-head .ph-div {
            height: 24px;
        }

        .page-head .ph-title {
            font-size: 22px;
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

        .emg-box {
            flex-direction: column;
            align-items: stretch;
            gap: 12px;
            padding: 16px;
        }

        .emg-box .emg-title {
            font-size: 19px;
            justify-content: center;
        }

        .emg-box .emg-call {
            justify-content: center;
            font-size: 20px;
        }

        .login-space {
            height: 2vh;
            min-height: 8px;
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


# ---------------------------------------------------------
# 6-1. 화면 이동 함수
#   버튼의 on_click 으로 연결합니다.
#   (클릭 즉시 화면 상태를 바꾸므로 st.rerun() 이 필요 없습니다.)
# ---------------------------------------------------------

def 이동_홈():
    st.session_state.화면 = "홈"
    st.session_state.관리자로그인 = False
    st.session_state.상세제보ID = None
    st.session_state.현황상세ID = None


def 이동_근로자메뉴():
    # 근로자 메뉴 화면은 폴더 탭으로 바뀌어, 제보하기 탭으로 이동
    st.session_state.화면 = "제보"
    st.session_state.현황상세ID = None


def 탭_제보():
    st.session_state.화면 = "제보"
    st.session_state.현황상세ID = None


def 탭_처리현황():
    st.session_state.화면 = "처리현황"
    st.session_state.현황상세ID = None


def 이동_처리현황목록():
    st.session_state.현황상세ID = None


def 이동_관리자목록():

    상세ID = st.session_state.상세제보ID

    if 상세ID is not None:
        for 접두 in ["action_detail_", "ai_result_", "planned_date_", "completed_date_"]:
            st.session_state.pop(f"{접두}{상세ID}", None)

    st.session_state.상세제보ID = None


def 이동_로그아웃():
    이동_관리자목록()
    이동_홈()


def 내비게이션(경로, 뒤로=None, 키="top", 홈버튼=True, 로그아웃=False, 경로표시=True):

    # 경로   : ["근로자", "안전제보"] 처럼 현재 위치를 순서대로
    # 뒤로   : ("← 근로자 메뉴", 이동함수)  /  없으면 None
    # 키     : 같은 화면에서 상단·하단 두 번 쓸 때 구분용

    if not 경로표시 and 키 != "top":
        st.markdown('<div class="nav-line bottom"></div>', unsafe_allow_html=True)

    오른쪽칸수 = (1 if 홈버튼 else 0) + (1 if 로그아웃 else 0)

    # 뒤로 버튼이 없으면 그 칸을 만들지 않아 경로 표시가 왼쪽 끝부터 시작
    비율 = ([1.6] if 뒤로 else []) + [4.4] + [1.25] * 오른쪽칸수

    칸들 = st.columns(비율, vertical_alignment="center")

    if 뒤로:
        with 칸들[0]:
            라벨, 동작 = 뒤로
            st.button(
                라벨,
                key=f"navback_{키}",
                on_click=동작,
                use_container_width=True
            )
        칸들 = 칸들[1:]

    with 칸들[0]:
        if 경로표시:
            조각 = ['<div class="crumb"><span>🏠 처음</span>']

            for i, 이름 in enumerate(경로):
                조각.append('<span class="sep">›</span>')

                if i == len(경로) - 1:
                    조각.append(f'<span class="now">{안전(이름)}</span>')
                else:
                    조각.append(f'<span>{안전(이름)}</span>')

            조각.append('</div>')

            st.markdown("".join(조각), unsafe_allow_html=True)

    다음칸 = 1

    if 홈버튼:
        with 칸들[다음칸]:
            st.button(
                "🏠 처음 화면",
                key=f"navhome_{키}",
                on_click=이동_홈,
                use_container_width=True
            )
        다음칸 += 1

    if 로그아웃:
        with 칸들[다음칸]:
            st.button(
                "로그아웃",
                key=f"navlogout_{키}",
                on_click=이동_로그아웃,
                use_container_width=True
            )

    if 경로표시:
        st.markdown('<div class="nav-line"></div>', unsafe_allow_html=True)


def 상태표시(상태):
    if 상태 == "미조치":
        return "🔴 미조치"
    elif 상태 == "조치중":
        return "🟡 조치중"
    elif 상태 == "조치완료":
        return "🟢 조치완료"
    return 상태


def 상태색(상태):
    # 진한 글씨색 (통계 숫자, 점 색 등)
    return {
        "미조치": "#B3261E",
        "조치중": "#9A5B00",
        "조치완료": "#137333"
    }.get(상태, "#5E6368")


def 상태톤(상태):
    # 상태 칩용: (연한 바탕색, 진한 글씨색)
    return {
        "미조치": ("#FCE8E6", "#B3261E"),
        "조치중": ("#FEF3D6", "#9A5B00"),
        "조치완료": ("#E6F4EA", "#137333")
    }.get(상태, ("#F1F3F4", "#5E6368"))


def 상태칩스타일(상태):
    바탕, 글씨 = 상태톤(상태)
    return f"background-color:{바탕};color:{글씨};"


def 페이지헤더(제목, 부제=""):

    if logo_image:
        로고 = f'<img src="{logo_image}"><span class="ph-div"></span>'
    else:
        로고 = ""

    조각 = (
        '<div class="page-head">'
        + 로고
        + '<div>'
        + f'<div class="ph-title">{안전(제목)}</div>'
        + f'<div class="ph-sub">{안전(부제)}</div>'
        + '</div></div>'
    )

    st.markdown(조각, unsafe_allow_html=True)


def 긴급연락처():

    # 번호는 코드에 적지 않고 Secrets 에서 읽습니다. (공개 저장소 노출 방지)
    # Secrets 예시:
    # [emergency]
    # name = "안전관리자"
    # phone = "010-0000-0000"

    try:
        이름 = str(st.secrets["emergency"].get("name", "안전관리자")).strip()
        번호 = str(st.secrets["emergency"]["phone"]).strip()
    except Exception:
        return None, None

    if not 번호:
        return None, None

    return 이름 or "안전관리자", 번호


def 긴급배너():

    이름, 번호 = 긴급연락처()

    # 전화 아이콘 (이모지 대신 SVG → 흰 원 안에 빨간 수화기로 선명하게 표시)
    아이콘 = (
        '<span class="emg-icon"><svg viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M6.62 10.79a15.05 15.05 0 0 0 6.59 6.59l2.2-2.2a1 1 0 0 1 1.02-.24 '
        '11.4 11.4 0 0 0 3.57.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5'
        'a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1.02l-2.2 2.2z"/></svg></span>'
    )

    if 번호:
        전화링크 = "".join(c for c in 번호 if c.isdigit() or c == "+")
        버튼 = f'<a class="emg-call" href="tel:{안전(전화링크)}">{아이콘}{안전(번호)}</a>'
    else:
        버튼 = f'<a class="emg-call" href="tel:119">{아이콘}119</a>'

    st.markdown(
        '<div class="emg-box">'
        + '<div class="emg-title">🚨 긴급 상황은 전화로 먼저</div>'
        + 버튼
        + '</div>',
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
            <div class="stat-bar" style="background-color:{색};"></div>
            <div class="stat-label">
                <span class="stat-dot" style="background-color:{색};"></span>
                {안전(라벨)}
            </div>
            <div class="stat-value" style="color:{색};">{값}<span class="stat-unit">건</span></div>
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
        통계카드("미조치", 미조치수, "#B3261E")

    with s3:
        통계카드("조치중", 조치중수, "#9A5B00")

    with s4:
        통계카드("조치완료", 조치완료수, "#137333")


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
                <span class="info-badge" style="{상태칩스타일(카드상태)}">{안전(카드상태)}</span>
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

    with st.container(border=True, key=f"card_row_{버튼키}"):

        c1, c2 = st.columns([5, 1.35], vertical_alignment="center")

        with c1:
            st.markdown(
                f"""
                <div class="row-wrap">
                    <div class="row-top">
                        <span class="chip chip-status" style="{상태칩스타일(상태)}">{안전(상태)}</span>
                        <span class="chip chip-id">#{안전(제보ID)}</span>
                        {태그}
                    </div>
                    <div class="row-body">{안전(내용)}</div>
                    <div class="row-meta">📍 {안전(제보.get("location", "-"))} · 🕒 {안전(생성시간)}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with c2:
            눌림 = st.button(
                "상세 보기 ›",
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

# 기존 10개 이름은 그대로 두고(이미 쌓인 제보 데이터와 호환), 빠져 있던 유형만 추가
위험유형목록 = [
    "끼임",
    "절단·베임·찔림",
    "추락",
    "충돌",
    "맞음(낙하·비래)",
    "깔림·뒤집힘",
    "무너짐",
    "미끄러짐·넘어짐",
    "중량물",
    "무리한 동작(근골격계)",
    "화재·폭발",
    "감전",
    "이상온도 접촉(화상)",
    "화학물질",
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

    # 홈 화면 전용: PC(가로 769px 이상)에서만 내용을 화면 상하 중앙에 배치
    # 휴대폰 화면과 다른 페이지에는 영향 없음
    st.markdown(
        """
        <style>
        @media (min-width: 769px) {

            /* 바깥 영역: 위아래 여백 제거 */
            .block-container,
            [data-testid="stMainBlockContainer"] {
                padding-top: 0 !important;
                padding-bottom: 0 !important;
            }

            /* 내용을 직접 담는 영역: 화면 높이만큼 늘리고 그 안에서 세로 가운데 정렬
               (Streamlit 버전마다 구조가 달라 두 가지 경로를 모두 지정) */
            .block-container > div[data-testid="stVerticalBlock"],
            [data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"],
            .block-container > div > div[data-testid="stVerticalBlock"],
            [data-testid="stMainBlockContainer"] > div > div[data-testid="stVerticalBlock"] {
                /* 화면 맨 위의 보이지 않는 스타일 요소가 차지하는 높이만큼 빼서
                   위·아래 여백이 같아지도록 보정 */
                min-height: calc(100vh - 48px);
                display: flex;
                flex-direction: column;
                justify-content: center;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    홈로고 = f'<img src="{logo_image}">' if logo_image else ""
    홈구분 = '<span class="home-div"></span>' if logo_image else ""

    st.markdown(
        '<div class="home-header">'
        + 홈로고
        + 홈구분
        + '<span class="home-title">안전제보시스템</span>'
        + '</div>',
        unsafe_allow_html=True
    )

    여백A, 배너칸, 여백B = st.columns([0.5, 8, 0.5])

    with 배너칸:
        긴급배너()

    여백L, col1, col2, 여백R = st.columns([0.5, 4, 4, 0.5], gap="medium")

    with col1:

        with st.container(border=True, key="card_home_worker"):

            사진 = f'<img src="{worker_image}">' if worker_image else "👷"

            st.markdown(
                f'<div class="home-card-mark"></div><div class="home-photo">{사진}</div>'
                + '<div class="home-card-desc">위험요인 제보 · 처리현황 확인</div>',
                unsafe_allow_html=True
            )

            if st.button(
                "근로자",
                type="primary",
                use_container_width=True,
                key="worker_button"
            ):
                st.session_state.화면 = "제보"
                st.rerun()

    with col2:

        with st.container(border=True, key="card_home_admin"):

            사진 = f'<img src="{admin_image}">' if admin_image else "🔐"

            st.markdown(
                f'<div class="home-card-mark"></div><div class="home-photo">{사진}</div>'
                + '<div class="home-card-desc">제보 확인 · 조치 등록 (로그인 필요)</div>',
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
# 7-1. 근로자 영역 (폴더형 탭: 왼쪽 탭 / 오른쪽 본문)
#   - 첫 화면에서 근로자를 누르면 '제보하기' 탭이 먼저 열립니다.
#   - 왼쪽 탭을 누르면 오른쪽 본문만 바뀝니다.
# =========================================================

elif st.session_state.화면 in ("근로자메뉴", "제보", "처리현황"):

    # 예전 '근로자 메뉴' 화면은 없어졌으므로 제보하기 탭으로 보냄
    if st.session_state.화면 == "근로자메뉴":
        st.session_state.화면 = "제보"

    현재탭 = st.session_state.화면

    내비게이션(
        ["근로자", "제보하기" if 현재탭 == "제보" else "처리현황"],
        뒤로=("← 처음 화면", 이동_홈),
        홈버튼=False
    )

    탭칸, 본문칸 = st.columns([1.1, 5], gap="small")

    with 탭칸:

        with st.container(key="folder_tabs"):

            st.button(
                "📝  제보하기",
                key="tab_report",
                type="primary" if 현재탭 == "제보" else "secondary",
                on_click=탭_제보,
                use_container_width=True
            )

            st.button(
                "📋  처리현황",
                key="tab_status",
                type="primary" if 현재탭 == "처리현황" else "secondary",
                on_click=탭_처리현황,
                use_container_width=True
            )

    with 본문칸:

        패널키 = "folder_panel_report" if 현재탭 == "제보" else "folder_panel_status"

        with st.container(key=패널키):

            # -------------------------------------------------
            # 탭 1. 제보하기
            # -------------------------------------------------

            if 현재탭 == "제보":

                페이지헤더("안전제보", "현장에서 발견한 유해·위험요인을 입력해주세요.")

                긴급배너()

                with st.container(border=True, key="card_report_form"):

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

                    내용 = st.text_area(
                        "유해·위험요인 내용",
                        placeholder="발견한 위험요인을 구체적으로 작성해주세요.",
                        height=190
                    )

                    위험유형 = st.selectbox(
                        "위험유형",
                        [AI자동분류] + 위험유형목록,
                        key="report_risk"
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

                                AI분류됨 = False

                                if 위험유형 == AI자동분류:
                                    with st.spinner("AI가 위험유형을 분류하는 중입니다."):
                                        최종유형 = AI_위험유형분류(부서, 단위작업, 내용.strip())
                                    AI분류됨 = True
                                else:
                                    최종유형 = 위험유형

                                데이터 = {
                                    "department": 부서,
                                    "location": 단위작업,
                                    "risk_type": 최종유형,
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
                                    if AI분류됨:
                                        st.info(f"AI가 분류한 위험유형: **{최종유형}** (관리자가 확인 후 수정할 수 있습니다.)")
                                    st.info(
                                        "관리자가 확인 후 처리상태를 변경합니다. 왼쪽 처리현황 탭에서 진행 상황을 볼 수 있습니다."
                                    )
                                else:
                                    st.error("제보 등록 결과를 확인할 수 없습니다.")

                            except Exception as e:
                                st.error("제보 등록 중 오류가 발생했습니다.")
                                st.code(str(e))

            # -------------------------------------------------
            # 탭 2. 처리현황 확인
            # -------------------------------------------------

            else:

                # -----------------------------------------------------
                # 8-1-1. 처리현황 상세
                # -----------------------------------------------------

                if st.session_state.현황상세ID is not None:

                    현황ID = st.session_state.현황상세ID

                    st.button(
                        "← 목록으로",
                        key="status_back_list",
                        on_click=이동_처리현황목록
                    )

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

                    with st.container(border=True, key="card_status_filter"):

                        현황검색어 = st.text_input(
                            "검색어",
                            placeholder="🔍 키워드를 검색하세요.",
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
                        f'<div class="list-count">조회 결과 <b>{len(현황결과)}</b>건</div>',
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



# =========================================================
# 9. 관리자 로그인
# =========================================================

elif (
    st.session_state.화면 == "관리자"
    and not st.session_state.관리자로그인
):

    내비게이션(
        ["관리자 로그인"],
        뒤로=("← 처음 화면", 이동_홈),
        홈버튼=False
    )

    페이지헤더("관리자 로그인", "관리자 계정으로 로그인해주세요.")

    st.markdown('<div class="login-space"></div>', unsafe_allow_html=True)

    l1, l2, l3 = st.columns([1, 2, 1])

    with l2:

        with st.container(border=True, key="card_login"):

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

                등록ID, 등록비밀번호 = 관리자계정()

                if not 등록ID or not 등록비밀번호:
                    st.error(
                        "관리자 계정이 설정되지 않았습니다. secrets 에 admin 항목을 추가해주세요."
                    )

                elif 관리자ID == 등록ID and 관리자비밀번호 == 등록비밀번호:
                    st.session_state.관리자로그인 = True
                    st.rerun()

                else:
                    st.error("ID 또는 비밀번호가 올바르지 않습니다.")


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

        내비게이션(
            ["관리자", "제보 목록", f"#{상세ID}"],
            뒤로=("← 제보 목록", 이동_관리자목록),
            로그아웃=True
        )

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

        else:

            페이지헤더(
                "안전제보 상세",
                f"제보 #{상세ID} 의 내용을 확인하고 조치를 등록합니다."
            )

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
                ⚠️ AI가 생성한 참고 초안입니다. 반드시 안전관리자가 검토·수정한 후 저장하세요.
                </div>
                """,
                unsafe_allow_html=True
            )

            a1, a2 = st.columns(2)

            with a1:

                if st.button(
                    "🤖 AI 조치방안 생성",
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
                    "↓ 처리내용란에 넣기",
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

            with st.container(border=True, key="card_process"):

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

                현재유형 = 제보.get("risk_type", "기타")

                if 현재유형 not in 위험유형목록:
                    현재유형 = "기타"

                새로운유형 = st.selectbox(
                    "위험유형 (AI 분류가 맞지 않으면 수정)",
                    위험유형목록,
                    index=위험유형목록.index(현재유형),
                    key=f"detail_risk_{상세ID}"
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
                    "💾 처리내용 및 상태 저장",
                    type="primary",
                    use_container_width=True,
                    key=f"detail_save_{상세ID}"
                ):

                    try:

                        저장데이터 = {
                            "status": 새로운상태,
                            "risk_type": 새로운유형,
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

                        이동_관리자목록()
                        st.rerun()

                    except Exception as e:

                        st.error("제보 삭제 중 오류가 발생했습니다.")
                        st.code(str(e))

        # 상세 화면도 길어서 맨 아래에 이동 버튼을 둡니다.
        내비게이션(
            ["관리자", "제보 목록", f"#{상세ID}"],
            뒤로=("← 제보 목록", 이동_관리자목록),
            키="bottom",
            로그아웃=True,
            경로표시=False
        )


    # =====================================================
    # 10-2. 관리자 목록
    # =====================================================

    else:

        내비게이션(
            ["관리자", "제보 목록"],
            뒤로=None,
            로그아웃=True
        )

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

        with st.container(border=True, key="card_admin_filter"):

            검색어 = st.text_input(
                "검색어",
                placeholder="🔍 키워드를 검색하세요."
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
                f'<div class="list-count">검색 결과 <b>{len(필터결과)}</b>건</div>',
                unsafe_allow_html=True
            )

        with 목록2:

            if 필터결과:

                엑셀데이터, 엑셀오류 = 엑셀만들기(필터결과)

                if 엑셀오류:
                    st.caption(엑셀오류)
                else:
                    st.download_button(
                        "📥 엑셀 다운로드",
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

        내비게이션(
            ["관리자", "제보 목록"],
            뒤로=None,
            키="bottom",
            로그아웃=True,
            경로표시=False
        )
