import asyncio
import io
import json
import logging
import os
from pathlib import Path
from threading import Thread
from typing import Awaitable, Callable, Sequence

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

# --- 1. سيرفر Flask لتفادي مشكلة Port في Render / Replit ---
app = Flask('')


@app.route('/')
def home():
  return 'Bot is running!'


def run_flask():
  port = int(os.environ.get('PORT', 8080))
  app.run(host='0.0.0.0', port=port)


def keep_alive():
  t = Thread(target=run_flask)
  t.start()


keep_alive()
# ---------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
)
logger = logging.getLogger('merge-bot')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)


def safe_filename(original_name: str, index: int) -> str:
  filename = Path(original_name).name
  if not filename or '.' not in filename:
    return f'original-{index}.png'
  return filename


def read_image(image_bytes: bytes) -> Image.Image:
  with Image.open(io.BytesIO(image_bytes)) as source:
    return ImageOps.exif_transpose(source).convert('RGBA')


def validate_image(image_bytes: bytes) -> None:
  with Image.open(io.BytesIO(image_bytes)) as image:
    image.verify()


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
  mask = Image.new('L', size, 0)
  ImageDraw.Draw(mask).rounded_rectangle(
      (0, 0, size[0] - 1, size[1] - 1),
      radius=radius,
      fill=255,
  )
  return mask


def create_avatar_design(first_bytes: bytes, second_bytes: bytes) -> bytes:
  background_source = read_image(second_bytes)
  portrait_source = read_image(first_bytes)

  canvas_size = (1000, 615)
  background = ImageOps.fit(
      background_source,
      canvas_size,
      method=Image.Resampling.LANCZOS,
      centering=(0.5, 0.5),
  )
  background = ImageEnhance.Brightness(background).enhance(0.48)
  background = ImageEnhance.Contrast(background).enhance(1.05)
  background = background.filter(ImageFilter.GaussianBlur(2.2))

  canvas = background.copy()
  canvas = Image.alpha_composite(
      canvas,
      Image.new('RGBA', canvas_size, (18, 21, 27, 72)),
  )

  panel_position = (48, 72)
  panel_size = (905, 318)
  panel = ImageOps.fit(
      background_source,
      panel_size,
      method=Image.Resampling.LANCZOS,
      centering=(0.5, 0.45),
  )
  panel = ImageEnhance.Contrast(panel).enhance(1.04)
  canvas.paste(
      panel,
      panel_position,
      rounded_mask(panel_size, 50),
  )
  draw = ImageDraw.Draw(canvas)
  panel_box = (
      panel_position[0],
      panel_position[1],
      panel_position[0] + panel_size[0] - 1,
      panel_position[1] + panel_size[1] - 1,
  )
  draw.rounded_rectangle(
      panel_box,
      radius=50,
      outline=(71, 82, 111, 255),
      width=8,
  )

  portrait_size = 310
  portrait = ImageOps.fit(
      portrait_source,
      (portrait_size, portrait_size),
      method=Image.Resampling.LANCZOS,
      centering=(0.5, 0.5),
  )
  portrait_position = (101, 235)
  shadow = Image.new('RGBA', canvas_size, (0, 0, 0, 0))
  shadow_mask = Image.new('L', (portrait_size, portrait_size), 0)
  ImageDraw.Draw(shadow_mask).ellipse(
      (0, 0, portrait_size - 1, portrait_size - 1),
      fill=175,
  )
  shadow.paste(
      (0, 0, 0, 255),
      (portrait_position[0] + 12, portrait_position[1] + 16),
      shadow_mask.filter(ImageFilter.GaussianBlur(12)),
  )
  canvas = Image.alpha_composite(canvas, shadow)

  portrait_mask = Image.new('L', (portrait_size, portrait_size), 0)
  ImageDraw.Draw(portrait_mask).ellipse(
      (0, 0, portrait_size - 1, portrait_size - 1),
      fill=255,
  )
  canvas.paste(portrait, portrait_position, portrait_mask)

  circle_box = (
      portrait_position[0],
      portrait_position[1],
      portrait_position[0] + portrait_size - 1,
      portrait_position[1] + portrait_size - 1,
  )
  draw.ellipse(circle_box, outline=(71, 82, 111, 255), width=8)

  output = io.BytesIO()
  canvas.save(output, format='PNG')
  return output.getvalue()


class DownloadButton(discord.ui.Button):

  def __init__(self, urls: list[str] = None):
    custom_id = 'merge:dl_btn'
    if urls:
      # تخزين الروابط داخل custom_id ليقرأها البوت بعد إعادة التشغيل
      data_str = json.dumps(urls)
      custom_id = f'merge:dl:{data_str}'

    super().__init__(
        label='⤓  تنزيل الصور',
        style=discord.ButtonStyle.secondary,
        custom_id=custom_id[:100],  # حد أقصى للـ custom_id في ديسكورد
    )

  async def callback(self, interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    urls = []
    if self.custom_id.startswith('merge:dl:'):
      try:
        urls = json.loads(self.custom_id[9:])
      except Exception:
        pass

    if not urls and interaction.message and interaction.message.attachments:
      urls = [att.url for att.url in interaction.message.attachments]

    if urls:
      try:
        files_to_send = []
        async with aiohttp.ClientSession() as session:
          for idx, url in enumerate(urls, start=1):
            async with session.get(url) as resp:
              if resp.status == 200:
                data = await resp.read()
                files_to_send.append(
                    discord.File(io.BytesIO(data), filename=f'original-{idx}.png')
                )

        if files_to_send:
          await interaction.user.send(
              '📂 هذه هي الصور الأصلية:', files=files_to_send
          )
          await interaction.followup.send(
              '✅ تم إرسال الصور الأصلية إلى خاصك!', ephemeral=True
          )
        else:
          await interaction.followup.send(
              'تعذر تحميل الصور.', ephemeral=True
          )
      except discord.Forbidden:
        await interaction.followup.send(
            '⚠️ خاصك مقفل! يرجى فتح الرسائل الخاصة.', ephemeral=True
        )
      except Exception as e:
        logger.exception('Error downloading images: %s', e)
        await interaction.followup.send(
            'حدث خطأ أثناء تنزيل الصور.', ephemeral=True
        )
    else:
      await interaction.followup.send('تعذر استرجاع الصور.', ephemeral=True)


class PersistentResultButtons(discord.ui.View):

  def __init__(self, urls: list[str] = None):
    super().__init__(timeout=None)
    self.add_item(DownloadButton(urls))


async def download_attachment(
    session: aiohttp.ClientSession,
    url: str,
) -> bytes:
  async with session.get(url) as response:
    response.raise_for_status()
    return await response.read()


async def fetch_images(urls: Sequence[str]) -> list[bytes]:
  timeout = aiohttp.ClientTimeout(total=30)
  async with aiohttp.ClientSession(timeout=timeout) as session:
    return list(
        await asyncio.gather(
            *(download_attachment(session, url) for url in urls)
        )
    )


async def send_result(
    send_func: Callable[..., Awaitable[object]],
    image_data: Sequence[bytes],
    filenames: Sequence[str],
    author_mention: str,
    original_urls: list[str],
) -> None:
  for image_bytes in image_data:
    validate_image(image_bytes)

  final_bytes = create_avatar_design(image_data[0], image_data[1])

  # إرسال الصورة المدمجة فقط في السيرفر
  file_to_send = discord.File(
      io.BytesIO(final_bytes), filename='noir-avatar.png'
  )
  view = PersistentResultButtons(original_urls)

  await send_func(
      content=f'**From:** {author_mention}',
      file=file_to_send,
      view=view,
  )


@bot.event
async def on_ready() -> None:
  bot.add_view(PersistentResultButtons())
  await bot.tree.sync()
  if bot.user:
    logger.info('Logged in as %s (%s)', bot.user, bot.user.id)


@bot.command(name='merge', aliases=['دمج'])
async def merge_images(ctx: commands.Context) -> None:
  if len(ctx.message.attachments) < 2:
    await ctx.send(
        '❌ يرجى إرفاق **صورتين** مع الأمر!',
        delete_after=5,
    )
    return

  attachments = ctx.message.attachments[:2]
  urls = [att.url for att in attachments]
  try:
    image_data = await fetch_images(urls)

    try:
      await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound):
      pass

    filenames = [
        safe_filename(attachment.filename, index)
        for index, attachment in enumerate(attachments, start=1)
    ]
    await send_result(
        ctx.send, image_data, filenames, ctx.author.mention, urls
    )
  except (aiohttp.ClientError, OSError, ValueError, IndexError) as error:
    logger.exception('Could not prepare the attached images: %s', error)
    await ctx.send('❌ تأكد من أن المرفقين صورتان صالحَتان.')
  except discord.HTTPException:
    logger.exception('Could not send the merge result to Discord.')


@bot.tree.command(name='merge', description='إنشاء تصميم من صورتين')
@app_commands.describe(
    first='الصورة الأولى، ستظهر كعنصر دائري',
    second='الصورة الثانية، ستكون خلفية التصميم',
)
async def merge_slash(
    interaction: discord.Interaction,
    first: discord.Attachment,
    second: discord.Attachment,
) -> None:
  await interaction.response.defer()
  urls = [first.url, second.url]
  try:
    image_data = await fetch_images(urls)
    filenames = [
        safe_filename(first.filename, 1),
        safe_filename(second.filename, 2),
    ]
    await send_result(
        interaction.followup.send,
        image_data,
        filenames,
        interaction.user.mention,
        urls,
    )
  except (aiohttp.ClientError, OSError, ValueError, IndexError) as error:
    logger.exception('Could not prepare slash-command images: %s', error)
    await interaction.followup.send(
        '❌ تأكد من أن المرفقين صورتان صالحَتان.',
        ephemeral=True,
    )
  except discord.HTTPException:
    logger.exception('Could not send the slash-command result to Discord.')


@bot.event
async def on_command_error(
    ctx: commands.Context,
    error: commands.CommandError,
) -> None:
  if isinstance(error, commands.CommandNotFound):
    return
  logger.exception('Unhandled command error: %s', error)


def main() -> None:
  token = os.getenv('DISCORD_TOKEN') or os.getenv('DISCORD_BOT_TOKEN')
  if not token:
    raise RuntimeError('DISCORD_TOKEN environment variable is not set!')
  bot.run(token, log_handler=None)


if __name__ == '__main__':
  main()
