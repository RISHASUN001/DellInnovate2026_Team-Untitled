import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI')
DB_NAME = os.getenv('SCS_DB_NAME', 'dellinnovate')
#testing
print("="*60)
print("MongoDB Auto-Setup for SCS Youth Helper Dashboard")
print("="*60)
print(f"\nDatabase: {DB_NAME}")
print(f"Connecting to MongoDB Atlas...")

try:
    client = MongoClient(MONGODB_URI)
    # Test connection
    client.admin.command('ping')
    print("Connected successfully!\n")
except Exception as e:
    print(f"Connection failed: {e}")
    exit(1)
client = MongoClient(MONGODB_URI)

db = client[DB_NAME]

def setup_collections_and_indexes():
    """Create collections and indexes"""
    print("🔧 Setting up MongoDB collections and indexes...\n")
    
    # 1. SCS Users Collection
    users_col = db['scs_users']
    users_col.create_index([("user_id", ASCENDING)], unique=True)
    users_col.create_index([("role", ASCENDING)])
    users_col.create_index([("is_active", ASCENDING)])
    users_col.create_index([("email", ASCENDING)])
    print("✅ Created scs_users collection with indexes")
    
    # 2. SCS Cases Collection
    cases_col = db['scs_cases']
    cases_col.create_index([("case_id", ASCENDING)], unique=True)
    cases_col.create_index([("user_id", ASCENDING)])  # IG handle
    cases_col.create_index([("assigned_to", ASCENDING)])
    cases_col.create_index([("case_status", ASCENDING)])
    cases_col.create_index([("work_status", ASCENDING)])
    cases_col.create_index([("priority", ASCENDING)])
    cases_col.create_index([("created_at", DESCENDING)])
    cases_col.create_index([
        ("assigned_to", ASCENDING),
        ("case_status", ASCENDING),
        ("work_status", ASCENDING)
    ])
    print("✅ Created scs_cases collection with indexes")
    
    # 3. Case History Collection
    history_col = db['scs_case_history']
    history_col.create_index([("case_id", ASCENDING)])
    history_col.create_index([("ingestion_date", DESCENDING)])
    history_col.create_index([
        ("case_id", ASCENDING),
        ("ingestion_date", DESCENDING)
    ])
    print("✅ Created scs_case_history collection with indexes")
    
    # 4. Checklist Templates Collection
    templates_col = db['scs_checklist_templates']
    templates_col.create_index([("template_id", ASCENDING)], unique=True)
    templates_col.create_index([("is_active", ASCENDING)])
    templates_col.create_index([("display_order", ASCENDING)])
    print("✅ Created scs_checklist_templates collection with indexes")
    
    # 5. Checklist Collection
    checklist_col = db['scs_checklist']
    checklist_col.create_index([("checklist_item_id", ASCENDING)], unique=True)
    checklist_col.create_index([("case_id", ASCENDING)])
    checklist_col.create_index([("template_id", ASCENDING)])
    checklist_col.create_index([("is_mandatory", ASCENDING)])
    checklist_col.create_index([("completed", ASCENDING)])
    checklist_col.create_index([
        ("case_id", ASCENDING),
        ("is_mandatory", DESCENDING),
        ("display_order", ASCENDING)
    ])
    print("✅ Created scs_checklist collection with indexes")
    
    # 6. Review Requests Collection
    review_col = db['scs_review_requests']
    review_col.create_index([("review_id", ASCENDING)], unique=True)
    review_col.create_index([("case_id", ASCENDING)])
    review_col.create_index([("request_status", ASCENDING)])
    review_col.create_index([("requested_at", DESCENDING)])
    review_col.create_index([
        ("request_status", ASCENDING),
        ("requested_at", DESCENDING)
    ])
    print("✅ Created scs_review_requests collection with indexes")
    
    # 7. Reassignment Requests Collection
    reassign_col = db['scs_reassignment_requests']
    reassign_col.create_index([("request_id", ASCENDING)], unique=True)
    reassign_col.create_index([("case_id", ASCENDING)])
    reassign_col.create_index([("request_status", ASCENDING)])
    reassign_col.create_index([("requested_at", DESCENDING)])
    reassign_col.create_index([
        ("request_status", ASCENDING),
        ("requested_at", DESCENDING)
    ])
    print("✅ Created scs_reassignment_requests collection with indexes")
    
    print("\n✅ All collections and indexes created successfully!\n")

def get_next_sequence_id(collection_name, field_name):
    """Get next auto-increment ID (simulating MySQL auto_increment)"""
    counter_col = db['counters']
    result = counter_col.find_one_and_update(
        {'_id': f"{collection_name}_{field_name}"},
        {'$inc': {'seq': 1}},
        upsert=True,
        return_document=True
    )
    return result['seq']

if __name__ == "__main__":
    setup_collections_and_indexes()