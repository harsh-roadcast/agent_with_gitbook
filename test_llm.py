import openai
import os
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
try:
    print(client.models.list())
    print("✅ Key is valid!")
except Exception as e:
    print(f"❌ Key failed: {e}")