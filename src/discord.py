import os

from discord_webhook import DiscordWebhook

from config import settings


def sendWebhook(product):
    miharaWebhook = settings.mihara_channel

    webhook = DiscordWebhook(url=miharaWebhook, content=product)
    return webhook.execute()
