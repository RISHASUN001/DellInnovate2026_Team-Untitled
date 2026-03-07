"""
Case Promotion Service
Bridges NLP analytics outputs to operational SCS case management tables
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.scs_models import (
    SCSCaseModel,
    SCSCaseHistoryModel,
    SCSChecklistItemModel,
    SCSChecklistTemplateModel,
    PriorityLevel,
    CaseStatus,
    WorkStatus
)

class CasePromotionService:
    """
    Service to promote risk profiles to operational cases
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.model_version = "nlp-v1-pca-v1"  # Update as needed
    
    async def ensure_checklist_templates(self) -> List[Dict]:
        """
        Ensure default checklist templates exist
        Returns list of templates
        """
        templates_collection = self.db.scs_checklist_templates
        
        # Default templates
        default_templates = [
            {
                "template_id": 1,
                "label": "Case Analysis Completed",
                "is_mandatory": True,
                "display_order": 1,
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "template_id": 2,
                "label": "Outreach Attempted",
                "is_mandatory": True,
                "display_order": 2,
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "template_id": 3,
                "label": "Response Received",
                "is_mandatory": True,
                "display_order": 3,
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "template_id": 4,
                "label": "Follow-up Scheduled",
                "is_mandatory": True,
                "display_order": 4,
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        ]
        
        # Check if templates exist
        count = await templates_collection.count_documents({})
        if count == 0:
            logger.info("Creating default checklist templates")
            await templates_collection.insert_many(default_templates)
            return default_templates
        else:
            # Fetch existing templates
            cursor = templates_collection.find({"is_active": True}).sort("display_order", 1)
            templates = await cursor.to_list(length=None)
            return templates
    
    async def get_next_case_id(self) -> str:
        """
        Generate next case ID in format CASE_YYYY_XXX
        """
        year = datetime.utcnow().year
        
        # Use a counter collection for atomic increment
        counters_collection = self.db.counters
        result = await counters_collection.find_one_and_update(
            {"_id": f"case_id_{year}"},
            {"$inc": {"sequence": 1}},
            upsert=True,
            return_document=True
        )
        
        if result:
            sequence = result.get("sequence", 1)
        else:
            sequence = 1
        
        return f"CASE_{year}_{sequence:03d}"
    
    async def get_next_history_id(self, case_id: str) -> int:
        """
        Get next history ID for a case
        """
        history_collection = self.db.scs_case_history
        
        # Find max history_id for this case
        pipeline = [
            {"$match": {"case_id": case_id}},
            {"$group": {"_id": None, "max_id": {"$max": "$history_id"}}}
        ]
        
        cursor = history_collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        
        if result and result[0].get("max_id"):
            return result[0]["max_id"] + 1
        else:
            return 1
    
    async def get_next_checklist_item_id(self, case_id: str) -> int:
        """
        Get next checklist item ID for a case
        """
        checklist_collection = self.db.scs_checklist
        
        pipeline = [
            {"$match": {"case_id": case_id}},
            {"$group": {"_id": None, "max_id": {"$max": "$checklist_item_id"}}}
        ]
        
        cursor = checklist_collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        
        if result and result[0].get("max_id"):
            return result[0]["max_id"] + 1
        else:
            return 1
    
    def map_priority(self, risk_level: str, risk_score: float) -> PriorityLevel:
        """
        Map analytics priority to SCS priority level
        """
        if risk_level == "High":
            if risk_score >= 80:
                return PriorityLevel.CRITICAL
            else:
                return PriorityLevel.HIGH
        elif risk_level == "Medium":
            return PriorityLevel.MEDIUM
        else:
            return PriorityLevel.LOW
    
    def build_ai_explanation(self, profile: Dict) -> Dict[str, Any]:
        """
        Build detailed AI explanation from profile metrics
        """
        return {
            "risk_score": profile.get("risk_score", 0),
            "risk_level": profile.get("risk_level", "Unknown"),
            "component_scores": {
                "distortion_rate": profile.get("distortion_rate", 0),
                "sentiment_std": profile.get("sentiment_std", 0),
                "negative_sentiment_rate": profile.get("negative_sentiment_rate", 0),
                "distress_emotion_rate": profile.get("distress_emotion_rate", 0)
            },
            "key_signals": profile.get("key_signals", []),
            "statistics": {
                "total_comments": profile.get("total_comments_received", 0),
                "total_captions": profile.get("total_captions", 0),
                "late_night_activity": profile.get("late_night_activity_rate", 0)
            },
            "emotion_distribution": profile.get("emotion_distribution", {}),
            "distortion_categories": profile.get("distortion_categories", {})
        }
    
    async def case_exists(self, user_id: str) -> Optional[Dict]:
        """
        Check if case already exists for this user
        """
        cases_collection = self.db.scs_cases
        return await cases_collection.find_one({"user_id": user_id})
    
    async def create_case(self, profile: Dict) -> str:
        """
        Create new case from risk profile
        """
        cases_collection = self.db.scs_cases
        
        # Generate case ID
        case_id = await self.get_next_case_id()
        
        # Map priority
        priority = self.map_priority(
            profile.get("risk_level", "Low"),
            profile.get("risk_score", 0)
        )
        
        # Build AI explanation
        ai_explanation = self.build_ai_explanation(profile)
        
        # Create case document
        case = SCSCaseModel(
            case_id=case_id,
            user_id=profile["case_user"],
            assigned_to=None,
            current_risk_score=profile["risk_score"],
            category=self.determine_category(profile),
            ai_explanation=ai_explanation,
            priority=priority,
            case_status=CaseStatus.UNASSIGNED,
            work_status=WorkStatus.NOT_STARTED
        )
        
        # Insert case
        await cases_collection.insert_one(case.dict())
        logger.info(f"Created new case: {case_id} for user {profile['case_user']}")
        
        return case_id
    
    async def update_case(self, case: Dict, profile: Dict) -> None:
        """
        Update existing case with new risk data
        Preserves workflow fields (assigned_to, case_status, work_status)
        """
        cases_collection = self.db.scs_cases
        
        # Map priority
        priority = self.map_priority(
            profile.get("risk_level", "Low"),
            profile.get("risk_score", 0)
        )
        
        # Build updated AI explanation
        ai_explanation = self.build_ai_explanation(profile)
        
        # Update only AI-generated fields, preserve workflow fields
        update_data = {
            "$set": {
                "current_risk_score": profile["risk_score"],
                "category": self.determine_category(profile),
                "ai_explanation": ai_explanation,
                "priority": priority,
                "updated_at": datetime.utcnow()
            }
        }
        
        await cases_collection.update_one(
            {"case_id": case["case_id"]},
            update_data
        )
        
        logger.info(f"Updated case: {case['case_id']} for user {profile['case_user']}")
    
    async def add_history_entry(self, case_id: str, profile: Dict) -> int:
        """
        Add history entry for a case
        Returns history_id
        """
        history_collection = self.db.scs_case_history
        
        # Get next history ID
        history_id = await self.get_next_history_id(case_id)
        
        # Build AI explanation
        ai_explanation = self.build_ai_explanation(profile)
        
        # Create history entry
        history_entry = SCSCaseHistoryModel(
            history_id=history_id,
            case_id=case_id,
            risk_score=profile["risk_score"],
            category=self.determine_category(profile),
            ai_explanation=ai_explanation,
            ingestion_date=datetime.utcnow(),
            model_version=self.model_version
        )
        
        await history_collection.insert_one(history_entry.dict())
        logger.info(f"Added history entry {history_id} for case {case_id}")
        
        return history_id
    
    async def create_checklist_items(self, case_id: str, templates: List[Dict]) -> List[int]:
        """
        Create checklist items for a new case from templates
        Returns list of created checklist_item_ids
        """
        checklist_collection = self.db.scs_checklist
        created_ids = []
        
        for template in templates:
            # Get next item ID
            item_id = await self.get_next_checklist_item_id(case_id)
            
            # Create checklist item
            checklist_item = SCSChecklistItemModel(
                checklist_item_id=item_id,
                case_id=case_id,
                template_id=template["template_id"],
                label=template["label"],
                is_mandatory=template["is_mandatory"],
                display_order=template["display_order"]
            )
            
            await checklist_collection.insert_one(checklist_item.dict())
            created_ids.append(item_id)
        
        logger.info(f"Created {len(created_ids)} checklist items for case {case_id}")
        return created_ids
    
    def determine_category(self, profile: Dict) -> str:
        """
        Determine category based on profile metrics
        """
        emotion_dist = profile.get("emotion_distribution", {})
        distress_rate = profile.get("distress_emotion_rate", 0)
        distortion_rate = profile.get("distortion_rate", 0)
        risk_level = profile.get("risk_level", "Low")
        
        # Check for specific patterns
        if emotion_dist.get("anger", 0) > emotion_dist.get("joy", 0) and emotion_dist.get("anger", 0) > 3:
            if risk_level in ["High", "Medium"]:
                return "anger_frustration"
        
        if emotion_dist.get("sadness", 0) > 3:
            if distress_rate > 0.4:
                return "depression_risk"
            else:
                return "sadness_isolation"
        
        if distortion_rate > 0.3:
            return "cognitive_distortion"
        
        # Default categories based on risk level
        if risk_level == "High":
            return "high_risk_monitoring"
        elif risk_level == "Medium":
            return "moderate_risk_monitoring"
        else:
            return "low_risk_monitoring"
    
    async def promote_profile(self, profile: Dict, templates: List[Dict]) -> Dict[str, Any]:
        """
        Promote a single risk profile to case management
        """
        result = {
            "user_id": profile["case_user"],
            "case_created": False,
            "case_updated": False,
            "history_added": False,
            "case_id": None,
            "error": None
        }
        
        try:
            # Check if case exists
            existing_case = await self.case_exists(profile["case_user"])
            
            if existing_case:
                # Update existing case
                await self.update_case(existing_case, profile)
                case_id = existing_case["case_id"]
                result["case_updated"] = True
                result["case_id"] = case_id
            else:
                # Create new case
                case_id = await self.create_case(profile)
                result["case_created"] = True
                result["case_id"] = case_id
                
                # Create checklist items for new case
                await self.create_checklist_items(case_id, templates)
            
            # Add history entry (always)
            await self.add_history_entry(case_id, profile)
            result["history_added"] = True
            
        except Exception as e:
            logger.error(f"Error promoting profile for {profile['case_user']}: {e}")
            result["error"] = str(e)
        
        return result
    
    async def promote_all_profiles(
        self,
        min_priority: str = "medium",
        limit: Optional[int] = None,
        ingestion_timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Promote all eligible risk profiles to case management
        
        Args:
            min_priority: Minimum priority to promote ("low", "medium", "high", "critical")
            limit: Maximum number of profiles to process
            ingestion_timestamp: Timestamp for this ingestion cycle
            
        Returns:
            Summary results
        """
        start_time = datetime.utcnow()
        logger.info("=" * 60)
        logger.info("Starting Case Promotion Service")
        logger.info("=" * 60)
        
        # Step 1: Ensure checklist templates exist
        templates = await self.ensure_checklist_templates()
        logger.info(f"Found {len(templates)} checklist templates")
        
        # Step 2: Get risk profiles from analytics
        risk_profiles_collection = self.db.case_risk_profiles
        
        # Build query based on priority filter
        query = {}
        if min_priority == "critical":
            query["risk_level"] = "High"
            query["risk_score"] = {"$gte": 80}
        elif min_priority == "high":
            query["risk_level"] = "High"
        elif min_priority == "medium":
            query["risk_level"] = {"$in": ["High", "Medium"]}
        # "low" includes all
        
        # Get profiles
        cursor = risk_profiles_collection.find(query).sort("risk_score", -1)
        if limit:
            cursor = cursor.limit(limit)
        
        profiles = await cursor.to_list(length=None)
        logger.info(f"Found {len(profiles)} eligible risk profiles")
        
        if not profiles:
            return {
                "status": "success",
                "message": "No eligible profiles found",
                "profiles_read": 0,
                "profiles_filtered": 0,
                "cases_created": 0,
                "cases_updated": 0,
                "history_entries_added": 0,
                "errors": []
            }
        
        # Step 3: Promote each profile
        results = []
        for profile in profiles:
            logger.info(f"Processing {profile['case_user']}...")
            result = await self.promote_profile(profile, templates)
            results.append(result)
        
        # Step 4: Compile statistics
        stats = {
            "profiles_read": len(profiles),
            "profiles_filtered": len(profiles),
            "cases_created": sum(1 for r in results if r["case_created"]),
            "cases_updated": sum(1 for r in results if r["case_updated"]),
            "history_entries_added": sum(1 for r in results if r["history_added"]),
            "checklist_items_created": len(templates) * sum(1 for r in results if r["case_created"]),
            "errors": [r["error"] for r in results if r["error"]]
        }
        
        # Step 5: Log summary
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.success(f"Promotion completed in {duration:.2f} seconds")
        logger.info(f"Profiles read: {stats['profiles_read']}")
        logger.info(f"Cases created: {stats['cases_created']}")
        logger.info(f"Cases updated: {stats['cases_updated']}")
        logger.info(f"History entries added: {stats['history_entries_added']}")
        logger.info(f"Checklist items created: {stats['checklist_items_created']}")
        if stats['errors']:
            logger.error(f"Errors: {len(stats['errors'])}")
        logger.info("=" * 60)
        
        return {
            "status": "success",
            "message": f"Promoted {stats['cases_created']} new cases, updated {stats['cases_updated']} existing cases",
            "results": stats,
            "started_at": start_time.isoformat(),
            "duration_seconds": duration,
            "ingestion_timestamp": ingestion_timestamp or start_time
        }


# Convenience function for simple usage
async def promote_risk_profiles_to_scs_cases(
    db: AsyncIOMotorDatabase,
    min_priority: str = "medium",
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Convenience function to promote risk profiles to SCS cases
    
    Args:
        db: MongoDB database connection
        min_priority: Minimum priority to promote
        limit: Maximum number of profiles to process
        
    Returns:
        Promotion results
    """
    service = CasePromotionService(db)
    return await service.promote_all_profiles(
        min_priority=min_priority,
        limit=limit
    )