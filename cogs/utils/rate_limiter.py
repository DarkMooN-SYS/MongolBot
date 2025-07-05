"""
Global Rate Limiter for Discord Bot
Дискорд ботонд зориулсан глобал rate limit зохицуулагч
"""

import asyncio
import time
import logging
from typing import Dict, Optional, Any
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GlobalRateLimiter:
    """
    Discord API-д зориулсан глобал rate limiter
    Секундэд 50 хүсэлтийн хязгаарлалт зохицуулдаг
    """
    
    def __init__(self, max_requests_per_second: int = 45):
        """
        Args:
            max_requests_per_second: Секундэд хийж болох дээд хүсэлтийн тоо (50-ээс бага байх ёстой)
        """
        self.max_requests_per_second = max_requests_per_second
        self.requests = deque()  # (timestamp, endpoint) хослол хадгалах
        self.lock = asyncio.Lock()
        self.global_reset_time: Optional[float] = None
        self.is_globally_limited = False
        
        # Statistics
        self.total_requests = 0
        self.total_blocked = 0
        self.last_reset = time.time()
        
    async def acquire(self, endpoint: str = "unknown") -> bool:
        """
        Rate limit шалгаад хүсэлт хийх зөвшөөрөл авах
        
        Args:
            endpoint: API endpoint нэр (log-д ашиглах)
            
        Returns:
            bool: Хүсэлт хийж болох эсэх
        """
        async with self.lock:
            current_time = time.time()
            
            # Global rate limit-д орсон эсэхийг шалгах
            if self.is_globally_limited and self.global_reset_time:
                if current_time < self.global_reset_time:
                    wait_time = self.global_reset_time - current_time
                    logger.warning(f"🔴 Global rate limit идэвхтэй. {wait_time:.1f} секунд хүлээх хэрэгтэй")
                    return False
                else:
                    # Rate limit дууссан
                    self.is_globally_limited = False
                    self.global_reset_time = None
                    logger.info("✅ Global rate limit арилсан")
            
            # 1 секундээс хуучин хүсэлтүүдийг устгах
            while self.requests and current_time - self.requests[0][0] > 1.0:
                self.requests.popleft()
            
            # Одоогийн секунд дэх хүсэлтийн тоог тоолох
            current_second_requests = len(self.requests)
            
            if current_second_requests >= self.max_requests_per_second:
                self.total_blocked += 1
                logger.warning(f"⚠️ Rate limit: {current_second_requests}/{self.max_requests_per_second} хүсэлт. Endpoint: {endpoint}")
                return False
            
            # Хүсэлт зөвшөөрөх
            self.requests.append((current_time, endpoint))
            self.total_requests += 1
            
            return True
    
    async def wait_if_needed(self, endpoint: str = "unknown") -> None:
        """
        Rate limit-д тохирох хүртэл хүлээх
        
        Args:
            endpoint: API endpoint нэр
        """
        max_wait_time = 60  # Дээд талаар 60 секунд хүлээх
        wait_start = time.time()
        
        while not await self.acquire(endpoint):
            if time.time() - wait_start > max_wait_time:
                logger.error(f"❌ Rate limit-ээс {max_wait_time} секунд хүлээсэн ч гарч чадсангүй")
                break
                
            # Жижиг хугацаа хүлээж дахин оролдох
            await asyncio.sleep(0.1)
    
    def set_global_rate_limit(self, retry_after: float) -> None:
        """
        Global rate limit-д орохыг тэмдэглэх
        
        Args:
            retry_after: Хэзээ дахин оролдож болох (секундээр)
        """
        self.is_globally_limited = True
        self.global_reset_time = time.time() + retry_after
        logger.error(f"🔴 Global rate limit! {retry_after} секунд хүлээх хэрэгтэй")
        
        # Message delete rate limit-ийн тусгай боловсруулалт
        if retry_after > 30:  # 30 секундээс дээш бол том алдаа
            logger.warning("⚠️ Урт хугацаатай rate limit - message delete командуудыг түр зогсоох хэрэгтэй!")
    
    def get_endpoint_stats(self, endpoint: str) -> dict:
        """Тодорхой endpoint-ийн статистик авах"""
        endpoint_requests = [req for req in self.requests if req[1] == endpoint]
        
        return {
            "endpoint": endpoint,
            "current_requests": len(endpoint_requests),
            "last_request_time": endpoint_requests[-1][0] if endpoint_requests else None,
            "requests_in_last_second": len(endpoint_requests)
        }

    def get_stats(self) -> Dict[str, Any]:
        """Rate limiter-ийн статистик мэдээлэл авах"""
        current_time = time.time()
        uptime = current_time - self.last_reset
        
        # Сүүлийн 10 хүсэлтийн endpoint-уудыг авах
        recent_endpoints = [req[1] for req in list(self.requests)[-10:]]
        
        return {
            "total_requests": self.total_requests,
            "total_blocked": self.total_blocked,
            "current_queue_size": len(self.requests),
            "requests_per_second_limit": self.max_requests_per_second,
            "is_globally_limited": self.is_globally_limited,
            "global_reset_in": self.global_reset_time - current_time if self.global_reset_time else 0,
            "uptime_seconds": uptime,
            "average_requests_per_second": self.total_requests / uptime if uptime > 0 else 0,
            "block_rate_percent": (self.total_blocked / max(self.total_requests, 1)) * 100,
            "recent_endpoints": recent_endpoints
        }
    
    def reset_stats(self) -> None:
        """Статистикийг reset хийх"""
        self.total_requests = 0
        self.total_blocked = 0
        self.last_reset = time.time()
        logger.info("📊 Rate limiter статистик reset хийгдлээ")

# Global instance
rate_limiter = GlobalRateLimiter()

# Convenience functions
async def check_rate_limit(endpoint: str = "unknown") -> bool:
    """Rate limit шалгах хялбар функц"""
    return await rate_limiter.acquire(endpoint)

async def wait_for_rate_limit(endpoint: str = "unknown") -> None:
    """Rate limit-ээс гарах хүртэл хүлээх хялбар функц"""
    await rate_limiter.wait_if_needed(endpoint)

def set_global_limit(retry_after: float) -> None:
    """Global rate limit тохируулах хялбар функц"""
    rate_limiter.set_global_rate_limit(retry_after)

def get_rate_limit_stats() -> Dict[str, Any]:
    """Rate limit статистик авах хялбар функц"""
    return rate_limiter.get_stats()
