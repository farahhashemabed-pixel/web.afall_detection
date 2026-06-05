import os

app_path = "app.py"
if not os.path.exists(app_path):
    print("Error: app.py not found")
    exit()

with open(app_path, "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

# تحديد المعيارين للبداية والنهاية
start_marker = "@app.route('/api/predict', methods=['POST'])"
end_marker = "@app.route('/api/predict_video', methods=['POST'])"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f"Error: Markers not found. start_idx={start_idx}, end_idx={end_idx}")
    exit()

# الكود البرمجي الصحيح والمحسن لنقطة النهاية
correct_predict_route = """@app.route('/api/predict', methods=['POST'])
def predict():
    \"\"\"معالجة الصور والتنبؤ بالوضعية\"\"\"
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
        print("🤖 بدء التنبؤ...")
        try:
            predictor = PosturePredictor()
            posture, confidence, processed_img = predictor.predict_image(filepath)
            
            if posture is None:
                print('❌ فشل التنبؤ - بدون نتيجة')
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({'error': 'خطأ في معالجة الصورة - بدون نتيجة'}), 500
            
            print(f'✅ النتيجة: {posture}')
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

"""

# إعادة دمج الملف
new_content = content[:start_idx] + correct_predict_route + content[end_idx:]

with open(app_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Success: app.py has been repaired successfully!")
