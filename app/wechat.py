import requests
import json
import time
import os
import settings
import voice_assistant
import db
from db import cache
from fastapi import Response
from pydub import AudioSegment

APP_ID = settings.WECHAT_ADMIN_APPID
APP_SECRET = settings.WECHAT_ADMIN_SECRET
TOKEN_CACHE_KEY = settings.WECHAT_ADMIN_APPID + '_access_token'

def _refresh_token():
    """ IMPORTANT: This will fail if the server is not IP whitelisted """
    s = requests.Session()
    response = s.get('https://api.weixin.qq.com/cgi-bin/token', params={
        'grant_type': 'client_credential',
        'appid': APP_ID,
        'secret': APP_SECRET,
    }).json()
    cache.set(TOKEN_CACHE_KEY, response['access_token'], ex=60*60*1)
    return response['access_token']

class ChatBot:
    def __init__(self, username, db_session=None):
        self.username = username
        self.db_session = db_session
        self.state_cache_key = 'state:' + self.username
        self.attached_message_key = 'attached_msg:' + self.username
   
    def __repr__(self):
        return f'<ChatBot for {self.username}>'
    
    @property
    def access_token(self):
        return cache.get(TOKEN_CACHE_KEY)
    
    def _validate_message(self, message):
        # Check if the message XML is valid
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

    def _format_message(self, original_message, content):
         # Format the reply according to the WeChat XML format for synchronous replies,
        # see: http://admin.wechat.com/wiki/index.php?title=Callback_Messages
        return (
            "<xml>"
            "<ToUserName><![CDATA[%s]]></ToUserName>"
            "<FromUserName><![CDATA[%s]]></FromUserName>"
            "<CreateTime>%s</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[%s]]></Content>"
            "</xml>"
        ) % (
            original_message['xml']['FromUserName'],
            original_message['xml']['ToUserName'],
            time.gmtime(),
            content
        )
    
    @property
    def state(self):
        """ gets the state of the bot for a given user
        """
        return cache.get(self.state_cache_key)
    
    @state.setter
    def state(self, value):
        _ = cache.set(self.state_cache_key, value)

    @property
    def attached_message(self):
        return cache.get(self.attached_message_key)
    
    @attached_message.setter
    def attached_message(self, value):
        return cache.set(self.attached_message_key, value)

    def receive_message(self, message=None, media_id=None, msg_type='text'):
        with db.SessionLocal() as session:
            bot = db.get_or_create_user(session, 'bot')
            user = db.get_or_create_user(session, self.username)
            message = db.log_message(session, user, bot, content=message, media_id=media_id,msg_type=msg_type, source='user')
        return message

    def send_text_response(self, reply, original_message):
        """
        Send direct text response to user (not async)
        to_user: openid of the receiver
        
        """
        with db.SessionLocal() as session:
            user = db.get_or_create_user(session, self.username)
            system = db.get_or_create_user(session, 'system')
            resp = self._format_message(original_message, reply)
            db.log_message(session, system, user, content=reply, msg_type='text')
        self.state = 'listening'
        return Response(content=resp, status_code=200)

    def send_async_text_response(self, message, send_voice=False):
        with db.SessionLocal() as session:
            user = db.get_or_create_user(session, self.username)
            sender = db.get_or_create_user(session, 'bot')

            tries = 1
            # TODO: handle case after 3 unsuccessful attempts
            while tries <= 3:
                access_token = self.access_token
                url = 'https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token=%s' % (access_token, )
                data = {
                    'touser': self.username,
                    'msgtype':'text',
                    'text':
                    {
                        'content': message
                    }
                }
                headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
                response = requests.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf-8'), headers=headers).json()
                if response.get('errcode') == 0:
                    break
                else:
                    time.sleep(2)
                    tries += 1

            db.log_message(session, sender, user, content=message, msg_type='text')

        if send_voice:
            v_response = self.send_async_voice_response(message)

        return response

    def send_async_voice_response(self, message):
        audio_file = voice_assistant.text_to_speech(message)
        access_token = self.access_token
        upload_audio_url = f'https://api.weixin.qq.com/cgi-bin/media/upload?access_token={access_token}&type=voice'
        with open(audio_file, 'rb') as f:
            send_files = {'media': (audio_file, f, 'audio/mpeg')}
            response = requests.post(upload_audio_url, files=send_files)
        media_id = response.json().get('media_id')

        url = 'https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token=%s' % (access_token, )
        data = {
            'touser': self.username,
            'msgtype':'voice',
            'voice': {'media_id': media_id}
        }
        headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        response = requests.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf-8'), headers=headers)
        os.remove(audio_file)

        with db.SessionLocal() as session:
            user = db.get_or_create_user(session, self.username)
            sender = db.get_or_create_user(session, 'bot')
            db.log_message(session, sender, user, content=message, msg_type='voice', media_id=media_id)
        return response

    def send_busy_status(self):
        self.state = 'busy'
        access_token = self.access_token
        url = 'https://api.weixin.qq.com/cgi-bin/message/custom/typing?access_token=%s' % (access_token, )
        data = {
            'touser': self.username,
            'command': 'Typing'
        }
        headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        response = requests.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf-8'), headers=headers)
        return response

    def send_menu_message(self):
        access_token = self.access_token
        url = 'https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token=%s' % (access_token, )
        data = {
            'touser': self.username,
            'msgtype': 'msgmenu',
            'msgmenu': {
                'head_content': 'are you satisfied?',
                'list': [
                    {
                        'id': '101',
                        'content': 'yes'
                    },
                    {
                        'id': '102',
                        'content': 'no'
                    }
                ],
                'tail_content': 'Thanks!'
            }
        }

        headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        response = requests.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf-8'), headers=headers)
        return response

    def get_voice_message(self, media_id):
        access_token = self.access_token
        url = f'https://api.weixin.qq.com/cgi-bin/media/get?access_token={access_token}&media_id={media_id}'
        response = requests.get(url)
        amr_file = str(media_id) + '.amr'
        with open(amr_file, 'wb') as f:
            f.write(response.content)
        return voice_assistant.transcribe_audio(amr_file)