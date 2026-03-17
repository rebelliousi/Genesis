import ee
import os
import time
import requests
from dotenv import load_dotenv

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# --- GOOGLE EARTH ENGINE BAŞLATMA ---
try:
    ee.Initialize(project=os.getenv("PRO_ID"))
except Exception as e:
    print(f"❌ GEE Başlatılamadı: {e}")

def calculate_ndvi_value(image, satellite, point):
    """
    GÜN 5: Belirli bir nokta için bilimsel NDVI (Yeşillik Sağlığı) değerini hesaplar.
    Formül: (NIR - RED) / (NIR + RED)
    """
    if not image:
        return 0
    
    try:
        # Uydu sensör tipine göre doğru bandları eşleştir
        if "LM02" in satellite:  # 1975 Landsat 2 (MSS)
            nir = 'B6'
            red = 'B5'
        elif "LE07" in satellite:  # 2000 Landsat 7 (ETM+)
            nir = 'SR_B4'
            red = 'SR_B3'
        else:  # 2024 Landsat 8 (OLI)
            nir = 'SR_B5'
            red = 'SR_B4'

        # NDVI hesapla: (NIR - RED) / (NIR + RED)
        ndvi_image = image.normalizedDifference([nir, red])
        
        # Nokta üzerindeki ortalama NDVI değerini çıkar (Reduce)
        stats = ndvi_image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point,
            scale=30,
            maxPixels=1e9
        ).getInfo()
        
        # 'nd' anahtarındaki değeri döndür (Genelde 0 ile 1 arasıdır)
        return stats.get('nd', 0)
    except Exception as e:
        print(f"⚠️ NDVI Hesaplama Hatası ({satellite}): {e}")
        return 0

def analyze_restoration_need(ndvi_old, ndvi_new):
    """
    GÜN 5: Trading mantığı (RSI gibi) kullanarak değişim analizi yapar.
    Kayıp > %40 ise KRİTİK olarak işaretler.
    """
    if ndvi_old is None or ndvi_old <= 0:
        return 0, "Yetersiz Veri"
    
    # Kayıp oranını hesapla
    diff_rate = ((ndvi_old - ndvi_new) / ndvi_old) * 100
    
    # Durum kuralı (Thresholding)
    if diff_rate > 40:
        status = "🔴 KRİTİK: Ciddi Doğa Kaybı (Acil Restorasyon Şart)"
    elif diff_rate > 15:
        status = "🟡 UYARI: Orta Seviye Bozulma (İyileştirme Tavsiye Edilir)"
    elif diff_rate < -5:
        status = "🟢 BAŞARILI: Doğa Kendini Yenilemiş (Pozitif Gelişim)"
    else:
        status = "⚪ STABİL: Doğa Dengede"
        
    return round(diff_rate, 2), status

def get_temporal_chunks(lat, lng):
    """3 farklı yıla ait uydu görüntülerini çeker (Retry Mekanizmalı)"""
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
                    results.append({"year": year["label"], "image_id": "Hata", "image": None, "satellite": year["satellite"]})
    
    return results

def get_thumbnail_url(image, lat, lng, satellite):
    """Görüntüyü GEE üzerinden bir PNG URL'sine çevirir."""
    if not image: return None
    
    point = ee.Geometry.Point([lng, lat])
    region = point.buffer(5000).bounds() # 5km'lik bir alan daha net analiz sağlar
    
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

def save_image_to_disk(url, analiz_id, year_label):
    """GÜN 4: Görüntüyü fiziksel diske kaydeder (Block Server)."""
    if not url: return None
    
    base_dir = "data/analyses"
    target_dir = os.path.join(base_dir, str(analiz_id))
    
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
    
    file_path = os.path.join(target_dir, f"{year_label}.png")
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(response.content)
            return file_path
    except Exception as e:
        print(f"❌ Kayıt Hatası: {e}")
    return None

# --- 🧪 TEST BLOĞU (İmleç İzleği Burada Başlar) ---
if __name__ == "__main__":
    lat, lng = 39.6992, 26.8735 # Örnek koordinat
    print(f"🚀 GÜN 5: {lat}, {lng} için NDVI Analiz Motoru Başlatılıyor...")
    
    chunks = get_temporal_chunks(lat, lng)
    point = ee.Geometry.Point([lng, lat])
    
    ndvi_results = {}
    
    for chunk in chunks:
        if chunk['image']:
            # 1. NDVI hesapla
            val = calculate_ndvi_value(chunk['image'], chunk['satellite'], point)
            ndvi_results[chunk['year']] = val
            print(f"📊 Yıl: {chunk['year']} | NDVI Değeri: {round(val, 4)}")
            
            # 2. Resmi diske kaydet (Day 4 özelliği hala aktif)
            url = get_thumbnail_url(chunk['image'], lat, lng, chunk['satellite'])
            save_image_to_disk(url, "TEST_G5", chunk['year'])

    # 3. Kıyasla (1975 vs 2024)
    kayip, rapor = analyze_restoration_need(ndvi_results.get("1975"), ndvi_results.get("2024"))
    print("-" * 30)
    print(f"📉 50 Yıllık Doğa Kaybı: %{kayip}")
    print(f"📝 Sonuç: {rapor}")