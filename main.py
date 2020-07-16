#!/bin/env python3
import discord

import lex_yacc as ly

import os

from asyncio import Lock

class DieBot(discord.Client):
    def __init__(self):
        super().__init__()
        self.lock = Lock()

    async def on_ready(self):
        game = discord.Game("with a lot of dice")
        await bot.change_presence(activity=game)

        print('Logged on as: ', self.user)

    async def on_message(self, message):
        if message.author == self.user:
            return

        if not message.content:
            return

        if message.content == '?ping':
            return await message.channel.send('pong')

        if message.content[0] != '?':
            return

        result = "Error"

        async with self.lock:
            ly.message = message
            ly.message.author.name.replace("/", "#")
            result = ""
            try:
                result = ly.parser.parse(message.content[1:])
            except ly.SyntaxError as e:
                result = e.message

        await message.channel.send(result)

bot = DieBot()

bot.run(os.environ['DISCORD_TOKEN'])
