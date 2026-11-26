import os
import re
import time
import socket
import datetime
import sqlite3
import logging
from werkzeug.security import generate_password_hash
from config import Config

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

logger = logging.getLogger('database')

_ACTIVE_DB_TYPE = None

# ==============================================================================
# Database Connection & Cursor Wrappers (PostgreSQL Native with SQLite Fallback)
# ==============================================================================

class RowWrapper(dict):
    """Dictionary supporting both column name access (row['name']) and index access (row[0])."""
    def __init__(self, data=None):
        if data:
            formatted = {}
            for k, v in data.items():
                if isinstance(v, (datetime.datetime, datetime.date)):
                    formatted[k] = v.strftime('%Y-%m-%d %H:%M:%S') if isinstance(v, datetime.datetime) else v.strftime('%Y-%m-%d')
                else:
                    formatted[k] = v
            super().__init__(formatted)
            self._keys = list(self.keys())
        else:
            super().__init__()
            self._keys = []

    def __getitem__(self, key):
        if isinstance(key, int):
            if 0 <= key < len(self._keys):
                return super().__getitem__(self._keys[key])
            raise IndexError("Row index out of range")
        return super().__getitem__(key)

    def get(self, key, default=None):
        if isinstance(key, int):
            if 0 <= key < len(self._keys):
                return super().__getitem__(self._keys[key])
            return default
        return super().get(key, default)


class DBCursorWrapper:
    """Cursor wrapper that normalizes parameter syntax (%s vs ?) and provides dict rows & lastrowid."""
    def __init__(self, raw_cursor, is_postgres=True):
        self.raw_cursor = raw_cursor
        self.is_postgres = is_postgres
        self.lastrowid = getattr(raw_cursor, 'lastrowid', None)

    def execute(self, sql, params=None):
        query = sql
        if self.is_postgres:
            # Convert SQLite parameter placeholder (?) to PostgreSQL (%s)
            query = query.replace('?', '%s')
            # If INSERT statement without RETURNING, append RETURNING id to capture lastrowid (skip tables without id like settings)
            clean_query = query.strip()
            if clean_query.upper().startswith('INSERT INTO') and 'RETURNING' not in clean_query.upper():
                table_match = re.search(r'INSERT\s+INTO\s+([a-zA-Z0-9_]+)', query, re.IGNORECASE)
                table_name = table_match.group(1).lower() if table_match else ''
                if table_name != 'settings':
                    query = query.rstrip().rstrip(';') + ' RETURNING id;'
        else:
            # Convert PostgreSQL parameter placeholder (%s) to SQLite (?)
            query = query.replace('%s', '?')
            # Convert PostgreSQL ILIKE to SQLite LIKE
            query = re.sub(r'\bILIKE\b', 'LIKE', query, flags=re.IGNORECASE)

        if params is not None:
            self.raw_cursor.execute(query, params)
        else:
            self.raw_cursor.execute(query)

        if self.is_postgres:
            if query.strip().upper().startswith('INSERT INTO') and 'RETURNING ID' in query.upper():
                try:
                    row = self.raw_cursor.fetchone()
                    if row:
                        self.lastrowid = row.get('id') if isinstance(row, dict) else row[0]
                except Exception:
                    pass
        else:
            self.lastrowid = getattr(self.raw_cursor, 'lastrowid', None)

        return self

    def executemany(self, sql, seq_of_params):
        query = sql
        if self.is_postgres:
            query = query.replace('?', '%s')
        else:
            query = query.replace('%s', '?')
        self.raw_cursor.executemany(query, seq_of_params)
        return self

    def fetchone(self):
        row = self.raw_cursor.fetchone()
        if row is None:
            return None
        return RowWrapper(dict(row))

    def fetchall(self):
        rows = self.raw_cursor.fetchall()
        return [RowWrapper(dict(r)) for r in rows]

    @property
    def rowcount(self):
        return self.raw_cursor.rowcount

    def __iter__(self):
        for row in self.raw_cursor:
            yield RowWrapper(dict(row)) if row is not None else None



class DBConnectionWrapper:
    """Connection wrapper providing .execute() shortcut, .cursor(), .commit(), and .close()."""
    def __init__(self, raw_conn, is_postgres=True):
        self.raw_conn = raw_conn
        self.is_postgres = is_postgres

    def cursor(self):
        return DBCursorWrapper(self.raw_conn.cursor(), self.is_postgres)

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self.raw_conn.commit()

    def rollback(self):
        self.raw_conn.rollback()

    def close(self):
        try:
            from flask import has_request_context
            if has_request_context():
                # In Flask request context, keep connection open until request teardown
                return
        except Exception:
            pass
        try:
            self.raw_conn.close()
        except Exception:
            pass

    def force_close(self):
        try:
            self.raw_conn.close()
        except Exception:
            pass


_PG_AVAILABLE = None
_PG_LAST_PROBE = 0
_PG_PROBE_INTERVAL = 10  # Seconds to cache PostgreSQL availability check

def is_postgres_alive():
    """Ultra-fast (100ms max) socket probe with 10s caching to avoid multi-second connection hangs."""
    global _PG_AVAILABLE, _PG_LAST_PROBE
    if not HAS_PSYCOPG2 or getattr(Config, 'DB_TYPE', 'postgres') != 'postgres':
        return False

    now = time.time()
    if _PG_AVAILABLE is not None and (now - _PG_LAST_PROBE) < _PG_PROBE_INTERVAL:
        return _PG_AVAILABLE

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.12)  # 120ms max probe
    try:
        host = getattr(Config, 'PG_HOST', '127.0.0.1')
        if host in ('localhost', '::1'):
            host = '127.0.0.1'
        port = int(getattr(Config, 'PG_PORT', 5432))
        s.connect((host, port))
        s.close()
        _PG_AVAILABLE = True
    except Exception:
        _PG_AVAILABLE = False
    _PG_LAST_PROBE = now
    return _PG_AVAILABLE


def _create_raw_connection():
    global _ACTIVE_DB_TYPE, _PG_AVAILABLE, _PG_LAST_PROBE
    if is_postgres_alive():
        try:
            db_url = Config.DATABASE_URL
            if 'localhost' in db_url:
                db_url = db_url.replace('localhost', '127.0.0.1')
            conn = psycopg2.connect(
                db_url,
                cursor_factory=RealDictCursor,
                connect_timeout=1
            )
            if _ACTIVE_DB_TYPE != 'postgres':
                _ACTIVE_DB_TYPE = 'postgres'
                print(f"[DATABASE] Terhubung ke server PostgreSQL ({db_url}).")
            return DBConnectionWrapper(conn, is_postgres=True)
        except Exception as e:
            _PG_AVAILABLE = False
            _PG_LAST_PROBE = time.time()
            if _ACTIVE_DB_TYPE != 'sqlite':
                _ACTIVE_DB_TYPE = 'sqlite'
                print(f"[DATABASE NOTICE] Server PostgreSQL tidak terjangkau ({e}). Menggunakan mode fallback SQLite lokal.")

    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    return DBConnectionWrapper(conn, is_postgres=False)


def get_db():
    """
    Returns an active database connection.
    In Flask web requests, reuses connection on flask.g for maximum performance (0ms overhead).
    Outside Flask (scripts/CLI), returns an active connection.
    """
    try:
        from flask import g, has_request_context
        if has_request_context():
            if not hasattr(g, '_db_conn') or g._db_conn is None:
                g._db_conn = _create_raw_connection()
            return g._db_conn
    except Exception:
        pass
    return _create_raw_connection()


# ==============================================================================
# Database Schema Initialization & Seeding
# ==============================================================================

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    if conn.is_postgres:
        # PostgreSQL DDL
        cursor.execute('''
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
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS packages (
            id SERIAL PRIMARY KEY,
            category VARCHAR(20) NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            duration_minutes INTEGER DEFAULT 60,
            price INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_slots (
            id SERIAL PRIMARY KEY,
            time_slot VARCHAR(20) UNIQUE NOT NULL,
            label VARCHAR(100) NOT NULL,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id SERIAL PRIMARY KEY,
            booking_code VARCHAR(100) UNIQUE NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            package_id INTEGER NOT NULL REFERENCES packages(id),
            vehicle_type VARCHAR(20) NOT NULL,
            vehicle_model VARCHAR(255) NOT NULL,
            license_plate VARCHAR(50) NOT NULL,
            booking_date VARCHAR(20) NOT NULL,
            booking_time VARCHAR(20) NOT NULL,
            customer_address TEXT NOT NULL,
            customer_notes TEXT,
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            total_price INTEGER NOT NULL,
            payment_method VARCHAR(50) DEFAULT 'Tunai',
            payment_status VARCHAR(50) DEFAULT 'Belum Bayar',
            status VARCHAR(50) DEFAULT 'pending',
            admin_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocked_slots (
            id SERIAL PRIMARY KEY,
            date VARCHAR(20) NOT NULL,
            time_slot VARCHAR(20) NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, time_slot)
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_vehicles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            vehicle_type VARCHAR(20) NOT NULL,
            vehicle_model VARCHAR(255) NOT NULL,
            license_plate VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, license_plate)
        );
        ''')

        cursor.execute('''
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
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key VARCHAR(100) PRIMARY KEY,
            value TEXT
        );
        ''')

    else:
        # SQLite DDL
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            is_verified INTEGER DEFAULT 0,
            verification_token TEXT,
            verification_code TEXT,
            profile_photo TEXT,
            reset_token TEXT,
            reset_token_expires TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            duration_minutes INTEGER DEFAULT 60,
            price INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time_slot TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_code TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            package_id INTEGER NOT NULL,
            vehicle_type TEXT NOT NULL,
            vehicle_model TEXT NOT NULL,
            license_plate TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            booking_time TEXT NOT NULL,
            customer_address TEXT NOT NULL,
            customer_notes TEXT,
            latitude REAL,
            longitude REAL,
            total_price INTEGER NOT NULL,
            payment_method TEXT DEFAULT 'Tunai',
            payment_status TEXT DEFAULT 'Belum Bayar',
            status TEXT DEFAULT 'pending',
            admin_notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(package_id) REFERENCES packages(id)
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocked_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            reason TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, time_slot)
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vehicle_type TEXT NOT NULL,
            vehicle_model TEXT NOT NULL,
            license_plate TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            UNIQUE(user_id, license_plate)
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            address TEXT NOT NULL,
            notes TEXT,
            latitude REAL,
            longitude REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        ''')

        # Check existing table columns for SQLite upgrade
        cursor.execute("PRAGMA table_info(bookings);")
        existing_cols = [row['name'] for row in cursor.fetchall()]
        if 'latitude' not in existing_cols:
            cursor.execute("ALTER TABLE bookings ADD COLUMN latitude REAL;")
        if 'longitude' not in existing_cols:
            cursor.execute("ALTER TABLE bookings ADD COLUMN longitude REAL;")

        cursor.execute("PRAGMA table_info(users);")
        user_cols = [row['name'] for row in cursor.fetchall()]
        if 'profile_photo' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN profile_photo TEXT;")
        if 'reset_token' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN reset_token TEXT;")
        if 'reset_token_expires' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN reset_token_expires TEXT;")

    conn.commit()
    seed_initial_data(cursor, conn)
    conn.close()


def seed_initial_data(cursor, conn):
    # 1. Admin User
    cursor.execute("SELECT id FROM users WHERE email = %s", ('admin@autokilap.com',))
    if not cursor.fetchone():
        admin_pw = generate_password_hash('admin123')
        cursor.execute('''
        INSERT INTO users (name, email, phone, password_hash, role, is_verified)
        VALUES (%s, %s, %s, %s, 'admin', 1)
        ''', ('Administrator AutoKilap', 'admin@autokilap.com', '081298765432', admin_pw))

    # 2. Customer User
    cursor.execute("SELECT id FROM users WHERE email = %s", ('customer@example.com',))
    if not cursor.fetchone():
        cust_pw = generate_password_hash('user123')
        cursor.execute('''
        INSERT INTO users (name, email, phone, password_hash, role, is_verified)
        VALUES (%s, %s, %s, %s, 'user', 1)
        ''', ('Budi Santoso', 'customer@example.com', '081234567890', cust_pw))

    # 3. Standard Time Slots
    cursor.execute("SELECT COUNT(*) as count FROM time_slots")
    row_count = cursor.fetchone()
    count_val = row_count['count'] if isinstance(row_count, dict) else row_count[0]
    if count_val == 0:
        slots = [
            ("08:00", "08:00 - 09:30 WIB", 1),
            ("09:30", "09:30 - 11:00 WIB", 2),
            ("11:00", "11:00 - 12:30 WIB", 3),
            ("13:00", "13:00 - 14:30 WIB", 4),
            ("14:30", "14:30 - 16:00 WIB", 5),
            ("16:00", "16:00 - 17:30 WIB", 6),
            ("17:30", "17:30 - 19:00 WIB", 7),
        ]
        cursor.executemany("INSERT INTO time_slots (time_slot, label, sort_order) VALUES (%s, %s, %s)", slots)

    # 4. Standard Wash Packages
    cursor.execute("SELECT COUNT(*) as count FROM packages")
    row_pkg = cursor.fetchone()
    pkg_count = row_pkg['count'] if isinstance(row_pkg, dict) else row_pkg[0]
    if pkg_count == 0:
        packages = [
            # Mobil
            ('mobil', 'Cuci Salju Reguler', 'Cuci bodi eksterior sabun salju pH balance, cuci velg, semir ban kilap, lap microfiber anti baret.', 45, 50000),
            ('mobil', 'Cuci Komplit + Vacuum', 'Cuci bodi luar salju, vacuum menyeluruh debu jok & karpet, pembersihan dashboard, semir ban, dan bonus pengharum mobil fresh.', 60, 75000),
            ('mobil', 'Cuci Detailing + Wax Kilap', 'Paket komplit + pembersihan kerak kaca ringan, aplikasi hydro-wax bodi kilap efek daun talas anti-jamur, semir interior premium.', 90, 135000),
            ('mobil', 'Deep Interior Cleaning', 'Cuci bodi luar + pembersihan noda jok mobil, cuci karpet dasar, plafon, dressing plastik, dan fogging anti kuman/bakteri.', 120, 220000),
            # Motor
            ('motor', 'Cuci Motor Salju', 'Cuci bodi salju, pembersihan velg, kolong spakbor, semir ban kilap, dan pelumasan rantai.', 30, 25000),
            ('motor', 'Cuci Komplit + Poles Wax', 'Cuci bodi salju, pembersihan mesin/kolong menyeluruh, poles wax bodi cat kilap, dressing bodi plastik hitam.', 45, 45000),
            ('motor', 'Detailing Motor Gede (Moge / 250cc+)', 'Cuci detail khusus motor besar, pembersihan kerak knalpot/mesin, chain lube, poles wax cat, peremajaan bodi kasar.', 60, 80000)
        ]
        cursor.executemany('''
        INSERT INTO packages (category, name, description, duration_minutes, price)
        VALUES (%s, %s, %s, %s, %s)
        ''', packages)

    # 5. Default System Settings
    default_settings = [
        ('demo_mode', '1'),
        ('admin_phone', '081298765432'),
        ('admin_address', 'Jl. AutoKilap Raya No. 1, Jakarta Selatan'),
        ('privacy_policy', '''<h3>Kebijakan Privasi AutoKilap</h3>
<p>Selamat datang di <strong>AutoKilap</strong>. Kami berkomitmen untuk melindungi dan menghormati privasi data pribadi Anda saat menggunakan layanan cuci mobil dan motor panggilan kami.</p>

<h4>1. Data yang Kami Kumpulkan</h4>
<p>Kami mengumpulkan informasi yang Anda berikan saat mendaftar akun dan melakukan booking layanan cuci, antara lain:</p>
<ul>
  <li>Nama lengkap dan alamat email.</li>
  <li>Nomor telepon / WhatsApp aktif untuk konfirmasi jadwal.</li>
  <li>Data kendaraan (jenis, model, dan nomor plat polisi).</li>
  <li>Alamat lengkap lokasi pencucian dan titik koordinat peta (GPS).</li>
</ul>

<h4>2. Tujuan Penggunaan Data</h4>
<p>Informasi yang terkumpul digunakan semata-mata untuk:</p>
<ul>
  <li>Menghubungi Anda via WhatsApp guna konfirmasi jadwal dan kedatangan tim pencuci.</li>
  <li>Membantu navigasi tim lapangan menuju lokasi Anda secara akurat melalui Google Maps.</li>
  <li>Pencatatan riwayat transaksi dan pelaporan keuangan internal admin.</li>
</ul>

<h4>3. Keamanan Informasi</h4>
<p>Data lokasi dan kontak Anda disimpan secara aman dan tidak akan diperjualbelikan atau disebarluaskan kepada pihak ketiga yang tidak berkepentingan.</p>''')
    ]
    for key, val in default_settings:
        cursor.execute("SELECT key FROM settings WHERE key = %s", (key,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO settings (key, value) VALUES (%s, %s)", (key, val))

    conn.commit()


# ==============================================================================
# Helper Query Functions
# ==============================================================================

def get_setting(key, default=None):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = %s", (key,)).fetchone()
    conn.close()
    if row and row.get('value') is not None:
        return row['value']
    return default

def get_all_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}

def update_settings(settings_dict):
    conn = get_db()
    for key, val in settings_dict.items():
        v = str(val) if val is not None else ''
        if conn.is_postgres:
            conn.execute('''
                INSERT INTO settings (key, value) VALUES (%s, %s)
                ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value
            ''', (key, v))
        else:
            conn.execute('''
                INSERT INTO settings (key, value) VALUES (%s, %s)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            ''', (key, v))
    conn.commit()
    conn.close()

def get_user_by_email(email):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(%s)", (email.strip(),)).fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()
    conn.close()
    return user

def get_packages(category=None, active_only=True):
    conn = get_db()
    query = "SELECT * FROM packages WHERE 1=1"
    params = []
    if category:
        query += " AND category = %s"
        params.append(category)
    if active_only:
        query += " AND is_active = 1"
    query += " ORDER BY category ASC, price ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows

def get_all_time_slots():
    conn = get_db()
    slots = conn.execute("SELECT * FROM time_slots WHERE is_active = 1 ORDER BY sort_order ASC").fetchall()
    conn.close()
    return slots

def get_slot_availability(date_str):
    """
    Returns slot availability for given date YYYY-MM-DD.
    Confirmed or in_progress bookings lock the slot from other customers.
    """
    conn = get_db()
    locked_bookings = conn.execute('''
        SELECT booking_time, status, booking_code, vehicle_model 
        FROM bookings 
        WHERE booking_date = %s AND status IN ('confirmed', 'in_progress')
    ''', (date_str,)).fetchall()

    pending_bookings = conn.execute('''
        SELECT booking_time, booking_code 
        FROM bookings 
        WHERE booking_date = %s AND status = 'pending'
    ''', (date_str,)).fetchall()

    blocked = conn.execute("SELECT time_slot, reason FROM blocked_slots WHERE date = %s", (date_str,)).fetchall()
    conn.close()

    locked_slots = {row['booking_time']: {'status': row['status'], 'code': row['booking_code']} for row in locked_bookings}
    pending_slots = {row['booking_time']: {'status': 'pending', 'code': row['booking_code']} for row in pending_bookings}
    blocked_dict = {row['time_slot']: {'reason': row['reason']} for row in blocked}

    return {
        'locked': locked_slots,
        'pending': pending_slots,
        'blocked': blocked_dict
    }

def get_admin_phone():
    setting_phone = get_setting('admin_phone')
    if setting_phone:
        return setting_phone
    conn = get_db()
    row = conn.execute("SELECT phone FROM users WHERE role = 'admin' AND phone IS NOT NULL ORDER BY id ASC LIMIT 1").fetchone()
    conn.close()
    if row and row.get('phone'):
        return row['phone']
    return Config.ADMIN_WHATSAPP

def get_user_addresses(user_id):
    conn = get_db()
    addresses = conn.execute('''
        SELECT id, label, address, notes, latitude, longitude 
        FROM user_addresses 
        WHERE user_id = %s 
        ORDER BY id DESC
    ''', (user_id,)).fetchall()
    conn.close()
    return addresses

def add_user_address(user_id, label, address, notes=None, latitude=None, longitude=None):
    lbl = (label or 'Alamat Utama').strip()
    addr = (address or '').strip()
    if not addr:
        return None

    lat = None
    lng = None
    try:
        if latitude not in (None, '', 'None'):
            lat = float(latitude)
        if longitude not in (None, '', 'None'):
            lng = float(longitude)
    except (ValueError, TypeError):
        lat = None
        lng = None

    conn = get_db()
    cur = conn.execute('''
        INSERT INTO user_addresses (user_id, label, address, notes, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (user_id, lbl, addr, (notes or '').strip(), lat, lng))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {
        'id': new_id,
        'user_id': user_id,
        'label': lbl,
        'address': addr,
        'notes': notes or '',
        'latitude': lat,
        'longitude': lng
    }

def get_user_vehicles(user_id):
    conn = get_db()
    vehicles = conn.execute('''
        SELECT id, vehicle_type, vehicle_model, license_plate 
        FROM user_vehicles 
        WHERE user_id = %s 
        ORDER BY id DESC
    ''', (user_id,)).fetchall()
    conn.close()
    return vehicles

def add_user_vehicle(user_id, vehicle_type, vehicle_model, license_plate):
    v_model = vehicle_model.strip()
    v_plate = license_plate.strip().upper()
    v_type = vehicle_type.strip().lower()
    if not v_model or not v_plate:
        return None

    conn = get_db()
    try:
        if conn.is_postgres:
            cur = conn.execute('''
                INSERT INTO user_vehicles (user_id, vehicle_type, vehicle_model, license_plate)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(user_id, license_plate) DO UPDATE SET
                    vehicle_type = EXCLUDED.vehicle_type,
                    vehicle_model = EXCLUDED.vehicle_model
            ''', (user_id, v_type, v_model, v_plate))
        else:
            cur = conn.execute('''
                INSERT INTO user_vehicles (user_id, vehicle_type, vehicle_model, license_plate)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(user_id, license_plate) DO UPDATE SET
                    vehicle_type = excluded.vehicle_type,
                    vehicle_model = excluded.vehicle_model
            ''', (user_id, v_type, v_model, v_plate))
        conn.commit()
        vehicle_id = cur.lastrowid
        conn.close()
        return {
            'id': vehicle_id,
            'user_id': user_id,
            'vehicle_type': v_type,
            'vehicle_model': v_model,
            'license_plate': v_plate
        }
    except Exception as e:
        conn.close()
        print(f"Error adding vehicle: {e}")
        return None

def get_financial_report(start_date=None, end_date=None, category=None):
    conn = get_db()
    base_where = "1=1"
    params = []

    if start_date:
        base_where += " AND b.booking_date >= %s"
        params.append(start_date)
    if end_date:
        base_where += " AND b.booking_date <= %s"
        params.append(end_date)
    if category and category != 'all':
        base_where += " AND b.vehicle_type = %s"
        params.append(category)

    query_completed = f'''
        SELECT COALESCE(SUM(b.total_price), 0) as total_rev, COUNT(b.id) as total_count
        FROM bookings b
        WHERE {base_where} AND (b.status = 'completed' OR b.payment_status = 'Lunas')
    '''
    completed_stat = conn.execute(query_completed, params).fetchone()

    query_potential = f'''
        SELECT COALESCE(SUM(b.total_price), 0) as total_rev, COUNT(b.id) as total_count
        FROM bookings b
        WHERE {base_where} AND b.status IN ('pending', 'confirmed', 'in_progress')
    '''
    potential_stat = conn.execute(query_potential, params).fetchone()

    query_all = f'''
        SELECT COALESCE(SUM(b.total_price), 0) as total_rev, COUNT(b.id) as total_count
        FROM bookings b
        WHERE {base_where}
    '''
    all_stat = conn.execute(query_all, params).fetchone()

    query_cancelled = f'''
        SELECT COALESCE(SUM(b.total_price), 0) as total_rev, COUNT(b.id) as total_count
        FROM bookings b
        WHERE {base_where} AND b.status = 'cancelled'
    '''
    cancelled_stat = conn.execute(query_cancelled, params).fetchone()

    query_pkg_breakdown = f'''
        SELECT p.name as package_name, p.category, 
               COUNT(b.id) as order_count,
               COALESCE(SUM(b.total_price), 0) as total_revenue,
               SUM(CASE WHEN b.status = 'completed' OR b.payment_status = 'Lunas' THEN b.total_price ELSE 0 END) as realized_revenue
        FROM bookings b
        JOIN packages p ON b.package_id = p.id
        WHERE {base_where}
        GROUP BY p.id, p.name, p.category
        ORDER BY total_revenue DESC
    '''
    package_breakdown = conn.execute(query_pkg_breakdown, params).fetchall()

    query_ledger = f'''
        SELECT b.*, p.name as package_name, u.name as customer_name, u.phone as customer_phone
        FROM bookings b
        JOIN packages p ON b.package_id = p.id
        JOIN users u ON b.user_id = u.id
        WHERE {base_where}
        ORDER BY b.booking_date DESC, b.booking_time DESC, b.id DESC
    '''
    ledger = conn.execute(query_ledger, params).fetchall()
    conn.close()

    total_realized = completed_stat['total_rev'] or 0
    total_orders = all_stat['total_count'] or 0
    aov = (total_realized / completed_stat['total_count']) if completed_stat['total_count'] > 0 else 0

    return {
        'summary': {
            'realized_revenue': total_realized,
            'realized_count': completed_stat['total_count'] or 0,
            'potential_revenue': potential_stat['total_rev'] or 0,
            'potential_count': potential_stat['total_count'] or 0,
            'gross_revenue': all_stat['total_rev'] or 0,
            'total_orders': total_orders,
            'cancelled_revenue': cancelled_stat['total_rev'] or 0,
            'cancelled_count': cancelled_stat['total_count'] or 0,
            'average_order_value': int(aov)
        },
        'packages': [dict(r) for r in package_breakdown],
        'ledger': [dict(r) for r in ledger]
    }

# ==============================================================================
# User Profile, Password Reset & Active Orders Helpers
# ==============================================================================

def update_user_profile(user_id, name, phone, profile_photo=None):
    """Update user's name, phone, and optional profile photo. Email remains strictly unmodifiable."""
    conn = get_db()
    if profile_photo is not None:
        if profile_photo == '':
            conn.execute("UPDATE users SET name = %s, phone = %s, profile_photo = NULL WHERE id = %s", (name, phone, user_id))
        else:
            conn.execute("UPDATE users SET name = %s, phone = %s, profile_photo = %s WHERE id = %s", (name, phone, profile_photo, user_id))
    else:
        conn.execute("UPDATE users SET name = %s, phone = %s WHERE id = %s", (name, phone, user_id))
    conn.commit()
    conn.close()
    return True

def update_user_password(user_id, password_hash):
    conn = get_db()
    conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))
    conn.commit()
    conn.close()
    return True

def set_password_reset_token(email, token, expires_iso):
    conn = get_db()
    user = conn.execute("SELECT id, name, email FROM users WHERE LOWER(email) = LOWER(%s)", (email.strip(),)).fetchone()
    if not user:
        conn.close()
        return None
    conn.execute(
        "UPDATE users SET reset_token = %s, reset_token_expires = %s WHERE id = %s",
        (token, expires_iso, user['id'])
    )
    conn.commit()
    conn.close()
    return user

def get_user_by_reset_token(token):
    if not token:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE reset_token = %s", (token.strip(),)).fetchone()
    conn.close()
    return user

def clear_password_reset_token(user_id):
    conn = get_db()
    conn.execute("UPDATE users SET reset_token = NULL, reset_token_expires = NULL WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    return True

def get_all_users_with_stats(search=None, role=None, verified=None):
    conn = get_db()
    base_query = '''
        SELECT 
            u.id, u.name, u.email, u.phone, u.role, u.is_verified, 
            u.profile_photo, u.created_at,
            COUNT(b.id) as total_bookings,
            COALESCE(SUM(CASE WHEN b.status = 'completed' OR b.payment_status = 'Lunas' THEN b.total_price ELSE 0 END), 0) as total_spent,
            MAX(b.booking_date) as last_booking_date
        FROM users u
        LEFT JOIN bookings b ON u.id = b.user_id
        WHERE 1=1
    '''
    params = []

    if search:
        search_term = f"%{search.strip()}%"
        base_query += " AND (u.name LIKE %s OR u.email LIKE %s OR u.phone LIKE %s)"
        params.extend([search_term, search_term, search_term])

    if role and role != 'all':
        base_query += " AND u.role = %s"
        params.append(role)

    if verified is not None and verified != 'all':
        base_query += " AND u.is_verified = %s"
        params.append(int(verified))

    base_query += '''
        GROUP BY u.id, u.name, u.email, u.phone, u.role, u.is_verified, u.profile_photo, u.created_at
        ORDER BY u.id DESC
    '''
    users = conn.execute(base_query, params).fetchall()
    conn.close()
    return [dict(u) for u in users]

def update_user_role(user_id, new_role):
    if new_role not in ['user', 'admin']:
        return False
    conn = get_db()
    conn.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
    conn.commit()
    conn.close()
    return True

def toggle_user_verification(user_id, is_verified):
    conn = get_db()
    conn.execute("UPDATE users SET is_verified = %s WHERE id = %s", (1 if is_verified else 0, user_id))
    conn.commit()
    conn.close()
    return True

def get_user_transactions(user_id, status_filter=None):
    conn = get_db()
    query = '''
        SELECT b.*, p.name as package_name, p.category, p.duration_minutes
        FROM bookings b
        JOIN packages p ON b.package_id = p.id
        WHERE b.user_id = %s
    '''
    params = [user_id]
    if status_filter and status_filter != 'all':
        query += " AND b.status = %s"
        params.append(status_filter)
    query += " ORDER BY b.id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_active_orders(user_id):
    """
    Get all active orders for a customer (pending, confirmed, in_progress).
    Returns list of dicts with formatted status badge, icon, and human-friendly description.
    """
    conn = get_db()
    query = '''
        SELECT b.*, p.name as package_name, p.category as package_category, p.duration_minutes
        FROM bookings b
        JOIN packages p ON b.package_id = p.id
        WHERE b.user_id = %s AND b.status IN ('pending', 'confirmed', 'in_progress')
        ORDER BY b.id DESC
    '''
    rows = conn.execute(query, (user_id,)).fetchall()
    conn.close()

    active_orders = []
    for r in rows:
        order = dict(r)
        status = order.get('status', 'pending')
        if status == 'pending':
            order['status_label'] = 'Menunggu Konfirmasi Admin'
            order['status_color'] = 'amber'
            order['status_icon'] = '⏳'
            order['status_bg'] = 'bg-amber-500'
            order['status_border'] = 'border-amber-300'
            order['status_desc'] = 'Admin kami sedang mengecek slot jadwal Anda dan akan segera menghubungi via WhatsApp.'
        elif status == 'confirmed':
            order['status_label'] = 'Jadwal Dikonfirmasi'
            order['status_color'] = 'sky'
            order['status_icon'] = '✓'
            order['status_bg'] = 'bg-sky-500'
            order['status_border'] = 'border-sky-300'
            order['status_desc'] = 'Slot jadwal telah dikonfirmasi dan dikunci. Tim pencuci kami akan datang tepat waktu ke lokasi Anda.'
        elif status == 'in_progress':
            order['status_label'] = 'Sedang Dicuci Tim'
            order['status_color'] = 'emerald'
            order['status_icon'] = '🔄'
            order['status_bg'] = 'bg-emerald-500'
            order['status_border'] = 'border-emerald-400'
            order['status_desc'] = 'Tim teknisi saat ini sedang melakukan proses pencucian dan perawatan kendaraan Anda.'
        else:
            order['status_label'] = status
            order['status_color'] = 'slate'
            order['status_icon'] = 'ℹ️'
            order['status_bg'] = 'bg-slate-500'
            order['status_border'] = 'border-slate-300'
            order['status_desc'] = ''

        active_orders.append(order)

    return active_orders


if __name__ == '__main__':
    init_db()
    print("Database AutoKilap successfully initialized!")
