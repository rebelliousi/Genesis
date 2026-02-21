import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import folium
from streamlit_folium import st_folium

def get_all_requests():
    conn=sqlite3.connect('genesis.db')
    df=pd.read_sql_query("SELECT * FROM analysis_requests ORDER  BY created_at DESC",conn)
    conn.close()
    return df

def add_coordinate(lat,lng):
    conn=sqlite3.connect('genesis.db')
    cursor=conn.cursor()
    cursor.execute('INSERT INTO analysis_requests(latitude,longitude,status) VALUES (?, ?,?)',(lat,lng,"PENDING"))
    conn.commit()
    conn.close()





def get_satellite_map(lat,lng):
    m=folium.Map(location=[lat,lng],zoom_start=15)
    esri_satellite="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"

    folium.TileLayer(
        tiles=esri_satellite,
        attr='Esri',
        name="Esri Satellite",
        overlay=False,
        control=True
    ).add_to(m)

    folium.Marker([lat,lng],popup="Analiz bolgesi").add_to(m)

    return m


st.set_page_config(page_title="Project GENESIS",layout="wide")

st.title("Project GENESIS:Global Bio-Restoration")
st.markdown("DUnyayi iyileshitmek ichin bir koordinat secin ve 50 yillik degsihimi analiz edin")

with st.sidebar:
    st.header("Yeni analzi bashlat")
    lat_input=st.number_input("EYlem (Latitude)",value=39.6992,format="%.4f")
    lng_input=st.number_input("BOylam(Longitude)", value=26.8735, format="%.4f")

    if st.button("Sisteme kaydet"):
        add_coordinate(lat_input,lng_input)
        st.session_state['active_lat']=lat_input
        st.session_state['active_lng']=lng_input
        st.rerun()

col1,col2=st.columns([2,1])

with col1:
    st.subheader("Analiz Haritasi")
    if 'active_lat' in st.session_state:
        m=get_satellite_map(st.session_state['active_lat'],st.session_state['active_lng'])
        st_folium(m,width=700,height=500)

    else:
        st.info('soldan bir koordinat girin ve analizi bashlata basin')
with col2:
    st.subheader("Gecmish analizler Metadata")
    df=get_all_requests()
    if not df.empty:
        st.dataframe(df[['id','latitude','longitude','status','created_at']], )
    else:
        st.write("Liste bosh")