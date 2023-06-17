import settings
import hashlib
import xmltodict
import re
from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from langchain.memory import RedisChatMessageHistory

import wechat
import english_assistant
import db
from db import cache

app = FastAPI()

class UserMessage(BaseModel):
    content: str
    user_id: int
    timestamp: int = None

@app.post('/chat')
async def chat(user_message: UserMessage):
    user_id = user_message.user_id
    print(user_message)

    history = RedisChatMessageHistory(url=settings.REDIS_URL, session_id=str(user_id), ttl=86400)
    history.add_user_message(user_message.content)
    # kick off background task to process messages
    # delay by 5 seconds
    print(history.messages)
    raise

    # response = chatbot(conversation)
    # history.add_ai_message(response.content)
    # return jsonify({'response': response.content})


############ chatbot functions ###################

# The WeChat server will issue a GET request in order to verify the chatbot backend server upon configuration.
# See: http://admin.wechat.com/wiki/index.php?title=Getting_Started#Step_2._Verify_validity_of_the_URL
# and: http://admin.wechat.com/wiki/index.php?title=Message_Authentication

# Dependency
def get_session():
    session = db.SessionLocal()
    try:
        yield session
    finally:
        session.close()

@app.get('/wechat')
async def wechat_get(signature, echostr, timestamp, nonce):
    # Compute the signature (note that the shared token is used too)
    verification_elements = [settings.WECHAT_BOT_TOKEN, timestamp, nonce]
    verification_elements.sort()
    verification_string = "".join(verification_elements)
    verification_string = hashlib.sha1(verification_string.encode('utf-8')).hexdigest()

    # If the signature is correct, output the same "echostr" provided by the WeChat server as a parameter
    if signature == verification_string:
        return Response(content=echostr)
    else:
        return HTTPException(status_code=401)
        

@app.post('/wechat')
async def wechat_post(request: Request, background_tasks: BackgroundTasks, session=Depends(get_session)):
    # Messages will be POSTed from the WeChat server to this endpoint
        
    # Parse the WeChat message XML format
    body = await request.body()
    
    message = xmltodict.parse(body)
    from_user = message['xml']['FromUserName']
    msg_type = message['xml']['MsgType']
    event = message['xml'].get('Event')
    content = message['xml'].get('Content')
    event_key = message['xml'].get('EventKey')

    bot_state_key = 'bot_state_' + from_user

    last_msg_key ='last_msg_' + from_user
    last_msg = cache.get(last_msg_key)

    # bot state can be one of:
    # 1. listening - ready to receive general responses
    # 2. responding - busy responding
    # 3. waiting_to_explain - waiting for user input to explain following english input
    # 4. waiting_to_pronounce - waiting for user input to pronounce following english input

    if cache.get(bot_state_key) == 'responding':
        reply = '我现在忙着，请稍等'
        return wechat.send_direct_text_response(session, from_user, reply, message)
    
    # set bot state as responding immediately in order to ignore further requests if tasks are still processing
    # in the future, this may depend on a scheduled task to read user messages
    v = cache.set(bot_state_key, 'responding', ex=86400)

    user = db.get_or_create_user(session, from_user)

    if event == 'subscribe':
        reply = wechat.INTRO_MESSAGE
        return wechat.send_direct_text_response(session, from_user, reply, message)
    
    if event == 'CLICK' and event_key == 'tutorial':
        reply = wechat.INTRO_MESSAGE
        return wechat.send_direct_text_response(session, from_user, reply, message)
    
    if msg_type == 'text' and wechat.validate_message(message):
        assistant = db.get_or_create_user(session, 'assistant')
        db.log_message(session, user, assistant, content=content, msg_type='text')
        reply = '稍等...'
        # kickoff async task

        if last_msg:
            content = f'{last_msg} "{content}"'
            cache.delete(last_msg_key)
        background_tasks.add_task(english_assistant.respond_to, from_user, content)
        return wechat.send_direct_text_response(session, from_user, reply, message, next_state=False)
    
    if event == 'CLICK' and event_key == 'explain':
        attach_message = '这句话是什么意思?'
        cache.set(last_msg_key, attach_message)
        reply = '[帮我解释下面这个英文句子]\n\n好的，你要我解释什么英文句子？直接发给我就行了'
        return wechat.send_direct_text_response(session, from_user, reply, message)
    
    if event == 'CLICK' and event_key == 'english_equivalent':
        attach_message = '怎么用英文表达这句话?'
        cache.set(last_msg_key, attach_message)
        reply = '[怎么用英文表达下面这个句话?]\n\n你想用英文表达什么话？直接发我中文句子就行了'
        return wechat.send_direct_text_response(session, from_user, reply, message)
    
    if event == 'CLICK' and event_key == 'voice':
        system = db.get_or_create_user(session, 'system')
        latest_message = db.get_latest_received_message(session, user)
        if not latest_message or not latest_message.content or len(latest_message.content) < 5 or latest_message.sender_id == system.id:
            reply = '对不起，没有话需要用语音重复。你有任何关于英文的问题吗?'
            return wechat.send_direct_text_response(session, from_user, reply, message)
        
        reply = '稍等，我来用语音重复一遍'
        background_tasks.add_task(wechat.repeat_with_voice, from_user, latest_message.content)
        return wechat.send_direct_text_response(session, from_user, reply, message, next_state=False)
    
    if event == 'CLICK' and event_key == 'similar':
        reply = '[教我一句相关的英文]\n\n好的，让我想想一句相关的英文词或句子...'
        user_request = '教我一个跟最近问的相关的英文词或句子'
        background_tasks.add_task(english_assistant.respond_to, from_user, user_request)
        cache.delete(last_msg_key)
        return wechat.send_direct_text_response(session, from_user, reply, message, next_state=False)
    
    
    reply = '对不起， 我不懂'
    return wechat.send_direct_text_response(session, from_user, reply, message)


# @app.post('/voice')
# async def voice_webhook(request: Request, background_tasks: BackgroundTasks, session=Depends(get_session)):
#     print(request)
#     return Response(content='', status_code=200)