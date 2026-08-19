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

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or('!'), intents=intents
)


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


# --- 4. دالة رسم قالب البروفايل (الخلفية الممتدة) ---
def create_matching_card(avatar_img, banner_img):
  W, H = 850, 480
  banner_w, banner_h = 730, 270
  avatar_size = 220

  # خلفية ممتدة بالكامل من البانر
  bg = ImageOps.fit(banner_img, (W, H), Image.Resampling.LANCZOS)
  dark_overlay = Image.new('RGBA', (W, H), (8, 10, 14, 180))
  bg.paste(dark_overlay, (0, 0), dark_overlay)

  # البانر الداخلي
  banner_crop = ImageOps.fit(
      banner_img, (banner_w, banner_h), Image.Resampling.LANCZOS
  )
  banner_x, banner_y = 60, 40

  banner_mask = Image.new('L', (banner_w, banner_h), 0)
  draw_bm = ImageDraw.Draw(banner_mask)
  draw_bm.rounded_rectangle((0, 0, banner_w, banner_h), radius=35, fill=255)

  bg.paste(banner_crop, (banner_x, banner_y), banner_mask)

  # إطار البانر
  draw_bg = ImageDraw.Draw(bg)
  draw_bg.rounded_rectangle(
      (banner_x - 2, banner_y - 2, banner_x + banner_w + 2, banner_y + banner_h + 2),
      outline=(120, 145, 175, 220),
      width=3,
      radius=35,
  )

  # الأفتار المتداخل
  avatar_crop = ImageOps.fit(
      avatar_img, (avatar_size, avatar_size), Image.Resampling.LANCZOS
  )
  avatar_x = 110
  avatar_y = (banner_y + banner_h) - (avatar_size // 2)

  circle_mask = Image.new('L', (avatar_size, avatar_size), 0)
  draw_cm = ImageDraw.Draw(circle_mask)
  draw_cm.ellipse((0, 0, avatar_size, avatar_size), fill=255)

  bg.paste(avatar_crop, (avatar_x, avatar_y), circle_mask)

  # إطار الأفتار
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


# --- 5. استقبال الرسائل المعالجة بشكل آمن ---
@bot.event
async def on_message(message):
  # الاستجابة فقط إذا أرسل العضو صوراً وكان المنشن للبوت أو استخدم !merge
  if message.author.bot:
    return

  is_command = message.content.startswith('!merge')
  is_mentioned = bot.user in message.mentions

  if (is_command or is_mentioned) and len(message.attachments) >= 2:
    ctx = await bot.get_context(message)

    async with aiohttp.ClientSession() as session:
      async with session.get(message.attachments[0].url) as resp1:
        avatar_data = await resp1.read()
      async with session.get(message.attachments[1].url) as resp2:
        banner_data = await resp2.read()

    # حذف رسالة المستخدم
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

    view = ProfileButtons(message.author.id, avatar_data, banner_data)

    await message.channel.send(
        content=f'**From:** {message.author.mention}',
        file=discord.File(fp=output_buffer, filename='matching_profile.png'),
        view=view,
    )

  await bot.process_commands(message)


bot.run(os.getenv('BOT_TOKEN'))
