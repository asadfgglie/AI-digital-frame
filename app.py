import asyncio
import base64

from flask import Flask, request, jsonify
import whisper
import json

from util import music_gen_pipline, GPT4_pipline, stable_diffusion_pipline, config

app = Flask(__name__)
whisper_model = whisper.load_model(config['whisper_model'])
VOICE_PROMPT = './VOICE_PROMPT.wav'

@app.route('/')
def index():
    return '<h1>This is AI digital frame backend server.</h1>'

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
        voice_prompt = whisper.transcribe(whisper_model, VOICE_PROMPT)

    gpt4_reply = GPT4_pipline(img, voice_prompt)

    gpt4_reply = json.loads(gpt4_reply)

    async def tmp(img, gpt4_reply):
        img = asyncio.create_task(stable_diffusion_pipline(gpt4_reply['img_prompt'], img))
        bgm = asyncio.create_task(music_gen_pipline(gpt4_reply['bgm_prompt']))
        return await img, await bgm

    img, bgm = asyncio.run(tmp(img, gpt4_reply))

    pic_comment = GPT4_pipline(img)

    return jsonify({
        'picture_comment': pic_comment,
        'img': img,
        'bgm': bgm
    })

if __name__ == '__main__':
    app.run()