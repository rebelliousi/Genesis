import sqlite3
from datetime import datetime
from contextlib import contextmanager

@contextmanager
def get_db():
    conn = sqlite3.connect('genesis.db')
    conn.row_factory = sqlite3.Row # Bu çok önemli! Verileri (0,1,2) diye değil 'id', 'lat' diye çekmeni sağlar.
    try:
        yield conn
        conn.commit() # Her şey yolundaysa otomatik kaydet
    except Exception as e:
        conn.rollback() # Hata varsa yapılanları geri al (Veri güvenliği)
        raise e
    finally:
        conn.close() # Ne olursa olsun bağlantıyı kapat

def setup_table():
    """
    GÜN 1-6: Tüm analiz verilerini ve metadata bilgilerini 
    saklayacak şekilde tabloyu inşa eder.
    """
    with get_db() as conn:

    # Tablo yapısı: 
    # ndvi_diff -> Bilimsel kayıp oranı (%) (Day 5)
    # image_folder -> Resimlerin fiziksel yolu (Day 4)
    # ai_plan -> Analiz sonucu/raporu (Day 5)
     conn.execute('''
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

  
    print("✅ Veritabanı Altyapısı Hazır: GÜN 6 (De-duplication) uyumlu.")

def save_analysis(lat, lng, status='PENDING', **kwargs):
    """Hem yeni kayıt açar hem de mevcut kaydı günceller."""
    with get_db() as conn:
        # Eğer kwargs içinde 'id' varsa bu bir güncellemedir
        if 'id' in kwargs:
            analiz_id = kwargs.pop('id')
            # Dinamik olarak hangi kolonlar gelirse onları UPDATE sorgusuna ekle
            cols = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            vals = list(kwargs.values())
            vals.append(analiz_id)
            conn.execute(f"UPDATE analysis_requests SET {cols} WHERE id = ?", vals)
            return analiz_id
        else:
            # Yeni kayıt açma (Insert)
            cursor = conn.execute(
                "INSERT INTO analysis_requests(latitude, longitude, status) VALUES(?, ?, ?)", 
                (lat, lng, status)
            )
            return cursor.lastrowid
# --- 🚀 GÜN 6 GÜNCELLEMESİ: DE-DUPLICATION (TEKİLLEŞTİRME) ---
def check_existing_analysis(lat, lng):
    """
    Alex Xu Ch.15: De-duplication (Tekilleştirme) mantığı.
    Aynı koordinatın daha önce analiz edilip edilmediğini kontrol eder.
    Hassasiyet: 4 ondalık basamak (yaklaşık 11 metre).
    """
    with get_db() as conn:

    # Koordinatları 4 basamağa yuvarlayarak veritabanında ara
     res=conn.execute('''
        SELECT * FROM analysis_requests 
        WHERE ROUND(latitude, 4) = ROUND(?, 4) 
        AND ROUND(longitude, 4) = ROUND(?, 4) 
        AND status = 'COMPLETED'
        ORDER BY created_at DESC LIMIT 1
    ''', (lat, lng)).fetchone()
    
    return dict(res) if res else None

def get_all_request():
    """Tüm talepleri getirir."""
    with get_db() as conn:
     conn.execute('''
        SELECT id, latitude, longitude, status, ndvi_diff, created_at 
        FROM analysis_requests 
        ORDER BY created_at DESC
    ''')
    rows = conn.fetchall()
    conn.close()
    return rows

# --- 🧪 TEST VE BAŞLATMA ---
if __name__ == "__main__":
    setup_table()
    
    # GÜN 6 Testi
    test_lat, test_lng = 39.6992, 26.8735
    print("\n--- GÜN 6: De-duplication Testi ---")
    
    # Önce kontrol et (Eğer veritabanın boşsa None döner)
    exists = check_existing_analysis(test_lat, test_lng)
    
    if exists:
        print(f"✨ Kayıt bulundu! Analiz ID: {exists[0]} | Sonuç: %{exists[4]}")
    else:
        print("🆕 Bu koordinat daha önce analiz edilmemiş. Yeni kayıt oluşturuluyor...")
        new_id = add_coordinate(test_lat, test_lng)
        update_analysis_results(new_id, 42.5, "🔴 KRİTİK", f"data/analyses/{new_id}/")
        print(f"✅ Yeni analiz tamamlandı ve kaydedildi. ID: {new_id}")