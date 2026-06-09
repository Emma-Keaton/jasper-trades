"""
Pattern Analyzer for Self-Learning AI
Uses ML to identify winning/losing patterns from trade history
"""
import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import joblib
import structlog
from datetime import datetime

logger = structlog.get_logger(__name__)

# Import Experience after definition to avoid circular import
from app.services.experience_buffer import Experience


class PatternAnalyzer:
    """
    Machine learning system that learns from trade history.
    Trains on закрытые positions to predict success probability of new trades.
    """
    
    def __init__(self):
        self.model_path = Path("data/models/pattern_model.joblib")
        self.model: Optional = None
        self.feature_names = [
            "vix", "is_bullish_trend", "rsi", "macd_signal", 
            "volume_ratio", "bb_position", "hold_hours"
        ]
        self.training_count = 0
        self.last_trained = None
        self.load_model()
    
    def prepare_features(self, experience: Experience) -> np.ndarray:
        """Convert experience to feature vector"""
        features = [
            experience.market_conditions.get("vix", 20),
            1 if experience.market_conditions.get("trend") == "bullish" else 0,
            experience.technical_features.get("rsi", 50),
            experience.technical_features.get("macd_signal", 0),
            experience.technical_features.get("volume_ratio", 1.0),
            experience.technical_features.get("bb_position", 0.5),
            experience.hold_duration_minutes / 60,  # Convert to hours
        ]
        return np.array(features, dtype=np.float32)
    
    def train_from_experiences(self, experiences: List[Experience], force: bool = False) -> bool:
        """
        Train ML model on historical trades.
        Returns True if training was successful.
        """
        if len(experiences) < 30 and not force:
            logger.debug(f"Not enough experiences for training: {len(experiences)} < 30")
            return False
        
        # Prepare training data
        X = []
        y = []  # 1 = win, 0 = loss
        
        for exp in experiences:
            # Skip incomplete or breakeven trades
            if exp.outcome == "BREAKEVEN" or exp.exit_price is None:
                continue
            
            features = self.prepare_features(exp)
            X.append(features)
            y.append(1 if exp.outcome == "WIN" else 0)
        
        if len(X) < 20:
            logger.debug(f"Not enough valid samples after filtering: {len(X)}")
            return False
        
        # Convert to numpy arrays
        X_arr = np.array(X)
        y_arr = np.array(y)
        
        # Train Random Forest classifier
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import cross_val_score
            
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=6,
                min_samples_split=5,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1
            )
            
            self.model.fit(X_arr, y_arr)
            self.training_count += 1
            self.last_trained = datetime.utcnow()
            
            # Evaluate
            cv_scores = cross_val_score(self.model, X_arr, y_arr, cv=3)
            accuracy = cv_scores.mean()
            
            self.save_model()
            
            win_rate = sum(y_arr) / len(y_arr)
            logger.info(
                f"Pattern model trained: {len(X)} samples, "
                f"CV accuracy: {accuracy:.2f}, win rate: {win_rate:.2f}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Pattern model training failed: {e}")
            return False
    
    def predict_success_probability(
        self, 
        market_conditions: Dict, 
        technical_features: Dict,
        expected_hold_hours: float = 4
    ) -> Tuple[float, Optional[str]]:
        """
        Predict probability of success for current market setup.
        Returns (probability, confidence_level) where confidence_level is HIGH/MEDIUM/LOW
        """
        if self.model is None:
            return 0.5, None
        
        # Build feature vector
        features = np.array([[
            market_conditions.get("vix", 20),
            1 if market_conditions.get("trend") == "bullish" else 0,
            technical_features.get("rsi", 50),
            technical_features.get("macd_signal", 0),
            technical_features.get("volume_ratio", 1.0),
            technical_features.get("bb_position", 0.5),
            expected_hold_hours,
        ]], dtype=np.float32)
        
        try:
            proba = self.model.predict_proba(features)[0]
            success_prob = float(proba[1])  # Probability of WIN
            
            # Determine confidence based on prediction certainty
            margin = abs(proba[1] - proba[0])
            if margin > 0.3:
                confidence = "HIGH"
            elif margin > 0.15:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"
            
            return success_prob, confidence
            
        except Exception as e:
            logger.error(f"Pattern prediction failed: {e}")
            return 0.5, None
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get importance of each feature in predictions"""
        if self.model is None:
            return {name: 0.0 for name in self.feature_names}
        
        importances = self.model.feature_importances_
        return dict(zip(self.feature_names, importances.tolist()))
    
    def get_what_if_analysis(
        self, 
        base_conditions: Dict, 
        base_features: Dict
    ) -> Dict[str, float]:
        """
        Analyze how changing individual factors affects success probability.
        Useful for explaining predictions to user.
        """
        baseline_prob, _ = self.predict_success_probability(base_conditions, base_features)
        
        analysis = {
            "baseline": baseline_prob,
            "factors": {}
        }
        
        # Test RSI impact
        for rsi_val in [25, 50, 75]:
            test_features = base_features.copy()
            test_features["rsi"] = rsi_val
            prob, _ = self.predict_success_probability(base_conditions, test_features)
            analysis["factors"][f"rsi_{rsi_val}"] = prob
        
        # Test VIX impact
        for vix_val in [15, 25, 35]:
            test_conditions = base_conditions.copy()
            test_conditions["vix"] = vix_val
            prob, _ = self.predict_success_probability(test_conditions, base_features)
            analysis["factors"][f"vix_{vix_val}"] = prob
        
        # Test trend impact
        for trend in ["bullish", "bearish"]:
            test_conditions = base_conditions.copy()
            test_conditions["trend"] = trend
            prob, _ = self.predict_success_probability(test_conditions, base_features)
            analysis["factors"][f"trend_{trend}"] = prob
        
        return analysis
    
    def save_model(self) -> None:
        """Persist model to disk"""
        self.model_path.parent.mkdir(exist_ok=True)
        joblib.dump(self.model, self.model_path)
        logger.debug(f"Pattern model saved to {self.model_path}")
    
    def load_model(self) -> None:
        """Load existing model from disk"""
        if self.model_path.exists():
            try:
                self.model = joblib.load(self.model_path)
                logger.info("Pattern model loaded from disk")
            except Exception as e:
                logger.error(f"Failed to load pattern model: {e}")
                self.model = None
    
    def get_training_status(self) -> Dict:
        """Get model training status"""
        return {
            "trained": self.model is not None,
            "training_count": self.training_count,
            "last_trained": self.last_trained.isoformat() if self.last_trained else None,
            "feature_importance": self.get_feature_importance(),
        }