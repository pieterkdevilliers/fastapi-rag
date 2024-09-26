
# from langchain.document_loaders import DirectoryLoader
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
# from langchain.embeddings import OpenAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
import openai 
from dotenv import load_dotenv
import os
import shutil


load_dotenv()

openai.api_key = os.environ['OPENAI_API_KEY']

CHROMA_PATH = "chroma"
DATA_PATH = "data/"
BATCH_SIZE = 5461


def main():
    """
    Generate a data store from the documents in the data directory.
    """
    generate_data_store()


def generate_data_store():
    """
    Generate a data store from the documents in the data directory.
    """
    documents = load_documents()
    chunks = split_text(documents)
    save_to_chroma_in_batches(chunks)


def load_documents():
    """
    Load the documents from the data directory.
    """
    loader = DirectoryLoader(DATA_PATH, glob="*.md")
    print(f"Loading documents from {DATA_PATH}.")
    documents = loader.load()
    print(f"Loaded {len(documents)} documents.")
    return documents


def split_text(documents: list[Document]):
    """
    Split the text into chunks.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=500,
        length_function=len,
        add_start_index=True,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split {len(documents)} documents into {len(chunks)} chunks.")

    document = chunks[10]
    print(document.page_content)
    print(document.metadata)

    return chunks


def batch(iterable, n=BATCH_SIZE):
    """
    Helper function to split a list into batches of size n.
    """
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]


def save_to_chroma_in_batches(chunks: list[Document]):
    """
    Save the chunks to the Chroma database in batches.
    """
    # Clear out the database first.
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)

    # Iterate over chunks in batches and save each batch
    embeddings = OpenAIEmbeddings()

    for chunk_batch in batch(chunks):
        db = Chroma.from_documents(
            chunk_batch, embeddings, persist_directory=CHROMA_PATH
        )
        db.persist()  # Persist the database after every batch
        print(f"Saved {len(chunk_batch)} chunks to {CHROMA_PATH}.")


if __name__ == "__main__":
    main()

# load_documents()
split_text(load_documents())
