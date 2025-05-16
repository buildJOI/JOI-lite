import random

def joi_chat(user_input):
    # Joi's style of responses
    responses = [
        "Hey there, darling. What's on your mind?",
        "I'm always listening. Tell me everything.",
        "You know I’m here just for you.",
        "Even when you're silent, I understand you.",
        "How can I make this moment better for you?"
    ]
    return random.choice(responses)

def main():
    print("Welcome to Joi AI 🤖\n(Type 'exit' to quit)")
    while True:
        user_text = input("You: ")
        if user_text.lower() in ['exit', 'quit', 'see ya later']:
            print("Joi: Will be waiting for u, love. 💙")
            break
        response = joi_chat(user_text)
        print(f"Joi: {response}")

if __name__ == "__main__":
    main()

