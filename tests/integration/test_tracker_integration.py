#!/usr/bin/env python3
"""
Test script for cvgorod-hub integrations:
- Yandex Tracker
- Perplexity
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project and MCP paths
project_root = Path(__file__).parent
mcp_path = Path("/Users/danielbadygov/MCP")

sys.path.insert(0, str(project_root))
sys.path.insert(0, str(mcp_path))

from dotenv import load_dotenv

# Load environment
load_dotenv(project_root / ".env.dev")


def test_secrets():
    """Test that secrets are loaded correctly."""
    print("=" * 60)
    print("TEST 1: Secrets Loading")
    print("=" * 60)
    
    secrets_to_check = [
        ("TRACKER_TOKEN", "Yandex Tracker"),
        ("TRACKER_ORG_ID", "Yandex Tracker Org ID"),
        ("PERPLEXITY_API_KEY", "Perplexity"),
        ("DEEPSEEK_API_KEY", "DeepSeek"),
        ("TELEGRAM_BOT_TOKEN", "Telegram"),
    ]
    
    all_ok = True
    for env_var, name in secrets_to_check:
        value = os.getenv(env_var)
        if value:
            # Mask value for security
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print(f"  [OK] {name}: {masked}")
        else:
            print(f"  [MISSING] {name}: {env_var} not set")
            all_ok = False
    
    return all_ok


def test_tracker_import():
    """Test that tracker module imports correctly."""
    print("\n" + "=" * 60)
    print("TEST 2: Tracker Module Import")
    print("=" * 60)
    
    try:
        from MCP.shared.tracker_events import TrackerEvents, PROJECT_QUEUES
        
        print(f"  [OK] TrackerEvents imported successfully")
        print(f"  [OK] PROJECT_QUEUES has {len(PROJECT_QUEUES)} mappings")
        
        # Check cvgorod-hub mapping
        if "cvgorod" in PROJECT_QUEUES:
            print(f"  [OK] cvgorod maps to queue: {PROJECT_QUEUES['cvgorod']}")
        else:
            print(f"  [WARN] cvgorod not in PROJECT_QUEUES, using default")
        
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to import tracker: {e}")
        return False


def test_tracker_instantiation():
    """Test that tracker can be instantiated."""
    print("\n" + "=" * 60)
    print("TEST 3: Tracker Instantiation")
    print("=" * 60)
    
    try:
        from services.tracker import tracker
        
        print(f"  [OK] Project: {tracker.project}")
        print(f"  [OK] Component: {tracker.component}")
        print(f"  [OK] Enabled: {tracker.enabled}")
        print(f"  [OK] Queue: {tracker.queue}")
        
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to instantiate tracker: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_tracker_api():
    """Test Yandex Tracker API connection."""
    print("\n" + "=" * 60)
    print("TEST 4: Yandex Tracker API")
    print("=" * 60)
    
    try:
        from MCP.shared.tracker_events import TrackerEvents
        
        tracker = TrackerEvents(
            project="cvgorod-hub",
            component="Hub",
            enabled=True,
        )
        
        # Test API connection
        print("  [INFO] Testing API connection...")
        
        async with tracker._get_client() as client:
            response = await client.get(
                f"{tracker.BASE_URL}/myself",
                headers=tracker._get_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  [OK] API connected successfully")
                print(f"  [OK] User: {data.get('display', 'Unknown')}")
                print(f"  [OK] Organization: {tracker.org_id}")
                return True
            else:
                print(f"  [ERROR] API returned status {response.status_code}")
                print(f"  [ERROR] {response.text[:200]}")
                return False
                
    except Exception as e:
        print(f"  [ERROR] API test failed: {e}")
        return False


async def test_perplexity_api():
    """Test Perplexity API connection."""
    print("\n" + "=" * 60)
    print("TEST 5: Perplexity API")
    print("=" * 60)
    
    try:
        from MCP.shared.perplexity_client import PerplexityClient
        
        if not os.getenv("PERPLEXITY_API_KEY"):
            print("  [SKIP] PERPLEXITY_API_KEY not set")
            return True
        
        print("  [INFO] Testing Perplexity API connection...")
        
        async with PerplexityClient() as pplx:
            # Simple search test
            result = await pplx.search("тест сообщение")
            
            print(f"  [OK] API connected successfully")
            print(f"  [OK] Model: {result.model}")
            print(f"  [OK] Answer length: {len(result.answer)} chars")
            print(f"  [OK] Sources: {len(result.sources)}")
            
            return True
                
    except Exception as e:
        print(f"  [ERROR] Perplexity test failed: {e}")
        return False


async def test_tracker_events():
    """Test creating tracker events."""
    print("\n" + "=" * 60)
    print("TEST 6: Tracker Events")
    print("=" * 60)
    
    try:
        from services.tracker import tracker, log_telegram_message
        
        # Test info event (creates comment if issue exists, logs locally)
        print("  [INFO] Testing info event...")
        
        result = await tracker.info(
            summary="Test event from cvgorod-hub",
            data={
                "test": True,
                "environment": os.getenv("ENVIRONMENT", "development"),
            },
        )
        
        print(f"  [OK] Info event created")
        print(f"  [OK] Issue key: {result.get('issue_key', 'N/A')}")
        
        return True
                
    except Exception as e:
        print(f"  [ERROR] Tracker events test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_tracker_helpers():
    """Test tracker helper functions."""
    print("\n" + "=" * 60)
    print("TEST 7: Tracker Helpers")
    print("=" * 60)
    
    try:
        from services.tracker import (
            log_telegram_message,
            log_database_operation,
            log_api_error,
        )
        
        # Test helpers (they should log without errors)
        print("  [INFO] Testing log_telegram_message...")
        await log_telegram_message(
            chat_id=12345,
            message_type="text",
            has_intent=True,
            intent_type="question",
        )
        print("  [OK] log_telegram_message works")
        
        print("  [INFO] Testing log_database_operation...")
        await log_database_operation(
            operation="test_operation",
            table="test_table",
            success=True,
            duration_ms=50,
        )
        print("  [OK] log_database_operation works")
        
        print("  [INFO] Testing log_api_error...")
        await log_api_error(
            endpoint="/api/v1/test",
            error="Test error message",
            status_code=500,
        )
        print("  [OK] log_api_error works")
        
        return True
                
    except Exception as e:
        print(f"  [ERROR] Tracker helpers test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("CVGOROD-HUB INTEGRATION TESTS")
    print("=" * 60)
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print()
    
    results = {}
    
    # Synchronous tests
    results["secrets"] = test_secrets()
    results["tracker_import"] = test_tracker_import()
    results["tracker_instance"] = test_tracker_instantiation()
    
    # Async tests
    results["tracker_api"] = await test_tracker_api()
    results["perplexity_api"] = await test_perplexity_api()
    results["tracker_events"] = await test_tracker_events()
    results["tracker_helpers"] = await test_tracker_helpers()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        icon = "[OK]" if result else "[FAIL]"
        print(f"  {icon} {test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print()
    print(f"Total: {passed + failed} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()
    
    if failed == 0:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
