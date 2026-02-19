import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

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

st.set_page_config(page_title="Project GENESIS",layout="wide")

st.title("Project GENESIS:Global Bio-Restoration")
st.markdown("DUnyayi iyileshitmek ichin bir koordinat secin ve 50 yillik degsihimi analiz edin")

with st.sidebar:
    st.header("Yeni analzi bashlat")
    lat_input=st.number_input("EYlem (Latitude)",value=39.6992,format="%.4f")
    lng_input=st.number_input("BOylam(Longitude)", value=26.8735, format="%.4f")

    if st.button("Sisteme kaydet"):
        add_coordinate(lat_input,lng_input)
        st.success('Koordinat Metadata db-ye eklendi')
        st.rerun()

col1,col2=st.columns([2,1])

with col1:
    st.subheader("Analiz Haritasi")
    df=get_all_requests()
    if not df.empty:
        st.map(df[['latitude','longitude']].rename(columns={'latitude':'lat','longitude':'lon'}))
    else:
        st.write('henuz analiz talebi yok')
with col2:
    st.subheader("Gecmish analizler Metadata")

    if not df.empty:
        st.dataframe(df[['id','latitude','longitude','status','created_at']], use_container_width=True)
    else:
        st.write("Liste bosh")