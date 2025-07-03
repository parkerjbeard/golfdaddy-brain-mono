"""
Documentation Cache Service

Provides intelligent caching for documentation operations to improve performance
and reduce external API calls.
"""

import logging
import json
import pickle
import hashlib
from typing import Dict, Any, Optional, Union, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
from functools import wraps

from app.config.settings import settings

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache storage levels."""
    MEMORY = "memory"
    DISK = "disk"
    DISTRIBUTED = "distributed"


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    cache_level: CacheLevel = CacheLevel.MEMORY
    content_hash: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.now() > self.expires_at
    
    def is_stale(self, max_age_seconds: int) -> bool:
        """Check if cache entry is stale."""
        return (datetime.now() - self.created_at).total_seconds() > max_age_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["expires_at"] = self.expires_at.isoformat()
        data["last_accessed"] = self.last_accessed.isoformat() if self.last_accessed else None
        data["cache_level"] = self.cache_level.value
        return data


class DocCacheService:
    """Advanced caching service for documentation operations."""
    
    def __init__(self):
        """Initialize the cache service."""
        # Memory cache
        self._memory_cache: Dict[str, CacheEntry] = {}
        
        # Configuration
        self.default_ttl_seconds = getattr(settings, 'DOC_CACHE_TTL_SECONDS', 3600)  # 1 hour
        self.max_memory_entries = getattr(settings, 'DOC_CACHE_MAX_MEMORY_ENTRIES', 1000)
        self.enable_cache = getattr(settings, 'ENABLE_DOC_CACHE', True)
        
        # Cache statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "memory_usage": 0
        }
        
        # Background cleanup task
        self._cleanup_task = None
        self._cleanup_started = False
        
        logger.info(f"DocCacheService initialized with TTL={self.default_ttl_seconds}s, "
                   f"max_entries={self.max_memory_entries}")
    
    def _start_cleanup_task(self):
        """Start background cleanup task."""
        if self._cleanup_task is None and not self._cleanup_started:
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())
                self._cleanup_started = True
            except RuntimeError:
                # No event loop running, skip cleanup task
                logger.debug("No event loop available for cleanup task")
    
    async def _cleanup_loop(self):
        """Background task to clean up expired cache entries."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                await self._cleanup_expired_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup loop: {e}")
    
    async def _cleanup_expired_entries(self):
        """Remove expired entries from cache."""
        if not self.enable_cache:
            return
        
        expired_keys = []
        now = datetime.now()
        
        for key, entry in self._memory_cache.items():
            if entry.expires_at < now:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._memory_cache[key]
            self.stats["evictions"] += 1
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _generate_cache_key(self, operation: str, **kwargs) -> str:
        """Generate cache key from operation and parameters."""
        # Sort kwargs for consistent key generation
        sorted_params = sorted(kwargs.items())
        param_str = json.dumps(sorted_params, sort_keys=True, default=str)
        
        # Create hash of parameters
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        
        return f"doc_cache:{operation}:{param_hash}"
    
    def _calculate_content_hash(self, content: Any) -> str:
        """Calculate hash of cached content."""
        if isinstance(content, str):
            return hashlib.md5(content.encode()).hexdigest()
        elif isinstance(content, (dict, list)):
            content_str = json.dumps(content, sort_keys=True, default=str)
            return hashlib.md5(content_str.encode()).hexdigest()
        else:
            content_str = str(content)
            return hashlib.md5(content_str.encode()).hexdigest()
    
    async def get(self, operation: str, **kwargs) -> Optional[Any]:
        """
        Get cached value for operation with parameters.
        
        Args:
            operation: Cache operation name
            **kwargs: Operation parameters
            
        Returns:
            Cached value or None if not found/expired
        """
        if not self.enable_cache:
            return None
        
        # Ensure cleanup task is started
        self._start_cleanup_task()
        
        cache_key = self._generate_cache_key(operation, **kwargs)
        
        entry = self._memory_cache.get(cache_key)
        if entry is None:
            self.stats["misses"] += 1
            return None
        
        # Check if expired
        if entry.is_expired():
            del self._memory_cache[cache_key]
            self.stats["misses"] += 1
            self.stats["evictions"] += 1
            return None
        
        # Update access statistics
        entry.access_count += 1
        entry.last_accessed = datetime.now()
        self.stats["hits"] += 1
        
        logger.debug(f"Cache hit for operation: {operation}")
        return entry.value
    
    async def set(self, operation: str, value: Any, ttl_seconds: Optional[int] = None, **kwargs) -> None:
        """
        Cache value for operation with parameters.
        
        Args:
            operation: Cache operation name
            value: Value to cache
            ttl_seconds: Time to live in seconds (uses default if None)
            **kwargs: Operation parameters
        """
        if not self.enable_cache:
            return
        
        # Ensure cleanup task is started
        self._start_cleanup_task()
        
        cache_key = self._generate_cache_key(operation, **kwargs)
        ttl = ttl_seconds or self.default_ttl_seconds
        
        now = datetime.now()
        expires_at = now + timedelta(seconds=ttl)
        
        entry = CacheEntry(
            key=cache_key,
            value=value,
            created_at=now,
            expires_at=expires_at,
            content_hash=self._calculate_content_hash(value)
        )
        
        # Check memory limit and evict if necessary
        if len(self._memory_cache) >= self.max_memory_entries:
            await self._evict_lru_entries()
        
        self._memory_cache[cache_key] = entry
        
        logger.debug(f"Cached result for operation: {operation} (TTL: {ttl}s)")
    
    async def _evict_lru_entries(self):
        """Evict least recently used entries to make space."""
        # Sort by last accessed time, oldest first
        sorted_entries = sorted(
            self._memory_cache.items(),
            key=lambda x: x[1].last_accessed or x[1].created_at
        )
        
        # Remove oldest 10% of entries
        evict_count = max(1, len(sorted_entries) // 10)
        
        for i in range(evict_count):
            key = sorted_entries[i][0]
            del self._memory_cache[key]
            self.stats["evictions"] += 1
        
        logger.debug(f"Evicted {evict_count} LRU cache entries")
    
    async def invalidate(self, operation: str, **kwargs) -> bool:
        """
        Invalidate cached value for specific operation.
        
        Args:
            operation: Cache operation name
            **kwargs: Operation parameters
            
        Returns:
            True if entry was found and removed
        """
        if not self.enable_cache:
            return False
        
        cache_key = self._generate_cache_key(operation, **kwargs)
        
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
            logger.debug(f"Invalidated cache for operation: {operation}")
            return True
        
        return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache entries matching pattern.
        
        Args:
            pattern: Pattern to match (e.g., "doc_quality:*")
            
        Returns:
            Number of entries invalidated
        """
        if not self.enable_cache:
            return 0
        
        # Convert simple pattern to regex-like matching
        pattern_key = pattern.replace("*", "")
        
        keys_to_remove = []
        for key in self._memory_cache.keys():
            if pattern_key in key:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._memory_cache[key]
        
        logger.debug(f"Invalidated {len(keys_to_remove)} cache entries matching pattern: {pattern}")
        return len(keys_to_remove)
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        if not self.enable_cache:
            return
        
        count = len(self._memory_cache)
        self._memory_cache.clear()
        self.stats["evictions"] += count
        
        logger.info(f"Cleared all cache entries ({count} entries)")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "enabled": self.enable_cache,
            "entries_count": len(self._memory_cache),
            "max_entries": self.max_memory_entries,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate_percent": round(hit_rate, 2),
            "evictions": self.stats["evictions"],
            "default_ttl_seconds": self.default_ttl_seconds
        }
    
    def get_entries(self) -> List[Dict[str, Any]]:
        """Get information about all cache entries."""
        if not self.enable_cache:
            return []
        
        return [entry.to_dict() for entry in self._memory_cache.values()]


# Global cache service instance
cache_service = DocCacheService()


def cached(operation: str, ttl_seconds: Optional[int] = None, 
          key_params: Optional[List[str]] = None):
    """
    Decorator for caching function results.
    
    Args:
        operation: Cache operation name
        ttl_seconds: Time to live in seconds
        key_params: List of parameter names to include in cache key
        
    Example:
        @cached("quality_validation", ttl_seconds=1800, key_params=["content", "doc_type"])
        async def validate_documentation(content: str, doc_type: str):
            # Expensive operation
            return result
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key parameters
            cache_params = {}
            
            if key_params:
                # Use specified parameters
                func_signature = func.__code__.co_varnames[:func.__code__.co_argcount]
                
                # Map positional args to parameter names
                arg_dict = dict(zip(func_signature, args))
                arg_dict.update(kwargs)
                
                # Extract specified parameters
                for param in key_params:
                    if param in arg_dict:
                        cache_params[param] = arg_dict[param]
            else:
                # Use all parameters
                func_signature = func.__code__.co_varnames[:func.__code__.co_argcount]
                cache_params = dict(zip(func_signature, args))
                cache_params.update(kwargs)
            
            # Try to get from cache
            cached_result = await cache_service.get(operation, **cache_params)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache_service.set(operation, result, ttl_seconds, **cache_params)
            
            return result
        
        return wrapper
    return decorator


class CacheWarmupService:
    """Service for warming up frequently used cache entries."""
    
    def __init__(self, cache_service: DocCacheService):
        self.cache_service = cache_service
    
    async def warmup_common_operations(self):
        """Warm up cache with commonly used operations."""
        logger.info("Starting cache warmup for common documentation operations")
        
        try:
            # Warmup examples - would be customized based on usage patterns
            common_doc_types = ["api", "guide", "reference", "tutorial"]
            
            # Pre-generate some quality validation templates
            for doc_type in common_doc_types:
                cache_key = f"quality_template_{doc_type}"
                template_data = {
                    "doc_type": doc_type,
                    "quality_threshold": self._get_quality_threshold(doc_type),
                    "validation_rules": self._get_validation_rules(doc_type)
                }
                
                await self.cache_service.set(
                    "quality_template",
                    template_data,
                    ttl_seconds=7200,  # 2 hours
                    doc_type=doc_type
                )
            
            logger.info("Cache warmup completed")
            
        except Exception as e:
            logger.error(f"Error during cache warmup: {e}")
    
    def _get_quality_threshold(self, doc_type: str) -> float:
        """Get quality threshold for document type."""
        thresholds = {
            "api": 85.0,
            "guide": 80.0,
            "reference": 90.0,
            "tutorial": 85.0
        }
        return thresholds.get(doc_type, 75.0)
    
    def _get_validation_rules(self, doc_type: str) -> List[str]:
        """Get validation rules for document type."""
        common_rules = ["headings_structure", "grammar", "links_format"]
        
        type_specific = {
            "api": ["code_blocks", "examples", "parameters"],
            "guide": ["step_by_step", "screenshots", "prerequisites"],
            "reference": ["completeness", "accuracy", "examples"],
            "tutorial": ["hands_on", "progression", "troubleshooting"]
        }
        
        return common_rules + type_specific.get(doc_type, [])


# Cache warmup service instance
warmup_service = CacheWarmupService(cache_service)


# Cache performance monitoring
class CacheMonitor:
    """Monitor cache performance and suggest optimizations."""
    
    def __init__(self, cache_service: DocCacheService):
        self.cache_service = cache_service
    
    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze cache performance and provide recommendations."""
        stats = self.cache_service.get_stats()
        
        recommendations = []
        
        # Check hit rate
        if stats["hit_rate_percent"] < 50:
            recommendations.append("Low cache hit rate - consider increasing TTL or cache size")
        
        # Check eviction rate
        total_requests = stats["hits"] + stats["misses"]
        if total_requests > 0:
            eviction_rate = (stats["evictions"] / total_requests) * 100
            if eviction_rate > 10:
                recommendations.append("High eviction rate - consider increasing max_entries")
        
        # Check memory usage
        usage_percent = (stats["entries_count"] / stats["max_entries"]) * 100
        if usage_percent > 90:
            recommendations.append("Cache near capacity - consider increasing max_entries")
        
        return {
            "stats": stats,
            "recommendations": recommendations,
            "status": "healthy" if not recommendations else "needs_attention"
        }


# Cache monitor instance
cache_monitor = CacheMonitor(cache_service)