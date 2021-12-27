from model import *
from strategy.roads import RoadNet, find_planet
from strategy.flying_group_advanced import AllFlyingGroups, find_group
from operator import itemgetter


# from strategy.resources_advanced import ResourceAdv


class MyStrategy:
    """MyStrategy"""

    """Карта дорог(граф)"""
    road_map: RoadNet

    """Словарь с летающими группами"""
    itinerary: dict

    """Планеты запланированные для стройки"""
    wait_build: set

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
                MyStrategy.my_planet_id = planet.id
        MyStrategy.enemy_score_past = 0
        MyStrategy.players = {}
        for i in range(6):
            MyStrategy.players[i] = [game.players[i].team_index, i]
        MyStrategy.road_map = RoadNet(game.planets, game.my_index, game.max_travel_distance, MyStrategy.players)
        MyStrategy.future_builds = []
        MyStrategy.future_moves = []
        MyStrategy.home_planet = MyStrategy.road_map.only_my_robots[0].id
        # print(MyStrategy.home_planet)
        MyStrategy.relation = {}
        for building in game.building_properties:
            MyStrategy.relation[game.building_properties[building].produce_resource] = building

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
        find_path_to_all = road_map.find_path_from_one_to_one
        itinerary = MyStrategy.itinerary
        flying_groups = AllFlyingGroups(game.flying_worker_groups, game.my_index, find_path_to_all, itinerary,
                                        MyStrategy.players)
        MyStrategy.road_map.categorise_planets(flying_groups.enemy_groups)
        future_builds = MyStrategy.future_builds
        future_moves = MyStrategy.future_moves
        home_planet = list(filter(lambda x: x.id == MyStrategy.home_planet, game.planets))[0]
        relation = MyStrategy.relation
        # print("Enemy_planets", road_map.planets_with_enemy_robots)

        if not len(my_planets) or (not len(enemy_planets) and not len(flying_groups.enemy_groups)):
            return Action([], [], Specialty.PRODUCTION)

        if current_tick == 1:
            moves, builds = flying_groups.make_move_build_action(moves, builds, current_tick, 0, 20, 100)
            print(moves)
            MyStrategy.road_map = road_map
            MyStrategy.itinerary = flying_groups.itinerary
            MyStrategy.future_builds = future_builds
            MyStrategy.future_moves = future_moves
            return Action(moves, builds, Specialty.PRODUCTION)

        # moves, builds, future_builds, future_moves = update(current_tick, flying_groups, moves, builds, future_builds, future_moves)
        # print(moves)
        # print(builds)
        # print(future_builds)
        #
        # distance_from_home, parents_from_home = road_map.find_path_to_all(home_planet.id)
        # planets_to_capture = [
        #     sorted(find_planet(game.planets, Resource.ORGANICS), key=lambda x: distance_from_home[x.id]) +
        #     sorted(find_planet(game.planets, Resource.SAND), key=lambda x: distance_from_home[x.id]) +
        #     sorted(find_planet(game.planets, Resource.ORE), key=lambda x: distance_from_home[x.id])][0]
        #
        # amount_stone_at_home = home_planet.resources[Resource.STONE] if len(home_planet.resources) != 0 else 0
        # for planet in planets_to_capture:
        #     need_to_count = 1
        #     if road_map.count_workers_on_planet(planet, game.my_index, 1) != 0 and planet.building is not None:
        #         need_to_count = 0
        #     for action in future_builds:
        #         action: list
        #         order: BuildingAction
        #         order = action[0]
        #         if order is not None and order.planet == planet.id:
        #             need_to_count = 0
        #             break
        #     for action in builds:
        #         action: BuildingAction
        #         if action.planet == planet.id:
        #             need_to_count = 0
        #     if len(find_group([group for pl in itinerary for group in itinerary[pl]], planet.id)) != 0:
        #         need_to_count = 0
        #     # print(need_to_count, planet)
        #     if need_to_count:
        #         if amount_stone_at_home >= 50:
        #             amount_stone_at_home -= 50
        #             moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick, home_planet.id,
        #                                                                  planet.id, 50, resource=Resource.STONE,
        #                                                                  build=BuildingAction(planet.id, relation[
        #                                                                      planet.harvestable_resource]))
        #             moves, future_builds = flying_groups.make_move_build_action(moves, future_builds, current_tick, home_planet.id,
        #                                                                  planet.id, 50)
        #         else:
        #             break

        moves, builds, future_builds, future_moves = update(current_tick, my_planets, flying_groups, moves, builds, future_builds, future_moves)
        moves += road_map.go_to_home(current_tick, 0, my_planets, game.building_properties, flying_groups)
        print(moves)
        print(builds)
        print(future_builds)
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
