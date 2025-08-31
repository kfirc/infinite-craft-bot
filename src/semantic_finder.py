#!/usr/bin/env python3
"""
Semantic Word Finder for Infinite Craft Automation

This module provides intelligent word combination suggestions using semantic similarity.
Instead of random combinations, it finds pairs of available elements that are most
likely to produce a target word based on word embeddings and cosine similarity.

Usage:
    finder = SemanticWordFinder()
    best_pairs = finder.find_best_combinations(available_words, target_word, top_k=5)
"""

import numpy as np
from itertools import combinations
from typing import List, Dict, Optional
from datetime import datetime
import json
import os

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("⚠️ sentence-transformers not available. Install with: pip install sentence-transformers")


class SemanticWordFinder:
    """
    Intelligent word combination finder using semantic similarity.
    
    Finds pairs of words that when semantically combined are most likely
    to produce a target word in Infinite Craft.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", cache_file: str = "../embeddings.cache.json"):
        """
        Initialize the semantic finder with word embeddings model.
        
        Args:
            model_name: HuggingFace sentence transformer model name
            cache_file: Path to cache embeddings for performance
        """
        self.model = None
        self.model_name = model_name
        self.cache_file = cache_file
        self.embeddings_cache = {}
        
        # Load cached embeddings if available
        self._load_embeddings_cache()
        
        # Initialize model if available
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.log("INFO", f"🧠 Loading semantic model: {model_name}")
                self.model = SentenceTransformer(model_name)
                self.log("INFO", f"✅ Semantic model loaded successfully")
            except Exception as e:
                self.log("ERROR", f"❌ Failed to load model: {e}")
                self.model = None
        else:
            self.log("WARNING", "⚠️ Sentence transformers not available - falling back to basic heuristics")
    
    def log(self, level: str, message: str):
        """Simple logging with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
    
    def _load_embeddings_cache(self):
        """Load cached embeddings from file for performance."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    self.embeddings_cache = {
                        word: np.array(embedding) 
                        for word, embedding in cache_data.items()
                    }
                self.log("INFO", f"📥 Loaded {len(self.embeddings_cache)} cached embeddings")
        except Exception as e:
            self.log("WARNING", f"⚠️ Failed to load embeddings cache: {e}")
            self.embeddings_cache = {}
    
    def _save_embeddings_cache(self):
        """Save embeddings cache to file."""
        try:
            cache_data = {
                word: embedding.tolist() 
                for word, embedding in self.embeddings_cache.items()
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            self.log("DEBUG", f"💾 Saved {len(self.embeddings_cache)} embeddings to cache")
        except Exception as e:
            self.log("WARNING", f"⚠️ Failed to save embeddings cache: {e}")
    
    def get_word_embedding(self, word: str) -> Optional[np.ndarray]:
        """
        Get word embedding, using cache when possible.
        
        Args:
            word: Word to get embedding for
            
        Returns:
            Embedding vector or None if model unavailable
        """
        if not self.model:
            return None
            
        # Check cache first
        if word in self.embeddings_cache:
            return self.embeddings_cache[word]
        
        try:
            # Generate embedding
            embedding = self.model.encode(word)
            
            # Cache it
            self.embeddings_cache[word] = embedding
            
            return embedding
            
        except Exception as e:
            self.log("WARNING", f"⚠️ Failed to get embedding for '{word}': {e}")
            return None
    
    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        except:
            return 0.0
    
    def semantic_merge(self, word1_embedding: np.ndarray, word2_embedding: np.ndarray, 
                      alpha: float = 0.5) -> np.ndarray:
        """
        Create semantic merge of two word embeddings.
        
        Args:
            word1_embedding: First word's embedding
            word2_embedding: Second word's embedding  
            alpha: Weight for first word (0.5 = equal average)
            
        Returns:
            Merged embedding vector
        """
        return alpha * word1_embedding + (1 - alpha) * word2_embedding
    
    def find_best_combinations(self, available_words: List[str], target_word: str, 
                              top_k: int = 5, test_alphas: bool = False) -> List[Dict]:
        """
        Find best word combinations to reach target word.
        
        Args:
            available_words: List of words available in sidebar
            target_word: Target word to reach
            top_k: Number of top combinations to return
            test_alphas: Whether to test different merge weights
            
        Returns:
            List of combination suggestions with scores
        """
        if not self.model:
            self.log("WARNING", "⚠️ Model not available - using fallback heuristics")
            return self._fallback_heuristics(available_words, target_word, top_k)
        
        self.log("INFO", f"🎯 Finding best combinations for target: '{target_word}'")
        self.log("INFO", f"📋 Available words: {len(available_words)}")
        
        # Get target embedding
        target_embedding = self.get_word_embedding(target_word)
        if target_embedding is None:
            self.log("ERROR", f"❌ Cannot get embedding for target word: {target_word}")
            return []
        
        # Get embeddings for all available words
        word_embeddings = {}
        for word in available_words:
            embedding = self.get_word_embedding(word)
            if embedding is not None:
                word_embeddings[word] = embedding
        
        if len(word_embeddings) < 2:
            self.log("ERROR", f"❌ Not enough words with embeddings: {len(word_embeddings)}")
            return []
        
        self.log("INFO", f"🧠 Computing similarities for {len(word_embeddings)} words...")
        
        # Find best combinations
        combinations_scores = []
        total_combinations = len(list(combinations(word_embeddings.keys(), 2)))
        processed = 0
        
        for word1, word2 in combinations(word_embeddings.keys(), 2):
            processed += 1
            if processed % 1000 == 0:
                self.log("DEBUG", f"📊 Processed {processed}/{total_combinations} combinations...")
            
            best_score = -1
            best_alpha = 0.5
            
            # Test different merge weights if requested
            if test_alphas:
                alphas = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
            else:
                alphas = [0.5]  # Just equal average
            
            for alpha in alphas:
                merged = self.semantic_merge(
                    word_embeddings[word1], 
                    word_embeddings[word2], 
                    alpha
                )
                score = self.cosine_similarity(merged, target_embedding)
                
                if score > best_score:
                    best_score = score
                    best_alpha = alpha
            
            combinations_scores.append({
                'word1': word1,
                'word2': word2,
                'score': best_score,
                'alpha': best_alpha,
                'confidence': 'high' if best_score > 0.7 else 'medium' if best_score > 0.5 else 'low'
            })
        
        # Sort by score and return top k
        combinations_scores.sort(key=lambda x: x['score'], reverse=True)
        top_combinations = combinations_scores[:top_k]
        
        self.log("INFO", f"🏆 Top {len(top_combinations)} combinations found:")
        for i, combo in enumerate(top_combinations, 1):
            self.log("INFO", f"  {i}. {combo['word1']} + {combo['word2']} → {combo['score']:.3f} ({combo['confidence']})")
        
        # Save cache after processing
        self._save_embeddings_cache()
        
        return top_combinations
    
    def _fallback_heuristics(self, available_words: List[str], target_word: str, 
                           top_k: int) -> List[Dict]:
        """
        Fallback heuristics when embeddings model is not available.
        
        Uses simple string-based heuristics like:
        - Words that share letters with target
        - Words that are related conceptually (hardcoded)
        """
        self.log("INFO", f"🔧 Using fallback heuristics for target: '{target_word}'")
        
        # Simple conceptual mappings
        concept_map = {
            'forest': ['tree', 'wood', 'plant', 'earth', 'green'],
            'ocean': ['water', 'fish', 'blue', 'wave', 'sea'],
            'mountain': ['rock', 'earth', 'stone', 'high', 'peak'],
            'dragon': ['fire', 'legend', 'myth', 'magic', 'beast'],
            'robot': ['metal', 'machine', 'electric', 'gear', 'tech'],
            'castle': ['stone', 'king', 'medieval', 'tower', 'fortress'],
            'wizard': ['magic', 'spell', 'wand', 'mystical', 'power']
        }
        
        combinations_scores = []
        target_lower = target_word.lower()
        
        # Find related words
        related_words = concept_map.get(target_lower, [])
        
        for word1, word2 in combinations(available_words, 2):
            score = 0
            
            # Letter overlap scoring
            w1_lower = word1.lower()
            w2_lower = word2.lower()
            
            # Score based on letter overlap with target
            target_letters = set(target_lower)
            w1_overlap = len(set(w1_lower) & target_letters) / len(target_letters)
            w2_overlap = len(set(w2_lower) & target_letters) / len(target_letters)
            score += (w1_overlap + w2_overlap) * 0.3
            
            # Score based on conceptual relation
            if w1_lower in related_words:
                score += 0.5
            if w2_lower in related_words:
                score += 0.5
                
            # Bonus if both words are related
            if w1_lower in related_words and w2_lower in related_words:
                score += 0.3
            
            combinations_scores.append({
                'word1': word1,
                'word2': word2,
                'score': score,
                'alpha': 0.5,
                'confidence': 'heuristic'
            })
        
        # Sort and return top k
        combinations_scores.sort(key=lambda x: x['score'], reverse=True)
        return combinations_scores[:top_k]
    
    def is_model_available(self) -> bool:
        """Check if semantic model is available."""
        return self.model is not None


# Test function
def test_semantic_finder():
    """Test the semantic finder with sample data."""
    print("🧪 Testing Semantic Word Finder")
    print("=" * 50)
    
    finder = SemanticWordFinder()
    
    # Sample test data
    available_words = [
        "Water", "Fire", "Wind", "Earth", "Plant", "Steam", 
        "Cloud", "Rain", "Lightning", "Tree", "Wood", "Metal",
        "Stone", "Glass", "Ice", "Mud", "Sand", "Dust"
    ]
    
    target_word = "Forest"
    
    print(f"Available words: {available_words}")
    print(f"Target word: {target_word}")
    print()
    
    # Find best combinations
    results = finder.find_best_combinations(available_words, target_word, top_k=5)
    
    if results:
        print("🏆 BEST COMBINATIONS:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['word1']} + {result['word2']} = {result['score']:.3f} ({result['confidence']})")
    else:
        print("❌ No combinations found")
    
    return results


if __name__ == "__main__":
    test_semantic_finder()
