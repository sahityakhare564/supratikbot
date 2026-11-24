- This file includes:
- Moderation: /ban, /kick, /timeout, /warn, /warnings, /purge, /lock,
  /unlock and /slowmode
- Tickets: /ticket-setup plus a Create Ticket button and Close Ticket button
- Utility: /avatar, /info, /serverinfo and /say
- Roles: /addrole and /removerole
- AFK: /afk, automatic AFK status removal when the user sends a message
- Activity: message tracking and /mostactive
- Welcome and leave messages
CONFIGURATION (EDIT THIS SECTION)
All IDs below are numeric Discord IDs, not channel/role names.
To copy an ID, enable Developer Mode in Discord, right-click the item,
and choose Copy ID.

WELCOME_CHANNEL_ID:
    Channel where new-member messages are sent. Use 0 to disable.

LEAVE_CHANNEL_ID:
    Channel where member departure messages are sent. Use 0 to disable.

TICKET_CATEGORY_ID:
    Existing category for ticket channels. Use 0 to let the bot create/find
    a category named "Tickets" when /ticket-setup is run.

TICKET_SUPPORT_ROLE_ID:
    Optional support-team role allowed to view tickets. Use 0 for none.
    The ticket creator, support role, and server staff with Manage Channels
    can view tickets.

ACTIVITY_LEADERBOARD_LIMIT:
    Number of members shown by /mostactive.

DEFAULT_WELCOME_MESSAGE / DEFAULT_LEAVE_MESSAGE:
    Edit the message text here. Available placeholders:
    {user} = member mention, {server} = server name, {count} = member count.

PERMISSIONS TO GIVE THE BOT
---------------------------
View Channels, Send Messages, Read Message History, Embed Links,
Attach Files, Manage Channels, Manage Messages, Kick Members, Ban Members,
Moderate Members, Manage Roles. Its highest role must be above roles it
needs to assign or members it needs to moderate.

DATA FILES
----------
The bot automatically creates these JSON files beside this script:
- warnings.json
- afk_data.json
- activity_data.json

Keep these files if you want the saved data to survive restarts. Back them up
before moving or editing the bot. Do not edit them while the bot is running.

