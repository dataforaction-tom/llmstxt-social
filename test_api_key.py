"""Simple script to test Anthropic API key authentication."""

import os
import sys

try:
    from dotenv import load_dotenv
    from anthropic import Anthropic
except ImportError as e:
    print("❌ Missing required dependencies")
    print(f"   Error: {e}")
    print("\nPlease install dependencies:")
    print("   pip install python-dotenv anthropic")
    print("\nOr if using uv:")
    print("   uv pip install python-dotenv anthropic")
    sys.exit(1)

# Load environment variables
load_dotenv()

def test_api_key():
    """Test if the Anthropic API key is valid."""
    print("Testing Anthropic API key...\n")
    
    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not found in environment")
        print("\nPlease:")
        print("1. Create a .env file in the project root")
        print("2. Add: ANTHROPIC_API_KEY=sk-ant-your-key-here")
        return False
    
    # Check for common issues
    api_key_stripped = api_key.strip()
    if api_key != api_key_stripped:
        print("⚠️  WARNING: API key has leading/trailing whitespace")
        print(f"   Original length: {len(api_key)}")
        print(f"   Stripped length: {len(api_key_stripped)}")
        api_key = api_key_stripped
    
    if not api_key.startswith("sk-ant-"):
        print("⚠️  WARNING: API key doesn't start with 'sk-ant-'")
        print(f"   Starts with: {api_key[:10]}...")
    
    print(f"✓ API key found (length: {len(api_key)} characters)")
    print(f"  First 10 chars: {api_key[:10]}...")
    print()
    
    # Test API call
    try:
        print("Making test API call...")
        client = Anthropic(api_key=api_key)
        
        # Make a minimal API call
        message = client.messages.create(
            model="claude-3-haiku-20240307",  # Use cheapest model for testing
            max_tokens=10,
            messages=[
                {
                    "role": "user",
                    "content": "Say 'test'"
                }
            ]
        )
        
        response = message.content[0].text
        print(f"✓ API call successful!")
        print(f"  Response: {response}")
        print("\n✅ Your API key is valid and working!")
        return True
        
    except Exception as e:
        error_str = str(e)
        print(f"\n❌ API call failed!")
        print(f"   Error: {error_str}")
        
        if "401" in error_str or "authentication" in error_str.lower():
            print("\n🔍 Authentication Error - Possible issues:")
            print("   1. API key is incorrect or expired")
            print("   2. API key has extra characters or whitespace")
            print("   3. API key doesn't have proper permissions")
            print("\n💡 Try:")
            print("   1. Get a new API key from https://console.anthropic.com")
            print("   2. Make sure your .env file has: ANTHROPIC_API_KEY=sk-ant-...")
            print("   3. Check there are no quotes around the key in .env")
            print("   4. Restart your terminal/IDE after updating .env")
        elif "429" in error_str:
            print("\n⚠️  Rate limit error - API key is valid but you've hit rate limits")
        else:
            print(f"\n   Full error details: {e}")
        
        return False

if __name__ == "__main__":
    success = test_api_key()
    exit(0 if success else 1)
