import os
from pymongo import MongoClient
from models import StoreRequest

MONGO_URI = os.getenv('MONGO_URI')
client = MongoClient(MONGO_URI)
db = client['scraperdb']
collection = db['personal_data']

def store_record(data: StoreRequest):
    doc = data.dict()
    result = collection.insert_one(doc)
    return result.inserted_id
