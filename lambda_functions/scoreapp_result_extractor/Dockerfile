FROM public.ecr.aws/amazonlinux/amazonlinux:2023

# Install Python 3.9 + dev tools
RUN dnf install -y python3.9 python3.9-devel gcc gcc-c++ make \
    && alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1 \
    && python3 -m ensurepip \
    && pip3 install --upgrade pip

# Set Lambda entrypoint
CMD ["extract_scorecard_text.handler"]
