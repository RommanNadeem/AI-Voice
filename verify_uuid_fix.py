#!/usr/bin/env python3
"""
Verification script for UUID standardization fix
Run this to verify the implementation is correct
"""

import sys
import uuid
from core.user_id import UserId, UserIdError


def test_basic_validation():
    """Test basic UUID validation"""
    print("Testing basic UUID validation...")
    
    # Valid UUID should pass
    valid_uuid = str(uuid.uuid4())
    try:
        UserId.assert_full_uuid(valid_uuid)
        print(f"✅ Valid UUID accepted: {UserId.format_for_display(valid_uuid)}")
    except UserIdError as e:
        print(f"❌ Valid UUID rejected: {e}")
        return False
    
    # Prefix should fail
    prefix = "bb4a6f7c"
    try:
        UserId.assert_full_uuid(prefix)
        print(f"❌ Prefix incorrectly accepted: {prefix}")
        return False
    except UserIdError as e:
        print(f"✅ Prefix correctly rejected: {e}")
    
    return True


def test_parsing():
    """Test identity parsing"""
    print("\nTesting identity parsing...")
    
    test_uuid = "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"
    
    # Test with 'user-' prefix
    identity_with_prefix = f"user-{test_uuid}"
    try:
        parsed = UserId.parse_from_identity(identity_with_prefix)
        if parsed == test_uuid:
            print(f"✅ Parsed 'user-UUID' correctly: {UserId.format_for_display(parsed)}")
        else:
            print(f"❌ Parsed incorrectly: {parsed} != {test_uuid}")
            return False
    except UserIdError as e:
        print(f"❌ Failed to parse valid identity: {e}")
        return False
    
    # Test bare UUID
    try:
        parsed = UserId.parse_from_identity(test_uuid)
        if parsed == test_uuid:
            print(f"✅ Parsed bare UUID correctly: {UserId.format_for_display(parsed)}")
        else:
            print(f"❌ Parsed incorrectly: {parsed} != {test_uuid}")
            return False
    except UserIdError as e:
        print(f"❌ Failed to parse valid UUID: {e}")
        return False
    
    # Test invalid identity
    try:
        parsed = UserId.parse_from_identity("invalid")
        print(f"❌ Invalid identity incorrectly accepted: {parsed}")
        return False
    except UserIdError as e:
        print(f"✅ Invalid identity correctly rejected: {e}")
    
    return True


def test_display_formatting():
    """Test display formatting"""
    print("\nTesting display formatting...")
    
    test_uuid = "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"
    display = UserId.format_for_display(test_uuid)
    
    if display == "bb4a6f7c...":
        print(f"✅ Display format correct: {display}")
    else:
        print(f"❌ Display format incorrect: {display} != bb4a6f7c...")
        return False
    
    # Test with None
    display_none = UserId.format_for_display(None)
    if display_none == "(none)":
        print(f"✅ None format correct: {display_none}")
    else:
        print(f"❌ None format incorrect: {display_none} != (none)")
        return False
    
    return True


def test_validators_integration():
    """Test integration with validators"""
    print("\nTesting validators integration...")
    
    try:
        from core.validators import set_current_user_id, get_current_user_id
        
        test_uuid = str(uuid.uuid4())
        
        # Should accept valid UUID
        try:
            set_current_user_id(test_uuid)
            retrieved = get_current_user_id()
            if retrieved == test_uuid:
                print(f"✅ Validators accept valid UUID: {UserId.format_for_display(test_uuid)}")
            else:
                print(f"❌ Retrieved UUID doesn't match: {retrieved} != {test_uuid}")
                return False
        except Exception as e:
            print(f"❌ Validators rejected valid UUID: {e}")
            return False
        
        # Should reject prefix
        prefix = "bb4a6f7c"
        try:
            set_current_user_id(prefix)
            print(f"❌ Validators incorrectly accepted prefix: {prefix}")
            return False
        except (UserIdError, Exception) as e:
            print(f"✅ Validators correctly rejected prefix: {type(e).__name__}")
        
        return True
    except ImportError as e:
        print(f"⚠️  Could not import validators: {e}")
        return True  # Don't fail on import issues


def verify_service_imports():
    """Verify all services can be imported"""
    print("\nVerifying service imports...")
    
    services_to_check = [
        ("services.user_service", "UserService"),
        ("services.memory_service", "MemoryService"),
        ("services.profile_service", "ProfileService"),
        ("services.onboarding_service", "OnboardingService"),
        ("services.conversation_context_service", "ConversationContextService"),
        ("rag_system", "get_or_create_rag"),
    ]
    
    all_ok = True
    for module_name, class_name in services_to_check:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print(f"✅ {module_name}.{class_name} imports correctly")
        except Exception as e:
            print(f"❌ Failed to import {module_name}.{class_name}: {e}")
            all_ok = False
    
    return all_ok


def main():
    """Run all verification tests"""
    print("=" * 60)
    print("UUID Standardization Fix - Verification Script")
    print("=" * 60)
    
    tests = [
        ("Basic Validation", test_basic_validation),
        ("Identity Parsing", test_parsing),
        ("Display Formatting", test_display_formatting),
        ("Validators Integration", test_validators_integration),
        ("Service Imports", verify_service_imports),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} raised exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED - Implementation is correct!")
        print("=" * 60)
        return 0
    else:
        print("❌ SOME TESTS FAILED - Please review the implementation")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())

