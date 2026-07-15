"""Test script to verify template lookup error handling."""
import asyncio
import sys
sys.path.insert(0, '.')

from app.services.template_service import get_template, TemplateLookupError

async def test_template_lookup():
    """Test template lookup with non-existent template."""
    print("Testing template lookup with non-existent template...")
    
    try:
        result = await get_template("non_existent_template", "en")
        print(f"ERROR: Expected TemplateLookupError but got result: {result}")
    except TemplateLookupError as e:
        print(f"✓ TemplateLookupError raised as expected")
        print(f"  Error message: {str(e)}")
        return True
    except Exception as e:
        print(f"ERROR: Unexpected exception: {type(e).__name__}: {e}")
        return False

async def test_template_lookup_empty():
    """Test template lookup when no approved templates available."""
    print("\nTesting template lookup when no approved templates available...")
    
    # This will fail if there are no approved templates in the system
    try:
        result = await get_template("any_template", "en")
        print(f"Result: {result}")
        return True
    except TemplateLookupError as e:
        print(f"✓ TemplateLookupError raised: {str(e)}")
        return True
    except Exception as e:
        print(f"ERROR: Unexpected exception: {type(e).__name__}: {e}")
        return False

async def main():
    print("=" * 60)
    print("Template Lookup Error Handling Tests")
    print("=" * 60)
    
    test1 = await test_template_lookup()
    test2 = await test_template_lookup_empty()
    
    print("\n" + "=" * 60)
    if test1 and test2:
        print("✓ All tests passed")
    else:
        print("✗ Some tests failed")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
