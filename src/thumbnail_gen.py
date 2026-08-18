from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
from io import BytesIO

def create_pro_thumbnail(bg_image_url, title, output_path):
    try:
        response = requests.get(bg_image_url)
        img = Image.open(BytesIO(response.content)).convert("RGB")
        img = img.resize((1280, 720))
        img = img.filter(ImageFilter.SHARPEN)
        
        draw = ImageDraw.Draw(img)
        # Note: You need a .ttf font file in the /template folder
        try:
            font = ImageFont.truetype("template/font.ttf", 80)
        except:
            font = ImageFont.load_default()
        
        # Darken bottom for text
        overlay = Image.new('RGBA', img.size, (0,0,0,0))
        draw_ov = ImageDraw.Draw(overlay)
        draw_ov.rectangle([0, 500, 1280, 720], fill=(0, 0, 0, 160))
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        
        draw = ImageDraw.Draw(img)
        text_pos = (50, 550)
        draw.text(text_pos, title.upper(), font=font, fill="yellow")
        
        img.save(output_path, quality=95)
        print(f"Thumbnail saved to {output_path}")
    except Exception as e:
        print(f"Thumbnail Error: {e}")
