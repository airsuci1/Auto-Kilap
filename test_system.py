import unittest
import json
from datetime import date, timedelta
from werkzeug.security import generate_password_hash
from app import app
from database import init_db, get_db, get_financial_report


class TestAutoKilapSystem(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        init_db()

    def test_01_pwa_assets(self):
        res = self.client.get('/manifest.json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data['display'], 'standalone')
        self.assertTrue(len(data['icons']) >= 2)
        print("✓ PWA Manifest valid and verified.")

        res_sw = self.client.get('/sw.js')
        self.assertEqual(res_sw.status_code, 200)
        self.assertIn(b'autokilap', res_sw.data)
        print("✓ PWA Service Worker served properly.")

    def test_02_landing_page(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Auto', res.data)
        self.assertIn(b'Kilap', res.data)
        self.assertIn(b'PWA', res.data)
        print("✓ Landing page rendered with packages.")

    def test_03_registration_email_verification_and_login(self):
        # 0. Check guest access to login, register, and protected booking redirect
        res_guest_login = self.client.get('/auth/login')
        self.assertEqual(res_guest_login.status_code, 200)
        self.assertIn(b'Masuk Akun', res_guest_login.data)

        res_guest_reg = self.client.get('/auth/register')
        self.assertEqual(res_guest_reg.status_code, 200)
        self.assertIn(b'Daftar Akun Baru', res_guest_reg.data)

        res_guest_booking = self.client.get('/booking/new')
        self.assertEqual(res_guest_booking.status_code, 302)
        self.assertIn('/auth/login', res_guest_booking.headers['Location'])

        # Check stale/invalid session handling: should clear session and allow login page access
        with self.client.session_transaction() as sess:
            sess['user_id'] = 9999999  # Non-existent user id in DB
        res_stale_login = self.client.get('/auth/login')
        self.assertEqual(res_stale_login.status_code, 200)
        self.assertIn(b'Masuk Akun', res_stale_login.data)

        import uuid
        test_email = f"test_{uuid.uuid4().hex[:8]}@gmail.com"
        
        # 1. Register
        res_reg = self.client.post('/auth/register', data={
            'name': 'Test Customer Two',
            'email': test_email,
            'phone': '081234567888',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(res_reg.status_code, 200)
        
        # 2. Retrieve verification code from DB
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (test_email,)).fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(user['is_verified'], 0)
        code = user['verification_code']
        conn.close()

        # 3. Verify code
        res_verify = self.client.post('/auth/verify', data={
            'email': test_email,
            'code': code
        }, follow_redirects=True)
        self.assertEqual(res_verify.status_code, 200)

        # 4. Login
        res_login = self.client.post('/auth/login', data={
            'email': test_email,
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(res_login.status_code, 200)
        print("✓ Registration, Email Verification (6-digit code), and Login verified.")

    def test_04_vehicles_api_and_booking_radio(self):
        # 1. Login as customer
        with self.client.session_transaction() as sess:
            conn = get_db()
            cust = conn.execute("SELECT id FROM users WHERE email = 'customer@example.com'").fetchone()
            sess['user_id'] = cust['id']
            sess['user_role'] = 'user'
            sess['user_name'] = 'Budi Santoso'
            conn.close()

        # 2. Add vehicle via AJAX API
        res_add_veh = self.client.post('/api/vehicles/add', json={
            'vehicle_type': 'mobil',
            'vehicle_model': 'Honda HR-V Putih',
            'license_plate': 'B 9999 KILAP'
        })
        self.assertEqual(res_add_veh.status_code, 200)
        veh_data = json.loads(res_add_veh.data)
        self.assertTrue(veh_data['success'])
        self.assertEqual(veh_data['vehicle']['license_plate'], 'B 9999 KILAP')
        print("✓ Vehicle added via inline API successfully.")

        # 3. Check /booking/new renders radio buttons and vehicles dropdown
        res_form = self.client.get('/booking/new')
        self.assertEqual(res_form.status_code, 200)
        self.assertIn(b'package_selection_radio', res_form.data)
        self.assertIn(b'user_vehicle_select', res_form.data)
        self.assertIn(b'B 9999 KILAP', res_form.data)
        print("✓ Booking page contains radio button for packages and user vehicle dropdown.")

    def test_05_whatsapp_customer_greeting_and_admin_confirmation(self):
        test_date = (date.today() + timedelta(days=3)).isoformat()
        test_slot = "11:00"

        # 1. Login as customer
        conn = get_db()
        cust = conn.execute("SELECT id FROM users WHERE email = 'customer@example.com'").fetchone()
        pkg = conn.execute("SELECT id FROM packages WHERE is_active = 1 LIMIT 1").fetchone()
        conn.close()
        pkg_id = pkg['id'] if pkg else 1

        with self.client.session_transaction() as sess:
            sess['user_id'] = cust['id']
            sess['user_role'] = 'user'
            sess['user_name'] = 'Budi Santoso'

        # 2. Create booking
        res_book = self.client.post('/booking/create', data={
            'vehicle_type': 'mobil',
            'package_id': pkg_id,
            'booking_date': test_date,
            'booking_time': test_slot,
            'vehicle_model': 'Toyota Fortuner',
            'license_plate': 'B 5555 JKT',
            'customer_address': 'Jl. Kemang Raya No. 10',
            'customer_notes': 'Kran air ada di samping garasi'
        }, follow_redirects=True)
        self.assertEqual(res_book.status_code, 200)

        # 3. Check Customer Booking Detail page
        conn = get_db()
        booking = conn.execute("SELECT * FROM bookings WHERE booking_date = ? AND booking_time = ?", (test_date, test_slot)).fetchone()
        self.assertIsNotNone(booking)
        booking_id = booking['id']
        admin_row = conn.execute("SELECT phone FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        admin_phone = admin_row['phone']
        conn.close()

        res_detail = self.client.get(f'/booking/{booking_id}')
        self.assertEqual(res_detail.status_code, 200)
        
        # WhatsApp message on customer detail MUST GREET ADMIN (Halo Admin AutoKilap)
        self.assertIn(b'Halo%20Admin%20AutoKilap', res_detail.data)
        self.assertIn(b'Budi%20Santoso', res_detail.data)
        self.assertIn(b'Hubungi Admin via WhatsApp', res_detail.data)
        print("✓ Customer WhatsApp link correctly points to Admin with greeting 'Halo Admin AutoKilap'.")

        # 4. Check Admin Dashboard: Admin WhatsApp button MUST GREET CUSTOMER
        with self.client.session_transaction() as sess:
            conn = get_db()
            admin = conn.execute("SELECT id FROM users WHERE email = 'admin@autokilap.com'").fetchone()
            sess['user_id'] = admin['id']
            sess['user_role'] = 'admin'
            sess['user_name'] = 'Administrator'
            conn.close()

        res_admin = self.client.get('/admin/dashboard')
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b'Halo%20Kak%20Budi%20Santoso', res_admin.data)
        print("✓ Admin WhatsApp link correctly greets Customer 'Halo Kak Budi Santoso'.")

        # 5. Confirm booking
        res_confirm = self.client.post(f'/admin/booking/{booking_id}/status', data={
            'status': 'confirmed'
        }, follow_redirects=True)
        self.assertEqual(res_confirm.status_code, 200)

        # Mark completed to test financial report
        res_complete = self.client.post(f'/admin/booking/{booking_id}/status', data={
            'status': 'completed'
        }, follow_redirects=True)
        self.assertEqual(res_complete.status_code, 200)
        print("✓ Booking marked as completed.")

    def test_06_admin_financial_report(self):
        with self.client.session_transaction() as sess:
            conn = get_db()
            admin = conn.execute("SELECT id FROM users WHERE email = 'admin@autokilap.com'").fetchone()
            sess['user_id'] = admin['id']
            sess['user_role'] = 'admin'
            sess['user_name'] = 'Administrator'
            conn.close()

        res_finance = self.client.get('/admin/finance')
        self.assertEqual(res_finance.status_code, 200)
        self.assertIn(b'Laporan Keuangan', res_finance.data)
        self.assertIn(b'Pendapatan Selesai', res_finance.data)
        self.assertIn(b'Rata-rata Order', res_finance.data)
        self.assertIn(b'Rekap Pendapatan per Paket Cuci', res_finance.data)
        self.assertIn(b'Rincian Buku Kas', res_finance.data)
        print("✓ Admin Financial Report (/admin/finance) verified with revenue metrics, package breakdowns, and order ledger.")

    def test_07_account_settings_and_readonly_email(self):
        # Reset password for customer before testing
        conn = get_db()
        from werkzeug.security import generate_password_hash
        conn.execute("UPDATE users SET password_hash = ? WHERE email = 'customer@example.com'", (generate_password_hash('user123'),))
        conn.commit()
        cust = conn.execute("SELECT * FROM users WHERE email = 'customer@example.com'").fetchone()
        conn.close()

        # 1. Login as customer
        with self.client.session_transaction() as sess:
            sess['user_id'] = cust['id']
            sess['user_role'] = 'user'
            sess['user_name'] = cust['name']
            orig_email = cust['email']


        # 2. Get account page
        res = self.client.get('/account')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Pengaturan Akun', res.data)
        self.assertIn(b'disabled readonly', res.data)
        self.assertIn(b'Email tidak dapat diubah', res.data)

        # 3. Update profile (name & phone)
        res_post = self.client.post('/account', data={
            'action': 'profile',
            'name': 'Budi Santoso Updated',
            'phone': '089988776655',
            'email': 'should_not_change@gmail.com' # Try to maliciously tamper email
        }, follow_redirects=True)
        self.assertEqual(res_post.status_code, 200)

        # 4. Verify in DB: name & phone updated, EMAIL REMAINS UNCHANGED
        conn = get_db()
        updated_cust = conn.execute("SELECT * FROM users WHERE id = ?", (cust['id'],)).fetchone()
        conn.close()
        self.assertEqual(updated_cust['name'], 'Budi Santoso Updated')
        self.assertEqual(updated_cust['phone'], '089988776655')
        self.assertEqual(updated_cust['email'], orig_email)
        print("✓ Account profile settings updated, email remains strictly unchanged (read-only).")

        # 5. Change password via account settings
        res_pwd = self.client.post('/account', data={
            'action': 'password',
            'current_password': 'user123',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }, follow_redirects=True)
        self.assertEqual(res_pwd.status_code, 200)

        # 6. Verify login with new password
        self.client.get('/auth/logout')
        res_login_new = self.client.post('/auth/login', data={
            'email': orig_email,
            'password': 'newpassword123'
        }, follow_redirects=True)
        self.assertEqual(res_login_new.status_code, 200)
        self.assertIn(b'Budi Santoso Updated', res_login_new.data)
        print("✓ Password successfully updated and verified through login.")

    def test_08_riwayat_transaksi(self):
        with self.client.session_transaction() as sess:
            conn = get_db()
            cust = conn.execute("SELECT * FROM users WHERE email = 'customer@example.com'").fetchone()
            sess['user_id'] = cust['id']
            sess['user_role'] = 'user'
            sess['user_name'] = cust['name']
            conn.close()

        # 1. Check /riwayat-transaksi page
        res = self.client.get('/riwayat-transaksi')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Riwayat Transaksi', res.data)
        self.assertIn(b'Total Transaksi', res.data)
        self.assertIn(b'Selesai Dicuci', res.data)
        self.assertIn(b'Dalam Proses', res.data)
        self.assertIn(b'Dibatalkan', res.data)
        self.assertNotIn(b'Total Pengeluaran', res.data)

        # 2. Check /my-bookings redirect alias
        res_alias = self.client.get('/my-bookings')
        self.assertEqual(res_alias.status_code, 302)
        self.assertIn('/riwayat-transaksi', res_alias.headers['Location'])

        # 3. Check /tracking (Status Order) page
        res_track = self.client.get('/tracking')
        self.assertEqual(res_track.status_code, 200)
        self.assertIn(b'Status & Pantau Pesanan', res_track.data)
        print("✓ Riwayat Transaksi page with psychological metrics (Dalam Proses, Selesai, Dibatalkan) verified.")
        print("✓ Tracking / Status Order page (/tracking) verified.")

    def test_09_forgot_password_and_10min_expiry(self):
        import uuid
        from datetime import datetime, timedelta

        # 1. Access forgot-password form
        res_form = self.client.get('/auth/forgot-password')
        self.assertEqual(res_form.status_code, 200)
        self.assertIn(b'Atur Ulang Kata Sandi', res_form.data)

        # 2. Submit request for customer
        res_submit = self.client.post('/auth/forgot-password', data={
            'email': 'customer@example.com'
        }, follow_redirects=True)
        self.assertEqual(res_submit.status_code, 200)
        self.assertIn(b'10 menit', res_submit.data)

        # 3. Check token saved in DB
        conn = get_db()
        cust = conn.execute("SELECT * FROM users WHERE email = 'customer@example.com'").fetchone()
        token = cust['reset_token']
        expires_str = cust['reset_token_expires']
        conn.close()

        self.assertIsNotNone(token)
        self.assertIsNotNone(expires_str)
        expires_dt = datetime.fromisoformat(expires_str)
        self.assertTrue(expires_dt > datetime.now())

        # 4. Open reset page with valid token
        res_reset_page = self.client.get(f'/auth/reset-password?token={token}')
        self.assertEqual(res_reset_page.status_code, 200)
        self.assertIn(b'Buat Kata Sandi Baru', res_reset_page.data)

        # 5. Test EXPIRED token (> 10 minutes)
        # Manually backdate expiration to 1 minute ago
        past_time = (datetime.now() - timedelta(minutes=1)).isoformat()
        conn = get_db()
        conn.execute("UPDATE users SET reset_token_expires = ? WHERE id = ?", (past_time, cust['id']))
        conn.commit()
        conn.close()

        res_expired = self.client.get(f'/auth/reset-password?token={token}', follow_redirects=True)
        self.assertEqual(res_expired.status_code, 200)
        self.assertIn(b'kadaluarsa', res_expired.data)
        print("✓ Password reset 10-minute expiry enforcement verified.")

        # 6. Issue fresh token and successfully reset password
        fresh_token = "fresh_test_token_123"
        fresh_expiry = (datetime.now() + timedelta(minutes=10)).isoformat()
        conn = get_db()
        conn.execute("UPDATE users SET reset_token = ?, reset_token_expires = ? WHERE id = ?", (fresh_token, fresh_expiry, cust['id']))
        conn.commit()
        conn.close()

        res_do_reset = self.client.post('/auth/reset-password', data={
            'token': fresh_token,
            'new_password': 'brandnewpassword999',
            'confirm_password': 'brandnewpassword999'
        }, follow_redirects=True)
        self.assertEqual(res_do_reset.status_code, 200)
        self.assertIn(b'berhasil diperbarui', res_do_reset.data)

        # Check token cleared
        conn = get_db()
        cust_after = conn.execute("SELECT reset_token, reset_token_expires FROM users WHERE id = ?", (cust['id'],)).fetchone()
        # Restore customer password for other test runs
        conn.execute("UPDATE users SET password_hash = ? WHERE email = 'customer@example.com'", (generate_password_hash('user123'),))
        conn.commit()
        conn.close()
        self.assertIsNone(cust_after['reset_token'])
        print("✓ Password reset with valid token succeeds and clears token.")


    def test_10_admin_user_management(self):
        # 1. Login as admin
        with self.client.session_transaction() as sess:
            conn = get_db()
            admin = conn.execute("SELECT * FROM users WHERE email = 'admin@autokilap.com'").fetchone()
            sess['user_id'] = admin['id']
            sess['user_role'] = 'admin'
            sess['user_name'] = admin['name']
            conn.close()

        # 2. Access /admin/users
        res = self.client.get('/admin/users')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Manajemen User & Pelanggan', res.data)
        self.assertIn(b'Total Pengguna', res.data)
        self.assertIn(b'customer@example.com', res.data)
        self.assertIn(b'Chat WA', res.data)

        # 3. Test Toggle Verification
        conn = get_db()
        cust = conn.execute("SELECT id, is_verified FROM users WHERE email = 'customer@example.com'").fetchone()
        cust_id = cust['id']
        current_v = cust['is_verified']
        conn.close()

        res_toggle = self.client.post(f'/admin/user/{cust_id}/toggle-verify', follow_redirects=True)
        self.assertEqual(res_toggle.status_code, 200)

        conn = get_db()
        cust_toggled = conn.execute("SELECT is_verified FROM users WHERE id = ?", (cust_id,)).fetchone()
        conn.close()
        self.assertEqual(cust_toggled['is_verified'], 0 if current_v else 1)

        # Restore verification
        conn = get_db()
        conn.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (cust_id,))
        conn.commit()
        conn.close()

        print("✓ Admin User & Customer Management (/admin/users) verified with stats, WhatsApp links, and actions.")

    def test_11_active_orders_for_customer(self):
        from database import get_user_active_orders
        
        # 1. Login as customer
        with self.client.session_transaction() as sess:
            conn = get_db()
            cust = conn.execute("SELECT * FROM users WHERE email = 'customer@example.com'").fetchone()
            sess['user_id'] = cust['id']
            sess['user_role'] = 'user'
            sess['user_name'] = cust['name']
            cust_id = cust['id']
            conn.close()

        # Clean past pending/confirmed for clear testing
        conn = get_db()
        conn.execute("UPDATE bookings SET status = 'completed' WHERE user_id = %s AND status IN ('pending', 'confirmed', 'in_progress')", (cust_id,))
        conn.commit()
        conn.close()

        # 2. Check landing page before new booking -> No active orders banner
        res_before = self.client.get('/')
        self.assertEqual(res_before.status_code, 200)
        self.assertNotIn(b'Pesanan Aktif Anda', res_before.data)

        # 3. Create a new booking
        conn = get_db()
        pkg = conn.execute("SELECT id FROM packages WHERE is_active = 1 LIMIT 1").fetchone()
        conn.close()
        pkg_id = pkg['id'] if pkg else 1

        test_date = (date.today() + timedelta(days=5)).isoformat()
        res_create = self.client.post('/booking/create', data={
            'vehicle_type': 'mobil',
            'package_id': pkg_id,
            'booking_date': test_date,
            'booking_time': '13:00',
            'vehicle_model': 'Mitsubishi Xpander Cross',
            'license_plate': 'B 7777 ACT',
            'customer_address': 'Jl. Tebet Barat Dalam No. 45',
            'customer_notes': 'Dekat minimarket'
        }, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)

        # 4. Verify helper function returns active order
        active_orders = get_user_active_orders(cust_id)
        self.assertTrue(len(active_orders) >= 1)
        self.assertEqual(active_orders[0]['vehicle_model'], 'Mitsubishi Xpander Cross')
        self.assertEqual(active_orders[0]['status'], 'pending')
        booking_id = active_orders[0]['id']

        # 5. Check landing page displays active order banner
        res_after = self.client.get('/')
        self.assertEqual(res_after.status_code, 200)
        self.assertIn(b'Pesanan Aktif Anda', res_after.data)
        self.assertIn(b'Mitsubishi Xpander Cross', res_after.data)
        self.assertIn(b'B 7777 ACT', res_after.data)
        self.assertIn(b'Menunggu Konfirmasi Admin', res_after.data)
        print("✓ Active order banner on Landing Page & Global Base successfully displayed for logged-in customer.")

        # 6. Admin confirms the booking -> verify status changes to Dikonfirmasi
        conn = get_db()
        conn.execute("UPDATE bookings SET status = 'confirmed' WHERE id = %s", (booking_id,))
        conn.commit()
        conn.close()

        res_confirmed = self.client.get('/')
        self.assertEqual(res_confirmed.status_code, 200)
        self.assertIn(b'Jadwal Dikonfirmasi', res_confirmed.data)
        print("✓ Active order status dynamically updates when confirmed by admin.")

        # 7. Complete the order -> active order banner disappears
        conn = get_db()
        conn.execute("UPDATE bookings SET status = 'completed' WHERE id = %s", (booking_id,))
        conn.commit()
        conn.close()

        res_completed = self.client.get('/')
        self.assertEqual(res_completed.status_code, 200)
        self.assertNotIn(b'Pesanan Aktif Anda', res_completed.data)
        print("✓ Active order banner automatically hides once the order is completed.")

    def test_12_database_wrapper_and_postgres_support(self):
        import os
        from database import get_db, DBCursorWrapper, DBConnectionWrapper
        
        # 1. Verify schema_postgres.sql exists
        self.assertTrue(os.path.exists('schema_postgres.sql'))
        with open('schema_postgres.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()
        self.assertIn('SERIAL PRIMARY KEY', sql_content)
        self.assertIn('CREATE TABLE IF NOT EXISTS users', sql_content)
        self.assertIn('CREATE TABLE IF NOT EXISTS bookings', sql_content)
        self.assertIn('CREATE TABLE IF NOT EXISTS packages', sql_content)
        print("✓ PostgreSQL schema definition (schema_postgres.sql) verified.")

        # 2. Test Connection Wrapper and dual parameter syntax
        conn = get_db()
        self.assertIsInstance(conn, DBConnectionWrapper)

        # Test %s parameter execution
        row = conn.execute("SELECT * FROM users WHERE email = %s", ('customer@example.com',)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['email'], 'customer@example.com')

        # Test ? parameter execution
        row2 = conn.execute("SELECT * FROM users WHERE email = ?", ('customer@example.com',)).fetchone()
        self.assertIsNotNone(row2)
        self.assertEqual(row2['email'], 'customer@example.com')
        conn.close()
        print("✓ Database wrapper with bidirectional parameter normalization (%s & ?) verified.")

if __name__ == '__main__':
    unittest.main()


