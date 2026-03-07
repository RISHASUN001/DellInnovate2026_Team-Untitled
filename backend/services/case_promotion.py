"""
Case Promotion Service

Bridges NLP analytics output to operational SCS case management tables.
Transforms risk profiles from case_risk_profiles → scs_cases + scs_case_history
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase


class CasePromotionService:
    """
    Promotes NLP analytics outputs to operational SCS tables.
    
    Flow:
    1. Read aggregated risk profiles from case_risk_profiles
    2. Filter based on priority threshold
    3. Upsert into scs_cases (create new or update existing)
    4. Append history to scs_case_history
    5. Create mandatory checklist items for new cases
    """
    
    def __init__(self, db: AsyncIOMotorDatabase, source_db: AsyncIOMotorDatabase = None):
        """Initialize case promotion service.
        
        Args:
            db: Operational database (dellinnovate) for writing cases
            source_db: Source database (instagram_scraper) for reading profiles
        """
        self.db = db  # dellinnovate - for writing
        self.source_db = source_db  # instagram_scraper - for reading
        self.version = "promotion-v1.0"
    
    
    async def promote_profiles_to_cases(
        self,
        min_priority: Optional[str] = "low",
        limit: Optional[int] = None,
        ingestion_timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Main promotion function. Reads case_risk_profiles and populates SCS tables.
        
        Args:
            min_priority: Minimum priority level to create cases ('low', 'medium', 'high', 'critical')
            limit: Maximum number of profiles to process (for testing)
            ingestion_timestamp: Timestamp for this ingestion cycle (defaults to now)
        
        Returns:
            Dictionary with promotion statistics
        """
        if ingestion_timestamp is None:
            ingestion_timestamp = datetime.utcnow()
        
        logger.info(f"Starting case promotion: min_priority={min_priority}, limit={limit}")
        
        # Priority ordering for filtering
        priority_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        min_priority_value = priority_order.get(min_priority.lower(), 1)
        
        # Statistics
        stats = {
            "profiles_read": 0,
            "profiles_filtered": 0,
            "cases_created": 0,
            "cases_updated": 0,
            "history_entries_added": 0,
            "checklist_items_created": 0,
            "errors": []
        }
        
        try:
            # Step 1: Read latest risk profiles
            profiles = await self._get_latest_risk_profiles(limit=limit)
            stats["profiles_read"] = len(profiles)
            
            if not profiles:
                logger.warning("No risk profiles found to promote")
                return stats
            
            logger.info(f"Retrieved {len(profiles)} risk profiles")
            
            # Step 2: Filter profiles based on priority threshold
            filtered_profiles = [
                p for p in profiles
                if priority_order.get(p.get("priority_level", "low").lower(), 0) >= min_priority_value
            ]
            stats["profiles_filtered"] = len(filtered_profiles)
            
            logger.info(f"Filtered to {len(filtered_profiles)} profiles meeting priority threshold")
            
            # Step 3: Process each profile
            for profile in filtered_profiles:
                try:
                    result = await self._process_single_profile(profile, ingestion_timestamp)
                    
                    if result["is_new_case"]:
                        stats["cases_created"] += 1
                        stats["checklist_items_created"] += result["checklist_items_created"]
                    else:
                        stats["cases_updated"] += 1
                    
                    stats["history_entries_added"] += 1
                    
                except Exception as e:
                    error_msg = f"Failed to process profile for {profile.get('case_user', 'unknown')}: {e}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)
            
            logger.info(f"Promotion complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Case promotion failed: {e}")
            stats["errors"].append(str(e))
            raise
    
    
    async def _get_latest_risk_profiles(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Retrieve latest risk profiles from case_risk_profiles collection.
        Gets one profile per user (most recent by timestamp).
        """
        pipeline = [
            # Sort by timestamp descending
            {"$sort": {"timestamp": -1}},
            
            # Group by case_user to get latest profile per user
            {
                "$group": {
                    "_id": "$case_user",
                    "latest_profile": {"$first": "$$ROOT"}
                }
            },
            
            # Replace root with the latest profile
            {"$replaceRoot": {"newRoot": "$latest_profile"}}
        ]
        
        if limit:
            pipeline.append({"$limit": limit})
        
        # Read from SOURCE database (instagram_scraper)
        profiles = await self.source_db.case_risk_profiles.aggregate(pipeline).to_list(length=None)
        return profiles
    
    
    async def _process_single_profile(
        self,
        profile: Dict,
        ingestion_timestamp: datetime
    ) -> Dict[str, Any]:
        """
        Process a single risk profile: upsert case, add history, create checklist if new.
        
        Returns:
            Dictionary with processing results
        """
        monitored_user = profile.get("case_user")
        if not monitored_user:
            raise ValueError("Profile missing case_user field")
        
        logger.debug(f"Processing profile for user: {monitored_user}")
        
        # Check if case already exists
        existing_case = await self.db.scs_cases.find_one({"user_id": monitored_user})
        is_new_case = existing_case is None
        
        if is_new_case:
            # Create new case
            case_id = await self._create_new_case(profile, ingestion_timestamp)
            
            # Create history entry
            await self._add_case_history(case_id, profile, ingestion_timestamp)
            
            # Create mandatory checklist items
            checklist_count = await self._create_checklist_items(case_id)
            
            logger.info(f"Created new case {case_id} for user {monitored_user}")
            
            return {
                "is_new_case": True,
                "case_id": case_id,
                "checklist_items_created": checklist_count
            }
        
        else:
            # Update existing case
            case_id = existing_case["case_id"]
            await self._update_existing_case(case_id, profile, ingestion_timestamp)
            
            # Add history entry
            await self._add_case_history(case_id, profile, ingestion_timestamp)
            
            logger.info(f"Updated existing case {case_id} for user {monitored_user}")
            
            return {
                "is_new_case": False,
                "case_id": case_id,
                "checklist_items_created": 0
            }
    
    
    async def _create_new_case(
        self,
        profile: Dict,
        ingestion_timestamp: datetime
    ) -> str:
        """
        Create a new case in scs_cases collection.
        
        Returns:
            Generated case_id
        """
        monitored_user = profile.get("case_user")
        
        # Generate case_id
        year = ingestion_timestamp.year
        counter = await self._get_next_sequence_id("scs_cases", "case_id")
        case_id = f"CASE_{year}_{counter:03d}"
        
        # Map priority_level from analytics to priority
        priority = self._map_priority(profile)
        
        # Extract risk category
        category = self._extract_category(profile)
        
        # Get risk score (handle both legacy and PCA scoring)
        risk_score = self._extract_risk_score(profile)
        
        # Build AI explanation
        ai_explanation = self._build_ai_explanation(profile)
        
        # Create case document
        case_doc = {
            "case_id": case_id,
            "user_id": monitored_user,  # Social media handle
            "assigned_to": None,  # Unassigned initially
            "current_risk_score": risk_score,
            "category": category,
            "ai_explanation": ai_explanation,
            "case_status": "unassigned",
            "work_status": "not_started",
            "priority": priority,
            "created_at": ingestion_timestamp,
            "updated_at": ingestion_timestamp
        }
        
        # Insert into database
        await self.db.scs_cases.insert_one(case_doc)
        
        logger.info(f"Created case {case_id} with priority={priority}, category={category}")
        
        return case_id
    
    
    async def _update_existing_case(
        self,
        case_id: str,
        profile: Dict,
        ingestion_timestamp: datetime
    ):
        """
        Update an existing case with new risk data.
        Only updates AI-driven fields, preserves workflow fields.
        """
        priority = self._map_priority(profile)
        category = self._extract_category(profile)
        risk_score = self._extract_risk_score(profile)
        ai_explanation = self._build_ai_explanation(profile)
        
        # Update only AI-driven fields
        update_doc = {
            "$set": {
                "current_risk_score": risk_score,
                "category": category,
                "ai_explanation": ai_explanation,
                "priority": priority,
                "updated_at": ingestion_timestamp
            }
        }
        
        await self.db.scs_cases.update_one(
            {"case_id": case_id},
            update_doc
        )
        
        logger.debug(f"Updated case {case_id} with new risk data")
    
    
    async def _add_case_history(
        self,
        case_id: str,
        profile: Dict,
        ingestion_timestamp: datetime
    ):
        """
        Append a history entry to scs_case_history.
        Always creates a new entry for each ingestion cycle.
        """
        history_id = await self._get_next_sequence_id("scs_case_history", "history_id")
        
        risk_score = self._extract_risk_score(profile)
        category = self._extract_category(profile)
        ai_explanation = self._build_ai_explanation(profile)
        
        # Determine model version
        model_version = profile.get("model_version", "nlp-v1")
        if "pca_run_id" in profile:
            model_version += "-pca-v1"
        if profile.get("llm_delta") is not None:
            model_version += "-llm-v1"
        
        history_doc = {
            "history_id": history_id,
            "case_id": case_id,
            "risk_score": risk_score,
            "category": category,
            "ai_explanation": ai_explanation,
            "ingestion_date": ingestion_timestamp,
            "model_version": model_version
        }
        
        await self.db.scs_case_history.insert_one(history_doc)
        
        logger.debug(f"Added history entry for case {case_id}")
    
    
    async def _create_checklist_items(self, case_id: str) -> int:
        """
        Create mandatory checklist items for a new case based on templates.
        
        Returns:
            Number of checklist items created
        """
        # Get active mandatory templates
        templates = await self.db.scs_checklist_templates.find(
            {"is_mandatory": True, "is_active": True}
        ).sort("display_order", 1).to_list(length=None)
        
        if not templates:
            logger.warning("No checklist templates found")
            return 0
        
        checklist_items = []
        for template in templates:
            checklist_item_id = await self._get_next_sequence_id("scs_checklist", "checklist_item_id")
            
            item_doc = {
                "checklist_item_id": checklist_item_id,
                "case_id": case_id,
                "template_id": template["template_id"],
                "label": template["label"],
                "is_mandatory": True,
                "completed": False,
                "comments": [],
                "completed_at": None,
                "completed_by": None,
                "display_order": template["display_order"],
                "created_at": datetime.utcnow()
            }
            
            checklist_items.append(item_doc)
        
        if checklist_items:
            await self.db.scs_checklist.insert_many(checklist_items)
            logger.info(f"Created {len(checklist_items)} checklist items for case {case_id}")
        
        return len(checklist_items)
    
    
    async def _get_next_sequence_id(self, collection_name: str, field_name: str) -> int:
        """
        Auto-increment ID generator using counters collection.
        """
        counter_col = self.db['counters']
        
        result = await counter_col.find_one_and_update(
            {'_id': f"{collection_name}_{field_name}"},
            {'$inc': {'seq': 1}},
            upsert=True,
            return_document=True
        )
        
        return result['seq']
    
    
    def _map_priority(self, profile: Dict) -> str:
        """
        Map analytics priority to SCS priority (handles multiple formats).
        """
        # Check for integer priority (BehavioralFeatureEngineer: 1=High, 2=Medium, 3=Low)
        if "priority" in profile and isinstance(profile["priority"], int):
            priority_int_mapping = {
                1: "high",
                2: "medium",
                3: "low"
            }
            return priority_int_mapping.get(profile["priority"], "medium")
        
        # Check for risk_level string (BehavioralFeatureEngineer)
        if "risk_level" in profile:
            return profile["risk_level"].lower()
        
        # Check for priority_level string (legacy)
        priority_level = profile.get("priority_level", "").lower()
        
        priority_mapping = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low"
        }
        
        return priority_mapping.get(priority_level, "medium")
    
    
    def _extract_category(self, profile: Dict) -> str:
        """
        Extract risk category from profile.
        """
        # Try different possible category field names
        category = (
            profile.get("category") or
            profile.get("risk_category") or
            profile.get("dominant_category") or
            profile.get("risk_level") or  # BehavioralFeatureEngineer uses risk_level
            "Unknown"
        )
        
        return category
    
    
    def _extract_risk_score(self, profile: Dict) -> float:
        """
        Extract risk score from profile (handles multiple scoring methods).
        """
        # Try BehavioralFeatureEngineer risk_score (0-100 scale)
        if "risk_score" in profile:
            return round(profile["risk_score"], 2)
        
        # Try PCA final_score (0-1 scale)
        if "final_score" in profile:
            return round(profile["final_score"] * 100, 2)  # Convert to 0-100 scale
        
        # Try legacy overall_risk_score
        if "overall_risk_score" in profile:
            return round(profile["overall_risk_score"], 2)
        
        # Fallback to base_score or risk_score_math
        if "base_score" in profile:
            return round(profile["base_score"] * 100, 2)
        
        if "risk_score_math" in profile:
            return round(profile["risk_score_math"] * 100, 2)
        
        logger.warning(f"No risk score found in profile, defaulting to 50.0")
        return 50.0
    
    
    def _build_ai_explanation(self, profile: Dict) -> str:
        """
        Build comprehensive AI explanation from profile data.
        """
        explanation_parts = []
        
        # Use existing explanation if available
        if "explanation" in profile:
            explanation_parts.append(profile["explanation"])
        
        # Add PCA-specific information
        if "pca_run_id" in profile:
            emotion_score = profile.get("emotion_score", 0)
            sentiment_score = profile.get("sentiment_score", 0)
            harm_score = profile.get("harm_score", 0)
            
            explanation_parts.append(
                f"Risk assessment based on aggregated signals: "
                f"emotion={emotion_score:.2f}, sentiment={sentiment_score:.2f}, harm={harm_score:.2f}."
            )
            
            # Add LLM calibration note
            if "llm_delta" in profile:
                llm_delta = profile["llm_delta"]
                explanation_parts.append(
                    f"LLM calibration applied: {llm_delta:+.2f} adjustment."
                )
        
        # Add behavioral metrics if available
        if "behavioral_metrics" in profile:
            metrics = profile["behavioral_metrics"]
            if "late_night_posts_ratio" in metrics:
                ratio = metrics["late_night_posts_ratio"]
                if ratio > 0.3:
                    explanation_parts.append(
                        f"High late-night activity detected ({ratio:.1%} of posts)."
                    )
        
        # Add distortion information
        if "distortion_metrics" in profile:
            dist = profile["distortion_metrics"]
            if dist.get("distortion_rate", 0) > 0.2:
                explanation_parts.append(
                    f"Cognitive distortions detected in {dist['distortion_rate']:.1%} of messages."
                )
        
        # Combine all parts
        if explanation_parts:
            return " ".join(explanation_parts)
        else:
            return "Risk detected through automated NLP analysis of social media content."


async def promote_risk_profiles_to_scs_cases(
    db: AsyncIOMotorDatabase,
    source_db: AsyncIOMotorDatabase = None,
    min_priority: str = "medium",
    limit: Optional[int] = None,
    ingestion_timestamp: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Convenience function to promote risk profiles to SCS cases.
    
    Args:
        db: MongoDB database connection (dellinnovate - operational)
        source_db: Source database (instagram_scraper - analytics), auto-detected if None
        min_priority: Minimum priority level to create cases
        limit: Maximum profiles to process (for testing)
        ingestion_timestamp: Timestamp for this cycle
    
    Returns:
        Statistics dictionary
    """
    from config.database import MongoDB
    
    # Auto-detect source database if not provided
    if source_db is None:
        source_db = MongoDB.get_source_db()
    
    service = CasePromotionService(db=db, source_db=source_db)
    return await service.promote_profiles_to_cases(
        min_priority=min_priority,
        limit=limit,
        ingestion_timestamp=ingestion_timestamp
    )
