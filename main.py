import asyncio

import discord
from discord.ext import commands

from moderation import ModCog
from music_cog import Music

class AnyBot(commands.Bot):
    async def setup_hook(self):
        await self.load_cogs()
        await self.tree.sync()

    async def load_cogs(self):
        await self.add_cog(ModCog(self))
        await self.add_cog(Music(self))

intents = discord.Intents.all()
client = AnyBot(command_prefix="!", intents=intents)
client.remove_command("help")

@client.event
async def on_ready():
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="to commands"))
    print(f"Discord Bot is ready,\nLogged in as {client.user},\n(ID: {client.user.id})")

@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(":x: You can't do that.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(":x: Please type all the required arguments.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send(":x: That isn't a command.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send(":x: Member not found.")
    else:
        raise error

@client.hybrid_command()
async def test(ctx):
    await ctx.send("Tested")

async def main():
    async with client:
        await client.start('MTM0NjE1ODg1NzY1MDcwNDQzNA.GUwt6c.Qmt024wNEslfcr3GSAsxo7zDo7oOnsunHtEp3E')

if __name__ == "__main__":
    asyncio.run(main())