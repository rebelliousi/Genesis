import sqlite3
from datetime import datetime
def create_connection():
    """it will create database file and make it work"""
    conn=sqlite3.connect('genesis.db')
    return conn

def setup_table():
    conn=create_connection()
    cursor=conn.cursor()


    '''creating table'''
    cursor.execute('''
   CREATE TABLE IF NOT EXISTS analysis_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        status TEXT DEFAULT 'PENDING',
        ndvi_diff REAL,
        ai_plan TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                   )
                   
'''
    )

    conn.commit()
    conn.close()

if __name__ =="__main__":
    setup_table()