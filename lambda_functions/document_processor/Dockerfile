# Use an official AWS Lambda Python base image
FROM public.ecr.aws/lambda/python:3.9

# --- Manual Pandoc Installation (The Correct and Final Version) ---

# Set Pandoc version as an argument for easy updates
ARG PANDOC_VERSION=3.1.13
# Define the CORRECT download URL for the pre-compiled Linux tar.gz binary
ARG PANDOC_URL="https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/pandoc-${PANDOC_VERSION}-linux-amd64.tar.gz"

# CRITICAL STEP: We install every required system utility explicitly:
# wget: for downloading
# tar: for handling the archive format
# gzip: for decompressing the .gz file, used by tar's 'z' flag
RUN yum install -y wget tar gzip && \
    wget -O /tmp/pandoc.tar.gz ${PANDOC_URL} && \
    tar -xzf /tmp/pandoc.tar.gz -C /tmp && \
    mv /tmp/pandoc-${PANDOC_VERSION}/bin/pandoc /usr/local/bin/ && \
    rm -rf /tmp/pandoc*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install -r requirements.txt

# Copy your Lambda function code into the container's task root
COPY document_processing_lambda.py ${LAMBDA_TASK_ROOT}

# Set the command to the Lambda handler
# Format: <filename>.<handler_function_name>
CMD [ "document_processing_lambda.handler" ]