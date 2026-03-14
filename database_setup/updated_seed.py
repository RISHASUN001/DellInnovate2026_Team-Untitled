"""
Seed script with AI explanation instead of structured risk_summary
"""

import os
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv('MONGODB_URI')
DB_NAME = os.getenv('SCS_DB_NAME', 'dellinnovate')

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

print("="*60)
print("🌱 SEEDING WITH AI EXPLANATION")
print("="*60)

def get_next_id(collection_name, field_name):
    counter_col = db['counters']
    result = counter_col.find_one_and_update(
        {'_id': f"{collection_name}_{field_name}"},
        {'$inc': {'seq': 1}},
        upsert=True,
        return_document=True
    )
    return result['seq']

def create_case_with_history(case_data):
    """Create case and initial history entry"""
    # Insert case
    db['scs_cases'].insert_one(case_data.copy())
    print(f"  ✅ Created case {case_data['case_id']}")
    
    # Create initial history entry with same structure
    history_entry = {
        "history_id": get_next_id('scs_case_history', 'history_id'),
        "case_id": case_data['case_id'],
        "risk_score": case_data['current_risk_score'],
        "category": case_data['category'],
        "ai_explanation": case_data['ai_explanation'],  # Same AI explanation
        "ingestion_date": datetime.now(),
        "model_version": "v2.1.0"
    }
    db['scs_case_history'].insert_one(history_entry)
    
    # Create checklist items
    templates = db['scs_checklist_templates'].find({'is_active': True}).sort('display_order', 1)
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
        db['scs_checklist'].insert_one(checklist_item)

def seed_all():
    """Seed all data with AI explanation"""
    
    # Clear existing data
    print("\n🧹 Clearing existing data...")
    db['scs_cases'].delete_many({})
    db['scs_case_history'].delete_many({})
    db['scs_checklist'].delete_many({})
    
    print("\n📋 Creating cases with AI explanations...")
    
    # Case 1: Depression
    case1 = {
        "case_id": "CASE_2026_001",
        "user_id": "@at_risk_teen_01",
        "assigned_to": None,
        "current_risk_score": 78.5,
        "category": "Depression",
        "ai_explanation": """Based on sentiment analysis of recent posts and behavioral patterns, this user shows concerning signs of depression. Key indicators include:

• Consistently negative emotional tone across 8 posts in the past week (3x their normal posting frequency)
• Frequent expressions of sadness, hopelessness, and feeling "stuck"
• Mentions of sleep disruption with late-night posting activity (12am-3am)
• 45% drop in engagement with their usual friend group
• References to feeling isolated despite being surrounded by people

While there are protective factors (supportive comments from friends, engagement with mental health content), the combination of behavioral changes and emotional distress warrants intervention. The risk score reflects moderate concern requiring proactive outreach.""",
        "case_status": "unassigned",
        "work_status": "not_started",
        "priority": "medium",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    create_case_with_history(case1)
    
    # Case 2: Self-Harm
    case2 = {
        "case_id": "CASE_2026_002",
        "user_id": "@vulnerable_user_02",
        "assigned_to": None,
        "current_risk_score": 92.3,
        "category": "Self-Harm",
        "ai_explanation": """This case requires urgent attention. Analysis reveals multiple high-risk indicators:

• Self-harm imagery detected in saved content and story shares
• Posts containing phrases like "escape from pain" and "want it to end"
• Dramatic behavioral shift: deleted 15 photos with friends, changed account to private
• Story views plummeted from 200+ to only 12, indicating severe social withdrawal
• Following accounts specifically related to self-harm content
• Active during crisis hours (2am-5am) with concerning search patterns

Recent trigger: breakup mentioned 3 days ago, followed by escalating distress signals. While user previously engaged with crisis hotline information and has one close friend still commenting, the rapid deterioration and explicit self-harm indicators place this at critical priority. Immediate intervention recommended.""",
        "case_status": "unassigned",
        "work_status": "not_started",
        "priority": "critical",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    create_case_with_history(case2)
    
    # Case 3: Academic Stress
    case3 = {
        "case_id": "CASE_2026_003",
        "user_id": "@youth_concern_03",
        "assigned_to": None,
        "current_risk_score": 65.2,
        "category": "Academic Stress",
        "ai_explanation": """Moderate academic stress detected with some concerning patterns:

• Repeated mentions of exam pressure and feeling overwhelmed by deadlines
• Sleep deprivation reported (3-4 hours per night during exam period)
• Posts show increased anxiety about performance and parental expectations
• Skipping meals mentioned, along with increased caffeine/energy drink references
• Posting during study-intensive hours (10pm-2am) suggesting poor sleep hygiene

Positive factors: Strong family support visible in interactions, participation in study groups, mentions of exercise as coping mechanism. The stress appears situational (exam period) rather than chronic, but warrants monitoring to prevent escalation. Recommend checking in to provide stress management resources and ensure healthy coping strategies.""",
        "case_status": "unassigned",
        "work_status": "not_started",
        "priority": "low",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    create_case_with_history(case3)
    
    # Case 4: Anxiety (Assigned)
    case4 = {
        "case_id": "CASE_2026_004",
        "user_id": "@struggling_teen_04",
        "assigned_to": "helper_001",
        "current_risk_score": 85.7,
        "category": "Anxiety",
        "ai_explanation": """Severe anxiety disorder presenting with panic attack symptoms:

• Multiple explicit mentions of panic attacks in posts and DMs
• Physical symptoms described: chest pain, dizziness, difficulty breathing
• Developing agoraphobia - fear of leaving house increasingly mentioned
• School attendance declining with 6 cancelled social plans in 2 weeks
• Avoidance behaviors escalating across multiple contexts

The anxiety appears to have been triggered by a public speaking event that led to first panic attack. Subsequent similar situations now trigger anticipatory anxiety and avoidance. User is actively seeking information about anxiety management and parents are aware and supportive, which are strong protective factors. However, the rapid functional decline and impact on daily life warrant high priority intervention and likely referral to mental health professional.""",
        "case_status": "assigned",
        "work_status": "in_progress",
        "priority": "high",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    create_case_with_history(case4)
    
    # Case 5: Social Isolation (Assigned)
    case5 = {
        "case_id": "CASE_2026_005",
        "user_id": "@isolated_user_05",
        "assigned_to": "helper_002",
        "current_risk_score": 71.4,
        "category": "Social Isolation",
        "ai_explanation": """Progressive social isolation with concerning trajectory:

• Direct statements of feeling alone and excluded from friend group
• Stopped participating in group activities that were previously important
• Excessive online time (8+ hours daily) replacing in-person interactions
• Passive social media consumption without meaningful engagement
• No longer posting group photos that were previously common

Timeline shows worsening: started 2 weeks ago after friend group conflict, has escalated steadily. Trigger event: friends attended event without including them, leading to perceived rejection. However, maintains connection with family (visible in some posts) and has online gaming friends. Responds to direct messages, suggesting openness to connection. Risk is moderate but trending upward - early intervention could prevent escalation to depression.""",
        "case_status": "assigned",
        "work_status": "in_progress",
        "priority": "medium",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    create_case_with_history(case5)
    
    # Case 6: Cyberbullying (Assigned)
    case6 = {
        "case_id": "CASE_2026_006",
        "user_id": "@cyberbully_victim_06",
        "assigned_to": "helper_003",
        "current_risk_score": 88.9,
        "category": "Cyberbullying",
        "ai_explanation": """Active cyberbullying situation with severe psychological impact:

• Evidence of coordinated harassment campaign - sharp increase in negative comments
• User shared screenshots of hate messages, indicating distress and possible call for help
• Posts expressing hopelessness and mentions of "not wanting to exist"
• Changed account to private and stopped posting photos of self (attempting to hide)
• Online activity reduced 70% - withdrawing from platform where bullying occurs

Trigger: photo shared without consent 2 weeks ago led to rumor spreading and coordinated bullying. User has taken some protective actions (blocking, private account, contacted school counselor) but psychological toll is severe. Some friends defending in comments shows social support exists. Critical priority due to explicit hopelessness statements combined with ongoing harassment. Requires immediate support and possibly platform safety intervention.""",
        "case_status": "assigned",
        "work_status": "in_progress",
        "priority": "critical",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    create_case_with_history(case6)
    
    # Case 7: Family Conflict (Assigned)
    case7 = {
        "case_id": "CASE_2026_007",
        "user_id": "@family_conflict_07",
        "assigned_to": "helper_001",
        "current_risk_score": 73.2,
        "category": "Family Conflict",
        "ai_explanation": """Significant family distress related to parental divorce:

• Frequent venting posts about family arguments and feeling unwanted at home
• Removed all family photos from profile - symbolic rejection of family unit
• Mentions considering running away, which raises safety concerns
• Spending increased time at friends' houses and posting from locations away from home
• Late-night emotional posts suggesting lack of stable home environment

Context: Parents' divorce proceedings recently started with ongoing custody dispute. User feeling caught in middle and expressing feeling like a burden. However, has close supportive friends providing temporary refuge and has engaged with family therapy resources. Teacher identified as trusted adult. High priority due to running away mention and unstable home situation, but protective factors suggest intervention can be effective.""",
        "case_status": "assigned",
        "work_status": "to_review",
        "priority": "high",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    create_case_with_history(case7)
    
    # Case 8: Bullying (Assigned)
    case8 = {
        "case_id": "CASE_2026_008",
        "user_id": "@bullied_teen_08",
        "assigned_to": "helper_002",
        "current_risk_score": 69.1,
        "category": "Bullying",
        "ai_explanation": """In-person bullying at school with online manifestations:

• Multiple mentions of avoiding school and dreading certain classes/locations
• Changed posting behavior - now hides face in photos, stopped posting about school
• References to "wanting to be invisible" and feeling unsafe
• Reduced interaction with classmates online, suggesting social anxiety
• Low self-esteem indicators in post language and content choices

School counselor and family are aware and engaged, which is positive. User maintains friendships outside of school context providing safe social space. The bullying appears localized to school environment rather than pervasive across all contexts. Moderate priority - situation is being addressed by school but user needs emotional support and coping strategies while resolution is pursued.""",
        "case_status": "assigned",
        "work_status": "completed",
        "priority": "medium",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    create_case_with_history(case8)
    
    # Case 9: Suicidal Ideation (Assigned)
    case9 = {
        "case_id": "CASE_2026_009",
        "user_id": "@crisis_user_09",
        "assigned_to": "helper_004",
        "current_risk_score": 95.8,
        "category": "Suicidal Ideation",
        "ai_explanation": """CRITICAL: Active suicidal ideation with concerning preparation behaviors:

• Direct mentions of suicide in recent posts - not veiled or metaphorical
• Posted photos of giving away possessions with goodbye messages to specific friends
• Created and shared "final playlist" on Spotify with concerning song choices
• Search history indicators suggest researching methods
• Complete isolation from all contacts except one persistent friend

This represents an acute crisis situation requiring immediate intervention. User has history of reaching out to crisis line previously, showing some ambivalence about death, and has therapy appointment scheduled which they mentioned. One friend actively trying to help and user occasionally responds to them. However, the combination of explicit suicidal statements, preparation behaviors (giving away items, goodbye messages), and method research places this at highest risk level. Emergency protocols should be initiated immediately.""",
        "case_status": "assigned",
        "work_status": "in_progress",
        "priority": "critical",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    create_case_with_history(case9)
    
    # Case 10: Substance Abuse (Assigned)
    case10 = {
        "case_id": "CASE_2026_010",
        "user_id": "@substance_concern_10",
        "assigned_to": "helper_005",
        "current_risk_score": 81.3,
        "category": "Substance Abuse",
        "ai_explanation": """Escalating substance use with warning signs:

• Dramatic increase in party photos and references to substance use
• Posts showing visible signs of intoxication at various times
• Mentions of declining school performance and missing classes
• Friend group has shifted entirely to known substance users
• Defensive, sometimes aggressive responses to concerned comments from family/old friends

Pattern suggests progression from experimental to regular use, with substances becoming central to social identity. Posts during odd hours with impaired judgment evident in content. However, parents recently became aware and are taking action. User still maintains some connection to athletic interests and has some sober friends in network. High priority due to rapid escalation and impact on functioning, but family engagement and remaining positive interests provide intervention opportunities.""",
        "case_status": "assigned",
        "work_status": "in_progress",
        "priority": "high",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    create_case_with_history(case10)
    
    print(f"\n✅ Created 10 cases with AI explanations")
    
    # Add historical entries for Case 5 to show evolution
    print("\n📊 Adding historical entries for Case 5 (showing progression)...")
    
    history_entries = [
        {
            "history_id": get_next_id('scs_case_history', 'history_id'),
            "case_id": "CASE_2026_005",
            "risk_score": 62.1,
            "category": "Social Isolation",
            "ai_explanation": """Early signs of social withdrawal detected:

• Slightly reduced frequency of interactions with usual friend group
• Still attending social events but engagement appears less enthusiastic
• Normal posting frequency maintained
• All previous social connections still visible and active

At this stage, isolation is minimal and could be temporary situational response. User maintains strong connections and participates in group activities. Monitoring recommended but no immediate intervention needed.""",
            "ingestion_date": datetime.now() - timedelta(days=5),
            "model_version": "v2.1.0"
        },
        {
            "history_id": get_next_id('scs_case_history', 'history_id'),
            "case_id": "CASE_2026_005",
            "risk_score": 68.3,
            "category": "Social Isolation",
            "ai_explanation": """Social isolation worsening - concerning trend:

• Sad emoji usage increased 200% compared to baseline
• Stopped attending weekly game night that was previously consistent
• More photos alone versus with friends (reversed ratio from previous pattern)
• Comments on others' posts decreased by 60%
• Friend group conflict mentioned in vague post

Clear progression from previous assessment. User is actively withdrawing rather than just being less engaged. The change appears connected to interpersonal conflict. Intervention becoming appropriate to prevent further isolation.""",
            "ingestion_date": datetime.now() - timedelta(days=2),
            "model_version": "v2.1.0"
        }
    ]
    
    db['scs_case_history'].insert_many(history_entries)
    print(f"✅ Added {len(history_entries)} historical entries showing progression")
    
    # Add historical entries for Case 9 showing crisis escalation
    print("\n📊 Adding historical entries for Case 9 (crisis escalation)...")
    
    crisis_history = [
        {
            "history_id": get_next_id('scs_case_history', 'history_id'),
            "case_id": "CASE_2026_009",
            "risk_score": 75.4,
            "category": "Depression",
            "ai_explanation": """Depression detected with increasing severity:

• Posts showing persistent sadness and negative self-perception
• Withdrawal from previously enjoyed activities
• Sleep pattern disruption mentioned
• Negative self-talk becoming more frequent
• Still communicating with friends but conversations more superficial

User attending therapy and has support system. Depression appears to be worsening despite treatment engagement, which warrants closer monitoring. Not yet at crisis level but trajectory concerning.""",
            "ingestion_date": datetime.now() - timedelta(days=7),
            "model_version": "v2.1.0"
        },
        {
            "history_id": get_next_id('scs_case_history', 'history_id'),
            "case_id": "CASE_2026_009",
            "risk_score": 88.2,
            "category": "Suicidal Ideation",
            "ai_explanation": """ESCALATION TO SUICIDAL IDEATION:

• First direct mention of not wanting to live appeared in post
• Expressions of hopelessness and seeing no future
• Stopped responding to messages from friends (isolation intensifying)
• Removed happy photos from profile - erasing positive memories
• Dark, cryptic posts suggesting despair

This represents significant deterioration from previous depression assessment. User crossed threshold from depression to active suicidal thoughts. Still attending therapy and one friend persistently trying to reach out. Requires immediate elevation to crisis protocols.""",
            "ingestion_date": datetime.now() - timedelta(days=3),
            "model_version": "v2.1.0"
        }
    ]
    
    db['scs_case_history'].insert_many(crisis_history)
    print(f"✅ Added {len(crisis_history)} crisis escalation entries")

def verify_data():
    """Verify seeded data"""
    print("\n" + "="*60)
    print("🔍 VERIFICATION")
    print("="*60)
    
    # Count by category
    print("\n📊 Cases by Category:")
    categories = db['scs_cases'].distinct('category')
    for cat in sorted(categories):
        count = db['scs_cases'].count_documents({'category': cat})
        print(f"  {cat}: {count}")
    
    # Count by priority
    print("\n⚠️  Cases by Priority:")
    for priority in ['low', 'medium', 'high', 'critical']:
        count = db['scs_cases'].count_documents({'priority': priority})
        print(f"  {priority.capitalize()}: {count}")
    
    # Show sample case with AI explanation
    print("\n📄 Sample Case (Cyberbullying):")
    sample = db['scs_cases'].find_one({'case_id': 'CASE_2026_006'})
    if sample:
        print(f"  Case ID: {sample['case_id']}")
        print(f"  Category: {sample['category']}")
        print(f"  Risk Score: {sample['current_risk_score']}")
        print(f"  AI Explanation (first 200 chars):")
        print(f"  {sample['ai_explanation'][:200]}...")
    
    # Show history evolution
    print("\n📈 Case History Evolution (Case 5):")
    history = db['scs_case_history'].find({'case_id': 'CASE_2026_005'}).sort('ingestion_date', 1)
    for entry in history:
        date_str = entry['ingestion_date'].strftime('%Y-%m-%d')
        explanation_preview = entry['ai_explanation'][:80].replace('\n', ' ')
        print(f"  {date_str}: Score {entry['risk_score']} - {explanation_preview}...")
    
    # Check schema
    print("\n🔍 Schema Verification:")
    sample = db['scs_cases'].find_one({})
    if sample:
        has_ai_explanation = 'ai_explanation' in sample
        has_old_fields = 'risk_summary' in sample or 'current_risk_signals' in sample
        
        if has_ai_explanation and not has_old_fields:
            print("  ✅ Correct schema: ai_explanation field present")
            print("  ✅ Old fields removed (risk_summary, current_risk_signals)")
        elif has_ai_explanation and has_old_fields:
            print("  ⚠️  Mixed schema: has both new and old fields")
        else:
            print("  ❌ Missing ai_explanation field")
    
    # Totals
    print("\n📊 Total Records:")
    print(f"  Cases: {db['scs_cases'].count_documents({})}")
    print(f"  History Entries: {db['scs_case_history'].count_documents({})}")
    print(f"  Checklist Items: {db['scs_checklist'].count_documents({})}")

if __name__ == "__main__":
    try:
        seed_all()
        verify_data()
        
        print("\n" + "="*60)
        print("✅ AI EXPLANATION SEED COMPLETE!")
        print("="*60)
        print("\n🤖 Schema Update:")
        print("  - Removed: risk_summary (structured JSON)")
        print("  - Added: ai_explanation (LLM-generated text)")
        print("  - Same structure in both scs_cases and scs_case_history")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()