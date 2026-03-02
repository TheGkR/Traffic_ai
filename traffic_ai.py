# traffic_ai.py
# System: Pressure-Based Adaptive Control (PB-ACS)
# Logic: Dynamic Scoring with Cycle Cooldowns

import random


class TrafficBrain:
    def __init__(self):
        # --- CONFIGURATION ---
        self.MIN_GREEN_TIME = 60  # ~1 sec (Prevents flickering)
        self.MAX_GREEN_TIME = 450  # ~7.5 sec (Prevents locking)
        self.ORANGE_TIME = 60  # ~1 sec (Clearance)

        # State Tracking
        self.current_phase_timer = 0
        self.pending_switch_target = None
        self.last_green_lane = None  # Remembers who went last to prevent loops

        # --- AI WEIGHTS (The "IQ") ---
        # 1. Queue Weight: How much we care about the # of cars
        self.W_QUEUE = 3.0

        # 2. Starvation Factor: How much we care about wait time
        # This grows exponentially. 10s wait is bad, 60s wait is CRITICAL.
        self.W_WAIT = 0.05

        # 3. Cooldown Penalty: Punishment for "Hogging" the green light
        # If a lane was just green, we subtract this from its score to let others go.
        self.COOLDOWN_PENALTY = 50.0

    def calculate_urgency(self, lane, data, current_green_lane):
        """
        Calculates a 'Pressure Score' for a lane.
        Formula: (Cars * 3) + (WaitTime * 0.05) - (Cooldown)
        """
        count = data[lane]['count']
        wait = data[lane]['total_wait']

        # Base Score (Throughput Focus)
        score = (count * self.W_QUEUE) + (wait * self.W_WAIT)

        # --- LOGIC FIX: THE ANTIDOTE TO PAIRING ---
        # If this lane was the LAST one to be green (before the current one),
        # we punish it heavily so it doesn't immediately grab the light back.
        if lane == self.last_green_lane and count < 8:
            # Only apply penalty if traffic is not critical (>8 cars overrides penalty)
            score -= self.COOLDOWN_PENALTY

        # --- SURVIVAL BONUS ---
        # If this lane is ALREADY green, give small bonus to keep flow smooth
        if lane == current_green_lane:
            score += 5.0

        return score

    def get_decision(self, current_state, sensor_data, emergency_data):
        self.current_phase_timer += 1

        parts = current_state.split('_')
        current_dir = parts[0]
        color = parts[1]

        # ==========================================
        # PRIORITY 0: EMERGENCY OVERRIDE (Ambulance)
        # ==========================================
        emergency_lane = None
        for direction, has_ambulance in emergency_data.items():
            if has_ambulance: emergency_lane = direction; break

        if emergency_lane:
            # If we are already serving the ambulance, stay Green.
            if current_dir == emergency_lane and color == 'GREEN':
                return current_state

            # If ambulance is blocked, switch IMMEDIATELY (Reset timer)
            elif current_dir != emergency_lane and color == 'GREEN':
                self.current_phase_timer = 0
                self.pending_switch_target = emergency_lane
                # Remember who we are switching FROM
                self.last_green_lane = current_dir
                return f"{current_dir}_ORANGE"

        # ==========================================
        # PRIORITY 1: ORANGE LIGHT SEQUENCER
        # ==========================================
        if color == 'ORANGE':
            if self.current_phase_timer > self.ORANGE_TIME:
                self.current_phase_timer = 0
                next_dir = self.pending_switch_target
                return f"{next_dir}_GREEN"
            else:
                return current_state

        # ==========================================
        # PRIORITY 2: ADAPTIVE AI LOGIC
        # ==========================================
        elif color == 'GREEN':
            # A. SAFETY LOCK (Minimum time)
            if self.current_phase_timer < self.MIN_GREEN_TIME:
                return current_state

            # B. CALCULATE SCORES
            scores = {}
            for lane in ['N', 'S', 'E', 'W']:
                scores[lane] = self.calculate_urgency(lane, sensor_data, current_dir)

            # Identify the "Challenger" (The lane with highest urgency)
            # We filter out the current lane to find the best alternative
            other_lanes = {k: v for k, v in scores.items() if k != current_dir}
            best_challenger = max(other_lanes, key=other_lanes.get)
            challenger_score = scores[best_challenger]
            current_score = scores[current_dir]

            should_switch = False

            # C. DECISION GATES

            # Gate 1: Hard Time Limit
            if self.current_phase_timer > self.MAX_GREEN_TIME:
                should_switch = True

            # Gate 2: The "Overwhelming" Check
            # If a challenger has DOUBLE the pressure of current lane, switch early.
            elif challenger_score > (current_score * 2.0) + 10:
                should_switch = True

            # Gate 3: The "Empty Road" Check
            # If current lane is empty (Score < 5) and ANYONE else is waiting
            elif current_score < 5.0 and challenger_score > 5.0:
                should_switch = True

            # D. EXECUTION
            if should_switch:
                self.current_phase_timer = 0
                self.pending_switch_target = best_challenger
                self.last_green_lane = current_dir  # Mark this lane as "Used"
                return f"{current_dir}_ORANGE"

            return current_state
