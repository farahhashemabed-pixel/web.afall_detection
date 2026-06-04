import os
# Fix protobuf error in some environments
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
import numpy as np
import cv2
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import tensorflow as tf
try:
    import keras
except ImportError:
    from tensorflow import keras

# Try to get ImageDataGenerator from keras or tf.keras
try:
    from keras.preprocessing.image import ImageDataGenerator
except ImportError:
    from tensorflow.keras.preprocessing.image import ImageDataGenerator

# Ensure we use standard tf.keras for layers and models if possible
try:
    layers = keras.layers
    models = keras.models
except Exception:
    layers = tf.keras.layers
    models = tf.keras.models

import pickle
import warnings
warnings.filterwarnings('ignore')

# إعدادات المشروع
IMG_SIZE = 224
BATCH_SIZE = 32
EPOCHS = 50  # زيادة عدد الحقب لتحسين التعلم بناء على طلب المستخدم
DATA_PATH = "dataset/data"
MODEL_PATH = "models/elderly_posture_model.h5"
LABEL_ENCODER_PATH = "models/label_encoder.pkl"

class PostureDetectionModel:
    def __init__(self):
        self.model = None
        self.label_encoder = LabelEncoder()
        # نستخدم الكلاسات بناء على الموجود في المجلدات
        self.classes = ['جالس', 'سقوط', 'ممدد', 'واقف']
        
        # قاموس لتحويل أسماء المجلدات الإنجليزية إلى الأسماء العربية المعتمدة
        self.folder_to_class = {
            'sitting': 'جالس',
            'standing': 'واقف',
            'lying': 'ممدد',
            'falling': 'سقوط'
        }
        
    def load_real_dataset(self):
        """تحميل البيانات الحقيقية من المجلدات"""
        print(f"🖼️ جاري قراءة الصور الحقيقية من المجلد: {DATA_PATH} ...")
        
        images = []
        labels = []
        
        if not os.path.exists(DATA_PATH):
            print(f"❌ لم يتم العثور على المسار: {DATA_PATH}")
            return np.array([]), np.array([])

        for folder_name in os.listdir(DATA_PATH):
            folder_path = os.path.join(DATA_PATH, folder_name)
            
            if not os.path.isdir(folder_path):
                continue
                
            # لو لم يكن الاسم مدعوماً في القاموس، استخدم الاسم نفسه
            class_name = self.folder_to_class.get(folder_name.lower(), folder_name)
            
            count = 0
            for img_name in os.listdir(folder_path):
                img_path = os.path.join(folder_path, img_name)
                
                try:
                    img = cv2.imread(img_path)
                    if img is None: continue
                    
                    # تغيير الحجم وتحويل الألوان للصيغة الصحيحة
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    img = cv2.resize(img, (IMG_SIZE, IMG_SIZE))
                    
                    # النورمالايزيشن
                    img_normalized = img / 255.0
                    
                    images.append(img_normalized)
                    labels.append(class_name)
                    count += 1
                except Exception as e:
                    pass
            print(f"✅ تم تحميل {count} صورة من مجلد '{folder_name}' -> '{class_name}'")
            
        return np.array(images), np.array(labels)
    
    def load_and_preprocess_data(self):
        """تحميل ومعالجة الصور للتدريب"""
        print("🖼️ جاري تحضير البيانات...")
        
        # تحميل البيانات الحقيقية بدلاً من الاصطناعية
        images, labels = self.load_real_dataset()
        
        if len(images) == 0:
            raise ValueError("لا يوجد صور صالحة للتدريب في مجلد dataset/data")
            
        print(f"📊 عدد الصور الكلي: {len(images)}")
        
        # تشفير التسميات بالأسماء المكتشفة فعلياً
        encoded_labels = self.label_encoder.fit_transform(labels)
        self.classes = self.label_encoder.classes_
        num_classes = len(self.classes)
        
        encoded_labels = keras.utils.to_categorical(encoded_labels, num_classes=num_classes)
        
        # إذا كانت البيانات قليلة جداً، قلل حجم الاختبار
        test_size = 0.2 if len(images) >= 10 else 0.5
        X_train, X_test, y_train, y_test = train_test_split(
            images, encoded_labels, test_size=test_size, random_state=42, stratify=labels
        )
        
        print(f"📊 عدد صور التدريب: {len(X_train)}")
        print(f"📊 عدد صور الاختبار: {len(X_test)}")
        
        return X_train, X_test, y_train, y_test
    
    def build_model(self):
        """بناء نموذج CNN"""
        print("\n🤖 جاري بناء النموذج...")
        
        base_model = keras.applications.MobileNetV2(
            input_shape=(IMG_SIZE, IMG_SIZE, 3),
            include_top=False,
            weights='imagenet'
        )
        
        # السماح بتدريب آخر 30 طبقة من MobileNetV2 لتحسين الدقة (Fine-tuning)
        base_model.trainable = True
        for layer in base_model.layers[:-30]:
            layer.trainable = False
        
        self.model = models.Sequential([
            base_model,
            layers.GlobalAveragePooling2D(),
            layers.Dense(512, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.5),
            layers.Dense(256, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.4),
            layers.Dense(128, activation='relu'),
            layers.Dropout(0.3),
            layers.Dense(len(self.classes), activation='softmax')
        ])
        
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.0001), # تعلم أبطأ للفاين-تيونينج
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        print("✅ تم بناء النموذج بنجاح")
    
    def train(self, X_train, X_test, y_train, y_test):
        """تدريب النموذج"""
        print("\n⚡ جاري تدريب النموذج...")
        
        # تحسين التدريب على الصور بشكل أكبر بإضافة المزيد من التعديلات (Data Augmentation) لتشمل تغييرات تشبه إطارات الفيديو
        data_augmentation = ImageDataGenerator(
            rotation_range=30,
            width_shift_range=0.2,
            height_shift_range=0.2,
            horizontal_flip=True,
            vertical_flip=False,
            zoom_range=0.3, # تقليل التقريب المفرط الذي قد يشوه الصورة
            shear_range=0.2,
            brightness_range=[0.5, 1.5], # مدى أوسع للإضاءة لمحاكاة الفيديوهات بشكل أفضل
            channel_shift_range=20.0, # تعديل في الألوان لاختلاف الكاميرات
            fill_mode='nearest'
        )
        
        history = self.model.fit(
            data_augmentation.flow(X_train, y_train, batch_size=BATCH_SIZE),
            epochs=EPOCHS,
            validation_data=(X_test, y_test),
            steps_per_epoch=len(X_train) // BATCH_SIZE,
            verbose=1
        )
        
        test_loss, test_accuracy = self.model.evaluate(X_test, y_test)
        print(f"\n📈 دقة الاختبار: {test_accuracy * 100:.2f}%")
        print(f"📉 خسارة الاختبار: {test_loss:.4f}")
        
        return history
    
    def save_model(self):
        """حفظ النموذج والمشفر"""
        print("\n💾 جاري حفظ النموذج...")
        self.model.save(MODEL_PATH)
        with open(LABEL_ENCODER_PATH, 'wb') as f:
            pickle.dump(self.label_encoder, f)
        print(f"✅ تم حفظ النموذج في: {MODEL_PATH}")

def main():
    print("=" * 60)
    print("🏥 نظام تدريب نموذج مراقبة كبار السن")
    print("=" * 60)
    
    detector = PostureDetectionModel()
    
    X_train, X_test, y_train, y_test = detector.load_and_preprocess_data()
    
    detector.build_model()
    
    detector.train(X_train, X_test, y_train, y_test)
    
    detector.save_model()
    
    print("\n" + "=" * 60)
    print("✅ تم إكمال التدريب بنجاح!")
    print("=" * 60)

if __name__ == "__main__":
    main()