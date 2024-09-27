import json
import os
import pathlib
import pprint
import sys
from datetime import datetime, timezone
from typing import List, Optional

from dotenv import load_dotenv
from loguru import logger
from pymongo import MongoClient

CONFIG = {}
logger.remove()
logger.add(sys.stderr, level="INFO")

load_dotenv()

printer = pprint.PrettyPrinter()


def get_current_file_path():
    return pathlib.Path(__file__).parent.resolve()


def load_config():
    global CONFIG
    logger.info("Loading config")
    if os.environ.get("MODE") == "dev":
        if os.environ.get("MODE") == "dev":
            config = {
                "api_key": "635FA675-6982-634B-9020-342DD7A589A854A0250D-0BF8-4787-B756-BC0394806C6F",
                "MONGO_INITDB_ROOT_USERNAME": "root",
                "MONGO_INITDB_ROOT_PASSWORD": "password",
                "ME_CONFIG_BASICAUTH_USERNAME": "mexpress",
                "ME_CONFIG_BASICAUTH_PASSWORD": "password",
                "character": "John The Tormentor",
                "update_every_minutes": 1,
            }
            CONFIG = config
            return

    config_file_name = (
        "config_dev.json" if os.environ.get("MODE") == "dev" else "config.json"
    )
    print(f"Config file: {config_file_name}")
    try:
        with open(os.path.join(sys._MEIPASS, config_file_name), "r") as f:
            CONFIG = json.load(f)
    except Exception:
        with open(os.path.join(get_current_file_path(), config_file_name), "r") as f:
            CONFIG = json.load(f)


load_config()
print(f"Loaded config: {CONFIG}")
mongo_client = MongoClient(
    host="172.17.0.1:27017",
    username=CONFIG.get("MONGO_INITDB_ROOT_USERNAME"),
    password=CONFIG.get("MONGO_INITDB_ROOT_PASSWORD"),
    serverSelectionTimeoutMS=60000,
)


def get_db():
    db = mongo_client.gw2tracker_database
    return db


def get_items_collection():
    db = get_db()
    db.items_collection.create_index("id", unique=True)
    return db.items_collection


def get_items_info_collection():
    db = get_db()
    db.items_info_collection.create_index("id", unique=True)
    return db.items_info_collection


def get_inventory_items_collection():
    db = get_db()
    # db.inventory_items_collection.create_index("id", unique=True)
    return db.inventory_items_collection


def get_materials_items_collection():
    db = get_db()
    db.materials_items_collection.create_index("id", unique=True)
    return db.materials_items_collection


def get_character_info_collection():
    db = get_db()
    db.character_info_collection.create_index("name", unique=True)
    return db.character_info_collection


def get_account_info_collection():
    db = get_db()
    return db.account_info_collection


def get_currencies_collection():
    db = get_db()
    db.currencies_collection.create_index("id", unique=True)
    return db.currencies_collection


def get_updated_at_collection():
    db = get_db()
    return db.collection_updated_at


def set_collection_updated_at(collection_name: str):
    get_updated_at_collection().update_one(
        {"name": collection_name},
        {
            "$set": {
                "name": collection_name,
                "updated_at": datetime.now(tz=timezone.utc),
            }
        },
        upsert=True,
    )


def get_collection_updated_at(collection_name: str):
    try:
        return (
            get_updated_at_collection()
            .find_one({"name": collection_name})
            .get("updated_at", None)
        )
    except Exception as e:
        logger.warning(
            f"Error getting updated at from collection {collection_name}. {e}"
        )
        return None


def add_items_info_to_db(items: List[dict]):
    logger.info("Adding items info to the database")
    items_info_collection = get_items_info_collection()
    items_info_collection.delete_many({})
    items_info_collection.insert_many(items)
    set_collection_updated_at("items_info_collection")


def get_items_info_from_db():
    logger.info("Getting items info from the database")
    items_info_collection = get_items_info_collection()
    items_info_collection.find()


def add_item_info_to_db(item: dict):
    logger.info("Adding item info to the database")
    items_info_collection = get_items_info_collection()

    # items_info_collection.update_one(
    #     {"id": item.get("id")},
    #     {"$set": item},
    #     upsert=True,
    # )
    try:
        items_info_collection.insert_one(item)
    except Exception:
        pass


def get_item_info_from_db(item_id: str):
    logger.info("Getting items info from the database")
    items_info_collection = get_items_info_collection()
    item = items_info_collection.find_one({"id": item_id}) or None
    logger.debug(f"Item found {item}")
    return item


# def add_items_to_db(items: List[dict], character_name: str):
#     logger.info("Adding items to the database")
#     items_collection = get_items_collection()
#     items_collection.insert_many({**items, "character_name": character_name})
#     set_collection_updated_at("items")


def get_items_from_db(character_name: str):
    logger.info("Getting items from the database")
    items_collection = get_items_collection()
    items = items_collection.find({"character_name": character_name})
    printer.pprint(items)
    return items


def add_inventory_items_to_db(items: List[dict]):
    logger.info("Adding inventory items to the database")
    inventory_items_collection = get_inventory_items_collection()
    inventory_items_collection.delete_many({})
    inventory_items_collection.insert_many(items)
    set_collection_updated_at("inventory_items_collection")


def get_inventory_items_from_db(character_name: str):
    logger.info(f"Getting {character_name} inventory items from the database")
    items_collection = get_inventory_items_collection()
    items = items_collection.find({"character_name": character_name})
    printer.pprint(items)
    return items


def get_trading_post_prices_collection():
    db = get_db()
    return db.trading_post_prices_collection


def add_trading_post_price_to_db(trading_post_price: dict):
    logger.info("Adding trading post price to the database")
    trading_post_prices_collection = get_trading_post_prices_collection()
    trading_post_prices_collection.update_one(
        {"id": trading_post_price.get("id")},
        {"$set": {**trading_post_price}},
        upsert=True,
    )


def add_trading_post_prices_to_db(trading_post_prices: List[dict]):
    logger.info("Adding trading post prices to the database")
    trading_post_prices_collection = get_trading_post_prices_collection()
    trading_post_prices_collection.insert_many(trading_post_prices)
    set_collection_updated_at("trading_post_prices_collection")


def get_trading_post_prices_from_db():
    logger.info("Getting trading post prices from the database")
    trading_post_prices = get_trading_post_prices_collection().find()
    printer.pprint(trading_post_prices)
    return trading_post_prices


def get_tp_item_price_by_id_from_db(item_id: str) -> Optional[int]:
    item_price = None
    logger.info(f"Getting trading post price for item {item_id} from the database")
    item_price = get_trading_post_prices_collection().find_one({"id": item_id})
    logger.debug(f"Item price {item_price}")
    return item_price


def add_current_inventory_value_to_db(
    current_inventory_value: int, character_name: str
):
    character_info_collection = get_character_info_collection()
    character_info_collection.update_one(
        {"character_name": character_name},
        {"$set": {"current_inventory_value": current_inventory_value}},
        upsert=True,
    )
    set_collection_updated_at("character_info_collection")


def add_current_materials_storage_value_to_db(value: int, character_name: str):
    character_info_collection = get_character_info_collection()
    character_info_collection.update_one(
        {"character_name": character_name},
        {"$set": {"material_storage_value": value}},
        upsert=True,
    )
    set_collection_updated_at("character_info_collection")


def add_coins_amount_to_db(value: int, character_name: str):
    character_info_collection = get_character_info_collection()
    character_info_collection.update_one(
        {"character_name": character_name},
        {"$set": {"coins_amount": value}},
        upsert=True,
    )
    set_collection_updated_at("character_info_collection")


def get_current_inventory_value_from_db(character_name: str) -> int:
    logger.info("Getting current inventory value")
    character_info_collection = get_character_info_collection()
    character_info = character_info_collection.find_one(
        {"character_name": character_name}
    )
    current_inventory_value = character_info.get("current_inventory_value")
    logger.debug(f"Current inventory value: {current_inventory_value}")
    return current_inventory_value


def get_current_material_storage_value_from_db(character_name: str) -> int:
    logger.info("Getting current material storage value")
    character_info_collection = get_character_info_collection()
    character_info = character_info_collection.find_one(
        {"character_name": character_name}
    )
    current_material_storage_value = character_info.get("material_storage_value")
    logger.debug(f"Current material storage value: {current_material_storage_value}")
    return current_material_storage_value


def get_item_name_from_db(item_id: str):
    logger.info(f"Getting item {item_id} name from the database")
    items_collection = get_items_info_collection()
    item_name = items_collection.find_one({"id": int(item_id)}).get("name")
    logger.info(f"Item {item_id} name: {item_name}")
    return item_name


def add_currencies_to_db(currencies: List[dict]):
    logger.info("Adding currencies to the database")
    currencies_collection = get_currencies_collection()
    currencies_collection.insert_many(currencies)


def get_currencies_from_db():
    logger.info("Getting currencies from the database")
    currencies = get_currencies_collection().find()
    printer.pprint(currencies)
    return currencies


def get_currency_from_db(currency_id: str):
    logger.info(f"Getting currency {currency_id} from the database")
    currency = get_currencies_collection().find_one({"id": currency_id})
    printer.pprint(currency)
    return currency
