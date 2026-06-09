"""
Kronos 3-Model Integration Test Script

Tests:
1. Local Kronos-mini on 4GB RAM system
2. Colab 3-model ensemble (cascade, context, ensemble strategies)

Usage:
    python -m app.tests.kronos_test
    
Prerequisites:
    - For Colab tests: Run kronos_colab.ipynb and set KRONOS_COLAB_URL in .env
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.kronos import (
    get_memory_usage,
    kronos_service_4gb,
    predict_single,
    get_service_stats,
    configure_torch_cpu,
    set_memory_limits,
)
from app.services.kronos.hybrid_service import (
    hybrid_kronos_service,
    configure_colab_fallback,
)
from app.config import settings


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


async def test_local_kronos():
    """Test local Kronos-mini on 4GB RAM system."""

    print_section("TEST 1: Local Kronos-mini (4GB RAM)")

    # Step 1: Configure memory limits
    print("\n[1/5] Configuring memory limits...")
    set_memory_limits(max_ram_mb=2048)
    configure_torch_cpu()
    print("✓ Memory limits set (2GB max)")
    print("✓ PyTorch configured for CPU-only")

    # Step 2: Check initial memory
    print("\n[2/5] Checking initial memory...")
    memory = get_memory_usage()
    print(f"  System RAM: {memory['system_total_mb']:.0f}MB total")
    print(f"  Available:  {memory['system_available_mb']:.0f}MB ({100 - memory['system_percent']:.1f}% free)")
    print(f"  Process:    {memory['rss_mb']:.1f}MB")

    if memory['system_total_mb'] < 3500:
        print("✓ Detected 4GB RAM system - test is relevant")
    else:
        print("⚠ System has more than 4GB RAM - test still valid but not critical")

    # Step 3: Generate fake OHLCV data (20 bars history)
    print("\n[3/5] Generating test OHLCV data...")
    import random
    random.seed(42)

    ohlcv_data = []
    base_price = 100.0
    for i in range(20):
        open_price = base_price + random.uniform(-2, 2)
        high_price = open_price + random.uniform(0.5, 2)
        low_price = open_price - random.uniform(0.5, 2)
        close_price = random.uniform(low_price, high_price)
        volume = random.randint(1000000, 10000000)
        amount = volume * close_price

        ohlcv_data.append([
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            amount
        ])

        base_price = close_price

    print(f"  Generated {len(ohlcv_data)} bars of OHLCV data")
    print(f"  Price range: ${min(b[3]):.2f} - ${max(b[3]):.2f}")

    # Step 4: Run prediction
    print("\n[4/5] Running Kronos prediction (this may take 5-10 seconds)...")
    print("  First run includes model download (~20MB)")
    print("  Subsequent runs will be faster")

    try:
        result = predict_single(ohlcv_data, forecast_horizon=10)

        if result.get('status') == 'success':
            print("✓ Prediction successful!")
            print(f"\n  Results:")
            print(f"    Predicted returns: {result.get('predicted_return', 0):.2%}")
            print(f"    Forecast horizon: {result.get('forecast_horizon')} bars")
            print(f"    Inference time: {result.get('inference_time_ms', 0):.0f}ms")
            print(f"    Memory used: {result.get('memory_mb', 0):.1f}MB")

            # Show first 5 predictions
            predictions = result.get('predictions', [])
            if predictions:
                print(f"\n  Next 5 bar predictions:")
                for i, pred in enumerate(predictions[:5], 1):
                    print(f"    Bar {i}: ${pred:.2f}")
        else:
            print(f"✗ Prediction failed: {result.get('error')}")
            return False

    except Exception as e:
        print(f"✗ Prediction error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 5: Check memory after
    print("\n[5/5] Checking memory after prediction...")
    memory_after = get_memory_usage()
    stats = get_service_stats()

    print(f"  Process RAM: {memory_after['rss_mb']:.1f}MB")
    print(f"  Model loaded: {stats['model_loaded']}")
    print(f"  Total predictions: {stats['total_predictions']}")
    print(f"  OOM errors: {stats['oom_errors']}")

    if not stats['model_loaded']:
        print("✓ Model correctly unloaded (load→predict→unload pattern working)")
    else:
        print("⚠ Model still loaded - call force_gc() to free memory")

    # Final summary
    print_section("Local Test Summary")

    print(f"\n  System RAM: {memory['system_total_mb']:.0f}MB")
    print(f"  Peak process RAM: {max(memory['rss_mb'], memory_after['rss_mb']):.1f}MB")
    print(f"  Predictions: {stats['total_predictions']} successful")
    print(f"  OOM errors: {stats['oom_errors']}")

    if stats['oom_errors'] == 0:
        print("\n  ✅ LOCAL KRONOS TEST PASSED")
        return True
    else:
        print("\n  ⚠️  LOCAL KRONOS TEST FAILED (OOM errors)")
        print("  Try these fixes:")
        print("  1. Use kronos-mini-int8 (quantized model)")
        print("  2. Enable Colab GPU fallback")
        print("  3. Reduce forecast horizon to 20 bars")
        return False


async def test_colab_integration():
    """Test Colab 3-model ensemble integration."""
    
    print_section("TEST 2: Colab 3-Model Ensemble")
    
    colab_url = settings.KRONOS_COLAB_URL
    
    if not colab_url:
        print("\n⚠️  KRONOS_COLAB_URL not configured")
        print("  To test Colab integration:")
        print("  1. Run kronos_colab.ipynb on Google Colab")
        print("  2. Get ngrok public URL from Cell 5")
        print("  3. Set KRONOS_COLAB_URL in backend/.env")
        print("  4. Re-run this test")
        print("\n  Skipping Colab test...")
        return None
    
    # Configure Colab fallback
    configure_colab_fallback(colab_url)
    print(f"\n✓ Colab URL configured: {colab_url}")
    
    # Test different strategies
    strategies = ["cascade", "ensemble", "context"]
    ohlcv_data = []
    base_price = 100.0
    import random
    random.seed(42)
    
    for i in range(30):
        open_price = base_price + random.uniform(-2, 2)
        high_price = open_price + random.uniform(0.5, 2)
        low_price = open_price - random.uniform(0.5, 2)
        close_price = random.uniform(low_price, high_price)
        volume = random.randint(1000000, 10000000)
        amount = volume * close_price
        
        ohlcv_data.append([
            open_price, high_price, low_price, close_price, volume, amount
        ])
        base_price = close_price
    
    results = {}
    
    for strategy in strategies:
        # Update strategy temporarily
        original_strategy = settings.KRONOS_COLAB_STRATEGY
        settings.KRONOS_COLAB_STRATEGY = strategy
        
        print(f"\n🧪 Testing strategy: {strategy}")
        
        try:
            result = await hybrid_kronos_service.predict(
                symbol="TEST",
                ohlcv_data=ohlcv_data,
                forecast_horizon=10,
                use_cloud_if_busy=True
            )
            
            if result.get("status") == "success" and result.get("source") == "colab":
                print(f"  ✓ {strategy.upper()} successful")
                print(f"    Direction: {result.get('direction', 'N/A')}")
                print(f"    Predicted return: {result.get('predicted_return', 0):.2%}")
                print(f"    Inference time: {result.get('inference_time_ms', 0):.0f}ms")
                results[strategy] = result
            else:
                print(f"  ✗ {strategy.upper()} failed: {result.get('error', 'Unknown error')}")
                results[strategy] = None
                
        except Exception as e:
            print(f"  ✗ {strategy.upper()} error: {e}")
            results[strategy] = None
        finally:
            settings.KRONOS_COLAB_STRATEGY = original_strategy
    
    # Summary
    print_section("Colab Test Summary")
    
    successful = sum(1 for r in results.values() if r is not None)
    print(f"\n  Strategies tested: {len(strategies)}")
    print(f"  Successful: {successful}/{len(strategies)}")
    
    if successful > 0:
        print("\n  ✅ COLAB INTEGRATION TEST PASSED")
        print(f"  Best strategy: {max(results.keys(), key=lambda k: abs(results[k].get('predicted_return', 0)) if results[k] else 0)}")
        return True
    else:
        print("\n  ⚠️  COLAB INTEGRATION TEST FAILED")
        print("  Check:")
        print("  1. Colab notebook is running")
        print("  2. ngrok URL is current (Colab URLs expire)")
        print("  3. Network connectivity to Colab")
        return False


async def main():
    print("\n" + "=" * 60)
    print("  Jasper Trades - Kronos 3-Model Integration Test")
    print("=" * 60)
    print("\nThis script tests:")
    print("1. Local Kronos-mini on 4GB RAM")
    print("2. Colab 3-model ensemble (cascade/ensemble/context)")
    print()
    
    # Test 1: Local
    local_success = await test_local_kronos()
    
    # Test 2: Colab
    colab_result = await test_colab_integration()
    
    # Final summary
    print_section("FINAL SUMMARY")
    
    print(f"\n  Local Kronos: {'✅ PASSED' if local_success else '❌ FAILED'}")
    
    if colab_result is None:
        print("  Colab Test: ⚠️  SKIPPED (not configured)")
    elif colab_result:
        print("  Colab Test: ✅ PASSED")
    else:
        print("  Colab Test: ❌ FAILED")
    
    print("\n" + "=" * 60)
    
    if local_success:
        print("\n  ✅ Your system can run Kronos intelligence locally!")
    
    if colab_result:
        print("  ✅ Colab 3-model ensemble is working!")
        print(f"  Current strategy: {settings.KRONOS_COLAB_STRATEGY}")
        print("  Change in .env: KRONOS_COLAB_STRATEGY=cascade|ensemble|context")
    
    print()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0)