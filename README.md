# AutoKilap - Sistem Booking Cuci Mobil & Motor Panggilan Online (PWA)

Sistem aplikasi web progresif (**Progressive Web App / PWA**) modern untuk layanan jasa cuci mobil dan motor panggilan ke rumah (*home service carwash*). Dilengkapi dengan instalasi icon ala aplikasi Android/iOS, verifikasi email, sistem pemilihan slot jadwal anti-bentrok, integrasi tombol WhatsApp admin, serta manajemen paket dan harga oleh admin.

---

## 🚀 Fitur Utama

### 1. Progressive Web App (PWA)
* **Instalasi Mandiri**: Ketika dibuka di smartphone (Android Chrome maupun iOS Safari), muncul rekomendasi / banner *"Tambah ke Layar Utama"* (*Add to Home Screen*) tanpa perlu mengunduh lewat Google Play Store.
* **Manifest & Service Worker**: Berjalan mandiri dalam mode `standalone` dengan icon splash screen dan offline fallback.
* **Mobile-First UX**: Dilengkapi *bottom navigation bar* yang nyaman untuk pengoperasian satu tangan.

### 2. Halaman Depan (Landing Page)
* Informasi lengkap pengenalan layanan cuci panggilan.
* Alur 4 langkah pemesanan yang mudah dipahami.
* Daftar paket & tarif cuci mobil dan motor yang dimuat dinamis dari database.
* Tombol CTA langsung menuju form booking.

### 3. Autentikasi & Verifikasi Email
* Registrasi akun baru (Nama, Email, No. WhatsApp/HP, Password).
* **Verifikasi Email**: Kode OTP 6-digit dan link verifikasi dikirimkan ke email pendaftar.
* Dukungan SMTP riil (Gmail, Mailtrap, dll.) serta *Simulation Box* pada lingkungan pengujian lokal agar mudah diuji langsung tanpa kendala setup SMTP.
* Akun wajib diverifikasi sebelum dapat melakukan login dan pemesanan.

### 4. Sistem Booking Cuci Online
* **Pilihan Kendaraan (Dropdown & In-Place Add)**:
  * Dropdown otomatis menampilkan kendaraan yang pernah diinput oleh pengguna.
  * Tombol **"+ Tambah Kendaraan Baru"** memunculkan formulir input kendaraan secara *inline* langsung di halaman yang sama tanpa harus berpindah halaman (*zero reload*).
  * Data kendaraan yang baru diinput otomatis tersimpan ke akun pelanggan untuk kemudahan booking berikutnya.
* **Pilihan Paket dengan Radio Button & Indikator Aktif**:
  * Setiap kartu paket dilengkapi **Radio Button** di pojok kiri atas.
  * Kartu yang diklik otomatis mendapatkan **border biru tegas**, latar aksen, dan radio button tercentang sehingga pengguna dengan jelas mengetahui paket yang sedang dipilih.
* **Slot Jadwal Real-Time**:
  * Pengguna memilih tanggal booking.
  * Sistem hanya mengizinkan pemilihan **jam kosong / tersedia**.
  * **Jadwal yang telah dikonfirmasi oleh Admin otomatis terkunci (Locked)** dan tidak dapat dipilih lagi oleh pengguna lain.
* **Metode Pembayaran**: Tunai di Tempat (*Cash on Delivery / COD*) langsung ke tim pencuci setelah pekerjaan selesai.
* **Pelacakan Pesanan**: Halaman *"Pesanan Saya"* dengan status dinamis (*Menunggu Konfirmasi*, *Dikonfirmasi*, *Sedang Dicuci*, *Selesai*, *Dibatalkan*).
* **Integrasi WhatsApp Pelanggan**:
  * Tombol *"Hubungi Admin via WhatsApp"* pada halaman rincian pesanan langsung merujuk ke nomor WhatsApp Admin resmi.
  * Pesan otomatis diformat dengan sapaan ke Admin (*"Halo Admin AutoKilap, Saya {nama_pelanggan}..."*) memuat rincian lengkap pesanan.

### 6. Riwayat Transaksi & Pengaturan Akun Pelanggan
* **Halaman Riwayat Transaksi (`/riwayat-transaksi`)**:
  * Tiga kartu metrik ringkasan: Total Transaksi, Selesai Dicuci, dan Total Pengeluaran (Belanja).
  * Filter tab status: *Semua Pesanan*, *Menunggu Konfirmasi*, *Dikonfirmasi & Proses*, *Selesai*, *Dibatalkan*.
  * Detail kartu pemesanan lengkap dengan nomor booking, jadwal, kendaraan, plat, paket cuci, nominal tagihan COD, dan tombol rincian/chat admin serta opsi pesan ulang (*re-order*).
* **Menu Pengaturan Akun (`/account`)**:
  * **Ubah Foto Profil**: Unggah foto profil baru dengan live preview, atau opsi hapus foto untuk menggunakan avatar standar.
  * **Ubah Nama Lengkap & Nomor HP / WhatsApp**: Memperbarui kontak aktif untuk koordinasi tim cuci.
  * **Email Terkunci (Read-Only)**: Alamat email tidak dapat diubah karena merupakan identitas login utama akun.
  * **Ganti Kata Sandi**: Formulir pembaruan kata sandi dengan validasi sandi saat ini dan konfirmasi sandi baru.
  * **Data Tersimpan**: Melihat daftar kendaraan tersimpan dan alamat panggilan yang pernah disimpan pengguna.

### 7. Fitur Lupa Kata Sandi (Password Reset) dengan Expired 10 Menit
* **Permintaan Reset (`/auth/forgot-password`)**:
  * Pengguna memasukkan email terdaftar.
  * Sistem membuat token reset kriptografis yang **otomatis kedaluwarsa dalam 10 menit**.
  * Tautan dikirim ke email pengguna (disertai *Simulation Helper* jika Demo Mode aktif).
* **Pembuatan Sandi Baru (`/auth/reset-password`)**:
  * Tautan diverifikasi terhadap batas waktu 10 menit. Jika melewati batas waktu, sistem otomatis menolak dan membatalkan token.
  * Pengguna membuat kata sandi baru (minimal 6 karakter) dan melakukan konfirmasi.

### 8. Manajemen User & Data Pelanggan Administrator (`/admin/users`)
* **Daftar Seluruh Pengguna**: Memuat nama, email, nomor WhatsApp, foto profil, dan tanggal bergabung.
* **Statistik Pemesanan Tiap Pelanggan**: Menampilkan jumlah transaksi booking yang pernah dibuat dan total belanja akumulatif (*Customer Lifetime Value*).
* **Filter & Pencarian**: Pencarian cepat berdasarkan nama, email, no HP, serta filter role dan status verifikasi.
* **Aksi Langsung**:
  * Tombol hijau 1-klik untuk membuka obrolan WhatsApp ke nomor pelanggan.
  * Tombol ubah role (jadikan Admin atau kembalikan ke Pelanggan).
  * Tombol aktivasi/verifikasi email secara manual jika pelanggan mengalami kendala penerimaan email.

### 9. Informasi Pesanan Aktif Pelanggan (Active Orders Banner)
* Ketika pelanggan yang memiliki pesanan aktif (`pending`, `confirmed`, `in_progress`) melakukan login:
  * **Di Halaman Utama / Beranda (`/`)**: Muncul kartu khusus *"Pesanan Aktif Anda"* di bagian paling atas, menampilkan status live (dengan indikator berkedip/pulse), jenis kendaraan, plat nomor, jadwal kedatangan, dan alamat cuci.
  * **Di Navigasi Global (`base.html`)**: Muncul bar notifikasi pesanan aktif di seluruh halaman dengan tombol 1-klik menuju rincian booking & WhatsApp admin.
  * Setelah pesanan diselesaikan (`completed`) atau dibatalkan, kartu aktif otomatis hilang dari layar.

### 10. Dukungan Penuh Database PostgreSQL
* Menggunakan driver **`psycopg2-binary`** dengan koneksi yang dapat diatur via variabel lingkungan `DATABASE_URL`.
* File skema PostgreSQL lengkap: [`schema_postgres.sql`](file:///d:/PROJECT/Cuci%20Mobil%20Panggilan/schema_postgres.sql).
* Dilengkapi *smart connection wrapper* yang memfasilitasi parameter PostgreSQL (`%s`), auto-commit, dan transisi mulus.



---

## 🛠️ Panduan Menjalankan Sistem

### Persyaratan:
* Python 3.10+
* Dependencies: Flask, Werkzeug, Pillow (sudah terinstal)

### 1. Jalankan Aplikasi
Buka terminal PowerShell pada direktori proyek, lalu jalankan:
```bash
python run.py
```
Aplikasi akan aktif di alamat: `http://localhost:5000`

### 2. Akun Uji Coba Default:
Pada halaman Login (`/auth/login`), terdapat tombol cepat untuk mengisi akun demo berikut:
* **Akun Admin**:
  * Email: `admin@autokilap.com`
  * Password: `admin123`
* **Akun Customer**:
  * Email: `customer@example.com`
  * Password: `user123`

---

## 📱 Panduan PWA di HP Smartphone

1. Buka browser di smartphone (misal Google Chrome di Android atau Safari di iPhone).
2. Akses alamat web (misal via IP lokal Wi-Fi laptop `http://192.168.x.x:5000`).
3. Banner **"Pasang Aplikasi AutoKilap"** akan muncul di bagian bawah:
   * Klik tombol **"+ Tambah Icon"** atau buka menu browser (titik tiga) -> **"Tambahkan ke Layar Utama" / "Install App"**.
4. Ikon **AutoKilap** akan muncul di beranda HP Anda dan dapat dibuka fullscreen seperti aplikasi native.

---

## ⚙️ Konfigurasi Tambahan (`config.py` / Environment Variables)

Untuk mengaktifkan pengiriman email riil melalui SMTP Gmail atau layanan email lain, atur variabel lingkungan berikut:
* `MAIL_SERVER`: contoh `smtp.gmail.com`
* `MAIL_PORT`: `587`
* `MAIL_USERNAME`: email pengirim Anda
* `MAIL_PASSWORD`: App Password email Anda
* `ADMIN_WHATSAPP`: Nomor WhatsApp admin (default: `6281234567890`)
