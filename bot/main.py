from time import sleep
from typing import Optional

from ares import AresBot
from ares.consts import UnitRole, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.group import AMoveGroup, PathGroupToTarget
from ares.behaviors.combat.individual import AMove, StutterUnitBack, KeepUnitSafe, PathUnitToTarget
from ares.managers.squad_manager import UnitSquad


from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit
from sc2.units import Units
from sc2.position import Point2, Point3


from cython_extensions import cy_pick_enemy_target

import numpy as np

class AnglerBot(AresBot):
    def __init__(self, game_step_override: Optional[int] = None):
       
        super().__init__(game_step_override)

        self._assigned_scout: bool = False
        self._assigned_range: bool = False
        self.defence_position: list[Point2] = []
        self.defence_stalker_position: Point2 = None
        self.map = None
       
        ## Flags
        self.arrive: bool = False
        self.melee_combat_started = False
        self.defense_mode = False
        self.delayed = False
        self.second_phase_position = False
        self.launch_late_attack = False

    # Debug 
    def _draw_debug_sphere_at_point(self, point: Point2):
        height = self.get_terrain_z_height(point)  # get the height in world coordinates
        radius = 1                                 # set the radius of the sphere
        point3 = Point3((point.x, point.y, height))  # convert the 2D point to a 3D point
        self._client.debug_sphere_out(point3, radius, color=Point3((255, 0, 0)))   


    def delayed_start(self):
        self.full_attack: bool = False
        self.enemy_supply: int = -1 # track enemy supply


        if len(self.pylon) == 0:
            # print("No pylon found")
            return
        print("center", self.game_info.map_center)
        print("enemy pylon", self.enemy_pylon[0].position)

        # check what map the bot is playing on
        if self.game_info.local_map_path == "PlateauMicro_1.SC2Map":
            self.map = "PM"
            # find out which side of the map we are on.
            # TODO -Adjust formation for Terran Match ups
            if self.game_info.map_center.x > self.pylon[0].position.x:
                print("Starting on the left - PM")
                self.defence_stalker_position = self.game_info.map_center + Point2((-7, 0))
                #self.defence_position = self.game_info.map_center  #+ Point2((4 , -4))
                self.defence_position = [
                    self.game_info.map_center + Point2((-4, 1.5)),
                    self.game_info.map_center + Point2((-4, 0.5)),
                    self.game_info.map_center + Point2((-4, -1.5)),
                    self.game_info.map_center + Point2((-4, -0.5)),
                ]
            else:
                print("Starting on the right - PM")
                self.defence_stalker_position = self.game_info.map_center + Point2((6, 0))
                # self.defence_position = self.game_info.map_center + Point2((-4, -4))
                self.defence_position = [
                    self.game_info.map_center + Point2((4, 1.5)),
                    self.game_info.map_center + Point2((4, 0.5)),
                    self.game_info.map_center + Point2((4, -1.5)),
                    self.game_info.map_center + Point2((4, -0.5)),
                ]
            
        else:
            self.map = "BMA"
            print("The maps is BotMicroArena_6:", self.game_info.local_map_path)
            if self.game_info.map_center.x > self.pylon[0].position.x:
                print("Starting on the left")
                self.defence_stalker_position = Point2((34,34))
            else:
                print("Starting on the right")
                self.defence_stalker_position = Point2((38,34))
            
            self.assign_defense_positions()

        
        self.delayed = True
        



    def assign_defense_positions(self):
        # Get the coordinates of the vision blockers
        vision_blockers = [
            Point2((43.6, 26.25)),
            Point2((43.6, 27.25)),
            Point2((43.6, 28.25)),
            Point2((43.6, 29.25)),
            Point2((28.4, 26.25)),
            Point2((28.4, 27.25)),
            Point2((28.4, 28.25)),
            Point2((28.4, 29.25)),
        ]
        # Sort vision blockers by their distance to the starting position
        sorted_blockers = sorted(vision_blockers, key=lambda blocker: blocker.distance_to(self.pylon[0].position))

        # Assign the four closest blockers to defense positions
        self.defence_position = sorted_blockers[:4]    
    
    async def on_step(self, iteration: int):
        await super(AnglerBot, self).on_step(iteration)
        self.pylon = self.structures(UnitTypeId.PYLON)
        self.enemy_pylon = self.enemy_structures(UnitTypeId.PYLON)
        
        if self.enemy_pylon:
        
            enemy_units: Units = self.enemy_units
            self.unit_scores = self.calculate_scores(enemy_units)
            melee_units = self.mediator.get_units_from_role(role=UnitRole.ATTACKING, unit_type={UnitTypeId.ZEALOT})
            if not self.delayed: 
                self.delayed_start()
            
            # self.check_defensive_position()
            self.check_attack_position()
            
            
            if enemy_units: # used to track enemies for final attack
                self.enemy_supply = self.get_total_supply(enemy_units)
                self.melee_combat_started = self.check_melee_combat_started(melee_units)
            else:
                self.enemy_supply = 0

            #retrieve all attacking units
            attacker: Units = self.mediator.get_units_from_role(role=UnitRole.ATTACKING)
            first_scout: Units = self.mediator.get_units_from_role(role=UnitRole.CONTROL_GROUP_ONE)

            

            
            # Current Target
            #TODO - Set coordinate of armry to go around if Launch_late_attack is true and it on map PM
            if not self.melee_combat_started and self.time > 40:
                self.launch_late_attack = True
                if self.full_attack or self.check_defensive_position():
                    self.full_attack = True
                    self.current_target = self.enemy_pylon[0].position
                    self.current_target_ranged = self.enemy_pylon[0].position
                    #print("should attack from defensive position now")
                else:
                    if map == "BMA":
                        #print("should circle around to attack now - BMA")
                        self.current_target = self.defence_stalker_position
                        self.current_target_ranged = self.defence_stalker_position
                    else:
                        #print("should circle around to attack now - PM")
                        self.current_target = self.enemy_pylon[0].position
                        self.current_target_ranged = self.enemy_pylon[0].position
            # elif not self.melee_combat_started and 20 < self.time < 40:
            #     self.second_phase_position = True
            #     self.current_target
            #     self.defence_position = sorted_blockers[4:8]        
                    
            elif self.defense_mode and self.pylon:
                print("changing to defense")
                #todo for PM increase the sensitivity of the enemy being close to the pylon
                self.current_target = self.pylon[0].position
                self.current_target_ranged = self.pylon[0].position
            elif self.full_attack or (self.enemy_supply == 0 and self.melee_combat_started):
                #print("changing to finishing blow")
                self.full_attack = True
                self.current_target = self.enemy_pylon[0].position
                self.current_target_ranged = self.enemy_pylon[0].position
            else:
                self.current_target = self.game_info.map_center # default for the melee should be adjusted if too far from range
                self.current_target_ranged: Point2 = self.defence_stalker_position
                
            # Scout controls
            if map == "PM":
                # at the start assign 1 random zealot to the scout role
                # This will remove them from the ATTACKING automatically
                if not self._assigned_scout and self.time > 1.0:
                    self._assigned_scout = True
                    zealots: Units = attacker(UnitTypeId.ZEALOT)
                    if zealots:
                        zealot = zealots.random
                        self.mediator.assign_role(tag=zealot.tag, role=UnitRole.CONTROL_GROUP_ONE)
            elif self.launch_late_attack:
                if not self._assigned_scout:
                    self._assigned_scout = True
                    zealots: Units = attacker(UnitTypeId.ZEALOT)
                    if zealots:
                        zealot = zealots.random
                        self.mediator.assign_role(tag=zealot.tag, role=UnitRole.CONTROL_GROUP_ONE)

                
            if first_scout:
                self.control_scout(
                    first_scout=first_scout,
                )

                
            
            self.control_attackers(
                attackers=attacker,
            )

        
            # sleep(0.1) #sleep timer to slow down the bot
            

            ### Pylon Defense
            if self.pylon and iteration >= 10:
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
        else:
            pass
        

    def check_melee_combat_started(self, melee_units: Units) -> bool:
        if self.melee_combat_started:
            return True

        if self.map == "BMA":
            if self.check_melee_shields(melee_units):
                print("Melee combat started - Shield Damage", self.time_formatted)
                return True
            if self.check_enemy_on_high_ground(melee_units[0].position3d.z):
                print("Melee combat started - Enemy HighGround", self.time_formatted)
                return True
        else:
            if self.check_melee_shields(melee_units):
                print("Melee combat started - Shield Damage", self.time_formatted)
                return True    
            
        return False
        

    #check if the enemy unit is on highround
    def check_enemy_on_high_ground(self, zpos: float) -> bool:
        for unit in self.enemy_units:
            if unit.position3d.z > zpos + 0.5:
                return True
        return False

    def calculate_scores(self, units: Units) -> dict:
        """Calculate health scores for each unit in the given Units object."""
        scores = {}
        for unit in units:
            missing_health = unit.health_max - unit.health
            missing_health_percent = missing_health / unit.health_max
            score = 100 - missing_health_percent
            scores[unit.tag] = score
        return scores

    
    def check_melee_shields(self, melee_units: Units) -> bool:
        """
        Check if any of the melee units have taken any damage.
        """
        for unit in melee_units:
            if unit.shield < unit.shield_max:
                print("Shield: {} Max: {}".format(unit.shield, unit.shield_max))

                return True
        return False

    # Set all units with ATTACKING to Center of the map
    def control_attackers(self, attackers: Units) -> None:
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
                    distances= 8.0,
                    query_tree=UnitTreeQueryType.EnemyGround,
                    return_as_dict=False,
                )[0].filter(lambda u: not u.is_memory and not u.is_structure)

            target_unit = close_ground_enemy[0] if close_ground_enemy else None
            squad_position: Point2 = squad.squad_position
            
            # breaking units into ranged and melee
            melee: list[Unit] = [u for u in units if u.ground_range <= 3]
            ranged: list[Unit] = [u for u in units if u.ground_range > 3]
            melee_tags: list[int] = [u.tag for u in melee]

            # if len(self.enemy_units) > 0:
            #     target_unit = sorted(self.enemy_units, key=lambda x: self.unit_scores[x.tag] - (x.distance_to(units[0].position) * x.distance_to(units[0].position)), reverse=True)[0]
            #     print("Found Best Target: {} Health: {}/{}".format(target_unit.tag, target_unit.health, target_unit.health_max))

        
            if ranged:
                if not (self.arrive or self.melee_combat_started) and self.map == "PM":
                    group_maneuver.add(
                        # TODO Adjust success at distance, increase danger distance, increase success threshold
                        PathGroupToTarget(
                            start=squad_position,
                            group=units,
                            group_tags=squad_tags,
                            grid=grid,
                            target=self.current_target_ranged,
                            success_at_distance=5.0,
                            sense_danger=True,
                            danger_distance=5.0,
                            danger_threshold=0.5,
                        )
                    )
                    # print("Ranged Target: ", self.current_target_ranged)
                    self.register_behavior(group_maneuver)

                elif close_ground_enemy:
                    for unit in ranged:
                        ranged_maneuver = CombatManeuver()
                        target_unit = sorted(self.enemy_units, key=lambda x: self.unit_scores[x.tag] - (x.distance_to(unit.position) * x.distance_to(unit.position)), reverse=True)[0]
                        if (unit.shield_health_percentage < 0.2 and unit.weapon_cooldown != 0) or self.check_ramps(unit):
                            ranged_maneuver.add(
                                KeepUnitSafe(unit, grid)
                            )
                        else:
                            ranged_maneuver.add(StutterUnitBack(unit=unit, target=target_unit, grid=grid))
                        self.register_behavior(ranged_maneuver)
                else:
                    group_maneuver.add(
                        AMoveGroup(
                            group=units,
                            group_tags=squad_tags,
                            target=self.current_target_ranged,
                        )
                    )
                    self.register_behavior(group_maneuver)


            if melee:
                if not self.melee_combat_started:
                    if self.full_attack or self.arrive and self.map == "PM":
                        # TODO Adjust success at distance, increase danger distance, increase success threshold
                        group_maneuver.add(
                            PathGroupToTarget(
                                start=squad_position,
                                group=melee,
                                group_tags=squad_tags,
                                grid=grid,
                                target=self.current_target,
                                success_at_distance=5.0,
                                danger_distance=5.0,
                                danger_threshold=0.5,
                                sense_danger=True,
                            )
                        )
                        #print("Target: ", self.current_target)
                        self.register_behavior(group_maneuver)
                    elif self.launch_late_attack:
                        group_maneuver.add(
                            AMoveGroup(
                                group=melee,
                                group_tags=squad_tags,
                                target=self.current_target,
                                )
                            )
                        self.register_behavior(group_maneuver)
                    else:
                        # print("Not Melee combat started")
                        for i, unit in enumerate(melee):
                            melee_maneuver = CombatManeuver()
                            position = self.defence_position[i % len(self.defence_position)]
                            
                            melee_maneuver.add(
                                PathUnitToTarget(
                                    unit=unit,
                                    target=position,
                                    grid=grid,
                                    success_at_distance=1.0,
                                )
                            )
                            self.register_behavior(melee_maneuver)
                            if self.map == "BMA":
                                unit.hold_position(queue=True)
                        # else:
                        #     # TODO - Set a better targer (current_target investigate)
                        #     group_maneuver.add(
                        #         AMoveGroup(
                        #             group=melee,
                        #             group_tags=squad_tags,
                        #             target=self.current_target,
                        #         )
                        #     )
                        #     self.register_behavior(group_maneuver)
                elif close_ground_enemy:
                    target_unit = cy_pick_enemy_target(close_ground_enemy)
                    melee_maneuver = CombatManeuver()
                    melee_maneuver.add(
                        AMoveGroup(
                            group=melee,
                            group_tags=melee_tags,
                            target=target_unit.position,
                        )
                    )
                    
                    self.register_behavior(melee_maneuver)
                else:
                    group_maneuver.add(
                        AMoveGroup(
                            group=melee,
                            group_tags=squad_tags,
                            target=self.current_target,
                        )
                    )
                    self.register_behavior(group_maneuver)


                    

    
        
    
        

    def control_scout(self, first_scout: Units) -> None:
        group_maneuver: CombatManeuver = CombatManeuver()
        target = self.current_target
        # TODO change the sensitivity of how close the scout gets before switching roles - use get_units_in_range or something
        if not self.enemy_units:
            target = self.enemy_pylon[0].position
        
        else:
            self.mediator.switch_roles(from_role=UnitRole.CONTROL_GROUP_ONE, to_role=UnitRole.ATTACKING)
       
           
        
        group_maneuver.add(
            AMoveGroup(
                group=first_scout,
                group_tags={r.tag for r in first_scout},
                target=target,
            )
        )
        
        # for unit in first_scout:
        #     print(f"Scout Unit {unit.tag} Position: {unit.position}")
        
        self.register_behavior(group_maneuver)
    


    async def on_unit_created(self, unit: Unit) -> None:
        await super(AnglerBot, self).on_unit_created(unit)
        #if a zealot is created assign it to the attacking role
        if unit.type_id == UnitTypeId.ZEALOT or unit.type_id == UnitTypeId.STALKER:
            self.mediator.assign_role(tag=unit.tag, role=UnitRole.ATTACKING)
        
    ## Defensive Position
    def check_defensive_position(self):
        if self.arrive:
            return True
        # TODO figure out if this is useful
        # if not self.enemy_units:
        #     return
        # check the nearest unit to the defensive_position
        if self.defence_stalker_position:
            all_units: Unit = self.units.further_than(3, self.defence_stalker_position)
            if all_units.empty:
                self.arrive = True
                print
        return self.arrive
    
    ## Attack Position
    def check_attack_position(self):
        if self.arrive:
            return True
        # check the nearest unit to enemy pylon
        if self.enemy_pylon:
            arrived_units: Unit = self.units.closer_than(4, self.enemy_pylon[0])
            if arrived_units:
                print("Arrived at Attack Position")
                self.arrive = True
        return self.arrive

    def check_ramps(self, inc_unit: Unit) -> bool:
        ramps = self.game_info.map_ramps
        for ramp in ramps:
            if self.is_visible(ramp.top_center):
                continue
            unit_at_bottom_of_ramp = inc_unit.position.distance_to(ramp.bottom_center) < 4
            if not unit_at_bottom_of_ramp:
                continue
            # loop enemies and see if close to ramp top center
            enemy_in_position = False
            for enemy_unit in self.enemy_units:
                if enemy_unit.ground_range < 2:
                    continue

                if enemy_unit.position.distance_to(ramp.top_center) < 4:
                    return True
            

            # if enemy_in_position and inc_unit.position.distance_to(ramp.bottom_center) < 4:
            #     print("Triggered Ramp Check: {}".format(inc_unit.position.distance_to(ramp.bottom_center)))
            #     return True

            # top_center = ramp.top_center
            # bottom_center = ramp.bottom_center
            # # Print the coordinates
            # print(f"Ramp top center: ({top_center.x}, {top_center.y})")
            # print(f"Ramp bottom center: ({bottom_center.x}, {bottom_center.y})")
        return False
    
    
             

    


