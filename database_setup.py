import sqlite3
from datetime import datetime

def create_connection():
    """Veritabanı bağlantısını oluşturur."""
    conn = sqlite3.connect('genesis.db')
    return conn

def setup_table():
    """
    GÜN 5 GÜNCELLEMESİ: 
    Tabloyu tüm analiz verilerini (NDVI kaybı, AI planı, Klasör yolu) 
    saklayacak şekilde inşa eder.
    """
    conn = create_connection()
    cursor = conn.cursor()

    # Tablo yapısı: 
    # ndvi_diff -> Bilimsel kayıp oranı (%)
    # image_folder -> Resimlerin fiziksel yolu (Day 4)
    # ai_plan -> Analiz sonucu/raporu (Day 5)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS analysis_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        status TEXT DEFAULT 'PENDING',
        ndvi_diff REAL,              
        image_folder TEXT,           
        ai_plan TEXT,                
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()
    print("✅ Veritabanı Altyapısı Hazır: GÜN 5 (Analiz Motoru) uyumlu.")

def add_coordinate(lat, lng):
    """
    Yeni bir analiz talebi ekler ve klasör oluşturma/analiz takibi için 
    oluşturulan benzersiz ID'yi döndürür.
    """
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        INSERT INTO analysis_requests(latitude, longitude, status)
        VALUES(?, ?, ?)
        ''', (lat, lng, "PENDING")
    )
    
    # Yeni eklenen satırın ID'sini al (Day 4 & 5 için kritik!)
    new_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return new_id

# --- 🚀 GÜN 5 GÜNCELLEMESİ: MERKEZİ GÜNCELLEME FONKSİYONU ---
def update_analysis_results(analiz_id, ndvi_diff, ai_report, folder_path):
    """
    Analiz tamamlandığında; hesaplanan kaybı, raporu ve dosya yolunu 
    tek seferde veritabanına işler ve durumu 'COMPLETED' yapar.
    """
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        UPDATE analysis_requests 
        SET ndvi_diff = ?, 
            ai_plan = ?, 
            image_folder = ?, 
            status = 'COMPLETED' 
        WHERE id = ?
        ''', (ndvi_diff, ai_report, folder_path, analiz_id)
    )

    conn.commit()
    conn.close()
    print(f"📊 Analiz #{analiz_id} sonuçları (NDVI: %{ndvi_diff}) başarıyla arşive işlendi.")

def get_all_request():
    """Tüm talepleri en yeni en üstte olacak şekilde getirir."""
    conn = create_connection()
    cursor = conn.cursor()
    # Ekranda göstermek istediğimiz kolonları seçiyoruz
    cursor.execute('''
        SELECT id, latitude, longitude, status, ndvi_diff, created_at 
        FROM analysis_requests 
        ORDER BY created_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- TEST VE BAŞLATMA ---
if __name__ == "__main__":
    # 1. Tabloyu kur/güncelle
    setup_table()
    
    # 2. Test: Yeni bir talep oluştur
    print("\n--- Test İşlemi Başlıyor ---")
    test_id = add_coordinate(39.6992, 26.8735)
    print(f"1. Yeni talep eklendi. ID: {test_id}")
    
    # 3. Test: Analiz sonuçlarını simüle et (Day 5 Mantığı)
    mock_ndvi_loss = 35.4
    mock_report = "🟡 UYARI: Orta seviye bozulma tespit edildi."
    mock_folder = f"data/analyses/{test_id}/"
    
    update_analysis_results(test_id, mock_ndvi_loss, mock_report, mock_folder)
    print(f"2. Analiz sonuçları güncellendi.")
    
    # 4. Test: Listele
    print("\n--- Güncel Kayıtlar ---")
    requests = get_all_request()
    for req in requests[:3]: # Son 3 kaydı göster
        print(f"ID: {req[0]} | Durum: {req[3]} | Kayıp: %{req[4]}")