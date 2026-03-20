FROM maven:3.9-eclipse-temurin-21

RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone https://github.com/sandromancuso/trip-service-kata.git . && git checkout master

WORKDIR /app/java
RUN mvn compile -q

CMD ["/bin/bash"]
