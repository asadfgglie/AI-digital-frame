import base64
import json
from typing import Optional

import requests
from flask import Blueprint
from flask import current_app
from flask import request, abort
from linebot import (LineBotApi, WebhookHandler)
from linebot.exceptions import (InvalidSignatureError)
from linebot.models import (
    MessageEvent,
    ImageMessage, ImageSendMessage, TextSendMessage, AudioSendMessage)

import app
import util

# ★★★
line = Blueprint('line', __name__, url_prefix='/line')
# app = Flask(__name__)


# Please setup your line.json
# channel_access_token: Messaging API 設定 > channel access token
# channel_secret:       channel basic 設定 > channel secret token
json_data = json.load(open('line.json', 'r'))
line_bot_api = LineBotApi(json_data['channel_access_token'])
handler = WebhookHandler(json_data['channel_secret'])
ngrok_url: Optional[str] = None


# ★★★
@line.route("/callback", methods=['POST'])
# @app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)
    current_app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    message_content = line_bot_api.get_message_content(event.message.id)

    # /generate
    result: dict = requests.post(f'localhost:{util.PORT}/generate',
                           json={
                               'img': base64.b64encode(message_content.content).decode('utf8')
                           }
    ).json()

    line_bot_api.reply_message(
        event.reply_token,
        [
            ImageSendMessage(
                original_content_url = ngrok_url + f"{util.IMG_OUTPUT[1:]}",
                # preview_image_url = ngrok_url + "/static/" + preview_encoded_url + ".png"
            ),
            TextSendMessage(result['img_comment'] + '\n\n - by ChatGPT4'),
            AudioSendMessage(ngrok_url + f"{util.BGM_OUTPUT[1:]}", int(util.config["BGM_duration"]))
        ]
    )