from discord_webhook import DiscordEmbed, DiscordWebhook
from dotenv import load_dotenv

load_dotenv()


def sendWebhook(productLink, description, channel):
    # Description is a tuple consisting of information about the product
    fullTitle, image, content = description

    webhook = DiscordWebhook(url=channel, rate_limit_retry=True)

    embed = DiscordEmbed(title=fullTitle, url=productLink)
    embed.set_image(image)
    embed.set_footer(text="Static Archive")
    webhook.add_embed(embed)

    return webhook.execute()
