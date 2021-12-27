from model import BuildingAction, MoveAction
from model.planet import Planet
from model.resource import Resource
from model.building import BuildingType
from strategy.flying_group_advanced import find_group
# from strategy.flying_group_advanced import AllFlyingGroups

"""Составляет карту игры"""


class RoadNet:
    """Makes RoadNet(Graph by planets)"""

    def __init__(self, vertices, my_index, max_distance, players, building_properties):
        self.building_properties = building_properties
        self.my_index = my_index
        self.players = players
        self.max_distance = max_distance
        self.vertices = vertices
        self.only_my_robots = []
        for planet in self.vertices:
            for group in planet.worker_groups:
                if group.player_index == self.my_index:
                    self.only_my_robots.append(planet)
        self.amount_vertices, self.net = self.build_graph()
        self.my_robots_on_planets = 0
        self.enemy_robots_on_planets = 0
        self.neutral_planets, self.planets_with_my_robots, self.planets_with_enemy_robots = [], [], []
        self.vertices_without_enemy = []
        self.enemy_groups = []

    """Сортирует планеты на дружественные, вражеские, нейтральные(общие)"""

    def categorise_planets(self, enemy_groups):
        self.only_my_robots = []
        for planet in self.vertices:
            for group in planet.worker_groups:
                if group.player_index == self.my_index:
                    self.only_my_robots.append(planet)
        neutral = []
        my_robots = []
        enemy_robots = []
        for planet in self.vertices:
            if len(planet.worker_groups) != 0:
                my_robots_here = 0  # 0 - None, 1 - My
                enemy_robots_here = 0  # 0 - None, 1 - Enemy
                for group in planet.worker_groups:
                    if self.players[group.player_index][0] == self.players[self.my_index][0]:
                        my_robots_here += group.number
                    else:
                        enemy_robots_here += group.number
                if my_robots_here and enemy_robots_here:
                    continue
                if my_robots_here:
                    my_robots.append(planet)
                    planet.worker_groups.sort(key=lambda x: x.number)
                else:
                    enemy_robots.append(planet)
                    planet.worker_groups.sort(key=lambda x: x.number)
                self.my_robots_on_planets += my_robots_here
                self.enemy_robots_on_planets += enemy_robots_here
            else:
                neutral.append(planet)

        self.planets_with_my_robots = my_robots
        self.planets_with_enemy_robots = enemy_robots
        self.neutral_planets = neutral
        self.vertices_without_enemy = self.planets_with_my_robots + self.neutral_planets
        self.planets_with_enemy_robots.sort(key=lambda planet: planet.id)
        self.planets_with_my_robots.sort(key=lambda planet: planet.id)
        self.enemy_groups = enemy_groups

    def count_workers_on_planet(self, planet_b: Planet, index, who):
        amount = 0
        for group in planet_b.worker_groups:
            if self.players[group.player_index][who] == index:
                amount += group.number
        return amount

    """Строит граф для перемещения по планетам"""

    def build_graph(self):
        g = {}
        n = 0
        for planet in self.vertices:
            n += 1
            g[planet.id] = list()
        for planet_from in self.vertices:
            for planet_to in self.vertices:
                if planet_to.id > planet_from.id:
                    length = abs(planet_from.x - planet_to.x) + abs(planet_from.y - planet_to.y)
                    cost = self.count_workers_on_planet(planet_to, 0 if self.players[self.my_index][0] else 1, 0)
                    if planet_to != planet_from and length <= self.max_distance:
                        g[planet_from.id].append([planet_to.id, [length, cost]])
                        g[planet_to.id].append([planet_from.id, [length, cost]])
        return n, g

    """Принимает массив предков, планету стратовую, конечную.
        Возвращает массив пути - по порядку планеты"""

    def find_path_from_one_to_one(self, planet_from, planet_to, enemy=1) -> list:
        INF = 1000000

        if planet_to == planet_from:
            return [[planet_to, 0]]

        n, graph = self.amount_vertices, self.net
        if enemy:
            # print("With")
            distance, parents = dijkstra(n, graph, planet_from, enemy, self.vertices, self.planets_with_enemy_robots, 0)
        else:
            distance, parents = dijkstra(n, graph, planet_from, enemy, self.vertices, self.planets_with_enemy_robots, 0)
            if distance[planet_to] == [INF, INF]:
                # print("Minimum of enemies")
                graph = self.build_graph()[1]
                distance, parents = dijkstra(n, graph, planet_from, 1, self.vertices, self.planets_with_enemy_robots, 1)
            else:
                # print("Without, luck")
                pass

        path = []
        v = planet_to
        while v != planet_from:
            v = parents[v]
            path.append([v, distance[v]])
        path.pop()
        path.reverse()
        path.append([planet_to, distance[planet_to]])
        return path

    """Находит безопасные пути от заданной планеты 'planet_from' до всех других.
        Исключает планеты с врагом. Но не прогнозирует, где приземлятся враги!
        Возвращает список кратчайших расстояний и список родителей"""

    def go_to_home(self, moves, builds, future_builds, future_moves, current_tick, home_planets, flying_groups, exception_planets: dict):
        # flying_groups: AllFlyingGroups
        my_planets_id = [p.id for p in self.only_my_robots]
        # print("XXXXXXX")
        # print(moves)

        for planet in self.only_my_robots:
            amount_workers = self.count_workers_on_planet(planet, self.my_index, 1)

            """Проверка запланированной стройки"""
            for action in future_builds:
                action: list
                order: BuildingAction
                order = action[0]
                if order is not None and order.planet == planet.id:
                    amount_workers = 0
                    break
            for action in builds:
                action: BuildingAction
                if action.planet == planet.id:
                    amount_workers = 0

            """Проверка транзитных групп"""
            # amount_workers -= flying_groups.count_workers_on_planet_in_flying_groups(planet)
            moves_transit = list(filter(lambda x: x.start_planet == planet.id, moves))
            for group_transit in moves_transit:
                group_transit: MoveAction
                amount_workers -= group_transit.worker_number
            moves_transit = list(filter(lambda x: x[0].start_planet == planet.id, future_moves))
            for obj in moves_transit:
                group_transit: MoveAction
                group_transit = obj[0]
                amount_workers -= group_transit.worker_number

            """Проверка рабочих роботов на здании"""
            if planet.building is not None:
                amount_workers -= self.building_properties[planet.building.building_type].max_workers
            elif amount_workers > 0:
                moves += flying_groups.make_flying_group(current_tick, planet.id, home_planets.id, amount_workers)[0]
                continue
            amount_workers -= exception_planets[planet.id]

            if amount_workers > 0:
                moves += flying_groups.make_flying_group(current_tick, planet.id, home_planets.id, amount_workers)[0]

        # print(moves)
        # print("XXXXXXXX")

        # my_workers_at_home = 0
        # for planet in home_planets:
        #     my_workers_at_home += self.count_workers_on_planet(planet, self.my_index, 1)
        # my_groups = flying_groups.my_groups
        # moves = []
        # my_workers_at_groups = {}
        # for planet in my_planets:
        #     my_workers_at_groups[planet.id] = 0
        # for group in my_groups:
        #     if group.next_planet in my_planets_id:
        #         my_workers_at_groups[group.next_planet] += group.number
        # for planet in my_planets:
        #     planet: Planet
        #     lentei = self.count_workers_on_planet(planet, self.my_index, 1)
        #     if planet.building is not None:
        #         # lentei -= building_properties[planet.building.building_type].max_workers
        #         continue
        #     lentei -= my_workers_at_groups[planet.id]
        #     if lentei > 0:
        #         moves, builds = flying_groups.make_move_build_action(moves, [], current_tick, planet.id,
        #                                                              home_planets, lentei)
        return moves

"""Алгоритм Дейкстры"""


def dijkstra(n, graph, planet_from, enemy, vertices, planets_with_enemy_robots, what_to_count):
    INF = 1000000
    d = {}
    p = {}
    u = {}
    for planet in vertices:
        d[planet.id] = [INF, INF]
        p[planet.id] = 0
        u[planet.id] = 0
        if not enemy and planet in planets_with_enemy_robots:
            u[planet.id] = 1
    d[planet_from] = [0, 0]

    for _ in range(n):
        v = -1
        for j in graph:
            if not u[j] and (v == -1 or d[j][what_to_count] < d[v][what_to_count]):
                v = j
        if v == -1:
            break
        if d[v] == [INF, INF]:
            break
        u[v] = 1
        for j in graph[v]:
            to = j[0]
            ln = j[1]
            if d[v][what_to_count] + ln[what_to_count] < d[to][what_to_count]:
                d[to][what_to_count] = d[v][what_to_count] + ln[what_to_count]
                d[to][0 if what_to_count else 1] = d[v][0 if what_to_count else 1] + ln[0 if what_to_count else 1]
                p[to] = v
    # print(planet_from, enemy)
    # print(d)
    return d, p


"""Находит планеты по необходимому добываемому ресурсу, лежащему на планете ресурсу, стоящему на планете зданию"""


def find_planet(planets_got, harvestable_resource_to_find: Resource = None, free_resource_to_find=None,
                building_to_find=None) -> list:  # -1 - Без объекта, None - Неважно есть или нет
    clause_b = lambda p, f: p.building is None if f == -1 else p.building.building_type == f if f is not None else 1
    clause_r = lambda p, f: not len(p.resources) if f == -1 else f in p.resources if f is not None else 1
    planets_were_found = []
    planets = planets_got
    for planet in planets:
        if (harvestable_resource_to_find is None or planet.harvestable_resource == harvestable_resource_to_find) and clause_b(planet, building_to_find) and \
                clause_r(planet, free_resource_to_find):
            planets_were_found.append(planet)
        # print(planet.harvestable_resource,
        #       planet.building.building_type if planet.building is not None else None,
        #       planet.resources, len(planets_were_found))
    return sorted(planets_were_found, key=lambda planet: planet.id)
