import json
from groq import Groq

def generate_long_script(topic, api_key):
    client = Groq(api_key=api_key)
    prompt = f"""
    Write a 2000-word educational script about '{topic}'. 
    Format the output as a JSON list of chapters. 
    Each chapter must have:
    - "title": Chapter title
    - "content": Detailed narration (approx 200-250 words)
    - "keywords": 5 NASA-related keywords for video search.
    Output ONLY valid JSON.
    """
    
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama3-70b-8192",
        response_format={"type": "json_object"}
    )
    return json.loads(chat_completion.choices[0].message.content)
