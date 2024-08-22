# flask-backend

This is a simple web application built using the [Flask](https://flask.palletsprojects.com/) framework.

## Prerequisites

Before you begin, ensure you have met the following requirements:

- [Python 3.8+](https://www.python.org/)
- [pip](https://pip.pypa.io/en/stable/)

## Installation

Follow these steps to get your Flask application up and running locally.

1. **Clone the repository**:

   ```bash
   git clone https://github.com/Memorality-tech/flask-backend.git
   cd flask-backend
   ```

2. **Create a virtual environment**:

   ```bash
   python3 -m venv venv
   ```

3. **Activate the virtual environment**:

   - On macOS/Linux:

     ```bash
     source venv/bin/activate
     ```

   - On Windows:

     ```bash
     venv\Scripts\activate
     ```

4. **Install the dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

5. **Set environment variables** :

   Create a `.env` file in the root directory of your project and add the necessary environment variables. For example:

   ```plaintext
       DOMAIN=example.org
       QDRANT_URL=YOUR_QDRANT_URL
       QDRANT_API_KEY=YOUR_QDRANT_KEY
       COLLECTION_NAME=my_collection
       PRODUCT_COLLECTION=products
       CRAWEL_TIME_COLLECTION=crawl_time
       SELLER_COLLECTION=sellers
       VECTOR_SIZE=384
       DISTANCE_METRIC=Cosine

   ```

## Running the Application

To start the Flask application, run the following command:

```bash
flask run
```
