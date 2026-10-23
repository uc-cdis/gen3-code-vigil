"""
This script is used by the test of the same name in the `TestGen3Workflow` class
"""

import os
import zipfile

from PIL import Image, ImageDraw

# Kind CI uses Mountpoint S3, which doesn't support appends or random-access writes
S3FILES = os.environ.get("S3FILES") == "YES"
print(f"S3FILES: {os.environ.get('S3FILES')} => {S3FILES}")

# Test sequential file writes
with open("output.txt", "w") as f:
    f.write("Initial sequential data\n")
if S3FILES:
    with open("output.txt", "a") as f:
        f.write("Second sequential data\n")


# Test multipage PDF creation
page_one = Image.new("RGB", (100, 200), color="white")
draw_tool = ImageDraw.Draw(page_one)
draw_tool.rectangle([(10, 10), (40, 40)], fill="black")
page_two = Image.new("RGB", (300, 400), color="lightgray")
draw_tool = ImageDraw.Draw(page_two)
draw_tool.rectangle([(20, 20), (40, 40)], fill=(255, 0, 0))
page_one.save("output.pdf", "PDF", save_all=True, append_images=[page_two])


# Test ZIP file creation
files_to_zip = ["output.txt", "output.pdf"]
if S3FILES:
    with zipfile.ZipFile("output.zip", "w", zipfile.ZIP_DEFLATED) as f:
        for file in files_to_zip:
            f.write(file)
else:
    # the task expects this output file to exist
    with open("output.zip", "w") as f:
        f.write("")
