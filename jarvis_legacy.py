import base64
import os
from random import randint, seed

import requests
from ifunny import Client
from moviepy.editor import VideoFileClip
from PIL import Image, ImageDraw, ImageFont

# Seed twice
seed()
seed()

DISC_WEBHOOK = ''
IMGUR_API_CLI_ID = ''
MIN_DURATION = 20

# tags to choose from
tags = ('gif', 'gifs')

funy = Client(prefix = '/')

# How many posts to choose from
SAMPLE_SIZE = 30
SAFE_LIMIT = 100
SAFETY_COUNTER = 1
CURRENT_SAMPLE = 1

# Fetch a list of gif posts
gifs = []
for post in funy.search_tags(tags[randint(0, len(tags) - 1)]):
    if CURRENT_SAMPLE >= SAMPLE_SIZE:
        break

    if SAFETY_COUNTER >= SAFE_LIMIT:
        break
    SAFETY_COUNTER += 1

    # gifs only >:(
    if post.type != 'gif_caption':
        continue

    CURRENT_SAMPLE += 1
    gifs.append(post)

chosen_gif = gifs[randint(0, len(gifs) - 1)]
gif_bytes = chosen_gif.content

with open('jarvis.gif', 'wb+') as file:
    file.write(gif_bytes)

# Extract the frames from the gif
clip = VideoFileClip('jarvis.gif')
new_frames = []
# Where to crop to remove the original caption (there's usually one)
crop_y = -1
for frame in clip.iter_frames():
    frameim = Image.fromarray(frame)
    frameim.convert('RGB')
    frame_size = frameim.size

    # Find out where to crop to remove the original caption
    if crop_y == -1:
        crop_y = 0
        pixel_color = frameim.getpixel((0, 0))

        # should be all white (255, 255, 255) until the actual gif
        while pixel_color[0] == 255 and pixel_color[1] == 255 and pixel_color[2] == 255:
            crop_y += 1
            pixel_color = frameim.getpixel((0, crop_y))

    # Crop away the original caption
    cropped_frame = frameim.crop((0, crop_y, frame_size[0], frame_size[1]))
    frame_size = cropped_frame.size

    # got 0.13 by trial and erroring font sizes until i got a gif that looked good, then computed font size / image width
    caption_size = int(frame_size[0] * 0.13)
    caption_height = caption_size * 2

    new_frame = Image.new(
        'RGB',
        (frame_size[0], frame_size[1] + caption_height),
        (255, 255, 255),
    )

    new_frame.paste(
        cropped_frame,
        (0, caption_height, frame_size[0], frame_size[1] + caption_height),
    )

    # draw fart on it
    font = ImageFont.truetype('C:/WINDOWS/FONTS/ADOBEFANHEITISTD-BOLD.OTF', caption_size)
    d = ImageDraw.Draw(new_frame)
    tsize = d.textsize('fart', font=font)
    d.multiline_text((frame_size[0] // 2 - tsize[0] // 2, tsize[1] // 2), 'fart', font=font, fill=(0, 0, 0, 255), align='center', spacing=0)

    new_frame.convert('P', palette=Image.ADAPTIVE)
    new_frames.append(new_frame)

clip.close()
gif = Image.open('jarvis.gif')

new_frames[0].save(
    'jarvisx3.gif',
    format='GIF',
    save_all=True,
    optimize=True,
    append_images=new_frames[1:],
    duration=max(MIN_DURATION, int(gif.info['duration'] // 3)),
    loop=0,
)

gif.close()

# upload the funny to imgur
imgur_link = ''
with open('jarvisx3.gif', 'rb') as gif_file:
    data = gif_file.read()
    b64_gif = base64.b64encode(data)

    header = {'Authorization': 'Client-ID ' + IMGUR_API_CLI_ID}
    data = {'image': b64_gif}

    response = requests.post('https://api.imgur.com/3/upload.json', headers=header, data=data)
    imgur_link = response.json()['data']['link']

print('uploaded to ' + imgur_link)
# post it to discord
response = requests.post(
    DISC_WEBHOOK,
    data={'content': imgur_link},
)

# delete the files
os.remove('jarvis.gif')
os.remove('jarvisx3.gif')
