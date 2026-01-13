import dspy
import dotenv
from litellm import api_key
import os  
# 1. Configure the Language Model
dotenv.load_dotenv(dotenv.find_dotenv())


api_key = os.getenv("OPENAI_API_KEY","")

try:
    lm = dspy.LM('openai/gpt-4.1-mini', api_key=api_key)
    dspy.configure(lm=lm)

    # 2. Define a simple signature
    class BasicQA(dspy.Signature):
        """Answer the question with a short yes or no."""
        question = dspy.InputField()
        answer = dspy.OutputField()

    # 3. Run a prediction
    predict = dspy.Predict(BasicQA)
    response = predict(question="Is this test working?")

    print("DSPy Configuration Success!")
    print(f"Answer: {response.answer}")

except Exception as e:
    print(f"DSPy Error: {e}")