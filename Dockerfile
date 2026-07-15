FROM python:3.14.0

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 暴露服务端口（与 .env 中的 SERVER_PORT 保持一致）
EXPOSE 26715

# 启动服务
CMD ["python", "main.py"]
