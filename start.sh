#!/bin/bash

# PolicyGraph QA - Docker Compose Startup Script

echo "🚀 PolicyGraph QA 시작..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker가 실행되고 있지 않습니다."
    echo "   Docker Desktop을 시작해주세요."
    exit 1
fi

# Check for .env file
if [ -f .env ]; then
    echo "✅ .env 파일 발견"
    source .env
    if [ -n "$OPENAI_API_KEY" ]; then
        echo "✅ OpenAI API 키 설정됨"
    else
        echo "⚠️  OpenAI API 키가 .env에 없습니다."
        echo "   애플리케이션 시작 후 웹 UI에서 설정할 수 있습니다."
    fi
else
    echo "⚠️  .env 파일이 없습니다."
    echo "   애플리케이션 시작 후 웹 UI에서 API 키를 설정할 수 있습니다."
fi

echo ""
echo "📦 Docker 이미지 빌드 및 컨테이너 시작..."
echo ""

# Build and start containers
docker-compose up --build -d

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ PolicyGraph QA가 성공적으로 시작되었습니다!"
    echo ""
    echo "📌 접속 URL:"
    echo "   - Frontend:  http://localhost:3000"
    echo "   - Backend:   http://localhost:8001"
    echo "   - Neo4j:     http://localhost:7474 (neo4j / policygraph123)"
    echo ""
    echo "💡 로그 확인: docker-compose logs -f"
    echo "🛑 중지하기:  docker-compose down"
    echo ""
else
    echo ""
    echo "❌ 시작에 실패했습니다. 로그를 확인해주세요:"
    echo "   docker-compose logs"
fi

