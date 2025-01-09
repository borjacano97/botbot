import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the bot token and development guild ID from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
DEV_GUILD = int(os.getenv('DEV_GUILD'))

# Initialize the bot with a command prefix
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')

@bot.command(name='ping')
async def ping(ctx):
    await ctx.send('Pong!')

# Run the bot with the token
bot.run(BOT_TOKEN)