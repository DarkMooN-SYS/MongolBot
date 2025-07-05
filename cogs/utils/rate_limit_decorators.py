"""
Discord.py интеграци хийсэн rate limit декораторууд
"""

from typing import Callable, Any, Optional
import functools
import discord
from discord.ext import commands
import logging
from .rate_limiter import rate_limiter, set_global_limit

logger = logging.getLogger(__name__)

def with_rate_limit(endpoint_name: Optional[str] = None):
    """
    Discord API хүсэлтүүдэд rate limit шалгах decorator
    
    Args:
        endpoint_name: API endpoint-ийн нэр (статистикт ашиглах)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Endpoint нэрийг тодорхойлох
            endpoint = endpoint_name or f"{func.__module__}.{func.__name__}"
            
            # Rate limit шалгах
            if not await rate_limiter.acquire(endpoint):
                # Rate limit-д тохирсон
                logger.warning(f"⚠️ Rate limit: {endpoint} хүсэлтийг түр зогсоолоо")
                
                # Хэрэв command бол хэрэглэгчид мэдэгдэх
                if len(args) > 0:
                    if hasattr(args[0], 'send'):  # Context object
                        try:
                            await args[0].send("⚠️ Хүсэлт хэтэрхий олон байна. Хэсэг хүлээж дахин оролдоно уу.")
                        except:
                            pass
                
                # Rate limit-ээс гарах хүртэл хүлээх
                await rate_limiter.wait_if_needed(endpoint)
            
            try:
                # Функцийг ажиллуулах
                result = await func(*args, **kwargs)
                return result
                
            except discord.HTTPException as e:
                # Discord API алдаа шалгах
                if e.status == 429:  # Rate limited
                    # Response headers-ээс retry_after авах
                    retry_after = getattr(e.response, 'headers', {}).get('Retry-After')
                    if retry_after:
                        try:
                            retry_after = float(retry_after)
                        except (ValueError, TypeError):
                            retry_after = 60  # Default 60 секунд
                    else:
                        retry_after = 60
                    
                    # Global rate limit эсэхийг шалгах
                    is_global = getattr(e.response, 'headers', {}).get('X-RateLimit-Global') == 'true'
                    
                    if is_global:
                        logger.error(f"🔴 Global rate limit! {retry_after} секунд хүлээх")
                        set_global_limit(retry_after)
                    else:
                        logger.warning(f"⚠️ Route rate limit: {endpoint} - {retry_after} секунд хүлээх")
                    
                    # Хэрэв command бол хэрэглэгчид мэдэгдэх
                    if len(args) > 0 and hasattr(args[0], 'send'):
                        try:
                            await args[0].send(f"⚠️ Discord API rate limit. {int(retry_after)} секунд хүлээж дахин оролдоно уу.")
                        except:
                            pass
                    
                    raise  # Алдааг дахин өргөх
                else:
                    raise  # Бусад HTTP алдаануудыг өргөх
            
            except Exception as e:
                # Бусад алдаанууд
                logger.error(f"❌ {endpoint} дээр алдаа гарлаа: {e}")
                raise
        
        return wrapper
    return decorator

def rate_limit_command():
    """Command-уудад зориулсан rate limit decorator"""
    return with_rate_limit()

def rate_limit_api(endpoint_name: str):
    """API хүсэлтүүдэд зориулсан rate limit decorator"""
    return with_rate_limit(endpoint_name)

def rate_limit_message_delete():
    """Message delete командуудад зориулсан тусгай rate limit decorator"""
    return with_rate_limit("DELETE_message")

def rate_limit_bulk_delete():
    """Bulk message delete командуудад зориулсан тусгай rate limit decorator"""
    return with_rate_limit("POST_bulk_delete")

# Auto-detecting dangerous commands (message deletion)
def auto_rate_limit():
    """Командын нэрээс харж автоматаар rate limiting нэмэх decorator"""
    def decorator(func: Callable) -> Callable:
        func_name = func.__name__.lower()
        
        # Message delete командуудыг илрүүлэх
        if any(keyword in func_name for keyword in ['delete', 'clear', 'purge', 'remove']):
            return rate_limit_message_delete()(func)
        # Bulk operations
        elif any(keyword in func_name for keyword in ['bulk', 'mass', 'all']):
            return rate_limit_bulk_delete()(func)
        # Хэвийн rate limiting
        else:
            return rate_limit_command()(func)
    
    return decorator

# Rate limit bypass для админов в экстренных случаях
def bypass_rate_limit_for_owner():
    """Owner хэрэглэгчид rate limit bypass-тай decorator"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Context-ийг олох
            ctx = None
            for arg in args:
                if hasattr(arg, 'author') and hasattr(arg, 'bot'):
                    ctx = arg
                    break
            
            # Owner эсэхийг шалгах
            if ctx and ctx.bot.owner_id and ctx.author.id == ctx.bot.owner_id:
                # Owner бол rate limiting алгасах
                return await func(*args, **kwargs)
            else:
                # Бусад хэрэглэгчид rate limiting ашиглах
                return await with_rate_limit()(func)(*args, **kwargs)
        
        return wrapper
    return decorator

# Context manager for manual rate limiting
class RateLimitContext:
    """Manual rate limiting хийх context manager"""
    
    def __init__(self, endpoint_name: str):
        self.endpoint_name = endpoint_name
        self.acquired = False
    
    async def __aenter__(self):
        await rate_limiter.wait_if_needed(self.endpoint_name)
        self.acquired = True
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_type is discord.HTTPException and exc_val.status == 429:
            # Rate limit handling
            retry_after = getattr(exc_val.response, 'headers', {}).get('Retry-After', 60)
            try:
                retry_after = float(retry_after)
            except (ValueError, TypeError):
                retry_after = 60
            
            is_global = getattr(exc_val.response, 'headers', {}).get('X-RateLimit-Global') == 'true'
            
            if is_global:
                set_global_limit(retry_after)
                logger.error(f"🔴 Global rate limit in context: {self.endpoint_name}")
            else:
                logger.warning(f"⚠️ Route rate limit in context: {self.endpoint_name}")
        
        return False  # Don't suppress exceptions
