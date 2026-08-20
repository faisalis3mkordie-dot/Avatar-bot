import io
import os
from threading import Thread
import aiohttp
import discord
from discord.ext import commands
from discord.ui import Button, View
from flask import Flask
from PIL import Image, ImageDraw, ImageFilter, ImageOps

# --- 1. سيرفر Flask للبقاء أونلاين ---
app = Flask('')


@app.route('/')
def home():
  return 'Bot Online'


def run():
  app.run(host='0.0.0.0', port=8080)


Thread(target=run).start()

# --- 2. إعدادات البوت ---
intents = discord.Intents.all()


# --- 3. زر التفاعل الدائم ---
class ProfileButtons(View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      emoji='📥',
      style=discord.ButtonStyle.secondary,
      custom_id='persistent_download_btn_v5',
  )
  async def download_btn(
      self, interaction: discord.Interaction, button: Button
  ):
    await interaction.response.defer(ephemeral=True)

    # جلب الصورتين الأصليتين المرفقتين بالرسالة
    if len(interaction.message.attachments) >= 3:
      files = []
      async with aiohttp.ClientSession() as session:
        # المرفق الثاني والثالث هما الصورتان الأصليتان
        for idx, att in enumerate(interaction.message.attachments[1:3]):
          async with session.get(att.url) as resp:
            data = await resp.read()
            files.append(
                discord.File(
                    fp=io.BytesIO(data), filename=f'original_{idx+1}.png'
                )
            )

      await interaction.followup.send(
          content='**الصور الأصلية:**', files=files, ephemeral=True
      )
    else:
      await interaction.followup.send(
          content='❌ تعذر العثور على الصور.', ephemeral=True
      )


class PersistentBot(commands.Bot):

  def __init__(self):
    super().__init__(command_prefix='!', intents=intents)

  async def setup_hook(self):
    self.add_view(ProfileButtons())


bot = PersistentBot()


# --- 4. دالة الرسم ---
def create_matching_card(avatar_img, banner_img):
  W, H = 850, 480
  banner_w, banner_h = 730, 270
  avatar_size = 220

  bg = ImageOps.fit(banner_img, (W, H), Image.Resampling.LANCZOS)
  dark_overlay = Image.new('RGBA', (W, H), (8, 10, 14, 180))
  bg.paste(dark_overlay, (0, 0), dark_overlay)

  banner_crop = ImageOps.fit(
      banner_img, (banner_w, banner_h), Image.Resampling.LANCZOS
  )
  banner_x, banner_y = 60, 40

  banner_mask = Image.new('L', (banner_w, banner_h), 0)
  draw_bm = ImageDraw.Draw(banner_mask)
  draw_bm.rounded_rectangle((0, 0, banner_w, banner_h), radius=35, fill=255)

  bg.paste(banner_crop, (banner_x, banner_y), banner_mask)

  draw_bg = ImageDraw.Draw(bg)
  draw_bg.rounded_rectangle(
      (banner_x - 2, banner_y - 2, banner_x + banner_w + 2, banner_y + banner_h + 2),
      outline=(120, 145, 175, 220),
      width=3,
      radius=35,
  )

  avatar_crop = ImageOps.fit(
      avatar_img, (avatar_size, avatar_size), Image.Resampling.LANCZOS)
  avatar_x = 110
  avatar_y = (banner_y + banner_h) - (avatar_size // 2)

  circle_mask = Image.new('L', (avatar_size, avatar_size), 0)
  draw_cm = ImageDraw.Draw(circle_mask)
  draw_cm.ellipse((0, 0, avatar_size, avatar_size), fill=255)

  bg.paste(avatar_crop, (avatar_x, avatar_y), circle_mask)

  draw_bg.ellipse(
      (
          avatar_x - 3,
          avatar_y - 3,
          avatar_x + avatar_size + 3,
          avatar_y + avatar_size + 3,
      ),
      outline=(140, 165, 195, 240),
      width=4,
  )

  return bg


# --- 5. استقبال وتجهيز الرسائل ---
@bot.event
async def on_message(message):
  if message.author.bot:
    return

  is_command = message.content.startswith('!merge')
  is_mentioned = bot.user in message.mentions

  if is_command or is_mentioned:
    target_attachments = message.attachments

    if len(target_attachments) < 2:
      async for msg in message.channel.history(limit=5):
        if len(msg.attachments) >= 2:
          target_attachments = msg.attachments
          break

    if len(target_attachments) >= 2:
      async with aiohttp.ClientSession() as session:
        async with session.get(target_attachments[0].url) as resp1:
          avatar_data = await resp1.read()
        async with session.get(target_attachments[1].url) as resp2:
          banner_data = await resp2.read()

      try:
        await message.delete()
      except Exception:
        pass

      avatar_img = Image.open(io.BytesIO(avatar_data)).convert('RGBA')
      banner_img = Image.open(io.BytesIO(banner_data)).convert('RGBA')

      final_card = create_matching_card(avatar_img, banner_img)

      output_buffer = io.BytesIO()
      final_card.save(output_buffer, format='PNG')
      output_buffer.seek(0)

      # إرسال الصورة المصممة ومعها الصورتان الأصلية في نفس الرسالة
      file_main = discord.File(
          fp=output_buffer, filename='matching_profile.png'
      )
      file_orig1 = discord.File(
          fp=io.BytesIO(avatar_data), filename='original_avatar.png'
      )
      file_orig2 = discord.File(
          fp=io.BytesIO(banner_data), filename='original_banner.png'
      )

      await message.channel.send(
          content=f'**From:** {message.author.mention}',
          files=[file_main, file_orig1, file_orig2],
          view=ProfileButtons(),
      )


bot.run(os.getenv('BOT_TOKEN'))
