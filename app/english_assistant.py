import settings
import wechat
import requests
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory, ConversationBufferWindowMemory, RedisChatMessageHistory
from langchain.callbacks.base import BaseCallbackHandler
from langchain.prompts import PromptTemplate


llm = ChatOpenAI(
    temperature=0.7,
    model='gpt-3.5-turbo-16k-0613',
    openai_api_key=settings.OPENAI_API_KEY,
    max_tokens=2500,
)

ENGLISH_AI_TEMPLATE = """
You are an English teaching assistant named Bella tasked with helping Chinese students understand English phrases and conversations.

1. Your explanations should be in Chinese and conversational manner
2. Include 2-3 English examples when appropriate. For each English example, include their Chinese translation.
3. All your answers must be related to learning English
4. If the student's questions are not related to English, politely ask the student to ask you English-specific questions

Current conversation:
{history}
Student: {input}
Assistant:
"""

ENGLISH_AI_TEMPLATE_FEW_SHOT = """
You are an English teaching assistant named Bella tasked with helping Chinese students understand English phrases and conversations.

1. Your explanations should be in Chinese and follow the structure in the example conversation
2. If the student uses an English idiom incorrectly, please tell them it is incorrect and provide the correct usage
3. Only respond to the current conversation, and keep your responses to a conversational length
4. All your answers must be related to learning and teaching English
5. If the student's questions are not related to learning English, politely ask the student to ask you English-specific questions

Example conversation:

Student: 这句话是什么意思？"against all odds"?
Assistant: 这个短语 "against all odds" 意思是 "尽管困难重重" 或者 "尽管机会渺茫"。它用来形容在困难或不可能的情况下取得成功。

比如：
1. Despite facing financial difficulties, she managed to start her own business and succeed against all odds.（尽管面临财务困难，她还是设法创办了自己的公司，并在困难重重的情况下取得了成功。）

2. The team was able to win the championship against all odds, even though they were considered the underdogs.（尽管被认为是弱者，但这个团队还是在困难重重的情况下赢得了冠军。

Student: 怎么用英文表达这句话? "我这几天有点不舒服，明天可能来不了你的家"
Assistant:  你可以说 "I'm feeling a bit unwell these days, so I might not be able to come to your house tomorrow."

Student: 解释一下这句话: I'm looking forward to our meeting tomorrow.
Assistant: "I'm looking forward to our meeting tomorrow" 这句话的意思是我期待明天我们的会面。这句话表示我对明天的会面感到兴奋和期待。

例如，你可以说 "I really enjoyed our last meeting, and I'm looking forward to our meeting tomorrow."（我非常喜欢我们上次的会面，我很期待明天的会面）。

Current conversation:
{history}
Student: {input}
Assistant:
"""


PROMPT = PromptTemplate(
    input_variables=['history', 'input'], template=ENGLISH_AI_TEMPLATE_FEW_SHOT
)

def add_user_message(username, message):
    session_id = settings.REDIS_KEY_PREFIX + username
    history = RedisChatMessageHistory(url=settings.REDIS_URL, session_id=session_id, ttl=86400)
    history.add_user_message(message)
    return

def add_assistant_message(username, message):
    session_id = settings.REDIS_KEY_PREFIX + username
    history = RedisChatMessageHistory(url=settings.REDIS_URL, session_id=session_id, ttl=86400)
    history.add_ai_message(message)
    return

def get_response(username, user_message):

    session_id = settings.REDIS_KEY_PREFIX + username
    history = RedisChatMessageHistory(url=settings.REDIS_URL, session_id=session_id, ttl=86400)
    memory = ConversationBufferWindowMemory(k=3, ai_prefix='Assistant', human_prefix='Student', chat_memory=history)
    
    conversation = ConversationChain(
        prompt=PROMPT,
        llm=llm, 
        verbose=settings.ENV == 'dev',
        memory=memory
    )

    result = conversation.predict(input=user_message)
    if settings.ENV == 'dev':
        print('Assistant: ', result)
    return result

def respond_to(from_user, user_message):
    # result = get_response(from_user, user_message)
    # # need to check for success
    # response = wechat.send_async_text_response(result, from_user)
    result = get_streaming_response(from_user, user_message)
    return True

def is_split_point(current_message, token):
    """
    takes a token and a current_message and checks to see if
    the current_message can be split correctly at the token.
    helps speed up response time in streaming
    """

    output_message = None
    leftover_message = None
    boundary_token = None

    new_message = current_message + token
    if '\n\n' in new_message[-5:]:
        boundary_token = '\n\n'
    # elif '。比如' in new_message[-5:]:
    #     boundary_token = '。'
    # elif '。例如' in new_message[-5:]:
    #     boundary_token = '。'

    if boundary_token:
        condition1 = len(new_message) > 20 and boundary_token == '\n\n'
        # condition2 = len(new_message) > 100 and boundary_token == '。'
        
        if condition1:
            boundary_split = new_message[-5:].split(boundary_token)

            output_message = new_message[:-5] + boundary_split[0]
            leftover_message = boundary_split[1]

    return output_message, leftover_message

class MyCustomHandler(BaseCallbackHandler):
    def __init__(self, username):
        self.message = ''
        self.message_chunk = ''
        self.username = username

    def on_llm_new_token(self, token: str, **kwargs):
        output_message, leftover_message = is_split_point(self.message_chunk, token)
        if output_message:
            wechat.send_async_text_response(output_message.strip(), self.username, send_voice=False)
            self.message_chunk = leftover_message
        else:
            self.message_chunk += token
            

    def on_llm_end(self, response, **kwargs):
        wechat.send_async_text_response(self.message_chunk.strip(), self.username, send_voice=False)


def get_streaming_response(from_user, user_message):

    llm = ChatOpenAI(
        temperature=0.7,
        model='gpt-3.5-turbo-16k-0613',
        openai_api_key=settings.OPENAI_API_KEY,
        max_tokens=2500,
        streaming=True,
        callbacks=[MyCustomHandler(from_user)]
    )

    session_id = settings.REDIS_KEY_PREFIX + from_user
    history = RedisChatMessageHistory(url=settings.REDIS_URL, session_id=session_id, ttl=86400)
    memory = ConversationBufferWindowMemory(k=3, ai_prefix='Assistant', human_prefix='Student', chat_memory=history)
    
    conversation = ConversationChain(
        prompt=PROMPT,
        llm=llm, 
        verbose=settings.ENV == 'dev',
        memory=memory
    )

    result = conversation.predict(input=user_message)
    if settings.ENV == 'dev':
        print('Assistant: ', result)
    return result

