# Oda Karşılaştırma Ekranı (Radar App)

Oda Karşılaştırma Ekranı, cihazınızın ağ (Wi-Fi) bağlantı kararlılığını farklı odalar arasında ölçerek, ağ değişimine dayalı bir yer tahmini sunan açık kaynaklı bir araçtır. Ağ bağlantısındaki anlık sıçramalar, ping dalgalanmaları ve kopmaları analiz ederek "en fazla değişim olan odayı" belirlemeye çalışır.

> **Önemli:** Bu program kesin bir cihaz veya kişi konumu bulmaz; tamamen Wi-Fi / bağlantı gecikme paternlerine (ping değişimine) dayalı tahmini bir analiz sunar.

## Özellikler

- **Ping Analizi:** Belirtilen IP adresine aralıklı ping göndererek süreleri kaydeder.
- **İstatistiksel Hesaplama:** Anlık ağ yavaşlamalarını filtreleyerek, her odanın standart gecikmesini, kayıp oranını ve değişim skorunu hesaplar.
- **Canlı Grafik:** Taranan odadaki anlık ping değerini, olağan seviyeyi ve uyarı sınırını interaktif bir grafik üzerinde canlı gösterir.
- **Odalar Arası Karşılaştırma:** Birden fazla odayı taradığınızda sonuçları kıyaslayarak hangi odanın daha tutarlı, hangisinin daha dalgalı olduğunu tespit eder.
- **Kayıt Alma (CSV):** Taranan sonuçları otomatik olarak `.csv` formatında aynı dizine kaydeder, böylece daha sonra analiz edebilirsiniz.
- **Kullanıcı Dostu Arayüz:** Gelişmiş, modern ve şık bir karanlık (dark) tema arayüzüne sahiptir. Butonlardaki 'hover' etkileşimleriyle pürüzsüz bir deneyim sunar.

## Kurulum ve Çalıştırma

Program tamamen standart kütüphaneler kullanılarak yazılmıştır. Bu nedenle ek bir bağımlılık kurmanıza gerek yoktur, doğrudan çalıştırabilirsiniz.

**Gereksinimler:**
- Python 3.10 veya üzeri
- Windows, macOS veya Linux

**Nasıl Çalıştırılır:**

1. Kodu bilgisayarınıza indirin.
2. Terminal veya Komut İstemini (CMD) açarak dosyanın bulunduğu klasöre gidin.
3. Aşağıdaki komutu çalıştırın:
```bash
python a.py
```

## Nasıl Kullanılır?

1. **IP Adresini Girin:** Program açıldığında sağ üst köşedeki kutuya ölçmek istediğiniz cihazın yerel ağdaki IP adresini yazın (Örn: `192.168.1.102`).
2. **Oda Adı Yazın:** Uygulamanın üst panelindeki giriş alanına şu an bulunduğunuz odanın adını yazın (Örn: `Salon`, `Yatak Odası`).
3. **Taramayı Başlatın:** "BU ODAYI TARA" butonuna basın ve tarama bitene kadar cihazınızın yerini değiştirmeyin. (Tarama süresince veri indirme gibi işlemleri durdurmanız daha net sonuçlar verir.)
4. **Diğer Odaya Geçin:** İlk odanın 50 ölçümü bittiğinde diğer bir odaya gidin, yeni odanın adını yazıp tekrar "BU ODAYI TARA"ya basın.
5. **Karşılaştırma Yapın:** En az 2 odanın taraması bittiğinde "ODALARI BİTİR" butonuna basarak programın odaları kıyaslamasını sağlayın.

## Test Modu (Geliştiriciler İçin)
Arayüzü açmadan sistemin hesaplama mantığını test etmek isterseniz komut satırından `--test` argümanı ile çalıştırabilirsiniz:
```bash
python a.py --test
```

## Lisans
Bu proje açık kaynaklıdır ve özgürce kullanılabilir, değiştirilebilir. Herhangi bir soruluk kabul edilmez.
