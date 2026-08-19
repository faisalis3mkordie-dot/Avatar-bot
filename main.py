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


# --- 3. أزرار التفاعل (تنزيل وحذف) ---
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
    await interaction.response.defer(ephemeral=True)

    file1 = discord.File(
        fp=io.BytesIO(self.avatar_bytes), filename='avatar.png'
    )
    file2 = discord.File(
        fp=io.BytesIO(self.banner_bytes), filename='banner.png'
    )

    await interaction.followup.send(
        content='**صورك الأصلية:**', files=[file1, file2], ephemeral=True
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


# --- 4. دالة رسم قالب البروفايل الزيتي والأنيق (iOS Style) ---
def create_matching_card(avatar_img, banner_img):
  W, H = 900, 500

  banner_w, banner_h = 780, 290
  avatar_size = 230

  banner_crop = ImageOps.fit(
      banner_img, (banner_w, banner_h), Image.Resampling.LANCZOS
  )
  avatar_crop = ImageOps.fit(
      avatar_img, (avatar_size, avatar_size), Image.Resampling.LANCZOS
  )

  # خلفية سوداء زيتية متدرجة فخمة
  bg = Image.new('RGBA', (W, H), (14, 16, 18, 255))

  # خلفية ضبابية تعكس ألوان البانر مع مسحة زيتية
  bg_blur = ImageOps.fit(banner_img, (W, H), Image.Resampling.LANCZOS)
  bg_blur = bg_blur.filter(ImageFilter.GaussianBlur(35))

  # طبقة تعتيم زيتية (Oil Overlay)
  oil_overlay = Image.new('RGBA', (W, H), (10, 15, 20, 210))
  bg_blur.paste(oil_overlay, (0, 0), oil_overlay)
  bg.paste(bg_blur, (0, 0))

  # قناع البانر
  banner_x, banner_y = 60, 45
  banner_mask = Image.new('L', (banner_w, banner_h), 0)
  draw_bm = ImageDraw.Draw(banner_mask)
  draw_bm.rounded_rectangle((0, 0, banner_w, banner_h), radius=40, fill=255)

  bg.paste(banner_crop, (banner_x, banner_y), banner_mask)

  # رسم الإطار الزجاجي (iOS Border)
  draw_bg = ImageDraw.Draw(bg)
  draw_bg.rounded_rectangle(
      (banner_x - 2, banner_y - 2, banner_x + banner_w + 2, banner_y + banner_h + 2),
      outline=(160, 185, 205, 180),
      width=3,
      radius=40,
  )

  # حساب موقع الأفتار (النصف بالداخل والنصف بالخارج)
  avatar_x = 110
  avatar_y = (banner_y + banner_h) - (avatar_size // 2)

  circle_mask = Image.new('L', (avatar_size, avatar_size), 0)
  draw_cm = ImageDraw.Draw(circle_mask)
  draw_cm.ellipse((0, 0, avatar_size, avatar_size), fill=255)

  bg.paste(avatar_crop, (avatar_x, avatar_y), circle_mask)

  # إطار دائر الأفتار
  draw_bg.ellipse(
      (
          avatar_x - 3,
          avatar_y - 3,
          avatar_x + avatar_size + 3,
          avatar_y + avatar_size + 3,
      ),
      outline=(180, 205, 225, 220),
      width=4,
  )

  return bg


# --- 5. الأمر !merge ---
@bot.command()
async def merge(ctx):
  if len(ctx.message.attachments) < 2:
    await ctx.send(
        '❌ يرجى إرفاق صورتين في نفس الرسالة! (الأولى للأفتار والثانية للبانر)'
    )
    return

  async with aiohttp.ClientSession() as session:
    async with session.get(ctx.message.attachments[0].url) as resp1:
      avatar_data = await resp1.read()
    async with session.get(ctx.message.attachments[1].url) as resp2:
      banner_data = await resp2.read()

  # حذف رسالة المستخدم تلقائياً
  try:
    await ctx.message.delete()
  except Exception:
    pass

  avatar_img = Image.open(io.BytesIO(avatar_data)).convert('RGBA')
  banner_img = Image.open(io.BytesIO(banner_data)).convert('RGBA')

  final_card = create_matching_card(avatar_img, banner_img)

  output_buffer = io.BytesIO()
  final_card.save(output_buffer, format='PNG')
  output_buffer.seek(0)

  view = ProfileButtons(ctx.author.id, avatar_data, banner_data)

  await ctx.send(
      content=f'**From:** {ctx.author.mention}',
      file=discord.File(fp=output_buffer, filename='matching_profile.png'),
      view=view,
  )


bot.run(os.getenv('BOT_TOKEN'))
