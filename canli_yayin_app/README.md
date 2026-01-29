# CCTV Canlı Yayın Paneli

YouTube canlı yayınlarını tek bir ekranda, CCTV tarzı bir ızgara (grid) yapısında izlemenizi sağlayan Web tabanlı bir araçtır.

## Özellikler

*   **Sabit Ekran (No-Scroll):** Kaç yayın eklerseniz ekleyin, hepsi tek ekrana sığar. Aşağı kaydırma gerektirmez.
*   **Dinamik Izgara:** Eklenen yayın sayısına göre ekranı otomatik olarak en verimli şekilde böler.
*   **Gizlenebilir Menü:** Sol taraftaki yönetim panelini gizleyerek ekran alanını maksimize edebilirsiniz.
*   **Kolay Yönetim:** YouTube linki yapıştırıp ekleyebilir, sürükle-bırak ile sıralayabilirsiniz.
*   **Otomatik Sessiz:** Tüm yayınlar başlangıçta sessiz açılır.
*   **Hafıza:** Sayfayı yenileseniz bile listeyi hatırlar.

## Kurulum ve Çalıştırma

Bu projeyi bilgisayarınızda çalıştırmak için **Node.js** yüklü olmalıdır.

1.  Proje klasöründe bir terminal açın.
2.  Gerekli paketleri yüklemek için şu komutu çalıştırın:
    ```bash
    npm install
    ```
3.  Uygulamayı başlatmak için:
    ```bash
    npm run dev
    ```
4.  Terminalde görünen yerel adrese (örn: `http://localhost:5173`) tıklayarak tarayıcınızda açın.

## Kullanım

*   Sol üstteki **Menü** butonuna basarak paneli açın/kapatın.
*   YouTube linkini (video veya canlı yayın) kutuya yapıştırın ve **+** butonuna basın.
*   Yayını kaldırmak için listedeki **Çöp Kutusu** simgesine tıklayın.
*   Sıralamayı değiştirmek için listedeki öğeleri sürükleyip bırakın.

## Windows Arka Planda Çalıştırma (Görev Çubuğu Gizli)

Sistemi başlattığınızda siyah komut ekranının (CMD) görev çubuğunda yer kaplamasını istemiyorsanız, hazırlanan dosyaları kullanabilirsiniz:

1.  **Sistemi Başlatmak İçin:**
    *   `Canlı Yayın.vbs` dosyasına çift tıklayın.
    *   Sistem arka planda çalışmaya başlayacak ve tarayıcınız otomatik olarak açılacaktır.
    *   Ekranda herhangi bir pencere kalabalığı oluşturmaz.

2.  **Sistemi Durdurmak İçin:**
    *   Arka planda çalışan sistemi kapatmak için `durdur.bat` dosyasına çift tıklayın.
    *   (Not: Bu işlem bilgisayardaki tüm çalışan Node.js işlemlerini sonlandırır.)
