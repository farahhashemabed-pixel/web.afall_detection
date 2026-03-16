import pickle
import os

LABEL_ENCODER_PATH = r"c:\Users\farah\OneDrive\Desktop\web_fall\models\label_encoder.pkl"
if os.path.exists(LABEL_ENCODER_PATH):
    with open(LABEL_ENCODER_PATH, 'rb') as f:
        le = pickle.load(f)
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print(f"Classes in label encoder: {le.classes_}")
else:
    print("Label encoder not found")
