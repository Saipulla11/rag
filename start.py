from langchain.embeddings import HuggingFaceEmbeddings
from langchain.document_loaders import TextLoader
from langchain.vectorstores import FAISS
from dotenv import set_key
import subprocess

from langchain_text_splitters import RecursiveCharacterTextSplitter


print("""Список комманд:\n
      /start - Запуск бота
      /changekey - Смена ключа безопасности
      /update - Дополнить уже существующую бд
      /exit - Выход\n""")

s = input()


if s == "/start":
    print("Напишите ваш вопрос:")
    


elif s == "changekey":
    set_key(".env", "MISTRAL_API_KEY", input("Новый ключ - "))


elif s == "/exit":
    exit()

elif s == "/update":
    loader = TextLoader("test.txt", encoding="utf-8")
    documents = loader.load()  # загружает весь текст как один документ

    # 2. Разбиение на чанки
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,      # размер фрагмента (в символах)
        chunk_overlap=200,    # перекрытие между фрагментами
        separators=["\n\n", "\n", " ", ""]  # разделители
    )
    splits = text_splitter.split_documents(documents)

    # 3. Создание векторной БД (FAISS)
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
    vectorstore = FAISS.from_documents(splits, embeddings)
    vectorstore.save_local("faiss_index")  # сохраняем на диск

    print("TXT-файл успешно загружен в векторную БД!")


else:
    print("Неизвестная комманда")