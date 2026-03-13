import streamlit as st
import pandas as pd
import numpy as np
import datetime
import json
import plotly.express as px
from sklearn.preprocessing import MinMaxScaler
from google import genai
from streamlit_gsheets import GSheetsConnection
from sqlalchemy import create_engine, text

# --- 1. CẤU HÌNH GIAO DIỆN WEB ---
st.set_page_config(page_title="LFS - Trợ lý Bất động sản", page_icon="🏡", layout="wide")

# ==========================================
# HỆ THỐNG BẢO MẬT: MÀN HÌNH ĐĂNG NHẬP
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

VALID_USER = "admin"
VALID_PASS = "faraland"

if not st.session_state['logged_in']:
    st.markdown("<h1 style='text-align: center;'>🔐 Hệ thống Quản trị LFS</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Vui lòng đăng nhập để truy cập dữ liệu nội bộ Faraland.</p>", unsafe_allow_html=True)
    
    col_login1, col_login2, col_login3 = st.columns([1, 1, 1])
    with col_login2:
        with st.form("login_form"):
            username = st.text_input("Tài khoản:")
            password = st.text_input("Mật khẩu:", type="password")
            submit_login = st.form_submit_button("Đăng nhập")
            
            if submit_login:
                if username == VALID_USER and password == VALID_PASS:
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("❌ Sai tài khoản hoặc mật khẩu!")
                    
# ==========================================
# GIAO DIỆN HỆ THỐNG CHÍNH
# ==========================================
else:
    st.title("🏡 Hệ thống LFS 10.0 - Trợ lý Ảo AI Toàn Diện")
    st.markdown("Dashboard điều hành, AI Khớp lệnh, Quản lý CRM & AI Gợi ý giao tiếp Zalo.")

    # --- NÚT ĐĂNG XUẤT ---
    st.sidebar.markdown("### 👤 Tài khoản: Admin")
    if st.sidebar.button("🚪 Đăng xuất"):
        st.session_state['logged_in'] = False
        st.rerun()
    st.sidebar.divider()

    # --- 2. CẤU HÌNH DỮ LIỆU ---
    st.sidebar.header("🔑 Cấu hình Hệ thống")
    api_key = st.sidebar.text_input("1. Gemini API Key:", type="password")
    sheet_url = st.sidebar.text_input("2. Link Google Sheets (Kho Hàng):", type="password")
    db_url = st.sidebar.text_input("3. Supabase URI (Lưu CRM):", type="password")

    # ==========================================
    def clean_currency(x):
        if pd.isna(x): return np.nan
        s = str(x).lower().replace(' ', '')
        multiplier = 1
        if 'tỷ' in s or 'ty' in s:
            multiplier = 1_000_000_000
            s = s.replace('tỷ', '').replace('ty', '')
        elif 'triệu' in s or 'trieu' in s:
            multiplier = 1_000_000
            s = s.replace('triệu', '').replace('trieu', '')
        s = s.replace(',', '.') 
        if s.count('.') > 1: s = s.replace('.', '')
        try:
            val = float(s) * multiplier
            if val > 0 and val < 1000: val = val * 1_000_000_000
            return val
        except:
            return np.nan

    def clean_area(x):
        if pd.isna(x): return np.nan
        s = str(x).lower().replace('m2', '').replace(' ', '').replace(',', '.')
        try:
            return float(s)
        except:
            return np.nan
    # ==========================================

    # --- 3. ĐỌC KHO HÀNG ---
    @st.cache_data(ttl=60) 
    def load_data_from_sheets(url):
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=url)
        df.columns = df.columns.str.strip() 
        
        if 'Phường Quận' not in df.columns: df['Phường Quận'] = "Chưa rõ"
        if 'Link ảnh' not in df.columns: df['Link ảnh'] = ""
        if 'Loại nhà' not in df.columns: df['Loại nhà'] = "Chưa phân loại"
        
        df = df.dropna(subset=['Giá bán', 'Diện tích', 'Địa chỉ'])
        df = df.rename(columns={
            'Địa chỉ': 'project_name', 'Giá bán': 'price', 'Diện tích': 'area', 
            'Số tầng': 'bedrooms', 'Loại nhà': 'property_type',
            'Phường Quận': 'district', 'Link ảnh': 'image_url'
        })
        
        df['price'] = df['price'].apply(clean_currency)
        df['area'] = df['area'].apply(clean_area)
        df['bedrooms'] = pd.to_numeric(df['bedrooms'], errors='coerce').fillna(1)
        
        if 'property_type' not in df.columns: df['property_type'] = "Chưa phân loại"
        else: df['property_type'] = df['property_type'].fillna("Chưa phân loại")
            
        return df.dropna(subset=['price', 'area'])

    if sheet_url:
        try:
            properties = load_data_from_sheets(sheet_url)
            st.success(f"✅ Đã kết nối rổ hàng. Quét thành công {len(properties)} sản phẩm.")
            
            # TẠO 3 TAB CHUYÊN NGHIỆP
            tab1, tab2, tab3 = st.tabs(["🚀 Phòng Điều Hành & Khớp Lệnh", "🕵️ Quản Lý Lịch Sử CRM", "💡 AI Gợi Ý Giao Tiếp"])
            
            with tab1:
                # ==========================================
                # PHÒNG ĐIỀU HÀNH: DASHBOARD TỔNG QUAN & BIỂU ĐỒ
                # ==========================================
                st.markdown("### 📊 Tổng quan Giỏ hàng Faraland")
                col_db1, col_db2, col_db3 = st.columns(3)
                with col_db1: st.metric(label="Tổng số Bất động sản", value=f"{len(properties)} căn")
                with col_db2:
                    if len(properties) > 0:
                        avg_price = properties['price'].mean() / 1_000_000_000 
                        st.metric(label="Mức giá trung bình", value=f"{avg_price:.2f} Tỷ VNĐ")
                    else: st.metric(label="Mức giá trung bình", value="0 Tỷ VNĐ")
                with col_db3:
                    if len(properties) > 0: st.metric(label="Phân khúc chủ đạo", value=str(properties['property_type'].mode()[0]))
                    else: st.metric(label="Phân khúc chủ đạo", value="N/A")
                
                # --- VẼ BIỂU ĐỒ VỚI PLOTLY ---
                if len(properties) > 0:
                    st.markdown("<br>", unsafe_allow_html=True)
                    col_chart1, col_chart2 = st.columns(2)
                    
                    with col_chart1:
                        district_counts = properties['district'].value_counts().reset_index()
                        district_counts.columns = ['Quận/Huyện', 'Số lượng']
                        fig_pie = px.pie(district_counts, values='Số lượng', names='Quận/Huyện', 
                                         title='Tỷ trọng Nguồn hàng theo Khu vực',
                                         hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                        st.plotly_chart(fig_pie, use_container_width=True)
                        
                    with col_chart2:
                        type_counts = properties['property_type'].value_counts().reset_index()
                        type_counts.columns = ['Loại BĐS', 'Số lượng']
                        fig_bar = px.bar(type_counts, x='Loại BĐS', y='Số lượng', 
                                         title='Thống kê theo Phân khúc (Loại nhà)',
                                         text_auto=True, color='Loại BĐS',
                                         color_discrete_sequence=px.colors.qualitative.Set2)
                        st.plotly_chart(fig_bar, use_container_width=True)

                st.divider() 

                # ==========================================
                # AI BÓC TÁCH TIN NHẮN TỰ ĐỘNG
                # ==========================================
                st.subheader("🤖 AI Khớp Lệnh Thần Tốc")
                raw_chat = st.text_area("Dán nguyên văn đoạn chat nhu cầu của khách vào đây:", 
                                        placeholder="VD: Em ơi anh Nam đây, anh tìm căn nào quanh Đống Đa tầm 4 củ tỏi đổ lại, rộng xíu cỡ 60m2 nhé, 2 ngủ là ok")
                
                col_btn_ai, col_btn_empty = st.columns([1, 3])
                with col_btn_ai:
                    btn_ai_submit = st.button("✨ Phân Tích & Khớp Lệnh", type="primary")

                st.markdown("<br>", unsafe_allow_html=True)
                
                with st.expander("Hoặc: Nhập thông tin thủ công (Dự phòng)"):
                    with st.form("manual_form"):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            m_name = st.text_input("Tên khách hàng:", "Khách hàng")
                            district_list = ["Bất kỳ"] + [d for d in properties['district'].unique() if str(d).strip() != "" and str(d) != "nan"]
                            m_district = st.selectbox("Khu vực ưu tiên:", district_list)
                        with col2:
                            m_budget = st.number_input("Ngân sách (VNĐ):", min_value=1000000000, value=3000000000, step=100000000)
                            m_area = st.number_input("Diện tích tối thiểu (m2):", min_value=30.0, value=50.0, step=1.0)
                        with col3:
                            m_bedrooms = st.number_input("Số phòng tối thiểu:", min_value=1, value=2, step=1)
                        btn_manual_submit = st.form_submit_button("Khớp Lệnh Thủ Công")

                # ==========================================
                # LOGIC XỬ LÝ KHỚP LỆNH
                # ==========================================
                if btn_ai_submit or btn_manual_submit:
                    if not api_key or not db_url:
                        st.warning("⚠️ Vui lòng nhập đủ Gemini API Key và Supabase URI ở menu trái!")
                    elif len(properties) == 0:
                        st.error("Rổ hàng trống.")
                    else:
                        with st.spinner("Đang kích hoạt AI để phân tích và matching..."):
                            if btn_ai_submit:
                                if not raw_chat:
                                    st.error("Vui lòng dán tin nhắn của khách vào ô trống!")
                                    st.stop()
                                
                                client = genai.Client(api_key=api_key)
                                prompt_json = f"""
                                Bạn là trợ lý trích xuất dữ liệu. Đọc tin nhắn và trích xuất thành 1 ĐỊNH DẠNG JSON duy nhất:
                                {{
                                  "name": "Tên khách hàng",
                                  "district": "Quận/Khu vực. Ghi 'Bất kỳ' nếu không rõ",
                                  "budget": Ngân sách tối đa ra số nguyên VNĐ (VD: 4 tỷ -> 4000000000. Mặc định 3000000000),
                                  "area": Diện tích bằng số (Mặc định 30.0),
                                  "bedrooms": Số phòng ngủ (Mặc định 1)
                                }}
                                TIN NHẮN: "{raw_chat}"
                                """
                                try:
                                    response_json = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_json)
                                    clean_json = response_json.text.replace('```json', '').replace('```', '').strip()
                                    extracted_data = json.loads(clean_json)
                                    
                                    cust_name = extracted_data.get("name", "Khách hàng")
                                    cust_district = extracted_data.get("district", "Bất kỳ")
                                    cust_budget = int(extracted_data.get("budget", 3000000000))
                                    cust_area = float(extracted_data.get("area", 30.0))
                                    cust_bedrooms = int(extracted_data.get("bedrooms", 1))
                                    
                                    st.success(f"**🤖 AI bóc tách dữ liệu:** Tên: **{cust_name}** | Khu vực: **{cust_district}** | Ngân sách: **{cust_budget:,.0f}đ** | **{cust_area}**m2 | **{cust_bedrooms}**PN")
                                except Exception as e:
                                    st.error("AI không thể phân tích tin nhắn này. Hãy thử nhập lại cho rõ nghĩa hơn hoặc dùng Form nhập tay.")
                                    st.stop()
                            else:
                                cust_name = m_name
                                cust_district = m_district
                                cust_budget = m_budget
                                cust_area = m_area
                                cust_bedrooms = m_bedrooms

                            # --- MATCHING ---
                            customer_req = pd.DataFrame({'budget': [cust_budget], 'area': [cust_area], 'bedrooms': [cust_bedrooms], 'district': [cust_district]})
                            all_prices = np.append(properties['price'].values, customer_req['budget'].values).reshape(-1, 1)
                            all_areas = np.append(properties['area'].values, customer_req['area'].values).reshape(-1, 1)
                            scaler_price = MinMaxScaler().fit(all_prices)
                            scaler_area = MinMaxScaler().fit(all_areas)

                            def calculate_match_score(house, customer):
                                score = 100 
                                if customer['district'][0] != "Bất kỳ":
                                    if str(house['district']).lower() in str(customer['district'][0]).lower() or str(customer['district'][0]).lower() in str(house['district']).lower(): 
                                        score += 50 
                                    else: 
                                        score -= 30 
                                        
                                house_price_norm = scaler_price.transform([[house['price']]])[0][0]
                                cust_budget_norm = scaler_price.transform([[customer['budget'][0]]])[0][0]
                                price_diff = house_price_norm - cust_budget_norm
                                budget_diff_vnd = house['price'] - customer['budget'][0]
                                
                                if budget_diff_vnd > 1000000000: score -= (price_diff * 50) 
                                elif 0 < budget_diff_vnd <= 1000000000: score -= (price_diff * 5)  
                                else: score += (abs(price_diff) * 10) 
                                    
                                house_area_norm = scaler_area.transform([[house['area']]])[0][0]
                                cust_area_norm = scaler_area.transform([[customer['area'][0]]])[0][0]
                                score -= (abs(house_area_norm - cust_area_norm) * 20) 
                                
                                if house['bedrooms'] < customer['bedrooms'][0]: score -= 30 
                                return max(0, round(score, 2)) 

                            properties['match_score'] = properties.apply(lambda row: calculate_match_score(row, customer_req), axis=1)
                            best_match = properties.sort_values(by='match_score', ascending=False).iloc[0]

                            # --- LƯU CRM SUPABASE ---
                            crm_saved = False
                            try:
                                engine_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
                                engine = create_engine(engine_url)
                                new_crm_record = pd.DataFrame([{
                                    "thoi_gian": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "ten_khach_hang": cust_name,
                                    "khu_vuc_tim_kiem": cust_district,
                                    "ngan_sach": f"{cust_budget:,.0f} VNĐ",
                                    "nhu_cau_chi_tiet": f"{cust_area}m2, {cust_bedrooms}PN",
                                    "can_ho_de_xuat": best_match['project_name'],
                                    "do_phu_hop": f"{best_match['match_score']}%"
                                }])
                                new_crm_record.to_sql('crm_khach_hang', engine, if_exists='append', index=False)
                                crm_saved = True
                            except Exception as e:
                                st.error("Lỗi lưu CRM vào Supabase.")

                            # --- KỊCH BẢN CHỐT ---
                            client = genai.Client(api_key=api_key)
                            prompt = f"""
                            Viết tin nhắn Zalo gửi {cust_name}. Người gửi là Đạt, môi giới bất động sản.
                            Thông tin: Khách tìm nhà {cust_budget:,.0f} VNĐ. Đang có căn {best_match['project_name']} (Khu vực: {best_match['district']}) phù hợp.
                            YÊU CẦU: Tối đa 3 câu. KHÔNG nhắc con số giá tiền. Phải có từ khóa kích thích khan hiếm/cơ hội. Rủ đi xem ngay.
                            """
                            response_zalo = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)

                            # --- HIỂN THỊ KẾT QUẢ ---
                            st.success("🎉 Khớp lệnh thành công!")
                            if crm_saved: st.info("☁️ Đã sao lưu hồ sơ khách hàng vào Supabase!")
                            
                            col_img, col_res, col_msg = st.columns([1.5, 1.5, 2])
                            with col_img:
                                st.write("**📸 Hình ảnh thực tế:**")
                                if pd.notna(best_match['image_url']) and str(best_match['image_url']).strip() != "":
                                    img_val = str(best_match['image_url']).strip()
                                    if img_val.startswith("http"):
                                        st.image(img_val, use_container_width=True)
                                    else:
                                        st.warning("⚠️ Vui lòng up ảnh lên Web (Drive/Imgur) thay vì thư mục máy tính để hiển thị.")
                                else:
                                    st.info("Chưa có hình ảnh.")
                                    
                            with col_res:
                                st.write(f"**🏠 Căn hộ chốt:** {best_match['project_name']}")
                                st.write(f"- **Khu vực:** {best_match['district']}")
                                st.write(f"- **Độ phù hợp:** {best_match['match_score']}%")
                                st.write(f"- **Giá nội bộ:** {best_match['price']:,.0f} VNĐ")
                                st.write(f"- **Diện tích:** {best_match['area']} m2")
                                
                            with col_msg:
                                st.write("**📱 Tin nhắn Zalo:**")
                                st.text_area("", response_zalo.text, height=150, label_visibility="collapsed")
                            
            # ========================================================
            # TAB 2: QUẢN LÝ LỊCH SỬ CRM & XÓA DỮ LIỆU
            # ========================================================
            with tab2:
                st.subheader("🕵️ Tra cứu lịch sử tư vấn / xem nhà")
                search_name = st.text_input("Nhập tên khách hàng cần tra cứu (VD: Anh Nguyễn Văn A):", key="search_crm")
                
                if st.button("Tra cứu Dữ liệu"):
                    if not db_url: st.warning("Vui lòng nhập Supabase URI ở menu bên trái!")
                    elif not search_name: st.warning("Vui lòng nhập tên khách hàng.")
                    else:
                        with st.spinner("Đang truy xuất Database..."):
                            try:
                                engine_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
                                engine = create_engine(engine_url)
                                query = f"SELECT thoi_gian, can_ho_de_xuat, ngan_sach, do_phu_hop FROM crm_khach_hang WHERE ten_khach_hang ILIKE '%%{search_name}%%' ORDER BY thoi_gian DESC"
                                history_df = pd.read_sql(query, engine)

                                if not history_df.empty:
                                    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                                    history_df['Ngày'] = pd.to_datetime(history_df['thoi_gian']).dt.strftime('%Y-%m-%d')
                                    today_df = history_df[history_df['Ngày'] == today_str]
                                    
                                    st.success(f"Đã tìm thấy **{len(history_df)}** lần tư vấn cho khách hàng này.")
                                    st.markdown(f"### 📍 Các căn nhà đã xem HÔM NAY ({today_str}):")
                                    if not today_df.empty: st.dataframe(today_df[['thoi_gian', 'can_ho_de_xuat', 'ngan_sach', 'do_phu_hop']], use_container_width=True)
                                    else: st.info("Hôm nay khách chưa có lịch sử khớp lệnh mới.")
                                        
                                    st.markdown("### 🗓️ Lịch sử các ngày trước:")
                                    past_df = history_df[history_df['Ngày'] != today_str]
                                    if not past_df.empty: st.dataframe(past_df[['thoi_gian', 'can_ho_de_xuat', 'ngan_sach', 'do_phu_hop']], use_container_width=True)
                                    else: st.write("Không có dữ liệu cũ.")
                                else:
                                    st.warning("Chưa tìm thấy dữ liệu hoặc khách chưa từng được tư vấn.")
                            except Exception as e:
                                st.error("Lỗi truy xuất dữ liệu từ Supabase.")
                
                st.divider()
                st.markdown("### 🗑️ Xóa Hồ Sơ Khách Hàng")
                del_name = st.text_input("Nhập CHÍNH XÁC tên khách hàng cần xóa:")
                if st.button("🚨 Xóa Vĩnh Viễn Dữ Liệu"):
                    if not db_url: st.warning("Vui lòng nhập Supabase URI!")
                    elif not del_name: st.warning("Vui lòng nhập tên khách hàng.")
                    else:
                        with st.spinner(f"Đang xóa hồ sơ của {del_name}..."):
                            try:
                                engine_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
                                engine = create_engine(engine_url)
                                with engine.begin() as conn:
                                    sql = text("DELETE FROM crm_khach_hang WHERE ten_khach_hang = :name")
                                    result = conn.execute(sql, {"name": del_name})
                                    deleted_rows = result.rowcount
                                if deleted_rows > 0: st.success(f"✅ Đã xóa thành công {deleted_rows} dòng dữ liệu của khách '{del_name}'!")
                                else: st.info("Không tìm thấy dữ liệu nào khớp với tên này.")
                            except Exception as e:
                                st.error("Lỗi khi xóa dữ liệu.")

            # ========================================================
            # TAB 3: AI XỬ LÝ TỪ CHỐI & GỢI Ý GIAO TIẾP
            # ========================================================
            with tab3:
                st.subheader("💡 AI Xử Lý Từ Chối & Gợi Ý Trả Lời Khách Hàng")
                st.markdown("Khách chê giá cao? Khách đòi hỏi giấy tờ rườm rà? Khách 'seen' không rep? Hãy dán tin nhắn vào đây để AI viết câu trả lời giúp bạn!")
                
                cust_msg = st.text_area("1. Khách hàng vừa nhắn gì cho bạn?", placeholder="VD: Em ơi giá 4 tỷ này hơi cao, bớt cho anh 500 triệu nhé được anh qua cọc luôn.")
                agent_intent = st.text_input("2. Ý định trả lời của bạn (Tùy chọn):", placeholder="VD: Giải thích căn này lô góc rất hiếm, chủ chỉ bớt lộc lá 50 triệu thôi.")
                
                if st.button("✨ Viết Câu Trả Lời Giúp Tôi", type="primary"):
                    if not api_key:
                        st.warning("Vui lòng nhập Gemini API Key ở menu bên trái trước!")
                    elif not cust_msg:
                        st.warning("Bạn chưa dán tin nhắn của khách kìa!")
                    else:
                        with st.spinner("AI đang soạn văn mẫu chốt sale đỉnh cao..."):
                            client = genai.Client(api_key=api_key)
                            prompt_reply = f"""
                            Bạn là Đạt, một siêu sao môi giới bất động sản tại công ty Faraland (Việt Nam), chuyên chốt sale qua Zalo.
                            Khách hàng vừa nhắn tin: "{cust_msg}"
                            Định hướng trả lời của tôi (nếu có): "{agent_intent}"

                            Nhiệm vụ: Viết một tin nhắn Zalo phản hồi lại khách hàng để tôi copy gửi luôn.
                            Yêu cầu:
                            - Cực kỳ khéo léo, thấu hiểu tâm lý khách hàng (xử lý từ chối mượt mà).
                            - Văn phong tự nhiên, lễ phép nhưng chuyên nghiệp, có dùng emoji Zalo vừa phải.
                            - Ngắn gọn, súc tích, đi thẳng vào vấn đề.
                            - Kết thúc bằng một lời đề nghị hành động (Call to action) để dẫn dắt khách đi xem nhà hoặc chốt cọc.
                            """
                            try:
                                reply_response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_reply)
                                st.success("Ting ting! Có ngay văn mẫu xịn sò cho bạn:")
                                st.text_area("Sao chép đoạn dưới đây và gửi Zalo ngay:", reply_response.text, height=250)
                            except Exception as e:
                                st.error("Lỗi kết nối AI. Vui lòng thử lại.")
                                st.write(e)

        except Exception as e:
            st.error("❌ Lỗi dữ liệu Kho Hàng.")
