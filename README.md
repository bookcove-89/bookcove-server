# BookCover Backend

## Tech Stack

This project's backend is built using the following core technologies, chosen for their efficiency, scalability, and robust features:

<div align="center">
  <img src="https://img.shields.io/badge/fastapi-109989?style=for-the-badge&logo=FASTAPI&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/rabbitmq-%23FF6600.svg?&style=for-the-badge&logo=rabbitmq&logoColor=white" alt="RabbitMQ" />
  <img src="https://img.shields.io/badge/MongoDB-4EA94B?style=for-the-badge&logo=mongodb&logoColor=white" alt="MongoDB" />
  <img src="https://img.shields.io/badge/redis-%23DD0031.svg?&style=for-the-badge&logo=redis&logoColor=white" alt="Redis" />
</div>

<div align="center">
  <img src="https://img.shields.io/badge/Appwrite-F02E65?style=for-the-badge&logo=Appwrite&logoColor=black" alt="Appwrite" />
  <img src="https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
</div>

---

## Setup & Configuration

Follow these steps to set up and configure the BookCover Backend for local development:

### 1. Prerequisites

Before you begin, ensure you have the following:

* **Google Books API Key:** Obtain an API key by following the instructions in the [Google Books API documentation](https://developers.google.com/books/docs/v1/using#APIKey). This is required to fetch book data.
* **MongoDB Instance:**
    * A running MongoDB database instance (local or hosted).
    * Acquire the **MongoDB Connection URI** for your database.
    * Decide on a name for your database (e.g., `bookcove_db`).
* **Docker** (Optional, but recommended for consistent environments): If you plan to run services via Docker.

### 2. Environment Variables

Create a `.env` file in the **root directory** of your project to store private configuration details.

```bash
touch .env
```
Populate the `.env` file with the following variables, replacing the placeholder values with your actual credentials and settings: 

```bash
# Google Books API Configuration
BOOK_API='<your-google-books-api-key>'
BASE_URL='https://www.googleapis.com/books/v1/volumes' # Base URL for Google Books API

# MongoDB Database Configuration
MONGO_URI='<your-mongodb-connection-uri>' 
DB_NAME='<your-database-name>'
```

### 3. Run With Docker Compose

Once your `.env` file is configured, you can launch all the services using Docker Compose. This command builds the necessary Docker images and starts the containers in detached mode.

```bash
docker-compose up --build -d
```

### 4. Access the API
After Docker Compose has successfully started all services, the FastAPI backend will be accessible locally.

1. **Verify Services**: Confirm all containers are running by executing:

```shell
docker-compose ps
```
2. **Access FastAPI Documentation (Swagger UI/ReDoc)**:
Open your web browser and navigate to the following URL to view the interactive API documentation:

* **Swagger UI**: http://localhost:8000/docs

* **ReDoc**: http://localhost:8000/redoc

> This interface allows exploration of available endpoints, understand their parameters, & test them directly