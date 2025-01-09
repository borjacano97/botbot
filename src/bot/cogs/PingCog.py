import discord
from discord.ext import commands

class PingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name='ping', description='Responds with Pong!')
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message('Pong!')