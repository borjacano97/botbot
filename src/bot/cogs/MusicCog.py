import os
from pyclbr import Function
from typing import Any, Callable, Coroutine, List, Optional, Union
from venv import logger
from attr import dataclass
import discord
from discord.ext import commands
from discord.ui import Button, View
import sqlite3
import yt_dlp
import logging
import asyncio

from collections import deque
from enum import Enum
import discord

@dataclass
class Song:
    title: str
    url: str
    path: str
    duration: int

class PlayerState(Enum):
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"

class MusicPlayer:
    def __init__(self) -> None:
        self.queue: deque[Song] = deque()
        self.current_song: Optional[Song] = None
        self.state = PlayerState.STOPPED
        self.volume = 1.0
        self.voice_client: Optional[discord.VoiceClient] = None

    async def connect(self, voice_channel: discord.VoiceChannel) -> None:
        if self.voice_client:
            await self.voice_client.disconnect()
            
        self.voice_client = await voice_channel.connect()

    def add_to_queue(self, song: Song) -> None:
        self.queue.append(song)

    async def play(self) -> None:
        if not self.voice_client or not self.queue:
            return

        if self.state == PlayerState.STOPPED:
            self.current_song = self.queue.popleft()
            if self.voice_client:
                self.voice_client.play(
                    discord.FFmpegPCMAudio(self.current_song.path),
                    after=self._song_finished
                )
            self.state = PlayerState.PLAYING

    def pause(self) -> None:
        if self.voice_client and self.state == PlayerState.PLAYING:
            self.voice_client.pause()
            self.state = PlayerState.PAUSED

    def resume(self) -> None:
        if self.voice_client and self.state == PlayerState.PAUSED:
            self.voice_client.resume()
            self.state = PlayerState.PLAYING

    def stop(self) -> None:
        if self.voice_client and self.voice_client:
            self.voice_client.stop()
            self.state = PlayerState.STOPPED
            self.current_song = None

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))
        if self.voice_client and self.voice_client.source:
            self.voice_client.source = discord.PCMVolumeTransformer(self.voice_client.source, volume=self.volume)

    def skip(self) -> None:
        if self.voice_client:
            self.voice_client.stop()
            self._play_next()

    def _song_finished(self, error: Optional[Exception]) -> None:
        if error:
            print(f"Error en la reproducción: {error}")
        self._play_next()

    def _play_next(self) -> None:
        if len(self.queue) > 0:
            self.current_song = self.queue.popleft()
            if self.voice_client:
                self.voice_client.play(
                    discord.FFmpegPCMAudio(self.current_song.path),
                    after=self._song_finished
                )
            self.state = PlayerState.PLAYING
        else:
            self.state = PlayerState.STOPPED
            self.current_song = None


class MusicCog(commands.Cog):
    LIBRARY_DIR = "data/music"
    DB_PATH = "data/music.db"

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger('musiccog')
        self.music_player = MusicPlayer()
        self.ensuse_db()
        self.create_tables()

    def ensuse_db(self) -> None:
        if not os.path.exists(self.LIBRARY_DIR):
            self.logger.warning("📁 Library directory not found. Creating library directory...")
            os.makedirs(self.LIBRARY_DIR)
        if not os.path.exists(self.DB_PATH):
            self.logger.warning("📁 Database file not found. Creating database file...")
            os.open(self.DB_PATH, os.O_CREAT)
        self.logger.info("✅ Database and library directories ensured.")

    def create_tables(self) -> None:
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

    def get_song(self, title: str) -> Optional[Song]:
        with sqlite3.connect(self.DB_PATH) as conn:
            cursor = conn.execute("SELECT * FROM favorites WHERE title = ?", (title,))
            row = cursor.fetchone()
            if row:
                return Song(title=row[1], url=row[2], path=row[3], duration=row[4])
        return None

    # Grupos de comandos
    music_group = discord.app_commands.Group(name="music", description="Music commands")
    favorites_group = discord.app_commands.Group(name="favorites", description="Favorite songs commands", parent=music_group)

    @music_group.command(name="pause", description="Pause the current song")
    async def music_pause(self, interaction: discord.Interaction) -> None:
        self.music_player.pause()
        await interaction.response.send_message("⏸️ Canción pausada.", ephemeral=True)

    @music_group.command(name="resume", description="Resume the paused song")
    async def music_resume(self, interaction: discord.Interaction) -> None:
        self.music_player.resume()
        await interaction.response.send_message("▶️ Canción resumida.", ephemeral=True)

    @music_group.command(name="stop", description="Stop the current song")
    async def music_stop(self, interaction: discord.Interaction) -> None:
        self.music_player.stop()
        await interaction.response.send_message("⏹️ Canción detenida.", ephemeral=True)

    @music_group.command(name="skip", description="Skip the current song")
    async def music_skip(self, interaction: discord.Interaction) -> None:
        self.music_player.skip()
        await interaction.response.send_message("⏭️ Canción saltada.", ephemeral=True)

    @music_group.command(name="volume", description="Set the volume of the player (0-100)")
    async def music_volume(self, interaction: discord.Interaction, volume: int) -> None:
        MAX = 100
        MIN = 0
        volume_01 = max(MIN, min(MAX, volume)) / 100
        self.music_player.set_volume(volume_01)
        await interaction.response.send_message(f"🔊 Volumen ajustado a {volume}%.", ephemeral=True)

    @favorites_group.command(name="play", description="Play a favorite song")
    async def favorites_play(self, interaction: discord.Interaction) -> None:
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
            def __init__(self, options: List[str], callback: Callable[[discord.Interaction, str], Coroutine[Any, Any, None]]) -> None:
                super().__init__()
                self.select = discord.ui.Select(
                    placeholder="Selecciona una canción favorita",
                    options=[discord.SelectOption(label=title, value=title) for title in options]
                )
                self.select.callback = self.select_callback
                self.callback = callback
                self.add_item(self.select)

            async def select_callback(self, interaction: discord.Interaction) -> None:
                selected_value = self.select.values[0]
                if self.callback and selected_value:
                    await interaction.response.defer(ephemeral=True)
                    await self.callback(interaction, selected_value)

        async def on_title_selected(interaction: discord.Interaction, title: str) -> None:
            song = self.get_song(title)
            if not song:
                await interaction.followup.send("❌ No se encontró la canción seleccionada.", ephemeral=True)
                return
            
            await interaction.followup.send(f"🎵 Reproduciendo: {title}", ephemeral=True)
            if interaction.guild is None:
                await interaction.followup.send("❌ No estás en un servidor.", ephemeral=True)
                return
            
            member = interaction.guild.get_member(interaction.user.id)
            if member is None or member.voice is None or member.voice.channel is None:
                await interaction.followup.send("❌ No estás en un canal de voz.", ephemeral=True)
                return
            if isinstance(member.voice.channel, discord.VoiceChannel):
                await self.music_player.connect(member.voice.channel)
            else:
                await interaction.followup.send("❌ El canal de voz no es válido.", ephemeral=True)

            self.music_player.add_to_queue(song)
            await self.music_player.play()

        await interaction.response.send_message("🎶 Aquí están las canciones favoritas:", view=FavoritesMenu(titles, on_title_selected), ephemeral=True)

    @favorites_group.command(name="add", description="Add a song to the favorites")
    async def favorites_add(self, interaction: discord.Interaction, title: str, url: str) -> None:
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
    async def on_ready(self) -> None:
        # Sincronizar los comandos de barra
        await self.bot.tree.sync()
        self.logger.info("✅ Slash commands synchronized.")