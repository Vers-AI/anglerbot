import random
import sys
from os import path
from pathlib import Path
from typing import List

from sc2 import maps
from sc2.data import AIBuild, Difficulty, Race
from sc2.main import run_game
from sc2.player import Bot, Computer
from sc2.bot_ai import BotAI
from sc2.constants import UnitTypeId
from sc2.position import Point2


sys.path.append("ares-sc2/src/ares")
sys.path.append("ares-sc2/src")
sys.path.append("ares-sc2")

import yaml

from bot.main import AnglerBot
from ladder import run_ladder_game

# change if non default setup / linux
# if having issues with this, modify `map_list` below manually
MAPS_PATH: str = "D:\\StarCraft II\\Maps"
CONFIG_FILE: str = "config.yml"
MAP_FILE_EXT: str = "SC2Map"
MY_BOT_NAME: str = "MyBotName"
MY_BOT_RACE: str = "MyBotRace"

class DummyBot(BotAI):
    def __init__(self):
        super().__init__()

    async def on_step(self, iteration: int):
        target = self.game_info.map_center
        if self.enemy_start_locations:
            target = self.enemy_start_locations[0]
        elif self.enemy_structures:
            target = self.enemy_structures.first.position
        for unit in self.units.idle:
            unit.attack(target)

class DefendBot(BotAI):
    def __init__(self):
        super().__init__()

    async def on_step(self, iteration: int):
        # await super(DefendBot, self).on_step(iteration)
        if self.structures(UnitTypeId.PYLON):
            target = self.structures(UnitTypeId.PYLON)[0]
            # target = Point2((0,0))  #Debug for testing against pylon only victory
        else:
            target = self.start_location

        for unit in self.units.idle:
            unit.move(target)


def main():
    bot_name: str = "MyBot"
    race: Race = Race.Protoss

    __user_config_location__: str = path.abspath(".")
    user_config_path: str = path.join(__user_config_location__, CONFIG_FILE)
    # attempt to get race and bot name from config file if they exist
    if path.isfile(user_config_path):
        with open(user_config_path) as config_file:
            config: dict = yaml.safe_load(config_file)
            if MY_BOT_NAME in config:
                bot_name = config[MY_BOT_NAME]
            if MY_BOT_RACE in config:
                race = Race[config[MY_BOT_RACE].title()]

    bot1 = Bot(race, AnglerBot(), bot_name)
    bot2 = Bot(Race.Protoss, DefendBot())


    if "--LadderServer" in sys.argv:
        # Ladder game started by LadderManager
        print("Starting ladder game...")
        result, opponentid = run_ladder_game(bot1)
        print(result, " against opponent ", opponentid)
    else:
        # Local game
        map_list: List[str] = [
             "PlateauMicro_1",
             # "BotMicroArena_6"
        ]
        

        # random_race = random.choice([Race.Zerg, Race.Terran, Race.Protoss])
        # random_race = random.choice([Race.Terran])
        # random_race = random.choice([Race.Zerg,])
        random_race = random.choice([Race.Protoss])
        print("Starting local game...")
        run_game(
            maps.get(random.choice(map_list)),
            [
                bot1,
                bot2,
            ],
            realtime=False,
        )


# Start game
if __name__ == "__main__":
    main()
