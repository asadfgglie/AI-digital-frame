import asyncio
import base64

from flask import Flask, request, jsonify
import json

import util

app = Flask(__name__)

VOICE_PROMPT = './VOICE_PROMPT.wav'

@app.route('/')
def index():
    return '<h1>This is AI digital frame backend server.</h1>'

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

    if voice_prompt is not None:
        with open(VOICE_PROMPT, 'wb') as f:
            f.write(base64.b64decode(voice_prompt))
        voice_prompt = util.whisper_model.transcribe(VOICE_PROMPT)

    gpt4_reply = util.GPT4_pipline(img, voice_prompt)

    gpt4_reply = json.loads(gpt4_reply)

    async def tmp(img, gpt4_reply):
        img = asyncio.create_task(util.stable_diffusion_pipline(gpt4_reply['img_prompt'], img))
        bgm = asyncio.create_task(util.music_gen_pipline(gpt4_reply['bgm_prompt']))
        return await img, await bgm

    img, bgm = asyncio.run(tmp(img, gpt4_reply))

    pic_comment = util.GPT4_pipline(img)

    return jsonify({
        'picture_comment': pic_comment,
        'img': img,
        'bgm': bgm
    })

if __name__ == '__main__':
    app.run()