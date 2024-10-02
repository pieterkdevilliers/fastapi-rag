import os
import shutil
import openai
import asyncio  # Import asyncio
from docx import Document as DocxDocument
import PyPDF2
import pypandoc
import markdown
# from langchain_community.document_loaders import DirectoryLoader
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from sqlalchemy.sql import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
from file_management.models import SourceFile
from db import async_engine

# Create a sessionmaker for the async session
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_async_session() -> AsyncSession:
    """
    Get Async Session
    """
    session = AsyncSessionLocal()  # Create a new session instance
    try:
        yield session  # Yield the session
    finally:
        await session.close()  # Ensure the session is closed after usage

load_dotenv()

openai.api_key = os.environ['OPENAI_API_KEY']

BATCH_SIZE = 5461


async def generate_chroma_db(account_unique_id, replace=False):
    """
    Generate a data store from the documents in the data directory.
    """
    print(f"Main called for {account_unique_id}.")
    
    # Get the session asynchronously
    async for session in get_async_session():  # Use async for instead of async with
        await generate_data_store(account_unique_id, replace, session)
    
    response = {"response": "success"}
    return response


async def generate_data_store(account_unique_id, replace, session: AsyncSession):
    """
    Generate a data store from the documents in the data directory.
    """
    print(f"Generating data store for account {account_unique_id}.")
    data_path = f"./files/{account_unique_id}"
    chroma_path = f"./chroma/{account_unique_id}"
    
    os.makedirs(chroma_path, exist_ok=True)
    
    documents = await load_documents(data_path, account_unique_id, session)
    chunks = await split_text(documents)
    await save_to_chroma_in_batches(chunks, chroma_path, replace)


# async def load_documents(data_path: str, account_unique_id: str, session: AsyncSession):
#     """
#     Load the documents from the data directory based on a database query.
#     """
#     statement = select(SourceFile).filter(
#         SourceFile.account_unique_id == account_unique_id,
#         SourceFile.included_in_source_data == True,
#         SourceFile.already_processed_to_source_data == False
#     )
#     result = await session.execute(statement)  # Use await here
#     documents_from_db = result.scalars().all()

#     documents = []
#     for db_file in documents_from_db:
#         file_path = os.path.join(data_path, db_file.file_name)
#         if os.path.exists(file_path):
#             with open(file_path, 'r') as file:
#                 content = file.read()
#                 documents.append(Document(page_content=content, metadata={"file_name": db_file.file_name, "source": db_file.file_path}))
#                 db_file.already_processed_to_source_data = True
#                 await session.commit()

#     print(f"Loaded {len(documents)} documents based on DB query.")
#     return documents


async def load_documents(data_path: str, account_unique_id: str, session: AsyncSession):
    """
    Load the documents from the data directory based on a database query.
    """
    statement = select(SourceFile).filter(
        SourceFile.account_unique_id == account_unique_id,
        SourceFile.included_in_source_data == True,
        SourceFile.already_processed_to_source_data == False
    )
    result = await session.execute(statement)
    documents_from_db = result.scalars().all()

    documents = []
    for db_file in documents_from_db:
        file_path = os.path.join(data_path, db_file.file_name)
        if os.path.exists(file_path):
            file_extension = os.path.splitext(db_file.file_name)[1].lower()

            # Handle text files
            if file_extension == ".txt":
                with open(file_path, 'r') as file:
                    content = file.read()

            # Handle docx files
            elif file_extension == ".docx":
                doc = DocxDocument(file_path)
                content = "\n".join([para.text for para in doc.paragraphs])

            # Handle doc files using pypandoc for conversion
            elif file_extension == ".doc":
                try:
                    content = pypandoc.convert_file(file_path, 'plain')
                except Exception as e:
                    print(f"Failed to convert .doc file: {e}")
                    continue

            # Handle markdown files
            elif file_extension == ".md":
                with open(file_path, 'r') as file:
                    markdown_content = file.read()
                    content = markdown.markdown(markdown_content)  # Convert markdown to plain text

            # Handle PDFs
            elif file_extension == ".pdf":
                with open(file_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    content = "\n".join([page.extract_text() for page in reader.pages])

            else:
                print(f"Unsupported file format: {file_extension}")
                continue

            documents.append(Document(page_content=content, metadata={"file_name": db_file.file_name, "source": db_file.file_path}))
            db_file.already_processed_to_source_data = True
            await session.commit()

    print(f"Loaded {len(documents)} documents based on DB query.")
    return documents


async def split_text(documents: list[Document]):
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
    return chunks


async def batch(iterable, n=BATCH_SIZE):
    """
    Helper function to split a list into batches of size n.
    """
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]
        await asyncio.sleep(0)  # Allow other tasks to run


async def save_to_chroma_in_batches(chunks: list[Document], chroma_path: str, replace: bool):
    """
    Save the chunks to the Chroma database in batches, appending to existing data.
    """
    embeddings = OpenAIEmbeddings()

    # Load existing Chroma instance if it exists, otherwise create a new one
    if os.path.exists(chroma_path):
        print(f"Chroma DB already exists at {chroma_path}.")
        if replace:
            print(f"Replacing existing Chroma DB at {chroma_path}.")
            shutil.rmtree(chroma_path)
            os.makedirs(chroma_path)  # Recreate the directory after removal
            db = Chroma(persist_directory=chroma_path, embedding_function=embeddings)
        else:
            print(f"Appending to existing Chroma DB at {chroma_path}.")
            db = Chroma(persist_directory=chroma_path, embedding_function=embeddings)
    else:
        print(f"Creating new Chroma DB at {chroma_path}.")
        os.makedirs(chroma_path)
        db = Chroma(persist_directory=chroma_path, embedding_function=embeddings)

    # Only add documents if chunks are available
    if chunks:
        # Iterate over chunks in batches and save each batch
        async for chunk_batch in batch(chunks):
            db.add_documents(chunk_batch)  # Append new documents to the existing Chroma DB
            db.persist()  # Ensure changes are persisted to the DB
            print(f"Saved {len(chunk_batch)} chunks to {chroma_path}.")
    else:
        print("No chunks to add to the Chroma DB.")


if __name__ == "__main__":
    account_unique_id = "18a318b688b04fa4"
    asyncio.run(generate_chroma_db(account_unique_id, replace=False))