import base64
import json
import os
import openai

import requests
from audiocraft.models import MusicGen
from audiocraft.data.audio import audio_write

with open('./config.json', 'r') as f:
    config = json.loads(f.read())

music_model = MusicGen.get_pretrained(config['music_model'])
music_model.set_generation_params(duration=config['BGM_duration'])

sd_payload = config['sd_payload']
openai.api_key = os.getenv("OPENAI_API_KEY") if os.getenv("OPENAI_API_KEY") is None else config['openai']['api_key']

async def music_gen_pipline(prompt: str):
    """
    Generate music by prompt.
    :param prompt: the prompt generated by GPT4.
    :return: the BGM generated by musicgen. the music will be warped by raw base64 text
    """
    wav = music_model.generate([prompt])
    audio_write('./BGM_OUTPUT', wav.cpu()[0], music_model.sample_rate, strategy="loudness", loudness_compressor=True)
    with open('./BGM_OUTPUT.wav', 'rb') as f:
        tmp = f.read()
    print('Music generated done.')

    return base64.b64encode(tmp).decode('utf8')

def GPT4_pipline(img: str, voice_prompt: str=None):
    """
    Use GPT4 to generate img & music prompt or image's comment and description.
    :param img: base64 raw text. let GPT4 to generate.
    :param voice_prompt: if this is None, GPT4 will generate image's comment and description, else it will generate prompts.
    :return: prompts or image's comment and description.
    """
    # TODO: 我去翻了openai的doc，我沒看到gpt4 with vision的api,所以我需要有人幫我找找這vision版具體怎麼用
    # 他好像是要先花錢排隊，等openai寄信給你你才能用的樣子
    openai_config = config['openai']

    if voice_prompt is not None: # use image and voice to generate prompt
        response_message = None
        for i in range(2):
            if response_message is None:
                response = openai.ChatCompletion.create(
                    model=openai_config['model'],
                    messages=[{"role": "user", "content": openai_config['img_and_voice_to_prompt'] + voice_prompt}],
                    functions=[
                        {
                            "name": "get_sd_and_musicgen_prompt",
                            "description": "use key word to describe a image to make stable diffusion be able to generate image"
                                           " and make music generator be able to generate music.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "img_prompt": {
                                        "type": "string",
                                        "description": "describe the image like: \"little dog, gray skin, big eyes, looking at viewer\", etc."
                                    },
                                    "bgm_prompt": {
                                        "type": "string",
                                        "description": "describe the music like: \"a light and cheerly EDM track, with syncopated drums, aery pads, and strong emotions bpm: 130\", etc."
                                    },
                                },
                                "required": ["img_prompt", "bgm_prompt"],
                            },
                        }
                    ]
                )
                response_message = response["choices"][0]["message"]

            if response_message.get("function_call"):
                try:
                    return json.loads(response_message["function_call"]["arguments"])
                except json.decoder.JSONDecodeError:
                    response = openai.ChatCompletion.create(
                        model=openai_config['model'],
                        messages=[{"role": "user", "content": "Complete the json syntax errors in the following text according to the legal json format."
                                                              "You don't need to say any thing except the json.\n" + response_message["function_call"]["arguments"]}]
                    )
                    response_message = response["choices"][0]["message"]
                    try:
                        return json.loads(response_message["function_call"]["arguments"])
                    except json.decoder.JSONDecodeError:
                        continue

        raise RuntimeError(f"GPT4 didn't generate legal prompt. prompt: {response_message['function_call']}")
    else: # give img comment
        return openai.ChatCompletion.create(
            model=openai_config['model'],
            messages=[{"role": "user", "content": openai_config['img_to_comment']}],
        )["choices"][0]["message"]['content']

async def stable_diffusion_pipline(prompt: str, img: str):
    """
    Generate img by sd.
    :param prompt: sd prompt.
    :param img: base img which warp by raw base64 text
    :return: generated img warp by raw base64 text
    """
    url = "http://127.0.0.1:7860"

    sd_payload['prompt'] = prompt
    sd_payload['init_images'].append(img)

    response = requests.post(url=f'{url}/sdapi/v1/img2img', json=sd_payload)

    r = response.json()
    print('Image generated done.')

    return r['images'][0]