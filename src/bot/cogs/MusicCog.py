import os
from pyclbr import Function
from typing import Any, Callable, Coroutine, List
from venv import logger
import discord
from discord.ext import commands
from discord.ui import Button, View
import sqlite3
import yt_dlp
import logging
import asyncio


class MusicCog(commands.Cog):
    LIBRARY_DIR = "data/music"
    DB_PATH = "data/music.db"

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('musiccog')
        self.ensuse_db()
        self.create_tables()

    def ensuse_db(self):
        if not os.path.exists(self.LIBRARY_DIR):
            self.logger.warning("📁 Library directory not found. Creating library directory...")
            os.makedirs(self.LIBRARY_DIR)
        if not os.path.exists(self.DB_PATH):
            self.logger.warning("📁 Database file not found. Creating database file...")
            os.open(self.DB_PATH, os.O_CREAT)
        self.logger.info("✅ Database and library directories ensured.")

    def create_tables(self):
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    path TEXT NOT NULL,
                    duration INTEGER NOT NULL,
                    UNIQUE(title)
                )
            """)
        self.logger.info("✅ Tables created or ensured.")

    # Grupos de comandos
    music_group = discord.app_commands.Group(name="music", description="Music commands")
    favorites_group = discord.app_commands.Group(name="favorites", description="Favorite songs commands", parent=music_group)

    async def join_and_play(self, interaction: discord.Interaction, path: str):
        """Join the voice channel and play the specified audio file."""
        if interaction.guild is None:
            await interaction.followup.send("❌ No estás en un servidor.", ephemeral=True)
            return
        
        member = interaction.guild.get_member(interaction.user.id)
        if member is None or member.voice is None:
            await interaction.followup.send("❌ No estás en un canal de voz.", ephemeral=True)
            return
        
        voice_channel = member.voice.channel
        if voice_channel is None:
            await interaction.followup.send("❌ No estás en un canal de voz.", ephemeral=True)
            return
        
        voice_client = await voice_channel.connect()
        logger.info(f"🔊 Joined voice channel: {voice_channel.name}")
        if not os.path.exists(path):
            await interaction.followup.send("❌ No se encontró el archivo de audio.", ephemeral=True)
            return
        
        logger.info(f"🎵 Playing audio file: {path}")
        voice_client.play(discord.FFmpegPCMAudio(path), after=lambda e: logger.error(f'Player error: {e}') if e else None)

        while voice_client.is_playing():
            await asyncio.sleep(1)

        await voice_client.disconnect()

    @favorites_group.command(name="play", description="Play a favorite song")
    async def favorites_play(self, interaction: discord.Interaction):
        # Obtener canciones favoritas de la base de datos
        titles: List[str] = []
        with sqlite3.connect(self.DB_PATH) as conn:
            cursor = conn.execute("SELECT title FROM favorites")
            for row in cursor:
                titles.append(row[0])

        # Si no hay canciones favoritas
        if not titles:
            await interaction.response.send_message("❌ No hay canciones favoritas en la base de datos.", ephemeral=True)
            return

        # Crear el menú interactivo con un Select
        class FavoritesMenu(discord.ui.View):
            def __init__(self, options: List[str], callback: Callable[[discord.Interaction, str], Coroutine[Any, Any, None]]):
                super().__init__()
                self.select = discord.ui.Select(
                    placeholder="Selecciona una canción favorita",
                    options=[discord.SelectOption(label=title, value=title) for title in options]
                )
                self.select.callback = self.select_callback
                self.callback = callback
                self.add_item(self.select)

            async def select_callback(self, interaction: discord.Interaction):
                selected_value = self.select.values[0]
                if self.callback and selected_value:
                    await interaction.response.defer(ephemeral=True)
                    await self.callback(interaction, selected_value)

        async def on_title_selected(interaction: discord.Interaction, title: str):
            with sqlite3.connect(self.DB_PATH) as conn:
                cursor = conn.execute("SELECT path FROM favorites WHERE title = ?", (title,))
                row = cursor.fetchone()
                if row:
                    path = row[0]
                    await interaction.followup.send(f"🎵 Reproduciendo: {title}", ephemeral=True)
                    await self.join_and_play(interaction, path)
                else:
                    await interaction.followup.send("❌ No se encontró la canción seleccionada.", ephemeral=True)

        await interaction.response.send_message("🎶 Aquí están las canciones favoritas:", view=FavoritesMenu(titles, on_title_selected), ephemeral=True)

    @favorites_group.command(name="add", description="Add a song to the favorites")
    async def favorites_add(self, interaction: discord.Interaction, title: str, url: str):
        # Enviar una respuesta diferida
        await interaction.response.defer(ephemeral=True)

        # Buscar si la canción ya está en la base de datos
        with sqlite3.connect(self.DB_PATH) as conn:
            cursor = conn.execute("SELECT * FROM favorites WHERE title = ?", (title,))
            if cursor.fetchone():
                await interaction.followup.send("❌ Ya tienes una canción favorita en la base de datos.", ephemeral=True)
                return
        # Descargar la canción
        path = os.path.join(self.LIBRARY_DIR, title)
        if not path.endswith(".mp3"):
            path += ".mp3"

        duration = 0

        try: 
            ydl_opts = {
                "format": "bestaudio/best",
                # FIXME: Esto es feo de pelotas, pero el cachondo de yt_dlp pone la extensión al final del path
                # así que si ya la tiene, se la quitamos. Porque si no, se descarga como "cancion.mp3.mp3"
                "outtmpl": path if not path.endswith(".mp3") else path[:-4], 
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info: 
                    duration = info.get("duration", 0)
        except Exception as e:
            self.logger.error(f"❌ Error al descargar la canción: {e}")
            await interaction.followup.send(f"❌ Error al descargar la canción: {e}", ephemeral=True)
            return
        
        # Insertar la canción en la base de datos
        try: 
            with sqlite3.connect(self.DB_PATH) as conn:
                conn.execute("INSERT INTO favorites (title, url, path, duration) VALUES (?, ?, ?, ?)", (title, url, path, duration))
        except Exception as e:
            self.logger.error(f"❌ Error al añadir la canción a la base de datos: {e}")
            await interaction.followup.send(f"❌ Error al añadir la canción a la base de datos: {e}", ephemeral=True)
            return

        self.logger.info(f"✅ Canción favorita añadida: {title}")
        await interaction.followup.send("✅ Canción favorita añadida correctamente.", ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        # Sincronizar los comandos de barra
        await self.bot.tree.sync()
        self.logger.info("✅ Slash commands synchronized.")