import asyncio
import base64
import json
import logging

import requests
from flask import Flask, request, jsonify, render_template

import util

app = Flask(__name__)

VOICE_PROMPT = './VOICE_PROMPT.wav'

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
    voice_prompt: str = args.get('voice', None)
    image_prompt: str = args.get('image_prompt', 'blonde hair,  long hair, fox ears, curled hair,  fox girl, (fluffy tail), fat tail, hands on the ground,'
            'gold eyes, black irises, long eyelashes, thick eyelashes,  looking at viewer,  smile, '
            '(gold cheongsam), belt, [ornate clothes], black bowtie, white thighhighs, black stockings,'
            'thick thighs, ')
    bgm_prompt: str = args.get('bgm_prompt', 'casual, light, relaxing, piano music, ')
    if voice_prompt is not None:
        with open(VOICE_PROMPT, 'wb') as f:
            f.write(base64.b64decode(voice_prompt))
        voice_prompt = util.whisper_model.transcribe(VOICE_PROMPT)["text"]
        logging.info('transcribe voice: ' + voice_prompt)

    payload = json.dumps({
        "image": img,
        "model": "clip"
    })

    logging.info('interrogate image prompt...')
    interrogate_img_prompt: str = requests.request('POST', "http://127.0.0.1:7860/sdapi/v1/interrogate", data=payload, headers={'Content-Type': 'application/json'}).json()['caption']

    # gpt4_reply = util.GPT4_pipline(img, voice_prompt)

    # gpt4_reply = json.loads(gpt4_reply)

    output_set: tuple[set[asyncio.Task], set] = asyncio.run(asyncio.wait([
        util.stable_diffusion_pipline(image_prompt + interrogate_img_prompt,  #gpt4_reply["interrogate_img_prompt"]
                                      img),
        util.music_gen_pipline(bgm_prompt + (voice_prompt if voice_prompt is not None else '')#gpt4_reply["bgm_prompt"]
    )]))
    output_set: list[asyncio.Task] = list(output_set[0])
    bgm = None
    img = None
    for i in output_set:
        if i.get_coro().__name__ is util.music_gen_pipline.__name__:
            bgm = i.result()
        elif i.get_coro().__name__ is util.stable_diffusion_pipline.__name__:
            img = i.result()

    # pic_comment = util.GPT4_pipline(img)

    return jsonify({
        'img_comment': 'test comment', #pic_comment,
        'img': img,
        'bgm': bgm
    })

if __name__ == '__main__':
    app.run('0.0.0.0')