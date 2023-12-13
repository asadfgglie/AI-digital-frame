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

parser.add_argument('--ngrok', '-nk', action='store_true',
                    help='whether use ngrok or not.')

import logging
logging.basicConfig(level=parser.parse_args().logging_level.upper(), format='%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logging.info('Importing...')

from typing import Optional
import json
import random

import numpy as np

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
import base64
from PIL import Image

from flask import Flask, request, jsonify, render_template, redirect

import util
import line
logging.info('Import done.')

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html', raspberrypi_url=util.config['raspberrypi_server'])

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

@app.route('/raspberrypi_url', methods=['POST'])
def raspberrypi_url():
    util.save_config("raspberrypi_server", request.values['raspberrypi_url'])
    return redirect('/')

@app.route('/comment', methods=['POST'])
def comment():
    if not request.is_json:
        return jsonify({
            'detail': 'need json format data as input!'
        }), 400
    data = request.json
    try:
        path = f"./static/log/{data['time_stmp']}/info.json"
        score = data['score']
    except Exception as e:
        return jsonify({
            'detail': str(e.args)
        }), 400

    with open(path, 'r') as f:
        prompt_style = json.loads(f.read())['prompt_style']
    util.config['prompt_style'].get(prompt_style, {"random_weight": 0})["random_weight"] += score
    util.save_config()

    return jsonify({
        k: util.config["prompt_style"][k]['random_weight'] for k in util.config["prompt_style"].keys()
    })

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

    style = None
    if image_prompt == '' and bgm_prompt == '' and util.config['now_prompt_style'] is not None:
        if util.config['now_prompt_style'] == util.RANDOM_PROMPT_STYLE:
            logging.info('use prompt style: ' + util.config['now_prompt_style'])
            style_list = list(util.config["prompt_style"].keys())
            weight = util.softmax(np.array([v['random_weight'] for v in util.config["prompt_style"].values()])).tolist()
            style = random.choices(style_list, weight)[0]
            logging.info('random prompt style: ' + style)
        else:
            try:
                style = util.config["prompt_style"][util.config['now_prompt_style']]
                logging.info('use prompt style: ' + util.config['now_prompt_style'])
            except:
                logging.info(f'Not find `{util.config["now_prompt_style"]}` prompt style.')
        try:
            image_prompt = util.config["prompt_style"][style]['image_prompt']
        except:
            logging.info(f'Not find `image_prompt` in `{style}` prompt style.')
        try:
            bgm_prompt = util.config["prompt_style"][style]['bgm_prompt']
        except:
            logging.info(f'Not find `bgm_prompt` in `{style}` prompt style.')

    if voice_prompt is not None:
        with open(util.VOICE_PROMPT, 'wb') as f:
            logging.info('save ' + util.VOICE_PROMPT)
            f.write(base64.b64decode(voice_prompt))
        voice_prompt = util.whisper_model.transcribe(util.VOICE_PROMPT)["text"]
        logging.info('transcribe voice: ' + voice_prompt)
    else:
        voice_prompt = ''

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

    try:
        gpt4_reply = util.GPT4_pipline(img, voice_prompt)
    except RuntimeError as e:
        logging.error(e.args[0], e)
        return jsonify({
            'detail': e.args[0]
        }), 400

    if voice_prompt == '':
        voice_prompt = None
    logging.info('gpt4_reply: ' + str(gpt4_reply))


    img = image_generate_pipline(image_prompt + interrogate_img_prompt + gpt4_reply["img_prompt"],
                                  img)

    if isinstance(img, tuple):
        logging.error(img[1][0], str(img[1]))
        return jsonify({'detail': str(img[1])}), 400

    bgm = util.music_gen_pipline(bgm_prompt + ('"' + voice_prompt + '", ' if voice_prompt is not None else '') + gpt4_reply["bgm_prompt"],
                           util.VOICE_PROMPT if voice_prompt is not None else None)


    pic_comment = util.GPT4_pipline(img)
    logging.info('GPT4 comment: ' + pic_comment)

    time_stmp = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime(time.time()))
    log_path = f'./static/log/{time_stmp}/'

    try:
        os.makedirs(log_path)
    except:
        i = 1
        while True:
            try:
                time_stmp += f'({i})'
                os.makedirs(log_path)
                break
            except:
                i += 1

    def log(name: str):
        try:
            with open(name, 'rb') as l:
                with open(log_path + name.split('/')[-1], 'wb') as f:
                    f.write(l.read())
        except FileNotFoundError:
            pass

    log(util.VOICE_PROMPT)
    log(util.IMG_INPUT)
    log(util.IMG_OUTPUT)
    log(util.BGM_OUTPUT)
    log(util.IMG_OUTPUT_PREVIEW)
    log(util.BGM_OUTPUT[:-4] + '.mp3')
    info_json = {
        'img_prompt': image_prompt + interrogate_img_prompt + gpt4_reply["img_prompt"],
        'bgm_prompt': bgm_prompt + ('"' + voice_prompt + '", ' if voice_prompt is not None else '') + gpt4_reply["bgm_prompt"],
        'now_prompt_style': util.config['now_prompt_style'],
        "prompt_style": style,
    }
    with open(log_path + 'info.json', 'w') as f:
        f.write(json.dumps(info_json, indent=2))

    try:
        title = pic_comment.find('"')
        title = title, pic_comment.find('"', title+1)
        title = pic_comment[title[0]+1: title[1]]
    except:
        title = pic_comment.split('\n')[0]

    try:
        nft_response = requests.post('https://artframe.kjchen.cloud/genNFT', json={
            "name": title,  # NFT title
            "to": util.config['NFT_wallet_address'],  # 鑄造出來的 NFT 要傳送到哪個錢包地址（不知道怎麼填就填一樣就好）
            "image": img,
            "description": pic_comment, # NFT 介紹
            "animation_url": bgm,  # NFT 音檔
            "attributes": [info_json]
        })
        if nft_response.status_code == 200:
            nft_response = dict(nft_response.json())
            nft_response.pop("to")
            nft_response.pop("description")
            nft_response.pop("attributes")

            info_json.update(nft_response)
            logging.info('Success uploading nft artwork!')
        else:
            logging.info(f'Fail uploading nft artwork!\nnft server response:\n{nft_response.content}')
    except Exception as e:
        logging.error("Can't upload artwork onto nft!", e)

    return jsonify({
        'img_comment': pic_comment,
        'img': img,
        'bgm': bgm,
        'time_stmp': time_stmp,
        'info': info_json
    })

if __name__ == '__main__':
    try:
        util.PORT = parser.parse_args().port
        if parser.parse_args().host != 'localhost':
            app.register_blueprint(line.line)
            if parser.parse_args().ngrok:
                ngrok_connect = ngrok.connect(str(util.PORT), 'http')
                line.ngrok_url = ngrok_connect.public_url
                logging.info(f'line-bot webhook public url: {ngrok_connect.public_url}/line/callback')
            else:
                line.ngrok_url = parser.parse_args().host
                logging.info(f'line-bot webhook public url: {line.ngrok_url}/line/callback')
        else:
            logging.warning('Now using localhost as uri. So line bot won\'t activate.')
        app.run(parser.parse_args().host, port=util.PORT)
    except KeyboardInterrupt:
        ngrok.kill()
        exit(0)