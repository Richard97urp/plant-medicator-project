import os

from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, UnstructuredPDFLoader
from langchain_community.vectorstores.pgvector import PGVector
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document


load_dotenv()

loader = DirectoryLoader(
    os.path.abspath("C:/Users/Fytli/OneDrive/Escritorio/plant_medicator_venv/plant-medicator/pdf-books"),
    glob="**/*.pdf",
    use_multithreading=True,
    show_progress=True,
    max_concurrency=50,
    loader_cls=UnstructuredPDFLoader,
)
docs = loader.load()

embeddings = OpenAIEmbeddings(model='text-embedding-ada-002', )

text_splitter = SemanticChunker(
    embeddings=embeddings
)

#flattened_docs = [doc[0] for doc in docs if doc]
#flattened_docs = [doc.page_content for doc in docs if doc.page_content]
# Crear nuevamente objetos Document de cada contenido textual
flattened_docs = [Document(page_content=doc.page_content) for doc in docs if doc.page_content]


chunks = text_splitter.split_documents(flattened_docs)

PGVector.from_documents(
    documents=chunks,
    embedding=embeddings,
    collection_name="collection164",
    connection_string=f"postgresql+psycopg://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}",
    pre_delete_collection=True,
)