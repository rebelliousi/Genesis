import sqlite3
from datetime import datetime

def create_connection():
    """Veritabanı bağlantısını oluşturur."""
    conn = sqlite3.connect('genesis.db')
    return conn

def setup_table():
    conn = create_connection()
    cursor = conn.cursor()

    # GÜN 4 GÜNCELLEMESİ: 'image_folder' sütunu eklendi
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS analysis_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        status TEXT DEFAULT 'PENDING',
        ndvi_diff REAL,
        image_folder TEXT, -- Resimlerin saklandığı klasör yolu (GÜN 4)
        ai_plan TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()
    print("✅ Veritabanı ve Tablo güncellendi.")

def add_coordinate(lat, lng):
    """Yeni bir analiz talebi ekler ve oluşturulan kaydın ID'sini döndürür."""
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        INSERT INTO analysis_requests(latitude, longitude, status)
        VALUES(?, ?, ?)
        ''', (lat, lng, "PENDING")
    )
    
    # Yeni eklenen satırın ID'sini al (Klasör oluşturmak için lazım!)
    new_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return new_id

def update_image_path(analiz_id, folder_path):
    """Analiz bittikten sonra resim klasör yolunu DB'ye yazar."""
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        UPDATE analysis_requests 
        SET image_folder = ?, status = 'COMPLETED' 
        WHERE id = ?
        ''', (folder_path, analiz_id)
    )

    conn.commit()
    conn.close()

def get_all_request():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM analysis_requests ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

if __name__ == "__main__":
    setup_table()
    # Test: Bir koordinat ekle ve dönen ID'yi gör
    test_id = add_coordinate(39.6992, 26.8735)
    print(f"🚀 Test kaydı eklendi. Analiz ID: {test_id}")
    
    # Test: Klasör yolunu güncelle
    update_image_path(test_id, f"data/analyses/{test_id}/")
    print(f"📁 Klasör yolu güncellendi: data/analyses/{test_id}/")