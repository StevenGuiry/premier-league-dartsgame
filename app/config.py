import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///darts.db')
    # Render provides postgres:// but SQLAlchemy requires postgresql://
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    START_SCORE = int(os.environ.get('START_SCORE', '501'))
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', '')
