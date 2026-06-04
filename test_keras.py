import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
try:
    import tensorflow as tf
    print(f"TensorFlow version: {tf.__version__}")
    print(f"Keras version: {tf.keras.__version__}")
except Exception as e:
    print(f"tf.keras failed: {e}")

try:
    import keras
    print(f"Standalone Keras version: {keras.__version__}")
except Exception as e:
    print(f"Standalone keras failed: {e}")
