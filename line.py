from argparse import ArgumentParser

from flask import Flask, request, abort
from linebot import (LineBotApi, WebhookHandler)
from linebot.exceptions import (InvalidSignatureError)
from linebot.models import (
    MessageEvent,
    TextMessage, TextSendMessage,
    ImageMessage, ImageSendMessage)

from flask import current_app
from flask import Blueprint
import urllib.parse
import json


# ★★★
line = Blueprint('line', __name__, url_prefix='/line')
# app = Flask(__name__)


# Please setup your line.json
# channel_access_token: Messaging API設定 > channel access token
# channel_secret:       チャネル基本設定   > channel secret token
json_data = json.load(open('line.json', 'r'))
line_bot_api = LineBotApi(json_data['channel_access_token'])
handler = WebhookHandler(json_data['channel_secret'])
ngrok_url = json_data['ngrok_url']


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


# @handler.add(MessageEvent, message=TextMessage)
# def handle_text_message(event):
#     message_content = event.message.text
#     line_bot_api.reply_message(
#             event.reply_token,
#             TextSendMessage(text = message_content))


@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    message_content = line_bot_api.get_message_content(event.message.id)

    # an image send from line is stored in static directory.
    with open("static/"+event.message.id+".jpg", "wb") as f:
        f.write(message_content.content)

    # /generate
    # generated_image =

    # PNG or JPEG only
    # original content file size: max 10MB
    original_encoded_url = urllib.parse.quote(event.message.id)
    # preview image file size: max 1MB
    preview_encoded_url = urllib.parse.quote(event.message.id)

    line_bot_api.reply_message(
        event.reply_token,
        ImageSendMessage(
            original_content_url = ngrok_url + "/static/"+ original_encoded_url +".jpg",
            preview_image_url = ngrok_url + "/static/" + preview_encoded_url + ".jpg"))


# ★★★ delete below codes
# if __name__ == "__main__":
#     arg_parser = ArgumentParser(
#         usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
#     )
#     arg_parser.add_argument('-p', '--port', type=int,
#                             default=8000, help='port')
#     arg_parser.add_argument('-d', '--debug', default=False, help='debug')
#     options = arg_parser.parse_args()

#     app.run(debug=options.debug, port=options.port)
