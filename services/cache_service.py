import json
import hashlib
from typing import Any, Optional
from flask import current_app
import logging

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

class CacheService:
    def __init__(self):
        self.redis_client = None
        self.memory_cache = {}
        
        if REDIS_AVAILABLE and current_app.config.get('CACHE_REDIS_URL'):
            try:
                self.redis_client = redis.from_url(
                    current_app.config['CACHE_REDIS_URL'],
                    decode_responses=True
                )
                # Test connection
                self.redis_client.ping()
                logging.info("Redis cache initialized")
            except Exception as e:
                logging.warning(f"Redis connection failed, using memory cache: {e}")
                self.redis_client = None
    
    def _get_key(self, key: str) -> str:
        """Generate cache key with namespace"""
        return f"cyberchat:{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            cache_key = self._get_key(key)
            
            if self.redis_client:
                value = self.redis_client.get(cache_key)
                if value:
                    return json.loads(value)
            else:
                return self.memory_cache.get(cache_key)
            
            return None
        except Exception as e:
            logging.error(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, timeout: int = 300) -> bool:
        """Set value in cache"""
        try:
            cache_key = self._get_key(key)
            
            if self.redis_client:
                return self.redis_client.setex(
                    cache_key, 
                    timeout, 
                    json.dumps(value)
                )
            else:
                self.memory_cache[cache_key] = value
                return True
        except Exception as e:
            logging.error(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            cache_key = self._get_key(key)
            
            if self.redis_client:
                return bool(self.redis_client.delete(cache_key))
            else:
                return bool(self.memory_cache.pop(cache_key, None))
        except Exception as e:
            logging.error(f"Cache delete error: {e}")
            return False
    
    def clear_pattern(self, pattern: str) -> bool:
        """Clear all keys matching pattern"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys(self._get_key(pattern))
                if keys:
                    return bool(self.redis_client.delete(*keys))
            else:
                # For memory cache, clear all keys containing pattern
                keys_to_delete = [k for k in self.memory_cache.keys() if pattern in k]
                for key in keys_to_delete:
                    del self.memory_cache[key]
            
            return True
        except Exception as e:
            logging.error(f"Cache clear pattern error: {e}")
            return False