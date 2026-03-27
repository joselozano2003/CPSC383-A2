# Camila Hernandez (30134911) - T01
# Jose Lozano (30144736) - T01
# Matias Campuzano (30144328) - T01
# Jose Zea (30226527) - T02
# Due Date: 03/27/2026
# CPSC 383 (Winter 2026)

from aegis_game.stub import *
import heapq

known_agents = set()        # track active agent IDs
dig2_waiting = {}           # rubble loc_key
saved_locs = []             # known saved survivors
scanned_rubble_locs = set() # rubble locations we have already scanned
my_targets = {}             # the current target for each agent
dig2_partner_dests = {}     # dig partner destinations
last_processed_round = {}   # prevent re reading messages

# ===========================================================================
# MESSAGE PROTOCOL CONSTANTS
# ===========================================================================
MSG_SAVED    = "SAVED"
MSG_DIG2_REQ = "DIG2_REQ"
MSG_DIG2_ACK = "DIG2_ACK"
MSG_REPLAN   = "REPLAN"

MAX_DIG2_WAIT_ROUNDS = 10

# Counter for A* tie-breaking
astar_counter = 0

# ===========================================================================
#  HELPERS
# ===========================================================================

def loc_key(loc):
    """Return a hashable string key for a Location (e.g. '3,7')."""
    return f"{loc.x},{loc.y}"

def key_to_loc(key):
    """Parse a loc_key string back into a Location."""
    x, y = key.split(",")
    return Location(int(x), int(y))


# ===========================================================================
# MESSAGE PROCESSING
# ===========================================================================

def process_messages():
    """Read and process messages received from other agents."""
    global known_agents, dig2_waiting, saved_locs

    aid = get_id()
    current_round = get_round_number()

    if aid not in last_processed_round:
        last_processed_round[aid] = 0

    for msg in read_messages():
        if msg.round_num <= last_processed_round[aid]:
            continue

        known_agents.add(msg.sender_id)

        parts = msg.message.split("|")
        if not parts:
            continue

        cmd = parts[0]

        # ── REPLAN: A goal changed, clear target to force re-evaluation ─────
        if cmd == MSG_REPLAN:
            my_targets[aid] = None

        # ── SAVED: A survivor was secured ───────────────────────────────────
        elif cmd == MSG_SAVED and len(parts) >= 3:
            key = f"{parts[1]},{parts[2]}"
            saved_locs.append(key)
            if my_targets.get(aid) is not None and loc_key(my_targets[aid]) == key:
                my_targets[aid] = None
            if dig2_partner_dests.get(aid) == key:
                dig2_partner_dests[aid] = None

        # ── DIG2_REQ: a peer needs a second agent to dig rubble ────────────
        elif cmd == MSG_DIG2_REQ and len(parts) >= 3:
            key = f"{parts[1]},{parts[2]}"
            if dig2_partner_dests.get(aid) is None:
                my_targets[aid] = None 
                dig2_partner_dests[aid] = key
                send_message(f"{MSG_DIG2_ACK}|{parts[1]}|{parts[2]}|{aid}", [])

        # ── DIG2_ACK: a partner is coming — stop re-broadcasting
        elif cmd == MSG_DIG2_ACK and len(parts) >= 4:
            key = f"{parts[1]},{parts[2]}"
            if key in dig2_waiting:
                del dig2_waiting[key]

    last_processed_round[aid] = current_round


# ===========================================================================
# TARGET SELECTION
# ===========================================================================

def choose_best_target(loc, survs):
    """
    Member 4: Multi-Goal Planning & Agent Splitting (Challenge 4 & 5).
    """
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

    # Use modulo math to assign a target. If fails, try the next one.
    for i in range(len(available)):
        target_idx = (my_index + i) % len(available)
        candidate = available[target_idx]
        
        if loc == candidate:
            return candidate
            
        path_check = a_star_search(loc, candidate)
        if len(path_check) > 1:
            return candidate

    return None


# ===========================================================================
# THINK — called once per round per agent by the AEGIS framework
# ===========================================================================

def think():
    """Do not remove this function, it must always be defined."""
    global dig2_waiting, saved_locs, scanned_rubble_locs

    aid = get_id()
    loc = get_location()
    energy = get_energy_level()

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

    # ── Stale target cleanup ────────────────────────────────────────────────
    if dig2_partner_dests[aid] is not None:
        t_loc = key_to_loc(dig2_partner_dests[aid])
        if not isinstance(get_cell_info_at(t_loc).top_layer, Rubble):
            dig2_partner_dests[aid] = None

    # ── PRIORITY 1: Survivor is directly accessible → SAVE ─────────────────
    if isinstance(top, Survivor):
        save()
        key = loc_key(loc)
        saved_locs.append(key)
        send_message(f"{MSG_SAVED}|{loc.x}|{loc.y}", [])
        send_message(MSG_REPLAN, [])
        my_targets[aid] = None
        dig2_partner_dests[aid] = None
        
        if key in dig2_waiting:
            del dig2_waiting[key]
            
        log(f"[A{aid}] SAVED survivor at {loc}")
        return

    # ── PRIORITY 2: Rubble at current location → coordinate DIG ────────────
    if isinstance(top, Rubble):
        rubble = top
        key    = loc_key(loc)

        if rubble.agents_required == 1:
            dig()
            return

        if len(cell.agents) >= 2:
            dig()
            if key in dig2_waiting:
                del dig2_waiting[key]
            log(f"[A{aid}] Cooperative DIG at {loc}")
            return

        if key not in dig2_waiting:
            dig2_waiting[key] = get_round_number()
        elif get_round_number() - dig2_waiting[key] >= MAX_DIG2_WAIT_ROUNDS:
            log(f"[A{aid}] DIG2 timeout at {key}; re-targeting")
            del dig2_waiting[key]
            my_targets[aid] = None
            move(Direction.CENTER)
            return

        send_message(f"{MSG_DIG2_REQ}|{loc.x}|{loc.y}", [])
        move(Direction.CENTER)
        log(f"[A{aid}] Waiting for DIG2 partner at {loc}")
        return

    # ── PRIORITY 3: En route as a committed DIG2 partner ───────────────────
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

    # ── PRIORITY 4: Navigate toward a survivor target ───────────────────────
    if survs:
        best_target = choose_best_target(loc, survs)

        if best_target is not None:
            curr_target = my_targets[aid]
            if curr_target is None or loc_key(best_target) != loc_key(curr_target):
                my_targets[aid] = best_target
                log(f"[A{aid}] Split to target {best_target}")

        curr_target = my_targets[aid]
        if curr_target is not None:
            
            # ── Challenge 3: Drone Scan Distant Rubble ──
            target_key = loc_key(curr_target)
            if target_key not in scanned_rubble_locs:
                target_cell = get_cell_info_at(curr_target)
                if isinstance(target_cell.top_layer, Rubble) and heuristic(loc, curr_target) > 1:
                    scan_result = drone_scan(curr_target)
                    scanned_rubble_locs.add(target_key) # Log it so we don't waste turns scanning it again
                    
                    if scan_result:
                        log(f"[A{aid}] Drone scanned {curr_target}: {scan_result.layers} layers.")
                        if scan_result.layers > 1:
                            send_message(f"{MSG_DIG2_REQ}|{curr_target.x}|{curr_target.y}", [])
                    return 
            
            # ── Standard Movement ──
            next_loc = next_move(loc, curr_target, energy)
            if next_loc is None:
                return
            if isinstance(next_loc, Location):
                move(loc.direction_to(next_loc))
            else:
                move(next_loc)
            return

    # ── PRIORITY 5: Nothing to do — stay in place ──────────────────────────
    move(Direction.CENTER)


# ===========================================================================
# PATHFINDING (Adapted from Camila Hernandez's Assignment 1 submission)
# ===========================================================================

def heuristic(a, b):
    return max(abs(a.x - b.x), abs(a.y - b.y))

def a_star_search(start, goal):
    global astar_counter
    frontier = []
    
    heapq.heappush(frontier, (0, astar_counter, start))
    astar_counter += 1
    
    came_from   = {start: None}
    cost_so_far = {start: 0}

    while frontier:
        _, _, current = heapq.heappop(frontier)

        if current == goal:
            break

        for direction in Direction:
            if direction == Direction.CENTER:
                continue

            adjacent = current.add(direction)

            if not on_map(adjacent):
                continue
                
            cell_info = get_cell_info_at(adjacent)
            
            if cell_info.is_killer_cell():
                continue

            cell_cost = cell_info.move_cost
            
            # treat negative cells as cost 1
            # go through traffic jams
            if cell_cost < 0:
                cell_cost = 1

            new_cost  = cost_so_far[current] + cell_cost

            if adjacent not in cost_so_far or new_cost < cost_so_far[adjacent]:
                cost_so_far[adjacent] = new_cost
                priority = new_cost + heuristic(goal, adjacent)
                
                heapq.heappush(frontier, (priority, astar_counter, adjacent))
                astar_counter += 1
                
                came_from[adjacent] = current

    path    = []
    current = goal
    while current != start:
        path.append(current)
        if current not in came_from:
            return [start]
        current = came_from[current]
    path.append(start)
    path.reverse()
    return path


def closest_target_cell(loc, targets):
    heap = [(heuristic(loc, t), t) for t in targets]
    heapq.heapify(heap)
    return heapq.heappop(heap)[1]

def estimate_path_cost(path):
    cost = 0
    for location in path:
        c = get_cell_info_at(location).move_cost
        cost += 1 if c < 0 else c
    return cost

def nearest_charging_cell(loc):
    chargers = get_charging_cells()
    if not chargers:
        return None
    heap = [(heuristic(loc, c), c) for c in chargers]
    heapq.heapify(heap)
    return heapq.heappop(heap)[1]


# ===========================================================================
# ENERGY-AWARE MOVEMENT (Adapted from Camila Hernandez's Assignment 1 submission)
# ===========================================================================

def next_move(agent_loc, target_loc, energy):
    charging_cells = get_charging_cells()

    if agent_loc in charging_cells:
        path_to_target = a_star_search(agent_loc, target_loc)
        cost_to_target = estimate_path_cost(path_to_target)
        if energy < cost_to_target:
            recharge()
            return None

    path_to_target = a_star_search(agent_loc, target_loc)
    cost_to_target = estimate_path_cost(path_to_target)

    if energy >= cost_to_target:
        if len(path_to_target) > 1:
            return path_to_target[1]
        return Direction.CENTER

    charger = nearest_charging_cell(agent_loc)
    if charger:
        path_to_charger = a_star_search(agent_loc, charger)
        if path_to_charger and len(path_to_charger) > 1:
            return path_to_charger[1]

    return Direction.CENTER