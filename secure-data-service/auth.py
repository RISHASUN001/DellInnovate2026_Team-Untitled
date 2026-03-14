import jwt
import os
from fastapi import Header, HTTPException
from jwt import InvalidTokenError
from typing import Optional
import datetime

PUBLIC_KEY_PATH = os.getenv('PUBLIC_KEY_PATH')

with open(PUBLIC_KEY_PATH, 'r') as f:
    PUBLIC_KEY = f.read()

def verify_jwt(Authorization: Optional[str] = Header(None)):
    import logging
    logger = logging.getLogger("secure-data-service.jwt")
    if not Authorization or not Authorization.startswith('Bearer '):
        logger.error("Missing or invalid Authorization header: %s", Authorization)
        raise HTTPException(status_code=401, detail='Missing or invalid Authorization header')
    token = Authorization.split(' ')[1]
    logger.info("JWT token received: %s", token)
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=['RS256'])
        logger.info("JWT payload decoded: %s", payload)
        # Allow all backend services with correct claims
        allowed_services = [
            'scraper-service',
            'analysis-service',
            'chatbot-service',
            'image-service',
            'mcp-service',
            'case-service'
        ]
        allowed_scopes = [
            'write:personal_data',
            'read:personal_data',
            'analyze:personal_data'
        ]
        if payload.get('service') not in allowed_services:
            logger.error("Invalid service claim: %s", payload.get('service'))
            raise HTTPException(status_code=403, detail='Invalid service claim')
        if payload.get('scope') not in allowed_scopes:
            logger.error("Invalid scope claim: %s", payload.get('scope'))
            raise HTTPException(status_code=403, detail='Invalid scope claim')
        now = datetime.datetime.utcnow().timestamp()
        if payload.get('exp') < now:
            logger.error("Token expired: exp=%s now=%s", payload.get('exp'), now)
            raise HTTPException(status_code=401, detail='Token expired')
        return payload
    except Exception as e:
        import traceback
        logger.error("JWT decode error: %s", str(e))
        logger.error("Exception type: %s", type(e))
        logger.error("Stack trace:\n%s", traceback.format_exc())
        raise HTTPException(status_code=401, detail='Invalid token')
