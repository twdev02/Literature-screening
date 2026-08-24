# --------------------------------------------------
# 📊 Excel(.xlsx) 변환 헬퍼 함수 (유니코드 폰트 깨짐 완전 방지)
# --------------------------------------------------
def convert_df_to_excel(df_input):
    import io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import dataframe_to_rows

    # 유니코드 특수 문자를 표준 일반 영문으로 원복
    bold_reverse_map = {
        '𝐀': 'A', '𝐁': 'B', '𝐂': 'C', '𝐃': 'D', '𝐄': 'E', '𝐅': 'F', '𝐆': 'G', '𝐇': 'H', '𝐈': 'I', '𝐉': 'J', '𝐊': 'K', '𝐋': 'L', '𝐌': 'M', '𝐍': 'N', '𝐎': 'O', '𝐏': 'P', '𝐐': 'Q', '𝐑': 'R', '𝐒': 'S', '𝐓': 'T', '𝐔': 'U', '𝐕': 'V', '𝐖': 'W', '𝐗': 'X', '𝐘': 'Y', '𝐙': 'Z',
        '𝐚': 'a', '𝐛': 'b', '𝐜': 'c', '𝐝': 'd', '𝐞': 'e', '𝐟': 'f', '𝐠': 'g', '𝐡': 'h', '𝐢': 'i', '𝐣': 'j', '𝐤': 'k', '𝐥': 'l', '𝐦': 'm', '𝐧': 'n', '𝐨': 'o', '𝐩': 'p', '𝐪': 'q', '𝐫': 'r', '𝐬': 's', '𝐭': 't', '𝐮': 'u', '𝐯': 'v', '𝐰': 'w', '𝐱': 'x', '𝐲': 'y', '𝐳': 'z'
    }
    
    df_clean = df_input.copy()
    for col in df_clean.columns:
        if df_clean[col].dtype == 'object':
            df_clean[col] = df_clean[col].astype(str).apply(
                lambda text: "".join(bold_reverse_map.get(c, c) for c in text)
            )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Screening Results"

    for r in dataframe_to_rows(df_clean, index=False, header=True):
        ws.append(r)

    header_fill = PatternFill(start_color="0B1A2D", end_color="0B1A2D", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    body_font = Font(name="Calibri", size=10)
    
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            cell.font = body_font
            cell.border = thin_border
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            
            val_str = str(cell.value or "")
            if val_str.startswith("Include"):
                cell.font = Font(name="Calibri", size=10, bold=True, color="166534")
            elif val_str.startswith("Exclude"):
                cell.font = Font(name="Calibri", size=10, bold=True, color="991B1B")

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 50)

    excel_io = io.BytesIO()
    wb.save(excel_io)
    excel_io.seek(0)
    return excel_io.getvalue()


# MODE 2 결과 출력 구역
if st.session_state["tab2_result"] is not None:
    st.success(f"[{due_category} - {sub_model}] 일괄 스크리닝 결과")
    res_df = st.session_state["tab2_result"]
    render_result_dashboard(res_df)
    pending_df = res_df[res_df["AI 판정"].str.contains("Manual Review Needed|Full-text Screening Needed", na=False)]

    v_tab1, v_tab2 = st.tabs(["전체 스크리닝 결과 보기", f"⚠️ 수동 검토 필요 대상 모아보기 ({len(pending_df)}건)"])
    with v_tab1:
        st.dataframe(res_df, hide_index=True)
        csv_data = res_df.to_csv(index=False).encode("utf-8-sig")
        excel_data = convert_df_to_excel(res_df)
        
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button("📊 전체 결과 Excel(.xlsx) 다운로드", data=excel_data, file_name="cer_screening_result_all.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with col_dl2:
            st.download_button("전체 스크리닝 결과 CSV 다운로드", data=csv_data, file_name="cer_screening_result_all.csv", mime="text/csv", use_container_width=True)
            
    with v_tab2:
        if len(pending_df) == 0: st.info("수동 검토 대상 논문이 없습니다.")
        else:
            st.warning("아래 목록은 PubMed 데이터상 초록이 없고 Open Access가 아니어서 수동 검토가 필요한 문헌들입니다.")
            st.dataframe(pending_df, hide_index=True)
            pending_excel = convert_df_to_excel(pending_df)
            
            col_p_dl1, col_p_dl2 = st.columns(2)
            with col_p_dl1:
                st.download_button("⚠️ 수동 검토 대상 Excel(.xlsx) 다운로드", data=pending_excel, file_name="cer_manual_review_needed.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            with col_p_dl2:
                st.download_button("⚠️ 수동 검토 대상만 CSV 다운로드", data=pending_df.to_csv(index=False).encode("utf-8-sig"), file_name="cer_manual_review_needed.csv", mime="text/csv", use_container_width=True)

# MODE 3 결과 출력 구역
    if st.session_state["tab3_result"] is not None:
        st.success(f"[{due_category} - {sub_model}] PICO 기반 자동 스크리닝 완료 결과")
        res_df = st.session_state["tab3_result"]
        render_result_dashboard(res_df)

        pending_df = res_df[res_df["AI 판정"].str.contains("Manual Review Needed|Full-text Screening Needed", na=False)]
        v_tab1, v_tab2 = st.tabs(["전체 스크리닝 결과 보기", f"⚠️ 수동 검토 필요 대상 모아보기 ({len(pending_df)}건)"])
        with v_tab1:
            st.dataframe(res_df, hide_index=True)
            csv_data = res_df.to_csv(index=False).encode("utf-8-sig")
            excel_data = convert_df_to_excel(res_df)
            
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button("📊 PICO 스크리닝 전체 결과 Excel(.xlsx) 다운로드", data=excel_data, file_name=f"pico_screening_{start_year}{start_month:02d}_{end_year}{end_month:02d}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            with col_dl2:
                st.download_button("PICO 스크리닝 전체 결과 CSV 다운로드", data=csv_data, file_name=f"pico_screening_{start_year}{start_month:02d}_{end_year}{end_month:02d}.csv", mime="text/csv", use_container_width=True)
        with v_tab2:
            if len(pending_df) == 0: st.info("수동 검토 대상 논문이 없습니다.")
            else:
                st.warning("아래 목록은 데이터 부족으로 수동 검토가 필요한 문헌들입니다.")
                st.dataframe(pending_df, hide_index=True)
                pending_excel = convert_df_to_excel(pending_df)
                
                col_p_dl1, col_p_dl2 = st.columns(2)
                with col_p_dl1:
                    st.download_button("⚠️ 수동 검토 대상 Excel(.xlsx) 다운로드", data=pending_excel, file_name=f"pico_manual_review_needed_{start_year}{start_month:02d}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                with col_p_dl2:
                    st.download_button("⚠️ 수동 검토 대상만 CSV 다운로드", data=pending_df.to_csv(index=False).encode("utf-8-sig"), file_name=f"pico_manual_review_needed_{start_year}{start_month:02d}.csv", mime="text/csv", use_container_width=True)

# MODE 4 결과 출력 구역
    if st.session_state["tab_gie_result"] is not None and selected_mode == "GIE RIS 파일 일괄 스크리닝":
        st.success(f"[{due_category} - {sub_model}] GIE RIS 스크리닝 완료 결과")
        res_df = st.session_state["tab_gie_result"]
        render_result_dashboard(res_df)

        pending_df = res_df[res_df["AI 판정"].str.contains("Manual Review Needed|Full-text Screening Needed", na=False)]
        v_tab1, v_tab2 = st.tabs(["전체 스크리닝 결과 보기", f"⚠️ 수동 검토 필요 대상 모아보기 ({len(pending_df)}건)"])
        with v_tab1:
            st.dataframe(res_df, hide_index=True)
            csv_data = res_df.to_csv(index=False).encode("utf-8-sig")
            excel_data = convert_df_to_excel(res_df)
            
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button("📊 GIE 스크리닝 전체 결과 Excel(.xlsx) 다운로드", data=excel_data, file_name="gie_ris_screening_result.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            with col_dl2:
                st.download_button("GIE 스크리닝 전체 결과 CSV 다운로드", data=csv_data, file_name="gie_ris_screening_result.csv", mime="text/csv", use_container_width=True)
        with v_tab2:
            if len(pending_df) == 0: st.info("수동 검토 대상 논문이 없습니다.")
            else:
                st.warning("아래 목록은 GIE RIS 파일 내 데이터 부족으로 수동 검토가 필요한 문헌들입니다.")
                st.dataframe(pending_df, hide_index=True)
                pending_excel = convert_df_to_excel(pending_df)
                
                col_p_dl1, col_p_dl2 = st.columns(2)
                with col_p_dl1:
                    st.download_button("⚠️ 수동 검토 대상 Excel(.xlsx) 다운로드", data=pending_excel, file_name="gie_manual_review_needed.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                with col_p_dl2:
                    st.download_button("⚠️ 수동 검토 대상만 CSV 다운로드", data=pending_df.to_csv(index=False).encode("utf-8-sig"), file_name="gie_manual_review_needed.csv", mime="text/csv", use_container_width=True)

# MODE 5 결과 출력 구역
    if st.session_state.get("tab_ct_result") is not None and selected_mode == "ClinicalTrials 자동 검색":
        st.success(f"[{due_category} - {sub_model}] ClinicalTrials.gov 스크리닝 완료 결과")
        res_df = st.session_state["tab_ct_result"]
        render_result_dashboard(res_df)

        pending_df = res_df[res_df["AI 판정"].str.contains("Manual Review Needed|Full-text Screening Needed", na=False)]
        v_tab1, v_tab2 = st.tabs(["전체 스크리닝 결과 보기", f"⚠️ 수동 검토 필요 대상 모아보기 ({len(pending_df)}건)"])
        with v_tab1:
            st.dataframe(res_df, hide_index=True)
            csv_data = res_df.to_csv(index=False).encode("utf-8-sig")
            excel_data = convert_df_to_excel(res_df)
            
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button("📊 ClinicalTrials 전체 결과 Excel(.xlsx) 다운로드", data=excel_data, file_name="clinicaltrials_screening_result.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            with col_dl2:
                st.download_button("ClinicalTrials 전체 결과 CSV 다운로드", data=csv_data, file_name="clinicaltrials_screening_result.csv", mime="text/csv", use_container_width=True)
        with v_tab2:
            if len(pending_df) == 0: st.info("수동 검토 대상 임상이 없습니다.")
            else:
                st.warning("아래 목록은 Summary 데이터 부족으로 수동 검토가 필요한 임상시험들입니다.")
                st.dataframe(pending_df, hide_index=True)
                pending_excel = convert_df_to_excel(pending_df)
                
                col_p_dl1, col_p_dl2 = st.columns(2)
                with col_p_dl1:
                    st.download_button("⚠️ 수동 검토 대상 Excel(.xlsx) 다운로드", data=pending_excel, file_name="clinicaltrials_manual_review_needed.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                with col_p_dl2:
                    st.download_button("⚠️ 수동 검토 대상만 CSV 다운로드", data=pending_df.to_csv(index=False).encode("utf-8-sig"), file_name="clinicaltrials_manual_review_needed.csv", mime="text/csv", use_container_width=True)
