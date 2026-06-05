from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import sys

from predict_posture import PosturePredictor
from telegram_alert import send_telegram_alert, load_telegram_settings, save_telegram_settings, test_telegram_connection
from datetime import datetime
import traceback
import cv2
import base64

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 256 * 1024 * 1024

# Ø§ÙØ³ÙØ§Ø­ Ø¨Ø£ÙÙØ§Ø¹ Ø§ÙÙÙÙØ§Øª Ø§ÙÙØ¯Ø¹ÙÙØ© ÙÙØµÙØ± ÙØ§ÙÙÙØ¯ÙÙ
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

# Ø¥ÙØ´Ø§Ø¡ Ø§ÙÙØ¬ÙØ¯Ø§Øª Ø§ÙÙØ·ÙÙØ¨Ø©
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('models', exist_ok=True)

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in IMAGE_EXTENSIONS


def allowed_video(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in VIDEO_EXTENSIONS

def send_alert_notification(posture, confidence):
    """Ø¥Ø±Ø³Ø§Ù ØªÙØ¨ÙÙ"""
    alert_data = {
        'timestamp': str(datetime.now()),
        'posture': posture,
        'confidence': confidence,
        'message': f'ØªÙØ¨ÙÙ: ØªÙ Ø§ÙØªØ´Ø§Ù {posture}'
    }
    print(f"ð¢ Ø¥Ø±Ø³Ø§Ù ØªÙØ¨ÙÙ: {alert_data}")
    return alert_data

@app.route('/')
def index():
    """Ø¹Ø±Ø¶ Ø§ÙØµÙØ­Ø© Ø§ÙØ±Ø¦ÙØ³ÙØ©"""
    print("ð± ØªÙ Ø·ÙØ¨ Ø§ÙØµÙØ­Ø© Ø§ÙØ±Ø¦ÙØ³ÙØ©")
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
        
        # حفظ الملف
        filename = secure_filename(file.filename)
        import time
        unique_filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        print(f'💾 حفظ الملف في: {filepath}')
        file.save(filepath)
        print(f'✅ تم حفظ الملف')
        
        # التحقق من أن الملف تم حفظه بنجاح
        if not os.path.exists(filepath):
            print('❌ فشل حفظ الملف')
            return jsonify({'error': 'فشل حفظ الملف'}), 500
        
        # التنبؤ
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
                
                # قراءة الصورة التي تم رسم الصناديق عليها بالفعل في المتصفح
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
            
            # ترميز الصورة المعالجة بالـ Base64
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
        
        # فحص التنبيهات وإرسال تيليغرام مع الصورة
        is_alert = posture in ['سقوط', 'ممدد'] and confidence > 0.6
        
        if is_alert:
            print(f"⚠️ تم اكتشاف تنبيه: {posture}")
            send_alert_notification(posture, confidence)
            tg_success, tg_msg = send_telegram_alert(posture, confidence * 100, image_path=filepath)
            print(f"📱 تيليغرام: {tg_msg}")
        
        # حذف الملف بعد المعالجة
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f'🗑️ تم حذف الملف المؤقت')
        
        # إرسال النتيجة
        response_data = {
            'status': 'success',
            'posture': posture,
            'confidence': f"{confidence * 100:.2f}%",
            'is_alert': is_alert,
            'alert_message': f"⚠️ تنبيه!" if is_alert else "✅ آمن",
            'description': get_posture_description(posture),
            'processed_image': processed_image_b64
        }
        
        print(f'📤 إرسال النتيجة: {response_data}')
        print("=" * 50)
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"❌ خطأ غير متوقع: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'خطأ في المعالجة: {str(e)}'}), 500
@app.route('/api/predict_video', methods=['POST'])
def predict_video():
    """ØªØ­ÙÙÙ ÙÙØ¯ÙÙ Ø¨Ø£Ø®Ø° ÙØ±ÙÙØ§Øª ÙÙ 15 Ø«Ø§ÙÙØ©"""
    print("=" * 50)
    print("ð¨ ØªÙ Ø§Ø³ØªÙØ¨Ø§Ù Ø·ÙØ¨ ØªØ­ÙÙÙ ÙÙØ¯ÙÙ")
    print("=" * 50)

    try:
        if 'file' not in request.files:
            print('â Ø®Ø·Ø£: ÙØ§ ÙÙØ¬Ø¯ ÙÙÙ ÙÙ Ø§ÙØ·ÙØ¨')
            return jsonify({'error': 'ÙÙ ÙØªÙ ØªØ­Ø¯ÙØ¯ ÙÙÙ'}), 400

        file = request.files['file']
        print(f'ð Ø§Ø³Ù ÙÙÙ Ø§ÙÙÙØ¯ÙÙ: {file.filename}')

        if file.filename == '':
            print('â Ø®Ø·Ø£: Ø§Ø³Ù Ø§ÙÙÙÙ ÙØ§Ø±Øº')
            return jsonify({'error': 'ÙÙ ÙØªÙ Ø§Ø®ØªÙØ§Ø± ÙÙÙ'}), 400

        if not allowed_video(file.filename):
            print(f'â ÙÙØ¹ ÙÙØ¯ÙÙ ØºÙØ± ÙØ¯Ø¹ÙÙ - {file.filename}')
            return jsonify({'error': 'ÙÙØ¹ Ø§ÙÙÙØ¯ÙÙ ØºÙØ± ÙØ¯Ø¹ÙÙ. Ø§Ø³ØªØ®Ø¯Ù: MP4, AVI, MOV, MKV'}), 400

        filename = secure_filename(file.filename)
        import time
        unique_filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        print(f'ð¾ Ø­ÙØ¸ Ø§ÙÙÙØ¯ÙÙ ÙÙ: {filepath}')
        file.save(filepath)
        print('â ØªÙ Ø­ÙØ¸ Ø§ÙÙÙØ¯ÙÙ')

        if not os.path.exists(filepath):
            print('â ÙØ´Ù Ø­ÙØ¸ Ø§ÙÙÙØ¯ÙÙ')
            return jsonify({'error': 'ÙØ´Ù Ø­ÙØ¸ Ø§ÙÙÙØ¯ÙÙ'}), 500

        predictor = PosturePredictor()
        cap = None

        try:
            cap = cv2.VideoCapture(filepath)
            if not cap.isOpened():
                print('â ÙÙ ÙØªÙÙÙ OpenCV ÙÙ ÙØªØ­ Ø§ÙÙÙØ¯ÙÙ')
                return jsonify({'error': 'ØªØ¹Ø°Ø± ÙØªØ­ ÙÙÙ Ø§ÙÙÙØ¯ÙÙ ÙÙØªØ­ÙÙÙ'}), 500

            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            if fps <= 0:
                fps = 25

            # Ø£Ø®Ø° ÙØ±ÙÙ ÙÙ 0.5 Ø«Ø§ÙÙØ© ÙØªØ­Ø³ÙÙ Ø¯ÙØ© Ø§ÙØªØ´Ø§Ù Ø§ÙØ³ÙÙØ· Ø§ÙØ³Ø±ÙØ¹
            frame_interval = max(int(fps * 0.5), 1)
            frame_index = 0
            
            detected_events = []
            highest_risk = None

            temp_frame_path = os.path.join(app.config['UPLOAD_FOLDER'], f'temp_frame_{unique_filename}.jpg')

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_index % frame_interval == 0:
                    # Ø­ÙØ¸ Ø§ÙÙØ±ÙÙ ÙØµÙØ±Ø© Ø«Ù ØªØ­ÙÙÙÙ ØªÙØ§ÙØ§Ù ÙÙØ§ ÙØ­Ø¯Ø« ÙØ¹ Ø§ÙØµÙØ± Ø§ÙÙØ±ÙÙØ¹Ø© ÙÙØ§ Ø·ÙØ¨ Ø§ÙÙØ³ØªØ®Ø¯Ù
                    cv2.imwrite(temp_frame_path, frame)
                    posture, confidence, processed_img = predictor.predict_image(temp_frame_path)

                    if posture is None:
                        frame_index += 1
                        continue

                    print(f'ðï¸ ÙØ±ÙÙ Ø¹ÙØ¯ Ø§ÙØ«Ø§ÙÙØ© ~{frame_index / fps:.1f}: {posture} ({confidence * 100:.2f}%)')

                    # ØªØµØºÙØ± Ø­Ø¬Ù Ø§ÙØµÙØ±Ø© Ø¬Ø¯Ø§Ù ÙØªÙÙÙÙ Ø§Ø³ØªÙÙØ§Ù Ø§ÙØ°Ø§ÙØ±Ø© ÙØ§ÙØ´Ø¨ÙØ©
                    small_frame = cv2.resize(frame, (160, 160))
                    # ØªØ­ÙÙÙ Ø§ÙÙØ±ÙÙ Ø¥ÙÙ Base64 ÙÙØ¹Ø±Ø¶ ÙÙ Ø§ÙÙØ§Ø¬ÙØ© ÙØ¹ Ø¶ØºØ· Ø¹Ø§ÙÙ Ø¬Ø¯Ø§Ù
                    success, buf = cv2.imencode('.jpg', small_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 20])
                    image_b64 = None
                    if success:
                        image_b64 = base64.b64encode(buf.tobytes()).decode('utf-8')

                    event = {
                        'time_sec': round(frame_index / fps, 1),
                        'posture': posture,
                        'confidence': float(f"{confidence:.4f}"),
                        'image_data': image_b64
                    }
                    detected_events.append(event)

                    if posture in ['Ø³ÙÙØ·', 'ÙÙØ¯Ø¯']:
                        if highest_risk is None or confidence > highest_risk['confidence']:
                            highest_risk = {
                                'time_sec': event['time_sec'],
                                'posture': posture,
                                'confidence': confidence
                            }

                frame_index += 1

            if os.path.exists(temp_frame_path):
                os.remove(temp_frame_path)

            if not detected_events:
                return jsonify({
                    'status': 'success',
                    'posture': 'ØºÙØ± ÙØ¹Ø±ÙÙ',
                    'confidence': '0.00%',
                    'is_alert': False,
                    'alert_message': 'ÙÙ ÙØªÙÙÙ Ø§ÙÙØ¸Ø§Ù ÙÙ Ø§Ø³ØªØ®Ø±Ø§Ø¬ ÙØ±ÙÙØ§Øª ØµØ§ÙØ­Ø© ÙÙ Ø§ÙÙÙØ¯ÙÙ',
                    'description': 'ØªØ­ÙÙ ÙÙ Ø£Ù Ø§ÙÙÙØ¯ÙÙ ÙØ§Ø¶Ø­ ÙÙØ­ØªÙÙ Ø¹ÙÙ Ø´Ø®Øµ ÙÙ Ø§ÙØ¥Ø·Ø§Ø±.',
                    'events': [],
                    'frames_count': 0
                }), 200

            if highest_risk:
                is_alert = True
                posture = highest_risk['posture']
                confidence = highest_risk['confidence']
                description = get_posture_description(posture) + f" (ÙÙØª Ø§ÙØ§ÙØªØ´Ø§Ù Ø§ÙØªÙØ±ÙØ¨Ù: {highest_risk['time_sec']} Ø«Ø§ÙÙØ©)"
                # Ø¥Ø±Ø³Ø§Ù ØªÙØ¨ÙÙ ØªÙÙÙØºØ±Ø§Ù ÙÙÙÙØ¯ÙÙ
                tg_success, tg_msg = send_telegram_alert(posture, confidence * 100)
                print(f"ð± ØªÙÙÙØºØ±Ø§Ù (ÙÙØ¯ÙÙ): {tg_msg}")
            else:
                last_event = detected_events[-1]
                posture = last_event['posture']
                confidence = last_event['confidence']
                is_alert = posture in ['Ø³ÙÙØ·', 'ÙÙØ¯Ø¯'] and confidence > 0.6
                description = get_posture_description(posture)

            response_data = {
                'status': 'success',
                'posture': posture,
                'confidence': f"{confidence * 100:.2f}%",
                'is_alert': is_alert,
                'alert_message': f"â ï¸ ØªÙØ¨ÙÙ ÙÙ Ø§ÙÙÙØ¯ÙÙ!" if is_alert else "â ÙØ§ ÙÙØ¬Ø¯ Ø³ÙÙØ· ÙØ§Ø¶Ø­ ÙÙ Ø§ÙÙÙØ¯ÙÙ",
                'description': description,
                'events': detected_events,
                'frames_count': len(detected_events)
            }

            # Ø¥Ø°Ø§ ÙØ§Ù Ø¹Ø¯Ø¯ Ø§ÙØ£Ø­Ø¯Ø§Ø« ÙØ¨ÙØ±Ø§Ù Ø¬Ø¯Ø§ÙØ ÙÙØªÙÙ Ø¨Ø£ÙÙ Ø§ÙØ£Ø­Ø¯Ø§Ø« ÙØªØ¬ÙØ¨ ØªØ¬Ø§ÙØ² Ø­Ø¯ÙØ¯ Ø§ÙØ´Ø¨ÙØ© ÙÙ Ø§ÙØ³ÙØ±ÙØ±Ø§Øª Ø§ÙÙØ¬Ø§ÙÙØ©
            if len(detected_events) > 15:
                # ÙØ­ØªÙØ¸ Ø¨ØµÙØ± Ø£Ø­Ø¯Ø§Ø« Ø§ÙØ³ÙÙØ· ÙÙØ· ÙÙÙØºÙ ØµÙØ± Ø§ÙÙØ´Ù Ø§ÙØ¹Ø§Ø¯Ù ÙØªÙÙÙÙ Ø§ÙØ­Ø¬Ù
                for event in detected_events:
                    if event['posture'] not in ['Ø³ÙÙØ·', 'ÙÙØ¯Ø¯']:
                        event['image_data'] = None 

            # Ø­Ø°ÙÙØ§ Ø£ÙØ± Ø§ÙØ·Ø¨Ø§Ø¹Ø© ÙÙØ§ ÙØ£ÙÙ ÙØ³Ø¨Ø¨ Ø®Ø·Ø£ Message too long Ø¨Ø³Ø¨Ø¨ Ø­Ø¬Ù ØµÙØ± Base64
            return jsonify(response_data), 200

        finally:
            if cap is not None:
                cap.release()
            try:
                if 'temp_frame_path' in locals() and os.path.exists(temp_frame_path):
                    os.remove(temp_frame_path)
            except Exception:
                pass
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    print('ðï¸ ØªÙ Ø­Ø°Ù ÙÙÙ Ø§ÙÙÙØ¯ÙÙ Ø§ÙÙØ¤ÙØª')
                except Exception as del_err:
                    print(f'â ï¸ ØªØ¹Ø°Ø± Ø­Ø°Ù ÙÙÙ Ø§ÙÙÙØ¯ÙÙ Ø§ÙÙØ¤ÙØª: {del_err}')

    except Exception as e:
        print(f"â Ø®Ø·Ø£ ØºÙØ± ÙØªÙÙØ¹ ÙÙ ØªØ­ÙÙÙ Ø§ÙÙÙØ¯ÙÙ: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Ø®Ø·Ø£ ÙÙ ÙØ¹Ø§ÙØ¬Ø© Ø§ÙÙÙØ¯ÙÙ: {str(e)}'}), 500

@app.route('/api/telegram/settings', methods=['GET'])
def get_telegram_settings():
    """Ø§ÙØ­ØµÙÙ Ø¹ÙÙ Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª ØªÙÙÙØºØ±Ø§Ù"""
    settings = load_telegram_settings()
    # ÙØ§ ÙÙØ±Ø¬Ø¹ Ø§ÙØªÙÙÙ ÙØ§ÙÙØ§Ù ÙÙØ£ÙØ§ÙØ ÙÙØ· ÙÙØ¸ÙØ± ÙÙ ÙÙ ÙØ¶Ø¨ÙØ· Ø£Ù ÙØ§
    return jsonify({
        'configured': bool(settings.get('bot_token') and settings.get('chat_id')),
        'chat_id': settings.get('chat_id', ''),
        'has_token': bool(settings.get('bot_token'))
    }), 200

@app.route('/api/telegram/settings', methods=['POST'])
def update_telegram_settings():
    """Ø­ÙØ¸ Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª ØªÙÙÙØºØ±Ø§Ù"""
    data = request.get_json()
    bot_token = data.get('bot_token', '').strip()
    chat_id = data.get('chat_id', '').strip()
    
    if not bot_token or not chat_id:
        return jsonify({'error': 'ÙØ±Ø¬Ù Ø¥Ø¯Ø®Ø§Ù Bot Token Ù Chat ID'}), 400
    
    save_telegram_settings(bot_token, chat_id)
    return jsonify({'status': 'success', 'message': 'ØªÙ Ø­ÙØ¸ Ø§ÙØ¥Ø¹Ø¯Ø§Ø¯Ø§Øª'}), 200

@app.route('/api/telegram/test', methods=['POST'])
def test_telegram():
    """Ø§Ø®ØªØ¨Ø§Ø± Ø§ÙØ§ØªØµØ§Ù Ø¨ØªÙÙÙØºØ±Ø§Ù ÙØ¥Ø±Ø³Ø§Ù Ø±Ø³Ø§ÙØ© ØªØ¬Ø±ÙØ¨ÙØ©"""
    data = request.get_json()
    bot_token = data.get('bot_token', '').strip()
    chat_id = data.get('chat_id', '').strip()
    
    if not bot_token or not chat_id:
        return jsonify({'error': 'ÙØ±Ø¬Ù Ø¥Ø¯Ø®Ø§Ù Ø§ÙØ¨ÙØ§ÙØ§Øª Ø£ÙÙØ§Ù'}), 400
    
    success, message = test_telegram_connection(bot_token, chat_id)
    if success:
        return jsonify({'status': 'success', 'message': message}), 200
    else:
        return jsonify({'error': message}), 400


@app.route('/api/health', methods=['GET'])
def health():
    """ÙØ­Øµ ØµØ­Ø© Ø§ÙÙØ¸Ø§Ù"""
    return jsonify({
        'status': 'online',
        'message': 'ÙØ¸Ø§Ù ÙØ±Ø§ÙØ¨Ø© ÙØ¨Ø§Ø± Ø§ÙØ³Ù - ÙØ¹ÙÙ Ø¨Ø´ÙÙ Ø·Ø¨ÙØ¹Ù',
        'timestamp': str(datetime.now())
    }), 200

@app.route('/api/stats', methods=['GET'])
def stats():
    """Ø¥Ø­ØµØ§Ø¦ÙØ§Øª Ø§ÙÙØ¸Ø§Ù"""
    return jsonify({
           'supported_postures': ['Ø¬Ø§ÙØ³', 'ÙØ§ÙÙ', 'Ø³ÙÙØ·'],
           'model_accuracy': '99.2%',
           'supported_image_formats': list(IMAGE_EXTENSIONS),
           'supported_video_formats': list(VIDEO_EXTENSIONS),
           'max_file_size': '256MB'
    }), 200

def get_posture_description(posture):
    """Ø§ÙØ­ØµÙÙ Ø¹ÙÙ ÙØµÙ ÙÙÙØ¶Ø¹ÙØ©"""
    descriptions = {
        'Ø¬Ø§ÙØ³': 'ð¤ Ø§ÙØ´Ø®Øµ ÙÙ ÙØ¶Ø¹ÙØ© Ø¬ÙÙØ³ - ÙØ¶Ø¹ Ø¢ÙÙ ÙØ·Ø¨ÙØ¹Ù',
        'ÙØ§ÙÙ': 'ð¶ Ø§ÙØ´Ø®Øµ ÙÙ ÙØ¶Ø¹ÙØ© ÙÙÙÙ - ÙØ¶Ø¹ Ø¢ÙÙ ÙØ·Ø¨ÙØ¹Ù',
        'Ø³ÙÙØ·': 'â ï¸ ØªÙ Ø§ÙØªØ´Ø§Ù Ø³ÙÙØ· ÙØ­ØªÙÙ - Ø§ØªØµÙ Ø¨Ø§ÙÙØ³Ø§Ø¹Ø¯Ø© ÙÙØ±Ø§Ù!'
    }
    return descriptions.get(posture, 'ÙØ¶Ø¹ÙØ© Ø¢ÙÙØ©')

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Ø§ÙØµÙØ­Ø© ØºÙØ± ÙÙØ¬ÙØ¯Ø©'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Ø®Ø·Ø£ ÙÙ Ø§ÙØ®Ø§Ø¯Ù'}), 500

if __name__ == '__main__':
    print("=" * 50)
    print("ð Ø¨Ø¯Ø¡ ØªØ´ØºÙÙ ÙØ¸Ø§Ù ÙØ±Ø§ÙØ¨Ø© ÙØ¨Ø§Ø± Ø§ÙØ³Ù...")
    print("ð Ø§ÙÙÙÙØ¹ ÙØªØ§Ø­ Ø¹ÙÙ: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)