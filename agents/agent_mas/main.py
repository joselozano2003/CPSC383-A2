# Camila Hernandez (30134911) - T01
# Jose Lozano (30144736) - T01
# Matias Campuzano (30144328) - T01
# Jose Zea (30226527) - T02
# Due Date: 03/27/2026
# CPSC 383 (Winter 2026)

from aegis_game.stub import *
import heapq

# Global variables
known_agents = set()        # Track active agent IDs
dig2_waiting = {}           # Rubble location key
saved_locs = []             # Known saved survivors
scanned_rubble_locs = set() # Rubble locations we have already scanned
my_targets = {}             # The current target for each agent
dig2_partner_dests = {}     # Dig partner destinations
last_processed_round = {}   # Prevent re-reading messages

# Message types
MSG_SAVED    = "SAVED"
MSG_DIG2_REQ = "DIG2_REQ"
MSG_DIG2_ACK = "DIG2_ACK"
MSG_REPLAN   = "REPLAN"

# Max time to wait for an agent to dig rubble before giving up
MAX_DIG2_WAIT_ROUNDS = 10

# Counter for A* tie-breaking
astar_counter = 0

# Helper functions
def loc_key(loc):
    # Convert location into a string
    return f"{loc.x},{loc.y}"

def key_to_loc(key):
    # Convert string back into Location
    x, y = key.split(",")
    return Location(int(x), int(y))

# This function allows agents to read and process messages coming from other agents.
# Citation: CPSC383-11MAS, Slide 21, Communication by Message Passing
# avoiding shared memory/blackboard bottlenecks 
def process_messages():
    global known_agents, dig2_waiting, saved_locs

    aid = get_id()
    current_round = get_round_number()

    # Initialize last processed round
    if aid not in last_processed_round:
        last_processed_round[aid] = 0

    for msg in read_messages():

        # Skip this if a message has already been processed
        if msg.round_num <= last_processed_round[aid]:
            continue

        # Track the agent who sent the message
        known_agents.add(msg.sender_id)

        parts = msg.message.split("|")
        if not parts:
            continue

        cmd = parts[0]

        # After an agent has saved a survivor, we will replan by clearing
        # the current target so the agent re-evaluates the next move.
        if cmd == MSG_REPLAN:
            my_targets[aid] = None

        # When a survivor is saved, the location is marked as done.
        elif cmd == MSG_SAVED and len(parts) >= 3:
            key = f"{parts[1]},{parts[2]}"
            saved_locs.append(key)

            # Clear the current target since the survivor is saved.
            if my_targets.get(aid) is not None and loc_key(my_targets[aid]) == key:
                my_targets[aid] = None

            # If an agent was moving towards the target location to dig, then we clear that location.
            if dig2_partner_dests.get(aid) == key:
                dig2_partner_dests[aid] = None

        # An agent needs the help of another agent to dig rubble.
        # Citation: CPSC383-13MASCollectiveDecisions, Slide 16, 
        # Using the contract net task allocation protocol
        elif cmd == MSG_DIG2_REQ and len(parts) >= 3:
            key = f"{parts[1]},{parts[2]}"

            # If the agent is available, it will respond by sending a message.
            if dig2_partner_dests.get(aid) is None:
                # Citation: CPSC383-11MAS, Slides 11 & 16 
                # Helping another agent for the main goal
                my_targets[aid] = None 
                dig2_partner_dests[aid] = key
                send_message(f"{MSG_DIG2_ACK}|{parts[1]}|{parts[2]}|{aid}", [])

        # After an agent has responded to the dig rubble request, the other agent
        # can stop broadcasting waiting.
        elif cmd == MSG_DIG2_ACK and len(parts) >= 4:
            key = f"{parts[1]},{parts[2]}"
            if key in dig2_waiting:
                del dig2_waiting[key]

    # Update the last processed round
    last_processed_round[aid] = current_round

# This function handles agent splitting to save all the survivors at the same time.
# Citation: CPSC383-11MAS, Slide 6, CPSC383-13MASCollectiveDecisions, Slide 7
# Re-evaluate the maps and distribution, 
# Use task distribution instead of leader follow. 
def choose_best_target(loc, survs):
    aid = get_id()
    
    available = []
    temp_saved = list(saved_locs)
    
    # Handle stacked survivors
    for s in survs:
        key = loc_key(s)
        if key in temp_saved:
            temp_saved.remove(key)
        else:
            available.append(s)

    if not available:
        return None

    # Sort so all agents generate the same list
    available.sort(key=lambda s: (s.x, s.y))
    all_agents = sorted(list(known_agents | {aid}))
    my_index = all_agents.index(aid)

    # Assign targets and give each agent a different target
    for i in range(len(available)):
        target_idx = (my_index + i) % len(available)
        candidate = available[target_idx]
        
        # If the agent is at the target location, then we will target this survivor.
        if loc == candidate:
            return candidate
        
        # Use A* search algorithm to see if the path exists from the agent's current location
        # to the target location and get the shortest path to the survivor.
        path_check = a_star_search(loc, candidate)
        
        # If the path exists, then we will target this survivor.
        if len(path_check) > 1:
            return candidate

    return None

def think() -> None:
    """Do not remove this function, it must always be defined."""
    log("Thinking")

    global dig2_waiting, saved_locs, scanned_rubble_locs

    aid = get_id()
    loc = get_location()
    energy = get_energy_level()

    # Intialize agent states
    if aid not in my_targets: my_targets[aid] = None
    if aid not in dig2_partner_dests: dig2_partner_dests[aid] = None

    log(f"[A{aid}] Round {get_round_number()} | Loc {loc} | Energy {energy}")

    if get_round_number() == 1:
        send_message("HELLO", [])
        move(Direction.CENTER)
        return

    process_messages()

    survs = get_survs()
    cell  = get_cell_info_at(loc)
    top   = cell.top_layer

    # If the rubble at that location is gone, then the agent will move on.
    if dig2_partner_dests[aid] is not None:
        t_loc = key_to_loc(dig2_partner_dests[aid])
        if not isinstance(get_cell_info_at(t_loc).top_layer, Rubble):
            dig2_partner_dests[aid] = None

    # If the agent is at the cell with a survivor on it, save them.
    if isinstance(top, Survivor):
        save()
        key = loc_key(loc)
        saved_locs.append(key)

        # Notify other agents
        send_message(f"{MSG_SAVED}|{loc.x}|{loc.y}", [])
        send_message(MSG_REPLAN, [])

        # Reset agent state
        my_targets[aid] = None
        dig2_partner_dests[aid] = None
        
        if key in dig2_waiting:
            del dig2_waiting[key]
        
        log(f"[A{aid}] SAVED survivor at {loc}")
        return

    # The agent is at a cell with rubble on it
    if isinstance(top, Rubble):
        rubble = top
        key    = loc_key(loc)

        # If the rubble requires only one agent to remove it, the agent will dig.
        if rubble.agents_required == 1:
            dig()
            return

        # If the rubble requires two or more agents to remove it, then they will dig together.
        # Citation: CPSC383-11MAS, Slide 26
        # Agents use the global round number for dig() at the same time
        if len(cell.agents) >= 2:
            dig()
            if key in dig2_waiting:
                del dig2_waiting[key]
            log(f"[A{aid}] Cooperative DIG at {loc}")
            return

        # If the required number of agents are not at the cell to dig, then the agent(s) will wait.
        if key not in dig2_waiting:
            dig2_waiting[key] = get_round_number()
        
        # Timeout if no other required agent comes
        elif get_round_number() - dig2_waiting[key] >= MAX_DIG2_WAIT_ROUNDS:
            log(f"[A{aid}] DIG2 timeout at {key}; re-targeting")
            del dig2_waiting[key]
            my_targets[aid] = None
            move(Direction.CENTER)
            return

        # Broadcast help request to dig to other agents
        send_message(f"{MSG_DIG2_REQ}|{loc.x}|{loc.y}", [])
        move(Direction.CENTER)
        log(f"[A{aid}] Waiting for DIG2 partner at {loc}")
        return

    # The agent will move toward the dig location if they accepted the request
    if dig2_partner_dests[aid] is not None:
        target = key_to_loc(dig2_partner_dests[aid])

        if loc == target:
            move(Direction.CENTER)
        else:
            next_loc = next_move(loc, target, energy)
            if next_loc is None:
                return
            if isinstance(next_loc, Location):
                move(loc.direction_to(next_loc))
            else:
                move(next_loc)
        return

    # If survivors exist on the map, we will choose the closest target to the agent to save.
    if survs:
        best_target = choose_best_target(loc, survs)

        # Update the target survivor
        if best_target is not None:
            curr_target = my_targets[aid]
            if curr_target is None or loc_key(best_target) != loc_key(curr_target):
                my_targets[aid] = best_target
                log(f"[A{aid}] Split to target {best_target}")

        curr_target = my_targets[aid]

        if curr_target is not None:
            # The agents will scan rubble from cells away before they commit to moving and digging.
            target_key = loc_key(curr_target)
            if target_key not in scanned_rubble_locs:
                target_cell = get_cell_info_at(curr_target)
                if isinstance(target_cell.top_layer, Rubble) and heuristic(loc, curr_target) > 1:
                    scan_result = drone_scan(curr_target)
                    scanned_rubble_locs.add(target_key)
                    
                    if scan_result:
                        log(f"[A{aid}] Drone scanned {curr_target}: {scan_result.layers} layers.")

                        # If there are multiple layers of rubble, the agent will send a message early for help digging.
                        if scan_result.layers > 1:
                            send_message(f"{MSG_DIG2_REQ}|{curr_target.x}|{curr_target.y}", [])
                    return 
            
            # Normal agent movement
            next_loc = next_move(loc, curr_target, energy)
            if next_loc is None:
                return
            if isinstance(next_loc, Location):
                move(loc.direction_to(next_loc))
            else:
                move(next_loc)
            return

    # If an agent has nothing to do, they will stay in place.
    move(Direction.CENTER)

### Pathfinding using A* Algorithm (adapted from Camila Hernandez's Assignment 1 submission) ###
# This function is adapted from https://www.geeksforgeeks.org/machine-learning/chebyshev-distance/
def heuristic(a, b):
    return max(abs(a.x - b.x), abs(a.y - b.y))

# This function used pseudocode from https://www.redblobgames.com/pathfinding/a-star/introduction.html
def a_star_search(start, goal):
    global astar_counter

    # Initialize frontier
    frontier = []
    
    heapq.heappush(frontier, (0, astar_counter, start))
    astar_counter += 1
    
    came_from   = {start: None}
    cost_so_far = {start: 0}

    while frontier:
        _, _, current = heapq.heappop(frontier)

        # Checks if the goal has been reached
        if current == goal:
            break

        # Check directions
        for direction in Direction:
            if direction == Direction.CENTER:
                continue
            
            # Determine the adjacent location to the current location of the agent
            adjacent = current.add(direction)

            # Skip this location if it is out of world bounds
            if not on_map(adjacent):
                continue
            
            # Skip this lcoation if the cell is a killer cell
            cell_info = get_cell_info_at(adjacent)
            if cell_info.is_killer_cell():
                continue

            # Retrieve the adjacent cell cost
            cell_cost = cell_info.move_cost
            
            # Handle negative cells
            if cell_cost < 0:
                if len(cell_info.agents) > 0:
                    # Another agent is here
                    cell_cost = 1
                elif isinstance(cell_info.top_layer, Rubble):
                    # There might be a cost
                    cell_cost = 15
                elif adjacent == goal:
                    # The goal
                    cell_cost = 1
                else:
                    # Can't go here
                    continue

            # Calculate the new cell cost
            new_cost  = cost_so_far[current] + cell_cost

            # If the adjacent cell is new or cheaper, the cost, priority and where it came from
            # will be updated
            if adjacent not in cost_so_far or new_cost < cost_so_far[adjacent]:
                cost_so_far[adjacent] = new_cost
                priority = new_cost + heuristic(goal, adjacent)
                heapq.heappush(frontier, (priority, astar_counter, adjacent))
                astar_counter += 1
                came_from[adjacent] = current

    # Reconstruct the path backwards from goal to start
    path = []
    current = goal
    while current != start:
        path.append(current)
        if current not in came_from:
            return [start]
        current = came_from[current]
    path.append(start)
    path.reverse()
    return path

# This function picks the closest target cell using the heuristic.
def closest_target_cell(loc, targets):
    heap = [(heuristic(loc, t), t) for t in targets]
    heapq.heapify(heap)
    return heapq.heappop(heap)[1]

# This fucntion estimates the energy cost to follow a path using
# the move cost of each cell.
def estimate_path_cost(path):
    cost = 0
    for location in path:
        c = get_cell_info_at(location).move_cost
        cost += 1 if c < 0 else c
    return cost

# This function returns the nearest charging cell locations using the
# heuristic, or returns nothing if no charging cells exist on the map.
def nearest_charging_cell(loc):
    chargers = get_charging_cells()
    if not chargers:
        return None
    heap = [(heuristic(loc, c), c) for c in chargers]
    heapq.heapify(heap)
    return heapq.heappop(heap)[1]

# This function decides the next move for each agent while avoiding running out of energy.
def next_move(agent_loc, target_loc, energy):
    charging_cells = get_charging_cells()

    # If the agent is on a charging cell, the agent can recharge if the calculated cost to the
    # target cell is greater than their current energy.
    if agent_loc in charging_cells:
        path_to_target = a_star_search(agent_loc, target_loc)
        cost_to_target = estimate_path_cost(path_to_target)
        if energy < cost_to_target:
            recharge()
            return None

    # Calculate the path to the target cell and its cost
    path_to_target = a_star_search(agent_loc, target_loc)
    cost_to_target = estimate_path_cost(path_to_target)

    # If the agent has enough energy, then it will move towards the target.
    if energy >= cost_to_target:
        if len(path_to_target) > 1:
            return path_to_target[1]
        return Direction.CENTER

    # If the agent is running low on energy and cannot make it to the target cell,
    # it will go to the nearest charging cell.
    charger = nearest_charging_cell(agent_loc)
    if charger:
        path_to_charger = a_star_search(agent_loc, charger)
        if path_to_charger and len(path_to_charger) > 1:
            return path_to_charger[1]

    return Direction.CENTER