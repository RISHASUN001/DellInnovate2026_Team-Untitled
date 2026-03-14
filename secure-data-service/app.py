

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from auth import verify_jwt
from models import StoreRequest
from database import store_record, collection
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('secure-data-service')

@app.post('/internal/store')
async def store_data(request: Request, data: StoreRequest, token: str = Depends(verify_jwt)):
    try:
        record_id = store_record(data)
        logger.info('Stored record_id: %s', record_id)
        return {'status': 'stored', 'record_id': str(record_id)}
    except Exception as e:
        logger.error('Error storing record: %s', str(e))
        return JSONResponse(status_code=500, content={"status": "error", "detail": "Internal server error"})


# GET endpoint for all authorized services (JWT required, restrict by service claim and scope)
@app.get('/internal/data')
async def get_data(token: dict = Depends(verify_jwt)):
    allowed_services = [
        'analysis-service',
        'chatbot-service',
        'image-service',
        'mcp-service',
        'case-service'
    ]
    if token.get('service') not in allowed_services:
        logger.warning('Unauthorized data access attempt by: %s', token.get('service'))
        raise HTTPException(status_code=403, detail='Forbidden')
    if token.get('scope') not in ['read:personal_data', 'analyze:personal_data']:
        logger.warning('Unauthorized data scope by: %s', token.get('scope'))
        raise HTTPException(status_code=403, detail='Forbidden')
    # Optionally filter data by service or add more logic here
    docs = list(collection.find({}, {'_id': 0}))
    return {'data': docs}
