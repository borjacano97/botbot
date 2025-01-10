from datetime import timedelta
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
from youtube_dl import YoutubeDL

import logging
import asyncio

from collections import deque
from enum import Enum
import discord

@dataclass
class Song:
    title: str
    url: str
    path: str|None
    duration: int

class PlayerState(Enum):
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"

import abc

class IMusicPlayer(abc.ABC):
    @abc.abstractmethod 
    async def connect(self, voice_channel: discord.VoiceChannel) -> None: pass

    @abc.abstractmethod
    def add_to_queue(self, song: Song) -> None: pass
    
    @abc.abstractmethod
    def get_queue(self) -> List[Song]: pass
    
    @abc.abstractmethod
    def remove_from_queue(self, index: int) -> Song|None: pass
    
    @abc.abstractmethod
    def play(self) -> None: pass

    @abc.abstractmethod
    def pause(self) -> None: pass

    @abc.abstractmethod
    def resume(self) -> None: pass

    @abc.abstractmethod
    def stop(self) -> None: pass

    @abc.abstractmethod
    def set_volume(self, volume: float) -> None: pass

    @abc.abstractmethod
    def skip(self) -> None: pass

    @abc.abstractmethod
    def _song_finished(self, error: Optional[Exception]) -> None: pass

    @abc.abstractmethod
    def _play_next(self) -> None: pass

    @abc.abstractmethod
    def destroy(self) -> None: pass

class DowloadedMusicPlayer(IMusicPlayer):
    def __init__(self) -> None:
        self.queue: deque[Song] = deque()
        self.current_song: Optional[Song] = None
        self.state = PlayerState.STOPPED
        self.volume = 1.0
        self.voice_client: Optional[discord.VoiceClient] = None
        logger.debug("DowloadedMusicPlayer initialized")

    def __del__(self) -> None:
        self.destroy()

    async def connect(self, voice_channel: discord.VoiceChannel) -> None:
        logger.debug(f"Connecting to voice channel: {voice_channel}")
        if self.voice_client:
            await self.voice_client.disconnect()
            
        self.voice_client = await voice_channel.connect()
        logger.info("Connected to voice channel")

    def add_to_queue(self, song: Song) -> None:
        self.queue.append(song)
        logger.debug(f"Added to queue: {song.title}")
        
    def get_queue(self) -> List[Song]:
        return list(self.queue)
    
    def remove_from_queue(self, index: int) -> Song|None:
        if 0 <= index < len(self.queue):
            song = self.queue[index]
            self.queue.remove(song)
            logger.debug(f"Removed from queue: {song.title}")
            return song
        return None

    def play(self) -> None:
        if not self.voice_client or not self.queue:
            logger.warning("No voice client or queue is empty")
            return

        if self.state == PlayerState.STOPPED:
            self.current_song = self.queue.popleft()
            if self.voice_client and self.current_song and self.current_song.path:
                self.voice_client.play(
                    discord.FFmpegPCMAudio(self.current_song.path),
                    after=self._song_finished
                )
            self.state = PlayerState.PLAYING
            logger.info(f"Playing song: {self.current_song.title}")

    def pause(self) -> None:
        if self.voice_client and self.state == PlayerState.PLAYING:
            self.voice_client.pause()
            self.state = PlayerState.PAUSED
            logger.info("Paused song")

    def resume(self) -> None:
        if self.voice_client and self.state == PlayerState.PAUSED:
            self.voice_client.resume()
            self.state = PlayerState.PLAYING
            logger.info("Resumed song")

    def stop(self) -> None:
        if self.voice_client and self.voice_client:
            self.voice_client.stop()
            self.state = PlayerState.STOPPED
            self.current_song = None
            logger.info("Stopped song")

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))
        if self.voice_client and self.voice_client.source:
            self.voice_client.source = discord.PCMVolumeTransformer(self.voice_client.source, volume=self.volume)
        logger.debug(f"Set volume to: {self.volume}")

    def skip(self) -> None:
        if self.voice_client:
            self.voice_client.stop()
            self._play_next()
        logger.info("Skipped song")

    def _song_finished(self, error: Optional[Exception]) -> None:
        if error:
            logger.error(f"Error en la reproducción: {error}")
        self._play_next()

    def _play_next(self) -> None:
        if len(self.queue) > 0:
            self.current_song = self.queue.popleft()
            if self.voice_client and self.current_song and self.current_song.path:
                self.voice_client.play(
                    discord.FFmpegPCMAudio(self.current_song.path),
                    after=self._song_finished
                )
            self.state = PlayerState.PLAYING
            logger.info(f"Playing next song: {self.current_song.title}")
        else:
            self.state = PlayerState.STOPPED
            self.current_song = None
            logger.info("Queue is empty, stopped playing")

    def destroy(self) -> None:
        if self.voice_client:
            self.voice_client.cleanup()
            self.voice_client = None
        logger.debug("Destroyed DowloadedMusicPlayer")

class StreamMusicPlayer(IMusicPlayer):
    def __init__(self) -> None:
        self.queue: deque[Song] = deque()
        self.current_song: Optional[Song] = None
        self.state = PlayerState.STOPPED
        self.volume = 1.0
        self.voice_client: Optional[discord.VoiceClient] = None
        logger.debug("StreamMusicPlayer initialized")

    def __del__(self) -> None:
        self.destroy()

    def get_queue(self) -> List[Song]:
        return list(self.queue)
    
    def remove_from_queue(self, index: int) -> Song|None:
        if 0 <= index < len(self.queue):
            song = self.queue[index]
            self.queue.remove(song)
            logger.debug(f"Removed from queue: {song.title}")
            return song
        return None

    def destroy(self) -> None:
        if self.voice_client:
            self.voice_client.cleanup()
            self.voice_client = None
        logger.debug("Destroyed StreamMusicPlayer")

    async def connect(self, voice_channel: discord.VoiceChannel) -> None:
        logger.debug(f"Connecting to voice channel: {voice_channel}")
        if self.voice_client:
            await self.voice_client.disconnect()
            
        self.voice_client = await voice_channel.connect()
        logger.info("Connected to voice channel")

    def add_to_queue(self, song: Song) -> None:
        self.queue.append(song)
        logger.debug(f"Added to queue: {song.title}")

    def play(self) -> None:
        if not self.voice_client or not self.queue:
            logger.warning("No voice client or queue is empty")
            return

        if self.state == PlayerState.STOPPED:
            try:
                self.current_song = self.queue.popleft()
                if not self.voice_client or not self.voice_client.is_connected():
                    logger.error("Voice client no está conectado o inicializado")
                    return
                
                ffmpeg_options = {
                    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                    'options': '-vn'
                }
                audio_source = discord.FFmpegPCMAudio(self.current_song.url, before_options=ffmpeg_options['before_options'])

                
                def after_callback(error):
                    if error:
                        logger.error(f"Error en reproducción: {error}")
                    self._song_finished()

                try:
                    if self.voice_client.is_playing():
                        self.voice_client.stop()
                    self.voice_client.play(audio_source, after=after_callback)
                except Exception as e:
                    logger.exception(f"Error al reproducir canción: {str(e)}")
                    self.state = PlayerState.STOPPED
                    self._song_finished()
                
                self.state = PlayerState.PLAYING
                logger.info(f"Playing song: {self.current_song.title}")
                
            except Exception as e:
                logger.exception(f"Error al reproducir canción: {str(e)}")
                self.state = PlayerState.STOPPED
                self._song_finished()

    def pause(self) -> None:
        if self.voice_client and self.state == PlayerState.PLAYING:
            self.voice_client.pause()
            self.state = PlayerState.PAUSED
            logger.info("Paused song")

    def resume(self) -> None:
        if self.voice_client and self.state == PlayerState.PAUSED:
            self.voice_client.resume()
            self.state = PlayerState.PLAYING
            logger.info("Resumed song")

    def stop(self) -> None:
        if self.voice_client and self.voice_client:
            self.voice_client.stop()
            self.state = PlayerState.STOPPED
            self.current_song = None
            logger.info("Stopped song")

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))
        if self.voice_client and self.voice_client.source:
            self.voice_client.source = discord.PCMVolumeTransformer(self.voice_client.source, volume=self.volume)
        logger.debug(f"Set volume to: {self.volume}")

    def skip(self) -> None:
        if self.voice_client:
            self.voice_client.stop()
            self._play_next()
        logger.info("Skipped song")

    def _song_finished(self, error: Optional[Exception] = None) -> None:
        if error:
            logger.error(f"Error en la reproducción: {error}")
        self._play_next()

    def _play_next(self) -> None:
        if self.queue and len(self.queue) > 0:
            self.current_song = self.queue.popleft()
            if self.voice_client:
                self.voice_client.play(
                    discord.FFmpegPCMAudio(self.current_song.url),
                    after=lambda e: self._song_finished(e)
                )
            self.state = PlayerState.PLAYING
            logger.info(f"Playing next song: {self.current_song.title}")
        else:
            self.state = PlayerState.STOPPED
            self.current_song = None
            logger.info("Queue is empty, stopped playing")

class MusicCog(commands.Cog):
    LIBRARY_DIR = "data/music"
    DB_PATH = "data/music.db"

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger('musiccog')
        self.music_player : IMusicPlayer | None = None
        self.ensuse_db()
        self.create_tables()
        logger.debug("MusicCog initialized")

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
                CREATE TABLE IF NOT EXISTS fav (
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
            cursor = conn.execute("SELECT * FROM fav WHERE title = ?", (title,))
            row = cursor.fetchone()
            if row:
                logger.debug(f"Song found in database: {title}")
                return Song(title=row[1], url=row[2], path=row[3], duration=row[4])
        logger.debug(f"Song not found in database: {title}")
        return None

    # Grupos de comandos
    music_group = discord.app_commands.Group(name="music", description="Music commands")
    fav_group = discord.app_commands.Group(name="fav", description="Favorite songs commands", parent=music_group)
    queue_group = discord.app_commands.Group(name="queue", description="Queue commands", parent=music_group)

    @music_group.command(name="pause", description="Pause the current song")
    async def music_pause(self, interaction: discord.Interaction) -> None:
        if not self.music_player:
            await interaction.response.send_message("❌ Reproductor no activo", ephemeral=True)
            return
        
        self.music_player.pause()
        await interaction.response.send_message("⏸️ Canción pausada.", ephemeral=True)
        logger.info("Paused song via command")

    @music_group.command(name="resume", description="Resume the paused song")
    async def music_resume(self, interaction: discord.Interaction) -> None:
        if not self.music_player:
            await interaction.response.send_message("❌ Reproductor no activo", ephemeral=True)
            return
        self.music_player.resume()
        await interaction.response.send_message("▶️ Canción resumida.", ephemeral=True)
        logger.info("Resumed song via command")

    @music_group.command(name="stop", description="Stop the current song")
    async def music_stop(self, interaction: discord.Interaction) -> None:
        if not self.music_player:
            await interaction.response.send_message("❌ Reproductor no activo", ephemeral=True)
            return
        
        self.music_player.stop()
        await interaction.response.send_message("⏹️ Canción detenida.", ephemeral=True)
        logger.info("Stopped song via command")

    @music_group.command(name="skip", description="Skip the current song")
    async def music_skip(self, interaction: discord.Interaction) -> None:
        if not self.music_player:
            await interaction.response.send_message("❌ Reproductor no activo", ephemeral=True)
            return
        
        self.music_player.skip()
        await interaction.response.send_message("⏭️ Canción saltada.", ephemeral=True)
        logger.info("Skipped song via command")

    @music_group.command(name="volume", description="Set the volume of the player (0-100)")
    async def music_volume(self, interaction: discord.Interaction, volume: int) -> None:
        MAX = 100
        MIN = 0
        volume_01 = max(MIN, min(MAX, volume)) / 100
        if not self.music_player:
            await interaction.response.send_message("❌ Reproductor no activo", ephemeral=True)
            return
        
        self.music_player.set_volume(volume_01)
        await interaction.response.send_message(f"🔊 Volumen ajustado a {volume}%.", ephemeral=True)
        logger.info(f"Set volume to {volume}% via command")

    @fav_group.command(name="play", description="Play a favorite song")
    async def fav_play(self, interaction: discord.Interaction) -> None:
        # Obtener canciones favoritas de la base de datos
        titles: List[str] = []
        with sqlite3.connect(self.DB_PATH) as conn:
            cursor = conn.execute("SELECT title FROM fav")
            for row in cursor:
                titles.append(row[0])

        # Si no hay canciones favoritas
        if not titles:
            await interaction.response.send_message("❌ No hay canciones favoritas en la base de datos.", ephemeral=True)
            return

        # Crear el menú interactivo con un Select
        class favMenu(discord.ui.View):
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
            if not self.music_player:
                    self.music_player = DowloadedMusicPlayer()
                    
            if not song:
                await interaction.followup.send("❌ No se encontró la canción seleccionada.", ephemeral=True)
                return
            
            await interaction.followup.send(f"🎵 Reproduciendo: {title}", ephemeral=True)
            if interaction.guild is None:
                await interaction.followup.send("❌ No estás en un servidor.", ephemeral=True)
                return
            
            member = interaction.guild.get_member(interaction.user.id)
            if member is None or member.voice is None or member.voice.channel is None or not isinstance(member.voice.channel, discord.VoiceChannel):
                await interaction.followup.send("❌ No estás en un canal de voz.", ephemeral=True)
                return
            await self.music_player.connect(member.voice.channel)

            self.music_player.add_to_queue(song)
            self.music_player.play()
            logger.info(f"Playing favorite song: {title}")

        await interaction.response.send_message("🎶 Aquí están las canciones favoritas:", view=favMenu(titles, on_title_selected), ephemeral=True)

    @fav_group.command(name="add", description="Add a song to the fav")
    async def fav_add(self, interaction: discord.Interaction, title: str, url: str) -> None:
        # Enviar una respuesta diferida
        await interaction.response.defer(ephemeral=True)

        # Buscar si la canción ya está en la base de datos
        with sqlite3.connect(self.DB_PATH) as conn:
            cursor = conn.execute("SELECT * FROM fav WHERE title = ?", (title,))
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
                conn.execute("INSERT INTO fav (title, url, path, duration) VALUES (?, ?, ?, ?)", (title, url, path, duration))
        except Exception as e:
            self.logger.error(f"❌ Error al añadir la canción a la base de datos: {e}")
            await interaction.followup.send(f"❌ Error al añadir la canción a la base de datos: {e}", ephemeral=True)
            return

        self.logger.info(f"✅ Canción favorita añadida: {title}")
        await interaction.followup.send("✅ Canción favorita añadida correctamente.", ephemeral=True)

    @music_group.command(name="search", description="Play a song")
    async def music_search(self, interaction: discord.Interaction, query: str) -> None:
        MAX_RESULTS = 5
        MAX_DURATION = 3600  # 1 hora en segundos
        TIMEOUT = 60  # Tiempo máximo para seleccionar

        # Enviar una respuesta diferida
        await interaction.response.defer(ephemeral=True)

        # Buscar la canción en YouTube. Recogemos los 5 primeros resultados
        ydl_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
        }

        TITLE_KEY = "title"
        URL_KEY = "webpage_url"
        DURATION_KEY = "duration"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await interaction.followup.send("🔍 Buscando...", ephemeral=True)
            loop = asyncio.get_event_loop()
            try:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch{MAX_RESULTS}:{query}", download=False))
                if not info:
                    await interaction.followup.send("❌ No se encontraron resultados.", ephemeral=True)
                    return

                songs = []
                entries = info.get('entries', [info])

                for entry in entries:
                    if not all(key in entry for key in [TITLE_KEY, URL_KEY, DURATION_KEY]):
                        continue

                    duration = entry[DURATION_KEY]
                    if duration > MAX_DURATION:
                        continue

                    songs.append(Song(
                        title=entry[TITLE_KEY],
                        url=entry[URL_KEY],
                        path=None,
                        duration=duration
                    ))
                    logger.debug(f"🎵 Canción encontrada: {entry[TITLE_KEY]} [{entry[URL_KEY]}]")

                if not songs:
                    await interaction.followup.send("❌ No se encontraron canciones válidas.", ephemeral=True)
                    return

                # Crear el menú interactivo con un Select
                class SearchMenu(discord.ui.View):
                    def __init__(self, songs: List[Song], callback: Callable[[discord.Interaction, str, List[Song]], Coroutine[Any, Any, None]]) -> None:
                        super().__init__(timeout=TIMEOUT)
                        self.select = discord.ui.Select(
                            placeholder="Selecciona una canción",
                            options=[discord.SelectOption(
                                label=f"{option.title[:80]}...", 
                                value=f"{option.title}_{i}",
                                description=f"Duración: {option.duration//60:02d}:{option.duration%60:02d}"
                            ) for i, option in enumerate(songs)]
                        )
                        self.select.callback = self.select_callback
                        self.callback = callback
                        self.songs = songs
                        self.add_item(self.select)

                    async def select_callback(self, interaction: discord.Interaction) -> None:
                        if not self.select.values:
                            await interaction.response.send_message("❌ No se seleccionó ninguna canción.", ephemeral=True)
                            return
                            
                        selected_value = self.select.values[0]
                        title = selected_value.rsplit('_', 1)[0]
                        await interaction.response.defer(ephemeral=True)
                        await self.callback(interaction, title, self.songs)

            except Exception as e:
                logger.error(f"Error al buscar canciones: {e}")
                await interaction.followup.send("❌ Ocurrió un error al buscar canciones.", ephemeral=True)

            async def on_song_selected(interaction: discord.Interaction, title: str, songs: List[Song]) -> None:
                song = next((song for song in songs if song.title == title), None)
                if not song:
                    await interaction.followup.send("❌ No se encontró la canción seleccionada.", ephemeral=True)
                    return

                if not self.music_player or not isinstance(self.music_player, StreamMusicPlayer):
                    self.music_player = StreamMusicPlayer()

                await interaction.followup.send(f"🎵 Reproduciendo: {title}", ephemeral=True)
                if interaction.guild is None:
                    await interaction.followup.send("❌ No estás en un servidor.", ephemeral=True)
                    return
                
                member = interaction.guild.get_member(interaction.user.id)
                if member is None or member.voice is None or member.voice.channel is None or not isinstance(member.voice.channel, discord.VoiceChannel):
                    await interaction.followup.send("❌ No estás en un canal de voz.", ephemeral=True)
                    return
                await self.music_player.connect(member.voice.channel)

                # Añadir la canción a la cola
                self.music_player.add_to_queue(song)

                # Si no se está reproduciendo, reproducir
                if self.music_player.state != PlayerState.PLAYING:
                    self.music_player.play()
                    logger.info(f"Playing song: {title}")

            await interaction.followup.send("🎶 Aquí están los resultados:", view=SearchMenu(songs, on_song_selected), ephemeral=True)
            
    @music_group.command(name="stream", description="Reproduce una canción en streaming")
    async def music_stream(self, interaction: discord.Interaction, url: str) -> None:
        await interaction.response.defer(ephemeral=True)
        
        if not self.music_player or not isinstance(self.music_player, StreamMusicPlayer):
            self.music_player = StreamMusicPlayer()
        
        ydl_opts = {"format": "bestaudio/best", "quiet": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info or 'url' not in info or 'title' not in info or 'duration' not in info:
                await interaction.followup.send("❌ No se encontró la URL de la canción.", ephemeral=True)
                return
            
            song = Song(title=info['title'], url = info['url'], path = None, duration = info.get('duration', 0))
            self.music_player.add_to_queue(song)
            
            if self.music_player.state != PlayerState.PLAYING:
                if interaction.guild is None:
                    await interaction.followup.send("❌ No estás en un servidor.", ephemeral=True)
                    return
                
                member = interaction.guild.get_member(interaction.user.id)
                if member is None or member.voice is None or member.voice.channel is None or not isinstance(member.voice.channel, discord.VoiceChannel):
                    await interaction.followup.send("❌ No estás en un canal de voz.", ephemeral=True)
                    return
                await self.music_player.connect(member.voice.channel)
                self.music_player.play()
                await interaction.followup.send(f"🎵 Reproduciendo {song.title}", ephemeral=True)
                logger.info(f"Playing song from URL: {url}")
            else: 
                await interaction.followup.send("🎵 Canción añadida a la cola.", ephemeral=True)
                logger.info(f"Added song to queue from URL: {url}")
    
    
    @queue_group.command(name="list", description="List the songs in the queue")
    async def queue_list(self, interaction: discord.Interaction) -> None:
        if not self.music_player:
            await interaction.response.send_message("❌ Reproductor no activo", ephemeral=True)
            return
        q = self.music_player.get_queue()
        if not q or len(q) == 0:
            await interaction.response.send_message("❌ La cola está vacía.", ephemeral=True)
            return

        songs = [f"{index + 1}. {song.title}" for index, song in enumerate(q)]
        await interaction.response.send_message(f"🎵 Canciones en la cola:\n" + "\n".join(songs), ephemeral=True)
        logger.info("Listed queue via command")
    
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # Sincronizar los comandos de barra
        await self.bot.tree.sync()
        self.logger.info("✅ Slash commands synchronized.")