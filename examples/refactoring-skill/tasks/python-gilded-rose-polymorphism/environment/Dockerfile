FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone https://github.com/emilybache/GildedRose-Refactoring-Kata.git . && git checkout main

RUN pip install pytest

# Verify tests pass at the "before" state
RUN cd python && python -m pytest test_gilded_rose.py -v

CMD ["/bin/bash"]
