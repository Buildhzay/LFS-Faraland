import streamlit as st
import pandas as pd
import numpy as np
import datetime
import json
import re
import os
import requests
from io import BytesIO
import PIL.Image
import PyPDF2
import plotly.express as px
from sklearn.preprocessing import MinMaxScaler
from google import genai
from streamlit_gsheets import GSheetsConnection
from sqlalchemy import create_engine, text

# ==========================================
# 1. CẤU HÌNH GIAO DIỆN WEB (MASTER V3.0)
# ==========================================
st.set_page_config(page_title="LFS Pro - Trợ lý Bất động sản", page_icon="🏢", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

VALID_USER = "admin"
VALID_PASS = "123456"

# ==========================================
# 2. MÀN HÌNH ĐĂNG NHẬP
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<h1 style='text-align: center;'>🔐 Hệ thống Quản trị LFS V3.0</h1>", unsafe_allow_html=True)
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

    st.title("🏢 LFS 3.0 - Trợ lý Ảo AI Toàn Diện")
    
    # --- HÀM XỬ LÝ DỮ LIỆU THÔNG MINH ---
    def process_image_url(url):
        url = str(url).strip()
        if "drive.google.com" in url:
            match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
            if match: return f"https://drive.google.com/uc?id={match.group(1)}"
        return url

    def smart_clean_price(x):
        if pd.isna(x): return np.nan
        try:
            nums = re.findall(r'[\d\.]+', str(x).replace(',', '.'))
            if nums:
                val = float(nums[0])
                if 0 < val < 1000: return val * 1_000_000_000
                return val
            return np.nan
        except: return np.nan

    def smart_clean_area(x):
        if pd.isna(x): return 0
        try:
            nums = re.findall(r'[\d\.]+', str(x).replace(',', '.'))
            if nums:
                val = float(nums[0])
                return int(val) if val.is_integer() else val
            return 0
        except: return 0

    @st.cache_data
    def load_sale_scripts(file_path):
        try:
            text_content = ""
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text_content += page.extract_text() + "\n"
                return text_content
            return "Hãy dùng kỹ năng chốt sale khéo léo nhất."
        except:
            return "Hãy dùng kỹ năng chốt sale khéo léo nhất."

    # --- KẾT NỐI DATABASE ---
    @st.cache_data(ttl=30)
    def load_clean_data(url):
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=url)
        df.columns = df.columns.str.strip()
        
        rename_map = {
            'DiaChi': 'project_name', 'GiaBan': 'price', 'DienTich': 'area',
            'SoTang': 'floors', 'PhuongQuan': 'district', 'LinkAnh': 'image_url',
            'LoaiNha': 'property_type', 'ViTriMap': 'location'
        }
        rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=rename_map)
        
        if 'price' in df.columns: df['price'] = df['price'].apply(smart_clean_price)
        if 'area' in df.columns: df['area'] = df['area'].apply(smart_clean_area)
        if 'floors' in df.columns: df['floors'] = pd.to_numeric(df['floors'], errors='coerce').fillna(1)
        if 'district' not in df.columns: df['district'] = "Chưa rõ"
        if 'property_type' not in df.columns: df['property_type'] = "Chưa phân loại"
        
        return df.dropna(subset=['price', 'project_name'])

    if sheet_url:
        try:
            properties = load_clean_data(sheet_url)
            st.success(f"✅ Đã kết nối Kho Hàng. Đang có {len(properties)} sản phẩm sẵn sàng giao dịch.")
            
            tab1, tab2, tab3, tab4 = st.tabs(["🚀 AI Khớp Lệnh", "📊 Quản Lý CRM", "💡 AI Content & Kịch Bản", "🖼️ AI Lọc Ảnh Mồi"])
            
            # ==========================================
            # TAB 1: PHÒNG ĐIỀU HÀNH & KHỚP LỆNH
            # ==========================================
            with tab1:
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
                            {{ "name": "Tên khách", "district": "Quận (mặc định 'Bất kỳ')", "budget": Ngân sách tối đa (số nguyên VNĐ. VD 5 tỷ -> 5000000000), "area": Diện tích (Mặc định 30.0), "floors": Số tầng (Mặc định 1) }}
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
                                
                                scaler_price = MinMaxScaler().fit(np.append(properties['price'].values, c_budg).reshape(-1, 1))
                                scaler_area = MinMaxScaler().fit(np.append(properties['area'].values, c_area).reshape(-1, 1))

                                def calc_score(house):
                                    score = 100
                                    if c_dist != "Bất kỳ":
                                        if str(house['district']).lower() in str(c_dist).lower() or str(c_dist).lower() in str(house['district']).lower(): score += 50 
                                        else: score -= 30 
                                    
                                    h_price_n = scaler_price.transform([[house['price']]])[0][0]
                                    c_budg_n = scaler_price.transform([[c_budg]])[0][0]
                                    diff_n = h_price_n - c_budg_n
                                    diff_vnd = house['price'] - c_budg
                                    
                                    if diff_vnd > 1_000_000_000: score -= (diff_n * 50) 
                                    elif 0 < diff_vnd <= 1_000_000_000: score -= (diff_n * 10)  
                                    else: score += (abs(diff_n) * 15) 
                                        
                                    h_area_n = scaler_area.transform([[house['area']]])[0][0]
                                    c_area_n = scaler_area.transform([[c_area]])[0][0]
                                    score -= (abs(h_area_n - c_area_n) * 20) 
                                    if house.get('floors', 0) < c_floors: score -= 20 
                                    
                                    return max(0, round(score, 2)) 

                                properties['match_score'] = properties.apply(calc_score, axis=1)
                                best = properties.sort_values(by='match_score', ascending=False).iloc[0]

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

                                prompt_zalo = f"Viết tin nhắn Zalo gửi {c_name}. Người gửi Đạt. Khách tìm nhà {c_budg:,.0f}đ. Có căn {best['project_name']} phù hợp. 3 câu, ngắn gọn, rủ đi xem nhà."
                                zalo_resp = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_zalo)

                                st.success(f"🎉 Khớp lệnh thành công! {crm_msg}")
                                c1, c2, c3 = st.columns([1.5, 1.5, 2])
                                with c1:
                                    st.write("**📸 Hình ảnh thực tế:**")
                                    img_val = process_image_url(best.get('image_url', ''))
                                    if img_val.startswith("http"): st.image(img_val, use_container_width=True)
                                    else: st.info("Ảnh gốc đang lưu tại Google Drive.")
                                with c2:
                                    st.write(f"**🏠 {best['project_name']}**")
                                    st.write(f"📍 **Khu vực:** {best['district']}")
                                    st.write(f"💰 **Giá:** {best['price']/1_000_000_000:.2f} Tỷ VNĐ")
                                    st.write(f"📐 **Diện tích:** {best['area']} m2 - **Tầng:** {best.get('floors', 'N/A')}")
                                    st.write(f"🔥 **Độ phù hợp:** {best['match_score']}%")
                                with c3:
                                    st.write("**📱 Tin nhắn Zalo:**")
                                    st.text_area("", zalo_resp.text, height=180, label_visibility="collapsed")

                            except Exception as e:
                                st.error(f"Lỗi xử lý AI: {e}")

            # ==========================================
            # TAB 2: QUẢN LÝ CRM
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

            # ==========================================
            # TAB 3: AI CONTENT & XỬ LÝ TỪ CHỐI BẰNG KỊCH BẢN
            # ==========================================
            with tab3:
                # --- PHẦN 1: TẠO TIN ĐĂNG ---
                st.subheader("📝 1. Tự Động Viết Tin Đăng (Few-Shot AI)")
                st.markdown("Hệ thống tự động trích xuất văn mẫu thực chiến để AI 'nhập hồn' và viết bài siêu tốc.")
                
                if len(properties) > 0:
                    house_options = properties['project_name'].tolist()
                    selected_house_name = st.selectbox("🔍 Chọn Bất động sản cần viết bài:", house_options)
                    
                    if st.button("✨ Viết Bài Đăng Bán Nhà", type="primary"):
                        if not api_key:
                            st.warning("⚠️ Vui lòng nhập Gemini API Key!")
                        else:
                            with st.spinner("AI đang đọc văn mẫu và soạn content..."):
                                client = genai.Client(api_key=api_key)
                                
                                selected_house = properties[properties['project_name'] == selected_house_name].iloc[0]
                                h_price = selected_house['price'] / 1_000_000_000
                                h_area = selected_house['area']
                                h_dist = selected_house['district']
                                h_floors = selected_house.get('floors', 'N/A')
                                h_type = str(selected_house.get('property_type', 'Bất động sản')).lower()
                                h_front = selected_house.get('MatTien', 'Rộng rãi')

                                # CHE MỜ GIÁ
                                if h_price >= 10: masked_price = str(int(h_price))[0] + "x.xx"
                                else: masked_price = str(int(h_price)) + ".xx"

                                # TÌM VĂN MẪU
                                file_mau = "mau_4_8ty.csv"
                                if any(word in h_type for word in ["dòng tiền", "ccmn", "căn hộ dịch vụ", "cho thuê"]): file_mau = "mau_dong_tien.csv"
                                elif h_price >= 20: file_mau = "mau_20ty.csv"
                                elif h_price >= 10: file_mau = "mau_10ty.csv"
                                
                                van_mau_text = ""
                                if os.path.exists(file_mau):
                                    try:
                                        df_mau = pd.read_csv(file_mau)
                                        if 'NỘI DUNG' in df_mau.columns:
                                            df_mau = df_mau.dropna(subset=['NỘI DUNG'])
                                            if not df_mau.empty:
                                                sample_df = df_mau.sample(min(3, len(df_mau)))
                                                for _, row in sample_df.iterrows():
                                                    van_mau_text += f"\n[VÍ DỤ]:\nTIÊU ĐỀ: {row.get('TIÊU ĐỀ', '')}\nNỘI DUNG:\n{row['NỘI DUNG']}\n---\n"
                                    except: pass
                                
                                if not van_mau_text.strip(): van_mau_text = "Tự viết bằng văn phong đỉnh cao."

                                prompt_marketing = f"""
                                Bạn là Đạt, một siêu cò bất động sản lão luyện. SĐT: 0886426918.
                                - Loại hình: {h_type} | Khu vực: Quận {h_dist} | Diện tích: {h_area} m2 | Mặt tiền: {h_front} | Số tầng: {h_floors} | Giá: {masked_price} Tỷ.

                                BÀI VĂN MẪU (Bắt chước Vibe):
                                {van_mau_text}

                                YÊU CẦU:
                                1. SIÊU NGẮN GỌN (< 150 từ).
                                2. BẮT BUỘC TRÌNH BÀY ĐÚNG FORM SAU VÀ GIỮ NGUYÊN KHOẢNG TRẮNG ĐỂ THỤT LỀ:

                                🚨🚨 [GIẬT TÍT SỐC: TỪ KHÓA + VỊ TRÍ + GIÁ CHỈ {masked_price} TỶ] 🚨🚨
                                
                                📍 Vị trí kim cương: [1 câu mô tả ẩn vị trí]
                                
                                🏡 SIÊU PHẨM MỚI CỨNG VỚI THÔNG SỐ VÀNG:
                                &nbsp;&nbsp;&nbsp;&nbsp;👉 Diện tích: {h_area} m² 🤯
                                &nbsp;&nbsp;&nbsp;&nbsp;👉 Kết cấu: {h_floors} tầng kiên cố, [công năng]
                                &nbsp;&nbsp;&nbsp;&nbsp;👉 Mặt tiền: {h_front} - [ưu điểm mặt tiền]
                                &nbsp;&nbsp;&nbsp;&nbsp;💰 GIÁ BÁN SỐC: CHỈ {masked_price} TỶ (Gà đẻ trứng vàng!)
                                
                                🎯 Tiềm năng: Cam kết dòng tiền ổn định, tiềm năng tăng giá cao trong tương lai gần!
                                
                                LH: E Đạt - 0886426918 ( chính chủ k tiếp môi giới )
                                """
                                try:
                                    marketing_res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_marketing)
                                    st.success(f"Ting ting! Đã tạo bài (Giá ẩn: {masked_price} Tỷ):")
                                    st.markdown(marketing_res.text)
                                except Exception as e: st.error(f"Lỗi kết nối AI: {e}")
                
                st.divider()

                # --- PHẦN 2: AI XỬ LÝ TỪ CHỐI BẰNG 90 KỊCH BẢN ---
                st.subheader("💬 2. AI Xử Lý Từ Chối (Được trang bị 90 Kịch Bản Chốt Sale)")
                st.markdown("Khi khách hàng do dự, AI sẽ tự động lục tìm trong '90 Kịch Bản Chốt Sale Thần Tốc' để đưa ra cách xử lý khéo léo nhất.")
                
                cust_msg = st.text_area("1. Khách hàng vừa nhắn gì cho bạn?", placeholder="VD: Để anh bàn lại với vợ đã / Giá này anh thấy hơi đắt em ạ...")
                agent_intent = st.text_input("2. Ý định trả lời của bạn (Tùy chọn):", placeholder="VD: Thuyết phục đi xem nhà ngay hôm nay kẻo khách khác chốt mất...")
                
                if st.button("✨ Viết Câu Trả Lời Giúp Tôi"):
                    if not api_key: st.warning("Vui lòng nhập Gemini API Key!")
                    elif not cust_msg: st.warning("Bạn chưa dán tin nhắn của khách kìa!")
                    else:
                        with st.spinner("AI đang lật mở bí kíp 90 Kịch Bản Chốt Sale và soạn văn mẫu..."):
                            client = genai.Client(api_key=api_key)
                            bi_kip_text = load_sale_scripts("kich_ban.pdf")
                            
                            prompt_reply = f"""
                            Bạn là Đạt, một chuyên gia chốt sale Bất động sản lão luyện tại Faraland (Việt Nam).
                            
                            DƯỚI ĐÂY LÀ CUỐN BÍ KÍP "90 KỊCH BẢN CHỐT SALE THẦN TỐC" CỦA BẠN:
                            {bi_kip_text}

                            TÌNH HUỐNG HIỆN TẠI:
                            Khách nhắn: "{cust_msg}". Định hướng của tôi: "{agent_intent}"

                            NHIỆM VỤ CỦA BẠN:
                            1. Đối chiếu xem tin nhắn thuộc tình huống từ chối nào trong Bí Kíp.
                            2. Sử dụng chiến thuật/lời thoại trong bí kíp để viết 1 tin nhắn Zalo phản hồi.
                            3. Viết cực kỳ tự nhiên, súc tích (Tối đa 4 câu), khéo léo đánh vào tâm lý dồn khách hẹn đi xem nhà hoặc chốt cọc.
                            """
                            try:
                                reply_response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_reply)
                                st.success("💡 Tuyệt chiêu phản hồi (Áp dụng từ Bí kíp):")
                                st.text_area("", reply_response.text, height=200, label_visibility="collapsed")
                            except Exception as e: st.error("Lỗi kết nối AI.")

            # ==========================================
            # TAB 4: AI GIÁM KHẢO LỌC ẢNH
            # ==========================================
            with tab4:
                st.header("🖼️ AI Giám Khảo - Chọn Ảnh 'Hút Khách'")
                option_anh = st.radio("Nguồn ảnh:", ["Tải lên từ máy", "Lấy từ Database"], horizontal=True)
                images_to_grade = []

                if option_anh == "Tải lên từ máy":
                    uploaded_files = st.file_uploader("Tải lên danh sách ảnh:", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
                    if uploaded_files:
                        for f in uploaded_files: images_to_grade.append({"name": f.name, "img": PIL.Image.open(f)})
                else:
                    if len(properties) > 0:
                        house_options = properties['project_name'].tolist()
                        selected_house_name = st.selectbox("🔍 Chọn Bất động sản cần lấy ảnh:", house_options)
                        selected_house = properties[properties['project_name'] == selected_house_name].iloc[0]
                        img_cols = [c for c in properties.columns if "Anh" in c or c in ["image_url", "LinkAnh"]]
                        
                        if st.button("📥 Hút Ảnh từ Database"):
                            count_found = 0
                            for col in img_cols:
                                val = process_image_url(str(selected_house.get(col, "")))
                                if val.startswith("http"):
                                    try:
                                        res = requests.get(val)
                                        images_to_grade.append({"name": col, "img": PIL.Image.open(BytesIO(res.content))})
                                        count_found += 1
                                    except: pass
                            if count_found > 0: st.success(f"✅ Đã hút thành công {count_found} ảnh!")
                            else: st.warning("⚠️ Không tìm thấy link ảnh (http) cho căn nhà này.")
                    else: st.warning("Kho hàng đang trống!")

                st.divider()

                if st.button("🌟 Bắt Đầu Chấm Điểm Ảnh", type="primary"):
                    if not api_key: st.warning("⚠️ Nhập API Key!")
                    elif not images_to_grade: st.warning("⚠️ Chưa có ảnh!")
                    else:
                        with st.spinner("AI đang chấm điểm..."):
                            client = genai.Client(api_key=api_key)
                            results = []
                            for item in images_to_grade:
                                try:
                                    prompt_image = """
                                    Chấm điểm thẩm mỹ ảnh BĐS làm "ảnh mồi" (1-10). Tiêu chí: Sáng sủa, góc rộng, hiện đại.
                                    Chỉ trả JSON: {"score": 9, "reason": "Ánh sáng tốt..."}
                                    """
                                    response = client.models.generate_content(model='gemini-2.5-flash', contents=[item["img"], prompt_image])
                                    data = json.loads(response.text.replace('```json', '').replace('```', '').strip())
                                    results.append({"name": item["name"], "img": item["img"], "score": data.get("score", 0), "reason": data.get("reason", "")})
                                except Exception as e: st.error(f"Lỗi: {e}")
                            
                            if results:
                                results.sort(key=lambda x: x['score'], reverse=True)
                                st.success("🎉 Bảng Xếp Hạng ảnh mồi:")
                                cols = st.columns(3)
                                for i, res in enumerate(results):
                                    with cols[i % 3]: 
                                        st.image(res["img"], use_container_width=True)
                                        st.markdown(f"**{res['name']}** | ⭐ **{res['score']}/10**")
                                        st.caption(f"🤖 **Nhận xét:** {res['reason']}")

        except Exception as e:
            st.error(f"❌ Lỗi đọc dữ liệu: {e}")
