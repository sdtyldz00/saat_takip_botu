import re
import requests

# --- KONFİGÜRASYON ---
SERPAPI_KEY = "7f6be9e1007fd0591fbc030fc268b800a5fbf9d5d307b8fd9d6ea2468d709adb"
TELEGRAM_BOT_TOKEN = "8713325438:AAECuPaL28575K314wdQC5dTKxn_TLrPo9M"
TELEGRAM_CHAT_ID = "1619221044"

# Maksimum Bütçe Sınırı (TL)
MAX_BUDGET = 4000

# Aratılacak Hedef Aramalar (İkili / Set Fırsatları da Dahil Edildi)
SEARCH_QUERIES = [
    "yuvarlak çelik kordon akıllı saat",
    "hasır kordon akıllı saat milanese",
    "2 li yuvarlak akıllı saat çelik",
    "fiyat performans yuvarlak akıllı saat çelik",
]

# Öne Çıkarılan F/P Markaları
FP_BRANDS = [
    "Kieslect",
    "Haylou",
    "Xiaomi",
    "Amazfit",
    "Honor",
    "Imilab",
    "Mibro",
    "Huawei",
    "Samsung",
]

# İkili Alım ve Kampanya Kelimeleri
MULTI_BUY_KEYWORDS = [
    "2'li",
    "2li",
    "2 adet",
    "çift",
    "2.si",
    "2. ürüne",
    "ikinciye",
    "2 al",
    "set",
    "paket",
    "çift kordon",
]


def clean_price(price_str):
  """Fiyat metnini sayısal değere dönüştürür."""
  if not price_str:
    return float("inf")
  try:
    clean = (
        price_str.replace("₺", "")
        .replace("TL", "")
        .replace(" ", "")
        .strip()
    )
    if "," in clean and "." in clean:
      clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
      clean = clean.replace(",", ".")
    return float(clean)
  except Exception:
    return float("inf")


def check_multi_buy_deal(item):
  """İlan başlığında veya satıcı uzantılarında ikili alım/indirim kampanyası var mı kontrol eder."""
  title = item.get("title", "").lower()
  extensions = [ext.lower() for ext in item.get("extensions", [])]

  # 1. Başlıkta ikili alım kontrolü
  for kw in MULTI_BUY_KEYWORDS:
    if kw in title:
      return f"🔥 **İKİLİ ALIM / SET FIRSATI** ({kw.upper()})"

  # 2. Satıcı indirim etiketlerinde (extensions) ikili kampanya kontrolü
  for ext in extensions:
    for kw in MULTI_BUY_KEYWORDS:
      if kw in ext:
        return f"🎁 **KAMPANYA:** {ext.title()}"

  return None


def search_smartwatches():
  url = "https://serpapi.com/search"
  all_items = []
  seen_titles = set()

  for query in SEARCH_QUERIES:
    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": "tr",
        "hl": "tr",
        "location": "Turkey",
        "sort": "p",  # Fiyata göre artan sırala
        "api_key": SERPAPI_KEY,
    }

    try:
      response = requests.get(url, params=params)
      data = response.json()
      results = data.get("shopping_results", [])

      for item in results:
        title = item.get("title", "")
        title_lower = title.lower()

        # Kare/dikdörtgen ve bileklik tarzı modelleri filtrele
        if any(
            skip in title_lower
            for skip in ["kare", "square", "apple watch", "band"]
        ):
          continue

        # Çelik/hasır/sırma kordon kontrolü
        if not any(
            k in title_lower
            for k in [
                "çelik",
                "hasır",
                "milanese",
                "sırma",
                "metal",
                "titanium",
            ]
        ):
          continue

        price_str = item.get("price", "")
        price_num = clean_price(price_str)

        # 4.000 TL Üstünü Filtrele
        if price_num > MAX_BUDGET:
          continue

        if title not in seen_titles:
          seen_titles.add(title)
          link = item.get("link", item.get("product_link", ""))
          source = item.get("source", "Satıcı")
          multi_deal_info = check_multi_buy_deal(item)

          # Marka tespiti
          detected_brand = "F/P Model"
          for brand in FP_BRANDS:
            if brand.lower() in title_lower:
              detected_brand = brand
              break

          all_items.append({
              "title": title,
              "brand": detected_brand,
              "price_num": price_num,
              "price_str": price_str,
              "source": source,
              "link": link,
              "multi_deal": multi_deal_info,
          })
    except Exception as e:
      print(f"Arama hatası ({query}): {e}")

  # İkili alım/kampanya olanları üste al, sonra fiyata göre sırala
  all_items.sort(
      key=lambda x: (0 if x["multi_deal"] else 1, x["price_num"])
  )
  return all_items[:6]  # En uygun ve avantajlı ilk 6 seçeneği al


def send_telegram_alert(message):
  """Telegram'a bildirim gönderir."""
  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
  payload = {
      "chat_id": TELEGRAM_CHAT_ID,
      "text": message,
      "parse_mode": "Markdown",
      "disable_web_page_preview": True,
  }
  try:
    requests.post(url, json=payload)
  except Exception as e:
    print(f"Telegram hatası: {e}")


def run_watch_tracker():
  print("⌚ Yuvarlak & Çelik Sırmalı Akıllı Saat Taraması Başlatılıyor...\n")
  watches = search_smartwatches()

  if not watches:
    send_telegram_alert(
        f"❌ **Saat Botu:** {MAX_BUDGET:,} TL altında kriterlere uygun model"
        " bulunamadı.".replace(",", ".")
    )
    return

  msg = "⌚ **GÜNLÜK FİYAT-PERFORMANS & İKİLİ ALIM SAAT RAPORU**\n"
  msg += (
      f"🎯 *Kriterler: Yuvarlak Kasalı, Çelik/Hasır Sırma Kordon | Maks. Bütçe:"
      f" {MAX_BUDGET:,} TL*\n\n".replace(",", ".")
  )

  for idx, watch in enumerate(watches, 1):
    deal_tag = f"\n   {watch['multi_deal']}" if watch["multi_deal"] else ""
    msg += (
        f"{idx}. 🏷️ **{watch['brand']}** - {watch['title']}{deal_tag}\n"
        f"   💰 **Fiyat:** {watch['price_str']}\n"
        f"   🏪 **Satıcı:** {watch['source']}\n"
        f"   🔗 [Modeli İncele]({watch['link']})\n"
        f"-----------------------------------\n"
    )

  send_telegram_alert(msg)
  print("✅ İkili alım odaklı akıllı saat raporu Telegram'a gönderildi.")


if __name__ == "__main__":
  run_watch_tracker()
