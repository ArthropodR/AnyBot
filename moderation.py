import datetime
import discord
from discord.ext import commands
from discord.ext.commands import has_permissions, HybridCommand

class ModCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.senior_moderator_role_id = 1345486289021178007
        self.junior_moderator_role_id = 1345486289021178007
    
    def get_role_mentions(self):
        senior_moderator_role = f"<@&{self.senior_moderator_role_id}>"
        junior_moderator_role = f"<@&{self.junior_moderator_role_id}>"
        return senior_moderator_role, junior_moderator_role

    @commands.hybrid_command(description="Kicks a member from the server.")
    @has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
        senior_moderator_role, junior_moderator_role = self.get_role_mentions()

        em = discord.Embed(title=f'{member.name} was kicked',
                           description="Reason: " + reason,
                           colour=discord.Colour.red())
        embed = discord.Embed(
            title=f'You were kicked from {ctx.guild.name}',
            description="Reason: " + reason,
            colour=discord.Colour.red())
        try:
            await member.kick(reason=reason)
            log_embed = discord.Embed(title=f"New Case | Kick | {member}",
                                      colour=discord.Colour.red())

            log_embed.add_field(name='Member', value=f'{member.mention}')
            log_embed.add_field(name="Moderator", value=f'{ctx.author}')
            log_embed.add_field(name="Reason", value=f'{reason}')
            mod_channel = self.bot.get_channel(1335611137764626537)
            if mod_channel:
                await mod_channel.send(f"{senior_moderator_role} {junior_moderator_role}", embed=log_embed)
            await ctx.send(embed=em)
        except discord.Forbidden:
            await ctx.send(":x: You can't kick an administrator or I lack the necessary permissions.")
        except Exception as e:
            await ctx.send(":x: An error occurred while trying to kick the member.")
            print(e)

        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("The member's DMs are off so I couldn't DM them.")
        except Exception as e:
            await ctx.send("An error occurred while sending the DM.")
            print(e)

    @commands.hybrid_command(description="Warns a member and gives them the 'Warned' role.")
    @has_permissions(ban_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
        senior_moderator_role, junior_moderator_role = self.get_role_mentions()

        mod_channel = self.bot.get_channel(1335611137764626537)
        em = discord.Embed(title=f'{member.name} was warned',
                           description="Reason: " + reason,
                           colour=discord.Colour.orange())

        try:
            warned = discord.utils.get(ctx.guild.roles, name="Warned")
            guild = ctx.guild
            if not warned:
                warned = await guild.create_role(name="Warned")

            await member.add_roles(warned)
            log_embed = discord.Embed(title=f"New Case | Warn | {member}",
                                      colour=discord.Colour.orange())

            log_embed.add_field(name='Member', value=f'{member.mention}')
            log_embed.add_field(name="Moderator", value=f'{ctx.author}')
            log_embed.add_field(name="Reason", value=f'{reason}')

            if mod_channel:
                await mod_channel.send(f"{senior_moderator_role} {junior_moderator_role}", embed=log_embed)
            await ctx.send(embed=em)
        except discord.Forbidden:
            await ctx.send("I don't have permission to add roles.")
        except Exception as e:
            await ctx.send("There was an error.")
            print(e)
            return

        try:
            dm_embed = discord.Embed(title="You were warned",
                                     description="Reason: " + reason,
                                     colour=discord.Colour.orange())
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            await ctx.send("The member's DMs are off so I couldn't DM them.")
        except Exception as e:
            await ctx.send("An error occurred while sending the DM.")
            print(e)

    @commands.hybrid_command(description="Reports a member to the moderators.")
    async def report(self, ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
        senior_moderator_role, junior_moderator_role = self.get_role_mentions()

        em = discord.Embed(
            title=":police_car: A new report has arrived",
            description=f"{ctx.author.mention} reported {member.mention} for " + reason,
            colour=discord.Colour.orange())
        channel = self.bot.get_channel(1335611137764626537)
        await ctx.send(f"{ctx.author.mention} Thanks for reporting, a staff member will look into it soon.")
        if channel:
            await channel.send(f"{senior_moderator_role} {junior_moderator_role}", embed=em)

    @commands.hybrid_command(description="Clears a specified number of messages.")
    @has_permissions(administrator=True)
    async def clear(self, ctx: commands.Context, amount: int = 1):
        try:
            await ctx.channel.purge(limit=amount)
            await ctx.send(f"Cleared {amount} messages.", delete_after=5)
        except discord.Forbidden:
            await ctx.send("I don't have permission to delete messages.")
        except Exception as e:
            await ctx.send(f"Error: {e}")

    @commands.hybrid_command(description="Mutes a member for a specified duration (in seconds).")
    @has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, duration: int, reason: str = "No reason provided"):
        senior_moderator_role, junior_moderator_role = self.get_role_mentions()

        try:
            await member.edit(timed_out_until=discord.utils.utcnow() + datetime.timedelta(seconds=duration))
            em = discord.Embed(title=f'{member.name} Has been muted for {duration} seconds',
                               description="Reason: " + reason,
                               colour=discord.Colour.teal())
            await ctx.send(embed=em)

            log_channel = self.bot.get_channel(1335611137764626537) 
            if log_channel:
                await log_channel.send(f"{senior_moderator_role} {junior_moderator_role}", embed=em)
        except discord.Forbidden:
            await ctx.send("I don't have permission to timeout members.")
        except Exception as e:
            await ctx.send(f"Error: {e}")
            print(e)

    @commands.hybrid_command(description="Unmutes a member.")
    @has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        senior_moderator_role, junior_moderator_role = self.get_role_mentions()

        try:
            await member.edit(timed_out_until=None)
            em = discord.Embed(title=f'{member.name} has been unmuted successfully',
                               colour=discord.Colour.teal())
            await ctx.send(embed=em)

            log_channel = self.bot.get_channel(1335611137764626537)  
            if log_channel:
                await log_channel.send(f"{senior_moderator_role} {junior_moderator_role}", embed=em)
        except discord.Forbidden:
            await ctx.send("I don't have permission to remove timeouts.")
        except Exception as e:
            await ctx.send(f"Error: {e}")
            print(e)

async def setup(bot):
    await bot.add_cog(ModCog(bot))