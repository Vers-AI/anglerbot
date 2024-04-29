from typing import Optional

from ares import AresBot
from ares.consts import UnitRole, ALL_STRUCTURES
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.group import AMoveGroup

from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit
from sc2.units import Units
from sc2.position import Point2

class AnglerBot(AresBot):
    def __init__(self, game_step_override: Optional[int] = None):
       
        super().__init__(game_step_override)

        self._assigned_main_army: bool = False

    async def on_step(self, iteration: int):
        await super(AnglerBot, self).on_step(iteration)
        
        #retrieve all attacking units
        attackers: Units = self.mediator.get_units_from_role(role=UnitRole.ATTACKING)
    
        #retrieve main army if one has been assigned
        main_army: Units = self.mediator.get_units_from_role(role=UnitRole.CONTROL_GROUP_ONE, unit_type=UnitTypeId.ZEALOT)

        self.control_main_army(
            main_army=main_army,
            target=self.enemy_start_locations[0]
        )
        
        self.control_attackers(
            attackers=attackers,
            target=self.game_info.map_center
        )


        # at 10 seconds assign all zealots to MAIN_ARMY role
        # This will remove them from the ATTACKING automatically
        if not self._assigned_main_army and self.time > 2.0:
            self._assigned_main_army = True
            zealots: list[Unit] = [
                u for u in attackers if u.type_id == UnitTypeId.ZEALOT
            ]
            for zealot in zealots:
                self.mediator.assign_role(tag=zealot.tag, role=UnitRole.CONTROL_GROUP_ONE
                )
            
    # Set all units with ATTACKING to Center of the map
    def control_attackers(self, attackers: Units, target: Point2) -> None:
        group_maneuver: CombatManeuver = CombatManeuver()
        target: self.enemy_start_locations[0]
        #add group behaviors
        #hold position for the first 10 seoconds then attack
        if self.time > 10.0:
            group_maneuver.add(
                AMoveGroup(
                    group=attackers,
                    group_tags={r.tag for r in attackers},
                    target=target,
                )
            )
            self.register_behavior(group_maneuver)

    def control_main_army(self, main_army: Units, target: Point2) -> None:
        #declare a new group maneuver
        group_maneuver: CombatManeuver = CombatManeuver()
        target: self.enemy_start_locations[0]
        #add group behaviors
        group_maneuver.add(
            AMoveGroup(
                group= main_army,
                group_tags={r.tag for r in main_army},
                target=target
            )
        )
        self.register_behavior(group_maneuver)
    


    async def on_unit_created(self, unit: Unit) -> None:
        await super(AnglerBot, self).on_unit_created(unit)
        #if a zealot is created assign it to the attacking role
        if unit.type_id == UnitTypeId.ZEALOT or unit.type_id == UnitTypeId.STALKER:
            self.mediator.assign_role(tag=unit.tag, role=UnitRole.ATTACKING)

    
