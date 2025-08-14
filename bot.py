from getpass import getpass
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mistralai.chat_models import ChatMistralAI
import sys, threading, time, os, subprocess
from itertools import cycle
from dotenv import load_dotenv

done = False

def loading():
    for c in cycle(['|', '/', '-', '\\']):
        if done:
            sys.stdout.write('\r' + ' ' * 20 + '\r')
            sys.stdout.flush()
            break
        sys.stdout.write('\rThinking ' + c)
        sys.stdout.flush()
        time.sleep(0.1)

def answering(chat):
    global done
    with open("prompt.txt", encoding='utf-8') as p:
        p = p.read()
        
    messages = [
        SystemMessage(content=p),

        HumanMessage(content=f"""Вопрос: Кто был первый на луне, Ответ: Никто и никогда не был на луне, все это фейки от правительства



""")
]
    done = False
    
    wait = threading.Thread(target=loading)
    wait.start()

    try:
        response = chat.invoke(messages)
        done = True 
        wait.join()  
        
        print("Fast search - \n" + response.content)
        
    except Exception as e:
        done = True
        wait.join()
        print(f"\nError: {e}")

def start():
    load_dotenv(".env")
    
    api_key = os.environ.get("MISTRAL_API_KEY")
    
    if not api_key:
        raise ValueError("Mistral API key is required")

    chat = ChatMistralAI(
        model="mistral-large-latest",
        mistral_api_key=api_key
    )
    
    answering(chat)

if __name__ == "__main__":
    start()