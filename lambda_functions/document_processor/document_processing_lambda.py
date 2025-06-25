# lambda_function.py
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
# These must be set in your Lambda function's configuration in the AWS console.
CHROMA_ENDPOINT = os.environ['CHROMA_ENDPOINT']
CHROMA_SERVER_AUTHN_CREDENTIALS = os.environ['CHROMA_SERVER_AUTHN_CREDENTIALS']
openai.api_key = os.environ['OPENAI_API_KEY']
BUCKET_NAME = os.environ['AWS_STORAGE_BUCKET_NAME']

# --- Global Clients and Helpers (Initialized once per Lambda container start) ---
s3_client = boto3.client('s3')
chroma_headers = {'X-Chroma-Token': CHROMA_SERVER_AUTHN_CREDENTIALS}
BATCH_SIZE = 100 # Batch size for adding chunks to ChromaDB

class ChromaEmbeddingFunction(EmbeddingFunction):
    """A wrapper for the LangChain OpenAIEmbeddings to be used by ChromaDB."""
    def __init__(self):
        self.embedding_function = OpenAIEmbeddings()

    def __call__(self, input: list[str]) -> list[list[float]]:
        # The chromadb client handles batching, so we process the whole input list.
        return self.embedding_function.embed_documents(input)

# === THE LAMBDA HANDLER - MAIN ENTRY POINT ===
def handler(event, context):
    """
    Main Lambda handler. Processes a single file from S3 and adds it to ChromaDB.
    'event' payload from FastAPI: {"s3_bucket": "...", "s3_key": "...", "account_unique_id": "..."}
    """
    s3_bucket = event['s3_bucket']
    s3_key = event['s3_key']
    account_unique_id = event.get('account_unique_id', s3_key.split('/')[0]) # Fallback for account_id

    print(f"Starting processing for s3://{s3_bucket}/{s3_key}")

    try:
        # 1. Download the file content from S3
        file_content, file_extension = download_from_s3(s3_bucket, s3_key)

        # 2. Parse the file content into raw text
        text = parse_file_content(file_content, file_extension)

        # 3. Split the text into chunks
        # We wrap the single text content in a Document object for the splitter
        source_document = Document(page_content=text, metadata={"source": s3_key})
        chunks = split_text([source_document]) # Pass as a list

        # 4. Save the chunks to ChromaDB
        if chunks:
            save_chunks_to_chroma(chunks, account_unique_id)
        else:
            print("No chunks were generated. Nothing to save.")

        # 5. Optional: Clean up the original file from S3 after success
        # s3_client.delete_object(Bucket=s3_bucket, Key=s3_key)
        # print(f"Successfully processed and deleted s3://{s3_bucket}/{s3_key}")
        
        return {"statusCode": 200, "body": "File processed successfully."}

    except Exception as e:
        print(f"FATAL ERROR processing {s3_key}: {e}")
        # Re-raising the error marks the Lambda invocation as failed,
        # which is crucial for monitoring and potential retries.
        raise e

# === HELPER FUNCTIONS ===

def download_from_s3(bucket, key):
    """Downloads a file from S3 and returns its content and extension."""
    print(f"Downloading {key} from bucket {bucket}...")
    s3_object = s3_client.get_object(Bucket=bucket, Key=key)
    file_content = s3_object['Body'].read()
    file_extension = os.path.splitext(key)[1].lower()
    return file_content, file_extension

def parse_file_content(file_content: bytes, file_extension: str) -> str:
    """Parses the content of a file based on its extension."""
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
        # pypandoc needs to write to the /tmp directory in Lambda
        temp_file_path = f"/tmp/{uuid.uuid4()}.doc"
        with open(temp_file_path, "wb") as f:
            f.write(file_content)
        return pypandoc.convert_file(temp_file_path, 'plain')
    else:
        raise ValueError(f"Unsupported file format: {file_extension}")

def split_text(documents: list[Document]):
    """Splits a list of Documents into smaller chunks."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200, # Reduced overlap for better efficiency
        length_function=len,
        add_start_index=True,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split document into {len(chunks)} chunks.")
    return chunks

def save_chunks_to_chroma(chunks: list[Document], account_unique_id: str):
    """Connects to remote ChromaDB and saves chunks."""
    print(f"Connecting to ChromaDB at {CHROMA_ENDPOINT}...")
    chroma_client = chromadb.HttpClient(host=CHROMA_ENDPOINT, headers=chroma_headers)
    
    collection_name = f"collection-{account_unique_id}"
    embedding_function = ChromaEmbeddingFunction()

    # Get or create the collection. This is idempotent.
    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_function
    )
    print(f"Using Chroma collection: {collection.name} with ID: {collection.id}")

    # The chromadb client is efficient and can handle batching.
    # We add all chunks from this one file at once.
    num_chunks = len(chunks)
    if num_chunks == 0:
        return

    collection.add(
        ids=[str(uuid.uuid4()) for _ in range(num_chunks)],
        documents=[chunk.page_content for chunk in chunks],
        metadatas=[chunk.metadata for chunk in chunks]
    )
    print(f"Successfully added {num_chunks} chunks to Chroma collection.")
    gc.collect() # Aggressively clean up memory