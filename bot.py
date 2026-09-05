import os
import re
import sqlite3
import datetime as dt

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "guild.db")

STATUSES = [
    ("in", "In", "✅"),
    ("maybe", "Maybe", "❔"),
    ("out", "Out", "❌"),
]
STATUS_LABEL = {k: label for k, label, _ in STATUSES}
STATUS_EMOJI = {k: emoji for k, _, emoji in STATUSES}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                message_id INTEGER PRIMARY KEY,
                guild_id   INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                title      TEXT    NOT NULL,
                when_text  TEXT    NOT NULL,
                when_ts    INTEGER,
                notes      TEXT,
                created_by INTEGER NOT NULL,
                created_at TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rsvps (
                message_id   INTEGER NOT NULL,
                user_id      INTEGER NOT NULL,
                display_name TEXT    NOT NULL,
                status       TEXT    NOT NULL,
                updated_at   TEXT    NOT NULL,
                PRIMARY KEY (message_id, user_id)
            );
            """
        )


def parse_when(text):
    """Turn 'YYYY-MM-DD HH:MM' into a unix timestamp in the machine's timezone.

    Anything else returns None and gets shown exactly as typed.
    """
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})[ T](\d{1,2}):(\d{2})", text.strip())
    if not m:
        return None
    year, month, day, hour, minute = (int(g) for g in m.groups())
    try:
        local = dt.datetime(year, month, day, hour, minute).astimezone()
    except ValueError:
        return None
    return int(local.timestamp())


def get_event(message_id):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM events WHERE message_id = ?", (message_id,)
        ).fetchone()


def set_rsvp(message_id, user_id, display_name, status):
    with db() as conn:
        conn.execute(
            """
            INSERT INTO rsvps (message_id, user_id, display_name, status, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(message_id, user_id) DO UPDATE SET
                display_name = excluded.display_name,
                status       = excluded.status,
                updated_at   = excluded.updated_at
            """,
            (message_id, user_id, display_name, status, dt.datetime.now().isoformat()),
        )


def clear_rsvp(message_id, user_id):
    with db() as conn:
        conn.execute(
            "DELETE FROM rsvps WHERE message_id = ? AND user_id = ?",
            (message_id, user_id),
        )


def get_rsvps(message_id):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM rsvps WHERE message_id = ? ORDER BY updated_at", (message_id,)
        ).fetchall()
    grouped = {key: [] for key, _, _ in STATUSES}
    for row in rows:
        grouped.setdefault(row["status"], []).append(row["display_name"])
    return grouped


def build_embed(event, grouped):
    if event["when_ts"]:
        when = "<t:%d:F>\n<t:%d:R>" % (event["when_ts"], event["when_ts"])
    else:
        when = event["when_text"]

    embed = discord.Embed(title=event["title"], colour=0x5865F2)
    embed.add_field(name="When", value=when, inline=False)
    if event["notes"]:
        embed.add_field(name="Notes", value=event["notes"], inline=False)

    for key, label, emoji in STATUSES:
        names = grouped.get(key, [])
        value = "\n".join(names) if names else "—"
        if len(value) > 1000:
            value = value[:1000].rsplit("\n", 1)[0] + "\n…"
        embed.add_field(name="%s %s (%d)" % (emoji, label, len(names)), value=value, inline=True)

    embed.set_footer(text="Click a button to sign up. Click it again to remove yourself.")
    return embed


async def refresh(message):
    event = get_event(message.id)
    if event is None:
        return
    await message.edit(embed=build_embed(event, get_rsvps(message.id)), view=RSVPView())


class RSVPButton(discord.ui.Button):
    def __init__(self, key, label, emoji):
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            custom_id="rsvp:%s" % key,
        )
        self.key = key

    async def callback(self, interaction):
        message_id = interaction.message.id
        if get_event(message_id) is None:
            await interaction.response.send_message(
                "I don't have a record of this event any more.", ephemeral=True
            )
            return

        user = interaction.user
        current = None
        with db() as conn:
            row = conn.execute(
                "SELECT status FROM rsvps WHERE message_id = ? AND user_id = ?",
                (message_id, user.id),
            ).fetchone()
            if row:
                current = row["status"]

        if current == self.key:
            clear_rsvp(message_id, user.id)
            note = "Taken you off the list."
        else:
            set_rsvp(message_id, user.id, user.display_name, self.key)
            note = "You're down as **%s**." % STATUS_LABEL[self.key]

        await interaction.response.edit_message(
            embed=build_embed(get_event(message_id), get_rsvps(message_id)),
            view=RSVPView(),
        )
        await interaction.followup.send(note, ephemeral=True)


class RSVPView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for key, label, emoji in STATUSES:
            self.add_item(RSVPButton(key, label, emoji))


class GuildBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Registered so the buttons keep working after the bot restarts.
        self.add_view(RSVPView())

        if TEST_GUILD_ID:
            guild = discord.Object(id=int(TEST_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self):
        print("Signed in as %s (%s)" % (self.user, self.user.id))


bot = GuildBot()


@bot.tree.command(name="event", description="Post an event sign-up sheet")
@app_commands.describe(
    title="What the event is, e.g. Raid night",
    when="When it is. Use YYYY-MM-DD HH:MM for a live countdown, or type it freely.",
    notes="Anything else people need to know (optional)",
)
async def event_command(interaction: discord.Interaction, title: str, when: str, notes: str = None):
    if interaction.guild is None:
        await interaction.response.send_message(
            "Run this in a server, not a DM.", ephemeral=True
        )
        return

    when_ts = parse_when(when)
    placeholder = {
        "title": title,
        "when_text": when,
        "when_ts": when_ts,
        "notes": notes,
    }

    await interaction.response.send_message(
        embed=build_embed(placeholder, {}), view=RSVPView()
    )
    message = await interaction.original_response()

    with db() as conn:
        conn.execute(
            """
            INSERT INTO events
                (message_id, guild_id, channel_id, title, when_text, when_ts, notes,
                 created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.id,
                interaction.guild.id,
                interaction.channel_id,
                title,
                when,
                when_ts,
                notes,
                interaction.user.id,
                dt.datetime.now().isoformat(),
            ),
        )


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit(
            "No DISCORD_TOKEN found. Copy .env.example to .env and put your bot token in it."
        )
    init_db()
    bot.run(TOKEN)
