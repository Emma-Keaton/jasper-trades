import sys
import os
sys.path.append('E:\Projects\jasper-trades\backend')
from app.config import Settings

print("Current working directory:", os.getcwd())
print("Looking for .env in:", os.path.join(os.getcwd(), '.env'))
print("Exists?", os.path.exists(os.path.join(os.getcwd(), '.env')))

settings = Settings()
print("\nInstance values:")
print("settings.MODEL_FAST:", settings.MODEL_FAST)
print("settings.MODEL_FREE_FAST:", settings.MODEL_FREE_FAST)
print("settings.MODEL_BALANCED:", settings.MODEL_BALANCED)
print("settings.MODEL_SMART:", settings.MODEL_SMART)
print("settings.MODEL_SMART_FREE:", settings.MODEL_SMART_FREE)
print("settings.MODEL_DEEP:", settings.MODEL_DEEP)
print("settings.MODEL_ALTERNATIVE:", settings.MODEL_ALTERNATIVE)
print("settings.NVIDIA_API_KEY:", settings.NVIDIA_API_KEY)