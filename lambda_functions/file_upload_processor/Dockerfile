# STEP 1: Use a modern, predictable, non-AWS base image.
# 'bookworm' is the latest stable Debian release with up-to-date libraries.
FROM python:3.11-slim-bookworm

# Set an environment variable for a non-interactive install
ENV DEBIAN_FRONTEND=noninteractive

# STEP 2: Install modern system libraries using apt-get.
# This version includes the previously missing 'libpangoft2-1.0-0'.
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    tar \
    gzip \
    # WeasyPrint dependencies
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    # Dependencies for C extensions if needed
    libffi-dev \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# STEP 3: Install Pandoc
ARG PANDOC_VERSION=3.1.13
ARG PANDOC_URL="https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/pandoc-${PANDOC_VERSION}-linux-amd64.tar.gz"
RUN wget -O /tmp/pandoc.tar.gz ${PANDOC_URL} && \
    tar -xzf /tmp/pandoc.tar.gz -C /tmp && \
    mv /tmp/pandoc-${PANDOC_VERSION}/bin/pandoc /usr/local/bin/ && \
    rm -rf /tmp/pandoc*

# Create function directory
WORKDIR /var/task

# Copy requirements and install them (including the Lambda RIC)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your application code
COPY . .

# STEP 4: Set up the Lambda entrypoint
COPY entry.sh /
RUN chmod +x /entry.sh
ENTRYPOINT [ "/entry.sh" ]

# The CMD is now just the name of your handler function
CMD [ "file_upload_processor_lambda.lambda_handler" ]