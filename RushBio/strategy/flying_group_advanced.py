from model.move_action import MoveAction
from model.resource import Resource
from model.building_type import BuildingType
from model.building_action import BuildingAction
from model.planet import Planet
# from strategy.roads import dijkstra


class AllFlyingGroups:
    """Contains in itself all flying worker groups that exists."""

    """Функция поиска пути от данной планеты до всех"""
    find_path_to_all = None

    def __init__(self, groups, my_index, find_path_to_all, itinerary, players, planets_id):
        self.planets_id = planets_id
        self.my_index = my_index
        self.players = players
        AllFlyingGroups.find_path_to_all = find_path_to_all
        self.itinerary = itinerary
        self.all_groups = groups
        self.my_groups = []
        self.enemy_groups = []
        for group in self.all_groups:
            if players[group.player_index][0] == players[self.my_index][0]:
                self.my_groups.append(group)
            else:
                self.enemy_groups.append(group)
        self.enemy_groups.sort(key=lambda x: x.number, reverse=True)

    def count_workers_on_planet_in_flying_groups(self, planet):
        number = 0
        worker_groups = self.itinerary[planet]
        for group in worker_groups:
            group: FlyingGroupAdv
            number += group.amount_workers
        return number

    """Обновляет все группы, что сидят на планетах в данный тик.
        Возвращает список движений(объекты MoveAction) и словарь летящих групп для обновления
        *В будущем можно замутить такое же отслеживание групп врага и прогнозировать куда они полетят"""

    def update_all_groups(self, current_tick):
        moves = []
        builds = []
        for planet in self.itinerary:
            groups_flew = self.itinerary[planet]
            groups_to_delete = []
            for group in groups_flew:
                action = group.update(current_tick)
                if action[0] == 0:
                    continue
                elif action[0] == 1:
                    groups_to_delete.append(group)
                    if action[1] is not None:
                        builds.append(action[1])
                else:
                    moves.append(action[0])
            for group in groups_to_delete:
                for index, group_in in enumerate(groups_flew):
                    if group_in == group:
                        groups_flew.pop(index)
                        break
        return moves, builds

    def i_am_to_young_to_die(self, future_moves, current_tick, my_planets, road_map):
        my_planets = [pl.id for pl in my_planets]
        # print("XXXXXXXXXXXXXXXX")
        for group in self.enemy_groups:
            if group.next_planet in my_planets:
                mn = [[1000000, 1000000], road_map.net[group.next_planet][0]]
                for planet in road_map.net[group.next_planet]:
                    if planet[1][1] == mn[0][1] and planet[1][0] < mn[0][0]:
                        mn = [planet[1], planet[0]]
                    elif planet[1][1] < mn[0][1]:
                        mn = [planet[1], planet[0]]
                planet = mn
                workers_on_planet = road_map.count_workers_on_planet(
                    self.planets_id[group.next_planet],
                    road_map.my_index,
                    1)
                workers_in_flying_group = self.count_workers_on_planet_in_flying_groups(
                    group.next_planet)
                for group_move in filter(lambda x: x[0].start_planet == group.next_planet, future_moves):
                    workers_in_flying_group += group_move[0].worker_number
                # print(list(filter(lambda x: x[0].start_planet == group.next_planet, future_moves)))
                # print(planet[1], workers_on_planet, workers_in_flying_group)
                if workers_on_planet - workers_in_flying_group <= 0:
                    continue
                action = [MoveAction(group.next_planet, planet[1],
                                     workers_on_planet - workers_in_flying_group, None),
                             group.next_planet_arrival_tick - 1]
                f = 0
                for obj in future_moves:
                    # print(obj)
                    if len(action) != 2:
                        f = 1
                        break
                    if obj[0].target_planet == action[0].target_planet and obj[0].start_planet == action[
                        0].start_planet and obj[0].worker_number == action[0].worker_number and obj[
                        0].take_resource == action[0].take_resource and obj[1] == action[1]:
                        f = 1
                        break

                if not f:
                    # print(action)
                    future_moves.append(action)
                # print(self.make_flying_group(current_tick + planet[1], planet[0], group.next_planet, 10000))
                action = [MoveAction(planet[1], group.next_planet,
                                     workers_on_planet - workers_in_flying_group, None),
                          group.next_planet_arrival_tick - 1 + planet[0][0]]

                f = 0
                for obj in future_moves:
                    if len(action) != 2:
                        f = 1
                        break
                    if obj[0].target_planet == action[0].target_planet and obj[0].start_planet == action[
                        0].start_planet and obj[0].worker_number == action[0].worker_number and obj[
                        0].take_resource == action[0].take_resource and obj[1] == action[1]:
                        f = 1
                        break

                if not f:
                    # print(action)
                    future_moves.append(action)
        # print("XXXXXXXXX")
        # print("XXXXXXXX")
        # print(moves)
        # print(future_moves)
        # print("XXXXXXXX")
        return future_moves

    """Создает безопасно летящую(наверное) группу роботов от home_planet до target_planet, с рабочими amount_workers и
        ресурсом с ними resource. Добавляет планету в словарь летающих групп.
        Возвращает [MoveAction], при этом если home_planet == target_planet, то пустой массив"""

    def make_flying_group(self, current_tick: int, home_planet: int, target_planet: int, amount_workers: int, enemy=0,
                          resource=None, build=None):
        group = FlyingGroupAdv(target_planet, home_planet, -1, amount_workers, resource, enemy, build)
        action = group.update(current_tick)
        self.itinerary[group.next_planet].append(group)
        return [action[0]] if action[0] != 1 and action[0] != 0 else [], action[1]

    """Тоже, что и .make_flying_group(...). Однако создано для удобства добавления в списки действий и строительства"""

    def make_move_build_action(self, moves, builds, current_tick: int, home_planet: int, target_planet: int,
                               amount_workers: int,
                               enemy=0,
                               resource=None, build=None):
        new_group = self.make_flying_group(current_tick, home_planet, target_planet, amount_workers, enemy, resource,
                                           build)
        moves += new_group[0]
        if new_group[1] is not None:
            builds += new_group[1]
        return moves, builds

    def clear(self):
        planets = []
        for planet in self.itinerary.keys():
            planets.append(planet)
        self.itinerary = {}
        for planet in planets:
            self.itinerary[planet] = []


class FlyingGroupAdv:
    """Flying Group that won't die by randomly flying near enemy flying group."""

    def __init__(self, target_planet, next_planet, tick, amount_workers, resource, enemy, build):
        self.target_planet = target_planet
        self.next_planet = next_planet
        self.tick = tick
        self.amount_workers = amount_workers
        self.resource = resource
        self.enemy = enemy
        self.build = build

    """Обновляет конфигурацию данной летящей группы по данному тику.
        Возвращает MoveAction - надо двигаться, 1 - надо удалить, иначе 0."""

    def update(self, current_tick):
        if self.tick > current_tick:
            return 0, []
        if self.target_planet == self.next_planet:
            return 1, [self.build, self.tick]
        group_to_itinerary = AllFlyingGroups.find_path_to_all(self.next_planet, self.target_planet, self.enemy)[0]
        move = MoveAction(self.next_planet, group_to_itinerary[0], self.amount_workers, self.resource)
        self.tick = group_to_itinerary[1][0] + current_tick
        self.next_planet = group_to_itinerary[0]
        return move, []

    def __repr__(self):
        return "FlyingGroupAdv(" + \
               repr(self.target_planet) + \
               ", " + \
               repr(self.next_planet) + \
               ", " + \
               repr(self.tick) + \
               ", " + \
               repr(self.amount_workers) + \
               ", " + \
               repr(self.resource) + \
               ", " + \
               repr(self.build) + \
               ", " + \
               repr(self.enemy) + \
               ")"


def find_group(got_groups, target_planet=None, next_planet=None, amount_workers=None, resource=None, build=None):
    groups_founded = []
    clause = lambda a, b: 1 if a is None else 1 if a == b else 0
    for group in got_groups:
        group: FlyingGroupAdv
        if clause(target_planet, group.target_planet) and clause(next_planet, group.next_planet) and clause(
                amount_workers, group.amount_workers) and clause(resource, group.resource) and clause(build, group.build):
            groups_founded.append(group)
    return groups_founded
