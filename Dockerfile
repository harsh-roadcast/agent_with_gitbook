FROM python:3.12-slim

# 1. Install Poetry
ENV POETRY_VERSION=1.8.2
RUN pip install "poetry==$POETRY_VERSION"

# 2. Set working directory
WORKDIR /app

# 3. Copy only dependency files first (for better caching)
COPY pyproject.toml poetry.lock* ./

# 4. Install dependencies
# --no-root: don't install the current project as a package yet
# --no-interaction: don't ask for user input
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# 5. Copy the rest of the code
COPY . .

# 6. Run your app
CMD ["python", "main.py"]