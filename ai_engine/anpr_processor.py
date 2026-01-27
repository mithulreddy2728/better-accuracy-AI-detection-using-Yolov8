from collections import Counter
import re

class AnprProcessor:
    """
    Handles temporal logic for ANPR to stabilize plate text and reduce OCR hallucinations.
    Uses a voting mechanism across multiple frames for each track ID.
    """
    def __init__(self, buffer_size=12, min_votes=4):
        self.buffer_size = buffer_size
        self.min_votes = min_votes
        # track_id -> [list of detected texts]
        self.history = {}
        # track_id -> {'text': str, 'conf': float} (current consensus)
        self.consensus = {}

    def add_prediction(self, track_id, text, confidence):
        """Add a new OCR prediction for a specific track ID"""
        if not text or len(text) < 4:
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
        """Determine the most likely plate text based on history with confidence weighting"""
        texts = self.history.get(track_id, [])
        if not texts:
            return None

        # Count occurrences
        counts = Counter(texts)
        most_common = counts.most_common(2)
        
        if not most_common:
            return None

        best_text, vote_count = most_common[0]
        
        # Check for ambiguity (if top 2 are very close)
        is_ambiguous = len(most_common) > 1 and (most_common[0][1] - most_common[1][1] < 2)

        # High strictness for stability
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
        if vote_count >= 2 and current_conf > 0.88:
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
