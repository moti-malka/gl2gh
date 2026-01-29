"""
Test script to verify the platform foundation is working correctly

This should be run inside the Docker container:
    docker-compose exec backend python /app/../test_foundation.py

Or from the host (if dependencies installed):
    python test_foundation.py
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_imports():
    """Test that all core modules can be imported"""
    print("Testing imports...")
    
    try:
        from app.config import settings
        print(f"  ✓ Config loaded: {settings.APP_NAME}")
    except Exception as e:
        print(f"  ✗ Config import failed: {e}")
        return False
    
    try:
        from app.models import User, MigrationProject, MigrationRun
        print("  ✓ Models imported successfully")
    except Exception as e:
        print(f"  ✗ Models import failed: {e}")
        return False
    
    try:
        from app.utils import encrypt_token, decrypt_token, mask_sensitive_data
        print("  ✓ Utils imported successfully")
    except Exception as e:
        print(f"  ✗ Utils import failed: {e}")
        return False
    
    try:
        from app.workers.celery_app import celery_app
        print("  ✓ Celery app imported successfully")
    except Exception as e:
        print(f"  ✗ Celery import failed: {e}")
        return False
    
    return True


def test_encryption():
    """Test token encryption/decryption"""
    print("\nTesting encryption...")
    
    try:
        from app.utils import encrypt_token, decrypt_token
        
        # Override APP_MASTER_KEY for testing
        os.environ['APP_MASTER_KEY'] = 'test-master-key-for-unit-tests-only'
        
        test_token = "glpat-test123456789"
        encrypted = encrypt_token(test_token)
        decrypted = decrypt_token(encrypted)
        
        if decrypted == test_token:
            print(f"  ✓ Encryption/decryption working")
            return True
        else:
            print(f"  ✗ Encryption failed: {decrypted} != {test_token}")
            return False
    except Exception as e:
        print(f"  ✗ Encryption test failed: {e}")
        return False


def test_masking():
    """Test sensitive data masking"""
    print("\nTesting secret masking...")
    
    try:
        from app.utils import mask_sensitive_data
        
        test_cases = [
            ("glpat-xxxxxxxxxxxxxxxxxxxx", "glpat-****"),
            ("Bearer ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "Bearer ****"),
            ("Token: github_pat_xxxxx", "Token: github_pat_****"),
        ]
        
        all_passed = True
        for input_text, expected_pattern in test_cases:
            masked = mask_sensitive_data(input_text)
            if expected_pattern in masked:
                print(f"  ✓ Masked: {input_text[:20]}... -> {masked[:30]}...")
            else:
                print(f"  ✗ Masking failed for: {input_text}")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"  ✗ Masking test failed: {e}")
        return False


def test_pydantic_models():
    """Test Pydantic model creation"""
    print("\nTesting Pydantic models...")
    
    try:
        from app.models import MigrationProject, ProjectSettings
        from datetime import datetime
        from bson import ObjectId
        
        # Create a test project
        project = MigrationProject(
            name="Test Project",
            created_by=ObjectId(),
            settings=ProjectSettings()
        )
        
        if project.name == "Test Project":
            print(f"  ✓ Project model created successfully")
        
        # Test JSON serialization
        json_data = project.model_dump(mode='json')
        if 'name' in json_data:
            print(f"  ✓ Model serialization working")
        
        return True
    except Exception as e:
        print(f"  ✗ Model test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("gl2gh Platform Foundation Tests")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Encryption", test_encryption()))
    results.append(("Masking", test_masking()))
    results.append(("Models", test_pydantic_models()))
    
    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All foundation tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
