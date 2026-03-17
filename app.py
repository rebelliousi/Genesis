import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium
import ee
# GEE servisinden GÜN 5 analiz fonksiyonlarını da dahil ediyoruz
from gee_service import (
    get_thumbnail_url, 
    get_temporal_chunks, 
    save_image_to_disk, 
    calculate_ndvi_value, 
    analyze_restoration_need
)
from dotenv import load_dotenv
import os

# --- BAŞLANGIÇ AYARLARI ---
load_dotenv()
try:
    ee.Initialize(project=os.getenv("PRO_ID"))
except Exception as e:
    st.error(f"Google Earth Engine başlatılamadı: {e}")

# --- SESSION STATE (OTURUM HAFIZASI) ---
if 'active_lat' not in st.session_state:
    st.session_state['active_lat'] = 39.6992
if 'active_lng' not in st.session_state:
    st.session_state['active_lng'] = 26.8735
if 'show_satellites' not in st.session_state:
    st.session_state['show_satellites'] = False
if 'current_id' not in st.session_state:
    st.session_state['current_id'] = None

# --- VERİTABANI FONKSİYONLARI (GÜNCELLENDİ) ---
@st.cache_data(ttl=5)
def get_all_requests():
    conn = sqlite3.connect('genesis.db')
    df = pd.read_sql_query("SELECT id, latitude, longitude, status, ndvi_diff FROM analysis_requests ORDER BY created_at DESC", conn)
    conn.close()
    return df

def add_coordinate(lat, lng):
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        st.error("Hatalı koordinat aralığı!")
        return None
    try:
        conn = sqlite3.connect('genesis.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO analysis_requests(latitude,longitude,status) VALUES (?,?,?)', (lat, lng, "PENDING"))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return new_id
    except Exception as e:
        st.error(f"Veritabanı hatası: {e}")
        return None

def finalize_analysis_in_db(analiz_id, folder_path, ndvi_diff, ai_report):
    """GÜN 5: Analiz sonuçlarını (NDVI ve Rapor) DB'ye yazar."""
    conn = sqlite3.connect('genesis.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE analysis_requests 
        SET image_folder = ?, ndvi_diff = ?, ai_plan = ?, status = ? 
        WHERE id = ?
    ''', (folder_path, ndvi_diff, ai_report, "COMPLETED", analiz_id))
    conn.commit()
    conn.close()

# --- HARİTA ---
def get_satellite_map(lat, lng):
    m = folium.Map(location=[lat, lng], zoom_start=15)
    esri_satellite = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    folium.TileLayer(tiles=esri_satellite, attr='Esri', name="Esri Satellite").add_to(m)
    folium.Marker([lat, lng], popup=f"Hedef: {lat}, {lng}").add_to(m)
    return m

# --- ARAYÜZ TASARIMI ---
st.set_page_config(page_title="Project GENESIS", layout="wide")
st.title("🌱 Project GENESIS: Analiz Motoru")

with st.sidebar:
    st.header("📍 Bölge Tanımla")
    lat_input = st.number_input("Enlem", value=float(st.session_state['active_lat']), format="%.4f")
    lng_input = st.number_input("Boylam", value=float(st.session_state['active_lng']), format="%.4f")

    if st.button("💾 Kaydet ve Analizi Başlat"):
        # Yeni bir ID oluştur ve analizi tetikle
        new_id = add_coordinate(lat_input, lng_input)
        if new_id:
            st.session_state['current_id'] = new_id
            st.session_state['active_lat'] = lat_input
            st.session_state['active_lng'] = lng_input
            st.session_state['show_satellites'] = True
            st.rerun()

# --- ANA PANEL ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🗺️ İnteraktif Harita")
    m = get_satellite_map(st.session_state['active_lat'], st.session_state['active_lng'])
    map_data = st_folium(m, width=700, height=450, key="main_map")
    
    if map_data and map_data.get('last_clicked'):
        c_lat, c_lng = map_data['last_clicked']['lat'], map_data['last_clicked']['lng']
        if c_lat != st.session_state['active_lat']:
            st.session_state['active_lat'] = c_lat
            st.session_state['active_lng'] = c_lng
            st.session_state['current_id'] = None
            st.rerun()

with col2:
    st.subheader("📜 Analiz Geçmişi")
    df = get_all_requests()
    st.dataframe(df, use_container_width=True, height=400)

# --- 🛰️ GÜN 5: BİLİMSEL ANALİZ VE RAPORLAMA ---
if st.session_state['show_satellites'] and st.session_state['current_id']:
    st.divider()
    analiz_id = st.session_state['current_id']
    st.subheader(f"📊 50 Yıllık Bilimsel Analiz Raporu: Analiz #{analiz_id}")
    
    # Analiz için gerekli GEE objesi
    point = ee.Geometry.Point([st.session_state['active_lng'], st.session_state['active_lat']])
    
    with st.spinner("Piksel verileri analiz ediliyor ve yeşillik endeksi hesaplanıyor..."):
        # 1. Görüntüleri çek (GÜN 3)
        chunks = get_temporal_chunks(st.session_state['active_lat'], st.session_state['active_lng'])
        
        ndvi_store = {}
        cols = st.columns(3)
        
        for i, chunk in enumerate(chunks):
            if chunk['image']:
                # 2. Resim URL'sini al
                url = get_thumbnail_url(chunk['image'], st.session_state['active_lat'], st.session_state['active_lng'], chunk['satellite'])
                
                # 3. Diske kaydet (GÜN 4 - Block Server)
                save_image_to_disk(url, analiz_id, chunk['year'])
                
                # 4. GÜN 5: NDVI Değerini Hesapla
                ndvi_val = calculate_ndvi_value(chunk['image'], chunk['satellite'], point)
                ndvi_store[chunk['year']] = ndvi_val
                
                # Ekranda göster
                with cols[i]:
                    st.image(url, caption=f"{chunk['year']} | NDVI: {round(ndvi_val, 3)}", use_container_width=True)

        # --- GÜN 5: KARŞILAŞTIRMA VE KARAR MEKANİZMASI ---
        ndvi_1975 = ndvi_store.get("1975", 0)
        ndvi_2024 = ndvi_store.get("2024", 0)
        
        loss_rate, report_text = analyze_restoration_need(ndvi_1975, ndvi_2024)
        
        # 5. Sonuçları Ekrana Bas (Metric ve Alert)
        st.write("---")
        m_col1, m_col2 = st.columns(2)
        
        with m_col1:
            st.metric(
                label="50 Yıllık Vejetasyon Değişimi", 
                value=f"%{loss_rate}", 
                delta=f"-{loss_rate}%" if loss_rate > 0 else f"+{abs(loss_rate)}%",
                delta_color="inverse"
            )
            
        with m_col2:
            st.markdown(f"**Analiz Durumu:**")
            if loss_rate > 40:
                st.error(report_text)
            elif loss_rate > 15:
                st.warning(report_text)
            else:
                st.success(report_text)

        # 6. GÜN 5: Sonuçları Veritabanına Kalıcı Olarak Yaz
        folder_path = f"data/analyses/{analiz_id}/"
        finalize_analysis_in_db(analiz_id, folder_path, loss_rate, report_text)
        
        st.info(f"💾 Tüm veriler `genesis.db` veritabanına işlendi ve görseller yerel arşive (`{folder_path}`) kaydedildi.")