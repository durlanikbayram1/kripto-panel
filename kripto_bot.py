# -*- coding: utf-8 -*-
"""
Kripto Momentum Botu — DEMO (gerçek para yok) — SUNUCU SÜRÜMÜ
Telefon kapalıyken de 7/24 çalışır. Telegram'dan @Kripto_Momentum_2026_bot ile yönetilir.
Yeniden başlarsa kaldığı yerden devam eder (durum kripto_durum.json dosyasında saklanır).
"""
import os, sys, csv, json, time, base64, datetime as dt
import requests
import hashlib, builtins, collections, traceback, subprocess, shutil

# --- Kayıt defteri: ekrana yazılan her satır son 500 satırlık hafızada da tutulur (uzaktan takip raporu için) ---
GUNLUK = collections.deque(maxlen=500)
_asil_print = builtins.print
def print(*args, **kw):
    try:
        GUNLUK.append(time.strftime("%m-%d %H:%M:%S ") + " ".join(str(a) for a in args))
    except Exception:
        pass
    kw.setdefault("flush", True)
    _asil_print(*args, **kw)
KURU_TEST = os.environ.get("KRIPTO_KURU_TEST") == "1"   # güncelleme öncesi deneme çalıştırması

# ======================= AYARLAR =======================
# >>> SADECE TOKEN SATIRINI DOLDUR <<<  (bu dosyayı kimseyle paylaşma)
KRIPTO_BOT_TOKEN_ELLE = ""          # BotFather'ın verdiği token, tırnakların arasına
KRIPTO_CHAT_ID_ELLE = ""            # sunucuda KRIPTO_CHAT_ID ortam değişkeninden gelir (dosya GitHub’da açık)

PANEL_URL = os.environ.get("KRIPTO_PANEL_URL", "")   # mini uygulama adresi (kurulum betiğinden gelir)
if "KULLANICIADI" in PANEL_URL:      # adres düzenlenmemişse uygulama düğmesi gösterilmez
    PANEL_URL = ""

BASLANGIC_USD = 100
CALISMA_SAATI = float(os.environ.get("KRIPTO_SURE_SAAT", "0"))   # 0 = durmadan çalış
KONTROL_ARALIGI_SN = 60
OZET_ARALIGI_SAAT = 4               # Telegram'a kaç saatte bir otomatik özet gelsin

MAKER_KOMISYON_YUZDE = 0.10
TAKER_KOMISYON_YUZDE = 0.15
KAYMA_YUZDE = 0.05

SICRAMA_PENCERE_DK = 5
SICRAMA_ESIGI_YUZDE = 0.8
HACIM_KATSAYISI = 3.0
MAKS_BEKLEME_DK = 0           # 0 = süre sınırı yok: pozisyon sadece stop / hedef / iz stop ile kapanır
TEKRAR_GIRIS_BEKLEME_DK = 15
KUR_YEDEK = 0

# Coin listesi: tüm TL çiftleri taranır (stabil coinler hariç)
MIN_FIYAT_TL = 0
MIN_HACIM_TL_24S = 0            # 0 = tüm TL çiftleri taranır (alımda likidite filtresi ayrıca var)
# Alım filtreleri ve başabaş stop (uygulamadaki Ayarlar'dan açılıp kapatılabilir)
BASABAS_ESIK_YUZDE = 1.0    # pozisyon bu kadar kâra geçince stop girişin üstüne çekilir
BASABAS_PAY_YUZDE = 0.4     # stop = giriş + %0,4 (alış/satış komisyonu ve kaymayı karşılar)
UST_FITIL_MAX = 30          # giriş mumunun üst fitili bu %'den uzunsa alınmaz (satış baskısı)
SICRAMA_MAX_YUZDE = 2.0     # 5 dk'da bundan fazla yükselmişse alınmaz (geç giriş)
MIN_DK_HACIM_TL = 20000     # dakikalık ortalama hacmi bunun altındaysa alınmaz (düşük likidite)

LISTE_YENILEME_DK = 30          # liste kaç dakikada bir yenilensin
COINLER_SABIT = []              # doluysa sadece bunlar taranır, ör. ["BTC", "ETH"]

# Uygulamadaki Ayarlar panelinden değiştirilebilen ayarlar
HASSASIYETLER = {"temkinli": (1.0, 4.0), "dengeli": (0.8, 3.0), "atak": (0.5, 2.0)}   # (5 dk %, hacim katı)
GUNLUK_ZARAR_LIMITI = 0         # %; 0 = kapalı. Gün içinde bu kadar kayıpta otomatik alım durur
ISLEM_BILDIRIMI = True          # her alım/satımda Telegram mesajı

# Tek strateji, sanal 100 $. Kâr/zarar ve pozisyon sayısı uygulamadaki Ayarlar'dan değiştirilebilir
KAR_AL_YUZDE = 2.0          # kâr al (en fazla %10)
ZARAR_DURDUR_YUZDE = 1.0    # zarar durdur (en fazla %5)
MAKS_POZISYON = 2           # aynı anda en fazla açık pozisyon; para eşit bölünür

# Çıkış modu:
#   "takip" = takip eden stop (önerilen): stop hep görülen en yüksek fiyatın MESAFE kadar altında durur,
#             sadece yukarı çıkar, sabit hedef yoktur (kazanan işlem stop'a çarpınca kapanır).
#             Başlangıç stopu da aynı mesafededir. Mesafe 0 = coinin oynaklığına göre otomatik.
#   "oto" = kârın %50–90'ını kilitleyen eski oto iz, "iz" = sabit mesafeli iz, "sabit" = hedefte sat
CIKIS_MODU = "takip"
TAKIP_ATR_KAT = 3.0         # oto mesafe = son 14 dakikanın ortalama mum boyu × 3
TAKIP_MIN_YUZDE = 0.7       # oto mesafe en az %0,7 (sakin coinler, BTC gibi)
TAKIP_MAX_YUZDE = 2.0       # oto mesafe en fazla %2 (oynak küçük coinler)
OTO_BASLAT_YUZDE = 1.0      # oto iz bu kâra ulaşınca başlar (ör. +%1 → stop +%0,5)
TEYIT_BEKLEME_SN = 200      # sinyalden sonra teyit için en fazla bekleme
MIN_POTANSIYEL_YUZDE = 1.0  # tahmini hareket bundan küçükse alınmaz (komisyonu karşılamaz)
IZ_BASLAT_YUZDE = 1.5       # pozisyon bu kadar kâra geçince iz süren stop devreye girer
IZ_MESAFE_YUZDE = 0.75      # stop, görülen en yüksek fiyatın bu kadar altında takip eder
# =======================================================

# ======================= VERİ VE TELEGRAM =======================

OTURUM = requests.Session()
OTURUM.headers["User-Agent"] = "Mozilla/5.0 (kripto-demo-bot)"

def _binance_bicim(veri):
    if isinstance(veri, dict):                       # bazı uçlar veriyi sarmalayabilir
        veri = veri.get("data") or veri.get("list") or []
    mumlar = []
    for r in veri:
        mumlar.append({"t": int(r[0]), "o": float(r[1]), "h": float(r[2]),
                       "l": float(r[3]), "c": float(r[4]), "v": float(r[5])})
    return mumlar

def mum_binance_tr(sembol, adet):
    r = OTURUM.get("https://api.binance.me/api/v1/klines",
                   params={"symbol": sembol, "interval": "1m", "limit": adet}, timeout=10)
    r.raise_for_status()
    return _binance_bicim(r.json())

def mum_binance_global(sembol, adet):
    r = OTURUM.get("https://data-api.binance.vision/api/v3/klines",
                   params={"symbol": sembol, "interval": "1m", "limit": adet}, timeout=10)
    r.raise_for_status()
    return _binance_bicim(r.json())

def mum_btcturk(sembol, adet):
    bitis = int(time.time())
    baslangic = bitis - (adet + 2) * 60
    r = OTURUM.get("https://graph-api.btcturk.com/v1/klines/history",
                   params={"symbol": sembol, "resolution": 1, "from": baslangic, "to": bitis}, timeout=10)
    r.raise_for_status()
    d = r.json()
    mumlar = []
    for i in range(len(d.get("t", []))):
        mumlar.append({"t": int(d["t"][i]) * 1000, "o": float(d["o"][i]), "h": float(d["h"][i]),
                       "l": float(d["l"][i]), "c": float(d["c"][i]), "v": float(d["v"][i])})
    return mumlar[-adet:]

KAYNAKLAR = [("Binance TR", mum_binance_tr), ("Binance (global veri)", mum_binance_global), ("BtcTurk", mum_btcturk)]
aktif_kaynak = None

def mumlari_al(sembol, adet=40):
    """Önce çalışan kaynağı dener, olmazsa sıradakine geçer."""
    global aktif_kaynak
    sira = sorted(KAYNAKLAR, key=lambda k: k[0] != aktif_kaynak)
    son_hata = None
    for ad, fonk in sira:
        try:
            mumlar = fonk(sembol, adet)
            if len(mumlar) >= 10 and mumlar[-1]["c"] > 0:
                if aktif_kaynak != ad:
                    print(f"ℹ️ Fiyat kaynağı: {ad}")
                aktif_kaynak = ad
                return mumlar
        except Exception as e:
            son_hata = f"{ad}: {type(e).__name__}"
    raise RuntimeError(f"{sembol} için veri alınamadı ({son_hata})")

# --- Bağlantı testi ---
print("🔌 Fiyat kaynakları test ediliyor (BTCTRY)...")
for ad, fonk in KAYNAKLAR:
    try:
        m = fonk("BTCTRY", 30)
        print(f"  ✅ {ad}: çalışıyor, BTC = {m[-1]['c']:,.0f} TL")
        if aktif_kaynak is None:
            aktif_kaynak = ad
    except Exception as e:
        print(f"  ❌ {ad}: çalışmıyor ({type(e).__name__})")
if aktif_kaynak is None:
    print("⚠️ Hiçbir fiyat kaynağına ulaşılamadı. Bu çıktıyı bana gönder.")
else:
    print(f"➡️ Kullanılacak kaynak: {aktif_kaynak}")

# --- Dolar kuru (USDT/TRY) ---
KUR = KUR_YEDEK
try:
    KUR = mumlari_al("USDTTRY", 15)[-1]["c"]
    print(f"💵 1 $ ≈ {KUR:.2f} TL (USDT/TRY)")
except Exception:
    print(f"⚠️ Kur alınamadı, yedek kur kullanılıyor: {KUR_YEDEK}")

# --- Telegram ---
def _gizli(ad):
    return os.environ.get(ad, "")

TG_TOKEN = (KRIPTO_BOT_TOKEN_ELLE.strip() or _gizli("KRIPTO_BOT_TOKEN")).strip().replace(" ", "")
TG_CHAT = KRIPTO_CHAT_ID_ELLE.strip() or _gizli("KRIPTO_CHAT_ID").strip()
TG_BOT_ADI = ""

if TG_TOKEN:
    try:
        TG_BOT_ADI = OTURUM.get(f"https://api.telegram.org/bot{TG_TOKEN}/getMe", timeout=10).json()["result"]["username"]
    except Exception:
        print("⚠️ KRIPTO_BOT_TOKEN geçersiz görünüyor. Token'ı BotFather'dan tekrar kontrol et.")
        TG_TOKEN = ""

if TG_TOKEN and not TG_CHAT:
    try:
        g = OTURUM.get(f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates", timeout=10).json()
        for u in reversed(g.get("result", [])):
            msg = u.get("message") or {}
            if msg.get("chat", {}).get("id"):
                TG_CHAT = str(msg["chat"]["id"])
                break
    except Exception:
        pass
    if TG_CHAT:
        print(f"💡 Sohbet numaran bulundu: {TG_CHAT}")
        print("   Kalıcı olsun diye bu numarayı dosyanın başındaki KRIPTO_CHAT_ID_ELLE satırına yaz.")

def telegram(metin, panel=None):
    print(metin)
    if not (TG_TOKEN and TG_CHAT):
        return
    veri = {"chat_id": TG_CHAT, "text": metin}
    if panel and PANEL_URL:
        veri["reply_markup"] = json.dumps({"inline_keyboard": [[
            {"text": "📊 Paneli aç", "web_app": {"url": PANEL_URL.rstrip("#") + "#d=" + panel}}]]})
    try:
        r = OTURUM.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=veri, timeout=10)
        if not r.ok and "reply_markup" in veri:          # düğme sorun çıkarırsa düğmesiz gönder
            veri.pop("reply_markup")
            OTURUM.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=veri, timeout=10)
    except Exception as e:
        print(f"(Telegram gönderilemedi: {type(e).__name__})")

if TG_TOKEN and TG_CHAT:
    print(f"✅ Telegram bağlı: @{TG_BOT_ADI}")
elif TG_TOKEN:
    print(f"⚠️ Bot bulundu (@{TG_BOT_ADI}) ama sohbet yok. Telegram'da @{TG_BOT_ADI} botuna /start yaz, sonra botu yeniden başlat.")
else:
    print("ℹ️ KRIPTO_BOT_TOKEN bulunamadı; mesajlar sadece burada görünecek.")
    print("   Dosyanın başındaki KRIPTO_BOT_TOKEN_ELLE satırına token'ı yaz.")

# --- Coin evreni: fiyatı MIN_FIYAT_TL ve üzeri olan tüm TL çiftleri ---
STABIL = {"USDT", "USDC", "FDUSD", "BUSD", "TUSD", "DAI", "USDP", "USDS", "USDE", "EUR", "EURI", "AEUR", "GBP"}
BINANCE_HOSTLAR = ["https://api.binance.me", "https://data-api.binance.vision"]
liste_kaynagi = None
_son_liste = 0

def tum_tl_ciftleri():
    """Tüm TL çiftlerinin son fiyatı ve 24 saatlik TL hacmi: {coin: (fiyat, hacim_tl)}"""
    for host in BINANCE_HOSTLAR:
        try:
            r = OTURUM.get(host + "/api/v3/ticker/24hr", timeout=20)
            r.raise_for_status()
            veri = r.json()
            sonuc = {}
            for t in veri:
                s = t.get("symbol", "")
                if s.endswith("TRY") and len(s) > 3:
                    sonuc[s[:-3]] = (float(t["lastPrice"]), float(t["quoteVolume"]))
            if len(sonuc) > 5:
                return ("Binance TR" if "binance.me" in host else "Binance (global veri)"), sonuc
        except Exception:
            continue
    try:
        r = OTURUM.get("https://api.btcturk.com/api/v2/ticker", timeout=20)
        r.raise_for_status()
        sonuc = {}
        for t in r.json().get("data", []):
            if t.get("denominatorSymbol") == "TRY":
                f = float(t["last"])
                sonuc[t["numeratorSymbol"]] = (f, f * float(t["volume"]))
        if sonuc:
            return "BtcTurk", sonuc
    except Exception:
        pass
    return None, {}

HACIM24 = {}      # coin -> 24 saatlik TL hacmi (kayıtlarda likidite bilgisi için)

def coin_listesi_guncelle(zorla=False):
    """COINLER listesini yeniler: fiyat >= MIN_FIYAT_TL ve 24s hacim >= MIN_HACIM_TL_24S (hacme göre sıralı)."""
    global COINLER, liste_kaynagi, _son_liste
    if COINLER_SABIT:
        COINLER = list(COINLER_SABIT)
        return
    if not zorla and COINLER and time.time() - _son_liste < LISTE_YENILEME_DK * 60:
        return
    kaynak, ciftler = tum_tl_ciftleri()
    if not ciftler:
        print("⚠️ Coin listesi alınamadı; eski liste kullanılıyor.")
        return
    secilen = [(c, f, h) for c, (f, h) in ciftler.items()
               if c not in STABIL and f >= MIN_FIYAT_TL and h >= MIN_HACIM_TL_24S]
    secilen.sort(key=lambda x: -x[2])
    COINLER = [c for c, _, _ in secilen]
    HACIM24.update({c: h for c, (f, h) in ciftler.items()})
    liste_kaynagi = kaynak
    _son_liste = time.time()

GECERSIZ = {}     # host -> bu kaynakta olmayan coinler (bir kez öğrenilir, sonra sorulmaz)

def _paket_getir(host, paket, sonuc, derinlik=0):
    """Bir paketi çeker; kaynakta olmayan bir sembol yüzünden hata dönerse paketi ikiye bölüp tekrar dener."""
    if not paket:
        return
    semboller = json.dumps([c + "TRY" for c in paket], separators=(",", ":"))
    r = OTURUM.get(host + "/api/v3/ticker", params={"symbols": semboller, "windowSize": "5m", "type": "MINI"}, timeout=20)
    if r.status_code == 400 and derinlik < 10:
        if len(paket) == 1:
            GECERSIZ.setdefault(host, set()).add(paket[0])
            return
        yarim = len(paket) // 2
        _paket_getir(host, paket[:yarim], sonuc, derinlik + 1)
        _paket_getir(host, paket[yarim:], sonuc, derinlik + 1)
        return
    r.raise_for_status()
    for t in r.json():
        acilis, son = float(t["openPrice"]), float(t["lastPrice"])
        if acilis > 0:
            sonuc[t["symbol"][:-3]] = ((son / acilis - 1) * 100, son)

def toplu_5dk_degisim(coinler):
    """Tek seferde (100'lük paketler) tüm coinlerin son 5 dakikalık değişimi: {coin: (yuzde, son_fiyat)}"""
    if not coinler:
        return {}
    for host in BINANCE_HOSTLAR:
        try:
            sonuc = {}
            liste = [c for c in coinler if c not in GECERSIZ.get(host, set())]
            for i in range(0, len(liste), 100):
                _paket_getir(host, liste[i:i + 100], sonuc)
            if len(sonuc) >= len(coinler) * 0.5:      # en az yarısı geldiyse bu kaynak yeterli
                return sonuc
        except Exception:
            continue
    return None      # toplu veri yoksa tarama tek tek yapılır

COINLER = []
coin_listesi_guncelle(zorla=True)
if COINLER:
    print(f"🪙 Taranacak coin: {len(COINLER)} (tüm TL çiftleri, stabil coinler hariç) · kaynak: {liste_kaynagi}")
    print("   " + ", ".join(COINLER[:30]) + (" ..." if len(COINLER) > 30 else ""))
else:
    COINLER = ["BTC", "ETH", "BNB", "SOL", "XRP", "AVAX", "DOGE", "ADA"]
    print("⚠️ Coin listesi alınamadı, varsayılan 8 coin kullanılacak.")

# ======================= BOT MOTORU =======================

KLASOR = os.path.dirname(os.path.abspath(__file__))
ISLEM_DOSYASI = os.path.join(KLASOR, "kripto_demo_islemler.csv")
DURUM_DOSYASI = os.path.join(KLASOR, "kripto_durum.json")

def simdi():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=3)))  # Türkiye saati

def tl(x):
    return f"{x:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")

def fiyat(x):
    """Türkçe fiyat biçimi: 3.062.454 / 333,80 / 2,8580"""
    d = 0 if x >= 10000 else (2 if x >= 10 else (4 if x >= 0.01 else 8))
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def usd(x_tl):
    if not KUR:
        return "-"
    return f"{x_tl / KUR:,.2f} $".replace(",", "X").replace(".", ",").replace("X", ".")

def sinyal_hesapla(mumlar):
    """Son mumlara bakıp ani sıçrama var mı karar verir.
    Son mum henüz kapanmamış olabilir; hacim için kapanmış mumları kullanırız."""
    gerekli = SICRAMA_PENCERE_DK + 22
    if not mumlar or len(mumlar) < gerekli:
        return None
    anlik = mumlar[-1]["c"]
    kapali = mumlar[:-1]                      # kapanmış mumlar
    eski_fiyat = kapali[-SICRAMA_PENCERE_DK]["c"]
    degisim = (anlik / eski_fiyat - 1) * 100
    son = kapali[-1]
    onceki = kapali[-21:-1]
    ort_hacim = sum(m["v"] for m in onceki) / len(onceki)
    hacim_kat = (son["v"] / ort_hacim) if ort_hacim > 0 else 0
    yesil = son["c"] > son["o"]
    sinyal = degisim >= SICRAMA_ESIGI_YUZDE and hacim_kat >= HACIM_KATSAYISI and yesil
    aralik = son["h"] - son["l"]
    return {"fiyat": anlik, "degisim": degisim, "hacim_kat": hacim_kat, "sinyal": sinyal,
            "mum_yuzde": (son["c"] / son["o"] - 1) * 100 if son["o"] else 0,
            "ust_fitil": (son["h"] - max(son["o"], son["c"])) / aralik * 100 if aralik > 0 else 0,
            "ort_hacim_tl": ort_hacim * anlik,
            "dk1": (anlik / son["c"] - 1) * 100 if son["c"] else 0}


def hedef_tahmini(mumlar, fiyat, sicrama=0.0):
    """Beklenen yükseliş (%) tahmini. Kesin bilgi değil; işlem kayıtlarıyla doğruluğu ölçülür.
    - ATR: son 14 kapanmış 1 dk mumun ortalama aralığı (coinin normal oynaklığı)
    - Momentum: sıçramanın büyüklüğü (güçlü sıçramalar genelde bir süre devam eder)
    - Direnç: sıçramadan önceki en yüksek fiyat (fiyat oraya gelince takılabilir)"""
    kap = mumlar[:-1]
    if len(kap) < 20 or not fiyat:
        return {"tahmin": None, "atr": None, "direnc": None}
    son14 = kap[-14:]
    atr = sum(m["h"] - m["l"] for m in son14) / len(son14) / fiyat * 100
    gecmis = kap[:-6]
    direnc = max(m["h"] for m in gecmis) if gecmis else None
    dr = (direnc / fiyat - 1) * 100 if direnc and direnc > fiyat * 1.003 else None
    beklenen = max(4 * atr, 0.8 * max(sicrama, 0))
    tahmin = min(beklenen, dr) if dr is not None and dr < beklenen else beklenen * (1.2 if dr is None else 1)
    tahmin = max(0.3, min(8.0, tahmin))
    return {"tahmin": round(tahmin, 2), "atr": round(atr, 3), "direnc": None if dr is None else round(dr, 2)}

def zararsiz_fiyat(giris_fiyati, alis_kom_orani):
    """Bu fiyatın altında stop'ta satılırsa (alış + satış komisyonu + kayma sonrası) zarar edilir."""
    return giris_fiyati / ((1 - alis_kom_orani) * (1 - KAYMA_YUZDE / 100) * (1 - TAKER_KOMISYON_YUZDE / 100))

def takip_ekle(z, mesafe=None):
    """Grid / dip pozisyonuna takip eden stop ekler (hedefi korunur). Açık eski pozisyonlara da uygulanır."""
    m = mesafe or (globals().get("AYAR", {}).get("tm", 0) / 100) or 1.0
    g = z["giris_fiyati"]
    z["takip"], z["iz_mesafe"] = True, m
    z["tepe"] = max(z.get("tepe", g), g)
    z.setdefault("zararsiz", zararsiz_fiyat(g, z.get("giris_komisyon", 0) / z["tutar"] if z.get("tutar") else 0.0015))
    z["stop"] = max(takip_stop_fiyati(z["tepe"], g, z["zararsiz"], m), z["stop"])   # stop asla aşağı inmez
    if not z.get("takip_gecti"):
        z["stop0"] = z["stop"]
    z["takip_gecti"] = True
    return z

KAR_KILIT_BASLA = 1.0       # coin bu kadar yükselince kâr kilidi devreye girer
KAR_KORU_ORAN = 0.70        # kilit devredeyken net kârın en az %70'i korunur

def takip_stop_fiyati(tepe, giris, zararsiz, mesafe):
    """Takip eden stop — her şey MALİYETE göre (alış + satış komisyonu + kayma dahil):
    - Başlangıçta stop'ta satılırsa net zarar = mesafe (ör. %1).
    - Coin ne kadar yükselirse stop da o kadar yükselir: +%1 yükselişte stop tam zararsız satış seviyesinde.
    - Yükseliş %1'i geçince net kârın en az %70'i korunur (yükseliş büyüdükçe tepenin %1 gerisi daha fazla korur)."""
    yukselis = (tepe / giris - 1) * 100
    net = yukselis - mesafe                                  # stop'ta satılırsa net sonuç (%)
    if yukselis >= KAR_KILIT_BASLA - 1e-9:          # %1 dahil
        net_kar = (tepe / zararsiz - 1) * 100                # tepede satılsaydı net kâr
        net = max(net, KAR_KORU_ORAN * net_kar)
    return zararsiz * (1 + net / 100)

def takip_mesafesi(bilgi=None):
    """Takip eden stop mesafesi (%). Ayar 0 ise coinin son dakikalardaki oynaklığından (ATR) hesaplanır."""
    tm = globals().get("AYAR", {}).get("tm", 0)
    if tm:
        return tm / 100
    atr = (bilgi or {}).get("atr")
    if atr:
        return round(max(TAKIP_MIN_YUZDE, min(TAKIP_MAX_YUZDE, TAKIP_ATR_KAT * atr)), 2)
    return 1.0

def oto_kilit(kazanc, tahmin=None):
    """OTO iz: kâr büyüdükçe kilitlenen pay artar. +%1→%50, +%2→%60, +%3→%70, +%4 ve üstü→%80+.
    Tahmini hedefe ulaşınca kârın %90'ı kilitlenir (yükseliş bitmek üzere olabilir)."""
    if kazanc < OTO_BASLAT_YUZDE:
        return None
    oran = min(0.85, 0.5 + 0.1 * (kazanc - 1))
    if tahmin and kazanc >= tahmin:
        oran = max(oran, 0.9)
    return kazanc * oran

class Profil:
    """Tek strateji, birden çok pozisyon. Boştaki para açılabilecek pozisyon sayısına eşit bölünür."""
    def __init__(self, baslangic_tl, tur="momentum"):
        self.tur = tur                    # momentum / grid / dip
        self.ek = {}                      # stratejiye özel durum (grid seviyeleri, bekleyen limit emirler)
        self.maks = None                  # en fazla pozisyon (None = MAKS_POZISYON ayarı)
        self.ana_para = baslangic_tl      # bot sadece bununla işlem yapar
        self.kilitli_kar = 0.0            # "kasaya" konan kâr, bot dokunmaz
        self.baslangic = baslangic_tl
        self.pozisyonlar = []
        self.bekleme = {}                 # coin -> tekrar girilebilecek zaman
        self.islemler = []
        self.komisyon_toplam = 0.0
        self.egri = [0.0]                 # her kapanan işlemden sonraki net sonuç (kâr grafiği)

    @property
    def ad(self):
        if self.tur == "grid":
            g = globals()
            return f"Grid · {', '.join(g.get('GRID_COINLER', []))} · {g.get('GRID_SEVIYE', 0)} basamak · limit emir"
        if self.tur == "dip":
            return f"Dipten alım · büyük coinler · hedef ortalamaya dönüş · stop %{globals().get('DIP_STOP', 0):g}".replace(".", ",")
        if CIKIS_MODU == "takip":
            tm = globals().get("AYAR", {}).get("tm", 0)
            return ("Takip stop: tepenin " + (f"%{tm / 100:g}" if tm else "oynaklığa göre %0,7–2") + " altı · sabit hedef yok").replace(".", ",")
        if CIKIS_MODU == "oto":
            return f"Oto iz: +%{OTO_BASLAT_YUZDE:g}'den itibaren kârın %50–90'ı kilitlenir / stop %{ZARAR_DURDUR_YUZDE:g}".replace(".", ",")
        if CIKIS_MODU == "iz":
            return f"İz süren: +%{IZ_BASLAT_YUZDE:g} kârda başlar, %{IZ_MESAFE_YUZDE:g} geriden / stop %{ZARAR_DURDUR_YUZDE:g}".replace(".", ",")
        return f"%{KAR_AL_YUZDE:g} kâr / %{ZARAR_DURDUR_YUZDE:g} zarar".replace(".", ",")

    def acik_coinler(self):
        return [z["coin"] for z in self.pozisyonlar]

    def serbest(self):
        return len(self.pozisyonlar) < (self.maks or MAKS_POZISYON)

    def bosta_para(self):
        return self.ana_para - sum(z["tutar"] for z in self.pozisyonlar)

    def gir(self, coin, fiyat, mum_t, bilgi=None, maker=False, tutar=None):
        """maker=True: limit emir (kayma yok, maker komisyonu). tutar verilirse o kadar alınır (grid basamağı)."""
        if tutar is None:
            if not self.serbest() or coin in self.acik_coinler():
                return None
            tutar = self.bosta_para() / ((self.maks or MAKS_POZISYON) - len(self.pozisyonlar))
        tutar = min(tutar, self.bosta_para())
        if tutar < 1:
            return None
        giris_fiyati = fiyat if maker else fiyat * (1 + KAYMA_YUZDE / 100)    # piyasa emri: biraz pahalıya alırız
        komisyon = tutar * (MAKER_KOMISYON_YUZDE if maker else TAKER_KOMISYON_YUZDE) / 100
        miktar = (tutar - komisyon) / giris_fiyati
        takip = CIKIS_MODU == "takip" and self.tur == "momentum"
        mesafe = takip_mesafesi(bilgi) if takip else IZ_MESAFE_YUZDE
        stop_yuzde = mesafe if takip else ZARAR_DURDUR_YUZDE
        tahmin = (bilgi or {}).get("tahmin")
        if CIKIS_MODU in ("oto", "takip"):
            hedef_yuzde = tahmin or 2.0            # takip modunda sadece gösterim içindir, bu fiyatta satılmaz
        elif CIKIS_MODU == "iz":
            hedef_yuzde = IZ_BASLAT_YUZDE
        else:
            hedef_yuzde = KAR_AL_YUZDE
        poz = {
            "coin": coin, "miktar": miktar, "tutar": tutar, "giris_fiyati": giris_fiyati,
            "giris_komisyon": komisyon, "giris_zamani": simdi(), "giris_mum_t": mum_t,
            "hedef": giris_fiyati * (1 + hedef_yuzde / 100),
            "oto": CIKIS_MODU == "oto", "takip": takip, "tahmin": tahmin,
            "stop": giris_fiyati * (1 - stop_yuzde / 100),
            "stop0": giris_fiyati * (1 - stop_yuzde / 100),
            "iz": CIKIS_MODU in ("iz", "oto", "takip"), "iz_mesafe": mesafe, "tepe": giris_fiyati, "iz_aktif": False,
            "islenen_t": mum_t,
            "bilgi": bilgi or {}, "mfe": 0.0, "mae": 0.0, "mfe_dk": 0, "kar1": False,
            "zararsiz": zararsiz_fiyat(giris_fiyati, komisyon / tutar),
        }
        if takip:
            poz["stop"] = poz["stop0"] = takip_stop_fiyati(giris_fiyati, giris_fiyati, poz["zararsiz"], mesafe)
        self.pozisyonlar.append(poz)
        self.komisyon_toplam += komisyon
        return poz

    def cik(self, p, fiyat, sebep, maker):
        if maker:   # kâr al: limit emir, kayma yok, maker komisyonu
            cikis_fiyati = fiyat
            oran = MAKER_KOMISYON_YUZDE
        else:       # zarar durdur / süre doldu: piyasa emri, kayma + taker komisyonu
            cikis_fiyati = fiyat * (1 - KAYMA_YUZDE / 100)
            oran = TAKER_KOMISYON_YUZDE
        brut = p["miktar"] * cikis_fiyati
        komisyon = brut * oran / 100
        net = brut - komisyon
        kar = net - p["tutar"]
        self.komisyon_toplam += komisyon
        if kar >= 0:
            self.kilitli_kar += kar
        else:
            self.ana_para += kar
        kayit = {
            "profil": self.ad, "strateji": self.tur, "coin": p["coin"],
            "giris_zamani": p["giris_zamani"].strftime("%Y-%m-%d %H:%M"),
            "cikis_zamani": simdi().strftime("%Y-%m-%d %H:%M"),
            "giris_fiyati": round(p["giris_fiyati"], 6), "cikis_fiyati": round(cikis_fiyati, 6),
            "tutar_tl": round(p["tutar"], 2), "kar_tl": round(kar, 2),
            "kar_yuzde": round(kar / p["tutar"] * 100, 2),
            "komisyon_tl": round(p["giris_komisyon"] + komisyon, 2), "sebep": sebep,
        }
        kayit.update(kayit_detayi(p, sebep, kayit))
        if p in self.pozisyonlar:
            self.pozisyonlar.remove(p)
        self.islemler.append(kayit)
        self.egri = (self.egri + [round(self.ana_para + self.kilitli_kar - self.baslangic, 2)])[-30:]
        self.bekleme[p["coin"]] = time.time() + TEKRAR_GIRIS_BEKLEME_DK * 60
        islem_kaydet(kayit)
        return kayit

    def kontrol_et(self, p, mumlar):
        """Açık pozisyon için stop / hedef / iz süren stop / süre kontrolü.
        Kapanmış her mum yalnızca BİR kez işlenir; stop yükseltmeleri sadece kapanmış mumlardan yapılır
        (aynı mum içinde önce düşük mü yüksek mi geldi bilinmediği için temkinli davranılır)."""
        if not mumlar:
            return None
        def stop_sebebi():
            if p.get("iz_aktif"):
                return "IZ STOP"
            return "BASABAS" if p.get("bs") else "ZARAR DURDUR"
        son_index = len(mumlar) - 1
        for i, m in enumerate(mumlar):
            if m["t"] <= max(p["giris_mum_t"], p.get("islenen_t", 0)):
                continue
            yol_guncelle(p, m)
            # Bu mum içinde stop canlı fiyatla yükseltildiyse, mumun dibi yükseltmeden ÖNCE gelmiş olabilir:
            # o mum için mum başındaki stop esas alınır (sonraki düşüşler 5 sn'lik canlı kontrolde yakalanır).
            esik = p.get("stop_mum_bas", p["stop"]) if m["t"] == p.get("canli_t") else p["stop"]
            if m["l"] <= esik:
                return self.cik(p, esik, stop_sebebi(), maker=False)
            if not p.get("iz") and m["h"] >= p["hedef"]:
                return self.cik(p, p["hedef"], "KAR AL", maker=True)
            if i < son_index:                       # mum kapandı: stop yükseltmeleri sonraki mumlardan geçerli
                iz_guncelle(p, m)
                basabas_kontrol(p)
                p["islenen_t"] = m["t"]
        anlik = mumlar[-1]["c"]
        if anlik <= p["stop"]:
            return self.cik(p, anlik, stop_sebebi(), maker=False)
        if not p.get("iz") and anlik >= p["hedef"]:
            return self.cik(p, p["hedef"], "KAR AL", maker=True)
        # Canlı stop: fiyat yeni tepe yaptıysa stop mumun kapanmasını beklemeden hemen yükselir
        if p.get("iz") or p.get("takip"):
            once = p["stop"]
            iz_guncelle(p, {"h": anlik})
            if p["stop"] > once and p.get("canli_t") != mumlar[-1]["t"]:
                p["canli_t"], p["stop_mum_bas"] = mumlar[-1]["t"], once
        # süre sınırı (0 = yok); iz süren stop devredeyse kâr koşsun diye uygulanmaz
        if MAKS_BEKLEME_DK and not p.get("iz_aktif") and (simdi() - p["giris_zamani"]).total_seconds() >= MAKS_BEKLEME_DK * 60:
            return self.cik(p, anlik, "SURE DOLDU", maker=False)
        return None

    def ozet(self):
        kazanan = sum(1 for i in self.islemler if i["kar_tl"] > 0)
        n = len(self.islemler)
        oran = f"%{kazanan / n * 100:.0f}" if n else "-"
        toplam = self.ana_para + self.kilitli_kar
        net = toplam - self.baslangic
        baslik = {"grid": "🧱 GRID", "dip": "🎣 DİPTEN ALIM"}.get(self.tur, "🚀 MOMENTUM")
        return (f"{baslik}: {self.ad}" + (f" · en fazla {MAKS_POZISYON} pozisyon" if self.tur == "momentum" else "") + "\n"
                f"  İşlem: {n}  |  Başarı: {oran}\n"
                f"  Ana para: {tl(self.ana_para)} ({usd(self.ana_para)})\n"
                f"  Kasadaki kâr: {tl(self.kilitli_kar)} ({usd(self.kilitli_kar)})\n"
                f"  Net sonuç: {tl(net)} ({usd(net)})\n"
                f"  Toplam komisyon: {tl(self.komisyon_toplam)}"
                + (f"\n  Açık pozisyon: {', '.join(self.acik_coinler())}" if self.pozisyonlar else ""))


def yol_guncelle(p, m):
    """Pozisyonun gördüğü en yüksek kâr (MFE) ve en derin düşüş (MAE), giriş fiyatına göre %."""
    g = p["giris_fiyati"]
    yuk, dus = (m["h"] / g - 1) * 100, (m["l"] / g - 1) * 100
    if yuk > p.get("mfe", 0):
        p["mfe"] = yuk
        p["mfe_dk"] = max(0, round((m["t"] - p["giris_mum_t"]) / 60000) - 1)
    p["mae"] = min(p.get("mae", 0), dus)
    if yuk >= 1.0:
        p["kar1"] = True

def basabas_kontrol(p):
    """Pozisyon +BASABAS_ESIK_YUZDE kâra ulaştıysa stopu girişin biraz üstüne çeker (ayar açıksa)."""
    ay = globals().get("AYAR", {})
    if (not ay.get("bs", 1) or p.get("bs") or p.get("iz_aktif") or p.get("oto") or p.get("takip")
            or p.get("mfe", 0) < BASABAS_ESIK_YUZDE):
        return
    yeni = p["giris_fiyati"] * (1 + BASABAS_PAY_YUZDE / 100)
    if yeni > p["stop"]:
        p["stop"] = yeni
        p["bs"] = True
        bildirim = globals().get("bildir")
        if bildirim:
            bildirim(f"🔒 {p['coin']} +%{p['mfe']:.2f} kâra ulaştı: stop başabaşa çekildi ({fiyat(yeni)}). Artık zararla kapanmaz.")

def iz_guncelle(p, m):
    """İz süren stop: kâr +IZ_BASLAT'a ulaşınca stop, görülen en yüksek fiyatın IZ_MESAFE altına taşınır."""
    if not p.get("iz") and not p.get("takip"):
        return
    p["tepe"] = max(p.get("tepe", p["giris_fiyati"]), m["h"])
    if p.get("takip"):
        # Takip eden stop: stop = tepe × (1 − mesafe), sadece yukarı. Fiyat mesafe + %0,4 yükselince
        # stop alış/satış komisyonunu ve kaymayı da karşılar: işlem artık zararla kapanmaz.
        yeni = takip_stop_fiyati(p["tepe"], p["giris_fiyati"], p.get("zararsiz", p["giris_fiyati"] * 1.0035), p.get("iz_mesafe", 1.0))
        if yeni > p["stop"]:
            p["stop"] = yeni
            if not p.get("iz_aktif") and yeni >= p.get("zararsiz", p["giris_fiyati"] * (1 + BASABAS_PAY_YUZDE / 100)):
                p["iz_aktif"] = True
                bildirim = globals().get("bildir")
                if bildirim:
                    kilit = (yeni / p["giris_fiyati"] - 1) * 100
                    bildirim(f"🔒 {p['coin']} +%{(p['tepe'] / p['giris_fiyati'] - 1) * 100:.2f}: stop kâra geçti ({fiyat(yeni)}, girişe göre %{kilit:+.2f}).\n"
                             f"Artık zararla kapanmaz · fiyat yükseldikçe stop %{p.get('iz_mesafe', 1.0):g} geriden takip ediyor.")
        return
    if p.get("oto"):
        kazanc = (p["tepe"] / p["giris_fiyati"] - 1) * 100
        kilit = oto_kilit(kazanc, p.get("tahmin"))
        if kilit is None:
            return
        yeni = p["giris_fiyati"] * (1 + kilit / 100)
        if p.get("tahmin") and kazanc >= p["tahmin"] and not p.get("hedef_bildi"):
            p["hedef_bildi"] = True
            bildirim = globals().get("bildir")
            if bildirim:
                bildirim(f"🎯 {p['coin']} tahmini hedefe ulaştı (+%{kazanc:.2f}): kârın %90'ı kilitlendi, stop {fiyat(yeni)}.")
    elif p["tepe"] < p["hedef"]:                   # hedef = iz başlama seviyesi
        return
    else:
        yeni = p["tepe"] * (1 - p.get("iz_mesafe", IZ_MESAFE_YUZDE) / 100)
    if yeni > p["stop"]:
        p["stop"] = yeni
        if not p.get("iz_aktif"):
            p["iz_aktif"] = True
            bildirim = globals().get("bildir")
            if bildirim:
                kilit = (yeni / p["giris_fiyati"] - 1) * 100
                bildirim(f"📈 {p['coin']} +%{(p['tepe'] / p['giris_fiyati'] - 1) * 100:.2f}: {'oto ' if p.get('oto') else ''}iz süren stop devrede.\n"
                         f"Stop {fiyat(yeni)} (girişe göre %{kilit:+.2f}) · fiyat yükseldikçe stop da yükselecek.")

def piyasa_ozet():
    pz = globals().get("PIYASA") or {}
    return pz.get("btc5"), pz.get("ort5")

def neden_etiketi(p, sebep, sure_dk, btc_cikis, piy_cikis):
    """Zarar/stop olan işlemin muhtemel nedenleri (birden fazla olabilir). Kârlı işlemler için 'BASARILI'."""
    b = p.get("bilgi", {})
    if sebep == "KAR AL":
        return "BASARILI"
    if sebep == "BASABAS":
        return "BASABAS_KORUDU"
    if sebep == "IZ STOP":
        return "IZ_KAR" if kayit_kar_pozitif(p) else "IZ_ERKEN"
    e = []
    if p.get("mfe", 0) < 0.3 and sure_dk <= 5:
        e.append("ANINDA_DONUS")            # girer girmez geri döndü: zirveden giriş / sahte sıçrama
    if p.get("mfe", 0) >= 1.0:
        e.append("KARI_GERI_VERDI")         # en az +%1 kâra geçip geri döndü: başabaş stop kurtarırdı
    elif p.get("mfe", 0) >= 0.5:
        e.append("YARIM_KAR_GERI")
    if btc_cikis is not None and btc_cikis <= -0.4:
        e.append("BTC_DUSUSU")              # genel piyasa düşerken stop oldu
    if piy_cikis is not None and piy_cikis <= -0.3:
        e.append("PIYASA_GENEL_DUSUS")
    if b.get("hacim_kat", 0) >= 50:
        e.append("ASIRI_HACIM")             # 50x+ hacim: az işlem gören coinde tek alım sıçraması
    if b.get("sicrama", 0) >= 2.0:
        e.append("GEC_GIRIS")               # 5 dk'da %2+ yükselmişken alındı: hareketin sonu
    if b.get("ust_fitil", 0) >= 50:
        e.append("UST_FITIL")               # giriş mumunda satış baskısı (uzun üst fitil)
    if 0 < b.get("hacim24_mtl", 99) < 5:
        e.append("DUSUK_LIKIDITE")          # 24 saatlik hacim 5 milyon TL altı
    if sebep == "SURE DOLDU":
        e.append("YATAY_KALDI")
    elif sure_dk >= 20 and p.get("mfe", 0) < 0.5:
        e.append("YAVAS_ERIME")             # uzun süre yükselmeden yavaşça düştü
    return "+".join(e) or "BELIRSIZ"

def kayit_kar_pozitif(p):
    return p.get("stop", 0) >= p["giris_fiyati"] * 1.004

def kayit_detayi(p, sebep, kayit):
    b = p.get("bilgi", {})
    sure_dk = round((simdi() - p["giris_zamani"]).total_seconds() / 60, 1)
    btc_cikis, piy_cikis = piyasa_ozet()
    return {
        "sure_dk": sure_dk,
        "giris_turu": b.get("tur", "OTO"),
        "sicrama_yuzde": round(b.get("sicrama", 0), 2),
        "hacim_kat": round(b.get("hacim_kat", 0), 1),
        "son_mum_yuzde": round(b.get("mum_yuzde", 0), 2),
        "ust_fitil_yuzde": round(b.get("ust_fitil", 0)),
        "dk_ort_hacim_tl": round(b.get("ort_hacim_tl", 0)),
        "hacim24_milyon_tl": round(b.get("hacim24_mtl", 0), 1),
        "btc_5dk_giris": b.get("btc5"), "piyasa_5dk_giris": b.get("ort5"),
        "btc_5dk_cikis": None if btc_cikis is None else round(btc_cikis, 2),
        "piyasa_5dk_cikis": None if piy_cikis is None else round(piy_cikis, 2),
        "max_kar_yuzde": round(p.get("mfe", 0), 2), "max_kar_dk": p.get("mfe_dk", 0),
        "max_dusus_yuzde": round(p.get("mae", 0), 2),
        "hassasiyet": f"%{SICRAMA_ESIGI_YUZDE:g}/{HACIM_KATSAYISI:g}x",
        "hedef_stop": (f"takip{p.get('iz_mesafe', 0):g}" if p.get("takip") else "oto" if p.get("oto") else f"iz+{(p['hedef'] / p['giris_fiyati'] - 1) * 100:.1f}/{p.get('iz_mesafe', 0):g}" if p.get("iz")
                       else f"%{(p['hedef'] / p['giris_fiyati'] - 1) * 100:.1f}") + f"/%{(1 - p.get('stop0', p['stop']) / p['giris_fiyati']) * 100:.1f}",
        "tepe_yuzde": round((p.get("tepe", p["giris_fiyati"]) / p["giris_fiyati"] - 1) * 100, 2),
        "tahmin_yuzde": b.get("tahmin"), "atr_yuzde": b.get("atr"), "direnc_yuzde": b.get("direnc"),
        "teyit_sn": b.get("teyit_sn"), "cikis_modu": "takip" if p.get("takip") else "oto" if p.get("oto") else ("iz" if p.get("iz") else "sabit"),
        "filtreler": "".join(k for k, a in (("B", "bs"), ("F", "fit"), ("G", "gec"), ("L", "lik"))
                             if globals().get("AYAR", {}).get(a, 1)) or "-",
        "neden": neden_etiketi(p, sebep, sure_dk, btc_cikis, piy_cikis),
    }

def islem_kaydet(kayit):
    # Sütunlar değiştiyse eski dosya kenara alınır (eski_...csv), yeni başlıkla devam edilir
    if os.path.exists(ISLEM_DOSYASI):
        with open(ISLEM_DOSYASI, encoding="utf-8") as f:
            baslik = f.readline().strip()
        if baslik and baslik != ",".join(kayit.keys()):
            os.replace(ISLEM_DOSYASI, ISLEM_DOSYASI.replace(".csv", f"_eski_{int(time.time())}.csv"))
    yeni = not os.path.exists(ISLEM_DOSYASI)
    with open(ISLEM_DOSYASI, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(kayit.keys()))
        if yeni:
            w.writeheader()
        w.writerow(kayit)

def panel_verisi(profiller, calisiyor=True, son_fiyatlar=None):
    """Mini uygulamanın okuyacağı özet. Sıkıştırılıp bağlantıya eklenir (#z=...)."""
    import zlib
    g = globals()
    son_fiyatlar = son_fiyatlar or {}
    p_liste, islemler = [], []
    acik = []
    if "hesaplar" in g:
        profiller = g["hesaplar"]()
    for i, p in enumerate(profiller):
        for z in p.pozisyonlar:
            acik.append({"c": z["coin"], "g": round(z["giris_fiyati"], 6), "h": round(z["hedef"], 6),
                         "st": round(z["stop"], 6), "f": round(son_fiyatlar.get(z["coin"], z["giris_fiyati"]), 6),
                         "m": round(z["tutar"], 2), "t": z["giris_mum_t"],
                         "iz": 1 if z.get("iz") else 0, "oto": 1 if z.get("oto") else 0, "tk": 1 if z.get("takip") else 0, "th": z.get("tahmin"), "ia": 1 if z.get("iz_aktif") else 0, "im": z.get("iz_mesafe", 0),
                         "s0": round(z.get("stop0", z["stop"]), 6), "tp": round(z.get("tepe", z["giris_fiyati"]), 6),
                         "bs": 1 if z.get("bs") else 0, "be": round(z.get("zararsiz", z["giris_fiyati"] * 1.004), 6),
                         "gz": int(z["giris_zamani"].timestamp()), "s": i, "gk": z.get("gk")})
        p_liste.append({"n": p.ad, "tr": p.tur, "on": 1 if g.get("AYAR", {}).get({"grid": "st_g", "dip": "st_d"}.get(p.tur, "st_m"), 1) else 0,
                        "b": round(p.baslangic, 2), "a": round(p.ana_para, 2),
                        "q": round(p.kilitli_kar, 2), "c": round(p.komisyon_toplam, 2),
                        "w": sum(1 for x in p.islemler if x["kar_tl"] > 0), "t": len(p.islemler),
                        "e": [round(v) if abs(v) >= 10 else round(v, 1) for v in getattr(p, "egri", [0])[-16:]]})
        for x in p.islemler[-6:]:
            islemler.append([i, x["coin"], x["kar_tl"], x["kar_yuzde"], x["sebep"], x["cikis_zamani"][-5:], x.get("komisyon_tl")])
    islemler.sort(key=lambda r: r[5], reverse=True)
    ay = g.get("AYAR", {})
    v = {"u": int(time.time()), "k": round(KUR, 2) if KUR else 0, "s": 1 if calisiyor else 0,
         "p": p_liste, "o": acik, "i": islemler[:6], "b": g.get("TG_BOT_ADI", ""),
         "oto": 1 if g.get("otomatik", True) else 0,
         "cl": (g.get("hareketliler") or COINLER)[:12], "n": g.get("taranan_sayisi") or len(COINLER),
         "ls": int(g.get("son_tarama_ts") or time.time()),
         "r": [[c, round(f, 6), round(d, 2), (round(h, 1) if h is not None else None)] for c, f, d, h in g.get("son_radar", [])[:16]],
         "fn": g.get("son_huni", [0, 0, 0, 0, 0]),
         "rj": g.get("REJIM", {}), "gr": g["grid_ozet"]() if "grid_ozet" in g else [],
         "sp": {c: round(son_fiyatlar[c], 6) for c in {z["coin"] for p in profiller for z in p.pozisyonlar} if c in son_fiyatlar},
         "kl": [x["kar_tl"] for p in profiller for x in p.islemler[-60:]],
         "gd": round((sum(p.ana_para + p.kilitli_kar for p in profiller) / g["GUN"]["baslangic"] - 1) * 100, 2)
               if g.get("GUN") and g["GUN"].get("baslangic") else 0,
         "kr": {"e": SICRAMA_ESIGI_YUZDE, "h": HACIM_KATSAYISI},
         "fl": {"f": MIN_FIYAT_TL, "h": MIN_HACIM_TL_24S},
         "ay": {"hs": ay.get("hs", "dengeli"), "sure": MAKS_BEKLEME_DK, "zl": ay.get("zl", GUNLUK_ZARAR_LIMITI),
                "bil": 1 if ay.get("bil", ISLEM_BILDIRIMI) else 0, "oz": ay.get("oz", OZET_ARALIGI_SAAT), "zd": 1 if ay.get("zd") else 0,
                "ka": KAR_AL_YUZDE, "zs": ZARAR_DURDUR_YUZDE, "mp": MAKS_POZISYON,
                "bs": ay.get("bs", 1), "fit": ay.get("fit", 1), "gec": ay.get("gec", 1), "lik": ay.get("lik", 1),
                "cm": CIKIS_MODU, "ib": IZ_BASLAT_YUZDE, "im": IZ_MESAFE_YUZDE,
                "tey": ay.get("tey", 1), "pot": ay.get("pot", 1), "tm": ay.get("tm", 0), "mb": ay.get("mb", 1)},
         "fe": g.get("ELENEN", {})}
    ham = json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(ham, 9)).decode().rstrip("=")

print("✅ Bot motoru hazır.")

# ======================= ÇALIŞTIR =======================

baslangic_tl = BASLANGIC_USD * KUR if KUR else BASLANGIC_USD
if not KUR:
    print("⚠️ Kur yok: bakiye TL yerine dolar gibi sayılacak.")
profiller = [Profil(baslangic_tl)]          # tek strateji (liste olarak tutulur; özet/rapor kodu aynı kalır)

# ---------------- Telegram kumanda ----------------
# Alttaki düğme klavyesi kaldırıldı: bot sohbetin sol altındaki 📱 Panel düğmesiyle ve
# mesajlardaki "📱 Uygulamayı aç" düğmesiyle yönetilir. Yazılı komutlar (tara, durum...) yine çalışır.
KLAVYE = "UYGULAMA"   # yaz(..., klavye=KLAVYE) → mesaja güncel verili uygulama düğmesi eklenir
KLAVYEYI_KALDIR = {"remove_keyboard": True}
AYAR = {"hs": "dengeli", "zl": GUNLUK_ZARAR_LIMITI, "bil": ISLEM_BILDIRIMI, "oz": OZET_ARALIGI_SAAT, "zd": 0,
        "bs": 1, "fit": 1, "gec": 1, "lik": 1, "tey": 1, "pot": 1, "rej": 1, "st_m": 1, "st_g": 1, "st_d": 1,
        "cm": "takip", "tm": 100, "mb": 1, "sv": 3}
ELENEN = {"tarih": None, "fit": 0, "gec": 0, "lik": 0, "tey": 0, "pot": 0, "rej": 0, "mb": 0}    # bugün filtrelere takılan sinyal sayısı
son_radar = []
son_tarama_ts = 0
son_huni = [0, 0, 0, 0, 0]     # son tarama: taranan, yükselen, aday, sinyal, bugünkü alım
BUGUN_ALIM = {"tarih": None, "n": 0}

def alim_say():
    bugun = simdi().date().isoformat()
    if BUGUN_ALIM["tarih"] != bugun:
        BUGUN_ALIM.update(tarih=bugun, n=0)
    BUGUN_ALIM["n"] += 1

def panel_adresi(kaynak):
    """Mini uygulama adresi: güncel özet bağlantıya eklenir (src = uygulamanın nereden açıldığı)."""
    return PANEL_URL.rstrip("#") + "#src=" + kaynak + "&z=" + panel_verisi(profiller, True, son_fiyatlar)

_son_menu = 0
def menu_guncelle(zorla=False):
    """Sohbetteki 📱 Panel menü düğmesini güncel verilerle yeniler (en fazla dakikada bir)."""
    global _son_menu
    if not PANEL_URL or (not zorla and time.time() - _son_menu < 60):
        return
    _son_menu = time.time()
    tg("setChatMenuButton", chat_id=TG_CHAT,
       menu_button={"type": "web_app", "text": "📱 Panel", "web_app": {"url": panel_adresi("menu")}})

def tg(metod, **veri):
    if not (TG_TOKEN and TG_CHAT):
        return {}
    try:
        return OTURUM.post(f"https://api.telegram.org/bot{TG_TOKEN}/{metod}", json=veri, timeout=40).json()
    except Exception as e:
        print(f"(Telegram hatası: {type(e).__name__})")
        return {}

def yaz(metin, klavye=None, satir_ici=None, panel=None):
    """Telegram'a mesaj. klavye=KLAVYE ya da panel verilirse 'Uygulamayı aç' düğmesi eklenir."""
    print(metin)
    if not (TG_TOKEN and TG_CHAT):
        return
    veri = {"chat_id": TG_CHAT, "text": metin}
    dugmeler = list(satir_ici or [])
    if (panel or klavye == KLAVYE) and PANEL_URL:
        dugmeler.append([{"text": "📱 Uygulamayı aç", "web_app": {"url": panel_adresi("in")}}])
    if dugmeler:
        veri["reply_markup"] = {"inline_keyboard": dugmeler}
    elif isinstance(klavye, dict):
        veri["reply_markup"] = klavye
    r = tg("sendMessage", **veri)
    if r and not r.get("ok") and "reply_markup" in veri:      # düğme sorun çıkarırsa düğmesiz gönder
        veri.pop("reply_markup", None)
        tg("sendMessage", **veri)

def bildir(metin):
    """Alım/satım bildirimi: Ayarlar'da kapatıldıysa sadece kayda yazılır."""
    if AYAR.get("bil", True):
        yaz(metin, klavye=KLAVYE)
    else:
        print(metin)

tg("setMyCommands", commands=[
    {"command": "menu", "description": "Düğmeleri göster"},
    {"command": "durum", "description": "Özet ve kasa durumu"},
    {"command": "tara", "description": "Coinleri şimdi tara"},
    {"command": "surum", "description": "Sürüm, güncelleme ve rapor durumu"},
    {"command": "guncelle", "description": "GitHub'daki yeni sürümü şimdi yükle"}])

# Bot kapalıyken gelen eski mesajları atla
guncelleme_no = 0
_eski = tg("getUpdates", timeout=0)
if _eski.get("result"):
    guncelleme_no = _eski["result"][-1]["update_id"] + 1

otomatik = True
calisiyor = True
son_fiyatlar = {}
son_tablo = []

# ---------------- Durumu kaydet / geri yükle (yeniden başlarsa kaldığı yerden devam) ----------------
def durumu_kaydet():
    try:
        veri = {"otomatik": otomatik, "profiller": [], "ayar": AYAR, "gun": GUN, "sure": MAKS_BEKLEME_DK}
        for p in hesaplar():
            pozlar = []
            for z in p.pozisyonlar:
                poz = dict(z)
                poz["giris_zamani"] = z["giris_zamani"].isoformat()
                pozlar.append(poz)
            veri["profiller"].append({
                "ad": p.ad, "ana_para": p.ana_para, "kilitli_kar": p.kilitli_kar,
                "baslangic": p.baslangic, "komisyon_toplam": p.komisyon_toplam,
                "islemler": p.islemler, "bekleme": p.bekleme, "pozisyonlar": pozlar, "egri": p.egri,
                "tur": p.tur, "ek": p.ek})
        veri["rejim"] = REJIM
        gecici = DURUM_DOSYASI + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False)
        os.replace(gecici, DURUM_DOSYASI)
    except Exception as e:
        print(f"(Durum kaydedilemedi: {e})")

def durumu_yukle():
    global otomatik, MAKS_BEKLEME_DK
    if not os.path.exists(DURUM_DOSYASI):
        return False
    try:
        veri = json.load(open(DURUM_DOSYASI, encoding="utf-8"))
        otomatik = veri.get("otomatik", True)
        kayitli = veri.get("ayar", {})
        AYAR.update(kayitli)
        if kayitli.get("sv", 0) < 2:            # eski sürümden geçiş: yeni önerilen ayarlar devreye girer
            AYAR.update(cm="takip", mb=1)
        if kayitli.get("sv", 0) < 3:            # sabit %1 takip mesafesi (tüm stratejiler aynı kural)
            AYAR.update(tm=100, sv=3)
        GUN.update(veri.get("gun", {}))
        MAKS_BEKLEME_DK = veri.get("sure", MAKS_BEKLEME_DK)
        hassasiyet_uygula(AYAR.get("hs", "dengeli"))
        kz_uygula()
        turler = {p.tur: p for p in hesaplar()}
        REJIM.update(veri.get("rejim", {}))
        for k in veri["profiller"]:
            p = turler.get(k.get("tur", "momentum"))
            if p is None:
                continue
            p.ek = k.get("ek", {})
            p.ana_para, p.kilitli_kar = k["ana_para"], k["kilitli_kar"]
            p.baslangic, p.komisyon_toplam = k["baslangic"], k["komisyon_toplam"]
            p.islemler, p.bekleme = k["islemler"], k["bekleme"]
            p.egri = k.get("egri", [0.0])
            eski = k.get("pozisyonlar") or ([k["pozisyon"]] if k.get("pozisyon") else [])
            for z in eski:
                poz = dict(z)
                poz["giris_zamani"] = dt.datetime.fromisoformat(poz["giris_zamani"])
                if p.tur in ("grid", "dip") and not poz.get("takip_gecti"):
                    takip_ekle(poz)              # eski uzak stop yerine %1 takip eden stop
                    print(f"🔁 {poz['coin']} ({p.tur}) takip eden stopa geçti: stop {fiyat(poz['stop'])}")
                poz.setdefault("zararsiz", zararsiz_fiyat(poz["giris_fiyati"], poz.get("giris_komisyon", 0) / poz["tutar"]))
                p.pozisyonlar.append(poz)
        return True
    except Exception as e:
        print(f"(Kayıtlı durum okunamadı, sıfırdan başlanıyor: {e})")
        return False

def tum_ozet(baslik):
    hs = globals()["hesaplar"]() if "hesaplar" in globals() else profiller
    rj = globals().get("REJIM", {})
    toplam = sum(p.ana_para + p.kilitli_kar for p in hs) - sum(p.baslangic for p in hs)
    return (baslik + ("" if otomatik else "\n⏸ Otomatik alış durdurulmuş")
            + (f"\nPiyasa: {dict(AYI='🐻 düşüş', BOGA='🐂 yükseliş', YATAY='↔️ yatay').get(rj.get('d'), '–')} (BTC 1s %{rj.get('b1', 0):+.2f})" if rj else "")
            + f"\n💰 Toplam net: {tl(toplam)}"
            + "\n\n" + "\n\n".join(p.ozet() for p in hs))

hareketliler = []        # son taramada en çok yükselenler (uygulama ve Al listesi için)
taranan_sayisi = 0

NEDEN_ADI = {"ANINDA_DONUS": "anında geri döndü", "KARI_GERI_VERDI": "+%1 kârı geri verdi",
             "YARIM_KAR_GERI": "+%0,5 kârı geri verdi", "BTC_DUSUSU": "BTC düşüşü", "PIYASA_GENEL_DUSUS": "piyasa geneli düştü",
             "ASIRI_HACIM": "aşırı hacim (50x+)", "GEC_GIRIS": "geç giriş (5dk %2+)", "UST_FITIL": "uzun üst fitil",
             "DUSUK_LIKIDITE": "düşük likidite", "YATAY_KALDI": "yatay kaldı", "YAVAS_ERIME": "yavaş eridi", "BELIRSIZ": "belirgin neden yok",
             "BASABAS_KORUDU": "başabaş stop korudu (zarar yok)", "IZ_KAR": "iz süren stop kârı kilitledi",
             "IZ_ERKEN": "iz süren stop erken tetiklendi"}

def neden_okunur(n):
    return ", ".join(NEDEN_ADI.get(x, x) for x in n.split("+"))

def momentum_rejim_engeli():
    """Momentum sadece yükseliş (BOGA) rejiminde alım yapar: yatay piyasada sıçramalar genelde geri döner."""
    return bool(AYAR.get("mb", 1)) and globals().get("REJIM", {}).get("d") != "BOGA"

def filtre_engeli(s):
    """Sinyal alım filtrelerine takılıyor mu? Takılıyorsa nedeni döner (ve günlük sayaç artar)."""
    bugun = simdi().date().isoformat()
    if ELENEN.get("tarih") != bugun:
        ELENEN.update(tarih=bugun, fit=0, gec=0, lik=0, tey=0, pot=0, rej=0, mb=0)
    if not AYAR.get("st_m", 1):
        return "kapali"
    if globals().get("rejim_engel", lambda: False)():
        neden = "rej"
    elif momentum_rejim_engeli():
        neden = "mb"
    elif AYAR.get("gec", 1) and s.get("degisim", 0) > SICRAMA_MAX_YUZDE:
        neden = "gec"
    elif AYAR.get("fit", 1) and s.get("ust_fitil", 0) >= UST_FITIL_MAX:
        neden = "fit"
    elif AYAR.get("lik", 1) and s.get("ort_hacim_tl", 0) < MIN_DK_HACIM_TL:
        neden = "lik"
    else:
        return None
    ELENEN[neden] = ELENEN.get(neden, 0) + 1
    return neden

def _coin_isle(coin, mumlar, yeni_giris):
    """Tek coin: açık pozisyonu kontrol et, sinyal varsa (otomatik açıksa) al. Sinyal bilgisini döndür."""
    son_fiyatlar[coin] = mumlar[-1]["c"]
    for p in profiller:
        for z in [z for z in p.pozisyonlar if z["coin"] == coin]:
            k = p.kontrol_et(z, mumlar)
            if k:
                isaret = "✅" if k["kar_tl"] >= 0 else "🔻"
                bildir(f"{isaret} SATIŞ (demo) | {k['profil']}\n{coin}: {k['sebep']}\n"
                    f"Sonuç: {tl(k['kar_tl'])} ({k['kar_yuzde']}%) | Komisyon: {tl(k['komisyon_tl'])}\n"
                    f"Süre: {k['sure_dk']:g} dk | En yüksek: +{k['max_kar_yuzde']}% | En düşük: {k['max_dusus_yuzde']}%"
                    + ("" if k["neden"] in ("BASARILI", "IZ_KAR") else f"\n🔎 Neden: {neden_okunur(k['neden'])}")
                    + (f"\n📈 Tepe: +%{k['tepe_yuzde']} · kilitlenen: %{k['kar_yuzde']}" if k["sebep"] == "IZ STOP" else ""))
    s = sinyal_hesapla(mumlar)
    if not yeni_giris or not s:
        return s
    bos_yer = any(p.serbest() and coin not in p.acik_coinler() and time.time() >= p.bekleme.get(coin, 0) for p in profiller)
    # 1) Teyit bekleyen sinyal: sinyal mumundan sonra yeni bir mum kapandı mı, sıçramayı korudu mu?
    b = BEKLEYEN.get(coin)
    if b:
        kap_son = mumlar[-2]
        if kap_son["t"] > b["t"]:
            del BEKLEYEN[coin]
            if kap_son["c"] >= b["orta"] and mumlar[-1]["c"] >= b["orta"] and bos_yer:
                sg = dict(b["s"], fiyat=mumlar[-1]["c"], teyit_sn=round(time.time() - b["zaman"]))
                return _alim_yap(coin, mumlar, sg) or s
            if bos_yer:
                ELENEN["tey"] = ELENEN.get("tey", 0) + 1
            return s
        if time.time() - b["zaman"] > TEYIT_BEKLEME_SN:
            del BEKLEYEN[coin]
        return s
    # 2) Yeni sinyal: filtreler → teyit bekle (ya da teyit kapalıysa hemen al)
    if s["sinyal"] and bos_yer:
        engel = filtre_engeli(s)
        if engel:
            s["sinyal"] = False
            s["elendi"] = engel
            return s
        if AYAR.get("tey", 1):
            son = mumlar[-2]
            BEKLEYEN[coin] = {"t": son["t"], "orta": (son["o"] + son["c"]) / 2, "s": dict(s), "zaman": time.time()}
            s["bekliyor"] = True
            return s
        _alim_yap(coin, mumlar, dict(s, teyit_sn=0))
    return s

BEKLEYEN = {}     # teyit bekleyen sinyaller: coin -> {t: sinyal mumu, orta: mumun ortası, s: sinyal, zaman}

def _alim_yap(coin, mumlar, s):
    """Hedef tahmini yapar, potansiyel yetersizse almaz; değilse alır ve bildirir."""
    if not AYAR.get("st_m", 1) or globals().get("rejim_engel", lambda: False)():
        return None
    if momentum_rejim_engeli():                      # teyit beklerken piyasa yükselişten çıktıysa alma
        ELENEN["mb"] = ELENEN.get("mb", 0) + 1
        return None
    try:
        uzun = mumlari_al(coin + "TRY", 120)         # direnç için daha uzun geçmiş
    except Exception:
        uzun = mumlar
    ht = hedef_tahmini(uzun, s["fiyat"], s.get("degisim", 0))
    if AYAR.get("pot", 1) and ht["tahmin"] is not None and ht["tahmin"] < MIN_POTANSIYEL_YUZDE:
        ELENEN["pot"] = ELENEN.get("pot", 0) + 1
        return None
    for p in profiller:
        if p.serbest() and coin not in p.acik_coinler() and time.time() >= p.bekleme.get(coin, 0):
            bilgi = giris_bilgisi(coin, s, "OTO")
            bilgi.update(ht, teyit_sn=s.get("teyit_sn"))
            poz = p.gir(coin, s["fiyat"], mumlar[-1]["t"], bilgi)
            if poz:
                alim_say()
                tah = f"Tahmini hedef: {fiyat(poz['giris_fiyati'] * (1 + ht['tahmin'] / 100))} (+%{ht['tahmin']:g})" if ht["tahmin"] else ""
                bildir(f"🟢 ALIŞ (demo, otomatik) | {p.ad}\n{coin}: {fiyat(poz['giris_fiyati'])} TL · Tutar: {tl(poz['tutar'])}\n"
                    f"Sıçrama: {s['degisim']:+.2f}% | Hacim: {s['hacim_kat']:.1f}x"
                    + (f" | Teyit: {s['teyit_sn']} sn" if s.get("teyit_sn") else "") + "\n"
                    + (f"Takip stop: tepenin %{poz['iz_mesafe']:g} altı · Stop: {fiyat(poz['stop'])}" + (f"\n{tah} (satış hedefi değil)" if tah else "")
                       if poz.get("takip") else
                       tah + f" | Stop: {fiyat(poz['stop'])}" if poz.get("oto") else
                       f"İz başlar: {fiyat(poz['hedef'])} | Stop: {fiyat(poz['stop'])}" if poz.get("iz")
                       else f"Hedef: {fiyat(poz['hedef'])} | Stop: {fiyat(poz['stop'])}"))
            return poz
    return None

PIYASA = {"btc5": None, "ort5": None}

def giris_bilgisi(coin, s, tur):
    """Alım anındaki koşullar (işlem kaydına yazılır, stop nedenini anlamak için)."""
    btc, ort = PIYASA.get("btc5"), PIYASA.get("ort5")
    return {"tur": tur, "sicrama": s.get("degisim", 0), "hacim_kat": s.get("hacim_kat", 0),
            "mum_yuzde": s.get("mum_yuzde", 0), "ust_fitil": s.get("ust_fitil", 0),
            "ort_hacim_tl": s.get("ort_hacim_tl", 0), "hacim24_mtl": HACIM24.get(coin, 0) / 1e6,
            "btc5": None if btc is None else round(btc, 2), "ort5": None if ort is None else round(ort, 2)}

POZ_KONTROL_SN = 5         # açık pozisyonlar bu sıklıkla kontrol edilir (canlı stop için) (tam tarama dakikada bir)

def pozisyonlari_kontrol():
    """Açık pozisyonların ve teyit bekleyen sinyallerin hızlı kontrolü (15 sn'de bir)."""
    for c in [c for p in profiller for c in p.acik_coinler()]:
        try:
            m = mumlari_al(c + "TRY", 40)
        except Exception:
            continue
        _coin_isle(c, m, False)
    if otomatik:
        for c in list(BEKLEYEN):
            try:
                m = mumlari_al(c + "TRY", 40)
            except Exception:
                continue
            _coin_isle(c, m, True)

def tara(yeni_giris=True, detay=0):
    """Tüm coinleri tarar. Önce hepsinin 5 dk değişimi tek seferde alınır; sadece hareketlenenler,
    açık pozisyonlar ve (detay>0 ise) en çok yükselen 'detay' kadar coin mum mum incelenir."""
    global hareketliler, taranan_sayisi
    coin_listesi_guncelle()
    toplu = toplu_5dk_degisim(COINLER)
    if toplu:
        degisimler = sorted(v[0] for v in toplu.values())
        PIYASA.update(btc5=toplu["BTC"][0] if "BTC" in toplu else None,
                      ort5=degisimler[len(degisimler) // 2] if degisimler else None)
    acik = [c for p in profiller for c in p.acik_coinler()]
    if toplu:
        for c, (_, f) in toplu.items():
            son_fiyatlar[c] = f
        sirali = sorted(toplu.items(), key=lambda x: -x[1][0])
        adaylar = [c for c, (yz, _) in sirali if yz >= SICRAMA_ESIGI_YUZDE * 0.5]
        adaylar += [c for c, _ in sirali[:detay]]
    else:
        sirali = []
        adaylar = list(COINLER)          # toplu veri yoksa hepsine tek tek bakılır (daha yavaş)
    incelenecek = list(dict.fromkeys(acik + list(BEKLEYEN) + adaylar))
    bilgiler = {}
    for coin in incelenecek:
        try:
            mumlar = mumlari_al(coin + "TRY", 40)
        except Exception:
            continue
        s = _coin_isle(coin, mumlar, yeni_giris)
        if s:
            bilgiler[coin] = s
        time.sleep(0.15)
    tablo = []
    if sirali:
        for c, (yz, f) in sirali:
            s = bilgiler.get(c)
            tablo.append((c, s if s else {"fiyat": f, "degisim": yz, "hacim_kat": None, "sinyal": False}))
    else:
        tablo = sorted(bilgiler.items(), key=lambda x: -x[1]["degisim"])
    taranan_sayisi = len(toplu) if toplu else len(COINLER)
    global son_radar, son_tarama_ts, son_huni
    son_tarama_ts = time.time()
    son_radar = [(c, s["fiyat"], s["degisim"], s.get("hacim_kat")) for c, s in sorted(tablo, key=lambda x: -x[1]["degisim"])[:16]]
    if not toplu and bilgiler:
        degisimler = sorted(b["degisim"] for b in bilgiler.values())
        PIYASA.update(btc5=bilgiler["BTC"]["degisim"] if "BTC" in bilgiler else None,
                      ort5=degisimler[len(degisimler) // 2])
    bugun = simdi().date().isoformat()
    son_huni = [taranan_sayisi, sum(1 for _, s in tablo if s["degisim"] > 0),
                len(set(incelenecek) - set(acik)), sum(1 for s in bilgiler.values() if s["sinyal"]),
                BUGUN_ALIM["n"] if BUGUN_ALIM["tarih"] == bugun else 0]
    hareketliler = list(dict.fromkeys(acik + [c for c, _ in tablo[:12]]))[:12]
    return tablo

def tablo_metni(tablo, adet=15):
    if not tablo:
        return "Veri alınamadı."
    sirali = sorted(tablo, key=lambda x: -x[1]["degisim"])[:adet]
    satirlar = []
    for c, s in sirali:
        hk = f"{s['hacim_kat']:.1f}x" if s.get("hacim_kat") is not None else "–"
        satirlar.append(f"{'🔥' if s['sinyal'] else '•'} {c}: {fiyat(s['fiyat'])} TL | 5dk {s['degisim']:+.2f}% | hacim {hk}")
    return (f"🔍 Tarama ({simdi():%H:%M}) · {taranan_sayisi} coin tarandı\n"
            f"Kural: 5dk ≥ +%{SICRAMA_ESIGI_YUZDE} ve hacim ≥ {HACIM_KATSAYISI}x\n"
            f"En çok yükselen {len(sirali)} coin:\n\n" + "\n".join(satirlar))

def pozisyon_metni():
    p = profiller[0]
    if not p.pozisyonlar:
        return f"💼 Pozisyonlar\n\nAçık pozisyon yok (en fazla {MAKS_POZISYON})."
    satir = []
    for z in p.pozisyonlar:
        f = son_fiyatlar.get(z["coin"], z["giris_fiyati"])
        deg = (f / z["giris_fiyati"] - 1) * 100
        satir.append(f"{z['coin']} | {tl(z['tutar'])}\n  giriş {fiyat(z['giris_fiyati'])} | şimdi {fiyat(f)} ({deg:+.2f}%)\n"
                     f"  hedef {fiyat(z['hedef'])} | stop {fiyat(z['stop'])}")
    return f"💼 Pozisyonlar ({len(p.pozisyonlar)}/{MAKS_POZISYON})\n\n" + "\n\n".join(satir)

def elle_al(coin, i=0):
    p = profiller[0]
    if coin in p.acik_coinler():
        return yaz(f"⚠️ {coin} pozisyonu zaten açık.", klavye=KLAVYE)
    if not p.serbest():
        return yaz(f"⚠️ En fazla {MAKS_POZISYON} pozisyon açılabilir ({', '.join(p.acik_coinler())}). Önce birini sat ya da Ayarlar'dan sayıyı artır.", klavye=KLAVYE)
    try:
        m = mumlari_al(coin + "TRY", 40)
    except Exception:
        return yaz(f"⚠️ {coin} fiyatı alınamadı, tekrar dene.")
    sg = sinyal_hesapla(m) or {}
    bilgi = giris_bilgisi(coin, sg, "ELLE")
    bilgi.update(hedef_tahmini(m, m[-1]["c"], sg.get("degisim", 0)))
    poz = p.gir(coin, m[-1]["c"], m[-1]["t"], bilgi)
    son_fiyatlar[coin] = m[-1]["c"]
    if poz:
        alim_say()
        yaz(f"🟢 ALIŞ (demo, elle) | {p.ad}\n{coin}: {fiyat(poz['giris_fiyati'])} TL · Tutar: {tl(poz['tutar'])}\n"
            + (f"Takip stop: tepenin %{poz['iz_mesafe']:g} altı" if poz.get("takip") else
               f"Tahmini hedef: {fiyat(poz['hedef'])}" if poz.get("oto") else f"İz başlar: {fiyat(poz['hedef'])}" if poz.get("iz") else f"Hedef: {fiyat(poz['hedef'])}")
            + f" | Stop: {fiyat(poz['stop'])}", klavye=KLAVYE)
    else:
        yaz("⚠️ Alım için boşta para kalmadı.", klavye=KLAVYE)

def elle_sat(j, s=0):
    p = hesaplar()[s] if "hesaplar" in globals() else profiller[0]
    if not (0 <= j < len(p.pozisyonlar)):
        return yaz("ℹ️ Bu pozisyon artık açık değil.", klavye=KLAVYE)
    z = p.pozisyonlar[j]
    coin = z["coin"]
    try:
        f = mumlari_al(coin + "TRY", 40)[-1]["c"]
    except Exception:
        return yaz(f"⚠️ {coin} fiyatı alınamadı, tekrar dene.")
    k = p.cik(z, f, "ELLE SATIS", maker=False)
    isaret = "✅" if k["kar_tl"] >= 0 else "🔻"
    yaz(f"{isaret} SATIŞ (demo, elle) | {p.ad}\n{coin}: {tl(k['kar_tl'])} ({k['kar_yuzde']}%) | Komisyon: {tl(k['komisyon_tl'])}\nSüre: {k['sure_dk']:g} dk | En yüksek: +{k['max_kar_yuzde']}% | En düşük: {k['max_dusus_yuzde']}%", klavye=KLAVYE)

def rapor_gonder():
    if not os.path.exists(ISLEM_DOSYASI):
        return yaz("ℹ️ Henüz kapanmış işlem yok, rapor boş.")
    try:
        with open(ISLEM_DOSYASI, "rb") as f:
            OTURUM.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument",
                        data={"chat_id": TG_CHAT, "caption": "📁 Tüm demo işlemleri (Excel'de açılabilir)"},
                        files={"document": ("kripto_demo_islemler.csv", f)}, timeout=30)
    except Exception as e:
        yaz(f"⚠️ Rapor gönderilemedi: {type(e).__name__}")

def komut_isle(metin):
    global otomatik, calisiyor
    m = metin.strip().lower()
    if m.startswith("/start ") and len(m.split()) == 2:     # uygulamadan gelen kısa komut (t.me/bot?start=...)
        return komut_kodu(metin.split()[1])
    if m in ("/start", "/menu", "menu"):
        tg("sendMessage", chat_id=TG_CHAT, text="⌨️ Eski düğmeler kaldırıldı.", reply_markup=KLAVYEYI_KALDIR)
        yaz("🤖 Momentum hazır. Uygulamayı aşağıdaki düğmeden ya da sol alttaki 📱 Panel'den açabilirsin.", klavye=KLAVYE)
    elif "tara" in m:
        yaz("⏳ Taranıyor...")
        yaz(tablo_metni(tara(yeni_giris=otomatik, detay=15)))
    elif "durum" in m:
        yaz(tum_ozet(f"📊 Durum ({simdi():%H:%M})"), klavye=KLAVYE)
    elif "pozisyon" in m:
        yaz(pozisyon_metni())
    elif "al" == m.replace("🟢", "").strip():
        liste = hareketliler or COINLER[:12]
        sira = [liste[i:i + 4] for i in range(0, len(liste), 4)]
        yaz("Hangi coini almak istiyorsun? (demo · en hareketli coinler)",
            satir_ici=[[{"text": c, "callback_data": f"al:{c}"} for c in s] for s in sira])
    elif "sat" == m.replace("🔴", "").strip():
        acik = profiller[0].pozisyonlar
        if not acik:
            yaz("ℹ️ Satılacak açık pozisyon yok.")
        else:
            yaz("Hangi pozisyonu satayım?",
                satir_ici=[[{"text": f"{z['coin']} · {tl(z['tutar'])}", "callback_data": f"sat:{j}"}] for j, z in enumerate(acik)])
    elif "durdur" in m:
        otomatik = False
        yaz("⏸ Otomatik alış durduruldu. Açık pozisyonların hedef/stop takibi sürüyor.", klavye=KLAVYE)
    elif "başlat" in m or "baslat" in m:
        otomatik = True
        yaz("▶️ Otomatik alış açık. Sinyal gelince bot kendisi alacak.", klavye=KLAVYE)
    elif "rapor" in m:
        rapor_gonder()
    else:
        yaz("Anlamadım. Düğmeleri kullan ya da /menu yaz.", klavye=KLAVYE)

def hassasiyet_uygula(ad):
    global SICRAMA_ESIGI_YUZDE, HACIM_KATSAYISI
    if ad in HASSASIYETLER:
        SICRAMA_ESIGI_YUZDE, HACIM_KATSAYISI = HASSASIYETLER[ad]
        AYAR["hs"] = ad

def kz_uygula():
    """Kayıtlı kâr/zarar ve pozisyon sayısı ayarlarını devreye alır."""
    global KAR_AL_YUZDE, ZARAR_DURDUR_YUZDE, MAKS_POZISYON, CIKIS_MODU, IZ_BASLAT_YUZDE, IZ_MESAFE_YUZDE
    CIKIS_MODU = AYAR.get("cm", CIKIS_MODU)
    if CIKIS_MODU not in ("takip", "oto", "iz", "sabit"):
        CIKIS_MODU = "takip"
    IZ_BASLAT_YUZDE = AYAR.get("ib", IZ_BASLAT_YUZDE)
    IZ_MESAFE_YUZDE = AYAR.get("im", IZ_MESAFE_YUZDE)
    KAR_AL_YUZDE = AYAR.get("ka", KAR_AL_YUZDE)
    ZARAR_DURDUR_YUZDE = AYAR.get("zs", ZARAR_DURDUR_YUZDE)
    MAKS_POZISYON = AYAR.get("mp", MAKS_POZISYON)

def ayar_uygula(ad, deger):
    """Uygulamadaki Ayarlar panelinden gelen değişiklikler."""
    global MAKS_BEKLEME_DK
    if ad == "hs" and deger in HASSASIYETLER:
        hassasiyet_uygula(deger)
        yaz(f"⚡ Hassasiyet: {deger.capitalize()} · sinyal için 5 dk'da +%{SICRAMA_ESIGI_YUZDE} ve {HACIM_KATSAYISI:g}x hacim", klavye=KLAVYE)
    elif ad == "sure" and deger in ("0", "30", "60", "120", "240"):
        MAKS_BEKLEME_DK = int(deger)
        yaz("⏱ Süre sınırı kaldırıldı: pozisyonlar sadece stop / hedef / iz stop ile kapanır." if MAKS_BEKLEME_DK == 0
            else f"⏱ Pozisyon süresi: en fazla {MAKS_BEKLEME_DK} dk (iz süren stop devredeyse uygulanmaz)", klavye=KLAVYE)
    elif ad == "zl" and deger in ("0", "2", "3", "5"):
        AYAR["zl"] = int(deger)
        yaz("🛡️ Günlük zarar limiti " + (f"%{deger} olarak ayarlandı" if deger != "0" else "kapatıldı"), klavye=KLAVYE)
    elif ad == "bil" and deger in ("0", "1"):
        AYAR["bil"] = deger == "1"
        yaz("🔔 Alım/satım mesajları " + ("açık" if AYAR["bil"] else "kapalı (işlemler uygulamada görünmeye devam eder)"), klavye=KLAVYE)
    elif ad == "kz" and "-" in deger:
        try:
            ka, zs = (int(x) / 10 for x in deger.split("-"))
        except ValueError:
            return yaz("ℹ️ Bu ayarı tanımadım.", klavye=KLAVYE)
        if not (0.5 <= ka <= 10 and 0.5 <= zs <= 5):
            return yaz("⚠️ Kâr %0,5–10, zarar %0,5–5 arasında olmalı.", klavye=KLAVYE)
        AYAR["ka"], AYAR["zs"] = ka, zs
        kz_uygula()
        yaz(f"🎯 Kâr al %{ka:g} · 🛑 Zarar durdur %{zs:g}".replace(".", ",") +
            "\nYeni açılan pozisyonlara uygulanır; açık pozisyonlar kendi hedef/stop değeriyle devam eder.", klavye=KLAVYE)
    elif ad == "mp" and deger in ("1", "2", "3"):
        AYAR["mp"] = int(deger)
        kz_uygula()
        yaz(f"📦 Aynı anda en fazla {deger} pozisyon · boştaki para eşit bölünür.", klavye=KLAVYE)
    elif ad == "tm" and deger in ("0", "75", "100", "150", "200"):
        AYAR["tm"] = int(deger)
        yaz(("📏 Takip mesafesi: otomatik (coinin oynaklığına göre %0,7–2)" if deger == "0"
             else f"📏 Takip mesafesi: %{int(deger) / 100:g} · stop tepenin bu kadar altında durur").replace(".", ",")
            + "\nYeni açılan pozisyonlara uygulanır.", klavye=KLAVYE)
    elif ad == "cm" and deger == "takip":
        AYAR["cm"] = deger
        kz_uygula()
        yaz("📏 Çıkış: takip eden stop · stop hep tepenin altında durur, sadece yukarı çıkar, sabit hedef yok"
            "\nYeni açılan pozisyonlara uygulanır.", klavye=KLAVYE)
    elif ad == "cm" and deger in ("oto", "iz", "sabit"):
        AYAR["cm"] = deger
        kz_uygula()
        yaz(("🤖 Çıkış: oto iz · +%1'de stop +%0,5'e çekilir, kâr büyüdükçe kilitlenen pay %90'a kadar artar" if deger == "oto" else
             "📈 Çıkış: iz süren stop · " + f"+%{IZ_BASLAT_YUZDE:g} kârda başlar, tepenin %{IZ_MESAFE_YUZDE:g} altından takip eder"
             if deger == "iz" else f"🎯 Çıkış: sabit hedef · %{KAR_AL_YUZDE:g} kârda satılır").replace(".", ",")
            + "\nYeni açılan pozisyonlara uygulanır.", klavye=KLAVYE)
    elif ad == "iz" and "-" in deger:
        try:
            parca = deger.split("-")
            ib, im = int(parca[0]) / 10, int(parca[1]) / 100
            zs = int(parca[2]) / 10 if len(parca) > 2 else ZARAR_DURDUR_YUZDE
        except ValueError:
            return yaz("ℹ️ Bu ayarı tanımadım.", klavye=KLAVYE)
        if not (0.5 <= ib <= 5 and 0.25 <= im <= 3 and 0.5 <= zs <= 5):
            return yaz("⚠️ İz başlama %0,5–5, mesafe %0,25–3, stop %0,5–5 arasında olmalı.", klavye=KLAVYE)
        AYAR["ib"], AYAR["im"], AYAR["zs"] = ib, im, zs
        kz_uygula()
        yaz(f"📈 İz süren stop: +%{ib:g} kârda başlar, tepenin %{im:g} altından takip eder · stop %{zs:g}".replace(".", ",")
            + "\nYeni açılan pozisyonlara uygulanır.", klavye=KLAVYE)
    elif ad == "st" and len(deger) == 2 and deger[0] in "mgd" and deger[1] in "01":
        anahtar = "st_" + deger[0]
        AYAR[anahtar] = int(deger[1])
        ad_ = {"m": "🚀 Momentum", "g": "🧱 Grid", "d": "🎣 Dipten alım"}[deger[0]]
        yaz(f"{ad_}: " + ("açık" if AYAR[anahtar] else "durduruldu (yeni alım yok; açık pozisyonlar yönetilmeye devam eder)"), klavye=KLAVYE)
    elif ad in ("bs", "fit", "gec", "lik", "tey", "pot", "rej", "mb") and deger in ("0", "1"):
        AYAR[ad] = int(deger)
        adlar = {"rej": "🐻 Piyasa rejimi filtresi (düşüşte yeni alım yok)",
                 "mb": "🐂 Momentum sadece yükselişte (yatay/düşüşte momentum alımı yok)","tey": "⏳ Giriş teyidi (sonraki mum sıçramayı korursa al)",
                 "pot": f"🎯 Potansiyel filtresi (tahmini hareket < %{MIN_POTANSIYEL_YUZDE:g} ise alma)","bs": f"🔒 Başabaş stop (+%{BASABAS_ESIK_YUZDE:g}'de stop girişe)",
                 "fit": f"🕯 Üst fitil filtresi (≥%{UST_FITIL_MAX})",
                 "gec": f"🏃 Geç giriş filtresi (5dk > %{SICRAMA_MAX_YUZDE:g})",
                 "lik": f"💧 Likidite filtresi (dakikada < {MIN_DK_HACIM_TL:,.0f} TL)".replace(",", ".")}
        yaz(adlar[ad] + (": açık" if AYAR[ad] else ": kapalı"), klavye=KLAVYE)
    elif ad == "oz" and deger in ("0", "1", "4", "24"):
        AYAR["oz"] = int(deger)
        yaz("🕐 Otomatik özet " + ({"0": "kapatıldı", "1": "saatte bir", "4": "4 saatte bir", "24": "günde bir"}[deger]), klavye=KLAVYE)
    else:
        yaz("ℹ️ Bu ayarı tanımadım.", klavye=KLAVYE)

GUN = {"tarih": None, "baslangic": 0.0}
def toplam_deger():
    return sum(p.ana_para + p.kilitli_kar for p in (globals()["hesaplar"]() if "hesaplar" in globals() else profiller))

def gunluk_kontrol():
    """Günlük zarar limiti: aşılırsa otomatik alım ertesi güne kadar durur."""
    global otomatik
    bugun = simdi().date().isoformat()
    if GUN.get("tarih") != bugun:
        GUN.update(tarih=bugun, baslangic=toplam_deger())
        if AYAR.get("zd"):
            AYAR["zd"] = 0
            otomatik = True
            yaz("🌅 Yeni gün: günlük zarar limiti sıfırlandı, otomatik alım yeniden açık.", klavye=KLAVYE)
    zl = AYAR.get("zl", 0)
    if zl and not AYAR.get("zd") and GUN["baslangic"] > 0:
        degisim = (toplam_deger() / GUN["baslangic"] - 1) * 100
        if degisim <= -zl:
            AYAR["zd"] = 1
            otomatik = False
            yaz(f"🛡️ Günlük zarar limiti (%{zl}) aşıldı: bugün {degisim:.2f}%. Otomatik alım yarına kadar durduruldu.", klavye=KLAVYE)

def hesabi_sifirla():
    if os.path.exists(ISLEM_DOSYASI):
        os.remove(ISLEM_DOSYASI)
    profiller[:] = [Profil(baslangic_tl)]
    LAB[:] = [Profil(baslangic_tl, "grid"), Profil(baslangic_tl, "dip")]
    LAB[1].maks = DIP_MAKS_POZ
    AYAR["zd"] = 0
    GUN.update(tarih=None, baslangic=0.0)
    yaz(f"🧹 Demo hesap sıfırlandı. Her strateji yeniden {BASLANGIC_USD} $ ({tl(baslangic_tl)}) ile başlıyor.", klavye=KLAVYE)

def komut_kodu(kod):
    """Mini uygulamadaki düğmelerden gelen kısa komutlar: tara, yenile, al_SOL_0, al_SOL_x, sat_1, oto_1, oto_0, rapor"""
    p = kod.strip().split("_")
    if p[0] == "tara":
        komut_isle("tara")
    elif p[0] in ("yenile", "durum"):
        menu_guncelle(zorla=True)
        yaz(tum_ozet(f"📊 Durum ({simdi():%H:%M})") + "\n\n🔄 Uygulamadaki veriler güncellendi.", klavye=KLAVYE)
    elif p[0] == "al" and len(p) in (2, 3) and p[1].upper() in COINLER:
        elle_al(p[1].upper())
    elif p[0] == "sat" and len(p) in (2, 3, 4) and p[1].isdigit():
        j = int(p[1])
        s = int(p[3]) if len(p) == 4 and p[3].isdigit() and int(p[3]) < len(hesaplar()) else 0
        acik = hesaplar()[s].pozisyonlar
        if len(p) >= 3:                      # coin adı geldiyse sıra kaymış olabilir: doğru pozisyonu bul
            uyan = [k for k, z in enumerate(acik) if z["coin"] == p[2].upper()]
            j = j if j in uyan else (uyan[0] if uyan else -1)
        elle_sat(j, s)
    elif p[0] == "oto" and len(p) == 2:
        komut_isle("▶️ Otomatiği başlat" if p[1] == "1" else "⏸ Otomatiği durdur")
    elif p[0] == "rapor" and "rapor_gonder" in globals():
        rapor_gonder()
    elif p[0] == "ayar" and len(p) == 3:
        ayar_uygula(p[1], p[2])
    elif p[0] == "sifirla" and len(p) == 2 and p[1] == "evet":
        hesabi_sifirla()
    else:
        yaz("ℹ️ Bu komutu tanımadım.", klavye=KLAVYE)
    menu_guncelle(zorla=True)

def dugme_isle(veri):
    if veri.startswith("al:") or veri.startswith("alp:"):
        elle_al(veri.split(":")[1])
    elif veri.startswith("sat:"):
        elle_sat(int(veri.split(":")[1]))

def telegrami_dinle(bekle):
    """Telegram'dan gelen düğme ve mesajları işler (en fazla 'bekle' saniye bekler)."""
    global guncelleme_no
    if not (TG_TOKEN and TG_CHAT):
        time.sleep(bekle)
        return
    r = tg("getUpdates", offset=guncelleme_no, timeout=int(bekle), allowed_updates=["message", "callback_query"])
    for u in r.get("result", []):
        guncelleme_no = u["update_id"] + 1
        if "callback_query" in u:
            cq = u["callback_query"]
            if str(cq["message"]["chat"]["id"]) != str(TG_CHAT):
                continue                                   # sadece senin sohbetin
            tg("answerCallbackQuery", callback_query_id=cq["id"])
            try:
                dugme_isle(cq.get("data", ""))
            except Exception as e:
                yaz(f"⚠️ Hata: {type(e).__name__}")
        elif "message" in u:
            msg = u["message"]
            if str(msg["chat"]["id"]) == str(TG_CHAT) and "web_app_data" in msg:   # uygulamadan sendData
                try:
                    komut_kodu(msg["web_app_data"].get("data", ""))
                except Exception as e:
                    yaz(f"⚠️ Hata: {type(e).__name__}")
                continue
            if str(msg["chat"]["id"]) != str(TG_CHAT) or "text" not in msg:
                continue
            try:
                SON_MESAJ["id"] = msg.get("message_id")
                komut_isle(msg["text"])
            except Exception as e:
                yaz(f"⚠️ Hata: {type(e).__name__}")


# ======================= STRATEJİ LABORATUVARI =======================
# Üç strateji aynı anda, her biri ayrı sanal 100 $ ile çalışır ve sonuçları yan yana karşılaştırılır:
#   🚀 Momentum   : ani sıçramaları yakalar (yukarıdaki kod)
#   🧱 Grid       : BTC/ETH'de merdiven gibi limit alış-satış emirleri; her basamak turunda küçük kâr
#   🎣 Dipten alım: büyük coinlerde aşırı düşüşte limit emirle alır, ortalamaya dönüşte satar
# Ortak koruma — piyasa rejimi: BTC ve genel piyasa düşüşteyse hiçbir strateji yeni alım yapmaz.
GRID_COINLER = ["BTC", "ETH"]
GRID_SEVIYE = 5              # her coin için merkezin altında 5 alış basamağı
GRID_ARALIK_MIN = 0.85       # basamak aralığı en az %0,85 (2 × %0,10 komisyon sonrası ~%0,65 net)
GRID_ARALIK_MAX = 2.0
GRID_BEKLEME_DK = 60         # grid stop olursa bu kadar bekler, sonra yeni fiyattan yeniden kurar
GRID_DUSUSTE_KAPAT = False   # piyasa düşüşe geçince elde kalan grid basamaklarını hemen kapat
DIP_COINLER = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX", "DOGE", "ADA", "LINK", "TRX"]
DIP_Z = 2.2                  # fiyat 60 dk ortalamasının 2,2 standart sapma altına inerse aşırı düşüş sayılır
DIP_MAKS_POZ = 2
DIP_STOP = 1.0               # eskiden %1,5 stop / %0,7 hedef idi: kazanç kayıptan küçüktü
DIP_HEDEF_MIN = 1.0          # ortalamaya uzaklık en az stop kadar değilse alınmaz (en az 1:1)
DIP_HEDEF_MAX = 2.0
DIP_LIMIT_IND = 0.1          # limit alış: anlık fiyatın %0,1 altına
DIP_EMIR_DK = 3              # dolmayan limit emir 3 dk sonra iptal

LAB = [Profil(baslangic_tl, "grid"), Profil(baslangic_tl, "dip")]
LAB[1].maks = DIP_MAKS_POZ

def hesaplar():
    return profiller + LAB

REJIM = {"d": "YATAY", "b1": 0.0, "b4": 0.0, "ts": 0, "bildirim": 0}
_lab_son_tam = 0

def _ort(x):
    return sum(x) / len(x) if x else 0.0

def rejim_guncelle():
    """Piyasa rejimi: BTC'nin 1 ve 4 saatlik değişimi, 4 saatlik ortalaması ve tüm coinlerin genel yönü."""
    try:
        m = mumlari_al("BTCTRY", 302)
    except Exception:
        return
    kap = m[:-1]
    if len(kap) < 241:
        return
    c = kap[-1]["c"]
    b1 = (c / kap[-61]["c"] - 1) * 100
    b4 = (c / kap[-241]["c"] - 1) * 100
    sma = _ort([x["c"] for x in kap[-240:]])
    ort5 = PIYASA.get("ort5")
    eski = REJIM["d"]
    # Düşüş: 4 saatte %2+ düşüş ve ortalamanın altında, ya da 1 saatte %2+ çöküş, ya da tüm piyasa sert düşüyor
    ayi = (b4 <= -2.0 and c < sma) or b1 <= -2.0 or (ort5 is not None and ort5 <= -0.8 and b1 <= -0.5)
    if eski == "AYI" and not ayi:
        ayi = not (b1 >= 0.3 and b4 > -2.0)          # gecikme payı: toparlanma görülmeden düşüş modundan çıkma
    d = "AYI" if ayi else ("BOGA" if c > sma and b1 >= 0 else "YATAY")
    REJIM.update(d=d, b1=round(b1, 2), b4=round(b4, 2), ts=int(time.time()))
    if AYAR.get("rej", 1) and (d == "AYI") != (eski == "AYI") and time.time() - REJIM["bildirim"] > 900:
        REJIM["bildirim"] = time.time()
        if d == "AYI":
            bildir(f"🐻 Piyasa düşüşte (BTC 1s %{b1:+.2f}, 4s %{b4:+.2f}). Paranı korumak için yeni alımlar durdu; açık pozisyonlar stoplarıyla yönetiliyor.")
        else:
            bildir(f"🌤 Piyasa toparlandı (BTC 1s %{b1:+.2f}). Stratejiler yeniden alım yapabilir.")

def rejim_engel():
    return bool(AYAR.get("rej", 1)) and REJIM["d"] == "AYI"

def lab_alim_serbest(anahtar):
    return otomatik and AYAR.get(anahtar, 1) and not rejim_engel()

def lab_satis_bildir(p, k, etiket, sessiz=False):
    isaret = "✅" if k["kar_tl"] >= 0 else "🔻"
    metin = (f"{isaret} {etiket} SATIŞ (demo) | {k['coin']}: {k['sebep']}\n"
             f"Sonuç: {tl(k['kar_tl'])} ({k['kar_yuzde']}%) | Komisyon: {tl(k['komisyon_tl'])} | {k['sure_dk']:g} dk")
    print(metin) if sessiz else bildir(metin)

# ---------------- 🧱 GRID ----------------
def grid_kur(coin, mumlar):
    kap = mumlar[:-1]
    c = kap[-1]["c"]
    atr = _ort([(x["h"] - x["l"]) / x["c"] * 100 for x in kap[-14:]])
    s = max(GRID_ARALIK_MIN, min(GRID_ARALIK_MAX, 4 * atr))
    return {"merkez": c, "s": round(s, 3), "islenen_t": kap[-1]["t"], "durdu": 0,
            "stop": c * (1 - s * (GRID_SEVIYE + 1) / 100)}

def grid_seviyeleri(st):
    return [st["merkez"] * (1 - st["s"] * k / 100) for k in range(1, GRID_SEVIYE + 1)]

def grid_isle(coin, mumlar):
    G = LAB[0]
    durum = G.ek.setdefault("g", {})
    st = durum.get(coin)
    # 1) açık basamaklar: hedefte (limit, maker) sat; stopta hepsini kapat
    for z in [z for z in G.pozisyonlar if z["coin"] == coin]:
        k = G.kontrol_et(z, mumlar)
        if k:
            lab_satis_bildir(G, k, "🧱 GRID", sessiz=k["sebep"] == "KAR AL")
            if k["sebep"] in ("ZARAR DURDUR", "BASABAS") and st:
                st["durdu"] = time.time() + GRID_BEKLEME_DK * 60
    acik = [z for z in G.pozisyonlar if z["coin"] == coin]
    serbest = lab_alim_serbest("st_g")
    # 2) grid kurulumu / yeniden kurulum
    if st and st.get("durdu"):
        if time.time() < st["durdu"]:
            return
        if not acik:
            bildir(f"🧱 Grid {coin}: bekleme bitti, güncel fiyattan yeniden kuruldu.")
            st = None
    if not serbest:
        if rejim_engel() and acik and GRID_DUSUSTE_KAPAT:
            for z in list(acik):           # piyasa düşüşe geçti: elde kalan basamaklar stop beklenmeden kapatılır
                k = G.cik(z, mumlar[-1]["c"], "PIYASA DUSUSU", maker=False)
                lab_satis_bildir(G, k, "🧱 GRID", sessiz=True)
            acik = []
            bildir(f"🧱 Grid {coin}: piyasa düşüşte, eldeki basamaklar kapatıldı (sonuç {tl(sum(x['kar_tl'] for x in G.islemler[-len(acik) or None:]))}).") if False else None
        if st and not acik:
            durum.pop(coin, None)        # düşüşte bekleyen alış emirleri iptal; sonra güncel fiyattan kurulur
        return
    if st is None:
        st = durum[coin] = grid_kur(coin, mumlar)
        return                           # emirler bu andan sonraki mumlarda dolabilir
    kap = mumlar[:-1]
    if not acik and kap[-1]["c"] > st["merkez"] * (1 + st["s"] / 100):
        durum[coin] = grid_kur(coin, mumlar)     # fiyat yükseldi, hiç basamak dolmadı: grid yukarı taşınır
        return
    # 3) alış basamakları: mum düşüğü basamağa değdiyse limit alış dolar
    seviyeler = grid_seviyeleri(st)
    pay = G.ana_para / len(GRID_COINLER) / GRID_SEVIYE
    for m in kap:
        if m["t"] <= st["islenen_t"]:
            continue
        dolu = {z.get("gk") for z in G.pozisyonlar if z["coin"] == coin}
        for k, L in enumerate(seviyeler, 1):
            if k in dolu or m["l"] > L:
                continue
            dolum = min(L, m["o"])                # açılış zaten basamağın altındaysa açılış fiyatından dolar
            poz = G.gir(coin, dolum, m["t"], {"tur": "GRID", "seviye": k}, maker=True, tutar=pay)
            if not poz:
                break
            poz.update(hedef=L * (1 + st["s"] / 100), iz=False, oto=False, gk=k)
            takip_ekle(poz)
            print(f"🧱 Grid {coin} {k}. basamak alındı: {fiyat(dolum)} · satış {fiyat(poz['hedef'])}")
        st["islenen_t"] = m["t"]

def grid_ozet():
    G = LAB[0]
    out = []
    for c, st in G.ek.get("g", {}).items():
        out.append({"c": c, "m": round(st["merkez"], 6), "s": st["s"], "N": GRID_SEVIYE,
                    "n": sum(1 for z in G.pozisyonlar if z["coin"] == c), "d": 1 if st.get("durdu", 0) > time.time() else 0})
    return out

# ---------------- 🎣 DİPTEN ALIM ----------------
def dip_tara():
    D = LAB[1]
    emirler = D.ek.setdefault("emir", {})
    if not lab_alim_serbest("st_d"):
        emirler.clear()
        return
    for coin in DIP_COINLER:
        if coin not in COINLER or coin in D.acik_coinler() or coin in emirler or time.time() < D.bekleme.get(coin, 0):
            continue
        if len(D.pozisyonlar) + len(emirler) >= DIP_MAKS_POZ:
            break
        try:
            m = mumlari_al(coin + "TRY", 302)
        except Exception:
            continue
        kap = m[:-1]
        if len(kap) < 300:
            continue
        kapanis = [x["c"] for x in kap]
        son60 = kapanis[-60:]
        ort60 = _ort(son60)
        std60 = (_ort([(x - ort60) ** 2 for x in son60])) ** 0.5
        if std60 <= 0:
            continue
        z = (kapanis[-1] - ort60) / std60
        trend_ok = _ort(kapanis[-240:]) >= _ort(kapanis[-300:-60])          # 4 saatlik ortalama yükseliyor
        cokus = (kapanis[-1] / kapanis[-6] - 1) * 100 <= -3.0                # 5 dk'da %3+ çöküşe girme
        c = kapanis[-1]
        uzaklik = (ort60 / c - 1) * 100                      # ortalamaya dönüşte beklenen yükseliş
        if z <= -DIP_Z and trend_ok and not cokus and uzaklik >= DIP_HEDEF_MIN:
            hedef = min(DIP_HEDEF_MAX, uzaklik)
            emirler[coin] = {"fiyat": c * (1 - DIP_LIMIT_IND / 100), "t": kap[-1]["t"],
                             "bitis": kap[-1]["t"] + DIP_EMIR_DK * 60000, "hedef": round(hedef, 2), "z": round(z, 2)}
            print(f"🎣 Dip {coin}: z={z:.2f}, limit alış {fiyat(emirler[coin]['fiyat'])} (hedef +%{hedef:.2f})")

def dip_isle(coin, mumlar):
    D = LAB[1]
    for z in [z for z in D.pozisyonlar if z["coin"] == coin]:
        k = D.kontrol_et(z, mumlar)
        if k:
            lab_satis_bildir(D, k, "🎣 DİP")
    emir = D.ek.get("emir", {}).get(coin)
    if not emir:
        return
    for m in mumlar[:-1]:
        if m["t"] <= emir["t"]:
            continue
        if m["l"] <= emir["fiyat"]:
            del D.ek["emir"][coin]
            if not lab_alim_serbest("st_d"):
                return
            dolum = min(emir["fiyat"], m["o"])
            poz = D.gir(coin, dolum, m["t"], {"tur": "DIP", "z": emir["z"], "tahmin": emir["hedef"]}, maker=True)
            if poz:
                poz.update(hedef=dolum * (1 + emir["hedef"] / 100), iz=False, oto=False)
                takip_ekle(poz)
                bildir(f"🎣 DİPTEN ALIM (demo, limit) | {coin}: {fiyat(dolum)} TL · Tutar: {tl(poz['tutar'])}\n"
                       f"Aşırı düşüş (z {emir['z']}) · Hedef: {fiyat(poz['hedef'])} (+%{emir['hedef']:g}) | Stop: {fiyat(poz['stop'])}")
            return
        if m["t"] >= emir["bitis"]:
            del D.ek["emir"][coin]
            return

def lab_isle(tam=False):
    """Grid ve dipten alım stratejilerini çalıştırır (15 sn'de bir; tam=True iken rejim ve dip taraması da)."""
    try:
        if tam:
            rejim_guncelle()
            dip_tara()
        for coin in GRID_COINLER:
            if AYAR.get("st_g", 1) or any(z["coin"] == coin for z in LAB[0].pozisyonlar):
                m = mumlari_al(coin + "TRY", 40)
                son_fiyatlar[coin] = m[-1]["c"]
                grid_isle(coin, m)
        D = LAB[1]
        for coin in set(D.acik_coinler()) | set(D.ek.get("emir", {})):
            m = mumlari_al(coin + "TRY", 40)
            son_fiyatlar[coin] = m[-1]["c"]
            dip_isle(coin, m)
    except Exception as e:
        print(f"(Strateji laboratuvarı hatası: {type(e).__name__}: {e})")

# ---------------- Telegram yedeği ----------------
# Sunucu silinip yeniden kurulsa da geçmiş kaybolmasın: durum ve işlem dökümü 10 dk'da bir
# sohbetteki SABİTLENMİŞ tek bir mesaja dosya olarak yazılır (aynı mesaj güncellenir, sohbet dolmaz).
# Yeni sunucuda dosya yoksa bot bu sabitlenmiş yedeği okuyup kaldığı yerden devam eder.
YEDEK_ADI = "kripto_yedek.json"
YEDEK_ARALIGI_SN = 600
YEDEK = {"mid": None, "son": 0}

def yedek_al(zorla=False):
    if not (TG_TOKEN and TG_CHAT) or not os.path.exists(DURUM_DOSYASI):
        return
    if not zorla and time.time() - YEDEK["son"] < YEDEK_ARALIGI_SN:
        return
    YEDEK["son"] = time.time()
    try:
        with open(DURUM_DOSYASI, encoding="utf-8") as f:
            durum = json.load(f)
        csv_metni = ""
        if os.path.exists(ISLEM_DOSYASI):
            with open(ISLEM_DOSYASI, encoding="utf-8") as f:
                csv_metni = f.read()
        icerik = json.dumps({"durum": durum, "csv": csv_metni, "zaman": simdi().isoformat()},
                            ensure_ascii=False).encode("utf-8")
        aciklama = f"💾 Otomatik yedek · {simdi():%d.%m %H:%M} · silme, sabit kalsın (sunucu yenilenirse buradan devam edilir)"
        url = f"https://api.telegram.org/bot{TG_TOKEN}/"
        if YEDEK["mid"]:
            r = OTURUM.post(url + "editMessageMedia", timeout=30,
                            data={"chat_id": TG_CHAT, "message_id": YEDEK["mid"],
                                  "media": json.dumps({"type": "document", "media": "attach://dosya", "caption": aciklama})},
                            files={"dosya": (YEDEK_ADI, icerik)}).json()
            if r.get("ok") or "not modified" in str(r.get("description", "")):
                return
        r = OTURUM.post(url + "sendDocument", timeout=30,
                        data={"chat_id": TG_CHAT, "caption": aciklama, "disable_notification": "true"},
                        files={"document": (YEDEK_ADI, icerik)}).json()
        if r.get("ok"):
            YEDEK["mid"] = r["result"]["message_id"]
            tg("pinChatMessage", chat_id=TG_CHAT, message_id=YEDEK["mid"], disable_notification=True)
    except Exception as e:
        print(f"(Yedek alınamadı: {type(e).__name__}: {e})")

def yedekten_geri_yukle():
    """Sabitlenmiş yedek mesajını bulur; sunucuda durum dosyası yoksa yedekten geri yükler."""
    if not (TG_TOKEN and TG_CHAT):
        return False
    try:
        pin = tg("getChat", chat_id=TG_CHAT).get("result", {}).get("pinned_message") or {}
        belge = pin.get("document") or {}
        if belge.get("file_name") != YEDEK_ADI:
            return False
        YEDEK["mid"] = pin.get("message_id")
        if os.path.exists(DURUM_DOSYASI):
            return False                       # sunucudaki durum daha güncel
        yol = tg("getFile", file_id=belge["file_id"]).get("result", {}).get("file_path")
        if not yol:
            return False
        paket = OTURUM.get(f"https://api.telegram.org/file/bot{TG_TOKEN}/{yol}", timeout=30).json()
        with open(DURUM_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(paket["durum"], f, ensure_ascii=False)
        if paket.get("csv"):
            with open(ISLEM_DOSYASI, "w", encoding="utf-8") as f:
                f.write(paket["csv"])
        print(f"💾 Yedekten geri yüklendi ({paket.get('zaman', '?')})")
        return True
    except Exception as e:
        print(f"(Yedek okunamadı: {type(e).__name__}: {e})")
        return False

_eski_sifirla = hesabi_sifirla
def hesabi_sifirla():
    _eski_sifirla()
    durumu_kaydet()
    yedek_al(zorla=True)

# ---------------- Uzaktan takip ve otomatik güncelleme ----------------
# 1) Otomatik güncelleme: 10 dk'da bir GitHub'daki kripto_bot.py'ye bakar. Değişmişse yeni kodu indirir,
#    ayrı bir klasörde deneme olarak başlatır (Telegram'sız, işlem yapmadan). Deneme sorunsuzsa durumu
#    kaydeder, eski sürümü kripto_bot_onceki.py olarak saklar ve yeni sürümle kendini yeniden başlatır.
#    Sunucuya girip Reboot etmeye gerek kalmaz.
# 2) Rapor: 15 dk'da bir durum, son hatalar ve işlem dökümü GİZLİ kripto-log deposuna yazılır (Claude takip eder).
#    Bunun için Telegram'dan bir kez:  /github <token>  gönderilir (mesaj hemen silinir, token sadece sunucuda durur).
KOD_DEPO = os.environ.get("KRIPTO_KOD_DEPO", "durlanikbayram1/kripto-panel")
KAYIT_DEPO = os.environ.get("KRIPTO_KAYIT_DEPO", "durlanikbayram1/kripto-log")
GH_TOKEN_DOSYASI = os.path.join(KLASOR, ".github_token")
GUNCELLEME_ARALIGI_SN = 600
RAPOR_ARALIGI_SN = 900
GH_API = "https://api.github.com"
SON_MESAJ = {"id": None}
GUNC = {"son": time.time(), "durum": "bekliyor", "red": None}
RAPOR = {"son": 0, "sha": {}, "csv_ozet": None, "durum": "token yok", "hata_say": 0}
BASLAMA_ZAMANI = time.time()

def _git_sha(veri):
    return hashlib.sha1(b"blob %d\0" % len(veri) + veri).hexdigest()

try:
    with open(os.path.abspath(__file__), "rb") as _f:
        YEREL_SHA = _git_sha(_f.read())
except Exception:
    YEREL_SHA = "?"
SURUM = YEREL_SHA[:7]

def gh_token():
    t = os.environ.get("KRIPTO_GH_TOKEN", "").strip()
    if not t and os.path.exists(GH_TOKEN_DOSYASI):
        try:
            t = open(GH_TOKEN_DOSYASI, encoding="utf-8").read().strip()
        except Exception:
            t = ""
    return t

def _gh_baslik(token=None):
    b = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        b["Authorization"] = "Bearer " + token
    return b

def kuru_test(dosya):
    """Yeni kodu ayrı klasörde, Telegram'sız ve işlem yapmadan başlatır; açılış sorunsuz mu bakar."""
    klasor = os.path.join(KLASOR, "_deneme")
    shutil.rmtree(klasor, ignore_errors=True)
    os.makedirs(klasor)
    hedef = os.path.join(klasor, "kripto_bot.py")
    shutil.copy(dosya, hedef)
    ortam = {k: v for k, v in os.environ.items() if k not in ("KRIPTO_BOT_TOKEN", "KRIPTO_CHAT_ID", "KRIPTO_GH_TOKEN")}
    ortam["KRIPTO_KURU_TEST"] = "1"
    try:
        r = subprocess.run([sys.executable, hedef], cwd=klasor, env=ortam, capture_output=True, text=True, timeout=240)
        cikti = (r.stdout + r.stderr)[-1500:]
        return r.returncode == 0 and "KURU_TEST_TAMAM" in r.stdout, cikti
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        shutil.rmtree(klasor, ignore_errors=True)

def guncelleme_kontrol(zorla=False):
    if KURU_TEST or (not zorla and time.time() - GUNC["son"] < GUNCELLEME_ARALIGI_SN):
        return
    GUNC["son"] = time.time()
    try:
        token = gh_token()
        r = OTURUM.get(f"{GH_API}/repos/{KOD_DEPO}/contents/kripto_bot.py", headers=_gh_baslik(token), timeout=30)
        if r.status_code == 401 and token:                      # token yanlışsa tokensız dene (depo açık)
            r = OTURUM.get(f"{GH_API}/repos/{KOD_DEPO}/contents/kripto_bot.py", headers=_gh_baslik(), timeout=30)
        if r.status_code != 200:
            GUNC["durum"] = f"GitHub {r.status_code}"
            return
        j = r.json()
        if j.get("sha") in (YEREL_SHA, GUNC["red"]):
            GUNC["durum"] = "güncel"
            if zorla:
                yaz(f"✅ Bot güncel (sürüm {SURUM}).")
            return
        yeni = base64.b64decode(j.get("content", ""))
        if _git_sha(yeni) != j.get("sha"):
            GUNC["durum"] = "indirme bozuk"
            return
        try:
            compile(yeni, "kripto_bot.py", "exec")              # yazım hatası varsa burada durur
        except SyntaxError as e:
            GUNC["red"] = j["sha"]
            GUNC["durum"] = f"yeni sürüm {j['sha'][:7]} yazım hatalı (satır {e.lineno}), eski sürümle devam"
            print(f"⛔ {GUNC['durum']}")
            return
        aday = os.path.join(KLASOR, "kripto_bot_yeni.py")
        with open(aday, "wb") as f:
            f.write(yeni)
        print(f"🔄 Yeni sürüm bulundu ({j['sha'][:7]}), deneme çalıştırması yapılıyor...")
        tamam, cikti = kuru_test(aday)
        if not tamam:
            GUNC["red"] = j["sha"]
            GUNC["durum"] = f"yeni sürüm {j['sha'][:7]} denemede çöktü, eski sürümle devam"
            print(f"⛔ Yeni sürüm {j['sha'][:7]} reddedildi (deneme başarısız):\n{cikti}")
            yaz(f"⛔ Yeni sürüm ({j['sha'][:7]}) denemeden geçemedi, bot eski sürümle ({SURUM}) çalışmaya devam ediyor.")
            os.remove(aday)
            return
        durumu_kaydet()
        yedek_al(zorla=True)
        kendi = os.path.abspath(__file__)
        shutil.copy(kendi, os.path.join(KLASOR, "kripto_bot_onceki.py"))
        os.replace(aday, kendi)
        print(f"🔄 Güncelleniyor: {SURUM} → {j['sha'][:7]}")
        yaz(f"🔄 Bot otomatik güncellendi ({SURUM} → {j['sha'][:7]}), yeniden başlıyor. Açık pozisyonlar korunuyor.")
        rapor_yaz(zorla=True)
        os.execv(sys.executable, [sys.executable, kendi] + sys.argv[1:])
    except Exception as e:
        GUNC["durum"] = f"hata: {type(e).__name__}: {e}"
        print(f"(Güncelleme kontrolü yapılamadı: {type(e).__name__}: {e})")

def _gh_yaz(token, yol, icerik, mesaj):
    url = f"{GH_API}/repos/{KAYIT_DEPO}/contents/{yol}"
    veri = {"message": mesaj, "content": base64.b64encode(icerik).decode()}
    sha = RAPOR["sha"].get(yol)
    if sha is None:
        g = OTURUM.get(url, headers=_gh_baslik(token), timeout=30)
        if g.status_code == 200:
            sha = g.json().get("sha")
    if sha:
        veri["sha"] = sha
    r = OTURUM.put(url, headers=_gh_baslik(token), json=veri, timeout=40)
    if r.status_code == 409 or r.status_code == 422:            # sha eskimiş: bir kez tazeleyip yeniden dene
        RAPOR["sha"].pop(yol, None)
        g = OTURUM.get(url, headers=_gh_baslik(token), timeout=30)
        if g.status_code == 200:
            veri["sha"] = g.json().get("sha")
            r = OTURUM.put(url, headers=_gh_baslik(token), json=veri, timeout=40)
    if r.status_code in (200, 201):
        RAPOR["sha"][yol] = r.json()["content"]["sha"]
        return True
    raise RuntimeError(f"{yol}: GitHub {r.status_code} {r.text[:120]}")

def _hata_satirlari():
    anahtar = ("⚠️", "⛔", "❌", "hata", "Hata", "Traceback", "Error", "yapılamadı", "alınamadı", "kaydedilemedi", "okunamadı")
    return [x for x in GUNLUK if any(k in x for k in anahtar)][-60:]

def rapor_yaz(zorla=False):
    if KURU_TEST:
        return
    if not zorla and time.time() - RAPOR["son"] < RAPOR_ARALIGI_SN:
        return
    RAPOR["son"] = time.time()
    token = gh_token()
    if not token:
        RAPOR["durum"] = "token yok (/github ile ver)"
        return
    try:
        durum = {}
        if os.path.exists(DURUM_DOSYASI):
            with open(DURUM_DOSYASI, encoding="utf-8") as f:
                durum = json.load(f)
        paket = {
            "zaman": simdi().isoformat(), "zaman_utc": dt.datetime.utcnow().isoformat() + "Z",
            "surum": SURUM, "calisma_suresi_dk": round((time.time() - BASLAMA_ZAMANI) / 60),
            "otomatik_alim": globals().get("otomatik"), "guncelleme": GUNC["durum"],
            "fiyat_kaynagi": globals().get("aktif_kaynak"), "coin_sayisi": len(globals().get("COINLER", [])),
            "rejim": globals().get("REJIM"), "elenen_bugun": globals().get("ELENEN"),
            "ozet": tum_ozet("Durum"), "son_hatalar": _hata_satirlari(), "son_kayitlar": list(GUNLUK)[-150:],
            "durum_dosyasi": durum,
        }
        icerik = json.dumps(paket, ensure_ascii=False, indent=1, default=str).encode("utf-8")
        _gh_yaz(token, "durum.json", icerik, f"durum {simdi():%d.%m %H:%M} · {SURUM}")
        if os.path.exists(ISLEM_DOSYASI):
            with open(ISLEM_DOSYASI, "rb") as f:
                csv_veri = f.read()
            oz = hashlib.sha1(csv_veri).hexdigest()
            if oz != RAPOR["csv_ozet"]:
                _gh_yaz(token, "islemler.csv", csv_veri, f"işlemler {simdi():%d.%m %H:%M}")
                RAPOR["csv_ozet"] = oz
        RAPOR["durum"] = f"son rapor {simdi():%H:%M}"
        RAPOR["hata_say"] = 0
    except Exception as e:
        RAPOR["hata_say"] += 1
        RAPOR["durum"] = f"rapor yazılamadı: {e}"
        print(f"(Rapor yazılamadı: {type(e).__name__}: {e})")
        if RAPOR["hata_say"] == 3:
            yaz("⚠️ GitHub'a rapor yazılamıyor (3 kez denendi). Token'ın süresi dolmuş ya da kripto-log deposuna "
                "yazma izni yok olabilir. Yeni token için: /github <token>")

def token_kaydet(token):
    token = token.strip()
    if SON_MESAJ["id"]:
        tg("deleteMessage", chat_id=TG_CHAT, message_id=SON_MESAJ["id"])   # token sohbette kalmasın
    if len(token) < 20 or " " in token:
        yaz("⚠️ Token geçersiz görünüyor. Şöyle gönder: /github github_pat_...")
        return
    r = OTURUM.get(f"{GH_API}/repos/{KAYIT_DEPO}", headers=_gh_baslik(token), timeout=30)
    if r.status_code != 200:
        yaz(f"⚠️ Token ile {KAYIT_DEPO} deposuna erişilemedi (GitHub {r.status_code}). "
            "Depo adını ve token'ın bu depoya 'Contents: Read and write' izni olduğunu kontrol et.")
        return
    with open(GH_TOKEN_DOSYASI, "w", encoding="utf-8") as f:
        f.write(token)
    try:
        os.chmod(GH_TOKEN_DOSYASI, 0o600)
    except Exception:
        pass
    RAPOR["hata_say"] = 0
    rapor_yaz(zorla=True)
    yaz("✅ GitHub bağlantısı tamam, token mesajın silindi. Bot artık 15 dk'da bir rapor yazacak "
        f"({RAPOR['durum']}). Claude buradan takip edebilir.")

def surum_metni():
    return (f"🧩 Sürüm: {SURUM} · çalışma: {round((time.time() - BASLAMA_ZAMANI) / 3600, 1)} saat\n"
            f"🔄 Güncelleme: {GUNC['durum']} (10 dk'da bir kontrol)\n"
            f"📤 Rapor: {RAPOR['durum']}")

_eski_komut_isle = komut_isle
def komut_isle(metin):
    m = metin.strip()
    if m.lower().startswith("/github"):
        parca = m.split(maxsplit=1)
        if len(parca) == 2:
            return token_kaydet(parca[1])
        return yaz("Kullanım: /github <token>  (mesaj hemen silinir)")
    if m.lower() in ("/guncelle", "/güncelle", "guncelle", "güncelle"):
        yaz("🔎 GitHub'da yeni sürüm aranıyor...")
        return guncelleme_kontrol(zorla=True)
    if m.lower() in ("/surum", "/sürüm", "surum", "sürüm"):
        return yaz(surum_metni())
    return _eski_komut_isle(metin)

if KURU_TEST:
    _asil_print("KURU_TEST_TAMAM")
    sys.exit(0)

yedekten = yedekten_geri_yukle()
yuklendi = durumu_yukle()
# ---------------- Ana döngü ----------------
if yuklendi:
    yaz(("💾 Sunucu yenilenmiş: geçmiş Telegram yedeğinden geri yüklendi.\n" if yedekten else "")
        + "♻️ Bot sunucuda yeniden başladı, kaldığı yerden devam ediyor.\n" + tum_ozet("Mevcut durum"), klavye=KLAVYEYI_KALDIR)
else:
    yaz(f"▶️ Momentum sunucuda başladı (7/24) | Bakiye: {BASLANGIC_USD} $ ({tl(baslangic_tl)})\n"
        f"Coinler: {len(COINLER)} coin (tüm TL çiftleri) | Kaynak: {aktif_kaynak}\n"
        f"Telefonun kapalıyken de çalışır. 📱 Uygulamayı sol alttaki Panel düğmesinden aç.", klavye=KLAVYEYI_KALDIR)
durumu_kaydet()
yedek_al(zorla=True)
menu_guncelle(zorla=True)

bitis = time.time() + CALISMA_SAATI * 3600 if CALISMA_SAATI else float("inf")
son_tarama = 0
son_poz_kontrol = time.time()
son_ozet = time.time()
tur = 0

try:
    while calisiyor and time.time() < bitis:
      try:
        if time.time() - son_tarama >= KONTROL_ARALIGI_SN:
            tur += 1
            son_tablo = tara(yeni_giris=otomatik)
            son_tarama = time.time()
            if tur == 1:
                print(tablo_metni(son_tablo))
            elif tur % 10 == 0:
                print(f"⏱️ {simdi():%H:%M} | {tur}. tarama tamam" + ("" if otomatik else " (otomatik kapalı)"))
        if time.time() - son_poz_kontrol >= POZ_KONTROL_SN:
            son_poz_kontrol = time.time()
            if any(p.pozisyonlar for p in profiller) or BEKLEYEN:
                pozisyonlari_kontrol()
            lab_isle(tam=time.time() - _lab_son_tam >= KONTROL_ARALIGI_SN)
            if time.time() - _lab_son_tam >= KONTROL_ARALIGI_SN:
                _lab_son_tam = time.time()
        gunluk_kontrol()
        if AYAR.get("oz") and time.time() - son_ozet >= AYAR["oz"] * 3600:
            yaz(tum_ozet(f"🕐 Özet ({simdi():%H:%M})"), klavye=KLAVYE)
            son_ozet = time.time()
        menu_guncelle()
        kalan = max(1, min(KONTROL_ARALIGI_SN - (time.time() - son_tarama), POZ_KONTROL_SN - (time.time() - son_poz_kontrol)))
        telegrami_dinle(min(25, kalan))
        durumu_kaydet()
        yedek_al()
        rapor_yaz()
        guncelleme_kontrol()
      except KeyboardInterrupt:
        raise
      except Exception as e:
        print(f"⚠️ Döngü hatası ({type(e).__name__}: {e}); 15 sn sonra devam.\n" + traceback.format_exc(limit=4))
        time.sleep(15)
except KeyboardInterrupt:
    print("⏹️ Durduruldu.")

durumu_kaydet()
yedek_al(zorla=True)
yaz(tum_ozet("⏹ Bot durdu (sunucu). Yeniden başlayınca kaldığı yerden devam eder."))
print(f"\nİşlem kayıtları: {ISLEM_DOSYASI}")
