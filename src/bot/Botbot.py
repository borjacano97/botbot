import discord
from discord.ext import commands
from discord.ext.commands import Context
import logging

from cogs.PingCog import PingCog
from cogs.MusicCog import MusicCog

class Botbot(commands.Bot):
    def __init__(self, *args, dev_guild=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.dev_guild = dev_guild
        self.logger = logging.getLogger('botbot')

    async def setup_hook(self):
        await self.add_cog(PingCog(self))
        await self.add_cog(MusicCog(self))

        if self.dev_guild:
            guild = discord.Object(id=self.dev_guild)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self):
        if self.user is None:
            self.logger.error("❌ Bot is not ready")
            return
        
        self.logger.info(f'✅ Logged in as {self.user.name} ({self.user.id})')
        self.logger.info('------')


