import settings
import openai
from flask import Blueprint, request

openai.api_key = settings.OPENAI_API_KEY

marketing_app = Blueprint('marketing_app', __name__)

@marketing_app.route("/", methods=('GET', 'POST'))
def index():
    if request.method == "POST":
        text = request.form["text"]
        print(text)
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=text,
            temperature=0.6,
            max_tokens=1000
        )
        return redirect(url_for("index", result=response.choices[0].text))

    result = request.args.get("result")
    return render_template("index.html", result=result)


@marketing_app.route('/generate/captions', methods=['POST'])
def generate_captions():
    data = request.json

    inputs = {
        'platform': data['platform'],
        'post_topic': data['postTopic'],
        'target_audience': data['targetAudience'],
        'tone': data['captionTone'],
        'caption_length': data['captionLength'],
        'include_emojis': data['includeEmojis'],
        'include_hashtags': data['includeHashtags'],
        'num_captions': data['numCaptions'],
        'keywords': data['includedKeywords']
    }
    
    prompt = generate_social_media_prompt(inputs)

    response = get_captions(prompt)

    result = response.choices[0].message.content.strip()
    
    captions = []

    try:
        result = json.loads(result)
        for caption in result:
            if 'caption' in caption:
                captions.append(caption['caption'])
    except:
        return {'result': 'error'}

    return {'result': captions}

def generate_social_media_prompt(inputs):
    """
    user inputs:
    platform: Instagram, Twitter, Tiktok
    word limit: platform-specific
    target audience
    post topic, e.g. Volleyball serve training equipment
    keywords in post: Volleyball, training, equipment, serve
    tone: Professional, 
    caption length: Short/long
    emoji_use: Yes/no
    caption samples: 2
    call to action: true/false

    """

    
    POST_CHAR_LIMITS = {
        'instagram': 2200,
        'tiktok': 100,
        'twitter': 280,
        'facebook': 2200,
        'linkedin': 2200
    }
    
    platform = inputs.get('platform')
    if not inputs.get('keywords'):
        keywords = ''
    else:
        keywords = ', '.join(inputs.get('keywords').split(',')[:10])
    post_topic = inputs.get('post_topic')
    tone = inputs.get('tone')
    cta = inputs.get('cta')
    target_audience = inputs.get('target_audience')
    caption_length = inputs.get('caption_length')
    num_captions = inputs.get('num_captions')
    include_emojis = inputs.get('include_emojis')
    include_hashtags = inputs.get('include_hashtags')
    
    prompt = 'Create a valid JSON array of {num_captions} captions for {platform} about {post_topic}. For each caption, make sure to follow all directions listed below:'.format(platform=platform.capitalize(), post_topic=post_topic, num_captions=num_captions)
    
    prompt_instructions = [
        ('The number of characters for each caption must be under {char_limit} characters'.format(char_limit=POST_CHAR_LIMITS[platform]), True),
        ('My target audience is {target_audience}.'.format(target_audience=target_audience), target_audience),
        ('Try and use these keywords in the captions: {keywords}.'.format(keywords=keywords), len(keywords) > 0),
        ('Make the tone of voice of each caption to be {tone}.'.format(tone=tone), tone),
        ('I want a call to action to visit our website.', cta),
        ('I want each caption to be {caption_length}.'.format(caption_length=caption_length), True),
        ('Include a few emojis', include_emojis),
        ('Include a few hashtags', include_hashtags)
    ]
    
    list_num = 1
    for instruction, include_flag in prompt_instructions:
        if include_flag:
            prompt += '\n{list_num}. '.format(list_num=list_num) + instruction
            list_num += 1
            
    return prompt

def get_captions(prompt, max_tokens=1000, temperature=0.6):
    response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo', 
        messages=[
            {'role': 'system', 'content': 'You are a social media marketing expert.'},
            {'role': 'user', 'content': prompt}
        ]
    )    
    return response


def get_captions_debug(prompt, max_tokens=1000, temperature=0.6):
    print(prompt)
    
    start = time.time()
    response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo', 
        messages=[
            {'role': 'system', 'content': 'You are a social media marketing expert.'},
            {'role': 'user', 'content': prompt}
        ]
    )
    response_time = round(time.time() - start, 2)
    
    print('\n======================================\n')
    
    print('Model: gpt-turbo-3.5     Response time: %s s     Total tokens used: %s'  % (response_time, response['usage']['total_tokens']))
    print('\n')
    print(response.choices[0].message.content.strip())
    
    return response


@marketing_app.route('/brand-strategy', methods=['GET'])
def brand_strategy():
    return render_template('brand_strategy.html')

@marketing_app.route('/generate/vision', methods=['POST'])
def generate_vision_statement():
    data = request.json

    inputs = {
        'product': 'Clothing',
        'strengths': 'unique and affordable',
        'differentiator': 'I think our unique design',
        'target_audience': 'Men and women who love streetwear or fashion'
    }

    vision_type = data.get('vision_type')
    
    prompt = prompts.build_vision_statement_prompt(inputs, vision_type)
    print(prompt)
    result = prompts.generate(prompt)
    print(result)
    return {'result': result}


@marketing_app.route('/generate/positioning', methods=['POST'])
def generate_brand_positioning():
    data = request.json

    inputs = {
        'product': 'Clothing',
        'strengths': 'unique and affordable',
        'differentiator': 'I think our unique design',
        'target_audience': 'Men and women who love streetwear or fashion'
    }

    positioning_type = data.get('positioning_type')
    
    prompt = prompts.build_brand_positioning_prompt(inputs, positioning_type)
    print(prompt)
    result = prompts.generate(prompt)
    print(result)
    return {'result': result}


@marketing_app.route('/prompt', methods=['POST'])
def get_response():
    prompt = request.json.get('prompt')
    result = prompts.english_teacher(prompt)
    return {'result': result}