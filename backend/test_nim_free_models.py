"""
Test which NVIDIA NIM models are actually FREE (no billing required).
"""
import requests
from concurrent.futures import ThreadPoolExecutor

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"

# Models to test - focusing on reasoning/chat models
TEST_MODELS = [
    # Meta Llama (often have free tier)
    "meta/llama-3.2-3b-instruct",
    "meta/llama-3.1-8b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.2-1b-instruct",
    
    # Microsoft Phi
    "microsoft/phi-3.5-moe-instruct",
    "microsoft/phi-4-mini-instruct",
    
    # Mistral
    "mistralai/mistral-7b-instruct-v0.3",
    "mistralai/mistral-large-2-instruct",
    "mistralai/mixtral-8x7b-instruct-v0.1",
    "nv-mistralai/mistral-nemo-12b-instruct",
    
    # NVIDIA Nemotron
    "nvidia/nemotron-mini-4b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/nemotron-3-ultra-550b-a55b",  # Requested
    "nvidia/nemotron-4-340b-instruct",
    
    # Moonshot AI
    "moonshotai/kimi-k2.6",  # Requested
    
    # IBM Granite (often free for dev)
    "ibm/granite-3.0-8b-instruct",
    "ibm/granite-34b-code-instruct",
    
    # Others
    "databricks/dbrx-instruct",
    "deepseek-ai/deepseek-coder-6.7b-instruct",
]

def test_model(model_id):
    """Test if a model is accessible (free or paid)."""
    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 10
            },
            timeout=15
        )
        
        if response.status_code == 200:
            return (model_id, "✅ WORKS", "")
        elif response.status_code == 402:
            return (model_id, "💰 PAID", "Payment required")
        elif response.status_code == 401:
            return (model_id, "❌ AUTH", "Unauthorized")
        elif response.status_code == 404:
            return (model_id, "❌ NOT FOUND", "Model not found")
        else:
            return (model_id, f"⚠️ {response.status_code}", response.text[:100])
    except Exception as e:
        return (model_id, f"❌ ERROR", str(e)[:100])

print("=" * 100)
print("TESTING NVIDIA NIM MODEL ACCESS (FREE vs PAID)")
print("=" * 100)
print()

# Test all models in parallel
with ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(test_model, TEST_MODELS))

# Categorize results
working = [r for r in results if "✅" in r[1]]
paid = [r for r in results if "💰" in r[1]]
errors = [r for r in results if "❌" in r[1] or "⚠️" in r[1]]

print("✅ WORKING MODELS (can use now):")
for model, status, _ in working:
    print(f"   {model}")

print()
print("💰 PAID MODELS (require billing):")
for model, status, reason in paid:
    print(f"   {model} - {reason}")

print()
print("⚠️ ERRORS:")
for model, status, reason in errors:
    print(f"   {model}: {reason}")

print()
print("=" * 100)
print("RECOMMENDED FREE TIER CONFIG:")
print("=" * 100)
if working:
    fast = next((m[0] for m in working if "3b" in m[0] or "1b" in m[0] or "mini" in m[0]), "meta/llama-3.2-3b-instruct")
    smart = next((m[0] for m in working if "70b" in m[0] or "34b" in m[0]), "meta/llama-3.1-70b-instruct")
    alternative = next((m[0] for m in working if "mistral" in m[0] or "nemotron" in m[0]), working[0][0] if working else "meta/llama-3.2-3b-instruct")
    
    print(f"""
# In backend/app/config.py:
MODEL_FAST = "{fast}"
MODEL_BALANCED = "meta/llama-3.1-8b-instruct"  # Test this separately
MODEL_SMART_FREE = "{smart}"
MODEL_ALTERNATIVE = "{alternative}"
""")
else:
    print("⚠️ No models working - check API key!")

print("=" * 100)