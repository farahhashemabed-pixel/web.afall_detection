import cv2
import numpy as np
import sys
import io
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
                self.classes = np.array(['جالس', 'واقف', 'ممدد', 'سقوط'])
                return
            
            self.model = keras.models.load_model(MODEL_PATH)
            
            if not os.path.exists(LABEL_ENCODER_PATH):
                self.dummy_mode = True
                self.classes = np.array(['جالس', 'واقف', 'ممدد', 'سقوط'])
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
            self.classes = np.array(['جالس', 'واقف', 'ممدد', 'سقوط'])
    
    def detect_body_parts(self, image_path):
        """كشف أجزاء الجسم"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None
            
            height, width = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # معالجة الصورة
            blurred = cv2.GaussianBlur(gray, (11, 11), 0)
            _, thresh = cv2.threshold(blurred, 100, 255, cv2.THRESH_BINARY)
            
            # كشف الحدود
            contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return None
            
            # أكبر حدود
            largest_contour = max(contours, key=cv2.contourArea)
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
        
        except Exception as e:
            safe_print(f"Error in body detection: {e}")
            return None
    
    def analyze_posture_advanced(self, image_path):
        """تحليل متقدم للوضعية"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None, 0
            
            body_info = self.detect_body_parts(image_path)
            if body_info is None:
                return None, 0
            
            height = body_info['height']
            width = body_info['width']
            img_height = body_info['img_height']
            img_width = body_info['img_width']
            
            # ==================== حسابات الوضعية ====================
            
            # 1️⃣ نسبة الأبعاد
            aspect_ratio = width / height if height > 0 else 0
            safe_print(f"Aspect Ratio (AR): {aspect_ratio:.3f}")
            
            # 2️⃣ كشف الحواف
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges) / (img_height * img_width)
            safe_print(f"Edge density: {edge_density:.5f}")
            
            # 3️⃣ ارتفاع الجسم مقارنة بارتفاع الصورة
            body_height_ratio = height / img_height
            safe_print(f"Body height ratio: {body_height_ratio:.3f}")
            
            # 4️⃣ عرض الجسم مقارنة بعرض الصورة
            body_width_ratio = width / img_width
            safe_print(f"Body width ratio: {body_width_ratio:.3f}")
            
            # 5️⃣ موضع المركز العمودي
            center_y_ratio = body_info['center_y'] / img_height
            safe_print(f"Center Y ratio: {center_y_ratio:.3f}")
            
            # ==================== قواعد التصنيف المصححة ====================
            
            safe_print("\n" + "="*50)
            safe_print("Posture Analysis [Heuristics Mode]:")
            safe_print("="*50)
            
            # **الواقف**: ضيق
            if aspect_ratio < 0.85 and body_height_ratio > 0.4:
                posture = 'واقف'
                confidence = 0.88
                reason = f"ضيق (AR={aspect_ratio:.2f}) وطويل"
                safe_print(f"Standing: {reason}")
            
            # **الجالس**: عرض متوسط
            elif 0.85 <= aspect_ratio < 1.4:
                posture = 'جالس'
                confidence = 0.87
                reason = f"متوسط (AR={aspect_ratio:.2f})"
                safe_print(f"Sitting: {reason}")
            
            # **السقوط/ممدد**: عريض جداً
            elif aspect_ratio >= 1.4:
                # إذا كان عريض جداً وقصير فهو ممدد، وإلا نعتبره سقوط
                if body_height_ratio < 0.45:
                    posture = 'ممدد'
                    confidence = 0.86
                    reason = f"عريض (AR={aspect_ratio:.2f}) وقصير"
                    safe_print(f"Lying down: {reason}")
                else:
                    posture = 'سقوط'
                    confidence = 0.85
                    reason = f"عريض جداً (AR={aspect_ratio:.2f})"
                    safe_print(f"Fall detected: {reason}")
            else:
                # القيمة الافتراضية
                posture = 'جالس'
                confidence = 0.70
                safe_print(f"Sitting (default)")
            
            safe_print(f"\nResult: {posture}")
            safe_print(f"Confidence: {confidence*100:.1f}%")
            safe_print("="*50 + "\n")
            
            return posture, confidence
        
        except Exception as e:
            safe_print(f"Error in analysis: {e}")
            import traceback
            traceback.print_exc()
            return None, 0
    
    def predict_image(self, image_path):
        """التنبؤ بوضعية الشخص"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None, 0
            
            print("\n" + "="*50)
            safe_print(f"Analyzing image")
            print("="*50)
            
            # استخدام النموذج الذكي إذا كان متاحاً
            if not getattr(self, 'dummy_mode', True) and self.model is not None and HAS_TF:
                try:
                    img_resized = cv2.resize(img, (IMG_SIZE, IMG_SIZE))
                    img_array = keras.preprocessing.image.img_to_array(img_resized)
                    img_array = np.expand_dims(img_array, axis=0)
                    img_array /= 255.0
                    
                    predictions = self.model.predict(img_array, verbose=0)[0]
                    class_idx = np.argmax(predictions)
                    posture = self.classes[class_idx]
                    confidence = float(predictions[class_idx])
                    
                    safe_print(f"[Model Output] Result: {posture} ({confidence*100:.1f}%)")
                    return posture, confidence
                except Exception as model_err:
                    safe_print(f"Model prediction failed, falling back to heuristics: {model_err}")
            
            # استخدام التحليل المتقدم كبديل
            return self.analyze_posture_advanced(image_path)
        
        except Exception as e:
            safe_print(f"Error: {e}")
            return None, 0
    
    def check_fall_alert(self, posture, confidence):
        """فحص التنبيهات"""
        if posture == 'سقوط' and confidence > 0.75:
            return True, "⚠️ تنبيه: تم اكتشاف سقوط محتمل!"
        elif posture == 'ممدد' and confidence > 0.70:
            return True, "⚠️ تحذير: الشخص في وضعية ممددة!"
        return False, f"✅ آمن: {posture}"

def predict_from_file(image_path):
    """دالة للتنبؤ"""
    predictor = PosturePredictor()
    posture, confidence = predictor.predict_image(image_path)
    
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