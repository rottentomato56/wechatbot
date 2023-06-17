import os
import requests
import settings
import time
import re
import ffmpeg

# play.ht voice models for chinese

models = [
    'zh-CN_LiNaVoice',
    'zh-CN_ZhangJingVoice',
    'zh-CN-XiaoxiaoNeural',
    'zh-CN-XiaoyouNeural',
    'zh-CN-HuihuiRUS',
    'zh-CN-Yaoyao-Apollo',
    'zh-CN-XiaohanNeural',
    'zh-CN-XiaomoNeural',
    'zh-CN-XiaoruiNeural',
    'zh-CN-XiaoxuanNeural',
    'zh-CN-XiaoshuangNeural'
]

CHINESE_MODEL = 'zh-CN-XiaomoNeural'

def text_to_speech(message, model=CHINESE_MODEL):
    message = prepare_text(message)
    url = "https://play.ht/api/v1/convert"

    payload = {
        'content': [message],
        'voice': model,
        'globalSpeed': '90%'
    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "AUTHORIZATION": settings.VOICE_AI_API_KEY,
        "X-USER-ID": settings.VOICE_AI_USER_ID
    }

    response = requests.post(url, json=payload, headers=headers)

    transcription_id = response.json().get('transcriptionId')

    # poll for job success, eventually migrate this to webhook

    job_done = False
    url = f"https://play.ht/api/v1/articleStatus?transcriptionId={transcription_id}"

    headers = {
        "accept": "application/json",
        "AUTHORIZATION": settings.VOICE_AI_API_KEY,
        "X-USER-ID": settings.VOICE_AI_USER_ID
    }

    while not job_done:
        response = requests.get(url, headers=headers)
        if response.json().get('converted'):
            job_done = True
            audio_file = response.json().get('audioUrl')
            audio_duration = response.json().get('audioDuration')
            print(audio_duration, 'duration')
        else:
            time.sleep(2)

    response = requests.get(audio_file)

    filename = transcription_id + '.mp3'
    with open(filename, 'wb') as f:
        f.write(response.content)

    if audio_duration > 60:
        trimmed_filename = transcription_id.replace('-', '') + '_trimmed.mp3'
        stream = ffmpeg.input(filename)
        stream = ffmpeg.output(stream, trimmed_filename, t=59)
        stream = ffmpeg.overwrite_output(stream)
        ffmpeg.run(stream)
        os.remove(filename)
        return trimmed_filename

    return filename


def has_english(text):
    """ 
    Will return True or False depending on if the text contains more than 8 english words. 
    Use this condition to determine if it is necessary to convert the text to speech  
    """
    english_words = re.findall(r'\b[A-Za-z\-]+\b', text)
    return len(english_words) > 8

def prepare_text(text):
    english_sections = re.findall(r'\b[A-Za-z\s.,;!?\-]+\b', text)
    for section in english_sections:
        text = text.replace(section, f',{section},', 1)
    return text

def test():
    s = '你可以学习这个短语 "self-care"（自我关怀）来描述一个人照顾自己身心健康的行为和习惯。例如，你可以说 "Practicing self-care is important for maintaining a healthy lifestyle."（实施自我关怀对于保持健康的生活方式很重要）。这个短语可以帮助你学习如何照顾自己的身心健康，与"laughter is the best medicine" 相关。你可以学习这个短语 "self-care"（自我关怀）来描述一个人照顾自己身心健康的行为和习惯。例如，你可以说 "Practicing self-care is important for maintaining a healthy lifestyle."（实施自我关怀对于保持健康的生活方式很重要）。这个短语可以帮助你学习如何照顾自己的身心健康，与"laughter is the best medicine" 相关。你可以学习这个短语 "self-care"（自我关怀）来描述一个人照顾自己身心健康的行为和习惯。例如，你可以说 "Practicing self-care is important for maintaining a healthy lifestyle."（实施自我关怀对于保持健康的生活方式很重要）。这个短语可以帮助你学习如何照顾自己的身心健康，与"laughter is the best medicine" 相关。'
    return text_to_speech(s)


