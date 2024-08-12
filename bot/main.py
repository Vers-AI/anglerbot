from typing import Optional

from ares import AresBot
from ares.consts import UnitRole, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.group import AMoveGroup, PathGroupToTarget
from ares.behaviors.combat.individual import AMove, StutterUnitBack, KeepUnitSafe
from ares.managers.squad_manager import UnitSquad


from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit
from sc2.units import Units
from sc2.position import Point2

from cython_extensions import cy_attack_ready, cy_pick_enemy_target, cy_in_attack_range

import numpy as np

class AnglerBot(AresBot):
    def __init__(self, game_step_override: Optional[int] = None):
       
        super().__init__(game_step_override)

        self._assigned_scout: bool = False
        self._assigned_range: bool = False
        self.defence_postion: Point2 = None
        self.defence_stalker_position: Point2 = None
       
        ## Flags
        self.arrive: bool = False
        self.combat_started = False
        self.defense_mode = False


    def delayed_start(self):
        self.full_attack: bool = False
        self.enemy_supply: int = -1 # track enemy supply



        if len(self.pylon) == 0:
            # print("No pylon found")
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
            if self.game_info.map_center.x > self.pylon[0].position.x:
                print("Starting on the left")
                self.defence_postion = Point2((34,36))
                self.defence_stalker_position = Point2((34,34))
            else:
                print("Starting on the right")
                self.defence_postion = Point2((38,36))
                self.defence_stalker_position = Point2((38,34))

    async def on_step(self, iteration: int):
        await super(AnglerBot, self).on_step(iteration)
        self.pylon = self.structures(UnitTypeId.PYLON)
        self.check_defensive_position()
        enemy_units: Units = self.enemy_units
        self.unit_scores = self.calculate_scores(enemy_units)

        if self.defence_postion is None:
            self.delayed_start()
        
        if enemy_units:
            self.combat_started = True
            self.enemy_supply = self.get_total_supply(enemy_units)
        else:
            self.enemy_supply = 0

        #retrieve all attacking units
        attacker: Units = self.mediator.get_units_from_role(role=UnitRole.ATTACKING)
    
        #retrieve main army if one has been assigned
        first_scout: Units = self.mediator.get_units_from_role(role=UnitRole.CONTROL_GROUP_ONE, unit_type=UnitTypeId.ZEALOT)
        # range_attack: Units = self.mediator.get_units_from_role(role=UnitRole.CONTROL_GROUP_TWO, unit_type=UnitTypeId.STALKER)

        ground_grid = self.mediator.get_ground_grid
        

        
        
        # Control of the Current Target
        if self.defense_mode:
            current_target = self.pylon[0].position
        elif self.enemy_supply == 0 and self.combat_started:
            self.full_attack = True
            current_target = self.enemy_start_locations[0]
        else:
            current_target: Point2 = self.defence_postion



        self.control_scout(
            first_scout=first_scout,
            target=current_target
        )
        
        self.control_attackers(
            attackers=attacker,
            target=current_target
        )

       

        # at the start assign 1 random zealot to the scout role
        # This will remove them from the ATTACKING automatically
        if not self._assigned_scout and self.time > 1.0:
            self._assigned_scout = True
            zealots: Units = attacker(UnitTypeId.ZEALOT)
            if zealots:
                zealot = zealots.random
                self.mediator.assign_role(tag=zealot.tag, role=UnitRole.CONTROL_GROUP_ONE)

       
    
        ### Pylon Defense
        if self.pylon:
            proximity_ground_enemy: Units = self.mediator.get_units_in_range(
                        start_points=[self.pylon[0].position],
                        distances= 8.0,
                        query_tree=UnitTreeQueryType.EnemyGround,
                        return_as_dict=False,
                    )[0].filter(lambda u: not u.is_memory)
    
            if proximity_ground_enemy:
                self.defense_mode = True
            else:
                self.defense_mode = False

    def calculate_scores(self, units: Units):
        scores = {}
        for unit in units:
            missing_health_percent = (unit.health_max - unit.health) / unit.health_max
            scores[unit.tag] = 100 - missing_health_percent
        return scores

    # Set all units with ATTACKING to Center of the map
    def control_attackers(self, attackers: Units, target: Point2) -> None:
        group_maneuver: CombatManeuver = CombatManeuver()
        squads: list[UnitSquad] = self.mediator.get_squads(role=UnitRole.ATTACKING, squad_radius=12.0)
        grid: np.ndarray = self.mediator.get_ground_grid
    

        for squad in squads:
            squad_position: Point2 = squad.squad_position
            units: list[Unit] = squad.squad_units
            squad_tags: set[int] = squad.tags

            if len(units) == 0:
                continue

            # retreive close enemy to the attacking squad
            close_ground_enemy: Units = self.mediator.get_units_in_range(
                    start_points=[squad_position],
                    distances=15,
                    query_tree=UnitTreeQueryType.EnemyGround,
                    return_as_dict=False,
                )[0].filter(lambda u: not u.is_memory and not u.is_structure)

            target_unit = close_ground_enemy[0] if close_ground_enemy else None
            squad_position: Point2 = squad.squad_position

            # if len(self.enemy_units) > 0:
            #     target_unit = sorted(self.enemy_units, key=lambda x: self.unit_scores[x.tag] - (x.distance_to(units[0].position) * x.distance_to(units[0].position)), reverse=True)[0]
            #     print("Found Best Target: {} Health: {}/{}".format(target_unit.tag, target_unit.health, target_unit.health_max))

            if close_ground_enemy:
                melee: list[Unit] = [u for u in units if u.ground_range <= 3]
                ranged: list[Unit] = [u for u in units if u.ground_range > 3]
                melee_tags: list[int] = [u.tag for u in melee]
                if ranged:   
                    for unit in ranged:
                        ranged_maneuver = CombatManeuver()
                        target_unit = sorted(self.enemy_units, key=lambda x: self.unit_scores[x.tag] - (x.distance_to(unit.position) * x.distance_to(unit.position)), reverse=True)[0]
                        if unit.shield_health_percentage < 0.2 and unit.weapon_cooldown != 0:
                            ranged_maneuver.add(
                                KeepUnitSafe(unit, grid)
                            )
                        else:
                            ranged_maneuver.add(StutterUnitBack(unit=unit, target=target_unit, grid=grid))
                        self.register_behavior(ranged_maneuver)

                if melee:
                    # target_unit = sorted(self.enemy_units, key=lambda x: self.unit_scores[x.tag] - (x.distance_to(melee[0].position) * x.distance_to(melee[0].position)), reverse=True)[0]
                    target_unit = cy_pick_enemy_target(close_ground_enemy)
                    melee_maneuver = CombatManeuver()
                    melee_maneuver.add(
                        AMoveGroup(
                            group=melee,
                            group_tags=melee_tags,
                            target=target_unit.position,
                        )
                    )
                    if target_unit:
                     print(f"Found target {target_unit.position}")
                    
                    self.register_behavior(melee_maneuver)
            else:
                group_maneuver.add(
                    AMoveGroup(
                        group=units,
                        group_tags=squad_tags,
                        target=target.position,
                    )
                )
                self.register_behavior(group_maneuver)
    
        
    
        

    def control_scout(self, first_scout: Units, target: Point2) -> None:
        #declare a new group maneuver
        group_maneuver: CombatManeuver = CombatManeuver()
       
        #move scout to the center of the map the map if there is no enemy at the start of the game else remove the scout from the group
    
        if not self.enemy_units:
            target = self.game_info.map_center
        
        
        else:
            self.mediator.switch_roles(from_role=UnitRole.CONTROL_GROUP_ONE, to_role=UnitRole.ATTACKING)
           
        
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
    
    
    
    
             

    
