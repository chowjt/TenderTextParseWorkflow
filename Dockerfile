FROM python:3.14.0

# 设置工作目录
WORKDIR /app

# 构建参数：可指定 pip 镜像源，例如 --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_INDEX_URL=
ARG PIP_TRUSTED_HOST=

# pip 配置：缩短超时、减少重试，支持自定义镜像源
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_TIMEOUT=30 \
    PIP_RETRIES=2

# 可选：使用国内镜像源
RUN if [ -n "$PIP_INDEX_URL" ]; then \
        pip config set global.index-url "$PIP_INDEX_URL"; \
    fi && \
    if [ -n "$PIP_TRUSTED_HOST" ]; then \
        pip config set global.trusted-host "$PIP_TRUSTED_HOST"; \
    fi

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --prefer-binary -r requirements.txt

# 复制项目代码
COPY . .

# 暴露服务端口（与 .env 中的 SERVER_PORT 保持一致）
EXPOSE 26715

# 启动服务
CMD ["python", "main.py"]
