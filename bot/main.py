from typing import Optional

from ares import AresBot
from ares.consts import UnitRole, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.group import AMoveGroup, StutterGroupBack
from ares.managers.squad_manager import UnitSquad


from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit
from sc2.units import Units
from sc2.position import Point2

import numpy as np

class AnglerBot(AresBot):
    def __init__(self, game_step_override: Optional[int] = None):
       
        super().__init__(game_step_override)

        self._assigned_scout: bool = False
        self._assigned_range: bool = False
        self.defence_postion: Point2 = None
        self.arrive: bool = False
 
    def delayed_start(self):
        if len(self.pylon) == 0:
            print("No pylon found")
            return
        print(self.game_info.map_center)
        # check what map the bot is playing on
        if self.game_info.local_map_path == "PlateauMicro_1.SC2Map":
            # find out which side of the map we are on.
            if self.game_info.map_center.x > self.pylon[0].position.x:
                print("Starting on the left")
                self.defence_postion = Point2((34,26))
            else:
                print("Starting on the right")
                self.defence_postion = Point2((38,26))
        else:
            print("The maps is BotMicroArena_6:", self.game_info.local_map_path)


    async def on_step(self, iteration: int):
        await super(AnglerBot, self).on_step(iteration)
        self.pylon = self.structures(UnitTypeId.PYLON)
        self.check_defensive_position()

        if self.defence_postion is None:
            self.delayed_start()
        
        #retrieve all attacking units
        attacker: Units = self.mediator.get_units_from_role(role=UnitRole.ATTACKING)
    
        #retrieve main army if one has been assigned
        first_scout: Units = self.mediator.get_units_from_role(role=UnitRole.CONTROL_GROUP_ONE, unit_type=UnitTypeId.ZEALOT)
        range_attack: Units = self.mediator.get_units_from_role(role=UnitRole.CONTROL_GROUP_TWO, unit_type=UnitTypeId.STALKER)

        ground_grid = self.mediator.get_ground_grid
        enemy_units: Units = self.enemy_units

        current_target: Point2 = self.defence_postion
        if self.arrive:
            current_target = self.enemy_start_locations[0]


        self.control_scout(
            first_scout=first_scout,
            target=current_target
        )
        
        self.control_attackers(
            attackers=attacker,
            target=current_target
        )

        self.control_range_attack(
            range_attack=range_attack,
            target=current_target,
            ground_grid=ground_grid
        )
        


        # at the start assign 1 random zealot to the scout role
        # This will remove them from the ATTACKING automatically
        if not self._assigned_scout and self.time > 1.0:
            self._assigned_scout = True
            zealots: Units = attacker(UnitTypeId.ZEALOT)
            if zealots:
                zealot = zealots.random
                self.mediator.assign_role(tag=zealot.tag, role=UnitRole.CONTROL_GROUP_ONE)

        # at the start assign  all the stalkers to the range attack role
        if not self._assigned_range and self.time > 1.0:
            self._assigned_range = True
            stalkers: Units = attacker(UnitTypeId.STALKER)
            if stalkers:
                for stalker in stalkers:
                    self.mediator.assign_role(tag=stalker.tag, role=UnitRole.CONTROL_GROUP_TWO)


    # Set all units with ATTACKING to Center of the map
    def control_attackers(self, attackers: Units, target: Point2) -> None:
        group_maneuver: CombatManeuver = CombatManeuver()
        #add group behaviors
        #hold position for the first 10 seoconds then attack
        if self.time > 5.0:
            group_maneuver.add(
                AMoveGroup(
                    group=attackers,
                    group_tags={r.tag for r in attackers},
                    target=target,
                )
            )
            self.register_behavior(group_maneuver)
        
    # Group Behavior for range attackers
    def control_range_attack(self, range_attack: Units, target: Point2, ground_grid: np.ndarray) -> None:
        group_maneuver: CombatManeuver = CombatManeuver()
        squads: list[UnitSquad] = self.mediator.get_squads(role=UnitRole.CONTROL_GROUP_TWO, squad_radius=9.0)
        


        for squad in squads:
            squad_position: Point2 = squad.squad_position
            units: list[Unit] = squad.squad_units
            squad_tags: set[int] = squad.tags
            
            # retreive close enemy to the range stalker squad
            close_ground_enemy: Units = self.mediator.get_units_in_range(
                start_points=[squad_position],
                distances=11.5,
                query_tree=UnitTreeQueryType.EnemyGround,
            )[0]
            
            target_unit = close_ground_enemy[0] if close_ground_enemy else None
            squad_position: Point2 = squad.squad_position
            

            #hold position for the first 20 seconds, then attack enemy start location unless there is an enemy then stutter back 
            if target_unit:
                group_maneuver.add(
                    StutterGroupBack(
                        group=units,
                        group_tags=squad_tags,
                        group_position=squad_position,
                        target=target_unit,
                        grid=ground_grid,
                    )
                )
            elif self.time > 5.0:
                group_maneuver.add(
                    AMoveGroup(
                        group=range_attack,
                        group_tags={r.tag for r in range_attack},
                        target=target,
                    )
                )
            self.register_behavior(group_maneuver)
        

    def control_scout(self, first_scout: Units, target: Point2) -> None:
        #declare a new group maneuver
        group_maneuver: CombatManeuver = CombatManeuver()
       
        #move scout to the center of the map the map if there is no enemy at the start of the game
    
        if not self.enemy_units and self.time < 20.0:
            target = self.game_info.map_center
        
        # Fix this logic to make the scout react when it sees an enemy
        # elif self.enemy_units and self.time < 20.0:
        #    target = self.start_location.position  # Not the permenant location, just a placeholder
        #    print(target)
        
        else:
            target = self.enemy_start_locations[0]
        
        group_maneuver.add(
            AMoveGroup(
                group=first_scout,
                group_tags={r.tag for r in first_scout},
                target=target,
            )
        )
        
        self.register_behavior(group_maneuver)
    


    async def on_unit_created(self, unit: Unit) -> None:
        await super(AnglerBot, self).on_unit_created(unit)
        #if a zealot is created assign it to the attacking role
        if unit.type_id == UnitTypeId.ZEALOT or unit.type_id == UnitTypeId.STALKER:
            self.mediator.assign_role(tag=unit.tag, role=UnitRole.ATTACKING)
        
    def check_defensive_position(self):
        if self.arrive:
            return
        if not self.enemy_units:
            return
        # check the nearest unit to the defensive_position
        if self.defence_postion:
            closest_unit: Unit = self.units.closest_to(self.defence_postion)
            if closest_unit:
                if closest_unit.distance_to(self.defence_postion) < 2:
                    self.arrive = True
             

    
