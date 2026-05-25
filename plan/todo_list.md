# Project Implementation Plan

## 01_Requirement_Analysis_and_Design
- **Goal**: Menyiapkan fondasi teknis dan arsitektur sistem.
- **Tasks**:
  - Tentukan environment Python dan virtual environment.
  - Rancang skema database (tabel: `posts`, `keywords`, `logs`, `sessions`).
  - Tentukan struktur direktori (seperti yang sudah dibuat).
  - Pilih library pendukung yang kompatibel dengan lingkungan eksekusi (pertimbangkan alternatif jika `playwright` tidak tersedia).

## 02_Authentication_and_Session_Management
- **Goal**: Menangani login Facebook secara aman dan persisten.
- **Tasks**:
  - Implementasi fungsi `login` dengan penanganan input kredensial.
  - Mekanisme penyimpanan cookie ke file JSON lokal.
  - Fungsi untuk memuat cookie guna menghindari *login loop*.
  - Logika pengecekan status sesi (apakah cookie masih valid atau butuh login ulang).

## 03_Watcher_Engine_Development
- **Goal**: Membangun mesin monitoring real-time.
- **Tasks**:
  - Implementasi loop utama (asynchronous) untuk pengecekan grup.
  - Logika navigasi ke feed grup.
  - Parser konten post (judul, link, timestamp, ID post).
  - Mekanisme rate-limiting (delay antar request) untuk keamanan akun.

## 04_Filtering_and_Processing_Logic
- **Goal**: Menentukan relevansi post dan tindakan otomatis.
- **Tasks**:
  - Implementasi filter kata kunci (blacklist/whitelist).
  - Logika deteksi post yang memenuhi kriteria lelang.
  - Implementasi fungsi auto-comment (simulasi klik/input).
  - Manajemen state agar tidak memproses post yang sama berulang kali.

## 05_Notification_and_Integration
- **Goal**: Menghubungkan sistem dengan user melalui notifikasi.
- **Tasks**:
  - Integrasi Bot API Telegram.
  - Format pesan notifikasi (detail post, link, alasan match).
  - Implementasi webhook handler (jika diperlukan untuk notifikasi eksternal).

## 06_Monitoring_and_Logging
- **Goal**: Memastikan sistem berjalan stabil dan mudah dipantau.
- **Tasks**:
  - Sistem logging ke file dan konsol (DEBUG/INFO/ERROR).
  - Pembuatan dashboard sederhana (bisa berupa CLI output atau file log yang diformat).
  - Implementasi modul statistik (jumlah post dipantau, jumlah match ditemukan).

## 07_Deployment_and_Optimization
- **Goal**: Menjalankan sistem di server produksi.
- **Tasks**:
  - Konfigurasi environment variabel pada server (Linux/VPS).
  - Setup service manager (systemd) agar script berjalan di latar belakang.
  - Pengujian beban (load testing) ringan.
  - Dokumentasi prosedur pemeliharaan (maintenance).
