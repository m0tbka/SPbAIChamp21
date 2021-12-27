from model import *
from strategy.roads import RoadNet, find_planet, find_path_from_one_to_one
from strategy.flying_group_advanced import AllFlyingGroups


# from strategy.resources_advanced import ResourceAdv


class MyStrategy:
    """MyStrategy"""

    """Карта дорог(граф)"""
    road_map: RoadNet

    """Словарь с летающими группами"""
    itinerary: dict

    """Планеты запланированные для стройки"""
    wait_build: dict
    wait_build_adv: list

    """Список индексов игроков"""
    players: dict

    my_old_wg: dict

    my_planet_id: int 
    built: dict

    def __init__(self, game: Game):
        MyStrategy.itinerary = {}
        for planet in game.planets:
            MyStrategy.itinerary[planet.id] = []
            if len(planet.worker_groups) != 0 and planet.worker_groups[0].player_index == game.my_index:
                MyStrategy.my_planet_id = planet.id
        MyStrategy.enemy_score_past = 0
        MyStrategy.players = {}
        for i in range(6):
            MyStrategy.players[i] = game.players[i].team_index
        MyStrategy.road_map = RoadNet(game.planets, game.my_index, game.max_travel_distance, MyStrategy.players)
        MyStrategy.wait_build = {}
        MyStrategy.wait_build_adv = []
        MyStrategy.my_old_wg = {}
        MyStrategy.built = {}

    @staticmethod
    def get_action(game: Game) -> Action:

        moves = []
        builds = []

        current_tick = game.current_tick
        #print("Tick:", current_tick)

        MyStrategy.road_map.vertices = game.planets
        MyStrategy.road_map.categorise_planets()

        my_planets = MyStrategy.road_map.only_my_robots
        enemy_planets = MyStrategy.road_map.planets_with_enemy_robots
        road_map = MyStrategy.road_map
        find_path_to_all = road_map.find_path_to_all
        itinerary = MyStrategy.itinerary
        flying_groups = AllFlyingGroups(game.flying_worker_groups, game.my_index, find_path_to_all, itinerary, MyStrategy.players)
        start_planet = list(filter(lambda x: x.id == MyStrategy.my_planet_id,game.planets))[0]
        moves += flying_groups.update_all_groups(current_tick)

        nearer = lambda pl: abs(start_planet.x - pl.x) + abs(start_planet.y - pl.y)

        if not len(my_planets) or (not len(enemy_planets) and not len(flying_groups.enemy_groups)):
            return Action([], [], None)

        pl_with_buildings = {}
        for pl in my_planets:
            if pl.building != None:
                b = pl.building.building_type
                if b in pl_with_buildings.keys():
                    pl_with_buildings[b][0].append(pl)
                    pl_with_buildings[b][1] += 1
                else:
                    pl_with_buildings[b]= [[pl], 1]

        for b, [pls, _] in pl_with_buildings.items():
            if b not in MyStrategy.built.keys():
                MyStrategy.built[b] = {}
                for pl in pls:
                    MyStrategy.built[b][pl.id] = False
            else:
                for pl in pls:
                    if pl.id not in MyStrategy.built[b].keys():
                        MyStrategy.built[b][pl.id] = False
        
        keys = list(MyStrategy.built.keys())
        for b in keys:
            if b not in pl_with_buildings.keys():
                MyStrategy.built.pop(b, None)

        for b, [pls, _] in pl_with_buildings.items():
            for pl in pls:
                if pl.id in MyStrategy.wait_build.keys():
                    MyStrategy.wait_build.pop(pl.id, None)

        basic = [(Resource.ORGANICS, BuildingType.FARM, 50, 2), (Resource.ORE, BuildingType.MINES, 0, 2),
                 (Resource.SAND, BuildingType.CAREER, 0, 2), (Resource.STONE, BuildingType.QUARRY, 0, 1)]
        
        advanced = [(BuildingType.FOUNDRY, 100, 3), (BuildingType.FURNACE, 100, 1),
                    (BuildingType.BIOREACTOR,100, 1), (BuildingType.CHIP_FACTORY, 100, 1),
                    (BuildingType.ACCUMULATOR_FACTORY, 100, 1)]

        if start_planet.resources != {}:
            for res, harv, add_num, max_count in basic:
                pl = []
                if harv in pl_with_buildings.keys():
                    pl = [x for x in find_planet(game.planets, harvestable_resource_to_find=res) if x.id not in [x.id for x in pl_with_buildings[harv][0]] and max_count>len(pl_with_buildings[harv][0])+len([1 for x in MyStrategy.wait_build.items() if x[1] == harv]) and x.id not in MyStrategy.wait_build.keys()]
                else:
                    pl = [x for x in find_planet(game.planets, harvestable_resource_to_find=res) if x.id not in MyStrategy.wait_build.keys() and max_count > len([1 for x in MyStrategy.wait_build.items() if x[1] == harv])]
                if len(pl) != 0 and start_planet.resources[Resource.STONE] >= 50:
                    bpl = sorted(pl, key=nearer)[0]
                    
                    MyStrategy.wait_build[bpl.id] = harv
                    moves += flying_groups.make_flying_group(current_tick, start_planet.id, bpl.id, 50, resource=Resource.STONE)
                    moves += flying_groups.make_flying_group(current_tick, start_planet.id, bpl.id, add_num)
                    start_planet.resources[Resource.STONE] -= 50
            
            if start_planet.resources[Resource.STONE] >= 200 and start_planet.worker_groups != [] and start_planet.worker_groups[0].number >= 100:
                pls = sorted([x for x in game.planets if x.building == None and x not in enemy_planets and x.id not in MyStrategy.wait_build.keys()], key=nearer)
                if len(pls) != 0:
                    pl = pls[0]
                    for btype, cost, num in advanced:
                        if btype not in pl_with_buildings.keys():
                            if num > len([1 for x in MyStrategy.wait_build.items() if x[1] == btype]):
                                MyStrategy.wait_build[pl.id] = btype
                                moves += flying_groups.make_flying_group(current_tick, start_planet.id, pl.id, cost, resource=Resource.STONE)
                                start_planet.resources[Resource.STONE] -= cost
                                break
                        elif num > len(pl_with_buildings[btype][0]) + len([1 for x in MyStrategy.wait_build.items() if x[1] == btype]):
                            MyStrategy.wait_build[pl.id] = btype
                            moves += flying_groups.make_flying_group(current_tick, start_planet.id, pl.id, cost, resource=Resource.STONE)
                            start_planet.resources[Resource.STONE] -= cost
                            break
                        
            if start_planet.worker_groups != [] and start_planet.worker_groups[0].number >= 200:  
                pls = sorted([x for x in game.planets if x.building == None and x not in enemy_planets and x.id not in MyStrategy.wait_build.keys()], key=nearer)

                if len(pls) and BuildingType.REPLICATOR not in pl_with_buildings.keys() and BuildingType.REPLICATOR not in MyStrategy.wait_build.values() and start_planet.resources[Resource.STONE] >= 200:
                    pl = pls[0]
                    MyStrategy.wait_build[pl.id] = BuildingType.REPLICATOR
                    moves += flying_groups.make_flying_group(current_tick, start_planet.id, pl.id, 200, resource=Resource.STONE)
                    start_planet.resources[Resource.STONE] -= 200
            if current_tick > 40:
                for res, harv, add_num, max_count in basic:
                    if harv not in pl_with_buildings.keys() or len(pl_with_buildings[harv][0]) < max_count:
                        pl = [x for x in find_planet(game.planets, harvestable_resource_to_find=res) if x.building == None and x.id not in [y.target_planet for y in game.flying_worker_groups if y.player_index == game.my_index] ]
                        if len(pl) != 0 and start_planet.resources[Resource.STONE] >= 50:
                            bpl = sorted(pl, key=nearer)[0]
                            
                            MyStrategy.wait_build[bpl.id] = harv
                            moves += flying_groups.make_flying_group(current_tick, start_planet.id, bpl.id, 50, resource=Resource.STONE)
                            moves += flying_groups.make_flying_group(current_tick, start_planet.id, bpl.id, add_num)
                            start_planet.resources[Resource.STONE] -= 50
                pls = sorted([x for x in game.planets if x.building == None and x not in enemy_planets and x.id not in MyStrategy.wait_build.keys()], key=nearer)
                if len(pls) != 0:
                    pl = pls[0]
                    for btype, cost, num in advanced:
                        if btype not in pl_with_buildings.keys() or num > len(pl_with_buildings[btype][0]) + len([1 for x in MyStrategy.wait_build.items() if x[1] == btype]):
                            MyStrategy.wait_build[pl.id] = btype
                            moves += flying_groups.make_flying_group(current_tick, start_planet.id, pl.id, cost, resource=Resource.STONE)
                            start_planet.resources[Resource.STONE] -= cost
                            break
                            



        for pl, t in MyStrategy.wait_build.items():
            builds.append(BuildingAction(pl, t))
        
        my_new_wg = {pl.id: (list(filter(lambda wg: wg.player_index == game.my_index, pl.worker_groups))[0], pl.building) for pl in my_planets}
        # for pl, data in my_new_wg.items():
        #     wg, b = data
        #     pln = list(filter(lambda x: x.id == pl, game.planets))[0]
        #     if pl in MyStrategy.my_old_wg.keys() and b == None and pln.building == None and pl not in [y.departure_planet for y in game.flying_worker_groups if y.player_index == game.my_index]:
        #         moves += flying_groups.make_flying_group(current_tick, pl, start_planet.id, wg.number)

        for b, data in MyStrategy.built.items():
            print(data)
            for pl, ret in data.items():
                if pl in my_new_wg.keys() and pl in MyStrategy.my_old_wg.keys():
                    pll = list(filter(lambda x: x.id == pl,game.planets))[0]
                    workers = list(filter(lambda wg: wg.player_index == game.my_index, pll.worker_groups))
                    need_workers = {BuildingType.QUARRY: (50, 50), BuildingType.FARM: (100, 100),
                                    BuildingType.CAREER: (50, 50), BuildingType.MINES: (50, 50),
                                    BuildingType.FOUNDRY: (100, 20), BuildingType.FURNACE: (100, 20),
                                    BuildingType.BIOREACTOR: (100, 20), BuildingType.CHIP_FACTORY: (100, 10),
                                    BuildingType.ACCUMULATOR_FACTORY: (100, 10), BuildingType.REPLICATOR: (200, 200)}[b]
                    if len(workers) == 0:
                        moves += flying_groups.make_flying_group(current_tick, start_planet.id, pl, need_workers)
                    elif not ret:
                        workers_count = need_workers[0]
                        if workers[0].number > need_workers[1]:
                            print("ret", pl, b)
                            moves += flying_groups.make_flying_group(current_tick, pl, start_planet.id, workers_count-need_workers[1])
                            MyStrategy.built[b][pl] = True

        if BuildingType.REPLICATOR in pl_with_buildings.keys():
            pl = pl_with_buildings[BuildingType.REPLICATOR][0][0]
            workers = list(filter(lambda wg: wg.player_index == game.my_index, pl.worker_groups))[0]
            if workers.number > 35:
                print(workers.number)
                moves += flying_groups.make_flying_group(current_tick, pl.id, start_planet.id, 10)


        #moves += flying_groups.i_am_to_young_to_die(current_tick, my_planets, enemy_planets)


        MyStrategy.itinerary = flying_groups.itinerary
        MyStrategy.my_old_wg = my_new_wg

        temp = list(MyStrategy.wait_build.items())
        for pl, b in temp:
            if pl not in MyStrategy.itinerary.keys():
                MyStrategy.wait_build.pop(pl)

        return Action(moves, builds, Specialty.PRODUCTION)
