CONFIG_FILE = './config.json'

import base64
import json
import logging
from typing import Optional
from pydub import AudioSegment

import requests
from PIL import Image
from flask import Blueprint
from flask import current_app
from flask import request, abort
from linebot import (LineBotApi, WebhookHandler)
from linebot.exceptions import (InvalidSignatureError)
from linebot.models import (
    MessageEvent, PostbackEvent,
    ImageMessage, ImageSendMessage,
    TextMessage, TextSendMessage,
    ButtonsTemplate, TemplateSendMessage, PostbackAction,
    QuickReply, QuickReplyButton,
    AudioSendMessage)

# import util
IMAGE_GENERATE_API = {
    'sd': ['sd', 'stable diffusion', 'stable_diffusion'],
    'dall-e': ['dall-e', 'dall-e2', 'dall-e-v2']
}
# line = Blueprint('line', __name__, url_prefix='/line')

from flask import Flask
from argparse import ArgumentParser
app = Flask(__name__)


# Please set up your line.json
# channel_access_token: Messaging API 設定 > channel access token
# channel_secret:       channel basic 設定 > channel secret token
json_data = json.load(open('line.json', 'r'))
line_bot_api = LineBotApi(json_data['channel_access_token'])
handler = WebhookHandler(json_data['channel_secret'])
ngrok_url: Optional[str] = None

# @line.route("/callback", methods=['POST'])
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)
    current_app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


new_prompt_style_title = ''
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    global new_prompt_style_title
    message_content = event.message.text

    # Switch AI API
    if message_content == 'SwitchAiApi':
        logging.info('Load config...')

        with open(CONFIG_FILE, 'r') as f:
            config: dict = json.loads(f.read())

        current_api = config['image_generate_api']
        switched_to = 'Switched to '

        if current_api in IMAGE_GENERATE_API['sd']:
            switched_to += 'DALL-E'
            config['image_generate_api'] = 'dall-e'
        elif current_api in IMAGE_GENERATE_API['dall-e']:
            switched_to += 'stable diffusion'
            config['image_generate_api'] = 'sd'

        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)

        line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text = switched_to))

    # Example cards
    elif message_content[0:5] == 'card:':
        prompt_style_title = message_content[5:]

        logging.info('Load config...')
        with open(CONFIG_FILE, 'r') as f:
            config: dict = json.loads(f.read())

        logging.info('Update now_prompt_style in config...')
        config['now_prompt_style'] = prompt_style_title
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)

        reply_message = 'Your prompt style was changed to\n"' + prompt_style_title + '"\n\n'
        reply_message += 'Prompt style detail'
        if config['prompt_style'][prompt_style_title]['image_prompt']:
            reply_message += '\n\nImage prompt:\n'
            reply_message += config['prompt_style'][prompt_style_title]['image_prompt']
        if config['prompt_style'][prompt_style_title]['bgm_prompt']:
            reply_message += '\n\nBgm prompt:\n'
            reply_message += config['prompt_style'][prompt_style_title]['bgm_prompt']

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text = reply_message))

    # Make my style
    # prompt title -> image_prompt -> bgm_prompt -> random_weight -> apply
    elif message_content == 'MakeMyStyle':

        # First step: prompt title
        buttons_template = ButtonsTemplate(
            title='4 steps left!',
            text='Please set a prompt style title.',
            actions=[
                PostbackAction(label='Set up',
                               data='input prompt style title',
                               input_option='openKeyboard',
                               fill_in_text='prompt_style_title: '),
            ])
        template_message = TemplateSendMessage(
            alt_text='Please set a prompt style title.',
            template=buttons_template)

        line_bot_api.reply_message(event.reply_token, template_message)

    elif message_content[0:19] == 'prompt_style_title:':
        # Add a new prompt style title
        new_prompt_style_title = message_content[19:]
        if new_prompt_style_title[0] == ' ':
            new_prompt_style_title = new_prompt_style_title[1:]

        logging.info('Load config...')
        with open(CONFIG_FILE, 'r') as f:
            config: dict = json.loads(f.read())

        logging.info('Added a new prompt style in config...')
        config['prompt_style'][new_prompt_style_title] = {}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)

        # Next step: image prompt
        buttons_template = ButtonsTemplate(
            title='3 steps left!',
            text='Please set a image prompt.',
            actions=[
                PostbackAction(
                    label='Set image prompt',
                    data='input image prompt',
                    input_option='openKeyboard',
                    fill_in_text='image_prompt: '),
            ])
        template_message = TemplateSendMessage(
            alt_text='Please set a image prompt.',
            template=buttons_template)

        line_bot_api.reply_message(event.reply_token, template_message)


    elif message_content[0:13] == 'image_prompt:':
        # Add a new image prompt
        new_image_prompt = message_content[13:]
        if new_image_prompt[0] == ' ':
            new_image_prompt = new_image_prompt[1:]

        logging.info('Load config...')
        with open(CONFIG_FILE, 'r') as f:
            config: dict = json.loads(f.read())

        logging.info('Added a new image prompt in config...')
        config['prompt_style'][new_prompt_style_title]['image_prompt'] = new_image_prompt
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)

        # Next step: bgm prompt
        buttons_template = ButtonsTemplate(
            title='2 steps left!',
            text='Please set a bgm prompt.',
            actions=[
                PostbackAction(
                    label='Set bgm prompt',
                    data='input bgm prompt',
                    input_option='openKeyboard',
                    fill_in_text='bgm_prompt: '),
            ])
        template_message = TemplateSendMessage(
            alt_text='Please set a bgm prompt.',
            template=buttons_template)

        line_bot_api.reply_message(event.reply_token, template_message)


    elif message_content[0:11] == 'bgm_prompt:':
        # Add a new bgm prompt
        new_bgm_prompt = message_content[11:]
        if new_bgm_prompt[0] == ' ':
            new_bgm_prompt = new_bgm_prompt[1:]

        logging.info('Load config...')
        with open(CONFIG_FILE, 'r') as f:
            config: dict = json.loads(f.read())

        logging.info('Added a new bgm prompt in config...')
        config['prompt_style'][new_prompt_style_title]['bgm_prompt'] = new_bgm_prompt
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)

        # Next step: random weight
        buttons_template = ButtonsTemplate(
            title='Last steps!',
            text='Please set a random weight.(Optional)',
            actions=[
                PostbackAction(
                    label='Set random weight',
                    data='input random weight',
                    input_option='openKeyboard',
                    fill_in_text='random_weight: 0'),
            ])
        template_message = TemplateSendMessage(
            alt_text='Please set a random weight.(Optional)',
            template=buttons_template)

        line_bot_api.reply_message(event.reply_token, template_message)


    elif message_content[0:14] == 'random_weight:':
        # Add a new random weight
        new_random_weight = float(message_content[14:])

        logging.info('Load config...')
        with open(CONFIG_FILE, 'r') as f:
            config: dict = json.loads(f.read())

        logging.info('Added a new random weight in config...')
        config['prompt_style'][new_prompt_style_title]['random_weight'] = new_random_weight
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)

        # Next step: random weight
        buttons_template = ButtonsTemplate(
            title='Complete!',
            text='Please apply your new style.',
            actions=[
                PostbackAction(
                    label='apply',
                    data='apply new style'),
            ])
        template_message = TemplateSendMessage(
            alt_text='Please apply your new style.',
            template=buttons_template)

        line_bot_api.reply_message(event.reply_token, template_message)


    elif message_content == 'rating':

        rating = QuickReply(items=[
            QuickReplyButton(action=PostbackAction(label='Excellent', data='rating:1.0')),
            QuickReplyButton(action=PostbackAction(label='Very Good', data='rating:0.5')),
            QuickReplyButton(action=PostbackAction(label='Fair', data='rating:0.0')),
            QuickReplyButton(action=PostbackAction(label='Poor', data='rating:-0.5')),
            QuickReplyButton(action=PostbackAction(label='Unacceptable', data='rating:-1.0'))])

        line_bot_api.reply_message(
            event.reply_token,
            [
                TextSendMessage(text = 'image'),
                TextSendMessage(text = 'text'),
                TextSendMessage(text = 'audio'),
                TextSendMessage(text='Are you satisfied with the output?', quick_reply = rating),
            ])


@handler.add(PostbackEvent)
def handle_postback_message(event):

    if event.postback.data == 'input prompt style title':
        example = 'Example of prompt style title\n\n'\
                'prompt_style_title: starry sky dall-e'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text = example))

    elif event.postback.data == 'input image prompt':
        example = 'Example of image prompt\n\n'\
                'image_prompt: '\
                'Long-exposure night photography of a starry sky over a mountain range, with light trails.'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text = example))

    elif event.postback.data == 'input bgm prompt':
        example = 'Example of bgm prompt\n\n'\
                'bgm_prompt: '\
                'Songs for the Planetarium, relaxing music,'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text = example))

    elif event.postback.data == 'input random weight':
        example = 'Optional settings\n\n'\
                'You can just push a send button.\n'\
                'Random weight is 0 as default. And doesn\'t affect your prompt style.'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text = example))

    elif event.postback.data == 'apply new style':
        logging.info('Load config...')
        with open(CONFIG_FILE, 'r') as f:
            config: dict = json.loads(f.read())

        logging.info('Update now_prompt_style in config...')
        config['now_prompt_style'] = new_prompt_style_title
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)

        reply_message = 'Your prompt style was changed to\n"' + new_prompt_style_title + '"\n\n'
        reply_message += 'Prompt style detail'
        if config['prompt_style'][new_prompt_style_title]['image_prompt'] is not None:
            reply_message += '\n\nImage prompt:\n'
            reply_message += config['prompt_style'][new_prompt_style_title]['image_prompt']
        if config['prompt_style'][new_prompt_style_title]['bgm_prompt'] is not None:
            reply_message += '\n\nBgm prompt:\n'
            reply_message += config['prompt_style'][new_prompt_style_title]['bgm_prompt']
        if config['prompt_style'][new_prompt_style_title]['random_weight'] is not None:
            reply_message += '\n\nRandom weight:\n'
            reply_message += str(config['prompt_style'][new_prompt_style_title]['random_weight'])

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text = reply_message))


    elif event.postback.data[0:7] == 'rating:':
        rating = float(event.postback.data[7:])
        logging.info('Load config...')
        with open(CONFIG_FILE, 'r') as f:
            config: dict = json.loads(f.read())

        prompt_style_title = config['now_prompt_style']
        if prompt_style_title in config['prompt_style']:
            logging.info('Rating a prompt style in config...')
            config['prompt_style'][prompt_style_title]['rating'] = rating
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        else:
            pass

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text = 'Thank you for your feedback!'))


@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    message_content = line_bot_api.get_message_content(event.message.id)

    result = requests.post(f'http://localhost:{util.PORT}/generate',
                           json={
                               'img': base64.b64encode(message_content.content).decode('utf8')
                           }
    )

    if result.status_code == 200:
        preview = Image.open(util.IMG_OUTPUT)
        preview = preview.resize((preview.size[0]//2, preview.size[1]//2))
        preview.save(util.IMG_OUTPUT_PREVIEW, format='png')

        AudioSegment.from_wav(util.BGM_OUTPUT).export(util.BGM_OUTPUT[:-4] + '.mp3', format='mp3')

        result = result.json()
        raspberrypi_result = None
        try:
            raspberrypi_result = requests.post(util.config['raspberrypi_server'] + '/line_get_generate',
                json=result.json(),
                headers={
                    'ngrok-skip-browser-warning':
                    'use it to skip ngrok warning. this value can be anything.'
                }
           )
        except ConnectionError as e:
            logging.error(f"Can't connect to raspberrypi! Set up in config or go to {ngrok_url} to set up!", e)

        text = result['img_comment'] + '\n\n - by ChatGPT4'

        if raspberrypi_result is None or raspberrypi_result.status_code != 200:
            text += f"\nCan't connect to raspberrypi! Set up in config or go to {ngrok_url} to set up!"
        line_bot_api.reply_message(
            event.reply_token,
            [
                ImageSendMessage(
                    original_content_url = ngrok_url + f"{util.IMG_OUTPUT[1:]}",
                    preview_image_url = ngrok_url + f"{util.IMG_OUTPUT_PREVIEW[1:]}"
                ),
                TextSendMessage(text),
                AudioSendMessage(ngrok_url + f"{util.BGM_OUTPUT[1: -4]}.mp3", int(util.config["BGM_duration"]))
            ]
        )

    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage('Error!\n```json\n' + json.dumps(result.json(), indent=2) + '\n```')
        )



if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', type=int,
                            default=8000, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    app.run(debug=options.debug, port=options.port)