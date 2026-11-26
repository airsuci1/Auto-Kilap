import os
import re
import time
import secrets
import urllib.parse
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, send_from_directory, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from config import Config
from database import (
    get_db, init_db, get_user_by_email, get_user_by_id,
    get_packages, get_all_time_slots, get_slot_availability,
    get_admin_phone, get_user_vehicles, add_user_vehicle,
    get_financial_report, get_setting, get_all_settings,
    update_settings, get_user_addresses, add_user_address,
    update_user_profile, update_user_password, set_password_reset_token,
    get_user_by_reset_token, clear_password_reset_token, get_all_users_with_stats,
    update_user_role, toggle_user_verification, get_user_transactions,
    get_user_active_orders
)

from email_service import (
    generate_verification_code, generate_verification_token,
    send_verification_email, get_latest_simulated_email,
    send_password_reset_email, get_latest_simulated_reset
)


app = Flask(__name__)
app.config.from_object(Config)

# Ensure DB is initialized and uploads directory exists
init_db()
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)


# --- Helpers & Decorators ---

def sanitize_phone_wa(phone):
    """Normalize phone number to international 62 format for WhatsApp API"""
    if not phone:
        return ""
    cleaned = re.sub(r'[^0-9]', '', str(phone))
    if cleaned.startswith('0'):
        cleaned = '62' + cleaned[1:]
    elif cleaned.startswith('8'):
        cleaned = '62' + cleaned
    return cleaned

def generate_admin_to_customer_wa_message(booking, customer_name):
    """Generate message sent by Admin to Customer via WhatsApp"""
    text = (
        f"Halo Kak {customer_name},\n\n"
        f"Kami dari *{Config.APP_NAME}* (Layanan Cuci Mobil & Motor Panggilan). "
        f"Menindaklanjuti pesanan cuci Anda dengan kode *#{booking['booking_code']}*:\n\n"
        f"📌 *Detail Pesanan:*\n"
        f"• Kendaraan: {booking['vehicle_model']} ({booking['license_plate']})\n"
        f"• Paket: {booking['package_name']}\n"
        f"• Jadwal: {booking['booking_date']} pk {booking['booking_time']} WIB\n"
        f"• Alamat: {booking['customer_address']}\n"
        f"• Total Biaya: Rp {booking['total_price']:,} (Bayar Tunai di Tempat)\n\n"
        f"Apakah alamat dan jadwal di atas sudah sesuai untuk kami konfirmasi kedatangan tim? Terima kasih!"
    )
    return urllib.parse.quote(text)

def generate_customer_to_admin_wa_message(booking, customer_name):
    """Generate message sent by Customer to Admin via WhatsApp (Customer greets Admin!)"""
    text = (
        f"Halo Admin {Config.APP_NAME},\n\n"
        f"Saya *{customer_name}*. Saya ingin menanyakan / konfirmasi pesanan cuci panggilan saya:\n\n"
        f"📌 *Detail Pesanan:*\n"
        f"• Kode Booking: *#{booking['booking_code']}*\n"
        f"• Kendaraan: {booking['vehicle_model']} ({booking['license_plate']})\n"
        f"• Paket: {booking['package_name']}\n"
        f"• Jadwal: {booking['booking_date']} pk {booking['booking_time']} WIB\n"
        f"• Alamat: {booking['customer_address']}\n"
        f"• Total Tagihan: Rp {booking['total_price']:,} (Tunai COD)\n\n"
        f"Mohon info dan konfirmasinya ya Admin. Terima kasih!"
    )
    return urllib.parse.quote(text)

@app.context_processor
def inject_global_data():
    user = None
    active_orders = []
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if not user:
            # Stale user_id in session cookie from old DB migration/reset -> clear it!
            session.clear()
        elif user.get('role') != 'admin':
            active_orders = get_user_active_orders(user['id'])
    
    admin_phone = get_admin_phone()
    demo_mode = (get_setting('demo_mode', '1') == '1')
    admin_address = get_setting('admin_address', 'Jl. AutoKilap Raya No. 1, Jakarta Selatan')
    return {
        'current_user': user,
        'active_orders': active_orders,
        'latest_active_order': active_orders[0] if active_orders else None,
        'app_name': Config.APP_NAME,
        'app_tagline': Config.APP_TAGLINE,
        'admin_wa': sanitize_phone_wa(admin_phone),
        'admin_phone': admin_phone,
        'admin_address': admin_address,
        'demo_mode': demo_mode,
        'now_year': datetime.now().year
    }

@app.teardown_appcontext
def teardown_db_connection(exception=None):
    from flask import g
    db = getattr(g, '_db_conn', None)
    if db is not None:
        db.force_close()
        g._db_conn = None


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan masuk ke akun Anda terlebih dahulu untuk melanjutkan.', 'warning')
            next_url = request.full_path.rstrip('?') if request.query_string else request.path
            return redirect(url_for('login', next=next_url))

        user = get_user_by_id(session['user_id'])
        if not user:
            session.clear()
            flash('Sesi akun Anda telah kedaluwarsa. Silakan masuk kembali.', 'warning')
            next_url = request.full_path.rstrip('?') if request.query_string else request.path
            return redirect(url_for('login', next=next_url))

        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Halaman khusus Administrator. Silakan masuk terlebih dahulu.', 'warning')
            return redirect(url_for('login', next=request.path))

        user = get_user_by_id(session['user_id'])
        if not user or user.get('role') != 'admin':
            if not user:
                session.clear()
            flash('Akses ditolak: Akun Anda bukan Administrator.', 'error')
            return redirect(url_for('index'))

        return f(*args, **kwargs)
    return decorated_function


# --- PWA Static Endpoints ---

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def serve_sw():
    response = send_from_directory('static', 'sw.js', mimetype='application/javascript')
    response.headers['Service-Worker-Allowed'] = '/'
    return response


# --- Public / Landing Page ---

@app.route('/')
def index():
    car_packages = get_packages(category='mobil')
    motor_packages = get_packages(category='motor')
    return render_template('index.html', car_packages=car_packages, motor_packages=motor_packages)

@app.route('/privacy-policy')
def privacy_policy():
    """Public Privacy Policy Page"""
    policy_content = get_setting('privacy_policy', '')
    return render_template('privacy.html', policy_content=policy_content)


# --- Authentication & Email Verification ---

@app.route('/auth/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if user:
            return redirect(url_for('index'))
        session.clear()

    next_url = request.form.get('next') or request.args.get('next', '')

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')

        if not name or not email or not phone or not password:
            flash('Semua kolom formulir wajib diisi.', 'error')
            return render_template('auth/register.html', next_url=next_url)

        if len(password) < 6:
            flash('Password minimal harus 6 karakter.', 'error')
            return render_template('auth/register.html', next_url=next_url)

        conn = get_db()
        existing_user = conn.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
        if existing_user:
            conn.close()
            flash('Email ini sudah terdaftar. Silakan gunakan email lain atau langsung masuk.', 'warning')
            return redirect(url_for('login', next=next_url))

        # Generate verification code & token
        code = generate_verification_code()
        token = generate_verification_token()
        hashed_pw = generate_password_hash(password)

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (name, email, phone, password_hash, role, is_verified, verification_code, verification_token)
            VALUES (?, ?, ?, ?, 'user', 0, ?, ?)
        ''', (name, email, phone, hashed_pw, code, token))
        conn.commit()
        conn.close()

        # Send verification email (SMTP or simulator)
        send_verification_email(email, name, code, token, host_url=request.host_url)

        flash('Pendaftaran berhasil! Kode verifikasi telah dikirimkan ke email Anda.', 'success')
        return redirect(url_for('verify', email=email, next=next_url))

    return render_template('auth/register.html', next_url=next_url)


@app.route('/auth/verify', methods=['GET', 'POST'])
def verify():
    email_target = request.args.get('email', '').strip().lower()
    token = request.args.get('token', '').strip()

    # 1-Click Verification via Link Token
    if token and email_target:
        conn = get_db()
        user = conn.execute(
            "SELECT id, is_verified FROM users WHERE LOWER(email) = ? AND verification_token = ?",
            (email_target, token)
        ).fetchone()

        if user:
            conn.execute("UPDATE users SET is_verified = 1, verification_token = NULL, verification_code = NULL WHERE id = ?", (user['id'],))
            conn.commit()
            conn.close()
            flash('Selamat! Email Anda telah berhasil diverifikasi. Silakan masuk.', 'success')
            return redirect(url_for('login'))
        conn.close()
        flash('Tautan verifikasi tidak valid atau telah kadaluarsa.', 'error')

    # Code Form Submission
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        code = request.form.get('code', '').strip()

        if not email or not code:
            flash('Silakan masukkan email dan 6-digit kode verifikasi.', 'error')
            return redirect(url_for('verify', email=email))

        conn = get_db()
        user = conn.execute(
            "SELECT id, is_verified FROM users WHERE LOWER(email) = ? AND verification_code = ?",
            (email, code)
        ).fetchone()

        if user:
            conn.execute("UPDATE users SET is_verified = 1, verification_token = NULL, verification_code = NULL WHERE id = ?", (user['id'],))
            conn.commit()
            conn.close()
            flash('Verifikasi berhasil! Akun Anda kini aktif. Silakan masuk.', 'success')
            return redirect(url_for('login'))
        else:
            conn.close()
            flash('Kode verifikasi salah atau tidak cocok. Silakan coba lagi.', 'error')
            return redirect(url_for('verify', email=email))

    # Dev/Simulator preview check
    sim_email = get_latest_simulated_email(email_target)

    return render_template('auth/verify.html', email_target=email_target, sim_email=sim_email)


@app.route('/auth/resend-code', methods=['POST'])
def resend_code():
    email = request.form.get('email', '').strip().lower()
    if not email:
        flash('Email tidak ditemukan.', 'error')
        return redirect(url_for('verify'))

    conn = get_db()
    user = conn.execute("SELECT id, name, is_verified FROM users WHERE LOWER(email) = ?", (email,)).fetchone()
    if not user:
        conn.close()
        flash('Akun dengan email tersebut tidak ditemukan.', 'error')
        return redirect(url_for('register'))

    if user['is_verified']:
        conn.close()
        flash('Akun sudah terverifikasi sebelumnya. Silakan langsung masuk.', 'info')
        return redirect(url_for('login'))

    new_code = generate_verification_code()
    new_token = generate_verification_token()

    conn.execute(
        "UPDATE users SET verification_code = ?, verification_token = ? WHERE id = ?",
        (new_code, new_token, user['id'])
    )
    conn.commit()
    conn.close()

    send_verification_email(email, user['name'], new_code, new_token, host_url=request.host_url)
    flash('Kode verifikasi baru telah dikirimkan ke email Anda!', 'success')
    return redirect(url_for('verify', email=email))


@app.route('/auth/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if user:
            return redirect(url_for('index'))
        session.clear()

    next_url = request.form.get('next') or request.args.get('next', '')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = get_user_by_email(email)
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Email atau password salah. Silakan coba lagi.', 'error')
            return render_template('auth/login.html', next_url=next_url)

        # Check email verification requirement
        if not user['is_verified']:
            flash('Akun Anda belum diverifikasi. Silakan masukkan kode verifikasi yang telah dikirim ke email.', 'warning')
            return redirect(url_for('verify', email=email, next=next_url))

        # Login success
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_role'] = user['role']

        flash(f'Selamat datang kembali, {user["name"]}!', 'success')

        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        if user['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('my_bookings'))

    return render_template('auth/login.html', next_url=next_url)


@app.route('/auth/logout')
def logout():
    session.clear()
    flash('Anda telah keluar dari akun.', 'info')
    return redirect(url_for('index'))


# --- Password Reset Flow (Expired 10 Menit) ---

@app.route('/auth/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Halaman Permintaan Reset Password dengan pengiriman tautan kadaluarsa 10 menit"""
    if 'user_id' in session:
        return redirect(url_for('account'))

    sim_reset = None
    target_email = request.args.get('email', '').strip().lower()

    if request.method == 'POST':
        target_email = request.form.get('email', '').strip().lower()
        if not target_email:
            flash('Harap masukkan alamat email Anda.', 'error')
            return render_template('auth/forgot_password.html', email=target_email)

        user = get_user_by_email(target_email)
        if not user:
            flash('Alamat email tersebut tidak terdaftar dalam sistem kami.', 'error')
            return render_template('auth/forgot_password.html', email=target_email)

        # Generate secure token with exact 10 minutes expiration
        token = secrets.token_urlsafe(32)
        expires_dt = datetime.now() + timedelta(minutes=10)
        set_password_reset_token(target_email, token, expires_dt.isoformat())

        # Send reset email
        send_password_reset_email(target_email, user['name'], token, expires_minutes=10, host_url=request.host_url)
        flash('Tautan atur ulang kata sandi telah dikirimkan ke email Anda. Tautan berlaku selama 10 menit.', 'success')

    # If demo mode is on and target_email provided, fetch simulated reset for 1-click testing
    demo_mode = (get_setting('demo_mode', '1') == '1')
    if demo_mode and target_email:
        sim_reset = get_latest_simulated_reset(target_email)

    return render_template('auth/forgot_password.html', email=target_email, sim_reset=sim_reset)


@app.route('/auth/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Halaman Buat Password Baru berdasarkan tautan token (validasi batas waktu 10 menit)"""
    token = request.args.get('token', '').strip() or request.form.get('token', '').strip()
    if not token:
        flash('Token atur ulang kata sandi tidak ditemukan atau tidak valid.', 'error')
        return redirect(url_for('forgot_password'))

    user = get_user_by_reset_token(token)
    if not user:
        flash('Tautan atur ulang kata sandi tidak valid atau sudah pernah digunakan.', 'error')
        return redirect(url_for('forgot_password'))

    # Check 10-minute expiration
    expires_str = user['reset_token_expires']
    if not expires_str:
        flash('Tautan atur ulang kata sandi sudah kadaluarsa.', 'error')
        return redirect(url_for('forgot_password'))

    try:
        expires_dt = datetime.fromisoformat(expires_str)
        if datetime.now() > expires_dt:
            clear_password_reset_token(user['id'])
            flash('Tautan atur ulang kata sandi telah kadaluarsa (melewati batas waktu 10 menit). Silakan ajukan tautan baru.', 'error')
            return redirect(url_for('forgot_password'))
    except Exception as e:
        clear_password_reset_token(user['id'])
        flash('Terjadi kesalahan validasi waktu. Silakan ajukan tautan baru.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not new_password or len(new_password) < 6:
            flash('Kata sandi baru minimal harus 6 karakter.', 'error')
            return render_template('auth/reset_password.html', token=token, email=user['email'], user_name=user['name'])

        if new_password != confirm_password:
            flash('Konfirmasi kata sandi tidak cocok. Harap periksa kembali.', 'error')
            return render_template('auth/reset_password.html', token=token, email=user['email'], user_name=user['name'])

        # Update password and clear token
        hashed_pw = generate_password_hash(new_password)
        update_user_password(user['id'], hashed_pw)
        clear_password_reset_token(user['id'])

        flash('Kata sandi Anda berhasil diperbarui! Silakan masuk dengan kata sandi baru Anda.', 'success')
        return redirect(url_for('login'))

    return render_template('auth/reset_password.html', token=token, email=user['email'], user_name=user['name'], expires_at=expires_str)



# --- Booking API & Views ---

@app.route('/api/slots')
def api_slots():
    """API to return operational time slots and lock status for given date"""
    date_str = request.args.get('date', '').strip()
    if not date_str:
        date_str = date.today().isoformat()

    all_slots = get_all_time_slots()
    availability = get_slot_availability(date_str)

    slot_list = [{
        'id': s['id'],
        'time_slot': s['time_slot'],
        'label': s['label']
    } for s in all_slots]

    return jsonify({
        'date': date_str,
        'slots': slot_list,
        'locked': availability['locked'],
        'pending': availability['pending'],
        'blocked': availability['blocked']
    })


@app.route('/api/vehicles/add', methods=['POST'])
@login_required
def api_add_vehicle():
    """API to add a new vehicle for the user without reloading the page"""
    data = request.get_json() if request.is_json else request.form
    v_type = data.get('vehicle_type', 'mobil').strip().lower()
    v_model = data.get('vehicle_model', '').strip()
    v_plate = data.get('license_plate', '').strip().upper()

    if not v_model or not v_plate:
        return jsonify({'success': False, 'message': 'Model kendaraan dan nomor plat wajib diisi.'}), 400

    user_id = session.get('user_id')
    user = get_user_by_id(user_id)
    if not user:
        session.clear()
        return jsonify({'success': False, 'message': 'Sesi Anda telah kedaluwarsa. Silakan masuk kembali.'}), 401

    try:
        saved = add_user_vehicle(user['id'], v_type, v_model, v_plate)
        if saved:
            return jsonify({'success': True, 'vehicle': saved})
        return jsonify({'success': False, 'message': 'Gagal menyimpan data kendaraan. Pastikan format plat dan tipe kendaraan benar.'}), 400
    except Exception as e:
        logger.error(f"Error add_user_vehicle: {e}")
        return jsonify({'success': False, 'message': f'Terjadi kendala saat menyimpan kendaraan: {str(e)}'}), 500


@app.route('/api/addresses/add', methods=['POST'])
@login_required
def api_add_address():
    """API to add a new address for the user with GPS coordinates without reloading the page"""
    data = request.get_json() if request.is_json else request.form
    label = data.get('label', 'Rumah').strip()
    address = data.get('address', '').strip()
    notes = data.get('notes', '').strip()
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if not address:
        return jsonify({'success': False, 'message': 'Alamat lengkap wajib diisi.'}), 400

    user_id = session.get('user_id')
    user = get_user_by_id(user_id)
    if not user:
        session.clear()
        return jsonify({'success': False, 'message': 'Sesi Anda telah kedaluwarsa. Silakan masuk kembali.'}), 401

    try:
        saved = add_user_address(user['id'], label, address, notes, latitude, longitude)
        if saved:
            return jsonify({'success': True, 'address': saved})
        return jsonify({'success': False, 'message': 'Gagal menyimpan data alamat.'}), 400
    except Exception as e:
        logger.error(f"Error add_user_address: {e}")
        return jsonify({'success': False, 'message': f'Terjadi kendala saat menyimpan alamat: {str(e)}'}), 500


@app.route('/booking/new')
@login_required
def booking_new():
    selected_category = request.args.get('category', 'mobil')
    preselected_package_id = request.args.get('package_id', type=int)
    packages = get_packages(active_only=True)
    user_vehicles = get_user_vehicles(session['user_id'])
    user_addresses = get_user_addresses(session['user_id'])
    
    return render_template(
        'booking/new.html',
        packages=packages,
        selected_category=selected_category,
        preselected_package_id=preselected_package_id,
        user_vehicles=[dict(v) for v in user_vehicles],
        user_addresses=[dict(a) for a in user_addresses]
    )


@app.route('/booking/create', methods=['POST'])
@login_required
def booking_create():
    user_id = session['user_id']
    vehicle_type = request.form.get('vehicle_type', 'mobil')
    package_id = request.form.get('package_id', type=int)
    booking_date = request.form.get('booking_date', '').strip()
    booking_time = request.form.get('booking_time', '').strip()
    vehicle_model = request.form.get('vehicle_model', '').strip()
    license_plate = request.form.get('license_plate', '').strip().upper()
    customer_address = request.form.get('customer_address', '').strip()
    customer_notes = request.form.get('customer_notes', '').strip()
    latitude = request.form.get('latitude')
    longitude = request.form.get('longitude')

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

    if not package_id or not booking_date or not booking_time or not vehicle_model or not license_plate or not customer_address:
        flash('Harap lengkapi semua kolom wajib.', 'error')
        return redirect(url_for('booking_new'))

    # Check slot availability: User Requirement: "jadwal yang di konfirmasi tidak dapat lagi dipilih oleh user lain."
    availability = get_slot_availability(booking_date)
    if booking_time in availability['locked']:
        flash('Maaf, jadwal pada tanggal dan jam tersebut baru saja dikonfirmasi atau telah terisi. Silakan pilih jam lain.', 'error')
        return redirect(url_for('booking_new'))

    if booking_time in availability['blocked']:
        flash('Maaf, slot jadwal tersebut sedang tidak beroperasi. Silakan pilih jam lain.', 'error')
        return redirect(url_for('booking_new'))

    conn = get_db()
    package = conn.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()
    if not package:
        conn.close()
        flash('Paket cuci tidak ditemukan.', 'error')
        return redirect(url_for('booking_new'))

    # Automatically save or update user vehicle for future dropdown
    add_user_vehicle(user_id, vehicle_type, vehicle_model, license_plate)

    # Automatically save address to user address book
    add_user_address(user_id, 'Alamat Booking', customer_address, customer_notes, lat, lng)

    # Generate unique booking code
    date_code = datetime.now().strftime('%Y%m%d')
    random_suffix = os.urandom(2).hex().upper()
    booking_code = f"CKM-{date_code}-{random_suffix}"

    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO bookings (
            booking_code, user_id, package_id, vehicle_type, vehicle_model,
            license_plate, booking_date, booking_time, customer_address,
            customer_notes, latitude, longitude, total_price, payment_method, payment_status, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Tunai', 'Belum Bayar', 'pending')
    ''', (
        booking_code, user_id, package_id, vehicle_type, vehicle_model,
        license_plate, booking_date, booking_time, customer_address,
        customer_notes, lat, lng, package['price']
    ))
    booking_id = cursor.lastrowid
    conn.commit()
    conn.close()

    flash('Pesanan booking cuci Anda berhasil dibuat! Admin kami akan menghubungi Anda via WhatsApp untuk konfirmasi jadwal.', 'success')
    return redirect(url_for('booking_detail', booking_id=booking_id))


@app.route('/booking/<int:booking_id>')
@login_required
def booking_detail(booking_id):
    conn = get_db()
    booking = conn.execute('''
        SELECT b.*, p.name as package_name, p.duration_minutes, u.name as customer_name, u.phone as customer_phone
        FROM bookings b
        JOIN packages p ON b.package_id = p.id
        JOIN users u ON b.user_id = u.id
        WHERE b.id = ?
    ''', (booking_id,)).fetchone()
    conn.close()

    if not booking:
        abort(404)

    # Only owner or admin can view
    if booking['user_id'] != session['user_id'] and session.get('user_role') != 'admin':
        abort(403)

    admin_phone = get_admin_phone()
    admin_wa = sanitize_phone_wa(admin_phone)
    # Message sent FROM customer TO admin: Greets Admin, provides customer name & booking details
    customer_wa_text = generate_customer_to_admin_wa_message(booking, booking['customer_name'])

    if booking['latitude'] and booking['longitude']:
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={booking['latitude']},{booking['longitude']}"
    else:
        maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(booking['customer_address'])}"

    return render_template(
        'booking/detail.html',
        booking=booking,
        customer_wa_text=customer_wa_text,
        admin_wa=admin_wa,
        maps_url=maps_url
    )


# --- Client: Riwayat Transaksi & Pengaturan Akun ---

@app.route('/tracking')
@app.route('/status')
@app.route('/pesanan-aktif')
@login_required
def tracking():
    """Halaman Tracking & Pemantauan Status Order Pelanggan Secara Real-Time"""
    user_id = session['user_id']
    active_orders = get_user_active_orders(user_id)

    admin_phone = get_admin_phone()
    user = get_user_by_id(user_id)
    user_name = user['name'] if user else session.get('user_name', 'Pelanggan')

    for order in active_orders:
        wa_text = generate_customer_to_admin_wa_message(order, user_name)
        order['wa_link'] = f"https://wa.me/{sanitize_phone_wa(admin_phone)}?text={wa_text}"
        status = order.get('status', 'pending')
        if status == 'pending':
            order['current_step'] = 1
        elif status == 'confirmed':
            order['current_step'] = 2
        elif status == 'in_progress':
            order['current_step'] = 3
        else:
            order['current_step'] = 4

    return render_template(
        'customer/tracking.html',
        active_orders=active_orders,
        user_name=user_name
    )


@app.route('/riwayat-transaksi')
@login_required
def riwayat_transaksi():
    """Halaman Riwayat Transaksi Pelanggan"""
    user_id = session['user_id']
    status_filter = request.args.get('status', 'all').strip()

    all_tx = get_user_transactions(user_id, status_filter='all')
    filtered_tx = get_user_transactions(user_id, status_filter=status_filter)

    total_orders = len(all_tx)
    in_progress_orders = sum(1 for t in all_tx if t['status'] in ['pending', 'confirmed', 'in_progress'])
    completed_orders = sum(1 for t in all_tx if t['status'] == 'completed')
    cancelled_orders = sum(1 for t in all_tx if t['status'] == 'cancelled')

    stats = {
        'total': total_orders,
        'in_progress': in_progress_orders,
        'completed': completed_orders,
        'cancelled': cancelled_orders
    }

    return render_template(
        'customer/orders.html',
        bookings=filtered_tx,
        stats=stats,
        current_status=status_filter
    )


@app.route('/my-bookings')
@login_required
def my_bookings():
    """Alias navigasi untuk Riwayat Transaksi"""
    return redirect(url_for('riwayat_transaksi'))


@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    """
    Halaman Menu Akun & Pengaturan Akun Pelanggan:
    - Ubah Nama Lengkap
    - Ubah Nomor Telepon / WhatsApp
    - Ubah Foto Profil
    - Ganti Kata Sandi
    - Catatan: Email tidak bisa diubah (readonly)
    """
    user_id = session['user_id']
    user = get_user_by_id(user_id)
    if not user:
        flash('Data pengguna tidak ditemukan.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        action = request.form.get('action', 'profile').strip()

        if action == 'profile':
            name = request.form.get('name', '').strip()
            phone = request.form.get('phone', '').strip()

            if not name or not phone:
                flash('Nama lengkap dan nomor telepon / WhatsApp wajib diisi.', 'error')
                return redirect(url_for('account'))

            # Handle photo profile upload
            photo_path = None
            if 'profile_photo' in request.files:
                file = request.files['profile_photo']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                    if ext in Config.ALLOWED_EXTENSIONS:
                        new_filename = f"avatar_{user_id}_{int(time.time())}.{ext}"
                        save_dest = os.path.join(Config.UPLOAD_FOLDER, new_filename)
                        file.save(save_dest)
                        photo_path = f"/static/uploads/avatars/{new_filename}"
                    else:
                        flash('Format gambar foto profil harus JPG, PNG, WEBP, atau GIF.', 'error')
                        return redirect(url_for('account'))

            # Check if user requested to remove photo
            if request.form.get('remove_photo') == '1':
                photo_path = ''

            # Update profile in database (Note: Email is strictly excluded and cannot be changed!)
            update_user_profile(user_id, name, phone, photo_path)
            session['user_name'] = name
            flash('Profil akun Anda berhasil diperbarui!', 'success')
            return redirect(url_for('account'))

        elif action == 'password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not check_password_hash(user['password_hash'], current_password):
                flash('Kata sandi saat ini tidak sesuai. Harap periksa kembali.', 'error')
                return redirect(url_for('account'))

            if not new_password or len(new_password) < 6:
                flash('Kata sandi baru minimal harus 6 karakter.', 'error')
                return redirect(url_for('account'))

            if new_password != confirm_password:
                flash('Konfirmasi kata sandi baru tidak cocok.', 'error')
                return redirect(url_for('account'))

            hashed_pw = generate_password_hash(new_password)
            update_user_password(user_id, hashed_pw)
            flash('Kata sandi akun Anda berhasil diperbarui!', 'success')
            return redirect(url_for('account'))

    user_vehicles = get_user_vehicles(user_id)
    user_addresses = get_user_addresses(user_id)
    recent_transactions = get_user_transactions(user_id)

    return render_template(
        'customer/account.html',
        user=user,
        user_vehicles=user_vehicles,
        user_addresses=user_addresses,
        total_transactions=len(recent_transactions)
    )



# --- Admin Panel, WhatsApp Management & Financial Report ---

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    status_filter = request.args.get('status', '').strip()
    date_filter = request.args.get('date', '').strip()

    conn = get_db()

    # Query statistics
    total = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM bookings WHERE status = 'pending'").fetchone()[0]
    confirmed = conn.execute("SELECT COUNT(*) FROM bookings WHERE status = 'confirmed'").fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM bookings WHERE status = 'completed'").fetchone()[0]

    stats = {
        'total': total,
        'pending': pending,
        'confirmed': confirmed,
        'completed': completed
    }

    # Query bookings with filters
    query = '''
        SELECT b.*, p.name as package_name, u.name as customer_name, u.phone as customer_phone
        FROM bookings b
        JOIN packages p ON b.package_id = p.id
        JOIN users u ON b.user_id = u.id
        WHERE 1=1
    '''
    params = []
    if status_filter:
        query += " AND b.status = ?"
        params.append(status_filter)
    if date_filter:
        query += " AND b.booking_date = ?"
        params.append(date_filter)

    query += " ORDER BY b.id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    # Prepare formatted data for each booking (sanitized phone, pre-filled WhatsApp text, and Google Maps Navigation link)
    bookings_data = []
    for r in rows:
        item = dict(r)
        item['wa_phone'] = sanitize_phone_wa(item['customer_phone'])
        # Message sent FROM admin TO customer: Greets customer
        item['wa_message'] = generate_admin_to_customer_wa_message(item, item['customer_name'])
        
        # Google Maps Navigation Link for field technician
        if item.get('latitude') and item.get('longitude'):
            item['maps_url'] = f"https://www.google.com/maps/dir/?api=1&destination={item['latitude']},{item['longitude']}"
        else:
            item['maps_url'] = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(item['customer_address'])}"
            
        bookings_data.append(item)

    return render_template(
        'admin/dashboard.html',
        bookings=bookings_data,
        stats=stats,
        current_status=status_filter,
        current_date=date_filter
    )


@app.route('/admin/finance')
@admin_required
def admin_finance():
    """Laporan Keuangan Administrator untuk menghitung orderan yang masuk"""
    period = request.args.get('period', 'all').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    category = request.args.get('category', 'all').strip()

    today = date.today()
    if period == 'today':
        start_date = today.isoformat()
        end_date = today.isoformat()
    elif period == 'this_month':
        start_date = today.replace(day=1).isoformat()
        end_date = today.isoformat()
    elif period == 'this_year':
        start_date = today.replace(month=1, day=1).isoformat()
        end_date = today.isoformat()

    report = get_financial_report(
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None,
        category=category
    )

    return render_template(
        'admin/finance.html',
        summary=report['summary'],
        packages=report['packages'],
        ledger=report['ledger'],
        period=period,
        start_date=start_date,
        end_date=end_date,
        category=category
    )


@app.route('/admin/booking/<int:booking_id>/status', methods=['POST'])
@admin_required
def admin_update_booking_status(booking_id):
    new_status = request.form.get('status', '').strip()
    valid_statuses = ['pending', 'confirmed', 'in_progress', 'completed', 'cancelled']

    if new_status not in valid_statuses:
        flash('Status tidak valid.', 'error')
        return redirect(url_for('admin_dashboard'))

    conn = get_db()
    booking = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if not booking:
        conn.close()
        flash('Pesanan tidak ditemukan.', 'error')
        return redirect(url_for('admin_dashboard'))

    # If changing to confirmed, verify if another booking already locked this slot!
    if new_status == 'confirmed':
        conflict = conn.execute('''
            SELECT booking_code FROM bookings
            WHERE booking_date = ? AND booking_time = ? AND status = 'confirmed' AND id != ?
        ''', (booking['booking_date'], booking['booking_time'], booking_id)).fetchone()

        if conflict:
            conn.close()
            flash(f'Slot tersebut sudah dikunci oleh pesanan #{conflict["booking_code"]}. Tidak dapat mengonfirmasi dua pesanan pada slot yang sama.', 'error')
            return redirect(url_for('admin_dashboard'))

    payment_status = 'Lunas' if new_status == 'completed' else booking['payment_status']

    conn.execute('''
        UPDATE bookings
        SET status = ?, payment_status = ?
        WHERE id = ?
    ''', (new_status, payment_status, booking_id))
    conn.commit()
    conn.close()

    flash(f'Status pesanan #{booking["booking_code"]} berhasil diubah menjadi: {new_status.upper()}.', 'success')
    return redirect(request.referrer or url_for('admin_dashboard'))


# --- Admin: Wash Packages Management ---

@app.route('/admin/packages')
@admin_required
def admin_packages():
    car_packages = get_packages(category='mobil', active_only=False)
    motor_packages = get_packages(category='motor', active_only=False)
    # Convert Row objects to dict for JSON serialization in template
    car_list = [dict(p) for p in car_packages]
    motor_list = [dict(p) for p in motor_packages]
    return render_template('admin/packages.html', car_packages=car_list, motor_packages=motor_list)


@app.route('/admin/package/create', methods=['POST'])
@admin_required
def admin_create_package():
    category = request.form.get('category', 'mobil')
    name = request.form.get('name', '').strip()
    price = request.form.get('price', type=int)
    duration_minutes = request.form.get('duration_minutes', type=int, default=60)
    description = request.form.get('description', '').strip()

    if not name or not price:
        flash('Nama paket dan harga wajib diisi.', 'error')
        return redirect(url_for('admin_packages'))

    conn = get_db()
    conn.execute('''
        INSERT INTO packages (category, name, price, duration_minutes, description, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
    ''', (category, name, price, duration_minutes, description))
    conn.commit()
    conn.close()

    flash(f'Paket cuci "{name}" berhasil ditambahkan!', 'success')
    return redirect(url_for('admin_packages'))


@app.route('/admin/package/<int:package_id>/update', methods=['POST'])
@admin_required
def admin_update_package(package_id):
    category = request.form.get('category', 'mobil')
    name = request.form.get('name', '').strip()
    price = request.form.get('price', type=int)
    duration_minutes = request.form.get('duration_minutes', type=int, default=60)
    description = request.form.get('description', '').strip()

    if not name or not price:
        flash('Nama paket dan harga wajib diisi.', 'error')
        return redirect(url_for('admin_packages'))

    conn = get_db()
    conn.execute('''
        UPDATE packages
        SET category = ?, name = ?, price = ?, duration_minutes = ?, description = ?
        WHERE id = ?
    ''', (category, name, price, duration_minutes, description, package_id))
    conn.commit()
    conn.close()

    flash('Paket cuci berhasil diperbarui!', 'success')
    return redirect(url_for('admin_packages'))


@app.route('/admin/package/<int:package_id>/delete', methods=['POST'])
@admin_required
def admin_delete_package(package_id):
    conn = get_db()
    conn.execute("DELETE FROM packages WHERE id = ?", (package_id,))
    conn.commit()
    conn.close()
    flash('Paket cuci berhasil dihapus.', 'info')
    return redirect(url_for('admin_packages'))


# --- Admin: Schedule & Blocked Slots ---

@app.route('/admin/schedule')
@admin_required
def admin_schedule():
    selected_date = request.args.get('date', '').strip()
    if not selected_date:
        selected_date = date.today().isoformat()

    all_slots = get_all_time_slots()
    availability = get_slot_availability(selected_date)

    return render_template(
        'admin/schedule.html',
        selected_date=selected_date,
        slots=all_slots,
        locked=availability['locked'],
        pending=availability['pending'],
        blocked=availability['blocked']
    )


@app.route('/admin/slot/block', methods=['POST'])
@admin_required
def admin_block_slot():
    date_str = request.form.get('date', '').strip()
    time_slot = request.form.get('time_slot', '').strip()
    reason = request.form.get('reason', 'Ditutup oleh admin').strip()

    if not date_str or not time_slot:
        flash('Parameter tanggal dan slot jam wajib ada.', 'error')
        return redirect(url_for('admin_schedule'))

    conn = get_db()
    try:
        conn.execute('''
            INSERT INTO blocked_slots (date, time_slot, reason)
            VALUES (?, ?, ?)
        ''', (date_str, time_slot, reason))
        conn.commit()
        flash(f'Slot jam {time_slot} pada {date_str} berhasil diblokir.', 'warning')
    except Exception as e:
        flash(f'Slot sudah diblokir sebelumnya.', 'info')
    conn.close()

    return redirect(url_for('admin_schedule', date=date_str))


@app.route('/admin/slot/unblock', methods=['POST'])
@admin_required
def admin_unblock_slot():
    date_str = request.form.get('date', '').strip()
    time_slot = request.form.get('time_slot', '').strip()

    conn = get_db()
    conn.execute('DELETE FROM blocked_slots WHERE date = ? AND time_slot = ?', (date_str, time_slot))
    conn.commit()
    conn.close()

    flash(f'Blokir slot jam {time_slot} pada {date_str} telah dibuka.', 'success')
    return redirect(url_for('admin_schedule', date=date_str))


# --- Admin: System & Business Settings ---

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    """Admin configuration settings: Demo Mode, Admin Phone, Address, Privacy Policy"""
    if request.method == 'POST':
        demo_mode_val = '1' if request.form.get('demo_mode') == 'on' else '0'
        admin_phone_val = request.form.get('admin_phone', '').strip()
        admin_address_val = request.form.get('admin_address', '').strip()
        privacy_policy_val = request.form.get('privacy_policy', '').strip()

        update_settings({
            'demo_mode': demo_mode_val,
            'admin_phone': admin_phone_val,
            'admin_address': admin_address_val,
            'privacy_policy': privacy_policy_val
        })
        flash('Konfigurasi sistem admin berhasil diperbarui!', 'success')
        return redirect(url_for('admin_settings'))

    settings = get_all_settings()
    return render_template('admin/settings.html', settings=settings)


# --- Admin: Manajemen User & Data Pelanggan ---

@app.route('/admin/users')
@admin_required
def admin_users():
    """Manajemen User dan Data Pelanggan oleh Admin"""
    search = request.args.get('search', '').strip()
    role_filter = request.args.get('role', 'all').strip()
    verified_filter = request.args.get('verified', 'all').strip()

    all_users = get_all_users_with_stats()
    filtered_users = get_all_users_with_stats(
        search=search if search else None,
        role=role_filter if role_filter != 'all' else None,
        verified=verified_filter if verified_filter != 'all' else None
    )

    # Attach sanitized WhatsApp phone for 1-click chat
    for u in filtered_users:
        u['wa_phone'] = sanitize_phone_wa(u['phone'])

    stats = {
        'total_users': len(all_users),
        'total_customers': sum(1 for u in all_users if u['role'] == 'user'),
        'total_admins': sum(1 for u in all_users if u['role'] == 'admin'),
        'total_verified': sum(1 for u in all_users if u['is_verified'] == 1)
    }

    return render_template(
        'admin/users.html',
        users=filtered_users,
        stats=stats,
        search=search,
        current_role=role_filter,
        current_verified=verified_filter
    )


@app.route('/admin/user/<int:user_id>/role', methods=['POST'])
@admin_required
def admin_update_user_role(user_id):
    """Admin can change user role between 'user' and 'admin'"""
    new_role = request.form.get('role', 'user').strip()
    if user_id == session['user_id']:
        flash('Anda tidak dapat mengubah role akun admin Anda sendiri demi keamanan.', 'error')
        return redirect(url_for('admin_users'))

    if update_user_role(user_id, new_role):
        flash(f'Role pengguna berhasil diubah menjadi: {new_role.upper()}.', 'success')
    else:
        flash('Gagal mengubah role pengguna.', 'error')
    return redirect(url_for('admin_users'))


@app.route('/admin/user/<int:user_id>/toggle-verify', methods=['POST'])
@admin_required
def admin_toggle_verify(user_id):
    """Admin can manually toggle user verification status"""
    user = get_user_by_id(user_id)
    if not user:
        flash('Pengguna tidak ditemukan.', 'error')
        return redirect(url_for('admin_users'))

    new_val = 0 if user['is_verified'] else 1
    toggle_user_verification(user_id, new_val)
    status_label = "Terverifikasi" if new_val == 1 else "Belum Verifikasi"
    flash(f'Status verifikasi email {user["name"]} berhasil diubah menjadi: {status_label}.', 'success')
    return redirect(url_for('admin_users'))


if __name__ == '__main__':

    port = int(os.environ.get('PORT', 5000))
    print(f"Starting {Config.APP_NAME} PWA server on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
