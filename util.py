import base64
import copy
import gc
import io
import json
import logging
import os
import time
from typing import Union

import openai
import requests
import torch.cuda
import torchaudio
import whisper
from PIL import Image
from audiocraft.data.audio import audio_write
from audiocraft.models import MusicGen

CONFIG_FILE = './config.json'
VOICE_PROMPT = './VOICE_PROMPT.wav'
IMG_INPUT = './IMAGE_INPUT.png'
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

IMAGE_GENERATE_API = {
    'sd': ['sd', 'stable diffusion', 'stable_diffusion'],
    'dall-e': ['dall-e', 'dall-e2', 'dall-e-v2']
}

logging.info('Load config...')
with open(CONFIG_FILE, 'r') as f:
    config: dict = json.loads(f.read())

logging.info('Load MusicGen model...')
music_model = MusicGen.get_pretrained(config['music_model'], DEVICE)
music_model.set_generation_params(duration=config['BGM_duration'])

logging.info('Load whisper model...')
whisper_model = whisper.load_model(config['whisper_model'], DEVICE)

openai.api_key = config['openai']['api_key'] if config['openai']['api_key'] is not None else os.getenv("OPENAI_API_KEY")
logging.info('openai api key: ' + str(openai.api_key))

async def music_gen_pipline(prompt: str, voice: str=None):
    """
    Generate music by prompt.
    :param prompt: the prompt generated by GPT4.
    :return: the BGM generated by musicgen. the music will be warped by raw base64 text
    """
    logging.info('Music generation start')
    logging.info('music prompt: ' + prompt)
    t1 = time.time()
    if voice is None or 'melody' not in config['music_model']:
        wav = music_model.generate([prompt], True)
    else:
        logging.info('load ' + VOICE_PROMPT)
        melody, sr = torchaudio.load(VOICE_PROMPT)
        wav = music_model.generate_with_chroma([prompt], melody, sr, True)
    audio_write('./BGM_OUTPUT', wav.cpu()[0], music_model.sample_rate, strategy="loudness", loudness_compressor=True)
    with open('./BGM_OUTPUT.wav', 'rb') as f:
        tmp = f.read()
    logging.info('Music generated done. take {:.2f} sec.'.format(time.time() - t1))

    return base64.b64encode(tmp).decode('utf8')

def GPT4_pipline(img: str, voice_prompt: str=None):
    """
    Use GPT4 to generate img & music prompt or image's comment and description.
    :param img: base64 raw text. let GPT4 to generate.
    :param voice_prompt: if this is None, GPT4 will generate image's comment and description, else it will generate prompts.
    :return: prompts or image's comment and description.
    """
    if isinstance(img, tuple):
        return img

    openai_config = copy.deepcopy(config['openai'])

    if voice_prompt is not None: # use image and voice to generate prompt
        response_message = None
        for i in range(2):
            if response_message is None:
                response = openai.OpenAI().chat.completions.create(
                    model=openai_config['model'],
                    messages=[{"role": "user", "content": [{
                        'type': 'text',
                        'text': openai_config['img_and_voice_to_prompt'].format(voice=voice_prompt)}]
                               },{
                        'type': 'image_url',
                        'image_url': {
                          "url": f"data:image/png;base64,{img}"
                        }
                    }],
                    # functions=openai_config['functions_prompt']
                )
                response_message = response.choices[0].message.content
                logging.debug('GPT4: ' + response_message)


            try:
                tmp = json.loads(response_message)
                check = tmp['img_prompt'] and tmp['bgm_prompt']
                return tmp
            except:
                response = openai.OpenAI().chat.completions.create(
                    model=openai_config['model'],
                    messages=[{"role": "user", "content": [
                        {'type': 'text', 'text': openai_config['json_fix_prompt'] + response_message},
                        {'type': 'image_url', 'image_url': f"data:image/png;base64,{img}"}
                    ]}]
                )
                response_message = response.choices[0].message.content
                logging.debug('GPT4: ' + response_message)
                try:
                    return json.loads(response_message)
                except json.decoder.JSONDecodeError:
                    continue

        raise RuntimeError(f"GPT4 didn't generate legal prompt. prompt: {response_message}")
    else: # give img comment
        response_message = openai.OpenAI().chat.completions.create(
            model=openai_config['model'],
            messages=[{"role": "user", "content": [
                {'type': 'text', 'text': openai_config['img_to_comment']},
                {'type': 'image_url', 'image_url': f"data:image/png;base64,{img}"}]}]
        ).choices[0].message.content
        logging.debug('GPT4: ' + response_message)
        return response_message

async def DALL_E_pipline(prompt: str, img: str):
    sd_payload = copy.deepcopy(config['sd_payload'])
    sd_payload['prompt'] = sd_payload['prompt'] + prompt
    logging.info('dall-e prompt: ' + sd_payload['prompt'])

    img = Image.open(base64.b64decode(img))
    img.resize(min(*img.size), min(*img.size))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='png')

    t1 = time.time()
    response = openai.OpenAI().images.create_variation(
        model='dall-e-2',
        image=img_bytes.getvalue(),
        n=1,
        size='512x512'
    )

    try:
        logging.info('Image generated done. take {:.2f} sec.'.format(time.time() - t1))
        Image.open(io.BytesIO(base64.b64decode(response.data[0].url))).save('./IMAGE_OUTPUT.png')
        return response.data[0].url
    except Exception as e:
        return 'dall-e error!', (response, e)

async def stable_diffusion_pipline(prompt: str, img: str):
    """
    Generate img by sd.
    :param prompt: sd prompt.
    :param img: base img which warp by raw base64 text
    :return: generated img warp by raw base64 text
    """
    logging.info('Image generation start')
    url = "http://127.0.0.1:7860"
    sd_payload = copy.deepcopy(config['sd_payload'])
    sd_payload['prompt'] = sd_payload['prompt'] + prompt
    sd_payload['init_images'] = [img]
    logging.info('sd prompt: ' + sd_payload['prompt'])

    t1 = time.time()
    response = requests.post(url=f'{url}/sdapi/v1/img2img', json=sd_payload)


    if response.status_code == 200:
        r = response.json()
        logging.info('Image generated done. take {:.2f} sec.'.format(time.time() - t1))
        Image.open(io.BytesIO(base64.b64decode(r['images'][0]))).save('./IMAGE_OUTPUT.png')

        return r['images'][0]
    else:
        return 'stable diffusion error!', response

def save_config(key: Union[str, dict], value=None):
    """
    save config and reload model if necessary
    :param key: `dict` or `str`. `dict` will update config by `dict`, `str` will update config by key-value pair
    :param value: only work if `key` is `str`
    """
    global music_model, whisper_model
    if isinstance(key, str):
        tmp_dict = {key: copy.deepcopy(value)}
        if isinstance(value, dict) and isinstance(config[key], dict):
            config[key].update(value)
        else:
            config[key] = value
    else:
        tmp_dict = copy.deepcopy(key)
        for k, v in key.items():
            if isinstance(v , dict):
                config[k].update(v)
            else:
                config[k] = v

    with open(CONFIG_FILE, 'w') as f:
        f.write(json.dumps(config, indent=2))

    if isinstance(key, dict):
        key = key.keys()
    else:
        key = [key]

    if 'music_model' in key:
        music_model = MusicGen.get_pretrained(config['music_model'], DEVICE)
        gc.collect()
        torch.cuda.empty_cache()

    if 'BGM_duration' in key:
        music_model.set_generation_params(duration=config['BGM_duration'])

    if 'whisper_model' in key:
        whisper_model = whisper.load_model(config['whisper_model'], DEVICE)
        gc.collect()
        torch.cuda.empty_cache()

    if 'openai' in key and tmp_dict.get('openai', dict()).get('api_key', False):
        openai.api_key = config['openai']['api_key']