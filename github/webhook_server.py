import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Discord webhook URL-г энд оруулна уу
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1389275813391765595/7hJzP18NsP0Z_sLPzZiLy58io-E628mSOkNiY7oZa5HIUABmbm_OAn6UUGo-YRoqvfDj"

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

    payload = {
        "content": content
    }
    resp = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    if resp.status_code != 204 and resp.status_code != 200:
        return jsonify({"error": "Failed to send to Discord", "discord_status": resp.status_code}), 500
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="46.247.108.38", port=6229)