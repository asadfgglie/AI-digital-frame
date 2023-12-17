import base64
import json
import logging
import os.path
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
    ImageMessage, ImageSendMessage, TextSendMessage, AudioSendMessage, TextMessage, TemplateSendMessage, PostbackAction,
    ButtonsTemplate, QuickReply, QuickReplyButton)
from linebot.models.events import MessageEvent as MsgEvent, PostbackEvent

import util

line = Blueprint('line', __name__, url_prefix='/line')


# Please set up your line.json
# channel_access_token: Messaging API 設定 > channel access token
# channel_secret:       channel basic 設定 > channel secret token
json_data = json.load(open('line.json', 'r'))
line_bot_api = LineBotApi(json_data['channel_access_token'])
handler = WebhookHandler(json_data['channel_secret'])
ngrok_url: Optional[str] = None

@line.route("/callback", methods=['POST'])
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
def handle_text_message(event: MsgEvent):
    global new_prompt_style_title
    message_content: str = event.message.text
    if message_content == 'SwitchAiApi':
        logging.info('Load config...')

        current_api = util.config['image_generate_api']
        switched_to = 'Switched to '

        if current_api in util.IMAGE_GENERATE_API['sd']:
            switched_to += 'DALL-E'
            util.save_config("image_generate_api", "dall-e")
        elif current_api in util.IMAGE_GENERATE_API['dall-e']:
            switched_to += 'stable diffusion'
            util.save_config("image_generate_api", "sd")

        line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text = switched_to))

    elif message_content == 'CallPromptExamples':
        logging.info('load prompt style...')
        messages = []
        for style in util.config['prompt_style'].keys():
            if os.path.isfile(f'./static/style_example/{style}.png'.replace(' ', '_').replace('-', '_')):
                messages.append(TextSendMessage(style))
                messages.append(ImageSendMessage(f"{ngrok_url}/style_example/" + f"{style}.png".replace(' ', '_').replace('-', '_'), f"{ngrok_url}/style_example/" + f"{style}.png".replace(' ', '_').replace('-', '_')))
            else:
                messages.append(TextSendMessage(style + "\n\n This style doesn't have example Image."))

        messages.append(TextSendMessage('use `!style <style name>` to change prompt style!'))
        logging.info('sending style examples...')
        for i in range(0, len(messages), 5):
            line_bot_api.push_message(
                event.source.user_id,
                messages[i: i+5]
            )
    elif message_content.startswith('!style '):
        try:
            style = message_content[message_content.find(' ')+1:]
        except:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(f'use `!style <style name>` to change prompt style!\nFor example:\n\n!style {util.config["now_prompt_style"]}')
            )
            return
        util.save_config("now_prompt_style", style)
        logging.info(f'Change style to \"{util.config["now_prompt_style"]}\".')
        if style not in util.config['prompt_style'].keys():
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    f'style \"{util.config["now_prompt_style"]}\" not exist, so prompt style won\'t work.')
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    f'Change style to \"{util.config["now_prompt_style"]}\".')
            )

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

        util.save_config('prompt_style', {new_prompt_style_title: {}})

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

        util.save_config('prompt_style', {new_prompt_style_title:{'image_prompt':new_image_prompt}})

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

        util.config['prompt_style'][new_prompt_style_title]['bgm_prompt'] = new_bgm_prompt
        util.save_config()

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
        new_random_weight = int(message_content[14:])

        util.config['prompt_style'][new_prompt_style_title]['random_weight'] = new_random_weight
        util.save_config()

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
            QuickReplyButton(action=PostbackAction(label='Excellent', data='rating:2')),
            QuickReplyButton(action=PostbackAction(label='Very Good', data='rating:1')),
            QuickReplyButton(action=PostbackAction(label='Fair', data='rating:0')),
            QuickReplyButton(action=PostbackAction(label='Poor', data='rating:-1')),
            QuickReplyButton(action=PostbackAction(label='Unacceptable', data='rating:-2'))])

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
        util.config['now_prompt_style'] = new_prompt_style_title
        util.save_config()

        reply_message = 'Your prompt style was changed to\n"' + new_prompt_style_title + '"\n\n'
        reply_message += 'Prompt style detail'
        if util.config['prompt_style'][new_prompt_style_title]['image_prompt'] is not None:
            reply_message += '\n\nImage prompt:\n'
            reply_message += util.config['prompt_style'][new_prompt_style_title]['image_prompt']
        if util.config['prompt_style'][new_prompt_style_title]['bgm_prompt'] is not None:
            reply_message += '\n\nBgm prompt:\n'
            reply_message += util.config['prompt_style'][new_prompt_style_title]['bgm_prompt']
        if util.config['prompt_style'][new_prompt_style_title]['random_weight'] is not None:
            reply_message += '\n\nRandom weight:\n'
            reply_message += str(util.config['prompt_style'][new_prompt_style_title]['random_weight'])

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text = reply_message))

    elif event.postback.data[0:7] == 'rating:':
        rating = int(event.postback.data[7:])

        prompt_style_title = util.config['now_prompt_style']
        if prompt_style_title in util.config['prompt_style']:
            util.config['prompt_style'][prompt_style_title]['random_weight'] += rating
            util.save_config()

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
    status_code = result.status_code
    result = result.json()

    if status_code == 200:
        preview = Image.open(util.IMG_OUTPUT)
        preview = preview.resize((preview.size[0]//2, preview.size[1]//2))

        AudioSegment.from_wav(util.BGM_OUTPUT).export(util.BGM_OUTPUT[:-4] + '.mp3', format='mp3')

        log_path = f"./static/log/{result['time_stmp']}"
        preview.save(log_path + util.IMG_OUTPUT_PREVIEW[8:], format='png')
        raspberrypi_result = None
        try:
            raspberrypi_result = requests.post(util.config['raspberrypi_server'] + '/line_get_generate',
                json=result,
                headers={
                    'ngrok-skip-browser-warning':
                    'use it to skip ngrok warning. this value can be anything.'
                }
           )
        except Exception as e:
            logging.error(f"Can't connect to raspberrypi! Set up in config or go to {ngrok_url} to set up!", e)

        text = result['img_comment'] + '\n\n - by ChatGPT4'

        text += '\n\n' + (("AI artwork has been uploaded on OpenSea!\n" + result["info"]["os_url"]) if result["info"].get("os_url", False) else 'Oops! Can\'t upload AI artwork on OpenSea!')

        if raspberrypi_result is None or raspberrypi_result.status_code != 200:
            text += f"\n\nCan't connect to raspberrypi!\nSet up in config or go to {ngrok_url} to set up!"

        original_img_url = result['info'].get('image', f"{ngrok_url}{log_path[1:]}{util.IMG_OUTPUT[8:]}")
        original_bgm_url = result['info'].get('animation_url', f"{ngrok_url}{log_path[1:]}{util.BGM_OUTPUT[8: -4]}.mp3")
        line_bot_api.reply_message(
            event.reply_token,
            [
                ImageSendMessage(
                    original_content_url=original_img_url,
                    preview_image_url=f"{ngrok_url}{log_path[1:]}{util.IMG_OUTPUT_PREVIEW[8:]}"
                ),
                TextSendMessage(text),
                AudioSendMessage(original_bgm_url, int(util.config["BGM_duration"]))
            ]
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage('Error!\n```\n' + json.dumps(result, indent=2) + '\n```')
        )