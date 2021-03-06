#!/usr/bin/env python3

"""
Panopticon by Megumi Sonoda
Copyright 2016, Megumi Sonoda
This file is licensed under the BSD 3-clause License
Upgraded to support discord.py 1.0.0a1540 by PikalaxALT
"""

# Imports from stdlib
import asyncio
import base64
from datetime import datetime, timezone
import time
import os
import re
import signal
import sys

# Imports from dependencies
import discord
from discord.ext import commands

# Import configuration
from config import (
    TOKEN, COMMAND_PREFIX,
    USE_LOCALTIME, LOG_DIR,
    MAX_MESSAGES, AWAY_STATUS
)

print('panopticon starting')

# Import IGNORE_SERVER separately, which was added later and might not exist in
#   config.py for some users. This is to prevent the script from crashing.
IGNORE_SERVERS = []
try:
    from config import IGNORE_SERVERS
except ImportError:
    pass
except:
    raise


# This sanitizes an input string to remove characters that aren't valid
#   in filenames. There are a lot of other bad filenames that can appear,
#   but given the predictable nature of our input in this application,
#   they aren't handled here.
def clean_filename(string):
    return re.sub(r'[/\\:*?"<>|\x00-\x1f]', '', string)


# This builds the relative file path & filename to log to,
#   based on the channel type of the message.
# It is affixed to the log directory set in config.py
def make_filename(message: discord.Message):
    if message.edited_at:
        time = message.edited_at
    else:
        time = message.created_at
    timestamp = time.strftime('%F')
    if isinstance(message.channel, discord.TextChannel):
        return "{}/{}-{}/#{}-{}/{}.log".format(
            LOG_DIR,
            clean_filename(message.guild.name),
            message.guild.id,
            clean_filename(message.channel.name),
            message.channel.id,
            timestamp
        )
    elif isinstance(message.channel, discord.DMChannel):
        return "{}/DM/{}-{}/{}.log".format(
            LOG_DIR,
            clean_filename(message.author.name),
            message.author.id,
            timestamp
        )
    elif isinstance(message.channel, discord.GroupChannel):
        return "{}/DM/{}-{}/{}.log".format(
            LOG_DIR,
            clean_filename(message.channel.name),
            message.channel.id,
            timestamp
        )


# Uses a Message object to build a very pretty string.
# Format:
#   (messageid) [21:30:00] <user#0000> hello world
# Message ID will be base64-encoded since it becomes shorter that way.
# If the message was edited, prefix messageid with E:
#   and use the edited timestamp and not the original.
def make_message(message: discord.Message):
    # Wrap the message ID in brackets, and prefix E: if the message was edited.
    # Also, base64-encode the message ID, because it's shorter.
    #   This uses less space on disk, and is easier to read in console.
    message_id = '[E:' if message.edited_at else '['
    message_id += "{}]".format(base64.b64encode(
        int(message.id).to_bytes(8, byteorder='little')
    ).decode('utf-8'))

    # Get the datetime from the message
    # If necessary, tell the naive datetime object it's in UTC
    #   and convert to localtime
    if message.edited_at:
        time = message.edited_at
    else:
        time = message.created_at
    if USE_LOCALTIME:
        time = time.replace(tzinfo=timezone.utc).astimezone(tz=None)

    # Convert the datetime to a string in [21:30:00] format
    timestamp = time.strftime('[%H:%M:%S]')

    # Get the author's name, in distinct form, and wrap it
    # in IRC-style brackets
    author = "<{}#{}>".format(
        message.author.name,
        message.author.discriminator
    )

    # Get the message content. Use `.clean_content` to
    #   substitute mentions for a nicer format
    content = message.clean_content.replace('\n', '\n(newline) ')

    # If the message has attachments, grab their URLs
    # attachments = '\n(attach) '.join(
    #     [attachment['url'] for attachment in message.attachments]
    # )
    attachments = ''
    if message.attachments:
        for attach in message.attachments:
            attachments += '\n(attach) {0.url}'.format(attach)

    # Use all of this to return as one string
    return("{} {} {} {} {}".format(
        message_id,
        timestamp,
        author,
        content,
        attachments
    ))


# Append to file, creating path if necessary
def write(filename, string):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    exists = os.path.exists(filename)
    with open(filename, 'a', encoding='utf8') as file:
        if not exists:
            dt_object = datetime.now() if USE_LOCALTIME else datetime.utcnow()
            starthour = 11 if time.daylight else 10
            file.write('Session start: {} {}:00\n'.format(dt_object.strftime('%Y-%m-%D'), starthour))
        file.write(string + "\n") 
        #print(string, file=file)


# Create bot object
bot = commands.Bot(COMMAND_PREFIX)


# Message action
def handle_message(message: discord.Message):
    if message.guild and message.guild.id in IGNORE_SERVERS:
        return
    filename = make_filename(message)
    string = make_message(message)
    write(filename, string)


# Register event handlers
# On message send
@bot.listen()
async def on_message(message: discord.Message):
    handle_message(message)


# On message edit
# Note from discord.py documentation:
#   If the message is not found in the Client.messages cache, then these
#   events will not be called. This happens if the message is too old
#   or the bot is participating in high traffic guilds.
# Through testing, messages from before the current bot session also do
#   not fire the event.
@bot.listen()
async def on_message_edit(before: discord.Message, after: discord.Message):
    # handle_message(after)
    pass


@bot.listen()
async def on_raw_message_edit(payload: discord.RawMessageUpdateEvent):
    message = bot._connection._get_message(payload.message_id)
    if message is None:
        channel = bot.get_channel(int(payload.data['channel_id']))
        if channel is None or (channel.guild is not None and channel.guild.id in IGNORE_SERVERS):
            return
        message = await channel.get_message(payload.message_id)
        if message is None:
            return
        handle_message(message)


@bot.listen()
async def on_message_edit(before, after):
    handle_message(after)


# On ready
# Typically, a bot has an always-green/'active'
#   status indicator. This provides the option to change the status when the
#   actual user goes offline or away.
@bot.listen()
async def on_ready():
    await bot.change_presence(status=AWAY_STATUS)


# Run bot
bot.run(TOKEN, max_messages=MAX_MESSAGES)
