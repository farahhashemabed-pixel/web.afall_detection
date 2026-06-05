# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import sys
import time
import traceback
import base64
import cv2
from datetime import datetime

from predict_posture import PosturePredictor
from telegram_alert import send_telegram_alert, load_telegram_settings, save_telegram_settings, test_telegram_connection

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 256 * 1024 * 1024

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('models', exist_ok=True)


def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in IMAGE_EXTENSIONS


def allowed_video(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in VIDEO_EXTENSIONS


def send_alert_notification(posture, confidence):
    alert_data = {
        'timestamp': str(datetime.now()),
        'posture': posture,
        'confidence': confidence,
        'message': f'تنبيه: تم الكشف عن {posture}'
    }
    print(f"🔔 إرسال تنبيه: {alert_data}")
    return alert_data


def get_posture_description(posture):
    descriptions = {
        'جالس': '🪑 الشخص في وضعية جلوس - وضع آمن وطبيعي',
        'واقف': '🚶 الشخص في وضعية وقوف - وضع آمن وطبيعي',
        'سقوط': '⚠️ تم الكشف عن سقوط محتمل - اتصل بالمساعدة فوراً!'
    }
    return descriptions.get(posture, 'وضعية آمنة')


@app.route('/')
def index():
    print("🌐 تم طلب الصفحة الرئيسية")
    return render_template('index.html')


@app.route('/api/predict', methods=['POST'])
def predict():
    """معالجة الصور والتنبؤ بالوضعية"""
    print("=" * 50)
    print("📨 تم استقبال طلب تحليل صورة")
    print("=" * 50)

    try:
        if 'file' not in request.files:
            print('❌ خطأ: لا يوجد ملف في الطلب')
            return jsonify({'error': 'لم يتم تحديد ملف'}), 400

        file = request.files['file']
        print(f'📁 اسم الملف: {file.filename}')

        if file.filename == '':
            print('❌ خطأ: اسم الملف فارغ')
            return jsonify({'error': 'لم يتم اختيار ملف'}), 400

        if not allowed_image(file.filename):
            print(f'❌ خطأ: نوع الملف غير مدعوم - {file.filename}')
            return jsonify({'error': 'نوع الملف غير مدعوم. استخدم: PNG, JPG, JPEG, GIF, BMP'}), 400

        filename = secure_filename(file.filename)
        unique_filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        print(f'💾 حفظ الملف في: {filepath}')
        file.save(filepath)
        print('✅ تم حفظ الملف')

        if not os.path.exists(filepath):
            print('❌ فشل حفظ الملف')
            return jsonify({'error': 'فشل حفظ الملف'}), 500

        client_posture = request.form.get('posture')
        client_confidence_str = request.form.get('confidence')

        posture = None
        confidence = 0.0
        processed_img = None

        try:
            if client_posture and client_confidence_str:
                print(f"🤖 استخدام التنبؤ المرسل من المتصفح: {client_posture} ({client_confidence_str})")
                posture = client_posture
                try:
                    confidence = float(client_confidence_str.replace('%', '')) / 100.0
                except ValueError:
                    confidence = 0.95
                processed_img = cv2.imread(filepath)
            else:
                print("🤖 بدء التنبؤ في السيرفر...")
                predictor = PosturePredictor()
                posture, confidence, processed_img = predictor.predict_image(filepath)

            if posture is None:
                print('❌ فشل التنبؤ - بدون نتيجة')
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({'error': 'خطأ في معالجة الصورة - بدون نتيجة'}), 500

            print(f'✅ النتيجة النهائية: {posture}')
            print(f'📊 درجة الثقة: {confidence * 100:.2f}%')

            processed_image_b64 = None
            if processed_img is not None:
                success, buf = cv2.imencode('.jpg', processed_img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if success:
                    processed_image_b64 = base64.b64encode(buf.tobytes()).decode('utf-8')

        except Exception as predict_error:
            print(f'❌ خطأ في التنبؤ: {str(predict_error)}')
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': f'خطأ في التنبؤ: {str(predict_error)}'}), 500

        no_alert = request.form.get('no_alert') == 'true'
        is_alert = posture == 'سقوط' and confidence > 0.6 and not no_alert

        # استخراج بيانات تيليغرام الخاصة بالمستخدم الحالي فقط
        bot_token = request.form.get('bot_token', '').strip()
        chat_id = request.form.get('chat_id', '').strip()

        if is_alert:
            print(f"⚠️ تم اكتشاف تنبيه: {posture}")
            send_alert_notification(posture, confidence)
            tg_success, tg_msg = send_telegram_alert(
                posture, confidence * 100,
                image_path=filepath,
                bot_token=bot_token,
                chat_id=chat_id
            )
            print(f"📱 تيليغرام: {tg_msg}")

        if os.path.exists(filepath):
            os.remove(filepath)
            print('🗑️ تم حذف الملف المؤقت')

        response_data = {
            'status': 'success',
            'posture': posture,
            'confidence': f"{confidence * 100:.2f}%",
            'is_alert': is_alert,
            'alert_message': "⚠️ تنبيه!" if is_alert else "✅ آمن",
            'description': get_posture_description(posture),
            'processed_image': processed_image_b64
        }

        print(f'📤 إرسال النتيجة: posture={posture}, is_alert={is_alert}')
        print("=" * 50)

        return jsonify(response_data), 200

    except Exception as e:
        print(f"❌ خطأ غير متوقع: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'خطأ في المعالجة: {str(e)}'}), 500


@app.route('/api/predict_video', methods=['POST'])
def predict_video():
    """تحليل فيديو بأخذ فريمات كل نصف ثانية"""
    print("=" * 50)
    print("🎬 تم استقبال طلب تحليل فيديو")
    print("=" * 50)

    filepath = None
    temp_frame_path = None
    cap = None

    try:
        if 'file' not in request.files:
            print('❌ خطأ: لا يوجد ملف في الطلب')
            return jsonify({'error': 'لم يتم تحديد ملف'}), 400

        file = request.files['file']
        print(f'📁 اسم ملف الفيديو: {file.filename}')

        if file.filename == '':
            print('❌ خطأ: اسم الملف فارغ')
            return jsonify({'error': 'لم يتم اختيار ملف'}), 400

        if not allowed_video(file.filename):
            print(f'❌ نوع فيديو غير مدعوم - {file.filename}')
            return jsonify({'error': 'نوع الفيديو غير مدعوم. استخدم: MP4, AVI, MOV, MKV'}), 400

        filename = secure_filename(file.filename)
        unique_filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        print(f'💾 حفظ الفيديو في: {filepath}')
        file.save(filepath)
        print('✅ تم حفظ الفيديو')

        if not os.path.exists(filepath):
            print('❌ فشل حفظ الفيديو')
            return jsonify({'error': 'فشل حفظ الفيديو'}), 500

        # استخراج بيانات تيليغرام الخاصة بالمستخدم الحالي فقط
        bot_token = request.form.get('bot_token', '').strip()
        chat_id = request.form.get('chat_id', '').strip()

        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened():
            print('❌ لم يتمكن OpenCV من فتح الفيديو')
            return jsonify({'error': 'تعذر فتح ملف الفيديو للتحليل'}), 500

        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        if fps <= 0:
            fps = 25

        # نأخذ فريم كل نصف ثانية
        frame_interval = max(int(fps * 0.5), 1)
        frame_index = 0

        predictor = PosturePredictor()
        detected_events = []
        highest_risk = None
        temp_frame_path = os.path.join(app.config['UPLOAD_FOLDER'], f'temp_frame_{unique_filename}.jpg')

        print(f"🎞️ FPS: {fps}, frame_interval: {frame_interval}")

        # معالجة الفريمات
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_index % frame_interval == 0:
                cv2.imwrite(temp_frame_path, frame)

                try:
                    posture, confidence, _ = predictor.predict_image(temp_frame_path)
                except Exception as frame_err:
                    print(f"⚠️ خطأ في فريم {frame_index}: {frame_err}")
                    frame_index += 1
                    continue

                if posture is None:
                    frame_index += 1
                    continue

                time_sec = round(frame_index / fps, 1)
                print(f'🤖 فريم {frame_index} (~{time_sec}s): {posture} ({confidence * 100:.2f}%)')

                # ترميز الفريم بجودة منخفضة لتقليل الحجم
                small_frame = cv2.resize(frame, (160, 120))
                ok, buf = cv2.imencode('.jpg', small_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 20])
                image_b64 = base64.b64encode(buf.tobytes()).decode('utf-8') if ok else None

                event = {
                    'time_sec': time_sec,
                    'posture': posture,
                    'confidence': float(f"{confidence:.4f}"),
                    'is_alert': posture == 'سقوط' and confidence > 0.6,
                    'image_data': image_b64
                }
                detected_events.append(event)

                # تتبع أعلى خطورة
                if posture == 'سقوط' and confidence > 0.6:
                    if highest_risk is None or confidence > highest_risk['confidence']:
                        highest_risk = {
                            'time_sec': time_sec,
                            'posture': posture,
                            'confidence': confidence
                        }

            frame_index += 1

        cap.release()
        cap = None

        # حذف الفريم المؤقت
        if temp_frame_path and os.path.exists(temp_frame_path):
            os.remove(temp_frame_path)
            temp_frame_path = None

        # إذا لم تُكتشف أي أحداث
        if not detected_events:
            response_data = {
                'status': 'success',
                'posture': 'غير معروف',
                'confidence': '0.00%',
                'is_alert': False,
                'alert_message': 'لم يتم كشف أي شخص في الفيديو',
                'events': [],
                'frames_count': 0
            }
            # حذف ملف الفيديو
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
            return jsonify(response_data), 200

        # تقليل حجم بيانات الصور للأحداث العادية (ليس سقوط)
        if len(detected_events) > 15:
            for event in detected_events:
                if not event['is_alert']:
                    event['image_data'] = None

        is_alert = highest_risk is not None
        alert_message = "⚠️ تم الكشف عن سقوط!" if is_alert else "✅ آمن"
        final_posture = highest_risk['posture'] if is_alert else detected_events[-1]['posture']
        final_confidence = highest_risk['confidence'] if is_alert else detected_events[-1]['confidence']

        # إرسال تنبيه تيليغرام فقط عند اكتشاف سقوط حقيقي
        if is_alert:
            print(f"⚠️ تم اكتشاف سقوط في الفيديو: {final_posture} ({final_confidence * 100:.2f}%)")
            tg_success, tg_msg = send_telegram_alert(
                final_posture,
                final_confidence * 100,
                image_path=filepath,
                bot_token=bot_token,
                chat_id=chat_id
            )
            print(f"📱 تيليغرام: {tg_msg}")

        response_data = {
            'status': 'success',
            'posture': final_posture,
            'confidence': f"{final_confidence * 100:.2f}%",
            'is_alert': is_alert,
            'alert_message': alert_message,
            'description': get_posture_description(final_posture),
            'events': detected_events,
            'frames_count': len(detected_events)
        }

        # حذف ملف الفيديو
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            print('🗑️ تم حذف ملف الفيديو المؤقت')

        print(f'📤 إرسال النتيجة: posture={final_posture}, is_alert={is_alert}, events={len(detected_events)}')
        print("=" * 50)
        return jsonify(response_data), 200

    except Exception as e:
        print(f"❌ خطأ غير متوقع في تحليل الفيديو: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'خطأ في معالجة الفيديو: {str(e)}'}), 500

    finally:
        if cap is not None:
            cap.release()
        if temp_frame_path and os.path.exists(temp_frame_path):
            try:
                os.remove(temp_frame_path)
            except Exception:
                pass
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass


@app.route('/api/telegram/settings', methods=['GET'])
def get_telegram_settings():
    """الحصول على إعدادات تيليغرام"""
    settings = load_telegram_settings()
    return jsonify({
        'configured': bool(settings.get('bot_token') and settings.get('chat_id')),
        'chat_id': settings.get('chat_id', ''),
        'has_token': bool(settings.get('bot_token'))
    }), 200


@app.route('/api/telegram/settings', methods=['POST'])
def update_telegram_settings():
    """حفظ إعدادات تيليغرام"""
    data = request.get_json()
    bot_token = data.get('bot_token', '').strip()
    chat_id = data.get('chat_id', '').strip()

    if not bot_token or not chat_id:
        return jsonify({'error': 'يرجى إدخال Bot Token و Chat ID'}), 400

    save_telegram_settings(bot_token, chat_id)
    return jsonify({'status': 'success', 'message': 'تم حفظ الإعدادات'}), 200


@app.route('/api/telegram/test', methods=['POST'])
def test_telegram():
    """اختبار الاتصال بتيليغرام وإرسال رسالة تجريبية"""
    data = request.get_json()
    bot_token = data.get('bot_token', '').strip()
    chat_id = data.get('chat_id', '').strip()

    if not bot_token or not chat_id:
        return jsonify({'error': 'يرجى إدخال البيانات أولاً'}), 400

    success, message = test_telegram_connection(bot_token, chat_id)
    if success:
        return jsonify({'status': 'success', 'message': message}), 200
    else:
        return jsonify({'error': message}), 400


@app.route('/api/health', methods=['GET'])
def health():
    """فحص صحة النظام"""
    return jsonify({
        'status': 'online',
        'message': 'نظام مراقبة كبار السن - يعمل بشكل طبيعي',
        'timestamp': str(datetime.now())
    }), 200


@app.route('/api/stats', methods=['GET'])
def stats():
    """إحصائيات النظام"""
    return jsonify({
        'supported_postures': ['جالس', 'واقف', 'سقوط'],
        'model_accuracy': '99.2%',
        'supported_image_formats': list(IMAGE_EXTENSIONS),
        'supported_video_formats': list(VIDEO_EXTENSIONS),
        'max_file_size': '256MB'
    }), 200


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'الصفحة غير موجودة'}), 404


@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'خطأ في الخادم'}), 500


if __name__ == '__main__':
    print("=" * 50)
    print("🚀 بدء تشغيل نظام مراقبة كبار السن...")
    print("🌐 الموقع متاح على: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)