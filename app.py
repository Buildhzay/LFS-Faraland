import streamlit as st
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from google import genai

# --- 1. CẤU HÌNH GIAO DIỆN WEB ---
st.set_page_config(page_title="LFS - Trợ lý Bất động sản", page_icon="🏡", layout="wide")
st.title("🏡 Hệ thống LFS - Trợ lý Ảo Faraland")
st.markdown("Hệ thống tự động matching nhu cầu khách hàng và tạo tin nhắn chốt sale.")

# --- 2. CẤU HÌNH API KEY (Nhập từ giao diện để bảo mật) ---
api_key = st.sidebar.text_input("Nhập Gemini API Key của bạn:", type="password")

# --- 3. DỮ LIỆU GIỎ HÀNG BẤT ĐỘNG SẢN (Mock Data) ---
@st.cache_data # Lưu cache để không bị load lại data mỗi lần bấm nút
def load_properties():
    return pd.DataFrame({
        'project_name': ['Smart City', 'The Tower', 'Green Villa'],
        'price': [3200000000, 4500000000, 3600000000], 
        'area': [68.5, 75.0, 60.0],
        'bedrooms': [2, 2, 1]
    })

properties = load_properties()

# --- 4. FORM NHẬP THÔNG TIN KHÁCH HÀNG ---
with st.form("customer_form"):
    st.subheader("👤 Thông tin Khách hàng")
    col1, col2 = st.columns(2)
    
    with col1:
        cust_name = st.text_input("Tên khách hàng:", "Anh Nguyễn Văn A")
        cust_budget = st.number_input("Ngân sách tối đa (VNĐ):", min_value=1000000000, value=3500000000, step=100000000)
    with col2:
        cust_area = st.number_input("Diện tích mong muốn (m2):", min_value=30.0, value=65.0, step=1.0)
        cust_bedrooms = st.number_input("Số phòng ngủ tối thiểu:", min_value=1, value=2, step=1)
        
    submitted = st.form_submit_button("Lọc nhà & Tạo tin nhắn Zalo")

# --- 5. LOGIC XỬ LÝ KHI BẤM NÚT ---
if submitted:
    if not api_key:
        st.warning("⚠️ Vui lòng nhập API Key ở menu bên trái trước khi chạy hệ thống!")
    else:
        with st.spinner('AI đang tính toán độ phù hợp và soạn tin nhắn...'):
            # --- Thuật toán Matching ---
            customer_req = pd.DataFrame({'budget': [cust_budget], 'area': [cust_area], 'bedrooms': [cust_bedrooms]})
            
            all_prices = np.append(properties['price'].values, customer_req['budget'].values).reshape(-1, 1)
            all_areas = np.append(properties['area'].values, customer_req['area'].values).reshape(-1, 1)
            scaler_price = MinMaxScaler().fit(all_prices)
            scaler_area = MinMaxScaler().fit(all_areas)

            def calculate_match_score(house, customer):
                score = 100 
                house_price_norm = scaler_price.transform([[house['price']]])[0][0]
                cust_budget_norm = scaler_price.transform([[customer['budget'][0]]])[0][0]
                price_diff = house_price_norm - cust_budget_norm
                
                if price_diff > 0: score -= (price_diff * 50) 
                else: score += (abs(price_diff) * 10)
                    
                house_area_norm = scaler_area.transform([[house['area']]])[0][0]
                cust_area_norm = scaler_area.transform([[customer['area'][0]]])[0][0]
                score -= (abs(house_area_norm - cust_area_norm) * 20) 
                
                if house['bedrooms'] < customer['bedrooms'][0]: score -= 30 
                return max(0, round(score, 2)) 

            properties['match_score'] = properties.apply(lambda row: calculate_match_score(row, customer_req), axis=1)
            best_match = properties.sort_values(by='match_score', ascending=False).iloc[0]

            # --- Gọi Gemini API tạo nội dung ---
            client = genai.Client(api_key=api_key)
            prompt = f"""
            Viết một tin nhắn Zalo gửi khách hàng {cust_name}.
            Người gửi là Đạt, chuyên viên tư vấn tại Faraland.

            Thông tin ngầm hiểu (ĐỂ AI BIẾT NHƯNG KHÔNG ĐƯỢC NÓI RA CON SỐ CỤ THỂ):
            - Khách tìm nhà tầm {cust_budget:,.0f} VNĐ.
            - Đang có căn {best_match['project_name']} giá {best_match['price']:,.0f} VNĐ.

            Yêu cầu NGHIÊM NGẶT:
            - Viết cực kỳ ngắn gọn, giống hệt phong cách nhắn tin Zalo thực tế của môi giới (tối đa 3 câu).
            - TUYỆT ĐỐI KHÔNG nhắc đến con số giá tiền cụ thể.
            - Chỉ khơi gợi sự tò mò: báo cho khách biết mình vừa tìm được một căn {best_match['project_name']} cực kỳ đúng ý, đúng tầm tài chính.
            - KHÔNG dùng từ ngữ sáo rỗng, công nghiệp của AI.
            - Kết thúc bằng một câu rủ đi xem nhà thực tế.
            """
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )

            # --- Hiển thị kết quả ra Web ---
            st.success("🎉 Đã tìm thấy căn hộ phù hợp nhất!")
            
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                st.info(f"**Căn hộ đề xuất:** {best_match['project_name']}")
                st.write(f"- **Độ phù hợp:** {best_match['match_score']}%")
                st.write(f"- **Giá nội bộ:** {best_match['price']:,.0f} VNĐ")
                st.write(f"- **Diện tích:** {best_match['area']} m2")
            
            with col_res2:
                st.write("**📱 Tin nhắn Zalo gợi ý:**")
                st.text_area("Copy và gửi ngay:", response.text, height=150)