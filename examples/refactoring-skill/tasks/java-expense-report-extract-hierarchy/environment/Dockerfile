FROM maven:3.9-eclipse-temurin-21

RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone https://github.com/christianhujer/expensereport.git . && git checkout trunk

WORKDIR /app/expensereport-java
RUN mvn compile -q || true

CMD ["/bin/bash"]
