import requests
import json
import time
import openai
import os
import voice_assistant

import settings
import db
from db import cache
from fastapi import Response

BOT_STATE_PREFIX = 'bot_state_'

def get_access_token(force_refresh=False):
    token = cache.get('wechat_token')
    if force_refresh or not token:
        s = requests.Session()

        response = s.get('https://api.weixin.qq.com/cgi-bin/token', params={
            'grant_type': 'client_credential',
            'appid': settings.WECHAT_ADMIN_APPID,
            'secret': settings.WECHAT_ADMIN_SECRET,
        }).json()
        token = response['access_token']
        cache.set('wechat_token', token, 6000)

    return token

def validate_message(message):
    # Check if the message XML is valid, this simple bot handles TEXT messages only!
    # To learn more about the supported types of messages and how to implement them, see:
    # Common Messages: http://admin.wechat.com/wiki/index.php?title=Common_Messages
    # Event Messages: http://admin.wechat.com/wiki/index.php?title=Event-based_Messages
    # Speech Recognition Messages: http://admin.wechat.com/wiki/index.php?title=Speech_Recognition_Messages
    return (
        message != None and
        message['xml'] != None and
        message['xml']['MsgType'] != None and
        message['xml']['MsgType'] == 'text' and
        message['xml']['Content'] != None
    )

# Format the reply according to the WeChat XML format for synchronous replies,
# see: http://admin.wechat.com/wiki/index.php?title=Callback_Messages
def format_message(original_message, content):
    return (
        "<xml>"
        "<ToUserName><![CDATA[%s]]></ToUserName>"
        "<FromUserName><![CDATA[%s]]></FromUserName>"
        "<CreateTime>%s</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        "<Content><![CDATA[%s]]></Content>"
        "</xml>"
    ) % (
        original_message['xml']['FromUserName'], # From and To must be inverted in replies ;)
        original_message['xml']['ToUserName'], # Same as above!
        time.gmtime(),
        content
    )

def send_direct_text_response(session, to_user, reply, original_message, next_state='listening'):
    """
    to_user: openid of the receiver
    
    """
    bot_state_key = BOT_STATE_PREFIX + to_user
    user = db.get_or_create_user(session, to_user)
    system = db.get_or_create_user(session, 'system')
    resp = format_message(original_message, reply)
    db.log_message(session, system, user, content=reply, msg_type='text')
    if next_state:
        cache.set(bot_state_key, next_state)
    return Response(content=resp, status_code=200)

def send_async_text_response(message, to_user, from_user='assistant', send_voice=True):
    session = db.SessionLocal()
    user = db.get_or_create_user(session, to_user)
    sender = db.get_or_create_user(session, from_user)

    access_token = get_access_token()
    url = 'https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token=%s' % (access_token, )
    data = {
        'touser': to_user,
        'msgtype':'text',
        'text':
        {
            'content': message
        }
    }
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    response = requests.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf-8'), headers=headers)
    print('Send msg response', response.json())

    db.log_message(session, sender, user, content=message, msg_type='text')

    if voice_assistant.has_english(message) and send_voice:
        text = voice_assistant.prepare_text(message)
        audio_file = voice_assistant.text_to_speech(text)
        voice_send_response = send_async_voice_response(audio_file, to_user)
        print(voice_send_response)

    session.close()
    bot_state_key = BOT_STATE_PREFIX + to_user 
    cache.set(bot_state_key, 'listening')
    return response

def send_async_voice_response(audio_file, to_user):
    access_token = get_access_token()
    upload_audio_url = f'https://api.weixin.qq.com/cgi-bin/media/upload?access_token={access_token}&type=voice'
    with open(audio_file, 'rb') as f:
        send_files = {'media': (audio_file, f, 'audio/mpeg')}
        response = requests.post(upload_audio_url, files=send_files)
    media_id = response.json().get('media_id')

    url = 'https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token=%s' % (access_token, )
    data = {
        'touser': to_user,
        'msgtype':'voice',
        'voice': {'media_id': media_id}
    }
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    response = requests.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf-8'), headers=headers)
    return response

openai.api_key = settings.OPENAI_API_KEY  # supply your API key however you choose

from pydub import AudioSegment
from hanziconv import HanziConv

def get_voice_message(media_id):
    access_token = get_access_token()
    url = f'https://api.weixin.qq.com/cgi-bin/media/get?access_token={access_token}&media_id={media_id}'
    response = requests.get(url)
    with open('sample.amr', 'wb') as f:
        f.write(response.content)

    amr_audio = AudioSegment.from_file('sample.amr', format='amr')
    mp3_audio = amr_audio.export('sample.mp3', format='mp3')
    transcript = openai.Audio.transcribe('whisper-1', mp3_audio)
    text = transcript.get('text')
    simplified = HanziConv.toSimplified(text)
    print(simplified)
    return simplified

INTRO_MESSAGE = """你好！我是 Bella，你的私人英语助手，帮你理解日常生活中遇到的任何有关英语的问题。你可以使用菜单下的功能：

[翻译解释] - 我帮你翻译或者解释某个英文词或句子
[英文表达] - 我来教你用英文表达某句中文话
[教我相关词] - 我会教你一句跟你之前问过相关的英语短语
[用语音重复] - 我用语音重复我最近发给你的信息

并且你可以直接问我问题， 比如:
1. bite the bullet 是什么意思?
2. 怎么用英文说 "我这几天有点不舒服，明天可能来不了你的家"?
3. 解释一下这句话: I\'m looking forward to our meeting tomorrow.

你有什么关于英语的问题吗?"""


def update_menu():
    access_token = get_access_token()
    data = {
        'button': [
             {
                'name': '功能介绍',
                'type': 'click',
                'key': 'tutorial'
            },
            {
                'name': '功能',
                'sub_button': [
                    {
                        'name': '翻译解释',
                        'type': 'click',
                        'key': 'explain'
                    },
                    {
                        'name': '英文表达',
                        'type': 'click',
                        'key': 'english_equivalent'
                    },
                    {
                        'name': '教我相关词',
                        'type': 'click',
                        'key': 'similar'
                    },
                    {
                        'name': '用语音重复',
                        'type': 'click',
                        'key': 'voice'
                    }
                ]
            }
		]
	}

    url = f'https://api.weixin.qq.com/cgi-bin/menu/create?access_token={access_token}'
    response = requests.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf-8')).text
    return response


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

def text_to_speech(message, model='zh-CN-XiaomoNeural'):
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
        print(response.json())
        if response.json().get('converted'):
            job_done = True
            audio_file = response.json().get('audioUrl')
        else:
            time.sleep(3)

    response = requests.get(audio_file)

    filename = transcription_id + '.mp3'

    with open(filename, 'wb') as f:
        f.write(response.content)

    return filename


def repeat_with_voice(from_user, content):
    audio_file = text_to_speech(content)
    access_token = get_access_token()
    upload_audio_url = f'https://api.weixin.qq.com/cgi-bin/media/upload?access_token={access_token}&type=voice'
    with open(audio_file, 'rb') as f:
        send_files = {'media': ('generated.mp3', f, 'audio/mpeg')}
        response = requests.post(upload_audio_url, files=send_files)
    media_id = response.json().get('media_id')

    url = 'https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token=%s' % (access_token, )
    data = {
        'touser': from_user,
        'msgtype':'voice',
        'voice': {'media_id': media_id}
    }
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    response = requests.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf-8'), headers=headers)
    session = db.SessionLocal()
    user = db.get_or_create_user(session, from_user)
    system = db.get_or_create_user(session, 'system')
    db.log_message(session, system, user, media_id=media_id, msg_type='voice')
    session.close()
    bot_state_key = BOT_STATE_PREFIX + from_user
    cache.set(bot_state_key, 'listening')
    os.remove(audio_file)
    return response