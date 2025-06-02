default_prefix = ["m", "M"]
prefixes = {}

def get_prefix(bot, message):
    """Get the command prefix for a specific guild."""
    guild_id = message.guild.id if message.guild else None
    return prefixes.get(guild_id, default_prefix)

async def set_prefix(guild_id, new_prefix):
    """Set a new command prefix for a specific guild."""
    if len(new_prefix) > 15:
        return "Prefix must be 15 characters or less."
    
    prefixes[guild_id] = new_prefix
    return f'Command prefix changed to: `{new_prefix}`'