import os
from datetime import timedelta

class Config:
    """إعدادات التطبيق الأساسية"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'elderly-monitoring-secret-key-2024'
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # نموذج الذكاء الاصطناعي
    MODEL_PATH = 'models/elderly_posture_model.h5'
    LABEL_ENCODER_PATH = 'models/label_encoder.pkl'
    
    # إعدادات التنبيهات
    ALERT_EMAIL = os.environ.get('ALERT_EMAIL') or 'caregiver@example.com'
    ALERT_PHONE = os.environ.get('ALERT_PHONE') or '+966500000000'
    
    # حد ثقة التنبيه
    ALERT_CONFIDENCE_THRESHOLD = 0.7
    
    # معدل التحديث
    UPDATE_INTERVAL = 5  # ثوان

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    DEBUG = True
    TESTING = True

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}