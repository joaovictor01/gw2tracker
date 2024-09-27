import os
import pathlib
import pprint
from datetime import datetime

# from deepdiff import DeepDiff
# from deepdiff.helper import CannotCompare
from loguru import logger

from database import get_item_info_from_db

printer = pprint.PrettyPrinter()


def get_current_file_path():
    return pathlib.Path(__file__).parent.resolve()


def get_ids_from_items_added(diff: dict):
    added_items_ids = []
    added_items = diff.get("dictionary_item_added")
    for item in added_items:
        item.replace("\n", " ")
        added_item_id = item.split("root[")[1].split("]")[0].strip()
        logger.debug(f"Added item id: {added_item_id}")
        added_items_ids.append(added_item_id)
    return added_items_ids


def get_ids_from_items_removed(diff: dict):
    added_items_ids = []
    added_items = diff.get("dictionary_item_removed")
    for item in added_items:
        item.replace("\n", "").strip()
        added_item_id = item.split("root[")[1].split("]")[0].strip()
        logger.debug(f"Removed item id: {added_item_id}")
        added_items_ids.append(added_item_id)
    return added_items_ids


def get_ids_from_items_changed(diff: dict):
    items_changed_ids = []
    changed_items = diff.get("values_changed")
    items_changed_keys = [key for key in changed_items]
    for key in items_changed_keys:
        key.replace("\n", "").strip()
        item_changed_id = key.split("root[")[1].split("]")[0].strip()
        items_changed_ids.append(item_changed_id)
    logger.debug(f"Changed items ids: {str(items_changed_ids)}")
    return items_changed_ids


def convert_list_to_dict(lst: list) -> dict:
    dictionary = {}
    for item in lst:
        dictionary[str(item.get("id"))] = item
    return dictionary


def is_item_sellable(item_id: str) -> bool:
    item_info = get_item_info_from_db(item_id)
    if not item_info:
        logger.warning(f"Item {item_id} not found in the database")
    if "NoSell" in item_info.get("flags") or "AccountBound" in item_info.get("flags"):
        return False
    return True


def is_date_difference_greater_than_one_day(date1, date2):
    difference = date1 - date2
    if difference.days > 0:
        return True
    return False


def is_older_than_one_day(date):
    if (datetime.now() - date).days > 0:
        return True
    return False


def create_program_folder(folder_name: str):
    home_folder_path = os.path.expanduser("~")
    program_folder_path = os.path.join(home_folder_path, folder_name)
    if not os.path.exists(program_folder_path):
        os.makedirs(program_folder_path)
        logger.info("Folder created: " + str(program_folder_path))
    return program_folder_path


def create_session_file(folder_name: str):
    datetime_str = datetime.now().isoformat(sep="_", timespec="seconds")
    return os.path.join(
        create_program_folder(folder_name), f"session_{datetime_str}.json"
    )


def format_value(value) -> str:
    value = int(value)
    gold = int(value / (100 * 100))
    silver = int(int(str(value / (100 * 100)).split(".")[1]) / 100)
    copper = int(str(value / 100).split(".")[1])
    formatted_value = f"{gold} gold, {silver} silver, {copper} copper"
    return formatted_value
