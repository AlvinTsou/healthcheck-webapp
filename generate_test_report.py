import os
from PIL import Image, ImageDraw, ImageFont

# Set up canvas
width, height = 800, 600
image = Image.new('RGB', (width, height), color=(255, 255, 255))
draw = ImageDraw.Draw(image)

# Font path on macOS
font_path = "/System/Library/Fonts/PingFang.ttc"
if not os.path.exists(font_path):
    # fallback to Arial Unicode if PingFang doesn't exist
    font_path = "/Library/Fonts/Arial Unicode.ttf"

try:
    font_title = ImageFont.truetype(font_path, 24)
    font_header = ImageFont.truetype(font_path, 16)
    font_text = ImageFont.truetype(font_path, 14)
except Exception:
    font_title = ImageFont.load_default()
    font_header = ImageFont.load_default()
    font_text = ImageFont.load_default()

# Colors
black = (0, 0, 0)
red = (220, 50, 50)
blue = (0, 100, 200)
gray = (128, 128, 128)
light_gray = (240, 240, 240)

# Draw Title
draw.text((300, 30), "健康檢查報告 (模擬測試)", fill=black, font=font_title)
draw.text((50, 80), "姓名：王小明", fill=black, font=font_header)
draw.text((250, 80), "性別：男", fill=black, font=font_header)
draw.text((450, 80), "年齡：45歲", fill=black, font=font_header)
draw.text((600, 80), "日期：2026-06-15", fill=black, font=font_header)

# Draw a thin separator line
draw.line((50, 110, 750, 110), fill=gray, width=2)

# Table Header
headers = ["檢驗項目", "英文名稱", "檢查結果", "單位", "參考值範圍", "判定"]
col_positions = [50, 200, 350, 450, 550, 680]
for col_idx, header in enumerate(headers):
    draw.text((col_positions[col_idx], 130), header, fill=blue, font=font_header)

draw.line((50, 160, 750, 160), fill=gray, width=1)

# Table Rows
# Row format: (name_zh, name_en, result, unit, ref_range, status, is_abnormal)
rows = [
    ("收縮壓", "Systolic BP", "135", "mmHg", "< 120", "偏高", True),
    ("舒張壓", "Diastolic BP", "85", "mmHg", "< 80", "偏高", True),
    ("空腹血糖", "Fasting Glucose", "115", "mg/dL", "70 - 99", "偏高", True),
    ("總膽固醇", "Total Cholesterol", "245", "mg/dL", "< 200", "偏高", True),
    ("三酸甘油脂", "Triglycerides", "165", "mg/dL", "< 150", "偏高", True),
    ("天門冬胺酸轉胺酶", "GOT (AST)", "35", "U/L", "< 37", "正常", False),
    ("丙胺酸轉胺酶", "GPT (ALT)", "32", "U/L", "< 41", "正常", False),
    ("肌酸酐", "Creatinine", "0.9", "mg/dL", "0.7 - 1.2", "正常", False),
]

y_pos = 180
for row in rows:
    zh, en, val, unit, ref, status, abnormal = row
    color = red if abnormal else black
    draw.text((col_positions[0], y_pos), zh, fill=color, font=font_text)
    draw.text((col_positions[1], y_pos), en, fill=color, font=font_text)
    draw.text((col_positions[2], y_pos), val, fill=color, font=font_text)
    draw.text((col_positions[3], y_pos), unit, fill=color, font=font_text)
    draw.text((col_positions[4], y_pos), ref, fill=color, font=font_text)
    draw.text((col_positions[5], y_pos), status, fill=color, font=font_text)
    # Draw horizontal divider
    draw.line((50, y_pos + 25, 750, y_pos + 25), fill=light_gray, width=1)
    y_pos += 40

# Add a warning footer
draw.text((50, 520), "* 模擬數據：僅供系統開發與整合測試使用，不具備任何醫學診斷效益。", fill=gray, font=font_text)

# Save
output_dir = "static"
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "test_report.png")
image.save(output_path)
print(f"Test report image generated successfully at: {output_path}")
