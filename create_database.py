import os
import io
import shutil
import boto3
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
from botocore.exceptions import ClientError

load_dotenv()

# Initialize the S3 client
s3 = boto3.client('s3')
BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')


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


async def generate_data_store(account_unique_id: str, replace: bool, session: AsyncSession):
    """
    Generate a data store from the documents uploaded to S3.
    """
    print(f"Generating data store for account {account_unique_id}.")
    
    chroma_path = f"./chroma/{account_unique_id}"

    # Fetch the document URLs from the database instead of reading from local file_path
    documents = await load_documents_from_s3(account_unique_id, session)

    # Split the text into chunks
    chunks = await split_text(documents)

    # Check for empty chunks before initializing the database
    if chunks:
        await save_to_chroma_in_batches(chunks, chroma_path, replace)
    else:
        print(f"No chunks generated for account {account_unique_id}. Skipping Chroma DB creation.")


async def load_documents_from_s3(account_unique_id: str, session: AsyncSession):
    """
    Load documents from S3 based on a database query.
    """
    # Query database for files to process
    statement = select(SourceFile).filter(
        SourceFile.account_unique_id == account_unique_id,
        SourceFile.included_in_source_data == True,
        SourceFile.already_processed_to_source_data == False
    )
    result = await session.execute(statement)
    documents_from_db = result.scalars().all()

    documents = []
    
    for db_file in documents_from_db:
        # Construct S3 key (path in S3) using account_unique_id and file name
        s3_key = f"{account_unique_id}/{db_file.file_name}"

        try:
            
            s3_object = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)

            file_content = s3_object['Body'].read()

            # Process file content based on its extension
            file_extension = os.path.splitext(db_file.file_name)[1].lower()
            content = await read_file_from_s3(file_content, file_extension)

            # Append the document with metadata
            documents.append(Document(
                page_content=content, 
                metadata={"file_name": db_file.file_name, "source": s3_key}
            ))

            # Mark file as processed in the database
            db_file.already_processed_to_source_data = True
            await session.commit()

        except ClientError as e:
            print(f"Failed to fetch file {db_file.file_name} from S3: {e}")
            continue
        except Exception as e:
            print(f"Failed to process file {db_file.file_name}: {e}")
            continue

    print(f"Loaded {len(documents)} documents from S3 based on DB query.")
    return documents


async def read_file_from_s3(file_content: bytes, file_extension: str) -> str:
    """
    Helper function to handle reading files from S3 based on the file extension.
    """
    print(f"Processing file with extension: {file_extension}")
    
    # Handling .txt files
    if file_extension == ".txt":
        try:
            return file_content.decode('utf-8')
        except Exception as e:
            print(f"Error decoding .txt file: {e}")
            raise

    # Handling .docx files
    elif file_extension == ".docx":
        try:
            # Convert the byte stream to an in-memory file-like object
            doc = DocxDocument(io.BytesIO(file_content))
            return "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            print(f"Error processing .docx file: {e}")
            raise

    # Handling .doc files
    elif file_extension == ".doc":
        try:
            # Save the file content to an in-memory file
            temp_file = io.BytesIO(file_content)
            temp_file.name = "temp.doc"  # Required for pypandoc
            return pypandoc.convert_file(temp_file.name, 'plain')
        except Exception as e:
            print(f"Failed to convert .doc file: {e}")
            raise

    # Handling .md (markdown) files
    elif file_extension == ".md":
        try:
            markdown_content = file_content.decode('utf-8')
            return markdown.markdown(markdown_content)
        except Exception as e:
            print(f"Error decoding markdown file: {e}")
            raise

    # Handling .pdf files
    elif file_extension == ".pdf":
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            return "\n".join([page.extract_text() for page in pdf_reader.pages])
        except Exception as e:
            print(f"Error processing .pdf file: {e}")
            raise

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