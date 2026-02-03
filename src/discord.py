from discord_webhook import DiscordEmbed, DiscordWebhook

def send_webhook(link, desc, channel):
    # Description is a tuple consisting of information about the product
    full_title, image, content = desc

    webhook = DiscordWebhook(url=channel, rate_limit_retry=True)

    embed = DiscordEmbed(title=full_title, url=link)
    embed.set_image(image)
    embed.set_footer(text="Static Archive")
    webhook.add_embed(embed)

    return webhook.execute()
