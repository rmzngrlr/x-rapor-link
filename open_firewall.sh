#!/bin/bash

echo "========================================"
echo "   Güvenlik Duvarı (UFW) Ayarı - 5000   "
echo "========================================"

if [ "$EUID" -ne 0 ]; then
  echo "HATA: Lütfen bu komutu 'sudo' ile çalıştırın."
  echo "Örnek: sudo ./open_firewall.sh"
  exit 1
fi

echo "5000 Portuna izin veriliyor..."
ufw allow 5000/tcp
echo "Güvenlik duvarı yeniden yükleniyor..."
ufw reload

echo.
echo "İşlem Tamamlandı!"
echo "Yerel IP Adresiniz:"
hostname -I | awk '{print $1}'
echo.
echo "Telefondan bağlanmak için: http://IP_ADRESINIZ:5000"
