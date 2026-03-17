import ee
import os
import time  # Yeniden denemeler arasında beklemek için
from dotenv import load_dotenv

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# --- GOOGLE EARTH ENGINE BAŞLATMA ---
try:
    # Proje ID'sini .env dosyasından alarak başlat
    ee.Initialize(project=os.getenv("PRO_ID"))
except Exception as e:
    print(f"❌ GEE Başlatılamadı: {e}")

def get_temporal_chunks(lat, lng):
    """
    Belirlenen koordinat için 3 farklı zaman diliminden (1975, 2000, 2024) 
    en temiz uydu görüntülerini çeker.
    
    Retry (Yeniden Deneme) mantığı: Google sunucularından yanıt gelmezse 3 kez dener.
    """
    point = ee.Geometry.Point([lng, lat])
    
    years = [
        {"label": "1975", "start": "1975-01-01", "end": "1975-12-31", "satellite": "LANDSAT/LM02/C02/T2"},
        {"label": "2000", "start": "2000-01-01", "end": "2000-12-31", "satellite": "LANDSAT/LE07/C02/T1_L2"},
        {"label": "2024", "start": "2024-01-01", "end": "2024-12-31", "satellite": "LANDSAT/LC08/C02/T1_L2"},
    ]
    
    results = []
    
    for year in years:
        # --- 🔁 RETRY MEKANİZMASI ---
        max_retries = 3
        success = False
        
        for attempt in range(max_retries):
            try:
                # GEE ImageCollection sorgusu
                collection = (
                    ee.ImageCollection(year["satellite"])
                    .filterBounds(point)
                    .filterDate(year["start"], year["end"])
                    .sort("CLOUD_COVER")
                    .first()
                )
                
                # getInfo() komutu internet üzerinden veri çektiği için hata riski yüksektir
                info = collection.getInfo()
                
                results.append({
                    "year": year["label"],
                    "image_id": info['id'] if info else "Görüntü bulunamadı",
                    "image": collection,
                    "satellite": year["satellite"]
                })
                success = True
                break  # Başarılı olursa deneme döngüsünden çık
                
            except Exception as e:
                print(f"⚠️ Hata: {year['label']} yılı için deneme {attempt + 1}/{max_retries} başarısız: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Tekrar denemeden önce 2 saniye bekle
                else:
                    # 3 deneme de başarısız olursa boş sonuç dön
                    results.append({
                        "year": year["label"],
                        "image_id": "Bağlantı Hatası (Sunucu yanıt vermedi)",
                        "image": None,
                        "satellite": year["satellite"]
                    })
        
    return results


def get_thumbnail_url(image, lat, lng, satellite):
    """
    GEE Image objesini görselleştirip bir PNG URL'sine dönüştürür.
    Retry Mekanizması: URL oluşturma başarısız olursa 3 kez dener.
    """
    if not image:
        return None
        
    point = ee.Geometry.Point([lng, lat])
    region = point.buffer(10000).bounds()
    
    # --- UYDU TİPİNE GÖRE GÖRSELLEŞTİRME AYARLARI ---
    if "LM02" in satellite:  # 1975 Landsat 2 (MSS)
        # MSS'de mavi bandı yoktur. Bitkileri kırmızı gösteren "False Color" kullanılır.
        bands = ['B6', 'B5', 'B4']
        min_val, max_val = 0, 100
    
    elif "LE07" in satellite:  # 2000 Landsat 7 (ETM+)
        # Landsat 7 Gerçek Renk: B3(R), B2(G), B1(B)
        bands = ['SR_B3', 'SR_B2', 'SR_B1']
        min_val, max_val = 7000, 15000 
        
    else:  # 2024 Landsat 8 (OLI)
        # Landsat 8 Gerçek Renk: B4(R), B3(G), B2(B)
        bands = ['SR_B4', 'SR_B3', 'SR_B2']
        min_val, max_val = 7000, 15000

    # --- 🔁 URL OLUŞTURMA RETRY MEKANİZMASI ---
    max_retries = 3
    for attempt in range(max_retries):
        try:
            url = image.getThumbURL({
                'min': min_val,
                'max': max_val,
                'bands': bands,
                'region': region,
                'dimensions': 512,
                'format': 'png'
            })
            return url
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"🔄 Thumbnail oluşturma denemesi {attempt + 1} başarısız, tekrar deneniyor...")
                time.sleep(2)
            else:
                print(f"❌ Thumbnail hatası: {e}")
                return None


if __name__ == "__main__":
    # Test Koordinatları: Edremit/Balıkesir civarı
    print("🛰️ Google Earth Engine bağlantısı test ediliyor...")
    chunks = get_temporal_chunks(39.6992, 26.8735)
    for chunk in chunks:
        print(f"📅 Yıl: {chunk['year']} | 🆔 ID: {chunk['image_id']}")