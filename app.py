import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium
import ee
import os
from dotenv import load_dotenv

# Kendi yazdığımız servislerden fonksiyonları çağırıyoruz
from gee_service import (
    get_thumbnail_url, 
    get_temporal_chunks, 
    save_image_to_disk, 
    calculate_ndvi_value, 
    analyze_restoration_need
)

# --- BAŞLANGIÇ AYARLARI ---
load_dotenv()
try:
    ee.Initialize(project=os.getenv("PRO_ID"))
except Exception as e:
    st.error(f"Google Earth Engine başlatılamadı: {e}")

# --- SESSION STATE (OTURUM HAFIZASI) ---
if 'active_lat' not in st.session_state: st.session_state['active_lat'] = 39.6992
if 'active_lng' not in st.session_state: st.session_state['active_lng'] = 26.8735
if 'show_satellites' not in st.session_state: st.session_state['show_satellites'] = False
if 'current_id' not in st.session_state: st.session_state['current_id'] = None
if 'is_cached' not in st.session_state: st.session_state['is_cached'] = False

# --- VERİTABANI FONKSİYONLARI ---
@st.cache_data(ttl=5)
def get_all_requests():
    conn = sqlite3.connect('genesis.db')
    df = pd.read_sql_query("SELECT id, latitude, longitude, status, ndvi_diff FROM analysis_requests ORDER BY created_at DESC", conn)
    conn.close()
    return df

def check_existing_analysis(lat, lng):
    """GÜN 6: Daha önce yapılmış analizi kontrol eder."""
    conn = sqlite3.connect('genesis.db')
    cursor = conn.cursor()
    # 4 basamak hassasiyetle (yaklaşık 11 metre) arama yapar
    cursor.execute('''
        SELECT * FROM analysis_requests 
        WHERE ROUND(latitude, 4) = ROUND(?, 4) 
        AND ROUND(longitude, 4) = ROUND(?, 4) 
        AND status = 'COMPLETED'
        ORDER BY created_at DESC LIMIT 1
    ''', (lat, lng))
    result = cursor.fetchone()
    conn.close()
    return result

def add_coordinate(lat, lng):
    conn = sqlite3.connect('genesis.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO analysis_requests(latitude,longitude,status) VALUES (?,?,?)', (lat, lng, "PENDING"))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def finalize_analysis_in_db(analiz_id, folder_path, ndvi_diff, ai_report):
    conn = sqlite3.connect('genesis.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE analysis_requests SET image_folder = ?, ndvi_diff = ?, ai_plan = ?, status = 'COMPLETED' 
        WHERE id = ?
    ''', (folder_path, ndvi_diff, ai_report, analiz_id))
    conn.commit()
    conn.close()

# --- HARİTA ---
def get_satellite_map(lat, lng):
    m = folium.Map(location=[lat, lng], zoom_start=15)
    esri_satellite = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    folium.TileLayer(tiles=esri_satellite, attr='Esri', name="Esri Satellite").add_to(m)
    folium.Marker([lat, lng], popup=f"Hedef: {lat}, {lng}").add_to(m)
    return m

# --- ARAYÜZ ---
st.set_page_config(page_title="Project GENESIS", layout="wide")
st.title("🌱 Project GENESIS: Akıllı Analiz Sistemi")

with st.sidebar:
    st.header("📍 Analiz Başlat")
    lat_input = st.number_input("Enlem", value=float(st.session_state['active_lat']), format="%.4f")
    lng_input = st.number_input("Boylam", value=float(st.session_state['active_lng']), format="%.4f")

    if st.button("🚀 Analizi Çalıştır"):
        # --- GÜN 6: TEKİLLEŞTİRME (DE-DUPLICATION) ---
        existing = check_existing_analysis(lat_input, lng_input)
        
        if existing:
            # Veri zaten varsa GEE'ye gitme, DB'deki ID'yi kullan
            st.session_state['current_id'] = existing[0]
            st.session_state['is_cached'] = True
            st.info("✨ Bu koordinat daha önce analiz edilmiş. Arşivden getiriliyor...")
        else:
            # Veri yoksa yeni kayıt aç
            st.session_state['current_id'] = add_coordinate(lat_input, lng_input)
            st.session_state['is_cached'] = False
        
        st.session_state['active_lat'] = lat_input
        st.session_state['active_lng'] = lng_input
        st.session_state['show_satellites'] = True
        st.rerun()

# --- ANA PANEL ---
col1, col2 = st.columns([2, 1])

with col1:
    m = get_satellite_map(st.session_state['active_lat'], st.session_state['active_lng'])
    map_data = st_folium(m, width=700, height=450, key="main_map")
    if map_data and map_data.get('last_clicked'):
        c_lat, c_lng = map_data['last_clicked']['lat'], map_data['last_clicked']['lng']
        if round(c_lat, 4) != round(st.session_state['active_lat'], 4):
            st.session_state['active_lat'] = c_lat
            st.session_state['active_lng'] = c_lng
            st.session_state['show_satellites'] = False
            st.rerun()

with col2:
    st.subheader("📜 Analiz Geçmişi")
    st.dataframe(get_all_requests(), use_container_width=True, height=400)

# --- 🛰️ GÜN 6: AKILLI ANALİZ GÖSTERİMİ (CACHED VS NEW) ---
if st.session_state['show_satellites'] and st.session_state['current_id']:
    st.divider()
    analiz_id = st.session_state['current_id']
    
    if st.session_state['is_cached']:
        # --- DURUM A: VERİLERİ DİSKTEN VE DB'DEN ÇEK ---
        conn = sqlite3.connect('genesis.db')
        data = conn.execute("SELECT * FROM analysis_requests WHERE id=?", (analiz_id,)).fetchone()
        conn.close()
        
        loss_rate, folder_path, report_text = data[4], data[5], data[6]
        
        st.subheader(f"📊 Arşiv Raporu: Analiz #{analiz_id}")
        cols = st.columns(3)
        for i, year in enumerate(["1975", "2000", "2024"]):
            img_path = os.path.join(folder_path, f"{year}.png")
            if os.path.exists(img_path):
                cols[i].image(img_path, caption=f"{year} (Arşiv)", use_container_width=True)

        m1, m2 = st.columns(2)
        m1.metric("Doğa Değişimi (Arşiv)", f"%{loss_rate}", delta=f"-{loss_rate}%", delta_color="inverse")
        m2.info(report_text)

    else:
        # --- DURUM B: YENİ ANALİZ YAP (GEE ÇAĞRISI) ---
        st.subheader(f"🛰️ Yeni Bilimsel Analiz: Analiz #{analiz_id}")
        point = ee.Geometry.Point([st.session_state['active_lng'], st.session_state['active_lat']])
        
        with st.spinner("Uydular taranıyor..."):
            chunks = get_temporal_chunks(st.session_state['active_lat'], st.session_state['active_lng'])
            ndvi_store = {}
            cols = st.columns(3)
            
            for i, chunk in enumerate(chunks):
                if chunk['image']:
                    # Görüntü URL ve Diske Kayıt
                    url = get_thumbnail_url(chunk['image'], st.session_state['active_lat'], st.session_state['active_lng'], chunk['satellite'])
                    save_image_to_disk(url, analiz_id, chunk['year'])
                    
                    # NDVI Hesapla
                    ndvi_val = calculate_ndvi_value(chunk['image'], chunk['satellite'], point)
                    ndvi_store[chunk['year']] = ndvi_val
                    
                    with cols[i]:
                        st.image(url, caption=f"{chunk['year']} | NDVI: {round(ndvi_val, 3)}", use_container_width=True)

            # Raporlama
            loss_rate, report_text = analyze_restoration_need(ndvi_store.get("1975", 0), ndvi_store.get("2024", 0))
            
            # Sonuçları Göster
            # --- DÜZELTİLMİŞ HALİ (BUNU YAPIŞTIR) ---
            m1, m2 = st.columns(2)
            with m1:
                st.metric("50 Yıllık Doğa Değişimi", f"%{loss_rate}", delta=f"-{loss_rate}%", delta_color="inverse")
            with m2:
                if loss_rate > 40:
                    st.error(report_text)
                elif loss_rate > 15:
                    st.warning(report_text)
                else:
                    st.success(report_text)
# ---------------------------------------
            
            # DB'ye Kaydet (Day 4-5)
            folder_path = f"data/analyses/{analiz_id}/"
            finalize_analysis_in_db(analiz_id, folder_path, loss_rate, report_text)