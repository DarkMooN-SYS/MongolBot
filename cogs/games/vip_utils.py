# VIP utility for lottery
from cogs.economy import vip as vip_cog
from discord.ext import commands

async def is_vip(bot: commands.Bot, user_id: int):
    # Find the VIP cog
    cog = bot.get_cog('VIP')
    check_vip_func = getattr(cog, 'check_vip', None)
    if cog and callable(check_vip_func):
        import inspect
        result = check_vip_func(user_id)
        if inspect.isawaitable(result):
            return await result
        return result
    return False

async def get_vip_level(bot: commands.Bot, user_id: int):
    cog = bot.get_cog('VIP')
    get_vip_level_func = getattr(cog, 'get_vip_level', None)
    if cog and callable(get_vip_level_func):
        import inspect
        result = get_vip_level_func(user_id)
        if inspect.isawaitable(result):
            return await result
        return result
    return None
