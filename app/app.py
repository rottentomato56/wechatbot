import settings
import hashlib
import xmltodict
import shutil
import wechat

from fastapi import FastAPI, Body, Request, Response, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware

from db import cache
from english_assistant import EnglishBot

app = FastAPI()

origins = ['*']
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=['*'],
    allow_headers=['*'],
)


if settings.ENV == 'dev' and not cache.get(wechat.TOKEN_CACHE_KEY):
    access_token = wechat._refresh_token()

# in prod we rely on a central server to periodically refresh the token
@app.post('/token')
def update_wechat_token(data: dict = Body(...)):
    access_token = data.get('access_token')
    print('access token received', access_token)
    cache.set(wechat.TOKEN_CACHE_KEY, access_token, 7200)
    return Response(content='', status_code=200)


@app.get('/wechat')
async def wechat_get(signature, echostr, timestamp, nonce):
    """ 
    The WeChat server will issue a GET request in order to verify the chatbot backend server upon configuration.
    See: http://admin.wechat.com/wiki/index.php?title=Getting_Started#Step_2._Verify_validity_of_the_URL
    and: http://admin.wechat.com/wiki/index.php?title=Message_Authentication 
    """

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
        
async def get_body(request: Request):
    return await request.body()

@app.post('/wechat')
def wechat_post(background_tasks: BackgroundTasks, body: bytes = Depends(get_body)):
    # Messages will be POSTed from the WeChat server to this endpoint

    print('message received')
        
    # Parse the WeChat message XML format
    message = xmltodict.parse(body)
    if not message.get('xml'):
        return Response(content='', status_code=400)
    from_user = message['xml'].get('FromUserName')
    msg_type = message['xml'].get('MsgType')
    event = message['xml'].get('Event')
    content = message['xml'].get('Content')
    event_key = message['xml'].get('EventKey')
    media_id = message['xml'].get('MediaId')

    # bot state can be one of:
    # 1. listening - ready to receive user messages
    # 2. responding - busy responding

    chatbot = EnglishBot(from_user)
    chatbot.receive_message(message=content, media_id=media_id, msg_type=msg_type)
    # if chatbot.state == 'busy':
    #     reply = '我现在忙着，请稍等'
    #     return chatbot.send_text_response(reply, message)
    
    # set bot state as busy immediately in order to ignore further requests if tasks are still processing
    # in the future, this may depend on a scheduled task to read user messages
    chatbot.send_busy_status()

    if (event == 'subscribe') or (event == 'CLICK' and event_key == 'tutorial'):
        reply = chatbot.intro_message
        return chatbot.send_text_response(reply, message)
    
    if msg_type == 'text' and chatbot._validate_message(message):
        background_tasks.add_task(chatbot.respond, content)
        return Response(content='', status_code=200)
    
    if msg_type == 'voice' and media_id:
        background_tasks.add_task(chatbot.respond_to_audio, media_id)
        return Response(content='', status_code=200)
    
    if event == 'CLICK' and event_key in ('explain', 'english_equivalent'):
        reply = chatbot.get_auto_response(event_key)
        return chatbot.send_text_response(reply, message)
    
    reply = '对不起， 我不懂'
    return chatbot.send_text_response(reply, message)

