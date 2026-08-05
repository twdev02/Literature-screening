import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests
import xml.etree.ElementTree as ET
import time

st.set_page_config(page_title="AI 문헌 스크리닝", layout="wide")
st.title("PubMed PMID 기반 문헌 스크리닝 시스템")

# --------------------------------------------------
# ⚙️ 사이드바: API Key 및 모델/DUE 분류 설정
# --------------------------------------------------
with st.sidebar:
    st.header("⚙️ 시스템 설정")
    
    # 🔑 Streamlit Secrets 안전 조회
    default_api_key = ""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            default_api_key = str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        default_api_key = ""
    
    # 사용자 직접 입력란
    user_api_key = st.text_input("Gemini API Key (미입력 시 서버 기본키 적용)", type="password")
    
    # 최종 적용할 API Key
    api_key = user_api_key.strip() if user_api_key.strip() else default_api_key
    
    if api_key:
        st.success("🟢 API Key가 정상 등록되었습니다.")
    else:
        st.error("🔴 API Key가 없습니다. Secrets 등록 또는 키를 입력하세요.")
        
    st.markdown("---")
    st.subheader("🤖 AI 모델 선택")
    
    # 💡 404 에러를 방지하는 공식 지원 모델선택
    selected_model_option = st.selectbox(
        "사용할 AI 모델을 선택하세요",
        [
            "gemini-2.5-flash (권장: 하루 1500회)",
            "gemini-2.0-flash (안정: 하루 1500회)",
            "gemini-3.6-flash (실험용: 하루 20회)"
        ]
    )
    
    # 모델 매핑 (정확한 API 명칭)
    if "2.5" in selected_model_option:
        model_code = "gemini-2.5-flash"
    elif "2.0" in selected_model_option:
        model_code = "gemini-2.0-flash"
    else:
        model_code = "gemini-3.6-flash"
    
    st.markdown("---")
    st.subheader("📋 제품 / 적응증 (DUE) 선택")
    
    due_category = st.selectbox(
        "카테고리를 선택하세요",
        [
            "직접 입력 (Custom)",
            "1. Biliary (담도)",
            "2. Esophageal (식도)",
            "3. Colonic (대장/결장)",
            "4. Pyloric (유문/위출구)",
            "5. Drainage (배액/배설)"
        ]
    )
    
    if due_category == "1. Biliary (담도)":
        default_inc = "1. 담도(Biliary tract) 질환 또는 담도 협착/폐색 환자 대상\n2. 담도 스텐트/카테터 임상적 유효성 및 안전성 평가\n3. 18세 이상 성인 환자"
        default_exc = "1. 췌장/식도/혈관 등 타 부위 단독 연구 (Different target area)\n2. 동물 실험 (Animal study, In vivo)\n3. 소아/청소년 대상 (Under 18 years old)\n4. 리뷰 논문 (Review article, Meta-analysis)"
    elif due_category == "2. Esophageal (식도)":
        default_inc = "1. 식도(Esophagus) 협착, 천공, 종양 환자 대상\n2. 식도 스텐트/치료 기기 임상 데이터\n3. 18세 이상 성인 환자"
        default_exc = "1. 위/대장/담도 등 타 장기 단독 연구 (Different target area)\n2. 동물 실험 (Animal study)\n3. 소아 대상 (Under 18 years old)\n4. 리뷰 논문 (Review article)"
    elif due_category == "3. Colonic (대장/결장)":
        default_inc = "1. 결장 및 대장(Colorectal/Colon) 협착 또는 폐색 환자 대상\n2. 대장 스텐트/처치 기기 유효성 및 안전성 평가\n3. 18세 이상 성인 환자"
        default_exc = "1. 소장/식도/담도 등 타 장기 단독 연구\n2. 동물 실험 (Animal study)\n3. 소아 대상 (Under 18 years old)\n4. 리뷰 논문 (Review article)"
    elif due_category == "4. Pyloric (유문/위출구)":
        default_inc = "1. 위출구 폐색(Gastric Outlet Obstruction, GOO) 및 유문(Pylorus) 협착 환자 대상\n2. 유문/십이지장 스텐트 임상 성과 데이터\n3. 18세 이상 성인 환자"
        default_exc = "1. 식도/하부 대장/혈관 단독 연구\n2. 동물 실험 (Animal study)\n3. 소아 대상 (Under 18 years old)\n4. 리뷰 논문 (Review article)"
    elif due_category == "5. Drainage (배액/배설)":
        default_inc = "1. 배액(Drainage) 관급/카테터/튜브 적용 체액/농양 배액 환자 대상\n2. 배액 성능, 개통성(Patency), 합병증 임상 평가\n3. 18세 이상 성인 환자"
        default_exc = "1. 단순 혈관 카테터 또는 주입 전용 기기\n2. 동물 실험 (Animal study)\n3. 소아 대상 (Under 18 years old)\n4. 리뷰 논문 (Review article)"
    else:
        default_inc = "1. 대상 환자군 조건 입력\n2. 임상 평가 목적 입력"
        default_exc = "1. 동물 실험 (Animal study)\n2. 소아 대상 (Under 18 years old)\n3. 리뷰 논문 (Review article)"

    st.markdown("---")
    include_criteria = st.text_area("🔵 포함 기준 (Inclusion Criteria)", value=default_inc, height=170)
    exclude_criteria = st.text_area("🔴 제외 기준 (Exclusion Criteria)", value=default_exc, height=170)

# 🌐 PubMed API 조회 함수
def fetch_pubmed_by_pmid(pmid):
    pmid = str(pmid).replace('.0', '').strip()
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None, None, f"NCBI 서버 통신 실패 (코드 {response.status_code})"
        
        root = ET.fromstring(response.content)
        article = root.find('.//Article')
        
        if article is None:
            return None, None, "존재하지 않는 PMID이거나 논문 정보를 찾을 수 없습니다."
            
        title_elem = article.find('.//ArticleTitle')
        title = title_elem.text if title_elem is not None else "제목 없음"
        
        abstract_elems = article.findall('.//AbstractText')
        if not abstract_elems:
            return title, None, "초록(Abstract)이 없는 문헌입니다."
            
        abstract_text = " ".join([elem.text for elem in abstract_elems if elem.text])
        return title, abstract_text, "성공"
        
    except Exception as e:
        return None, None, f"데이터 파싱 에러: {str(e)}"

# 탭 구성
tab1, tab2 = st.tabs(["🔢 단일 PMID 입력", "📁 PMID 리스트 CSV 업로드"])

# --------------------------------------------------
# TAB 1: 단일 PMID 테스트
# --------------------------------------------------
with tab1:
    single_pmid = st.text_input("PubMed PMID 번호를 입력하세요 (예: 31234567)")
    if st.button("단일 PMID 스크리닝 실행"):
        if not api_key:
            st.error("❌ API Key가 설정되지 않았습니다! 사이드바에서 키를 입력하거나 Secrets를 확인해 주세요.")
        elif not single_pmid:
            st.error("❌ PMID 번호를 입력해 주세요!")
        else:
            with st.spinner("PubMed 공식 API에서 논문 정보 조회 중..."):
                title, abstract_text, status = fetch_pubmed_by_pmid(single_pmid)
                
            if not abstract_text:
                st.error(f"❌ 데이터 조회 실패: {status}")
            else:
                st.success(f"📌 **논문 제목:** {title}")
                st.info(f"📄 **초록 내용:**\n{abstract_text[:400]}...")
                
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(model_code)
                
                prompt = f"""
                너는 임상평가(CER) 전문가야. 아래 논문 초록을 읽고 선택된 카테고리의 포함기준과 제외기준을 평가해 판정해 줘.

                [선택된 카테고리/분류]: {due_category}

                [판정 규칙]:
                1. [포함기준]을 만족하고, [제외기준]에 하나도 해당하지 않는 경우만 'Include'로 판정한다.
                2. [포함기준]을 만족하지 못하거나, [제외기준]에 하나라도 해당하는 경우 'Exclude'로 판정한다.

                [포함기준]:
                {include_criteria}

                [제외기준]:
                {exclude_criteria}

                [논문 제목]: {title}
                [논문 초록]: {abstract_text}

                답변형식:
                판정: (Include 또는 Exclude)
                사유: (포함/제외 기준 중 어떤 조건 때문인지 구체적 사유 및 근거 작성)
                """
                
                try:
                    res = model.generate_content(prompt)
                    st.success("AI 스크리닝 판정 완료!")
                    st.markdown(res.text)
                except Exception as e:
                    if "429" in str(e):
                        st.error("⏳ 해당 모델 사용량이 초과되었습니다. 사이드바에서 다른 모델로 변경해 보세요!")
                    else:
                        st.error(f"AI 통신 에러 발생: {str(e)}")

# --------------------------------------------------
# TAB 2: CSV 파일 PMID 일괄 스크리닝
# --------------------------------------------------
with tab2:
    uploaded_file = st.file_uploader("PMID가 적힌 CSV 업로드 ('PMID' 열 필수)", type=['csv'])
    if st.button("PMID 일괄 스크리닝 실행"):
        if not api_key:
            st.error("❌ API Key가 설정되지 않았습니다! 사이드바에서 키를 입력하거나 Secrets를 확인해 주세요.")
        elif not uploaded_file:
            st.error("❌ CSV 파일을 업로드해 주세요!")
        else:
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8')
            except:
                df = pd.read_csv(uploaded_file, encoding='cp949')

            if 'PMID' not in df.columns:
                st.error("CSV 파일 안에 'PMID' 라는 이름의 열(Column)이 있어야 합니다.")
            else:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(model_code)
                
                titles = []
                abstracts = []
                results = []
                reasons = []
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                total = len(df)
                
                for idx, row in df.iterrows():
                    pmid = str(row['PMID']).replace('.0', '').strip()
                    status_text.text(f"[{idx+1}/{total}] PubMed API 데이터 수집 및 분석 중... PMID: {pmid}")
                    
                    title, abs_text, status = fetch_pubmed_by_pmid(pmid)
                    
                    if not abs_text:
                        titles.append(title if title else "조회 실패")
                        abstracts.append(status)
                        results.append("Error")
                        reasons.append(status)
                    else:
                        titles.append(title)
                        abstracts.append(abs_text[:150] + "...")
                        
                        prompt = f"""
                        너는 임상평가(CER) 전문가야. 아래 논문 초록을 읽고 선택된 카테고리의 포함기준과 제외기준을 평가해 판정해 줘.

                        [선택된 카테고리/분류]: {due_category}

                        [판정 규칙]:
                        1. [포함기준]을 만족하고, [제외기준]에 하나도 해당하지 않는 경우만 'Include'로 판정한다.
                        2. [포함기준]을 만족하지 못하거나, [제외기준]에 하나라도 해당하는 경우 'Exclude'로 판정한다.

                        [포함기준]:
                        {include_criteria}

                        [제외기준]:
                        {exclude_criteria}

                        [논문 제목]: {title}
                        [논문 초록]: {abs_text}

                        답변형식:
                        판정: (Include 또는 Exclude)
                        사유: (포함/제외 기준 중 어떤 조건 때문인지 구체적 사유 작성)
                        """
                        try:
                            res = model.generate_content(prompt)
                            ans = res.text
                            results.append("Include (포함)" if "Include" in ans and "Exclude" not in ans.split("판정:")[1] else "Exclude (제외)")
                            reasons.append(ans.split("사유:")[-1].strip() if "사유:" in ans else ans)
                        except Exception as e:
                            results.append("Error")
                            if "429" in str(e):
                                reasons.append("할당량 초과 (다른 모델 선택 추천)")
                            else:
                                reasons.append(f"AI 통신 에러: {str(e)}")
                    
                    progress_bar.progress((idx + 1) / total)
                    time.sleep(4.0)
                
                df['논문 제목'] = titles
                df['초록 요약'] = abstracts
                df['AI 판정'] = results
                df['상세 사유'] = reasons
                
                st.success(f"[{due_category}] PMID 기반 일괄 스크리닝이 완료되었습니다!")
                st.dataframe(df)
                
                csv_data = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 스크리닝 결과 CSV 다운로드",
                    data=csv_data,
                    file_name="cer_screening_result.csv",
                    mime="text/csv"
                )
