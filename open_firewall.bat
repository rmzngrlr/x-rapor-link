@echo off
echo ========================================================
echo X Link Toplayici - Uzaktan Erisim Ayari
echo ========================================================
echo.
echo Bu islem, Web Arayuzune (Port 5000) telefondan erisebilmeniz icin
echo Windows Guvenlik Duvarinda gerekli izni otomatik acacaktir.
echo.
echo Lutfen bu dosyayi SAG TIKLAYIP "Yonetici Olarak Calistir" deyin.
echo.
pause

echo.
echo Kural ekleniyor...
netsh advfirewall firewall add rule name="X_Link_Scraper_Web" dir=in action=allow protocol=TCP localport=5000
echo.
echo Islem Tamamlandi!
echo.
echo Simdi bilgisayarinizin IP adresini asagida gorebilirsiniz.
echo Telefondan baglanmak icin tarayiciya: http://IP_ADRESI:5000 yazin.
echo.
echo IP Adresiniz (IPv4 Address yazan yer):
echo --------------------------------------------------------
ipconfig | findstr "IPv4"
echo --------------------------------------------------------
echo.
pause
