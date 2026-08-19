import io
import os
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
# 🎨 고급 커스텀 CSS (태웅메디칼 브랜딩 & UI 개선)
# --------------------------------------------------
st.markdown(
    """
<style>
    /* 1. 홈 화면 전체 세로 스크롤 허용 (창 짤림 방지) */
    html, body, [data-testid="stAppViewContainer"] {
        overflow-y: auto !important;
        height: auto !important;
    }

    /* 상단 메인 히어로 배너 디자인 */
    .hero-container {
        background: linear-gradient(135deg, #0b1a2d 0%, #1a324b 100%);
        padding: 28px 32px;
        border-radius: 16px;
        color: #ffffff;
        box-shadow: 0 10px 20px -3px rgba(11, 26, 45, 0.3);
        margin-bottom: 20px;
        border-left: 6px solid #00a8ff;
    }
    .hero-header-flex {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }
    .hero-tag {
        background: linear-gradient(90deg, #84cc16 0%, #06b6d4 100%);
        color: #ffffff;
        font-size: 12px;
        font-weight: 800;
        padding: 4px 12px;
        border-radius: 20px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        display: inline-block;
    }
    .dept-tag {
        color: #94a3b8;
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.3px;
    }
    .hero-title {
        font-size: 26px;
        font-weight: 800;
        color: #ffffff;
        margin: 4px 0px 6px 0px;
        letter-spacing: -0.5px;
    }
    .hero-subtitle {
        font-size: 14px;
        color: #cbd5e1;
        margin-bottom: 0px;
        font-weight: 400;
    }

    /* 카드 박스 내부 텍스트 스타일 */
    .card-title {
        font-size: 12px;
        font-weight: 700;
        color: #0284c7;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .card-value {
        font-size: 14px;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 4px;
        letter-spacing: -0.3px;
    }
    .card-desc {
        font-size: 12px;
        color: #64748b;
        margin-bottom: 12px;
    }

    /* 선택된 품목 반투명 하이라이트 박스 */
    .selected-category-box {
        background-color: rgba(11, 26, 45, 0.04);
        border: 1px solid rgba(11, 26, 45, 0.12);
        border-left: 5px solid #0284c7;
        border-radius: 12px;
        padding: 16px 22px;
        margin-bottom: 18px;
    }
    .selected-category-label {
        font-size: 11px;
        font-weight: 800;
        color: #0284c7;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 4px;
    }
    .selected-category-title {
        font-size: 20px;
        font-weight: 800;
        color: #0f172a;
        margin: 0;
    }

    /* 🔥 세그먼티드 컨트롤 커스텀 */
    div[data-testid="stSegmentedControl"] {
        background-color: #f1f5f9;
        padding: 6px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        display: flex !important;
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
    }
    
    div[data-testid="stSegmentedControl"] button {
        border-radius: 8px !important;
        font-weight: 1000 !important;
        font-size: 13px !important;
        border: none !important;
        padding: 8px 14px !important;
        white-space: nowrap !important;
        transition: all 0.2s ease !important;
        flex: 1 1 auto !important;
    }
    
    div[data-testid="stSegmentedControl"] button[aria-selected="true"] {
        background-color: #0b1a2d !important;
        color: #ffffff !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
    }

    /* 제품명 상자 이탈 방지 & 자동 줄바꿈 스타일 */
    .prod-item-title {
        font-weight: 700;
        font-size: 15px;
        color: #0f172a;
        white-space: normal !important;
        word-break: keep-all !important;
        margin-bottom: 6px;
    }

    .prod-item-desc {
        font-size: 13px;
        color: #475569;
        word-break: break-word !important;
        line-height: 1.5;
    }
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

# 누적 스크리닝 이력 저장용 메모리
if "screened_history" not in st.session_state:
    st.session_state["screened_history"] = {}


# 품목/세부모델 변경 시 이전 화면 결과를 리셋하는 콜백
def clear_screening_results():
    st.session_state["tab1_result"] = None
    st.session_state["tab2_result"] = None
    st.session_state["tab3_result"] = None
    st.session_state["tab_gie_result"] = None


# HOME 버튼 클릭 시 리셋
def reset_to_home():
    clear_screening_results()
    if "radio_category" in st.session_state:
        del st.session_state["radio_category"]


# 이전 스크리닝 히스토리 삭제 함수
def clear_history():
    st.session_state["screened_history"] = {}
    st.toast("이전 스크리닝 누적 기록이 초기화되었습니다.")


# --------------------------------------------------
# ⚙️ 사이드바 UI 구성 (순서: 설정 -> 품목 -> 세부모델 -> HOME)
# --------------------------------------------------
with st.sidebar:
    st.header("시스템 설정")

    default_api_key = ""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            default_api_key = str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        default_api_key = ""

    user_api_key = st.text_input(
        "Gemini API Key (미입력 시 서버 기본키 적용)", type="password"
    )
    api_key = user_api_key.strip() if user_api_key.strip() else default_api_key

    if api_key:
        st.success("API Key가 정상 등록되었습니다.")
    else:
        st.error("API Key가 없습니다. Secrets 등록 또는 키를 입력하세요.")

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
        index=None,
        key="radio_category",
        on_change=clear_screening_results,
    )

    # 세부 모델 선택
    sub_model = "전체 (All Models)"
    if due_category == "1. Biliary Stent":
        sub_model = st.selectbox(
            "세부 모델/유형을 선택하세요",
            options=[
                "Niti-S Biliary Uncovered Stent",
                "Niti-S Biliary Covered Stent",
                "ComVi Biliary Stent",
            ],
            key="sb_biliary",
            on_change=clear_screening_results,
        )
    elif due_category == "2. Esophageal Stent":
        sub_model = st.selectbox(
            "세부 모델/유형을 선택하세요",
            options=["Niti-S Esophageal Covered Stent"],
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
            key="sb_drainage",
            on_change=clear_screening_results,
        )

    # 누적 스크리닝 현황 표기 및 리셋 버튼
    st.markdown("---")
    history_cnt = len(st.session_state["screened_history"])
    st.caption(f"현재 누적 스크리닝 이력: **{history_cnt}건**")
    if st.button("이전 스크리닝 기록 초기화", help="이전 모델 스크리닝 이력을 비우고 다시 시작합니다."):
        clear_history()

    # HOME 버튼
    st.markdown("---")
    st.button(
        "HOME",
        type="secondary",
        use_container_width=True,
        help="홈 대시보드로 이동",
        on_click=reset_to_home,
    )

# --------------------------------------------------
# 🏠 품목 선택이 안 되었을 때 (홈 대시보드 화면)
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
                <div class="card-desc">아래 상자를 클릭하여 세부 라인업 및 제품 카탈로그 정보를 확인하세요.</div>
                """,
                unsafe_allow_html=True,
            )

            # 👈 [100% 원복 & 튕김 차단] 하위 탭 구조로 모든 원본 제품 데이터 완전 보존
            with st.expander("View Detailed Product Catalog"):
                c_tab1, c_tab2, c_tab3, c_tab4, c_tab5 = st.tabs([
                    "Biliary", "Esophageal", "Pyloric/Duodenal", "Colonic", "Drainage"
                ])

                # 1. Biliary Stent (전체 원본 리스트)
                with c_tab1:
                    st.markdown("#### **Niti-S & ComVi Biliary Stent**")
                    b_sub1, b_sub2, b_sub3 = st.tabs(["Uncovered Stent", "Covered Stent", "ComVi Stent"])
                    
                    with b_sub1:
                        biliary_uncovered_models = [
                            ("S-Type", "biliary_uncovered_s.png", "Niti-S Biliary Uncovered Stent [S-Type] is indicated for use in malignant strictures."),
                            ("D-Type", "biliary_uncovered_d.png", "Niti-S Biliary Uncovered Stent [D-Type] is indicated for use in malignant strictures."),
                            ("M-Type", "biliary_uncovered_m.png", "Niti-S Biliary Uncovered Stent [M-Type] is indicated for use in malignant strictures."),
                            ("LCD-Type", "biliary_uncovered_lcd.png", "Niti-S Biliary Uncovered Stent [LCD-Type] is indicated for use in malignant strictures."),
                        ]
                        with st.container(border=True):
                            for m_name, m_img, m_desc in biliary_uncovered_models:
                                c1, c2 = st.columns([1, 2.2])
                                with c1:
                                    if os.path.exists(m_img):
                                        st.image(m_img, use_container_width=True)
                                    else:
                                        st.caption(f"📷 {m_img} 이미지 등록 필요")
                                with c2:
                                    st.markdown(
                                        f'<div class="prod-item-title">Niti-S Biliary Uncovered Stent [{m_name}]</div>'
                                        f'<div class="prod-item-desc">• {m_desc}</div>',
                                        unsafe_allow_html=True,
                                    )
                                st.divider()

                    with b_sub2:
                        biliary_covered_models = [
                            ("Full Covered-Type", "biliary_covered_full.png", "Niti-S Biliary Covered Stent [Full Covered-Type] is indicated for use in malignant and/or benign strictures."),
                            ("Both Bare-Type", "biliary_covered_bothbare.png", "Niti-S Biliary Covered Stent [Both Bare-Type] is indicated for use in malignant strictures."),
                            ("Giobor", "biliary_covered_giobor.png", "Niti-S Biliary Covered Stent [Giobor] is indicated for use in malignant strictures."),
                            ("Flare-Type", "biliary_covered_flare.png", "Niti-S Biliary Covered Stent [Flare-Type] is indicated for use in malignant and/or benign strictures."),
                            ("Kaffes", "biliary_covered_kaffes.png", "Niti-S Biliary Covered Stent [Kaffes] is indicated for use in malignant and/or benign strictures."),
                            ("Bumpy", "biliary_covered_bumpy.png", "Niti-S Biliary Covered Stent [Bumpy] is indicated for use in malignant and/or benign biliary strictures and benign pancreatic ductal strictures."),
                        ]
                        with st.container(border=True):
                            for m_name, m_img, m_desc in biliary_covered_models:
                                c1, c2 = st.columns([1, 2.2])
                                with c1:
                                    if os.path.exists(m_img):
                                        st.image(m_img, use_container_width=True)
                                    else:
                                        st.caption(f"📷 {m_img} 이미지 등록 필요")
                                with c2:
                                    st.markdown(
                                        f'<div class="prod-item-title">Niti-S Biliary Covered Stent [{m_name}]</div>'
                                        f'<div class="prod-item-desc">• {m_desc}</div>',
                                        unsafe_allow_html=True,
                                    )
                                st.divider()

                    with b_sub3:
                        biliary_comvi_models = [
                            ("Full Covered-Type", "biliary_comvi_full.png", "ComVi Biliary Stent [Full Covered-Type] is indicated for use in malignant strictures."),
                            ("Both Bare-Type", "biliary_comvi_bothbare.png", "ComVi Biliary Stent [Both Bare-Type] is indicated for use in malignant strictures."),
                            ("End Bare-Type", "biliary_comvi_endbare.png", "ComVi Biliary Stent [End Bare-Type] is indicated for use in malignant strictures."),
                        ]
                        with st.container(border=True):
                            for m_name, m_img, m_desc in biliary_comvi_models:
                                c1, c2 = st.columns([1, 2.2])
                                with c1:
                                    if os.path.exists(m_img):
                                        st.image(m_img, use_container_width=True)
                                    else:
                                        st.caption(f"📷 {m_img} 이미지 등록 필요")
                                with c2:
                                    st.markdown(
                                        f'<div class="prod-item-title">ComVi Biliary Stent [{m_name}]</div>'
                                        f'<div class="prod-item-desc">• {m_desc}</div>',
                                        unsafe_allow_html=True,
                                    )
                                st.divider()

                # 2. Esophageal Stent (전체 원본 리스트)
                with c_tab2:
                    st.markdown("#### **Niti-S Esophageal Stent**")
                    e_sub1 = st.tabs(["Covered Stent"])[0]
                    with e_sub1:
                        esophageal_covered_models = [
                            ("Full Covered-Type", "esophageal_covered_full.png", "Niti-S Esophageal Covered Stent [Full Covered-Type] is indicated for use in malignant and/or refractory benign stricture and tracheoesophageal fistula."),
                            ("Cervical", "esophageal_covered_cervical.png", "Niti-S Esophageal Covered Stent [Cervical] is indicated for use in malignant strictures."),
                            ("Both Bare-Type", "esophageal_covered_bothbare.png", "Niti-S Esophageal Covered Stent [Both Bare-Type] is indicated for use in malignant strictures."),
                            ("Conio", "esophageal_covered_conio.png", "Niti-S Esophageal Covered Stent [Conio] is indicated for use in malignant and/or benign stricture and tracheoesophageal fistula."),
                            ("Anti Reflux-Type", "esophageal_covered_antireflux.png", "Niti-S Esophageal Covered Stent [Anti Reflux-Type] is indicated for use in malignant and/or benign stricture and tracheoesophageal fistula."),
                            ("Double Anti Reflux-Type", "esophageal_covered_doubleantireflux.png", "Niti-S Esophageal Covered Stent [Double Anti-Reflux-Type] is indicated for use in malignant strictures."),
                            ("Double-Type", "esophageal_covered_double.png", "Niti-S Esophageal Covered Stent [Double-Type] is indicated for use in malignant strictures."),
                            ("Beta-2", "esophageal_covered_beta2.png", "Niti-S Esophageal Covered Stent [Beta-2] is indicated for use in malignant and/or benign stricture and tracheoesophageal fistula."),
                        ]
                        with st.container(border=True):
                            for m_name, m_img, m_desc in esophageal_covered_models:
                                c1, c2 = st.columns([1, 2.2])
                                with c1:
                                    if os.path.exists(m_img):
                                        st.image(m_img, use_container_width=True)
                                    else:
                                        st.caption(f"📷 {m_img} 이미지 등록 필요")
                                with c2:
                                    st.markdown(
                                        f'<div class="prod-item-title">Niti-S Esophageal Covered Stent [{m_name}]</div>'
                                        f'<div class="prod-item-desc">• {m_desc}</div>',
                                        unsafe_allow_html=True,
                                    )
                                st.divider()

                # 3. Pyloric/Duodenal Stent (전체 원본 리스트)
                with c_tab3:
                    st.markdown("#### **Niti-S & ComVi Pyloric/Duodenal Stent**")
                    p_sub1, p_sub2, p_sub3 = st.tabs(["Uncovered Stent", "Covered Stent", "ComVi Stent"])
                    
                    with p_sub1:
                        pyloric_uncovered_models = [
                            ("D-Type", "pyloric_uncovered_d.png", "Niti-S Pyloric/Duodenal Uncovered Stent [D-Type] is indicated for use in intrinsic and/or extrinsic malignant stricture."),
                        ]
                        with st.container(border=True):
                            for m_name, m_img, m_desc in pyloric_uncovered_models:
                                c1, c2 = st.columns([1, 2.2])
                                with c1:
                                    if os.path.exists(m_img):
                                        st.image(m_img, use_container_width=True)
                                    else:
                                        st.caption(f"📷 {m_img} 이미지 등록 필요")
                                with c2:
                                    st.markdown(
                                        f'<div class="prod-item-title">Niti-S Pyloric/Duodenal Uncovered Stent [{m_name}]</div>'
                                        f'<div class="prod-item-desc">• {m_desc}</div>',
                                        unsafe_allow_html=True,
                                    )
                                st.divider()

                    with p_sub2:
                        pyloric_covered_models = [
                            ("Full Covered-Type", "pyloric_covered_full.png", "Niti-S Pyloric/Duodenal Covered Stent [Full Covered-Type] is indicated for use in intrinsic and/or extrinsic malignant and/or benign stricture."),
                            ("Both Bare-Type", "pyloric_covered_bothbare.png", "Niti-S Pyloric/Duodenal Covered Stent [Both Bare-Type] is indicated for use in intrinsic and/or extrinsic malignant stricture."),
                            ("End Bare-Type", "pyloric_covered_endbare.png", "Niti-S Pyloric/Duodenal Covered Stent [End Bare-Type] is indicated for use in intrinsic and/or extrinsic malignant stricture."),
                        ]
                        with st.container(border=True):
                            for m_name, m_img, m_desc in pyloric_covered_models:
                                c1, c2 = st.columns([1, 2.2])
                                with c1:
                                    if os.path.exists(m_img):
                                        st.image(m_img, use_container_width=True)
                                    else:
                                        st.caption(f"📷 {m_img} 이미지 등록 필요")
                                with c2:
                                    st.markdown(
                                        f'<div class="prod-item-title">Niti-S Pyloric/Duodenal Covered Stent [{m_name}]</div>'
                                        f'<div class="prod-item-desc">• {m_desc}</div>',
                                        unsafe_allow_html=True,
                                    )
                                st.divider()

                    with p_sub3:
                        pyloric_comvi_models = [
                            ("Flare-Type", "pyloric_comvi_flare.png", "ComVi Pyloric/Duodenal Stent [Flare-Type] is indicated for use in intrinsic and/or extrinsic malignant stricture."),
                            ("Both Bare-Type", "pyloric_comvi_bothbare.png", "ComVi Pyloric/Duodenal Stent [Both Bare-Type] is indicated for use in intrinsic and/or extrinsic malignant stricture."),
                        ]
                        with st.container(border=True):
                            for m_name, m_img, m_desc in pyloric_comvi_models:
                                c1, c2 = st.columns([1, 2.2])
                                with c1:
                                    if os.path.exists(m_img):
                                        st.image(m_img, use_container_width=True)
                                    else:
                                        st.caption(f"📷 {m_img} 이미지 등록 필요")
                                with c2:
                                    st.markdown(
                                        f'<div class="prod-item-title">ComVi Pyloric/Duodenal Stent [{m_name}]</div>'
                                        f'<div class="prod-item-desc">• {m_desc}</div>',
                                        unsafe_allow_html=True,
                                    )
                                st.divider()

                # 4. Colonic Stent (전체 원본 리스트)
                with c_tab4:
                    st.markdown("#### **Niti-S & ComVi Enteral Colonic Stent**")
                    col_sub1, col_sub2, col_sub3 = st.tabs(["Uncovered Stent", "Covered Stent", "ComVi Stent"])
                    
                    with col_sub1:
                        colonic_uncovered_models = [
                            ("S-Type", "colonic_uncovered_s.png", "Niti-S Enteral Colonic Uncovered Stent [S-Type] is indicated for use in colon stricture caused by intrinsic and/or extrinsic malignant stricture."),
                            ("D-Type", "colonic_uncovered_d.png", "Niti-S Enteral Colonic Uncovered Stent [D-Type] is indicated for use in colon stricture caused by intrinsic and/or extrinsic malignant stricture."),
                        ]
                        with st.container(border=True):
                            for m_name, m_img, m_desc in colonic_uncovered_models:
                                c1, c2 = st.columns([1, 2.2])
                                with c1:
                                    if os.path.exists(m_img):
                                        st.image(m_img, use_container_width=True)
                                    else:
                                        st.caption(f"📷 {m_img} 이미지 등록 필요")
                                with c2:
                                    st.markdown(
                                        f'<div class="prod-item-title">Niti-S Enteral Colonic Uncovered Stent [{m_name}]</div>'
                                        f'<div class="prod-item-desc">• {m_desc}</div>',
                                        unsafe_allow_html=True,
                                    )
                                st.divider()

                    with col_sub2:
                        colonic_covered_models = [
                            ("Full Covered-Type", "colonic_covered_full.png", "Niti-S Enteral Colonic Covered Stent [Full Covered-Type] is indicated for use in colon stricture caused by intrinsic and/or extrinsic malignant and/or benign stricture."),
                            ("Both Bare-Type", "colonic_covered_bothbare.png", "Niti-S Enteral Colonic Covered Stent [Both Bare-Type] is indicated for use in colon stricture caused by intrinsic and/or extrinsic malignant stricture."),
                            ("End Bare-Type", "colonic_covered_endbare.png", "Niti-S Enteral Colonic Covered Stent [End Bare-Type] is indicated for use in colon stricture caused by intrinsic and/or extrinsic malignant stricture."),
                        ]
                        with st.container(border=True):
                            for m_name, m_img, m_desc in colonic_covered_models:
                                c1, c2 = st.columns([1, 2.2])
                                with c1:
                                    if os.path.exists(m_img):
                                        st.image(m_img, use_container_width=True)
                                    else:
                                        st.caption(f"📷 {m_img} 이미지 등록 필요")
                                with c2:
                                    st.markdown(
                                        f'<div class="prod-item-title">Niti-S Enteral Colonic Covered Stent [{m_name}]</div>'
                                        f'<div class="prod-item-desc">• {m_desc}</div>',
                                        unsafe_allow_html=True,
                                    )
                                st.divider()

                    with col_sub3:
                        colonic_comvi_models = [
                            ("Both Bare-Type", "colonic_comvi_bothbare.png", "ComVi Enteral Colonic Stent [Both Bare-Type] is indicated for use in colon stricture caused by intrinsic and/or extrinsic malignant stricture."),
                        ]
                        with st.container(border=True):
                            for m_name, m_img, m_desc in colonic_comvi_models:
                                c1, c2 = st.columns([1, 2.2])
                                with c1:
                                    if os.path.exists(m_img):
                                        st.image(m_img, use_container_width=True)
                                    else:
                                        st.caption(f"📷 {m_img} 이미지 등록 필요")
                                with c2:
                                    st.markdown(
                                        f'<div class="prod-item-title">ComVi Enteral Colonic Stent [{m_name}]</div>'
                                        f'<div class="prod-item-desc">• {m_desc}</div>',
                                        unsafe_allow_html=True,
                                    )
                                st.divider()

                # 5. Drainage Stent (전체 원본 리스트)
                with c_tab5:
                    st.markdown("#### **Niti-S Drainage Stent**")
                    d_sub1, d_sub2, d_sub3 = st.tabs(["SPAXUS Stent", "Hot SPAXUS Stent", "Nagi Stent"])
                    
                    with d_sub1:
                        spaxus_models = [
                            ("SPAXUS", "drainage_spaxus.png", "Niti-S SPAXUS™ Stent is indicated for transgastric or transduodenal drainage of a pancreatic pseudocyst or a walled off necrosis or a gallbladder or the biliary tract."),
                        ]
                        with st.container(border=True):
                            for m_name, m_img, m_desc in spaxus_models:
                                c1, c2 = st.columns([1, 2.2])
                                with c1:
                                    if os.path.exists(m_img):
                                        st.image(m_img, use_container_width=True)
                                    else:
                                        st.caption(f"📷 {m_img} 이미지 등록 필요")
                                with c2:
                                    st.markdown(
                                        f'<div class="prod-item-title">Niti-S SPAXUS Stent</div>'
                                        f'<div class="prod-item-desc">• {m_desc}</div>',
                                        unsafe_allow_html=True,
                                    )
                                st.divider()

                    with d_sub2:
                        hot_spaxus_models = [
                            ("Hot SPAXUS", "drainage_hot_spaxus.png", "Niti-S Hot SPAXUS™ Stent is indicated for transgastric or transduodenal drainage of a pancreatic pseudocyst or a walled off necrosis or a gallbladder or the biliary tract."),
                        ]
                        with st.container(border=True):
                            for m_name, m_img, m_desc in hot_spaxus_models:
                                c1, c2 = st.columns([1, 2.2])
                                with c1:
                                    if os.path.exists(m_img):
                                        st.image(m_img, use_container_width=True)
                                    else:
                                        st.caption(f"📷 {m_img} 이미지 등록 필요")
                                with c2:
                                    st.markdown(
                                        f'<div class="prod-item-title">Niti-S Hot SPAXUS Stent</div>'
                                        f'<div class="prod-item-desc">• {m_desc}</div>',
                                        unsafe_allow_html=True,
                                    )
                                st.divider()

                    with d_sub3:
                        nagi_models = [
                            ("Nagi", "drainage_nagi.png", "Niti-S Nagi™ Stent is indicated for drainage of a pancreatic pseudocyst through a transgastric or transduodenal approach."),
                        ]
                        with st.container(border=True):
                            for m_name, m_img, m_desc in nagi_models:
                                c1, c2 = st.columns([1, 2.2])
                                with c1:
                                    if os.path.exists(m_img):
                                        st.image(m_img, use_container_width=True)
                                    else:
                                        st.caption(f"📷 {m_img} 이미지 등록 필요")
                                with c2:
                                    st.markdown(
                                        f'<div class="prod-item-title">Niti-S Nagi Stent</div>'
                                        f'<div class="prod-item-desc">• {m_desc}</div>',
                                        unsafe_allow_html=True,
                                    )
                                st.divider()

    with col_ov2:
        with st.container(border=True):
            st.markdown(
                """
                <div class="card-title">AI PIPELINE</div>
                <div class="card-value">Gemini 3.6 Flash + PubMed & GIE Engine</div>
                <div class="card-desc">AI 기반 문헌 스크리닝</div>
                <br>
                """,
                unsafe_allow_html=True,
            )

    with col_ov3:
        with st.container(border=True):
            st.markdown(
                """
                <div class="card-title">REGULATORY GOAL</div>
                <div class="card-value" style="white-space: nowrap; font-size: 14px;">Standardization and Automation of Literature Review</div>
                <div class="card-desc">일관성 및 추적성을 확보한 스크리닝 기록</div>
                <br>
                """,
                unsafe_allow_html=True,
            )

    st.stop()

# --------------------------------------------------
# 🔬 품목 선택 시 세부 모델별 프롬프트 및 PICO 키워드 자동 세팅
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
3. Irrelevant articles: Articles not related to biliary/pancreatic luminal stenting or stricture management
4. Non-study publications: Editorials, letters, comments (단, Review 및 Case report는 제외하지 않음)"""

    if sub_model == "Niti-S Biliary Uncovered Stent":
        default_p = "Biliary obstruction\nBiliary stricture\nMalignant biliary stricture\nMalignant biliary obstruction"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nUncovered stent"
        default_c = "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nUncovered stent\nEvolution\nWallFlex\nEGIS\nBonastent\nHanarostent"
        default_o = "Stent patency\nDecreased bilirubin"
    elif sub_model == "Niti-S Biliary Covered Stent":
        default_p = "Biliary obstruction\nBiliary stricture\nBenign biliary stricture\nBenign biliary obstruction\nMalignant biliary stricture\nMalignant biliary obstruction\nBenign pancreatic duct stricture"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nCovered stent"
        default_c = "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nEvolution\nWallFlex\nEGIS\nBonastent\nHanarostent"
        default_o = "Stent patency\nDecreased bilirubin\nRemoval"
    elif sub_model == "ComVi Biliary Stent":
        default_p = "Biliary obstruction\nBiliary stricture\nMalignant biliary stricture\nMalignant biliary obstruction"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nComVi\nCovered stent"
        default_c = "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nEvolution\nWallFlex\nEGIS\nBonastent\nHanarostent"
        default_o = "Stent patency\nDecreased bilirubin"
    else:
        default_p = "Biliary obstruction\nBiliary stricture\nMalignant biliary stricture\nMalignant biliary obstruction\nBenign biliary obstruction\nBenign biliary stricture\nBenign pancreatic duct stricture"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nComVi\nUncovered stent\nCovered stent"
        default_c = "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nUncovered stent\nEvolution\nWallFlex\nEGIS\nBonastent\nHanarostent"
        default_o = "Stent patency\nDecreased bilirubin\nRemoval"

elif due_category == "2. Esophageal Stent":
    include_criteria = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Esophageal stricture/obstruction (Malignant or Benign), Refractory benign esophageal stricture, Tracheoesophageal fistula (TEF / TE fistula)
5. Intervention: Esophageal SEMS, Covered type. Specific Taewoong Medical models: Niti-S Esophageal (Full covered, Cervical, Both bare type, Conio, Anti reflux, Double anti reflux, Double type, Beta-2)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (WallFlex, Ultraflex, Evolution, Hanarostent, Aixstent, EGIS, Bonastent, Micro-Tech)
7. Outcomes: Stent patency, Dysphagia improvement, Fistula closure, Removal (in benign strictures)"""
    exclude_criteria = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-esophageal target areas only (e.g., pure biliary, colonic, duodenal, vascular)
3. Irrelevant articles: Articles not related to esophageal stenting, stricture dilation, or TE fistula management
4. Non-study publications: Editorials, letters, comments (단, Review 및 Case report는 제외하지 않음)"""

    default_p = "Esophageal stricture\nEsophageal obstruction\nMalignant esophageal stricture\nMalignant esophageal obstruction\nBenign esophageal stricture\nRefractory benign esophageal stricture\nBenign esophgeal obstruction\nTracheoesophageal fistula"
    default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nCovered stent"
    default_c = "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nWallFlex\nUltraflex\nEvolution\nHanarostent\nAixstent\nEGIS\nBonastent\nMicro-tech"
    default_o = "Stent patency\nDysphagia improvement\nFistula closure\nRemoval"

elif due_category == "3. Pyloric/Duodenal Stent":
    include_criteria = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Pyloric/Duodenal stricture or obstruction, Gastric Outlet Obstruction (GOO), Malignant or Benign
5. Intervention: Pyloric/Duodenal SEMS, Uncovered or Covered type. Specific Taewoong Medical models: Niti-S Pyloric/Duodenal (D-Type, Full Covered, Both Bare, End Bare), ComVi Pyloric/Duodenal (Flare-Type, Both Bare)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (WallFlex, WallFlex Soft, Hanarostent, Evolution, EGIS, Bonastent)
7. Outcomes: Stent patency, Obstruction relief/resolution/improvement, GOOSS score / Oral intake, Technical/Clinical success, Complications, Stent removal (for benign strictures)"""
    exclude_criteria = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-pyloric/duodenal target areas only (e.g., pure biliary, esophageal, colonic, or vascular stents without duodenal/gastric outlet involvement)
3. Irrelevant articles: Articles not related to pyloric/duodenal stenting or GOO management
4. Non-study publications: Editorials, letters, comments (단, Review 및 Case report는 제외하지 않음)"""

    if sub_model == "Niti-S Pyloric/Duodenal Uncovered Stent":
        default_p = "Pyloric stricture\nPyloric obstruction\nDuodenal stricture\nDuodenal obstruction\nGastric outlet obstruction\nMalignant pyloric stricture\nMalignant pyloric obstruction\nMalignant duodenal stricture\nMalignant duodenal obstruction"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nUncovered stent"
        default_c = "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nUncovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nEvolution\nEGIS\nBonastent"
        default_o = "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement"
    elif sub_model == "Niti-S Pyloric/Duodenal Covered Stent":
        default_p = "Pyloric stricture\nPyloric obstruction\nDuodenal stricture\nDuodenal obstruction\nGastric outlet obstruction\nMalignant pyloric stricture\nMalignant pyloric obstruction\nMalignant duodenal stricture\nMalignant duodenal obstruction\nBenign pyloric stricture\nBenign pyloric obstruction\nBenign duodenal stricture\nBenign duodenal obstruction"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nCovered stent"
        default_c = "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nEvolution\nEGIS\nBonastent"
        default_o = "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement\nRemoval"
    elif sub_model == "ComVi Pyloric/Duodenal Stent":
        default_p = "Pyloric stricture\nPyloric obstruction\nDuodenal stricture\nDuodenal obstruction\nGastric outlet obstruction\nMalignant pyloric stricture\nMalignant pyloric obstruction\nMalignant duodenal stricture\nMalignant duodenal obstruction"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nComVi\nCovered stent"
        default_c = "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nEvolution\nEGIS\nBonastent"
        default_o = "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement"
    else:
        default_p = "Pyloric stricture\nPyloric obstruction\nDuodenal stricture\nDuodenal obstruction\nGastric outlet obstruction\nMalignant pyloric stricture\nMalignant pyloric obstruction\nMalignant duodenal stricture\nMalignant duodenal obstruction\nBenign pyloric stricture\nBenign pyloric obstruction\nBenign duodenal stricture\nBenign duodenal obstruction"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nComVi\nCovered stent\nUncovered stent"
        default_c = "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nUncovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nEvolution\nEGIS\nBonastent"
        default_o = "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement\nRemoval"

elif due_category == "4. Colonic Stent":
    include_criteria = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Colonic/Colorectal stricture or obstruction (Malignant or Benign)
5. Intervention: Colonic SEMS, Uncovered or Covered type. Specific Taewoong Medical models: Niti-S Enteral Colonic (S-Type, D-Type, Full Covered, Both Bare, End Bare), ComVi Enteral Colonic (Both Bare-Type)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (WallFlex, WallFlex Soft, Hanarostent, Micro-Tech, Bonastent)
7. Outcomes: Stent patency, Obstruction relief/resolution/improvement, Technical/Clinical success, Complications, Stent removal (for benign strictures)"""
    exclude_criteria = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-colonic target areas only (e.g., pure biliary, esophageal, pyloric/duodenal, or vascular stents without colonic/colorectal involvement)
3. Irrelevant articles: Articles not related to colonic stenting or colorectal obstruction management
4. Non-study publications: Editorials, letters, comments (단, Review 및 Case report는 제외하지 않음)"""

    if sub_model == "Niti-S Enteral Colonic Uncovered Stent":
        default_p = "Colonic stricture\nColonic obstruction\nColorectal stricture\nColorectal obstruction\nMalignant colonic stricture\nMalignant colonic obstruction\nMalignant colorectal stricture\nMalignant colorectal obstruction"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nUncovered stent"
        default_c = "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nUncovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nMicro-Tech\nBonastent"
        default_o = "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement"
    elif sub_model == "Niti-S Enteral Colonic Covered Stent":
        default_p = "Colonic stricture\nColonic obstruction\nColorectal stricture\nColorectal obstruction\nMalignant colonic stricture\nMalignant colonic obstruction\nMalignant colorectal stricture\nMalignant colorectal obstruction\nBenign colonic stricture\nBenign colonic obstruction\nBenign colorectal stricture\nBenign colorectal obstruction"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nCovered stent"
        default_c = "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nMicro-Tech\nBonastent"
        default_o = "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement\nRemoval"
    elif sub_model == "ComVi Enteral Colonic Stent":
        default_p = "Colonic stricture\nColonic obstruction\nColorectal stricture\nColorectal obstruction\nMalignant colonic stricture\nMalignant colonic obstruction\nMalignant colorectal stricture\nMalignant colorectal obstruction"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nComVi\nCovered stent"
        default_c = "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nMicro-Tech\nBonastent"
        default_o = "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement"
    else:
        default_p = "Colonic stricture\nColonic obstruction\nColorectal stricture\nColorectal obstruction\nMalignant colonic stricture\nMalignant colonic obstruction\nMalignant colorectal stricture\nMalignant colorectal obstruction\nBenign colonic stricture\nBenign colonic obstruction\nBenign colorectal stricture\nBenign colorectal obstruction"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nComVi\nUncovered stent\nCovered stent"
        default_c = "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nUncovered stent\nWallFlex\nWallFlex Soft\nHanarostent\nMicro-tech\nBonastent"
        default_o = "Stent patency\nObstruction relief\nObstruction resolution\nObstruction improvement\nRemoval"

elif due_category == "5. Drainage Stent":
    include_criteria = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Pancreatic pseudocyst, Walled-off necrosis (WON) / Pancreatic necrosis, Gallbladder drainage (Cholecystitis) / Biliary tract drainage, Transgastric or transduodenal drainage indications
5. Intervention: Lumen-apposing metal stents (LAMS) or EUS-guided drainage stents. Specific Taewoong Medical models: Niti-S Nagi, Niti-S SPAXUS, Niti-S Hot SPAXUS (Electrocautery Delivery System)
6. Comparators: Surgery, Percutaneous drainage, Plastic double-pigtail stents, or competitor LAMS (e.g., AXIOS / Hot AXIOS)
7. Outcomes: Technical/Clinical success rate, Drainage efficacy, Resolution of pseudocyst/necrosis, Complications (Bleeding, Stent migration, Perforation, Occlusion), Removal rate"""
    exclude_criteria = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication/Irrelevant: Non-drainage target indications or vascular/intraluminal stenting without transluminal/EUS drainage purpose
3. Non-study publications: Editorials, letters, comments (단, Review 및 Case report는 제외하지 않음)"""

    if sub_model == "Niti-S SPAXUS Stent":
        default_p = "Pancreatic pseudocyst\nWalled off necrosis\nGallbladder\nBiliary tract"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nLumen apposing metal stent\nLAMS\nEUS gallbladder drainage\nEUS choledochoduodenostomy\nTaewoong\nNiti-S\nSPAXUS"
        default_c = "Surgery\nPercutaneous drainage\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nLumen apposing metal stent\nLAMS\nAXIOS\nHot AXIOS"
        default_o = "Pancreatic pseudocyst drainage\nWalled off necrosis drainage\nGallbladder drainage\nBiliary tract drainage"
    elif sub_model == "Niti-S Hot SPAXUS Stent":
        default_p = "Pancreatic pseudocyst\nWalled off necrosis\nGallbladder\nBiliary tract"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nLumen apposing metal stent\nLAMS\nEUS gallbladder\nEUS choledochoduodenostomy\nElectrocautery delivery system\nHot delivery\nTaewoong\nNiti-S\nHot SPAXUS"
        default_c = "Surgery\nPercutaneous drainage\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nLumen apposing metal stent\nLAMS\nAXIOS\nHot AXIOS "
        default_o = "Pancreatic pseudocyst drainage\nWalled off necrosis drainage\nGallbladder drainage\nBiliary tract drainage"
    elif sub_model == "Niti-S Nagi Stent":
        default_p = "Pancreatic pseudocyst"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nLumen apposing metal stent\nLAMS\nBiflanged metal stent\nBFMS\nTaewoong\nNiti-S\nNagi"
        default_c = "Surgery\nPercutaneous drainage\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nLumen apposing metal stent\nLAMS\nBiflanged metal stent\nBFMS\nAXIOS\nHot AXIOS"
        default_o = "Pancreatic pseudocyst drainage"
    else:
        default_p = "Pancreatic pseudocyst\nWalled off necrosis\nGallbladder\nBiliary tract"
        default_i = "Self-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nTaewoong\nNiti-S\nComVi\nUncovered stent\nCovered stent"
        default_c = "Surgery\nPercutaneous drainage\nSelf-expandable metallic stent\nSelf-expandable metal stent\nSEMS\nLumen apposing metal stent\nLAMS\nBiflanged metal stent\nBFMS\nAXIOS\nHot AXIOS"
        default_o = "Pancreatic pseudocyst drainage\nWalled off necrosis drainage\nGallbladder drainage\nBiliary tract drainage"

else:
    include_criteria = "Include All Relevant Clinical Papers"
    exclude_criteria = "Exclude Non-Clinical/Irrelevant Papers"
    default_p = "Obstructive Jaundice\nBiliary Stricture"
    default_i = "Biliary Stent\nSEMS"
    default_c = "Surgery\nPlastic stent"
    default_o = "Technical success\nClinical success"


# --------------------------------------------------
# PubMed API 기능 및 XML 파싱 함수
# --------------------------------------------------

def parse_pico_input(text):
    if not text or not text.strip():
        return ""

    raw_keywords = text.replace(",", "\n").split("\n")
    keywords = [kw.strip() for kw in raw_keywords if kw.strip()]

    if not keywords:
        return ""

    formatted = []
    for kw in keywords:
        if '"' in kw or "[" in kw:
            formatted.append(kw)
        else:
            formatted.append(f"({kw})")

    if len(formatted) == 1:
        return formatted[0]
    else:
        return f"({' OR '.join(formatted)})"


def search_pubmed_pmids_pico(
    p_text,
    i_text,
    c_text="",
    o_text="",
    start_year=2026,
    start_month=1,
    end_year=2026,
    end_month=12,
    fetch_all=False,
    max_results=20,
):
    query_parts = []

    p_query = parse_pico_input(p_text)
    i_query = parse_pico_input(i_text)
    c_query = parse_pico_input(c_text)
    o_query = parse_pico_input(o_text)

    if p_query:
        query_parts.append(p_query)
    if i_query:
        query_parts.append(i_query)
    if c_query:
        query_parts.append(c_query)
    if o_query:
        query_parts.append(o_query)

    full_query = " AND ".join(query_parts)
    if not full_query:
        return [], ""

    min_date_str = f"{start_year}/{int(start_month):02d}/01"
    max_date_str = f"{end_year}/{int(end_month):02d}/31"

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

    params_count = {
        "db": "pubmed",
        "term": full_query,
        "retmode": "json",
        "retmax": 0,
        "datetype": "pdat",
        "mindate": min_date_str,
        "maxdate": max_date_str,
    }

    try:
        res_count = requests.get(url, params=params_count, timeout=10).json()
        total_found = int(res_count.get("esearchresult", {}).get("count", 0))

        actual_retmax = total_found if fetch_all else min(max_results, total_found)
        if actual_retmax == 0:
            return [], full_query

        params_fetch = {
            "db": "pubmed",
            "term": full_query,
            "retmode": "json",
            "retmax": actual_retmax,
            "datetype": "pdat",
            "mindate": min_date_str,
            "maxdate": max_date_str,
        }

        response = requests.get(url, params=params_fetch, timeout=10)
        data = response.json()
        pmid_list = data.get("esearchresult", {}).get("idlist", [])
        return pmid_list, full_query

    except Exception as e:
        st.error(f"PubMed 검색 도중 오류 발생: {str(e)}")
        return [], full_query


def fetch_pubmed_by_pmid(pmid):
    pmid = str(pmid).replace(".0", "").strip()
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None, None, f"NCBI 서버 통신 실패 (코드 {response.status_code})"

        root = ET.fromstring(response.content)
        article = root.find(".//Article")

        if article is None:
            return None, None, "존재하지 않는 PMID이거나 논문 정보를 찾을 수 없습니다."

        title_elem = article.find(".//ArticleTitle")
        title = (
            "".join(title_elem.itertext()).strip()
            if title_elem is not None
            else "제목 없음"
        )

        abstract_elem = article.find(".//Abstract")
        if abstract_elem is None:
            return title, None, "초록(Abstract)이 없는 문헌입니다."

        abstract_text = "".join(abstract_elem.itertext()).strip()
        if not abstract_text:
            return title, None, "초록(Abstract) 내용이 비어있습니다."

        return title, abstract_text, "성공"

    except Exception as e:
        return None, None, f"데이터 파싱 에러: {str(e)}"


def call_gemini_with_retry(model, prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            res = model.generate_content(prompt)
            return res.text, None
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg and attempt < max_retries - 1:
                time.sleep(5)
                continue
            return None, err_msg


# --------------------------------------------------
# 🤖 공통 AI 프롬프트 생성 함수 (한글 사유 완전 제거 & Conclusion 전용)
# --------------------------------------------------
def generate_prompt(
    due_category, include_criteria, exclude_criteria, title, abstract_text
):
    return f"""
    너는 임상평가(CER) 전문가야. 아래 논문 초록을 읽고 선택된 카테고리의 포함기준과 제외기준을 평가해 판정해 줘.

    [선택된 카테고리/분류]: {due_category} ({sub_model})

    [판정 규칙]:
    1. [포함기준]을 모두 만족하고, [제외기준]에 하나도 해당하지 않는 경우만 'Include'로 판정한다.
    2. [포함기준]을 하나라도 만족하지 못하거나, [제외기준]에 하나라도 해당하는 경우 'Exclude'로 판정한다.
    3. 중요: 종설(Review) 논문이나 증례 보고(Case report/series)라 하더라도, 대상 적응증과 관련 내용이 일치한다면 포함(Include) 대상으로 간주한다. 절대 '논문 유형'만을 이유로 Exclude 판정을 내리지 마라.

    [포함기준]:
    {include_criteria}

    [제외기준]:
    {exclude_criteria}

    [논문 제목]: {title}
    [논문 초록]: {abstract_text}

    답변형식 (한국어 설명 없이 오직 아래 지정된 영문 형식으로만 완벽히 작성할 것):

    판정: (Include 또는 Exclude)

    Conclusion:
    (영문 사유 1문장)

    [Conclusion 작성 가이드 - 매우 중요!]
    1. 한국어(한글) 설명이나 사유는 절대로 작성하지 마라.
    2. Include인 경우:
       - 'Conclusion:' 이라는 말머리조차 절대로 붙이지 말고, 완결된 영문 문장 자체만 적어라.
       - 'Included because', 'It is because' 같은 수식어를 절대 쓰지 마라.
       - 예시: The study evaluates clinical efficacy and safety of enteral colonic stenting in adult patients with malignant colorectal obstruction.

    3. Exclude인 경우:
       - 아래 4가지 말머리 중 가장 적절한 하나를 반드시 골라 붙이고 문장을 적어라:
         * **Different indication:**
         * **Irrelevant article:**
         * **Insufficient information:**
         * **Literature without human clinical data:**
       - 예시: **Different indication:** The study is focused exclusively on esophageal stenting rather than colonic stenting.
    """


# --------------------------------------------------
# ✨ 2단계 세그먼티드 컨트롤 메뉴 개편 (큰 버튼 ➔ 세부 버튼)
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

# 1단계: 큰 플랫폼 엔진 선택 (PubMed / GIE Journal)
target_engine = st.segmented_control(
    "",
    options=[
        "PubMed Engine",
        "GIE Journal Engine",
    ],
    default="PubMed Engine",
    key="engine_mode_seg",
)

st.markdown("<br>", unsafe_allow_html=True)

# 2단계: 선택된 엔진에 따른 세부 입력 모드 노출
if target_engine == "PubMed Engine":
    selected_mode = st.segmented_control(
        "",
        options=[
            "PubMed PICO 자동 검색",
            "PMID 리스트 CSV 업로드",
            "단일 PMID 입력",
        ],
        default="PubMed PICO 자동 검색",
        key="pubmed_sub_mode_seg",
    )
else:
    selected_mode = st.segmented_control(
        "",
        options=[
            "GIE RIS 파일 일괄 스크리닝",
        ],
        default="GIE RIS 파일 일괄 스크리닝",
        key="gie_sub_mode_seg",
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
                title, abstract_text, status = fetch_pubmed_by_pmid(single_pmid)

            if not abstract_text:
                st.error(f"데이터 조회 실패: {status}")
            else:
                st.success(f"**논문 제목:** {title}")
                st.info(f"**초록 내용:**\n{abstract_text[:400]}...")

                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-3.6-flash")
                prompt = generate_prompt(
                    due_category,
                    include_criteria,
                    exclude_criteria,
                    title,
                    abstract_text,
                )

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
    uploaded_file = st.file_uploader(
        "PMID가 적힌 CSV 업로드 ('PMID' 열 필수)", type=["csv"]
    )
    if st.button("CSV PMID 일괄 스크리닝 실행"):
        if not api_key:
            st.error("API Key가 설정되지 않았습니다!")
        elif not uploaded_file:
            st.error("CSV 파일을 업로드해 주세요!")
        else:
            try:
                df = pd.read_csv(uploaded_file, encoding="utf-8")
            except Exception:
                df = pd.read_csv(uploaded_file, encoding="cp949")

            if "PMID" not in df.columns:
                st.error(
                    "CSV 파일 안에 'PMID' 라는 이름의 열(Column)이 있어야 합니다."
                )
            else:
                df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
                if "No" in df.columns:
                    df = df.drop(columns=["No"])

                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-3.6-flash")

                titles, abstracts, results, conclusions = [], [], [], []
                progress_bar = st.progress(0)
                status_text = st.empty()
                total = len(df)

                for idx, row in df.iterrows():
                    pmid = str(row["PMID"]).replace(".0", "").strip()
                    status_text.text(
                        f"[{idx+1}/{total}] PubMed API 수집 & 분석 중... PMID: {pmid}"
                    )

                    title, abs_text, status = fetch_pubmed_by_pmid(pmid)

                    if not abs_text:
                        titles.append(title if title else "조회 실패")
                        abstracts.append(status)
                        results.append(
                            "Exclude (초록없음)" if "초록" in status else "Error"
                        )
                        conclusions.append(status)
                    else:
                        identifier = pmid
                        if identifier in st.session_state["screened_history"]:
                            prev_info = st.session_state["screened_history"][identifier]
                            prev_mod = prev_info["sub_model"]
                            prev_res = prev_info["result"]
                            titles.append(title)
                            abstracts.append(abs_text[:150] + "...")
                            results.append(f"Exclude (이전중복: {prev_mod})")
                            conclusions.append(f"Duplicate literature previously screened in [{prev_mod}] step.")
                        else:
                            titles.append(title)
                            abstracts.append(abs_text[:150] + "...")

                            prompt = generate_prompt(
                                due_category,
                                include_criteria,
                                exclude_criteria,
                                title,
                                abs_text,
                            )
                            ans, err = call_gemini_with_retry(model, prompt)

                            if ans:
                                res_label = (
                                    "Include (포함)"
                                    if "Include" in ans and "Exclude" not in ans.split("판정:")[1]
                                    else "Exclude (제외)"
                                )
                                results.append(res_label)
                                
                                raw_conclusion = ans.split("Conclusion:")[-1].strip() if "Conclusion:" in ans else ans
                                conclusions.append(raw_conclusion)

                                st.session_state["screened_history"][identifier] = {
                                    "category": due_category,
                                    "sub_model": sub_model,
                                    "result": res_label
                                }
                            else:
                                results.append("Error")
                                conclusions.append(f"AI 에러: {err}")

                    progress_bar.progress((idx + 1) / total)
                    time.sleep(1)

                df["논문 제목"] = titles
                df["초록 요약"] = abstracts
                df["AI 판정"] = results
                df["Conclusion"] = conclusions

                df.insert(0, "No", range(1, len(df) + 1))
                df.index = df.index + 1

                st.session_state["tab2_result"] = df

    if st.session_state["tab2_result"] is not None:
        st.success(f"[{due_category} - {sub_model}] 일괄 스크리닝 결과")
        st.dataframe(st.session_state["tab2_result"], hide_index=True)

        csv_data = (
            st.session_state["tab2_result"]
            .to_csv(index=False)
            .encode("utf-8-sig")
        )
        st.download_button(
            "결과 CSV 다운로드",
            data=csv_data,
            file_name="cer_screening_result.csv",
            mime="text/csv",
        )

# --------------------------------------------------
# MODE 3: PubMed PICO 키워드 자동 검색 & 스크리닝
# --------------------------------------------------
elif selected_mode == "PubMed PICO 자동 검색":
    st.subheader(f"PubMed PICO 다중 키워드 입력")
    st.caption(
        "선택하신 품목 및 세부 모델에 맞춰 P, I, C, O 키워드가 자동으로"
        " 세팅되었습니다. 필요 시 추가/수정이 가능합니다."
    )

    col_pico1, col_pico2 = st.columns(2)
    with col_pico1:
        p_val = st.text_area(
            "P (Patient / Population / Problem)", value=default_p, height=140
        )
        i_val = st.text_area("I (Intervention)", value=default_i, height=140)
    with col_pico2:
        c_val = st.text_area("C (Comparison)", value=default_c, height=140)
        o_val = st.text_area("O (Outcome)", value=default_o, height=140)

    st.markdown("---")
    st.subheader("문헌 검색 기간(연/월) 및 추출 개수 설정")

    col_s1, col_s2, col_e1, col_e2 = st.columns(4)
    with col_s1:
        start_year = st.number_input(
            "시작 연도", min_value=1990, max_value=2026, value=2026
        )
    with col_s2:
        start_month = st.number_input(
            "시작 월", min_value=1, max_value=12, value=1
        )

    with col_e1:
        end_year = st.number_input(
            "종료 연도", min_value=1990, max_value=2026, value=2026
        )
    with col_e2:
        end_month = st.number_input(
            "종료 월", min_value=1, max_value=12, value=8
        )

    col_opt1, col_opt2 = st.columns([1, 1])
    with col_opt1:
        fetch_all_toggle = st.checkbox(
            "검색된 전체 논문 수집 (개수 제한 없음)", value=False
        )
    with col_opt2:
        if not fetch_all_toggle:
            max_limit = st.number_input(
                "가져올 최대 논문 수", min_value=1, max_value=2000, value=20
            )
        else:
            max_limit = 0
            st.info("조건에 맞는 PubMed의 전체 PMID를 가져옵니다.")

    if st.button("PICO 다중 조합 검색 및 AI 스크리닝 실행"):
        if not api_key:
            st.error("API Key가 설정되지 않았습니다!")
        elif not p_val.strip() or not i_val.strip():
            st.error("최소한 P(환자군)와 I(시술법) 키워드는 입력해야 합니다!")
        else:
            date_range_label = (
                f"{start_year}년 {start_month:02d}월 ~ {end_year}년"
                f" {end_month:02d}월"
            )
            with st.spinner(
                f"PubMed에서 [{date_range_label}] 기간의 PICO 조합 조건으로"
                " 검색 중..."
            ):
                found_pmids, used_query = search_pubmed_pmids_pico(
                    p_text=p_val,
                    i_text=i_val,
                    c_text=c_val,
                    o_text=o_val,
                    start_year=start_year,
                    start_month=start_month,
                    end_year=end_year,
                    end_month=end_month,
                    fetch_all=fetch_all_toggle,
                    max_results=max_limit,
                )

            if not found_pmids:
                st.warning(
                    f"[{date_range_label}] 기간 및 입력하신 PICO 조건에 부합하는"
                    " PubMed 논문이 없습니다."
                )
                st.info(f"생성된 조합 쿼리:\n`{used_query}`")
            else:
                st.success(
                    f"**[{date_range_label}]** 검색 결과, 총 **{len(found_pmids)}건**의"
                    " PMID가 추출되었습니다!"
                )

                with st.expander(
                    "자동 생성된 PubMed 조합 쿼리식 확인 (CER 제출용)", expanded=True
                ):
                    st.code(used_query, language="sql")

                pmid_summary = ", ".join(found_pmids[:10])
                st.write(
                    f"**추출된 PMID 목록 (상위 10개):** {pmid_summary}"
                    + (" ... (이하 생략)" if len(found_pmids) > 10 else "")
                )

                st.markdown("---")
                st.subheader("추출된 PMID 기반 AI 스크리닝 진행 중...")

                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-3.6-flash")

                auto_df = pd.DataFrame({"PMID": found_pmids})
                titles, abstracts, results, conclusions = [], [], [], []

                progress_bar = st.progress(0)
                status_text = st.empty()
                total = len(auto_df)

                for idx, row in auto_df.iterrows():
                    pmid = str(row["PMID"])
                    status_text.text(
                        f"[{idx+1}/{total}] PubMed 초록 분석 중... PMID: {pmid}"
                    )

                    title, abs_text, status = fetch_pubmed_by_pmid(pmid)

                    if not abs_text:
                        titles.append(title if title else "조회 실패")
                        abstracts.append(status)
                        results.append(
                            "Exclude (초록없음)" if "초록" in status else "Error"
                        )
                        conclusions.append(status)
                    else:
                        identifier = pmid
                        if identifier in st.session_state["screened_history"]:
                            prev_info = st.session_state["screened_history"][identifier]
                            prev_mod = prev_info["sub_model"]
                            prev_res = prev_info["result"]
                            titles.append(title)
                            abstracts.append(abs_text[:150] + "...")
                            results.append(f"Exclude (이전중복: {prev_mod})")
                            conclusions.append(f"Duplicate literature previously screened in [{prev_mod}] step.")
                        else:
                            titles.append(title)
                            abstracts.append(abs_text[:150] + "...")

                            prompt = generate_prompt(
                                due_category,
                                include_criteria,
                                exclude_criteria,
                                title,
                                abs_text,
                            )
                            ans, err = call_gemini_with_retry(model, prompt)

                            if ans:
                                res_label = (
                                    "Include (포함)"
                                    if "Include" in ans and "Exclude" not in ans.split("판정:")[1]
                                    else "Exclude (제외)"
                                )
                                results.append(res_label)
                                
                                raw_conclusion = ans.split("Conclusion:")[-1].strip() if "Conclusion:" in ans else ans
                                conclusions.append(raw_conclusion)

                                st.session_state["screened_history"][identifier] = {
                                    "category": due_category,
                                    "sub_model": sub_model,
                                    "result": res_label
                                }
                            else:
                                results.append("Error")
                                conclusions.append(f"AI 에러: {err}")

                    progress_bar.progress((idx + 1) / total)
                    time.sleep(1)

                auto_df["논문 제목"] = titles
                auto_df["초록 요약"] = abstracts
                auto_df["AI 판정"] = results
                auto_df["Conclusion"] = conclusions

                auto_df.insert(0, "No", range(1, len(auto_df) + 1))

                st.session_state["tab3_result"] = auto_df

    if st.session_state["tab3_result"] is not None:
        st.success(f"[{due_category} - {sub_model}] PICO 기반 자동 스크리닝 완료 결과")
        st.dataframe(st.session_state["tab3_result"], hide_index=True)

        csv_data = (
            st.session_state["tab3_result"]
            .to_csv(index=False)
            .encode("utf-8-sig")
        )
        st.download_button(
            "PICO 스크리닝 결과 CSV 다운로드",
            data=csv_data,
            file_name=(
                f"pico_screening_{start_year}{start_month:02d}_{end_year}{end_month:02d}.csv"
            ),
            mime="text/csv",
        )

# --------------------------------------------------
# MODE 4: GIE RIS 파일 전용 일괄 AI 스크리닝
# --------------------------------------------------
elif selected_mode == "GIE RIS 파일 일괄 스크리닝":
    st.subheader("GIE Journal RIS 파일 업로드 스크리닝")
    st.caption(
        "giejournal.org 접속 ➔ Advanced Search 실행 ➔ [Export Citation] ➔ RIS 파일 다운로드 ➔ 아래 업로드 창에 드래그 & 드롭"
    )

    gie_file = st.file_uploader(
        "GIE에서 Export한 RIS 파일(.ris)을 업로드하세요", type=["ris", "txt"]
    )

    if st.button("GIE RIS 파일 AI 스크리닝 실행"):
        if not api_key:
            st.error("API Key가 설정되지 않았습니다!")
        elif not gie_file:
            st.error("GIE RIS 파일을 업로드해 주세요!")
        else:
            try:
                content = gie_file.getvalue().decode("utf-8")
            except UnicodeDecodeError:
                content = gie_file.getvalue().decode("cp949", errors="ignore")

            try:
                entries = rispy.loads(content)
            except Exception as e:
                st.error(f"RIS 파일 구조 파싱 실패: {str(e)}")
                entries = []

            if not entries:
                st.error("업로드하신 RIS 파일에서 추출된 논문 정보가 없습니다.")
            else:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-3.6-flash")

                titles, abstracts, results, conclusions, doi_list = [], [], [], [], []
                progress_bar = st.progress(0)
                status_text = st.empty()
                total = len(entries)

                for idx, entry in enumerate(entries):
                    title = entry.get("title", entry.get("primary_title", "제목 없음"))
                    abstract_text = entry.get("abstract", "").strip()
                    doi = entry.get("doi", entry.get("url", "-")).strip()

                    status_text.text(f"[{idx+1}/{total}] GIE 초록 AI 분석 중... ({title[:30]}...)")

                    identifier = doi.lower() if doi and doi != "-" else title.lower()

                    doi_list.append(doi)
                    titles.append(title)

                    if not abstract_text:
                        abstracts.append("GIE RIS 파일 내 초록(Abstract) 미포함")
                        results.append("Exclude (초록없음)")
                        conclusions.append("Abstract text is missing in the GIE RIS file.")

                    elif identifier in st.session_state["screened_history"]:
                        prev_info = st.session_state["screened_history"][identifier]
                        prev_mod = prev_info["sub_model"]
                        prev_res = prev_info["result"]
                        abstracts.append(abstract_text[:150] + "...")
                        results.append(f"Exclude (이전중복: {prev_mod})")
                        conclusions.append(f"Duplicate literature previously screened in [{prev_mod}] step.")

                    else:
                        abstracts.append(abstract_text[:150] + "...")

                        prompt = generate_prompt(
                            due_category,
                            include_criteria,
                            exclude_criteria,
                            title,
                            abstract_text,
                        )
                        ans, err = call_gemini_with_retry(model, prompt)

                        if ans:
                            res_label = (
                                "Include (포함)"
                                if "Include" in ans and "Exclude" not in ans.split("판정:")[1]
                                else "Exclude (제외)"
                            )
                            results.append(res_label)

                            raw_conclusion = ans.split("Conclusion:")[-1].strip() if "Conclusion:" in ans else ans
                            conclusions.append(raw_conclusion)

                            st.session_state["screened_history"][identifier] = {
                                "category": due_category,
                                "sub_model": sub_model,
                                "result": res_label
                            }
                        else:
                            results.append("Error")
                            conclusions.append(f"AI 에러: {err}")

                    progress_bar.progress((idx + 1) / total)
                    time.sleep(0.5)

                res_df = pd.DataFrame({
                    "No": range(1, len(entries) + 1),
                    "DOI / URL": doi_list,
                    "논문 제목": titles,
                    "초록 요약": abstracts,
                    "AI 판정": results,
                    "Conclusion": conclusions
                })

                st.session_state["tab_gie_result"] = res_df

    if st.session_state["tab_gie_result"] is not None and selected_mode == "GIE RIS 파일 일괄 스크리닝":
        st.success(f"[{due_category} - {sub_model}] GIE RIS 스크리닝 완료 결과")
        st.dataframe(st.session_state["tab_gie_result"], hide_index=True)

        csv_data = (
            st.session_state["tab_gie_result"]
            .to_csv(index=False)
            .encode("utf-8-sig")
        )
        st.download_button(
            "GIE 스크리닝 결과 CSV 다운로드",
            data=csv_data,
            file_name="gie_ris_screening_result.csv",
            mime="text/csv",
        )
