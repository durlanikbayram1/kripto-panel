# kripto-panel — Claude için çalışma kuralları

Bu depo kullanıcının DEMO kripto botudur (sanal para). `kripto_bot.py` Oracle sunucusunda 7/24 çalışır,
`index.html` Telegram Mini App'tir (GitHub Pages).

## Bot kendini günceller
- Bot 10 dk'da bir bu deponun varsayılan dalındaki `kripto_bot.py`'ye bakar. Değişmişse yeni dosyayı
  `KRIPTO_KURU_TEST=1` ile ayrı klasörde deneme olarak başlatır; çıktıda `KURU_TEST_TAMAM` görürse kendini
  yeni sürümle yeniden başlatır (os.execv). Deneme başarısızsa eski sürümle devam eder.
- Bu yüzden main'e yüklenen her sürüm CANLIYA gider. Yüklemeden önce mutlaka:
  1. `python3 -m py_compile kripto_bot.py`
  2. Boş bir klasörde `KRIPTO_KURU_TEST=1 python3 kripto_bot.py` → son satır `KURU_TEST_TAMAM` olmalı.
  3. Değişen mantık için çevrimdışı test (kodu `yedekten = yedekten_geri_yukle()` satırına kadar exec edip
     fonksiyonları sahte verilerle çağır).
- `uzaktan takip` bölümündeki `if KURU_TEST: ... sys.exit(0)` bloğunu, `GUNLUK`/`print` yakalamayı,
  `rapor_yaz()` ve `guncelleme_kontrol()` çağrılarını ASLA kaldırma: kaldırılırsa bot bir daha
  otomatik güncellenemez ve rapor yazamaz.
- Durum dosyası (`kripto_durum.json`) biçimini geriye uyumlu tut: açık pozisyonlar yeniden başlatmada yüklenir.

## Raporlar
Bot 15 dk'da bir gizli `durlanikbayram1/kripto-log` deposuna `durum.json` (sürüm, özet, son hatalar,
son kayıtlar, tam durum) ve `islemler.csv` yazar. `durum.json` 45 dakikadan eskiyse bot durmuş olabilir.

## Sınırlar ve strateji güncellemeleri
- Sadece demo. Gerçek para / borsa API anahtarı ekleme.
- Kullanıcı, zararlı işlemlerin nedenlerini bulup botu kâr edecek şekilde güncellemeye izin verdi; ama
  SADECE yeterli veriyle: ilgili stratejide son değişiklikten bu yana en az 10 zararlı ve 20 kapanmış işlem,
  ve zarar nedeni bunların belirgin kısmında (~%40+) tekrar etmeli. Tek işleme göre değişiklik yapılmaz.
- Strateji başına bir seferde tek değişiklik; geçmiş CSV'de geriye dönük sına; 20 işlem sonra önce/sonra
  karşılaştır, kötüleştiyse geri al. Her değişiklik kripto-log/claude_notlar.md "Değişiklik günlüğü"ne yazılır.
- Kullanıcının temel kuralları değişmez (gerekirse sadece öneri): stop maliyete göre (komisyon dahil),
  coin yükseldikçe stop da yükselir, +%1'den sonra net kârın en az %70'i korunur, tüm TL coinleri taranır
  (alım filtresi eklemek serbest), pozisyonlarda süre sınırı yok, üç strateji ayrı sanal 100 $ ile yarışır.
- Token, chat id gibi gizli bilgiler dosyaya yazılmaz (sunucuda ortam değişkeni / .github_token).
