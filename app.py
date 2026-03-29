import streamlit as st
import pandas as pd
import numpy as np
import datetime
import json
import re
import plotly.express as px
from sklearn.preprocessing import MinMaxScaler
from google import genai
from streamlit_gsheets import GSheetsConnection
from sqlalchemy import create_engine, text

# ==========================================
# 1. CẤU HÌNH GIAO DIỆN WEB (CLEAN CODE V2.0)
# ==========================================
st.set_page_config(page_title="LFS Pro - Trợ lý Bất động sản", page_icon="🏢", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

VALID_USER = "admin"
VALID_PASS = "faraland"

# ==========================================
# 2. MÀN HÌNH ĐĂNG NHẬP
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<h1 style='text-align: center;'>🔐 Hệ thống Quản trị LFS V2.0</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Nền tảng Công nghệ Bất động sản Faraland</p>", unsafe_allow_html=True)
    
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
# 3. GIAO DIỆN HỆ THỐNG CHÍNH
# ==========================================
else:
    # --- THANH BÊN (SIDEBAR) ---
    st.sidebar.markdown("### 👤 Tài khoản: Admin")
    if st.sidebar.button("🚪 Đăng xuất"):
        st.session_state['logged_in'] = False
        st.rerun()
    st.sidebar.divider()

    st.sidebar.header("🔑 Cấu hình API & Data")
    api_key = st.sidebar.text_input("1. Gemini API Key:", type="password")
    sheet_url = st.sidebar.text_input("2. Link Google Sheets (Kho Hàng):", type="password")
    db_url = st.sidebar.text_input("3. Supabase URI (Lưu CRM):", type="password")

    st.title("🏢 LFS 2.0 - Trợ lý Ảo AI Toàn Diện")
    
    # --- HÀM XỬ LÝ DỮ LIỆU THÔNG MINH ---
    def process_image_url(url):
        url = str(url).strip()
        if "drive.google.com" in url:
            match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
            if match: return f"https://drive.google.com/uc?id={match.group(1)}"
        return url

    def smart_clean_number(x):
        if pd.isna(x): return np.nan
        try:
            val = float(str(x).replace(',', '').replace(' ', ''))
            # Nếu nhập 10, hệ thống tự hiểu là 10 tỷ
            if 0 < val < 1000: return val * 1_000_000_000
            return val
        except:
            return np.nan

    # --- KẾT NỐI DATABASE MỚI ---
    @st.cache_data(ttl=30) # Cập nhật mỗi 30s
    def load_clean_data(url):
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=url)
        df.columns = df.columns.str.strip()
        
        # Đổi tên cột chuẩn V2.0 sang biến tiếng Anh để thuật toán chạy
        rename_map = {
            'DiaChi': 'project_name', 'GiaBan': 'price', 'DienTich': 'area',
            'SoTang': 'floors', 'PhuongQuan': 'district', 'LinkAnh': 'image_url',
            'LoaiNha': 'property_type', 'ViTriMap': 'location'
        }
        # Chỉ giữ lại các cột có trong database
        rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=rename_map)
        
        # Xử lý dọn dẹp data
        if 'price' in df.columns: df['price'] = df['price'].apply(smart_clean_number)
        if 'area' in df.columns: df['area'] = df['area'].apply(smart_clean_number)
        if 'floors' in df.columns: df['floors'] = pd.to_numeric(df['floors'], errors='coerce').fillna(1)
        if 'district' not in df.columns: df['district'] = "Chưa rõ"
        if 'property_type' not in df.columns: df['property_type'] = "Chưa phân loại"
        
        return df.dropna(subset=['price', 'area', 'project_name'])

    if sheet_url:
        try:
            properties = load_clean_data(sheet_url)
            st.success(f"✅ Đã kết nối Kho Hàng V2.0. Đang có {len(properties)} sản phẩm sẵn sàng giao dịch.")
            
            tab1, tab2, tab3 = st.tabs(["🚀 AI Khớp Lệnh & Dashboard", "📊 Quản Lý CRM", "💡 AI Giao Tiếp"])
            
            # ==========================================
            # TAB 1: PHÒNG ĐIỀU HÀNH & KHỚP LỆNH
            # ==========================================
            with tab1:
                # --- BIỂU ĐỒ TỔNG QUAN ---
                st.markdown("### 📊 Tổng quan Nguồn hàng")
                col_db1, col_db2, col_db3 = st.columns(3)
                with col_db1: st.metric("Tổng số Bất động sản", f"{len(properties)} căn")
                with col_db2:
                    avg_price = (properties['price'].mean() / 1_000_000_000) if len(properties) > 0 else 0
                    st.metric("Mức giá trung bình", f"{avg_price:.2f} Tỷ VNĐ")
                with col_db3:
                    mode_type = str(properties['property_type'].mode()[0]) if len(properties) > 0 else "N/A"
                    st.metric("Phân khúc chủ đạo", mode_type)
                
                if len(properties) > 0:
                    col_chart1, col_chart2 = st.columns(2)
                    with col_chart1:
                        fig_pie = px.pie(properties, names='district', title='Tỷ trọng theo Quận/Huyện', hole=0.4)
                        st.plotly_chart(fig_pie, use_container_width=True)
                    with col_chart2:
                        fig_bar = px.histogram(properties, x='property_type', title='Thống kê Loại BĐS', text_auto=True)
                        st.plotly_chart(fig_bar, use_container_width=True)

                st.divider() 

                # --- AI KHỚP LỆNH ---
                st.subheader("🤖 AI Khớp Lệnh Thần Tốc")
                raw_chat = st.text_area("Dán tin nhắn nhu cầu khách hàng vào đây:", placeholder="VD: Anh tìm căn Cầu Giấy tầm 5 tỷ, diện tích tầm 40m2, nhà 4 tầng...")
                col_btn_ai, _ = st.columns([1, 4])
                with col_btn_ai:
                    btn_ai_submit = st.button("✨ Phân Tích", type="primary", use_container_width=True)

                if btn_ai_submit:
                    if not api_key: st.warning("⚠️ Nhập Gemini API Key ở menu trái!")
                    elif len(properties) == 0: st.error("Rổ hàng trống.")
                    elif not raw_chat: st.warning("Vui lòng dán tin nhắn!")
                    else:
                        with st.spinner("Đang kích hoạt AI & Matching..."):
                            client = genai.Client(api_key=api_key)
                            prompt_json = f"""
                            Trích xuất JSON:
                            {{ "name": "Tên khách (mặc định 'Khách hàng')", "district": "Quận (mặc định 'Bất kỳ')", "budget": Ngân sách tối đa (số nguyên VNĐ. VD 5 tỷ -> 5000000000), "area": Diện tích (Mặc định 30.0), "floors": Số tầng (Mặc định 1) }}
                            TIN NHẮN: "{raw_chat}"
                            """
                            try:
                                response_json = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_json)
                                clean_json = response_json.text.replace('```json', '').replace('```', '').strip()
                                ext_data = json.loads(clean_json)
                                
                                c_name = ext_data.get("name", "Khách hàng")
                                c_dist = ext_data.get("district", "Bất kỳ")
                                c_budg = int(ext_data.get("budget", 3000000000))
                                c_area = float(ext_data.get("area", 30.0))
                                c_floors = int(ext_data.get("floors", 1))
                                
                                st.success(f"**🤖 AI bóc tách:** Khách: **{c_name}** | Khu vực: **{c_dist}** | Tài chính: **{c_budg:,.0f}đ** | **{c_area}**m2 | **{c_floors}** Tầng")
                                
                                # THUẬT TOÁN MATCHING V2.0
                                customer_req = pd.DataFrame({'price': [c_budg], 'area': [c_area]})
                                scaler_price = MinMaxScaler().fit(np.append(properties['price'].values, c_budg).reshape(-1, 1))
                                scaler_area = MinMaxScaler().fit(np.append(properties['area'].values, c_area).reshape(-1, 1))

                                def calc_score(house):
                                    score = 100
                                    # Chấm điểm Khu vực
                                    if c_dist != "Bất kỳ":
                                        if str(house['district']).lower() in str(c_dist).lower() or str(c_dist).lower() in str(house['district']).lower(): score += 50 
                                        else: score -= 30 
                                    
                                    # Chấm điểm Giá (Giá thấp hơn budget là điểm cộng)
                                    h_price_n = scaler_price.transform([[house['price']]])[0][0]
                                    c_budg_n = scaler_price.transform([[c_budg]])[0][0]
                                    diff_n = h_price_n - c_budg_n
                                    diff_vnd = house['price'] - c_budg
                                    
                                    if diff_vnd > 1_000_000_000: score -= (diff_n * 50) 
                                    elif 0 < diff_vnd <= 1_000_000_000: score -= (diff_n * 10)  
                                    else: score += (abs(diff_n) * 15) 
                                        
                                    # Chấm điểm Diện tích & Số tầng
                                    h_area_n = scaler_area.transform([[house['area']]])[0][0]
                                    c_area_n = scaler_area.transform([[c_area]])[0][0]
                                    score -= (abs(h_area_n - c_area_n) * 20) 
                                    if house.get('floors', 0) < c_floors: score -= 20 
                                    
                                    return max(0, round(score, 2)) 

                                properties['match_score'] = properties.apply(calc_score, axis=1)
                                best = properties.sort_values(by='match_score', ascending=False).iloc[0]

                                # LƯU CRM
                                crm_msg = ""
                                if db_url:
                                    try:
                                        engine = create_engine(db_url.replace("postgresql://", "postgresql+psycopg2://"))
                                        new_record = pd.DataFrame([{
                                            "thoi_gian": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                            "ten_khach_hang": c_name, "khu_vuc_tim_kiem": c_dist,
                                            "ngan_sach": f"{c_budg:,.0f} VNĐ", "nhu_cau_chi_tiet": f"{c_area}m2, {c_floors} Tầng",
                                            "can_ho_de_xuat": best['project_name'], "do_phu_hop": f"{best['match_score']}%"
                                        }])
                                        new_record.to_sql('crm_khach_hang', engine, if_exists='append', index=False)
                                        crm_msg = "☁️ Đã sao lưu CRM vào Supabase!"
                                    except:
                                        crm_msg = "⚠️ Không lưu được CRM (Kiểm tra lại link Supabase)."

                                # AI VĂN MẪU ZALO
                                prompt_zalo = f"Viết tin nhắn Zalo gửi {c_name}. Người gửi Đạt (Môi giới BĐS). Khách tìm nhà {c_budg:,.0f}đ. Có căn {best['project_name']} phù hợp. Tối đa 3 câu, ngắn gọn, rủ đi xem nhà."
                                zalo_resp = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_zalo)

                                # KẾT QUẢ
                                st.success(f"🎉 Khớp lệnh thành công! {crm_msg}")
                                c1, c2, c3 = st.columns([1.5, 1.5, 2])
                                with c1:
                                    st.write("**📸 Hình ảnh thực tế:**")
                                    img_val = process_image_url(best.get('image_url', ''))
                                    if img_val.startswith("http"): st.image(img_val, use_container_width=True)
                                    else: st.info("Ảnh gốc AppSheet đang lưu tại Google Drive. Cần cấu hình public để xem.")
                                with c2:
                                    st.write(f"**🏠 {best['project_name']}**")
                                    st.write(f"📍 **Khu vực:** {best['district']}")
                                    st.write(f"💰 **Giá:** {best['price']/1_000_000_000:.2f} Tỷ VNĐ")
                                    st.write(f"📐 **Diện tích:** {best['area']} m2 - **Tầng:** {best.get('floors', 'N/A')}")
                                    if 'location' in best and pd.notna(best['location']):
                                        st.write(f"🌍 **GPS:** `{best['location']}`")
                                    st.write(f"🔥 **Độ phù hợp:** {best['match_score']}%")
                                with c3:
                                    st.write("**📱 Tin nhắn Zalo:**")
                                    st.text_area("", zalo_resp.text, height=180, label_visibility="collapsed")

                            except Exception as e:
                                st.error(f"Lỗi xử lý AI: {e}")

            # ==========================================
            # TAB 2 & 3: CRM & GỢI Ý GIAO TIẾP (Giữ nguyên logic)
            # ==========================================
            with tab2:
                st.subheader("🕵️ Lịch sử Tư vấn & Xuất Báo Cáo")
                if db_url:
                    try:
                        engine = create_engine(db_url.replace("postgresql://", "postgresql+psycopg2://"))
                        history_df = pd.read_sql("SELECT * FROM crm_khach_hang ORDER BY thoi_gian DESC", engine)
                        st.dataframe(history_df, use_container_width=True)
                        st.download_button("📥 Tải Báo Cáo (.csv)", data=history_df.to_csv(index=False).encode('utf-8-sig'), file_name="Bao_Cao_CRM.csv", mime="text/csv")
                    except: st.warning("Chưa có dữ liệu CRM hoặc lỗi kết nối Supabase.")
                else: st.warning("Nhập Supabase URI để xem CRM.")

            with tab3:
                st.subheader("💡 AI Xử Lý Từ Chối")
                cust_msg = st.text_area("Khách hàng nhắn gì?")
                agent_intent = st.text_input("Ý định trả lời:")
                if st.button("✨ Viết Câu Trả Lời"):
                    if api_key and cust_msg:
                        client = genai.Client(api_key=api_key)
                        res = client.models.generate_content(model='gemini-2.5-flash', contents=f"Bạn là Đạt (môi giới). Khách nói: '{cust_msg}'. Ý định của bạn: '{agent_intent}'. Viết phản hồi Zalo ngắn gọn, khéo léo chốt sale.")
                        st.success("Văn mẫu Zalo:")
                        st.text_area("", res.text, height=200, label_visibility="collapsed")
                    else: st.warning("Vui lòng nhập API Key và tin nhắn khách!")

        except Exception as e: st.error(f"❌ Lỗi đọc dữ liệu Kho Hàng: {e}")
