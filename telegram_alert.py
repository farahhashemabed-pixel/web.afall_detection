import requests
import json
import os

SETTINGS_FILE = "telegram_settings.json"

def load_telegram_settings():
    """تحميل إعدادات تيليغرام من الملف"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"bot_token": "", "chat_id": ""}

def save_telegram_settings(bot_token, chat_id):
    """حفظ إعدادات تيليغرام في الملف"""
    data = {"bot_token": bot_token, "chat_id": chat_id}
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def send_telegram_alert(posture, confidence, image_path=None, bot_token=None, chat_id=None):
    """Send a Telegram alert with optional image, requiring explicit bot_token and chat_id.
    Returns (success: bool, message: str)."""
    # Ensure token and chat_id are provided explicitly; do not fallback to global settings.
    if not bot_token or not chat_id:
        print("⚠️ إعدادات تيليغرام غير مكتملة أو غير مقدمة")
        return False, "إعدادات تيليغرام غير مكتملة أو غير مقدمة"
    
    icon = "🚨" if posture == "سقوط" else "⚠️"
    caption = (
        f"{icon} *تنبيه طوارئ - نظام مراقبة كبار السن*\n\n"
        f"📍 *الوضعية المكتشفة:* {posture}\n"
        f"🎯 *درجة الثقة:* {confidence:.1f}%\n\n"
        f"{'🚨 تم اكتشاف *سقوط* محتمل! يرجى التحقق فوراً!' if posture == 'سقوط' else '⚠️ الشخص في وضعية *استلقاء* غير طبيعية!'}\n\n"
        f"⏰ هذا تنبيه تلقائي من نظام ElderCare"
    )

    # Ensure image_path, if provided, is within the uploads directory to prevent cross-user image sending
    if image_path:
        try:
            uploads_dir = os.path.abspath('uploads')
            img_path_abs = os.path.abspath(image_path)
            if not img_path_abs.startswith(uploads_dir + os.sep):
                print("⚠️ محاولة إرسال صورة من مسار غير مسموح به");
                image_path = None
        except Exception:
            image_path = None

    # محاولة إرسال مع صورة أولاً
    if image_path and os.path.exists(image_path):
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            with open(image_path, 'rb') as photo_file:
                response = requests.post(url, data={
                    "chat_id": chat_id,
                    "caption": caption,
                    "parse_mode": "Markdown"
                }, files={"photo": photo_file}, timeout=15)

            if response.status_code == 200:
                print(f"✅ تم إرسال تنبيه تيليغرام مع صورة: {posture}")
                return True, "تم الإرسال مع الصورة بنجاح"
            else:
                print(f"⚠️ فشل إرسال الصورة، سيتم الإرسال كنص فقط: {response.text}")
        except Exception as e:
            print(f"⚠️ خطأ في إرسال الصورة: {e} — سيتم الإرسال كنص")

    # إرسال نص فقط (كبديل إذا فشلت الصورة أو لم تكن موجودة)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": caption,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ تم إرسال تنبيه تيليغرام (نص): {posture}")
            return True, "تم الإرسال بنجاح"
        else:
            err = response.json().get("description", "خطأ غير معروف")
            print(f"❌ فشل إرسال تيليغرام: {err}")
            return False, err
    except Exception as e:
        print(f"❌ خطأ في الاتصال بتيليغرام: {e}")
        return False, str(e)



def test_telegram_connection(bot_token, chat_id):
    """اختبار الاتصال بتيليغرام"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "✅ *نظام ElderCare* - تم الاتصال بنجاح!\nستصلك التنبيهات على هذا الحساب عند اكتشاف أي سقوط أو وضعية خطرة.",
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return True, "تم الاتصال بنجاح! تحقق من تيليغرام"
        else:
            err = response.json().get("description", "خطأ")
            return False, f"فشل: {err}"
    except Exception as e:
        return False, f"خطأ في الاتصال: {str(e)}"
