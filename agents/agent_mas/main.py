# Camila Hernandez (30134911)
# Jose Lozano
# Matias Campuzano
# Jose Zea
# Due Date: 03/27/2026
# CPSC 383 (Winter 2026)

from aegis_game.stub import *
import heapq

def think() -> None:
    """Do not remove this function, it must always be defined."""
    log("Thinking")

    # Initialize variables
    loc = get_location()
    survs = get_survs()
    energy = get_energy_level()

    # On the first round, send a request for surrounding information
    # by moving to the center (not moving). This will help initiate pathfinding.
    if get_round_number() == 1:
        move(Direction.CENTER)
        send_message("hello world", [])  # Broadcast to all teammates
        return

    # On subsequent rounds, read and log all received messages.
    messages = read_messages()
    log(messages)

    # Fetch the cell at the agent's current location.
    # If you want to check a different location, use `on_map(loc)` first
    # to ensure it's within the world bounds. The agent's own location is always valid.
    cell = get_cell_info_at(get_location())

    # Get the top layer at the agent's current location.
    # If a survivor is present, save it and end the turn.
    top_layer = cell.top_layer
    if isinstance(top_layer, Survivor):
        save()
        return
    
    # If there is rubble, dig and end thr turn.
    if isinstance(top_layer, Rubble):
         dig()
         return

    # The following is code from Camila's A1:
    # Using A* search algorithm, we obtain the shortest path to the survivor.
    path = a_star_search(get_location(), get_survs()[0])
    # Move if the path has more than one location
    if len(path) > 1:
            move(get_location().direction_to(path[1]))

# The following is code from Camila's A1:
# This function is adapted from https://www.geeksforgeeks.org/machine-learning/chebyshev-distance/
def heuristic(a, b):
    return max(abs(a.x - b.x), abs(a.y - b.y))

# The following is code from Camila's A1:
# This function used pseudocode from https://www.redblobgames.com/pathfinding/a-star/introduction.html
# A* search algorithm uses the actual distance from the spawn location and the estimated distance to the goal.
def a_star_search(start: Location, goal: Location):
    # Initialize frontier
    frontier = []

    # Direction priority used for tie-break
    dir_priority = {
         Direction.NORTH: 0,
         Direction.NORTHEAST: 1,
         Direction.EAST: 2,
         Direction.SOUTHEAST: 3,
         Direction.SOUTH: 4,
         Direction.SOUTHWEST: 5,
         Direction.WEST: 6,
         Direction.NORTHWEST: 7,
         Direction.CENTER: 8
    }
    
    heapq.heappush(frontier, (0, 0, start))
    came_from = {start: None}
    cost_so_far = {start: 0}
    current: Location

    while len(frontier) > 0:
        _, _, current = heapq.heappop(frontier)

        # Checks if the goal has been reached
        if current == goal:
            break

        # Check directions
        for direction in Direction:
            # Determines the adjacent location to the current location
            adjacent = current.add(direction)

            # Skip if this location is out of world bounds
            if not on_map(adjacent):
                continue

            # Skip this location if the cell is a killer cell
            if get_cell_info_at(adjacent).is_killer_cell():
                continue

            # Retrieve the adjacent cell cost
            cell_cost = get_cell_info_at(adjacent).move_cost

            # Calculate the new cell cost
            new_cost = cost_so_far[current] + cell_cost

            # If the adjacent cell is new or cheaper, updates the cost, priority and where it came from
            if adjacent not in cost_so_far or new_cost < cost_so_far[adjacent]:
                    cost_so_far[adjacent] = new_cost
                    priority = new_cost + heuristic(goal, adjacent)
                    heapq.heappush(frontier, (priority, dir_priority[direction], adjacent))
                    came_from[adjacent] = current
    
    # Reconstruct the path backwards from goal to start
    path = []
    current = goal
    while current != start:
        path.append(current)
        if current not in came_from:  # Safety check
            log(f"Cannot reconstruct path from {current} to {start}")
            return [start]  # Fallback
        current = came_from[current]
    path.append(start)
    path.reverse()
    log(path)
    return path

# Calculate the energy cost to travel to a survivor
def estimate_path_cost(path):
    cost = 0
    for location in path:
        cost += get_cell_info_at(location).move_cost
    return cost

# Calculate the nearest charging cells
def nearest_charging_cell(loc):
    chargers = get_charging_cells()
    if not chargers:
        return None

    # Use a heap to find the closest charger
    heap = [(heuristic(loc, c), c) for c in chargers]
    heapq.heapify(heap)
    return heapq.heappop(heap)[1]

def next_move(agent_loc, target_loc, energy):
    charging_cells = get_charging_cells()

    # If the agent is standing on a charging cell and it doesn't have enough energy to reach the target cell, recharge
    if agent_loc in charging_cells:
        path_to_target = a_star_search(agent_loc, target_loc)
        cost_to_target = estimate_path_cost(path_to_target)
        if energy < cost_to_target:
            recharge()
            return None

    # Path to target cell
    path_to_target = a_star_search(agent_loc, target_loc)
    cost_to_target = estimate_path_cost(path_to_target)

    # If the agent has enough energy, move toward target cell
    if energy >= cost_to_target:
        if len(path_to_target) > 1:
            return path_to_target[1]
        return Direction.CENTER

    # If the agent does not have enough energy, move toward the nearest charger
    charger = nearest_charging_cell(agent_loc)
    if charger:
        path_to_charger = a_star_search(agent_loc, charger)
        if path_to_charger and len(path_to_charger) > 1:
            return path_to_charger[1]

    return Direction.CENTER