"""
DuckDB storage for Kronos predictions.
File-based storage to minimize RAM usage on 4GB systems.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import duckdb
import structlog
from pathlib import Path

from app.config import settings

logger = structlog.get_logger(__name__)


class KronosPredictionStore:
    """
    Store Kronos predictions in DuckDB (file-based, not RAM).
    
    Critical for 4GB systems: Predictions are written to disk immediately,
    not cached in memory.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(settings.DATA_DIR) / "kronos_predictions.duckdb"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
        logger.info(f"Initialized Kronos prediction store at {db_path}")
    
    def _init_db(self):
        """Initialize DuckDB schema."""
        conn = duckdb.connect(str(self.db_path))
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id BIGINT PRIMARY KEY DEFAULT nextval('seq_predictions'),
                symbol VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                model_name VARCHAR NOT NULL,
                forecast_horizon INTEGER NOT NULL,
                predictions DOUBLE[] NOT NULL,
                confidence_lower DOUBLE[],
                confidence_upper DOUBLE[],
                predicted_return DOUBLE,
                current_price DOUBLE,
                timeframe VARCHAR DEFAULT '1h',
                prediction_data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seq_predictions (
                seq_value BIGINT DEFAULT 0
            )
        """)
        
        conn.execute("""
            INSERT OR IGNORE INTO seq_predictions (seq_value) SELECT COALESCE(MAX(id), 0) + 1 FROM predictions
        """)
        
        # Create index for fast lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_predictions_symbol 
            ON predictions (symbol, timestamp DESC)
        """)
        
        conn.commit()
        conn.close()
    
    def save_prediction(
        self,
        symbol: str,
        predictions: List[float],
        model_name: str,
        forecast_horizon: int,
        current_price: float,
        confidence_lower: Optional[List[float]] = None,
        confidence_upper: Optional[List[float]] = None,
        predicted_return: Optional[float] = None,
        timeframe: str = '1h',
        prediction_data: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Save a prediction to DuckDB.
        """
        conn = duckdb.connect(str(self.db_path))
        
        # Get next sequence value
        result = conn.execute("SELECT nextval('seq_predictions')").fetchone()
        prediction_id = result[0]
        
        # Insert prediction
        conn.execute("""
            INSERT INTO predictions (
                id, symbol, timestamp, model_name, forecast_horizon,
                predictions, confidence_lower, confidence_upper,
                predicted_return, current_price, timeframe, prediction_data
            ) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            prediction_id,
            symbol,
            model_name,
            forecast_horizon,
            predictions,
            confidence_lower,
            confidence_upper,
            predicted_return,
            current_price,
            timeframe,
            str(prediction_data) if prediction_data else None,
        ])
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Saved prediction {prediction_id} for {symbol}")
        return prediction_id
    
    def get_latest_prediction(self, symbol: str, timeframe: str = '1h') -> Optional[Dict[str, Any]]:
        """Get the most recent prediction for a symbol."""
        conn = duckdb.connect(str(self.db_path))
        
        result = conn.execute("""
            SELECT id, symbol, timestamp, model_name, forecast_horizon,
                   predictions, confidence_lower, confidence_upper,
                   predicted_return, current_price, timeframe, prediction_data
            FROM predictions
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, [symbol, timeframe]).fetchone()
        
        conn.close()
        
        if result is None:
            return None
        
        return {
            "id": result[0],
            "symbol": result[1],
            "timestamp": result[2],
            "model_name": result[3],
            "forecast_horizon": result[4],
            "predictions": result[5],
            "confidence_lower": result[6],
            "confidence_upper": result[7],
            "predicted_return": result[8],
            "current_price": result[9],
            "timeframe": result[10],
            "prediction_data": result[11],
        }
    
    def get_predictions_for_symbols(
        self,
        symbols: List[str],
        timeframe: str = '1h',
        limit_per_symbol: int = 1,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get latest predictions for multiple symbols."""
        conn = duckdb.connect(str(self.db_path))
        
        results = {}
        for symbol in symbols:
            predictions = conn.execute("""
                SELECT id, symbol, timestamp, model_name, forecast_horizon,
                       predictions, confidence_lower, confidence_upper,
                       predicted_return, current_price, timeframe, prediction_data
                FROM predictions
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, [symbol, timeframe, limit_per_symbol]).fetchall()
            
            results[symbol] = [
                {
                    "id": p[0],
                    "symbol": p[1],
                    "timestamp": p[2],
                    "model_name": p[3],
                    "forecast_horizon": p[4],
                    "predictions": p[5],
                    "confidence_lower": p[6],
                    "confidence_upper": p[7],
                    "predicted_return": p[8],
                    "current_price": p[9],
                    "timeframe": p[10],
                    "prediction_data": p[11],
                }
                for p in predictions
            ]
        
        conn.close()
        return results
    
    def get_top_k_predictions(
        self,
        k: int = 10,
        timeframe: str = '1h',
        min_confidence: float = 0.02,
    ) -> List[Dict[str, Any]]:
        """Get top-K predictions by predicted return (Top-K Strategy)."""
        conn = duckdb.connect(str(self.db_path))
        
        results = conn.execute("""
            SELECT id, symbol, timestamp, model_name, forecast_horizon,
                   predictions, confidence_lower, confidence_upper,
                   predicted_return, current_price, timeframe, prediction_data
            FROM predictions
            WHERE timeframe = ?
              AND timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
              AND predicted_return IS NOT NULL
            ORDER BY predicted_return DESC
            LIMIT ?
        """, [timeframe, k]).fetchall()
        
        conn.close()
        
        return [
            {
                "id": p[0],
                "symbol": p[1],
                "timestamp": p[2],
                "model_name": p[3],
                "forecast_horizon": p[4],
                "predictions": p[5],
                "confidence_lower": p[6],
                "confidence_upper": p[7],
                "predicted_return": p[8],
                "current_price": p[9],
                "timeframe": p[10],
                "prediction_data": p[11],
            }
            for p in results
            if p[8] is not None and abs(p[8]) >= min_confidence
        ]
    
    def cleanup_old_predictions(self, max_age_hours: int = 24):
        """Remove predictions older than max_age_hours."""
        conn = duckdb.connect(str(self.db_path))
        
        result = conn.execute("""
            DELETE FROM predictions
            WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '? hours'
        """, [max_age_hours])
        
        deleted = result.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Cleaned up {deleted} old predictions")
        return deleted
    
    def get_stats(self) -> Dict[str, Any]:
        """Get prediction store statistics."""
        conn = duckdb.connect(str(self.db_path))
        
        total = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        
        symbol_count = conn.execute(
            "SELECT COUNT(DISTINCT symbol) FROM predictions"
        ).fetchone()[0]
        
        timeframes = conn.execute("""
            SELECT timeframe, COUNT(*) as count
            FROM predictions
            GROUP BY timeframe
        """).fetchall()
        
        conn.close()
        
        return {
            "total_predictions": total,
            "unique_symbols": symbol_count,
            "timeframes": {tf[0]: tf[1] for tf in timeframes},
            "db_path": str(self.db_path),
            "db_size_mb": self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0,
        }


# Global instance
prediction_store = KronosPredictionStore()


def get_prediction_store() -> KronosPredictionStore:
    """Get the prediction store instance."""
    return prediction_store