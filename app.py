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
parser.add_argument('--env', action='store',
                    help='what `.env` file should be load.',
                    default=False)

import logging
logging.basicConfig(level=parser.parse_args().logging_level.upper(), format='%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logging.info('Importing...')

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
    :http body json args:
        img: image warp by raw base64 text,
        voice: mp3 or wav file warp by raw base64 text
    :return:
        a json include `generated bgm`, `generated picture`, and `generated picture's comment and description`.
    """
    args = request.json
    img = args.get('img')
    Image.open(io.BytesIO(base64.b64decode(img))).save(util.IMG_INPUT)
    voice_prompt: str = args.get('voice', None)
    image_prompt: str = args.get('image_prompt', 'blonde hair,  long hair, fox ears, curled hair,  fox girl, (fluffy tail), fat tail, hands on the ground,'
            'gold eyes, black irises, long eyelashes, thick eyelashes,  looking at viewer,  smile, '
            '(gold cheongsam), belt, [ornate clothes], black bowtie, white thighhighs, black stockings,'
            'thick thighs, ')
    bgm_prompt: str = args.get('bgm_prompt', 'casual, light, relaxing, piano music, ')
    if voice_prompt is not None:
        with open(util.VOICE_PROMPT, 'wb') as f:
            logging.info('save ' + util.VOICE_PROMPT)
            f.write(base64.b64decode(voice_prompt))
        voice_prompt = util.whisper_model.transcribe(util.VOICE_PROMPT)["text"]
        logging.info('transcribe voice: ' + voice_prompt)

    logging.info('interrogate image prompt...')
    t1 = time.time()
    interrogate_img_prompt: str = requests.post("http://127.0.0.1:7860/sdapi/v1/interrogate", json={
        "image": img,
        "model": "clip"
    }).json()['caption']
    logging.info('interrogate image prompt done. take {:.2f} sec.'.format(time.time() - t1))

    gpt4_reply = {
        "img_prompt":'', "bgm_prompt": ''
    }
    # gpt4_reply = util.GPT4_pipline(img, voice_prompt)
    # logging.info('gpt4_reply: ' + str(gpt4_reply))

    output_set: tuple[set[asyncio.Task], set] = asyncio.run(asyncio.wait([
        util.stable_diffusion_pipline(image_prompt + interrogate_img_prompt + gpt4_reply["img_prompt"],
                                      img),
        util.music_gen_pipline(bgm_prompt + ('"' + voice_prompt + '", ' if voice_prompt is not None else '') + gpt4_reply["bgm_prompt"],
                               util.VOICE_PROMPT
    )]))
    output_set: list[asyncio.Task] = list(output_set[0])
    bgm = None
    img = None
    for i in output_set:
        if i.get_coro().__name__ is util.music_gen_pipline.__name__:
            bgm = i.result()
        elif i.get_coro().__name__ is util.stable_diffusion_pipline.__name__:
            img = i.result()

    pic_comment = util.GPT4_pipline(img)
    logging.info('GPT4 comment: ' + pic_comment)

    return jsonify({
        'img_comment': pic_comment,
        'img': img,
        'bgm': bgm
    })

if __name__ == '__main__':
    app.run('0.0.0.0')