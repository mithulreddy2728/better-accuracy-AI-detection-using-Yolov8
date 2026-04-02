from collections import Counter
import re
from difflib import SequenceMatcher

class AnprProcessor:
    """
    Handles temporal logic for ANPR to stabilize plate text and reduce OCR hallucinations.
    Uses a voting mechanism across multiple frames for each track ID.
    """
    def __init__(self, buffer_size=20, min_votes=3):
        self.buffer_size = buffer_size
        self.min_votes = min_votes
        # track_id -> [list of detected texts]
        self.history = {}
        # track_id -> {'text': str, 'conf': float} (current consensus)
        self.consensus = {}

    def add_prediction(self, track_id, text, confidence):
        """Add a new OCR prediction for a specific track ID"""
        if not text or len(text) < 3:  # Lowered from 4 to 3
            return None

        if track_id not in self.history:
            self.history[track_id] = []

        # High Confidence Override: If we get a very high confidence read, 
        # we can boost its weight in the history
        weight = 1
        if confidence > 0.92: weight = 3
        elif confidence > 0.85: weight = 2
        
        for _ in range(weight):
            self.history[track_id].append(text)
            
        # Keep within buffer size
        if len(self.history[track_id]) > self.buffer_size:
            overage = len(self.history[track_id]) - self.buffer_size
            self.history[track_id] = self.history[track_id][overage:]

        # Calculate new consensus
        return self._calculate_consensus(track_id, confidence)

    def _calculate_consensus(self, track_id, current_conf):
        """Determine the most likely plate text based on history with fuzzy matching"""
        texts = self.history.get(track_id, [])
        if not texts:
            return None

        # Count occurrences with fuzzy matching for similar plates
        fuzzy_groups = {}
        for text in texts:
            matched = False
            for key in fuzzy_groups.keys():
                # Use fuzzy matching (e.g., "ABC123" matches "ABC1Z3" at 83% similarity)
                similarity = SequenceMatcher(None, text, key).ratio()
                if similarity > 0.85:  # 85% similarity threshold
                    fuzzy_groups[key].append(text)
                    matched = True
                    break
            if not matched:
                fuzzy_groups[text] = [text]
        
        # Find the group with most votes
        best_group = max(fuzzy_groups.items(), key=lambda x: len(x[1]))
        best_text = best_group[0]  # Use the key as representative
        vote_count = len(best_group[1])
        
        # Check for ambiguity
        sorted_groups = sorted(fuzzy_groups.items(), key=lambda x: len(x[1]), reverse=True)
        is_ambiguous = len(sorted_groups) > 1 and (len(sorted_groups[0][1]) - len(sorted_groups[1][1]) < 2)

        # Consensus logic
        if vote_count >= self.min_votes and not is_ambiguous:
            # Update consensus cache
            if track_id not in self.consensus or vote_count >= self.consensus[track_id].get('votes', 0):
                self.consensus[track_id] = {
                    'text': best_text,
                    'votes': vote_count,
                    'is_stable': True
                }
            return best_text
        
        # If not yet stable but we have a strong candidate
        if vote_count >= 2 and current_conf > 0.85:  # Lowered from 0.88
             return best_text
             
        return self.consensus.get(track_id, {}).get('text')

    def get_consensus(self, track_id):
        """Retrieve the current consensus for a track ID"""
        return self.consensus.get(track_id, {}).get('text')

    def is_stable(self, track_id):
        """Check if the consensus for a track ID is considered stable"""
        return self.consensus.get(track_id, {}).get('is_stable', False)

    def clear(self, track_id=None):
        """Clear history for a specific track ID or all IDs"""
        if track_id:
            self.history.pop(track_id, None)
            self.consensus.pop(track_id, None)
        else:
            self.history = {}
            self.consensus = {}
