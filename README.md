#  Guild Wars 2 Session Tracker

Track profit while playing Guild Wars 2. This program will use your API key to get your inventory and material storage content when starts and will calculate every minute (or interval you set) to calculate the profit.

## Installation

First, get your API key from the Arenanet site: https://account.arena.net/applications

Create an API Key with the permissions:

+ wallet
+ inventories
+ tradingpost
+ account

Copy and paste the API key on the `config.json` file, in the `api_key` field, and set the character you will be playing in the session on the field `character_name`

```json
{
    "api_key": "PUT_YOUR_API_KEY_HERE",
    "character": "Your Character Name Here",
    "update_every_minutes": 1
}
```

run the MongoDB
```
docker-compose up --build
```
to run the MongoDB docker container that will be used to store items, trading post and your account and character information to avoid making too many requests to the API that is slower.

then run the installer, you will need `python, docker, docker-compose` installed:
```bash
pip3 install virtualenv
virtualenv venv
source venv/bin/activate
pip3 install pyinstaller
pyinstaller --clean -y -n "GW2Tracker" --add-data="src/config.json:src" --windowed main.py
```

## Running

Run the MongoDB database
```
docker-compose up -d
```

run the application:

Run the application that will be stored at `dist/GW2Tracker/`

