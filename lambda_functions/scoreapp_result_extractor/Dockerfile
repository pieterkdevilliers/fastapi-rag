# ==========================
# Base image: Amazon Linux 2023
# ==========================
FROM public.ecr.aws/amazonlinux/amazonlinux:2023

# --------------------------
# Install Python 3.9 + build tools
# --------------------------
RUN dnf install -y python3.9 python3.9-devel gcc gcc-c++ make \
    && alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1 \
    && python3 -m ensurepip \
    && pip3 install --upgrade pip \
    && dnf clean all

# --------------------------
# Set Lambda task root
# --------------------------
ENV LAMBDA_TASK_ROOT=/var/task
WORKDIR ${LAMBDA_TASK_ROOT}

# --------------------------
# Copy Lambda function code
# --------------------------
COPY extract_scorecard_text.py ${LAMBDA_TASK_ROOT}

# --------------------------
# Install Python dependencies locally in /var/task
# --------------------------
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip3 install --no-cache-dir -r requirements.txt -t ${LAMBDA_TASK_ROOT}

# --------------------------
# Lambda entrypoint
# --------------------------
# Use Amazon Linux python path and Lambda Runtime Interface Client (awslambdaric)
RUN pip3 install --upgrade awslambdaric
ENTRYPOINT ["/usr/bin/python3", "-m", "awslambdaric"]
CMD ["extract_scorecard_text.handler"]
