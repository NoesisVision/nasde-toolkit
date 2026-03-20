FROM maven:3.9-eclipse-temurin-17

RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone https://github.com/gregorriegler/order-dispatch-refactoring-kata.git . && git checkout master

# Java source is in /app/java/ — build from there
RUN cd java && mvn compile -q -B

CMD ["/bin/bash"]
