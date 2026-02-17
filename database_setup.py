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

def add_test_coordinate(lat,lng):
    conn=create_connection()
    cursor=conn.cursor()



    '''new coordinate adding'''
    cursor.execute(
        '''
     INSERT INTO analysis_requests(latitude,longitude)
     VALUES(? , ?)
''',(lat,lng)
    )
    conn.commit()
    conn.close()

# def get_all_request():
#     conn=create_connection()
#     cursor=conn.cursor()

#     cursor.execute('SELECT * FROM analysis_requests')

#     rows=cursor.fetchall()

#     for row in rows:
    
#         print(f"ID:{row[0]} | Coordinate:{row[1],row[2]} | Situation:{row[3]} | Date:{row[6]}")
#     conn.close()


if __name__ =="__main__":
    setup_table()

    add_test_coordinate(39.6992, 26.8735)
    # get_all_request()