"""Clan data and scheduling rules. No Discord/network side effects in this module."""

from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
UTC = dt.UTC
STAT_FIELDS = ("armor", "armor_pen", "potency", "resistance")
STAT_LABELS = ("Armor", "Armor penetration", "Potency", "Resistance")
DEFAULT_BODY = (
    "Are you going? Choose below.\n"
    "If you're going, submit your armor, armor penetration, potency, and resistance."
)
# Monday=0. Invitation is the preceding calendar day at 17:00 Eastern.
DEFAULT_SCHEDULES = (
    ("thursday", "Shadow War", 3),
    ("saturday", "Shadow War", 5),
    ("sunday", "Rite of Exile / Vigil of Blades", 6),
)


def now_ts():
    return int(dt.datetime.now(UTC).timestamp())


def parse_stat(value):
    text = str(value).strip()
    if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)", text):
        raise ValueError("Each stat must be a whole number of zero or higher, e.g. 5000 or 5,000.")
    number = int(text.replace(",", ""))
    if number > 9_223_372_036_854_775_807:
        raise ValueError("That stat is too large to store. Please check the number.")
    return number


def validate_stats(values):
    if len(values) != 4:
        raise ValueError("All four stats are required.")
    return tuple(parse_stat(value) for value in values)


def parse_eastern(value):
    try:
        local = dt.datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=EASTERN)
    except ValueError as exc:
        raise ValueError("Use YYYY-MM-DD HH:MM in Eastern time (24-hour clock).") from exc
    # Reject nonexistent/ambiguous local times rather than silently choosing a DST fold.
    if local.astimezone(UTC).astimezone(EASTERN).replace(tzinfo=None) != local.replace(tzinfo=None):
        raise ValueError("That local time does not exist because daylight saving time changes.")
    if local.replace(fold=0).utcoffset() != local.replace(fold=1).utcoffset():
        raise ValueError(
            "That local time happens twice. Choose a time outside the daylight saving change."
        )
    return int(local.timestamp())


def occurrences(weekday, timestamp, weeks=3):
    """Include current week for catch-up, never send invitations for past events."""
    today = dt.datetime.fromtimestamp(timestamp, EASTERN).date()
    monday = today - dt.timedelta(days=today.weekday())
    for week in range(weeks):
        date = monday + dt.timedelta(days=weekday, weeks=week)
        starts = dt.datetime.combine(date, dt.time(20), EASTERN)
        sends = dt.datetime.combine(date - dt.timedelta(days=1), dt.time(17), EASTERN)
        if int(starts.timestamp()) > timestamp:
            yield int(starts.timestamp()), int(sends.timestamp())


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.db() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS clan_settings (
                    guild_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL,
                    configured_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS clan_managers (
                    guild_id INTEGER NOT NULL, slot TEXT NOT NULL, user_id INTEGER NOT NULL,
                    PRIMARY KEY(guild_id, slot), UNIQUE(guild_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS clan_schedules (
                    id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, key TEXT NOT NULL,
                    title TEXT NOT NULL, weekday INTEGER NOT NULL, body TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0, UNIQUE(guild_id,key)
                );
                CREATE TABLE IF NOT EXISTS clan_targets (
                    schedule_id INTEGER NOT NULL REFERENCES clan_schedules(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL CHECK(kind IN ('role','user')), target_id INTEGER NOT NULL,
                    PRIMARY KEY(schedule_id,kind,target_id)
                );
                CREATE TABLE IF NOT EXISTS clan_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL,
                    schedule_id INTEGER REFERENCES clan_schedules(id), title TEXT NOT NULL,
                    body TEXT NOT NULL, starts_at INTEGER NOT NULL, sends_at INTEGER NOT NULL,
                    state TEXT NOT NULL DEFAULT 'scheduled', snapshotted INTEGER NOT NULL DEFAULT 0,
                    created_by INTEGER NOT NULL, created_at INTEGER NOT NULL,
                    UNIQUE(schedule_id,starts_at)
                );
                CREATE TABLE IF NOT EXISTS clan_recipients (
                    event_id INTEGER NOT NULL REFERENCES clan_events(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL, display_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'awaiting' CHECK(status IN ('awaiting','going','not_going')),
                    armor INTEGER, armor_pen INTEGER, potency INTEGER, resistance INTEGER,
                    updated_at INTEGER, delivery TEXT NOT NULL DEFAULT 'pending',
                    message_id INTEGER, delivery_error TEXT,
                    cancellation TEXT NOT NULL DEFAULT 'pending',
                    PRIMARY KEY(event_id,user_id)
                );
                CREATE TABLE IF NOT EXISTS clan_stats (
                    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                    armor INTEGER NOT NULL, armor_pen INTEGER NOT NULL,
                    potency INTEGER NOT NULL, resistance INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL, PRIMARY KEY(guild_id,user_id)
                );
                CREATE TABLE IF NOT EXISTS clan_audit (
                    id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL,
                    event_id INTEGER REFERENCES clan_events(id) ON DELETE CASCADE,
                    actor_id INTEGER NOT NULL, subject_id INTEGER, action TEXT NOT NULL,
                    detail TEXT NOT NULL, created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS clan_reports (
                    event_id INTEGER NOT NULL REFERENCES clan_events(id) ON DELETE CASCADE,
                    page INTEGER NOT NULL, message_id INTEGER NOT NULL,
                    PRIMARY KEY(event_id,page)
                );
                CREATE TABLE IF NOT EXISTS clan_dirty (
                    event_id INTEGER PRIMARY KEY REFERENCES clan_events(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS clan_announcement_deliveries (
                    batch TEXT NOT NULL, user_id INTEGER NOT NULL, state TEXT NOT NULL,
                    PRIMARY KEY(batch,user_id)
                );
                CREATE TABLE IF NOT EXISTS clan_members (
                    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, game_name TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1, updated_at INTEGER NOT NULL,
                    PRIMARY KEY(guild_id,user_id)
                );
                CREATE TABLE IF NOT EXISTS clan_onboarding (
                    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, join_key TEXT NOT NULL,
                    nonce TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'awaiting',
                    delivery TEXT NOT NULL DEFAULT 'pending', message_id INTEGER, error TEXT,
                    updated_at INTEGER NOT NULL, PRIMARY KEY(guild_id,user_id)
                );
                CREATE TABLE IF NOT EXISTS clan_features (
                    guild_id INTEGER PRIMARY KEY, onboarding_since INTEGER NOT NULL
                );
            """)
            # An in-flight external send cannot safely be retried after an abrupt crash.
            conn.execute(
                "UPDATE clan_onboarding SET delivery='uncertain',error='Restart during welcome delivery' WHERE delivery='sending'"
            )
            conn.execute(
                "UPDATE clan_recipients SET delivery='uncertain', delivery_error="
                "'Restart during send; delivery needs review' WHERE delivery='sending'"
            )
            conn.execute(
                "UPDATE clan_recipients SET cancellation='uncertain' WHERE cancellation='sending'"
            )
            conn.execute(
                "INSERT OR IGNORE INTO clan_dirty SELECT DISTINCT event_id FROM clan_recipients "
                "WHERE delivery='uncertain' OR cancellation='uncertain'"
            )

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def rows(self, sql, args=()):
        with self.db() as conn:
            return [dict(row) for row in conn.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        rows = self.rows(sql, args)
        return rows[0] if rows else None

    def settings(self, guild_id):
        return self.one("SELECT * FROM clan_settings WHERE guild_id=?", (guild_id,))

    def onboarding_since(self, guild_id):
        with self.db() as conn:
            conn.execute("INSERT OR IGNORE INTO clan_features VALUES(?,?)", (guild_id, now_ts()))
            return conn.execute(
                "SELECT onboarding_since FROM clan_features WHERE guild_id=?", (guild_id,)
            ).fetchone()[0]

    def welcome(self, guild_id, user_id):
        return self.one(
            "SELECT * FROM clan_onboarding WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        )

    def prepare_welcome(self, guild_id, user_id, join_key):
        with self.db() as conn:
            old = conn.execute(
                "SELECT * FROM clan_onboarding WHERE guild_id=? AND user_id=?", (guild_id, user_id)
            ).fetchone()
            if old and old["join_key"] == join_key:
                return False
            conn.execute(
                "INSERT INTO clan_onboarding(guild_id,user_id,join_key,nonce,updated_at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(guild_id,user_id) DO UPDATE SET join_key=excluded.join_key,nonce=excluded.nonce,"
                "state='awaiting',delivery='pending',message_id=NULL,error=NULL,updated_at=excluded.updated_at",
                (guild_id, user_id, join_key, uuid.uuid4().hex[:12], now_ts()),
            )
            conn.execute(
                "UPDATE clan_members SET active=0 WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            )
            return True

    def welcome_delivery(self, guild_id, user_id, nonce, state, message_id=None, error=None):
        with self.db() as conn:
            conn.execute(
                "UPDATE clan_onboarding SET delivery=?,message_id=?,error=? WHERE guild_id=? AND user_id=? AND nonce=?",
                (state, message_id, error, guild_id, user_id, nonce),
            )

    def register_member(self, guild_id, user_id, nonce, game_name):
        name = game_name.strip()
        if (
            not 1 <= len(name) <= 32
            or any(ord(c) < 32 for c in name)
            or any(c in name for c in "@<>")
        ):
            raise ValueError(
                "Enter an in-game name of 1–32 characters, without line breaks or mentions."
            )
        with self.db() as conn:
            row = conn.execute(
                "SELECT nonce,state FROM clan_onboarding WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            ).fetchone()
            if not row or row["nonce"] != nonce or row["state"] == "left":
                raise ValueError("This welcome form is outdated. Use /join-buddys in the server.")
            conn.execute(
                "INSERT INTO clan_members VALUES(?,?,?,1,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET "
                "game_name=excluded.game_name,active=1,updated_at=excluded.updated_at",
                (guild_id, user_id, name, now_ts()),
            )
            conn.execute(
                "UPDATE clan_onboarding SET state='registered',updated_at=? WHERE guild_id=? AND user_id=?",
                (now_ts(), guild_id, user_id),
            )

    def decline_membership(self, guild_id, user_id, nonce):
        with self.db() as conn:
            result = conn.execute(
                "UPDATE clan_onboarding SET state='not_member',updated_at=? WHERE guild_id=? AND user_id=? AND nonce=?",
                (now_ts(), guild_id, user_id, nonce),
            )
            if not result.rowcount:
                raise ValueError(
                    "This welcome message is outdated. Use /join-buddys in the server."
                )
            conn.execute(
                "UPDATE clan_members SET active=0,updated_at=? WHERE guild_id=? AND user_id=?",
                (now_ts(), guild_id, user_id),
            )

    def member_left(self, guild_id, user_id):
        with self.db() as conn:
            conn.execute(
                "UPDATE clan_members SET active=0,updated_at=? WHERE guild_id=? AND user_id=?",
                (now_ts(), guild_id, user_id),
            )
            conn.execute(
                "UPDATE clan_onboarding SET state='left',updated_at=? WHERE guild_id=? AND user_id=?",
                (now_ts(), guild_id, user_id),
            )

    def registered_members(self, guild_id):
        return self.rows(
            "SELECT * FROM clan_members WHERE guild_id=? AND active=1 ORDER BY game_name",
            (guild_id,),
        )

    def configure(self, guild_id, channel_id, timestamp):
        with self.db() as conn:
            conn.execute(
                "INSERT INTO clan_settings VALUES(?,?,?) ON CONFLICT(guild_id) "
                "DO UPDATE SET channel_id=excluded.channel_id",
                (guild_id, channel_id, timestamp),
            )
            for key, title, weekday in DEFAULT_SCHEDULES:
                conn.execute(
                    "INSERT OR IGNORE INTO clan_schedules(guild_id,key,title,weekday,body) "
                    "VALUES(?,?,?,?,?)",
                    (guild_id, key, title, weekday, DEFAULT_BODY),
                )

    def managers(self, guild_id):
        return self.rows(
            "SELECT slot,user_id FROM clan_managers WHERE guild_id=? ORDER BY slot",
            (guild_id,),
        )

    def is_manager(self, guild_id, user_id, owner_id):
        return user_id == owner_id or any(m["user_id"] == user_id for m in self.managers(guild_id))

    def set_managers(self, guild_id, actor_id, owner_id, leader, officers):
        if actor_id != owner_id:
            raise PermissionError("Only the configured bot owner can assign managers.")
        people = [owner_id, leader, *officers]
        if len(officers) != 4 or len(set(people)) != 6:
            raise ValueError("Select six different people: you, the leader, and four officers.")
        with self.db() as conn:
            conn.execute("DELETE FROM clan_managers WHERE guild_id=?", (guild_id,))
            conn.executemany(
                "INSERT INTO clan_managers VALUES(?,?,?)",
                [
                    (guild_id, slot, uid)
                    for slot, uid in zip(
                        (
                            "owner",
                            "leader",
                            "officer1",
                            "officer2",
                            "officer3",
                            "officer4",
                        ),
                        people,
                    )
                ],
            )
            self._audit(conn, guild_id, None, actor_id, None, "managers", {"users": people})

    def schedule(self, guild_id, key):
        row = self.one("SELECT * FROM clan_schedules WHERE guild_id=? AND key=?", (guild_id, key))
        if row is None:
            raise ValueError("Run /clan-setup first and choose thursday, saturday, or sunday.")
        return row

    def targets(self, schedule_id):
        return self.rows(
            "SELECT kind,target_id FROM clan_targets WHERE schedule_id=?",
            (schedule_id,),
        )

    def target(self, schedule_id, kind, target_id, remove=False):
        with self.db() as conn:
            if remove:
                conn.execute(
                    "DELETE FROM clan_targets WHERE schedule_id=? AND kind=? AND target_id=?",
                    (schedule_id, kind, target_id),
                )
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO clan_targets VALUES(?,?,?)",
                    (schedule_id, kind, target_id),
                )

    def edit_schedule(self, schedule_id, title, body, enabled, actor_id):
        if not title.strip() or len(title) > 100 or len(body) > 1500:
            raise ValueError(
                "Use a title of 1–100 characters and message text up to 1,500 characters."
            )
        schedule_guild = self.one("SELECT guild_id FROM clan_schedules WHERE id=?", (schedule_id,))
        if (
            enabled
            and not self.targets(schedule_id)
            and not self.registered_members(schedule_guild["guild_id"])
        ):
            raise ValueError(
                "Select recipients or register at least one Buddys member before enabling this schedule."
            )
        with self.db() as conn:
            conn.execute(
                "UPDATE clan_schedules SET title=?,body=?,enabled=? WHERE id=?",
                (title.strip(), body, enabled, schedule_id),
            )
            # Already delivered invitations are a historical record. Only future unsent text follows edits.
            conn.execute(
                "UPDATE clan_events SET title=?,body=? WHERE schedule_id=? "
                "AND snapshotted=0 AND state='scheduled'",
                (title.strip(), body, schedule_id),
            )
            schedule = conn.execute(
                "SELECT * FROM clan_schedules WHERE id=?", (schedule_id,)
            ).fetchone()
            self._audit(
                conn,
                schedule["guild_id"],
                None,
                actor_id,
                None,
                "schedule",
                {
                    "key": schedule["key"],
                    "title": title,
                    "body": body,
                    "enabled": bool(enabled),
                },
            )

    def materialize(self, timestamp):
        for schedule in self.rows("SELECT * FROM clan_schedules WHERE enabled=1"):
            for starts, sends in occurrences(schedule["weekday"], timestamp):
                self.create_event(
                    schedule["guild_id"],
                    schedule["title"],
                    schedule["body"],
                    starts,
                    sends,
                    0,
                    timestamp,
                    schedule["id"],
                )

    def create_event(
        self,
        guild_id,
        title,
        body,
        starts,
        sends,
        actor_id,
        timestamp,
        schedule_id=None,
    ):
        if not title.strip() or len(title) > 100 or len(body) > 1500 or sends >= starts:
            raise ValueError(
                "Check the event title, message length, and invitation time (before start)."
            )
        with self.db() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO clan_events(guild_id,schedule_id,title,body,"
                "starts_at,sends_at,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    guild_id,
                    schedule_id,
                    title,
                    body,
                    starts,
                    sends,
                    actor_id,
                    timestamp,
                ),
            )
            if cursor.rowcount:
                conn.execute("INSERT OR IGNORE INTO clan_dirty VALUES(?)", (cursor.lastrowid,))
                return cursor.lastrowid
            return conn.execute(
                "SELECT id FROM clan_events WHERE schedule_id=? AND starts_at=?",
                (schedule_id, starts),
            ).fetchone()[0]

    def event(self, event_id, guild_id=None):
        row = self.one("SELECT * FROM clan_events WHERE id=?", (event_id,))
        if row is None or (guild_id is not None and row["guild_id"] != guild_id):
            raise ValueError("Event not found in this server.")
        return row

    def snapshot(self, event_id, people):
        with self.db() as conn:
            row = conn.execute(
                "SELECT snapshotted FROM clan_events WHERE id=?", (event_id,)
            ).fetchone()
            if row["snapshotted"]:
                return
            conn.executemany(
                "INSERT OR IGNORE INTO clan_recipients(event_id,user_id,display_name) "
                "VALUES(?,?,?)",
                [(event_id, uid, name) for uid, name in people.items()],
            )
            conn.execute("UPDATE clan_events SET snapshotted=1 WHERE id=?", (event_id,))
            conn.execute("INSERT OR IGNORE INTO clan_dirty VALUES(?)", (event_id,))

    def recipient(self, event_id, user_id):
        return self.one(
            "SELECT * FROM clan_recipients WHERE event_id=? AND user_id=?",
            (event_id, user_id),
        )

    def recipients(self, event_id):
        return self.rows(
            "SELECT * FROM clan_recipients WHERE event_id=? ORDER BY status,display_name,user_id",
            (event_id,),
        )

    def last_stats(self, guild_id, user_id):
        row = self.one(
            "SELECT * FROM clan_stats WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        )
        return tuple(row[key] for key in STAT_FIELDS) if row else ("", "", "", "")

    @staticmethod
    def _audit(conn, guild_id, event_id, actor_id, subject_id, action, detail):
        conn.execute(
            "INSERT INTO clan_audit(guild_id,event_id,actor_id,subject_id,action,detail,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                guild_id,
                event_id,
                actor_id,
                subject_id,
                action,
                json.dumps(detail),
                now_ts(),
            ),
        )

    def respond(self, event_id, user_id, status, values, timestamp, actor_id=None):
        if status not in ("going", "not_going"):
            raise ValueError("Choose Going or Not going.")
        stats = validate_stats(values) if status == "going" else (None,) * 4
        with self.db() as conn:
            event = conn.execute("SELECT * FROM clan_events WHERE id=?", (event_id,)).fetchone()
            if event is None or event["state"] == "cancelled" or timestamp >= event["starts_at"]:
                raise ValueError("This event is closed or cancelled.")
            before = conn.execute(
                "SELECT * FROM clan_recipients WHERE event_id=? AND user_id=?",
                (event_id, user_id),
            ).fetchone()
            if before is None:
                raise PermissionError("You are not on this event's recipient list.")
            conn.execute(
                "UPDATE clan_recipients SET status=?,armor=?,armor_pen=?,potency=?,resistance=?,"
                "updated_at=? WHERE event_id=? AND user_id=?",
                (status, *stats, timestamp, event_id, user_id),
            )
            if status == "going":
                conn.execute(
                    "INSERT INTO clan_stats VALUES(?,?,?,?,?,?,?) ON CONFLICT(guild_id,user_id) "
                    "DO UPDATE SET armor=excluded.armor,armor_pen=excluded.armor_pen,"
                    "potency=excluded.potency,resistance=excluded.resistance,updated_at=excluded.updated_at",
                    (event["guild_id"], user_id, *stats, timestamp),
                )
            self._audit(
                conn,
                event["guild_id"],
                event_id,
                actor_id or user_id,
                user_id,
                "correction" if actor_id else "response",
                {"before": dict(before), "status": status, "stats": stats},
            )
            conn.execute("INSERT OR IGNORE INTO clan_dirty VALUES(?)", (event_id,))

    def cancel(self, event_id, actor_id):
        with self.db() as conn:
            event = conn.execute("SELECT * FROM clan_events WHERE id=?", (event_id,)).fetchone()
            if event["state"] == "cancelled":
                return
            conn.execute("UPDATE clan_events SET state='cancelled' WHERE id=?", (event_id,))
            self._audit(conn, event["guild_id"], event_id, actor_id, None, "cancelled", {})
            conn.execute("INSERT OR IGNORE INTO clan_dirty VALUES(?)", (event_id,))

    def claim(self, event_id, user_id, cancellation=False):
        field = "cancellation" if cancellation else "delivery"
        with self.db() as conn:
            result = conn.execute(
                f"UPDATE clan_recipients SET {field}='sending' WHERE event_id=? AND user_id=? "
                f"AND {field}='pending'",
                (event_id, user_id),
            )
            return result.rowcount == 1

    def delivery(self, event_id, user_id, state, message_id=None, error=None, cancellation=False):
        with self.db() as conn:
            if cancellation:
                conn.execute(
                    "UPDATE clan_recipients SET cancellation=? WHERE event_id=? AND user_id=?",
                    (state, event_id, user_id),
                )
            else:
                conn.execute(
                    "UPDATE clan_recipients SET delivery=?,message_id=?,delivery_error=? "
                    "WHERE event_id=? AND user_id=?",
                    (state, message_id, error, event_id, user_id),
                )
            conn.execute("INSERT OR IGNORE INTO clan_dirty VALUES(?)", (event_id,))

    def cleanup(self, timestamp):
        with self.db() as conn:
            cutoff = timestamp - 90 * 86400
            conn.execute("DELETE FROM clan_events WHERE starts_at<?", (cutoff,))
            conn.execute(
                "DELETE FROM clan_audit WHERE event_id IS NULL AND created_at<?",
                (cutoff,),
            )


def report_pages(event, recipients, audits, timestamp):
    """Paginate every recipient; never silently truncate the observable roster."""
    counts = {
        status: sum(r["status"] == status for r in recipients)
        for status in ("going", "not_going", "awaiting")
    }
    state = (
        "Cancelled"
        if event["state"] == "cancelled"
        else ("Closed" if timestamp >= event["starts_at"] else "Open")
    )
    header = (
        f"**Event #{event['id']} · {event['title']}** — {state}\n"
        f"<t:{event['starts_at']}:F>\nGoing: {counts['going']} · Not going: {counts['not_going']} · "
        f"Awaiting: {counts['awaiting']} · Total: {len(recipients)}\n"
        "Stats: Armor / Armor penetration / Potency / Resistance\n"
    )
    changes = {row["subject_id"]: row for row in audits if row["action"] == "correction"}
    lines = []
    for row in recipients:
        name = re.sub(r"[\\`*_~|<>@\r\n]", "", row["display_name"])[:80]
        label = {
            "going": "Going",
            "not_going": "Not going",
            "awaiting": "Awaiting response",
        }[row["status"]]
        stats = " / ".join(str(row[k]) for k in STAT_FIELDS) if row["status"] == "going" else "—"
        delivery = row["delivery"]
        issue = f" ({row['delivery_error']})" if row["delivery_error"] else ""
        line = f"{name} <@{row['user_id']}> · **{label}** · {stats} · DM: {delivery}{issue}"
        if event["state"] == "cancelled":
            line += f" · cancellation: {row['cancellation']}"
        if row["user_id"] in changes:
            change = changes[row["user_id"]]
            line += f" · corrected by <@{change['actor_id']}> <t:{change['created_at']}:f>"
        lines.append(line + "\n")
    pages = []
    page = header
    for line in lines or ["No recipients selected yet.\n"]:
        if len(page) + len(line) > 1850:
            pages.append(page)
            page = header
        page += line
    pages.append(page)
    return [f"{page}\nPage {i + 1}/{len(pages)}" for i, page in enumerate(pages)]
