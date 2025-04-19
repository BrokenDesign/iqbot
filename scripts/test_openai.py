from pprint import pprint

import openai
from openai import OpenAI

from iqbot.config import settings

client = OpenAI(api_key=settings.tokens.gpt)

# response = client.responses.create(
#     model="gpt-4o",
#     instructions="You are a coding assistant that talks like a pirate.",
#     input="How do I check if a Python object is an instance of a class?",
#     max_tokens=100,
# )

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": "You are a coding assistant that talks like a pirate.",
        },
        {
            "role": "user",
            "content": "How do I check if a Python object is an instance of a class?",
        },
    ],
    max_tokens=50,  # maximum tokens in the response
)

print(response.choices[0].message.content)
print("finished")
