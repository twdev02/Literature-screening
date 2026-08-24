import io
import os
import re
import time
import xml.etree.ElementTree as ET
import google.generativeai as genai
import pandas as pd
import requests
import rispy  # 👈 GIE RIS 파일 파싱용
import streamlit as st

st.set_page_config(
    page_title="Taewoong Medical - AI 문헌 스크리닝", layout="wide"
)

# --------------------------------------------------
# 🛡️ 브라우저 새로고침(F5) 및 탭 닫기 이탈 방지 스크립트
# --------------------------------------------------
st.components.v1.html(
    """
    <script>
    window.addEventListener('beforeunload', function (e) {
        e.preventDefault();
        e.returnValue = '';
    });
    </script>
    """,
    height=0,
)

# --------------------------------------------------
# 🔤 마크다운 별표(**)를 유니코드 굵은 글씨로 변환하는 함수
# --------------------------------------------------
def to_unicode_bold(text):
    if not text:
        return text
    bold_map = {
        'A': '𝐀', 'B': '𝐁', 'C': '𝐂', 'D': '𝐃', 'E': '𝐄', 'F': '𝐅', 'G': '𝐆', 'H': '𝐇', 'I': '𝐈', 'J': '𝐉', 'K': '𝐊', 'L': '𝐋', 'M': '𝐌', 'N': '𝐍', 'O': '𝐎', 'P': '𝐏', 'Q': '𝐐', 'R': '𝐑', 'S': '𝐒', 'T': '𝐓', 'U': '𝐔', 'V': '𝐕', 'W': '𝐖', 'X': '𝐗', 'Y': '𝐘', 'Z': '𝐙',
        'a': '𝐚', 'b': '𝐛', 'c': '𝐜', 'd': '𝐝', 'e': '𝐞', 'f': '𝐟', 'g': '𝐠', 'h': '𝐡', 'i': '𝐢', 'j': '𝐣', 'k': '𝐤', 'l': '𝐥', 'm': '𝐦', 'n': '𝐧', 'o': '𝐨', 'p': '𝐩', 'q': '𝐪', 'r': '𝐫', 's': '𝐬', 't': '𝐭', 'u': '𝐮', 'v': '𝐯', 'w': '𝐰', 'x': '𝐱', 'y': '𝐲', 'z': '𝐳'
    }
    def replace_bold(match):
        word = match.group(1)
        return "".join(bold_map.get(c, c) for c in word)
    
    return re.sub(r'\*\*(.*?)\*\*', replace_bold, text)

# --------------------------------------------------
# 🎨 고급 커스텀 CSS (기존 비율 유지 + 깨짐 방지)
# --------------------------------------------------
st.markdown(
    """
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        max-width: 96% !important;
    }
    html, body, [data-testid="stAppViewContainer"] {
        overflow-y: auto !important;
        height: auto !important;
    }
    section[data-testid="stSidebar"] {
        font-size: 15px !important;
    }
    section[data-testid="stSidebar"] label {
        font-size: 14px !important;
        font-weight: 700 !important;
    }
    section[data-testid="stSidebar"] input {
        font-size: 14px !important;
        padding: 8px 12px !important;
    }
    div[data-testid="stFileUploader"] label p {
        letter-spacing: -0.8px !important;
        white-space: nowrap !important;
    }
    .hero-container {
        background: linear-gradient(135deg, #0b1a2d 0%, #1a324b 100%);
        padding: 28px 32px;
        border-radius: 16px;
        color: #ffffff;
        box-shadow: 0 10px 20px -3px rgba(11, 26, 45, 0.3);
        margin-bottom: 20px;
        border-left: 6px solid #00a8ff;
    }
    .hero-header-flex { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .hero-tag { background: linear-gradient(90deg, #84cc16 0%, #06b6d4 100%); color: #ffffff; font-size: 12px; font-weight: 800; padding: 4px 12px; border-radius: 20px; text-transform: uppercase; }
    .dept-tag { color: #94a3b8; font-size: 13px; font-weight: 600; }
    .hero-title { font-size: 26px; font-weight: 800; color: #ffffff; margin: 4px 0px 6px 0px; letter-spacing: -0.5px; }
    .hero-subtitle { font-size: 14px; color: #cbd5e1; margin-bottom: 0px; font-weight: 400; }
    .card-title { font-size: 12px; font-weight: 700; color: #0284c7; text-transform: uppercase; margin-bottom: 4px; }
    .card-value { font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 4px; letter-spacing: -0.3px; white-space: normal !important; word-break: keep-all !important; }
    .card-desc { font-size: 12px; color: #64748b; margin-bottom: 12px; word-break: keep-all !important; }
    .selected-category-box { background-color: rgba(11, 26, 45, 0.04); border: 1px solid rgba(11, 26, 45, 0.12); border-left: 5px solid #0284c7; border-radius: 12px; padding: 16px 22px; margin-bottom: 18px; }
    .selected-category-label { font-size: 11px; font-weight: 800; color: #0284c7; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px; }
    .selected-category-title { font-size: 20px; font-weight: 800; color: #0f172a; margin: 0; }
    div[data-testid="stSegmentedControl"] { background-color: #f1f5f9; padding: 6px; border-radius: 12px; border: 1px solid #e2e8f0; display: flex !important; flex-wrap: nowrap !important; overflow-x: auto !important; }
    div[data-testid="stSegmentedControl"] button { border-radius: 8px !important; font-weight: 1000 !important; font-size: 13px !important; border: none !important; padding: 8px 14px !important; white-space: nowrap !important; transition: all 0.2s ease !important; flex: 1 1 auto !important; }
    div[data-testid="stSegmentedControl"] button[aria-selected="true"] { background-color: #0b1a2d !important; color: #ffffff !important; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important; }
    .prod-item-title { font-weight: 700; font-size: 15px; color: #0f172a; white-space: normal !important; word-break: keep-all !important; margin-bottom: 6px; }
    .prod-item-desc { font-size: 13px; color: #475569; word-break: break-word !important; line-height: 1.5; }
    .result-summary-box { display: flex; gap: 12px; margin-bottom: 16px; }
    .res-card { flex: 1; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px; text-align: center; }
    .res-card-label { font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 4px; }
    .res-card-val { font-size: 22px; font-weight: 800; }
    .res-card.inc { border-top: 3px solid #10b981; background: #f0fdf4; }
    .res-card.inc .res-card-val { color: #166534; }
    .res-card.exc { border-top: 3px solid #ef4444; background: #fef2f2; }
    .res-card.exc .res-card-val { color: #991b1b; }
    .res-card.pending { border-top: 3px solid #f59e0b; background: #fffbeb; }
    .res-card.pending .res-card-val { color: #92400e; }
    .res-card.dup { border-top: 3px solid #64748b; background: #f8fafc; }
    .res-card.dup .res-card-val { color: #334155; }
</style>
""",
    unsafe_allow_html=True,
)

# --------------------------------------------------
# ⚙️ Session State 메모리 저장소 초기화
# --------------------------------------------------
if "tab1_result" not in st.session_state:
    st.session_state["tab1_result"] = None
if "tab2_result" not in st.session_state:
    st.session_state["tab2_result"] = None
if "tab3_result" not in st.session_state:
    st.session_state["tab3_result"] = None
if "tab_gie_result" not in st.session_state:
    st.session_state["tab_gie_result"] = None
if "tab_ct_result" not in st.session_state:
    st.session_state["tab_ct_result"] = None

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0
if "show_reset_msg" not in st.session_state:
    st.session_state["show_reset_msg"] = False
if "screened_history" not in st.session_state:
    st.session_state["screened_history"] = {}
if "radio_category" not in st.session_state:
    st.session_state["radio_category"] = None


def clear_screening_results():
    st.session_state["tab1_result"] = None
    st.session_state["tab2_result"] = None
    st.session_state["tab3_result"] = None
    st.session_state["tab_gie_result"] = None
    st.session_state["tab_ct_result"] = None

def reset_to_home():
    clear_screening_results()
    st.session_state["radio_category"] = None

def clear_history():
    st.session_state["screened_history"] = {}
    st.session_state["uploader_key"] += 1  
    st.session_state["show_reset_msg"] = True  

def render_result_dashboard(df):
    total_cnt = len(df)
    inc_cnt = len(df[df["AI 판정"] == "Include (포함)"])
    exc_cnt = len(df[df["AI 판정"] == "Exclude (제외)"])
    pending_cnt = len(df[df["AI 판정"].str.contains("Full-text Screening Needed|Manual Review Needed", na=False)])
    dup_cnt = len(df[df["AI 판정"].str.contains("Duplicated", na=False)])

    st.markdown(
        f"""
        <div class="result-summary-box">
            <div class="res-card">
                <div class="res-card-label">전체 대상</div>
                <div class="res-card-val">{total_cnt}건</div>
            </div>
            <div class="res-card inc">
                <div class="res-card-label">Include (포함)</div>
                <div class="res-card-val">{inc_cnt}건</div>
            </div>
            <div class="res-card exc">
                <div class="res-card-label">Exclude (제외)</div>
                <div class="res-card-val">{exc_cnt}건</div>
            </div>
            <div class="res-card pending">
                <div class="res-card-label">Full-Text/Manual Review Needed</div>
                <div class="res-card-val">{pending_cnt}건</div>
            </div>
            <div class="res-card dup">
                <div class="res-card-label">Duplicated (중복)</div>
                <div class="res-card-val">{dup_cnt}건</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# --------------------------------------------------
# ⚙️ 사이드바 UI 구성
# --------------------------------------------------
with st.sidebar:
    st.header("시스템 설정")

    # 1. Gemini API 키 불러오기 (클라우드 Secrets 우선)
    try:
        default_api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        default_api_key = ""

    user_api_key = st.text_input(
        "Gemini API Key (미입력 시 클라우드 기본키 적용)", type="password"
    )
    api_key = user_api_key.strip() if user_api_key.strip() else default_api_key

    # 2. NCBI API 키 불러오기 (화면 입력창 숨김, 백그라운드에서만 로드)
    try:
        ncbi_api_key = st.secrets["NCBI_API_KEY"]
    except Exception:
        ncbi_api_key = ""

    # 연결 상태 표시
    if api_key:
        st.success("Gemini API Key 등록 완료")
    else:
        st.error("Gemini API Key가 필요합니다.")
        
    st.markdown("---")
    st.subheader("품목 선택")

    category_options = [
        "1. Biliary Stent",
        "2. Esophageal Stent",
        "3. Pyloric/Duodenal Stent",
        "4. Colonic Stent",
        "5. Drainage Stent",
    ]

    due_category = st.radio(
        "스크리닝할 카테고리를 선택하세요",
        options=category_options,
        index=(
            category_options.index(st.session_state["radio_category"])
            if st.session_state.get("radio_category") in category_options
            else None
        ),
        key="radio_category",
        on_change=clear_screening_results,
    )

    current_engine = st.session_state.get("engine_mode_seg", "PubMed Engine")
    sub_model = None

    if current_engine == "ClinicalTrials Engine":
        st.markdown(
        """
        <div style="background-color: #f0f7ff; border-left: 4px solid #0284c7; padding: 10px 14px; border-radius: 6px; font-size: 13px; color: #0f172a; line-height: 1.5; word-break: keep-all;">
            ClinicalTrials.gov는 세부 모델 구분 없이 선택하신 [품목 전체] 통합 검색이 적용됩니다.
        </div>
        """,
        unsafe_allow_html=True
    )
        sub_model = "통합 품목 검색"
    else:
        if due_category == "1. Biliary Stent":
            sub_model = st.selectbox(
                "세부 모델/유형을 선택하세요",
                options=[
                    "Niti-S Biliary Uncovered Stent",
                    "Niti-S Biliary Covered Stent",
                    "ComVi Biliary Stent",
                ],
                index=0,
                key="sb_biliary",
                on_change=clear_screening_results,
            )
        elif due_category == "2. Esophageal Stent":
            sub_model = st.selectbox(
                "세부 모델/유형을 선택하세요",
                options=["Niti-S Esophageal Covered Stent"],
                index=0,
                key="sb_esophageal",
                on_change=clear_screening_results,
            )
        elif due_category == "3. Pyloric/Duodenal Stent":
            sub_model = st.selectbox(
                "세부 모델/유형을 선택하세요",
                options=[
                    "Niti-S Pyloric/Duodenal Uncovered Stent",
                    "Niti-S Pyloric/Duodenal Covered Stent",
                    "ComVi Pyloric/Duodenal Stent",
                ],
                index=0,
                key="sb_pyloric",
                on_change=clear_screening_results,
            )
        elif due_category == "4. Colonic Stent":
            sub_model = st.selectbox(
                "세부 모델/유형을 선택하세요",
                options=[
                    "Niti-S Enteral Colonic Uncovered Stent",
                    "Niti-S Enteral Colonic Covered Stent",
                    "ComVi Enteral Colonic Stent",
                ],
                index=0,
                key="sb_colonic",
                on_change=clear_screening_results,
            )
        elif due_category == "5. Drainage Stent":
            sub_model = st.selectbox(
                "세부 모델/유형을 선택하세요",
                options=[
                    "Niti-S SPAXUS Stent",
                    "Niti-S Hot SPAXUS Stent",
                    "Niti-S Nagi Stent",
                ],
                index=0,
                key="sb_drainage",
                on_change=clear_screening_results,
            )

    st.markdown("---")
    history_cnt = len(st.session_state["screened_history"])
    st.caption(f"현재 누적 스크리닝 이력: **{history_cnt}건**")

    with st.expander("이전 스크리닝 CSV 불러오기"):
        history_files = st.file_uploader(
            "과거 스크리닝 결과 CSV 선택 (복수 가능)",
            type=["csv"],
            accept_multiple_files=True,
            key=f"history_csv_uploader_{st.session_state['uploader_key']}", 
        )
        if st.button("이력 메모리에 복원", use_container_width=True):
            if history_files:
                restored_count = 0
                for h_file in history_files:
                    try:
                        try:
                            h_df = pd.read_csv(h_file, encoding="utf-8")
                        except UnicodeDecodeError:
                            h_df = pd.read_csv(h_file, encoding="cp949")

                        for _, row in h_df.iterrows():
                            identifier = None
                            if "PMID" in row and pd.notna(row["PMID"]):
                                identifier = str(row["PMID"]).replace(".0", "").strip()
                            elif "NCT 번호 (URL)" in row and pd.notna(row["NCT 번호 (URL)"]):
                                identifier = str(row["NCT 번호 (URL)"]).split('/')[-1].strip().lower()
                            elif "DOI / URL" in row and pd.notna(row["DOI / URL"]):
                                identifier = str(row["DOI / URL"]).strip().lower()
                            elif "논문 제목" in row and pd.notna(row["논문 제목"]):
                                identifier = str(row["논문 제목"]).strip().lower()
                            elif "임상시험 제목" in row and pd.notna(row["임상시험 제목"]):
                                identifier = str(row["임상시험 제목"]).strip().lower()

                            if identifier and identifier != "-":
                                cat = str(row.get("카테고리", "기존 이력"))
                                mod = str(row.get("세부 모델", "과거 CSV"))
                                res = str(row.get("AI 판정", "Screened"))

                                st.session_state["screened_history"][identifier] = {
                                    "category": cat,
                                    "sub_model": mod,
                                    "result": res,
                                }
                                restored_count += 1
                        st.success(f"총 {restored_count}건의 이력이 복원되었습니다!")
                    except Exception as e:
                        st.error(f"파일 읽기 오류 ({h_file.name}): {str(e)}")
            else:
                st.warning("복원할 CSV 파일을 선택하세요.")

    if st.button("이전 스크리닝 기록 초기화"):
        clear_history()

    if st.session_state.get("show_reset_msg", False):
        st.success("✅ 누적 기록 및 업로드 파일이  \n성공적으로 초기화되었습니다.")
        st.session_state["show_reset_msg"] = False  
        time.sleep(2)  
        st.rerun()    

    st.markdown("---")
    st.button(
        "HOME",
        type="secondary",
        use_container_width=True,
        on_click=reset_to_home,
    )

# --------------------------------------------------
# 🏠 1. 카테고리가 아예 선택되지 않았을 때 홈 대시보드
# --------------------------------------------------
if not due_category:
    st.markdown(
        """<div class="hero-container">
<div class="hero-header-flex">
<div class="hero-tag">TAEWOONG MEDICAL CLINICAL EVALUATION PLATFORM</div>
<div class="dept-tag">Development Department | Development 2nd Team</div>
</div>
<div class="hero-title">AI 문헌 스크리닝 시스템</div>
<div class="hero-subtitle">Medical Device Regulatory Compliance & Systematic Literature Review Powered by Gemini 3.6 Flash</div>
</div>""",
        unsafe_allow_html=True,
    )
    col_ov1, col_ov2, col_ov3 = st.columns([2.5, 1, 1.5])
    with col_ov1:
        with st.container(border=True):
            st.markdown(
                """
                <div class="card-title">TARGET PRODUCTS</div>
                <div class="card-value">Taewoong Medical’s Stent Product Lines</div>
                <div class="card-desc">사이드바에서 스크리닝할 품목을 선택해주세요.</div>
                """,
                unsafe_allow_html=True,
            )
    with col_ov2:
        with st.container(border=True):
            st.markdown(
                """
                <div class="card-title">AI PIPELINE</div>
                <div class="card-value">Gemini 3.6 Flash + PubMed / GIE / ClinicalTrials</div>
                <div class="card-desc">AI 기반 문헌 스크리닝 (Open Access 지원)</div>
                <br>
                """,
                unsafe_allow_html=True,
            )
    with col_ov3:
        with st.container(border=True):
            st.markdown(
                """
                <div class="card-title">REGULATORY GOAL</div>
                <div class="card-value">Standardization and Automation of Literature Review</div>
                <div class="card-desc">일관성 및 추적성을 확보한 스크리닝 기록</div>
                <br>
                """,
                unsafe_allow_html=True,
            )
    st.stop()

# --------------------------------------------------
# 🔬 세부 모델별 프롬프트 및 PICO 키워드 세팅
# --------------------------------------------------
if due_category == "1. Biliary Stent":
    include_criteria = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Malignant biliary obstruction/stricture, Benign biliary obstruction/stricture, Benign pancreatic duct stricture
5. Intervention: Biliary SEMS (Uncovered or Covered). Specific Taewoong Medical models: Niti-S (S, D, M, LCD, Full Covered, Both Bare, Giobor, Flare, Kaffes, Bumpy), ComVi (Full Covered, Both Bare, End Bare)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (e.g., WallFlex, Evolution, EGIS, Bonastent, Hanarostent)
7. Outcomes: Stent patency, Decreased bilirubin, Technical/Clinical success, Complications, Stent removal (for benign cases)"""
    exclude_criteria = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-biliary/pancreatic target areas only (e.g., vascular, esophageal, colonic, tracheal)
3. Irrelevant articles: Articles not related to biliary/pancreatic luminal stenting or stricture management (e.g., EUS-CDS, EUS-HGS primary LAMS procedures, RFA combined therapies, vascular reconstructions)
4. Non-study publications: Editorials, letters, comments, study protocols (단, Review 및 Case report는 제외하지 않음)
5. Insufficient Information: Valid information relevant to performance and/or safety is limited.
6. Held by Taewoong: This article is already held by Taewoong Medical."""

    if sub_model == "Niti-S Biliary Uncovered Stent":
        default_p, default_i, default_c, default_o = "Biliary obstruction\nBiliary stricture\nMalignant biliary stricture\nMalignant biliary obstruction", "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nUncovered stent", "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nUncovered stent\nEvolution\nWallFlex\nEGIS\nBonastent\nHanarostent", "Stent patency\nDecreased bilirubin"
    elif sub_model == "Niti-S Biliary Covered Stent":
        default_p, default_i, default_c, default_o = "Biliary obstruction\nBiliary stricture\nBenign biliary stricture\nBenign biliary obstruction\nMalignant biliary stricture\nMalignant biliary obstruction\nBenign pancreatic duct stricture", "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nCovered stent", "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nEvolution\nWallFlex\nEGIS\nBonastent\nHanarostent", "Stent patency\nDecreased bilirubin\nRemoval"
    elif sub_model == "ComVi Biliary Stent":
        default_p, default_i, default_c, default_o = "Biliary obstruction\nBiliary stricture\nMalignant biliary stricture\nMalignant biliary obstruction", "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nComVi\nCovered stent", "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nEvolution\nWallFlex\nEGIS\nBonastent\nHanarostent", "Stent patency\nDecreased bilirubin"
    else:
        default_p, default_i, default_c, default_o = "Biliary obstruction\nBiliary stricture\nMalignant biliary stricture\nMalignant biliary obstruction\nBenign biliary obstruction\nBenign biliary stricture\nBenign pancreatic duct stricture", "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nComVi\nUncovered stent\nCovered stent", "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nUncovered stent\nEvolution\nWallFlex\nEGIS\nBonastent\nHanarostent", "Stent patency\nDecreased bilirubin\nRemoval"

elif due_category == "2. Esophageal Stent":
    include_criteria = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Esophageal stricture/obstruction (Malignant or Benign), Refractory benign esophageal stricture, Tracheoesophageal fistula (TEF / TE fistula)
5. Intervention: Esophageal SEMS, Covered type. Specific Taewoong Medical models: Niti-S Esophageal (Full covered, Cervical, Both bare type, Conio, Anti reflux, Double anti reflux, Double type, Beta-2)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (WallFlex, Ultraflex, Evolution, Hanarostent, Aixstent, EGIS, Bonastent, Micro-Tech)
7. Outcomes: Stent patency, Dysphagia improvement, Fistula closure, Removal (in benign strictures)"""
    exclude_criteria = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-esophageal target areas only (e.g., pure systemic/chemotherapy outcomes, non-stricture indications)
3. Irrelevant articles: Articles not related to esophageal stenting, stricture dilation, or TE fistula management
4. Non-study publications: Editorials, letters, comments, study protocols (단, Review 및 Case report는 제외하지 않음)
5. Insufficient Information: Valid information relevant to performance and/or safety is limited.
6. Held by Taewoong: This article is already held by Taewoong Medical."""
    default_p, default_i, default_c, default_o = "Esophageal stricture\nEsophageal obstruction\nMalignant esophageal stricture\nMalignant esophageal obstruction\nBenign esophageal stricture\nRefractory benign esophageal stricture\nBenign esophgeal obstruction\nTracheoesophageal fistula", "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nCovered stent", "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nWallFlex\nUltraflex\nEvolution\nHanarostent\nAixstent\nEGIS\nBonastent\nMicro-tech", "Stent patency\nDysphagia improvement\nFistula closure\nRemoval"

elif due_category == "3. Pyloric/Duodenal Stent":
    include_criteria = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Pyloric/Duodenal stricture or obstruction, Gastric Outlet Obstruction (GOO), Malignant or Benign
5. Intervention: Pyloric/Duodenal SEMS, Uncovered or Covered type. Specific Taewoong Medical models: Niti-S Pyloric/Duodenal (D-Type, Full Covered, Both Bare, End Bare), ComVi Pyloric/Duodenal (Flare-Type, Both Bare)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (WallFlex, WallFlex Soft, Hanarostent, Evolution, EGIS, Bonastent)
7. Outcomes: Stent patency, Obstruction relief/resolution/improvement, GOOSS score / Oral intake, Technical/Clinical success, Complications, Stent removal"""
    exclude_criteria = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-pyloric/duodenal target areas only
3. Irrelevant articles: Articles not related to pyloric/duodenal stenting or GOO management
4. Non-study publications: Editorials, letters, comments, study protocols
5. Insufficient Information: Valid information relevant to performance and/or safety is limited.
6. Held by Taewoong: This article is already held by Taewoong Medical."""
    if sub_model == "Niti-S Pyloric/Duodenal Uncovered Stent":
        default_p, default_i, default_c, default_o = "Pyloric stricture\nPyloric obstruction\nDuodenal stricture\nDuodenal obstruction\nGastric outlet obstruction\nMalignant pyloric stricture\nMalignant pyloric obstruction\nMalignant duodenal stricture\nMalignant duodenal obstruction", "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nUncovered stent", "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nUncovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nEvolution\nEGIS\nBonastent", "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement"
    elif sub_model == "Niti-S Pyloric/Duodenal Covered Stent":
        default_p, default_i, default_c, default_o = "Pyloric stricture\nPyloric obstruction\nDuodenal stricture\nDuodenal obstruction\nGastric outlet obstruction\nMalignant pyloric stricture\nMalignant pyloric obstruction\nMalignant duodenal stricture\nMalignant duodenal obstruction\nBenign pyloric stricture\nBenign pyloric obstruction\nBenign duodenal stricture\nBenign duodenal obstruction", "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nCovered stent", "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nEvolution\nEGIS\nBonastent", "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement\nRemoval"
    elif sub_model == "ComVi Pyloric/Duodenal Stent":
        default_p, default_i, default_c, default_o = "Pyloric stricture\nPyloric obstruction\nDuodenal stricture\nDuodenal obstruction\nGastric outlet obstruction\nMalignant pyloric stricture\nMalignant pyloric obstruction\nMalignant duodenal stricture\nMalignant duodenal obstruction", "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nComVi\nCovered stent", "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nEvolution\nEGIS\nBonastent", "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement"
    else:
        default_p, default_i, default_c, default_o = "Pyloric stricture\nDuodenal stricture\nGastric outlet obstruction\nMalignant pyloric stricture\nBenign pyloric stricture", "SEMS\nTaewoong\nNiti-S\nComVi\nCovered stent\nUncovered stent", "Surgery\nPlastic stent\nBalloon dilation\nSEMS\nWallFlex", "Stent patency\nObstruction relief\nRemoval"

elif due_category == "4. Colonic Stent":
    include_criteria = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Colonic/Colorectal stricture or obstruction (Malignant or Benign)
5. Intervention: Colonic SEMS, Uncovered or Covered type. Specific Taewoong Medical models: Niti-S Enteral Colonic (S-Type, D-Type, Full Covered, Both Bare, End Bare), ComVi Enteral Colonic (Both Bare-Type)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (WallFlex, WallFlex Soft, Hanarostent, Micro-Tech, Bonastent)
7. Outcomes: Stent patency, Obstruction relief/resolution/improvement, Technical/Clinical success, Complications, Stent removal"""
    exclude_criteria = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-colonic target areas only
3. Irrelevant articles: Articles not related to colonic stenting or colorectal obstruction management
4. Non-study publications: Editorials, letters, comments, study protocols
5. Insufficient Information: Valid information relevant to performance and/or safety is limited.
6. Held by Taewoong: This article is already held by Taewoong Medical."""
    if sub_model == "Niti-S Enteral Colonic Uncovered Stent":
        default_p, default_i, default_c, default_o = "Colonic stricture\nColonic obstruction\nColorectal stricture\nColorectal obstruction\nMalignant colonic stricture\nMalignant colonic obstruction\nMalignant colorectal stricture\nMalignant colorectal obstruction", "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nUncovered stent", "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nUncovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nMicro-Tech\nBonastent", "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement"
    elif sub_model == "Niti-S Enteral Colonic Covered Stent":
        default_p, default_i, default_c, default_o = "Colonic stricture\nColonic obstruction\nColorectal stricture\nColorectal obstruction\nMalignant colonic stricture\nMalignant colonic obstruction\nMalignant colorectal stricture\nMalignant colorectal obstruction\nBenign colonic stricture\nBenign colonic obstruction\nBenign colorectal stricture\nBenign colorectal obstruction", "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nCovered stent", "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nMicro-Tech\nBonastent", "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement\nRemoval"
    elif sub_model == "ComVi Enteral Colonic Stent":
        default_p, default_i, default_c, default_o = "Colonic stricture\nColonic obstruction\nColorectal stricture\nColorectal obstruction\nMalignant colonic stricture\nMalignant colonic obstruction\nMalignant colorectal stricture\nMalignant colorectal obstruction", "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nComVi\nCovered stent", "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nMicro-Tech\nBonastent", "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement"
    else:
        default_p, default_i, default_c, default_o = "Colonic stricture\nColorectal obstruction\nMalignant colonic stricture\nBenign colonic stricture", "SEMS\nTaewoong\nNiti-S\nComVi\nUncovered stent\nCovered stent", "Surgery\nPlastic stent\nBalloon dilation\nSEMS\nWallFlex", "Stent patency\nObstruction relief\nRemoval"

elif due_category == "5. Drainage Stent":
    include_criteria = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Pancreatic pseudocyst, Walled-off necrosis (WON) / Pancreatic necrosis, Gallbladder drainage (Cholecystitis) / Biliary tract drainage, Transgastric or transduodenal drainage indications
5. Intervention: Lumen-apposing metal stents (LAMS) or EUS-guided drainage stents. Specific Taewoong Medical models: Niti-S Nagi, Niti-S SPAXUS, Niti-S Hot SPAXUS
6. Comparators: Surgery, Percutaneous drainage, Plastic double-pigtail stents, or competitor LAMS (e.g., AXIOS / Hot AXIOS)
7. Outcomes: Technical/Clinical success rate, Drainage efficacy, Resolution of pseudocyst/necrosis, Complications, Removal rate"""
    exclude_criteria = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-drainage target indications
3. Irrelevant articles: Articles not related to transluminal/EUS-guided drainage or LAMS management
4. Non-study publications: Editorials, letters, comments, study protocols
5. Insufficient Information: Valid information relevant to performance and/or safety is limited.
6. Held by Taewoong: This article is already held by Taewoong Medical."""
    if sub_model == "Niti-S SPAXUS Stent":
        default_p, default_i, default_c, default_o = "Pancreatic pseudocyst\nWalled off necrosis\nGallbladder\nBiliary tract", "Self-expandable metallic stent\nSEMS\nLumen apposing metal stent\nLAMS\nEUS gallbladder drainage\nEUS choledochoduodenostomy\nTaewoong\nNiti-S\nSPAXUS", "Surgery\nPercutaneous drainage\nSEMS\nLAMS\nAXIOS\nHot AXIOS", "Pancreatic pseudocyst drainage\nWalled off necrosis drainage\nGallbladder drainage\nBiliary tract drainage"
    elif sub_model == "Niti-S Hot SPAXUS Stent":
        default_p, default_i, default_c, default_o = "Pancreatic pseudocyst\nWalled off necrosis\nGallbladder\nBiliary tract", "SEMS\nLumen apposing metal stent\nLAMS\nEUS gallbladder\nEUS choledochoduodenostomy\nElectrocautery delivery system\nHot delivery\nTaewoong\nNiti-S\nHot SPAXUS", "Surgery\nPercutaneous drainage\nSEMS\nLAMS\nAXIOS\nHot AXIOS", "Pancreatic pseudocyst drainage\nWalled off necrosis drainage\nGallbladder drainage\nBiliary tract drainage"
    elif sub_model == "Niti-S Nagi Stent":
        default_p, default_i, default_c, default_o = "Pancreatic pseudocyst", "SEMS\nLumen apposing metal stent\nLAMS\nBiflanged metal stent\nBFMS\nTaewoong\nNiti-S\nNagi", "Surgery\nPercutaneous drainage\nSEMS\nLAMS\nBiflanged metal stent\nBFMS\nAXIOS\nHot AXIOS", "Pancreatic pseudocyst drainage"
    else:
        default_p, default_i, default_c, default_o = "Pancreatic pseudocyst\nWalled off necrosis\nGallbladder", "SEMS\nLAMS\nTaewoong\nNiti-S\nComVi", "Surgery\nPercutaneous drainage\nLAMS\nAXIOS", "Drainage"

else:
    include_criteria = "Include All Relevant Clinical Papers"
    exclude_criteria = "Exclude Non-Clinical/Irrelevant Papers"
    default_p, default_i, default_c, default_o = "Obstructive Jaundice\nBiliary Stricture", "Biliary Stent\nSEMS", "Surgery\nPlastic stent", "Technical success\nClinical success"

# --------------------------------------------------
# API 기능 및 파싱 함수들
# --------------------------------------------------
def parse_pico_input(text):
    if not text or not text.strip(): return ""
    raw_keywords = text.replace(",", "\n").split("\n")
    keywords = [kw.strip() for kw in raw_keywords if kw.strip()]
    if not keywords: return ""
    formatted = [kw if '"' in kw or "[" in kw else f"({kw})" for kw in keywords]
    return formatted[0] if len(formatted) == 1 else f"({' OR '.join(formatted)})"

def search_pubmed_pmids_pico(p_text, i_text, c_text="", o_text="", start_year=2026, start_month=1, end_year=2026, end_month=12, fetch_all=False, max_results=20, ncbi_api_key=""):
    query_parts = []
    for q in [parse_pico_input(t) for t in [p_text, i_text, c_text, o_text]]:
        if q: query_parts.append(q)
    
    full_query = " AND ".join(query_parts)
    if not full_query: return [], ""

    min_date_str = f"{start_year}/{int(start_month):02d}/01"
    max_date_str = f"{end_year}/{int(end_month):02d}/31"
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

    params_count = {
        "db": "pubmed", "term": full_query, "retmode": "json", "retmax": 0,
        "datetype": "pdat", "mindate": min_date_str, "maxdate": max_date_str,
    }
    if ncbi_api_key: params_count["api_key"] = ncbi_api_key

    try:
        res_count = requests.get(url, params=params_count, timeout=10).json()
        total_found = int(res_count.get("esearchresult", {}).get("count", 0))
        actual_retmax = total_found if fetch_all else min(max_results, total_found)
        if actual_retmax == 0: return [], full_query

        params_fetch = params_count.copy()
        params_fetch["retmax"] = actual_retmax

        response = requests.get(url, params=params_fetch, timeout=10)
        pmid_list = response.json().get("esearchresult", {}).get("idlist", [])
        return pmid_list, full_query
    except Exception as e:
        st.error(f"PubMed 검색 오류: {str(e)}")
        return [], full_query

def fetch_pubmed_by_pmid(pmid, ncbi_api_key=""):
    pmid = str(pmid).replace(".0", "").strip()
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml"
    if ncbi_api_key: url += f"&api_key={ncbi_api_key}"
        
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None, None, None, f"NCBI 서버 통신 실패 (코드 {response.status_code})"

        root = ET.fromstring(response.content)
        article = root.find(".//Article")
        if article is None:
            return None, None, None, "존재하지 않는 PMID이거나 정보가 없습니다."

        title_elem = article.find(".//ArticleTitle")
        title = "".join(title_elem.itertext()).strip() if title_elem is not None else "제목 없음"

        pmcid = None
        pmcid_elem = root.find(".//ArticleIdList/ArticleId[@IdType='pmc']")
        if pmcid_elem is not None:
            pmcid = pmcid_elem.text.strip() 

        abstract_elem = article.find(".//Abstract")
        if abstract_elem is None:
            abstract_elem = root.find(".//OtherAbstract")

        abstract_text = "".join(abstract_elem.itertext()).strip() if abstract_elem is not None else None

        return title, abstract_text, pmcid, "성공"
    except Exception as e:
        return None, None, None, f"데이터 파싱 에러: {str(e)}"

def fetch_pmc_fulltext(pmcid, ncbi_api_key=""):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmcid}&retmode=xml"
    if ncbi_api_key: url += f"&api_key={ncbi_api_key}"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200: return None
        root = ET.fromstring(response.content)
        body_elem = root.find(".//body")
        if body_elem is None: return None
        full_text = "".join(body_elem.itertext()).strip()
        return re.sub(r'\s+', ' ', full_text)
    except Exception:
        return None

# 🚀 [추가/수정] ClinicalTrials.gov (NCT) API 전체/개수제한 수집 함수 (페이지네이션 적용)
def search_clinicaltrials(condition, intervention, status_filters=None, type_filters=None, fetch_all=False, max_results=20):
    url = "https://clinicaltrials.gov/api/v2/studies"
    page_size = 1000 if fetch_all else min(max_results, 1000)
    
    params = {
        "pageSize": page_size,
        "format": "json",
        "countTotal": "true"
    }
    if condition: params["query.cond"] = condition
    if intervention: params["query.intr"] = intervention
    
    if status_filters:
        params["filter.overallStatus"] = ",".join(status_filters)
        
    if type_filters:
        params["filter.studyType"] = ",".join(type_filters)
    
    results = []
    page_token = None
    first_url = None

    try:
        while True:
            current_params = params.copy()
            if page_token:
                current_params["pageToken"] = page_token
            
            response = requests.get(url, params=current_params, timeout=15)
            if response.status_code != 200: 
                return [], "API 통신 에러"
            
            if first_url is None:
                first_url = response.url
                
            data = response.json()
            studies = data.get("studies", [])
            
            for study in studies:
                protocol = study.get("protocolSection", {})
                ident = protocol.get("identificationModule", {})
                desc = protocol.get("descriptionModule", {})
                status_mod = protocol.get("statusModule", {})
                
                nct_id = ident.get("nctId", "Unknown")
                title = desc.get("briefTitle", "제목 없음")
                summary = desc.get("briefSummary", "")
                status = status_mod.get("overallStatus", "Unknown")
                
                results.append((nct_id, title, summary, status))
                
                if not fetch_all and len(results) >= max_results:
                    break
            
            if not fetch_all and len(results) >= max_results:
                results = results[:max_results]
                break
                
            page_token = data.get("nextPageToken")
            if not page_token:
                break
                
        return results, first_url
    except Exception as e:
        return [], str(e)

def call_gemini_with_retry(model, prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            res = model.generate_content(prompt)
            return res.text, None
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                time.sleep(5)
                continue
            return None, str(e)

# --------------------------------------------------
# 🤖 공통 AI 프롬프트 (판정 우선순위 및 Case Report 방어 적용)
# --------------------------------------------------
def generate_prompt(due_category, include_criteria, exclude_criteria, title, article_content):
    return f"""
    너는 의료기기 임상평가(CER) 및 체계적 문헌고찰(Systematic Review) 전문가야. 
    아래 제공된 논문 정보(초록 또는 전문(Full-text))를 정밀하게 읽고, 제공된 [포함기준]과 [제외기준] 및 [인간 평가자 실제 판정 예시]를 학습하여 정확한 판정을 내려라.

    [선택된 카테고리/분류]: {due_category} ({sub_model})

    [엄격한 판정 가이드라인]:
    1. Include 조건: [포함기준]을 완벽히 만족하고, 컴포넌트나 적응증이 임상적으로 타당한 경우 'Include'로 판정한다. 원문(Full-text) 전체가 제공된 경우, 서론보다는 연구 방법(Methods)과 결과(Results) 섹션을 중점적으로 확인하여 평가 대상 기구가 실제 사용되었는지 엄격히 검증하라.
    
    2. CER 통합 보고서 연속성 및 Benign(양성) 처리 핵심 지침 (중요!):
       - 현재 선택된 모델이 Uncovered 라 하더라도, 논문에 Benign(양성) 적응증 관련 내용이 포함되어 있다는 이유만으로 선제적 배제(Exclude)를 하지 말 것!
       - 이유: 본 스크리닝은 하나의 통합 CER 보고서 섹션으로 취급되므로, Uncovered 단계에서 Benign 논문이 불필요하게 Exclude 되면 차후 Covered 단계 검토 시 'Duplicated(중복)' 처리되어 영구 누락되는 사고가 발생함. 양성/악성 모두 유연하게 포용하여 판단할 것.
       
    3. Exclude 판단 핵심 규칙 및 적용 순서 (★반드시 아래 1순위부터 순서대로 검토하여 가장 먼저 해당하는 사유를 적용할 것):
       - 1순위. **Literature without human clinical data**: Preclinical proof-of-concept, In-vitro, 동물실험 연구 등 인간 대상 임상 데이터가 없는 경우.
       - 2순위. **Irrelevant article**: 평가 대상 스텐트 기구(I)가 아닌 타 장기 기구(예: 식도 스텐트 심사 시 기도/기관지 스텐트 사용)를 사용했거나, 스텐트 성과/안전성과 무관한 타 시술/수술(RFA, EIs, 진단 기술 등)이 주목적인 경우.
       - 3순위. **Different indication**: 평가 대상 스텐트 기구(I)를 사용했으나, Target 적응증이 아닌 전혀 무관한 질환/목적으로 사용된 경우.
       - 4순위. **Insufficient information**: 위 1~3순위에 모두 해당하지 않으면서(즉, 올바른 기구와 적응증을 사용했음에도) 아래의 이유로 평가가 불가한 경우에만 최후의 수단으로 적용할 것.
         * Valid information relevant to performance and/or safety is limited: 제공된 텍스트 상 유효 데이터가 부족하여 스텐트의 실제 성능 및 안전성을 확인할 수 없는 경우.
         * Letter / Protocol: 논문 형태가 Letter, Comment, 단순 Study Protocol인 경우. (🚨강력 주의: 서론에서 타 연구를 인용 및 논평하는 문장이 있더라도, 실제 환자의 임상 경과를 다룬 'Case Report'나 'Case Series'라면 절대 이 사유로 배제하지 말고 최우선적으로 Include 할 것!)
       - 5순위. **This article is already held by Taewoong Medical.**: 태웅메디칼 내부 보유 또는 이전에 검토 완료된 문헌인 경우.

    [품목별 인간 평가자 주요 판정 학습 예시 (Few-shot Examples)]:
    - Biliary: Covered SEMS vs Uncovered SEMS 유효성/안전성 Meta-analysis 및 RCT -> Include
    - Esophageal: FC-SEMS 마이그레이션 방지(Suturing 등) 비교 연구 -> Include | 기도/기관지 스텐트(Airway stent) 사용 연구 -> Exclude (Irrelevant article: The study focuses on airway/tracheal stenting rather than esophageal stent placement.)
    - Pyloric/Duodenal: EUS-GJ vs Duodenal SEMS vs SGJ 삼자 비교 Review -> Include | Balloon dilation vs SEMS 비교 -> Include | 2차 Duodenal SEMS 재시술 성과 -> Include | Case Report -> Include
    - Colonic: Emergency Surgery 대비 Bridge 단기 목적 SEMS 성과/생존율 -> Include | CReST2 Trial(완화 목적 Covered vs Uncovered) -> Include | Stent Patency 예측 모델 개발 -> Include
    - Drainage: Percutaneous cystogastrostomy / EUS-GBD / EUS-BD 임상 성과 -> Include | High-surgical-risk 환자 배액술 가이드라인 -> Include | EUS-BD 안전성 실무 임상 -> Include

    [포함기준]:
    {include_criteria}

    [제외기준]:
    {exclude_criteria}

    [평가 대상 논문 정보]
    - [논문 제목]: {title}
    - [제공된 텍스트 (초록 또는 전문)]: 
    {article_content}

    답변형식 (한국어 설명 없이 오직 아래 지정된 영문 형식으로만 완벽히 작성할 것):

    판정: (Include 또는 Exclude)

    Conclusion:
    (영문 사유 1문장)

    [Conclusion 작성 규칙]:
    1. 마크다운 별표(**)를 절대로 사용하지 마라.
    2. Include인 경우: 'Conclusion:' 이라는 말머리나 수식어('Included because' 등)를 일체 붙이지 말고 완결된 1개 영문 문장 자체만 적어라.
    3. Exclude인 경우: 반드시 위에서 지정한 1~5순위 사유 중 가장 먼저 해당하는 정확한 사유의 말머리(예: 'Irrelevant article:', 'Different indication:')를 맨 앞에 붙이고 사유를 적어라.
    """

# --------------------------------------------------
# ✨ 2단계 세그먼티드 컨트롤 메뉴
# --------------------------------------------------
st.markdown(
    f"""
<div class="selected-category-box">
    <div class="selected-category-label">SELECTED CATEGORY & MODEL</div>
    <div class="selected-category-title">{due_category} - {sub_model}</div>
</div>
""",
    unsafe_allow_html=True,
)

target_engine = st.segmented_control(
    "", options=["PubMed Engine", "GIE Journal Engine", "ClinicalTrials Engine"], default="PubMed Engine", key="engine_mode_seg",
)
st.markdown("<br>", unsafe_allow_html=True)

if target_engine == "PubMed Engine":
    selected_mode = st.segmented_control(
        "", options=["PubMed PICO 자동 검색", "PMID 리스트 CSV 업로드", "단일 PMID 입력"], default="PubMed PICO 자동 검색", key="pubmed_sub_mode_seg",
    )
elif target_engine == "GIE Journal Engine":
    selected_mode = st.segmented_control(
        "", options=["GIE RIS 파일 일괄 스크리닝"], default="GIE RIS 파일 일괄 스크리닝", key="gie_sub_mode_seg",
    )
else:
    selected_mode = st.segmented_control(
        "", options=["ClinicalTrials 자동 검색"], default="ClinicalTrials 자동 검색", key="ct_sub_mode_seg",
    )

st.markdown("<br>", unsafe_allow_html=True)

# --------------------------------------------------
# MODE 1: 단일 PMID 테스트
# --------------------------------------------------
if selected_mode == "단일 PMID 입력":
    single_pmid = st.text_input("PubMed PMID 번호를 입력하세요 (예: 31234567)")
    if st.button("단일 PMID 스크리닝 실행"):
        if not api_key:
            st.error("API Key가 설정되지 않았습니다!")
        elif not single_pmid:
            st.error("PMID 번호를 입력해 주세요!")
        else:
            with st.spinner("PubMed 공식 API에서 논문 정보 조회 중..."):
                title, abs_text, pmcid, status = fetch_pubmed_by_pmid(single_pmid, ncbi_api_key)

            pmid_url = f"https://pubmed.ncbi.nlm.nih.gov/{single_pmid.strip()}/"

            article_content = ""
            eval_source = ""

            if pmcid:
                st.info(f"💡 Open Access 논문 확인됨 (PMCID: {pmcid}). 전문(Full-text)을 가져옵니다.")
                full_text = fetch_pmc_fulltext(pmcid, ncbi_api_key)
                if full_text:
                    eval_source = "Full-text (Open Access)"
                    article_content = f"[Title]\n{title}\n\n[Full-text Body]\n{full_text}"
                else:
                    eval_source = "Abstract Only"
                    article_content = f"[Title]\n{title}\n\n[Abstract]\n{abs_text}"
            elif abs_text:
                eval_source = "Abstract Only"
                article_content = f"[Title]\n{title}\n\n[Abstract]\n{abs_text}"
            else:
                eval_source = "No Data"

            if eval_source == "No Data":
                st.warning(f"**논문 제목:** {title if title else '제목 없음'}")
                st.info(f"📌 **원문 직접 링크:** [{pmid_url}]({pmid_url})")
                st.error(f"판정: **Manual Review Needed (Abstract Missing)**")
                st.caption(f"Reason: **Insufficient information:** Abstract/Full-text is unavailable. Manual full-text review is required.")
            else:
                st.success(f"**논문 제목:** {title}")
                st.caption(f"평가 기준: **{eval_source}**")
                
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-3.6-flash")
                prompt = generate_prompt(due_category, include_criteria, exclude_criteria, title, article_content)

                ans_text, err = call_gemini_with_retry(model, prompt)
                if ans_text:
                    st.success("AI 스크리닝 판정 완료!")
                    st.markdown(ans_text)
                else:
                    st.error(f"AI 통신 에러 발생: {err}")

# --------------------------------------------------
# MODE 2: CSV 파일 PMID 일괄 스크리닝
# --------------------------------------------------
elif selected_mode == "PMID 리스트 CSV 업로드":
    uploaded_file = st.file_uploader("PMID가 적힌 CSV 업로드 ('PMID' 열 필수)", type=["csv"])
    if st.button("CSV PMID 일괄 스크리닝 실행"):
        if not api_key: st.error("API Key가 설정되지 않았습니다!")
        elif not uploaded_file: st.error("CSV 파일을 업로드해 주세요!")
        else:
            try: df = pd.read_csv(uploaded_file, encoding="utf-8")
            except Exception: df = pd.read_csv(uploaded_file, encoding="cp949")

            if "PMID" not in df.columns:
                st.error("CSV 파일 안에 'PMID' 열이 있어야 합니다.")
            else:
                df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
                if "No" in df.columns: df = df.drop(columns=["No"])

                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-3.6-flash")

                titles, abstracts, results, conclusions, pubmed_urls, eval_sources = [], [], [], [], [], []
                progress_bar = st.progress(0)
                status_text = st.empty()
                total = len(df)

                for idx, row in df.iterrows():
                    pmid = str(row["PMID"]).replace(".0", "").strip()
                    title, abs_text, pmcid, status = fetch_pubmed_by_pmid(pmid, ncbi_api_key)
                    pmid_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    pubmed_urls.append(pmid_url)

                    content_for_ai = ""
                    eval_source = ""

                    if pmcid:
                        status_text.markdown(f"⏳ **[{idx+1}/{total}] PMC 원문 수집 & 정밀 분석 중...** (PMID: {pmid})")
                        full_text = fetch_pmc_fulltext(pmcid, ncbi_api_key)
                        if full_text:
                            eval_source = "Full-text (Open Access)"
                            content_for_ai = f"[Title]\n{title}\n\n[Full-text Body]\n{full_text}" 
                        else:
                            eval_source = "Abstract Only"
                            content_for_ai = f"[Title]\n{title}\n\n[Abstract]\n{abs_text}"
                    elif abs_text:
                        status_text.markdown(f"⏳ **[{idx+1}/{total}] 초록(Abstract) 분석 중...** (PMID: {pmid})")
                        eval_source = "Abstract Only"
                        content_for_ai = f"[Title]\n{title}\n\n[Abstract]\n{abs_text}"
                    else:
                        status_text.markdown(f"⏳ **[{idx+1}/{total}] 데이터 확보 불가, 예외 처리 중...** (PMID: {pmid})")
                        eval_source = "No Data"

                    if eval_source == "No Data":
                        titles.append(title if title else "조회 실패")
                        abstracts.append("No Abstract or Full-text Available")
                        results.append("Manual Review Needed")
                        conclusions.append(to_unicode_bold(f"Insufficient information: No abstract or open-access full-text available. Manual retrieval and review required."))
                        eval_sources.append(eval_source)
                    else:
                        identifier = pmid
                        if identifier in st.session_state["screened_history"]:
                            prev_info = st.session_state["screened_history"][identifier]
                            prev_mod = prev_info["sub_model"]
                            titles.append(title)
                            abstracts.append(abs_text[:150] + "..." if abs_text else "원문 확인 (요약 생략)")
                            results.append(f"Duplicated (이전중복: {prev_mod})")
                            conclusions.append(f"Duplicate literature previously screened in [{prev_mod}] step.")
                            eval_sources.append(eval_source)
                        else:
                            titles.append(title)
                            abstracts.append(abs_text[:150] + "..." if abs_text else "원문 확인 (요약 생략)")

                            prompt = generate_prompt(due_category, include_criteria, exclude_criteria, title, content_for_ai)
                            ans, err = call_gemini_with_retry(model, prompt)

                            if ans:
                                res_label = "Include (포함)" if "Include" in ans and "Exclude" not in ans.split("판정:")[1] else "Exclude (제외)"
                                results.append(res_label)
                                if "Conclusion:" in ans:
                                    raw_conclusion = ans.split("Conclusion:")[-1].strip()
                                else:
                                    raw_conclusion = ans.split("\n\n")[-1].replace("Conclusion:", "").strip()
                                conclusions.append(to_unicode_bold(raw_conclusion))
                                st.session_state["screened_history"][identifier] = {
                                    "category": due_category, "sub_model": sub_model, "result": res_label
                                }
                            else:
                                results.append("Error")
                                conclusions.append(f"AI 에러: {err}")
                            eval_sources.append(eval_source)

                    progress_bar.progress((idx + 1) / total)
                    time.sleep(0.12 if ncbi_api_key else 0.35)

                status_text.empty(); progress_bar.empty()

                df["카테고리"] = due_category
                df["세부 모델"] = sub_model
                df["논문 제목"] = titles
                df["평가 기준"] = eval_sources
                df["초록 요약"] = abstracts
                df["AI 판정"] = results
                df["Conclusion"] = conclusions
                df["PubMed Link"] = pubmed_urls

                df.insert(0, "No", range(1, len(df) + 1))
                df.index = df.index + 1
                st.session_state["tab2_result"] = df

    if st.session_state["tab2_result"] is not None:
        st.success(f"[{due_category} - {sub_model}] 일괄 스크리닝 결과")
        res_df = st.session_state["tab2_result"]
        render_result_dashboard(res_df)
        pending_df = res_df[res_df["AI 판정"].str.contains("Manual Review Needed|Full-text Screening Needed", na=False)]

        v_tab1, v_tab2 = st.tabs(["전체 스크리닝 결과 보기", f"⚠️ 수동 검토 필요 대상 모아보기 ({len(pending_df)}건)"])
        with v_tab1:
            st.dataframe(res_df, hide_index=True)
            csv_data = res_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("전체 스크리닝 결과 CSV 다운로드", data=csv_data, file_name="cer_screening_result_all.csv", mime="text/csv", use_container_width=True)
        with v_tab2:
            if len(pending_df) == 0: st.info("수동 검토 대상 논문이 없습니다.")
            else:
                st.warning("아래 목록은 PubMed 데이터상 초록이 없고 Open Access가 아니어서 수동 검토가 필요한 문헌들입니다.")
                st.dataframe(pending_df, hide_index=True)
                st.download_button("⚠️ 수동 검토 대상만 CSV 다운로드", data=pending_df.to_csv(index=False).encode("utf-8-sig"), file_name="cer_manual_review_needed.csv", mime="text/csv", use_container_width=True)

# --------------------------------------------------
# MODE 3: PubMed PICO 키워드 자동 검색 & 스크리닝
# --------------------------------------------------
elif selected_mode == "PubMed PICO 자동 검색":
    st.subheader(f"PubMed PICO 다중 키워드 입력")
    st.caption("선택하신 품목 및 세부 모델에 맞춰 P, I, C, O 키워드가 자동으로 세팅되었습니다.")

    col_pico1, col_pico2 = st.columns(2)
    with col_pico1:
        p_val = st.text_area("P (Patient / Population / Problem)", value=default_p, height=140)
        i_val = st.text_area("I (Intervention)", value=default_i, height=140)
    with col_pico2:
        c_val = st.text_area("C (Comparison)", value=default_c, height=140)
        o_val = st.text_area("O (Outcome)", value=default_o, height=140)

    st.markdown("---")
    st.subheader("문헌 검색 기간(연/월) 및 추출 개수 설정")

    col_s1, col_s2, col_e1, col_e2 = st.columns(4)
    with col_s1: start_year = st.number_input("시작 연도", min_value=1990, max_value=2026, value=2026)
    with col_s2: start_month = st.number_input("시작 월", min_value=1, max_value=12, value=1)
    with col_e1: end_year = st.number_input("종료 연도", min_value=1990, max_value=2026, value=2026)
    with col_e2: end_month = st.number_input("종료 월", min_value=1, max_value=12, value=8)

    col_opt1, col_opt2 = st.columns([1, 1])
    with col_opt1: fetch_all_toggle = st.checkbox("검색된 전체 논문 수집 (개수 제한 없음)", value=False)
    with col_opt2:
        if not fetch_all_toggle: max_limit = st.number_input("가져올 최대 논문 수", min_value=1, max_value=2000, value=20)
        else: max_limit = 0; st.info("조건에 맞는 PubMed의 전체 PMID를 가져옵니다.")

    if st.button("PICO 다중 조합 검색 및 AI 스크리닝 실행"):
        if not api_key: st.error("API Key가 설정되지 않았습니다!")
        elif not (p_val.strip() or i_val.strip() or c_val.strip() or o_val.strip()): st.error("최소한 하나 이상의 PICO 키워드를 입력해 주세요!")
        else:
            date_range_label = f"{start_year}년 {start_month:02d}월 ~ {end_year}년 {end_month:02d}월"
            with st.spinner(f"PubMed에서 [{date_range_label}] 기간의 PICO 조합 조건으로 검색 중..."):
                found_pmids, used_query = search_pubmed_pmids_pico(
                    p_text=p_val, i_text=i_val, c_text=c_val, o_text=o_val,
                    start_year=start_year, start_month=start_month, end_year=end_year, end_month=end_month,
                    fetch_all=fetch_all_toggle, max_results=max_limit, ncbi_api_key=ncbi_api_key
                )

            if not found_pmids:
                st.warning(f"[{date_range_label}] 기간 및 입력하신 PICO 조건에 부합하는 PubMed 논문이 없습니다.")
                st.info(f"생성된 조합 쿼리:\n`{used_query}`")
            else:
                st.success(f"**[{date_range_label}]** 검색 결과, 총 **{len(found_pmids)}건**의 PMID가 추출되었습니다!")
                with st.expander("자동 생성된 PubMed 조합 쿼리식 확인", expanded=True): st.code(used_query, language="sql")

                pmid_summary = ", ".join(found_pmids[:10])
                st.write(f"**추출된 PMID 목록 (상위 10개):** {pmid_summary}" + (" ... (이하 생략)" if len(found_pmids) > 10 else ""))
                st.markdown("---")

                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-3.6-flash")

                auto_df = pd.DataFrame({"PMID": found_pmids})
                titles, abstracts, results, conclusions, pubmed_urls, eval_sources = [], [], [], [], [], []
                progress_bar = st.progress(0)
                status_text = st.empty()
                total = len(auto_df)

                for idx, row in auto_df.iterrows():
                    pmid = str(row["PMID"])
                    title, abs_text, pmcid, status = fetch_pubmed_by_pmid(pmid, ncbi_api_key)
                    pmid_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    pubmed_urls.append(pmid_url)

                    content_for_ai = ""
                    eval_source = ""

                    if pmcid:
                        status_text.markdown(f"⏳ **[{idx+1}/{total}] PMC 원문 수집 & 정밀 분석 중...** (PMID: {pmid})")
                        full_text = fetch_pmc_fulltext(pmcid, ncbi_api_key)
                        if full_text:
                            eval_source = "Full-text (Open Access)"
                            content_for_ai = f"[Title]\n{title}\n\n[Full-text Body]\n{full_text}" 
                        else:
                            eval_source = "Abstract Only"
                            content_for_ai = f"[Title]\n{title}\n\n[Abstract]\n{abs_text}"
                    elif abs_text:
                        status_text.markdown(f"⏳ **[{idx+1}/{total}] 초록(Abstract) 분석 중...** (PMID: {pmid})")
                        eval_source = "Abstract Only"
                        content_for_ai = f"[Title]\n{title}\n\n[Abstract]\n{abs_text}"
                    else:
                        status_text.markdown(f"⏳ **[{idx+1}/{total}] 데이터 확보 불가, 예외 처리 중...** (PMID: {pmid})")
                        eval_source = "No Data"

                    if eval_source == "No Data":
                        titles.append(title if title else "조회 실패")
                        abstracts.append("No Abstract or Full-text Available")
                        results.append("Manual Review Needed")
                        conclusions.append(to_unicode_bold(f"Insufficient information: No abstract or open-access full-text available. Manual retrieval and review required."))
                        eval_sources.append(eval_source)
                    else:
                        identifier = pmid
                        if identifier in st.session_state["screened_history"]:
                            prev_info = st.session_state["screened_history"][identifier]
                            prev_mod = prev_info["sub_model"]
                            titles.append(title)
                            abstracts.append(abs_text[:150] + "..." if abs_text else "원문 확인 (요약 생략)")
                            results.append(f"Duplicated (이전중복: {prev_mod})")
                            conclusions.append(f"Duplicate literature previously screened in [{prev_mod}] step.")
                            eval_sources.append(eval_source)
                        else:
                            titles.append(title)
                            abstracts.append(abs_text[:150] + "..." if abs_text else "원문 확인 (요약 생략)")

                            prompt = generate_prompt(due_category, include_criteria, exclude_criteria, title, content_for_ai)
                            ans, err = call_gemini_with_retry(model, prompt)

                            if ans:
                                res_label = "Include (포함)" if "Include" in ans and "Exclude" not in ans.split("판정:")[1] else "Exclude (제외)"
                                results.append(res_label)
                                if "Conclusion:" in ans:
                                    raw_conclusion = ans.split("Conclusion:")[-1].strip()
                                else:
                                    raw_conclusion = ans.split("\n\n")[-1].replace("Conclusion:", "").strip()
                                conclusions.append(to_unicode_bold(raw_conclusion))
                                st.session_state["screened_history"][identifier] = {
                                    "category": due_category, "sub_model": sub_model, "result": res_label
                                }
                            else:
                                results.append("Error")
                                conclusions.append(f"AI 에러: {err}")
                            eval_sources.append(eval_source)

                    progress_bar.progress((idx + 1) / total)
                    time.sleep(0.12 if ncbi_api_key else 0.35)

                status_text.empty(); progress_bar.empty()

                auto_df["카테고리"] = due_category
                auto_df["세부 모델"] = sub_model
                auto_df["논문 제목"] = titles
                auto_df["평가 기준"] = eval_sources
                auto_df["초록 요약"] = abstracts
                auto_df["AI 판정"] = results
                auto_df["Conclusion"] = conclusions
                auto_df["PubMed Link"] = pubmed_urls
                auto_df.insert(0, "No", range(1, len(auto_df) + 1))
                st.session_state["tab3_result"] = auto_df

    if st.session_state["tab3_result"] is not None:
        st.success(f"[{due_category} - {sub_model}] PICO 기반 자동 스크리닝 완료 결과")
        res_df = st.session_state["tab3_result"]
        render_result_dashboard(res_df)

        pending_df = res_df[res_df["AI 판정"].str.contains("Manual Review Needed|Full-text Screening Needed", na=False)]
        v_tab1, v_tab2 = st.tabs(["전체 스크리닝 결과 보기", f"⚠️ 수동 검토 필요 대상 모아보기 ({len(pending_df)}건)"])
        with v_tab1:
            st.dataframe(res_df, hide_index=True)
            csv_data = res_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("PICO 스크리닝 전체 결과 CSV 다운로드", data=csv_data, file_name=f"pico_screening_{start_year}{start_month:02d}_{end_year}{end_month:02d}.csv", mime="text/csv", use_container_width=True)
        with v_tab2:
            if len(pending_df) == 0: st.info("수동 검토 대상 논문이 없습니다.")
            else:
                st.warning("아래 목록은 데이터 부족으로 수동 검토가 필요한 문헌들입니다.")
                st.dataframe(pending_df, hide_index=True)
                st.download_button("⚠️ 수동 검토 대상만 CSV 다운로드", data=pending_df.to_csv(index=False).encode("utf-8-sig"), file_name=f"pico_manual_review_needed_{start_year}{start_month:02d}.csv", mime="text/csv", use_container_width=True)

# --------------------------------------------------
# MODE 4: GIE RIS 파일 전용 일괄 AI 스크리닝
# --------------------------------------------------
elif selected_mode == "GIE RIS 파일 일괄 스크리닝":
    st.subheader("GIE Journal RIS 파일 업로드 스크리닝")
    st.caption("giejournal.org 접속 ➔ Advanced Search 실행 ➔ [Export Citation] ➔ RIS 파일 다운로드 ➔ 아래 업로드 창에 드래그 & 드롭")

    gie_file = st.file_uploader("GIE에서 Export한 RIS 파일(.ris)을 업로드하세요", type=["ris", "txt"])

    if st.button("GIE RIS 파일 AI 스크리닝 실행"):
        if not api_key: st.error("API Key가 설정되지 않았습니다!")
        elif not gie_file: st.error("GIE RIS 파일을 업로드해 주세요!")
        else:
            try: content = gie_file.getvalue().decode("utf-8")
            except UnicodeDecodeError: content = gie_file.getvalue().decode("cp949", errors="ignore")

            try: entries = rispy.loads(content)
            except Exception as e: st.error(f"RIS 파일 구조 파싱 실패: {str(e)}"); entries = []

            if not entries: st.error("업로드하신 RIS 파일에서 추출된 논문 정보가 없습니다.")
            else:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-3.6-flash")

                titles, abstracts, results, conclusions, doi_list, eval_sources = [], [], [], [], [], []
                progress_bar = st.progress(0)
                status_text = st.empty()
                total = len(entries)

                for idx, entry in enumerate(entries):
                    title = entry.get("title", entry.get("primary_title", "제목 없음"))
                    abstract_text = entry.get("abstract", "").strip()
                    doi = entry.get("doi", entry.get("url", "-")).strip()

                    status_text.markdown(f"⏳ **[{idx+1}/{total}] GIE 초록 AI 분석 진행 중...** ({title[:30]}...)")
                    identifier = doi.lower() if doi and doi != "-" else title.lower()

                    doi_list.append(doi)
                    
                    eval_source = "Abstract Only" if abstract_text else "No Data"

                    if eval_source == "No Data":
                        titles.append(title)
                        abstracts.append("No Abstract Available")
                        results.append("Manual Review Needed")
                        conclusions.append(to_unicode_bold(f"Insufficient information: Abstract text is missing in the GIE RIS file. Manual full-text review is required."))
                        eval_sources.append(eval_source)
                    else:
                        if identifier in st.session_state["screened_history"]:
                            prev_info = st.session_state["screened_history"][identifier]
                            prev_mod = prev_info["sub_model"]
                            titles.append(title)
                            abstracts.append(abstract_text[:150] + "...")
                            results.append(f"Duplicated (이전중복: {prev_mod})")
                            conclusions.append(f"Duplicate literature previously screened in [{prev_mod}] step.")
                            eval_sources.append(eval_source)
                        else:
                            titles.append(title)
                            abstracts.append(abstract_text[:150] + "...")

                            prompt = generate_prompt(due_category, include_criteria, exclude_criteria, title, abstract_text)
                            ans, err = call_gemini_with_retry(model, prompt)

                            if ans:
                                res_label = "Include (포함)" if "Include" in ans and "Exclude" not in ans.split("판정:")[1] else "Exclude (제외)"
                                results.append(res_label)
                                if "Conclusion:" in ans:
                                    raw_conclusion = ans.split("Conclusion:")[-1].strip()
                                else:
                                    raw_conclusion = ans.split("\n\n")[-1].replace("Conclusion:", "").strip()
                                conclusions.append(to_unicode_bold(raw_conclusion))
                                st.session_state["screened_history"][identifier] = {
                                    "category": due_category, "sub_model": sub_model, "result": res_label
                                }
                            else:
                                results.append("Error")
                                conclusions.append(f"AI 에러: {err}")
                            eval_sources.append(eval_source)

                    progress_bar.progress((idx + 1) / total)
                    time.sleep(0.3)

                status_text.empty(); progress_bar.empty()

                res_df = pd.DataFrame({
                    "No": range(1, len(entries) + 1),
                    "카테고리": due_category,
                    "세부 모델": sub_model,
                    "DOI / URL": doi_list,
                    "논문 제목": titles,
                    "평가 기준": eval_sources,
                    "초록 요약": abstracts,
                    "AI 판정": results,
                    "Conclusion": conclusions
                })
                st.session_state["tab_gie_result"] = res_df

    if st.session_state["tab_gie_result"] is not None and selected_mode == "GIE RIS 파일 일괄 스크리닝":
        st.success(f"[{due_category} - {sub_model}] GIE RIS 스크리닝 완료 결과")
        res_df = st.session_state["tab_gie_result"]
        render_result_dashboard(res_df)

        pending_df = res_df[res_df["AI 판정"].str.contains("Manual Review Needed|Full-text Screening Needed", na=False)]
        v_tab1, v_tab2 = st.tabs(["전체 스크리닝 결과 보기", f"⚠️ 수동 검토 필요 대상 모아보기 ({len(pending_df)}건)"])
        with v_tab1:
            st.dataframe(res_df, hide_index=True)
            csv_data = res_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("GIE 스크리닝 전체 결과 CSV 다운로드", data=csv_data, file_name="gie_ris_screening_result.csv", mime="text/csv", use_container_width=True)
        with v_tab2:
            if len(pending_df) == 0: st.info("수동 검토 대상 논문이 없습니다.")
            else:
                st.warning("아래 목록은 GIE RIS 파일 내 데이터 부족으로 수동 검토가 필요한 문헌들입니다.")
                st.dataframe(pending_df, hide_index=True)
                st.download_button("⚠️ 수동 검토 대상만 CSV 다운로드", data=pending_df.to_csv(index=False).encode("utf-8-sig"), file_name="gie_manual_review_needed.csv", mime="text/csv", use_container_width=True)

# --------------------------------------------------
# MODE 5: ClinicalTrials.gov 전용 API 자동 스크리닝
# --------------------------------------------------
elif selected_mode == "ClinicalTrials 자동 검색":
    st.subheader("ClinicalTrials.gov (NCT) 품목별 통합 자동 검색")
    st.caption("세부 모델 구분 없이 선택하신 품목 카테고리 전체의 임상시험 데이터를 통합 검색합니다. (API Key 불필요)")

    # 🚀 품목 카테고리별 상위 통합 키워드 자동 매핑
    if due_category == "1. Biliary Stent":
        ct_default_cond = '("Biliary obstruction" OR "Biliary stricture")'
        ct_default_intr = '("Self expandable metal stent" OR "SEMS" OR "Biliary stent")'
    elif due_category == "2. Esophageal Stent":
        ct_default_cond = '("Esophageal stricture" OR "Esophageal obstruction" OR "Tracheoesophageal fistula")'
        ct_default_intr = '("Self expandable metal stent" OR "SEMS" OR "Esophageal stent")'
    elif due_category == "3. Pyloric/Duodenal Stent":
        ct_default_cond = '("Pyloric stricture" OR "Pyloric obstruction" OR "Duodenal stricture" OR "Duodenal obstruction")'
        ct_default_intr = '("Self expandable metal stent" OR "SEMS" OR "Pyloric stent" OR "Duodenal stent")'
    elif due_category == "4. Colonic Stent":
        ct_default_cond = '("Colonic stricture" OR "Colonic obstruction")'
        ct_default_intr = '("Self expandable metal stent" OR "SEMS" OR "Colonic stent")'
    elif due_category == "5. Drainage Stent":
        ct_default_cond = '("Pancreatic pseudocyst" OR "Walled off necrosis" OR "Gallbladder" OR "Biliary tract")'
        ct_default_intr = '("Lumen apposing metal stent" OR "LAMS" OR "Drainage stent")'
    else:
        ct_default_cond = '"Biliary stricture"'
        ct_default_intr = '"Stent"'

    col_ct1, col_ct2 = st.columns(2)
    with col_ct1:
        cond_val = st.text_input("Condition/disease (질환명)", value=ct_default_cond)
    with col_ct2:
        intr_val = st.text_input("Intervention/treatment (중재시술)", value=ct_default_intr)

    st.markdown("##### Focus Your Search (필터 설정)")
    
    # 🚀 [1행] 필터 드롭다운 수평 깔끔 정돈
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        status_options = {
            "Recruiting (모집 중)": "RECRUITING",
            "Completed (완료됨)": "COMPLETED",
            "Active, not recruiting (활성, 모집안함)": "ACTIVE_NOT_RECRUITING",
            "Not yet recruiting (모집 예정)": "NOT_YET_RECRUITING",
            "Terminated (조기 종료)": "TERMINATED"
        }
        selected_statuses = st.multiselect(
            "임상 진행 상태 (Status)", 
            options=list(status_options.keys()), 
            default=[],
            placeholder="미선택 시 전체 상태(All) 검색"
        )
        api_status_filters = [status_options[k] for k in selected_statuses]
        
    with col_f2:
        type_options = {
            "Interventional (중재적 연구)": "INTERVENTIONAL",
            "Observational (관찰 연구)": "OBSERVATIONAL"
        }
        selected_types = st.multiselect(
            "연구 유형 (Study Type)", 
            options=list(type_options.keys()),
            default=[],
            placeholder="미선택 시 전체 유형(All) 검색"
        )
        api_type_filters = [type_options[k] for k in selected_types]

    # 🚀 [2행] 수집 방식 옵션 수평 배치
    col_opt1, col_opt2 = st.columns([1, 1])
    with col_opt1:
        fetch_all_ct_toggle = st.checkbox("검색된 전체 임상시험 수집 (개수 제한 없음)", value=False)
    with col_opt2:
        if not fetch_all_ct_toggle:
            max_limit = st.number_input("가져올 최대 임상시험 수", min_value=1, max_value=2000, value=20)
        else:
            max_limit = 0
            st.info("조건에 부합하는 전체 임상시험을 페이지네이션으로 수집합니다.")

    if st.button("ClinicalTrials 검색 및 AI 스크리닝 실행"):
        if not api_key: st.error("Gemini API Key가 설정되지 않았습니다!")
        elif not cond_val.strip() and not intr_val.strip(): st.error("질환명이나 중재시술 중 하나는 반드시 입력해야 합니다!")
        else:
            with st.spinner("ClinicalTrials.gov 공식 API에서 조건에 맞는 데이터를 수집 중..."):
                studies, used_query = search_clinicaltrials(
                    cond_val, intr_val, 
                    status_filters=api_status_filters, 
                    type_filters=api_type_filters, 
                    fetch_all=fetch_all_ct_toggle,
                    max_results=max_limit
                )

            if not studies:
                st.warning("검색 조건에 일치하는 임상시험을 찾을 수 없습니다.")
                st.info(f"생성된 API 요청 URL:\n{used_query}")
            else:
                st.success(f"총 **{len(studies)}건**의 진행/완료된 임상시험 데이터가 추출되었습니다!")
                with st.expander("자동 생성된 API 쿼리 URL 확인", expanded=True):
                    st.code(used_query, language="http")

                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-3.6-flash")

                titles, abstracts, results, conclusions, urls, eval_sources, statuses = [], [], [], [], [], [], []
                progress_bar = st.progress(0)
                status_text = st.empty()
                total = len(studies)

                for idx, (nct_id, title, summary, status) in enumerate(studies):
                    status_text.markdown(f"⏳ **[{idx+1}/{total}] 임상시험 브리핑(Summary) AI 분석 중...** ({nct_id})")
                    
                    nct_url = f"https://clinicaltrials.gov/study/{nct_id}"
                    identifier = nct_id.lower()
                    
                    urls.append(nct_url)
                    statuses.append(status)
                    
                    eval_source = "Abstract Only" if summary.strip() else "No Data"

                    if eval_source == "No Data":
                        titles.append(title)
                        abstracts.append("No Summary Available")
                        results.append("Manual Review Needed")
                        conclusions.append(to_unicode_bold(f"Insufficient information: No brief summary available for {nct_id}."))
                        eval_sources.append(eval_source)
                    else:
                        if identifier in st.session_state["screened_history"]:
                            prev_info = st.session_state["screened_history"][identifier]
                            prev_mod = prev_info["sub_model"]
                            titles.append(title)
                            abstracts.append(summary[:150] + "...")
                            results.append(f"Duplicated (이전중복: {prev_mod})")
                            conclusions.append(f"Duplicate literature previously screened in [{prev_mod}] step.")
                            eval_sources.append(eval_source)
                        else:
                            titles.append(title)
                            abstracts.append(summary[:150] + "...")

                            article_content = f"[NCT ID]: {nct_id}\n[Status]: {status}\n[Title]\n{title}\n\n[Brief Summary]\n{summary}"
                            prompt = generate_prompt(due_category, include_criteria, exclude_criteria, title, article_content)
                            
                            ans, err = call_gemini_with_retry(model, prompt)

                            if ans:
                                res_label = "Include (포함)" if "Include" in ans and "Exclude" not in ans.split("판정:")[1] else "Exclude (제외)"
                                results.append(res_label)
                                if "Conclusion:" in ans:
                                    raw_conclusion = ans.split("Conclusion:")[-1].strip()
                                else:
                                    raw_conclusion = ans.split("\n\n")[-1].replace("Conclusion:", "").strip()
                                conclusions.append(to_unicode_bold(raw_conclusion))
                                st.session_state["screened_history"][identifier] = {
                                    "category": due_category, "sub_model": sub_model, "result": res_label
                                }
                            else:
                                results.append("Error")
                                conclusions.append(f"AI 에러: {err}")
                            eval_sources.append(eval_source)

                    progress_bar.progress((idx + 1) / total)
                    time.sleep(0.35) 

                status_text.empty()
                progress_bar.empty()

                res_df = pd.DataFrame({
                    "No": range(1, len(studies) + 1),
                    "카테고리": due_category,
                    "세부 모델": sub_model,
                    "NCT 번호 (URL)": urls,
                    "임상 진행 상태": statuses,
                    "임상시험 제목": titles,
                    "평가 기준": eval_sources,
                    "요약 (Summary)": abstracts,
                    "AI 판정": results,
                    "Conclusion": conclusions
                })
                st.session_state["tab_ct_result"] = res_df

    if st.session_state.get("tab_ct_result") is not None and selected_mode == "ClinicalTrials 자동 검색":
        st.success(f"[{due_category} - {sub_model}] ClinicalTrials.gov 스크리닝 완료 결과")
        res_df = st.session_state["tab_ct_result"]
        render_result_dashboard(res_df)

        pending_df = res_df[res_df["AI 판정"].str.contains("Manual Review Needed|Full-text Screening Needed", na=False)]
        v_tab1, v_tab2 = st.tabs(["전체 스크리닝 결과 보기", f"⚠️ 수동 검토 필요 대상 모아보기 ({len(pending_df)}건)"])
        with v_tab1:
            st.dataframe(res_df, hide_index=True)
            csv_data = res_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("ClinicalTrials 전체 결과 CSV 다운로드", data=csv_data, file_name="clinicaltrials_screening_result.csv", mime="text/csv", use_container_width=True)
        with v_tab2:
            if len(pending_df) == 0: st.info("수동 검토 대상 임상이 없습니다.")
            else:
                st.warning("아래 목록은 Summary 데이터 부족으로 수동 검토가 필요한 임상시험들입니다.")
                st.dataframe(pending_df, hide_index=True)
                st.download_button("⚠️ 수동 검토 대상만 CSV 다운로드", data=pending_df.to_csv(index=False).encode("utf-8-sig"), file_name="clinicaltrials_manual_review_needed.csv", mime="text/csv", use_container_width=True)
