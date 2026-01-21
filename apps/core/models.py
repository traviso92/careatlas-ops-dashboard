"""
Core models and MongoDB connection utilities.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId
from pymongo import MongoClient
from django.conf import settings


# MongoDB Connection
_client = None
_db = None


def get_db():
    """Get MongoDB database connection."""
    global _client, _db
    if _db is None:
        _client = MongoClient(settings.MONGODB_URI)
        _db = _client[settings.MONGODB_DATABASE]
    return _db


def get_collection(name: str):
    """Get a MongoDB collection."""
    return get_db()[name]


class BaseDocument:
    """Base class for MongoDB document models."""

    collection_name: str = None

    @classmethod
    def get_collection(cls):
        return get_collection(cls.collection_name)

    @classmethod
    def find_by_id(cls, doc_id: str):
        """Find document by ID."""
        if isinstance(doc_id, str):
            try:
                doc_id = ObjectId(doc_id)
            except:
                pass
        doc = cls.get_collection().find_one({'_id': doc_id})
        return doc

    @classmethod
    def find_one(cls, query: dict):
        """Find single document matching query."""
        return cls.get_collection().find_one(query)

    @classmethod
    def find(cls, query: dict = None, sort: list = None, limit: int = 0, skip: int = 0):
        """Find documents matching query."""
        cursor = cls.get_collection().find(query or {})
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    @classmethod
    def count(cls, query: dict = None):
        """Count documents matching query."""
        return cls.get_collection().count_documents(query or {})

    @classmethod
    def insert(cls, document: dict):
        """Insert a document."""
        document['created_at'] = datetime.utcnow()
        document['updated_at'] = datetime.utcnow()
        result = cls.get_collection().insert_one(document)
        return result.inserted_id

    @classmethod
    def update(cls, doc_id, update: dict):
        """Update a document."""
        if isinstance(doc_id, str):
            try:
                doc_id = ObjectId(doc_id)
            except:
                pass
        update['updated_at'] = datetime.utcnow()
        return cls.get_collection().update_one(
            {'_id': doc_id},
            {'$set': update}
        )

    @classmethod
    def delete(cls, doc_id):
        """Delete a document."""
        if isinstance(doc_id, str):
            try:
                doc_id = ObjectId(doc_id)
            except:
                pass
        return cls.get_collection().delete_one({'_id': doc_id})


def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    if doc is None:
        return None
    result = dict(doc)
    if '_id' in result:
        result['id'] = str(result.pop('_id'))
    for key, value in result.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
    return result
