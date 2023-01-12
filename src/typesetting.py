import base64
import io
from PIL import Image, ImageDraw, ImageFont


font = ImageFont.truetype("src/resources/wenquanyi_10pt.pcf", 13)


def text_bitmap(
    text="string\nlorem ipsum 114514\n1919810\n共计处理了489975条消息",
    font=font,
    line_height=28,
    margin=8,
    border=3,
    padding_inline=12,
    padding_block=4,
    scale=2,
    dash_on=4,
    dash_off=4,
):
    img0 = Image.new("RGB", (274, line_height * (text.count("\n") + 1) - 1), "#fff3df")
    for y in range(line_height - 1, img0.height, line_height):
        for x in range(0, img0.width, dash_on + dash_off):
            img0.paste("#ffcc80", (x, y, x + dash_on, y + 1))
    ImageDraw.Draw(img0).multiline_text(
        (0, 8), text, fill="black", font=font, spacing=15
    )

    img1 = Image.new(
        "RGB",
        (
            img0.width + (margin + border + padding_inline) * 2,
            img0.height + (margin + border + padding_block) * 2,
        ),
        "#ffcc80",
    )
    ImageDraw.Draw(img1).rectangle(
        ((margin, margin), (img1.width - margin, img1.height - margin)),
        outline="#b53c00",
        fill="#fff3df",
        width=border,
    )

    img1.paste(
        img0, (margin + border + padding_inline, margin + border + padding_block)
    )
    img1 = img1.resize(
        (img1.width * scale, img1.height * scale), resample=Image.NEAREST
    )
    return img1


def pil_image_to_base64(img: Image.Image) -> str:
    with io.BytesIO() as f:
        img.save(f, format="PNG")
        return base64.b64encode(f.getvalue()).decode()


text_bitmap().save("output.png", "PNG")
