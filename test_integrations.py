#!/usr/bin/env python3
"""
Simple test script for cvgorod-hub integrations.
"""

import asyncio
import os
import sys
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent
# Use MCP_PATH env var, or default to ~/MCP
MCP_PATH = Path(os.getenv("MCP_PATH", str(Path.home() / "MCP")))

# Add paths to sys.path for imports
for p in [str(PROJECT_ROOT), str(MCP_PATH)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Load dotenv
from dotenv import load_dotenv
load_dotenv(str(PROJECT_ROOT / ".env.dev"), override=False)

# Load secrets
from dotenv import load_dotenv as load_dotenv_local

secrets_dir = Path("/Users/danielbadygov/.secrets")
for env_file in [
    secrets_dir / "cloud" / "yandex-tracker.env",
    secrets_dir / "cloud" / "perplexity.env",
    secrets_dir / "cloud" / "deepseek.env",
    secrets_dir / "telegram" / "cvgorod.env",
]:
    if env_file.exists():
        load_dotenv_local(str(env_file), override=True)
        print(f"Loaded: {env_file.name}")


print("\n" + "=" * 60)
print("CVGOROD-HUB INTEGRATION TESTS")
print("=" * 60)


def check_env_vars():
    """Check environment variables."""
    print("\n[1] Environment Variables")
    
    env_vars = [
        ("TRACKER_TOKEN", "Yandex Tracker Token"),
        ("TRACKER_ORG_ID", "Yandex Tracker Org ID"),
        ("PERPLEXITY_API_KEY", "Perplexity API Key"),
        ("DEEPSEEK_API_KEY", "DeepSeek API Key"),
        ("TELEGRAM_BOT_TOKEN", "Telegram Bot Token"),
    ]
    
    results = []
    for var, name in env_vars:
        value = os.getenv(var)
        if value:
            masked = value[:8] + "..." if len(value) > 8 else "***"
            print(f"  [OK] {name}: {masked}")
            results.append(True)
        else:
            print(f"  [MISSING] {name} ({var})")
            results.append(False)
    
    return all(results)


def test_shared_modules():
    """Test shared modules import."""
    print("\n[2] Shared Modules Import")
    
    try:
        from shared.tracker_events import TrackerEvents, PROJECT_QUEUES
        print(f"  [OK] TrackerEvents imported")
        print(f"  [OK] PROJECT_QUEUES: {len(PROJECT_QUEUES)} entries")
        
        # Check cvgorod mapping
        if "cvgorod" in PROJECT_QUEUES:
            print(f"  [OK] cvgorod -> {PROJECT_QUEUES['cvgorod']}")
        else:
            print(f"  [INFO] cvgorod uses default queue")
        
        return True
    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tracker_service():
    """Test local tracker service."""
    print("\n[3] Local Tracker Service")
    
    try:
        # Force reload
        modules_to_remove = [k for k in sys.modules.keys() if "tracker" in k.lower()]
        for m in modules_to_remove:
            del sys.modules[m]
        
        from services.tracker import tracker
        
        print(f"  [OK] Project: {tracker.project}")
        print(f"  [OK] Component: {tracker.component}")
        print(f"  [OK] Enabled: {tracker.enabled}")
        print(f"  [OK] Queue: {tracker.queue}")
        
        return True
    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_tracker_api():
    """Test Yandex Tracker API."""
    print("\n[4] Yandex Tracker API")
    
    try:
        import httpx
        
        token = os.getenv("TRACKER_TOKEN")
        org_id = os.getenv("TRACKER_ORG_ID")
        
        if not token or not org_id:
            print("  [SKIP] TRACKER_TOKEN or TRACKER_ORG_ID not set")
            return True
        
        headers = {
            "Authorization": f"OAuth {token}",
            "X-Cloud-Org-Id": org_id,
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://api.tracker.yandex.net/v2/myself",
                headers=headers,
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  [OK] API connected")
                print(f"  [OK] User: {data.get('display', 'Unknown')}")
                return True
            else:
                print(f"  [ERROR] Status: {response.status_code}")
                print(f"  [ERROR] {response.text[:200]}")
                return False
                
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


async def test_tracker_events():
    """Test tracker event creation."""
    print("\n[5] Tracker Events")
    
    try:
        # Force reload
        modules_to_remove = [k for k in sys.modules.keys() if "tracker" in k.lower()]
        for m in modules_to_remove:
            del sys.modules[m]
        
        from services.tracker import tracker, log_telegram_message, log_database_operation
        
        # Test info event (returns bool for local logging)
        result = await tracker.info(
            summary="Test event from cvgorod-hub integration test",
            data={"test": True},
        )
        
        print(f"  [OK] Info event logged: {result}")
        
        # Test log_telegram_message helper
        await log_telegram_message(
            chat_id=123456,
            message_type="text",
            has_intent=True,
            intent_type="order",
        )
        print(f"  [OK] log_telegram_message works")
        
        # Test log_database_operation helper
        await log_database_operation(
            operation="test_save",
            table="messages",
            success=True,
            duration_ms=42,
        )
        print(f"  [OK] log_database_operation works")
        
        return True
                
    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_perplexity():
    """Test Perplexity API."""
    print("\n[6] Perplexity API")
    
    if not os.getenv("PERPLEXITY_API_KEY"):
        print("  [SKIP] PERPLEXITY_API_KEY not set")
        return True
    
    try:
        from shared.perplexity_client import PerplexityClient
        
        async with PerplexityClient() as pplx:
            result = await pplx.search("цветы тюльпаны цена")
            
            print(f"  [OK] API connected")
            print(f"  [OK] Model: {result.model}")
            print(f"  [OK] Sources: {len(result.sources)}")
            
            return True
                
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


async def main():
    """Run all tests."""
    results = {}
    
    results["env_vars"] = check_env_vars()
    results["shared_modules"] = test_shared_modules()
    results["tracker_service"] = test_tracker_service()
    results["tracker_api"] = await test_tracker_api()
    results["tracker_events"] = await test_tracker_events()
    results["perplexity"] = await test_perplexity()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    
    for name, result in results.items():
        icon = "[OK]" if result else "[FAIL]"
        print(f"  {icon} {name}")
    
    print(f"\nPassed: {passed}/{len(results)}")
    
    if failed == 0:
        print("\nAll integration tests passed!")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
