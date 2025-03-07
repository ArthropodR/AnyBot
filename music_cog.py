import asyncio
import random
import re
import traceback
from typing import Optional, List, Dict

import discord
import yt_dlp
import lyricsgenius
import requests
from discord.ext import commands, pages

class TrackInfo:
    def __init__(self, data: Dict):
        self.title = data.get('title', 'Unknown Track')
        self.url = data.get('webpage_url')
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail')
        self.stream_url = data.get('url')
        self.id = data.get('id')
        self.requester = data.get('requester')
        self.artist = data.get('artist')

class MusicQueue:
    def __init__(self):
        self._queue: List[TrackInfo] = []
        self._history: List[TrackInfo] = []

    def add(self, track: TrackInfo):
        self._queue.append(track)

    def next(self) -> Optional[TrackInfo]:
        if not self._queue:
            return None
        track = self._queue.pop(0)
        self._history.append(track)
        return track

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def __len__(self):
        return len(self._queue)

    def get_queue(self):
        return self._queue.copy()

class Music(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.queue = MusicQueue()
        self.current_track = None
        self.voice_client = None
        self.is_loop = False
        self.is_playing = False
        self.volume = 1.0
        
        try:
            self.genius = lyricsgenius.Genius("")
            self.genius.verbose = False
            self.genius.remove_section_headers = True
        except:
            self.genius = None

        self.YDL_OPTIONS = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'default_search': 'ytsearch',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'quiet': True,  
            'no_warnings': True,
        }

        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

    @staticmethod
    def format_duration(seconds: Optional[int]) -> str:
        if not seconds:
            return "∞ Live/Unknown"
        
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        
        parts = []
        if hours:
            parts.append(f"{hours:02d}h")
        parts.append(f"{minutes:02d}m")
        parts.append(f"{secs:02d}s")
        
        return " ".join(parts)

    def _fetch_track_info(self, query: str, requester: discord.Member):
        try:
            with yt_dlp.YoutubeDL(self.YDL_OPTIONS) as ydl:
                info = ydl.extract_info(query, download=False)
        
            if 'entries' in info:
                info = info['entries'][0]
        
            artist = None
            if self.genius:
                try:
                    title_parts = info.get('title', '').split('-')
                    if len(title_parts) > 1:
                        artist = title_parts[0].strip()
                
                    if not artist:
                        song = self.genius.search_song(info.get('title', ''))
                        artist = song.artist if song else None
                except Exception as e:
                    print(f"Lyrics search error: {e}")

            return TrackInfo({
                'title': info.get('title', 'Unknown Track'),
                'webpage_url': info.get('webpage_url'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'url': info.get('url'),
                'id': info.get('id'),
                'requester': requester,
                'artist': artist or info.get('uploader')
            })
        except Exception as e:
            print(f"Track retrieval failed: {e}")
            print(traceback.format_exc())
            raise ValueError(f"Track retrieval failed: {str(e)}")

    async def _play_track(self, ctx: commands.Context, track: TrackInfo):
        try:
            if not ctx.author.voice or not ctx.author.voice.channel:
                if ctx.voice_client:
                    await ctx.voice_client.disconnect()
                return

            if not ctx.voice_client:
                await ctx.author.voice.channel.connect()

            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()

            try:
                source = discord.FFmpegPCMAudio(
                    track.stream_url, 
                    **self.FFMPEG_OPTIONS
                )
                
                volume_controlled = discord.PCMVolumeTransformer(source, volume=self.volume)
                
            except Exception as ffmpeg_error:
                print(f"FFmpeg Error: {ffmpeg_error}")
                await ctx.send(embed=discord.Embed(
                    title="Playback Error", 
                    description=f"Could not convert track to audio: {str(ffmpeg_error)}", 
                    color=0xe74c3c
                ))
                return

            try:
                ctx.voice_client.play(
                    volume_controlled, 
                    after=lambda e: asyncio.run_coroutine_threadsafe(
                        self._track_finished(ctx), 
                        self.client.loop
                    ) if e is None else print(f"Player error: {e}" if e else "Unknown player error")
                )
            except Exception as play_error:
                print(f"Playback Error: {play_error}")
                await ctx.send(embed=discord.Embed(
                    title="Playback Error", 
                    description=f"Could not play track: {str(play_error)}", 
                    color=0xe74c3c
                ))
                return

            self.current_track = track
            self.is_playing = True

            embed = discord.Embed(
                title="🎵 Now Playing", 
                description=f"**{track.title}**\n"
                            f"Artist: {track.artist or 'Unknown'}\n"
                            f"Duration: {self.format_duration(track.duration)}\n"
                            f"Requested by: {track.requester.mention}",
                color=0x2ecc71
            )
            embed.set_thumbnail(url=track.thumbnail)
            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Unexpected error in _play_track: {e}")
            await ctx.send(embed=discord.Embed(
                title="Playback Error", 
                description=f"Unexpected error: {str(e)}", 
                color=0xe74c3c
            ))
            if ctx.voice_client:
                await ctx.voice_client.disconnect()


    async def _track_finished(self, ctx: commands.Context):
        self.is_playing = False

        if self.is_loop and self.current_track:
            await self._play_track(ctx, self.current_track)
            return

        next_track = self.queue.next()
        if next_track:
            await self._play_track(ctx, next_track)
        else:
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
                self.current_track = None

    @commands.hybrid_command(name="lyrics")
    async def get_lyrics(self, ctx: commands.Context, *, query: Optional[str] = None):
        if not self.genius:
            return await ctx.send("Lyrics service is not available.")

        try:
            if not query and self.current_track:
                query = f"{self.current_track.title} {self.current_track.artist}"
            
            if not query:
                return await ctx.send("Please provide a song name or play a track first.")

            song = self.genius.search_song(query)
            
            if not song:
                return await ctx.send(f"No lyrics found for {query}")

            lyrics_pages = []
            lyrics_chunks = [song.lyrics[i:i+4000] for i in range(0, len(song.lyrics), 4000)]
            
            for i, chunk in enumerate(lyrics_chunks, 1):
                embed = discord.Embed(
                    title=f"Lyrics - {song.title} by {song.artist} (Page {i}/{len(lyrics_chunks)})",
                    description=chunk,
                    color=0x3498db
                )
                lyrics_pages.append(embed)

            paginator = pages.Paginator(pages=lyrics_pages)
            await paginator.send(ctx)

        except Exception as e:
            await ctx.send(f"Error fetching lyrics: {str(e)}")

    @commands.hybrid_command(name="saveplaylist")
    async def save_playlist(self, ctx: commands.Context, name: str):
        if not self.queue.get_queue():
            return await ctx.send("No tracks in the queue to save.")

        try:
            playlist_data = {
                'name': name,
                'tracks': [
                    {
                        'title': track.title,
                        'url': track.url
                    } for track in self.queue.get_queue()
                ]
            }

            try:
                with open(f"playlists/{ctx.author.id}_{name}.txt", "w") as f:
                    import json
                    json.dump(playlist_data, f)
            except FileNotFoundError:
                import os
                os.makedirs("playlists", exist_ok=True)
                with open(f"playlists/{ctx.author.id}_{name}.txt", "w") as f:
                    import json
                    json.dump(playlist_data, f)

            await ctx.send(f"Playlist '{name}' saved successfully!")

        except Exception as e:
            await ctx.send(f"Error saving playlist: {str(e)}")

    @commands.hybrid_command(name="loadplaylist")
    async def load_playlist(self, ctx: commands.Context, name: str):
        try:
            with open(f"playlists/{ctx.author.id}_{name}.txt", "r") as f:
                import json
                playlist_data = json.load(f)

            self.queue.clear()
            for track_info in playlist_data['tracks']:
                track = self._fetch_track_info(track_info['url'], ctx.author)
                self.queue.add(track)

            await ctx.send(f"Playlist '{name}' loaded successfully!")

            if not self.is_playing:
                next_track = self.queue.next()
                await self._play_track(ctx, next_track)

        except FileNotFoundError:
            await ctx.send(f"Playlist '{name}' not found.")
        except Exception as e:
            await ctx.send(f"Error loading playlist: {str(e)}")

    @commands.hybrid_command(name="search")
    async def advanced_search(self, ctx: commands.Context, *, query: str):
        try:
            with yt_dlp.YoutubeDL(self.YDL_OPTIONS) as ydl:
                search_results = ydl.extract_info(f"ytsearch5:{query}", download=False)['entries']

            search_pages = []
            for i, result in enumerate(search_results, 1):
                embed = discord.Embed(
                    title=f"Search Results for '{query}'",
                    description=f"{i}. **{result['title']}**\n"
                                f"Channel: {result.get('uploader', 'Unknown')}\n"
                                f"Duration: {self.format_duration(result.get('duration'))}\n"
                                f"[Watch on YouTube]({result['webpage_url']})",
                    color=0x3498db
                )
                embed.set_thumbnail(url=result.get('thumbnail'))
                search_pages.append(embed)

            paginator = pages.Paginator(pages=search_pages)
            await paginator.send(ctx)

        except Exception as e:
            await ctx.send(f"Search failed: {str(e)}")

    @commands.command(name="connect", aliases=["join"])
    async def connect(self, ctx: commands.Context):
        if not ctx.author.voice:
            return await ctx.send("You must be in a voice channel.")
        
        await ctx.author.voice.channel.connect()
        await ctx.send(f"Connected to {ctx.author.voice.channel.name}")

    @commands.command(name="disconnect", aliases=["leave"])
    async def disconnect(self, ctx: commands.Context):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("Disconnected from voice channel.")
        else:
            await ctx.send("Not connected to a voice channel.")

    @commands.hybrid_command(name="play")
    async def play(self, ctx: commands.Context, *, query: str):
        await ctx.defer()

        if not ctx.author.voice:
            return await ctx.send(embed=discord.Embed(
                title="Connection Required", 
                description="Please join a voice channel first.", 
                color=0xe74c3c
            ))

        try:
            track = self._fetch_track_info(query, ctx.author)

            if self.is_playing:
                self.queue.add(track)
                await ctx.send(embed=discord.Embed(
                    title="Added to Queue", 
                    description=f"**{track.title}** has been added to the playlist.", 
                    color=0x3498db
                ))
            else:
                await self._play_track(ctx, track)

        except ValueError as ve:
            await ctx.send(embed=discord.Embed(
                title="Track Error", 
                description=str(ve), 
                color=0xe74c3c
            ))

    @commands.hybrid_command(name="queue")
    async def show_queue(self, ctx: commands.Context):
        queue_list = self.queue.get_queue()
        
        if not queue_list:
            return await ctx.send(embed=discord.Embed(
                title="Queue Status", 
                description="No tracks in the queue.", 
                color=0xf39c12
            ))

        queue_pages = []
        for i in range(0, len(queue_list), 5):
            embed = discord.Embed(title="🎶 Current Playlist", color=0x3498db)
            for j, track in enumerate(queue_list[i:i+5], start=i+1):
                embed.add_field(
                    name=f"{j}. {track.title}", 
                    value=f"Duration: {self.format_duration(track.duration)} | Requested by: {track.requester.mention}", 
                    inline=False
                )
            queue_pages.append(embed)

        paginator = pages.Paginator(pages=queue_pages)
        await paginator.send(ctx)

    @commands.hybrid_command(name="skip")
    async def skip(self, ctx: commands.Context):
        if not ctx.voice_client or not self.is_playing:
            return await ctx.send(embed=discord.Embed(
                title="Skip Failed", 
                description="No track is currently playing.", 
                color=0xe74c3c
            ))

        skipped_track = self.current_track
        ctx.voice_client.stop()

        await ctx.send(embed=discord.Embed(
            title="Track Skipped", 
            description=f"Skipped **{skipped_track.title}**", 
            color=0xf39c12
        ))

        if self.queue.get_queue():
            next_track = self.queue.next()
            await self._play_track(ctx, next_track)

    @commands.hybrid_command(name="loop")
    async def toggle_loop(self, ctx: commands.Context):
        self.is_loop = not self.is_loop
        
        await ctx.send(embed=discord.Embed(
            title="Loop Status", 
            description=f"Looping is now {'enabled' if self.is_loop else 'disabled'}.", 
            color=0x2ecc71
        ))
    
    @commands.hybrid_command(name="pause")
    async def pause(self, ctx: commands.Context):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send(embed=discord.Embed(
                title="Playback Paused",
                description=f"**{self.current_track.title}** paused",
                color=0xf39c12
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="Pause Failed",
                description="No track currently playing",
                color=0xe74c3c
            ))

    @commands.hybrid_command(name="resume")
    async def resume(self, ctx: commands.Context):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send(embed=discord.Embed(
                title="Playback Resumed",
                description=f"**{self.current_track.title}** resumed",
                color=0x2ecc71
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="Resume Failed",
                description="Player is not paused",
                color=0xe74c3c
            ))

    @commands.hybrid_command(name="volume")
    async def set_volume(self, ctx: commands.Context, volume: int):
        if 0 <= volume <= 200:
            self.volume = volume / 100
            
            if ctx.voice_client and ctx.voice_client.source and isinstance(ctx.voice_client.source, discord.PCMVolumeTransformer):
                ctx.voice_client.source.volume = self.volume
                
                await ctx.send(embed=discord.Embed(
                    title="Volume Changed",
                    description=f"Volume set to {volume}%",
                    color=0x3498db
                ))
            else:
                await ctx.send(embed=discord.Embed(
                    title="Volume Changed",
                    description=f"Volume set to {volume}% (will apply to next track)",
                    color=0x3498db
                ))
        else:
            await ctx.send(embed=discord.Embed(
                title="Invalid Volume",
                description="Volume must be between 0 and 200",
                color=0xe74c3c
            ))

    @commands.hybrid_command(name="shuffle")
    async def shuffle_queue(self, ctx: commands.Context):
        if len(self.queue) > 1:
            self.queue.shuffle()
            await ctx.send(embed=discord.Embed(
                title="Queue Shuffled",
                description="Playlist order randomized",
                color=0x2ecc71
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="Shuffle Failed",
                description="Need at least 2 tracks in queue to shuffle",
                color=0xe74c3c
            ))

    @commands.hybrid_command(name="nowplaying", aliases=["np"])
    async def now_playing(self, ctx: commands.Context):
        if self.current_track:
            embed = discord.Embed(
                title="🎶 Now Playing",
                description=f"**{self.current_track.title}**\n"
                            f"Artist: {self.current_track.artist or 'Unknown'}\n"
                            f"Duration: {self.format_duration(self.current_track.duration)}\n"
                            f"Requested by: {self.current_track.requester.mention}",
                color=0x2ecc71
            )
            embed.set_thumbnail(url=self.current_track.thumbnail)
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=discord.Embed(
                title="Now Playing",
                description="No track currently playing",
                color=0xf39c12
            ))

    @commands.hybrid_command(name="remove")
    async def remove_track(self, ctx: commands.Context, position: int):
        if 1 <= position <= len(self.queue):
            removed = self.queue._queue.pop(position-1)
            await ctx.send(embed=discord.Embed(
                title="Track Removed",
                description=f"Removed **{removed.title}** from position {position}",
                color=0x2ecc71
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="Invalid Position",
                description="Please provide a valid queue position",
                color=0xe74c3c
            ))

    @commands.hybrid_command(name="clear")
    async def clear_queue(self, ctx: commands.Context):
        self.queue.clear()
        await ctx.send(embed=discord.Embed(
            title="Queue Cleared",
            description="All tracks removed from playlist",
            color=0x2ecc71
        ))

    @commands.hybrid_command(name="history")
    async def show_history(self, ctx: commands.Context):
        if not self.queue._history:
            return await ctx.send(embed=discord.Embed(
                title="Play History",
                description="No tracks in history",
                color=0xf39c12
            ))

        history_pages = []
        for i in range(0, len(self.queue._history), 5):
            embed = discord.Embed(title="⏪ Play History", color=0x3498db)
            for j, track in enumerate(self.queue._history[i:i+5], start=i+1):
                embed.add_field(
                    name=f"{j}. {track.title}",
                    value=f"Duration: {self.format_duration(track.duration)} | Requested by: {track.requester.mention}",
                    inline=False
                )
            history_pages.append(embed)

        paginator = pages.Paginator(pages=history_pages)
        await paginator.send(ctx)

    @play.before_invoke
    async def ensure_voice(self, ctx: commands.Context):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send(embed=discord.Embed(
                    title="Voice Channel Required",
                    description="You need to be in a voice channel to use this command",
                    color=0xe74c3c
                ))
                raise commands.CommandError("Author not connected to voice channel")
        elif ctx.voice_client.is_playing() and ctx.voice_client.channel != ctx.author.voice.channel:
            await ctx.send(embed=discord.Embed(
                title="Channel Mismatch",
                description="You need to be in the same voice channel as the bot",
                color=0xe74c3c
            ))
            raise commands.CommandError("Bot and author in different voice channels")
        
    @commands.hybrid_command(name="stop")
    async def stop(self, ctx: commands.Context):
        if ctx.voice_client:
            ctx.voice_client.stop()
            self.queue.clear()
            self.current_track = None
            self.is_playing = False
            await ctx.voice_client.disconnect()
        
            await ctx.send(embed=discord.Embed(
                title="Playback Stopped", 
                description="Music session has been terminated.", 
                color=0xf39c12
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="Stop Failed", 
                description="No active music session.", 
                color=0xe74c3c
            ))

async def setup(client):
    await client.add_cog(Music(client))
