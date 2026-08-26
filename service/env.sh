# 本项目 Java 服务层环境变量; 用法: source env.sh
# 锁定 Java 21 LTS (Spring Boot 3.x 稳定支持; 系统默认 Java 11 跑不了)
export JAVA_HOME="/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home"
export PATH="$JAVA_HOME/bin:$PATH"

# 内部鉴权 token (公网部署时启用; 本地留空则 AuthFilter 放行)
export INTERNAL_TOKEN="${INTERNAL_TOKEN:-}"

echo "JAVA_HOME=$JAVA_HOME"
java -version
