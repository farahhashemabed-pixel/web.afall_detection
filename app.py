from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import sys

from predict_posture import PosturePredictor
from datetime import datetime
import traceback
import cv2
import base64

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 256 * 1024 * 1024

# السماح بأنواع الملفات المدعومة للصور والفيديو
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

# إنشاء المجلدات المطلوبة
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('models', exist_ok=True)

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in IMAGE_EXTENSIONS


def allowed_video(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in VIDEO_EXTENSIONS

def send_alert_notification(posture, confidence):
    """إرسال تنبيه"""
    alert_data = {
        'timestamp': str(datetime.now()),
        'posture': posture,
        'confidence': confidence,
        'message': f'تنبيه: تم اكتشاف {posture}'
    }
    print(f"📢 إرسال تنبيه: {alert_data}")
    return alert_data

@app.route('/')
def index():
    """عرض الصفحة الرئيسية"""
    print("📱 تم طلب الصفحة الرئيسية")
    return render_template('index.html')

@app.route('/api/predict', methods=['POST'])
def predict():
    """معالجة الصور والتنبؤ بالوضعية"""
    print("=" * 50)
    print("📨 تم استقبال طلب تحليل صورة")
    print("=" * 50)
    
    try:
        # فحص وجود ملف
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
        # أضف timestamp لتجنب تضارب الأسماء
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
        print("🤖 بدء التنبؤ...")
        try:
            predictor = PosturePredictor()
            posture, confidence = predictor.predict_image(filepath)
            
            if posture is None:
                print('❌ فشل التنبؤ - بدون نتيجة')
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({'error': 'خطأ في معالجة الصورة - بدون نتيجة'}), 500
            
            print(f'✅ النتيجة: {posture}')
            print(f'📊 درجة الثقة: {confidence * 100:.2f}%')
            
        except Exception as predict_error:
            print(f'❌ خطأ في التنبؤ: {str(predict_error)}')
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': f'خطأ في التنبؤ: {str(predict_error)}'}), 500
        
        # فحص التنبيهات
        is_alert = posture in ['سقوط', 'ممدد'] and confidence > 0.6
        
        if is_alert:
            print(f"⚠️ تم اكتشاف تنبيه: {posture}")
            send_alert_notification(posture, confidence)
        
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
            'description': get_posture_description(posture)
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
    """تحليل فيديو بأخذ فريمات كل 15 ثانية"""
    print("=" * 50)
    print("📨 تم استقبال طلب تحليل فيديو")
    print("=" * 50)

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
        import time
        unique_filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        print(f'💾 حفظ الفيديو في: {filepath}')
        file.save(filepath)
        print('✅ تم حفظ الفيديو')

        if not os.path.exists(filepath):
            print('❌ فشل حفظ الفيديو')
            return jsonify({'error': 'فشل حفظ الفيديو'}), 500

        predictor = PosturePredictor()
        cap = None

        try:
            cap = cv2.VideoCapture(filepath)
            if not cap.isOpened():
                print('❌ لم يتمكن OpenCV من فتح الفيديو')
                return jsonify({'error': 'تعذر فتح ملف الفيديو للتحليل'}), 500

            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            if fps <= 0:
                fps = 25

            # أخذ فريم كل 3 ثواني تقريباً
            frame_interval = max(int(fps * 3), 1)
            frame_index = 0
            
            detected_events = []
            highest_risk = None

            temp_frame_path = os.path.join(app.config['UPLOAD_FOLDER'], f'temp_frame_{unique_filename}.jpg')

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_index % frame_interval == 0:
                    # حفظ الفريم مؤقتاً والتحليل
                    cv2.imwrite(temp_frame_path, frame)
                    posture, confidence = predictor.predict_image(temp_frame_path)

                    if posture is None:
                        frame_index += 1
                        continue

                    print(f'🎞️ فريم عند الثانية ~{frame_index / fps:.1f}: {posture} ({confidence * 100:.2f}%)')

                    # تحويل الفريم إلى Base64 للعرض في الواجهة مع ضغط عالي جداً لتجنب خطأ Message too long
                    # نستخدم جودة 30% لتقليل حجم البيانات التي يتم إرسالها في الاستجابة
                    success, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
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

                    if posture in ['سقوط', 'ممدد']:
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
                    'posture': 'غير معروف',
                    'confidence': '0.00%',
                    'is_alert': False,
                    'alert_message': 'لم يتمكن النظام من استخراج فريمات صالحة من الفيديو',
                    'description': 'تحقق من أن الفيديو واضح ويحتوي على شخص في الإطار.',
                    'events': [],
                    'frames_count': 0
                }), 200

            if highest_risk:
                is_alert = True
                posture = highest_risk['posture']
                confidence = highest_risk['confidence']
                description = get_posture_description(posture) + f" (وقت الاكتشاف التقريبي: {highest_risk['time_sec']} ثانية)"
            else:
                last_event = detected_events[-1]
                posture = last_event['posture']
                confidence = last_event['confidence']
                is_alert = posture in ['سقوط', 'ممدد'] and confidence > 0.6
                description = get_posture_description(posture)

            response_data = {
                'status': 'success',
                'posture': posture,
                'confidence': f"{confidence * 100:.2f}%",
                'is_alert': is_alert,
                'alert_message': f"⚠️ تنبيه في الفيديو!" if is_alert else "✅ لا يوجد سقوط واضح في الفيديو",
                'description': description,
                'events': detected_events,
                'frames_count': len(detected_events)
            }

            # إذا كان عدد الأحداث كبيراً جداً، نكتفي بأهم الأحداث لتجنب تجاوز حدود الشبكة في السيرفرات المجانية
            if len(detected_events) > 15:
                # نحتفظ بصور أحداث السقوط فقط ونلغي صور المشي العادي لتقليل الحجم
                for event in detected_events:
                    if event['posture'] not in ['سقوط', 'ممدد']:
                        event['image_data'] = None 

            print(f'📤 نتيجة تحليل الفيديو: {response_data}')
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
                    print('🗑️ تم حذف ملف الفيديو المؤقت')
                except Exception as del_err:
                    print(f'⚠️ تعذر حذف ملف الفيديو المؤقت: {del_err}')

    except Exception as e:
        print(f"❌ خطأ غير متوقع في تحليل الفيديو: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'خطأ في معالجة الفيديو: {str(e)}'}), 500


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
           'supported_postures': ['جالس', 'واقف', 'ممدد', 'سقوط'],
           'model_accuracy': '98%',
           'supported_image_formats': list(IMAGE_EXTENSIONS),
           'supported_video_formats': list(VIDEO_EXTENSIONS),
           'max_file_size': '256MB'
    }), 200

def get_posture_description(posture):
    """الحصول على وصف للوضعية"""
    descriptions = {
        'جالس': '👤 الشخص في وضعية جلوس - وضع آمن وطبيعي',
        'واقف': '🚶 الشخص في وضعية وقوف - وضع آمن وطبيعي',
        'ممدد': '🛏️ الشخص في وضعية استلقاء - يرجى التحقق من سلامته',
        'سقوط': '⚠️ تم اكتشاف سقوط محتمل - اتصل بالمساعدة فوراً!'
    }
    return descriptions.get(posture, 'وضعية غير معروفة')

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