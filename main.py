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
  return 'Bot is online!'


def run():
  app.run(host='0.0.0.0', port=8080)


Thread(target=run).start()

# --- 2. إعدادات البوت ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)


# --- 3. أزرار التفاعل مع حفظ الصور الأصلية ---
class ProfileButtons(View):

  def __init__(self, author_id, avatar_bytes, banner_bytes):
    super().__init__(timeout=None)
    self.author_id = author_id
    self.avatar_bytes = avatar_bytes
    self.banner_bytes = banner_bytes

  @discord.ui.button(
      emoji='📥', style=discord.ButtonStyle.secondary, custom_id='download_btn'
  )
  async def download_btn(
      self, interaction: discord.Interaction, button: Button
  ):
    # إبلاغ ديسكورد بالمعالجة
    await interaction.response.defer(ephemeral=False)

    img1 = Image.open(io.BytesIO(self.avatar_bytes)).convert('RGBA')
    img2 = Image.open(io.BytesIO(self.banner_bytes)).convert('RGBA')

    # توحيد الارتفاع للصور الأصلية لدمجهما جنبًا إلى جنب
    h = min(img1.height, img2.height)
    img1_resized = img1.resize((int(img1.width * h / img1.height), h))
    img2_resized = img2.resize((int(img2.width * h / img2.height), h))

    # دمج الصورتين في صورة واحدة
    combined = Image.new('RGBA', (img1_resized.width + img2_resized.width, h))
    combined.paste(img1_resized, (0, 0))
    combined.paste(img2_resized, (img1_resized.width, 0))

    output = io.BytesIO()
    combined.save(output, format='PNG')
    output.seek(0)

    # إرسال رد كـ Reply بنفس الطريقة الظاهرة في الصورة
    await interaction.followup.send(
        content='**صورك الأصلية:**',
        file=discord.File(fp=output, filename='original_images.png'),
    )

  @discord.ui.button(
      emoji='🗑️', style=discord.ButtonStyle.secondary, custom_id='delete_btn'
  )
  async def delete_btn(self, interaction: discord.Interaction, button: Button):
    if interaction.user.id == self.author_id:
      await interaction.message.delete()
    else:
      await interaction.response.send_message(
          '❌ يمكنك حذف تصميمك فقط!', ephemeral=True
      )


# --- 4. تصميم قالب البروفايل ---
def create_matching_card(avatar_img, banner_img):
  W, H = 800, 420

  banner_crop = ImageOps.fit(banner_img, (600, 220), Image.Resampling.LANCZOS)
  avatar_crop = ImageOps.fit(avatar_img, (160, 160), Image.Resampling.LANCZOS)

  bg = ImageOps.fit(banner_img, (W, H), Image.Resampling.LANCZOS)
  bg = bg.filter(ImageFilter.GaussianBlur(18))

  overlay = Image.new('RGBA', (W, H), (15, 18, 22, 170))
  bg.paste(overlay, (0, 0), overlay)

  banner_mask = Image.new('L', (600, 220), 0)
  draw_bm = ImageDraw.Draw(banner_mask)
  draw_bm.rounded_rectangle((0, 0, 600, 220), radius=20, fill=255)

  bg.paste(banner_crop, (100, 50), banner_mask)

  draw_bg = ImageDraw.Draw(bg)
  draw_bg.rounded_rectangle(
      (98, 48, 702, 272), outline=(100, 130, 160, 255), width=3, radius=20
  )

  circle_mask = Image.new('L', (160, 160), 0)
  draw_cm = ImageDraw.Draw(circle_mask)
  draw_cm.ellipse((0, 0, 160, 160), fill=255)

  bg.paste(avatar_crop, (140, 170), circle_mask)
  draw_bg.ellipse(
      (137, 167, 303, 333), outline=(100, 130, 160, 255), width=4
  )

  return bg


# --- 5. الأمر !merge ---
@bot.command()
async def merge(ctx):
  if len(ctx.message.attachments) < 2:
    await ctx.send(
        '❌ يرجى إرفاق صورتين! (الأولى للأفتار والثانية للبانر)'
    )
    return

  async with aiohttp.ClientSession() as session:
    # الصورة 0 = أفتار | الصورة 1 = بانر
    async with session.get(ctx.message.attachments[0].url) as resp1:
      avatar_data = await resp1.read()
    async with session.get(ctx.message.attachments[1].url) as resp2:
      banner_data = await resp2.read()

  avatar_img = Image.open(io.BytesIO(avatar_data)).convert('RGBA')
  banner_img = Image.open(io.BytesIO(banner_data)).convert('RGBA')

  final_card = create_matching_card(avatar_img, banner_img)

  output_buffer = io.BytesIO()
  final_card.save(output_buffer, format='PNG')
  output_buffer.seek(0)

  # نمرر بيانات الصور الأصلية للأزرار لتنزيلها لاحقاً
  view = ProfileButtons(ctx.author.id, avatar_data, banner_data)

  await ctx.send(
      content=f'**From:** {ctx.author.mention}',
      file=discord.File(fp=output_buffer, filename='profile.png'),
      view=view,
  )


bot.run(os.getenv('BOT_TOKEN'))
