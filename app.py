import os
import time
import xml.etree.ElementTree as ET
import google.generativeai as genai
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Taewoong Medical - AI 문헌 스크리닝", layout="wide"
)

# --------------------------------------------------
# 🎨 고급 커스텀 CSS (태웅메디컬 브랜딩 & UI 개선)
# --------------------------------------------------
st.markdown(
    """
<style>
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
        font-size: 15px;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 4px;
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

    /* 세그먼티드 컨트롤 커스텀 */
    div[data-testid="stSegmentedControl"] {
        background-color: #f1f5f9;
        padding: 6px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
    }
    
    div[data-testid="stSegmentedControl"] button {
        border-radius: 8px !important;
        font-weight: 1000 !important;
        font-size: 14px !important;
        border: none !important;
        padding: 8px 24px !important;
        transition: all 0.2s ease !important;
    }
    
    div[data-testid="stSegmentedControl"] button[aria-selected="true"] {
        background-color: #0b1a2d !important;
        color: #ffffff !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
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


# HOME 버튼 클릭 시 리셋을 위한 콜백 함수
def reset_to_home():
    if "radio_category" in st.session_state:
        del st.session_state["radio_category"]


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
    )

    # 세부 모델 선택 (품목 선택 바로 아래 위치)
    sub_model = "전체 (All Models)"
    if due_category == "1. Biliary Stent":
        sub_model = st.selectbox(
            "세부 모델/유형을 선택하세요",
            options=[
                "Niti-S Biliary Covered Stent",
                "Niti-S Biliary Uncovered Stent",
                "ComVi Biliary Stent",
            ],
        )
    elif due_category == "2. Esophageal Stent":
        sub_model = st.selectbox(
            "세부 모델/유형을 선택하세요",
            options=["Niti-S Esophageal Covered Stent"],
        )
    elif due_category == "3. Pyloric/Duodenal Stent":
        sub_model = st.selectbox(
            "세부 모델/유형을 선택하세요",
            options=[
                "Niti-S Pyloric/Duodenal Covered Stent",
                "Niti-S Pyloric/Duodenal Uncovered Stent",
                "ComVi Pyloric/Duodenal Stent",
            ],
        )
    elif due_category == "4. Colonic Stent":
        sub_model = st.selectbox(
            "세부 모델/유형을 선택하세요",
            options=[
                "Niti-S Enteral Colonic Covered Stent",
                "Niti-S Enteral Colonic Uncovered Stent",
                "ComVi Enteral Colonic Stent",
            ],
        )
    elif due_category == "5. Drainage Stent":
        sub_model = st.selectbox(
            "세부 모델/유형을 선택하세요",
            options=[
                "Niti-S SPAXUS Stent",
                "Niti-S Hot SPAXUS Stent",
                "Niti-S NAGI Stent",
            ],
        )

    # HOME 버튼 (사이드바 최하단 위치)
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
<div class="hero-tag">TAEWOONG MEDICAL CER PLATFORM</div>
<div class="dept-tag">Development Department | Development 2nd Team</div>
</div>
<div class="hero-title">PubMed PMID 기반 AI 문헌 스크리닝 시스템</div>
<div class="hero-subtitle">Medical Device Regulatory Compliance & Systematic Literature Review Powered by Gemini 3.6 Flash</div>
</div>""",
        unsafe_allow_html=True,
    )

    col_ov1, col_ov2, col_ov3 = st.columns(3)

    with col_ov1:
        with st.container(border=True):
            st.markdown(
                """
                <div class="card-title">TARGET PRODUCTS</div>
                <div class="card-value">Taewoong Medical’s Stent Product Lines</div>
                <div class="card-desc">클릭하여 세부 라인업 및 제품 카탈로그 정보를 확인하세요.</div>
                """,
                unsafe_allow_html=True,
            )

            with st.popover("제품 라인업 카탈로그 상세보기", use_container_width=True):
                prod_tab1, prod_tab2, prod_tab3, prod_tab4, prod_tab5 = st.tabs([
                    "Biliary",
                    "Esophageal",
                    "Pyloric/Duodenal",
                    "Colonic",
                    "Drainage",
                ])

                # --------------------------------------------------
                # 📌 1. Biliary 탭 (Total 13 Types)
                # --------------------------------------------------
                with prod_tab1:
                    st.markdown("#### **Niti-S & ComVi Biliary Stent**")
                    st.write("")

                    with st.expander("🔹 Niti-S Biliary Uncovered Stent"):
                        biliary_uncovered_models = [
                            ("S-Type", "biliary_uncovered_s.png", "기본형 Uncovered Stent"),
                            ("D-Type", "biliary_uncovered_d.png", "Dual Structure 유연성 강화 모델"),
                            ("M-Type", "biliary_uncovered_m.png", "Mesh 구조 설계로 방사력 유지"),
                            ("LCD-Type", "biliary_uncovered_lcd.png", "Large Cell Design 적용"),
                        ]
                        for m_name, m_img, m_desc in biliary_uncovered_models:
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if os.path.exists(m_img):
                                    st.image(m_img, use_container_width=True)
                                else:
                                    st.caption(f"📷 {m_img} 이미지 등록 필요")
                            with c2:
                                st.markdown(f"**Niti-S Biliary Uncovered [{m_name}]**\n\n- {m_desc}")
                            st.divider()

                    with st.expander("🔹 Niti-S Biliary Covered Stent"):
                        biliary_covered_models = [
                            ("Full Covered-Type", "biliary_covered_full.png", "전체 피복 구조로 종양 내성장 방지"),
                            ("Both Bare-Type", "biliary_covered_bothbare.png", "양끝 단 Bare 구조로 이동 방지"),
                            ("Giobor", "biliary_covered_giobor.png", "특수 덮개 구조 및 위치 고정 강화"),
                            ("Flare-Type", "biliary_covered_flare.png", "Flared Ends 적용으로 Position 유지"),
                            ("Kaffes", "biliary_covered_kaffes.png", "제거 용이 디자인 (Removable Stent)"),
                            ("Bumpy", "biliary_covered_bumpy.png", "Bumpy 굴곡 구조 적용, 췌관 Stricture용"),
                        ]
                        for m_name, m_img, m_desc in biliary_covered_models:
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if os.path.exists(m_img):
                                    st.image(m_img, use_container_width=True)
                                else:
                                    st.caption(f"📷 {m_img} 이미지 등록 필요")
                            with c2:
                                st.markdown(f"**Niti-S Biliary Covered [{m_name}]**\n\n- {m_desc}")
                            st.divider()

                    with st.expander("🔹 ComVi Biliary Stent"):
                        biliary_comvi_models = [
                            ("Full Covered-Type", "biliary_comvi_full.png", "이중막(PTFE+PTFE) 구조로 Tissue Ingrowth 완전 차단"),
                            ("Both Bare-Type", "biliary_comvi_bothbare.png", "ComVi 이중막 구조 + 양 끝단 Bare 앵커링"),
                            ("End Bare-Type", "biliary_comvi_endbare.png", "한쪽 끝단 Bare 적용 모델"),
                        ]
                        for m_name, m_img, m_desc in biliary_comvi_models:
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if os.path.exists(m_img):
                                    st.image(m_img, use_container_width=True)
                                else:
                                    st.caption(f"📷 {m_img} 이미지 등록 필요")
                            with c2:
                                st.markdown(f"**ComVi Biliary [{m_name}]**\n\n- {m_desc}")
                            st.divider()

                # --------------------------------------------------
                # 📌 2. Esophageal 탭 (Total 8 Types)
                # --------------------------------------------------
                with prod_tab2:
                    st.markdown("#### **Niti-S Esophageal Stent**")
                    st.write("")

                    with st.expander("🔹 Niti-S Esophageal Covered Stent"):
                        esophageal_covered_models = [
                            ("Full Covered-Type", "esophageal_covered_full.png", "식도 전체 피복 구조로 병변 침투 방지 및 협착 완화"),
                            ("Cervical", "esophageal_covered_cervical.png", "경부 식도(Cervical Esophagus) 협착 전용 특수 설계"),
                            ("Both Bare-Type", "esophageal_covered_bothbare.png", "양 끝단 Bare 메쉬 적용으로 위치 이동(Migration) 방지"),
                            ("Conio", "esophageal_covered_conio.png", "Conio 형태 적용 특수 구조 모델"),
                            ("Anti Reflux-Type", "esophageal_covered_antireflux.png", "역류 방지 밸브 구조 적용으로 위산 역류 예방"),
                            ("Double Anti Reflux-Type", "esophageal_covered_doubleantireflux.png", "이중 역류 방지 구조로 강력한 역류 차단 기능 제공"),
                            ("Double-Type", "esophageal_covered_double.png", "이중 레이어 메쉬 구조로 인체공학적 유연성 확보"),
                            ("Beta-2", "esophageal_covered_beta2.png", "Beta-2 차세대 유연성 메쉬 설계 모델"),
                        ]
                        for m_name, m_img, m_desc in esophageal_covered_models:
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if os.path.exists(m_img):
                                    st.image(m_img, use_container_width=True)
                                else:
                                    st.caption(f"📷 {m_img} 이미지 등록 필요")
                            with c2:
                                st.markdown(f"**Niti-S Esophageal Covered [{m_name}]**\n\n- {m_desc}")
                            st.divider()

                # --------------------------------------------------
                # 📌 3. Pyloric/Duodenal 탭 (Total 6 Types)
                # --------------------------------------------------
                with prod_tab3:
                    st.markdown("#### **Niti-S & ComVi Pyloric/Duodenal Stent**")
                    st.write("")

                    with st.expander("🔹 Niti-S Pyloric/Duodenal Uncovered Stent"):
                        pyloric_uncovered_models = [
                            ("D-Type", "pyloric_uncovered_d.png", "Dual Structure 유연 구조로 위출구/십이지장 협착부 유연성 및 통과성 강화"),
                        ]
                        for m_name, m_img, m_desc in pyloric_uncovered_models:
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if os.path.exists(m_img):
                                    st.image(m_img, use_container_width=True)
                                else:
                                    st.caption(f"📷 {m_img} 이미지 등록 필요")
                            with c2:
                                st.markdown(f"**Niti-S Pyloric/Duodenal Uncovered [{m_name}]**\n\n- {m_desc}")
                            st.divider()

                    with st.expander("🔹 Niti-S Pyloric/Duodenal Covered Stent"):
                        pyloric_covered_models = [
                            ("Full Covered-Type", "pyloric_covered_full.png", "전체 피복 구조 적용으로 위출구 및 십이지장 종양 내성장 방지"),
                            ("Both Bare-Type", "pyloric_covered_bothbare.png", "양 끝단 Bare 구조 적용으로 스텐트 위치 고정 및 이동(Migration) 방지"),
                            ("End Bare-Type", "pyloric_covered_endbare.png", "한쪽 끝단 Bare 적용으로 조직 고정력 향상"),
                        ]
                        for m_name, m_img, m_desc in pyloric_covered_models:
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if os.path.exists(m_img):
                                    st.image(m_img, use_container_width=True)
                                else:
                                    st.caption(f"📷 {m_img} 이미지 등록 필요")
                            with c2:
                                st.markdown(f"**Niti-S Pyloric/Duodenal Covered [{m_name}]**\n\n- {m_desc}")
                            st.divider()

                    with st.expander("🔹 ComVi Pyloric/Duodenal Stent"):
                        pyloric_comvi_models = [
                            ("Flare-Type", "pyloric_comvi_flare.png", "ComVi 이중막 구조 + Flare 확장 구조로 위치 고정력 극대화"),
                            ("Both Bare-Type", "pyloric_comvi_bothbare.png", "ComVi 이중막(PTFE+PTFE) 구조 + 양 끝단 Bare 앵커링"),
                        ]
                        for m_name, m_img, m_desc in pyloric_comvi_models:
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if os.path.exists(m_img):
                                    st.image(m_img, use_container_width=True)
                                else:
                                    st.caption(f"📷 {m_img} 이미지 등록 필요")
                            with c2:
                                st.markdown(f"**ComVi Pyloric/Duodenal [{m_name}]**\n\n- {m_desc}")
                            st.divider()

                # --------------------------------------------------
                # 📌 4. Colonic 탭 (Total 6 Types)
                # --------------------------------------------------
                with prod_tab4:
                    st.markdown("#### **Niti-S & ComVi Enteral Colonic Stent**")
                    st.write("")

                    with st.expander("🔹 Niti-S Enteral Colonic Uncovered Stent"):
                        colonic_uncovered_models = [
                            ("S-Type", "colonic_uncovered_s.png", "기본형 대장 Uncovered Stent 구조"),
                            ("D-Type", "colonic_uncovered_d.png", "Dual Structure 적용으로 대장 굴곡부 우수한 통과성 확보"),
                        ]
                        for m_name, m_img, m_desc in colonic_uncovered_models:
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if os.path.exists(m_img):
                                    st.image(m_img, use_container_width=True)
                                else:
                                    st.caption(f"📷 {m_img} 이미지 등록 필요")
                            with c2:
                                st.markdown(f"**Niti-S Enteral Colonic Uncovered [{m_name}]**\n\n- {m_desc}")
                            st.divider()

                    with st.expander("🔹 Niti-S Enteral Colonic Covered Stent"):
                        colonic_covered_models = [
                            ("Full Covered-Type", "colonic_covered_full.png", "전체 피복 구조로 대장/직장 종양 내성장 차단"),
                            ("Both Bare-Type", "colonic_covered_bothbare.png", "양 끝단 Bare 구조 적용으로 이동(Migration) 방지"),
                            ("End Bare-Type", "colonic_covered_endbare.png", "한쪽 끝단 Bare 적용으로 대장 내 고정력 향상"),
                        ]
                        for m_name, m_img, m_desc in colonic_covered_models:
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if os.path.exists(m_img):
                                    st.image(m_img, use_container_width=True)
                                else:
                                    st.caption(f"📷 {m_img} 이미지 등록 필요")
                            with c2:
                                st.markdown(f"**Niti-S Enteral Colonic Covered [{m_name}]**\n\n- {m_desc}")
                            st.divider()

                    with st.expander("🔹 ComVi Enteral Colonic Stent"):
                        colonic_comvi_models = [
                            ("Both Bare-Type", "colonic_comvi_bothbare.png", "ComVi 이중막(PTFE+PTFE) 구조로 조직 침투 차단 + 양 끝단 Bare 앵커링"),
                        ]
                        for m_name, m_img, m_desc in colonic_comvi_models:
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if os.path.exists(m_img):
                                    st.image(m_img, use_container_width=True)
                                else:
                                    st.caption(f"📷 {m_img} 이미지 등록 필요")
                            with c2:
                                st.markdown(f"**ComVi Enteral Colonic [{m_name}]**\n\n- {m_desc}")
                            st.divider()

                # --------------------------------------------------
                # 📌 5. Drainage 탭 (Total 3 Types)
                # --------------------------------------------------
                with prod_tab5:
                    st.markdown("#### **Niti-S Drainage Stent**")
                    st.write("")

                    with st.expander("🔹 Niti-S SPAXUS Stent"):
                        spaxus_models = [
                            ("SPAXUS", "drainage_spaxus.png", "EUS-guided Transluminal Drainage 전용 Lumen-Apposing Stent"),
                        ]
                        for m_name, m_img, m_desc in spaxus_models:
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if os.path.exists(m_img):
                                    st.image(m_img, use_container_width=True)
                                else:
                                    st.caption(f"📷 {m_img} 이미지 등록 필요")
                            with c2:
                                st.markdown(f"**Niti-S [{m_name}] Stent**\n\n- {m_desc}")
                            st.divider()

                    with st.expander("🔹 Niti-S Hot SPAXUS Stent"):
                        hot_spaxus_models = [
                            ("Hot SPAXUS", "drainage_hot_spaxus.png", "Electrocautery Delivery System 일체형 스텐트"),
                        ]
                        for m_name, m_img, m_desc in hot_spaxus_models:
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if os.path.exists(m_img):
                                    st.image(m_img, use_container_width=True)
                                else:
                                    st.caption(f"📷 {m_img} 이미지 등록 필요")
                            with c2:
                                st.markdown(f"**Niti-S [{m_name}] Stent**\n\n- {m_desc}")
                            st.divider()

                    with st.expander("🔹 Niti-S Nagi Stent"):
                        nagi_models = [
                            ("NAGI", "drainage_nagi.png", "Pancreatic Pseudocyst & WON 배액 전용 대구경 Flare 스텐트"),
                        ]
                        for m_name, m_img, m_desc in nagi_models:
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if os.path.exists(m_img):
                                    st.image(m_img, use_container_width=True)
                                else:
                                    st.caption(f"📷 {m_img} 이미지 등록 필요")
                            with c2:
                                st.markdown(f"**Niti-S [{m_name}] Stent**\n\n- {m_desc}")
                            st.divider()

    with col_ov2:
        with st.container(border=True):
            st.markdown(
                """
                <div class="card-title">AI PIPELINE</div>
                <div class="card-value">Gemini 3.6 Flash + PubMed Engine</div>
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
                <div class="card-value">Standardization and Automation of Literature Review</div>
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
    default_inc = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Malignant biliary obstruction/stricture, Benign biliary obstruction/stricture (Covered types only), Benign pancreatic duct stricture (Niti-S Bumpy type only)
5. Intervention: Biliary SEMS (Uncovered or Covered). Specific Taewoong Medical models: Niti-S (S, D, M, LCD, Full Covered, Both Bare, Giobor, Flare, Kaffes, Bumpy), ComVi (Full Covered, Both Bare, End Bare)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (e.g., WallFlex, Evolution, EGIS, Bonastent, Hanarostent)
7. Outcomes: Stent patency, Decreased bilirubin, Technical/Clinical success, Complications, Stent removal (for benign cases)"""
    default_exc = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-biliary/pancreatic target areas only (e.g., vascular, esophageal, colonic, tracheal)
3. Irrelevant articles: Articles not related to biliary/pancreatic luminal stenting or stricture management
4. Non-study publications: Editorials, letters, comments (단, Review 및 Case report는 제외하지 않음)"""

    if sub_model == "Niti-S Biliary Covered Stent":
        default_p = (
            "Biliary obstruction\nBiliary stricture\nMalignant biliary"
            " stricture\nBenign biliary stricture"
        )
        default_i = (
            "Niti-S Covered\nNiti-S Full Covered\nCovered biliary SEMS\nCovered"
            " metal stent\nTaewoong Covered"
        )
        default_c = "Uncovered stent\nPlastic stent\nSurgery\nWallFlex Covered"
        default_o = (
            "Stent patency\nDecreased bilirubin\nStent removal\nComplications"
        )
    elif sub_model == "Niti-S Biliary Uncovered Stent":
        default_p = (
            "Biliary obstruction\nBiliary stricture\nMalignant biliary"
            " stricture\nMalignant biliary obstruction"
        )
        default_i = (
            "Niti-S Uncovered\nNiti-S Bare\nUncovered biliary SEMS\nUncovered metal"
            " stent\nBoth Bare"
        )
        default_c = "Covered stent\nPlastic stent\nSurgery\nWallFlex Uncovered"
        default_o = (
            "Stent patency\nDecreased bilirubin\nTumor ingrowth\nComplications"
        )
    elif sub_model == "ComVi Biliary Covered Stent":
        default_p = (
            "Biliary obstruction\nBiliary stricture\nMalignant biliary"
            " stricture\nMalignant biliary obstruction"
        )
        default_i = "ComVi\nComVi Biliary\nComVi Covered\nTaewoong ComVi"
        default_c = (
            "Single layer Covered SEMS\nUncovered stent\nPlastic stent\nWallFlex"
        )
        default_o = (
            "Stent patency\nTumor ingrowth prevention\nTechnical success\nClinical"
            " success"
        )
    else:
        default_p = (
            "Biliary obstruction\nBiliary stricture\nMalignant biliary"
            " stricture\nMalignant biliary obstruction\nBenign biliary"
            " obstruction\nBenign biliary stricture\nBenign pancreatic duct"
            " stricture"
        )
        default_i = (
            "Self-expandable metallic stent\nSelf-expandable metal"
            " stent\nSEMS\nTaewoong\nNiti-S\nComVi\nUncovered stent\nCovered stent"
        )
        default_c = (
            "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic"
            " stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nUncovered"
            " stent\nEvolution\nWallFlex\nEGIS\nBonastent\nHanarostent"
        )
        default_o = "Stent patency\nDecreased bilirubin\nRemoval"

elif due_category == "2. Esophageal Stent":
    default_inc = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Esophageal stricture/obstruction (Malignant or Benign), Refractory benign esophageal stricture, Tracheoesophageal fistula (TEF / TE fistula)
5. Intervention: Esophageal SEMS, Covered type. Specific Taewoong Medical models: Niti-S Esophageal (Full covered, Cervical, Both bare type, Conio, Anti reflux, Double anti reflux, Double type, Beta-2)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (WallFlex, Ultraflex, Evolution, Hanarostent, Aixstent, EGIS, Bonastent, Micro-Tech)
7. Outcomes: Stent patency, Dysphagia improvement, Fistula closure, Removal (in benign strictures)"""
    default_exc = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-esophageal target areas only (e.g., pure biliary, colonic, duodenal, vascular)
3. Irrelevant articles: Articles not related to esophageal stenting, stricture dilation, or TE fistula management
4. Non-study publications: Editorials, letters, comments (단, Review 및 Case report는 제외하지 않음)"""

    default_p = (
        "Esophageal stricture\nEsophageal obstruction\nMalignant esophageal"
        " stricture\nMalignant esophageal obstruction\nBenign esophageal"
        " stricture\nRefractory benign esophageal stricture\nBenign esophgeal"
        " obstruction\nTracheoesophageal fistula"
    )
    default_i = (
        "Self-expandable metallic stent\nSelf-expandable metal"
        " stent\nSEMS\nTaewoong\nNiti-S\nCovered stent"
    )
    default_c = (
        "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic"
        " stent\nSelf-expandable metal stent\nSEMS\nCovered"
        " stent\nWallFlex\nUltraflex\nEvolution\nHanarostent\nAixstent\nEGIS\nBonastent\nMicro-tech"
    )
    default_o = (
        "Stent patency\nDysphagia improvement\nFistula closure\nRemoval"
    )

elif due_category == "3. Pyloric/Duodenal Stent":
    default_inc = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Pyloric/Duodenal stricture or obstruction, Gastric Outlet Obstruction (GOO), Malignant or Benign (for Covered types)
5. Intervention: Pyloric/Duodenal SEMS, Uncovered or Covered type. Specific Taewoong Medical models: Niti-S Pyloric/Duodenal (D-Type, Full Covered, Both Bare, End Bare), ComVi Pyloric/Duodenal (Flare-Type, Both Bare)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (WallFlex, WallFlex Soft, Hanarostent, Evolution, EGIS, Bonastent)
7. Outcomes: Stent patency, Obstruction relief/resolution/improvement, GOOSS score / Oral intake, Technical/Clinical success, Complications, Stent removal (for benign strictures)"""
    default_exc = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-pyloric/duodenal target areas only (e.g., pure biliary, esophageal, colonic, or vascular stents without duodenal/gastric outlet involvement)
3. Irrelevant articles: Articles not related to pyloric/duodenal stenting or GOO management
4. Non-study publications: Editorials, letters, comments (단, Review 및 Case report는 제외하지 않음)"""

    default_p = (
        "Pyloric stricture\nPyloric obstruction\nDuodenal stricture\nDuodenal"
        " obstruction\nGastric outlet obstruction\nMalignant pyloric"
        " stricture\nMalignant pyloric obstruction\nMalignant duodenal"
        " stricture\nMalignant duodenal obstruction\nBenign pyloric"
        " stricture\nBenign pyloric obstruction\nBenign duodenal"
        " stricture\nBenign duodenal obstruction"
    )
    default_i = (
        "Self-expandable metallic stent\nSelf-expandable metal"
        " stent\nSEMS\nTaewoong\nNiti-S\nComVi\nCovered stent\nUncovered stent"
    )
    default_c = (
        "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic"
        " stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nUncovered"
        " stent\nWallFlex\nWallFlex Soft\nHanarostent\nEvolution\nEGIS\nBonastent"
    )
    default_o = (
        "Stent patency\nObstruction relief\nObstruction resolution\nObstruction"
        " improvement\nRemoval"
    )

elif due_category == "4. Colonic Stent":
    default_inc = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Colonic/Colorectal stricture or obstruction (Malignant or Benign for Covered types)
5. Intervention: Colonic SEMS, Uncovered or Covered type. Specific Taewoong Medical models: Niti-S Enteral Colonic (S-Type, D-Type, Full Covered, Both Bare, End Bare), ComVi Enteral Colonic (Both Bare-Type)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (WallFlex, WallFlex Soft, Hanarostent, Micro-Tech, Bonastent)
7. Outcomes: Stent patency, Obstruction relief/resolution/improvement, Technical/Clinical success, Complications, Stent removal (for benign strictures)"""
    default_exc = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-colonic target areas only (e.g., pure biliary, esophageal, pyloric/duodenal, or vascular stents without colonic/colorectal involvement)
3. Irrelevant articles: Articles not related to colonic stenting or colorectal obstruction management
4. Non-study publications: Editorials, letters, comments (단, Review 및 Case report는 제외하지 않음)"""

    default_p = (
        "Colonic stricture\nColonic obstruction\nColorectal stricture\nColorectal"
        " obstruction\nMalignant colonic stricture\nMalignant colonic"
        " obstruction\nMalignant colorectal stricture\nMalignant colorectal"
        " obstruction\nBenign colonic stricture\nBenign colonic"
        " obstruction\nBenign colorectal stricture\nBenign colorectal"
        " obstruction"
    )
    default_i = (
        "Self-expandable metallic stent\nSelf-expandable metal"
        " stent\nSEMS\nTaewoong\nNiti-S\nComVi\nUncovered stent\nCovered stent"
    )
    default_c = (
        "Surgery\nPlastic stent\nBalloon dilation\nSelf-expandable metallic"
        " stent\nSelf-expandable metal stent\nSEMS\nCovered stent\nUncovered"
        " stent\nWallFlex\nWallFlex Soft\nHanarostent\nMicro-tech\nBonastent"
    )
    default_o = (
        "Stent patency\nObstruction relief\nObstruction resolution\nObstruction"
        " improvement\nRemoval"
    )

elif due_category == "5. Drainage Stent":
    default_inc = """1. Text availability: Full text (Original articles, Reviews, Case reports/series 모두 포함)
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Pancreatic pseudocyst, Walled-off necrosis (WON) / Pancreatic necrosis, Gallbladder drainage (Cholecystitis) / Biliary tract drainage, Transgastric or transduodenal drainage indications
5. Intervention: Lumen-apposing metal stents (LAMS) or EUS-guided drainage stents. Specific Taewoong Medical models: Niti-S Nagi, Niti-S SPAXUS, Niti-S Hot SPAXUS (Electrocautery Delivery System)
6. Comparators: Surgery, Percutaneous drainage, Plastic double-pigtail stents, or competitor LAMS (e.g., AXIOS / Hot AXIOS)
7. Outcomes: Technical/Clinical success rate, Drainage efficacy, Resolution of pseudocyst/necrosis, Complications (Bleeding, Stent migration, Perforation, Occlusion), Removal rate"""
    default_exc = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication/Irrelevant: Non-drainage target indications or vascular/intraluminal stenting without transluminal/EUS drainage purpose
3. Non-study publications: Editorials, letters, comments (단, Review 및 Case report는 제외하지 않음)"""

    default_p = (
        "Pancreatic pseudocyst\nWalled-off necrosis\nWON\nGallbladder drainage"
    )
    default_i = "Lumen-apposing metal stents\nLAMS\nNiti-S SPAXUS\nSPAXUS"
    default_c = (
        "Self-expandable metallic stent\nSelf-expandable metal"
        " stent\nSEMS\nTaewoong\nNiti-S\nComVi\nUncovered stent\nCovered stent"
    )
    default_o = (
        "Technical success\nClinical success\nDrainage efficacy\nResolution\nComplications"
    )

else:
    default_p = "Obstructive Jaundice\nBiliary Stricture"
    default_i = "Biliary Stent\nSEMS"
    default_c = "Surgery\nPlastic stent"
    default_o = "Technical success\nClinical success"

include_criteria = default_inc
exclude_criteria = default_exc


# --------------------------------------------------
# 🌐 PubMed API 기능 및 XML 파싱 함수
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
                time.sleep(10)
                continue
            return None, err_msg


# --------------------------------------------------
# 🤖 공통 AI 프롬프트 생성 함수
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

    답변형식 (마크다운 환경에서 텍스트가 뭉치지 않도록 반드시 항목과 항목 사이에 **빈 줄(Enter 2번)**을 넣어 작성할 것):

    판정: (Include 또는 Exclude)

    사유:
    **(항목명):** (내용)

    **(항목명):** (내용)

    ---
    **(영어 요약 항목명):** (내용)

    [사유 및 결론 작성 가이드 - 매우 중요!]
    1. 사유 (한국어 설명 부분):
       - "기준 4", "제외기준 2", "- 1" 같은 **번호나 숫자는 절대 표기하지 마라.**
       - 각 사유의 항목명은 반드시 **볼드 처리(**)**하여 작성할 것. (예시: "**적응증 (Clinical Conditions):** ...", "**중재시술 (Intervention):** ...")
       - 화면에 한 줄씩 예쁘게 보이도록, 각 사유 항목이 끝날 때마다 **반드시 한 줄을 띄우고(빈 줄 삽입)** 다음 사유를 작성하라.
    
    2. 결론 요약 (영어 부분):
       - 한국어 사유 작성이 모두 끝난 후 **반드시 빈 줄을 띄우고 마크다운 구분선(`---`)**을 넣어라. ('Conclusion' 이라는 단어는 절대 쓰지 마라)
       - 구분선 바로 다음 줄에 영어(English)로 한 문장 작성한다.
       - 판정이 'Include'인 경우: 논문이 포함된 핵심 이유를 자연스러운 영어 문장으로 작성.
       - 판정이 'Exclude'인 경우: 제외된 핵심 이유를 반드시 아래 4가지 [배제 해당사항] 중 가장 적절한 하나를 골라 "**배제해당사항:** 영어 문장" 형식으로 작성할 것. (배제해당사항 이름은 볼드 처리)
         * **Different indication:**
         * **Irrelevant article:**
         * **Insufficient information:**
         * **Literature without human clinical data:**
    """


# --------------------------------------------------
# ✨ 세그먼티드 컨트롤 메뉴 및 선택된 품목 하이라이트 헤더
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

selected_mode = st.segmented_control(
    "",
    options=[
        "단일 PMID 입력",
        "PMID 리스트 CSV 업로드",
        "PICO 다중 검색어 기반 자동 추출",
    ],
    default="PICO 다중 검색어 기반 자동 추출",
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
            except:
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

                titles, abstracts, results, reasons = [], [], [], []
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
                        reasons.append(status)
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
                            results.append(
                                "Include (포함)"
                                if "Include" in ans and "Exclude" not in ans.split("판정:")[1]
                                else "Exclude (제외)"
                            )
                            reasons.append(
                                ans.split("사유:")[-1].strip() if "사유:" in ans else ans
                            )
                        else:
                            results.append("Error")
                            reasons.append(f"AI 에러: {err}")

                    progress_bar.progress((idx + 1) / total)
                    time.sleep(4.5)

                df["논문 제목"] = titles
                df["초록 요약"] = abstracts
                df["AI 판정"] = results
                df["상세 사유"] = reasons

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
# MODE 3: PICO 키워드 조합 기반 자동 검색 & 스크리닝
# --------------------------------------------------
elif selected_mode == "PICO 다중 검색어 기반 자동 추출":
    st.subheader(f"PICO 다중 키워드 입력")
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
                titles, abstracts, results, reasons = [], [], [], []

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
                        reasons.append(status)
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
                            results.append(
                                "Include (포함)"
                                if "Include" in ans and "Exclude" not in ans.split("판정:")[1]
                                else "Exclude (제외)"
                            )
                            reasons.append(
                                ans.split("사유:")[-1].strip() if "사유:" in ans else ans
                            )
                        else:
                            results.append("Error")
                            reasons.append(f"AI 에러: {err}")

                    progress_bar.progress((idx + 1) / total)
                    time.sleep(4.5)

                auto_df["논문 제목"] = titles
                auto_df["초록 요약"] = abstracts
                auto_df["AI 판정"] = results
                auto_df["상세 사유"] = reasons

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
