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

    """Исключения для планет(по сколько роботов должно быть) для go_to_home"""
    exception_planets: dict

    my_organics: list
    my_organics_workers: dict
    my_workers_on_organics: dict
    my_reactor: dict
    my_reactor_workers: dict
    used: dict

    def __init__(self, game: Game):
        MyStrategy.itinerary = {}
        MyStrategy.planets_id = {}
        MyStrategy.exception_planets = {}
        for planet in game.planets:
            MyStrategy.exception_planets[planet.id] = 0
            MyStrategy.planets_id[planet.id] = planet
            MyStrategy.itinerary[planet.id] = []
            if len(planet.worker_groups) != 0 and planet.worker_groups[0].player_index == game.my_index:
                MyStrategy.home_planet = planet.id
        MyStrategy.enemy_score_past = 0
        MyStrategy.players = {}
        for i in range(len(game.players)):
            MyStrategy.players[i] = [game.players[i].team_index, i]
        MyStrategy.road_map = RoadNet(game.planets, game.my_index, game.max_travel_distance, MyStrategy.players,
                                      game.building_properties)
        MyStrategy.future_builds = []
        MyStrategy.future_moves = []
        MyStrategy.relation = {}
        for building in game.building_properties:
            MyStrategy.relation[game.building_properties[building].produce_resource] = building
        distance = dijkstra(MyStrategy.road_map.amount_vertices, MyStrategy.road_map.net, MyStrategy.home_planet, 1,
                 MyStrategy.road_map.vertices, MyStrategy.road_map.planets_with_enemy_robots, 1)[0]
        MyStrategy.my_organics = sorted([p.id for p in
                                  find_planet(game.planets, harvestable_resource_to_find=Resource.ORGANICS, building_to_find=-1)], key=lambda x: distance[x][0])
        MyStrategy.my_reactor = {}
        MyStrategy.my_organics_workers = {}
        MyStrategy.my_reactor_workers = {}
        MyStrategy.my_workers_on_organics = {}
        MyStrategy.used = {}
        my_reactor = []
        for planet in MyStrategy.my_organics:
            distance = sorted(filter(lambda x: MyStrategy.planets_id[x[0]].building is None and x[0] not in my_reactor, [[k, v] for k, v in
                               dijkstra(MyStrategy.road_map.amount_vertices, MyStrategy.road_map.net, planet, 1,
                                        MyStrategy.road_map.vertices, MyStrategy.road_map.planets_with_enemy_robots, 1)[
                                   0].items()]), key=lambda x: x[1][0])
            MyStrategy.my_reactor[planet] = [distance[1][0], distance[2][0]]
            my_reactor.append(distance[1][0])
            my_reactor.append(distance[2][0])
            fly_time1 = distance[1][1][0] * 2
            fly_time2 = distance[2][1][0] * 2
            MyStrategy.my_organics_workers[planet] = (fly_time1 + fly_time2) * 20 + 80
            MyStrategy.my_reactor_workers[distance[1][0]] = fly_time1 * 20 + 20
            MyStrategy.my_reactor_workers[distance[2][0]] = fly_time2 * 20 + 20
            MyStrategy.exception_planets[planet] = MyStrategy.my_organics_workers[planet]
            MyStrategy.exception_planets[distance[1][0]] = MyStrategy.my_reactor_workers[distance[1][0]]
            MyStrategy.exception_planets[distance[2][0]] = MyStrategy.my_reactor_workers[distance[2][0]]
            MyStrategy.my_workers_on_organics[planet] = 0
            MyStrategy.used[planet] = [0, 0, 0]

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
        home_planet: Planet
        home_planet = planets_id[MyStrategy.home_planet]
        relation = MyStrategy.relation
        exception_planets = MyStrategy.exception_planets
        my_organics = MyStrategy.my_organics
        my_reactor = MyStrategy.my_reactor
        my_workers_on_organics = MyStrategy.my_workers_on_organics
        used = MyStrategy.used
        my_planets_id = {}
        for planet in my_planets:
            my_planets_id[planet.id] = planet

        if not len(my_planets) or current_tick < 0:
            return Action([], [], Specialty.PRODUCTION)

        if home_planet.building is None:
            builds.append(BuildingAction(home_planet.id, BuildingType.QUARRY))

        moves, builds, future_builds, future_moves = update(current_tick, my_planets, flying_groups, moves, builds,
                                                            future_builds, future_moves, road_map)

        # print("____________________")
        # print(moves)
        # print(future_moves)
        # print(builds)
        # print(future_builds)
        # print("____________________")

        print("+++++++++++++++")
        print(my_organics)
        print(my_reactor)
        # print(MyStrategy.my_reactor_workers)
        # print(MyStrategy.my_organics_workers)
        # print(exception_planets)
        print(my_workers_on_organics)
        print("+++++++++++++++")

        # """Проверка наличия ферм и их постройка"""
        # for farm in my_organics:
        #     """Нужно ли дослать роботов"""
        #     # print(planets_id[farm])
        #     if my_planets_id.get(planets_id[farm].id, None) is not None and my_planets_id[farm].building is not None \
        #             and my_planets_id.get(my_reactor[farm][0], None) is not None and my_planets_id.get(my_reactor[farm][0], None).building is not None \
        #             and my_planets_id.get(my_reactor[farm][1], None) is not None and my_planets_id.get(my_reactor[farm][1], None).building is not None:
        #         # print(1)
        #         if my_workers_on_organics[farm] < exception_planets[farm]:
        #             # print(2)
        #             # print(exception_planets[farm], my_workers_on_organics[farm])
        #             moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
        #                                                                         home_planet.id,
        #                                                                         planets_id[farm].id,
        #                                                                         exception_planets[farm] - my_workers_on_organics[farm])
        #     # Нужно ли строить
        #     if (len(find_group([group for planet in itinerary for group in itinerary[planet]],
        #                         target_planet=planets_id[farm].id)) == 0 and my_planets_id.get(planets_id[farm].id, None) is None) and home_planet.resources.get(Resource.STONE,
        #                                                                                                0) >= 50:
        #         # print(3)
        #         moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
        #                                                                     home_planet.id, planets_id[farm].id, 50,
        #                                                                     resource=Resource.STONE,
        #                                                                     build=BuildingAction(planets_id[farm].id,
        #                                                                                          BuildingType.FARM))
        #         moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
        #                                                                     home_planet.id, planets_id[farm].id, 30)
        #         home_planet.resources[Resource.STONE] -= 50

        """Проверка наличия реакторов"""
        for farm in my_reactor:
            """Нужно ли дослать роботов"""
            # print(planets_id[farm])
            if my_planets_id.get(planets_id[farm].id, None) is not None and my_planets_id[farm].building is not None \
                    and my_planets_id.get(my_reactor[farm][0], None) is not None and my_planets_id.get(
                my_reactor[farm][0], None).building is not None \
                    and my_planets_id.get(my_reactor[farm][1], None) is not None and my_planets_id.get(
                my_reactor[farm][1], None).building is not None:
                # print(1)
                if my_workers_on_organics[farm] < exception_planets[farm]:
                    # print(2)
                    # print(exception_planets[farm], my_workers_on_organics[farm])
                    moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
                                                                                home_planet.id,
                                                                                planets_id[farm].id,
                                                                                exception_planets[farm] -
                                                                                my_workers_on_organics[farm])
            # Нужно ли строить
            if (len(find_group([group for planet in itinerary for group in itinerary[planet]],
                               target_planet=planets_id[farm].id)) == 0 and my_planets_id.get(planets_id[farm].id,
                                                                                              None) is None):
                if home_planet.resources.get(
                Resource.STONE,
                0) >= 50:
                    # print(3)
                    moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
                                                                            home_planet.id, planets_id[farm].id, 50,
                                                                            resource=Resource.STONE,
                                                                            build=BuildingAction(planets_id[farm].id,
                                                                                                 BuildingType.FARM))
                    moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
                                                                            home_planet.id, planets_id[farm].id, 30)
                    home_planet.resources[Resource.STONE] -= 50
                else:
                    break
            f = 0
            for reactor in my_reactor[farm]:
                """Нужно ли дослать роботов"""
                # print(planets_id[reactor])
                if my_planets_id.get(planets_id[reactor].id, None) is not None:
                    # print(1)
                    if road_map.count_workers_on_planet(my_planets_id[planets_id[reactor].id], game.my_index, 1) < 20:
                        # print(2)
                        moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
                                                                                    home_planet.id,
                                                                                    planets_id[reactor].id,
                                                                                    20 - road_map.count_workers_on_planet(
                                                                                        my_planets_id[
                                                                                            planets_id[reactor].id],
                                                                                        game.my_index, 1))
                # Нужно ли строить
                elif (len(find_group([group for planet in itinerary for group in itinerary[planet]],
                                    target_planet=planets_id[reactor].id)) == 0 and my_planets_id.get(planets_id[farm].id, None) is None):
                    if home_planet.resources.get(
                    Resource.STONE, 0) >= 100:
                        # print(3)
                        moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
                                                                                home_planet.id, planets_id[reactor].id,
                                                                                100,
                                                                                resource=Resource.STONE,
                                                                                build=BuildingAction(
                                                                                    planets_id[reactor].id,
                                                                                    BuildingType.BIOREACTOR))
                        if exception_planets[planets_id[reactor].id] > 100:
                            moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick,
                                                                                    home_planet.id,
                                                                                    planets_id[reactor].id,
                                                                                    exception_planets[
                                                                                        planets_id[reactor].id] - 100)
                        home_planet.resources[Resource.STONE] -= 100
                    else:
                        f = 1
                        break
            if f:
                break

        print("B", moves)

        """Логистика"""
        """Отправка лишних роботов с биореакторов на ферму за органикой"""
        for farm in my_reactor:
            for reactor in my_reactor[farm]:
                workers_here = road_map.count_workers_on_planet(planets_id[reactor], game.my_index, 1)
                workers_here -= 20
                if workers_here > 0:
                    moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick, reactor, farm, workers_here, 1)

        """Отправка лишних роботов с фермы на биореакторы с органикой"""
        for farm in my_reactor:
            workers_here = road_map.count_workers_on_planet(planets_id[farm], game.my_index, 1) - 80
            organics_here = my_planets_id.get(farm, Planet(0, 0, 0, None, [], {}, None)).resources.get(Resource.ORGANICS, 0)
            for reactor in my_reactor[farm]:
                flag = 0
                if road_map.count_workers_on_planet(planets_id[reactor], game.my_index, 1) > 20:
                    flag = 1
                    continue
                for group in flying_groups.my_groups:
                    group: FlyingWorkerGroup
                    if group.target_planet == reactor:
                        flag = 1
                        break
                if flag:
                    continue
                if workers_here >= exception_planets[reactor] - 20 and organics_here >= exception_planets[reactor] - 20:
                    moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick, farm, reactor, exception_planets[reactor] - 20, 1, resource=Resource.ORGANICS)
                    workers_here -= (exception_planets[reactor] - 20)
                    organics_here -= (exception_planets[reactor] - 20)


        print("L", moves)

        """Подсчет роботов на производствах"""
        for farm in my_organics:
            workers_on_farm = road_map.count_workers_on_planet(planets_id[farm], game.my_index, 1) + \
                              road_map.count_workers_on_planet(planets_id[my_reactor[farm][0]], game.my_index, 1) + \
                              road_map.count_workers_on_planet(planets_id[my_reactor[farm][1]], game.my_index, 1)
            access_planets = [farm, my_reactor[farm][0], my_reactor[farm][1]]
            # print("FARM", farm)
            # print(workers_on_farm)
            for group in flying_groups.my_groups:
                group: FlyingWorkerGroup
                if group.target_planet in access_planets and group.departure_planet in access_planets:
                    workers_on_farm += group.number
            # print(workers_on_farm)
            my_workers_on_organics[farm] = workers_on_farm

        moves = road_map.go_to_home(moves, builds, future_builds, future_moves, current_tick, home_planet,
                                    flying_groups, exception_planets)

        # print("____________________")
        # print(moves)
        # print(future_moves)
        # print(builds)
        # print(future_builds)
        # print("____________________")

        MyStrategy.used = used
        MyStrategy.my_workers_on_organics = my_workers_on_organics
        MyStrategy.exception_planets = exception_planets
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
    buildings = buildings[index:]
    new_buildings = []
    for b in buildings:
        if b[0] is not None and b[1] != -1:
            new_buildings.append(b)
    buildings = new_buildings
    future_moves = flyings.i_am_to_young_to_die(future_moves, current_tick, my_planets, road_map)
    # print("PPP", future_moves)
    future_moves.sort(key=itemgetter(1))
    index = 0
    for order, tick in future_moves:
        # print(order, tick)
        if tick > current_tick:
            break
        if order is not []:
            moves.append(order)
        index += 1
    future_moves = future_moves[index:]
    new_future_moves = []
    for f in future_moves:
        if f[0] is not None and f[1] != -1:
            new_future_moves.append(f)
    future_moves = new_future_moves
    return moves, builds, buildings, future_moves
