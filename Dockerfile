# Use an official Python runtime as a parent image
FROM python:3.10

# Set the working directory
WORKDIR /app

# Copy files to container
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the bot
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "shed_bot:app"]
