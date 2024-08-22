from qdrant_client import QdrantClient
from dotenv import dotenv_values
from qdrant_client.http import models

config = dotenv_values(".env")

qdrant_client = QdrantClient(
    url=config.get("QDRANT_URL"),
    api_key=config.get("QDRANT_API_KEY"),
)


# Create or recreate a collection (only needs to be done once)
def create_collection():
    # delete collections
    qdrant_client.delete_collection(collection_name=config.get('PRODUCT_COLLECTION'))
    qdrant_client.delete_collection(collection_name=config.get('SELLER_COLLECTION'))
    qdrant_client.delete_collection(collection_name=config.get('CRAWEL_TIME_COLLECTION'))
    # if not qdrant_client.collection_exists(config.get('PRODUCT_COLLECTION')):
    qdrant_client.create_collection(
        collection_name=config.get('PRODUCT_COLLECTION'),
        vectors_config=models.VectorParams(size=config.get('VECTOR_SIZE'),
                                           distance=models.Distance[config.get('DISTANCE_METRIC').upper()]),
    )
    qdrant_client.create_collection(
        collection_name=config.get('SELLER_COLLECTION'),
        vectors_config=models.VectorParams(size=config.get('VECTOR_SIZE'),
                                           distance=models.Distance[config.get('DISTANCE_METRIC').upper()]),
    )
    qdrant_client.create_collection(
        collection_name=config.get('CRAWEL_TIME_COLLECTION'),
        vectors_config=models.VectorParams(size=config.get('VECTOR_SIZE'),
                                           distance=models.Distance[config.get('DISTANCE_METRIC').upper()]),
    )


def create_collection_catagories():
    qdrant_client.delete_collection(
        collection_name=config.get('CATAGORIES_COLLECTION'))
    qdrant_client.create_collection(
        collection_name=config.get('CATAGORIES_COLLECTION'),
        vectors_config=models.VectorParams(size=config.get('VECTOR_SIZE'),
                                           distance=models.Distance[config.get('DISTANCE_METRIC').upper()]),
    )
