FROM python:3.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive

# Install all system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget tar gzip \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    libffi-dev build-essential \
    libreoffice-writer \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Fix ONLY for Fontconfig, as it's a common override.
# The HOME=/tmp fix will handle everything else.
RUN mkdir -p /tmp/fontconfig && chmod 1777 /tmp/fontconfig
ENV FONTCONFIG_CACHE_DIR="/tmp/fontconfig"

# Install Pandoc
# ... (this section remains the same) ...
ARG PANDOC_VERSION=3.1.13
ARG PANDOC_URL="https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/pandoc-${PANDOC_VERSION}-linux-amd64.tar.gz"
RUN wget -O /tmp/pandoc.tar.gz ${PANDOC_URL} && \
    tar -xzf /tmp/pandoc.tar.gz -C /tmp && \
    mv /tmp/pandoc-${PANDOC_VERSION}/bin/pandoc /usr/local/bin/ && \
    rm -rf /tmp/pandoc*

# Install Python requirements and copy code
# ... (this section remains the same) ...
WORKDIR /var/task
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY entry.sh /
RUN chmod +x /entry.sh
ENTRYPOINT [ "/entry.sh" ]
CMD [ "file_upload_processor_lambda.lambda_handler" ]