import openai

BRAND_STRATEGY_SYSTEM_PROMPT = 'I want you to act as a marketing expert for my company, please give me answers in quotations only and do not include any prefixes.'

def generate(prompt, max_tokens=1000, temperature=0.6):
    response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo', 
        messages=[
            {'role': 'system', 
             'content': 'I want you to act as a marketing expert for my company, please give me answers in quotations only and do not include any prefixes.'},
            {'role': 'user', 'content': prompt}
        ],
        max_tokens=max_tokens,
        temperature=temperature
    )
    result = response.choices[0].message.content.strip()
    return result


def english_teacher(prompt, max_tokens=1000, temperature=0.6):
    response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo', 
        messages=[
            {'role': 'system', 
             'content': 'I want you to act as an English teacher for a non-native Chinese student.'},
            {'role': 'user', 'content': prompt}
        ],
        max_tokens=max_tokens,
        temperature=temperature
    )
    result = response.choices[0].message.content.strip()
    return result


def _brand_strategy_(prompt):
    response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo', 
        messages=[
            {'role': 'system', 
             'content': BRAND_STRATEGY_SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt}
        ]
    )
    
    return response

def _build_base_prompt(inputs):
    product = inputs.get('product')
    strengths = inputs.get('strengths')
    differentiator = inputs.get('differentiator')
    target_audience = inputs.get('target_audience')

    prompt = f'''
    Below are the following information: 
    1. Product/Service: {product} 
    2. Strengths/USPs: {strengths} 
    3. Differentiation: {differentiator}
    4. Who are your target audiences: {target_audience}
    '''

    return prompt

def build_vision_statement_prompt(base_inputs, vision_type):
    base_prompt = _build_base_prompt(base_inputs)
    prompt = f'''
    Based on the above information, recommend only 1 {vision_type} company Vision & Mission statement, and explain in 150 words why
    '''
    prompt = base_prompt + prompt
    return prompt

def build_brand_positioning_prompt(base_inputs, positioning_type):
    base_prompt = _build_base_prompt(base_inputs)
    prompt = f'''
    Based on the above information, recommend 1 {positioning_type} brand positioning option, and provide a one liner in 5-6 words only to summarize, and explain in 150 words why
    '''
    prompt = base_prompt + prompt
    return prompt