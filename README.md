<div align="center">
  
# 📡 Wi-Fi Room Radar

**Akıllı Ağ ve Konum Analiz Aracı**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](#)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Ağınızdaki cihazların (veya sizin) farklı odalardaki bağlantı kararlılığını analiz eden, gecikme sıçramalarını yakalayan ve verileri istatistiksel olarak karşılaştıran modern bir açık kaynaklı uygulamadır.

[Özellikler](#-özellikler) • [Kurulum](#-kurulum) • [Nasıl Kullanılır](#-nasıl-kullanılır) • [Lisans](#-lisans)

</div>

---

## 🚀 Proje Hakkında

**Wi-Fi Room Radar**, sadece bir ping aracı değildir. Wi-Fi bağlantısının doğası gereği olan anlık dalgalanmaları ve gecikme (latency) paternlerini kullanarak, ağ kalitesini ve cihazların ağ içerisindeki tahmini konum/oda değişimlerini istatistiksel olarak anlamlandırır.

> **⚠️ Önemli Not:** Bu uygulama GPS benzeri kesin bir koordinat sağlamaz; tamamen ağ trafiğindeki gecikme paternlerine (ping) ve sinyal sapmalarına dayalı tahmini ve kıyaslamalı bir sonuç üretir.

<br>

## ✨ Özellikler

| Özellik | Açıklama |
| :--- | :--- |
| 📊 **Anlık Grafik Analizi** | Taranan odadaki ping değerlerini, genel ortalamayı (baseline) ve uyarı sınırlarını canlı ve akıcı bir grafikte çizer. |
| 🧮 **Akıllı İstatistik Motoru** | Ağdaki normal dalgalanmaları (jitter) ayıklar. Yalnızca gerçek fiziksel ve çevresel değişimlerden kaynaklı sıçramaları tespit eder. |
| 🏆 **Odalar Arası Kıyaslama** | Birden fazla odada yapılan ölçümleri yan yana koyarak, ağ kalitesinin en tutarlı veya en sorunlu olduğu bölgeleri belirler. |
| 💾 **Otomatik CSV Kaydı** | Tüm ölçümler ve hesaplanan "değişim skorları" daha sonra incelenebilmesi için otomatik olarak bir Excel/CSV dosyasına kaydedilir. |
| 🎨 **Modern ve Şık Arayüz** | Göz yormayan karanlık tema (Dark Mode), dinamik "hover" efektleri ve pürüzsüz yerleşim düzeni ile kusursuz bir kullanıcı deneyimi sunar. |

<br>

## 🛠 Kurulum

Bu proje **%100 saf Python** ile geliştirilmiştir. Ekstra hiçbir `pip` paketine veya harici bağımlılığa ihtiyacınız yoktur. Sadece bilgisayarınızda Python yüklü olması yeterlidir.

```bash
# 1. Projeyi bilgisayarınıza klonlayın
git clone https://github.com/Winslowe/wifi-room-radar.git

# 2. Proje dizinine girin
cd wifi-room-radar

# 3. Uygulamayı başlatın
python a.py
```

<br>

## 📖 Nasıl Kullanılır?

1. **Hedefi Belirleyin:** Program açıldığında `ÖLÇÜLECEK CİHAZIN IP ADRESİ` kısmına modeminizin veya ağdaki test cihazınızın IP adresini girin (Örn: `192.168.1.1`).
2. **Konumunuzu Girin:** `1. Bulunduğun odanın adını yaz` kısmına şu anki konumunuzu yazın (Örn: `Salon`).
3. **Analizi Başlatın:** `BU ODAYI TARA` butonuna basarak 50 pinglik analiz testini başlatın. Bu süreçte cihazınızı sabit tutmanız verilerin sağlığı için önemlidir.
4. **Keşfe Çıkın:** İlk oda tamamlandığında, farklı bir odaya geçip aynı işlemleri tekrarlayın.
5. **Sonuçları Karşılaştırın:** İşlemler bittiğinde `ODALARI BİTİR` butonuna basarak tüm odaların istatistiksel kıyaslamasını anında görün!

<br>

## 🧪 Test Modu (Geliştiriciler İçin)

Eğer UI arayüzünü açmadan, programın çekirdek istatistik ve ping analiz algoritmalarının düzgün çalışıp çalışmadığını doğrulamak isterseniz:

```bash
python a.py --test
```
Bu komut, sahte (mock) verilerle programın karar alma mekanizmasını hızlıca test eder ve komut satırına rapor verir.

<br>

## 📜 Lisans

Bu proje **MIT Lisansı** ile lisanslanmıştır. Daha fazla bilgi için `LICENSE` dosyasına göz atabilirsiniz. Kodu dilediğiniz gibi kullanabilir, değiştirebilir ve kendi projelerinizde (ticari dahil) değerlendirebilirsiniz.

---
<div align="center">
  <i>Winslowe tarafından ❤️ ile geliştirilmiştir.</i>
</div>
