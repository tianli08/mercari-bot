from discord_webhook import DiscordWebhook

def sendWebhook(product):
    webhook = DiscordWebhook(url="https://discord.com/api/webhooks/1465144214948937853/M_qGcwL4NuxOKE0R_TG1dG7ibN9GJlvJWmPPMkk-f91a0t8pbpyP6mLfo4zlVu3G-65T", content=product)
    return webhook.execute()