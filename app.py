import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests
import xml.etree.ElementTree as ET
import time

st.set_page_config(page_title="AI 문헌 스크리닝", layout="wide")
st.title("PubMed PMID 기반 문헌 스크리닝 시스템")

# --------------------------------------------------
# ⚙️ 사이드바: API Key 및 DUE 분류 설정
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
    st.subheader("📋 품목 선택")
    
    # st.radio를 사용하여 한 행에 하나씩 세로로 출력
    due_category = st.radio(
        "스크리닝할 카테고리를 선택하세요",
        options=[
            "1. Biliary Stent",
            "2. Esophageal Stent",
            "3. Pyloric/Duodenal Stent",
            "4. Colonic Stent",
            "5. Drainage Stent"
        ],
        index=None  # 핵심: 처음에 아무것도 선택되지 않음
    )

    # 아무것도 선택되지 않았을 때의 예외 처리 (에러 방지)
    if not due_category:
        st.info("👆 위에서 스크리닝할 카테고리를 먼저 선택해 주세요.")
        st.stop() # 카테고리를 선택하기 전까지 아래 코드는 실행하지 않음
    
    # UI에 보여주지 않고 내부 프롬프트용으로만 사용하는 상세 기준 데이터
    if due_category == "1. Biliary Stent":
        default_inc = """1. Text availability: Full text / Original articles
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Malignant biliary obstruction/stricture, Benign biliary obstruction/stricture (Covered types only), Benign pancreatic duct stricture (Niti-S Bumpy type only)
5. Intervention: Biliary SEMS (Uncovered or Covered). Specific Taewoong Medical models: Niti-S (S, D, M, LCD, Full Covered, Both Bare, Giobor, Flare, Kaffes, Bumpy), ComVi (Full Covered, Both Bare, End Bare)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (e.g., WallFlex, Evolution, EGIS, Bonastent, Hanarostent)
7. Outcomes: Stent patency, Decreased bilirubin, Technical/Clinical success, Complications, Stent removal (for benign cases)"""
        default_exc = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-biliary/pancreatic target areas only (e.g., vascular, esophageal, colonic, tracheal)
3. Irrelevant articles: Articles not related to biliary/pancreatic luminal stenting or stricture management
4. Non-study publications: Editorials, letters, comments"""

    elif due_category == "2. Esophageal Stent":
        default_inc = """1. Text availability: Full text / Original articles
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Esophageal stricture/obstruction (Malignant or Benign), Refractory benign esophageal stricture, Tracheoesophageal fistula (TEF / TE fistula)
5. Intervention: Esophageal SEMS, Covered type. Specific Taewoong Medical models: Niti-S Esophageal (Full covered, Cervical, Both bare type, Conio, Anti reflux, Double anti reflux, Double type, Beta-2)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (WallFlex, Ultraflex, Evolution, Hanarostent, Aixstent, EGIS, Bonastent, Micro-Tech)
7. Outcomes: Stent patency, Dysphagia improvement, Fistula closure, Removal (in benign strictures)"""
        default_exc = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-esophageal target areas only (e.g., pure biliary, colonic, duodenal, vascular)
3. Irrelevant articles: Articles not related to esophageal stenting, stricture dilation, or TE fistula management
4. Non-study publications: Editorials, letters, comments"""

    elif due_category == "3. Pyloric/Duodenal Stent":
        default_inc = """1. Text availability: Full text / Original articles
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Pyloric/Duodenal stricture or obstruction, Gastric Outlet Obstruction (GOO), Malignant or Benign (for Covered types)
5. Intervention: Pyloric/Duodenal SEMS, Uncovered or Covered type. Specific Taewoong Medical models: Niti-S Pyloric/Duodenal (D-Type, Full Covered, Both Bare, End Bare), ComVi Pyloric/Duodenal (Flare-Type, Both Bare)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (WallFlex, WallFlex Soft, Hanarostent, Evolution, EGIS, Bonastent)
7. Outcomes: Stent patency, Obstruction relief/resolution/improvement, GOOSS score / Oral intake, Technical/Clinical success, Complications, Stent removal (for benign strictures)"""
        default_exc = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-pyloric/duodenal target areas only (e.g., pure biliary, esophageal, colonic, or vascular stents without duodenal/gastric outlet involvement)
3. Irrelevant articles: Articles not related to pyloric/duodenal stenting or GOO management
4. Non-study publications: Editorials, letters, comments"""

    elif due_category == "4. Colonic Stent":
        default_inc = """1. Text availability: Full text / Original articles
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Colonic/Colorectal stricture or obstruction (Malignant or Benign for Covered types)
5. Intervention: Colonic SEMS, Uncovered or Covered type. Specific Taewoong Medical models: Niti-S Enteral Colonic (S-Type, D-Type, Full Covered, Both Bare, End Bare), ComVi Enteral Colonic (Both Bare-Type)
6. Comparators: Surgery, Plastic stent, Balloon dilation, or competitor SEMS (WallFlex, WallFlex Soft, Hanarostent, Micro-Tech, Bonastent)
7. Outcomes: Stent patency, Obstruction relief/resolution/improvement, Technical/Clinical success, Complications, Stent removal (for benign strictures)"""
        default_exc = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication: Non-colonic target areas only (e.g., pure biliary, esophageal, pyloric/duodenal, or vascular stents without colonic/colorectal involvement)
3. Irrelevant articles: Articles not related to colonic stenting or colorectal obstruction management
4. Non-study publications: Editorials, letters, comments"""

    elif due_category == "5. Drainage Stent":
        default_inc = """1. Text availability: Full text / Original articles
2. Species: Human (not animal, artificial simulation)
3. Patient population: Adult patients, irrespective of gender
4. Clinical Conditions: Pancreatic pseudocyst, Walled-off necrosis (WON) / Pancreatic necrosis, Gallbladder drainage (Cholecystitis) / Biliary tract drainage, Transgastric or transduodenal drainage indications
5. Intervention: Lumen-apposing metal stents (LAMS) or EUS-guided drainage stents. Specific Taewoong Medical models: Niti-S Nagi, Niti-S SPAXUS, Niti-S Hot SPAXUS (Electrocautery Delivery System)
6. Comparators: Surgery, Percutaneous drainage, Plastic double-pigtail stents, or competitor LAMS (e.g., AXIOS / Hot AXIOS)
7. Outcomes: Technical/Clinical success rate, Drainage efficacy, Resolution of pseudocyst/necrosis, Complications (Bleeding, Stent migration, Perforation, Occlusion), Removal rate"""
        default_exc = """1. Species: Not human beings (animal test, artificial simulation, in vitro test)
2. Different indication/Irrelevant: Non-drainage target indications or vascular/intraluminal stenting without transluminal/EUS drainage purpose
3. Non-study publications: Editorials, letters, comments"""

    else:
        default_inc = "1. 대상 환자군 조건 입력\n2. 임상 평가 목적 입력\n3. 개입(Intervention) 및 대조군(Comparator) 설정"
        default_exc = "1. 동물 실험 (Animal test, artificial simulation, in vitro test)\n2. 상관없는 적응증 또는 다른 타겟 부위"

    # UI 노출용 st.text_area를 제거하고 내부 변수로 바로 매핑
    include_criteria = default_inc
    exclude_criteria = default_exc

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

# --------------------------------------------------
# 공통 프롬프트 생성 함수
# --------------------------------------------------
def generate_prompt(due_category, include_criteria, exclude_criteria, title, abstract_text):
    return f"""
    너는 임상평가(CER) 전문가야. 아래 논문 초록을 읽고 선택된 카테고리의 포함기준과 제외기준을 평가해 판정해 줘.

    [선택된 카테고리/분류]: {due_category}

    [판정 규칙]:
    1. [포함기준]을 모두 만족하고, [제외기준]에 하나도 해당하지 않는 경우만 'Include'로 판정한다.
    2. [포함기준]을 하나라도 만족하지 못하거나, [제외기준]에 하나라도 해당하는 경우 'Exclude'로 판정한다.

    [포함기준]:
    {include_criteria}

    [제외기준]:
    {exclude_criteria}

    [논문 제목]: {title}
    [논문 초록]: {abstract_text}

    답변형식 (반드시 아래 형식을 그대로 지켜서 작성할 것):
    판정: (Include 또는 Exclude)
    사유:
    (항목별로 반드시 줄바꿈(엔터)을 하여 한 줄씩 보기 좋게 작성)

    **Conclusion**
    (이곳에 영어로 최종 결론 요약 작성 - 아래 가이드 필수 준수)

    [사유 및 Conclusion 작성 가이드 - 매우 중요!]
    1. 사유 (한국어 설명 부분):
       - "기준 4", "제외기준 2", "- 1" 같은 **번호나 숫자는 절대 표기하지 마라.**
       - 각 사유의 항목명은 반드시 **볼드 처리(**)**하여 작성할 것. (예시: "**적응증 (Clinical Conditions):** ...", "**중재시술 (Intervention):** ...")
       - 각 사유는 한 줄에 하나씩 나타나도록 반드시 줄바꿈(Enter)을 명확하게 넣어라.
    
    2. Conclusion (영어 요약 부분):
       - 맨 마지막에 **Conclusion** 이라고 볼드 처리하여 적고, 그 다음 줄에 영어(English)로 한 문장 작성한다.
       - 판정이 'Include'인 경우: 논문이 포함된 핵심 이유를 자연스러운 영어 문장으로 작성.
       - 판정이 'Exclude'인 경우: 제외된 핵심 이유를 반드시 아래 4가지 [배제 해당사항] 중 가장 적절한 하나를 골라 "**배제해당사항:** 영어 문장" 형식으로 작성할 것. (이 때도 배제해당사항 이름은 볼드 처리)
         * **Different indication:**
         * **Irrelevant article:**
         * **Insufficient information:**
         * **Literature without human clinical data:**
         (작성 예시: **Different indication:** The study concerns WON drainage for pancreatic and peripheral diseases, and corresponds to a study on a non-esophageal target area.)
    """

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
                model = genai.GenerativeModel("gemini-3.6-flash") 
                
                prompt = generate_prompt(due_category, include_criteria, exclude_criteria, title, abstract_text)
                
                try:
                    res = model.generate_content(prompt)
                    st.success("AI 스크리닝 판정 완료!")
                    st.markdown(res.text)
                except Exception as e:
                    if "429" in str(e):
                        st.warning("⏳ 무료 일일 사용량(Quota) 초과 에러입니다. 구글 AI Studio에서 결제 수단(Pay-as-you-go)을 등록하시거나 대기시간 후 재시도해 주세요.")
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
                model = genai.GenerativeModel("gemini-3.6-flash") 
                
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
                        
                        prompt = generate_prompt(due_category, include_criteria, exclude_criteria, title, abs_text)
                        
                        try:
                            res = model.generate_content(prompt)
                            ans = res.text
                            results.append("Include (포함)" if "Include" in ans and "Exclude" not in ans.split("판정:")[1] else "Exclude (제외)")
                            reasons.append(ans.split("사유:")[-1].strip() if "사유:" in ans else ans)
                        except Exception as e:
                            results.append("Error")
                            if "429" in str(e):
                                reasons.append("일일 무료 한도 초과")
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
