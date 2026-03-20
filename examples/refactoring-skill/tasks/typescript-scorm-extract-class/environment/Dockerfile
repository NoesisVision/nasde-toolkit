FROM node:20-slim

RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone https://github.com/jcputney/scorm-again.git . && git checkout main

RUN npm install

# Verify build and tests pass at the "before" state
RUN npm run build
RUN npm test || true

CMD ["/bin/bash"]
