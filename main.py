import io
import os
from threading import Thread
import aiohttp
import discord
from discord.ext import commands
from discord.ui import Button, View
from flask import Flask
from PIL import Image, ImageDraw, ImageOps

# --- 1. سيرفر Flask للبقاء أونلاين ---
app = Flask('')


@app.route('/')
def home():
  return 'Bot is online!'


def run():
  app.run(host='0.0.0.0', port=8080)


Thread(target=run).start()

# --- 2. إعدادات البوت ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)


# --- 3. أزرار التنزيل والحذف ---
class ProfileButtons(View):

  def __init__(self, author_id):
    super().__init__(timeout=None)
    self.author_id = author_id

  @discord.ui.button(label='تنزيل 📥', style=discord.ButtonStyle.primary)
  async def download_btn(
      self, interaction: discord.Interaction, button: Button
  ):
    await interaction.response.send_message(
        'تم التنزيل بنجاح!', ephemeral=True
    )

  @discord.ui.button(label='🗑️', style=discord.ButtonStyle.danger)
  async def delete_btn(self, interaction: discord.Interaction, button: Button):
    if interaction.user.id == self.author_id:
      await interaction.message.delete()
    else:
      await interaction.response.send_message(
        '❌ يمكنك حذف التصميم الخاص بك فقط!', ephemeral=True
      )


# --- 4. أمر دمج الأفتار مع البانر !merge ---
@bot.command()
async def merge(ctx):
  if len(ctx.message.attachments) < 2:
    await ctx.send('❌ يرجى إرفاق صورتين (الأولى للبانر والثانية للأفتار)!')
    return

  async with aiohttp.ClientSession() as session:
    async with session.get(ctx.message.attachments[0].url) as resp1:
      banner_data = await resp1.read()
    async with session.get(ctx.message.attachments[1].url) as resp2:
      avatar_data = await resp2.read()

  banner_img = Image.open(io.BytesIO(banner_data)).convert('RGBA')
  avatar_img = Image.open(io.BytesIO(avatar_data)).convert('RGBA')

  # إنشاء خلفية تصميم البروفايل (سوداء مع حواف دائرية)
  canvas_w, canvas_h = 600, 350
  base = Image.new('RGBA', (canvas_w, canvas_h), (18, 18, 18, 255))

  # تجهيز البانر وتصغيره
  banner_resized = ImageOps.fit(
      banner_img, (540, 200), Image.Resampling.LANCZOS
  )
  base.paste(banner_resized, (30, 30))

  # تجهيز الأفتار بشكل دائري
  avatar_size = 130
  avatar_resized = ImageOps.fit(
      avatar_img, (avatar_size, avatar_size), Image.Resampling.LANCZOS
  )

  mask = Image.new('L', (avatar_size, avatar_size), 0)
  draw = ImageDraw.Draw(mask)
  draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

  # وضع الأفتار بشكل متداخل فوق البانر
  base.paste(avatar_resized, (60, 160), mask)

  output_buffer = io.BytesIO()
  base.save(output_buffer, format='PNG')
  output_buffer.seek(0)

  view = ProfileButtons(ctx.author.id)
  await ctx.send(
      content=f'**From:** {ctx.author.mention}',
      file=discord.File(fp=output_buffer, filename='profile.png'),
      view=view,
  )


bot.run(os.getenv('BOT_TOKEN'))
