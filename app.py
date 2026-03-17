import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium
import ee
from gee_service import get_thumbnail_url
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
# Uygulama yenilendiğinde koordinatların kaybolmaması için
if 'active_lat' not in st.session_state:
    st.session_state['active_lat'] = 39.6992
if 'active_lng' not in st.session_state:
    st.session_state['active_lng'] = 26.8735
if 'show_satellites' not in st.session_state:
    st.session_state['show_satellites'] = False

# --- VERİTABANI FONKSİYONLARI ---
@st.cache_data(ttl=5)
def get_all_requests():
    conn = sqlite3.connect('genesis.db')
    df = pd.read_sql_query("SELECT * FROM analysis_requests ORDER BY created_at DESC", conn)
    conn.close()
    return df

def add_coordinate(lat, lng):
    # --- 1. VALIDASYON (GEÇERLİLİK KONTROLÜ) ---
    if not (-90 <= lat <= 90):
        st.error("Enlem (Latitude) -90 ile 90 arasında olmalıdır!")
        return False
    if not (-180 <= lng <= 180):
        st.error("Boylam (Longitude) -180 ile 180 arasında olmalıdır!")
        return False
    
    try:
        conn = sqlite3.connect('genesis.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO analysis_requests(latitude,longitude,status) VALUES (?,?,?)', (lat, lng, "PENDING"))
        conn.commit()
        conn.close()
        st.success("Koordinat başarıyla sisteme kaydedildi!")
        return True
    except Exception as e:
        st.error(f"Veritabanı hatası: {e}")
        return False

# --- HARİTA FONKSİYONU ---
def get_satellite_map(lat, lng):
    m = folium.Map(location=[lat, lng], zoom_start=15)
    esri_satellite = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    folium.TileLayer(
        tiles=esri_satellite, 
        attr='Esri', 
        name="Esri Satellite", 
        overlay=False, 
        control=True
    ).add_to(m)
    folium.Marker([lat, lng], popup=f"Seçili: {lat}, {lng}").add_to(m)
    return m

# --- SAYFA TASARIMI ---
st.set_page_config(page_title="Project GENESIS", layout="wide")
st.title("Project GENESIS: Global Bio-Restoration")
st.markdown("Dünyayı iyileştirmek için bir koordinat seçin (Haritaya tıklayabilir veya manuel girebilirsiniz)")

# --- YAN PANEL (SIDEBAR) ---
with st.sidebar:
    st.header("📍 Analiz Parametreleri")
    
    # Inputlar Session State'den beslenir, böylece haritaya tıklandığında buralar güncellenir
    lat_input = st.number_input("Enlem (Latitude)", 
                                value=float(st.session_state['active_lat']), 
                                format="%.4f", 
                                step=0.0001)
    lng_input = st.number_input("Boylam (Longitude)", 
                                value=float(st.session_state['active_lng']), 
                                format="%.4f", 
                                step=0.0001)

    if st.button("💾 Sisteme Kaydet"):
        if add_coordinate(lat_input, lng_input):
            # Kayıttan sonra state'i güncelle ve sayfayı yenile
            st.session_state['active_lat'] = lat_input
            st.session_state['active_lng'] = lng_input
            st.rerun()

    if st.button("🛰️ 50 Yıllık Değişimi Analiz Et"):
        st.session_state['show_satellites'] = True

# --- ANA PANEL (HARİTA VE TABLO) ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🗺️ İnteraktif Seçim Haritası")
    # Haritayı oluştur
    base_map = get_satellite_map(st.session_state['active_lat'], st.session_state['active_lng'])
    
    # --- 2. HARİTADAN TIKLAYARAK SEÇME (PRO ÖZELLİK) ---
    map_data = st_folium(base_map, width=700, height=500, key="main_map")
    
    # Eğer haritada bir yere tıklandıysa koordinatları yakala
    if map_data and map_data.get('last_clicked'):
        clicked_lat = map_data['last_clicked']['lat']
        clicked_lng = map_data['last_clicked']['lng']
        
        # Eğer tıklanan yer mevcut koordinattan farklıysa güncelle
        if clicked_lat != st.session_state['active_lat']:
            st.session_state['active_lat'] = clicked_lat
            st.session_state['active_lng'] = clicked_lng
            st.rerun()

with col2:
    st.subheader("📜 Son İstekler")
    df = get_all_requests()
    if not df.empty:
        st.dataframe(df[['id', 'latitude', 'longitude', 'status', 'created_at']], use_container_width=True)
    else:
        st.info("Henüz analiz talebi bulunmuyor.")

# --- UYDU GÖRÜNTÜLERİ ALANI ---
if st.session_state['show_satellites']:
    st.divider()
    st.subheader(f"🛰️ 50 Yıllık Değişim Analizi ({st.session_state['active_lat']:.4f}, {st.session_state['active_lng']:.4f})")
    
    YEARS = [
        {"label": "1975 (Landsat 2)", "start": "1975-01-01", "end": "1975-12-31", "satellite": "LANDSAT/LM02/C02/T2"},
        {"label": "2000 (Landsat 7)", "start": "2000-01-01", "end": "2000-12-31", "satellite": "LANDSAT/LE07/C02/T1_L2"},
        {"label": "2024 (Landsat 8)", "start": "2024-01-01", "end": "2024-12-31", "satellite": "LANDSAT/LC08/C02/T1_L2"},
    ]
    
    # Seçili koordinatı GEE formatına çevir
    point = ee.Geometry.Point([st.session_state['active_lng'], st.session_state['active_lat']])
    
    cols = st.columns(3)
    
    for i, year in enumerate(YEARS):
        with cols[i]:
            with st.spinner(f"{year['label']} hazırlanıyor..."):
                try:
                    # GEE üzerinden filtreleme yap
                    image = (
                        ee.ImageCollection(year["satellite"])
                        .filterBounds(point)
                        .filterDate(year["start"], year["end"])
                        .sort("CLOUD_COVER")
                        .first()
                    )
                    
                    # Önizleme URL'sini gee_service'den al
                    url = get_thumbnail_url(image, st.session_state['active_lat'], st.session_state['active_lng'], year["satellite"])
                    
                    st.image(url, caption=year["label"], use_container_width=True)
                except Exception as e:
                    st.error(f"{year['label']} verisi yüklenemedi.")
                    # st.write(e) # Debug için hatayı açabilirsin