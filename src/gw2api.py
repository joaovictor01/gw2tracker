import sys
import pprint
import urllib.parse
from typing import List, Optional

import requests
from dotenv import load_dotenv
from loguru import logger
from src.helpers import is_item_sellable
from src.database import (
    add_inventory_items_to_db,
    add_trading_post_price_to_db,
    add_trading_post_prices_to_db,
    add_items_info_to_db,
    add_currencies_to_db,
    get_currencies_from_db,
    add_coins_amount_to_db,
)

printer = pprint.PrettyPrinter()
logger.remove()
logger.add(sys.stderr, level="INFO")

load_dotenv()


class Gw2Api:
    def __init__(self, api_key: str):
        self.base_url = "https://api.guildwars2.com/v2"
        self.owned_items_tp_prices = {}
        self.active_character = ""
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
        if not is_item_sellable(item_id):
            logger.warning("Item not sellable")
            return None
        response = requests.get(
            f"{self.base_url}/commerce/prices/{item_id}", headers=self.headers
        )
        if response.status_code < 200 or response.status_code > 299:
            logger.error("Failed to fetch item price")
            return None

        logger.info("Successfully fetched item price")
        add_trading_post_price_to_db(response.json())
        return response.json()

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
