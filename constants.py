# Actions for RabbitMQ receiver to handle
ADD_FAV = "added_favorite"
RM_FAV = "remove_favorite"
UPDATED_FAV = "updated_to_favorite"

ADD_LIB = "added_to_library"
RM_LIB = "remove_from_library"
UPDATE_LIB = "update_from_library"


# RabbitMQ declared queues
RABBIT_QUEUE_LIB = "book-lib-queue"
RABBIT_QUEUE_FAV = "book-favorites-queue"


# Redis cache keys
FAV_CACHE_KEY = lambda uid: f"user_{uid}_fav_books"
LIB_CACHE_KEY = lambda uid: f"user_{uid}_lib_books"

