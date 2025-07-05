"""
Real-time Rate Limit Monitor
Discord API rate limit-ийг бодит цагт хянах систем
"""

from typing import Dict, List, Any
import asyncio
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict, deque
import discord

logger = logging.getLogger(__name__)

class RealTimeRateLimitMonitor:
    """Бодит цагийн rate limit мониторинг систем"""
    
    def __init__(self):
        self.rate_limit_incidents = deque(maxlen=100)  # Сүүлийн 100 тохиолдол
        self.endpoint_stats = defaultdict(lambda: {"count": 0, "last_incident": None})
        self.is_monitoring = False
        self.alert_threshold = 5  # 5 rate limit 1 минутад гарвал анхааруулга
        
    def record_rate_limit(self, method: str, path: str, retry_after: float, is_global: bool = False):
        """Rate limit тохиолдлыг бүртгэх"""
        incident = {
            "timestamp": time.time(),
            "datetime": datetime.now(),
            "method": method,
            "path": path,
            "retry_after": retry_after,
            "is_global": is_global,
            "endpoint": f"{method}_{path.split('/')[-1] if path else 'unknown'}"
        }
        
        self.rate_limit_incidents.append(incident)
        endpoint = incident["endpoint"]
        current_count = self.endpoint_stats[endpoint].get("count", 0)
        if current_count is None:
            current_count = 0
        self.endpoint_stats[endpoint]["count"] = current_count + 1
        self.endpoint_stats[endpoint]["last_incident"] = incident["datetime"]
        
        # Log бичих
        level = logging.ERROR if is_global else logging.WARNING
        logger.log(level, f"🚨 Rate Limit Detected: {method} {path} - {retry_after}s {'(GLOBAL)' if is_global else ''}")
        
        # Анхааруулга шалгах
        self._check_alert_conditions()
    
    def _check_alert_conditions(self):
        """Анхааруулга нөхцөлийг шалгах"""
        current_time = time.time()
        
        # Сүүлийн 1 минутын rate limit тоолох
        recent_incidents = [
            incident for incident in self.rate_limit_incidents
            if current_time - incident["timestamp"] <= 60
        ]
        
        if len(recent_incidents) >= self.alert_threshold:
            logger.critical(f"🚨 RATE LIMIT ALERT: {len(recent_incidents)} incidents in 1 minute!")
            self._suggest_actions(recent_incidents)
    
    def _suggest_actions(self, incidents: List[dict]):
        """Rate limit асуудлын шийдлийг санал болгох"""
        endpoint_counts = defaultdict(int)
        
        for incident in incidents:
            endpoint_counts[incident["endpoint"]] += 1
        
        # Хамгийн их асуудалтай endpoint
        most_problematic = max(endpoint_counts.items(), key=lambda x: x[1])
        
        logger.warning(f"💡 Suggested Actions:")
        logger.warning(f"   Most problematic endpoint: {most_problematic[0]} ({most_problematic[1]} incidents)")
        
        if most_problematic[0].startswith("DELETE_"):
            logger.warning(f"   🔧 Suggestion: Reduce message deletion frequency")
            logger.warning(f"   🔧 Use bulk delete for multiple messages")
            logger.warning(f"   🔧 Add delays between delete operations")
        elif most_problematic[0].startswith("POST_"):
            logger.warning(f"   🔧 Suggestion: Reduce message sending frequency")
            logger.warning(f"   🔧 Batch multiple updates together")
        else:
            logger.warning(f"   🔧 Suggestion: Add rate limiting to {most_problematic[0]} operations")
    
    def get_monitoring_report(self) -> Dict:
        """Мониторингийн тайлан гаргах"""
        current_time = time.time()
        
        # Сүүлийн янз бүрийн хугацааны статистик
        periods = {
            "last_minute": 60,
            "last_5_minutes": 300,
            "last_hour": 3600
        }
        
        report = {
            "total_incidents": len(self.rate_limit_incidents),
            "monitoring_since": datetime.now() - timedelta(seconds=current_time - self.rate_limit_incidents[0]["timestamp"]) if self.rate_limit_incidents else None,
            "periods": {}
        }
        
        for period_name, seconds in periods.items():
            incidents_in_period = [
                incident for incident in self.rate_limit_incidents
                if current_time - incident["timestamp"] <= seconds
            ]
            
            report["periods"][period_name] = {
                "count": len(incidents_in_period),
                "global_count": sum(1 for i in incidents_in_period if i["is_global"]),
                "avg_retry_after": sum(i["retry_after"] for i in incidents_in_period) / len(incidents_in_period) if incidents_in_period else 0
            }
        
        # Endpoint статистик
        report["endpoint_stats"] = dict(self.endpoint_stats)
        
        return report
    
    def get_recent_incidents(self, limit: int = 10) -> List[dict]:
        """Сүүлийн rate limit тохиолдлуудыг авах"""
        return list(self.rate_limit_incidents)[-limit:]
    
    def clear_history(self):
        """Monitoring түүхийг цэвэрлэх"""
        self.rate_limit_incidents.clear()
        self.endpoint_stats.clear()
        logger.info("✅ Rate limit monitoring түүх цэвэрлэгдлээ")

# Global monitor instance
rate_limit_monitor = RealTimeRateLimitMonitor()

def parse_discord_log_for_rate_limit(log_message: str):
    """Discord.py log мессежээс rate limit мэдээллийг гаргаж авах"""
    try:
        # Log форматын жишээ:
        # "We are being rate limited. DELETE https://discord.com/api/v10/channels/123/messages/456 responded with 429. Retrying in 0.47 seconds."
        
        import re
        
        # HTTP method
        method_match = re.search(r'(GET|POST|PUT|DELETE|PATCH)', log_message)
        method = method_match.group(1) if method_match else "UNKNOWN"
        
        # URL path
        url_match = re.search(r'https://discord\.com/api/v\d+(.+?)\s', log_message)
        path = url_match.group(1) if url_match else "/unknown"
        
        # Retry after
        retry_match = re.search(r'Retrying in ([\d.]+) seconds', log_message)
        retry_after = float(retry_match.group(1)) if retry_match else 60.0
        
        # Rate limit-ийг бүртгэх
        rate_limit_monitor.record_rate_limit(method, path, retry_after, is_global=False)
        
        return {
            "method": method,
            "path": path,
            "retry_after": retry_after
        }
        
    except Exception as e:
        logger.error(f"❌ Discord log парс хийхэд алдаа: {e}")
        return None

# Discord.py logging handler-тай холбох
class DiscordRateLimitHandler(logging.Handler):
    """Discord.py rate limit log-уудыг барих handler"""
    
    def emit(self, record: Any) -> None:
        if record.name == 'discord.http' and 'rate limited' in record.getMessage().lower():
            parse_discord_log_for_rate_limit(record.getMessage())

# Handler бүртгэх
discord_logger = logging.getLogger('discord.http')
discord_logger.addHandler(DiscordRateLimitHandler())
discord_logger.setLevel(logging.WARNING)
