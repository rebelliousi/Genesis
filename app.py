import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium
import ee
from gee_service import get_thumbnail_url
from dotenv import load_dotenv
import os

load_dotenv()
ee.Initialize(project=os.getenv("PRO_ID"))

@st.cache_data(ttl=5)
def get_all_requests():
    conn = sqlite3.connect('genesis.db')
    df = pd.read_sql_query("SELECT * FROM analysis_requests ORDER BY created_at DESC", conn)
    conn.close()
    return df

def add_coordinate(lat, lng):
    conn = sqlite3.connect('genesis.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO analysis_requests(latitude,longitude,status) VALUES (?,?,?)', (lat, lng, "PENDING"))
    conn.commit()
    conn.close()

def get_satellite_map(lat, lng):
    m = folium.Map(location=[lat, lng], zoom_start=15)
    esri_satellite = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    folium.TileLayer(tiles=esri_satellite, attr='Esri', name="Esri Satellite", overlay=False, control=True).add_to(m)
    folium.Marker([lat, lng], popup="Analiz bolgesi").add_to(m)
    return m

YEARS = [
    {"label": "1975", "start": "1975-01-01", "end": "1975-12-31", "satellite": "LANDSAT/LM02/C02/T2"},
    {"label": "2000", "start": "2000-01-01", "end": "2000-12-31", "satellite": "LANDSAT/LE07/C02/T1_L2"},
    {"label": "2024", "start": "2024-01-01", "end": "2024-12-31", "satellite": "LANDSAT/LC08/C02/T1_L2"},
]

st.set_page_config(page_title="Project GENESIS", layout="wide")
st.title("Project GENESIS: Global Bio-Restoration")
st.markdown("Dünyayı iyileştirmek için bir koordinat seçin ve 50 yıllık değişimi analiz edin")

with st.sidebar:
    st.header("Yeni Analiz Başlat")
    lat_input = st.number_input("Enlem (Latitude)", value=39.6992, format="%.4f")
    lng_input = st.number_input("Boylam (Longitude)", value=26.8735, format="%.4f")

    if st.button("Sisteme Kaydet"):
        add_coordinate(lat_input, lng_input)
        st.session_state['active_lat'] = lat_input
        st.session_state['active_lng'] = lng_input
        st.rerun()

    if st.button("🛰️ 50 Yıllık Uydu Görüntüleri"):
        st.session_state['show_satellites'] = True

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Analiz Haritası")
    if 'active_lat' in st.session_state:
        m = get_satellite_map(st.session_state['active_lat'], st.session_state['active_lng'])
        st_folium(m, width=700, height=500)
    else:
        st.info('Soldan bir koordinat girin ve analizi başlatın')

with col2:
    st.subheader("Geçmiş Analizler")
    df = get_all_requests()
    if not df.empty:
        st.dataframe(df[['id', 'latitude', 'longitude', 'status', 'created_at']])
    else:
        st.write("Liste boş")

if st.session_state.get('show_satellites'):
    st.subheader("🛰️ 50 Yıllık Değişim")
    point = ee.Geometry.Point([lng_input, lat_input])
    cols = st.columns(3)
    for i, year in enumerate(YEARS):
        image = (
            ee.ImageCollection(year["satellite"])
            .filterBounds(point)
            .filterDate(year["start"], year["end"])
            .sort("CLOUD_COVER")
            .first()
        )
        url = get_thumbnail_url(image, lat_input, lng_input, year["satellite"])
        cols[i].image(url, caption=year["label"], use_container_width=True)