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
    MessageEvent,
    ImageMessage, ImageSendMessage,
    TextMessage, TextSendMessage,
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


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    message_content = event.message.text
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