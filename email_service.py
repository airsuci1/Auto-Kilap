import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import random
from config import Config

# Storage for dev-mode verification messages (so tester can view them anytime)
SIMULATED_INBOX = []
SIMULATED_RESETS = []

def generate_verification_code():
    return f"{random.randint(100000, 999999)}"

def generate_verification_token():
    return secrets.token_urlsafe(32)

def send_verification_email(to_email, user_name, code, token, host_url="http://localhost:5000"):
    verify_url = f"{host_url.rstrip('/')}/auth/verify?token={token}&email={to_email}"
    
    subject = f"Kode Verifikasi Pendaftaran {Config.APP_NAME}: {code}"
    
    # HTML Email body
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; }}
            .card {{ max-width: 500px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid #e2e8f0; }}
            .header {{ background: linear-gradient(135deg, #0284c7, #0369a1); color: #ffffff; padding: 32px 24px; text-align: center; }}
            .body {{ padding: 32px 24px; color: #334155; line-height: 1.6; }}
            .code-box {{ background: #f8fafc; border: 2px dashed #0284c7; border-radius: 12px; text-align: center; padding: 20px; margin: 24px 0; }}
            .code {{ font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #0284c7; font-family: monospace; }}
            .btn {{ display: block; width: fit-content; margin: 24px auto; background: #0284c7; color: #ffffff !important; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; }}
            .footer {{ background: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <h1 style="margin: 0; font-size: 24px;">🚗 {Config.APP_NAME}</h1>
                <p style="margin: 8px 0 0 0; opacity: 0.9; font-size: 14px;">Cuci Mobil & Motor Panggilan</p>
            </div>
            <div class="body">
                <p>Halo <strong>{user_name}</strong>,</p>
                <p>Terima kasih telah mendaftar di <strong>{Config.APP_NAME}</strong>! Masukkan kode verifikasi 6-digit berikut untuk mengaktifkan akun Anda:</p>
                
                <div class="code-box">
                    <div style="font-size: 12px; color: #64748b; margin-bottom: 6px; text-transform: uppercase; font-weight: bold;">Kode Verifikasi Anda</div>
                    <div class="code">{code}</div>
                </div>
                
                <p style="text-align: center; margin-top: 16px;">Atau klik tombol di bawah untuk verifikasi otomatis:</p>
                <a href="{verify_url}" class="btn" style="color:#ffffff;">Verifikasi Email Sekarang</a>
                
                <p style="font-size: 13px; color: #64748b; margin-top: 24px;">
                    Jika Anda tidak merasa mendaftar di {Config.APP_NAME}, abaikan email ini.
                </p>
            </div>
            <div class="footer">
                &copy; 2026 {Config.APP_NAME} - Layanan Cuci Kendaraan Panggilan Online
            </div>
        </div>
    </body>
    </html>
    """
    
    # Check if SMTP is configured
    is_sent = False
    error_msg = None
    if Config.MAIL_SERVER and Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = Config.MAIL_DEFAULT_SENDER
            msg['To'] = to_email
            
            part = MIMEText(html_content, 'html')
            msg.attach(part)
            
            if Config.MAIL_PORT == 465:
                server = smtplib.SMTP_SSL(Config.MAIL_SERVER, Config.MAIL_PORT)
            else:
                server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT)
                if Config.MAIL_USE_TLS:
                    server.starttls()
            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.sendmail(Config.MAIL_DEFAULT_SENDER, [to_email], msg.as_string())
            server.quit()
            is_sent = True
        except Exception as e:
            error_msg = str(e)
            print(f"[Email Error] Failed to send email via SMTP: {e}")
            
    # Always keep in simulated inbox for developer preview
    simulation_record = {
        'to': to_email,
        'user_name': user_name,
        'code': code,
        'token': token,
        'verify_url': verify_url,
        'smtp_sent': is_sent,
        'error': error_msg
    }
    SIMULATED_INBOX.insert(0, simulation_record)
    if len(SIMULATED_INBOX) > 20:
        SIMULATED_INBOX.pop()
        
    print(f"[EMAIL VERIFICATION] To: {to_email} | Code: {code} | URL: {verify_url}")
    return simulation_record

def get_latest_simulated_email(email=None):
    if not SIMULATED_INBOX:
        return None
    if not email:
        return SIMULATED_INBOX[0]
    for item in SIMULATED_INBOX:
        if item['to'].lower() == email.lower():
            return item
    return None

def send_password_reset_email(to_email, user_name, token, expires_minutes=10, host_url="http://localhost:5000"):
    reset_url = f"{host_url.rstrip('/')}/auth/reset-password?token={token}"
    subject = f"Atur Ulang Kata Sandi Akun {Config.APP_NAME}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; }}
            .card {{ max-width: 500px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid #e2e8f0; }}
            .header {{ background: linear-gradient(135deg, #0284c7, #0369a1); color: #ffffff; padding: 32px 24px; text-align: center; }}
            .body {{ padding: 32px 24px; color: #334155; line-height: 1.6; }}
            .alert-box {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 10px; padding: 14px; margin: 18px 0; color: #92400e; font-size: 13px; }}
            .btn {{ display: block; width: fit-content; margin: 24px auto; background: #0284c7; color: #ffffff !important; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; text-align: center; }}
            .footer {{ background: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <h1 style="margin: 0; font-size: 24px;">🔑 {Config.APP_NAME}</h1>
                <p style="margin: 8px 0 0 0; opacity: 0.9; font-size: 14px;">Permintaan Atur Ulang Kata Sandi</p>
            </div>
            <div class="body">
                <p>Halo <strong>{user_name}</strong>,</p>
                <p>Kami menerima permintaan untuk mereset kata sandi akun Anda di <strong>{Config.APP_NAME}</strong>.</p>
                
                <div class="alert-box">
                    <strong>⏱️ Batas Waktu Tautan:</strong> Tautan atur ulang kata sandi ini hanya berlaku selama <strong>{expires_minutes} menit</strong> demi keamanan akun Anda.
                </div>
                
                <p style="text-align: center; margin-top: 20px;">Klik tombol di bawah ini untuk membuat kata sandi baru:</p>
                <a href="{reset_url}" class="btn" style="color:#ffffff;">Buat Kata Sandi Baru</a>
                
                <p style="font-size: 12px; color: #64748b; margin-top: 24px; word-break: break-all;">
                    Jika tombol di atas tidak berfungsi, salin dan buka tautan berikut di peramban Anda:<br>
                    <a href="{reset_url}" style="color: #0284c7;">{reset_url}</a>
                </p>
                <p style="font-size: 13px; color: #64748b; margin-top: 20px;">
                    Jika Anda tidak mengajukan permintaan ini, silakan abaikan email ini. Kata sandi akun Anda tidak akan berubah.
                </p>
            </div>
            <div class="footer">
                &copy; 2026 {Config.APP_NAME} - Layanan Cuci Kendaraan Panggilan Online
            </div>
        </div>
    </body>
    </html>
    """
    
    is_sent = False
    error_msg = None
    if Config.MAIL_SERVER and Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = Config.MAIL_DEFAULT_SENDER
            msg['To'] = to_email
            
            part = MIMEText(html_content, 'html')
            msg.attach(part)
            
            if Config.MAIL_PORT == 465:
                server = smtplib.SMTP_SSL(Config.MAIL_SERVER, Config.MAIL_PORT)
            else:
                server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT)
                if Config.MAIL_USE_TLS:
                    server.starttls()
            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.sendmail(Config.MAIL_DEFAULT_SENDER, [to_email], msg.as_string())
            server.quit()
            is_sent = True
        except Exception as e:
            error_msg = str(e)
            print(f"[Email Error] Failed to send reset email via SMTP: {e}")
            
    simulation_record = {
        'to': to_email,
        'user_name': user_name,
        'token': token,
        'reset_url': reset_url,
        'expires_minutes': expires_minutes,
        'smtp_sent': is_sent,
        'error': error_msg
    }
    SIMULATED_RESETS.insert(0, simulation_record)
    if len(SIMULATED_RESETS) > 20:
        SIMULATED_RESETS.pop()
        
    print(f"[PASSWORD RESET] To: {to_email} | Expires: {expires_minutes}m | URL: {reset_url}")
    return simulation_record

def get_latest_simulated_reset(email=None):
    if not SIMULATED_RESETS:
        return None
    if not email:
        return SIMULATED_RESETS[0]
    for item in SIMULATED_RESETS:
        if item['to'].lower() == email.lower():
            return item
    return None

