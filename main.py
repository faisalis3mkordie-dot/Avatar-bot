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


# --- 3. أزرار التحكم المصغرة ---
class ProfileButtons(View):

  def __init__(self, author_id):
    super().__init__(timeout=None)
    self.author_id = author_id

  @discord.ui.button(
      label='📥', style=discord.ButtonStyle.secondary, custom_id='download_btn'
  )
  async def download_btn(
      self, interaction: discord.Interaction, button: Button
  ):
    await interaction.response.send_message(
        'تم التنزيل بنجاح!', ephemeral=True
    )

  @discord.ui.button(
      label='🗑️', style=discord.ButtonStyle.secondary, custom_id='delete_btn'
  )
  async def delete_btn(self, interaction: discord.Interaction, button: Button):
    if interaction.user.id == self.author_id:
      await interaction.message.delete()
    else:
      await interaction.response.send_message(
          '❌ يمكنك حذف تصميمك فقط!', ephemeral=True
      )


# --- 4. دالة رسم قالب البروفايل بالملي ---
def create_matching_card(avatar_img, banner_img):
  # المقاس الكلي للكارت
  W, H = 800, 480

  # تجهيز الصورة الأولى (الأفتار) والتصغير
  avatar_crop = ImageOps.fit(avatar_img, (220, 220), Image.Resampling.LANCZOS)
  banner_crop = ImageOps.fit(banner_img, (580, 210), Image.Resampling.LANCZOS)

  # خلفية ضبابية مموهة من صورة البانر
  bg = ImageOps.fit(banner_img, (W, H), Image.Resampling.LANCZOS)
  bg = bg.filter(ImageFilter.GaussianBlur(15))

  # طبقة سوداء شفافة لتعتيم الخلفية
  overlay = Image.new('RGBA', (W, H), (15, 18, 22, 160))
  bg.paste(overlay, (0, 0), overlay)

  # رسم الإطار الزجاجي الداخلي للبانر بحواف دائرية
  banner_mask = Image.new('L', (580, 210), 0)
  draw_bm = ImageDraw.Draw(banner_mask)
  draw_bm.rounded_rectangle((0, 0, 580, 210), radius=25, fill=255)

  # لصق البانر داخل الكارت
  bg.paste(banner_crop, (170, 70), banner_mask)

  # إطار أزرق رمادي حول البانر
  draw_bg = ImageDraw.Draw(bg)
  draw_bg.rounded_rectangle(
      (168, 68, 752, 282), outline=(100, 130, 160, 255), width=3, radius=25
  )

  # تجهيز الأفتار بشكل دائري
  circle_mask = Image.new('L', (220, 220), 0)
  draw_cm = ImageDraw.Draw(circle_mask)
  draw_cm.ellipse((0, 0, 220, 220), fill=255)

  # لصق الأفتار
  bg.paste(avatar_crop, (80, 120), circle_mask)

  # إطار أزرق رمادي حول الأفتار
  draw_bg.ellipse(
      (77, 117, 303, 343), outline=(100, 130, 160, 255), width=4
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
    # الصورة الأولى 0 = الأفتار
    async with session.get(ctx.message.attachments[0].url) as resp1:
      avatar_data = await resp1.read()
    # الصورة الثانية 1 = البانر
    async with session.get(ctx.message.attachments[1].url) as resp2:
      banner_data = await resp2.read()

  avatar_img = Image.open(io.BytesIO(avatar_data)).convert('RGBA')
  banner_img = Image.open(io.BytesIO(banner_data)).convert('RGBA')

  final_card = create_matching_card(avatar_img, banner_img)

  output_buffer = io.BytesIO()
  final_card.save(output_buffer, format='PNG')
  output_buffer.seek(0)

  view = ProfileButtons(ctx.author.id)

  # إرسال النتيجة مع الخط الفاصل والأزرار
  await ctx.send(
      content=f'**From:** {ctx.author.mention}',
      file=discord.File(fp=output_buffer, filename='matching_profile.png'),
      view=view,
  )
  await ctx.send(content='༻𓏲```python
  await ctx.send(content='༻𓏲```python
  await ctx.send(content='༻𓏲⏝ Noir ⏝𓏲༺')


bot.run(os.getenv('BOT_TOKEN'))
