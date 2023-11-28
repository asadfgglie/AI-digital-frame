import argparse
import os.path

parser = argparse.ArgumentParser(
    prog=os.path.basename(__file__),
    description='This is AI digital frame backend server.')
tmp = ['CRITICAL', 'FATAL', 'ERROR', 'WARN', 'WARNING', 'INFO', 'DEBUG', 'NOTSET']
tmp = tmp + [i.lower() for i in tmp]
parser.add_argument('-l', '--logging-level',
                    choices=tmp,
                    default='INFO',
                    help='set logging level')
parser.add_argument('--env', '-e', action='store',
                    help='what `.env` file should be load.',
                    default=False)
parser.add_argument('--host', action='store',
                    help='start host', default='localhost')
parser.add_argument('--port', '-p', action='store',
                    type=int, help='start post', default=5000)

import logging
logging.basicConfig(level=parser.parse_args().logging_level.upper(), format='%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logging.info('Importing...')

from typing import Optional

from pyngrok import ngrok
if parser.parse_args().env:
    logging.info('load env values...')
    from dotenv import load_dotenv
    if load_dotenv(parser.parse_args().env):
        logging.info(f'load `{parser.parse_args().env}` success.')
    else:
        logging.warning('no .env file has load.')

import time

import requests

import io
import asyncio
import base64
from PIL import Image

from flask import Flask, request, jsonify, render_template

import util
import line
logging.info('Import done.')

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'GET':
        return jsonify(util.config)
    else:
        args = dict(request.args)
        if request.is_json:
            args.update(request.json)
        util.save_config(args)
        return jsonify(util.config)

@app.route('/generate', methods=['POST'])
def generate():
    """
    http body json args:
        img: image warp by raw base64 text,
        voice: mp3 or wav file warp by raw base64 text
    :return:
        a json include `generated bgm`, `generated picture`, and `generated picture's comment and description`.
    """
    args = request.json
    img = args.get('img')
    try:
        Image.open(io.BytesIO(base64.b64decode(img))).save(util.IMG_INPUT)
    except:
        return jsonify({'detail':'need img as input!'}), 400
    voice_prompt: Optional[str] = args.get('voice', None)
    image_prompt: str = args.get('image_prompt', '')
    bgm_prompt: str = args.get('bgm_prompt', '')

    if image_prompt == '' and bgm_prompt == '' and util.config['now_prompt_style'] is not None:
        style = None
        try:
            style = util.config["prompt_style"][util.config['now_prompt_style']]
            logging.info('use prompt style: ' + util.config['now_prompt_style'])
        except:
            logging.info(f'Not find `{util.config["now_prompt_style"]}` prompt style.')
        try:
            image_prompt = style['image_prompt']
        except:
            logging.info(f'Not find `image_prompt` in `{util.config["now_prompt_style"]}` prompt style.')
        try:
            bgm_prompt = style['bgm_prompt']
        except:
            logging.info(f'Not find `bgm_prompt` in `{util.config["now_prompt_style"]}` prompt style.')

    if voice_prompt is not None:
        with open(util.VOICE_PROMPT, 'wb') as f:
            logging.info('save ' + util.VOICE_PROMPT)
            f.write(base64.b64decode(voice_prompt))
        voice_prompt = util.whisper_model.transcribe(util.VOICE_PROMPT)["text"]
        logging.info('transcribe voice: ' + voice_prompt)
    else:
        voice_prompt = ''

    image_generate_pipline = None
    interrogate_img_prompt: str = ''
    if util.config['image_generate_api'].lower() in util.IMAGE_GENERATE_API['sd']:
        logging.info('interrogate image prompt...')
        t1 = time.time()
        interrogate_img_prompt = requests.post("http://127.0.0.1:7860/sdapi/v1/interrogate", json={
            "image": img,
            "model": "clip"
        }).json()['caption']
        logging.info('interrogate image prompt done. take {:.2f} sec.'.format(time.time() - t1))
        image_generate_pipline = util.stable_diffusion_pipline
    elif util.config['image_generate_api'].lower() in util.IMAGE_GENERATE_API['dall-e']:
        image_generate_pipline = util.DALL_E_pipline
    else:
        return jsonify({
            'detail': f'set config.json `image_generate_api` as {util.IMAGE_GENERATE_API}'
        }), 400
    logging.info(f'Image api: {image_generate_pipline.__name__}')

    gpt4_reply = util.GPT4_pipline(img, voice_prompt)
    if voice_prompt == '':
        voice_prompt = None
    logging.info('gpt4_reply: ' + str(gpt4_reply))

    output_set: tuple[set[asyncio.Task], set] = asyncio.run(asyncio.wait([
        image_generate_pipline(image_prompt + interrogate_img_prompt + gpt4_reply["img_prompt"],
                                      img),
        util.music_gen_pipline(bgm_prompt + ('"' + voice_prompt + '", ' if voice_prompt is not None else '') + gpt4_reply["bgm_prompt"],
                               util.VOICE_PROMPT if voice_prompt is not None else None
    )]))
    output_set: list[asyncio.Task] = list(output_set[0])
    bgm = None
    img:  Optional[str, tuple] = None
    for i in output_set:
        if i.get_coro().__name__ is util.music_gen_pipline.__name__:
            bgm = i.result()
        elif i.get_coro().__name__ is image_generate_pipline.__name__:
            img = i.result()
    if isinstance(img, tuple):
        logging.error(img[1][0], str(img[1]))
        return jsonify({'detail': str(img[1])}), 400

    pic_comment = util.GPT4_pipline(img)
    logging.info('GPT4 comment: ' + pic_comment)

    return jsonify({
        'img_comment': pic_comment,
        'img': img,
        'bgm': bgm
    })


if __name__ == '__main__':
    try:
        util.PORT = parser.parse_args().port
        if parser.parse_args().host != 'localhost':
            app.register_blueprint(line.line)
            ngrok_connect = ngrok.connect(str(util.PORT), 'http')
            line.ngrok_url = ngrok_connect.public_url
            logging.info(f'public_url: {ngrok_connect.public_url}')
        else:
            logging.warning('Now using localhost as uri. So line bot won\'t activate.')
        app.run(parser.parse_args().host, port=util.PORT)
    except KeyboardInterrupt:
        ngrok.kill()
        exit(0)