import os
import sys
import urllib.parse
from typing import List, Optional

import requests
from dotenv import load_dotenv
from loguru import logger

from database import (
    add_coins_amount_to_db,
    add_currencies_to_db,
    add_current_inventory_value_to_db,
    add_current_materials_storage_value_to_db,
    add_inventory_items_to_db,
    add_item_info_to_db,
    add_items_info_to_db,
    add_trading_post_price_to_db,
    add_trading_post_prices_to_db,
    get_currencies_from_db,
    get_item_info_from_db,
    get_tp_item_price_by_id_from_db,
)
from helpers import format_value, is_item_sellable

logger.remove()
logger.add(sys.stderr, level="INFO")

load_dotenv()

EXPENSIVE_LIMIT = 10000


class Gw2Api:
    def __init__(self, api_key: str):
        self.base_url = "https://api.guildwars2.com/v2"
        self.owned_items_tp_prices = {}
        self.active_character = ""
        if os.environ.get("GW2_API_KEY"):
            self.headers = {"Authorization": f"Bearer {api_key}"}
        else:
            self.headers = {"Authorization": f"Bearer {api_key}"}

    @staticmethod
    def url_encode(string: str) -> str:
        return urllib.parse.quote(string, safe="")

    def set_api_key(self, api_key: str):
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def set_active_character(self, name: str):
        logger.info(f"Setting active character: {name}")
        self.active_character = name

    def get_active_character(self):
        return self.active_character

    def get_character(self, character_name: str):
        character_name = character_name or self.active_character
        encoded_name = self.url_encode(character_name)
        response = requests.get(
            f"{self.base_url}/characters/{encoded_name}",
            headers=self.headers,
        )
        return response.json()

    def get_character_inventory(self, character_name: Optional[str] = None):
        character_name = character_name or self.active_character
        encoded_name = self.url_encode(character_name)
        response = requests.get(
            f"{self.base_url}/characters/{encoded_name}/inventory",
            headers=self.headers,
        )
        if response.status_code < 200 or response.status_code > 299:
            logger.warning("Failed to get character inventory")
            return None

        logger.info("Successfully fetched character inventory")
        return response.json()

    def get_character_inventory_items(self, character_name: Optional[str] = None):
        character_name = character_name or self.active_character
        logger.info(f"Getting items from character {character_name} inventory")
        items = []
        inventory = self.get_character_inventory(character_name)
        for bag in inventory["bags"]:
            for item in bag["inventory"]:
                if item:
                    items.append({**item, "character_name": character_name})
        add_inventory_items_to_db(items)
        return items

    def inventory_changes(self, character_name: str):
        pass

    def get_bank_content(self):
        logger.info("Getting bank content")
        response = requests.get(
            f"{self.base_url}/account/bank",
            headers=self.headers,
        )
        if response.status_code == 200:
            logger.info("Successfully fetched bank content")
            return response.json()
        else:
            logger.error("Failed to fetch bank content")
            return []

    def get_materials(self):
        response = requests.get(
            f"{self.base_url}/account/materials",
            headers=self.headers,
        )
        if response.status_code == 200:
            logger.info("Successfully fetched materials")
            return response.json()
        else:
            logger.error("Failed to fetch materials")
            return []

    def get_owned_items_ids(self, character_name: Optional[str] = None) -> List[str]:
        character_name = character_name or self.active_character
        inventory_items = self.get_character_inventory_items(character_name)
        bank_items = self.get_bank_content()
        materials = self.get_materials()
        all_items = inventory_items + bank_items + materials
        all_items_ids = []
        for item in all_items:
            if not item:
                continue
            all_items_ids.append(str(item.get("id")))
        return all_items_ids

    def get_prices_from_chunk(self, chunk: List[str]):
        items_url = str(",".join(chunk))

        response = requests.get(
            f"{self.base_url}/commerce/prices?ids={items_url}", headers=self.headers
        )
        if response.status_code >= 200 or response.status_code <= 299:
            logger.info("Successfully fetched trading post prices")
            return response.json()
        else:
            logger.error("Failed to fetch trading post prices")
            return []

    def chunk_list(self, lst: List[str], chunk_size: int):
        while len(lst) > chunk_size:
            chunk = lst[:chunk_size]
            del lst[:chunk_size]
            yield chunk

    def get_prices_from_trading_post(self, items: Optional[List[str]] = []):
        items = items or self.get_owned_items_ids()
        chunk_length = 30
        chunks = []
        chunks_prices = []

        while len(items) > chunk_length:
            chunk = items[:chunk_length]
            chunk_prices = self.get_prices_from_chunk(chunk)
            chunks_prices += chunk_prices
            chunks.append(chunk)
            del items[:chunk_length]

        self.owned_items_tp_prices = chunks_prices
        add_trading_post_prices_to_db(chunks_prices)

    def get_item_price_from_trading_post(self, item_id: str):

        if not get_item_info_from_db(item_id):
            self.fetch_item_info(item_id)
        if not is_item_sellable(item_id):
            logger.warning("Item not sellable")
            return None
        response = requests.get(
            f"{self.base_url}/commerce/prices/{item_id}", headers=self.headers
        )
        if response.status_code < 200 or response.status_code > 299:
            logger.error(f"Failed to fetch item {item_id} price")
            return None

        logger.info("Successfully fetched item price")
        add_trading_post_price_to_db(response.json())
        return response.json()

    def get_item_sell_price(self, item_id: str):
        tp_price = self.get_item_price_from_trading_post(item_id)
        if tp_price:
            return tp_price.get("sells").get("unit_price")
        return 0

    def get_item_buy_price(self, item_id: str):
        tp_price = self.get_item_price_from_trading_post(item_id)
        if tp_price:
            return tp_price.get("buys").get("unit_price")
        return 0

    def get_all_gw2_items_ids(self):
        response = requests.get(f"{self.base_url}/items", headers=self.headers)
        if response.status_code < 200 or response.status_code > 299:
            logger.error("Failed to fetch items")
            return []

        logger.info("Successfully fetched items")
        logger.info(f"Total items: {len(response.json())}")
        return response.json()

    def add_owned_items_info_to_db(self):
        items = []
        items_ids = self.get_owned_items_ids()
        for chunk in self.chunk_list(items_ids, 30):
            items_url = str(",".join(chunk))
            response = requests.get(
                f"{self.base_url}/items?ids={items_url}", headers=self.headers
            )
            if response.status_code < 200 or response.status_code > 299:
                logger.error("Failed to fetch items")
                return []

            logger.info("Successfully fetched items")
            items += response.json()
            logger.info(f"Total items: {len(response.json())}")
        add_items_info_to_db(items)

    def fetch_item_info(self, item_id: str):
        """
        Fetches item info from the GW2 API given an item id.

        Args:
            item_id (str): The id of the item to fetch.

        Returns:
            dict: The item info fetched from the API.
        """
        response = requests.get(
            f"{self.base_url}/items/{item_id}", headers=self.headers
        )
        if response.status_code < 200 or response.status_code > 299:
            logger.error(f"Failed to fetch item {item_id}")
            return None
        logger.info("Successfully fetched item")
        add_item_info_to_db(response.json())
        return response.json()

    def get_currency_name(self, currency_id: str):
        response = requests.get(
            f"{self.base_url}/currencies/{currency_id}", headers=self.headers
        )
        if response.status_code < 200 or response.status_code > 299:
            logger.error("Failed to fetch currency")
            return None
        logger.info("Successfully fetched currency")
        return response.json().get("name")

    def get_all_currencies_and_save_on_db(self):
        response = requests.get(
            "https://api.guildwars2.com/v2/currencies?ids=all", headers=self.headers
        )
        if response.status_code < 200 or response.status_code > 299:
            logger.error("Failed to fetch currencies")
            return None
        logger.info("Successfully fetched currencies")
        add_currencies_to_db(response.json())
        return response.json()

    def get_currencies_from_db(self):
        logger.info("Getting currencies from the database")
        currencies = get_currencies_from_db()
        if not currencies:
            currencies = self.get_all_currencies_and_save_on_db()
        return currencies

    def get_wallet_content(self):
        response = requests.get(f"{self.base_url}/account/wallet", headers=self.headers)
        if response.status_code < 200 or response.status_code > 299:
            logger.error("Failed to fetch wallet content")
            return None

        logger.info("Successfully fetched wallet content")
        return response.json()

    def get_wallet_coins(self) -> int:
        """Return the amount of coins from account wallet
        The "id" of the currency Coin in the Guild Wars 2 API is 1

        Returns:
            int: wallet coins
        """
        character_name = self.get_active_character()
        response = requests.get(f"{self.base_url}/account/wallet", headers=self.headers)
        if response.status_code < 200 or response.status_code > 299:
            logger.error("Failed to fetch wallet coins")
            return None
        for currency in response.json():
            if currency.get("id") == 1:
                logger.info("Successfully fetched wallet coins")
                coins_amount = currency.get("value")
                if not coins_amount:
                    logger.warning("Wallet coins not found")
                add_coins_amount_to_db(coins_amount, character_name)
                return coins_amount

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
            price = self.get_item_price_from_trading_post(item_id)
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

    def get_upgrades_from_inventory_item(self, inventory_item: dict) -> List[dict]:
        upgrades = inventory_item.get("upgrades")
        logger.info(f"Upgrades: {upgrades}")
        upgrades_info = []
        if not upgrades:
            return []
        for upgrade in upgrades:
            item_info = self.fetch_item_info(upgrade)
            upgrade_price = self.get_item_sell_price(upgrade)
            upgrades_info.append(
                {
                    "id": upgrade,
                    "name": item_info.get("name"),
                    "price": upgrade_price,
                    "formatted_price": format_value(upgrade_price),
                }
            )
        return upgrades_info

    def get_infusions_from_inventory_item(self, inventory_item: dict):
        infusions = inventory_item.get("infusions")
        infusions_info = []
        if not infusions:
            return []
        for infusion in infusions:
            item_info = self.fetch_item_info(infusion)
            infusion_price = self.get_item_sell_price(infusion)
            infusions_info.append(
                {
                    "id": infusion,
                    "name": item_info.get("name"),
                    "price": infusion_price,
                    "formatted_price": format_value(infusion_price),
                }
            )
        return infusions_info

    def check_inventory_items_upgrades_and_infusions_of_items(
        self, character_name: Optional[str] = None
    ) -> dict:
        upgrades = []
        infusions = []
        character_name = character_name or self.get_active_character()
        inventory_items = self.get_character_inventory_items(character_name)
        if not inventory_items:
            logger.error("Failed to fetch inventory items")
            return None
        logger.info("Successfully fetched inventory items")
        for item in inventory_items:
            upgrades_info = self.get_upgrades_from_inventory_item(item)
            if upgrades_info:
                upgrades.append(upgrades_info)
            infusions_info = self.get_infusions_from_inventory_item(item)
            if infusions_info:
                infusions.append(infusions_info)
        return {"upgrades": upgrades, "infusions": infusions}

    def check_expensive_item_on_inventory(self, character_name: Optional[str] = None):
        character_name = character_name or self.get_active_character()
        expensive_items = []
        inventory_items = self.get_character_inventory_items(character_name)
        if not inventory_items:
            logger.error("Failed to fetch inventory items")
            return None
        logger.info("Successfully fetched inventory items")
        for item in inventory_items:
            item_unit_price = 0
            item_info = get_item_info_from_db(item.get("id"))
            if not item_info:
                item_info = self.fetch_item_info(item.get("id"))
                if not item_info:
                    logger.warning(f"No item with id {item.get('id')} found")
                    continue
                add_item_info_to_db(item_info)
            where_to_sell = self.where_to_sell_item(item.get("id"), item_info, item)
            upgrades = self.get_upgrades_from_inventory_item(item)
            infusions = self.get_infusions_from_inventory_item(item)
            if not where_to_sell:
                continue
            elif where_to_sell == "vendor":
                item_unit_price = self.get_item_vendor_value(item_info)
            elif where_to_sell == "trading_post":
                item_unit_price = self.get_price_from_item(item.get("id"), "sell")
            if item_unit_price > EXPENSIVE_LIMIT:
                expensive_items.append(
                    {
                        "id": item.get("id"),
                        "name": item_info.get("name"),
                        "price": item_unit_price,
                        "formatted_price": format_value(item_unit_price),
                    }
                )
            for upgrade in upgrades:
                if upgrade.get("price") > EXPENSIVE_LIMIT:
                    expensive_items.append(
                        {
                            "id": upgrade.get("id"),
                            "name": upgrade.get("name"),
                            "price": upgrade.get("price"),
                            "formatted_price": upgrade.get("formatted_price"),
                        }
                    )

            for infusion in infusions:
                if infusion.get("price") > EXPENSIVE_LIMIT:
                    expensive_items.append(
                        {
                            "id": infusion.get("id"),
                            "name": infusion.get("name"),
                            "price": infusion.get("price"),
                            "formatted_price": infusion.get("formatted_price"),
                        }
                    )

        return expensive_items
