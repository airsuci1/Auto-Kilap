-- ==============================================================
-- Schema PostgreSQL Database: AutoKilap (Cuci Mobil & Motor Panggilan)
-- ==============================================================

-- 1. Tabel Users (Pelanggan & Admin)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    is_verified INTEGER DEFAULT 0,
    verification_token VARCHAR(255),
    verification_code VARCHAR(20),
    profile_photo VARCHAR(255),
    reset_token VARCHAR(255),
    reset_token_expires VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabel Paket Cuci
CREATE TABLE IF NOT EXISTS packages (
    id SERIAL PRIMARY KEY,
    category VARCHAR(20) NOT NULL, -- 'mobil' atau 'motor'
    name VARCHAR(255) NOT NULL,
    description TEXT,
    duration_minutes INTEGER DEFAULT 60,
    price INTEGER NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabel Slot Jadwal Operasional
CREATE TABLE IF NOT EXISTS time_slots (
    id SERIAL PRIMARY KEY,
    time_slot VARCHAR(20) UNIQUE NOT NULL, -- contoh: '08:00', '09:30'
    label VARCHAR(100) NOT NULL,
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0
);

-- 4. Tabel Pesanan Cuci (Bookings)
CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    booking_code VARCHAR(100) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    package_id INTEGER NOT NULL REFERENCES packages(id),
    vehicle_type VARCHAR(20) NOT NULL, -- 'mobil' atau 'motor'
    vehicle_model VARCHAR(255) NOT NULL,
    license_plate VARCHAR(50) NOT NULL,
    booking_date VARCHAR(20) NOT NULL, -- YYYY-MM-DD
    booking_time VARCHAR(20) NOT NULL, -- HH:MM
    customer_address TEXT NOT NULL,
    customer_notes TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    total_price INTEGER NOT NULL,
    payment_method VARCHAR(50) DEFAULT 'Tunai',
    payment_status VARCHAR(50) DEFAULT 'Belum Bayar', -- 'Belum Bayar' atau 'Lunas'
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'confirmed', 'in_progress', 'completed', 'cancelled'
    admin_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Tabel Blokir Slot Jam
CREATE TABLE IF NOT EXISTS blocked_slots (
    id SERIAL PRIMARY KEY,
    date VARCHAR(20) NOT NULL,
    time_slot VARCHAR(20) NOT NULL,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, time_slot)
);

-- 6. Tabel Kendaraan Tersimpan Milik Pelanggan
CREATE TABLE IF NOT EXISTS user_vehicles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vehicle_type VARCHAR(20) NOT NULL,
    vehicle_model VARCHAR(255) NOT NULL,
    license_plate VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, license_plate)
);

-- 7. Tabel Alamat Tersimpan & Titik Koordinat Peta Pelanggan
CREATE TABLE IF NOT EXISTS user_addresses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label VARCHAR(100) NOT NULL,
    address TEXT NOT NULL,
    notes TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Tabel Pengaturan Sistem & Bisnis
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT
);

-- Indeks untuk optimasi performa pencarian
CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_date_status ON bookings(booking_date, status);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
