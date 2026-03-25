# Camila Hernandez (30134911) - T01
# Jose Lozano (30144736) - T01
# Matias Campuzano
# Jose Zea (30226527) - T02
# Due Date: 03/27/2026
# CPSC 383 (Winter 2026)

from aegis_game.stub import *
import heapq



# The survivor/rubble location this agent is currently heading toward.
my_target = None            # Location | None

# Targets claimed by other agents: maps loc_key -> agent_id.
# Used to avoid sending multiple agents to the same survivor.
peer_targets = {}           # dict[str, int]

# Survivor locations that have already been rescued (learned via SAVED messages).
saved_locs = set()          # set[str]

# If this agent has committed to be a DIG2 partner, this holds the loc_key
# of the rubble it is heading toward to help dig.
dig2_partner_dest = None    # str | None

# Rubble locations where this agent is waiting for a DIG2 partner:
#   loc_key -> round number when waiting started.
dig2_waiting = {}           # dict[str, int]

# Tracks the last round whose messages have been processed, to prevent
# re-processing the same messages on subsequent think() calls.
last_processed_round = 0    # int

# ===========================================================================
# MESSAGE PROTOCOL CONSTANTS
# ---------------------------------------------------------------------------
# All messages use pipe-separated strings for easy parsing.
#
#   CLAIM|x|y         — "I am claiming the survivor target at (x, y)."
#   SAVED|x|y         — "The survivor at (x, y) has been rescued."
#   DIG2_REQ|x|y      — "I need a second agent to dig rubble at (x, y)."
#   DIG2_ACK|x|y|aid  — "I (agent aid) will come help dig at (x, y)."
# ===========================================================================
MSG_CLAIM    = "CLAIM"
MSG_SAVED    = "SAVED"
MSG_DIG2_REQ = "DIG2_REQ"
MSG_DIG2_ACK = "DIG2_ACK"

# How many rounds to wait for a DIG2 partner before giving up on that rubble.
MAX_DIG2_WAIT_ROUNDS = 10


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
    global peer_targets, saved_locs, dig2_partner_dest
    global last_processed_round, my_target

    current_round = get_round_number()

    for msg in read_messages():
        # Only process messages we have not seen before.
        if msg.round_num <= last_processed_round:
            continue

        parts = msg.message.split("|")
        if not parts:
            continue

        cmd = parts[0]

        # ── CLAIM: another agent claimed a survivor target ──────────────────
        if cmd == MSG_CLAIM and len(parts) >= 3:
            key = f"{parts[1]},{parts[2]}"
            peer_targets[key] = msg.sender_id

        # ── SAVED: a survivor was rescued — remove from tracking ────────────
        elif cmd == MSG_SAVED and len(parts) >= 3:
            key = f"{parts[1]},{parts[2]}"
            saved_locs.add(key)
            # Drop my target if it was the one just saved.
            if my_target is not None and loc_key(my_target) == key:
                my_target = None
            # Drop DIG2 commitment if the destination was saved.
            if dig2_partner_dest == key:
                dig2_partner_dest = None

        # ── DIG2_REQ: a peer needs a second agent to dig rubble ────────────
        elif cmd == MSG_DIG2_REQ and len(parts) >= 3:
            key = f"{parts[1]},{parts[2]}"
            # Only volunteer if this agent is currently idle (no target of its
            # own and no existing DIG2 commitment).
            if my_target is None and dig2_partner_dest is None:
                dig2_partner_dest = key
                send_message(
                    f"{MSG_DIG2_ACK}|{parts[1]}|{parts[2]}|{get_id()}", []
                )

        # ── DIG2_ACK: a partner is coming — stop re-broadcasting ───────────
        elif cmd == MSG_DIG2_ACK and len(parts) >= 4:
            key = f"{parts[1]},{parts[2]}"
            # A partner acknowledged our DIG2_REQ; remove the waiting record
            # so we stop re-broadcasting every round.
            if key in dig2_waiting:
                del dig2_waiting[key]

    last_processed_round = current_round


# ===========================================================================
# TARGET SELECTION
# ===========================================================================

def choose_best_target(loc, survs):
    """
    Return the best survivor Location for this agent to target, or None.

    Priority:
      1. Closest survivor not yet claimed by a peer agent.
      2. Closest survivor among all remaining (if all are claimed).
    """
    available = [s for s in survs if loc_key(s) not in saved_locs]
    if not available:
        return None

    unclaimed = [s for s in available if loc_key(s) not in peer_targets]
    if unclaimed:
        return closest_target_cell(loc, unclaimed)

    # All survivors are claimed — assist the nearest one anyway.
    return closest_target_cell(loc, available)


# ===========================================================================
# THINK — called once per round per agent by the AEGIS framework
# ===========================================================================

def think():
    """Do not remove this function, it must always be defined."""
    global my_target, dig2_partner_dest, dig2_waiting

    loc    = get_location()
    energy = get_energy_level()

    log(f"[A{get_id()}] Round {get_round_number()} | Loc {loc} | Energy {energy}")

    # ── Round 1: stand still to populate adjacency info ────────────────────
    if get_round_number() == 1:
        move(Direction.CENTER)
        return

    # ── Process messages from peers (updates shared coordination state) ─────
    process_messages()

    survs = get_survs()
    cell  = get_cell_info_at(loc)
    top   = cell.top_layer

    # ── Stale target cleanup ────────────────────────────────────────────────
    if my_target is not None and loc_key(my_target) in saved_locs:
        my_target = None

    # ── PRIORITY 1: Survivor is directly accessible → SAVE ─────────────────
    if isinstance(top, Survivor):
        save()
        key = loc_key(loc)
        saved_locs.add(key)
        send_message(f"{MSG_SAVED}|{loc.x}|{loc.y}", [])
        my_target = None
        dig2_partner_dest = None
        if key in dig2_waiting:
            del dig2_waiting[key]
        log(f"[A{get_id()}] SAVED survivor at {loc}")
        return

    # ── PRIORITY 2: Rubble at current location → coordinate DIG ────────────
    if isinstance(top, Rubble):
        rubble = top
        key    = loc_key(loc)

        # Case A: rubble only needs one agent — dig immediately.
        if rubble.agents_required == 1:
            dig()
            return

        # Case B: rubble needs two agents — check if a partner is here.
        # cell.agents lists all agent IDs present at this cell.
        if len(cell.agents) >= 2:
            dig()
            if key in dig2_waiting:
                del dig2_waiting[key]
            log(f"[A{get_id()}] Cooperative DIG at {loc}")
            return

        # Case C: only one agent here — request a partner and wait.
        if key not in dig2_waiting:
            dig2_waiting[key] = get_round_number()
        elif get_round_number() - dig2_waiting[key] >= MAX_DIG2_WAIT_ROUNDS:
            # Waited too long — give up and re-target next round.
            log(f"[A{get_id()}] DIG2 timeout at {key}; re-targeting")
            del dig2_waiting[key]
            my_target = None
            move(Direction.CENTER)
            return

        send_message(f"{MSG_DIG2_REQ}|{loc.x}|{loc.y}", [])
        move(Direction.CENTER)
        log(f"[A{get_id()}] Waiting for DIG2 partner at {loc}")
        return

    # ── PRIORITY 3: En route as a committed DIG2 partner ───────────────────
    if dig2_partner_dest is not None:
        target = key_to_loc(dig2_partner_dest)

        if loc == target:
            # Arrived — stay in place so both agents see each other next round.
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
        if my_target is None or loc_key(my_target) in saved_locs:
            my_target = choose_best_target(loc, survs)
            if my_target is not None:
                send_message(f"{MSG_CLAIM}|{my_target.x}|{my_target.y}", [])
                log(f"[A{get_id()}] Claimed target {my_target}")

        if my_target is not None:
            next_loc = next_move(loc, my_target, energy)
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
# PATHFINDING  (adapted from Camila's Assignment 1 submission)
# ===========================================================================

# Chebyshev distance heuristic — works for 8-directional movement.
# Adapted from: https://www.geeksforgeeks.org/machine-learning/chebyshev-distance/
def heuristic(a, b):
    return max(abs(a.x - b.x), abs(a.y - b.y))


# A* search returning the full path from start to goal as a list of Locations.
# Pseudocode reference: https://www.redblobgames.com/pathfinding/a-star/introduction.html
def a_star_search(start, goal):
    dir_priority = {
        Direction.NORTH:     0,
        Direction.NORTHEAST: 1,
        Direction.EAST:      2,
        Direction.SOUTHEAST: 3,
        Direction.SOUTH:     4,
        Direction.SOUTHWEST: 5,
        Direction.WEST:      6,
        Direction.NORTHWEST: 7,
        Direction.CENTER:    8,
    }

    frontier = []
    heapq.heappush(frontier, (0, 0, start))
    came_from   = {start: None}
    cost_so_far = {start: 0}

    while frontier:
        _, _, current = heapq.heappop(frontier)

        if current == goal:
            break

        for direction in Direction:
            adjacent = current.add(direction)

            if not on_map(adjacent):
                continue
            if get_cell_info_at(adjacent).is_killer_cell():
                continue

            cell_cost = get_cell_info_at(adjacent).move_cost
            new_cost  = cost_so_far[current] + cell_cost

            if adjacent not in cost_so_far or new_cost < cost_so_far[adjacent]:
                cost_so_far[adjacent] = new_cost
                priority = new_cost + heuristic(goal, adjacent)
                heapq.heappush(
                    frontier,
                    (priority, dir_priority[direction], adjacent)
                )
                came_from[adjacent] = current

    path    = []
    current = goal
    while current != start:
        path.append(current)
        if current not in came_from:
            log(f"[A{get_id()}] A* could not reconstruct path {current} -> {start}")
            return [start]
        current = came_from[current]
    path.append(start)
    path.reverse()
    return path


def closest_target_cell(loc, targets):
    """Return the target Location closest to loc using the Chebyshev heuristic."""
    heap = [(heuristic(loc, t), t) for t in targets]
    heapq.heapify(heap)
    return heapq.heappop(heap)[1]


def estimate_path_cost(path):
    """Sum the move costs of all cells along the given path."""
    return sum(get_cell_info_at(location).move_cost for location in path)


def nearest_charging_cell(loc):
    """Return the charging cell Location closest to loc, or None if none exist."""
    chargers = get_charging_cells()
    if not chargers:
        return None
    heap = [(heuristic(loc, c), c) for c in chargers]
    heapq.heapify(heap)
    return heapq.heappop(heap)[1]


# ===========================================================================
# ENERGY-AWARE MOVEMENT  (adapted from Camila's Assignment 1 submission)
# ===========================================================================

def next_move(agent_loc, target_loc, energy):
    charging_cells = get_charging_cells()

    # If standing on a charger and energy is insufficient to reach target, recharge.
    if agent_loc in charging_cells:
        path_to_target = a_star_search(agent_loc, target_loc)
        cost_to_target = estimate_path_cost(path_to_target)
        if energy < cost_to_target:
            recharge()
            return None

    path_to_target = a_star_search(agent_loc, target_loc)
    cost_to_target = estimate_path_cost(path_to_target)

    # Enough energy to reach the target directly.
    if energy >= cost_to_target:
        if len(path_to_target) > 1:
            return path_to_target[1]
        return Direction.CENTER

    # Not enough energy — route to the nearest charger instead.
    charger = nearest_charging_cell(agent_loc)
    if charger:
        path_to_charger = a_star_search(agent_loc, charger)
        if path_to_charger and len(path_to_charger) > 1:
            return path_to_charger[1]

    return Direction.CENTER
