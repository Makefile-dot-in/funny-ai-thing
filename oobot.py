import discord
import json
import os
from discord import MessageType, Webhook
from datetime import datetime, timedelta
import openai
import traceback
import jason
import asyncio
import aiohttp
import re
import pytz

webhook_id = int(os.getenv("WEBHOOK_ID"))
webhook_url = os.getenv("WEBHOOK_URL")
user_id = int(os.getenv("USER_ID"))
channel_id = int(os.getenv("CHANNEL_ID"))
webhook_user = os.getenv("WEBHOOK_USER")
sred_tag = os.getenv("SRED_TAG")

fmt_regex = re.compile(r"(?s)(?:\n|^)(?:\d+ )?(?P<time>\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\d): .+?#\d\d\d\d \(ID: \d+\)(?:: (?P<defcontent>.+?)| replied to (?P<refmsg>\d+) with (?P<replycontent>.+?)| (?P<metacontent>.+?))(?:\s+Embeds:\s+(?P<embeds>.+?))?(?:(?=\n\d{3,}|$))")
url_regex = re.compile(r"https://discord.com/channels/.+?/.+?/(?P<msgref>.+?)/?")
mention_regex = re.compile(r"<@(%d|%d)>" % (webhook_id, channel_id))
mention_subst_dict = {
        str(webhook_id): str(user_id),
        str(user_id): os.getenv("SRED_ID")
}
mention_subst = lambda matchobj: "<@" + mention_subst_dict[matchobj.group(1)] + ">"
 

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True

openai.api_key = os.getenv("OPENAI_API_KEY")

guild = int(os.getenv("GUILD_ID"))
client = discord.Bot(intents=intents)

def text(m):
    if m.author.id == webhook_id:
        user = webhook_user
    elif m.author.id == user_id:
        user = sred_tag
    else:
        user = f"{m.author} (ID: {m.author.id})"
    msgembeds = m.embeds
    rawcontent = mention_regex.sub(mention_subst, m.content)
    match m.type:
        case MessageType.pins_add: msgcontent = f" pinned message {m.reference.message_id}"
        case MessageType.new_member: msgcontent = " joined"
        case MessageType.thread_created: msgcontent = f" created a thread with name {rawcontent}"
        case MessageType.reply: msgcontent = f" replied to {m.reference.message_id} with {rawcontent}"
        case _ if len(embeds := [embed for embed in m.embeds if embed.title == "Reply"]) == 1:
            embed = embeds[0]
            msgembeds.remove(embed)
            refid = url_regex.fullmatch(embed.url)["msgref"]
            msgcontent = f" replied to {refid} with {rawcontent}"

        case _: msgcontent = f": {rawcontent}"

    attachments = "".join(f"\nAttached file: {attachment.filename}" for attachment in m.attachments)
    reactions = "" if not m.reactions else "\nReactions: " \
        + "".join(f"{r.emoji.name if r.is_custom_emoji() else r.emoji}: {r.count}" for r in m.reactions)
    embeds = "" if not m.embeds else "\nEmbeds: " + "".join(f"\n{json.dumps(e.to_dict())}" for e in m.embeds)
    return f"{m.id} {m.created_at.strftime('%Y-%m-%dT%H:%M:%S')}: {user}{msgcontent}{attachments}{reactions}{embeds}"

def stop():
    raise StopIteration

@client.slash_command(guild_ids=[guild])
async def runoober(interaction: discord.Interaction):
    "Run oober bot."

    await interaction.response.send_message("OK", ephemeral=True)
    await runcompletion(interaction.channel, interaction.guild)

@client.event
async def on_message(m: discord.Message):
    if m.author.bot: return
    if client.user.mentioned_in(m) and m.channel.id == channel_id:
        await runcompletion(m.channel, m.guild)

async def runcompletion(channel, guild):
    messages = []
    async for m in channel.history(limit=20):
        if datetime.now(pytz.utc) - m.created_at >= timedelta(hours=7): break
        if m.content == "$STOP": break
        messages.append(text(m))

    prompt = "\n".join(reversed(messages)) + "\n---\n"
    response = openai.Completion.create(model="ada:ft-personal-2022-08-25-20-17-55", prompt=prompt, temperature=0.4, presence_penalty=1, frequency_penalty=0.8, max_tokens=256).choices[0].text

    print(prompt)
    print(response)

    async with aiohttp.ClientSession() as session:
        webhook = Webhook.from_url(webhook_url, session=session)
        start = datetime.now(pytz.utc)
        for m in fmt_regex.finditer(response):
            print(m)
            time = min(datetime.strptime(m["time"], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc), datetime.now(pytz.utc) + timedelta(minutes=2))
            embeds = []
            if m["embeds"]:
                for e in m["embeds"]:
                    try:
                        embeds.append(discord.Embed.from_dict(jason.parse(e)))
                    except Exception:
                        traceback.print_exc()
           
            seconds = (time - datetime.now(pytz.utc)).total_seconds()
            print(seconds)
            seconds = max(0, min(seconds, 10))
            print(seconds)
            await asyncio.sleep(seconds)
            match {key: value for key, value in m.groupdict().items() if value is not None}:
                case {"defcontent": content} | {"metacontent": content}: pass
                case {"refmsg": refmsg, "replycontent": content}:
                    url = f"https://discord.com/channels/{guild.id}/{channel.id}/{refmsg}"
                    embeds.append(discord.Embed(
                        title="Reply", 
                        description=f"Replied to [this message]({url})",
                        url=url
                    ))

                    
            await webhook.send(content, embeds=embeds, allowed_mentions=discord.AllowedMentions.all())

client.run(os.environ["BOT_TOKEN"])
