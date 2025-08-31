"""Intelligent word combination finder using semantic similarity."""

import json
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None
    np = None

try:
    from sklearn.metrics.pairwise import cosine_similarity

    COSINE_SIMILARITY_AVAILABLE = True
except ImportError:
    COSINE_SIMILARITY_AVAILABLE = False
    cosine_similarity = None


# Fallback implementations for missing dependencies
def fallback_cosine_similarity(vec1, vec2):
    """Simple cosine similarity implementation."""
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(a * a for a in vec2) ** 0.5

    return dot_product / (magnitude1 * magnitude2) if magnitude1 * magnitude2 != 0 else 0.0


class SemanticService:
    """
    Intelligent word combination finder using semantic similarity.

    Finds pairs of words that when semantically combined are most likely
    to produce a target word in Infinite Craft.

    This is the main entry point that coordinates the combination finding process.
    Broken into smaller methods to avoid monolithic code.
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

        # Incremental processing optimization
        self.last_processed_elements = set()
        self.semantic_scores_cache = {}  # Cache for semantic similarity scores
        self.current_target_word = None

        # Load cached embeddings if available
        self._load_embeddings_cache()

        # Initialize model if available
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.log("INFO", f"🧠 Loading semantic model: {model_name}")
                self.model = SentenceTransformer(model_name)
                self.log("INFO", "✅ Semantic model loaded successfully")
            except Exception as e:
                self.log("ERROR", f"❌ Failed to load model: {e}")
                self.model = None
        else:
            self.log("WARNING", "⚠️ Sentence transformers not available - falling back to basic heuristics")

    def log(self, level: str, message: str):
        """Log a message with a timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def _load_embeddings_cache(self):
        """Load cached embeddings from file for performance, respecting IGNORE_CACHE."""
        try:
            # Check IGNORE_CACHE setting
            from config import config

            ignore_cache = getattr(config, "IGNORE_CACHE", False)

            if ignore_cache:
                self.log("INFO", "🔄 IGNORE_CACHE enabled - starting with empty embeddings cache")
                self.embeddings_cache = {}
                return

            cache_path = Path(self.cache_file)
            if cache_path.exists():
                with open(cache_path, "r") as f:
                    cache_data = json.load(f)
                    self.embeddings_cache = {k: np.array(v) if np else v for k, v in cache_data.items()}
                self.log("INFO", f"📥 Loaded {len(self.embeddings_cache)} cached embeddings")
            else:
                self.log("INFO", "📝 No embedding cache found - will create new one")
                self.embeddings_cache = {}
        except Exception as e:
            self.log("WARNING", f"⚠️ Failed to load embedding cache: {e}")
            self.embeddings_cache = {}

    def _save_embeddings_cache(self):
        """Save embeddings cache to file, merging with existing embeddings."""
        try:
            cache_path = Path(self.cache_file)
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing embeddings if file exists
            existing_embeddings = {}
            if cache_path.exists():
                try:
                    with open(cache_path, "r") as f:
                        existing_data = json.load(f)
                        existing_embeddings = {k: np.array(v) if np else v for k, v in existing_data.items()}
                        self.log("DEBUG", f"📥 Loaded {len(existing_embeddings)} existing embeddings for merging")
                except Exception as e:
                    self.log("WARNING", f"⚠️ Could not load existing embeddings for merging: {e}")

            # Merge session embeddings with existing (session takes precedence)
            merged_embeddings = existing_embeddings.copy()
            merged_embeddings.update(self.embeddings_cache)

            # Convert numpy arrays to lists for JSON serialization
            cache_data = {k: v.tolist() if hasattr(v, "tolist") else v for k, v in merged_embeddings.items()}

            with open(cache_path, "w") as f:
                json.dump(cache_data, f)

            self.log(
                "DEBUG",
                f"💾 Merged and saved {len(cache_data)} embeddings to cache (session: {
                    len(self.embeddings_cache)}, total: {len(cache_data)})",
            )
        except Exception as e:
            self.log("WARNING", f"⚠️ Failed to save embedding cache: {e}")

    def get_word_embedding(self, word: str) -> Optional[np.ndarray]:
        """
        Get word embedding, using cache when possible.

        Args:
            word: Word to get embedding for

        Returns:
            Embedding vector or None if unavailable
        """
        if not self.model:
            return None

        # Check cache first
        if word in self.embeddings_cache:
            cached = self.embeddings_cache[word]
            return np.array(cached) if np else cached

        try:
            # Generate new embedding
            embedding = self.model.encode([word])[0]
            self.embeddings_cache[word] = embedding
            return embedding
        except Exception as e:
            self.log("WARNING", f"⚠️ Failed to get embedding for '{word}': {e}")
            return None

    def cosine_similarity(self, vec1, vec2) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score (0-1)
        """
        if COSINE_SIMILARITY_AVAILABLE and np is not None:
            return cosine_similarity([vec1], [vec2])[0][0]
        else:
            return fallback_cosine_similarity(vec1, vec2)

    def semantic_merge(self, word1_embedding, word2_embedding, alpha: float = 0.5):
        """
        Merge two word embeddings using weighted average.

        Args:
            word1_embedding: First word embedding
            word2_embedding: Second word embedding
            alpha: Weight for first word (0.5 = equal average)

        Returns:
            Merged embedding vector
        """
        return alpha * word1_embedding + (1 - alpha) * word2_embedding

    def find_best_combinations(
        self,
        available_words: List[str],
        target_word: str,
        top_k: int = 5,
        test_alphas: bool = False,
        cache_service=None,
    ) -> List[Dict]:
        """
        Find best word combinations to reach target word.

        This is the main entry point that coordinates the combination finding process.
        Broken into smaller methods to avoid monolithic code.

        Args:
            available_words: List of words available in sidebar
            target_word: Target word to reach
            top_k: Number of top combinations to return
            test_alphas: Whether to test different merge weights
            cache_service: Optional cache service to filter out already tested combinations

        Returns:
            List of combination suggestions with scores
        """
        if not self.model:
            self.log("WARNING", "⚠️ Model not available - using fallback heuristics")
            return self._fallback_heuristics(available_words, target_word, top_k)

        # Check if we can use incremental processing
        current_elements = set(available_words)
        target_changed = self.current_target_word != target_word

        if target_changed:
            self.log(
                "INFO",
                f"🎯 Target changed from '{self.current_target_word}' to '{
                    target_word}' - semantic recalculation needed",
            )
            # Only clear semantic cache if target actually changed, not on every call
            self.semantic_scores_cache.clear()
            self.current_target_word = target_word

        new_elements = current_elements - self.last_processed_elements

        if new_elements and not target_changed:
            self.log(
                "INFO",
                f"🔄 Incremental processing: {
                    len(new_elements)} new elements detected ({
                    ', '.join(
                        list(new_elements)[
                            :5])}{
                        ', ...' if len(new_elements) > 5 else ''})",
            )
            return self._incremental_processing(
                available_words, target_word, new_elements, top_k, test_alphas, cache_service
            )
        elif not new_elements and not target_changed and self.semantic_scores_cache:
            self.log(
                "INFO", f"⚡ No new elements - using cached semantic scores ({len(self.semantic_scores_cache)} cached)"
            )
            # IGNORE_CACHE only affects initial loading, not runtime cache usage
            return self._get_top_from_cache(top_k, cache_service)
        else:
            self.log("INFO", f"🔄 Full semantic processing: {len(available_words)} elements")
            return self._full_processing(available_words, target_word, top_k, test_alphas, cache_service)

    def _prepare_embeddings(self, available_words: List[str], target_word: str) -> tuple:
        """Prepare target and word embeddings."""
        self.log("INFO", f"🎯 Finding best combinations for target: '{target_word}'")
        self.log("INFO", f"📋 Available words: {len(available_words)}")

        # Get target embedding
        target_embedding = self.get_word_embedding(target_word)
        if target_embedding is None:
            self.log("ERROR", f"❌ Could not get embedding for target word: {target_word}")
            return None, {}

        # Get embeddings for all available words
        word_embeddings = {}
        for word in available_words:
            embedding = self.get_word_embedding(word)
            if embedding is not None:
                word_embeddings[word] = embedding

        if len(word_embeddings) < 2:
            self.log("ERROR", f"❌ Not enough words with embeddings: {len(word_embeddings)}")
            return None, {}

        self.log("INFO", f"🧠 Computing similarities for {len(word_embeddings)} words...")
        return target_embedding, word_embeddings

    def _generate_and_filter_combinations(self, word_embeddings: Dict, cache_service) -> List[tuple]:
        """Generate all possible combinations and filter cached ones if needed."""

        # Generate all possible combinations including same word twice
        all_possible_combinations = []
        word_list = list(word_embeddings.keys())

        # Add combinations without repetition (A+B where A != B)
        for word1, word2 in combinations(word_list, 2):
            all_possible_combinations.append((word1, word2))

        # Add combinations with repetition (A+A)
        for word in word_list:
            all_possible_combinations.append((word, word))

        # Filter out cached combinations BEFORE expensive semantic computation
        if cache_service:
            filtered_combinations = []
            cached_count = 0
            for word1, word2 in all_possible_combinations:
                # Only keep uncached combinations
                if not cache_service.is_combination_tested_by_names(word1, word2):
                    filtered_combinations.append((word1, word2))
                else:
                    cached_count += 1
                    if cached_count <= 5:  # Only show first 5 for brevity
                        self.log("DEBUG", f"⏭️ Skipping cached combination: {word1} + {word2}")

            combinations_to_test = filtered_combinations
            self.log(
                "INFO",
                f"🔍 Filtered {len(all_possible_combinations)
                              } -> {len(combinations_to_test)} uncached combinations ({cached_count} cached)",
            )
        else:
            combinations_to_test = all_possible_combinations
            self.log(
                "INFO", f"🔍 No cache service provided - testing all {len(all_possible_combinations)} combinations"
            )

        if not combinations_to_test:
            self.log("INFO", "⚠️ No uncached combinations found")

        return combinations_to_test

    def _score_combinations(
        self, combinations_to_test: List[tuple], word_embeddings: Dict, target_embedding, test_alphas: bool
    ) -> List[Dict]:
        """Score all combinations using semantic similarity."""
        combinations_scores = []
        total_combinations = len(combinations_to_test)
        processed = 0

        for word1, word2 in combinations_to_test:
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
                merged = self.semantic_merge(word_embeddings[word1], word_embeddings[word2], alpha)
                score = self.cosine_similarity(merged, target_embedding)

                if score > best_score:
                    best_score = score
                    best_alpha = alpha

            combinations_scores.append(
                {
                    "word1": word1,
                    "word2": word2,
                    "score": best_score,
                    "alpha": best_alpha,
                    "confidence": "high" if best_score > 0.7 else "medium" if best_score > 0.5 else "low",
                }
            )

        return combinations_scores

    def _format_top_results(self, combinations_scores: List[Dict], top_k: int) -> List[Dict]:
        """Sort and format top combinations."""
        # Sort by score and return top k
        combinations_scores.sort(key=lambda x: x["score"], reverse=True)
        top_combinations = combinations_scores[:top_k]

        self.log("INFO", f"🏆 Top {len(top_combinations)} semantic combinations:")
        for i, combo in enumerate(top_combinations, 1):
            self.log(
                "INFO",
                f"  {i}. {
                    combo['word1']} + {
                    combo['word2']} → {
                    combo['score']:.3f} ({
                    combo['confidence']})",
            )

        # Save cache after processing
        self._save_embeddings_cache()

        return top_combinations

    def _fallback_heuristics(self, available_words: List[str], target_word: str, top_k: int) -> List[Dict]:
        """
        Fallback heuristics when embeddings model is not available.

        Uses simple string-based heuristics like:
        - Words that share letters with target
        - Words that are related conceptually (hardcoded)
        """
        self.log("INFO", f"🔧 Using fallback heuristics for target: '{target_word}'")

        # Simple conceptual mappings
        concept_map = {
            "forest": ["tree", "wood", "plant", "earth", "green"],
            "ocean": ["water", "fish", "blue", "wave", "sea"],
            "mountain": ["rock", "earth", "stone", "high", "peak"],
            "dragon": ["fire", "legend", "myth", "magic", "beast"],
            "robot": ["metal", "machine", "electric", "gear", "tech"],
            "castle": ["stone", "king", "medieval", "tower", "fortress"],
            "wizard": ["magic", "spell", "wand", "mystical", "power"],
        }

        combinations_scores = []
        target_lower = target_word.lower()

        # Find related words
        related_words = concept_map.get(target_lower, [])

        # Score combinations based on simple heuristics
        for word1 in available_words:
            for word2 in available_words:
                if word1 >= word2:  # Avoid duplicates (A+B vs B+A)
                    continue

                score = 0.0

                # Boost if either word is conceptually related
                if word1.lower() in related_words or word2.lower() in related_words:
                    score += 0.5

                # Boost if words share letters with target
                shared_letters1 = len(set(word1.lower()) & set(target_lower))
                shared_letters2 = len(set(word2.lower()) & set(target_lower))
                score += (shared_letters1 + shared_letters2) * 0.1

                # Boost for shorter words (easier to combine)
                if len(word1) < 6 and len(word2) < 6:
                    score += 0.2

                if score > 0.1:  # Only include combinations with some potential
                    combinations_scores.append(
                        {
                            "word1": word1,
                            "word2": word2,
                            "score": min(score, 0.9),  # Cap at 0.9 to show these are heuristic
                            "alpha": 0.5,
                            "confidence": "low",
                        }
                    )

        # Sort and return top results
        combinations_scores.sort(key=lambda x: x["score"], reverse=True)
        return combinations_scores[:top_k]

    def _full_processing(
        self, available_words: List[str], target_word: str, top_k: int, test_alphas: bool, cache_service
    ) -> List[Dict]:
        """Full semantic processing when target changes or first run."""
        # Step 1: Prepare embeddings
        target_embedding, word_embeddings = self._prepare_embeddings(available_words, target_word)
        if target_embedding is None or len(word_embeddings) < 2:
            return []

        # Step 2: Generate and filter combinations
        combinations_to_test = self._generate_and_filter_combinations(word_embeddings, cache_service)
        if not combinations_to_test:
            return []

        # Step 3: Score combinations and cache results
        combinations_scores = self._score_combinations(
            combinations_to_test, word_embeddings, target_embedding, test_alphas
        )

        # Cache the scores for future incremental processing
        for combo in combinations_scores:
            cache_key = f"{combo['word1']}+{combo['word2']}"
            self.semantic_scores_cache[cache_key] = combo

        # Update tracking
        self.last_processed_elements = set(available_words)

        # Step 4: Return top results
        return self._format_top_results(combinations_scores, top_k)

    def _incremental_processing(
        self,
        available_words: List[str],
        target_word: str,
        new_elements: set,
        top_k: int,
        test_alphas: bool,
        cache_service,
    ) -> List[Dict]:
        """Incremental processing - only compute combinations involving new elements."""
        # Step 1: Prepare embeddings (only for new elements + target)
        target_embedding = self.get_word_embedding(target_word)
        if target_embedding is None:
            return []

        # Get embeddings for new elements only
        new_word_embeddings = {}
        for word in new_elements:
            embedding = self.get_word_embedding(word)
            if embedding is not None:
                new_word_embeddings[word] = embedding

        # Get embeddings for all words (for combinations with existing elements)
        all_word_embeddings = {}
        for word in available_words:
            embedding = self.get_word_embedding(word)
            if embedding is not None:
                all_word_embeddings[word] = embedding

        if not new_word_embeddings or len(all_word_embeddings) < 2:
            # No new embeddings, return cached results
            return self._get_top_from_cache(top_k, cache_service)

        # Step 2: Generate combinations involving new elements
        new_combinations = []

        # New element + any other element (including other new elements)
        for new_word in new_word_embeddings.keys():
            for other_word in all_word_embeddings.keys():
                if new_word != other_word:
                    # Ensure consistent ordering to avoid duplicates
                    word1, word2 = sorted([new_word, other_word])
                    new_combinations.append((word1, word2))
                # Also add self-combinations for new elements
                elif new_word == other_word:
                    new_combinations.append((new_word, new_word))

        # Remove duplicates and filter cached combinations
        new_combinations = list(set(new_combinations))
        combinations_to_test = self._filter_cached_combinations(new_combinations, cache_service)

        self.log(
            "INFO",
            f"🔄 Processing {len(combinations_to_test)} new combinations (filtered from {len(new_combinations)})",
        )

        # Step 3: Score only new combinations
        if combinations_to_test:
            new_combinations_scores = self._score_combinations(
                combinations_to_test, all_word_embeddings, target_embedding, test_alphas
            )

            # Add to cache
            for combo in new_combinations_scores:
                cache_key = f"{combo['word1']}+{combo['word2']}"
                self.semantic_scores_cache[cache_key] = combo

        # Update tracking
        self.last_processed_elements = set(available_words)

        # Step 4: Return top results from merged cache
        return self._get_top_from_cache(top_k, cache_service)

    def _get_top_from_cache(self, top_k: int, cache_service) -> List[Dict]:
        """Get top combinations from semantic scores cache, filtered against CURRENT combination cache state."""
        if not self.semantic_scores_cache:
            return []

        # ALWAYS filter against current combination cache state (this is key to avoiding repeats)
        filtered_combinations = []
        if cache_service:
            # ALWAYS check CURRENT cache state for each combination (IGNORE_CACHE only affects initial loading)
            cache_filter_count = 0
            for combo in self.semantic_scores_cache.values():
                is_tested = cache_service.is_combination_tested_by_names(combo["word1"], combo["word2"])
                if not is_tested:
                    filtered_combinations.append(combo)
                else:
                    cache_filter_count += 1
                    if cache_filter_count <= 3:  # Log first 3 filtered combinations
                        self.log("DEBUG", f"🔍 FILTERED OUT: {combo['word1']} + {combo['word2']} (already cached)")

            self.log(
                "INFO",
                f"🔍 Filtered semantic cache: {len(self.semantic_scores_cache)} total → {
                    len(filtered_combinations)} untested ({cache_filter_count} already cached)",
            )
        else:
            filtered_combinations = list(self.semantic_scores_cache.values())
            self.log(
                "WARNING", f"⚠️ No cache_service provided - using all {len(self.semantic_scores_cache)} combinations"
            )

        # Sort and return top results
        filtered_combinations.sort(key=lambda x: x["score"], reverse=True)
        top_combinations = filtered_combinations[:top_k]

        if top_combinations:
            self.log("INFO", f"🏆 Top {len(top_combinations)} untested combinations:")
            for i, combo in enumerate(top_combinations, 1):
                self.log(
                    "INFO", f"  {i}. {combo['word1']} + {combo['word2']} → {combo['score']:.3f} ({combo['confidence']})"
                )
        else:
            self.log("INFO", "⚠️ No untested combinations found in semantic cache")

        return top_combinations

    def _filter_cached_combinations(self, combinations: List[tuple], cache_service) -> List[tuple]:
        """Filter out already tested combinations. IGNORE_CACHE only affects initial loading, not runtime filtering."""
        if not cache_service:
            return combinations

        # ALWAYS filter during runtime (IGNORE_CACHE only affects initial cache loading)
        filtered = []
        for word1, word2 in combinations:
            if not cache_service.is_combination_tested_by_names(word1, word2):
                filtered.append((word1, word2))

        return filtered
