from flask import Flask, jsonify, request
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler
from qdrant_instance import create_collection,create_collection_catagories, qdrant_client, config as Config
import sys
import time
import logging
from qdrant_client.http import models
from qdrant_client import models as qdrant_client_model
from sentence_transformers import SentenceTransformer
from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from datetime import datetime
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flasgger import Swagger
import uuid
from flask_cors import CORS,cross_origin

# from PIL import Image
# from io import BytesIO
# from torchvision import models as ModelVision, transforms
# import torch
app = Flask(__name__)
CORS(app)
# Initialize Flasgger
swagger = Swagger(app)

# Initialize Flask-Limiter
limiter = Limiter(
    get_remote_address,  # Use the client's IP address to identify users
    app=app,
    default_limits=["200 per day", "50 per hour"]  # Default rate limits
)

# Load the pre-trained model
sentenceModel = SentenceTransformer(
    'paraphrase-MiniLM-L6-v2')  # This is a lightweight model; you can use other models if needed

books = [
    {'id': 1, 'name': 'abn'},
    {'id': 2, 'name': 'samir'},
    {'id': 3, 'name': 'Daruom'},
]
finalCrawl = []

import numpy as np


def combine_title_and_localisation(title, localisation, catalog):
    return f"{title} - {localisation} - {catalog}"


def combine_vector(description, title, delegation, governorate, publisher, price):
    return f"{description} {title} {delegation} {governorate} {publisher} {price}"


def text_to_vector(text):
    return sentenceModel.encode(text).tolist()


def get_current_timestamp():
    return datetime.utcnow().isoformat() + 'Z'


# # Download the image from the URL
# def download_image(url):
#     response = requests.get(url)
#     img = Image.open(BytesIO(response.content))
#     return img

# # Preprocess the image and convert it to a vector
# def image_to_vector(image):
#     preprocess = transforms.Compose([
#         transforms.Resize(256),
#         transforms.CenterCrop(224),
#         transforms.ToTensor(),
#         transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
#     ])
#
#     image_tensor = preprocess(image).unsqueeze(0)
#     image_model = ModelVision.resnet50(pretrained=True)
#     image_model.eval()
#
#     with torch.no_grad():
#         image_vector = image_model(image_tensor).flatten().numpy()
#     return image_vector


@app.route('/crawl', methods=['POST'])
@limiter.limit("5 per minute")  # Rate limit of crawl
def crawlData():
    data = request.json
    create_collection()
    update_crawl_time()
    id = 0
    # for j in range(1):
    url = "https://www.tayara.tn/api/marketplace/search-api/"
    siteUrl = requests.post(url, json={
        "searchRequest": {
            "query": data.get('query', ''),
            "offset": data.get('offset', 0),
            "limit": data.get('limit', 30),
            "sort": 0,
            "filter": {
                "categoryId": "",
                "subCategoryId": "",
                "adParamsMap": {},
                "rangeAdParamsMap": {},
                "governorate": "",
                "delegation": [
                    ""
                ],
                "minPrice": 0,
                "maxPrice": 0,
                "level": 0,
                "state": 2
            }
        },
        "withPremium": True
    })

    results = siteUrl.json()
    tables = results[0][0] + results[1]
    id = 0
    for result in results[0][0]:
        id = str(uuid.uuid4())
        combined_text = combine_vector(result['description'], result['title'], result['location']['delegation'],
                                       result['location']['governorate'], result['metadata']['publisher']['name'],
                                       result['price'])

        text_vector = text_to_vector(combined_text)
        result['createdAt'] = get_current_timestamp()
        result['seller'] = result['metadata']['publisher']
        result['seller']['subCategory'] = result['metadata']['subCategory']
        result['seller']['sellerId'] = str(uuid.uuid4())
        del result['metadata']
        points = [
            models.PointStruct(
                id=id,
                vector=text_vector,
                payload=result
            )
        ]
        qdrant_client.upsert(collection_name=Config.get('PRODUCT_COLLECTION'), points=points)

        # seller part
        seller = result['seller']

        seller['createdAt'] = get_current_timestamp()
        text_vector = text_to_vector(seller['name'])

        points = [
            models.PointStruct(
                id=id,
                vector=text_vector,
                payload=seller
            )
        ]
        qdrant_client.upsert(collection_name=Config.get('SELLER_COLLECTION'), points=points)
    return jsonify(
        {"status": "success", "message": "Data inserted successfully", "totalItems": len(tables), 'data': tables})

@app.route('/productsBySellerName', methods=['POST'])
def productBySellerName():
    data = request.json
    query_vector = text_to_vector(data.get('name', ''))

    query_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="seller.name",
                match=models.MatchValue(value=data.get('name', '')),
            )
        ]
    )
    search_result = qdrant_client.search(
        collection_name=Config.get('PRODUCT_COLLECTION'),
        query_filter=query_filter,
        query_vector=query_vector,
        offset=data.get('offset', 0),
        limit=data.get('limit', 10),
    )
    search_result_dicts = [record.dict() for record in search_result]
    return jsonify({"status": "success", 'data': search_result_dicts})

@app.route('/update_crawl_time', methods=['POST'])
def update_crawl_time():
    data = request.json
    vector_id = 1
    vector = text_to_vector(get_current_timestamp())  # Assuming the vector is part of the payload
    last_crawl_time = get_current_timestamp()

    # Update the vector with the new last_crawl_time
    qdrant_client.upsert(
        collection_name=Config.get('CRAWEL_TIME_COLLECTION'),
        points=[
            {
                'id': vector_id,
                'vector': vector,
                'payload': {'last_crawl_time': last_crawl_time}
            }
        ]
    )

    return jsonify({'status': 'success', 'last_crawl_time': last_crawl_time})


@app.route('/stats', methods=['GET'])
def get_collection_stats():
    # Get collection info
    collection_info = qdrant_client.get_collection(Config.get('PRODUCT_COLLECTION'))

    total_points = collection_info.points_count
    last_crawl_time = get_time()  # Replace with actual timestamp if available

    # Return statistics as JSON
    # return jsonify({
    #     "total_indexed_listings": total_points,
    #     "last_crawl_time": last_crawl_time
    # })

    return jsonify({
        "status": collection_info.status,
        "optimizer_status": collection_info.optimizer_status,
        "vectors_count": collection_info.vectors_count,
        "indexed_vectors_count": collection_info.indexed_vectors_count,
        "points_count": collection_info.points_count,
        "segments_count": collection_info.segments_count,
        "last_crawl_time": last_crawl_time
    })


@app.route('/crawltime', methods=['GET'])
def get_time():
    search_result = qdrant_client.retrieve(
        collection_name=Config.get('CRAWEL_TIME_COLLECTION'),
        ids=[1]
    )
    search_result_dicts = [record.dict() for record in search_result]
    return search_result_dicts[0]['payload']['last_crawl_time']


@app.route('/seller/<int:id>', methods=['GET'])
def get_seller(id):
    search_result = qdrant_client.retrieve(
        collection_name=Config.get('SELLER_COLLECTION'),
        ids=[id]

    )
    search_result_dicts = [record.dict() for record in search_result]
    return jsonify(search_result_dicts)


@app.route('/product/<int:id>', methods=['GET'])
def get_product(id):
    search_result = qdrant_client.retrieve(
        collection_name=Config.get('PRODUCT_COLLECTION'),
        ids=[id]
    )
    search_result_dicts = [record.dict() for record in search_result]
    return jsonify(search_result_dicts)


@app.route('/fetsh', methods=['GET'])
def fetchData():
    create_collection_catagories()
    # for j in range(1):
    url = "https://www.tayara.tn/ads/c/Immobilier/?page=1"
    siteUrl = requests.get(url)

    # browser = webdriver.Firefox()
    # browser.get(url)
    # print(browser.title)
    # browser.implicitly_wait(10)
    # submit_btn = browser.find_element(by=By.CSS_SELECTOR,value='button')

    # print(submit_btn)

    page = BeautifulSoup(siteUrl.content, 'html.parser')
    articles = page.find_all('article')

    for article in articles:
        body = {}
        body['id'] = str(uuid.uuid4())

        catalog = article.find('span', class_="truncate")
        if catalog:
            body['catalog'] = catalog.text

        text_vector = text_to_vector(body['catalog'])

        points = [
            models.PointStruct(
                id=body['id'],
                vector=text_vector,
                payload=body
            )
        ]
        qdrant_client.upsert(collection_name=Config.get('CATAGORIES_COLLECTION'), points=points)
        finalCrawl.append(body)

    return jsonify({"status": "success", "message": "Data inserted successfully", 'data': finalCrawl})


# Flask route for the search function
@app.route('/search', methods=['POST'])
def search():
    """
       Perform a search operation with pagination, filtering, and additional query parameters.
       ---
       tags:
         - Search
       requestBody:
         description: JSON object containing search parameters.
         required: true
         content:
           application/json:
             schema:
               type: object
               properties:
                 keyword:
                   type: string
                   description: The keyword used for searching the items.
                   example: "example"
                 offset:
                   type: integer
                   description: The number of items to skip for pagination.
                   example: 0
                 limit:
                   type: integer
                   description: The maximum number of items to return in the response.
                   example: 10
                 title:
                   type: string
                   description: (Optional) Filter results by item title.
                   example: "Item Title"
                 priceGte:
                   type: number
                   format: float
                   description: (Optional) Filter results to include items with a price greater than or equal to this value.
                   example: 10.00
                 priceLte:
                   type: number
                   format: float
                   description: (Optional) Filter results to include items with a price less than or equal to this value.
                   example: 100.00
                 categoryId:
                   type: string
                   description: (Optional) Filter results by category ID.
                   example: "12345"
                 locationId:
                   type: string
                   description: (Optional) Filter results by location ID.
                   example: "67890"
       responses:
         200:
           description: A list of search results and the total count of items.
           content:
             application/json:
               schema:
                 type: object
                 properties:
                   results:
                     type: array
                     items:
                       type: object
                       properties:
                         id:
                           type: integer
                           description: Unique identifier for the item.
                           example: 1
                         name:
                           type: string
                           description: The name of the item.
                           example: "Item Name"
                         description:
                           type: string
                           description: A detailed description of the item.
                           example: "A detailed description of the item."
                         seller:
                           type: string
                           description: The seller or publisher of the item.
                           example: "Seller Name"
                   total_count:
                     type: integer
                     description: The total number of items available that match the search criteria.
                     example: 100
         400:
           description: Bad request. The request was invalid or missing parameters.
           content:
             application/json:
               schema:
                 type: object
                 properties:
                   error:
                     type: string
                     example: "Invalid parameters"
         500:
           description: Internal server error. An unexpected error occurred on the server.
           content:
             application/json:
               schema:
                 type: object
                 properties:
                   error:
                     type: string
                     example: "Internal server error"
       """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid request body, must be JSON"}), 400

        keyword = data.get('keyword', '').lower()
        offset = data.get('offset')
        limit = data.get('limit')

        if keyword is None or offset is None or limit is None:
            return jsonify({"error": "Missing required parameters"}), 400

        query_filter_conditions = []

        # Add title filter if provided
        title = data.get("title", '')
        if title:
            query_filter_conditions.append(
                models.FieldCondition(
                    key="title",
                    match=models.MatchValue(value=title),
                )
            )

        # Add price range filter if provided
        price_gte = data.get('priceGte')
        price_lte = data.get('priceLte')
        if price_gte is not None or price_lte is not None:
            query_filter_conditions.append(
                models.FieldCondition(
                    key="price",
                    range=models.Range(
                        lt=None,
                        gt=None,
                        gte=price_gte,
                        lte=price_lte,
                    ),
                )
            )
        #
        # # Add other filters if needed (e.g., categoryId, locationId)
        # category_id = data.get('categoryId')
        # if category_id:
        #     query_filter_conditions.append(
        #         models.FieldCondition(
        #             key="categoryId",
        #             match=models.MatchValue(value=category_id),
        #         )
        #     )
        #
        # location_id = data.get('locationId')
        # if location_id:
        #     query_filter_conditions.append(
        #         models.FieldCondition(
        #             key="locationId",
        #             match=models.MatchValue(value=location_id),
        #         )
        #     )

        query_filter = models.Filter(must=query_filter_conditions) if query_filter_conditions else None
        print(query_filter)
        query_vector = text_to_vector(keyword)
        search_result = qdrant_client.search(
            collection_name=Config.get('PRODUCT_COLLECTION'),
            query_vector=query_vector,
            query_filter=query_filter,
            search_params=models.SearchParams(hnsw_ef=128, exact=False),
            offset=offset,
            limit=limit,
        )
        search_result_dicts = [record.dict() for record in search_result]

        results = []
        for item in search_result_dicts:
            item['payload']['id'] = item['id']
            item = item['payload']
            try:
                item['seller'] = item['metadata']['publisher']
                del item['metadata']
            except:
                item['seller'] = None
            results.append(item)

        collection_info = qdrant_client.get_collection(Config.get('PRODUCT_COLLECTION'))
        total_elements = collection_info.points_count

        return jsonify({"results": results, "totalElements": total_elements})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/insert', methods=['POST'])
def insert_data():
    data = request.json
    text = data.get('text', '')

    vector = sentenceModel.encode(text).tolist()
    points = [
        models.PointStruct(
            id=data['id'],
            vector=vector,
            payload=data.get('payload', {})
        )
    ]
    qdrant_client.upsert(collection_name=Config.get('COLLECTION_NAME'), points=points)
    return jsonify({"status": "success", "message": "Data inserted successfully"})


@app.route("/books", methods=['GET'])
def getAllBooks():
    return {'status': '200', 'message': 'books retrieved', 'data': books}


@app.route("/books/<int:id>", methods=['GET'])
def getAlBooks(id):
    for book in books:
        if book['id'] == id:
            return book
    return {'error': 'Book not found'}, 404


@app.route("/books", methods=['POST'])
def createBook():
    try:
        for book in books:
            if book['name'] == request.json['name']:
                return {'error': 'Book already exists'}, 400
        newBook = {'id': len(books) + 1, 'name': request.json['name']}
        books.append(newBook)
        return {'data': newBook, 'status': '201', 'message': 'book created'}, 201
    except:
        if 'name' not in request.json:
            return {'error': 'name is required'}, 400
        else:
            return {'error': 'bad request'}, 400


@app.route("/books/<int:id>", methods=['PUT'])
def updateBook(id):
    for book in books:
        if book['id'] == id:
            book['name'] = request.json['name']
            return {'data': book, 'status': '200', 'message': 'book updated'}
    return {'error': 'Book not found'}, 404


@app.route("/books/<int:id>", methods=['DELETE'])
def deleteBook(id):
    for book in books:
        if book['id'] == id:
            books.remove(book)
            return {'data': book, 'status': '200', 'message': 'book deleted'}
    return {'error': 'Book not found'}, 404


# Error handling for rate limit exceeded
@app.errorhandler(429)
def ratelimit_error(e):
    return jsonify(error="ratelimit exceeded", message=str(e.description)), 429


if __name__ == "__main__":
    # app.run()
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    path = sys.argv[1] if len(sys.argv) > 1 else '.'
    event_handler = LoggingEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
