import re
import requests

# --- KONFİGÜRASYON ---
SERPAPI_KEY = "7f6be9e1007fd0591fbc030fc268b800a5fbf9d5d307b8fd9d6ea2468d709adb"
TELEGRAM_BOT_TOKEN = "8713325438:AAECuPaL28575K314wdQC5dTKxn_TLrPo9M"
TELEGRAM_CHAT_ID = "1619221044"

# Yeni Bütçe Sınırları (TL)
MIN_BUDGET = 2500  # En az 2.500 TL (Kordon/aksesuar ve kalitesiz saatleri eler)
MAX_BUDGET = 4000  # En fazla 4.000 TL

# Minimum Değerlendirme Puanı
MIN_RATING = 3.8

# Aratılacak Hedef Aramalar (Sadece Yuvarlak Akıllı Saat Odaklı)
SEARCH_QUERIES = [
    "yuvarlak akıllı saat",
    "yuvarlak kasa akıllı saat",
    "fiyat performans yuvarlak akıllı saat",
    "2 li akıllı saat yuvarlak",
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
    "HK8",
    "HK9",
    "DT NO.1",
    "Zeblaze",
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


def is_actual_smartwatch(title_lower, price_num):
  """İlanın aksesuar değil GERÇEK BİR AKILLI SAAT olup olmadığını doğrular."""
  # 1. Bütçe Aralığı Kontrolü (2.500 TL - 4.000 TL)
  if price_num < MIN_BUDGET or price_num > MAX_BUDGET:
    return False

  # 2. Aksesuar Belirteçleri: İçinde 'kordon' veya diğer aksesuar geçen her şeyi ELE
  accessory_indicators = [
      "kordon",
      "kayış",
      "kılıf",
      "koruyucu",
      "ekran camı",
      "şarj",
      "stand",
      "aparat",
      "uyumlu",
      " için",
      "yedek",
      "bileklik",
  ]
  for term in accessory_indicators:
    if term in title_lower:
      return False

  # 3. İlan başlığında gerçek akıllı saat ibaresi kontrolü
  if not any(
      w in title_lower for w in ["akıllı saat", "smart watch", "smartwatch"]
  ):
    return False

  return True


def check_multi_buy_deal(item):
  """İkili alım veya kampanya kontrolü yapar."""
  title = item.get("title", "").lower()
  extensions = [ext.lower() for ext in item.get("extensions", [])]

  for kw in MULTI_BUY_KEYWORDS:
    if kw in title:
      return f"🔥 **İKİLİ ALIM / SET FIRSATI** ({kw.upper()})"

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
        "sort": "p",
        "api_key": SERPAPI_KEY,
    }

    try:
      response = requests.get(url, params=params)
      data = response.json()
      results = data.get("shopping_results", [])

      for item in results:
        title = item.get("title", "")
        title_lower = title.lower()
        price_str = item.get("price", "")
        price_num = clean_price(price_str)

        # --- GERÇEK SAAT FİLTRESİ ---
        if not is_actual_smartwatch(title_lower, price_num):
          continue

        # --- KARE / DİKDÖRTGEN SAAT FİLTRESİ ---
        if any(
            skip in title_lower
            for skip in ["kare", "square", "apple watch", "band"]
        ):
          continue

        # --- KULLANICI PUANI FİLTRESİ ---
        rating = item.get("rating")
        reviews = item.get("reviews", 0)
        if rating is not None and float(rating) < MIN_RATING:
          continue

        if title not in seen_titles:
          seen_titles.add(title)
          link = item.get("link", item.get("product_link", ""))
          source = item.get("source", "Satıcı")
          multi_deal_info = check_multi_buy_deal(item)

          detected_brand = "F/P Model"
          for brand in FP_BRANDS:
            if brand.lower() in title_lower:
              detected_brand = brand
              break

          rating_str = (
              f"⭐ {rating}/5 ({reviews} Yorum)"
              if rating
              else "⭐ Yüksek Memnuniyet"
          )

          all_items.append({
              "title": title,
              "brand": detected_brand,
              "price_num": price_num,
              "price_str": price_str,
              "source": source,
              "link": link,
              "multi_deal": multi_deal_info,
              "rating_num": float(rating) if rating else 0,
              "rating_str": rating_str,
          })
    except Exception as e:
      print(f"Arama hatası ({query}): {e}")

  # Sıralama: Önce İkili/Set Kampanyaları, Sonra Yüksek Puan, Sonra Uygun Fiyat
  all_items.sort(
      key=lambda x: (0 if x["multi_deal"] else 1, -x["rating_num"], x["price_num"])
  )
  return all_items[:6]


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
  print("⌚ Yuvarlak Akıllı Saat Taraması Başlatılıyor...\n")
  watches = search_smartwatches()

  if not watches:
    send_telegram_alert(
        f"❌ **Saat Botu:** {MIN_BUDGET:,} TL - {MAX_BUDGET:,} TL arasında"
        " kriterlere uygun kaliteli akıllı saat bulunamadı.".replace(",", ".")
    )
    return

  msg = "⌚ **GÜNLÜK AKILLI SAAT RAPORU**\n"
  msg += (
      f"🎯 *Kriterler: Gerçek Akıllı Saat, Yuvarlak Kasa | Bütçe: {MIN_BUDGET:,}"
      f" TL - {MAX_BUDGET:,} TL*\n\n".replace(",", ".")
  )

  for idx, watch in enumerate(watches, 1):
    deal_tag = f"\n   {watch['multi_deal']}" if watch["multi_deal"] else ""
    msg += (
        f"{idx}. 🏷️ **{watch['brand']}** - {watch['title']}{deal_tag}\n"
        f"   💰 **Fiyat:** {watch['price_str']}\n"
        f"   📊 **Puan:** {watch['rating_str']}\n"
        f"   🏪 **Satıcı:** {watch['source']}\n"
        f"   🔗 [Modeli İncele]({watch['link']})\n"
        f"-----------------------------------\n"
    )

  send_telegram_alert(msg)
  print("✅ Akıllı saat raporu Telegram'a gönderildi.")


if __name__ == "__main__":
  run_watch_tracker()
