from math import e
import os
import discord
import logging
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from Botbot import Botbot

async def main():
    try:
        # Set up logging using Discord's utility
        discord.utils.setup_logging()

        # Load environment variables from .env file
        load_dotenv()

        # Get the bot token and development guild ID from environment variables
        BOT_TOKEN = os.getenv('BOT_TOKEN')
        if BOT_TOKEN is None:
            logging.critical('No BOT_TOKEN found in environment variables')
            exit(1)

        DEV_GUILD = os.getenv('DEV_GUILD')
        if DEV_GUILD is None:
            logging.critical('No DEV_GUILD found in environment variables')
            exit(1)
        DEV_GUILD = int(DEV_GUILD)

        # Initialize the bot with a command prefix
        intents = discord.Intents.default()
        intents.messages = True  # To listen to messages.
        intents.message_content = True  # Required if you use Message Content Intent.
        intents.presences = True  # For presence updates, if needed.
        intents.members = True  # For member information.

        bot = Botbot(command_prefix="/", intents=intents, dev_guild=DEV_GUILD)

        logging.info('Bot initialized')

        await bot.start(BOT_TOKEN)
    except discord.LoginFailure:
        logging.critical('Invalid token')
        exit(1)
    except discord.HTTPException:
        logging.critical('Failed to connect to Discord')
        exit(1)
    except KeyboardInterrupt:
        logging.info('Bot shutting down')
    except Exception as e:
        logging.critical(f'An error occurred: {e}')
        exit(1)
    finally:
        await bot.close()
        logging.info('Bot shut down')
        exit(0)

if __name__ == "__main__":
    asyncio.run(main())