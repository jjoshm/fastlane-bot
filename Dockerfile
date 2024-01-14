FROM python:3.9.18-slim-bookworm
WORKDIR /app
COPY requirements.txt requirements.txt
COPY setup.py setup.py
RUN pip install -r requirements.txt
COPY . .
RUN python setup.py install
ENTRYPOINT ["python", "main.py"]
