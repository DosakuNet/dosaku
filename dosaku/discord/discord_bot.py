from math import floor
import os
import requests
from typing import List, Optional

import discord
from discord.ext import commands

from dosaku import DosakuBase
from dosaku.utils import ifnone
from dosaku.backend import Server


class DiscordBot(DosakuBase):
    def __init__(
            self,
            host: str = 'http://localhost:8080/',
            description='Dosaku Assistant',
            command_prefixes: Optional[List[str]] = None
    ):
        super().__init__()
        self.backend_server = Server.connection(host)
        self.description = description
        self.command_prefixes = ifnone(command_prefixes, default=['>', 'dosaku '])

        self.intents = discord.Intents.default()
        self.intents.members = True
        self.intents.message_content = True

        self.supported_commands = [
            'list_commands',
            'text_to_image',
            'text_to_speech'
        ]

    def discord_bot(self):
        bot = commands.Bot(
            description=self.description,
            command_prefix=self.command_prefixes,
            intents=self.intents)

        @bot.event
        async def on_ready():
            self.logger.info(f'Logged in as {bot.user} (ID: {bot.user.id}).')

        @bot.event
        async def on_message(message):
            self.logger.debug(f'Received message from user {message.author}.')
            # Make sure we do not reply to ourselves
            if message.author.id == bot.user.id:
                return

            # If the message starts with a command prefix, do the command and return
            if any([message.content.startswith(prefix) for prefix in self.command_prefixes]):
                await bot.process_commands(message)
                return

            # Else if the message is a DM maintain a standard chat convo
            if not message.guild:  # message is a DM
                self.logger.debug(f'Message from {message.author} sent to free DM chat. Message: {message.content}')
                try:
                    response = self.backend_server.chat(text=message.content)
                    max_len = 2000
                    num_chunks = max(floor(len(response.text) // max_len), 1)
                    for idx in range(num_chunks):
                        start = idx * max_len
                        end = (idx + 1) * max_len
                        await message.channel.send(response.text[start:end])
                    if len(response.images) > 0:
                        for image in response.images:
                            filename = os.path.join(self.config['DIR_PATHS']['TEMP'], 'image.png')
                            image.save(filename)
                            with open(filename, 'rb') as image_bytes:
                                discord_image = discord.File(image_bytes)
                                await message.channel.send(file=discord_image)
                            await message.channel.send(file=filename)
                    self.logger.debug(f'Returning DM message from user {message.author}.')
                except discord.errors.Forbidden:
                    pass

            # Else if the message mentions us in some way, add a reply on how to use us.
            elif 'dosaku' in message.content.lower():
                self.logger.debug(f'Message from {message.author} sent to channel chat. Message: {message.content}')
                try:
                    response = (
                        f'Hello! If you\'re trying to chat with me, you can chat with me freely by DMing me. You may '
                        f'also run any of my commands in any channel:\n\n'
                        f'command prefixes: {self.command_prefixes}\n'
                        f'commands: {self.backend_server.commands()}\n\n'
                        f'For example, you may use me to generate an image with:\n'
                        f'>text_to_image An astronaut riding a horse, 4k photograph f/1.4'
                    )
                    await message.reply(response, mention_author=True)
                    self.logger.debug(f'Returning channel message from user {message.author}.')
                except discord.errors.Forbidden as err:
                    self.logger.exception(f'Error raised in processing message from user {message.author}:\n{err}')

        @bot.command()
        async def list_commands(ctx):
            self.logger.debug(f'Received list_commands request from user {ctx.author}.')
            message = 'Sure. I know the following commands, and can chat freely through DMs:\n'
            for command in self.supported_commands:
                message += f'\n\t>{command}'
            message += '\n\nYou may DM me for further help in using my commands.'
            self.logger.debug(f'Returning list_commands request for user {ctx.author}:\n{message}')
            await ctx.send(message)

        @bot.command()
        async def text_to_image(ctx, *, prompt: str):
            self.logger.debug(f'Received text_to_image request from user {ctx.author} with prompt: {prompt}')
            image = self.backend_server.text_to_image(prompt)
            filename = os.path.join(self.config['DIR_PATHS']['TEMP'], 'image.png')
            image.save(filename)
            self.logger.debug(f'Returning text_to_image request for user {ctx.author} with image saved to {filename}.')
            await ctx.send('Sure, how about this?', file=discord.File(filename))

        @bot.command()
        async def text_to_speech(ctx, *, text: Optional[str] = None):
            self.logger.debug(f'Received text_to_speech request from user {ctx.author} with text: {text}')
            filename = os.path.join(self.config['DIR_PATHS']['TEMP'], 'audio.mp3')
            audio = self.backend_server.text_to_speech(text=text)
            audio.write(filename=filename)
            self.logger.debug(f'Returning text_to_speech request for user {ctx.author} with audio save to {filename}.')
            await ctx.send('Sure, here\'s the associated audio:', file=discord.File(filename))

        @bot.command()
        async def transcribe_audio(
                ctx,
                interviewer: Optional[str] = 'Interviewer',
                interviewee: Optional[str] = 'Interviewee'
        ):
            self.logger.debug(f'Received transcribe_audio request from user {ctx.author}.')
            attachment_url = ctx.message.attachments[0].url
            file_request = requests.get(attachment_url)
            filename = os.path.join(self.config['DIR_PATHS']['TEMP'], 'audio.mp3')
            with open(filename, 'wb') as audio_file:
                audio_file.write(file_request.content)

            transcription = self.backend_server.transcribe_interview(
                audio_file=filename,
                interviewer=interviewer,
                interviewee=interviewee
            )
            self.logger.debug(f'Returning transcribe_audio request for user {ctx.author}.')
            await ctx.send(f'{transcription}')

        @bot.command()
        async def set_voice(ctx, voice: str):
            self.logger.debug(f'Received set_voice request from user {ctx.author} to voice {voice}.')
            if voice is None or voice not in self.backend_server.voices():
                await ctx.send(f'I do not know that voice. Please select one of {self.backend_server.voices()}')
            else:
                self.voice = voice
                await ctx.send(f'Certainly, I\'ll use the {voice} voice from now on.')
            self.logger.debug(f'Returning set_voice request for user {ctx.author}.')

        return bot

    def connect_to_discord(self, bot=None):
        self.logger.debug(f'Received request connect_to_discord for {self.name}.')
        if bot is None:
            bot = self.discord_bot()
        bot.run(self.config['API_KEYS']['DISCORD'])
