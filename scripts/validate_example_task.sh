#!/bin/bash
set -euo pipefail

TASK_DIR="$1"
TASK_NAME="$(basename "$TASK_DIR")"

echo "=== Validating task: $TASK_NAME ==="

DOCKERFILE="$TASK_DIR/environment/Dockerfile"
if [ ! -f "$DOCKERFILE" ]; then
    echo "SKIP: No Dockerfile found at $DOCKERFILE"
    exit 0
fi

IMAGE_TAG="nasde-ci-${TASK_NAME}"

echo "Building Docker image..."
docker build -t "$IMAGE_TAG" -f "$DOCKERFILE" "$TASK_DIR/environment/"

echo "Starting container..."
CONTAINER_ID=$(docker run -d "$IMAGE_TAG" sleep infinity)
docker exec "$CONTAINER_ID" mkdir -p /logs/verifier

SOLVE_SCRIPT="$TASK_DIR/solution/solve.sh"
if [ -f "$SOLVE_SCRIPT" ]; then
    echo "Running reference solution..."
    docker cp "$SOLVE_SCRIPT" "$CONTAINER_ID:/tmp/solve.sh"
    docker exec "$CONTAINER_ID" chmod +x /tmp/solve.sh
    docker exec "$CONTAINER_ID" /tmp/solve.sh
else
    echo "No solution/solve.sh found — verifying Docker build only"
    echo "PASS: $TASK_NAME (Docker build OK, no solution to verify)"
    docker rm -f "$CONTAINER_ID" >/dev/null 2>&1
    exit 0
fi

echo "Running verifier (test.sh)..."
TEST_SCRIPT="$TASK_DIR/tests/test.sh"
docker cp "$TEST_SCRIPT" "$CONTAINER_ID:/tmp/test.sh"
docker exec "$CONTAINER_ID" chmod +x /tmp/test.sh

if docker exec "$CONTAINER_ID" /tmp/test.sh; then
    REWARD=$(docker exec "$CONTAINER_ID" cat /logs/verifier/reward.txt 2>/dev/null || echo "missing")
    if [ "$REWARD" = "1" ]; then
        echo "PASS: $TASK_NAME (reward=1)"
    else
        echo "FAIL: $TASK_NAME (reward=$REWARD, expected 1)"
        docker rm -f "$CONTAINER_ID" >/dev/null 2>&1
        exit 1
    fi
else
    echo "FAIL: $TASK_NAME (test.sh exited non-zero)"
    docker rm -f "$CONTAINER_ID" >/dev/null 2>&1
    exit 1
fi

docker rm -f "$CONTAINER_ID" >/dev/null 2>&1
echo "=== Done: $TASK_NAME ==="
