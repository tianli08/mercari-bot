import os
from dotenv import load_dotenv
from discord_webhook import DiscordWebhook
load_dotenv()

def sendWebhook(product):

    miharaWebhook = os.getenv("MIHARA_CHANNEL")

    webhook = DiscordWebhook(url=miharaWebhook, content=product)
    return webhook.execute()