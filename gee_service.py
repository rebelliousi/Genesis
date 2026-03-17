import ee
import os
import time
import requests  # Görüntüleri internetten indirip kaydetmek için
from dotenv import load_dotenv

load_dotenv()

# --- GOOGLE EARTH ENGINE BAŞLATMA ---
try:
    ee.Initialize(project=os.getenv("PRO_ID"))
except Exception as e:
    print(f"❌ GEE Başlatılamadı: {e}")

def get_temporal_chunks(lat, lng):
    """3 farklı yıla ait uydu görüntülerini çeker (Retry Mekanizması ile)"""
    point = ee.Geometry.Point([lng, lat])
    
    years = [
        {"label": "1975", "start": "1975-01-01", "end": "1975-12-31", "satellite": "LANDSAT/LM02/C02/T2"},
        {"label": "2000", "start": "2000-01-01", "end": "2000-12-31", "satellite": "LANDSAT/LE07/C02/T1_L2"},
        {"label": "2024", "start": "2024-01-01", "end": "2024-12-31", "satellite": "LANDSAT/LC08/C02/T1_L2"},
    ]
    
    results = []
    
    for year in years:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                collection = (
                    ee.ImageCollection(year["satellite"])
                    .filterBounds(point)
                    .filterDate(year["start"], year["end"])
                    .sort("CLOUD_COVER")
                    .first()
                )
                
                info = collection.getInfo()
                
                results.append({
                    "year": year["label"],
                    "image_id": info['id'] if info else "Görüntü bulunamadı",
                    "image": collection,
                    "satellite": year["satellite"]
                })
                break
                
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    results.append({"year": year["label"], "image_id": "Hata", "image": None})
    
    return results

def get_thumbnail_url(image, lat, lng, satellite):
    """Görüntüyü GEE üzerinden bir PNG URL'sine çevirir."""
    if not image: return None
    
    point = ee.Geometry.Point([lng, lat])
    region = point.buffer(10000).bounds()
    
    # Görselleştirme ayarları (Landsat versiyonlarına göre)
    if "LM02" in satellite: # 1975
        bands = ['B6', 'B5', 'B4']; min_val, max_val = 0, 100
    elif "LE07" in satellite: # 2000
        bands = ['SR_B3', 'SR_B2', 'SR_B1']; min_val, max_val = 7000, 15000
    else: # 2024
        bands = ['SR_B4', 'SR_B3', 'SR_B2']; min_val, max_val = 7000, 15000

    try:
        url = image.getThumbURL({
            'min': min_val, 'max': max_val, 'bands': bands,
            'region': region, 'dimensions': 512, 'format': 'png'
        })
        return url
    except:
        return None

# --- 📂 GÜN 4: BLOCK SERVER - DISKE KAYDETME MANTIĞI ---
def save_image_to_disk(url, analiz_id, year_label):
    """
    Google'dan gelen URL'yi indirir ve 'data/analyses/ID/' klasörüne kaydeder.
    Alex Xu Ch.15: Block Server - Veriyi fiziksel olarak bloklara ayırıp saklama.
    """
    if not url: return None
    
    # Klasör yapısını oluştur: data/analyses/1/ (Örneğin analiz ID'si 1 ise)
    base_dir = "data/analyses"
    target_dir = os.path.join(base_dir, str(analiz_id))
    
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
    
    file_name = f"{year_label}.png"
    file_path = os.path.join(target_dir, file_name)
    
    try:
        # Resmi internetten indir
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ Kaydedildi: {file_path}")
            return file_path
        else:
            print(f"❌ İndirme hatası: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Dosya kaydetme hatası: {e}")
        return None

# --- TEST BLOĞU ---
if __name__ == "__main__":
    test_lat, test_lng = 39.6992, 26.8735
    test_analiz_id = 101 # Deneme için bir ID veriyoruz
    
    print(f"🚀 {test_lat}, {test_lng} için Zaman Yolculuğu Başlıyor...")
    
    chunks = get_temporal_chunks(test_lat, test_lng)
    
    for chunk in chunks:
        if chunk['image']:
            # 1. URL'yi al
            url = get_thumbnail_url(chunk['image'], test_lat, test_lng, chunk['satellite'])
            
            # 2. URL'yi fiziksel olarak diske kaydet (GÜN 4)
            path = save_image_to_disk(url, test_analiz_id, chunk['year'])
            
            if path:
                print(f"📅 Yıl: {chunk['year']} | 📂 Dosya Yolu: {path}")
            else:
                print(f"📅 Yıl: {chunk['year']} | ❌ Dosya kaydedilemedi.")