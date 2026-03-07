import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

print("="*60)
print("🔍 MONGODB CONNECTION DIAGNOSTICS")
print("="*60)

MONGODB_URI = os.getenv('MONGODB_URI')
SCS_DB_NAME = os.getenv('SCS_DB_NAME', 'dellinnovate')

print(f"\n📍 MongoDB URI: {MONGODB_URI[:50]}...")
print(f"📍 SCS Database Name: {SCS_DB_NAME}")

try:
    print("\n🔗 Connecting to MongoDB...")
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    
    # Test connection
    client.admin.command('ping')
    print("✅ Connection successful!")
    
    # Get database
    db = client[SCS_DB_NAME]
    
    # List all databases
    print("\n📚 Available databases:")
    for db_name in client.list_database_names():
        print(f"  - {db_name}")
    
    # List collections in SCS database
    print(f"\n📦 Collections in '{SCS_DB_NAME}':")
    collections = db.list_collection_names()
    if collections:
        for coll in collections:
            count = db[coll].count_documents({})
            print(f"  - {coll}: {count} documents")
    else:
        print("  ⚠️  No collections found (database may not exist yet)")
    
    # Try inserting a test document
    print(f"\n🧪 Testing insert into '{SCS_DB_NAME}'...")
    test_col = db['_test_connection']
    result = test_col.insert_one({"test": "data", "timestamp": "now"})
    print(f"✅ Insert successful! ID: {result.inserted_id}")
    
    # Clean up test
    test_col.delete_one({"_id": result.inserted_id})
    print("✅ Test document cleaned up")
    
    # Now check again
    print(f"\n🔍 Collections after test:")
    collections = db.list_collection_names()
    if collections:
        for coll in collections:
            count = db[coll].count_documents({})
            print(f"  - {coll}: {count} documents")
    else:
        print("  ℹ️  Still no collections (test cleaned up)")
    
    print("\n" + "="*60)
    print("✅ DIAGNOSTICS COMPLETE - CONNECTION WORKS!")
    print("="*60)
    print("\nYou can now run: python3 database_setup/scs_seed.py")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()