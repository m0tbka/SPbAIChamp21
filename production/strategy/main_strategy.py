from model import *
from strategy.roads import RoadNet, find_planet, dijkstra
from strategy.flying_group_advanced import AllFlyingGroups, find_group
from operator import itemgetter

flat = lambda t: [item for sublist in t for item in sublist]

need_workers = {BuildingType.QUARRY: 0, BuildingType.FARM: 0,
                BuildingType.CAREER: 0, BuildingType.MINES: 0,
                BuildingType.FOUNDRY: 80, BuildingType.FURNACE: 80,
                BuildingType.BIOREACTOR: 80, BuildingType.CHIP_FACTORY: 90,
                BuildingType.ACCUMULATOR_FACTORY: 90, BuildingType.REPLICATOR: 175}

basic = [(Resource.ORGANICS, BuildingType.FARM, 50, 2), (Resource.ORE, BuildingType.MINES, 0, 2),
         (Resource.SAND, BuildingType.CAREER, 0, 2), (Resource.STONE, BuildingType.QUARRY, 0, 1)]

advanced = [(BuildingType.FOUNDRY, 100, 3), (BuildingType.FURNACE, 100, 1),
            (BuildingType.BIOREACTOR, 100, 1), (BuildingType.CHIP_FACTORY, 100, 1),
            (BuildingType.ACCUMULATOR_FACTORY, 100, 1), (BuildingType.REPLICATOR, 200, 1)]


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

    def __init__(self, game: Game):
        MyStrategy.itinerary = {}
        for planet in game.planets:
            MyStrategy.itinerary[planet.id] = []
            if len(planet.worker_groups) != 0 and planet.worker_groups[0].player_index == game.my_index:
                MyStrategy.home_planet = planet.id
        MyStrategy.enemy_score_past = 0
        MyStrategy.players = {}
        for i in range(6):
            MyStrategy.players[i] = [game.players[i].team_index, i]
        MyStrategy.road_map = RoadNet(game.planets, game.my_index, game.max_travel_distance, MyStrategy.players)
        MyStrategy.future_builds = []
        MyStrategy.future_moves = []
        MyStrategy.relation = {}
        MyStrategy.wait_build = {}
        for building in game.building_properties:
            MyStrategy.relation[game.building_properties[building].produce_resource] = building
        if len(find_planet(game.planets, Resource.ORGANICS)) == 4:
            basic[0] = (Resource.ORGANICS, BuildingType.FARM, 50, 4)

    @staticmethod
    def get_action(game: Game) -> Action:

        moves = []
        builds = []

        current_tick = game.current_tick
        print("Tick:", current_tick)

        MyStrategy.road_map.vertices = game.planets

        my_planets = MyStrategy.road_map.only_my_robots
        enemy_planets = MyStrategy.road_map.planets_with_enemy_robots
        road_map = MyStrategy.road_map
        itinerary = MyStrategy.itinerary
        flying_groups = AllFlyingGroups(game.flying_worker_groups, game.my_index, road_map.find_path_from_one_to_one,
                                        itinerary,
                                        MyStrategy.players)
        MyStrategy.road_map.categorise_planets(flying_groups.enemy_groups)
        home_planet = [x for x in game.planets if x.id == MyStrategy.home_planet][0]
        future_builds = MyStrategy.future_builds
        future_moves = MyStrategy.future_moves
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

        if home_planet.resources != {} and home_planet.worker_groups != [] and [x for x in home_planet.worker_groups if
                                                                                x.player_index == game.my_index] != []:
            """Базовая добыча ресурсов"""
            for res, harv, add_num, max_count in basic:
                if harv not in MyStrategy.wait_build.keys(): MyStrategy.wait_build[harv] = []
                if harv not in pl_with_buildings.keys(): pl_with_buildings[harv] = []
                if max_count <= len(MyStrategy.wait_build[harv]) + len(pl_with_buildings[harv]): continue

                pl = [x for x in find_planet(game.planets, harvestable_resource_to_find=res, building_to_find=-1)
                      if x.id not in flat(MyStrategy.wait_build.values())]

                if [x for x in home_planet.worker_groups if x.player_index == game.my_index][0].number < 50: continue

                if len(pl) != 0 and home_planet.resources[Resource.STONE] >= 50:
                    bpl = sorted(pl, key=nearer)[0]
                    moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
                                                                                home_planet.id, bpl.id, 50,
                                                                                resource=Resource.STONE,
                                                                                build=BuildingAction(bpl.id, harv))
                    moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
                                                                                home_planet.id, bpl.id, add_num,
                                                                                resource=None, build=None)
                    MyStrategy.wait_build[harv].append(bpl.id)
                    home_planet.resources[Resource.STONE] -= 50
            """Продвинутая переработка ресурсов"""
            for btype, cost, num in advanced:
                if btype not in MyStrategy.wait_build.keys(): MyStrategy.wait_build[btype] = []
                if btype not in pl_with_buildings.keys(): pl_with_buildings[btype] = []
                if num <= len(MyStrategy.wait_build[btype]) + len(pl_with_buildings[btype]): continue
                distance_from_home = \
                    dijkstra(road_map.amount_vertices, road_map.net, home_planet.id, 1, road_map.vertices,
                             road_map.planets_with_enemy_robots, 0)[0]

                pls = sorted([x for x in find_planet(game.planets, building_to_find=-1)
                              if x.id not in flat(MyStrategy.wait_build.values())],
                             key=lambda x: distance_from_home[x.id])
                if len(pls) == 0 or home_planet.resources[Resource.STONE] < cost or \
                        [x for x in home_planet.worker_groups if x.player_index == game.my_index][
                            0].number < cost: continue
                pl = pls[0]
                print(btype, pl.id)
                moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
                                                                            home_planet.id, pl.id, cost,
                                                                            resource=Resource.STONE,
                                                                            build=BuildingAction(pl.id, btype))
                MyStrategy.wait_build[btype].append(pl.id)
                home_planet.resources[Resource.STONE] -= cost
                break

        """Возврат бездельников с планет"""
        for pl_id in list(set(flat(MyStrategy.wait_build.values()))):
            pl = [x for x in game.planets if x.id == pl_id][0]
            if pl.building != None and MyStrategy.itinerary[pl_id] == []:
                MyStrategy.wait_build[pl.building.building_type].remove(pl_id)
                count = need_workers[pl.building.building_type]
                moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
                                                                            pl_id, home_planet.id, count,
                                                                            resource=None, build=None)

        moves, builds, future_builds, future_moves = update(current_tick, my_planets, flying_groups, moves, builds,
                                                            future_builds, future_moves)

        print(moves)

        MyStrategy.road_map = road_map
        MyStrategy.itinerary = flying_groups.itinerary
        MyStrategy.future_builds = future_builds
        MyStrategy.future_moves = future_moves
        return Action(moves, builds, Specialty.PRODUCTION)


def update(current_tick, my_planets, flyings: AllFlyingGroups, moves, builds, buildings, future_moves):
    moves_update, update_future_builds = flyings.update_all_groups(current_tick)
    moves += moves_update
    buildings += update_future_builds
    buildings.sort(key=itemgetter(1))
    # print(moves, buildings, sep='\n')
    index = 0
    for order, tick in buildings:
        if tick > current_tick:
            break
        if order is not None:
            builds.append(order)
        index += 1
    # moves_update, update_future_moves = flyings.i_am_to_young_to_die(current_tick, my_planets)
    # moves += moves_update
    # future_moves += update_future_moves
    # future_moves.sort(key=itemgetter(1))
    # print("PPP", future_moves)
    # index = 0
    # for order, tick in future_moves:
    #     print(order, tick)
    #     if tick > current_tick:
    #         break
    #     if order[0] is not []:
    #         moves.append(order[0])
    #     index += 1

    return moves, builds, buildings[index:], future_moves[index:]
