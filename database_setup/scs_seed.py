print("="*60)
print("🚀 SEED SCRIPT STARTING...")
print("="*60)

import os
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

print("✅ Imports successful")

load_dotenv()
print("✅ .env loaded")

MONGODB_URI = os.getenv('MONGODB_URI')
DB_NAME = os.getenv('SCS_DB_NAME', 'dellinnovate')

print(f"📍 Database: {DB_NAME}")
print(f"📍 URI exists: {bool(MONGODB_URI)}")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

print("✅ MongoDB client created\n")

def get_next_id(collection_name, field_name):
    """Auto-increment ID generator"""
    counter_col = db['counters']
    result = counter_col.find_one_and_update(
        {'_id': f"{collection_name}_{field_name}"},
        {'$inc': {'seq': 1}},
        upsert=True,
        return_document=True
    )
    return result['seq']

def seed_users():
    """Seed users collection"""
    users_col = db['scs_users']
    users_col.delete_many({})  # Clean slate
    
    users = [
        {
            "user_id": "admin_001",
            "username": "Admin Sarah",
            "role": "admin",
            "email": "sarah.admin@example.com",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        },
        {
            "user_id": "admin_002",
            "username": "Admin Mike",
            "role": "admin",
            "email": "mike.admin@example.com",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        },
        {
            "user_id": "helper_001",
            "username": "Alex Johnson",
            "role": "youth_helper",
            "email": "alex.johnson@example.com",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        },
        {
            "user_id": "helper_002",
            "username": "Maya Patel",
            "role": "youth_helper",
            "email": "maya.patel@example.com",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        },
        {
            "user_id": "helper_003",
            "username": "Jordan Lee",
            "role": "youth_helper",
            "email": "jordan.lee@example.com",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        },
        {
            "user_id": "helper_004",
            "username": "Sam Rivera",
            "role": "youth_helper",
            "email": "sam.rivera@example.com",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        },
        {
            "user_id": "helper_005",
            "username": "Casey Wong",
            "role": "youth_helper",
            "email": "casey.wong@example.com",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
    ]
    
    result = users_col.insert_many(users)
    print(f"✅ Seeded {len(result.inserted_ids)} users")

def seed_checklist_templates():
    """Seed mandatory checklist templates"""
    templates_col = db['scs_checklist_templates']
    templates_col.delete_many({})
    
    templates = [
        {
            "template_id": 1,
            "label": "Case Analysis Completed",
            "is_mandatory": True,
            "display_order": 1,
            "is_active": True,
            "created_at": datetime.now()
        },
        {
            "template_id": 2,
            "label": "Outreach Attempted",
            "is_mandatory": True,
            "display_order": 2,
            "is_active": True,
            "created_at": datetime.now()
        },
        {
            "template_id": 3,
            "label": "Response Received",
            "is_mandatory": True,
            "display_order": 3,
            "is_active": True,
            "created_at": datetime.now()
        },
        {
            "template_id": 4,
            "label": "Follow-up Scheduled",
            "is_mandatory": True,
            "display_order": 4,
            "is_active": True,
            "created_at": datetime.now()
        }
    ]
    
    result = templates_col.insert_many(templates)
    print(f"✅ Seeded {len(result.inserted_ids)} checklist templates")

def create_case_with_checklist_and_history(case_data):
    """Helper function to create case with checklist and initial history"""
    cases_col = db['scs_cases']
    checklist_col = db['scs_checklist']
    history_col = db['scs_case_history']
    templates_col = db['scs_checklist_templates']
    
    # Insert case
    case_data['created_at'] = datetime.now()
    case_data['updated_at'] = datetime.now()
    cases_col.insert_one(case_data)
    
    # Create mandatory checklist items
    templates = templates_col.find({'is_active': True}).sort('display_order', 1)
    for template in templates:
        checklist_item = {
            "checklist_item_id": get_next_id('scs_checklist', 'checklist_item_id'),
            "case_id": case_data['case_id'],
            "template_id": template['template_id'],
            "label": template['label'],
            "is_mandatory": template['is_mandatory'],
            "completed": False,
            "comments": [],
            "completed_at": None,
            "completed_by": None,
            "display_order": template['display_order'],
            "created_at": datetime.now()
        }
        checklist_col.insert_one(checklist_item)
    
    # Create initial history entry
    history_entry = {
        "history_id": get_next_id('scs_case_history', 'history_id'),
        "case_id": case_data['case_id'],
        "risk_score": case_data['current_risk_score'],
        "category": case_data['current_category'],
        "risk_signals": case_data['current_risk_signals'],
        "ingestion_date": datetime.now()
    }
    history_col.insert_one(history_entry)

def seed_cases():
    """Seed cases (triggers checklist and history creation)"""
    cases_col = db['scs_cases']
    cases_col.delete_many({})
    
    db['scs_checklist'].delete_many({})
    db['scs_case_history'].delete_many({})
    
    cases = [
        # Unassigned cases
        {
            "case_id": "CASE_2026_001",
            "user_id": "@at_risk_teen_01",
            "assigned_to": None,
            "current_risk_score": 78.5,
            "current_category": "Moderate Risk - Depression",
            "current_risk_signals": "Multiple posts expressing sadness, isolation mentions",
            "case_status": "unassigned",
            "work_status": "not_started",
            "priority": "medium"
        },
        {
            "case_id": "CASE_2026_002",
            "user_id": "@vulnerable_user_02",
            "assigned_to": None,
            "current_risk_score": 92.3,
            "current_category": "High Risk - Self Harm",
            "current_risk_signals": "Self-harm imagery detected, withdrawal from social activities",
            "case_status": "unassigned",
            "work_status": "not_started",
            "priority": "high"
        },
        {
            "case_id": "CASE_2026_003",
            "user_id": "@youth_concern_03",
            "assigned_to": None,
            "current_risk_score": 65.2,
            "current_category": "Low Risk - Stress",
            "current_risk_signals": "Academic stress indicators, sleep issues mentioned",
            "case_status": "unassigned",
            "work_status": "not_started",
            "priority": "low"
        },
        # Assigned cases
        {
            "case_id": "CASE_2026_004",
            "user_id": "@struggling_teen_04",
            "assigned_to": "helper_001",
            "current_risk_score": 85.7,
            "current_category": "High Risk - Anxiety",
            "current_risk_signals": "Panic attack mentions, avoidance behavior patterns",
            "case_status": "assigned",
            "work_status": "in_progress",
            "priority": "high"
        },
        {
            "case_id": "CASE_2026_005",
            "user_id": "@isolated_user_05",
            "assigned_to": "helper_002",
            "current_risk_score": 71.4,
            "current_category": "Moderate Risk - Social Isolation",
            "current_risk_signals": "Declining friend interactions, increased online time",
            "case_status": "assigned",
            "work_status": "in_progress",
            "priority": "medium"
        },
        {
            "case_id": "CASE_2026_006",
            "user_id": "@depressed_youth_06",
            "assigned_to": "helper_003",
            "current_risk_score": 88.9,
            "current_category": "High Risk - Depression",
            "current_risk_signals": "Suicidal ideation detected, hopelessness expressions",
            "case_status": "assigned",
            "work_status": "in_progress",
            "priority": "critical"
        },
        {
            "case_id": "CASE_2026_007",
            "user_id": "@complex_case_07",
            "assigned_to": "helper_001",
            "current_risk_score": 94.1,
            "current_category": "Critical Risk - Multiple Factors",
            "current_risk_signals": "Self-harm + substance abuse indicators",
            "case_status": "assigned",
            "work_status": "to_review",
            "priority": "critical"
        },
        {
            "case_id": "CASE_2026_008",
            "user_id": "@recovered_user_08",
            "assigned_to": "helper_002",
            "current_risk_score": 42.3,
            "current_category": "Low Risk - Improving",
            "current_risk_signals": "Positive progress, engaging with support",
            "case_status": "assigned",
            "work_status": "completed",
            "priority": "low"
        },
        {
            "case_id": "CASE_2026_009",
            "user_id": "@success_story_09",
            "assigned_to": "helper_004",
            "current_risk_score": 38.1,
            "current_category": "Low Risk - Stable",
            "current_risk_signals": "Successfully connected with resources",
            "case_status": "assigned",
            "work_status": "completed",
            "priority": "low"
        },
        {
            "case_id": "CASE_2026_010",
            "user_id": "@needs_specialist_10",
            "assigned_to": "helper_005",
            "current_risk_score": 91.8,
            "current_category": "High Risk - Complex Trauma",
            "current_risk_signals": "Trauma indicators requiring specialized intervention",
            "case_status": "assigned",
            "work_status": "in_progress",
            "priority": "high"
        }
    ]
    
    for case in cases:
        create_case_with_checklist_and_history(case)
    
    print(f"✅ Seeded {len(cases)} cases with checklist and history")

def seed_custom_checklist_items():
    """Add custom checklist items"""
    checklist_col = db['scs_checklist']
    
    custom_items = [
        {
            "checklist_item_id": get_next_id('scs_checklist', 'checklist_item_id'),
            "case_id": "CASE_2026_004",
            "template_id": None,
            "label": "Contact school counselor",
            "is_mandatory": False,
            "completed": False,
            "comments": [],
            "completed_at": None,
            "completed_by": None,
            "display_order": 5,
            "created_at": datetime.now()
        },
        {
            "checklist_item_id": get_next_id('scs_checklist', 'checklist_item_id'),
            "case_id": "CASE_2026_004",
            "template_id": None,
            "label": "Share anxiety management resources",
            "is_mandatory": False,
            "completed": False,
            "comments": [],
            "completed_at": None,
            "completed_by": None,
            "display_order": 6,
            "created_at": datetime.now()
        },
        {
            "checklist_item_id": get_next_id('scs_checklist', 'checklist_item_id'),
            "case_id": "CASE_2026_006",
            "template_id": None,
            "label": "Notify emergency contact",
            "is_mandatory": True,
            "completed": False,
            "comments": [],
            "completed_at": None,
            "completed_by": None,
            "display_order": 5,
            "created_at": datetime.now()
        },
        {
            "checklist_item_id": get_next_id('scs_checklist', 'checklist_item_id'),
            "case_id": "CASE_2026_006",
            "template_id": None,
            "label": "Daily check-in scheduled",
            "is_mandatory": True,
            "completed": False,
            "comments": [],
            "completed_at": None,
            "completed_by": None,
            "display_order": 6,
            "created_at": datetime.now()
        },
        {
            "checklist_item_id": get_next_id('scs_checklist', 'checklist_item_id'),
            "case_id": "CASE_2026_006",
            "template_id": None,
            "label": "Crisis hotline provided",
            "is_mandatory": True,
            "completed": False,
            "comments": [],
            "completed_at": None,
            "completed_by": None,
            "display_order": 7,
            "created_at": datetime.now()
        }
    ]
    
    checklist_col.insert_many(custom_items)
    print(f"✅ Seeded {len(custom_items)} custom checklist items")

def seed_checklist_progress():
    """Mark some checklist items as completed"""
    checklist_col = db['scs_checklist']
    
    now = datetime.now()
    
    # Case 004 - 2 items completed
    checklist_col.update_one(
        {"case_id": "CASE_2026_004", "label": "Case Analysis Completed"},
        {"$set": {
            "completed": True,
            "completed_at": now,
            "completed_by": "helper_001",
            "comments": [{
                "comment": "Initial analysis done, anxiety disorder suspected",
                "timestamp": now.isoformat(),
                "by": "helper_001"
            }]
        }}
    )
    
    checklist_col.update_one(
        {"case_id": "CASE_2026_004", "label": "Outreach Attempted"},
        {"$set": {
            "completed": True,
            "completed_at": now,
            "completed_by": "helper_001",
            "comments": [{
                "comment": "Sent DM via Instagram, awaiting response",
                "timestamp": now.isoformat(),
                "by": "helper_001"
            }]
        }}
    )
    
    # Case 005 - 3 items completed
    checklist_col.update_one(
        {"case_id": "CASE_2026_005", "label": "Case Analysis Completed"},
        {"$set": {
            "completed": True,
            "completed_at": now,
            "completed_by": "helper_002",
            "comments": [{
                "comment": "Reviewed profile, signs of social withdrawal",
                "timestamp": now.isoformat(),
                "by": "helper_002"
            }]
        }}
    )
    
    checklist_col.update_one(
        {"case_id": "CASE_2026_005", "label": "Outreach Attempted"},
        {"$set": {
            "completed": True,
            "completed_at": now,
            "completed_by": "helper_002",
            "comments": [{
                "comment": "Made initial contact, user responsive",
                "timestamp": now.isoformat(),
                "by": "helper_002"
            }]
        }}
    )
    
    checklist_col.update_one(
        {"case_id": "CASE_2026_005", "label": "Response Received"},
        {"$set": {
            "completed": True,
            "completed_at": now,
            "completed_by": "helper_002",
            "comments": [{
                "comment": "User replied positively, open to support",
                "timestamp": now.isoformat(),
                "by": "helper_002"
            }]
        }}
    )
    
    print("✅ Updated checklist progress for multiple cases")

def seed_additional_case_history():
    """Add historical entries (simulating re-ingestion)"""
    history_col = db['scs_case_history']
    
    history_entries = [
        # Case 005 - risk increased
        {
            "history_id": get_next_id('scs_case_history', 'history_id'),
            "case_id": "CASE_2026_005",
            "risk_score": 62.1,
            "category": "Moderate Risk - Social Isolation",
            "risk_signals": "Early signs of isolation",
            "ingestion_date": datetime.now() - timedelta(days=5)
        },
        {
            "history_id": get_next_id('scs_case_history', 'history_id'),
            "case_id": "CASE_2026_005",
            "risk_score": 68.3,
            "category": "Moderate Risk - Social Isolation",
            "risk_signals": "Isolation worsening, fewer interactions",
            "ingestion_date": datetime.now() - timedelta(days=2)
        },
        # Case 006 - got worse
        {
            "history_id": get_next_id('scs_case_history', 'history_id'),
            "case_id": "CASE_2026_006",
            "risk_score": 75.4,
            "category": "High Risk - Depression",
            "risk_signals": "Depression symptoms noted",
            "ingestion_date": datetime.now() - timedelta(days=7)
        },
        {
            "history_id": get_next_id('scs_case_history', 'history_id'),
            "case_id": "CASE_2026_006",
            "risk_score": 82.7,
            "category": "High Risk - Depression",
            "risk_signals": "Worsening symptoms, ideation mentioned",
            "ingestion_date": datetime.now() - timedelta(days=3)
        },
        # Case 008 - improved
        {
            "history_id": get_next_id('scs_case_history', 'history_id'),
            "case_id": "CASE_2026_008",
            "risk_score": 68.9,
            "category": "Moderate Risk - Depression",
            "risk_signals": "Initial depression indicators",
            "ingestion_date": datetime.now() - timedelta(days=15)
        },
        {
            "history_id": get_next_id('scs_case_history', 'history_id'),
            "case_id": "CASE_2026_008",
            "risk_score": 55.2,
            "category": "Low Risk - Improving",
            "risk_signals": "Showing signs of improvement",
            "ingestion_date": datetime.now() - timedelta(days=8)
        }
    ]
    
    history_col.insert_many(history_entries)
    print(f"✅ Seeded {len(history_entries)} additional history entries")

def seed_review_requests():
    """Seed review requests"""
    review_col = db['scs_review_requests']
    review_col.delete_many({})
    
    reviews = [
        {
            "review_id": get_next_id('scs_review_requests', 'review_id'),
            "case_id": "CASE_2026_007",
            "requested_by": "helper_001",
            "reason": "This case involves multiple risk factors (self-harm + substance abuse). Need guidance on best intervention approach and whether to escalate to emergency services.",
            "request_status": "pending",
            "requested_at": datetime.now() - timedelta(hours=2),
            "resolved_by": None,
            "resolved_at": None,
            "resolution_notes": None
        },
        {
            "review_id": get_next_id('scs_review_requests', 'review_id'),
            "case_id": "CASE_2026_004",
            "requested_by": "helper_001",
            "reason": "User mentioned panic attacks. Should I refer to mental health professional immediately?",
            "request_status": "resolved",
            "requested_at": datetime.now() - timedelta(days=3),
            "resolved_by": "admin_001",
            "resolved_at": datetime.now() - timedelta(days=2),
            "resolution_notes": "Yes, provide mental health resources and continue monitoring. Document all interactions."
        }
    ]
    
    review_col.insert_many(reviews)
    print(f"✅ Seeded {len(reviews)} review requests")

def seed_reassignment_requests():
    """Seed reassignment requests"""
    reassign_col = db['scs_reassignment_requests']
    reassign_col.delete_many({})
    
    reassignments = [
        {
            "request_id": get_next_id('scs_reassignment_requests', 'request_id'),
            "case_id": "CASE_2026_010",
            "requested_by": "helper_005",
            "current_assigned_to": "helper_005",
            "reason": "This case requires specialized trauma-informed care that is beyond my current expertise. Recommend reassignment to helper with trauma training.",
            "suggested_helper": "helper_003",
            "request_status": "pending",
            "requested_at": datetime.now() - timedelta(hours=5),
            "reviewed_by": None,
            "reviewed_at": None,
            "new_assigned_to": None,
            "review_notes": None
        },
        {
            "request_id": get_next_id('scs_reassignment_requests', 'request_id'),
            "case_id": "CASE_2026_006",
            "requested_by": "helper_001",
            "current_assigned_to": "helper_001",
            "reason": "I have 8 active critical cases. Need to balance workload for effective case management.",
            "suggested_helper": "helper_003",
            "request_status": "approved",
            "requested_at": datetime.now() - timedelta(days=4),
            "reviewed_by": "admin_001",
            "reviewed_at": datetime.now() - timedelta(days=4),
            "new_assigned_to": "helper_003",
            "review_notes": "Approved due to workload concerns. Case reassigned to helper_003."
        },
        {
            "request_id": get_next_id('scs_reassignment_requests', 'request_id'),
            "case_id": "CASE_2026_005",
            "requested_by": "helper_002",
            "current_assigned_to": "helper_002",
            "reason": "Requesting reassignment due to scheduling conflicts.",
            "suggested_helper": "helper_004",
            "request_status": "declined",
            "requested_at": datetime.now() - timedelta(days=2),
            "reviewed_by": "admin_002",
            "reviewed_at": datetime.now() - timedelta(days=1),
            "new_assigned_to": None,
            "review_notes": "Please work through scheduling conflicts. Case complexity matches your skill set. Case remains with you."
        }
    ]
    
    reassign_col.insert_many(reassignments)
    print(f"✅ Seeded {len(reassignments)} reassignment requests")

def verify_seed_data():
    """Verify seeded data"""
    print("\n" + "="*60)
    print("SEED DATA VERIFICATION")
    print("="*60)
    
    # Users
    users_count = db['scs_users'].count_documents({})
    admin_count = db['scs_users'].count_documents({"role": "admin"})
    helper_count = db['scs_users'].count_documents({"role": "youth_helper"})
    print(f"\n👥 Users: {users_count} (Admins: {admin_count}, Helpers: {helper_count})")
    
    # Cases
    total_cases = db['scs_cases'].count_documents({})
    unassigned = db['scs_cases'].count_documents({"case_status": "unassigned"})
    assigned = db['scs_cases'].count_documents({"case_status": "assigned"})
    print(f"\n📋 Cases: {total_cases} (Unassigned: {unassigned}, Assigned: {assigned})")
    
    # Case priorities
    for priority in ["low", "medium", "high", "critical"]:
        count = db['scs_cases'].count_documents({"priority": priority})
        print(f"   {priority.capitalize()}: {count}")
    
    # Work statuses
    print("\n⚙️  Work Status (Assigned Cases):")
    for status in ["not_started", "in_progress", "to_review", "completed"]:
        count = db['scs_cases'].count_documents({"work_status": status, "case_status": "assigned"})
        print(f"   {status}: {count}")
    
    # Checklist
    checklist_count = db['scs_checklist'].count_documents({})
    mandatory_count = db['scs_checklist'].count_documents({"is_mandatory": True})
    completed_count = db['scs_checklist'].count_documents({"completed": True})
    print(f"\n✅ Checklist Items:")
    print(f"   Total: {checklist_count}")
    print(f"   Mandatory: {mandatory_count}")
    print(f"   Completed: {completed_count}")
    
    # History
    history_count = db['scs_case_history'].count_documents({})
    print(f"\n📊 Case History Entries: {history_count}")
    
    # Review requests
    print("\n🔍 Review Requests:")
    for status in ["pending", "resolved"]:
        count = db['scs_review_requests'].count_documents({"request_status": status})
        print(f"   {status.capitalize()}: {count}")
    
    # Reassignment requests
    print("\n🔄 Reassignment Requests:")
    for status in ["pending", "approved", "declined"]:
        count = db['scs_reassignment_requests'].count_documents({"request_status": status})
        print(f"   {status.capitalize()}: {count}")
    
    # Pending admin actions
    pending_reviews = db['scs_review_requests'].count_documents({"request_status": "pending"})
    pending_reassignments = db['scs_reassignment_requests'].count_documents({"request_status": "pending"})
    print(f"\n⚠️  Pending Admin Actions: {pending_reviews + pending_reassignments}")
    
    # Helper workload
    print("\n👨‍💼 Youth Helper Workload:")
    helpers = db['scs_users'].find({"role": "youth_helper", "is_active": True})
    for helper in helpers:
        active_cases = db['scs_cases'].count_documents({
            "assigned_to": helper['user_id'],
            "case_status": "assigned"
        })
        critical = db['scs_cases'].count_documents({
            "assigned_to": helper['user_id'],
            "priority": "critical"
        })
        high = db['scs_cases'].count_documents({
            "assigned_to": helper['user_id'],
            "priority": "high"
        })
        print(f"   {helper['username']}: {active_cases} active cases ({critical} critical, {high} high)")
    
    print("\n" + "="*60)

def main():
    """Run all seed functions"""
    print("🌱 Starting MongoDB seeding...\n")
    
    try:
        seed_users()
        seed_checklist_templates()
        seed_cases()  # Creates cases with checklist and history
        seed_custom_checklist_items()
        seed_checklist_progress()
        seed_additional_case_history()
        seed_review_requests()
        seed_reassignment_requests()
        
        print("\n" + "="*60)
        print("✅ ALL SEED DATA INSERTED SUCCESSFULLY")
        print("="*60)
        
        verify_seed_data()
        
        print("\n🎉 MongoDB setup complete!")
        print(f"📍 Database: {DB_NAME}")
        print(f"🔗 URI: {MONGODB_URI.split('@')[1].split('/')[0]}")
        
    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
        raise

# AT THE VERY BOTTOM, make sure you have:
if __name__ == "__main__":
    print("\n🌱 Calling main()...\n")
    main()
    print("\n✅ main() completed!")