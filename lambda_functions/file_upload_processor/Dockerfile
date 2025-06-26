# Use an official AWS base image for Python
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

# Install system dependencies for WeasyPrint and Pandoc
# For Amazon Linux 2 (the base for the image above), use yum
RUN yum install -y pango cairo gdk-pixbuf2 libffi-devel

# Copy your requirements file
COPY requirements.txt ./

# Install the Python packages
RUN python3.9 -m pip install -r requirements.txt -t .

# Copy your function code
COPY file_upload_processor_lambda.py ./
COPY convert_to_pdf.py ./

# Set the command to your handler
CMD ["file_upload_processor_lambda.lambda_handler"]