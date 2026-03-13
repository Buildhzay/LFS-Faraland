import streamlit as st
import pandas as pd
import numpy as np
import datetime
from sklearn.preprocessing import MinMaxScaler
from google import genai
from streamlit_gsheets import GSheetsConnection
from sqlalchemy import create_engine, text

# --- 1. CẤU HÌNH GIAO DIỆN WEB ---
st.set_page_config(page_title="LFS - Trợ lý Bất động sản", page_icon="🏡", layout="wide")
st.title("🏡 Hệ thống LFS 6.0 - Trợ lý Ảo Toàn Diện")
st.markdown("Matching tự động, tạo kịch bản Zalo & Quản lý lịch sử xem nhà trực tuyến.")

# --- 2. CẤU HÌNH BẢO MẬT ---
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
        
        # --- TẠO TAB ĐỂ GIAO DIỆN GỌN GÀNG HƠN ---
        tab1, tab2 = st.tabs(["🎯 Khớp Lệnh & Chốt Sale", "🕵️ Quản Lý Khách Xem Hôm Nay"])
        
        with tab1:
            st.markdown("### 📊 Tổng quan Giỏ hàng")
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
            st.divider() 

            with st.form("customer_form"):
                st.subheader("👤 Hồ Sơ Nhu Cầu Khách Hàng")
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    cust_name = st.text_input("Tên khách hàng:", "Anh Nguyễn Văn A")
                    district_list = ["Bất kỳ"] + [d for d in properties['district'].unique() if str(d).strip() != "" and str(d) != "nan"]
                    cust_district = st.selectbox("Khu vực ưu tiên:", district_list)
                with col2:
                    cust_budget = st.number_input("Ngân sách (VNĐ):", min_value=1000000000, value=3500000000, step=100000000)
                    cust_area = st.number_input("Diện tích tối thiểu (m2):", min_value=30.0, value=65.0, step=1.0)
                with col3:
                    cust_bedrooms = st.number_input("Số phòng tối thiểu:", min_value=1, value=2, step=1)
                    
                submitted = st.form_submit_button("Khớp Lệnh, Lưu CRM Supabase & Tạo Kịch Bản")

            if submitted:
                if not api_key or not db_url:
                    st.warning("⚠️ Vui lòng nhập đủ API Key và Supabase URI!")
                elif len(properties) == 0:
                    st.error("Rổ hàng trống.")
                else:
                    with st.spinner('Đang tính toán matching và lưu CRM...'):
                        customer_req = pd.DataFrame({'budget': [cust_budget], 'area': [cust_area], 'bedrooms': [cust_bedrooms], 'district': [cust_district]})
                        all_prices = np.append(properties['price'].values, customer_req['budget'].values).reshape(-1, 1)
                        all_areas = np.append(properties['area'].values, customer_req['area'].values).reshape(-1, 1)
                        scaler_price = MinMaxScaler().fit(all_prices)
                        scaler_area = MinMaxScaler().fit(all_areas)

                        def calculate_match_score(house, customer):
                            score = 100 
                            if customer['district'][0] != "Bất kỳ":
                                if str(house['district']).lower() == str(customer['district'][0]).lower(): score += 50 
                                else: score -= 30 
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

                        # GHI SUPABASE
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
                            print(e)

                        # SINH AI PROMPT
                        client = genai.Client(api_key=api_key)
                        prompt = f"""
                        Viết tin nhắn Zalo gửi {cust_name}. Người gửi là Đạt, môi giới bất động sản.
                        Thông tin: Khách tìm nhà {cust_budget:,.0f} VNĐ. Đang có căn {best_match['project_name']} phù hợp.
                        YÊU CẦU: Tối đa 3 câu. KHÔNG nhắc con số giá tiền. Phải có từ khóa kích thích khan hiếm/cơ hội. Rủ đi xem ngay.
                        """
                        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)

                        st.success("🎉 Khớp lệnh thành công!")
                        if crm_saved: st.info("☁️ Đã sao lưu hồ sơ khách hàng vào Supabase!")
                        
                        col_img, col_res, col_msg = st.columns([1.5, 1.5, 2])
                        with col_img:
                            st.write("**📸 Hình ảnh thực tế:**")
                            if pd.notna(best_match['image_url']) and str(best_match['image_url']).strip() != "":
                                img_val = str(best_match['image_url']).strip()
                                # BỘ LỌC CHỐNG LỖI ẢNH MÁY TÍNH
                                if img_val.startswith("http"):
                                    st.image(img_val, use_container_width=True)
                                else:
                                    st.warning("⚠️ Ảnh lưu theo thư mục AppSheet. Vui lòng up ảnh lên Web (Drive/Imgur) để hiển thị.")
                            else:
                                st.info("Chưa có hình ảnh.")
                                
                        with col_res:
                            st.write(f"**🏠 Căn hộ:** {best_match['project_name']}")
                            st.write(f"- **Khu vực:** {best_match['district']}")
                            st.write(f"- **Giá nội bộ:** {best_match['price']:,.0f} VNĐ")
                            st.write(f"- **Diện tích:** {best_match['area']} m2")
                            
                        with col_msg:
                            st.write("**📱 Tin nhắn Zalo:**")
                            st.text_area("", response.text, height=120, label_visibility="collapsed")
                        
        # ========================================================
        # TAB 2: QUẢN LÝ LỊCH SỬ DẪN KHÁCH HÔM NAY
        # ========================================================
        with tab2:
            st.subheader("🕵️ Tra cứu lịch sử tư vấn / xem nhà")
            st.markdown("Hệ thống sẽ đồng bộ với CSDL Đám mây Supabase để tìm kiếm toàn bộ lịch sử khớp lệnh của khách hàng.")
            
            search_name = st.text_input("Nhập tên khách hàng cần tra cứu (VD: Anh Nguyễn Văn A):", key="search_crm")
            
            if st.button("Tra cứu Dữ liệu"):
                if not db_url:
                    st.warning("Vui lòng nhập Supabase URI ở menu bên trái trước!")
                elif not search_name:
                    st.warning("Vui lòng nhập tên khách hàng.")
                else:
                    with st.spinner("Đang truy xuất Database..."):
                        try:
                            engine_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
                            engine = create_engine(engine_url)
                            
                            # Dùng câu lệnh SQL truy vấn trực tiếp tên khách hàng (không phân biệt hoa thường)
                            query = f"SELECT thoi_gian, can_ho_de_xuat, ngan_sach, do_phu_hop FROM crm_khach_hang WHERE ten_khach_hang ILIKE '%%{search_name}%%' ORDER BY thoi_gian DESC"
                            history_df = pd.read_sql(query, engine)

                            if not history_df.empty:
                                # Lọc ra các căn nhà đã xem TRONG HÔM NAY
                                today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                                history_df['Ngày'] = pd.to_datetime(history_df['thoi_gian']).dt.strftime('%Y-%m-%d')
                                today_df = history_df[history_df['Ngày'] == today_str]
                                
                                st.success(f"Đã tìm thấy tổng cộng **{len(history_df)}** lần tư vấn cho khách hàng này trên hệ thống.")
                                
                                st.markdown(f"### 📍 Các căn nhà đã xem HÔM NAY ({today_str}):")
                                if not today_df.empty:
                                    st.dataframe(today_df[['thoi_gian', 'can_ho_de_xuat', 'ngan_sach', 'do_phu_hop']], use_container_width=True)
                                else:
                                    st.info("Hôm nay khách chưa có lịch sử khớp lệnh/xem nhà nào mới.")
                                    
                                st.markdown("### 🗓️ Lịch sử các ngày trước:")
                                past_df = history_df[history_df['Ngày'] != today_str]
                                if not past_df.empty:
                                    st.dataframe(past_df[['thoi_gian', 'can_ho_de_xuat', 'ngan_sach', 'do_phu_hop']], use_container_width=True)
                                else:
                                    st.write("Không có dữ liệu cũ.")
                                    
                            else:
                                st.warning("Chưa tìm thấy dữ liệu hoặc khách hàng chưa từng được tư vấn trên hệ thống.")
                        except Exception as e:
                            st.error("Lỗi truy xuất dữ liệu từ Supabase. Đảm bảo bạn đã từng Khớp Lệnh ít nhất 1 lần để hệ thống tự tạo Bảng CRM.")
                            st.write(e)

    except Exception as e:
        st.error("❌ Lỗi dữ liệu Kho Hàng.")
        st.write(e)
