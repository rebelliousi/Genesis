import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium
import ee
# gee_service'den gerekli tüm fonksiyonları alıyoruz
from gee_service import get_thumbnail_url, get_temporal_chunks, save_image_to_disk
from dotenv import load_dotenv
import os

# --- BAŞLANGIÇ AYARLARI ---
load_dotenv()
try:
    # GEE projesini başlat
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
    df = pd.read_sql_query("SELECT * FROM analysis_requests ORDER BY created_at DESC", conn)
    conn.close()
    return df

def add_coordinate(lat, lng):
    """Koordinatı kaydeder ve yeni oluşan Analiz ID'sini döndürür."""
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        st.error("Hatalı koordinat aralığı!")
        return None
    
    try:
        conn = sqlite3.connect('genesis.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO analysis_requests(latitude,longitude,status) VALUES (?,?,?)', (lat, lng, "PENDING"))
        new_id = cursor.lastrowid # GÜN 4: Oluşan ID'yi yakalıyoruz
        conn.commit()
        conn.close()
        return new_id
    except Exception as e:
        st.error(f"Veritabanı hatası: {e}")
        return None

def update_db_after_analysis(analiz_id, folder_path):
    """Analiz tamamlandığında DB'yi günceller (GÜN 4)."""
    conn = sqlite3.connect('genesis.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE analysis_requests SET image_folder = ?, status = ? WHERE id = ?', 
                   (folder_path, "COMPLETED", analiz_id))
    conn.commit()
    conn.close()

# --- HARİTA FONKSİYONU ---
def get_satellite_map(lat, lng):
    m = folium.Map(location=[lat, lng], zoom_start=15)
    esri_satellite = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    folium.TileLayer(tiles=esri_satellite, attr='Esri', name="Esri Satellite", overlay=False).add_to(m)
    folium.Marker([lat, lng], popup=f"Seçili: {lat}, {lng}").add_to(m)
    return m

# --- SAYFA TASARIMI ---
st.set_page_config(page_title="Project GENESIS", layout="wide")
st.title("Project GENESIS: Global Bio-Restoration")

# --- YAN PANEL (SIDEBAR) ---
with st.sidebar:
    st.header("📍 Analiz Paneli")
    lat_input = st.number_input("Enlem", value=float(st.session_state['active_lat']), format="%.4f")
    lng_input = st.number_input("Boylam", value=float(st.session_state['active_lng']), format="%.4f")

    if st.button("💾 Sisteme Kaydet"):
        new_id = add_coordinate(lat_input, lng_input)
        if new_id:
            st.session_state['current_id'] = new_id
            st.session_state['active_lat'] = lat_input
            st.session_state['active_lng'] = lng_input
            st.success(f"Analiz #{new_id} kaydedildi.")
            st.rerun()

    if st.button("🛰️ 50 Yıllık Analizi Başlat"):
        # Eğer henüz kaydedilmemişse önce kaydet
        if st.session_state['current_id'] is None:
            st.session_state['current_id'] = add_coordinate(lat_input, lng_input)
        st.session_state['show_satellites'] = True

# --- ANA PANEL ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🗺️ Bölge Seçimi")
    m = get_satellite_map(st.session_state['active_lat'], st.session_state['active_lng'])
    map_data = st_folium(m, width=700, height=500, key="main_map")
    
    # Haritadan tıklama ile seçim
    if map_data and map_data.get('last_clicked'):
        c_lat, c_lng = map_data['last_clicked']['lat'], map_data['last_clicked']['lng']
        if c_lat != st.session_state['active_lat']:
            st.session_state['active_lat'] = c_lat
            st.session_state['active_lng'] = c_lng
            st.session_state['current_id'] = None # Yeni yer seçilince ID'yi sıfırla
            st.rerun()

with col2:
    st.subheader("📜 Son İstekler")
    df = get_all_requests()
    if not df.empty:
        # DB'ye yeni eklediğimiz image_folder ve status'ü gösteriyoruz
        st.dataframe(df[['id', 'latitude', 'longitude', 'status']], use_container_width=True)

# --- 🛰️ GÜN 4: ANALİZ VE BLOCK SERVER (DEPOLAMA) BÖLÜMÜ ---
if st.session_state['show_satellites'] and st.session_state['current_id']:
    st.divider()
    analiz_id = st.session_state['current_id']
    st.subheader(f"📊 Analiz Raporu: #{analiz_id}")
    
    cols = st.columns(3)
    
    # GEE Servisinden verileri çekiyoruz
    with st.spinner("Uydular taranıyor ve görüntüler yerel arşive indiriliyor..."):
        # 1. GEE'den görüntüleri bul (Retry mekanizmalı servisimiz)
        chunks = get_temporal_chunks(st.session_state['active_lat'], st.session_state['active_lng'])
        
        saved_paths = []
        
        for i, chunk in enumerate(chunks):
            if chunk['image']:
                # 2. Resim URL'sini al
                url = get_thumbnail_url(chunk['image'], st.session_state['active_lat'], st.session_state['active_lng'], chunk['satellite'])
                
                # 3. Resme fiziksel olarak diske kaydet (BLOCK SERVER)
                local_path = save_image_to_disk(url, analiz_id, chunk['year'])
                
                # 4. Ekranda göster
                with cols[i]:
                    st.image(url, caption=f"{chunk['year']} (Arşivlendi)", use_container_width=True)
                    if local_path:
                        saved_paths.append(local_path)
        
        # 5. Başarıyla indirildiyse Veritabanını güncelle
        if len(saved_paths) > 0:
            final_folder = f"data/analyses/{analiz_id}/"
            update_db_after_analysis(analiz_id, final_folder)
            st.success(f"✅ Başarılı! Görüntüler '{final_folder}' klasörüne bloklar halinde kaydedildi.")