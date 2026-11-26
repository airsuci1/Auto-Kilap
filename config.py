import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'autokilap-pwa-secret-key-2026')
    
    # Database Configuration (PostgreSQL primary)
    DB_TYPE = os.environ.get('DB_TYPE', 'postgres')
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@127.0.0.1:5432/autokilap')
    PG_HOST = os.environ.get('PG_HOST', '127.0.0.1')
    PG_PORT = int(os.environ.get('PG_PORT', 5432))
    PG_DATABASE = os.environ.get('PG_DATABASE', 'autokilap')
    PG_USER = os.environ.get('PG_USER', 'postgres')
    PG_PASSWORD = os.environ.get('PG_PASSWORD', 'postgres')
    
    # Fallback storage if PostgreSQL server is not locally running during development
    DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'autokilap.db')

    
    # Email SMTP configuration (Optional, default uses dev preview simulator)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'no-reply@autokilap.com')
    
    # Admin WhatsApp for contact
    ADMIN_WHATSAPP = os.environ.get('ADMIN_WHATSAPP', '6281234567890')
    APP_NAME = "AutoKilap"
    APP_TAGLINE = "Layanan Cuci Mobil & Motor Panggilan Online Langsung ke Rumah Anda"
    
    # Upload folder for profile avatars
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'avatars')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

