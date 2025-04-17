from pprint import pprint

import openai

from senor_bot.config import settings

openai.api_key = settings.tokens.gpt
response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
        {
            "role": "user",
            "content": "Can 'Something approaching fascism' be considered a response to the question 'What is the governmental system in Canada?'",
        },
    ],
)
print(response)
print("********")
print("Response from GPT-3 Turbo:", response.choices[0].message.content.strip())
print(
    "Response from GPT-3 Turbo:", "yes" in response.choices[0].message.content.strip()
)
