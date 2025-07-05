"""
Discord.py HTTP Integration
Discord.py-ийн HTTP client-тай rate limiting-ийг холбох систем
"""

import asyncio
import logging
import discord
from typing import Any, Optional, Sequence, Iterable, Dict
from .rate_limiter import rate_limiter, set_global_limit

logger = logging.getLogger(__name__)

class RateLimitedHTTPClient:
    """Discord.py HTTP client-тай интеграци хийсэн rate limiter"""
    
    def __init__(self, original_client: Any):
        self.original_client = original_client
        self._original_request = original_client.request
        
    async def request(
        self,
        route: Any,
        *,
        files: Optional[Sequence[Any]] = None,
        form: Optional[Iterable[Dict[str, Any]]] = None,
        **kwargs: Any
    ):
        """HTTP хүсэлтийг rate limiting-тайгаар дамжуулах"""
        endpoint = f"{route.method}_{route.path.split('/')[-1] if route.path else 'unknown'}"
        
        # Rate limit шалгах
        if not await rate_limiter.acquire(endpoint):
            logger.warning(f"🔴 Pre-request rate limit blocked: {route.method} {route.path}")
            await rate_limiter.wait_if_needed(endpoint)
        
        try:
            # Жинхэнэ хүсэлт илгээх
            return await self._original_request(
                route,
                files=files,
                form=form,
                **kwargs
            )
            
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                # Discord-аас ирсэн rate limit мэдээллийг авах
                retry_after = e.response.headers.get('Retry-After', '60')
                try:
                    retry_after_seconds = float(retry_after)
                except (ValueError, TypeError):
                    retry_after_seconds = 60
                
                # Global rate limit эсэхийг шалгах
                is_global = e.response.headers.get('X-RateLimit-Global') == 'true'
                scope = e.response.headers.get('X-RateLimit-Scope', 'unknown')
                
                if is_global:
                    logger.error(f"🔴 Discord Global Rate Limit: {retry_after_seconds}s")
                    set_global_limit(retry_after_seconds)
                else:
                    logger.warning(f"⚠️ Discord Route Rate Limit: {route.method} {route.path} - {retry_after_seconds}s")
                
                # Rate limiting статистикт тэмдэглэх
                rate_limiter.total_blocked += 1
                
                # Мэдээлэл бичих
                logger.info(f"📊 Rate Limit Details:")
                logger.info(f"   Route: {route.method} {route.path}")
                logger.info(f"   Retry After: {retry_after_seconds}s")
                logger.info(f"   Scope: {scope}")
                logger.info(f"   Global: {is_global}")
                
                raise  # Алдааг дахин өргөх
            else:
                raise
        
        except Exception as e:
            logger.error(f"❌ HTTP Request error: {route.method} {route.path} - {e}")
            raise

def patch_discord_http(bot: discord.Client):
    """Discord.py bot-ийн HTTP client-д rate limiting нэмэх"""
    try:
        if hasattr(bot, 'http') and bot.http:
            # HTTP client-ийг rate limited хувилбар болгох
            rate_limited_client = RateLimitedHTTPClient(bot.http)
            # Save the original request method for unpatching
            setattr(bot.http, "_original_request", bot.http.request)
            bot.http.request = rate_limited_client.request
            
            logger.info("✅ Discord.py HTTP client rate limiting патч хийгдлээ")
            return True
    except Exception as e:
        logger.error(f"❌ Discord.py HTTP патч хийхэд алдаа: {e}")
        return False

def unpatch_discord_http(bot: discord.Client):
    """Rate limiting патчийг арилгах"""
    try:
        if hasattr(bot, 'http') and hasattr(bot.http, '_original_request'):
            original_request = getattr(bot.http, '_original_request', None)
            if original_request is not None:
                bot.http.request = original_request
                logger.info("✅ Discord.py HTTP патч арилгагдлаа")
            else:
                logger.warning("⚠️ _original_request attribute not found on bot.http")
    except Exception as e:
        logger.error(f"❌ Discord.py HTTP патч арилгахад алдаа: {e}")

# Discord message delete-ийн тусгай хамгаалалт
async def safe_message_delete(message: discord.Message, delay: Optional[float] = None, reason: Optional[str] = None):
    """Message-ийг rate limit-тай аюулгүй устгах"""
    endpoint = "DELETE_message"
    
    # Rate limit шалгах
    await rate_limiter.wait_if_needed(endpoint)
    
    try:
        if delay:
            await asyncio.sleep(delay)
        await message.delete()
        logger.debug(f"✅ Message устгагдлаа: {message.id}")
        
    except discord.NotFound:
        logger.debug(f"⚠️ Message аль хэдийн устсан: {message.id}")
    except discord.Forbidden:
        logger.warning(f"❌ Message устгах эрх хүрэлцэхгүй: {message.id}")
    except discord.HTTPException as e:
        if e.status == 429:
            retry_after = float(e.response.headers.get('Retry-After', '60'))
            logger.warning(f"⚠️ Message delete rate limited: {retry_after}s")
            set_global_limit(retry_after)
        raise

# Bulk message delete-ийн аюулгүй хувилбар
async def safe_bulk_delete(channel: discord.abc.Messageable, messages: Sequence[discord.Message], reason: Optional[str] = None):
    """Олон message-ийг rate limit-тай аюулгүй устгах"""
    endpoint = "POST_bulk_delete"
    
    # Rate limit шалгах
    await rate_limiter.wait_if_needed(endpoint)
    
    try:
        # Ensure channel supports bulk delete (TextChannel or Thread)
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            await channel.delete_messages(messages, reason=reason)
            logger.debug(f"✅ {len(messages)} message bulk устгагдлаа")
        else:
            logger.warning("⚠️ Channel does not support bulk delete. Deleting messages one by one.")
            for message in messages:
                try:
                    await message.delete()
                except Exception as e:
                    logger.warning(f"⚠️ Failed to delete message {message.id}: {e}")
        
    except discord.HTTPException as e:
        if e.status == 429:
            retry_after = float(e.response.headers.get('Retry-After', '60'))
            logger.warning(f"⚠️ Bulk delete rate limited: {retry_after}s")
            set_global_limit(retry_after)
        raise
