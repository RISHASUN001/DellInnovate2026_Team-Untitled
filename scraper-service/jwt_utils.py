import jwt
import datetime
from typing import Any

def generate_jwt(private_key_path: str) -> str:
    with open(private_key_path, 'r') as f:
        private_key = f.read()
    now = datetime.datetime.utcnow()
    payload = {
        'service': 'scraper-service',
        'scope': 'write:personal_data',
        'iat': int(now.timestamp()),
        'exp': int((now + datetime.timedelta(minutes=5)).timestamp())
    }
    token = jwt.encode(payload, private_key, algorithm='RS256')
    return token
