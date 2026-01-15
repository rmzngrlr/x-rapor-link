# X Link Toplayıcı (Web + PWA)

Bu proje, X (Twitter) üzerinden belirli tarih aralığındaki tweetlerin linklerini toplamak için geliştirilmiş, **Kalıcı Tarayıcı** ve **İş Kuyruğu** mimarisine sahip modern bir Web Uygulamasıdır.

## 🚀 Özellikler

*   **Web Arayüzü:** Masaüstü programı yerine, ağınızdaki herhangi bir cihazdan (PC, Telefon, Tablet) erişilebilen şık bir web paneli.
*   **Kalıcı Tarayıcı (Persistent Driver):** Sistem, arka planda sürekli açık bir Chrome tarayıcısı tutar. Bu sayede her işlemde tekrar tekrar giriş yapmaz, çok daha hızlı çalışır ve X'in bot korumasına takılmaz.
*   **İş Kuyruğu (Job Queue):** Birden fazla kişi aynı anda işlem başlatsa bile sistem kilitlenmez. Talepleri sıraya alır ve tek tek işler.
*   **Gelişmiş Tarama Modları:**
    *   **Kullanıcı Profili:** Bir kullanıcının ana tweetlerini toplar. (Reklamları ve başkalarının tweetlerini eler).
    *   **Twitter Listesi:** Bir Liste URL'si vererek o listedeki tüm kullanıcıların tweetlerini toplar.
    *   **Sadece Yanıtlar:** Bir kullanıcının sadece *başkalarına* verdiği yanıtları toplar (Kendi floodları ve ana tweetleri hariç).
*   **Mobil Uygulama (PWA):** Telefonda "Ana Ekrana Ekle" diyerek tam ekran, uygulama gibi çalıştırılabilir.
*   **Akıllı Kaydırma (Smart Scroll):** Sayfayı insan gibi kaydırır, yüklemeyi bekler ve hiç tweet kaçırmadan hızlıca toplar.

## 🛠️ Kurulum

### 1. Gereksinimler
*   Python 3.10 veya üzeri.
*   Google Chrome tarayıcısı.

### 2. Windows Kurulumu
1.  Bu klasörde bir komut satırı (CMD) açın.
2.  Gerekli kütüphaneleri yükleyin:
    ```bash
    pip install -r requirements.txt
    ```

### 3. Linux (Ubuntu Desktop) Kurulumu
Ubuntu masaüstü sürümünde terminali açın ve şu komutları sırasıyla uygulayın:

**Sistem Hazırlığı:**
```bash
sudo apt update && sudo apt install python3 python3-pip python3-venv -y
```

**Chrome Kurulumu (Eğer yoksa):**
```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt -f install -y
```

### 4. Ortak Ayarlar
1.  `config.json` dosyasını açın ve kendi X (Twitter) kullanıcı adı ve şifrenizi girin.

## ▶️ Çalıştırma

### Windows'ta
1.  **`start.bat`** dosyasına çift tıklayın. Bu dosya hem Python hem de Node.js sunucusunu başlatacaktır.
2.  Telefondan erişim için **`open_firewall.bat`** dosyasına sağ tıklayıp "Yönetici Olarak Çalıştır" deyin.

### Linux'ta (Ubuntu)
Bu sürüm, **GörüntüX** özelliği için Node.js gerektirir. Lütfen Node.js'in yüklü olduğundan emin olun.

1. Bağımlılıkları yükleyin:
   ```bash
   pip install -r requirements.txt
   cd x-screenshot-araci
   npm install
   cd ..
   ```

2. Sunucuları başlatın:
   ```bash
   chmod +x start.sh
   ./start.sh
   ```
   Bu komut hem Python hem de Node.js sunucusunu başlatacaktır.

Uzaktan (telefondan) erişim için port açmak isterseniz:
```bash
sudo ./open_firewall.sh
```

### Erişim
*   **Bilgisayardan:** `http://localhost:5000`
*   **Telefondan:** Başlatma ekranında yazan IP adresi ile (Örn: `http://192.168.1.20:5000`) bağlanın ve "Ana Ekrana Ekle" diyerek uygulama gibi kullanın.

## 📖 Kullanım Kılavuzu

### Tarama Yapma
1.  **Tarama Türü**nü seçin (Profil, Liste veya Yanıtlar).
2.  **Hedef** bilgisini girin (Kullanıcı adı veya Liste URL'si).
3.  **Tarih** aralığını seçin.
4.  **Başlat**'a basın.

İşlem bittiğinde sonuçları ekranda görebilir, Excel olarak indirebilir veya WhatsApp'tan paylaşabilirsiniz.
