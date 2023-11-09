#!/usr/bin/python3
# -*- coding:utf-8 -*-
import sys
import os

picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

import logging
from waveshare_epd import epd7in3f
import time
from PIL import Image  # ,ImageDraw,ImageFont
import base64, requests  # , traceback

logging.basicConfig(level=logging.DEBUG)

import argparse as ap

p = ap.ArgumentParser()
p.add_argument("--api_path", default="https://78fa-140-122-136-198.ngrok-free.app", help="Use Generated AI or not")
p.add_argument("--img_path", help="The path of image, which you want to print it on ePaper")
p.add_argument("--useGeneratedAI", default="Y", help="Use Generated AI or not")
args = p.parse_args()

if args.useGeneratedAI == "Y":
    with open(args.img_path, 'rb') as f:
        img = base64.b64encode(f.read()).decode('utf8')
    response = requests.post(
        args.api_path + "/generate",
        headers={'ngrok-skip-browser-warning': 'use it to skip ngrok warning. this value can be anything.'},
        json={'img': img}  # , 'voice': voice # Optional }
    ).json();
    img = response['img'];
    img_comment = response['img_comment']  # bgm = response['bgm']

    with open('./rcv_img.png', 'wb') as f:
        f.write(base64.b64decode(img))
    args.img_path = './rcv_img.png'
    print(f'Save to {args.img_path}')
    print(img_comment)

# open PNG
input_image = Image.open(args.img_path)

# 定義目標畫布大小
canvas_width = 800
canvas_height = 480

# 計算縮放比例
width_ratio = canvas_width / input_image.width
height_ratio = canvas_height / input_image.height
scaling_factor = min(width_ratio, height_ratio)

# 計算新的圖片尺寸
new_width = int(input_image.width * scaling_factor)
new_height = int(input_image.height * scaling_factor)

# 縮小PNG圖片
resized_image = input_image.resize((new_width, new_height), Image.ANTIALIAS)

# 創建一個800x480的空白畫布
canvas = Image.new("RGB", (canvas_width, canvas_height), "white")

# 計算將圖片放在畫布中央的位置
x_offset = (canvas_width - new_width) // 2
y_offset = (canvas_height - new_height) // 2

# 在畫布上繪製縮小後的圖片
canvas.paste(resized_image, (x_offset, y_offset))

# 保存結果為BMP檔
import random;
import string;

N = 10
tmp = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(N))
tmp = args.img_path[:-4] + f"_800_480_out_{tmp}.bmp"
canvas.save(tmp)

try:
    logging.info("epd7in3f Demo")

    epd = epd7in3f.EPD()
    logging.info("init and Clear")
    epd.init()
    epd.Clear()

    logging.info("read bmp file")
    #   Himage = Image.open(os.path.join(picdir, '7in3f3.bmp'))
    #   Himage = Image.open(args.bmp_path)
    Himage = Image.open(tmp)
    epd.display(epd.getbuffer(Himage))
    time.sleep(10)

    #   logging.info("Clear...")
    #   epd.Clear()

    logging.info("Goto Sleep...")
    epd.sleep()

except IOError as e:
    logging.info(e)

except KeyboardInterrupt:
    logging.info("ctrl + c:")
    epd7in3f.epdconfig.module_exit()
    exit()
