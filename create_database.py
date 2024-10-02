import os
import shutil
import openai
import asyncio  # Import asyncio
from docx import Document as DocxDocument
import PyPDF2
import pypandoc
import markdown
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from sqlalchemy.sql import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
from file_management.models import SourceFile
from db import async_engine

load_dotenv()

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
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()


openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")

BATCH_SIZE = 5461


async def generate_chroma_db(account_unique_id, replace=False):
    """
    Generate a data store from the documents.
    """
    print(f"generate_chroma_db called for {account_unique_id}.")

    # Correctly use async for to manage the session
    async for session in get_async_session():
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
    
    documents = await load_documents(data_path, account_unique_id, session)
    chunks = await split_text(documents)

    # Check for empty chunks before initializing the database
    if chunks:
        await save_to_chroma_in_batches(chunks, chroma_path, replace)
    else:
        print(f"No chunks generated for account {account_unique_id}. Skipping Chroma DB creation.")


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

            try:
                content = await read_file(file_path, file_extension)
            except Exception as e:
                print(f"Failed to read file {db_file.file_name}: {e}")
                continue

            documents.append(Document(page_content=content, metadata={"file_name": db_file.file_name, "source": db_file.file_path}))
            db_file.already_processed_to_source_data = True
            await session.commit()

    print(f"Loaded {len(documents)} documents based on DB query.")
    return documents


async def read_file(file_path: str, file_extension: str) -> str:
    """
    Helper function to handle reading files based on the file extension.
    """
    if file_extension == ".txt":
        with open(file_path, 'r') as file:
            return file.read()

    elif file_extension == ".docx":
        doc = DocxDocument(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

    elif file_extension == ".doc":
        try:
            return pypandoc.convert_file(file_path, 'plain')
        except Exception as e:
            raise Exception(f"Failed to convert .doc file: {e}")

    elif file_extension == ".md":
        with open(file_path, 'r') as file:
            markdown_content = file.read()
            return markdown.markdown(markdown_content)

    elif file_extension == ".pdf":
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            return "\n".join([page.extract_text() for page in reader.pages])

    else:
        raise ValueError(f"Unsupported file format: {file_extension}")


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
        await asyncio.sleep(0)


async def save_to_chroma_in_batches(chunks: list[Document], chroma_path: str, replace: bool):
    """
    Save the chunks to the Chroma database in batches.
    """
    embeddings = OpenAIEmbeddings()
    
    if not os.path.exists(chroma_path):
        await create_chroma_db_dir(chroma_path)
        print(f"Directory created: {chroma_path}")
    else:
        print(f"Directory already exists: {chroma_path}")
    
    db = None
    if replace:
        print(f"Creating new Chroma DB at {chroma_path}.")
        db = await create_new_chroma_db(chroma_path, embeddings)
    else:
        print(f"Loading existing Chroma DB at {chroma_path}.")
        db = Chroma(persist_directory=chroma_path, embedding_function=embeddings)

    # Confirm that the database is initialized correctly
    if db is None:
        print("Error initializing Chroma DB.")
        return {"response": "error", "message": "Failed to initialize Chroma DB."}
    
    else:
        print(f"Successfully initialized Chroma DB at {chroma_path}.")

        # Proceed to batch saving chunks
        chunks_status = await save_chunks_to_db_in_batches(chunks, db, chroma_path)
        print(f"Chunks Status: {chunks_status}.")
        return chunks_status


async def create_chroma_db_dir(chroma_path: str):
    """
    Get or Create Chroma DB Directory.
    """
    os.makedirs(chroma_path, exist_ok=True)
    os.chmod(chroma_path, 0o775)
    print(f"Successfully created new directory: {chroma_path}.")
    
    return chroma_path


async def create_new_chroma_db(chroma_path: str, embeddings):
    """
    Create a new Chroma database.
    """
    try:
        # Initialize the Chroma DB with the specified directory
        db = Chroma(persist_directory=chroma_path, embedding_function=embeddings)
        print(f"Chroma DB initialized successfully at {chroma_path}.")
        
        return db
    except Exception as e:
        print(f"Error initializing Chroma DB: {e}")
        return None


async def save_chunks_to_db_in_batches(chunks: list[Document], db: Chroma, chroma_path: str):
    """
    Save the chunks to the Chroma database in batches.
    """
    if not chunks:
        print("No chunks to add to the Chroma DB.")
        return {"response": "error", "message": "No chunks provided."}

    # Iterate over chunks and save them in batches
    async for chunk_batch in batch(chunks):
        try:
            db.add_documents(chunk_batch)  # Append new documents to the Chroma DB
            print(f"Saved {len(chunk_batch)} chunks to {chroma_path}.")
        except Exception as e:
            print(f"Error saving chunks to Chroma DB: {e}")
            return {"response": "error", "message": str(e)}
    
    return {"response": "success"}