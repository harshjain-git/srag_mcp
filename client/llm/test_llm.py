import os

from dotenv import load_dotenv

from client.llm.factory import get_llm


load_dotenv()


def main():
    provider = os.getenv("LLM_PROVIDER", "gemini")

    print(f"Testing provider: {provider}")

    llm = get_llm(provider)

    response = llm.generate(
        [
            {
                "role": "user",
                "content": "What is 2 + 2? Answer in one sentence.",
            }
        ]
    )

    print("\nLLM response:")
    print(response)


if __name__ == "__main__":
    main()

