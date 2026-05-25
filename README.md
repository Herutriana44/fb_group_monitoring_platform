# FB Group Monitoring Platform

## Arsitektur Sistem
1. **Collector Engine**: Menggunakan Playwright (asynchronous) untuk menangani sesi Facebook.
2. **Database**: SQLite untuk penyimpanan lokal yang ringan dan cepat.
3. **Task Processor**: Asyncio worker untuk memproses post dan menjalankan filtering.
4. **Notifier**: Asynchronous client untuk integrasi Telegram/Webhook.

## Struktur Direktori
- `/src`: Source code utama.
- `/data`: Database dan log.
- `/config`: Konfigurasi environment dan rules.
- `/plan`: Dokumentasi rencana kerja.
