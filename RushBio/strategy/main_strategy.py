from model import *
from strategy.roads import RoadNet, find_planet, dijkstra
from strategy.flying_group_advanced import AllFlyingGroups, find_group
from operator import itemgetter

flat = lambda t: [item for sublist in t for item in sublist]


# need_workers = {BuildingType.QUARRY: 0, BuildingType.FARM: 0,
#                 BuildingType.CAREER: 0, BuildingType.MINES: 0,
#                 BuildingType.FOUNDRY: 80, BuildingType.FURNACE: 80,
#                 BuildingType.BIOREACTOR: 80, BuildingType.CHIP_FACTORY: 90,
#                 BuildingType.ACCUMULATOR_FACTORY: 90, BuildingType.REPLICATOR: 175}

# basic = [(Resource.ORGANICS, BuildingType.FARM, 50, 2), (Resource.ORE, BuildingType.MINES, 0, 2),
#          (Resource.SAND, BuildingType.CAREER, 0, 2), (Resource.STONE, BuildingType.QUARRY, 0, 1)]

# advanced = [(BuildingType.FOUNDRY, 100, 3), (BuildingType.FURNACE, 100, 1),
#             (BuildingType.BIOREACTOR, 100, 1), (BuildingType.CHIP_FACTORY, 100, 1),
#             (BuildingType.ACCUMULATOR_FACTORY, 100, 1), (BuildingType.REPLICATOR, 200, 1)]


class MyStrategy:
    """MyStrategy"""

    """Карта дорог(граф)"""
    road_map: RoadNet

    """Словарь с летающими группами"""
    itinerary: dict

    """Планеты запланированные для стройки"""
    wait_build: dict

    """Список индексов игроков"""
    players: dict

    """Будущие постройки(группа уже летит к планете, без промежуточных)"""
    future_builds: list

    """Домашняя планета, где добываем камень."""
    home_planet: Planet

    """Словарь Resource: BuildingType"""
    relation: dict

    """Будущие перемещения(в тик 'X' совершить действие MoveAction('Y'))"""
    future_moves: list

    """Словарь планет по id объект Planet"""
    planets_id: dict

    mini_farms: dict

    def __init__(self, game: Game):
        MyStrategy.itinerary = {}
        MyStrategy.planets_id = {}
        for planet in game.planets:
            MyStrategy.planets_id[planet.id] = planet
            MyStrategy.itinerary[planet.id] = []
            if len(planet.worker_groups) != 0 and planet.worker_groups[0].player_index == game.my_index:
                MyStrategy.home_planet = planet.id
        MyStrategy.enemy_score_past = 0
        MyStrategy.players = {}
        for i in range(6):
            MyStrategy.players[i] = [game.players[i].team_index, i]
        MyStrategy.road_map = RoadNet(game.planets, game.my_index, game.max_travel_distance, MyStrategy.players, game.building_properties)
        MyStrategy.future_builds = []
        MyStrategy.future_moves = []
        MyStrategy.relation = {}
        MyStrategy.wait_build = {}
        MyStrategy.mini_farms = {}
        for building in game.building_properties:
            MyStrategy.relation[game.building_properties[building].produce_resource] = building

    @staticmethod
    def get_action(game: Game) -> Action:

        moves = []
        builds = []

        current_tick = game.current_tick
        print("Tick:", current_tick)

        for planet in game.planets:
            MyStrategy.planets_id[planet.id] = planet

        MyStrategy.road_map.vertices = game.planets
        MyStrategy.road_map.categorise_planets([])

        planets_id = MyStrategy.planets_id
        my_planets = MyStrategy.road_map.only_my_robots
        enemy_planets = MyStrategy.road_map.planets_with_enemy_robots
        road_map = MyStrategy.road_map
        find_path_to_all = road_map.find_path_from_one_to_one
        itinerary = MyStrategy.itinerary
        flying_groups = AllFlyingGroups(game.flying_worker_groups, game.my_index, find_path_to_all, itinerary,
                                        MyStrategy.players, planets_id)
        future_builds = MyStrategy.future_builds
        future_moves = MyStrategy.future_moves
        home_planet = planets_id[MyStrategy.home_planet]
        relation = MyStrategy.relation

        nearer = lambda pl: abs(home_planet.x - pl.x) + abs(home_planet.y - pl.y)

        if not len(my_planets) or (not len(enemy_planets) and not len(flying_groups.enemy_groups)):
            return Action([], [], Specialty.PRODUCTION)

        pl_with_buildings = {}
        for pl in my_planets:
            if pl.building != None:
                b = pl.building.building_type
                if b in pl_with_buildings.keys():
                    pl_with_buildings[b].append(pl)
                else:
                    pl_with_buildings[b] = [pl]
                if b in MyStrategy.wait_build.keys() and pl.id in MyStrategy.wait_build[b]:
                    MyStrategy.wait_build[b].remove(pl.id)

        if home_planet.resources != {} and home_planet.worker_groups != [] and [x for x in home_planet.worker_groups if
                                                                                x.player_index == game.my_index] != []:
            org_pl = find_planet(game.planets, harvestable_resource_to_find=Resource.ORGANICS)
            org = len(org_pl)
            for pl in org_pl:
                if BuildingType.FARM not in MyStrategy.wait_build.keys(): MyStrategy.wait_build[BuildingType.FARM] = []
                if [x for x in home_planet.worker_groups if x.player_index == game.my_index][0].number < 250: break
                if home_planet.resources[Resource.STONE] >= 250 and pl.building == None and pl.id not in \
                        MyStrategy.wait_build[BuildingType.FARM]:
                    MyStrategy.wait_build[BuildingType.FARM].append(pl.id)
                    moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
                                                                                home_planet.id, pl.id, 250,
                                                                                resource=Resource.STONE,
                                                                                build=BuildingAction(pl.id,
                                                                                                     BuildingType.FARM))
                    moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
                                                                                home_planet.id, pl.id,
                                                                                (1000 - 250 * org) // org)
                    home_planet.resources[Resource.STONE] -= 250

        for pl in [x for x in game.planets if x not in enemy_planets]:
            if pl.building != None and pl.building.building_type == BuildingType.FARM:
                if pl.id not in MyStrategy.mini_farms.keys():
                    distance_from_home = dijkstra(road_map.amount_vertices, road_map.net, pl.id, 1, road_map.vertices,
                                                  road_map.planets_with_enemy_robots, 0)[0]
                    pls = sorted(find_planet(game.planets, building_to_find=-1), key=lambda x: distance_from_home[x.id])
                    if len(pls) >= 2:
                        plb = pls[0]
                        plb2 = pls[1]
                        moves.append(MoveAction(pl.id, plb.id, 100, Resource.STONE))
                        future_builds.append(
                            [BuildingAction(plb.id, BuildingType.BIOREACTOR), current_tick + abs(plb.x - pl.x) + abs(plb.y - pl.y)])
                        moves.append(MoveAction(pl.id, plb2.id, 100, Resource.STONE))
                        future_builds.append(
                            [BuildingAction(plb2.id, BuildingType.BIOREACTOR), current_tick + abs(plb2.x - pl.x) + abs(plb2.y - pl.y)])
                        MyStrategy.mini_farms[pl.id] = [plb.id, plb2.id]
                else:
                    plb_id, plb2_id = MyStrategy.mini_farms[pl.id]
                    plb = [x for x in game.planets if x.id == plb_id][0]
                    plb2 = [x for x in game.planets if x.id == plb2_id][0]
                    workers = [x for x in plb.worker_groups if x.player_index == game.my_index]
                    workers2 = [x for x in plb2.worker_groups if x.player_index == game.my_index]
                    workers_on_pl = [x for x in pl.worker_groups if x.player_index == game.my_index]
                    if len(workers_on_pl) == 0 and workers != [] and plb.building != None:
                        moves.append(MoveAction(plb.id, pl.id, workers[0].number, None))
                    if len(workers_on_pl) == 0 and workers2 != [] and plb2.building != None:
                        moves.append(MoveAction(plb2.id, pl.id, workers2[0].number, None))

                    if workers != [] and plb.building != None and workers[0].number > 20:
                        moves.append(MoveAction(plb.id, pl.id, workers[0].number - 20, None))
                    if workers2 != [] and plb2.building != None and workers2[0].number > 20:
                        moves.append(MoveAction(plb2.id, pl.id, workers2[0].number, None))
                    if Resource.ORGANICS in pl.resources.keys():
                        number = min(50, pl.resources[Resource.ORGANICS])
                        if Resource.ORGANICS not in plb.resources.keys() or plb.resources[Resource.ORGANICS] < 100:
                            moves.append(MoveAction(pl.id, plb.id, number, Resource.ORGANICS))
                        if Resource.ORGANICS not in plb2.resources.keys() or plb2.resources[Resource.ORGANICS] < 100:
                            moves.append(MoveAction(pl.id, plb2.id, number, Resource.ORGANICS))

        moves, builds, future_builds, future_moves = update(current_tick, my_planets, flying_groups, moves, builds,
                                                            future_builds, future_moves, road_map)
        moves = road_map.go_to_home(moves, builds, future_builds, future_moves, current_tick, home_planet, flying_groups, [])

        print(moves)

        MyStrategy.road_map = road_map
        MyStrategy.itinerary = flying_groups.itinerary
        MyStrategy.future_builds = future_builds
        MyStrategy.future_moves = future_moves
        return Action(moves, builds, Specialty.PRODUCTION)


def update(current_tick, my_planets, flyings: AllFlyingGroups, moves, builds, buildings, future_moves,
           road_map: RoadNet):
    moves_update, update_future_builds = flyings.update_all_groups(current_tick)
    moves += moves_update
    # print("V", id(builds), builds)
    buildings += update_future_builds
    # print("B", id(buildings), builds)
    buildings.sort(key=itemgetter(1))
    # print(moves, buildings, sep='\n')
    index = 0
    for order, tick in buildings:
        # print(order)
        if tick > current_tick:
            break
        if order is not None:
            builds.append(order)
        index += 1
    # future_moves = flyings.i_am_to_young_to_die(future_moves, current_tick, my_planets, road_map)
    # # print("PPP", future_moves)
    # future_moves.sort(key=itemgetter(1))
    # index = 0
    # for order, tick in future_moves:
    #     # print(order, tick)
    #     if tick > current_tick:
    #         break
    #     if order is not []:
    #         moves.append(order)
    #     index += 1
    return moves, builds, buildings[index:], future_moves[index:]
