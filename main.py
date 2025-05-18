import os
from ticket_bot import bot

token = os.getenv("DISCORD_TOKEN")

if __name__ == "__main__":
    bot.run(token)
