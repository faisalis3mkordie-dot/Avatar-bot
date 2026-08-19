import io
import os
from threading import Thread
import aiohttp
import discord
from discord.ext import commands
from discord.ui import Button, View
from flask import Flask
from PIL import Image, ImageDraw, ImageFilter, ImageOps

# --- 1. سيرفر Flask للبقاء أونلاين مجاناً في Render ---
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
    # إبلاغ ديسكورد بالبدء لتجهيز الرد الخاص (Ephemeral)
    await interaction.response.defer(ephemeral=True)

    img1 = Image.open(io.BytesIO(self.avatar_bytes)).convert('RGBA')
    img2 = Image.open(io.BytesIO(self.banner_bytes)).convert('RGBA')

    # ضبط الصورتين بمقاس مربع موحد بحواف دائرية (كما في الأصل)
    size = (350, 350)
    img1_cropped = ImageOps.fit(img1, size, Image.Resampling.LANCZOS)
    img2_cropped = ImageOps.fit(img2, size, Image.Resampling.LANCZOS)

    # قناع حواف دائرية للصور الأصلية
    mask = Image.new('L', size, 0)
    draw_m = ImageDraw.Draw(mask)
    draw_m.rounded_rectangle((0, 0, 350, 350), radius=30, fill=255)

    combined = Image.new('RGBA', (730, 350), (0, 0, 0, 0))
    combined.paste(img1_cropped, (0, 0), mask)
    combined.paste(img2_cropped, (380, 0), mask)

    output = io.BytesIO()
    combined.save(output, format='PNG')
    output.seek(0)

    # إرسال الصور الأصلية في رسالة مخفية تظهر لك فقط
    await interaction.followup.send(
        content='**صورك الأصلية:**',
        file=discord.File(fp=output, filename='original_images.png'),
        ephemeral=True,
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


# --- 4. دالة رسم قالب Noir المطابق 100% ---
def create_matching_card(avatar_img, banner_img):
  W, H = 850, 480

  # قص الصور بمقاسات دقيقة
  banner_crop = ImageOps.fit(banner_img, (730, 300), Image.Resampling.LANCZOS)
  avatar_crop = ImageOps.fit(avatar_img, (210, 210), Image.Resampling.LANCZOS)

  # خلفية داكنة ضبابية مأخوذة من صورة البانر
  bg = ImageOps.fit(banner_img, (W, H), Image.Resampling.LANCZOS)
  bg = bg.filter(ImageFilter.GaussianBlur(22))

  # تعتيم ضبابي خلف القالب
  overlay = Image.new('RGBA', (W, H), (10, 12, 16, 175))
  bg.paste(overlay, (0, 0), overlay)

  # قناع البانر المستطيل بحواف منحنية
  banner_mask = Image.new('L', (730, 300), 0)
  draw_bm = ImageDraw.Draw(banner_mask)
  draw_bm.rounded_rectangle((0, 0, 730, 300), radius=35, fill=255)

  # وضع البانر
  bg.paste(banner_crop, (60, 50), banner_mask)

  # رسم الإطار الزجاجي العريض للبانر
  draw_bg = ImageDraw.Draw(bg)
  draw_bg.rounded_rectangle(
      (57, 47, 793, 353), outline=(110, 140, 165, 230), width=4, radius=35
  )

  # قناع الأفتار الدائري
  circle_mask = Image.new('L', (210, 210), 0)
  draw_cm = ImageDraw.Draw(circle_mask)
  draw_cm.ellipse((0, 0, 210, 210), fill=255)

  # وضع دائرة الأفتار متداخلة مع البانر من اليسار
  bg.paste(avatar_crop, (100, 150), circle_mask)

  # إطار أزرق رمادي سميك حول دائرة الأفتار
  draw_bg.ellipse(
      (96, 146, 314, 364), outline=(100, 130, 155, 255), width=6
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
    # 0 = الأفتار | 1 = البانر
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

  view = ProfileButtons(ctx.author.id, avatar_data, banner_data)

  # إرسال الكارت ومعه الأزرار والرمز الزخرفي السفلي
  await ctx.send(
      content=f'**From:** {ctx.author.mention}',
      file=discord.File(fp=output_buffer, filename='matching_profile.png'),
      view=view,
  )
  await ctx.send(content='༻𓏲⏝ Noir ⏝𓏲༺')


bot.run(os.getenv('BOT_TOKEN'))
