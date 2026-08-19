import asyncio
import io
import json
import logging
import os
from pathlib import Path
from typing import Sequence, Optional

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageOps

# إعداد السجل (Logging)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

tree_synced = False
views_restored = False
RESULTS_DIR = Path("data/profile_results")


def save_result_originals(
    result_message_id: int,
    originals: Sequence[tuple[bytes, str]],
) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    metadata = []
    for index, (image_bytes, filename) in enumerate(originals, start=1):
        stored_name = f"{result_message_id}_{index}.bin"
        (RESULTS_DIR / stored_name).write_bytes(image_bytes)
        metadata.append({"path": stored_name, "filename": filename})
    
    (RESULTS_DIR / f"{result_message_id}.json").write_text(
        json.dumps(metadata, ensure_ascii=False),
        encoding="utf-8",
    )


def load_result_originals(result_message_id: int) -> list[tuple[bytes, str]]:
    metadata_path = RESULTS_DIR / f"{result_message_id}.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return [
        (
            (RESULTS_DIR / item["path"]).read_bytes(),
            str(item["filename"]),
        )
        for item in metadata
    ]


def remove_saved_result(result_message_id: int) -> None:
    metadata_path = RESULTS_DIR / f"{result_message_id}.json"
    if not metadata_path.exists():
        return
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        for item in metadata:
            (RESULTS_DIR / item["path"]).unlink(missing_ok=True)
    finally:
        metadata_path.unlink(missing_ok=True)


def restore_result_views() -> None:
    if not RESULTS_DIR.exists():
        return
    for metadata_path in RESULTS_DIR.glob("*.json"):
        try:
            result_message_id = int(metadata_path.stem)
            originals = load_result_originals(result_message_id)
            if len(originals) >= 1:
                bot.add_view(
                    ResultButtons(originals),
                    message_id=result_message_id,
                )
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            logger.exception(
                "Could not restore result buttons from %s.",
                metadata_path,
            )


def create_rounded_image(image_bytes: bytes, size: tuple[int, int], radius: int) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = ImageOps.fit(img, size, method=Image.Resampling.LANCZOS)
    
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + size, radius=radius, fill=255)
    
    output = Image.new("RGBA", size)
    output.putalpha(mask)
    output.paste(img, (0, 0), mask)
    return output


def create_profile_card(banner_bytes: bytes, avatar_bytes: bytes) -> bytes:
    card_size = (800, 450)
    banner_size = (780, 280)
    avatar_frame_size = (220, 220)
    avatar_size = (200, 200)
    
    background_color = (35, 39, 42)
    card_image = Image.new("RGBA", card_size, background_color)
    draw = ImageDraw.Draw(card_image)
    
    banner_pil = Image.open(io.BytesIO(banner_bytes)).convert("RGBA")
    banner_pil = ImageOps.fit(banner_pil, banner_size, method=Image.Resampling.LANCZOS)
    card_image.paste(banner_pil, (10, 10))
    
    frame_color = (114, 137, 218)
    frame_thickness = 8
    
    frame_x = 50
    frame_y = banner_size[1] - (avatar_frame_size[1] // 2)
    
    draw.ellipse(
        [frame_x, frame_y, frame_x + avatar_frame_size[0], frame_y + avatar_frame_size[1]],
        fill=background_color,
        outline=frame_color,
        width=frame_thickness
    )
    
    avatar_pil_round = create_rounded_image(avatar_bytes, avatar_size, radius=100)

    avatar_x = frame_x + (avatar_frame_size[0] - avatar_size[0]) // 2
    avatar_y = frame_y + (avatar_frame_size[1] - avatar_size[1]) // 2
    
    card_image.paste(avatar_pil_round, (avatar_x, avatar_y), avatar_pil_round)

    output = io.BytesIO()
    card_image.save(output, format="PNG")
    return output.getvalue()


def validate_image(image_bytes: bytes) -> None:
    with Image.open(io.BytesIO(image_bytes)) as img:
        img.verify()


class ResultButtons(discord.ui.View):
    def __init__(self, originals: Sequence[tuple[bytes, str]]):
        super().__init__(timeout=None)
        self.originals = list(originals)

    @discord.ui.button(label="تنزيل", style=discord.ButtonStyle.primary, custom_id="download_result_btn", emoji="📥")
    async def download_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            final_image_bytes = load_result_originals(interaction.message.id)[0][0]
            await interaction.response.send_message(
                file=discord.File(io.BytesIO(final_image_bytes), filename="profile_card.png"),
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(f"حدث خطأ أثناء جلب الصورة: {e}", ephemeral=True)

    @discord.ui.button(label="حذف النتيجة", style=discord.ButtonStyle.danger, custom_id="delete_result_btn", emoji="🗑️")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
            await interaction.message.delete()
            remove_saved_result(interaction.message.id)
        except discord.Forbidden:
            await interaction.followup.send(
                "لا يمكنني حذف الرسالة. تأكد من منحي صلاحية إدارة الرسائل.",
                ephemeral=True,
            )


@bot.event
async def on_ready() -> None:
    global tree_synced, views_restored
    if not tree_synced:
        await bot.tree.sync()
        tree_synced = True
    if not views_restored:
        restore_result_views()
        views_restored = True
    if bot.user:
        logger.info("Logged in as %s (%s)", bot.user, bot.user.id)


@bot.tree.command(name="merge", description="إنشاء بطاقة بروفايل احترافية بدمج البانر والأفاتار")
async def merge_command(
    interaction: discord.Interaction,
    banner: discord.Attachment,
    avatar: discord.Attachment,
    member: Optional[discord.Member] = None
):
    await interaction.response.defer()
    
    try:
        data1 = await banner.read()
        data2 = await avatar.read()
        
        validate_image(data1)
        validate_image(data2)
        
        final_bytes = create_profile_card(data1, data2)
        
        target_member = member or interaction.user
        
        result_message = await interaction.followup.send(
            content=f"**From:** {target_member.mention}",
            file=discord.File(
                io.BytesIO(final_bytes),
                filename="profile_card.png",
            ),
            view=ResultButtons([(final_bytes, "profile_card.png")]),
        )
        
        result_message_id = getattr(result_message, "id", None)
        if isinstance(result_message_id, int):
            save_result_originals(result_message_id, [(final_bytes, "profile_card.png")])
            
    except Exception as e:
        await interaction.followup.send(f"حدث خطأ أثناء معالجة الصور: {e}", ephemeral=True)


bot.run(os.getenv("BOT_TOKEN"))
