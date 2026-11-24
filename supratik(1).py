

import json
import os
from pathlib import Path
from datetime import timedelta, datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands


# server config

WELCOME_CHANNEL_ID = 0
LEAVE_CHANNEL_ID = 0

TICKET_CATEGORY_ID = 0
TICKET_SUPPORT_ROLE_ID = 0

ACTIVITY_LEADERBOARD_LIMIT = 10

DEFAULT_WELCOME_MESSAGE = (
    "Welcome {user} to **{server}**! You are member **#{count}**."
)
DEFAULT_LEAVE_MESSAGE = (
    "{user} has left **{server}**. We now have **{count}** members."
)

# Data files are created in the same directory as this script.
BASE_DIR = Path(__file__).resolve().parent
WARNINGS_FILE = BASE_DIR / "warnings.json"
AFK_FILE = BASE_DIR / "afk_data.json"
ACTIVITY_FILE = BASE_DIR / "activity_data.json"

# =============================================================================
# bot initialization
# =============================================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.messages = True

class CustomBot(commands.Bot):
    async def setup_hook(self):
        # Persistent ticket buttons keep working after bot restarts.
        self.add_view(TicketPanelView())
        self.add_view(TicketCloseView())
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} slash commands.")
        except discord.HTTPException as error:
            print(f"Could not sync slash commands: {error}")


bot = CustomBot(command_prefix="!", intents=intents)


# =============================================================================
# JSON STORAGE HELPERS
# =============================================================================

def load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)
    temporary_path.replace(path)


def load_warnings():
    data = load_json(WARNINGS_FILE, {})
    return data if isinstance(data, dict) else {}


def save_warnings(data):
    save_json(WARNINGS_FILE, data)


def load_afk():
    data = load_json(AFK_FILE, {})
    return data if isinstance(data, dict) else {}


def load_activity():
    data = load_json(ACTIVITY_FILE, {})
    return data if isinstance(data, dict) else {}


def has_permission(interaction: discord.Interaction, permission: str):
    return bool(getattr(interaction.user.guild_permissions, permission, False))


def can_moderate(interaction: discord.Interaction, member=None):
    guild = interaction.guild
    if guild is None:
        return False, "This command can only be used in a server."

    if member is not None:
        if member.id == interaction.user.id:
            return False, "You cannot moderate yourself."
        if member.id == guild.owner_id:
            return False, "You cannot moderate the server owner."
        if member.top_role >= interaction.user.top_role and interaction.user.id != guild.owner_id:
            return False, "Your role is not high enough."
        bot_member = guild.me
        if bot_member is None or member.top_role >= bot_member.top_role:
            return False, "My role is not high enough."
    return True, None


def get_text_channel(guild: discord.Guild, channel_id: int):
    if not channel_id:
        return None
    channel = guild.get_channel(channel_id)
    return channel if isinstance(channel, discord.TextChannel) else None


# =============================================================================
# moderation system
# =============================================================================

@bot.tree.command(name="ban", description="Ban a member")
@app_commands.default_permissions(ban_members=True)
async def ban_command(
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str = "No reason provided"
):
    allowed, error = can_moderate(interaction, user)
    if not allowed:
        return await interaction.response.send_message(error, ephemeral=True)
    if not has_permission(interaction, "ban_members"):
        return await interaction.response.send_message(
            "You need Ban Members permission.", ephemeral=True
        )
    try:
        await user.ban(reason=f"{reason} | Moderator: {interaction.user}")
        await interaction.response.send_message(
            f"🔨 **{user}** has been banned.\nReason: {reason}"
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "I cannot ban this member. Check my role and permissions.",
            ephemeral=True
        )
    except discord.HTTPException:
        await interaction.response.send_message(
            "Discord could not complete the ban.", ephemeral=True
        )


@bot.tree.command(name="kick", description="Kick a member")
@app_commands.default_permissions(kick_members=True)
async def kick_command(
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str = "No reason provided"
):
    allowed, error = can_moderate(interaction, user)
    if not allowed:
        return await interaction.response.send_message(error, ephemeral=True)
    if not has_permission(interaction, "kick_members"):
        return await interaction.response.send_message(
            "You need Kick Members permission.", ephemeral=True
        )
    try:
        await user.kick(reason=f"{reason} | Moderator: {interaction.user}")
        await interaction.response.send_message(
            f"👢 **{user}** has been kicked.\nReason: {reason}"
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "I cannot kick this member. Check my role and permissions.",
            ephemeral=True
        )
    except discord.HTTPException:
        await interaction.response.send_message(
            "Discord could not complete the kick.", ephemeral=True
        )


@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(minutes="Timeout duration in minutes")
async def timeout_command(
    interaction: discord.Interaction,
    user: discord.Member,
    minutes: app_commands.Range[int, 1, 40320],
    reason: str = "No reason provided"
):
    allowed, error = can_moderate(interaction, user)
    if not allowed:
        return await interaction.response.send_message(error, ephemeral=True)
    if not has_permission(interaction, "moderate_members"):
        return await interaction.response.send_message(
            "You need Moderate Members permission.", ephemeral=True
        )
    try:
        await user.timeout(
            timedelta(minutes=minutes),
            reason=f"{reason} | Moderator: {interaction.user}"
        )
        await interaction.response.send_message(
            f"⏳ **{user}** timed out for **{minutes} minutes**.\nReason: {reason}"
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "I cannot timeout this member. Check my role and permissions.",
            ephemeral=True
        )
    except discord.HTTPException:
        await interaction.response.send_message(
            "Discord could not apply the timeout.", ephemeral=True
        )


@bot.tree.command(name="warn", description="Warn a member")
@app_commands.default_permissions(manage_messages=True)
async def warn_command(
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str
):
    allowed, error = can_moderate(interaction, user)
    if not allowed:
        return await interaction.response.send_message(error, ephemeral=True)
    if not has_permission(interaction, "manage_messages"):
        return await interaction.response.send_message(
            "You need Manage Messages permission.", ephemeral=True
        )

    data = load_warnings()
    key = f"{interaction.guild.id}_{user.id}"
    data.setdefault(key, []).append({
        "reason": reason,
        "moderator": interaction.user.id,
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    })
    save_warnings(data)
    await interaction.response.send_message(
        f"⚠️ **{user}** has received a warning!\n"
        f"Reason: {reason}\nTotal warnings: **{len(data[key])}**"
    )


@bot.tree.command(name="warnings", description="Check a member's warnings")
@app_commands.default_permissions(manage_messages=True)
async def warnings_command(
    interaction: discord.Interaction,
    user: discord.Member
):
    if not has_permission(interaction, "manage_messages"):
        return await interaction.response.send_message(
            "You need Manage Messages permission.", ephemeral=True
        )
    data = load_warnings()
    warnings = data.get(f"{interaction.guild.id}_{user.id}", [])
    if not warnings:
        return await interaction.response.send_message(
            f"**{user}** has no warnings.", ephemeral=True
        )

    embed = discord.Embed(
        title=f"Warnings — {user}",
        color=discord.Color.orange()
    )
    for index, warning in enumerate(warnings[-10:], 1):
        embed.add_field(
            name=f"Warning #{index}",
            value=(
                f"Reason: {discord.utils.escape_markdown(str(warning.get('reason', 'Unknown')))}\n"
                f"Moderator ID: {warning.get('moderator', 'Unknown')}\n"
                f"Date: {warning.get('time', 'Unknown')}"
            ),
            inline=False
        )
    embed.set_footer(text=f"Total warnings: {len(warnings)}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="purge", description="Delete multiple messages")
@app_commands.default_permissions(manage_messages=True)
async def purge_command(
    interaction: discord.Interaction,
    amount: app_commands.Range[int, 1, 100]
):
    if not has_permission(interaction, "manage_messages"):
        return await interaction.response.send_message(
            "You need Manage Messages permission.", ephemeral=True
        )
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "Use this command in a text channel.", ephemeral=True
        )
    await interaction.response.defer(ephemeral=True)
    try:
        deleted = await interaction.channel.purge(
            limit=amount,
            reason=f"Purged by {interaction.user}"
        )
        await interaction.followup.send(
            f"🧹 Deleted **{len(deleted)} messages**.", ephemeral=True
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "I need Manage Messages and Read Message History permissions.",
            ephemeral=True
        )


@bot.tree.command(name="lock", description="Lock this channel")
@app_commands.default_permissions(manage_channels=True)
async def lock_command(interaction: discord.Interaction):
    if not has_permission(interaction, "manage_channels"):
        return await interaction.response.send_message(
            "You need Manage Channels permission.", ephemeral=True
        )
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "Use this command in a text channel.", ephemeral=True
        )
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    try:
        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite,
            reason=f"Channel locked by {interaction.user}"
        )
        await interaction.response.send_message("🔒 This channel has been locked.")
    except discord.Forbidden:
        await interaction.response.send_message(
            "I need Manage Channels permission.", ephemeral=True
        )


@bot.tree.command(name="unlock", description="Unlock this channel")
@app_commands.default_permissions(manage_channels=True)
async def unlock_command(interaction: discord.Interaction):
    if not has_permission(interaction, "manage_channels"):
        return await interaction.response.send_message(
            "You need Manage Channels permission.", ephemeral=True
        )
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "Use this command in a text channel.", ephemeral=True
        )
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = None
    try:
        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite,
            reason=f"Channel unlocked by {interaction.user}"
        )
        await interaction.response.send_message("🔓 This channel has been unlocked.")
    except discord.Forbidden:
        await interaction.response.send_message(
            "I need Manage Channels permission.", ephemeral=True
        )


@bot.tree.command(name="slowmode", description="Set channel slowmode")
@app_commands.default_permissions(manage_channels=True)
async def slowmode_command(
    interaction: discord.Interaction,
    seconds: app_commands.Range[int, 0, 21600]
):
    if not has_permission(interaction, "manage_channels"):
        return await interaction.response.send_message(
            "You need Manage Channels permission.", ephemeral=True
        )
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "Use this command in a text channel.", ephemeral=True
        )
    try:
        await interaction.channel.edit(
            slowmode_delay=seconds,
            reason=f"Slowmode changed by {interaction.user}"
        )
        await interaction.response.send_message(
            f"🐢 Slowmode set to **{seconds} seconds**."
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "I need Manage Channels permission.", ephemeral=True
        )


# =============================================================================
# ticket system
# =============================================================================

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.green,
        emoji="🎫",
        custom_id="ticket_system:create"
    )
    async def create_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "Tickets can only be created in a server.", ephemeral=True
            )

        existing = discord.utils.get(
            guild.text_channels,
            topic=f"ticket_owner:{interaction.user.id}"
        )
        if existing:
            return await interaction.response.send_message(
                f"You already have an open ticket: {existing.mention}",
                ephemeral=True
            )

        category = guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID else None
        if category is not None and not isinstance(category, discord.CategoryChannel):
            category = None
        if category is None:
            category = discord.utils.get(guild.categories, name="Tickets")
        if category is None:
            try:
                category = await guild.create_category("Tickets")
            except discord.Forbidden:
                return await interaction.response.send_message(
                    "I need Manage Channels permission to create the ticket category.",
                    ephemeral=True
                )

        bot_member = guild.me
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True
            )
        }
        support_role = guild.get_role(TICKET_SUPPORT_ROLE_ID) if TICKET_SUPPORT_ROLE_ID else None
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        safe_name = "".join(
            char.lower() if char.isalnum() else "-"
            for char in interaction.user.name
        ).strip("-")[:30] or "member"
        channel_name = f"ticket-{safe_name}"
        try:
            channel = await guild.create_text_channel(
                channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"ticket_owner:{interaction.user.id}",
                reason=f"Ticket opened by {interaction.user}"
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "I could not create your ticket. Check my Manage Channels permission.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="Support Ticket",
            description=(
                f"Hello {interaction.user.mention}! Support will be with you soon.\n"
                "Please explain your issue in detail."
            ),
            color=discord.Color.green()
        )
        await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=TicketCloseView()
        )
        await interaction.response.send_message(
            f"Your ticket has been created: {channel.mention}",
            ephemeral=True
        )


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket_system:close"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not channel.topic:
            return await interaction.response.send_message(
                "This does not look like a ticket channel.", ephemeral=True
            )

        owner_text = channel.topic.removeprefix("ticket_owner:")
        is_owner = str(interaction.user.id) == owner_text
        is_staff = (
            interaction.user.guild_permissions.manage_channels
            or (
                TICKET_SUPPORT_ROLE_ID
                and any(role.id == TICKET_SUPPORT_ROLE_ID for role in interaction.user.roles)
            )
        )
        if not (is_owner or is_staff):
            return await interaction.response.send_message(
                "Only the ticket creator or support staff can close this ticket.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Ticket will be deleted in 5 seconds."
        )
        await discord.utils.sleep_until(
            discord.utils.utcnow() + timedelta(seconds=5)
        )
        try:
            await channel.delete(reason=f"Ticket closed by {interaction.user}")
        except discord.Forbidden:
            pass


@bot.tree.command(name="ticket-setup", description="Create the ticket panel in this channel")
@app_commands.default_permissions(manage_channels=True)
async def ticket_setup(interaction: discord.Interaction):
    if not has_permission(interaction, "manage_channels"):
        return await interaction.response.send_message(
            "You need Manage Channels permission.", ephemeral=True
        )
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message(
            "Run this command in a text channel.", ephemeral=True
        )
    embed = discord.Embed(
        title="🎫 Support Tickets",
        description="Click the button below to create a private support ticket.",
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(
        embed=embed,
        view=TicketPanelView()
    )


# =============================================================================
# utility cmds

@bot.tree.command(name="avatar", description="Show a member's avatar")
async def avatar_command(
    interaction: discord.Interaction,
    user: discord.Member = None
):
    target = user or interaction.user
    embed = discord.Embed(
        title=f"{target.display_name}'s Avatar",
        color=discord.Color.blurple()
    )
    embed.set_image(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="info", description="Show information about a member")
async def info_command(
    interaction: discord.Interaction,
    user: discord.Member = None
):
    target = user or interaction.user
    embed = discord.Embed(
        title=f"User Information — {target}",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Username", value=str(target), inline=True)
    embed.add_field(name="User ID", value=str(target.id), inline=True)
    embed.add_field(
        name="Account Created",
        value=discord.utils.format_dt(target.created_at, style="F"),
        inline=False
    )
    if target.joined_at:
        embed.add_field(
            name="Joined Server",
            value=discord.utils.format_dt(target.joined_at, style="F"),
            inline=False
        )
    embed.add_field(
        name="Top Role",
        value=target.top_role.mention if target.top_role else "None",
        inline=True
    )
    embed.add_field(name="Bot Account", value="Yes" if target.bot else "No", inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="serverinfo", description="Show information about this server")
async def serverinfo_command(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        return await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
    embed = discord.Embed(
        title=f"{guild.name} — Server Information",
        color=discord.Color.blurple()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Server ID", value=str(guild.id), inline=True)
    embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
    embed.add_field(name="Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Text Channels", value=str(len(guild.text_channels)), inline=True)
    embed.add_field(name="Voice Channels", value=str(len(guild.voice_channels)), inline=True)
    embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
    embed.add_field(
        name="Created",
        value=discord.utils.format_dt(guild.created_at, style="F"),
        inline=False
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="say", description="Make the bot send a message")
@app_commands.default_permissions(manage_messages=True)
async def say_command(interaction: discord.Interaction, message: str):
    if not has_permission(interaction, "manage_messages"):
        return await interaction.response.send_message(
            "You need Manage Messages permission.", ephemeral=True
        )
    if not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
        return await interaction.response.send_message(
            "Use this command in a text channel.", ephemeral=True
        )
    await interaction.response.send_message("Message sent.", ephemeral=True)
    await interaction.channel.send(
        message,
        allowed_mentions=discord.AllowedMentions.none()
    )


# =============================================================================
# role management


def role_assignment_error(guild: discord.Guild, member: discord.Member, role: discord.Role):
    if role.is_default():
        return "The @everyone role cannot be assigned or removed."
    if role.managed:
        return "That role is managed by an integration and cannot be changed manually."
    if role >= guild.me.top_role:
        return "My highest role must be above the role you want to manage."
    if member.id != guild.owner_id and role >= member.top_role:
        return "The target member's highest role must be below the role being managed."
    return None


@bot.tree.command(name="addrole", description="Add a role to a member")
@app_commands.default_permissions(manage_roles=True)
async def addrole_command(
    interaction: discord.Interaction,
    user: discord.Member,
    role: discord.Role
):
    if not has_permission(interaction, "manage_roles"):
        return await interaction.response.send_message(
            "You need Manage Roles permission.", ephemeral=True
        )
    error = role_assignment_error(interaction.guild, user, role)
    if error:
        return await interaction.response.send_message(error, ephemeral=True)
    try:
        await user.add_roles(role, reason=f"Role added by {interaction.user}")
        await interaction.response.send_message(
            f"✅ Added {role.mention} to {user.mention}."
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "I cannot assign that role. Check my role hierarchy.", ephemeral=True
        )


@bot.tree.command(name="removerole", description="Remove a role from a member")
@app_commands.default_permissions(manage_roles=True)
async def removerole_command(
    interaction: discord.Interaction,
    user: discord.Member,
    role: discord.Role
):
    if not has_permission(interaction, "manage_roles"):
        return await interaction.response.send_message(
            "You need Manage Roles permission.", ephemeral=True
        )
    error = role_assignment_error(interaction.guild, user, role)
    if error:
        return await interaction.response.send_message(error, ephemeral=True)
    try:
        await user.remove_roles(role, reason=f"Role removed by {interaction.user}")
        await interaction.response.send_message(
            f"✅ Removed {role.mention} from {user.mention}."
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "I cannot remove that role. Check my role hierarchy.", ephemeral=True
        )


# =============================================================================
# afk system

@bot.tree.command(name="afk", description="Set your AFK status")
async def afk_command(interaction: discord.Interaction, reason: str = "AFK"):
    data = load_afk()
    data[str(interaction.user.id)] = {
        "reason": reason[:500],
        "since": datetime.now(timezone.utc).isoformat()
    }
    save_json(AFK_FILE, data)
    await interaction.response.send_message(
        f"💤 Your AFK status has been set: **{reason[:500]}**",
        ephemeral=True
    )


# =============================================================================
# activity tracking

@bot.tree.command(name="mostactive", description="Show the most active members by message count")
async def mostactive_command(interaction: discord.Interaction):
    if interaction.guild is None:
        return await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )

    data = load_activity()
    guild_data = data.get(str(interaction.guild.id), {})
    valid_members = []
    for user_id, count in guild_data.items():
        member = interaction.guild.get_member(int(user_id))
        if member is not None and not member.bot:
            valid_members.append((member, int(count)))

    valid_members.sort(key=lambda item: item[1], reverse=True)
    if not valid_members:
        return await interaction.response.send_message(
            "No activity has been recorded yet.", ephemeral=True
        )

    lines = []
    for position, (member, count) in enumerate(
        valid_members[:max(1, ACTIVITY_LEADERBOARD_LIMIT)], 1
    ):
        lines.append(f"**{position}.** {member.mention} — **{count}** messages")

    embed = discord.Embed(
        title="🏆 Most Active Members",
        description="\n".join(lines),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Counts messages sent after activity tracking was enabled.")
    await interaction.response.send_message(embed=embed)


# =============================================================================
# welcome, leave events, afk removal and msg activity

@bot.event
async def on_member_join(member: discord.Member):
    channel = get_text_channel(member.guild, WELCOME_CHANNEL_ID)
    if channel:
        message = DEFAULT_WELCOME_MESSAGE.format(
            user=member.mention,
            server=member.guild.name,
            count=member.guild.member_count or 0
        )
        try:
            await channel.send(
                message,
                allowed_mentions=discord.AllowedMentions(users=True)
            )
        except discord.Forbidden:
            pass


@bot.event
async def on_member_remove(member: discord.Member):
    channel = get_text_channel(member.guild, LEAVE_CHANNEL_ID)
    if channel:
        message = DEFAULT_LEAVE_MESSAGE.format(
            user=discord.utils.escape_markdown(str(member)),
            server=discord.utils.escape_markdown(member.guild.name),
            count=member.guild.member_count or 0
        )
        try:
            await channel.send(message, allowed_mentions=discord.AllowedMentions.none())
        except discord.Forbidden:
            pass


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    # Count non-bot messages per server for the activity leaderboard.
    activity = load_activity()
    guild_key = str(message.guild.id)
    user_key = str(message.author.id)
    activity.setdefault(guild_key, {})
    activity[guild_key][user_key] = int(activity[guild_key].get(user_key, 0)) + 1
    save_json(ACTIVITY_FILE, activity)

    # Remove the author's AFK status when they speak again.
    afk_data = load_afk()
    author_key = str(message.author.id)
    if author_key in afk_data:
        old_status = afk_data.pop(author_key)
        save_json(AFK_FILE, afk_data)
        try:
            await message.channel.send(
                f"Welcome back {message.author.mention}! Your AFK status was removed.",
                delete_after=8,
                allowed_mentions=discord.AllowedMentions(users=True)
            )
        except discord.Forbidden:
            pass

    # Notify users when they mention someone who is AFK.
    mentioned_lines = []
    for mentioned in message.mentions:
        status = afk_data.get(str(mentioned.id))
        if status:
            reason = discord.utils.escape_markdown(str(status.get("reason", "AFK")))
            mentioned_lines.append(f"💤 **{mentioned.display_name}** is AFK: {reason}")

    if mentioned_lines:
        try:
            await message.reply(
                "\n".join(mentioned_lines),
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none()
            )
        except discord.Forbidden:
            pass

    await bot.process_commands(message)


# =============================================================================
# startup

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is ready.")


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN is not set. Set it as an environment variable before running."
        )
    bot.run(token)
