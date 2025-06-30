import threading
import asyncio
from flask import Flask, request, jsonify
from discord.ext import commands
import discord

app = Flask(__name__)
bot_instance = None
CHANNEL_ID = 1297446170263552022  # Энд Discord channel-ийн ID-г оруулна уу

@app.route("/github", methods=["POST"])
def github_webhook():
    data = request.json
    if not data or "commits" not in data:
        return jsonify({"error": "Invalid payload"}), 400

    repo = data.get("repository", {}).get("full_name", "Unknown repo")
    pusher = data.get("pusher", {}).get("name", "Unknown user")
    commits = data.get("commits", [])
    commit_messages = "\n".join([f"[`{c['id'][:7]}`]({c['url']}) {c['message']} - {c['author']['name']}" for c in commits])
    branch = data.get("ref", "refs/heads/main").split("/")[-1]

    content = f"**{pusher}** pushed to **{branch}** in **{repo}**\n{commit_messages}"

    if bot_instance:
        loop = asyncio.get_event_loop()
        loop.create_task(send_to_discord(content))
        return jsonify({"status": "ok"})
    else:
        return jsonify({"error": "Bot not ready"}), 500

async def send_to_discord(content: str):
    if bot_instance is not None:
        channel = bot_instance.get_channel(CHANNEL_ID)
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            await channel.send(content)

class GithubWebhookCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        global bot_instance
        bot_instance = bot
        self.bot = bot
        threading.Thread(target=self.run_flask, daemon=True).start()

    def run_flask(self):
        app.run(host="46.247.108.38", port=6229)

async def setup(bot: commands.Bot):
    await bot.add_cog(GithubWebhookCog(bot))
