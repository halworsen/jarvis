"""jarvis.py"""

from base64 import b64encode
from os import remove
from random import choice, seed

from ifunny import Client
from moviepy.editor import VideoFileClip
from PIL import Image, ImageDraw, ImageFont
from requests import post


class Jarvis:
    """
    A Jarvis instance can independently fetch and process gifs to caption
    """

    # The safety limit
    FETCH_SAFETY_LIMIT = 100

    # The width to font size ratio. Used to determine caption font size
    # One pixel of width equates to an additional CAPTION_SIZE_RATIO px in font size
    # 0.13 was found by trial and error and then computing the ratio as font size / image width
    CAPTION_SIZE_RATIO = 0.13

    # Min duration between each frame. Any lower and many gif players
    # will ignore the duration and play it slower than intended
    MIN_FRAME_DURATION = 20

    # The API endpoint used to upload to Imgur
    IMGUR_UPLOAD_ENDPOINT = 'https://api.imgur.com/3/upload.json'

    # URL format for Discord webhooks
    DISCORD_WEBHOOK_FORMAT = 'https://discordapp.com/api/webhooks/{}/{}'

    # How many pixels to pad the caption with
    CAPTION_PADDING = 20

    def __init__(self):
        self.ifunny_client = Client(prefix='/')
        self.caption_pool = ['fart']

        self.imgur_client_id = ''
        self.discord_webhook_id = ''
        self.discord_webhook_token = ''

        self.font = 'C:/WINDOWS/FONTS/ARIAL.TTF'

    def set_imgur_client_id(self, new_id):
        """
        Set the client ID to use for authenticating with Imgur

        Arguments:
            new_id: The client ID to use
        """
        self.imgur_client_id = new_id

    def set_webhook_id(self, new_id):
        """
        Set the webhook ID to use for posting to Discord

        Arguments:
            new_id: The webhook ID to use
        """
        self.discord_webhook_id = new_id

    def set_webhook_token(self, new_token):
        """
        Set the client ID to use for authenticating with Imgur

        Arguments:
            new_token: The client ID to use
        """
        self.discord_webhook_token = new_token

    def add_caption(self, caption):
        """
        Add a new caption to the caption pool

        Arguments:
            caption: The caption to add to the caption pool
        """
        self.caption_pool.append(caption)

    def set_font(self, font):
        """
        Set the font to use when captioning GIFs

        Arguments:
            font: Path to the new font to use
        """
        self.font = font

    def fetch_gif_frames(self, samples, tags):
        """
        Fetches the frames of a random gif from iFunny.
        May raise an exception if the safety limit when
        attempting to fetch gifs is exceeded

        Arguments:
            samples: How many sample gifs to fetch from iFunny
            tags: A collection of iFunny tags to look for gifs in

        Returns:
            A tuple containing a list of the frames of a
            random iFunny GIF and the frame duration
        """

        # Seed the PRNG for better results (maybe?)
        seed()

        post_pool = []
        current_sample = 0
        loop_count = 0
        for ifunny_post in self.ifunny_client.search_tags(choice(tags)):
            if loop_count >= self.FETCH_SAFETY_LIMIT:
                break

            # We're only interested in gifs
            if ifunny_post.type != 'gif_caption':
                loop_count += 1
                continue

            # Add the gif bytes to the pool of gifs
            post_pool.append(ifunny_post)
            current_sample += 1

            if current_sample == samples:
                break

        if not len(post_pool):
            raise RuntimeError('Failed to fetch gifs within safety limit')

        chosen_post = choice(post_pool)
        gif_bytes = chosen_post.content

        # Simply saving to disk saves us some trouble
        file_name = 'jarvis_{}.gif'.format(chosen_post.id)
        with open(file_name, 'wb+') as file:
            file.write(gif_bytes)

        # Find out the frame duration first
        gif = Image.open(file_name)
        frame_duration = gif.info['duration']
        gif.close()

        # This is a bit ugly but PIL has a bug that reads the GIF
        # frames wrong and it screws the image up
        gif = VideoFileClip(file_name)
        frames = []
        for frame in gif.iter_frames():
            frame_image = Image.fromarray(frame)
            frame_image.convert('RGB')
            frames.append(frame_image)
        gif.close()

        remove(file_name)

        return (frames, frame_duration)

    def crop_frame(self, image):
        """
        Crops the caption out of the given image

        Arguments:
            image: The image to crop

        Returns: A cropped image without the caption
        """

        if not image:
            raise TypeError('No image was given')

        crop_y = 0
        pixel_color = image.getpixel((0, 0))
        # The caption should be all white, i.e. (255, 255, 255) until the actual image begins
        while pixel_color[0] == 255 and pixel_color[1] == 255 and pixel_color[2] == 255:
            crop_y += 1
            pixel_color = image.getpixel((0, crop_y))

        # Crop away the original caption
        cropped_image = image.crop((0, crop_y, image.size[0], image.size[1]))
        return cropped_image

    def add_caption(self, image, caption, padding):
        """
        Adds a solid white & black caption to the top of the image

        Arguments:
            image: The image to caption
            caption: The caption to add to the image
            padding: The amount of padding in pixels to use in the y direction

        Returns: A captioned image
        """

        caption_font_size = int(image.size[0] * self.CAPTION_SIZE_RATIO)
        caption_font = ImageFont.truetype(self.font, caption_font_size)

        draw_ctx = ImageDraw.Draw(image)
        caption_size = draw_ctx.textsize(caption, font=caption_font)
        if caption_size[0] > image.size[0]:
            raise ValueError("The caption is too long to fit in the image! Split it up into more lines")
        # Caption size including padding
        # For the * 1.21 see https://stackoverflow.com/questions/55773962/pillow-how-to-put-the-text-in-the-center-of-the-image
        true_caption_size = (caption_size[0], int(caption_size[1] * 1.20 + padding * 2))

        captioned_image = Image.new(
            'RGB',
            (image.size[0] , image.size[1] + true_caption_size[1]),
            (255, 255, 255),
        )

        # Paste in the original image
        captioned_image.paste(
            image,
            (0, true_caption_size[1], image.size[0], captioned_image.size[1]),
        )

        # Draw the caption
        draw_ctx = ImageDraw.Draw(captioned_image)
        draw_ctx.multiline_text(
            (image.size[0] // 2 - caption_size[0] // 2, padding),
            caption,
            font=caption_font,
            fill=(0, 0, 0, 255),
            spacing=4,
        )

        return captioned_image

    def get_jarvised_gif(self, samples, caption):
        """
        Fetches a random gif from iFunny, speeds it up, adds a new caption and returns it

        Arguments:
            samples: The sample size of gifs to pick from
            caption: The new caption

        Returns:
            A tuple containing a list of frames from re-captioned
            random GIF from iFunny and its frame duration
        """

        # Tags are hardcoded in for now, doesn't seem like you can
        # consistently get good gifs from any other tags?
        frames_data = self.fetch_gif_frames(samples, ('gif', 'gifs'))
        # Speed the frame speed up by 3
        new_duration = max(self.MIN_FRAME_DURATION, int(frames_data[1] // 3))

        recaptioned_frames = []
        for frame in frames_data[0]:
            cropped_frame = self.crop_frame(frame)
            captioned_frame = self.add_caption(cropped_frame, caption, self.CAPTION_PADDING)

            recaptioned_frames.append(captioned_frame)

        return (recaptioned_frames, new_duration)

    def save_random_gif(self, file_name, samples, caption):
        """
        Jarvises a random gif from iFunny and saves it to file

        Arguments:
            file_name: The filename to save to
            samples: The sample size of gifs to pick from
            caption: The new caption
        """

        frames = self.get_jarvised_gif(samples, caption)
        frames[0][0].save(
            file_name,
            format='GIF',
            save_all=True,
            optimize=True,
            append_images=frames[0][1:],
            duration=frames[1],
            loop=0,
        )

    def upload_to_imgur(self, file):
        """
        Uploads the given file to Imgur as a GIF

        Arguments:
            file: The filename of the file to upload to Imgur

        Returns: A link to the uploaded GIF
        """

        if self.imgur_client_id == '':
            raise ValueError('Invalid Imgur API client ID')

        imgur_link = ''
        with open(file, 'rb') as gif_file:
            data = gif_file.read()
            b64_gif = b64encode(data)
            print('Client-ID {}'.format(self.imgur_client_id))
            header = {'Authorization': 'Client-ID {}'.format(self.imgur_client_id)}
            data = {'image': b64_gif}

            response = post(
                self.IMGUR_UPLOAD_ENDPOINT,
                headers=header,
                data=data,
            )
            if response.status_code != 200:
                raise RuntimeError('Imgur upload failed ({})'.format(response.status_code))

            imgur_link = response.json()['data']['link']

        return imgur_link

    def post_to_discord(self, link):
        """
        Use a webhook to post the given link as a message on Discord

        Arguments:
            link: The link to post
        """

        if self.discord_webhook_id == '':
            raise ValueError('Invalid Discord webhook ID')

        if self.discord_webhook_token == '':
            raise ValueError('Invalid Discord webhook token')

        response = post(
            self.DISCORD_WEBHOOK_FORMAT.format(self.discord_webhook_id, self.discord_webhook_token),
            data={ 'content': link }
        )

        if response.status_code != 204:
            raise RuntimeError('Failed to post to Discord ({})'.format(response.status_code))

    def work(self):
        """
        Jarvis, enter iFunny, choose random gif, set speed to 3 times
        and add "fart" as caption, then share on discord.
        """

        self.save_random_gif(
            'jarvis_tmp.gif',
            20,
            choice(self.caption_pool)
        )

        imgur_link = self.upload_to_imgur('jarvis_tmp.gif')
        remove('jarvis_tmp.gif')
        self.post_to_discord(imgur_link)
