# THIS MUST BE THE VERY FIRST THING IN THE FILE, BEFORE ANY OTHER IMPORTS.
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import os
import io
import uuid
import gc
import boto3
import openai
import chromadb

# Import all necessary parsing and langchain libraries
from docx import Document as DocxDocument
import PyPDF2
import pypandoc
import markdown
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from chromadb.api.types import EmbeddingFunction


# --- Configuration (Loaded from Lambda Environment Variables) ---
# The chromadb client will now read ALL the CHROMA_* variables automatically.
openai.api_key = os.environ['OPENAI_API_KEY']
BUCKET_NAME = os.environ['AWS_STORAGE_BUCKET_NAME']

# --- Global Clients (Initialized once per Lambda container start) ---
s3_client = boto3.client('s3')

CHROMA_SERVER_AUTHN_CREDENTIALS = os.environ['CHROMA_SERVER_AUTHN_CREDENTIALS']
chroma_headers = {'X-Chroma-Token': CHROMA_SERVER_AUTHN_CREDENTIALS}

class ChromaEmbeddingFunction(EmbeddingFunction):
    """A wrapper for the LangChain OpenAIEmbeddings to be used by ChromaDB."""
    def __init__(self):
        self.embedding_function = OpenAIEmbeddings()

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self.embedding_function.embed_documents(input)

# === THE LAMBDA HANDLER - MAIN ENTRY POINT ===
# This function does not need to change.
def handler(event, context):
    s3_bucket = event['s3_bucket']
    s3_key = event['s3_key']
    account_unique_id = event.get('account_unique_id', s3_key.split('/')[0])
    print(f"Starting processing for s3://{s3_bucket}/{s3_key}")
    try:
        file_content, file_extension = download_from_s3(s3_bucket, s3_key)
        text = parse_file_content(file_content, file_extension)
        source_document = Document(page_content=text, metadata={"source": s3_key})
        chunks = split_text([source_document])
        if chunks:
            save_chunks_to_chroma(chunks, account_unique_id)
        else:
            print("No chunks were generated. Nothing to save.")
        return {"statusCode": 200, "body": "File processed successfully."}
    except Exception as e:
        print(f"FATAL ERROR processing {s3_key}: {e}")
        raise e

# === HELPER FUNCTIONS ===

# The 'save_chunks_to_chroma' function becomes incredibly simple now.
def save_chunks_to_chroma(chunks: list[Document], account_unique_id: str):
    """Connects to remote ChromaDB and saves chunks."""
    # THE ONLY CHANGE IS THE NEXT LINE. We let the client auto-configure.
    CHROMA_ENDPOINT = os.environ['CHROMA_ENDPOINT']
    print(f"Connecting to ChromaDB at {CHROMA_ENDPOINT}...")
    chroma_client = chromadb.HttpClient(
        host=CHROMA_ENDPOINT,
        headers=chroma_headers
    )

    print(f"Successfully connected to ChromaDB.")
    collection_name = f"collection-{account_unique_id}"
    embedding_function = ChromaEmbeddingFunction()
    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_function
    )
    print(f"Using Chroma collection: {collection.name} with ID: {collection.id}")
    num_chunks = len(chunks)
    if num_chunks == 0:
        return
    collection.add(
        ids=[str(uuid.uuid4()) for _ in range(num_chunks)],
        documents=[chunk.page_content for chunk in chunks],
        metadatas=[chunk.metadata for chunk in chunks]
    )
    print(f"Successfully added {num_chunks} chunks to Chroma collection.")
    gc.collect()

# The other helper functions remain the same
def download_from_s3(bucket, key):
    print(f"Downloading {key} from bucket {bucket}...")
    s3_object = s3_client.get_object(Bucket=bucket, Key=key)
    file_content = s3_object['Body'].read()
    file_extension = os.path.splitext(key)[1].lower()
    return file_content, file_extension

def parse_file_content(file_content: bytes, file_extension: str) -> str:
    print(f"Parsing file with extension: {file_extension}")
    if file_extension == ".pdf":
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        return "\n".join([page.extract_text() for page in pdf_reader.pages])
    elif file_extension == ".docx":
        doc = DocxDocument(io.BytesIO(file_content))
        return "\n".join([para.text for para in doc.paragraphs])
    elif file_extension == ".txt":
        return file_content.decode('utf-8')
    elif file_extension == ".md":
        return markdown.markdown(file_content.decode('utf-8'))
    elif file_extension == ".doc":
        temp_file_path = f"/tmp/{uuid.uuid4()}.doc"
        with open(temp_file_path, "wb") as f:
            f.write(file_content)
        return pypandoc.convert_file(temp_file_path, 'plain')
    else:
        raise ValueError(f"Unsupported file format: {file_extension}")

def split_text(documents: list[Document]):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        add_start_index=True,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split document into {len(chunks)} chunks.")
    return chunks