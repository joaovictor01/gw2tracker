from datetime import datetime
import json
import os
import pprint
import sys
import threading
import time
from typing import List, Optional

from loguru import logger

from src.database import (
    add_current_inventory_value_to_db,
    add_current_materials_storage_value_to_db,
    add_item_info_to_db,
    get_collection_updated_at,
    get_current_inventory_value_from_db,
    get_current_material_storage_value_from_db,
    get_item_info_from_db,
    get_item_name_from_db,
    get_tp_item_price_by_id_from_db,
)
from src.gw2api import Gw2Api
from src.helpers import (
    get_current_file_path,
    is_older_than_one_day,
)

logger.remove()
logger.add(sys.stderr, level="INFO")
printer = pprint.PrettyPrinter()

TRADING_POST_MODE = {"buy": "buys", "sell": "sells"}
TRADING_POST_DEFAULT_MODE = "sells"


class SessionTracker:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.load_config()
        self.start_value = 0
        self.current_value = 0
        self.inventory_value = 0
        self.materials_value = 0
        self.profit_value = 0
        if not self.api_key:
            if api_key := os.getenv("GW2_API_KEY"):
                self.set_api_key(api_key)
            else:
                self.set_api_key(self.config.get("api_key"))
        self.api = Gw2Api(api_key=self.api_key)
        self.api.set_active_character(self.config.get("character"))
        update_tp_prices_thread = threading.Thread(
            target=self.update_trading_post_prices
        )
        update_tp_prices_thread.start()
        self.start_time = datetime.now()

    def get_api(self):
        return self.api

    def set_api_key(self, api_key: str):
        self.api_key = api_key
        self.api.set_api_key(api_key)

    def reset_session(self):
        self.start_value = 0
        self.current_value = 0
        self.inventory_value = 0
        self.materials_value = 0
        self.profit_value = 0
        self.start_time = datetime.now()

    def get_session_data(self):
        return {
            "start_value": self.start_value,
            "current_value": self.current_value,
            "profit_value": self.profit_value,
            "start_time": self.start_time.isoformat(sep="_", timespec="seconds"),
        }

    def update_trading_post_prices(self):
        tp_updated_at = get_collection_updated_at("trading_post_prices_collection")
        if not tp_updated_at or is_older_than_one_day(tp_updated_at):
            logger.info(
                "Trading post prices older than 1 day. Updating trading post prices..."
            )
            time.sleep(60)
            self.api.get_prices_from_trading_post()

    def load_config(self):
        logger.info("Loading config")

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
            self.config = config
            if self.config.get("api_key"):
                self.api_key = self.config.get("api_key")
            return
        config_file_name = (
            "config_dev.json" if os.environ.get("MODE") == "dev" else "config.json"
        )
        print(f"Config file: {config_file_name}")
        with open(os.path.join(get_current_file_path(), config_file_name), "r") as f:
            self.config = json.load(f)
        if self.config.get("api_key"):
            self.api_key = self.config.get("api_key")

    def get_buy_price_from_item(self, item_id: str) -> Optional[int]:
        logger.info(f"Getting buy price for item {item_id}")
        price = get_tp_item_price_by_id_from_db(item_id)
        buy_price = None
        try:
            buy_price = price.get("buys").get("unit_price")
        except Exception as e:
            logger.warning(f"Error getting buy price for item {item_id}. {e}")
        return buy_price

    def get_sell_price_from_item(self, item_id: str) -> Optional[int]:
        logger.info(f"Getting sell price for item {item_id}")
        price = get_tp_item_price_by_id_from_db(item_id)
        sell_price = None
        try:
            sell_price = price.get("sells").get("unit_price")
        except Exception as e:
            logger.warning(f"Error getting sell price for item {item_id}. {e}")
        return sell_price

    def get_price_from_item(
        self, item_id: str, trading_post_mode="sells"
    ) -> Optional[int]:
        logger.info(f"Getting {trading_post_mode} price for item {item_id}")
        price = get_tp_item_price_by_id_from_db(item_id)
        if not price:
            price = self.api.get_item_price_from_trading_post(item_id)
        trading_post_mode_price = None
        try:
            trading_post_mode_price = price.get("sells").get("unit_price")
        except Exception as e:
            logger.warning(
                f"Error getting {trading_post_mode} price for item {item_id}. {e}"
            )
        return trading_post_mode_price

    def is_junk_item(self, item_info: dict) -> bool:
        if item_info.get("rarity").lower() == "junk":
            return True
        return False

    def can_sell_item_to_vendor(self, item_info: dict) -> bool:
        flags = item_info.get("flags")
        if "NoSell" in flags:
            return False
        return True

    def get_item_vendor_value(self, item_info: dict) -> int:
        if item_info:
            item_vendor_value = item_info.get("vendor_value", 0)
            return item_vendor_value
        return 0

    def where_to_sell_item(self, item_id, item_info, inventory_item) -> Optional[str]:
        """Compares the price the item is being sold of the Trading Post with the price
        the item is being sold on a vendor and returns the best option."""
        vendor_value = 0
        tp_value = 0
        if self.can_sell_item_to_vendor(item_info):
            vendor_value = self.get_item_vendor_value(item_info) or 0
        if self.can_sell_item_on_trading_post(inventory_item):
            tp_value = self.get_price_from_item(item_id) or 0
        if vendor_value == 0 and tp_value == 0:
            logger.info("Item can't be sold")
            return None
        if vendor_value >= tp_value:
            return "vendor"
        return "trading_post"

    def can_sell_item_on_trading_post(self, inventory_item: dict) -> bool:
        if not inventory_item.get("binding"):
            return True
        return False

    def add_new_item_to_db(self, item_id: str):
        logger.info(f"Adding new item {item_id} to the database")
        item_info = self.api.fetch_item_info(item_id)
        self.api.add_item_info_to_db(item_info)

    def sort_items_by_value(self, items_dict: dict, order="desc"):
        """Sort items by value in descending(desc) or ascending(asc) order"""
        reverse = True if order == "desc" else False
        sorted_dict = dict(
            sorted(items_dict.items(), key=lambda item: item[1], reverse=reverse)
        )
        return sorted_dict

    def format_sorted_items_dict(self, items_dict: dict):
        """Format the items dict to a human readable format, adding the names of
        the items"""
        formatted_items_dict = {}
        for key in items_dict:
            formatted_items_dict[key] = {}
            formatted_items_dict[key]["name"] = get_item_name_from_db(key)
            formatted_items_dict[key]["price"] = items_dict[key]
        return formatted_items_dict

    def calculate_items_value(self, items: List[dict], trading_post_mode="sell") -> int:
        total_items_price = 0
        items_unit_price = {}
        items_price = {}
        for item in items:
            item_info = get_item_info_from_db(item.get("id"))
            if not item_info:
                item_info = self.api.fetch_item_info(item.get("id"))
                if not item_info:
                    logger.warning(f"No item with id {item.get('id')} found")
                    continue
                add_item_info_to_db(item_info)
            where_to_sell = self.where_to_sell_item(item.get("id"), item_info, item)
            if not where_to_sell:
                continue
            elif where_to_sell == "vendor":
                item_unit_price = self.get_item_vendor_value(item_info)
                item_price = item_unit_price * item.get("count")
                items_unit_price[item.get("id")] = item_unit_price
                items_price[item.get("id")] = item_price
                total_items_price += item_price
            elif where_to_sell == "trading_post":
                item_unit_price = self.get_price_from_item(
                    item.get("id"), trading_post_mode
                )
                item_price = item_unit_price * item.get("count")
                items_unit_price[item.get("id")] = item_unit_price
                items_price[item.get("id")] = item_price
                total_items_price += item_price
        return total_items_price

    def calculate_inventory_value(
        self,
        inventory_items: List[dict],
        trading_post_mode="sell",
        character_name: Optional[str] = None,
    ) -> int:
        character_name = character_name or self.api.get_active_character()
        inventory_price = self.calculate_items_value(inventory_items, trading_post_mode)
        logger.info(f"Inventory value: {inventory_price}")
        self.inventory_value = inventory_price
        add_current_inventory_value_to_db(inventory_price, character_name)
        return inventory_price

    def calculate_materials_storage_value(
        self,
        material_storage_items: List[dict],
        trading_post_mode="sell",
        character_name: Optional[str] = None,
    ) -> int:

        character_name = character_name or self.api.get_active_character()
        materials_storage_price = self.calculate_items_value(
            material_storage_items, trading_post_mode
        )
        logger.info(f"materials_storage value: {materials_storage_price}")
        self.materials_value = materials_storage_price
        add_current_materials_storage_value_to_db(
            materials_storage_price, character_name
        )
        return materials_storage_price

    def calculate_profit(self):
        character_name = self.api.get_active_character()
        previous_inventory_value = get_current_inventory_value_from_db(character_name)
        previous_material_storage_value = get_current_material_storage_value_from_db(
            character_name
        )
        previous_total = previous_inventory_value + previous_material_storage_value

        current_inventory_value = self.calculate_inventory_value(
            self.api.get_character_inventory_items()
        )
        current_materials_storage_value = self.calculate_materials_storage_value(
            self.api.get_materials()
        )
        current_total = current_inventory_value + current_materials_storage_value
        profit = current_total - previous_total
        logger.info(f"Profit: {profit}")
        return profit

    def get_current_items_value(self, character_name: Optional[str] = None):
        character_name = character_name or self.api.get_active_character()
        current_inventory_value = self.calculate_inventory_value(
            self.api.get_character_inventory_items()
        )
        current_materials_storage_value = self.calculate_materials_storage_value(
            self.api.get_materials()
        )
        current_total = current_inventory_value + current_materials_storage_value
        return current_total

    def get_values(self, character_name: Optional[str] = None):
        character_name = character_name or self.api.get_active_character()
        current_inventory_value = self.calculate_inventory_value(
            self.api.get_character_inventory_items()
        )
        current_materials_storage_value = self.calculate_materials_storage_value(
            self.api.get_materials()
        )
        current_total = current_inventory_value + current_materials_storage_value
        return {
            "inventory_value": current_inventory_value,
            "materials_value": current_materials_storage_value,
            "total_value": current_total,
        }

    def get_current_total_value(self, character_name: Optional[str] = None):
        character_name = character_name or self.api.get_active_character()
        items_value = self.get_current_items_value(character_name)
        current_total = items_value + self.api.get_wallet_coins()
        return current_total

    def start_session(self, character_name: Optional[str] = None):
        if character_name:
            self.api.set_active_character(character_name)
        session_start_value = self.get_current_total_value(character_name)
        self.start_value = session_start_value
        logger.info(f"START VALUE: {self.start_value}")
        return {
            "start_value": session_start_value,
            "inventory_value": self.inventory_value,
            "materials_value": self.materials_value,
        }

    def update_session(self, character_name: Optional[str] = None):
        character_name = character_name or self.api.get_active_character()
        self.current_value = self.get_current_total_value(character_name)
        self.profit_value = self.current_value - self.start_value
        return {
            "current_value": self.current_value,
            "inventory_value": self.inventory_value,
            "materials_value": self.materials_value,
            "profit_value": self.profit_value,
        }
