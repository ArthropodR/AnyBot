import discord
import yt_dlp as youtube_dl
from discord.ext import commands


class Music(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.loop = False
        self.queue = []
        self.current_info = None

    async def play_next(self, ctx):
        if self.loop and self.current_info:
            self.queue.insert(0, self.current_info)

        if len(self.queue) > 0:
            self.current_info = self.queue.pop(0)
            FFMPEG_OPTIONS = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn'
            }
            source = await discord.FFmpegOpusAudio.from_probe(self.current_info['url'], **FFMPEG_OPTIONS)
            ctx.voice_client.play(source, after=lambda e: self.client.loop.create_task(self.play_next(ctx)))

            embed = discord.Embed(title="Now Playing", description=self.current_info['title'], color=discord.Color.green())
            embed.set_thumbnail(url=self.current_info.get('thumbnail', ''))
            await ctx.send(embed=embed)
        else:
            self.current_info = None

    @commands.hybrid_command(description="Joins the voice channel you're in.")
    async def join(self, ctx):
        if ctx.author.voice is None:
            embed = discord.Embed(title="Error", description="Please join a voice channel first.", color=discord.Color.red())
            await ctx.send(embed=embed)
            return

        voice_channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            try:
                await voice_channel.connect()
                embed = discord.Embed(title="Success", description=f"Successfully joined {voice_channel.name}!", color=discord.Color.teal())
                await ctx.send(embed=embed)
            except discord.Forbidden:
                embed = discord.Embed(title="Error", description="I don't have permission to connect to the voice channel!", color=discord.Color.red())
                await ctx.send(embed=embed)
            except discord.HTTPException as e:
                embed = discord.Embed(title="Error", description=f"An HTTP exception occurred: {str(e)}", color=discord.Color.red())
                await ctx.send(embed=embed)
        else:
            if ctx.voice_client.channel != voice_channel:
                await ctx.voice_client.move_to(voice_channel)
                embed = discord.Embed(title="Moved", description=f"Moved to {voice_channel.name}!", color=discord.Color.green())
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="Already Here", description=f"Already in {voice_channel.name}.", color=discord.Color.blue())
                await ctx.send(embed=embed)

    @commands.hybrid_command(description="Leaves the voice channel.")
    async def leave(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            embed = discord.Embed(title="Disconnecting...", description="Disconnected from the voice channel.", color=discord.Color.dark_red())
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="I'm not connected to a voice channel.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.hybrid_command(description="Plays a song.")
    async def play(self, ctx, *, search: str):
        await ctx.defer()
        if ctx.author.voice is None:
            embed = discord.Embed(title="Error", description="Please join a voice channel first.", color=discord.Color.red())
            await ctx.send(embed=embed)
            return

        voice_channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await voice_channel.connect()

        ctx.voice_client.stop()
        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        YDL_OPTIONS = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'noplaylist': True,
            'default_search': 'ytsearch',
            'quiet': True
        }
        vc = ctx.voice_client

        with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(search, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                url2 = info['url']
                source = await discord.FFmpegOpusAudio.from_probe(url2, **FFMPEG_OPTIONS)
                vc.play(source, after=lambda e: self.client.loop.create_task(self.play_next(ctx)))
                self.current_info = info

                embed = discord.Embed(title=f"Now playing: {info['title']}", color=discord.Color.teal())
                embed.set_thumbnail(url=info.get('thumbnail', ''))
                await ctx.send(embed=embed)
            except Exception as e:
                embed = discord.Embed(title="Error", description=f"An error occurred: {str(e)}", color=discord.Color.red())
                await ctx.send(embed=embed)

    @commands.hybrid_command(description="Adds a song to the queue.")
    async def queue(self, ctx, *, search: str):
        await ctx.defer()
        if ctx.author.voice is None:
            embed = discord.Embed(title="Error", description="Please join a voice channel first.", color=discord.Color.red())
            await ctx.send(embed=embed)
            return

        if ctx.voice_client is None:
            embed = discord.Embed(title="Error", description="I'm not connected to a voice channel. Please use /join first.", color=discord.Color.red())
            await ctx.send(embed=embed)
            return

        YDL_OPTIONS = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'noplaylist': True,
            'default_search': 'ytsearch',
            'quiet': True
        }

        with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(search, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                self.queue.append(info)
                embed = discord.Embed(title="Added to Queue", description=info['title'], color=discord.Color.blue())
                embed.set_thumbnail(url=info.get('thumbnail', ''))
                await ctx.send(embed=embed)
            except Exception as e:
                embed = discord.Embed(title="Error", description=f"An error occurred: {str(e)}", color=discord.Color.red())
                await ctx.send(embed=embed)

    @commands.hybrid_command(description="Pauses the currently playing song.")
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            embed = discord.Embed(title="Pausing....", description="Paused ⏸️", color=discord.Color.dark_blue())
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="Nothing is being currently played. To play music, use /play <song name>", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.hybrid_command(description="Resumes the paused song.")
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            embed = discord.Embed(title="Resuming....", description="Resumed ⏯️", color=discord.Color.blue())
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="Nothing is currently paused.", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.hybrid_command(description="Stops the currently playing song.")
    async def stop(self, ctx):
        if ctx.voice_client:
            ctx.voice_client.stop()
            embed = discord.Embed(title="Stopping....", description="Stopped ⏹️", color=discord.Color.red())
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="Nothing is being played currently. To get started, use /join then /play <song name>", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.hybrid_command(description="Toggles the loop for the currently playing song.")
    async def loop(self, ctx):
        self.loop = not self.loop
        status = "enabled" if self.loop else "disabled"
        embed = discord.Embed(title="Loop Status", description=f"Looping is now {status} 🔁", color=discord.Color.blue())
        await ctx.send(embed=embed)

async def setup(client):
    await client.add_cog(Music(client))