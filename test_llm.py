import openai
client = openai.OpenAI(api_key="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")
try:
    print(client.models.list())
    print("✅ Key is valid!")
except Exception as e:
    print(f"❌ Key failed: {e}")