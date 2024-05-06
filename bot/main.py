from typing import Optional

from ares import AresBot
from ares.consts import UnitRole, ALL_STRUCTURES
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.group import AMoveGroup, PathGroupToTarget, StutterGroupBack

from cython_extensions import cy_closest_to, cy_distance_to

from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit
from sc2.units import Units
from sc2.position import Point2

import numpy as np

class AnglerBot(AresBot):
    def __init__(self, game_step_override: Optional[int] = None):
       
        super().__init__(game_step_override)

        self._assigned_scout: bool = False

    async def on_step(self, iteration: int):
        await super(AnglerBot, self).on_step(iteration)
        
        #retrieve all attacking units
        attacker: Units = self.mediator.get_units_from_role(role=UnitRole.ATTACKING)
    
        #retrieve main army if one has been assigned
        first_scout: Units = self.mediator.get_units_from_role(role=UnitRole.CONTROL_GROUP_ONE, unit_type=UnitTypeId.ZEALOT)
        self.pylon = self.structures(UnitTypeId.PYLON)
        ground_grid = self.mediator.get_ground_grid


        self.control_scout(
            first_scout=first_scout,
            target=self.game_info.map_center,
        )
        
        self.control_attackers(
            attackers=attacker,
            target=self.enemy_start_locations[0]
        )
        


        # at the start assign 1 random zealot to the scout role
        # This will remove them from the ATTACKING automatically
        if not self._assigned_scout and self.time > 2.0:
            self._assigned_scout = True
            zealots: Units = attacker(UnitTypeId.ZEALOT)
            if zealots:
                zealot = zealots.random
                self.mediator.assign_role(tag=zealot.tag, role=UnitRole.CONTROL_GROUP_ONE)
            
    # Set all units with ATTACKING to Center of the map
    def control_attackers(self, attackers: Units, target: Point2) -> None:
        group_maneuver: CombatManeuver = CombatManeuver()
        target: self.enemy_start_locations[0]
        #add group behaviors
        #hold position for the first 10 seoconds then attack
        if self.time > 20.0:
            group_maneuver.add(
                AMoveGroup(
                    group=attackers,
                    group_tags={r.tag for r in attackers},
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

    
