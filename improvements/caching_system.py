"""
Caching System for Okik CLI
Reduces redundant operations and improves performance
"""

import os
import json
import hashlib
import pickle
import time
from functools import wraps, lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Callable, Union
from datetime import datetime, timedelta
import yaml

class FileCache:
    """File-based cache for persistent storage"""
    
    def __init__(self, cache_dir: str = ".okik/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.cache_dir / "metadata.json"
        self._load_metadata()
    
    def _load_metadata(self):
        """Load cache metadata"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {}
    
    def _save_metadata(self):
        """Save cache metadata"""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for a key"""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    def get(self, key: str, default=None) -> Any:
        """Get value from cache"""
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return default
        
        # Check if cache is expired
        if key in self.metadata:
            expiry = self.metadata[key].get('expiry')
            if expiry and datetime.now().timestamp() > expiry:
                self.delete(key)
                return default
        
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except (pickle.PickleError, OSError):
            self.delete(key)
            return default
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache with optional TTL (seconds)"""
        cache_path = self._get_cache_path(key)
        
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(value, f)
            
            # Update metadata
            self.metadata[key] = {
                'created': datetime.now().timestamp(),
                'size': cache_path.stat().st_size
            }
            
            if ttl:
                self.metadata[key]['expiry'] = (datetime.now() + timedelta(seconds=ttl)).timestamp()
            
            self._save_metadata()
        except (pickle.PickleError, OSError) as e:
            print(f"Cache write error: {e}")
    
    def delete(self, key: str):
        """Delete value from cache"""
        cache_path = self._get_cache_path(key)
        
        if cache_path.exists():
            cache_path.unlink()
        
        if key in self.metadata:
            del self.metadata[key]
            self._save_metadata()
    
    def clear(self):
        """Clear all cache"""
        for file in self.cache_dir.glob("*.cache"):
            file.unlink()
        self.metadata = {}
        self._save_metadata()
    
    def size(self) -> int:
        """Get total cache size in bytes"""
        return sum(meta.get('size', 0) for meta in self.metadata.values())
    
    def cleanup_expired(self):
        """Remove expired cache entries"""
        now = datetime.now().timestamp()
        expired_keys = []
        
        for key, meta in self.metadata.items():
            if 'expiry' in meta and now > meta['expiry']:
                expired_keys.append(key)
        
        for key in expired_keys:
            self.delete(key)

class ConfigCache:
    """Specialized cache for configuration files"""
    
    def __init__(self, cache_dir: str = ".okik/cache/configs"):
        self.cache = FileCache(cache_dir)
        self.file_timestamps = {}
    
    def get_config(self, config_path: str, loader_func: Optional[Callable] = None) -> Optional[Dict]:
        """Get configuration with file modification check"""
        config_file = Path(config_path)
        
        if not config_file.exists():
            return None
        
        # Check file modification time
        current_mtime = config_file.stat().st_mtime
        cache_key = f"config_{config_path}"
        
        # Get cached config
        cached_data = self.cache.get(cache_key)
        
        if cached_data and cache_key in self.file_timestamps:
            if self.file_timestamps[cache_key] == current_mtime:
                return cached_data['config']
        
        # Load fresh config
        try:
            if loader_func:
                config = loader_func(config_path)
            else:
                with open(config_file, 'r') as f:
                    if config_path.endswith('.json'):
                        config = json.load(f)
                    elif config_path.endswith(('.yml', '.yaml')):
                        config = yaml.safe_load(f)
                    else:
                        # For non-JSON/YAML files, return as dict with content
                        return {"content": f.read()}
            
            # Ensure config is a dict
            if not isinstance(config, dict):
                return None
            
            # Cache the config
            self.cache.set(cache_key, {'config': config, 'mtime': current_mtime})
            self.file_timestamps[cache_key] = current_mtime
            
            return config
        except Exception as e:
            print(f"Error loading config {config_path}: {e}")
            return None

class BuildCache:
    """Cache for Docker builds and artifacts"""
    
    def __init__(self, cache_dir: str = ".okik/cache/builds"):
        self.cache = FileCache(cache_dir)
    
    def get_build_hash(self, dockerfile_path: str, context_files: list) -> str:
        """Generate hash for build context"""
        hasher = hashlib.sha256()
        
        # Add dockerfile content
        if os.path.exists(dockerfile_path):
            with open(dockerfile_path, 'rb') as f:
                hasher.update(f.read())
        
        # Add context files content
        for file_path in sorted(context_files):
            if os.path.exists(file_path):
                hasher.update(file_path.encode())
                with open(file_path, 'rb') as f:
                    hasher.update(f.read())
        
        return hasher.hexdigest()
    
    def is_build_cached(self, build_hash: str) -> bool:
        """Check if build is already cached"""
        return self.cache.get(f"build_{build_hash}") is not None
    
    def cache_build(self, build_hash: str, image_name: str, build_logs: str):
        """Cache successful build"""
        build_data = {
            'image_name': image_name,
            'build_time': datetime.now().isoformat(),
            'logs': build_logs
        }
        self.cache.set(f"build_{build_hash}", build_data, ttl=86400)  # 24 hours
    
    def get_cached_build(self, build_hash: str) -> Optional[Dict]:
        """Get cached build information"""
        return self.cache.get(f"build_{build_hash}")

class KubernetesCache:
    """Cache for Kubernetes API responses"""
    
    def __init__(self, cache_dir: str = ".okik/cache/k8s"):
        self.cache = FileCache(cache_dir)
    
    def cache_resource(self, resource_type: str, namespace: str, data: Any, ttl: int = 300):
        """Cache Kubernetes resource data"""
        cache_key = f"k8s_{resource_type}_{namespace}"
        self.cache.set(cache_key, data, ttl=ttl)
    
    def get_cached_resource(self, resource_type: str, namespace: str) -> Optional[Any]:
        """Get cached Kubernetes resource data"""
        cache_key = f"k8s_{resource_type}_{namespace}"
        return self.cache.get(cache_key)

# Decorator for caching function results
def cached(ttl: int = 3600, cache_key_func: Optional[Callable] = None):
    """Decorator to cache function results"""
    def decorator(func):
        cache = FileCache(f".okik/cache/functions/{func.__name__}")
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if cache_key_func:
                key = cache_key_func(*args, **kwargs)
            else:
                key = f"{func.__name__}_{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Try to get from cache
            result = cache.get(key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(key, result, ttl=ttl)
            return result
        
        return wrapper
    return decorator

# Global cache instances
_config_cache = ConfigCache()
_build_cache = BuildCache()
_k8s_cache = KubernetesCache()

# Convenience functions
@lru_cache(maxsize=128)
def load_cached_config(config_path: str) -> Optional[Dict]:
    """Load configuration with caching"""
    return _config_cache.get_config(config_path)

def cache_build_result(dockerfile: str, context_files: list, image_name: str, logs: str):
    """Cache a successful build"""
    build_hash = _build_cache.get_build_hash(dockerfile, context_files)
    _build_cache.cache_build(build_hash, image_name, logs)

def is_build_cached(dockerfile: str, context_files: list) -> bool:
    """Check if a build is cached"""
    build_hash = _build_cache.get_build_hash(dockerfile, context_files)
    return _build_cache.is_build_cached(build_hash)

def get_cached_build_info(dockerfile: str, context_files: list) -> Optional[Dict]:
    """Get cached build information"""
    build_hash = _build_cache.get_build_hash(dockerfile, context_files)
    return _build_cache.get_cached_build(build_hash)

@cached(ttl=300)  # Cache for 5 minutes
def get_kubernetes_deployments(namespace: str = "default"):
    """Get Kubernetes deployments with caching"""
    # This would be replaced with actual Kubernetes API call
    from kubernetes import client
    try:
        v1 = client.AppsV1Api()
        return v1.list_namespaced_deployment(namespace=namespace)
    except Exception as e:
        print(f"Error fetching deployments: {e}")
        return None

@cached(ttl=300)
def get_kubernetes_services(namespace: str = "default"):
    """Get Kubernetes services with caching"""
    # This would be replaced with actual Kubernetes API call
    from kubernetes import client
    try:
        v1 = client.CoreV1Api()
        return v1.list_namespaced_service(namespace=namespace)
    except Exception as e:
        print(f"Error fetching services: {e}")
        return None

# Cache management utilities
def clear_all_caches():
    """Clear all caches"""
    _config_cache.cache.clear()
    _build_cache.cache.clear()
    _k8s_cache.cache.clear()

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    return {
        'config_cache_size': _config_cache.cache.size(),
        'build_cache_size': _build_cache.cache.size(),
        'k8s_cache_size': _k8s_cache.cache.size(),
        'total_size': _config_cache.cache.size() + _build_cache.cache.size() + _k8s_cache.cache.size()
    }

def cleanup_expired_caches():
    """Clean up expired cache entries"""
    _config_cache.cache.cleanup_expired()
    _build_cache.cache.cleanup_expired()
    _k8s_cache.cache.cleanup_expired()

# Example usage
if __name__ == "__main__":
    # Example: Caching configuration
    config = load_cached_config("pyproject.toml")
    print(f"Loaded config: {config is not None}")
    
         # Example: Build caching
     dockerfile = "Dockerfile"
     context = ["main.py", "requirements.txt"]
     
     if is_build_cached(dockerfile, context):
         build_info = get_cached_build_info(dockerfile, context)
         if build_info:
             print(f"Build cached: {build_info['image_name']}")
     else:
         print("Build not cached, would need to build")
         # After successful build:
         cache_build_result(dockerfile, context, "my-app:latest", "Build successful")
    
    # Example: Cache stats
    stats = get_cache_stats()
    print(f"Total cache size: {stats['total_size']} bytes")
    
    # Cleanup
    cleanup_expired_caches()