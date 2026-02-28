"""
Stage 2: PCA-based Risk Profiling with LLM Calibration

Replaces hand-coded feature engineering with:
1. Aggregation: mean + p90 weighting for emotion/sentiment/harm scores
2. Low-data damping: sigmoid function for small sample sizes
3. PCA weight learning: principal component analysis across users
4. Guardrail: prevent harm_score underweighting
5. LLM calibration: bounded delta adjustment (±0.10)
"""

import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from loguru import logger
import uuid

from .llm_calibration import calibrate_with_llm


def sigmoid(x: float) -> float:
    """Sigmoid function for damping"""
    return 1.0 / (1.0 + np.exp(-x))


def compute_damping_factor(n_units: int, 
                          threshold: int = 8, 
                          steepness: float = 3.0) -> float:
    """
    Compute damping factor for low sample sizes
    
    Args:
        n_units: Number of text units
        threshold: Center point for sigmoid
        steepness: Controls sigmoid steepness
        
    Returns:
        Damping factor (0-1)
    """
    return sigmoid((n_units - threshold) / steepness)


def aggregation_mean_p90(values: np.ndarray, 
                         mean_weight: float = 0.7,
                         p90_weight: float = 0.3) -> float:
    """
    Weighted combination of mean and 90th percentile
    
    Args:
        values: Array of values
        mean_weight: Weight for mean (default: 0.7)
        p90_weight: Weight for p90 (default: 0.3)
        
    Returns:
        Aggregated score
    """
    if len(values) == 0:
        return 0.0
    
    mean_val = float(np.mean(values))
    p90_val = float(np.percentile(values, 90))
    
    return mean_weight * mean_val + p90_weight * p90_val


def apply_guardrail(risk_score_math: float, 
                   harm_score: float,
                   harm_weight: float = 0.40) -> float:
    """
    Apply guardrail: base_score ≥ harm_weight * harm_score
    
    Prevents PCA from underweighting severe distortions
    
    Args:
        risk_score_math: PCA-derived risk score
        harm_score: Harm/distortion score
        harm_weight: Minimum weight for harm (default: 0.40)
        
    Returns:
        Guardrailed base score
    """
    floor = harm_weight * harm_score
    return max(risk_score_math, floor)


async def aggregate_user_signals(db: AsyncIOMotorDatabase,
                                 username: str,
                                 window_days: int = 30) -> Optional[Dict]:
    """
    Aggregate signals for a single user
    
    Args:
        db: MongoDB database
        username: User to aggregate
        window_days: Time window for signals
        
    Returns:
        Dict with aggregated scores or None if insufficient data
    """
    cutoff_date = datetime.now() - timedelta(days=window_days)
    
    # Query signals
    signals = await db.text_units_signals.find({
        'case_user': username,
        'created_at': {'$gte': cutoff_date}
    }).to_list(length=None)
    
    if not signals:
        logger.debug(f"No signals for {username}")
        return None
    
    n_units = len(signals)
    
    # Extract arrays
    distress_emotions = []
    is_negatives = []
    distortion_flags = []
    distortion_scores = []
    unit_ids = []
    
    for sig in signals:
        distress_emotions.append(sig.get('distress_emotion', 0.0))
        is_negatives.append(sig.get('is_negative', 0))
        distortion_flags.append(sig.get('distortion_flag', 0))
        distortion_scores.append(sig.get('distortion_score', 0.0))
        unit_ids.append(str(sig['_id']))
    
    distress_emotions = np.array(distress_emotions)
    is_negatives = np.array(is_negatives)
    distortion_flags = np.array(distortion_flags)
    distortion_scores = np.array(distortion_scores)
    
    # Aggregate scores using mean + p90
    emotion_score = aggregation_mean_p90(distress_emotions)
    sentiment_score = aggregation_mean_p90(is_negatives)
    harm_score = aggregation_mean_p90(distortion_flags)
    
    # Compute damping factor
    damp = compute_damping_factor(n_units)
    
    # Apply damping
    emotion_score *= damp
    sentiment_score *= damp
    harm_score *= damp
    
    # Select evidence units
    # Top 3 by distress_emotion
    top_distress_idx = np.argsort(distress_emotions)[-3:][::-1]
    # Top 3 by distortion_score
    top_distortion_idx = np.argsort(distortion_scores)[-3:][::-1]
    # Combine and deduplicate
    evidence_idx = np.unique(np.concatenate([top_distress_idx, top_distortion_idx]))
    evidence_unit_ids = [unit_ids[i] for i in evidence_idx]
    
    # Get evidence texts
    evidence_texts = []
    for idx in evidence_idx:
        sig = signals[idx]
        text = sig.get('text', '')[:200]  # Truncate long texts
        evidence_texts.append(text)
    
    return {
        'username': username,
        'n_units': n_units,
        'emotion_score': emotion_score,
        'sentiment_score': sentiment_score,
        'harm_score': harm_score,
        'damp': damp,
        'evidence_unit_ids': evidence_unit_ids,
        'evidence_texts': evidence_texts,
        'signals': signals  # Keep for later reference
    }


async def run_pca_scoring(aggregated_users: List[Dict],
                         pca_run_id: str) -> List[Dict]:
    """
    Apply PCA to learn weights and compute risk scores
    
    Args:
        aggregated_users: List of user aggregation dicts
        pca_run_id: Unique identifier for this PCA run
        
    Returns:
        List of users with PCA scores added
    """
    if len(aggregated_users) < 2:
        logger.warning("Not enough users for PCA, using direct average")
        # Fallback: simple average
        for user_data in aggregated_users:
            risk_score_math = (user_data['emotion_score'] + 
                             user_data['sentiment_score'] + 
                             user_data['harm_score']) / 3.0
            user_data['risk_score_math'] = risk_score_math
            user_data['pc1_loadings'] = {'emotion': 0.33, 'sentiment': 0.33, 'harm': 0.33}
            user_data['pca_run_id'] = pca_run_id
        return aggregated_users
    
    # Build feature matrix
    X = np.array([
        [u['emotion_score'], u['sentiment_score'], u['harm_score']]
        for u in aggregated_users
    ])
    
    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # PCA
    pca = PCA(n_components=1)
    pc1_scores = pca.fit_transform(X_scaled).flatten()
    
    # Get loadings (weights)
    loadings = pca.components_[0]
    
    logger.info(f"PCA loadings: emotion={loadings[0]:.3f}, "
               f"sentiment={loadings[1]:.3f}, harm={loadings[2]:.3f}")
    
    # Normalize PC1 scores to [0, 1]
    pc1_min = pc1_scores.min()
    pc1_max = pc1_scores.max()
    
    if pc1_max - pc1_min > 1e-6:
        pc1_normalized = (pc1_scores - pc1_min) / (pc1_max - pc1_min)
    else:
        pc1_normalized = np.ones_like(pc1_scores) * 0.5
    
    # Add PCA results to user data
    for i, user_data in enumerate(aggregated_users):
        user_data['risk_score_math'] = float(pc1_normalized[i])
        user_data['pc1_loadings'] = {
            'emotion': float(loadings[0]),
            'sentiment': float(loadings[1]),
            'harm': float(loadings[2])
        }
        user_data['pca_run_id'] = pca_run_id
    
    return aggregated_users


async def apply_guardrails_and_llm(db: AsyncIOMotorDatabase,
                                   user_data: Dict,
                                   use_llm: bool = True,
                                   llm_model: str = "llama2",
                                   ollama_url: str = "http://localhost:11434") -> Dict:
    """
    Apply guardrails and LLM calibration to compute final score
    
    Args:
        db: MongoDB database
        user_data: User aggregation with PCA score
        use_llm: Whether to use LLM calibration
        llm_model: Ollama model name
        ollama_url: Ollama endpoint
        
    Returns:
        User data with final_score and priority_level
    """
    # Apply guardrail
    base_score = apply_guardrail(
        user_data['risk_score_math'],
        user_data['harm_score']
    )
    user_data['base_score'] = base_score
    
    # LLM calibration
    llm_delta = 0.0
    if use_llm:
        try:
            llm_result = await calibrate_with_llm(
                case_user=user_data['username'],
                emotion_score=user_data['emotion_score'],
                sentiment_score=user_data['sentiment_score'],
                harm_score=user_data['harm_score'],
                n_units=user_data['n_units'],
                evidence_texts=user_data['evidence_texts'],
                model=llm_model,
                ollama_url=ollama_url
            )
            llm_delta = llm_result['llm_delta']
            user_data['llm_delta1'] = llm_result.get('delta1', 0.0)
            user_data['llm_delta2'] = llm_result.get('delta2', 0.0)
        except Exception as e:
            logger.error(f"LLM calibration failed for {user_data['username']}: {e}")
            llm_delta = 0.0
    
    user_data['llm_delta'] = llm_delta
    
    # Final score
    final_score = base_score + llm_delta
    final_score = max(0.0, min(1.0, final_score))  # Clamp [0, 1]
    user_data['final_score'] = final_score
    
    # Priority level
    if final_score >= 0.75:
        priority_level = 'critical'
    elif final_score >= 0.50:
        priority_level = 'high'
    elif final_score >= 0.30:
        priority_level = 'medium'
    else:
        priority_level = 'low'
    
    user_data['priority_level'] = priority_level
    
    return user_data


async def run_case_scoring(db: AsyncIOMotorDatabase,
                          window_days: int = 30,
                          limit_users: Optional[int] = None,
                          use_llm: bool = True,
                          llm_model: str = "llama2",
                          ollama_url: str = "http://localhost:11434") -> Dict:
    """
    Run complete Stage 2: PCA-based risk profiling with LLM calibration
    
    Args:
        db: MongoDB database
        window_days: Time window for signals
        limit_users: Limit number of users (for testing)
        use_llm: Whether to use LLM calibration
        llm_model: Ollama model name
        ollama_url: Ollama endpoint
        
    Returns:
        Dict with success flag, n_profiles, profiles
    """
    logger.info(f"Running Stage 2 PCA scoring (window={window_days} days)...")
    
    # Get distinct usernames from signals
    cutoff_date = datetime.now() - timedelta(days=window_days)
    pipeline_usernames = [
        {'$match': {'created_at': {'$gte': cutoff_date}}},
        {'$group': {'_id': '$case_user'}},
        {'$project': {'username': '$_id', '_id': 0}}
    ]
    
    if limit_users:
        pipeline_usernames.append({'$limit': limit_users})
    
    usernames_cursor = db.text_units_signals.aggregate(pipeline_usernames)
    usernames = [doc['username'] async for doc in usernames_cursor]
    
    logger.info(f"Found {len(usernames)} users with signals")
    
    if not usernames:
        return {
            'success': False,
            'message': 'No users with signals in time window',
            'n_profiles': 0,
            'profiles': []
        }
    
    # Step 1: Aggregate per-user signals
    logger.info("Aggregating per-user signals...")
    aggregated_users = []
    for username in usernames:
        user_data = await aggregate_user_signals(db, username, window_days)
        if user_data:
            aggregated_users.append(user_data)
    
    logger.info(f"Aggregated {len(aggregated_users)} users")
    
    if not aggregated_users:
        return {
            'success': False,
            'message': 'No users with sufficient data',
            'n_profiles': 0,
            'profiles': []
        }
    
    # Step 2: Run PCA scoring
    pca_run_id = str(uuid.uuid4())[:8]
    logger.info(f"Running PCA (run_id={pca_run_id})...")
    aggregated_users = await run_pca_scoring(aggregated_users, pca_run_id)
    
    # Step 3: Apply guardrails and LLM calibration
    logger.info("Applying guardrails and LLM calibration...")
    final_profiles = []
    for i, user_data in enumerate(aggregated_users):
        logger.info(f"Processing user {i+1}/{len(aggregated_users)}: {user_data['username']}")
        user_data = await apply_guardrails_and_llm(
            db, user_data, use_llm, llm_model, ollama_url
        )
        final_profiles.append(user_data)
    
    # Step 4: Store in MongoDB
    logger.info("Storing risk profiles in MongoDB...")
    for profile in final_profiles:
        profile_doc = {
            'case_user': profile['username'],
            'timestamp': datetime.now(),
            'window_days': window_days,
            # New PCA-based scores
            'emotion_score': profile['emotion_score'],
            'sentiment_score': profile['sentiment_score'],
            'harm_score': profile['harm_score'],
            'n_units': profile['n_units'],
            'damp': profile['damp'],
            'risk_score_math': profile['risk_score_math'],
            'base_score': profile['base_score'],
            'llm_delta': profile['llm_delta'],
            'llm_delta1': profile.get('llm_delta1', 0.0),
            'llm_delta2': profile.get('llm_delta2', 0.0),
            'final_score': profile['final_score'],
            'priority_level': profile['priority_level'],
            'pc1_loadings': profile['pc1_loadings'],
            'pca_run_id': profile['pca_run_id'],
            'evidence_unit_ids': profile['evidence_unit_ids'],
            # Legacy fields (for backward compatibility)
            'risk_score': profile['final_score'] * 100,  # Convert to 0-100
            'metrics': {
                'emotion_score': profile['emotion_score'],
                'sentiment_score': profile['sentiment_score'],
                'harm_score': profile['harm_score']
            }
        }
        
        # Upsert
        await db.case_risk_profiles.update_one(
            {'case_user': profile['username']},
            {'$set': profile_doc},
            upsert=True
        )
    
    logger.info(f"✓ Stage 2 complete: {len(final_profiles)} risk profiles stored")
    
    return {
        'success': True,
        'n_profiles': len(final_profiles),
        'profiles': final_profiles,
        'pca_run_id': pca_run_id
    }
