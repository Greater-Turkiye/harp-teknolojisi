# Harp teknolojisi takibi

Savaşlarda kullanılan teknolojiyle ilgili haberleri tek yerde toplayan bir takip aracı. Burada yeni bilgi üretilmez: herkesin okuyabildiği savunma ve haber sitelerindeki haberler derlenir ve konulara ayrılır. Amaç iki şey. Birincisi, takip etmeyi kolaylaştırmak. İkincisi, teknolojinin ne hızla geliştiğini ve nasıl evrildiğini görmek: küçük bir FPV dronun tank imha etmesi, fiber optik kablonun karıştırıcıları etkisiz kılması, mikrofon ağlarının ucuz bir radara dönüşmesi gibi.

**Son derleme: [SON.md](SON.md)** · **Evrim: [EVRIM.md](EVRIM.md)** · Günlük arşiv: [raporlar/gunluk](raporlar/gunluk) · Saha notları: [saha-notlari](saha-notlari)

## Ne yapar

| Parça | Görevi |
|---|---|
| [`kaynaklar.toml`](kaynaklar.toml) | Kamuya açık RSS akışları: TWZ, Breaking Defense, Naval News, Euromaidan Press, Kyiv Post, War on the Rocks ve diğerleri. Ayrıca her konu için bir Google News araması |
| [`konular.toml`](konular.toml) | 13 konu, her biri neden önemli olduğuyla: fiber optik dronlar, akustik tespit, önleyici dronlar, FPV, elektronik harp, otonomi, insansız deniz ve kara araçları, lazer/mikrodalga, uzun menzilli saldırılar, uydu ve ağlar, zırhın cevabı, üretim ve maliyet |
| [`derle.py`](derle.py) | Akışları çeker, konuya göre süzer, aynı haberi tek kayıtta birleştirir (birden çok yayıncı = önem), kırmızı çizgilerden geçirir, `veri/` ve `raporlar/gunluk/` altına yazar. Yalnızca Python standart kütüphanesi |
| [`EVRIM.md`](EVRIM.md) | Her konunun haftalık haber sayısı ve arşivdeki en eski haberi: hangi teknoloji yükselişte, hangisi durgun |
| [`.github/workflows/derle.yml`](.github/workflows/derle.yml) | Günde iki kez (07:15 ve 19:15 TSİ) testleri çalıştırır, derler ve sonucu depoya işler |
| [`saha-notlari/`](saha-notlari) | Haber akışının ötesinde, tek bir gelişmeyi derinlemesine anlatan notlar: ne, nasıl çalışıyor, sahada ne değişti, karşı önlem, Türkiye için anlamı, kaynaklar |

Elle çalıştırmak için: `python derle.py` (ağa çıkmadan raporu yeniden yazmak için `--kuru`).

## Kurallar

- **Kırmızı çizgiler** ([handbook](https://github.com/Greater-Turkiye/handbook/blob/main/tr/02-red-lines.md)): Türk kuvvetlerinin konum, hareket, konuşlanma veya zafiyetine dair haber derlenmez. Gizli ya da sızdırılmış materyal kullanılmaz. Bu, derleyicide bir kapıdır: şüpheli öğe hiç kaydedilmez ve her raporun sonunda elenen sayısı yazılır. Türk savunma sanayiinin ürün haberleri bu kapsamda değildir.
- **Derleme doğrulama değildir.** Başlıklar kaynağın kendi sözleridir. Bir iddia, birden çok bağımsız yayıncı aynı haberi verdiğinde güç kazanır; raporlar bu sayıyı gösterir.
- **Telif:** Yalnızca başlık, kısa özet ve bağlantı saklanır; makale metni kopyalanmaz.
- **Bu bir yapım kılavuzu değildir.** Saha notları bir teknolojinin ne işe yaradığını ve savaşı nasıl değiştirdiğini anlatır; üretim ya da yapım ayrıntısı içermez.
