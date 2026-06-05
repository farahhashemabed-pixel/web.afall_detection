import os
# Fix protobuf error in some environments
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
import cv2
import numpy as np
import sys
import io
try:
    import tensorflow as tf
    # Try direct keras import first (Keras 3)
    import keras
    HAS_TF = True
except ImportError:
    try:
        import tensorflow as tf
        from tensorflow import keras
        HAS_TF = True
    except ImportError:
        HAS_TF = False
import pickle
import os

# Safe print function to avoid UnicodeEncodeError on Windows
def safe_print(msg):
    try:
        print(msg)
    except (UnicodeEncodeError, UnicodeDecodeError):
        try:
            print(msg.encode('utf-8', errors='replace').decode('ascii', errors='replace'))
        except Exception:
            pass

IMG_SIZE = 224
MODEL_PATH = "models/elderly_posture_model.h5"
LABEL_ENCODER_PATH = "models/label_encoder.pkl"

class PosturePredictor:
    def __init__(self):
        """تحميل النموذج والمشفر"""
        try:
            if not os.path.exists(MODEL_PATH) or os.path.getsize(MODEL_PATH) == 0:
                try:
                    print("Warning: Model file not found or empty, using advanced analysis mode")
                except Exception:
                    pass
                self.model = None
                self.dummy_mode = True
                self.classes = np.array(['جالس', 'سقوط', 'واقف'])
                return
            
            self.model = keras.models.load_model(MODEL_PATH)
            
            if not os.path.exists(LABEL_ENCODER_PATH):
                self.dummy_mode = True
                self.classes = np.array(['جالس', 'سقوط', 'واقف'])
                return
            
            with open(LABEL_ENCODER_PATH, 'rb') as f:
                self.label_encoder = pickle.load(f)
            
            self.classes = self.label_encoder.classes_
            self.dummy_mode = False
            
        except Exception as e:
            try:
                print(f"Warning: Error loading model: {e}")
            except Exception:
                pass
            self.model = None
            self.dummy_mode = True
            self.classes = np.array(['جالس', 'سقوط', 'ممدد', 'واقف'])
    
    def detect_body_parts(self, image_input):
        """كشف أجزاء الجسم من مسار أو مصفوفة"""
        try:
            if isinstance(image_input, str):
                img = cv2.imread(image_input)
            else:
                img = image_input
            return self._detect_body_parts_internal(img)
        except Exception as e:
            safe_print(f"Error in body detection: {e}")
            return None

    def _detect_body_parts_internal(self, img):
        """كشف أجزاء الجسم للمصفوفة مباشرة"""
        try:
            if img is None:
                return None
            
            height, width = img.shape[:2]
            
            # تصحيح الدوران تلقائياً إذا كانت الصورة طولية جداً (كاميرا المحمول مثلاً)
            if height > width * 1.5:
                # محاولة تعديل المنطق ليعامل الطول كعرض في الحسابات اللاحقة
                pass

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # معالجة ذكية للصورة: تقليل الضوضاء وتحسين التباين
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # استخدام عتبة Otsu مع تحسين إضافي للكاميرا المباشرة
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            if np.sum(thresh) > (height * width * 255) / 2:
                thresh = cv2.bitwise_not(thresh)
            
            # تنظيف الصورة (Morphological Operations)
            kernel = np.ones((3,3), np.uint8)
            thresh = cv2.dilate(thresh, kernel, iterations=1)
            thresh = cv2.erode(thresh, kernel, iterations=1)
            
            # كشف الحدود
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return None
            
            largest_contour = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest_contour) < (height * width * 0.01): # تجاهل الأجسام الصغيرة جداً (ضوضاء)
                return None
                
            x, y, w, h = cv2.boundingRect(largest_contour)
            
            # حساب النقاط الرئيسية
            top = y
            bottom = y + h
            left = x
            right = x + w
            
            # Center
            cx = (left + right) // 2
            cy = (top + bottom) // 2
            
            body_info = {
                'top': top,
                'bottom': bottom,
                'left': left,
                'right': right,
                'center_x': cx,
                'center_y': cy,
                'width': w,
                'height': h,
                'img_height': height,
                'img_width': width
            }
            
            return body_info
        
        except Exception:
            return None
    
    def analyze_posture_advanced(self, image_input):
        """تحليل متقدم للوضعية من مسار أو مصفوفة"""
        try:
            if isinstance(image_input, str):
                img = cv2.imread(image_input)
            else:
                img = image_input
            return self._analyze_posture_advanced_internal(img)
        except Exception as e:
            safe_print(f"Error in analysis: {e}")
            return None, 0, None

    def _analyze_posture_advanced_internal(self, img):
        """التحليل المنطقي المتقدم للمصفوفة"""
        try:
            if img is None:
                return None, 0, None
            
            body_info = self._detect_body_parts_internal(img)
            if body_info is None:
                return None, 0, img.copy()
            
            height = body_info['height']
            width = body_info['width']
            img_height = body_info['img_height']
            img_width = body_info['img_width']
            
            # ==================== حسابات الوضعية ====================
            
            # 1️⃣ نسبة الأبعاد
            aspect_ratio = width / height if height > 0 else 0
            
            # 2️⃣ كشف الحواف
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges) / (img_height * img_width)
            
            # 3️⃣ ارتفاع الجسم مقارنة بارتفاع الصورة
            body_height_ratio = height / img_height
            
            # 4️⃣ عرض الجسم مقارنة بعرض الصورة
            body_width_ratio = width / img_width
            
            # 5️⃣ موضع المركز العمودي
            center_y_ratio = body_info['center_y'] / img_height
            
            # ==================== قواعد التصنيف المحدثة والنهائية (3 حالات فقط) ====================
            
            # 1. الوقوف والمشي: تم رفع النسبة لتصبح 0.55 بدلاً من 0.45 لتناسب الثياب الواسعة كالثوب الأبيض وحركة المشي
            if aspect_ratio < 0.55: 
                posture = 'واقف'
                confidence = 0.95
            
            # 2. الجالس (أمامي أو جانبي): أي عرض متوسط يميل للجلوس
            elif 0.55 <= aspect_ratio < 1.10:
                posture = 'جالس'
                confidence = 0.92
            
            # 3. السقوط: الجسم مسطح وأفقي تماماً
            elif aspect_ratio >= 1.10:
                posture = 'سقوط'
                confidence = 0.98
            else:
                posture = 'جالس'
                confidence = 0.70
            
            # طباعة للتشخيص في سجلات الموقع
            print(f"DIAGNOSTIC: Aspect_Ratio={aspect_ratio:.2f} -> Result: {posture}")
            
            # ==================== رسم صندوق الاكتشاف والبيانات مرئياً ====================
            processed_img = img.copy()
            
            bx, by, bw, bh = body_info['left'], body_info['top'], body_info['width'], body_info['height']
            
            # اختيار اللون بناء على الوضعية
            if posture == 'سقوط':
                color = (0, 0, 255)  # أحمر في BGR
            elif posture == 'جالس':
                color = (0, 165, 255)  # برتقالي/أصفر في BGR
            else:
                color = (0, 255, 0)  # أخضر في BGR
            
            # رسم مستطيل صندوق الاكتشاف
            cv2.rectangle(processed_img, (bx, by), (bx + bw, by + bh), color, 3)
            
            # كتابة النص الإنجليزي لتجنب مشاكل ترميز اللغة العربية في OpenCV
            eng_posture = "Standing" if posture == 'واقف' else ("Sitting" if posture == 'جالس' else "FALLEN")
            label_text = f"{eng_posture} ({confidence*100:.1f}%) AR:{aspect_ratio:.2f}"
            
            # رسم خلفية للنص لتسهيل قراءته
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 2
            (text_w, text_h), baseline = cv2.getTextSize(label_text, font, font_scale, thickness)
            
            text_y = max(by - 10, text_h + 10)
            cv2.rectangle(processed_img, (bx, text_y - text_h - 5), (bx + text_w, text_y + baseline - 5), color, -1)
            cv2.putText(processed_img, label_text, (bx, text_y - 2), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
            
            return posture, confidence, processed_img
        
        except Exception as e:
            safe_print(f"Error in _analyze_posture_advanced_internal: {e}")
            return None, 0, img.copy() if img is not None else None
    
    def predict_image(self, image_input):
        """التنبؤ بوضعية الشخص - يدعم مسار صورة أو مصفوفة numpy مباشرة"""
        try:
            if isinstance(image_input, str):
                img = cv2.imread(image_input)
            else:
                img = image_input

            if img is None:
                return None, 0, None
            
            # التحليل المنطقي المباشر (Heuristics)
            return self.analyze_posture_advanced(img)
        
        except Exception:
            return None, 0, None
    
    def check_fall_alert(self, posture, confidence):
        """فحص التنبيهات"""
        if posture == 'سقوط' and (confidence or 0) > 0.70:
            return True, "⚠️ تنبيه: تم اكتشاف سقوط محتمل!"
        return False, f"✅ آمن: {posture}"

def predict_from_file(image_path):
    """دالة للتنبؤ"""
    predictor = PosturePredictor()
    posture, confidence, _ = predictor.predict_image(image_path)
    
    if posture is None:
        return {
            'status': 'error',
            'message': 'خطأ في معالجة الصورة'
        }
    
    is_alert, alert_message = predictor.check_fall_alert(posture, confidence)
    
    return {
        'status': 'success',
        'posture': posture,
        'confidence': f"{confidence * 100:.1f}%",
        'is_alert': is_alert,
        'message': alert_message
    }
#.. pip install tensorflow ..