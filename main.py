import io
import os
from threading import Thread
import aiohttp
import discord
from discord.ext import commands
from flask import Flask
from PIL import Image, ImageOps

# --- 1. سيرفر وهمي لتجاوز فحص البورت مجاناً في Render ---
app = Flask('')


@app.route('/')
def home():
  return 'Bot is online!'


def run():
  app.run(host='0.0.0.0', port=8080)


Thread(target=run).start()

# --- 2. إعدادات البوت والـ Intents ---
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
  print(f'Logged in as {bot.user}')


# --- 3. أمر دمج الصورتين !merge ---
@bot.command()
async def merge(ctx):
  if len(ctx.message.attachments) < 2:
    await ctx.send('❌ يرجى إرفاق صورتين في نفس الرسالة مع الأمر!')
    return

  async with aiohttp.ClientSession() as session:
    async with session.get(ctx.message.attachments[0].url) as resp1:
      img1_data = await resp1.read()
    async with session.get(ctx.message.attachments[1].url) as resp2:
      img2_data = await resp2.read()

  img1 = Image.open(io.BytesIO(img1_data)).convert('RGBA')
  img2 = Image.open(io.BytesIO(img2_data)).convert('RGBA')

  # قص وتصغير الصورتين بمقاس مربع موحد (300x300) لتجنب المط والتشويه
  target_size = (300, 300)
  img1 = ImageOps.fit(img1, target_size, Image.Resampling.LANCZOS)
  img2 = ImageOps.fit(img2, target_size, Image.Resampling.LANCZOS)

  # دمج الصورتين جنباً إلى جنب
  new_img = Image.new('RGBA', (600, 300))
  new_img.paste(img1, (0, 0))
  new_img.paste(img2, (300, 0))

  output_buffer = io.BytesIO()
  new_img.save(output_buffer, format='PNG')
  output_buffer.seek(0)

  await ctx.send(
      file=discord.File(fp=output_buffer, filename='merged_avatar.png')
  )


# --- 4. تشغيل البوت ---
bot.run(os.getenv('BOT_TOKEN'))
