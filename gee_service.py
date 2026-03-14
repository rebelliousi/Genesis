import ee
import os
from dotenv import load_dotenv

load_dotenv()

ee.Initialize(project=os.getenv("PRO_ID"))

def get_temporal_chunks(lat, lng):
    # Alex Xu Ch.15: Temporal Chunking
    point = ee.Geometry.Point([lng, lat])
    
    years = [
        {"label": "1975", "start": "1975-01-01", "end": "1975-12-31", "satellite": "LANDSAT/LM02/C02/T2"},
        {"label": "2000", "start": "2000-01-01", "end": "2000-12-31", "satellite": "LANDSAT/LE07/C02/T1_L2"},
        {"label": "2024", "start": "2024-01-01", "end": "2024-12-31", "satellite": "LANDSAT/LC08/C02/T1_L2"},
    ]
    
    results = []
    
    for year in years:
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
            "image": collection
        })
    
    return results


def get_thumbnail_url(image, lat, lng, satellite):
    point = ee.Geometry.Point([lng, lat])
    region = point.buffer(10000).bounds()
    
    if "LM02" in satellite:  # 1975 Landsat 2 (MSS)
        # MSS'de mavi bandı yoktur. 
        # Standart yaklaşım: R=B6 (NIR), G=B5 (Red), B=B4 (Green) -> Klasik Yanlış Renk
        # Veya "Doğal görünüme en yakın" için: B5, B4, B4 (biraz grileşir)
        bands = ['B6', 'B5', 'B4'] # Bu bildiğimiz 'Kırmızı Bitki' görüntüsünü verir
        min_val, max_val = 0, 100
    
    elif "LE07" in satellite:  # 2000 Landsat 7 (ETM+)
        # Landsat 7'de Gerçek Renk: B3(R), B2(G), B1(B)
        bands = ['SR_B3', 'SR_B2', 'SR_B1']
        min_val, max_val = 7000, 15000 # SR verileri için bu aralık daha iyidir
        
    else:  # 2024 Landsat 8 (OLI)
        # Landsat 8'de Gerçek Renk: B4(R), B3(G), B2(B)
        bands = ['SR_B4', 'SR_B3', 'SR_B2']
        min_val, max_val = 7000, 15000

    url = image.getThumbURL({
        'min': min_val,
        'max': max_val,
        'bands': bands,
        'region': region,
        'dimensions': 512,
        'format': 'png'
    })
    return url


if __name__ == "__main__":
    chunks = get_temporal_chunks(39.6992, 26.8735)
    for chunk in chunks:
        print(f"Yıl: {chunk['year']} | Görüntü: {chunk['image_id']}")